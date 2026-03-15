"""
🍽️ page_menu_manager.py — إدارة قائمة الطعام لكل مطعم
✅ عرض + إضافة + تعديل + حذف الأكلات
✅ كل مطعم له شيت خاص به — النظام يميز تلقائياً
"""
import streamlit as st
import logging
log = logging.getLogger(__name__)
import gspread
import json
import os
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from gemini_helper import gemini_text, gemini_vision, gemini_available
from groq_helper import translate_batch_groq, translate_single_groq, groq_available, groq_vision, groq_vision_available
import requests as _requests

load_dotenv()

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")
ROUTER_BASE_URL = os.getenv("ROUTER_BASE_URL","https://restaurant-qr-saas.onrender.com")
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD","admin_fes_2026")

def _refresh_api_cache(restaurant_id: str):
    """✅ يمسح cache المنيو في الـ API — الصور تظهر فوراً بعد الحفظ"""
    try:
        url = f"{ROUTER_BASE_URL}/cache/refresh/{restaurant_id}"
        _requests.post(url, timeout=8,
                       headers={"X-Admin-Key": ADMIN_PASSWORD})
    except Exception:
        pass  # لا نوقف العملية إذا فشل الـ cache refresh

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

def _detect_language(name: str) -> str:
    """يكتشف لغة الاسم: arabic / french / english"""
    arabic_chars = sum(1 for c in name if '؀' <= c <= 'ۿ')
    if arabic_chars > 1:
        return "arabic"
    # كلمات فرنسية شائعة في المينيو
    fr_words = ["tajine","couscous","poulet","viande","salade","soupe","tarte","mousse",
                "sorbet","creme","gateau","briouats","pastilla","sardine","filet","plat",
                "omelette","aubergine","courgette","brochette","merguez","harira","seffa",
                "tanjia","rafissa","bastilla","de","du","au","aux","les","avec","sans"]
    name_l = name.lower()
    if any(w in name_l for w in fr_words):
        return "french"
    return "english"


def auto_translate(arabic_name: str) -> tuple:
    """
    يترجم اسم الأكلة للفرنسية والإنجليزية
    يدعم العربية والفرنسية والإنجليزية
    """
    name = arabic_name.strip()
    # قاموس محلي للعربية
    for ar, (fr, en) in FOOD_DICT.items():
        if ar in name or name == ar:
            return fr, en
    # Gemini للترجمة مع دوران تلقائي
    try:
        lang = _detect_language(name)
        if lang == "arabic":
            prompt = f"Translate this Moroccan Arabic food name to French and English.\nReply ONLY: French | English\nFood: {name}"
        elif lang == "french":
            prompt = f"Translate this French food name to English. Also give the original French back.\nReply ONLY: French | English\nFood: {name}"
        else:
            prompt = f"This is an English food name. Translate it to French.\nReply ONLY: French | English\nFood: {name}"
        txt = gemini_text(prompt, max_tokens=60, temperature=0)
        parts = [p.strip() for p in txt.split("|")]
        if len(parts) == 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return "", ""


def translate_three_languages(name: str) -> tuple:
    """
    يترجم اسم الأكلة للغات الثلاث: عربي | فرنسي | إنجليزي
    يكتشف لغة الاسم تلقائياً ويترجم للباقيتين
    يرجع: (name_ar, name_fr, name_en)
    """
    name = name.strip()
    if not name:
        return "", "", ""
    try:
        lang = _detect_language(name)
        prompt = (
            f'This is a Moroccan restaurant dish name: "{name}"\n'
            f'Detected language: {lang}\n\n'
            "Translate it to all 3 languages. Reply ONLY in this exact format:\n"
            "Arabic | French | English\n\n"
            "Rules:\n"
            "- Arabic: use Modern Standard Arabic or Moroccan Arabic\n"
            "- French: standard French used in Moroccan restaurants\n"
            "- English: clear English description\n"
            "- No extra text, just: Arabic | French | English"
        )

        txt = gemini_text(prompt, max_tokens=80, temperature=0)
        parts = [p.strip() for p in txt.split("|")]
        if len(parts) == 3:
            ar, fr, en = parts[0], parts[1], parts[2]
            # إذا كان الاسم الأصلي عربي — استخدمه مباشرة
            if lang == "arabic":
                ar = name
            elif lang == "french":
                fr = name
            elif lang == "english":
                en = name
            return ar, fr, en
    except Exception:
        pass
    # fallback — إذا فشل Gemini
    fr, en = auto_translate(name)
    lang = _detect_language(name)
    if lang == "arabic":
        return name, fr, en
    elif lang == "french":
        return "", name, en
    else:
        return "", fr, name

