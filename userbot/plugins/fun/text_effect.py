"""
IBEKS USERBOT - Plugin: Fun Text Effect
Commands:
  .flip <teks>    - Membalik teks secara vertikal/terbalik (upside down)
  .glitch <teks>  - Memberi efek glitch / corrupted unicode pada teks
  .bold <teks>    - Mengubah teks menjadi huruf tebal (unicode bold)
  .tiny <teks>    - Mengubah teks menjadi huruf kecil mini (small caps)
  .bubble <teks>  - Mengubah teks menjadi huruf dalam lingkaran (bubble)
  .zalgo <teks>   - Memberi efek seram / zalgo bertingkat pada teks
  .mock <teks>    - Mengubah teks menjadi gaya SpongeBob Mocking (kapital selang-seling)
  .random <teks>  - Mengubah kapitalisasi huruf secara acak
  .alay <teks>    - Mengubah teks menjadi gaya tulisan alay / 4l4y
  .type <teks>    - Efek mesin tik (typewriter) dengan edit message bertahap

Plugin ini mandiri, sederhana, dan tidak memerlukan database.
"""

import asyncio
import random
from typing import Any

from pyrogram import filters

from utils.formatter import warning
from plugins.utils.ui import edit_ui
from utils.filters import dynamic_command
from utils.logger import log

__version__ = "1.0.0"
__author__ = "IBEKS"

# ── 1. MAPS & DATA TRANSFORMASI TEKS ─────────────────────────────────────────

FLIP_MAP: dict[str, str] = {
    "a": "ɐ", "b": "q", "c": "ɔ", "d": "p", "e": "ǝ", "f": "ɟ", "g": "ƃ", "h": "ɥ",
    "i": "ᴉ", "j": "ɾ", "k": "ʞ", "l": "l", "m": "ɯ", "n": "u", "o": "o", "p": "d",
    "q": "b", "r": "ɹ", "s": "s", "t": "ʇ", "u": "n", "v": "ʌ", "w": "ʍ", "x": "x",
    "y": "ʎ", "z": "z",
    "A": "∀", "B": "𐐒", "C": "Ɔ", "D": "p", "E": "Ǝ", "F": "Ⅎ", "G": "פ", "H": "H",
    "I": "I", "J": "ſ", "K": "ʞ", "L": "˥", "M": "W", "N": "N", "O": "O", "P": "Ԁ",
    "Q": "Q", "R": "ɹ", "S": "S", "T": "┴", "U": "∩", "V": "Λ", "W": "M", "X": "X",
    "Y": "⅄", "Z": "Z",
    "0": "0", "1": "Ɩ", "2": "ᄅ", "3": "Ɛ", "4": "ㄣ", "5": "ϛ", "6": "9", "7": "ㄥ",
    "8": "8", "9": "6",
    ".": "˙", ",": "'", "'": ",", '"': "„", "!": "¡", "?": "¿", "<": ">", ">": "<",
    "(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "_": "‾", "&": "⅋",
    ";": "؛", ":": ":", "`": "ˎ",
}

TINY_MAP: dict[str, str] = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ғ", "g": "ɢ",
    "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ",
    "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "s", "t": "ᴛ", "u": "ᴜ",
    "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
    "A": "ᴀ", "B": "ʙ", "C": "ᴄ", "D": "ᴅ", "E": "ᴇ", "F": "ғ", "G": "ɢ",
    "H": "ʜ", "I": "ɪ", "J": "ᴊ", "K": "ᴋ", "L": "ʟ", "M": "ᴍ", "N": "ɴ",
    "O": "ᴏ", "P": "ᴘ", "Q": "ǫ", "R": "ʀ", "S": "s", "T": "ᴛ", "U": "ᴜ",
    "V": "ᴠ", "W": "ᴡ", "X": "x", "Y": "ʏ", "Z": "ᴢ",
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
}

ALAY_MAP: dict[str, str] = {
    "a": "4", "A": "4",
    "e": "3", "E": "3",
    "i": "1", "I": "1",
    "g": "9", "G": "9",
    "o": "0", "O": "0",
    "s": "5", "S": "5",
    "b": "8", "B": "8",
    "z": "2", "Z": "2",
}

GLITCH_COMBINING: tuple[str, ...] = (
    "\u0334", "\u0335", "\u0336", "\u0337", "\u0338",
    "\u035b", "\u035c", "\u035d", "\u035e", "\u0360", "\u0361", "\u0362",
)

