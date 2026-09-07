"""
IBEKS USERBOT - Helper Utilities
Fungsi-fungsi pembantu umum yang dapat digunakan seluruh plugin.
"""

import time
import psutil


def get_ram_usage() -> float:
    """Kembalikan persentase penggunaan RAM sistem."""
    return psutil.virtual_memory().percent


def get_cpu_usage() -> float:
    """Kembalikan persentase penggunaan CPU sistem (interval 0.1 detik)."""
    return psutil.cpu_percent(interval=0.1)


async def measure_ping(client) -> float:
    """
    Ukur waktu respons API Telegram dalam milidetik.
    Menggunakan get_me() sebagai indikator ping API.
    """
    start = time.monotonic()
    await client.get_me()
    return round((time.monotonic() - start) * 1000, 2)
