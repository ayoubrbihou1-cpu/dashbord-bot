"""
👑 super_admin_agencies.py — صفحة إدارة الوكالات
"""
import streamlit as st
import requests, os, random, string
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

ROUTER_URL = os.getenv("ROUTER_BASE_URL","https://restaurant-qr-saas.onrender.com")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD","admin_fes_2026")
SB_URL     = os.getenv("SUPABASE_URL","")
SB_KEY     = os.getenv("SUPABASE_KEY","")

# ══════════════════════════════════════════════════════
# 📦 باقات الوكالات — ميزات حقيقية لكل باقة
# ══════════════════════════════════════════════════════
AGENCY_PLANS = {
    "basic": {
        "label": "🔵 Basic",
        "price": "مجاني / تجريبي",
        "color": "#3498db",
        "max_restaurants": 5,
        "features": [
            ("✅","حتى 5 مطاعم"),
            ("✅","مينيو QR أساسي"),
            ("✅","كوزينة + Telegram"),
            ("✅","نادل + ليفرور"),
            ("✅","تقارير أسبوعية"),
            ("❌","صور احترافية للبطاقات"),
            ("❌","توصيل GPS للزبائن"),
            ("❌","تقارير يومية"),
            ("❌","كاشير الدفع"),
            ("❌","AI لترتيب المينيو"),
        ]
    },
    "pro": {
        "label": "🟡 Pro",
        "price": "300 د.م/شهر",
        "color": "#C9A84C",
        "max_restaurants": 20,
        "features": [
            ("✅","حتى 20 مطعم"),
            ("✅","QR بطاقات بصور احترافية"),
            ("✅","كوزينة + كاشير دفع"),
            ("✅","توصيل GPS للزبائن"),
            ("✅","تقارير يومية + أسبوعية"),
            ("✅","30 طاولة لكل مطعم"),
            ("✅","زر تعديل الأخطاء"),
            ("✅","إشعارات البوس كاملة"),
            ("❌","AI لترتيب المينيو"),
        ]
    },
    "unlimited": {
        "label": "👑 Unlimited",
        "price": "800 د.م/شهر",
        "color": "#9b59b6",
        "max_restaurants": 999,
        "features": [
            ("✅","مطاعم + طاولات غير محدودة"),
            ("✅","كل ميزات Pro"),
            ("✅","AI يقرأ ويرتب المينيو"),
            ("✅","صور AI مخصصة لكل مطعم"),
            ("✅","تقارير متقدمة + ملخص الوكالة"),
            ("✅","كاشير مع ملخص يومي"),
            ("✅","إعداد أول مطعم مجاناً"),
            ("✅","دعم فني مخصص 24/7"),
        ]
    }
}

