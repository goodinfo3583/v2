# views/sidebar.py
import streamlit as st
import pandas as pd
import requests
import re
import base64
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.data_utils import get_latest_csv, get_prev_csv

# ==========================================
# 🌟 "側邊雙視窗" 變數雷達與自動載入各區塊引擎  新增補載頁面1
# ==========================================
KEY_MAP = {
    'b1_final_df': ['b1_final_df', 'my_final_df'],
    'b1_down_final_df': ['b1_down_final_df'],
    'b1_foreign_df': ['b1_foreign_df'],
    'b2_1': ['b2_1', 'df_blk2_1'],
    'b2_2': ['b2_2', 'df_blk2_2'],
    'b2_3': ['b2_3', 'df_blk2_3'],
    'b2_4': ['b2_4', 'df_blk2_4'],
    'b3_main': ['b3_main', 'df_blk3_main'],
    'b4_margin_pct': ['b4_margin_pct', 'df_margin_pct'],
    'b4_short_pct': ['b4_short_pct', 'df_short_pct'],
    'b4_margin_plus_pct': ['b4_margin_plus_pct', 'df_margin_plus_pct'],
    'b4_margin_vol': ['b4_margin_vol', 'df_margin_vol'],
    'b4_short_vol': ['b4_short_vol', 'df_short_vol'],
    'b4_margin_plus_vol': ['b4_margin_plus_vol', 'df_margin_plus_vol'],
    'b5_400': ['b5_400', 'df_blk5'],
    'b5_1000': ['b5_1000', 'df_blk5_1000'],
    'b7_main': ['b7_main', 'df_blk7_main', 'df_b7_main'],
    'b7_pledge': ['b7_pledge', 'df_pledge', 'df_b7_pledge'],
    'b7_pledge_history': ['b7_pledge_history', 'df_pledge_history', 'df_b7_pledge_history'],  
    'broker_history': ['broker_history_df'] 
}

def get_sidebar_df(primary_key):
    """🌟 側邊欄專用萬能變數雷達：支援新舊 Session State 鑰匙"""
    aliases = KEY_MAP.get(primary_key, [primary_key])
    for k in aliases:
        df = st.session_state.get(k)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    return pd.DataFrame()

def ensure_b1_to_b5_loaded(DATA_DIR):
    """🚀 背景自動補載機制：當搜尋時發現數據缺失，自動觸發 B1~B5 後台同步引擎"""
    if not DATA_DIR or not os.path.exists(DATA_DIR):
        return
    # B1 補載
    if get_sidebar_df('b1_final_df').empty:
        try:
            from views.b1_page import sync_b1_data
            sync_b1_data(DATA_DIR)
        except: pass

    # B2 補載
    if get_sidebar_df('b2_1').empty:
        try:
            from views.b2_page import sync_b2_data
            sync_b2_data(DATA_DIR)
        except: pass

    # B3 補載
    if get_sidebar_df('b3_main').empty:
        try:
            from views.b3_page import sync_b3_data
            sync_b3_data(DATA_DIR)
        except: pass

    # B4 補載
    if get_sidebar_df('b4_margin_pct').empty:
        try:
            from views.b4_page import sync_b4_data
            sync_b4_data(DATA_DIR)
        except: pass

    # B5 補載
    if get_sidebar_df('b5_1000').empty:
        try:
            from views.b5_page import sync_b5_data
            sync_b5_data(DATA_DIR)
        except: pass
        
    # B7 補載 
    if get_sidebar_df('b7_main').empty:
        try:
            from views.b7_page import sync_b7_data
            sync_b7_data(DATA_DIR)
        except: pass
        
    # B7 最新質押比 補載
    if get_sidebar_df('b7_pledge').empty:
        try:
            from views.b7_page import sync_pledge_data
            sync_pledge_data(DATA_DIR)
        except: pass

    # B7 質押歷史趨勢 補載
    if get_sidebar_df('b7_pledge_history').empty:
        try:
            from views.b7_page import sync_pledge_history_data
            sync_pledge_history_data(DATA_DIR)
        except: pass 

    # 券商分點歷史明細 補載
    if get_sidebar_df('broker_history').empty:
        try:
            from views.broker_page import load_raw_broker_history
            remote_csv_url = "https://raw.githubusercontent.com/goodinfo3583/tw-broker-data/main/data/broker/broker_history.csv"
            df_broker = load_raw_broker_history(remote_csv_url)
            if not df_broker.empty:
                st.session_state['broker_history_df'] = df_broker
        except: pass

# ==========================================
# 🌟 快搜各頁面與顯示工具函數區 
# ==========================================
def robust_search_engine(df, query):
    if df is None or df.empty: return pd.DataFrame()
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    query = str(query).strip()
    if not query: return pd.DataFrame()

    col_id = '股票代號' if '股票代號' in df.columns else ('代號' if '代號' in df.columns else None)
    col_name = '股票名稱' if '股票名稱' in df.columns else ('名稱' if '名稱' in df.columns else None)

    if col_id:
        df[col_id] = df[col_id].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    if col_name:
        df[col_name] = df[col_name].astype(str).str.strip()

    exact_mask = pd.Series(False, index=df.index)
    if col_id:
        exact_mask = exact_mask | (df[col_id] == query)
    if col_name:
        exact_mask = exact_mask | (df[col_name].str.lower() == query.lower())

    exact_result = df[exact_mask]
    if not exact_result.empty:
        return exact_result

    partial_mask = pd.Series(False, index=df.index)
    if col_id:
        partial_mask = partial_mask | df[col_id].str.contains(query, na=False)
    if col_name:
        partial_mask = partial_mask | df[col_name].str.contains(query, na=False, case=False)

    return df[partial_mask]

# ==========================================
def scan_and_display(title, session_key, query):
    st.markdown(f"<h6 style='color: #E2E8F0; margin-bottom: 5px;'>{title}</h6>", unsafe_allow_html=True)
    df = get_sidebar_df(session_key)
    if df.empty:
        st.write("⚪ 尚未載入資料表")
        return
    res = robust_search_engine(df, query)
    if not res.empty:
        pct_cols = [c for c in res.columns if '持股' in c or '佔' in c or '%' in c]
        if pct_cols:
            all_zero = True
            for c in pct_cols:
                val = res.iloc[0][c]
                if pd.isna(val): continue
                val_str = str(val).strip().replace('%', '')
                if val_str.lower() in ['', '-', 'nan', 'none', 'null']: continue
                try:
                    if abs(float(val_str)) > 0.0001:
                        all_zero = False
                        break
                except ValueError: continue
            if all_zero:
                st.write("⚪ 未進榜")
                return
        st.dataframe(res, use_container_width=True, hide_index=True)
    else:
        st.write("⚪ 未進榜")

def generate_stock_commentary(query):
    if not query: return ""
    score = 0
    warns = []
    
    for key in ['b2_1', 'b2_2', 'b2_3', 'b2_4']:
        df = get_sidebar_df(key)
        if not df.empty:
            res = robust_search_engine(df, query)
            if not res.empty:
                score += 1.5

    df_b3 = get_sidebar_df('b3_main')
    if not df_b3.empty:
        res = robust_search_engine(df_b3, query)
        if not res.empty:
            score += len(res) * 1.5

    for key in ['b4_margin_pct', 'b4_short_pct', 'b4_margin_plus_pct', 'b4_margin_vol', 'b4_short_vol', 'b4_margin_plus_vol']:
        df = get_sidebar_df(key)
        if not df.empty:
            res = robust_search_engine(df, query)
            if not res.empty:
                score += 0.5

    def check_big_holder(key):
        df = get_sidebar_df(key)
        if not df.empty:
            res = robust_search_engine(df, query)
            if not res.empty:
                for col in res.columns:
                    if "動向" in col or "狀態" in col or "趨勢" in col or "動態" in col:
                        return str(res.iloc[0][col])
        return ""

    b5_trend_400 = check_big_holder('b5_400')
    if "增" in b5_trend_400: score += 2
    elif "減" in b5_trend_400: 
        score -= 2
        warns.append("400張大戶減碼")

    b5_trend_1000 = check_big_holder('b5_1000')
    if "增" in b5_trend_1000: score += 2
    elif "減" in b5_trend_1000: 
        score -= 2
        warns.append("千張超級大戶減碼")

    has_warning = len(warns) > 0
    warn_str = "、".join(warns)
    high_score = score >= 4
    
    if has_warning and high_score:
        return f"⚔️ 【激烈換手】偵測到法人大戶分歧 ({warn_str})，但籌碼動能獲 {score} 分評估！倒貨正被吃下，需嚴設停損。"
    if has_warning and not high_score:
        return f"🚨 【風險警示】大戶正在進行倒貨調節 ({warn_str})，且無強大買盤承接。建議暫避風頭。"
    if "大減" in b5_trend_400 or "大減" in b5_trend_1000:
        return "⚠️ 【大戶撤退】大戶出現明顯『大減』跡象，主力籌碼渙散，建議先行觀望。"
    if score >= 6:
        base_comment = f"🔥 【強勢噴發】籌碼極度優異 (積分: {score})！法人與大戶同步共振做多，具波段上攻潛力。"
        if "大增" in b5_trend_400 or "大增" in b5_trend_1000: base_comment += "大股東籌碼大幅集中，是極佳防守標的。"
        return base_comment
    elif score >= 3: 
        return f"📈 【偏多佈局】主力籌碼進駐 (積分: {score})，法人與券資數據給予支撐。具備穩健的波段潛力。"
    elif score >= 1: 
        return f"🔄 【中性觀望】籌碼表現較為平淡 (積分: {score})，缺乏連續性。建議多看少做。"
    else: 
        return "❄️ 【弱勢整理】未進入任何核心法人與大戶買超榜單，籌碼流失或無主力認養。建議暫不考量。"

