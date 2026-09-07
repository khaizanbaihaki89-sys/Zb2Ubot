"""
IBEKS USERBOT - Fun Tahap 7
Commands:
  .cnenen - laporan ukuran, bentuk, keindahan, dan tier target reply
  .cange  - laporan aura, modus, keunggulan, dan tier target reply

Semua hasil deterministik berdasarkan User ID target + minggu ISO berjalan.
"""

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Sequence

from pyrogram import filters
from pyrogram.types import User

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui, warning
from plugins.utils.ui import send_ui


_CNENEN_SIZE = (
    "Cup A (Nasi KPC): Setara nasi kucing porsi ekonomis, mini size tapi bikin nagih.",
    "Cup B (Bakpao Coklat): Empuk, bulat sempurna, siap dikukus hangat di segala suasana.",
    "Cup C (Bantal Sofa): Ukuran ideal buat sandaran, bikin betah berlama-lama tanpa pegal.",
    "Cup D (Galon Le Minerale): Bukan cuma haus, tapi bisa bikin banjir satu ruangan kalau tumpah.",
    "Cup E (Gunung Merapi): Siap meletus kapan saja, skala bahaya tinggi dan bikin panik warga.",
    "Cup L (Tsunami Ghoib): Ukuran di luar nalar manusia, hanya bisa dilihat oleh mereka yang beriman.",
)

_CNENEN_SHAPE = (
    "Bentuk A (Adonan Mendoan): Masih lembek, hangat, dan butuh kasih sayang biar makin krispi.",
    "Bentuk B (Jelly Nutrijell): Terlalu kenyal, kena angin sepoi-sepoi langsung goyang inul.",
    "Bentuk C (Karah-Karah): Bergelombang layaknya rintangan offroad, menantang nyali para petualang.",
    "Bentuk D (Geometris): Sudut 90 derajat, presisi tingkat dewa seperti hasil ukur jangka sorong.",
    "Bentuk E (Random): Mengikuti arah angin, tidak bisa diprediksi ilmuwan atau dukun mana pun.",
    "Bentuk L (Paradoks Ghoib): Wujudnya bisa berubah kalau disentuh orang yang banyak dosa.",
)

_CNENEN_BEAUTY = (
    "Keindahan A (Low Budget): Sederhana, apa adanya, yang penting berfungsi sesuai fungsi dasarnya.",
    "Keindahan B (Seni Abstrak): Butuh kursus estetika tiga tahun untuk memahami maknanya.",
    "Keindahan C (High Definition 8K): Terlihat pori-porinya sampai menembus jiwa terdalam.",
    "Keindahan D (Efek CGI): Terlalu bagus untuk jadi nyata, bikin curiga ini hasil editan AI.",
    "Keindahan E (Silau Menyilaukan): Butuh kacamata hitam polarized untuk menatapnya.",
    "Keindahan L (Wujud Hologram): Indahnya bukan main, cuma terlihat dengan mata batin dan doa.",
)

_CNENEN_TIER = (
    "Tier A (KOCING OREN): Agresif, liar, dan bikin panik penghuni rumah setiap saat.",
    "Tier B (BPJS - Badan Penuh Janji Surga): Menjanjikan ketenangan, realitanya bikin darah tinggi.",
    "Tier C (TUKANG KEBUN): Tiap melihat, bawaannya ingin menyiram pakai air mata.",
    "Tier D (KELAS KAKAP): Hanya sultan yang sanggup menghadapi tantangan dan pajaknya.",
    "Tier E (MITOS NUSANTARA): Sering dibicarakan, tapi belum ada yang melihat wujud aslinya.",
    "Tier L (DEWA KEKACAUAN): Membuat dukun dan ilmuwan pensiun dini.",
)

_CANGE_AURA = (
    "Adem Ayem: Kelihatan suci, padahal isi kepalanya random.",
    "Hangat Kuku: Ada getaran halus, tapi masih bisa ditahan pakai wudhu.",
    "Penyebab Global Warming: Bikin sekitar ikut gerah dan salah tingkah.",
    "Manas Berat: AC kamar sudah 16°C tapi tetap keringetan.",
    "Bahaya Laten: Terlihat tenang, aslinya siap meledak kapan saja.",
    "Titik Didih 100°C: Uapnya ke mana-mana, butuh disiram air es.",
)

_CANGE_MODUS = (
    'Taktik "Kangen Jam 12 Malam": Tiba-tiba chat bilang, "aku ange".',
    "Spam Emoji 👀 & 🥵: Mancing reaksi tanpa harus mengetik banyak kata.",
    "Chat Late Night — Jam 2 Pagi: Akal sehat kalah sama gabut.",
    "Alibi pura-pura ngajak nobar drakor, tapi filmnya belok sendiri.",
    "Balas Story Sambil Gombal: Story receh, arah obrolan langsung sesat.",
    "Pura-pura Salah Kirim Foto: Klasik, buram estetik tapi framing-nya niat.",
)

