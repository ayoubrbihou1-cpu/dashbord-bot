"""
🖼️ image_engine.py — محرك الصور الموحد
3 طرق في موديول واحد:
  1. 🆓 Unsplash API  — مجاني
  2. 🤖 DALL-E 3      — AI توليدي
  3. 📸 رفع يدوي     — صورك الخاصة
"""

import os, json, time, logging, requests, base64
from io import BytesIO
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("img_engine")

UNSPLASH_KEY  = os.getenv("UNSPLASH_ACCESS_KEY", "")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
PEXELS_KEY    = os.getenv("PEXELS_API_KEY", "")
PIXABAY_KEY   = os.getenv("PIXABAY_API_KEY", "")

# ─── cache لتفادي طلبات مكررة ───────────────────────────
_cache: dict[str, str] = {}

# ══════════════════════════════════════════════════════════
# 🔧 SHARED UTILS
# ══════════════════════════════════════════════════════════

def get_food_emoji(name: str, category: str = "") -> str:
    n = (name + " " + category).lower()
    mapping = [
        (["طاجين","tajine","tagine"],               "🫕"),
        (["كسكس","couscous"],                        "🥘"),
        (["حريرة","harira","soupe","شوربة","soup"],  "🍲"),
        (["سلطة","salade","salad"],                  "🥗"),
        (["سمك","fish","poisson","thon"],             "🐟"),
        (["دجاج","poulet","chicken"],                 "🍗"),
        (["لحم","viande","beef","kefta"],             "🥩"),
        (["مشوي","grillé","bbq","brochette"],         "🍢"),
        (["بيتزا","pizza"],                           "🍕"),
        (["برغر","burger"],                           "🍔"),
        (["باستا","pasta","spaghetti"],               "🍝"),
        (["ساندويش","sandwich"],                      "🥪"),
        (["بيض","egg","oeuf","عجة","omelette"],       "🍳"),
        (["بريوات","briouats","pastilla","بسطيلة"],   "🥟"),
        (["حلوى","dessert","gâteau","كيك","cake"],    "🍰"),
        (["تارت","tart","فطيرة","pie"],               "🥧"),
        (["آيس","ice cream"],                         "🍦"),
        (["قهوة","café","coffee"],                    "☕"),
        (["أتاي","thé","tea","شاي"],                  "🍵"),
        (["عصير","jus","juice"],                      "🥤"),
        (["ماء","eau","water"],                       "💧"),
        (["كوكا","cola","pepsi","soda"],              "🥤"),
    ]
    for kws, emoji in mapping:
        if any(k in n for k in kws):
            return emoji
    return "🍽️"



# ══════════════════════════════════════════════════════════════════
# 🎨 METHOD 4 — POLLINATIONS AI (توليد صور بالذكاء الاصطناعي)
# ══════════════════════════════════════════════════════════════════

POLLINATIONS_KEY = os.getenv("POLLINATIONS_API_KEY", "")
POLLINATIONS_URL = "https://image.pollinations.ai/prompt"

def fetch_pollinations(name: str, count: int = 5) -> list:
    """
    يولد صور AI لأكلة معينة باستخدام Pollinations
    يرجع قائمة من روابط الصور
    count: عدد الصور المطلوبة (افتراضي 5)
    """
    results = []
    
    # بناء prompt احترافي للأكلة المغربية
    base_prompt = f"professional food photography of {name}, moroccan cuisine, restaurant quality, appetizing, high resolution, natural lighting, close up"
    
    headers = {}
    if POLLINATIONS_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_KEY}"
    
    for i in range(count):
        try:
            # seed مختلف لكل صورة للحصول على تنوع
            seed = 100 + (i * 37)
            url = f"{POLLINATIONS_URL}/{requests.utils.quote(base_prompt)}?width=512&height=512&seed={seed}&model=flux&nologo=true"
            
            # تأخير بسيط بين الطلبات
            if i > 0:
                time.sleep(2)
            
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                results.append({
                    "url": url,
                    "thumb": url,
                    "credit": f"AI Generated — Pollinations ({name})",
                    "method": "pollinations",
                    "seed": seed
                })
        except Exception as e:
            log.warning(f"Pollinations error for {name}: {e}")
            continue
    
    return results


