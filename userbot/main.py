"""
IBEKS USERBOT - Entry Point
Inisialisasi Pyrogram client, database, dan plugin loader.
"""

import sys
import os
import re
import sqlite3

# Tambahkan direktori userbot ke sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import utils.telegram_patch  # Patch native collapsible blockquotes Layer 178+
import pyrogram
from pyrogram import Client, filters, idle
from pyrogram.errors import ApiIdInvalid, AuthKeyUnregistered, SessionRevoked

from config import (
    API_ID,
    API_HASH,
    STRING_SESSION,
    OWNER_ID,
    MANAGER_DATABASE_PATH,
    BOT_NAME,
    VERSION,
    CMD_PREFIX,
    MAIN_FILE,
    MANAGER_BOT_ID,
    RESTART_STATE_FILE,
    RUNNER_READY_FILE,
)
from db import init_db
from loader import load_plugins, plugin_filename
from utils.logger import log
from utils.prefix_manager import set_owner_id, get_prefix
from utils.error_handler import install_client_error_handler, install_global_error_handler
from utils.voice_manager import voice_manager
from utils.voice_bridge import start_voice_bridge
from utils.clone_bridge import start_clone_bridge


_TELEGRAM_BOT_TOKEN_RE = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b")


def _redact_debug_text(text: str) -> str:
    """Redaksi token Bot API sebelum pesan masuk ke log debug."""
    return _TELEGRAM_BOT_TOKEN_RE.sub("[TELEGRAM_BOT_TOKEN_REDACTED]", text)


def validate_config() -> None:
    """Pastikan semua konfigurasi wajib tersedia sebelum memulai."""
    errors = []
    if not API_ID:
        errors.append("API_ID belum di-set di Replit Secrets.")
    if not API_HASH:
        errors.append("API_HASH belum di-set di Replit Secrets.")
    if not STRING_SESSION:
        errors.append("STRING_SESSION belum di-set di Replit Secrets.")

    if errors:
        for err in errors:
            log.critical(f"[Config] {err}")
        sys.exit(1)


def _read_restart_state() -> dict:
    """Baca state restart dari file."""
    if not os.path.exists(RESTART_STATE_FILE):
        return {}
    try:
        with open(RESTART_STATE_FILE, "r", encoding="utf-8") as f:
            marker = f.read().strip()
        return {"pending": bool(marker)} if marker else {}
    except Exception as exc:
        log.warning(f"[Main] Gagal membaca state restart: {exc}")
    return {}


def _clear_restart_state() -> None:
    """Hapus file state restart jika ada."""
    try:
        if os.path.exists(RESTART_STATE_FILE):
            os.remove(RESTART_STATE_FILE)
    except Exception as exc:
        log.warning(f"[Main] Gagal menghapus state restart: {exc}")


def _clear_runner_ready() -> None:
    try:
        if os.path.exists(RUNNER_READY_FILE):
            os.remove(RUNNER_READY_FILE)
    except Exception as exc:
        log.warning(f"[Main] Gagal menghapus marker Runner: {exc}")


def _mark_runner_ready() -> None:
    try:
        os.makedirs(os.path.dirname(RUNNER_READY_FILE), exist_ok=True)
        with open(RUNNER_READY_FILE, "w", encoding="utf-8") as ready:
            ready.write(str(os.getpid()))
    except Exception as exc:
        log.warning(f"[Main] Gagal menulis marker Runner: {exc}")


def _send_restart_notification(client) -> None:
    """Kirim notifikasi restart hanya ke private chat Bot Manager."""
    if not MANAGER_BOT_ID:
        log.warning(
            "[Main] BOT_TOKEN Bot Manager tidak tersedia; "
            "notifikasi restart tidak dapat dikirim."
        )
        return

    try:
        from pyrogram.enums import ChatType

        manager_chat = client.get_chat(MANAGER_BOT_ID)
        if manager_chat.type not in {ChatType.PRIVATE, ChatType.BOT}:
            log.warning(
                "[Main] Tujuan notifikasi restart bukan private/Bot chat; "
                "pesan dibatalkan."
            )
            return
        client.send_message(MANAGER_BOT_ID, "✅ Userbot berhasil direstart.")
        log.info("[Main] Notifikasi restart dikirim ke Bot Manager.")
    except Exception as exc:
        log.warning(f"[Main] Gagal mengirim notifikasi restart: {exc}")


