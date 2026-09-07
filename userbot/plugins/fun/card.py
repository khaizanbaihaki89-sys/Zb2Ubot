"""
IBEKS USERBOT - Plugin: Card
Command:
- .cardp (ID Card Pria - Gold Metallic Theme)
- .cardw (ID Card Wanita - Pink / Rose Gold Metallic Theme)
- .card  (ID Card Default Pria - Gold)

Membuat kartu identitas futuristik/eksklusif untuk diri sendiri atau user yang di-reply.
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import filters

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error
from utils.fun_card_generator import generate_fun_card
from plugins.utils.ui import send_ui


def setup(client):
    """Daftarkan handler .cardp, .cardw, dan .card."""

    async def _send_card(client, message, card_type: str):
        """Helper untuk generate dan kirim kartu ID."""
        target = (
            message.reply_to_message.from_user
            if message.reply_to_message and message.reply_to_message.from_user
            else message.from_user
        )
        if target is None:
            target = await client.get_me()

        chat_id = message.chat.id

        try:
            card_buffer = await generate_fun_card(client, target, card_type=card_type)
            card_buffer.name = f"ibeks_card_{card_type}_{target.id}.png"
            await client.send_photo(
                chat_id=chat_id,
                photo=card_buffer,
                caption=None,
            )
        except Exception as exc:
            logging.exception("[Card] Gagal generate card: %s", exc)
            await send_ui(client, chat_id, error("GAGAL GENERATE CARD", str(exc)))

    @client.on_message(dynamic_command("cardp") & filters.me)
    async def cmd_cardp(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        await _send_card(client, message, "male")

    @client.on_message(dynamic_command("cardw") & filters.me)
    async def cmd_cardw(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        await _send_card(client, message, "female")

    @client.on_message(dynamic_command("card") & filters.me)
    async def cmd_card(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        await _send_card(client, message, "male")
