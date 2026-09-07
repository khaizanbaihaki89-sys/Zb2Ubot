"""IPC panel Clone antara Userbot worker dan Bot Manager."""

from __future__ import annotations

import json
import os
import tempfile
import asyncio
from pathlib import Path

from config import CLONE_ACTION_PATH, CLONE_REQUEST_PATH, CLONE_RESPONSE_PATH
from utils.logger import log


def _atomic_write(path: Path, payload: dict) -> None:
    """Tulis payload secara atomik agar Manager tidak membaca JSON setengah."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temporary_file:
            json.dump(payload, temporary_file, ensure_ascii=False)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def request_clone_panel(*, user_id: int, target_name: str) -> None:
    """Minta Manager membuat atau memperbarui satu panel Clone."""
    _atomic_write(
        Path(CLONE_REQUEST_PATH),
        {
            "user_id": int(user_id),
            "target_name": target_name or "Tidak diketahui",
        },
    )


def _write_response(*, user_id: int, message_id: int, success: bool, detail: str = "") -> None:
    """Kirim hasil Restore ke Manager untuk memperbarui panel yang sama."""
    _atomic_write(
        Path(CLONE_RESPONSE_PATH),
        {
            "user_id": int(user_id),
            "message_id": int(message_id),
            "success": bool(success),
            "detail": detail or "",
        },
    )


async def _handle_action(client, payload: dict) -> None:
    action = str(payload.get("action") or "")
    if action != "restore":
        log.warning("[Clone] Action IPC tidak dikenal: %s", action)
        return

    user_id = int(payload["user_id"])
    message_id = int(payload["message_id"])
    try:
        # Import setelah plugin selesai dimuat untuk memakai fungsi Restore
        # yang sama dengan command .restore tanpa membuat import siklik.
        from plugins.fun.restore import restore_profile

        success, detail = await restore_profile(client)
        _write_response(
            user_id=user_id,
            message_id=message_id,
            success=success,
            detail=detail,
        )
    except Exception as exc:
        log.exception("[Clone] Restore dari panel gagal: %s", exc)
        _write_response(
            user_id=user_id,
            message_id=message_id,
            success=False,
            detail=str(exc).strip() or exc.__class__.__name__,
        )


async def _watch_actions(client) -> None:
    action_path = Path(CLONE_ACTION_PATH)
    while True:
        try:
            if client.is_connected and action_path.exists():
                try:
                    payload = json.loads(action_path.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError) as exc:
                    log.warning("[Clone] Action IPC invalid: %s", exc)
                    payload = None
                action_path.unlink(missing_ok=True)
                if payload:
                    await _handle_action(client, payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[Clone] Action watcher gagal; polling dilanjutkan.")
        await asyncio.sleep(0.25)


def start_clone_bridge(client) -> None:
    """Mulai watcher action Restore dari Bot Manager."""
    task = getattr(client, "_ibeks_clone_bridge_task", None)
    if task is None or task.done():
        client._ibeks_clone_bridge_task = client.loop.create_task(
            _watch_actions(client)
        )
    log.info("[Clone] Worker bridge aktif.")