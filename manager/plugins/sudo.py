"""
IBEKS MANAGER BOT - Plugin: Sudo Manager
Owner commands:
  .addsudo <account_id> <user> - Tambah Sudo ke runtime account tertentu
  .delsudo <account_id> <user> - Hapus Sudo dari runtime account tertentu
  .listsudo <account_id>       - Tampilkan Sudo account tertentu
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pyrogram import filters

from config import OWNER_ID, USERBOT_RUNTIME_DIR
from formatter import display_date, display_username
from logger import log, safe_handler

MAX_SUDO_USERS = 5


def _runtime_db(account_id: int) -> Path:
    if account_id <= 0:
        raise ValueError("Account ID tidak valid.")
    runtime_dir = Path(USERBOT_RUNTIME_DIR) / str(account_id)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    db_path = runtime_dir / "database.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sudo_users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                added_by INTEGER,
                added_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
    return db_path


def _account_sudo_list(account_id: int) -> list[dict]:
    db_path = _runtime_db(account_id)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in connection.execute(
                "SELECT telegram_id, username, full_name, added_by, added_at FROM sudo_users ORDER BY added_at ASC"
            ).fetchall()
        ]


def _account_add_sudo(
    account_id: int,
    target_id: int,
    username: str | None,
    full_name: str | None,
) -> tuple[bool, str, int]:
    db_path = _runtime_db(account_id)
    current = len(_account_sudo_list(account_id))
    with sqlite3.connect(db_path) as connection:
        if connection.execute(
            "SELECT 1 FROM sudo_users WHERE telegram_id = ?", (target_id,)
        ).fetchone():
            return False, f"User `{target_id}` sudah terdaftar sebagai Sudo.", current
        if current >= MAX_SUDO_USERS:
            return False, f"Batas maksimal {MAX_SUDO_USERS} Sudo tercapai ({current}/{MAX_SUDO_USERS}).", current
        connection.execute(
            "INSERT INTO sudo_users (telegram_id, username, full_name, added_by, added_at) VALUES (?, ?, ?, ?, ?)",
            (target_id, username, full_name or "Pengguna Telegram", OWNER_ID, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
    return True, "Sudo berhasil ditambahkan.", current + 1


def _account_delete_sudo(account_id: int, target_id: int) -> tuple[bool, str, int]:
    db_path = _runtime_db(account_id)
    current = len(_account_sudo_list(account_id))
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute("DELETE FROM sudo_users WHERE telegram_id = ?", (target_id,))
        if cursor.rowcount == 0:
            return False, f"User `{target_id}` tidak ditemukan sebagai Sudo.", current
    return True, "Sudo berhasil dicabut.", current - 1


def _is_owner(message_or_user) -> bool:
    """Verifikasi apakah pengirim pesan adalah Owner bot."""
    user = getattr(message_or_user, "from_user", None) or message_or_user
    user_id = getattr(user, "id", None)
    return bool(OWNER_ID and user_id == OWNER_ID)


async def _resolve_target(
    client, message, *,
    argument_index: int = 2,
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
    parts = text.split()
    if len(parts) <= argument_index:
        return None, None, None, "Format tidak lengkap. Balas (reply) pesan user atau sertakan ID / Username."

    raw_target = parts[argument_index].strip()
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


def _parse_account_id(message) -> tuple[int | None, str | None]:
    """Account runtime selalu wajib disebut agar target tidak ambigu."""
    text = message.text or message.caption or ""
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return None, "Format wajib: <code>.<b>command</b> &lt;account_id&gt; [user]</code>."
    return int(parts[1]), None


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

        account_id, account_err = _parse_account_id(message)
        if account_err:
            await message.reply(account_err)
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

        success, msg, count = _account_add_sudo(account_id, target_id, username, full_name)
        await message.reply(msg)
        log.info(
            f"[Sudo] Add account={account_id} target={target_id} by={OWNER_ID} success={success} total={count}"
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

        account_id, account_err = _parse_account_id(message)
        if account_err:
            await message.reply(account_err)
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

        success, msg, count = _account_delete_sudo(account_id, target_id)
        await message.reply(msg)
        log.info(
            f"[Sudo] Del account={account_id} target={target_id} by={OWNER_ID} success={success} total={count}"
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

        account_id, account_err = _parse_account_id(message)
        if account_err:
            await message.reply(account_err)
            return
        sudo_list = _account_sudo_list(account_id)
        total = len(sudo_list)

        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"👑 <b>DAFTAR SUDO ACCOUNT {account_id} ({total}/{MAX_SUDO_USERS})</b>",
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
