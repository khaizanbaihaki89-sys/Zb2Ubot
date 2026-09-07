"""Entry point IBEKS MANAGER BOT."""

from __future__ import annotations

import sys
import fcntl
import os
import signal
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    API_HASH,
    API_ID,
    BOT_NAME,
    BOT_TOKEN,
    INSTANCE_LOCK_PATH,
    VERSION,
)

# Import Telegram patch dari userbot
userbot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "userbot")
if userbot_dir not in sys.path:
    sys.path.append(userbot_dir)

import utils.telegram_patch  # Patch native collapsible blockquotes Layer 178+
import pyrogram
from pyrogram import Client
from database import init_db
from help_bridge import start_help_bridge
from panel_bridge import start_panel_bridge
from voice_bridge import start_voice_bridge
from clone_bridge import start_clone_bridge
from loader import load_plugins
from logger import install_global_error_handler, log
from runner import UserbotRunner, set_runner
from subscription import check_all_sync, start_checker


def validate_config() -> None:
    """Pastikan semua secret wajib tersedia sebelum bot dimulai."""
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not API_ID:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if missing:
        raise RuntimeError(f"Secret belum tersedia: {', '.join(missing)}")


def acquire_instance_lock():
    """Pastikan hanya satu proses Manager memakai BOT_TOKEN."""
    lock_file = INSTANCE_LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise RuntimeError(
            "Manager Bot instance lain masih berjalan; startup dibatalkan."
        ) from exc
    lock_file.write(f"pid={os.getpid()}\n")
    lock_file.flush()
    return lock_file


def _handle_shutdown_signal(signum, _frame) -> None:
    """Biarkan ``finally`` menghentikan semua worker sebelum Manager keluar."""
    log.info("Sinyal shutdown diterima (%s). Menutup Manager dengan aman.", signum)
    raise KeyboardInterrupt


def main() -> None:
    install_global_error_handler()
    lock_file = None
    runner = UserbotRunner()
    try:
        signal.signal(signal.SIGTERM, _handle_shutdown_signal)
        signal.signal(signal.SIGINT, _handle_shutdown_signal)
        lock_file = acquire_instance_lock()
        validate_config()
        init_db()
        log.info("✓ Database SQLite siap.")
        check_all_sync()

        client = Client(
            name="ibeks_manager_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            in_memory=True,
        )
        log.info(
            "%s v%s mulai dengan Pyrogram %s.",
            BOT_NAME,
            VERSION,
            pyrogram.__version__,
        )

        stats = load_plugins(client)
        if stats["failed"]:
            log.error("Sebagian plugin gagal dimuat: %s", stats["failed"])
        set_runner(runner)
        runner.start()
        start_help_bridge(client)
        start_panel_bridge(client)
        start_voice_bridge(client)
        start_clone_bridge(client)
        start_checker(client)
        client.run()
    except KeyboardInterrupt:
        log.info("Manager Bot dihentikan oleh pengguna.")
    except pyrogram.errors.FloodWait as e:
        log.warning("[Manager] Terkena FloodWait dari Telegram: perlu menunggu %s detik.", e.value)
        # Tunggu sampai FloodWait selesai sebelum restart
        time.sleep(min(e.value, 3600))
    except Exception:
        log.exception("Manager Bot berhenti karena error.")
        sys.exit(1)
    finally:
        runner.stop_all()
        set_runner(None)
        if lock_file is not None:
            lock_file.close()
        log.info("Manager Bot offline.")


if __name__ == "__main__":
    main()