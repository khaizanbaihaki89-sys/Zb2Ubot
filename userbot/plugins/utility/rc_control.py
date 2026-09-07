"""
IBEKS USERBOT - Plugin: rc_control
Nama File: rc_control.py
Fungsi: Room Chat Control (PM Control) - Mengatur siapa yang boleh mengirim chat pribadi ke Owner.

Commands:
- .rc buka    : Mengizinkan semua orang mengirim PM ke Owner.
- .rc kontak  : Hanya kontak Owner yang boleh mengirim PM. Non-kontak ditolak & pesan dihapus.
- .rc tutup   : Semua PM dari orang lain ditolak & pesan dihapus.
- .rcset <msg>: Mengganti pesan notifikasi penolakan yang diterima pengirim.
"""

from __future__ import annotations

import asyncio
import time
from pyrogram import StopPropagation, filters

from config import AUTO_DELETE_CMD, MANAGER_BOT_ID, OWNER_ID as LEGACY_OWNER_ID
from db import (
    get_rc_settings,
    migrate_rc_settings,
    set_rc_message,
    set_rc_mode,
)
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error, format_ui, success, warning
from plugins.utils.ui import send_ui

DEFAULT_RC_REJECT_MESSAGE = (
    "Maaf, saat ini pemilik akun tidak menerima pesan pribadi (Room Chat ditutup). "
    "Silakan hubungi melalui grup."
)

# Debounce kirim notifikasi penolakan per chat_id agar tidak spam jika lawan chat kirim banyak pesan cepat
_cooldown_notified: dict[int, float] = {}
_COOLDOWN_SECONDS = 20.0
_contacts_cache: dict[int, tuple[float, frozenset[int]]] = {}
_CONTACTS_CACHE_SECONDS = 15.0


def _active_account_id(client, message=None) -> int:
    """Ambil ID akun Userbot yang sedang menjalankan handler ini."""
    me = getattr(client, "me", None)
    account_id = getattr(me, "id", 0)
    if account_id:
        return int(account_id)

    # Fallback hanya untuk test/client yang belum mengisi ``client.me``.
    from_user = getattr(message, "from_user", None)
    if from_user and getattr(from_user, "is_self", False) and getattr(from_user, "id", 0):
        return int(from_user.id)
    return 0


async def _get_active_account_contact_ids(client) -> frozenset[int] | None:
    """Ambil ID kontak dari address book akun Userbot aktif.

    ``None`` berarti Telegram gagal dibaca. Pada mode ``kontak`` kondisi ini
    diperlakukan sebagai bukan kontak agar gate tidak terbuka tanpa verifikasi.
    """
    me = getattr(client, "me", None)
    account_id = getattr(me, "id", None)
    cache_key = int(account_id) if account_id else id(client)
    now = time.monotonic()
    cached = _contacts_cache.get(cache_key)
    if cached and now - cached[0] < _CONTACTS_CACHE_SECONDS:
        return cached[1]

    try:
        contacts = await client.get_contacts()
        contact_ids = frozenset(
            int(contact.id)
            for contact in (contacts or [])
            if getattr(contact, "id", None)
        )
    except Exception:
        _contacts_cache.pop(cache_key, None)
        return None

    _contacts_cache[cache_key] = (now, contact_ids)
    return contact_ids


async def _is_active_account_contact(client, sender_id: int) -> bool:
    """Cek kontak berdasarkan address book akun yang sedang aktif."""
    contact_ids = await _get_active_account_contact_ids(client)
    return contact_ids is not None and int(sender_id) in contact_ids


def _prepare_rc_account(account_id: int) -> None:
    """Pulihkan state RC lama ke akun aktif tanpa menimpa state baru."""
    if LEGACY_OWNER_ID and LEGACY_OWNER_ID != account_id:
        migrate_rc_settings(LEGACY_OWNER_ID, account_id)


def _is_private_chat(client, message) -> bool:
    """
    Scope RC Control Command:
    - Private chat (PM dengan lawan bicara atau Saved Messages) -> True
    - Group / Channel (chat_id < 0) -> False
    """
    chat = getattr(message, "chat", None)
    if not chat:
        return False

    # ID chat negatif di Telegram adalah Group, Supergroup, atau Channel
    if chat.id < 0:
        return False

    chat_type_str = str(getattr(chat, "type", "")).lower()
    if "group" in chat_type_str or "channel" in chat_type_str:
        return False

    return True


