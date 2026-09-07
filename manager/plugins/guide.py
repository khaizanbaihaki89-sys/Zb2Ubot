"""Callback menu Panduan."""

from __future__ import annotations

from pyrogram import filters

from formatter import guide_text
from logger import safe_handler
from plugins.start.start import home_keyboard


def setup(client):
    @client.on_callback_query(filters.regex(r"^manager:guide$"))
    @safe_handler
    async def guide_callback(client, query):
        await query.answer()
        if query.message:
            await query.message.edit(guide_text(), reply_markup=home_keyboard())