# views/b3_page.py
import streamlit as st
import pandas as pd
import glob
import os
import re

# 引入共用防呆讀取工具
from utils.data_utils import robust_read_csv 

# ==========================================
# 🌟 區塊 3 專屬工具函數區
# ==========================================
def extract_date_from_name(filename):
    match = re.search(r'(\d{8})', os.path.basename(str(filename)))
    return match.group(1) if match else "00000000"

def read_live_ln_report(DATA_DIR, file_keyword, strict_type, exact_field_name, prefix_keyword, col_label):
    """核心函數：讀取法人連續買超報告 (已大幅優化記憶體)"""
    if strict_type == "日":
        search_pattern1 = os.path.join(DATA_DIR, f"*{file_keyword}*(日)*.csv")
        search_pattern2 = os.path.join(DATA_DIR, f"*{file_keyword}*日*.csv")
        target_files = glob.glob(search_pattern1) + glob.glob(search_pattern2)
        target_files = [f for f in target_files if "週" not in os.path.basename(f) and "周" not in os.path.basename(f) and "wk" not in os.path.basename(f).lower()]
    else:
        search_pattern1 = os.path.join(DATA_DIR, f"*{file_keyword}*(週)*.csv")
        search_pattern2 = os.path.join(DATA_DIR, f"*{file_keyword}*週*.csv")
        target_files = glob.glob(search_pattern1) + glob.glob(search_pattern2)
        
    target_files = list(set(target_files))
    if not target_files: return pd.DataFrame(), None
        
    latest_file = sorted(target_files, key=extract_date_from_name, reverse=True)[0]
    date_str = extract_date_from_name(latest_file) 
    
    try:
        df = robust_read_csv(latest_file)
        
        # 💡 優化 1：用 List Comprehension 取代 Pandas 原生字串連續轉換，大幅節省記憶體
        df.columns = [str(c).replace('\n', '').replace(' ', '').replace('\ufeff', '').strip() for c in df.columns]
        
        col_id = next((c for c in df.columns if '代號' in c), df.columns[0])
        col_name = next((c for c in df.columns if '名稱' in c), df.columns[1])
        
        target_key = exact_field_name.replace(' ', '')
        if target_key in df.columns:
            target_data_col = target_key
        else:
            matched_cols = [c for c in df.columns if '買賣' in c and strict_type in c]
            target_data_col = matched_cols[0] if matched_cols else df.columns[2]
            
        # 💡 優化 2：轉換為數字，並及早過濾 (Early Filtering)！把幾千筆無用資料瞬間砍除。
        df[target_data_col] = pd.to_numeric(df[target_data_col], errors='coerce').fillna(0)
        df_sorted = df[df[target_data_col] > 0].copy() # 只留大於0的
        
        if df_sorted.empty: return pd.DataFrame(), date_str
            
        df_sorted = df_sorted.sort_values(by=target_data_col, ascending=False)
        
        output_df = pd.DataFrame()
        # 💡 優化 3：記憶體降級！將字串轉為 category 型態，體積縮小 80%
        output_df["股票代號"] = df_sorted[col_id].astype(str).str.strip().astype('category')
        output_df["股票名稱"] = df_sorted[col_name].astype(str).str.strip().astype('category')
        
        def get_status_tag(val):
            if strict_type == "日":
                if val >= 10: return "🔥 波段認養"
                elif val >= 5: return "⚡ 買盤點火"
                else: return "🆕 試單觀察"
            else:
                if val >= 10: return "👑 長線主控"
                elif val >= 5: return "🚀 趨勢加溫"
                else: return "🌱 週線發動"
                
        output_df["狀態動態"] = df_sorted[target_data_col].apply(get_status_tag).astype('category')
        output_df[col_label] = df_sorted[target_data_col].astype('int16')
        
        real_pct_trade = [c for c in df_sorted.columns if prefix_keyword in c and "佔成交" in c]
        real_pct_issue = [c for c in df_sorted.columns if prefix_keyword in c and "佔發行量" in c]
        
        # 💡 優化 4：強制加上 .round(2) 確保不會出現很醜的浮點數精度溢出
        if real_pct_trade: output_df["佔成交(%)"] = pd.to_numeric(df_sorted[real_pct_trade[0]], errors='coerce').fillna(0.0).round(2)
        else: output_df["佔成交(%)"] = 0.0
            
        if real_pct_issue: output_df["佔發行量(%)"] = pd.to_numeric(df_sorted[real_pct_issue[0]], errors='coerce').fillna(0.0).round(2)
        else: output_df["佔發行量(%)"] = 0.0
            
        return output_df, date_str
    except Exception as e:
        return pd.DataFrame(), f"解讀失敗: {str(e)}"


