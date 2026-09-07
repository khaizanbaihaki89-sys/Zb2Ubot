"""
IBEKS USERBOT - AI Safety & Anti-Scam Filter
Proteksi keamanan terhadap penipuan, phishing, permintaan OTP/password, dan eksploitasi.
"""

from __future__ import annotations

import re
from typing import Tuple

# Pola regex untuk mendeteksi potensi penipuan, phishing, dan pencurian kredensial
_SCAM_PATTERNS = [
    # Permintaan OTP / Kode Verifikasi Telegram
    r"(?i)\b(kode|nomor|kirimkan|minta|minta\s*kode|bagi)\s*(otp|verifikasi|login|telegram\s*code|sms\s*code)\b",
    r"(?i)\b(share|send|give|forward)\s*(your)?\s*(otp|verification\s*code|login\s*code)\b",
    # Permintaan Password / Kredensial Pribadi / Seed Phrase / PIN
    r"(?i)\b(password|kata\s*sandi|pin\s*atm|pin\s*rekening|cvv|cvc|private\s*key|seed\s*phrase|secret\s*phrase)\b",
    # Skema Penipuan Transfer Uang / Hadiah Palsu / Duit Kaget Palsu / Deposit Tugas
    r"(?i)\b(transfer\s*dulu|biaya\s*admin\s*dulu|klaim\s*hadiah|menang\s*undian|dana\s*kaget\s*palsu|tugas\s*like\s*subscribe|investasi\s*profit\s*pasti)\b",
    # Phishing link mencurigakan
    r"(?i)\b(login-telegram|free-telegram-premium|t\.me\/[a-zA-Z0-9_-]+\?start=login|klaim-dana|hadiah-telegram)\b",
    # Rekening minta kirim uang / transfer darurat penipuan
    r"(?i)\b(pinjam\s*dulu\s*seratus|minta\s*pulsa\s*darurat|tolong\s*transferin\s*ke\s*rek)\b",
]

_COMPILED_PATTERNS = [re.compile(p) for p in _SCAM_PATTERNS]


def is_safe_message(text: str) -> Tuple[bool, str]:
    """
    Periksa apakah teks percakapan bebas dari unsur penipuan, phishing, atau permintaan data sensitif.

    Returns
    -------
    Tuple[bool, str]
        (is_safe, reason)
    """
    if not text:
        return True, ""

    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return False, "Pesan mengandung indikasi phishing, permintaan kode verifikasi/OTP, atau penipuan finansial."

    return True, ""


def sanitize_ai_output(text: str) -> str:
    """
    Bersihkan dan amankan teks balasan AI dari kemungkinan kebocoran data sensitif.
    """
    if not text:
        return ""

    cleaned = text

    # Filter jika AI secara tidak sengaja memuntahkan API Key atau format token
    cleaned = re.sub(
        r"AIzaSy[A-Za-z0-9_-]{33}",
        "[REDACTED_API_KEY]",
        cleaned,
    )
    cleaned = re.sub(
        r"AQ\.[A-Za-z0-9_-]{30,}",
        "[REDACTED_API_KEY]",
        cleaned,
    )
    cleaned = re.sub(
        r"\b\d{5,6}\b(?=.*(?:kode|otp|verifikasi))",
        "[REDACTED_OTP]",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


def sanitize_error_message(err: Exception | str) -> str:
    """
    Saring pesan error agar tidak membocorkan kunci API, token, atau informasi sensitif.
    """
    msg = str(err) if err else ""
    if not msg:
        return "Unknown error"

    # Hapus pola Google API Key standar (AIzaSy... atau AQ.Ab8...)
    msg = re.sub(r"AIzaSy[A-Za-z0-9_-]{33}", "[REDACTED_API_KEY]", msg)
    msg = re.sub(r"AQ\.[A-Za-z0-9_-]{20,}", "[REDACTED_API_KEY]", msg)
    msg = re.sub(r"(?:key|api_key|token)[=:]\s*['\"]?[A-Za-z0-9_.-]{10,}['\"]?", "key=[REDACTED]", msg, flags=re.IGNORECASE)

    return msg.strip()


def setup(client=None) -> None:
    """Fungsi registrasi kompatibilitas plugin loader."""
    pass
