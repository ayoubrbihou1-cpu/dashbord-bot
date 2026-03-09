"""
🎨 محرك التصميم التوليدي (Generative Design Engine)
باستخدام Pillow — يصمم بطاقات الطاولات برمجياً بثلاثة أطوار بصرية
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import qrcode
import qrcode.image.pil
import math
import io
import os
import colorsys
import textwrap
from dataclasses import dataclass
from typing import Tuple, Optional

# ─────────────────────────────────────────────────────────────────
# 📐 CONSTANTS
# ─────────────────────────────────────────────────────────────────

# A5 at 150 DPI — optimal for table tents
CARD_W, CARD_H = 1240, 874   # landscape A5 @ 150dpi
MARGIN = 60

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

# ─────────────────────────────────────────────────────────────────
# 🔧 UTILS
# ─────────────────────────────────────────────────────────────────

@dataclass
class Theme:
    name: str
    bg:        Tuple[int,int,int]
    fg:        Tuple[int,int,int]
    accent:    Tuple[int,int,int]
    accent2:   Tuple[int,int,int]
    font_display: str
    font_body:    str
    style: str  # modern | luxury | classic


THEMES = {
    "modern": Theme(
        name="Modern",
        bg=(18, 18, 18),
        fg=(255, 255, 255),
        accent=(0, 220, 180),
        accent2=(0, 150, 130),
        font_display="bold",
        font_body="regular",
        style="modern"
    ),
    "luxury": Theme(
        name="Luxury",
        bg=(10, 8, 4),
        fg=(250, 240, 210),
        accent=(201, 168, 76),
        accent2=(140, 100, 30),
        font_display="bold",
        font_body="regular",
        style="luxury"
    ),
    "classic": Theme(
        name="Classic",
        bg=(252, 248, 238),
        fg=(40, 25, 10),
        accent=(139, 69, 19),
        accent2=(180, 100, 40),
        font_display="bold",
        font_body="regular",
        style="classic"
    ),
}


def hex_to_rgb(hex_color: str) -> Tuple[int,int,int]:
    hex_color = hex_color.strip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0,2,4))


def luminance(rgb: Tuple[int,int,int]) -> float:
    r,g,b = [c/255 for c in rgb]
    r = r/12.92 if r<=0.03928 else ((r+0.055)/1.055)**2.4
    g = g/12.92 if g<=0.03928 else ((g+0.055)/1.055)**2.4
    b = b/12.92 if b<=0.03928 else ((b+0.055)/1.055)**2.4
    return 0.2126*r + 0.7152*g + 0.0722*b


def contrast_ratio(c1, c2) -> float:
    l1, l2 = luminance(c1)+0.05, luminance(c2)+0.05
    return max(l1,l2)/min(l1,l2)


def auto_fg(bg: Tuple[int,int,int]) -> Tuple[int,int,int]:
    """اختار اللون الأبيض أو الأسود بناءً على التباين"""
    return (255,255,255) if contrast_ratio(bg,(255,255,255)) > contrast_ratio(bg,(0,0,0)) else (0,0,0)


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """حاول تحميل خط، إذا فشل ارجع للخط الافتراضي"""
    font_paths = []
    if bold:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


def auto_font_size(text: str, max_w: int, max_h: int, bold: bool=True, min_size=20, max_size=120) -> Tuple[ImageFont.FreeTypeFont, int]:
    """حساب حجم الخط تلقائياً ليناسب المساحة المتاحة"""
    for size in range(max_size, min_size-1, -2):
        font = get_font(size, bold)
        # تقدير عرض النص
        test_img = Image.new("RGB", (1,1))
        draw = ImageDraw.Draw(test_img)
        try:
            bbox = draw.textbbox((0,0), text, font=font)
            w = bbox[2]-bbox[0]
            h = bbox[3]-bbox[1]
        except:
            w = len(text)*size*0.6
            h = size
        if w <= max_w and h <= max_h:
            return font, size
    return get_font(min_size, bold), min_size


def draw_text_centered(draw, text, cx, cy, font, color, shadow=None):
    """رسم نص في المنتصف مع ظل اختياري"""
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        w = bbox[2]-bbox[0]
        h = bbox[3]-bbox[1]
    except:
        w = len(text)*20
        h = 30
    x = cx - w//2
    y = cy - h//2
    if shadow:
        draw.text((x+2, y+2), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=color)
    return h


def make_qr(data: str, fg=(0,0,0), bg=(255,255,255), size=200) -> Image.Image:
    """توليد QR Code بألوان مخصصة"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10, border=2
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg, back_color=bg)
    img = img.convert("RGB")
    return img.resize((size, size), Image.LANCZOS)


