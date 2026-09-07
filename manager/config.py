"""Konfigurasi mandiri IBEKS MANAGER BOT."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PLUGINS_DIR = BASE_DIR / "plugins"
LOGS_DIR = BASE_DIR / "logs"
ASSETS_DIR = BASE_DIR / "assets"
DATABASE_PATH = BASE_DIR / "database.db"
INSTANCE_LOCK_PATH = BASE_DIR / "manager.lock"
USERBOT_SOURCE_DIR = BASE_DIR.parent / "userbot"
USERBOT_MAIN_FILE = USERBOT_SOURCE_DIR / "main.py"
USERBOT_RUNTIME_DIR = BASE_DIR / "userbot_runtime"
VOICE_REQUEST_FILENAME = ".voice_request.json"
VOICE_RESPONSE_FILENAME = ".voice_response.json"
VOICE_ACTION_FILENAME = ".voice_action.json"
CLONE_REQUEST_FILENAME = ".clone_request.json"
CLONE_RESPONSE_FILENAME = ".clone_response.json"
CLONE_ACTION_FILENAME = ".clone_action.json"
PANEL_REQUEST_FILENAME = ".panel_request.json"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
API_ID = int(os.environ.get("API_ID", "0") or 0)
API_HASH = os.environ.get("API_HASH", "").strip()
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or 0)

BOT_NAME = "IBEKS MANAGER BOT"
VERSION = "1.0.0"
DEVELOPER = "IBEKS Developer"
