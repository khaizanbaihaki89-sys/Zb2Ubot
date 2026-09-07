"""
IBEKS USERBOT - Fun Card Generator
Implementasi rendering kartu identitas menggunakan TEMPLATE RESMI:
- cardp_ gold.jpg (Pria / Gold Theme)
- cardw_ pink.jpg (Wanita / Pink Theme)

Aturan Desain & Tipografi:
1. TEMPLATE: Menggunakan file template asli apa adanya tanpa resize, crop, redraw, atau ubah desain.
   - Header 'ZB ID CARD', footer 'IBEKS UBOT', barcode, ring, garis, dan ornamen tetap asli.
2. TEKS INFORMASI (Label, Colon, Value):
   - Font: Montserrat SemiBold (40 px tetap untuk semua teks informasi).
   - Alignment: Semua tanda ':' sejajar secara vertikal.
   - Alignment Value: Semua value dimulai pada posisi yang sama persis setelah tanda ':'.
   - Text Wrapping: Jika value panjang, baris lanjutan sejajar secara vertikal dengan awal value setelah ':'.
   - Tanpa auto-shrink.
   - Warna teks: Menyesuaikan warna tema kartu template (Gold untuk Pria / Rose Pink untuk Wanita).
3. FOTO PROFIL:
   - Foto asli user di-crop lingkaran sempurna.
   - Posisi dan ukuran pas di dalam ring template tanpa keluar dari area lingkaran.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
try:
    from pyrogram import Client
    from pyrogram.types import User
except ImportError:
    Client = Any  # type: ignore
    User = Any    # type: ignore

from utils.card_stats import get_card_stats, get_user_display_name


# Ukuran font Montserrat SemiBold tetap untuk seluruh teks informasi (40 px)
FONT_SIZE = 40

# Konfigurasi Tema Warna & Template Resmi
THEMES: dict[str, dict[str, Any]] = {
    "male": {
        "name": "GOLD",
        "score_label": "TAMPAN",
        "template_candidates": [
            "cardp_ gold.jpg",
            "cardp_gold.jpg",
            "cardp gold.jpg",
            "id cardp.jpg",
            "id_cardp.jpg",
            "card_template.jpg",
            "card_template.png",
        ],
        "text_color": (225, 195, 125),      # Gold metallic matching template
        "text_shadow": (25, 18, 10),
        "avatar_bg": (28, 26, 24),
        "avatar_accent": (225, 195, 125),
        "avatar_cx": 248,
        "avatar_cy": 362,
        "avatar_radius": 166,
        "label_x": 460,
        "colon_x": 730,
        "val_x": 760,
        "clean_box": (450, 190, 1270, 605),
    },
    "female": {
        "name": "PINK",
        "score_label": "CANTIK",
        "template_candidates": [
            "cardw_ pink.jpg",
            "cardw_pink.jpg",
            "cardw pink.jpg",
            "id_ cardw.jpg",
            "id_cardw.jpg",
            "card_template_wanita.jpg",
            "card_template_wanita.png",
        ],
        "text_color": (240, 175, 190),      # Rose pink metallic matching template
        "text_shadow": (35, 10, 20),
        "avatar_bg": (32, 24, 26),
        "avatar_accent": (240, 175, 190),
        "avatar_cx": 240,
        "avatar_cy": 374,
        "avatar_radius": 158,
        "label_x": 455,
        "colon_x": 725,
        "val_x": 755,
        "clean_box": (440, 210, 1270, 625),
    },
}

THEMES["gold"] = THEMES["male"]
THEMES["cardp"] = THEMES["male"]
THEMES["pink"] = THEMES["female"]
THEMES["cardw"] = THEMES["female"]


def _get_font(size: int = FONT_SIZE) -> ImageFont.FreeTypeFont:
    """Mengambil font Montserrat SemiBold."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_paths = [
        os.path.join(current_dir, "..", "data", "fonts", "Montserrat-SemiBold.ttf"),
        os.path.join(current_dir, "..", "data", "fonts", "Montserrat-Variable.ttf"),
        os.path.join(os.getcwd(), "userbot", "data", "fonts", "Montserrat-SemiBold.ttf"),
        os.path.join(os.getcwd(), "userbot", "data", "fonts", "Montserrat-Variable.ttf"),
        "/usr/share/fonts/truetype/montserrat/Montserrat-SemiBold.ttf",
        "/usr/share/fonts/truetype/Montserrat-SemiBold.ttf",
        "/usr/share/fonts/opentype/montserrat/Montserrat-SemiBold.otf",
        os.path.join(current_dir, "..", "data", "fonts", "RobotoSlab-Regular.otf"),
        os.path.join(current_dir, "..", "data", "fonts", "card_font.ttf"),
    ]

    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue

    return ImageFont.load_default()


