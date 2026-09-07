"""Domain subscription dan pemeriksaan akses berkala Manager."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from config import OWNER_ID
from database import list_users, update_subscription_state
from logger import log

CHECK_INTERVAL = 60 * 60
PLANS = ("FREE", "PRO", "PREMIUM")
_checker_task: asyncio.Task | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expiry(user: dict) -> datetime | None:
    value = user.get("expired_at")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_subscription_active(user: dict | None) -> bool:
    if not user:
        return False
    if int(user.get("remaining_days") or 0) == -1:
        return True
    expiry = _expiry(user)
    return bool(expiry and expiry > _now())


def remaining_days(user: dict) -> int:
    if int(user.get("remaining_days") or 0) == -1:
        return -1
    expiry = _expiry(user)
    if not expiry:
        return 0
    seconds = (expiry - _now()).total_seconds()
    return max(0, int((seconds + 86399) // 86400))


def expiry_label(user: dict) -> str:
    if int(user.get("remaining_days") or 0) == -1:
        return "Lifetime"
    return user.get("expired_at") or "Belum tersedia"


async def _notify(client, telegram_id: int, text: str) -> None:
    if client is None:
        return
    try:
        await client.send_message(telegram_id, text)
    except Exception:
        log.exception("[Subscription] Gagal mengirim notifikasi ke user %s.", telegram_id)


async def check_all(client=None, *, mark_checked: bool = True) -> None:
    """Perbarui seluruh membership dan kirim notifikasi H-3/H-1/Expired."""
    now = _now()
    today = now.date().isoformat()
    for user in list_users():
        telegram_id = int(user["telegram_id"])
        if OWNER_ID and telegram_id == OWNER_ID:
            continue
        if user.get("approval_status") != "approved" or not user.get("session_string"):
            update_subscription_state(
                telegram_id,
                remaining_days=0,
                last_check=now.isoformat(timespec="seconds") if mark_checked else None,
            )
            continue
        days = remaining_days(user)
        active = is_subscription_active(user)
        was_expired = user.get("status") == "Expired"
        status = "Active" if active and was_expired else (
            "Expired" if not active else None
        )
        last_check = user.get("last_check") or ""
        checked_today = last_check[:10] == today
        update_subscription_state(
            telegram_id,
            status=status,
            remaining_days=days,
            last_check=now.isoformat(timespec="seconds") if mark_checked else None,
        )
        if status == "Expired" and not was_expired:
            log.info("[Subscription] Expired telegram_id=%s.", telegram_id)
        if status == "Active" and was_expired:
            log.info("[Subscription] Restore telegram_id=%s.", telegram_id)
        if client is None:
            continue
        if status == "Expired" and not was_expired:
            await _notify(
                client,
                telegram_id,
                "�� Subscription Anda telah Expired. Userbot dihentikan.",
            )
        elif not checked_today and days == 3:
            await _notify(
                client,
                telegram_id,
                "⚠️ Subscription Anda tersisa 3 hari (H-3). Silakan lakukan renew.",
            )
        elif not checked_today and days == 1:
            await _notify(
                client,
                telegram_id,
                "⚠️ Subscription Anda tersisa 1 hari (H-1). Silakan lakukan renew.",
            )


def check_all_sync(*, mark_checked: bool = True) -> None:
    """Jalankan pemeriksaan akses sebelum worker Userbot dimulai."""
    now = _now()
    try:
        users = list_users()
        for user in users:
            telegram_id = int(user["telegram_id"])
            if OWNER_ID and telegram_id == OWNER_ID:
                continue
            if user.get("approval_status") != "approved" or not user.get("session_string"):
                update_subscription_state(
                    telegram_id,
                    remaining_days=0,
                    last_check=now.isoformat(timespec="seconds") if mark_checked else None,
                )
                continue
            days = remaining_days(user)
            active = is_subscription_active(user)
            was_expired = user.get("status") == "Expired"
            status = "Active" if active and was_expired else (
                "Expired" if not active else None
            )
            update_subscription_state(
                telegram_id,
                status=status,
                remaining_days=days,
                last_check=now.isoformat(timespec="seconds") if mark_checked else None,
            )
            if status == "Expired" and not was_expired:
                log.info("[Subscription] Expired telegram_id=%s.", telegram_id)
            elif status == "Active" and was_expired:
                log.info("[Subscription] Restore telegram_id=%s.", telegram_id)
    except Exception:
        log.exception("[Subscription] Pemeriksaan startup gagal.")


async def _checker(client) -> None:
    while True:
        try:
            await check_all(client)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[Subscription] Pemeriksaan berkala gagal.")
        await asyncio.sleep(CHECK_INTERVAL)


def start_checker(client) -> None:
    """Mulai subscription checker dengan proper event loop handling."""
    global _checker_task
    if _checker_task and not _checker_task.done():
        return
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Tidak ada running loop, coba get_event_loop()
            loop = asyncio.get_event_loop()
        
        if loop.is_closed():
            log.warning("[Subscription] Event loop sudah tertutup; skip checker.")
            return
            
        _checker_task = loop.create_task(_checker(client))
        log.info("[Subscription] Subscription checker dimulai.")
    except Exception:
        log.exception("[Subscription] Gagal menjadwalkan checker.")
