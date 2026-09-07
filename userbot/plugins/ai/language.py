"""
IBEKS USERBOT - AI Language & Dialect Detection
Modul deteksi dan adaptasi otomatis bahasa, dialek lokal, dan gaya komunikasi.

Mendukung:
- Bahasa Indonesia (Santai / Standar)
- Bahasa Gaul Jaksel (Campuran Indo-English)
- Dialek Betawi
- Bahasa Jawa (Ngoko, Krama, Suroboyoan, Semarang)
- Dialek Ngapak / Banyumasan
- Bahasa Sunda
- Bahasa Daerah Lain (Minang, Batak, Bugis/Makassar, Banjar, Bali, dll)
- Bahasa Inggris (English)
- Bahasa Korea (한국어 / Romanized)
- Bahasa Jepang (日本語 / Romaji)
- Bahasa Campuran (Code-Switching)
"""

from __future__ import annotations

import re
from typing import Any

# Pola Regex & Kata Kunci Khas
_REGEX_HANGUL = re.compile(r"[\uac00-\ud7a3]")
_REGEX_JAPANESE = re.compile(r"[\u3040-\u30ff\u4e00-\u9faf]")

# Kamus Kata Kunci Khas Dialek & Bahasa
_KEYWORDS_SUNDA = {
    "kumaha", "damang", "nuhun", "hatur", "punten", "abdi", "urang", "maneh", "anjeun",
    "teh", "mah", "atuh", "euy", "geura", "tos", "parantos", "acan", "teu", "henteu",
    "aya", "saha", "naon", "iraha", "dimana", "kamana", "bade", "hayu", "kuring",
    "sia", "aing", "cageur", "lemes", "naha", "kela", "sakedik", "enya", "muhun", "hiji"
}

_KEYWORDS_NGAPAK = {
    "inyong", "rika", "nyong", "kepriwe", "keprime", "madang", "ngelih", "kencot",
    "kayong", "koh", "ganing", "jere", "ora kepenak", "gumun", "kading",
    "kiye", "kuwe", "mbuh", "ora nana", "laka"
}

_KEYWORDS_TEGAL_BREBES = {
    "enyong", "kowen", "pimen", "priwe", "pan", "belih", "adong", "maring", "ora ilok",
    "sing", "njagong", "bapane", "mbokane", "laka", "nang", "karo", "wong"
}

_KEYWORDS_CIREBON_INDRAMAYU = {
    "isun", "sira", "beli", "bli", "priben", "keder", "maning", "nok", "tong", "kula",
    "reang", "mangga", "bagen", "dikit", "sing", "laka", "ora nana", "ira"
}

_KEYWORDS_JAWA = {
    "piye", "kepriye", "karepmu", "matur", "suwun", "mboten", "monggo", "nggih",
    "ora", "ra", "wes", "wis", "durung", "opo", "ngopo", "ngendi", "sopo", "iki",
    "iku", "kui", "kuwi", "kowe", "sampeyan", "panjenengan", "kula", "awakmu",
    "arep", "neng", "nang", "sek", "sekalian", "meneh", "tenan", "tenane", "apik",
    "cidro", "turu", "mangan", "ngombe", "mlaku", "rek", "cuk", "jancuk", "yo", "ngene"
}

_KEYWORDS_BETAWI = {
    "aye", "ente", "elu", "kaga", "kagak", "aje", "ape", "ngape", "kenape", "noh",
    "iye", "tong", "babeh", "enyak", "nyang", "pan", "gimane", "mane", "udeh", "ngarti",
    "buset", "dah", "beneran", "pan kapan", "bocah"
}

_KEYWORDS_JAKSEL = {
    "which is", "literally", "honestly", "basically", "prefer", "tbh", "fyi",
    "worth it", "make sense", "vibes", "vibe", "toxic", "healing", "overthinking",
    "deep talk", "cringe", "relate", "lowkey", "highkey", "slay", "spill", "glow up",
    "fomo", "red flag", "green flag", "part of", "like", "even", "somehow", "as a"
}

