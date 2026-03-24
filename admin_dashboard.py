"""
👑 admin_dashboard.py — لوحة التحكم الرئيسية
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 Supabase ← مصدر البيانات الرئيسي
   fetch_all()        → يقرأ المطاعم من Supabase
   _update_master_field() → يكتب في Supabase
   pg_plans()         → يحفظ الباقات في Supabase
   page_agencies()    → يدير الوكالات عبر API→Supabase

📋 Google Sheets ← قراءة المنيو فقط
   page_menu_manager() → يعدّل الأكلات والأسعار
   page_images()       → يعدّل صور الأكلات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import streamlit as st
import gspread, io, os, json, time, requests
from google.oauth2.service_account import Credentials
from datetime import datetime
from dotenv import load_dotenv

from auto_provisioner import provision_restaurant, ProvisionResult, build_reg_link
from super_admin_agencies import page_agencies
from generative_design import generate_table_card, card_to_bytes, STYLE_LABELS, BG_LABELS, SOCIAL_CONFIG
from pdf_generator import generate_table_tents_pdf, generate_single_table_preview
from page_images import page_images
from page_menu_manager import page_menu_manager

load_dotenv()

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID","")
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD","admin2024")
ROUTER_URL      = os.getenv("ROUTER_BASE_URL","https://your-api.onrender.com")
SUPABASE_URL    = os.getenv("SUPABASE_URL","")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY","")

# ══════════════════════════════════════════════════════════
# 🗄️ Supabase Direct Helpers — للداشبورد
# ══════════════════════════════════════════════════════════
def _sb_get(table, filters="", limit=500):
    """جلب مباشر من Supabase REST API"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        import requests as _rq
        h = {"apikey": SUPABASE_KEY,
             "Authorization": f"Bearer {SUPABASE_KEY}",
             "Content-Type": "application/json"}
        url = f"{SUPABASE_URL}/rest/v1/{table}?limit={limit}"
        if filters:
            url += f"&{filters}"
        r = _rq.get(url, headers=h, timeout=10)
        return r.json() if r.status_code == 200 else []
    except:
        return []

