"""
🏭 auto_provisioner.py — الحل النهائي الصحيح
✅ صاحب المطعم ينشئ Sheet بنفسه → يشاركه مع SA → يلصق ID
   لا quota issues — كل مطعم عنده Sheet خاص في Drive تاعه
"""
import gspread, json, os, logging, requests
from google.oauth2.service_account import Credentials
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
SA_EMAIL        = "restaurant-bot@gen-lang-client-0967477901.iam.gserviceaccount.com"

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
# ✅ الدالة الجديدة — تهيئ Sheet موجود (أنشأه صاحب المطعم)
# ══════════════════════════════════════════════════════════
def setup_existing_sheet(sheet_id: str, name: str) -> tuple[str, str]:
    """
    تهيئ Sheet أنشأه صاحب المطعم مسبقاً وشاركه مع SA
    - تضيف الـ Tabs الصحيحة
    - تملأ Headers + بيانات أولية
    - تنسق الألوان
    """
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
    colors   = [
        {"red":.10,"green":.15,"blue":.10},{"red":.12,"green":.10,"blue":.18},
        {"red":.20,"green":.10,"blue":.10},{"red":.08,"green":.15,"blue":.22},
        {"red":.05,"green":.05,"blue":.20},
    ]

    tabs = list(MENU_TABS.keys())

    # إعادة تسمية الورقة الأولى إذا كانت "Sheet1" أو "Feuille 1"
    try:
        first = spread.sheet1
        if first.title in ("Sheet1","Feuille 1","Feuille1","sheet1"):
            first.update_title(tabs[0])
            existing[0] = tabs[0]
    except: pass

    for i,(tab,rows) in enumerate(MENU_TABS.items()):
        if tab not in existing:
            spread.add_worksheet(title=tab, rows=500, cols=15)
        try:
            ws = spread.worksheet(tab)
            ws.update(rows, "A1")
            _fmt_header(spread, ws, colors[i])
            _freeze(spread, ws)
            log.info(f"✅ Tab '{tab}' جاهز")
        except Exception as e:
            log.warning(f"Tab {tab}: {e}")

    log.info(f"✅ Sheet {sheet_id} جاهز: {url}")
    return sheet_id, url

# ── Master DB ─────────────────────────────────────────────
MASTER_HEADERS = ["restaurant_id","name","sheet_id","telegram_chat_id",
    "wifi_ssid","wifi_password","primary_color","accent_color",
    "style","num_tables","logo_url","owner_email","status","created_at"]

def save_to_master(data):
    try:
        ws = _gs().open_by_key(MASTER_SHEET_ID).sheet1
        if not ws.get_all_values(): ws.append_row(MASTER_HEADERS)
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
        ws      = _gs().open_by_key(MASTER_SHEET_ID).sheet1
        headers = ws.row_values(1)
        cc = headers.index("telegram_chat_id")+1
        sc = headers.index("status")+1 if "status" in headers else None
        for i,r in enumerate(ws.get_all_records()):
            if str(r.get("restaurant_id",""))==str(restaurant_id):
                ws.update_cell(i+2,cc,chat_id)
                if sc: ws.update_cell(i+2,sc,"active")
                return True
        return False
    except Exception as e: log.error(f"update_chat_id: {e}"); return False

# ── Telegram ──────────────────────────────────────────────
def _tg(chat_id, text):
    if not TG_TOKEN or not chat_id: return False
    try:
        r=requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":text,"parse_mode":"Markdown",
                  "disable_web_page_preview":False},timeout=10)
        return r.status_code==200
    except: return False

def build_reg_link(restaurant_id):
    if not TG_TOKEN: return ""
    try:
        r=requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe",timeout=5)
        if r.status_code==200:
            return f"https://t.me/{r.json()['result']['username']}?start=reg_{restaurant_id}"
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
def provision_restaurant(restaurant_id, name, wifi_ssid, wifi_password,
    sheet_id="",   # ← الجديد: ID الـ Sheet الذي أنشأه صاحب المطعم
    style="luxury", primary_color="#0a0804", accent_color="#C9A84C",
    num_tables=10, logo_url="", owner_email="", telegram_chat_id=""):

    res=ProvisionResult(); steps=[]
    menu_url=f"{FRONTEND_URL}?rest_id={restaurant_id}"

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

    # تهيئ الـ Sheet الموجود
    try:
        sid, url = setup_existing_sheet(sheet_id.strip(), name)
        res.sheet_id=sid; res.sheet_url=url
        steps.append("✅ Sheet مهيأ — Tabs وHeaders جاهزة")
    except Exception as e:
        res.error=str(e); res.steps=steps; return res

    # حفظ في Master_DB
    if not save_to_master({
        "restaurant_id":restaurant_id, "name":name, "sheet_id":sid,
        "telegram_chat_id":telegram_chat_id, "wifi_ssid":wifi_ssid,
        "wifi_password":wifi_password, "primary_color":primary_color,
        "accent_color":accent_color, "style":style, "num_tables":num_tables,
        "logo_url":logo_url, "owner_email":owner_email,
        "status":"active" if telegram_chat_id else "pending_telegram",
        "created_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }):
        res.error="فشل Master_DB"; res.steps=steps; return res
    steps.append("✅ محفوظ في Master_DB")

    reg=build_reg_link(restaurant_id); res.reg_link=reg
    steps.append("✅ رابط Telegram جاهز" if reg else "⚠️ تحقق من TG_TOKEN")

    if telegram_chat_id:
        ok=send_welcome(telegram_chat_id,name,url,menu_url,wifi_ssid)
        steps.append("✅ رسالة ترحيب أُرسلت" if ok else "⚠️ Telegram فشل")

    res.success=True; res.menu_url=menu_url; res.steps=steps
    return res
