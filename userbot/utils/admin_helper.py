"""
IBEKS USERBOT - Admin Helper
Utilitas umum untuk command admin grup: ekstrak target user,
cek izin admin Userbot, parse durasi mute, dan format pesan error.
"""

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from pyrogram import Client
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import (
    BadRequest,
    ChatAdminRequired,
    FloodWait,
    RPCError,
    UserAdminInvalid,
)
from pyrogram.types import Message

from utils.logger import log


def is_group(chat) -> bool:
    """Cek apakah chat adalah grup/channel."""
    return chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL)


async def get_target_user(client: Client, message: Message) -> Optional[int]:
    """Ambil target user_id dari reply atau argumen (username/id/link)."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    text = message.text or message.caption or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None

    arg = parts[1].strip()

    # ID numerik langsung
    if arg.isdigit():
        return int(arg)

    # Username @username
    if arg.startswith("@"):
        username = arg[1:]
        try:
            user = await client.get_users(username)
            return user.id
        except Exception as exc:
            log.warning(f"[AdminHelper] Gagal resolve username {username}: {exc}")
            return None

    # Link t.me/username
    match = re.match(r"https?://t\.me/(\w+)", arg)
    if match:
        username = match.group(1)
        try:
            user = await client.get_users(username)
            return user.id
        except Exception as exc:
            log.warning(f"[AdminHelper] Gagal resolve t.me/{username}: {exc}")
            return None

    return None


async def check_userbot_rights(
    client: Client, chat_id: int, required_priv: str
) -> Tuple[bool, str]:
    """
    Cek apakah Userbot adalah admin dan punya privilege tertentu.

    required_priv: nama atribut ChatPrivileges, misal 'can_restrict_members'.
    Return (True, "") jika diizinkan, else (False, error_message).
    """
    try:
        me = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
    except Exception as exc:
        log.warning(f"[AdminHelper] Gagal cek status admin: {exc}")
        return False, "❌ Gagal memeriksa status admin Userbot."

    if member.status == ChatMemberStatus.OWNER:
        return True, ""

    if member.status != ChatMemberStatus.ADMINISTRATOR:
        return False, "❌ Userbot bukan admin di grup ini."

    privileges = member.privileges
    if privileges is None:
        return False, "❌ Userbot tidak memiliki izin yang diperlukan."

    if not getattr(privileges, required_priv, False):
        return False, "❌ Userbot tidak memiliki izin yang diperlukan untuk perintah ini."

    return True, ""


def parse_duration(text: Optional[str]) -> Optional[int]:
    """
    Parse string durasi seperti '1h30m', '7d', '30m', '1h'.
    Return total detik, atau None untuk selamanya.
    """
    if not text:
        return None

    total_seconds = 0
    found = False
    pattern = re.compile(r"(\d+)\s*([smhd])", re.IGNORECASE)
    for match in pattern.finditer(text):
        found = True
        value = int(match.group(1))
        unit = match.group(2).lower()
        if unit == "s":
            total_seconds += value
        elif unit == "m":
            total_seconds += value * 60
        elif unit == "h":
            total_seconds += value * 3600
        elif unit == "d":
            total_seconds += value * 86400

    return total_seconds if found else None


def format_duration(seconds: Optional[int]) -> str:
    """Format detik menjadi durasi yang mudah dibaca."""
    if seconds is None:
        return "selamanya"
    if seconds < 60:
        return f"{seconds} detik"
    if seconds < 3600:
        return f"{seconds // 60} menit"
    if seconds < 86400:
        return f"{seconds // 3600} jam"
    return f"{seconds // 86400} hari"


def until_date(seconds: Optional[int]) -> datetime:
    """Buat datetime UTC untuk until_date Pyrogram. None => jauh di masa depan."""
    if seconds is None:
        # Telegram 0 atau tanggal jauh di masa depan = selamanya
        return datetime(2038, 1, 1, tzinfo=timezone.utc)
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


async def get_user_name(client: Client, user_id: int) -> str:
    """Ambil nama user jika memungkinkan."""
    try:
        user = await client.get_users(user_id)
        name = user.first_name or ""
        if user.last_name:
            name = f"{name} {user.last_name}".strip()
        return name or user.username or str(user_id)
    except Exception as exc:
        log.warning(f"[AdminHelper] Gagal ambil nama user {user_id}: {exc}")
        return str(user_id)


def admin_error_message(exc: Exception) -> str:
    """Format pesan error untuk command admin."""
    if isinstance(exc, FloodWait):
        return f"❌ Terkena FloodWait. Coba lagi dalam {exc.value} detik."
    if isinstance(exc, ChatAdminRequired):
        return "❌ Userbot bukan admin atau tidak memiliki izin yang cukup."
    if isinstance(exc, UserAdminInvalid):
        return "❌ Target adalah admin/owner dan tidak dapat diproses."
    if isinstance(exc, BadRequest):
        return f"❌ Permintaan ditolak Telegram: {exc}"
    if isinstance(exc, RPCError):
        return f"❌ Error Telegram: {exc}"
    return f"❌ Terjadi kesalahan: {exc}"


def is_self_target(client: Client, user_id: int) -> bool:
    """Cek apakah target adalah akun Userbot sendiri (sync-safe)."""
    # Client.me bisa None saat startup; gunakan get_me() async untuk keakuratan.
    # Fungsi sync ini hanya placeholder; gunakan async version di bawah.
    return False


async def is_self_target_async(client: Client, user_id: int) -> bool:
    """Cek apakah target adalah akun Userbot sendiri."""
    try:
        me = await client.get_me()
        return me.id == user_id
    except Exception as exc:
        log.warning(f"[AdminHelper] Gagal cek self target: {exc}")
        return False
