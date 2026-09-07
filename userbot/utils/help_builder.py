"""Builder untuk sistem inline help Userbot.

Katalog command sengaja dibaca langsung dari ``plugins/``. Dengan begitu,
folder kategori dan file plugin baru ikut tampil tanpa daftar manual.
"""

from __future__ import annotations

import ast
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.formatter import DEFAULT_FOOTER, format_ui, to_small_caps

try:
    from config import PLUGINS_DIR
except (ImportError, AttributeError):
    PLUGINS_DIR = str(Path(__file__).resolve().parents[1] / "plugins")

try:
    from config import MANAGER_DATABASE_PATH
except (ImportError, AttributeError):
    MANAGER_DATABASE_PATH = str(
        Path(__file__).resolve().parents[2] / "manager" / "database.db"
    )


HELP_FOOTER = DEFAULT_FOOTER
PAGE_SIZE = 8
UTILITY_DESCRIPTIONS = {
    "tt": "Download TikTok",
    "ig": "Download Instagram",
    "tgdl": "Download Telegram Private",
}


def _voice_help_lines(prefix: str) -> list[str]:
    """Susun daftar lengkap command Voice Clone/TTS."""
    return [
        f"• {prefix}voice",
        f"• {prefix}voice add",
        f"• {prefix}voice <nama> <teks>",
        f"• {prefix}voice list",
        f"• {prefix}voice delete <nama>",
        f"• {prefix}voice diag",
        f"• {prefix}joinvc",
    ]
@dataclass(frozen=True)
class PluginInfo:
    """Informasi command dari satu file plugin."""

    name: str
    commands: tuple[str, ...]


@dataclass(frozen=True)
class CategoryInfo:
    """Informasi kategori yang berasal dari satu folder plugins/."""

    key: str
    name: str
    plugins: tuple[PluginInfo, ...]

    @property
    def commands(self) -> tuple[str, ...]:
        return tuple(
            command
            for plugin in self.plugins
            for command in plugin.commands
        )


def _category_name(folder_name: str) -> str:
    """Buat label dari nama folder, tanpa mapping kategori hardcode."""
    if folder_name.casefold() == "utility":
        return "🛠️ Utility"
    return folder_name.replace("-", " ").replace("_", " ").title()


def _command_names(source: str) -> tuple[str, ...]:
    """Ambil nama command dari pemanggilan dynamic_command(...)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()

    commands: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "dynamic_command":
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                if argument.value not in commands:
                    commands.append(argument.value)
    return tuple(sorted(commands, key=str.casefold))


def scan_plugins(root: str | Path | None = None) -> dict[str, CategoryInfo]:
    """Scan file plugin secara rekursif dan kelompokkan berdasarkan folder."""
    root = Path(root) if root is not None else Path(PLUGINS_DIR)
    categories: dict[str, list[PluginInfo]] = {}

    if not root.exists():
        return {}

    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if path.name == "__init__.py" or "__pycache__" in relative.parts:
            continue

        commands = _command_names(path.read_text(encoding="utf-8"))
        if not commands:
            continue

        if len(relative.parts) < 2 or "utils" in relative.parts:
            continue
        category_key = relative.parts[0]
        categories.setdefault(category_key, []).append(
            PluginInfo(name=path.stem, commands=commands)
        )

    result: dict[str, CategoryInfo] = {}
    for key, plugins in sorted(
        categories.items(),
        key=lambda item: _category_name(item[0]).casefold(),
    ):
        result[key] = CategoryInfo(
            key=key,
            name=_category_name(key),
            plugins=tuple(sorted(plugins, key=lambda item: item.name.casefold())),
        )
    return result


def total_plugins(catalog: dict[str, CategoryInfo]) -> int:
    """Jumlah file plugin yang memiliki command."""
    return sum(len(category.plugins) for category in catalog.values())


def total_commands(catalog: dict[str, CategoryInfo]) -> int:
    """Jumlah command yang ditemukan di seluruh plugin."""
    return sum(len(category.commands) for category in catalog.values())


def page_count(catalog: dict[str, CategoryInfo]) -> int:
    """Jumlah halaman kategori, minimal satu agar tombol navigasi tetap valid."""
    return max(1, (len(catalog) + PAGE_SIZE - 1) // PAGE_SIZE)


def clamp_page(catalog: dict[str, CategoryInfo], page: int) -> int:
    """Batasi nomor halaman ke rentang yang tersedia."""
    return max(0, min(page, page_count(catalog) - 1))


def categories_for_page(
    catalog: dict[str, CategoryInfo],
    page: int,
) -> list[CategoryInfo]:
    """Kembalikan maksimal delapan kategori untuk satu halaman."""
    current_page = clamp_page(catalog, page)
    start = current_page * PAGE_SIZE
    return list(catalog.values())[start:start + PAGE_SIZE]


def _button(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def home_keyboard(
    catalog: dict[str, CategoryInfo],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Keyboard home: dua kolom kategori dan navigasi halaman.

    Untuk katalog satu halaman, Back tetap disediakan agar layout navigasi
    selalu memiliki aksi eksplisit selain Home.
    """
    current_page = clamp_page(catalog, page)
    categories = categories_for_page(catalog, current_page)
    rows = [
        [
            _button(category.name, f"help_category:{category.key}:{current_page}")
            for category in categories[index:index + 2]
        ]
        for index in range(0, len(categories), 2)
    ]
    if page_count(catalog) == 1:
        rows.append(
            [
                _button("⬅️ Back", "help_back:0"),
                _button("🏠 Home", "help_home"),
            ]
        )
    else:
        previous_page = max(0, current_page - 1)
        next_page = min(page_count(catalog) - 1, current_page + 1)
        rows.append(
            [
                _button("◀️", f"help_page:{previous_page}"),
                _button("🏠 Home", "help_home"),
                _button("▶️", f"help_page:{next_page}"),
            ]
        )
    return InlineKeyboardMarkup(rows)


