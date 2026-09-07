"""
IBEKS USERBOT - Fun Tahap 8
Commands:
  .ctitit - laporan panjang, bentuk, kebersihan, dan keunggulan target reply
  .cmeki  - laporan ukuran, kebersihan, kelebihan, dan tier target reply

Hasil dibuat deterministik berdasarkan User ID target + minggu ISO berjalan.
Tidak memakai random global dan tidak membutuhkan database tambahan.
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


_CTITIT_LEVELS = (
    "Nano-Nano (2 cm): Baru disentuh angin langsung minder, butuh mikroskop buat ngecek.",
    "Standar Pabrik (10 cm): Lumayan buat pemula, tidak bikin kaget kalau sedang beraksi.",
    "Seukuran Jempol Kaki (15 cm): Pas di genggaman, andalan emak-emak pos ronda.",
    "Gede Tingkat Akhir (25 cm): Bikin celana jeans megap-megap, jalannya agak ngangkang.",
    "Panjang Sebelah (30 cm): Bentuknya misterius, masuknya harus dicicil dua kali.",
    "Mutan Antar Galaksi (50 cm+): Bisa dipakai buat galah jemuran atau todongan maling.",
)

_CTITIT_SHAPES = (
    "Bentuk Pisang Kepok: Melengkung estetis, arahnya belok ke kiri seperti mau belokan tol.",
    "Bentuk Huruf S: Bergelombang patah-patah, hasil karya seni jalan berlubang.",
    "Lurus Sempurna — Kayak Excalibur: Tegak perkasa, siap membelah lautan asmara.",
    "Bentuk Bumerang: Kalau dilempar bakal balik lagi ke kantong celana.",
    "Model Keris Semar Mesem: Ada lekukan keramat, bikin yang melihat langsung takzim.",
    "Bentuk Random Suka-Suka: Berubah bentuk tiap kena suhu dingin AC.",
)

_CTITIT_CLEANLINESS = (
    "Sarang Laba-Laba: Berdebu dan agak bau terasi basi, jarang dijamah sabun.",
    "Standar Mandi Kucing: Cuma dibilas air keran, handuknya pakai gorden.",
    "Cukup Wangi Downy: Habis direndam pewangi pakaian biar wangi mawar merah.",
    "Steril Sempurna — Klinik Dewa: Kinclong memantulkan cahaya ilahi.",
    "Wangi Parfum Laundry Kiloan: Aroma melati campur kimia gosong yang menyengat.",
    "Suci Tanpa Noda: Disucikan dengan air zamzam dan doa restu mertua.",
)

_CTITIT_ADVANTAGES = (
    "Spesialis Masuk-Masuk Keluar Cepat: Rekor MURI tiga detik langsung selesai.",
    "Anti Loyo Mode Hemat Baterai: Tahan banting meski begadang tiga hari tiga malam.",
    "Bisa Bergetar Sendiri: Karena faktor kedinginan atau kesurupan penunggu kasur.",
    "Auto Sange Akut: Efek halusinasi tingkat tinggi bagi yang melihat.",
    "Pawang Malam Jumat Kliwon: Kekuatannya meningkat 300% pas tengah malam.",
    "Pemersatu Bangsa Nasional: Sekali beraksi, grup WhatsApp langsung ribut.",
)

_CTITIT_TIERS = (
    "BEBAN CELANA: Cuma bikin berat di ongkos jahit kolor.",
    "KUCING GARONG KAMPUNG: Nongkrong di semak-semak, nyalinya ciut.",
    "SIGMA SOK KERAS: Gaya garang, diajak tempel langsung ngibrit.",
    "SULTAN SANGE: Hidupnya penuh kemewahan dunia malam.",
    "LEGENDARIS: Namanya dihafal para ciwi-ciwi kesepian se-kecamatan.",
    "DEWA PEMBUAT BENCANA: Bikin satu RT istighfar massal.",
)

_CMEKI_LEVELS = (
    "Seupil Semut (Sempit Banget): Ujung jari baru masuk langsung ngilu.",
    "Pas di Genggaman: Standar pabrik, tidak kekecilan dan tidak terlalu longgar.",
    "Cukup Buat Masukin Galon: Agak longgar, angin malam masuk bebas.",
    "Gedhe — Seukuran Pintu Tol: Bisa dipakai parkir kontainer Fuso.",
    "Tanpa Batas (Blackhole): Apa pun yang masuk tersedot ke dimensi lain.",
    "Luas Seluas Samudra Pasifik: Melempar lidi terasa seperti di lapangan bola.",
)

_CMEKI_CLEANLINESS = (
    "Berlumut Alami: Nuansa hutan tropis lengkap dengan embun pagi misterius.",
    "Higienis Maks — Klinik Dewa: Kinclong, wangi sabun bayi, dan steril.",
    "Bau-Bau Terasi Basi: Aromanya khas, bikin hidung bergetar hebat.",
    "Becek Berkabut: Lembap permanen walau sedang musim kemarau panjang.",
    "Lengket Manis Kayak Es Teler: Disentuh sedikit langsung nempel.",
    "Suci Berkilau: Disucikan dengan air zamzam dan doa para leluhur.",
)

_CMEKI_ADVANTAGES = (
    "Anti Licin-Licin Club: Cengkeramannya kuat seperti rem tangan truk batu bara.",
    "Longgar Banget — Angin Masuk Gratis: Sirkulasi udara jadi juara.",
    "Bisa Berbunyi Kayak Peluit: Gerak cepat mengeluarkan nada do-re-mi.",
    "Spesialis Bikin Ngilu Tulang Belakang: Sekali kedip lutut langsung lemas.",
    "Pawang Malam Jumat: Kekuatannya otomatis naik 500% tengah malam.",
    "Penyedot Debu Otomatis: Sekali sedot langsung bersih tanpa sisa.",
)

_CMEKI_TIERS = (
    "SEMPIT — MINTA AMPUN: Jalurnya ekstrem, bikin mikir dua kali.",
    "PAS — CUKUP NYAMAN: Standar aman untuk kalangan pemula.",
    "LONGGAR — ANGIN SEMILIR: Sensasi goyang sepoi-sepoi.",
    "LEBAR — KEBESARAN: Cuma bisa dilihatin sambil elus dada.",
    "GHOIB — TAK KASAT MATA: Wujudnya ada, dicari tidak ketemu.",
    "FINAL BOSS — BENCANA NASIONAL: Bikin satu tongkrongan tobat massal.",
)

_CTITIT_PERCENTAGES = (16, 33, 50, 66, 83, 100)
_CMEKI_PERCENTAGES = (10, 30, 50, 70, 90, 100)


def _week_key() -> str:
    """Kembalikan kunci minggu UTC agar hasil tidak berubah sampai minggu berikutnya."""
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _stable_indices(user_id: int, namespace: str, count: int = 6) -> list[int]:
    """Buat indeks stabil dari ID target dan minggu berjalan tanpa menyimpan state."""
    digest = hashlib.sha256(
        f"{namespace}:{user_id}:{_week_key()}".encode("utf-8")
    ).digest()
    return [
        int.from_bytes(digest[offset:offset + 4], "big") % count
        for offset in range(0, count * 4, 4)
    ]


def _progress(percent: int) -> str:
    """Buat progress bar enam segmen sesuai level Tahap 8."""
    filled = round(percent / 100 * 6)
    return f"{'▰' * filled}{'▱' * (6 - filled)} {percent}%"


def _display_name(user: User) -> str:
    name = " ".join(part for part in (user.first_name, user.last_name) if part)
    return name or user.username or "Unknown"


def _pick(values: Sequence[str], index: int) -> str:
    return values[index % len(values)]


def _ctitit_report(user: User) -> str:
    indices = _stable_indices(user.id, "ctitit")
    level = indices[0]
    body = (
        f"👤 Target : {_display_name(user)}\n"
        f"🆔 ID : {user.id}\n"
        f"📊 Rating : {_progress(_CTITIT_PERCENTAGES[level])}\n"
        f"🔖 Panjang : {_pick(_CTITIT_LEVELS, level)}\n"
        f"😈 Bentuk : {_pick(_CTITIT_SHAPES, indices[1])}\n"
        f"💖 Kebersihan : {_pick(_CTITIT_CLEANLINESS, indices[2])}\n"
        f"⭐ Keunggulan : {_pick(_CTITIT_ADVANTAGES, indices[3])}\n"
        f"🔞 Tier : {_pick(_CTITIT_TIERS, indices[4])}"
    )
    return format_ui(
        title="CEK TITIT",
        body=body,
        emoji="🔞",
        expandable=True,
    )


def _cmeki_report(user: User) -> str:
    indices = _stable_indices(user.id, "cmeki")
    level = indices[0]
    body = (
        f"👤 Target : {_display_name(user)}\n"
        f"🆔 ID : {user.id}\n"
        f"📊 Rating : {_progress(_CMEKI_PERCENTAGES[level])}\n"
        f"🔖 Ukuran Lobang : {_pick(_CMEKI_LEVELS, level)}\n"
        f"💖 Kebersihan : {_pick(_CMEKI_CLEANLINESS, indices[1])}\n"
        f"⭐ Kelebihan : {_pick(_CMEKI_ADVANTAGES, indices[2])}\n"
        f"😶 Tier : {_pick(_CMEKI_TIERS, indices[3])}"
    )
    return format_ui(
        title="CEK MEMEK",
        body=body,
        emoji="🔞",
        expandable=True,
    )


def setup(client):
    """Daftarkan hanya .ctitit dan .cmeki, keduanya wajib reply ke user."""

    async def _get_reply_target(message):
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await send_ui(
                client,
                message.chat.id,
                warning("CEK FUN", "👤 Target : Reply dulu ke user."),
            )
            return None
        return message.reply_to_message.from_user

    @client.on_message(dynamic_command("ctitit") & filters.me)
    async def cmd_ctitit(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        target = await _get_reply_target(message)
        if target:
            await send_ui(client, message.chat.id, _ctitit_report(target), expandable=True)

    @client.on_message(dynamic_command("cmeki") & filters.me)
    async def cmd_cmeki(client, message):
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        target = await _get_reply_target(message)
        if target:
            await send_ui(client, message.chat.id, _cmeki_report(target), expandable=True)