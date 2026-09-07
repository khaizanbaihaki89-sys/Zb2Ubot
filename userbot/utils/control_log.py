"""Audit log untuk aktivitas IBEKS Control Panel."""

from __future__ import annotations

import os
from datetime import datetime

from config import LOGS_DIR
from utils.logger import log


def record(action: str, detail: str = "") -> None:
    entry = (
        f"{datetime.now().astimezone().isoformat()} | "
        f"{action} | {detail}\n"
    )
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(
            os.path.join(LOGS_DIR, "control_panel.log"),
            "a",
            encoding="utf-8",
        ) as audit:
            audit.write(entry)
    except Exception:
        log.exception("[ControlPanel] Gagal menulis audit log.")
    log.info("[ControlPanel] %s %s", action, detail)