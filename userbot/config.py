"""
IBEKS USERBOT - Configuration
Membaca semua konfigurasi dari environment variables (Replit Secrets).
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ── Telegram credentials ──────────────────────────────────────────────────────
API_ID: int = int(os.environ.get("API_ID", 0))
API_HASH: str = os.environ.get("API_HASH", "")
STRING_SESSION: str = os.environ.get("STRING_SESSION", "")
OWNER_ID: int = int(os.environ.get("OWNER_ID", 0) or 0)
MANAGER_BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "").strip()


def _manager_bot_id_from_token(token: str) -> int:
    """Ambil ID Bot Manager dari token tanpa pernah mencatat tokennya."""
    try:
        bot_id = int(token.split(":", 1)[0])
    except (AttributeError, ValueError, IndexError):
        return 0
    return bot_id if bot_id > 0 else 0


MANAGER_BOT_ID: int = _manager_bot_id_from_token(MANAGER_BOT_TOKEN)

_MANAGER_BOT_USERNAME: str = (
    os.environ.get("MANAGER_BOT_USERNAME", os.environ.get("BOT_USERNAME", ""))
    .strip()
    .lstrip("@")
)


def get_manager_bot_username() -> str:
    """Ambil username Bot Manager dari env atau via getMe Telegram Bot API."""
    global _MANAGER_BOT_USERNAME
    if _MANAGER_BOT_USERNAME:
        return _MANAGER_BOT_USERNAME
    if not MANAGER_BOT_TOKEN:
        return ""
    try:
        import json
        import urllib.request

        url = f"https://api.telegram.org/bot{MANAGER_BOT_TOKEN}/getMe"
        req = urllib.request.Request(url, headers={"User-Agent": "TELEUB-Userbot"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok") and "result" in data:
                uname = data["result"].get("username", "")
                if uname:
                    _MANAGER_BOT_USERNAME = str(uname).lstrip("@")
                    return _MANAGER_BOT_USERNAME
    except Exception:
        pass
    return ""


MANAGER_BOT_USERNAME: str = get_manager_bot_username()

# ── Bot metadata ──────────────────────────────────────────────────────────────
BOT_NAME: str = "IBEKS USERBOT"
VERSION: str = "1.0.0"
CMD_PREFIX: str = "."  # Default fallback; prefix aktif dibaca dari database

# ── Paths ─────────────────────────────────────────────────────────────────────
SOURCE_DIR: str = os.path.dirname(os.path.abspath(__file__))
BASE_DIR: str = os.environ.get("IBEKS_USERBOT_RUNTIME_DIR", SOURCE_DIR)
MANAGER_DATABASE_PATH: str = os.path.join(
    os.environ.get(
        "IBEKS_MANAGER_DATABASE_PATH",
        os.path.join(SOURCE_DIR, "..", "manager", "database.db"),
    )
)
PLUGINS_DIR: str = os.path.join(SOURCE_DIR, "plugins")
DATABASE_PATH: str = os.path.join(BASE_DIR, "database.db")
LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
MAIN_FILE: str = os.path.join(SOURCE_DIR, "main.py")

# ── Restart state ─────────────────────────────────────────────────────────────
RESTART_STATE_FILE: str = os.path.join(BASE_DIR, ".restart_state")
RUNNER_READY_FILE: str = os.environ.get(
    "IBEKS_RUNNER_READY_FILE",
    os.path.join(BASE_DIR, ".runner_ready"),
)
HELP_REQUEST_PATH: str = os.environ.get(
    "IBEKS_HELP_REQUEST_PATH",
    os.path.join(BASE_DIR, ".help_request.json"),
)
PANEL_REQUEST_PATH: str = os.environ.get(
    "IBEKS_PANEL_REQUEST_PATH",
    os.path.join(BASE_DIR, ".panel_request.json"),
)
VOICE_REQUEST_PATH: str = os.environ.get(
    "IBEKS_VOICE_REQUEST_PATH",
    os.path.join(BASE_DIR, ".voice_request.json"),
)
VOICE_ACTION_PATH: str = os.environ.get(
    "IBEKS_VOICE_ACTION_PATH",
    os.path.join(BASE_DIR, ".voice_action.json"),
)
VOICE_RESPONSE_PATH: str = os.environ.get(
    "IBEKS_VOICE_RESPONSE_PATH",
    os.path.join(BASE_DIR, ".voice_response.json"),
)
CLONE_REQUEST_PATH: str = os.environ.get(
    "IBEKS_CLONE_REQUEST_PATH",
    os.path.join(BASE_DIR, ".clone_request.json"),
)
CLONE_ACTION_PATH: str = os.environ.get(
    "IBEKS_CLONE_ACTION_PATH",
    os.path.join(BASE_DIR, ".clone_action.json"),
)
CLONE_RESPONSE_PATH: str = os.environ.get(
    "IBEKS_CLONE_RESPONSE_PATH",
    os.path.join(BASE_DIR, ".clone_response.json"),
)

# ── Auto-delete delay (detik) ─────────────────────────────────────────────────
AUTO_DELETE_CMD: int = 5   # Hapus pesan command setelah N detik
