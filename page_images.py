"""
📥 page_images.py — صفحة الصور الموحدة
3 طرق في UI واحد — أنت تختار كل مرة
"""

import streamlit as st
import gspread
import json
import os
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from image_engine import (
    fetch_unsplash_batch, generate_dalle_batch,
    process_manual_upload, fetch_image,
    get_food_emoji, available_methods,
    fetch_multi_source_photos, available_sources,
    _arabic_to_search,
    UNSPLASH_KEY, OPENAI_KEY, PEXELS_KEY, PIXABAY_KEY
)

load_dotenv()

SCOPES          = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
SA_JSON_PATH    = os.getenv("GOOGLE_SA_JSON","./service_account.json")
SA_JSON_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT","")

# ══════════════════════════════════════════════════════════
# 🎨 CSS
# ══════════════════════════════════════════════════════════
CSS = """
<style>
/* METHOD SELECTOR */
.method-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin:1rem 0}
.method-card{
  background:#101010;border:2px solid #1a1a1a;border-radius:14px;
  padding:1.2rem 1rem;text-align:center;cursor:pointer;
  transition:all .25s;user-select:none
}
.method-card:hover{border-color:#C9A84C55;background:#141414}
.method-card.active{border-color:#C9A84C;background:#1a1500;box-shadow:0 0 20px rgba(201,168,76,.12)}
.method-icon{font-size:2.2rem;margin-bottom:.5rem}
.method-title{font-size:.9rem;font-weight:700;color:#E8C97A;margin-bottom:.2rem}
.method-badge{
  display:inline-block;font-size:.65rem;font-weight:700;
  padding:.15rem .55rem;border-radius:10px;margin-top:.3rem
}
.badge-free{background:rgba(0,230,118,.12);color:#69f0ae;border:1px solid rgba(0,230,118,.2)}
.badge-paid{background:rgba(229,57,53,.1);color:#ef9a9a;border:1px solid rgba(229,57,53,.2)}
.badge-always{background:rgba(201,168,76,.12);color:#C9A84C;border:1px solid rgba(201,168,76,.2)}
.method-desc{font-size:.75rem;color:#444;margin-top:.4rem;line-height:1.5}

/* ITEMS GRID */
.items-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
  gap:.8rem;margin:1rem 0
}
.item-cell{
  background:#101010;border:1px solid #1a1a1a;border-radius:12px;
  overflow:hidden;transition:border-color .2s
}
.item-cell:hover{border-color:#C9A84C55}
.item-cell.has-img{border-color:#C9A84C33}
.cell-img{width:100%;height:110px;object-fit:cover}
.cell-emoji{width:100%;height:110px;display:flex;align-items:center;
  justify-content:center;font-size:2.8rem;background:#0a0a0a}
.cell-body{padding:.55rem .6rem}
.cell-name{font-size:.78rem;font-weight:700;color:#E8C97A;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cell-price{font-size:.82rem;color:#C9A84C;font-weight:900;margin-top:.1rem}
.cell-badge{font-size:.6rem;color:#333;margin-top:.2rem}

/* STATUS LINE */
.status-line{
  display:flex;align-items:center;gap:.5rem;
  font-size:.8rem;padding:.4rem .7rem;
  border-radius:8px;margin:.2rem 0
}
.s-ok  {background:rgba(0,230,118,.06);color:#69f0ae;border:1px solid rgba(0,230,118,.15)}
.s-warn{background:rgba(255,193,7,.06);color:#ffe57f;border:1px solid rgba(255,193,7,.15)}
.s-err {background:rgba(229,57,53,.06);color:#ef9a9a;border:1px solid rgba(229,57,53,.15)}
.s-info{background:rgba(201,168,76,.06);color:#C9A84C;border:1px solid rgba(201,168,76,.15)}

/* UPLOAD ZONE */
.upload-zone{
  border:2px dashed #2a2a2a;border-radius:14px;
  padding:2rem;text-align:center;background:#0a0a0a;
  transition:border-color .2s
}
.upload-zone:hover{border-color:#C9A84C55}

/* PROGRESS */
.prg-out{background:#111;border-radius:6px;height:6px;overflow:hidden;margin:.5rem 0}
.prg-in{height:100%;border-radius:6px;
  background:linear-gradient(90deg,#C9A84C,#E8C97A);transition:width .3s}
</style>
"""