def pollinations_available() -> tuple:
    """يتحقق من إمكانية استخدام Pollinations"""
    if POLLINATIONS_KEY:
        return True, "✅ متصل بمفتاح"
    # يعمل بدون مفتاح أيضاً لكن أبطأ
    return True, "✅ يعمل بدون مفتاح (أبطأ)"


def _arabic_to_search(name: str) -> str:
    """
    تحويل اسم الأكلة لكلمة بحث إنجليزية
    يدعم العربية والفرنسية والإنجليزية
    """
    ar_map = {
        # عربي
        "طاجين دجاج":  "moroccan chicken tagine",
        "طاجين لحم":   "moroccan beef tagine",
        "طاجين":       "moroccan tagine",
        "كسكس":        "moroccan couscous",
        "حريرة":       "harira soup moroccan",
        "بسطيلة":      "moroccan bastilla pie",
        "بريوات":      "moroccan briouats pastry",
        "مشوي":        "grilled meat skewers",
        "دجاج مشوي":   "grilled chicken",
        "سمك مشوي":    "grilled fish",
        "سمك":         "fish dish",
        "سلطة":        "fresh salad",
        "حلوى":        "moroccan dessert",
        "شباكية":      "moroccan chebakia sweet",
        "أتاي":        "moroccan mint tea",
        "عصير":        "fresh juice glass",
        "قهوة":        "coffee cup",
        "برغر":        "gourmet burger",
        "بيتزا":       "pizza",
        "باستا":       "pasta dish",
        "ساندويش":     "sandwich",
        "لحم":         "meat dish",
        "دجاج":        "chicken dish",
        # فرنسي → إنجليزي
        "tajine":      "moroccan tagine food",
        "couscous":    "moroccan couscous",
        "pastilla":    "moroccan pastilla pie",
        "harira":      "moroccan harira soup",
        "briouats":    "moroccan briouats",
        "tanjia":      "moroccan tanjia meat",
        "seffa":       "moroccan seffa noodles",
        "rafissa":     "moroccan rafissa chicken",
        "sardine":     "sardines fish dish",
        "filet":       "beef filet steak",
        "poulet":      "chicken dish",
        "viande":      "meat dish",
        "salade":      "salad dish",
        "soupe":       "soup bowl",
        "creme":       "cream soup",
        "tarte":       "tart dessert",
        "mousse":      "chocolate mousse dessert",
        "sorbet":      "sorbet ice cream",
        "crepe":       "crepes dessert",
        "tiramisu":    "tiramisu dessert",
        "brulee":      "creme brulee dessert",
        "panacota":    "panna cotta dessert",
        "millefeuille":"millefeuille pastry",
        "gateau":      "cake dessert",
        "fondant":     "chocolate fondant",
        "soufle":      "souffle dish",
        "omelette":    "omelette eggs",
        "auberge":     "eggplant dish",
    }
    name_l = name.strip().lower()

    # بحث في القاموس
    for key, en in ar_map.items():
        if key.lower() in name_l:
            return en

    # إذا كان بالفرنسية/الإنجليزية — أضف "food" فقط
    # للتأكد أن البحث يجلب صور أكل
    if any(c.isascii() and c.isalpha() for c in name_l):
        # اسم لاتيني — استخدمه مباشرة + food
        clean = name.strip().lower()
        # احذف كلمات عامة لا تفيد البحث
        for w in ["de", "du", "la", "le", "les", "au", "aux", "et", "a"]:
            clean = clean.replace(f" {w} ", " ")
        return f"{clean.strip()} food dish"

    return name.strip()


