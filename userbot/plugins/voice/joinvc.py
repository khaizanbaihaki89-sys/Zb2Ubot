"""IBEKS USERBOT - Plugin: Voice Chat - Join VC."""

from pyrogram import filters

from utils.filters import dynamic_command
from utils.voice_bridge import request_voice_panel
from utils.voice_manager import voice_manager


def setup(client):
    """Daftarkan handler .joinvc."""
    voice_manager.set_client(client)

    @client.on_message(dynamic_command("joinvc") & filters.me)
    async def cmd_joinvc(client, message):
        chat_id = message.chat.id
        owner = await client.get_me()

        # O comando nunca deixa status no grupo; o resultado vai ao Manager.
        try:
            await message.delete()
        except Exception:
            pass

        success, text = await voice_manager.join(chat_id)
        try:
            chat = await client.get_chat(chat_id)
            room = chat.title or chat.first_name or chat.username or str(chat_id)
        except Exception:
            room = str(chat_id)
        request_voice_panel(
            group_chat_id=chat_id,
            user_id=owner.id,
            room=room,
            success=success,
            reason="" if success else text,
        )
