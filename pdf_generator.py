"""
📄 مولد PDF التلقائي — Table Tents
يولد PDF متعدد الصفحات (وجهان لكل طاولة)
"""

import io
from PIL import Image
from reportlab.lib.pagesizes import A5, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Image as RLImage, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from generative_design import generate_table_card, card_to_bytes


def pil_to_rl_image(pil_img: Image.Image, width_mm: float, height_mm: float):
    """تحويل Pillow Image لـ ReportLab Image"""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG", dpi=(150,150))
    buf.seek(0)
    return RLImage(buf, width=width_mm*mm, height=height_mm*mm)


def generate_table_tents_pdf(
    restaurant_name: str,
    ssid: str,
    wifi_password: str,
    menu_base_url: str,
    restaurant_id: str,
    num_tables: int,
    style: str = "luxury",
    primary_color: str = "#0a0804",
    accent_color: str = "#C9A84C"
) -> bytes:
    """
    🏭 توليد PDF كامل — صفحتان لكل طاولة

    Args:
        restaurant_name: اسم المطعم
        ssid: اسم شبكة WiFi
        wifi_password: كلمة مرور WiFi
        menu_base_url: رابط الفرونتاند (بدون بارامترات)
        restaurant_id: رقم المطعم
        num_tables: عدد الطاولات
        style: modern | luxury | classic
        primary_color: اللون الأساسي hex
        accent_color: لون التمييز hex

    Returns:
        bytes — محتوى PDF جاهز للطباعة
    """

    # A5 landscape
    PAGE_W = 210 * mm   # عرض A5 بالـ landscape
    PAGE_H = 148 * mm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))

    total_pages = num_tables * 2

    for table_num in range(1, num_tables + 1):
        # رابط ديناميكي فريد لكل طاولة
        menu_url = f"{menu_base_url}?rest_id={restaurant_id}&table={table_num}"

        # توليد الوجهين
        wifi_img, menu_img = generate_table_card(
            restaurant_name=restaurant_name,
            ssid=ssid,
            wifi_password=wifi_password,
            table_number=table_num,
            menu_url=menu_url,
            style=style,
            primary_color_hex=primary_color,
            accent_color_hex=accent_color
        )

        # ── الصفحة A: WiFi ──
        wifi_buf = io.BytesIO()
        wifi_img.save(wifi_buf, format="PNG", dpi=(150,150))
        wifi_buf.seek(0)

        c.drawImage(
            wifi_buf,
            x=0, y=0,
            width=PAGE_W, height=PAGE_H,
            preserveAspectRatio=True,
            anchor='c'
        )

        # رقم صفحة صغير
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(5*mm, 4*mm, f"T{table_num} | WiFi | {restaurant_name}")

        c.showPage()  # صفحة جديدة

        # ── الصفحة B: Menu QR ──
        menu_buf = io.BytesIO()
        menu_img.save(menu_buf, format="PNG", dpi=(150,150))
        menu_buf.seek(0)

        c.drawImage(
            menu_buf,
            x=0, y=0,
            width=PAGE_W, height=PAGE_H,
            preserveAspectRatio=True,
            anchor='c'
        )

        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(5*mm, 4*mm, f"T{table_num} | Menu QR | {restaurant_name} | {menu_url}")

        if table_num < num_tables:
            c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


def generate_single_table_preview(
    restaurant_name, ssid, wifi_password, menu_base_url,
    restaurant_id, table_num=1, style="luxury",
    primary_color="#0a0804", accent_color="#C9A84C"
) -> tuple:
    """معاينة طاولة واحدة — للـ Dashboard"""
    menu_url = f"{menu_base_url}?rest_id={restaurant_id}&table={table_num}"
    return generate_table_card(
        restaurant_name=restaurant_name,
        ssid=ssid,
        wifi_password=wifi_password,
        table_number=table_num,
        menu_url=menu_url,
        style=style,
        primary_color_hex=primary_color,
        accent_color_hex=accent_color
    )
