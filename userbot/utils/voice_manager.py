"""
IBEKS USERBOT - Voice Chat Manager
Mengelola instance PyTgCalls untuk join/leave/mute voice chat di grup/channel.
"""

import asyncio
import random
from typing import Optional, Dict

from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError, BadRequest, Forbidden
from pyrogram.raw import functions

try:
    from pytgcalls import GroupCallFactory
    from pytgcalls.exceptions import GroupCallNotFoundError, PytgcallsBaseException
    HAS_PYTGCALLS = True
except ImportError:
    GroupCallFactory = None
    class GroupCallNotFoundError(Exception): pass
    class PytgcallsBaseException(Exception): pass
    HAS_PYTGCALLS = False

from utils.logger import log


class VoiceManager:
    """Singleton-like manager untuk satu client Pyrogram."""

    def __init__(self):
        self.client: Optional[Client] = None
        self._factory: Optional[GroupCallFactory] = None
        # chat_id -> GroupCall instance
        self._calls: Dict[int, any] = {}

    def set_client(self, client: Client) -> None:
        """Inisialisasi factory setelah Pyrogram client tersedia."""
        self.client = client
        if HAS_PYTGCALLS and GroupCallFactory is not None:
            self._factory = GroupCallFactory(client)
        else:
            self._factory = None

    def _ensure_initialized(self) -> bool:
        """Pastikan factory memakai client utama sebelum command voice berjalan."""
        if self.client is None:
            return False
        if self._factory is None and HAS_PYTGCALLS and GroupCallFactory is not None:
            self._factory = GroupCallFactory(self.client)
        return self._factory is not None

    async def _create_group_call(self, chat_id: int) -> None:
        """Buat voice chat baru di chat via raw MTProto."""
        if not self.client:
            raise RuntimeError("Voice manager belum diinisialisasi.")

        peer = await self.client.resolve_peer(chat_id)
        await self.client.invoke(
            functions.phone.CreateGroupCall(
                peer=peer,
                random_id=random.randint(0, 0x7FFFFFFF),
                rtmp_stream=None,
            )
        )

    async def join(self, chat_id: int) -> tuple[bool, str]:
        """
        Bergabung ke voice chat. Jika belum ada, coba buat dulu.
        Return (success, message).
        """
        if not self._ensure_initialized():
            return False, "❌ Voice manager belum diinisialisasi."

        # Jika sudah join, laporkan status
        existing = self._calls.get(chat_id)
        if existing and getattr(existing, "is_connected", False):
            return True, "✅ Userbot sudah berada di Voice Chat."

        group_call = self._factory.get_group_call()

        try:
            await group_call.start(chat_id)
            self._calls[chat_id] = group_call
            return True, "✅ Berhasil bergabung ke Voice Chat."
        except GroupCallNotFoundError:
            # Belum ada voice chat; coba buat otomatis
            try:
                await self._create_group_call(chat_id)
            except FloodWait as exc:
                return False, f"❌ Terkena FloodWait saat membuat Voice Chat. Coba lagi dalam {exc.value} detik."
            except BadRequest as exc:
                return False, (
                    "❌ Gagal membuat Voice Chat.\n"
                    "Kemungkinan:\n"
                    "• Userbot bukan admin.\n"
                    "• Tidak memiliki izin Manage Voice Chat.\n"
                    f"• Telegram menolak permintaan. ({exc})"
                )
            except Forbidden as exc:
                return False, (
                    "❌ Gagal membuat Voice Chat.\n"
                    "Kemungkinan:\n"
                    "• Userbot bukan admin.\n"
                    "• Tidak memiliki izin Manage Voice Chat.\n"
                    f"• Telegram menolak permintaan. ({exc})"
                )
            except Exception as exc:
                return False, (
                    "❌ Gagal membuat Voice Chat.\n"
                    "Kemungkinan:\n"
                    "• Userbot bukan admin.\n"
                    "• Tidak memiliki izin Manage Voice Chat.\n"
                    f"• Telegram menolak permintaan. ({exc})"
                )

            # Tunggu Telegram menyebarluaskan update voice chat
            await asyncio.sleep(1.5)

            try:
                await group_call.start(chat_id)
            except GroupCallNotFoundError:
                return False, (
                    "❌ Gagal membuat Voice Chat.\n"
                    "Kemungkinan:\n"
                    "• Userbot bukan admin.\n"
                    "• Tidak memiliki izin Manage Voice Chat.\n"
                    "• Telegram menolak permintaan."
                )
            except Exception as exc:
                return False, f"❌ Gagal bergabung ke Voice Chat yang baru dibuat: {exc}"

            self._calls[chat_id] = group_call
            return True, "✅ Voice Chat berhasil dibuat.\n✅ Userbot berhasil bergabung."
        except FloodWait as exc:
            return False, f"❌ Terkena FloodWait. Coba lagi dalam {exc.value} detik."
        except Exception as exc:
            log.exception(f"[VoiceManager] Gagal join VC {chat_id}: {exc}")
            return False, f"❌ Gagal bergabung ke Voice Chat: {exc}"

    async def leave(self, chat_id: int) -> tuple[bool, str]:
        """Keluar dari voice chat."""
        group_call = self._calls.get(chat_id)
        if not group_call:
            return False, "❌ Userbot belum berada di Voice Chat."

        try:
            await group_call.stop()
        except Exception as exc:
            log.exception(f"[VoiceManager] Gagal leave VC {chat_id}: {exc}")
            return False, f"❌ Gagal keluar dari Voice Chat: {exc}"
        finally:
            self._calls.pop(chat_id, None)

        return True, "✅ Berhasil keluar dari Voice Chat."

    async def set_mute(self, chat_id: int, muted: bool) -> tuple[bool, str]:
        """Atur status mute mikrofon."""
        group_call = self._calls.get(chat_id)
        if not group_call:
            return False, "❌ Userbot belum berada di Voice Chat."

        try:
            await group_call.set_is_mute(muted)
        except Exception as exc:
            log.exception(f"[VoiceManager] Gagal set mute={muted} VC {chat_id}: {exc}")
            return False, f"❌ Gagal mengubah status mikrofon: {exc}"

        if muted:
            return True, "🔇 Mikrofon berhasil dimatikan."
        return True, "🎙 Mikrofon berhasil diaktifkan."

    def is_connected(self, chat_id: int) -> bool:
        """Kembalikan status koneção sem alterar o estado da chamada."""
        group_call = self._calls.get(chat_id)
        return bool(group_call and getattr(group_call, "is_connected", False))


voice_manager = VoiceManager()
