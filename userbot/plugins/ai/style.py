"""
IBEKS USERBOT - AI Style Profile
Gaya penulisan, pola chat santai, analisis gaya mengetik (.aistyle learn), dan contoh few-shot.

Command:
  .aistyle status      - Menampilkan gaya tulisan AI saat ini.
  .aistyle set <gaya>  - Mengatur gaya tulisan khusus AI secara manual.
  .aistyle learn       - Menganalisis pola mengetik dari riwayat chat & simpan sebagai Style Profile.
  .aistyle reset       - Mengembalikan gaya tulisan ke default bawaan.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        @classmethod
        def model_validate_json(cls, json_str: str):
            data = json.loads(json_str)
            return cls(**data)
    def Field(*args, **kwargs):
        return None

from pyrogram import filters

from config import AUTO_DELETE_CMD, MANAGER_BOT_ID
from utils.autodelete import auto_delete
from utils.filters import dynamic_command
from utils.formatter import FormattedUI, format_ui, info, success, warning
from utils.logger import log
from plugins.utils.ui import send_ui
from plugins.ai.config import (
    get_api_key,
    get_active_model,
    get_custom_style,
    set_custom_style,
    reset_custom_style,
    get_manual_style,
    set_manual_style,
    get_learned_style,
    set_learned_style,
    FALLBACK_MODELS,
)


class StyleAnalysisSchema(BaseModel):
    """Schema output terstruktur untuk analisis gaya mengetik Gemini."""
    length_desc: str = Field(description="Deskripsi pola panjang kalimat dari sampel (contoh: 'Sangat singkat (1-5 kata)' atau 'Sedang santai (6-12 kata)')")
    language_desc: str = Field(description="Bahasa / dialek yang digunakan (contoh: 'Indonesia santai / gaul', 'Campuran santai & daerah')")
    jokes_desc: str = Field(description="Pola tawa / jokes (contoh: 'Suka menyelipkan wkwk / tawa santai' atau 'Lugas dan ramah')")
    abbreviations_desc: str = Field(description="Singkatan kata yang sering digunakan (contoh: 'Aktif: yg, udh, bgt, gk' atau 'Sedikit singkatan')")
    casing_desc: str = Field(description="Pola huruf dan tanda baca (contoh: 'Huruf kecil di awal kalimat, tanpa titik penutup')")
    answering_style_desc: str = Field(description="Cara jawab (contoh: 'To-the-point, langsung ke inti jawaban, tanpa basa-basi')")
    speaking_style_desc: str = Field(description="Gaya bicara (contoh: 'Kasual, akrab, bersahabat layaknya teman akrab')")
    emoji_desc: str = Field(description="Pola emoji (contoh: '0-1 emoji relevan' atau 'Jarang / tanpa emoji')")
    frequent_emojis_desc: str = Field(description="Emoji yang sering digunakan terdeteksi dari sampel (contoh: '👍, 😂, 🔥' atau 'Tidak ada')")
    additional_description: str = Field(description="Deskripsi tambahan / rangkuman aturan konkret gaya mengetik pemilik akun (1-3 kalimat singkat)")
    profile_rules: list[str] = Field(
        description="4-6 butir aturan konkret dan padat untuk diterapkan AI saat membalas chat agar sama persis dengan gaya mengetik pengguna di atas (santai, singkatan yang sesuai, panjang balasan, tanpa format teknis/CLI/bullet kaku)"
    )



STYLE_GUIDELINES = """
Panduan Gaya Penulisan Chat (Style Profile):
1. **Pemahaman Singkatan, Slang, & Typo Chat Telegram**:
   - AI WAJIB memahami secara mendalam makna dari berbagai singkatan chat Telegram/WhatsApp, typo wajar, slang/bahasa gaul, dan variasi penulisan berdasarkan konteks kalimat (misal: "yg", "udh/udah", "blm", "bgt", "gk/ga/gak", "klo/kalo", "knp", "gmn/gimana", "kek", "lg", "dmn", "sm", "aja", "btw", "otw", "tpi/tp", "bkn", "jg", "bs", "skrg", "mksih/thx", "ywdh", "emg", "beneran", dll).
   - Jangan hanya bergantung pada daftar kata statis; tangkap dan pahami maksud serta intisari pertanyaan lawan bicara dari konteks kalimat seutuhnya.
   - AI tidak wajib membalas dengan singkatan tersebut; sesuaikan dan ikuti gaya lawan bicara secara santai dan luwes jika cocok.

2. **Karakteristik Chat Manusia (Bukan Customer Service)**:
   - Gunakan gaya bahasa chat santai, natural, dan to-the-point layaknya teman ngobrol di Telegram/WhatsApp.
   - DILARANG KERAS menggunakan sapaan/basa-basi formal ("Halo! Ada yang bisa saya bantu?", "Tentu saja, saya siap membantu", dll). Langsung jawab ke intinya.
   - Boleh menggunakan singkatan chat umum yang wajar jika konteks percakapannya santai.

