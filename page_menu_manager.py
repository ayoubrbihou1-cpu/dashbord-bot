"""
🍽️ page_menu_manager.py — إدارة قائمة الطعام لكل مطعم
✅ عرض + إضافة + تعديل + حذف الأكلات
✅ كل مطعم له شيت خاص به — النظام يميز تلقائياً
"""
import streamlit as st
import gspread
import json
import os
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")

TABS = ["الأطباق الرئيسية","المقبلات","الحلويات","المشروبات"]
HEADERS = ["name","name_fr","name_en","price","description","available","image_url","image_credit"]

def _gs():
    if SA_JSON_CONTENT:
        c = Credentials.from_service_account_info(json.loads(SA_JSON_CONTENT), scopes=SCOPES)
    else:
        c = Credentials.from_service_account_file(SA_JSON_PATH, scopes=SCOPES)
    return gspread.authorize(c)

def _get_ws(sheet_id: str, tab: str):
    return _gs().open_by_key(sheet_id).worksheet(tab)

def load_items(sheet_id: str, tab: str) -> list:
    """تحميل أكلات tab معين"""
    try:
        ws = _get_ws(sheet_id, tab)
        all_vals = ws.get_all_values()
        if len(all_vals) < 2:
            return []
        headers = all_vals[0]
        items = []
        for i, row in enumerate(all_vals[1:], start=2):
            if not any(cell.strip() for cell in row):
                continue
            padded = row + [''] * (len(headers) - len(row))
            item = dict(zip(headers, padded))
            item["_row"] = i
            items.append(item)
        return items
    except Exception as e:
        st.error(f"❌ تحميل القائمة: {e}")
        return []

def add_item(sheet_id: str, tab: str, data: dict) -> bool:
    try:
        ws = _get_ws(sheet_id, tab)
        headers = ws.row_values(1)
        if not headers:
            ws.append_row(HEADERS)
            headers = HEADERS
        row = [data.get(h, "") for h in headers]
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"❌ إضافة أكلة: {e}")
        return False

def update_item(sheet_id: str, tab: str, row_num: int, data: dict) -> bool:
    try:
        ws = _get_ws(sheet_id, tab)
        headers = ws.row_values(1)
        for col_idx, h in enumerate(headers, start=1):
            if h in data:
                ws.update_cell(row_num, col_idx, data[h])
        return True
    except Exception as e:
        st.error(f"❌ تحديث الأكلة: {e}")
        return False

def delete_item(sheet_id: str, tab: str, row_num: int) -> bool:
    try:
        ws = _get_ws(sheet_id, tab)
        ws.delete_rows(row_num)
        return True
    except Exception as e:
        st.error(f"❌ حذف الأكلة: {e}")
        return False

def toggle_available(sheet_id: str, tab: str, row_num: int, current: str) -> bool:
    new_val = "FALSE" if current.upper() == "TRUE" else "TRUE"
    return update_item(sheet_id, tab, row_num, {"available": new_val})


