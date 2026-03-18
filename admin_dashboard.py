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
from generative_design import generate_table_card, card_to_bytes, STYLE_LABELS, BG_LABELS, SOCIAL_CONFIG
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

# مفاتيح الصور للخلفية food_photo
PEXELS_KEY    = os.getenv("PEXELS_API_KEY","")
UNSPLASH_KEY  = os.getenv("UNSPLASH_ACCESS_KEY","")
PIXABAY_KEY   = os.getenv("PIXABAY_API_KEY","")

# ══════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════
st.set_page_config(page_title="👑 لوحة الإمبراطور", page_icon="👑",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&family=Outfit:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Outfit','Cairo',sans-serif!important}

/* ══════════ المتغيرات — الليل (افتراضي) ══════════ */
:root{
  --bg:#080808; --bg2:#101010; --bg3:#1a1a1a;
  --sidebar:#0a0a0a; --sidebar2:#111;
  --text:#f0f0f0; --text2:#aaa; --text3:#555;
  --border:#222; --border2:#1a1a1a;
  --input-bg:#111; --input-text:#eee; --input-border:#222;
  --gold:#C9A84C; --gold2:#E8C97A;
  --card-bg:#101010; --card-border:#1a1a1a;
  --tab-bg:#0e0e0e; --tab-text:#444;
  --placeholder:#444;
}

/* ══════════ المتغيرات — النهار ══════════ */
body.day-theme{
  --bg:#f5f0e8; --bg2:#ede8dc; --bg3:#e0d8c8;
  --sidebar:#ede8dc; --sidebar2:#e0d8c8;
  --text:#1a1208; --text2:#5a4020; --text3:#8a7050;
  --border:#c8b898; --border2:#d5c9a8;
  --input-bg:#ffffff; --input-text:#1a1208; --input-border:#c8b898;
  --gold:#b8860b; --gold2:#8a6010;
  --card-bg:#e8e0d0; --card-border:#c8b898;
  --tab-bg:#ddd5c0; --tab-text:#5a4020;
  --placeholder:#a09070;
}

/* ══════════ تطبيق المتغيرات ══════════ */
.stApp,[data-testid="stAppViewContainer"],[data-testid="stAppViewBlockContainer"],
.main,.block-container,[data-testid="stHeader"]
{background:var(--bg)!important;color:var(--text)!important}

section[data-testid="stSidebar"],
section[data-testid="stSidebar"]>div
{background:var(--sidebar)!important}
section[data-testid="stSidebar"] *{color:var(--text)!important}

/* ══ كل الحقول ══ */
.stTextInput>div>div>input,
.stTextArea textarea,
.stNumberInput>div>div>input,
.stNumberInput input,
[data-baseweb="input"] input,
[data-baseweb="textarea"],
input[type="text"],input[type="email"],input[type="tel"],
input[type="number"],input[type="password"],input[type="url"],
textarea
{background:var(--input-bg)!important;color:var(--input-text)!important;
 border-color:var(--input-border)!important;border-radius:8px!important}

/* placeholder */
::placeholder{color:var(--placeholder)!important;opacity:1!important}
::-webkit-input-placeholder{color:var(--placeholder)!important}
::-moz-placeholder{color:var(--placeholder)!important}

/* ══ أزرار number ══ */
.stNumberInput button,[data-baseweb="input"] button
{background:var(--bg3)!important;color:var(--text)!important;border-color:var(--border)!important}

/* ══ selectbox ══ */
.stSelectbox>div>div,.stSelectbox>div>div>div,
[data-baseweb="select"]>div,
[data-baseweb="select"] [class*="control"],
[data-baseweb="select"] [class*="valueContainer"],
[data-baseweb="select"] [class*="singleValue"],
[data-baseweb="select"] [class*="placeholder"]
{background:var(--input-bg)!important;color:var(--input-text)!important;
 border-color:var(--input-border)!important}

[data-baseweb="popover"],[data-baseweb="popover"] *,
[data-baseweb="menu"],[data-baseweb="menu"] *,
[role="listbox"],[role="listbox"] *,[role="option"]
{background:var(--input-bg)!important;color:var(--input-text)!important}
[role="option"]:hover{background:var(--bg2)!important}

/* ══ tabs ══ */
.stTabs [data-baseweb="tab-list"]{background:var(--tab-bg)!important;border-radius:8px;padding:3px}
.stTabs [data-baseweb="tab"]{color:var(--tab-text)!important;border-radius:6px!important}
.stTabs [aria-selected="true"]{background:var(--gold)!important;color:#000!important;font-weight:700!important}
[data-baseweb="tab-panel"]{background:var(--bg)!important}
[data-baseweb="tab-panel"] *{color:var(--text)!important}

/* ══ labels & text ══ */
label{color:var(--text2)!important;font-size:.8rem!important}
p,span,li,td,th,a,.stMarkdown *{color:var(--text)!important}
h1,h2,h3,h4{color:var(--gold)!important}

/* ══ كروت مخصصة ══ */
.s-card,.r-card,.iblk,.tgbox,.info-box,.res
{background:var(--card-bg)!important;border-color:var(--card-border)!important}
.s-num,.r-name,.iv{color:var(--gold)!important}
.s-lbl,.r-meta,.il{color:var(--text2)!important}
.ok{color:#69f0ae!important}
.err{color:#ef9a9a!important}
.warn{color:#ffe57f!important}

/* ══ g-title — gradient يبقى دائماً ══ */
.g-title{background:linear-gradient(135deg,#C9A84C,#E8C97A,#C9A84C)!important;
  background-size:200%!important;-webkit-background-clip:text!important;
  -webkit-text-fill-color:transparent!important;animation:gs 3s linear infinite!important}
@keyframes gs{0%{background-position:0%}100%{background-position:200%}}

/* ══ expander ══ */
[data-testid="stExpander"],[data-testid="stExpander"]>div,
[data-testid="stExpander"] summary,
[data-testid="stExpanderDetails"],
[data-testid="stExpanderDetails"] *
{background:var(--bg2)!important;color:var(--text)!important}

/* ══ steps ══ */
.stp{color:var(--text3)!important;border-color:var(--border)!important}
.stp.done{color:#00e676!important;border-color:#00e676!important}
.stp.now{color:var(--gold)!important;border-color:var(--gold)!important}
.prg-out{background:var(--bg3)!important}

/* ══ radio & checkbox ══ */
[data-testid="stRadio"] p,[data-testid="stCheckbox"] p{color:var(--text)!important}

/* ══ metric ══ */
[data-testid="stMetricValue"],[data-testid="stMetricLabel"]{color:var(--text)!important}

/* ══ code ══ */
code,pre{background:var(--bg3)!important;color:var(--gold2)!important}

/* ══ أزرار ══ */
.stButton>button{background:linear-gradient(135deg,#C9A84C,#8a6020)!important;
  color:#000!important;font-weight:700!important;border:none!important;
  border-radius:8px!important;transition:all .2s!important}
.stButton>button:hover{transform:translateY(-2px)!important;
  box-shadow:0 6px 20px rgba(201,168,76,.3)!important}

/* ══ color picker — لا نلمسه ══ */
[data-testid="stColorPicker"] label{color:var(--text2)!important}

/* ══ gdiv ══ */
.gdiv{height:1px;background:linear-gradient(90deg,transparent,#C9A84C22,transparent);margin:.8rem 0}
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
@st.cache_resource(ttl=600)  # 10 دقائق بدل 5
def gs():
    try:
        if SA_JSON_CONTENT:
            c = Credentials.from_service_account_info(json.loads(SA_JSON_CONTENT), scopes=SCOPES)
        else:
            c = Credentials.from_service_account_file(SA_JSON_PATH, scopes=SCOPES)
        return gspread.authorize(c)
    except Exception as e:
        st.error(f"❌ Google Auth: {e}"); return None

def _safe_int(val, default=10, lo=1, hi=100):
    """يحوّل أي قيمة لـ int بأمان — يتجاهل النصوص والفراغات"""
    try:
        v = int(str(val).strip().split(".")[0])
        return max(lo, min(hi, v))
    except:
        return default

def _safe_str(val, default=""):
    """يضمن أن القيمة نص نظيف"""
    s = str(val).strip() if val is not None else ""
    return s if s not in ("None","nan","NaN") else default

def _sanitize_record(rec: dict) -> dict:
    """
    يُنظّف كل حقل في سجل المطعم بعد قراءته من الشيت.
    يتعامل مع: أعمدة مختلطة، قيم فارغة، نصوص بدل أرقام...
    """
    import json as _json

    # حقول نصية عادية
    for f in ["restaurant_id","name","sheet_id","telegram_chat_id",
              "wifi_ssid","wifi_password","primary_color","accent_color",
              "style","logo_url","owner_email","status","created_at"]:
        rec[f] = _safe_str(rec.get(f,""))

    # ألوان — قيمة افتراضية إذا غير صالحة
    if not rec["primary_color"].startswith("#"):
        rec["primary_color"] = "#0a0804"
    if not rec["accent_color"].startswith("#"):
        rec["accent_color"] = "#C9A84C"

    # style — قيمة افتراضية
    if rec["style"] not in ("luxury","classic","modern","bold","neon","rustic",""):
        rec["style"] = "luxury"
    if not rec["style"]:
        rec["style"] = "luxury"

    # bg_type
    bg = _safe_str(rec.get("bg_type",""))
    rec["bg_type"] = bg if bg in ("minimal","food_photo","gradient") else "minimal"

    # num_tables — عدد صحيح بين 1 و 200
    rec["num_tables"] = _safe_int(rec.get("num_tables", 10), default=10, lo=1, hi=200)

    # socials — dict دائماً
    raw = rec.get("socials","")
    if isinstance(raw, dict):
        rec["socials"] = raw
    elif isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            rec["socials"] = _json.loads(raw)
        except:
            rec["socials"] = {}
    else:
        rec["socials"] = {}

    return rec

@st.cache_data(ttl=30)   # ✅ إصلاح: 30 ثانية بدل 120 — تحديث أسرع بعد أي تغيير
def fetch_all():
    """
    ✅ يقرأ من tab 'Master_DB' حصراً
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
                records.append(_sanitize_record(rec))
        return records
    except Exception as e:
        # عند خطأ 429 — لا نُظهر خطأ ونرجع قائمة فارغة بصمت
        if "429" in str(e) or "Quota" in str(e):
            st.warning("⚠️ Google Sheets: حد الطلبات مؤقتاً — انتظر دقيقة", icon="⏳")
        else:
            st.error(f"Master DB: {e}")
        return []

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
            except:
                st.warning("⚠️ API غير متاح")
            # ✅ إصلاح: مسح كل الـ cache — st.cache_data + st.cache_resource
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

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

    defs = {
        "luxury":  ("#0a0804","#C9A84C"),
        "modern":  ("#121212","#00DCB4"),
        "classic": ("#fcf8ee","#8B4513"),
        "bold":    ("#1a0a00","#FF6B35"),
        "neon":    ("#050510","#00FF88"),
        "rustic":  ("#2d1b0a","#D4A853"),
    }
    with t2:
        c1,c2 = st.columns(2)
        with c1:
            rstyle   = st.selectbox("🎭 الطابع",
                list(STYLE_LABELS.keys()),
                format_func=lambda x: STYLE_LABELS.get(x, x))
            dp, da   = defs.get(rstyle, ("#0a0804","#C9A84C"))
            rprimary = st.color_picker("🎨 اللون الأساسي", dp)
            raccent  = st.color_picker("✨ لون التمييز", da)
            rbg_type = st.selectbox("🖼️ خلفية البطاقة",
                list(BG_LABELS.keys()),
                format_func=lambda x: BG_LABELS.get(x, x))
            # نوع المطعم — لتحديد خلفية مناسبة
            VENUE_TYPES = {
                "restaurant":  "🍽️ مطعم عادي",
                "cafe":        "☕ مقهى / كافيه",
                "fastfood":    "🍔 وجبات سريعة",
                "pizza":       "🍕 بيتزا",
                "seafood":     "🦞 مأكولات بحرية",
                "moroccan":    "🍲 مطعم مغربي",
                "grill":       "🔥 مشويات / شواء",
                "sushi":       "🍣 سوشي / آسيوي",
                "pastry":      "🥐 حلويات / مخبزة",
                "juice":       "🥤 عصائر ومشروبات",
            }
            VENUE_QUERIES = {
                "restaurant": ["fine dining restaurant food","elegant restaurant interior","gourmet food plating"],
                "cafe":       ["coffee shop cozy","cafe latte art","coffee beans barista"],
                "fastfood":   ["burger fast food","fries hamburger","fast food restaurant"],
                "pizza":      ["pizza wood fired","italian pizza restaurant","pizza chef making"],
                "seafood":    ["seafood platter fresh","grilled fish restaurant","lobster seafood"],
                "moroccan":   ["moroccan tagine food","couscous moroccan","moroccan restaurant interior"],
                "grill":      ["bbq grilled meat","steakhouse grill","charcoal grilled food"],
                "sushi":      ["sushi restaurant japanese","sushi platter fresh","japanese food"],
                "pastry":     ["pastry bakery","croissant pastry shop","patisserie cake"],
                "juice":      ["fresh juice colorful","smoothie bar","tropical fruit drinks"],
            }
            rvenue_type = st.selectbox("🏪 نوع المطعم (للخلفية)",
                list(VENUE_TYPES.keys()),
                format_func=lambda x: VENUE_TYPES.get(x,x),
                key="add_venue_type")
        with c2:
            st.markdown("##### 👁️ معاينة")
            st.markdown(f"""<div style="background:{rprimary};border:2px solid {raccent};
              border-radius:12px;padding:1.5rem;text-align:center;margin-top:.5rem">
              <div style="color:{raccent};font-size:1.2rem;font-weight:900">
                {rname or "اسم المطعم"}</div>
              <div style="color:{raccent};opacity:.5;font-size:.8rem;margin-top:.4rem">
                {STYLE_LABELS.get(rstyle,rstyle)} · {BG_LABELS.get(rbg_type,rbg_type)}</div>
            </div>""", unsafe_allow_html=True)

    # ── تبويب جديد: مواقع التواصل ─────────────────────────
    st.markdown("##### 📱 مواقع التواصل الاجتماعي (اختياري)")
    st.markdown('<div style="color:#888;font-size:.82rem;margin-bottom:.5rem">تظهر أسفل بطاقة QR — اتركها فارغة إذا لم تريدها</div>', unsafe_allow_html=True)
    soc_c1, soc_c2, soc_c3, soc_c4 = st.columns(4)
    with soc_c1:
        s_instagram = st.text_input("📷 Instagram", placeholder="@restaurant", key="add_ig")
        s_facebook  = st.text_input("👍 Facebook",  placeholder="NomPage",     key="add_fb")
    with soc_c2:
        s_whatsapp  = st.text_input("💬 WhatsApp",  placeholder="+212600000000", key="add_wa")
        s_tiktok    = st.text_input("🎵 TikTok",    placeholder="@handle",      key="add_tt")
    with soc_c3:
        s_website   = st.text_input("🌐 Site Web",  placeholder="www.resto.ma", key="add_ws")
        s_phone     = st.text_input("📞 Téléphone", placeholder="+212600000000", key="add_ph")
    with soc_c4:
        s_snapchat  = st.text_input("👻 Snapchat",  placeholder="@handle",      key="add_sc")
        s_youtube   = st.text_input("▶️ YouTube",   placeholder="@channel",     key="add_yt")
    rsocials = {k:v for k,v in {
        "instagram": s_instagram, "facebook": s_facebook,
        "whatsapp": s_whatsapp,   "tiktok": s_tiktok,
        "website": s_website,     "phone": s_phone,
        "snapchat": s_snapchat,   "youtube": s_youtube,
    }.items() if v.strip()}

    with t3:
        c1,c2 = st.columns(2)
        with c1:
            rssid  = st.text_input("📶 اسم الشبكة (SSID) *", placeholder="Resto_WiFi")
            rwpass = st.text_input("🔒 كلمة مرور WiFi", type="password")
        with c2:
            st.markdown('<div style="color:#C9A84C;font-size:.85rem;font-weight:700;margin-bottom:.4rem">🍳 كلمة مرور الكوزينة</div>', unsafe_allow_html=True)
            rkitchen_pass = st.text_input("🔑 كلمة مرور الكوزينة *",
                type="password", placeholder="كلمة مرور يعرفها الطاهي فقط",
                help="يحتاجها الطاهي لفتح شاشة الكوزينة — لا يعرفها الزباءن")

        # ✅ خيار التوصيل
        st.markdown("---")
        st.markdown('<div style="color:#C9A84C;font-size:.9rem;font-weight:700;margin-bottom:.5rem">🛵 خدمة التوصيل</div>', unsafe_allow_html=True)
        rdelivery = st.toggle(
            "تفعيل خيار التوصيل للمنزل 🛵",
            value=False,
            help="إذا فعّلت هذا الخيار، سيظهر للزبون زران: 🍽️ أكل في المطعم | 🛵 توصيل للمنزل"
        )
        if rdelivery:
            st.info("✅ عند التفعيل، الزبون سيختار بين الأكل في المطعم أو التوصيل مع تحديد موقعه GPS")

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
            num_tables=rtables, logo_url=rlogo.strip(), owner_email=remail.strip(),
            bg_type=rbg_type, socials=rsocials,
            kitchen_password=rkitchen_pass.strip(),
            delivery_active=rdelivery)

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


            # ✅ نتيجة إنشاء المطعم
            if result.kitchen_url:
                st.markdown("**🍳 بشاشة الكوزينة:**")
                st.code(result.kitchen_url)

            if result.sheet_url:
                st.markdown(f"**📊 Google Sheet:** [افتح الشيت]({result.sheet_url})")

            if result.error:
                st.error(result.error)

            if result.steps:
                with st.expander("📋 تفاصيل الإنشاء"):
                    for step in result.steps:
                        st.write(step)



# ══════════════════════════════════════════════════════════
def pg_manage(rs):
    """⚙️ إدارة المطاعم — الأصلية"""
    st.markdown("## ⚙️ إدارة المطاعم")

    # ── Telegram Webhook ──
    with st.expander("🤖 Telegram Webhook", expanded=False):
        wh_url = f"{ROUTER_URL}/webhook/telegram"
        col_wh1, col_wh2 = st.columns(2)
        with col_wh1:
            if st.button("📡 تسجيل Webhook", use_container_width=True,
                         help=wh_url):
                try:
                    resp = requests.post(
                        f"https://api.telegram.org/bot{TG_TOKEN}/setWebhook",
                        json={"url": wh_url,
                              "allowed_updates": ["message","callback_query","my_chat_member"]},
                        timeout=10)
                    d = resp.json()
                    if d.get("ok"): st.success("✅ Webhook مسجل!")
                    else:           st.error(f"❌ {d.get('description')}")
                except Exception as e: st.error(f"❌ {e}")
        with col_wh2:
            if st.button("🔍 اختبار البوت", use_container_width=True):
                try:
                    r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=8)
                    d = r.json()
                    if d.get("ok"):
                        b = d["result"]
                        st.success(f"✅ @{b.get('username')} — {b.get('first_name')}")
                    else: st.error("❌ Token خاطئ")
                except Exception as e: st.error(f"❌ {e}")

    st.markdown("---")

    # ── قائمة المطاعم ──
    # rs هي list من fetch_all()
    if not rs:
        st.info("لا يوجد مطاعم بعد — أضف مطعماً من 'إضافة مطعم'")
        return

    for r in rs:
        rid   = str(r.get("restaurant_id","?")).strip()
        rname = r.get("name","مطعم")

        with st.expander(f"🍽️ #{rid} — {rname}", expanded=False):
            c1, c2 = st.columns(2)

            with c1:
                # ── معلومات ──
                sid = r.get("sheet_id","")
                if sid:
                    st.markdown(f"**📊 Sheet:** [{sid[:20]}...](https://docs.google.com/spreadsheets/d/{sid}/edit)")
                st.markdown(f"**📟 Telegram (رئيسي):** `{r.get('telegram_chat_id','') or 'لم يُربط'}`")
                st.markdown(f"**👑 Boss chat_id:** `{r.get('boss_chat_id','') or '❌ لم يُربط'}`")
                st.markdown(f"**🍽️ النوادل chat_id:** `{r.get('waiters_chat_id','') or '❌ لم يُربط'}`")
                st.markdown(f"**🛵 التوصيل chat_id:** `{r.get('delivery_chat_id','') or '❌ لم يُربط'}`")
                st.markdown(f"**📶 WiFi:** {r.get('wifi_ssid','')} | {r.get('wifi_password','')}")
                st.markdown(f"**🎨 طابع:** {r.get('style','')} | 🪑 {r.get('num_tables','')} طاولة")
                st.markdown(f"**🔑 كلمة سر الكوزينة:** `{r.get('kitchen_password','')}`")
                delivery_on = str(r.get("delivery_active","")).lower() in ("true","1","yes")
                st.markdown(f"**🛵 التوصيل:** {'✅ مفعّل' if delivery_on else '❌ مغلق'}")

            with c2:
                # ── روابط ──
                mu = f"{FRONTEND_URL}?rest_id={rid}"
                st.markdown(f"**🌐 رابط المينيو:**")
                st.code(mu)

                bot_username = os.getenv("TELEGRAM_BOT_USERNAME","Ayoub_Resto_bot")
                kitchen_link = f"{KITCHEN_URL}?api={ROUTER_URL}&rid={rid}&name={requests.utils.quote(rname)}"
                st.markdown("**🍳 بشاشة الكوزينة:**")
                st.code(kitchen_link)

                st.markdown("**🔗 رابط Telegram:**")
                st.markdown(f"""
👑 **المدير (أنت)** — يفتح هذا الرابط في محادثته مع البوت:
`https://t.me/{bot_username}?start=boss_{rid}`

🍽️ **مجموعة السيرفورات** — خطوتين:
1. أضف البوت `@{bot_username}` للمجموعة
2. أرسل في المجموعة: `/ربط waiters_{rid}`

🛵 **مجموعة التوصيل** — خطوتين:
1. أضف البوت `@{bot_username}` للمجموعة
2. أرسل في المجموعة: `/ربط delivery_{rid}`
""")
                st.code(f"/ربط waiters_{rid}", language=None)
                st.code(f"/ربط delivery_{rid}", language=None)

            # ── أزرار الإجراءات ──
            uid = f"{rid}_{rname}"
            col_a, col_b, col_c = st.columns(3)

            with col_a:
                # تفعيل/إلغاء التوصيل
                dlv_label = "🛵 إلغاء التوصيل" if delivery_on else "🛵 تفعيل التوصيل"
                if st.button(dlv_label, key=f"del_tog_{uid}", use_container_width=True):
                    new_val = "false" if delivery_on else "true"
                    try:
                        import gspread as _gsp
                        from google.oauth2.service_account import Credentials as _Cr
                        import json as _jj
                        _SA  = os.getenv("GOOGLE_SA_JSON_CONTENT","")
                        _MSI = os.getenv("MASTER_SHEET_ID","")
                        if _SA and _MSI:
                            _cr  = _Cr.from_service_account_info(_jj.loads(_SA),
                                       scopes=["https://www.googleapis.com/auth/spreadsheets"])
                            _cl  = _gsp.authorize(_cr)
                            _ws  = _cl.open_by_key(_MSI).worksheet("Master_DB")
                            _hd  = _ws.row_values(1)
                            if "delivery_active" not in _hd:
                                _ws.update_cell(1, len(_hd)+1, "delivery_active")
                                _hd.append("delivery_active")
                            _dc  = _hd.index("delivery_active") + 1
                            _rc  = _hd.index("restaurant_id")   if "restaurant_id" in _hd else 0
                            for _i, _row in enumerate(_ws.get_all_values()[1:], start=2):
                                if len(_row) > _rc and str(_row[_rc]).strip() == rid:
                                    _ws.update_cell(_i, _dc, new_val); break
                        requests.post(f"{ROUTER_URL}/cache/refresh/{rid}",
                                      headers={"X-Admin-Key": ADMIN_PASSWORD}, timeout=8)
                        requests.post(f"{ROUTER_URL}/cache/refresh",
                                      headers={"X-Admin-Key": ADMIN_PASSWORD}, timeout=8)
                        st.cache_data.clear()
                        st.success(f"التوصيل {'مفعّل ✅' if new_val=='true' else 'ملغى ✅'}")
                        st.rerun()
                    except Exception as _e: st.error(f"❌ {_e}")

            with col_b:
                if st.button("🔄 تطبيق فوري", key=f"ref_del_{uid}", use_container_width=True):
                    try:
                        requests.post(f"{ROUTER_URL}/cache/refresh/{rid}",
                                      headers={"X-Admin-Key": ADMIN_PASSWORD}, timeout=10)
                        requests.post(f"{ROUTER_URL}/cache/refresh",
                                      headers={"X-Admin-Key": ADMIN_PASSWORD}, timeout=10)
                    except: pass
                    st.cache_data.clear()
                    st.success("✅ تم التطبيق الفوري!")
                    st.rerun()

            with col_c:
                if st.button("🗑️ حذف", key=f"del_{uid}", use_container_width=True):
                    st.session_state[f"confirm_del_{uid}"] = True

            if st.session_state.get(f"confirm_del_{uid}"):
                st.warning(f"⚠️ حذف {rname}؟ لا يمكن التراجع!")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ تأكيد الحذف", key=f"conf_{uid}"):
                        try:
                            requests.delete(f"{ROUTER_URL}/restaurants/{rid}",
                                            headers={"X-Admin-Key": ADMIN_PASSWORD}, timeout=10)
                        except: pass
                        st.cache_data.clear()
                        st.session_state.pop(f"confirm_del_{uid}", None)
                        st.rerun()
                with cc2:
                    if st.button("❌ إلغاء", key=f"canc_{uid}"):
                        st.session_state.pop(f"confirm_del_{uid}", None)
                        st.rerun()


def pg_main():
    """الصفحة الرئيسية — إحصائيات سريعة"""
    st.markdown("## 📊 Dashboard")
    records = fetch_all()  # list of dicts
    if not records:
        st.info("لا يوجد مطاعم — أضف مطعماً أولاً")
        return
    total  = len(records)
    active = sum(1 for r in records if r.get("status","") == "active")
    st.metric("إجمالي المطاعم", total)
    st.metric("المطاعم النشطة", active)
    for r in records:
        rid = r.get("restaurant_id","?")
        st.markdown(f"**#{rid}** — {r.get('name','')} | {r.get('status','')}")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        st.markdown("## 👑 الإمبراطور — تسجيل الدخول")
        pwd = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("❌ كلمة المرور خاطئة")
        return

    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👑 الإمبراطور")
        rs = fetch_all()
        st.caption(f"مطعم مسجّل {len(rs)}")
        st.markdown("---")
        pages = {
            "📊 Dashboard":        "main",
            "➕ إضافة مطعم":      "add",
            "⚙️ إدارة القائمة":   "manage",
            "🖼️ صور الأكلات":     "images",
            "📋 إدارة القائمة":   "menu",
            "🖨️ بطاقات PDF":       "pdf",
            "⚙️ إدارة":            "settings",
        }
        if "page" not in st.session_state:
            st.session_state.page = "main"
        for label, key in pages.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()
        st.markdown("---")
        if st.button("🌙 وضع الليل" if st.session_state.get("theme","dark")=="dark" else "☀️ النهار",
                     use_container_width=True):
            st.session_state.theme = "light" if st.session_state.get("theme","dark")=="dark" else "dark"
        if st.button("📤 خروج", use_container_width=True):
            st.session_state.auth = False
            st.rerun()

    page = st.session_state.get("page","main")
    rs   = fetch_all()

    if page == "main":       pg_dashboard(rs)
    elif page == "add":      pg_add()
    elif page == "manage":   pg_manage(rs)
    elif page == "images":   show("صور الأكلات", "images")
    elif page == "menu":     show("إدارة القائمة", "menu")
    elif page == "pdf":      show("بطاقات PDF", "pdf")
    elif page == "settings": show("إدارة", "settings")


if __name__ == "__main__":
    main()
