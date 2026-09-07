"""Formatter teks yang dipakai plugin Manager Bot."""

from __future__ import annotations

from datetime import datetime


def full_name(user) -> str:
    return " ".join(
        part
        for part in [
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        ]
        if part
    ) or "Pengguna Telegram"


def display_username(username: str | None) -> str:
    return f"@{username}" if username else "Tidak ada"


def display_date(value: str | None) -> str:
    if not value:
        return "Belum tersedia"
    try:
        return datetime.fromisoformat(value).strftime("%d-%m-%Y %H:%M UTC")
    except ValueError:
        return value


def welcome_text() -> str:
    return (
        "👋 Selamat Datang di IBEKS USERBOT\n\n"
        "Silakan pilih menu di bawah untuk mulai menggunakan layanan."
    )


def account_text(user_data: dict) -> str:
    status = user_data.get("status") or "Belum Aktif"
    if status == "Active":
        status_line = "🟢 Active"
    elif status == "Expired":
        status_line = "🔴 Expired"
    elif status == "Pending":
        status_line = "🟡 Pending"
    else:
        status_line = "🔴 Belum Aktif"
    userbot_status = user_data.get("userbot_status") or "Offline"
    userbot_status_line = {
        "Online": "🟢 Online",
        "Starting": "🟡 Starting",
        "Offline": "🔴 Offline",
    }.get(userbot_status, f"🔴 {userbot_status}")
    plan = user_data.get("plan") or "FREE"
    remaining = user_data.get("remaining_days")
    remaining_line = "Lifetime" if remaining == -1 else f"{remaining or 0} hari"
    expired_at = (
        "Lifetime"
        if remaining == -1
        else display_date(user_data.get("expired_at"))
    )
    return (
        "👤 Akun Saya\n\n"
        f"Nama : {user_data.get('full_name') or 'Tidak diketahui'}\n"
        f"Username : {display_username(user_data.get('username'))}\n"
        f"Telegram ID : {user_data.get('telegram_id')}\n"
        f"Status : {status_line}\n"
        f"Plan : {plan}\n"
        f"Sisa Hari : {remaining_line}\n"
        f"Expired : {expired_at}\n"
        f"Userbot : {userbot_status_line}\n"
        f"Mulai Terakhir : {display_date(user_data.get('last_started'))}\n"
        f"Berhenti Terakhir : {display_date(user_data.get('last_stopped'))}\n"
        f"Tanggal Bergabung : {display_date(user_data.get('created_at'))}"
    )


def guide_text() -> str:
    return (
        "📖 Panduan\n\n"
        "1. Tekan Minta Akses.\n"
        "2. Masukkan nomor Telegram.\n"
        "3. Verifikasi OTP.\n"
        "4. Userbot aktif."
    )


def about_text(
    name: str,
    version: str,
    developer: str,
    python_version: str,
    pyrogram_version: str,
) -> str:
    return (
        "ℹ️ Tentang\n\n"
        f"Nama Bot : {name}\n"
        f"Versi : {version}\n"
        f"Developer : {developer}\n"
        "Library : Pyrogram\n"
        f"Python : {python_version}\n"
        f"Pyrogram : {pyrogram_version}"
    )