def _api(method, path, data=None):
    headers = {"X-Admin-Key": ADMIN_PASS, "Content-Type":"application/json"}
    try:
        fn = {"GET":requests.get,"POST":requests.post,"PATCH":requests.patch}[method]
        r  = fn(f"{ROUTER_URL}{path}", json=data, headers=headers, timeout=15) if data else fn(f"{ROUTER_URL}{path}", headers=headers, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def _sb_patch(table, filters, data):
    if not SB_URL or not SB_KEY: return False
    try:
        h = {"apikey":SB_KEY,"Authorization":f"Bearer {SB_KEY}",
             "Content-Type":"application/json","Prefer":"return=minimal"}
        r = requests.patch(f"{SB_URL}/rest/v1/{table}?{filters}", headers=h, json=data, timeout=8)
        return r.status_code in (200,204)
    except: return False

def _gen_password(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def page_agencies():
    st.markdown("## 👑 إدارة الوكالات")
    dark = st.session_state.get("dark_mode", True)
    card_bg  = "#0f0f0f" if dark else "#f5f0e8"
    card_brd = "#222"    if dark else "#d0c8b0"
    txt_sec  = "#666"    if dark else "#8a7050"

    # ── إحصاءات كلية
    stats = _api("GET", "/superadmin/stats")
    cols  = st.columns(5)
    for col,(val,color,lbl) in zip(cols,[
        (stats.get("agencies",0),    "#C9A84C","🏢 وكالات"),
        (stats.get("restaurants",0), "#29b6f6","🏪 مطاعم"),
        (stats.get("orders",0),      "#ff9800","📦 طلبات"),
        (stats.get("today",0),       "#00e676","📅 اليوم"),
        (f"{int(stats.get('revenue',0))} د.م","#E8C97A","💰 الإيرادات"),
    ]):
        with col:
            st.markdown(f"""<div style="background:{card_bg};border:1px solid {card_brd};
              border-radius:12px;padding:.8rem;text-align:center">
              <div style="font-size:1.5rem;font-weight:900;color:{color}">{val}</div>
              <div style="font-size:.72rem;color:{txt_sec}">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📋 قائمة الوكالات", "➕ وكالة جديدة", "📦 عرض الباقات"])

    # ══════════════════════════════════════════════════════
    # TAB 1: قائمة الوكالات + زر ترقية
    # ══════════════════════════════════════════════════════
    with tab1:
        data     = _api("GET", "/superadmin/agencies")
        agencies = data.get("agencies",[])
        if not agencies:
            st.info("📭 لا توجد وكالات بعد")
        else:
            for ag in agencies:
                if ag.get("agency_id") == "SUPER": continue
                s        = ag.get("stats",{})
                aid      = ag["agency_id"]
                cur_plan = ag.get("plan","basic")
                pi       = AGENCY_PLANS.get(cur_plan, AGENCY_PLANS["basic"])

                with st.expander(
                    f"🏢 {ag['name']} — #{aid} | "
                    f"{s.get('restaurants',0)} مطاعم | "
                    f"{int(s.get('revenue',0))} درهم | "
                    f"{pi['label']}"
                ):
                    # ── بيانات الوكالة
                    r1,r2,r3 = st.columns(3)
                    with r1:
                        st.markdown(f"**📍 المدينة:** {ag.get('city','—')}")
                        st.markdown(f"**👤 المسؤول:** {ag.get('contact_name','—')}")
                        st.markdown(f"**📱 الهاتف:** {ag.get('contact_phone','—')}")
                    with r2:
                        plan_color = pi['color']
                        st.markdown(
                            f"**📋 الخطة:** <b style='color:{plan_color}'>{pi['label']}</b>",
                            unsafe_allow_html=True
                        )
                        st.markdown(f"**🏪 المطاعم:** {s.get('restaurants',0)} / {ag.get('max_restaurants',5)}")
                        st.markdown(f"**📦 الطلبات:** {s.get('orders',0)}")
                    with r3:
                        st.markdown(f"**💰 الإيراد:** {int(s.get('revenue',0))} درهم")
                        status_lbl = "✅ نشطة" if ag.get("status") == "active" else "⛔ موقوفة"
                        st.markdown(f"**⚡ الحالة:** {status_lbl}")
                        st.markdown(f"**📅 أُنشئت:** {str(ag.get('created_at',''))[:10]}")

                    # ── ✅ زر ترقية الباقة
                    st.markdown("---")
                    st.markdown("#### ⬆️ ترقية / تغيير الباقة")
                    u1,u2,u3 = st.columns([2,1,1])
                    with u1:
                        new_plan = st.selectbox(
                            "الباقة الجديدة",
                            list(AGENCY_PLANS.keys()),
                            index=list(AGENCY_PLANS.keys()).index(cur_plan) if cur_plan in AGENCY_PLANS else 0,
                            format_func=lambda x: f"{AGENCY_PLANS[x]['label']} — {AGENCY_PLANS[x]['price']}",
                            key=f"plan_sel_{aid}"
                        )
                        new_max = st.number_input(
                            "حد المطاعم",
                            min_value=1, max_value=9999,
                            value=ag.get("max_restaurants", AGENCY_PLANS[new_plan]["max_restaurants"]),
                            key=f"max_{aid}"
                        )
                    with u2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("💾 حفظ", key=f"upg_{aid}", width="stretch", type="primary"):
                            ok = _sb_patch("agencies", f"agency_id=eq.{aid}",
                                           {"plan": new_plan, "max_restaurants": int(new_max)})
                            if not ok:
                                res = _api("PATCH", f"/superadmin/agencies/{aid}",
                                           {"plan": new_plan, "max_restaurants": int(new_max)})
                                ok  = res.get("ok", False)
                            if ok:
                                st.success(f"✅ تم تحديث {ag['name']} → {AGENCY_PLANS[new_plan]['label']}")
                                st.rerun()
                            else:
                                st.error("❌ فشل التحديث")
                    with u3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        new_status = "suspended" if ag.get("status") == "active" else "active"
                        btn_lbl    = "🔴 تعليق" if ag.get("status") == "active" else "✅ تفعيل"
                        if st.button(btn_lbl, key=f"tog_{aid}", width="stretch"):
                            _sb_patch("agencies", f"agency_id=eq.{aid}", {"status": new_status})
                            st.rerun()

                    # رابط البوابة
                    portal_url = os.getenv("AGENCY_PORTAL_URL","https://agency-portal-2oz.pages.dev")
                    if portal_url:
                        import urllib.parse as _up2
                        _url = f"{portal_url}?agency_id={aid}&name={_up2.quote(ag.get('name',''))}"
                        st.markdown("**🔗 رابط البوابة:**")
                        st.code(_url)
                    if ag.get("notes"):
                        st.info(f"📝 {ag['notes']}")

    # ══════════════════════════════════════════════════════
    # TAB 2: إضافة وكالة جديدة
    # ══════════════════════════════════════════════════════
    with tab2:
        st.markdown("### ➕ إضافة وكالة شريكة جديدة")
        c1,c2 = st.columns(2)
        with c1:
            agency_id   = st.text_input("🔑 رمز الوكالة (Agency ID) *", placeholder="FES001").strip().upper()
            agency_name = st.text_input("🏢 اسم الوكالة *", placeholder="وكالة فاس للمطاعم")
            city        = st.text_input("🌆 المدينة", placeholder="فاس")
            contact_n   = st.text_input("👤 اسم المسؤول", placeholder="محمد الأمين")
            contact_p   = st.text_input("📱 هاتف المسؤول", placeholder="+212 6XX XXX XXX")
        with c2:
            plan_new  = st.selectbox("📋 الخطة", list(AGENCY_PLANS.keys()),
                            format_func=lambda x: f"{AGENCY_PLANS[x]['label']} — {AGENCY_PLANS[x]['price']}")
            max_rest  = st.number_input("🏪 الحد الأقصى",
                            min_value=1, max_value=9999,
                            value=AGENCY_PLANS[plan_new]["max_restaurants"])
            if "agency_gen_pw" not in st.session_state:
                st.session_state["agency_gen_pw"] = _gen_password()
            password  = st.text_input("🔒 كلمة المرور",
                            value=st.session_state["agency_gen_pw"],
                            key="agency_pw_input")
            st.session_state["agency_gen_pw"] = password
            notes     = st.text_area("📝 ملاحظات", height=80)

        if "agency_create_msg" in st.session_state:
            msg = st.session_state.pop("agency_create_msg")
            if msg.get("ok"):
                st.success(f"✅ تم إنشاء **{agency_name}** بنجاح!")
                p_url = os.getenv("AGENCY_PORTAL_URL","https://agency-portal-2oz.pages.dev")
                import urllib.parse as _up
                _full = f"{p_url}?agency_id={agency_id}&name={_up.quote(agency_name)}"
                st.code(f"Agency ID: {agency_id}\nPassword:  {password}\nالرابط:    {_full}")
                st.session_state.pop("agency_gen_pw", None)
            else:
                st.error(f"❌ {msg.get('detail', msg.get('error','خطأ'))}")

        if st.button("✅ إنشاء الوكالة", width="stretch", type="primary"):
            if not agency_id or not agency_name:
                st.error("❌ رمز الوكالة والاسم مطلوبان")
            else:
                with st.spinner("⏳ جاري الإنشاء..."):
                    result = _api("POST", "/superadmin/agencies", {
                        "agency_id":agency_id, "name":agency_name, "password":password,
                        "contact_name":contact_n, "contact_phone":contact_p, "city":city,
                        "plan":plan_new, "max_restaurants":int(max_rest), "notes":notes,
                    })
                    st.session_state["agency_create_msg"] = result
                    st.rerun()

    # ══════════════════════════════════════════════════════
    # TAB 3: مقارنة الباقات
    # ══════════════════════════════════════════════════════
    with tab3:
        st.markdown("### 📦 مقارنة باقات الوكالات")
        pc1,pc2,pc3 = st.columns(3)
        for col,(pk,pi) in zip([pc1,pc2,pc3], AGENCY_PLANS.items()):
            dark2 = st.session_state.get("dark_mode", True)
            bg2   = "#0a0f1a" if dark2 else "#f8f6f0"
            txt_f = "#ccc"    if dark2 else "#333"
            with col:
                feats_html = "".join(
                    f"<div style='padding:.28rem 0;font-size:.83rem;color:{txt_f}'>{icon} {feat}</div>"
                    for icon,feat in pi["features"]
                )
                st.markdown(f"""
                <div style="background:{bg2};border:2px solid {pi['color']};border-radius:16px;
                     padding:1.5rem;text-align:center">
                  <div style="font-size:1.3rem;font-weight:900;color:{pi['color']}">{pi['label']}</div>
                  <div style="font-size:.95rem;color:{pi['color']};margin:.3rem 0 1rem;
                       font-weight:600">{pi['price']}</div>
                  <hr style="border-color:{pi['color']}55;margin:.8rem 0">
                  <div style="text-align:right">{feats_html}</div>
                </div>""", unsafe_allow_html=True)
