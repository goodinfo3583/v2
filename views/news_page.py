# views/news_page.py
import streamlit as st
import requests
import time
import math

# 💡 效能救星 1：保留快取，並且隱藏轉圈圈避免跳動
@st.cache_data(ttl=600, show_spinner=False)
def fetch_historical_news(days_to_load=3):
    """背景快取引擎工具 - 去 GitHub 搬運多天份的資料"""
    base_url = "https://raw.githubusercontent.com/voidful/tw_news_stocker/main/docs/data"
    cache_buster = int(time.time() / 600) 
    index_url = f"{base_url}/news_index.json?t={cache_buster}"
    
    all_news = []
    try:
        index_res = requests.get(index_url)
        index_res.raise_for_status()
        news_dates = index_res.json()
        
        news_dates.sort(reverse=True)
        target_dates = news_dates[:days_to_load]
        
        for date in target_dates:
            data_url = f"{base_url}/news/{date}.json?t={cache_buster}"
            res = requests.get(data_url)
            if res.status_code == 200:
                day_data = res.json()
                all_news.extend(day_data)
                
        return all_news, target_dates
    except Exception as e:
        return [], []

# 💡 效能救星 2：把搜尋、過濾、換頁與卡片渲染全部包裝進 Fragment。
# 這樣打字搜尋或換頁時，畫面絕對不會跳回頂端或閃爍！
@st.fragment
def render_news_dashboard():
    col1, col2 = st.columns([1, 2])
    with col1:
        # 加上 key 讓 Streamlit 更好追蹤狀態
        days_option = st.selectbox("載入歷史天數", [1, 3, 7, 14, 30, 90, 180, 365], index=0, key="news_days_option")
    with col2:
        search_query = st.text_input("🔍 搜尋市場新聞標題、關鍵字或股票代號...", key="news_search_query")
        
    st.markdown("---")
    
    # 這裡的 spinner 只會在「改變載入天數」去 GitHub 抓新資料時短暫出現，
    # 只要資料進了快取，之後你打字搜尋或換頁，都不會再轉圈圈了！
    with st.spinner(f"正在從資料庫撈取近 {days_option} 天的新聞..."):
        news_data, loaded_dates = fetch_historical_news(days_option)
        
    if not news_data:
        st.error("無法取得新聞資料，請檢查網路連線。")
        return
        
    try:
        sorted_news = sorted(news_data, key=lambda x: x.get("ts", ""), reverse=True)
    except:
        sorted_news = news_data

    filtered_news = []
    for news in sorted_news:
        title = news.get("title", "")
        codes = news.get("codes", [])
        
        if search_query:
            q = search_query.lower()
            match_title = q in title.lower()
            match_code = any(q in str(c).lower() for c in codes)
            if not (match_title or match_code):
                continue 
                
        filtered_news.append(news)

    total_items = len(filtered_news)
    
    if total_items == 0:
        st.warning(f"找不到包含「{search_query}」的新聞，建議增加上方的「載入歷史天數」再試一次！")
        return

    ITEMS_PER_PAGE = 50 
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) 
    
    col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
    with col_p2:
        current_page = st.number_input(
            f"📄 選擇頁數 (共 {total_pages} 頁)", 
            min_value=1, max_value=total_pages, value=1, step=1,
            key="news_current_page"
        )
        
    start_item = (current_page - 1) * ITEMS_PER_PAGE + 1
    end_item = min(current_page * ITEMS_PER_PAGE, total_items)
    st.caption(f"<div style='text-align: center; color: #94A3B8; margin-bottom: 20px;'>共 {total_items} 則新聞，目前顯示第 {start_item} 到 {end_item} 則，千萬不要僅憑新聞操作買賣</div>", unsafe_allow_html=True)

    start_idx = (current_page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    display_news = filtered_news[start_idx:end_idx] 

    for news in display_news:
        title = news.get("title", "")
        codes = news.get("codes", [])
        codes_html = "".join([f"<span class='code-tag'>{c}</span>" for c in codes]) if codes else ""
        link = news.get('link', '#')
        host = news.get('source_host', '未知')
        ts = news.get('ts', '')
        if "T" in ts:
            ts = ts.split("T")[0] + " " + ts.split("T")[1][:5]
        
        card_html = f"""
        <div class="glass-card">
            <a href="{link}" target="_blank" class="news-title">{title}</a>
            <div class="news-info">
                <span>來源: {host} &nbsp;|&nbsp; 時間: {ts}</span>
                <div>{codes_html}</div>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)


# ==========================================
# 🖼️ 主頁面渲染入口
# ==========================================
def show_news_page():
    """市場消息頁面 UI 渲染"""
    st.markdown("""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            市場消息
        </h2>
    </div>
    """, unsafe_allow_html=True)
    
    # 💡 呼叫被 Fragment 隔離的互動區塊
    render_news_dashboard()
