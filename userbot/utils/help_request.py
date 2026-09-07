"""IPC lokal Userbot -> Manager Bot untuk perintah .help."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from config import HELP_REQUEST_PATH


REQUEST_PATH = Path(HELP_REQUEST_PATH)


def request_help(*, chat_id: int, user_id: int, owner: str, prefix: str) -> None:
    """Tulis request Help secara atomik agar Manager tidak membaca setengah file."""
    payload = {
        "chat_id": int(chat_id),
        "user_id": int(user_id),
        "owner": owner or str(user_id),
        "prefix": prefix or ".",
    }
    REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=".help_request.",
        suffix=".tmp",
        dir=REQUEST_PATH.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temporary_file:
            json.dump(payload, temporary_file, ensure_ascii=False)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, REQUEST_PATH)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass