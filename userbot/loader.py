"""
IBEKS USERBOT - Plugin Loader
Memuat semua plugin dalam folder plugins/ secara otomatis.
Tidak ada import manual yang diperlukan.

Setiap plugin dapat mendaftarkan handler ke instance client dengan cara
menyediakan fungsi `setup(client)` yang berisi decorator `@client.on_message(...)`.
"""

import importlib
import ast
import os
import sys
import traceback
from datetime import datetime
from typing import Any

from utils.logger import log
from config import PLUGINS_DIR
from db import (
    get_plugin_status,
    set_plugin_runtime,
    upsert_plugin_status,
)


_PLUGIN_STATS = {
    "loaded": [],
    "failed": [],
    "failed_details": [],
}
_PLUGIN_HANDLERS: dict[str, list[tuple[Any, int]]] = {}
_PLUGIN_MODULES: dict[str, Any] = {}
_HANDLER_PATCHED = False


def plugin_filename(module_name: str) -> str:
    """Ubah nama modul menjadi nama file plugin untuk ditampilkan."""
    return f"{module_name.rsplit('.', 1)[-1]}.py"


def plugin_category(module_name: str) -> str:
    """Kembalikan kategori folder plugin dengan nama tampilan yang konsisten."""
    parts = module_name.split(".")
    category = parts[-2] if len(parts) > 1 else "other"
    return {
        "admin": "Permission",
        "ai": "AI",
        "animasi": "Animasi",
        "broadcast": "Broadcast",
        "core": "Core",
        "fun": "Fun",
        "permission": "Permission",
        "utility": "Utility",
        "voice": "Voice",
    }.get(category, category.replace("_", " ").title())


def get_plugin_stats() -> dict:
    """Ambil salinan statistik plugin terakhir yang dimuat."""
    return {
        "loaded": list(_PLUGIN_STATS["loaded"]),
        "failed": list(_PLUGIN_STATS["failed"]),
        "failed_details": [dict(item) for item in _PLUGIN_STATS["failed_details"]],
    }


def _plugin_metadata(module_name: str, filepath: str) -> dict:
    """Ambil metadata ringan dari module source tanpa memaksa plugin baru."""
    version = "1.0.0"
    author = "IBEKS"
    command_names: set[str] = set()
    try:
        with open(filepath, "r", encoding="utf-8") as source:
            tree = ast.parse(source.read(), filename=filepath)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"__version__", "VERSION"}:
                        if isinstance(node.value, ast.Constant):
                            version = str(node.value.value)
                    if isinstance(target, ast.Name) and target.id in {"__author__", "AUTHOR"}:
                        if isinstance(node.value, ast.Constant):
                            author = str(node.value.value)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "dynamic_command"
            ):
                for argument in node.args:
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        command_names.add(argument.value)
        command_count = len(command_names)
    except Exception as exc:
        log.debug("[Loader] Metadata plugin gagal %s: %s", module_name, exc)
    return {
        "module": module_name,
        "filename": plugin_filename(module_name),
        "category": plugin_category(module_name),
        "version": version,
        "author": author,
        "command_count": command_count,
        "file_size": os.path.getsize(filepath) if os.path.exists(filepath) else 0,
        "file_path": filepath,
    }


def _patch_handler_registry(client) -> None:
    """Catat handler tanpa mengubah kontrak decorator plugin lama."""
    global _HANDLER_PATCHED
    if _HANDLER_PATCHED:
        return
    original_add_handler = client.add_handler

    def add_handler(handler, group=0):
        result = original_add_handler(handler, group)
        module_name = getattr(
            getattr(handler, "callback", None), "__module__", None
        )
        if module_name and module_name.startswith("plugins."):
            _PLUGIN_HANDLERS.setdefault(module_name, []).append((handler, group))
        return result

    add_handler._ibeks_registry_patch = True
    client.add_handler = add_handler
    _HANDLER_PATCHED = True


def _remove_plugin_handlers(client, module_name: str) -> None:
    for handler, group in _PLUGIN_HANDLERS.pop(module_name, []):
        try:
            client.remove_handler(handler, group)
        except Exception as exc:
            log.warning("[Loader] Gagal melepas handler %s: %s", module_name, exc)


def _set_runtime(module_name: str, loaded: bool, error: str | None = None) -> None:
    try:
        set_plugin_runtime(
            module_name,
            loaded=loaded,
            loaded_at=datetime.now().astimezone().isoformat() if loaded else None,
            last_error=error,
        )
    except Exception as exc:
        log.warning("[Loader] Gagal menyimpan status runtime %s: %s", module_name, exc)


def _find_plugin_files() -> dict[str, str]:
    files = {}
    userbot_dir = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, names in os.walk(PLUGINS_DIR):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", "utils"}]
        for filename in sorted(names):
            if (
                not filename.endswith(".py")
                or filename.startswith("_")
                or filename == "__init__.py"
            ):
                continue
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, userbot_dir)
            files[rel_path.replace(os.sep, ".").removesuffix(".py")] = filepath
    return files