def setup(client):
    """Daftarkan handler RC Control pada instance client."""

    # =====================================================
    # 1. INCOMING PM GATE (Group -99)
    # Filter dan cegah PM yang tidak diizinkan masuk ke inbox Owner
    # HANYA memproses incoming PM dari user lain (bukan Owner/Saved Messages/Group)
    # =====================================================
    @client.on_message(filters.incoming & filters.private, group=-99)
    async def rc_incoming_gate(client, message):
        # Abaikan jika pesan keluar / outgoing
        if getattr(message, "outgoing", False):
            return

        # Abaikan jika pesan dari diri sendiri
        if not message.from_user or getattr(message.from_user, "is_self", False):
            return

        sender_id = message.from_user.id
        my_id = _active_account_id(client, message)
        if not my_id:
            return

        # Abaikan jika pengirim adalah Owner sendiri
        if sender_id == my_id:
            return

        # Pastikan chat valid, bukan group/channel/supergroup (ID < 0)
        chat = getattr(message, "chat", None)
        if not chat or chat.id < 0:
            return

        chat_type_str = str(getattr(chat, "type", "")).lower()
        if "group" in chat_type_str or "channel" in chat_type_str:
            return

        # Abaikan jika chat adalah Saved Messages (chat ke akun sendiri / Owner)
        if chat.id == my_id:
            return

        # Pastikan strictly 1-on-1 incoming private chat dari user lain
        if chat.id != sender_id:
            return

        # Jangan tolak Telegram Service Notifications / OTP Telegram resmi / Support bot
        if sender_id in (777000, 42777) or getattr(message.from_user, "is_support", False):
            return

        # Abaikan pesan dari Manager Bot (misal UI Panel, Help, Notifikasi sistem)
        if MANAGER_BOT_ID and sender_id == MANAGER_BOT_ID:
            return

        _prepare_rc_account(my_id)

        # Ambil status mode RC saat ini
        rc_cfg = get_rc_settings(my_id)
        mode = rc_cfg.get("mode", "buka")

        # Mode Buka: izinkan semua PM
        if mode == "buka":
            return

        chat_id = message.chat.id

        # Mode Kontak: izinkan jika sender adalah kontak akun aktif
        if mode == "kontak":
            # 1. Fast-path: jika metadata pesan dari Telegram sudah menandai kontak
            if getattr(message.from_user, "is_contact", False) is True:
                return
            # 2. Verifikasi mendalam ke address book akun Telegram aktif
            if await _is_active_account_contact(client, sender_id):
                return

        # Mode Tutup atau Mode Kontak (Non-Kontak): TOLAK PESAN
        # 1. Hapus pesan asli dari sisi Owner agar tidak sampai/terlihat di inbox Owner
        try:
            await client.delete_messages(chat_id, message.id, revoke=False)
        except Exception:
            pass

        # 2. Kirim pesan penolakan ke pengirim (dengan debounce cooldown)
        now = time.time()
        last_sent = _cooldown_notified.get(chat_id, 0.0)
        if now - last_sent >= _COOLDOWN_SECONDS:
            _cooldown_notified[chat_id] = now
            reject_text = rc_cfg.get("reject_message") or DEFAULT_RC_REJECT_MESSAGE
            try:
                await client.send_message(chat_id, reject_text)
            except Exception:
                pass

        # 3. Hentikan propagasi agar tidak diproses oleh plugin/handler lain
        raise StopPropagation

    # =====================================================
    # 2. COMMAND .rc <buka|kontak|tutup>
    # =====================================================
    @client.on_message(dynamic_command("rc") & filters.me)
    async def cmd_rc(client, message):
        """Handler command .rc <buka|kontak|tutup>"""
        if not _is_private_chat(client, message):
            return

        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        effective_owner_id = _active_account_id(client, message)
        if not effective_owner_id:
            return
        _prepare_rc_account(effective_owner_id)
        chat_id = message.chat.id
        text = (message.text or message.caption or "").strip()

        parts = text.split(maxsplit=1)
        subcmd = parts[1].lower().strip() if len(parts) > 1 else ""

        if subcmd == "buka":
            set_rc_mode(effective_owner_id, "buka")
            await send_ui(
                client,
                chat_id,
                success(
                    "RC CONTROL",
                    "RC berhasil dibuka.",
                ),
            )
        elif subcmd == "kontak":
            set_rc_mode(effective_owner_id, "kontak")
            await send_ui(
                client,
                chat_id,
                success(
                    "RC CONTROL",
                    "RC mode kontak berhasil diaktifkan.",
                ),
            )
        elif subcmd == "tutup":
            set_rc_mode(effective_owner_id, "tutup")
            await send_ui(
                client,
                chat_id,
                success(
                    "RC CONTROL",
                    "RC berhasil ditutup.",
                ),
            )
        else:
            await send_ui(
                client,
                chat_id,
                warning(
                    "RC CONTROL",
                    [
                        "📝 Format : <code>.rc &lt;buka|kontak|tutup&gt;</code>",
                        "• <code>.rc buka</code> - Buka semua PM",
                        "• <code>.rc kontak</code> - Hanya kontak",
                        "• <code>.rc tutup</code> - Tutup semua PM",
                        "• <code>.rcset &lt;pesan&gt;</code> - Set pesan penolakan",
                    ],
                ),
            )

    # =====================================================
    # 3. COMMAND .rcset <pesan>
    # =====================================================
    @client.on_message(dynamic_command("rcset") & filters.me)
    async def cmd_rcset(client, message):
        """Handler command .rcset <pesan>"""
        if not _is_private_chat(client, message):
            return

        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        effective_owner_id = _active_account_id(client, message)
        if not effective_owner_id:
            return
        _prepare_rc_account(effective_owner_id)
        chat_id = message.chat.id
        text = (message.text or message.caption or "").strip()

        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await send_ui(
                client,
                chat_id,
                warning(
                    "RC CONTROL",
                    "📝 Format : <code>.rcset &lt;pesan&gt;</code>\nContoh : <code>.rcset Maaf sedang sibuk, hubungi di grup.</code>",
                ),
            )
            return

        new_msg = parts[1].strip()
        set_rc_message(effective_owner_id, new_msg)

        # Sesuai instruksi: Owner mendapat notifikasi singkat "Pesan RC berhasil diperbarui."
        await send_ui(
            client,
            chat_id,
            success("RC CONTROL", "Pesan RC berhasil diperbarui."),
        )
