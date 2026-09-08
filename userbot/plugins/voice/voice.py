"""
IBEKS USERBOT - Plugin: Voice Clone / TTS
Command handler utama untuk .voice (add, list, delete, dan sintesis VN) berbasis Fish Audio.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any

from pyrogram import filters
from pyrogram.types import Message

import config
from plugins.utils.ui import send_ui
from plugins.voice.audio import validate_and_convert_sample
from plugins.voice.config import (
    RECOMMENDED_MAX_DURATION,
    RECOMMENDED_MIN_DURATION,
    TTS_MODEL,
)
from plugins.voice.profiles import (
    add_sample_to_profile,
    delete_profile,
    get_profile,
    list_profiles,
    sanitize_profile_name,
)
from plugins.voice.tts import (
    ACCENT_LABELS,
    detect_intonation,
    generate_speech,
    get_voice_diagnostic,
)
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui, list_ui, error, success
from utils.logger import log

__version__ = "1.1.0"
__author__ = "IBEKS"

ACCENT_KEYWORDS = tuple(ACCENT_LABELS)


def parse_voice_request(args_str: str) -> tuple[str, str, str]:
    """Parse `.voice <nama> [aksen] <teks>` tanpa mengganggu command lama."""
    parts = str(args_str or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return (parts[0] if parts else "", "normal", "")

    profile_name, remaining = parts
    text_parts = remaining.split(maxsplit=1)
    if len(text_parts) == 2 and text_parts[0].lower() in ACCENT_KEYWORDS:
        return profile_name, text_parts[0].lower(), text_parts[1].strip()
    return profile_name, "normal", remaining.strip()


def _tts_info_text(subcommand: str) -> tuple[str, str]:
    """Kembalikan judul dan isi bantuan TTS."""
    if subcommand == "aksen":
        body = "\n".join(
            f"{index}. {ACCENT_LABELS[key]}"
            for index, key in enumerate(ACCENT_KEYWORDS, start=1)
        )
        return "DAFTAR AKSEN / GAYA SUARA", f"🎙️ DAFTAR AKSEN / GAYA SUARA\n\n{body}"

    if subcommand == "emosi":
        body = (
            "🎭 OTOMATIS INTONASI\n\n"
            "!!! → Marah / Tegas\n"
            "!! → Antusias / Senang\n"
            "... → Sedih / Kecewa\n"
            "?! / !? → Kaget\n"
            "?? → Bingung / Ragu\n"
            "~ → Lembut / Santai\n"
            "KAPITAL + !!! → Teriak / Sangat Tegas\n"
            ". → Berhenti / Akhir Kalimat\n"
            ", → Jeda Napas\n"
            "Tanpa tanda khusus → Normal"
        )
        return "OTOMATIS INTONASI", body

    return (
        "TTS",
        "🎙️ Bantuan TTS\n\n"
        "• .tts aksen - Daftar aksen / gaya suara\n"
        "• .tts emosi - Daftar deteksi intonasi otomatis",
    )


async def _notify_manager(client: Any, text: str) -> None:
    """Kirim notifikasi status atau error Voice Clone hanya ke Manager Bot."""
    mgr_id = getattr(config, "MANAGER_BOT_ID", None)
    if not mgr_id:
        log.warning("[VoicePlugin] MANAGER_BOT_ID tidak tersedia. Status: %s", text)
        return
    try:
        await client.send_message(mgr_id, text)
        log.info("[VoicePlugin] Status Voice terkirim ke Manager Bot: %s", text)
    except Exception as exc:
        log.error("[VoicePlugin] Gagal kirim notifikasi ke Manager Bot (%s): %s", mgr_id, exc)


def _extract_sender_name(replied: Message) -> str | None:
    """
    Ambil nama pengirim dari pesan media yang di-reply.
    Mengutamakan nama user asli (first_name, atau first_name + last_name, atau username).
    """
    raw_name = ""
    if replied.from_user:
        first = (replied.from_user.first_name or "").strip()
        last = (replied.from_user.last_name or "").strip()
        user_name = (replied.from_user.username or "").strip()
        if first:
            raw_name = f"{first} {last}".strip() if last else first
        elif user_name:
            raw_name = user_name
    elif getattr(replied, "forward_from", None):
        first = (replied.forward_from.first_name or "").strip()
        last = (replied.forward_from.last_name or "").strip()
        user_name = (replied.forward_from.username or "").strip()
        if first:
            raw_name = f"{first} {last}".strip() if last else first
        elif user_name:
            raw_name = user_name
    elif getattr(replied, "forward_sender_name", None):
        raw_name = (replied.forward_sender_name or "").strip()
    elif getattr(replied, "sender_chat", None) and replied.sender_chat.title:
        raw_name = replied.sender_chat.title.strip()
    elif getattr(replied, "forward_from_chat", None) and replied.forward_from_chat.title:
        raw_name = replied.forward_from_chat.title.strip()

    raw_name = raw_name.strip()
    if not raw_name:
        return None

    slug = sanitize_profile_name(raw_name)
    if not slug or slug == "default_voice":
        return None

    return raw_name


async def _process_voice_add(client: Any, sender_name: str, replied_msg: Message) -> None:
    """Jalankan proses download, validasi, dan penambahan sample ke profil suara di background."""
    temp_dl = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
    temp_dl.close()
    temp_dl_path = temp_dl.name

    temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_wav.close()
    temp_wav_path = temp_wav.name

    try:
        downloaded = await client.download_media(replied_msg, file_name=temp_dl_path)
        if not downloaded or not os.path.exists(temp_dl_path):
            await _notify_manager(
                client,
                f"❌ **[Voice Clone] Gagal:** Tidak dapat mengunduh media audio (Profil: `{sender_name}`)."
            )
            return

        # Validasi dan konversi audio (durasi, dB level, clipping/noise)
        ok, val_msg, dur = validate_and_convert_sample(temp_dl_path, temp_wav_path)
        if not ok:
            await _notify_manager(
                client,
                f"❌ **[Voice Clone] Sample Ditolak (`{sender_name}`):** {val_msg} (Durasi: `{dur:.1f}s`)"
            )
            return

        # Simpan sample ke profil
        ok_add, add_msg, profile_data = add_sample_to_profile(sender_name, temp_wav_path, dur)
        if not ok_add or not profile_data:
            await _notify_manager(
                client,
                f"❌ **[Voice Clone] Gagal menyimpan voice `{sender_name}`:** {add_msg}"
            )
            return

        # Berhasil: kirim status singkat hanya ke Manager Bot
        await _notify_manager(
            client,
            f"🎙️ **[Voice Clone]** Voice `{sender_name}` berhasil disimpan."
        )
    except Exception as exc:
        log.error("[VoicePlugin] Exception saat memproses .voice add: %s", exc)
        await _notify_manager(
            client,
            f"❌ **[Voice Clone] Terjadi kesalahan saat memproses voice `{sender_name}`:** {exc}"
        )
    finally:
        if os.path.exists(temp_dl_path):
            try:
                os.remove(temp_dl_path)
            except Exception:
                pass
        if os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except Exception:
                pass


def setup(client: Any) -> None:
    """Daftarkan seluruh handler command .voice dan .voiceadd."""

    @client.on_message(dynamic_command("voice", "voiceadd") & filters.me)
    async def cmd_voice_handler(client, message: Message):
        text = (message.text or message.caption or "").strip()
        parts = text.split(maxsplit=1)
        raw_cmd = parts[0].strip() if parts else ""
        args_str = parts[1].strip() if len(parts) > 1 else ""

        # ── Handler Khusus .voiceadd ─────────────────────────────────────────
        # Mendukung Mode 1 (.voiceadd tanpa nama) & Mode 2 (.voiceadd <nama>)
        if "voiceadd" in raw_cmd.lower():
            try:
                await message.delete()
            except Exception:
                pass

            replied = message.reply_to_message
            if not replied or not (replied.voice or replied.audio or replied.video_note or replied.document):
                await _notify_manager(
                    client,
                    "❌ **[Voice Clone] Gagal:** Command `.voiceadd` wajib me-reply pesan Voice Note atau Audio."
                )
                return

            if args_str:
                # Mode 2: Menggunakan nama manual yang diberikan user (seluruh teks setelah command)
                target_name = args_str.strip()
            else:
                # Mode 1: Mekanisme lama menggunakan nama pengirim voice yang di-reply
                target_name = _extract_sender_name(replied)

            if not target_name:
                await _notify_manager(
                    client,
                    "❌ **[Voice Clone] Gagal:** Tidak dapat memperoleh nama pengirim dari pesan yang di-reply."
                )
                return

            asyncio.create_task(_process_voice_add(client, target_name, replied))
            return

        # Bantuan / Help Menu jika tanpa argumen
        if not args_str:
            asyncio.create_task(auto_delete(message, delay=getattr(config, "AUTO_DELETE_CMD", 0), force=True))
            body = (
                "📖 Perintah Tersedia:\n"
                "• .voice add [nama] : Tambah sample suara (Wajib reply VN/Audio)\n"
                "• .voiceadd [nama] : Tambah sample suara (Wajib reply VN/Audio)\n"
                "• .voice <Nama> <teks> : Generate VN dengan profil suara\n"
                "• .voice <Nama> <aksen> <teks> : Generate VN dengan aksen opsional\n"
                "• .voice list : Lihat daftar profil suara tersimpan\n"
                "• .voice delete <Nama> : Hapus profil suara\n"
                "• .voice diag : Cek status & koneksi Fish Audio API\n\n"
                "• .tts aksen : Daftar aksen yang tersedia\n"
                "• .tts emosi : Daftar intonasi otomatis\n\n"
                "💡 Standar Sample Suara (Fish Audio):\n"
                f"• Model : {TTS_MODEL}\n"
                "• Minimal : 5 detik suara vokal jelas\n"
                f"• Rekomendasi : {RECOMMENDED_MIN_DURATION:.0f}–{RECOMMENDED_MAX_DURATION:.0f} detik jernih & tanpa noise"
            )
            help_text = format_ui(
                title="FISH AUDIO VOICE CLONE & TTS",
                body=body,
                emoji="🎙️",
                expandable=True,
            )
            await send_ui(client, message.chat.id, help_text, expandable=True)
            return

        cmd_lower = args_str.lower().strip()

        # ── 0. .voice diag / status ──────────────────────────────────────────
        if cmd_lower in ("diag", "status", "check"):
            asyncio.create_task(auto_delete(message, delay=getattr(config, "AUTO_DELETE_CMD", 0), force=True))
            diag_info = get_voice_diagnostic()
            k_status = "🟢 Ditemukan" if diag_info.get("key_found") else "🔴 Tidak Ditemukan"
            m_key = diag_info.get("masked_key", "None")
            api_stat = diag_info.get("status", "Unknown")
            model_name = diag_info.get("model", TTS_MODEL)
            body = (
                "🔑 Status API Key:\n"
                f"• Environment Key : {k_status}\n"
                f"• Key Masked : {m_key}\n"
                f"• Model TTS : {model_name}\n\n"
                "🌐 Endpoint Resmi Fish Audio:\n"
                "• Clone : POST /model\n"
                "• Synthesis : POST /v1/tts\n"
                "• Delete : DELETE /model/{id}\n\n"
                f"📡 Koneksi & Permission : {api_stat}"
            )
            diag_text = format_ui(
                title="DIAGNOSTIK FISH AUDIO VOICE",
                body=body,
                emoji="🔍",
                expandable=True,
            )
            await send_ui(client, message.chat.id, diag_text, expandable=True)
            return

        # ── 1. .voice list ───────────────────────────────────────────────────
        if cmd_lower == "list":
            asyncio.create_task(auto_delete(message, delay=getattr(config, "AUTO_DELETE_CMD", 0), force=True))
            profiles = list_profiles()
            if not profiles:
                res_text = list_ui(
                    title="VOICE LIST",
                    items=[],
                    emoji="🎙️",
                    empty_message="(Belum ada profil suara tersimpan)",
                )
                await send_ui(client, message.chat.id, res_text)
                return

            items = []
            for p in profiles:
                p_name = p.get("slug") or p.get("name") or "unknown"
                items.append(f"voice {p_name.lower()}")

            res_text = list_ui(
                title="VOICE LIST",
                items=items,
                emoji="🎙️",
            )
            await send_ui(client, message.chat.id, res_text)
            return

        # ── 2. .voice delete <Nama> ──────────────────────────────────────────
        if cmd_lower.startswith("delete ") or cmd_lower.startswith("del "):
            asyncio.create_task(auto_delete(message, delay=getattr(config, "AUTO_DELETE_CMD", 0), force=True))
            del_name = args_str.split(maxsplit=1)[1].strip() if len(args_str.split(maxsplit=1)) > 1 else ""
            if not del_name:
                err_text = error(
                    title="FORMAT TIDAK LENGKAP",
                    message="Gunakan: .voice delete <Nama>\n• Contoh: .voice delete Alex",
                )
                await send_ui(client, message.chat.id, err_text, expandable=True)
                return

            ok, del_msg = delete_profile(del_name)
            res_text = success(
                title="HAPUS PROFIL SUARA",
                message=f"👤 Nama Profil : {del_name}\nℹ️ Status : {del_msg}",
                emoji="🗑️",
            )
            await send_ui(client, message.chat.id, res_text, expandable=True)
            return

        # ── 3. .voice add ────────────────────────────────────────────────────
        if cmd_lower.startswith("add"):
            # Hapus pesan command segera agar tidak ada jejak di grup / PM
            try:
                await message.delete()
            except Exception:
                pass

            # Cek apakah me-reply pesan media
            replied = message.reply_to_message
            if not replied or not (replied.voice or replied.audio or replied.video_note or replied.document):
                await _notify_manager(
                    client,
                    "❌ **[Voice Clone] Gagal:** Command `.voice add` wajib me-reply pesan Voice Note atau Audio."
                )
                return

            # Cek apakah ada nama manual yang diberikan setelah "add" (contoh: .voice add suara keren)
            if cmd_lower.startswith("add "):
                custom_name = args_str.split(maxsplit=1)[1].strip() if len(args_str.split(maxsplit=1)) > 1 else ""
                target_name = custom_name if custom_name else _extract_sender_name(replied)
            else:
                target_name = _extract_sender_name(replied)

            if not target_name:
                await _notify_manager(
                    client,
                    "❌ **[Voice Clone] Gagal:** Tidak dapat memperoleh nama pengirim dari pesan yang di-reply."
                )
                return

            asyncio.create_task(_process_voice_add(client, target_name, replied))
            return

        # ── 4. .voice <Nama> <teks...> ───────────────────────────────────────
        voice_args = args_str.split(maxsplit=1)
        if len(voice_args) < 2:
            asyncio.create_task(auto_delete(message, delay=getattr(config, "AUTO_DELETE_CMD", 0), force=True))
            err_text = format_ui(
                title="CARA PAKAI VOICE CLONE",
                body=(
                    "📖 Format Command:\n"
                    "• .voice <Nama> <teks yang ingin disuarakan>\n\n"
                    "📝 Contoh:\n"
                    "• .voice Alex Halo semuanya, ini pesan suara saya!"
                ),
                emoji="❓",
                expandable=True,
            )
            await send_ui(client, message.chat.id, err_text, expandable=True)
            return

        profile_target_name, accent, speech_text = parse_voice_request(args_str)

        # Cek apakah profil suara tersedia
        profile_obj = get_profile(profile_target_name)
        if not profile_obj:
            asyncio.create_task(auto_delete(message, delay=getattr(config, "AUTO_DELETE_CMD", 0), force=True))
            err_text = error(
                title="PROFIL SUARA TIDAK DITEMUKAN",
                message=(
                    f"👤 Nama Profil : {profile_target_name}\n\n"
                    "💡 Cara Membuat:\n"
                    "• Reply Voice Note dengan: .voice add\n"
                    "• Lihat profil yang ada: .voice list"
                ),
                emoji="❌",
            )
            await send_ui(client, message.chat.id, err_text, expandable=True)
            return

        # Kirim langsung ke chat tempat command dijalankan
        dest_chat_id = message.chat.id

        # Hapus pesan command agar bersih
        try:
            await message.delete()
        except Exception:
            pass

        # Jalankan sintesis suara secara background task agar tidak memblokir event loop
        async def _do_synthesis():
            try:
                loop = asyncio.get_running_loop()
                ok, msg, ogg_path = await loop.run_in_executor(
                    None, generate_speech, profile_target_name, speech_text, accent
                )
                if not ok or not ogg_path or not os.path.exists(ogg_path):
                    log.error("[VoicePlugin] Gagal sintesis: %s", msg)
                    fail_text = error(
                        title="GAGAL MEMBUAT VOICE NOTE",
                        message=f"👤 Profil : {profile_target_name}\n⚠️ Error : {msg}",
                        emoji="❌",
                    )
                    await send_ui(client, message.chat.id, fail_text, expandable=True)
                    return

                try:
                    await client.send_voice(
                        chat_id=dest_chat_id,
                        voice=ogg_path,
                            reply_to_message_id=message.reply_to_message.id if message.reply_to_message else None,
                    )
                finally:
                    if os.path.exists(ogg_path):
                        try:
                            os.remove(ogg_path)
                        except Exception:
                            pass
            except Exception as exc:
                log.error("[VoicePlugin] Exception saat sintesis: %s", exc)
                fail_text = error(
                    title="TERJADI KESALAHAN VOICE",
                    message=f"👤 Profil : {profile_target_name}\n⚠️ Error : {exc}",
                    emoji="❌",
                )
                await send_ui(client, message.chat.id, fail_text, expandable=True)

        asyncio.create_task(_do_synthesis())

    @client.on_message(dynamic_command("tts") & filters.me)
    async def cmd_tts_info(client, message: Message):
        text = (message.text or message.caption or "").strip()
        parts = text.split(maxsplit=1)
        subcommand = parts[1].strip().lower() if len(parts) > 1 else ""
        title, body = _tts_info_text(subcommand)
        asyncio.create_task(auto_delete(message, delay=getattr(config, "AUTO_DELETE_CMD", 0), force=True))
        await send_ui(
            client,
            message.chat.id,
            format_ui(title=title, body=body, emoji="🎙️", expandable=True),
            expandable=True,
        )
