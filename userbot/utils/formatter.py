"""
IBEKS USERBOT - Centralized UI Formatter (Native Telegram MessageEntity Edition)
Standar UI Global untuk seluruh IBEKS Userbot:
- Header: Emoji + <b>Judul Small Caps</b> (MessageEntityBold)
- Separator: ─────────★─────────
- Konten Utama / Detail: Native Telegram Blockquote (MessageEntityBlockquote Layer 158)
- Separator: ─────────★─────────
- Footer: ⊱༺༄༅ <b>ɪʙᴇᴋ ᴜʙᴏᴛ</b> ༄༅༻⊰ dalam Native Blockquote terpisah (MessageEntityBlockquote Layer 158)
- Menggunakan Direct Telegram MessageEntity + UTF-16 Offset murni tanpa parser HTML.
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any, List, Optional, Sequence, Tuple

from pyrogram import raw
from pyrogram.types import User

# Import dan aktifkan patch MTProto Layer 158 Blockquote
from utils.telegram_patch import (
    PatchedMessageEntityBlockquote,
    apply_telegram_blockquote_patch,
    utf16_len,
)

apply_telegram_blockquote_patch()

SMALL_CAPS_MAP: dict[str, str] = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ғ", "g": "ɢ",
    "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ",
    "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "s", "t": "ᴛ", "u": "ᴜ",
    "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
    "A": "ᴀ", "B": "ʙ", "C": "ᴄ", "D": "ᴅ", "E": "ᴇ", "F": "ғ", "G": "ɢ",
    "H": "ʜ", "I": "ɪ", "J": "ᴊ", "K": "ᴋ", "L": "ʟ", "M": "ᴍ", "N": "ɴ",
    "O": "ᴏ", "P": "ᴘ", "Q": "ǫ", "R": "ʀ", "S": "s", "T": "ᴛ", "U": "ᴜ",
    "V": "ᴠ", "W": "ᴡ", "X": "x", "Y": "ʏ", "Z": "ᴢ",
}

SEPARATOR: str = "━━━━━━ ★ ━━━━━━"
DEFAULT_FOOTER: str = "✦ ɪʙᴇᴋs ᴜʙᴏᴛ ✦"

_CLEAN_FRAME_REGEX = re.compile(
    r"^[╭╰├│]\s*─*|^\s*│\s*|^\s*╰➤\s*",
    re.MULTILINE,
)
_LEGACY_FRAME_STRIP = re.compile(
    r"[╭╰├│─]|⨱\s*IBEKS\s*USERBOT\s*⨱|⨱\s*𝗜𝗕𝗘𝗞𝗦\s*𝗨𝗦𝗘𝗥𝗕𝗢𝗧\s*⨱",
    re.IGNORECASE,
)
_TAG_BLOCKQUOTE_REGEX = re.compile(
    r"</?blockquote(?:\s+[^>]*)?>",
    re.IGNORECASE,
)

# Inline formatting tags regex
_INLINE_TAG_REGEX = re.compile(
    r"<code>(?P<code>.*?)</code>|"
    r"`(?P<backtick_code>[^`\n]+)`|"
    r"<b>(?P<b>.*?)</b>|"
    r"\*\*(?P<markdown_bold>[^\*\n]+)\*\*|"
    r"<i>(?P<i>.*?)</i>|"
    r"__(?P<markdown_italic>[^_\n]+)__|"
    r"<u>(?P<u>.*?)</u>|"
    r"<s>(?P<s>.*?)</s>|"
    r'<a\s+href=[\'"](?P<url>[^\'"]+)[\'"]>(?P<link_text>.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)


class FormattedUI:
    """
    Objek hasil formatting UI yang menyimpan plain text dan daftar native Telegram MessageEntity.
    Mendukung unpacking (text, entities), konversi ke string str(obj), dan akses indeks.
    """

    __slots__ = ("text", "entities")

    def __init__(self, text: str, entities: list[Any]):
        self.text = str(text)
        self.entities = list(entities)

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"<FormattedUI len={len(self.text)} entities={len(self.entities)}>"

    def __iter__(self):
        yield self.text
        yield self.entities

    def __getitem__(self, item):
        if item == 0:
            return self.text
        elif item == 1:
            return self.entities
        raise IndexError(f"FormattedUI index out of range: {item}")


def to_small_caps(text: str) -> str:
    """Konversi teks alfabet menjadi karakter Unicode Small Caps."""
    if not text:
        return ""
    return "".join(SMALL_CAPS_MAP.get(ch, ch) for ch in text)


def char_width(c: str) -> int:
    """Hitung lebar visual satu karakter (emoji/fullwidth = 2 col, regular = 1 col)."""
    if ord(c) in (0xFE0E, 0xFE0F):
        return 0
    w = unicodedata.east_asian_width(c)
    if w in ("W", "F"):
        return 2
    code = ord(c)
    if (
        (0x1F000 <= code <= 0x1FFFF)
        or (0x2600 <= code <= 0x27BF)
        or (0x2300 <= code <= 0x23FF)
        or (0x2B00 <= code <= 0x2BFF)
        or (0x2100 <= code <= 0x21FF)
        or (0x203C <= code <= 0x2049)
    ):
        return 2
    return 1


def visual_width(s: str) -> int:
    """Hitung lebar visual teks dengan mengabaikan HTML tags."""
    clean = re.sub(r"<[^>]+>", "", str(s))
    return sum(char_width(c) for c in clean)


def wrap_text_words(text: str, max_w: int) -> List[str]:
    """Bungkus teks panjang per kata tanpa memotong kata."""
    words = str(text).split(" ")
    lines: List[str] = []
    curr = ""
    for w in words:
        if not w:
            continue
        if not curr:
            curr = w
        elif visual_width(curr + " " + w) <= max_w:
            curr += " " + w
        else:
            lines.append(curr)
            curr = w
    if curr:
        lines.append(curr)
    return lines or [str(text)]


def is_kv_line(line_str: str) -> bool:
    """Deteksi apakah satu baris string merupakan format label:value."""
    line_s = line_str.strip()
    if not line_s or line_s.startswith(("•", "├", "│", "╰", "╭", "—", "-", "*", "#", "http://", "https://")):
        return False
    if " : " in line_s:
        k, _ = line_s.split(" : ", 1)
        k_clean = re.sub(r"<[^>]+>", "", k).strip()
        if k_clean and not any(k_clean.startswith(p) for p in ("http:", "https:", "tg:")) and len(k_clean) <= 32:
            return True
    elif ":" in line_s:
        parts = line_s.split(":", 1)
        k = parts[0].strip()
        k_clean = re.sub(r"<[^>]+>", "", k).strip()
        if k_clean and len(k_clean) <= 32 and not any(k_clean.startswith(p) for p in ("http", "https", "tg")) and not re.match(r"^\d+$", k_clean):
            return True
    return False


def parse_line_kv(line_str: str) -> Tuple[str, Optional[str]]:
    """Parse satu baris label : value menjadi tuple (label, value)."""
    line_s = line_str.strip()
    if " : " in line_s:
        k, v = line_s.split(" : ", 1)
        return k.strip(), v.strip()
    elif ":" in line_s:
        parts = line_s.split(":", 1)
        return parts[0].strip(), parts[1].strip()
    return line_str, None


def format_kv_block(kv_pairs: Sequence[Tuple[str, Optional[str]]], max_width: int = 42) -> List[str]:
    """Format satu blok key-value: ratakan tanda ':', gunakan compact font jika panjang, dan wrap nilai panjang dengan indentasi sejajar."""
    if not kv_pairs:
        return []
    valid_pairs = [(k, v) for k, v in kv_pairs if v is not None and k]
    if not valid_pairs:
        return [k if v is None else f"{k} : {v}" for k, v in kv_pairs]

    max_lbl_w = max(visual_width(k) for k, v in valid_pairs)
    lines: List[str] = []
    for k, v in kv_pairs:
        if v is None:
            lines.append(k)
            continue
        if not k:
            lines.append(v)
            continue
        lbl_w = visual_width(k)
        pad = " " * max(0, max_lbl_w - lbl_w)
        prefix = f"{k}{pad} : "
        indent = " " * visual_width(prefix)
        avail_w = max(16, max_width - visual_width(prefix))

        v_subparts = str(v).split("\n")
        wrapped_all: List[str] = []
        for sub in v_subparts:
            # Jika nilai pendek, tetap gunakan font sekarang.
            # Jika nilai terlalu panjang melebihi avail_w di layar, gunakan versi font Unicode yang lebih compact.
            sub_clean = re.sub(r"<[^>]+>", "", sub)
            if visual_width(sub_clean) > avail_w and not ("<code" in sub or "<a " in sub):
                sub_formatted = to_small_caps(sub)
            else:
                sub_formatted = sub
            # Jika masih terlalu panjang setelah compact, lakukan word-wrap per kata
            wrapped_all.extend(wrap_text_words(sub_formatted, avail_w))

        if not wrapped_all:
            lines.append(prefix.rstrip())
        else:
            lines.append(f"{prefix}{wrapped_all[0]}")
            for cont in wrapped_all[1:]:
                lines.append(f"{indent}{cont}")
    return lines


def format_kv(items: Any, max_width: int = 42) -> str:
    """
    Helper Formatter Utama untuk seluruh output Label : Value di UBot.
    
    Fitur:
    - Semua tanda ':' sejajar vertikal per blok.
    - Jika nilai terlalu panjang, otomatis turun ke baris berikutnya.
    - Baris lanjutan sejajar dengan awal nilai setelah ':'.
    - Tidak memotong kata (word-wrap aman).
    - Mempertahankan font dan isi teks secara utuh.
    - Menerima dict, list of tuples, list of strings, atau multiline string.
    """
    if items is None:
        return ""

    if isinstance(items, dict):
        pairs = [(str(k).strip(), str(v).strip()) for k, v in items.items()]
        return "\n".join(format_kv_block(pairs, max_width=max_width))

    raw_entries: List[Any] = []
    if isinstance(items, str):
        raw_entries = items.splitlines()
    elif isinstance(items, (list, tuple, set)):
        for item in items:
            if item is None:
                continue
            if isinstance(item, (list, tuple)) and len(item) == 2:
                raw_entries.append((str(item[0]).strip(), str(item[1]).strip()))
            else:
                for sub in str(item).splitlines():
                    raw_entries.append(sub)

    result_lines: List[str] = []
    current_block: List[Tuple[str, Optional[str]]] = []

    for entry in raw_entries:
        if isinstance(entry, tuple):
            current_block.append(entry)
        elif isinstance(entry, str):
            line_s = entry.strip()
            if not line_s:
                if current_block:
                    result_lines.extend(format_kv_block(current_block, max_width=max_width))
                    current_block = []
                result_lines.append("")
            elif is_kv_line(line_s):
                k, v = parse_line_kv(line_s)
                current_block.append((k, v))
            else:
                if current_block:
                    result_lines.extend(format_kv_block(current_block, max_width=max_width))
                    current_block = []
                result_lines.append(line_s)

    if current_block:
        result_lines.extend(format_kv_block(current_block, max_width=max_width))

    return "\n".join(result_lines)


def center_aligned_footer(footer_text: str, target_width: int = 16) -> str:
    """
    Hitung alignment posisi tengah footer secara matematis agar tepat sejajar dengan titik tengah separator (★).
    Tidak menggunakan tebak-tebakan spasi manual melainkan visual_width.
    """
    f_clean = str(footer_text or "").strip()
    if not f_clean:
        return ""
    vw = visual_width(f_clean)
    if vw >= target_width:
        return f_clean
    pad_total = target_width - vw
    pad_left = pad_total // 2
    return (" " * pad_left) + f_clean


def clean_content_text(body: Any) -> str:
    """Bersihkan teks dan format label:value secara konsisten dengan indentasi sejajar."""
    if isinstance(body, FormattedUI):
        return body.text

    if body is None:
        return ""

    # Format semua label:value secara seragam
    formatted = format_kv(body)

    cleaned_lines = []
    for line in formatted.splitlines():
        line_clean = _CLEAN_FRAME_REGEX.sub("", line).rstrip()
        line_clean = _TAG_BLOCKQUOTE_REGEX.sub("", line_clean).rstrip()
        line_str = line_clean.strip()
        if line_str in ("│", "╭─", "╰─", "├", "│  ╰➤", "━━━━━━ ★ ━━━━━━", "─────────★─────────"):
            continue
        if "⨱ IBEKS USERBOT ⨱" in line or "⨱ 𝗜𝗕𝗘𝗞𝗦 𝗨𝗦𝗘𝗥𝗕𝗢𝗧 ⨱" in line:
            continue
        if line_str.startswith("「") and line_str.endswith("」"):
            continue
        if ("IBEK UBOT" in line_clean or "ɪʙᴇᴋ ᴜʙᴏᴛ" in line_clean or "ɪʙᴇᴋs ᴜʙᴏᴛ" in line_clean) and any(sym in line_clean for sym in ("⊱", "༺", "༻", "༒", "✦")):
            continue
        cleaned_lines.append(line_clean)
    return "\n".join(cleaned_lines).strip()


def parse_inline_entities(raw_text: str, base_offset: int = 0) -> Tuple[str, List[Any]]:
    """
    Parse inline format tags (code, bold, italic, underline, strike, url) dari raw_text.
    Mengembalikan tuple (plain_text_tanpa_tag, list_raw_entities) dengan offset UTF-16 yang akurat.
    """
    if not raw_text:
        return "", []

    entities: List[Any] = []
    plain_parts: List[str] = []
    current_plain_len = 0
    last_idx = 0

    for match in _INLINE_TAG_REGEX.finditer(raw_text):
        start, end = match.span()
        # Tambahkan teks sebelum match
        if start > last_idx:
            pre_text = html.unescape(raw_text[last_idx:start])
            plain_parts.append(pre_text)
            current_plain_len += utf16_len(pre_text)

        matched_dict = match.groupdict()
        if matched_dict.get("code") is not None:
            inner = html.unescape(matched_dict["code"])
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityCode(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16
        elif matched_dict.get("backtick_code") is not None:
            inner = html.unescape(matched_dict["backtick_code"])
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityCode(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16
        elif matched_dict.get("b") is not None:
            inner = html.unescape(matched_dict["b"])
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityBold(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16
        elif matched_dict.get("markdown_bold") is not None:
            inner = html.unescape(matched_dict["markdown_bold"])
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityBold(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16
        elif matched_dict.get("i") is not None:
            inner = html.unescape(matched_dict["i"])
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityItalic(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16
        elif matched_dict.get("markdown_italic") is not None:
            inner = html.unescape(matched_dict["markdown_italic"])
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityItalic(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16
        elif matched_dict.get("u") is not None:
            inner = html.unescape(matched_dict["u"])
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityUnderline(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16
        elif matched_dict.get("s") is not None:
            inner = html.unescape(matched_dict["s"])
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityStrike(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16
        elif matched_dict.get("url") is not None:
            url = matched_dict["url"]
            inner = html.unescape(matched_dict.get("link_text") or url)
            inner_u16 = utf16_len(inner)
            entities.append(
                raw.types.MessageEntityTextUrl(
                    offset=base_offset + current_plain_len,
                    length=inner_u16,
                    url=url,
                )
            )
            plain_parts.append(inner)
            current_plain_len += inner_u16

        last_idx = end

    if last_idx < len(raw_text):
        tail_text = html.unescape(raw_text[last_idx:])
        plain_parts.append(tail_text)

    return "".join(plain_parts), entities


def format_ui(
    title: str,
    body: Any = "",
    emoji: str = "💠",
    footer_text: str = DEFAULT_FOOTER,
    expandable: bool = False,
    status: str = "",
) -> FormattedUI:
    """
    Format visual resmi lengkap IBEKS Userbot dengan Direct Telegram MessageEntity (Layer 158):
    - Header (Small Caps + MessageEntityBold)
    - Separator
    - Body (PatchedMessageEntityBlockquote Layer 158)
    - Separator
    - Footer (PatchedMessageEntityBlockquote Layer 158 + <b>ɪʙᴇᴋ ᴜʙᴏᴛ</b>)
    """
    # 1. Bersihkan & siapkan Header (Emoji + Bold Small Caps)
    raw_title = (title or "").strip()
    raw_title = _LEGACY_FRAME_STRIP.sub("", raw_title).strip().strip("「」[]()<>")

    parts = raw_title.split(maxsplit=1)
    if parts and any(ord(c) > 127 for c in parts[0]) and not parts[0].isalnum():
        extracted_emoji = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        header_title = f"{extracted_emoji} {to_small_caps(rest)}".strip()
    else:
        title_sc = to_small_caps(raw_title)
        header_title = f"{emoji} {title_sc}".strip() if emoji else title_sc

    # 2. Bersihkan & rakit isi Body
    body_raw = clean_content_text(body)
    if status:
        status_clean = clean_content_text(status)
        body_raw = f"{body_raw}\n\n{status_clean}".strip() if body_raw else status_clean
    if not body_raw:
        body_raw = "-"

    # 3. Hitung offset UTF-16 struktur pesan
    # Baris 1: Header
    header_offset = 0
    header_length = utf16_len(header_title)

    # Baris 2: Separator atas
    sep_top = SEPARATOR

    # Hitung base offset untuk Body
    body_base_offset = utf16_len(f"{header_title}\n{sep_top}\n")

    # Parse inline formatting (<code>, <b>, dll.) di dalam body
    body_plain, body_inline_entities = parse_inline_entities(body_raw, base_offset=body_base_offset)
    body_length = utf16_len(body_plain)

    # Baris Separator bawah
    sep_bottom = SEPARATOR

    # Baris Footer (Dihitung centering alignment sejajar dengan ★ separator secara matematis)
    f_text = (footer_text or DEFAULT_FOOTER).strip()
    if "IBEK UBOT" in f_text:
        f_text = f_text.replace("IBEK UBOT", "ɪʙᴇᴋs ᴜʙᴏᴛ")
    elif "ɪʙᴇᴋ ᴜʙᴏᴛ" in f_text and "ɪʙᴇᴋs ᴜʙᴏᴛ" not in f_text:
        f_text = f_text.replace("ɪʙᴇᴋ ᴜʙᴏᴛ", "ɪʙᴇᴋs ᴜʙᴏᴛ")

    f_centered = center_aligned_footer(f_text, target_width=visual_width(sep_bottom))

    footer_base_offset = utf16_len(f"{header_title}\n{sep_top}\n{body_plain}\n{sep_bottom}\n")
    footer_length = utf16_len(f_centered)

    # 4. Susun plain text akhir
    full_text = f"{header_title}\n{sep_top}\n{body_plain}\n{sep_bottom}\n{f_centered}"

    # 5. Susun seluruh native MessageEntity
    entities: List[Any] = []

    # Entity Bold untuk Header
    entities.append(raw.types.MessageEntityBold(offset=header_offset, length=header_length))

    # Entity Native Blockquote untuk Body Konten Utama (Layer 158 standard)
    entities.append(
        PatchedMessageEntityBlockquote(
            offset=body_base_offset,
            length=body_length,
            collapsed=False,
        )
    )

    # Tambahkan inline formatting di dalam body (code, bold, italic, dll.)
    entities.extend(body_inline_entities)

    # Entity Native Blockquote untuk Footer
    entities.append(
        PatchedMessageEntityBlockquote(
            offset=footer_base_offset,
            length=footer_length,
            collapsed=False,
        )
    )

    # Entity Bold untuk kata 'ɪʙᴇᴋs ᴜʙᴏᴛ' / 'ɪʙᴇᴋ ᴜʙᴏᴛ' di Footer
    for target_sub in ("ɪʙᴇᴋs ᴜʙᴏᴛ", "ɪʙᴇᴋ ᴜʙᴏᴛ"):
        if target_sub in f_centered:
            sub_idx = f_centered.find(target_sub)
            sub_offset = footer_base_offset + utf16_len(f_centered[:sub_idx])
            sub_len = utf16_len(target_sub)
            entities.append(raw.types.MessageEntityBold(offset=sub_offset, length=sub_len))
            break

    return FormattedUI(full_text, entities)


# Alias resmi
ibeks_ui = format_ui


def success(
    title: str = "SUKSES",
    message: Any = "",
    emoji: str = "✅",
    footer_text: str = DEFAULT_FOOTER,
    expandable: bool = False,
) -> FormattedUI:
    """Format pesan sukses dengan native blockquote."""
    return format_ui(
        title=title,
        body=message,
        emoji=emoji,
        footer_text=footer_text,
        expandable=expandable,
    )


def error(
    title: str = "ERROR",
    message: Any = "",
    emoji: str = "❌",
    footer_text: str = DEFAULT_FOOTER,
    expandable: bool = False,
) -> FormattedUI:
    """Format pesan error dengan native blockquote."""
    return format_ui(
        title=title,
        body=message,
        emoji=emoji,
        footer_text=footer_text,
        expandable=expandable,
    )


def warning(
    title: str = "WARNING",
    message: Any = "",
    emoji: str = "⚠️",
    footer_text: str = DEFAULT_FOOTER,
    expandable: bool = False,
) -> FormattedUI:
    """Format pesan peringatan dengan native blockquote."""
    return format_ui(
        title=title,
        body=message,
        emoji=emoji,
        footer_text=footer_text,
        expandable=expandable,
    )


def info(
    title: str = "INFO",
    message: Any = "",
    emoji: str = "ℹ️",
    footer_text: str = DEFAULT_FOOTER,
    expandable: bool = False,
) -> FormattedUI:
    """Format pesan informasi dengan native blockquote."""
    return format_ui(
        title=title,
        body=message,
        emoji=emoji,
        footer_text=footer_text,
        expandable=expandable,
    )


def list_ui(
    title: str,
    items: Sequence[str],
    emoji: str = "📋",
    footer_text: str = DEFAULT_FOOTER,
    expandable: bool = False,
) -> FormattedUI:
    """Format tampilan daftar / list data dengan native blockquote."""
    formatted_items = [f"• {item}" if not str(item).startswith("•") else str(item) for item in items]
    return format_ui(
        title=title,
        body="\n".join(formatted_items),
        emoji=emoji,
        footer_text=footer_text,
        expandable=expandable,
    )


def escape_md(text: Optional[str]) -> str:
    """Escape karakter Markdown umum."""
    if not text:
        return ""
    chars = ["_", "*", "[", "]", "(", ")", "~", "`", "\\", ">", "#", "+", "-", "=", "|", "{", "}"]
    for ch in chars:
        text = text.replace(ch, f"\\{ch}")
    return text


def escape_html(text: Optional[str]) -> str:
    """Escape teks HTML."""
    if not text:
        return ""
    return html.escape(str(text), quote=False)


def mention(user: User) -> str:
    """Buat mention dari objek User."""
    if user.username:
        return f"@{user.username}"
    name = user.first_name or "Unknown"
    return f'<a href="tg://user?id={user.id}">{escape_html(name)}</a>'


def format_user_info(user: User, chat_id: Optional[int] = None) -> FormattedUI:
    """Format informasi user untuk command .id"""
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Tidak diketahui"
    username = f"@{user.username}" if user.username else "Tidak ada"
    status = "Bot" if getattr(user, "is_bot", False) else "User"

    body_lines = [
        f"👤 Nama : {name}",
        f"🔗 Username : {username}",
        f"🆔 User ID : <code>{user.id}</code>",
        f"🤖 Status : {status}",
    ]
    if chat_id is not None:
        body_lines.append(f"💬 Chat ID : <code>{chat_id}</code>")

    return format_ui(
        title="INFO USER",
        body=body_lines,
        emoji="👤",
    )


def format_me_info(user: User) -> FormattedUI:
    """Format informasi akun sendiri untuk command .me"""
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    username = f"@{user.username}" if user.username else "Tidak ada"
    premium = "Ya" if getattr(user, "is_premium", False) else "Tidak"
    dc_id = getattr(user, "dc_id", None)
    dc_info = f"<code>{dc_id}</code>" if dc_id else "Tidak tersedia"

    body_lines = [
        f"👤 Nama : {name}",
        f"🔗 Username : {username}",
        f"🆔 User ID : <code>{user.id}</code>",
        f"⭐ Premium : {premium}",
        f"🌐 DC ID : {dc_info}",
    ]

    return format_ui(
        title="INFO AKUN",
        body=body_lines,
        emoji="👤",
    )


def format_status(success_flag: bool, text: str) -> FormattedUI:
    """Format pesan status dengan UI konsisten."""
    if success_flag:
        return success("SUKSES", text)
    return error("GAGAL", text)
