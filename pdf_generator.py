"""
📄 مولد PDF التلقائي — Table Tents
✅ إصلاح: استخدام ImageReader بدل BytesIO مباشرة مع reportlab
"""

import io
from PIL import Image
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader   # ✅ الإصلاح الرئيسي
from generative_design import generate_table_card


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
    🏭 توليد PDF كامل — صفحتان لكل طاولة
    الصفحة 1: QR المينيو | الصفحة 2: QR WiFi
    """
    # A5 landscape
    PAGE_W = 210 * mm
    PAGE_H = 148 * mm

    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(PAGE_W, PAGE_H))

    for table_num in range(1, num_tables + 1):
        menu_url = f"{menu_base_url}?rest_id={restaurant_id}&table={table_num}"

        # توليد الوجهين (menu_img أولاً، wifi_img ثانياً)
        menu_img, wifi_img = generate_table_card(
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

        # ── الصفحة 1: QR المينيو ──────────────────────────────
        menu_buf = io.BytesIO()
        menu_img.save(menu_buf, format="PNG")
        menu_buf.seek(0)
        menu_reader = ImageReader(menu_buf)   # ✅ ImageReader يحل المشكلة

        c.drawImage(
            menu_reader,
            x=0, y=0,
            width=PAGE_W, height=PAGE_H,
            preserveAspectRatio=True,
            anchor='c'
        )
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        # استخدام رقم الطاولة فقط في الـ footer (Helvetica لا يدعم العربية)
        c.drawString(5*mm, 4*mm, f"T{table_num} | Menu QR | #{table_num}")
        c.showPage()

        # ── الصفحة 2: QR WiFi ────────────────────────────────
        wifi_buf = io.BytesIO()
        wifi_img.save(wifi_buf, format="PNG")
        wifi_buf.seek(0)
        wifi_reader = ImageReader(wifi_buf)   # ✅

        c.drawImage(
            wifi_reader,
            x=0, y=0,
            width=PAGE_W, height=PAGE_H,
            preserveAspectRatio=True,
            anchor='c'
        )
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(5*mm, 4*mm, f"T{table_num} | WiFi QR | #{table_num}")

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
        accent_color_hex=accent_color,
        bg_type=bg_type,
        socials=socials or {},
        pexels_key=pexels_key,
        unsplash_key=unsplash_key,
        pixabay_key=pixabay_key,
        photo_query=photo_query or restaurant_name,
    )
