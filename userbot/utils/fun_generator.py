"""
IBEKS USERBOT - Fun Generator
Generator laporan lucu untuk .ctampan dan .ccantik.
Nilai deterministik berdasarkan User ID + minggu ISO saat ini.
"""

import random
from datetime import datetime
from typing import Tuple

from pyrogram.types import User

from utils.fun_data import (
    CTAMPAN_AURA,
    CTAMPAN_PENAMPILAN,
    CTAMPAN_KEUNGGULAN,
    CTAMPAN_TIER,
    CCANTIK_AURA,
    CCANTIK_PENAMPILAN,
    CCANTIK_KEUNGGULAN,
    CCANTIK_TIER,
)


def _current_week_seed() -> int:
    """Seed unik untuk minggu ISO saat ini (tahun + minggu)."""
    iso = datetime.now().isocalendar()
    return iso.year * 100 + iso.week


def _build_progress_bar(percent: int, length: int = 10) -> str:
    """Buat progress bar visual."""
    filled = min(length, max(0, percent // 10))
    empty = length - filled
    return "▰" * filled + "▱" * empty + f" {percent}%"


def _safe_name(user: User) -> str:
    """Kembalikan nama user yang aman untuk ditampilkan."""
    name = user.first_name or ""
    if user.last_name:
        name = f"{name} {user.last_name}".strip()
    return name or user.username or "Unknown"


def generate_ctampan(user: User) -> Tuple[str, int, str, str, str, str, str]:
    """
    Generate laporan .ctampan.
    Return (target_name, user_id, progress_bar, aura, outfit, plus, tier).
    """
    seed = user.id * 100000 + _current_week_seed()
    rng = random.Random(seed)

    percent = rng.randint(50, 100)
    progress = _build_progress_bar(percent)
    aura = rng.choice(CTAMPAN_AURA)
    outfit = rng.choice(CTAMPAN_PENAMPILAN)
    plus = rng.choice(CTAMPAN_KEUNGGULAN)
    tier = rng.choice(CTAMPAN_TIER)

    return _safe_name(user), user.id, progress, aura, outfit, plus, tier


def generate_ccantik(user: User) -> Tuple[str, int, str, str, str, str, str]:
    """
    Generate laporan .ccantik.
    Return (target_name, user_id, progress_bar, aura, outfit, plus, tier).
    """
    seed = user.id * 100000 + _current_week_seed() + 7
    rng = random.Random(seed)

    percent = rng.randint(50, 100)
    progress = _build_progress_bar(percent)
    aura = rng.choice(CCANTIK_AURA)
    outfit = rng.choice(CCANTIK_PENAMPILAN)
    plus = rng.choice(CCANTIK_KEUNGGULAN)
    tier = rng.choice(CCANTIK_TIER)

    return _safe_name(user), user.id, progress, aura, outfit, plus, tier
