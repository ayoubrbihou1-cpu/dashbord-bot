"""
🏭 auto_provisioner.py — ينشئ كل شيء تلقائياً
🔧 FIX v2: Drive API + DRIVE_FOLDER_ID لحل مشكلة storage quota
"""
import gspread, json, os, logging, requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime
from dataclasses import dataclass, field

log = logging.getLogger("provisioner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID","")
TG_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN","")
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")
FRONTEND_URL    = os.getenv("FRONTEND_URL","https://your-menu.netlify.app")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID","")  # ← الجديد: Folder في Drive تاعك

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

def _sa_email():
    try:
        if SA_JSON_CONTENT: return json.loads(SA_JSON_CONTENT).get("client_email","")
        if os.path.exists(SA_JSON_PATH):
            with open(SA_JSON_PATH) as f: return json.load(f).get("client_email","")
    except: pass
    return ""

# ── Sheet Structure ───────────────────────────────────────
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
# 🔧 الدالة المُصلَحة — Drive API + Parent Folder
# ══════════════════════════════════════════════════════════
def create_restaurant_sheet(name: str) -> tuple[str, str]:
    """
    ينشئ Google Sheet للمطعم داخل DRIVE_FOLDER_ID
    هذا يحل مشكلة: APIError [403] Drive storage quota exceeded
    
    الشرط: الـ Folder مشارك مع Service Account كـ Editor
    """
    creds = _creds()

    if DRIVE_FOLDER_ID:
        # ✅ الطريقة الصحيحة: Drive API يخلق الملف في Folder تاعك
        drive = build('drive', 'v3', credentials=creds)
        file_meta = {
            'name':     f'🍽️ Menu — {name}',
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'parents':  [DRIVE_FOLDER_ID],
        }
        created = drive.files().create(
            body=file_meta,
            fields='id',
            supportsAllDrives=True
        ).execute()
        sid = created['id']
        log.info(f"✅ Created in folder {DRIVE_FOLDER_ID}: {sid}")
    else:
        # ⚠️ الطريقة القديمة — تسبب خطأ quota
        # ستظهر هذه الرسالة إذا نسي المستخدم إضافة DRIVE_FOLDER_ID
        raise Exception(
            "DRIVE_FOLDER_ID غير محدد في Secrets!\n"
            "أضفه في Streamlit Secrets → DRIVE_FOLDER_ID = \"your_folder_id\"\n"
            "شوف التعليمات أسفل."
        )

    url    = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
    client = _gs()
    spread = client.open_by_key(sid)

    # إعادة تسمية الورقة الأولى
    spread.sheet1.update_title(list(MENU_TABS.keys())[0])

    # إضافة باقي الـ tabs
    for tab in list(MENU_TABS.keys())[1:]:
        spread.add_worksheet(title=tab, rows=500, cols=15)

    # ملء البيانات + تنسيق
    colors = [
        {"red":.10,"green":.15,"blue":.10},{"red":.12,"green":.10,"blue":.18},
        {"red":.20,"green":.10,"blue":.10},{"red":.08,"green":.15,"blue":.22},
        {"red":.05,"green":.05,"blue":.20},
    ]
    for i,(tab,rows) in enumerate(MENU_TABS.items()):
        try:
            ws = spread.worksheet(tab)
            ws.update(rows,"A1")
            _fmt_header(spread, ws, colors[i])
            _freeze(spread, ws)
        except Exception as e:
            log.warning(f"Tab {tab}: {e}")

    log.info(f"✅ Sheet ready: {url}")
    return sid, url

def share_sheet(sid, email, role="writer", notify=False):
    try:
        _gs().open_by_key(sid).share(email, perm_type="user", role=role, notify=notify)
        return True
    except Exception as e: log.error(f"Share {email}: {e}"); return False

MASTER_HEADERS = ["restaurant_id","name","sheet_id","telegram_chat_id",
    "wifi_ssid","wifi_password","primary_color","accent_color",
    "style","num_tables","logo_url","owner_email","status","created_at"]

