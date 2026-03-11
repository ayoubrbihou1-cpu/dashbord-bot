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
from gemini_helper import gemini_text, gemini_vision, gemini_available

load_dotenv()

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")

TABS = ["الأطباق الرئيسية","المقبلات","الحلويات","المشروبات"]

# ══════════════════════════════════════════════════════════
# 🌍 ترجمة تلقائية للأسماء
# ══════════════════════════════════════════════════════════
# Gemini key is read inside auto_translate()
FOOD_DICT = {
    # أكلات مغربية شائعة
    "طاجين دجاج":  ("Tajine Poulet",       "Chicken Tagine"),
    "طاجين لحم":   ("Tajine Viande",        "Beef Tagine"),
    "طاجين":       ("Tajine",               "Tagine"),
    "كسكس مغربي":  ("Couscous Marocain",    "Moroccan Couscous"),
    "كسكس":        ("Couscous",             "Couscous"),
    "حريرة":       ("Harira",               "Harira Soup"),
    "بسطيلة":      ("Pastilla",             "Pastilla"),
    "بريوات":      ("Briouats",             "Briouats"),
    "مشوي مختلط":  ("Grillade Mixte",       "Mixed Grill"),
    "دجاج مشوي":   ("Poulet Grillé",        "Grilled Chicken"),
    "سمك مشوي":    ("Poisson Grillé",       "Grilled Fish"),
    "سمك":         ("Poisson",              "Fish"),
    "سلطة مغربية": ("Salade Marocaine",     "Moroccan Salad"),
    "سلطة":        ("Salade",               "Salad"),
    "شوربة":       ("Soupe",                "Soup"),
    "مرق":         ("Bouillon",             "Broth"),
    "أرز":         ("Riz",                  "Rice"),
    "بيتزا":       ("Pizza",                "Pizza"),
    "برغر":        ("Burger",               "Burger"),
    "ساندويش":     ("Sandwich",             "Sandwich"),
    "باستا":       ("Pâtes",               "Pasta"),
    "بسطيلة حلوة": ("Pastilla Sucrée",      "Sweet Pastilla"),
    "شباكية":      ("Chebakia",             "Chebakia"),
    "حلوى مغربية": ("Pâtisserie Marocaine", "Moroccan Pastry"),
    "كعب الغزال":  ("Cornes de Gazelle",    "Gazelle Horns"),
    "آيس كريم":    ("Glace",               "Ice Cream"),
    "تارت":        ("Tarte",                "Tart"),
    "كيك":         ("Gâteau",              "Cake"),
    "أتاي بالنعناع":("Thé à la Menthe",    "Mint Tea"),
    "أتاي":        ("Thé Marocain",         "Moroccan Tea"),
    "شاي":         ("Thé",                 "Tea"),
    "قهوة":        ("Café",                "Coffee"),
    "عصير برتقال": ("Jus d'Orange",        "Orange Juice"),
    "عصير":        ("Jus",                 "Juice"),
    "ماء":         ("Eau",                 "Water"),
    "كوكا":        ("Coca-Cola",           "Coca-Cola"),
    "سودا":        ("Soda",                "Soda"),
    "لبن":         ("Lait",                "Milk"),
    "لبن رائب":    ("Lben",                "Buttermilk"),
    "دجاج":        ("Poulet",              "Chicken"),
    "لحم":         ("Viande",              "Meat"),
    "لحم مفروم":   ("Viande Hachée",       "Minced Meat"),
    "كفتة":        ("Kefta",               "Kefta"),
    "مقبلات":      ("Entrées",             "Starters"),
    "فطائر":       ("Feuilletés",          "Pastries"),
}

