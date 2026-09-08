"""Akses SQLite untuk pengguna dan hasil login Telegram."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DATABASE_PATH, OWNER_ID, USERBOT_RUNTIME_DIR, USERBOT_SOURCE_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _in_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(
        timespec="seconds"
    )


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(Path(DATABASE_PATH))
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Buat tabel users dan migrasikan kolom login tanpa menghapus data lama."""
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Belum Aktif',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                phone_number TEXT,
                session_string TEXT,
                login_at TEXT,
                approval_status TEXT NOT NULL DEFAULT 'pending',
                approved_by INTEGER,
                approved_at TEXT,
                userbot_status TEXT NOT NULL DEFAULT 'Offline',
                last_started TEXT,
                last_stopped TEXT,
                plan TEXT NOT NULL DEFAULT 'FREE',
                expired_at TEXT,
                remaining_days INTEGER NOT NULL DEFAULT 0,
                last_renew TEXT,
                last_check TEXT
            );

            """
        )
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        for column, definition in (
            ("phone_number", "TEXT"),
            ("session_string", "TEXT"),
            ("login_at", "TEXT"),
            ("approval_status", "TEXT NOT NULL DEFAULT 'pending'"),
            ("approved_by", "INTEGER"),
            ("approved_at", "TEXT"),
            ("userbot_status", "TEXT NOT NULL DEFAULT 'Offline'"),
            ("last_started", "TEXT"),
            ("last_stopped", "TEXT"),
            ("plan", "TEXT NOT NULL DEFAULT 'FREE'"),
            ("expired_at", "TEXT"),
            ("remaining_days", "INTEGER NOT NULL DEFAULT 0"),
            ("last_renew", "TEXT"),
            ("last_check", "TEXT"),
        ):
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {definition}"
                )
        connection.execute(
            "UPDATE users SET plan = 'FREE' WHERE (plan IS NULL OR plan = '') AND (telegram_id != ? OR ? = 0)",
            (OWNER_ID or 0, OWNER_ID or 0),
        )
        if OWNER_ID:
            connection.execute(
                "UPDATE users SET plan = 'PREMIUM' WHERE telegram_id = ?",
                (OWNER_ID,),
            )
        connection.execute(
            """
            UPDATE users
            SET expired_at = ?,
                remaining_days = 30,
                last_renew = ?,
                status = 'Active'
            WHERE approval_status = 'approved'
              AND session_string IS NOT NULL
              AND expired_at IS NULL
              AND COALESCE(remaining_days, 0) = 0
            """,
            (_in_days(30), _now()),
        )
        connection.commit()


def get_user(telegram_id: int) -> dict | None:
    """Ambil satu pengguna berdasarkan Telegram ID."""
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT telegram_id, username, full_name, status, created_at, updated_at,
                   phone_number, session_string, login_at, approval_status,
                    approved_by, approved_at, userbot_status, last_started,
                    last_stopped, plan, expired_at, remaining_days, last_renew,
                    last_check
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        ).fetchone()
    return dict(row) if row else None


def get_or_create_user(
    telegram_id: int,
    username: str | None,
    full_name: str,
) -> dict:
    """Buat user pertama kali atau segarkan profilnya."""
    timestamp = _now()
    is_owner = bool(OWNER_ID and telegram_id == OWNER_ID)
    default_plan = "PREMIUM" if is_owner else "FREE"
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO users (
                telegram_id, username, full_name, status, plan, created_at, updated_at
            )
            VALUES (?, ?, ?, 'Belum Aktif', ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                plan = CASE WHEN telegram_id = ? THEN 'PREMIUM' ELSE users.plan END,
                updated_at = excluded.updated_at
            """,
            (
                telegram_id,
                username,
                full_name or "Pengguna Telegram",
                default_plan,
                timestamp,
                timestamp,
                OWNER_ID or -1,
            ),
        )
        connection.commit()
    return get_user(telegram_id) or {}


