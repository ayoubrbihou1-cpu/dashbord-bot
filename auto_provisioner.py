import json
"""
🏭 auto_provisioner.py — الإصدار المُصلح
✅ إصلاح: حفظ Master DB في tab مستقل "Master_DB" وليس sheet1
✅ إصلاح: دعم إرسال إيميل Gmail عبر SMTP
"""
import gspread, json, os, logging, requests, smtplib
from google.oauth2.service_account import Credentials
from datetime import datetime
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger("provisioner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID","")
SUPABASE_URL    = os.getenv("SUPABASE_URL","")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY","")
TG_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN","")
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")
FRONTEND_URL    = os.getenv("FRONTEND_URL","https://your-menu.netlify.app")
KITCHEN_URL     = os.getenv("KITCHEN_URL","https://your-kitchen.netlify.app")
ROUTER_BASE_URL = os.getenv("ROUTER_BASE_URL","https://restaurant-qr-saas.onrender.com")
SA_EMAIL        = "restaurant-bot@gen-lang-client-0967477901.iam.gserviceaccount.com"

# Gmail للإرسال (اختياري)
GMAIL_USER      = os.getenv("GMAIL_USER","")
GMAIL_PASSWORD  = os.getenv("GMAIL_APP_PASSWORD","")

@dataclass
class ProvisionResult:
    success:   bool = False
    sheet_id:  str  = ""
    sheet_url: str  = ""
    menu_url:  str  = ""
    reg_link:  str  = ""
    error:     str  = ""
    steps:     list = field(default_factory=list)

def _creds():
    if SA_JSON_CONTENT:
        return Credentials.from_service_account_info(json.loads(SA_JSON_CONTENT), scopes=SCOPES)
    return Credentials.from_service_account_file(SA_JSON_PATH, scopes=SCOPES)

def _gs(): return gspread.authorize(_creds())

# ── Headers لكل Tab ───────────────────────────────────────
MENU_TABS = {
    "الأطباق الرئيسية": [
        ["name","name_fr","name_en","price","description","available","image_url","image_credit"],
        ["طاجين دجاج","Tajine Poulet","Chicken Tagine","85","تقليدي بالزيتون","TRUE","",""],
        ["كسكس مغربي","Couscous Marocain","Moroccan Couscous","70","بالخضار والمرق","TRUE","",""],
    ],
    "المقبلات": [
        ["name","name_fr","name_en","price","description","available","image_url","image_credit"],
        ["سلطة مغربية","Salade Marocaine","Moroccan Salad","30","طازج","TRUE","",""],
    ],
    "الحلويات": [
        ["name","name_fr","name_en","price","description","available","image_url","image_credit"],
        ["بسطيلة حلوة","Pastilla Sucrée","Sweet Pastilla","35","بالمكسرات","TRUE","",""],
    ],
    "المشروبات": [
        ["name","name_fr","name_en","price","description","available","image_url","image_credit"],
        ["أتاي بالنعناع","Thé à la Menthe","Mint Tea","15","تقليدي","TRUE","",""],
        ["عصير برتقال","Jus d'Orange","Orange Juice","20","طازج","TRUE","",""],
    ],
    "Orders": [
        ["order_id","table_number","customer_name","customer_phone",
         "items","total_price","status","notes","created_at","lang"],
    ],
}

# ✅ headers المطاعم — tab منفصل
MASTER_HEADERS = [
    "restaurant_id","name","sheet_id","telegram_chat_id",
    "wifi_ssid","wifi_password","primary_color","accent_color",
    "style","bg_type","socials","num_tables","logo_url",
    "kitchen_password","owner_email","status","created_at",
    # ✅ حقول جديدة للتوصيل والمجموعات
    "delivery_active",    # true/false — تفعيل خيار التوصيل
    "boss_chat_id",       # chat_id مدير المطعم (للأرباح والإشعارات)
    "waiters_chat_id",    # chat_id مجموعة النوادل (dine_in جاهز)
    "delivery_chat_id",   # chat_id مجموعة التوصيل
    "sa_json",            # Service Account JSON الخاص بهذا المطعم
]

def _fmt_header(spread, ws, color):
    try:
        spread.batch_update({"requests":[{"repeatCell":{
            "range":{"sheetId":ws.id,"startRowIndex":0,"endRowIndex":1},
            "cell":{"userEnteredFormat":{
                "backgroundColor":color,
                "textFormat":{"bold":True,"foregroundColor":{"red":1,"green":.85,"blue":0}}
            }},"fields":"userEnteredFormat(backgroundColor,textFormat)"
        }}]})
    except: pass

