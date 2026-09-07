"""
IBEKS USERBOT - AI Chatbot Configuration
Konfigurasi dan state untuk plugin Chatbot AI Gemini.
Command:
  .aiconfig        - Menampilkan ringkasan konfigurasi Chatbot AI saat ini.
  .aiconfig status - Menampilkan ringkasan konfigurasi Chatbot AI saat ini.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from pyrogram import filters

from config import AUTO_DELETE_CMD
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import format_ui
from plugins.utils.ui import send_ui

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Gemini API Credentials & Model ──────────────────────────────────────────
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "").strip()
DEFAULT_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash").strip()
FALLBACK_MODELS: list[str] = [
    DEFAULT_MODEL,
    "gemini-3.7-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-flash-latest",
]

# ── Context & Conversation Settings ─────────────────────────────────────────
DEFAULT_CONTEXT_LIMIT: int = 8      # Jumlah pesan histori chat default
MIN_CONTEXT_LIMIT: int = 1
MAX_CONTEXT_LIMIT: int = 30
MAX_OUTPUT_TOKENS: int = 1024

# ── Typing Simulation Settings ──────────────────────────────────────────────
TYPING_SPEED_CPS: float = 28.0      # Estimasi karakter per detik
DEFAULT_MIN_DELAY: float = 1.2      # Durasi minimal typing auto (detik)
DEFAULT_MAX_DELAY: float = 6.0      # Durasi maksimal typing auto (detik)

# ── Global Runtime State (In-Memory) ────────────────────────────────────────
_AI_STATE: dict[str, Any] = {
    "total_replies": 0,
    "last_reply_at": None,
    "active_model": DEFAULT_MODEL,
    "custom_style": None,           # str | None (backward compatibility)
    "manual_style": None,           # str | None (dari .aistyle set)
    "learned_style": None,          # str | None (dari .aistyle learn)
    "context_limit": DEFAULT_CONTEXT_LIMIT,
    "delay_mode": "auto",           # "auto" | "fixed" | "range"
    "delay_fixed": None,            # float | None
    "delay_min": None,              # float | None
    "delay_max": None,              # float | None
}


# ── State Accessors ─────────────────────────────────────────────────────────

def is_ai_enabled(chat_id: int | str | None = None) -> bool:
    """
    Periksa apakah Chatbot AI aktif.
    Wajib memeriksa status per-chat (tidak ada global fallback).
    """
    if chat_id is None:
        return False
    try:
        from db import is_ai_chat_active
        return is_ai_chat_active(chat_id)
    except Exception:
        return False


def set_ai_enabled(enabled: bool, chat_id: int | str | None = None) -> None:
    """Set status aktif per-chat jika chat_id diberikan."""
    if chat_id is not None:
        try:
            from db import set_ai_chat_state
            set_ai_chat_state(chat_id=int(chat_id), enabled=bool(enabled))
        except Exception:
            pass


def get_active_model() -> str:
    """Ambil model Gemini yang sedang aktif digunakan."""
    return str(_AI_STATE.get("active_model", DEFAULT_MODEL))


def set_active_model(model_name: str) -> None:
    """Perbarui model aktif pada state."""
    if model_name:
        _AI_STATE["active_model"] = model_name.strip()


def get_ai_stats() -> dict[str, Any]:
    """Ambil seluruh statistik dan konfigurasi runtime Chatbot AI."""
    return dict(_AI_STATE)


def increment_ai_counter() -> None:
    """Tambah hitungan balasan AI yang berhasil."""
    _AI_STATE["total_replies"] = _AI_STATE.get("total_replies", 0) + 1


def get_api_key() -> str:
    """Ambil Gemini API Key dari environment variable terbaru."""
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_key")
        or os.environ.get("GEMINI_API")
        or os.environ.get("GEMINI_KEY")
        or GEMINI_API_KEY
    ).strip()


# ── Style State ─────────────────────────────────────────────────────────────

def get_manual_style() -> str | None:
    """Ambil instruksi gaya manual AI (.aistyle set)."""
    val = _AI_STATE.get("manual_style")
    if val is not None:
        return val.strip() if val.strip() else None
    try:
        from db import get_ai_manual_style
        db_val = get_ai_manual_style()
        if db_val:
            _AI_STATE["manual_style"] = db_val
            return db_val
    except Exception:
        pass
    return None


def set_manual_style(style_text: str | None) -> None:
    """Setel instruksi gaya manual AI (.aistyle set)."""
    text = style_text.strip() if style_text else None
    _AI_STATE["manual_style"] = text
    try:
        from db import set_ai_manual_style
        set_ai_manual_style(text)
    except Exception:
        pass


def get_learned_style() -> str | None:
    """Ambil profil gaya terpelajari AI (.aistyle learn)."""
    val = _AI_STATE.get("learned_style")
    if val is not None:
        return val.strip() if val.strip() else None
    try:
        from db import get_ai_learned_style
        db_val = get_ai_learned_style()
        if db_val:
            _AI_STATE["learned_style"] = db_val
            return db_val
    except Exception:
        pass
    return None


def set_learned_style(style_text: str | None) -> None:
    """Setel profil gaya terpelajari AI (.aistyle learn)."""
    text = style_text.strip() if style_text else None
    _AI_STATE["learned_style"] = text
    try:
        from db import set_ai_learned_style
        set_ai_learned_style(text)
    except Exception:
        pass


def reset_manual_style() -> None:
    """Reset instruksi gaya manual AI."""
    _AI_STATE["manual_style"] = None
    try:
        from db import set_ai_manual_style
        set_ai_manual_style(None)
    except Exception:
        pass


def reset_learned_style() -> None:
    """Reset profil gaya terpelajari AI."""
    _AI_STATE["learned_style"] = None
    try:
        from db import set_ai_learned_style
        set_ai_learned_style(None)
    except Exception:
        pass


def get_custom_style() -> str | None:
    """Ambil custom style yang sedang aktif (kompatibilitas backward)."""
    return get_learned_style() or get_manual_style() or _AI_STATE.get("custom_style")


def set_custom_style(style_text: str | None) -> None:
    """Setel custom style tulisan AI (kompatibilitas backward)."""
    set_learned_style(style_text)
    _AI_STATE["custom_style"] = style_text.strip() if style_text else None


def reset_custom_style() -> None:
    """Kembalikan style tulisan ke default (reset learned & manual)."""
    _AI_STATE["custom_style"] = None
    reset_manual_style()
    reset_learned_style()


# ── Context Limit State ─────────────────────────────────────────────────────

def get_context_limit() -> int:
    """Ambil jumlah batasan histori pesan percakapan."""
    return int(_AI_STATE.get("context_limit", DEFAULT_CONTEXT_LIMIT))


def set_context_limit(count: int) -> int:
    """Setel jumlah batasan histori pesan percakapan (dibatasi 1 s/d MAX_CONTEXT_LIMIT)."""
    clamped = max(MIN_CONTEXT_LIMIT, min(int(count), MAX_CONTEXT_LIMIT))
    _AI_STATE["context_limit"] = clamped
    return clamped


def reset_context_limit() -> int:
    """Kembalikan batasan histori ke default."""
    _AI_STATE["context_limit"] = DEFAULT_CONTEXT_LIMIT
    return DEFAULT_CONTEXT_LIMIT


# ── Delay State ─────────────────────────────────────────────────────────────

def get_delay_config() -> dict[str, Any]:
    """Ambil konfigurasi delay saat ini."""
    return {
        "mode": _AI_STATE.get("delay_mode", "auto"),
        "fixed": _AI_STATE.get("delay_fixed"),
        "min": _AI_STATE.get("delay_min"),
        "max": _AI_STATE.get("delay_max"),
    }


def set_fixed_delay(seconds: float) -> float:
    """Setel delay tetap dalam detik."""
    val = round(max(0.5, min(float(seconds), 30.0)), 2)
    _AI_STATE["delay_mode"] = "fixed"
    _AI_STATE["delay_fixed"] = val
    _AI_STATE["delay_min"] = None
    _AI_STATE["delay_max"] = None
    return val


def set_range_delay(min_s: float, max_s: float) -> tuple[float, float]:
    """Setel rentang delay acak (min, max) dalam detik."""
    mn = round(max(0.5, min(float(min_s), 30.0)), 2)
    mx = round(max(0.5, min(float(max_s), 30.0)), 2)
    if mn > mx:
        mn, mx = mx, mn
    _AI_STATE["delay_mode"] = "range"
    _AI_STATE["delay_fixed"] = None
    _AI_STATE["delay_min"] = mn
    _AI_STATE["delay_max"] = mx
    return mn, mx


def reset_delay() -> None:
    """Kembalikan delay ke mode auto/default."""
    _AI_STATE["delay_mode"] = "auto"
    _AI_STATE["delay_fixed"] = None
    _AI_STATE["delay_min"] = None
    _AI_STATE["delay_max"] = None


# ── Command .aiconfig ───────────────────────────────────────────────────────

def setup(client) -> None:
    """Daftarkan command .aiconfig pada instance client."""

    @client.on_message(dynamic_command("aiconfig") & filters.me)
    async def cmd_aiconfig(client, message):
        """Handler command .aiconfig [status]"""
        asyncio.create_task(auto_delete(message, delay=AUTO_DELETE_CMD))

        stats = get_ai_stats()
        api_has_key = bool(get_api_key())
        api_status = "✅ Terhubung" if api_has_key else "❌ Belum Disetel"

        # Status AI
        status_text = "🟢 Aktif" if stats.get("enabled", True) else "🔴 Dinonaktifkan"

        # Model
        model_name = stats.get("active_model", DEFAULT_MODEL)

        # Context
        ctx_val = stats.get("context_limit", DEFAULT_CONTEXT_LIMIT)
        ctx_desc = f"`{ctx_val} pesan`" + (" (Default)" if ctx_val == DEFAULT_CONTEXT_LIMIT else "")

        # Delay
        d_mode = stats.get("delay_mode", "auto")
        if d_mode == "fixed":
            delay_desc = f"`Tetap ({stats.get('delay_fixed')} detik)`"
        elif d_mode == "range":
            delay_desc = f"`Acak ({stats.get('delay_min')}s - {stats.get('delay_max')}s)`"
        else:
            delay_desc = f"`Otomatis ({DEFAULT_MIN_DELAY}s - {DEFAULT_MAX_DELAY}s)`"

        # Style
        manual_st = get_manual_style()
        learned_st = get_learned_style()
        if manual_st and learned_st:
            style_desc = "`Kombinasi (Manual + Learn)`"
        elif manual_st:
            style_desc = f"`Manual: {manual_st[:30]}...`" if len(manual_st) > 30 else f"`Manual: {manual_st}`"
        elif learned_st:
            style_desc = "`Gaya Saya (Learn)`"
        else:
            style_desc = "`Default (Santai & Natural)`"

        # Total replies
        replies_count = stats.get("total_replies", 0)

        # Per-chat AI state
        chat_id = message.chat.id
        try:
            from db import get_ai_chat_state, list_ai_chat_states
            chat_state = get_ai_chat_state(chat_id)
            all_chat_states = list_ai_chat_states()
            active_chat_count = sum(1 for c in all_chat_states if c.get("enabled"))
        except Exception:
            chat_state = None
            active_chat_count = 0

        chat_status_str = "🟢 Aktif (ON)" if (chat_state and chat_state.get("enabled")) else "⚪ Nonaktif (OFF)"
        chat_instruction = (
            f"`{chat_state['custom_instruction'][:35]}...`"
            if (chat_state and chat_state.get("custom_instruction") and len(chat_state["custom_instruction"]) > 35)
            else (f"`{chat_state['custom_instruction']}`" if (chat_state and chat_state.get("custom_instruction")) else "`Tidak ada (Default)`")
        )

        body_lines = [
            f"📍 Status Chat Ini : {chat_status_str}",
            f"📝 Instruksi Chat : {chat_instruction}",
            f"🌐 Total Chat AI Aktif : {active_chat_count} chat/grup",
            f"🔑 Gemini API : {api_status}",
            f"🧠 Model : {model_name}",
            f"💬 Konteks : {ctx_desc}",
            f"⏳ Delay / Typing : {delay_desc}",
            f"🎨 Style Tulisan : {style_desc}",
            f"📊 Total Balasan : {replies_count} pesan",
            "",
            "🛠️ Command Owner:",
            "• .aibls [instruksi] : Aktifkan AI di chat ini",
            "• .aistop : Matikan AI di chat ini",
            "• .aistyle : Atur gaya tulisan",
            "• .aicontext : Atur jumlah konteks",
            "• .aidelay : Atur jeda balasan",
        ]

        text = format_ui(
            title="KONFIGURASI CHATBOT AI",
            body="\n".join(body_lines),
            emoji="⚙️",
            expandable=True,
        )

        await send_ui(client, message.chat.id, text, expandable=True)

