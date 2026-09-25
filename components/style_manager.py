# components/style_manager.py
import streamlit as st
import pandas as pd
import base64
import os
import random
import streamlit.components.v1 as components

# ==========================================
# 💡 效能救星：全域快取 Base64 圖片編碼
# ==========================================
@st.cache_data(show_spinner=False)
def get_cached_base64_image(image_path):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as file:
                encoded_string = base64.b64encode(file.read()).decode()
                mime_type = "image/gif" if image_path.lower().endswith('.gif') else "image/png"
                return f"data:{mime_type};base64,{encoded_string}"
    except Exception:
        pass
    return ""

def apply_global_theme(image_path="./image/派對盛宴邀請.png"):
    """合併原本的 load_global_css 與 set_background，統一管理所有視覺與拖曳引擎"""
    theme = st.session_state.get('theme', 'dark')
    opacity = st.session_state.get('bg_opacity', 88) / 100.0
    block_opacity = opacity * 0.7 
    
    theme_settings = {
        'pink':   {'rgb': '139, 109, 98', 'img': './image/鐵風堡.png'},
        'green':  {'rgb': '0, 54, 16',    'img': './image/翡翠林鎮.png'},
        'purple': {'rgb': '87, 99, 158',  'img': './image/月下綠洲城.png'},
        'brown':  {'rgb': '161, 115, 0',  'img': './image/沙漠衛星都市.png'},
        'blue':  {'rgb': '135, 206, 235',  'img': './image/漂浮之都藍晶港.png'},
        'dark':   {'rgb': '15, 23, 42',   'img': image_path}
    }
    
    current = theme_settings.get(theme, theme_settings['dark'])
    base_color = f"rgba({current['rgb']}, {opacity})"
    block_bg = f"rgba({current['rgb']}, {block_opacity})"
    actual_image = current['img']
    
    if not os.path.exists(actual_image):
        actual_image = image_path

    # 💡 使用快取函數讀取背景圖片，瞬間完成！
    bg_base64 = get_cached_base64_image(actual_image)
    if bg_base64:
        bg_image_css = f"""
            background-image: linear-gradient({base_color}, {base_color}), url({bg_base64});
            background-size: cover; background-position: center center; background-attachment: fixed;
        """
    else:
        bg_image_css = f"background-color: {base_color} !important;"

    # 🚨 注意這裡的 CSS，所有的大括號都必須是 {{ }}
    global_css = f"""
    <style>
    /* 隱藏預設 UI */
    #MainMenu, footer, header, div[data-testid="stToolbar"] {{ visibility: hidden; }}
    .block-container {{ padding-top: 0rem; }}
    
    /* 懸浮視窗縮放與圖示特效 */
    .glass-panel, .glass-panel-b2, .glass-panel-b4, .glass-panel-b5, .npc-overlay, .settings-modal-active {{ resize: both !important; overflow: auto !important; }}
    
    /* 👇 全域預先隱藏代理按鈕，徹底消滅 0.5 秒閃爍 */
    div[data-testid="stElementContainer"]:has(#hidden-nav-anchor),
    div[data-testid="stElementContainer"]:has(#hidden-nav-anchor) ~ div[data-testid="stElementContainer"] {{
        display: none !important;
    }}

    img[src*="icon-card"], img[alt*="icon-card"] {{ cursor: pointer !important; transition: all 0.2s ease !important; }}
    img[src*="icon-card"]:hover, img[alt*="icon-card"]:hover {{ transform: scale(1.08) !important; filter: drop-shadow(0 0 8px rgba(0, 210, 255, 0.6)) !important; }}
    img[src*="icon-card"]:active, img[alt*="icon-card"]:active {{ transform: scale(0.95) !important; }}

    /* 應用背景與區塊毛玻璃 (這裡的 {bg_image_css} 故意維持單一括號，因為它是真的要呼叫 Python 變數) */
    .stApp {{ {bg_image_css} }}
    div[data-testid="stVerticalBlock"] > div[style*="border"] {{ background-color: {block_bg} !important; backdrop-filter: blur(4px); }}
    
    /* 字體、輸入框與按鈕顏色 */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, .stText {{ color: #E2E8F0 !important; }}
    [data-testid="stAlert"] {{ background-color: transparent !important; border: 1px solid #2D3748 !important; }}
    [data-testid="stSidebar"] {{ background-color: rgba(17, 22, 34, 0.95) !important; border-right: 1px solid #1E293B; }}
    .stTextInput>div>div>input {{ background-color: #1A202C !important; color: #FFFFFF !important; border: 1px solid #4A5568 !important; }}
    div[data-testid="stDataFrame"] {{ background-color: #111622 !important; border: 1px solid #1E293B !important; border-radius: 6px; }}
    .stButton > button, .stLinkButton > a {{ background-color: #1E293B !important; color: #94A3B8 !important; border: 1px solid #334155 !important; transition: all 0.2s ease-in-out; }}
    .stButton > button:hover, .stLinkButton > a:hover {{ border-color: #00D2FF !important; color: #00D2FF !important; box-shadow: 0 0 8px rgba(0, 210, 255, 0.2); }}
    </style>
    """
    st.markdown(global_css, unsafe_allow_html=True)

    drag_engine_js = """
    <script>
    (function() {
        if (window.parent.window.customDragDelegated) return;
        window.parent.window.customDragDelegated = true;
        const doc = window.parent.document;
        
        // --- 1. 一鍵收合邏輯 ---
        doc.addEventListener('click', (e) => {
            let isIconCard = false;
            let t = e.target;
            if (t.tagName === 'IMG' && ((t.src && t.src.includes('icon-card')) || (t.alt && t.alt.includes('icon-card')))) { isIconCard = true; } 
            else if (t.closest) {
                let parentImg = t.closest('div[data-testid="stImage"]')?.querySelector('img');
                if (parentImg && ((parentImg.src && parentImg.src.includes('icon-card')) || (parentImg.alt && parentImg.alt.includes('icon-card')))) { isIconCard = true; }
            }
            if (isIconCard) {
                e.preventDefault(); e.stopPropagation();
                const getCb = (id) => doc.getElementById(id);
                const minCbs = [getCb('min-b2-card'), getCb('min-card'), getCb('min-b4-card'), getCb('min-b5-card')];
                const closeCbs = [getCb('close-b2-card'), getCb('close-card'), getCb('close-b4-card'), getCb('close-b5-card')];
                
                let isAnyOpen = false;
                let isAnyMinimized = false;
                for (let i = 0; i < 4; i++) {
                    let minCb = minCbs[i]; let closeCb = closeCbs[i];
                    if (minCb && closeCb) {
                        if (!closeCb.checked && !minCb.checked) isAnyOpen = true;
                        if (!closeCb.checked && minCb.checked) isAnyMinimized = true;
                    }
                }
                
                let nextMin = false; let nextClose = false;
                if (isAnyOpen) { nextMin = true; nextClose = false; } 
                else if (isAnyMinimized) { nextMin = false; nextClose = true; } 
                else { nextMin = false; nextClose = false; }
                
                minCbs.forEach(cb => { if (cb) cb.checked = nextMin; });
                closeCbs.forEach(cb => { if (cb) cb.checked = nextClose; });
            }
        }, true);
        
        // --- 2. 拖曳引擎 ---
        let isDragging = false, currentEl = null, startX, startY, initialX, initialY;
        const onDown = (e) => {
            let handle = e.target.closest('.header-bar, .header-bar-b2, .header-bar-b4, .header-bar-b5, .npc-drag-handle, .settings-drag-handle');
            if (!handle || e.target.closest('button, input, label, .action-btn, .action-btn-b2, .action-btn-b4, .action-btn-b5')) return;
            let el = handle.closest('.glass-panel, .glass-panel-b2, .glass-panel-b4, .glass-panel-b5, .npc-wrapper, .settings-modal-active');
            if (!el) el = handle.closest('div[data-testid="stVerticalBlock"].settings-modal-active');
            if (!el) return;
            
            isDragging = true; currentEl = el;
            let clientX = e.touches ? e.touches[0].clientX : e.clientX;
            let clientY = e.touches ? e.touches[0].clientY : e.clientY;
            startX = clientX; startY = clientY;
            let rect = el.getBoundingClientRect();
            
            el.style.transition = 'none';
            el.style.left = rect.left + 'px'; el.style.top = rect.top + 'px';
            el.style.right = 'auto'; el.style.bottom = 'auto'; el.style.transform = 'none'; el.style.margin = '0';
            initialX = rect.left; initialY = rect.top; handle.style.cursor = 'grabbing';
        };
        const onMove = (e) => {
            if (!isDragging || !currentEl) return;
            e.preventDefault(); 
            let clientX = e.touches ? e.touches[0].clientX : e.clientX;
            let clientY = e.touches ? e.touches[0].clientY : e.clientY;
            currentEl.style.left = (initialX + (clientX - startX)) + 'px';
            currentEl.style.top = (initialY + (clientY - startY)) + 'px';
        };
        const onUp = () => {
            if (isDragging && currentEl) {
                currentEl.style.transition = '';
                let handle = currentEl.querySelector('.header-bar, .header-bar-b2, .header-bar-b4, .header-bar-b5, .npc-drag-handle, .settings-drag-handle');
                if(handle) handle.style.cursor = 'grab';
            }
            isDragging = false; currentEl = null;
        };
        doc.addEventListener('mousedown', onDown); doc.addEventListener('touchstart', onDown, {passive: false});
        doc.addEventListener('mousemove', onMove, {passive: false}); doc.addEventListener('touchmove', onMove, {passive: false});
        doc.addEventListener('mouseup', onUp); doc.addEventListener('touchend', onUp);
    })();
    </script>
    """
    components.html(drag_engine_js, height=0, width=0)

def render_fireflies():
    num_fireflies = 5 
    css_rules, html_divs = [], []
    for i in range(num_fireflies):
        size = random.uniform(2, 5)          
        start_x, start_y = random.uniform(0, 100), random.uniform(0, 100)      
        move_x, move_y = random.uniform(-20, 20), random.uniform(-20, 20)      
        duration, delay, pulse_dur = random.uniform(10, 25), random.uniform(0, 10), random.uniform(2, 5)     
        
        css_rules.append(f"""
        .firefly-{i} {{ position: absolute; width: {size}px; height: {size}px; left: {start_x}vw; top: {start_y}vh; background: #FFFFDF; border-radius: 50%; box-shadow: 0 0 {size*3}px {size}px rgba(255, 215, 0, 0.6); animation: drift-{i} {duration}s infinite ease-in-out {delay}s, flash-{i} {pulse_dur}s infinite ease-in-out {delay}s; opacity: 0; }}
        @keyframes drift-{i} {{ 0% {{ transform: translate(0px, 0px); }} 25% {{ transform: translate({move_x}vw, {move_y}vh); }} 50% {{ transform: translate({move_x/2}vw, {move_y*1.5}vh); }} 75% {{ transform: translate({-move_x}vw, {move_y/2}vh); }} 100% {{ transform: translate(0px, 0px); }} }}
        @keyframes flash-{i} {{ 0%, 100% {{ opacity: 0; }} 50% {{ opacity: {random.uniform(0.5, 1.0)}; }} }}
        """)
        html_divs.append(f"<div class='firefly-{i}'></div>")
    
    st.markdown(f"<style>.fireflies-container {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 1000; overflow: hidden; }} {''.join(css_rules)}</style><div class='fireflies-container'>{''.join(html_divs)}</div>", unsafe_allow_html=True)

