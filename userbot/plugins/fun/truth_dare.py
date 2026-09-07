"""
IBEKS USERBOT - Plugin: Truth & Dare
Commands:
  MEMBER:
    /join / .join        - Bergabung dalam sesi Truth & Dare di chat/grup ini
    /start / .start      - Mulai sesi Truth & Dare setelah minimal 2 pemain bergabung
    .truth / .true / .t  - Beri Truth ke target (@username) (Hanya giliran aktif)
    .dare / .d           - Beri Dare ke target (@username) (Hanya giliran aktif)
    .tod                 - Acak Truth/Dare ke target (@username) (Hanya giliran aktif)
    .end / .tdend        - Akhiri sesi Truth & Dare & reset peserta di chat ini

  OWNER:
    .tdset / .tdadd <truth|dare|penalty> <teks/multiline>  - Tambah konten Truth/Dare/Penalty
    .tdlist <truth|dare|penalty>                           - Tampilkan daftar konten dengan ID
    .tddel <truth|dare|penalty> <id>                       - Hapus konten berdasarkan ID
"""

from __future__ import annotations

import asyncio
import random
import re

from pyrogram import filters

from config import AUTO_DELETE_CMD
from db import (
    add_td_item,
    add_td_items,
    add_td_participant,
    advance_td_turn,
    delete_td_item,
    find_td_participants,
    get_random_td_item,
    get_td_current_turn,
    get_td_game_state,
    get_td_items,
    get_td_participant,
    get_td_participants,
    is_td_participant,
    reset_td_participants,
    set_td_current_turn,
    start_td_game,
)
from plugins.utils.ui import send_ui
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui
from utils.prefix_manager import get_prefix

__version__ = "2.0.0"
__author__ = "IBEKS"

VALID_CATEGORIES = {"truth", "dare", "penalty"}
CATEGORY_NAMES = {
    "truth": "Truth",
    "dare": "Dare",
    "penalty": "Penalty",
}
CATEGORY_ALIASES = {
    "truth": "truth",
    "true": "truth",
    "t": "truth",
    "dare": "dare",
    "d": "dare",
    "penalty": "penalty",
    "p": "penalty",
}


def parse_td_items(raw_text: str) -> list[str]:
    """
    Ekstrak daftar item Truth/Dare dari teks multiline atau single line.
    Menangani penanda nomor seperti:
    1. Pertanyaan pertama
    2) Pertanyaan kedua
    3 - Pertanyaan ketiga
    4 - Pertanyaan keempat
    Nomor awalan dihilangkan sehingga hanya menyimpan teks pertanyaan/tantangan murni.
    """
    if not raw_text or not raw_text.strip():
        return []
    lines = raw_text.strip().splitlines()
    item_pattern = re.compile(r"^\s*\d+\s*[\.\)\-:]\s*(.+)$")
    items = []
    has_numbered_items = any(item_pattern.match(line) for line in lines)
    if has_numbered_items:
        current_item = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            m = item_pattern.match(line)
            if m:
                if current_item:
                    items.append(" ".join(current_item).strip())
                    current_item = []
                current_item.append(m.group(1).strip())
            else:
                if current_item:
                    current_item.append(line_str)
                else:
                    current_item.append(line_str)
        if current_item:
            items.append(" ".join(current_item).strip())
    else:
        for line in lines:
            cleaned = line.strip()
            if cleaned:
                items.append(cleaned)
    return [it for it in items if it]


def join_command():
    """Filter command untuk /join dan .join secara dinamis."""
    async def filter_func(filter_obj, client, message):
        if not message or (not message.text and not message.caption):
            return False
        text = (message.text or message.caption).strip()
        prefix = get_prefix()
        valid_prefixes = {prefix, "/", "."}
        for p in valid_prefixes:
            full = f"{p}join"
            if text == full or text.startswith(full + " ") or text.startswith(full + "\n"):
                return True
            me = getattr(client, "me", None)
            username = getattr(me, "username", None) if me else None
            if username:
                at = f"@{username}"
                if text == full + at or text.startswith(full + at + " ") or text.startswith(full + at + "\n"):
                    return True
        return False
    return filters.create(filter_func, "JoinCommandFilter")