def _sb_patch(table, filters, data):
    """تحديث مباشر في Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        import requests as _rq
        h = {"apikey": SUPABASE_KEY,
             "Authorization": f"Bearer {SUPABASE_KEY}",
             "Content-Type": "application/json",
             "Prefer": "return=minimal"}
        r = _rq.patch(f"{SUPABASE_URL}/rest/v1/{table}?{filters}",
                      headers=h, json=data, timeout=8)
        return r.status_code in (200, 204)
    except:
        return False

def fetch_orders_supabase(restaurant_id, limit=100):
    """جلب طلبات مطعم من Supabase"""
    rows = _sb_get("orders",
                   f"restaurant_id=eq.{restaurant_id}&order=created_at.desc",
                   limit)
    import json as _j
    for r in rows:
        if isinstance(r.get("items"), str):
            try: r["items"] = _j.loads(r["items"])
            except: r["items"] = []
        if isinstance(r.get("delivery_active"), bool):
            r["delivery_active"] = "true" if r["delivery_active"] else "false"
    return rows

def fetch_staff_supabase(restaurant_id):
    """جلب موظفي مطعم من Supabase"""
    return _sb_get("staff",
                   f"restaurant_id=eq.{restaurant_id}&status=eq.active")


FRONTEND_URL    = os.getenv("FRONTEND_URL","https://your-menu.netlify.app")
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")
TG_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN","")
KITCHEN_URL     = os.getenv("KITCHEN_URL","https://kitchen-qr.netlify.app")
CAISSE_URL      = os.getenv("CAISSE_URL","https://caisse-restcaf.pages.dev")

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
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
html,body,[class*="css"]{font-family:'Cairo',sans-serif!important}

/* ══ متغيرات الليل (افتراضي) ══ */
:root{
  --bg:#0d0d0d; --bg2:#141414; --bg3:#1c1c1c;
  --sidebar:#0a0a0a;
  --text:#f0ede6; --text2:#a09880; --text3:#5a5040;
  --border:#252520; --border2:#1e1e18;
  --gold:#C9A84C; --gold2:#E8C97A; --gold-dim:#3a2e10;
  --card:#141414; --card-border:#252520;
  --input-bg:#1c1c1c; --input-text:#f0ede6; --input-border:#2a2a20;
  --btn-sidebar:linear-gradient(135deg,#C9A84C,#a07830);
  --btn-sidebar-txt:#000;
  --success:#1a8a40; --danger:#a02020; --info:#1a5a9a;
  --tab-active:#C9A84C; --tab-active-txt:#000;
  --shadow:0 2px 12px rgba(0,0,0,.6);
  --radius:10px; --radius-lg:16px;
}

/* ══ متغيرات النهار ══ */
body.day-theme{
  --bg:#f7f3ec; --bg2:#ede8df; --bg3:#e4ddd2;
  --sidebar:#ede8df;
  --text:#1a150a; --text2:#5a4820; --text3:#9a8a60;
  --border:#ccc4a8; --border2:#ddd5bc;
  --gold:#7a5008; --gold2:#a07030; --gold-dim:#e8d8a0;
  --card:#ffffff; --card-border:#ccc4a8;
  --input-bg:#ffffff; --input-text:#1a150a; --input-border:#c8b890;
  --btn-sidebar:linear-gradient(135deg,#7a5008,#5a3800);
  --btn-sidebar-txt:#fff;
  --success:#1a6028; --danger:#881515; --info:#1a4a88;
  --tab-active:#7a5008; --tab-active-txt:#fff;
  --shadow:0 2px 8px rgba(0,0,0,.12);
}

/* ══ تطبيق على كل العناصر ══ */
.stApp,[data-testid="stAppViewContainer"],[data-testid="stAppViewBlockContainer"],
.main,.block-container,[data-testid="stHeader"],
[data-testid="stDecoration"]
{background:var(--bg)!important;color:var(--text)!important}

section[data-testid="stSidebar"],
section[data-testid="stSidebar"]>div,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"]
{background:var(--sidebar)!important}
section[data-testid="stSidebar"] *
{color:var(--text)!important}

/* ══ الحقول ══ */
.stTextInput>div>div>input,
.stTextArea textarea,
.stNumberInput input,
[data-baseweb="input"] input,
[data-baseweb="textarea"],
input[type="text"],input[type="email"],input[type="tel"],
input[type="number"],input[type="password"],input[type="url"],textarea
{background:var(--input-bg)!important;color:var(--input-text)!important;
 border:1.5px solid var(--input-border)!important;border-radius:8px!important}
.stTextInput>div>div>input:focus,[data-baseweb="input"] input:focus
{border-color:var(--gold)!important;box-shadow:0 0 0 3px var(--gold-dim)!important}
::placeholder{color:var(--text3)!important;opacity:1!important}

/* ══ selectbox ══ */
.stSelectbox>div>div,[data-baseweb="select"]>div,
[data-baseweb="select"] [class*="control"],
[data-baseweb="select"] [class*="singleValue"],
[data-baseweb="select"] [class*="placeholder"],
[data-baseweb="select"] [class*="valueContainer"]
{background:var(--input-bg)!important;color:var(--input-text)!important;
 border-color:var(--input-border)!important}
[data-baseweb="select"] [class*="menu"],
[data-baseweb="popover"]>div,[data-baseweb="popover"] ul
{background:var(--bg2)!important;border:1px solid var(--border)!important;
 border-radius:var(--radius)!important}
[data-baseweb="select"] [class*="option"]:hover,
[data-baseweb="menu-item"]:hover
{background:var(--gold-dim)!important}

/* ══ radio/checkbox ══ */
.stRadio>div,[data-baseweb="radio"]>div,[data-testid="stRadio"]>div
{color:var(--text)!important}
[data-baseweb="radio"] div[aria-checked="true"]>div
{background:var(--gold)!important;border-color:var(--gold)!important}

/* ══ الأزرار في السيدبار ══ */
section[data-testid="stSidebar"] .stButton>button{
  background:var(--btn-sidebar)!important;
  color:var(--btn-sidebar-txt)!important;
  border:none!important;border-radius:12px!important;
  font-weight:700!important;font-size:.9rem!important;
  padding:.6rem .8rem!important;
  box-shadow:var(--shadow)!important;
  transition:all .15s ease!important;
}
section[data-testid="stSidebar"] .stButton>button:hover
{opacity:.88!important;transform:translateX(-2px)!important}

/* ══ الأزرار العامة ══ */
[data-testid="stButton"]>button[kind="primary"],
.stButton>button[kind="primary"]
{background:var(--btn-sidebar)!important;color:var(--btn-sidebar-txt)!important;
 border:none!important;border-radius:10px!important;font-weight:700!important;
 box-shadow:var(--shadow)!important}

[data-testid="stButton"]>button[kind="secondary"],
.stButton>button[kind="secondary"],
[data-testid="stButton"]>button:not([kind="primary"]),
.stButton>button:not([kind="primary"])
{background:var(--bg3)!important;color:var(--text)!important;
 border:1px solid var(--border)!important;border-radius:10px!important}

.stButton>button:hover{filter:brightness(1.08)!important}

/* ══ التبويبات ══ */
[data-baseweb="tab-list"],[role="tablist"]
{background:var(--bg2)!important;border-bottom:1px solid var(--border)!important}
[data-baseweb="tab"],[role="tab"]
{color:var(--text2)!important;border-radius:8px 8px 0 0!important;font-weight:600!important}
[aria-selected="true"][data-baseweb="tab"],[aria-selected="true"][role="tab"]
{color:var(--tab-active)!important;border-bottom:2px solid var(--tab-active)!important;
 background:transparent!important}

/* ══ expanders ══ */
[data-testid="stExpander"]>details,
[data-testid="stExpander"]
{background:var(--card)!important;border:1px solid var(--card-border)!important;
 border-radius:var(--radius)!important}
[data-testid="stExpander"] summary
{color:var(--text)!important;font-weight:700!important}
[data-testid="stExpander"] summary:hover
{background:var(--bg3)!important;border-radius:var(--radius)!important}

/* ══ alerts / info / success / error ══ */
[data-testid="stAlert"],[data-baseweb="notification"]
{border-radius:var(--radius)!important;border-width:1px!important}
.stSuccess{background:color-mix(in srgb,var(--success) 12%,var(--bg))!important;
  border-color:var(--success)!important;color:var(--success)!important}
.stError{background:color-mix(in srgb,var(--danger) 12%,var(--bg))!important;
  border-color:var(--danger)!important;color:var(--danger)!important}
.stInfo{background:color-mix(in srgb,var(--info) 12%,var(--bg))!important;
  border-color:var(--info)!important;color:var(--info)!important}
.stWarning{background:color-mix(in srgb,#d4800a 12%,var(--bg))!important;
  border-color:#d4800a!important;color:#d4800a!important}

/* ══ metrics ══ */
[data-testid="stMetric"],[data-testid="metric-container"]
{background:var(--card)!important;border:1px solid var(--card-border)!important;
 border-radius:var(--radius)!important;padding:.8rem!important}
[data-testid="stMetricValue"]{color:var(--gold)!important;font-weight:900!important}
[data-testid="stMetricLabel"]{color:var(--text2)!important}
[data-testid="stMetricDelta"]{color:var(--success)!important}

/* ══ جداول ══ */
[data-testid="stDataFrame"],table
{background:var(--card)!important;border:1px solid var(--border)!important;
 border-radius:var(--radius)!important}
th{background:var(--bg3)!important;color:var(--gold)!important;font-weight:700!important}
td{color:var(--text)!important;border-color:var(--border)!important}

/* ══ code blocks ══ */
[data-testid="stCode"]>div,code,pre
{background:var(--bg3)!important;color:var(--gold)!important;
 border:1px solid var(--border)!important;border-radius:8px!important}

/* ══ dividers ══ */
hr,.gdiv{border-color:var(--border)!important}
[data-testid="stMarkdown"] hr{border-color:var(--border)!important}

/* ══ file uploader ══ */
[data-testid="stFileUploader"]>div
{background:var(--bg3)!important;border:2px dashed var(--border)!important;
 border-radius:var(--radius)!important}

/* ══ spinner ══ */
.stSpinner>div{color:var(--gold)!important}

/* ══ progress bar ══ */
.stProgress>div>div{background:var(--gold)!important}

/* ══ slider ══ */
[data-testid="stSlider"] div[data-baseweb="slider"] div[role="slider"]
{background:var(--gold)!important;border-color:var(--gold)!important}

/* ══ scrollbar ══ */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--bg2)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--gold)}

/* ══ custom classes ══ */
.res{padding:.8rem 1rem;border-radius:var(--radius);margin:.4rem 0;
     border:1px solid var(--border);font-size:.88rem}
.res.ok{background:color-mix(in srgb,var(--success) 10%,var(--bg));
  border-color:var(--success);color:var(--success)}
.res.warn{background:color-mix(in srgb,#d4800a 10%,var(--bg));
  border-color:#d4800a;color:#d4800a}
.gdiv{border-top:1px solid var(--border);margin:1rem 0}

/* ══ الجانبي: سطر التعريف بالمستخدم ══ */
.user-badge{
  background:var(--gold-dim);border:1px solid var(--gold);
  border-radius:var(--radius);padding:.6rem .8rem;text-align:center;
  margin:.5rem 0;font-weight:700;color:var(--gold);font-size:.9rem;
}
/* ══ ضمان وضوح كل شيء في وضع النهار ══ */
body.day-theme p, body.day-theme li, body.day-theme span,
body.day-theme label, body.day-theme h1, body.day-theme h2,
body.day-theme h3, body.day-theme h4, body.day-theme div
{color:var(--text)!important}
body.day-theme [data-testid="stMarkdown"] *,
body.day-theme [data-testid="stMarkdownContainer"] *
{color:var(--text)!important}
body.day-theme [data-testid="stExpander"] *,
body.day-theme [data-testid="stExpanderDetails"] *
{color:var(--text)!important;background:var(--card)!important}
body.day-theme [data-testid="stMetricValue"]
{color:var(--gold)!important}
body.day-theme [data-testid="stMetricLabel"]
{color:var(--text2)!important}
/* ضمان وضوح النص في حقول الإدخال بالنهار */
body.day-theme input, body.day-theme textarea, body.day-theme select
{color:var(--input-text)!important;background:var(--input-bg)!important}
/* ضمان وضوح الأزرار في النهار */
body.day-theme .stButton>button
{color:var(--gold)!important}
body.day-theme section[data-testid="stSidebar"] .stButton>button
{color:var(--gold)!important;background:var(--gold-dim)!important;
 border-color:var(--border)!important}
/* تابات واضحة في النهار */
body.day-theme [data-baseweb="tab"]
{color:var(--text2)!important}
body.day-theme [aria-selected="true"][data-baseweb="tab"]
{color:var(--tab-active)!important}
/* code واضح في النهار */
body.day-theme code, body.day-theme pre
{background:var(--bg3)!important;color:var(--gold)!important;
 border:1px solid var(--border)!important}
/* أيقونات sidebar في النهار */
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
    ✅ يُنظّف كل حقل في سجل المطعم (Supabase أو Sheets)
    """
    import json as _json

    # ✅ حقول نصية كاملة بما فيها Supabase-only fields
    for f in ["restaurant_id","name","sheet_id","telegram_chat_id",
              "wifi_ssid","wifi_password","primary_color","accent_color",
              "style","logo_url","owner_email","status","created_at",
              "kitchen_password","slug","plan","agency_id",
              "boss_chat_id","waiters_chat_id","delivery_chat_id","sa_json"]:
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

