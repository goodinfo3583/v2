# views/b7_page.py
import streamlit as st
import pandas as pd
import os
import glob
import re

# ==========================================
# ⚙️ 區塊 7：統一讀檔與多模組生成引擎 (效能極致版)
# ==========================================
@st.cache_data(show_spinner=False, ttl=600)
def process_all_b7_data(DATA_DIR):
    """
    一次性讀取所有董監/質押檔案，並直接拆分出三張所需的 DataFrame：
    1. df_hold_trend (董監持股比增減)
    2. df_pledge_latest (董監最新質押比)
    3. df_pledge_trend (董監質押歷史趨勢)
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
        
    if not files: 
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
    df_list = []
    for f in list(files):
        df = None
        if f.endswith('.parquet'):
            try: df = pd.read_parquet(f)
            except Exception: pass
        else:
            for enc in ['utf-8-sig', 'big5', 'cp950', 'utf-8']:
                try:
                    df = pd.read_csv(f, encoding=enc, header=0, dtype=str)
                    break
                except: pass
                
        if df is not None and not df.empty:
            # 💡 清洗欄位名稱
            df.columns = [re.sub(r'[\s\n\r\t\u3000\ufeff]+', '', str(c)) for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            df_list.append(df)
            
    if not df_list: 
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
    # 將所有歷史檔案堆疊為一個巨型母表
    master_df = pd.concat(df_list, ignore_index=True)
    
    # 尋找關鍵欄位
    c_code = next((c for c in master_df.columns if "代號" in c), None)
    c_name = next((c for c in master_df.columns if "名稱" in c), None)
    c_month = next((c for c in master_df.columns if "持股資料月份" in c), None)
    c_hold = next((c for c in master_df.columns if "全體董監持股(%)" in c), None)
    c_pledge = next((c for c in master_df.columns if "全體董監質押(%)" in c), None)
    
    if not all([c_code, c_month]): 
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 清理核心索引欄位，轉為 category 節省記憶體
    master_df = master_df.dropna(subset=[c_code, c_month])
    master_df[c_code] = master_df[c_code].astype(str).str.strip().astype('category')
    master_df[c_name] = master_df[c_name].astype(str).str.strip().astype('category')
    master_df[c_month] = master_df[c_month].astype(str).str.strip()

    # ---------------------------------------------------------
    # 產出模組 1：董監持股比增減 (df_hold_trend)
    # ---------------------------------------------------------
    df_hold_trend = pd.DataFrame()
    if c_hold:
        hold_df = master_df[[c_code, c_name, c_month, c_hold]].copy()
        hold_df[c_hold] = pd.to_numeric(hold_df[c_hold].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False), errors='coerce').astype('float32')
        hold_df = hold_df.drop_duplicates(subset=[c_code, c_month], keep='first')
        
        pivot_h = hold_df.pivot(index=[c_code, c_name], columns=c_month, values=c_hold).reset_index()
        m_cols_h = sorted([c for c in pivot_h.columns if c not in [c_code, c_name]], reverse=True)[:6]
        
        if len(m_cols_h) >= 2:
            m1, m2 = m_cols_h[0], m_cols_h[1]
            pivot_h['近月增減%'] = (pivot_h[m1] - pivot_h[m2]).astype('float32')
            
            target_idx = min(5, len(m_cols_h) - 1)
            m_old = m_cols_h[target_idx]
            pivot_h['▼近半年增減%'] = (pivot_h[m1] - pivot_h[m_old]).astype('float32')
            
            def get_hold_trend(val):
                if pd.isna(val): return "無"
                if val >= 1.0: return "🔥 大增"
                if val >= 0.1: return "📈 增"
                if val > 0: return "↗️ 微增"
                if val == 0: return "🔄 持平"
                if val > -0.1: return "↘️ 微減"
                return "🚨 減/大減"
                
            pivot_h['動態'] = pivot_h['近月增減%'].apply(get_hold_trend).astype('category')
            
            rename_dict = {c_code: "股票代號", c_name: "股票名稱"}
            for m in m_cols_h: rename_dict[m] = f"{m}持股%"
            pivot_h = pivot_h.rename(columns=rename_dict)
            
            cols_order_h = ['股票代號', '股票名稱', '動態', '近月增減%', '▼近半年增減%'] + [f"{m}持股%" for m in m_cols_h]
            df_hold_trend = pivot_h[[c for c in cols_order_h if c in pivot_h.columns]].sort_values('近月增減%', ascending=False)

    # ---------------------------------------------------------
    # 產出模組 2：董監最新質押比 (df_pledge_latest)
    # ---------------------------------------------------------
    df_pledge_latest = pd.DataFrame()
    latest_m = master_df[c_month].max()
    latest_df = master_df[master_df[c_month] == latest_m].drop_duplicates(subset=[c_code], keep='first').copy()
    
    req_cols_map = {
        "排名": "排名", 
        c_code: "代號", 
        c_name: "名稱", 
        c_month: "持股 資料 月份",
        "全體董監持股(%)": "全體 董監 持股 (%)", 
        "全體董監質押(%)": "全體 董監 質押 (%)", 
        "全體董監持股(萬張)": "全體 董監 持股 (萬張)", 
        "全體董監質押(萬張)": "全體 董監 質押 (萬張)", 
        "全體董監增減張數": "全體 董監 增減 張數"
    }
    
    avail_cols = []
    rename_l_dict = {}
    
    # 💡 修正處：精確且防呆的欄位配對，杜絕 Duplicate columns
    for orig_c, new_c in req_cols_map.items():
        if not orig_c: continue
        
        matched = None
        if orig_c in latest_df.columns:
            matched = orig_c
        else:
            matched = next((c for c in latest_df.columns if orig_c in c), None)
            
        # 確保不會抓到重複的欄位
        if matched and matched not in avail_cols:
            avail_cols.append(matched)
            rename_l_dict[matched] = new_c
            
    if avail_cols:
        df_pledge_latest = latest_df[avail_cols].copy()
        df_pledge_latest = df_pledge_latest.rename(columns=rename_l_dict)
        # 最終保險：剃除意外的重複欄位
        df_pledge_latest = df_pledge_latest.loc[:, ~df_pledge_latest.columns.duplicated()]
        
        if "排名" in df_pledge_latest.columns:
            df_pledge_latest["排名"] = pd.to_numeric(df_pledge_latest["排名"], errors='coerce').astype('float32')
            df_pledge_latest = df_pledge_latest.dropna(subset=["排名"]).sort_values(by="排名", ascending=True)

    # ---------------------------------------------------------
    # 產出模組 3：董監質押歷史趨勢 (df_pledge_trend)
    # ---------------------------------------------------------
    df_pledge_trend = pd.DataFrame()
    if c_pledge:
        pledge_df = master_df[[c_code, c_name, c_month, c_pledge]].copy()
        pledge_df[c_pledge] = pd.to_numeric(pledge_df[c_pledge].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False), errors='coerce').astype('float32')
        pledge_df = pledge_df.drop_duplicates(subset=[c_code, c_month], keep='first')
        
        pivot_p = pledge_df.pivot(index=[c_code, c_name], columns=c_month, values=c_pledge).reset_index()
        m_cols_p = sorted([c for c in pivot_p.columns if c not in [c_code, c_name]], reverse=True)[:5]
        
        if len(m_cols_p) >= 2:
            m1, m2 = m_cols_p[0], m_cols_p[1]
            pivot_p['近月質押增減(%)'] = (pivot_p[m1] - pivot_p[m2]).astype('float32')
            
            def get_pledge_trend(val):
                if pd.isna(val): return "無"
                if val >= 5.0: return "🚨 暴增"
                if val >= 1.0: return "⚠️ 大增"
                if val > 0: return "↗️ 微增"
                if val == 0: return "➖ 持平"
                if val <= -5.0: return "🌟 遽減"
                if val <= -1.0: return "✅ 大減"
                return "↘️ 微減"
                
            pivot_p['動態'] = pivot_p['近月質押增減(%)'].apply(get_pledge_trend).astype('category')
            
            rename_dict = {c_code: "代號", c_name: "名稱"}
            for m in m_cols_p: rename_dict[m] = f"{m}質押%"
            pivot_p = pivot_p.rename(columns=rename_dict)
            
            cols_order_p = ['代號', '名稱', '動態', '近月質押增減(%)'] + [f"{m}質押%" for m in m_cols_p]
            df_pledge_trend = pivot_p[[c for c in cols_order_p if c in pivot_p.columns]]
            
            if len(m_cols_p) > 0:
                df_pledge_trend = df_pledge_trend.sort_values(by=f"{m_cols_p[0]}質押%", ascending=False)

    return df_hold_trend, df_pledge_latest, df_pledge_trend


# ==========================================
# 🔄 資料同步接口：供後台引擎呼叫
# ==========================================
def sync_b7_data(DATA_DIR):
    """一次性更新 b7 的三張表"""
    df_hold_trend, df_pledge_latest, df_pledge_trend = process_all_b7_data(DATA_DIR)
    st.session_state['b7_main'] = df_hold_trend
    st.session_state['b7_pledge'] = df_pledge_latest
    st.session_state['b7_pledge_history'] = df_pledge_trend
    
# 為了避免其他模組呼叫舊函數報錯，建立空殼重定向
def sync_pledge_data(DATA_DIR):
    sync_b7_data(DATA_DIR)

def sync_pledge_history_data(DATA_DIR):
    sync_b7_data(DATA_DIR)


# ==========================================
# 🚀 局部渲染魔法：將 Tabs 包裝進 Fragment
# ==========================================
@st.fragment
def render_b7_dashboard(df_pledge, df_history, df_b7):
    tab1, tab2, tab3 = st.tabs(["🔹 董監最新質押比", "🔹 董監質押歷史趨勢", "🔹 董監持股比增減"])

    # 💡 渲染時強制掛上 style.format 解決小數點跑版問題
    with tab1:
        if df_pledge.empty:
            st.warning("⚠️ 找不到董監質押比資料，請確認 data 資料夾中存在相關 CSV 或 Parquet 檔案。")
        else:
            st.dataframe(df_pledge, use_container_width=True, hide_index=True)
            
    with tab2:
        if df_history.empty:
            st.warning("⚠️ 歷史質押資料不足或檔案讀取異常，請確認檔名包含「質押比」。")
        else:
            st.dataframe(df_history.style.format(precision=2), use_container_width=True, hide_index=True)

    with tab3:
        if df_b7.empty:
            st.warning("⚠️ 在資料夾中找不到董監事持股資料，請確認檔名包含「神秘金字塔」與「董監事持股」。")
        else:
            st.dataframe(df_b7.style.format(precision=2), use_container_width=True, hide_index=True)


# ==========================================
# 🖼️ 前台畫面渲染 (三頁籤切換)
# ==========================================
def show_b7_page(DATA_DIR, STOCK_DICT):
    if 'b7_main' not in st.session_state or 'b7_pledge' not in st.session_state or 'b7_pledge_history' not in st.session_state:
        sync_b7_data(DATA_DIR)
            
    st.write("---")
    st.markdown("<div id='section-7'></div>", unsafe_allow_html=True)
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
