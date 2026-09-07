"""
IBEKS USERBOT - Fun Card Data & Stats Engine
Menyediakan kalkulasi deterministik berbasis user ID dan mingguan untuk:
- TAMPAN (0-100%) / CANTIK (0-100%)
- AURA
- TIER
- STATUS MENTAL
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

try:
    from pyrogram.types import User
except ImportError:
    User = Any  # type: ignore

from utils.fun_data import CCANTIK_AURA, CCANTIK_TIER, CTAMPAN_AURA, CTAMPAN_TIER
from utils.id_data import STATUS_MENTAL


def week_key() -> str:
    """Kunci rotasi mingguan ISO."""
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def stable_indices(user_id: int, card_type: str, count: int) -> list[int]:
    """Menghasilkan indeks angka deterministik berbasis seed user_id, card_type, dan minggu berjalan."""
    digest = hashlib.sha256(
        f"ibeks-card:{card_type}:{user_id}:{week_key()}".encode("utf-8")
    ).digest()
    return [
        int.from_bytes(digest[offset : offset + 4], "big") % count
        for offset in range(0, count * 4, 4)
    ]


def get_card_stats(user: User, card_type: str = "male") -> dict[str, Any]:
    """
    Kalkulasi data statistik random untuk Card:
    - score: Nilai TAMPAN/CANTIK (0 - 100)
    - aura: Aura dari pool fun_data
    - tier: Tier dari pool fun_data
    - mental: Status mental dari pool id_data
    """
    key = card_type.lower()
    indices = stable_indices(user.id, key, 5)
    is_female = key in {"female", "pink", "cardw"}
    aura_pool = CCANTIK_AURA if is_female else CTAMPAN_AURA
    tier_pool = CCANTIK_TIER if is_female else CTAMPAN_TIER

    score_digest = hashlib.sha256(
        f"ibeks-score:{key}:{user.id}:{week_key()}".encode("utf-8")
    ).digest()
    score = int.from_bytes(score_digest[:2], "big") % 101

    return {
        "score": score,
        "score_label": "CANTIK" if is_female else "TAMPAN",
        "aura": aura_pool[indices[1] % len(aura_pool)],
        "tier": tier_pool[indices[2] % len(tier_pool)],
        "mental": STATUS_MENTAL[indices[3] % len(STATUS_MENTAL)],
    }


def get_user_display_name(user: User) -> str:
    """Mengambil nama lengkap user atau username fallback."""
    name = " ".join(part for part in (user.first_name, user.last_name) if part)
    return name or user.username or "Unknown"