def render_marquee():
    image_folder, image_files = "static", ["沙漠之城.png", "法人意向.png", "月影綠洲.png", "組合化學晶礦.png", "鐵風堡b.png"]
    total_images, time_per_slide = len(image_files), 5  
    total_time, visible_percent = total_images * time_per_slide, (1 / total_images) * 100 

    image_tags, delay_css = "", ""
    for i, img_name in enumerate(image_files):
        img_path = os.path.join(image_folder, img_name)
        img_base64 = get_cached_base64_image(img_path)
        if img_base64:
            image_tags += f'<img class="slide slide-{i}" src="{img_base64}">'
            delay_css += f"    .slide-{i} {{ animation-delay: {i * time_per_slide}s; }}\n"
        else:
            if os.path.exists(img_path): st.error(f"系統找不到圖片：{img_path}")

    st.markdown(f"""
    <style>
        .slideshow-container {{ position: relative; width: 800px; height: 100px; margin: 0 auto 10px auto; background-color: transparent; display: flex; justify-content: center; align-items: center; overflow: hidden; }}
        .slide {{ position: absolute; height: 100%; object-fit: contain; visibility: hidden; opacity: 0; animation: cut {total_time}s infinite; }}
        {delay_css}
        @keyframes cut {{ 0%, {visible_percent - 0.01:.2f}% {{ visibility: visible; opacity: 1; }} {visible_percent:.2f}%, 100% {{ visibility: hidden; opacity: 0; }} }}
    </style>
    <div class="slideshow-container">{image_tags}</div>
    """, unsafe_allow_html=True)
    
#跑馬燈懸浮卡片
#B2法人掃貨
def render_b2_top10_glass_card():
    if 'df_blk2_1' not in st.session_state: return
    try:
        raw_df_21 = st.session_state.get('df_blk2_1', pd.DataFrame()) 
        raw_df_22 = st.session_state.get('df_blk2_2', pd.DataFrame()) 
        raw_df_23 = st.session_state.get('df_blk2_3', pd.DataFrame()) 
        raw_df_24 = st.session_state.get('df_blk2_4', pd.DataFrame()) 
        def get_top10(df, target_col):
            if df is None or df.empty or target_col not in df.columns: return pd.DataFrame()
            df['股票代號'] = df['股票代號'].astype(str).str.strip()
            pure = df[(df['股票代號'].str.len() == 4) & (~df['股票代號'].str.startswith('00'))].copy()
            pure[target_col] = pd.to_numeric(pure[target_col], errors='coerce').fillna(0)
            return pure.sort_values(by=target_col, ascending=False).head(10)
        def get_col(df, kw):
            cols = [c for c in df.columns if kw in c]
            if not cols: return None, "未知"
            return cols[0], cols[0].replace(kw, "")
        c21, d21 = get_col(raw_df_21, "成交比%")
        c22, d22 = get_col(raw_df_22, "成交比%")
        c23, d23 = get_col(raw_df_23, "發行數%")
        c24, d24 = get_col(raw_df_24, "發行數%")
        df_21, df_22 = get_top10(raw_df_21, c21), get_top10(raw_df_22, c22)
        df_23, df_24 = get_top10(raw_df_23, c23), get_top10(raw_df_24, c24)
        def make_list_html(df, val_col):
            if df.empty or val_col is None: return "<p style='font-size:13.5px; text-align:center; color:#94A3B8; margin-top:40px;'>無資料</p>"
            html = "<ul style='padding-left: 0; margin: 0; list-style-type: none;'>"
            for i, row in enumerate(df.to_dict('records')):
                val = row.get(val_col, 0)
                cs = row.get('今日短動態', '').split('(')[0].strip()              
                if "轉賣反轉" in cs: short_status = "🚨轉賣"
                elif "卡位" in cs: short_status = "🆕卡位"
                elif "加碼" in cs: short_status = "🔥加碼"
                elif "強延續" in cs: short_status = "🔥強攻"
                elif "倒貨" in cs: short_status = "🚨倒貨"
                elif "調節" in cs: short_status = "📉調節"
                elif "持平" in cs: short_status = "🔄持平"
                elif "趨緩" in cs: short_status = "⚠️趨緩"
                else: short_status = cs[:3]
                html += (
                    f"<li style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; font-size: 13.5px; line-height: 1.4;'>"
                    f"  <div style='display: flex; align-items: center; width: 50%; overflow: hidden;'>"
                    f"      <b style='color:#FFF; width:22px; flex-shrink: 0;'>{i+1}.</b>"
                    f"      <span style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{row['股票代號']}{row['股票名稱']}</span>"
                    f"  </div>"
                    f"  <div style='width: 25%; color:#FFD700; font-size: 11px; text-align: right; white-space:nowrap;'>{short_status}</div>"
                    f"  <div style='width: 25%; color:#FF4C4C; font-weight:bold; text-align: right;'>{val:.1f}%</div>"
                    f"</li>"
                )
            html += "</ul>"
            return html
        h_21, h_22 = make_list_html(df_21, c21), make_list_html(df_22, c22)
        h_23, h_24 = make_list_html(df_23, c23), make_list_html(df_24, c24)
        card_html = f"""
<input type="checkbox" id="close-b2-card" style="display:none;">
<input type="checkbox" id="min-b2-card" style="display:none;">
<input type="checkbox" id="pause-b2-card" style="display:none;">
<style>
#close-b2-card:checked ~ #b2-top10-card {{ display: none !important; }}
#min-b2-card:checked ~ #b2-top10-card .carousel-wrapper-b2 {{ max-height: 0; opacity: 0; margin-top: 0; }}
#min-b2-card:checked ~ #b2-top10-card {{ padding-bottom: 8px; width: 150px; height: auto; }}
#min-b2-card:checked ~ #b2-top10-card .min-icon-b2::after {{ content: '□'; font-size: 14px; }}
#min-b2-card:not(:checked) ~ #b2-top10-card .min-icon-b2::after {{ content: '_'; font-size: 14px; position: relative; top: -3px; }}
#pause-b2-card:checked ~ #b2-top10-card .carousel-item-b2 {{ animation-play-state: paused !important; }}
#pause-b2-card:checked ~ #b2-top10-card .pause-icon-b2::after {{ content: '▶'; font-size: 11px; color: #FFD700; }}
#pause-b2-card:not(:checked) ~ #b2-top10-card .pause-icon-b2::after {{ content: '⏸'; font-size: 11px; }}
@keyframes slideInDownB2 {{ from {{ transform: translateY(-50%); opacity: 0; }} to {{ transform: translateY(0); opacity: 1; }} }}
.glass-panel-b2 {{position: fixed; top: 85px; left: 84.5vw; width: 15.5vw; min-width: 220px; background: rgba(30, 20, 20, 0.88); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255, 76, 76, 0.35); border-radius: 0 12px 12px 0; padding: 10px 12px; z-index: 999998; color: #E2E8F0; animation: slideInDownB2 0.9s cubic-bezier(0.25, 0.8, 0.25, 1); transition: all 0.3s ease; box-sizing: border-box; }}
.header-bar-b2 {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; margin-bottom: 8px; cursor: default; }}
.header-title-b2 {{ font-size: 13px; font-weight: bold; color: #FF7676; white-space:nowrap; }}
.action-btns-b2 {{ display: flex; gap: 8px; align-items: center; }}
.action-btn-b2 {{ cursor: pointer; color: #94A3B8; font-weight: bold; transition: color 0.2s; user-select: none; display: flex; align-items: center; justify-content: center; }}
.action-btn-b2:hover {{ color: #FF4C4C; }}
.panel-title-b2 {{ margin: 0 0 8px 0; font-size: 12.5px; font-weight: bold; color: #FF4C4C; display: flex; justify-content: space-between; align-items: flex-end; }}
.date-badge-b2 {{ font-size: 10px; color: #94A3B8; font-weight: normal; }}
.carousel-wrapper-b2 {{ position: relative; max-height: 285px; height: 285px; overflow: hidden; transition: all 0.3s ease; opacity: 1; }}
.carousel-item-b2 {{ position: absolute; top: 0; left: 0; width: 100%; opacity: 0; animation: fadeSwitchB2 20s infinite; }}
.carousel-item-b2:nth-child(1) {{ animation-delay: 0s; }}
.carousel-item-b2:nth-child(2) {{ animation-delay: 5s; }}
.carousel-item-b2:nth-child(3) {{ animation-delay: 10s; }}
.carousel-item-b2:nth-child(4) {{ animation-delay: 15s; }}
@keyframes fadeSwitchB2 {{ 0%, 22% {{ opacity: 1; z-index: 2; }} 25%, 97% {{ opacity: 0; z-index: 1; }} 100% {{ opacity: 1; z-index: 2; }} }}
@media (max-width: 1200px) {{ .glass-panel-b2 {{ position: relative; top: auto; left: auto; width: 90%; max-width: 350px; margin: 10px auto; display: block; }} }}
</style>
<div class="glass-panel-b2" id="b2-top10-card">
<div class="header-bar-b2"><span class="header-title-b2"><img src="app/static/magicbookwind.png" style="width:18px; margin-right:6px; vertical-align:-3px;" onerror="this.style.display='none'">法人掃貨</span>
<div class="action-btns-b2">
<label for="pause-b2-card" class="action-btn-b2 pause-icon-b2" title="暫停/播放輪播"></label>
<label for="min-b2-card" class="action-btn-b2 min-icon-b2" title="縮放"></label>
<label for="close-b2-card" class="action-btn-b2" title="關閉">✕</label>
</div></div>
<div class="carousel-wrapper-b2">
<div class="carousel-item-b2"><div class="panel-title-b2"><span>外資買超(成交%)</span><span class="date-badge-b2">{d21}</span></div>{h_21}</div>
<div class="carousel-item-b2"><div class="panel-title-b2"><span>投信買超(成交%)</span><span class="date-badge-b2">{d22}</span></div>{h_22}</div>
<div class="carousel-item-b2"><div class="panel-title-b2"><span>外資買超(發行%)</span><span class="date-badge-b2">{d23}</span></div>{h_23}</div>
<div class="carousel-item-b2"><div class="panel-title-b2"><span>投信買超(發行%)</span><span class="date-badge-b2">{d24}</span></div>{h_24}</div>
</div></div>
"""
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e: pass

