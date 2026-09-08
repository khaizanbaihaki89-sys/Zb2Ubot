"""Kontrol AI di Manager Bot: Mengatur status AI per-chat via Panel Terpusat dan Inline Keyboard."""

from __future__ import annotations

import asyncio
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from pyrogram import ContinuePropagation, filters
except ImportError:
    class ContinuePropagation(Exception):
        pass
    filters = None
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    from config import USERBOT_RUNTIME_DIR
except (ImportError, AttributeError):
    USERBOT_RUNTIME_DIR = Path(__file__).resolve().parent.parent / "userbot_runtime"

try:
    from logger import log, safe_handler
except ImportError:
    import logging
    log = logging.getLogger("ai_control")
    def safe_handler(func):
        return func

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── State Tracking & Timers ──────────────────────────────────────────────────
# user_id -> message_id of the active panel in Manager Bot
_active_panels: dict[int, int] = {}
# user_id -> chat_id -> panel entry.
# This is deliberately in-memory: the panel list is a session, not database data.
_panel_chats: dict[int, dict[int, dict[str, Any]]] = {}
# user_id -> asyncio.Task for 10-second auto deletion
_panel_delete_tasks: dict[int, asyncio.Task] = {}


def _runtime_db_path(account_id: int | None) -> Path | None:
    """Return exactly one existing database for the selected UBot account."""
    try:
        account_id = int(account_id or 0)
    except (TypeError, ValueError):
        return None
    if account_id <= 0:
        return None
    path = Path(USERBOT_RUNTIME_DIR) / str(account_id) / "database.db"
    return path if path.is_file() else None


def get_all_ai_chats(user_id: int | None = None) -> list[dict]:
    """Ambil chat yang terdaftar pada sesi panel aktif saja.

    Database tetap menjadi sumber status runtime AI, tetapi tidak pernah menjadi
    sumber list panel. Dengan begitu, sesi baru tidak mewarisi chat dari panel
    yang sudah dihapus atau dari sesi Manager sebelumnya.
    """
    if user_id is None:
        return []
    return list(_panel_chats.get(int(user_id), {}).values())


def _register_panel_chat(
    user_id: int,
    chat_id: int,
    *,
    enabled: bool,
    chat_title: str = "",
    chat_type: str = "",
) -> dict:
    """Tambah/update satu entry pada sesi panel in-memory."""
    user_id = int(user_id)
    chat_id = int(chat_id)
    session = _panel_chats.setdefault(user_id, {})
    existing = session.get(chat_id, {})
    entry = {
        "chat_id": chat_id,
        "chat_title": chat_title or existing.get("chat_title", ""),
        "chat_type": chat_type or existing.get("chat_type", "private"),
        "enabled": bool(enabled),
        "custom_instruction": existing.get("custom_instruction", ""),
        "updated_at": _now(),
    }
    session[chat_id] = entry
    return entry


def _update_panel_chat_if_present(
    user_id: int,
    chat_id: int,
    *,
    enabled: bool,
    chat_title: str = "",
    chat_type: str = "",
) -> dict | None:
    """Update entry yang sudah ada tanpa membuat panel/list baru dari OFF."""
    session = _panel_chats.get(int(user_id))
    if not session or int(chat_id) not in session:
        return None
    return _register_panel_chat(
        user_id,
        chat_id,
        enabled=enabled,
        chat_title=chat_title,
        chat_type=chat_type,
    )


def _clear_panel_session(user_id: int, *, message_id: int | None = None) -> None:
    """Hapus referensi panel dan seluruh list sesi dari memory."""
    user_id = int(user_id)
    if message_id is None or _active_panels.get(user_id) == message_id:
        _active_panels.pop(user_id, None)
        _panel_chats.pop(user_id, None)


