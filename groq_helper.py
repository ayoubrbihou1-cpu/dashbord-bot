"""
⚡ groq_helper.py — مساعد Groq للترجمة مع دوران تلقائي على 6 مفاتيح
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ أسرع من Gemini للترجمة النصية
✅ مجاني تماماً
✅ 6 مفاتيح = لن تنفذ أبداً
✅ موديل: llama-3.3-70b-versatile
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os, requests, logging, time, json
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("groq_helper")

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

# ── جمع كل المفاتيح ──────────────────────────────────────────────
def _get_keys() -> list:
    keys = []
    for var in [
        "GROQ_API_KEY",   "GROQ_API_KEY_2", "GROQ_API_KEY_3",
        "GROQ_API_KEY_4", "GROQ_API_KEY_5", "GROQ_API_KEY_6"
    ]:
        k = os.getenv(var, "").strip()
        if k:
            keys.append(k)
    return keys


def _call_groq(key: str, messages: list, max_tokens: int = 2000, temperature: float = 0) -> str | None:
    """استدعاء Groq بمفتاح محدد"""
    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            },
            timeout=30
        )

        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()

        if resp.status_code == 429:
            log.warning(f"Groq rate limit — switching to next key")
            time.sleep(1)
            return None

        if resp.status_code == 503:
            log.warning(f"Groq overloaded — switching to next key")
            time.sleep(2)
            return None

        log.error(f"Groq error {resp.status_code}: {resp.text[:200]}")
        return None

    except Exception as e:
        log.warning(f"Groq request failed: {e}")
        return None


def groq_text(prompt: str, system: str = "", max_tokens: int = 2000, temperature: float = 0) -> str:
    """
    استدعاء Groq مع دوران تلقائي على المفاتيح
    """
    keys = _get_keys()
    if not keys:
        raise RuntimeError("❌ لا يوجد GROQ_API_KEY في المتغيرات البيئية")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(2):
        for i, key in enumerate(keys):
            log.info(f"Trying Groq key {i+1}/{len(keys)} (attempt {attempt+1})")
            result = _call_groq(key, messages, max_tokens, temperature)
            if result is not None:
                return result
        if attempt == 0:
            log.warning("All Groq keys exhausted — waiting 30 seconds...")
            time.sleep(30)

    raise RuntimeError(f"❌ كل مفاتيح Groq ({len(keys)}) فشلت — حاول لاحقاً")


def groq_available() -> tuple:
    """يتحقق من وجود مفاتيح Groq"""
    keys = _get_keys()
    if not keys:
        return False, "لا يوجد GROQ_API_KEY"
    return True, f"{len(keys)} مفتاح متاح"


# ══════════════════════════════════════════════════════════════════
# 🌍 دوال الترجمة الجاهزة
# ══════════════════════════════════════════════════════════════════

def translate_batch_groq(names: list) -> list:
    """
    يترجم قائمة أسماء أكلات للغات الثلاث دفعة واحدة
    يرجع قائمة من (name_ar, name_fr, name_en)

    مثال:
        results = translate_batch_groq(["TAJINE POULET", "Fruit Salad"])
        # [("طاجين دجاج", "Tajine Poulet", "Chicken Tagine"), ...]
    """
    if not names:
        return []

    numbered = "\n".join(f"{i+1}. {n}" for i, n in enumerate(names))

    system = (
        "You are a Moroccan restaurant menu translator. "
        "You translate dish names to Arabic, French, and English. "
        "Reply ONLY with a valid JSON array. No explanation, no markdown."
    )

    prompt = (
        f"Translate each dish name to all 3 languages.\n"
        f"Reply ONLY with this JSON format (array of objects):\n"
        f'[{{"ar":"Arabic name","fr":"French name","en":"English name"}}]\n\n'
        f"Dish names:\n{numbered}"
    )

    try:
        txt = groq_text(prompt, system=system, max_tokens=4000, temperature=0)

        # تنظيف JSON
        txt = txt.strip()
        if "```json" in txt:
            txt = txt.split("```json")[1].split("```")[0].strip()
        elif "```" in txt:
            txt = txt.split("```")[1].split("```")[0].strip()
        if not txt.startswith("["):
            start = txt.find("[")
            if start != -1:
                txt = txt[start:]
        if not txt.endswith("]"):
            end = txt.rfind("]")
            if end != -1:
                txt = txt[:end+1]

        parsed = json.loads(txt)

        result = []
        for i, item in enumerate(parsed[:len(names)]):
            orig = names[i] if i < len(names) else ""
            ar = item.get("ar", "").strip()
            fr = item.get("fr", "").strip()
            en = item.get("en", "").strip()
            # إذا كان الاسم الأصلي بلغة معينة نستخدمه مباشرة
            orig_lower = orig.lower()
            has_arabic = any('\u0600' <= c <= '\u06ff' for c in orig)
            if has_arabic and not ar:
                ar = orig
            elif not has_arabic and any(w in orig_lower for w in ["tajine","couscous","poulet","salade","soupe"]):
                if not fr:
                    fr = orig
            result.append((ar, fr, en))

        # تكملة إذا كانت النتائج أقل من المدخلات
        while len(result) < len(names):
            i = len(result)
            orig = names[i]
            has_ar = any('\u0600' <= c <= '\u06ff' for c in orig)
            if has_ar:
                result.append((orig, "", ""))
            else:
                result.append(("", orig, orig))

        return result

    except (json.JSONDecodeError, Exception) as e:
        log.error(f"translate_batch_groq failed: {e}")
        # fallback بسيط
        result = []
        for name in names:
            has_ar = any('\u0600' <= c <= '\u06ff' for c in name)
            if has_ar:
                result.append((name, "", ""))
            else:
                result.append(("", name, name))
        return result


def translate_single_groq(name: str) -> tuple:
    """
    يترجم اسم أكلة واحدة للغات الثلاث
    يرجع: (name_ar, name_fr, name_en)
    """
    results = translate_batch_groq([name])
    return results[0] if results else ("", "", "")
