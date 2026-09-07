"""Callback menu Tentang."""

from __future__ import annotations

import platform

import pyrogram
from pyrogram import filters

from config import BOT_NAME, DEVELOPER, VERSION
from formatter import about_text
from logger import safe_handler
from plugins.start.start import home_keyboard


def setup(client):
    @client.on_callback_query(filters.regex(r"^manager:about$"))
    @safe_handler
    async def about_callback(client, query):
        await query.answer()
        if query.message:
            await query.message.edit(
                about_text(
                    BOT_NAME,
                    VERSION,
                    DEVELOPER,
                    platform.python_version(),
                    pyrogram.__version__,
                ),
                reply_markup=home_keyboard(),
            )