def mark_login_pending(telegram_id: int, phone_number: str) -> None:
    """Tandai percobaan login aktif tanpa menyimpan OTP atau password."""
    timestamp = _now()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE users
            SET phone_number = ?,
                status = 'Pending',
                session_string = NULL,
                login_at = NULL,
                approval_status = 'pending',
                approved_by = NULL,
                approved_at = NULL,
                userbot_status = 'Offline',
                updated_at = ?
            WHERE telegram_id = ?
            """,
            (phone_number, timestamp, telegram_id),
        )
        connection.commit()


def save_login_success(
    telegram_id: int,
    phone_number: str,
    session_string: str,
    *,
    approval_status: str = "pending",
    approved_by: int | None = None,
) -> None:
    """Simpan session hanya setelah akun Telegram berhasil login."""
    timestamp = _now()
    approved_at = timestamp if approval_status == "approved" else None
    is_owner = bool(OWNER_ID and telegram_id == OWNER_ID)
    with _connect() as connection:
        connection.execute(
            """
            UPDATE users
            SET phone_number = ?,
                session_string = ?,
                login_at = ?,
                status = 'Active',
                approval_status = ?,
                approved_by = ?,
                approved_at = ?,
                userbot_status = 'Offline',
                plan = CASE WHEN ? = 1 THEN 'PREMIUM' ELSE COALESCE(plan, 'FREE') END,
                updated_at = ?
            WHERE telegram_id = ?
            """,
            (
                phone_number,
                session_string,
                timestamp,
                approval_status,
                approved_by,
                approved_at,
                1 if is_owner else 0,
                timestamp,
                telegram_id,
            ),
        )
        connection.commit()


def mark_login_failed(telegram_id: int) -> None:
    """Kembalikan status ke Pending setelah percobaan login gagal."""
    timestamp = _now()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE users
            SET status = 'Pending', updated_at = ?
            WHERE telegram_id = ?
            """,
            (timestamp, telegram_id),
        )
        connection.commit()


def approve_user(telegram_id: int, owner_id: int) -> dict | None:
    """Setujui user yang masih menunggu persetujuan."""
    timestamp = _now()
    is_owner = bool(OWNER_ID and telegram_id == OWNER_ID)
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET approval_status = 'approved',
                approved_by = ?,
                approved_at = ?,
                plan = CASE WHEN ? = 1 THEN 'PREMIUM' ELSE COALESCE(plan, 'FREE') END,
                expired_at = COALESCE(expired_at, ?),
                remaining_days = CASE
                    WHEN expired_at IS NULL THEN 30
                    ELSE remaining_days
                END,
                last_renew = CASE
                    WHEN expired_at IS NULL THEN ?
                    ELSE last_renew
                END,
                status = CASE
                    WHEN expired_at IS NULL THEN 'Active'
                    ELSE status
                END,
                updated_at = ?
            WHERE telegram_id = ? AND approval_status = 'pending'
            """,
            (owner_id, timestamp, 1 if is_owner else 0, _in_days(30), timestamp, timestamp, telegram_id),
        )
        connection.commit()
        if cursor.rowcount != 1:
            return None
    return get_user(telegram_id)


def reject_user(telegram_id: int) -> dict | None:
    """Tolak user dan hapus session Telegram yang tersimpan."""
    timestamp = _now()
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET approval_status = 'rejected',
                session_string = NULL,
                userbot_status = 'Offline',
                updated_at = ?
            WHERE telegram_id = ? AND approval_status = 'pending'
            """,
            (timestamp, telegram_id),
        )
        connection.commit()
        if cursor.rowcount != 1:
            return None
    return get_user(telegram_id)


def list_users() -> list[dict]:
    """Ambil semua user untuk rekonsiliasi lifecycle Userbot."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT telegram_id, username, full_name, status, created_at, updated_at,
                   phone_number, session_string, login_at, approval_status,
                    approved_by, approved_at, userbot_status, last_started,
                    last_stopped, plan, expired_at, remaining_days, last_renew,
                    last_check
            FROM users
            ORDER BY telegram_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def set_userbot_status(
    telegram_id: int,
    userbot_status: str,
    *,
    started: bool = False,
    stopped: bool = False,
) -> None:
    """Simpan status runtime Userbot tanpa mengubah status akses user."""
    timestamp = _now()
    assignments = ["userbot_status = ?", "updated_at = ?"]
    values: list[object] = [userbot_status, timestamp]
    if started:
        assignments.append("last_started = ?")
        values.append(timestamp)
    if stopped:
        assignments.append("last_stopped = ?")
        values.append(timestamp)
    values.append(telegram_id)
    with _connect() as connection:
        connection.execute(
            f"UPDATE users SET {', '.join(assignments)} WHERE telegram_id = ?",
            values,
        )
        connection.commit()


def set_user_status(telegram_id: int, status: str) -> dict | None:
    """Perbarui status akses user untuk operasi Admin Panel."""
    timestamp = _now()
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET status = ?, updated_at = ?
            WHERE telegram_id = ?
            """,
            (status, timestamp, telegram_id),
        )
        connection.commit()
        if cursor.rowcount != 1:
            return None
    return get_user(telegram_id)


