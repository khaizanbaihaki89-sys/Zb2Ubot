"""
IBEKS USERBOT - Logger
Setup logging terpusat menggunakan logging bawaan Python.
"""

import logging
import os
import sys
import warnings
from logging.handlers import RotatingFileHandler

from config import LOGS_DIR, BOT_NAME

# ── Buat direktori logs jika belum ada ────────────────────────────────────────
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOGS_DIR, "ibeks.log")

# ── Format log ────────────────────────────────────────────────────────────────
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger() -> logging.Logger:
    """Inisialisasi dan return logger utama."""
    logger = logging.getLogger(BOT_NAME)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Console handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # ── File handler (rotating, max 5MB, 3 backup) ────────────────────────────
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # ── Capture warning dari asyncio dan library lain ───────────────────────────
    warnings.filterwarnings("always")
    logging.captureWarnings(True)

    # ── Capture log dari Pyrogram dan library lain via root logger ────────────
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(file_handler)
        root.setLevel(logging.WARNING)
    else:
        # Pastikan file handler juga ada di root agar log pihak ketiga tersimpan
        has_file = any(isinstance(h, RotatingFileHandler) and h.baseFilename == LOG_FILE for h in root.handlers)
        if not has_file:
            root.addHandler(file_handler)

    # ── Logger Pyrogram khusus: turunkan level jika terlalu berisik ───────────
    pyrogram_logger = logging.getLogger("pyrogram")
    pyrogram_logger.setLevel(logging.WARNING)

    return logger


# ── Singleton logger ──────────────────────────────────────────────────────────
log = setup_logger()
