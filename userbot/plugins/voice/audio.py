"""
IBEKS USERBOT - Voice Clone / Audio Processing & Validation
Modul pemrosesan, konversi, dan validasi kelayakan sample audio untuk Voice Cloning.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

from plugins.voice.config import (
    MAX_AUDIO_DURATION,
    MAX_MEAN_VOLUME_DB,
    MIN_AUDIO_DURATION,
    MIN_MAX_VOLUME_DB,
    MIN_MEAN_VOLUME_DB,
    RECOMMENDED_MAX_DURATION,
    RECOMMENDED_MIN_DURATION,
)
from utils.logger import log

__version__ = "1.0.0"
__author__ = "IBEKS"


def get_audio_info(file_path: str) -> dict[str, Any]:
    """
    Ekstrak informasi audio (durasi, codec, sample rate, channels) menggunakan ffprobe.
    """
    if not os.path.exists(file_path):
        return {"valid": False, "error": "File audio tidak ditemukan."}

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return {"valid": False, "error": "File audio rusak atau format tidak dapat dibaca."}

        data = json.loads(res.stdout or "{}")
        streams = data.get("streams", [])
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        format_info = data.get("format", {})

        if not audio_stream:
            return {"valid": False, "error": "Tidak ditemukan stream audio dalam file."}

        duration = 0.0
        if "duration" in format_info and format_info["duration"]:
            try:
                duration = float(format_info["duration"])
            except ValueError:
                duration = 0.0
        elif "duration" in audio_stream and audio_stream["duration"]:
            try:
                duration = float(audio_stream["duration"])
            except ValueError:
                duration = 0.0

        sample_rate = int(audio_stream.get("sample_rate", 0) or 0)
        channels = int(audio_stream.get("channels", 0) or 0)

        return {
            "valid": True,
            "duration": duration,
            "sample_rate": sample_rate,
            "channels": channels,
            "codec": audio_stream.get("codec_name", "unknown"),
        }
    except Exception as exc:
        log.warning("[VoiceAudio] Gagal mengecek audio info %s: %s", file_path, exc)
        return {"valid": False, "error": f"Gagal menganalisis audio: {exc}"}


def check_audio_levels(file_path: str) -> dict[str, float]:
    """
    Hitung level volume (mean_volume dan max_volume dalam dB) menggunakan filter volumedetect ffmpeg.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i", file_path,
        "-af", "volumedetect",
        "-vn", "-sn", "-dn",
        "-f", "null",
        "/dev/null",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        stderr = res.stderr or ""

        mean_match = re.search(r"mean_volume:\s*([-0-9.]+)\s*dB", stderr)
        max_match = re.search(r"max_volume:\s*([-0-9.]+)\s*dB", stderr)

        mean_vol = float(mean_match.group(1)) if mean_match else -99.0
        max_vol = float(max_match.group(1)) if max_match else -99.0

        return {"mean_volume": mean_vol, "max_volume": max_vol}
    except Exception as exc:
        log.warning("[VoiceAudio] Gagal mengukur volume %s: %s", file_path, exc)
        return {"mean_volume": -30.0, "max_volume": -10.0}


