"""Registration entry point for the .panel command."""

from __future__ import annotations

import asyncio

from pyrogram import filters

try:
    from config import AUTO_DELETE_CMD
except (ImportError, AttributeError):
    AUTO_DELETE_CMD = 5

from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.panel_request import request_panel
from utils.prefix_manager import get_prefix


_registered_clients = set()


def register(client) -> None:
    client_id = id(client)
    if client_id in _registered_clients:
        return
    _registered_clients.add(client_id)

    @client.on_message(dynamic_command("panel") & filters.me)
    async def panel_command(_client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        owner_user = await _client.get_me()
        owner_name = owner_user.first_name or owner_user.username or str(owner_user.id)
        request_panel(
            chat_id=message.chat.id,
            user_id=owner_user.id,
            owner=owner_name,
            prefix=get_prefix(),
        )