@st.cache_data(ttl=30)   # ✅ إصلاح: 30 ثانية — تحديث أسرع بعد أي تغيير
def fetch_all():
    """
    ✅ FIX 8: يقرأ من Supabase أولاً (delivery_active صحيح) ثم من Google Sheets كـ fallback
    """
    import requests as _rq8
    sb_url = SUPABASE_URL
    sb_key = SUPABASE_KEY
    if sb_url and sb_key:
        try:
            h8 = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                  "Content-Type": "application/json"}
            resp8 = _rq8.get(
                f"{sb_url}/rest/v1/restaurants?order=created_at.desc&limit=1000",
                headers=h8, timeout=10
            )
            if resp8.status_code == 200:
                rows8 = resp8.json() or []
                if rows8:
                    records8 = []
                    for r8 in rows8:
                        # تحويل delivery_active للنص لأن الداشبورد يقرأه بـ str().lower()
                        if isinstance(r8.get("delivery_active"), bool):
                            r8["delivery_active"] = "true" if r8["delivery_active"] else "false"
                        # تحويل الـ nulls لـ strings فارغة
                        for k8, v8 in r8.items():
                            if v8 is None:
                                r8[k8] = ""
                        records8.append(_sanitize_record(r8))
                    return records8
        except Exception as _e8:
            pass  # fallback للـ Sheets أدناه
    # ── Fallback: Google Sheets ──────────────────────────
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
            _slug_r = r.get('slug','').strip()
            mu = f"{FRONTEND_URL}/{_slug_r}" if _slug_r else f"{FRONTEND_URL}?rest_id={r.get('restaurant_id')}"
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
        # ✅ زر اختبار الإيميل
        st.markdown("---")
        st.markdown("**📧 اختبار إرسال الإيميل:**")
        _test_email = st.text_input("📮 أدخل إيميل للاختبار", placeholder="test@gmail.com", key="test_email_inp")
        if st.button("📤 إرسال إيميل اختبار", key="btn_test_email"):
            if _test_email.strip():
                try:
                    import smtplib, os as _ose
                    from email.mime.text import MIMEText
                    _gu = _ose.getenv("GMAIL_USER","")
                    _gp = _ose.getenv("GMAIL_APP_PASSWORD","")
                    if not _gu or not _gp:
                        st.error("❌ GMAIL_USER أو GMAIL_APP_PASSWORD غير موجودَين في Secrets")
                    else:
                        _msg = MIMEText(f"<h2>✅ اختبار ناجح!</h2><p>الإيميل يعمل من {_gu}</p>", "html", "utf-8")
                        _msg["Subject"] = "✅ اختبار إيميل النظام"
                        _msg["From"] = _gu
                        _msg["To"] = _test_email.strip()
                        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as _srv:
                            _srv.login(_gu, _gp)
                            _srv.sendmail(_gu, _test_email.strip(), _msg.as_string())
                        st.success(f"✅ تم الإرسال بنجاح إلى {_test_email.strip()} — تحقق من البريد الوارد وSpam")
                except smtplib.SMTPAuthenticationError:
                    st.error("❌ GMAIL_APP_PASSWORD خاطئة — أنشئ App Password جديدة من Google Account")
                except Exception as _te:
                    st.error(f"❌ خطأ: {type(_te).__name__}: {_te}")
            else:
                st.warning("⚠️ أدخل إيميل أولاً")

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
            rslug    = st.text_input("🔗 Slug (رابط نظيف) *",
                        placeholder="nakhil — يُستخدم في الرابط: menu.netlify.app/nakhil",
                        help="حروف صغيرة بدون مسافات — مثال: nakhil أو najm")
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
            rcashier_pass = st.text_input("💰 كلمة مرور الكاسيير",
                placeholder="اتركه فارغاً إذا لم تريد كلمة مرور",
                key="new_cashier_pass")

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

    # ══ Service Account الخاص بالمطعم ══
    st.markdown("---")
    st.markdown("**🔑 Service Account الخاص بهذا المطعم (موصى به):**")
    st.caption("أنشئ SA جديد من Google Cloud لكل مطعم — يضمن 60 req/min مستقلة — اتركه فارغاً لاستخدام SA المشترك")
    col_sa_new1, col_sa_new2 = st.columns([4, 1])
    with col_sa_new1:
        rsa_json = st.text_area(
            "sa_json_new", value="",
            placeholder='{"type":"service_account","project_id":"...","private_key":"...",...}',
            height=80, key="new_sa_json", label_visibility="collapsed"
        )
    with col_sa_new2:
        st.markdown("<br>", unsafe_allow_html=True)
        if rsa_json.strip():
            try:
                import json as _jj; _jj.loads(rsa_json.strip())
                st.success("✅ JSON صالح")
            except: st.error("❌ JSON خاطئ")
        else:
            st.info("⚠️ SA مشترك")

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
        _clean_slug = rslug.strip().lower().replace(" ","-").replace("_","-") if rslug.strip() else ""
        result: ProvisionResult = provision_restaurant(
            restaurant_id=rid.strip(), name=rname.strip(),
            sheet_id=rsheetid.strip(),
            wifi_ssid=rssid.strip(), wifi_password=rwpass.strip(),
            style=rstyle, primary_color=rprimary, accent_color=raccent,
            num_tables=rtables, logo_url=rlogo.strip(), owner_email=remail.strip(),
            bg_type=rbg_type, socials=rsocials,
            kitchen_password=rkitchen_pass.strip(),
            delivery_active=rdelivery,
            sa_json=rsa_json.strip() if rsa_json.strip() else "",
            slug=_clean_slug,
            cashier_password=rcashier_pass.strip() if rcashier_pass.strip() else "")

        done = len([s for s in result.steps if "✅" in s])
        show(min(done, len(steps_lbl)-1), result.steps)
        pb.empty(); pl.empty()

        if result.success:
            st.markdown(f'<div class="res ok"><b>🎉 تم إنشاء "{rname}" بنجاح!</b><br><br>'
                        f'{"<br>".join(result.steps)}</div>', unsafe_allow_html=True)
            # ✅ الرابط النظيف من الـ slug
            _slug_new = _clean_slug if _clean_slug else ""
            mu = f"{FRONTEND_URL}/{_slug_new}" if _slug_new else f"{FRONTEND_URL}?rest_id={rid}"
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

            # ✅ slug من المتغير المُدخل مباشرة
            _slug_k = _clean_slug if _clean_slug else rid.strip()
            kitchen_link = (
                f"{KITCHEN_URL}/{_slug_k}?api={ROUTER_URL}"
                if _slug_k else
                f"{KITCHEN_URL}?api={ROUTER_URL}&rid={rid.strip()}&name={requests.utils.quote(rname.strip())}"
            )
            kitchen_link_old = f"{KITCHEN_URL}?api={ROUTER_URL}&rid={rid.strip()}&name={requests.utils.quote(rname.strip())}"
            st.markdown(f"""<div style="background:rgba(255,152,0,.07);border:1px solid rgba(255,152,0,.2);
              border-radius:12px;padding:1rem 1.2rem;margin:.5rem 0">
              <b style="color:#ff9800">🍳 رابط شاشة الكوزينة — ضعه على التابليت:</b><br>
              <div style="background:#0a0800;border:1px solid rgba(255,152,0,.2);border-radius:8px;
                   padding:.6rem 1rem;font-family:monospace;font-size:.78rem;color:#ff9800;
                   word-break:break-all;margin:.5rem 0">{kitchen_link}</div>
              <small style="color:#555">📌 Bookmark على التابليت في الكوزينة</small>
            </div>""", unsafe_allow_html=True)
            st.code(kitchen_link, language=None)

            # ✅ رابط الكاشير (الدفع)
            if CAISSE_URL:
                _caisse_rid_new = _clean_slug if _clean_slug else rid.strip()
                _caisse_link_new = f"{CAISSE_URL}?rid={_caisse_rid_new}&api={ROUTER_URL}"
                _cashier_pw_new = rcashier_pass.strip() if rcashier_pass.strip() else "بدون كلمة مرور"
                st.markdown(f"""<div style="background:rgba(0,200,83,.07);border:1px solid rgba(0,200,83,.2);
                  border-radius:12px;padding:1rem 1.2rem;margin:.5rem 0">
                  <b style="color:#00c853">💰 رابط شاشة الكاشير (الدفع):</b><br>
                  <div style="background:#001a08;border:1px solid rgba(0,200,83,.2);border-radius:8px;
                       padding:.6rem 1rem;font-family:monospace;font-size:.78rem;color:#00c853;
                       word-break:break-all;margin:.5rem 0">{_caisse_link_new}</div>
                  <b style="color:#69f0ae">🔑 كلمة مرور الكاشير:</b>
                  <code style="background:#002210;color:#69f0ae;padding:2px 8px;border-radius:4px">{_cashier_pw_new}</code><br>
                  <small style="color:#555">📌 ضعه على كمبيوتر الكاشير — تصله الطلبات فور تقديمها من النادل</small>
                </div>""", unsafe_allow_html=True)
                st.code(_caisse_link_new, language=None)

            # توليد البطاقات
            st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)
            st.markdown("### 🔲 بطاقات الطاولات")

            with st.spinner("🎨 توليد البطاقات..."):
                import random
                _queries = VENUE_QUERIES.get(rvenue_type, [rname])
                _photo_query = random.choice(_queries)
                menu_img, wifi_img = generate_table_card(
                    rname, rssid, rwpass, 1,
                    # ✅ FIX: بناء URL صحيح مع table param
                    (f"{mu}?table=1" if "?" not in mu else f"{mu}&table=1"),
                    rstyle, rprimary, raccent, rbg_type, rsocials,
                    pexels_key=PEXELS_KEY,
                    unsplash_key=UNSPLASH_KEY,
                    pixabay_key=PIXABAY_KEY,
                    photo_query=_photo_query,
                )
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
                    "last_rbg_type": rbg_type,
                    "last_rsocials": rsocials,
                    "last_photo_query": _photo_query,
                    # ✅ FIX: احفظ slug و base_url للـ PDF
                    "last_slug": _clean_slug,
                    "last_base_url": mu.split("&table=")[0] if "&table=" in mu else mu,
                })
                st.session_state.pop("last_pdf_bytes", None)

            _show_cards_and_pdf()
            # ✅ إصلاح: مسح cache_data + cache_resource بعد الإنشاء
            st.cache_data.clear()
            st.cache_resource.clear()

            # ✅ عرض روابط المجموعات بعد الإنشاء مباشرة
            try:
                _tg_me = requests.get(
                    f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=5)
                _bot_user = _tg_me.json().get("result",{}).get("username","") if _tg_me.ok else ""
            except:
                _bot_user = ""

            if _bot_user:
                _boss_lnk     = f"https://t.me/{_bot_user}?start=boss_{rid}"
                _waiters_lnk  = f"https://t.me/{_bot_user}?startgroup=waiters_{rid}"
                _delivery_lnk = f"https://t.me/{_bot_user}?startgroup=delivery_{rid}"
                st.markdown(f"""<div style="background:rgba(0,136,204,.07);border:1px solid rgba(0,136,204,.2);
                  border-radius:12px;padding:1rem 1.2rem;margin:.5rem 0">
                  <b style="color:#29b6f6">📲 روابط ربط المجموعات:</b><br><br>
                  👑 <b>المدير (يفتحه المدير في محادثته الخاصة):</b><br>
                  <code style="color:#29b6f6">{_boss_lnk}</code><br><br>
                  🍽️ <b>النوادل (أضف البوت للمجموعة ثم أرسل الرابط):</b><br>
                  <code style="color:#29b6f6">{_waiters_lnk}</code><br><br>
                  🛵 <b>التوصيل (أضف البوت للمجموعة ثم أرسل الرابط):</b><br>
                  <code style="color:#29b6f6">{_delivery_lnk}</code><br><br>
                  <small style="color:#555">💡 للمجموعات: أضف البوت أولاً → ثم أرسل الرابط في المجموعة</small>
                </div>""", unsafe_allow_html=True)

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
    rbg     = st.session_state.get("last_rbg_type","minimal")
    rsoc    = st.session_state.get("last_rsocials",{})
    if not mb or not wb: return

    qc1,qc2 = st.columns(2)
    with qc1:
        st.image(mb, caption="📱 QR المينيو — للطلب", use_container_width=True)
        st.download_button("⬇️ تحميل QR المينيو", mb,
            f"Menu_QR_{rname}.png","image/png",
            use_container_width=True, key="dl_menu_qr")
    with qc2:
        st.image(wb, caption="📶 QR WiFi — اتصال تلقائي", use_container_width=True)
        st.download_button("⬇️ تحميل QR WiFi", wb,
            f"WiFi_QR_{rname}.png","image/png",
            use_container_width=True, key="dl_wifi_qr")

    st.markdown('<div class="gdiv"></div>', unsafe_allow_html=True)

    if st.button(f"📄 توليد PDF كامل ({rtables} طاولة = {rtables*2} صفحة)",
                 use_container_width=True, key="btn_gen_pdf"):
        with st.spinner(f"⏳ {rtables*2} صفحة..."):
            try:
                from pdf_generator import generate_table_tents_pdf
                # ✅ استخدام نفس الـ photo_query المحفوظ من عند توليد البطاقة
                saved_query = st.session_state.get("last_photo_query", rname)
                # ✅ FIX: استخدم last_base_url المحفوظة مباشرة — لا تحتاج _clean_slug
                _last_mu = st.session_state.get("last_mu", "")
                _last_base = st.session_state.get("last_base_url", "")
                if _last_base:
                    _pdf_base_url = _last_base
                elif _last_mu:
                    _pdf_base_url = _last_mu.split("&table=")[0] if "&table=" in _last_mu else _last_mu
                else:
                    _last_slug_ss = st.session_state.get("last_slug", "")
                    _pdf_base_url = f"{FRONTEND_URL}/{_last_slug_ss}" if _last_slug_ss else f"{FRONTEND_URL}?rest_id={rid}"
                # ✅ FIX: تأكد أن الـ URL يحتوي rest_id أو slug بشكل صحيح
                _pdf_url_clean = _pdf_base_url.rstrip("/")
                pdf = generate_table_tents_pdf(
                    rname, rssid, rwpass, _pdf_url_clean,
                    rid, rtables, rstyle, rp, ra,
                    bg_type=rbg, socials=rsoc,
                    pexels_key=PEXELS_KEY,
                    unsplash_key=UNSPLASH_KEY,
                    pixabay_key=PIXABAY_KEY,
                    photo_query=saved_query)
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
        _nt = int(r.get("num_tables", 10))
        n  = st.number_input("عدد الطاولات", min_value=1, max_value=200, value=_nt)
        pv = st.number_input("معاينة طاولة رقم", min_value=1, max_value=int(n), value=1)
    with c2:
        saved_bg  = r.get("bg_type","") or "minimal"
        bg_opts   = list(BG_LABELS.keys())
        bg_def    = bg_opts.index(saved_bg) if saved_bg in bg_opts else 0
        pdf_bg    = st.selectbox("🖼️ خلفية البطاقة", bg_opts,
                                 index=bg_def,
                                 format_func=lambda x: BG_LABELS.get(x,x),
                                 key="pdf_bg_sel")
        saved_style = r.get("style","luxury") or "luxury"
        style_opts  = list(STYLE_LABELS.keys())
        style_def   = style_opts.index(saved_style) if saved_style in style_opts else 0
        pdf_style   = st.selectbox("🎭 الطابع", style_opts,
                                   index=style_def,
                                   format_func=lambda x: STYLE_LABELS.get(x,x),
                                   key="pdf_style_sel")
        VENUE_TYPES_PDF = {
            "restaurant":"🍽️ مطعم","cafe":"☕ مقهى","fastfood":"🍔 وجبات سريعة",
            "pizza":"🍕 بيتزا","seafood":"🦞 بحري","moroccan":"🍲 مغربي",
            "grill":"🔥 مشويات","sushi":"🍣 سوشي","pastry":"🥐 حلويات","juice":"🥤 عصائر"
        }
        VENUE_QUERIES_PDF = {
            "restaurant":["fine dining food elegant","gourmet restaurant plating","restaurant food photography"],
            "cafe":["coffee shop cozy latte","cafe interior coffee","barista coffee art"],
            "fastfood":["burger fast food crispy","fries hamburger meal","fast food restaurant"],
            "pizza":["pizza wood fired","italian pizza cheese","pizza restaurant"],
            "seafood":["seafood fresh platter","grilled fish lemon","seafood restaurant"],
            "moroccan":["moroccan tagine food","couscous moroccan dish","moroccan cuisine"],
            "grill":["bbq grilled meat smoke","steakhouse grill","charcoal grilled"],
            "sushi":["sushi platter fresh","japanese food restaurant","sushi rolls"],
            "pastry":["pastry bakery croissant","cake patisserie sweet","bakery bread"],
            "juice":["fresh juice tropical","smoothie colorful fruits","juice bar drinks"],
        }
        pdf_venue = st.selectbox("🏪 نوع المطعم",
            list(VENUE_TYPES_PDF.keys()),
            format_func=lambda x: VENUE_TYPES_PDF.get(x,x),
            key="pdf_venue_sel")

    socials = r.get("socials", {}) or {}
    import random as _rand
    _pdf_query = _rand.choice(VENUE_QUERIES_PDF.get(pdf_venue, [r.get("name","food")]))

    if st.button("👁️ معاينة", use_container_width=True, key="btn_preview"):
        with st.spinner("🎨..."):
            try:
                _prev_slug = r.get("slug","").strip()
                _prev_base = f"{FRONTEND_URL}/{_prev_slug}" if _prev_slug else FRONTEND_URL
                mi, wi = generate_single_table_preview(
                    r.get("name","مطعم"), r.get("wifi_ssid","WiFi"),
                    r.get("wifi_password",""), _prev_base,
                    r.get("restaurant_id","1"), pv,
                    pdf_style, r.get("primary_color","#0a0804"),
                    r.get("accent_color","#C9A84C"),
                    pdf_bg, socials,
                    pexels_key=PEXELS_KEY, unsplash_key=UNSPLASH_KEY,
                    pixabay_key=PIXABAY_KEY, photo_query=_pdf_query)
                st.session_state["prev_m"] = card_to_bytes(mi)
                st.session_state["prev_w"] = card_to_bytes(wi)
                # ✅ احفظ الـ query المستخدم لإعادة استخدامه في PDF
                st.session_state["prev_pdf_query"] = _pdf_query
                st.session_state["prev_pdf_bg"]    = pdf_bg
                st.session_state["prev_pdf_style"] = pdf_style
            except Exception as e:
                st.error(f"❌ {e}")

    if st.session_state.get("prev_m"):
        ca,cb = st.columns(2)
        ca.image(st.session_state["prev_m"], caption=f"📱 QR المينيو T{pv}", use_container_width=True)
        cb.image(st.session_state["prev_w"], caption=f"📶 QR WiFi T{pv}", use_container_width=True)

    if st.button("📄 توليد PDF كامل", use_container_width=True, key="btn_pdf_pg"):
        with st.spinner(f"⏳ {n*2} صفحة..."):
            try:
                from pdf_generator import generate_table_tents_pdf
                # ✅ استخدم نفس الـ query والـ style من المعاينة
                final_query = st.session_state.get("prev_pdf_query", _pdf_query)
                final_bg    = st.session_state.get("prev_pdf_bg", pdf_bg)
                final_style = st.session_state.get("prev_pdf_style", pdf_style)
                # ✅ استخدم الرابط النظيف إذا وُجد slug
                _r_slug = r.get("slug","").strip()
                _r_base = f"{FRONTEND_URL}/{_r_slug}" if _r_slug else FRONTEND_URL
                pdf = generate_table_tents_pdf(
                    r.get("name","مطعم"), r.get("wifi_ssid","WiFi"),
                    r.get("wifi_password",""), _r_base,
                    r.get("restaurant_id","1"), n,
                    final_style,
                    r.get("primary_color","#0a0804"),
                    r.get("accent_color","#C9A84C"),
                    final_bg,
                    socials,
                    pexels_key=PEXELS_KEY,
                    unsplash_key=UNSPLASH_KEY,
                    pixabay_key=PIXABAY_KEY,
                    photo_query=final_query)
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
                        json={
                            "url": wh_url,
                            # ✅ message + callback_query + my_chat_member (ربط تلقائي)
                            "allowed_updates": ["message", "callback_query", "my_chat_member"]
                        }, timeout=10)
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
                boss_id     = r.get("boss_chat_id","") or "⏳ لم يُربط"
                waiters_id  = r.get("waiters_chat_id","") or "⏳ لم تُربط"
                delivery_id = r.get("delivery_chat_id","") or "⏳ لم تُربط"
                st.markdown(f"""
                **📊 Sheet:** [{sid[:28] if sid else 'لا يوجد'}]({su})

                **📨 Telegram (رئيسي):** `{r.get('telegram_chat_id','⏳ لم يُربط بعد')}`

                **👑 Boss chat_id:** `{boss_id}`

                **🍽️ النوادل chat_id:** `{waiters_id}`

                **🛵 التوصيل chat_id:** `{delivery_id}`

                **📶 WiFi:** `{r.get('wifi_ssid','')}` | `{r.get('wifi_password','')}`

                **🎨 طابع:** {r.get('style','')} | 🪑 {r.get('num_tables','')} طاولة

                **🔑 كلمة سر الكوزينة:** `{r.get('kitchen_password','⚠️ غير محددة')}`
                **💰 كلمة سر الكاسيير:** `{r.get('cashier_password','') or '⚠️ غير محددة'}`

                **🛵 التوصيل:** {'✅ مفعّل' if str(r.get('delivery_active','')).lower()=='true' else '❌ غير مفعّل'}
                """)
            with c2:
                _slug_d = r.get("slug","").strip()
                mu = f"{FRONTEND_URL}/{_slug_d}" if _slug_d else f"{FRONTEND_URL}?rest_id={rid}"
                st.code(mu)
                reg = build_reg_link(rid)
                if reg:
                    st.markdown("**🔗 رابط Telegram (ربط المطعم):**")
                    st.code(reg)
                if r.get("owner_email"):
                    st.markdown(f"**📧** {r.get('owner_email')}")
                kitchen_link = f"{KITCHEN_URL}?api={ROUTER_URL}&rid={rid}&name={requests.utils.quote(r.get('name',''))}"
                st.markdown("**🍳 شاشة الكوزينة:**")
                st.code(kitchen_link)
                if CAISSE_URL:
                    _slug_m = r.get("slug","").strip() or rid
                    _caisse_m = f"{CAISSE_URL}?rid={_slug_m}&api={ROUTER_URL}"
                    st.markdown("**💰 رابط الكاشير:**")
                    st.code(_caisse_m)
                    _cpw = r.get("cashier_password","")
                    if _cpw:
                        st.markdown(f"**🔑 كلمة مرور الكاشير:** `{_cpw}`")

                # ✅ إصلاح: جلب اسم البوت ديناميكياً من API Telegram
                try:
                    _tg_me = requests.get(
                        f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=5)
                    bot_username = _tg_me.json().get("result",{}).get("username","") if _tg_me.ok else ""
                except:
                    bot_username = os.getenv("TELEGRAM_BOT_USERNAME","")

                if bot_username:
                    boss_link = f"https://t.me/{bot_username}?start=boss_{rid}"
                    st.markdown("**📲 ربط Telegram:**")
                    st.markdown(f"👑 **المدير** — يفتح هذا الرابط في محادثته الخاصة مع البوت:")
                    st.code(boss_link)

                    st.markdown(f"""**🍽️ مجموعة النوادل** — خطوتين:
1. أضف البوت `@{bot_username}` للمجموعة
2. أرسل في المجموعة: `/ربط waiters_{rid}`""")

                    st.markdown(f"""**🛵 مجموعة التوصيل** — خطوتين:
1. أضف البوت `@{bot_username}` للمجموعة
2. أرسل في المجموعة: `/ربط delivery_{rid}`""")

                    st.code(f"/ربط waiters_{rid}", language=None)
                    st.code(f"/ربط delivery_{rid}", language=None)
                else:
                    st.warning("⚠️ TELEGRAM_BOT_TOKEN غير محدد")

            with c3:
                if st.button("🗑️ حذف", key=f"del_{uid}"):
                    if del_r(rid):
                        st.success("تم!")
                        st.cache_data.clear()
                        st.cache_resource.clear()
                        st.rerun()
                if st.button("🔄 Cache", key=f"cache_{uid}"):
                    try:
                        requests.post(f"{ROUTER_URL}/cache/refresh/{rid}", timeout=5)
                        st.success("✅ Cache مُحدَّث")
                    except:
                        st.warning("API غير متاح")
                    st.cache_data.clear()
                    st.rerun()

                # ✅ زر تفعيل/إلغاء التوصيل — يكتب في Supabase مباشرة
                delivery_on = (
                    r.get("delivery_active") is True or
                    str(r.get("delivery_active","")).lower() == "true"
                )
                delivery_label = "🛵 إلغاء التوصيل" if delivery_on else "🛵 تفعيل التوصيل"
                delivery_color = "🟢 مفعّل" if delivery_on else "🔴 غير مفعّل"
                st.markdown(f"<div style='font-size:.8rem;color:#888;margin-bottom:.3rem'>التوصيل: {delivery_color}</div>", unsafe_allow_html=True)

                if st.button(delivery_label, key=f"del_tog_{uid}", use_container_width=True,
                             type="primary" if not delivery_on else "secondary"):
                    new_bool = not delivery_on
                    new_val  = "true" if new_bool else "false"
                    try:
                        # ✅ 1) كتابة في Supabase أولاً (boolean صحيح)
                        _ok_sb = _sb_patch(
                            "restaurants",
                            f"restaurant_id=eq.{rid}",
                            {"delivery_active": new_bool}
                        )
                        # ✅ 2) كتابة في Google Sheets كـ backup
                        try:
                            import gspread as _gs_mod
                            from google.oauth2.service_account import Credentials as _Creds
                            import json as _json
                            _SA     = os.getenv("GOOGLE_SA_JSON_CONTENT","")
                            _MASTER = os.getenv("MASTER_SHEET_ID","")
                            _SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
                            if _SA and _MASTER:
                                _creds  = _Creds.from_service_account_info(_json.loads(_SA), scopes=_SCOPES)
                                _client = _gs_mod.authorize(_creds)
                                _ws     = _client.open_by_key(_MASTER).worksheet("Master_DB")
                                _headers = _ws.row_values(1)
                                if "delivery_active" not in _headers:
                                    _ws.update_cell(1, len(_headers)+1, "delivery_active")
                                    _headers.append("delivery_active")
                                _col = _headers.index("delivery_active") + 1
                                _rid_col = _headers.index("restaurant_id") if "restaurant_id" in _headers else 0
                                for _i, _row in enumerate(_ws.get_all_values()[1:], start=2):
                                    if len(_row) > _rid_col and str(_row[_rid_col]).strip() == rid:
                                        _ws.update_cell(_i, _col, new_val)
                                        break
                        except: pass
                        # ✅ 3) مسح cache الـ Router فوراً
                        try:
                            requests.post(f"{ROUTER_URL}/cache/refresh/{rid}",
                                          headers={"X-Admin-Key": SPASSWORD}, timeout=8)
                            requests.post(f"{ROUTER_URL}/cache/refresh",
                                          headers={"X-Admin-Key": SPASSWORD}, timeout=8)
                        except: pass
                        # ✅ 4) مسح cache الداشبورد وإعادة التحميل
                        st.cache_data.clear()
                        lbl = "مفعّل 🛵" if new_bool else "ملغى ❌"
                        if _ok_sb:
                            st.success(f"✅ التوصيل {lbl} — تم الحفظ في Supabase فوراً")
                        else:
                            st.warning(f"⚠️ التوصيل {lbl} — تحقق من الاتصال بـ Supabase")
                        st.rerun()
                    except Exception as _e:
                        st.error(f"❌ خطأ: {_e}")

            # ══ خانة الـ Slug (رابط نظيف) ══
            st.markdown("---")
            current_slug = r.get("slug","").strip()
            FRONTEND = os.getenv("FRONTEND_URL","")
            st.markdown("**🔗 Slug (رابط نظيف):**")
            st.caption(
                f"الرابط الحالي: `{FRONTEND}/{current_slug}`" if current_slug
                else "أضف slug للحصول على رابط نظيف مثل: menu.netlify.app/nakhil"
            )
            col_sl1, col_sl2 = st.columns([3,1])
            with col_sl1:
                new_slug = st.text_input(
                    "Slug", value=current_slug,
                    placeholder="nakhil (بدون مسافات أو رموز خاصة)",
                    key=f"slug_{uid}", label_visibility="collapsed"
                )
            with col_sl2:
                if st.button("💾 حفظ", key=f"save_slug_{uid}", use_container_width=True):
                    clean_slug = new_slug.strip().lower().replace(" ","-")
                    if clean_slug != current_slug:
                        try:
                            import gspread as _gsp_s
                            from google.oauth2.service_account import Credentials as _Cr_s
                            import json as _jj_s
                            _SA_s  = os.getenv("GOOGLE_SA_JSON_CONTENT","")
                            _MSI_s = os.getenv("MASTER_SHEET_ID","")
                            if _SA_s and _MSI_s:
                                _cr_s  = _Cr_s.from_service_account_info(
                                    _jj_s.loads(_SA_s),
                                    scopes=["https://www.googleapis.com/auth/spreadsheets"])
                                _cl_s  = _gsp_s.authorize(_cr_s)
                                _ws_s  = _cl_s.open_by_key(_MSI_s).worksheet("Master_DB")
                                _hd_s  = _ws_s.row_values(1)
                                if "slug" not in _hd_s:
                                    _ws_s.update_cell(1, len(_hd_s)+1, "slug")
                                    _hd_s.append("slug")
                                _sc_s  = _hd_s.index("slug") + 1
                                _rc_s  = _hd_s.index("restaurant_id") if "restaurant_id" in _hd_s else 0
                                for _i_s, _row_s in enumerate(_ws_s.get_all_values()[1:], start=2):
                                    if len(_row_s) > _rc_s and str(_row_s[_rc_s]).strip() == rid:
                                        _ws_s.update_cell(_i_s, _sc_s, clean_slug)
                                        break
                                try:
                                    requests.post(f"{ROUTER_URL}/cache/refresh",
                                                  headers={"X-Admin-Key": ADMIN_PASSWORD}, timeout=8)
                                except: pass
                                st.cache_data.clear()
                                new_url = f"{FRONTEND}/{clean_slug}"
                                st.success(f"✅ الرابط الجديد: {new_url}")
                                st.rerun()
                        except Exception as _e_s:
                            st.error(f"❌ {_e_s}")
                    else:
                        st.info("لم يتغير الـ slug")

            # ══ خانة الدومين الخاص (مستقبلاً) ══
            st.markdown("---")
            current_domain = r.get("custom_domain","").strip()
            st.markdown("**🌐 دومين خاص (اختياري):**")
            st.caption("إذا كان للمطعم دومين خاص مثل menu.restaurant.com — ضعه هنا")
            col_dom1, col_dom2 = st.columns([3,1])
            with col_dom1:
                new_domain = st.text_input(
                    "الدومين",
                    value=current_domain,
                    placeholder="https://menu.restaurant.ma",
                    key=f"dom_{uid}",
                    label_visibility="collapsed"
                )
            with col_dom2:
                if st.button("💾 حفظ", key=f"save_dom_{uid}", use_container_width=True):
                    if new_domain != current_domain:
                        try:
                            import gspread as _gsp_d
                            from google.oauth2.service_account import Credentials as _Cr_d
                            import json as _jj_d
                            _SA_d  = os.getenv("GOOGLE_SA_JSON_CONTENT","")
                            _MSI_d = os.getenv("MASTER_SHEET_ID","")
                            if _SA_d and _MSI_d:
                                _cr_d  = _Cr_d.from_service_account_info(
                                    _jj_d.loads(_SA_d),
                                    scopes=["https://www.googleapis.com/auth/spreadsheets"])
                                _cl_d  = _gsp_d.authorize(_cr_d)
                                _ws_d  = _cl_d.open_by_key(_MSI_d).worksheet("Master_DB")
                                _hd_d  = _ws_d.row_values(1)
                                # أضف عمود custom_domain إذا ناقص
                                if "custom_domain" not in _hd_d:
                                    _ws_d.update_cell(1, len(_hd_d)+1, "custom_domain")
                                    _hd_d.append("custom_domain")
                                _dc_d  = _hd_d.index("custom_domain") + 1
                                _rc_d  = _hd_d.index("restaurant_id") if "restaurant_id" in _hd_d else 0
                                for _i_d, _row_d in enumerate(_ws_d.get_all_values()[1:], start=2):
                                    if len(_row_d) > _rc_d and str(_row_d[_rc_d]).strip() == rid:
                                        _ws_d.update_cell(_i_d, _dc_d, new_domain.strip())
                                        break
                                # مسح cache فوراً
                                try:
                                    requests.post(f"{ROUTER_URL}/cache/refresh/{rid}",
                                                  headers={"X-Admin-Key": ADMIN_PASSWORD}, timeout=8)
                                    requests.post(f"{ROUTER_URL}/cache/refresh",
                                                  headers={"X-Admin-Key": ADMIN_PASSWORD}, timeout=8)
                                except: pass
                                st.cache_data.clear()
                                st.success("✅ تم حفظ الدومين وتطبيقه فوراً!")
                                st.rerun()
                        except Exception as _e_d:
                            st.error(f"❌ {_e_d}")
                    else:
                        st.info("لم يتغير الدومين")

                if st.button("🔴 تعطيل" if status=="active" else "🟢 تفعيل",
                             key=f"tog_{uid}"):
                    st.info("ميزة قريباً")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════