def generate_technical_signals(df_sig):
    signals = []
    if df_sig is None or df_sig.empty or len(df_sig) < 20: return signals
    latest_close = df_sig['Close'].iloc[-1]
    latest_vol = df_sig['Volume'].iloc[-1]
    
    vol_20ma = df_sig['Volume'].rolling(window=20).mean().iloc[-2] 
    if pd.notna(vol_20ma) and vol_20ma > 0 and latest_vol > (vol_20ma * 2.5):
        signals.append(f"🧨 爆量出擊：今日成交量達 20 日均量的 {latest_vol/vol_20ma:.1f} 倍！")

    mas = {'5MA': 5, '10MA': 10, '20MA': 20, '60MA': 60, '120MA': 120, '240MA': 240}
    for ma_name, period in mas.items():
        if len(df_sig) >= period:
            ma_val = df_sig['Close'].rolling(window=period).mean().iloc[-1]
            if 0 < (latest_close - ma_val) / ma_val < 0.015:
                signals.append(f"🎯 回測支撐：股價極度貼近 {ma_name} ({ma_val:.2f}) 關鍵支撐線。")

    if len(df_sig) >= 60:
        highest_60d = df_sig['High'].iloc[-60:].max()
        if df_sig['High'].iloc[-1] >= highest_60d:
            signals.append("🚀 波段創高：突破 60 日 (一季) 以來新高點，上攻動能強！")
    return signals

def render_b4_panorama(view_title, keys_and_labels, query, stock_name="-"):
    st.markdown(f"<h5 style='color: #E2E8F0; margin-bottom: 5px;'>{view_title}</h5>", unsafe_allow_html=True)
    
    for label, key in keys_and_labels:
        df = get_sidebar_df(key)
        if not df.empty:
            res = robust_search_engine(df, query)
            if not res.empty:
                st.markdown(f"<div style='font-size:14px; font-weight:bold; color:#38BDF8; margin-top:8px; margin-bottom:4px;'>{label}</div>", unsafe_allow_html=True)
                
                row_data = res.iloc[[0]].copy()
                if '股票代號' not in row_data.columns: row_data.insert(0, '股票代號', query)
                if '股票名稱' not in row_data.columns: row_data.insert(1, '股票名稱', stock_name)
                
                for c in row_data.columns: 
                    row_data[c] = row_data[c].apply(lambda x: str(x)[:-2] if str(x).endswith('.0') else x)
                    
                st.dataframe(row_data, use_container_width=True, hide_index=True)
            else:
                st.markdown(f"<div style='font-size:13px; color:#94a3b8; margin-top:4px; margin-bottom:4px;'>{label}： <span style='color:#E2E8F0;'>⚪ 未進榜</span></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-size:13px; color:#94a3b8; margin-top:4px; margin-bottom:4px;'>{label}： <span style='color:#f59e0b;'>⚠️ 尚未載入</span></div>", unsafe_allow_html=True)

def render_sidebar_broker_tracking(query, display_name):
    df_raw = get_sidebar_df('broker_history')
    if df_raw.empty:
        st.write("⚪ 尚未載入券商資料")
        return
        
    stock_raw = df_raw[df_raw['stock_code'] == str(query)].copy()
    if stock_raw.empty:
        st.write("⚪ 未進榜 (無近期券商資料)")
        return
        
    broker_col = next((c for c in ['broker', 'broker_name', '券商名稱', '券商', 'name'] if c in stock_raw.columns), None)
    if not broker_col: return

    available_dates = sorted(stock_raw['trade_date'].unique(), reverse=True)
    if not available_dates: return
    
    try:
        from utils.data_utils import calculate_chip_concentration
        remote_csv_url = "https://raw.githubusercontent.com/goodinfo3583/tw-broker-data/main/data/broker/broker_history.csv"
        df_trend = calculate_chip_concentration(remote_csv_url, str(query))
        
        if not df_trend.empty:
            latest_data = df_trend.iloc[-1]
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.metric(label=f"最新集中度 ({latest_data['trade_date']})", value=f"{latest_data['concentration_%']}%")
            with m_col2:
                net_buy_val = latest_data['net_buy']
                net_str = f"+{net_buy_val:,}" if net_buy_val > 0 else f"{net_buy_val:,}"
                st.metric(label="主體淨買賣超", value=f"{net_str} 張")
            
            with st.expander("📅 展開查看：近 60 日集中度與淨買超", expanded=False):
                df_trend_disp = df_trend.sort_values('trade_date', ascending=False).head(60).copy()
                df_trend_disp = df_trend_disp[['trade_date', 'net_buy', 'concentration_%']]
                df_trend_disp.columns = ['交易日期', '淨買超(張)', '集中度(%)']
                
                def color_trend(val):
                    try:
                        v = float(val)
                        if v > 0: return 'color: #FF4B4B;'
                        elif v < 0: return 'color: #00E272;'
                    except: pass
                    return 'color: #94A3B8;'
                
                # '集中度(%)': "{:.2f}" 讓小數點強制鎖定在第二位
                if hasattr(df_trend_disp.style, 'map'):
                    styled_trend = df_trend_disp.style.map(color_trend, subset=['淨買超(張)', '集中度(%)']).format({'淨買超(張)': "{:,.0f}", '集中度(%)': "{:.2f}"})
                else:
                    styled_trend = df_trend_disp.style.applymap(color_trend, subset=['淨買超(張)', '集中度(%)']).format({'淨買超(張)': "{:,.0f}", '集中度(%)': "{:.2f}"})
                
                st.dataframe(styled_trend, use_container_width=True, hide_index=True)
            
            st.markdown("<hr style='border-color: rgba(56, 189, 248, 0.3); margin: 10px 0px;'>", unsafe_allow_html=True)
    except Exception as e:
        pass 

    recent_dates = available_dates[:60]
    recent_raw = stock_raw[stock_raw['trade_date'].isin(recent_dates)].copy()
    recent_raw['real_net_vol'] = recent_raw.apply(
        lambda x: abs(x['net_vol']) if x['side'] == 'buy' else -abs(x['net_vol']), axis=1
    )
    
    hoard_df = recent_raw.groupby(broker_col)['real_net_vol'].sum().reset_index()
    hoard_df.columns = [broker_col, '區間淨買賣']
    
    top_5_hoarders = hoard_df[hoard_df['區間淨買賣'] > 0].sort_values('區間淨買賣', ascending=False).head(5)
    
    if top_5_hoarders.empty:
        st.write("⚪ 近 60 日無明顯囤貨分點")
        return
        
    top_5_names = top_5_hoarders[broker_col].tolist()
    
    st.markdown("<h6 style='color: #E2E8F0; margin-top: 5px; margin-bottom: 5px;'>📈 近 60 日囤貨分點 (前 5 名)</h6>", unsafe_allow_html=True)
    styled_hoard = top_5_hoarders.copy()
    styled_hoard.columns = ['中文券商分點', '淨買超(張)']
    styled_hoard = styled_hoard.style.format({'淨買超(張)': "{:,.0f}"})
    st.dataframe(styled_hoard, use_container_width=True, hide_index=True)
    
    st.markdown("<h6 style='color: #E2E8F0; margin-top: 10px; margin-bottom: 5px;'>🗺️ 囤貨分點進出矩陣 (近 15 日)</h6>", unsafe_allow_html=True)
    
    matrix_raw = stock_raw[stock_raw[broker_col].isin(top_5_names)].copy()
    matrix_raw['signed_vol'] = matrix_raw.apply(
        lambda x: abs(x['net_vol']) if x['side'] == 'buy' else -abs(x['net_vol']), axis=1
    )
    
    full_pivot = matrix_raw.pivot_table(index=broker_col, columns='trade_date', values='signed_vol', aggfunc='sum')
    all_dates_sorted = sorted(full_pivot.columns, reverse=True)
    
    display_dates = available_dates[:15]
    display_dates = [d for d in display_dates if d in full_pivot.columns]
    pivot_df = full_pivot[display_dates].copy()
    
    def calc_daily_streak(row_name):
        if row_name not in full_pivot.index: return "-"
        row = full_pivot.loc[row_name]
        streak = 0
        sign = None
        for c in all_dates_sorted:
            val = row.get(c, 0)
            if pd.isna(val) or val == 0: break
            current_sign = 1 if val > 0 else -1
            if sign is None:
                sign = current_sign
                streak = sign
            elif sign == current_sign:
                streak += sign
            else:
                break
        if streak > 0: return f"連買 {streak} 日"
        elif streak < 0: return f"連賣 {-streak} 日"
        else: return "-"

    pivot_df['日連買動態'] = pivot_df.index.to_series().apply(calc_daily_streak)
    pivot_df = pivot_df.reindex(top_5_names) 
    pivot_df[display_dates] = pivot_df[display_dates].fillna("-")
    pivot_df.index.name = "中文券商分點"
    
    cols = ['日連買動態'] + display_dates
    pivot_df = pivot_df[cols]
    
    def color_net_vol(val):
        if isinstance(val, str):
            if val == "-": return 'color: #64748B;'
            if "連買" in val: return 'color: #FF4B4B;'
            if "連賣" in val: return 'color: #00E272;'
        try:
            v = float(val)
            if v > 0: return 'color: #FF4B4B;'
            elif v < 0: return 'color: #00E272;'
        except: pass
        return 'color: #94A3B8;'

    if hasattr(pivot_df.style, 'map'):
        styled_pivot = pivot_df.style.map(color_net_vol).format(lambda x: "{:,.0f}".format(x) if isinstance(x, (int, float)) else x)
    else:
        styled_pivot = pivot_df.style.applymap(color_net_vol).format(lambda x: "{:,.0f}".format(x) if isinstance(x, (int, float)) else x)
    
    st.dataframe(styled_pivot, use_container_width=True)

# ==========================================
# 📈 側邊雙視窗 K 線圖與技術分析引擎
# ==========================================
# 💡 效能優化：加入 show_spinner=False，避免畫面卡頓跳動
@st.cache_data(show_spinner=False, ttl=900)
def fetch_yfinance_data(ticker, period="3y"):
    import yfinance as yf
    try:
        df = yf.download(ticker, period=period, progress=False)
        return df
    except:
        return pd.DataFrame()

