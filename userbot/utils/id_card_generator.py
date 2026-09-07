"""
IBEKS USERBOT - ID Card Generator v2
Membuat kartu identitas futuristik hitam-hijau neon untuk command .id,
.cardp, dan .cardw. Layout terinspirasi dari kartu ID game/esports.
Lebih terang, lebih bersih, dan lebih mirip referensi.
"""

import io
import os
import random
from datetime import datetime
from typing import List, Optional, Tuple

import qrcode
from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pyrogram import Client
from pyrogram.types import User

from utils.fun_data import CTAMPAN_AURA, CTAMPAN_TIER, CCANTIK_AURA, CCANTIK_TIER
from utils.id_data import STATUS_MENTAL
from utils.logger import log


# ── Dimensi & Warna ─────────────────────────────────────────────────────────

CARD_WIDTH = 1280
CARD_HEIGHT = 720

COLORS = {
    "bg": (12, 14, 12),
    "bg_panel": (18, 22, 18),
    "neon": (57, 255, 20),
    "neon_bright": (140, 255, 80),
    "neon_yellow": (220, 255, 0),
    "neon_dim": (40, 100, 35),
    "white": (255, 255, 255),
    "gray": (180, 180, 180),
    "dark_gray": (80, 80, 80),
    "black": (0, 0, 0),
}

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _current_week_seed() -> int:
    iso = datetime.now().isocalendar()
    return iso.year * 100 + iso.week


def _generate_stats(user: User, card_type: str) -> dict:
    """
    Generate nilai deterministik untuk kartu ID.
    card_type: 'id' | 'male' | 'female'
    """
    base_seed = user.id * 100000 + _current_week_seed()
    rng = random.Random(base_seed)

    tampan_pct = rng.randint(0, 100)
    cantik_pct = rng.randint(0, 100)

    if card_type == "male":
        aura = rng.choice(CTAMPAN_AURA)
        tier = rng.choice(CTAMPAN_TIER)
    elif card_type == "female":
        aura = rng.choice(CCANTIK_AURA)
        tier = rng.choice(CCANTIK_TIER)
    else:  # id
        aura = rng.choice(CTAMPAN_AURA)
        tier = rng.choice(CTAMPAN_TIER)

    mental = rng.choice(STATUS_MENTAL)

    return {
        "tampan": tampan_pct,
        "cantik": cantik_pct,
        "aura": aura,
        "tier": tier,
        "mental": mental,
    }


async def _fetch_profile_photo(client: Client, user: User) -> Optional[Image.Image]:
    """Download foto profil user dari Telegram."""
    try:
        if not user.photo:
            return None
        photo_io = await client.download_media(user.photo.big_file_id, in_memory=True)
        if photo_io is None:
            return None
        if isinstance(photo_io, bytes):
            return Image.open(io.BytesIO(photo_io))
        if hasattr(photo_io, "getvalue"):
            return Image.open(io.BytesIO(photo_io.getvalue()))
        if hasattr(photo_io, "read"):
            return Image.open(photo_io)
        return None
    except Exception as exc:
        log.warning(f"[IDCard] Gagal download foto profil: {exc}")
        return None


