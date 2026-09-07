"""Small, side-effect-free helpers shared by Control Panel modules."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from config import MANAGER_DATABASE_PATH, OWNER_ID
from db import get_setting, list_plugin_status
from utils.prefix_manager import get_owner_id, get_prefix
from utils.theme import current


def update_owner_id(update) -> int:
    user = getattr(update, "from_user", None)
    if user is None:
        user = getattr(getattr(update, "message", None), "from_user", None)
    return int(getattr(user, "id", 0) or 0)


def owner_id() -> int:
    return int(get_owner_id() or OWNER_ID or 0)


def is_owner(update) -> bool:
    expected = owner_id()
    candidate = update_owner_id(update)
    return bool(expected and candidate == expected)


def owner_name(update) -> str:
    user = getattr(update, "from_user", None)
    if user is None:
        user = getattr(getattr(update, "message", None), "from_user", None)
    if not user:
        return "Unknown"
    username = getattr(user, "username", None)
    if username:
        return f"@{username}"
    name = " ".join(
        part for part in (
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        ) if part
    ).strip()
    return name or str(getattr(user, "id", "Unknown"))


def plan_for(telegram_id: int) -> str:
    """Read the current plan without changing either database."""
    path = Path(MANAGER_DATABASE_PATH)
    if not path.exists() or not telegram_id:
        return "FREE"
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT plan FROM users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        return str(row[0]) if row and row[0] else "FREE"
    except (OSError, sqlite3.Error):
        return "FREE"


def plugin_counts() -> tuple[int, int, int]:
    rows = list_plugin_status()
    total = len(rows)
    active = sum(1 for row in rows if row["enabled"] and row["loaded"])
    return total, active, total - active


def home_values(update) -> dict[str, object]:
    telegram_id = update_owner_id(update)
    total, active, disabled = plugin_counts()
    return {
        "owner": owner_name(update),
        "plan": plan_for(telegram_id),
        "total_plugin": total,
        "plugin_active": active,
        "plugin_disable": disabled,
        "prefix": get_setting(telegram_id, "prefix", get_prefix()),
        "theme": current(),
    }