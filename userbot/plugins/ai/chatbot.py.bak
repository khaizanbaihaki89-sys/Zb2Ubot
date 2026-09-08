"""
IBEKS USERBOT - Plugin: Chatbot AI
Command:
  .aibls [instruksi] - Mengaktifkan AI pada chat/grup saat ini (+ simpan instruksi jika ada).
                       Jika mereply pesan, langsung membalas pesan tersebut dengan AI.
  .aistop            - Mematikan AI hanya pada chat/grup saat ini.

Fitur & Perilaku:
  - PM (Private Message): Saat aktif, AI otomatis membalas pesan masuk.
  - Grup: Saat aktif, AI hanya membalas jika di-mention/tag atau di-reply.
  - Gemini API (google-genai) dengan retry & fallback cascade model (503 handling).
  - Multi-bahasa & dialek adaptif (Indonesia, Jaksel, Betawi, Jawa, Ngapak, Sunda, daerah, English, Korea, Jepang).
  - Context percakapan sebelumnya, Persona Prompt, dan Style Profile.
  - Simulasi typing indicator + delay natural.
  - Safety filter anti-penipuan & phishing (pesan penipuan diabaikan, ubot tetap berjalan).
  - Status tersimpan per-chat di SQLite database.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pyrogram import filters
from pyrogram.enums import ChatType, MessageEntityType

from config import AUTO_DELETE_CMD, MANAGER_BOT_ID
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import error
from utils.logger import log
from plugins.utils.ui import send_ui

from db import (
    set_ai_chat_state,
    get_ai_chat_state,
    is_ai_chat_active,
    list_ai_chat_states,
)

from plugins.ai.config import (
    get_api_key,
    DEFAULT_MODEL,
    FALLBACK_MODELS,
    get_active_model,
    set_active_model,
    increment_ai_counter,
)
from plugins.ai.persona import get_persona_prompt
from plugins.ai.style import format_style_instructions
from plugins.ai.context import fetch_chat_context, format_context_for_prompt
from plugins.ai.safety import is_safe_message, sanitize_ai_output, sanitize_error_message
from plugins.ai.delay import calculate_typing_delay, simulate_typing
from plugins.ai.language import detect_language_and_dialect, format_language_prompt_context

# Inisialisasi client Google GenAI
_genai_client = None
_last_api_key = None

# Lock concurrency per-chat
_chat_locks: dict[int, asyncio.Lock] = {}


def _get_chat_lock(chat_id: int) -> asyncio.Lock:
    """Ambil atau buat asyncio.Lock khusus per chat_id."""
    if chat_id not in _chat_locks:
        _chat_locks[chat_id] = asyncio.Lock()
    return _chat_locks[chat_id]


def _get_genai_client():
    """Dapatkan instance Google GenAI Client secara aman."""
    global _genai_client, _last_api_key
    api_key = get_api_key()
    if not api_key:
        return None
    if _genai_client is None or _last_api_key != api_key:
        from google import genai
        _genai_client = genai.Client(
            api_key=api_key,
            http_options={"headers": {"User-Agent": "aistudio-build"}},
        )
        _last_api_key = api_key
    return _genai_client


def _extract_instruction(text: str) -> str:
    """Ambil instruksi tambahan jika owner mengetik misal '.aibls jawab santai pakai bahasa jawa'."""
    parts = (text or "").strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _call_gemini_sync(ai_client, model_name: str, full_prompt: str, config):
    """Fungsi pembungkus sinkron untuk memanggil Gemini generate_content."""
    return ai_client.models.generate_content(
        model=model_name,
        contents=full_prompt,
        config=config,
    )


async def _generate_gemini_reply(
    prompt_context: str,
    user_query: str,
    custom_instruction: str = "",
    language_context: str = "",
) -> str:
    """
    Panggil Gemini API dengan retry exponential backoff dan fallback cascade model
    untuk menangani error 503 UNAVAILABLE (High Demand) secara andal.
    """
    ai_client = _get_genai_client()
    if not ai_client:
        raise ValueError("GEMINI_API_KEY belum disetel pada Environment Variables.")

    from google.genai import types

    # Susun system instruction lengkap: Persona + Style Guidelines + Pemahaman Singkatan Chat Telegram
    system_instruction = (
        f"{get_persona_prompt()}\n\n"
        f"{format_style_instructions()}\n\n"
        "Aturan Pemahaman Singkatan & Konteks Chat Telegram:\n"
        "- WAJIB memahami makna dari berbagai singkatan chat Telegram/WhatsApp, typo wajar, slang, dan variasi penulisan berdasarkan konteks kalimat (misal: 'yg' [yang], 'udh/udah' [sudah], 'blm' [belum], 'bgt' [banget], 'gk/ga/gak' [nggak/tidak], 'klo/kalo' [kalau], 'knp' [kenapa], 'gmn/gimana' [bagaimana], 'kek' [kayak], 'lg' [lagi], 'dmn' [di mana], 'sm' [sama], 'aja' [saja], 'btw' [by the way], 'otw' [on the way], 'tpi/tp' [tapi], 'bkn' [bukan], 'jg' [juga], 'bs' [bisa], 'skrg' [sekarang], dll).\n"
        "- Tangkap dan pahami maksud pesan dari konteks kalimat seutuhnya, bukan sekadar pencocokan kata harfiah.\n"
        "- AI TIDAK WAJIB harus membalas dengan singkatan tersebut; ikuti dan sesuaikan gaya santai lawan bicara secara luwes dan alami.\n\n"
        "Aturan Format & Perilaku:\n"
        "- Berikan HANYA teks balasan yang akan dikirim langsung ke chat.\n"
        "- DILARANG menyertakan tanda kutip pembungkus, label 'AI:', 'Jawaban:', atau meta komentar apapun.\n"
        "- AI harus terasa seperti MANUSIA yang sedang chatting, BUKAN bot atau customer service.\n"
        "- DILARANG menyapa dengan kalimat formal seperti 'Halo! Ada yang bisa saya bantu?'. Langsung ke inti respon.\n"
        "- Sesuaikan bahasa, dialek, dan kosakata balasan dengan lawan bicara secara luwes dan alami."
    )

    # Analisis panjang pesan lawan bicara untuk proporsionalitas balasan
    word_count = len(user_query.strip().split())
    length_instruction = ""
    if word_count <= 8:
        length_instruction = (
            f"ATURAN PANJANG BALASAN (WAJIB DIIKUTI):\n"
            f"- Pesan lawan bicara SANGAT PENDEK ({word_count} kata: '{user_query}').\n"
            f"- Balas dengan SANGAT SINGKAT (1 baris / 1-8 kata), santai, to-the-point, jangan bertele-tele atau membuat paragraf panjang.\n"
            f"- Jangan pakai salam pembuka/penutup formal atau gaya customer service."
        )
    elif word_count <= 25:
        length_instruction = (
            "ATURAN PANJANG BALASAN:\n"
            "- Balas secara ringkas, santai, dan padat (1-2 kalimat) sesuai konteks percakapan."
        )

    # Susun konten input prompt
    content_parts = []
    if prompt_context:
        content_parts.append(prompt_context)

    if language_context:
        content_parts.append(language_context)

    if length_instruction:
        content_parts.append(length_instruction)

    if custom_instruction:
        content_parts.append(f"Instruksi Khusus untuk Chat Ini: {custom_instruction}")

    content_parts.append(f"Balas pesan berikut sekarang:\n\"{user_query}\"")
    full_prompt = "\n\n".join(content_parts)

    # Konfigurasi parameter model Gemini
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=1024,
        temperature=0.75,
    )

    # Susun daftar model prioritas (Model aktif saat ini didahulukan, diikuti fallback)
    preferred_model = get_active_model()
    candidate_models: list[str] = [preferred_model]
    for fb in FALLBACK_MODELS:
        if fb and fb not in candidate_models:
            candidate_models.append(fb)

    loop = asyncio.get_running_loop()
    last_error: Exception | None = None

    for model_name in candidate_models:
        # Lakukan hingga 2 percobaan per model (dengan jeda backoff jika error 503/429)
        for attempt in range(1, 3):
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda m=model_name: _call_gemini_sync(ai_client, m, full_prompt, config),
                )

                if response and response.text:
                    # Sukses: perbarui model aktif jika berbeda
                    if model_name != preferred_model:
                        set_active_model(model_name)
                        log.info(f"[Chatbot AI] Beralih menggunakan model aktif: {model_name}")
                    return sanitize_ai_output(response.text)

            except Exception as exc:
                last_error = exc
                err_clean = sanitize_error_message(exc)
                is_transient = any(
                    code in err_clean
                    for code in ("503", "UNAVAILABLE", "high demand", "429", "RESOURCE_EXHAUSTED", "Timeout")
                )

                if is_transient and attempt == 1:
                    log.warning(
                        f"[Chatbot AI] Model {model_name} sibuk ({err_clean[:60]}), mencoba ulang dalam 1.2s..."
                    )
                    await asyncio.sleep(1.2)
                    continue

                log.warning(
                    f"[Chatbot AI] Model {model_name} gagal pada percobaan {attempt} ({err_clean[:80]})."
                )
                break

    # Jika seluruh kandidat model gagal
    err_desc = sanitize_error_message(last_error) if last_error else "Semua model sibuk."
    if "503" in err_desc or "high demand" in err_desc or "UNAVAILABLE" in err_desc:
        raise RuntimeError(
            "Layanan Gemini sedang mengalami lonjakan trafik tinggi (503). Silakan coba lagi beberapa saat lagi."
        )
    raise RuntimeError(f"Gagal memproses AI: {err_desc}")


_manager_peer_cache: dict[int | str, Any] = {}


async def _resolve_manager_peer(client) -> Any:
    """Resolve Bot Manager menjadi target Telegram yang valid (int, str, atau raw InputPeer).

    Catatan penting: Pyrogram send_message(chat_id, ...) mengeksekusi storage.get_peer_by_id(chat_id)
    jika diberikan objek yang bukan string. Jika diberikan objek types.User, SQLite storage akan
    gagal dengan `Error binding parameter 1: type 'User' is not supported`.
    Oleh karena itu, fungsi ini me-resolve peer ke cache Pyrogram (via @username atau get_users),
    lalu mengembalikan target yang aman untuk send_message (int ID atau @username).
    """
    if not MANAGER_BOT_ID:
        return None

    me = getattr(client, "me", None)
    client_key = getattr(me, "id", None) or id(client)
    if client_key in _manager_peer_cache:
        return _manager_peer_cache[client_key]

    get_users = getattr(client, "get_users", None)
    get_chat = getattr(client, "get_chat", None)
    resolution_errors: list[str] = []

    # Ambil username Bot Manager jika tersedia
    try:
        from config import get_manager_bot_username

        bot_uname = get_manager_bot_username()
    except Exception:
        bot_uname = ""

    targets_to_try: list[Any] = []
    if bot_uname:
        clean_uname = bot_uname.lstrip("@")
        targets_to_try.append(f"@{clean_uname}")
    targets_to_try.append(MANAGER_BOT_ID)

    for target in targets_to_try:
        if callable(get_users):
            try:
                user_res = await get_users(target)
                if isinstance(user_res, (list, tuple)):
                    user_res = user_res[0] if user_res else None
                if user_res:
                    # Ambil target yang aman untuk Pyrogram send_message
                    safe_target = (
                        f"@{user_res.username}"
                        if getattr(user_res, "username", None)
                        else (getattr(user_res, "id", None) or MANAGER_BOT_ID)
                    )
                    _manager_peer_cache[client_key] = safe_target
                    return safe_target
            except Exception as exc:
                resolution_errors.append(f"get_users({target}): {type(exc).__name__}")

        if callable(get_chat):
            try:
                chat_res = await get_chat(target)
                if chat_res:
                    safe_target = (
                        f"@{chat_res.username}"
                        if getattr(chat_res, "username", None)
                        else (getattr(chat_res, "id", None) or MANAGER_BOT_ID)
                    )
                    _manager_peer_cache[client_key] = safe_target
                    return safe_target
            except Exception as exc:
                resolution_errors.append(f"get_chat({target}): {type(exc).__name__}")

    # Fallback ke username jika ada, atau MANAGER_BOT_ID
    if bot_uname:
        fallback_target = f"@{bot_uname.lstrip('@')}"
    else:
        fallback_target = MANAGER_BOT_ID

    _manager_peer_cache[client_key] = fallback_target
    return fallback_target


# Penyimpanan referensi notifikasi ON yang aktif per chat_id: chat_id -> list[dict[str, Any]]
_on_notifications: dict[int, list[dict[str, Any]]] = {}


async def _send_ai_ui_notification(
    client,
    chat_title: str,
    chat_id: int,
    chat_type_str: str,
    is_on: bool,
) -> Any:
    """
    Kirim notifikasi status AI Chatbot ke Manager Bot dengan format UI standar IBEKS.
    Format:
    ✦ [AI Chatbot]
    • Diaktifkan (ON) / Dinonaktifkan (OFF)
    • 🏷 Chat: {chat_title}
    • 🆔 Chat ID: {chat_id}
    • 📂 Tipe: {chat_type}
    """
    if not MANAGER_BOT_ID:
        return None

    status_line = "• Diaktifkan (ON)" if is_on else "• Dinonaktifkan (OFF)"
    body = (
        f"{status_line}\n"
        f"• 🏷 Chat: {chat_title or 'Private/Group'}\n"
        f"• 🆔 Chat ID: {chat_id}\n"
        f"• 📂 Tipe: {chat_type_str}"
    )

    try:
        manager_peer = await _resolve_manager_peer(client)
        target = manager_peer or MANAGER_BOT_ID
        sent_msg = await send_ui(
            client,
            target,
            body=body,
            title="AI Chatbot",
            emoji="✦",
        )
        if sent_msg and getattr(sent_msg, "id", None):
            target_chat_id = getattr(sent_msg.chat, "id", None) if getattr(sent_msg, "chat", None) else target
            log.info(
                f"[Chatbot AI] Notifikasi UI {'ON' if is_on else 'OFF'} terkirim ke Manager Bot "
                f"(chat_id={target_chat_id}, message_id={sent_msg.id})."
            )
            return sent_msg
        return None
    except Exception as exc:
        log.error(f"[Chatbot AI] Gagal kirim notifikasi UI ke Manager Bot ({MANAGER_BOT_ID}): {exc}")
        return None


async def _delete_ai_notification_pair(
    client,
    on_entries: list[Any],
    off_msg: Any,
    delay: int = 10,
) -> None:
    """
    Jadwalkan penghapusan notifikasi ON dan notifikasi OFF secara bersamaan
    setelah delay 10 detik.
    """
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return
    except Exception:
        pass

    to_delete_by_chat: dict[Any, set[int]] = {}
    fallback_msgs: list[Any] = []

    # 1. Kumpulkan semua pesan ON
    for item in on_entries:
        if not item:
            continue
        if isinstance(item, dict):
            c_id = item.get("chat_id")
            m_id = item.get("message_id")
            if c_id and m_id:
                to_delete_by_chat.setdefault(c_id, set()).add(m_id)
            if item.get("msg"):
                fallback_msgs.append(item["msg"])
        elif hasattr(item, "id"):
            m_id = item.id
            c_id = getattr(item.chat, "id", None) if getattr(item, "chat", None) else None
            if c_id and m_id:
                to_delete_by_chat.setdefault(c_id, set()).add(m_id)
            fallback_msgs.append(item)

    # 2. Kumpulkan pesan OFF
    if off_msg:
        off_m_id = getattr(off_msg, "id", None) or getattr(off_msg, "message_id", None)
        off_c_id = getattr(off_msg.chat, "id", None) if getattr(off_msg, "chat", None) else None
        if off_c_id and off_m_id:
            to_delete_by_chat.setdefault(off_c_id, set()).add(off_m_id)
        fallback_msgs.append(off_msg)

    # 3. Hapus serentak menggunakan client.delete_messages (batch per target chat)
    deleted_ids: set[int] = set()
    for target_chat, msg_ids in to_delete_by_chat.items():
        if not msg_ids:
            continue
        try:
            await client.delete_messages(chat_id=target_chat, message_ids=list(msg_ids), revoke=True)
            deleted_ids.update(msg_ids)
            log.info(f"[Chatbot AI] Berhasil menghapus bersama notifikasi ON & OFF {list(msg_ids)} di {target_chat}.")
        except Exception as exc:
            log.warning(f"[Chatbot AI] Gagal batch-delete notifikasi di {target_chat}: {exc}")

    # 4. Fallback per pesan jika belum terhapus
    for msg in fallback_msgs:
        m_id = getattr(msg, "id", None) or getattr(msg, "message_id", None)
        if m_id and m_id in deleted_ids:
            continue
        try:
            del_fn = getattr(msg, "delete", None)
            if callable(del_fn):
                res = del_fn()
                if asyncio.iscoroutine(res):
                    await res
            elif hasattr(client, "delete_messages"):
                c_id = getattr(msg.chat, "id", None) if getattr(msg, "chat", None) else None
                if c_id and m_id:
                    await client.delete_messages(chat_id=c_id, message_ids=[m_id], revoke=True)
        except Exception as exc:
            log.debug(f"[Chatbot AI] Fallback delete msg failed: {exc}")


async def _is_mentioned_or_replied(
    client,
    message,
    my_id: int | None,
    my_username: str | None,
    my_first_name: str | None = None,
) -> bool:
    """
    Periksa apakah pesan di grup me-reply pesan ubot atau me-mention ubot.
    """
    # 1. Cek apakah me-reply pesan akun ini
    if message.reply_to_message:
        rep = message.reply_to_message
        if getattr(rep, "outgoing", False):
            return True
        if rep.from_user:
            if getattr(rep.from_user, "is_self", False):
                return True
            if my_id and rep.from_user.id == my_id:
                return True
    elif getattr(message, "reply_to_message_id", None):
        try:
            rep = await client.get_messages(message.chat.id, message.reply_to_message_id)
            if rep:
                if getattr(rep, "outgoing", False):
                    return True
                if rep.from_user:
                    if getattr(rep.from_user, "is_self", False):
                        return True
                    if my_id and rep.from_user.id == my_id:
                        return True
        except Exception:
            pass

    text = (message.text or message.caption or "")
    if not text:
        return False

    # 2. Cek mention via username di teks biasa
    if my_username:
        username_clean = my_username.lower().lstrip("@")
        if f"@{username_clean}" in text.lower():
            return True

    # 3. Cek mention via Message Entities
    entities = message.entities or message.caption_entities
    if entities:
        for ent in entities:
            if ent.type == MessageEntityType.TEXT_MENTION and ent.user:
                if (my_id and ent.user.id == my_id) or getattr(ent.user, "is_self", False):
                    return True
            if ent.type == MessageEntityType.MENTION and my_username:
                mention_text = text[ent.offset : ent.offset + ent.length].lower().lstrip("@")
                if mention_text == my_username.lower().lstrip("@"):
                    return True

    return False


def setup(client):
    """Daftarkan command .aibls, .aistop, serta auto-responder AI pada instance client."""

    # ── Command .aistop ─────────────────────────────────────────────────────
    @client.on_message(dynamic_command("aistop") & filters.me)
    async def cmd_aistop(client, message):
        """Handler command .aistop untuk mematikan AI pada chat/grup saat ini."""
        chat_id = message.chat.id
        if message.chat.first_name:
            chat_title = f"{message.chat.first_name} {message.chat.last_name or ''}".strip()
        else:
            chat_title = (message.chat.title or "").strip()
        chat_type_str = str(message.chat.type.name.lower() if hasattr(message.chat.type, "name") else message.chat.type)

        # Hapus pesan command dari chat/grup sesegera mungkin
        try:
            await message.delete()
        except Exception:
            pass

        # Nonaktifkan pada chat saat ini di database SQLite (Per-Chat State)
        set_ai_chat_state(
            chat_id=chat_id,
            enabled=False,
            chat_title=chat_title,
            chat_type=chat_type_str,
        )

        # Ambil notifikasi ON yang tersimpan sebelumnya untuk chat ini
        on_entries = _on_notifications.pop(chat_id, [])

        # Kirim notifikasi status OFF UI baru, lalu jadwalkan hapus ON + OFF bersamaan setelah 10 detik
        async def _send_and_schedule_delete():
            sent_off = await _send_ai_ui_notification(
                client=client,
                chat_title=chat_title,
                chat_id=chat_id,
                chat_type_str=chat_type_str,
                is_on=False,
            )
            asyncio.create_task(_delete_ai_notification_pair(client, on_entries, sent_off, delay=10))

        asyncio.create_task(_send_and_schedule_delete())

    # ── Command .aibls ──────────────────────────────────────────────────────
    @client.on_message(dynamic_command("aibls") & filters.me)
    async def cmd_aibls(client, message):
        """
        Handler command .aibls:
        - .aibls [instruksi] tanpa reply: Mengaktifkan AI di chat ini (+ simpan instruksi kustom).
        - .aibls [instruksi] dengan reply: Mengaktifkan AI di chat ini & langsung membalas pesan target.
        * Notifikasi status HANYA dikirim ke Manager Bot, tidak mengirim konfirmasi ke chat/grup.
        """
        chat_id = message.chat.id
        reply_msg = message.reply_to_message
        custom_inst = _extract_instruction(message.text or message.caption or "")
        if message.chat.first_name:
            chat_title = f"{message.chat.first_name} {message.chat.last_name or ''}".strip()
        else:
            chat_title = (message.chat.title or "").strip()
        chat_type_str = str(message.chat.type.name.lower() if hasattr(message.chat.type, "name") else message.chat.type)

        # Hapus pesan command dari chat/grup sesegera mungkin
        try:
            await message.delete()
        except Exception:
            pass

        # Simpan status aktif khusus chat ini di database SQLite (Per-Chat State)
        set_ai_chat_state(
            chat_id=chat_id,
            enabled=True,
            custom_instruction=custom_inst if custom_inst else None,
            chat_title=chat_title,
            chat_type=chat_type_str,
        )

        # Kirim notifikasi status UI HANYA ke Manager Bot (JANGAN dihapus sampai .aistop dijalankan)
        async def _send_on_notify():
            sent_on = await _send_ai_ui_notification(
                client=client,
                chat_title=chat_title,
                chat_id=chat_id,
                chat_type_str=chat_type_str,
                is_on=True,
            )
            if sent_on and getattr(sent_on, "id", None):
                target_c_id = getattr(sent_on.chat, "id", None) if getattr(sent_on, "chat", None) else MANAGER_BOT_ID
                entry = {
                    "chat_id": target_c_id,
                    "message_id": sent_on.id,
                    "msg": sent_on,
                }
                _on_notifications.setdefault(chat_id, []).append(entry)

        asyncio.create_task(_send_on_notify())

        # Jika tidak me-reply pesan, proses selesai (tanpa mengirim kartu ke chat)
        if not reply_msg:
            return

        # Kasus 2: Dipanggil dengan me-reply pesan lawan bicara -> Generate dan kirim balasan langsung
        api_key = get_api_key()
        if not api_key:
            log.warning(f"[Chatbot AI] .aibls reply gagal di chat {chat_id}: GEMINI_API_KEY belum disetel.")
            return

        # Ambil teks pesan yang di-reply
        target_text = (reply_msg.text or reply_msg.caption or "").strip()
        if not target_text and reply_msg.media:
            target_text = f"[Media: {reply_msg.media}]"
        elif not target_text:
            target_text = "[Pesan tanpa teks]"

        # Safety Check: Cegah penipuan, phishing, atau permintaan OTP
        is_safe, reason = is_safe_message(target_text)
        if not is_safe:
            log.warning(f"[Chatbot AI] Pesan diblokir oleh Safety Filter: {reason}")
            return

        # Identifikasi nama pengirim pesan yang di-reply
        target_sender = "User"
        if reply_msg.from_user:
            target_sender = reply_msg.from_user.first_name or reply_msg.from_user.username or "User"
        elif reply_msg.sender_chat:
            target_sender = reply_msg.sender_chat.title or "Channel"

        lock = _get_chat_lock(chat_id)
        async with lock:
            try:
                # Ambil konteks percakapan riwayat sebelumnya
                context_messages = await fetch_chat_context(
                    client,
                    chat_id=chat_id,
                    current_message_id=message.id,
                )
                prompt_context = format_context_for_prompt(
                    context_messages=context_messages,
                    replied_message_text=target_text,
                    replied_sender_name=target_sender,
                )

                # Ambil instruksi khusus dari chat_state jika tidak ada di command saat ini
                effective_instruction = custom_inst
                if not effective_instruction:
                    st = get_ai_chat_state(chat_id)
                    if st and st.get("custom_instruction"):
                        effective_instruction = st["custom_instruction"]

                # Analisis otomatis bahasa & dialek lawan bicara sebelum generate response
                detected_lang = detect_language_and_dialect(target_text)
                language_context = format_language_prompt_context(detected_lang)
                log.info(f"[Chatbot AI] Gaya bahasa terdeteksi di chat {chat_id}: {detected_lang.get('name')}")

                # Generate respon dari Gemini API
                ai_reply = await _generate_gemini_reply(
                    prompt_context=prompt_context,
                    user_query=target_text,
                    custom_instruction=effective_instruction,
                    language_context=language_context,
                )

                # Hitung delay pengetikan manusia yang natural
                typing_delay = calculate_typing_delay(ai_reply)

                # Jalankan status typing selama durasi delay
                await simulate_typing(client, chat_id, typing_delay)

                # Kirim balasan langsung me-reply pesan lawan bicara
                await client.send_message(
                    chat_id,
                    ai_reply,
                    reply_to_message_id=reply_msg.id,
                )

                # Catat statistik runtime
                increment_ai_counter()
                log.info(f"[Chatbot AI] Sukses membalas pesan di chat {chat_id} (delay {typing_delay}s)")

            except Exception as exc:
                safe_err = sanitize_error_message(exc)
                log.exception(f"[Chatbot AI] Error saat membalas pesan: {safe_err}")
                err_msg = await send_ui(
                    client,
                    chat_id,
                    error("AI ERROR", safe_err),
                )
                asyncio.create_task(auto_delete(err_msg, delay=6))

    # ── Automatic Incoming Messages Responder ───────────────────────────────
    @client.on_message(filters.incoming & ~filters.service, group=2)
    async def ai_auto_responder(client, message):
        """
        Listener otomatis untuk setiap pesan masuk:
        - PM: Otomatis membalas setiap pesan jika AI berstatus ON untuk chat ini.
        - Grup: Membalas jika AI berstatus ON DAN pesan me-reply ubot atau me-mention ubot.
        - Safety filter: Jika penipuan/phishing, pesan diabaikan tanpa membalas.
        """
        if not message or not message.chat:
            return

        chat_id = message.chat.id

        # Abaikan pesan outgoing (milik akun sendiri)
        if getattr(message, "outgoing", False):
            return

        # 1. Cek status aktif per-chat dari database SQLite
        if not is_ai_chat_active(chat_id):
            return

        # 2. Cek API Key
        api_key = get_api_key()
        if not api_key:
            log.warning(f"[Chatbot AI Auto] Pesan di chat {chat_id} diabaikan karena GEMINI_API_KEY belum disetel.")
            return

        # 3. Identifikasi identitas ubot
        my_id = getattr(getattr(client, "me", None), "id", None)
        my_username = getattr(getattr(client, "me", None), "username", None)
        my_first_name = getattr(getattr(client, "me", None), "first_name", None)
        if not my_id:
            try:
                me = await client.get_me()
                if me:
                    my_id = me.id
                    my_username = me.username
                    my_first_name = me.first_name
            except Exception:
                pass

        # Double check: Jangan balas jika pengirim adalah akun ubot sendiri
        if message.from_user:
            if getattr(message.from_user, "is_self", False):
                return
            if my_id and message.from_user.id == my_id:
                return

        # 4. Identifikasi tipe chat (PM vs Grup/Supergroup)
        chat_type = getattr(message.chat, "type", None)
        chat_type_str = str(getattr(chat_type, "value", chat_type)).lower()
        is_pm = (
            chat_type == ChatType.PRIVATE
            or "private" in chat_type_str
            or chat_type == ChatType.BOT
            or "bot" in chat_type_str
            or (isinstance(chat_id, int) and chat_id > 0)
        )
        is_group = (
            chat_type in (ChatType.GROUP, ChatType.SUPERGROUP)
            or "group" in chat_type_str
            or (isinstance(chat_id, int) and chat_id < 0 and chat_type != ChatType.CHANNEL)
        )

        # 5. Aturan Grup vs PM:
        # - Di Grup: Hanya balas jika di-mention atau di-reply
        # - Di PM: Otomatis balas setiap pesan
        if is_group:
            is_target = await _is_mentioned_or_replied(
                client, message, my_id, my_username, my_first_name
            )
            if not is_target:
                return
        elif not is_pm:
            # Channel atau tipe lainnya diabaikan
            return

        target_text = (message.text or message.caption or "").strip()
        if not target_text and message.media:
            target_text = f"[Media: {message.media}]"
        elif not target_text:
            return

        # 6. Safety Check: Filter anti-penipuan, phishing, permintaan OTP/PIN
        is_safe, reason = is_safe_message(target_text)
        if not is_safe:
            log.warning(f"[Chatbot AI Auto] Pesan berisiko penipuan di chat {chat_id} diabaikan: {reason}")
            return

        target_sender = "User"
        if message.from_user:
            target_sender = message.from_user.first_name or message.from_user.username or "User"
        elif message.sender_chat:
            target_sender = message.sender_chat.title or "Channel"

        lock = _get_chat_lock(chat_id)
        async with lock:
            try:
                # Ambil context histori percakapan
                context_messages = await fetch_chat_context(
                    client,
                    chat_id=chat_id,
                    current_message_id=message.id,
                )
                prompt_context = format_context_for_prompt(
                    context_messages=context_messages,
                    replied_message_text=target_text,
                    replied_sender_name=target_sender,
                )

                # Ambil instruksi kustom khusus chat ini jika ada
                chat_state = get_ai_chat_state(chat_id)
                custom_inst = chat_state.get("custom_instruction", "") if chat_state else ""

                # Analisis otomatis bahasa & dialek lawan bicara sebelum generate response
                detected_lang = detect_language_and_dialect(target_text)
                language_context = format_language_prompt_context(detected_lang)
                log.info(f"[Chatbot AI Auto] Gaya bahasa terdeteksi di chat {chat_id}: {detected_lang.get('name')}")

                # Generate respons AI via Gemini
                ai_reply = await _generate_gemini_reply(
                    prompt_context=prompt_context,
                    user_query=target_text,
                    custom_instruction=custom_inst,
                    language_context=language_context,
                )

                if not ai_reply:
                    return

                # Hitung delay natural & simulasikan typing
                typing_delay = calculate_typing_delay(ai_reply)
                await simulate_typing(client, chat_id, typing_delay)

                # Kirim balasan me-reply pesan pengirim
                await client.send_message(
                    chat_id,
                    ai_reply,
                    reply_to_message_id=message.id,
                )
                increment_ai_counter()
                log.info(f"[Chatbot AI Auto] Berhasil membalas pesan masuk di chat {chat_id} ({typing_delay}s)")

            except Exception as exc:
                err_clean = sanitize_error_message(exc)
                log.warning(f"[Chatbot AI Auto] Gagal membalas pesan otomatis di chat {chat_id}: {err_clean}")
