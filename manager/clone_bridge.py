"""Bridge panel Clone: Userbot meminta, Manager mengontrol Restore."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pyrogram import filters
from pyrogram.errors import RPCError
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import USERBOT_RUNTIME_DIR
from logger import log


POLL_INTERVAL = 0.25
CALLBACK_FILTER = filters.regex(r"^clone:restore:\d+$")


@dataclass
class ClonePanel:
    user_id: int
    message_id: int
    target_name: str
    pending: bool = False


_panels: dict[tuple[int, int], ClonePanel] = {}
_latest_panels: dict[int, tuple[int, int]] = {}
_watcher_task: asyncio.Task | None = None


def _atomic_write(path: Path, payload: dict) -> None:
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


def _read_payload(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        log.warning("[Clone] IPC invalid dari %s: %s", path, exc)
        return None


def _request_paths() -> list[Path]:
    if not USERBOT_RUNTIME_DIR.exists():
        return []
    return sorted(USERBOT_RUNTIME_DIR.glob("*/.clone_request.json"))


def _response_paths() -> list[Path]:
    if not USERBOT_RUNTIME_DIR.exists():
        return []
    return sorted(USERBOT_RUNTIME_DIR.glob("*/.clone_response.json"))


def _panel_text(panel: ClonePanel) -> str:
    if panel.pending:
        return (
            "👤 CLONE MODE\n\n"
            "♻️ Restore sedang diproses...\n\n"
            "⨱ IBEKS USERBOT ⨱"
        )
    if panel.target_name:
        return (
            "👤 CLONE MODE\n\n"
            "✅ Clone berhasil.\n\n"
            f"Target:\n{panel.target_name}\n\n"
            "⚠️ Akun sedang menggunakan mode clone.\n\n"
            "⨱ IBEKS USERBOT ⨱"
        )
    return (
        "👤 CLONE MODE\n\n"
        "✅ Restore berhasil.\n\n"
        "⨱ IBEKS USERBOT ⨱"
    )


def _keyboard(panel: ClonePanel) -> InlineKeyboardMarkup | None:
    if panel.pending or not panel.target_name:
        return None
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "♻️ Restore",
                callback_data=f"clone:restore:{panel.user_id}",
            )
        ]]
    )


async def _edit_panel(client, panel: ClonePanel) -> None:
    await client.edit_message_text(
        panel.user_id,
        panel.message_id,
        _panel_text(panel),
        reply_markup=_keyboard(panel),
    )


async def _send_or_update_panel(client, payload: dict) -> None:
    user_id = int(payload["user_id"])
    target_name = str(payload.get("target_name") or "Tidak diketahui")
    previous_key = _latest_panels.get(user_id)
    panel = _panels.get(previous_key) if previous_key else None

    if panel is not None:
        panel.target_name = target_name
        panel.pending = False
        try:
            await _edit_panel(client, panel)
            return
        except RPCError:
            _panels.pop(previous_key, None)
            _latest_panels.pop(user_id, None)

    panel = ClonePanel(user_id=user_id, message_id=0, target_name=target_name)
    message = await client.send_message(
        user_id,
        _panel_text(panel),
        reply_markup=_keyboard(panel),
    )
    panel.message_id = message.id
    key = (user_id, message.id)
    _panels[key] = panel
    _latest_panels[user_id] = key
    log.info("[Clone] Panel terkirim user_id=%s message_id=%s.", user_id, message.id)


async def _apply_response(client, payload: dict) -> None:
    user_id = int(payload["user_id"])
    message_id = int(payload.get("message_id") or 0)
    panel = _panels.get((user_id, message_id))
    if panel is None:
        log.warning("[Clone] Response tanpa panel user_id=%s.", user_id)
        return

    success = bool(payload.get("success"))
    detail = str(payload.get("detail") or "")
    panel.pending = False
    if success:
        panel.target_name = ""
    else:
        panel.target_name = panel.target_name or "Tidak diketahui"
        panel.pending = False

    text = _panel_text(panel)
    if not success:
        text = (
            "👤 CLONE MODE\n\n"
            f"❌ Restore gagal.\n\n{detail}\n\n"
            "⨱ IBEKS USERBOT ⨱"
        )
    await client.edit_message_text(
        panel.user_id,
        panel.message_id,
        text,
        reply_markup=_keyboard(panel),
    )


async def _handle_callback(client, query) -> None:
    message = query.message
    if not message:
        return
    try:
        _prefix, _action, raw_user_id = (query.data or "").split(":", 2)
        user_id = int(raw_user_id)
    except (ValueError, AttributeError):
        await query.answer("Aksi Clone tidak valid.", show_alert=True)
        return

    if query.from_user is None or int(query.from_user.id) != user_id:
        await query.answer("Panel ini bukan milik Anda.", show_alert=True)
        return

    panel = _panels.get((user_id, message.id))
    if panel is None:
        await query.answer("Panel Clone sudah kedaluwarsa.", show_alert=True)
        return
    if panel.pending or not panel.target_name:
        await query.answer("Panel Clone sudah diproses.", show_alert=True)
        return

    panel.pending = True
    await _edit_panel(client, panel)
    _atomic_write(
        USERBOT_RUNTIME_DIR / str(user_id) / ".clone_action.json",
        {
            "action": "restore",
            "user_id": user_id,
            "message_id": panel.message_id,
        },
    )
    await query.answer("Restore sedang diproses.")


async def _watch_requests(client) -> None:
    while True:
        try:
            if client.is_connected:
                for path in _request_paths():
                    payload = _read_payload(path)
                    path.unlink(missing_ok=True)
                    if payload is None:
                        continue
                    try:
                        await _send_or_update_panel(client, payload)
                    except Exception:
                        log.exception("[Clone] Gagal mengirim atau memperbarui panel.")

                for path in _response_paths():
                    payload = _read_payload(path)
                    path.unlink(missing_ok=True)
                    if payload is None:
                        continue
                    try:
                        await _apply_response(client, payload)
                    except Exception:
                        log.exception("[Clone] Gagal memperbarui hasil Restore.")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[Clone] Watcher IPC gagal; polling dilanjutkan.")
        await asyncio.sleep(POLL_INTERVAL)


def start_clone_bridge(client) -> None:
    """Daftarkan callback dan watcher panel Clone pada Manager."""
    global _watcher_task
    client.add_handler(CallbackQueryHandler(_handle_callback, CALLBACK_FILTER))
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = client.loop.create_task(_watch_requests(client))
    log.info("[Clone] Bridge BOT_TOKEN aktif; panel dan callback siap.")