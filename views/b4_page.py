# views/b4_page.py
import streamlit as st
import pandas as pd
import os
import glob
import re
from utils.data_utils import robust_read_csv 

# ==========================================
# 🌟 區塊 4 專屬工具函數區 (純運算，無 UI)
# ==========================================
def get_specific_margin_data(DATA_DIR, keyword):
    """特定籌碼數據讀取 (改用 glob 提升搜尋效率)"""
    search_pattern = os.path.join(DATA_DIR, f"*{keyword}*.csv")
    found_files = glob.glob(search_pattern)
    
    if not found_files:
        return pd.DataFrame(), f"找不到包含『{keyword}』的檔案"
    
    latest_file = sorted(found_files, key=lambda x: os.path.basename(x), reverse=True)[0]
    file_name = os.path.basename(latest_file)
    
    try:
        df = robust_read_csv(latest_file)
        if df.empty:
            return pd.DataFrame(), f"讀取成功但內容為空: {file_name}"
        
        df.columns = df.columns.astype(str).str.replace('\ufeff', '').str.strip()
        
        for col in df.columns:
            if "幅度" in col or "張數" in col or "%" in col or "％" in col or "漲跌" in col:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df, file_name
    except Exception as e:
        return pd.DataFrame(), f"讀取崩潰 ({file_name}): {str(e)}"

def process_margin_df(df, type_name):
    """欄位清理與萃取 (移除 UI 過濾，保留 100% 原始資料給底層)"""
    if df.empty: return df
    df = df.copy()
    
    cols_to_drop = [c for c in df.columns if "更新" in str(c) and "日期" in str(c)]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
        
    target_idx = -1
    if type_name == "幅度":
        for i, col in enumerate(df.columns):
            if "3個月" in str(col) and ("%" in str(col) or "％" in str(col)):
                target_idx = i
                break
    else: 
        for i, col in enumerate(df.columns):
            if "3個月" in str(col) and "張數" in str(col):
                target_idx = i
                break
                
    if target_idx != -1:
        df = df.iloc[:, :target_idx+1]
        
    col_name = next((c for c in df.columns if '名稱' in c), None)
    col_id = next((c for c in df.columns if '代號' in c), None)
    
    if col_name and col_id:
        df = df.rename(columns={col_id: '股票代號', col_name: '股票名稱'})
        df['股票代號'] = df['股票代號'].astype(str).str.strip()
        df['股票名稱'] = df['股票名稱'].astype(str).str.strip()

    sort_col = next((c for c in df.columns if '漲跌' in str(c) or '漲幅' in str(c)), None)
    if sort_col:
        df = df.rename(columns={sort_col: '漲跌幅%'}) 
        df['漲跌幅%'] = pd.to_numeric(df['漲跌幅%'], errors='coerce').fillna(0)

    df = df.reset_index(drop=True)
    df.index = df.index + 1
    return df

