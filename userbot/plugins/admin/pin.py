"""
IBEKS USERBOT - Admin: Pin
Command: .pin (reply ke pesan yang akan dipin)
"""

import asyncio

from pyrogram import filters

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
    @client.on_message(dynamic_command("pin") & filters.me)
    async def cmd_pin(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        chat = message.chat

        if not is_group(chat):
            await send_ui(client, chat.id, error("PIN", "Perintah ini hanya bisa digunakan di grup."))
            return

        ok, err = await check_userbot_rights(client, chat.id, "can_pin_messages")
        if not ok:
            await send_ui(client, chat.id, error("PIN", f"🔐 Hak Akses : {err}"))
            return

        if not message.reply_to_message:
            await send_ui(client, chat.id, error("PIN", "💬 Pesan : Reply ke pesan yang ingin dipin."))
            return

        try:
            await client.pin_chat_message(
                chat.id,
                message.reply_to_message.id,
                disable_notification=False,
            )
            await send_ui(
                client,
                chat.id,
                success(
                    "PIN",
                    "📌 Status : Pesan berhasil dipin.",
                ),
            )
        except Exception as exc:
            log.exception(f"[Admin:Pin] Gagal pin pesan: {exc}")
            await send_ui(
                client,
                chat.id,
                error(
                    "PIN",
                    f"⚠️ Error : {admin_error_message(exc)}",
                ),
            )