ZALGO_UP: tuple[str, ...] = tuple(
    [chr(i) for i in range(0x0300, 0x0315)] + [chr(i) for i in range(0x033D, 0x0345)]
)
ZALGO_MID: tuple[str, ...] = tuple(
    [chr(i) for i in range(0x0315, 0x031C)] + [chr(i) for i in range(0x0334, 0x0339)]
)
ZALGO_DOWN: tuple[str, ...] = tuple(
    [chr(i) for i in range(0x0316, 0x0321)] + [chr(i) for i in range(0x0329, 0x0334)]
)


# ── 2. FUNGSI TRANSFORMASI ──────────────────────────────────────────────────

def effect_flip(text: str) -> str:
    """Membalik urutan dan orientasi teks (upside down)."""
    return "".join(FLIP_MAP.get(c, c) for c in reversed(text))


def effect_glitch(text: str) -> str:
    """Memberikan efek glitch strikethrough & combining character."""
    result: list[str] = []
    for c in text:
        if c.isspace():
            result.append(c)
        else:
            result.append(c)
            # Berikan 1-2 combining overlay glitch
            for _ in range(random.randint(1, 2)):
                result.append(random.choice(GLITCH_COMBINING))
    return "".join(result)


def effect_bold(text: str) -> str:
    """Mengubah teks alfabet dan angka menjadi Unicode Mathematical Sans-Bold."""
    result: list[str] = []
    for c in text:
        if "A" <= c <= "Z":
            result.append(chr(ord(c) - ord("A") + 0x1D5D4))
        elif "a" <= c <= "z":
            result.append(chr(ord(c) - ord("a") + 0x1D5EE))
        elif "0" <= c <= "9":
            result.append(chr(ord(c) - ord("0") + 0x1D7EC))
        else:
            result.append(c)
    return "".join(result)


def effect_tiny(text: str) -> str:
    """Mengubah teks menjadi Unicode Small Caps & Subscript."""
    return "".join(TINY_MAP.get(c, c) for c in text)


def effect_bubble(text: str) -> str:
    """Mengubah teks menjadi huruf dan angka berlingkar (bubble)."""
    result: list[str] = []
    for c in text:
        if "A" <= c <= "Z":
            result.append(chr(ord(c) - ord("A") + 0x24B6))
        elif "a" <= c <= "z":
            result.append(chr(ord(c) - ord("a") + 0x24D0))
        elif "1" <= c <= "9":
            result.append(chr(ord(c) - ord("1") + 0x2460))
        elif c == "0":
            result.append("⓪")
        else:
            result.append(c)
    return "".join(result)


def effect_zalgo(text: str) -> str:
    """Memberikan efek zalgo bertingkat di atas, tengah, dan bawah karakter."""
    result: list[str] = []
    for c in text:
        if c.isspace():
            result.append(c)
            continue
        result.append(c)
        for _ in range(random.randint(1, 3)):
            result.append(random.choice(ZALGO_UP))
        for _ in range(random.randint(0, 1)):
            result.append(random.choice(ZALGO_MID))
        for _ in range(random.randint(1, 3)):
            result.append(random.choice(ZALGO_DOWN))
    return "".join(result)


def effect_mock(text: str) -> str:
    """SpongeBob Mocking Case (kapital selang-seling)."""
    result: list[str] = []
    upper = False
    for c in text:
        if c.isalpha():
            result.append(c.upper() if upper else c.lower())
            upper = not upper
        else:
            result.append(c)
    return "".join(result)


def effect_random(text: str) -> str:
    """Kapitalisasi acak untuk setiap huruf."""
    result: list[str] = []
    for c in text:
        if c.isalpha():
            result.append(random.choice((c.lower(), c.upper())))
        else:
            result.append(c)
    return "".join(result)


def effect_alay(text: str) -> str:
    """Gaya tulisan alay dengan penggantian angka dan variasi huruf."""
    result: list[str] = []
    for i, c in enumerate(text):
        if c in ALAY_MAP:
            result.append(ALAY_MAP[c])
        elif c.isalpha():
            result.append(c.upper() if i % 2 == 0 else c.lower())
        else:
            result.append(c)
    return "".join(result)