def delete_user(telegram_id: int) -> bool:
    """Hapus row user beserta STRING_SESSION dari SQLite."""
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        connection.commit()
    return cursor.rowcount == 1


def update_subscription_state(
    telegram_id: int,
    *,
    status: str | None = None,
    remaining_days: int | None = None,
    last_check: str | None = None,
) -> dict | None:
    """Simpan hasil pemeriksaan subscription tanpa menyentuh session/approval."""
    assignments = ["updated_at = ?"]
    values: list[object] = [_now()]
    if status is not None:
        assignments.append("status = ?")
        values.append(status)
    if remaining_days is not None:
        assignments.append("remaining_days = ?")
        values.append(remaining_days)
    if last_check is not None:
        assignments.append("last_check = ?")
        values.append(last_check)
    values.append(telegram_id)
    with _connect() as connection:
        cursor = connection.execute(
            f"UPDATE users SET {', '.join(assignments)} WHERE telegram_id = ?",
            values,
        )
        connection.commit()
        if cursor.rowcount != 1:
            return None
    return get_user(telegram_id)


def renew_subscription(telegram_id: int, days: int | None) -> dict | None:
    """Perpanjang dari expiry aktif atau dari waktu sekarang; None = lifetime."""
    now = datetime.now(timezone.utc)
    with _connect() as connection:
        row = connection.execute(
            "SELECT expired_at FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        if not row:
            return None
        if days is None:
            expired_at = None
            remaining = -1
        else:
            current_expiry = None
            if row["expired_at"]:
                try:
                    current_expiry = datetime.fromisoformat(row["expired_at"])
                    if current_expiry.tzinfo is None:
                        current_expiry = current_expiry.replace(tzinfo=timezone.utc)
                except ValueError:
                    current_expiry = None
            base = max(current_expiry or now, now)
            new_expiry = base + timedelta(days=days)
            expired_at = new_expiry.isoformat(timespec="seconds")
            remaining = max(
                0,
                int(
                    (
                        new_expiry - now
                    ).total_seconds()
                    + 86399
                )
                // 86400,
            )
        timestamp = _now()
        connection.execute(
            """
            UPDATE users
            SET expired_at = ?,
                remaining_days = ?,
                last_renew = ?,
                status = 'Active',
                updated_at = ?
            WHERE telegram_id = ?
            """,
            (expired_at, remaining, timestamp, timestamp, telegram_id),
        )
        connection.commit()
    return get_user(telegram_id)


def change_plan(telegram_id: int, plan: str) -> dict | None:
    """Ubah plan saja; expiry dan session tetap dipertahankan."""
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE users SET plan = ?, updated_at = ?
            WHERE telegram_id = ?
            """,
            (plan, _now(), telegram_id),
        )
        connection.commit()
        if cursor.rowcount != 1:
            return None
    return get_user(telegram_id)


def get_ai_chat_states() -> list[dict]:
    """Mengambil daftar seluruh chat yang memiliki pengaturan status AI."""
    results: list[dict] = []
    seen_chat_ids: set[int] = set()

    candidate_paths = [
        USERBOT_SOURCE_DIR / "database.db",
        Path(DATABASE_PATH),
    ]

    if USERBOT_RUNTIME_DIR.exists():
        for sub_db in USERBOT_RUNTIME_DIR.glob("*/database.db"):
            candidate_paths.append(sub_db)

    for p in candidate_paths:
        if not p.exists():
            continue
        try:
            with sqlite3.connect(p) as conn:
                conn.row_factory = sqlite3.Row
                has_table = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_chat_settings'"
                ).fetchone()
                if has_table:
                    rows = conn.execute(
                        "SELECT * FROM ai_chat_settings ORDER BY updated_at DESC"
                    ).fetchall()
                    for r in rows:
                        cid = int(r["chat_id"])
                        if cid not in seen_chat_ids:
                            seen_chat_ids.add(cid)
                            results.append(dict(r))
        except Exception:
            pass

    return results


def toggle_ai_chat_state_in_dbs(chat_id: int) -> bool | None:
    """Toggle status aktif (ON/OFF) untuk chat_id di database."""
    candidate_paths = [
        USERBOT_SOURCE_DIR / "database.db",
        Path(DATABASE_PATH),
    ]

    if USERBOT_RUNTIME_DIR.exists():
        for sub_db in USERBOT_RUNTIME_DIR.glob("*/database.db"):
            candidate_paths.append(sub_db)

    found_state: bool | None = None
    for p in candidate_paths:
        if not p.exists():
            continue
        try:
            with sqlite3.connect(p) as conn:
                conn.row_factory = sqlite3.Row
                has_table = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_chat_settings'"
                ).fetchone()
                if not has_table:
                    continue
                row = conn.execute(
                    "SELECT enabled FROM ai_chat_settings WHERE chat_id = ?",
                    (int(chat_id),),
                ).fetchone()
                if row is not None:
                    if found_state is None:
                        new_val = 0 if row["enabled"] else 1
                        found_state = bool(new_val)
                    else:
                        new_val = 1 if found_state else 0
                    conn.execute(
                        "UPDATE ai_chat_settings SET enabled = ?, updated_at = ? WHERE chat_id = ?",
                        (new_val, _now(), int(chat_id)),
                    )
                    conn.commit()
        except Exception:
            pass

    return found_state


MAX_SUDO_USERS: int = 5


def count_sudo_users() -> int:
    """Hitung jumlah user Sudo aktif saat ini."""
    with _connect() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM sudo_users").fetchone()
        return int(row["total"]) if row else 0


def list_sudo_users() -> list[dict]:
    """Ambil seluruh daftar user Sudo aktif."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT telegram_id, username, full_name, added_by, added_at
            FROM sudo_users
            ORDER BY added_at ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_sudo_user(telegram_id: int) -> dict | None:
    """Ambil data satu user Sudo berdasarkan Telegram ID."""
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT telegram_id, username, full_name, added_by, added_at
            FROM sudo_users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        ).fetchone()
    return dict(row) if row else None


