"""
IBEKS USERBOT - Broadcast Utilities
Helper untuk operasi broadcast (gcast/u cast) dengan penanganan FloodWait,
blacklist, dan delay antar pengiriman.
"""

import asyncio
import uuid
from typing import Optional

from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from db import is_blacklisted
from utils.formatter import format_ui, success
from utils.logger import log


BROADCAST_DELAY: float = 1.0  # Jeda antar pengiriman (detik)


def _generate_task_id() -> str:
    """Generate task ID singkat untuk broadcast."""
    return uuid.uuid4().hex[:8].upper()


async def _send_message_to_chat(
    client: Client,
    chat_id: int,
    text: Optional[str] = None,
    source_message: Optional[Message] = None,
) -> bool:
    """
    Kirim pesan ke satu chat. Gunakan copy jika source_message tersedia,
    atau send_message jika hanya text.
    Return True jika berhasil, False jika gagal.
    """
    try:
        if source_message is not None:
            await source_message.copy(chat_id)
        else:
            await client.send_message(chat_id, text or "")
        return True
    except FloodWait as exc:
        # Tunggu sesuai permintaan Telegram lalu coba sekali lagi
        wait = exc.value
        log.warning(f"[Broadcast] FloodWait {wait}s untuk chat {chat_id}")
        await asyncio.sleep(wait)
        try:
            if source_message is not None:
                await source_message.copy(chat_id)
            else:
                await client.send_message(chat_id, text or "")
            return True
        except Exception as exc2:
            log.warning(f"[Broadcast] Gagal kirim ulang ke chat {chat_id}: {exc2}")
            return False
    except Exception as exc:
        log.warning(f"[Broadcast] Gagal kirim ke chat {chat_id}: {exc}")
        return False


async def broadcast_gcast(
    client: Client,
    text: Optional[str] = None,
    source_message: Optional[Message] = None,
) -> dict:
    """
    Broadcast pesan hanya ke group dan supergroup.
    Channel, private chat, dan bot chat selalu dilewati tanpa pengiriman.
    """
    task_id = _generate_task_id()
    success = 0
    failed = 0
    skipped = 0

    async for dialog in client.get_dialogs():
        chat = dialog.chat
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            skipped += 1
            continue
        if is_blacklisted(chat.id):
            skipped += 1
            continue

        if await _send_message_to_chat(client, chat.id, text, source_message):
            success += 1
        else:
            failed += 1

        await asyncio.sleep(BROADCAST_DELAY)

    total = success + failed
    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "task_id": task_id,
    }


async def broadcast_ucast(
    client: Client,
    text: Optional[str] = None,
    source_message: Optional[Message] = None,
) -> dict:
    """
    Broadcast pesan hanya ke private chat user.
    Bot chat dan Saved Messages (chat dengan diri sendiri) selalu dilewati.
    """
    task_id = _generate_task_id()
    success = 0
    failed = 0
    skipped = 0
    me = await client.get_me()

    async for dialog in client.get_dialogs():
        chat = dialog.chat
        if chat.type != ChatType.PRIVATE:
            skipped += 1
            continue
        if chat.id == me.id or getattr(chat, "is_self", False):
            skipped += 1
            continue
        if getattr(chat, "is_bot", False):
            skipped += 1
            continue
        if is_blacklisted(chat.id):
            skipped += 1
            continue

        if await _send_message_to_chat(client, chat.id, text, source_message):
            success += 1
        else:
            failed += 1

        await asyncio.sleep(BROADCAST_DELAY)

    total = success + failed
    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "task_id": task_id,
    }


def format_broadcast_result(broadcast_type: str, result: dict) -> str:
    """Format hasil broadcast dengan field hasil yang nyata."""
    label = broadcast_type.upper()
    body = [
        f"✅ Success : {result['success']}",
        f"❌ Failed : {result['failed']}",
        f"📊 Total : {result['total']}",
        f"🤖 Type : {label}",
        f"📎 Task ID : <code>{result['task_id']}</code>",
    ]
    return format_ui(f"BROADCAST {label}", body, emoji="📢")


def format_gcast_result(result: dict) -> str:
    """Format laporan GCAST dengan jumlah grup berhasil, gagal, dan dilewati."""
    body = [
        f"✅ Berhasil : {result['success']} Grup",
        f"❌ Gagal : {result['failed']} Grup",
        f"⏭️ Dilewati : {result['skipped']} Chat",
    ]
    return format_ui("GCAST REPORT", body, emoji="📢")


def format_ucast_result(result: dict) -> str:
    """Format laporan UCAST dengan jumlah user berhasil, gagal, dan dilewati."""
    body = [
        f"✅ Berhasil : {result['success']} User",
        f"❌ Gagal : {result['failed']} User",
        f"⏭️ Dilewati : {result['skipped']} Chat",
    ]
    return format_ui("UCAST REPORT", body, emoji="📨")