def category_keyboard(previous_page: int = 0) -> InlineKeyboardMarkup:
    """Keyboard detail kategori dengan satu tombol kembali."""
    return InlineKeyboardMarkup(
        [[_button("⬅ Back", f"help_back:{max(0, previous_page)}")]]
    )


def get_plan(
    user_id: int,
    manager_database_path: str | Path | None = None,
) -> str:
    """Ambil plan dari database Manager tanpa mengubah database Userbot."""
    try:
        database_path = (
            Path(manager_database_path)
            if manager_database_path is not None
            else Path(MANAGER_DATABASE_PATH)
        )
        with sqlite3.connect(database_path) as connection:
            row = connection.execute(
                "SELECT plan FROM users WHERE telegram_id = ?",
                (user_id,),
            ).fetchone()
        return (row[0] if row and row[0] else "FREE").upper()
    except (OSError, sqlite3.Error):
        return "FREE"


def build_home_text(
    *,
    plan: str,
    prefix: str,
    plugins: int,
    owner: str,
    page: int,
    pages: int,
) -> str:
    """Susun teks home sesuai format visual resmi IBEKS."""
    lines = [
        f"👑 Plan : {plan}",
        f"⚡ Prefix : <code>{prefix}</code>",
        f"🧩 Plugins : {plugins}",
        f"👤 Owner : {owner}",
        "",
        f"📚 Categories — Page {page + 1}/{pages}",
    ]
    return format_ui(
        title="IBEKS USERBOT",
        body=lines,
        emoji="🟢",
    )


def build_category_text(
    *,
    category: CategoryInfo,
    plan: str,
    prefix: str,
    plugins: int,
    owner: str,
) -> str:
    """Susun halaman detail command satu kategori."""
    lines = [
        f"👑 Plan : {plan}",
        f"⚡ Prefix : <code>{prefix}</code>",
        f"👤 Owner : {owner}",
        "",
    ]
    if category.key == "voice":
        lines.extend(_voice_help_lines(prefix))
    else:
        for command in category.commands:
            description = (
                f" — {UTILITY_DESCRIPTIONS[command]}"
                if category.key == "utility" and command in UTILITY_DESCRIPTIONS
                else ""
            )
            lines.append(f"• <code>{prefix}{command}</code>{description}")

    return format_ui(
        title=category.name,
        body=lines,
        emoji="📂",
    )

