"""
IBEKS USERBOT - Admin: Ban
Command: .ban (reply | username | id)
"""

import asyncio

from pyrogram import filters

from config import AUTO_DELETE_CMD
from utils.admin_helper import (
    admin_error_message,
    check_userbot_rights,
    get_target_user,
    is_group,
    is_self_target_async,
)
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error, success
from utils.logger import log
from plugins.utils.ui import send_ui


def setup(client):
    @client.on_message(dynamic_command("ban") & filters.me)
    async def cmd_ban(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        chat = message.chat

        if not is_group(chat):
            await send_ui(client, chat.id, error("BAN", "Perintah ini hanya bisa digunakan di grup."))
            return

        ok, err = await check_userbot_rights(client, chat.id, "can_restrict_members")
        if not ok:
            await send_ui(client, chat.id, error("BAN", f"🔐 Hak Akses : {err}"))
            return

        target_id = await get_target_user(client, message)
        if not target_id:
            await send_ui(client, chat.id, error("BAN", "👤 Target : Tidak ditemukan. Reply ke pesan user atau berikan username/ID."))
            return

        if await is_self_target_async(client, target_id):
            await send_ui(client, chat.id, error("BAN", "👤 Target : Tidak bisa banned diri sendiri."))
            return

        try:
            await client.ban_chat_member(chat.id, target_id)
            await send_ui(
                client,
                chat.id,
                success(
                    "BAN",
                    [
                        f"👤 Target : <code>{target_id}</code>",
                        "📌 Status : Berhasil dibanned dari grup.",
                    ],
                ),
            )
        except Exception as exc:
            log.exception(f"[Admin:Ban] Gagal ban user {target_id}: {exc}")
            await send_ui(
                client,
                chat.id,
                error(
                    "BAN",
                    [
                        f"👤 Target : <code>{target_id}</code>",
                        f"⚠️ Error : {admin_error_message(exc)}",
                    ],
                ),
            )