def get_report_with_fallback(DATA_DIR, keywords, strict_type, exact_field_name, prefix_keyword, col_label):
    """遞迴嘗試不同的檔案關鍵字，減少重複程式碼"""
    for kw in keywords:
        df, date = read_live_ln_report(DATA_DIR, kw, strict_type, exact_field_name, prefix_keyword, col_label)
        if not df.empty or date is not None:
            return df, date
    return pd.DataFrame(), None


# ==========================================
# 💡 效能救星 1：將複雜的讀取與合併動作快取起來
# ==========================================
@st.cache_data(show_spinner=False, ttl=300)
def get_cached_b3_data(DATA_DIR):
    """回傳 (b3_data_dict, df_blk3_main) 兩個變數"""
    
    fo_keywords = ["外資連續買超", "外資連買"]
    it_keywords = ["投信連續買超", "投信連買", "外資連續買超", "外資連買"] # 後兩者為原代碼的備案邏輯

    # 💡 優化 5：合併冗長的巢狀 IF 判斷，改用 List Fallback
    live_fo_day, date_fo_day = get_report_with_fallback(DATA_DIR, fo_keywords, "日", "外資連續買賣日數", "外資", "最新連買天數")
    live_it_day, date_it_day = get_report_with_fallback(DATA_DIR, it_keywords, "日", "投信連續買賣日數", "投信", "最新連買天數")
    live_fo_wk, date_fo_wk = get_report_with_fallback(DATA_DIR, fo_keywords, "週", "外資連續買賣週數", "外資", "最新連買週數")
    live_it_wk, date_it_wk = get_report_with_fallback(DATA_DIR, it_keywords, "週", "投信連續買賣週數", "投信", "最新連買週數")

    b3_data_dict = {
        'fo_day': (live_fo_day, date_fo_day),
        'it_day': (live_it_day, date_it_day),
        'fo_wk': (live_fo_wk, date_fo_wk),
        'it_wk': (live_it_wk, date_it_wk)
    }

    # 組合給 Sidebar 和 Weight Backtest 使用的全市場母表
    b3_combined_list = []
    
    def append_to_combined(df, type_name, col_name):
        if not df.empty:
            df_tmp = df[['股票代號', '股票名稱', '狀態動態', col_name]].copy()
            df_tmp['連買類型'] = type_name
            df_tmp = df_tmp.rename(columns={col_name: '連買週期數'})
            b3_combined_list.append(df_tmp)

    append_to_combined(live_fo_day, '🌐 外資日連買', '最新連買天數')
    append_to_combined(live_it_day, '🏦 投信日連買', '最新連買天數')
    append_to_combined(live_fo_wk, '🌐 外資週連買', '最新連買週數')
    append_to_combined(live_it_wk, '🏦 投信週連買', '最新連買週數')

    if b3_combined_list:
        df_b3 = pd.concat(b3_combined_list, ignore_index=True)
        df_b3['連買類型'] = df_b3['連買類型'].astype('category') # 記憶體降級
        df_blk3_main = df_b3[['連買類型', '股票代號', '股票名稱', '狀態動態', '連買週期數']]
    else:
        df_blk3_main = pd.DataFrame(columns=['連買類型', '股票代號', '股票名稱', '狀態動態', '連買週期數'])

    return b3_data_dict, df_blk3_main

# ==========================================
# ⚙️ 後台資料引擎 (橋接函式)：讓其他頁面抓得到資料
# ==========================================
def sync_b3_data(DATA_DIR):
    """將瞬間算好的快取資料，寫入 session_state 供側邊欄與過濾器讀取"""
    b3_data_dict, df_blk3_main = get_cached_b3_data(DATA_DIR)
    st.session_state['b3_data'] = b3_data_dict
    # 因為 B3 過濾完後的資料量極小 (通常不到 100 筆)，放入 session_state 供側邊欄使用非常安全
    st.session_state['df_blk3_main'] = df_blk3_main