def build_squeeze_radar(DATA_DIR):
    """軋空雷達運算引擎"""
    buy_pattern = os.path.join(DATA_DIR, "*三大法人買超佔成交比*.csv")
    margin_dec_pattern = os.path.join(DATA_DIR, "*融資減少張數*.csv")       
    sbl_dec_pattern = os.path.join(DATA_DIR, "*借券賣出減少金額*.csv")   
    short_inc_pattern = os.path.join(DATA_DIR, "*融券增加張數*.csv")      
    
    buy_files = sorted(glob.glob(buy_pattern), reverse=True)
    margin_dec_files = sorted(glob.glob(margin_dec_pattern), reverse=True)
    sbl_dec_files = sorted(glob.glob(sbl_dec_pattern), reverse=True)
    short_inc_files = sorted(glob.glob(short_inc_pattern), reverse=True)
    
    if not buy_files: return pd.DataFrame(), "找不到三大法人買超檔案", "", False

    def get_date(filepath):
        match = re.search(r'(\d{8})', os.path.basename(filepath))
        return match.group(1) if match else ""
    
    dates = [
        get_date(buy_files[0]) if buy_files else "",
        get_date(margin_dec_files[0]) if margin_dec_files else "",
        get_date(sbl_dec_files[0]) if sbl_dec_files else "",
        get_date(short_inc_files[0]) if short_inc_files else ""
    ]
    
    valid_dates = [d for d in dates if d]
    is_sync = len(set(valid_dates)) == 1 if valid_dates else False
    display_date = f"{dates[0][:4]}/{dates[0][4:6]}/{dates[0][6:]}" if len(dates[0]) == 8 else dates[0]

    try:
        df_buy = robust_read_csv(buy_files[0])
        df_buy.columns = [str(c).replace(" ", "").replace("\n", "").replace("\ufeff", "").strip() for c in df_buy.columns]
        
        id_col = next((c for c in df_buy.columns if '代號' in c), df_buy.columns[1])
        name_col = next((c for c in df_buy.columns if '名稱' in c), df_buy.columns[2])
        df_buy = df_buy.rename(columns={id_col: '代號', name_col: '名稱'})
        df_buy['代號'] = df_buy['代號'].astype(str).str.strip()
        
        keep_cols = ['代號', '名稱', '成交', '漲跌價', '漲跌幅']
        for keyword in ['當日', '2日', '3日', '5日']:
            matched_cols = [c for c in df_buy.columns if keyword in c and '買賣超佔成交' in c]
            if matched_cols: keep_cols.append(matched_cols[0])
                
        keep_cols = list(dict.fromkeys(keep_cols)) 
        keep_cols = [c for c in keep_cols if c in df_buy.columns]
        df_squeeze = df_buy[keep_cols].copy()
        
        rename_mapping = {}      
        for col in df_squeeze.columns:
            if '買賣超佔成交' in col:
                new_name = col.replace('買賣超佔成交', '買佔成交')
                if '當日' in new_name: new_name = new_name.replace('當日', '▼當日')
                rename_mapping[col] = new_name                
        df_squeeze = df_squeeze.rename(columns=rename_mapping)
        
        for col in df_squeeze.columns:
            if col not in ['代號', '名稱']:
                df_squeeze[col] = pd.to_numeric(df_squeeze[col].astype(str).str.replace('%', '', regex=False), errors='coerce')
                if pd.api.types.is_float_dtype(df_squeeze[col]):
                    df_squeeze[col] = df_squeeze[col].round(2)
        
        df_squeeze = df_squeeze[df_squeeze['漲跌幅'] > 0] 
    except Exception as e:
        return pd.DataFrame(), f"讀取買超母表失敗: {str(e)}", "", False

    def get_danger_ids(files, data_type='vol'):
        danger_ids = set()
        if files:
            try:
                df_temp = robust_read_csv(files[0])
                t_id_col = next((c for c in df_temp.columns if '代號' in c), None)
                if t_id_col:
                    df_temp[t_id_col] = df_temp[t_id_col].astype(str).str.replace(r'\D', '', regex=True)
                    
                    col_5d = next((c for c in df_temp.columns if '5日' in c), None)
                    col_price = next((c for c in df_temp.columns if '成交' in c and '買賣' not in c), None)
                    
                    if col_5d:
                        df_temp['num_5d'] = pd.to_numeric(df_temp[col_5d].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0).abs()
                        
                        if data_type == 'amt':
                            valid_df = df_temp[df_temp['num_5d'] >= 1000]
                            danger_ids = set(valid_df[t_id_col])
                        elif data_type == 'vol' and col_price:
                            df_temp['price'] = pd.to_numeric(df_temp[col_price].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)
                            valid_df = df_temp[(df_temp['num_5d'] * df_temp['price'] * 1000) >= 10000000]
                            danger_ids = set(valid_df[t_id_col])
            except: pass
        return danger_ids

    df_squeeze['📉融資減'] = df_squeeze['代號'].apply(lambda x: "✔️" if x in get_danger_ids(margin_dec_files, 'vol') else "")
    df_squeeze['📉借券減'] = df_squeeze['代號'].apply(lambda x: "✔️" if x in get_danger_ids(sbl_dec_files, 'amt') else "")
    df_squeeze['📈融券增'] = df_squeeze['代號'].apply(lambda x: "✔️" if x in get_danger_ids(short_inc_files, 'vol') else "")
    
    df_squeeze['軋空指數'] = 1 + (df_squeeze['📉融資減'] == "✔️").astype(int) + (df_squeeze['📉借券減'] == "✔️").astype(int) + (df_squeeze['📈融券增'] == "✔️").astype(int)
    df_squeeze = df_squeeze.sort_values(by=['軋空指數', '漲跌幅'], ascending=[False, False]).reset_index(drop=True)
    
    def get_squeeze_tag(score):
        if score == 4: return "💥 終極"
        elif score == 3: return "🚀 強軋"
        elif score == 2: return "🔥 點火"
        return "🔼 進駐"
        
    df_squeeze.insert(2, '軋空評估', df_squeeze['軋空指數'].apply(get_squeeze_tag))
    df_squeeze = df_squeeze.drop(columns=['軋空指數'])
    
    return df_squeeze, "Success", display_date, is_sync

