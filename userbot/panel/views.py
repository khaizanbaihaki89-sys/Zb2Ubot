"""Text views for the stage-one Control Panel foundation."""

from __future__ import annotations

from . import buttons
from .utils import home_values


def home(update) -> tuple[str, object]:
    values = home_values(update)
    text = (
        "🟢 IBEKS CONTROL PANEL\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"👤 Owner      : {values['owner']}\n"
        f"👑 Plan       : {values['plan']}\n"
        f"📦 Plugin     : {values['total_plugin']}\n"
        f"🟢 Active     : {values['plugin_active']}\n"
        f"🔴 Disabled   : {values['plugin_disable']}\n"
        f"⚙ Prefix     : {values['prefix']}\n"
        f"🎨 Theme      : {values['theme']}\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "Pilih menu di bawah.\n\n"
        "⨱ IBEKS USERBOT ⨱"
    )
    return text, buttons.home()


def plugins(update) -> tuple[str, object]:
    return (
        "📦 Plugin Manager\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Plugin Manager akan dikembangkan pada tahap berikutnya.",
        buttons.plugin(),
    )


def themes(_update) -> tuple[str, object]:
    return (
        "🎨 Theme Engine\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Theme Engine akan dikembangkan pada tahap berikutnya.",
        buttons.theme(),
    )


def dashboard(_update) -> tuple[str, object]:
    return (
        "📊 Dashboard\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Dashboard akan dikembangkan pada tahap berikutnya.",
        buttons.dashboard(),
    )


def macro(_update) -> tuple[str, object]:
    return (
        "⚡ Macro\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Macro akan dikembangkan pada tahap berikutnya.",
        buttons.macro(),
    )


def backup(_update) -> tuple[str, object]:
    return (
        "☁️ Backup\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Backup akan dikembangkan pada tahap berikutnya.",
        buttons.backup(),
    )


def permission(_update) -> tuple[str, object]:
    return (
        "👤 Permission\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Permission akan dikembangkan pada tahap berikutnya.",
        buttons.permission(),
    )


def settings(_update) -> tuple[str, object]:
    return (
        "⚙️ Settings\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Settings akan dikembangkan pada tahap berikutnya.",
        buttons.settings(),
    )


def store(_update) -> tuple[str, object]:
    return (
        "🧩 Plugin Store\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Plugin Store akan dikembangkan pada tahap berikutnya.",
        buttons.store(),
    )


def update(_update) -> tuple[str, object]:
    return (
        "🔄 Update\n\n"
        "Placeholder Tahap 1.\n"
        "Fitur Update akan dikembangkan pada tahap berikutnya.",
        buttons.update(),
    )


def placeholder(page_name: str, action: str, update) -> tuple[str, object]:
    labels = {
        "plugins": "📦 Plugin Manager",
        "themes": "🎨 Theme Engine",
        "dashboard": "📊 Dashboard",
        "macro": "⚡ Macro",
        "backup": "☁️ Backup",
        "permission": "👤 Permission",
        "settings": "⚙️ Settings",
        "store": "🧩 Plugin Store",
        "update": "🔄 Update",
    }
    return (
        f"{labels[page_name]}\n\n"
        f"Placeholder: {action.replace('_', ' ').title()}.\n"
        "Fitur ini akan dikembangkan pada tahap berikutnya.",
        buttons.page(page_name, f"ibp:{page_name}"),
    )


def for_page(page_name: str, update) -> tuple[str, object]:
    return {
        "plugins": plugins,
        "themes": themes,
        "dashboard": dashboard,
        "macro": macro,
        "backup": backup,
        "permission": permission,
        "settings": settings,
        "store": store,
        "update": update,
    }[page_name](update)