3. **Proporsionalitas & Panjang Balasan**:
   - WAJIB menyesuaikan panjang balasan dengan panjang chat lawan bicara.
   - Jika lawan bicara mengirim chat pendek (1-5 kata), balas SANGAT SINGKAT (1 baris / 1-10 kata).
   - DILARANG membalas chat singkat dengan paragraf panjang.

4. **Format & Estetika**:
   - Lebih sering gunakan huruf kecil santai di awal kalimat.
   - Gunakan emoji seperlunya (0-1 emoji relevan), jangan spam emoji.
   - Boleh menyelipkan candaan ringan, tawa santai ("wkwk", "haha"), atau ekspresi santai jika sesuai konteks.

Contoh Pola Chat (Few-shot):
- Lawan bicara: "kabare priwe.?"
  Respons: "apik kiye, rika kepriwe?"

- Lawan bicara: "bujug dah"
  Respons: "kenape emang dah wkwk"

- Lawan bicara: "pinter lu"
  Respons: "wkwk jelas dong haha"

- Lawan bicara: "oi"
  Respons: "yo, kenapa bro?"

- Lawan bicara: "halo bro, lagi sibuk gk?"
  Respons: "santai nih bro, kenapa?"

- Lawan bicara: "lu dmn skrg? otw kmn?"
  Respons: "lg di rumah nih, blm kmn-kmn. knp bro?"

- Lawan bicara: "bisa minta tolong cekin file ini bentar?"
  Respons: "oke siap, kirim aja filenya ya"

- Lawan bicara: "makasih ya!"
  Respons: "sama-sama santai aja 👍"

- Lawan bicara: "apa bedanya RAM sama ROM?"
  Respons: "singkatnya: RAM itu memori sementara pas app jalan, ROM itu memori simpan file/sistem permanen."