def _freeze(spread, ws):
    try:
        spread.batch_update({"requests":[{"updateSheetProperties":{
            "properties":{"sheetId":ws.id,"gridProperties":{"frozenRowCount":1}},
            "fields":"gridProperties.frozenRowCount"
        }}]})
    except: pass

# ══════════════════════════════════════════════════════════
# ✅ تهيئ Sheet موجود
# ══════════════════════════════════════════════════════════
def setup_existing_sheet(sheet_id: str, name: str, sa_json: str = "") -> tuple:
    url    = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    
    # ✅ استخدم SA الخاص بالمطعم إذا وُجد، وإلا SA الرئيسي
    if sa_json and sa_json.strip().startswith("{"):
        try:
            import json as _j
            from google.oauth2.service_account import Credentials as _Cr
            _creds_r = _Cr.from_service_account_info(
                _j.loads(sa_json),
                scopes=["https://www.googleapis.com/auth/spreadsheets",
                        "https://www.googleapis.com/auth/drive"]
            )
            client = gspread.authorize(_creds_r)
            sa_email_used = _j.loads(sa_json).get("client_email", SA_EMAIL)
        except Exception as _e:
            log.warning(f"SA JSON خاطئ: {_e} — نستخدم SA الرئيسي")
            client = _gs()
            sa_email_used = SA_EMAIL
    else:
        client = _gs()
        sa_email_used = SA_EMAIL

    try:
        spread = client.open_by_key(sheet_id)
    except Exception as e:
        raise Exception(
            f"لا يمكن الوصول للـ Sheet!\n\n"
            f"تأكد أن صاحب المطعم شارك الـ Sheet مع:\n"
            f"📧 {sa_email_used}\n\n"
            f"كـ Editor ثم حاول مجدداً.\n\nالخطأ: {e}"
        )

    existing = [ws.title for ws in spread.worksheets()]
    tab_colors = [
        {"red":.10,"green":.15,"blue":.10},
        {"red":.12,"green":.10,"blue":.18},
        {"red":.20,"green":.10,"blue":.10},
        {"red":.08,"green":.15,"blue":.22},
        {"red":.05,"green":.05,"blue":.20},
    ]

    tabs = list(MENU_TABS.keys())

    # إعادة تسمية الورقة الأولى إذا كانت Sheet1
    try:
        first = spread.sheet1
        if first.title in ("Sheet1","Feuille 1","Feuille1","sheet1"):
            first.update_title(tabs[0])
            existing[0] = tabs[0]
    except: pass

    for i, (tab, rows) in enumerate(MENU_TABS.items()):
        if tab not in existing:
            spread.add_worksheet(title=tab, rows=500, cols=15)
        try:
            ws = spread.worksheet(tab)
            ws.update(rows, "A1")
            _fmt_header(spread, ws, tab_colors[i])
            _freeze(spread, ws)
            log.info(f"✅ Tab '{tab}' جاهز")
        except Exception as e:
            log.warning(f"Tab {tab}: {e}")

    log.info(f"✅ Sheet {sheet_id} جاهز: {url}")
    return sheet_id, url


# ══════════════════════════════════════════════════════════
# ✅ Master DB — tab مستقل في نفس الـ MASTER_SHEET_ID
# ══════════════════════════════════════════════════════════
def _get_or_create_master_tab(client) -> gspread.Worksheet:
    """
    ✅ يحصل على tab 'Master_DB' أو ينشئه
    هذا يحل مشكلة خلط بيانات المطاعم مع بيانات المينيو
    """
    spread = client.open_by_key(MASTER_SHEET_ID)
    tab_name = "Master_DB"

    try:
        ws = spread.worksheet(tab_name)
        return ws
    except gspread.WorksheetNotFound:
        ws = spread.add_worksheet(title=tab_name, rows=500, cols=20)
        ws.append_row(MASTER_HEADERS)
        # تنسيق header
        try:
            spread.batch_update({"requests":[{"repeatCell":{
                "range":{"sheetId":ws.id,"startRowIndex":0,"endRowIndex":1},
                "cell":{"userEnteredFormat":{
                    "backgroundColor":{"red":.05,"green":.1,"blue":.2},
                    "textFormat":{"bold":True,"foregroundColor":{"red":0.8,"green":0.65,"blue":0.2}}
                }},"fields":"userEnteredFormat(backgroundColor,textFormat)"
            }}]})
        except: pass
        log.info(f"✅ Tab 'Master_DB' أُنشئ")
        return ws