def render_technical_chart(stock_id, timeframe="日線", selected_mas=[], show_rsi=False, show_macd=False, show_kd=False):
    ticker_tw = f"{stock_id}.TW"
    ticker_two = f"{stock_id}.TWO"
    
    df = fetch_yfinance_data(ticker_tw)
    if df is None or df.empty:
        df = fetch_yfinance_data(ticker_two)
        
    if df is None or df.empty:
        st.warning(f"⚠️ 無法取得 {stock_id} 的即時報價。")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.loc[:, ~df.columns.duplicated()]

    if df.index.tz is not None: df.index = df.index.tz_convert('Asia/Taipei')
    else: df.index = df.index.tz_localize('UTC').tz_convert('Asia/Taipei')

    daily_df = df.copy()
            
    if timeframe == "週線":
        daily_df = daily_df.resample('W-FRI').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
    elif timeframe == "月線":
        daily_df = daily_df.resample('ME').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

    for ma in [5, 10, 20, 60, 120, 240]:
        daily_df[f'{ma}MA'] = daily_df['Close'].rolling(window=ma).mean()

    close_series = daily_df['Close'].squeeze()
    
    if show_rsi:
        delta = close_series.diff()
        gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
        ema_gain = gain.ewm(com=13, adjust=False).mean(); ema_loss = loss.ewm(com=13, adjust=False).mean()
        rs = ema_gain / ema_loss.replace(0, 1e-9)
        daily_df['RSI'] = 100 - (100 / (1 + rs))

    if show_macd:
        ema12 = close_series.ewm(span=12, adjust=False).mean(); ema26 = close_series.ewm(span=26, adjust=False).mean()
        daily_df['DIF'] = ema12 - ema26
        daily_df['MACD_Sign'] = daily_df['DIF'].ewm(span=9, adjust=False).mean()
        daily_df['MACD_Hist'] = daily_df['DIF'] - daily_df['MACD_Sign']
        
    if show_kd:
        low_9 = daily_df['Low'].rolling(window=9).min(); high_9 = daily_df['High'].rolling(window=9).max()
        rsv = (close_series - low_9) / (high_9 - low_9).replace(0, 1e-9) * 100
        daily_df['K'] = rsv.ewm(com=2, adjust=False).mean()
        daily_df['D'] = daily_df['K'].ewm(com=2, adjust=False).mean()

    def get_latest_price(col):
        valid_data = daily_df[col].dropna()
        if not valid_data.empty:
            val = valid_data.iloc[-1]
            if isinstance(val, pd.Series): val = val.iloc[0]
            return f"{float(val):.2f}"
        return "-"

    rows = 2
    row_heights = [0.5, 0.15]
    if show_rsi: rows += 1; row_heights.append(0.12)
    if show_macd: rows += 1; row_heights.append(0.14)
    if show_kd: rows += 1; row_heights.append(0.14)

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=row_heights)
                                        
    up_color = 'rgb(240, 90, 90)'     
    down_color = 'rgb(80, 200, 120)'  

    fig.add_trace(go.Candlestick(
        x=daily_df.index, open=daily_df['Open'], high=daily_df['High'], 
        low=daily_df['Low'], close=daily_df['Close'], name='K線', 
        increasing=dict(line=dict(color=up_color, width=1.5), fillcolor=up_color),
        decreasing=dict(line=dict(color=down_color, width=1.5), fillcolor=down_color),
        hovertemplate="開：%{open:.2f}<br>高：%{high:.2f}<br>低：%{low:.2f}<br>收：%{close:.2f}<extra></extra>"
    ), row=1, col=1)
    
    fig.update_yaxes(title_text="股價 (TWD)", row=1, col=1, title_font=dict(size=12, color="#E2E8F0"), rangemode="nonnegative")

    if not daily_df.empty:
        max_price = daily_df['High'].max()
        max_date = daily_df['High'].idxmax()
        fig.add_hline(y=max_price, line_dash="dot", line_color="rgba(255, 215, 0, 0.4)", row=1, col=1)
        fig.add_annotation(
            x=max_date, y=max_price, text=f"<b>前高: {max_price:.2f}</b>",
            showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="#FFD700", ax=0, ay=-40, 
            font=dict(size=13, color="#FFD700"), bgcolor="rgba(17, 22, 34, 0.85)", bordercolor="#FFD700", borderwidth=1, borderpad=4, row=1, col=1
        )

    ma_config = {
        '5MA': {'color': '#FFFF37'}, '10MA': {'color': '#00FFFF'},
        '20MA': {'color': '#921AFF'}, '60MA': {'color': '#D0D0D0'},
        '120MA': {'color': '#D200D2'}, '240MA': {'color': '#BB3D00'}
    }
    for ma_name in selected_mas:
        if ma_name in daily_df.columns:
            latest_val = get_latest_price(ma_name)
            fig.add_trace(go.Scatter(
                x=daily_df.index, y=daily_df[ma_name], mode='lines', 
                name=f'{ma_name} ({latest_val})', line=dict(color=ma_config[ma_name]['color'], width=1.3),
                hovertemplate=f"<b>{ma_name}</b>： %{{y:.2f}}<extra></extra>"
            ), row=1, col=1)

    vol_colors = [up_color if c >= o else down_color for c, o in zip(daily_df['Close'], daily_df['Open'])]
    fig.add_trace(go.Bar(
        x=daily_df.index, y=daily_df['Volume'], name='成交量', 
        marker_color=vol_colors, showlegend=False, hovertemplate="<b>成交量</b>： %{y}<extra></extra>"
    ), row=2, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1, title_font=dict(size=12, color="#E2E8F0"), rangemode="nonnegative")

    current_row = 3
    if show_kd:
        fig.add_trace(go.Scatter(x=daily_df.index, y=daily_df['K'], mode='lines', name='K (9)', line=dict(color='#00CCFF', width=1.2), hovertemplate="<b>K</b>: %{y:.2f}<extra></extra>"), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=daily_df.index, y=daily_df['D'], mode='lines', name='D (3)', line=dict(color='#FFCC00', width=1.2), hovertemplate="<b>D</b>: %{y:.2f}<extra></extra>"), row=current_row, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color="rgba(240,90,90,0.4)", row=current_row, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="rgba(80,200,120,0.4)", row=current_row, col=1)
        fig.update_yaxes(title_text="KD(9,3,3)", row=current_row, col=1, title_font=dict(size=11, color="#E2E8F0"))
        current_row += 1
        
    if show_rsi:
        fig.add_trace(go.Scatter(x=daily_df.index, y=daily_df['RSI'], mode='lines', name='RSI (14)', line=dict(color='#E1BEE7', width=1.5), hovertemplate="<b>RSI</b>: %{y:.2f}<extra></extra>"), row=current_row, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color="rgba(240,90,90,0.4)", row=current_row, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="rgba(80,200,120,0.4)", row=current_row, col=1)
        fig.update_yaxes(title_text="RSI(14)", row=current_row, col=1, title_font=dict(size=11, color="#E2E8F0"))
        current_row += 1

    if show_macd:
        fig.add_trace(go.Scatter(x=daily_df.index, y=daily_df['DIF'], mode='lines', name='DIF', line=dict(color='#FFF', width=1)), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=daily_df.index, y=daily_df['MACD_Sign'], mode='lines', name='MACD', line=dict(color='#FFCC00', width=1)), row=current_row, col=1)
        hist_colors = [up_color if h >= 0 else down_color for h in daily_df['MACD_Hist']]
        fig.add_trace(go.Bar(x=daily_df.index, y=daily_df['MACD_Hist'], name='柱狀圖', marker_color=hist_colors), row=current_row, col=1)
        fig.update_yaxes(title_text="MACD", row=current_row, col=1, title_font=dict(size=11, color="#E2E8F0"))
        current_row += 1

    fig.update_layout(
        xaxis_rangeslider_visible=False, height=500 + (rows - 1) * 110, 
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',  
        margin=dict(l=10, r=65, t=30, b=10), hovermode='x unified',
        hoverlabel=dict(bgcolor="#1A202C", font_size=15, font_color="#FFFFFF"),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0.01, font=dict(color='#E2E8F0', size=16), itemsizing='constant'),
        dragmode='pan' 
    )
    
    fig.update_xaxes(showspikes=True, spikecolor="rgba(255, 235, 100, 0.5)", spikesnap="cursor", spikemode="across", spikethickness=0.5, spikedash="dash", gridcolor="rgba(255, 255, 255, 0.05)")
    fig.update_yaxes(showspikes=True, spikecolor="rgba(255, 235, 100, 0.5)", spikesnap="cursor", spikemode="across", spikethickness=0.5, spikedash="dash", side="right", gridcolor="rgba(255, 255, 255, 0.05)")
    
    for r in range(1, rows + 1): fig.update_xaxes(hoverformat="%Y-%m-%d", tickformat="%Y-%m-%d", row=r, col=1)
    
    if not daily_df.empty:
        latest_date = daily_df.index[-1] 
        start_date = latest_date - pd.Timedelta(days=140) 
        zoom_range = [start_date.strftime('%Y-%m-%d'), latest_date.strftime('%Y-%m-%d')]
        for r in range(1, rows + 1): fig.update_xaxes(range=zoom_range, row=r, col=1)
    
    if timeframe == "日線":
        all_days = pd.date_range(start=daily_df.index.min().normalize(), end=daily_df.index.max().normalize(), freq='D')
        actual_days = daily_df.index.normalize()
        missing_days = all_days.difference(actual_days).strftime('%Y-%m-%d').tolist()
        for r in range(1, rows + 1): fig.update_xaxes(rangebreaks=[dict(values=missing_days)], row=r, col=1)
    
    plotly_config = {'scrollZoom': True, 'displaylogo': False, 'modeBarButtonsToRemove': ['zoom2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'select2d', 'lasso2d', 'hoverClosestCartesian', 'hoverCompareCartesian', 'toggleSpikelines']}
    st.plotly_chart(fig, use_container_width=True, key=f"kline_{stock_id}_{timeframe}_{len(selected_mas)}_{show_rsi}_{show_macd}_{show_kd}", config=plotly_config)

# ======================================================
# 分頁功能渲染區: 🔹 大盤籌碼 🔹 選擇權 🔹 總經導航
# ======================================================
def get_diff_ui(current, prev):
    if prev is None or pd.isna(prev): return ""
    diff = current - prev
    if diff > 0: return f" <span style='color: #ff4b4b; font-size: 11px;'>(+{int(diff):,})</span>"
    elif diff < 0: return f" <span style='color: #00e676; font-size: 11px;'>({int(diff):,})</span>"
    return ""

def render_sidebar_market_summary():
    df_spot, date_spot = get_latest_csv("三大法人買賣超金額")
    df_fut, _ = get_latest_csv("三大法人期貨多空")
    df_fut_prev = get_prev_csv("三大法人期貨多空", date_spot)
    df_margin, margin_csv_name = get_latest_csv("融資融券餘額")
    
    df_twse, _ = get_latest_csv("大盤上市成交量")
    df_tpex, _ = get_latest_csv("大盤上櫃成交量")
    
    if df_spot is None or df_fut is None:
        st.warning("尚無大盤數據，請確認資料夾中已有今日 CSV。")
        return "未知"

    net_foreign, net_trust, net_dealer, net_total = 0.0, 0.0, 0.0, 0.0
    for _, row in df_spot.iterrows():
        name = str(row.get('單位名稱', ''))
        try: val = float(str(row.get('買賣差額', '0')).replace(',', '')) / 100000000
        except: val = 0.0
        if '外資' in name and '不含' in name: net_foreign += val
        elif '外資自營商' in name: net_foreign += val
        elif '投信' in name: net_trust += val
        elif '自營商' in name: net_dealer += val
        elif '合計' in name: net_total = val

    oi_foreign, oi_trust, oi_dealer = 0, 0, 0
    if df_fut is not None:
        target_oi_col = next((c for c in df_fut.columns if '未平倉' in c and '多空淨額' in c), None)
        if target_oi_col:
            for _, row in df_fut.iterrows():
                row_vals = " ".join([str(x) for x in row.values])
                if '臺股期貨' in row_vals:
                    iden = str(row.values[2]) 
                    try: val = int(str(row[target_oi_col]).replace(',', ''))
                    except: val = 0
                    if '外資' in iden: oi_foreign = val
                    elif '投信' in iden: oi_trust = val
                    elif '自營商' in iden: oi_dealer = val
    total_oi = oi_foreign + oi_trust + oi_dealer

    oi_f_prev, oi_t_prev, oi_d_prev = None, None, None
    if df_fut_prev is not None:
        t_col_prev = next((c for c in df_fut_prev.columns if '未平倉' in c and '多空淨額' in c), None)
        if t_col_prev:
            for _, row in df_fut_prev.iterrows():
                r_vals = " ".join([str(x) for x in row.values])
                if '臺股期貨' in r_vals:
                    iden = str(row.values[2]) 
                    try: val = int(str(row[t_col_prev]).replace(',', ''))
                    except: val = 0
                    if '外資' in iden: oi_f_prev = val
                    elif '投信' in iden: oi_t_prev = val
                    elif '自營商' in iden: oi_d_prev = val

    margin_diff_yi, margin_today_yi = 0.0, 0.0
    if df_margin is not None:
        for _, row in df_margin.iterrows():
            row_list = [str(x).replace(',', '').strip() for x in row.values]
            row_str = "".join(row_list)
            if '融資金額' in row_str:
                try:
                    margin_prev = float(row_list[-2]) 
                    margin_today = float(row_list[-1])
                    margin_diff_yi = (margin_today - margin_prev) / 100000
                    margin_today_yi = margin_today / 100000
                    break
                except: pass

    twse_vol_today, twse_diff = 0.0, 0.0
    if df_twse is not None and len(df_twse) >= 2:
        try:
            v_today = float(str(df_twse.iloc[-1]['成交金額']).replace(',', '')) / 100000000
            v_yest = float(str(df_twse.iloc[-2]['成交金額']).replace(',', '')) / 100000000
            twse_vol_today = v_today
            twse_diff = v_today - v_yest
        except: pass

    tpex_vol_today, tpex_diff = 0.0, 0.0
    if df_tpex is not None and len(df_tpex) >= 2:
        try:
            v_today = float(str(df_tpex.iloc[-1]['成交金額(千元)']).replace(',', '')) / 100000
            v_yest = float(str(df_tpex.iloc[-2]['成交金額(千元)']).replace(',', '')) / 100000
            tpex_vol_today = v_today
            tpex_diff = v_today - v_yest
        except: pass

    total_vol_today = twse_vol_today + tpex_vol_today
    total_diff = twse_diff + tpex_diff

    def get_color(val, is_float=True):
        if val > 0: return "#ff4b4b", f"+{val:,.1f}" if is_float else f"+{val:,}"
        elif val < 0: return "#00e676", f"{val:,.1f}" if is_float else f"{val:,}"
        return "#e0e0e0", "0.0" if is_float else "0"

    f_c, f_s = get_color(net_foreign)
    t_c, t_s = get_color(net_trust)
    d_c, d_s = get_color(net_dealer)
    to_c, to_s = get_color(net_total)
    fo_c, fo_s = get_color(oi_foreign, False)
    to_oc, to_os = get_color(oi_trust, False)
    do_c, do_os = get_color(oi_dealer, False)
    too_c, too_os = get_color(total_oi, False)
    m_c, m_s = get_color(margin_diff_yi)
    
    tw_c, tw_s = get_color(twse_diff)
    tp_c, tp_s = get_color(tpex_diff)
    tot_c, tot_s = get_color(total_diff)

    html = f"<div style='font-size: 13px; color: #00D2FF;'>基準日：{date_spot}</div>"
    
    html += "<table style='width: 100%; text-align: center; border-collapse: collapse; margin-top: 5px; font-size: 14px;'>"
    html += "<tr style='border-bottom: 1px solid #555; background-color: #262730;'>"
    html += "<th style='padding: 5px;'>法人</th><th style='padding: 5px;'>現貨(億)</th><th style='padding: 5px;'>TX未平倉</th></tr>"
    html += f"<tr><td style='padding: 4px;'>🌐 外資</td><td style='color: {f_c}; vertical-align: middle;'>{f_s}</td><td style='color: {fo_c}; vertical-align: middle; padding-bottom: 6px;'>{fo_s}{get_diff_ui(oi_foreign, oi_f_prev)}</td></tr>"
    html += f"<tr><td style='padding: 4px;'>🏦 投信</td><td style='color: {t_c}; vertical-align: middle;'>{t_s}</td><td style='color: {to_oc}; vertical-align: middle; padding-bottom: 6px;'>{to_os}{get_diff_ui(oi_trust, oi_t_prev)}</td></tr>"
    html += f"<tr><td style='padding: 4px;'>🏢 自營商</td><td style='color: {d_c}; vertical-align: middle;'>{d_s}</td><td style='color: {do_c}; vertical-align: middle; padding-bottom: 6px;'>{do_os}{get_diff_ui(oi_dealer, oi_d_prev)}</td></tr>"
    
    tot_prev = (oi_f_prev + oi_t_prev + oi_d_prev) if oi_f_prev is not None else None
    html += f"<tr style='border-top: 1px solid #555; font-weight: bold;'><td style='padding: 4px;'> 合計</td><td style='color: {to_c}; vertical-align: middle;'>{to_s}</td><td style='color: {too_c}; vertical-align: middle; padding-bottom: 6px;'>{too_os}{get_diff_ui(total_oi, tot_prev)}</td></tr>"
    html += "</table>"
    
    if total_vol_today > 0:
        html += "<div style='margin-top: 8px; padding: 6px; background-color: #1e1e24; border: 1px solid #555; border-radius: 5px; font-size: 13px;'>"
        html += "<div style='font-weight: bold; margin-bottom: 4px;'>市場成交量 (億)</div>"
        html += f"<div style='color: #aaa; margin-top: 2px;'> 上市 <span style='float: right; color: #fff;'>{twse_vol_today:,.1f} <span style='color: {tw_c}; font-size: 11px; margin-left: 2px;'>({tw_s})</span></span></div>"
        html += f"<div style='color: #aaa; margin-top: 2px;'> 上櫃 <span style='float: right; color: #fff;'>{tpex_vol_today:,.1f} <span style='color: {tp_c}; font-size: 11px; margin-left: 2px;'>({tp_s})</span></span></div>"
        html += "<div style='border-top: 1px dashed #555; margin: 4px 0;'></div>"
        html += f"<div style='color: #fbbf24; font-weight: bold; margin-top: 2px;'> 總量 <span style='float: right;'>{total_vol_today:,.1f} <span style='color: {tot_c}; font-size: 11px; margin-left: 2px;'>({tot_s})</span></span></div>"
        html += "</div>"
    
    if margin_today_yi != 0.0:
        margin_date = margin_csv_name[:8] if margin_csv_name else "未知"
        html += "<div style='margin-top: 8px; padding: 6px; background-color: #1e1e24; border: 1px solid #555; border-radius: 5px; font-size: 13px;'>"
        html += f"<div style='font-weight: bold;'>大盤融資餘額 <span style='font-size: 13px; color: #00D2FF; font-weight: normal; margin-left: 5px;'>({margin_date})</span></div>"
        html += f"<div style='color: #aaa; margin-top: 4px;'>今日增減(億) <span style='color: {m_c}; font-weight: bold; float: right;'>{m_s}</span></div>"
        html += f"<div style='color: #aaa; margin-top: 2px;'>餘額總計(億) <span style='float: right; color: #fff;'>{margin_today_yi:,.1f}</span></div>"
        html += "</div>"
        
    st.markdown(html, unsafe_allow_html=True)
    return date_spot

def render_options_dashboard():
    df_opt, date_opt = get_latest_csv("臺指選擇權行情簡表")
    df_pcr, _ = get_latest_csv("臺指選擇權PC比")
    df_opt_prev = get_prev_csv("臺指選擇權行情簡表", date_opt)
    
    if date_opt and date_opt != "未知":
        st.markdown(f"<div style='font-size: 13px; color: #00D2FF; margin-bottom: 12px;'>基準日：{date_opt}</div>", unsafe_allow_html=True)
    
    if df_opt is None:
        st.warning("尚無選擇權資料。")
        return

    pcr_val = 0.0
    if df_pcr is not None:
        pcr_col = next((c for c in df_pcr.columns if '買賣權未平倉量比率' in c), None)
        if pcr_col:
            try: pcr_val = float(str(df_pcr[pcr_col].dropna().iloc[-1]).replace('%', ''))
            except: pass
    pcr_color = "#FF4B4B" if pcr_val > 100 else "#00E272"
    st.markdown(f"**PCR:** <span style='color:{pcr_color}; font-size: 16px;'>{pcr_val}%</span>", unsafe_allow_html=True)

    col_strike = next((c for c in df_opt.columns if '履約價' in c), None)
    col_type = next((c for c in df_opt.columns if '買賣權' in c), None)
    col_oi = next((c for c in df_opt.columns if '未沖銷' in c or '未平倉' in c), None)
    col_month = next((c for c in df_opt.columns if '到期' in c or '月份' in c), None)
    
    if not all([col_strike, col_type, col_oi, col_month]):
        st.info("🔄 選擇權格式讀取失敗。")
        return

    valid_months = [m for m in df_opt[col_month].dropna().unique() if str(m).startswith('20')]
    if not valid_months: return
    front_month = sorted(valid_months)[0]
    df_opt = df_opt[df_opt[col_month] == front_month].copy()

    df_opt[col_strike] = pd.to_numeric(df_opt[col_strike], errors='coerce')
    df_opt[col_oi] = pd.to_numeric(df_opt[col_oi].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    df_call = df_opt[df_opt[col_type].str.contains('Call|買權', case=False, na=False)].copy()
    df_put = df_opt[df_opt[col_type].str.contains('Put|賣權', case=False, na=False)].copy()
    
    top_calls = df_call.nlargest(2, col_oi).reset_index(drop=True)
    top_puts = df_put.nlargest(2, col_oi).reset_index(drop=True)
    max_pressure = int(top_calls.loc[0, col_strike]) if not top_calls.empty else 0
    max_support = int(top_puts.loc[0, col_strike]) if not top_puts.empty else 0

    prev_oi_dict = {}
    if df_opt_prev is not None and col_strike in df_opt_prev.columns:
        valid_months_p = [m for m in df_opt_prev[col_month].dropna().unique() if str(m).startswith('20')]
        if valid_months_p:
            f_month_p = sorted(valid_months_p)[0]
            df_opt_prev = df_opt_prev[df_opt_prev[col_month] == f_month_p]
            df_opt_prev[col_strike] = pd.to_numeric(df_opt_prev[col_strike], errors='coerce')
            df_opt_prev[col_oi] = pd.to_numeric(df_opt_prev[col_oi].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            
            for _, row in df_opt_prev.iterrows():
                strike_val = row[col_strike]
                if pd.isna(strike_val): continue
                strike_val = int(strike_val)
                type_val = str(row[col_type])
                oi_val = int(row[col_oi])
                
                if strike_val not in prev_oi_dict: prev_oi_dict[strike_val] = {'c': 0, 'p': 0}
                if 'Call' in type_val or '買權' in type_val: prev_oi_dict[strike_val]['c'] += oi_val
                if 'Put' in type_val or '賣權' in type_val: prev_oi_dict[strike_val]['p'] += oi_val

    start_strike = int(max_pressure) + 2000
    end_strike = int(max_support) - 3000
    if start_strike >= 36000 and end_strike < 36000: end_strike = 36000
        
    display_strikes = list(range(start_strike, end_strike - 1, -1000))
    
    html_opt = "<table style='width: 100%; text-align: center; border-collapse: collapse; margin-top: 5px; font-size: 13px;'>"
    html_opt += "<tr style='border-bottom: 1px solid #555; background-color: #262730;'>"
    html_opt += "<th style='padding: 5px;'>點位</th><th style='padding: 5px;'>⚔️ Call (口)</th><th style='padding: 5px;'>🛡️ Put (口)</th></tr>"
    
    for strike in display_strikes:
        c_val = df_call[df_call[col_strike] == strike][col_oi].sum()
        p_val = df_put[df_put[col_strike] == strike][col_oi].sum()
        if c_val == 0 and p_val == 0: continue
            
        strike_label = str(strike)
        if strike == max_pressure: strike_label += "<br><span style='color:#FF4B4B; font-size:10px;'>(最壓)</span>"
        elif strike == max_support: strike_label += "<br><span style='color:#00E272; font-size:10px;'>(最撐)</span>"

        prev_c = prev_oi_dict.get(strike, {}).get('c', None)
        prev_p = prev_oi_dict.get(strike, {}).get('p', None)

        html_opt += f"<tr style='border-bottom: 1px solid #333;'>"
        html_opt += f"<td style='padding: 6px; font-weight: bold; vertical-align: middle;'>{strike_label}</td>"
        html_opt += f"<td style='padding: 6px; color: #FF4B4B; vertical-align: middle;'>{int(c_val):,}{get_diff_ui(c_val, prev_c)}</td>"
        html_opt += f"<td style='padding: 6px; color: #00E272; vertical-align: middle;'>{int(p_val):,}{get_diff_ui(p_val, prev_p)}</td>"
        html_opt += f"</tr>"
        
    html_opt += "</table>"
    st.markdown(html_opt, unsafe_allow_html=True)

# 💡 效能優化：加入 show_spinner=False，避免背景讀取時畫面跳動
@st.cache_data(show_spinner=False, ttl=300) 
def fetch_macro_indicators():
    data = {
        "vix": {"value": None, "pct": None},
        "vixtwn": {"value": None, "pct": None},
        "fng": {"score": None, "rating": "無法取得"}
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9"
    }

    try:
        yf_url = "https://query1.finance.yahoo.com/v8/finance/chart/^VIX?interval=1d&range=5d"
        res_us = requests.get(yf_url, headers=headers, timeout=5)
        if res_us.status_code == 200:
            us_json = res_us.json()
            closes = us_json['chart']['result'][0]['indicators']['quote'][0]['close']
            valid_closes = [c for c in closes if c is not None]
            if len(valid_closes) >= 2:
                latest = float(valid_closes[-1])
                prev = float(valid_closes[-2])
                data["vix"]["value"] = latest
                data["vix"]["pct"] = (latest - prev) / prev * 100
    except: pass

    prev_vix = None
    try:
        res_daily = requests.get("https://www.taifex.com.tw/cht/3/vixInfo", headers=headers, timeout=5)
        if res_daily.status_code == 200:
            matches_d = re.findall(r'(\d{3,4}/\d{2}/\d{2})[\s\S]{1,100}?([1-9]\d{1,2}\.\d{2,4})', res_daily.text)
            if matches_d:
                data["vixtwn"]["value"] = float(matches_d[-1][1])
                if len(matches_d) >= 2:
                    prev_vix = float(matches_d[-2][1])
                    data["vixtwn"]["pct"] = (data["vixtwn"]["value"] - prev_vix) / prev_vix * 100
    except: pass

    try:
        res_min = requests.get("https://www.taifex.com.tw/cht/7/vixMinNew", headers=headers, timeout=5)
        if res_min.status_code == 200:
            matches_m = re.findall(r'(\d{2}:\d{2}:\d{2})[\s\S]{1,100}?([1-9]\d{1,2}\.\d{2,4})', res_min.text)
            if matches_m:
                latest_vix = float(matches_m[-1][1])
                data["vixtwn"]["value"] = latest_vix
                if prev_vix:
                    data["vixtwn"]["pct"] = (latest_vix - prev_vix) / prev_vix * 100
    except: pass

    if data["vixtwn"]["value"] is None:
        try:
            res_hi = requests.get("https://histock.tw/stock/tcharti.aspx?no=VIXTWN", headers=headers, timeout=5)
            if res_hi.status_code == 200:
                match = re.search(r'CPHB1_lblPrice[^>]*>\s*([\d\.]+)\s*<', res_hi.text)
                if match:
                    data["vixtwn"]["value"] = float(match.group(1))
                    data["vixtwn"]["pct"] = 0.0
        except: pass

    try:
        headers_cnn = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
            "Referer": "https://edition.cnn.com/"
        }
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, headers=headers_cnn, timeout=5)
        if res.status_code == 200:
            fg_data = res.json()
            score = int(fg_data['fear_and_greed']['score'])
            if score < 15: rating_tw = "🉐 分批加碼"
            elif score < 25: rating_tw = "🈵 積極買點"
            elif score > 90: rating_tw = "🈲 提高現金"
            elif score > 85: rating_tw = "🈹 獲利了結"
            elif score > 75: rating_tw = "🈴 分批減碼"
            else: rating_tw = "⚖️ 中立平穩"
            data["fng"]["score"] = score
            data["fng"]["rating"] = rating_tw
    except: pass

    return data


# =======================================================
# 🎨 自訂圖片轉換引擎：讓標題輕鬆鑲嵌本地圖片
# =======================================================
def get_img_html(filename, height="28px"):
    img_path = f"./static/{filename}"
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        return f'<img src="data:image/png;base64,{img_b64}" style="height: {height}; vertical-align: text-bottom; margin-right: 8px;">'
    return "" 
# =======================================================
# 🚀 效能優化快取區塊：將 Plotly 圖表繪製獨立出來並快取
# =======================================================
@st.cache_data(show_spinner=False, ttl=300)
def create_b1_bar_chart(stock_name, clean_x_labels, y_vals):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=clean_x_labels, y=y_vals,  
        marker_color=['#FF4B4B' if i == len(y_vals)-1 else '#4B8BFF' for i in range(len(y_vals))],
        text=[f"{v}%" if v > 0 else "" for v in y_vals], textposition='outside'
    ))
    fig.update_layout(
        title=dict(text=f"📈 持股波段真實軌跡 ({stock_name})", font=dict(color="#E2E8F0")),
        height=300, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis=dict(title="持股比例 (%)", showgrid=True, gridcolor='#334155'), xaxis=dict(tickangle=45), dragmode='pan'
    )
    return fig

