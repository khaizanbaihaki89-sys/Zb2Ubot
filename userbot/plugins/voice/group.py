"""
IBEKS USERBOT - Voice Clone / Target Group Settings
Pengelolaan konfigurasi grup tujuan pengiriman Voice Note di data/voice/settings.json.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from plugins.voice.config import SETTINGS_FILE
from utils.logger import log

__version__ = "1.0.0"
__author__ = "IBEKS"


def _read_settings() -> dict[str, Any]:
    """Baca file settings.json."""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.error("[VoiceGroup] Gagal membaca settings.json: %s", exc)
        return {}


def _write_settings(data: dict[str, Any]) -> bool:
    """Tulis file settings.json."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as exc:
        log.error("[VoiceGroup] Gagal menulis settings.json: %s", exc)
        return False


def get_target_group() -> dict[str, Any] | None:
    """
    Ambil grup tujuan yang telah disetel.
    Mengembalikan dict {"target_group_id": int, "target_group_title": str} atau None.
    """
    settings = _read_settings()
    group_id = settings.get("target_group_id")
    if group_id:
        return {
            "target_group_id": int(group_id),
            "target_group_title": settings.get("target_group_title") or str(group_id),
            "updated_at": settings.get("updated_at"),
        }
    return None


def set_target_group(chat_id: int, title: str) -> dict[str, Any]:
    """
    Simpan grup target ke settings.json.
    """
    settings = _read_settings()
    now_iso = datetime.now(timezone.utc).isoformat()
    settings["target_group_id"] = int(chat_id)
    settings["target_group_title"] = title.strip() or f"Group {chat_id}"
    settings["updated_at"] = now_iso
    _write_settings(settings)
    return {
        "target_group_id": int(chat_id),
        "target_group_title": settings["target_group_title"],
        "updated_at": now_iso,
    }


def unset_target_group() -> bool:
    """
    Hapus pengaturan grup target dari settings.json.
    """
    settings = _read_settings()
    settings["target_group_id"] = None
    settings["target_group_title"] = None
    settings["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _write_settings(settings)


def setup(client: Any) -> None:
    """Setup hook untuk plugin loader."""
    pass
