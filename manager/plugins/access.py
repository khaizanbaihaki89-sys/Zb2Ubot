"""Pemicu alur login Telegram dari menu Minta Akses."""

from __future__ import annotations

from pyrogram import filters

from logger import safe_handler
from plugins.auth.login import begin_login
from plugins.start.start import home_keyboard


def setup(client):
    @client.on_callback_query(filters.regex(r"^manager:request$"))
    @safe_handler
    async def request_access_callback(client, query):
        if not query.from_user or not query.message:
            await query.answer()
            return
        await query.answer()
        await begin_login(query.from_user, query.message)