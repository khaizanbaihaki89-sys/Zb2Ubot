"""Akses SQLite untuk pengguna dan hasil login Telegram."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DATABASE_PATH, OWNER_ID


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



