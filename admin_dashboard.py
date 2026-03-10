"""
👑 admin_dashboard.py — لوحة الإمبراطور النهائية
الإصلاحات:
  ✅ إصلاح خطأ duplicate headers في Master DB
  ✅ الواجهة الأولى = QR للصفحة | الواجهة الثانية = QR WiFi
  ✅ زر PDF يعمل بدون إعادة إنشاء (session_state)
  ✅ تحميل QR/WiFi بدون إعادة إنشاء (session_state)
"""
import streamlit as st
import gspread, io, os, json, time, requests
from google.oauth2.service_account import Credentials
from datetime import datetime
from dotenv import load_dotenv

from auto_provisioner import provision_restaurant, send_test, ProvisionResult, build_reg_link
from generative_design import generate_table_card, card_to_bytes
from pdf_generator import generate_table_tents_pdf, generate_single_table_preview
from page_images import page_images

load_dotenv()

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID","")
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD","admin2024")
ROUTER_URL      = os.getenv("ROUTER_BASE_URL","https://your-api.onrender.com")
FRONTEND_URL    = os.getenv("FRONTEND_URL","https://your-menu.netlify.app")
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")

# ══════════════════════════════════════════════════════════
st.set_page_config(page_title="👑 لوحة الإمبراطور",page_icon="👑",
                   layout="wide",initial_sidebar_state="expanded")
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
.s-lbl{font-size:.75rem;color:#333;margin-top:.2rem}
.r-card{background:#101010;border:1px solid #1a1a1a;border-left:3px solid #C9A84C;
  border-radius:10px;padding:.8rem 1rem;margin-bottom:.5rem}
.r-name{font-size:.9rem;font-weight:700;color:#E8C97A}
.r-meta{font-size:.7rem;color:#333;margin-top:.2rem}
.res{border-radius:10px;padding:1rem 1.2rem;margin:.7rem 0;line-height:1.8}
.ok{background:rgba(0,230,118,.07);border:1px solid rgba(0,230,118,.2);color:#69f0ae}
.err{background:rgba(229,57,53,.07);border:1px solid rgba(229,57,53,.2);color:#ef9a9a}
.warn{background:rgba(255,193,7,.07);border:1px solid rgba(255,193,7,.2);color:#ffe57f}
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
.prg-in{height:100%;border-radius:6px;background:linear-gradient(90deg,#C9A84C,#E8C97A);transition:width .4s}
.stButton>button{background:linear-gradient(135deg,#C9A84C,#8a6020)!important;
  color:#000!important;font-weight:700!important;border:none!important;border-radius:8px!important;transition:all .2s!important}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 6px 20px rgba(201,168,76,.3)!important}
.stTextInput>div>div>input,.stTextArea textarea,.stSelectbox>div>div>div,.stNumberInput>div>div>input{
  background:#111!important;color:#eee!important;border:1px solid #222!important;border-radius:8px!important}
.stTextInput>div>div>input:focus,.stTextArea textarea:focus{
  border-color:#C9A84C!important;box-shadow:0 0 0 2px rgba(201,168,76,.15)!important}
label{color:#555!important;font-size:.8rem!important}
.stTabs [data-baseweb="tab-list"]{background:#0e0e0e!important;border-radius:8px;padding:3px}
.stTabs [data-baseweb="tab"]{color:#444!important;border-radius:6px!important}
.stTabs [aria-selected="true"]{background:#C9A84C!important;color:#000!important;font-weight:700!important}
</style>
""",unsafe_allow_html=True)

# ══ AUTH ══════════════════════════════════════════════════
def auth():
    if st.session_state.get("ok"): return True
    st.markdown('<div class="g-title">👑 لوحة الإمبراطور</div>',unsafe_allow_html=True)
    col=st.columns([1,1.1,1])[1]
    with col:
        p=st.text_input("🔑 كلمة المرور",type="password")
        if st.button("دخول 🚀",use_container_width=True):
            if p==ADMIN_PASSWORD: st.session_state.ok=True; st.rerun()
            else: st.error("❌ خطأ")
    return False

# ══ SHEETS ════════════════════════════════════════════════
@st.cache_resource(ttl=300)
def gs():
    try:
        if SA_JSON_CONTENT:
            c=Credentials.from_service_account_info(json.loads(SA_JSON_CONTENT),scopes=SCOPES)
        else:
            c=Credentials.from_service_account_file(SA_JSON_PATH,scopes=SCOPES)
        return gspread.authorize(c)
    except Exception as e: st.error(f"Google: {e}"); return None

def fetch_all():
    """
    ✅ إصلاح: استخدام get_all_values() بدلاً من get_all_records()
    لتفادي خطأ duplicate headers
    """
    c=gs()
    if not c or not MASTER_SHEET_ID: return []
    try:
        ws = c.open_by_key(MASTER_SHEET_ID).sheet1
        all_values = ws.get_all_values()
        if not all_values or len(all_values) < 2:
            return []
        # أول صف = headers
        headers = all_values[0]
        # إزالة الأعمدة المكررة بإضافة suffix
        seen = {}
        clean_headers = []
        for h in headers:
            if h in seen:
                seen[h] += 1
                clean_headers.append(f"{h}_{seen[h]}")
            else:
                seen[h] = 0
                clean_headers.append(h)
        # تحويل لـ list of dicts
        records = []
        for row in all_values[1:]:
            # تجاهل الصفوف الفارغة
            if not any(cell.strip() for cell in row):
                continue
            # تمديد الصف إذا كان أقصر من الـ headers
            padded = row + [''] * (len(clean_headers) - len(row))
            records.append(dict(zip(clean_headers, padded)))
        return records
    except Exception as e:
        st.error(f"Master DB: {e}")
        return []

def del_r(rid):
    c=gs()
    if not c: return False
    try:
        ws=c.open_by_key(MASTER_SHEET_ID).sheet1
        all_values = ws.get_all_values()
        if not all_values: return False
        headers = all_values[0]
        rid_col = headers.index("restaurant_id") if "restaurant_id" in headers else 0
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) > rid_col and str(row[rid_col]) == str(rid):
                ws.delete_rows(i)
                return True
    except Exception as e:
        st.error(f"حذف: {e}")
    return False

def nxt(rs):
    if not rs: return "1"
    ids=[int(r.get("restaurant_id",0)) for r in rs if str(r.get("restaurant_id","")).isdigit()]
    return str(max(ids)+1) if ids else "1"

# ══ HELPERS لـ session_state ══════════════════════════════
def _store_cards(key_prefix, menu_bytes, wifi_bytes):
    """حفظ البطاقتين في session_state"""
    st.session_state[f"{key_prefix}_menu_bytes"] = menu_bytes
    st.session_state[f"{key_prefix}_wifi_bytes"]  = wifi_bytes

def _store_pdf(key, pdf_bytes):
    """حفظ PDF في session_state"""
    st.session_state[f"pdf_{key}"] = pdf_bytes

# ══ DASHBOARD ═════════════════════════════════════════════
def pg_dashboard(rs):
    st.markdown('<div class="g-title">👑 لوحة الإمبراطور</div>',unsafe_allow_html=True)
    st.markdown('<div class="gdiv"></div>',unsafe_allow_html=True)
    total=len(rs); active=sum(1 for r in rs if r.get("status","active")=="active")
    pending=sum(1 for r in rs if r.get("status","")=="pending_telegram")
    c1,c2,c3,c4=st.columns(4)
    for col,n,lbl in [(c1,total,"🍽️ المطاعم"),(c2,active,"✅ نشطة"),(c3,pending,"⏳ Telegram"),(c4,sum(1 for r in rs if r.get("style")=="luxury"),"✨ فاخر")]:
        col.markdown(f'<div class="s-card"><div class="s-num">{n}</div><div class="s-lbl">{lbl}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="gdiv"></div>',unsafe_allow_html=True)
    cl,cr=st.columns([3,2])
    with cl:
        st.markdown("### 🍽️ المطاعم")
        if not rs: st.info("📭 أضف أول مطعم")
        for r in rs:
            sm={"luxury":"✨","modern":"⚡","classic":"🏛️"}
            st_cls="badge-g" if r.get("status","active")=="active" else "badge"
            st_lbl="🟢 نشط" if r.get("status","active")=="active" else "⏳ Telegram"
            mu=f"{FRONTEND_URL}?rest_id={r.get('restaurant_id')}"
            su=f"https://docs.google.com/spreadsheets/d/{r.get('sheet_id','')}/edit"
            st.markdown(f"""<div class="r-card">
              <div class="r-name">#{r.get('restaurant_id')} — {r.get('name')}</div>
              <div class="r-meta">
                <span class="badge">{sm.get(r.get('style',''),'')} {r.get('style','')}</span>
                <span class="{st_cls}" style="margin-left:.4rem">{st_lbl}</span>
                &nbsp; 📶 {r.get('wifi_ssid','')} &nbsp; 🪑 {r.get('num_tables','')}
              </div>
              <div class="r-meta" style="margin-top:.25rem">
                📱 <a href="{mu}" target="_blank" style="color:#C9A84C">{mu[:50]}...</a>
                &nbsp;|&nbsp; 📊 <a href="{su}" target="_blank" style="color:#3a3a7a">الشيت</a>
              </div></div>""",unsafe_allow_html=True)
    with cr:
        st.markdown("### 🔌 النظام")
        try:
            r=requests.get(f"{ROUTER_URL}/health",timeout=4)
            cls="ok" if r.status_code==200 else "warn"
            msg=f"🟢 API يعمل" if r.status_code==200 else f"🟡 {r.status_code}"
        except: cls="err"; msg="🔴 API غير متاح"
        st.markdown(f'<div class="res {cls}">{msg}</div>',unsafe_allow_html=True)
        st.code(f"API: {ROUTER_URL}\nFrontend: {FRONTEND_URL}")

# ══ ADD RESTAURANT ════════════════════════════════════════
def pg_add(rs):
    st.markdown("## 🚀 إضافة مطعم جديد")
    SA_EMAIL = "restaurant-bot@gen-lang-client-0967477901.iam.gserviceaccount.com"
    st.markdown(f'''<div class="res warn">
    📋 <b>الخطوات لصاحب المطعم قبل الإضافة:</b><br>
    1️⃣ يفتح <a href="https://sheets.google.com" target="_blank" style="color:#C9A84C">sheets.google.com</a> → ينشئ Spreadsheet جديد<br>
    2️⃣ يشاركه مع <b style="color:#C9A84C">{SA_EMAIL}</b> كـ <b>Editor</b><br>
    3️⃣ ينسخ الـ ID من الرابط ويلصقه أسفل
    </div>''',unsafe_allow_html=True)

    t1,t2,t3=st.tabs(["📋 المعلومات","🎨 الهوية البصرية","📶 WiFi"])
    with t1:
        c1,c2=st.columns(2)
        with c1:
            rid      =st.text_input("🔢 رقم المطعم",value=nxt(rs))
            rname    =st.text_input("🏪 اسم المطعم *",placeholder="مطعم النخيل الذهبي")
            rsheetid =st.text_input("📊 Sheet ID *",placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",help="ID من رابط الـ Spreadsheet")
            remail   =st.text_input("📧 بريد صاحب المطعم (اختياري)",placeholder="owner@gmail.com")
        with c2:
            rtables=st.number_input("🪑 عدد الطاولات",1,100,10)
            rlogo  =st.text_input("🖼️ رابط اللوجو (اختياري)",placeholder="https://...")
            st.markdown('<div class="res warn" style="font-size:.78rem;padding:.6rem .9rem">📨 Telegram: لا تحتاج Chat ID — رابط تلقائي يُولد بعد الإنشاء</div>',unsafe_allow_html=True)

    defs={"luxury":("#0a0804","#C9A84C"),"modern":("#121212","#00DCB4"),"classic":("#fcf8ee","#8B4513")}
    with t2:
        c1,c2=st.columns(2)
        with c1:
            rstyle =st.selectbox("🎭 الطابع",["luxury","modern","classic"],
                format_func=lambda x:{"luxury":"✨ فاخر","modern":"⚡ عصري","classic":"🏛️ كلاسيكي"}[x])
            dp,da  =defs[rstyle]
            rprimary=st.color_picker("🎨 اللون الأساسي",dp)
            raccent =st.color_picker("✨ لون التمييز",da)
        with c2:
            st.markdown("##### 👁️ معاينة")
            st.markdown(f'<div style="background:{rprimary};border:2px solid {raccent};border-radius:12px;padding:1.2rem;text-align:center"><div style="color:{raccent};font-size:1.1rem;font-weight:900">{rname or "اسم المطعم"}</div><div style="color:{raccent};opacity:.4;font-size:.8rem;margin-top:.2rem">{rstyle}</div></div>',unsafe_allow_html=True)
            if st.button("🖼️ معاينة بطاقة طاولة") and rname:
                with st.spinner("🎨..."):
                    menu_img, wifi_img = generate_table_card(
                        rname,"WiFi","pass",1,
                        f"{FRONTEND_URL}?rest_id={rid}&table=1",
                        rstyle,rprimary,raccent
                    )
                st.image(card_to_bytes(menu_img),use_column_width=True,caption="📱 QR المينيو")
                st.image(card_to_bytes(wifi_img),use_column_width=True,caption="📶 QR WiFi")

    with t3:
        c1,c2=st.columns(2)
        with c1:
            rssid =st.text_input("📶 اسم الشبكة (SSID) *",placeholder="Resto_NakhilDhahabi")
            rwpass=st.text_input("🔒 كلمة مرور WiFi",type="password")

    st.markdown('<div class="gdiv"></div>',unsafe_allow_html=True)
    if st.button("🚀 إنشاء المطعم — كل شيء أوتوماتيكي!",use_container_width=True):
        errs=[]
        if not rname.strip(): errs.append("اسم المطعم مطلوب")
        if not rsheetid.strip(): errs.append("Sheet ID مطلوب")
        if not rssid.strip(): errs.append("SSID مطلوب")
        if errs:
            for e in errs: st.error(f"❌ {e}")
            return

        steps_lbl=["📊 الشيت","🔗 المشاركة","💾 DB","🤖 Telegram","✅ اكتمل"]
        pb=st.empty(); pl=st.empty()

        def show(cur,logs):
            h="".join(f'<div class="stp {"done" if i<cur else "now" if i==cur else ""}">{l}</div>' for i,l in enumerate(steps_lbl))
            pct=int((cur/len(steps_lbl))*100)
            pb.markdown(f'<div class="steps">{h}</div><div class="prg-out"><div class="prg-in" style="width:{pct}%"></div></div>',unsafe_allow_html=True)
            pl.markdown(f'<div style="background:#050f05;border:1px solid #0a2a0a;border-radius:8px;padding:.8rem;font-family:monospace;font-size:.8rem;color:#69f0ae;line-height:1.7">{"<br>".join(logs)}</div>',unsafe_allow_html=True)

        show(0,["⏳ جارٍ الإنشاء..."])
        result:ProvisionResult=provision_restaurant(
            restaurant_id=rid.strip(),name=rname.strip(),
            sheet_id=rsheetid.strip(),
            wifi_ssid=rssid.strip(),wifi_password=rwpass.strip(),
            style=rstyle,primary_color=rprimary,accent_color=raccent,
            num_tables=rtables,logo_url=rlogo.strip(),owner_email=remail.strip())

        done=len([s for s in result.steps if "✅" in s])
        show(min(done,len(steps_lbl)-1),result.steps)
        pb.empty(); pl.empty()

        if result.success:
            show(5,result.steps)
            st.markdown(f'<div class="res ok"><b>🎉 تم إنشاء "{rname}" بنجاح!</b><br><br>{"<br>".join(result.steps)}</div>',unsafe_allow_html=True)
            mu=f"{FRONTEND_URL}?rest_id={rid}"
            su=f"https://docs.google.com/spreadsheets/d/{result.sheet_id}/edit"
            c1,c2,c3=st.columns(3)
            c1.markdown(f'<div class="iblk"><div class="il">📱 رابط المينيو</div><div class="iv"><a href="{mu}" target="_blank" style="color:#C9A84C">{mu}</a></div></div>',unsafe_allow_html=True)
            c2.markdown(f'<div class="iblk"><div class="il">📊 Google Sheet</div><div class="iv"><a href="{su}" target="_blank" style="color:#C9A84C">افتح الشيت</a></div></div>',unsafe_allow_html=True)
            c3.markdown(f'<div class="iblk"><div class="il">🔢 رقم المطعم</div><div class="iv">{rid}</div></div>',unsafe_allow_html=True)

            if result.reg_link:
                st.markdown(f"""<div class="tgbox">
                  <b style="color:#29b6f6">📨 رابط Telegram — أرسله لصاحب المطعم:</b><br>
                  <div style="background:#0d1a24;border:1px solid rgba(0,136,204,.3);border-radius:8px;
                       padding:.6rem 1rem;font-family:monospace;font-size:.85rem;color:#29b6f6;margin:.5rem 0;word-break:break-all">
                    {result.reg_link}
                  </div>
                  <small style="color:#555">صاحب المطعم يضغطه مرة واحدة فقط → يتفعل تلقائياً</small>
                </div>""",unsafe_allow_html=True)
                st.code(result.reg_link,language=None)

            st.markdown('<div class="gdiv"></div>',unsafe_allow_html=True)
            st.markdown("### 🔲 بطاقات الطاولات")

            with st.spinner("🎨 توليد البطاقات..."):
                # ✅ الواجهة الأولى = QR المينيو | الواجهة الثانية = QR WiFi
                menu_img, wifi_img = generate_table_card(
                    rname, rssid, rwpass, 1,
                    f"{mu}&table=1", rstyle, rprimary, raccent
                )
                # تحويل لـ bytes وحفظ في session_state
                mb = io.BytesIO(); menu_img.save(mb,"PNG"); mb.seek(0)
                wb = io.BytesIO(); wifi_img.save(wb,"PNG"); wb.seek(0)
                menu_bytes = mb.getvalue()
                wifi_bytes = wb.getvalue()

            # ✅ حفظ في session_state لتجنب إعادة التوليد عند الضغط
            st.session_state["last_menu_bytes"] = menu_bytes
            st.session_state["last_wifi_bytes"]  = wifi_bytes
            st.session_state["last_rname"]       = rname
            st.session_state["last_rssid"]       = rssid
            st.session_state["last_rwpass"]       = rwpass
            st.session_state["last_mu"]           = mu
            st.session_state["last_rstyle"]       = rstyle
            st.session_state["last_rprimary"]     = rprimary
            st.session_state["last_raccent"]      = raccent
            st.session_state["last_rtables"]      = rtables
            st.session_state["last_rid"]          = rid

            _show_cards_and_pdf()
            st.cache_resource.clear()
        else:
            st.markdown(f'<div class="res err"><b>❌ {result.error}</b><br>{"<br>".join(result.steps)}</div>',unsafe_allow_html=True)

    # ✅ إذا كانت البطاقات محفوظة مسبقاً — اعرضها مباشرة
    elif st.session_state.get("last_menu_bytes"):
        st.markdown('<div class="gdiv"></div>',unsafe_allow_html=True)
        st.markdown("### 🔲 بطاقات الطاولات (آخر إنشاء)")
        _show_cards_and_pdf()


def _show_cards_and_pdf():
    """
    ✅ عرض البطاقتين وأزرار التحميل والـ PDF
    يستخدم session_state — لا يحتاج إعادة إنشاء
    """
    menu_bytes = st.session_state.get("last_menu_bytes")
    wifi_bytes  = st.session_state.get("last_wifi_bytes")
    rname       = st.session_state.get("last_rname","المطعم")
    rssid       = st.session_state.get("last_rssid","WiFi")
    rwpass      = st.session_state.get("last_rwpass","")
    mu          = st.session_state.get("last_mu","")
    rstyle      = st.session_state.get("last_rstyle","luxury")
    rprimary    = st.session_state.get("last_rprimary","#0a0804")
    raccent     = st.session_state.get("last_raccent","#C9A84C")
    rtables     = st.session_state.get("last_rtables",10)
    rid         = st.session_state.get("last_rid","1")

    if not menu_bytes or not wifi_bytes:
        return

    qc1, qc2 = st.columns(2)
    with qc1:
        # ✅ الواجهة الأولى = QR المينيو (صفحة الطلب)
        st.image(menu_bytes, caption="📱 QR المينيو — يفتح صفحة الطلب", use_column_width=True)
        st.download_button(
            "⬇️ تحميل QR المينيو",
            menu_bytes,
            f"Menu_QR_{rname}.png",
            "image/png",
            use_container_width=True,
            key="dl_menu_qr"
        )
    with qc2:
        # ✅ الواجهة الثانية = QR WiFi
        st.image(wifi_bytes, caption="📶 QR WiFi — يتصل بالشبكة مباشرة", use_column_width=True)
        st.download_button(
            "⬇️ تحميل QR WiFi",
            wifi_bytes,
            f"WiFi_QR_{rname}.png",
            "image/png",
            use_container_width=True,
            key="dl_wifi_qr"
        )

    st.markdown('<div class="gdiv"></div>',unsafe_allow_html=True)

    # ✅ زر PDF — يعمل مع session_state
    col1, col2 = st.columns([1, 2])
    with col1:
        generate_pdf = st.button(
            f"📄 PDF كامل لجميع الطاولات ({rtables} طاولة)",
            use_container_width=True,
            key="btn_gen_pdf"
        )

    if generate_pdf:
        with st.spinner(f"⏳ جاري إنشاء {rtables * 2} صفحة..."):
            pdf_bytes = generate_table_tents_pdf(
                rname, rssid, rwpass,
                FRONTEND_URL, rid, rtables,
                rstyle, rprimary, raccent
            )
        st.session_state["last_pdf_bytes"] = pdf_bytes
        st.session_state["last_pdf_name"]  = rname

    # ✅ زر التحميل يبقى ظاهراً حتى بعد الضغط
    if st.session_state.get("last_pdf_bytes"):
        pdf_name = st.session_state.get("last_pdf_name", rname)
        st.success(f"✅ PDF جاهز — {rtables} طاولة | {rtables*2} صفحة")
        st.download_button(
            f"⬇️ تحميل PDF ({rtables*2} صفحة)",
            st.session_state["last_pdf_bytes"],
            f"Tents_{pdf_name}.pdf",
            "application/pdf",
            use_container_width=True,
            key="dl_pdf_final"
        )


# ══ PDF ═══════════════════════════════════════════════════
def pg_pdf(rs):
    st.markdown("## 🖨️ بطاقات الطاولات — PDF")
    if not rs: st.info("📭 أضف مطعماً أولاً"); return
    opts={f"#{r['restaurant_id']} — {r['name']}":r for r in rs}
    sel=st.selectbox("المطعم",list(opts.keys())); r=opts[sel]
    c1,c2=st.columns(2)
    with c1:
        n=st.number_input("عدد الطاولات",1,int(r.get("num_tables",10)),int(r.get("num_tables",10)))
        pv=st.number_input("معاينة طاولة رقم",1,n,1)
    pc1,pc2=st.columns(2)
    with pc1:
        if st.button("👁️ معاينة",use_container_width=True):
            with st.spinner("🎨..."):
                # ✅ swap: menu first, wifi second
                menu_img, wifi_img = generate_single_table_preview(
                    r["name"],r.get("wifi_ssid","WiFi"),r.get("wifi_password",""),
                    FRONTEND_URL,r["restaurant_id"],pv,
                    r.get("style","luxury"),r.get("primary_color","#0a0804"),r.get("accent_color","#C9A84C")
                )
                m_bytes = card_to_bytes(menu_img)
                w_bytes = card_to_bytes(wifi_img)
                st.session_state["preview_menu"] = m_bytes
                st.session_state["preview_wifi"]  = w_bytes

    if st.session_state.get("preview_menu"):
        ca,cb=st.columns(2)
        ca.image(st.session_state["preview_menu"],caption=f"📱 QR المينيو T{pv}",use_column_width=True)
        cb.image(st.session_state["preview_wifi"],caption=f"📶 QR WiFi T{pv}",use_column_width=True)

    with pc2:
        gen_pdf = st.button("📄 توليد PDF",use_container_width=True)

    if gen_pdf:
        with st.spinner(f"⏳ {n*2} صفحة..."):
            pdf = generate_table_tents_pdf(
                r["name"],r.get("wifi_ssid","WiFi"),r.get("wifi_password",""),
                FRONTEND_URL,r["restaurant_id"],n,
                r.get("style","luxury"),r.get("primary_color","#0a0804"),r.get("accent_color","#C9A84C")
            )
        st.session_state["pg_pdf_bytes"] = pdf
        st.session_state["pg_pdf_name"]  = r["name"]
        st.session_state["pg_pdf_n"]     = n

    # ✅ زر التحميل مستقل عن التوليد
    if st.session_state.get("pg_pdf_bytes"):
        _n = st.session_state.get("pg_pdf_n", n)
        st.success(f"✅ {_n} طاولة | {_n*2} صفحة جاهزة")
        st.download_button(
            "⬇️ تحميل PDF",
            st.session_state["pg_pdf_bytes"],
            f"Tents_{st.session_state.get('pg_pdf_name','')}.pdf",
            "application/pdf",
            use_container_width=True,
            key="dl_pg_pdf"
        )

# ══ MANAGE ════════════════════════════════════════════════
def pg_manage(rs):
    st.markdown("## ⚙️ إدارة المطاعم")
    st.markdown("### 🤖 إعداد Telegram Webhook")
    st.markdown('<div class="res warn" style="font-size:.8rem">يُسجَّل مرة واحدة فقط بعد Deploy على Render</div>',unsafe_allow_html=True)
    if st.button("🔗 تسجيل Webhook"):
        try:
            r=requests.get(f"{ROUTER_URL}/webhook/set?base_url={ROUTER_URL}",timeout=10)
            data=r.json()
            if data.get("✅"): st.success(f"✅ Webhook مسجل: {ROUTER_URL}/webhook/telegram")
            else: st.error(str(data))
        except Exception as e: st.error(str(e))
    st.markdown('<div class="gdiv"></div>',unsafe_allow_html=True)
    if not rs: st.info("لا توجد مطاعم"); return
    for r in rs:
        with st.expander(f"#{r.get('restaurant_id')} — {r.get('name')} {'🟢' if r.get('status','active')=='active' else '⏳'}"):
            c1,c2,c3=st.columns([2,2,1])
            with c1:
                sid=r.get("sheet_id","")
                su=f"https://docs.google.com/spreadsheets/d/{sid}/edit" if sid else "#"
                st.markdown(f"**📊** [{sid[:25]}...]({su})\n\n**📨 Telegram:** `{r.get('telegram_chat_id','⏳ لم يُربط')}`\n\n**📶** `{r.get('wifi_ssid','')}` / `{r.get('wifi_password','')}`")
            with c2:
                mu=f"{FRONTEND_URL}?rest_id={r.get('restaurant_id')}"
                st.code(mu)
                reg=build_reg_link(r.get("restaurant_id",""))
                if reg: st.markdown(f"**🔗 Telegram:**"); st.code(reg)
            with c3:
                if st.button("🗑️ حذف",key=f"d_{r.get('restaurant_id')}"):
                    if del_r(r.get("restaurant_id")): st.success("تم!"); st.rerun()
                if st.button("🔄 Cache",key=f"c_{r.get('restaurant_id')}"):
                    try: requests.post(f"{ROUTER_URL}/cache/refresh",timeout=5); st.success("✅")
                    except: st.warning("API غير متاح")

# ══ MAIN ══════════════════════════════════════════════════
def main():
    if not auth(): return
    rs=fetch_all()
    with st.sidebar:
        st.markdown('<div style="color:#C9A84C;font-size:1.1rem;font-weight:900;text-align:center;padding:.3rem">👑 الإمبراطور</div>',unsafe_allow_html=True)
        st.markdown(f'<div style="text-align:center;color:#222;font-size:.7rem">{len(rs)} مطعم</div>',unsafe_allow_html=True)
        st.markdown("---")
        page=st.radio("",["🏠 Dashboard","🚀 إضافة مطعم","🖼️ صور الأكلات","🖨️ بطاقات PDF","⚙️ إدارة"],label_visibility="hidden")
        st.markdown("---")
        if st.button("🚪 خروج",use_container_width=True):
            st.session_state.ok=False; st.rerun()

    if   page=="🏠 Dashboard":      pg_dashboard(rs)
    elif page=="🚀 إضافة مطعم":    pg_add(rs)
    elif page=="🖼️ صور الأكلات":   page_images(rs)
    elif page=="🖨️ بطاقات PDF":    pg_pdf(rs)
    elif page=="⚙️ إدارة":          pg_manage(rs)

if __name__=="__main__":
    main()
