"""Callback menu Akun Saya."""

from __future__ import annotations

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database import get_or_create_user
from formatter import account_text, full_name
from logger import safe_handler


def account_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Menu Utama", callback_data="manager:home")]]
    )


def setup(client):
    @client.on_callback_query(filters.regex(r"^manager:account$"))
    @safe_handler
    async def account_callback(client, query):
        await query.answer()
        if not query.message or not query.from_user:
            return
        user = query.from_user
        data = get_or_create_user(user.id, user.username, full_name(user))
        await query.message.edit(account_text(data), reply_markup=account_keyboard())