# ══════════════════════════════════════════════════════════
# الصفحة الرئيسية
# ══════════════════════════════════════════════════════════
def page_menu_manager(restaurants: list):
    st.markdown("## 🍽️ إدارة قائمة الطعام")

    if not restaurants:
        st.info("📭 أضف مطعماً أولاً من صفحة 🚀 إضافة مطعم")
        return

    # ── شرح كيف يعمل النظام ─────────────────────────────
    with st.expander("ℹ️ كيف يعمل النظام؟"):
        st.markdown("""
        **كل مطعم له Google Sheet خاص به:**
        ```
        مطعم 1 (محمد) → Sheet_ID_1 → قائمته الخاصة
        مطعم 2 (علي)  → Sheet_ID_2 → قائمته الخاصة
        مطعم 3 (سارة) → Sheet_ID_3 → قائمته الخاصة
        ```
        - عندما يفتح الزبون `?rest_id=1` → يقرأ من Sheet مطعم محمد فقط
        - عندما يفتح `?rest_id=2` → يقرأ من Sheet مطعم علي فقط
        - **لا يختلطان أبداً ✅**

        **الصور:** أضف رابط الصورة في عمود `image_url` أو استخدم صفحة **🖼️ صور الأكلات**
        """)

    # ── اختيار المطعم ───────────────────────────────────
    c1, c2 = st.columns([2, 1])
    with c1:
        opts = {f"#{r.get('restaurant_id','?')} — {r.get('name','مطعم')}": r for r in restaurants}
        sel  = st.selectbox("🏪 اختر المطعم", list(opts.keys()), key="mm_rest_sel")
        rest = opts[sel]
        sheet_id = rest.get("sheet_id","")
        rid      = rest.get("restaurant_id","")

    with c2:
        # معلومات المطعم
        st.markdown(f"""
        <div style="background:#111;border:1px solid #C9A84C33;border-radius:10px;padding:.8rem;margin-top:1.6rem">
          <div style="color:#C9A84C;font-size:.8rem;font-weight:700">#{rid} — {rest.get('name','')}</div>
          <div style="color:#555;font-size:.7rem;margin-top:.3rem">📶 {rest.get('wifi_ssid','')}</div>
          <div style="color:#333;font-size:.65rem;margin-top:.2rem">Sheet: {sheet_id[:20]}...</div>
        </div>
        """, unsafe_allow_html=True)

    if not sheet_id:
        st.error("❌ هذا المطعم ليس له Sheet ID")
        return

    # ── اختيار الصنف ────────────────────────────────────
    tab_sel = st.radio("📂 الصنف", TABS, horizontal=True, key="mm_tab_sel")

    st.markdown("---")

    # ── تبويبان: عرض + إضافة ────────────────────────────
    view_tab, add_tab, import_tab = st.tabs(["📋 عرض وتعديل", "➕ إضافة أكلة جديدة", "📤 استيراد سريع"])

    # ══ عرض وتعديل ════════════════════════════════════════
    with view_tab:
        if st.button("🔄 تحديث القائمة", key="mm_refresh"):
            st.cache_data.clear()

        items = load_items(sheet_id, tab_sel)

        if not items:
            st.info(f"📭 لا توجد أكلات في '{tab_sel}' بعد — أضف من التبويب التالي")
        else:
            st.markdown(f"**{len(items)} أكلة في {tab_sel}**")

            for item in items:
                row_num = item.get("_row", 0)
                name    = item.get("name","")
                price   = item.get("price","0")
                avail   = item.get("available","TRUE")
                img_url = item.get("image_url","")
                desc    = item.get("description","")
                is_avail = avail.upper() == "TRUE"

                avail_color = "#69f0ae" if is_avail else "#ef9a9a"
                avail_label = "✅ متوفر" if is_avail else "❌ غير متوفر"

                with st.expander(f"{'✅' if is_avail else '❌'} {name} — {price} درهم"):
                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        new_name  = st.text_input("🍽️ الاسم بالعربية", name,
                                                   key=f"name_{row_num}")
                        new_name_fr = st.text_input("🇫🇷 بالفرنسية",
                                                     item.get("name_fr",""),
                                                     key=f"fr_{row_num}")
                        new_desc  = st.text_input("📝 الوصف", desc,
                                                   key=f"desc_{row_num}")
                    with col2:
                        new_price = st.number_input("💰 السعر (درهم)",
                                                     value=float(price) if str(price).replace('.','').isdigit() else 0.0,
                                                     min_value=0.0, step=5.0,
                                                     key=f"price_{row_num}")
                        new_img   = st.text_input("🖼️ رابط الصورة",
                                                   img_url,
                                                   key=f"img_{row_num}")
                        if new_img:
                            st.image(new_img, width=120)

                    with col3:
                        st.markdown(f'<div style="margin-top:1.5rem;color:{avail_color};font-weight:700">{avail_label}</div>',
                                    unsafe_allow_html=True)

                        # تبديل التوفر
                        if st.button("🔄 تبديل", key=f"tog_{row_num}"):
                            if toggle_available(sheet_id, tab_sel, row_num, avail):
                                st.success("✅ تم"); st.rerun()

                        # حفظ التعديلات
                        if st.button("💾 حفظ", key=f"save_{row_num}"):
                            ok = update_item(sheet_id, tab_sel, row_num, {
                                "name":        new_name,
                                "name_fr":     new_name_fr,
                                "price":       str(new_price),
                                "description": new_desc,
                                "image_url":   new_img,
                            })
                            if ok: st.success("✅ تم الحفظ"); st.rerun()

                        # حذف
                        if st.button("🗑️ حذف", key=f"del_{row_num}"):
                            if delete_item(sheet_id, tab_sel, row_num):
                                st.success("🗑️ تم الحذف"); st.rerun()

    # ══ إضافة أكلة ════════════════════════════════════════
    with add_tab:
        st.markdown(f"### ➕ إضافة أكلة جديدة في **{tab_sel}**")
        st.markdown(f'<div style="background:#0a0a0a;border:1px solid #C9A84C33;border-radius:10px;padding:1rem;margin-bottom:1rem"><b style="color:#C9A84C">المطعم:</b> {rest.get("name","")} &nbsp;|&nbsp; <b style="color:#C9A84C">الصنف:</b> {tab_sel}</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            n_name    = st.text_input("🍽️ الاسم بالعربية *", key="add_name",
                                       placeholder="طاجين دجاج")
            n_name_fr = st.text_input("🇫🇷 بالفرنسية", key="add_fr",
                                       placeholder="Tajine Poulet")
            n_name_en = st.text_input("🇬🇧 بالإنجليزية", key="add_en",
                                       placeholder="Chicken Tagine")
            n_desc    = st.text_area("📝 الوصف", key="add_desc",
                                      placeholder="وصف مختصر للأكلة", height=80)
        with c2:
            n_price = st.number_input("💰 السعر (درهم) *", min_value=0.0,
                                       step=5.0, key="add_price")
            n_avail = st.selectbox("📦 التوفر", ["TRUE","FALSE"],
                                    key="add_avail")
            n_img   = st.text_input("🖼️ رابط الصورة (اختياري)", key="add_img",
                                     placeholder="https://...")
            if n_img:
                st.image(n_img, width=150, caption="معاينة الصورة")

        if st.button("➕ إضافة للقائمة", use_container_width=True, key="btn_add_item"):
            if not n_name.strip():
                st.error("❌ الاسم مطلوب")
            elif n_price <= 0:
                st.error("❌ أدخل سعراً صحيحاً")
            else:
                ok = add_item(sheet_id, tab_sel, {
                    "name":        n_name.strip(),
                    "name_fr":     n_name_fr.strip(),
                    "name_en":     n_name_en.strip(),
                    "price":       str(n_price),
                    "description": n_desc.strip(),
                    "available":   n_avail,
                    "image_url":   n_img.strip(),
                    "image_credit": ""
                })
                if ok:
                    st.success(f"✅ تمت إضافة '{n_name}' بسعر {n_price} درهم")
                    st.rerun()

    # ══ استيراد سريع ══════════════════════════════════════
    with import_tab:
        st.markdown("### 📤 استيراد سريع — الصق قائمتك")
        st.markdown("""
        <div style="background:#0a1a0a;border:1px solid #C9A84C22;border-radius:8px;padding:.8rem;font-size:.8rem;color:#888;margin-bottom:.8rem">
        الصيغة المقبولة — سطر لكل أكلة:<br>
        <code style="color:#C9A84C">اسم الأكلة | السعر | الوصف (اختياري)</code><br><br>
        مثال:<br>
        <code style="color:#69f0ae">طاجين دجاج | 85 | تقليدي بالزيتون</code><br>
        <code style="color:#69f0ae">كسكس مغربي | 70</code><br>
        <code style="color:#69f0ae">سلطة مغربية | 30 | طازج يومياً</code>
        </div>
        """, unsafe_allow_html=True)

        bulk_text = st.text_area("📝 الصق هنا", height=200, key="bulk_import",
                                  placeholder="طاجين دجاج | 85 | بالزيتون\nكسكس مغربي | 70\n...")

        if st.button("📤 استيراد", use_container_width=True, key="btn_bulk"):
            if not bulk_text.strip():
                st.warning("الحقل فارغ")
            else:
                lines = [l.strip() for l in bulk_text.split("\n") if l.strip()]
                added = 0; errors = []
                for line in lines:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 2:
                        errors.append(f"⚠️ تجاهلت: {line[:40]}")
                        continue
                    name_  = parts[0]
                    price_ = parts[1].replace("درهم","").replace("دراهم","").strip()
                    desc_  = parts[2] if len(parts) > 2 else ""
                    if not price_.replace(".","").isdigit():
                        errors.append(f"⚠️ سعر غير صحيح: {line[:40]}")
                        continue
                    ok = add_item(sheet_id, tab_sel, {
                        "name": name_, "name_fr": "", "name_en": "",
                        "price": price_, "description": desc_,
                        "available": "TRUE", "image_url": "", "image_credit": ""
                    })
                    if ok: added += 1

                if added > 0:
                    st.success(f"✅ تمت إضافة {added} أكلة إلى '{tab_sel}'")
                for e in errors:
                    st.warning(e)
                if added > 0:
                    st.rerun()