# 📦 pg_plans — إدارة الباقات
# ══════════════════════════════════════════════════════

PLANS = {
    "basic":   {"label":"🔵 أساسي",  "price":300, "color":"#3498db"},
    "pro":     {"label":"🟡 متكامل", "price":500, "color":"#C9A84C"},
    "premium": {"label":"👑 متميز",  "price":800, "color":"#9b59b6"},
}
PLAN_FEATURES_DISPLAY = {
    "basic": [
        "✅ مينيو QR أساسي", "✅ كوزينة + Telegram",
        "✅ نادل + ليفرور", "✅ تقارير أسبوعية",
        "✅ 15 طاولة",
        "❌ صور احترافية", "❌ توصيل GPS",
        "❌ تقارير يومية", "❌ كاشير دفع", "❌ AI مينيو",
    ],
    "pro": [
        "✅ كل الأساسي",
        "✅ QR بطاقات بصور احترافية",
        "✅ توصيل GPS للزبائن",
        "✅ تقارير يومية + شهرية",
        "✅ كاشير دفع متكامل",
        "✅ 30 طاولة",
        "✅ زر تعديل الأخطاء",
        "❌ AI لترتيب المينيو",
    ],
    "premium": [
        "✅ كل المتكامل",
        "✅ AI يقرأ ويرتب المينيو",
        "✅ صور AI مخصصة",
        "✅ طاولات غير محدودة",
        "✅ تقارير متقدمة",
        "✅ إعداد أول مطعم مجاناً",
        "✅ دعم فني مخصص 24/7",
    ],
}

