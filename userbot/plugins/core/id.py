"""IBEKS USERBOT - Plugin: id.

Command: .id
Menampilkan informasi akun sendiri atau akun pada pesan yang direply.
"""

import asyncio

from pyrogram import filters

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_user_info
from plugins.utils.ui import send_ui


def setup(client):
    """Daftarkan handler .id pada instance client."""

    @client.on_message(dynamic_command("id") & filters.me)
    async def cmd_id(client, message):
        """Handler command .id"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        reply = message.reply_to_message
        target = reply.from_user if reply else message.from_user
        if target is None:
            target = await client.get_me()

        chat_id = message.chat.id if message.chat else None
        text = format_user_info(target, chat_id=chat_id)
        await send_ui(client, message.chat.id, text)

