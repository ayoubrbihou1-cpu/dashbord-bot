"""
👑 admin_dashboard.py — النسخة النهائية الكاملة v5.0
═══════════════════════════════════════════════════
✅ كيف يعمل التعدد:
   - كل مطعم له Sheet ID خاص = قاعدة بياناته المستقلة
   - Master_DB tab = جدول الفهرس (restaurant_id → sheet_id)
   - عندما يفتح الزبون ?rest_id=2 → API يبحث في Master_DB
     عن restaurant_id=2 → يجلب sheet_id → يقرأ منه فقط
   - لا يختلط مطعم بآخر أبداً

✅ إصلاحات:
   - KeyError في صور الأكلات
   - DuplicateElementKey في الإدارة
   - PDF يعمل (ImageReader)
   - Telegram Webhook صحيح
   - صور الأكلات تُحفظ في Sheet كل مطعم
"""
import streamlit as st
import gspread, io, os, json, time, requests
from google.oauth2.service_account import Credentials
from datetime import datetime
from dotenv import load_dotenv

from auto_provisioner import provision_restaurant, ProvisionResult, build_reg_link
from generative_design import generate_table_card, card_to_bytes
from pdf_generator import generate_table_tents_pdf, generate_single_table_preview
from page_images import page_images
from page_menu_manager import page_menu_manager

load_dotenv()

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID","")
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD","admin2024")
ROUTER_URL      = os.getenv("ROUTER_BASE_URL","https://your-api.onrender.com")
FRONTEND_URL    = os.getenv("FRONTEND_URL","https://your-menu.netlify.app")
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")
TG_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN","")
KITCHEN_URL     = os.getenv("KITCHEN_URL","https://kitchen-qr.netlify.app")