# ══════════════════════════════════════════════════════════
# 📊 GOOGLE SHEETS
# ══════════════════════════════════════════════════════════

def _gs():
    if SA_JSON_CONTENT:
        c = Credentials.from_service_account_info(json.loads(SA_JSON_CONTENT), scopes=SCOPES)
    else:
        c = Credentials.from_service_account_file(SA_JSON_PATH, scopes=SCOPES)
    return gspread.authorize(c)

def load_sheet_items(sheet_id: str, tab: str) -> list[dict]:
    """يجلب الأكلات الموجودة في الشيت"""
    try:
        ws = _gs().open_by_key(sheet_id).worksheet(tab)
        return ws.get_all_records()
    except Exception as e:
        st.error(f"خطأ في قراءة الشيت: {e}")
        return []

def update_images_in_sheet(sheet_id: str, tab: str, items: list[dict]) -> int:
    """يحدث عمود image_url في الشيت — يرجع عدد الصفوف المحدثة"""
    try:
        client = _gs()
        spread = client.open_by_key(sheet_id)
        ws     = spread.worksheet(tab)

        headers = ws.row_values(1)

        # تأكد من وجود عمود image_url
        if "image_url" not in headers:
            ws.update_cell(1, len(headers)+1, "image_url")
            headers.append("image_url")
        if "image_credit" not in headers:
            ws.update_cell(1, len(headers)+1, "image_credit")
            headers.append("image_credit")

        img_col    = headers.index("image_url") + 1
        credit_col = headers.index("image_credit") + 1
        name_col   = headers.index("name") + 1 if "name" in headers else 1

        records = ws.get_all_records()
        updated = 0

        # بناء قاموس اسم → صف
        name_to_row = {}
        for i, r in enumerate(records):
            nm = str(r.get("name","")).strip()
            if nm:
                name_to_row[nm] = i + 2   # +1 header +1 1-indexed

        # batch update
        cell_updates = []
        for item in items:
            nm  = str(item.get("name","")).strip()
            url = item.get("image_url","")
            crd = item.get("image_credit","")
            if nm in name_to_row and url:
                row = name_to_row[nm]
                cell_updates.append({"range": gspread.utils.rowcol_to_a1(row, img_col),    "values": [[url]]})
                cell_updates.append({"range": gspread.utils.rowcol_to_a1(row, credit_col), "values": [[crd]]})
                updated += 1

        if cell_updates:
            ws.batch_update(cell_updates)

        return updated
    except Exception as e:
        st.error(f"خطأ في تحديث الشيت: {e}")
        return 0


# ══════════════════════════════════════════════════════════
# 🚀 MAIN PAGE
# ══════════════════════════════════════════════════════════