def _load_template(candidates: list[str]) -> Image.Image:
    """Mencari dan memuat file template asli dari folder data tanpa mengubah ukuran/desain."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        os.path.join(current_dir, "..", "data"),
        os.path.join(current_dir, "..", "..", "userbot", "data"),
        os.path.join(os.getcwd(), "userbot", "data"),
        os.path.join(os.getcwd(), "data"),
        "/app/applet/userbot/data",
        "userbot/data",
    ]

    for filename in candidates:
        for sdir in search_dirs:
            full_path = os.path.join(sdir, filename)
            if os.path.isfile(full_path):
                try:
                    img = Image.open(full_path).convert("RGB")
                    return img
                except Exception:
                    continue

    # Fallback canvas jika template tidak ditemukan
    return Image.new("RGB", (1336, 784), (20, 20, 20))


def _clean_text_area(
    img: Image.Image,
    box: tuple[int, int, int, int],
) -> Image.Image:
    """
    Membersihkan area informasi pada kartu agar label & value baru dapat
    dirender secara presisi dengan font Montserrat SemiBold tanpa bayangan teks lama.
    """
    x1, y1, x2, y2 = box
    arr = np.array(img).copy()

    for y in range(y1, y2):
        row = arr[y, x1:x2, :]
        mask = (row.mean(axis=1) < 65)
        if mask.sum() > 20:
            bg_color = np.median(row[mask], axis=0).astype(np.uint8)
        else:
            bg_color = arr[y, max(0, x1 - 10):x1, :].mean(axis=0).astype(np.uint8)
        noise = np.random.normal(0, 1.2, (x2 - x1, 3))
        new_row = np.clip(bg_color + noise, 0, 255).astype(np.uint8)
        arr[y, x1:x2, :] = new_row

    cleaned = Image.fromarray(arr)
    mask = Image.new("L", img.size, 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.rectangle([x1 + 5, y1 + 5, x2 - 5, y2 - 5], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(4))
    return Image.composite(cleaned, img, mask)


def _draw_default_avatar(diameter: int, bg_color: tuple[int, int, int], accent_color: tuple[int, int, int]) -> Image.Image:
    """Membuat gambar avatar default siluet bulat jika user tidak memiliki foto profil."""
    avatar = Image.new("RGB", (diameter, diameter), bg_color)
    draw = ImageDraw.Draw(avatar)

    cx = diameter // 2
    r_head = int(diameter * 0.20)
    head_y = int(diameter * 0.35)
    r_body = int(diameter * 0.38)
    body_y = int(diameter * 0.85)

    # Kepala siluet bulat
    draw.ellipse([cx - r_head, head_y - r_head, cx + r_head, head_y + r_head], fill=accent_color)
    # Pundak siluet melengkung
    draw.chord([cx - r_body, body_y - r_body, cx + r_body, body_y + r_body], 180, 360, fill=accent_color)

    return avatar


def _render_info_row(
    draw: ImageDraw.Draw,
    label: str,
    value: str,
    label_x: int,
    colon_x: int,
    val_x: int,
    baseline_y: int,
    text_color: tuple[int, int, int],
    shadow_color: tuple[int, int, int],
    font: ImageFont.FreeTypeFont,
    shadow_offset: tuple[int, int] = (2, 2),
    max_x: int = 1260,
    line_height: int = 44,
) -> None:
    """
    Merender baris teks informasi:
    - Label, tanda ':', dan value semuanya menggunakan font Montserrat SemiBold 40 px.
    - Semua tanda ':' sejajar secara vertikal di posisi colon_x.
    - Semua value dimulai tepat di posisi val_x.
    - Wrapping: Jika value terlalu panjang, baris lanjutan turun ke bawah dan
      dimulai tepat di posisi val_x (sejajar vertikal dengan awal value).
    - Tanpa auto-shrink.
    """
    ox, oy = shadow_offset

    # 1. Render Label
    draw.text((label_x + ox, baseline_y + oy), label, font=font, fill=shadow_color, anchor="ls")
    draw.text((label_x, baseline_y), label, font=font, fill=text_color, anchor="ls")

    # 2. Render Colon (sejajar vertikal)
    draw.text((colon_x + ox, baseline_y + oy), ":", font=font, fill=shadow_color, anchor="ls")
    draw.text((colon_x, baseline_y), ":", font=font, fill=text_color, anchor="ls")

    # 3. Render Value dengan wrapping jika panjang
    max_width = max(100, max_x - val_x)
    if font.getlength(value) <= max_width:
        lines = [value]
    else:
        words = value.split(" ")
        lines = []
        curr_words: list[str] = []
        for word in words:
            test_line = " ".join(curr_words + [word]) if curr_words else word
            if font.getlength(test_line) <= max_width:
                curr_words.append(word)
            else:
                if curr_words:
                    lines.append(" ".join(curr_words))
                    curr_words = [word]
                else:
                    lines.append(word)
                    curr_words = []
        if curr_words:
            lines.append(" ".join(curr_words))

    # Render setiap baris value dengan indentasi val_x yang sama persis
    for idx, line_text in enumerate(lines):
        line_baseline_y = baseline_y + (idx * line_height)
        draw.text((val_x + ox, line_baseline_y + oy), line_text, font=font, fill=shadow_color, anchor="ls")
        draw.text((val_x, line_baseline_y), line_text, font=font, fill=text_color, anchor="ls")


async def generate_fun_card(
    client: Client,
    user: User,
    card_type: str = "male",
) -> io.BytesIO:
    """
    Menghasilkan Fun ID Card menggunakan TEMPLATE RESMI:
    - .card / .cardp (male / gold): Menggunakan template Gold (cardp_ gold.jpg)
    - .cardw (female / pink): Menggunakan template Pink (cardw_ pink.jpg)
    """
    card_key = card_type.lower()
    is_female = card_key in {"female", "pink", "cardw"}
    theme = THEMES["female"] if is_female else THEMES["male"]

    # 1. Dapatkan data statistik deterministik mingguan
    stats = get_card_stats(user, "female" if is_female else "male")
    display_name = get_user_display_name(user)
    username = f"@{user.username}" if user.username else "-"

    # 2. Muat gambar template asli apa adanya tanpa resize/crop
    base_img = _load_template(theme["template_candidates"])
    # Bersihkan area teks informasi untuk rendering presisi
    img = _clean_text_area(base_img, theme["clean_box"])
    draw = ImageDraw.Draw(img)

    # 3. Proses Foto Profil: Crop bulat mengikuti lingkaran ring template
    cx = theme["avatar_cx"]
    cy = theme["avatar_cy"]
    radius = theme["avatar_radius"]
    diameter = radius * 2

    user_photo_img: Optional[Image.Image] = None
    try:
        if user.photo and user.photo.big_file_id:
            photo_bytes = await client.download_media(user.photo.big_file_id, in_memory=True)
            if photo_bytes:
                photo_bytes.seek(0)
                user_photo_img = Image.open(photo_bytes).convert("RGB")
    except Exception:
        user_photo_img = None

    if user_photo_img is None:
        user_photo_img = _draw_default_avatar(diameter, theme["avatar_bg"], theme["avatar_accent"])
    else:
        # Resize & crop proporsional bujursangkar (diameter x diameter)
        user_photo_img = ImageOps.fit(user_photo_img, (diameter, diameter), method=Image.Resampling.LANCZOS)

    # Mask lingkaran sempurna berkualitas tinggi (antialiased)
    mask = Image.new("L", (diameter * 2, diameter * 2), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, diameter * 2 - 1, diameter * 2 - 1], fill=255)
    mask = mask.resize((diameter, diameter), Image.Resampling.LANCZOS)

    # Tempel foto bulat ke dalam area lingkaran template
    img.paste(user_photo_img, (cx - radius, cy - radius), mask=mask)

    # 4. Render TEKS INFORMASI menggunakan font Montserrat SemiBold 40 px
    font = _get_font(FONT_SIZE)
    score_val = f"{stats['score']}%"

    if is_female:
        # Pink Template (cardw_ pink.jpg)
        info_rows: list[tuple[str, str, int]] = [
            ("NAMA", display_name, 253),
            ("USERNAME", username, 319),
            ("CANTIK", score_val, 384),
            ("AURA", stats["aura"], 449),
            ("TIER", stats["tier"], 514),
            ("MENTAL", stats["mental"], 579),
        ]
    else:
        # Gold Template (cardp_ gold.jpg)
        info_rows: list[tuple[str, str, int]] = [
            ("NAMA", display_name, 233),
            ("USERNAME", username, 299),
            ("TAMPAN", score_val, 365),
            ("AURA", stats["aura"], 431),
            ("TIER", stats["tier"], 496),
            ("MENTAL", stats["mental"], 563),
        ]

    for label_text, value_text, baseline_y in info_rows:
        _render_info_row(
            draw=draw,
            label=label_text,
            value=value_text,
            label_x=theme["label_x"],
            colon_x=theme["colon_x"],
            val_x=theme["val_x"],
            baseline_y=baseline_y,
            text_color=theme["text_color"],
            shadow_color=theme["text_shadow"],
            font=font,
            shadow_offset=(2, 2),
            max_x=1260,
            line_height=44,
        )

    # 5. Simpan ke BytesIO PNG berkualitas tinggi
    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output


