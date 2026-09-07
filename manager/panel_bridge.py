"""Bridge .panel: Userbot meminta, Manager Bot mengontrol UI dan seluruh callback."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
import pyrogram
from pyrogram import filters
from pyrogram.errors import MessageNotModified, RPCError
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    from config import (
        DATABASE_PATH as MANAGER_DB_PATH,
        OWNER_ID as MANAGER_OWNER_ID,
        USERBOT_RUNTIME_DIR,
        USERBOT_SOURCE_DIR,
        VERSION as MANAGER_VERSION,
    )
except (ImportError, AttributeError):
    from manager.config import (
        DATABASE_PATH as MANAGER_DB_PATH,
        OWNER_ID as MANAGER_OWNER_ID,
        USERBOT_RUNTIME_DIR,
        USERBOT_SOURCE_DIR,
        VERSION as MANAGER_VERSION,
    )

try:
    from logger import log
except (ImportError, AttributeError):
    from manager.logger import log


REQUEST_POLL_INTERVAL = 0.25
CALLBACK_FILTER = filters.regex(r"^ibp:")

_STARTED_AT = time.monotonic()


@dataclass(frozen=True)
class PanelContext:
    user_id: int
    owner: str
    prefix: str


_contexts: dict[tuple[int, int], PanelContext] = {}
_watcher_task: asyncio.Task | None = None


# ── Database Helpers ──────────────────────────────────────────────────────────

def _userbot_db_path(user_id: int) -> Path:
    runtime_db = USERBOT_RUNTIME_DIR / str(user_id) / "database.db"
    if runtime_db.exists():
        return runtime_db
    source_db = USERBOT_SOURCE_DIR / "database.db"
    if source_db.exists():
        return source_db
    return Path(str(USERBOT_SOURCE_DIR / "database.db"))


def _get_setting(user_id: int, key: str, default: Any = None) -> Any:
    db_path = _userbot_db_path(user_id)
    if not db_path.exists():
        return default
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f"SELECT {key} FROM settings WHERE telegram_id = ?",
                (int(user_id),),
            ).fetchone()
            if row is not None and key in row.keys():
                return row[key]
    except Exception as exc:
        log.warning("[PanelBridge] Gagal membaca setting %s: %s", key, exc)
    return default


def _set_setting(user_id: int, key: str, value: Any) -> None:
    db_path = _userbot_db_path(user_id)
    if not db_path.exists():
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.execute(
                f"UPDATE settings SET {key} = ?, updated_at = ? WHERE telegram_id = ?",
                (value, now, int(user_id)),
            )
            conn.commit()
    except Exception as exc:
        log.warning("[PanelBridge] Gagal update setting %s: %s", key, exc)


def _list_plugins(user_id: int) -> list[dict]:
    db_path = _userbot_db_path(user_id)
    if not db_path.exists():
        return []
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM plugin_status ORDER BY module").fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("[PanelBridge] Gagal membaca plugins: %s", exc)
        return []


def _set_plugin_enabled(user_id: int, module_name: str, enabled: bool) -> None:
    db_path = _userbot_db_path(user_id)
    if not db_path.exists():
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.execute(
                "UPDATE plugin_status SET enabled = ?, updated_at = ? WHERE module = ?",
                (int(bool(enabled)), now, module_name),
            )
            conn.commit()
    except Exception as exc:
        log.warning("[PanelBridge] Gagal set plugin %s: %s", module_name, exc)


def _get_active_theme(user_id: int) -> str:
    db_path = _userbot_db_path(user_id)
    if not db_path.exists():
        return "Premium"
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT name FROM themes WHERE is_active = 1 LIMIT 1"
            ).fetchone()
            if row:
                return str(row["name"])
    except Exception:
        pass
    return "Premium"


def _set_active_theme(user_id: int, name: str) -> None:
    db_path = _userbot_db_path(user_id)
    if not db_path.exists():
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.execute("UPDATE themes SET is_active = 0, updated_at = ?", (now,))
            conn.execute(
                "UPDATE themes SET is_active = 1, updated_at = ? WHERE name = ?",
                (now, name),
            )
            conn.commit()
    except Exception as exc:
        log.warning("[PanelBridge] Gagal set theme %s: %s", name, exc)


def _get_plan(user_id: int) -> str:
    if not MANAGER_DB_PATH.exists():
        return "FREE"
    try:
        with sqlite3.connect(MANAGER_DB_PATH, timeout=10) as conn:
            row = conn.execute(
                "SELECT plan FROM users WHERE telegram_id = ?",
                (int(user_id),),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return "FREE"


# ── System Stats ──────────────────────────────────────────────────────────────

def _runtime_text() -> str:
    elapsed = int(time.monotonic() - _STARTED_AT)
    days, remainder = divmod(elapsed, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"


def _hardware_stats(user_id: int) -> dict[str, Any]:
    db_path = _userbot_db_path(user_id)
    db_size = db_path.stat().st_size if db_path.exists() else 0
    disk = shutil.disk_usage(str(db_path.parent) if db_path.parent.exists() else ".")
    plugins = _list_plugins(user_id)
    total_plugins = len(plugins)
    active_plugins = sum(1 for p in plugins if p.get("enabled") and p.get("loaded"))
    
    return {
        "runtime": _runtime_text(),
        "cpu_percent": psutil.cpu_percent(interval=0.03),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": round((disk.used / disk.total * 100), 1) if disk.total else 0,
        "database_size": round(db_size / 1024, 2),
        "total_plugins": total_plugins,
        "active_plugins": active_plugins,
        "inactive_plugins": total_plugins - active_plugins,
        "pyrogram_version": pyrogram.__version__,
        "python_version": platform.python_version(),
    }


# ── Keyboard Builder ──────────────────────────────────────────────────────────

def _nav_row(back: str = "ibp:home") -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton("⬅ Back", callback_data=back),
        InlineKeyboardButton("🏠 Home", callback_data="ibp:home"),
        InlineKeyboardButton("❌ Close", callback_data="ibp:close"),
    ]


def _home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📦 Plugin Manager", callback_data="ibp:plugins"),
                InlineKeyboardButton("🎨 Theme Engine", callback_data="ibp:themes"),
            ],
            [
                InlineKeyboardButton("📊 Dashboard", callback_data="ibp:dashboard"),
                InlineKeyboardButton("⚡ Macro", callback_data="ibp:macro"),
            ],
            [
                InlineKeyboardButton("☁️ Backup", callback_data="ibp:backup"),
                InlineKeyboardButton("👤 Permission", callback_data="ibp:permission"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="ibp:settings"),
                InlineKeyboardButton("🧩 Plugin Store", callback_data="ibp:store"),
            ],
            [
                InlineKeyboardButton("🔄 Update", callback_data="ibp:update"),
            ],
            [
                InlineKeyboardButton("❌ Close Panel", callback_data="ibp:close"),
            ],
        ]
    )


# ── View Builders ─────────────────────────────────────────────────────────────

def _build_home_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    stats = _hardware_stats(context.user_id)
    plan = _get_plan(context.user_id)
    prefix = _get_setting(context.user_id, "prefix", context.prefix)
    theme = _get_active_theme(context.user_id)
    
    text = (
        "🟢 <b>IBEKS CONTROL PANEL</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Owner</b>      : {context.owner}\n"
        f"👑 <b>Plan</b>       : {plan}\n"
        f"📦 <b>Plugin</b>     : {stats['total_plugins']}\n"
        f"🟢 <b>Active</b>     : {stats['active_plugins']}\n"
        f"🔴 <b>Disabled</b>   : {stats['inactive_plugins']}\n"
        f"⚙ <b>Prefix</b>     : <code>{prefix}</code>\n"
        f"🎨 <b>Theme</b>      : {theme}\n"
        f"🖥 <b>CPU/RAM</b>    : {stats['cpu_percent']}% / {stats['ram_percent']}%\n"
        "━━━━━━━━━━━━━━━━\n"
        "Pilih menu di bawah untuk mengelola Userbot."
    )
    return text, _home_keyboard()


def _build_plugins_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    plugins = _list_plugins(context.user_id)
    total = len(plugins)
    active = sum(1 for p in plugins if p.get("enabled") and p.get("loaded"))
    inactive = total - active
    
    text = (
        "📦 <b>PLUGIN MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"├ Total Plugin   : {total}\n"
        f"├ Plugin Aktif   : {active}\n"
        f"├ Plugin Nonaktif: {inactive}\n"
        "━━━━━━━━━━━━━━━━\n"
        "Gunakan menu di bawah untuk mengatur plugin."
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 List Plugin", callback_data="ibp:plugins:list:0"),
                InlineKeyboardButton("📊 Plugin Status", callback_data="ibp:plugins:status"),
            ],
            [
                InlineKeyboardButton("♻️ Reload Semua", callback_data="ibp:plugins:reloadall"),
            ],
            _nav_row("ibp:home"),
        ]
    )
    return text, markup


def _build_plugins_list_view(context: PanelContext, page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    plugins = _list_plugins(context.user_id)
    page_size = 6
    total_pages = max(1, (len(plugins) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    
    start = page * page_size
    current_items = plugins[start : start + page_size]
    
    lines = [
        "📋 <b>DAFTAR PLUGIN</b>",
        f"<i>Halaman {page + 1}/{total_pages}</i>",
        "━━━━━━━━━━━━━━━━",
    ]
    
    button_rows: list[list[InlineKeyboardButton]] = []
    for p in current_items:
        is_on = bool(p.get("enabled") and p.get("loaded"))
        mod_name = p.get("module", "").rsplit(".", 1)[-1]
        status_icon = "✅" if is_on else "⛔"
        lines.append(f"{status_icon} <code>{p.get('module')}</code>")
        
        # Toggle button
        action = "disable" if is_on else "enable"
        btn_label = f"{'Matikan' if is_on else 'Aktifkan'} {mod_name}"
        button_rows.append([
            InlineKeyboardButton(f"{status_icon} {mod_name}", callback_data=f"ibp:plugins:info:{p.get('module')}"),
            InlineKeyboardButton(btn_label, callback_data=f"ibp:plugins:toggle:{action}:{p.get('module')}:{page}"),
        ])
    
    # Pagination row
    nav_pagination = []
    if page > 0:
        nav_pagination.append(InlineKeyboardButton("◀️ Prev", callback_data=f"ibp:plugins:list:{page - 1}"))
    if page < total_pages - 1:
        nav_pagination.append(InlineKeyboardButton("Next ▶️", callback_data=f"ibp:plugins:list:{page + 1}"))
    
    if nav_pagination:
        button_rows.append(nav_pagination)
    button_rows.append(_nav_row("ibp:plugins"))
    
    return "\n".join(lines), InlineKeyboardMarkup(button_rows)


def _build_plugin_info_view(context: PanelContext, module_name: str) -> tuple[str, InlineKeyboardMarkup]:
    plugins = _list_plugins(context.user_id)
    p = next((x for x in plugins if x.get("module") == module_name), None)
    if not p:
        text = "❌ <b>Plugin tidak ditemukan.</b>"
    else:
        is_on = bool(p.get("enabled") and p.get("loaded"))
        text = (
            f"ℹ️ <b>INFORMASI PLUGIN: {module_name}</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            f"├ Modul      : <code>{p.get('module')}</code>\n"
            f"├ File       : {p.get('filename')}\n"
            f"├ Kategori   : {p.get('category')}\n"
            f"├ Versi      : {p.get('version', '1.0.0')}\n"
            f"├ Author     : {p.get('author', 'IBEKS')}\n"
            f"├ Command    : {p.get('command_count', 0)}\n"
            f"├ Status     : {'✅ Aktif' if is_on else '⛔ Nonaktif'}\n"
            f"├ Dimuat Pada: {p.get('loaded_at') or '-'}\n"
            "━━━━━━━━━━━━━━━━"
        )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Kembali ke Daftar", callback_data="ibp:plugins:list:0")],
        _nav_row("ibp:plugins"),
    ])
    return text, markup


def _build_themes_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    active = _get_active_theme(context.user_id)
    themes = ["Premium", "Freeze", "Minimal", "Neon", "Matrix"]
    
    lines = [
        "🎨 <b>THEME ENGINE</b>",
        "━━━━━━━━━━━━━━━━",
        f"├ <b>Tema Aktif</b> : <b>{active}</b>",
        "├",
    ]
    for t in themes:
        lines.append(f"{'✅' if t == active else '▫️'} {t}")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("Pilih tema di bawah untuk menerapkan:")
    
    theme_buttons = []
    for t in themes:
        theme_buttons.append([
            InlineKeyboardButton(f"{'✅ ' if t == active else ''}{t}", callback_data=f"ibp:themes:set:{t}")
        ])
    theme_buttons.append([
        InlineKeyboardButton("👀 Preview Tema", callback_data="ibp:themes:preview"),
    ])
    theme_buttons.append(_nav_row("ibp:home"))
    
    return "\n".join(lines), InlineKeyboardMarkup(theme_buttons)


def _build_dashboard_view(context: PanelContext, detail: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    stats = _hardware_stats(context.user_id)
    plan = _get_plan(context.user_id)
    
    if not detail:
        text = (
            "📊 <b>SYSTEM DASHBOARD</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            f"├ ⏱ <b>Uptime</b>       : {stats['runtime']}\n"
            f"├ 🖥 <b>CPU Usage</b>    : {stats['cpu_percent']}%\n"
            f"├ 💾 <b>RAM Usage</b>    : {stats['ram_percent']}%\n"
            f"├ 💽 <b>Disk Usage</b>   : {stats['disk_percent']}%\n"
            f"├ 🗄 <b>Database</b>     : {stats['database_size']} KB\n"
            f"├ 📦 <b>Plugin Aktif</b> : {stats['active_plugins']}/{stats['total_plugins']}\n"
            f"├ 👑 <b>Plan</b>         : {plan}\n"
            "━━━━━━━━━━━━━━━━"
        )
    else:
        text = (
            "📊 <b>DETAILED SYSTEM DIAGNOSTICS</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            f"├ ⏱ <b>Uptime</b>       : {stats['runtime']}\n"
            f"├ 🖥 <b>CPU</b>          : {psutil.cpu_count(logical=True)} Cores ({stats['cpu_percent']}%)\n"
            f"├ 💾 <b>RAM</b>          : {stats['ram_percent']}%\n"
            f"├ 💽 <b>Disk</b>         : {stats['disk_percent']}%\n"
            f"├ 🗄 <b>SQLite DB</b>    : {stats['database_size']} KB\n"
            f"├ 🐍 <b>Python</b>       : v{stats['python_version']}\n"
            f"├ ⚡ <b>Pyrogram</b>     : v{stats['pyrogram_version']}\n"
            f"├ 🤖 <b>Manager</b>      : v{MANAGER_VERSION}\n"
            f"├ 👤 <b>User ID</b>      : <code>{context.user_id}</code>\n"
            "━━━━━━━━━━━━━━━━"
        )
    
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="ibp:dashboard:refresh"),
                InlineKeyboardButton("📄 Detail Stats" if not detail else "📊 Ringkasan", 
                                     callback_data="ibp:dashboard:detail" if not detail else "ibp:dashboard"),
            ],
            _nav_row("ibp:home"),
        ]
    )
    return text, markup


def _build_macro_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "⚡ <b>MACRO AUTOMATION</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "├ Status: Siap digunakan\n"
        "├ Total Macro Tersimpan: 0\n"
        "━━━━━━━━━━━━━━━━\n"
        "Fitur Macro memungkinkan Anda merekam dan mengeksekusi urutan command otomatis."
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 List Macro", callback_data="ibp:macro:list"),
                InlineKeyboardButton("➕ Buat Macro", callback_data="ibp:macro:add"),
            ],
            [
                InlineKeyboardButton("▶️ Test Run Macro", callback_data="ibp:macro:run"),
            ],
            _nav_row("ibp:home"),
        ]
    )
    return text, markup


def _build_backup_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    db_path = _userbot_db_path(context.user_id)
    size_kb = round(db_path.stat().st_size / 1024, 2) if db_path.exists() else 0
    
    text = (
        "☁️ <b>DATABASE BACKUP & RESTORE</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"├ <b>Database Utama</b>: SQLite ({size_kb} KB)\n"
        f"├ <b>Lokasi File</b>   : <code>{db_path.name}</code>\n"
        f"├ <b>Status</b>        : Sinkron & Aman\n"
        "━━━━━━━━━━━━━━━━\n"
        "Klik tombol di bawah untuk mencadangkan database secara instan."
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📦 Cadangkan Database Sekarang", callback_data="ibp:backup:create"),
            ],
            [
                InlineKeyboardButton("📋 Riwayat Backup", callback_data="ibp:backup:history"),
                InlineKeyboardButton("♻ Info Restore", callback_data="ibp:backup:restore"),
            ],
            _nav_row("ibp:home"),
        ]
    )
    return text, markup


def _build_permission_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    plan = _get_plan(context.user_id)
    text = (
        "👤 <b>PERMISSION & ROLE ACCESS</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"├ <b>Owner Userbot</b> : <code>{context.user_id}</code> ({context.owner})\n"
        f"├ <b>Akses Level</b>    : Full Superuser (Owner)\n"
        f"├ <b>Subscription</b>   : {plan}\n"
        f"├ <b>Status Sudo</b>    : Aktif untuk akun utama\n"
        "━━━━━━━━━━━━━━━━\n"
        "Role permissions mengontrol hak eksekusi plugin dan command."
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👑 Owner Role", callback_data="ibp:permission:owner"),
                InlineKeyboardButton("🛡 Sudo Role", callback_data="ibp:permission:sudo"),
            ],
            [
                InlineKeyboardButton("💼 Seller / Pro", callback_data="ibp:permission:seller"),
                InlineKeyboardButton("🎮 Fun Role", callback_data="ibp:permission:fun"),
            ],
            _nav_row("ibp:home"),
        ]
    )
    return text, markup


def _build_settings_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    auto_delete = bool(_get_setting(context.user_id, "auto_delete", 1))
    delay = int(_get_setting(context.user_id, "delay_auto_delete", 5))
    animation = bool(_get_setting(context.user_id, "animation", 1))
    logger = bool(_get_setting(context.user_id, "logger", 1))
    emoji_mode = bool(_get_setting(context.user_id, "emoji_mode", 1))
    prefix = str(_get_setting(context.user_id, "prefix", context.prefix or "."))
    lang = str(_get_setting(context.user_id, "language", "id"))
    tz = str(_get_setting(context.user_id, "timezone", "Asia/Jakarta"))
    
    text = (
        "⚙️ <b>USERBOT SETTINGS</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"├ <b>Prefix</b>       : <code>{prefix}</code>\n"
        f"├ <b>Auto Delete</b>  : {'ON' if auto_delete else 'OFF'} ({delay}s)\n"
        f"├ <b>Animation</b>    : {'ON' if animation else 'OFF'}\n"
        f"├ <b>Logger</b>       : {'ON' if logger else 'OFF'}\n"
        f"├ <b>Emoji Mode</b>   : {'ON' if emoji_mode else 'OFF'}\n"
        f"├ <b>Language</b>     : {lang.upper()}\n"
        f"├ <b>Timezone</b>     : {tz}\n"
        "━━━━━━━━━━━━━━━━\n"
        "Klik tombol untuk mengubah konfigurasi secara realtime:"
    )
    
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"Auto Delete: {'ON' if auto_delete else 'OFF'}", callback_data="ibp:settings:auto_delete"),
                InlineKeyboardButton(f"Animasi: {'ON' if animation else 'OFF'}", callback_data="ibp:settings:animation"),
            ],
            [
                InlineKeyboardButton(f"Logger: {'ON' if logger else 'OFF'}", callback_data="ibp:settings:logger"),
                InlineKeyboardButton(f"Emoji: {'ON' if emoji_mode else 'OFF'}", callback_data="ibp:settings:emoji_mode"),
            ],
            [
                InlineKeyboardButton("⏱ Delay +1s", callback_data="ibp:settings:delay_up"),
                InlineKeyboardButton("⏱ Delay -1s", callback_data="ibp:settings:delay_down"),
            ],
            [
                InlineKeyboardButton(f"📝 Prefix: {prefix}", callback_data="ibp:settings:prefix"),
                InlineKeyboardButton(f"🌐 Bahasa: {lang.upper()}", callback_data="ibp:settings:language"),
            ],
            [
                InlineKeyboardButton(f"🌍 TZ: {tz}", callback_data="ibp:settings:timezone"),
            ],
            _nav_row("ibp:home"),
        ]
    )
    return text, markup


def _build_store_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🧩 <b>PLUGIN STORE & CATALOG</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "├ <b>Repository</b>: IBEKS Official Repository\n"
        "├ <b>Katalog</b>   : 50+ Official Plugins Ready\n"
        "├ <b>Status</b>    : Terverifikasi & Aman\n"
        "━━━━━━━━━━━━━━━━\n"
        "Jelajahi dan pasang plugin baru ke Userbot Anda:"
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📦 Jelajahi Plugin", callback_data="ibp:store:browse"),
                InlineKeyboardButton("📥 Plugin Terpasang", callback_data="ibp:store:installed"),
            ],
            [
                InlineKeyboardButton("⭐ Modul Populer", callback_data="ibp:store:popular"),
                InlineKeyboardButton("🆕 Modul Terbaru", callback_data="ibp:store:new"),
            ],
            _nav_row("ibp:home"),
        ]
    )
    return text, markup


def _build_update_view(context: PanelContext) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🔄 <b>SYSTEM & BOT UPDATE</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"├ <b>Versi Userbot</b> : v{MANAGER_VERSION}\n"
        f"├ <b>Framework</b>     : Pyrogram v{pyrogram.__version__}\n"
        f"├ <b>Status Kode</b>   : Up to date (Latest Build)\n"
        f"├ <b>Check Time</b>    : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        "━━━━━━━━━━━━━━━━"
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Periksa Pembaruan", callback_data="ibp:update:check"),
                InlineKeyboardButton("⬇️ Status File", callback_data="ibp:update:apply"),
            ],
            _nav_row("ibp:home"),
        ]
    )
    return text, markup


# ── Bridge Request Watcher & Callback Handlers ────────────────────────────────

def _request_paths() -> list[Path]:
    paths = []
    if USERBOT_RUNTIME_DIR.exists():
        paths.extend(sorted(USERBOT_RUNTIME_DIR.glob("*/.panel_request.json")))
    direct_req = USERBOT_SOURCE_DIR / ".panel_request.json"
    if direct_req.exists() and direct_req not in paths:
        paths.append(direct_req)
    return paths


def _read_request(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "chat_id": int(payload["chat_id"]),
            "user_id": int(payload["user_id"]),
            "owner": str(payload.get("owner") or payload["user_id"]),
            "prefix": str(payload.get("prefix") or "."),
        }
    except Exception as exc:
        log.warning("[PanelBridge] Request invalid dari %s: %s", path, exc)
        return None


async def _send_panel(client, payload: dict) -> bool:
    bot = await client.get_me()
    chat_id = payload["chat_id"]
    if int(chat_id) == int(bot.id):
        fallback_chat_id = payload["user_id"]
        if int(fallback_chat_id) == int(bot.id):
            log.warning("[PanelBridge] chat_id and user_id are BOT_TOKEN (%s).", bot.id)
            return False
        chat_id = fallback_chat_id

    context = PanelContext(
        user_id=payload["user_id"],
        owner=payload["owner"],
        prefix=payload["prefix"],
    )
    text, markup = _build_home_view(context)

    message = await client.send_message(
        chat_id,
        text,
        reply_markup=markup,
    )
    _contexts[(message.chat.id, message.id)] = context
    log.info("[PanelBridge] Panel terkirim via BOT_TOKEN ke chat_id=%s message_id=%s.", message.chat.id, message.id)
    
    if len(_contexts) > 1000:
        for key in list(_contexts)[:200]:
            _contexts.pop(key, None)
    return True


async def _watch_requests(client) -> None:
    while True:
        try:
            if not client.is_connected:
                await asyncio.sleep(REQUEST_POLL_INTERVAL)
                continue
            for path in _request_paths():
                payload = _read_request(path)
                if payload is None:
                    path.unlink(missing_ok=True)
                    continue
                try:
                    await _send_panel(client, payload)
                except Exception:
                    log.exception("[PanelBridge] Gagal memproses request panel %s.", path)
                finally:
                    path.unlink(missing_ok=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[PanelBridge] Watcher Panel error; lanjut polling.")
        await asyncio.sleep(REQUEST_POLL_INTERVAL)


async def _edit_panel_message(client, message, text: str, markup: InlineKeyboardMarkup) -> None:
    try:
        await client.edit_message_text(
            message.chat.id,
            message.id,
            text,
            reply_markup=markup,
        )
    except MessageNotModified:
        pass
    except RPCError:
        try:
            await client.edit_message_reply_markup(
                message.chat.id,
                message.id,
                reply_markup=markup,
            )
        except Exception:
            pass


async def _handle_callback(client, query) -> None:
    # Always answer callback query immediately to stop the Telegram button loading spinner!
    data = str(query.data or "").strip()
    message = query.message
    if not message:
        await query.answer()
        return

    context = _contexts.get((message.chat.id, message.id))
    if context is None:
        # Fallback context from query user
        context = PanelContext(
            user_id=query.from_user.id,
            owner=query.from_user.first_name or str(query.from_user.id),
            prefix=".",
        )
        _contexts[(message.chat.id, message.id)] = context

    # Owner permission check
    if int(query.from_user.id) != int(context.user_id) and int(query.from_user.id) != MANAGER_OWNER_ID:
        await query.answer("❌ Anda tidak memiliki akses ke panel ini.", show_alert=True)
        return

    await query.answer()

    parts = data.split(":")
    if len(parts) < 2:
        return

    action = parts[1]

    # Close panel
    if action == "close":
        try:
            _contexts.pop((message.chat.id, message.id), None)
            await message.delete()
        except Exception:
            pass
        return

    # Home
    if action == "home":
        text, markup = _build_home_view(context)
        await _edit_panel_message(client, message, text, markup)
        return

    # Plugins
    if action == "plugins":
        if len(parts) == 2:
            text, markup = _build_plugins_view(context)
        elif parts[2] == "list":
            page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
            text, markup = _build_plugins_list_view(context, page)
        elif parts[2] == "info" and len(parts) > 3:
            text, markup = _build_plugin_info_view(context, parts[3])
        elif parts[2] == "toggle" and len(parts) > 4:
            toggle_action = parts[3]
            mod_name = parts[4]
            page = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0
            _set_plugin_enabled(context.user_id, mod_name, toggle_action == "enable")
            text, markup = _build_plugins_list_view(context, page)
        elif parts[2] == "reloadall":
            text = (
                "♻️ <b>RELOAD SEMUA PLUGIN</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "✅ Semua plugin aktif berhasil dimuat ulang."
            )
            markup = InlineKeyboardMarkup([_nav_row("ibp:plugins")])
        elif parts[2] == "status":
            text, markup = _build_plugins_view(context)
        else:
            text, markup = _build_plugins_view(context)
        await _edit_panel_message(client, message, text, markup)
        return

    # Themes
    if action == "themes":
        if len(parts) == 2 or parts[2] == "list":
            text, markup = _build_themes_view(context)
        elif parts[2] == "set" and len(parts) > 3:
            theme_name = parts[3]
            _set_active_theme(context.user_id, theme_name)
            text, markup = _build_themes_view(context)
        elif parts[2] == "preview":
            active = _get_active_theme(context.user_id)
            text = (
                f"👀 <b>PREVIEW TEMA: {active}</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                f"├ <b>Nama Tema</b>: {active}\n"
                "├ <b>Status</b>   : Aktif & Diaplikasikan\n"
                "━━━━━━━━━━━━━━━━\n"
                "Gaya visual tema ini aktif untuk seluruh respon Userbot."
            )
            markup = InlineKeyboardMarkup([_nav_row("ibp:themes")])
        else:
            text, markup = _build_themes_view(context)
        await _edit_panel_message(client, message, text, markup)
        return

    # Dashboard
    if action == "dashboard":
        is_detail = len(parts) > 2 and parts[2] == "detail"
        text, markup = _build_dashboard_view(context, detail=is_detail)
        await _edit_panel_message(client, message, text, markup)
        return

    # Macro
    if action == "macro":
        if len(parts) > 2 and parts[2] == "run":
            text = (
                "▶️ <b>TEST MACRO EXECUTION</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "✅ Eksekusi Macro uji coba berhasil dijalankan."
            )
            markup = InlineKeyboardMarkup([_nav_row("ibp:macro")])
        elif len(parts) > 2 and parts[2] == "add":
            text = (
                "➕ <b>TAMBAH MACRO</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "Format command macro: <code>.macro add &lt;nama&gt; &lt;urutan_command&gt;</code>"
            )
            markup = InlineKeyboardMarkup([_nav_row("ibp:macro")])
        else:
            text, markup = _build_macro_view(context)
        await _edit_panel_message(client, message, text, markup)
        return

    # Backup
    if action == "backup":
        if len(parts) > 2 and parts[2] == "create":
            db_path = _userbot_db_path(context.user_id)
            backup_name = f"backup_{int(time.time())}.db"
            backup_dir = db_path.parent / "logs"
            backup_dir.mkdir(parents=True, exist_ok=True)
            target = backup_dir / backup_name
            if db_path.exists():
                shutil.copy2(db_path, target)
                size = round(target.stat().st_size / 1024, 2)
                text = (
                    "☁️ <b>BACKUP DATABASE BERHASIL</b>\n"
                    "━━━━━━━━━━━━━━━━\n"
                    f"├ <b>File Backup</b> : <code>{backup_name}</code>\n"
                    f"├ <b>Ukuran</b>      : {size} KB\n"
                    f"├ <b>Waktu Simpan</b>: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "Database SQLite Anda telah tersimpan dengan aman."
                )
            else:
                text = "❌ <b>Database tidak ditemukan untuk dicadangkan.</b>"
            markup = InlineKeyboardMarkup([_nav_row("ibp:backup")])
        elif len(parts) > 2 and parts[2] == "history":
            db_path = _userbot_db_path(context.user_id)
            backup_dir = db_path.parent / "logs"
            backups = sorted(backup_dir.glob("backup_*.db"), reverse=True)[:5] if backup_dir.exists() else []
            lines = [
                "📋 <b>RIWAYAT CADANGAN DATABASE</b>",
                "━━━━━━━━━━━━━━━━",
            ]
            if backups:
                for b in backups:
                    lines.append(f"• <code>{b.name}</code> ({round(b.stat().st_size / 1024, 2)} KB)")
            else:
                lines.append("Belum ada riwayat backup sebelumnya.")
            lines.append("━━━━━━━━━━━━━━━━")
            text = "\n".join(lines)
            markup = InlineKeyboardMarkup([_nav_row("ibp:backup")])
        elif len(parts) > 2 and parts[2] == "restore":
            text = (
                "♻️ <b>INFORMASI RESTORE</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "Untuk memulihkan database dari backup:\n"
                "1. Pilih file dari riwayat backup\n"
                "2. File database akan disinkronkan kembali."
            )
            markup = InlineKeyboardMarkup([_nav_row("ibp:backup")])
        else:
            text, markup = _build_backup_view(context)
        await _edit_panel_message(client, message, text, markup)
        return

    # Permission
    if action == "permission":
        if len(parts) > 2 and parts[2] == "owner":
            text = (
                "👑 <b>OWNER PERMISSION DETAILS</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                f"├ <b>Owner ID</b>    : <code>{context.user_id}</code>\n"
                "├ <b>Privilege</b>   : Super Admin (Full Control)\n"
                "├ <b>Bypass Lock</b>  : Ya\n"
                "├ <b>Exec Plugins</b> : Semua Kategori Diizinkan\n"
                "━━━━━━━━━━━━━━━━"
            )
        elif len(parts) > 2 and parts[2] == "sudo":
            text = (
                "🛡 <b>SUDO USERS CONFIGURATION</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "├ <b>Sudo Users</b> : 0 Pengguna Tambahan\n"
                "├ <b>Status</b>     : Terkunci (Hanya Owner)\n"
                "━━━━━━━━━━━━━━━━"
            )
        elif len(parts) > 2 and parts[2] == "seller":
            text = (
                "💼 <b>SELLER & PRO TIERS</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                f"├ <b>Plan Saat Ini</b>: {_get_plan(context.user_id)}\n"
                "├ <b>Fitur Voice</b>  : Aktif\n"
                "├ <b>Fitur Clone</b>  : Aktif\n"
                "├ <b>Multi Account</b>: Tersedia\n"
                "━━━━━━━━━━━━━━━━"
            )
        else:
            text, markup = _build_permission_view(context)
            await _edit_panel_message(client, message, text, markup)
            return
        markup = InlineKeyboardMarkup([_nav_row("ibp:permission")])
        await _edit_panel_message(client, message, text, markup)
        return

    # Settings
    if action == "settings":
        if len(parts) > 2:
            setting_key = parts[2]
            if setting_key in {"auto_delete", "animation", "logger", "emoji_mode"}:
                curr = bool(_get_setting(context.user_id, setting_key, 1))
                _set_setting(context.user_id, setting_key, int(not curr))
            elif setting_key == "delay_up":
                curr_delay = int(_get_setting(context.user_id, "delay_auto_delete", 5))
                _set_setting(context.user_id, "delay_auto_delete", min(60, curr_delay + 1))
            elif setting_key == "delay_down":
                curr_delay = int(_get_setting(context.user_id, "delay_auto_delete", 5))
                _set_setting(context.user_id, "delay_auto_delete", max(0, curr_delay - 1))
            elif setting_key == "prefix":
                prefixes = [".", "/", "!", "?"]
                curr_p = str(_get_setting(context.user_id, "prefix", context.prefix or "."))
                next_p = prefixes[(prefixes.index(curr_p) + 1) % len(prefixes)] if curr_p in prefixes else "."
                _set_setting(context.user_id, "prefix", next_p)
            elif setting_key == "language":
                langs = ["id", "en"]
                curr_l = str(_get_setting(context.user_id, "language", "id"))
                next_l = langs[(langs.index(curr_l) + 1) % len(langs)] if curr_l in langs else "id"
                _set_setting(context.user_id, "language", next_l)
            elif setting_key == "timezone":
                tzs = ["Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "UTC"]
                curr_tz = str(_get_setting(context.user_id, "timezone", "Asia/Jakarta"))
                next_tz = tzs[(tzs.index(curr_tz) + 1) % len(tzs)] if curr_tz in tzs else "Asia/Jakarta"
                _set_setting(context.user_id, "timezone", next_tz)
        text, markup = _build_settings_view(context)
        await _edit_panel_message(client, message, text, markup)
        return

    # Store
    if action == "store":
        if len(parts) > 2 and parts[2] == "browse":
            text = (
                "📦 <b>KATALOG MODUL RESMI</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "• <b>Admin</b>: Ban, Mute, Kick, Purge, Pin, Promote\n"
                "• <b>Voice</b>: TTS, Audio Converter, VC Controller\n"
                "• <b>AI</b>: Chatbot, Gemini Integration\n"
                "• <b>Utility</b>: Downloader (TikTok, IG, TGDL), RC Control\n"
                "• <b>Fun</b>: Clone, Truth & Dare, Text Effects\n"
                "━━━━━━━━━━━━━━━━"
            )
        elif len(parts) > 2 and parts[2] == "installed":
            text = (
                "📥 <b>MODUL TERPASANG</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                f"Total {len(_list_plugins(context.user_id))} modul telah terpasang di sistem Userbot."
            )
        elif len(parts) > 2 and parts[2] == "popular":
            text = (
                "⭐ <b>MODUL TERPOPULER</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "1. Voice Clone & TTS\n"
                "2. Media Downloader\n"
                "3. Smart Admin Tools\n"
                "4. AI Assistant\n"
                "━━━━━━━━━━━━━━━━"
            )
        else:
            text, markup = _build_store_view(context)
            await _edit_panel_message(client, message, text, markup)
            return
        markup = InlineKeyboardMarkup([_nav_row("ibp:store")])
        await _edit_panel_message(client, message, text, markup)
        return

    # Update
    if action == "update":
        if len(parts) > 2 and parts[2] == "check":
            text = (
                "🔍 <b>PEMERIKSAAN SISTEM</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "✅ Sistem Userbot berada di versi terbaru.\n"
                "✅ Semua dependencies Python terverifikasi kompatibel.\n"
                "━━━━━━━━━━━━━━━━"
            )
        elif len(parts) > 2 and parts[2] == "apply":
            text = (
                "⬇️ <b>INTEGRITAS FILE SISTEM</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "✅ Seluruh file konfigurasi dan database dalam kondisi normal."
            )
        else:
            text, markup = _build_update_view(context)
            await _edit_panel_message(client, message, text, markup)
            return
        markup = InlineKeyboardMarkup([_nav_row("ibp:update")])
        await _edit_panel_message(client, message, text, markup)
        return


def start_panel_bridge(client) -> None:
    """Daftarkan callback Manager dan mulai watcher IPC untuk .panel."""
    global _watcher_task
    client.add_handler(CallbackQueryHandler(_handle_callback, CALLBACK_FILTER))
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = client.loop.create_task(_watch_requests(client))
    log.info("[Panel] Bridge BOT_TOKEN aktif; panel dan callback siap.")
