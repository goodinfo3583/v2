# views/b0_page.py
import streamlit as st
import pandas as pd
import numpy as np
import os
import glob
import re

# ==========================================
# 💡 效能救星 1：極輕量化讀取與智能欄位映射
# ==========================================
@st.cache_data(show_spinner=False, ttl=300)
def get_cached_b0_data(DATA_DIR):
    # 🔍 抓取後台運算好的 master_features 檔案
    files = glob.glob(os.path.join(DATA_DIR, "*master_features*.parquet"))
    if not files:
        files = glob.glob(os.path.join(DATA_DIR, "*合併*.parquet")) + glob.glob(os.path.join(DATA_DIR, "*成交價*.parquet"))
        
    if not files: return None, None
        
    # 依照修改時間排序 (最新在最前面)
    files = sorted(files, key=os.path.getmtime, reverse=True)
    latest_file = files[0]
    
    try:
        # 1. 完整讀取最新一天的資料作為今日看板
        df_today = pd.read_parquet(latest_file)
        
        # 🚀 關鍵修復：將後台的英文與帶單位欄位，自動映射為前台 UI 所需的名稱
        rename_map = {
            'trade_date': '標準日期',
            'stock_code': '統一代號',
            'stock_name': '股票名稱',
            '今日成交額(萬)': '成交額(萬)',
            '成交金額日變化率(%)': '成交金額日變化率'
        }
        for p in [5, 10, 20, 30, 45, 60, 120]:
            rename_map[f'{p}日均額(萬)'] = f'{p}日均額'
            rename_map[f'較{p}日均額增加(萬)'] = f'較{p}日均額增加'
            rename_map[f'{p}日均量(張)'] = f'{p}日均量'
            
        df_today = df_today.rename(columns=rename_map)

        # 清理欄位名稱格式與代號
        df_today.columns = [re.sub(r'\s+', '', str(c)) for c in df_today.columns]
        df_today = df_today.loc[:, ~df_today.columns.duplicated()]

        if '統一代號' in df_today.columns: 
            df_today['統一代號'] = df_today['統一代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
        if '標準日期' in df_today.columns:
            df_today['標準日期'] = df_today['標準日期'].astype(str).str.strip()
            df_today = df_today[~df_today['標準日期'].str.lower().isin(['nan', 'nat', 'none', ''])]
            
        unique_dates = sorted([str(d) for d in df_today['標準日期'].unique()], reverse=True) if '標準日期' in df_today.columns else []
        if unique_dates:
            df_today['股價日期'] = unique_dates[0]

        # 2. 💡 記憶體魔法：只抽取歷史檔案中的 3 個欄位來還原歷史盤面
        hist_dfs = []
        for f in files[:20]: # 追溯最近 20 個交易日
            try:
                schema = pd.read_parquet(f, columns=[]).columns
                use_cols = []
                if 'stock_code' in schema: use_cols.append('stock_code')
                elif '統一代號' in schema: use_cols.append('統一代號')
                
                if 'trade_date' in schema: use_cols.append('trade_date')
                elif '標準日期' in schema: use_cols.append('標準日期')
                
                if '漲跌幅' in schema: use_cols.append('漲跌幅')
                
                # 只有當含有代號、日期與漲跌幅時才讀取
                if len(use_cols) >= 2:
                    temp_df = pd.read_parquet(f, columns=use_cols)
                    temp_df = temp_df.rename(columns={'stock_code': '統一代號', 'trade_date': '標準日期'})
                    hist_dfs.append(temp_df)
            except Exception:
                continue
                
        if hist_dfs:
            df_history = pd.concat(hist_dfs, ignore_index=True)
            df_history['統一代號'] = df_history['統一代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df_history['標準日期'] = df_history['標準日期'].astype(str).str.strip()
        else:
            df_history = df_today[['統一代號', '標準日期', '漲跌幅']] if '漲跌幅' in df_today.columns else pd.DataFrame()

        return df_today, df_history
        
    except Exception as e:
        return None, None

def sync_b0_data(DATA_DIR):
    if (res := get_cached_b0_data(DATA_DIR)) is not None and res[0] is not None: 
        st.session_state['b0_price'] = res[0]

# ==========================================
# 🚀 效能救星 2：Fragment 化互動面板
# ==========================================
@st.fragment
def render_b0_interactive_dashboard(df_b0, df_history):
    top_container = st.container()

    has_status = 'B0_量價狀態' in df_b0.columns
    has_special = 'B0_特殊型態' in df_b0.columns

    with st.expander("🛠️ 全域條件篩選 (點擊展開/收合)", expanded=True):
        c1, c2, c3, c4 = st.columns([1.5, 1, 1.5, 1])
        search_kw = c1.text_input("🔍 搜尋代號/名稱", placeholder="例如: 2330 或 台積電")
        vol_filter = c2.number_input("成交量 > (張)", min_value=0, value=0, step=1000)
        
        status_opts = sorted([str(x) for x in df_b0['B0_量價狀態'].unique() if pd.notna(x)]) if has_status else []
        sel_status = c3.multiselect("🎯 狀態過濾", status_opts, placeholder="預設全選" if has_status else "無狀態欄位")
        
        sel_per = c4.selectbox("⚖️ 估值(PER)過濾", ["全部顯示", "PER < 15 (低估值)", "PER < 30 (合理)", "僅顯示獲利公司 (PER>0)"])
        st.markdown("---")
        
        special_opts = [opt for opt in df_b0['B0_特殊型態'].unique() if opt != "-" and pd.notna(opt)] if has_special else []
        sel_special = st.multiselect("🕵️ 特殊洗盤與窒息量篩選 (高勝率買點)", special_opts, placeholder="未選擇則顯示全部" if has_special else "無特殊型態欄位")

    # 執行過濾
    f_df = df_b0.copy()
    if search_kw: f_df = f_df[f_df['統一代號'].str.contains(search_kw) | f_df['股票名稱'].str.contains(search_kw)]
    if vol_filter > 0 and '成交張數_num' in f_df.columns: f_df = f_df[f_df['成交張數_num'] >= vol_filter]
    elif vol_filter > 0 and '成交張數' in f_df.columns: f_df = f_df[f_df['成交張數'] >= vol_filter]
        
    if sel_status and has_status: f_df = f_df[f_df['B0_量價狀態'].isin(sel_status)]
    
    if 'PER' in f_df.columns:
        if "PER < 15" in sel_per: f_df = f_df[(f_df['PER'] > 0) & (f_df['PER'] < 15)]
        elif "PER < 30" in sel_per: f_df = f_df[(f_df['PER'] > 0) & (f_df['PER'] < 30)]
        elif "PER>0" in sel_per: f_df = f_df[f_df['PER'] > 0]
            
    if sel_special and has_special: f_df = f_df[f_df['B0_特殊型態'].isin(sel_special)]

    # 🌟 回填頂部盤面結構
    with top_container:
        st.markdown("### 📊 盤面結構 (基於當前篩選條件)")
        
        h_df = df_history[df_history['統一代號'].isin(f_df['統一代號'].unique())].copy()
        if not h_df.empty and '漲跌幅' in h_df.columns:
            bh = h_df.assign(
                up=h_df['漲跌幅'] > 0, dn=h_df['漲跌幅'] < 0, fl=h_df['漲跌幅'] == 0,
                lu=h_df['漲跌幅'] >= 9.5, ld=h_df['漲跌幅'] <= -9.5
            ).groupby('標準日期')[['up', 'dn', 'fl', 'lu', 'ld']].sum().reset_index().sort_values('標準日期', ascending=False)
            
            t, y = (bh.iloc[0], bh.iloc[1]) if len(bh) > 1 else (bh.iloc[0] if len(bh) > 0 else pd.Series(0, index=['up','dn','fl','lu','ld']), pd.Series([None]*5, index=['up','dn','fl','lu','ld']))
            if len(bh) == 0: t = pd.Series(0, index=['up','dn','fl','lu','ld'])

            m = st.columns(5)
            m[0].metric("漲家數 📈", f"{t.get('up', 0)} 家", delta=None if y.get('up') is None else f"{int(t.get('up', 0) - y.get('up', 0))} 家")
            m[1].metric("跌家數 📉", f"{t.get('dn', 0)} 家", delta=None if y.get('dn') is None else f"{int(t.get('dn', 0) - y.get('dn', 0))} 家", delta_color="inverse")
            m[2].metric("平盤數 ➖", f"{t.get('fl', 0)} 家", delta=None if y.get('fl') is None else f"{int(t.get('fl', 0) - y.get('fl', 0))} 家", delta_color="off")
            m[3].metric("漲停數 🚀", f"{t.get('lu', 0)} 家", delta=None if y.get('lu') is None else f"{int(t.get('lu', 0) - y.get('lu', 0))} 家")
            m[4].metric("跌停數 ☠️", f"{t.get('ld', 0)} 家", delta=None if y.get('ld') is None else f"{int(t.get('ld', 0) - y.get('ld', 0))} 家", delta_color="inverse")
            
        if '漲跌幅' in f_df.columns:
            l_up, l_dn = f_df[f_df['漲跌幅'] >= 9.5], f_df[f_df['漲跌幅'] <= -9.5]
            if not l_up.empty:
                with st.expander(f"✨ 查看 {len(l_up)} 檔漲停標的"): st.write("、".join((l_up['統一代號'] + " " + l_up['股票名稱']).tolist()))
            if not l_dn.empty:
                with st.expander(f"⚠️ 查看 {len(l_dn)} 檔跌停標的"): st.write("、".join((l_dn['統一代號'] + " " + l_dn['股票名稱']).tolist()))

        if 'bh' in locals() and not bh.empty:
            st.markdown("##### 📅 歷史盤面變化")
            bt = bh.rename(columns={'up':'漲家數','dn':'跌家數','fl':'平盤數','lu':'漲停數','ld':'跌停數'}).set_index('標準日期').T
            # 🚀 修復日期顯示問題 (10/08 變 0/08)，改為取後 5 碼
            bt.columns = [str(c)[-5:] if len(str(c)) >= 5 else str(c) for c in bt.columns]
            st.dataframe(bt, use_container_width=True)

        st.markdown("---")

    tab_basic, tab_momentum = st.tabs(["🔹 全市場基礎量價", "🔹 資金動能雷達"])

    with tab_basic:
        st.markdown(f"**共找到 {len(f_df)} 檔符合條件的標的**")
        # 改為顯示 成交額(萬)
        basic_cols = [c for c in ['統一代號', '股票名稱', '成交', '漲跌幅', '成交張數', '成交額(萬)', '成交金額日變化率', 'PER', '5日均量', '5日均額', 'B0_量價狀態', 'B0_特殊型態'] if c in f_df.columns]
        st.dataframe(f_df[basic_cols],
            use_container_width=True, hide_index=True, height=500, column_config={
                "統一代號": st.column_config.TextColumn("代號"), "股票名稱": st.column_config.TextColumn("名稱"),
                "成交金額日變化率": st.column_config.NumberColumn("日變化率(%)", format="%+.1f %%"),
                "B0_量價狀態": st.column_config.TextColumn("量價主力照妖鏡", width="large"), "B0_特殊型態": st.column_config.TextColumn("特殊型態雷達", width="medium"),
                **{k: st.column_config.NumberColumn(n, format=f) for k, n, f in [("成交","成交價","%.2f"), ("漲跌幅","漲跌幅(%)","%.2f"), ("成交張數","今日成交(張)","%d"), ("5日均量","5日均量(張)","%d"), ("成交額(萬)","成交額(萬)","%.0f"), ("5日均額","5日均額(萬)","%.0f"), ("PER","本益比","%.2f")]}
            })

    with tab_momentum:
        st.markdown("#### 資金動力渦輪：找出真正的行情燃料\n<small>排除流動性過差標的 (避免倍數失真)。</small>", unsafe_allow_html=True)
        # 🚀 單位由百萬轉為萬，過濾條件改為 > 5000萬 (即原來的 50M)
        if '成交額(萬)' in f_df.columns and '成交' in f_df.columns:
            m_df = f_df[(f_df['成交額(萬)'] > 5000) & (f_df['成交'] > 10)].copy()
        else:
            m_df = f_df.copy()
            
        periods = [5, 10, 20, 30, 45]
        base_cfg = {"統一代號": st.column_config.TextColumn("代號"), "股票名稱": st.column_config.TextColumn("名稱"), "成交金額日變化率": st.column_config.NumberColumn("日變化率(%)", format="%+.1f %%"), "成交額(萬)": st.column_config.NumberColumn("今日成交(萬)", format="%.0f")}

        st.markdown("---")
        st.markdown("##### 🏆 成交額大熱鍋\n<small>市場資金總量增加最多，代表用錢砸出來的活絡程度。</small>", unsafe_allow_html=True)
        abs_tabs = st.tabs(["🔥 總覽"] + [f"🔹相較 {p} 日" for p in periods])
        with abs_tabs[0]:
            # 🚀 修正 fallback KeyError：改用新的 成交額(萬)
            sort_k = '較5日均額增加' if '較5日均額增加' in m_df.columns else '成交額(萬)'
            abs_cols = [c for c in ['統一代號', '股票名稱', '成交金額日變化率', '成交額(萬)'] + [f'較{p}日均額增加' for p in periods] if c in m_df.columns]
            if not m_df.empty and sort_k in m_df.columns:
                st.dataframe(m_df.sort_values(sort_k, ascending=False).head(50)[abs_cols], use_container_width=True, hide_index=True, height=500, column_config={**base_cfg, **{f'較{p}日均額增加': st.column_config.NumberColumn(f"較{p}日增加(萬)", format="+%.0f") for p in periods}})
        
        for i, p in enumerate(periods):
            with abs_tabs[i+1]:
                if f'較{p}日均額增加' in m_df.columns and not m_df.empty:
                    st.dataframe(m_df.sort_values(f'較{p}日均額增加', ascending=False).head(30)[['統一代號', '股票名稱', f'較{p}日均額增加', '成交額(萬)', f'{p}日均額', '成交金額日變化率', '漲跌幅']], use_container_width=True, hide_index=True, height=400, column_config={**base_cfg, f'較{p}日均額增加': st.column_config.NumberColumn(f"▲較{p}日增加(萬)", format="+%.0f"), f'{p}日均額': st.column_config.NumberColumn(f"{p}日均額(萬)", format="%.0f"), "漲跌幅": st.column_config.NumberColumn("漲跌幅%", format="%.2f")})

        st.markdown("##### 🚀 出量點火器\n<small>尋找異常放量的股票 (突破或波段發動)。</small>", unsafe_allow_html=True)
        ign_tabs = st.tabs(["🔥 總覽"] + [f"🔹相較 {p} 日" for p in periods])
        with ign_tabs[0]:
            sort_k = '5日爆發倍數' if '5日爆發倍數' in m_df.columns else '成交額(萬)'
            ign_cols = [c for c in ['統一代號', '股票名稱', '成交金額日變化率', '成交額(萬)'] + [f'{p}日爆發倍數' for p in periods] if c in m_df.columns]
            if not m_df.empty and sort_k in m_df.columns:
                st.dataframe(m_df.sort_values(sort_k, ascending=False).head(50)[ign_cols], use_container_width=True, hide_index=True, height=500, column_config={**base_cfg, **{f'{p}日爆發倍數': st.column_config.NumberColumn(f"{p}日倍數", format="%.1fx") for p in periods}})

        for i, p in enumerate(periods):
            with ign_tabs[i+1]:
                if f'{p}日爆發倍數' in m_df.columns and not m_df.empty:
                    st.dataframe(m_df.sort_values(f'{p}日爆發倍數', ascending=False).head(30)[['統一代號', '股票名稱', f'{p}日爆發倍數', '成交額(萬)', f'{p}日均額', '成交金額日變化率', '漲跌幅']], use_container_width=True, hide_index=True, height=400, column_config={**base_cfg, f'{p}日爆發倍數': st.column_config.NumberColumn("🚀爆發倍數", format="%.1fx"), f'{p}日均額': st.column_config.NumberColumn(f"{p}日均額(萬)", format="%.0f"), "漲跌幅": st.column_config.NumberColumn("漲跌幅%", format="%.2f")})

        st.markdown("##### 📈 持續資金水龍頭\n<small>短週期 > 長週期，代表成交金額持續擴張，資金連續進駐。</small>", unsafe_allow_html=True)
        if '成交額(萬)' in m_df.columns and not m_df.empty:
            flow_cols = [c for c in ['統一代號', '股票名稱', '資金延續趨勢', '成交額(萬)', '5日均額', '10日均額', '20日均額', '30日均額'] if c in m_df.columns]
            st.dataframe(m_df.sort_values('成交額(萬)', ascending=False).head(150)[flow_cols], use_container_width=True, hide_index=True, height=600, column_config={"統一代號": "代號", "股票名稱": "名稱", "資金延續趨勢": st.column_config.TextColumn("資金延續狀態", width="medium"), **{k: st.column_config.NumberColumn(n, format="%.0f") for k, n in [("成交額(萬)","今日成交(萬)"), ("5日均額","5日均"), ("10日均額","10日均"), ("20日均額","20日均"), ("30日均額","30日均")]}})

# ==========================================
# 🌟 主渲染入口
# ==========================================
def show_b0_page(DATA_DIR, STOCK_DICT):
    res = get_cached_b0_data(DATA_DIR)
    if not res or res[0] is None or res[0].empty: 
        return st.warning("⚠️ 查無合併資料。請確認後台的 B0 運算腳本是否成功產出合併版檔案。")
        
    df_b0, df_history = res
    d_raw = str(df_b0['股價日期'].iloc[0]) if '股價日期' in df_b0.columns else ""
    dt_str = f"{d_raw[:4]}/{d_raw[4:6]}/{d_raw[6:8]}" if len(d_raw) >= 8 else (f"2026/{d_raw[:2]}/{d_raw[2:]}" if len(d_raw) == 4 else d_raw)

    st.markdown("""<div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;"><h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">量價與估值掃描</h2></div>""", unsafe_allow_html=True)
    st.caption(f"資料基準日: **{dt_str}** ｜ 透視全市場資金動能與主力控盤狀態。")
    st.write("---")
    
    # 🚀 Vectorized name mapping
    if 'B0_原始名稱' in df_b0.columns:
        df_b0['股票名稱'] = df_b0['B0_原始名稱'].replace({'nan': '', 'none': '', 'NaN': ''})
        if STOCK_DICT:
            name_map = {k: v.get('name', '') for k, v in STOCK_DICT.items()}
            df_b0['股票名稱'] = np.where(df_b0['股票名稱'] == '', df_b0['統一代號'].map(name_map).fillna(''), df_b0['股票名稱'])
    elif '股票名稱' not in df_b0.columns and STOCK_DICT:
        name_map = {k: v.get('name', '') for k, v in STOCK_DICT.items()}
        df_b0['股票名稱'] = df_b0['統一代號'].map(name_map).fillna('')

    render_b0_interactive_dashboard(df_b0, df_history)