def save_to_master(data):
    try:
        client = _gs()
        ws = _get_or_create_master_tab(client)

        existing_headers = ws.row_values(1) if ws.row_count > 0 else []
        if not existing_headers:
            ws.append_row(MASTER_HEADERS)
            existing_headers = MASTER_HEADERS
        else:
            # ✅ أضف أي عمود ناقص في الـ headers تلقائياً
            missing = [h for h in MASTER_HEADERS if h not in existing_headers]
            if missing:
                for h in missing:
                    existing_headers.append(h)
                # حدّث صف الـ headers في الشيت
                ws.update("A1", [existing_headers])
                log.info(f"✅ أضفت أعمدة جديدة: {missing}")

        # كتابة الصف بنفس ترتيب الـ headers
        row = [str(data.get(h, "")) for h in existing_headers]
        ws.append_row(row)
        log.info(f"✅ محفوظ في Master_DB: {data.get('name','')}")
        return True
    except Exception as e:
        log.error(f"Master DB: {e}")
        return False


def update_telegram_chat_id(restaurant_id, chat_id):
    try:
        client = _gs()
        ws = _get_or_create_master_tab(client)
        headers = ws.row_values(1)
        if "restaurant_id" not in headers:
            return False
        rid_col = headers.index("restaurant_id") + 1
        cc      = headers.index("telegram_chat_id") + 1 if "telegram_chat_id" in headers else None
        sc      = headers.index("status") + 1 if "status" in headers else None

        all_values = ws.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) >= rid_col and str(row[rid_col-1]) == str(restaurant_id):
                if cc: ws.update_cell(i, cc, chat_id)
                if sc: ws.update_cell(i, sc, "active")
                return True
        return False
    except Exception as e:
        log.error(f"update_chat_id: {e}")
        return False


