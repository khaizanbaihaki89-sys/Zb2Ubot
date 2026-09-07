"""Scanner katalog help menu dari struktur plugin dan source command."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from config import PLUGINS_DIR
from loader import plugin_category


@dataclass(frozen=True)
class PluginInfo:
    """Informasi satu file plugin yang memiliki command."""

    category_key: str
    category_name: str
    name: str
    commands: tuple[str, ...]


def _command_names(source: str) -> tuple[str, ...]:
    """Ambil semua nama command dari pemanggilan dynamic_command(...)."""
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

    return tuple(sorted(commands))


def scan_plugins() -> dict[str, list[PluginInfo]]:
    """Scan plugin files dan kembalikan katalog berdasarkan folder kategori."""
    root = Path(PLUGINS_DIR)
    catalog: dict[str, list[PluginInfo]] = {}

    if not root.exists():
        return catalog

    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if (
            path.name == "__init__.py"
            or "__pycache__" in relative.parts
            or "utils" in relative.parts
            or len(relative.parts) < 2
        ):
            continue

        commands = _command_names(path.read_text(encoding="utf-8"))
        if not commands:
            continue

        category_key = relative.parts[0]
        module_name = f"plugins.{'.'.join(relative.with_suffix('').parts)}"
        category_name = plugin_category(module_name)
        info = PluginInfo(
            category_key=category_key,
            category_name=category_name,
            name=path.stem,
            commands=commands,
        )
        catalog.setdefault(category_key, []).append(info)

    for plugins in catalog.values():
        plugins.sort(key=lambda item: item.name.casefold())

    return dict(sorted(catalog.items(), key=lambda item: item[1][0].category_name.casefold()))


def category_commands(plugins: list[PluginInfo]) -> list[str]:
    """Gabungkan command seluruh plugin dalam satu kategori."""
    return sorted(
        (command for plugin in plugins for command in plugin.commands),
        key=str.casefold,
    )


def total_commands(catalog: dict[str, list[PluginInfo]]) -> int:
    """Hitung total command dari seluruh kategori."""
    return sum(len(category_commands(plugins)) for plugins in catalog.values())