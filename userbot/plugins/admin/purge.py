"""
IBEKS USERBOT - Admin: Purge
Command: .purge (reply ke pesan paling awal yang ingin dihapus)
Menghapus semua pesan dari reply target hingga command .purge.
"""

import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait

from config import AUTO_DELETE_CMD
from utils.admin_helper import (
    admin_error_message,
    check_userbot_rights,
    is_group,
)
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error, success
from utils.logger import log
from plugins.utils.ui import send_ui


def setup(client):
    @client.on_message(dynamic_command("purge") & filters.me)
    async def cmd_purge(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        chat = message.chat

        if not is_group(chat):
            await send_ui(client, chat.id, error("PURGE", "Perintah ini hanya bisa digunakan di grup."))
            return

        ok, err = await check_userbot_rights(client, chat.id, "can_delete_messages")
        if not ok:
            await send_ui(client, chat.id, error("PURGE", f"🔐 Hak Akses : {err}"))
            return

        if not message.reply_to_message:
            await send_ui(client, chat.id, error("PURGE", "💬 Pesan : Reply ke pesan paling awal yang ingin dihapus."))
            return

        start_id = message.reply_to_message.id
        end_id = message.id
        if start_id > end_id:
            await send_ui(client, chat.id, error("PURGE", "📏 Rentang : Pesan tidak valid."))
            return

        try:
            message_ids = list(range(start_id, end_id + 1))
            total_deleted = 0
            chunk_size = 100

            for i in range(0, len(message_ids), chunk_size):
                chunk = message_ids[i : i + chunk_size]
                try:
                    await client.delete_messages(chat.id, chunk)
                    total_deleted += len(chunk)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                    await client.delete_messages(chat.id, chunk)
                    total_deleted += len(chunk)
                except Exception as chunk_err:
                    log.warning(f"[Admin:Purge] Gagal delete chunk {chunk[0]}-{chunk[-1]}: {chunk_err}")

                if i + chunk_size < len(message_ids):
                    await asyncio.sleep(0.2)

            await send_ui(
                client,
                chat.id,
                success(
                    "PURGE",
                    f"🗑 Jumlah : {total_deleted} pesan berhasil dihapus.",
                ),
            )
        except Exception as exc:
            log.exception(f"[Admin:Purge] Gagal purge pesan: {exc}")
            await send_ui(
                client,
                chat.id,
                error(
                    "PURGE",
                    f"⚠️ Error : {admin_error_message(exc)}",
                ),
            )