# ══════════════════════════════════════════════════════════
# ✅ إرسال إيميل Gmail
# ══════════════════════════════════════════════════════════
def send_welcome_email(to_email: str, restaurant_name: str,
                       sheet_url: str, menu_url: str,
                       wifi_ssid: str, reg_link: str = "",
                       kitchen_url: str = "", kitchen_password: str = "",
                       group_links: dict = None) -> bool:
    if not GMAIL_USER or not GMAIL_PASSWORD:
        log.warning("⚠️ GMAIL_USER أو GMAIL_APP_PASSWORD غير محدد — تخطي الإيميل")
        return False
    if not to_email:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎉 مرحباً في QR Menu — {restaurant_name}"
        msg["From"]    = GMAIL_USER
        msg["To"]      = to_email

        tg_section = ""  # محذوف

        # ✅ قسم روابط المجموعات (boss / waiters / delivery)
        gl = group_links or {}
        groups_section = f"""
        <tr>
          <td colspan="2" style="padding:12px;background:#0a0a1a;border-radius:8px;margin-top:8px">
            <b style="color:#7986cb">📲 روابط ربط مجموعات Telegram</b><br><br>
            <table width="100%">
              <tr>
                <td style="padding:6px 0">
                  <b style="color:#ffd54f">👑 المدير (أنت):</b><br>
                  <a href="{gl.get('boss','#')}" style="color:#29b6f6;font-size:.85rem">{gl.get('boss','—')}</a><br>
                  <small style="color:#666">اضغط لربط حسابك وتلقي إشعارات الأرباح</small>
                </td>
              </tr>
              <tr>
                <td style="padding:6px 0">
                  <b style="color:#a5d6a7">🍽️ مجموعة النوادل:</b><br>
                  <a href="{gl.get('waiters','#')}" style="color:#29b6f6;font-size:.85rem">{gl.get('waiters','—')}</a><br>
                  <small style="color:#666">أضف هذا الرابط في مجموعة النوادل على Telegram</small>
                </td>
              </tr>
              <tr>
                <td style="padding:6px 0">
                  <b style="color:#80deea">🛵 مجموعة التوصيل:</b><br>
                  <a href="{gl.get('delivery','#')}" style="color:#29b6f6;font-size:.85rem">{gl.get('delivery','—')}</a><br>
                  <small style="color:#666">أضف هذا الرابط في مجموعة عمال التوصيل</small>
                </td>
              </tr>
            </table>
          </td>
        </tr>""" if gl else ""

        kitchen_section = f"""
        <tr>
          <td colspan="2" style="padding:12px;background:#1a0d00;border-radius:8px;margin-top:8px">
            <b style="color:#ff9800">🍳 شاشة الكوزينة:</b><br>
            <a href="{kitchen_url}" style="color:#ff9800;font-size:.85rem">{kitchen_url}</a><br>
            <b style="color:#ff9800">🔑 كلمة مرور الكوزينة:</b>
            <code style="background:#2a1500;color:#ffcc80;padding:2px 8px;border-radius:4px;font-size:1rem">
              {kitchen_password}
            </code><br>
            <small style="color:#888">📌 احفظها على التابليت في الكوزينة</small>
          </td>
        </tr>""" if kitchen_url else ""

        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#0a0a0a;color:#eee;padding:20px">
          <div style="max-width:600px;margin:0 auto;background:#111;border-radius:16px;
                      border:1px solid #C9A84C44;overflow:hidden">
            <div style="background:linear-gradient(135deg,#0a0804,#1a1200);
                        padding:24px;text-align:center;border-bottom:1px solid #C9A84C44">
              <h1 style="color:#C9A84C;margin:0;font-size:1.6rem">🎉 مرحباً في QR Menu!</h1>
              <p style="color:#888;margin:.5rem 0 0">مطعمك جاهز الآن</p>
            </div>
            <div style="padding:24px">
              <table width="100%" cellpadding="8">
                <tr>
                  <td style="color:#C9A84C;font-weight:bold">🏪 المطعم:</td>
                  <td>{restaurant_name}</td>
                </tr>
                <tr>
                  <td style="color:#C9A84C;font-weight:bold">📱 رابط الزبائن:</td>
                  <td><a href="{menu_url}" style="color:#C9A84C">{menu_url}</a></td>
                </tr>
                <tr>
                  <td style="color:#C9A84C;font-weight:bold">📊 Google Sheet:</td>
                  <td><a href="{sheet_url}" style="color:#888">افتح الشيت</a></td>
                </tr>
                <tr>
                  <td style="color:#C9A84C;font-weight:bold">📶 WiFi:</td>
                  <td>{wifi_ssid}</td>
                </tr>
                {kitchen_section}
                {groups_section}
              </table>
              <hr style="border-color:#222;margin:16px 0">
              <p style="color:#555;font-size:.85rem;text-align:center">
                عدّل الأسعار في الشيت — تظهر فوراً للزبائن ✨
              </p>
            </div>
          </div>
        </body></html>
        """

        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        log.info(f"✅ إيميل أُرسل إلى: {to_email}")
        return True
    except Exception as e:
        log.error(f"Gmail: {e}")
        return False


# ── Telegram ──────────────────────────────────────────────
def _tg(chat_id, text):
    if not TG_TOKEN or not chat_id: return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text,
                  "parse_mode": "Markdown", "disable_web_page_preview": False},
            timeout=10
        )
        return r.status_code == 200
    except: return False

def build_reg_link(restaurant_id):
    if not TG_TOKEN: return ""
    try:
        r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=5)
        if r.status_code == 200:
            username = r.json()["result"]["username"]
            return f"https://t.me/{username}?start=reg_{restaurant_id}"
    except: pass
    return ""

def build_group_links(restaurant_id):
    """
    يبني روابط Deep Linking لـ boss / waiters / delivery
    ✅ إصلاح: boss يستخدم ?start= (خاص) — waiters/delivery يستخدمان ?startgroup= (مجموعة)
    كلاهما يُسجّل chat_id في Google Sheet عبر webhook /webhook/telegram
    """
    if not TG_TOKEN: return {}
    try:
        r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=5)
        if r.status_code == 200:
            username = r.json()["result"]["username"]
            return {
                "boss":     f"https://t.me/{username}?start=boss_{restaurant_id}",
                "waiters":  f"https://t.me/{username}?startgroup=waiters_{restaurant_id}",
                "delivery": f"https://t.me/{username}?startgroup=delivery_{restaurant_id}",
            }
    except: pass
    return {}

def send_welcome(chat_id, name, sheet_url, menu_url, wifi,
                 kitchen_url="", kitchen_password="", group_links=None):
    kitchen_part = (
        f"\n━━━━━━━━━━━━\n"
        f"🍳 *شاشة الكوزينة:*\n`{kitchen_url}`\n"
        f"🔑 *كلمة مرور الكوزينة:* `{kitchen_password}`\n"
        f"📌 احفظها على التابليت"
    ) if kitchen_url else ""

    gl = group_links or {}
    groups_part = ""
    if gl:
        groups_part = (
            f"\n━━━━━━━━━━━━\n"
            f"📲 *روابط ربط المجموعات:*\n"
            f"👑 المدير: {gl.get('boss','')}\n"
            f"🍽️ النوادل: {gl.get('waiters','')}\n"
            f"🛵 التوصيل: {gl.get('delivery','')}"
        )
    return _tg(chat_id,
        f"🎉 *مرحباً في QR Menu!*\n🏪 *{name}*\n\n"
        f"📊 [قائمتك الآن]({sheet_url})\n"
        f"📱 رابط الزبائن: `{menu_url}`\n"
        f"📶 WiFi: `{wifi}`\n"
        f"{kitchen_part}"
        f"{groups_part}\n\n"
        f"✏️ عدّل الأسعار مباشرة في الشيت — تظهر فوراً للزبائن!\n"
        f"⚡ الطلبات ستصلك هنا.")

def send_test(chat_id, name):
    return _tg(chat_id, f"✅ الاتصال ناجح!\n🏪 {name}")


# ── Main ──────────────────────────────────────────────────
def provision_restaurant(
    restaurant_id, name, wifi_ssid, wifi_password,
    sheet_id="",
    style="luxury", primary_color="#0a0804", accent_color="#C9A84C",
    num_tables=10, logo_url="", owner_email="", telegram_chat_id="",
    bg_type="minimal", socials=None, kitchen_password="",
    delivery_active=False, sa_json="", slug=""
):
    res = ProvisionResult()
    steps = []
    # ✅ استخدم الرابط النظيف إذا وُجد slug
    _slug_clean = slug.strip().lower().replace(" ","-") if slug else ""
    menu_url = f"{FRONTEND_URL}/{_slug_clean}" if _slug_clean else f"{FRONTEND_URL}?rest_id={restaurant_id}"

    if not sheet_id.strip():
        # حدد email الـ SA الصحيح للعرض
        _sa_email_show = SA_EMAIL
        if sa_json and sa_json.strip().startswith("{"):
            try:
                import json as _jj
                _sa_email_show = _jj.loads(sa_json).get("client_email", SA_EMAIL)
            except: pass
        res.error = (
            "❌ لم يتم إدخال Sheet ID!\n\n"
            "📋 الخطوات:\n"
            "1. صاحب المطعم يفتح sheets.google.com\n"
            "2. ينشئ Spreadsheet جديد\n"
            f"3. يشاركه مع: {_sa_email_show} كـ Editor\n"
            "4. ينسخ الـ ID من الرابط\n"
            "5. يلصقه في حقل 'Sheet ID' أعلاه"
        )
        res.steps = steps
        return res

    # تهيئ الـ Sheet — باستخدام SA الخاص بالمطعم إذا وُجد
    try:
        sid, url = setup_existing_sheet(sheet_id.strip(), name, sa_json=sa_json)
        res.sheet_id = sid
        res.sheet_url = url
        steps.append("✅ Sheet مهيأ — Tabs وHeaders جاهزة")
    except Exception as e:
        res.error = str(e)
        res.steps = steps
        return res

    # ✅ حفظ في Supabase أولاً — Sheets كـ fallback
    _sb_url = SUPABASE_URL
    _sb_key = SUPABASE_KEY
    _saved_supabase = False

    if _sb_url and _sb_key:
        try:
            _rq = requests  # already imported at top
            _rest_payload = {
                "restaurant_id":   restaurant_id,
                "name":            name,
                "agency_id":       "SUPER",
                "sheet_id":        sid,
                "slug":            _slug_clean,
                "telegram_chat_id":telegram_chat_id or "",
                "wifi_ssid":       wifi_ssid or "",
                "wifi_password":   wifi_password or "",
                "primary_color":   primary_color or "#0a0804",
                "accent_color":    accent_color or "#C9A84C",
                "style":           style or "luxury",
                "bg_type":         bg_type or "minimal",
                "num_tables":      int(num_tables or 10),
                "logo_url":        logo_url or "",
                "owner_email":     owner_email or "",
                "kitchen_password":kitchen_password or "",
                "delivery_active": bool(delivery_active),
                "socials":         json.dumps(socials or {}, ensure_ascii=False),
                "sa_json":         sa_json.strip() if sa_json else "",
                "status":          "active" if telegram_chat_id else "pending_telegram",
                "plan":            "basic",
            }
            _h = {
                "apikey": _sb_key,
                "Authorization": f"Bearer {_sb_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=representation"
            }
            _r = _rq.post(
                f"{_sb_url}/rest/v1/restaurants?on_conflict=restaurant_id",
                headers=_h, json=_rest_payload, timeout=10
            )
            if _r.status_code in (200, 201):
                _saved_supabase = True
                steps.append("✅ محفوظ في Supabase")
                log.info(f"✅ Supabase: {restaurant_id}")
            else:
                steps.append(f"⚠️ Supabase {_r.status_code} — سيُحفظ في Sheets")
        except Exception as _sbe:
            steps.append(f"⚠️ Supabase error: {str(_sbe)[:40]} — سيُحفظ في Sheets")

    # حفظ في Master_DB tab (دائماً كـ backup)
    saved = save_to_master({
        "restaurant_id":    restaurant_id,
        "name":             name,
        "sheet_id":         sid,
        "telegram_chat_id": telegram_chat_id,
        "wifi_ssid":        wifi_ssid,
        "wifi_password":    wifi_password,
        "primary_color":    primary_color,
        "accent_color":     accent_color,
        "style":            style,
        "bg_type":          bg_type,
        "socials":          json.dumps(socials or {}, ensure_ascii=False),
        "num_tables":       num_tables,
        "logo_url":         logo_url,
        "kitchen_password": kitchen_password,
        "owner_email":      owner_email,
        "status":           "active" if telegram_chat_id else "pending_telegram",
        "created_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "delivery_active":  "true" if delivery_active else "false",
        "boss_chat_id":     "",
        "waiters_chat_id":  "",
        "delivery_chat_id": "",
        "sa_json":          sa_json.strip() if sa_json else "",
        "slug":             _slug_clean,
    })
    if not saved and not _saved_supabase:
        res.error = "فشل الحفظ في Supabase وGoogle Sheets"
        res.steps = steps
        return res
    if saved:
        steps.append("✅ محفوظ في Master_DB (backup)")

    # رابط Telegram
    reg = build_reg_link(restaurant_id)
    res.reg_link = reg
    if reg:
        steps.append("✅ رابط Telegram جاهز")
    else:
        steps.append("⚠️ تحقق من TELEGRAM_BOT_TOKEN")

    # رابط الكوزينة
    kitchen_url = f"{KITCHEN_URL}?api={ROUTER_BASE_URL}&rid={restaurant_id}&name={requests.utils.quote(name)}" if KITCHEN_URL else ""

    # ✅ إصلاح: بناء روابط المجموعات قبل send_welcome (كانت بعده — خطأ كبير!)
    gl = build_group_links(restaurant_id)
    if gl:
        steps.append("✅ روابط المجموعات جاهزة (Boss / نوادل / توصيل)")
    else:
        steps.append("⚠️ روابط المجموعات: تحقق من TELEGRAM_BOT_TOKEN")

    # إرسال رسالة Telegram — الآن gl معرّف
    if telegram_chat_id:
        ok = send_welcome(telegram_chat_id, name, url, menu_url, wifi_ssid,
                          kitchen_url=kitchen_url, kitchen_password=kitchen_password,
                          group_links=gl)
        steps.append("✅ رسالة Telegram أُرسلت" if ok else "⚠️ Telegram فشل")

    # ✅ إرسال إيميل Gmail
    if owner_email:
        email_ok = send_welcome_email(
            owner_email, name, url, menu_url, wifi_ssid, reg,
            kitchen_url=kitchen_url, kitchen_password=kitchen_password,
            group_links=gl
        )
        steps.append("✅ إيميل أُرسل" if email_ok else "⚠️ إيميل فشل (تحقق من GMAIL_USER/GMAIL_APP_PASSWORD)")

    res.success = True
    res.menu_url = menu_url
    res.steps = steps
    return res