def start_command():
    """Filter command untuk /start, .start, /tdstart, dan .tdstart secara dinamis."""
    async def filter_func(filter_obj, client, message):
        if not message or (not message.text and not message.caption):
            return False
        text = (message.text or message.caption).strip()
        prefix = get_prefix()
        valid_prefixes = {prefix, "/", "."}
        for p in valid_prefixes:
            for base in ("start", "tdstart"):
                full = f"{p}{base}"
                if text == full or text.startswith(full + " ") or text.startswith(full + "\n"):
                    return True
                me = getattr(client, "me", None)
                username = getattr(me, "username", None) if me else None
                if username:
                    at = f"@{username}"
                    if text == full + at or text.startswith(full + at + " ") or text.startswith(full + at + "\n"):
                        return True
        return False
    return filters.create(filter_func, "StartCommandFilter")


def _format_user_mention(user_data: dict | object | None) -> str:
    """Format mention user (memakai @username bila tersedia, atau link mention tg://)."""
    if not user_data:
        return "Pemain"
    if isinstance(user_data, dict):
        username = user_data.get("username")
        if username:
            clean = str(username).lstrip("@").strip()
            if clean:
                return f"@{clean}"
        user_name = user_data.get("user_name") or "Pemain"
        user_id = user_data.get("user_id")
        if user_id:
            return f"[{user_name}](tg://user?id={user_id})"
        return str(user_name)
    # Pyrogram User object
    username = getattr(user_data, "username", None)
    if username:
        return f"@{username}"
    first_name = getattr(user_data, "first_name", None) or "Pemain"
    user_id = getattr(user_data, "id", None)
    if user_id:
        return f"[{first_name}](tg://user?id={user_id})"
    return str(first_name)


def _extract_target_info(message) -> tuple[str | int | None, str | None]:
    """
    Ekstrak raw input identifier target dari message (@username, entity, reply, atau teks).
    Mengembalikan tuple (identifier, display_str).
    Jika tidak ada target yang ditentukan, mengembalikan (None, None).
    """
    text = (message.text or message.caption or "").strip()

    # 1. Cek entities jika ada text_mention (user tanpa username)
    if getattr(message, "entities", None):
        for ent in message.entities:
            ent_type_str = str(getattr(ent, "type", ""))
            if "TEXT_MENTION" in ent_type_str and getattr(ent, "user", None):
                u = ent.user
                disp = f"@{u.username}" if u.username else u.first_name
                return u.id, disp
            if "MENTION" in ent_type_str:
                offset = ent.offset
                length = ent.length
                mention_text = text[offset : offset + length].strip()
                if mention_text.startswith("@"):
                    return mention_text, mention_text

    # 2. Cek argumen setelah command (contoh: .true @viona atau .true viona atau .true Viona Cantik)
    m_cmd = re.match(r"^[./]?(truth|true|t|dare|d|tod)\b(?:\s+(.+))?$", text, re.IGNORECASE)
    if m_cmd and m_cmd.group(2):
        arg = m_cmd.group(2).strip()
        if arg:
            return arg, arg

    # 3. Cek reply_to_message jika pengirim me-reply chat pemain lain
    if message.reply_to_message and message.reply_to_message.from_user:
        ru = message.reply_to_message.from_user
        if not ru.is_bot:
            disp = f"@{ru.username}" if ru.username else ru.first_name
            return ru.id, disp

    return None, None


