# views/news_page.py
import streamlit as st
import requests
import time
import math

# 💡 效能救星 1：保留快取，並且隱藏轉圈圈避免跳動。
# 🚀 瘦身優化：使用雙層推導式 (Nested Comprehension) 極速攤平 JSON 陣列
@st.cache_data(ttl=600, show_spinner=False)
def fetch_historical_news(days_to_load=3):
    base_url = f"https://raw.githubusercontent.com/voidful/tw_news_stocker/main/docs/data"
    cb = int(time.time() / 600)
    try:
        dates = sorted(requests.get(f"{base_url}/news_index.json?t={cb}").json(), reverse=True)[:days_to_load]
        return [news for d in dates if (res := requests.get(f"{base_url}/news/{d}.json?t={cb}")).status_code == 200 for news in res.json()]
    except Exception: return []

# 💡 效能救星 2：把搜尋、過濾、換頁與卡片渲染全部包裝進 Fragment
@st.fragment
def render_news_dashboard():
    c1, c2 = st.columns([1, 2])
    days_option = c1.selectbox("載入歷史天數", [1, 3, 7, 14, 30, 90, 180, 365], index=0, key="news_days_option")
    q = c2.text_input("🔍 搜尋市場新聞標題、關鍵字或股票代號...", key="news_search_query").strip().lower()
    st.markdown("---")
    
    with st.spinner(f"正在從資料庫撈取近 {days_option} 天的新聞..."):
        news_data = fetch_historical_news(days_option)
        
    if not news_data: return st.error("無法取得新聞資料，請檢查網路連線。")

    # 🚀 運算最佳化：用一行 List Comprehension 取代原本數十行的 for 迴圈過濾
    filtered_news = [n for n in sorted(news_data, key=lambda x: x.get("ts", ""), reverse=True) 
                     if not q or q in n.get("title", "").lower() or any(q in str(c).lower() for c in n.get("codes", []))]

    total_items = len(filtered_news)
    if total_items == 0: return st.warning(f"找不到包含「{q}」的新聞，建議增加上方的「載入歷史天數」再試一次！")

    # 處理分頁
    total_pages = math.ceil(total_items / 50)
    curr_page = st.columns([1, 2, 1])[1].number_input(f"📄 選擇頁數 (共 {total_pages} 頁)", 1, total_pages, 1, key="news_current_page")
    
    start_idx, end_idx = (curr_page - 1) * 50, min(curr_page * 50, total_items)
    st.caption(f"<div style='text-align: center; color: #94A3B8; margin-bottom: 20px;'>共 {total_items} 則新聞，目前顯示第 {start_idx + 1} 到 {end_idx} 則，千萬不要僅憑新聞操作買賣</div>", unsafe_allow_html=True)

    # 🚀 記憶體極限瘦身：單次批量 HTML 渲染 (取代迴圈呼叫 50 次 st.markdown)
    # 預先寫入高效能 CSS 樣式，避免每張卡片都塞滿 inline-style
    html_blocks = ["""<style>
        .n-card { background:rgba(30,41,59,0.4); backdrop-filter:blur(12px); border-radius:10px; border:1px solid rgba(255,255,255,0.1); padding:15px; margin-bottom:12px; transition:all 0.3s; }
        .n-card:hover { border-color:rgba(56,189,248,0.5); transform:translateY(-2px); box-shadow:0 4px 15px rgba(56,189,248,0.15); }
        .n-title { color:#E0F2FE; font-size:16px; font-weight:bold; text-decoration:none; display:block; margin-bottom:8px; transition:color 0.2s; }
        .n-title:hover { color:#38BDF8; }
        .n-info { display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#94A3B8; }
        .n-tag { background:#1E293B; border:1px solid #0369a1; color:#38BDF8; padding:2px 6px; border-radius:4px; margin-left:4px; }
    </style>"""]
    
    for n in filtered_news[start_idx:end_idx]:
        ts = n.get('ts', '').replace('T', ' ')[:16] # 快速格式化日期
        tags = "".join([f"<span class='n-tag'>{c}</span>" for c in n.get("codes", [])])
        html_blocks.append(f"""
        <div class="n-card">
            <a href="{n.get('link', '#')}" target="_blank" class="n-title">{n.get('title', '無標題')}</a>
            <div class="n-info">
                <span>來源: {n.get('source_host', '未知')} &nbsp;|&nbsp; 時間: {ts}</span>
                <div>{tags}</div>
            </div>
        </div>""")
        
    st.markdown("".join(html_blocks), unsafe_allow_html=True)


# ==========================================
# 🖼️ 主頁面渲染入口
# ==========================================
def show_news_page():
    st.markdown("""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            市場消息
        </h2>
    </div>
    """, unsafe_allow_html=True)
    
    render_news_dashboard()
