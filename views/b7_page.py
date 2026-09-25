# views/b7_page.py
import streamlit as st
import pandas as pd
import os
import glob
import re

# ==========================================
# ⚙️ 區塊 7：董監持股運算引擎 (高效統一版 - 從質押檔提取)
# ==========================================
@st.cache_data(show_spinner=False, ttl=600)
def process_directors_data(DATA_DIR):
    """統一讀取 Goodinfo 質押比檔案，並萃取「持股比例」進行多月份動態比較"""
    search_patterns = [
        os.path.join(DATA_DIR, "*質押*.parquet"),
        os.path.join(DATA_DIR, "*董監*.parquet"),
        os.path.join(DATA_DIR, "*質押*.csv"),
        os.path.join(DATA_DIR, "*董監*.csv")
    ]
    files = set()
    for pattern in search_patterns:
        files.update(glob.glob(pattern))
        
    if not files: return pd.DataFrame()
    
    df_list = []
    for f in list(files):
        df = None
        if f.endswith('.parquet'):
            try:
                df = pd.read_parquet(f)
            except Exception: pass
        else:
            for enc in ['utf-8-sig', 'big5', 'cp950', 'utf-8']:
                try:
                    df = pd.read_csv(f, encoding=enc, header=0, dtype=str)
                    break
                except: pass
            
        if df is not None and not df.empty:
            df.columns = [re.sub(r'[\s\n\r\t\u3000\ufeff]+', '', str(c)) for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            
            # 鎖定 Goodinfo 的欄位
            c_code = next((c for c in df.columns if "代號" in c), None)
            c_name = next((c for c in df.columns if "名稱" in c), None)
            c_month = next((c for c in df.columns if "持股資料月份" in c), None)
            c_hold = next((c for c in df.columns if "全體董監持股(%)" in c), None)
            
            if all([c_code, c_name, c_month, c_hold]):
                df = df.rename(columns={
                    c_code: "股票代號",
                    c_name: "股票名稱",
                    c_month: "持股資料月份",
                    c_hold: "全體董監持股(%)"
                })
                clean_df = df[["股票代號", "股票名稱", "持股資料月份", "全體董監持股(%)"]].copy()
                df_list.append(clean_df)
                
    if not df_list: return pd.DataFrame()
    
    # 堆疊所有歷史檔案
    merged_df = pd.concat(df_list, ignore_index=True)
    merged_df = merged_df.dropna(subset=["股票代號", "持股資料月份"])
    merged_df["股票代號"] = merged_df["股票代號"].astype(str).str.strip()
    merged_df["股票名稱"] = merged_df["股票名稱"].astype(str).str.strip()
    merged_df["持股資料月份"] = merged_df["持股資料月份"].astype(str).str.strip()
    merged_df["全體董監持股(%)"] = pd.to_numeric(merged_df["全體董監持股(%)"].astype(str).str.replace('%', '').str.replace(',', ''), errors='coerce')
    
    # 去重覆後，進行樞紐分析 (將月份轉成直欄)
    merged_df = merged_df.drop_duplicates(subset=["股票代號", "持股資料月份"], keep='first')
    pivot_df = merged_df.pivot(index=["股票代號", "股票名稱"], columns="持股資料月份", values="全體董監持股(%)").reset_index()
    
    # 抓出所有的月份，由新到舊排序
    month_cols = sorted([c for c in pivot_df.columns if c not in ["股票代號", "股票名稱"]], reverse=True)
    
    if not month_cols: return pd.DataFrame()
    
    # 取最新的 6 個月即可 (保持版面乾淨)
    month_cols = month_cols[:6]
    
    # 計算近月與近半年的增減
    if len(month_cols) >= 2:
        m1, m2 = month_cols[0], month_cols[1]
        pivot_df['近月增減%'] = (pivot_df[m1] - pivot_df[m2]).round(2)
        
        # 🌟 近半年波段持股增減 (找前5個月的資料對比，若不足半年則取最舊的)
        target_idx = min(5, len(month_cols) - 1)
        m_old = month_cols[target_idx]
        pivot_df['▼近半年增減%'] = (pivot_df[m1] - pivot_df[m_old]).round(2)
        
        def get_trend(val):
            if pd.isna(val): return "無"
            if val >= 1.0: return "🔥 大增"
            if val >= 0.1: return "📈 增"
            if val > 0: return "↗️ 微增"
            if val == 0: return "🔄 持平"
            if val > -0.1: return "↘️ 微減"
            return "🚨 減/大減"
            
        pivot_df['動態'] = pivot_df['近月增減%'].apply(get_trend)
        
    # 將欄位名稱加上 "持股%" 供前端與策略實驗室辨識
    rename_dict = {}
    for m in month_cols:
        rename_dict[m] = f"{m}持股%"
    pivot_df = pivot_df.rename(columns=rename_dict)
    
    # 安排最終顯示的欄位順序
    cols_order = ['股票代號', '股票名稱']
    if '動態' in pivot_df.columns: cols_order.extend(['動態', '近月增減%'])
    if '▼近半年增減%' in pivot_df.columns: cols_order.append('▼近半年增減%')
    for m in month_cols:
        cols_order.append(f"{m}持股%")
        
    pivot_df = pivot_df[[c for c in cols_order if c in pivot_df.columns]]
    
    # 依照近月增減量排序，凸顯近期內部人加碼的飆股
    if '近月增減%' in pivot_df.columns:
        pivot_df = pivot_df.sort_values('近月增減%', ascending=False)
        
    return pivot_df


# ==========================================
# ⚙️ 區塊 7：董監質押比最新月份 (第一張表)
# ==========================================
@st.cache_data(show_spinner=False, ttl=600)
def process_pledge_data(DATA_DIR):
    """讀取並自動堆疊所有檔案，動態過濾並僅保留最新月份資料"""
    search_patterns = [
        os.path.join(DATA_DIR, "*質押*.parquet"),
        os.path.join(DATA_DIR, "*董監*.parquet"),
        os.path.join(DATA_DIR, "*質押*.csv"),
        os.path.join(DATA_DIR, "*董監*.csv")
    ]
    files = set()
    for pattern in search_patterns:
        files.update(glob.glob(pattern))
        
    if not files: return pd.DataFrame()
    
    df_list = []
    for f in list(files):
        df = None
        if f.endswith('.parquet'):
            try:
                df = pd.read_parquet(f)
            except Exception: pass
        else:
            for enc in ['utf-8-sig', 'big5', 'cp950', 'utf-8']:
                try:
                    df = pd.read_csv(f, encoding=enc, header=0, dtype=str)
                    break
                except: pass
            
        if df is not None and not df.empty:
            df.columns = [re.sub(r'[\s\n\r\t\u3000\ufeff]+', '', str(c)) for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            df_list.append(df)
            
    if not df_list: return pd.DataFrame()
    
    merged_df = pd.concat(df_list, ignore_index=True)
    
    c_code = next((c for c in merged_df.columns if "代號" in c), None)
    c_month = next((c for c in merged_df.columns if "持股資料月份" in c), None)
    
    if c_code and c_month:
        merged_df = merged_df.dropna(subset=[c_code, c_month])
        merged_df[c_code] = merged_df[c_code].astype(str).str.strip()
        merged_df[c_month] = merged_df[c_month].astype(str).str.strip()
        
        latest_month = merged_df[c_month].max()
        merged_df = merged_df[merged_df[c_month] == latest_month]
        merged_df = merged_df.drop_duplicates(subset=[c_code], keep='first')
    
    requested_cols = [
        "排名", "代號", "名稱", "持股資料月份",
        "全體董監持股(%)", "全體董監質押(%)", 
        "全體董監持股(萬張)", "全體董監質押(萬張)", 
        "全體董監增減張數"
    ]
    
    actual_cols = []
    for req_c in requested_cols:
        matched_col = next((c for c in merged_df.columns if req_c in c), None)
        if matched_col:
            actual_cols.append(matched_col)
            
    if actual_cols:
        merged_df = merged_df[actual_cols]
        rename_dict = {
            "持股資料月份": "持股 資料 月份",
            "全體董監持股(%)": "全體 董監 持股 (%)", 
            "全體董監質押(%)": "全體 董監 質押 (%)", 
            "全體董監持股(萬張)": "全體 董監 持股 (萬張)", 
            "全體董監質押(萬張)": "全體 董監 質押 (萬張)", 
            "全體董監增減張數": "全體 董監 增減 張數"
        }
        merged_df = merged_df.rename(columns=rename_dict)
    
    if "排名" in merged_df.columns:
        merged_df["排名"] = pd.to_numeric(merged_df["排名"], errors='coerce')
        merged_df = merged_df.dropna(subset=["排名"])
        merged_df = merged_df.sort_values(by="排名", ascending=True)

    return merged_df


# ==========================================
# ⚙️ 區塊 7：董監質押歷史趨勢引擎 (第二張表 - 終極動態防呆 + 圖示版)
# ==========================================
@st.cache_data(show_spinner=False, ttl=600)
def process_pledge_history_data(DATA_DIR):
    """
    不管未來累積了多少個月的檔案，系統自動降冪排好後，
    永遠只擷取「最新的 5 個月份」，並加入視覺化的質押增減「動態」判斷。
    """
    search_patterns = [
        os.path.join(DATA_DIR, "*質押*.parquet"),
        os.path.join(DATA_DIR, "*董監*.parquet"),
        os.path.join(DATA_DIR, "*質押*.csv"),
        os.path.join(DATA_DIR, "*董監*.csv")
    ]
    files = set()
    for pattern in search_patterns:
        files.update(glob.glob(pattern))
        
    if not files: return pd.DataFrame()
    
    df_list = []
    for f in list(files):
        df = None
        if f.endswith('.parquet'):
            try:
                df = pd.read_parquet(f)
            except Exception: pass
        else:
            for enc in ['utf-8-sig', 'big5', 'cp950', 'utf-8']:
                try:
                    df = pd.read_csv(f, encoding=enc, header=0, dtype=str)
                    break
                except: pass
            
        if df is not None and not df.empty:
            df.columns = [re.sub(r'[\s\n\r\t\u3000\ufeff]+', '', str(c)) for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]            
            
            c_code = next((c for c in df.columns if "代號" in c), None)
            c_name = next((c for c in df.columns if "名稱" in c), None)
            c_month = next((c for c in df.columns if "持股資料月份" in c), None)
            c_pledge = next((c for c in df.columns if "全體董監質押(%)" in c), None)
            
            if all([c_code, c_name, c_month, c_pledge]):
                df = df.rename(columns={
                    c_code: "std_代號",
                    c_name: "std_名稱",
                    c_month: "std_持股資料月份",
                    c_pledge: "std_質押比"
                })
                clean_df = df[["std_代號", "std_名稱", "std_持股資料月份", "std_質押比"]].copy()
                df_list.append(clean_df)
            
    if not df_list: return pd.DataFrame()
    
    merged_df = pd.concat(df_list, ignore_index=True)
    
    merged_df = merged_df.dropna(subset=["std_代號", "std_持股資料月份"])
    merged_df["std_代號"] = merged_df["std_代號"].astype(str).str.strip()
    merged_df["std_名稱"] = merged_df["std_名稱"].astype(str).str.strip()
    merged_df["std_持股資料月份"] = merged_df["std_持股資料月份"].astype(str).str.strip()
    
    merged_df["std_質押比"] = pd.to_numeric(merged_df["std_質押比"].astype(str).str.replace('%', '').str.replace(',', ''), errors='coerce')
    
    merged_df = merged_df.drop_duplicates(subset=["std_代號", "std_持股資料月份"], keep='first')
    
    pivot_df = merged_df.pivot(index=["std_代號", "std_名稱"], columns="std_持股資料月份", values="std_質押比").reset_index()
    
    month_cols = sorted([c for c in pivot_df.columns if c not in ["std_代號", "std_名稱"]], reverse=True)
    
    if not month_cols:
        return pd.DataFrame()
        
    # 🎯 取最新的 5 個月
    month_cols = month_cols[:5]
    
    # 動態計算與視覺化動態判斷
    if len(month_cols) >= 2:
        m1, m2 = month_cols[0], month_cols[1]
        pivot_df['近月質押增減(%)'] = (pivot_df[m1] - pivot_df[m2]).round(2)
        
        def get_pledge_trend(val):
            if pd.isna(val): return "無"
            if val >= 5.0: return "🚨 暴增"
            if val >= 1.0: return "⚠️ 大增"
            if val > 0: return "↗️ 微增"
            if val == 0: return "➖ 持平"
            if val <= -5.0: return "🌟 遽減"
            if val <= -1.0: return "✅ 大減"
            return "↘️ 微減"
            
        pivot_df['動態'] = pivot_df['近月質押增減(%)'].apply(get_pledge_trend)
        
    rename_dict = {"std_代號": "代號", "std_名稱": "名稱"}
    for m in month_cols:
        rename_dict[m] = f"{m}質押%"
    pivot_df = pivot_df.rename(columns=rename_dict)
    
    final_cols = ["代號", "名稱"]
    if '動態' in pivot_df.columns:
        final_cols.append('動態')
    if '近月質押增減(%)' in pivot_df.columns:
        final_cols.append('近月質押增減(%)')
        
    dynamic_pledge_cols = [f"{m}質押%" for m in month_cols]
    final_cols.extend(dynamic_pledge_cols)
    
    pivot_df = pivot_df[final_cols]
    
    if dynamic_pledge_cols:
        latest_col = dynamic_pledge_cols[0] 
        if latest_col in pivot_df.columns:
            pivot_df = pivot_df.sort_values(by=latest_col, ascending=False)

    return pivot_df


# ==========================================
# 🔄 資料同步接口：供後台引擎呼叫
# ==========================================
def sync_b7_data(DATA_DIR):
    st.session_state['b7_main'] = process_directors_data(DATA_DIR)
    
def sync_pledge_data(DATA_DIR):
    st.session_state['b7_pledge'] = process_pledge_data(DATA_DIR)

def sync_pledge_history_data(DATA_DIR):
    st.session_state['b7_pledge_history'] = process_pledge_history_data(DATA_DIR)


# ==========================================
# 🚀 局部渲染魔法：將 Tabs 包裝進 Fragment
# ==========================================
@st.fragment
def render_b7_dashboard(df_pledge, df_history, df_b7):
    tab1, tab2, tab3 = st.tabs(["🔹 董監最新質押比", "🔹 董監質押歷史趨勢", "🔹 董監持股比增減"])

    with tab1:
        if df_pledge.empty:
            st.warning("⚠️ 找不到董監質押比資料，請確認 data 資料夾中存在相關 CSV 或 Parquet 檔案。")
        else:
            st.dataframe(df_pledge, use_container_width=True, hide_index=True)
            
    with tab2:
        if df_history.empty:
            st.warning("⚠️ 歷史質押資料不足或檔案讀取異常，請確認檔名包含「質押比」。")
        else:
            st.dataframe(df_history, use_container_width=True, hide_index=True)

    with tab3:
        if df_b7.empty:
            st.warning("⚠️ 在資料夾中找不到董監事持股資料，請確認檔名包含「神秘金字塔」與「董監事持股」。")
        else:
            st.dataframe(df_b7, use_container_width=True, hide_index=True)


# ==========================================
# 🖼️ 前台畫面渲染 (三頁籤切換)
# ==========================================
def show_b7_page(DATA_DIR, STOCK_DICT):
    if 'b7_main' not in st.session_state:
        sync_b7_data(DATA_DIR)
            
    if 'b7_pledge' not in st.session_state:
        sync_pledge_data(DATA_DIR)
            
    if 'b7_pledge_history' not in st.session_state:
        sync_pledge_history_data(DATA_DIR)
            
    st.write("---")
    st.markdown("", unsafe_allow_html=True)
    st.markdown("""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            董監動向
        </h2>
    </div>
    """, unsafe_allow_html=True)

    df_pledge = st.session_state.get('b7_pledge', pd.DataFrame())
    df_history = st.session_state.get('b7_pledge_history', pd.DataFrame())
    df_b7 = st.session_state.get('b7_main', pd.DataFrame())

    render_b7_dashboard(df_pledge, df_history, df_b7)