#B3法人連買
def render_top10_glass_card():
    if 'b3_data' not in st.session_state: return
    try:
        raw_fo_day_df, date_fo_day = st.session_state['b3_data']['fo_day']
        raw_it_day_df, date_it_day = st.session_state['b3_data']['it_day']
        raw_fo_wk_df, date_fo_wk = st.session_state['b3_data']['fo_wk']
        raw_it_wk_df, date_it_wk = st.session_state['b3_data']['it_wk']

        def get_top10(df):
            if df is None or df.empty: return pd.DataFrame()
            df['股票代號'] = df['股票代號'].astype(str).str.strip()
            return df[(df['股票代號'].str.len() == 4) & (~df['股票代號'].str.startswith('00'))].head(10) 
        fo_day_df, it_day_df = get_top10(raw_fo_day_df), get_top10(raw_it_day_df)
        fo_wk_df, it_wk_df = get_top10(raw_fo_wk_df), get_top10(raw_it_wk_df)

        fmt_d = lambda d: d[-4:] if (d and d != "00000000") else "未知"
        d_fo_day, d_it_day, d_fo_wk, d_it_wk = fmt_d(date_fo_day), fmt_d(date_it_day), fmt_d(date_fo_wk), fmt_d(date_it_wk)

        def make_list_html(df, col_days, unit):
            if df is None or df.empty: return "<p style='font-size:13.5px; text-align:center; color:#94A3B8; margin-top:40px;'>無資料</p>"
            html = "<ul style='padding-left: 0px; margin: 0; list-style-type: none;'>"
            for i, row in enumerate(df.to_dict('records')):
                val, status = row.get(col_days, 0), row.get('狀態動態', '')
                html += (
                    f"<li style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; font-size: 13.5px; line-height: 1.4;'>"
                    f"<div style='display:flex; width:55%; overflow:hidden;'>"
                    f"<b style='color:#FFF; display:inline-block; width:22px; flex-shrink:0;'>{i+1}.</b>"
                    f"<span style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{row['股票代號']}{row['股票名稱']}</span>"
                    f"</div>"
                    f"<div style='width:45%; text-align:right; white-space:nowrap;'>"
                    f"<span style='color:#FFD700; font-size: 11px; margin-right:4px;'>{status}</span>"
                    f"<span style='color:#00D2FF; font-weight:bold;'>{val}{unit}</span>"
                    f"</div></li>"
                )
            html += "</ul>"
            return html

        fo_day_html, it_day_html = make_list_html(fo_day_df, "最新連買天數", "天"), make_list_html(it_day_df, "最新連買天數", "天")
        fo_wk_html, it_wk_html = make_list_html(fo_wk_df, "最新連買週數", "週"), make_list_html(it_wk_df, "最新連買週數", "週")
        card_html = f"""
<input type="checkbox" id="close-card" style="display:none;">
<input type="checkbox" id="min-card" style="display:none;">
<input type="checkbox" id="pause-card" style="display:none;">
<style>
#close-card:checked ~ #b3-top10-card {{ display: none !important; }}
#min-card:checked ~ #b3-top10-card .carousel-wrapper {{ max-height: 0; opacity: 0; margin-top: 0; }}
#min-card:checked ~ #b3-top10-card {{ padding-bottom: 8px; width: 150px; height: auto; }}
#min-card:checked ~ #b3-top10-card .min-icon::after {{ content: '□'; font-size: 14px; }}
#min-card:not(:checked) ~ #b3-top10-card .min-icon::after {{ content: '_'; font-size: 14px; position: relative; top: -3px; }}
#pause-card:checked ~ #b3-top10-card .carousel-item {{ animation-play-state: paused !important; }}
#pause-card:checked ~ #b3-top10-card .pause-icon::after {{ content: '▶'; font-size: 11px; color: #FFD700; }}
#pause-card:not(:checked) ~ #b3-top10-card .pause-icon::after {{ content: '⏸'; font-size: 11px; }}
@keyframes slideInDownB3 {{ from {{ transform: translateY(-50%); opacity: 0; }} to {{ transform: translateY(0); opacity: 1; }} }}
/* 💡 將 top: 75px 改為 top: 100px */
.glass-panel {{position: fixed; top: 85px; left: 69vw; width: 15.5vw; min-width: 220px; background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(0, 210, 255, 0.35); border-right: none; border-radius: 0; padding: 10px 12px; z-index: 999999; color: #E2E8F0; animation: slideInDownB3 0.8s cubic-bezier(0.25, 0.8, 0.25, 1); transition: all 0.3s ease; box-sizing: border-box;}}
.header-bar {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; margin-bottom: 8px; cursor: default; }}
.header-title {{ font-size: 13px; font-weight: bold; color: #64748B; white-space:nowrap; }}
.action-btns {{ display: flex; gap: 8px; align-items: center; }}
.action-btn {{ cursor: pointer; color: #94A3B8; font-weight: bold; transition: color 0.2s; user-select: none; display: flex; align-items: center; justify-content: center; }}
.action-btn:hover {{ color: #00D2FF; }}
.close-btn:hover {{ color: #FF4C4C; }}
.panel-title {{ margin: 0 0 8px 0; font-size: 12.5px; font-weight: bold; color: #00D2FF; display: flex; justify-content: space-between; align-items: flex-end; }}
.date-badge {{ font-size: 10px; color: #94A3B8; font-weight: normal; }}
.carousel-wrapper {{ position: relative; max-height: 285px; height: 285px; overflow: hidden; transition: all 0.3s ease; opacity: 1; }}
.carousel-item {{ position: absolute; top: 0; left: 0; width: 100%; opacity: 0; animation: fadeSwitch 20s infinite; }}
.carousel-item:nth-child(1) {{ animation-delay: 0s; }}
.carousel-item:nth-child(2) {{ animation-delay: 5s; }}
.carousel-item:nth-child(3) {{ animation-delay: 10s; }}
.carousel-item:nth-child(4) {{ animation-delay: 15s; }}
@keyframes fadeSwitch {{ 0%, 22% {{ opacity: 1; z-index: 2; }} 25%, 97% {{ opacity: 0; z-index: 1; }} 100% {{ opacity: 1; z-index: 2; }} }}
@media (max-width: 1200px) {{ .glass-panel {{ position: relative; top: auto; left: auto; width: 90%; max-width: 350px; margin: 10px auto; display: block; }} }}
</style>
<div class="glass-panel" id="b3-top10-card">
<div class="header-bar"><span class="header-title"><img src="app/static/magicbookwater.png" style="width:18px; margin-right:6px; vertical-align:-3px;" onerror="this.style.display='none'"> 法人連買</span>
<div class="action-btns">
<label for="pause-card" class="action-btn pause-icon" title="暫停/播放輪播"></label>
<label for="min-card" class="action-btn min-icon" title="縮放"></label>
<label for="close-card" class="action-btn close-btn" title="關閉">✕</label>
</div></div>
<div class="carousel-wrapper">
<div class="carousel-item"><div class="panel-title"><span>外資日連買</span><span class="date-badge">{d_fo_day}</span></div>{fo_day_html}</div>
<div class="carousel-item"><div class="panel-title"><span>投信日連買</span><span class="date-badge">{d_it_day}</span></div>{it_day_html}</div>
<div class="carousel-item"><div class="panel-title"><span>外資週連買</span><span class="date-badge">{d_fo_wk}</span></div>{fo_wk_html}</div>
<div class="carousel-item"><div class="panel-title"><span>投信週連買</span><span class="date-badge">{d_it_wk}</span></div>{it_wk_html}</div>
</div></div>
"""
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e: pass  

