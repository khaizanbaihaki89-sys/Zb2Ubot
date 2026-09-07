"""Inline keyboard definitions for the IBEKS Control Panel foundation."""

from __future__ import annotations

from utils.control_ui import keyboard


def _cb(*parts: str) -> str:
    return ":".join(("ibp", *parts))


def nav_rows(back: str = "ibp:home") -> list[list[tuple[str, str]]]:
    return [[
        ("⬅ Back", back),
        ("🏠 Home", _cb("home")),
        ("❌ Close", _cb("close")),
    ]]


def home() -> object:
    return keyboard(
        [
            [("📦 Plugin Manager", _cb("plugins")), ("🎨 Theme Engine", _cb("themes"))],
            [("📊 Dashboard", _cb("dashboard")), ("⚡ Macro", _cb("macro"))],
            [("☁️ Backup", _cb("backup")), ("👤 Permission", _cb("permission"))],
            [("⚙️ Settings", _cb("settings")), ("🧩 Plugin Store", _cb("store"))],
            [("🔄 Update", _cb("update"))],
            [("❌ Close", _cb("close"))],
        ]
    )


def plugin(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("📋 List Plugin", _cb("plugins", "list"))],
            [("➕ Enable Plugin", _cb("plugins", "enable"))],
            [("➖ Disable Plugin", _cb("plugins", "disable"))],
            [("♻️ Reload Plugin", _cb("plugins", "reload"))],
            [("ℹ️ Plugin Info", _cb("plugins", "info"))],
            [("📊 Plugin Status", _cb("plugins", "status"))],
            *nav_rows(back),
        ]
    )


def theme(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("📋 Theme List", _cb("themes", "list"))],
            [("👀 Preview Theme", _cb("themes", "preview"))],
            [("✅ Apply Theme", _cb("themes", "apply"))],
            [("⚙ Theme Setting", _cb("themes", "settings"))],
            *nav_rows(back),
        ]
    )


def dashboard(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("🔄 Refresh", _cb("dashboard", "refresh"))],
            [("📄 Detail", _cb("dashboard", "detail"))],
            *nav_rows(back),
        ]
    )


def macro(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("➕ Add Macro", _cb("macro", "add"))],
            [("📋 List Macro", _cb("macro", "list"))],
            [("✏ Edit Macro", _cb("macro", "edit"))],
            [("🗑 Delete Macro", _cb("macro", "delete"))],
            [("▶ Run Macro", _cb("macro", "run"))],
            *nav_rows(back),
        ]
    )


def backup(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("📦 Backup", _cb("backup", "create"))],
            [("♻ Restore", _cb("backup", "restore"))],
            [("📋 History", _cb("backup", "history"))],
            *nav_rows(back),
        ]
    )


def permission(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("Owner", _cb("permission", "owner"))],
            [("Sudo", _cb("permission", "sudo"))],
            [("Seller", _cb("permission", "seller"))],
            [("Pro", _cb("permission", "pro"))],
            [("Fun User", _cb("permission", "fun"))],
            *nav_rows(back),
        ]
    )


def settings(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("Prefix", _cb("settings", "prefix"))],
            [("Theme", _cb("settings", "theme"))],
            [("Animation", _cb("settings", "animation"))],
            [("Logger", _cb("settings", "logger"))],
            [("Auto Delete", _cb("settings", "auto_delete"))],
            [("Timezone", _cb("settings", "timezone"))],
            [("Language", _cb("settings", "language"))],
            *nav_rows(back),
        ]
    )


def store(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("📦 Browse Plugin", _cb("store", "browse"))],
            [("📥 Installed", _cb("store", "installed"))],
            [("⭐ Popular", _cb("store", "popular"))],
            [("🆕 New Plugin", _cb("store", "new"))],
            *nav_rows(back),
        ]
    )


def update(back: str = "ibp:home") -> object:
    return keyboard(
        [
            [("🔍 Check Update", _cb("update", "check"))],
            [("⬇ Update Plugin", _cb("update", "apply"))],
            [("♻ Rollback", _cb("update", "rollback"))],
            *nav_rows(back),
        ]
    )


def page(page_name: str, back: str = "ibp:home") -> object:
    builders = {
        "plugins": plugin,
        "themes": theme,
        "dashboard": dashboard,
        "macro": macro,
        "backup": backup,
        "permission": permission,
        "settings": settings,
        "store": store,
        "update": update,
    }
    return builders[page_name](back)