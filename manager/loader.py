"""Memuat otomatis semua plugin yang memiliki setup(client)."""

from __future__ import annotations

import importlib

from config import PLUGINS_DIR
from logger import log


def load_plugins(client) -> dict[str, list]:
    """Cari seluruh file Python dalam plugins dan daftarkan handler-nya."""
    loaded: list[str] = []
    failed: list[dict[str, str]] = []

    for path in sorted(PLUGINS_DIR.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        relative = path.relative_to(PLUGINS_DIR).with_suffix("")
        module_name = "plugins." + ".".join(relative.parts)
        try:
            module = importlib.import_module(module_name)
            setup = getattr(module, "setup", None)
            if setup is None:
                log.info("Plugin dilewati (tidak memiliki setup): %s", module_name)
                continue
            setup(client)
            loaded.append(module_name)
            if path.name == "panel.py":
                log.info("[Loader] Loaded panel.py")
                log.info("[Loader] Registered /panel")
                log.info("[Panel] Ready")
            log.info("✓ Plugin aktif: %s", module_name)
        except Exception as exc:
            failed.append({"module": module_name, "error": str(exc)})
            if path.name == "panel.py":
                log.error("[Loader] Failed panel.py: %s", exc)
            log.exception("✗ Plugin gagal dimuat: %s", module_name)

    log.info(
        "Total plugin: %s berhasil, %s gagal.",
        len(loaded),
        len(failed),
    )
    return {"loaded": loaded, "failed": failed}