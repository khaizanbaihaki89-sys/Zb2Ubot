"""
IBEKS USERBOT - Plugin: Fun
Commands:
  .ctampan       - Cek ketampanan akun sendiri atau yang direply
  .ccantik       - Cek kecantikan akun sendiri atau yang direply

Nilai deterministik berdasarkan User ID + minggu ISO saat ini.
"""

import asyncio

from pyrogram import filters

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui, error
from utils.fun_generator import generate_ctampan, generate_ccantik
from plugins.utils.ui import send_ui


def setup(client):
    """Daftarkan handler fun commands."""

    @client.on_message(dynamic_command("ctampan") & filters.me)
    async def cmd_ctampan(client, message):
        """Handler command .ctampan"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id
        target_user = message.reply_to_message.from_user if message.reply_to_message else message.from_user

        if not target_user:
            await send_ui(
                client,
                chat_id,
                error("CEK TAMPAN", "👤 Target : Tidak ditemukan."),
            )
            return

        name, user_id, progress, aura, outfit, plus, tier = generate_ctampan(target_user)

        body = (
            f"👤 Target : {name}\n"
            f"🆔 ID : {user_id}\n"
            f"📊 Ketampanan : {progress}\n"
            f"😎 Aura : {aura}\n"
            f"👕 Outfit : {outfit}\n"
            f"⭐ Plus : {plus}\n"
            f"👑 Tier : {tier}"
        )
        text = format_ui(
            title="CEK TAMPAN",
            body=body,
            emoji="✨",
            expandable=True,
        )
        await send_ui(client, chat_id, text, expandable=True)

    @client.on_message(dynamic_command("ccantik") & filters.me)
    async def cmd_ccantik(client, message):
        """Handler command .ccantik"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id
        target_user = message.reply_to_message.from_user if message.reply_to_message else message.from_user

        if not target_user:
            await send_ui(
                client,
                chat_id,
                error("CEK CANTIK", "👤 Target : Tidak ditemukan."),
            )
            return

        name, user_id, progress, aura, outfit, plus, tier = generate_ccantik(target_user)

        body = (
            f"👤 Target : {name}\n"
            f"🆔 ID : {user_id}\n"
            f"📊 Kecantikan : {progress}\n"
            f"💖 Aura : {aura}\n"
            f"👗 Outfit : {outfit}\n"
            f"⭐ Plus : {plus}\n"
            f"👑 Tier : {tier}"
        )
        text = format_ui(
            title="CEK CANTIK",
            body=body,
            emoji="✨",
            expandable=True,
        )
        await send_ui(client, chat_id, text, expandable=True)
