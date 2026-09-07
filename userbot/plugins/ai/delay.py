"""
IBEKS USERBOT - AI Typing Simulation & Delay
Menghitung jeda pengetikan yang natural dan mengirim status typing di Telegram.
Command:
  .aidelay status     - Menampilkan konfigurasi delay saat ini.
  .aidelay <detik>    - Mengatur delay tetap (misal: .aidelay 5).
  .aidelay <min> <max>- Mengatur delay acak dalam rentang (misal: .aidelay 3 7).
  .aidelay reset      - Mengembalikan delay ke mode otomatis/default.
"""

from __future__ import annotations

import asyncio
import random
from pyrogram import filters
from pyrogram.enums import ChatAction

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui, success, warning
from utils.logger import log
from plugins.utils.ui import send_ui
from plugins.ai.config import (
    DEFAULT_MIN_DELAY,
    DEFAULT_MAX_DELAY,
    TYPING_SPEED_CPS,
    get_delay_config,
    set_fixed_delay,
    set_range_delay,
    reset_delay,
)


def calculate_typing_delay(
    text: str,
    min_delay: float = DEFAULT_MIN_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    speed_cps: float = TYPING_SPEED_CPS,
) -> float:
    """
    Hitung durasi simulasi mengetik manusia berdasarkan konfigurasi delay aktif.

    Parameters
    ----------
    text : str
        Teks yang akan dikirim.
    min_delay : float
        Waktu jeda minimal default (detik).
    max_delay : float
        Waktu jeda maksimal default (detik).
    speed_cps : float
        Kecepatan mengetik dalam karakter per detik.

    Returns
    -------
    float
        Durasi delay dalam detik.
    """
    cfg = get_delay_config()
    mode = cfg.get("mode", "auto")

    # Mode 1: Delay Tetap (Fixed)
    if mode == "fixed" and cfg.get("fixed") is not None:
        return float(cfg["fixed"])

    # Mode 2: Delay Acak dalam Rentang (Range)
    if mode == "range" and cfg.get("min") is not None and cfg.get("max") is not None:
        mn = float(cfg["min"])
        mx = float(cfg["max"])
        val = random.uniform(mn, mx)
        return round(val, 2)

    # Mode 3: Delay Otomatis / Natural Berdasarkan Panjang Teks
    char_count = len(text.strip()) if text else 0
    estimated_time = char_count / max(speed_cps, 1.0)
    delay = max(min_delay, min(estimated_time, max_delay))
    return round(delay, 2)


async def simulate_typing(client, chat_id: int, duration: float) -> None:
    """
    Kirim sinyal status 'Sedang mengetik...' (TYPING) ke chat selama durasi yang ditentukan.
    """
    try:
        await client.send_chat_action(chat_id, ChatAction.TYPING)
        # Jika durasi lebih dari 4 detik, perbarui status typing setiap 4 detik
        remaining = duration
        while remaining > 0:
            step = min(remaining, 4.0)
            await asyncio.sleep(step)
            remaining -= step
            if remaining > 0:
                await client.send_chat_action(chat_id, ChatAction.TYPING)
    except Exception as exc:
        log.debug(f"[AI Delay] Gagal mengirim chat action typing: {exc}")


def setup(client) -> None:
    """Daftarkan command .aidelay pada instance client."""

    @client.on_message(dynamic_command("aidelay") & filters.me)
    async def cmd_aidelay(client, message):
        """Handler command .aidelay [status | <detik> | <min> <max> | reset]"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        raw_text = (message.text or message.caption or "").strip()
        parts = raw_text.split()
        subcommand = parts[1].lower() if len(parts) > 1 else "status"

        if subcommand == "status":
            cfg = get_delay_config()
            mode = cfg.get("mode", "auto")
            if mode == "fixed":
                mode_desc = "Tetap (Fixed)"
                delay_desc = f"{cfg.get('fixed')} detik"
            elif mode == "range":
                mode_desc = "Acak dalam Rentang (Random Range)"
                delay_desc = f"{cfg.get('min')}s s/d {cfg.get('max')}s"
            else:
                mode_desc = "Otomatis Natural (Auto)"
                delay_desc = f"{DEFAULT_MIN_DELAY}s - {DEFAULT_MAX_DELAY}s (sesuai panjang teks)"

            body = (
                f"📌 Mode Delay : {mode_desc}\n"
                f"⏱️ Durasi Saat Ini : {delay_desc}\n"
                f"⌨️ Indikator Typing : Aktif selama delay\n\n"
                "💡 Cara Penggunaan:\n"
                "• .aidelay <detik> (contoh: .aidelay 5)\n"
                "• .aidelay <min> <max> (contoh: .aidelay 3 7)\n"
                "• .aidelay reset\n"
                "• .aidelay status"
            )
            text = format_ui(
                title="DELAY & TYPING AI",
                body=body,
                emoji="⏳",
                expandable=True,
            )
            await send_ui(client, message.chat.id, text, expandable=True)
            return

        if subcommand == "reset":
            reset_delay()
            text = success(
                title="DELAY AI DIRESET",
                message=f"📌 Status : Delay dikembalikan ke mode Otomatis ({DEFAULT_MIN_DELAY}s - {DEFAULT_MAX_DELAY}s).",
                emoji="🔄",
            )
            await send_ui(client, message.chat.id, text, expandable=True)
            return

        # Kasus rentang acak: .aidelay <min> <max>
        if len(parts) >= 3:
            try:
                val_min = float(parts[1])
                val_max = float(parts[2])
                mn, mx = set_range_delay(val_min, val_max)
                text = success(
                    title="DELAY AI DIPERBARUI",
                    message=(
                        "📌 Mode : Rentang Acak (Random Range)\n"
                        f"⏱️ Rentang Jeda : {mn}s sampai {mx}s\n"
                        "⌨️ Typing : Status mengetik akan aktif selama rentang tersebut."
                    ),
                    emoji="✅",
                )
                await send_ui(client, message.chat.id, text, expandable=True)
                return
            except ValueError:
                pass

        # Kasus single number: .aidelay <detik>
        try:
            val_sec = float(parts[1])
            applied = set_fixed_delay(val_sec)
            text = success(
                title="DELAY AI DIPERBARUI",
                message=(
                    "📌 Mode : Delay Tetap (Fixed)\n"
                    f"⏱️ Durasi Jeda : {applied} detik\n"
                    f"⌨️ Typing : Status mengetik akan aktif selama {applied}s sebelum pesan dikirim."
                ),
                emoji="✅",
            )
            await send_ui(client, message.chat.id, text, expandable=True)
            return
        except ValueError:
            pass

        # Subcommand tidak valid
        help_text = format_ui(
            title="BANTUAN AI DELAY",
            body=(
                "📖 Perintah Tersedia:\n"
                "• .aidelay status : Lihat konfigurasi delay\n"
                "• .aidelay <detik> : Set delay tetap (contoh: .aidelay 5)\n"
                "• .aidelay <min> <max> : Set delay acak (contoh: .aidelay 3 7)\n"
                "• .aidelay reset : Kembalikan ke otomatis"
            ),
            emoji="❓",
            expandable=True,
        )
        await send_ui(client, message.chat.id, help_text, expandable=True)

