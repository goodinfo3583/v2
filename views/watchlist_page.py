# views/watchlist_page.py
import streamlit as st
import json
import re
import time
import pandas as pd

# ==========================================
# 💾 資料庫存取 (Google Sheets 正式連線版)
# ==========================================
def get_user_watchlist(username, conn, SHEET_URL):
    if not conn or not SHEET_URL: return {}
    try:
        # 💡 效能優化：讀取名冊給予 60 秒快取，避免每次打字都去要資料
        df = conn.read(spreadsheet=SHEET_URL, worksheet="會員名冊", ttl=60)
        if df.empty or '帳號' not in df.columns or 'Watchlist' not in df.columns:
            return {}
            
        clean_accounts = df['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower()
        target_user = str(username).strip().lower()
        match = df[clean_accounts == target_user]
        
        if not match.empty:
            gs_watchlist_str = match.iloc[0]['Watchlist']
            if pd.notna(gs_watchlist_str) and str(gs_watchlist_str).strip() != "":
                data = json.loads(str(gs_watchlist_str))
                if isinstance(data, list): return {stock: "" for stock in data}
                return data
    except Exception as e: pass
    return {}

def save_user_watchlist(username, watchlist, conn, SHEET_URL):
    if not conn or not SHEET_URL:
        st.error("無法連線至資料庫，無法存檔。")
        return
    try:
        watchlist_str = json.dumps(watchlist, ensure_ascii=False)
        # 💡 寫入時保持 ttl=0，確保拿到最新版本的資料庫以防覆蓋別人資料
        df = conn.read(spreadsheet=SHEET_URL, worksheet="會員名冊", ttl=0)
        if df.empty or '帳號' not in df.columns: return
            
        if 'Watchlist' not in df.columns: df['Watchlist'] = ""
        df['Watchlist'] = df['Watchlist'].astype(object)
            
        clean_accounts = df['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower()
        target_user = str(username).strip().lower()
        idx = df[clean_accounts == target_user].index
        
        if len(idx) > 0:
            df.at[idx[0], 'Watchlist'] = watchlist_str
            conn.update(spreadsheet=SHEET_URL, worksheet="會員名冊", data=df)
            # 寫入成功後，清除快取讓下次讀取能拿到最新資料
            st.cache_data.clear() 
    except Exception as e:
        st.error(f"存檔失敗: {e}")

# ==========================================
# 🚀 高效能批次報價引擎
# ==========================================
# 💡 效能優化：加上 show_spinner=False 消除閃爍感
@st.cache_data(show_spinner=False, ttl=300)
def get_watchlist_quotes(stock_codes):
    import yfinance as yf
    if not stock_codes: return {}
    
    tickers = [f"{c}.TW" for c in stock_codes] + [f"{c}.TWO" for c in stock_codes]
    try: df = yf.download(tickers, period="5d", progress=False)
    except: return {}
        
    quotes = {}
    if df.empty: return quotes
    
    if isinstance(df.columns, pd.MultiIndex):
        close_df = df['Close'] if 'Close' in df.columns else pd.DataFrame()
        vol_df = df['Volume'] if 'Volume' in df.columns else pd.DataFrame()
    else:
        close_df = pd.DataFrame({tickers[0]: df['Close']}) if 'Close' in df.columns else pd.DataFrame()
        vol_df = pd.DataFrame({tickers[0]: df['Volume']}) if 'Volume' in df.columns else pd.DataFrame()

    for c in stock_codes:
        tw, two = f"{c}.TW", f"{c}.TWO"
        closes = close_df[tw].dropna() if tw in close_df.columns else pd.Series(dtype=float)
        vols = vol_df[tw].dropna() if tw in vol_df.columns else pd.Series(dtype=float)
        
        if closes.empty:
            closes = close_df[two].dropna() if two in close_df.columns else pd.Series(dtype=float)
            vols = vol_df[two].dropna() if two in vol_df.columns else pd.Series(dtype=float)
            
        if len(closes) >= 2 and len(vols) >= 2:
            c_today, c_yest = float(closes.iloc[-1]), float(closes.iloc[-2])
            v_today, v_yest = float(vols.iloc[-1]), float(vols.iloc[-2])
            
            p_pct = (c_today - c_yest) / c_yest * 100 if c_yest > 0 else 0
            v_pct = (v_today - v_yest) / v_yest * 100 if v_yest > 0 else 0
            quotes[c] = {"price": c_today, "price_pct": p_pct, "vol": int(v_today / 1000), "vol_pct": v_pct, "date": closes.index[-1].strftime("%Y/%m/%d")}
    return quotes


# ==========================================
# 🚀 獨立渲染魔法區塊一：實驗室模型追蹤
# ==========================================
@st.fragment
def render_tab_track(username, conn):
    st.subheader("模型鎖定清單與績效追蹤")
    st.markdown("這裡顯示您從「權重與回測」寫入的標的，方便您每日檢視策略績效。")
    
    st.markdown(
        """
        <style>
        .track-card {
            background: rgba(30, 41, 59, 0.4);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            padding: 15px 15px;
            margin-bottom: 15px;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        }
        .track-card:hover {
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid rgba(56, 189, 248, 0.5);
            box-shadow: 0 8px 25px rgba(56, 189, 248, 0.2);
            transform: translateY(-2px);
        }
        .stat-box {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 8px;
            padding: 8px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .stat-title { font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
        .stat-value { font-size: 15px; font-weight: bold; }
        .pos-return { color: #FF4B4B; }
        .neg-return { color: #00E272; }
        .neu-return { color: #94A3B8; }
        </style>
        """,
        unsafe_allow_html=True
    )

    if conn:
        try:
            TRACKING_URL = "https://docs.google.com/spreadsheets/d/1TxHDahg8ul6lmUtDN-7X75cBXbkU0jaZ3M9zg6exBgU/edit?gid=687268023#gid=687268023"
            # 💡 效能優化：ttl 從 0 改為 60，避免重複讀取卡死
            df_track = conn.read(spreadsheet=TRACKING_URL, worksheet="實驗室模型追蹤", ttl=60)
            
            if df_track.empty or '帳號' not in df_track.columns:
                st.info("尚無追蹤紀錄。請至「權重與回測」過濾標的並點擊寫入。")
            else:
                clean_accounts = df_track['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower()
                user_track = df_track[clean_accounts == username.strip().lower()].copy()
                
                if user_track.empty:
                    st.info("您目前沒有將任何模型標的寫入追蹤喔！")
                else:
                    track_codes = []
                    for idx, row in user_track.iterrows():
                        code = str(row.get('代號', '')).replace('.0', '').strip()
                        if not code:
                            uni_code = str(row.get('統一代號', ''))
                            m = re.search(r'\d+', uni_code)
                            if m: code = m.group()
                        if code and code not in track_codes:
                            track_codes.append(code)

                    track_quotes = {}
                    if track_codes:
                        track_quotes = get_watchlist_quotes(track_codes)

                    st.markdown("### 鎖定標的戰情面板")
                    
                    cards_data = list(user_track.iterrows())
                    cols_per_row = 3 
                    
                    for i in range(0, len(cards_data), cols_per_row):
                        cols = st.columns(cols_per_row)
                        for j in range(cols_per_row):
                            if i + j < len(cards_data):
                                idx, row = cards_data[i + j]
                                
                                lock_date = row.get('鎖定日期', '未知')
                                name = row.get('名稱', row.get('股票名稱', '未知'))
                                
                                code = str(row.get('代號', '')).replace('.0', '').strip()
                                if not code:
                                    uni_code = str(row.get('統一代號', ''))
                                    m = re.search(r'\d+', uni_code)
                                    if m: code = m.group()

                                lock_price_raw = row.get('鎖定收盤價', row.get('B0_成交', 0))
                                try: lock_price = float(str(lock_price_raw).replace(',', ''))
                                except: lock_price = 0

                                current_price = lock_price
                                if code in track_quotes:
                                    current_price = track_quotes[code]['price']

                                if lock_price > 0:
                                    roi = ((current_price - lock_price) / lock_price) * 100
                                    roi = round(roi, 2)
                                else:
                                    roi = 0.0
                                    
                                if roi == 0.0 or roi == -0.0:
                                    roi = 0.0

                                roi_class = "pos-return" if roi > 0 else ("neg-return" if roi < 0 else "neu-return")
                                sign = "+" if roi > 0 else ""

                                with cols[j]:
                                    st.markdown(f"""
                                    <div class="track-card">
                                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                            <div style="font-size: 16px; font-weight: bold; color: #fff;"><span style="color: #38BDF8; margin-right: 6px;">{code}</span>{name}</div>
                                            <div style="font-size: 11px; color: #94a3b8; background: rgba(0,0,0,0.3); padding: 4px 6px; border-radius: 4px;">鎖定: {lock_date}</div>
                                        </div>                                            
                                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;">
                                            <div class="stat-box">
                                                <div class="stat-title">鎖定價</div>
                                                <div class="stat-value" style="color: #e2e8f0;">{lock_price:.2f}</div>
                                            </div>
                                            <div class="stat-box">
                                                <div class="stat-title">最新價</div>
                                                <div class="stat-value" style="color: #e2e8f0;">{current_price:.2f}</div>
                                            </div>
                                            <div class="stat-box" style="background: rgba({ '255,75,75' if roi > 0 else ('0,226,114' if roi < 0 else '148,163,184') }, 0.1); border-color: rgba({ '255,75,75' if roi > 0 else ('0,226,114' if roi < 0 else '148,163,184') }, 0.3);">
                                                <div class="stat-title">報酬</div>
                                                <div class="stat-value {roi_class}">{sign}{roi:.2f}%</div>
                                            </div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                    st.markdown("<hr style='border-color: #334155; margin: 10px 0 20px 0;'>", unsafe_allow_html=True)
                    
                    st.markdown("### 原始數據總表")
                    
                    display_df = user_track.drop(columns=['帳號']) if '帳號' in user_track.columns else user_track.copy()
                    
                    new_prices = []
                    new_rois = []
                    for idx, row in display_df.iterrows():
                        code = str(row.get('代號', '')).replace('.0', '').strip()
                        if not code:
                            uni_code = str(row.get('統一代號', ''))
                            m = re.search(r'\d+', uni_code)
                            if m: code = m.group()
                            
                        lock_price_raw = row.get('鎖定收盤價', row.get('B0_成交', 0))
                        try: lock_price = float(str(lock_price_raw).replace(',', ''))
                        except: lock_price = 0
                        
                        cur_price = lock_price
                        if code in track_quotes: cur_price = track_quotes[code]['price']
                        
                        roi = ((cur_price - lock_price) / lock_price) * 100 if lock_price > 0 else 0.0
                        roi = round(roi, 2)
                        if roi == 0.0 or roi == -0.0: roi = 0.0
                        
                        new_prices.append(cur_price)
                        new_rois.append(f"{roi:.2f}%")
                    
                    if '鎖定收盤價' in display_df.columns:
                        loc = display_df.columns.get_loc('鎖定收盤價') + 1
                        display_df.insert(loc, '最新價格', new_prices)
                        display_df.insert(loc + 1, '區間報酬', new_rois)
                    else:
                        display_df['最新價格'] = new_prices
                        display_df['區間報酬'] = new_rois

                    st.dataframe(display_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"讀取追蹤資料時發生錯誤：{e}")


# ==========================================
# 🚀 獨立渲染魔法區塊二：自訂追蹤名單
# ==========================================
@st.fragment
def render_tab_custom(username, conn, SHEET_URL, STOCK_DICT):
    wl_cache_key = f"wl_cache_{username}"

    if wl_cache_key not in st.session_state:
        st.session_state[wl_cache_key] = get_user_watchlist(username, conn, SHEET_URL)
        
    watchlist = st.session_state[wl_cache_key]
    MAX_STOCKS = 20

    for stock in list(watchlist.keys()):
        nk = f"note_{stock}"
        if nk not in st.session_state:
            st.session_state[nk] = watchlist[stock]

    st.subheader(f"新增自訂標的 (目前 {len(watchlist)}/{MAX_STOCKS} 檔)")
    col1, col2 = st.columns([3, 1])
    
    stock_options = []
    if STOCK_DICT:
        unique_options = {f"{v['id']} {v['name']}" for v in STOCK_DICT.values() if len(str(v['id'])) <= 4}
        stock_options = sorted(list(unique_options))

    with col1:
        new_stock = st.selectbox(
            "請選擇股票", 
            options=[""] + stock_options,
            key="new_stock_input",
            label_visibility="collapsed"
        )
        
    with col2:
        if st.button("加入追蹤", use_container_width=True):
            if new_stock:
                if len(watchlist) >= MAX_STOCKS:
                    st.error(f"追蹤名單已達 {MAX_STOCKS} 檔上限！")
                else:
                    if new_stock not in watchlist:
                        watchlist[new_stock] = "" 
                        st.session_state[f"note_{new_stock}"] = ""
                        st.success(f"已暫存「{new_stock}」，請記得點擊下方「存檔」！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.info(f"「{new_stock}」已在名單中囉！")

    st.markdown("<hr style='border-color: #334155; margin: 10px 0;'>", unsafe_allow_html=True)
    
    stock_codes = []
    for stock in watchlist.keys():
        m = re.search(r'\d+', stock)
        if m: stock_codes.append(m.group())

    market_data = {}
    market_date = "今日"
    if stock_codes:
        # 💡 移除 spinner，因為已有快取保護，會瞬間完成
        market_data = get_watchlist_quotes(stock_codes)
        if market_data:
            market_date = list(market_data.values())[0]["date"]

    # 定義在 fragment 內部的按鈕回呼函數
    def append_quote_to_note(stock_name, p_code):
        if p_code and p_code in market_data:
            d = market_data[p_code]
            append_str = f"[{d['date'][5:]}] 收:{d['price']:.2f} 量:{d['vol']:,}張"
            nk = f"note_{stock_name}"
            current_text = st.session_state.get(nk, "").strip()
            if current_text:
                st.session_state[nk] = current_text + f"\n{append_str}"
            else:
                st.session_state[nk] = append_str
            watchlist[stock_name] = st.session_state[nk]

    def append_dynamic_to_note(stock_name, p_code):
        dyn_msg = "⚪ B1未進榜"
        display_date = market_date[5:] if '/' in market_date else "今日"
        try:
            df_b1 = st.session_state.get('b1_final_df')
            if df_b1 is None or df_b1.empty:
                df_b1 = st.session_state.get('my_final_df')
            df_b1_down = st.session_state.get('b1_down_final_df')

            if df_b1 is not None and not df_b1.empty:
                date_cols = [c for c in df_b1.columns if '持股%' in c or str(c).isdigit()]
                if date_cols:
                    sorted_dates = sorted(date_cols, reverse=True)
                    date_match = re.search(r'20\d{6}', str(sorted_dates[0]))
                    if date_match:
                        ds = date_match.group()
                        display_date = f"{ds[4:6]}/{ds[6:8]}"

                col_id = '股票代號' if '股票代號' in df_b1.columns else ('代號' if '代號' in df_b1.columns else None)
                if col_id:
                    df_b1[col_id] = df_b1[col_id].astype(str).str.strip()
                    res = df_b1[df_b1[col_id] == str(p_code)]
                    if not res.empty:
                        row = res.iloc[0]
                        def safe_get(target_row, target_cols, col_keywords, exclude_keywords=[], default="-"):
                            for col in target_cols:
                                if any(exc in col for exc in exclude_keywords): continue
                                if any(k in col for k in col_keywords):
                                    val = str(target_row[col]).strip()
                                    if val.lower() in ['nan', 'none', '']: return default
                                    try:
                                        f_val = float(val)
                                        return f"{f_val:.2f}"
                                    except ValueError:
                                        return val
                            return default

                        status = safe_get(row, res.columns, ['最新動態', '狀態動態', '動態'], exclude_keywords=['衰退'])
                        tags = safe_get(row, res.columns, ['今日上榜', '原始上榜', '上榜'], exclude_keywords=['衰退'])
                        delta = safe_get(row, res.columns, ['單日△', '精準單日', '單日', '△'], exclude_keywords=['衰退'])
                        msg_lines = [f"📌動態:{status} | 🏷️上榜:{tags} | 📊單日△:{delta}"]
                        
                        decay_tags, decay_delta = "無", "-"
                        if df_b1_down is not None and not df_b1_down.empty:
                            col_id_down = '股票代號' if '股票代號' in df_b1_down.columns else ('代號' if '代號' in df_b1_down.columns else None)
                            if col_id_down:
                                df_b1_down[col_id_down] = df_b1_down[col_id_down].astype(str).str.strip()
                                res_down = df_b1_down[df_b1_down[col_id_down] == str(p_code)]
                                if not res_down.empty:
                                    row_down = res_down.iloc[0]
                                    decay_tags = safe_get(row_down, res_down.columns, ['衰退上榜', '提款機', '衰退追蹤', '衰退'])
                                    decay_delta = safe_get(row_down, res_down.columns, ['衰退單日', '提款單日', '衰退△', '單日△', '精準單日', '△'])

                        if decay_tags != "無" and decay_tags != "未進榜" and decay_tags != "-":
                            msg_lines.append(f"📉提款 🏷️衰退:{decay_tags} | 📊單日△:{decay_delta}")
                            
                        dyn_msg = "\n  ".join(msg_lines)
            else:
                dyn_msg = "⚠️ B1資料未載入(請先點側邊欄搜尋或全市場掃描)"
        except Exception as e:
            dyn_msg = f"讀取異常: {e}"

        append_str = f"[{display_date}]\n  {dyn_msg}"
        nk = f"note_{stock_name}"
        current_text = st.session_state.get(nk, "").strip()
        if current_text:
            st.session_state[nk] = current_text + f"\n{append_str}"
        else:
            st.session_state[nk] = append_str
        watchlist[stock_name] = st.session_state[nk]

    def batch_append_quotes():
        for stock_name in list(watchlist.keys()):
            stock_code_match = re.search(r'\d+', stock_name)
            pure_code = stock_code_match.group() if stock_code_match else None
            append_quote_to_note(stock_name, pure_code)

    def batch_append_dynamics():
        for stock_name in list(watchlist.keys()):
            stock_code_match = re.search(r'\d+', stock_name)
            pure_code = stock_code_match.group() if stock_code_match else None
            append_dynamic_to_note(stock_name, pure_code)

    def batch_remove_all():
        for stock_name in list(watchlist.keys()):
            nk = f"note_{stock_name}"
            if nk in st.session_state:
                del st.session_state[nk]
        watchlist.clear()
        if "selected_watch_stock" in st.session_state:
            st.session_state["selected_watch_stock"] = None
        if "global_search_final" in st.session_state:
            st.session_state["global_search_final"] = ""

    def batch_clear_notes():
        for stock_name in list(watchlist.keys()):
            nk = f"note_{stock_name}"
            st.session_state[nk] = ""
            watchlist[stock_name] = ""

    # 左上角存檔、匯出與日期區塊 
    col_save, col_export, col_date, col_space = st.columns([1.5, 1.5, 3.0, 4.0])
    with col_save:
        if st.button("存檔", icon=":material/save:", use_container_width=True, type="primary", help="將目前的變更同步至雲端"):
            with st.spinner("正在上傳至雲端..."):
                for stock in list(watchlist.keys()):
                    nk = f"note_{stock}"
                    if nk in st.session_state:
                        watchlist[stock] = st.session_state[nk]
                save_user_watchlist(username, watchlist, conn, SHEET_URL)
            st.success("存檔成功！")
            time.sleep(1)
            st.rerun()
            
    with col_export:
        if watchlist:
            export_data = []
            for stock, note in watchlist.items():
                current_note = st.session_state.get(f"note_{stock}", note)
                pure_code = None
                stock_code_match = re.search(r'\d+', stock)
                if stock_code_match: pure_code = stock_code_match.group()
                
                price, vol = "", ""
                if pure_code and pure_code in market_data:
                    price = market_data[pure_code]["price"]
                    vol = market_data[pure_code]["vol"]
                    
                export_data.append({"標的名稱": stock, "最新價": price, "成交量(張)": vol, "專屬筆記": current_note})
                
            df_export = pd.DataFrame(export_data)
            csv = df_export.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            
            st.download_button(
                label="匯出",
                icon=":material/download:",
                data=csv,
                file_name=f"watchlist_{username}.csv",
                mime="text/csv",
                use_container_width=True,
                help="下載為 CSV 檔"
            )
        else:
            st.button("匯出", icon=":material/download:", use_container_width=True, disabled=True)

    with col_date:
        if watchlist and market_data:
            st.markdown(f"<div style='padding-top:8px; color:#38BDF8; font-size:15px; font-weight:bold;'>日期：{market_date}</div>", unsafe_allow_html=True)

    st.write("") 
    
    if not watchlist:
        st.info("目前還沒有追蹤任何標的，趕快新增一個吧！")
    else:
        # 注入玻璃卡片的專屬 CSS 特效
        st.markdown(
            """
            <style>
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.stock-card-marker) {
                background: rgba(30, 41, 59, 0.3) !important;
                backdrop-filter: blur(12px) !important;
                -webkit-backdrop-filter: blur(12px) !important;
                border-radius: 12px !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
                margin-bottom: 8px !important; 
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.stock-card-marker):hover {
                background: rgba(30, 41, 59, 0.6) !important;
                border: 1px solid rgba(56, 189, 248, 0.4) !important;
                box-shadow: 0 8px 25px rgba(56, 189, 248, 0.15) !important;
                transform: translateY(-2px) !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.stock-card-marker) > div {
                padding: 10px 15px !important;
                gap: 0px !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.header-row-marker) {
                border: none !important;
                background: transparent !important;
                box-shadow: none !important;
                margin-bottom: -15px !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.header-row-marker) > div {
                padding: 10px 15px !important;
                gap: 0px !important;
            }
            div[data-testid="stColumn"]:has(.header-btn-blue) button {
                background-color: #0284C7 !important;
                color: #FFFFFF !important;
                border: none !important;
                border-radius: 6px !important;
                transition: all 0.3s ease !important;
                margin-top: 0px !important;
            }
            div[data-testid="stColumn"]:has(.header-btn-blue) button:hover {
                background-color: #0EA5E9 !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 4px 10px rgba(14, 165, 233, 0.4) !important;
            }
            div[data-testid="stColumn"]:has(.header-btn-red) button {
                background-color: #E11D48 !important;
                color: #FFFFFF !important;
                border: none !important;
                border-radius: 6px !important;
                transition: all 0.3s ease !important;
            }
            div[data-testid="stColumn"]:has(.header-btn-red) button:hover {
                background-color: #F43F5E !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 4px 10px rgba(225, 29, 72, 0.4) !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        col_ratios = [1.1, 0.9, 1.1, 1.1, 3.9, 0.5, 0.5, 0.5, 0.5]
        
        def fmt_color(val, is_pct=False, is_vol=False):
            color = "#FF4B4B" if val > 0 else ("#00E272" if val < 0 else "#94A3B8")
            sign = "+" if val > 0 else ""
            tail = "%" if is_pct else ""
            if is_vol: return f"<span style='color:{color}; font-size:12px;'>({sign}{val:.1f}%)</span>"
            return f"<span style='color:{color}; font-weight:bold;'>{sign}{val:.2f}{tail}</span>"

        with st.container(border=True):
            st.markdown("<span class='header-row-marker'></span>", unsafe_allow_html=True)
            h1, h2, h3, h4, h5, h6, h7, h8, h9 = st.columns(col_ratios)
            
            with h1: st.markdown("<div style='padding-top:10px;'><span style='color:#94a3b8; font-size:14px;'>標的名稱</span></div>", unsafe_allow_html=True)
            with h2: st.markdown("<div style='padding-top:10px;'><span style='color:#94a3b8; font-size:14px;'>產業別</span></div>", unsafe_allow_html=True)
            with h3: st.markdown("<div style='padding-top:10px;'><span style='color:#94a3b8; font-size:14px;'>最新價</span></div>", unsafe_allow_html=True)
            with h4: st.markdown("<div style='padding-top:10px;'><span style='color:#94a3b8; font-size:14px;'>成交量 (張)</span></div>", unsafe_allow_html=True)
            
            with h5:
                hc1, hc2 = st.columns([3.4, 0.5])
                with hc1:
                    st.markdown("<div style='padding-top:10px;'><span style='color:#94a3b8; font-size:14px;'>專屬筆記 (一鍵清空 👉)</span></div>", unsafe_allow_html=True)
                with hc2:
                    st.markdown("<span class='header-btn-blue'></span>", unsafe_allow_html=True)
                    st.button("", icon=":material/ink_eraser:", key="batch_clear", help="一鍵清空所有筆記", use_container_width=True, on_click=batch_clear_notes)
            
            with h6:
                st.markdown("<span class='header-btn-blue'></span>", unsafe_allow_html=True)
                st.button("", icon=":material/input:", key="batch_quote", help="一鍵帶入所有今日行情", use_container_width=True, on_click=batch_append_quotes)
            with h7:
                st.markdown("<span class='header-btn-blue'></span>", unsafe_allow_html=True)
                st.button("", icon=":material/psychology:", key="batch_dyn", help="一鍵帶入所有籌碼動態", use_container_width=True, on_click=batch_append_dynamics)
            with h8:
                st.markdown("") 
            with h9:
                st.markdown("<span class='header-btn-red'></span>", unsafe_allow_html=True)
                st.button("", icon=":material/delete:", key="batch_delete", help="一鍵移除所有標的", use_container_width=True, on_click=batch_remove_all)
        
        for stock in list(watchlist.keys()):
            nk = f"note_{stock}"
            pure_code = None
            stock_code_match = re.search(r'\d+', stock)
            if stock_code_match: pure_code = stock_code_match.group()

            industry_label = "未知"
            if pure_code and STOCK_DICT and pure_code in STOCK_DICT:
                industry_label = STOCK_DICT[pure_code].get("industry", "未知")

            p_str, v_str = "<span style='color:#555;'>-</span>", "<span style='color:#555;'>-</span>"
            if pure_code and pure_code in market_data:
                d = market_data[pure_code]
                p_str = f"<span style='font-size:16px;'>{d['price']:.2f}</span><br>{fmt_color(d['price_pct'], True)}"
                v_str = f"<span style='font-size:15px;'>{d['vol']:,}</span><br>{fmt_color(d['vol_pct'], False, True)}"
            
            with st.container(border=True):
                st.markdown("<span class='stock-card-marker'></span>", unsafe_allow_html=True)
                c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns(col_ratios)
                
                with c1: st.markdown(f"<div style='padding-top:8px; font-weight:bold; font-size:15px;'>{stock}</div>", unsafe_allow_html=True)
                with c2: st.markdown(f"<div style='padding-top:10px; font-size:12px; color:#38BDF8;'><span style='background-color:#1E293B; padding:2px 5px; border-radius:4px; border: 1px solid #0369a1;'>{industry_label}</span></div>", unsafe_allow_html=True)
                with c3: st.markdown(f"<div style='padding-top:4px;'>{p_str}</div>", unsafe_allow_html=True)
                with c4: st.markdown(f"<div style='padding-top:4px;'>{v_str}</div>", unsafe_allow_html=True)
                
                # 💡 魔法發生處：只要在這個文字框輸入內容，因為 @st.fragment 的保護，它只會重整自己這塊，不會卡死整頁！
                with c5:
                    st.markdown("<div style='padding-top:2px;'>", unsafe_allow_html=True)
                    st.text_area("筆記", key=nk, label_visibility="collapsed", placeholder="點此輸入筆記...", height=68)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                with c6:
                    st.markdown("<div style='padding-top:15px;'>", unsafe_allow_html=True)
                    st.button("", icon=":material/input:", key=f"import_{stock}", use_container_width=True, help="將今日行情寫入筆記", on_click=append_quote_to_note, args=(stock, pure_code))
                    st.markdown("</div>", unsafe_allow_html=True)
                with c7:
                    st.markdown("<div style='padding-top:15px;'>", unsafe_allow_html=True)
                    st.button("", icon=":material/psychology:", key=f"dyn_{stock}", use_container_width=True, help="將籌碼動態寫入筆記", on_click=append_dynamic_to_note, args=(stock, pure_code))
                    st.markdown("</div>", unsafe_allow_html=True)
                with c8:
                    st.markdown("<div style='padding-top:15px;'>", unsafe_allow_html=True)
                    if st.button("", icon=":material/monitoring:", key=f"view_{stock}", use_container_width=True, help="顯示籌碼診斷"):
                        standard_format = stock
                        if pure_code and STOCK_DICT and pure_code in STOCK_DICT:
                            v = STOCK_DICT[pure_code]
                            standard_format = f"{v['id']} {v['name']}"
                        st.session_state["selected_watch_stock"] = standard_format
                        st.session_state["global_search_final"] = standard_format
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                with c9:
                    st.markdown("<div style='padding-top:15px;'>", unsafe_allow_html=True)
                    if st.button("", icon=":material/delete:", key=f"remove_{stock}", use_container_width=True, help="移除此標的"):
                        del watchlist[stock]
                        if nk in st.session_state: del st.session_state[nk]
                        if st.session_state.get("selected_watch_stock") == stock:
                            st.session_state["selected_watch_stock"] = None
                            st.session_state["global_search_final"] = ""
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)


# ==========================================
# 🎨 畫面渲染主程式 (裝載所有 Fragment)
# ==========================================
def show_watchlist_page(STOCK_DICT=None, conn=None, SHEET_URL=None):
    st.markdown("""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            自選名單
        </h2>
    </div>
    """, unsafe_allow_html=True)

    # 🔒 門禁系統
    if not st.session_state.get("logged_in", False):
        st.warning("「這區是 VIP 專屬！請先前往登入頁面註冊或出示邀請函。」")
        if st.button("前往登入", key="go_login_from_watchlist"):
            st.query_params["page"] = "login"
            st.rerun()
        return

    username = st.session_state.get("username", "guest")
    
    # 🗂️ 雙分頁設計
    tab_track, tab_custom = st.tabs(["🔹 權重回測寶庫", "🔹 自訂追蹤名單"])

    # 分別將渲染交給受保護的 Fragment 引擎
    with tab_track:
        render_tab_track(username, conn)

    with tab_custom:
        render_tab_custom(username, conn, SHEET_URL, STOCK_DICT)

    # 回到頂部的 JavaScript 與按鈕 (移到 Fragment 外面確保運作)
    st.markdown('<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />', unsafe_allow_html=True)
    st.markdown(
        """
        <a href="#" id="custom-b2t-btn"
           style="display: flex; justify-content: center; align-items: center; background-color: rgba(14, 165, 233, 0.1); 
                  color: #38bdf8; font-size: 14px; font-weight: bold; padding: 12px; 
                  border-radius: 8px; text-decoration: none; margin-top: 40px; margin-bottom: 20px; 
                  border: 1px solid rgba(56, 189, 248, 0.3); box-shadow: 0px 4px 6px rgba(0,0,0,0.3); gap: 6px;">
            <span class="material-symbols-outlined" style="font-size: 20px;">move_up</span> 
            回到頂部
        </a>
        """, 
        unsafe_allow_html=True
    )
    
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        const parentDoc = window.parent.document;
        const parentWin = window.parent;
        const b2tBtn = parentDoc.getElementById('custom-b2t-btn');
        if (b2tBtn) {
            b2tBtn.onclick = function(e) {
                e.preventDefault(); 
                const containers = [
                    parentDoc.querySelector('[data-testid="stAppViewContainer"]'),
                    parentDoc.querySelector('[data-testid="stMain"]'),
                    parentDoc.documentElement,
                    parentWin
                ];
                containers.forEach(container => {
                    if (container) { try { container.scrollTo({top: 0, behavior: 'smooth'}); } catch(err) {} }
                });
            };
        }
        </script>
        """, height=0, width=0
    )
