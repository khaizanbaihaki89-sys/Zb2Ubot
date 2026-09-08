"""
IBEKS USERBOT - Voice Clone / TTS Configuration
Konfigurasi direktori, API key, model, dan parameter audio untuk Fish Audio Voice Cloning & TTS.
"""

from __future__ import annotations

import os
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

__version__ = "1.0.0"
__author__ = "IBEKS"

# ── API Key Secrets ──────────────────────────────────────────────────────────
# Menggunakan FISH_API_KEY dari environment variable
FISH_API_KEY: str = os.environ.get("FISH_API_KEY", "").strip()

# ── Paths & Data Directory ───────────────────────────────────────────────────
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Cek root project atau userbot directory
_USERBOT_DIR = os.path.dirname(os.path.dirname(_CURRENT_DIR))
_WORKSPACE_ROOT = os.path.dirname(_USERBOT_DIR)

# Prioritaskan data/voice di workspace root atau userbot/data/voice
_CANDIDATE_DATA_DIRS = [
    os.path.join(_WORKSPACE_ROOT, "data", "voice"),
    os.path.join(_USERBOT_DIR, "data", "voice"),
]
DATA_VOICE_DIR = _CANDIDATE_DATA_DIRS[0]
for d in _CANDIDATE_DATA_DIRS:
    if os.path.exists(d):
        DATA_VOICE_DIR = d
        break

os.makedirs(DATA_VOICE_DIR, exist_ok=True)
PROFILES_DIR: str = os.path.join(DATA_VOICE_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)
SETTINGS_FILE: str = os.path.join(DATA_VOICE_DIR, "settings.json")

# ── Fish Audio Voice Clone & TTS Parameters ──────────────────────────────────
FISH_AUDIO_BASE_URL: str = "https://api.fish.audio"
TTS_MODEL: str = os.environ.get("FISH_TTS_MODEL", "s2.1-pro-free").strip()

# ── Audio Quality & Duration Constraints ────────────────────────────────────
MIN_AUDIO_DURATION: float = 5.0          # Minimal 5 detik suara jelas
RECOMMENDED_MIN_DURATION: float = 10.0   # Rekomendasi minimal 10 detik
RECOMMENDED_MAX_DURATION: float = 60.0   # Rekomendasi maksimal 60 detik per sample
MAX_AUDIO_DURATION: float = 180.0        # Batas maksimal durasi per sample

# Batas level audio (dB) untuk deteksi keheningan / noise berlebih
MIN_MAX_VOLUME_DB: float = -42.0         # Jika suara puncak < -42 dB, dianggap terlalu hening/tidak jelas
MIN_MEAN_VOLUME_DB: float = -55.0        # Rata-rata minimal agar tidak kosong
MAX_MEAN_VOLUME_DB: float = -6.0         # Jika rata-rata > -6 dB, kemungkinan distorsi/clipping


def get_api_key() -> str:
    """Ambil API Key Fish Audio secara dinamis dan selalu perbarui dari environment / .env."""
    try:
        from dotenv import load_dotenv
        # Cek .env di workspace root, userbot/, atau manager/
        for p in [
            os.path.join(_WORKSPACE_ROOT, ".env"),
            os.path.join(_USERBOT_DIR, ".env"),
            os.path.join(_WORKSPACE_ROOT, "manager", ".env"),
        ]:
            if os.path.exists(p):
                load_dotenv(p, override=True)
    except Exception:
        pass

    return os.environ.get("FISH_API_KEY", "").strip()


def setup(client: Any) -> None:
    """Setup hook untuk plugin loader."""
    pass