def load_plugins(client) -> dict:
    """
    Scan seluruh subdirektori dalam PLUGINS_DIR, import setiap file .py,
    lalu panggil `setup(client)` jika tersedia.

    Parameters
    ----------
    client : pyrogram.Client
        Instance client Pyrogram yang aktif.

    Returns
    -------
    dict
        {'loaded': list nama modul berhasil, 'failed': list nama modul gagal}
    """
    _patch_handler_registry(client)
    loaded = []
    failed = []
    failed_details = []

    # Tambahkan direktori userbot ke sys.path agar import relatif berjalan
    userbot_dir = os.path.dirname(os.path.abspath(__file__))
    if userbot_dir not in sys.path:
        sys.path.insert(0, userbot_dir)

    for module_name, filepath in _find_plugin_files().items():
        metadata = _plugin_metadata(module_name, filepath)
        upsert_plugin_status(metadata)
        stored = get_plugin_status(module_name)
        if stored and not stored["enabled"]:
            _set_runtime(module_name, False, None)
            continue

        try:
            module = importlib.import_module(module_name)

            # Panggil setup(client) jika plugin menyediakannya
            setup = getattr(module, "setup", None)
            if not callable(setup):
                raise TypeError("Plugin tidak memiliki fungsi setup(client)")

            _PLUGIN_HANDLERS.pop(module_name, None)
            setup(client)
            _PLUGIN_MODULES[module_name] = module
            _set_runtime(module_name, True)
            log.info(f"[Loader] ✓ Plugin aktif: {module_name}")

            loaded.append(module_name)
        except Exception as exc:
            err = traceback.format_exc()
            _set_runtime(module_name, False, str(exc).strip() or type(exc).__name__)
            log.error(f"[Loader] ✗ Gagal memuat plugin {module_name}: {exc}\n{err}")
            failed.append(module_name)
            failed_details.append(
                {
                    "module": module_name,
                    "filename": plugin_filename(module_name),
                    "category": plugin_category(module_name),
                    "error_type": type(exc).__name__,
                    "reason": str(exc).strip() or type(exc).__name__,
                }
            )

    log.info(f"[Loader] Total plugin: {len(loaded)} berhasil, {len(failed)} gagal.")
    if failed:
        log.warning(f"[Loader] Plugin gagal: {failed}")

    _PLUGIN_STATS["loaded"] = loaded
    _PLUGIN_STATS["failed"] = failed
    _PLUGIN_STATS["failed_details"] = failed_details
    return get_plugin_stats()


def plugin_modules() -> list[str]:
    """Kembalikan module plugin yang sedang aktif di runtime."""
    return sorted(_PLUGIN_MODULES)


def enable_plugin(module_name: str) -> bool:
    """Aktifkan plugin pada database; berlaku saat reload atau restart."""
    from db import set_plugin_enabled
    if not get_plugin_status(module_name):
        return False
    set_plugin_enabled(module_name, True)
    return True


def disable_plugin(client, module_name: str) -> bool:
    """Nonaktifkan plugin dan lepaskan semua handler aktifnya."""
    from db import set_plugin_enabled
    if not get_plugin_status(module_name):
        return False
    _remove_plugin_handlers(client, module_name)
    _PLUGIN_MODULES.pop(module_name, None)
    set_plugin_enabled(module_name, False)
    _set_runtime(module_name, False)
    _PLUGIN_STATS["loaded"] = [name for name in _PLUGIN_STATS["loaded"] if name != module_name]
    return True


def reload_plugin(client, module_name: str) -> tuple[bool, str]:
    """Reload satu plugin dengan kontrak setup(client) yang sama."""
    status = get_plugin_status(module_name)
    if not status:
        return False, "Plugin tidak ditemukan."
    if not status["enabled"]:
        return False, "Plugin sedang nonaktif. Enable terlebih dahulu."
    _remove_plugin_handlers(client, module_name)
    try:
        module = _PLUGIN_MODULES.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
        else:
            module = importlib.reload(module)
        setup = getattr(module, "setup", None)
        if not callable(setup):
            raise TypeError("Plugin tidak memiliki fungsi setup(client)")
        setup(client)
        _PLUGIN_MODULES[module_name] = module
        if module_name not in _PLUGIN_STATS["loaded"]:
            _PLUGIN_STATS["loaded"].append(module_name)
        _set_runtime(module_name, True)
        return True, "Plugin berhasil dimuat ulang."
    except Exception as exc:
        _set_runtime(module_name, False, str(exc).strip() or type(exc).__name__)
        log.exception("[Loader] Reload plugin gagal: %s", module_name)
        return False, f"{type(exc).__name__}: {exc}"