# ══════════════════════════════════════════════════════════
# 🆓 METHOD 1 — UNSPLASH
# ══════════════════════════════════════════════════════════

def fetch_unsplash(name: str, search_hint: str = "") -> dict:
    """
    يجلب صورة من Unsplash بناءً على اسم الأكلة
    search_hint: كلمة بحث مخصصة (اختياري)
    """
    if not UNSPLASH_KEY:
        return {"url": "", "thumb": "", "credit": "", "method": "unsplash", "error": "UNSPLASH_ACCESS_KEY غير محدد"}

    query = search_hint.strip() if search_hint.strip() else _arabic_to_search(name)
    cache_key = f"unsplash_{query.lower()}"

    if cache_key in _cache:
        return {"url": _cache[cache_key], "thumb": _cache[cache_key],
                "credit": "Unsplash (cached)", "method": "unsplash"}

    # محاولتين: بحث دقيق ثم بسيط
    for attempt_query in [f"food {query}", query.split()[0] + " food"]:
        try:
            r = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": attempt_query, "per_page": 1,
                        "orientation": "squarish", "content_filter": "high"},
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                timeout=8
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    photo = results[0]
                    url   = photo["urls"]["regular"]
                    thumb = photo["urls"]["small"]
                    _cache[cache_key] = url
                    log.info(f"✅ Unsplash: {name} → {url[:50]}...")
                    return {
                        "url":    url,
                        "thumb":  thumb,
                        "credit": f"📸 {photo['user']['name']} on Unsplash",
                        "method": "unsplash"
                    }
            elif r.status_code == 403:
                return {"url":"","thumb":"","credit":"","method":"unsplash",
                        "error":"Rate limit أو Key خاطئ"}
        except Exception as e:
            log.warning(f"Unsplash attempt error: {e}")
            continue

    return {"url":"","thumb":"","credit":"","method":"unsplash","error":f"لم تُوجد صورة لـ: {query}"}


def fetch_unsplash_batch(items: list[dict], progress_cb=None, delay=0.35) -> list[dict]:
    for i, item in enumerate(items):
        hint   = item.get("search_hint","") or item.get("search_query","")
        result = fetch_unsplash(item.get("name",""), search_hint=hint)
        item["image_url"]    = result.get("url","")
        item["image_thumb"]  = result.get("thumb","")
        item["image_credit"] = result.get("credit","")
        item["image_method"] = "unsplash"
        item["emoji"]        = get_food_emoji(item.get("name",""), item.get("category",""))
        if progress_cb:
            progress_cb(i+1, len(items), item["name"],
                        "✅ صورة" if result.get("url") else "⚠️ emoji fallback")
        if i < len(items)-1:
            time.sleep(delay)
    return items


# ══════════════════════════════════════════════════════════
# 🤖 METHOD 2 — DALL-E 3 (AI توليدي)
# ══════════════════════════════════════════════════════════

