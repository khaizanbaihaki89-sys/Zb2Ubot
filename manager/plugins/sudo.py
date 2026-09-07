"""
IBEKS MANAGER BOT - Plugin: Sudo Manager
Owner commands:
  .addsudo <user> / /addsudo <user>  - Tambah user ke daftar Sudo (Max 5)
  .delsudo <user> / /delsudo <user>  - Hapus user dari daftar Sudo
  .listsudo / /listsudo              - Tampilkan daftar user Sudo aktif
"""

from __future__ import annotations

from pyrogram import filters

from config import OWNER_ID
from database import (
    MAX_SUDO_USERS,
    add_sudo_user,
    count_sudo_users,
    del_sudo_user,
    list_sudo_users,
)
from formatter import display_date, display_username
from logger import log, safe_handler


def _is_owner(message_or_user) -> bool:
    """Verifikasi apakah pengirim pesan adalah Owner bot."""
    user = getattr(message_or_user, "from_user", None) or message_or_user
    user_id = getattr(user, "id", None)
    return bool(OWNER_ID and user_id == OWNER_ID)


async def _resolve_target(
    client, message
) -> tuple[int | None, str | None, str | None, str | None]:
    """
    Ekstrak target user dari reply atau argumen command.
    Return (telegram_id, username, full_name, error_message).
    """
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        name = (
            f"{target_user.first_name or ''} {target_user.last_name or ''}"
        ).strip() or target_user.username or f"User {target_user.id}"
        return target_user.id, target_user.username, name, None

    text = message.text or message.caption or ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        return None, None, None, "Format tidak lengkap. Balas (reply) pesan user atau sertakan ID / Username."

    raw_target = parts[1].strip()
    # Jika berupa numeric ID
    if raw_target.isdigit() or (raw_target.startswith("-") and raw_target[1:].isdigit()):
        target_id = int(raw_target)
        try:
            user_obj = await client.get_users(target_id)
            name = (
                f"{user_obj.first_name or ''} {user_obj.last_name or ''}"
            ).strip() or user_obj.username or f"User {user_obj.id}"
            return user_obj.id, user_obj.username, name, None
        except Exception:
            return target_id, None, f"User {target_id}", None

    # Jika berupa username (@username atau username)
    try:
        user_obj = await client.get_users(raw_target)
        name = (
            f"{user_obj.first_name or ''} {user_obj.last_name or ''}"
        ).strip() or user_obj.username or f"User {user_obj.id}"
        return user_obj.id, user_obj.username, name, None
    except Exception as exc:
        log.warning(f"[Sudo] Gagal resolve user {raw_target}: {exc}")
        return None, None, None, f"Pengguna <code>{raw_target}</code> tidak ditemukan di Telegram."


def setup(client):
    """Daftarkan handler command Sudo ke Manager Client."""

    @client.on_message(
        filters.command(["addsudo"], prefixes=[".", "/"])
    )
    @safe_handler
    async def cmd_addsudo(_client, message):
        """Handler .addsudo <user> - Hanya untuk Owner."""
        if not _is_owner(message):
            await message.reply("⛔ <b>Akses ditolak.</b> Perintah ini hanya dapat dijalankan oleh Owner bot.")
            return

        target_id, username, full_name, err = await _resolve_target(_client, message)
        if err:
            await message.reply(
                f"⚠️ {err}\n\n"
                "💡 <b>Contoh Penggunaan:</b>\n"
                "• <code>.addsudo 123456789</code>\n"
                "• <code>.addsudo @username</code>\n"
                "• Reply pesan user lalu ketik <code>.addsudo</code>"
            )
            return

        if not target_id:
            await message.reply("❌ Gagal mengidentifikasi Telegram ID user.")
            return

        success, msg, count = add_sudo_user(
            telegram_id=target_id,
            username=username,
            full_name=full_name,
            added_by=OWNER_ID,
        )
        await message.reply(msg)
        log.info(
            f"[Sudo] Add sudo target={target_id} by={OWNER_ID} success={success} total={count}"
        )

    @client.on_message(
        filters.command(["delsudo"], prefixes=[".", "/"])
    )
    @safe_handler
    async def cmd_delsudo(_client, message):
        """Handler .delsudo <user> - Hanya untuk Owner."""
        if not _is_owner(message):
            await message.reply("⛔ <b>Akses ditolak.</b> Perintah ini hanya dapat dijalankan oleh Owner bot.")
            return

        target_id, username, full_name, err = await _resolve_target(_client, message)
        if err:
            await message.reply(
                f"⚠️ {err}\n\n"
                "💡 <b>Contoh Penggunaan:</b>\n"
                "• <code>.delsudo 123456789</code>\n"
                "• <code>.delsudo @username</code>\n"
                "• Reply pesan user lalu ketik <code>.delsudo</code>"
            )
            return

        if not target_id:
            await message.reply("❌ Gagal mengidentifikasi Telegram ID user.")
            return

        success, msg, count = del_sudo_user(telegram_id=target_id)
        await message.reply(msg)
        log.info(
            f"[Sudo] Del sudo target={target_id} by={OWNER_ID} success={success} total={count}"
        )

    @client.on_message(
        filters.command(["listsudo"], prefixes=[".", "/"])
    )
    @safe_handler
    async def cmd_listsudo(_client, message):
        """Handler .listsudo - Hanya untuk Owner."""
        if not _is_owner(message):
            await message.reply("⛔ <b>Akses ditolak.</b> Perintah ini hanya dapat dijalankan oleh Owner bot.")
            return

        sudo_list = list_sudo_users()
        total = len(sudo_list)

        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"👑 <b>DAFTAR SUDO BOT ({total}/{MAX_SUDO_USERS})</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        if not sudo_list:
            lines.append("<i>Belum ada user Sudo yang terdaftar.</i>")
            lines.append(f"💡 Tambahkan dengan <code>.addsudo &lt;user&gt;</code> (Slot: 0/{MAX_SUDO_USERS})")
        else:
            for idx, user in enumerate(sudo_list, 1):
                name = user.get("full_name") or "Tidak diketahui"
                uname = display_username(user.get("username"))
                uid = user["telegram_id"]
                added_at = display_date(user.get("added_at"))
                lines.extend([
                    f"<b>{idx}. {name}</b> ({uname})",
                    f"   🆔 ID: <code>{uid}</code>",
                    f"   📅 Ditambahkan: <code>{added_at}</code>",
                    "",
                ])
            lines.append(f"📊 <b>Slot Digunakan:</b> {total}/{MAX_SUDO_USERS} (Sisa: {MAX_SUDO_USERS - total})")

        lines.extend(["", "━━━━━━━━━━━━━━━━━━━━━━"])
        await message.reply("\n".join(lines).strip())
