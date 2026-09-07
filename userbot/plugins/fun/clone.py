"""IBEKS USERBOT - Plugin Clone.

Satu-satunya command yang didaftarkan plugin ini adalah ``.clone``.
"""

import asyncio
import io
import json
import os
import tempfile
from typing import Optional

from pyrogram import filters
from pyrogram.errors import RPCError

from config import AUTO_DELETE_CMD, BASE_DIR
from utils.autodelete import auto_delete
from utils.clone_bridge import request_clone_panel
from utils.filters import dynamic_command
from utils.formatter import format_ui
from utils.logger import log
from plugins.utils.ui import send_ui


BACKUP_METADATA_PATH = os.path.join(BASE_DIR, ".clone_profile_backup.json")
BACKUP_PHOTO_PATH = os.path.join(BASE_DIR, ".clone_profile_photo.jpg")


async def _download_target_photo(client, target):
    """Unduh foto profil target ke memory, atau kembalikan None."""
    if not target.photo:
        return None

    try:
        downloaded = await client.download_media(
            target.photo.big_file_id,
            in_memory=True,
        )
        if downloaded is None:
            return None
        if isinstance(downloaded, bytes):
            return io.BytesIO(downloaded)
        if hasattr(downloaded, "getvalue"):
            return io.BytesIO(downloaded.getvalue())
        if hasattr(downloaded, "read"):
            if hasattr(downloaded, "seek"):
                downloaded.seek(0)
            return downloaded
        log.warning("[Clone] Format hasil download foto tidak didukung.")
    except Exception as exc:
        log.exception("[Clone] Gagal mengunduh foto target %s: %s", target.id, exc)
    return None


async def _get_profile_data(client):
    """Ambil data profil akun userbot yang sedang login."""
    me = await client.get_me()
    profile = await client.get_chat(me.id)
    return me, {
        "first_name": me.first_name or "",
        "last_name": me.last_name or "",
        "bio": profile.bio or "",
    }


def _write_backup(metadata: dict, photo_bytes: Optional[bytes]) -> None:
    """Simpan backup terakhir secara atomik agar tidak korup saat restart."""
    metadata_dir = os.path.dirname(BACKUP_METADATA_PATH) or BASE_DIR
    photo_dir = os.path.dirname(BACKUP_PHOTO_PATH) or BASE_DIR
    os.makedirs(metadata_dir, exist_ok=True)
    os.makedirs(photo_dir, exist_ok=True)
    photo_temp = None
    metadata_temp = None
    try:
        if photo_bytes is not None:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=photo_dir, prefix=".clone-photo-", delete=False
            ) as file:
                file.write(photo_bytes)
                photo_temp = file.name

        metadata["photo_file"] = os.path.basename(BACKUP_PHOTO_PATH) if photo_bytes else None
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=metadata_dir,
            prefix=".clone-metadata-",
            delete=False,
        ) as file:
            json.dump(metadata, file, ensure_ascii=False, indent=2)
            file.write("\n")
            metadata_temp = file.name

        if photo_temp:
            os.replace(photo_temp, BACKUP_PHOTO_PATH)
        elif os.path.exists(BACKUP_PHOTO_PATH):
            os.remove(BACKUP_PHOTO_PATH)
        os.replace(metadata_temp, BACKUP_METADATA_PATH)
    finally:
        for path in (photo_temp, metadata_temp):
            if path and os.path.exists(path):
                os.remove(path)


async def create_profile_backup(client) -> None:
    """Backup profil asli sebelum clone; gagal berarti clone dibatalkan."""
    me, profile_data = await _get_profile_data(client)
    photo_bytes = None
    if me.photo:
        photo = await _download_target_photo(client, me)
        if photo is None:
            raise RuntimeError("foto profil asli gagal diunduh")
        photo.seek(0)
        photo_bytes = photo.read()
        if not photo_bytes:
            raise RuntimeError("foto profil asli kosong")

    try:
        orig_photos = [p.file_id async for p in client.get_chat_photos("me")]
        profile_data["original_photo_ids"] = orig_photos
    except Exception as exc:
        log.warning("[Clone] Gagal mengambil daftar foto profil asli: %s", exc)
        profile_data["original_photo_ids"] = []

    profile_data["clone_photo_id"] = None
    _write_backup(profile_data, photo_bytes)
    log.info("[Clone] Backup profil asli berhasil disimpan.")


def _telegram_error(exc: Exception) -> str:
    """Ambil alasan Telegram yang cukup jelas untuk ditampilkan ke user."""
    reason = str(exc).strip()
    return reason or exc.__class__.__name__