def _create_avatar(size: int, color: Tuple[int, int, int]) -> Image.Image:
    """Buat avatar default lingkaran dengan silhouette neon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size, size], fill=(20, 25, 20, 255))
    # Silhouette kepala
    draw.ellipse(
        [size * 0.35, size * 0.18, size * 0.65, size * 0.55],
        fill=(*color, 120),
    )
    # Silhouette bahu
    draw.ellipse(
        [size * 0.15, size * 0.60, size * 0.85, size * 1.15],
        fill=(*color, 100),
    )
    return img


def _circular_mask(image: Image.Image, size: int) -> Image.Image:
    """Crop image menjadi lingkaran dengan ukuran tertentu."""
    image = image.convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.paste(image, (x, y))

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size, size], fill=255)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(canvas, (0, 0), mask)
    return result


def _draw_glow_line(
    draw: ImageDraw.ImageDraw,
    start: Tuple[int, int],
    end: Tuple[int, int],
    color: Tuple[int, int, int],
    width: int = 2,
) -> None:
    """Gambar garis dengan efek glow."""
    draw.line([start, end], fill=color, width=width)


def _draw_corner_brackets(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    color: Tuple[int, int, int],
    length: int = 50,
    width: int = 3,
) -> None:
    """Gambar bracket sudut HUD."""
    draw.line([(x, y + length), (x, y), (x + length, y)], fill=color, width=width)
    draw.line([(x + w - length, y), (x + w, y), (x + w, y + length)], fill=color, width=width)
    draw.line([(x, y + h - length), (x, y + h), (x + length, y + h)], fill=color, width=width)
    draw.line([(x + w - length, y + h), (x + w, y + h), (x + w, y + h - length)], fill=color, width=width)


def _draw_target_brackets(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int,
    color: Tuple[int, int, int],
    length: int = 35,
    width: int = 3,
) -> None:
    """Gambar bracket target di sekitar lingkaran foto."""
    r = radius + 20
    # Top-left arc
    draw.line([(cx - r, cy - r + length), (cx - r, cy - r), (cx - r + length, cy - r)], fill=color, width=width)
    # Top-right
    draw.line([(cx + r - length, cy - r), (cx + r, cy - r), (cx + r, cy - r + length)], fill=color, width=width)
    # Bottom-left
    draw.line([(cx - r, cy + r - length), (cx - r, cy + r), (cx - r + length, cy + r)], fill=color, width=width)
    # Bottom-right
    draw.line([(cx + r - length, cy + r), (cx + r, cy + r), (cx + r, cy + r - length)], fill=color, width=width)


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    percent: int,
    color: Tuple[int, int, int],
) -> None:
    """Gambar progress bar dengan glow."""
    percent = max(0, min(100, percent))
    filled = int(width * percent / 100)
    # Background track
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height // 2, outline=COLORS["dark_gray"], width=2)
    # Filled
    if filled > 0:
        draw.rounded_rectangle([x, y, x + filled, y + height], radius=height // 2, fill=color)
    # Glow strip tipis
    if filled > 2:
        draw.rounded_rectangle([x + filled - 2, y, x + filled, y + height], radius=height // 2, fill=COLORS["white"])


def _draw_text_shadow(
    draw: ImageDraw.ImageDraw,
    text: str,
    pos: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
) -> None:
    """Gambar teks dengan bayangan tipis."""
    x, y = pos
    draw.text((x + 2, y + 2), text, font=font, fill=COLORS["black"])
    draw.text((x, y), text, font=font, fill=fill)


def _draw_tech_grid(draw: ImageDraw.ImageDraw, step: int = 50) -> None:
    """Gambar grid teknis tipis sebagai background."""
    color = COLORS["neon_dim"]
    for x in range(0, CARD_WIDTH + 1, step):
        draw.line([(x, 0), (x, CARD_HEIGHT)], fill=color, width=1)
    for y in range(0, CARD_HEIGHT + 1, step):
        draw.line([(0, y), (CARD_WIDTH, y)], fill=color, width=1)


def _draw_header_bar(draw: ImageDraw.ImageDraw) -> None:
    """Gambar header bar dengan garis-garis HUD."""
    # Top bar
    draw.rectangle([0, 0, CARD_WIDTH, 80], fill=(10, 12, 10, 200))
    draw.line([(0, 80), (CARD_WIDTH, 80)], fill=COLORS["neon"], width=2)
    # Decorative dots
    for x in range(40, CARD_WIDTH, 80):
        draw.ellipse([x - 2, 75 - 2, x + 2, 75 + 2], fill=COLORS["neon_dim"])
    # Vertical separator left-right
    draw.line([(700, 110), (700, 620)], fill=COLORS["neon_dim"], width=1)


def _generate_barcode(user_id: int) -> Image.Image:
    """Generate barcode Code128 dari user ID."""
    try:
        writer = ImageWriter()
        writer.set_options({
            "write_text": False,
            "module_height": 14,
            "module_width": 0.28,
            "quiet_zone": 2,
        })
        code = Code128(str(user_id), writer=writer)
        buffer = io.BytesIO()
        code.write(buffer)
        buffer.seek(0)
        return Image.open(buffer).convert("RGBA")
    except Exception as exc:
        log.warning(f"[IDCard] Gagal generate barcode: {exc}")
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))


def _generate_qr(user_id: int) -> Image.Image:
    """Generate QR code dari user ID."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(str(user_id))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        return img
    except Exception as exc:
        log.warning(f"[IDCard] Gagal generate QR: {exc}")
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))


