"""Callback router for the stage-one Control Panel."""

from __future__ import annotations

from pyrogram.errors import MessageNotModified

from plugins.utils.ui import edit_ui
from utils.logger import log

from . import views
from .utils import is_owner


PAGES = {
    "plugins",
    "themes",
    "dashboard",
    "macro",
    "backup",
    "permission",
    "settings",
    "store",
    "update",
}


async def _edit(query, text: str, markup) -> None:
    try:
        await edit_ui(
            query._client,
            query.message,
            text,
            reply_markup=markup,
        )
    except MessageNotModified:
        pass
    except Exception:
        log.exception("[ControlPanel] Gagal mengedit halaman panel.")


async def handle(query) -> None:
    if not is_owner(query):
        await query.answer("❌ Anda tidak memiliki akses.", show_alert=True)
        return

    await query.answer()
    data = query.data or ""
    parts = data.split(":")
    if len(parts) < 2:
        return

    route = parts[1]
    if route == "close":
        try:
            await query.message.delete()
        except Exception:
            log.exception("[ControlPanel] Gagal menghapus panel.")
        return
    if route == "home":
        text, markup = views.home(query)
        await _edit(query, text, markup)
        return
    if route in PAGES:
        if len(parts) == 2:
            text, markup = views.for_page(route, query)
        else:
            text, markup = views.placeholder(route, parts[2], query)
        await _edit(query, text, markup)