# ── 3. HELPER EKSTRAKSI TEKS ─────────────────────────────────────────────────

def _extract_input_text(message: Any) -> str:
    """Ekstrak teks yang diberikan setelah nama command."""
    content = message.text or message.caption or ""
    parts = content.split(None, 1)
    if len(parts) > 1:
        return parts[1].strip()
    return ""


async def _apply_text_effect(client: Any, message: Any, cmd_name: str, transform_func: Any) -> None:
    """Helper untuk menjalankan transformasi dan mengedit pesan."""
    input_text = _extract_input_text(message)
    if not input_text:
        await edit_ui(client, message, warning("TEXT EFFECT", f"Berikan teks yang ingin diolah!\n💡 Contoh: <code>.{cmd_name} teks kamu</code>"))
        return

    transformed = transform_func(input_text)
    try:
        await message.edit_text(transformed)
    except Exception as exc:
        log.debug(f"[TextEffect] Gagal edit pesan untuk .{cmd_name}: {exc}")


# ── 4. PLUGIN LOADER SETUP ───────────────────────────────────────────────────

def setup(client: Any) -> None:
    """Daftarkan seluruh handler Fun Text Effect ke client."""

    @client.on_message(dynamic_command("flip") & filters.me)
    async def cmd_flip(client: Any, message: Any):
        """Handler command .flip <teks>"""
        await _apply_text_effect(client, message, "flip", effect_flip)

    @client.on_message(dynamic_command("glitch") & filters.me)
    async def cmd_glitch(client: Any, message: Any):
        """Handler command .glitch <teks>"""
        await _apply_text_effect(client, message, "glitch", effect_glitch)

    @client.on_message(dynamic_command("bold") & filters.me)
    async def cmd_bold(client: Any, message: Any):
        """Handler command .bold <teks>"""
        await _apply_text_effect(client, message, "bold", effect_bold)

    @client.on_message(dynamic_command("tiny") & filters.me)
    async def cmd_tiny(client: Any, message: Any):
        """Handler command .tiny <teks>"""
        await _apply_text_effect(client, message, "tiny", effect_tiny)

    @client.on_message(dynamic_command("bubble") & filters.me)
    async def cmd_bubble(client: Any, message: Any):
        """Handler command .bubble <teks>"""
        await _apply_text_effect(client, message, "bubble", effect_bubble)

    @client.on_message(dynamic_command("zalgo") & filters.me)
    async def cmd_zalgo(client: Any, message: Any):
        """Handler command .zalgo <teks>"""
        await _apply_text_effect(client, message, "zalgo", effect_zalgo)

    @client.on_message(dynamic_command("mock") & filters.me)
    async def cmd_mock(client: Any, message: Any):
        """Handler command .mock <teks>"""
        await _apply_text_effect(client, message, "mock", effect_mock)

    @client.on_message(dynamic_command("random") & filters.me)
    async def cmd_random(client: Any, message: Any):
        """Handler command .random <teks>"""
        await _apply_text_effect(client, message, "random", effect_random)

    @client.on_message(dynamic_command("alay") & filters.me)
    async def cmd_alay(client: Any, message: Any):
        """Handler command .alay <teks>"""
        await _apply_text_effect(client, message, "alay", effect_alay)

    @client.on_message(dynamic_command("type") & filters.me)
    async def cmd_type(client: Any, message: Any):
        """Handler command .type <teks> (efek typewriter bertahap)."""
        input_text = _extract_input_text(message)
        if not input_text:
            await edit_ui(client, message, warning("TYPE EFFECT", "Berikan teks yang ingin diketik!\n💡 Contoh: <code>.type Halo semuanya!</code>"))
            return

        cursor = "▌"
        # Sesuaikan langkah karakter agar animasi mulus tanpa memicu flood limit
        text_len = len(input_text)
        step = 1 if text_len <= 25 else (2 if text_len <= 60 else 3)
        delay = 0.08 if text_len <= 30 else 0.05

        for i in range(1, text_len + 1, step):
            partial_text = input_text[:i]
            try:
                await message.edit_text(partial_text + cursor)
                await asyncio.sleep(delay)
            except Exception:
                pass

        # Edit akhir menampilkan teks final tanpa kursor
        try:
            await message.edit_text(input_text)
        except Exception as exc:
            log.debug(f"[TextEffect] Final edit .type gagal: {exc}")