def resolve_game_target(chat_id: int, message) -> tuple[dict | None, str | None]:
    """
    Validasi dan temukan target participant untuk game Truth or Dare.
    Mengembalikan (target_participant_dict, error_message_if_any).
    """
    raw_target, raw_disp = _extract_target_info(message)
    if not raw_target:
        err = "⚠️ **Pilih pemain terlebih dahulu!** Tag atau tulis nama pemain yang ingin kamu pilih."
        return None, err

    matches = find_td_participants(chat_id, raw_target)
    if not matches:
        err = (
            f"⚠️ **Pemain {raw_disp} belum bergabung dalam permainan!**\n"
            "Pastikan target sudah ketik `/join` terlebih dahulu di chat ini."
        )
        return None, err

    if len(matches) > 1:
        err = (
            f"⚠️ Ditemukan lebih dari 1 pemain dengan nama **{raw_disp}**.\n"
            "Gunakan `@username` untuk memilih target secara spesifik."
        )
        return None, err

    return matches[0], None


def _format_truth_message(
    giver_mention: str,
    target_mention: str,
    item_text: str,
    next_turn_mention: str,
    penalty_text: str | None = None,
) -> str:
    """Format tampilan tantangan Truth."""
    body_lines = [
        f"👤 Pemberi : {giver_mention}",
        f"🎯 Target : {target_mention}",
        f"🎲 Pertanyaan Truth : {item_text}",
    ]
    if penalty_text:
        body_lines.append(f"⚖️ Penalty : {penalty_text.strip()}")
    body_lines.extend([
        "",
        f"👉 Giliran Berikutnya : {next_turn_mention}",
        "Ketik `.true @target`, `.dare @target`, atau `.tod @target`.",
    ])
    return format_ui(title="TRUTH OR DARE - TRUTH", body=body_lines, emoji="🎯")


def _format_dare_message(
    giver_mention: str,
    target_mention: str,
    item_text: str,
    next_turn_mention: str,
    penalty_text: str | None = None,
) -> str:
    """Format tampilan tantangan Dare."""
    body_lines = [
        f"👤 Pemberi : {giver_mention}",
        f"🎯 Target : {target_mention}",
        f"🔥 Tantangan Dare : {item_text}",
    ]
    if penalty_text:
        body_lines.append(f"⚖️ Penalty : {penalty_text.strip()}")
    body_lines.extend([
        "",
        f"👉 Giliran Berikutnya : {next_turn_mention}",
        "Ketik `.true @target`, `.dare @target`, atau `.tod @target`.",
    ])
    return format_ui(title="TRUTH OR DARE - DARE", body=body_lines, emoji="🔥")