#b4 資券玻璃卡片
def render_b4_top10_glass_card():
    if 'b4_squeeze_radar' not in st.session_state or 'b4_risk_radar' not in st.session_state: return
    try:
        sq_data, rk_data = st.session_state['b4_squeeze_radar'], st.session_state['b4_risk_radar']
        df_sq, df_rk = sq_data['df'], rk_data['df']
        date_sq = sq_data['date'][-4:] if sq_data['date'] and len(sq_data['date']) >= 4 else "未知"
        date_rk = rk_data['date'][-4:] if rk_data['date'] and len(rk_data['date']) >= 4 else "未知"
        def get_pure_radar_stocks(df):
            if df is None or df.empty: return pd.DataFrame()
            df['代號'] = df['代號'].astype(str).str.strip()
            return df[(df['代號'].str.len() == 4) & (~df['代號'].str.startswith('00'))].copy()
        pure_sq, pure_rk = get_pure_radar_stocks(df_sq).head(20), get_pure_radar_stocks(df_rk).head(20)
        def make_radar_html(df, start_idx, theme):
            sub_df = df.iloc[start_idx : start_idx+10]
            if sub_df.empty: return "<p style='font-size:13.5px; text-align:center; color:#94A3B8; margin-top:40px;'>尚無目標</p>"
            html = "<ul style='padding-left: 0; margin: 0; list-style-type: none;'>"
            for i, row in enumerate(sub_df.to_dict('records')):
                status = row.get('軋空評估', '') if theme == 'sq' else row.get('套牢評估', '')
                pct = row.get('漲跌幅', 0.0)
                short_status = status[:7] if len(status) > 7 else status
                pct_color = "#FF4C4C" if theme == 'sq' else "#00e676"                
                html += (
                    f"<li style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; font-size: 13.5px; line-height: 1.4;'>"
                    f"  <div style='display: flex; align-items: center; width: 55%; overflow: hidden;'>"
                    f"      <b style='color:#FFF; width:22px; flex-shrink: 0;'>{start_idx + i + 1}.</b>"
                    f"      <span style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{row['代號']}{row['名稱']}</span>"
                    f"  </div>"
                    f"  <div style='width: 25%; color:#FFD700; font-size: 11px; text-align: left; white-space:nowrap;'>{short_status}</div>"
                    f"  <div style='width: 20%; color:{pct_color}; font-weight:bold; text-align: right;'>{pct}%</div>"
                    f"</li>"
                )
            html += "</ul>"
            return html
        h_sq_1_10, h_sq_11_20 = make_radar_html(pure_sq, 0, 'sq'), make_radar_html(pure_sq, 10, 'sq')
        h_rk_1_10, h_rk_11_20 = make_radar_html(pure_rk, 0, 'rk'), make_radar_html(pure_rk, 10, 'rk')

        card_html = f"""
<input type="checkbox" id="close-b4-card" style="display:none;">
<input type="checkbox" id="min-b4-card" style="display:none;">
<input type="checkbox" id="pause-b4-card" style="display:none;">
<style>
#close-b4-card:checked ~ #b4-top10-card {{ display: none !important; }}
#min-b4-card:checked ~ #b4-top10-card .carousel-wrapper-b4 {{ max-height: 0; opacity: 0; margin-top: 0; }}
#min-b4-card:checked ~ #b4-top10-card {{ padding-bottom: 8px; width: 150px; height: auto; }}
#min-b4-card:checked ~ #b4-top10-card .min-icon-b4::after {{ content: '□'; font-size: 14px; }}
#min-b4-card:not(:checked) ~ #b4-top10-card .min-icon-b4::after {{ content: '_'; font-size: 14px; position: relative; top: -3px; }}
#pause-b4-card:checked ~ #b4-top10-card .carousel-item-b4 {{ animation-play-state: paused !important; }}
#pause-b4-card:checked ~ #b4-top10-card .pause-icon-b4::after {{ content: '▶'; font-size: 11px; color: #FFD700; }}
#pause-b4-card:not(:checked) ~ #b4-top10-card .pause-icon-b4::after {{ content: '⏸'; font-size: 11px; }}
@keyframes slideInDownB4 {{ from {{ transform: translateY(-50%); opacity: 0; }} to {{ transform: translateY(0); opacity: 1; }} }}
@keyframes radarBreath {{ 0%, 49.9% {{ border-color: rgba(188, 19, 254, 0.4); box-shadow: 0 4px 15px rgba(188, 19, 254, 0.15); }} 50%, 100% {{ border-color: rgba(0, 230, 118, 0.4); box-shadow: 0 4px 15px rgba(0, 230, 118, 0.1); }} }}
/* 💡 將 top: 75px 改為 top: 100px */
.glass-panel-b4 {{ position: fixed; top: 85px; left: 38vw; width: 15.5vw; min-width: 220px; background: rgba(20, 22, 35, 0.88); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(188, 19, 254, 0.35); border-right: none; border-radius: 12px 0 0 12px; padding: 10px 12px; z-index: 999997; color: #E2E8F0;animation: slideInDownB4 0.6s cubic-bezier(0.25, 0.8, 0.25, 1);     transition: all 0.3s ease; box-sizing: border-box; }}
.header-bar-b4 {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; margin-bottom: 8px; cursor: default; }}
.header-title-b4 {{ font-size: 13px; font-weight: bold; color: #E2E8F0; white-space:nowrap; }}
.action-btns-b4 {{ display: flex; gap: 8px; align-items: center; }}
.action-btn-b4 {{ cursor: pointer; color: #94A3B8; font-weight: bold; transition: color 0.2s; user-select: none; display: flex; align-items: center; justify-content: center; }}
.action-btn-b4:hover {{ color: #00D2FF; }}
.panel-title-b4 {{ margin: 0 0 8px 0; font-size: 12.5px; font-weight: bold; color: #bc13fe; display: flex; justify-content: space-between; align-items: flex-end; }}
.panel-title-b4.risk {{ color: #00e676; }}
.date-badge-b4 {{ font-size: 10px; color: #94A3B8; font-weight: normal; }}
.carousel-wrapper-b4 {{ position: relative; max-height: 285px; height: 285px; overflow: hidden; transition: all 0.3s ease; opacity: 1; }}
.carousel-item-b4 {{ position: absolute; top: 0; left: 0; width: 100%; opacity: 0; animation: fadeSwitchB4 20s infinite; }}
.carousel-item-b4:nth-child(1) {{ animation-delay: 0s; }}
.carousel-item-b4:nth-child(2) {{ animation-delay: 5s; }}
.carousel-item-b4:nth-child(3) {{ animation-delay: 10s; }}
.carousel-item-b4:nth-child(4) {{ animation-delay: 15s; }}
@keyframes fadeSwitchB4 {{ 0%, 22% {{ opacity: 1; z-index: 2; }} 25%, 97% {{ opacity: 0; z-index: 1; }} 100% {{ opacity: 1; z-index: 2; }} }}
@media (max-width: 1200px) {{ .glass-panel-b4 {{ position: relative; top: auto; left: auto; width: 90%; max-width: 350px; margin: 10px auto; display: block; }} }}
</style>
<div class="glass-panel-b4" id="b4-top10-card">
<div class="header-bar-b4"><span class="header-title-b4"><img src="app/static/magicbookground.png" style="width:18px; margin-right:6px; vertical-align:-3px;" onerror="this.style.display='none'">資券雷達</span>
<div class="action-btns-b4">
<label for="pause-b4-card" class="action-btn-b4 pause-icon-b4" title="暫停/播放輪播"></label>
<label for="min-b4-card" class="action-btn-b4 min-icon-b4" title="縮放"></label>
<label for="close-b4-card" class="action-btn-b4" title="關閉">✕</label>
</div></div>
<div class="carousel-wrapper-b4">
<div class="carousel-item-b4"><div class="panel-title-b4"><span>軋空(1-10)</span><span class="date-badge-b4">{date_sq}</span></div>{h_sq_1_10}</div>
<div class="carousel-item-b4"><div class="panel-title-b4"><span>軋空(11-20)</span><span class="date-badge-b4">{date_sq}</span></div>{h_sq_11_20}</div>
<div class="carousel-item-b4"><div class="panel-title-b4 risk"><span>套牢(1-10)</span><span class="date-badge-b4">{date_rk}</span></div>{h_rk_1_10}</div>
<div class="carousel-item-b4"><div class="panel-title-b4 risk"><span>套牢(11-20)</span><span class="date-badge-b4">{date_rk}</span></div>{h_rk_11_20}</div>
</div></div>
"""
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e: pass  

