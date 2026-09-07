"""
IBEKS USERBOT - Plugin: alive
Command: .alive
Menampilkan status online bot beserta info versi dan owner.

Flow:
1. Hapus pesan command asli.
2. Kirim pesan baru sebagai response.
"""

import asyncio
import sys

import pyrogram
from pyrogram import filters

from config import BOT_NAME, VERSION, AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui
from utils.uptime import format_uptime
from plugins.utils.ui import send_ui


def setup(client):
    """Daftarkan handler .alive pada instance client."""

    @client.on_message(dynamic_command("alive") & filters.me)
    async def cmd_alive(client, message):
        """Handler command .alive"""
        # Hapus pesan command asli
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        me = await client.get_me()
        owner = me.first_name or me.username or "Unknown"
        python_ver = sys.version.split()[0]
        pyrogram_ver = pyrogram.__version__
        uptime = format_uptime()

        body_lines = [
            f"🤖 Bot : {BOT_NAME}",
            "📌 Status : Online",
            f"📦 Versi : {VERSION}",
            f"🐍 Python : {python_ver}",
            f"⚙️ Pyrogram : {pyrogram_ver}",
            f"⏰ Uptime : {uptime}",
            f"👤 Owner : {owner}",
        ]

        text = format_ui(
            title="ALIVE STATUS",
            body=body_lines,
            emoji="💀",
        )
        await send_ui(client, message.chat.id, text)

