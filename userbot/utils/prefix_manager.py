"""
IBEKS USERBOT - Prefix Manager
Mengelola prefix command dari database.
Semua plugin membaca prefix melalui utilitas ini agar perubahan prefix
langsung berlaku tanpa hardcode.
"""

from typing import Optional

try:
    from config import CMD_PREFIX
except (ImportError, AttributeError):
    CMD_PREFIX = "."

from db import get_prefix as _db_get_prefix, set_prefix as _db_set_prefix

# Owner ID di-cache setelah login agar tidak perlu query get_me() berulang kali
_owner_id: Optional[int] = None


def set_owner_id(telegram_id: int) -> None:
    """Set owner ID yang akan digunakan sebagai kunci prefix di database."""
    global _owner_id
    _owner_id = telegram_id


def get_owner_id() -> Optional[int]:
    """Kembalikan owner ID yang sudah di-cache."""
    return _owner_id


def get_prefix(default: Optional[str] = None) -> str:
    """
    Kembalikan prefix aktif dari database.
    Jika belum ada di database, kembalikan default dari config.
    """
    if _owner_id is None:
        return default or CMD_PREFIX
    return _db_get_prefix(_owner_id, default=default or CMD_PREFIX)


def set_prefix(prefix: str) -> None:
    """Simpan prefix baru ke database untuk owner yang sedang login."""
    if _owner_id is None:
        raise RuntimeError("Owner ID belum di-set. Panggil set_owner_id() setelah login.")
    _db_set_prefix(_owner_id, prefix)


def is_valid_prefix(prefix: str) -> bool:
    """Validasi prefix yang didukung IBEKS USERBOT."""
    return prefix in {".", "/", "!", "?"}
