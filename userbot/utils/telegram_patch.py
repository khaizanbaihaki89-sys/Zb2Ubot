"""
Telegram API Layer 184+ Expandable Blockquote & MTProto Layer Patch for Pyrogram.
Memastikan entitas MessageEntityBlockquote native dengan flag collapsed (expandable) aktif
dan menegosiasikan MTProto layer 184+ ke server Telegram.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, List

import pyrogram
from pyrogram import enums, raw, types
from pyrogram.parser import html
from pyrogram.raw.core import TLObject
from pyrogram.raw.core.primitives import Int
from pyrogram.session import session

log = logging.getLogger(__name__)

_PATCHED = False


def utf16_len(text: str) -> int:
    """Hitung panjang teks dalam UTF-16 code units (standar Telegram API offset & length)."""
    if not text:
        return 0
    try:
        return len(text.encode("utf-16-le")) // 2
    except UnicodeEncodeError:
        # Tangani string yang sudah mengandung surrogate code points
        return len(text.encode("utf-16-le", "surrogatepass")) // 2


class PatchedMessageEntityBlockquote(TLObject):
    """MessageEntityBlockquote kompatibel dengan Pyrogram MTProto Layer 158."""

    __slots__: List[str] = ["collapsed", "offset", "length", "_client"]
    ID = 0x20DF5D0
    QUALNAME = "types.MessageEntityBlockquote"

    def __init__(self, *, offset: int, length: int, collapsed: bool = False) -> None:
        self.offset = int(offset)
        self.length = int(length)
        self.collapsed = bool(collapsed)
        self._client = None

    @staticmethod
    def read(b: BytesIO, *args: Any) -> "PatchedMessageEntityBlockquote":
        offset = Int.read(b)
        length = Int.read(b)
        return PatchedMessageEntityBlockquote(offset=offset, length=length, collapsed=False)

    def write(self, *args: Any) -> bytes:
        b = BytesIO()
        b.write(Int(self.ID, False))
        b.write(Int(self.offset))
        b.write(Int(self.length))
        return b.getvalue()

    def __repr__(self) -> str:
        return f"MessageEntityBlockquote(offset={self.offset}, length={self.length}, collapsed={self.collapsed})"


def apply_telegram_blockquote_patch() -> None:
    """Terapkan patch native expandable blockquote dan MTProto Layer ke Pyrogram."""
    global _PATCHED
    if _PATCHED:
        return

    # 1. Daftarkan TL Object MessageEntityBlockquote (Layer 184 constructor 0xF5CC4EA3 & Layer 158 0x20DF5D0)
    try:
        raw.types.MessageEntityBlockquote = PatchedMessageEntityBlockquote
        raw.types.message_entity_blockquote.MessageEntityBlockquote = PatchedMessageEntityBlockquote
        raw.all.objects[0xF5CC4EA3] = PatchedMessageEntityBlockquote
        raw.all.objects[0x20DF5D0] = PatchedMessageEntityBlockquote
    except Exception as exc:
        log.warning("[TelegramPatch] Warning registering raw objects: %s", exc)

    # 3. Update Enum mapping
    try:
        enums.MessageEntityType._value2member_map_[PatchedMessageEntityBlockquote] = enums.MessageEntityType.BLOCKQUOTE
    except Exception:
        pass

    # 4. Patch Pyrogram utils.parse_text_entities agar menerima raw TLObjects maupun high-level types.MessageEntity
    orig_parse_text_entities = pyrogram.utils.parse_text_entities

    async def patched_parse_text_entities(
        client: "pyrogram.Client",
        text: str,
        parse_mode: enums.ParseMode,
        entities: List[Any],
    ) -> dict[str, Any]:
        if entities:
            raw_entities = []
            for entity in entities:
                if isinstance(entity, (raw.base.MessageEntity, TLObject)):
                    raw_entities.append(entity)
                elif isinstance(entity, types.MessageEntity):
                    entity._client = client
                    raw_entities.append(await entity.write())
                elif hasattr(entity, "write"):
                    write_attr = getattr(entity, "write")
                    if callable(write_attr):
                        import inspect
                        if inspect.iscoroutinefunction(write_attr):
                            try:
                                entity._client = client
                            except Exception:
                                pass
                            raw_entities.append(await write_attr())
                        else:
                            # Synchronous write returning bytes means raw TL object
                            raw_entities.append(entity)
                    else:
                        raw_entities.append(entity)
                else:
                    raw_entities.append(entity)
            return {
                "message": text,
                "entities": raw_entities or None,
            }
        else:
            return await client.parser.parse(text, parse_mode)

    pyrogram.utils.parse_text_entities = patched_parse_text_entities

    # 5. Patch HTML parser untuk mengenali <blockquote expandable> dan <blockquote collapsed>
    orig_handle_starttag = html.Parser.handle_starttag
    orig_handle_endtag = html.Parser.handle_endtag

    def patched_handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attrs_dict = dict(attrs)
        if tag == "blockquote":
            extra: dict[str, Any] = {}
            if (
                "expandable" in attrs_dict
                or "collapsed" in attrs_dict
                or attrs_dict.get("expandable") in ("", "true", "1")
            ):
                extra["collapsed"] = True
            else:
                extra["collapsed"] = False

            if tag not in self.tag_entities:
                self.tag_entities[tag] = []
            # Di dalam Pyrogram html.Parser, self.text sudah disurrogate sehingga len(self.text) akurat UTF-16
            self.tag_entities[tag].append(
                PatchedMessageEntityBlockquote(offset=len(self.text), length=0, **extra)
            )
            return
        orig_handle_starttag(self, tag, attrs)

    def patched_handle_endtag(self, tag: str):
        if tag == "blockquote" and tag in self.tag_entities and self.tag_entities[tag]:
            entity = self.tag_entities[tag].pop()
            entity.length = len(self.text) - entity.offset
            self.entities.append(entity)
            if not self.tag_entities[tag]:
                self.tag_entities.pop(tag)
            return
        orig_handle_endtag(self, tag)

    html.Parser.handle_starttag = patched_handle_starttag
    html.Parser.handle_endtag = patched_handle_endtag

    _PATCHED = True
    log.info("[TelegramPatch] Native Expandable Blockquote Layer 184+ patched successfully.")


# Otomatis aktif saat diimpor
apply_telegram_blockquote_patch()