HEADERS = ["name","name_fr","name_en","price","description","available","image_url","image_credit"]


def translate_batch(names: list) -> list:
    """
    يترجم قائمة أسماء دفعة واحدة في استدعاء Gemini واحد فقط
    يرجع قائمة من (name_ar, name_fr, name_en) لكل اسم
    """
    if not names:
        return []
    try:
        # بناء قائمة الأسماء مرقمة
        numbered = "\n".join(f"{i+1}. {n}" for i, n in enumerate(names))
        prompt = (
            "You are a Moroccan restaurant menu translator.\n"
            "Translate each dish name below to Arabic, French, and English.\n"
            "Reply ONLY with a JSON array, no extra text:\n"
            '[{"ar":"...","fr":"...","en":"..."}]\n\n'
            f"Dishes:\n{numbered}"
        )
        txt = gemini_text(prompt, max_tokens=4000, temperature=0)
        # تنظيف JSON
        txt = txt.strip()
        if "```json" in txt:
            txt = txt.split("```json")[1].split("```")[0].strip()
        elif "```" in txt:
            txt = txt.split("```")[1].split("```")[0].strip()
        import json as _json
        txt = txt.strip()
        if "```json" in txt:
            txt = txt.split("```json")[1].split("```")[0].strip()
        elif "```" in txt:
            txt = txt.split("```")[1].split("```")[0].strip()
        start = txt.find("[")
        if start != -1:
            txt = txt[start:]
        # raw_decode لتجاهل أي نص بعد الـ JSON
        try:
            parsed, _ = _json.JSONDecoder().raw_decode(txt)
        except _json.JSONDecodeError:
            end = txt.rfind("]")
            if end != -1:
                txt = txt[:end+1]
            parsed = _json.loads(txt)
        result = []
        for i, item in enumerate(parsed):
            orig = names[i] if i < len(names) else ""
            lang = _detect_language(orig)
            ar = item.get("ar", "") or (orig if lang == "arabic" else "")
            fr = item.get("fr", "") or (orig if lang == "french" else "")
            en = item.get("en", "") or (orig if lang == "english" else "")
            result.append((ar, fr, en))
        return result
    except Exception as e:
        # fallback — إرجاع الاسم الأصلي بدون ترجمة
        result = []
        for name in names:
            lang = _detect_language(name)
            if lang == "arabic":
                result.append((name, "", ""))
            elif lang == "french":
                result.append(("", name, ""))
            else:
                result.append(("", "", name))
        return result

def _gs():
    if SA_JSON_CONTENT:
        c = Credentials.from_service_account_info(json.loads(SA_JSON_CONTENT), scopes=SCOPES)
    else:
        c = Credentials.from_service_account_file(SA_JSON_PATH, scopes=SCOPES)
    return gspread.authorize(c)

def _get_ws(sheet_id: str, tab: str):
    return _gs().open_by_key(sheet_id).worksheet(tab)

@st.cache_data(ttl=120)  # cache القائمة 2 دقيقة — يقلل طلبات Sheets API بـ 90%
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
    """إضافة أكلة واحدة"""
    return add_items_batch(sheet_id, tab, [data]) == 1


