"""Dashboard Admin Owner-only untuk mengelola Userbot Manager."""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

from pyrogram import ContinuePropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import OWNER_ID, USERBOT_RUNTIME_DIR
from database import (
    change_plan,
    delete_user,
    get_user,
    list_users,
    renew_subscription,
    set_user_status,
)
from formatter import display_date, display_username
from logger import log, safe_handler
from runner import OFFLINE, ONLINE, STARTING, get_runner, running_clients
from subscription import PLANS, expiry_label, remaining_days


PAGE_SIZE = 8
_searching: set[int] = set()


def _is_owner(update) -> bool:
    user = getattr(update, "from_user", None)
    return bool(OWNER_ID and user and user.id == OWNER_ID)


def _users() -> list[dict]:
    """Dashboard tidak menampilkan row Owner jika legacy row masih ada."""
    return [
        user
        for user in list_users()
        if not OWNER_ID or int(user["telegram_id"]) != OWNER_ID
    ]


def _status_label(status: str | None) -> str:
    return {
        ONLINE: "🟢 Online",
        STARTING: "🟡 Starting",
        OFFLINE: "🔴 Offline",
    }.get(status or OFFLINE, f"🔴 {status}")


def _runtime_ids() -> set[int]:
    return {
        int(telegram_id)
        for telegram_id, managed in running_clients.items()
        if managed.process.poll() is None
        and (not OWNER_ID or int(telegram_id) != OWNER_ID)
    }


def _stats(users: Iterable[dict]) -> dict[str, int]:
    users = list(users)
    return {
        "total": len(users),
        "online": sum(user.get("userbot_status") == ONLINE for user in users),
        "offline": sum(user.get("userbot_status") != ONLINE for user in users),
        "pending": sum(user.get("approval_status") == "pending" for user in users),
        "rejected": sum(user.get("approval_status") == "rejected" for user in users),
        "active_runtime": len(_runtime_ids()),
    }


def _dashboard_text() -> str:
    stats = _stats(_users())
    runner = get_runner()
    runtime = "Running" if runner else "Offline"
    return (
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 IBEKS MANAGER PANEL\n\n"
        f"👥 Total User: {stats['total']}\n"
        f"🟢 Userbot Online: {stats['online']}\n"
        f"🔴 Userbot Offline: {stats['offline']}\n"
        f"⏳ Pending Approval: {stats['pending']}\n"
        f"❌ Rejected: {stats['rejected']}\n"
        "💾 Database: SQLite\n"
        f"⚙ Runtime Status: {runtime} ({stats['active_runtime']} aktif)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )


def _home_text() -> str:
    return (
        "🎛 IBEKS CONTROL PANEL\n\n"
        "Pilih menu yang ingin dibuka.\n"
        "Navigasi dilakukan pada pesan panel yang sama."
    )


def _navigation_keyboard(back_callback: str = "panel:home") -> InlineKeyboardMarkup:
    """Navigasi wajib untuk seluruh submenu Control Panel."""
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("⬅ Back", callback_data=back_callback),
            InlineKeyboardButton("🏠 Home", callback_data="panel:home"),
            InlineKeyboardButton("❌ Close", callback_data="panel:close"),
        ]]
    )


