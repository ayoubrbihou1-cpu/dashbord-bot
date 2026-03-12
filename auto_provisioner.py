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
TG_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN","")
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")
FRONTEND_URL    = os.getenv("FRONTEND_URL","https://your-menu.netlify.app")
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
    "style","bg_type","socials","num_tables","logo_url","owner_email","status","created_at"
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
def setup_existing_sheet(sheet_id: str, name: str) -> tuple:
    url    = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    client = _gs()

    try:
        spread = client.open_by_key(sheet_id)
    except Exception as e:
        raise Exception(
            f"لا يمكن الوصول للـ Sheet!\n\n"
            f"تأكد أن صاحب المطعم شارك الـ Sheet مع:\n"
            f"📧 {SA_EMAIL}\n\n"
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

        # التحقق من الـ headers
        existing_headers = ws.row_values(1) if ws.row_count > 0 else []
        if not existing_headers:
            ws.append_row(MASTER_HEADERS)

        ws.append_row([
            data.get("restaurant_id",""),
            data.get("name",""),
            data.get("sheet_id",""),
            data.get("telegram_chat_id",""),
            data.get("wifi_ssid",""),
            data.get("wifi_password",""),
            data.get("primary_color","#0a0804"),
            data.get("accent_color","#C9A84C"),
            data.get("style","luxury"),
            data.get("num_tables",10),
            data.get("logo_url",""),
            data.get("owner_email",""),
            data.get("status","pending_telegram"),
            data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ])
        log.info(f"✅ محفوظ في Master_DB tab")
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
                       wifi_ssid: str, reg_link: str = "") -> bool:
    """
    إرسال إيميل ترحيب لصاحب المطعم
    يحتاج: GMAIL_USER + GMAIL_APP_PASSWORD في المتغيرات البيئية
    """
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

        tg_section = f"""
        <tr>
          <td style="padding:12px;background:#0d1a24;border-radius:8px;margin-top:12px">
            <b style="color:#29b6f6">📨 رابط Telegram:</b><br>
            <a href="{reg_link}" style="color:#29b6f6">{reg_link}</a><br>
            <small style="color:#888">اضغط مرة واحدة لربط الطلبات بـ Telegram</small>
          </td>
        </tr>
        """ if reg_link else ""

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
                {tg_section}
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

def send_welcome(chat_id, name, sheet_url, menu_url, wifi):
    return _tg(chat_id,
        f"🎉 *مرحباً في QR Menu!*\n🏪 *{name}*\n\n"
        f"📊 [قائمتك الآن]({sheet_url})\n"
        f"📱 رابط الزبائن: `{menu_url}`\n"
        f"📶 WiFi: `{wifi}`\n\n"
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
    bg_type="minimal", socials=None
):
    res = ProvisionResult()
    steps = []
    menu_url = f"{FRONTEND_URL}?rest_id={restaurant_id}"

    if not sheet_id.strip():
        res.error = (
            "❌ لم يتم إدخال Sheet ID!\n\n"
            "📋 الخطوات:\n"
            "1. صاحب المطعم يفتح sheets.google.com\n"
            "2. ينشئ Spreadsheet جديد\n"
            f"3. يشاركه مع: {SA_EMAIL} كـ Editor\n"
            "4. ينسخ الـ ID من الرابط\n"
            "5. يلصقه في حقل 'Sheet ID' أعلاه"
        )
        res.steps = steps
        return res

    # تهيئ الـ Sheet
    try:
        sid, url = setup_existing_sheet(sheet_id.strip(), name)
        res.sheet_id = sid
        res.sheet_url = url
        steps.append("✅ Sheet مهيأ — Tabs وHeaders جاهزة")
    except Exception as e:
        res.error = str(e)
        res.steps = steps
        return res

    # حفظ في Master_DB tab
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
        "owner_email":      owner_email,
        "status":           "active" if telegram_chat_id else "pending_telegram",
        "created_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    if not saved:
        res.error = "فشل حفظ في Master_DB"
        res.steps = steps
        return res
    steps.append("✅ محفوظ في Master_DB")

    # رابط Telegram
    reg = build_reg_link(restaurant_id)
    res.reg_link = reg
    if reg:
        steps.append("✅ رابط Telegram جاهز")
    else:
        steps.append("⚠️ تحقق من TELEGRAM_BOT_TOKEN")

    # إرسال رسالة Telegram
    if telegram_chat_id:
        ok = send_welcome(telegram_chat_id, name, url, menu_url, wifi_ssid)
        steps.append("✅ رسالة Telegram أُرسلت" if ok else "⚠️ Telegram فشل")

    # ✅ إرسال إيميل Gmail
    if owner_email:
        email_ok = send_welcome_email(
            owner_email, name, url, menu_url, wifi_ssid, reg
        )
        steps.append("✅ إيميل أُرسل" if email_ok else "⚠️ إيميل فشل (تحقق من GMAIL_USER/GMAIL_APP_PASSWORD)")

    res.success = True
    res.menu_url = menu_url
    res.steps = steps
    return res
