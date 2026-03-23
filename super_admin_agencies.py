"""
👑 super_admin_agencies.py — صفحة إدارة الوكالات (للسوبر أدمين فقط)
تُضاف في admin_dashboard.py كصفحة إضافية
"""
import streamlit as st
import requests, os, random, string
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ROUTER_URL   = os.getenv("ROUTER_BASE_URL","https://restaurant-qr-saas.onrender.com")
ADMIN_PASS   = os.getenv("ADMIN_PASSWORD","admin_fes_2026")

def _api(method, path, data=None):
    headers = {"X-Admin-Key": ADMIN_PASS, "Content-Type":"application/json"}
    try:
        if method == "GET":
            r = requests.get(f"{ROUTER_URL}{path}", headers=headers, timeout=15)
        else:
            r = requests.post(f"{ROUTER_URL}{path}", json=data, headers=headers, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def _gen_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def page_agencies():
    st.markdown("## 👑 إدارة الوكالات")

    # ── إحصاءات كلية ──────────────────────────────────────
    stats = _api("GET", "/superadmin/stats")
    c1,c2,c3,c4,c5 = st.columns(5)
    metrics = [
        (c1, stats.get("agencies",0),    "#C9A84C", "🏢 وكالات نشطة"),
        (c2, stats.get("restaurants",0), "#29b6f6", "🏪 مطاعم كلي"),
        (c3, stats.get("orders",0),      "#ff9800", "📦 طلبات كلي"),
        (c4, stats.get("today",0),       "#00e676", "📅 طلبات اليوم"),
        (c5, f"{int(stats.get('revenue',0))} د.م", "#E8C97A", "💰 إجمالي الإيرادات"),
    ]
    for col, val, color, lbl in metrics:
        with col:
            st.markdown(f"""<div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;
              padding:.8rem;text-align:center">
              <div style="font-size:1.6rem;font-weight:900;color:{color}">{val}</div>
              <div style="font-size:.72rem;color:#555">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2 = st.tabs(["📋 قائمة الوكالات", "➕ وكالة جديدة"])

    # ── TAB 1: قائمة الوكالات ─────────────────────────────
    with tab1:
        data = _api("GET", "/superadmin/agencies")
        agencies = data.get("agencies",[])
        if not agencies:
            st.info("📭 لا توجد وكالات بعد")
        else:
            for ag in agencies:
                if ag.get("agency_id") == "SUPER":
                    continue  # لا تعرض SUPER في القائمة
                s = ag.get("stats",{})
                with st.expander(f"🏢 {ag['name']} — #{ag['agency_id']} | {s.get('restaurants',0)} مطاعم | {int(s.get('revenue',0))} درهم"):
                    c1,c2,c3 = st.columns(3)
                    with c1:
                        st.markdown(f"**المدينة:** {ag.get('city','—')}")
                        st.markdown(f"**المسؤول:** {ag.get('contact_name','—')}")
                        st.markdown(f"**الهاتف:** {ag.get('contact_phone','—')}")
                    with c2:
                        st.markdown(f"**الخطة:** `{ag.get('plan','basic').upper()}`")
                        st.markdown(f"**المطاعم:** {s.get('restaurants',0)} / {ag.get('max_restaurants',5)}")
                        st.markdown(f"**الطلبات:** {s.get('orders',0)}")
                    with c3:
                        st.markdown(f"**الإيراد:** {int(s.get('revenue',0))} درهم")
                        st.markdown(f"**الحالة:** {'✅ نشطة' if ag.get('status')=='active' else '⛔ موقوفة'}")
                        st.markdown(f"**أُنشئت:** {str(ag.get('created_at',''))[:10]}")

                    # رابط لوحة الوكالة
                    agency_portal_url = os.getenv("AGENCY_PORTAL_URL","https://agency-portal-2oz.pages.dev")
                    if agency_portal_url:
                        import urllib.parse as _up2
                        _ag_name_enc = _up2.quote(ag.get("name",""))
                        _ag_full_url = (
                            f"{agency_portal_url}"
                            f"?agency_id={ag['agency_id']}"
                            f"&name={_ag_name_enc}"
                        )
                        st.markdown("**🔗 رابط البوابة:**")
                        st.code(_ag_full_url)
                        st.caption("📌 رابط خاص بهذه الوكالة — يظهر اسمها عند الفتح")

                    if ag.get("notes"):
                        st.info(f"📝 {ag['notes']}")

    # ── TAB 2: إضافة وكالة جديدة ──────────────────────────
    with tab2:
        st.markdown("### ➕ إضافة وكالة شريكة جديدة")

        c1,c2 = st.columns(2)
        with c1:
            agency_id   = st.text_input("🔑 رمز الوكالة (Agency ID) *",
                                         placeholder="FES001",
                                         help="حروف وأرقام فقط — مثال: FES001, CASA01").strip().upper()
            agency_name = st.text_input("🏢 اسم الوكالة *", placeholder="وكالة فاس للمطاعم")
            city        = st.text_input("🌆 المدينة", placeholder="فاس")
            contact_n   = st.text_input("👤 اسم المسؤول", placeholder="محمد الأمين")
            contact_p   = st.text_input("📱 هاتف المسؤول", placeholder="+212 6XX XXX XXX")

        with c2:
            plan        = st.selectbox("📋 الخطة", ["basic","pro","unlimited"],
                                        format_func=lambda x: {"basic":"🔵 Basic (5 مطاعم)",
                                                                "pro":"🟡 Pro (20 مطعم)",
                                                                "unlimited":"👑 Unlimited"}[x])
            max_rest    = st.number_input("🏪 الحد الأقصى للمطاعم",
                                          min_value=1, max_value=9999,
                                          value={"basic":5,"pro":20,"unlimited":999}[plan])
            # ✅ FIX: نولّد كلمة المرور مرة واحدة فقط ونحفظها في session_state
            # حتى لا تُعاد في كل render وتمحو ما كتبه المستخدم
            if "agency_gen_pw" not in st.session_state:
                st.session_state["agency_gen_pw"] = _gen_password()
            password = st.text_input(
                "🔒 كلمة المرور",
                value=st.session_state["agency_gen_pw"],
                key="agency_pw_input",
                help="يمكنك تغييرها — ستُعطى للوكالة"
            )
            # حدّث session_state بما كتبه المستخدم
            st.session_state["agency_gen_pw"] = password
            notes       = st.text_area("📝 ملاحظات", placeholder="معلومات إضافية...", height=80)

        if "agency_create_msg" in st.session_state:
            msg = st.session_state.pop("agency_create_msg")
            if msg.get("ok"):
                st.success(f"✅ تم إنشاء الوكالة **{agency_name}** بنجاح!")
                agency_portal_url = os.getenv("AGENCY_PORTAL_URL","https://agency-portal-2oz.pages.dev")
                # ✅ FIX 2: رابط خاص بكل وكالة يحتوي على agency_id
                _agency_link = f"{agency_portal_url}?agency_id={agency_id}" if agency_portal_url else ""
                st.markdown("**بيانات الدخول لإعطائها للوكالة:**")
                st.code(
                    f"Agency ID: {agency_id}\n"
                    f"Password:  {password}\n"
                    f"الرابط:    {_agency_link}",
                    language=None
                )
                if _agency_link:
                    import urllib.parse as _up
                    _name_enc = _up.quote(agency_name)
                    _full_link = f"{agency_portal_url}?agency_id={agency_id}&name={_name_enc}"
                    st.markdown(f"**🔗 رابط البوابة الخاص بالوكالة:**")
                    st.code(_full_link, language=None)
                    st.caption("📌 هذا الرابط خاص بهذه الوكالة — سيظهر اسمها عند فتحه")
                # امسح كلمة المرور المولّدة حتى تتجهز للوكالة التالية
                st.session_state.pop("agency_gen_pw", None)
            else:
                st.error(f"❌ {msg.get('detail',msg.get('error','خطأ'))}")

        if st.button("✅ إنشاء الوكالة", use_container_width=True, type="primary"):
            if not agency_id or not agency_name:
                st.error("❌ رمز الوكالة والاسم مطلوبان")
            else:
                with st.spinner("⏳ جاري الإنشاء..."):
                    result = _api("POST", "/superadmin/agencies", {
                        "agency_id":       agency_id,
                        "name":            agency_name,
                        "password":        password,
                        "contact_name":    contact_n,
                        "contact_phone":   contact_p,
                        "city":            city,
                        "plan":            plan,
                        "max_restaurants": int(max_rest),
                        "notes":           notes,
                    })
                    st.session_state["agency_create_msg"] = result
                    st.rerun()