def set_ai_chat_state_in_db(
    chat_id: int,
    enabled: bool,
    chat_title: str = "",
    chat_type: str = "",
    user_id: int | None = None,
) -> bool:
    """Update AI hanya di database runtime account yang menerima operasi."""
    db_path = _runtime_db_path(user_id)
    if db_path is None:
        log.warning("[AI Control] Runtime database account %s tidak ditemukan.", user_id)
        return False
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_chat_settings'"
            ).fetchone()
            if not table:
                return False
            existing = conn.execute(
                "SELECT * FROM ai_chat_settings WHERE chat_id = ?", (int(chat_id),)
            ).fetchone()
            title = chat_title or (existing["chat_title"] if existing else "")
            c_type = chat_type or (
                existing["chat_type"] if existing else ("group" if chat_id < 0 else "private")
            )
            conn.execute(
                """
                INSERT INTO ai_chat_settings
                    (chat_id, chat_title, chat_type, enabled, custom_instruction, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    chat_title = excluded.chat_title,
                    chat_type = excluded.chat_type,
                    enabled = excluded.enabled,
                    custom_instruction = excluded.custom_instruction,
                    updated_at = excluded.updated_at
                """,
                (
                    int(chat_id),
                    title,
                    c_type,
                    int(bool(enabled)),
                    existing["custom_instruction"] if existing else "",
                    _now(),
                ),
            )
            conn.commit()
        return True
    except Exception as exc:
        log.error("[AI Control] Gagal update runtime database %s: %s", db_path, exc)
        return False