def _userbot_access_decision(telegram_id: int) -> tuple[bool, str]:
    """Tentukan akses startup tanpa mengirim session atau credential ke log."""
    if OWNER_ID and telegram_id == OWNER_ID:
        return True, "akun adalah Owner; approval tidak diperlukan"

    try:
        with sqlite3.connect(MANAGER_DATABASE_PATH) as connection:
            row = connection.execute(
                "SELECT approval_status FROM users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        return False, f"database approval tidak dapat dibaca: {type(exc).__name__}"

    if not row:
        return False, "akun tidak terdaftar di Manager"
    approval_status = row[0] or "pending"
    if approval_status == "approved":
        return True, "approval_status=approved"
    return False, f"approval_status={approval_status}; approval diperlukan"


def log_startup_info(client, me, plugin_stats) -> None:
    """Tampilkan login, daftar plugin, dan total plugin saat startup."""
    owner = me.first_name or me.username or "Unknown"
    log.info("✓ Login berhasil")
    log.info("✓ Userbot aktif")
    log.info(f"Nama akun Telegram : {owner}")
    log.info(f"User ID            : {me.id}")
    log.info(f"Prefix             : {get_prefix()}")

    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        f"🤖 {BOT_NAME}",
        "",
        "📦 Plugin Loaded",
        "",
    ]
    lines.extend(f"✅ {plugin_filename(module)}" for module in plugin_stats["loaded"])
    for failure in plugin_stats.get("failed_details", []):
        lines.append(f"❌ {failure['filename']}")
        lines.append(f"   {failure['error_type']}: {failure['reason']}")
    lines.extend(
        [
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📊 Total Plugin : {len(plugin_stats['loaded'])}",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
    )
    log.info("\n".join(lines))


def main() -> None:
    """Titik masuk utama IBEKS USERBOT."""
    log.info(f"╭━━━━━━━━━━━━━━━━━━━━━━╮")
    log.info(f"     💀 {BOT_NAME}")
    log.info(f"     📦 Version {VERSION}")
    log.info(f"╰━━━━━━━━━━━━━━━━━━━━━━╯")
    _clear_runner_ready()

    # ── Validasi konfigurasi ──────────────────────────────────────────────────
    validate_config()

    # ── Inisialisasi database ─────────────────────────────────────────────────
    init_db()

    # ── Buat Pyrogram client ──────────────────────────────────────────────────
    client = Client(
        name="ibeks_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=STRING_SESSION,
        in_memory=True,       # Tidak menyimpan file .session di disk
    )

    # ── Inisialisasi voice chat manager dengan client Pyrogram ───────────────
    voice_manager.set_client(client)

    # ── Pasang global error handler agar error plugin tidak merusak bot ───────
    install_global_error_handler()
    install_client_error_handler(client)

    # ── Muat semua plugin ke instance client ──────────────────────────────────
    plugin_stats = load_plugins(client)

    # ── Daftarkan Control Panel jika tersedia ──────────────────────────────────
    try:
        import panel
        panel.register(client)
        log.info("[Main] Control Panel terdaftar.")
    except Exception:
        log.exception("[Main] Gagal mendaftarkan Control Panel.")

    # ── Debug handler: log semua pesan masuk (hanya log, tidak reply) ────────
    @client.on_message(filters.incoming)
    async def debug_incoming(_client, message):
        try:
            chat_id = message.chat.id if message.chat else "n/a"
            from_id = message.from_user.id if message.from_user else "n/a"
            text = _redact_debug_text(message.text or message.caption or "[no text]")
            log.info(f"[Debug] Incoming msg | chat={chat_id} from={from_id} text={text!r}")
        except Exception as exc:
            log.warning(f"[Debug] Gagal log pesan: {exc}")

    # ── Jalankan client ───────────────────────────────────────────────────────
    try:
        log.info("[Main] Menghubungkan ke Telegram...")
        client.start()

        try:
            me = client.get_me()
        except Exception as exc:
            log.critical(f"[Main] Gagal mengambil profil user: {exc}")
            sys.exit(1)

        # Cache owner ID untuk prefix manager dan utilities lain
        set_owner_id(me.id)

        access_allowed, access_reason = _userbot_access_decision(me.id)
        if access_allowed:
            log.info(
                "[Access] Userbot dijalankan untuk %s: %s.",
                me.id,
                access_reason,
            )
        else:
            log.warning(
                "[Access] Userbot tidak dijalankan untuk %s: %s.",
                me.id,
                access_reason,
            )
            client.stop()
            return

        log_startup_info(client, me, plugin_stats)
        _mark_runner_ready()
        start_voice_bridge(client)
        start_clone_bridge(client)

        # Kirim notifikasi restart jika bot baru saja dihidupkan ulang
        restart_state = _read_restart_state()
        if restart_state:
            _send_restart_notification(client)
            _clear_restart_state()

        idle()
    except ApiIdInvalid:
        log.critical("[Main] API_ID atau API_HASH tidak valid. Periksa Replit Secrets.")
        sys.exit(1)
    except AuthKeyUnregistered:
        log.critical("[Main] STRING_SESSION tidak valid atau sudah kedaluwarsa.")
        sys.exit(1)
    except SessionRevoked:
        log.critical("[Main] STRING_SESSION telah dicabut oleh Telegram. Generate ulang dengan: cd userbot && python generate_session.py")
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("[Main] Bot dihentikan oleh pengguna.")
    except Exception as exc:
        log.exception(f"[Main] Error tidak terduga: {exc}")
        sys.exit(1)
    finally:
        _clear_runner_ready()
        log.info("[Main] IBEKS USERBOT offline.")


if __name__ == "__main__":
    main()