def is_sudo(telegram_id: int) -> bool:
    """Periksa apakah Telegram ID adalah Owner atau terdaftar sebagai Sudo."""
    if OWNER_ID and telegram_id == OWNER_ID:
        return True
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM sudo_users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        return bool(row)


def add_sudo_user(
    telegram_id: int,
    username: str | None = None,
    full_name: str | None = None,
    added_by: int | None = None,
) -> tuple[bool, str, int]:
    """
    Tambah user ke daftar Sudo.
    Maksimal 5 user aktif.
    Return (success, message, current_count).
    """
    current_count = count_sudo_users()
    if OWNER_ID and telegram_id == OWNER_ID:
        return False, "⚠️ User tersebut adalah Owner bot, sudah memiliki akses penuh.", current_count

    if get_sudo_user(telegram_id):
        return False, f"⚠️ User `{telegram_id}` sudah terdaftar sebagai Sudo Bot.", current_count

    if current_count >= MAX_SUDO_USERS:
        return (
            False,
            f"❌ Batas maksimal {MAX_SUDO_USERS} Sudo sudah tercapai ({current_count}/{MAX_SUDO_USERS}).\n"
            f"Hapus salah satu Sudo dengan `.delsudo <user>` terlebih dahulu.",
            current_count,
        )

    timestamp = _now()
    clean_name = full_name or "Pengguna Telegram"
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO sudo_users (telegram_id, username, full_name, added_by, added_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (telegram_id, username, clean_name, added_by, timestamp),
        )
        connection.commit()

    new_count = current_count + 1
    name_display = f"{clean_name} (@{username})" if username else clean_name
    return (
        True,
        f"✅ Berhasil menambahkan <b>{name_display}</b> (<code>{telegram_id}</code>) sebagai Sudo Bot ({new_count}/{MAX_SUDO_USERS}).",
        new_count,
    )


def del_sudo_user(telegram_id: int) -> tuple[bool, str, int]:
    """
    Hapus user dari daftar Sudo.
    Return (success, message, new_count).
    """
    current_count = count_sudo_users()
    existing = get_sudo_user(telegram_id)
    if not existing:
        return False, f"❌ User `{telegram_id}` tidak ditemukan dalam daftar Sudo Bot.", current_count

    with _connect() as connection:
        connection.execute(
            "DELETE FROM sudo_users WHERE telegram_id = ?",
            (telegram_id,),
        )
        connection.commit()

    new_count = count_sudo_users()
    name_display = existing.get("full_name") or str(telegram_id)
    return (
        True,
        f"✅ Berhasil mencabut akses Sudo dari <b>{name_display}</b> (<code>{telegram_id}</code>) ({new_count}/{MAX_SUDO_USERS}).",
        new_count,
    )



