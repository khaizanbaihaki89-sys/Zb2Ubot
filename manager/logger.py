"""Logging file/console dan wrapper error global Manager Bot."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from functools import wraps
from pathlib import Path
from typing import Any

from pyrogram import ContinuePropagation, StopPropagation

from config import LOGS_DIR

LOGS_PATH = Path(LOGS_DIR)
LOGS_PATH.mkdir(parents=True, exist_ok=True)
log = logging.getLogger("ibeks.manager")
log.setLevel(logging.INFO)
log.propagate = False

if not log.handlers:
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(LOGS_PATH / "manager.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    log.addHandler(file_handler)
    log.addHandler(stream_handler)


def install_global_error_handler() -> None:
    """Catat exception asyncio tanpa menghentikan event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Belum ada running loop; coba get_event_loop() sebagai fallback
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                log.warning("[Logger] Event loop sudah tertutup; skip asyncio error handler.")
                return
        except RuntimeError:
            # Tidak ada event loop sama sekali; skip registration
            log.debug("[Logger] Tidak ada event loop tersedia untuk error handler asyncio.")
            return

    def handler(loop, context):
        error = context.get("exception")
        if error:
            log.error(
                "Global asyncio error: %s",
                context.get("message"),
                exc_info=error,
            )
        else:
            log.error("Global asyncio error: %s", context.get("message"))

    try:
        loop.set_exception_handler(handler)
        log.debug("[Logger] Asyncio exception handler registered.")
    except Exception as exc:
        log.warning("[Logger] Gagal mendaftarkan asyncio error handler: %s", exc)


def safe_handler(function: Callable[..., Awaitable[Any]]):
    """Pastikan error satu handler tidak membuat bot crash."""

    @wraps(function)
    async def wrapped(client, update, *args, **kwargs):
        try:
            return await function(client, update, *args, **kwargs)
        except (ContinuePropagation, StopPropagation):
            raise
        except Exception:
            log.exception("Handler %s gagal.", function.__name__)
            try:
                if hasattr(update, "answer"):
                    await update.answer(
                        "Terjadi kesalahan. Silakan coba lagi.",
                        show_alert=True,
                    )
                elif hasattr(update, "reply"):
                    await update.reply("❌ Terjadi kesalahan. Silakan coba lagi.")
            except Exception:
                log.exception(
                    "Gagal mengirim pesan error dari handler %s.",
                    function.__name__,
                )

    return wrapped