def build_risk_radar(DATA_DIR):
    """避險雷達運算引擎"""
    sell_pattern = os.path.join(DATA_DIR, "*三大法人賣超佔成交比*.csv")
    margin_pattern = os.path.join(DATA_DIR, "*融資增加張數*.csv")
    short_pattern = os.path.join(DATA_DIR, "*借券賣出增加金額*.csv")
    
    sell_files = sorted(glob.glob(sell_pattern), reverse=True)
    margin_files = sorted(glob.glob(margin_pattern), reverse=True)
    short_files = sorted(glob.glob(short_pattern), reverse=True)
    
    if not sell_files: return pd.DataFrame(), "找不到三大法人賣超檔案", "", False

    def get_date(filepath):
        match = re.search(r'(\d{8})', os.path.basename(filepath))
        return match.group(1) if match else ""
    
    sell_date = get_date(sell_files[0]) if sell_files else ""
    margin_date = get_date(margin_files[0]) if margin_files else ""
    short_date = get_date(short_files[0]) if short_files else ""
    
    is_sync = (sell_date == margin_date == short_date)
    display_date = f"{sell_date[:4]}/{sell_date[4:6]}/{sell_date[6:]}" if len(sell_date) == 8 else sell_date

    try:
        df_sell = robust_read_csv(sell_files[0])
        df_sell.columns = [str(c).replace(" ", "").replace("\n", "").replace("\ufeff", "").strip() for c in df_sell.columns]
        
        id_col = next((c for c in df_sell.columns if '代號' in c), df_sell.columns[1])
        name_col = next((c for c in df_sell.columns if '名稱' in c), df_sell.columns[2])
        df_sell = df_sell.rename(columns={id_col: '代號', name_col: '名稱'})
        df_sell['代號'] = df_sell['代號'].astype(str).str.strip()
        
        keep_cols = ['代號', '名稱']
        for keyword in ['成交', '漲跌價', '漲跌幅', '當日', '2日', '3日', '5日']:
            matched_cols = [c for c in df_sell.columns if keyword in c and '月' not in c and '年' not in c]
            if matched_cols: keep_cols.append(matched_cols[0])
                
        keep_cols = list(dict.fromkeys(keep_cols))
        df_risk = df_sell[keep_cols].copy()
        
        rename_mapping = {}
        for col in df_risk.columns:
            if '買賣超佔成交' in col:
                new_name = col.replace('買賣超佔成交', '賣佔成交')
                if '當日' in new_name: new_name = new_name.replace('當日', '▼當日')
                rename_mapping[col] = new_name
        df_risk = df_risk.rename(columns=rename_mapping)
        
        for col in df_risk.columns:
            if col not in ['代號', '名稱']:
                df_risk[col] = pd.to_numeric(df_risk[col].astype(str).str.replace('%', '', regex=False), errors='coerce')
                if pd.api.types.is_float_dtype(df_risk[col]):
                    df_risk[col] = df_risk[col].round(2)
        
        df_risk = df_risk[df_risk['漲跌幅'] < 0] 
    except Exception as e:
        return pd.DataFrame(), f"讀取賣超母表失敗: {str(e)}", "", False

    def get_danger_ids(files, data_type='vol'):
        danger_ids = set()
        if files:
            try:
                df_temp = robust_read_csv(files[0])
                t_id_col = next((c for c in df_temp.columns if '代號' in c), None)
                if t_id_col:
                    df_temp[t_id_col] = df_temp[t_id_col].astype(str).str.replace(r'\D', '', regex=True)
                    
                    col_5d = next((c for c in df_temp.columns if '5日' in c), None)
                    col_price = next((c for c in df_temp.columns if '成交' in c and '買賣' not in c), None)
                    
                    if col_5d:
                        df_temp['num_5d'] = pd.to_numeric(df_temp[col_5d].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0).abs()
                        
                        if data_type == 'amt':
                            valid_df = df_temp[df_temp['num_5d'] >= 1000]
                            danger_ids = set(valid_df[t_id_col])
                        elif data_type == 'vol' and col_price:
                            df_temp['price'] = pd.to_numeric(df_temp[col_price].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)
                            valid_df = df_temp[(df_temp['num_5d'] * df_temp['price'] * 1000) >= 10000000]
                            danger_ids = set(valid_df[t_id_col])
            except: pass
        return danger_ids

    margin_danger_ids = get_danger_ids(margin_files, 'vol')
    short_danger_ids = get_danger_ids(short_files, 'amt')

    df_risk['🚨融資套牢'] = df_risk['代號'].apply(lambda x: "✔️" if x in margin_danger_ids else "")
    df_risk['📉借券大增'] = df_risk['代號'].apply(lambda x: "✔️" if x in short_danger_ids else "")
    
    df_risk['危險指數'] = 1 + (df_risk['🚨融資套牢'] == "✔️").astype(int) + (df_risk['📉借券大增'] == "✔️").astype(int)
    df_risk = df_risk.sort_values(by=['危險指數', '漲跌幅'], ascending=[False, True]).reset_index(drop=True)
    
    def get_risk_tag(score):
        if score == 3: return "☠️ 極危"
        elif score == 2: return "🚨 高危"
        return "⚠️ 初危"
        
    df_risk.insert(2, '套牢評估', df_risk['危險指數'].apply(get_risk_tag))
    df_risk = df_risk.drop(columns=['危險指數'])
    
    return df_risk, "Success", display_date, is_sync


