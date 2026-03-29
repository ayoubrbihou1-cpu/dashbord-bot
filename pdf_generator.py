"""
📄 مولد PDF الشيفالي (Table Tent) — هندسة رياضية دقيقة
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 قياسات الشيفالي:
   ┌──────────────────────┐  ▲
   │  واجهة المنيو/QR     │  │ 14.8cm (مقلوبة 180°)
   │  (مقلوبة للطباعة)    │  ▼
   ├──────────────────────┤  ▲
   │     القاعدة           │  │ 4.4cm  (فراغ ← تلقائي)
   ├──────────────────────┤  ▼
   │  واجهة WiFi/QR       │  ▲
   │  (مقادة — 0 درجة)    │  │ 14.8cm
   └──────────────────────┘  ▼
   العرض الكلي: 10.5cm | الطول الكلي: 34cm
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import io
from PIL import Image
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from generative_design import generate_table_card


# ── القياسات الهندسية الثابتة (بالنقاط — points) ─────────────────────────────
_W        = 105 * mm   # عرض الشيفالي:        10.5cm
_H        = 340 * mm   # طول الشيفالي الكلي:   34cm
_PANEL_H  = 148 * mm   # ارتفاع كل واجهة:      14.8cm
# القاعدة = _H - 2*_PANEL_H = 340 - 296 = 44mm = 4.4cm ← تلقائي ✅

# إحداثيات الواجهتين في نظام reportlab (y=0 في الأسفل)
_MENU_Y   = _H - _PANEL_H   # الواجهة العلوية تبدأ من:  192mm ← 19.2cm
_WIFI_Y   = 0               # الواجهة السفلية تبدأ من:  0

# دقة الصور (150 dpi)
_DPI        = 150
_PX_PER_MM  = _DPI / 25.4
_PANEL_PX_W = int(105 * _PX_PER_MM)   # ≈ 620px
_PANEL_PX_H = int(148 * _PX_PER_MM)   # ≈ 874px


def _crop_to_panel(img: Image.Image) -> Image.Image:
    """
    يحوّل صورة A5 landscape (1240×874) إلى portrait (620×874)
    بقص المنتصف — بدون تشويه للمحتوى
    """
    src_w, src_h = img.size
    tgt_ratio    = _PANEL_PX_W / _PANEL_PX_H  # ≈ 0.71 (portrait)
    src_ratio    = src_w / src_h               # ≈ 1.42 (landscape)

    if src_ratio > tgt_ratio:
        # الصورة أعرض من اللازم → نقطع من الجانبين
        new_w = int(src_h * tgt_ratio)
        left  = (src_w - new_w) // 2
        img   = img.crop((left, 0, left + new_w, src_h))
    else:
        # الصورة أطول من اللازم → نقطع من الأعلى والأسفل
        new_h = int(src_w / tgt_ratio)
        top   = (src_h - new_h) // 2
        img   = img.crop((0, top, src_w, top + new_h))

    return img.resize((_PANEL_PX_W, _PANEL_PX_H), Image.LANCZOS)


def _img_to_reader(img: Image.Image) -> ImageReader:
    """PIL Image → ImageReader لـ reportlab"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def generate_table_tents_pdf(
    restaurant_name: str,
    ssid: str,
    wifi_password: str,
    menu_base_url: str,
    restaurant_id: str,
    num_tables: int,
    style: str = "luxury",
    primary_color: str = "#0a0804",
    accent_color: str = "#C9A84C",
    bg_type: str = "minimal",
    socials: dict = None,
    pexels_key: str = "",
    unsplash_key: str = "",
    pixabay_key: str = "",
    photo_query: str = "",
) -> bytes:
    """
    🏭 توليد PDF الشيفالي — صفحة واحدة (10.5×34cm) لكل طاولة

    الهندسة الرياضية:
      • الواجهة العلوية (المنيو): y=192mm → y=340mm  | مقلوبة 180°
      • القاعدة (فراغ تلقائي):   y=148mm → y=192mm  | 4.4cm فارغ
      • الواجهة السفلية (WiFi):  y=0     → y=148mm  | مقادة 0°
    """
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(_W, _H))

    for table_num in range(1, num_tables + 1):
        # بناء رابط الطاولة
        if "?" not in menu_base_url:
            menu_url = f"{menu_base_url}?table={table_num}"
        else:
            menu_url = f"{menu_base_url}&table={table_num}"

        # توليد صورتي الواجهتين (A5 landscape)
        menu_img_raw, wifi_img_raw = generate_table_card(
            restaurant_name=restaurant_name,
            ssid=ssid,
            wifi_password=wifi_password,
            table_number=table_num,
            menu_url=menu_url,
            style=style,
            primary_color_hex=primary_color,
            accent_color_hex=accent_color,
            bg_type=bg_type,
            socials=socials or {},
            pexels_key=pexels_key,
            unsplash_key=unsplash_key,
            pixabay_key=pixabay_key,
            photo_query=photo_query or restaurant_name,
        )

        # تحويل الصور إلى portrait (قص المنتصف 620×874)
        menu_portrait = _crop_to_panel(menu_img_raw)
        wifi_portrait  = _crop_to_panel(wifi_img_raw)

        # ── الواجهة العلوية: المنيو مقلوبة 180° ────────────────────
        # الهدف: عند طي الشيفالي تكون قابلة للقراءة من الناحية الأولى
        menu_flipped = menu_portrait.rotate(180)
        c.drawImage(
            _img_to_reader(menu_flipped),
            x=0, y=_MENU_Y,            # من 19.2cm إلى 34cm
            width=_W, height=_PANEL_H,
            preserveAspectRatio=False,  # القياس محسوب رياضياً — نملأ كاملاً
        )

        # ── الواجهة السفلية: WiFi مقادة 0° ─────────────────────────
        c.drawImage(
            _img_to_reader(wifi_portrait),
            x=0, y=_WIFI_Y,            # من 0 إلى 14.8cm
            width=_W, height=_PANEL_H,
            preserveAspectRatio=False,
        )

        # ── القاعدة (4.4cm) ─────────────────────────────────────────
        # تبقى فارغة تلقائياً: الفراغ بين y=148mm و y=192mm
        # لا يحتاج لأي كود — المطبعي يستعملها للقص (Massicot)

        if table_num < num_tables:
            c.showPage()

    c.save()
    pdf_buf.seek(0)
    return pdf_buf.read()


def generate_single_table_preview(
    restaurant_name, ssid, wifi_password, menu_base_url,
    restaurant_id, table_num=1, style="luxury",
    primary_color="#0a0804", accent_color="#C9A84C",
    bg_type="minimal", socials=None,
    pexels_key="", unsplash_key="", pixabay_key="", photo_query=""
) -> tuple:
    """
    معاينة طاولة واحدة للـ Dashboard
    يرجع (menu_img, wifi_img) landscape للعرض في الواجهة
    """
    if "?" not in menu_base_url:
        menu_url = f"{menu_base_url}?table={table_num}"
    else:
        menu_url = f"{menu_base_url}&table={table_num}"

    return generate_table_card(
        restaurant_name=restaurant_name,
        ssid=ssid,
        wifi_password=wifi_password,
        table_number=table_num,
        menu_url=menu_url,
        style=style,
        primary_color_hex=primary_color,
        accent_color_hex=accent_color,
        bg_type=bg_type,
        socials=socials or {},
        pexels_key=pexels_key,
        unsplash_key=unsplash_key,
        pixabay_key=pixabay_key,
        photo_query=photo_query or restaurant_name,
    )
