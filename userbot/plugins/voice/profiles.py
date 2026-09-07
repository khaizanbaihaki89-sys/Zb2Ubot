"""
IBEKS USERBOT - Voice Clone / Profile Management
Pengelolaan profil suara, penyimpanan sample WAV, dan metadata JSON di data/voice/profiles/.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any

from plugins.voice.audio import concatenate_samples
from plugins.voice.config import PROFILES_DIR
from utils.logger import log

__version__ = "1.0.0"
__author__ = "IBEKS"


def sanitize_profile_name(name: str) -> str:
    """Bersihkan nama profil agar aman digunakan sebagai nama direktori."""
    name = name.strip()
    slug = re.sub(r"[^\w\-]", "_", name).lower()
    return slug.strip("_") or "default_voice"


def get_profile_dir(name: str) -> str:
    """Ambil path direktori profil berdasarkan nama."""
    slug = sanitize_profile_name(name)
    return os.path.join(PROFILES_DIR, slug)


def get_profile_file(name: str) -> str:
    """Ambil path file profile.json."""
    return os.path.join(get_profile_dir(name), "profile.json")


def get_profile(name: str) -> dict[str, Any] | None:
    """
    Muat data profil dari disk jika ada.
    """
    json_path = get_profile_file(name)
    if not os.path.exists(json_path):
        # Cari case-insensitive jika slug sedikit berbeda
        slug = sanitize_profile_name(name)
        if os.path.exists(PROFILES_DIR):
            for entry in os.listdir(PROFILES_DIR):
                if entry.lower() == slug:
                    candidate = os.path.join(PROFILES_DIR, entry, "profile.json")
                    if os.path.exists(candidate):
                        json_path = candidate
                        break

    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.error("[VoiceProfiles] Gagal membaca profil %s: %s", name, exc)
        return None


def save_profile(name: str, data: dict[str, Any]) -> bool:
    """Simpan data profil ke file profile.json."""
    pdir = get_profile_dir(name)
    os.makedirs(pdir, exist_ok=True)
    json_path = get_profile_file(name)
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as exc:
        log.error("[VoiceProfiles] Gagal menyimpan profil %s: %s", name, exc)
        return False


def list_profiles() -> list[dict[str, Any]]:
    """
    Daftar semua profil suara yang tersimpan di data/voice/profiles/.
    """
    results: list[dict[str, Any]] = []
    if not os.path.exists(PROFILES_DIR):
        return results

    for entry in sorted(os.listdir(PROFILES_DIR)):
        entry_dir = os.path.join(PROFILES_DIR, entry)
        if os.path.isdir(entry_dir):
            json_file = os.path.join(entry_dir, "profile.json")
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        results.append(data)
                except Exception:
                    pass
    return results


def add_sample_to_profile(
    name: str,
    wav_sample_path: str,
    duration: float,
) -> tuple[bool, str, dict[str, Any] | None]:
    """
    Tambahkan sample suara baru ke profil.
    Jika profil belum ada, profil baru akan dibuat secara otomatis.
    Jika profil sudah ada, sample akan diakumulasikan ke profil yang sama.
    """
    pdir = get_profile_dir(name)
    os.makedirs(pdir, exist_ok=True)

    profile = get_profile(name)
    now_iso = datetime.now(timezone.utc).isoformat()

    if not profile:
        profile = {
            "name": name.strip(),
            "slug": sanitize_profile_name(name),
            "voice_id": None,
            "created_at": now_iso,
            "updated_at": now_iso,
            "total_duration": 0.0,
            "samples": [],
        }

    sample_id = len(profile.get("samples", [])) + 1
    sample_filename = f"sample_{sample_id}.wav"
    dest_path = os.path.join(pdir, sample_filename)

    try:
        shutil.copyfile(wav_sample_path, dest_path)
    except Exception as exc:
        return False, f"Gagal menyimpan file sample audio: {exc}", None

    sample_entry = {
        "id": sample_id,
        "filename": sample_filename,
        "duration": round(duration, 2),
        "added_at": now_iso,
    }

    profile.setdefault("samples", []).append(sample_entry)
    total_dur = sum(s.get("duration", 0.0) for s in profile["samples"])
    profile["total_duration"] = round(total_dur, 2)
    profile["updated_at"] = now_iso

    # Reset voice_id agar engine melakukan re-enrollment ke Fish Audio dengan sample komposit terbaru
    old_voice_id = profile.get("voice_id")
    if old_voice_id:
        try:
            from plugins.voice.tts import delete_voice_clone
            delete_voice_clone(old_voice_id)
        except Exception:
            pass
    profile["voice_id"] = None

    # Buat file komposit gabungan jika terdapat lebih dari 1 sample
    all_sample_paths = [
        os.path.join(pdir, s["filename"])
        for s in profile["samples"]
        if os.path.exists(os.path.join(pdir, s["filename"]))
    ]
    combined_wav_path = os.path.join(pdir, "combined.wav")
    concatenate_samples(all_sample_paths, combined_wav_path)

    save_profile(name, profile)
    return True, "Sample suara berhasil ditambahkan ke profil.", profile


def delete_profile(name: str) -> tuple[bool, str]:
    """Hapus seluruh data profil lokal dan voice clone di Fish Audio jika ada."""
    pdir = get_profile_dir(name)
    if not os.path.exists(pdir):
        return False, f"Profil suara `{name}` tidak ditemukan."

    profile = get_profile(name)
    if profile and profile.get("voice_id"):
        try:
            from plugins.voice.tts import delete_voice_clone
            delete_voice_clone(profile["voice_id"])
        except Exception as exc:
            log.warning("[VoiceProfiles] Gagal menghapus voice clone dari Fish Audio: %s", exc)

    try:
        shutil.rmtree(pdir)
        return True, f"Profil suara `{name}` dan seluruh sample berhasil dihapus."
    except Exception as exc:
        return False, f"Gagal menghapus profil `{name}`: {exc}"


def update_profile_voice_id(name: str, voice_id: str) -> bool:
    """Perbarui voice_id hasil pendaftaran dari Fish Audio API."""
    profile = get_profile(name)
    if not profile:
        return False
    profile["voice_id"] = voice_id
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    return save_profile(name, profile)


def get_profile_audio_for_enrollment(name: str) -> str | None:
    """
    Ambil file audio terbaik untuk enrollment:
    Jika ada combined.wav -> gunakan combined.wav.
    Jika tidak -> gunakan sample pertama yang tersedia.
    """
    pdir = get_profile_dir(name)
    combined = os.path.join(pdir, "combined.wav")
    if os.path.exists(combined):
        return combined

    profile = get_profile(name)
    if profile and profile.get("samples"):
        first_sample = profile["samples"][0].get("filename")
        if first_sample:
            sp = os.path.join(pdir, first_sample)
            if os.path.exists(sp):
                return sp
    return None


def setup(client: Any) -> None:
    """Setup hook untuk plugin loader."""
    pass