def _panel_keyboard() -> InlineKeyboardMarkup:
    """Menu utama Bot Manager."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📦 Plugin Manager", callback_data="panel:plugins"),
                InlineKeyboardButton("🎨 Theme Engine", callback_data="panel:themes"),
            ],
            [
                InlineKeyboardButton("📊 Dashboard", callback_data="panel:dashboard"),
                InlineKeyboardButton("⚙️ Settings", callback_data="panel:settings"),
            ],
        ]
    )


def _plugin_manager_keyboard() -> InlineKeyboardMarkup:
    """Menu plugin yang tetap menyediakan seluruh operasi admin lama."""
    rows = [
        [
            InlineKeyboardButton("👥 Daftar User", callback_data="panel:users:0"),
            InlineKeyboardButton("🟢 User Online", callback_data="panel:online"),
        ],
        [
            InlineKeyboardButton("⏳ Pending", callback_data="panel:pending"),
            InlineKeyboardButton("🔍 Cari User", callback_data="panel:search"),
        ],
        [
            InlineKeyboardButton("📊 Statistik", callback_data="panel:stats"),
            InlineKeyboardButton("♻ Refresh", callback_data="panel:refresh"),
        ],
        [InlineKeyboardButton("📅 Subscription", callback_data="panel:subscriptions:0")],
    ]
    rows.extend(_navigation_keyboard("panel:home").inline_keyboard)
    return InlineKeyboardMarkup(rows)


def _back_panel_keyboard() -> InlineKeyboardMarkup:
    return _navigation_keyboard("panel:plugins")


def _theme_text() -> str:
    return (
        "🎨 Theme Engine\n\n"
        "Tema Bot Manager siap digunakan.\n"
        "Tema aktif: Premium"
    )


def _settings_text() -> str:
    return (
        "⚙️ Settings\n\n"
        "Pengaturan Bot Manager tersimpan secara terpusat.\n"
        "Belum ada perubahan pada tahap ini."
    )


def _plugin_manager_text() -> str:
    return (
        "📦 Plugin Manager\n\n"
        "Kelola Userbot, status akses, subscription, dan runtime "
        "melalui menu di bawah."
    )


def _user_list_text(users: list[dict], title: str, page: int = 0) -> str:
    if not users:
        return f"👥 {title}\n\nTidak ada user."
    start = page * PAGE_SIZE
    selected = users[start : start + PAGE_SIZE]
    lines = [f"👥 {title}", ""]
    for index, user in enumerate(selected, start=start + 1):
        lines.extend(
            [
                f"{index}. {user.get('full_name') or 'Tidak diketahui'}",
                f"   {display_username(user.get('username'))} · `{user['telegram_id']}`",
                f"   {_status_label(user.get('userbot_status'))} · "
                f"{user.get('status') or 'Belum Aktif'}",
                f"   Login: {display_date(user.get('login_at'))}",
                "",
            ]
        )
    total_pages = (len(users) + PAGE_SIZE - 1) // PAGE_SIZE
    lines.append(f"Halaman {page + 1}/{total_pages}")
    return "\n".join(lines)


def _subscription_list_text(users: list[dict], page: int = 0) -> str:
    if not users:
        return "📅 Subscription\n\nTidak ada user."
    start = page * PAGE_SIZE
    selected = users[start : start + PAGE_SIZE]
    lines = ["📅 Subscription", ""]
    for user in selected:
        remaining = remaining_days(user)
        lines.extend(
            [
                f"👤 {user.get('full_name') or 'Tidak diketahui'}",
                f"   Plan: {user.get('plan') or 'FREE'}",
                f"   Expired: {expiry_label(user)}",
                f"   Sisa Hari: {'Lifetime' if remaining == -1 else remaining}",
                f"   Status: {user.get('status') or 'Belum Aktif'}",
                "",
            ]
        )
    total_pages = (len(users) + PAGE_SIZE - 1) // PAGE_SIZE
    lines.append(f"Halaman {page + 1}/{total_pages}")
    return "\n".join(lines)


def _user_list_keyboard(
    users: list[dict],
    page: int = 0,
    *,
    back_callback: str = "panel:refresh",
) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    selected = users[start : start + PAGE_SIZE]
    rows = [
        [
            InlineKeyboardButton(
                f"▶ Detail {user['telegram_id']}",
                callback_data=f"panel:user:{user['telegram_id']}",
            )
        ]
        for user in selected
    ]
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton("⬅️ Sebelumnya", callback_data=f"panel:users:{page - 1}")
        )
    if start + PAGE_SIZE < len(users):
        navigation.append(
            InlineKeyboardButton("Berikutnya ➡️", callback_data=f"panel:users:{page + 1}")
        )
    if navigation:
        rows.append(navigation)
    rows.extend(_navigation_keyboard("panel:plugins").inline_keyboard)
    return InlineKeyboardMarkup(rows)


def _detail_text(user: dict) -> str:
    runtime = "Online" if int(user["telegram_id"]) in _runtime_ids() else "Offline"
    return (
        "👤 Detail User\n\n"
        f"Nama: {user.get('full_name') or 'Tidak diketahui'}\n"
        f"Username: {display_username(user.get('username'))}\n"
        f"Telegram ID: {user['telegram_id']}\n"
        f"Nomor: {user.get('phone_number') or 'Tidak tersedia'}\n"
        f"Status Approval: {user.get('approval_status') or 'pending'}\n"
        f"Plan: {user.get('plan') or 'FREE'}\n"
        f"Expired: {expiry_label(user)}\n"
        f"Sisa Hari: {'Lifetime' if remaining_days(user) == -1 else remaining_days(user)}\n"
        f"Subscription Status: {user.get('status') or 'Belum Aktif'}\n"
        f"Status Userbot: {_status_label(user.get('userbot_status'))}\n"
        f"Login Terakhir: {display_date(user.get('login_at'))}\n"
        f"Runtime: {runtime}\n"
        "Version: IBEKS USERBOT v1.0.0"
    )


def _detail_keyboard(user: dict) -> InlineKeyboardMarkup:
    telegram_id = int(user["telegram_id"])
    status = user.get("userbot_status")
    rows = [
        [
            InlineKeyboardButton(
                "▶️ Start Userbot",
                callback_data=f"panel:start:{telegram_id}",
            ),
            InlineKeyboardButton(
                "⏹ Stop Userbot",
                callback_data=f"panel:stop:{telegram_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Restart Userbot",
                callback_data=f"panel:restart:{telegram_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "📅 Subscription",
                callback_data=f"panel:subscription:{telegram_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Suspend",
                callback_data=f"panel:suspend:{telegram_id}",
            ),
            InlineKeyboardButton(
                "🗑 Hapus User",
                callback_data=f"panel:delete:{telegram_id}",
            ),
        ],
        [InlineKeyboardButton("⬅️ Daftar User", callback_data="panel:users:0")],
    ]
    if status == "Suspended":
        rows[2][0] = InlineKeyboardButton(
            "✅ Aktifkan",
            callback_data=f"panel:activate:{telegram_id}",
        )
    rows.extend(_navigation_keyboard("panel:plugins").inline_keyboard)
    return InlineKeyboardMarkup(rows)


def _subscription_text(user: dict) -> str:
    remaining = remaining_days(user)
    return (
        "📅 Subscription\n\n"
        f"Nama: {user.get('full_name') or 'Tidak diketahui'}\n"
        f"Plan: {user.get('plan') or 'FREE'}\n"
        f"Expired: {expiry_label(user)}\n"
        f"Sisa Hari: {'Lifetime' if remaining == -1 else remaining}\n"
        f"Status: {user.get('status') or 'Belum Aktif'}"
    )


def _subscription_success_text(user: dict) -> str:
    remaining = remaining_days(user)
    return (
        "✅ Subscription berhasil diperbarui.\n\n"
        f"Plan: {user.get('plan') or 'FREE'}\n"
        f"Expired: {expiry_label(user)}\n"
        f"Sisa Hari: {'Lifetime' if remaining == -1 else remaining}"
    )


def _subscription_keyboard(user: dict) -> InlineKeyboardMarkup:
    telegram_id = int(user["telegram_id"])
    current_plan = user.get("plan") or "FREE"
    rows = [
        [
            InlineKeyboardButton("➕ 7 Hari", callback_data=f"panel:renew:7:{telegram_id}"),
            InlineKeyboardButton("➕ 30 Hari", callback_data=f"panel:renew:30:{telegram_id}"),
        ],
        [
            InlineKeyboardButton("➕ 90 Hari", callback_data=f"panel:renew:90:{telegram_id}"),
            InlineKeyboardButton("♾ Lifetime", callback_data=f"panel:renew:lifetime:{telegram_id}"),
        ],
    ]
    rows.append(
        [
            InlineKeyboardButton(
                "⬆ Upgrade Plan",
                callback_data=f"panel:upgrade:{telegram_id}",
            ),
            InlineKeyboardButton(
                "⬇ Downgrade Plan",
                callback_data=f"panel:downgrade:{telegram_id}",
            ),
        ]
    )
    rows.append([InlineKeyboardButton(f"Plan Saat Ini: {current_plan}", callback_data="panel:noop")])
    rows.append([InlineKeyboardButton("⬅️ Kembali", callback_data=f"panel:user:{telegram_id}")])
    rows.extend(_navigation_keyboard("panel:plugins").inline_keyboard)
    return InlineKeyboardMarkup(rows)


def _stats_text() -> str:
    stats = _stats(_users())
    return (
        "📊 Statistik Manager\n\n"
        f"Total User: {stats['total']}\n"
        f"User Aktif: {sum(user.get('status') == 'Active' for user in _users())}\n"
        f"User Online: {stats['online']}\n"
        f"User Offline: {stats['offline']}\n"
        f"Pending: {stats['pending']}\n"
        f"Rejected: {stats['rejected']}\n"
        f"Runtime Aktif: {stats['active_runtime']}\n"
    )


def _search_results(query: str) -> list[dict]:
    normalized = query.strip().lstrip("@").lower()
    return [
        user
        for user in _users()
        if normalized in str(user["telegram_id"])
        or normalized in (user.get("username") or "").lower()
        or normalized in (user.get("full_name") or "").lower()
    ]


def _remove_runtime(telegram_id: int) -> None:
    runtime_dir: Path = USERBOT_RUNTIME_DIR / str(telegram_id)
    try:
        shutil.rmtree(runtime_dir)
    except FileNotFoundError:
        return
    except Exception:
        log.exception("[Panel] Gagal menghapus runtime user %s.", telegram_id)


async def _edit_panel(client, message, text: str, markup: InlineKeyboardMarkup) -> None:
    """Edit panel yang sama; navigasi tidak mengirim pesan baru."""
    await client.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=text,
        reply_markup=markup,
    )


async def _show_panel(client, message) -> None:
    await _edit_panel(client, message, _home_text(), _panel_keyboard())


async def _show_detail(query, telegram_id: int) -> bool:
    user = get_user(telegram_id)
    if not user or (OWNER_ID and telegram_id == OWNER_ID):
        await query.answer("User tidak ditemukan.", show_alert=True)
        return False
    await query.message.edit(_detail_text(user), reply_markup=_detail_keyboard(user))
    return True


async def _owner_action(query, action: str, telegram_id: int) -> None:
    """Jalankan aksi user dengan re-check Owner dan target database."""
    if not _is_owner(query):
        await query.answer("❌ Akses ditolak.", show_alert=True)
        return
    if OWNER_ID and telegram_id == OWNER_ID:
        await query.answer("Owner dikelola dari Owner Session.", show_alert=True)
        return
    user = get_user(telegram_id)
    runner = get_runner()
    if not user:
        await query.answer("User tidak ditemukan.", show_alert=True)
        return
    if not runner:
        await query.answer("Runner belum aktif.", show_alert=True)
        return

    if action == "start":
        success = runner.start_userbot(telegram_id, reason="Panel start")
        text = "▶️ Userbot dijalankan." if success else "❌ User belum memenuhi syarat."
    elif action == "stop":
        success = runner.stop_userbot(
            telegram_id,
            reason="Panel stop",
            suppress_restart=True,
        )
        text = "⏹ Userbot dihentikan." if success else "ℹ️ Userbot sudah offline."
    elif action == "restart":
        runner.stop_userbot(telegram_id, reason="Panel restart", suppress_restart=True)
        success = runner.start_userbot(telegram_id, reason="Panel restart")
        text = "🔄 Userbot direstart." if success else "❌ Userbot gagal direstart."
    elif action == "suspend":
        updated = set_user_status(telegram_id, "Suspended")
        runner.stop_userbot(
            telegram_id,
            reason="Panel suspend",
            suppress_restart=True,
        )
        success = updated is not None
        text = "❌ User disuspend dan Userbot dihentikan."
    else:
        updated = set_user_status(telegram_id, "Active")
        success = updated is not None
        if success:
            runner.sync_user(telegram_id)
        text = "✅ User diaktifkan kembali."
    await query.answer(text, show_alert=not success)
    await _show_detail(query, telegram_id)
    log.info("[Panel] Owner action=%s telegram_id=%s success=%s.", action, telegram_id, success)


def setup(client):
    # Login memiliki handler teks umum pada group 0. Tempatkan command khusus
    # ini lebih awal agar /panel tidak dikonsumsi handler teks login.
    @client.on_message(
        filters.command("panel") & filters.private,
        group=-90,
    )
    @safe_handler
    async def panel_command(_client, message):
        if not _is_owner(message):
            await message.reply("❌ Akses ditolak.")
            return
        await message.reply(_home_text(), reply_markup=_panel_keyboard())

    @client.on_message(filters.private & filters.text & ~filters.command("start"))
    @safe_handler
    async def search_message(_client, message):
        if not message.from_user or message.from_user.id not in _searching:
            raise ContinuePropagation
        if not _is_owner(message):
            _searching.discard(message.from_user.id)
            raise ContinuePropagation
        _searching.discard(message.from_user.id)
        results = _search_results(message.text or "")
        await message.reply(
            _user_list_text(results, f"Hasil pencarian: {message.text}"),
            reply_markup=_user_list_keyboard(results),
        )

    @client.on_callback_query(
        filters.regex(
            r"^panel:(home|close|plugins|themes|dashboard|settings|refresh|online|pending|stats|search|users:\d+|user:\d+|"
            r"aichats:\d+|aichats|aichat_toggle:-?\d+(:\d+)?|"
            r"start:\d+|stop:\d+|restart:\d+|suspend:\d+|activate:\d+|"
            r"subscription:\d+|subscriptions:\d+|renew:(7|30|90|lifetime):\d+|"
            r"upgrade:\d+|downgrade:\d+|noop|delete:\d+|delete_confirm:\d+)$"
        )
    )
    @safe_handler
    async def panel_callback(_client, query):
        if not _is_owner(query):
            await query.answer("❌ Akses ditolak.", show_alert=True)
            return
        action, *values = query.data.split(":")[1:]
        if not query.message:
            return
        if action == "close":
            await query.answer()
            await query.message.delete()
        elif action == "home":
            await query.answer()
            await _show_panel(_client, query.message)
        elif action == "plugins":
            await query.answer()
            await _edit_panel(
                _client,
                query.message,
                _plugin_manager_text(),
                _plugin_manager_keyboard(),
            )
        elif action == "themes":
            await query.answer()
            await _edit_panel(
                _client,
                query.message,
                _theme_text(),
                _navigation_keyboard("panel:home"),
            )
        elif action == "dashboard":
            await query.answer()
            await _edit_panel(
                _client,
                query.message,
                _dashboard_text(),
                _navigation_keyboard("panel:home"),
            )
        elif action == "settings":
            await query.answer()
            await _edit_panel(
                _client,
                query.message,
                _settings_text(),
                _navigation_keyboard("panel:home"),
            )
        elif action in {"refresh"}:
            await query.answer()
            await _edit_panel(
                _client,
                query.message,
                _plugin_manager_text(),
                _plugin_manager_keyboard(),
            )
        elif action == "users":
            await query.answer()
            page = int(values[0])
            users = _users()
            await query.message.edit(
                _user_list_text(users, "Daftar User", page),
                reply_markup=_user_list_keyboard(users, page),
            )
        elif action in {"online", "pending"}:
            await query.answer()
            users = _users()
            if action == "online":
                users = [user for user in users if user.get("userbot_status") == ONLINE]
                title = "User Online"
            else:
                users = [user for user in users if user.get("approval_status") == "pending"]
                title = "Pending Approval"
            await query.message.edit(
                _user_list_text(users, title),
                reply_markup=_user_list_keyboard(users),
            )
        elif action == "stats":
            await query.answer()
            await _edit_panel(
                _client,
                query.message,
                _stats_text(),
                _navigation_keyboard("panel:plugins"),
            )
        elif action == "search":
            await query.answer()
            _searching.add(query.from_user.id)
            await query.message.edit(
                "🔍 Cari User\n\nKirim nama, username, atau Telegram ID.",
                reply_markup=_navigation_keyboard("panel:plugins"),
            )
        elif action == "user":
            await query.answer()
            await _show_detail(query, int(values[0]))
        elif action == "subscriptions":
            await query.answer()
            users = _users()
            page = int(values[0])
            await query.message.edit(
                _subscription_list_text(users, page),
                reply_markup=_user_list_keyboard(
                    users,
                    page,
                    back_callback="panel:refresh",
                ),
            )
        elif action == "subscription":
            await query.answer()
            user = get_user(int(values[0]))
            if not user or (OWNER_ID and int(values[0]) == OWNER_ID):
                await query.answer("User tidak ditemukan.", show_alert=True)
                return
            await query.message.edit(
                _subscription_text(user),
                reply_markup=_subscription_keyboard(user),
            )
        elif action == "renew":
            telegram_id = int(values[1])
            user = get_user(telegram_id)
            if not user or (OWNER_ID and telegram_id == OWNER_ID):
                await query.answer("User tidak ditemukan.", show_alert=True)
                return
            renewal = values[0]
            days = None if renewal == "lifetime" else int(renewal)
            was_expired = user.get("status") == "Expired"
            updated = renew_subscription(telegram_id, days)
            if not updated:
                await query.answer("Renew gagal.", show_alert=True)
                return
            runner = get_runner()
            if runner:
                runner.sync_user(telegram_id)
            await query.answer("Subscription diperpanjang.")
            log.info(
                "[Subscription] Renew telegram_id=%s days=%s.",
                telegram_id,
                "lifetime" if days is None else days,
            )
            if was_expired:
                log.info("[Subscription] Restore telegram_id=%s.", telegram_id)
            await query.message.edit(
                _subscription_success_text(updated),
                reply_markup=_subscription_keyboard(updated),
            )
        elif action == "plan":
            plan = values[0]
            telegram_id = int(values[1])
            user = get_user(telegram_id)
            if not user or (OWNER_ID and telegram_id == OWNER_ID):
                await query.answer("User tidak ditemukan.", show_alert=True)
                return
            updated = change_plan(telegram_id, plan)
            if not updated:
                await query.answer("Plan gagal diubah.", show_alert=True)
                return
            await query.answer(f"Plan diubah ke {plan}.")
            log.info(
                "[Subscription] Plan Changed telegram_id=%s from=%s to=%s.",
                telegram_id,
                user.get("plan") or "FREE",
                plan,
            )
            await query.message.edit(
                _subscription_success_text(updated),
                reply_markup=_subscription_keyboard(updated),
            )
        elif action in {"upgrade", "downgrade"}:
            telegram_id = int(values[0])
            user = get_user(telegram_id)
            if not user or (OWNER_ID and telegram_id == OWNER_ID):
                await query.answer("User tidak ditemukan.", show_alert=True)
                return
            current_plan = user.get("plan") or "FREE"
            if current_plan not in PLANS:
                current_plan = "FREE"
            index = PLANS.index(current_plan)
            target_index = index + (1 if action == "upgrade" else -1)
            if target_index < 0 or target_index >= len(PLANS):
                await query.answer("Tidak ada perubahan plan.", show_alert=True)
                return
            target_plan = PLANS[target_index]
            updated = change_plan(telegram_id, target_plan)
            if not updated:
                await query.answer("Plan gagal diubah.", show_alert=True)
                return
            await query.answer(f"Plan diubah ke {target_plan}.")
            log.info(
                "[Subscription] Plan Changed telegram_id=%s from=%s to=%s.",
                telegram_id,
                current_plan,
                target_plan,
            )
            await query.message.edit(
                _subscription_success_text(updated),
                reply_markup=_subscription_keyboard(updated),
            )
        elif action == "noop":
            await query.answer()
        elif action == "delete":
            telegram_id = int(values[0])
            user = get_user(telegram_id)
            if not user or (OWNER_ID and telegram_id == OWNER_ID):
                await query.answer("User tidak ditemukan.", show_alert=True)
                return
            await query.answer()
            await query.message.edit(
                f"⚠️ Hapus user {telegram_id}?\n\n"
                "Database, STRING_SESSION, approval, dan runtime akan dihapus.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ Ya, hapus",
                                callback_data=f"panel:delete_confirm:{telegram_id}",
                            ),
                            InlineKeyboardButton(
                                "Batal",
                                callback_data=f"panel:user:{telegram_id}",
                            ),
                        ]
                    ]
                ),
            )
        elif action == "delete_confirm":
            telegram_id = int(values[0])
            if not _is_owner(query) or (OWNER_ID and telegram_id == OWNER_ID):
                await query.answer("❌ Akses ditolak.", show_alert=True)
                return
            runner = get_runner()
            if runner:
                runner.stop_userbot(
                    telegram_id,
                    reason="Panel delete",
                    suppress_restart=True,
                )
            deleted = delete_user(telegram_id)
            _remove_runtime(telegram_id)
            await query.answer("User dihapus." if deleted else "User tidak ditemukan.")
            await _show_panel(_client, query.message)
            log.info("[Panel] Deleted user %s success=%s.", telegram_id, deleted)
        elif action in {"start", "stop", "restart", "suspend", "activate"}:
            await _owner_action(query, action, int(values[0]))