# ==========================================
# 💡 效能救星 1：將複雜運算加上快取保護
# ==========================================
@st.cache_data(show_spinner=False, ttl=300)
def get_cached_b4_data(DATA_DIR):
    """一次性讀取所有資券資料與雷達，並回傳字典 (Dict) 結構"""
    
    # 4-1
    df_41_pct, _ = get_specific_margin_data(DATA_DIR, "融資減少幅度")
    df_41_vol, _ = get_specific_margin_data(DATA_DIR, "融資減少張數")
    
    # 4-2
    df_42_pct, _ = get_specific_margin_data(DATA_DIR, "借券賣出減少幅度")
    df_42_vol, _ = get_specific_margin_data(DATA_DIR, "借券賣出減少張數")

    # 4-3
    df_43_pct, _ = get_specific_margin_data(DATA_DIR, "融券增加幅度")
    df_43_vol, _ = get_specific_margin_data(DATA_DIR, "融券增加張數")

    # 回測隱藏版
    df_inc_margin_pct, _ = get_specific_margin_data(DATA_DIR, "融資增加幅度")
    df_inc_margin_vol, _ = get_specific_margin_data(DATA_DIR, "融資增加張數")
    df_inc_short_pct, _ = get_specific_margin_data(DATA_DIR, "借券賣出增加幅度")
    df_inc_short_vol, _ = get_specific_margin_data(DATA_DIR, "借券賣出增加張數")
    df_inc_short_amt, _ = get_specific_margin_data(DATA_DIR, "借券賣出增加金額")
    df_dec_short_amt, _ = get_specific_margin_data(DATA_DIR, "借券賣出減少金額")
    
    # 雷達
    df_squeeze, _, date_sq, sync_sq = build_squeeze_radar(DATA_DIR)
    df_risk, _, date_rk, sync_rk = build_risk_radar(DATA_DIR)

    return {
        'df_margin_pct': process_margin_df(df_41_pct, "幅度"),
        'df_margin_vol': process_margin_df(df_41_vol, "張數"),
        'df_short_pct': process_margin_df(df_42_pct, "幅度"),
        'df_short_vol': process_margin_df(df_42_vol, "張數"),
        'df_margin_plus_pct': process_margin_df(df_43_pct, "幅度"),
        'df_margin_plus_vol': process_margin_df(df_43_vol, "張數"),
        
        # 供權重回測使用的隱藏資券資料
        'df_margin_inc_pct': process_margin_df(df_inc_margin_pct, "幅度"),
        'df_margin_inc_vol': process_margin_df(df_inc_margin_vol, "張數"),
        'df_short_inc_pct': process_margin_df(df_inc_short_pct, "幅度"),
        'df_short_inc_vol': process_margin_df(df_inc_short_vol, "張數"),
        'df_short_inc_amt': process_margin_df(df_inc_short_amt, "金額"),
        'df_short_dec_amt': process_margin_df(df_dec_short_amt, "金額"),
        
        # 雷達
        'b4_squeeze_radar': {'df': df_squeeze, 'date': date_sq, 'sync': sync_sq},
        'b4_risk_radar': {'df': df_risk, 'date': date_rk, 'sync': sync_rk}
    }


