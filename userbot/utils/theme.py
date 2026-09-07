"""Theme Engine untuk seluruh fitur IBEKS Userbot."""

from __future__ import annotations

from db import active_theme, list_themes, save_theme
from utils.formatter import format_ui

THEME_EMOJI = {
    "Premium": "💎",
    "Freeze": "❄️",
    "Minimal": "▣",
    "Neon": "⚡",
    "Matrix": "🟢",
}


def available() -> list[dict]:
    return list_themes()


def current() -> str:
    return active_theme()


def set_active(name: str) -> bool:
    """Aktifkan tema yang sudah terdaftar."""
    match = next((item for item in list_themes() if item["name"].casefold() == name.casefold()), None)
    if not match:
        return False
    save_theme(match["name"], match["definition"], active=True)
    return True


def render(title: str, body: str = "", status: str = "") -> str:
    """Render satu blok UI konsisten sesuai standar UI global IBEKS."""
    theme_name = current()
    em = THEME_EMOJI.get(theme_name, "💠")
    return format_ui(title=title, body=body, emoji=em, status=status)


def render_theme(name: str, title: str, body: str = "", status: str = "") -> str:
    """Render tema tertentu untuk preview tanpa mengubah tema aktif."""
    em = THEME_EMOJI.get(name, "💠")
    return format_ui(title=title, body=body, emoji=em, status=status)


def emoji(name: str = "") -> str:
    return THEME_EMOJI.get(name or current(), "💠")