def validate_and_convert_sample(
    input_path: str,
    output_wav_path: str,
) -> tuple[bool, str, float]:
    """
    Validasi kelayakan sample suara sesuai standar Qwen / Model Studio:
      - Minimal sekitar 5 detik suara jelas.
      - Rekomendasi 10–20 detik.
      - Memeriksa keheningan (silent audio) & noise berlebih / distorsi.
      - Mengonversi audio ke format standar WAV 24kHz Mono PCM 16-bit.

    Returns
    -------
    tuple[bool, str, float]
        (is_valid, message, duration)
    """
    info = get_audio_info(input_path)
    if not info.get("valid"):
        return False, info.get("error", "Audio tidak dapat diproses."), 0.0

    duration = info.get("duration", 0.0)

    # 1. Cek Durasi Minimal (Standar Qwen: minimal ~5 detik)
    if duration < MIN_AUDIO_DURATION:
        return (
            False,
            f"❌ Durasi audio terlalu pendek: `{duration:.1f} detik`.\n"
            f"⚠️ Minimal durasi adalah `{MIN_AUDIO_DURATION:.0f} detik` "
            f"(direkomendasikan `{RECOMMENDED_MIN_DURATION:.0f}–{RECOMMENDED_MAX_DURATION:.0f} detik`).",
            duration,
        )

    if duration > MAX_AUDIO_DURATION:
        return (
            False,
            f"❌ Durasi audio terlalu panjang: `{duration:.1f} detik` (maksimal `{MAX_AUDIO_DURATION:.0f} detik`).",
            duration,
        )

    # 2. Cek Level Volume (Deteksi keheningan / noise berlebih)
    levels = check_audio_levels(input_path)
    mean_vol = levels.get("mean_volume", -99.0)
    max_vol = levels.get("max_volume", -99.0)

    # Terlalu hening / tidak ada suara vokal manusia yang terdengar jelas
    if max_vol < MIN_MAX_VOLUME_DB or mean_vol < MIN_MEAN_VOLUME_DB:
        return (
            False,
            "❌ Audio terlalu hening atau tidak terdeteksi suara yang jelas.\n"
            "⚠️ Pastikan rekaman suara terdengar jelas dan tidak berbisik.",
            duration,
        )

    # Terlalu berisik / clipping / suara rusak parah
    if mean_vol > MAX_MEAN_VOLUME_DB:
        return (
            False,
            "❌ Audio terlalu berisik atau terjadi distorsi ekstrem (clipping).\n"
            "⚠️ Rekam ulang di lingkungan yang lebih tenang tanpa noise berlebih.",
            duration,
        )

    # 3. Konversi ke WAV 24kHz mono PCM 16-bit yang bersih
    os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
    conv_cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "24000",
        "-c:a", "pcm_s16le",
        output_wav_path,
    ]
    try:
        res = subprocess.run(conv_cmd, capture_output=True, text=True, timeout=20)
        if res.returncode != 0 or not os.path.exists(output_wav_path):
            return False, "❌ Gagal mengonversi sample audio ke format standar WAV.", duration
    except Exception as exc:
        return False, f"❌ Terjadi kesalahan saat memproses audio: {exc}", duration

    return True, "✅ Sample suara valid dan berhasil diproses.", duration


def convert_to_telegram_voice(input_path: str, output_ogg_path: str) -> bool:
    """
    Konversi file audio hasil TTS ke format Voice Note Telegram (OGG OPUS).
    """
    os.makedirs(os.path.dirname(output_ogg_path), exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-c:a", "libopus",
        "-b:a", "32k",
        "-vbr", "on",
        output_ogg_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return res.returncode == 0 and os.path.exists(output_ogg_path)
    except Exception as exc:
        log.error("[VoiceAudio] Gagal mengonversi ke voice ogg: %s", exc)
        return False


def concatenate_samples(sample_paths: list[str], output_combined_path: str) -> bool:
    """
    Gabungkan beberapa sample audio menjadi satu file WAV komposit untuk training/enrollment.
    """
    if not sample_paths:
        return False
    if len(sample_paths) == 1:
        # Salin satu sample jika hanya ada 1
        try:
            import shutil
            shutil.copyfile(sample_paths[0], output_combined_path)
            return True
        except Exception:
            return False

    os.makedirs(os.path.dirname(output_combined_path), exist_ok=True)
    list_txt_path = f"{output_combined_path}.list.txt"
    try:
        with open(list_txt_path, "w", encoding="utf-8") as f:
            for sp in sample_paths:
                if os.path.exists(sp):
                    f.write(f"file '{os.path.abspath(sp)}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_txt_path,
            "-ac", "1",
            "-ar", "24000",
            "-c:a", "pcm_s16le",
            output_combined_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res.returncode == 0 and os.path.exists(output_combined_path)
    except Exception as exc:
        log.error("[VoiceAudio] Gagal menggabungkan sample: %s", exc)
        return False
    finally:
        if os.path.exists(list_txt_path):
            try:
                os.remove(list_txt_path)
            except Exception:
                pass


def setup(client: Any) -> None:
    """Setup hook untuk plugin loader."""
    pass