def add_items_batch(sheet_id: str, tab: str, items: list) -> int:
    """
    إضافة عدة أكلات دفعة واحدة — طلب واحد فقط لـ Google Sheets
    يرجع عدد الأكلات المضافة بنجاح
    """
    if not items:
        return 0
    try:
        ws = _get_ws(sheet_id, tab)
        headers = ws.row_values(1)
        if not headers:
            ws.append_row(HEADERS)
            headers = HEADERS

        rows = []
        for data in items:
            row = [data.get(h, "") for h in headers]
            rows.append(row)

        # كتابة كل الصفوف في طلب واحد بدل طلب لكل أكلة
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        return len(rows)
    except Exception as e:
        st.error(f"❌ إضافة الأكلات: {e}")
        return 0

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
            # ✅ مسح cache الـ API أيضاً حتى تظهر آخر التغييرات في المينيو
            _refresh_api_cache(rid)
            st.toast("✅ تم تحديث القائمة — الصور ستظهر فوراً في المينيو", icon="🔄")

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
                            if ok:
                                # ✅ مسح cache الـ API حتى تظهر الصورة فوراً في المينيو
                                if new_img.strip():
                                    _refresh_api_cache(rid)
                                st.success("✅ تم الحفظ"); st.rerun()

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
                # إذا لم يدخل المستخدم الترجمة يدوياً — يترجم تلقائياً
                groq_ok3, _ = groq_available()
                _ar3, _fr3, _en3 = (translate_single_groq(n_name.strip()) 
                    if groq_ok3 else translate_three_languages(n_name.strip()))
                final_fr = n_name_fr.strip() or _fr3
                final_en = n_name_en.strip() or _en3
                final_ar = _ar3 if _ar3 else n_name.strip()
                ok = add_item(sheet_id, tab_sel, {
                    "name":        final_ar,
                    "name_fr":     final_fr,
                    "name_en":     final_en,
                    "price":       str(n_price),
                    "description": n_desc.strip(),
                    "available":   n_avail,
                    "image_url":   n_img.strip(),
                    "image_credit": ""
                })
                if ok:
                    # ✅ مسح cache الـ API حتى تظهر الصورة فوراً في المينيو
                    if n_img.strip():
                        _refresh_api_cache(rid)
                    st.success(f"✅ تمت إضافة '{n_name}' بسعر {n_price} درهم")
                    st.rerun()

    # ══ استيراد من صورة ══════════════════════════════════
    with import_tab:
        _render_image_import_tab(sheet_id, tab_sel, rest, rid)