def _update_master_field(rid, field, value):
    """✅ تحديث حقل في Supabase — مع تحويل النوع الصحيح لكل حقل"""
    try:
        import requests as _rq
        sb_url = SUPABASE_URL
        sb_key = SUPABASE_KEY
        if sb_url and sb_key:
            h = {"apikey":sb_key,"Authorization":f"Bearer {sb_key}",
                 "Content-Type":"application/json","Prefer":"return=minimal"}
            # ✅ FIX 7: تحويل القيمة للنوع الصحيح حسب الحقل
            BOOLEAN_FIELDS = {"delivery_active"}
            INT_FIELDS = {"num_tables", "max_restaurants"}
            if field in BOOLEAN_FIELDS:
                typed_val = value in (True, "true", "1", 1)
            elif field in INT_FIELDS:
                try: typed_val = int(value)
                except: typed_val = value
            else:
                typed_val = value
            resp = _rq.patch(
                f"{sb_url}/rest/v1/restaurants?restaurant_id=eq.{rid}",
                headers=h, json={field: typed_val}, timeout=8
            )
            # أيضاً حدّث Google Sheets عبر Router cache refresh
            try:
                router_url = os.getenv("ROUTER_BASE_URL","")
                admin_pass = os.getenv("ADMIN_PASSWORD","")
                if router_url and admin_pass:
                    _rq.post(f"{router_url}/cache/refresh/{rid}",
                             headers={"X-Admin-Key": admin_pass}, timeout=5)
            except: pass
    except: pass