def generate_dalle(name: str, style: str = "luxury", custom_prompt: str = "") -> dict:
    """
    يولد صورة بـ DALL-E 3 — مخصصة 100% لاسم الأكلة
    style: luxury | modern | classic
    """
    if not OPENAI_KEY:
        return {"url":"","thumb":"","credit":"","method":"dalle",
                "error":"OPENAI_API_KEY غير محدد"}

    style_prompts = {
        "luxury":  "professional food photography, luxury restaurant plate, dark moody background, gold accents, Michelin star presentation, 4K",
        "modern":  "modern minimalist food photography, white plate, natural light, top-down view, trendy restaurant, high resolution",
        "classic": "traditional home-style food photography, warm tones, rustic wooden table, authentic presentation, appetizing",
    }

    if custom_prompt.strip():
        prompt = custom_prompt.strip()
    else:
        # بناء prompt ذكي من اسم الأكلة
        search_name = _arabic_to_search(name)
        style_desc  = style_prompts.get(style, style_prompts["luxury"])
        prompt = f"A beautiful appetizing photo of {search_name}, {style_desc}, no text, no watermark"

    try:
        r = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model":   "dall-e-3",
                "prompt":  prompt,
                "size":    "1024x1024",
                "quality": "standard",   # standard=$0.04 | hd=$0.08
                "n":       1
            },
            timeout=45
        )
        if r.status_code == 200:
            url = r.json()["data"][0]["url"]
            _cache[f"dalle_{name}"] = url
            log.info(f"✅ DALL-E: {name}")
            return {
                "url":    url,
                "thumb":  url,
                "credit": "🤖 AI Generated (DALL-E 3)",
                "method": "dalle",
                "prompt": prompt
            }
        else:
            err = r.json().get("error",{}).get("message","Unknown error")
            log.error(f"DALL-E error: {err}")
            return {"url":"","thumb":"","credit":"","method":"dalle","error":err}
    except Exception as e:
        return {"url":"","thumb":"","credit":"","method":"dalle","error":str(e)}


def generate_dalle_batch(items: list[dict], style: str = "luxury",
                          progress_cb=None, delay=1.5) -> list[dict]:
    """DALL-E batch — delay أكبر لأن التوليد يأخذ وقت"""
    for i, item in enumerate(items):
        custom = item.get("dalle_prompt","")
        result = generate_dalle(item.get("name",""), style=style, custom_prompt=custom)
        item["image_url"]    = result.get("url","")
        item["image_thumb"]  = result.get("thumb","")
        item["image_credit"] = result.get("credit","")
        item["image_method"] = "dalle"
        item["emoji"]        = get_food_emoji(item.get("name",""), item.get("category",""))
        if progress_cb:
            progress_cb(i+1, len(items), item["name"],
                        "✅ صورة AI" if result.get("url") else f"⚠️ {result.get('error','')[:40]}")
        if i < len(items)-1:
            time.sleep(delay)
    return items


# ══════════════════════════════════════════════════════════
# 📸 METHOD 3 — MANUAL UPLOAD
# ══════════════════════════════════════════════════════════

def process_manual_upload(uploaded_file, item_name: str) -> dict:
    """
    يعالج صورة مرفوعة يدوياً
    uploaded_file: BytesIO أو Streamlit UploadedFile
    Returns: dict مع base64 data URL
    """
    try:
        if hasattr(uploaded_file, "read"):
            data = uploaded_file.read()
        else:
            data = uploaded_file

        # ضغط خفيف بـ Pillow لتوفير الحجم
        from PIL import Image
        img = Image.open(BytesIO(data))

        # تحويل لـ RGB إذا RGBA
        if img.mode in ("RGBA","P"):
            img = img.convert("RGB")

        # Resize لـ 600x600 max (كافي للمينيو)
        img.thumbnail((600, 600), Image.LANCZOS)

        # حفظ كـ JPEG محسّن
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        buf.seek(0)
        compressed = buf.read()

        # تحويل لـ base64 data URL
        b64 = base64.b64encode(compressed).decode()
        data_url = f"data:image/jpeg;base64,{b64}"

        size_kb = len(compressed) // 1024
        log.info(f"✅ Manual upload: {item_name} — {size_kb}KB")

        return {
            "url":    data_url,
            "thumb":  data_url,
            "credit": "📸 صورة المطعم",
            "method": "manual",
            "size_kb": size_kb
        }
    except Exception as e:
        log.error(f"Manual upload error: {e}")
        return {"url":"","thumb":"","credit":"","method":"manual","error":str(e)}


# ══════════════════════════════════════════════════════════
# 🎯 UNIFIED DISPATCHER
# ══════════════════════════════════════════════════════════

