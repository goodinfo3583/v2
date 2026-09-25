# views/pool_page.py
import streamlit as st
import pandas as pd
import glob
import os
import re
import datetime
from datetime import timedelta
import html
import plotly.express as px
import yfinance as yf

# 引入共用工具
from utils.data_utils import robust_read_csv

# ==========================================
# ⚡ 效能救星：全域股價快取引擎 (快取 1 小時)
# ==========================================
@st.cache_data(show_spinner=False, ttl=3600)
def get_cached_stock_price(sid, start_str=None, end_str=None):
    """將 yfinance 抓取價格的動作快取起來，避免迴圈重複呼叫拖垮效能"""
    ticker_tw = f"{sid}.TW"
    ticker_two = f"{sid}.TWO"
    try:
        if start_str and end_str:
            p_df = yf.download(ticker_tw, start=start_str, end=end_str, progress=False)
            if p_df.empty: p_df = yf.download(ticker_two, start=start_str, end=end_str, progress=False)
            if not p_df.empty:
                val = p_df['Close'].iloc[0]
                return round(float(val.iloc[0] if isinstance(val, pd.Series) else val), 2)
        else:
            p_df = yf.download(ticker_tw, period="1d", progress=False)
            if p_df.empty: p_df = yf.download(ticker_two, period="1d", progress=False)
            if not p_df.empty:
                val = p_df['Close'].iloc[-1]
                return round(float(val.iloc[0] if isinstance(val, pd.Series) else val), 2)
    except:
        pass
    return 0.0


# ==========================================
# 🌟 "觀察名單"專屬工具函數區 
# ==========================================
def get_df_safe(*keys): 
    """🌟 升級版：支援多重 Key 備援，完美橋接新舊版記憶體變數"""
    for k in keys:
        df = st.session_state.get(k)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy()
    return pd.DataFrame()

def fmt_d(d_str): 
    return f"{d_str[4:6]}/{d_str[6:]}" if d_str != "00000000" else "--/--"

def check_b2_strict(df, sid, bad_keywords):
    if df.empty or '股票代號' not in df.columns or sid not in df['股票代號'].values: return False
    dyn = str(df[df['股票代號'] == sid].iloc[0].get('今日短動態', ''))
    if any(bad in dyn for bad in bad_keywords): return False
    return True

def get_b3_score(df, sid, type_keyword):
    if df is None or df.empty or '股票代號' not in df.columns: 
        return 0, ""
    
    type_col = next((c for c in df.columns if '類型' in str(c) or '連買' in str(c)), None)
    days_col = next((c for c in df.columns if '週期' in str(c) or '天數' in str(c) or '日' in str(c)), None)
    
    if not type_col or not days_col or type_col not in df.columns:
        return 0, ""

    match = df[(df['股票代號'] == sid) & (df[type_col].astype(str).str.contains(type_keyword, na=False))]
    if match.empty: return 0, ""
    
    days = pd.to_numeric(match.iloc[0].get(days_col, 0), errors='coerce')
    if pd.isna(days) or days == 0: return 0, ""
    
    if '日' in type_keyword:
        if days >= 10: return 1.0, f"✔️({days}日)"
        elif days >= 5: return 0.8, f"✔️({days}日)"
        else: return 0.5, f"✔️({days}日)"
    else:
        if days >= 10: return 2.0, f"✔️({days}週)"
        elif days >= 5: return 1.5, f"✔️({days}週)"
        else: return 1.0, f"✔️({days}週)"

def get_today_ratio(df, stock_id, col_name):
    if df is not None and not df.empty and '股票代號' in df.columns and stock_id in df['股票代號'].values:
        try: return float(df.loc[df['股票代號'] == stock_id, col_name].iloc[0])
        except: 
            fuzzy_col = next((c for c in df.columns if '當日' in str(c) and ('買' in str(c) or '比' in str(c))), None)
            if fuzzy_col:
                try: return float(df.loc[df['股票代號'] == stock_id, fuzzy_col].iloc[0])
                except: pass
    return 0.0