def _render_image_import_tab(sheet_id, tab_sel, rest, rid=""):
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
        "📷 ارفع ملف المينيو",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
        key="menu_img_upload",
        help="صورة JPG/PNG أو ملف PDF للمينيو"
    )

    target_tab = st.selectbox(
        "📂 أضف الأكلات إلى صنف:",
        ["كل الأصناف تلقائياً", "الأطباق الرئيسية", "المقبلات", "الحلويات", "المشروبات"],
        key="img_target_tab"
    )

    if uploaded:
        col_img, col_btn = st.columns([2, 1])
        with col_img:
            # عرض معاينة حسب نوع الملف
            if uploaded.type == "application/pdf":
                st.markdown(f"""
                <div style="background:#0a1a0a;border:1px solid #C9A84C33;border-radius:10px;
                     padding:1.5rem;text-align:center">
                  <div style="font-size:3rem">📄</div>
                  <div style="color:#C9A84C;font-weight:700;margin-top:.5rem">{uploaded.name}</div>
                  <div style="color:#555;font-size:.8rem;margin-top:.3rem">PDF — سيتم تحليل الصفحة الأولى</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.image(uploaded, caption="الصورة المرفوعة", use_container_width=True)
        with col_btn:
            st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
            analyze_btn = st.button("🤖 تحليل بالذكاء الاصطناعي",
                                     use_container_width=True,
                                     key="btn_analyze_menu")

        if analyze_btn or st.session_state.get("_analyzed_items"):
            if analyze_btn:
                with st.spinner("🤖 جاري تحليل الملف... قد يستغرق 10-30 ثانية"):
                    try:
                        file_bytes = uploaded.read()
                        mime = uploaded.type or "image/jpeg"

                        # تحويل PDF لصورة إذا لزم
                        if uploaded.type == "application/pdf" or uploaded.name.lower().endswith(".pdf"):
                            try:
                                import fitz  # PyMuPDF
                                pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
                                # تحليل كل الصفحات ودمجها في صورة واحدة طويلة
                                images_b64 = []
                                for page_num in range(min(pdf_doc.page_count, 4)):  # max 4 صفحات
                                    page = pdf_doc[page_num]
                                    mat = fitz.Matrix(2, 2)  # دقة عالية x2
                                    pix = page.get_pixmap(matrix=mat)
                                    images_b64.append(base64.b64encode(pix.tobytes("jpeg")).decode())
                                img_b64 = images_b64[0]  # الصفحة الأولى للتحليل الأساسي
                                mime = "image/jpeg"
                                st.info(f"📄 تم تحويل PDF ({pdf_doc.page_count} صفحة) — يتم تحليل الصفحة الأولى")
                            except ImportError:
                                st.error("❌ مكتبة PyMuPDF غير مثبتة — أضف 'pymupdf' في requirements.txt")
                                return
                            except Exception as e:
                                st.error(f"❌ خطأ في تحويل PDF: {e}")
                                return
                        else:
                            img_b64 = base64.b64encode(file_bytes).decode()

                        prompt = """You are an expert at reading restaurant menus. This menu may be in Arabic, French, or both.

Extract ALL dishes and their prices from this image.

Rules:
- Keep the dish name exactly as written in the menu (French or Arabic)
- price must be a number only (no currency symbol). If two numbers like "40,15" take the first: 40
- If no price found use 0
- category must be one of exactly: الأطباق الرئيسية, المقبلات, الحلويات, المشروبات
- Guess category from section headers (ENTREES=المقبلات, PLATS=الأطباق الرئيسية, DESSERTS=الحلويات, BOISSONS=المشروبات)
- description can be empty string

Reply ONLY with valid JSON, no extra text, no markdown, no code blocks:
{"items":[{"name":"dish name","price":40,"description":"","category":"الأطباق الرئيسية"}]}"""

                        # جرب Groq Vision أولاً (6 مفاتيح مجانية)
                        # إذا فشل → Gemini كـ fallback
                        groq_vis_ok, _ = groq_vision_available()
                        try:
                            if groq_vis_ok:
                                raw = groq_vision(prompt, img_b64, mime, max_tokens=4000)
                                st.info("⚡ تم التحليل بـ Groq Vision")
                            else:
                                raise RuntimeError("Groq غير متاح")
                        except Exception as _groq_err:
                            log.warning(f"Groq vision failed: {_groq_err} — falling back to Gemini")
                            raw = gemini_vision(prompt, img_b64, mime, max_tokens=4000, temperature=0)
                            st.info("🤖 تم التحليل بـ Gemini")

                        # تنظيف JSON من أي نص زائد
                        raw = raw.strip()
                        if "```json" in raw:
                            raw = raw.split("```json")[1].split("```")[0].strip()
                        elif "```" in raw:
                            raw = raw.split("```")[1].split("```")[0].strip()

                        # نحدد نوع الـ JSON: object أو array
                        first_char = ""
                        for ch in raw:
                            if ch in "{[":
                                first_char = ch
                                break

                        if first_char == "[":
                            # رجع array مباشرة — ابحث عنه
                            start = raw.find("[")
                            raw = raw[start:]
                            try:
                                items_found, _ = json.JSONDecoder().raw_decode(raw)
                            except json.JSONDecodeError:
                                end = raw.rfind("]")
                                items_found = json.loads(raw[:end+1] if end != -1 else raw)
                        else:
                            # رجع object — ابحث عنه
                            start = raw.find("{")
                            if start != -1:
                                raw = raw[start:]
                            try:
                                parsed, _ = json.JSONDecoder().raw_decode(raw)
                            except json.JSONDecodeError:
                                end = raw.rfind("}")
                                if end != -1:
                                    raw = raw[:end+1]
                                parsed = json.loads(raw)
                            # جرب كل المفاتيح الممكنة
                            items_found = (
                                parsed.get("items") or
                                parsed.get("dishes") or
                                parsed.get("menu") or
                                parsed.get("data") or
                                (list(parsed.values())[0] if parsed and isinstance(list(parsed.values())[0], list) else [])
                            )

                        # تأكد أن النتيجة list of dicts
                        if not isinstance(items_found, list):
                            items_found = []
                        items_found = [i for i in items_found if isinstance(i, dict) and i.get("name","").strip()]
                        st.session_state["_analyzed_items"] = items_found
                        st.session_state["_analyzed_edits"] = {i: dict(item) for i, item in enumerate(items_found)}
                        if items_found:
                            st.success(f"✅ تم استخراج {len(items_found)} أكلة!")
                        else:
                            st.warning("⚠️ لم يتم استخراج أي أكلة — رد الذكاء الاصطناعي:")
                            st.code(raw[:800])
                    except json.JSONDecodeError as e:
                        st.error(f"❌ خطأ في قراءة JSON: {e}")
                        st.code(raw[:500] if 'raw' in dir() else "لا يوجد رد")
                        return
                    except RuntimeError as e:
                        st.error(f"❌ {e}")
                        return
                    except Exception as e:
                        st.error(f"❌ خطأ غير متوقع: {type(e).__name__}: {e}")
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
                        with st.spinner("⏳ جاري الترجمة والحفظ..."):
                            from collections import defaultdict

                            # جمع كل الأسماء الصالحة
                            valid_items = [
                                (i, item_data)
                                for i, item_data in edits.items()
                                if item_data.get("name","").strip()
                            ]

                            # ترجمة كل الأسماء في استدعاء Gemini واحد فقط
                            names_list = [item_data["name"].strip() for _, item_data in valid_items]
                            # Groq للترجمة — أسرع وأوفر لـ Gemini
                            groq_ok, _ = groq_available()
                            if groq_ok:
                                translations = translate_batch_groq(names_list)
                            else:
                                translations = translate_batch(names_list)

                            # تجميع حسب الصنف
                            by_tab = defaultdict(list)
                            for idx2, (i, item_data) in enumerate(valid_items):
                                ar, fr, en = translations[idx2] if idx2 < len(translations) else ("","","")
                                main_name = ar if ar else item_data["name"].strip()
                                save_tab = item_data.get("category","الأطباق الرئيسية")
                                if target_tab != "كل الأصناف تلقائياً":
                                    save_tab = target_tab
                                by_tab[save_tab].append({
                                    "name":         main_name,
                                    "name_fr":      fr,
                                    "name_en":      en,
                                    "price":        str(int(item_data.get("price",0) or 0)),
                                    "description":  item_data.get("description","").strip(),
                                    "available":    "TRUE",
                                    "image_url":    "",
                                    "image_credit": ""
                                })

                            # حفظ كل صنف في طلب واحد فقط
                            added = 0
                            for tab_name, tab_items in by_tab.items():
                                n = add_items_batch(sheet_id, tab_name, tab_items)
                                added += n

                        if added > 0:
                            # ✅ مسح cache الـ API — الأكلات تظهر فوراً في المينيو
                            _refresh_api_cache(rid)
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
                groq_ok_b, _ = groq_available()
                _ar, _fr, _en = (translate_single_groq(name_) 
                    if groq_ok_b else translate_three_languages(name_))
                _main = _ar if _ar else name_
                ok = add_item(sheet_id, tab_sel, {
                    "name": _main, "name_fr": _fr, "name_en": _en,
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
