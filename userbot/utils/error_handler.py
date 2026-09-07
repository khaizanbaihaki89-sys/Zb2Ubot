"""
IBEKS USERBOT - Global Error Handler
Menangkap error tak terduga secara global, mencatatnya ke log file,
dan mencegah bot crash akibat error plugin.

Pyrogram sendiri sudah menangkap error di handler plugin sehingga bot
 tidak crash. Error handler di sini menangkap error di luar handler
(uncaught exception) dan memastikan log tetap tersimpan di file.
"""

import asyncio
import inspect
import os
import sys
import traceback
from datetime import datetime

import pyrogram

from config import LOGS_DIR
from utils.logger import log


def _command_name(update) -> str:
    """Ambil token command dari Message atau kembalikan penanda umum."""
    text = getattr(update, "text", None) or getattr(update, "caption", None) or ""
    return text.strip().split(maxsplit=1)[0] if text.strip() else "unknown"


def record_plugin_error(plugin_name: str, update, exc: BaseException) -> None:
    """Catat error plugin dengan metadata yang mudah dicari di logs/."""
    now = datetime.now().astimezone()
    detail = str(exc).strip() or repr(exc)
    traceback_text = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    ).rstrip()
    entry = (
        f"Tanggal: {now.strftime('%Y-%m-%d')}\n"
        f"Waktu: {now.strftime('%H:%M:%S %z')}\n"
        f"Nama Plugin: {plugin_name}\n"
        f"Nama Command: {_command_name(update)}\n"
        f"Jenis Error: {type(exc).__name__}\n"
        f"Detail Error: {detail}\n"
        f"Traceback:\n{traceback_text}\n"
        f"{'-' * 72}\n"
    )
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(
            os.path.join(LOGS_DIR, "plugin_errors.log"),
            "a",
            encoding="utf-8",
        ) as error_log:
            error_log.write(entry)
    except Exception:
        # Logging error tidak boleh menjadi sumber crash baru.
        log.exception("[GlobalError] Gagal menulis plugin_errors.log.")
    log.error(
        "[PluginError] plugin=%s command=%s type=%s detail=%s",
        plugin_name,
        _command_name(update),
        type(exc).__name__,
        detail,
    )


async def _safe_async_callback(callback, client, update) -> None:
    """Jalankan callback plugin dan isolasi exception-nya."""
    try:
        await callback(client, update)
    except (pyrogram.StopPropagation, pyrogram.ContinuePropagation):
        raise
    except Exception as exc:
        record_plugin_error(callback.__module__, update, exc)


def _safe_sync_callback(callback, client, update) -> None:
    """Versi sinkron untuk callback non-async."""
    try:
        callback(client, update)
    except (pyrogram.StopPropagation, pyrogram.ContinuePropagation):
        raise
    except Exception as exc:
        record_plugin_error(callback.__module__, update, exc)


def _wrap_handler(handler) -> None:
    """Wrap callback plugin sekali tanpa mengubah handler atau loader."""
    callback = getattr(handler, "callback", None)
    if callback is None or getattr(callback, "_ibeks_error_wrapped", False):
        return

    if inspect.iscoroutinefunction(callback):
        async def wrapped(client, update):
            await _safe_async_callback(callback, client, update)
    else:
        def wrapped(client, update):
            _safe_sync_callback(callback, client, update)

    wrapped.__name__ = getattr(callback, "__name__", "plugin_callback")
    wrapped.__module__ = getattr(callback, "__module__", "unknown")
    wrapped._ibeks_error_wrapped = True
    handler.callback = wrapped


def install_client_error_handler(client) -> None:
    """Isolasi exception callback untuk semua handler yang didaftarkan client."""
    dispatcher = client.dispatcher
    for handlers in dispatcher.groups.values():
        for handler in handlers:
            _wrap_handler(handler)

    original_add_handler = client.add_handler
    if getattr(original_add_handler, "_ibeks_error_patch", False):
        return

    def add_handler(handler, group=0):
        _wrap_handler(handler)
        return original_add_handler(handler, group)

    add_handler._ibeks_error_patch = True
    client.add_handler = add_handler


def _handle_exception(exc_type, exc_value, exc_traceback) -> None:
    """Hook sys.excepthook untuk menangkap exception tak tertangani."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log.exception(f"[GlobalError] Uncaught exception: {exc_value}\n{tb}")


def _handle_async_exception(loop, context) -> None:
    """Hook asyncio exception handler untuk menangkap error di event loop."""
    message = context.get("message", "Unknown async error")
    exception = context.get("exception")
    if exception:
        tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
        log.exception(f"[GlobalError] Async error: {message}\n{''.join(tb)}")
    else:
        log.error(f"[GlobalError] Async error: {message}")


def install_global_error_handler() -> None:
    """Pasang hook global untuk menangkap error dan mencatatnya ke log."""
    sys.excepthook = _handle_exception

    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(_handle_async_exception)
    except RuntimeError:
        # Belum ada loop yang running; biarkan Pyrogram mengatur loop-nya nanti
        pass
