"""
IBEKS USERBOT - Plugin: ping
Command: .ping
Menampilkan status bot, uptime, RAM, CPU, dan info owner.

Flow:
1. Hapus pesan command asli.
2. Kirim pesan baru sebagai response.
3. Edit response ke hasil akhir.
"""

import asyncio
import time

from pyrogram import filters

from config import BOT_NAME, VERSION, AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.helper import get_ram_usage, get_cpu_usage
from utils.uptime import format_uptime
from utils.filters import dynamic_command
from utils.formatter import format_ui
from plugins.utils.ui import edit_ui, send_ui
from utils.logger import log


def setup(client):
    """Daftarkan handler .ping pada instance client."""

    @client.on_message(dynamic_command("ping") & filters.me)
    async def cmd_ping(client, message):
        """Handler command .ping"""
        # Hapus pesan command asli
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id

        # Ukur ping lokal (waktu kirim pesan "loading")
        t_start = time.monotonic()
        loading_text = format_ui(
            title="PING",
            body="⏱ Status : Mengukur ping...",
            emoji="🏓",
        )
        sent = await send_ui(client, chat_id, loading_text)
        ping_ms = round((time.monotonic() - t_start) * 1000, 2)

        # Ukur API ping via get_me()
        api_start = time.monotonic()
        me = await client.get_me()
        api_ping_ms = round((time.monotonic() - api_start) * 1000, 2)

        # Ambil nama owner
        owner = me.first_name or me.username or "Unknown"

        # Statistik sistem
        ram = get_ram_usage()
        cpu = get_cpu_usage()
        uptime = format_uptime()

        content_body = (
            f"🏓 Ping : {ping_ms} ms\n"
            f"⚡ API : {api_ping_ms} ms\n"
            f"⏰ Uptime : {uptime}\n"
            f"💾 RAM : {ram}%\n"
            f"🖥 CPU : {cpu}%\n"
            f"👤 Owner : {owner}"
        )

        final_ui = format_ui(
            title="INFO STATUS",
            body=content_body,
            emoji="💀",
        )
        try:
            await edit_ui(client, sent, final_ui)
        except Exception as exc:
            log.exception("[Ping] Gagal mengedit hasil ping: %s", exc)
