"""IBEKS USERBOT - Downloader.

Commands:
  .tt <url>    - Download TikTok.
  .ig <url>    - Download Instagram Reel/Post/Video.
  .tgdl <link> - Download media dari pesan Telegram yang dapat diakses.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pyrogram import filters

from plugins.utils.ui import send_ui
from utils.formatter import error, warning
from utils.downloader import (
    DownloaderError,
    download_social,
    download_telegram_media,
    is_video_file,
)
from utils.filters import dynamic_command
from utils.logger import log


def _argument(message) -> str | None:
    text = (message.text or message.caption or "").strip()
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) == 2 and parts[1].strip() else None


async def _send_error(client, chat_id: int, error: Exception) -> None:
    if isinstance(error, DownloaderError):
        await send_ui(client, chat_id, f"❌ {error}")
        return
    log.exception("[Downloader] Kesalahan tidak terduga: %s", error)
    await send_ui(client, chat_id, "❌ Downloader gagal memproses permintaan.")


async def _send_file(client, chat_id: int, path: Path, caption: str) -> None:
    if is_video_file(path):
        await client.send_video(chat_id, str(path), caption=caption)
    else:
        await client.send_document(chat_id, str(path), caption=caption)


async def _handle_social(client, message, service: str, label: str) -> None:
    url = _argument(message)
    if not url:
        await send_ui(client, message.chat.id, f"❌ Gunakan: .{label} <url>")
        return

    temporary: tempfile.TemporaryDirectory | None = None
    try:
        path, temporary = await download_social(url, service)
        await _send_file(client, message.chat.id, path, f"✅ {service.title()} download selesai.")
    except Exception as exc:
        await _send_error(client, message.chat.id, exc)
    finally:
        if temporary is not None:
            temporary.cleanup()


async def _handle_telegram(client, message) -> None:
    url = _argument(message)
    if not url:
        await send_ui(client, message.chat.id, "❌ Gunakan: .tgdl <private_link>")
        return

    temporary = tempfile.TemporaryDirectory(prefix="ibeks_telegram_")
    try:
        path = await download_telegram_media(client, url, Path(temporary.name))
        await _send_file(client, message.chat.id, path, "✅ Telegram download selesai.")
    except Exception as exc:
        await _send_error(client, message.chat.id, exc)
    finally:
        temporary.cleanup()


def setup(client):
    """Daftarkan tiga command downloader yang didukung."""

    @client.on_message(dynamic_command("tt") & filters.me)
    async def cmd_tiktok(client, message):
        await _handle_social(client, message, "tiktok", "tt")

    @client.on_message(dynamic_command("ig") & filters.me)
    async def cmd_instagram(client, message):
        await _handle_social(client, message, "instagram", "ig")

    @client.on_message(dynamic_command("tgdl") & filters.me)
    async def cmd_telegram(client, message):
        await _handle_telegram(client, message)