# ==========================================
# 🚀 觀察名單主畫面渲染函數
# ==========================================
def show_pool_page(conn, SHEET_URL, DATA_DIR, STOCK_DICT):
    with st.container():
        st.write("---")
        st.markdown("<div id='section-top-pool'></div>", unsafe_allow_html=True)

        df_b1 = get_df_safe('b1_final_df', 'my_final_df')
        df_b5_1000 = get_df_safe('b5_1000', 'df_blk5_1000')
        df_b5_400 = get_df_safe('b5_400', 'df_blk5')
        df_b2_1 = get_df_safe('b2_1', 'df_blk2_1')
        df_b2_2 = get_df_safe('b2_2', 'df_blk2_2')
        df_b2_3 = get_df_safe('b2_3', 'df_blk2_3')
        df_b2_4 = get_df_safe('b2_4', 'df_blk2_4')
        df_b3 = get_df_safe('b3_main', 'df_blk3_main')
        df_b4_mar_pct = get_df_safe('b4_margin_pct', 'df_margin_pct')
        df_b4_mar_vol = get_df_safe('b4_margin_vol', 'df_margin_vol')
        df_b4_sho_pct = get_df_safe('b4_short_pct', 'df_short_pct')
        df_b4_sho_vol = get_df_safe('b4_short_vol', 'df_short_vol')
        df_b4_mp_pct = get_df_safe('b4_margin_plus_pct', 'df_margin_plus_pct')
        df_b4_mp_vol = get_df_safe('b4_margin_plus_vol', 'df_margin_plus_vol')
        
        all_files = glob.glob(os.path.join(DATA_DIR, "*"))
        anchor_date_str = "00000000"
        d_b1_inst, d_b23_chip, d_b4_margin, d_b5_share = "00000000", "00000000", "00000000", "00000000"
        
        if all_files:
            for f in all_files:
                filename = os.path.basename(f)
                match = re.search(r'(202\d{5})', filename)
                if match:
                    file_date = match.group(1)
                    if file_date > anchor_date_str: anchor_date_str = file_date
                    if "持股排名變化" in filename or "JSON_History" in filename:
                        if file_date > d_b1_inst: d_b1_inst = file_date
                    elif "佔成交比" in filename or "連買" in filename or "買賣超" in filename:
                        if file_date > d_b23_chip: d_b23_chip = file_date
                    elif "融資" in filename or "融券" in filename or "借券" in filename or "資券" in filename:
                        if file_date > d_b4_margin: d_b4_margin = file_date
                    elif "大股東" in filename or "神秘金字塔" in filename or "集保" in filename:
                        if file_date > d_b5_share: d_b5_share = file_date

        def fmt_d_str(date_str):
            if date_str and len(date_str) >= 8 and date_str != "00000000":
                return f"{date_str[4:6]}/{date_str[6:8]}"
            return "--/--"

        st.markdown(f"""
        <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                    border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; border-radius: 10px;
                    text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
            <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
                觀察名單
            </h2>
            <div style='font-size:13px; color:#00D2FF; font-weight:500; margin-top:8px;'>
                 基準日 : 📍法人持股: {fmt_d_str(d_b1_inst)} ｜ 📍法人買況: {fmt_d_str(d_b23_chip)} ｜ 📍資券: {fmt_d_str(d_b4_margin)} ｜ 📍大腿: {fmt_d_str(d_b5_share)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.container(border=True):
            st.info("💡 我們試著觀察近5/20/60/120日法人動向持股上升的變化前段班且當天持續買入的標的...")

            if df_b1.empty or df_b5_1000.empty:
                st.warning("⚠️ 記憶體中尚無最新數據 (或尚未載入大股東資料)，請點擊下方按鈕啟動全市場掃描引擎。")
                c_btn1, c_btn2, c_btn3 = st.columns([1, 2, 1])
                with c_btn2:
                    if st.button("🚀 啟動全市場掃描 (計算總分)", type="primary", use_container_width=True):
                        st.session_state.current_page = "all" 
                        st.query_params["page"] = "all"
                        st.rerun()
                return 

            # ---------------- 開始正式運算數據分析觀察名單打底及積分 ----------------
            dyn_col = next((c for c in df_b1.columns if '動態' in c or '動能' in c), None)
            rank_col = next((c for c in df_b1.columns if '今日上榜' in c or '上榜' in c), None)
            
            if dyn_col:
                mask = df_b1[dyn_col].astype(str).str.contains('趨緩|上升|升|吸籌|衝進|回歸', na=False)
                pool_df = df_b1[mask].copy()
            else:
                pool_df = df_b1.copy()
                
            if pool_df.empty:
                st.warning("⚪ 目前區塊 1 中沒有符合動能的標的。")
            else:
                fo_sell_ids, it_sell_ids = set(), set()
                try:
                    fo_sell_files = glob.glob(os.path.join(DATA_DIR, "*外資賣出佔成交比*3日*.csv"))
                    if not fo_sell_files: fo_sell_files = glob.glob(os.path.join(DATA_DIR, "*外資賣出佔成交比*.csv"))
                    if fo_sell_files:
                        df_fs = robust_read_csv(sorted(fo_sell_files, reverse=True)[0])
                        id_c = next((c for c in df_fs.columns if '代號' in c), None)
                        if id_c: fo_sell_ids = set(df_fs[id_c].astype(str).str.replace(r'\D', '', regex=True))
                    
                    it_sell_files = glob.glob(os.path.join(DATA_DIR, "*投信賣出佔成交比*5日*.csv"))
                    if not it_sell_files: it_sell_files = glob.glob(os.path.join(DATA_DIR, "*投信賣出佔成交比*.csv"))
                    if it_sell_files:
                        df_is = robust_read_csv(sorted(it_sell_files, reverse=True)[0])
                        id_c = next((c for c in df_is.columns if '代號' in c), None)
                        if id_c: it_sell_ids = set(df_is[id_c].astype(str).str.replace(r'\D', '', regex=True))
                except: pass

                s_b4_mar_pct, s_b4_mar_vol = set(df_b4_mar_pct.get('股票代號', [])), set(df_b4_mar_vol.get('股票代號', []))
                s_b4_sho_pct, s_b4_sho_vol = set(df_b4_sho_pct.get('股票代號', [])), set(df_b4_sho_vol.get('股票代號', []))
                s_b4_mp_pct, s_b4_mp_vol = set(df_b4_mp_pct.get('股票代號', [])), set(df_b4_mp_vol.get('股票代號', []))

                bad_b2_vol = ['持平', '調節洗盤', '劇烈倒貨', '觀望']
                bad_b2_iss = ['轉賣反轉', '籌碼沉澱中', '今日量縮持平']

                block_sids = set()
                try:
                    if 'fetch_block_trades' in globals():
                        temp_block = fetch_block_trades()
                        if not temp_block.empty:
                            block_sids = set(temp_block['證券代號'].astype(str).str.replace(r'\D', '', regex=True))
                except: pass

                def ultra_clean_id(val):
                    v = str(val).strip().replace('.0', '')
                    return re.sub(r'\D', '', v)

                def raw_delta_to_trend(val):
                    try:
                        v = float(str(val).replace('+', '').replace('%', '').strip())
                        if v >= 1.5: return "🔥 大增"
                        if v >= 0.5: return "📈 增"
                        if v > 0: return "↗ 微增"
                        if v == 0: return "🔄 持平"
                        if v > -0.5: return "↘ 微減"
                        return "🚨 減/大減"
                    except: return "無資料"

                dict_1000, dict_400 = {}, {}
                
                if not df_b5_1000.empty and '股票代號' in df_b5_1000.columns:
                    if '週動態' in df_b5_1000.columns:
                        dict_1000 = {ultra_clean_id(k): str(v) for k, v in zip(df_b5_1000['股票代號'], df_b5_1000['週動態'])}
                    else:
                        delta_col = next((c for c in df_b5_1000.columns if '1千張增減' in c or '1000張增減' in c or '增減' in c), None)
                        if delta_col:
                            dict_1000 = {ultra_clean_id(k): raw_delta_to_trend(v) for k, v in zip(df_b5_1000['股票代號'], df_b5_1000[delta_col])}

                if not df_b5_400.empty and '股票代號' in df_b5_400.columns:
                    if '週動態' in df_b5_400.columns:
                        dict_400 = {ultra_clean_id(k): str(v) for k, v in zip(df_b5_400['股票代號'], df_b5_400['週動態'])}
                    else:
                        delta_col = next((c for c in df_b5_400.columns if '400張增減' in c or '總增減' in c or '增減' in c), None)
                        if delta_col:
                            dict_400 = {ultra_clean_id(k): raw_delta_to_trend(v) for k, v in zip(df_b5_400['股票代號'], df_b5_400[delta_col])}

                results = []
                for _, row in pool_df.iterrows():
                    sid = ultra_clean_id(row['股票代號'])
                    sname = str(row.get('股票名稱', '')).strip()
                    b1_dyn = str(row.get(dyn_col, '')) if dyn_col else '-'
                    
                    try:
                        delta_val = float(row.get('△', 0.0))
                        b1_delta = "0.00" if abs(delta_val) < 0.005 else (f"+{delta_val:.2f}" if delta_val > 0 else f"{delta_val:.2f}")
                    except: b1_delta = "0.00"
                    
                    if sid in block_sids: b1_dyn = f"{b1_dyn} | 🎣 鉅額交易"
                    b1_rank = str(row.get(rank_col, '-')) if rank_col else '-'
                    
                    score, details = 0.0, [] 
                    
                    if check_b2_strict(df_b2_1, sid, bad_b2_vol): score += 1; details.append("外買佔: +1"); r_b2_1 = "✔️"
                    else: r_b2_1 = ""
                    if check_b2_strict(df_b2_2, sid, bad_b2_vol): score += 1; details.append("投買佔: +1"); r_b2_2 = "✔️"
                    else: r_b2_2 = ""
                    if check_b2_strict(df_b2_3, sid, bad_b2_iss): score += 1; details.append("外佔發行: +1"); r_b2_3 = "✔️"
                    else: r_b2_3 = ""
                    if check_b2_strict(df_b2_4, sid, bad_b2_iss): score += 1; details.append("投佔發行: +1"); r_b2_4 = "✔️"
                    else: r_b2_4 = ""
                    
                    if get_today_ratio(df_b2_1, sid, '當日買佔比%') <= -10: score -= 0.5; details.append("外買佔(<-10%): -0.5")
                    if get_today_ratio(df_b2_2, sid, '當日買佔比%') <= -10: score -= 0.5; details.append("投買佔(<-10%): -0.5")
                    if get_today_ratio(df_b2_3, sid, '當日買發比%') <= -10: score -= 0.5; details.append("外佔發(<-10%): -0.5")
                    if get_today_ratio(df_b2_4, sid, '當日買發比%') <= -10: score -= 0.5; details.append("投佔發(<-10%): -0.5")
                    
                    s_fd, r_b3_fd = get_b3_score(df_b3, sid, '外資日'); score += s_fd; 
                    if s_fd > 0: details.append(f"外資日連: +{s_fd}")
                    s_fw, r_b3_fw = get_b3_score(df_b3, sid, '外資週'); score += s_fw; 
                    if s_fw > 0: details.append(f"外資週連: +{s_fw}")
                    s_id, r_b3_id = get_b3_score(df_b3, sid, '投信日'); score += s_id; 
                    if s_id > 0: details.append(f"投信日連: +{s_id}")
                    s_iw, r_b3_iw = get_b3_score(df_b3, sid, '投信週'); score += s_iw; 
                    if s_iw > 0: details.append(f"投信週連: +{s_iw}")
                    
                    r_b4_mar, b4_list_count = "", 0
                    if sid in s_b4_mar_pct: r_b4_mar += "✔️(幅)"; score += 1.0; details.append("資減(幅): +1.0"); b4_list_count += 1
                    if sid in s_b4_mar_vol: r_b4_mar += "✔️(量)"; score += 0.5; details.append("資減(量): +0.5"); b4_list_count += 1
                    
                    r_b4_sho = ""
                    if sid in s_b4_sho_pct: r_b4_sho += "✔️(幅)"; score += 1.0; details.append("借減(幅): +1.0"); b4_list_count += 1
                    if sid in s_b4_sho_vol: r_b4_sho += "✔️(量)"; score += 0.5; details.append("借減(量): +0.5"); b4_list_count += 1
                    
                    r_b4_mp = ""
                    if sid in s_b4_mp_pct: r_b4_mp += "✔️(幅)"; score += 1.0; details.append("券增(幅): +1.0"); b4_list_count += 1
                    if sid in s_b4_mp_vol: r_b4_mp += "✔️(量)"; score += 0.5; details.append("券增(量): +0.5"); b4_list_count += 1
                    
                    if b4_list_count > 0:
                        change_val = 0.0
                        for b4_df in [df_b4_mar_pct, df_b4_mar_vol, df_b4_sho_pct, df_b4_sho_vol, df_b4_mp_pct, df_b4_mp_vol]:
                            if not b4_df.empty and sid in b4_df['股票代號'].values and '漲跌幅%' in b4_df.columns:
                                try: change_val = float(str(b4_df.loc[b4_df['股票代號'] == sid, '漲跌幅%'].iloc[0]).replace('%', '')); break 
                                except: pass
                        if change_val > 0:
                            score += 0.7; details.append("榜上+當日上漲: +0.7")
                            if change_val > 3: score += 0.7; details.append("榜上+漲幅>3%: +0.7")
                                
                        short_decrease_val = 0.0
                        if not df_b4_sho_pct.empty and sid in df_b4_sho_pct['股票代號'].values:
                            s_col = next((c for c in df_b4_sho_pct.columns if '當日' in str(c) and ('%' in str(c) or '增減' in str(c))), None)
                            if s_col:
                                try: short_decrease_val = float(str(df_b4_sho_pct.loc[df_b4_sho_pct['股票代號'] == sid, s_col].iloc[0]).replace('%', ''))
                                except: pass
                        if abs(short_decrease_val) >= 1: score += 1.2; details.append("空頭認輸(借券減>1%): +1.2")

                    # 動態捕捉
                    r_b5_1000, r_b5_400 = "-", "-"
                    trend_1000_val = dict_1000.get(sid, "")
                    if trend_1000_val:
                        if '大增' in trend_1000_val: score += 2.0; r_b5_1000 = "🔥千張大增(+2)"; details.append("千張大增: +2")
                        elif '增' in trend_1000_val and '微' not in trend_1000_val: score += 1.0; r_b5_1000 = "📈千張增(+1)"; details.append("千張增: +1")
                        elif '微增' in trend_1000_val: score += 0.5; r_b5_1000 = "↗️千微增(+0.5)"; details.append("千張微增: +0.5")
                        elif '大減' in trend_1000_val: score -= 0.5; r_b5_1000 = "🚨千大減(-0.5)"; details.append("千張大減: -0.5")
                        elif '減' in trend_1000_val: score -= 0.5; r_b5_1000 = "📉千減(-0.5)"; details.append("千張減: -0.5")
                        else: r_b5_1000 = f"千{trend_1000_val}"

                    trend_400_val = dict_400.get(sid, "")
                    if trend_400_val:
                        if '大增' in trend_400_val: score += 1.0; r_b5_400 = "🔥四百大增(+1)"; details.append("四百大增: +1")
                        elif '增' in trend_400_val and '微' not in trend_400_val: score += 0.5; r_b5_400 = "📈四百增(+0.5)"; details.append("四百增: +0.5")
                        elif '微增' in trend_400_val: score += 0.0; r_b5_400 = "↗️四百微增(0)"
                        elif '大減' in trend_400_val: score -= 0.0; r_b5_400 = "🚨四百大減(0)" 
                        elif '減' in trend_400_val: score -= 0.0; r_b5_400 = "📉四百減(0)"
                        else: r_b5_400 = f"四百{trend_400_val}"

                    if ('增' in trend_1000_val and '減' in trend_400_val):
                        score += 1.0; details.append("🌟籌碼極集中: +1"); r_b5_1000 = f"{r_b5_1000}🌟"

                    r_b5 = f"{r_b5_1000} | {r_b5_400}" if (r_b5_1000 != "-" or r_b5_400 != "-") else "-"
                    
                    is_fo_sell = sid in fo_sell_ids; is_it_sell = sid in it_sell_ids
                    if is_fo_sell and is_it_sell: r_warn = "🚨外投雙倒"; score -= 2.0; details.append("外投雙倒: -2")
                    elif is_fo_sell: r_warn = "⚠️外資倒"
                    elif is_it_sell: r_warn = "⚠️投信倒"
                    else: r_warn = "-"

                    results.append({
                        '總分': score, '代號': sid, '名稱': sname, '▼明細': " \n".join(details) if details else "無加扣分", '△': b1_delta,
                        '最新動態': b1_dyn, '今日上榜': b1_rank, '賣出警示': r_warn,
                        '外買佔比': r_b2_1, '投買佔比': r_b2_2, '外佔發行': r_b2_3, '投佔發行': r_b2_4,
                        '外日連': r_b3_fd, '外週連': r_b3_fw, '投日連': r_b3_id, '投週連': r_b3_iw,
                        '資減': r_b4_mar, '借減': r_b4_sho, '券增': r_b4_mp, '大股東動向': r_b5
                    })
                    
                res_df = pd.DataFrame(results).sort_values(by='總分', ascending=False).drop_duplicates(subset=['代號']).reset_index(drop=True)
                
                # ==========================================
                # 🔥 Delta 計算與 Google Sheets (使用 TTL=60 避免連續讀取)
                # ==========================================
                prev_scores_dict = {}
                hist_combined = pd.DataFrame() 
                try:
                    # 💡 把 ttl 從 10 延長至 60 秒，避免頁面互動時連續卡住
                    gs_history = conn.read(spreadsheet=SHEET_URL, worksheet="選股歷史", ttl=60)
                    gs_history = gs_history.dropna(how="all")
                    if not gs_history.empty and '紀錄日期' in gs_history.columns:
                        gs_history['紀錄日期'] = gs_history['紀錄日期'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(8)
                        hist_combined = gs_history.copy()
                        available_dates = sorted(gs_history['紀錄日期'].unique(), reverse=True)
                        if len(available_dates) >= 2:
                            prev_df = gs_history[gs_history['紀錄日期'] == available_dates[1]]
                            id_col = '代號' if '代號' in prev_df.columns else '股票代號' if '股票代號' in prev_df.columns else None
                            if id_col: prev_scores_dict = dict(zip(prev_df[id_col].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True), prev_df['總分']))
                except Exception as e: 
                    st.warning(f"⚠️ 無法讀取 Google Sheets 歷史紀錄以計算變量，錯誤訊息：{e}")

                def calc_table_delta(row):
                    sid = str(row['代號']).strip()
                    try: curr_score = float(row.get('總分', 0))
                    except: curr_score = 0.0
                    if sid in prev_scores_dict:
                        try: prev_score = float(prev_scores_dict[sid])
                        except: prev_score = 0.0
                        delta = curr_score - prev_score
                        if delta > 0.01: return f"+{delta:.1f}"
                        elif delta < -0.01: return f"{delta:.1f}"
                        else: return "0.0"
                    else: return f"🆕 +{curr_score:.1f}"

                if not res_df.empty and '總分' in res_df.columns:
                    res_df['▼變量'] = res_df.apply(calc_table_delta, axis=1)

                cols = [c for c in res_df.columns if c not in ['▼變量', '▼明細', '△', '賣出警示']]
                cols.insert(cols.index('總分') + 1, '▼變量')
                cols.insert(cols.index('名稱') + 1, '▼明細')
                cols.insert(cols.index('▼明細') + 1, '△')
                cols.insert(cols.index('今日上榜') + 1, '賣出警示')
                res_df = res_df[cols]
                st.session_state['top_pool_df'] = res_df
                
                valid_calc = False
                if not res_df.empty and '總分' in res_df.columns:
                    valid_calc = (res_df['總分'] > 0).sum() >= 5 
                    
                if valid_calc and anchor_date_str != "00000000":
                    save_df = res_df.copy()
                    save_df.insert(0, '紀錄日期', anchor_date_str)
                    if st.session_state.get('last_gsheet_save_date') != anchor_date_str:
                        try:
                            # 💡 寫入前清除快取確保拿到最新，寫完後會重新刷新
                            old_df = conn.read(spreadsheet=SHEET_URL, worksheet="選股歷史", ttl=0).dropna(how="all")
                            if not old_df.empty and '紀錄日期' in old_df.columns:
                                old_df['紀錄日期'] = old_df['紀錄日期'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(8)
                                final_save_df = pd.concat([old_df[old_df['紀錄日期'] != anchor_date_str], save_df], ignore_index=True)
                            else: final_save_df = save_df
                            conn.update(spreadsheet=SHEET_URL, worksheet="選股歷史", data=final_save_df)
                            st.session_state['last_gsheet_save_date'] = anchor_date_str
                            hist_combined = final_save_df.copy()
                        except Exception as e: st.warning(f"⚠️ 歷史同步暫緩({e})")
                elif not valid_calc:
                    st.warning("⚠️ 本次計算總分多數為 0，已啟動防呆攔截機制：暫不覆寫 Google Sheets 歷史紀錄。請點擊上方按鈕載入最新籌碼大數據。")

                # ==========================================
                # 🚀 局部渲染魔法 (Fragment) 避免畫面亂跳
                # ==========================================
                st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)
                
                @st.fragment
                def render_pool_interactive_ui(f_res_df, f_hist_combined):
                    selected_view = st.radio(
                        "切換檢視面板：",
                        ["🔹 今日最新排行", "🔹 歷史分數追蹤表", "🔹 模型驗證：每週 Top 5 追蹤"],
                        horizontal=True,
                        label_visibility="collapsed",
                        key="pool_view_state"
                    )
                    
                    if selected_view in ["🔹 今日最新排行", "今日最新排行"]:
                        st.dataframe(f_res_df, use_container_width=True, hide_index=True, column_config={"▼明細": st.column_config.TextColumn("▼明細", help="滑鼠游標停留在這裡查看", width="small", max_chars=4)})
                        
                        st.write("---")
                        st.markdown("### 🧩 觀察名單中的資金聚落")
                        st.caption("將上方觀察名單轉換為產業面積大小，觀察法人口袋中持股變化集中的標的，切換顯示 總分 ▼變量  △ 名次 一覽 (我們排除 ETF 與債券)。")
                        
                        if not f_res_df.empty and STOCK_DICT:
                            st.write("")
                            c_opt, c_search = st.columns([3, 1.5])
                            with c_opt:
                                pool_filter = st.radio("設定觀測範圍與排序：", 
                                    ["全部顯示 (預設)", "顯示總分前100名", "顯示 ▼變量 前100名", "顯示 △ 前100名"], 
                                    horizontal=True, key="pool_treemap_filter"
                                )
                            with c_search:
                                pool_search = st.text_input("🔍 板塊內標的搜尋", placeholder="輸入代號/名稱以聚焦...", key="pool_treemap_search")

                            treemap_pool_df = f_res_df.copy()

                            treemap_pool_df['數值_總分'] = pd.to_numeric(treemap_pool_df['總分'], errors='coerce').fillna(0.0)
                            treemap_pool_df['數值_△'] = pd.to_numeric(treemap_pool_df['△'].astype(str).str.replace('+', '', regex=False).str.replace('%', '', regex=False), errors='coerce').fillna(0.0)
                            
                            if '▼變量' in treemap_pool_df.columns:
                                treemap_pool_df['數值_變量'] = pd.to_numeric(treemap_pool_df['▼變量'], errors='coerce').fillna(0.0)
                            else:
                                treemap_pool_df['數值_變量'] = 0.0

                            if "總分" in pool_filter:
                                treemap_pool_df = treemap_pool_df.nlargest(100, '數值_總分')
                            elif "變量" in pool_filter:
                                treemap_pool_df = treemap_pool_df.nlargest(100, '數值_變量')
                            elif "△" in pool_filter:
                                treemap_pool_df = treemap_pool_df.nlargest(100, '數值_△')

                            if pool_search:
                                query = pool_search.strip()
                                treemap_pool_df = treemap_pool_df[
                                    treemap_pool_df['代號'].astype(str).str.contains(query, case=False, na=False) | 
                                    treemap_pool_df['名稱'].astype(str).str.contains(query, case=False, na=False)
                                ]
                                if treemap_pool_df.empty:
                                    st.warning(f"找不到符合「{query}」的標的。")

                            treemap_pool_df['產業別'] = treemap_pool_df['代號'].astype(str).apply(
                                lambda sid: STOCK_DICT.get(sid, {}).get("industry", "ETF / 債券 / 其他")
                            )
                            treemap_pool_df['產業別'] = treemap_pool_df['產業別'].replace('', 'ETF / 債券 / 其他')

                            pool_excluded_etfs = treemap_pool_df[treemap_pool_df['產業別'] == 'ETF / 債券 / 其他'].sort_values(by='代號').copy()
                            treemap_pool_df = treemap_pool_df[treemap_pool_df['產業別'] != 'ETF / 債券 / 其他']

                            if not treemap_pool_df.empty:
                                treemap_pool_df['計數'] = 1 
                                today_counts = treemap_pool_df['產業別'].value_counts().to_dict()

                                def format_industry_label(industry):
                                    t_count = today_counts.get(industry, 0)
                                    return f"<b>{industry}</b><br><span style='font-size: 13px;'>{t_count}檔</span>"
                                treemap_pool_df['產業別'] = treemap_pool_df['產業別'].apply(format_industry_label)

                                treemap_pool_df['總分_格式化'] = treemap_pool_df['數值_總分'].apply(lambda x: f"{x:.1f}")
                                treemap_pool_df['△_格式化'] = treemap_pool_df['數值_△'].apply(lambda x: f"+{x:.2f}" if x > 0 else f"{x:.2f}")

                                def format_clean_stock_label(row):
                                    name = row.get('名稱', '')
                                    score = row.get('總分_格式化', '0.0')
                                    return f"<b>{name}</b><br><span style='font-size: 11px; color: #E5E7EB;'>{score}分</span>"
                                treemap_pool_df['顯示名稱'] = treemap_pool_df.apply(format_clean_stock_label, axis=1)

                                hover_columns = ['代號', '總分_格式化', '▼明細', '△_格式化', '最新動態', '大股東動向'] 

                                custom_dark_colors = [
                                    "rgba(60, 84, 62, 0.85)",     "rgba(78, 34, 28, 0.85)",     "rgba(81, 81, 168, 0.85)",    "rgba(167, 77, 110, 0.85)", 
                                    "rgba(67, 38, 58, 0.85)",     "rgba(244, 124, 35, 0.85)",   "rgba(177, 128, 236, 0.85)",  "rgba(13, 82, 89, 0.85)", 
                                    "rgba(111, 97, 94, 0.85)",    "rgba(196, 8, 28, 0.85)",     "rgba(30, 41, 59, 0.85)",     "rgba(77, 83, 60, 0.85)", 
                                    "rgba(107, 29, 47, 0.85)",    "rgba(70, 130, 180, 0.85)",   "rgba(133, 100, 4, 0.85)",    "rgba(30, 27, 75, 0.85)", 
                                    "rgba(6, 78, 59, 0.85)",      "rgba(154, 52, 18, 0.85)",    "rgba(112, 26, 117, 0.85)",   "rgba(51, 65, 85, 0.85)"
                                ]

                                fig = px.treemap(
                                    treemap_pool_df,
                                    path=[px.Constant("板塊資金聚落"), '產業別', '顯示名稱'], 
                                    values='計數',
                                    color='產業別', 
                                    hover_data=hover_columns, 
                                    color_discrete_sequence=custom_dark_colors
                                )

                                fig.update_traces(
                                    textinfo="label", 
                                    textfont=dict(color="white", size=15),
                                    marker=dict(line=dict(color='#0B0F19', width=2), pad=dict(t=35, l=10, r=10, b=10)),
                                    hovertemplate=(
                                        '<b>%{label}</b><br>'
                                        '股票代號: %{customdata[0]}<br>'
                                        '模型總分: <b>%{customdata[1]} 分</b><br>'
                                        '▼明細: %{customdata[2]}<br>'
                                        '△: %{customdata[3]}<br>'
                                        '最新動態: %{customdata[4]}<br>'
                                        '大股東動向: %{customdata[5]}<br>'
                                        '<extra></extra>' 
                                    )
                                )
                                
                                fig.update_layout(
                                    margin=dict(t=30, l=0, r=0, b=0),
                                    height=650, 
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(family="sans-serif") 
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                if not pool_search:
                                    st.info("⚪ 目前觀察名單中沒有一般產業的股票。")

                            if not pool_excluded_etfs.empty:
                                st.write("")
                                st.markdown("##### 🗑️ 本次已剔除的非一般產業 (ETF / 債券 / 指數)")
                                st.caption("以下標的已進榜觀察名單，但因非一般企業已從上方產業聚落中剔除。💡 **游標懸停於標籤可查看詳細分數與大股東動向。**")
                                
                                tags_html = ""
                                
                                for _, r in pool_excluded_etfs.iterrows():
                                    name = str(r.get('名稱', ''))
                                    sid = str(r.get('代號', ''))
                                    detail = str(r.get('▼明細', '-'))
                                    dyn = str(r.get('最新動態', '-'))
                                    holder = str(r.get('大股東動向', '-'))
                                    
                                    d_val = r.get('數值_△', 0.0)
                                    s_val = r.get('數值_總分', 0.0)
                                    
                                    safe_name = html.escape(name, quote=True)
                                    safe_sid = html.escape(sid, quote=True)
                                    safe_detail = html.escape(detail, quote=True)
                                    safe_dyn = html.escape(dyn, quote=True)
                                    safe_holder = html.escape(holder, quote=True)
                                    
                                    if d_val > 0:
                                        bg_color = "rgba(255, 75, 75, 0.15)"   
                                        border_color = "rgba(255, 75, 75, 0.4)" 
                                        text_color = "#FF4B4B"                  
                                        d_str = f"+{d_val:.2f}"
                                    elif d_val < 0:
                                        bg_color = "rgba(0, 230, 118, 0.15)"   
                                        border_color = "rgba(0, 230, 118, 0.4)" 
                                        text_color = "#00E676"                  
                                        d_str = f"{d_val:.2f}"
                                    else:
                                        bg_color = "rgba(30, 41, 59, 0.6)"     
                                        border_color = "#334155"
                                        text_color = "#94A3B8"
                                        d_str = "0.00"
                                        
                                    tooltip_text = (
                                        f"【{safe_name}】&#10;"
                                        f"股票代號: {safe_sid}&#10;"
                                        f"模型總分: {s_val:.1f} 分&#10;"
                                        f"單日△: {d_str}&#10;"
                                        f"▼明細: {safe_detail}&#10;"
                                        f"最新動態: {safe_dyn}&#10;"
                                        f"大股東動向: {safe_holder}"
                                    )
                                    
                                    tags_html += f"<div title=\"{tooltip_text}\" style=\"background-color: {bg_color}; color: #E2E8F0; border: 1px solid {border_color}; padding: 6px 14px; border-radius: 20px; margin: 5px; display: inline-flex; align-items: center; font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); cursor: help; transition: transform 0.2s;\">{safe_name} ({safe_sid}) <span style='color: {text_color}; font-weight: bold; margin-left: 8px;'>△ {d_str}</span></div>"
                                
                                st.markdown(f"<div style='margin-top: 5px; line-height: 2.4;'>{tags_html}</div>", unsafe_allow_html=True)
                                
                        else:
                            st.info("⚪ 尚無數據或找不到產業字典，無法繪製產業板塊圖。")

                    elif selected_view == "🔹 歷史分數追蹤表":
                        try:
                            if not f_hist_combined.empty:
                                recent_dates = sorted(f_hist_combined['紀錄日期'].unique(), reverse=True)[:20]
                                df_h = f_hist_combined[f_hist_combined['紀錄日期'].isin(recent_dates)].copy()
                                id_col = '代號' if '代號' in df_h.columns else '股票代號' if '股票代號' in df_h.columns else None
                                if id_col and '總分' in df_h.columns:
                                    df_h['日期'] = df_h['紀錄日期'].apply(lambda x: f"{x[4:6]}/{x[6:]}" if len(x)==8 else x)
                                    df_h['代號'] = df_h[id_col].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
                                    hist_pivot = df_h[['代號', '總分', '日期']].pivot_table(index='代號', columns='日期', values='總分', aggfunc='first').reset_index()
                                    sorted_date_columns = sorted([col for col in hist_pivot.columns if col not in ['代號', '名稱']], reverse=True)
                                    hist_pivot = hist_pivot[['代號'] + sorted_date_columns]
                                    hist_pivot.insert(1, '名稱', hist_pivot['代號'].map(dict(zip(f_res_df['代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True), f_res_df['名稱']))).fillna('-'))
                                    hist_pivot = hist_pivot[hist_pivot['名稱'] != '-']
                                    if not hist_pivot.empty and sorted_date_columns[0] in hist_pivot.columns:
                                        st.dataframe(hist_pivot.sort_values(by=sorted_date_columns[0], ascending=False).reset_index(drop=True), use_container_width=True, hide_index=True)
                                        st.info("我們也記錄了法人們口袋名單在觀察名單的總分變化，試著學習觀察籌碼動能的延續性與驗證 ▼變量...")
                                    else:
                                        st.warning("⚪ 尚無足夠的歷史分數紀錄。")
                            else: 
                                st.warning("⚪ 尚無足夠的歷史分數紀錄。")
                        except Exception as e: 
                            st.error(f"發生錯誤: {e}")

                    elif selected_view == "🔹 模型驗證：每週 Top 5 追蹤":
                        st.markdown("### 🏆 嚴選 5 檔模型追蹤")
                        st.info("💡 我們先排除了法人丟出籌碼警示的標的，並根據總分與當日△選出前 5 名，但是有時候倒貨僅是換手，這個部分還相當困難阿，真是傷腦筋")
                        if not f_res_df.empty:
                            safe_df = f_res_df[f_res_df['賣出警示'] == "-"].copy()
                            if not safe_df.empty:
                                safe_df['數值△'] = pd.to_numeric(safe_df['△'].astype(str).str.replace('+', '', regex=False).str.replace('%', '', regex=False), errors='coerce').fillna(0)
                                top5_df = safe_df.sort_values(by=['總分', '數值△'], ascending=[False, False]).head(5).drop(columns=['數值△'])
                                
                                cols = st.columns(5)
                                for idx, (i, row) in enumerate(top5_df.iterrows()):
                                    with cols[idx]:
                                        delta_str = str(row['△'])
                                        delta_color = "#FF4B4B" if "+" in delta_str else ("#00E272" if "-" in delta_str else "#E2E8F0")
                                        st.markdown(f"""
                                            <div style="background-color:rgba(0, 210, 255, 0.05); border-top: 3px solid #00D2FF; padding: 10px; border-radius: 5px;">
                                                <h4 style="margin:0; color:#E2E8F0;">{row['名稱']}</h4>
                                                <p style="margin:0; font-size:12px; color:#A0AEC0;">{row['代號']}</p>
                                                <h2 style="margin:10px 0; color:#00D2FF;">{row['總分']:.1f} 分</h2>
                                                <p style="margin:0; font-size:14px;"><strong>當日△:</strong> <span style="color:{delta_color}; font-weight:bold;">{delta_str}</span></p>
                                                <p style="margin:5px 0 0 0; font-size:12px; line-height:1.2;">{row['大股東動向']}</p>
                                            </div>
                                        """, unsafe_allow_html=True)
                                
                                st.write("")
                                st.dataframe(top5_df[['代號', '名稱', '總分', '▼變量', '△', '最新動態', '▼明細']], use_container_width=True, hide_index=True)
                                
                                st.write("---")
                                c_space, c_main = st.columns([3, 2])
                                with c_main:
                                    with st.expander("🔐 站長用寫入追蹤名單", expanded=True):
                                        track_pw = st.text_input("密碼", type="password", key="track_pw")
                                        
                                        expected_pw = st.secrets["passwords"]["pool_admin"]
                                        
                                        if track_pw == expected_pw:
                                            st.markdown("""
                                            <style>
                                            div[data-testid="stButton"] > button { padding: 0.25rem 0.5rem; font-size: 14px; }
                                            </style>
                                            """, unsafe_allow_html=True)
                                            
                                            if st.button("💾 儲存至 Google 雲端", type="primary", use_container_width=True):
                                                with st.spinner("正在抓取當前收盤價並寫入雲端..."):
                                                    import datetime
                                                    track_date = datetime.datetime.now().strftime("%Y-%m-%d")
                                                    current_prices = {}
                                                    
                                                    # 💡 效能救星：改呼叫我們自己寫的快取函數
                                                    for sid in top5_df['代號']:
                                                        current_prices[sid] = get_cached_stock_price(sid)
                                                    
                                                    top5_df['鎖定日期'] = track_date
                                                    top5_df['鎖定收盤價'] = top5_df['代號'].astype(str).map(current_prices)
                                                    
                                                    try:
                                                        try: old_track = conn.read(spreadsheet=SHEET_URL, worksheet="歷史名單回測觀察", ttl=0).dropna(how="all")
                                                        except: old_track = pd.DataFrame()
                                                        new_track = pd.concat([old_track, top5_df], ignore_index=True)
                                                        conn.update(spreadsheet=SHEET_URL, worksheet="歷史名單回測觀察", data=new_track)
                                                        st.success(f"✅ 已成功將 {track_date} 的名單寫入 Google Sheets！")
                                                    except Exception as e:
                                                        st.error(f"❌ 寫入失敗：{e} (請確認 Google Sheets 是否已建立『歷史名單回測觀察』工作表)")
                                        elif track_pw != "": st.error("密碼錯誤")
                                            
                        st.markdown("### 📊 歷史名單回測觀察")
                        try:
                            # 💡 效能救星：將 ttl 從 0 提升到 60 秒，避免頁面稍有互動就一直去讀取 Google Sheets 導致卡死
                            history_track_df = conn.read(spreadsheet=SHEET_URL, worksheet="歷史名單回測觀察", ttl=60).dropna(how="all")
                            if not history_track_df.empty:
                                selected_week = st.selectbox("選擇要回顧的鎖定日期", sorted(history_track_df['鎖定日期'].unique(), reverse=True))
                                week_df = history_track_df[history_track_df['鎖定日期'] == selected_week].copy()
                                
                                import datetime
                                from datetime import timedelta
                                lock_date_obj = datetime.datetime.strptime(selected_week, "%Y-%m-%d")
                                days_passed = (datetime.datetime.now() - lock_date_obj).days
                                
                                is_expired = days_passed >= 28 
                                
                                if is_expired:
                                    status_tag = "🔴 已結案 (凍結在第4週)"
                                    target_start = lock_date_obj + timedelta(days=28)
                                    start_str = target_start.strftime("%Y-%m-%d")
                                    end_str = (target_start + timedelta(days=5)).strftime("%Y-%m-%d")
                                else:
                                    weeks_passed = (days_passed // 7) + 1
                                    status_tag = f"🟢 追蹤中 (第 {weeks_passed} 週)"
                                    start_str = None 

                                st.markdown(f"**目前狀態：** `{status_tag}` ｜ **已鎖定：** `{days_passed} 天`")

                                with st.spinner("正在連線抓取檢測價格..."):
                                    latest_prices = {}
                                    for sid in week_df['代號'].astype(str).str.replace(r'\.0$', '', regex=True):
                                        # 💡 效能救星：改呼叫快取，抓過一次就秒出
                                        if start_str: 
                                            latest_prices[sid] = get_cached_stock_price(sid, start_str, end_str)
                                        else: 
                                            latest_prices[sid] = get_cached_stock_price(sid)

                                col_price_name = "結案價格" if is_expired else "最新價格"
                                week_df[col_price_name] = week_df['代號'].astype(str).str.replace(r'\.0$', '', regex=True).map(latest_prices)
                                
                                def calc_price_return(row):
                                    try:
                                        lock_p = float(row.get('鎖定收盤價', 0))
                                        curr_p = float(row.get(col_price_name, 0))
                                        if lock_p > 0 and curr_p > 0:
                                            pct = ((curr_p - lock_p) / lock_p) * 100
                                            if pct > 0: return f"🚀 +{pct:.1f}%"
                                            elif pct < 0: return f"🩸 {pct:.1f}%"
                                            else: return "0.0%"
                                        return "-"
                                    except: return "-"
                                    
                                week_df['區間報酬'] = week_df.apply(calc_price_return, axis=1)

                                if not f_res_df.empty:
                                    today_scores = dict(zip(f_res_df['代號'].astype(str), f_res_df['總分']))
                                    week_df['今日分數'] = week_df['代號'].astype(str).str.replace(r'\.0$', '', regex=True).map(today_scores).fillna(0)
                                    
                                    def score_diff(row):
                                        try:
                                            diff = float(row['今日分數']) - float(row['總分']) 
                                            if diff > 0: return f"📈 +{diff:.1f}"
                                            elif diff < 0: return f"📉 {diff:.1f}"
                                            else: return "-"
                                        except: return "-"
                                        
                                    week_df['模型分數變化'] = week_df.apply(score_diff, axis=1)
                                    
                                    show_cols = ['鎖定日期', '▼明細', '代號', '名稱', '鎖定收盤價', col_price_name, '區間報酬', '總分', '今日分數', '模型分數變化']

                                    st.dataframe(
                                        week_df[[c for c in show_cols if c in week_df.columns]], 
                                        use_container_width=True, 
                                        hide_index=True,
                                        column_config={
                                            "▼明細": st.column_config.TextColumn(
                                                "▼明細", 
                                                help="滑鼠游標停留在這裡，查看鎖定當時的各項權重分數", 
                                                width="small", 
                                                max_chars=4
                                            )
                                        }
                                    )
                                    
                                    if is_expired:
                                        st.info("🔒 此梯次名單已追蹤滿 4 週。為了客觀評估波段策略，此表已凍結於結案當時的收盤價與績效，不再隨每日盤勢波動。")
                                    else:
                                        st.info("💡 **驗證方法**：觀察鎖定股票的『區間報酬』是否為正，並核對『模型分數變化』是否持續上升。這能印證籌碼集中度與股價的連動性！")
                        except Exception as e:
                            st.write("⚪ 尚無歷史追蹤紀錄，請輸入密碼鎖定第一筆，或確認 Google Sheets 已建立工作表。")

                # 👇 呼叫這個局部渲染魔法函數，把剛剛算好的分數傳進去！
                render_pool_interactive_ui(res_df, hist_combined)