def save_to_master(data):
    try:
        client = _gs()
        ws     = client.open_by_key(MASTER_SHEET_ID).sheet1
        if not ws.get_all_values():
            ws.append_row(MASTER_HEADERS)
        ws.append_row([
            data.get("restaurant_id",""), data.get("name",""),
            data.get("sheet_id",""),      data.get("telegram_chat_id",""),
            data.get("wifi_ssid",""),     data.get("wifi_password",""),
            data.get("primary_color","#0a0804"), data.get("accent_color","#C9A84C"),
            data.get("style","luxury"),   data.get("num_tables",10),
            data.get("logo_url",""),      data.get("owner_email",""),
            data.get("status","pending_telegram"),
            data.get("created_at",datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ])
        return True
    except Exception as e: log.error(f"Master DB: {e}"); return False

def update_telegram_chat_id(restaurant_id, chat_id):
    try:
        client  = _gs()
        ws      = client.open_by_key(MASTER_SHEET_ID).sheet1
        headers = ws.row_values(1)
        cc = headers.index("telegram_chat_id") + 1
        sc = headers.index("status") + 1 if "status" in headers else None
        for i,r in enumerate(ws.get_all_records()):
            if str(r.get("restaurant_id","")) == str(restaurant_id):
                ws.update_cell(i+2, cc, chat_id)
                if sc: ws.update_cell(i+2, sc, "active")
                return True
        return False
    except Exception as e: log.error(f"Update chat_id: {e}"); return False

def _tg(chat_id, text):
    if not TG_TOKEN or not chat_id: return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":text,"parse_mode":"Markdown",
                  "disable_web_page_preview":False}, timeout=10)
        return r.status_code == 200
    except: return False

def build_reg_link(restaurant_id):
    if not TG_TOKEN: return ""
    try:
        r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=5)
        if r.status_code == 200:
            return f"https://t.me/{r.json()['result']['username']}?start=reg_{restaurant_id}"
    except: pass
    return ""

def send_welcome(chat_id, name, sheet_url, menu_url, wifi):
    return _tg(chat_id, f"🎉 *مرحباً في QR Menu!*\n🏪 *{name}*\n\n📊 [الشيت]({sheet_url})\n📱 `{menu_url}`\n📶 `{wifi}`\n\n⚡ ستصلك الطلبات هنا.")

def send_test(chat_id, name):
    return _tg(chat_id, f"✅ الاتصال ناجح!\n🏪 {name}")

def provision_restaurant(restaurant_id, name, wifi_ssid, wifi_password,
    style="luxury", primary_color="#0a0804", accent_color="#C9A84C",
    num_tables=10, logo_url="", owner_email="", telegram_chat_id=""):

    res=ProvisionResult(); steps=[]; menu_url=f"{FRONTEND_URL}?rest_id={restaurant_id}"

    try:
        sid,url=create_restaurant_sheet(name)
        res.sheet_id=sid; res.sheet_url=url
        steps.append("✅ Google Sheet مصاوب مع كل الأطواب")
    except Exception as e:
        res.error=f"فشل الشيت: {str(e)}"; res.steps=steps; return res

    sa=_sa_email()
    if sa: steps.append("✅ مشارك مع SA" if share_sheet(sid,sa) else "⚠️ فشلت مشاركة SA")
    if owner_email: steps.append(f"✅ مشارك مع {owner_email}" if share_sheet(sid,owner_email,notify=True) else f"⚠️ فشلت مشاركة {owner_email}")

    if not save_to_master({"restaurant_id":restaurant_id,"name":name,"sheet_id":sid,
            "telegram_chat_id":telegram_chat_id,"wifi_ssid":wifi_ssid,"wifi_password":wifi_password,
            "primary_color":primary_color,"accent_color":accent_color,"style":style,
            "num_tables":num_tables,"logo_url":logo_url,"owner_email":owner_email,
            "status":"active" if telegram_chat_id else "pending_telegram",
            "created_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}):
        res.error="فشل Master_DB"; res.steps=steps; return res
    steps.append("✅ محفوظ في Master_DB")

    reg=build_reg_link(restaurant_id); res.reg_link=reg
    steps.append("✅ رابط Telegram جاهز" if reg else "⚠️ تحقق من TG_TOKEN")

    if telegram_chat_id:
        steps.append("✅ رسالة ترحيب أُرسلت" if send_welcome(telegram_chat_id,name,url,menu_url,wifi_ssid) else "⚠️ Telegram فشل")

    res.success=True; res.menu_url=menu_url; res.steps=steps
    return res
