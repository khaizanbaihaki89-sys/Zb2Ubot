"""
IBEKS USERBOT - Plugin: Sudo Management (Owner Only)
Command:
- .addsudo <user> (Tambah user Sudo Bot - Max 5)
- .delsudo <user> (Hapus user Sudo Bot)
- .listsudo       (Lihat daftar Sudo Bot aktif & slot 5)
"""

from __future__ import annotations

import asyncio
from pyrogram import filters

from config import AUTO_DELETE_CMD, OWNER_ID
from db import (
    add_sudo_user as _db_add_sudo_user,
    count_sudo_users,
    del_sudo_user,
    get_sudo_user,
    list_sudo_users,
)
from plugins.utils.ui import edit_ui, send_ui
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error, format_ui, info, success, warning

MAX_SUDO_USERS = 5
add_sudo_user = _db_add_sudo_user


def is_sudo(telegram_id: int | None) -> bool:
    """Periksa apakah Telegram ID adalah Owner atau terdaftar sebagai Sudo."""
    if not telegram_id:
        return False
    from utils.prefix_manager import get_owner_id

    owner_id = get_owner_id() or OWNER_ID
    if owner_id and telegram_id == owner_id:
        return True
    return bool(get_sudo_user(telegram_id))



async def _resolve_user(client, message) -> tuple[int | None, str | None, str | None, str | None]:
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        name = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username or f"User {u.id}"
        return u.id, u.username, name, None

    text = message.text or message.caption or ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        return None, None, None, "Format tidak lengkap. Reply pesan user atau sertakan ID / Username."

    raw = parts[1].strip()
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        uid = int(raw)
        try:
            u = await client.get_users(uid)
            name = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username or f"User {u.id}"
            return u.id, u.username, name, None
        except Exception:
            return uid, None, f"User {uid}", None

    try:
        u = await client.get_users(raw)
        name = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username or f"User {u.id}"
        return u.id, u.username, name, None
    except Exception as exc:
        return None, None, None, f"User <code>{raw}</code> tidak ditemukan di Telegram."


def setup(client):
    """Daftarkan command .addsudo, .delsudo, dan .listsudo di Userbot."""

    @client.on_message(dynamic_command("addsudo") & filters.me)
    async def cmd_addsudo(client, message):
        asyncio.create_task(auto_delete(message, delay=3, force=True))
        target_id, username, full_name, err = await _resolve_user(client, message)
        if err:
            res_msg = await send_ui(client, message.chat.id, warning("SUDO BOT", err))
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=3, force=True))
            return

        ok, msg, count = add_sudo_user(
            telegram_id=target_id,
            username=username,
            full_name=full_name,
            added_by=message.from_user.id,
            max_users=MAX_SUDO_USERS,
        )
        if ok:
            ui = success("SUDO BOT", f"User: <b>{full_name}</b> (<code>{target_id}</code>)\nSlot Sudo: <b>{count}/{MAX_SUDO_USERS}</b>")
        else:
            ui = error("SUDO BOT", msg)
        res_msg = await send_ui(client, message.chat.id, ui)
        if res_msg:
            asyncio.create_task(auto_delete(res_msg, delay=3, force=True))

    @client.on_message(dynamic_command("delsudo") & filters.me)
    async def cmd_delsudo(client, message):
        asyncio.create_task(auto_delete(message, delay=3, force=True))
        target_id, username, full_name, err = await _resolve_user(client, message)
        if err:
            res_msg = await send_ui(client, message.chat.id, warning("SUDO BOT", err))
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=3, force=True))
            return

        ok, msg, count = del_sudo_user(telegram_id=target_id)
        if ok:
            ui = success("SUDO BOT", f"User: <code>{target_id}</code> telah dicabut.\nSlot Sudo: <b>{count}/{MAX_SUDO_USERS}</b>")
        else:
            ui = error("SUDO BOT", msg)
        res_msg = await send_ui(client, message.chat.id, ui)
        if res_msg:
            asyncio.create_task(auto_delete(res_msg, delay=3, force=True))

    @client.on_message(dynamic_command("listsudo") & filters.me)
    async def cmd_listsudo(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        sudo_list = list_sudo_users()
        total = len(sudo_list)

        if not sudo_list:
            ui = info("DAFTAR SUDO BOT", f"Belum ada user Sudo terdaftar.\nSlot: <b>0/{MAX_SUDO_USERS}</b>")
            await send_ui(client, message.chat.id, ui)
            return

        body = [f"📊 Slot Digunakan: <b>{total}/{MAX_SUDO_USERS}</b>", ""]
        for idx, u in enumerate(sudo_list, 1):
            name = u.get("full_name") or "User"
            uname = f"@{u['username']}" if u.get("username") else "-"
            uid = u["telegram_id"]
            added = (u.get("added_at") or "")[:19]
            body.append(f"{idx}. <b>{name}</b> ({uname})\n   🆔 ID: <code>{uid}</code>\n   📅 Ditambahkan: <code>{added}</code>")

        ui = format_ui(title="DAFTAR SUDO BOT", body=body, emoji="👑", expandable=True)
        await send_ui(client, message.chat.id, ui)
