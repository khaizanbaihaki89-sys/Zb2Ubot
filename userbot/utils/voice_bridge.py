"""IPC Voice Chat entre um Userbot worker e o Manager Bot."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from config import VOICE_ACTION_PATH, VOICE_REQUEST_PATH, VOICE_RESPONSE_PATH
from utils.logger import log
from utils.voice_manager import voice_manager


POLL_INTERVAL = 0.25
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


def request_voice_panel(
    *,
    group_chat_id: int,
    user_id: int,
    room: str,
    success: bool,
    reason: str = "",
) -> None:
    """Publica o resultado do join para o Manager sem enviar mensagem ao grupo."""
    _atomic_write(
        Path(VOICE_REQUEST_PATH),
        {
            "group_chat_id": int(group_chat_id),
            "user_id": int(user_id),
            "room": room or "Unknown",
            "success": bool(success),
            "reason": reason or "",
        },
    )


async def _room_name(client, chat_id: int) -> str:
    try:
        chat = await client.get_chat(chat_id)
        return chat.title or chat.first_name or chat.username or str(chat_id)
    except Exception as exc:
        log.warning("[Voice] Gagal membaca nama room %s: %s", chat_id, exc)
        return str(chat_id)


def _is_connected(chat_id: int) -> bool:
    return voice_manager.is_connected(chat_id)


def _write_response(
    *,
    user_id: int,
    group_chat_id: int,
    message_id: int,
    action: str,
    connected: bool,
    room: str,
    reason: str = "",
    mic_muted: bool | None = None,
) -> None:
    payload = {
        "user_id": int(user_id),
        "group_chat_id": int(group_chat_id),
        "message_id": int(message_id),
        "action": action,
        "connected": bool(connected),
        "room": room,
        "reason": reason or "",
    }
    if mic_muted is not None:
        payload["mic_muted"] = bool(mic_muted)
    _atomic_write(Path(VOICE_RESPONSE_PATH), payload)


async def _handle_action(client, payload: dict) -> None:
    action = str(payload.get("action") or "")
    user_id = int(payload["user_id"])
    group_chat_id = int(payload["group_chat_id"])
    message_id = int(payload["message_id"])
    room = await _room_name(client, group_chat_id)

    if action == "onmic":
        success, text = await voice_manager.set_mute(group_chat_id, muted=False)
        _write_response(
            user_id=user_id,
            group_chat_id=group_chat_id,
            message_id=message_id,
            action=action,
            connected=_is_connected(group_chat_id),
            room=room,
            reason="" if success else text,
            mic_muted=False if success else None,
        )
    elif action == "offmic":
        success, text = await voice_manager.set_mute(group_chat_id, muted=True)
        _write_response(
            user_id=user_id,
            group_chat_id=group_chat_id,
            message_id=message_id,
            action=action,
            connected=_is_connected(group_chat_id),
            room=room,
            reason="" if success else text,
            mic_muted=True if success else None,
        )
    elif action == "leave":
        success, text = await voice_manager.leave(group_chat_id)
        connected = _is_connected(group_chat_id)
        _write_response(
            user_id=user_id,
            group_chat_id=group_chat_id,
            message_id=message_id,
            action=action,
            connected=connected,
            room=room,
            reason="" if success else text,
        )
    elif action == "refresh":
        connected = _is_connected(group_chat_id)
        _write_response(
            user_id=user_id,
            group_chat_id=group_chat_id,
            message_id=message_id,
            action=action,
            connected=connected,
            room=room,
            reason="" if connected else "Userbot belum berada di Voice Chat.",
        )


async def _watch_actions(client) -> None:
    action_path = Path(VOICE_ACTION_PATH)
    while True:
        try:
            if client.is_connected and action_path.exists():
                try:
                    payload = json.loads(action_path.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError) as exc:
                    log.warning("[Voice] Action IPC inválido: %s", exc)
                    payload = None
                action_path.unlink(missing_ok=True)
                if payload:
                    try:
                        await _handle_action(client, payload)
                    except Exception as exc:
                        log.exception("[Voice] Ação %s falhou: %s", payload.get("action"), exc)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[Voice] Action watcher falhou; polling continua.")
        await asyncio.sleep(POLL_INTERVAL)


def start_voice_bridge(client) -> None:
    """Inicia o watcher de callbacks enviados pelo Manager Bot."""
    global _watcher_task
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = client.loop.create_task(_watch_actions(client))
    log.info("[Voice] Worker bridge ativo.")