def page_images(restaurants: list):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("## 🖼️ إدارة صور الأكلات")
    st.markdown("اختر الطريقة المناسبة — يمكنك تغييرها في كل مرة بحرية تامة")

    if not restaurants:
        st.info("📭 أضف مطعماً أولاً"); return

    avail = available_methods()

    # ── اختيار المطعم والـ Tab
    c1, c2 = st.columns(2)
    with c1:
        opts     = {f"#{r.get('restaurant_id','?')} — {r.get('name','مطعم')}": r for r in restaurants}
        sel      = st.selectbox("🏪 المطعم", list(opts.keys()))
        r        = opts[sel]
        sheet_id = r.get("sheet_id","")
    with c2:
        tab_opts = ["الأطباق الرئيسية","المقبلات","الحلويات","المشروبات"]
        sel_tab  = st.selectbox("📂 الصنف (Tab)", tab_opts)
        custom_tab = st.text_input("أو اكتب Tab مخصص", placeholder="اتركه فارغاً للاستخدام المختار أعلاه")
        final_tab  = custom_tab.strip() if custom_tab.strip() else sel_tab

    # ══════════════════════════════════════════════════════
    # 🎛️ METHOD SELECTOR — البطاقات الثلاث
    # ══════════════════════════════════════════════════════
    st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
    st.markdown("### 🎛️ اختر طريقة الصور")

    # نبني HTML للبطاقات
    def method_card_html(mid, icon, title, badge_cls, badge_txt, desc, available, active):
        border_cls = "active" if active else ""
        lock       = "" if available else ' style="opacity:.4;cursor:not-allowed"'
        unavail    = "" if available else "<br><small style='color:#555'>⛔ Key غير محدد</small>"
        return f"""
        <div class="method-card {border_cls}" id="mc_{mid}" onclick="selectMethod('{mid}')" {lock}>
          <div class="method-icon">{icon}</div>
          <div class="method-title">{title}</div>
          <div><span class="method-badge {badge_cls}">{badge_txt}</span></div>
          <div class="method-desc">{desc}{unavail}</div>
        </div>"""

    # الطريقة المحددة حالياً
    if "img_method" not in st.session_state:
        st.session_state.img_method = "multi"  # الافتراضي: اختيار من 3 مصادر

    cur = st.session_state.img_method

    # Streamlit radio مخفي لتتبع الاختيار
    method_labels = {
        "multi":    "🎯 اختر من 3 مصادر — الأفضل",
        "unsplash": "🆓 Unsplash — مجاني",
        "dalle":    "🤖 AI توليدي — DALL-E",
        "manual":   "📸 رفع يدوي — صورك الخاصة",
    }
    # إضافة multi كخيار دائم
    all_methods = {"multi": True, **avail}
    available_keys = [k for k,v in all_methods.items() if v]
    display_labels = [method_labels[k] for k in available_keys]

    chosen_label = st.radio(
        "طريقة الصور",
        display_labels,
        index=available_keys.index(cur) if cur in available_keys else 0,
        horizontal=True,
        label_visibility="collapsed"
    )
    selected_method = available_keys[display_labels.index(chosen_label)]
    st.session_state.img_method = selected_method

    # بطاقة شرح الطريقة المحددة
    method_info = {
        "multi": {
            "icon": "🎯",
            "color": "#C9A84C",
            "title": "اختر من Pexels + Pixabay + Unsplash",
            "details": "يجلب صور من 3 مصادر في نفس الوقت — أنت تختار الأنسب لكل أكلة",
            "warning": "",
            "cost": "مجاني 100%",
        },
        "unsplash": {
            "icon": "🆓",
            "color": "#69f0ae",
            "title": "Unsplash — مجاني 100%",
            "details": "يبحث عن صور احترافية حسب اسم الأكلة — 50 صورة/ساعة مجاناً",
            "warning": "",
            "cost": "مجاني تماماً",
        },
        "dalle": {
            "icon": "🤖",
            "color": "#C9A84C",
            "title": "DALL-E 3 — AI يصنع الصور",
            "details": "يولد صورة مخصصة 100% لكل أكلة بناءً على اسمها وطابع المطعم",
            "warning": "~$0.04 لكل صورة",
            "cost": "مدفوع",
        },
        "manual": {
            "icon": "📸",
            "color": "#29b6f6",
            "title": "رفع يدوي — صورك الحقيقية",
            "details": "أنت ترفع صور أكلاتك الحقيقية — الأفضل لمن يبغي دقة عالية",
            "warning": "",
            "cost": "مجاني",
        },
    }
    info = method_info[selected_method]
    st.markdown(f"""
    <div style="background:#0a0a0a;border:1px solid {info['color']}33;border-right:3px solid {info['color']};
         border-radius:10px;padding:.8rem 1.1rem;margin:.5rem 0 1.2rem;display:flex;gap:1rem;align-items:center">
      <span style="font-size:1.8rem">{info['icon']}</span>
      <div>
        <div style="color:{info['color']};font-weight:700;font-size:.9rem">{info['title']}</div>
        <div style="color:#555;font-size:.78rem;margin-top:.15rem">{info['details']}</div>
        {f'<div style="color:#ef9a9a;font-size:.72rem;margin-top:.1rem">💰 {info["warning"]}</div>' if info['warning'] else ''}
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ══════════════════════════════════════════════════════
    # PANELS حسب الطريقة
    # ══════════════════════════════════════════════════════

    # ── جلب الأكلات من الشيت
    items_from_sheet = []
    if sheet_id:
        with st.spinner("📊 جاري قراءة القائمة من الشيت..."):
            items_from_sheet = load_sheet_items(sheet_id, final_tab)

    if not items_from_sheet and selected_method != "manual":
        st.warning(f"📭 لا توجد أكلات في Tab '{final_tab}' — أضف الأكلات أولاً أو اختر tab آخر")

    # ─────────────────────────────────────────────────────
    # PANEL 0: MULTI SOURCE — اختيار من 3 مصادر
    # ─────────────────────────────────────────────────────
    if selected_method == "multi":
        srcs = available_sources()
        active_sources = [s for s,v in srcs.items() if v]

        # إظهار حالة المصادر
        src_cols = st.columns(3)
        src_info = {
            "pexels":   ("Pexels",   "🟢" if srcs["pexels"]   else "🔴", "#69f0ae" if srcs["pexels"]   else "#ef9a9a"),
            "pixabay":  ("Pixabay",  "🟢" if srcs["pixabay"]  else "🔴", "#69f0ae" if srcs["pixabay"]  else "#ef9a9a"),
            "unsplash": ("Unsplash", "🟢" if srcs["unsplash"] else "🔴", "#69f0ae" if srcs["unsplash"] else "#ef9a9a"),
        }
        for i, (src, (name, icon, color)) in enumerate(src_info.items()):
            with src_cols[i]:
                status = "متصل ✅" if srcs[src] else "Key غير محدد ⚠️"
                st.markdown(f"""
                <div style="background:#101010;border:1px solid {color}33;border-radius:10px;
                     padding:.7rem;text-align:center">
                  <div style="font-size:1.5rem">{icon}</div>
                  <div style="color:{color};font-weight:700;font-size:.85rem">{name}</div>
                  <div style="color:#444;font-size:.7rem">{status}</div>
                </div>""", unsafe_allow_html=True)

        if not active_sources:
            st.error("❌ لا يوجد أي API Key محدد — أضف PEXELS_API_KEY أو PIXABAY_API_KEY في Secrets")
        else:
            st.markdown(f"✅ **{len(active_sources)} مصادر متاحة:** {', '.join(active_sources)}")

        # اختيار الأكلة
        if items_from_sheet:
            st.markdown("---")
            st.markdown("### 🍽️ اختر أكلة وابحث عن صورها")

            item_names = [i.get("name","") for i in items_from_sheet if i.get("name")]
            sel_item_multi = st.selectbox("اختر الأكلة", item_names, key="multi_item_sel")

            # البحث — تحويل الاسم لكلمة بحث إنجليزية
            sel_item_obj = next((i for i in items_from_sheet if i.get("name") == sel_item_multi), {})
            # إذا كان الاسم بالفرنسية أو الإنجليزية نستخدمه مباشرة
            _ar_result = _arabic_to_search(sel_item_multi)
            default_query = _ar_result if _ar_result and _ar_result != sel_item_multi else sel_item_multi

            col_q, col_btn = st.columns([3, 1])
            with col_q:
                search_q = st.text_input("🔍 كلمة البحث (بالإنجليزي)",
                                          value=default_query,
                                          key="multi_search_q",
                                          help="يمكنك تعديلها لنتائج أدق")
            with col_btn:
                st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
                search_btn = st.button("🔍 بحث", use_container_width=True, key="multi_search_btn")

            if search_btn or st.session_state.get("_multi_photos"):
                if search_btn:
                    with st.spinner(f"🔍 جاري البحث في {len(active_sources)} مصادر..."):
                        photos = fetch_multi_source_photos(search_q, per_source=4)
                        st.session_state["_multi_photos"] = photos
                        st.session_state["_multi_item"] = sel_item_multi

                photos = st.session_state.get("_multi_photos", [])
                current_item = st.session_state.get("_multi_item", sel_item_multi)

                if photos:
                    st.markdown(f"### 📸 {len(photos)} صورة — اختر الأنسب لـ **{current_item}**")

                    # عرض الصور في شبكة 4 أعمدة
                    cols_per_row = 4
                    for row_start in range(0, len(photos), cols_per_row):
                        row_photos = photos[row_start:row_start+cols_per_row]
                        cols = st.columns(cols_per_row)
                        for j, photo in enumerate(row_photos):
                            with cols[j]:
                                src_color = {"Pexels":"#69f0ae","Pixabay":"#80d8ff","Unsplash":"#C9A84C"}.get(photo["source"],"#888")
                                st.image(photo["thumb"], use_container_width=True)
                                st.markdown(f'<div style="font-size:.65rem;color:{src_color};text-align:center;margin-top:.2rem">{photo["source"]}</div>', unsafe_allow_html=True)
                                if st.button(f"✅ اختر", key=f"pick_photo_{row_start+j}", use_container_width=True):
                                    # حفظ الصورة في الشيت
                                    target = {"name": current_item, "image_url": photo["url"], "image_credit": photo["credit"]}
                                    updated = update_images_in_sheet(sheet_id, final_tab, [target])
                                    if updated:
                                        st.success(f"✅ تم حفظ صورة '{current_item}' من {photo['source']} في الشيت!")
                                        st.session_state.pop("_multi_photos", None)
                                        st.rerun()
                                    else:
                                        st.error("❌ لم يتم الحفظ — تأكد من اسم الأكلة")
                else:
                    st.warning("⚠️ لم تُجلب أي صور — جرب كلمة بحث أخرى")

        else:
            st.warning("📭 لا توجد أكلات في هذا الصنف — أضف الأكلات أولاً")

    # ─────────────────────────────────────────────────────
    # PANEL A: UNSPLASH
    # ─────────────────────────────────────────────────────
    elif selected_method == "unsplash":
        st.markdown("#### 🆓 إعدادات Unsplash")

        col1, col2 = st.columns(2)
        with col1:
            only_missing = st.toggle("🔄 تحديث الأكلات التي ليس لها صور فقط", value=True)
        with col2:
            custom_delay = st.slider("التأخير بين الطلبات (ثانية)", 0.2, 2.0, 0.4, 0.1,
                                     help="زد الرقم إذا ظهر Rate Limit")

        # تخصيص كلمات البحث
        with st.expander("🔍 تخصيص كلمات البحث (اختياري)"):
            st.markdown('<div style="color:#555;font-size:.78rem;margin-bottom:.5rem">يمكنك تغيير كلمة البحث لكل أكلة لنتائج أفضل</div>', unsafe_allow_html=True)
            search_overrides = {}
            if items_from_sheet:
                for item in items_from_sheet[:10]:
                    nm = item.get("name","")
                    if nm:
                        from image_engine import _arabic_to_search
                        default_q = item.get("search_hint","") or _arabic_to_search(nm)
                        override  = st.text_input(f"`{nm}`", value=default_q, key=f"sh_{nm}")
                        search_overrides[nm] = override

        if items_from_sheet and st.button("🚀 جلب صور Unsplash", use_container_width=True):
            targets = [i for i in items_from_sheet
                      if not only_missing or not i.get("image_url","")]
            if not targets:
                st.info("✅ كل الأكلات لها صور بالفعل — ألغِ تفعيل 'تحديث الناقصة فقط' لإعادة الجلب")
            else:
                # تطبيق الـ overrides
                for item in targets:
                    nm = item.get("name","")
                    if nm in search_overrides:
                        item["search_hint"] = search_overrides[nm]

                pb      = st.progress(0)
                stat    = st.empty()
                results = []

                def on_progress(done, total, name, status):
                    pb.progress(done/total)
                    icon = "📸" if "صورة" in status else "⚠️"
                    stat.markdown(f'{icon} **{done}/{total}** — `{name}` — {status}')
                    results.append((name, status))

                with st.spinner(""):
                    fetch_unsplash_batch(targets, progress_cb=on_progress, delay=custom_delay)

                pb.progress(1.0)
                found = sum(1 for _,s in results if "صورة" in s)
                stat.markdown(f"✅ **{found}/{len(targets)}** صورة من Unsplash")

                st.session_state["pending_items"]    = targets
                st.session_state["pending_sheet_id"] = sheet_id
                st.session_state["pending_tab"]      = final_tab

    # ─────────────────────────────────────────────────────
    # PANEL B: DALL-E
    # ─────────────────────────────────────────────────────
    elif selected_method == "dalle":
        st.markdown("#### 🤖 إعدادات DALL-E 3")

        col1, col2 = st.columns(2)
        with col1:
            dalle_style = st.selectbox("🎨 طابع الصور",
                ["luxury","modern","classic"],
                format_func=lambda x:{
                    "luxury":  "✨ فاخر — خلفية داكنة وذهبي",
                    "modern":  "⚡ عصري — أبيض ونظيف",
                    "classic": "🏛️ كلاسيكي — دافئ وتقليدي"
                }[x])
            only_missing_d = st.toggle("تحديث الناقصة فقط", value=True, key="dm")
        with col2:
            st.markdown("""
            <div style="background:rgba(229,57,53,.06);border:1px solid rgba(229,57,53,.15);
                 border-radius:8px;padding:.8rem;font-size:.8rem;color:#ef9a9a">
            <b>💰 تقدير التكلفة:</b><br>
            • 10 صور: ~$0.40<br>
            • 30 صور: ~$1.20<br>
            • Standard quality — 1024×1024
            </div>
            """, unsafe_allow_html=True)

        # Prompt مخصص per item
        with st.expander("✏️ Prompts مخصصة لأكلات محددة (اختياري)"):
            st.markdown('<div style="color:#555;font-size:.78rem;margin-bottom:.5rem">اتركه فارغاً لتوليد تلقائي</div>', unsafe_allow_html=True)
            custom_prompts = {}
            if items_from_sheet:
                for item in items_from_sheet[:8]:
                    nm = item.get("name","")
                    if nm:
                        p = st.text_input(f"`{nm}`", value="", placeholder="وصف الصورة بالإنجليزي...", key=f"dp_{nm}")
                        if p.strip():
                            custom_prompts[nm] = p.strip()

        # تقدير تكلفة
        if items_from_sheet:
            targets_count = sum(1 for i in items_from_sheet if not i.get("image_url",""))
            cost_est      = targets_count * 0.04
            st.markdown(f"""
            <div class="status-line s-info">
            💰 الأكلات التي تحتاج صوراً: <b>{targets_count}</b> — التكلفة التقديرية: <b>~${cost_est:.2f}</b>
            </div>""", unsafe_allow_html=True)

        if items_from_sheet and st.button("🤖 توليد صور AI", use_container_width=True):
            targets = [i for i in items_from_sheet
                      if not only_missing_d or not i.get("image_url","")]
            if not targets:
                st.info("✅ كل الأكلات لها صور")
            else:
                for item in targets:
                    nm = item.get("name","")
                    if nm in custom_prompts:
                        item["dalle_prompt"] = custom_prompts[nm]

                pb   = st.progress(0)
                stat = st.empty()
                results = []

                def on_dalle(done, total, name, status):
                    pb.progress(done/total)
                    stat.markdown(f'🤖 **{done}/{total}** — `{name}` — {status}')
                    results.append((name, status))

                with st.spinner("🤖 DALL-E يصنع الصور..."):
                    generate_dalle_batch(targets, style=dalle_style,
                                         progress_cb=on_dalle, delay=2.0)

                found = sum(1 for _,s in results if "AI" in s)
                stat.markdown(f"✅ **{found}/{len(targets)}** صورة مولدة")

                st.session_state["pending_items"]    = targets
                st.session_state["pending_sheet_id"] = sheet_id
                st.session_state["pending_tab"]      = final_tab

    # ─────────────────────────────────────────────────────
    # PANEL C: MANUAL UPLOAD
    # ─────────────────────────────────────────────────────
    elif selected_method == "manual":
        st.markdown("#### 📸 رفع صورك الخاصة")
        st.markdown("""
        <div style="background:#0a0a0a;border:1px solid #1a1a1a;border-radius:10px;
             padding:.8rem 1.1rem;font-size:.8rem;color:#555;margin-bottom:1rem">
        <b style="color:#29b6f6">كيف يشتغل:</b><br>
        1. اختر الأكلة من القائمة المنسدلة<br>
        2. ارفع صورتها (JPG/PNG)<br>
        3. اضغط "حفظ" — الصورة تُكتب في الشيت فوراً<br>
        يمكنك تكرار العملية لكل الأكلات
        </div>
        """, unsafe_allow_html=True)

        # اختيار الأكلة
        if items_from_sheet:
            item_names = [i.get("name","") for i in items_from_sheet if i.get("name")]
            sel_item = st.selectbox("🍽️ اختر الأكلة", item_names)
        else:
            sel_item = st.text_input("🍽️ اسم الأكلة", placeholder="طاجين دجاج")

        # رفع الصورة
        col1, col2 = st.columns([3,2])
        with col1:
            uploaded = st.file_uploader(
                "📎 ارفع صورة الأكلة",
                type=["jpg","jpeg","png","webp"],
                help="الحجم الأقصى: 5MB — يتم ضغطها تلقائياً"
            )
        with col2:
            if uploaded:
                st.image(uploaded, caption="معاينة", use_column_width=True)

        if uploaded and sel_item and st.button("💾 حفظ الصورة في الشيت", use_container_width=True):
            with st.spinner("⏳ جاري المعالجة..."):
                result = process_manual_upload(uploaded, sel_item)

            if result.get("url"):
                # ابحث عن الأكلة في الشيت وحدّث صورتها
                target_item = {"name": sel_item,
                               "image_url": result["url"],
                               "image_credit": result["credit"]}
                updated = update_images_in_sheet(sheet_id, final_tab, [target_item])
                if updated:
                    size_kb = result.get("size_kb", 0)
                    st.success(f"✅ صورة '{sel_item}' محفوظة في الشيت ({size_kb}KB)")
                    st.balloons()
                else:
                    st.warning(f"⚠️ الصورة معالجة لكن لم تُحدَّث في الشيت — تأكد من اسم الأكلة")
                    st.code(result["url"][:80] + "...")
            else:
                st.error(f"❌ {result.get('error','خطأ غير محدد')}")

        # Bulk Upload
        st.markdown("---")
        st.markdown("#### 📦 رفع جماعي (اختياري)")
        st.markdown("""
        <div style="color:#555;font-size:.78rem;margin-bottom:.8rem">
        ارفع صوراً متعددة دفعة واحدة — <b>اسم الملف</b> يجب أن يطابق اسم الأكلة في الشيت
        <br>مثال: <code>طاجين دجاج.jpg</code>، <code>كسكس مغربي.png</code>
        </div>
        """, unsafe_allow_html=True)

        bulk_files = st.file_uploader(
            "📎 ارفع عدة صور",
            type=["jpg","jpeg","png","webp"],
            accept_multiple_files=True,
            key="bulk_upload"
        )

        if bulk_files and st.button("📦 حفظ الجميع", use_container_width=True):
            pb       = st.progress(0)
            stat     = st.empty()
            uploaded_items = []

            for i, f in enumerate(bulk_files):
                # استخدام اسم الملف بدون امتداد كاسم الأكلة
                item_name = os.path.splitext(f.name)[0].strip()
                result    = process_manual_upload(f, item_name)

                if result.get("url"):
                    uploaded_items.append({
                        "name":          item_name,
                        "image_url":     result["url"],
                        "image_credit":  result["credit"],
                        "image_method":  "manual",
                    })
                    stat.markdown(f"✅ **{i+1}/{len(bulk_files)}** — `{item_name}`")
                else:
                    stat.markdown(f"⚠️ **{i+1}/{len(bulk_files)}** — `{item_name}` — {result.get('error','')}")

                pb.progress((i+1)/len(bulk_files))

            if uploaded_items:
                total = update_images_in_sheet(sheet_id, final_tab, uploaded_items)
                st.success(f"✅ {total} صورة محفوظة في الشيت")
                st.session_state["pending_items"]    = uploaded_items
                st.session_state["pending_sheet_id"] = sheet_id
                st.session_state["pending_tab"]      = final_tab
            return   # Manual: لا نحتاج Preview أو Save

    # ══════════════════════════════════════════════════════
    # 👁️ PREVIEW + SAVE (للـ Unsplash و DALL-E)
    # ══════════════════════════════════════════════════════
    pending = st.session_state.get("pending_items", [])

    if pending and selected_method in ("unsplash", "dalle"):
        st.markdown("---")
        with_img   = sum(1 for i in pending if i.get("image_url"))
        with_emoji = len(pending) - with_img

        st.markdown(f"### 👁️ معاينة — {len(pending)} أكلة")

        c1, c2, c3 = st.columns(3)
        c1.metric("الأكلات", len(pending))
        c2.metric("📸 مع صورة", with_img)
        c3.metric("🎯 بدون صورة (emoji)", with_emoji)

        # Grid
        grid = '<div class="items-grid">'
        for item in pending:
            nm    = item.get("name","")
            price = item.get("price",0)
            url   = item.get("image_thumb") or item.get("image_url","")
            emoji = get_food_emoji(nm, item.get("category",""))
            meth  = item.get("image_method","")
            meth_badge = {"unsplash":"📸","dalle":"🤖","manual":"📷"}.get(meth,"🎯")

            img_blk = (f'<img class="cell-img" src="{url}" loading="lazy" onerror="this.outerHTML=\'<div class=cell-emoji>{emoji}</div>\'">'
                      if url else f'<div class="cell-emoji">{emoji}</div>')

            grid += f"""
            <div class="item-cell {"has-img" if url else ""}">
              {img_blk}
              <div class="cell-body">
                <div class="cell-name" title="{nm}">{nm}</div>
                <div class="cell-price">{float(price):.0f} {'د.م' if price else ''}</div>
                <div class="cell-badge">{meth_badge} {meth}</div>
              </div>
            </div>"""
        grid += '</div>'
        st.markdown(grid, unsafe_allow_html=True)

        # ── Save button
        st.markdown("---")
        pending_sid = st.session_state.get("pending_sheet_id", sheet_id)
        pending_tab = st.session_state.get("pending_tab", final_tab)

        c_save, c_cancel = st.columns(2)
        with c_save:
            if st.button(f"✅ حفظ {with_img} صورة في الشيت", use_container_width=True, type="primary"):
                with st.spinner("💾 جاري التحديث..."):
                    updated = update_images_in_sheet(pending_sid, pending_tab, pending)
                st.success(f"🎉 تم تحديث **{updated}** أكلة في Google Sheet")
                st.balloons()
                # Clear
                for k in ["pending_items","pending_sheet_id","pending_tab"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with c_cancel:
            if st.button("🗑️ إلغاء", use_container_width=True):
                for k in ["pending_items","pending_sheet_id","pending_tab"]:
                    st.session_state.pop(k, None)
                st.rerun()