@st.cache_data(show_spinner=False, ttl=300)
def create_b1_down_bar_chart(stock_name_down, clean_x_labels_down, y_vals_down):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=clean_x_labels_down, y=y_vals_down,
        marker_color=['#00E676' if i == len(y_vals_down)-1 else '#0284C7' for i in range(len(y_vals_down))],
        text=[f"{v}%" if v > 0 else "" for v in y_vals_down], textposition='outside'
    ))
    fig.update_layout(
        title=dict(text=f"📉 衰退波段真實軌跡 ({stock_name_down})", font=dict(color="#E2E8F0")),
        height=300, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis=dict(title="持股比例 (%)", showgrid=True, gridcolor='#334155'), xaxis=dict(tickangle=45), dragmode='pan'
    )
    return fig

@st.cache_data(show_spinner=False, ttl=300)
def create_foreign_bar_chart(clean_x_for, y_vals_for):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=clean_x_for, y=y_vals_for,
        marker_color='#38BDF8',
        text=[f"{v}%" if v > 0 else "" for v in y_vals_for], textposition='outside'
    ))
    fig.update_layout(
        title=dict(text=f"🌎 外資持股 20日軌跡", font=dict(color="#E2E8F0", size=13)),
        height=250, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(title="外資持股 (%)", showgrid=True, gridcolor='#334155'), xaxis=dict(tickangle=45), dragmode='pan'
    )
    return fig

