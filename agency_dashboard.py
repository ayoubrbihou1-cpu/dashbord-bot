"""
🏢 agency_dashboard.py — لوحة الوكالات
═══════════════════════════════════════════════════════════
✅ نسخة مصغرة من admin_dashboard للوكالات الشريكة
✅ كل وكالة ترى مطاعمها فقط
✅ لا يمكنها رؤية وكالات أخرى أو الأرباح الكلية
═══════════════════════════════════════════════════════════
"""
import streamlit as st
import os, json, requests, time
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
                        st.session_state["agency"] = d["agency"]
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
            st.markdown(f"""
            **🔢 رقم المطعم:** `{rid}`

            **🍽️ رابط المينيو:**
            """)
            st.code(res.get("menu_url",""), language=None)
            if res.get("kitchen_url"):
                st.markdown("**🍳 شاشة الكوزينة:**")
                st.code(res["kitchen_url"], language=None)
            if res.get("reg_link"):
                st.markdown("**📱 رابط Telegram:**")
                st.code(res["reg_link"], language=None)
        else:
            st.error(f"❌ {res.get('detail','خطأ في الإنشاء')}")

    if st.button("🚀 إنشاء المطعم", use_container_width=True, type="primary"):
        if not name.strip():
            st.error("❌ أدخل اسم المطعم")
            return
        if not sheet_id.strip():
            st.error("❌ أدخل Sheet ID")
            return
        with st.spinner("⏳ جاري الإنشاء... (قد يستغرق 30 ثانية)"):
            result = api_post("/agency/provision", {
                "agency_id":       agency["agency_id"],
                "name":            name.strip(),
                "sheet_id":        sheet_id.strip(),
                "wifi_ssid":       wifi.strip(),
                "wifi_password":   wifi_p.strip(),
                "style":           style,
                "num_tables":      tables,
                "owner_email":     email.strip(),
                "kitchen_password":kpass.strip(),
                "primary_color":   color1,
                "accent_color":    color2,
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
            ("🏠 الرئيسية",     "🏠 الرئيسية"),
            ("➕ مطعم جديد",   "➕ مطعم جديد"),
            ("📦 الطلبات",      "📦 الطلبات"),
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
    if   page == "🏠 الرئيسية":   pg_home(agency)
    elif page == "➕ مطعم جديد":  pg_add_restaurant(agency)
    elif page == "📦 الطلبات":    pg_orders(agency)


if __name__ == "__main__":
    main()