_KEYWORDS_MINANG = {
    "onde", "mande", "rancak", "ambo", "aden", "sia", "dima", "baa", "kama", "apo",
    "lai", "tarimo", "kasih", "sabana", "gadang", "lamak", "salamaik", "saketek", "bana"
}

_KEYWORDS_BATAK = {
    "horas", "mauliate", "aha", "ise", "didia", "boha", "au", "hamu", "lae", "ito",
    "amang", "inang", "boti", "nungnga", "hata", "kabarmu"
}

_KEYWORDS_MAKASSAR = {
    "tabe", "kodong", "aga", "kareba", "kurru", "sumange", "tena", "inai", "kemae",
    "ji", "ki", "ta", "pi", "mi", "mo", "baji"
}

_KEYWORDS_BALI = {
    "swastyastu", "suksma", "tiang", "bli", "gek", "kenken", "dija", "nyen", "sing", "napi"
}

_KEYWORDS_ENGLISH = {
    "hello", "hi", "how", "what", "where", "when", "why", "who", "thanks", "thank",
    "please", "could", "would", "should", "want", "need", "awesome", "great", "nice",
    "good", "morning", "afternoon", "evening", "night", "you", "your", "they", "them",
    "with", "about", "help", "check", "sorry", "excuse", "sure", "fine", "really", "friend"
}

_KEYWORDS_KOREAN_ROM = {
    "annyeong", "annyeonghaseyo", "gamsahamnida", "kamsahamnida", "daebak", "jinjja",
    "oppa", "unnie", "noona", "hyung", "saranghae", "chuka", "mianhae", "yeoboseyo",
    "jebal", "otoke", "ottoke", "gomawo", "kyeopta", "chingu", "hwaiting", "araseo"
}

_KEYWORDS_JAPANESE_ROM = {
    "arigatou", "ohayou", "konnichiwa", "konbanwa", "nani", "desu", "kawaii",
    "daijoubu", "sumimasen", "gomen", "sugoi", "baka", "sensei", "senpai",
    "sayonara", "chotto", "hontou", "otsukare", "ikuzo", "itadakimasu", "yamete"
}


