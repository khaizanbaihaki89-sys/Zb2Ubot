"""
IBEKS USERBOT - Plugin: Animasi
Commands:
  .ayang  - Animasi pesan ayang (1 bubble reply, edit bertahap)
  .gombal - Animasi pesan gombal (1 bubble reply, edit bertahap)
  .gembel - Animasi pesan gembel (1 bubble reply, edit bertahap)
  .prank  - Animasi pesan prank (1 bubble reply, edit bertahap)
  .ange   - Animasi pesan ange (1 bubble reply, edit bertahap)
  .vcc    - Animasi pesan vcc (1 bubble reply, edit bertahap)
  .desah  - Animasi pesan desah (1 bubble reply, edit bertahap)
  .pasrah - Animasi pesan pasrah (1 bubble reply, edit bertahap)
  .basah  - Animasi pesan basah (1 bubble reply, edit bertahap)
  .remes  - Animasi pesan remes (1 bubble reply, edit bertahap)
  .crot   - Animasi pesan crot (1 bubble reply, edit bertahap)
  .kasar  - Animasi pesan kasar (1 bubble reply, edit bertahap)
  .masukin - Animasi pesan masukin (1 bubble reply, edit bertahap)
  .genjot - Animasi pesan genjot (1 bubble reply, edit bertahap)
  .sempit - Animasi pesan sempit (1 bubble reply, edit bertahap)
  .masker - Animasi pesan masker (1 bubble reply, edit bertahap)
  .peluk  - Animasi pesan peluk (1 bubble reply, edit bertahap)

Sistem Animasi:
- Setiap command hanya menghasilkan 1 pesan/bubble dari bot.
- Pesan pertama dikirim sebagai REPLY ke pesan command user.
- Jeda 2.5 detik (non-blocking async sleep) antar tahap.
- Mengedit pesan bot yang sama secara berurutan.
- Tidak membuat bubble baru selama animasi.
- Penanganan FloodWait dan exception Telegram secara aman.
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import filters
from pyrogram.errors import FloodWait, MessageNotModified

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command

_AYANG_MESSAGES = (
    "aku kangen kamu 🥺",
    "pengen ketemu kamu 💗",
    "jangan lama-lama ya 🫶🏻",
)

_GOMBAL_MESSAGES = (
    "kamu cantik banget 🥰",
    "tapi ada yang kurang 😏",
    "kurang aku di samping kamu ❤️",
)

_GEMBEL_MESSAGES = (
    "aku nggak butuh banyak orang 🫶🏻",
    "cukup kamu 🥺",
    "yang selalu bikin nyaman ❤️",
)

_PRANK_MESSAGES = (
    "sebenarnya... 🥺",
    "aku suka kamu ❤️",
    "tapi.... 😏",
    "boong 🤣",
)

_ANGE_MESSAGES = (
    "sayang 🥺❤️",
    "ange... 😳💦",
    "picies yu... 🙈👉👈",
)

_VCC_MESSAGES = (
    "kesepian nih... 🥺🌙",
    "temenin yuk... 🔥",
    "vc yuk tapi gelap-gelapan... 🙈🔞",
)

_DESAH_MESSAGES = (
    "ahh... 💦",
    "jgn gitu dong... 🔥",
    "nanti aku ketagihan... 🤤❤️",
)

_PASRAH_MESSAGES = (
    "udah gak tahan... 🫠💦",
    "terserah kamu mau diapain... 🫣🔥",
    "yang penting pelan-pelan ya... 🙈🔞",
)

_BASAH_MESSAGES = (
    "aduhh udah banjir nih... 💦",
    "cepatan masukin... 🔥",
    "jgn kasih ampun ya... 🤤🔞",
)

_REMES_MESSAGES = (
    "tangan kamu nakal bgt... 🔥",
    "remes aja terus... 🤤💦",
    "ampe aku merintih... 🙈🔞",
)

_CROT_MESSAGES = (
    "bentar lagi mau keluar... 💦",
    "tahan dulu jgn dikeluarin... 🤫🔥",
    "didalam aja ya sayang... 🤤🔞",
    "ahhhh nikmat..🤪",
)

_KASAR_MESSAGES = (
    "jambak rambut aku... 🔥",
    "genjot yang keras... 💦",
    "bikin aku gak bisa jalan... 🤤🔞",
)

_MASUKIN_MESSAGES = (
    "basahin dulu ujungnya biar licin... 💦",
    "lubangnya kecil banget susah masuk... 🔥",
    "paksain dikit biar mentok... 🤤💥",
    "akhirnya benang bisa masuk ke jarum 🪡🧷",
)

_GENJOT_MESSAGES = (
    "genjotnya makin kenceng dong... 🔥",
    "aduh tenggorokan aku udah basah... 💦",
    "cape banget tapi ketagihan... 🤤💥",
    "gowes sore ini emang bikin lemes... 🚴‍♂️💨",
)

_SEMPIT_MESSAGES = (
    "aduh sempit banget susah masuknya... 🔥",
    "dorong dikit lagi dari belakang... 💦",
    "paksain dikit biar muat... 🤤💥",
    "celana jeans lama aku udah kekecilan... 👖😭",
)

_MASKER_MESSAGES = (
    "tempelin pas di tengah muka... ✨",
    "aduh dingin dan licin banget... 💦",
    "biarin nempel 15 menit sampe lemes... 🤤💥",
    "sheet mask-nya bikin kulit adem banget... 🎭😋",
)

_PELUK_MESSAGES = (
    "peluk erat-erat jangan dilepas... 🌙",
    "aduh empuk banget pas diusap... ✨",
    "nempel terus gak mau lepas... 🤤🔥",
    "guling kesayangan emang bikin mager bangun... 🛋️😴",
)

_ANIMATION_DELAY = 2.5


def _sudo_or_me():
    """Filter yang mengizinkan Owner bot dan user Sudo yang terdaftar."""
    async def filter_func(_, __, message):
        if not message:
            return False
        if message.outgoing:
            return True
        user = getattr(message, "from_user", None)
        if not user or not user.id:
            return False
        from plugins.permission.sudo import is_sudo
        return is_sudo(user.id)

    return filters.create(filter_func, "SudoOrMeAnimasiFilter")


async def _play_animation(
    client,
    message,
    stages: tuple[str, ...],
) -> None:
    """
    Jalankan animasi 1 bubble Telegram:
    1. Kirim pesan awal sebagai reply ke pesan command user.
    2. Tunggu 2.5 detik (non-blocking async sleep).
    3. Edit pesan bot yang sama untuk setiap tahap berikutnya.
    """
    if not stages:
        return

    bot_msg = None
    while True:
        try:
            bot_msg = await client.send_message(
                chat_id=message.chat.id,
                text=stages[0],
                reply_to_message_id=message.id,
            )
            break
        except FloodWait as fw:
            logging.warning(f"[Animasi] FloodWait terdeteksi saat kirim: tidur {fw.value}s")
            await asyncio.sleep(fw.value + 1)
        except Exception as exc:
            logging.exception(f"[Animasi] Gagal mengirim pesan reply animasi: {exc}")
            return

    if not bot_msg:
        return

    for text in stages[1:]:
        await asyncio.sleep(_ANIMATION_DELAY)
        while True:
            try:
                await bot_msg.edit_text(text)
                break
            except MessageNotModified:
                break
            except FloodWait as fw:
                logging.warning(f"[Animasi] FloodWait terdeteksi saat edit: tidur {fw.value}s")
                await asyncio.sleep(fw.value + 1)
            except Exception as exc:
                logging.warning(f"[Animasi] Gagal mengedit pesan animasi: {exc}")
                return


def setup(client):
    """Daftarkan handler command animasi."""

    @client.on_message(dynamic_command("ayang") & _sudo_or_me())
    async def cmd_ayang(client, message):
        """Handler command .ayang."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _AYANG_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .ayang: %s", exc)

    @client.on_message(dynamic_command("gombal") & _sudo_or_me())
    async def cmd_gombal(client, message):
        """Handler command .gombal."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _GOMBAL_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .gombal: %s", exc)

    @client.on_message(dynamic_command("gembel") & _sudo_or_me())
    async def cmd_gembel(client, message):
        """Handler command .gembel."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _GEMBEL_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .gembel: %s", exc)

    @client.on_message(dynamic_command("prank") & _sudo_or_me())
    async def cmd_prank(client, message):
        """Handler command .prank."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _PRANK_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .prank: %s", exc)

    @client.on_message(dynamic_command("ange") & _sudo_or_me())
    async def cmd_ange(client, message):
        """Handler command .ange."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _ANGE_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .ange: %s", exc)

    @client.on_message(dynamic_command("vcc") & _sudo_or_me())
    async def cmd_vcc(client, message):
        """Handler command .vcc."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _VCC_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .vcc: %s", exc)

    @client.on_message(dynamic_command("desah") & _sudo_or_me())
    async def cmd_desah(client, message):
        """Handler command .desah."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _DESAH_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .desah: %s", exc)

    @client.on_message(dynamic_command("pasrah") & _sudo_or_me())
    async def cmd_pasrah(client, message):
        """Handler command .pasrah."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _PASRAH_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .pasrah: %s", exc)

    @client.on_message(dynamic_command("basah") & _sudo_or_me())
    async def cmd_basah(client, message):
        """Handler command .basah."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _BASAH_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .basah: %s", exc)

    @client.on_message(dynamic_command("remes") & _sudo_or_me())
    async def cmd_remes(client, message):
        """Handler command .remes."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _REMES_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .remes: %s", exc)

    @client.on_message(dynamic_command("crot") & _sudo_or_me())
    async def cmd_crot(client, message):
        """Handler command .crot."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _CROT_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .crot: %s", exc)

    @client.on_message(dynamic_command("kasar") & _sudo_or_me())
    async def cmd_kasar(client, message):
        """Handler command .kasar."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _KASAR_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .kasar: %s", exc)

    @client.on_message(dynamic_command("masukin") & _sudo_or_me())
    async def cmd_masukin(client, message):
        """Handler command .masukin."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _MASUKIN_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .masukin: %s", exc)

    @client.on_message(dynamic_command("genjot") & _sudo_or_me())
    async def cmd_genjot(client, message):
        """Handler command .genjot."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _GENJOT_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .genjot: %s", exc)

    @client.on_message(dynamic_command("sempit") & _sudo_or_me())
    async def cmd_sempit(client, message):
        """Handler command .sempit."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _SEMPIT_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .sempit: %s", exc)

    @client.on_message(dynamic_command("masker") & _sudo_or_me())
    async def cmd_masker(client, message):
        """Handler command .masker."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _MASKER_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .masker: %s", exc)

    @client.on_message(dynamic_command("peluk") & _sudo_or_me())
    async def cmd_peluk(client, message):
        """Handler command .peluk."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        try:
            await _play_animation(client, message, _PELUK_MESSAGES)
        except Exception as exc:
            logging.exception("[Animasi] Gagal menjalankan .peluk: %s", exc)


