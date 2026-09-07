"""
IBEKS USERBOT - Voice Clone / TTS Synthesis Engine
Integrasi Fish Audio Voice Cloning & Speech Synthesis API (Model s2.1-pro-free).
Menggunakan modul bawaan Python (urllib.request) untuk keandalan maksimal tanpa dependensi eksternal.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
import uuid
from typing import Any

from plugins.voice.audio import convert_to_telegram_voice
from plugins.voice.config import (
    FISH_AUDIO_BASE_URL,
    TTS_MODEL,
    get_api_key,
)
from plugins.voice.profiles import (
    get_profile,
    get_profile_audio_for_enrollment,
    update_profile_voice_id,
)
from utils.logger import log

__version__ = "1.0.0"
__author__ = "IBEKS"

ACCENT_CUES: dict[str, str] = {
    "normal": "",
    "sunda": "Indonesian Sundanese accent",
    "jawa": "Indonesian Javanese accent",
    "ngapak": "Banyumasan Ngapak Indonesian accent",
    "cirebon": "Cirebonese Indonesian accent",
    "betawi": "Betawi Indonesian accent",
    "medan": "Medan Indonesian accent",
    "palu": "Palu Indonesian accent",
    "jaksel": "Jakarta Selatan Indonesian accent with a natural English mix",
    "inggris": "natural English accent",
    "korea": "natural Korean accent while preserving the original words",
    "mandarin": "natural Mandarin Chinese accent while preserving the original words",
}

ACCENT_LABELS: dict[str, str] = {
    "normal": "Normal",
    "sunda": "Sunda",
    "jawa": "Jawa",
    "ngapak": "Ngapak",
    "cirebon": "Cirebon",
    "betawi": "Betawi",
    "medan": "Medan",
    "palu": "Palu",
    "jaksel": "Jaksel",
    "inggris": "Inggris",
    "korea": "Korea",
    "mandarin": "Mandarin",
}

INTONATION_CUES: dict[str, tuple[str, str]] = {
    "shouting": ("Teriak / Sangat Tegas", "shouting"),
    "firm": ("Marah / Tegas", "angry and firm"),
    "excited": ("Antusias / Senang", "excited and happy"),
    "sad": ("Sedih / Kecewa", "sad and disappointed"),
    "surprised": ("Kaget", "surprised"),
    "uncertain": ("Bingung / Ragu", "confused and uncertain"),
    "gentle": ("Lembut / Santai", "gentle and relaxed"),
    "ending": ("Berhenti / Akhir Kalimat", "natural sentence ending"),
    "pause": ("Jeda Napas", "a natural breathing pause"),
    "normal": ("Normal", ""),
}


def detect_intonation(text: str) -> dict[str, str]:
    """Deteksi gaya dari punctuation tanpa menghapus punctuation asli."""
    source = str(text or "")
    letters = "".join(character for character in source if character.isalpha())

    if "!!!" in source and letters and letters.isupper():
        key = "shouting"
    elif "!!!" in source:
        key = "firm"
    elif "?!" in source or "!?" in source:
        key = "surprised"
    elif "..." in source:
        key = "sad"
    elif "!!" in source:
        key = "excited"
    elif "??" in source:
        key = "uncertain"
    elif "~" in source:
        key = "gentle"
    elif "." in source:
        key = "ending"
    elif "," in source:
        key = "pause"
    else:
        key = "normal"

    label, cue = INTONATION_CUES[key]
    return {"key": key, "label": label, "cue": cue}


def prepare_tts_text(text: str, accent: str = "normal") -> str:
    """Tambahkan cue Fish Audio secara internal dan pertahankan teks asli."""
    clean_text = str(text or "").strip()
    accent_key = str(accent or "normal").strip().lower()
    accent_instruction = ACCENT_CUES.get(accent_key, "")
    intonation = detect_intonation(clean_text)

    cues = []
    if accent_instruction:
        cues.append(f"[{accent_instruction}]")
    if intonation["cue"]:
        cues.append(f"[{intonation['cue']}]")

    if not cues:
        return clean_text
    return f"{' '.join(cues)} {clean_text}".strip()


def _http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 60,
) -> tuple[int, bytes, dict[str, str]]:
    """Helper fungsi HTTP request menggunakan urllib standar."""
    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            content = resp.read()
            resp_headers = dict(resp.headers)
            return status_code, content, resp_headers
    except urllib.error.HTTPError as err:
        error_body = err.read() if hasattr(err, "read") else b""
        return err.code, error_body, dict(err.headers) if hasattr(err, "headers") else {}
    except Exception as exc:
        raise exc


def _http_post_multipart(
    url: str,
    headers: dict[str, str],
    form_data: dict[str, str],
    files: list[tuple[str, str, bytes, str]],
    timeout: int = 60,
) -> tuple[int, bytes]:
    """Mengirim multipart/form-data untuk upload file audio ke Fish Audio."""
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = bytearray()

    # Form fields
    for key, value in form_data.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{value}\r\n".encode("utf-8"))

    # File fields
    for field_name, filename, file_bytes, content_type in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_bytes)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req_headers = dict(headers)
    req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req_headers["Content-Length"] = str(len(body))

    status_code, resp_bytes, _ = _http_request(
        url=url,
        method="POST",
        headers=req_headers,
        data=bytes(body),
        timeout=timeout,
    )
    return status_code, resp_bytes


def enroll_voice_clone(profile_name: str) -> tuple[bool, str, str | None]:
    """
    Daftarkan atau perbarui Voice Clone ke Fish Audio API.
    Endpoint: POST /model
    """
    api_key = get_api_key()
    if not api_key:
        return (
            False,
            "❌ API Key `FISH_API_KEY` belum disetel. Tambahkan `FISH_API_KEY` pada environment variables / secrets!",
            None,
        )

    profile = get_profile(profile_name)
    if not profile:
        return False, f"❌ Profil suara `{profile_name}` tidak ditemukan.", None

    if not profile.get("samples"):
        return (
            False,
            f"❌ Profil suara `{profile_name}` belum memiliki sample audio. Gunakan `.voice add {profile_name}` terlebih dahulu.",
            None,
        )

    # Jika voice_id sudah ada dan masih tercatat, gunakan kembali
    existing_voice_id = profile.get("voice_id")
    if existing_voice_id:
        return True, "Voice ID sudah terdaftar.", existing_voice_id

    audio_path = get_profile_audio_for_enrollment(profile_name)
    if not audio_path or not os.path.exists(audio_path):
        return (
            False,
            f"❌ File audio untuk profil `{profile_name}` tidak ditemukan di penyimpanan.",
            None,
        )

    url = f"{FISH_AUDIO_BASE_URL}/model"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        form_data = {
            "type": "tts",
            "title": profile.get("name", profile_name).strip(),
            "train_mode": "fast",
            "visibility": "private",
            "enhance_audio_quality": "true",
            "description": f"Voice clone for {profile_name} created via IBEKS Userbot",
        }
        files = [
            ("voices", os.path.basename(audio_path), audio_bytes, "audio/wav"),
        ]

        status_code, resp_bytes = _http_post_multipart(
            url=url,
            headers=headers,
            form_data=form_data,
            files=files,
            timeout=60,
        )

        resp_text = resp_bytes.decode("utf-8", errors="replace")
        if status_code in (200, 201):
            res_data = json.loads(resp_text)
            voice_id = res_data.get("_id") or res_data.get("id")
            if voice_id:
                update_profile_voice_id(profile_name, voice_id)
                return True, "Voice clone berhasil didaftarkan ke Fish Audio.", voice_id
            return False, f"❌ Fish Audio tidak mengembalikan voice ID yang valid: {resp_text}", None
        else:
            try:
                err_json = json.loads(resp_text)
                detail = err_json.get("detail", {})
                if isinstance(detail, dict):
                    err_msg = detail.get("message", str(detail))
                elif isinstance(detail, list):
                    err_msg = "; ".join(str(d) for d in detail)
                else:
                    err_msg = str(detail)
            except Exception:
                err_msg = resp_text

            log.error("[FishAudio] Gagal enroll voice: %s (Status: %s)", err_msg, status_code)
            return False, f"❌ Gagal mendaftarkan voice clone Fish Audio ({status_code}): {err_msg}", None

    except Exception as exc:
        log.exception("[FishAudio] Exception saat enroll voice: %s", exc)
        return False, f"❌ Terjadi kesalahan jaringan ke Fish Audio: {exc}", None


def delete_voice_clone(voice_id: str) -> tuple[bool, str]:
    """
    Hapus voice model dari Fish Audio API.
    Endpoint: DELETE /model/{voice_id}
    """
    api_key = get_api_key()
    if not api_key or not voice_id:
        return False, "API Key atau Voice ID tidak tersedia."

    url = f"{FISH_AUDIO_BASE_URL}/model/{voice_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        status_code, resp_bytes, _ = _http_request(url, method="DELETE", headers=headers, timeout=20)
        resp_text = resp_bytes.decode("utf-8", errors="replace")
        if status_code in (200, 204, 404):
            return True, "Voice berhasil dihapus dari Fish Audio."
        else:
            return False, f"HTTP {status_code}: {resp_text}"
    except Exception as exc:
        log.warning("[FishAudio] Gagal menghapus voice %s: %s", voice_id, exc)
        return False, str(exc)


def generate_speech(
    profile_name: str,
    text: str,
    accent: str = "normal",
) -> tuple[bool, str, str | None]:
    """
    Sintesis teks menjadi suara (Voice Note) menggunakan Fish Audio TTS.
    Model default: s2.1-pro-free
    Returns
    -------
    tuple[bool, str, str | None]
        (success, status_message, ogg_file_path)
    """
    api_key = get_api_key()
    if not api_key:
        return (
            False,
            "❌ API Key `FISH_API_KEY` belum disetel. Tambahkan `FISH_API_KEY` pada environment variables / secrets!",
            None,
        )

    text = text.strip()
    if not text:
        return False, "❌ Teks yang akan disuarakan tidak boleh kosong.", None
    prepared_text = prepare_tts_text(text, accent)

    profile = get_profile(profile_name)
    if not profile:
        return (
            False,
            f"❌ Profil suara `{profile_name}` tidak ditemukan. Buat dulu dengan me-reply audio `.voice add {profile_name}`.",
            None,
        )

    # Pastikan voice_id tersedia (daftarkan clone jika belum ada)
    voice_id = profile.get("voice_id")
    if not voice_id:
        ok, msg, vid = enroll_voice_clone(profile_name)
        if not ok or not vid:
            return False, f"❌ Gagal mendaftarkan voice clone: {msg}", None
        voice_id = vid

    # Panggil Fish Audio Text-to-Speech API
    url = f"{FISH_AUDIO_BASE_URL}/v1/tts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": TTS_MODEL,
    }
    payload = {
        "text": prepared_text,
        "reference_id": voice_id,
        "format": "mp3",
        "latency": "normal",
        "normalize": True,
        "prosody": {
            "speed": 1,
            "volume": 0,
            "normalize_loudness": True,
        },
    }

    temp_raw_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_raw_audio.close()
    raw_audio_path = temp_raw_audio.name

    temp_ogg_voice = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
    temp_ogg_voice.close()
    ogg_voice_path = temp_ogg_voice.name

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        status_code, resp_bytes, _ = _http_request(
            url=url,
            method="POST",
            headers=headers,
            data=data_bytes,
            timeout=60,
        )

        if status_code == 200:
            with open(raw_audio_path, "wb") as f:
                f.write(resp_bytes)
        else:
            resp_text = resp_bytes.decode("utf-8", errors="replace")
            try:
                err_json = json.loads(resp_text)
                detail = err_json.get("detail", {})
                if isinstance(detail, dict):
                    err_msg = detail.get("message", str(detail))
                elif isinstance(detail, list):
                    err_msg = "; ".join(str(d) for d in detail)
                else:
                    err_msg = str(detail)
            except Exception:
                err_msg = resp_text

            log.error("[FishAudio] Gagal TTS: %s (Status: %s)", err_msg, status_code)
            return (
                False,
                f"❌ Gagal menghasilkan suara dari Fish Audio ({status_code}): {err_msg}",
                None,
            )

    except Exception as exc:
        log.exception("[FishAudio] Exception saat generate TTS: %s", exc)
        return False, f"❌ Terjadi kesalahan jaringan ke Fish Audio TTS: {exc}", None

    finally:
        # Bersihkan file jika kosong atau gagal
        if not os.path.exists(raw_audio_path) or os.path.getsize(raw_audio_path) == 0:
            if os.path.exists(raw_audio_path):
                try:
                    os.remove(raw_audio_path)
                except Exception:
                    pass
            if os.path.exists(ogg_voice_path):
                try:
                    os.remove(ogg_voice_path)
                except Exception:
                    pass

    if not os.path.exists(raw_audio_path) or os.path.getsize(raw_audio_path) == 0:
        return False, "❌ Audio yang dihasilkan dari Fish Audio kosong.", None

    # Konversi hasil audio ke format Voice Note Telegram (.ogg opus)
    ok_conv = convert_to_telegram_voice(raw_audio_path, ogg_voice_path)
    if os.path.exists(raw_audio_path):
        try:
            os.remove(raw_audio_path)
        except Exception:
            pass

    if not ok_conv or not os.path.exists(ogg_voice_path):
        return False, "❌ Gagal mengonversi hasil sintesis audio ke format Voice Note Telegram.", None

    return True, "✅ Voice Note berhasil dibuat.", ogg_voice_path


def get_voice_diagnostic() -> dict[str, Any]:
    """
    Diagnostik aman Fish Audio untuk memeriksa status koneksi, permission API Key,
    dan endpoint tanpa pernah menampilkan API key lengkap.
    """
    api_key = get_api_key()
    key_found = bool(api_key)
    masked_key = ("*" * (len(api_key) - 4) + api_key[-4:]) if len(api_key) >= 4 else ("****" if key_found else "None")

    endpoints_info = {
        "clone_endpoint": f"{FISH_AUDIO_BASE_URL}/model (POST multipart/form-data)",
        "tts_endpoint": f"{FISH_AUDIO_BASE_URL}/v1/tts (POST JSON)",
        "delete_endpoint": f"{FISH_AUDIO_BASE_URL}/model/{{id}} (DELETE)",
        "model": TTS_MODEL,
    }

    if not key_found:
        return {
            "key_found": False,
            "masked_key": "None",
            "model": TTS_MODEL,
            "endpoints": endpoints_info,
            "status": "API Key tidak ditemukan di environment.",
            "code": 0,
        }

    # Test koneksi endpoint Fish Audio model
    check_url = f"{FISH_AUDIO_BASE_URL}/model?page_size=1&self=true"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        status_code, resp_bytes, _ = _http_request(check_url, method="GET", headers=headers, timeout=10)
        if status_code == 200:
            status_desc = "Koneksi API Key Valid (Akses Fish Audio OK)"
        elif status_code == 401:
            status_desc = "API Key Tidak Valid / Unauthorized (401)"
        elif status_code == 403:
            status_desc = "API Key Tidak Memiliki Izin / Forbidden (403)"
        else:
            status_desc = f"HTTP {status_code}"
    except Exception as exc:
        status_code = -1
        status_desc = f"Koneksi Gagal: {exc}"

    return {
        "key_found": True,
        "masked_key": masked_key,
        "model": TTS_MODEL,
        "endpoints": endpoints_info,
        "status": status_desc,
        "code": status_code,
    }


def setup(client: Any) -> None:
    """Setup hook untuk plugin loader."""
    pass
