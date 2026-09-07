"""
IBEKS USERBOT - Plugin: Broadcast
Commands:
  .gcast <pesan> / .gcast (reply)
  .ucast <pesan> / .ucast (reply)
  .addbl
  .delbl
  .listbl
"""

import asyncio

from pyrogram import filters

from config import AUTO_DELETE_CMD
from db import add_blacklist, del_blacklist, is_blacklisted, list_blacklist
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error, format_ui, list_ui, success
from utils.broadcast import (
    broadcast_gcast,
    broadcast_ucast,
    format_broadcast_result,
    format_gcast_result,
    format_ucast_result,
)
from plugins.utils.ui import send_ui

def setup(client):
    """Daftarkan handler broadcast pada instance client."""

    @client.on_message(dynamic_command("gcast") & filters.me)
    async def cmd_gcast(client, message):
        """Handler command .gcast"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id
        reply = message.reply_to_message

        # Ambil konten: reply jika ada, atau teks setelah command
        text = None
        if reply:
            source = reply
        else:
            parts = (message.text or message.caption or "").split(maxsplit=1)
            if len(parts) < 2:
                await send_ui(
                    client,
                    chat_id,
                    error("GCAST", "Masukkan pesan atau reply ke sebuah pesan."),
                )
                return
            text = parts[1]
            source = None

        await send_ui(
            client,
            chat_id,
            format_ui("GCAST", "📌 Status : Sedang berjalan...", emoji="🔄"),
        )
        result = await broadcast_gcast(client, text=text, source_message=source)
        await send_ui(client, chat_id, format_gcast_result(result), expandable=True)

    @client.on_message(dynamic_command("ucast") & filters.me)
    async def cmd_ucast(client, message):
        """Handler command .ucast"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id
        reply = message.reply_to_message

        text = None
        if reply:
            source = reply
        else:
            parts = (message.text or message.caption or "").split(maxsplit=1)
            if len(parts) < 2:
                await send_ui(
                    client,
                    chat_id,
                    error("UCAST", "Masukkan pesan atau reply ke sebuah pesan."),
                )
                return
            text = parts[1]
            source = None

        await send_ui(
            client,
            chat_id,
            format_ui("UCAST", "📌 Status : Sedang berjalan...", emoji="🔄"),
        )
        result = await broadcast_ucast(client, text=text, source_message=source)
        await send_ui(client, chat_id, format_ucast_result(result), expandable=True)

    @client.on_message(dynamic_command("addbl") & filters.me)
    async def cmd_addbl(client, message):
        """Handler command .addbl"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id
        chat_title = message.chat.title or message.chat.first_name or "Unknown"

        if is_blacklisted(chat_id):
            await send_ui(
                client,
                chat_id,
                error("ADDBL", "Chat sudah ada di Blacklist."),
            )
            return

        add_blacklist(chat_id, chat_title)
        await send_ui(
            client,
            chat_id,
            success(
                "ADDBL",
                [
                    f"💬 Chat : {chat_title}",
                    "📌 Status : Berhasil ditambahkan ke Blacklist.",
                ],
            ),
        )

    @client.on_message(dynamic_command("delbl") & filters.me)
    async def cmd_delbl(client, message):
        """Handler command .delbl"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id
        if del_blacklist(chat_id):
            await send_ui(
                client,
                chat_id,
                success(
                    "DELBL",
                    [
                        f"🆔 Chat ID : <code>{chat_id}</code>",
                        "📌 Status : Berhasil dihapus dari Blacklist.",
                    ],
                ),
            )
        else:
            await send_ui(
                client,
                chat_id,
                error(
                    "DELBL",
                    [
                        f"🆔 Chat ID : <code>{chat_id}</code>",
                        "📌 Status : Chat tidak ditemukan di Blacklist.",
                    ],
                ),
            )

    @client.on_message(dynamic_command("listbl") & filters.me)
    async def cmd_listbl(client, message):
        """Handler command .listbl"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        chat_id = message.chat.id
        items = list_blacklist()
        if not items:
            await send_ui(
                client,
                chat_id,
                format_ui("BLACKLIST", "Tidak ada blacklist.", emoji="📋"),
            )
            return

        formatted_items = [
            f"{item['chat_title'] or 'Unknown'} (<code>{item['chat_id']}</code>)"
            for item in items
        ]
        await send_ui(
            client,
            chat_id,
            list_ui("BLACKLIST", formatted_items, emoji="📋"),
            expandable=True,
        )