def _draw_logo(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """Gambar logo IBEKS USERBOT di bagian bawah."""
    font_big = _font("DejaVuSans-Bold.ttf", 44)
    font_small = _font("DejaVuSans-Bold.ttf", 20)

    text = "IBEKS"
    bbox = draw.textbbox((0, 0), text, font=font_big)
    text_w = bbox[2] - bbox[0]
    _draw_text_shadow(draw, text, (cx - text_w // 2, cy - 40), font_big, COLORS["white"])

    sub = "USERBOT"
    bbox = draw.textbbox((0, 0), sub, font=font_small)
    sub_w = bbox[2] - bbox[0]
    _draw_text_shadow(draw, sub, (cx - sub_w // 2, cy + 10), font_small, COLORS["neon"])

    # Skull icon
    draw.ellipse([cx - 14, cy - 72, cx + 14, cy - 46], outline=COLORS["neon"], width=3)
    draw.ellipse([cx - 6, cy - 64, cx - 2, cy - 58], fill=COLORS["neon"])
    draw.ellipse([cx + 2, cy - 64, cx + 6, cy - 58], fill=COLORS["neon"])
    draw.rectangle([cx - 4, cy - 56, cx + 4, cy - 50], fill=COLORS["neon"])


async def generate_user_card(client: Client, user: User, card_type: str = "id") -> io.BytesIO:
    """
    Generate kartu ID futuristik.

    card_type:
      - 'id'     : kartu ID umum (tampilkan tampan + cantik)
      - 'male'   : kartu ID pria (ketampanan)
      - 'female' : kartu ID wanita (kecantikan)
    """
    stats = _generate_stats(user, card_type)
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    username = f"@{user.username}" if user.username else "N/A"
    user_id_str = str(user.id)

    # Fonts
    font_header = _font("DejaVuSans-Bold.ttf", 22)
    font_title = _font("DejaVuSans-Bold.ttf", 32)
    font_label = _font("DejaVuSans-Bold.ttf", 20)
    font_value = _font("DejaVuSans.ttf", 20)
    font_badge = _font("DejaVuSans-Bold.ttf", 16)
    font_small = _font("DejaVuSans.ttf", 13)
    font_percent = _font("DejaVuSans-Bold.ttf", 16)

    # Base image
    img = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    # Background gradient (radial brighter center)
    for r in range(max(CARD_WIDTH, CARD_HEIGHT) // 2, 0, -4):
        ratio = r / (max(CARD_WIDTH, CARD_HEIGHT) // 2)
        alpha = int(35 * (1 - ratio))
        draw.ellipse(
            [CARD_WIDTH // 2 - r, CARD_HEIGHT // 2 - r, CARD_WIDTH // 2 + r, CARD_HEIGHT // 2 + r],
            fill=(20, 28, 20, alpha),
        )

    # Tech grid
    _draw_tech_grid(draw, step=60)

    # Main frame border
    _draw_corner_brackets(draw, 25, 20, CARD_WIDTH - 50, CARD_HEIGHT - 40, COLORS["neon"], length=80, width=4)
    draw.rectangle([40, 35, CARD_WIDTH - 40, CARD_HEIGHT - 35], outline=COLORS["neon_dim"], width=1)

    # Header
    _draw_header_bar(draw)
    _draw_text_shadow(draw, "ID CARD", (40, 28), font_header, COLORS["neon"])
    header_text = "IBEKS USERBOT OFFICIAL ID"
    bbox = draw.textbbox((0, 0), header_text, font=font_header)
    header_w = bbox[2] - bbox[0]
    _draw_text_shadow(draw, header_text, ((CARD_WIDTH - header_w) // 2, 28), font_header, COLORS["white"])

    # Title & Badge area
    badge_text = "IBEKS OFFICIAL"
    if card_type == "male":
        title_text = "MALE ID"
        badge_text = "IBEKS MALE"
    elif card_type == "female":
        title_text = "FEMALE ID"
        badge_text = "IBEKS FEMALE"
    else:
        title_text = "ID CARD"

    _draw_text_shadow(draw, title_text, (40, 110), font_title, COLORS["white"])

    # Badge
    badge_w, badge_h = 170, 32
    badge_x, badge_y = 40 + draw.textbbox((0, 0), title_text, font=font_title)[2] + 25, 112
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=8, fill=COLORS["neon_yellow"])
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(
        (badge_x + (badge_w - text_w) // 2, badge_y + (badge_h - text_h) // 2 - 1),
        badge_text,
        font=font_badge,
        fill=COLORS["black"],
    )

    # Info panel fields
    if card_type == "id":
        fields: List[Tuple[str, str, bool]] = [
            ("NAMA", name, False),
            ("USERNAME", username, False),
            ("USER ID", user_id_str, False),
            ("TAMPAN", f"{stats['tampan']}%", True),
            ("CANTIK", f"{stats['cantik']}%", True),
            ("AURA", stats["aura"], False),
            ("TIER", stats["tier"], False),
            ("STATUS MENTAL", stats["mental"], False),
        ]
    elif card_type == "male":
        fields = [
            ("NAMA", name, False),
            ("USERNAME", username, False),
            ("USER ID", user_id_str, False),
            ("KETAMPANAN", f"{stats['tampan']}%", True),
            ("AURA", stats["aura"], False),
            ("TIER", stats["tier"], False),
            ("STATUS MENTAL", stats["mental"], False),
        ]
    else:  # female
        fields = [
            ("NAMA", name, False),
            ("USERNAME", username, False),
            ("USER ID", user_id_str, False),
            ("KECANTIKAN", f"{stats['cantik']}%", True),
            ("AURA", stats["aura"], False),
            ("TIER", stats["tier"], False),
            ("STATUS MENTAL", stats["mental"], False),
        ]

    start_y = 180
    line_height = 52
    label_x = 40
    value_x = 230
    progress_width = 220

    for i, (label, value, is_progress) in enumerate(fields):
        y = start_y + i * line_height

        # Icon square neon
        draw.rectangle([label_x, y + 2, label_x + 22, y + 24], outline=COLORS["neon"], width=2)
        # Label
        _draw_text_shadow(draw, label, (label_x + 32, y), font_label, COLORS["neon"])
        _draw_text_shadow(draw, ":", (label_x + 185, y), font_label, COLORS["white"])

        # Value
        if is_progress:
            pct = int(value.replace("%", ""))
            _draw_text_shadow(draw, value, (value_x, y), font_value, COLORS["white"])
            _draw_progress_bar(draw, value_x + 65, y + 8, progress_width, 12, pct, COLORS["neon"])
        else:
            # Truncate panjang
            max_width = 440 if label == "STATUS MENTAL" else 460
            while True:
                bbox = draw.textbbox((0, 0), value, font=font_value)
                text_w = bbox[2] - bbox[0]
                if text_w <= max_width or len(value) <= 3:
                    break
                value = value[:-1]
            if len(value) < len(fields[i][1]):
                value += "..."
            _draw_text_shadow(draw, value, (value_x, y), font_value, COLORS["white"])

    # Profile photo area
    circle_center = (980, 340)
    circle_radius = 170

    # Target brackets around circle
    _draw_target_brackets(draw, circle_center[0], circle_center[1], circle_radius, COLORS["neon"], length=45, width=3)

    # Glow ring
    glow_layer = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    for offset in range(20, 0, -4):
        glow_draw.ellipse(
            [
                circle_center[0] - circle_radius - offset,
                circle_center[1] - circle_radius - offset,
                circle_center[0] + circle_radius + offset,
                circle_center[1] + circle_radius + offset,
            ],
            outline=(*COLORS["neon"], 25),
            width=5,
        )
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # Main neon ring
    draw.ellipse(
        [
            circle_center[0] - circle_radius,
            circle_center[1] - circle_radius,
            circle_center[0] + circle_radius,
            circle_center[1] + circle_radius,
        ],
        outline=COLORS["neon"],
        width=5,
    )
    # Inner dim ring
    draw.ellipse(
        [
            circle_center[0] - circle_radius + 12,
            circle_center[1] - circle_radius + 12,
            circle_center[0] + circle_radius - 12,
            circle_center[1] + circle_radius - 12,
        ],
        outline=COLORS["neon_dim"],
        width=2,
    )

    # Profile photo
    profile_img = await _fetch_profile_photo(client, user)
    if profile_img is None:
        profile_img = _create_avatar(circle_radius * 2 - 25, COLORS["neon"])
    profile_circle = _circular_mask(profile_img, circle_radius * 2 - 25)
    img.paste(
        profile_circle,
        (
            circle_center[0] - (circle_radius * 2 - 25) // 2,
            circle_center[1] - (circle_radius * 2 - 25) // 2,
        ),
        profile_circle,
    )

    # Bottom section: Barcode & QR
    barcode_img = _generate_barcode(user.id)
    barcode_img = barcode_img.resize((280, 70), Image.Resampling.LANCZOS)
    img.paste(barcode_img, (940, 580), barcode_img)
    _draw_text_shadow(draw, "IBEKS USERBOT OFFICIAL ID", (985, 660), font_small, COLORS["gray"])

    qr_img = _generate_qr(user.id)
    qr_img = qr_img.resize((95, 95), Image.Resampling.LANCZOS)
    qr_border = Image.new("RGBA", (105, 105), (*COLORS["white"], 255))
    qr_border.paste(qr_img, (5, 5))
    img.paste(qr_border, (1160, 560), qr_border)

    # Logo bottom center-left
    _draw_logo(draw, 420, 630)

    # Convert to RGB dan save
    final = img.convert("RGB")
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer


def generate_id_card(client: Client, user: User) -> io.BytesIO:
    """Wrapper backward-compatible untuk plugin .id"""
    return generate_user_card(client, user, card_type="id")