def pg_plans(rs):
    st.markdown("## 📦 إدارة الباقات")
    if not rs:
        st.info("📭 لا توجد مطاعم"); return

    plan_counts = {"basic":0,"pro":0,"premium":0}
    for r in rs:
        p = r.get("plan","basic")
        if p in plan_counts: plan_counts[p] += 1

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("🔵 أساسي", plan_counts["basic"], "300 د.م/مطعم")
    with c2: st.metric("🟡 متكامل", plan_counts["pro"], "500 د.م/مطعم")
    with c3: st.metric("👑 متميز", plan_counts["premium"], "800 د.م/مطعم")
    total = plan_counts["basic"]*300 + plan_counts["pro"]*500 + plan_counts["premium"]*800
    with c4: st.metric("💰 إيراد شهري", f"{total:,} د.م")

    st.markdown("---")
    st.markdown("### 📋 الباقات المتاحة")
    pc1,pc2,pc3 = st.columns(3)
    for col,(pk,pi) in zip([pc1,pc2,pc3],PLANS.items()):
        with col:
            feats="".join(f"<div style=\'font-size:.78rem;padding:.2rem 0;color:#aaa\'>{f}</div>" for f in PLAN_FEATURES_DISPLAY[pk])
            st.markdown(f"""<div style="background:#111;border:1px solid {pi['color']}33;border-radius:12px;padding:1.2rem;text-align:center">
              <div style="font-size:1.1rem;font-weight:900;color:{pi['color']}">{pi['label']}</div>
              <div style="font-size:2rem;font-weight:900;color:{pi['color']}">{pi['price']}</div>
              <div style="font-size:.72rem;color:#555;margin-bottom:.8rem">درهم/شهر</div>
              {feats}</div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🏪 إدارة باقة كل مطعم")
    for r in rs:
        rid      = r.get("restaurant_id","")
        name     = r.get("name","—")
        cur_plan = r.get("plan","basic")
        delivery = str(r.get("delivery_active","false")).lower() in ("true","1")
        pi       = PLANS.get(cur_plan, PLANS["basic"])

        with st.expander(f"{pi['label']} | {name} — #{rid}"):
            col1, col2 = st.columns([2,1])
            with col1:
                new_plan = st.selectbox("📦 الباقة",
                    options=list(PLANS.keys()),
                    format_func=lambda x: f"{PLANS[x]['label']} — {PLANS[x]['price']} د.م/شهر",
                    index=list(PLANS.keys()).index(cur_plan) if cur_plan in PLANS else 0,
                    key=f"plan_{rid}")
                can_del = new_plan in ("pro","premium")
                if can_del:
                    new_del = st.checkbox("🛵 تفعيل التوصيل", value=delivery, key=f"del_{rid}")
                else:
                    st.markdown("<div style='font-size:.8rem;color:#e74c3c'>🛵 التوصيل: يتطلب باقة متكاملة أو متميزة</div>", unsafe_allow_html=True)
                    new_del = False
            with col2:
                for f in PLAN_FEATURES_DISPLAY.get(new_plan,[]):
                    color = "#2ecc71" if f.startswith("✅") else "#e74c3c"
                    st.markdown(f"<div style='font-size:.75rem;color:{color}'>{f}</div>", unsafe_allow_html=True)

            if st.button(f"💾 حفظ الباقة", key=f"save_plan_{rid}", use_container_width=True,
                         type="primary"):
                try:
                    import requests as _rqp
                    # ✅ 1) حفظ في Supabase مباشرة (boolean صحيح)
                    _ok1 = _sb_patch("restaurants", f"restaurant_id=eq.{rid}",
                                     {"plan": new_plan,
                                      "delivery_active": bool(new_del)})
                    # ✅ 2) حفظ عبر _update_master_field (Sheets backup)
                    _update_master_field(rid, "plan", new_plan)
                    _update_master_field(rid, "delivery_active", "true" if new_del else "false")
                    # ✅ 3) مسح cache الـ Router فوراً — يُطبَّق على المينيو لحظياً
                    try:
                        _rqp.post(f"{ROUTER_URL}/cache/refresh/{rid}",
                                  headers={"X-Admin-Key": SPASSWORD}, timeout=5)
                        _rqp.post(f"{ROUTER_URL}/cache/refresh",
                                  headers={"X-Admin-Key": SPASSWORD}, timeout=5)
                    except: pass
                    # ✅ 4) مسح cache الداشبورد
                    st.cache_data.clear()
                    del_status = "🛵 مع توصيل" if new_del else "بدون توصيل"
                    st.success(f"✅ {name} → {PLANS[new_plan]['label']} {del_status} — طُبِّق فوراً!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

            if st.button(f"📱 أرسل إشعار للمطعم", key=f"notif_{rid}", use_container_width=True):
                chat_id = r.get("telegram_chat_id","")
                if chat_id:
                    try:
                        import requests as _rq
                        plan_lbl = PLANS[new_plan]["label"]
                        price    = PLANS[new_plan]["price"]
                        feats_txt = chr(10).join(f"  {f}" for f in PLAN_FEATURES_DISPLAY[new_plan] if f.startswith("✅"))
                        msg = f"🎉 *تم تفعيل باقتك!*{chr(10)}━━━━━━{chr(10)}📦 الباقة: *{plan_lbl}*{chr(10)}💰 {price} درهم/شهر{chr(10)}━━━━━━{chr(10)}✅ ما تشمله:{chr(10)}{feats_txt}"
                        _rq.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                                 json={"chat_id":chat_id,"text":msg,"parse_mode":"Markdown"}, timeout=8)
                        st.success("✅ الإشعار أُرسل")
                    except Exception as e:
                        st.error(f"❌ {e}")
                else:
                    st.warning("⚠️ المطعم لم يربط Telegram بعد")

def main():
    if not auth(): return
    rs = fetch_all()
    # ══ تطبيق الثيم — CSS مباشر بدون JavaScript ══
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True

    if not st.session_state.dark_mode:
        st.markdown("""<style>
/* ══ وضع النهار — يُحقن مباشرة بـ Python كل render ══ */
:root, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"], .main, .block-container {
  --bg:#f7f3ec !important; --bg2:#ede8df !important; --bg3:#e4ddd2 !important;
  --sidebar:#ede8df !important;
  --text:#1a150a !important; --text2:#5a4820 !important; --text3:#9a8a60 !important;
  --border:#ccc4a8 !important; --border2:#ddd5bc !important;
  --gold:#7a5008 !important; --gold2:#a07030 !important; --gold-dim:#e8d8a0 !important;
  --card:#ffffff !important; --card-border:#ccc4a8 !important;
  --input-bg:#ffffff !important; --input-text:#1a150a !important;
  --input-border:#c8b890 !important;
  --btn-sidebar:linear-gradient(135deg,#7a5008,#5a3800) !important;
  --btn-sidebar-txt:#ffffff !important;
  --tab-active:#7a5008 !important;
  --shadow:0 2px 8px rgba(0,0,0,.12) !important;
}
/* الخلفيات */
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"], [data-testid="stHeader"],
.main, .block-container, [data-testid="stDecoration"]
{ background:#f7f3ec !important; color:#1a150a !important; }

section[data-testid="stSidebar"],
section[data-testid="stSidebar"]>div
{ background:#ede8df !important; }

/* كل النصوص */
section[data-testid="stSidebar"] *,
p, span, div, label, li, td, th, h1, h2, h3, h4, h5,
[data-testid="stMarkdown"] *, [data-testid="stMarkdownContainer"] *,
[data-testid="stText"] *, [data-testid="stCaption"] *,
.stMarkdown *, .element-container *
{ color:#1a150a !important; }

/* الحقول */
input, textarea, select,
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-baseweb="input"] input, [data-baseweb="textarea"]
{ background:#ffffff !important; color:#1a150a !important;
  border-color:#c8b890 !important; }
::placeholder { color:#9a8a60 !important; opacity:1 !important; }

/* الأزرار */
.stButton>button
{ background:#e8d8a0 !important; color:#7a5008 !important;
  border:1px solid #c8b890 !important; }
.stButton>button:hover
{ background:linear-gradient(135deg,#7a5008,#5a3800) !important;
  color:#ffffff !important; border-color:#7a5008 !important; }

/* أزرار السيدبار */
section[data-testid="stSidebar"] .stButton>button
{ background:#e8d8a0 !important; color:#7a5008 !important;
  border:1px solid #ccc4a8 !important; font-weight:600 !important; }
section[data-testid="stSidebar"] .stButton>button:hover
{ background:linear-gradient(135deg,#7a5008,#5a3800) !important;
  color:#ffffff !important; }

/* selectbox */
[data-baseweb="select"]>div,
[data-baseweb="select"] [class*="control"],
[data-baseweb="select"] [class*="singleValue"],
[data-baseweb="select"] [class*="placeholder"]
{ background:#ffffff !important; color:#1a150a !important;
  border-color:#c8b890 !important; }
[data-baseweb="select"] [class*="menu"],
[data-baseweb="popover"]>div
{ background:#f7f3ec !important; border-color:#ccc4a8 !important; }
[data-baseweb="select"] [class*="option"]
{ background:#f7f3ec !important; color:#1a150a !important; }
[data-baseweb="select"] [class*="option"]:hover
{ background:#e8d8a0 !important; }

/* تابات */
[data-baseweb="tab-list"], [role="tablist"]
{ background:#ede8df !important; border-color:#ccc4a8 !important; }
[data-baseweb="tab"], [role="tab"]
{ color:#5a4820 !important; }
[aria-selected="true"][data-baseweb="tab"],
[aria-selected="true"][role="tab"]
{ color:#7a5008 !important; border-bottom-color:#7a5008 !important;
  background:transparent !important; }

/* expanders */
[data-testid="stExpander"]>details,
[data-testid="stExpander"]
{ background:#ffffff !important; border-color:#ccc4a8 !important; }
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary *
{ color:#1a150a !important; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stExpander"] [data-testid="stExpanderDetails"] *
{ background:#ffffff !important; color:#1a150a !important; }

/* metrics */
[data-testid="stMetricValue"] { color:#7a5008 !important; }
[data-testid="stMetricLabel"] { color:#5a4820 !important; }
[data-testid="stMetric"], [data-testid="metric-container"]
{ background:#ffffff !important; border-color:#ccc4a8 !important; }

/* code */
code, pre, [data-testid="stCode"]>div
{ background:#e4ddd2 !important; color:#7a5008 !important;
  border-color:#ccc4a8 !important; }

/* alerts */
[data-testid="stAlert"] { border-radius:10px !important; }

/* radio / checkbox */
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label,
[data-testid="stRadio"] p, [data-testid="stCheckbox"] p,
[data-testid="stRadio"] span, [data-testid="stCheckbox"] span
{ color:#1a150a !important; }

/* file uploader */
[data-testid="stFileUploader"]>div
{ background:#e4ddd2 !important; border-color:#ccc4a8 !important; }
[data-testid="stFileUploader"] *
{ color:#1a150a !important; }

/* slider */
[data-testid="stSlider"] *
{ color:#1a150a !important; }

/* tabs panel */
[data-baseweb="tab-panel"] *
{ color:#1a150a !important; }

/* custom cards in page */
.s-card,.r-card,.iblk,.tgbox,.info-box
{ background:#ffffff !important; border-color:#ccc4a8 !important; }
.s-num,.r-name,.iv { color:#7a5008 !important; }
.s-lbl,.r-meta,.il { color:#5a4820 !important; }

/* table */
table, th, td { color:#1a150a !important; }
th { background:#e4ddd2 !important; color:#7a5008 !important; }

/* ══ iframe / stIFrame — preview cards ══ */
[data-testid="stIFrame"] { background:#ffffff !important; }

/* ══ كل الصناديق السوداء المتبقية ══ */
[data-testid="stImage"] > div,
[data-testid="stVerticalBlock"] > div,
[class*="stBlock"] { background:transparent !important; }

/* ══ info/warning/error boxes ══ */
[data-testid="stAlert"] > div
{ background:#f0f0f0 !important; color:#1a150a !important; }
[data-baseweb="notification"]
{ background:#f0f0f0 !important; }

/* ══ المحاور (axes) في صفحة صور الأكلات ══ */
[data-testid="stHorizontalBlock"] > div,
[data-testid="stColumn"] > div
{ background:transparent !important; }

/* ══ color picker ══ */
[data-baseweb="popover"] *
{ background:#f7f3ec !important; color:#1a150a !important; }

/* ══ markdown html blocks ══ */
.stMarkdown div, .element-container div
{ background:transparent !important; }

/* ══ progress/spinner ══ */
[data-testid="stSpinner"] { color:#7a5008 !important; }

/* ══ checkbox ══ */
[data-baseweb="checkbox"] div
{ background:transparent !important; }
[data-baseweb="checkbox"] [aria-checked="true"] div
{ background:#7a5008 !important; }

/* ══ number input buttons ══ */
.stNumberInput button
{ background:#e8d8a0 !important; color:#7a5008 !important;
  border-color:#c8b890 !important; }

/* ══ radio buttons ══ */
[data-baseweb="radio"] [role="radio"]
{ border-color:#7a5008 !important; }
[data-baseweb="radio"] [role="radio"][aria-checked="true"]
{ background:#7a5008 !important; }

/* ══ الحاوية الرئيسية لكل element ══ */
.element-container { background:transparent !important; }

/* ══ stForm ══ */
[data-testid="stForm"]
{ background:#ffffff !important; border:1px solid #ccc4a8 !important;
  border-radius:10px !important; padding:1rem !important; }

/* ══ تأكيد: كل * في الـ app ══ */
.stApp * { color:inherit !important; }
.stApp { color:#1a150a !important; }
</style>""", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown('<div style="color:#C9A84C;font-size:1.1rem;font-weight:900;'
                    'text-align:center;padding:.5rem 0">👑 الإمبراطور</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div style="text-align:center;color:#444;font-size:.75rem">'
                    f'{len(rs)} مطعم مسجّل</div>', unsafe_allow_html=True)
        st.markdown("---")
        # ✅ أزرار تنقل نظيفة — زر واحد فقط
        nav_items = [
            ("🏠 Dashboard",      "🏠 Dashboard"),
            ("🚀 إضافة مطعم",    "🚀 إضافة مطعم"),
            ("🍽️ إدارة القائمة", "🍽️ إدارة القائمة"),
            ("🖼️ صور الأكلات",   "🖼️ صور الأكلات"),
            ("🖨️ بطاقات PDF",    "🖨️ بطاقات PDF"),
            ("⚙️ إدارة",          "⚙️ إدارة"),
            ("📦 الباقات",        "📦 الباقات"),
            ("🏢 الوكالات",       "🏢 الوكالات"),
        ]
        if "page" not in st.session_state:
            st.session_state["page"] = "🏠 Dashboard"
        active = st.session_state.get("page","🏠 Dashboard")

        # CSS: كل أزرار الـ sidebar ذهبية، النشط أغمق
        active_idx = [k for _,k in nav_items].index(active) if active in [k for _,k in nav_items] else 0
        css_btns = ""
        for i,(lbl,key) in enumerate(nav_items):
            if key == active:
                css_btns += f"""
        div[data-testid="stSidebar"] .stButton:nth-of-type({i+1})>button {{
            background:var(--btn-sidebar)!important;
            color:var(--btn-sidebar-txt)!important;
            font-weight:800!important;
            border:2px solid var(--gold)!important;
        }}"""
        st.markdown(f"""<style>
        div[data-testid="stSidebar"] .stButton>button {{
            width:100%; border-radius:10px; padding:.5rem .8rem;
            background:var(--gold-dim); color:var(--gold);
            border:1px solid var(--border); font-size:.88rem;
            margin:.1rem 0; transition:all .2s; font-weight:600;
        }}
        div[data-testid="stSidebar"] .stButton>button:hover {{
            background:var(--btn-sidebar)!important;
            color:var(--btn-sidebar-txt)!important;
            border-color:var(--gold)!important;
        }}
        {css_btns}
        </style>""", unsafe_allow_html=True)

        for label, key in nav_items:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["page"] = key
                st.rerun()

        page = st.session_state.get("page", "🏠 Dashboard")
        st.markdown("---")
        mode_label = "☀️ وضع النهار" if st.session_state.dark_mode else "🌙 وضع الليل"
        if st.button(mode_label, use_container_width=True, key="btn_theme"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()
        if st.button("🚪 خروج", use_container_width=True, key="btn_logout"):
            st.session_state.ok = False; st.rerun()

    if   page == "🏠 Dashboard":      pg_dashboard(rs)
    elif page == "🚀 إضافة مطعم":    pg_add(rs)
    elif page == "🍽️ إدارة القائمة": page_menu_manager(rs)
    elif page == "🖼️ صور الأكلات":   page_images(rs)
    elif page == "🖨️ بطاقات PDF":    pg_pdf(rs)
    elif page == "⚙️ إدارة":          pg_manage(rs)
    elif page == "📦 الباقات":        pg_plans(rs)
    elif page == "🏢 الوكالات":       page_agencies()

if __name__ == "__main__":
    main()