#B5 大腿動向玻璃卡片
def render_b5_top10_glass_card():
    if 'b5_1000' not in st.session_state or 'b5_400' not in st.session_state: return
    try:
        df_1000, df_400 = st.session_state['b5_1000'], st.session_state['b5_400']
        if df_1000.empty or df_400.empty: return
        latest_col_1000 = next((c for c in df_1000.columns if c.startswith('▼') and '6周' not in c), None)
        latest_col_400 = next((c for c in df_400.columns if c.startswith('▼') and '6周' not in c), None)
        if not latest_col_1000 or not latest_col_400: return
        date_str = latest_col_1000.replace('▼', '') 

        def get_pure(df):
            df['股票代號'] = df['股票代號'].astype(str).str.strip()
            return df[(df['股票代號'].str.len() == 4) & (~df['股票代號'].str.startswith('00'))].copy()
        df_1k_sub = get_pure(df_1000)[['股票代號', '股票名稱', '週動態', '▼6周增減', latest_col_1000]].copy()
        df_1k_sub = df_1k_sub.rename(columns={'▼6周增減': '6周(千)', latest_col_1000: '最新(千)', '週動態': '狀態(千)'})
        df_400_sub = get_pure(df_400)[['股票代號', '週動態', '▼6周增減', latest_col_400]].copy()
        df_400_sub = df_400_sub.rename(columns={'▼6周增減': '6周(四)', latest_col_400: '最新(四)', '週動態': '狀態(四)'})

        sync_df = pd.merge(df_1k_sub, df_400_sub, on='股票代號', how='inner')
        for col in ['6周(千)', '最新(千)', '6周(四)', '最新(四)']:
            sync_df[f"{col}_val"] = pd.to_numeric(sync_df[col].astype(str).str.replace('+', '', regex=False).str.replace('%', '', regex=False), errors='coerce').fillna(0)
        cond_6w = (sync_df['6周(千)_val'] > 0) & (sync_df['6周(四)_val'] > 0)
        top10_6w = sync_df[cond_6w].sort_values(by='6周(千)_val', ascending=False).head(10)
        cond_latest = (sync_df['最新(千)_val'] > 0) & (sync_df['最新(四)_val'] > 0)
        top10_latest = sync_df[cond_latest].sort_values(by='最新(千)_val', ascending=False).head(10)

        def unify_status_text(s):
            s = str(s)
            if "🚀" in s: return "🚀劇增"
            if "🔥" in s: return "🔥大增"
            if "📈" in s: return "📈小增"
            if "↗️" in s: return "↗️微增"
            if "🔄" in s: return "🔄持平"
            if "↘️" in s: return "↘️微減"
            if "📉" in s: return "📉小減"
            if "⚠️" in s: return "⚠️大減"
            if "🚨" in s: return "🚨劇減"
            return "⚪無字"

        def make_resonance_html(df, is_6w):
            if df.empty: return "<p style='font-size:13.5px; text-align:center; color:#94A3B8; margin-top:40px;'>尚無共振標的</p>"
            html = "<ul style='padding-left: 0; margin: 0; list-style-type: none;'>"
            for i, row in enumerate(df.to_dict('records')):
                if is_6w:
                    v1, v2 = row['6周(千)_val'], row['6周(四)_val']
                    # 💡 修改1：字體加大至 13.5px (對齊B4)，並加入 flex-shrink: 0 確保數值區塊絕對不會被擠壓換行
                    info_html = f"<div style='display:flex; justify-content:flex-end; align-items:center; color:#F59E0B; font-weight:bold; font-size:13.5px; white-space:nowrap; flex-shrink:0;'><span style='width:48px; text-align:right;'>{v1:.1f}%</span><span style='color:#94A3B8; font-size:13.5px; margin:0 3px;'>/</span><span style='width:48px; text-align:right;'>{v2:.1f}%</span></div>"
                else:
                    s1, s2 = unify_status_text(row.get('狀態(千)', '')), unify_status_text(row.get('狀態(四)', ''))
                    # 💡 修改2：狀態文字加大至 11px (對齊B4)，同樣設定 flex-shrink: 0
                    info_html = f"<div style='display:flex; justify-content:flex-end; align-items:center; color:#F59E0B; font-size:11px; white-space:nowrap; flex-shrink:0;'><span style='width:48px; text-align:right;'>{s1}</span><span style='color:#94A3B8; font-size:11px; margin:0 3px;'>/</span><span style='width:48px; text-align:right;'>{s2}</span></div>"
                    
                html += (
                    f"<li style='display:flex; align-items:center; justify-content:space-between; margin-bottom:6px; font-size:13.5px; line-height:1.4;'>"
                    # 💡 修改3：左側股票區塊捨棄 width:50%，改用 flex:1 自動吃掉剩餘空間，加上 margin-right 稍微拉近數值間距，避免文字跑到下一行
                    f"  <div style='display:flex; align-items:center; flex:1; overflow:hidden; margin-right:8px;'>"
                    f"      <b style='color:#FFF; width:22px; flex-shrink:0;'>{i+1}.</b>"
                    f"      <span style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{row['股票代號']}{row['股票名稱']}</span>"
                    f"  </div>{info_html}</li>"
                )
            html += "</ul>"
            return html

        h_6w, h_latest = make_resonance_html(top10_6w, True), make_resonance_html(top10_latest, False)
        card_html = f"""
<input type="checkbox" id="close-b5-card" style="display:none;">
<input type="checkbox" id="min-b5-card" style="display:none;">
<input type="checkbox" id="pause-b5-card" style="display:none;">
<style>
#close-b5-card:checked ~ #b5-top10-card {{ display: none !important; }}
#min-b5-card:checked ~ #b5-top10-card .carousel-wrapper-b5 {{ max-height: 0; opacity: 0; margin-top: 0; }}
#min-b5-card:checked ~ #b5-top10-card {{ padding-bottom: 8px; width: 150px; height: auto; }}
#min-b5-card:checked ~ #b5-top10-card .min-icon-b5::after {{ content: '□'; font-size: 14px; }}
#min-b5-card:not(:checked) ~ #b5-top10-card .min-icon-b5::after {{ content: '_'; font-size: 14px; position: relative; top: -3px; }}
#pause-b5-card:checked ~ #b5-top10-card .carousel-item-b5 {{ animation-play-state: paused !important; }}
#pause-b5-card:checked ~ #b5-top10-card .pause-icon-b5::after {{ content: '▶'; font-size: 11px; color: #FFD700; }}
#pause-b5-card:not(:checked) ~ #b5-top10-card .pause-icon-b5::after {{ content: '⏸'; font-size: 11px; }}
@keyframes slideInDownB5 {{ from {{ transform: translateY(-50%); opacity: 0; }} to {{ transform: translateY(0); opacity: 1; }} }}
.glass-panel-b5 {{position: fixed; top: 85px; left: 53.5vw; width: 15.5vw; min-width: 220px; background: rgba(30, 25, 10, 0.88); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(245, 158, 11, 0.4); border-right: none; border-radius: 0; padding: 10px 12px; z-index: 999996; color: #E2E8F0; animation: slideInDownB5 0.7s cubic-bezier(0.25, 0.8, 0.25, 1); transition: all 0.3s ease; box-sizing: border-box;}}
.header-bar-b5 {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; margin-bottom: 8px; cursor: default; }}
.header-title-b5 {{ font-size: 13px; font-weight: bold; color: #FCD34D; white-space:nowrap; }}
.action-btns-b5 {{ display: flex; gap: 8px; align-items: center; }}
.action-btn-b5 {{ cursor: pointer; color: #94A3B8; font-weight: bold; transition: color 0.2s; user-select: none; display: flex; align-items: center; justify-content: center; }}
.action-btn-b5:hover {{ color: #F59E0B; }}
.panel-title-b5 {{ margin: 0 0 8px 0; font-size: 12.5px; font-weight: bold; color: #F59E0B; display: flex; justify-content: space-between; align-items: flex-end; }}
.date-badge-b5 {{ font-size: 10px; color: #94A3B8; font-weight: normal; }}
.carousel-wrapper-b5 {{ position: relative; max-height: 285px; height: 285px; overflow: hidden; transition: all 0.3s ease; opacity: 1; }}
.carousel-item-b5 {{ position: absolute; top: 0; left: 0; width: 100%; opacity: 0; animation: fadeSwitchB5 10s infinite; }}
.carousel-item-b5:nth-child(1) {{ animation-delay: 0s; }}
.carousel-item-b5:nth-child(2) {{ animation-delay: 5s; }}
@keyframes fadeSwitchB5 {{ 0%, 45% {{ opacity: 1; z-index: 2; }} 50%, 95% {{ opacity: 0; z-index: 1; }} 100% {{ opacity: 1; z-index: 2; }} }}
@media (max-width: 1200px) {{ .glass-panel-b5 {{ position: relative; top: auto; left: auto; width: 90%; max-width: 350px; margin: 10px auto; display: block; }} }}
</style>
<div class="glass-panel-b5" id="b5-top10-card">
<div class="header-bar-b5"><span class="header-title-b5"><img src="app/static/wirtleg.png" style="width:18px; margin-right:6px; vertical-align:-3px;" onerror="this.style.display='none'">大腿共振</span>
<div class="action-btns-b5">
<label for="pause-b5-card" class="action-btn-b5 pause-icon-b5" title="暫停/播放輪播"></label>
<label for="min-b5-card" class="action-btn-b5 min-icon-b5" title="縮放"></label>
<label for="close-b5-card" class="action-btn-b5" title="關閉">✕</label>
</div></div>
<div class="carousel-wrapper-b5">
<div class="carousel-item-b5"><div class="panel-title-b5"><span>6周累積(1000/400)</span><span class="date-badge-b5">{date_str}</span></div>{h_6w}</div>
<div class="carousel-item-b5"><div class="panel-title-b5"><span>本週動能(1000/400)</span><span class="date-badge-b5">{date_str}</span></div>{h_latest}</div>
</div></div>
"""
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e: pass