# ==========================================
# 🚀 局部渲染魔法：UI 與表格的結界
# ==========================================
@st.fragment
def render_b3_dashboard(data):
    """負責渲染 4 個表格與 Checkbox，隔離點擊造成的閃爍"""
    c_f1, c_f2 = st.columns(2)
    show_etf_b3 = c_f1.checkbox("顯示 ETF", value=True, key="b3_etf_filter")
    show_bond_b3 = c_f2.checkbox("顯示 債券/債券ETF", value=True, key="b3_bond_filter")

    def apply_b3_filter(df):
        if df is None or df.empty:
            return df
        # 防呆：確保欄位被轉回 string 再運算長度，防止 category 報錯
        code_str = df['股票代號'].astype(str)
        mask = (code_str.str.len() == 4)
        if show_etf_b3: mask |= ((code_str.str.len() >= 5) & (~code_str.str.endswith('B')))
        if show_bond_b3: mask |= code_str.str.endswith('B')
        res_df = df[mask].copy()
        res_df.index = range(1, len(res_df) + 1)
        return res_df

    live_fo_day, date_fo_day = data['fo_day']
    live_it_day, date_it_day = data['it_day']
    live_fo_wk, date_fo_wk = data['fo_wk']
    live_it_wk, date_it_wk = data['it_wk']

    # 套用畫面顯示篩選器
    live_fo_day_disp = apply_b3_filter(live_fo_day)
    live_it_day_disp = apply_b3_filter(live_it_day)
    live_fo_wk_disp = apply_b3_filter(live_fo_wk)
    live_it_wk_disp = apply_b3_filter(live_it_wk)

    # 渲染最新單日區塊
    h_day1, h_day2 = st.columns(2)
    with h_day1:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 0;'>外資最新 日連買</h3>", unsafe_allow_html=True)
    with h_day2:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 0;'>投信最新 日連買</h3>", unsafe_allow_html=True)

    st.markdown("<div style='color: white; margin-top: 5px; margin-bottom: 18px; font-size: 16px;'>💡 <b>日動態說明：</b> 🔥 波段認養 (連買10天以上)  ⚡ 買盤點火 (連買5~9天)  🆕 試單觀察 (連買1~4天)</div>", unsafe_allow_html=True)

    c_day1, c_day2 = st.columns(2)
    with c_day1:
        if not live_fo_day_disp.empty: st.dataframe(live_fo_day_disp, use_container_width=True)
        else: st.write("無資料")
        st.markdown(f"<div style='color: #00D2FF; font-size: 16px; margin-top: 1px;'>基準日: {date_fo_day if date_fo_day else '無資料'}</div>", unsafe_allow_html=True)

    with c_day2:
        if not live_it_day_disp.empty: st.dataframe(live_it_day_disp, use_container_width=True)
        else: st.write("無資料")
        st.markdown(f"<div style='color: #00D2FF; font-size: 16px; margin-top: 1px;'>基準日: {date_it_day if date_it_day else '無資料'}</div>", unsafe_allow_html=True)

    st.write("---") 

    # 渲染最新單週區塊
    h_wk1, h_wk2 = st.columns(2)
    with h_wk1:
        st.markdown("<h3 style='margin-top: 0; margin-bottom: 0;'>外資最新 週連買</h3>", unsafe_allow_html=True)
    with h_wk2:
        st.markdown("<h3 style='margin-bottom: 0;'>投信最新 週連買</h3>", unsafe_allow_html=True)

    st.markdown("<div style='color: white; margin-top: 5px; margin-bottom: 18px; font-size: 16px;'>💡 <b>週動態說明：</b> 👑 長線主控 (連買10週以上)  🚀 趨勢加溫 (連買5~9週)  🌱 週線發動 (連買1~4週)</div>", unsafe_allow_html=True)

    c_wk1, c_wk2 = st.columns(2)
    with c_wk1:
        if not live_fo_wk_disp.empty: st.dataframe(live_fo_wk_disp, use_container_width=True)
        else: st.write("無資料")
        st.markdown(f"<div style='color: #00D2FF; font-size: 16px; margin-top: 1px;'>基準日: {date_fo_wk if date_fo_wk else '無資料'}</div>", unsafe_allow_html=True)

    with c_wk2:
        if not live_it_wk_disp.empty: st.dataframe(live_it_wk_disp, use_container_width=True)
        else: st.write("無資料")
        st.markdown(f"<div style='color: #00D2FF; font-size: 16px; margin-top: 1px;'>基準日: {date_it_wk if date_it_wk else '無資料'}</div>", unsafe_allow_html=True)


# ==========================================
# 🖼️ 前台畫面渲染主程式
# ==========================================
def show_b3_page(DATA_DIR):
    """B3 專屬頁面 UI 渲染"""
    
    # 💡 效能救星啟動：直接呼叫快取取得資料
    b3_data_dict, df_blk3_main = get_cached_b3_data(DATA_DIR)
    
    # 確保側邊欄與其他頁面抓得到最新的無過濾資料
    st.session_state['b3_data'] = b3_data_dict
    st.session_state['df_blk3_main'] = df_blk3_main

    st.write("---")
    st.markdown("<div id='section-3'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            法人連買
        </h2>
    </div>
    """, unsafe_allow_html=True)

    # 💡 呼叫 Fragment 隔離渲染，打勾時不再閃爍！
    render_b3_dashboard(b3_data_dict)