# =======================================================
# 🚀 終極局部渲染魔法：將整個側邊視窗獨立為「不閃爍區塊」
# =======================================================
@st.fragment
def render_sidebar_war_room(STOCK_DICT, DATA_DIR="data"):
    st.markdown("<div id='section-search'></div>", unsafe_allow_html=True)
    # ==========================================
    # 🌟 新增：追蹤名單聯動顯示區塊 (放在最頂端)
    # ==========================================
    if st.session_state.get("logged_in", False):
        selected_stock = st.session_state.get("selected_watch_stock", None)
        
        if selected_stock:
            st.markdown(f"### 🎯 焦點標的：{selected_stock}")
            
            stock_code_match = re.search(r'\d+', selected_stock)
            if stock_code_match:
                stock_code = stock_code_match.group()
                col_l1, col_l2, col_l3 = st.columns(3)
                with col_l1: 
                    st.markdown(f"[🔗Goodinfo](https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={stock_code})")
                with col_l2: 
                    st.markdown(f"[🔗Yahoo](https://tw.stock.yahoo.com/quote/{stock_code})")
                with col_l3: 
                    st.markdown(f"[🔗Fugle](https://www.fugle.tw/ai/{stock_code})")
            else:
                st.info("無法解析股票代碼，請確認追蹤名稱中包含數字代號。")
            
            st.write("") 
            if st.button("❌ 關閉焦點", use_container_width=True, key="close_focus_btn"):
                st.session_state["selected_watch_stock"] = None
                st.session_state["global_search_final"] = ""
                st.rerun()
                
            st.markdown("<hr style='border-color: #38BDF8; margin: 15px 0px;'>", unsafe_allow_html=True)

    st.markdown("""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 20px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 25px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            🔍 個股籌碼快搜
        </h2>
        <p style="color: #94a3b8; margin-top: 8px; font-size: 14px; margin-bottom: 0;">一起看看K線吧(興櫃標的僅有線圖無籌碼資訊)</p>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        def clear_search():
            st.session_state['global_search_final'] = ""

        st.markdown("<div style='font-size: 14px; color: #E2E8F0; margin-bottom: 5px; font-weight: bold;'>輸入 或 選擇標的 ：</div>", unsafe_allow_html=True)
        
        c_search, c_btn_go, c_btn_clear = st.columns([6, 1.5, 1.5])
        
        stock_options = []
        if STOCK_DICT:
            unique_options = {f"{v['id']} {v['name']}" for v in STOCK_DICT.values() if len(str(v['id'])) <= 4}
            stock_options = sorted(list(unique_options))

        with c_search:
            search_query = st.selectbox(
                "搜尋標的",
                options=[""] + stock_options,
                key="global_search_final",
                label_visibility="collapsed"
            )
        
        with c_btn_go:
            st.button("→", key="btn_go", type="tertiary", use_container_width=True, help="送出搜尋")
            
        with c_btn_clear:
            st.button("×", key="btn_clear", type="tertiary", on_click=clear_search, use_container_width=True, help="清空欄位")

        pure_stock_id = ""
        display_name = search_query
        industry_label = "未分類"
        
        if search_query:
            query_clean = search_query.strip()
            match_code = re.search(r'^[A-Za-z0-9]{2,4}', query_clean)
            
            if match_code:
                pure_stock_id = match_code.group(0)
            else:
                pure_stock_id = query_clean
            
            ensure_b1_to_b5_loaded(DATA_DIR)

            if STOCK_DICT:
                if pure_stock_id in STOCK_DICT:
                    v = STOCK_DICT[pure_stock_id]
                    pure_stock_id = str(v["id"])
                    display_name = f"{v['id']} {v['name']}"
                    industry_label = v.get("industry", "未分類")
                else:
                    display_name = search_query

            target_query = pure_stock_id if pure_stock_id else search_query

            st.markdown(f"### 🎯 綜合診斷標的：<span style='color: #00D2FF;'>{display_name}</span> <span style='font-size:16px; background-color:#1E293B; padding:4px 10px; border-radius:6px; color:#38BDF8; border: 1px solid #38BDF8; margin-left:10px;'>🏷️ {industry_label}</span>", unsafe_allow_html=True)

            # ==========================================
            # 🚀 技術面 AI 訊號區 (已移除籌碼積分，保留均線回測等技術訊號)
            # ==========================================
            new_ai_msgs = []
            if pure_stock_id:
                
                df_tech = fetch_yfinance_data(f"{pure_stock_id}.TW", period="1y")
                if df_tech is None or df_tech.empty:
                    df_tech = fetch_yfinance_data(f"{pure_stock_id}.TWO", period="1y")
                    
                if df_tech is not None and not df_tech.empty:
                    if isinstance(df_tech.columns, pd.MultiIndex):
                        df_tech.columns = df_tech.columns.get_level_values(0)
                    df_tech = df_tech.loc[:, ~df_tech.columns.duplicated()]
                    new_ai_msgs = generate_technical_signals(df_tech)

            if new_ai_msgs:
                signal_html = "<div style='background-color: rgba(0, 210, 255, 0.05); border-left: 4px solid #00D2FF; padding: 12px; border-radius: 5px; margin: 10px 0px;'>"
                signal_html += "<h5 style='color: #00D2FF; margin-top:0px; margin-bottom: 10px;'>📡 技術雷達訊號</h5>"
                
                for sig in new_ai_msgs:
                    signal_html += f"<p style='color: #E2E8F0; margin: 5px 0px; font-size: 14.5px;'>{sig}</p>"
                    
                signal_html += "</div>"
                st.markdown(signal_html, unsafe_allow_html=True)
            elif pure_stock_id:
                st.info("📡 AI 雷達：目前尚無強烈技術訊號。")

            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)

            # ==========================================
            # 📊 K 線控制台
            # ==========================================
            show_kline = st.toggle("📊 展開技術 K 線圖 (雙擊縮放)", value=st.session_state.get('show_kline', False), key="toggle_kline")
            st.session_state.show_kline = show_kline

            if show_kline:
                if pure_stock_id != "":          
                    st.markdown("##### 技術線圖與指標配置面板")
                    
                    kline_period = st.radio("選擇週期", ["日線", "週線", "月線"], horizontal=True, label_visibility="collapsed", key="kline_radio_period")
                    
                    ind_c1, ind_c2, ind_c3 = st.columns(3)
                    chk_kd = ind_c1.checkbox("顯示 KD (9,3,3)", value=False, key="kd_chk")
                    chk_macd = ind_c2.checkbox("顯示 MACD (12,26,9)", value=False, key="macd_chk")
                    chk_rsi = ind_c3.checkbox("顯示 RSI (14)", value=False, key="rsi_chk")
                    st.write("") 
                    
                    #with st.spinner(f"正在擷取 {pure_stock_id} 的最新數據..."):
                    all_mas = ["5MA", "10MA", "20MA", "60MA", "120MA", "240MA"]
                    render_technical_chart(pure_stock_id, kline_period, all_mas, chk_rsi, chk_macd, chk_kd)
                else:
                    st.warning("⚠️ 技術 K 線圖目前僅支援代號查詢。")

            # ==========================================
            # 👑 區塊 0 ~ 7：數據庫展演
            # ==========================================
            # 區塊 0
            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color: #FCD34D;'>⚡ 量價與動能雷達</h4>", unsafe_allow_html=True)
            
            try:
                from views.b0_page import get_cached_b0_data
                b0_cache = get_cached_b0_data(DATA_DIR)
                if b0_cache is not None:
                    df_b0_today, _ = b0_cache
                    # 利用純代號過濾出該股資料
                    b0_res = df_b0_today[df_b0_today['統一代號'] == pure_stock_id]
                    
                    if not b0_res.empty:
                        row_b0 = b0_res.iloc[0]
                        
                        # 基礎資料提取
                        price = row_b0.get('成交', 0)
                        pct = row_b0.get('漲跌幅', 0)
                        vol = row_b0.get('成交張數_num', 0)
                        amt = row_b0.get('成交額(百萬)', 0)
                        
                        # 👇 1. 新增：提取本益比並做防呆處理
                        per_val = row_b0.get('PER', 0)
                        try:
                            per_str = f"{float(per_val):.2f}" if float(per_val) > 0 else "虧損或無"
                        except:
                            per_str = "-"
                        
                        # 動態雷達提取
                        status = row_b0.get('B0_量價狀態', '-')
                        special = row_b0.get('B0_特殊型態', '-')
                        ma5_amt = row_b0.get('5日均額', 0)
                        ma10_amt = row_b0.get('10日均額', 0)
                        ma20_amt = row_b0.get('20日均額', 0)
                        
                        # 計算資金延續趨勢 (仿照 b0_page 邏輯)
                        fund_trend = "⚪ 資料不足"
                        if ma5_amt > 0 and ma10_amt > 0 and ma20_amt > 0:
                            if ma5_amt > ma10_amt and ma10_amt > ma20_amt:
                                fund_trend = "🔥 資金湧入 (延續性強)"
                            elif amt > ma5_amt and ma5_amt <= ma10_amt:
                                fund_trend = "⚡ 單日點火 (需觀察)"
                            elif ma5_amt < ma10_amt and ma10_amt < ma20_amt:
                                fund_trend = "💧 資金退潮 (動能弱)"
                            else:
                                fund_trend = "⚖️ 震盪換手"
                                
                        # 計算 5日爆發倍數
                        burst_ratio = (amt / ma5_amt) if ma5_amt > 0 else 0
                        
                        # 顏色判定
                        pct_color = "#FF4B4B" if pct > 0 else ("#00E272" if pct < 0 else "#E2E8F0")
                        
                        # 👇 2. 新增：在 UI 卡片中插入本益比 (⚖️ 估值狀態)
                        st.markdown(f"""
                        <div style='background-color: rgba(255,255,255,0.05); border-left: 3px solid #F59E0B; padding: 10px 12px; border-radius: 4px; margin-bottom: 12px; font-size: 13.5px; line-height: 1.6;'>
                            <div style='color: #E2E8F0;'>💰 <b>收盤報價：</b> <span style='color:{pct_color}; font-weight:bold;'>{price} ({pct:+.2f}%)</span></div>
                            <div style='color: #E2E8F0;'>⚖️ <b>本 益 比 ：</b> <span style='color:#E2E8F0;'>{per_str}</span></div>
                            <div style='color: #E2E8F0;'>📊 <b>今日成交：</b> <span style='color:#38BDF8;'>{int(vol):,} 張 / {amt:,.0f} 百萬</span></div>
                            <div style='color: #E2E8F0;'>🔮 <b>量價狀態：</b> <span style='color:#FCD34D;'>{status}</span></div>
                            <div style='color: #E2E8F0;'>🕵️ <b>特殊型態：</b> <span style='color:#A78BFA;'>{special}</span></div>
                            <hr style='border-color: rgba(255,255,255,0.1); margin: 6px 0px;'>
                            <div style='color: #E2E8F0;'>🚀 <b>5日爆發倍數：</b> <span style='color:#FF4B4B;'>{burst_ratio:.1f}x</span></div>
                            <div style='color: #E2E8F0;'>🌊 <b>資金水龍頭：</b> <span style='color:#10B981;'>{fund_trend}</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    else:
                        st.write("⚪ 查無此標的當日量價資料")
                else:
                    st.write("⚪ 尚未載入量價資料庫")
            except Exception as e:
                st.write(f"⚪ 量價模組載入異常: {e}")

            # b1

            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
            
            icon_b1 = get_img_html("magicbookleaf.png") 
            st.markdown(f"<h4 style='color: #FCD34D;'>{icon_b1}法人動向</h4>", unsafe_allow_html=True)
            
            df_b1 = get_sidebar_df('b1_final_df')
            if not df_b1.empty:
                res_b1 = robust_search_engine(df_b1, target_query)
                if not res_b1.empty:
                    date_cols = [c for c in res_b1.columns if '持股%' in c or c.isdigit()]
                    is_all_unranked = True
                    for c in date_cols:
                        val = str(res_b1.iloc[0][c]).strip()
                        if val != "未進榜" and val not in ['0', '0.0', 'nan', '-']:
                            is_all_unranked = False
                            break
                            
                    if is_all_unranked:
                        st.write("⚪ 未進榜")
                    else:
                        row = res_b1.iloc[0]
                        dyn_str = str(row.get('最新動態', '-'))
                        tag_str = str(row.get('今日上榜', ''))
                        if not tag_str.strip(): tag_str = "未上榜"
                        
                        delta_val = row.get('△', 0)
                        try:
                            d_val = float(str(delta_val).replace('%', '').replace('+', ''))
                            delta_str = f"+{d_val:.2f}" if d_val > 0 else f"{d_val:.2f}"
                            delta_color = "#FF4B4B" if d_val > 0 else ("#00E676" if d_val < 0 else "#94A3B8")
                        except:
                            delta_str = str(delta_val)
                            delta_color = "#94A3B8"

                        st.markdown(f"""
                        <div style='background-color: rgba(255,255,255,0.05); border-left: 3px solid #38BDF8; padding: 10px 12px; border-radius: 4px; margin-bottom: 12px; font-size: 13.5px; line-height: 1.6;'>
                            <div style='color: #E2E8F0;'>📌 <b>最新動態：</b><span style='color:#FCD34D;'>{dyn_str}</span></div>
                            <div style='color: #E2E8F0;'>🏷️ <b>今日上榜：</b><span style='color:#38BDF8;'>{tag_str}</span></div>
                            <div style='color: #E2E8F0;'>📊 <b>單日△：</b> <span style='color:{delta_color}; font-weight:bold;'>{delta_str}</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        hide_keywords = ['_區塊', '排序', '上榜數量', '原始上榜', '精準單日']
                        clean_cols = [c for c in res_b1.columns if not any(k in c for k in hide_keywords)]
                        st.dataframe(res_b1[clean_cols], use_container_width=True, hide_index=True)
                        
                        stock_name = row.get('股票名稱', display_name)
                        raw_x_vals = date_cols[::-1]
                        clean_x_labels = [c.replace('持股%', '')[-4:] for c in raw_x_vals]
                        
                        y_vals = []
                        for c in raw_x_vals:
                            val = row[c]
                            if str(val) == "未進榜" or pd.isna(val): y_vals.append(0.0)
                            else:
                                try: y_vals.append(float(val))
                                except: y_vals.append(0.0)
                                    
                        # 配合快取
                        fig_b1 = create_b1_bar_chart(stock_name, tuple(clean_x_labels), tuple(y_vals))
                        st.plotly_chart(fig_b1, use_container_width=True, config={'displayModeBar': False})
                else: st.write("⚪ 未進榜")
            else: st.info("⚪ 尚未載入資料表")

            # ------------------------------------------
            # 📉 新增：法人提款機 (衰退追蹤) 區塊
            # ------------------------------------------
            st.markdown("<h5 style='color: #00E676; margin-top: 15px; margin-bottom: 5px;'>📉 法人提款機 (衰退追蹤)</h5>", unsafe_allow_html=True)
            df_b1_down = get_sidebar_df('b1_down_final_df')
            if not df_b1_down.empty:
                res_b1_down = robust_search_engine(df_b1_down, target_query)
                if not res_b1_down.empty:
                    date_cols_down = [c for c in res_b1_down.columns if '持股%' in c or c.isdigit()]
                    is_all_unranked_down = True
                    for c in date_cols_down:
                        val = str(res_b1_down.iloc[0][c]).strip()
                        if val != "未進榜" and val not in ['0', '0.0', 'nan', '-']:
                            is_all_unranked_down = False
                            break

                    if is_all_unranked_down:
                        st.write("⚪ 未進榜")
                    else:
                        row_down = res_b1_down.iloc[0]
                        tag_down_str = str(row_down.get('今日衰退上榜', ''))
                        if not tag_down_str.strip(): tag_down_str = "未上榜"
                        
                        delta_down_val = row_down.get('單日△', 0)
                        try:
                            d_down_val = float(str(delta_down_val).replace('%', '').replace('+', ''))
                            delta_down_str = f"+{d_down_val:.2f}" if d_down_val > 0 else f"{d_down_val:.2f}"
                            delta_down_color = "#FF4B4B" if d_down_val > 0 else ("#00E676" if d_down_val < 0 else "#94A3B8")
                        except:
                            delta_down_str = str(delta_down_val)
                            delta_down_color = "#94A3B8"

                        st.markdown(f"""
                        <div style='background-color: rgba(0, 230, 118, 0.05); border-left: 3px solid #00E676; padding: 10px 12px; border-radius: 4px; margin-bottom: 12px; font-size: 13.5px; line-height: 1.6;'>
                            <div style='color: #E2E8F0;'>🏷️ <b>衰退上榜：</b><span style='color:#00E676;'>{tag_down_str}</span></div>
                            <div style='color: #E2E8F0;'>📊 <b>單日△：</b> <span style='color:{delta_down_color}; font-weight:bold;'>{delta_down_str}</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        hide_keywords_down = ['_區塊', '排序', '上榜數量', '原始上榜', '精準單日']
                        clean_cols_down = [c for c in res_b1_down.columns if not any(k in c for k in hide_keywords_down)]
                        
                        st.dataframe(
                            res_b1_down[clean_cols_down].style.apply(lambda x: ['background-color: rgba(0, 230, 118, 0.1)'] * len(x), axis=1), 
                            use_container_width=True, 
                            hide_index=True
                        )

                        stock_name_down = row_down.get('股票名稱', display_name)
                        raw_x_vals_down = date_cols_down[::-1]
                        clean_x_labels_down = [c.replace('持股%', '')[-4:] for c in raw_x_vals_down]

                        y_vals_down = []
                        for c in raw_x_vals_down:
                            val = row_down[c]
                            if str(val) == "未進榜" or pd.isna(val): y_vals_down.append(0.0)
                            else:
                                try: y_vals_down.append(float(val))
                                except: y_vals_down.append(0.0)

                        # 配合快取
                        fig_b1_down = create_b1_down_bar_chart(stock_name_down, tuple(clean_x_labels_down), tuple(y_vals_down))
                        st.plotly_chart(fig_b1_down, use_container_width=True, config={'displayModeBar': False})
                else:st.write("⚪ 未進榜")
            else:st.info("⚪ 尚未載入資料表")

            # ------------------------------------------
            # 🌎 新增：外資大腿 20日軌跡 區塊
            # ------------------------------------------
            st.markdown("<h5 style='color: #38BDF8; margin-top: 15px; margin-bottom: 5px;'>🌎 外資大腿 20日軌跡</h5>", unsafe_allow_html=True)
            df_foreign_sb = get_sidebar_df('b1_foreign_df')
            df_b1_sb = get_sidebar_df('b1_final_df')
                        
            if not df_foreign_sb.empty and not df_b1_sb.empty:
                res_for = robust_search_engine(df_foreign_sb, target_query)
                if not res_for.empty:
                    foreign_dates = {c.replace('外資持股_', '') for c in df_foreign_sb.columns if '外資持股_' in c}
                    total_dates = {c.replace('持股%', '') for c in df_b1_sb.columns if '持股%' in c}
                    common_dates = sorted(list(foreign_dates & total_dates), reverse=True)[:20]
                                
                    if common_dates:
                        for_cols = [f'外資持股_{d}' for d in common_dates if f'外資持股_{d}' in res_for.columns]
                        if for_cols:
                            row_for = res_for.iloc[0]
                            clean_x_for = [d[-4:] for d in common_dates if f'外資持股_{d}' in res_for.columns]
                            y_vals_for = []
                            for d in common_dates:
                                col_name = f'外資持股_{d}'
                                if col_name in row_for:
                                    val = row_for[col_name]
                                    try: y_vals_for.append(float(str(val).replace('%', '')))
                                    except: y_vals_for.append(0.0)
                                else:
                                    y_vals_for.append(0.0)
                                        
                            display_for_dict = {d[-4:]: [row_for[f'外資持股_{d}']] for d in common_dates if f'外資持股_{d}' in row_for}
                            if display_for_dict:
                                display_for_df = pd.DataFrame(display_for_dict)
                                st.dataframe(display_for_df, use_container_width=True, hide_index=True)
                                        
                            # 配合快取
                            fig_for = create_foreign_bar_chart(tuple(clean_x_for[::-1]), tuple(y_vals_for[::-1]))
                            st.plotly_chart(fig_for, use_container_width=True, config={'displayModeBar': False})
                        else:
                            st.write("⚪ 尚無外資軌跡資料")
                    else:
                        st.write("⚪ 尚無對應日期")
                else:
                    st.write("⚪ 未進榜外資持股資料")
            else:
                st.info("⚪ 尚未載入外資資料表")

            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
            
            # 🎯 區塊 2
            icon_b2 = get_img_html("magicbookwind.png")
            st.markdown(f"<h4 style='color: #FCD34D;'>{icon_b2}法人掃貨</h4>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1: scan_and_display("🌐 外資 5 日淨買佔成交量", 'b2_1', target_query)
            with c2: scan_and_display("🏦 投信 5 日淨買佔成交量", 'b2_2', target_query)
            c3, c4 = st.columns(2)
            with c3: scan_and_display("🌐 外資 5 日淨買佔發行量", 'b2_3', target_query)
            with c4: scan_and_display("🏦 投信 5 日淨買佔發行量", 'b2_4', target_query)

            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
            
            # 📅 區塊 3
            icon_b3 = get_img_html("magicbookwater.png") 
            st.markdown(f"<h4 style='color: #FCD34D;'>{icon_b3}法人連買</h4>", unsafe_allow_html=True)
            df_b3 = get_sidebar_df('b3_main')
            if not df_b3.empty:
                res_b3 = robust_search_engine(df_b3, target_query)
                if res_b3.empty:
                    st.write("⚪ 未進榜")
                else:
                    st.dataframe(res_b3, use_container_width=True, hide_index=True)
            else: 
                st.info("⚪ 區塊 3：尚未載入資料表")

            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
            
            # 🔄 區塊 4
            icon_b4 = get_img_html("magicbookground.png") 
            st.markdown(f"<h4 style='color: #FCD34D;'>{icon_b4}資券動向</h4>", unsafe_allow_html=True)
            just_name = display_name.replace(pure_stock_id, "").strip() if pure_stock_id else display_name
            
            render_b4_panorama("5日幅度變動排名", [('📉 融資減少', 'b4_margin_pct'), ('📉 借券減少', 'b4_short_pct'), ('📈 融券增加', 'b4_margin_plus_pct')], target_query, just_name)
            st.write("") 
            render_b4_panorama("5日張數變動排名", [('📉 融資減少', 'b4_margin_vol'), ('📉 借券減少', 'b4_short_vol'), ('📈 融券增加', 'b4_margin_plus_vol')], target_query, just_name)

            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
            
            # 💰 區塊 5
            icon_b5 = get_img_html("wirtleg.png") 
            st.markdown(f"<h4 style='color: #FCD34D;'>{icon_b5}大腿動向</h4>", unsafe_allow_html=True)
            
            col_400, col_1000 = st.columns(2)
            with col_400: scan_and_display("💎 400張以上大戶動向", 'b5_400', target_query)
            with col_1000: scan_and_display("🐳 1000張以上超級大戶動向", 'b5_1000', target_query)

            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
            
            # 👔 區塊 7
            icon_b7 = get_img_html("magicbookboss.png") 
            st.markdown(f"<h4 style='color: #FCD34D;'>{icon_b7}董監動向</h4>", unsafe_allow_html=True)
            scan_and_display("🔹 董監最新質押比", 'b7_pledge', target_query)
            scan_and_display("🔹 董監質押歷史趨勢", 'b7_pledge_history', target_query)
            scan_and_display("🔹 董監持股比增減", 'b7_main', target_query)

            # 👇 新增：區塊 8 券商分點追蹤 
            st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
            icon_broker = get_img_html("icon-building.png") 
            st.markdown(f"<h4 style='color: #FCD34D;'>{icon_broker}分點追蹤</h4>", unsafe_allow_html=True)
            render_sidebar_broker_tracking(target_query, display_name)
            
    # ==========================================            
    # 💡 當搜尋列「沒有內容」時，顯示大盤總經
    if not search_query:
        st.write("---") 
        tab1, tab2, tab3 = st.tabs(["🔹 大盤籌碼", "🔹 選擇權", "🔹 總經導航🛠️"])
        
        with tab1:
            actual_data_date = render_sidebar_market_summary()
            
        with tab2:
            render_options_dashboard()
            
        with tab3:
            macro_data = fetch_macro_indicators()
            
            vix_val = macro_data["vix"]["value"]
            vix_color = "#a1a1aa" 
            if vix_val is not None:
                if vix_val < 20: vix_color = "#10b981" 
                elif vix_val < 28.7: vix_color = "#3b82f6" 
                elif vix_val < 33.5: vix_color = "#f59e0b" 
                else: vix_color = "#ef4444" 
            vix_tooltip = f"VIX 市場恐慌指標\n目前 VIX： {vix_val if vix_val else '無'}\n綠色：市場平穩。\n藍色：報酬較差。\n橘色：報酬達 15%。\n紅色：報酬達 25%。"

            vixtwn_val = macro_data["vixtwn"]["value"]
            vixtwn_color = "#a1a1aa"
            if vixtwn_val is not None:
                if vixtwn_val < 20: vixtwn_color = "#3b82f6" 
                elif vixtwn_val < 30: vixtwn_color = "#10b981" 
                elif vixtwn_val < 40: vixtwn_color = "#f59e0b" 
                else: vixtwn_color = "#ef4444" 
            vixtwn_tooltip = f"VIXTWN 台灣恐慌指標\n目前： {vixtwn_val if vixtwn_val else '無'}\n藍：多頭常態。\n綠：波動加劇。\n橘：恐慌殺盤布局。\n紅：極度恐慌買點。"

            fng_val = macro_data["fng"]["score"]
            fng_color = "#a1a1aa"
            if fng_val is not None:
                if fng_val < 25: fng_color = "#ef4444" 
                elif fng_val > 75: fng_color = "#10b981" 
                else: fng_color = "#f59e0b" 
            fng_tooltip = f"FNG 恐懼貪婪指數\n目前： {fng_val if fng_val else '無'}\n<25 積極買點\n<15 分批加碼\n>75 分批減碼\n>85 獲利了結\n>90 提高現金"

            col_left, col_right = st.columns([1, 1])
            
            with col_left:
                v1_str = f"{vix_val:.2f}" if vix_val else "無資料"
                p1_str = f"{'+' if macro_data['vix']['pct'] and macro_data['vix']['pct'] > 0 else ''}{macro_data['vix']['pct']:.2f}%" if macro_data['vix']['pct'] is not None else "-"
                st.markdown(f"""
                <div title="{vix_tooltip}" style="background-color: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); text-align: center; cursor: help; margin-bottom: 10px;">
                    <div style="font-size: 13px; color: #a1a1aa; margin-bottom: 4px;">🇺🇸 美股 VIX</div>
                    <div style="font-size: 22px; font-weight: 700; color: {vix_color}; margin-bottom: 2px;">{v1_str}</div>
                    <div style="font-size: 12px; color: #71717a;">{p1_str}</div>
                </div>
                """, unsafe_allow_html=True)
                
                v2_str = f"{vixtwn_val:.2f}" if vixtwn_val else "無資料"
                p2_str = "最新數值" if vixtwn_val else "-"
                st.markdown(f"""
                <div title="{vixtwn_tooltip}" style="background-color: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); text-align: center; cursor: help;">
                    <div style="font-size: 13px; color: #a1a1aa; margin-bottom: 4px;">🇹🇼 台股 VIX</div>
                    <div style="font-size: 22px; font-weight: 700; color: {vixtwn_color}; margin-bottom: 2px;">{v2_str}</div>
                    <div style="font-size: 12px; color: #71717a;">{p2_str}</div>
                </div>
                """, unsafe_allow_html=True)

            with col_right:
                f_str = str(fng_val) if fng_val else "無資料"
                f_rating = macro_data["fng"]["rating"]
                st.markdown(f"""
                <div title="{fng_tooltip}" style="background-color: rgba(255,255,255,0.03); padding: 12px; height: calc(100% - 24px); display: flex; flex-direction: column; justify-content: center; align-items: center; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); text-align: center; cursor: help;">
                    <div style="font-size: 15px; color: #a1a1aa; margin-bottom: 15px;">恐懼與貪婪</div>
                    <div style="font-size: 36px; font-weight: 700; color: {fng_color}; margin-bottom: 10px;">{f_str}</div>
                    <div style="font-size: 14px; font-weight: 600; color: {fng_color};">{f_rating}</div>
                </div>
                """, unsafe_allow_html=True)

    # ==========================================
    # 🚀 快速回到頂部按鈕 (Google Material Icons 版)
    # ==========================================
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />',
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <a href="#section-search" target="_self" 
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