_CANGE_ADVANTAGE = (
    "Spesialis Ngaret Waktu Chat: Malam secepat kilat, siang baru centang dua.",
    "Master of Double Meaning: Bicara makanan, konotasinya ke mana-mana.",
    "Spesialis Chat Penuh Kode: Jago menyelipkan kode di obrolan santai.",
    "Ahli Bikin Baper Berjamaah: Sekali reply story bikin target salah tingkah.",
    "Pawang Jam Rawan: Aktif pukul 1 sampai 4 pagi demi mengejar gebetan.",
    "Pakar Alibi Tingkat Tinggi: Punya alasan logis untuk tindakan mencurigakan.",
)

_CANGE_TIER = (
    "NPC (Non-Player Character): Lempeng, tidak tahu apa-apa soal dunia malam.",
    "BOCIL LAYAR HP: Nonton yang aneh-aneh, ketemu langsung salah tingkah.",
    "SIGMA LOKAL: Sok cool di luar, menyimpan seribu kegabutan di galeri.",
    "SULTAN GABUT: Rajin reply story orang untuk mencari mangsa obrolan.",
    "FREAK — Sange Brutal: Folder hidden penuh hal-hal misterius.",
    "FINAL BOSS GHOIB: Sekali muncul langsung merusak mental satu grup.",
)


def _week_key() -> str:
    """Kunci waktu mingguan yang sama untuk semua user selama satu minggu."""
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _stable_values(user_id: int, namespace: str, count: int) -> list[int]:
    """Ambil indeks deterministik tanpa menyimpan state atau memakai random global."""
    digest = hashlib.sha256(f"{namespace}:{user_id}:{_week_key()}".encode()).digest()
    return [int.from_bytes(digest[index:index + 4], "big") % count for index in range(0, count * 4, 4)]


def _progress(percent: int) -> str:
    filled = round(percent / 10)
    return f"{'▰' * filled}{'▱' * (10 - filled)} {percent}%"


def _name(user: User) -> str:
    full_name = " ".join(part for part in (user.first_name, user.last_name) if part)
    return full_name or user.username or "Unknown"


def _pick(items: Sequence[str], index: int) -> str:
    return items[index % len(items)]


def _report_cnenen(user: User) -> str:
    values = _stable_values(user.id, "cnenen", 5)
    level = values[0] + 1
    percent = level * 20
    # The final (L) descriptions remain available as a rare weekly variation.
    l_variant = values[1] == 0 and level == 5
    index = 5 if l_variant else level - 1
    body = (
        f"👤 Target : {_name(user)}\n"
        f"🆔 ID : {user.id}\n"
        f"📊 Level : {_progress(percent)}\n"
        f"🔖 Ukuran : {_pick(_CNENEN_SIZE, index)}\n"
        f"💖 Bentuk : {_pick(_CNENEN_SHAPE, index)}\n"
        f"✨ Keindahan : {_pick(_CNENEN_BEAUTY, index)}\n"
        f"👑 Tier : {_pick(_CNENEN_TIER, index)}"
    )
    return format_ui(
        title="CEK NENEN",
        body=body,
        emoji="🔞",
        expandable=True,
    )


def _report_cange(user: User) -> str:
    values = _stable_values(user.id, "cange", 6)
    level = values[0] + 1
    percent = (16, 33, 50, 66, 83, 100)[level - 1]
    body = (
        f"👤 Target : {_name(user)}\n"
        f"🆔 ID : {user.id}\n"
        f"📊 Level Sange : {_progress(percent)}\n"
        f"🔥 Aura : {_pick(_CANGE_AURA, values[1])}\n"
        f"💣 Modus : {_pick(_CANGE_MODUS, values[2])}\n"
        f"💖 Keunggulan : {_pick(_CANGE_ADVANTAGE, values[3])}\n"
        f"😈 Tier : {_pick(_CANGE_TIER, values[4])}"
    )
    return format_ui(
        title="CEK SANGE",
        body=body,
        emoji="🔞",
        expandable=True,
    )


def setup(client):
    """Daftarkan tepat dua command Tahap 7, keduanya wajib berupa reply."""

    async def _target_or_prompt(message):
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await send_ui(
                client,
                message.chat.id,
                warning("CEK FUN", "👤 Target : Reply dulu ke user."),
            )
            return None
        return message.reply_to_message.from_user

    @client.on_message(dynamic_command("cnenen") & filters.me)
    async def cmd_cnenen(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        target = await _target_or_prompt(message)
        if target:
            await send_ui(client, message.chat.id, _report_cnenen(target), expandable=True)

    @client.on_message(dynamic_command("cange") & filters.me)
    async def cmd_cange(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        target = await _target_or_prompt(message)
        if target:
            await send_ui(client, message.chat.id, _report_cange(target), expandable=True)