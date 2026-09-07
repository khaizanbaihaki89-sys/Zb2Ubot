"""
IBEKS USERBOT - Uptime Tracker
Menyimpan waktu mulai bot dan menghitung durasi uptime.
"""

import time

_START_TIME: float = time.time()


def get_uptime_seconds() -> float:
    """Kembalikan jumlah detik sejak bot dimulai."""
    return time.time() - _START_TIME


def format_uptime() -> str:
    """Format uptime menjadi string yang mudah dibaca: Xh Xm Xs."""
    total = int(get_uptime_seconds())
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"
