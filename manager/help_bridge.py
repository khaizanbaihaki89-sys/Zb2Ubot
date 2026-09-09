"""Bridge .help: Userbot meminta, Manager Bot mengirim dan mengedit UI."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyrogram import filters
from pyrogram.errors import RPCError
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup

from config import DATABASE_PATH, USERBOT_RUNTIME_DIR, USERBOT_SOURCE_DIR
from logger import log

if str(USERBOT_SOURCE_DIR) not in sys.path:
    sys.path.append(str(USERBOT_SOURCE_DIR))

_BUILDER_PATH = USERBOT_SOURCE_DIR / "utils" / "help_builder.py"
_BUILDER_SPEC = importlib.util.spec_from_file_location(
    "ibeks_manager_help_builder",
    _BUILDER_PATH,
)
if _BUILDER_SPEC is None or _BUILDER_SPEC.loader is None:
    raise ImportError(f"Help builder tidak ditemukan: {_BUILDER_PATH}")
_BUILDER = importlib.util.module_from_spec(_BUILDER_SPEC)
sys.modules[_BUILDER_SPEC.name] = _BUILDER
_BUILDER_SPEC.loader.exec_module(_BUILDER)

build_category_text = _BUILDER.build_category_text
build_home_text = _BUILDER.build_home_text
category_keyboard = _BUILDER.category_keyboard
clamp_page = _BUILDER.clamp_page
home_keyboard = _BUILDER.home_keyboard
page_count = _BUILDER.page_count
scan_plugins = _BUILDER.scan_plugins
total_plugins = _BUILDER.total_plugins
get_plan = _BUILDER.get_plan

CALLBACK_FILTER = filters.regex(
    r"^(?:help_home|help_page(?::\d+)?|help_category:[^:]+:\d+|help_back(?::\d+)?)$"
)
REQUEST_POLL_INTERVAL = 0.25
PLUGIN_ROOT = USERBOT_SOURCE_DIR / "plugins"


@dataclass(frozen=True)
class HelpContext:
    user_id: int
    owner: str
    prefix: str


_contexts: dict[tuple[int, int], HelpContext] = {}
_watcher_task: asyncio.Task | None = None


def _request_paths() -> list[Path]:
    if not USERBOT_RUNTIME_DIR.exists():
        return []
    return sorted(USERBOT_RUNTIME_DIR.glob("*/.help_request.json"))


def _read_request(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "chat_id": int(payload["chat_id"]),
            "user_id": int(payload["user_id"]),
            "owner": str(payload.get("owner") or payload["user_id"]),
            "prefix": str(payload.get("prefix") or "."),
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("[Help] Request invalid dari %s: %s.", path, exc)
        return None


def _is_valid_user_id(chat_id: int | str) -> bool:
    """
    Validasi bahwa chat_id adalah user ID pribadi (positif).
    Chat ID grup/supergroup adalah negatif dan tidak dapat menerima pesan via send_message
    ketika Pyrogram menggunakan in_memory=True (tidak ada persistent storage).
    
    Return: True jika chat_id valid untuk send_message, False jika grup/supergroup.
    """
    try:
        cid = int(chat_id)
        # User ID pribadi adalah positif; group/supergroup adalah negatif
        if cid <= 0:
            return False
        return True
    except (ValueError, TypeError):
        return False


def _home_payload(context: HelpContext, page: int):
    catalog = scan_plugins(PLUGIN_ROOT)
    page = clamp_page(catalog, page)
    text = build_home_text(
        plan=get_plan(context.user_id, DATABASE_PATH),
        prefix=context.prefix,
        plugins=total_plugins(catalog),
        owner=context.owner,
        page=page,
        pages=page_count(catalog),
    )
    return catalog, text, home_keyboard(catalog, page), page


async def _edit_help(
    client,
    message,
    text: Any,
    markup: InlineKeyboardMarkup,
) -> None:
    entities = getattr(text, "entities", None)
    plain_text = getattr(text, "text", str(text))
    try:
        if entities:
            await client.edit_message_text(
                message.chat.id,
                message.id,
                plain_text,
                entities=entities,
                reply_markup=markup,
            )
        else:
            await client.edit_message_text(
                message.chat.id,
                message.id,
                plain_text,
                reply_markup=markup,
            )
    except RPCError:
        try:
            await client.edit_message_reply_markup(
                message.chat.id,
                message.id,
                reply_markup=markup,
            )
        except Exception:
            pass


async def _send_help(client, payload: dict) -> bool:
    bot = await client.get_me()
    chat_id = payload["chat_id"]
    
    # PATCH: Validasi chat_id adalah user ID pribadi (positif)
    if not _is_valid_user_id(chat_id):
        log.warning(
            "[Help] Request tidak dapat dikirim: chat_id=%s bukan user ID pribadi "
            "(mungkin grup/supergroup dengan ID negatif). Fallback ke user_id=%s.",
            chat_id,
            payload["user_id"],
        )
        chat_id = payload["user_id"]
        # Double-check fallback juga valid
        if not _is_valid_user_id(chat_id):
            log.warning(
                "[Help] Fallback user_id=%s juga tidak valid. Request dibatalkan.",
                chat_id,
            )
            return False
    
    if int(chat_id) == int(bot.id):
        # Telegram tidak mengizinkan bot mengirim pesan ke dirinya sendiri.
        # Ini terjadi jika Userbot menjalankan .help di private chat Manager.
        # Kirim ke akun Userbot peminta agar command tetap menghasilkan UI.
        fallback_chat_id = payload["user_id"]
        if int(fallback_chat_id) == int(bot.id):
            log.warning(
                "[Help] Request tidak dapat dikirim: chat_id dan user_id "
                "sama-sama akun BOT_TOKEN (%s).",
                bot.id,
            )
            return False
        log.warning(
            "[Help] chat_id=%s adalah akun BOT_TOKEN sendiri; "
            "menggunakan fallback user_id=%s.",
            chat_id,
            fallback_chat_id,
        )
        chat_id = fallback_chat_id

    context = HelpContext(
        user_id=payload["user_id"],
        owner=payload["owner"],
        prefix=payload["prefix"],
    )
    catalog, text, markup, _page = _home_payload(context, 0)
    if not isinstance(markup, InlineKeyboardMarkup):
        raise TypeError("Help home harus menghasilkan InlineKeyboardMarkup")

    entities = getattr(text, "entities", None)
    plain_text = getattr(text, "text", str(text))

    if entities:
        message = await client.send_message(
            chat_id,
            plain_text,
            entities=entities,
            reply_markup=markup,
        )
    else:
        message = await client.send_message(
            chat_id,
            plain_text,
            reply_markup=markup,
        )
    _contexts[(message.chat.id, message.id)] = context
    log.info(
        "[Help] UI terkirim via BOT_TOKEN chat_id=%s message_id=%s categories=%s.",
        message.chat.id,
        message.id,
        len(catalog),
    )
    if len(_contexts) > 1000:
        for key in list(_contexts)[:200]:
            _contexts.pop(key, None)
    return True


async def _watch_requests(client) -> None:
    while True:
        try:
            # start_help_bridge() dipasang sebelum client.run(). Jangan
            # mengonsumsi request ketika session Bot belum siap; request harus
            # tetap menunggu sampai BOT_TOKEN benar-benar connected.
            if not client.is_connected:
                await asyncio.sleep(REQUEST_POLL_INTERVAL)
                continue
            for path in _request_paths():
                payload = _read_request(path)
                if payload is None:
                    path.unlink(missing_ok=True)
                    continue
                try:
                    await _send_help(client, payload)
                except Exception:
                    log.exception("[Help] Gagal memproses request %s.", path)
                finally:
                    # Consume each request once; never spin on a bad Telegram target.
                    path.unlink(missing_ok=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[Help] Watcher Help gagal; polling tetap berjalan.")
        await asyncio.sleep(REQUEST_POLL_INTERVAL)


async def _handle_callback(client, query) -> None:
    try:
        await query.answer()
        message = query.message
        if not message:
            return
        context = _contexts.get((message.chat.id, message.id))
        if context is None:
            await query.answer(
                "Help sudah kedaluwarsa. Jalankan .help lagi.",
                show_alert=True,
            )
            return

        data = query.data or ""
        if isinstance(data, bytes):
            data = data.decode(errors="ignore")
        catalog = scan_plugins(PLUGIN_ROOT)

        if data == "help_home":
            _catalog, text, markup, _page = _home_payload(context, 0)
        elif data.startswith("help_page:"):
            try:
                page = int(data.split(":", 1)[1])
            except ValueError:
                page = 0
            _catalog, text, markup, _page = _home_payload(context, page)
        elif data.startswith("help_category:"):
            _, key, raw_page = data.split(":", 2)
            try:
                previous_page = int(raw_page)
            except ValueError:
                previous_page = 0
            category = catalog.get(key)
            if category is None:
                _catalog, text, markup, _page = _home_payload(
                    context,
                    previous_page,
                )
            else:
                text = build_category_text(
                    category=category,
                    plan=get_plan(context.user_id, DATABASE_PATH),
                    prefix=context.prefix,
                    plugins=total_plugins(catalog),
                    owner=context.owner,
                )
                markup = category_keyboard(previous_page)
        elif data.startswith("help_back:"):
            try:
                page = int(data.split(":", 1)[1])
            except ValueError:
                page = 0
            _catalog, text, markup, _page = _home_payload(context, page)
        else:
            return

        await _edit_help(client, message, text, markup)
        log.info("[Help] Callback %s message_id=%s.", data, message.id)
    except Exception:
        log.exception("[Help] Callback Help gagal diproses.")
        try:
            await query.answer("Help gagal diperbarui.", show_alert=True)
        except Exception:
            pass


def start_help_bridge(client) -> None:
    """Daftarkan callback Manager dan mulai watcher IPC."""
    global _watcher_task
    client.add_handler(CallbackQueryHandler(_handle_callback, CALLBACK_FILTER))
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = client.loop.create_task(_watch_requests(client))
    log.info("[Help] Bridge BOT_TOKEN aktif; callback dan watcher siap.")
