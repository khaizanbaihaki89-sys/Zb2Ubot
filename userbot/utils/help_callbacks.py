"""CallbackQueryHandler untuk navigasi inline help."""

from __future__ import annotations

from pyrogram import filters
from pyrogram.errors import RPCError
from pyrogram.handlers import CallbackQueryHandler

from utils.help_builder import (
    build_category_text,
    build_home_text,
    category_keyboard,
    clamp_page,
    get_plan,
    home_keyboard,
    page_count,
    scan_plugins,
    total_plugins,
)
from utils.logger import log
from utils.prefix_manager import get_prefix


CALLBACK_FILTER = filters.regex(
    r"^(?:help_home|help_page(?::\d+)?|help_category:[^:]+:\d+|help_back(?::\d+)?)$"
)


async def _owner_name(client) -> str:
    user = await client.get_me()
    return user.first_name or user.username or str(user.id)


async def _edit_text_and_markup(client, message, text, reply_markup) -> None:
    """Edit pesan yang sama; tidak pernah membuat pesan navigasi baru."""
    try:
        await client.edit_message_text(
            message.chat.id,
            message.id,
            text,
            reply_markup=reply_markup,
        )
    except RPCError as exc:
        # Telegram mengembalikan MessageNotModified jika user menekan tombol
        # halaman yang sama. Tetap sinkronkan markup jika diperlukan.
        log.debug("[Help] Teks tidak berubah: %s", exc)
        try:
            await client.edit_message_reply_markup(
                message.chat.id,
                message.id,
                reply_markup=reply_markup,
            )
        except RPCError as markup_exc:
            log.debug("[Help] Keyboard tidak berubah: %s", markup_exc)


async def _render_home(client, message, catalog, page: int) -> None:
    page = clamp_page(catalog, page)
    owner = await _owner_name(client)
    text = build_home_text(
        plan=get_plan(client.me.id),
        prefix=get_prefix(),
        plugins=total_plugins(catalog),
        owner=owner,
        page=page,
        pages=page_count(catalog),
    )
    await _edit_text_and_markup(client, message, text, home_keyboard(catalog, page))


async def _render_category(client, message, catalog, key: str, previous_page: int) -> None:
    category = catalog.get(key)
    if category is None:
        await _render_home(client, message, catalog, previous_page)
        return

    owner = await _owner_name(client)
    text = build_category_text(
        category=category,
        plan=get_plan(client.me.id),
        prefix=get_prefix(),
        plugins=total_plugins(catalog),
        owner=owner,
    )
    await _edit_text_and_markup(
        client,
        message,
        text,
        category_keyboard(previous_page),
    )


async def handle_help_callback(client, query) -> None:
    """Tangani empat jenis callback help dengan prefix data yang konsisten."""
    data = query.data or ""
    if isinstance(data, bytes):
        data = data.decode(errors="ignore")

    await query.answer()
    if not query.message:
        return

    catalog = scan_plugins()
    if data == "help_home":
        await _render_home(client, query.message, catalog, 0)
    elif data.startswith("help_page:"):
        try:
            page = int(data.split(":", 1)[1])
        except ValueError:
            page = 0
        await _render_home(client, query.message, catalog, page)
    elif data.startswith("help_category:"):
        _, key, page = data.split(":", 2)
        try:
            previous_page = int(page)
        except ValueError:
            previous_page = 0
        await _render_category(client, query.message, catalog, key, previous_page)
    elif data.startswith("help_back:"):
        try:
            page = int(data.split(":", 1)[1])
        except ValueError:
            page = 0
        await _render_home(client, query.message, catalog, page)


def register_help_callbacks(client) -> None:
    """Daftarkan callback melalui CallbackQueryHandler eksplisit."""
    client.add_handler(CallbackQueryHandler(handle_help_callback, CALLBACK_FILTER))