def auto_translate(arabic_name: str) -> tuple:
    """
    يترجم اسم الأكلة للفرنسية والإنجليزية
    1. قاموس محلي أولاً (سريع)
    2. OpenAI إذا متوفر
    3. إرجاع فارغ كـ fallback
    """
    name = arabic_name.strip()
    # قاموس محلي
    for ar, (fr, en) in FOOD_DICT.items():
        if ar in name or name == ar:
            return fr, en
    # ✅ Gemini مع دوران تلقائي على 4 مفاتيح
    try:
        prompt = f"Translate this Moroccan/Arabic food name to French and English.\nReply ONLY in this format: French | English\nFood: {name}"
        txt = gemini_text(prompt, max_tokens=40, temperature=0)
        parts = [p.strip() for p in txt.split("|")]
        if len(parts) == 2:
            return parts[0], parts[1]
    except Exception as e:
        pass
    return "", ""

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
    view_tab, add_tab, import_tab = st.tabs(["📋 عرض وتعديل", "➕ إضافة أكلة جديدة", "📸 استيراد من صورة"])

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

        # ── إدخال الاسم + ترجمة تلقائية ──────────────────
        c0 = st.columns([3, 1])
        with c0[0]:
            n_name = st.text_input("🍽️ الاسم بالعربية *", key="add_name",
                                    placeholder="طاجين دجاج")
        with c0[1]:
            st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
            if st.button("🌍 ترجم تلقائياً", key="btn_translate", use_container_width=True):
                if n_name.strip():
                    fr, en = auto_translate(n_name.strip())
                    st.session_state["_auto_fr"] = fr
                    st.session_state["_auto_en"] = en
                    if fr or en:
                        st.success(f"🇫🇷 {fr or '?'} | 🇬🇧 {en or '?'}")
                    else:
                        st.warning("⚠️ أضف اسم الأكلة أولاً أو أدخل الترجمة يدوياً")

        c1, c2 = st.columns(2)
        with c1:
            n_name_fr = st.text_input("🇫🇷 بالفرنسية", key="add_fr",
                                       value=st.session_state.get("_auto_fr",""),
                                       placeholder="Tajine Poulet")
            n_name_en = st.text_input("🇬🇧 بالإنجليزية", key="add_en",
                                       value=st.session_state.get("_auto_en",""),
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

    # ══ استيراد من صورة ══════════════════════════════════
    with import_tab:
        _render_image_import_tab(sheet_id, tab_sel, rest)

def _render_image_import_tab(sheet_id, tab_sel, rest):
    """تبويب استيراد المينيو من صورة باستخدام Gemini"""
    import base64

    ok, msg = gemini_available()

    st.markdown("### 📸 استيراد المينيو من صورة")
    st.markdown("""
    <div style="background:#0a1a0a;border:1px solid #C9A84C33;border-radius:10px;padding:1rem;margin-bottom:1rem;font-size:.85rem;color:#888;line-height:1.8">
    📌 <b style="color:#C9A84C">كيف يعمل؟</b><br>
    1. ارفع صورة المينيو (ورقي أو صورة هاتف)<br>
    2. الذكاء الاصطناعي يستخرج الأكلات والأسعار تلقائياً<br>
    3. راجع النتائج وعدّل إذا لزم<br>
    4. اضغط <b style="color:#69f0ae">حفظ في Google Sheet</b> ← تظهر فوراً في المينيو
    </div>
    """, unsafe_allow_html=True)

    if not ok:
        st.error(f"❌ {msg} — أضف GEMINI_API_KEY في Secrets")
        return
    st.markdown(f'<div style="color:#69f0ae;font-size:.8rem">🤖 Gemini: {msg} — دوران تلقائي عند نفاذ الحصة</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "📷 ارفع صورة المينيو",
        type=["jpg", "jpeg", "png", "webp"],
        key="menu_img_upload",
        help="صورة واضحة للمينيو الورقي أو صورة من الهاتف"
    )

    target_tab = st.selectbox(
        "📂 أضف الأكلات إلى صنف:",
        ["كل الأصناف تلقائياً", "الأطباق الرئيسية", "المقبلات", "الحلويات", "المشروبات"],
        key="img_target_tab"
    )

    if uploaded:
        col_img, col_btn = st.columns([2, 1])
        with col_img:
            st.image(uploaded, caption="الصورة المرفوعة", use_container_width=True)
        with col_btn:
            st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
            analyze_btn = st.button("🤖 تحليل بالذكاء الاصطناعي",
                                     use_container_width=True,
                                     key="btn_analyze_menu")

        if analyze_btn or st.session_state.get("_analyzed_items"):
            if analyze_btn:
                with st.spinner("🤖 جاري تحليل الصورة... قد يستغرق 10-20 ثانية"):
                    try:
                        img_bytes = uploaded.read()
                        img_b64 = base64.b64encode(img_bytes).decode()
                        mime = uploaded.type or "image/jpeg"

                        prompt = """أنت خبير في قراءة قوائم طعام المطاعم المغربية.
انظر لهذه الصورة واستخرج كل الأكلات والأسعار.

أجب فقط بـ JSON بهذا الشكل بدون أي كلام آخر:
{
  "items": [
    {
      "name": "اسم الأكلة بالعربية",
      "price": 85,
      "description": "وصف مختصر إن وجد",
      "category": "الأطباق الرئيسية"
    }
  ]
}

الأصناف المتاحة فقط: الأطباق الرئيسية, المقبلات, الحلويات, المشروبات
إذا لم تجد صنف واضح ضعه في الأطباق الرئيسية
السعر يجب أن يكون رقم فقط بدون درهم
إذا لم يكن هناك سعر واضح ضع 0"""

                        raw = gemini_vision(prompt, img_b64, mime, max_tokens=2000, temperature=0)
                        if "```json" in raw:
                            raw = raw.split("```json")[1].split("```")[0].strip()
                        elif "```" in raw:
                            raw = raw.split("```")[1].split("```")[0].strip()
                        parsed = json.loads(raw)
                        items_found = parsed.get("items", [])
                        st.session_state["_analyzed_items"] = items_found
                        st.session_state["_analyzed_edits"] = {i: dict(item) for i, item in enumerate(items_found)}
                        st.success(f"✅ تم استخراج {len(items_found)} أكلة!")
                    except json.JSONDecodeError:
                        st.error("❌ الذكاء الاصطناعي لم يتمكن من قراءة الصورة — جرب صورة أوضح")
                        return
                    except RuntimeError as e:
                        st.error(f"❌ {e}")
                        return
                    except Exception as e:
                        st.error(f"❌ خطأ: {e}")
                        return

            items_found = st.session_state.get("_analyzed_items", [])
            edits = st.session_state.get("_analyzed_edits", {})

            if items_found:
                st.markdown(f"### ✏️ راجع وعدّل ({len(items_found)} أكلة مستخرجة)")

                for i, item in enumerate(items_found):
                    with st.expander(f"🍽️ {item.get('name','؟')} — {item.get('price',0)} درهم", expanded=False):
                        c1, c2, c3 = st.columns([2, 1, 1])
                        with c1:
                            new_name = st.text_input("الاسم", value=edits[i].get("name",""), key=f"ai_name_{i}")
                            edits[i]["name"] = new_name
                            new_desc = st.text_input("الوصف", value=edits[i].get("description",""), key=f"ai_desc_{i}")
                            edits[i]["description"] = new_desc
                        with c2:
                            new_price = st.number_input("السعر", value=float(edits[i].get("price",0) or 0),
                                                         min_value=0.0, step=5.0, key=f"ai_price_{i}")
                            edits[i]["price"] = new_price
                        with c3:
                            cats = ["الأطباق الرئيسية","المقبلات","الحلويات","المشروبات"]
                            cur_cat = edits[i].get("category","الأطباق الرئيسية")
                            if cur_cat not in cats: cur_cat = "الأطباق الرئيسية"
                            new_cat = st.selectbox("الصنف", cats, index=cats.index(cur_cat), key=f"ai_cat_{i}")
                            edits[i]["category"] = new_cat

                st.session_state["_analyzed_edits"] = edits
                st.markdown("---")

                col_save, col_clear = st.columns([3, 1])
                with col_save:
                    if st.button("💾 حفظ كل الأكلات في Google Sheet ✅",
                                  use_container_width=True, key="btn_save_ai_items"):
                        added = 0
                        for i, item_data in edits.items():
                            if not item_data.get("name","").strip():
                                continue
                            fr, en = auto_translate(item_data["name"])
                            save_tab = item_data.get("category","الأطباق الرئيسية")
                            if target_tab != "كل الأصناف تلقائياً":
                                save_tab = target_tab
                            ok = add_item(sheet_id, save_tab, {
                                "name":         item_data["name"].strip(),
                                "name_fr":      fr,
                                "name_en":      en,
                                "price":        str(int(item_data.get("price",0) or 0)),
                                "description":  item_data.get("description","").strip(),
                                "available":    "TRUE",
                                "image_url":    "",
                                "image_credit": ""
                            })
                            if ok: added += 1
                        if added > 0:
                            st.success(f"✅ تم حفظ {added} أكلة في Google Sheet! تظهر في المينيو فوراً 🎉")
                            st.session_state.pop("_analyzed_items", None)
                            st.session_state.pop("_analyzed_edits", None)
                            st.rerun()
                with col_clear:
                    if st.button("🗑️ مسح", key="btn_clear_ai"):
                        st.session_state.pop("_analyzed_items", None)
                        st.session_state.pop("_analyzed_edits", None)
                        st.rerun()

    st.markdown("---")
    st.markdown("### 📤 أو استيراد نصي سريع — الصق قائمتك")

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