def detect_language_and_dialect(text: str) -> dict[str, Any]:
    """
    Analisis bahasa, dialek, dan gaya komunikasi dari teks pesan lawan bicara.

    Parameters
    ----------
    text : str
        Pesan teks dari pengguna/lawan bicara.

    Returns
    -------
    dict[str, Any]
        {
            "name": str,            # Nama bahasa/dialek terdeteksi
            "category": str,        # Kode kategori bahasa/dialek
            "confidence": float,    # Skor keyakinan (0.0 - 1.0)
            "instruction": str,     # Instruksi penyesuaian khusus untuk model AI
            "notes": str,           # Catatan ringkas fitur dialek
        }
    """
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return {
            "name": "Bahasa Indonesia (Santai / Default)",
            "category": "id_casual",
            "confidence": 0.5,
            "instruction": "Gunakan bahasa Indonesia percakapan yang santai, akrab, dan natural.",
            "notes": "Pesan kosong / default",
        }

    # 1. Cek Aksara Hangeul (Korea)
    if _REGEX_HANGUL.search(text):
        return {
            "name": "Bahasa Korea (한국어)",
            "category": "ko_kr",
            "confidence": 0.99,
            "instruction": "Balas secara alami dalam Bahasa Korea (한국어). Sesuaikan tingkat kesopanan (존댓말 / 반말) dengan nada pesan lawan bicara.",
            "notes": "Menggunakan aksara Hangul",
        }

    # 2. Cek Aksara Jepang (Kanji / Hiragana / Katakana)
    if _REGEX_JAPANESE.search(text):
        return {
            "name": "Bahasa Jepang (日本語)",
            "category": "ja_jp",
            "confidence": 0.99,
            "instruction": "Balas secara alami dalam Bahasa Jepang (日本語). Sesuaikan tingkat kesopanan (Keigo/Desu-Masu atau Casual/Tameguchi) dengan lawan bicara.",
            "notes": "Menggunakan aksara Jepang (Kana/Kanji)",
        }

    # Tokenisasi kata
    words = re.findall(r"\b[a-z0-9'-]+\b", cleaned)
    words_set = set(words)
    text_lower = f" {cleaned} "

    # 3. Cek Frasa Multi-kata Jaksel
    jaksel_matches = [p for p in _KEYWORDS_JAKSEL if f" {p} " in text_lower or p in words_set]
    if len(jaksel_matches) >= 2 or (len(jaksel_matches) >= 1 and len(words) <= 5 and ("which is" in text_lower or "literally" in text_lower or "vibes" in text_lower)):
        return {
            "name": "Bahasa Gaul Jaksel (Indo-English Code-Switching)",
            "category": "id_jaksel",
            "confidence": 0.9,
            "instruction": "Balas dengan gaya bahasa gaul Jaksel santai (campuran kosakata Indo-English seperti 'which is', 'literally', 'vibes', 'lo-gue' secara natural dan tidak berlebihan).",
            "notes": f"Terdeteksi kata/frasa: {', '.join(jaksel_matches[:3])}",
        }

    # 4. Hitung skor kecocokan kata kunci per dialek/bahasa
    def _score(kw_set: set[str]) -> tuple[int, list[str]]:
        matches = [w for w in words if w in kw_set]
        return len(matches), list(set(matches))

    score_ngapak, m_ngapak = _score(_KEYWORDS_NGAPAK)
    score_tegal, m_tegal = _score(_KEYWORDS_TEGAL_BREBES)
    score_cirebon, m_cirebon = _score(_KEYWORDS_CIREBON_INDRAMAYU)
    score_sunda, m_sunda = _score(_KEYWORDS_SUNDA)
    score_jawa, m_jawa = _score(_KEYWORDS_JAWA)
    score_betawi, m_betawi = _score(_KEYWORDS_BETAWI)
    score_minang, m_minang = _score(_KEYWORDS_MINANG)
    score_batak, m_batak = _score(_KEYWORDS_BATAK)
    score_makassar, m_makassar = _score(_KEYWORDS_MAKASSAR)
    score_bali, m_bali = _score(_KEYWORDS_BALI)
    score_en, m_en = _score(_KEYWORDS_ENGLISH)
    score_ko_rom, m_ko_rom = _score(_KEYWORDS_KOREAN_ROM)
    score_ja_rom, m_ja_rom = _score(_KEYWORDS_JAPANESE_ROM)

    # 5. Evaluasi Prioritas Berdasarkan Bobot Kecocokan & Ciri Khas
    # Cirebon / Indramayu check
    if score_cirebon >= 1 and ("isun" in m_cirebon or "sira" in m_cirebon or "beli" in m_cirebon or "bli" in m_cirebon or "priben" in m_cirebon or "reang" in m_cirebon or "keder" in m_cirebon or score_cirebon >= 2):
        return {
            "name": "Dialek Cirebon / Indramayu",
            "category": "jv_cirebon",
            "confidence": 0.93,
            "instruction": "Balas dalam Dialek Cirebon / Indramayu yang khas dan luwes (gunakan diksi seperti 'isun', 'sira/ira', 'beli/bli', 'priben', 'keder', 'maning', 'bagen', 'laka').",
            "notes": f"Terdeteksi kosakata Cirebon/Indramayu: {', '.join(m_cirebon)}",
        }

    # Brebes / Tegal / Tegalan check
    if score_tegal >= 1 and ("enyong" in m_tegal or "kowen" in m_tegal or "pimen" in m_tegal or "belih" in m_tegal or "maring" in m_tegal or ("pan" in m_tegal and ("priwe" in m_tegal or "laka" in m_tegal)) or score_tegal >= 2):
        return {
            "name": "Dialek Brebes / Tegal (Tegalan)",
            "category": "jv_tegal",
            "confidence": 0.93,
            "instruction": "Balas dalam Dialek Tegal / Brebes (Tegalan) yang medok, akrab, dan luwes (gunakan diksi khas seperti 'enyong', 'kowen', 'pimen/priwe', 'pan' [mau/akan], 'belih', 'laka', 'adong').",
            "notes": f"Terdeteksi kosakata Tegalan/Brebes: {', '.join(m_tegal)}",
        }

    # Ngapak Banyumasan check
    if score_ngapak >= 1 and ("inyong" in m_ngapak or "rika" in m_ngapak or "kepriwe" in m_ngapak or "madang" in m_ngapak or "kencot" in m_ngapak or "kayong" in m_ngapak or "ganing" in m_ngapak or "laka" in m_ngapak or score_ngapak >= 2):
        return {
            "name": "Dialek Ngapak / Banyumasan",
            "category": "jv_ngapak",
            "confidence": 0.92,
            "instruction": "Balas dalam Dialek Ngapak / Banyumasan yang luwes, medok, dan akrab (gunakan diksi seperti 'inyong/nyong', 'rika', 'kiye/kuwe', 'kepriwe', 'madang', 'kayong', dsb).",
            "notes": f"Terdeteksi kosakata Ngapak: {', '.join(m_ngapak)}",
        }

    # Betawi check
    if score_betawi >= 1 and ("aye" in m_betawi or "ente" in m_betawi or "kaga" in m_betawi or "kagak" in m_betawi or "babeh" in m_betawi or "enyak" in m_betawi or "gimane" in m_betawi or (score_betawi > score_ngapak and score_betawi > score_jawa)):
        return {
            "name": "Dialek Betawi",
            "category": "id_betawi",
            "confidence": 0.90,
            "instruction": "Balas dengan dialek Betawi percakapan yang luwes (gunakan diksi seperti 'lu-gue', 'kaga/kagak', 'aje', 'dah', 'begitu').",
            "notes": f"Terdeteksi kosakata Betawi: {', '.join(m_betawi)}",
        }

    # Sunda check
    if score_sunda >= 1:
        return {
            "name": "Bahasa Sunda",
            "category": "su_id",
            "confidence": 0.92,
            "instruction": "Balas dalam Bahasa Sunda yang natural, akrab, dan santun (gunakan partikel Sunda yang pas seperti 'euy', 'atuh', 'mah', 'teh' dan kosakata Sunda yang relevan).",
            "notes": f"Terdeteksi kosakata Sunda: {', '.join(m_sunda)}",
        }

    # Jawa check
    if score_jawa >= 1:
        is_suroboyo = any(w in m_jawa for w in ["rek", "cuk", "jancuk"])
        jawa_desc = "Bahasa Jawa (Dialek Suroboyoan/Timuran)" if is_suroboyo else "Bahasa Jawa (Ngoko/Krama)"
        return {
            "name": jawa_desc,
            "category": "jv_id",
            "confidence": 0.90,
            "instruction": f"Balas dalam {jawa_desc} yang luwes dan alami sesuai tingkat keakraban lawan bicara.",
            "notes": f"Terdeteksi kosakata Jawa: {', '.join(m_jawa)}",
        }

    # Minang check
    if score_minang >= 1:
        return {
            "name": "Bahasa Minang / Padang",
            "category": "min_id",
            "confidence": 0.88,
            "instruction": "Balas dengan Bahasa Minang / dialek Minang yang ramah dan alami.",
            "notes": f"Terdeteksi kosakata Minang: {', '.join(m_minang)}",
        }

    # Batak check
    if score_batak >= 1:
        return {
            "name": "Bahasa Batak / Dialek Sumatera Utara",
            "category": "btk_id",
            "confidence": 0.88,
            "instruction": "Balas dengan sapaan atau dialek Batak yang hangat dan natural (misal: 'Horas', 'Mauliate').",
            "notes": f"Terdeteksi kosakata Batak: {', '.join(m_batak)}",
        }

    # Makassar check
    if score_makassar >= 1 and ("tabe" in m_makassar or "kodong" in m_makassar or "aga" in m_makassar):
        return {
            "name": "Dialek Makassar / Bugis",
            "category": "mak_id",
            "confidence": 0.88,
            "instruction": "Balas dengan dialek Makassar/Bugis yang luwes (gunakan partikel khas seperti 'ji', 'ki', 'mi', 'kodong', 'tabe').",
            "notes": f"Terdeteksi kosakata Makassar: {', '.join(m_makassar)}",
        }

    # Bali check
    if score_bali >= 1:
        return {
            "name": "Bahasa Bali / Dialek Bali",
            "category": "ban_id",
            "confidence": 0.88,
            "instruction": "Balas dengan Bahasa / Dialek Bali yang santun dan akrab (misal: 'Suksma', 'Bli', 'Gek').",
            "notes": f"Terdeteksi kosakata Bali: {', '.join(m_bali)}",
        }

    # Korean Romaji check
    if score_ko_rom >= 1:
        return {
            "name": "Bahasa Korea (Romanized)",
            "category": "ko_rom",
            "confidence": 0.85,
            "instruction": "Lawan bicara menggunakan bahasa Korea (Romaji/Romanized). Balas dalam bahasa Korea yang natural dan ramah.",
            "notes": f"Terdeteksi kosakata Korea: {', '.join(m_ko_rom)}",
        }

    # Japanese Romaji check
    if score_ja_rom >= 1:
        return {
            "name": "Bahasa Jepang (Romaji)",
            "category": "ja_rom",
            "confidence": 0.85,
            "instruction": "Lawan bicara menggunakan bahasa Jepang (Romaji). Balas dalam bahasa Jepang yang natural dan santai.",
            "notes": f"Terdeteksi kosakata Jepang: {', '.join(m_ja_rom)}",
        }

    # English check
    if score_en >= 2 or (score_en >= 1 and len(words) <= 4 and any(w in m_en for w in ["hello", "hi", "thanks", "please", "awesome", "what", "friend"])):
        return {
            "name": "Bahasa Inggris (English)",
            "category": "en_us",
            "confidence": 0.90,
            "instruction": "Reply naturally and fluently in English. Match the user's casual, polite, or direct tone.",
            "notes": f"Terdeteksi kosakata Bahasa Inggris: {', '.join(m_en)}",
        }

    # Default: Bahasa Indonesia Santai
    return {
        "name": "Bahasa Indonesia (Santai / Gaul Natural)",
        "category": "id_casual",
        "confidence": 0.80,
        "instruction": "Gunakan bahasa Indonesia percakapan santai yang mengalir alami, ramah, dan to-the-point.",
        "notes": "Bahasa Indonesia percakapan standar/santai",
    }


