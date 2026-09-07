"""
IBEKS USERBOT - AI Conversation Context
Mengambil dan memformat riwayat pesan sebelumnya untuk konteks model AI.
Command:
  .aicontext status   - Menampilkan jumlah pesan konteks saat ini.
  .aicontext <jumlah> - Mengatur jumlah pesan konteks yang dibaca AI (1 - 30).
  .aicontext reset    - Mengembalikan jumlah pesan konteks ke default (8).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pyrogram import filters

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui, success, warning
from utils.logger import log
from plugins.utils.ui import send_ui
from plugins.ai.config import (
    DEFAULT_CONTEXT_LIMIT,
    MIN_CONTEXT_LIMIT,
    MAX_CONTEXT_LIMIT,
    get_context_limit,
    set_context_limit,
    reset_context_limit,
)


async def fetch_chat_context(
    client,
    chat_id: int,
    current_message_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Ambil riwayat pesan terakhir dari chat/grup untuk konteks percakapan.

    Parameters
    ----------
    client : pyrogram.Client
        Client Pyrogram aktif.
    chat_id : int
        ID chat tempat percakapan berlangsung.
    current_message_id : int | None
        ID pesan saat ini (untuk filter agar tidak menduplikasi perintah).
    limit : int | None
        Jumlah pesan maksimal yang diambil. Jika None, gunakan get_context_limit().

    Returns
    -------
    list[dict[str, Any]]
        Daftar pesan terurut dari yang terlama ke terbaru.
    """
    target_limit = limit if limit is not None else get_context_limit()
    messages_data: list[dict[str, Any]] = []
    try:
        my_id = getattr(getattr(client, "me", None), "id", None)
        if not my_id:
            try:
                me = await client.get_me()
                my_id = me.id if me else None
            except Exception:
                my_id = None

        # Ambil pesan dari history chat
        async for msg in client.get_chat_history(chat_id, limit=target_limit + 3):
            # Abaikan pesan kosong
            text = (msg.text or msg.caption or "").strip()
            if not text:
                continue
            if current_message_id and msg.id == current_message_id:
                continue
            if text.startswith((".", "!", "/")) and any(
                text.startswith(f"{p}ai") for p in (".", "!", "/")
            ):
                continue

            # Tentukan identitas pengirim
            is_me = False
            if msg.from_user:
                is_me = (msg.from_user.id == my_id) or msg.from_user.is_self
                sender_name = "Saya (Owner)" if is_me else (msg.from_user.first_name or "User")
            elif msg.sender_chat:
                sender_name = msg.sender_chat.title or "Channel/Group"
            else:
                sender_name = "User"

            messages_data.append({
                "id": msg.id,
                "sender": sender_name,
                "is_me": is_me,
                "text": text,
                "date": msg.date.isoformat() if getattr(msg, "date", None) else "",
            })

            if len(messages_data) >= target_limit:
                break

    except Exception as exc:
        log.warning(f"[AI Context] Gagal mengambil chat history: {exc}")

    # Urutkan dari pesan lama ke baru (kronologis)
    messages_data.reverse()
    return messages_data


def format_context_for_prompt(
    context_messages: list[dict[str, Any]],
    replied_message_text: str | None = None,
    replied_sender_name: str | None = None,
) -> str:
    """
    Ubah daftar pesan menjadi format teks terstruktur yang rapi untuk prompt Gemini.
    """
    lines: list[str] = []

    if context_messages:
        lines.append("=== RIWAYAT PERCAKAPAN SEBELUMNYA ===")
        for msg in context_messages:
            lines.append(f"[{msg['sender']}]: {msg['text']}")
        lines.append("=====================================\n")

    if replied_message_text:
        sender = replied_sender_name or "Lawan Bicara"
        lines.append(f"=== PESAN YANG SEDANG DIBALAS ===")
        lines.append(f"[{sender}]: {replied_message_text}")
        lines.append("=================================\n")

    return "\n".join(lines)


def setup(client) -> None:
    """Daftarkan command .aicontext pada instance client."""

    @client.on_message(dynamic_command("aicontext") & filters.me)
    async def cmd_aicontext(client, message):
        """Handler command .aicontext [status | <jumlah> | reset]"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        raw_text = (message.text or message.caption or "").strip()
        parts = raw_text.split()
        arg = parts[1].lower() if len(parts) > 1 else "status"

        if arg == "status":
            current_limit = get_context_limit()
            is_default = (current_limit == DEFAULT_CONTEXT_LIMIT)
            desc = f"{current_limit} pesan" + (" (Default)" if is_default else " (Kustom)")

            body = (
                f"📊 Jumlah Pesan : {desc}\n"
                f"📏 Batas Izin : {MIN_CONTEXT_LIMIT} - {MAX_CONTEXT_LIMIT} pesan\n\n"
                "💡 Cara Penggunaan:\n"
                "• .aicontext <jumlah> (contoh: .aicontext 15)\n"
                "• .aicontext reset\n"
                "• .aicontext status"
            )
            text = format_ui(
                title="KONTEKS CHATBOT AI",
                body=body,
                emoji="💬",
                expandable=True,
            )
            await send_ui(client, message.chat.id, text, expandable=True)
            return

        if arg == "reset":
            val = reset_context_limit()
            text = success(
                title="KONTEKS AI DIRESET",
                message=f"📌 Status : Konteks dikembalikan ke default {val} pesan.",
                emoji="🔄",
            )
            await send_ui(client, message.chat.id, text, expandable=True)
            return

        # Cek apakah arg berupa angka
        try:
            val_int = int(arg)
            if val_int < MIN_CONTEXT_LIMIT or val_int > MAX_CONTEXT_LIMIT:
                warn_text = warning(
                    title="BATAS KONTEKS AI",
                    message=(
                        f"❌ Nilai Diluar Jangkauan : Jumlah harus di antara {MIN_CONTEXT_LIMIT} sampai {MAX_CONTEXT_LIMIT} pesan.\n\n"
                        "📝 Contoh : .aicontext 15"
                    ),
                    emoji="⚠️",
                )
                await send_ui(client, message.chat.id, warn_text, expandable=True)
                return

            applied = set_context_limit(val_int)
            text = success(
                title="KONTEKS AI DIPERBARUI",
                message=(
                    f"💬 Jumlah Pesan : {applied} pesan histori\n"
                    f"💡 Info : AI akan membaca hingga {applied} pesan sebelumnya saat merespons."
                ),
                emoji="✅",
            )
            await send_ui(client, message.chat.id, text, expandable=True)
            return

        except ValueError:
            help_text = format_ui(
                title="BANTUAN AI KONTEKS",
                body=(
                    "📖 Perintah Tersedia:\n"
                    "• .aicontext status : Lihat jumlah konteks saat ini\n"
                    "• .aicontext <jumlah> : Atur jumlah konteks (1 - 30)\n"
                    "• .aicontext reset : Kembalikan ke default (8)\n\n"
                    "📝 Contoh:\n"
                    "• .aicontext 15"
                ),
                emoji="❓",
                expandable=True,
            )
            await send_ui(client, message.chat.id, help_text, expandable=True)