def round_rectangle(draw, xy, radius, fill, outline=None, width=2):
    """رسم مستطيل بزوايا مدورة"""
    x1,y1,x2,y2 = xy
    draw.rectangle([x1+radius, y1, x2-radius, y2], fill=fill)
    draw.rectangle([x1, y1+radius, x2, y2-radius], fill=fill)
    draw.ellipse([x1, y1, x1+2*radius, y1+2*radius], fill=fill)
    draw.ellipse([x2-2*radius, y1, x2, y1+2*radius], fill=fill)
    draw.ellipse([x1, y2-2*radius, x1+2*radius, y2], fill=fill)
    draw.ellipse([x2-2*radius, y2-2*radius, x2, y2], fill=fill)
    if outline:
        draw.arc([x1, y1, x1+2*radius, y1+2*radius], 180, 270, fill=outline, width=width)
        draw.arc([x2-2*radius, y1, x2, y1+2*radius], 270, 360, fill=outline, width=width)
        draw.arc([x1, y2-2*radius, x1+2*radius, y2], 90, 180, fill=outline, width=width)
        draw.arc([x2-2*radius, y2-2*radius, x2, y2], 0, 90, fill=outline, width=width)
        draw.line([x1+radius, y1, x2-radius, y1], fill=outline, width=width)
        draw.line([x1+radius, y2, x2-radius, y2], fill=outline, width=width)
        draw.line([x1, y1+radius, x1, y2-radius], fill=outline, width=width)
        draw.line([x2, y1+radius, x2, y2-radius], fill=outline, width=width)


# ─────────────────────────────────────────────────────────────────
# 🎨 STYLE ENGINES
# ─────────────────────────────────────────────────────────────────