def format_language_prompt_context(detected_info: dict[str, Any]) -> str:
    """
    Format hasil deteksi bahasa ke dalam blok prompt konteks untuk Gemini.
    """
    name = detected_info.get("name", "Bahasa Indonesia")
    instruction = detected_info.get("instruction", "Balas dengan bahasa yang sesuai.")
    notes = detected_info.get("notes", "")
    notes_line = f"Catatan: {notes}\n" if notes else ""

    return (
        "=== DETEKSI BAHASA & DIALEK LAWAN BICARA ===\n"
        f"Bahasa / Dialek Terdeteksi: {name}\n"
        f"{notes_line}"
        f"Instruksi Penyesuaian:\n"
        f"- {instruction}\n"
        "- WAJIB IKUTI GAYA & DIALEK: Tiru dan gunakan kosakata, partikel, serta logat yang sama dengan lawan bicara.\n"
        "- Jika tidak yakin dengan nama daerahnya, cukup cerminkan kosakata dan gaya santai lawan bicara secara langsung tanpa memaksakan bahasa baku.\n"
        "- Jika lawan bicara berganti bahasa atau dialek di pesan berikutnya, kamu WAJIB langsung ikut berganti menyesuaikan.\n"
        "============================================="
    )


def setup(client=None) -> None:
    """Fungsi registrasi kompatibilitas plugin loader."""
    pass