# ==========================================
# ⚙️ 後台資料引擎 (橋接函式)
# ==========================================
def sync_b4_data(DATA_DIR):
    """將快取的結果寫入 session_state，完美相容權重回測與側邊欄"""
    cached_data = get_cached_b4_data(DATA_DIR)
    for k, v in cached_data.items():
        st.session_state[k] = v


# ==========================================
# 🖼️ 局部渲染魔法區域 (Fragments)
# ==========================================

def apply_ui_filter(df, show_etf, show_bond):
    """前端專用過濾器"""
    if df is None or df.empty: return df
    mask = (df['股票代號'].str.len() == 4)
    if show_etf: mask |= ((df['股票代號'].str.len() >= 5) & (~df['股票代號'].str.endswith('B')))
    if show_bond: mask |= df['股票代號'].str.endswith('B')
    res_df = df[mask].copy()
    res_df.index = range(1, len(res_df) + 1)
    return res_df

def render_styled_margin_table(clean_df):
    if clean_df.empty:
        st.warning("⚠️ 無相符資料")
        return
        
    display_df = clean_df.copy()
    change_col = next((c for c in display_df.columns if '漲跌' in str(c) or '漲幅' in str(c)), None)
    
    for col in display_df.columns:
        if col not in ['股票代號', '股票名稱']:
            try:
                display_df[col] = display_df[col].apply(
                    lambda x: f"{x:.1f}".rstrip('0').rstrip('.') if pd.notna(x) and isinstance(x, (int, float)) else x
                )
            except: pass

    def style_row_by_price(row):
        styles = [''] * len(row)
        if change_col:
            try:
                if float(clean_df.loc[row.name, change_col]) > 0:
                    return ['color: #ff4b4b;'] * len(row)
            except: pass
        return styles

    styled_df = display_df.style.apply(style_row_by_price, axis=1)
    col_config = {
        "股票代號": st.column_config.TextColumn("代號", width="small"),
        "股票名稱": st.column_config.TextColumn("名稱", width="medium")
    }
    st.dataframe(styled_df, use_container_width=True, hide_index=True, column_config=col_config)


