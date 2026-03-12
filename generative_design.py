"""
🎨 محرك التصميم v3 — بطاقات QR احترافية
✅ إصلاحات:
  - نص عربي صحيح (arabic_reshaper + bidi)
  - أيقونات سوشيال كأشكال هندسية (لا emojis)
  - تصميم فاخر يشبه بطاقات المطاعم الحقيقية
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
import math, io, os, logging
import colorsys
from dataclasses import dataclass
from typing import Tuple, Optional, List

log = logging.getLogger("gen_design")

# ── جلب صور الطعام من APIs ──────────────────────────────────────
try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

def fetch_food_photo_bytes(
    query: str,
    pexels_key: str = "",
    unsplash_key: str = "",
    pixabay_key: str = "",
) -> Optional[bytes]:
    """
    يجلب صورة طعام من Pexels أو Unsplash أو Pixabay.
    يرجع bytes الصورة أو None.
    """
    if not _HAS_REQUESTS:
        return None

    # ── Pexels أولاً ─────────────────────────────────────
    if pexels_key:
        try:
            r = _requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": pexels_key},
                params={"query": query + " food", "per_page": 3,
                        "orientation": "landscape", "size": "medium"},
                timeout=10
            )
            if r.status_code == 200:
                photos = r.json().get("photos", [])
                if photos:
                    img_url = photos[0]["src"]["large"]
                    resp = _requests.get(img_url, timeout=15)
                    if resp.status_code == 200:
                        log.info(f"✅ Pexels photo: {query}")
                        return resp.content
        except Exception as e:
            log.warning(f"Pexels: {e}")

    # ── Unsplash ──────────────────────────────────────────
    if unsplash_key:
        try:
            r = _requests.get(
                "https://api.unsplash.com/search/photos",
                headers={"Authorization": f"Client-ID {unsplash_key}"},
                params={"query": query + " food restaurant", "per_page": 3,
                        "orientation": "landscape"},
                timeout=10
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    img_url = results[0]["urls"]["regular"]
                    resp = _requests.get(img_url, timeout=15)
                    if resp.status_code == 200:
                        log.info(f"✅ Unsplash photo: {query}")
                        return resp.content
        except Exception as e:
            log.warning(f"Unsplash: {e}")

    # ── Pixabay ────────────────────────────────────────────
    if pixabay_key:
        try:
            r = _requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": pixabay_key, "q": query,
                    "image_type": "photo", "category": "food",
                    "per_page": 3, "orientation": "horizontal",
                    "safesearch": "true", "min_width": 800
                },
                timeout=10
            )
            if r.status_code == 200:
                hits = r.json().get("hits", [])
                if hits:
                    img_url = hits[0]["webformatURL"]
                    resp = _requests.get(img_url, timeout=15)
                    if resp.status_code == 200:
                        log.info(f"✅ Pixabay photo: {query}")
                        return resp.content
        except Exception as e:
            log.warning(f"Pixabay: {e}")

    return None

# ── Arabic reshaping (تلقائي إن وُجد) ──────────────────────────
try:
    import arabic_reshaper
    from bidi.algorithm import get_display as bidi_display
    _HAS_ARABIC = True
except ImportError:
    _HAS_ARABIC = False

def fix_arabic(text: str) -> str:
    """إصلاح النص العربي — تشكيل الحروف + الاتجاه"""
    if not text:
        return text
    has_ar = any('\u0600' <= c <= '\u06FF' for c in text)
    if not has_ar:
        return text
    if _HAS_ARABIC:
        reshaped = arabic_reshaper.reshape(text)
        return bidi_display(reshaped)
    # Fallback: عكس الكلمات فقط (تحسين بسيط بدون مكتبة)
    words = text.split()
    return ' '.join(reversed(words))

# ─────────────────────────────────────────────────────────────────
# 📐 CONSTANTS
# ─────────────────────────────────────────────────────────────────
CARD_W, CARD_H = 1240, 874   # A5 landscape @ 150dpi
MARGIN = 55

# ─────────────────────────────────────────────────────────────────
# 🔧 COLOR UTILS
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
    lum = luminance(bg)
    return (255,255,255) if lum < 0.35 else (20,20,20)

def blend(c1, c2, t):
    return tuple(int(c1[i]*(1-t)+c2[i]*t) for i in range(3))

def darken(c, f=0.6):
    return tuple(int(x*f) for x in c)

def lighten(c, f=1.4):
    return tuple(min(255, int(x*f)) for x in c)

def with_alpha(rgb, a):
    return (*rgb, a)

# ─────────────────────────────────────────────────────────────────
# 🔤 FONTS — مع تحميل تلقائي للخطوط العربية
# ─────────────────────────────────────────────────────────────────
_FONT_CACHE = {}

# مجلد الخطوط بجانب هذا الملف
_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR  = os.path.join(_THIS_DIR, "fonts")

# روابط تحميل Noto Naskh Arabic (Google Fonts CDN)
_ARABIC_URLS = {
    # NotoNaskhArabic — أصبح variable font، الاسم تغيّر في Google Fonts
    "naskh_bold": [
        "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf",
        "https://fonts.gstatic.com/s/notonaskharabic/v33/IdGgIokULBLRYcmAYRAY7dlBBjJTLQBc_6mAtGnl6D6LQIMF3tBatBU.ttf",
    ],
    # NotoSansArabic variable font — يعمل بنجاح ✅
    "sans_var": [
        "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf",
    ],
}
_LATIN_URLS = {
    "bold": [
        "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/poppins/Poppins-Bold.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Bold.ttf",
    ],
    "reg": [
        "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/poppins/Poppins-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Regular.ttf",
    ],
}

def _download_font(fname: str, urls: list) -> bool:
    """يحاول تحميل الخط من قائمة روابط — يتوقف عند أول نجاح"""
    dest = os.path.join(_FONTS_DIR, fname)
    for url in urls:
        try:
            log.info(f"⬇️  تحميل {fname} من: {url}")
            r = _requests.get(url, timeout=30, allow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 10_000:
                with open(dest, "wb") as fh:
                    fh.write(r.content)
                log.info(f"✅ تم تحميل: {fname} ({len(r.content)//1024} KB)")
                return True
            else:
                log.warning(f"⚠️  {url} → status={r.status_code} size={len(r.content)}")
        except Exception as e:
            log.warning(f"⚠️  فشل {url}: {e}")
    log.error(f"❌ فشل تحميل {fname} من كل الروابط!")
    return False

def _ensure_fonts():
    """
    يحمّل الخطوط — NotoSansArabic هو الخط العربي الأساسي (يعمل ✅)
    NotoNaskhArabic غيّر اسمه لـ variable font → نحاول تحميله كـ bonus
    """
    os.makedirs(_FONTS_DIR, exist_ok=True)
    if not _HAS_REQUESTS:
        log.warning("⚠️  requests غير متاح — لن تُحمَّل الخطوط")
        return

    # ── 1. NotoSansArabic (الأساسي — يعمل ✅) ─────────────────────
    sans_dest = os.path.join(_FONTS_DIR, "NotoSansArabic-Regular.ttf")
    if not os.path.exists(sans_dest):
        _download_font("NotoSansArabic-Regular.ttf", _ARABIC_URLS["sans_var"])
    else:
        log.info("✔️  الخط موجود: NotoSansArabic-Regular.ttf")

    # ── 2. NotoNaskhArabic (محاولة — الاسم تغيّر) ─────────────────
    naskh_dest = os.path.join(_FONTS_DIR, "NotoNaskhArabic-Bold.ttf")
    if not os.path.exists(naskh_dest):
        ok = _download_font("NotoNaskhArabic-Bold.ttf", _ARABIC_URLS["naskh_bold"])
        if ok:
            import shutil
            reg_dest = os.path.join(_FONTS_DIR, "NotoNaskhArabic-Regular.ttf")
            if not os.path.exists(reg_dest):
                shutil.copy(naskh_dest, reg_dest)
                log.info("✅ نسخ NotoNaskhArabic-Bold → Regular")
    else:
        log.info("✔️  الخط موجود: NotoNaskhArabic-Bold.ttf")

    # ── 3. خطوط لاتينية ────────────────────────────────────────────
    for fname, urls in [
        ("Poppins-Bold.ttf",    _LATIN_URLS["bold"]),
        ("Poppins-Regular.ttf", _LATIN_URLS["reg"]),
    ]:
        dest = os.path.join(_FONTS_DIR, fname)
        if not os.path.exists(dest):
            _download_font(fname, urls)
        else:
            log.info(f"✔️  الخط موجود: {fname}")

# تشغيل تحميل الخطوط فور import
try:
    _ensure_fonts()
except Exception as _fe:
    log.warning(f"Font init error: {_fe}")


def _find_font(bold=False, arabic=False):
    """يبحث عن أفضل خط متاح — يفضّل الخطوط المحملة"""

    # ── 1. الخطوط المحملة في مجلد fonts/ ─────────────────────────
    if arabic:
        local = [
            # NotoSansArabic أولاً — يُحمَّل بنجاح ✅
            os.path.join(_FONTS_DIR, "NotoSansArabic-Regular.ttf"),
            # NotoNaskhArabic ثانياً — إن نجح تحميله
            os.path.join(_FONTS_DIR, "NotoNaskhArabic-Bold.ttf")    if bold else
            os.path.join(_FONTS_DIR, "NotoNaskhArabic-Regular.ttf"),
            os.path.join(_FONTS_DIR, "NotoNaskhArabic-Bold.ttf"),
        ]
    else:
        local = [
            os.path.join(_FONTS_DIR, "Poppins-Bold.ttf")    if bold else
            os.path.join(_FONTS_DIR, "Poppins-Regular.ttf"),
        ]
    for p in local:
        if p and os.path.exists(p):
            return p

    # ── 2. خطوط النظام (Ubuntu / Render) ──────────────────────────
    system_arabic = [
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        # مسارات إضافية على Render / Debian
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    system_latin_bold = [
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    system_latin_reg = [
        "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    if arabic:
        paths = system_arabic
    elif bold:
        paths = system_latin_bold
    else:
        paths = system_latin_reg

    for p in paths:
        if os.path.exists(p):
            return p
    return None

def get_font(size: int, bold=False, arabic=False) -> ImageFont.FreeTypeFont:
    key = (size, bold, arabic)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = _find_font(bold, arabic)
    try:
        f = ImageFont.truetype(path, size) if path else ImageFont.load_default()
    except:
        f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f

def auto_font_size(text, max_w, max_h, bold=True, arabic=False, min_s=16, max_s=100):
    for s in range(max_s, min_s-1, -2):
        f = get_font(s, bold, arabic)
        tmp = Image.new("RGB",(1,1))
        d = ImageDraw.Draw(tmp)
        try:
            bb = d.textbbox((0,0), text, font=f)
            w,h = bb[2]-bb[0], bb[3]-bb[1]
        except:
            w,h = len(text)*s*0.6, s
        if w <= max_w and h <= max_h:
            return f, s
    return get_font(min_s, bold, arabic), min_s

def text_wh(draw, text, font):
    try:
        bb = draw.textbbox((0,0), text, font=font)
        return bb[2]-bb[0], bb[3]-bb[1]
    except:
        return len(text)*20, 30

def draw_center(draw, text, cx, cy, font, color, shadow_c=None, shadow_off=3):
    text = fix_arabic(text)
    w,h = text_wh(draw, text, font)
    x,y = cx-w//2, cy-h//2
    if shadow_c:
        draw.text((x+shadow_off, y+shadow_off), text, font=font, fill=shadow_c)
    draw.text((x, y), text, font=font, fill=color)
    return h

# ─────────────────────────────────────────────────────────────────
# 📷 QR CODE
# ─────────────────────────────────────────────────────────────────
def make_qr(data: str, fg=(0,0,0), bg=(255,255,255), size=300) -> Image.Image:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10, border=2
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg, back_color=bg).convert("RGB")
    return img.resize((size, size), Image.LANCZOS)

# ─────────────────────────────────────────────────────────────────
# 🎨 SOCIAL MEDIA ICONS — رسم هندسي بدون emojis
# ─────────────────────────────────────────────────────────────────
SOCIAL_CONFIG = {
    "instagram": {"label": "Instagram",  "color": (193, 53, 132), "draw": "_icon_instagram"},
    "facebook":  {"label": "Facebook",   "color": (24, 119, 242),  "draw": "_icon_facebook"},
    "whatsapp":  {"label": "WhatsApp",   "color": (37, 211, 102),  "draw": "_icon_whatsapp"},
    "tiktok":    {"label": "TikTok",     "color": (255, 60, 100),  "draw": "_icon_tiktok"},
    "website":   {"label": "Website",    "color": (100, 149, 237), "draw": "_icon_website"},
    "phone":     {"label": "Phone",      "color": (80, 200, 120),  "draw": "_icon_phone"},
    "snapchat":  {"label": "Snapchat",   "color": (255, 232, 0),   "draw": "_icon_snapchat"},
    "youtube":   {"label": "YouTube",    "color": (255, 0, 0),     "draw": "_icon_youtube"},
}

def _icon_instagram(draw, cx, cy, r, col):
    """Instagram: مربع مستدير + دائرة + نقطة - أوضح وأكبر"""
    s = int(r * 0.85)
    # الإطار الخارجي (مربع مستدير)
    draw.rounded_rectangle([cx-s, cy-s, cx+s, cy+s], radius=s//3, outline=col, width=3)
    # الدائرة الداخلية
    cr = int(s * 0.52)
    draw.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], outline=col, width=2)
    # نقطة الكاميرا
    dot = max(3, s//5)
    draw.ellipse([cx+s//2-dot, cy-s//2-dot, cx+s//2+dot, cy-s//2+dot], fill=col)

def _icon_facebook(draw, cx, cy, r, col):
    """Facebook: f أبيض على خلفية زرقاء (الخلفية تُرسم في draw_social_bar)"""
    f_font = get_font(int(r * 1.35), bold=True)
    fw, fh = text_wh(draw, "f", f_font)
    draw.text((cx - fw//2 + r//8, cy - fh//2), "f", font=f_font, fill=col)

def _icon_whatsapp(draw, cx, cy, r, col):
    """WhatsApp: W أبيض على خلفية خضراء"""
    wf = get_font(int(r * 1.1), bold=True)
    ww, wh = text_wh(draw, "W", wf)
    draw.text((cx - ww//2, cy - wh//2), "W", font=wf, fill=col)

def _icon_tiktok(draw, cx, cy, r, col):
    """TikTok: مستطيل داكن + TT"""
    draw.rounded_rectangle([cx-r, cy-r, cx+r, cy+r], radius=r//4, fill=col)
    f = get_font(int(r * 0.9), bold=True)
    w, h = text_wh(draw, "TT", f)
    draw.text((cx - w//2, cy - h//2), "TT", font=f, fill=(255, 255, 255))

def _icon_website(draw, cx, cy, r, col):
    """Website: كرة أرضية"""
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=col, width=3)
    draw.line([cx, cy-r, cx, cy+r], fill=col, width=2)
    draw.line([cx-r, cy, cx+r, cy], fill=col, width=2)
    # قوس أفقي
    draw.arc([cx-r//2, cy-r, cx+r//2, cy+r], 0, 180, fill=col, width=2)
    draw.arc([cx-r//2, cy-r, cx+r//2, cy+r], 180, 360, fill=col, width=2)

def _icon_phone(draw, cx, cy, r, col):
    """Phone: دائرة + هاتف"""
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=col)
    pw, ph = r//2, int(r * 0.85)
    draw.rounded_rectangle([cx-pw//2, cy-ph//2, cx+pw//2, cy+ph//2],
                            radius=pw//3, outline=(255,255,255), width=2)
    draw.line([cx-pw//4, cy-ph//2+4, cx+pw//4, cy-ph//2+4], fill=(255,255,255), width=2)

def _icon_snapchat(draw, cx, cy, r, col):
    """Snapchat: شبح"""
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=col)
    f = get_font(int(r * 1.1), bold=True)
    w, h = text_wh(draw, "SC", f)
    draw.text((cx - w//2, cy - h//2), "SC", font=f, fill=(255, 255, 255))

def _icon_youtube(draw, cx, cy, r, col):
    """YouTube: مستطيل أحمر + مثلث"""
    draw.rounded_rectangle([cx-r, cy-r//2, cx+r, cy+r//2], radius=r//4, fill=col)
    pts = [(cx - r//3, cy - r//3), (cx - r//3, cy + r//3), (cx + r//2, cy)]
    draw.polygon(pts, fill=(255, 255, 255))


def _draw_star(draw, cx, cy, r, col, points=4):
    """يرسم نجمة هندسية بدون unicode"""
    import math
    pts = []
    for i in range(points * 2):
        angle = math.pi / points * i - math.pi / 2
        radius = r if i % 2 == 0 else r // 3
        pts.append((cx + int(radius * math.cos(angle)),
                    cy + int(radius * math.sin(angle))))
    draw.polygon(pts, fill=col)

_ICON_FUNCS = {
    "instagram": _icon_instagram,
    "facebook":  _icon_facebook,
    "whatsapp":  _icon_whatsapp,
    "tiktok":    _icon_tiktok,
    "website":   _icon_website,
    "phone":     _icon_phone,
    "snapchat":  _icon_snapchat,
    "youtube":   _icon_youtube,
}

def draw_social_bar(img: Image.Image, y_start: int,
                    socials: dict, accent: Tuple, fg: Tuple,
                    bg_color: Tuple) -> int:
    """يرسم شريط مواقع التواصل الاجتماعي — مع دعم كامل للعربية"""
    if not socials:
        return y_start

    active = [(k, v.strip()) for k, v in socials.items()
              if v.strip() and k in SOCIAL_CONFIG]
    if not active:
        return y_start

    draw = ImageDraw.Draw(img)

    # خط فاصل ذهبي أنيق
    sep_col = blend(accent, fg, 0.35)
    draw.line([MARGIN + 20, y_start - 8, CARD_W - MARGIN - 20, y_start - 8],
              fill=sep_col, width=1)

    icon_r  = 22
    item_w  = max(150, (CARD_W - MARGIN * 2) // max(len(active), 1))
    item_w  = min(item_w, 220)
    total_w = len(active) * item_w
    x_start = (CARD_W - total_w) // 2

    for i, (key, val) in enumerate(active):
        cfg  = SOCIAL_CONFIG[key]
        fn   = _ICON_FUNCS.get(key)
        cx   = x_start + i * item_w + item_w // 2
        cy   = y_start + 32

        # دائرة خلفية ملونة
        brand_color = cfg["color"]
        draw.ellipse([cx - icon_r - 3, cy - icon_r - 3,
                      cx + icon_r + 3, cy + icon_r + 3],
                     fill=brand_color)
        draw.ellipse([cx - icon_r - 3, cy - icon_r - 3,
                      cx + icon_r + 3, cy + icon_r + 3],
                     outline=blend(brand_color, (255, 255, 255), 0.25), width=1)

        # رسم الأيقونة
        if fn:
            try:
                fn(draw, cx, cy, icon_r, (255, 255, 255))
            except:
                pass

        # اسم المنصة (دائماً بالإنجليزية)
        lbl       = cfg["label"]
        lbl_font  = get_font(13, bold=True)
        lw, lh    = text_wh(draw, lbl, lbl_font)
        draw.text((cx - lw // 2, cy + icon_r + 6), lbl,
                  font=lbl_font, fill=accent)

        # قيمة المستخدم — دعم كامل للعربية
        has_ar    = any('\u0600' <= c <= '\u06FF' for c in val)
        val_fixed = fix_arabic(val) if has_ar else val
        val_font  = get_font(15, bold=False, arabic=has_ar)
        if len(val_fixed) > 14:
            val_fixed = val_fixed[:14] + "..."
        vw, vh    = text_wh(draw, val_fixed, val_font)
        val_col   = blend(fg, bg_color, 0.2)
        draw.text((cx - vw // 2, cy + icon_r + 6 + lh + 3), val_fixed,
                  font=val_font, fill=val_col)

    return y_start + icon_r * 2 + 72


# ─────────────────────────────────────────────────────────────────
# 🖼️ BACKGROUND GENERATORS
# ─────────────────────────────────────────────────────────────────

def _make_base(primary: Tuple) -> Image.Image:
    """خلفية أساسية متدرجة"""
    img = Image.new("RGB", (CARD_W, CARD_H), primary)
    draw = ImageDraw.Draw(img)
    # تدرج من أعلى لأسفل
    lighter = lighten(primary, 1.3)
    for y in range(CARD_H):
        t = y / CARD_H
        col = blend(lighter, primary, t * 0.6)
        draw.line([(0, y), (CARD_W, y)], fill=col)
    return img

def draw_minimal_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    draw = ImageDraw.Draw(img)
    # خطوط قطرية ناعمة
    col = blend(accent, img.getpixel((0,0)), 0.92)
    for i in range(-CARD_H, CARD_W + CARD_H, 100):
        draw.line([(i, 0), (i+CARD_H, CARD_H)], fill=col, width=1)
    return img

def draw_arabesque_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    draw = ImageDraw.Draw(img)
    bg = img.getpixel((0,0))
    col = blend(accent, bg, 0.88)

    step = 110
    for row in range(-1, CARD_H//step+2):
        for col_i in range(-1, CARD_W//step+2):
            cx = col_i*step + (55 if row%2 else 0)
            cy = row*step
            r = 40
            pts = []
            for k in range(8):
                ra = r if k%2==0 else r//2
                ang = k * math.pi/4 - math.pi/8
                pts.append((cx+int(ra*math.cos(ang)), cy+int(ra*math.sin(ang))))
            draw.polygon(pts, outline=col, fill=None)
    return img

def draw_zellige_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    draw = ImageDraw.Draw(img)
    bg = img.getpixel((0,0))
    col = blend(accent, bg, 0.87)
    tile = 80
    for row in range(CARD_H//tile+2):
        for ci in range(CARD_W//tile+2):
            x, y = ci*tile, row*tile
            draw.rectangle([x+3, y+3, x+tile-3, y+tile-3], outline=col, width=1)
            cx, cy = x+tile//2, y+tile//2
            r_out, r_in = 26, 13
            pts = []
            for k in range(8):
                ra = r_out if k%2==0 else r_in
                ang = k*math.pi/4 - math.pi/8
                pts.append((cx+int(ra*math.cos(ang)), cy+int(ra*math.sin(ang))))
            draw.polygon(pts, fill=col)
    return img

def draw_herringbone_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """خلفية تشبه نسيج هيرينغبون — راقية"""
    draw = ImageDraw.Draw(img)
    bg = img.getpixel((0,0))
    col = blend(accent, bg, 0.90)
    step = 40
    for i in range(-CARD_H, CARD_W+CARD_H, step*2):
        draw.line([(i, 0), (i+CARD_H, CARD_H)], fill=col, width=2)
        draw.line([(i+step, 0), (i+step-CARD_H, CARD_H)], fill=col, width=1)
    return img

def draw_diamond_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """خلفية ماسات — فاخرة"""
    draw = ImageDraw.Draw(img)
    bg = img.getpixel((0,0))
    col = blend(accent, bg, 0.89)
    step = 70
    for row in range(-1, CARD_H//step+3):
        for ci in range(-1, CARD_W//step+3):
            cx = ci*step + (step//2 if row%2 else 0)
            cy = row*step
            r = step//2 - 6
            pts = [(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)]
            draw.polygon(pts, outline=col, fill=None)
    return img

def draw_moroccan_bg(img: Image.Image, accent: Tuple) -> Image.Image:
    """نجوم مغربية — 8 نقاط"""
    draw = ImageDraw.Draw(img)
    bg = img.getpixel((0,0))
    col = blend(accent, bg, 0.88)
    step = 130
    for row in range(-1, CARD_H//step+2):
        for ci in range(-1, CARD_W//step+2):
            cx = ci*step + (65 if row%2 else 0)
            cy = row*step
            r = 45
            pts = []
            for k in range(16):
                ra = r if k%2==0 else r*0.4
                ang = k*math.pi/8
                pts.append((cx+int(ra*math.cos(ang)), cy+int(ra*math.sin(ang))))
            draw.polygon(pts, fill=col)
    return img

BG_FUNCS = {
    "minimal":    draw_minimal_bg,
    "arabesque":  draw_arabesque_bg,
    "zellige":    draw_zellige_bg,
    "herringbone":draw_herringbone_bg,
    "diamond":    draw_diamond_bg,
    "moroccan":   draw_moroccan_bg,
    # legacy aliases
    "tajine":     draw_moroccan_bg,
    "sandwich":   draw_herringbone_bg,
    "couscous":   draw_zellige_bg,
}

BG_LABELS = {
    "minimal":     "✨ بسيط وأنيق",
    "arabesque":   "🌟 زخارف عربية",
    "zellige":     "🔷 بلاط مغربي",
    "herringbone": "〰️ نسيج هيرينغبون",
    "diamond":     "💎 ماسات",
    "moroccan":    "⭐ نجوم مغربية",
    "food_photo":  "📸 صورة طعام حقيقية",
}

STYLE_LABELS = {
    "luxury":  "👑 فاخر ذهبي",
    "modern":  "🔷 عصري",
    "classic": "📜 كلاسيكي",
    "bold":    "⚡ جريء",
    "neon":    "🌈 نيون",
    "rustic":  "🌿 ريفي",
}


# ─────────────────────────────────────────────────────────────────
# 🖼️ FRAMES
# ─────────────────────────────────────────────────────────────────

def _frame_luxury(draw, acc, bg):
    """إطار فاخر — خطان ذهبيان + نقاط زوايا"""
    for m, w in [(12, 3), (22, 1)]:
        draw.rectangle([m, m, CARD_W-m, CARD_H-m], outline=acc, width=w)
    # زخرفة الزوايا
    c_size = 18
    for cx, cy in [(22,22), (CARD_W-22,22), (22,CARD_H-22), (CARD_W-22,CARD_H-22)]:
        draw.ellipse([cx-c_size//2, cy-c_size//2, cx+c_size//2, cy+c_size//2], fill=acc)
        draw.ellipse([cx-c_size//4, cy-c_size//4, cx+c_size//4, cy+c_size//4], fill=bg)
    # خط متقطع داخلي
    seg = 35
    for x in range(35, CARD_W-35, seg*2):
        draw.line([x, 34, x+seg, 34], fill=acc, width=1)
        draw.line([x, CARD_H-34, x+seg, CARD_H-34], fill=acc, width=1)
    for y in range(35, CARD_H-35, seg*2):
        draw.line([34, y, 34, y+seg], fill=acc, width=1)
        draw.line([CARD_W-34, y, CARD_W-34, y+seg], fill=acc, width=1)

def _frame_modern(draw, acc, bg):
    draw.rectangle([0, 0, CARD_W, 12], fill=acc)
    draw.rectangle([0, CARD_H-12, CARD_W, CARD_H], fill=acc)
    draw.rectangle([0, 0, 10, CARD_H], fill=darken(acc, 0.8))
    draw.rectangle([CARD_W-10, 0, CARD_W, CARD_H], fill=darken(acc, 0.8))

def _frame_classic(draw, acc, bg):
    for m, w in [(12, 4), (24, 1)]:
        draw.rectangle([m, m, CARD_W-m, CARD_H-m], outline=acc, width=w)
    for cx, cy in [(12,12), (CARD_W-12,12), (12,CARD_H-12), (CARD_W-12,CARD_H-12)]:
        draw.ellipse([cx-10, cy-10, cx+10, cy+10], fill=acc)

def _frame_bold(draw, acc, bg, fg):
    draw.rectangle([0, 0, CARD_W, 85], fill=acc)
    draw.rectangle([0, CARD_H-55, CARD_W, CARD_H], fill=darken(acc, 0.7))

def _frame_neon(draw, acc, bg):
    neon = lighten(acc, 1.5)
    for m, w, a in [(10,5,acc), (18,2,lighten(acc,1.3)), (24,1,acc)]:
        draw.rectangle([m, m, CARD_W-m, CARD_H-m], outline=a, width=w)

def _frame_rustic(draw, acc, bg):
    seg = 45
    for x in range(16, CARD_W-16, seg*2):
        draw.line([x, 16, x+seg, 16], fill=acc, width=3)
        draw.line([x, CARD_H-16, x+seg, CARD_H-16], fill=acc, width=3)
    for y in range(16, CARD_H-16, seg*2):
        draw.line([16, y, 16, y+seg], fill=acc, width=3)
        draw.line([CARD_W-16, y, CARD_W-16, y+seg], fill=acc, width=3)
    # نجوم في الزوايا
    star_f = get_font(28, bold=True)
    for cx, cy in [(24,24), (CARD_W-44,24), (24,CARD_H-44), (CARD_W-44,CARD_H-44)]:
        draw.text((cx, cy), "*", font=star_f, fill=acc)


# ─────────────────────────────────────────────────────────────────
# 📱 QR PLACEMENT
# ─────────────────────────────────────────────────────────────────

def _place_qr(img, draw, style, data, primary, acc, fg, card_type):
    qr_size = 310

    qr_x = CARD_W//2 - qr_size//2
    qr_y = CARD_H//2 - qr_size//2 + (30 if style != "bold" else 55)

    # ألوان QR
    if style == "luxury":
        qr_fg, qr_bg = primary, acc
        border_c, border_w = acc, 16
    elif style == "neon":
        qr_fg, qr_bg = primary, lighten(acc, 1.3)
        border_c, border_w = lighten(acc, 1.3), 12
    elif style == "bold":
        qr_fg, qr_bg = primary, (245, 245, 240)
        border_c, border_w = (245,245,240), 14
    elif style == "rustic":
        qr_fg, qr_bg = darken(acc, 0.55), lighten(primary, 1.4)
        border_c, border_w = acc, 12
    else:
        qr_fg, qr_bg = primary, acc
        border_c, border_w = acc, 12

    qr_img = make_qr(data, fg=qr_fg, bg=qr_bg, size=qr_size)

    # إطار أبيض + إطار ملون
    total = qr_size + border_w*2 + 8
    framed = Image.new("RGB", (total, total), border_c)
    inner  = Image.new("RGB", (qr_size+8, qr_size+8), (255,255,255))
    inner.paste(qr_img, (4,4))
    framed.paste(inner, (border_w, border_w))
    img.paste(framed, (qr_x, qr_y))

    return qr_size, qr_x, qr_y, total


# ─────────────────────────────────────────────────────────────────
# ✍️ TEXT DRAWING
# ─────────────────────────────────────────────────────────────────

def _draw_texts(draw, style, name, table_num, primary, acc, fg,
                qr_x, qr_y, qr_size, qr_total, card_type,
                ssid, wifi_pass, socials):
    """يرسم كل النصوص"""

    has_social  = bool(socials and any(v.strip() for v in socials.values()))
    social_h    = 95 if has_social else 0
    bottom_safe = CARD_H - MARGIN - social_h

    is_arabic = any('\u0600' <= c <= '\u06FF' for c in name)
    name_fixed = fix_arabic(name)

    # ── اسم المطعم ──────────────────────────────────────────────
    if style == "bold":
        name_font, _ = auto_font_size(name_fixed, CARD_W-100, 60,
                                       bold=True, arabic=is_arabic, max_s=60)
        name_fg = auto_fg(acc)
        shd     = darken(name_fg, 0.65)
        draw_center(draw, name_fixed, CARD_W//2, 44, name_font, name_fg, shd)
    else:
        name_font, _ = auto_font_size(name_fixed, CARD_W-130, 70,
                                       bold=True, arabic=is_arabic, max_s=72)
        shd = darken(fg, 0.55) if fg == (255,255,255) else (180,180,180)
        draw_center(draw, name_fixed, CARD_W//2, qr_y - 58, name_font, fg, shd)

    # ── خط زخرفي تحت الاسم ──────────────────────────────────────
    lx, ll = CARD_W//2, 230
    deco_y  = qr_y - 22
    if style == "luxury":
        draw.line([lx-ll//2, deco_y, lx+ll//2, deco_y], fill=acc, width=1)
        # نجمة وسط
        sf = get_font(18, bold=True)
        sw, sh = text_wh(draw, "+", sf)
        draw.text((lx-sw//2, deco_y-sh//2-1), "+", font=sf, fill=acc)
    elif style in ("classic", "modern", "neon"):
        draw.line([lx-ll//2, deco_y, lx+ll//2, deco_y], fill=acc, width=2)
    elif style == "rustic":
        for rx in range(lx-ll//2, lx+ll//2, 16):
            draw.line([rx, deco_y, rx+10, deco_y], fill=acc, width=2)

    # ── CTA + رقم الطاولة — شريط واضح دائماً تحت QR ─────────────
    cta_y = qr_y + qr_total + 10
    if card_type == "menu":
        cta_text = "Scannez pour voir le menu"
        if is_arabic:
            cta_text = fix_arabic("امسح للطلب")
    else:
        cta_text = "Scanner pour le WiFi"

    cta_is_ar = any('\u0600' <= c <= '\u06FF' for c in cta_text)
    cta_font  = get_font(22, bold=True, arabic=cta_is_ar)
    cw, ch    = text_wh(draw, cta_text, cta_font)

    tbl_text  = f"Table  {table_num}"
    tf        = get_font(20, bold=True)
    tw, th    = text_wh(draw, tbl_text, tf)

    pad_x   = 28
    pad_top = 12
    pad_bot = 12
    gap     = 10
    strip_w = max(cw + pad_x * 2, tw + pad_x * 2, 300)
    strip_h = pad_top + ch + gap + th + pad_bot
    sx      = CARD_W // 2 - strip_w // 2
    sy      = cta_y

    # خلفية معتمة تماماً
    _rounded_rect(draw,
                  [sx, sy, sx + strip_w, sy + strip_h],
                  10, primary, acc, 2)

    # سطر CTA — لون الأكسنت
    cta_col  = acc if style != "bold" else auto_fg(primary)
    cta_cy   = sy + pad_top + ch // 2
    draw_center(draw, cta_text, CARD_W // 2, cta_cy, cta_font, cta_col)

    # فاصل ذهبي
    fsep_y = sy + pad_top + ch + gap // 2
    draw.line([sx + 20, fsep_y, sx + strip_w - 20, fsep_y],
              fill=blend(acc, primary, 0.5), width=1)

    # رقم الطاولة
    tbl_cy = sy + pad_top + ch + gap + th // 2
    draw_center(draw, tbl_text, CARD_W // 2, tbl_cy, tf, fg)

    # ── WiFi info ────────────────────────────────────────────────
    if card_type == "wifi" and ssid:
        _draw_wifi_info(draw, ssid, wifi_pass, primary, acc, fg,
                        style, qr_x, qr_y, qr_size, bottom_safe)

    return bottom_safe + 8


def _draw_wifi_info(draw, ssid, wifi_pass, primary, acc, fg, style,
                    qr_x, qr_y, qr_size, bottom_y):
    info_x  = 50
    info_w  = qr_x - 80
    if info_w < 200:
        info_x = MARGIN
        info_w = CARD_W - MARGIN*2
        base_y = qr_y + qr_size + 70
    else:
        base_y = qr_y + 50

    lf = get_font(20)
    vf_s, _ = auto_font_size(ssid, info_w, 52, bold=True, max_s=40, min_s=18)
    vf_p, _ = auto_font_size(wifi_pass, info_w, 52, bold=True, max_s=44, min_s=18)
    lc = blend(fg, primary, 0.4)

    draw.text((info_x, base_y), "RÉSEAU / SSID", font=lf, fill=lc)
    _, ssid_h = text_wh(draw, ssid, vf_s)
    draw.text((info_x, base_y+26), ssid, font=vf_s, fill=fg)

    sep_y = base_y + 26 + ssid_h + 14
    draw.line([info_x, sep_y, info_x+info_w, sep_y], fill=acc, width=1)

    draw.text((info_x, sep_y+10), "MOT DE PASSE", font=lf, fill=lc)
    draw.text((info_x, sep_y+36), wifi_pass, font=vf_p, fill=acc)


def _rounded_rect(draw, xy, r, fill, outline=None, width=2):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=r, fill=fill,
                            outline=outline, width=width if outline else 0)


# ─────────────────────────────────────────────────────────────────
# 🏭 MAIN RENDERER
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
    card_type: str,
    ssid: str = "",
    wifi_pass: str = "",
) -> Image.Image:

    img  = _make_base(primary)
    draw = ImageDraw.Draw(img)
    fg   = auto_fg(primary)

    # خلفية
    bg_fn = BG_FUNCS.get(bg_type, draw_minimal_bg)
    img   = bg_fn(img, accent)
    draw  = ImageDraw.Draw(img)

    # إطار
    if style == "luxury":
        _frame_luxury(draw, accent, primary)
    elif style == "modern":
        _frame_modern(draw, accent, primary)
    elif style == "classic":
        _frame_classic(draw, accent, primary)
    elif style == "bold":
        _frame_bold(draw, accent, primary, fg)
    elif style == "neon":
        _frame_neon(draw, accent, primary)
    elif style == "rustic":
        _frame_rustic(draw, accent, primary)

    # QR
    qr_size, qr_x, qr_y, qr_total = _place_qr(
        img, draw, style, qr_data, primary, accent, fg, card_type
    )

    # نصوص
    draw = ImageDraw.Draw(img)
    social_y = _draw_texts(
        draw, style, name, table_num, primary, accent, fg,
        qr_x, qr_y, qr_size, qr_total, card_type, ssid, wifi_pass, socials
    )

    # سوشيال
    if socials and any(v.strip() for v in socials.values()):
        draw_social_bar(img, social_y, socials, accent, fg, primary)

    return img


# ─────────────────────────────────────────────────────────────────
# 🌐 PUBLIC API
# ─────────────────────────────────────────────────────────────────

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
    # خيارات صورة الطعام (تُستخدم عندما bg_type="food_photo")
    photo_bytes: Optional[bytes] = None,
    photo_query: str = "",
    pexels_key: str = "",
    unsplash_key: str = "",
    pixabay_key: str = "",
    cta_line1: str = "VIEW OUR",
    cta_line2: str = "MENU",
) -> tuple:
    """يولد (menu_card, wifi_card) كـ PIL Images"""
    if socials is None:
        socials = {}

    # ── مسار صورة الطعام ──────────────────────────────────
    if bg_type == "food_photo":
        return generate_food_photo_card(
            restaurant_name=restaurant_name,
            ssid=ssid, wifi_password=wifi_password,
            table_number=table_number, menu_url=menu_url,
            primary_color_hex=primary_color_hex,
            accent_color_hex=accent_color_hex,
            photo_bytes=photo_bytes,
            photo_query=photo_query or restaurant_name,
            pexels_key=pexels_key,
            unsplash_key=unsplash_key,
            pixabay_key=pixabay_key,
            socials=socials,
            cta_line1=cta_line1,
            cta_line2=cta_line2,
        )

    # ── المسار العادي ─────────────────────────────────────
    style   = style.lower()
    primary = hex_to_rgb(primary_color_hex)
    accent  = hex_to_rgb(accent_color_hex)
    wifi_qr = f"WIFI:T:WPA;S:{ssid};P:{wifi_password};;"

    menu_card = _render_card(
        style=style, name=restaurant_name, qr_data=menu_url,
        table_num=table_number, primary=primary, accent=accent,
        bg_type=bg_type, socials=socials, card_type="menu",
    )
    wifi_card = _render_card(
        style=style, name=restaurant_name, qr_data=wifi_qr,
        table_num=table_number, primary=primary, accent=accent,
        bg_type=bg_type, socials=socials, card_type="wifi",
        ssid=ssid, wifi_pass=wifi_password,
    )
    return menu_card, wifi_card


def card_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150,150))
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────
# 📸 FOOD PHOTO CARD — مثل صورة Table Tent
# ─────────────────────────────────────────────────────────────────

def _render_food_photo_card(
    name: str,
    qr_data: str,
    table_num: int,
    primary: Tuple,
    accent: Tuple,
    card_type: str,
    photo_bytes: Optional[bytes],
    ssid: str = "",
    wifi_pass: str = "",
    socials: dict = None,
    cta_line1: str = "VIEW OUR",
    cta_line2: str = "MENU",
) -> Image.Image:
    """
    تصميم Table Tent احترافي:
    - الجزء العلوي (38%): هيدر داكن + اسم المطعم + شعار وزخارف
    - الجزء السفلي (62%): صورة طعام + QR في المنتصف + بيانات منظمة
    """
    if socials is None:
        socials = {}

    has_social   = bool(socials and any(v.strip() for v in socials.values()))
    is_arabic    = any('\u0600' <= c <= '\u06FF' for c in name)
    name_fixed   = fix_arabic(name)
    fg           = auto_fg(primary)

    # ── أبعاد المناطق ────────────────────────────────────
    HEADER_H = int(CARD_H * 0.38)   # منطقة الهيدر
    PHOTO_Y  = HEADER_H
    SOC_H    = 90 if has_social else 0
    PHOTO_H  = CARD_H - HEADER_H    # منطقة الصورة كاملة

    # ── الصورة الأساسية ──────────────────────────────────
    img  = Image.new("RGB", (CARD_W, CARD_H), primary)
    draw = ImageDraw.Draw(img)

    # تدرج في الهيدر (من أفتح للأداكن)
    header_light = lighten(primary, 1.3)
    for y in range(HEADER_H):
        t   = y / HEADER_H
        col = blend(header_light, primary, t * 0.75)
        draw.line([(0, y), (CARD_W, y)], fill=col)

    # ── الجزء السفلي: صورة أو تدرج دافئ ────────────────
    if photo_bytes:
        try:
            photo    = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
            ph_w, ph_h = photo.size
            # ملء الجزء السفلي بالكامل
            target_w, target_h = CARD_W, PHOTO_H
            scale = max(target_w / ph_w, target_h / ph_h)
            nw    = int(ph_w * scale)
            nh    = int(ph_h * scale)
            photo = photo.resize((nw, nh), Image.LANCZOS)
            ox    = (nw - target_w) // 2
            oy    = (nh - target_h) // 2
            photo = photo.crop((ox, oy, ox + target_w, oy + target_h))

            # تعتيم خفيف لتحسين قراءة النص فوق الصورة
            overlay = Image.new("RGB", (CARD_W, target_h), (0, 0, 0))
            photo   = Image.blend(photo, overlay, 0.30)

            img.paste(photo, (0, PHOTO_Y))
        except Exception as e:
            log.warning(f"Photo error: {e}")
            _draw_warm_gradient_bg(img, PHOTO_Y, primary, accent)
    else:
        _draw_warm_gradient_bg(img, PHOTO_Y, primary, accent)

    draw = ImageDraw.Draw(img)

    # ── إطار فاخر ─────────────────────────────────────────
    _frame_luxury(draw, accent, primary)

    # شريط ذهبي فاصل بين الهيدر والصورة
    draw.rectangle([0, HEADER_H - 4, CARD_W, HEADER_H + 4], fill=accent)

    # ════════════════════════════════════════════════════
    # HEADER — نصوص وزخارف الجزء العلوي
    # ════════════════════════════════════════════════════

    # نجوم زخرفية في أعلى الهيدر
    star_y = 38
    for sx in [CARD_W // 2 - 240, CARD_W // 2 + 230]:
        _draw_star(draw, sx, star_y, 7, blend(accent, (255,255,255), 0.5), points=4)

    # سطر CTA صغير فوق الاسم
    if is_arabic:
        cta_small = fix_arabic("امسح لرؤية")
    else:
        cta_small = cta_line1  # e.g. "VIEW OUR"

    cta_small_font = get_font(26, bold=False, arabic=is_arabic)
    csw, csh       = text_wh(draw, cta_small, cta_small_font)
    cta_y          = 30
    # خط زخرفي على الجانبين
    line_len = (CARD_W - csw - 80) // 2
    line_y   = cta_y + csh // 2
    draw.line([40, line_y, 40 + line_len, line_y],        fill=blend(accent, primary, 0.6), width=1)
    draw.line([CARD_W - 40 - line_len, line_y, CARD_W - 40, line_y], fill=blend(accent, primary, 0.6), width=1)
    draw.text((CARD_W // 2 - csw // 2, cta_y), cta_small,
              font=cta_small_font, fill=blend(fg, accent, 0.4))

    # اسم المطعم — كبير وبارز في وسط الهيدر
    name_max_w = CARD_W - 120
    name_max_h = HEADER_H - csh - 80
    name_font, name_sz = auto_font_size(
        name_fixed, name_max_w, name_max_h,
        bold=True, arabic=is_arabic, max_s=90, min_s=28
    )
    name_center_y = cta_y + csh + (HEADER_H - cta_y - csh - 35) // 2 + 8
    shd_col       = darken(fg, 0.5) if fg == (255,255,255) else (150,150,150)
    draw_center(draw, name_fixed, CARD_W // 2, name_center_y, name_font, fg, shd_col, 2)

    # سطر MENU / المنيو تحت الاسم (للإنجليزية)
    if not is_arabic:
        l2_font = get_font(30, bold=False)
        l2w, l2h = text_wh(draw, cta_line2, l2_font)
        draw_center(draw, cta_line2, CARD_W // 2, HEADER_H - 28,
                    l2_font, blend(fg, accent, 0.55))

    # نجوم زخرفية أسفل الهيدر (خط صغير ونجوم)
    bot_star_y = HEADER_H - 18
    for sx in [CARD_W // 2 - 110, CARD_W // 2, CARD_W // 2 + 100]:
        _draw_star(draw, sx, bot_star_y, 5, accent, points=4)

    # ════════════════════════════════════════════════════
    # PHOTO ZONE — QR + نصوص على الصورة
    # ════════════════════════════════════════════════════

    # حساب الارتفاع المتاح للـ QR والنصوص (فوق شريط السوشيال)
    available_h = PHOTO_H - SOC_H - 20
    qr_size   = min(280, available_h - 100)   # QR يتكيّف مع المساحة
    qr_border = 14
    total_qr  = qr_size + qr_border * 2 + 8

    # توسيط QR عمودياً في المنطقة المتاحة
    qr_zone_h = available_h - 85   # مساحة للـ QR فقط (الباقي للنصوص أسفله)
    qr_x      = CARD_W // 2 - total_qr // 2
    qr_y      = PHOTO_Y + (qr_zone_h - total_qr) // 2 + 5

    # ألوان QR: داكن على أبيض — قابل للقراءة دائماً
    qr_img = make_qr(qr_data, fg=(15, 10, 5), bg=(255, 255, 255), size=qr_size)

    # ظل ناعم خلف إطار QR
    shadow   = Image.new("RGBA", (total_qr + 24, total_qr + 24), (0, 0, 0, 140))
    img_rgba = img.convert("RGBA")
    img_rgba.paste(shadow, (qr_x - 12, qr_y - 6), shadow)
    img      = img_rgba.convert("RGB")
    draw     = ImageDraw.Draw(img)

    # إطار ذهبي + أبيض حول QR
    framed = Image.new("RGB", (total_qr, total_qr), accent)
    inner  = Image.new("RGB", (qr_size + 8, qr_size + 8), (255, 255, 255))
    inner.paste(qr_img, (4, 4))
    framed.paste(inner, (qr_border, qr_border))
    img.paste(framed, (qr_x, qr_y))
    draw = ImageDraw.Draw(img)

    # ── نصوص أسفل QR — شريط معلومات واضح دائماً ───────────
    info_y = qr_y + total_qr + 8

    # نص امسح / Scan
    if card_type == "menu":
        scan_text = fix_arabic("امسح للطلب") if is_arabic else "Scan to Order"
    else:
        scan_text_raw = f"WiFi  {ssid}" if ssid else "WiFi"
        scan_text = fix_arabic(scan_text_raw) if is_arabic else scan_text_raw

    scan_ar   = is_arabic or any('\u0600' <= c <= '\u06FF' for c in scan_text)
    scan_font = get_font(22, bold=True, arabic=scan_ar)
    sw, sh    = text_wh(draw, scan_text, scan_font)

    tbl_font  = get_font(20, bold=True)
    tbl_text  = f"Table  {table_num}"
    tw, th    = text_wh(draw, tbl_text, tbl_font)

    pad_x   = 28
    pad_top = 12
    pad_bot = 12
    gap     = 10
    strip_w = max(sw + pad_x * 2, tw + pad_x * 2, total_qr)
    strip_h = pad_top + sh + gap + th + pad_bot
    strip_x = CARD_W // 2 - strip_w // 2
    strip_y = info_y

    # شريط خلفية معتمة تماماً
    draw.rounded_rectangle(
        [strip_x, strip_y, strip_x + strip_w, strip_y + strip_h],
        radius=10, fill=primary, outline=accent, width=2,
    )

    # سطر "امسح للطلب" — أكسنت ذهبي
    draw_center(draw, scan_text,
                CARD_W // 2, strip_y + pad_top + sh // 2,
                scan_font, accent)

    # فاصل
    sep_y = strip_y + pad_top + sh + gap // 2
    draw.line([strip_x + 20, sep_y, strip_x + strip_w - 20, sep_y],
              fill=blend(accent, primary, 0.6), width=1)

    # رقم الطاولة
    draw_center(draw, tbl_text,
                CARD_W // 2, strip_y + pad_top + sh + gap + th // 2,
                tbl_font, fg)

    # ── شريط السوشيال ─────────────────────────────────────
    if has_social:
        # شريط خلفية داكن شبه شفاف للسوشيال
        soc_bg_y = CARD_H - SOC_H - 8
        draw.rectangle([0, soc_bg_y - 4, CARD_W, CARD_H],
                       fill=blend(primary, (0, 0, 0), 0.55))
        draw_social_bar(img, soc_bg_y, socials, accent, (255, 255, 255), primary)

    return img


def _draw_warm_gradient_bg(img, start_y, primary, accent):
    """خلفية دافئة بديلة عن صورة الطعام"""
    draw = ImageDraw.Draw(img)
    warm1 = blend(primary, (180, 110, 40), 0.55)
    warm2 = blend(primary, (120, 60, 20), 0.4)
    for y in range(start_y, CARD_H):
        t = (y - start_y) / max(CARD_H - start_y, 1)
        col = blend(warm1, warm2, t * 0.8)
        draw.line([(0, y), (img.width, y)], fill=col)

    # زخارف طعام مرسومة
    d = draw
    a = blend(accent, (0,0,0), 0.7)
    cx, cy = img.width // 2, start_y + (CARD_H - start_y) // 2
    step = 140
    for ox in range(-step*3, img.width + step, step):
        for oy in range(start_y, CARD_H, step):
            d.ellipse([ox-25, oy-15, ox+25, oy+15], outline=a, width=1)
            d.ellipse([ox-12, oy-6, ox+12, oy+6], fill=a)


def generate_food_photo_card(
    restaurant_name: str,
    ssid: str,
    wifi_password: str,
    table_number: int,
    menu_url: str,
    primary_color_hex: str = "#1a5c1a",
    accent_color_hex:  str = "#ffffff",
    photo_bytes: Optional[bytes] = None,
    photo_query: str = "restaurant food",
    pexels_key: str = "",
    unsplash_key: str = "",
    pixabay_key: str = "",
    socials: dict = None,
    cta_line1: str = "VIEW OUR",
    cta_line2: str = "MENU",
) -> tuple:
    """
    📸 يولد بطاقة Table Tent بصورة طعام حقيقية
    
    يجلب الصورة من Pexels/Unsplash/Pixabay تلقائياً
    أو يقبل photo_bytes مباشرة.
    
    Returns: (menu_card, wifi_card) كـ PIL Images
    """
    if socials is None:
        socials = {}

    primary = hex_to_rgb(primary_color_hex)
    accent  = hex_to_rgb(accent_color_hex)
    wifi_qr = f"WIFI:T:WPA;S:{ssid};P:{wifi_password};;"

    # جلب صورة إذا لم تُعطَ
    photo = photo_bytes
    if not photo and (pexels_key or unsplash_key or pixabay_key):
        photo = fetch_food_photo_bytes(
            photo_query or restaurant_name,
            pexels_key=pexels_key,
            unsplash_key=unsplash_key,
            pixabay_key=pixabay_key,
        )

    menu_card = _render_food_photo_card(
        name=restaurant_name, qr_data=menu_url,
        table_num=table_number, primary=primary, accent=accent,
        card_type="menu", photo_bytes=photo, socials=socials,
        cta_line1=cta_line1, cta_line2=cta_line2,
    )
    wifi_card = _render_food_photo_card(
        name=restaurant_name, qr_data=wifi_qr,
        table_num=table_number, primary=primary, accent=accent,
        card_type="wifi", photo_bytes=photo, ssid=ssid,
        wifi_pass=wifi_password, socials=socials,
        cta_line1="CONNECT TO", cta_line2="WIFI",
    )
    return menu_card, wifi_card