def fetch_image(
    method:       str,           # "unsplash" | "dalle" | "manual"
    item_name:    str,
    category:     str   = "",
    search_hint:  str   = "",    # Unsplash: كلمة بحث مخصصة
    dalle_style:  str   = "luxury",
    dalle_prompt: str   = "",    # DALL-E: prompt مخصص
    upload_file          = None, # Manual: الملف المرفوع
) -> dict:
    """
    🎯 الدالة الموحدة — استدعها بأي طريقة
    """
    if method == "unsplash":
        return fetch_unsplash(item_name, search_hint=search_hint)

    elif method == "dalle":
        return generate_dalle(item_name, style=dalle_style, custom_prompt=dalle_prompt)

    elif method == "manual":
        if upload_file:
            return process_manual_upload(upload_file, item_name)
        return {"url":"","thumb":"","credit":"","method":"manual","error":"لم يتم رفع ملف"}

    else:
        return {"url":"","thumb":"","credit":"","method":"none","error":f"طريقة غير معروفة: {method}"}


def available_methods() -> dict:
    """يرجع الطرق المتاحة بناءً على الـ API Keys الموجودة"""
    return {
        "unsplash": bool(UNSPLASH_KEY),
        "dalle":    bool(OPENAI_KEY),
        "manual":   True,   # دائماً متاح
    }

# ══════════════════════════════════════════════════════════
# 🆕 PEXELS + PIXABAY — جلب صور متعددة للاختيار
# ══════════════════════════════════════════════════════════

def fetch_multi_source_photos(search_query: str, per_source: int = 4) -> list:
    """
    يجلب صور من Pexels + Pixabay + Unsplash في نفس الوقت
    يرجع قائمة من الصور مع المصدر لكل واحدة
    """
    results = []

    # ── 1. Pexels ──────────────────────────────────────
    if PEXELS_KEY:
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_KEY},
                params={"query": search_query, "per_page": per_source, "orientation": "square"},
                timeout=8
            )
            if r.status_code == 200:
                for photo in r.json().get("photos", []):
                    results.append({
                        "url":    photo["src"]["medium"],
                        "thumb":  photo["src"]["small"],
                        "source": "Pexels",
                        "credit": f"Photo by {photo['photographer']} on Pexels",
                        "id":     str(photo["id"])
                    })
        except Exception as e:
            log.warning(f"Pexels: {e}")

    # ── 2. Pixabay ─────────────────────────────────────
    if PIXABAY_KEY:
        try:
            r = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": PIXABAY_KEY,
                    "q": search_query,
                    "per_page": per_source,
                    "image_type": "photo",
                    "category": "food",
                    "safesearch": "true"
                },
                timeout=8
            )
            if r.status_code == 200:
                for hit in r.json().get("hits", []):
                    results.append({
                        "url":    hit["webformatURL"],
                        "thumb":  hit["previewURL"],
                        "source": "Pixabay",
                        "credit": f"Image from Pixabay",
                        "id":     str(hit["id"])
                    })
        except Exception as e:
            log.warning(f"Pixabay: {e}")

    # ── 3. Unsplash ────────────────────────────────────
    if UNSPLASH_KEY:
        try:
            r = requests.get(
                "https://api.unsplash.com/search/photos",
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                params={"query": search_query, "per_page": per_source, "orientation": "squarish"},
                timeout=8
            )
            if r.status_code == 200:
                for photo in r.json().get("results", []):
                    results.append({
                        "url":    photo["urls"]["regular"],
                        "thumb":  photo["urls"]["small"],
                        "source": "Unsplash",
                        "credit": f"Photo by {photo['user']['name']} on Unsplash",
                        "id":     photo["id"]
                    })
        except Exception as e:
            log.warning(f"Unsplash: {e}")

    return results


def available_sources() -> dict:
    """يرجع المصادر المتاحة"""
    return {
        "pexels":   bool(PEXELS_KEY),
        "pixabay":  bool(PIXABAY_KEY),
        "unsplash": bool(UNSPLASH_KEY),
    }
