"""
🏢 agency_dashboard.py — لوحة الوكالات
═══════════════════════════════════════════════════════════
✅ نسخة مصغرة من admin_dashboard للوكالات الشريكة
✅ كل وكالة ترى مطاعمها فقط
✅ لا يمكنها رؤية وكالات أخرى أو الأرباح الكلية
═══════════════════════════════════════════════════════════
"""
import streamlit as st
import os, json, requests, time, io, base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── إعدادات الاتصال بـ API ───────────────────────────────
ROUTER_URL   = os.getenv("ROUTER_BASE_URL","https://restaurant-qr-saas.onrender.com")
FRONTEND_URL = os.getenv("FRONTEND_URL","https://menu-restcaf.pages.dev")
KITCHEN_URL  = os.getenv("KITCHEN_URL","https://kitchen-restcaf.pages.dev")

# ══════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="🏢 بوابة الوكالات",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
html,body,[class*="css"]{font-family:'Cairo',sans-serif!important}
:root{
  --bg:#080808;--bg2:#101010;--gold:#C9A84C;--gold2:#E8C97A;
  --text:#f0f0f0;--muted:#555;--border:#222;--card:#101010;
  --green:#00e676;--red:#ff5252;--orange:#ff9800;--blue:#29b6f6;
}
.metric-card{
  background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:1rem 1.2rem;text-align:center
}
.metric-num{font-size:2rem;font-weight:900;color:var(--gold)}
.metric-lbl{font-size:.75rem;color:var(--muted);margin-top:.2rem}
.rest-box{
  background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:1rem 1.2rem;margin-bottom:.7rem
}
.rest-title{font-size:1rem;font-weight:700;color:var(--gold2)}
.rest-id{font-size:.72rem;color:var(--muted);font-family:monospace}
.status-badge{
  display:inline-block;padding:.15rem .6rem;border-radius:6px;
  font-size:.72rem;font-weight:700
}
.status-active{background:rgba(0,230,118,.1);color:#00e676;border:1px solid rgba(0,230,118,.2)}
.status-pending{background:rgba(255,152,0,.1);color:#ff9800;border:1px solid rgba(255,152,0,.2)}
div[data-testid="stSidebar"] .stButton>button{
  width:100%;border-radius:10px;padding:.5rem;
  background:rgba(201,168,76,.1);color:#C9A84C;
  border:1px solid rgba(201,168,76,.25);font-size:.88rem;
  margin:.1rem 0;transition:all .2s;
}
div[data-testid="stSidebar"] .stButton>button:hover{
  background:rgba(201,168,76,.2)!important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# SESSION HELPERS
# ══════════════════════════════════════════════════════════

def api_headers():
    """X-Agency-Key للمصادقة"""
    ag = st.session_state.get("agency",{})
    return {"X-Agency-Key": f"{ag.get('agency_id','')}:{ag.get('password','')}"}

def api_get(path: str) -> dict:
    try:
        r = requests.get(f"{ROUTER_URL}{path}", headers=api_headers(), timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def api_post(path: str, data: dict) -> dict:
    try:
        r = requests.post(
            f"{ROUTER_URL}{path}",
            json=data,
            headers={**api_headers(),"Content-Type":"application/json"},
            timeout=30
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════

def pg_login():
    st.markdown("""
    <div style="max-width:420px;margin:5rem auto;text-align:center">
      <div style="font-size:3rem;margin-bottom:.5rem">🏢</div>
      <div style="font-size:1.8rem;font-weight:900;color:#C9A84C;margin-bottom:.3rem">بوابة الوكالات</div>
      <div style="color:#555;font-size:.85rem;margin-bottom:2rem">أدخل بيانات وكالتك للدخول</div>
    </div>
    """, unsafe_allow_html=True)

    col = st.columns([1,2,1])[1]
    with col:
        agency_id = st.text_input("🔑 رمز الوكالة (Agency ID)", placeholder="مثال: FES001").strip().upper()
        password  = st.text_input("🔒 كلمة المرور", type="password", placeholder="••••••••")
        if st.button("🚀 دخول", use_container_width=True, type="primary"):
            if not agency_id or not password:
                st.error("أدخل رمز الوكالة وكلمة المرور")
                return
            with st.spinner("⏳ جاري التحقق..."):
                try:
                    r = requests.post(
                        f"{ROUTER_URL}/agency/login",
                        json={"agency_id": agency_id, "password": password},
                        timeout=15
                    )
                    d = r.json()
                    if d.get("ok"):
                        # ✅ نحفظ password في session للاستخدام في provision
                        agency_data = d["agency"]
                        agency_data["password"] = password  # للـ API calls
                        st.session_state["agency"] = agency_data
                        st.session_state["logged_in"] = True
                        st.rerun()
                    else:
                        st.error(f"❌ {d.get('detail','البيانات غير صحيحة')}")
                except Exception as e:
                    st.error(f"❌ خطأ في الاتصال: {e}")


# ══════════════════════════════════════════════════════════
# DASHBOARD HOME
# ══════════════════════════════════════════════════════════

def pg_home(agency: dict):
    st.markdown(f"## 🏠 لوحة الوكالة — {agency.get('name','')}")

    # Stats
    stats = api_get(f"/agency/{agency['agency_id']}/stats")
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-num" style="color:#C9A84C">{stats.get('restaurants',0)}</div>
          <div class="metric-lbl">🏪 مطاعم</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-num" style="color:#29b6f6">{stats.get('orders',0)}</div>
          <div class="metric-lbl">📦 إجمالي الطلبات</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-num" style="color:#00e676">{int(stats.get('revenue',0))}</div>
          <div class="metric-lbl">💰 الإيرادات (درهم)</div></div>""", unsafe_allow_html=True)
    with c4:
        max_r = agency.get('max_restaurants',5)
        cur   = stats.get('restaurants',0)
        st.markdown(f"""<div class="metric-card">
          <div class="metric-num" style="color:#ff9800">{cur}/{max_r}</div>
          <div class="metric-lbl">📋 الخطة: {agency.get('plan','basic')}</div></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # قائمة المطاعم
    st.markdown("### 🏪 مطاعمي")
    data = api_get(f"/agency/{agency['agency_id']}/restaurants")
    rests = data.get("restaurants",[])
    if not rests:
        st.info("📭 لا توجد مطاعم بعد — اضغط **➕ مطعم جديد** من الشريط الجانبي")
        return
    for r in rests:
        st.markdown(f"""<div class="rest-box">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
            <div>
              <div class="rest-title">{r['name']}</div>
              <div class="rest-id">#{r['restaurant_id']}</div>
            </div>
            <div class="status-badge {'status-active' if r.get('status')=='active' else 'status-pending'}">
              {'✅ نشط' if r.get('status')=='active' else '⏳ '+str(r.get('status',''))}
            </div>
          </div>
          <div style="margin-top:.7rem;display:flex;gap:.5rem;flex-wrap:wrap">
            <span style="font-size:.78rem;color:#555">📋 Sheet: {r.get('sheet_id','—')[:20]}...</span>
            <span style="font-size:.78rem;color:#555">🍽️ {r.get('num_tables',10)} طاولة</span>
          </div>
        </div>""", unsafe_allow_html=True)

        # روابط
        menu_url    = f"{FRONTEND_URL}?rest_id={r['restaurant_id']}"
        kitchen_url = f"{KITCHEN_URL}?api={ROUTER_URL}&rid={r['restaurant_id']}"
        c1,c2,c3 = st.columns(3)
        with c1: st.code(menu_url, language=None)
        with c2: st.code(kitchen_url, language=None)
        with c3:
            if r.get("wifi_password"):
                st.markdown(f"**📶 WiFi:** `{r.get('wifi_ssid','')}` / `{r.get('wifi_password','')}`")


# ══════════════════════════════════════════════════════════
# ADD RESTAURANT
# ══════════════════════════════════════════════════════════

def pg_add_restaurant(agency: dict):
    st.markdown("## ➕ إضافة مطعم جديد")

    # تحقق من الحد
    stats = api_get(f"/agency/{agency['agency_id']}/stats")
    cur   = stats.get("restaurants",0)
    max_r = agency.get("max_restaurants",5)
    if cur >= max_r:
        st.error(f"❌ وصلت للحد الأقصى ({max_r} مطاعم). تواصل مع الإدارة للترقية.")
        return

    st.info(f"📊 لديك {cur}/{max_r} مطاعم مستخدمة")

    with st.expander("📋 كيف تحضر Sheet ID؟", expanded=False):
        st.markdown("""
        1. افتح [sheets.google.com](https://sheets.google.com) وأنشئ Spreadsheet جديد
        2. شاركه مع: `restaurant-bot@gen-lang-client-0967477901.iam.gserviceaccount.com` كـ **Editor**
        3. انسخ الـ ID من الرابط: `docs.google.com/spreadsheets/d/**ID_هنا**/edit`
        """)

    c1,c2 = st.columns(2)
    with c1:
        name     = st.text_input("🏪 اسم المطعم *", placeholder="مطعم النخيل")
        sheet_id = st.text_input("📋 Sheet ID *", placeholder="1BXujpcDww...")
        wifi     = st.text_input("📶 WiFi SSID", placeholder="Wifi 5g")
        wifi_p   = st.text_input("🔑 WiFi Password", placeholder="pass@1234")
    with c2:
        style    = st.selectbox("🎨 الطابع", ["luxury","modern","classic"],
                                format_func=lambda x: {"luxury":"✨ Luxury","modern":"🏙️ Modern","classic":"🏛️ Classic"}[x])
        tables   = st.number_input("🍽️ عدد الطاولات", 1, 200, 10)
        email    = st.text_input("📧 إيميل صاحب المطعم", placeholder="owner@email.com")
        kpass    = st.text_input("🔐 كلمة مرور الكوزينة", placeholder="kitchen2026")

    pc1,pc2 = st.columns(2)
    with pc1: color1 = st.color_picker("لون الخلفية", "#0a0804")
    with pc2: color2 = st.color_picker("لون الذهب",   "#C9A84C")

    if "agency_add_result" in st.session_state:
        res = st.session_state.pop("agency_add_result")
        if res.get("ok"):
            st.success("✅ تم إنشاء المطعم بنجاح!")
            rid = res.get("restaurant_id","")
            c_a, c_b = st.columns(2)
            with c_a:
                st.markdown(f"**🔢 رقم المطعم:** `{rid}`")
                if res.get("menu_url"):
                    st.markdown("**📱 رابط المينيو:**")
                    st.code(res["menu_url"], language=None)
                if res.get("reg_link"):
                    st.markdown("**📲 رابط Telegram:**")
                    st.code(res["reg_link"], language=None)
            with c_b:
                if res.get("kitchen_url"):
                    st.markdown("**🍳 شاشة الكوزينة:**")
                    st.code(res["kitchen_url"], language=None)
                _caisse_url = os.getenv("CAISSE_URL","https://caisse-restcaf.pages.dev")
                if _caisse_url:
                    _slug_r = res.get("slug","") or rid
                    _caisse_link = f"{_caisse_url}?rid={_slug_r}&api={ROUTER_URL}"
                    st.markdown("**💰 صفحة الكاشير:**")
                    st.code(_caisse_link, language=None)
        else:
            err_msg = res.get("detail") or res.get("error") or str(res)
            st.error(f"❌ {err_msg}")

    # رقم المطعم وslug
    c3, c4 = st.columns(2)
    with c3:
        rid_input = st.text_input("🔢 رقم المطعم (ID)", placeholder="مثال: 10 أو أي رقم فريد")
    with c4:
        slug_input = st.text_input("🔗 Slug (رابط نظيف)", placeholder="مثال: nakhil (بالإنجليزية)")

    if st.button("🚀 إنشاء المطعم", use_container_width=True, type="primary"):
        if not name.strip():
            st.error("❌ أدخل اسم المطعم"); return
        if not sheet_id.strip():
            st.error("❌ أدخل Sheet ID"); return
        if not rid_input.strip():
            st.error("❌ أدخل رقم المطعم"); return
        
        # slug آمن
        import re
        _slug = slug_input.strip().lower().replace(" ","-") if slug_input.strip() else re.sub(r"[^a-z0-9-]","",name.strip().lower().replace(" ","-"))[:25]
        
        with st.spinner("⏳ جاري الإنشاء... (قد يستغرق 30 ثانية)"):
            result = api_post("/agency/provision", {
                "agency_id":        agency["agency_id"],
                "password":         agency.get("password",""),
                "restaurant_id":    rid_input.strip(),
                "name":             name.strip(),
                "sheet_id":         sheet_id.strip(),
                "slug":             _slug,
                "wifi_ssid":        wifi.strip(),
                "wifi_password":    wifi_p.strip(),
                "style":            style,
                "num_tables":       tables,
                "owner_email":      email.strip(),
                "kitchen_password": kpass.strip(),
                "primary_color":    color1,
                "accent_color":     color2,
            })
            st.session_state["agency_add_result"] = result
            st.rerun()


# ══════════════════════════════════════════════════════════
# ORDERS
# ══════════════════════════════════════════════════════════

def pg_orders(agency: dict):
    st.markdown("## 📦 الطلبات")
    data   = api_get(f"/agency/{agency['agency_id']}/orders")
    orders = data.get("orders",[])
    if not orders:
        st.info("📭 لا توجد طلبات بعد")
        return

    # فلتر سريع
    status_filter = st.selectbox("فلتر", ["الكل","⏳ جديد","👨‍🍳 يُحضَّر","✅ جاهز","🚫 ملغي"])
    if status_filter != "الكل":
        orders = [o for o in orders if o.get("status") == status_filter]

    st.markdown(f"**إجمالي: {len(orders)} طلب**")

    for o in orders[:100]:
        status = o.get("status","")
        color  = "#C9A84C" if "جديد" in status else "#00e676" if "جاهز" in status or "سُلِّم" in status else "#ff5252" if "ملغي" in status else "#ff9800"
        st.markdown(f"""
        <div style="background:#111;border:1px solid #1e1e1e;border-radius:10px;
          padding:.7rem 1rem;margin-bottom:.4rem;display:flex;
          justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
          <div>
            <div style="font-family:monospace;font-size:.72rem;color:#555">{o.get('order_id','')}</div>
            <div style="font-size:.85rem">{o.get('restaurant_name',o.get('restaurant_id',''))} | طاولة {o.get('table_number','')}</div>
            <div style="font-size:.78rem;color:#777">{o.get('customer_name','')} | {o.get('total_price',0)} درهم</div>
          </div>
          <div style="color:{color};font-size:.78rem;font-weight:700">{status}</div>
          <div style="font-size:.72rem;color:#555">{str(o.get('created_at','')).split('T')[-1][:8]}</div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════
# 🖨️ PDF + QR CODE
# ══════════════════════════════════════════════════════════

def pg_pdf(agency: dict):
    st.markdown("## 🖨️ بطاقات PDF + QR Code")

    data  = api_get(f"/agency/{agency['agency_id']}/restaurants")
    rests = data.get("restaurants",[])
    if not rests:
        st.info("📭 أضف مطعماً أولاً"); return

    rest_names = {r["restaurant_id"]: r["name"] for r in rests}
    sel_rid = st.selectbox("🏪 اختر المطعم", options=list(rest_names.keys()),
                            format_func=lambda x: rest_names[x])
    sel_rest = next((r for r in rests if r["restaurant_id"]==sel_rid), {})

    c1,c2 = st.columns(2)
    with c1:
        num_tables = st.number_input("عدد الطاولات", 1, 200,
                                      int(sel_rest.get("num_tables",10)))
    with c2:
        style = st.selectbox("الطابع", ["luxury","modern","classic"],
                              index=["luxury","modern","classic"].index(sel_rest.get("style","luxury")))

    if st.button("🖨️ توليد PDF", use_container_width=True, type="primary"):
        with st.spinner("⏳ جاري توليد PDF..."):
            r = requests.post(
                f"{ROUTER_URL}/generate_pdf",
                json={
                    "restaurant_id": sel_rid,
                    "num_tables":    num_tables,
                    "style":         style,
                    "agency_check":  agency["agency_id"],
                },
                headers={**api_headers(),"Content-Type":"application/json"},
                timeout=60
            )
            if r.status_code == 200 and r.headers.get("content-type","").startswith("application/pdf"):
                st.download_button(
                    "⬇️ تحميل PDF",
                    data     = r.content,
                    file_name= f"qr_{sel_rest.get('name',sel_rid)}.pdf",
                    mime     = "application/pdf",
                    use_container_width=True
                )
                st.success("✅ PDF جاهز!")
            else:
                try:
                    err = r.json().get("detail","خطأ في التوليد")
                except: err = r.text[:200]
                st.error(f"❌ {err}")

    st.markdown("---")
    st.markdown("### 📱 روابط QR مباشرة")
    # menu_url already set above
    kitchen_url = f"{KITCHEN_URL}?api={ROUTER_URL}&rid={sel_rid}"
    slug_k = sel_rest.get("slug","").strip()
    menu_url = f"{FRONTEND_URL}/{slug_k}" if slug_k else f"{FRONTEND_URL}?rest_id={sel_rid}"
    st.markdown(f"**🍽️ رابط المينيو:**")
    st.code(menu_url)
    st.markdown(f"**🍳 رابط الكوزينة:**")
    st.code(kitchen_url)


# ══════════════════════════════════════════════════════════
# 🖼️ صور الأكلات
# ══════════════════════════════════════════════════════════

def pg_images(agency: dict):
    st.markdown("## 🖼️ صور الأكلات")

    data  = api_get(f"/agency/{agency['agency_id']}/restaurants")
    rests = data.get("restaurants",[])
    if not rests:
        st.info("📭 أضف مطعماً أولاً"); return

    rest_names = {r["restaurant_id"]: r["name"] for r in rests}
    sel_rid = st.selectbox("🏪 اختر المطعم",
                            options=list(rest_names.keys()),
                            format_func=lambda x: rest_names[x],
                            key="img_rest_sel")
    sel_rest = next((r for r in rests if r["restaurant_id"]==sel_rid), {})
    sheet_id = sel_rest.get("sheet_id","")

    if not sheet_id:
        st.error("❌ هذا المطعم ليس لديه Sheet ID"); return

    TABS = ["الأطباق الرئيسية","المقبلات","الحلويات","المشروبات"]
    tab_sel = st.selectbox("📋 الصنف", TABS, key="img_tab_sel")

    st.markdown("---")
    tab1, tab2 = st.tabs(["🔍 Unsplash تلقائي", "📸 تحليل صورة المينيو"])

    with tab1:
        st.info("أدخل اسم الأكلة → سيبحث عن صورة مناسبة تلقائياً")
        dish_name = st.text_input("اسم الأكلة", placeholder="طاجين دجاج")
        if st.button("🔍 بحث عن صورة", use_container_width=True):
            if dish_name:
                with st.spinner("⏳ جاري البحث..."):
                    r = requests.get(
                        f"{ROUTER_URL}/image/search",
                        params={"q": dish_name, "restaurant_id": sel_rid},
                        headers=api_headers(), timeout=15
                    )
                    if r.status_code == 200:
                        d = r.json()
                        if d.get("url"):
                            st.image(d["url"], width=200)
                            st.code(d["url"])
                            st.success("✅ الصورة جاهزة — انسخ الرابط وضعه في إدارة القائمة")
                    else:
                        st.error("❌ لم يجد صورة")

    with tab2:
        st.info("ارفع صورة المينيو → سيستخرج الأكلات والأسعار تلقائياً ويضيفها للـ Sheet")
        uploaded = st.file_uploader("📸 صورة المينيو", type=["jpg","jpeg","png","webp"])
        if uploaded and st.button("🤖 تحليل وإضافة للـ Sheet", use_container_width=True):
            with st.spinner("⏳ جاري التحليل بـ Gemini Vision..."):
                img_b64 = base64.b64encode(uploaded.read()).decode()
                r = requests.post(
                    f"{ROUTER_URL}/menu/scan",
                    json={"image_b64": img_b64,
                          "mime_type": uploaded.type,
                          "restaurant_id": sel_rid,
                          "sheet_id": sheet_id,
                          "tab": tab_sel,
                          "agency_id": agency["agency_id"]},
                    headers={**api_headers(),"Content-Type":"application/json"},
                    timeout=60
                )
                if r.status_code == 200:
                    d = r.json()
                    st.success(f"✅ تم إضافة {d.get('added',0)} أكلة للـ Sheet!")
                    if d.get("items"):
                        st.dataframe(d["items"])
                else:
                    try: st.error(f"❌ {r.json().get('detail','خطأ')}")
                    except: st.error("❌ خطأ في التحليل")


# ══════════════════════════════════════════════════════════
# 🍽️ إدارة القائمة
# ══════════════════════════════════════════════════════════

def pg_menu(agency: dict):
    st.markdown("## 🍽️ إدارة القائمة")

    data  = api_get(f"/agency/{agency['agency_id']}/restaurants")
    rests = data.get("restaurants",[])
    if not rests:
        st.info("📭 أضف مطعماً أولاً"); return

    rest_names = {r["restaurant_id"]: r["name"] for r in rests}
    sel_rid = st.selectbox("🏪 اختر المطعم",
                            options=list(rest_names.keys()),
                            format_func=lambda x: rest_names[x],
                            key="menu_rest_sel")
    sel_rest = next((r for r in rests if r["restaurant_id"]==sel_rid), {})
    sheet_id = sel_rest.get("sheet_id","")

    if not sheet_id:
        st.error("❌ هذا المطعم ليس لديه Sheet ID"); return

    TABS = ["الأطباق الرئيسية","المقبلات","الحلويات","المشروبات"]
    tab_sel = st.selectbox("📋 الصنف", TABS, key="menu_tab_sel")

    # جلب الأكلات من API
    r = requests.get(
        f"{ROUTER_URL}/menu_items/{sel_rid}/{tab_sel}",
        headers=api_headers(), timeout=15
    )
    items = []
    if r.status_code == 200:
        items = r.json().get("items", [])

    if items:
        st.markdown(f"**{len(items)} أكلة في {tab_sel}:**")
        for i, item in enumerate(items):
            with st.expander(f"{item.get('name','')} — {item.get('price','')} درهم"):
                c1,c2 = st.columns(2)
                with c1:
                    st.text(f"🇫🇷 {item.get('name_fr','')}")
                    st.text(f"🇬🇧 {item.get('name_en','')}")
                with c2:
                    st.text(f"✅ متاح: {item.get('available','TRUE')}")
                    if item.get('image_url'):
                        st.image(item['image_url'], width=80)
    else:
        st.info("📭 لا توجد أكلات بعد")

    st.markdown("---")
    st.markdown("### ➕ إضافة أكلة جديدة")
    c1,c2 = st.columns(2)
    with c1:
        n_name  = st.text_input("🍽️ الاسم بالعربية *", key="ag_add_name")
        n_price = st.number_input("💰 السعر (درهم)", 0.0, 9999.0, 0.0, key="ag_add_price")
        n_desc  = st.text_area("📝 الوصف", key="ag_add_desc", height=70)
    with c2:
        n_fr    = st.text_input("🇫🇷 الاسم بالفرنسية", key="ag_add_fr")
        n_en    = st.text_input("🇬🇧 الاسم بالإنجليزية", key="ag_add_en")
        n_img   = st.text_input("🖼️ رابط الصورة", key="ag_add_img", placeholder="https://...")

    if st.button("➕ إضافة للقائمة", use_container_width=True, type="primary", key="ag_btn_add"):
        if not n_name.strip():
            st.error("❌ الاسم مطلوب"); return
        if n_price <= 0:
            st.error("❌ أدخل سعراً صحيحاً"); return
        r = requests.post(
            f"{ROUTER_URL}/menu_items/{sel_rid}/{tab_sel}",
            json={"name":n_name.strip(),"name_fr":n_fr.strip(),
                  "name_en":n_en.strip(),"price":str(n_price),
                  "description":n_desc.strip(),"available":"TRUE",
                  "image_url":n_img.strip()},
            headers={**api_headers(),"Content-Type":"application/json"},
            timeout=20
        )
        if r.status_code == 200:
            st.success("✅ تمت الإضافة!")
            st.rerun()
        else:
            try: st.error(f"❌ {r.json().get('detail','خطأ')}")
            except: st.error("❌ خطأ في الإضافة")


# ══════════════════════════════════════════════════════════
# 📊 STATS + REPORTS
# ══════════════════════════════════════════════════════════

def pg_reports(agency: dict):
    st.markdown("## 📊 التقارير والإحصاءات")

    data  = api_get(f"/agency/{agency['agency_id']}/restaurants")
    rests = data.get("restaurants",[])
    if not rests:
        st.info("📭 لا توجد مطاعم"); return

    rest_names = {r["restaurant_id"]: r["name"] for r in rests}
    sel_rid = st.selectbox("🏪 اختر المطعم",
                            options=["الكل"] + list(rest_names.keys()),
                            format_func=lambda x: "📊 الكل" if x=="الكل" else rest_names[x])

    period = st.radio("الفترة", ["يومي","أسبوعي","شهري"], horizontal=True)

    if st.button("📊 إنشاء التقرير وإرساله PDF", use_container_width=True, type="primary"):
        if sel_rid == "الكل":
            targets = list(rest_names.keys())
        else:
            targets = [sel_rid]

        for rid in targets:
            with st.spinner(f"⏳ {rest_names.get(rid,rid)}..."):
                r = requests.post(
                    f"{ROUTER_URL}/report/pdf/{rid}",
                    json={"period": period},
                    headers={**api_headers(), "Content-Type":"application/json"},
                    timeout=30
                )
                if r.status_code == 200:
                    d = r.json()
                    st.success(f"✅ {rest_names.get(rid,rid)} — {d.get('orders',0)} طلب — {d.get('revenue',0):.0f} درهم")
                else:
                    st.error(f"❌ {rest_names.get(rid,rid)}")

    st.markdown("---")

    # Orders summary per restaurant
    st.markdown("### 📦 ملخص الطلبات")
    orders_data = api_get(f"/agency/{agency['agency_id']}/orders")
    orders = orders_data.get("orders", [])

    if orders:
        from collections import Counter
        rest_orders = Counter(o.get("restaurant_id","") for o in orders)
        rest_revenue = {}
        for o in orders:
            rid = o.get("restaurant_id","")
            if o.get("status") in ("✅ جاهز","🏁 سُلِّم"):
                rest_revenue[rid] = rest_revenue.get(rid,0) + float(o.get("total_price",0))

        for rid, name in rest_names.items():
            c1,c2,c3 = st.columns(3)
            with c1: st.metric(f"🏪 {name}", f"{rest_orders.get(rid,0)} طلب")
            with c2: st.metric("💰 الإيراد", f"{rest_revenue.get(rid,0):.0f} درهم")
            with c3: st.metric("📈 متوسط", f"{rest_revenue.get(rid,0)/max(rest_orders.get(rid,1),1):.0f} درهم")
    else:
        st.info("لا توجد طلبات بعد")


# ══════════════════════════════════════════════════════════
# ⚙️ إعدادات المطعم
# ══════════════════════════════════════════════════════════

def pg_settings(agency: dict):
    st.markdown("## ⚙️ إعدادات المطاعم")

    data  = api_get(f"/agency/{agency['agency_id']}/restaurants")
    rests = data.get("restaurants",[])
    if not rests:
        st.info("📭 لا توجد مطاعم"); return

    rest_names = {r["restaurant_id"]: r["name"] for r in rests}
    sel_rid  = st.selectbox("🏪 اختر المطعم", options=list(rest_names.keys()),
                             format_func=lambda x: rest_names[x])
    sel_rest = next((r for r in rests if r["restaurant_id"]==sel_rid), {})

    tab1, tab2, tab3 = st.tabs(["🔗 الروابط", "📱 Telegram", "🎨 الألوان"])

    with tab1:
        st.markdown("**روابط المطعم:**")
        # menu_url set below with slug
        kitchen_url = f"{KITCHEN_URL}?api={ROUTER_URL}&rid={sel_rid}"
        slug_k = sel_rest.get("slug","").strip()
        menu_url = f"{FRONTEND_URL}/{slug_k}" if slug_k else f"{FRONTEND_URL}?rest_id={sel_rid}"
        st.markdown("🍽️ رابط المينيو للزبائن:")
        st.code(menu_url)
        st.markdown("🍳 رابط شاشة الكوزينة:")
        st.code(kitchen_url)
        st.markdown(f"📶 WiFi: `{sel_rest.get('wifi_ssid','')}` | `{sel_rest.get('wifi_password','')}`")

    with tab2:
        st.markdown("**روابط ربط Telegram للمطعم:**")
        bot = os.getenv("TELEGRAM_BOT_USERNAME","Ayoub_Resto_bot")
        rid = sel_rid
        links = {
            "صاحب المطعم":  f"https://t.me/{bot}?start=reg_{rid}",
            "مجموعة النوادل": f"https://t.me/{bot}?start=waiters_{rid}",
            "مجموعة التوصيل": f"https://t.me/{bot}?start=delivery_{rid}",
            "مجموعة المدير":  f"https://t.me/{bot}?start=boss_{rid}",
        }
        for name, link in links.items():
            c1,c2 = st.columns([3,1])
            with c1: st.markdown(f"**{name}:**"); st.code(link)
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(f"[🔗 فتح]({link})")

        st.info("📌 أرسل كل رابط للشخص المناسب — يضغطه مرة واحدة فقط ويتفعل تلقائياً")

    with tab3:
        st.markdown("**ألوان المطعم:**")
        c1,c2 = st.columns(2)
        with c1:
            pc = st.color_picker("لون الخلفية", sel_rest.get("primary_color","#0a0804"))
        with c2:
            ac = st.color_picker("لون الذهب", sel_rest.get("accent_color","#C9A84C"))
        if st.button("💾 حفظ الألوان"):
            st.info("⚠️ تغيير الألوان يتطلب إعادة provision — تواصل مع الدعم")


# ══════════════════════════════════════════════════════════
# 🆘 الدعم الفني
# ══════════════════════════════════════════════════════════

def pg_support(agency: dict):
    st.markdown("## 🆘 الدعم الفني")

    st.markdown("""
    <div style="background:#111;border:1px solid #C9A84C33;border-radius:12px;padding:1.2rem;margin-bottom:1rem">
      <div style="color:#C9A84C;font-weight:700;font-size:1rem;margin-bottom:.5rem">📋 دليل الاستخدام السريع</div>
      <div style="color:#aaa;font-size:.85rem;line-height:1.8">
        1️⃣ <b>إضافة مطعم جديد:</b> أنشئ Google Sheet → شاركه مع SA email → أضفه هنا<br>
        2️⃣ <b>إضافة القائمة:</b> صفحة "إدارة القائمة" أو ارفع صورة المينيو<br>
        3️⃣ <b>ربط Telegram:</b> صفحة الإعدادات → أرسل الروابط<br>
        4️⃣ <b>طباعة QR:</b> صفحة "بطاقات PDF" → حمّل وطبع<br>
        5️⃣ <b>الكوزينة:</b> افتح رابط الكوزينة على التابليت
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📧 SA Email للمشاركة")
    sa = "restaurant-bot@gen-lang-client-0967477901.iam.gserviceaccount.com"
    st.code(sa)
    st.caption("شارك كل Google Sheet مع هذا العنوان كـ Editor")

    st.markdown("### ❓ أسئلة شائعة")
    with st.expander("كيف أضيف مطعم جديد؟"):
        st.markdown("""
        1. اذهب sheets.google.com وأنشئ Spreadsheet
        2. شاركه مع SA Email أعلاه كـ Editor
        3. انسخ الـ ID من رابط الشيت
        4. اضغط "مطعم جديد" وأدخل البيانات
        """)
    with st.expander("لماذا لا تظهر الطلبات في الكوزينة؟"):
        st.markdown("تأكد من ربط Telegram للمطعم، وأن شاشة الكوزينة مفتوحة على الرابط الصحيح")
    with st.expander("كيف أضيف صور للأكلات؟"):
        st.markdown("صفحة **صور الأكلات** → ابحث بالاسم أو ارفع صورة المينيو")

    st.markdown("---")
    st.info("للدعم المباشر: تواصل مع مزود الخدمة")

def main():
    # تهيئة session
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "page" not in st.session_state:
        st.session_state["page"] = "🏠 الرئيسية"

    # ── شاشة الدخول ──────────────────────────────────────
    if not st.session_state.get("logged_in"):
        pg_login()
        return

    agency = st.session_state.get("agency",{})

    # ── شريط جانبي ───────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:.5rem 0">
          <div style="font-size:1.5rem">🏢</div>
          <div style="color:#C9A84C;font-size:1rem;font-weight:900">{agency.get('name','')}</div>
          <div style="color:#555;font-size:.72rem">وكالة #{agency.get('agency_id','')}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

        nav = [
            ("🏠 الرئيسية",       "🏠 الرئيسية"),
            ("➕ مطعم جديد",     "➕ مطعم جديد"),
            ("🍽️ إدارة القائمة", "🍽️ إدارة القائمة"),
            ("🖼️ صور الأكلات",   "🖼️ صور الأكلات"),
            ("🖨️ بطاقات PDF",    "🖨️ بطاقات PDF"),
            ("📦 الطلبات",       "📦 الطلبات"),
            ("📊 التقارير",      "📊 التقارير"),
            ("⚙️ الإعدادات",     "⚙️ الإعدادات"),
            ("🆘 الدعم",         "🆘 الدعم"),
        ]
        for label, key in nav:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["page"] = key
                st.rerun()

        st.markdown("---")
        if st.button("🚪 خروج", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["agency"] = {}
            st.rerun()

        # معلومات الخطة
        st.markdown(f"""
        <div style="background:#111;border:1px solid #1e1e1e;border-radius:8px;
          padding:.7rem;margin-top:1rem;text-align:center">
          <div style="font-size:.72rem;color:#555">الخطة</div>
          <div style="color:#C9A84C;font-weight:700">{agency.get('plan','basic').upper()}</div>
          <div style="font-size:.72rem;color:#555">حتى {agency.get('max_restaurants',5)} مطاعم</div>
        </div>
        """, unsafe_allow_html=True)

    # ── صفحات ────────────────────────────────────────────
    page = st.session_state.get("page","🏠 الرئيسية")
    if   page == "🏠 الرئيسية":        pg_home(agency)
    elif page == "➕ مطعم جديد":       pg_add_restaurant(agency)
    elif page == "🍽️ إدارة القائمة":   pg_menu(agency)
    elif page == "🖼️ صور الأكلات":     pg_images(agency)
    elif page == "🖨️ بطاقات PDF":      pg_pdf(agency)
    elif page == "📦 الطلبات":         pg_orders(agency)
    elif page == "📊 التقارير":        pg_reports(agency)
    elif page == "⚙️ الإعدادات":       pg_settings(agency)
    elif page == "🆘 الدعم":           pg_support(agency)


if __name__ == "__main__":
    main()
