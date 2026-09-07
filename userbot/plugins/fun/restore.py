"""IBEKS USERBOT - Plugin Restore.

Command:
  .restore - pulihkan profil terakhir yang dibackup oleh .clone
"""

import asyncio
import json
import os

from pyrogram import filters
from pyrogram.errors import RPCError

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui, success as success_ui
from utils.logger import log
from plugins.fun.clone import BACKUP_METADATA_PATH, BACKUP_PHOTO_PATH
from plugins.utils.ui import send_ui


def _telegram_error(exc: Exception) -> str:
    reason = str(exc).strip()
    return reason or exc.__class__.__name__


async def _notify(client, chat_id: int, text: str) -> None:
    try:
        formatted = format_ui(
            title="RESTORE",
            body=f"📌 Status : {text}",
            emoji="♻️",
        )
        await send_ui(
            client,
            chat_id,
            formatted,
        )
    except Exception as exc:
        log.exception("[Restore] Gagal mengirim status ke chat %s: %s", chat_id, exc)


def _load_backup() -> dict | None:
    if not os.path.exists(BACKUP_METADATA_PATH):
        return None
    try:
        with open(BACKUP_METADATA_PATH, "r", encoding="utf-8") as file:
            backup = json.load(file)
        if not isinstance(backup, dict):
            raise ValueError("format backup tidak valid")
        required = ("first_name", "last_name", "bio")
        if any(key not in backup for key in required):
            raise ValueError("data backup tidak lengkap")
        return backup
    except Exception as exc:
        log.exception("[Restore] Gagal membaca backup: %s", exc)
        return None


async def _remove_current_photo(client) -> None:
    """Hapus foto profil saat backup awal memang tidak memiliki foto."""
    me = await client.get_me()
    if not me.photo:
        return
    photo_id = getattr(me.photo, "file_id", None) or me.photo.big_file_id
    await client.delete_profile_photos(photo_id)


async def restore_profile(client) -> tuple[bool, str]:
    """Jalankan restore profil dan kembalikan status untuk pemanggil UI."""
    backup = _load_backup()
    if backup is None:
        return False, "Backup profil tidak ditemukan."

    errors = []
    try:
        await client.update_profile(
            first_name=backup["first_name"],
            last_name=backup["last_name"],
            bio=backup["bio"],
        )
    except RPCError as exc:
        errors.append(f"data profil ({_telegram_error(exc)})")
        log.exception("[Restore] Telegram menolak data profil: %s", exc)
    except Exception as exc:
        errors.append(f"data profil ({_telegram_error(exc)})")
        log.exception("[Restore] Gagal memulihkan data profil: %s", exc)

    photo_file = backup.get("photo_file")
    clone_photo_id = backup.get("clone_photo_id")
    original_photo_ids = backup.get("original_photo_ids") or []

    try:
        current_photos = [p.file_id async for p in client.get_chat_photos("me")]

        if photo_file:
            # Kasus 1: Owner sebelum clone memiliki foto profil
            # Hapus foto clone yang ditambahkan saat .clone agar tidak tertinggal di riwayat
            if clone_photo_id and clone_photo_id in current_photos:
                await client.delete_profile_photos(clone_photo_id)
            elif original_photo_ids:
                to_delete = [p for p in current_photos if p not in original_photo_ids]
                if to_delete:
                    await client.delete_profile_photos(to_delete[0])
            elif len(current_photos) > 1:
                await client.delete_profile_photos(current_photos[0])

            # Pastikan foto profil aktif; jika kosong, pasang kembali dari file backup
            me = await client.get_me()
            if not me.photo:
                if not os.path.exists(BACKUP_PHOTO_PATH):
                    raise FileNotFoundError("file foto backup tidak ditemukan")
                with open(BACKUP_PHOTO_PATH, "rb") as photo:
                    await client.set_profile_photo(photo=photo)
        else:
            # Kasus 2: Owner sebelum clone tidak memiliki foto profil
            # Hapus foto clone sehingga profil kembali bersih tanpa foto
            if clone_photo_id and clone_photo_id in current_photos:
                await client.delete_profile_photos(clone_photo_id)
            elif current_photos:
                await client.delete_profile_photos(current_photos[0])

            me = await client.get_me()
            if me.photo:
                remaining = [p.file_id async for p in client.get_chat_photos("me")]
                if remaining:
                    await client.delete_profile_photos(remaining)
    except RPCError as exc:
        errors.append(f"foto ({_telegram_error(exc)})")
        log.exception("[Restore] Telegram menolak foto backup: %s", exc)
    except Exception as exc:
        errors.append(f"foto ({_telegram_error(exc)})")
        log.exception("[Restore] Gagal memulihkan foto backup: %s", exc)

    if errors:
        return False, f"Profil dipulihkan sebagian. Alasan: {'; '.join(errors)}."
    return True, ""


def setup(client):
    """Daftarkan command .restore."""

    @client.on_message(dynamic_command("restore") & filters.me)
    async def cmd_restore(client, message):
        chat_id = message.chat.id
        success, detail = await restore_profile(client)
        if not success:
            await _notify(client, chat_id, f"❌ {detail}")
            return
        success_text = success_ui(
            title="RESTORE BERHASIL",
            message="Profil berhasil dikembalikan.",
            emoji="✅",
        )
        try:
            success_message = await send_ui(client, chat_id, success_text)
        except Exception as exc:
            log.exception("[Restore] Gagal mengirim pesan sukses: %s", exc)
            success_message = None
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        if success_message is not None:
            asyncio.create_task(
                auto_delete(
                    success_message,
                    delay=AUTO_DELETE_CMD,
                    force=True,
                )
            )