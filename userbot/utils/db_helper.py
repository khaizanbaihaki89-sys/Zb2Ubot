"""
IBEKS USERBOT - Database Helper
Wrapper helper untuk akses database yang sering digunakan plugin.
Semua fungsi bersifat synchronous karena SQLite; panggil dari async handler
jika hanya read/write ringan.
"""

from typing import Optional

from db import get_conn


def log_command(user_id: int, command: str, chat_id: int) -> None:
    """Catat command yang dieksekusi ke tabel command_logs."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO command_logs (user_id, command, chat_id) VALUES (?, ?, ?)",
        (user_id, command, chat_id),
    )
    conn.commit()


def ensure_user(user_id: int, first_name: Optional[str] = None, username: Optional[str] = None) -> None:
    """Simpan atau update data user dasar ke tabel users."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (user_id, first_name, username) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET first_name = excluded.first_name, username = excluded.username",
        (user_id, first_name, username),
    )
    conn.commit()