@st.fragment
def render_b4_squeeze_radar(sq_data):
    df_squeeze = sq_data['df']
    header_html = "可能軋空雷達 "
    if sq_data['date']:
        header_html += f"<span style='color: #00D2FF; font-size: 0.7em;'>({sq_data['date']})</span>"
        if not sq_data['sync']: header_html += " <span style='color: #ffa500; font-size: 0.5em;'>⏳籌碼待更新</span>"

    st.markdown(f"<h2>{header_html}</h2>", unsafe_allow_html=True)
    st.write("💡 觀察法人們買超，且伴隨融資退場、借券回補或融券逆勢增加的潛在軋空標的。")

    if not df_squeeze.empty:
        show_all_sq = st.checkbox("顯示榜內被法人買超的上漲標的，但籌碼未見軋空特徵", value=False, key="b4_sq_chk")
        df_sq_display = df_squeeze.copy()
        
        if not show_all_sq:
            df_sq_display = df_sq_display[df_sq_display['軋空評估'].str.contains("💥|🚀|🔥", regex=True)]

        if df_sq_display.empty:
            st.success("🎉 目前沒有同時出現法人買超與軋空特徵的強勢名單！")
        else:
            def highlight_squeeze(row):
                return ['color: #ff4b4b;' if c in ['成交', '漲跌價', '漲跌幅'] else '' for c in row.index]
            
            st.dataframe(df_sq_display.style.apply(highlight_squeeze, axis=1).format(precision=2), 
                         use_container_width=True, hide_index=True)
    else:
        st.warning("軋空雷達載入失敗或無資料。")


@st.fragment
def render_b4_risk_radar(rk_data):
    df_risk = rk_data['df']
    header_html = "短線套牢名單 "
    if rk_data['date']:
        header_html += f"<span style='color: #00D2FF; font-size: 0.7em;'>({rk_data['date']})</span>"
        if not rk_data['sync']: header_html += " <span style='color: #ffa500; font-size: 0.5em;'>⏳融券資待更新</span>"

    st.markdown(f"<h2>{header_html}</h2>", unsafe_allow_html=True)
    st.write("💡 法人們賣超，且股價下跌融資套牢或借券增加的籌碼惡化標的。")

    if not df_risk.empty:
        show_all_rk = st.checkbox("顯示榜內被法人賣超的下跌/持平標的但融資借券未上榜", value=False, key="b4_rk_chk")
        df_rk_display = df_risk.copy()
        
        if not show_all_rk:
            df_rk_display = df_rk_display[df_rk_display['套牢評估'].str.contains("☠️|🚨", regex=True)]

        if df_rk_display.empty:
            st.success("🎉 目前沒有同時出現法人賣超與籌碼惡化的危險名單！")
        else:
            def highlight_risk(row):
                styles = []
                for col_name in row.index:
                    if col_name in ['成交', '漲跌價', '漲跌幅']: styles.append('color: #00e676;')
                    elif col_name == '▼當日賣佔成交' and pd.to_numeric(row[col_name], errors='coerce') > 0: styles.append('color: #ff4b4b;')
                    else: styles.append('')
                return styles
            
            st.dataframe(df_rk_display.style.apply(highlight_risk, axis=1).format(precision=2), 
                         use_container_width=True, hide_index=True)
    else:
        st.warning("避險雷達載入失敗或無資料。")