def setup(client):
    """Daftarkan seluruh handler Truth & Dare ke client."""

    # -------------------------------------------------------------------------
    # COMMAND MEMBER: JOIN / START / GAME TRUTH / DARE / TOD / END
    # -------------------------------------------------------------------------

    @client.on_message(join_command())
    async def cmd_join(client, message):
        """Handler /join atau .join - Masuk ke sesi Truth & Dare pada chat saat ini."""
        chat_id = message.chat.id
        from_user = message.from_user
        if not from_user:
            await send_ui(
                client,
                chat_id,
                "⚠️ Tidak dapat mendeteksi akun pengguna. Pastikan kamu tidak mengirim sebagai Channel / Anonymous Admin untuk bergabung.",
            )
            return

        user_id = from_user.id
        user_name = from_user.first_name or from_user.username or "Pemain"
        username = from_user.username or ""

        if is_td_participant(chat_id, user_id):
            res = f"⚠️ **{user_name}**, kamu sudah terdaftar dalam sesi Truth & Dare di chat ini!"
            await send_ui(client, chat_id, res)
            return

        add_td_participant(chat_id, user_id, user_name, username)
        participants = get_td_participants(chat_id)
        total = len(participants)
        game_state = get_td_game_state(chat_id)
        is_active = game_state.get("status") == "active"
        user_disp = _format_user_mention(from_user)

        if not is_active:
            body_lines = [
                f"👤 Pemain : {user_disp}",
                f"📊 Total Peserta : {total} Orang",
                "⏳ Status : Menunggu Permainan Dimulai",
                "",
                "💡 Pemain lain ketik `.join` untuk ikut bergabung.",
                "🎮 Ketik `.start` jika peserta sudah siap (minimal 2 pemain)!",
            ]
        else:
            current_turn = get_td_current_turn(chat_id)
            turn_disp = _format_user_mention(current_turn) if current_turn else "Pemain"
            body_lines = [
                f"👤 Pemain : {user_disp}",
                f"📊 Total Peserta : {total} Orang",
                f"🎯 Giliran Saat Ini : {turn_disp}",
                "",
                "🎮 Permainan sedang berlangsung!",
                "Tunggu giliranmu untuk memberikan tantangan.",
            ]

        text = format_ui(title="TRUTH OR DARE - JOIN", body=body_lines, emoji="🎮")
        await send_ui(client, chat_id, text)

    @client.on_message(start_command())
    async def cmd_start(client, message):
        """Handler /start, .start, atau .tdstart - Memulai sesi permainan Truth & Dare."""
        chat_id = message.chat.id
        from_user = message.from_user
        if not from_user:
            return

        participants = get_td_participants(chat_id)
        if len(participants) < 2:
            res = (
                f"⚠️ **Peserta belum cukup!** (Saat ini: {len(participants)} pemain)\n"
                "Dibutuhkan minimal **2 pemain** yang sudah `.join` untuk memulai permainan.\n"
                "Ajak temanmu untuk ketik `.join` di chat ini!"
            )
            await send_ui(client, chat_id, res)
            return

        game_state = get_td_game_state(chat_id)
        if game_state.get("status") == "active":
            current_turn = get_td_current_turn(chat_id)
            turn_disp = _format_user_mention(current_turn) if current_turn else "Pemain"
            res = (
                "⚠️ **Permainan sudah berjalan!**\n"
                f"🎯 Saat ini giliran: {turn_disp}\n"
                "Ketik `.true @target`, `.dare @target`, atau `.tod @target`."
            )
            await send_ui(client, chat_id, res)
            return

        success, first_player, msg = start_td_game(chat_id)
        if not success or not first_player:
            await send_ui(client, chat_id, f"⚠️ Gagal memulai permainan: {msg}")
            return

        first_disp = _format_user_mention(first_player)
        total = len(participants)

        body_lines = [
            "🔥 Permainan Truth & Dare resmi dimulai!",
            f"👥 Total Peserta : {total} Orang",
            f"🎯 Giliran Pertama : {first_disp}",
            "",
            "🎮 Cara Bermain:",
            f"{first_disp}, silakan pilih target pemain lain:",
            "• `.true @username` untuk memberi Truth",
            "• `.dare @username` untuk memberi Dare",
            "• `.tod @username` untuk memberi Truth/Dare acak",
        ]
        text = format_ui(title="TRUTH OR DARE - START", body=body_lines, emoji="🔥")
        await send_ui(client, chat_id, text)

    @client.on_message(dynamic_command("truth", "true", "t"))
    async def cmd_truth(client, message):
        """Handler .truth / .true / .t - Berikan pertanyaan Truth kepada target yang dipilih."""
        chat_id = message.chat.id
        from_user = message.from_user
        if not from_user:
            return
        user_id = from_user.id
        player_name = from_user.first_name or from_user.username or "Pemain"

        # 1. Validasi: Status permainan harus active
        game_state = get_td_game_state(chat_id)
        if game_state.get("status") != "active":
            res = (
                "⚠️ **Permainan belum dimulai!**\n"
                "Ketik `.start` untuk memulai sesi Truth & Dare setelah minimal 2 pemain `.join`."
            )
            await send_ui(client, chat_id, res)
            return

        # 2. Validasi: Pengirim harus sudah /join
        if not is_td_participant(chat_id, user_id):
            res = (
                f"⚠️ **{player_name}**, kamu belum bergabung dalam sesi Truth & Dare di chat ini!\n"
                "👉 Silakan ketik `.join` terlebih dahulu untuk ikut bermain."
            )
            await send_ui(client, chat_id, res)
            return

        # 3. Validasi: Minimal 2 peserta
        participants = get_td_participants(chat_id)
        if len(participants) < 2:
            res = (
                "⚠️ **Peserta belum cukup!**\n"
                "Dibutuhkan minimal 2 pemain yang sudah `.join` untuk bermain.\n"
                "Ajak temanmu untuk ketik `.join` di chat ini."
            )
            await send_ui(client, chat_id, res)
            return

        # 4. Validasi: Giliran pengirim
        current_turn = get_td_current_turn(chat_id)
        if current_turn and current_turn.get("user_id") != user_id:
            turn_disp = _format_user_mention(current_turn)
            res = (
                "⚠️ **Bukan giliranmu!**\n"
                f"Saat ini giliran: {turn_disp}\n"
                "Tunggu giliranmu untuk memberikan tantangan!"
            )
            await send_ui(client, chat_id, res)
            return

        # 5. Validasi: Target harus dipilih secara manual dan terdaftar sebagai peserta
        target_p, err_msg = resolve_game_target(chat_id, message)
        if err_msg or not target_p:
            await send_ui(client, chat_id, err_msg or "⚠️ **Pilih pemain terlebih dahulu!**")
            return

        # 6. Validasi: Tidak boleh memilih diri sendiri
        if target_p.get("user_id") == user_id:
            res = (
                "⚠️ **Kamu tidak bisa memilih dirimu sendiri!**\n"
                "Pilih atau tag pemain lain yang sudah `.join`."
            )
            await send_ui(client, chat_id, res)
            return

        # 7. Ambil konten Truth dari database
        truth_item = get_random_td_item("truth")
        if not truth_item:
            await send_ui(
                client,
                chat_id,
                "❌ Daftar Truth masih kosong.\n"
                "💡 Silakan minta Owner untuk menambahkan dengan: `.tdset true <teks>`",
            )
            return

        penalty_item = get_random_td_item("penalty")
        penalty_text = penalty_item["text"] if penalty_item else None

        # 8. Lanjutkan giliran ke peserta berikutnya secara acak/random
        next_turn = advance_td_turn(chat_id)

        giver_disp = _format_user_mention(from_user)
        target_disp = _format_user_mention(target_p)
        next_disp = _format_user_mention(next_turn)

        text = _format_truth_message(giver_disp, target_disp, truth_item["text"], next_disp, penalty_text)
        await send_ui(client, chat_id, text)

    @client.on_message(dynamic_command("dare", "d"))
    async def cmd_dare(client, message):
        """Handler .dare / .d - Berikan tantangan Dare kepada target yang dipilih."""
        chat_id = message.chat.id
        from_user = message.from_user
        if not from_user:
            return
        user_id = from_user.id
        player_name = from_user.first_name or from_user.username or "Pemain"

        # 1. Validasi: Status permainan harus active
        game_state = get_td_game_state(chat_id)
        if game_state.get("status") != "active":
            res = (
                "⚠️ **Permainan belum dimulai!**\n"
                "Ketik `.start` untuk memulai sesi Truth & Dare setelah minimal 2 pemain `.join`."
            )
            await send_ui(client, chat_id, res)
            return

        # 2. Validasi: Pengirim harus sudah /join
        if not is_td_participant(chat_id, user_id):
            res = (
                f"⚠️ **{player_name}**, kamu belum bergabung dalam sesi Truth & Dare di chat ini!\n"
                "👉 Silakan ketik `.join` terlebih dahulu untuk ikut bermain."
            )
            await send_ui(client, chat_id, res)
            return

        # 3. Validasi: Minimal 2 peserta
        participants = get_td_participants(chat_id)
        if len(participants) < 2:
            res = (
                "⚠️ **Peserta belum cukup!**\n"
                "Dibutuhkan minimal 2 pemain yang sudah `.join` untuk bermain.\n"
                "Ajak temanmu untuk ketik `.join` di chat ini."
            )
            await send_ui(client, chat_id, res)
            return

        # 4. Validasi: Giliran pengirim
        current_turn = get_td_current_turn(chat_id)
        if current_turn and current_turn.get("user_id") != user_id:
            turn_disp = _format_user_mention(current_turn)
            res = (
                "⚠️ **Bukan giliranmu!**\n"
                f"Saat ini giliran: {turn_disp}\n"
                "Tunggu giliranmu untuk memberikan tantangan!"
            )
            await send_ui(client, chat_id, res)
            return

        # 5. Validasi: Target harus dipilih secara manual dan terdaftar sebagai peserta
        target_p, err_msg = resolve_game_target(chat_id, message)
        if err_msg or not target_p:
            await send_ui(client, chat_id, err_msg or "⚠️ **Pilih pemain terlebih dahulu!**")
            return

        # 6. Validasi: Tidak boleh memilih diri sendiri
        if target_p.get("user_id") == user_id:
            res = (
                "⚠️ **Kamu tidak bisa memilih dirimu sendiri!**\n"
                "Pilih atau tag pemain lain yang sudah `.join`."
            )
            await send_ui(client, chat_id, res)
            return

        # 7. Ambil konten Dare dari database
        dare_item = get_random_td_item("dare")
        if not dare_item:
            await send_ui(
                client,
                chat_id,
                "❌ Daftar Dare masih kosong.\n"
                "💡 Silakan minta Owner untuk menambahkan dengan: `.tdset dare <teks>`",
            )
            return

        penalty_item = get_random_td_item("penalty")
        penalty_text = penalty_item["text"] if penalty_item else None

        # 8. Lanjutkan giliran ke peserta berikutnya secara acak/random
        next_turn = advance_td_turn(chat_id)

        giver_disp = _format_user_mention(from_user)
        target_disp = _format_user_mention(target_p)
        next_disp = _format_user_mention(next_turn)

        text = _format_dare_message(giver_disp, target_disp, dare_item["text"], next_disp, penalty_text)
        await send_ui(client, chat_id, text)

    @client.on_message(dynamic_command("tod"))
    async def cmd_tod(client, message):
        """Handler .tod - Acak Truth atau Dare kepada target yang dipilih."""
        chat_id = message.chat.id
        from_user = message.from_user
        if not from_user:
            return
        user_id = from_user.id
        player_name = from_user.first_name or from_user.username or "Pemain"

        # 1. Validasi: Status permainan harus active
        game_state = get_td_game_state(chat_id)
        if game_state.get("status") != "active":
            res = (
                "⚠️ **Permainan belum dimulai!**\n"
                "Ketik `.start` untuk memulai sesi Truth & Dare setelah minimal 2 pemain `.join`."
            )
            await send_ui(client, chat_id, res)
            return

        # 2. Validasi: Pengirim harus sudah /join
        if not is_td_participant(chat_id, user_id):
            res = (
                f"⚠️ **{player_name}**, kamu belum bergabung dalam sesi Truth & Dare di chat ini!\n"
                "👉 Silakan ketik `.join` terlebih dahulu untuk ikut bermain."
            )
            await send_ui(client, chat_id, res)
            return

        # 3. Validasi: Minimal 2 peserta
        participants = get_td_participants(chat_id)
        if len(participants) < 2:
            res = (
                "⚠️ **Peserta belum cukup!**\n"
                "Dibutuhkan minimal 2 pemain yang sudah `.join` untuk bermain.\n"
                "Ajak temanmu untuk ketik `.join` di chat ini."
            )
            await send_ui(client, chat_id, res)
            return

        # 4. Validasi: Giliran pengirim
        current_turn = get_td_current_turn(chat_id)
        if current_turn and current_turn.get("user_id") != user_id:
            turn_disp = _format_user_mention(current_turn)
            res = (
                "⚠️ **Bukan giliranmu!**\n"
                f"Saat ini giliran: {turn_disp}\n"
                "Tunggu giliranmu untuk memberikan tantangan!"
            )
            await send_ui(client, chat_id, res)
            return

        # 5. Validasi: Target harus dipilih secara manual dan terdaftar sebagai peserta
        target_p, err_msg = resolve_game_target(chat_id, message)
        if err_msg or not target_p:
            await send_ui(client, chat_id, err_msg or "⚠️ **Pilih pemain terlebih dahulu!**")
            return

        # 6. Validasi: Tidak boleh memilih diri sendiri
        if target_p.get("user_id") == user_id:
            res = (
                "⚠️ **Kamu tidak bisa memilih dirimu sendiri!**\n"
                "Pilih atau tag pemain lain yang sudah `.join`."
            )
            await send_ui(client, chat_id, res)
            return

        # 7. Pilih kategori secara acak antara Truth dan Dare
        has_truth = bool(get_td_items("truth"))
        has_dare = bool(get_td_items("dare"))

        if not has_truth and not has_dare:
            await send_ui(
                client,
                chat_id,
                "❌ Daftar Truth maupun Dare masih kosong.\n"
                "💡 Silakan minta Owner untuk menambahkan dengan: `.tdset true <teks>` atau `.tdset dare <teks>`",
            )
            return

        if has_truth and has_dare:
            category = random.choice(["truth", "dare"])
        elif has_truth:
            category = "truth"
        else:
            category = "dare"

        selected_item = get_random_td_item(category)
        if not selected_item:
            return

        penalty_item = get_random_td_item("penalty")
        penalty_text = penalty_item["text"] if penalty_item else None

        # 8. Lanjutkan giliran ke peserta berikutnya secara acak/random
        next_turn = advance_td_turn(chat_id)

        giver_disp = _format_user_mention(from_user)
        target_disp = _format_user_mention(target_p)
        next_disp = _format_user_mention(next_turn)

        if category == "truth":
            text = _format_truth_message(giver_disp, target_disp, selected_item["text"], next_disp, penalty_text)
        else:
            text = _format_dare_message(giver_disp, target_disp, selected_item["text"], next_disp, penalty_text)

        await send_ui(client, chat_id, text)

    @client.on_message(dynamic_command("end", "tdend"))
    async def cmd_end(client, message):
        """Handler .end / .tdend - Mengakhiri sesi Truth & Dare pada chat saat ini."""
        chat_id = message.chat.id
        deleted_count = reset_td_participants(chat_id)

        body_lines = [
            "🛑 Sesi Truth & Dare di chat ini telah diakhiri.",
            f"👥 Peserta yang di-reset : {deleted_count} orang",
            "",
            "💡 Untuk memulai sesi baru, semua pemain harus ketik `.join` kembali lalu ketik `.start`.",
        ]
        text = format_ui(title="TRUTH OR DARE - END", body=body_lines, emoji="🛑")
        await send_ui(client, chat_id, text)

    # -------------------------------------------------------------------------
    # COMMAND OWNER: TDSET / TDADD / TDLIST / TDDEL
    # -------------------------------------------------------------------------

    @client.on_message(dynamic_command("tdset", "tdadd") & filters.me)
    async def cmd_tdset(client, message):
        """Handler .tdset / .tdadd <truth|dare|penalty> <teks/multiline> (Owner only)."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        chat_id = message.chat.id

        text_content = message.text or message.caption or ""
        match = re.match(r"^([^\s]+)\s+([a-zA-Z0-9_-]+)([\s\S]*)$", text_content)

        if not match:
            res_msg = await send_ui(
                client,
                chat_id,
                "❌ **Format .tdset Tidak Sesuai**\n\n"
                "Gunakan format:\n"
                "• `.tdset <truth|dare|penalty> <teks>`\n\n"
                "**Contoh Multiline:**\n"
                "`.tdset dare`\n"
                "1. Tantangan pertama\n"
                "2. Tantangan kedua\n"
                "3. Tantangan ketiga",
            )
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))
            return

        raw_category = match.group(2).lower().strip()
        category = CATEGORY_ALIASES.get(raw_category)
        if not category:
            res_msg = await send_ui(
                client,
                chat_id,
                f"❌ Gagal menyimpan. Kategori `{raw_category}` tidak valid (pilih: truth, dare, penalty).",
            )
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))
            return

        body_content = match.group(3).strip()
        items = parse_td_items(body_content)
        if not items:
            res_msg = await send_ui(
                client,
                chat_id,
                "❌ Gagal menyimpan. Teks pertanyaan/tantangan tidak boleh kosong.",
            )
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))
            return

        try:
            item_ids = add_td_items(category, items)
            cat_name = CATEGORY_NAMES.get(category, category.capitalize())
            if len(item_ids) == 1:
                res_text = (
                    f"✅ **{cat_name}** berhasil ditambahkan!\n"
                    f"🆔 ID: `{item_ids[0]}`\n"
                    f"📝 Teks: {items[0]}"
                )
            else:
                id_list = ", ".join(f"`{i}`" for i in item_ids)
                res_text = (
                    f"✅ Berhasil menambahkan **{len(item_ids)} item {cat_name}**!\n"
                    f"🆔 ID: {id_list}"
                )
            res_msg = await send_ui(client, chat_id, res_text)
        except Exception as exc:
            res_msg = await send_ui(
                client,
                chat_id,
                f"❌ Gagal menyimpan. {exc}",
            )

        if res_msg:
            asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))

    @client.on_message(dynamic_command("tdlist") & filters.me)
    async def cmd_tdlist(client, message):
        """Handler .tdlist <truth|dare|penalty> (Owner only)."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        chat_id = message.chat.id

        text_content = message.text or message.caption or ""
        parts = text_content.split()

        raw_category = parts[1].lower().strip() if len(parts) >= 2 else ""
        category = CATEGORY_ALIASES.get(raw_category)

        if not category:
            res_msg = await send_ui(
                client,
                chat_id,
                "⚠️ **Format .tdlist Tidak Sesuai**\n\n"
                "Gunakan salah satu format berikut:\n"
                "• `.tdlist truth` (atau `.tdlist true`)\n"
                "• `.tdlist dare`\n"
                "• `.tdlist penalty`",
            )
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))
            return

        cat_name = CATEGORY_NAMES.get(category, category.capitalize())
        items = get_td_items(category)

        if not items:
            res_msg = await send_ui(
                client,
                chat_id,
                f"📋 Daftar {cat_name} masih kosong.\n"
                f"💡 Tambahkan dengan: `.tdset {category} <teks>`",
            )
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))
            return

        lines = [f"📋 **Daftar {cat_name}** ({len(items)} item):\n"]
        for idx, item in enumerate(items, 1):
            lines.append(f"{idx}. `[ID: {item['id']}]` {item['text']}")

        res_msg = await send_ui(client, chat_id, "\n".join(lines))
        if res_msg:
            asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))

    @client.on_message(dynamic_command("tddel") & filters.me)
    async def cmd_tddel(client, message):
        """Handler .tddel <truth|dare|penalty> <id> (Owner only)."""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))
        chat_id = message.chat.id

        text_content = message.text or message.caption or ""
        parts = text_content.split()

        raw_category = parts[1].lower().strip() if len(parts) >= 2 else ""
        category = CATEGORY_ALIASES.get(raw_category)

        if not category or len(parts) < 3 or not parts[2].isdigit():
            res_msg = await send_ui(
                client,
                chat_id,
                "⚠️ **Format .tddel Tidak Sesuai**\n\n"
                "Gunakan salah satu format berikut:\n"
                "• `.tddel truth <id>`\n"
                "• `.tddel dare <id>`\n"
                "• `.tddel penalty <id>`\n\n"
                "💡 Cek ID item menggunakan command `.tdlist <truth|dare|penalty>`",
            )
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))
            return

        cat_name = CATEGORY_NAMES.get(category, category.capitalize())
        item_id = int(parts[2])

        success = delete_td_item(category, item_id)
        if success:
            text = f"✅ {cat_name} dengan ID `{item_id}` berhasil dihapus!"
        else:
            text = f"❌ Gagal menghapus. {cat_name} dengan ID `{item_id}` tidak ditemukan."

        res_msg = await send_ui(client, chat_id, text)
        if res_msg:
            asyncio.create_task(auto_delete(res_msg, delay=AUTO_DELETE_CMD))
