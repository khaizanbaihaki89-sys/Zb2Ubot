"""
IBEKS USERBOT - Plugin: logs
Command: .logs
Mengirim file log terbaru ke chat.
"""

import asyncio
import os

from pyrogram import filters

from config import AUTO_DELETE_CMD, LOGS_DIR
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error, warning
from plugins.utils.ui import send_ui


def setup(client):
    """Daftarkan handler .logs pada instance client."""

    @client.on_message(dynamic_command("logs") & filters.me)
    async def cmd_logs(client, message):
        """Handler command .logs"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id
        log_file = os.path.join(LOGS_DIR, "ibeks.log")

        if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
            await send_ui(
                client,
                chat_id,
                warning("LOG", "📄 File : Tidak ada log."),
            )
            return

        try:
            await client.send_document(
                chat_id,
                document=log_file,
                caption="📄 Log terbaru IBEKS USERBOT",
            )
        except Exception as exc:
            from utils.logger import log
            log.exception(f"[Logs] Gagal mengirim log: {exc}")
            await send_ui(
                client,
                chat_id,
                error("LOG", "📄 File : Gagal mengirim file log."),
            )