"""


async def _notify_manager_bot(client, text: str, delay: int = 30) -> Any:
    """
    Kirim notifikasi teks status AI ke Manager Bot jika MANAGER_BOT_ID tersedia.
    Menangkap message_id dari hasil send_message dan menjadwalkan auto-delete setelah delay detik (default: 30s).
    """
    if not MANAGER_BOT_ID:
        return None
    try:
        try:
            from plugins.ai.chatbot import _resolve_manager_peer

            manager_peer = await _resolve_manager_peer(client)
        except Exception:
            manager_peer = MANAGER_BOT_ID

        sent_msg = await client.send_message(manager_peer or MANAGER_BOT_ID, text)
        if sent_msg and getattr(sent_msg, "id", None):
            target_chat_id = sent_msg.chat.id if sent_msg.chat else MANAGER_BOT_ID
            target_msg_id = sent_msg.id
            log.info(
                f"[AI Style] Notifikasi status terkirim ke Manager Bot "
                f"(chat_id={target_chat_id}, message_id={target_msg_id})."
            )
            asyncio.create_task(auto_delete(sent_msg, delay=delay, force=True))
            return sent_msg
        return None
    except Exception as exc:
        log.error(f"[AI Style] Gagal kirim notifikasi ke Manager Bot ({MANAGER_BOT_ID}): {exc}")
        return None


def extract_prompt_from_learned(raw_learned: str | None) -> str | None:
    """
    Ekstrak teks instruksi sistem dari data learned_style (mendukung format JSON terstruktur maupun teks warisan).
    """
    if not raw_learned or not raw_learned.strip():
        return None
    raw_s = raw_learned.strip()
    try:
        data = json.loads(raw_s)
        if isinstance(data, dict):
            if data.get("profile_text"):
                return str(data["profile_text"]).strip()
            rules = data.get("rules", [])
            if rules and isinstance(rules, list):
                return "Style Profile Pemilik Akun (Hasil Analisis Real-Chat):\n" + "\n".join(f"- {r}" for r in rules if r)
    except Exception:
        pass
    return raw_s


def get_learned_style_data() -> dict[str, Any] | None:
    """
    Mengambil structured data hasil analisis learning yang tersimpan di state/database.
    """
    raw = get_learned_style()
    if not raw or not raw.strip():
        return None
    raw_s = raw.strip()
    try:
        data = json.loads(raw_s)
        if isinstance(data, dict) and ("details" in data or "additional_description" in data or "rules" in data):
            return data
    except Exception:
        pass

    # Fallback untuk format teks biasa lama
    return {
        "profile_text": raw_s,
        "details": {
            "length": "Singkat & santai",
            "language": "Indonesia santai / gaul",
            "jokes": "Santai & wajar",
            "abbreviations": "Wajar",
            "casing": "Huruf kecil santai",
            "answering_style": "To-the-point & santai",
            "speaking_style": "Kasual & akrab",
            "emoji": "0-1 emoji relevan",
            "frequent_emojis": "Tidak ada",
        },
        "additional_description": raw_s,
        "rules": [raw_s],
    }


def format_learn_ui_block(learned_data: dict[str, Any] | None) -> str:
    """
    Format blok LEARN status/hasil analisis sesuai spesifikasi UI.
    """
    if not learned_data:
        return (
            "⚙️ Mode            : Default\n"
            "📊 Status          : Aktif\n"
            "🧠 Gaya            : Default\n"
            "📚 Gaya Dipelajari : Belum dipelajari"
        )

    details = learned_data.get("details", {})
    add_desc = (
        learned_data.get("additional_description")
        or "Gaya mengetik santai dan mengalir alami sesuai percakapan asli pemilik akun."
    ).strip()

    lines = [
        "⚙️ Mode            : Gaya Gua",
        "📊 Status          : Aktif",
        "🧠 Gaya            : Gaya Gua",
        "📚 Gaya Dipelajari : Style Profil Pemilik Akun",
        "",
        "📋 Hasil Analisis",
        f"• Panjang chat     : {details.get('length', 'Singkat & santai')}",
        f"• Bahasa           : {details.get('language', 'Indonesia santai / gaul')}",
        f"• Jokes            : {details.get('jokes', 'Santai & wajar')}",
        f"• Singkatan        : {details.get('abbreviations', 'Wajar')}",
        f"• Casing           : {details.get('casing', 'Huruf kecil santai')}",
        f"• Cara jawab       : {details.get('answering_style', 'To-the-point & santai')}",
        f"• Gaya bicara      : {details.get('speaking_style', 'Kasual & akrab')}",
        f"• Emoji            : {details.get('emoji', '0-1 emoji relevan')}",
        f"• Emoji yang sering digunakan : {details.get('frequent_emojis', 'Tidak ada')}",
        "",
        "📝 Deskripsi Tambahan",
        add_desc,
    ]
    return "\n".join(lines)


def format_aistyle_full_ui() -> FormattedUI:
    """
    Format tampilan utama .aistyle (mencakup status LEARN dan status prompt SET).
    """
    learned_data = get_learned_style_data()
    manual_prompt = get_manual_style()
    prompt_str = manual_prompt.strip() if manual_prompt and manual_prompt.strip() else "Belum diatur"

    learn_block = format_learn_ui_block(learned_data)

    body = (
        "🧠 AI STYLE LEARN\n\n"
        f"{learn_block}\n\n"
        "⚙️ AI STYLE SET\n"
        f"📝 Prompt : {prompt_str}"
    )

    return format_ui(
        title="AI STYLE",
        body=body,
        emoji="🎨",
        expandable=True,
    )


def format_aistyle_learn_ui() -> FormattedUI:
    """
    Format tampilan khusus .aistyle learn (hanya menampilkan status/hasil LEARN).
    """
    learned_data = get_learned_style_data()
    learn_block = format_learn_ui_block(learned_data)

    return format_ui(
        title="AI STYLE STATUS",
        body=learn_block,
        emoji="🎨",
        expandable=True,
    )


def get_style_status_info() -> dict[str, Any]:
    """
    Mengambil status Style Profile saat ini berdasarkan state tersimpan di runtime & database.
    Mendukung gaya otomatis (.aistyle learn), gaya manual (.aistyle set), atau kombinasi keduanya.
    """
    learned_data = get_learned_style_data()
    manual = get_manual_style()

    if learned_data and manual:
        return {
            "has_profile": True,
            "mode": "Kombinasi (Manual + Learn)",
            "status": "Aktif",
            "source": "Manual (.aistyle set) + Real Chat (.aistyle learn)",
            "manual": manual,
            "learned": learned_data.get("profile_text") or "Style Profil Pemilik Akun",
            "profile": f"Manual: {manual}\n\nLearn: {learned_data.get('profile_text')}",
        }
    elif manual:
        return {
            "has_profile": True,
            "mode": "Gaya Manual",
            "status": "Aktif",
            "source": "Manual (.aistyle set)",
            "manual": manual,
            "learned": None,
            "profile": manual,
        }
    elif learned_data:
        return {
            "has_profile": True,
            "mode": "Gaya Gua",
            "status": "Aktif",
            "source": "Style Profil Pemilik Akun (.aistyle learn)",
            "manual": None,
            "learned": learned_data.get("profile_text") or "Style Profil Pemilik Akun",
            "profile": learned_data.get("profile_text"),
        }
    return {
        "has_profile": False,
        "mode": "Default",
        "status": "Aktif",
        "source": None,
        "manual": None,
        "learned": None,
        "profile": None,
    }


def format_style_instructions(
    custom_style: str | None = None,
    manual_style: str | None = None,
    learned_style: str | None = None,
) -> str:
    """
    Format instruksi gaya tulisan untuk disuntikkan ke prompt sistem Gemini.
    Menggabungkan panduan dasar, profil hasil .aistyle learn, dan instruksi manual dari .aistyle set.
    """
    active_manual = manual_style if manual_style is not None else get_manual_style()
    active_learned = learned_style if learned_style is not None else (
        custom_style if custom_style is not None else get_learned_style()
    )
    active_learned_prompt = extract_prompt_from_learned(active_learned)

    parts = [STYLE_GUIDELINES.strip()]

    if active_learned_prompt and active_learned_prompt.strip():
        parts.append(
            f"=== INSTRUKSI GAYA KHUSUS PEMILIK AKUN (STYLE PROFILE DARI .aistyle learn) ===\n"
            f"{active_learned_prompt.strip()}\n"
            f"- Terapkan karakteristik gaya di atas (panjang pesan, singkatan, casing, jokes, emoji).\n"
            f"================================================================================="
        )

    if active_manual and active_manual.strip():
        parts.append(
            f"=== PANDUAN GAYA MANUAL (DARI .aistyle set) ===\n"
            f"{active_manual.strip()}\n"
            f"- WAJIB terapkan seluruh instruksi gaya manual di atas dalam seluruh balasan.\n"
            f"================================================="
        )

    return "\n\n".join(parts)


def _heuristic_analyze_style(samples: list[str]) -> dict[str, Any]:
    """
    Analisis linguistik deterministik pola gaya mengetik jika offline / tanpa API key.
    Menganalisis panjang kalimat, bahasa, jokes, singkatan, casing, cara jawab, gaya bicara, dan emoji.
    """
    if not samples:
        default_details = {
            "length": "Singkat & santai",
            "language": "Indonesia santai / gaul",
            "jokes": "Santai & wajar",
            "abbreviations": "Wajar",
            "casing": "Huruf kecil santai",
            "answering_style": "To-the-point & santai",
            "speaking_style": "Kasual & akrab",
            "emoji": "0-1 emoji relevan",
            "frequent_emojis": "Tidak ada",
        }
        return {
            "summary": "Gaya santai standar, respons singkat dan natural.",
            "profile_text": "Style Profile Pemilik Akun:\n- Gaya santai, kalimat singkat-sedang, singkatan wajar (yg, udh, bgt), huruf kecil santai, emoji minim.",
            "details": default_details,
            "additional_description": "Merespons dengan gaya santai dan mengalir alami, memprioritaskan keringkasan dan keramahan tanpa nada kaku.",
            "rules": [
                "Gunakan balasan singkat dan langsung ke inti percakapan.",
                "Gunakan bahasa Indonesia santai sehari-hari.",
                "Gunakan huruf kecil santai di awal kalimat.",
                "Gunakan emoji seperlunya (0-1 emoji relevan).",
            ],
        }

    total_len = sum(len(s.split()) for s in samples)
    avg_words = total_len / len(samples)

    # 1. Panjang chat
    if avg_words <= 5:
        len_desc = "Sangat singkat (1-5 kata)"
        len_rule = "Gunakan balasan sangat singkat dan langsung pada intinya (1-5 kata)."
    elif avg_words <= 12:
        len_desc = "Sedang santai (6-12 kata)"
        len_rule = "Gunakan balasan berukuran sedang yang santai dan mengalir alami (6-12 kata)."
    else:
        len_desc = "Ekspresif & deskriptif (> 12 kata)"
        len_rule = "Gunakan balasan yang cukup lengkap dan ekspresif jika diperlukan."

    # 2. Singkatan
    abbrev_dict = {
        "yg": "yang", "gk": "nggak", "ga": "nggak", "udh": "sudah", "udah": "sudah",
        "bgt": "banget", "tp": "tapi", "klo": "kalau", "krn": "karena", "dgn": "dengan",
        "aja": "saja", "nih": "ini", "dong": "dong", "dr": "dari", "sm": "sama", "skrg": "sekarang",
    }
    found_abbrevs = set()
    for s in samples:
        for w in re.findall(r"\b[a-z]+\b", s.lower()):
            if w in abbrev_dict:
                found_abbrevs.add(w)

    if found_abbrevs:
        abbr_desc = f"Aktif: {', '.join(list(found_abbrevs)[:5])}"
        abbr_rule = f"Gunakan singkatan chat yang wajar seperti: {', '.join(list(found_abbrevs)[:5])}."
    else:
        abbr_desc = "Wajar / penulisan relatif utuh"
        abbr_rule = "Gunakan kata-kata yang relatif utuh dan mudah dipahami."

    # 3. Typo ringan & Casing
    lowercase_starts = sum(1 for s in samples if s and s[0].islower())
    no_trailing_dot = sum(1 for s in samples if s and not s.rstrip().endswith((".", "!", "?")))
    repeated_chars = sum(1 for s in samples if re.search(r"(.)\1{2,}", s))

    casing_traits = []
    if lowercase_starts >= len(samples) * 0.5:
        casing_traits.append("huruf kecil di awal kalimat")
    if no_trailing_dot >= len(samples) * 0.5:
        casing_traits.append("tanpa titik di akhir kalimat")
    if repeated_chars > 0:
        casing_traits.append("huruf berulang ekspresif")

    casing_desc = ", ".join(casing_traits) if casing_traits else "Huruf kecil santai / standar"
    casing_rule = f"Pola pengetikan: {casing_desc}."

    # 4. Bahasa & Slang
    slang_pool = {"gue", "lu", "lo", "gw", "bro", "cuy", "gan", "anjir", "bjir", "gas", "santuy", "gokil", "mantap"}
    found_slang = set()
    for s in samples:
        for w in re.findall(r"\b[a-z]+\b", s.lower()):
            if w in slang_pool:
                found_slang.add(w)

    if found_slang:
        lang_desc = "Indonesia santai / gaul"
        speak_desc = f"Kasual, akrab ({', '.join(list(found_slang)[:3])})"
        slang_rule = f"Gunakan sapaan dan diksi gaul santai seperti {', '.join(list(found_slang)[:4])}."
    else:
        lang_desc = "Indonesia santai sehari-hari"
        speak_desc = "Kasual & ramah bersahabat"
        slang_rule = "Gunakan bahasa santai ramah umum yang luwes dan alami."

    # 5. Jokes / Tawa
    laugh_tokens = sum(len(re.findall(r"\b(wkwk+|haha+|hehe+|xixi+|lol|wk)\b", s.lower())) for s in samples)
    if laugh_tokens >= 2:
        jokes_desc = "Suka menyelipkan wkwk / tawa santai"
        jokes_rule = "Boleh menyisipkan candaan ringan atau 'wkwk' secara wajar pada momen santai."
    else:
        jokes_desc = "Santai, lugas, humor wajar"
        jokes_rule = "Jaga nada bicara tetap santai, lugas, dan bersahabat."

    # 6. Emoji & Sering digunakan
    emoji_pattern = re.compile(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]"
    )
    all_emojis = []
    for s in samples:
        all_emojis.extend(emoji_pattern.findall(s))

    if len(all_emojis) >= len(samples):
        emoji_desc = "1-2 emoji ekspresif"
        emoji_rule = "Gunakan 1-2 emoji yang relevan untuk memperkuat emosi pesan."
    elif len(all_emojis) > 0:
        emoji_desc = "0-1 emoji relevan"
        emoji_rule = "Gunakan emoji sesekali saja (maksimal 1 emoji) jika relevan."
    else:
        emoji_desc = "Jarang / tanpa emoji"
        emoji_rule = "Hindari penggunaan emoji berlebihan, utamakan teks langsung."

    unique_emojis = list(dict.fromkeys(all_emojis))[:5]
    frequent_emojis_desc = ", ".join(unique_emojis) if unique_emojis else "Tidak ada"

    answer_desc = "To-the-point, langsung ke inti jawaban"

    rules = [
        len_rule,
        abbr_rule,
        casing_rule,
        slang_rule,
        jokes_rule,
        emoji_rule,
    ]

    add_desc = "Merespons dengan gaya santai dan mengalir alami, memprioritaskan keringkasan dan keramahan tanpa nada kaku."

    profile_text = (
        "Style Profile Pemilik Akun (Hasil Analisis Real-Chat):\n"
        + "\n".join(f"- {r}" for r in rules)
        + f"\n- {add_desc}"
    )

    details = {
        "length": len_desc,
        "language": lang_desc,
        "jokes": jokes_desc,
        "abbreviations": abbr_desc,
        "casing": casing_desc,
        "answering_style": answer_desc,
        "speaking_style": speak_desc,
        "emoji": emoji_desc,
        "frequent_emojis": frequent_emojis_desc,
    }

    return {
        "summary": f"{speak_desc}, {len_desc}",
        "profile_text": profile_text,
        "details": details,
        "additional_description": add_desc,
        "rules": rules,
    }


async def _learn_style_from_samples(samples: list[str]) -> dict[str, Any]:
    """
    Ekstrak Style Profile dari kumpulan sampel pesan chat pengguna.
    Menggunakan Gemini API dengan Structured JSON Schema, dengan fallback ke modul analisis linguistik.
    Mengembalikan dictionary lengkap data hasil analisis untuk disimpan ke database.
    """
    api_key = get_api_key()
    heuristic_res = _heuristic_analyze_style(samples)

    if not api_key:
        return {
            "profile_text": heuristic_res["profile_text"],
            "details": heuristic_res["details"],
            "additional_description": heuristic_res["additional_description"],
            "rules": heuristic_res["rules"],
        }

    try:
        from google import genai
        from google.genai import types

        client_ai = genai.Client(
            api_key=api_key,
            http_options={"headers": {"User-Agent": "aistudio-build"}},
        )

        samples_text = "\n".join(f"{i+1}. \"{s}\"" for i, s in enumerate(samples[:25]))
        prompt = (
            "Kamu adalah penganalisis gaya mengetik percakapan Telegram manusia.\n"
            "Tugasmu: Analisis pola gaya mengetik pemilik akun dari sampel pesan chat aslinya di bawah ini.\n\n"
            "ATURAN WAJIB:\n"
            "1. Ekstrak HANYA pola penulisan yang benar-benar ada pada sampel (panjang kata, bahasa, jokes, singkatan, casing, cara jawab, gaya bicara, emoji, emoji sering digunakan).\n"
            "2. DILARANG membuat asumsi 'Technical', 'Minimalist Userbot', format CLI, atau format bullet kaku.\n"
            "3. DILARANG memaksa bahasa formal atau gaya customer service.\n"
            "4. Buat 'profile_rules' berupa 4-6 butir instruksi gaya percakapan yang santai, luwes, dan alami persis sesuai sampel.\n"
            "5. Buat 'additional_description' berupa deskripsi ringkas (1-2 kalimat) gaya mengetik pemilik akun.\n\n"
            f"Sampel Pesan Chat Asli Pengguna ({len(samples)} pesan):\n"
            f"{samples_text}\n"
        )

        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1000,
            response_mime_type="application/json",
            response_schema=StyleAnalysisSchema,
        )

        loop = asyncio.get_running_loop()
        models_to_try = [get_active_model()] + FALLBACK_MODELS
        seen_models = set()
        dedup_models = []
        for m in models_to_try:
            if m and m not in seen_models:
                seen_models.add(m)
                dedup_models.append(m)

        response = None
        for model_candidate in dedup_models:
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda m=model_candidate: client_ai.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=config,
                    ),
                )
                if response and response.text and response.text.strip():
                    break
            except Exception as model_err:
                log.debug(f"[AI Style Learn] Model {model_candidate} error: {model_err}")
                continue

        if response and response.text and response.text.strip():
            raw_json = response.text.strip()
            # Validasi dengan Pydantic
            try:
                parsed = StyleAnalysisSchema.model_validate_json(raw_json)
                rules = [r for r in parsed.profile_rules if r.strip()]
                learned_profile = (
                    "Style Profile Pemilik Akun (Hasil Analisis Real-Chat):\n"
                    + "\n".join(f"- {r}" for r in rules)
                    + (f"\n- {parsed.additional_description}" if parsed.additional_description else "")
                )
                details = {
                    "length": parsed.length_desc,
                    "language": parsed.language_desc,
                    "jokes": parsed.jokes_desc,
                    "abbreviations": parsed.abbreviations_desc,
                    "casing": parsed.casing_desc,
                    "answering_style": parsed.answering_style_desc,
                    "speaking_style": parsed.speaking_style_desc,
                    "emoji": parsed.emoji_desc,
                    "frequent_emojis": parsed.frequent_emojis_desc,
                }
                return {
                    "profile_text": learned_profile,
                    "details": details,
                    "additional_description": parsed.additional_description,
                    "rules": rules,
                }
            except Exception as parse_err:
                log.debug(f"[AI Style Learn] Pydantic validation fallback to json.loads: {parse_err}")
                data = json.loads(raw_json)
                rules = data.get("profile_rules", heuristic_res["rules"])
                learned_profile = (
                    "Style Profile Pemilik Akun (Hasil Analisis Real-Chat):\n"
                    + "\n".join(f"- {r}" for r in rules if isinstance(r, str) and r.strip())
                )
                details = {
                    "length": data.get("length_desc", heuristic_res["details"]["length"]),
                    "language": data.get("language_desc", heuristic_res["details"]["language"]),
                    "jokes": data.get("jokes_desc", heuristic_res["details"]["jokes"]),
                    "abbreviations": data.get("abbreviations_desc", heuristic_res["details"]["abbreviations"]),
                    "casing": data.get("casing_desc", heuristic_res["details"]["casing"]),
                    "answering_style": data.get("answering_style_desc", heuristic_res["details"]["answering_style"]),
                    "speaking_style": data.get("speaking_style_desc", heuristic_res["details"]["speaking_style"]),
                    "emoji": data.get("emoji_desc", heuristic_res["details"]["emoji"]),
                    "frequent_emojis": data.get("frequent_emojis_desc", heuristic_res["details"]["frequent_emojis"]),
                }
                return {
                    "profile_text": learned_profile,
                    "details": details,
                    "additional_description": data.get("additional_description", heuristic_res["additional_description"]),
                    "rules": rules,
                }

    except Exception as exc:
        log.warning(f"[AI Style Learn] Gemini analysis error, using heuristic profile: {exc}")

    return {
        "profile_text": heuristic_res["profile_text"],
        "details": heuristic_res["details"],
        "additional_description": heuristic_res["additional_description"],
        "rules": heuristic_res["rules"],
    }


def setup(client) -> None:
    """Daftarkan command .aistyle pada instance client."""

    @client.on_message(dynamic_command("aistyle") & filters.me)
    async def cmd_aistyle(client, message):
        """
        Handler command .aistyle:
        - .aistyle : Tampilkan status AI Style (LEARN + SET)
        - .aistyle learn : Pelajari pola gaya mengetik dari chat / tampilkan hasil LEARN
        - .aistyle set <prompt> : Setel atau perbarui manual prompt AI Style
        - .aistyle reset : Kembalikan gaya ke default bawaan
        """
        chat_id = message.chat.id
        raw_text = (message.text or message.caption or "").strip()
        parts = raw_text.split(maxsplit=2)
        subcommand = parts[1].lower() if len(parts) > 1 else ""

        # Hapus pesan command dari chat/grup sesegera mungkin
        try:
            await message.delete()
        except Exception:
            pass

        # ── 1. Sub-command: LEARN (.aistyle learn) ──────────────────────────
        if subcommand == "learn":
            # Ambil sampel pesan dari riwayat chat saat ini untuk pembelajaran
            samples: list[str] = []
            my_id = getattr(getattr(client, "me", None), "id", None)
            if not my_id:
                try:
                    me = await client.get_me()
                    my_id = me.id if me else None
                except Exception:
                    my_id = None

            try:
                async for msg in client.get_chat_history(chat_id, limit=60):
                    if not msg:
                        continue
                    txt = (msg.text or msg.caption or "").strip()
                    if not txt:
                        continue
                    # Abaikan pesan command bot
                    if txt.startswith((".", "!", "/")):
                        continue

                    is_owner_msg = getattr(msg, "outgoing", False) or (
                        msg.from_user and ((my_id and msg.from_user.id == my_id) or getattr(msg.from_user, "is_self", False))
                    )

                    if is_owner_msg:
                        samples.append(txt)
                    elif len(samples) < 15 and txt:
                        # Fallback ke pesan chat umum jika pesan owner sedikit
                        samples.append(txt)

                    if len(samples) >= 25:
                        break
            except Exception as exc:
                log.warning(f"[AI Style Learn] Gagal mengambil riwayat pesan: {exc}")

            # Jika sampel percakapan di chat saat ini mencukupi (>=3), lakukan analisis baru
            if len(samples) >= 3:
                learned_data = await _learn_style_from_samples(samples)
                # Simpan Style Profile ke runtime & database dalam bentuk JSON terstruktur
                set_learned_style(json.dumps(learned_data, ensure_ascii=False))

            # Tampilkan status LEARN (jika belum dipelajari → Default, jika sudah → Gaya Gua + Hasil Analisis)
            chat_ui_text = format_aistyle_learn_ui()
            res_msg = await send_ui(client, chat_id, chat_ui_text, expandable=True)
            asyncio.create_task(auto_delete(message, delay=30, force=True))
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=30, force=True))

            # Kirim ringkasan ke Manager Bot jika dikonfigurasi
            learned_current = get_learned_style_data()
            if learned_current:
                det = learned_current.get("details", {})
                manager_text = (
                    "🎨 **[AI Style Learn] Gaya Mengetik Dipelajari**\n\n"
                    f"• Mode: `Gaya Gua`\n"
                    f"• Status: `Aktif`\n"
                    f"• Gaya Dipelajari: `Style Profil Pemilik Akun`\n\n"
                    "📋 **Hasil Analisis:**\n"
                    f"• Panjang chat: `{det.get('length', '-')}`\n"
                    f"• Bahasa: `{det.get('language', '-')}`\n"
                    f"• Jokes: `{det.get('jokes', '-')}`\n"
                    f"• Singkatan: `{det.get('abbreviations', '-')}`\n"
                    f"• Casing: `{det.get('casing', '-')}`\n"
                    f"• Cara jawab: `{det.get('answering_style', '-')}`\n"
                    f"• Gaya bicara: `{det.get('speaking_style', '-')}`\n"
                    f"• Emoji: `{det.get('emoji', '-')}`\n"
                    f"• Emoji sering digunakan: `{det.get('frequent_emojis', '-')}`"
                )
            else:
                manager_text = (
                    "🎨 **[AI Style Learn] Status Saat Ini**\n"
                    "• Mode: `Default`\n"
                    "• Status: `Aktif`\n"
                    "• Gaya: `Default`\n"
                    "• Gaya Dipelajari: `Belum dipelajari`"
                )
            asyncio.create_task(_notify_manager_bot(client, manager_text))
            return

        # ── 2. Sub-command: SET (.aistyle set <prompt>) ─────────────────────
        if subcommand == "set":
            if len(parts) < 3 or not parts[2].strip():
                warn_text = warning(
                    title="FORMAT SALAH",
                    message=(
                        "Gunakan: .aistyle set <prompt>\n"
                        "• Contoh: .aistyle set jawab dengan gaya cuek, singkat, dan jangan terlalu formal"
                    ),
                    emoji="⚠️",
                )
                res_msg = await send_ui(client, chat_id, warn_text)
                asyncio.create_task(auto_delete(message, delay=30, force=True))
                if res_msg:
                    asyncio.create_task(auto_delete(res_msg, delay=30, force=True))
                return

            new_prompt = parts[2].strip()
            # Simpan prompt manual SET ke runtime & database
            set_manual_style(new_prompt)

            # Tampilkan notifikasi keberhasilan menggunakan format standar UBot
            chat_ui_text = success(
                title="AI STYLE SET DIPERBARUI",
                message="Prompt berhasil diperbarui.",
                emoji="✅",
            )
            res_msg = await send_ui(client, chat_id, chat_ui_text, expandable=True)
            asyncio.create_task(auto_delete(message, delay=30, force=True))
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=30, force=True))

            manager_text = (
                "🎨 **[AI Style Set] Prompt Manual Diperbarui**\n\n"
                f"📝 **Prompt:**\n_{new_prompt}_\n\n"
                "✅ Prompt berhasil disimpan dan aktif diterapkan pada AI."
            )
            asyncio.create_task(_notify_manager_bot(client, manager_text))
            return

        # ── 3. Sub-command: RESET (.aistyle reset) ──────────────────────────
        if subcommand == "reset":
            reset_custom_style()

            chat_ui_text = success(
                title="AI STYLE DIRESET",
                message="ℹ️ Status : Gaya penulisan AI kembali ke default bawaan",
                emoji="🎨",
            )
            res_msg = await send_ui(client, chat_id, chat_ui_text, expandable=True)
            asyncio.create_task(auto_delete(message, delay=30, force=True))
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=30, force=True))

            manager_text = (
                "🎨 **[AI Style Profile] Direset ke Default**\n"
                "• Gaya penulisan AI kembali ke bawaan (Santai, gaul natural, responsif)."
            )
            asyncio.create_task(_notify_manager_bot(client, manager_text))
            return

        # ── 4. Default / Sub-command: STATUS (.aistyle / .aistyle status) ────
        if subcommand in ("", "status"):
            chat_ui_text = format_aistyle_full_ui()
            res_msg = await send_ui(client, chat_id, chat_ui_text, expandable=True)
            asyncio.create_task(auto_delete(message, delay=30, force=True))
            if res_msg:
                asyncio.create_task(auto_delete(res_msg, delay=30, force=True))

            # Notifikasi ke Manager Bot
            learned_current = get_learned_style_data()
            manual_current = get_manual_style()
            manager_lines = [
                "🎨 **[AI Style] Status Saat Ini**",
                f"• Mode: `{'Gaya Gua' if learned_current else 'Default'}`",
                f"• Status: `Aktif`",
                f"• Gaya Dipelajari: `{'Style Profil Pemilik Akun' if learned_current else 'Belum dipelajari'}`",
                f"• Prompt SET: `{(manual_current or 'Belum diatur')}`",
            ]
            manager_text = "\n".join(manager_lines)
            asyncio.create_task(_notify_manager_bot(client, manager_text))
            return

        # ── Sub-command Lainnya / Bantuan ───────────────────────────────────
        help_ui_text = format_ui(
            title="AI STYLE HELP",
            body=(
                "📖 Petunjuk Command:\n"
                "• .aistyle : Tampilkan status AI Style & prompt aktif\n"
                "• .aistyle learn : Pelajari pola mengetik dari riwayat chat\n"
                "• .aistyle set <prompt> : Setel atau perbarui manual prompt AI Style\n"
                "• .aistyle reset : Kembalikan gaya tulisan ke default bawaan"
            ),
            emoji="🎨",
            expandable=True,
        )
        res_msg = await send_ui(client, chat_id, help_ui_text, expandable=True)
        asyncio.create_task(auto_delete(message, delay=30, force=True))
        if res_msg:
            asyncio.create_task(auto_delete(res_msg, delay=30, force=True))

        help_text = (
            "🎨 **[AI Style Profile] Petunjuk Command**\n"
            "• `.aistyle` : Tampilkan status AI Style & prompt aktif\n"
            "• `.aistyle learn` : Pelajari pola mengetik dari riwayat chat\n"
            "• `.aistyle set <prompt>` : Setel atau perbarui manual prompt AI Style\n"
            "• `.aistyle reset` : Kembalikan gaya tulisan ke default bawaan"
        )
        asyncio.create_task(_notify_manager_bot(client, help_text))
