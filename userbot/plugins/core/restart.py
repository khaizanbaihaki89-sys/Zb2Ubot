"""
IBEKS USERBOT - Plugin: restart
Command: .restart
Merestart userbot dan mengirim notifikasi setelah hidup kembali.
"""

import os
import sys

from pyrogram import filters

from config import MAIN_FILE, RESTART_STATE_FILE
from utils.filters import dynamic_command
from utils.logger import log


def setup(client):
    """Daftarkan handler .restart pada instance client."""

    @client.on_message(dynamic_command("restart") & filters.me)
    async def cmd_restart(client, message):
        """Handler command .restart"""
        # Hanya simpan marker. Main akan mengirim notifikasi ke Bot Manager,
        # bukan ke chat tempat command diketik (yang bisa saja berupa grup).
        try:
            with open(RESTART_STATE_FILE, "w", encoding="utf-8") as f:
                f.write("1")
        except Exception as exc:
            log.warning(f"[Restart] Gagal menyimpan state restart: {exc}")

        # Ganti proses saat ini dengan instance baru dari main.py
        try:
            os.execv(sys.executable, [sys.executable, MAIN_FILE])
        except Exception as exc:
            log.exception(f"[Restart] Gagal restart: {exc}")
