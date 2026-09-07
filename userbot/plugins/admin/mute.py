"""
IBEKS USERBOT - Admin: Mute
Command: .mute (reply | username | id) [durasi]
Durasi: 1h, 30m, 7d, 1h30m, dst. Tanpa durasi = selamanya.
"""

import asyncio

from pyrogram import filters
from pyrogram.types import ChatPermissions

from config import AUTO_DELETE_CMD
from utils.admin_helper import (
    admin_error_message,
    check_userbot_rights,
    format_duration,
    get_target_user,
    is_group,
    is_self_target_async,
    parse_duration,
    until_date,
)
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error, success
from utils.logger import log
from plugins.utils.ui import send_ui


def setup(client):
    @client.on_message(dynamic_command("mute") & filters.me)
    async def cmd_mute(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        chat = message.chat

        if not is_group(chat):
            await send_ui(client, chat.id, error("MUTE", "Perintah ini hanya bisa digunakan di grup."))
            return

        ok, err = await check_userbot_rights(client, chat.id, "can_restrict_members")
        if not ok:
            await send_ui(client, chat.id, error("MUTE", f"🔐 Hak Akses : {err}"))
            return

        target_id = await get_target_user(client, message)
        if not target_id:
            await send_ui(client, chat.id, error("MUTE", "👤 Target : Tidak ditemukan. Reply ke pesan user atau berikan username/ID."))
            return

        if await is_self_target_async(client, target_id):
            await send_ui(client, chat.id, error("MUTE", "👤 Target : Tidak bisa mute diri sendiri."))
            return

        # Parse durasi dari seluruh argumen setelah command
        text = message.text or message.caption or ""
        parts = text.split(maxsplit=1)
        duration = None
        if len(parts) > 1:
            duration = parse_duration(parts[1])

        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_send_polls=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )

        try:
            await client.restrict_chat_member(
                chat.id,
                target_id,
                permissions,
                until_date=until_date(duration),
            )
            dur_text = format_duration(duration)
            await send_ui(
                client,
                chat.id,
                success(
                    "MUTE",
                    [
                        f"👤 Target : <code>{target_id}</code>",
                        f"⏱ Durasi : {dur_text}",
                        "📌 Status : Berhasil dimute.",
                    ],
                ),
            )
        except Exception as exc:
            log.exception(f"[Admin:Mute] Gagal mute user {target_id}: {exc}")
            await send_ui(
                client,
                chat.id,
                error(
                    "MUTE",
                    [
                        f"👤 Target : <code>{target_id}</code>",
                        f"⚠️ Error : {admin_error_message(exc)}",
                    ],
                ),
            )

