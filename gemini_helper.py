"""
🤖 gemini_helper.py — مساعد Gemini مع دوران تلقائي على 4 مفاتيح
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ إذا نفذت حصة المفتاح الأول → ينتقل للثاني تلقائياً
✅ يدعم النص والصور (base64)
✅ موديل: gemini-2.5-flash
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os, requests, logging
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("gemini_helper")

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL   = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# ── جمع كل المفاتيح المتاحة ──────────────────────────────
def _get_keys() -> list[str]:
    keys = []
    for var in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4"]:
        k = os.getenv(var, "").strip()
        if k:
            keys.append(k)
    return keys


def _call_gemini(key: str, parts: list, max_tokens: int = 1000, temperature: float = 0) -> str | None:
    """
    استدعاء Gemini بمفتاح محدد — يرجع النص أو None عند الفشل
    """
    import time
    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature
                }
            },
            timeout=60
        )

        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        # 429 = quota/rate limit — انتظر ثم جرب المفتاح التالي
        if resp.status_code == 429:
            log.warning(f"Key quota/limit — switching to next key. Status: {resp.status_code}")
            time.sleep(2)  # انتظر ثانيتين قبل المفتاح التالي
            return None

        # 503 = server overloaded
        if resp.status_code == 503:
            log.warning(f"Gemini overloaded — switching to next key.")
            time.sleep(3)
            return None

        # خطأ آخر
        log.error(f"Gemini error {resp.status_code}: {resp.text[:200]}")
        return None

    except Exception as e:
        log.warning(f"Gemini request failed: {e}")
        return None


def quota_error(resp) -> int:
    """يتحقق إذا كان الخطأ متعلق بالحصة"""
    try:
        body = resp.json()
        msg = str(body).lower()
        if "quota" in msg or "exceeded" in msg or "billing" in msg:
            return resp.status_code
    except:
        pass
    return -1


def gemini_text(prompt: str, max_tokens: int = 1000, temperature: float = 0) -> str:
    """
    استدعاء Gemini بنص فقط مع دوران تلقائي على المفاتيح
    
    مثال:
        result = gemini_text("ترجم طاجين دجاج للفرنسية")
    """
    keys = _get_keys()
    if not keys:
        raise RuntimeError("❌ لا يوجد GEMINI_API_KEY في المتغيرات البيئية")

    parts = [{"text": prompt}]

    import time
    for attempt in range(2):
        for i, key in enumerate(keys):
            log.info(f"Trying Gemini key {i+1}/{len(keys)} (attempt {attempt+1})")
            result = _call_gemini(key, parts, max_tokens, temperature)
            if result is not None:
                return result
        if attempt == 0:
            time.sleep(65)

    raise RuntimeError(f"❌ كل مفاتيح Gemini ({len(keys)}) نفذت حصتها — حاول بعد دقيقة")


def gemini_vision(prompt: str, image_b64: str, mime_type: str = "image/jpeg",
                  max_tokens: int = 2000, temperature: float = 0) -> str:
    """
    استدعاء Gemini بصورة + نص مع دوران تلقائي على المفاتيح
    يحاول مرتين على كل المفاتيح إذا كانت المشكلة Rate Limit مؤقتة
    """
    import time
    keys = _get_keys()
    if not keys:
        raise RuntimeError("❌ لا يوجد GEMINI_API_KEY في المتغيرات البيئية")

    parts = [
        {"text": prompt},
        {"inline_data": {"mime_type": mime_type, "data": image_b64}}
    ]

    # محاولتان — الثانية بعد انتظار 60 ثانية
    for attempt in range(2):
        for i, key in enumerate(keys):
            log.info(f"Trying Gemini vision key {i+1}/{len(keys)} (attempt {attempt+1})")
            result = _call_gemini(key, parts, max_tokens, temperature)
            if result is not None:
                return result

        if attempt == 0:
            log.warning("All keys exhausted — waiting 65 seconds for rate limit reset...")
            time.sleep(65)  # انتظر دقيقة لإعادة تعيين الحد

    raise RuntimeError(f"❌ كل مفاتيح Gemini ({len(keys)}) نفذت حصتها — حاول بعد دقيقة")


def gemini_available() -> tuple[bool, str]:
    """
    يتحقق من وجود مفاتيح متاحة
    يرجع: (True/False, رسالة)
    """
    keys = _get_keys()
    if not keys:
        return False, "لا يوجد GEMINI_API_KEY"
    return True, f"{len(keys)} مفتاح متاح"
