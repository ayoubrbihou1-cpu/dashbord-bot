"""
🎨 محرك التصميم التوليدي v2 — 6 أطوار بصرية + خلفيات طعام + أيقونات سوشيال
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
import math, io, os
import colorsys
from dataclasses import dataclass
from typing import Tuple, Optional, List

# ─────────────────────────────────────────────────────────────────
# 📐 CONSTANTS
# ─────────────────────────────────────────────────────────────────
CARD_W, CARD_H = 1240, 874   # A5 landscape @ 150dpi
MARGIN = 55

# ─────────────────────────────────────────────────────────────────
# 🔧 UTILS
# ─────────────────────────────────────────────────────────────────

def hex_to_rgb(h: str) -> Tuple[int,int,int]:
    h = h.strip("#")
    return tuple(int(h[i:i+2], 16) for i in (0,2,4))

def luminance(rgb):
    r,g,b = [c/255 for c in rgb]
    r = r/12.92 if r<=0.03928 else ((r+0.055)/1.055)**2.4
    g = g/12.92 if g<=0.03928 else ((g+0.055)/1.055)**2.4
    b = b/12.92 if b<=0.03928 else ((b+0.055)/1.055)**2.4
    return 0.2126*r + 0.7152*g + 0.0722*b

def auto_fg(bg):
    return (255,255,255) if luminance(bg)+0.05 > 0.179 and luminance(bg) < 0.4 else (
        (255,255,255) if luminance(bg) < 0.4 else (20,20,20)
    )

def blend(c1, c2, t):
    return tuple(int(c1[i]*(1-t)+c2[i]*t) for i in range(3))

def darken(c, f=0.6):
    return tuple(int(x*f) for x in c)

def lighten(c, f=1.4):
    return tuple(min(255, int(x*f)) for x in c)

def alpha_composite_manual(base_img, overlay_color, alpha):
    """Add semi-transparent overlay"""
    overlay = Image.new("RGB", base_img.size, overlay_color)
    return Image.blend(base_img, overlay, alpha)

def get_font(size: int, bold=False) -> ImageFont.FreeTypeFont:
    paths = []
    if bold:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
    else:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: continue
    return ImageFont.load_default()

def auto_font_size(text, max_w, max_h, bold=True, min_s=18, max_s=110):
    for s in range(max_s, min_s-1, -2):
        f = get_font(s, bold)
        tmp = Image.new("RGB",(1,1)); d = ImageDraw.Draw(tmp)
        try:
            bb = d.textbbox((0,0), text, font=f)
            w,h = bb[2]-bb[0], bb[3]-bb[1]
        except:
            w,h = len(text)*s*0.6, s
        if w <= max_w and h <= max_h:
            return f, s
    return get_font(min_s, bold), min_s

def text_wh(draw, text, font):
    try:
        bb = draw.textbbox((0,0), text, font=font)
        return bb[2]-bb[0], bb[3]-bb[1]
    except:
        return len(text)*20, 30

def draw_center(draw, text, cx, cy, font, color, shadow_c=None, shadow_off=3):
    w,h = text_wh(draw, text, font)
    x,y = cx-w//2, cy-h//2
    if shadow_c:
        draw.text((x+shadow_off, y+shadow_off), text, font=font, fill=shadow_c)
    draw.text((x, y), text, font=font, fill=color)
    return h

def make_qr(data: str, fg=(0,0,0), bg=(255,255,255), size=260) -> Image.Image:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg, back_color=bg).convert("RGB")
    return img.resize((size, size), Image.LANCZOS)

def rounded_rect(draw, xy, r, fill, outline=None, width=2):
    x1,y1,x2,y2 = xy
    draw.rectangle([x1+r,y1,x2-r,y2], fill=fill)
    draw.rectangle([x1,y1+r,x2,y2-r], fill=fill)
    for cx,cy in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([cx,cy,cx+2*r,cy+2*r], fill=fill)
    if outline:
        for m,c in [(0,outline)]:
            draw.arc([x1,y1,x1+2*r,y1+2*r],180,270,fill=c,width=width)
            draw.arc([x2-2*r,y1,x2,y1+2*r],270,360,fill=c,width=width)
            draw.arc([x1,y2-2*r,x1+2*r,y2],90,180,fill=c,width=width)
            draw.arc([x2-2*r,y2-2*r,x2,y2],0,90,fill=c,width=width)
            draw.line([x1+r,y1,x2-r,y1],fill=c,width=width)
            draw.line([x1+r,y2,x2-r,y2],fill=c,width=width)
            draw.line([x1,y1+r,x1,y2-r],fill=c,width=width)
            draw.line([x2,y1+r,x2,y2-r],fill=c,width=width)

# ─────────────────────────────────────────────────────────────────
# 🍽️ FOOD BACKGROUND GENERATORS
# ─────────────────────────────────────────────────────────────────

def draw_tajine_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """خلفية طاجين مغربي — أواني فخارية وزخارف"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    a = accent

    def tajine(cx, cy, s, alpha_=0.18):
        # قاعدة الطاجين (دائرية)
        base_r = s
        col = blend(a, (0,0,0), 1-alpha_)
        draw.ellipse([cx-base_r, cy+s//2, cx+base_r, cy+s//2+s//3], fill=col)
        # جسم الطاجين
        draw.polygon([
            (cx-base_r, cy+s//2+s//6),
            (cx+base_r, cy+s//2+s//6),
            (cx+base_r//2, cy-s//4),
            (cx-base_r//2, cy-s//4),
        ], fill=col)
        # غطاء مخروطي
        draw.polygon([
            (cx-base_r//2, cy-s//4),
            (cx+base_r//2, cy-s//4),
            (cx, cy-s),
        ], fill=blend(a, (255,255,255), 0.1 if alpha_ < 0.15 else 0))
        # رأس المخروط
        draw.ellipse([cx-8, cy-s-8, cx+8, cy-s+8], fill=a)

    # طاجين كبير — خلفية
    tajine(150, h//2+80, 120, 0.12)
    tajine(CARD_W-160, h//2+80, 110, 0.10)
    tajine(CARD_W//2, h-100, 90, 0.08)
    # صغيرة مبعثرة
    tajine(80, 100, 55, 0.07)
    tajine(CARD_W-90, 110, 50, 0.07)
    tajine(CARD_W//2-180, 80, 45, 0.05)

    return img

def draw_sandwich_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """خلفية ساندويش وبرغر"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    a = accent

    def bun(cx, cy, s, alpha_=0.15):
        col = blend(a, (180, 100, 30), 0.4)
        col2 = blend(col, (0,0,0), 1-alpha_)
        # خبزة عليا (نصف دائرة)
        draw.pieslice([cx-s, cy-s//2, cx+s, cy+s//2], 180, 360, fill=col2)
        # حشوة (خط ملون)
        fill_col = blend(a, (100, 180, 50), 0.5)
        fill_col2 = blend(fill_col, (0,0,0), 1-alpha_)
        draw.rectangle([cx-s, cy, cx+s, cy+s//5], fill=fill_col2)
        # خبزة سفلى
        draw.ellipse([cx-s, cy+s//6, cx+s, cy+s//2+s//3], fill=col2)

    bun(160, h//2, 130, 0.14)
    bun(CARD_W-170, h//2+20, 120, 0.12)
    bun(CARD_W//2, h-80, 100, 0.10)
    bun(90, 130, 60, 0.08)
    bun(CARD_W-100, 90, 55, 0.08)

    return img

def draw_couscous_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """خلفية كسكس — صحون مغربية وزخارف هندسية"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    a = accent

    def plate(cx, cy, r, alpha_=0.15):
        col = blend(a, (220,200,150), 0.3)
        col = blend(col, (0,0,0), 1-alpha_)
        # طبق
        draw.ellipse([cx-r, cy-r//4, cx+r, cy+r//4], fill=col)
        # حافة
        inner = blend(a, (255,255,255), 0.05)
        draw.ellipse([cx-r+12, cy-r//4+6, cx+r-12, cy+r//4-6], fill=inner)
        # كسكس (نقاط صغيرة)
        for i in range(8):
            px = cx + int((r//2)*math.cos(i*math.pi/4))
            py = cy + int((r//8)*math.sin(i*math.pi/4))
            draw.ellipse([px-5,py-5,px+5,py+5], fill=col)

    plate(150, h//2+50, 130, 0.14)
    plate(CARD_W-160, h//2+40, 120, 0.12)
    plate(CARD_W//2, h-60, 100, 0.10)
    plate(90, 110, 65, 0.08)

    # زخارف هندسية مغربية (نجوم)
    def star(cx, cy, r, pts=8, alpha_=0.08):
        col = blend(a, (255,255,255), alpha_)
        angle_step = math.pi / pts
        coords = []
        for i in range(pts*2):
            rad = r if i%2==0 else r//2
            angle = i * angle_step - math.pi/2
            coords.append((cx + int(rad*math.cos(angle)), cy + int(rad*math.sin(angle))))
        draw.polygon(coords, fill=col)

    star(CARD_W//4, CARD_H//4, 60, 8, 0.07)
    star(3*CARD_W//4, CARD_H//4, 50, 8, 0.06)
    star(CARD_W//2, CARD_H//2, 40, 8, 0.05)

    return img

def draw_arabic_pattern_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """خلفية زخارف عربية هندسية"""
    draw = ImageDraw.Draw(img)
    a = accent

    def hexagon(cx, cy, r, alpha_=0.1):
        col = blend(a, (255,255,255), alpha_)
        pts = [(cx+int(r*math.cos(math.pi/3*i-math.pi/6)),
                cy+int(r*math.sin(math.pi/3*i-math.pi/6))) for i in range(6)]
        draw.polygon(pts, outline=col, fill=None)
        # داخل صغير
        r2 = r*0.5
        pts2 = [(cx+int(r2*math.cos(math.pi/3*i-math.pi/6+math.pi/6)),
                 cy+int(r2*math.sin(math.pi/3*i-math.pi/6+math.pi/6))) for i in range(6)]
        draw.polygon(pts2, fill=blend(a,(0,0,0),0.85))

    # شبكة سداسية
    step_x, step_y = 140, 120
    for row in range(-1, CARD_H//step_y+2):
        for col in range(-1, CARD_W//step_x+2):
            cx = col*step_x + (70 if row%2 else 0)
            cy = row*step_y
            hexagon(cx, cy, 55, 0.09)

    return img

def draw_moroccan_tiles_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """خلفية بلاط مغربي — zellige"""
    draw = ImageDraw.Draw(img)
    a = accent

    tile_s = 80
    for row in range(CARD_H//tile_s + 2):
        for col in range(CARD_W//tile_s + 2):
            x = col * tile_s
            y = row * tile_s
            # مربع خارجي
            draw.rectangle([x+2, y+2, x+tile_s-2, y+tile_s-2],
                          outline=blend(a,(0,0,0),0.82), width=1)
            # نجمة داخلية
            cx, cy = x+tile_s//2, y+tile_s//2
            r_out, r_in = 28, 14
            pts = []
            for i in range(8):
                r = r_out if i%2==0 else r_in
                ang = i*math.pi/4 - math.pi/8
                pts.append((cx+int(r*math.cos(ang)), cy+int(r*math.sin(ang))))
            draw.polygon(pts, fill=blend(a,(0,0,0),0.80))

    return img

def draw_minimal_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """خلفية بسيطة بخطوط أنيقة"""
    draw = ImageDraw.Draw(img)
    a = accent
    w, h = img.size

    # خطوط قطرية خفيفة
    col = blend(a, (0,0,0), 0.88)
    step = 90
    for i in range(-h, w+h, step):
        draw.line([(i, 0), (i+h, h)], fill=col, width=1)

    return img


# اختيار الخلفية حسب الطابع
BG_FUNCS = {
    "tajine":   draw_tajine_bg,
    "sandwich": draw_sandwich_bg,
    "couscous": draw_couscous_bg,
    "arabesque": draw_arabic_pattern_bg,
    "zellige":  draw_moroccan_tiles_bg,
    "minimal":  draw_minimal_bg,
}

BG_LABELS = {
    "tajine":    "🫕 طاجين مغربي",
    "sandwich":  "🥙 ساندويش وبرغر",
    "couscous":  "🍲 كسكس وأطباق",
    "arabesque": "🌟 زخارف عربية",
    "zellige":   "🔷 بلاط مغربي",
    "minimal":   "✨ بسيط وأنيق",
}

# ─────────────────────────────────────────────────────────────────
# 📱 SOCIAL MEDIA ICONS (text-based, no external images)
# ─────────────────────────────────────────────────────────────────

SOCIAL_CONFIG = {
    "instagram": {"label": "Instagram",  "icon": "📷", "color": (193, 53, 132)},
    "facebook":  {"label": "Facebook",   "icon": "👍", "color": (24, 119, 242)},
    "whatsapp":  {"label": "WhatsApp",   "icon": "💬", "color": (37, 211, 102)},
    "tiktok":    {"label": "TikTok",     "icon": "🎵", "color": (255, 0, 80)},
    "website":   {"label": "Website",    "icon": "🌐", "color": (100, 149, 237)},
    "phone":     {"label": "Téléphone",  "icon": "📞", "color": (100, 200, 100)},
    "snapchat":  {"label": "Snapchat",   "icon": "👻", "color": (255, 252, 0)},
    "youtube":   {"label": "YouTube",    "icon": "▶️", "color": (255, 0, 0)},
}

def draw_social_bar(draw: ImageDraw, img_w: int, y_start: int,
                    socials: dict, accent: Tuple, fg: Tuple,
                    bg_color: Tuple, card_height: int) -> int:
    """
    يرسم شريط مواقع التواصل أسفل البطاقة
    socials = {"instagram": "@my_resto", "whatsapp": "+212600000000", ...}
    يرجع: Y النهاية
    """
    if not socials:
        return y_start

    active = [(k, v) for k, v in socials.items() if v.strip() and k in SOCIAL_CONFIG]
    if not active:
        return y_start

    # خط فاصل
    sep_col = blend(accent, fg, 0.3)
    draw.line([MARGIN, y_start-10, img_w-MARGIN, y_start-10], fill=sep_col, width=1)

    icon_font  = get_font(22, bold=True)
    label_font = get_font(18)
    val_font   = get_font(20, bold=True)

    # حساب عرض كل عنصر
    item_w = (img_w - MARGIN*2) // max(len(active), 1)
    item_w = min(item_w, 220)
    total_w = len(active) * item_w
    x_start = (img_w - total_w) // 2

    for i, (key, val) in enumerate(active):
        cfg = SOCIAL_CONFIG[key]
        cx = x_start + i * item_w + item_w // 2
        cy = y_start + 30

        # دائرة خلفية للأيقونة
        r = 22
        icon_bg = blend(cfg["color"], bg_color, 0.7)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=icon_bg)

        # أيقونة
        iw, ih = text_wh(draw, cfg["icon"], icon_font)
        draw.text((cx-iw//2, cy-ih//2), cfg["icon"], font=icon_font, fill=(255,255,255))

        # قيمة (handle أو رقم)
        display = val[:18] + "…" if len(val) > 18 else val
        vw, vh = text_wh(draw, display, val_font)
        draw.text((cx-vw//2, cy+r+8), display, font=val_font, fill=accent)

    return y_start + 80


# ─────────────────────────────────────────────────────────────────
# 🎨 STYLE RENDERERS — 6 STYLES
# ─────────────────────────────────────────────────────────────────

def _render_card(
    style: str,
    name: str,
    qr_data: str,
    table_num: int,
    primary: Tuple,
    accent: Tuple,
    bg_type: str,
    socials: dict,
    card_type: str,   # "menu" | "wifi"
    ssid: str = "",
    wifi_pass: str = ""
) -> Image.Image:
    """المعالج الموحد لكل الأطوار"""

    img = Image.new("RGB", (CARD_W, CARD_H), primary)
    draw = ImageDraw.Draw(img)

    fg = auto_fg(primary)
    acc = accent

    # ── خلفية ───────────────────────────────────────────────────
    bg_fn = BG_FUNCS.get(bg_type, draw_minimal_bg)
    img = bg_fn(img, acc)
    draw = ImageDraw.Draw(img)

    # ── إطار حسب الطابع ─────────────────────────────────────────
    if style == "luxury":
        _frame_luxury(draw, acc, primary)
    elif style == "modern":
        _frame_modern(draw, acc, primary)
    elif style == "classic":
        _frame_classic(draw, acc, primary)
    elif style == "bold":
        _frame_bold(draw, acc, primary, fg)
    elif style == "neon":
        _frame_neon(draw, acc, primary)
    elif style == "rustic":
        _frame_rustic(draw, acc, primary)

    # ── QR ──────────────────────────────────────────────────────
    qr_size, qr_x, qr_y = _place_qr(
        img, draw, style, qr_data, primary, acc, fg, card_type
    )

    # ── نص ──────────────────────────────────────────────────────
    social_y = _draw_texts(
        draw, style, name, table_num, primary, acc, fg,
        qr_x, qr_y, qr_size, card_type, ssid, wifi_pass, socials
    )

    # ── سوشيال ─────────────────────────────────────────────────
    if socials:
        draw_social_bar(draw, CARD_W, social_y, socials, acc, fg, primary, CARD_H)

    return img


# ── إطارات ──────────────────────────────────────────────────────

def _frame_luxury(draw, acc, bg):
    for m, w in [(14,2),(26,1)]:
        draw.rectangle([m,m,CARD_W-m,CARD_H-m], outline=acc, width=w)
    for cx,cy in [(26,26),(CARD_W-26,26),(26,CARD_H-26),(CARD_W-26,CARD_H-26)]:
        draw.ellipse([cx-6,cy-6,cx+6,cy+6], fill=acc)
        draw.ellipse([cx-3,cy-3,cx+3,cy+3], fill=bg)

def _frame_modern(draw, acc, bg):
    # خط علوي ملون
    draw.rectangle([0,0,CARD_W,10], fill=acc)
    draw.rectangle([0,CARD_H-10,CARD_W,CARD_H], fill=acc)
    # خط جانبي
    draw.rectangle([0,0,8,CARD_H], fill=darken(acc, 0.8))

def _frame_classic(draw, acc, bg):
    for m, w in [(14,3),(26,1)]:
        draw.rectangle([m,m,CARD_W-m,CARD_H-m], outline=acc, width=w)
    # نقاط زوايا
    for cx,cy in [(14,14),(CARD_W-14,14),(14,CARD_H-14),(CARD_W-14,CARD_H-14)]:
        draw.ellipse([cx-8,cy-8,cx+8,cy+8], fill=acc)

def _frame_bold(draw, acc, bg, fg):
    # شريط علوي عريض
    draw.rectangle([0,0,CARD_W,90], fill=acc)
    # شريط سفلي
    draw.rectangle([0,CARD_H-60,CARD_W,CARD_H], fill=darken(acc,0.7))

def _frame_neon(draw, acc, bg):
    # إطار متوهج
    neon = lighten(acc, 1.5)
    for m, w, a in [(10,4,acc),(14,2,lighten(acc,1.3)),(18,1,acc)]:
        draw.rectangle([m,m,CARD_W-m,CARD_H-m], outline=a, width=w)

def _frame_rustic(draw, acc, bg):
    # إطار خشبي متقطع
    seg = 40
    for x in range(14, CARD_W-14, seg*2):
        draw.line([x,14,x+seg,14], fill=acc, width=3)
        draw.line([x,CARD_H-14,x+seg,CARD_H-14], fill=acc, width=3)
    for y in range(14, CARD_H-14, seg*2):
        draw.line([14,y,14,y+seg], fill=acc, width=3)
        draw.line([CARD_W-14,y,CARD_W-14,y+seg], fill=acc, width=3)
    # نجوم في الزوايا
    for cx,cy in [(28,28),(CARD_W-28,28),(28,CARD_H-28),(CARD_W-28,CARD_H-28)]:
        draw.text((cx-10,cy-12), "✦", font=get_font(24), fill=acc)


# ── وضع QR ──────────────────────────────────────────────────────

def _place_qr(img, draw, style, data, primary, acc, fg, card_type):
    """يضع QR في موقعه ويرجع (size, x, y)"""
    qr_size = 300

    if style in ("bold",):
        qr_x = CARD_W//2 - qr_size//2
        qr_y = CARD_H//2 - qr_size//2 + 30
    else:
        qr_x = CARD_W//2 - qr_size//2
        qr_y = CARD_H//2 - qr_size//2 + 15

    # ألوان QR حسب الطابع
    if style == "luxury":
        qr_img = make_qr(data, fg=primary, bg=acc, size=qr_size)
        border, border_col = 14, acc
    elif style == "neon":
        qr_img = make_qr(data, fg=primary, bg=lighten(acc,1.4), size=qr_size)
        border, border_col = 10, lighten(acc,1.4)
    elif style == "bold":
        qr_img = make_qr(data, fg=primary, bg=fg, size=qr_size)
        border, border_col = 12, fg
    elif style == "rustic":
        qr_img = make_qr(data, fg=darken(acc,0.6), bg=lighten(primary,1.3), size=qr_size)
        border, border_col = 12, acc
    else:  # modern, classic
        qr_img = make_qr(data, fg=primary, bg=acc, size=qr_size)
        border, border_col = 12, acc

    # إطار حول QR
    framed = Image.new("RGB", (qr_size+border*2, qr_size+border*2), border_col)
    framed.paste(qr_img, (border, border))
    img.paste(framed, (qr_x, qr_y))

    return qr_size, qr_x, qr_y


# ── النصوص ──────────────────────────────────────────────────────

def _draw_texts(draw, style, name, table_num, primary, acc, fg,
                qr_x, qr_y, qr_size, card_type, ssid, wifi_pass, socials):
    """يرسم كل النصوص ويرجع Y لشريط السوشيال"""

    has_social = bool(socials and any(v.strip() for v in socials.values()))
    social_reserve = 90 if has_social else 0
    bottom_y = CARD_H - 50 - social_reserve

    # ── اسم المطعم ──────────────────────────────────────────────
    if style == "bold":
        # الاسم في الشريط العلوي
        name_font, _ = auto_font_size(name, CARD_W-100, 65, bold=True, max_s=65)
        name_fg = auto_fg(acc)
        shadow_c = darken(name_fg, 0.7) if name_fg==(255,255,255) else lighten(name_fg,1.3)
        draw_center(draw, name, CARD_W//2, 48, name_font, name_fg, shadow_c)
    else:
        # الاسم أعلى QR
        name_font, _ = auto_font_size(name, CARD_W-120, 70, bold=True, max_s=72)
        shadow_c = darken(fg, 0.6) if fg==(255,255,255) else (200,200,200)
        draw_center(draw, name, CARD_W//2, qr_y - 55, name_font, fg, shadow_c)

    # ── خط زخرفي تحت الاسم ──────────────────────────────────────
    if style == "luxury":
        lx = CARD_W//2
        ll = 220
        draw.line([lx-ll//2, qr_y-22, lx+ll//2, qr_y-22], fill=acc, width=1)
        draw.text((lx-8, qr_y-34), "✦", font=get_font(18), fill=acc)
    elif style == "classic":
        lx = CARD_W//2; ll = 200
        draw.line([lx-ll//2, qr_y-20, lx+ll//2, qr_y-20], fill=acc, width=2)
    elif style in ("modern", "neon"):
        lx = CARD_W//2; ll = 180
        draw.line([lx-ll//2, qr_y-20, lx+ll//2, qr_y-20], fill=acc, width=3)

    # ── نص CTA تحت QR ───────────────────────────────────────────
    cta_y = qr_y + qr_size + 28 + 14  # 28 = border*2
    if card_type == "menu":
        cta_text = "↑ Scannez pour commander ↑" if style != "luxury" else "✦  Scannez pour voir le menu  ✦"
    else:
        cta_text = "↑ Scanner pour se connecter au WiFi ↑"

    cta_font = get_font(22, bold=(style in ("bold","neon")))
    cta_col = acc if style not in ("bold",) else auto_fg(primary)
    draw_center(draw, cta_text, CARD_W//2, cta_y, cta_font, cta_col)

    # ── رقم الطاولة ─────────────────────────────────────────────
    tbl_text = f"Table  {table_num}"
    tbl_y = cta_y + 50

    if style == "bold":
        # في الشريط السفلي
        tbl_font = get_font(30, bold=True)
        tbl_fg = auto_fg(darken(acc,0.7))
        draw_center(draw, tbl_text, CARD_W//2, CARD_H - 34, tbl_font, tbl_fg)
    elif style == "luxury":
        tbl_font = get_font(28, bold=True)
        draw_center(draw, tbl_text, CARD_W//2, min(tbl_y, bottom_y-10), tbl_font, fg)
    else:
        # Badge
        tbl_font = get_font(24, bold=True)
        tbl_fg_c = auto_fg(acc)
        tw, th = text_wh(draw, tbl_text, tbl_font)
        bx = CARD_W//2 - tw//2 - 20
        by = min(tbl_y - 10, bottom_y - 45)
        rounded_rect(draw, [bx, by, bx+tw+40, by+th+18], 12, acc)
        draw.text((bx+20, by+9), tbl_text, font=tbl_font, fill=tbl_fg_c)

    # ── معلومات WiFi (بطاقة WiFi فقط) ──────────────────────────
    if card_type == "wifi" and ssid:
        _draw_wifi_info(draw, ssid, wifi_pass, primary, acc, fg, style, qr_x, qr_y, qr_size, bottom_y)

    return bottom_y + 10


def _draw_wifi_info(draw, ssid, wifi_pass, primary, acc, fg, style, qr_x, qr_y, qr_size, bottom_y):
    """معلومات الشبكة — تُعرض بجانب/أسفل QR"""

    # نضعها على يسار أو يمين QR حسب المكان المتاح
    info_x = 40
    info_w  = qr_x - 80
    if info_w < 200:
        # نضعها أسفل
        info_x = MARGIN
        info_w  = CARD_W - MARGIN*2
        base_y  = qr_y + qr_size + 60
    else:
        base_y = qr_y + 40

    label_font = get_font(22)
    val_font   = get_font(32, bold=True)
    label_col  = blend(fg, primary, 0.35)

    # SSID
    draw.text((info_x, base_y), "RÉSEAU / SSID", font=label_font, fill=label_col)
    ssid_font, _ = auto_font_size(ssid, info_w, 50, bold=True, max_s=42, min_s=20)
    ssid_w, ssid_h = text_wh(draw, ssid, ssid_font)
    draw.text((info_x, base_y+28), ssid, font=ssid_font, fill=fg)

    # فاصل
    sep_y = base_y + 28 + ssid_h + 12
    draw.line([info_x, sep_y, info_x+info_w, sep_y], fill=acc, width=1)

    # Password
    draw.text((info_x, sep_y+10), "MOT DE PASSE", font=label_font, fill=label_col)
    pass_font, _ = auto_font_size(wifi_pass, info_w, 55, bold=True, max_s=46, min_s=20)
    draw.text((info_x, sep_y+36), wifi_pass, font=pass_font, fill=acc)


# ─────────────────────────────────────────────────────────────────
# 🏭 PUBLIC API
# ─────────────────────────────────────────────────────────────────

STYLE_LABELS = {
    "luxury":  "👑 فاخر ذهبي",
    "modern":  "🔷 عصري",
    "classic": "📜 كلاسيكي",
    "bold":    "⚡ جريء",
    "neon":    "🌈 نيون",
    "rustic":  "🌿 ريفي",
}

def generate_table_card(
    restaurant_name: str,
    ssid: str,
    wifi_password: str,
    table_number: int,
    menu_url: str,
    style: str = "luxury",
    primary_color_hex: str = "#0a0804",
    accent_color_hex:  str = "#C9A84C",
    bg_type: str = "minimal",
    socials: dict = None,
) -> tuple:
    """
    🎨 يولد بطاقتين: (menu_card, wifi_card)
    
    bg_type: tajine | sandwich | couscous | arabesque | zellige | minimal
    socials: {"instagram": "@handle", "whatsapp": "+212...", ...}
    """
    if socials is None:
        socials = {}

    primary = hex_to_rgb(primary_color_hex)
    accent  = hex_to_rgb(accent_color_hex)
    style   = style.lower()

    wifi_qr = f"WIFI:T:WPA;S:{ssid};P:{wifi_password};;"

    menu_card = _render_card(
        style=style, name=restaurant_name, qr_data=menu_url,
        table_num=table_number, primary=primary, accent=accent,
        bg_type=bg_type, socials=socials, card_type="menu"
    )

    wifi_card = _render_card(
        style=style, name=restaurant_name, qr_data=wifi_qr,
        table_num=table_number, primary=primary, accent=accent,
        bg_type=bg_type, socials=socials, card_type="wifi",
        ssid=ssid, wifi_pass=wifi_password
    )

    return menu_card, wifi_card


def card_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150,150))
    return buf.getvalue()
