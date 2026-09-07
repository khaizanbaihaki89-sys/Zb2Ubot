"""Transport UI tunggal untuk fitur IBEKS Control Panel."""

from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from plugins.utils.ui import edit_ui
from utils.theme import emoji, render


def keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Buat markup inline Pyrogram dari label dan callback data."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=data) for label, data in row]
            for row in rows
        ]
    )


def nav_rows(back: str = "cp:home") -> list[list[tuple[str, str]]]:
    return [[("⬅ Back", back), ("🏠 Home", "cp:home"), ("❌ Close", "cp:close")]]


def body(title: str, lines: list[str], status: str = "") -> str:
    return render(f"{emoji(title)} {title}", "\n".join(lines), status=status)


async def edit_panel(query, title: str, lines: list[str], markup=None, status: str = ""):
    """Edit pesan panel yang sama, dengan fallback jika pesan belum bisa diedit."""
    text = body(title, lines, status=status)
    await edit_ui(
        query._client,
        query.message,
        text,
        reply_markup=markup,
        expandable=False,
    )