# ==========================================
# 🎓 課程 NPC 懸浮對話框 
# ==========================================
# 💡 效能救星：讓按鈕與課程選單變成獨立的網頁，完全不干擾 B1~B7 的運作！
@st.fragment
def render_course_npc():
    if not st.session_state.get('show_course_npc', False): return
    if 'course_view' not in st.session_state:
        st.session_state['course_view'] = 'list'
        
    current_view = st.session_state['course_view']
    
    common_css = """<style>
/* --- 桌面版預設樣式 --- */
.npc-overlay {
    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); 
    width: 90vw; max-width: 800px; height: 85vh; max-height: 900px;
    background: rgba(15, 23, 42, 0.98); border: 2px solid #00D2FF; border-radius: 12px;
    z-index: 9999999; display: flex; flex-direction: column; padding: 25px;
    box-shadow: 0 8px 30px rgba(0, 210, 255, 0.4); color: white;
    animation: fadeInScale 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.1); box-sizing: border-box;
}
@keyframes fadeInScale { from { transform: translate(-50%, -45%) scale(0.9); opacity: 0; } to { transform: translate(-50%, -50%) scale(1); opacity: 1; } }

/* 頂部按鈕與標題區 */
.top-actions { position: absolute; top: 15px; right: 20px; display: flex; gap: 12px; z-index: 10; }
.action-btn { cursor: pointer; color: #94A3B8; font-size: 20px; font-weight:bold; transition: 0.2s; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.5); width: 32px; height: 32px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.1); }
.action-btn:hover { background: rgba(0,210,255,0.3); color: #FFF; transform: scale(1.1); border-color: #00D2FF; }
.action-btn.close:hover { background: rgba(255,76,76,0.8); border-color: #FF4C4C; }
.detail-header, .npc-header { display: flex; align-items: flex-end; margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px; gap: 20px; }

/* 圖片與對話框 */
.npc-big-image { width: 140px; height: 160px; background-size: contain; background-repeat: no-repeat; background-position: bottom; filter: drop-shadow(0 0 10px rgba(0,210,255,0.6)); flex-shrink: 0; }
.dialogue-box { flex: 1; background: rgba(0, 210, 255, 0.08); border: 1px solid rgba(0, 210, 255, 0.3); border-radius: 12px; padding: 18px; position: relative; margin-bottom: 10px; }
.dialogue-box::before { content: ''; position: absolute; left: -14px; bottom: 30px; border-width: 12px 14px 12px 0; border-style: solid; border-color: transparent rgba(0, 210, 255, 0.3) transparent transparent; }
.npc-name { color: #00D2FF; font-weight: bold; font-size: 20px; margin-bottom: 8px; }
.npc-text { font-size: 15px; color: #E2E8F0; line-height: 1.6; }

/* 滾動內容區與表格 */
.table-container, .course-list { flex: 1; overflow-y: auto; padding-right: 10px; overflow-x: hidden; }
.table-container::-webkit-scrollbar, .course-list::-webkit-scrollbar { width: 6px; }
.table-container::-webkit-scrollbar-thumb, .course-list::-webkit-scrollbar-thumb { background: rgba(0, 210, 255, 0.4); border-radius: 3px; }
.pv-table { width: 100%; border-collapse: collapse; font-size: 14px; text-align: center; margin-bottom: 15px; }
.pv-table th { background: rgba(0, 210, 255, 0.15); color: #00D2FF; padding: 10px; border-bottom: 2px solid #00D2FF; font-weight: bold; }
.pv-table td { padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #CBD5E1; }
.pv-table tr:hover td { background: rgba(255,255,255,0.05); color: #FFF; }
.section-title { color: #00D2FF; font-size: 16px; font-weight: bold; margin: 15px 0 8px 0; border-left: 4px solid #00D2FF; padding-left: 8px; }

/* 課程列表項目 */
.course-item { margin-bottom: 15px; padding: 15px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; transition: 0.2s; cursor: pointer; }
.course-item:hover { background: rgba(0, 210, 255, 0.1); border-color: #00D2FF; transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,210,255,0.2); }
.course-title { color: #FFD700; font-weight: bold; font-size: 16px; margin-bottom: 8px; display: flex; align-items: center; }
.course-icon { width: 24px; height: 24px; object-fit: contain; margin-right: 8px; filter: drop-shadow(0 0 5px rgba(0,210,255,0.8)); transition: 0.3s; }
.course-desc { font-size: 13.5px; color: #CBD5E1; line-height: 1.5; }

/* 特定元素樣式 */
.info-box { background: rgba(0, 210, 255, 0.05); border: 1px solid rgba(0, 210, 255, 0.2); border-radius: 8px; padding: 12px; margin-bottom: 15px; font-size: 14px; color: #CBD5E1; line-height: 1.6; }
.tree-node { background: rgba(0, 210, 255, 0.15); border: 1px solid #00D2FF; color: white; padding: 6px 12px; border-radius: 8px; font-weight: bold; }
.trend-up { color: #FF4C4C; font-weight: bold; } .trend-down { color: #00E676; font-weight: bold; } .trend-flat { color: #FFD700; font-weight: bold; }

/* --- 📱 手機版 RWD 優化 --- */
@media (max-width: 768px) {
    .npc-overlay { width: 95vw; height: 90vh; padding: 15px; }
    .detail-header { flex-direction: column; align-items: center; text-align: center; gap: 10px; padding-bottom: 10px; }
    .npc-big-image { width: 90px; height: 100px; margin-bottom: 0px; }
    .dialogue-box { width: 100%; padding: 12px; }
    .dialogue-box::before { display: none; }
    .pv-table { font-size: 12px; }
    .pv-table th, .pv-table td { padding: 6px 4px; }
    .top-actions { top: 8px; right: 8px; gap: 8px; }
    .action-btn { width: 28px; height: 28px; font-size: 16px; }
    .npc-name { font-size: 18px; }
    .npc-text { font-size: 14px; }
    .section-title { font-size: 15px; }
    .info-box { font-size: 13px; padding: 10px; }
}
</style>"""

    html_code = ""

    if current_view == 'list':
        html_code = f"""{common_css}
<div class="npc-overlay">
<div class="top-actions"><label class="action-btn close" id="btn-close-list" title="關閉">✕</label></div>
<div class="npc-header">
<div class="npc-big-image" style="background-image: url('app/static/npcnatzu.png');"></div>
<div class="dialogue-box">
<div class="npc-name">籌碼導師</div>
<div class="npc-text">「冒險者，選擇你想強化的能力吧！」</div>
</div>
</div>
<div class="course-list">
<div class="course-item" id="btn-open-course-1"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 1. 宏觀經濟與景氣循環</div><div class="course-desc">學習解讀 GDP、CPI、利率與匯率等基本指標，判斷大盤景氣階段。</div></div>
<div class="course-item" id="btn-open-course-2"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 2. 股市基本架構與名詞解析</div><div class="course-desc">認識台股交易規則、各類委託單與基本盤面術語。</div></div>
<div class="course-item" id="btn-open-course-3"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 3. 財報與基本面入門</div><div class="course-desc">學習閱讀三大財務報表，挑選具備長期競爭力的公司。</div></div>
<div class="course-item" id="btn-open-course-4"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 4. 量價關係與盤面解讀</div><div class="course-desc">對照成交量與股價互動，判斷多空雙方的企圖心與買賣力道。</div></div>
<div class="course-item" id="btn-open-course-5"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 5. 技術分析與指標應用</div><div class="course-desc">熟悉常用技術指標(MA, MACD, RSI, KDJ, BBW)，掌握趨勢轉折。</div></div>
<div class="course-item" id="btn-open-course-6"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 6. 籌碼面追蹤：法人與大戶結構</div><div class="course-desc">認識外資、投信、自營商大戶持股，觀察資金集中或分散。</div></div>
<div class="course-item" id="btn-open-course-7"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 7. 券資關係與融資融券分析</div><div class="course-desc">觀察融資餘額與券資比，評估市場潛在「軋空」或「多殺多」。</div></div>
<div class="course-item" id="btn-open-course-8"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 8. 產業趨勢與題材選股</div><div class="course-desc">掌握主流產業輪動脈絡，佈局具備成長爆發力的賽道。</div></div>
<div class="course-item" id="btn-open-course-9"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 9. 資金控管與風險管理</div><div class="course-desc">學習部位配置、分批進場與停損機制，避免重大虧損。</div></div>
<div class="course-item" id="btn-open-course-10"><div class="course-title"><img src="app/static/icon-course1.png" class="course-icon">Lv 10. 交易心理學與個人策略總結</div><div class="course-desc">克服貪婪與恐懼，建立專屬於自己的穩定獲利交易系統。</div></div>
</div>
</div>"""

    elif current_view.startswith('detail_'):
        courses_data = {
            'detail_1': {
                'npc': '蘿西', 'img': 'npcroxy.png', 'text': '「冒險者注意！經濟並不是永遠上升，而是不斷『🟢 復甦 → 擴張 → 過熱 → 放緩 → 衰退』的循環。現在的市場環境，究竟該積極、觀望，還是提高風險意識？讓我們從總體經濟數據中找答案吧！」',
                'html': """<div class="section-title">📊 總體經濟關鍵指標解析</div>
<table class="pv-table"><thead><tr><th width="15%">指標</th><th width="35%">主要觀察什麼</th><th width="50%">上升通常代表對市場的影響</th></tr></thead>
<tbody><tr><td><b>GDP</b></td><td style="text-align:left;">經濟成長速度</td><td style="text-align:left;">經濟活動增加 🟢 景氣可能擴張</td></tr><tr><td><b>CPI</b></td><td style="text-align:left;">物價與通膨</td><td style="text-align:left;">生活成本上升 🟠 可能增加升息壓力</td></tr><tr><td><b>利率</b></td><td style="text-align:left;">資金成本</td><td style="text-align:left;">借錢成本提高 🔴 股市估值可能承壓</td></tr><tr><td><b>匯率</b></td><td style="text-align:left;">貨幣強弱</td><td style="text-align:left;">資金與出口環境變化 🟡 需搭配產業判讀</td></tr></tbody></table>
<div class="section-title">⚡ 景氣循環核心狀態對照</div>
<table class="pv-table"><thead><tr><th width="30%">景氣狀態</th><th width="40%">核心數據表現</th><th width="30%">市場含義</th></tr></thead>
<tbody><tr><td style="color:#4ADE80; font-weight:bold;">🟢 景氣復甦</td><td>GDP↑ / CPI→ / 利率低</td><td style="text-align:left;">景氣回升，初升段</td></tr><tr><td style="color:#4ADE80; font-weight:bold;">🟢 經濟擴張</td><td>GDP↑↑ / 企業活動↑</td><td style="text-align:left;">多頭主升段延續</td></tr><tr><td style="color:#FB923C; font-weight:bold;">🟠 景氣過熱</td><td>GDP↑ / CPI↑↑ / 利率↑</td><td style="text-align:left;">通膨升溫，注意緊縮</td></tr><tr><td style="color:#F87171; font-weight:bold;">🔴 經濟放緩</td><td>GDP↓ / 消費↓</td><td style="text-align:left;">動能減弱，防守為主</td></tr><tr><td style="color:#EF4444; font-weight:bold;">🚨 經濟衰退</td><td>GDP↓↓ / 失業↑</td><td style="text-align:left;">熊市風險，資金避險</td></tr></tbody></table>"""
            },
            'detail_2': {
                'npc': '蘿西', 'img': 'npcroxy.png', 'text': '「冒險者，歡迎來到基礎訓練營！進入市場前，熟悉『盤面術語』與『市場角色』是最基本的要求。記住，台股是『紅漲綠跌』，搞懂這些名詞，未來的籌碼分析才會事半功倍喔！」',
                'html': """<div class="section-title">📖 盤面速讀與狀態判讀</div>
<table class="pv-table"><thead><tr><th width="25%">狀態</th><th width="40%">一眼判讀</th><th width="35%">初步理解</th></tr></thead>
<tbody><tr><td style="color:#4ADE80; font-weight:bold;">🟢 買盤積極</td><td>股價↑ / 成交量↑</td><td style="text-align:left;">市場買方積極</td></tr><tr><td style="color:#F87171; font-weight:bold;">🔴 賣壓增加</td><td>股價↓ / 成交量↑</td><td style="text-align:left;">市場賣方積極</td></tr><tr><td style="color:#FACC15; font-weight:bold;">🟡 市場觀望</td><td>股價→ / 成交量↓</td><td style="text-align:left;">市場交易意願降低</td></tr><tr><td style="color:#FB923C; font-weight:bold;">🟠 波動加劇</td><td>高低價差↑ / 成交量↑</td><td style="text-align:left;">多空雙方競爭激烈</td></tr></tbody></table>
<div class="section-title">🏷️ 盤面常見名詞</div>
<table class="pv-table"><thead><tr><th width="20%">名詞</th><th width="40%">一眼理解</th><th width="40%">代表什麼</th></tr></thead>
<tbody><tr><td><b>開盤價</b></td><td style="text-align:left;">今天第一筆成交價</td><td style="text-align:left;">市場開盤的第一個價格</td></tr><tr><td><b>收盤價</b></td><td style="text-align:left;">最後成交價格</td><td style="text-align:left;">當日市場最後結果</td></tr><tr><td style="color:#00E676; font-weight:bold;">內盤</td><td style="text-align:left;">主動賣方成交</td><td style="text-align:left;">賣方較積極</td></tr><tr><td style="color:#FF4C4C; font-weight:bold;">外盤</td><td style="text-align:left;">主動買方成交</td><td style="text-align:left;">買方較積極</td></tr></tbody></table>"""
            },
            'detail_3': {
                'npc': '蘿西', 'img': 'npcroxy.png', 'text': '「冒險者，想找出真正能長期幫你賺錢的金雞母嗎？財報就是公司的體檢表！學會看懂基本面，才不會被虛假的包裝騙了喔！」',
                'html': """<div class="section-title">📖 三大財務報表白話理解</div>
<table class="pv-table"><thead><tr><th width="25%">財務報表</th><th width="35%">白話理解</th><th width="40%">主要看什麼</th></tr></thead>
<tbody><tr><td><b>📈 綜合損益表</b></td><td style="text-align:left;">公司這段時間賺多少</td><td style="text-align:left;">營收、毛利、營業利益、淨利</td></tr><tr><td><b>🏦 資產負債表</b></td><td style="text-align:left;">公司現在有多少家底</td><td style="text-align:left;">資產、負債、股東權益</td></tr><tr><td><b>💵 現金流量表</b></td><td style="text-align:left;">錢實際怎麼流動</td><td style="text-align:left;">營業、投資、籌資現金流</td></tr></tbody></table>
<div class="section-title">🔍 基本面狀態一眼判讀</div>
<table class="pv-table"><thead><tr><th width="25%">狀態</th><th width="40%">一眼判讀</th><th width="35%">初步解讀</th></tr></thead>
<tbody><tr><td style="color:#4ADE80; font-weight:bold;">🟢 穩定成長</td><td>營收↑ / EPS↑ / 現金流↑</td><td style="text-align:left;">公司營運與獲利同步改善</td></tr><tr><td style="color:#4ADE80; font-weight:bold;">🟢 獲利改善</td><td>營收→ / 毛利↑ / EPS↑</td><td style="text-align:left;">公司效率或產品組合改善</td></tr><tr><td style="color:#FACC15; font-weight:bold;">🟡 成長放緩</td><td>營收↑但增速↓ / EPS→</td><td style="text-align:left;">公司仍成長，但速度減慢</td></tr><tr><td style="color:#FB923C; font-weight:bold;">🟠 虛胖成長</td><td>營收↑ / EPS↓ / 現金流↓</td><td style="text-align:left;">生意變大，但獲利品質可能下降</td></tr><tr><td style="color:#EF4444; font-weight:bold;">🚨 基本面惡化</td><td>營收↓ / EPS↓ / 現金流↓</td><td style="text-align:left;">核心營運同步轉弱</td></tr></tbody></table>"""
            },
            'detail_4': {
                'npc': '羅德', 'img': 'npcroad.png', 'text': '「量價關係是市場最真實的足跡！仔細看這張表，當『量』與『價』出現背離時，就是趨勢即將反轉的危險警訊喔！」',
                'html': """<table class="pv-table" style="margin-top:10px;"><thead><tr><th width="15%">趨勢</th><th width="20%">狀態</th><th width="65%">市場含義</th></tr></thead>
<tbody>
<tr><td class="trend-up">上漲</td><td>價升量縮</td><td style="text-align:left;">量價背離，下方有承接，短期回調，後續拉高</td></tr>
<tr><td class="trend-up">上漲</td><td>放量滯漲</td><td style="text-align:left;">趨勢高位，拋壓增大，即將見頂反轉，減倉清倉</td></tr>
<tr><td class="trend-up">上漲</td><td>縮量大漲</td><td style="text-align:left;">趨勢中途，縮量加速，鎖倉高控盤，延續上漲</td></tr>
<tr><td class="trend-up">上漲</td><td>放量大漲</td><td style="text-align:left;">價漲量增，量價齊升，多方吸籌，持續看漲</td></tr>
<tr><td class="trend-down">下跌</td><td>縮量小跌</td><td style="text-align:left;">主力洗盤，拋壓減弱，止跌位置，擇機進場</td></tr>
<tr><td class="trend-down">下跌</td><td>放量小跌</td><td style="text-align:left;">見底信號，買方增強，越跌越買，反轉新倉</td></tr>
<tr><td class="trend-down">下跌</td><td>縮量大跌</td><td style="text-align:left;">一致看空，無人接盤，下跌中繼，加速下跌</td></tr>
<tr><td class="trend-down">下跌</td><td>放量大跌</td><td style="text-align:left;">跟風砸盤，大量賣出，高位出貨，持續下跌</td></tr>
</tbody></table>"""
            },
            'detail_5': {
                'npc': '羅德', 'img': 'npcroad.png', 'text': '「冒險者！技術指標可不是單純告訴你『買』或『賣』的魔法棒！它幫你從不同角度觀察市場的方向、動能與熱度。來看看這張儀表板吧！」',
                'html': """<div class="info-box"><b>🧭 指標核心雷達：</b><br>📈 MA 看方向 ｜ ⚡ MACD 看動能 ｜ 🌡️ RSI 看熱度 ｜ 🎢 KDJ 看短線節奏 ｜ 📏 BBW 看波動</div>
<div class="section-title">📊 綜合總表：多指標狀態判讀</div>
<table class="pv-table"><thead><tr><th width="18%">市場狀態</th><th width="20%">MA 趨勢</th><th width="22%">MACD 動能</th><th width="20%">RSI／KDJ</th><th width="20%">BBW 波動</th></tr></thead>
<tbody>
<tr><td style="color:#60A5FA; font-weight:bold;">🔵 蓄力整理</td><td>均線糾結</td><td>接近 0 軸</td><td>RSI 40～60</td><td>↓↓ 極度收縮</td></tr>
<tr><td style="color:#4ADE80; font-weight:bold;">🚀 向上突破</td><td>突破均線</td><td>DIF > DEA</td><td>RSI > 50</td><td>↑ 開始擴張</td></tr>
<tr><td style="color:#4ADE80; font-weight:bold;">🟢 多頭趨勢</td><td>股價 > MA</td><td>0軸上/偏多</td><td>RSI 50～70</td><td>正常或擴張</td></tr>
<tr><td style="color:#FF7676; font-weight:bold;">🔥 強勢加速</td><td>多頭排列</td><td>柱體↑↑</td><td>RSI 70↑</td><td>↑↑ 快速擴張</td></tr>
<tr><td style="color:#FACC15; font-weight:bold;">🟡 高檔過熱</td><td>維持多頭</td><td>動能縮小</td><td>RSI > 70</td><td>高檔擴張或收斂</td></tr>
<tr><td style="color:#FB923C; font-weight:bold;">🟠 趨勢轉弱</td><td>跌破短均</td><td>死亡交叉</td><td>RSI 跌破50</td><td>可能收縮或轉向</td></tr>
<tr><td style="color:#F87171; font-weight:bold;">🔴 空頭趨勢</td><td>股價 < MA</td><td>DIF < DEA</td><td>RSI < 40</td><td>向下擴張</td></tr>
</tbody></table>"""
            },
            'detail_6': {
                'npc': '羅德', 'img': 'npcroad.png', 'text': '「冒險者！市場上真正能呼風喚雨的，往往是那些掌握龐大資金的『法人』與『大戶』。透過這張籌碼結構表，我們可以看穿誰在買，進而判斷買盤的延續性喔！」',
                'html': """<div class="section-title">📊 法人、大戶與分點怎麼看？</div>
<table class="pv-table"><thead><tr><th width="20%">觀察對象</th><th width="25%">主要看什麼</th><th width="25%">🟢 偏多／集中</th><th width="30%">🔴 偏空／分散</th></tr></thead>
<tbody>
<tr><td><b>🌍 外資</b></td><td style="text-align:left;">連續買賣超</td><td style="color:#4ADE80; font-weight:bold;">連續買超／持股↑</td><td style="color:#F87171; font-weight:bold;">連續賣超／持股↓</td></tr>
<tr><td><b>🏦 投信</b></td><td style="text-align:left;">連續買賣超</td><td style="color:#4ADE80; font-weight:bold;">連續買超</td><td style="color:#F87171; font-weight:bold;">連續賣超</td></tr>
<tr><td><b>⚙️ 自營商</b></td><td style="text-align:left;">買賣超方向</td><td style="color:#4ADE80; font-weight:bold;">持續買超</td><td style="color:#F87171; font-weight:bold;">持續賣超</td></tr>
<tr><td><b>🦈 400 張</b></td><td style="text-align:left;">中大型持有人</td><td style="color:#4ADE80; font-weight:bold;">人數↓／持股↑</td><td style="color:#F87171; font-weight:bold;">人數↑／持股↓</td></tr>
<tr><td><b>🐋 1000 張</b></td><td style="text-align:left;">大型持有人</td><td style="color:#4ADE80; font-weight:bold;">持股↑／集中↑</td><td style="color:#F87171; font-weight:bold;">持股↓／集中↓</td></tr>
<tr><td><b>🔍 單一分點</b></td><td style="text-align:left;">連續買超占比</td><td style="color:#4ADE80; font-weight:bold;">連續買超／集中↑</td><td style="color:#F87171; font-weight:bold;">連續賣超</td></tr>
</tbody></table>"""
            },
            'detail_7': {
                'npc': '蘿西', 'img': 'npcroxy.png', 'text': '「融資與融券的變化，往往暗示著主力與散戶的籌碼流動！觀察下方這張『券資關係與軋空狀態表』，小心別被『軋空』或『多殺多』掃出市場喔！」',
                'html': """<table class="pv-table" style="margin-top:10px;"><thead><tr><th width="20%">趨勢</th><th width="35%">狀態</th><th width="45%">市場含義</th></tr></thead>
<tbody>
<tr><td style="color:#60A5FA; font-weight:bold;">🔵 可能軋空</td><td>股價↑ / 融券↑ / 借券↑ / 融資→↓</td><td style="text-align:left;">空方部位高，股價走強，後續可能回補</td></tr>
<tr><td style="color:#4ADE80; font-weight:bold;">🟢 正在軋空</td><td>股價↑↑ / 融券↓ / 借券↓ / 融資→↓</td><td style="text-align:left;">股價上漲同時空方下降，空方回補推升</td></tr>
<tr><td style="color:#FACC15; font-weight:bold;">🟡 軋空下降</td><td>股價↑→ / 券降幅縮 / 資↑</td><td style="text-align:left;">空方回補減弱，多方接棒力道需觀察</td></tr>
<tr><td style="color:#FB923C; font-weight:bold;">🟠 融資追價</td><td>股價↑ / 融資↑↑ / 券→↓</td><td style="text-align:left;">上漲伴隨融資增加，槓桿追價升溫</td></tr>
<tr><td style="color:#FACC15; font-weight:bold;">🟡 多空混戰</td><td>股價→ / 融資↑ / 融券↑</td><td style="text-align:left;">多空雙方同步加碼，方向尚未明確</td></tr>
<tr><td style="color:#F87171; font-weight:bold;">🔴 空方增加</td><td>股價↓ / 融券↑ / 借券↑↑</td><td style="text-align:left;">股價弱且空單增，空方壓力升高</td></tr>
<tr><td style="color:#EF4444; font-weight:bold;">🚨 多殺多</td><td>股價↓↓ / 融資↓↓ / 券→↓</td><td style="text-align:left;">股價跌導致融資退場，出現槓桿賣壓</td></tr>
</tbody></table>"""
            },
            'detail_8': {
                'npc': '蘿西', 'img': 'npcroxy.png', 'text': '「冒險者，市場資金就像流水，哪裡有『題材』就往哪裡去！真正的強勢產業會引發『族群共振』。當上下游供應鏈同步轉強，才代表大部隊進場囉！」',
                'html': """<div class="info-box"><b style="color: #FFD700;">🎯 重點不是追熱門，而是問自己：</b><br>市場炒什麼？是單檔漲還是族群共振？有無基本面支撐？是剛起漲還是過熱？</div>
<div class="section-title">🌊 資金輪動與題材階段解讀</div>
<table class="pv-table"><thead><tr><th width="20%">題材階段</th><th width="25%">族群共振</th><th width="55%">初步解讀</th></tr></thead>
<tbody>
<tr><td style="color:#60A5FA; font-weight:bold;">🌱 題材萌芽</td><td>單點啟動</td><td style="text-align:left;">少數公司受關注，尚未擴散。</td></tr>
<tr><td style="color:#4ADE80; font-weight:bold;">🚀 趨勢成長</td><td>局部共振</td><td style="text-align:left;">上下游陸續轉強，資金慢慢流入。</td></tr>
<tr><td style="color:#FACC15; font-weight:bold;">🧩 族群共振</td><td>全產業擴散</td><td style="text-align:left;">多家公司同步走強，資金高度集中。</td></tr>
<tr><td style="color:#FF7676; font-weight:bold;">🔥 市場主流</td><td>強烈共振</td><td style="text-align:left;">討論度極高，主流確立，注意追高風險。</td></tr>
<tr><td style="color:#FB923C; font-weight:bold;">⚠️ 高檔過熱</td><td>共振分歧</td><td style="text-align:left;">強弱分明，注意資金輪動與獲利了結。</td></tr>
<tr><td style="color:#94A3B8; font-weight:bold;">🌙 題材退燒</td><td>共振消失</td><td style="text-align:left;">強勢股減少、資金撤離。</td></tr>
</tbody></table>"""
            },
            'detail_9': {
                'npc': '蘿西', 'img': 'npcroxy.png', 'text': '「冒險者！資金控管就是你的護城河。別總想著『重壓一把』，學會根據大盤環境調整資金比例，才能在股海裡安穩航行喔！」',
                'html': """<div class="info-box"><b style="color: #FFD700;">🛡️ 大原則：</b> 🟢 大盤越明確 → 提高配置 ｜ 🟡 大盤越震盪 → 分批操作 ｜ 🔴 大盤越弱 → 提高現金</div>
<div class="section-title">📉 大盤環境與資金配置思維</div>
<table class="pv-table"><thead><tr><th width="24%">大盤狀態</th><th width="35%">資金配置思維</th><th width="41%">實戰操作方式</th></tr></thead>
<tbody>
<tr><td style="color:#4ADE80; font-weight:bold;">🚀 多頭趨勢</td><td style="text-align:left;">逐步提高參與度 (較高)</td><td style="text-align:left;">分批進場，不一次滿倉</td></tr>
<tr><td style="color:#60A5FA; font-weight:bold;">🟢 偏多震盪</td><td style="text-align:left;">保留部分現金 (中高)</td><td style="text-align:left;">分批建立部位，注意轉弱</td></tr>
<tr><td style="color:#FACC15; font-weight:bold;">🟡 區間震盪</td><td style="text-align:left;">控制總曝險 (中低)</td><td style="text-align:left;">避免追高，分批試單</td></tr>
<tr><td style="color:#FB923C; font-weight:bold;">🟠 偏空震盪</td><td style="text-align:left;">提高現金比例 (低)</td><td style="text-align:left;">嚴控風險，防個股受拖累</td></tr>
<tr><td style="color:#F87171; font-weight:bold;">🔴 空頭趨勢</td><td style="text-align:left;">優先控制風險 (觀望)</td><td style="text-align:left;">極低或不投入，避免攤平</td></tr>
<tr><td style="color:#bc13fe; font-weight:bold;">🚨 連續看錯</td><td style="text-align:left;">暫停或明顯降低部位</td><td style="text-align:left;">防情緒化交易，檢討策略</td></tr>
</tbody></table>"""
            },
            'detail_10': {
                'npc': '蘿西', 'img': 'npcroxy.png', 'text': '「恭喜你來到最後一關！技術再好，心態崩了也是白搭。真正成熟的投資者知道『何時該收手』。讓我們建立屬於你的交易系統吧！」',
                'html': """<div class="info-box" style="border-color:rgba(255,76,76,0.3); background:rgba(255,76,76,0.05);"><b style="color: #FF4C4C;">⚠️ 致命陷阱：輸在太想賺！</b><br>一直交易不代表積極，而是不願等待。過度追求易導致：追高➔ 放大部位➔ 不願停損➔ <b>大虧損！</b></div>
<div class="section-title">🧠 常見心理陷阱與對策</div>
<table class="pv-table"><thead><tr><th width="20%">心理陷阱</th><th width="35%">常見想法</th><th width="45%">更好的做法</th></tr></thead>
<tbody>
<tr><td style="color:#F87171; font-weight:bold;">😨 恐懼</td><td>「再跌一點就完了...」</td><td style="text-align:left;">嚴守停損，該砍就砍。</td></tr>
<tr><td style="color:#4ADE80; font-weight:bold;">🤑 貪婪</td><td>「應該還會漲，繼續凹！」</td><td style="text-align:left;">不憑感覺，嚴守停利點。</td></tr>
<tr><td style="color:#FACC15; font-weight:bold;">🏃 FOMO</td><td>「現在不買就錯過了！」</td><td style="text-align:left;">寧可錯過也不做錯，等待條件。</td></tr>
<tr><td style="color:#FB923C; font-weight:bold;">🎲 過度交易</td><td>「今天一定要做點什麼...」</td><td style="text-align:left;">無高勝率不交易，休息是策略。</td></tr>
<tr><td style="color:#bc13fe; font-weight:bold;">🔥 報復交易</td><td>「我要把虧的賺回來！」</td><td style="text-align:left;">關閉螢幕，暫停交易並檢討。</td></tr>
</tbody></table>
<div class="section-title">🏰 建立專屬交易系統</div>
<table class="pv-table"><thead><tr><th width="25%">系統環節</th><th width="75%">核心觀念</th></tr></thead>
<tbody>
<tr><td><b>🔎 選股條件</b></td><td style="text-align:left;">專注熟悉領域，不必什麼都做。</td></tr>
<tr><td><b>🎯 進場/部位</b></td><td style="text-align:left;">耐心等進打擊區，嚴控單筆承受風險。</td></tr>
<tr><td><b>🛑 停損停利</b></td><td style="text-align:left;">小錯可接受，大錯絕對避免；讓獲利延續。</td></tr>
<tr><td><b>🧘 等待機制</b></td><td style="text-align:left;">沒機會時不動作，這就是最強防守策略。</td></tr>
</tbody></table>"""
            }
        }
        
        data = courses_data.get(current_view, courses_data['detail_1'])
        
        html_code = f"""{common_css}
<div class="npc-overlay">
<div class="top-actions">
<label class="action-btn back" id="btn-back-detail" title="回到選單">←</label>
<label class="action-btn close" id="btn-close-detail" title="關閉">✕</label>
</div>
<div class="detail-header">
<div class="npc-big-image" style="background-image: url('app/static/{data['img']}');"></div>
<div class="dialogue-box">
<div class="npc-name">籌碼導師 {data['npc']}</div>
<div class="npc-text">{data['text']}</div>
</div>
</div>
<div class="table-container">
{data['html']}
</div>
</div>"""

    st.markdown(html_code, unsafe_allow_html=True)     
    
    def close_npc_action():
        st.session_state['show_course_npc'] = False
        st.session_state['course_view'] = 'list'
        
    def switch_view_action(view_name):
        st.session_state['course_view'] = view_name

    # 💡 將實體按鈕放入 st.empty() 裡面，確保它們在最後被渲染
    hidden_btn_container = st.empty()
    with hidden_btn_container.container():
        cols = st.columns(12)
        with cols[0]: st.button("CloseNPC", key="npc_btn_close", on_click=close_npc_action)
        with cols[1]: st.button("OpenCourse1", key="npc_btn_c1", on_click=switch_view_action, args=('detail_1',))
        with cols[2]: st.button("OpenCourse2", key="npc_btn_c2", on_click=switch_view_action, args=('detail_2',))
        with cols[3]: st.button("OpenCourse3", key="npc_btn_c3", on_click=switch_view_action, args=('detail_3',))
        with cols[4]: st.button("OpenCourse4", key="npc_btn_c4", on_click=switch_view_action, args=('detail_4',))
        with cols[5]: st.button("OpenCourse5", key="npc_btn_c5", on_click=switch_view_action, args=('detail_5',))
        with cols[6]: st.button("OpenCourse6", key="npc_btn_c6", on_click=switch_view_action, args=('detail_6',))
        with cols[7]: st.button("OpenCourse7", key="npc_btn_c7", on_click=switch_view_action, args=('detail_7',))
        with cols[8]: st.button("OpenCourse8", key="npc_btn_c8", on_click=switch_view_action, args=('detail_8',))
        with cols[9]: st.button("OpenCourse9", key="npc_btn_c9", on_click=switch_view_action, args=('detail_9',))
        with cols[10]: st.button("OpenCourse10", key="npc_btn_c10", on_click=switch_view_action, args=('detail_10',))
        with cols[11]: st.button("BackToList", key="npc_btn_back", on_click=switch_view_action, args=('list',))
        
    # 💡 使用 onclick 覆寫事件，確保不會綁定到無效的死按鈕，這在切換頁面時特別關鍵
    bind_js = """<script>
    setInterval(() => {
        const doc = window.parent.document;
        if (!doc) return;

        const stBtns = Array.from(doc.querySelectorAll('button'));
        const btnClose = stBtns.find(b => b.textContent.includes('CloseNPC'));
        const btnOpen1 = stBtns.find(b => b.textContent.includes('OpenCourse1'));
        const btnOpen2 = stBtns.find(b => b.textContent.includes('OpenCourse2'));
        const btnOpen3 = stBtns.find(b => b.textContent.includes('OpenCourse3'));
        const btnOpen4 = stBtns.find(b => b.textContent.includes('OpenCourse4'));
        const btnOpen5 = stBtns.find(b => b.textContent.includes('OpenCourse5'));
        const btnOpen6 = stBtns.find(b => b.textContent.includes('OpenCourse6'));
        const btnOpen7 = stBtns.find(b => b.textContent.includes('OpenCourse7'));
        const btnOpen8 = stBtns.find(b => b.textContent.includes('OpenCourse8'));
        const btnOpen9 = stBtns.find(b => b.textContent.includes('OpenCourse9'));
        const btnOpen10 = stBtns.find(b => b.textContent.includes('OpenCourse10'));
        const btnBack = stBtns.find(b => b.textContent.includes('BackToList'));

        // 瞬間將按鈕推到畫面之外隱藏
        [btnClose, btnOpen1, btnOpen2, btnOpen3, btnOpen4, btnOpen5, btnOpen6, btnOpen7, btnOpen8, btnOpen9, btnOpen10, btnBack].forEach(b => {
            if(b) {
                const container = b.closest('div[data-testid="stElementContainer"]');
                if(container) {
                    container.style.position = 'fixed';
                    container.style.top = '-9999px';
                    container.style.left = '-9999px';
                }
            }
        });

        const bindEvent = (uiId, stBtn) => {
            const uiEl = doc.getElementById(uiId);
            if(uiEl && stBtn) {
                uiEl.style.cursor = 'pointer'; 
                uiEl.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    stBtn.click(); 
                };
            }
        };

        bindEvent('btn-close-list', btnClose);
        bindEvent('btn-close-detail', btnClose);
        bindEvent('btn-back-detail', btnBack);
        bindEvent('btn-open-course-1', btnOpen1);
        bindEvent('btn-open-course-2', btnOpen2);
        bindEvent('btn-open-course-3', btnOpen3);
        bindEvent('btn-open-course-4', btnOpen4);
        bindEvent('btn-open-course-5', btnOpen5);
        bindEvent('btn-open-course-6', btnOpen6);
        bindEvent('btn-open-course-7', btnOpen7);
        bindEvent('btn-open-course-8', btnOpen8);
        bindEvent('btn-open-course-9', btnOpen9);
        bindEvent('btn-open-course-10', btnOpen10);

    }, 15);
    </script>"""

    components.html(bind_js, height=0, width=0)