def render_modern_wifi(name, ssid, password, table_num, primary_color, accent_color) -> Image.Image:
    """بطاقة WiFi — طابع عصري"""
    bg = primary_color
    fg = auto_fg(bg)
    acc = accent_color

    img = Image.new("RGB", (CARD_W, CARD_H), bg)
    draw = ImageDraw.Draw(img)

    # خط عمودي ملون كزخرفة
    bar_w = 12
    draw.rectangle([0, 0, bar_w, CARD_H], fill=acc)

    # مستطيل ضبابي في الخلفية
    for i in range(3):
        r = 150 + i*80
        x0 = CARD_W - r - 20
        y0 = -r//2
        opacity_factor = 0.04 - i*0.01
        overlay_color = tuple(
            int(c + (255-c)*opacity_factor) if fg == (0,0,0)
            else int(c*opacity_factor)
            for c in bg
        )
        draw.ellipse([x0, y0, x0+r*2, y0+r*2], fill=overlay_color)

    # اسم المطعم
    name_font, name_size = auto_font_size(name, CARD_W//2 - MARGIN*2, 120, bold=True, max_size=90)
    shadow_c = tuple(max(0, c-40) for c in fg) if fg==(255,255,255) else tuple(min(255, c+40) for c in fg)
    draw_text_centered(draw, name, CARD_W//4 + bar_w//2, 180, name_font, fg, shadow=None)

    # خط فاصل
    sep_x = CARD_W//2
    draw.line([sep_x, MARGIN, sep_x, CARD_H-MARGIN], fill=acc, width=2)

    # WiFi icon (دوائر)
    cx, cy = CARD_W//4 + bar_w//2, CARD_H//2 + 20
    for r in [80, 55, 30]:
        draw.arc([cx-r, cy-r, cx+r, cy+r], 210, 330, fill=acc, width=4)
    draw.ellipse([cx-8, cy-8, cx+8, cy+8], fill=acc)

    # WiFi label
    wifi_font = get_font(28, bold=True)
    draw.text((cx - 60, cy + 95), "📶  WiFi", font=wifi_font, fill=acc)

    # كارطة المعلومات
    info_x = CARD_W//2 + MARGIN
    info_w = CARD_W//2 - MARGIN*2

    # SSID
    ssid_label_font = get_font(22)
    ssid_font, _ = auto_font_size(ssid, info_w, 60, bold=True, max_size=52, min_size=24)
    draw.text((info_x, 120), "SSID", font=ssid_label_font, fill=tuple(int(c*0.6) for c in fg) if fg==(255,255,255) else tuple(int(c+40) for c in fg))
    draw_text_centered(draw, ssid, info_x + info_w//2, 200, ssid_font, fg)

    # خط فاصل داخلي
    draw.line([info_x, 240, info_x + info_w, 240], fill=acc, width=1)

    # Password
    draw.text((info_x, 260), "Password", font=ssid_label_font, fill=tuple(int(c*0.6) for c in fg) if fg==(255,255,255) else tuple(int(c+40) for c in fg))
    pass_font, _ = auto_font_size(password, info_w, 60, bold=True, max_size=52, min_size=20)
    draw_text_centered(draw, password, info_x + info_w//2, 340, pass_font, acc)

    # Table number badge
    badge_x, badge_y = info_x + info_w - 100, CARD_H - 120
    round_rectangle(draw, [badge_x, badge_y, badge_x+180, badge_y+70], 12, acc)
    tbl_font = get_font(26, bold=True)
    tbl_fg = auto_fg(acc)
    draw.text((badge_x + 12, badge_y + 18), f"Table {table_num}", font=tbl_font, fill=tbl_fg)

    # Footer
    footer_font = get_font(20)
    footer_c = tuple(int(c*0.5) for c in fg) if fg==(255,255,255) else tuple(min(255, c+80) for c in fg)
    draw.text((bar_w + MARGIN, CARD_H - 50), "Connectez-vous et commandez", font=footer_font, fill=footer_c)

    return img


def render_luxury_wifi(name, ssid, password, table_num, primary_color, accent_color) -> Image.Image:
    """بطاقة WiFi — طابع فاخر"""
    GOLD = accent_color
    DARK = primary_color
    CREAM = auto_fg(DARK)

    img = Image.new("RGB", (CARD_W, CARD_H), DARK)
    draw = ImageDraw.Draw(img)

    # إطار ذهبي
    frame_m = 20
    draw.rectangle([frame_m, frame_m, CARD_W-frame_m, CARD_H-frame_m], outline=GOLD, width=2)
    inner_m = 32
    draw.rectangle([inner_m, inner_m, CARD_W-inner_m, CARD_H-inner_m], outline=GOLD, width=1)

    # زخارف زوايا
    corner_size = 40
    for cx, cy in [(inner_m, inner_m), (CARD_W-inner_m, inner_m),
                   (inner_m, CARD_H-inner_m), (CARD_W-inner_m, CARD_H-inner_m)]:
        draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill=GOLD)

    # اسم المطعم
    name_font, _ = auto_font_size(name, CARD_W//2 - 100, 100, bold=True, max_size=80)
    draw_text_centered(draw, name, CARD_W//4, 150, name_font, GOLD)

    # خط ذهبي تحت الاسم
    center_x = CARD_W//4
    line_len = min(300, CARD_W//3)
    draw.line([center_x-line_len//2, 210, center_x+line_len//2, 210], fill=GOLD, width=1)
    draw.text((center_x - 12, 198), "✦", font=get_font(20), fill=GOLD)

    # WiFi دوائر
    qcx, qcy = CARD_W//4, CARD_H//2 + 10
    for r, w in [(90, 2), (60, 2), (32, 3)]:
        draw.arc([qcx-r, qcy-r, qcx+r, qcy+r], 210, 330, fill=GOLD, width=w)
    draw.ellipse([qcx-7, qcy-7, qcx+7, qcy+7], fill=GOLD)

    # فاصل عمودي
    mid = CARD_W//2
    for y in range(inner_m+10, CARD_H-inner_m-10, 15):
        draw.line([mid, y, mid, y+8], fill=GOLD, width=1)

    # معلومات الاتصال
    info_x = mid + 60
    info_w = CARD_W - mid - inner_m - 60
    label_font = get_font(22)
    label_color = tuple(int(c*0.6) for c in CREAM)

    draw.text((info_x, 100), "RÉSEAU", font=label_font, fill=label_color)
    ssid_font, _ = auto_font_size(ssid, info_w, 70, bold=True, max_size=55, min_size=22)
    draw_text_centered(draw, ssid, info_x + info_w//2, 175, ssid_font, CREAM)

    draw.line([info_x, 215, info_x+info_w, 215], fill=GOLD, width=1)

    draw.text((info_x, 235), "MOT DE PASSE", font=label_font, fill=label_color)
    pass_font, _ = auto_font_size(password, info_w, 70, bold=True, max_size=55, min_size=22)
    draw_text_centered(draw, password, info_x + info_w//2, 315, pass_font, GOLD)

    draw.line([info_x, 360, info_x+info_w, 360], fill=GOLD, width=1)

    draw.text((info_x, 380), "TABLE", font=label_font, fill=label_color)
    tbl_font = get_font(60, bold=True)
    draw_text_centered(draw, str(table_num), info_x + info_w//2, 460, tbl_font, CREAM)

    # Footer
    footer_font = get_font(18)
    draw_text_centered(draw, "✦  Bienvenue  ✦", CARD_W//2, CARD_H - 55, footer_font, GOLD)

    return img


def render_classic_wifi(name, ssid, password, table_num, primary_color, accent_color) -> Image.Image:
    """بطاقة WiFi — طابع كلاسيكي"""
    CREAM = primary_color
    BROWN = accent_color
    TEXT  = auto_fg(CREAM)

    img = Image.new("RGB", (CARD_W, CARD_H), CREAM)
    draw = ImageDraw.Draw(img)

    # حدود مزدوجة
    m1, m2 = 15, 28
    draw.rectangle([m1, m1, CARD_W-m1, CARD_H-m1], outline=BROWN, width=3)
    draw.rectangle([m2, m2, CARD_W-m2, CARD_H-m2], outline=BROWN, width=1)

    # زخارف زوايا كلاسيكية
    for ox, oy in [(m2,m2), (CARD_W-m2,m2), (m2,CARD_H-m2), (CARD_W-m2,CARD_H-m2)]:
        draw.ellipse([ox-8, oy-8, ox+8, oy+8], fill=BROWN)
        draw.ellipse([ox-4, oy-4, ox+4, oy+4], fill=CREAM)

    # زخرفة علوية مركزية
    top_y = 50
    draw_text_centered(draw, "❦", CARD_W//2, top_y, get_font(36), BROWN)

    # اسم المطعم
    name_font, _ = auto_font_size(name, CARD_W - 150, 90, bold=True, max_size=75)
    draw_text_centered(draw, name, CARD_W//2, 130, name_font, BROWN)

    # خط فاصل أنيق
    sep_y = 190
    draw.line([80, sep_y, CARD_W-80, sep_y], fill=BROWN, width=2)
    draw_text_centered(draw, "✦", CARD_W//2, sep_y, get_font(16), BROWN)

    # كولونتين لـ WiFi والمعلومات
    left_cx = CARD_W // 4
    right_cx = 3 * CARD_W // 4

    # WiFi دوائر
    wcy = CARD_H // 2 + 30
    for r, w in [(75, 3), (50, 3), (27, 3)]:
        draw.arc([left_cx-r, wcy-r, left_cx+r, wcy+r], 210, 330, fill=BROWN, width=w)
    draw.ellipse([left_cx-7, wcy-7, left_cx+7, wcy+7], fill=BROWN)
    wifi_label = get_font(22, bold=True)
    draw_text_centered(draw, "WiFi", left_cx, wcy+90, wifi_label, BROWN)

    # فاصل عمودي نقطي
    vx = CARD_W // 2
    for y in range(200, CARD_H-50, 12):
        draw.ellipse([vx-2, y-2, vx+2, y+2], fill=BROWN)

    # معلومات
    label_font = get_font(22)
    value_font_ssid, _ = auto_font_size(ssid, CARD_W//2-80, 60, bold=True, max_size=48, min_size=20)
    value_font_pass, _ = auto_font_size(password, CARD_W//2-80, 60, bold=True, max_size=48, min_size=20)
    info_w = CARD_W//2 - 60

    draw.text((right_cx - info_w//2, 220), "Réseau WiFi", font=label_font, fill=BROWN)
    draw_text_centered(draw, ssid, right_cx, 290, value_font_ssid, TEXT)
    draw.line([right_cx-150, 330, right_cx+150, 330], fill=BROWN, width=1)

    draw.text((right_cx - info_w//2, 350), "Mot de passe", font=label_font, fill=BROWN)
    draw_text_centered(draw, password, right_cx, 420, value_font_pass, BROWN)

    # رقم الطاولة
    tbl_y = CARD_H - 110
    draw.line([right_cx-120, tbl_y-15, right_cx+120, tbl_y-15], fill=BROWN, width=1)
    tbl_font = get_font(42, bold=True)
    draw_text_centered(draw, f"Table {table_num}", right_cx, tbl_y + 25, tbl_font, BROWN)

    # footer
    footer_font = get_font(18)
    draw_text_centered(draw, "Bon appétit  ❦", CARD_W//2, CARD_H - 42, footer_font, BROWN)

    return img


# ─────────────────────────────────────────────────────────────────
# 📱 QR MENU CARDS (Side B)
# ─────────────────────────────────────────────────────────────────

def render_menu_qr_card(name, menu_url, table_num, style, primary_color, accent_color) -> Image.Image:
    """الوجه الثاني — QR للمينيو"""
    if style == "modern":
        return _menu_qr_modern(name, menu_url, table_num, primary_color, accent_color)
    elif style == "luxury":
        return _menu_qr_luxury(name, menu_url, table_num, primary_color, accent_color)
    else:
        return _menu_qr_classic(name, menu_url, table_num, primary_color, accent_color)


def _menu_qr_modern(name, url, table_num, primary, accent):
    bg = primary; fg = auto_fg(bg); acc = accent
    img = Image.new("RGB", (CARD_W, CARD_H), bg)
    draw = ImageDraw.Draw(img)

    # خط جانبي
    draw.rectangle([CARD_W-12, 0, CARD_W, CARD_H], fill=acc)

    # QR بألوان مخصصة
    qr_size = 340
    qr_bg = fg; qr_fg = bg
    qr_img = make_qr(url, fg=qr_fg, bg=qr_bg, size=qr_size)
    # إضافة padding للـ QR
    padded = Image.new("RGB", (qr_size+16, qr_size+16), fg)
    padded.paste(qr_img, (8,8))
    round_qr = padded
    qr_x = CARD_W//2 - qr_size//2 - 8
    qr_y = CARD_H//2 - qr_size//2 - 8
    img.paste(padded, (qr_x, qr_y))

    # اسم فوق
    name_font, _ = auto_font_size(name, CARD_W - 160, 80, bold=True, max_size=68)
    shadow = tuple(max(0,c-50) for c in fg)
    draw_text_centered(draw, name, CARD_W//2, 85, name_font, fg)

    # خط أسفل الاسم
    draw.line([CARD_W//2-120, 130, CARD_W//2+120, 130], fill=acc, width=2)

    # نص الدعوة
    cta_font = get_font(26, bold=True)
    cta_y = qr_y + qr_size + 24
    draw_text_centered(draw, "↑ Scannez pour commander ↑", CARD_W//2, cta_y + 16, cta_font, acc)

    # Table badge
    badge_w, badge_h = 160, 52
    bx = MARGIN; by = CARD_H - MARGIN - badge_h
    round_rectangle(draw, [bx, by, bx+badge_w, by+badge_h], 10, acc)
    tbl_font = get_font(24, bold=True)
    tbl_fg = auto_fg(acc)
    draw.text((bx+12, by+12), f"Table {table_num}", font=tbl_font, fill=tbl_fg)

    return img


def _menu_qr_luxury(name, url, table_num, primary, accent):
    GOLD = accent; DARK = primary; CREAM = auto_fg(DARK)
    img = Image.new("RGB", (CARD_W, CARD_H), DARK)
    draw = ImageDraw.Draw(img)

    # إطارات
    for m, w in [(15,2), (27,1)]:
        draw.rectangle([m, m, CARD_W-m, CARD_H-m], outline=GOLD, width=w)

    # زخرفة علوية
    draw_text_centered(draw, "✦", CARD_W//2, 50, get_font(30), GOLD)

    # الاسم
    name_font, _ = auto_font_size(name, CARD_W - 140, 80, bold=True, max_size=72)
    draw_text_centered(draw, name, CARD_W//2, 120, name_font, GOLD)

    # خط ذهبي
    draw.line([CARD_W//2-200, 165, CARD_W//2+200, 165], fill=GOLD, width=1)

    # QR مع إطار ذهبي
    qr_size = 300
    qr_img = make_qr(url, fg=DARK, bg=CREAM, size=qr_size)
    border = 14
    framed = Image.new("RGB", (qr_size+border*2, qr_size+border*2), GOLD)
    framed.paste(qr_img, (border, border))
    qx = CARD_W//2 - (qr_size+border*2)//2
    qy = CARD_H//2 - (qr_size+border*2)//2 + 10
    img.paste(framed, (qx, qy))

    # CTA
    cta_y = qy + qr_size + border*2 + 20
    draw_text_centered(draw, "✦  Scannez pour commander  ✦", CARD_W//2, cta_y + 14, get_font(22), GOLD)

    # رقم طاولة
    tbl_font = get_font(26, bold=True)
    draw_text_centered(draw, f"Table  {table_num}", CARD_W//2, CARD_H - 48, tbl_font, CREAM)

    return img


def _menu_qr_classic(name, url, table_num, primary, accent):
    CREAM = primary; BROWN = accent; TEXT = auto_fg(CREAM)
    img = Image.new("RGB", (CARD_W, CARD_H), CREAM)
    draw = ImageDraw.Draw(img)

    for m, w in [(15,3), (27,1)]:
        draw.rectangle([m, m, CARD_W-m, CARD_H-m], outline=BROWN, width=w)

    draw_text_centered(draw, "❦", CARD_W//2, 50, get_font(36), BROWN)

    name_font, _ = auto_font_size(name, CARD_W-140, 80, bold=True, max_size=72)
    draw_text_centered(draw, name, CARD_W//2, 120, name_font, BROWN)
    draw.line([CARD_W//2-180, 165, CARD_W//2+180, 165], fill=BROWN, width=2)

    qr_size = 300
    qr_img = make_qr(url, fg=BROWN, bg=CREAM, size=qr_size)
    border = 12
    framed = Image.new("RGB", (qr_size+border*2, qr_size+border*2), BROWN)
    framed.paste(qr_img, (border, border))
    qx = CARD_W//2 - (qr_size+border*2)//2
    qy = CARD_H//2 - (qr_size+border*2)//2 + 10
    img.paste(framed, (qx, qy))

    cta_y = qy + qr_size + border*2 + 18
    draw_text_centered(draw, "❦  Scannez pour voir le menu  ❦", CARD_W//2, cta_y+14, get_font(22), BROWN)

    tbl_font = get_font(26, bold=True)
    draw_text_centered(draw, f"Table  {table_num}", CARD_W//2, CARD_H-48, tbl_font, BROWN)

    return img


# ─────────────────────────────────────────────────────────────────
# 🏭 PUBLIC FACTORY FUNCTION
# ─────────────────────────────────────────────────────────────────

def generate_table_card(
    restaurant_name: str,
    ssid: str,
    wifi_password: str,
    table_number: int,
    menu_url: str,
    style: str = "luxury",
    primary_color_hex: str = "#0a0804",
    accent_color_hex: str = "#C9A84C"
) -> Tuple[Image.Image, Image.Image]:
    """
    🎨 الدالة الرئيسية — تنتج وجهين لبطاقة الطاولة

    Returns:
        (wifi_card, menu_qr_card) — صورتان بحجم A5
    """
    primary = hex_to_rgb(primary_color_hex)
    accent  = hex_to_rgb(accent_color_hex)
    style   = style.lower()

    # ── Wifi Card (Side A)
    if style == "modern":
        wifi_card = render_modern_wifi(restaurant_name, ssid, wifi_password, table_number, primary, accent)
    elif style == "luxury":
        wifi_card = render_luxury_wifi(restaurant_name, ssid, wifi_password, table_number, primary, accent)
    else:
        wifi_card = render_classic_wifi(restaurant_name, ssid, wifi_password, table_number, primary, accent)

    # ── Menu QR Card (Side B)
    menu_card = render_menu_qr_card(restaurant_name, menu_url, table_number, style, primary, accent)

    return wifi_card, menu_card


def card_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150,150))
    return buf.getvalue()