@st.fragment
def render_b4_margin_dec(df_pct, df_vol):
    st.markdown(f"### 融資減少動向", unsafe_allow_html=True)
    f_col1, f_col2, _ = st.columns([1, 1, 2])
    with f_col1: show_etf_41 = st.checkbox("顯示 ETF", value=True, key="margin_show_etf")
    with f_col2: show_bond_41 = st.checkbox("顯示債券/債券ETF", value=True, key="margin_show_bond")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 10px;'>📉 融資減少比例排名</h3>", unsafe_allow_html=True)
        render_styled_margin_table(apply_ui_filter(df_pct, show_etf_41, show_bond_41))
    with c2:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 10px;'>📉 融資減少張數排名</h3>", unsafe_allow_html=True)
        render_styled_margin_table(apply_ui_filter(df_vol, show_etf_41, show_bond_41))


@st.fragment
def render_b4_sbl_dec(df_pct, df_vol):
    st.markdown(f"### 借券賣出減少動向", unsafe_allow_html=True)
    f_col1, f_col2, _ = st.columns([1, 1, 2])
    with f_col1: show_etf_42 = st.checkbox("顯示 ETF", value=True, key="stock_show_etf_42")
    with f_col2: show_bond_42 = st.checkbox("顯示債券/債券ETF", value=True, key="stock_show_bond_42")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 10px;'>📉 借券賣出減少比例排名</h3>", unsafe_allow_html=True)
        render_styled_margin_table(apply_ui_filter(df_pct, show_etf_42, show_bond_42))
    with c2:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 10px;'>📉 借券賣出減少張數排名</h3>", unsafe_allow_html=True)
        render_styled_margin_table(apply_ui_filter(df_vol, show_etf_42, show_bond_42))


@st.fragment
def render_b4_short_inc(df_pct, df_vol):
    st.markdown(f"### 融券增加動向", unsafe_allow_html=True)
    f_col1, f_col2, _ = st.columns([1, 1, 2])
    with f_col1: show_etf_43 = st.checkbox("顯示 ETF", value=True, key="stock_show_etf_43")
    with f_col2: show_bond_43 = st.checkbox("顯示債券/債券ETF", value=True, key="stock_show_bond_43")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 10px;'>📈 融券增加比例排名</h3>", unsafe_allow_html=True)
        render_styled_margin_table(apply_ui_filter(df_pct, show_etf_43, show_bond_43))
    with c2:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 10px;'>📈 融券增加張數排名</h3>", unsafe_allow_html=True)
        render_styled_margin_table(apply_ui_filter(df_vol, show_etf_43, show_bond_43))


# ==========================================
# 🖼️ 主渲染入口
# ==========================================
def show_b4_page(DATA_DIR):
    """B4 專屬頁面 UI 渲染"""
    
    # 💡 效能救星啟動：直接呼叫快取取得資料
    cached_data = get_cached_b4_data(DATA_DIR)
    
    # 將需要提供給側邊欄或權重回測的資料，同步回 session_state
    for k, v in cached_data.items():
        st.session_state[k] = v

    st.write("---")
    st.markdown("<div id='section-4'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            資券動向
        </h2>
    </div>
    """, unsafe_allow_html=True)

    

    # ==================== 4-4 軋空雷達 ====================
    render_b4_squeeze_radar(cached_data['b4_squeeze_radar'])
    st.write("---")
    
    # ==================== 4-5 套牢名單 ====================
    render_b4_risk_radar(cached_data['b4_risk_radar'])
    st.write("---")
    
    # ==================== 4-1 融資減少 ====================
    render_b4_margin_dec(cached_data['df_margin_pct'], cached_data['df_margin_vol'])
    st.write("---")
    
    # ==================== 4-2 借券賣出減少 ====================
    render_b4_sbl_dec(cached_data['df_short_pct'], cached_data['df_short_vol'])
    st.write("---")
    
    # ==================== 4-3 融券增加 ====================
    render_b4_short_inc(cached_data['df_margin_plus_pct'], cached_data['df_margin_plus_vol'])