# ══════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════
st.set_page_config(page_title="👑 لوحة الإمبراطور", page_icon="👑",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&family=Outfit:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Outfit','Cairo',sans-serif!important}
.stApp{background:#080808!important;color:#f0f0f0}
section[data-testid="stSidebar"]{background:#0a0a0a!important;border-right:1px solid #1a1a1a}
.g-title{font-size:1.8rem;font-weight:900;text-align:center;padding:.4rem 0;
  background:linear-gradient(135deg,#C9A84C,#E8C97A,#C9A84C);background-size:200%;
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:gs 3s linear infinite}
@keyframes gs{0%{background-position:0%}100%{background-position:200%}}
.gdiv{height:1px;background:linear-gradient(90deg,transparent,#C9A84C22,transparent);margin:.8rem 0}
.s-card{background:#101010;border:1px solid #1a1a1a;border-radius:12px;padding:1.1rem;text-align:center}
.s-num{font-size:2.2rem;font-weight:900;color:#C9A84C;line-height:1}
.s-lbl{font-size:.75rem;color:#444;margin-top:.2rem}
.r-card{background:#101010;border:1px solid #1a1a1a;border-left:3px solid #C9A84C;
  border-radius:10px;padding:.8rem 1rem;margin-bottom:.5rem}
.r-name{font-size:.9rem;font-weight:700;color:#E8C97A}
.r-meta{font-size:.7rem;color:#444;margin-top:.2rem}
.res{border-radius:10px;padding:1rem 1.2rem;margin:.7rem 0;line-height:1.8}
.ok{background:rgba(0,230,118,.07);border:1px solid rgba(0,230,118,.2);color:#69f0ae}
.err{background:rgba(229,57,53,.07);border:1px solid rgba(229,57,53,.2);color:#ef9a9a}
.warn{background:rgba(255,193,7,.07);border:1px solid rgba(255,193,7,.2);color:#ffe57f}
.info-box{background:rgba(41,182,246,.07);border:1px solid rgba(41,182,246,.2);
  border-radius:10px;padding:1rem;color:#80d8ff;font-size:.85rem;line-height:1.8}
.tgbox{background:linear-gradient(135deg,rgba(0,136,204,.1),rgba(0,88,140,.06));
  border:1px solid rgba(0,136,204,.25);border-radius:12px;padding:1.1rem 1.3rem;margin:.7rem 0}
.iblk{background:#080818;border:1px solid #14143a;border-radius:10px;padding:.8rem 1rem}
.il{font-size:.72rem;font-weight:600;color:#3a3a7a;margin-bottom:.1rem}
.iv{color:#C9A84C;font-family:monospace;font-size:.85rem;word-break:break-all}
.badge{display:inline-block;padding:.12rem .55rem;border-radius:10px;font-size:.68rem;
  font-weight:600;background:rgba(201,168,76,.1);color:#C9A84C;border:1px solid rgba(201,168,76,.2)}
.badge-g{background:rgba(0,230,118,.1);color:#69f0ae;border-color:rgba(0,230,118,.2)}
.steps{display:flex;margin:1.2rem 0 .8rem;gap:0}
.stp{flex:1;text-align:center;padding:.5rem .2rem;font-size:.7rem;font-weight:700;
  color:#222;border-bottom:2px solid #1a1a1a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stp.done{color:#00e676;border-color:#00e676}
.stp.now{color:#C9A84C;border-color:#C9A84C}
.prg-out{background:#111;border-radius:6px;height:5px;overflow:hidden;margin:.4rem 0}
.prg-in{height:100%;border-radius:6px;background:linear-gradient(90deg,#C9A84C,#E8C97A)}
.stButton>button{background:linear-gradient(135deg,#C9A84C,#8a6020)!important;
  color:#000!important;font-weight:700!important;border:none!important;border-radius:8px!important;transition:all .2s!important}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 6px 20px rgba(201,168,76,.3)!important}
.stTextInput>div>div>input,.stTextArea textarea,.stSelectbox>div>div>div,.stNumberInput>div>div>input{
  background:#111!important;color:#eee!important;border:1px solid #222!important;border-radius:8px!important}
label{color:#555!important;font-size:.8rem!important}
.stTabs [data-baseweb="tab-list"]{background:#0e0e0e!important;border-radius:8px;padding:3px}
.stTabs [data-baseweb="tab"]{color:#444!important;border-radius:6px!important}
.stTabs [aria-selected="true"]{background:#C9A84C!important;color:#000!important;font-weight:700!important}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════
def auth():
    if st.session_state.get("ok"): return True
    st.markdown('<div class="g-title">👑 لوحة الإمبراطور</div>', unsafe_allow_html=True)
    col = st.columns([1,1.1,1])[1]
    with col:
        p = st.text_input("🔑 كلمة المرور", type="password")
        if st.button("دخول 🚀", use_container_width=True):
            if p == ADMIN_PASSWORD:
                st.session_state.ok = True; st.rerun()
            else:
                st.error("❌ كلمة مرور خاطئة")
    return False

# ══════════════════════════════════════════════════════════
# GOOGLE SHEETS — قراءة Master_DB
# ══════════════════════════════════════════════════════════
@st.cache_resource(ttl=300)
def gs():
    try:
        if SA_JSON_CONTENT:
            c = Credentials.from_service_account_info(json.loads(SA_JSON_CONTENT), scopes=SCOPES)
        else:
            c = Credentials.from_service_account_file(SA_JSON_PATH, scopes=SCOPES)
        return gspread.authorize(c)
    except Exception as e:
        st.error(f"❌ Google Auth: {e}"); return None

def fetch_all():
    """
    ✅ يقرأ من tab 'Master_DB' حصراً
    يحتوي على: restaurant_id | name | sheet_id | wifi_ssid | ...
    كل سطر = مطعم مختلف بـ sheet_id مختلف
    """
    c = gs()
    if not c or not MASTER_SHEET_ID: return []
    try:
        spread = c.open_by_key(MASTER_SHEET_ID)
        try:
            ws = spread.worksheet("Master_DB")
        except gspread.WorksheetNotFound:
            return []

        all_vals = ws.get_all_values()
        if not all_vals or len(all_vals) < 2: return []

        headers = all_vals[0]
        if "restaurant_id" not in headers: return []

        records = []
        for row in all_vals[1:]:
            if not any(c.strip() for c in row): continue
            padded = row + [''] * (len(headers) - len(row))
            rec = dict(zip(headers, padded))
            if rec.get("restaurant_id","").strip():
                records.append(rec)
        return records
    except Exception as e:
        st.error(f"Master DB: {e}"); return []

def del_r(rid):
    c = gs()
    if not c: return False
    try:
        ws = c.open_by_key(MASTER_SHEET_ID).worksheet("Master_DB")
        vals = ws.get_all_values()
        if not vals: return False
        h = vals[0]
        if "restaurant_id" not in h: return False
        ci = h.index("restaurant_id")
        for i, row in enumerate(vals[1:], start=2):
            if len(row) > ci and str(row[ci]) == str(rid):
                ws.delete_rows(i); return True
    except Exception as e:
        st.error(f"حذف: {e}")
    return False

def nxt(rs):
    if not rs: return "1"
    ids = [int(r.get("restaurant_id",0)) for r in rs
           if str(r.get("restaurant_id","")).isdigit()]
    return str(max(ids)+1) if ids else "1"

# ══════════════════════════════════════════════════════════
# صفحة: DASHBOARD
# ══════════════════════════════════════════════════════════
def pg_dashboard(rs):
    st.markdown('<div class="g-title">👑 لوحة الإمبراطور</div>', unsafe_allow_html=True)
    st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)

    # إحصائيات
    total   = len(rs)
    active  = sum(1 for r in rs if r.get("status","active") == "active")
    pending = sum(1 for r in rs if r.get("status","") == "pending_telegram")

    c1,c2,c3,c4 = st.columns(4)
    for col,n,lbl in [(c1,total,"🍽️ المطاعم"),(c2,active,"✅ نشطة"),
                       (c3,pending,"⏳ انتظار Telegram"),(c4,total-pending,"🤖 مربوط")]:
        col.markdown(f'<div class="s-card"><div class="s-num">{n}</div>'
                     f'<div class="s-lbl">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)

    # ── شرح كيف يعمل نظام التعدد ─────────────────────
    with st.expander("ℹ️ كيف يفرق النظام بين المطاعم؟"):
        st.markdown("""
        <div class="info-box">
        <b>🏗️ هيكل النظام:</b><br><br>

        <b>Master_DB tab</b> (فهرس كل المطاعم):<br>
        <code>rest_id=1 → sheet_id=ABC → مطعم محمد</code><br>
        <code>rest_id=2 → sheet_id=XYZ → مطعم علي</code><br>
        <code>rest_id=3 → sheet_id=QRS → مطعم سارة</code><br><br>

        <b>عندما يفتح الزبون القائمة:</b><br>
        <code>?rest_id=2</code> → API يبحث عن id=2 في Master_DB<br>
        → يجد sheet_id=XYZ → يقرأ <b>فقط</b> من Sheet مطعم علي<br>
        → لا يرى بيانات مطعم محمد أبداً ✅<br><br>

        <b>الصور:</b> تُضاف في عمود <code>image_url</code> في Sheet كل مطعم<br>
        أو من صفحة <b>🖼️ صور الأكلات</b> في الـ Dashboard
        </div>
        """, unsafe_allow_html=True)

    cl, cr = st.columns([3,2])
    with cl:
        st.markdown("### 🍽️ قائمة المطاعم")
        if not rs:
            st.info("📭 لا توجد مطاعم بعد — أضف أول مطعم من 🚀 إضافة مطعم")
        for r in rs:
            sm = {"luxury":"✨","modern":"⚡","classic":"🏛️"}
            st_cls = "badge-g" if r.get("status","active")=="active" else "badge"
            st_lbl = "🟢 نشط" if r.get("status","active")=="active" else "⏳ انتظار Telegram"
            mu = f"{FRONTEND_URL}?rest_id={r.get('restaurant_id')}"
            su = f"https://docs.google.com/spreadsheets/d/{r.get('sheet_id','')}/edit"
            st.markdown(f"""<div class="r-card">
              <div class="r-name">#{r.get('restaurant_id')} — {r.get('name','')}</div>
              <div class="r-meta">
                <span class="badge">{sm.get(r.get('style',''),'')} {r.get('style','')}</span>
                <span class="{st_cls}" style="margin-left:.4rem">{st_lbl}</span>
                &nbsp; 📶 {r.get('wifi_ssid','')} &nbsp; 🪑 {r.get('num_tables','')} طاولة
              </div>
              <div class="r-meta" style="margin-top:.3rem">
                📱 <a href="{mu}" target="_blank" style="color:#C9A84C">{mu}</a>
                &nbsp;|&nbsp;
                📊 <a href="{su}" target="_blank" style="color:#555">Sheet</a>
              </div></div>""", unsafe_allow_html=True)

    with cr:
        st.markdown("### 🔌 حالة الأنظمة")
        try:
            r = requests.get(f"{ROUTER_URL}/health", timeout=4)
            if r.status_code == 200:
                st.markdown('<div class="res ok">🟢 API يعمل بشكل طبيعي</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="res warn">🟡 API: {r.status_code}</div>', unsafe_allow_html=True)
        except:
            st.markdown('<div class="res err">🔴 API غير متاح (Render نائم؟)</div>', unsafe_allow_html=True)

        st.code(f"API:      {ROUTER_URL}\nFrontend: {FRONTEND_URL}")

        if st.button("🔄 تحديث Cache", key="dash_refresh"):
            try:
                requests.post(f"{ROUTER_URL}/cache/refresh", timeout=5)
                st.success("✅ Cache محدّث")
                st.cache_resource.clear()
                st.rerun()
            except:
                st.warning("API غير متاح")

# ══════════════════════════════════════════════════════════
# صفحة: إضافة مطعم
# ══════════════════════════════════════════════════════════
def pg_add(rs):
    st.markdown("## 🚀 إضافة مطعم جديد")
    SA_EMAIL = "restaurant-bot@gen-lang-client-0967477901.iam.gserviceaccount.com"

    st.markdown(f"""<div class="res warn">
    📋 <b>الخطوات لصاحب المطعم قبل الإضافة:</b><br>
    1️⃣ يفتح <a href="https://sheets.google.com" target="_blank" style="color:#C9A84C">sheets.google.com</a>
       → ينشئ Spreadsheet جديد<br>
    2️⃣ يشاركه مع <code style="color:#C9A84C">{SA_EMAIL}</code> كـ <b>Editor</b><br>
    3️⃣ ينسخ الـ ID من الرابط ويلصقه أسفل
    </div>""", unsafe_allow_html=True)

    t1,t2,t3 = st.tabs(["📋 المعلومات","🎨 الهوية البصرية","📶 WiFi"])

    with t1:
        c1,c2 = st.columns(2)
        with c1:
            rid      = st.text_input("🔢 رقم المطعم", value=nxt(rs))
            rname    = st.text_input("🏪 اسم المطعم *", placeholder="مطعم النخيل الذهبي")
            rsheetid = st.text_input("📊 Sheet ID *",
                                      placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
                                      help="ID من رابط الـ Spreadsheet الذي أنشأه صاحب المطعم")
            remail   = st.text_input("📧 بريد صاحب المطعم (للإيميل التلقائي)",
                                      placeholder="owner@gmail.com")
        with c2:
            rtables = st.number_input("🪑 عدد الطاولات", 1, 100, 10)
            rlogo   = st.text_input("🖼️ رابط اللوجو (اختياري)", placeholder="https://...")
            st.markdown("""<div class="res warn" style="font-size:.78rem;padding:.6rem .9rem">
            📨 <b>Telegram:</b> رابط تلقائي يُولد بعد الإنشاء<br>
            📧 <b>Gmail:</b> يرسل تلقائياً إذا أضفت GMAIL_USER في المتغيرات
            </div>""", unsafe_allow_html=True)

    defs = {"luxury":("#0a0804","#C9A84C"),"modern":("#121212","#00DCB4"),"classic":("#fcf8ee","#8B4513")}
    with t2:
        c1,c2 = st.columns(2)
        with c1:
            rstyle   = st.selectbox("🎭 الطابع", ["luxury","modern","classic"],
                format_func=lambda x:{"luxury":"✨ فاخر","modern":"⚡ عصري","classic":"🏛️ كلاسيكي"}[x])
            dp, da   = defs[rstyle]
            rprimary = st.color_picker("🎨 اللون الأساسي", dp)
            raccent  = st.color_picker("✨ لون التمييز", da)
        with c2:
            st.markdown("##### 👁️ معاينة")
            st.markdown(f"""<div style="background:{rprimary};border:2px solid {raccent};
              border-radius:12px;padding:1.5rem;text-align:center;margin-top:.5rem">
              <div style="color:{raccent};font-size:1.2rem;font-weight:900">
                {rname or "اسم المطعم"}</div>
              <div style="color:{raccent};opacity:.5;font-size:.8rem;margin-top:.4rem">{rstyle}</div>
            </div>""", unsafe_allow_html=True)

    with t3:
        c1,c2 = st.columns(2)
        with c1:
            rssid  = st.text_input("📶 اسم الشبكة (SSID) *", placeholder="Resto_WiFi")
            rwpass = st.text_input("🔒 كلمة مرور WiFi", type="password")

    st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)

    if st.button("🚀 إنشاء المطعم — كل شيء أوتوماتيكي!", use_container_width=True):
        errs = []
        if not rname.strip():    errs.append("اسم المطعم مطلوب")
        if not rsheetid.strip(): errs.append("Sheet ID مطلوب")
        if not rssid.strip():    errs.append("SSID مطلوب")
        if errs:
            for e in errs: st.error(f"❌ {e}")
            return

        steps_lbl = ["📊 الشيت","🔗 الـ Tabs","💾 Master_DB","🤖 Telegram","✅ اكتمل"]
        pb = st.empty(); pl = st.empty()

        def show(cur, logs):
            h = "".join(f'<div class="stp {"done" if i<cur else "now" if i==cur else ""}">{l}</div>'
                        for i,l in enumerate(steps_lbl))
            pct = int((cur/len(steps_lbl))*100)
            pb.markdown(f'<div class="steps">{h}</div>'
                        f'<div class="prg-out"><div class="prg-in" style="width:{pct}%"></div></div>',
                        unsafe_allow_html=True)
            pl.markdown(f'<div style="background:#050f05;border:1px solid #0a2a0a;border-radius:8px;'
                        f'padding:.8rem;font-family:monospace;font-size:.8rem;color:#69f0ae;line-height:1.7">'
                        f'{"<br>".join(logs)}</div>', unsafe_allow_html=True)

        show(0, ["⏳ جارٍ الإنشاء..."])
        result: ProvisionResult = provision_restaurant(
            restaurant_id=rid.strip(), name=rname.strip(),
            sheet_id=rsheetid.strip(),
            wifi_ssid=rssid.strip(), wifi_password=rwpass.strip(),
            style=rstyle, primary_color=rprimary, accent_color=raccent,
            num_tables=rtables, logo_url=rlogo.strip(), owner_email=remail.strip())

        done = len([s for s in result.steps if "✅" in s])
        show(min(done, len(steps_lbl)-1), result.steps)
        pb.empty(); pl.empty()

        if result.success:
            st.markdown(f'<div class="res ok"><b>🎉 تم إنشاء "{rname}" بنجاح!</b><br><br>'
                        f'{"<br>".join(result.steps)}</div>', unsafe_allow_html=True)
            mu = f"{FRONTEND_URL}?rest_id={rid}"
            su = f"https://docs.google.com/spreadsheets/d/{result.sheet_id}/edit"
            c1,c2,c3 = st.columns(3)
            c1.markdown(f'<div class="iblk"><div class="il">📱 رابط المينيو</div>'
                        f'<div class="iv"><a href="{mu}" target="_blank" style="color:#C9A84C">{mu}</a></div></div>',
                        unsafe_allow_html=True)
            c2.markdown(f'<div class="iblk"><div class="il">📊 Google Sheet</div>'
                        f'<div class="iv"><a href="{su}" target="_blank" style="color:#C9A84C">افتح الشيت</a></div></div>',
                        unsafe_allow_html=True)
            c3.markdown(f'<div class="iblk"><div class="il">🔢 رقم المطعم</div>'
                        f'<div class="iv">{rid}</div></div>', unsafe_allow_html=True)

            if result.reg_link:
                st.markdown(f"""<div class="tgbox">
                  <b style="color:#29b6f6">📨 رابط Telegram — أرسله لصاحب المطعم (مرة واحدة فقط):</b><br>
                  <div style="background:#0d1a24;border:1px solid rgba(0,136,204,.3);border-radius:8px;
                       padding:.6rem 1rem;font-family:monospace;color:#29b6f6;margin:.5rem 0">
                    {result.reg_link}
                  </div>
                  <small style="color:#555">صاحب المطعم يضغطه مرة واحدة → يتفعل تلقائياً</small>
                </div>""", unsafe_allow_html=True)
                st.code(result.reg_link, language=None)

            # ✅ رابط شاشة الكوزينة
            kitchen_link = f"{KITCHEN_URL}?api={ROUTER_URL}&rid={rid}"
            st.markdown(f"""<div style="background:rgba(255,152,0,.07);border:1px solid rgba(255,152,0,.2);
              border-radius:12px;padding:1rem 1.2rem;margin:.5rem 0">
              <b style="color:#ff9800">🍳 رابط شاشة الكوزينة — ضعه على التابليت:</b><br>
              <div style="background:#0a0800;border:1px solid rgba(255,152,0,.2);border-radius:8px;
                   padding:.6rem 1rem;font-family:monospace;font-size:.78rem;color:#ff9800;
                   word-break:break-all;margin:.5rem 0">{kitchen_link}</div>
              <small style="color:#555">📌 Bookmark على التابليت في الكوزينة</small>
            </div>""", unsafe_allow_html=True)
            st.code(kitchen_link, language=None)

            # توليد البطاقات
            st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)
            st.markdown("### 🔲 بطاقات الطاولات")

            with st.spinner("🎨 توليد البطاقات..."):
                menu_img, wifi_img = generate_table_card(
                    rname, rssid, rwpass, 1, f"{mu}&table=1",
                    rstyle, rprimary, raccent)
                mb = io.BytesIO(); menu_img.save(mb,"PNG"); mb.seek(0)
                wb = io.BytesIO(); wifi_img.save(wb,"PNG"); wb.seek(0)
                st.session_state.update({
                    "last_menu_bytes": mb.getvalue(),
                    "last_wifi_bytes": wb.getvalue(),
                    "last_rname": rname, "last_rssid": rssid,
                    "last_rwpass": rwpass, "last_mu": mu,
                    "last_rstyle": rstyle, "last_rprimary": rprimary,
                    "last_raccent": raccent, "last_rtables": rtables,
                    "last_rid": rid,
                })
                st.session_state.pop("last_pdf_bytes", None)

            _show_cards_and_pdf()
            st.cache_resource.clear()

            # خطوات ما بعد الإنشاء
            st.markdown("""<div class="res warn" style="margin-top:1rem">
            <b>✅ خطوات ما بعد الإنشاء:</b><br>
            1️⃣ أرسل رابط Telegram لصاحب المطعم → يضغطه مرة واحدة<br>
            2️⃣ اذهب لـ <b>🍽️ إدارة القائمة</b> → أضف الأكلات والأسعار<br>
            3️⃣ اذهب لـ <b>🖼️ صور الأكلات</b> → أضف الصور تلقائياً<br>
            4️⃣ اطبع PDF البطاقات من <b>🖨️ بطاقات PDF</b>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="res err"><b>❌ {result.error}</b><br>'
                        f'{"<br>".join(result.steps)}</div>', unsafe_allow_html=True)

    elif st.session_state.get("last_menu_bytes"):
        st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)
        st.markdown("### 🔲 بطاقات الطاولات (آخر إنشاء)")
        _show_cards_and_pdf()


def _show_cards_and_pdf():
    mb      = st.session_state.get("last_menu_bytes")
    wb      = st.session_state.get("last_wifi_bytes")
    rname   = st.session_state.get("last_rname","المطعم")
    rssid   = st.session_state.get("last_rssid","WiFi")
    rwpass  = st.session_state.get("last_rwpass","")
    rstyle  = st.session_state.get("last_rstyle","luxury")
    rp      = st.session_state.get("last_rprimary","#0a0804")
    ra      = st.session_state.get("last_raccent","#C9A84C")
    rtables = st.session_state.get("last_rtables",10)
    rid     = st.session_state.get("last_rid","1")
    if not mb or not wb: return

    qc1,qc2 = st.columns(2)
    with qc1:
        st.image(mb, caption="📱 QR المينيو — للطلب", use_column_width=True)
        st.download_button("⬇️ تحميل QR المينيو", mb,
            f"Menu_QR_{rname}.png","image/png",
            use_container_width=True, key="dl_menu_qr")
    with qc2:
        st.image(wb, caption="📶 QR WiFi — اتصال تلقائي", use_column_width=True)
        st.download_button("⬇️ تحميل QR WiFi", wb,
            f"WiFi_QR_{rname}.png","image/png",
            use_container_width=True, key="dl_wifi_qr")

    st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)

    if st.button(f"📄 توليد PDF كامل ({rtables} طاولة = {rtables*2} صفحة)",
                 use_container_width=True, key="btn_gen_pdf"):
        with st.spinner(f"⏳ {rtables*2} صفحة..."):
            try:
                from pdf_generator import generate_table_tents_pdf
                pdf = generate_table_tents_pdf(
                    rname, rssid, rwpass, FRONTEND_URL,
                    rid, rtables, rstyle, rp, ra)
                st.session_state["last_pdf_bytes"] = pdf
                st.session_state["last_pdf_name"]  = rname
            except Exception as e:
                st.error(f"❌ PDF: {e}")

    if st.session_state.get("last_pdf_bytes"):
        st.success(f"✅ PDF جاهز — {rtables} طاولة | {rtables*2} صفحة")
        st.download_button(
            f"⬇️ تحميل PDF ({rtables*2} صفحة)",
            st.session_state["last_pdf_bytes"],
            f"Tents_{st.session_state.get('last_pdf_name',rname)}.pdf",
            "application/pdf",
            use_container_width=True, key="dl_pdf_final")

# ══════════════════════════════════════════════════════════
# صفحة: بطاقات PDF
# ══════════════════════════════════════════════════════════
def pg_pdf(rs):
    st.markdown("## 🖨️ بطاقات الطاولات — PDF")
    if not rs: st.info("📭 أضف مطعماً أولاً"); return

    opts = {f"#{r.get('restaurant_id','?')} — {r.get('name','مطعم')}": r for r in rs}
    sel  = st.selectbox("🏪 المطعم", list(opts.keys()))
    r    = opts[sel]

    c1,c2 = st.columns(2)
    with c1:
        n  = st.number_input("عدد الطاولات",1,100,int(r.get("num_tables",10) or 10))
        pv = st.number_input("معاينة طاولة رقم",1,n,1)

    if st.button("👁️ معاينة", use_container_width=True, key="btn_preview"):
        with st.spinner("🎨..."):
            try:
                mi, wi = generate_single_table_preview(
                    r.get("name","مطعم"), r.get("wifi_ssid","WiFi"),
                    r.get("wifi_password",""), FRONTEND_URL,
                    r.get("restaurant_id","1"), pv,
                    r.get("style","luxury"), r.get("primary_color","#0a0804"),
                    r.get("accent_color","#C9A84C"))
                st.session_state["prev_m"] = card_to_bytes(mi)
                st.session_state["prev_w"] = card_to_bytes(wi)
            except Exception as e:
                st.error(f"❌ {e}")

    if st.session_state.get("prev_m"):
        ca,cb = st.columns(2)
        ca.image(st.session_state["prev_m"], caption=f"📱 QR المينيو T{pv}", use_column_width=True)
        cb.image(st.session_state["prev_w"], caption=f"📶 QR WiFi T{pv}", use_column_width=True)

    if st.button("📄 توليد PDF كامل", use_container_width=True, key="btn_pdf_pg"):
        with st.spinner(f"⏳ {n*2} صفحة..."):
            try:
                from pdf_generator import generate_table_tents_pdf
                pdf = generate_table_tents_pdf(
                    r.get("name","مطعم"), r.get("wifi_ssid","WiFi"),
                    r.get("wifi_password",""), FRONTEND_URL,
                    r.get("restaurant_id","1"), n,
                    r.get("style","luxury"), r.get("primary_color","#0a0804"),
                    r.get("accent_color","#C9A84C"))
                st.session_state["pg_pdf"] = pdf
                st.session_state["pg_pdf_nm"] = r.get("name","")
                st.session_state["pg_pdf_n"]  = n
            except Exception as e:
                st.error(f"❌ PDF: {e}")

    if st.session_state.get("pg_pdf"):
        _n = st.session_state.get("pg_pdf_n",n)
        st.success(f"✅ {_n} طاولة | {_n*2} صفحة جاهزة")
        st.download_button("⬇️ تحميل PDF",
            st.session_state["pg_pdf"],
            f"Tents_{st.session_state.get('pg_pdf_nm','')}.pdf",
            "application/pdf", use_container_width=True, key="dl_pg_pdf")

# ══════════════════════════════════════════════════════════
# صفحة: إدارة
# ══════════════════════════════════════════════════════════
def pg_manage(rs):
    st.markdown("## ⚙️ إدارة المطاعم")

    # Telegram Webhook
    st.markdown("### 🤖 Telegram Webhook")
    wh_url = f"{ROUTER_URL}/webhook/telegram"
    st.code(f"Webhook URL: {wh_url}")

    c1,c2 = st.columns(2)
    with c1:
        if st.button("🔗 تسجيل Webhook", key="reg_wh"):
            if not TG_TOKEN:
                st.error("❌ TELEGRAM_BOT_TOKEN غير محدد")
            else:
                try:
                    resp = requests.post(
                        f"https://api.telegram.org/bot{TG_TOKEN}/setWebhook",
                        json={"url": wh_url}, timeout=10)
                    d = resp.json()
                    if d.get("ok"):
                        st.success(f"✅ مسجل: {wh_url}")
                    else:
                        st.error(f"❌ {d.get('description')}")
                except Exception as e:
                    st.error(str(e))
    with c2:
        if st.button("🧪 اختبار البوت", key="test_bot"):
            if TG_TOKEN:
                try:
                    r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=5)
                    d = r.json()
                    if d.get("ok"):
                        b = d["result"]
                        st.success(f"✅ @{b.get('username')} — {b.get('first_name')}")
                    else:
                        st.error(str(d))
                except Exception as e:
                    st.error(str(e))

    st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)
    st.markdown("### 🍽️ قائمة المطاعم")
    if not rs: st.info("لا توجد مطاعم"); return

    for idx, r in enumerate(rs):
        rid    = str(r.get("restaurant_id", f"r{idx}"))
        uid    = f"{idx}_{rid}"
        status = r.get("status","active")
        icon   = "🟢" if status == "active" else "⏳"

        with st.expander(f"{icon} #{rid} — {r.get('name','?')}"):
            c1,c2,c3 = st.columns([2,2,1])
            with c1:
                sid = r.get("sheet_id","")
                su  = f"https://docs.google.com/spreadsheets/d/{sid}/edit" if sid else "#"
                st.markdown(f"""
                **📊 Sheet:** [{sid[:28] if sid else 'لا يوجد'}]({su})

                **📨 Telegram:** `{r.get('telegram_chat_id','⏳ لم يُربط بعد')}`

                **📶 WiFi:** `{r.get('wifi_ssid','')}` | `{r.get('wifi_password','')}`

                **🎨 طابع:** {r.get('style','')} | 🪑 {r.get('num_tables','')} طاولة
                """)
            with c2:
                mu = f"{FRONTEND_URL}?rest_id={rid}"
                st.code(mu)
                reg = build_reg_link(rid)
                if reg:
                    st.markdown("**🔗 رابط Telegram:**")
                    st.code(reg)
                if r.get("owner_email"):
                    st.markdown(f"**📧** {r.get('owner_email')}")
                kitchen_link = f"{KITCHEN_URL}?api={ROUTER_URL}&rid={rid}"
                st.markdown("**🍳 شاشة الكوزينة:**")
                st.code(kitchen_link)
            with c3:
                if st.button("🗑️ حذف", key=f"del_{uid}"):
                    if del_r(rid):
                        st.success("تم!")
                        st.cache_resource.clear()
                        st.rerun()
                if st.button("🔄 Cache", key=f"cache_{uid}"):
                    try:
                        requests.post(f"{ROUTER_URL}/cache/refresh", timeout=5)
                        st.success("✅")
                    except:
                        st.warning("API غير متاح")
                if st.button("🔴 تعطيل" if status=="active" else "🟢 تفعيل",
                             key=f"tog_{uid}"):
                    st.info("ميزة قريباً")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    if not auth(): return
    rs = fetch_all()

    with st.sidebar:
        st.markdown('<div style="color:#C9A84C;font-size:1.1rem;font-weight:900;'
                    'text-align:center;padding:.5rem 0">👑 الإمبراطور</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div style="text-align:center;color:#444;font-size:.75rem">'
                    f'{len(rs)} مطعم مسجّل</div>', unsafe_allow_html=True)
        st.markdown("---")
        page = st.radio("", [
            "🏠 Dashboard",
            "🚀 إضافة مطعم",
            "🍽️ إدارة القائمة",
            "🖼️ صور الأكلات",
            "🖨️ بطاقات PDF",
            "⚙️ إدارة",
        ], label_visibility="hidden")
        st.markdown("---")
        if st.button("🚪 خروج", use_container_width=True, key="btn_logout"):
            st.session_state.ok = False; st.rerun()

    if   page == "🏠 Dashboard":      pg_dashboard(rs)
    elif page == "🚀 إضافة مطعم":    pg_add(rs)
    elif page == "🍽️ إدارة القائمة": page_menu_manager(rs)
    elif page == "🖼️ صور الأكلات":   page_images(rs)
    elif page == "🖨️ بطاقات PDF":    pg_pdf(rs)
    elif page == "⚙️ إدارة":          pg_manage(rs)

if __name__ == "__main__":
    main()
