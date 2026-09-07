"""
Transport teks UI yang diformat dengan standar resmi IBEKS Userbot.
Menggunakan Direct Telegram MessageEntity + entities (MTProto Layer 158 Native Blockquote).
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from utils.formatter import (
    FormattedUI,
    clean_content_text,
    format_ui,
    parse_inline_entities,
)
import utils.telegram_patch  # Patch native blockquotes


def _extract_ui(
    body: Any,
    title: str = "",
    category: str = "",
    status: str = "",
    expandable: bool = False,
    emoji: str = "💀",
) -> Tuple[str, List[Any]]:
    """
    Ekstrak plain text dan direct MessageEntity objects dari input body.
    Menjamin tidak ada ketergantungan pada HTML Parser Pyrogram.
    """
    # Kasus 1: Input sudah berupa instance FormattedUI
    if isinstance(body, FormattedUI):
        return body.text, body.entities

    # Kasus 2: Input berupa tuple (text, entities)
    if (
        isinstance(body, (tuple, list))
        and len(body) == 2
        and isinstance(body[0], str)
        and isinstance(body[1], (list, tuple))
    ):
        return body[0], list(body[1])

    raw = str(body or "").strip()

    # Kasus 3: Jika caller memberikan title eksplisit
    if title:
        formatted = format_ui(
            title=title,
            body=raw,
            emoji=emoji,
            status=status,
            expandable=expandable,
        )
        return formatted.text, formatted.entities

    # Kasus 4: Deteksi judul otomatis dari teks plain / legacy
    cleaned = clean_content_text(raw)
    if not cleaned:
        cleaned = "-"

    default_title = "INFO"
    default_emoji = emoji
    lower_cleaned = cleaned.lower()

    if cleaned.startswith("✅") or "berhasil" in lower_cleaned or "sukses" in lower_cleaned:
        default_title = "SUKSES"
        default_emoji = "✅"
    elif cleaned.startswith("❌") or "gagal" in lower_cleaned or "error" in lower_cleaned:
        default_title = "ERROR"
        default_emoji = "❌"
    elif cleaned.startswith("⚠️") or "peringatan" in lower_cleaned or "warning" in lower_cleaned:
        default_title = "WARNING"
        default_emoji = "⚠️"

    formatted = format_ui(
        title=default_title,
        body=cleaned,
        emoji=default_emoji,
        status=status,
        expandable=expandable,
    )
    return formatted.text, formatted.entities


async def send_ui(
    client,
    chat_id: int,
    body: Any,
    title: str = "",
    category: str = "",
    status: str = "",
    expandable: bool = False,
    reply_markup=None,
    emoji: str = "💀",
    **kwargs,
):
    """Kirim teks UI dengan Direct MessageEntity sesuai standar IBEKS."""
    text, entities = _extract_ui(
        body=body,
        title=title,
        category=category,
        status=status,
        expandable=expandable,
        emoji=emoji,
    )

    # Pastikan parse_mode tidak menimpa entitas langsung
    kwargs.pop("parse_mode", None)
    kwargs["entities"] = entities

    return await client.send_message(
        chat_id,
        text,
        reply_markup=reply_markup,
        **kwargs,
    )


async def edit_ui(
    client,
    message,
    body: Any,
    title: str = "",
    emoji: str = "💀",
    reply_markup=None,
    expandable: bool = False,
    status: str = "",
    **kwargs,
):
    """Edit teks UI dengan Direct MessageEntity sesuai standar IBEKS."""
    text, entities = _extract_ui(
        body=body,
        title=title,
        status=status,
        expandable=expandable,
        emoji=emoji,
    )

    message_id = getattr(message, "id", None)
    if message_id is None:
        message_id = getattr(message, "message_id", None)
    if message_id is None:
        raise AttributeError("Message object tidak memiliki id untuk diedit")

    chat_id = getattr(message, "chat", None)
    chat_id = getattr(chat_id, "id", None) if chat_id else message_id

    # Pastikan parse_mode tidak menimpa entitas langsung
    kwargs.pop("parse_mode", None)
    kwargs["entities"] = entities

    return await client.edit_message_text(
        chat_id,
        message_id,
        text,
        reply_markup=reply_markup,
        **kwargs,
    )