def extract_chat_id(text: str) -> int | None:
    """Ekstrak Chat ID dari teks notifikasi AI secara tangguh."""
    if not text:
        return None

    patterns = [
        r"Chat\s*ID\s*:\s*[`*_\s]*([-\d]+)",
        r"(?:🆔|ID)\s*:\s*[`*_\s]*([-\d]+)",
        r"🆔\s*Chat\s*ID\s*:\s*[`*_\s]*([-\d]+)",
        r"\b(-100\d{7,15})\b",
        r"\b(\d{7,15})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue

    return None


def extract_chat_title(text: str) -> str:
    """Ekstrak judul/nama chat dari teks notifikasi AI."""
    if not text:
        return ""
    m = re.search(r"Chat\s*:\s*[*`]*([^\n`*]+)[*`]*", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def extract_chat_type(text: str) -> str:
    """Ekstrak tipe chat dari teks notifikasi AI."""
    if not text:
        return ""
    m = re.search(r"Tipe\s*:\s*[`*_\s]*([^\n`*_\s]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def _format_place_name(chat: dict | None) -> str:
    """Format nama tempat (group/PM) dengan batas panjang maksimal agar UI rapi."""
    if not chat:
        return "Unknown"
    raw_name = (chat.get("chat_title") or "").strip()
    chat_id = chat.get("chat_id", 0)

    if not raw_name:
        raw_name = "Grup" if chat_id < 0 else "User"

    # Truncate if too long (maksimal ~14-16 karakter)
    if len(raw_name) > 16:
        return raw_name[:13] + "..."
    return raw_name


def setup(client):
    """Daftarkan callback inline, auto-notifier, dan fallback command pada Manager Bot."""

    # 1. Handler Callback Query untuk Toggle ON/OFF per tempat
    @client.on_callback_query(filters.regex(r"^ai:toggle:([-\d]+):([01])$"))
    @safe_handler
    async def handle_ai_toggle(client, query):
        user_id = query.from_user.id if query.from_user else 0
        match = re.match(r"^ai:toggle:([-\d]+):([01])$", query.data)
        if not match:
            await query.answer()
            return

        chat_id = int(match.group(1))
        target_state = bool(int(match.group(2)))

        target_chat = _panel_chats.get(user_id, {}).get(chat_id)
        chat_title = target_chat.get("chat_title", "") if target_chat else ""
        chat_type = target_chat.get("chat_type", "") if target_chat else ""

        # Update database
        set_ai_chat_state_in_db(chat_id, enabled=target_state, user_id=user_id)

        _register_panel_chat(
            user_id,
            chat_id,
            enabled=target_state,
            chat_title=chat_title,
            chat_type=chat_type,
        )
        place_name = _format_place_name(target_chat)

        if target_state:
            await query.answer(f"🟢 AI diaktifkan untuk {place_name}", show_alert=False)
        else:
            await query.answer(f"🔴 AI dinonaktifkan untuk {place_name}", show_alert=False)

    # 2. Handler Pesan Notifikasi dari Userbot (.aibls / .aistop)
    @client.on_message(filters.private & ~filters.me, group=-20)
    @safe_handler
    async def handle_incoming_ai_notify(client, message):
        text = message.text or message.caption or ""
        sender_id = message.from_user.id if message.from_user else 0

        # Cek apakah ini notifikasi status AI dari Userbot
        is_ai_msg = (
            "[AI Chatbot]" in text
            or "AI Chatbot" in text
            or "ᴀɪ ᴄʜᴀᴛʙᴏᴛ" in text
            or "Chat ID:" in text
            or "Chat ID" in text
            or "Diaktifkan (ON)" in text
            or "Dinonaktifkan (OFF)" in text
        )
        if not is_ai_msg:
            raise ContinuePropagation

        chat_id = extract_chat_id(text)
        chat_title = extract_chat_title(text)
        chat_type = extract_chat_type(text)
        if chat_id is not None:
            is_enabled = (
                "Diaktifkan (ON)" in text
                or "diaktifkan" in text.lower()
                or not ("Dinonaktifkan" in text or "OFF" in text)
            )
            set_ai_chat_state_in_db(
                chat_id=chat_id,
                enabled=is_enabled,
                chat_title=chat_title,
                chat_type=chat_type,
                user_id=sender_id,
            )
            if is_enabled:
                _register_panel_chat(
                    sender_id,
                    chat_id,
                    enabled=True,
                    chat_title=chat_title,
                    chat_type=chat_type,
                )
            else:
                _update_panel_chat_if_present(
                    sender_id,
                    chat_id,
                    enabled=False,
                    chat_title=chat_title,
                    chat_type=chat_type,
                )

        # Jangan hapus pesan UI notifikasi, dan jangan kirim panel lama.
        raise ContinuePropagation

    # 3. Fallback Command /aistop pada Manager Bot
    @client.on_message(filters.command(["aistop", "stopai"]))
    @safe_handler
    async def handle_aistop(client, message):
        sender_id = message.from_user.id if message.from_user else 0
        reply_msg = message.reply_to_message

        if not reply_msg:
            help_text = (
                "⚠️ **Gunakan Reply Notifikasi**\n\n"
                "Command `/aistop` dapat digunakan dengan me-**reply** pesan notifikasi **AI ON**."
            )
            help_msg = await message.reply_text(help_text)
            asyncio.create_task(
                client.delete_messages(chat_id=message.chat.id, message_ids=[message.id, help_msg.id])
            )
            return

        reply_text = reply_msg.text or reply_msg.caption or ""
        target_chat_id = extract_chat_id(reply_text)
        target_chat_title = extract_chat_title(reply_text)

        if target_chat_id is None:
            help_text = (
                "⚠️ **Bukan Notifikasi AI ON yang Valid**\n\n"
                "Pesan yang di-reply tidak memuat Chat ID AI yang valid."
            )
            help_msg = await message.reply_text(help_text)
            return

        # Matikan AI pada chat target
        set_ai_chat_state_in_db(target_chat_id, enabled=False, chat_title=target_chat_title, user_id=sender_id)
        _update_panel_chat_if_present(
            sender_id,
            target_chat_id,
            enabled=False,
            chat_title=target_chat_title,
        )

        # Hapus pesan trigger
        try:
            await message.delete()
            await reply_msg.delete()
        except Exception:
            pass