async def _notify(client, chat_id: int, text: str) -> None:
    """Kirim status tanpa membiarkan error jaringan mematikan handler."""
    try:
        formatted = format_ui(
            title="CLONE",
            body=f"📌 Status : {text}",
            emoji="🧬",
        )
        await send_ui(
            client,
            chat_id,
            formatted,
        )
    except Exception as exc:
        log.exception("[Clone] Gagal mengirim status ke chat %s: %s", chat_id, exc)


def setup(client):
    """Daftarkan command .clone."""

    @client.on_message(dynamic_command("clone") & filters.me)
    async def cmd_clone(client, message):
        chat_id = message.chat.id

        reply = message.reply_to_message
        if not reply or not reply.from_user:
            await _notify(client, chat_id, "❌ Reply ke pengguna yang ingin di-clone.")
            return

        target = reply.from_user
        photo_status = "tidak ada"
        errors = []

        try:
            await create_profile_backup(client)
        except Exception as exc:
            log.exception("[Clone] Backup profil asli gagal: %s", exc)
            await _notify(
                client,
                chat_id,
                f"❌ Clone dibatalkan karena backup profil gagal: {_telegram_error(exc)}.",
            )
            return

        # Bio tidak tersedia di object User reply; ambil dari chat target.
        target_bio = ""
        try:
            target_chat = await client.get_chat(target.id)
            target_bio = target_chat.bio or ""
        except Exception as exc:
            log.exception("[Clone] Gagal mengambil bio target %s: %s", target.id, exc)
            errors.append(f"bio ({_telegram_error(exc)})")

        # Foto diproses terpisah agar nama dan bio tetap bisa diclone.
        target_photo = await _download_target_photo(client, target)
        if target.photo and target_photo is None:
            photo_status = "tidak dapat diunduh"
        if target_photo is not None:
            try:
                await client.set_profile_photo(photo=target_photo)
                photo_status = "berhasil"
                try:
                    current_photos = [p.file_id async for p in client.get_chat_photos("me", limit=1)]
                    if current_photos and os.path.exists(BACKUP_METADATA_PATH):
                        with open(BACKUP_METADATA_PATH, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        meta["clone_photo_id"] = current_photos[0]
                        with open(BACKUP_METADATA_PATH, "w", encoding="utf-8") as f:
                            json.dump(meta, f, ensure_ascii=False, indent=2)
                except Exception as exc:
                    log.warning("[Clone] Gagal mencatat clone_photo_id: %s", exc)
            except RPCError as exc:
                photo_status = f"gagal ({_telegram_error(exc)})"
                log.exception("[Clone] Telegram menolak foto target %s: %s", target.id, exc)
                errors.append(f"foto ({_telegram_error(exc)})")
            except Exception as exc:
                photo_status = f"gagal ({_telegram_error(exc)})"
                log.exception("[Clone] Gagal menerapkan foto target %s: %s", target.id, exc)
                errors.append(f"foto ({_telegram_error(exc)})")

        # Nama dan bio tetap dicoba walaupun foto tidak ada atau gagal.
        first_name = target.first_name or "IBEKS USERBOT"
        last_name = target.last_name or ""
        try:
            await client.update_profile(
                first_name=first_name,
                last_name=last_name,
                bio=target_bio if target_bio is not None else None,
            )
        except RPCError as exc:
            reason = _telegram_error(exc)
            errors.append(f"profil ({reason})")
            log.exception("[Clone] Telegram menolak data target %s: %s", target.id, exc)
        except Exception as exc:
            reason = _telegram_error(exc)
            errors.append(f"profil ({reason})")
            log.exception("[Clone] Gagal menerapkan data target %s: %s", target.id, exc)

        if errors:
            details = "; ".join(errors)
            await _notify(
                client,
                chat_id,
                f"⚠️ Profil berhasil diproses sebagian. Foto: {photo_status}. "
                f"Alasan: {details}.",
            )
            return

        target_name = " ".join(
            part for part in (target.first_name, target.last_name) if part
        ) or target.username or str(target.id)
        try:
            me = await client.get_me()
            request_clone_panel(
                user_id=me.id,
                target_name=target_name,
            )
        except Exception as exc:
            # Clone sudah berhasil; kegagalan IPC tidak boleh mengubah
            # profil atau mengirim balasan ke grup.
            log.exception("[Clone] Gagal mengirim panel Manager: %s", exc)
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))