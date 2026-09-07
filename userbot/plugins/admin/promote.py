"""
IBEKS USERBOT - Admin: Promote
Command: .promote (reply | username | id)
"""

import asyncio

from pyrogram import filters
from pyrogram.types import ChatPrivileges

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
    @client.on_message(dynamic_command("promote") & filters.me)
    async def cmd_promote(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        chat = message.chat

        if not is_group(chat):
            await send_ui(client, chat.id, error("PROMOTE", "Perintah ini hanya bisa digunakan di grup."))
            return

        ok, err = await check_userbot_rights(client, chat.id, "can_promote_members")
        if not ok:
            await send_ui(client, chat.id, error("PROMOTE", f"🔐 Hak Akses : {err}"))
            return

        target_id = await get_target_user(client, message)
        if not target_id:
            await send_ui(client, chat.id, error("PROMOTE", "👤 Target : Tidak ditemukan. Reply ke pesan user atau berikan username/ID."))
            return

        if await is_self_target_async(client, target_id):
            await send_ui(client, chat.id, error("PROMOTE", "👤 Target : Tidak bisa promote diri sendiri."))
            return

        privileges = ChatPrivileges(
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_change_info=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_promote_members=False,
            can_post_messages=False,
            can_edit_messages=False,
            is_anonymous=False,
        )

        try:
            await client.promote_chat_member(chat.id, target_id, privileges=privileges)
            await send_ui(
                client,
                chat.id,
                success(
                    "PROMOTE",
                    [
                        f"👤 Target : <code>{target_id}</code>",
                        "📌 Status : Berhasil menjadi admin.",
                    ],
                ),
            )
        except Exception as exc:
            log.exception(f"[Admin:Promote] Gagal promote user {target_id}: {exc}")
            await send_ui(
                client,
                chat.id,
                error(
                    "PROMOTE",
                    [
                        f"👤 Target : <code>{target_id}</code>",
                        f"⚠️ Error : {admin_error_message(exc)}",
                    ],
                ),
            )

