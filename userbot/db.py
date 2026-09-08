"""SQLite storage for the IBEKS Userbot.

The userbot keeps one SQLite database for settings and runtime state.  All
helpers in this module are synchronous because each operation is a small
SQLite transaction and the callers already run in the Pyrogram event loop.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import BASE_DIR, DATABASE_PATH


_SETTINGS_COLUMNS = {
    "prefix",
    "auto_delete",
    "delay_auto_delete",
    "animation",
    "logger",
    "emoji_mode",
    "theme",
    "language",
    "timezone",
    "ai_manual_style",
    "ai_learned_style",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active_account_id() -> int:
    """Return the Telegram ID represented by this isolated runtime."""
    runtime_name = Path(BASE_DIR).name
    try:
        account_id = int(runtime_name)
    except (TypeError, ValueError):
        return 0
    return account_id if account_id > 0 else 0


def get_conn() -> sqlite3.Connection:
    """Open the configured database with dictionary-like rows."""
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    """Create/migrate the existing userbot schema without replacing its data."""
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                added_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS settings (
                telegram_id INTEGER PRIMARY KEY,
                prefix TEXT DEFAULT '.',
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS blacklist (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS command_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                command TEXT,
                chat_id INTEGER,
                executed_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS plugin_status (
                module TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                category TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                loaded INTEGER NOT NULL DEFAULT 0,
                version TEXT NOT NULL DEFAULT '1.0.0',
                author TEXT NOT NULL DEFAULT 'IBEKS',
                command_count INTEGER NOT NULL DEFAULT 0,
                loaded_at TEXT,
                file_size INTEGER NOT NULL DEFAULT 0,
                file_path TEXT,
                last_error TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS dashboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                runtime TEXT,
                cpu_percent REAL,
                ram_percent REAL,
                disk_percent REAL,
                database_size INTEGER,
                total_plugins INTEGER,
                active_plugins INTEGER,
                inactive_plugins INTEGER,
                captured_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS themes (
                name TEXT PRIMARY KEY,
                definition TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS ai_chat_settings (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT DEFAULT '',
                chat_type TEXT DEFAULT 'private',
                enabled INTEGER NOT NULL DEFAULT 0,
                custom_instruction TEXT DEFAULT '',
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sudo_users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                added_by INTEGER,
                added_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS truth_dare (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS td_participants (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                username TEXT DEFAULT '',
                joined_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (chat_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS td_game_state (
                chat_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'waiting',
                current_user_id INTEGER,
                current_user_name TEXT,
                current_username TEXT DEFAULT '',
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS rc_settings (
                owner_id INTEGER PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'buka',
                reject_message TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            """
        )

        # Settings were added incrementally by the control-panel features.
        for column, definition in (
            ("auto_delete", "INTEGER NOT NULL DEFAULT 1"),
            ("delay_auto_delete", "INTEGER NOT NULL DEFAULT 5"),
            ("animation", "INTEGER NOT NULL DEFAULT 1"),
            ("logger", "INTEGER NOT NULL DEFAULT 1"),
            ("emoji_mode", "INTEGER NOT NULL DEFAULT 1"),
            ("theme", "TEXT NOT NULL DEFAULT 'Premium'"),
            ("language", "TEXT NOT NULL DEFAULT 'id'"),
            ("timezone", "TEXT NOT NULL DEFAULT 'UTC'"),
            ("ai_manual_style", "TEXT DEFAULT ''"),
            ("ai_learned_style", "TEXT DEFAULT ''"),
        ):
            _ensure_column(conn, "settings", column, definition)

        _ensure_column(conn, "td_participants", "username", "TEXT DEFAULT ''")
        _ensure_column(conn, "td_game_state", "status", "TEXT NOT NULL DEFAULT 'waiting'")

        default_definition = "╭─「 {title} 」\n│\n{body}\n│\n╰─ ⨱ IBEKS USERBOT ⨱"
        for name in ("Premium", "Freeze", "Minimal", "Neon", "Matrix"):
            conn.execute(
                """
                INSERT OR IGNORE INTO themes
                    (name, definition, is_active, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, default_definition, 1 if name == "Premium" else 0, _now()),
            )
        conn.commit()
    finally:
        conn.close()


def ensure_user_settings(telegram_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO settings (telegram_id, prefix, updated_at) VALUES (?, '.', ?)",
            (int(telegram_id), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_setting(telegram_id: int, key: str, default: Any = None) -> Any:
    if key not in _SETTINGS_COLUMNS:
        raise ValueError(f"Unknown settings key: {key}")
    ensure_user_settings(int(telegram_id))
    conn = get_conn()
    try:
        row = conn.execute(
            f"SELECT {key} FROM settings WHERE telegram_id = ?",
            (int(telegram_id),),
        ).fetchone()
        return row[key] if row is not None else default
    finally:
        conn.close()


def set_setting(telegram_id: int, key: str, value: Any) -> None:
    if key not in _SETTINGS_COLUMNS:
        raise ValueError(f"Unknown settings key: {key}")
    ensure_user_settings(int(telegram_id))
    conn = get_conn()
    try:
        conn.execute(
            f"UPDATE settings SET {key} = ?, updated_at = ? WHERE telegram_id = ?",
            (value, _now(), int(telegram_id)),
        )
        conn.commit()
    finally:
        conn.close()


def get_prefix(telegram_id: int, default: str = ".") -> str:
    return str(get_setting(telegram_id, "prefix", default) or default)


def set_prefix(telegram_id: int, prefix: str) -> None:
    set_setting(telegram_id, "prefix", prefix)


def add_blacklist(chat_id: int, chat_title: str = "") -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO blacklist (chat_id, chat_title, created_at) VALUES (?, ?, ?)",
            (int(chat_id), chat_title, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def del_blacklist(chat_id: int) -> bool:
    conn = get_conn()
    try:
        cursor = conn.execute("DELETE FROM blacklist WHERE chat_id = ?", (int(chat_id),))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def is_blacklisted(chat_id: int) -> bool:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT 1 FROM blacklist WHERE chat_id = ?", (int(chat_id),)
        ).fetchone() is not None
    finally:
        conn.close()


def list_blacklist() -> list[dict]:
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(
            "SELECT chat_id, chat_title, created_at FROM blacklist ORDER BY created_at DESC"
        ).fetchall()]
    finally:
        conn.close()


def upsert_plugin_status(metadata: dict) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO plugin_status
                (module, filename, category, version, author, command_count,
                 file_size, file_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(module) DO UPDATE SET
                filename = excluded.filename,
                category = excluded.category,
                version = excluded.version,
                author = excluded.author,
                command_count = excluded.command_count,
                file_size = excluded.file_size,
                file_path = excluded.file_path,
                updated_at = excluded.updated_at
            """,
            (
                metadata["module"],
                metadata["filename"],
                metadata["category"],
                metadata.get("version", "1.0.0"),
                metadata.get("author", "IBEKS"),
                int(metadata.get("command_count", 0)),
                int(metadata.get("file_size", 0)),
                metadata.get("file_path"),
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_plugin_status(module_name: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM plugin_status WHERE module = ?", (module_name,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_plugin_status() -> list[dict]:
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM plugin_status ORDER BY module"
        ).fetchall()]
    finally:
        conn.close()


def set_plugin_runtime(module_name: str, loaded: bool, loaded_at: str | None = None,
                       last_error: str | None = None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE plugin_status
            SET loaded = ?, loaded_at = ?, last_error = ?, updated_at = ?
            WHERE module = ?
            """,
            (int(bool(loaded)), loaded_at, last_error, _now(), module_name),
        )
        conn.commit()
    finally:
        conn.close()


def set_plugin_enabled(module_name: str, enabled: bool) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE plugin_status SET enabled = ?, updated_at = ? WHERE module = ?",
            (int(bool(enabled)), _now(), module_name),
        )
        conn.commit()
    finally:
        conn.close()


def record_dashboard(snapshot: dict) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO dashboard
                (runtime, cpu_percent, ram_percent, disk_percent, database_size,
                 total_plugins, active_plugins, inactive_plugins)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.get("runtime"),
                snapshot.get("cpu_percent"),
                snapshot.get("ram_percent"),
                snapshot.get("disk_percent"),
                snapshot.get("database_size"),
                snapshot.get("total_plugins"),
                snapshot.get("active_plugins"),
                snapshot.get("inactive_plugins"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_themes() -> list[dict]:
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(
            "SELECT name, definition, is_active, updated_at FROM themes ORDER BY name"
        ).fetchall()]
    finally:
        conn.close()


def active_theme() -> str:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT name FROM themes WHERE is_active = 1 ORDER BY name LIMIT 1"
        ).fetchone()
        return str(row["name"]) if row else "Premium"
    finally:
        conn.close()


def save_theme(name: str, definition: str, active: bool = False) -> None:
    conn = get_conn()
    try:
        if active:
            conn.execute("UPDATE themes SET is_active = 0, updated_at = ?", (_now(),))
        conn.execute(
            """
            INSERT INTO themes (name, definition, is_active, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                definition = excluded.definition,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
            """,
            (name, definition, int(bool(active)), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def set_ai_chat_state(
    chat_id: int,
    enabled: bool,
    custom_instruction: str | None = None,
    chat_title: str = "",
    chat_type: str = "private",
) -> None:
    """Simpan status aktivasi dan instruksi AI per-chat."""
    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT * FROM ai_chat_settings WHERE chat_id = ?",
            (int(chat_id),),
        ).fetchone()

        instruction = (
            custom_instruction
            if custom_instruction is not None
            else (existing["custom_instruction"] if existing else "")
        )
        title = chat_title or (existing["chat_title"] if existing else "")
        c_type = chat_type or (existing["chat_type"] if existing else "private")

        conn.execute(
            """
            INSERT INTO ai_chat_settings (chat_id, chat_title, chat_type, enabled, custom_instruction, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                chat_title = excluded.chat_title,
                chat_type = excluded.chat_type,
                enabled = excluded.enabled,
                custom_instruction = excluded.custom_instruction,
                updated_at = excluded.updated_at
            """,
            (int(chat_id), title, c_type, int(bool(enabled)), instruction, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_ai_chat_state(chat_id: int | str) -> dict | None:
    """Ambil status dan konfigurasi AI untuk chat tertentu secara akurat per-chat."""
    if chat_id is None:
        return None
    try:
        cid = int(chat_id)
    except (ValueError, TypeError):
        return None

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM ai_chat_settings WHERE chat_id = ?",
            (cid,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def is_ai_chat_active(chat_id: int | str) -> bool:
    """Cek apakah AI aktif khusus untuk chat_id ini (Per-Chat State)."""
    state = get_ai_chat_state(chat_id)
    return bool(state and state.get("enabled"))


def list_ai_chat_states() -> list[dict]:
    """Ambil seluruh daftar chat yang memiliki pengaturan AI."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM ai_chat_settings ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_ai_chat_state(chat_id: int) -> bool:
    """Hapus entri konfigurasi AI chat."""
    conn = get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM ai_chat_settings WHERE chat_id = ?",
            (int(chat_id),),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def count_sudo_users() -> int:
    """Hitung Sudo hanya di database runtime account aktif."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) AS total FROM sudo_users").fetchone()
        return int(row["total"]) if row else 0
    finally:
        conn.close()


def list_sudo_users() -> list[dict]:
    """Ambil daftar Sudo dari runtime account aktif."""
    conn = get_conn()
    try:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT telegram_id, username, full_name, added_by, added_at
                FROM sudo_users
                ORDER BY added_at ASC
                """
            ).fetchall()
        ]
    finally:
        conn.close()


def get_sudo_user(telegram_id: int) -> dict | None:
    """Cari Sudo hanya di runtime account aktif."""
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT telegram_id, username, full_name, added_by, added_at
            FROM sudo_users
            WHERE telegram_id = ?
            """,
            (int(telegram_id),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_sudo_user(
    telegram_id: int,
    username: str | None,
    full_name: str | None,
    added_by: int | None,
    max_users: int = 5,
) -> tuple[bool, str, int]:
    """Tambah Sudo ke runtime account aktif dengan batas per-account."""
    current_count = count_sudo_users()
    if get_sudo_user(telegram_id):
        return False, f"User {telegram_id} sudah terdaftar sebagai Sudo.", current_count
    if current_count >= max_users:
        return False, f"Batas maksimal {max_users} Sudo tercapai ({current_count}/{max_users}).", current_count

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO sudo_users (telegram_id, username, full_name, added_by, added_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(telegram_id),
                username,
                full_name or "Pengguna Telegram",
                added_by,
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return True, "Berhasil menambahkan Sudo", current_count + 1


def del_sudo_user(telegram_id: int) -> tuple[bool, str, int]:
    """Hapus Sudo dari runtime account aktif."""
    current_count = count_sudo_users()
    conn = get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM sudo_users WHERE telegram_id = ?", (int(telegram_id),)
        )
        conn.commit()
        if cursor.rowcount == 0:
            return False, f"User {telegram_id} tidak ditemukan dalam daftar Sudo.", current_count
    finally:
        conn.close()
    return True, "Berhasil mencabut Sudo", current_count - 1


def add_td_item(category: str, text: str) -> int:
    """Tambah konten Truth/Dare/Penalty ke database."""
    category = str(category).lower().strip()
    text = str(text).strip()
    conn = get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO truth_dare (category, text, created_at) VALUES (?, ?, ?)",
            (category, text, _now()),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def add_td_items(category: str, items: list[str]) -> list[int]:
    """Tambah beberapa konten Truth/Dare/Penalty sekaligus ke database."""
    category = str(category).lower().strip()
    conn = get_conn()
    added_ids = []
    try:
        for text in items:
            clean_text = str(text).strip()
            if clean_text:
                cursor = conn.execute(
                    "INSERT INTO truth_dare (category, text, created_at) VALUES (?, ?, ?)",
                    (category, clean_text, _now()),
                )
                added_ids.append(cursor.lastrowid)
        conn.commit()
        return added_ids
    finally:
        conn.close()


def add_td_participant(chat_id: int, user_id: int, user_name: str = "", username: str = "") -> bool:
    """Tambahkan user ke daftar peserta sesi Truth & Dare pada chat tertentu."""
    clean_uname = str(username or "").lstrip("@").strip()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO td_participants (chat_id, user_id, user_name, username, joined_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                user_name = excluded.user_name,
                username = CASE WHEN excluded.username != '' THEN excluded.username ELSE td_participants.username END
            """,
            (int(chat_id), int(user_id), str(user_name or "Pemain"), clean_uname, _now()),
        )
        # Pastikan ada entry game_state berstatus 'waiting' jika belum ada (tanpa menentukan giliran)
        conn.execute(
            """
            INSERT INTO td_game_state (chat_id, status, updated_at)
            VALUES (?, 'waiting', ?)
            ON CONFLICT(chat_id) DO NOTHING
            """,
            (int(chat_id), _now()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_td_game_state(chat_id: int) -> dict:
    """Ambil status sesi Truth & Dare pada chat tertentu."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT chat_id, status, current_user_id, current_user_name, current_username, updated_at FROM td_game_state WHERE chat_id = ?",
            (int(chat_id),),
        ).fetchone()
        if row:
            return {
                "chat_id": row["chat_id"],
                "status": str(row["status"] or "waiting"),
                "current_user_id": row["current_user_id"],
                "current_user_name": row["current_user_name"],
                "current_username": row["current_username"],
                "updated_at": row["updated_at"],
            }
        return {
            "chat_id": int(chat_id),
            "status": "waiting",
            "current_user_id": None,
            "current_user_name": None,
            "current_username": "",
            "updated_at": None,
        }
    finally:
        conn.close()


def start_td_game(chat_id: int) -> tuple[bool, dict | None, str]:
    """
    Mulai sesi Truth & Dare di chat tertentu jika peserta minimal 2.
    Mengubah status menjadi 'active' dan menentukan giliran pertama.
    Mengembalikan (success, first_turn_participant, message).
    """
    import random

    conn = get_conn()
    try:
        participants = [
            dict(r)
            for r in conn.execute(
                "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? ORDER BY joined_at ASC, rowid ASC",
                (int(chat_id),),
            ).fetchall()
        ]
        if len(participants) < 2:
            return (
                False,
                None,
                f"Peserta belum cukup ({len(participants)}/2). Minimal butuh 2 pemain yang sudah .join!",
            )

        first_player = random.choice(participants)
        conn.execute(
            """
            INSERT INTO td_game_state (chat_id, status, current_user_id, current_user_name, current_username, updated_at)
            VALUES (?, 'active', ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                status = 'active',
                current_user_id = excluded.current_user_id,
                current_user_name = excluded.current_user_name,
                current_username = excluded.current_username,
                updated_at = excluded.updated_at
            """,
            (
                int(chat_id),
                first_player["user_id"],
                first_player["user_name"],
                first_player.get("username", ""),
                _now(),
            ),
        )
        conn.commit()
        return True, first_player, "Permainan berhasil dimulai!"
    finally:
        conn.close()


def is_td_participant(chat_id: int, user_id: int) -> bool:
    """Periksa apakah user sudah bergabung dalam sesi Truth & Dare di chat tertentu."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM td_participants WHERE chat_id = ? AND user_id = ?",
            (int(chat_id), int(user_id)),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_td_participants(chat_id: int) -> list[dict]:
    """Ambil seluruh daftar peserta sesi Truth & Dare di chat tertentu."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? ORDER BY joined_at ASC, rowid ASC",
            (int(chat_id),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_td_participant(chat_id: int, identifier: str | int) -> dict | None:
    """Cari peserta Truth & Dare tunggal berdasarkan user_id, username (@user), atau nama."""
    matches = find_td_participants(chat_id, identifier)
    if len(matches) == 1:
        return matches[0]
    return None


def find_td_participants(chat_id: int, identifier: str | int) -> list[dict]:
    """
    Cari semua peserta Truth & Dare yang cocok berdasarkan user_id, username (@user), atau nama.
    Mengembalikan list peserta yang cocok.
    """
    if identifier is None:
        return []
    conn = get_conn()
    try:
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.strip().isdigit()):
            rows = conn.execute(
                "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? AND user_id = ?",
                (int(chat_id), int(identifier)),
            ).fetchall()
            if rows:
                return [dict(r) for r in rows]

        raw_str = str(identifier).strip()
        is_username_query = raw_str.startswith("@")
        clean_str = raw_str.lstrip("@").strip().lower()
        if not clean_str:
            return []

        # 1. Jika diawali @ atau dicari sebagai username:
        if is_username_query:
            rows = conn.execute(
                "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? AND LOWER(username) = ?",
                (int(chat_id), clean_str),
            ).fetchall()
            if rows:
                return [dict(r) for r in rows]

        # 2. Jika tanpa @, prioritaskan username exact match dulu jika ada
        rows = conn.execute(
            "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? AND LOWER(username) = ?",
            (int(chat_id), clean_str),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]

        # 3. Cari berdasarkan exact user_name (case-insensitive)
        rows = conn.execute(
            "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? AND LOWER(user_name) = ?",
            (int(chat_id), clean_str),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]

        # 4. Cari berdasarkan substring/prefix nama jika diperlukan
        rows = conn.execute(
            "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? AND LOWER(user_name) LIKE ?",
            (int(chat_id), f"%{clean_str}%"),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]

        return []
    finally:
        conn.close()


def get_td_current_turn(chat_id: int) -> dict | None:
    """Ambil data pemain yang sedang memegang giliran saat ini."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT current_user_id, current_user_name, current_username, status FROM td_game_state WHERE chat_id = ?",
            (int(chat_id),),
        ).fetchone()
        if row and row["current_user_id"]:
            p_row = conn.execute(
                "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? AND user_id = ?",
                (int(chat_id), int(row["current_user_id"])),
            ).fetchone()
            if p_row:
                return dict(p_row)
        return None
    finally:
        conn.close()


def set_td_current_turn(chat_id: int, user_id: int, user_name: str = "", username: str = "") -> bool:
    """Set secara manual/eksplisit giliran pemain aktif."""
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO td_game_state (chat_id, status, current_user_id, current_user_name, current_username, updated_at)
            VALUES (?, 'active', ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                status = 'active',
                current_user_id = excluded.current_user_id,
                current_user_name = excluded.current_user_name,
                current_username = excluded.current_username,
                updated_at = excluded.updated_at
            """,
            (int(chat_id), int(user_id), str(user_name or "Pemain"), str(username or "").lstrip("@"), _now()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def advance_td_turn(chat_id: int, next_user_id: int | None = None) -> dict | None:
    """
    Lanjutkan giliran ke pemain berikutnya.
    Jika next_user_id tidak ditentukan, pilih secara acak/random dari daftar peserta yang sudah /join di chat ini.
    """
    import random

    conn = get_conn()
    try:
        participants = [
            dict(r) for r in conn.execute(
                "SELECT chat_id, user_id, user_name, username, joined_at FROM td_participants WHERE chat_id = ? ORDER BY joined_at ASC, rowid ASC",
                (int(chat_id),),
            ).fetchall()
        ]
        if not participants:
            conn.execute("DELETE FROM td_game_state WHERE chat_id = ?", (int(chat_id),))
            conn.commit()
            return None

        target_p = None
        if next_user_id is not None:
            for p in participants:
                if p["user_id"] == int(next_user_id):
                    target_p = p
                    break

        if not target_p:
            # Utamakan pengacakan/random dari daftar peserta yang valid
            target_p = random.choice(participants)

        conn.execute(
            """
            INSERT INTO td_game_state (chat_id, status, current_user_id, current_user_name, current_username, updated_at)
            VALUES (?, 'active', ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                status = 'active',
                current_user_id = excluded.current_user_id,
                current_user_name = excluded.current_user_name,
                current_username = excluded.current_username,
                updated_at = excluded.updated_at
            """,
            (int(chat_id), target_p["user_id"], target_p["user_name"], target_p.get("username", ""), _now()),
        )
        conn.commit()
        return target_p
    finally:
        conn.close()


def reset_td_participants(chat_id: int) -> int:
    """Reset / hapus semua peserta dan state sesi Truth & Dare pada chat tertentu."""
    conn = get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM td_participants WHERE chat_id = ?",
            (int(chat_id),),
        )
        conn.execute(
            "DELETE FROM td_game_state WHERE chat_id = ?",
            (int(chat_id),),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_td_items(category: str) -> list[dict]:
    """Ambil semua daftar konten Truth/Dare/Penalty."""
    category = str(category).lower().strip()
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, category, text, created_at FROM truth_dare WHERE category = ? ORDER BY id ASC",
            (category,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_random_td_item(category: str) -> dict | None:
    """Ambil satu konten Truth/Dare/Penalty secara acak."""
    category = str(category).lower().strip()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, category, text, created_at FROM truth_dare WHERE category = ? ORDER BY RANDOM() LIMIT 1",
            (category,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_td_item(category: str, item_id: int) -> bool:
    """Hapus konten Truth/Dare/Penalty berdasarkan ID."""
    category = str(category).lower().strip()
    conn = get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM truth_dare WHERE category = ? AND id = ?",
            (category, int(item_id)),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_rc_settings(account_id: int) -> dict:
    """Ambil konfigurasi RC Control untuk akun Userbot tertentu."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT mode, reject_message FROM rc_settings WHERE owner_id = ?",
            (int(account_id),),
        ).fetchone()
        if row:
            return {
                "mode": str(row["mode"] or "buka"),
                "reject_message": str(row["reject_message"]) if row["reject_message"] else None,
            }
        return {"mode": "buka", "reject_message": None}
    finally:
        conn.close()


def migrate_rc_settings(source_account_id: int, target_account_id: int) -> bool:
    """Pindahkan state RC legacy jika row akun aktif belum tersedia."""
    source_id = int(source_account_id)
    target_id = int(target_account_id)
    if source_id <= 0 or target_id <= 0 or source_id == target_id:
        return False

    conn = get_conn()
    try:
        source = conn.execute(
            "SELECT mode, reject_message, updated_at FROM rc_settings WHERE owner_id = ?",
            (source_id,),
        ).fetchone()
        if not source:
            return False

        target_exists = conn.execute(
            "SELECT 1 FROM rc_settings WHERE owner_id = ?",
            (target_id,),
        ).fetchone()
        if target_exists:
            return False

        conn.execute(
            """
            INSERT INTO rc_settings (owner_id, mode, reject_message, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                target_id,
                str(source["mode"] or "buka"),
                source["reject_message"],
                source["updated_at"] or _now(),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def set_rc_mode(account_id: int, mode: str) -> None:
    """Set mode RC Control ('buka', 'kontak', 'tutup') untuk akun tertentu."""
    mode = str(mode or "buka").lower().strip()
    if mode not in ("buka", "kontak", "tutup"):
        mode = "buka"
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO rc_settings (owner_id, mode, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(owner_id) DO UPDATE SET
                mode = excluded.mode,
                updated_at = excluded.updated_at
            """,
            (int(account_id), mode, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def set_rc_message(account_id: int, message: str) -> None:
    """Set custom rejection message untuk akun Userbot tertentu."""
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO rc_settings (owner_id, mode, reject_message, updated_at)
            VALUES (?, 'buka', ?, ?)
            ON CONFLICT(owner_id) DO UPDATE SET
                reject_message = excluded.reject_message,
                updated_at = excluded.updated_at
            """,
            (int(account_id), str(message), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_ai_manual_style(owner_id: int | None = None) -> str | None:
    """Ambil instruksi gaya manual dari row account aktif saja."""
    account_id = int(owner_id) if owner_id is not None else _active_account_id()
    ensure_user_settings(account_id)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT ai_manual_style FROM settings WHERE telegram_id = ?",
            (account_id,),
        ).fetchone()
        if row and row["ai_manual_style"]:
            return str(row["ai_manual_style"]).strip() or None
        return None
    except Exception:
        return None
    finally:
        conn.close()


def set_ai_manual_style(prompt: str | None, owner_id: int | None = None) -> None:
    """Simpan instruksi gaya manual hanya untuk account aktif."""
    val = str(prompt).strip() if prompt else ""
    account_id = int(owner_id) if owner_id is not None else _active_account_id()
    ensure_user_settings(account_id)
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE settings SET ai_manual_style = ?, updated_at = ? WHERE telegram_id = ?",
            (val, _now(), account_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_ai_learned_style(owner_id: int | None = None) -> str | None:
    """Ambil profil gaya terpelajari dari row account aktif saja."""
    account_id = int(owner_id) if owner_id is not None else _active_account_id()
    ensure_user_settings(account_id)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT ai_learned_style FROM settings WHERE telegram_id = ?",
            (account_id,),
        ).fetchone()
        if row and row["ai_learned_style"]:
            return str(row["ai_learned_style"]).strip() or None
        return None
    except Exception:
        return None
    finally:
        conn.close()


def set_ai_learned_style(prompt: str | None, owner_id: int | None = None) -> None:
    """Simpan profil gaya terpelajari hanya untuk account aktif."""
    val = str(prompt).strip() if prompt else ""
    account_id = int(owner_id) if owner_id is not None else _active_account_id()
    ensure_user_settings(account_id)
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE settings SET ai_learned_style = ?, updated_at = ? WHERE telegram_id = ?",
            (val, _now(), account_id),
        )
        conn.commit()
    finally:
        conn.close()


