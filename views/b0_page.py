# views/b0_page.py
import streamlit as st
import pandas as pd
import numpy as np
import os
import glob
import re

# ==========================================
# 💡 效能救星 1：向量化資料處理引擎 (Vectorized Cache)
# ==========================================
@st.cache_data(show_spinner=False, ttl=300)
def get_cached_b0_data(DATA_DIR):
    files = glob.glob(os.path.join(DATA_DIR, "*成交價*.parquet")) + glob.glob(os.path.join(DATA_DIR, "*成交價*.csv"))
    if not files: return None
        
    all_dfs = []
    for f in files:
        try:
            df = pd.read_parquet(f) if f.endswith('.parquet') else pd.read_csv(f, encoding='utf-8-sig', dtype=str)
        except:
            for enc in ['big5', 'cp950', 'utf-8']:
                try: df = pd.read_csv(f, encoding=enc, dtype=str); break
                except: pass
            else: continue
            
        if df is not None and not df.empty:
            df.columns = [re.sub(r'\s+', '', str(c)) for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()] # 剔除重複欄位
            
            c_code = next((c for c in df.columns if '代號' in c), None)
            date_col = next((c for c in df.columns if '日期' in c), None)
            name_col = next((c for c in df.columns if c in ['名稱', '股票名稱', '證券名稱']), None)
            
            if c_code and date_col:
                df['統一代號'] = df[c_code].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df['標準日期'] = df[date_col].astype(str).str.strip()
                df['B0_原始名稱'] = df[name_col].astype(str).str.strip() if name_col else ""
                
                # 🚀 記憶體砍半魔法：加入 downcast='integer' 與 downcast='float'
                vol_col = next((c for c in df.columns if c in ['成交張數', '總量', '成交量', '累積成交張數', '張數']), None)
                if vol_col:
                    df['成交張數_num'] = pd.to_numeric(df[vol_col].astype(str).str.replace(',', ''), errors='coerce', downcast='integer').fillna(0)
                else:
                    df['成交張數_num'] = np.int32(0)
                df['成交張數'] = df['成交張數_num'] 
                
                amt_col = next((c for c in df.columns if c in ['成交額(百萬)', '成交金額', '成交額', '總金額']), None)
                if amt_col:
                    df['成交額_num'] = pd.to_numeric(df[amt_col].astype(str).str.replace(',', ''), errors='coerce', downcast='float').fillna(0)
                else:
                    df['成交額_num'] = np.float32(0)
                df['成交額(百萬)'] = df['成交額_num']
                
                for c in ['PER', '成交', '漲跌幅']:
                    if c in df.columns: 
                        df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[,%]', '', regex=True), errors='coerce', downcast='float')
                
                all_dfs.append(df)
                
    if not all_dfs: return None
    
    combined_df = pd.concat(all_dfs, ignore_index=True)
    if '統一代號' in combined_df.columns: combined_df['統一代號'] = combined_df['統一代號'].fillna("").astype(str)
    combined_df['標準日期'] = combined_df['標準日期'].fillna("").astype(str)
    combined_df = combined_df[~combined_df['標準日期'].str.lower().str.strip().isin(['nan', 'nat', 'none', ''])]

    # 排序與去重
    combined_df = combined_df.sort_values(by=['統一代號', '標準日期', '成交張數_num'], ascending=[True, False, False])
    combined_df = combined_df.drop_duplicates(subset=['統一代號', '標準日期'], keep='first')
    
    unique_dates = sorted([str(d) for d in combined_df['標準日期'].unique()], reverse=True)
    if not unique_dates: return None
    latest_date = unique_dates[0]
    
    df_today = combined_df[combined_df['標準日期'] == latest_date].copy()
    sorted_df = combined_df.sort_values(by=['統一代號', '標準日期'], ascending=[True, False])
    
    # 🚀 Pandas 向量化多週期計算 (取代冗長迴圈合併)
    periods = [5, 10, 20, 30, 45]
    for p in periods:
        p_avg = sorted_df.groupby('統一代號').head(p).groupby('統一代號').agg(
            **{f'{p}日均量': ('成交張數_num', 'mean'), f'{p}日均額': ('成交額_num', 'mean')}
        ).reset_index()
        df_today = df_today.merge(p_avg, on='統一代號', how='left')
        df_today[f'{p}日均量'] = df_today[f'{p}日均量'].round(0)
        df_today[f'{p}日均額'] = df_today[f'{p}日均額'].round(2)

    df_today['股價日期'] = latest_date
    
    # 擷取昨日資料
    prev_day = sorted_df.groupby('統一代號').nth(1).reset_index()[['統一代號', '成交額_num', '成交張數_num', '漲跌幅']].rename(
        columns={'成交額_num': '昨日成交額', '成交張數_num': '昨日成交量', '漲跌幅': '昨日漲跌幅'})
    df_today = df_today.merge(prev_day, on='統一代號', how='left')
    
    df_today['成交金額日變化率'] = ((df_today['成交額_num'] / df_today['昨日成交額'].replace(0, 0.01).fillna(0.01)) - 1) * 100

    # 🚀 效能突破點：使用 np.select 取代 apply(axis=1) 瞬間完成陣列計算
    tdy_pct, yst_pct = df_today['漲跌幅'].fillna(0), df_today['昨日漲跌幅'].fillna(0)
    tdy_vol, yst_vol, avg_v = df_today['成交張數_num'].fillna(0), df_today['昨日成交量'].fillna(0), df_today['5日均量'].fillna(0)
    
    cond_wash = (yst_pct >= 4.0) & (yst_vol >= 1000) & (tdy_vol <= yst_vol * 0.5) & (tdy_pct >= -2.0)
    cond_choke = (avg_v >= 500) & (tdy_vol > 0) & (tdy_vol <= avg_v * 0.3) & (tdy_pct.abs() <= 1.5)
    df_today['B0_特殊型態'] = np.select([cond_wash, cond_choke], ["🕵️ 昨強今急縮 (洗盤防守)", "💤 極致窒息量 (醞釀表態)"], default="-")

    ratio = tdy_vol / avg_v.replace(0, np.nan)
    v_s = np.select([ratio >= 1.5, ratio <= 0.7], ["放量", "縮量"], default="平量")
    p_s = np.select([tdy_pct >= 4.0, tdy_pct > 1.5, tdy_pct >= -1.5, tdy_pct > -4.0], ["大漲", "價升", "滯漲", "小跌"], default="大跌")
    
    status_map = {"放量大漲":"🚀 放量大漲 (量價齊升，持續看漲)", "縮量大漲":"🔒 縮量大漲 (鎖倉高控盤，延續上漲)", "平量大漲":"✈️ 平量大漲 (一致看漲無拋壓，加速上漲)",
                  "縮量價升":"📈 價升量縮 (量價背離，下方承接看拉高)", "放量滯漲":"⚠️ 放量滯漲 (拋壓增大，即將見頂反轉)", "平量滯漲":"⏸️ 平量滯漲 (拋壓增大，高位見頂)",
                  "縮量小跌":"📉 縮量小跌 (主力洗盤止跌，擇機進場)", "放量小跌":"🛡️ 放量小跌 (見底信號，越跌越買反轉)", "平量小跌":"🥀 平量價縮 (下跌中繼，弱反彈信號)",
                  "縮量大跌":"☠️ 縮量大跌 (一致看空無承接，加速下跌)", "放量大跌":"🩸 放量大跌 (跟風砸盤，高位出貨持續跌)", "平量大跌":"🕳️ 平量大跌 (一致看空無承接，加速下跌)"}
    
    df_today['B0_量價狀態'] = pd.Series(v_s + p_s).map(status_map).fillna("⚖️ 溫和震盪整理").values
    df_today['B0_量價狀態'] = np.where((avg_v == 0) | (tdy_vol == 0), "⚪ 無明顯動能", df_today['B0_量價狀態'])
    
    return df_today, combined_df

def sync_b0_data(DATA_DIR):
    if (res := get_cached_b0_data(DATA_DIR)) is not None: st.session_state['b0_price'] = res[0]


# ==========================================
# 🚀 效能救星 2：Fragment 化互動面板
# ==========================================
@st.fragment
def render_b0_interactive_dashboard(df_b0, df_history):
    top_container = st.container()

    with st.expander("🛠️ 全域條件篩選 (點擊展開/收合)", expanded=True):
        c1, c2, c3, c4 = st.columns([1.5, 1, 1.5, 1])
        search_kw = c1.text_input("🔍 搜尋代號/名稱", placeholder="例如: 2330 或 台積電")
        vol_filter = c2.number_input("成交量 > (張)", min_value=0, value=0, step=1000)
        sel_status = c3.multiselect("🎯 狀態過濾", sorted(df_b0['B0_量價狀態'].unique()), placeholder="預設全選")
        sel_per = c4.selectbox("⚖️ 估值(PER)過濾", ["全部顯示", "PER < 15 (低估值)", "PER < 30 (合理)", "僅顯示獲利公司 (PER>0)"])
        st.markdown("---")
        sel_special = st.multiselect("🕵️ 特殊洗盤與窒息量篩選 (高勝率買點)", [opt for opt in df_b0['B0_特殊型態'].unique() if opt != "-"], placeholder="未選擇則顯示全部")

    # 執行過濾
    f_df = df_b0.copy()
    if search_kw: f_df = f_df[f_df['統一代號'].str.contains(search_kw) | f_df['股票名稱'].str.contains(search_kw)]
    if vol_filter > 0: f_df = f_df[f_df['成交張數_num'] >= vol_filter]
    if sel_status: f_df = f_df[f_df['B0_量價狀態'].isin(sel_status)]
    if "PER < 15" in sel_per: f_df = f_df[(f_df['PER'] > 0) & (f_df['PER'] < 15)]
    elif "PER < 30" in sel_per: f_df = f_df[(f_df['PER'] > 0) & (f_df['PER'] < 30)]
    elif "PER>0" in sel_per: f_df = f_df[f_df['PER'] > 0]
    if sel_special: f_df = f_df[f_df['B0_特殊型態'].isin(sel_special)]

    # 🌟 回填頂部盤面結構
    with top_container:
        st.markdown("### 📊 盤面結構 (基於當前篩選條件)")
        
        # 🚀 向量化聚合計算，取代 groupby lambda
        h_df = df_history[df_history['統一代號'].isin(f_df['統一代號'].unique())].copy()
        bh = h_df.assign(
            up=h_df['漲跌幅'] > 0, dn=h_df['漲跌幅'] < 0, fl=h_df['漲跌幅'] == 0,
            lu=h_df['漲跌幅'] >= 9.5, ld=h_df['漲跌幅'] <= -9.5
        ).groupby('標準日期')[['up', 'dn', 'fl', 'lu', 'ld']].sum().reset_index().sort_values('標準日期', ascending=False)
        
        t, y = (bh.iloc[0], bh.iloc[1]) if len(bh) > 1 else (bh.iloc[0] if len(bh) > 0 else pd.Series(0, index=['up','dn','fl','lu','ld']), pd.Series([None]*5, index=['up','dn','fl','lu','ld']))
        if len(bh) == 0: t = pd.Series(0, index=['up','dn','fl','lu','ld'])

        m = st.columns(5)
        m[0].metric("漲家數 📈", f"{t['up']} 家", delta=None if y['up'] is None else f"{int(t['up'] - y['up'])} 家")
        m[1].metric("跌家數 📉", f"{t['dn']} 家", delta=None if y['dn'] is None else f"{int(t['dn'] - y['dn'])} 家", delta_color="inverse")
        m[2].metric("平盤數 ➖", f"{t['fl']} 家", delta=None if y['fl'] is None else f"{int(t['fl'] - y['fl'])} 家", delta_color="off")
        m[3].metric("漲停數 🚀", f"{t['lu']} 家", delta=None if y['lu'] is None else f"{int(t['lu'] - y['lu'])} 家")
        m[4].metric("跌停數 ☠️", f"{t['ld']} 家", delta=None if y['ld'] is None else f"{int(t['ld'] - y['ld'])} 家", delta_color="inverse")
        
        l_up, l_dn = f_df[f_df['漲跌幅'] >= 9.5], f_df[f_df['漲跌幅'] <= -9.5]
        if not l_up.empty:
            with st.expander(f"✨ 查看 {len(l_up)} 檔漲停標的"): st.write("、".join((l_up['統一代號'] + " " + l_up['股票名稱']).tolist()))
        if not l_dn.empty:
            with st.expander(f"⚠️ 查看 {len(l_dn)} 檔跌停標的"): st.write("、".join((l_dn['統一代號'] + " " + l_dn['股票名稱']).tolist()))

        if not bh.empty:
            st.markdown("##### 📅 歷史盤面變化")
            bt = bh.rename(columns={'up':'漲家數','dn':'跌家數','fl':'平盤數','lu':'漲停數','ld':'跌停數'}).set_index('標準日期').T
            bt.columns = [str(c)[-4:] for c in bt.columns]
            st.dataframe(bt, use_container_width=True)

        st.markdown("---")

    tab_basic, tab_momentum = st.tabs(["🔹 全市場基礎量價", "🔹 資金動能雷達"])

    with tab_basic:
        st.markdown(f"**共找到 {len(f_df)} 檔符合條件的標的**")
        st.dataframe(f_df[[c for c in ['統一代號', '股票名稱', '成交', '漲跌幅', '成交張數', '成交額(百萬)', '成交金額日變化率', 'PER', '5日均量', '5日均額', 'B0_量價狀態', 'B0_特殊型態'] if c in f_df.columns]],
            use_container_width=True, hide_index=True, height=500, column_config={
                "統一代號": st.column_config.TextColumn("代號"), "股票名稱": st.column_config.TextColumn("名稱"),
                "成交金額日變化率": st.column_config.NumberColumn("日變化率(%)", format="%+.1f %%"),
                "B0_量價狀態": st.column_config.TextColumn("量價主力照妖鏡", width="large"), "B0_特殊型態": st.column_config.TextColumn("特殊型態雷達", width="medium"),
                **{k: st.column_config.NumberColumn(n, format=f) for k, n, f in [("成交","成交價","%.2f"), ("漲跌幅","漲跌幅(%)","%.2f"), ("成交張數","今日成交(張)","%d"), ("5日均量","5日均量(張)","%d"), ("成交額(百萬)","成交額(百萬)","%.2f"), ("5日均額","5日均成交額(百萬)","%.2f"), ("PER","本益比","%.2f")]}
            })

    with tab_momentum:
        st.markdown("#### 資金動力渦輪：找出真正的行情燃料\n<small>排除流動性過差標的 (成交額 > 50M 且 股價 > 10)，避免倍數失真。</small>", unsafe_allow_html=True)
        m_df = f_df[(f_df['成交額(百萬)'] > 50) & (f_df['成交'] > 10) & (f_df.get('5日均額', 0) > 10)].copy()
        periods = [5, 10, 20, 30, 45]
        
        # 🚀 一次性向量化所有週期計算
        for p in periods:
            if f'{p}日均額' in m_df.columns:
                m_df[f'較{p}日均額增加'] = m_df['成交額(百萬)'] - m_df[f'{p}日均額']
                m_df[f'{p}日爆發倍數'] = (m_df['成交額(百萬)'] / m_df[f'{p}日均額'].replace(0, 0.01)).fillna(0)

        # 🚀 運用 np.select 取代 apply 計算資金延續趨勢
        t_amt, m5, m10, m20 = m_df['成交額(百萬)'].fillna(0), m_df.get('5日均額', pd.Series(0, index=m_df.index)).fillna(0), m_df.get('10日均額', pd.Series(0, index=m_df.index)).fillna(0), m_df.get('20日均額', pd.Series(0, index=m_df.index)).fillna(0)
        v = (m5 > 0) & (m10 > 0) & (m20 > 0)
        m_df['資金延續趨勢'] = np.select(
            [v & (m5 > m10) & (m10 > m20), v & (t_amt > m5) & (m5 <= m10), v & (m5 < m10) & (m10 < m20), v],
            ["🔥 資金湧入 (延續性強)", "⚡ 單日點火 (需觀察)", "💧 資金退潮 (動能弱)", "⚖️ 震盪換手"], default="⚪ 資料不足"
        )

        # UI 元件共用設定
        base_cfg = {"統一代號": st.column_config.TextColumn("代號"), "股票名稱": st.column_config.TextColumn("名稱"), "成交金額日變化率": st.column_config.NumberColumn("日變化率(%)", format="%+.1f %%"), "成交額(百萬)": st.column_config.NumberColumn("今日成交額", format="%.0f")}

        st.markdown("---")
        st.markdown("##### 🏆 成交額大熱鍋\n<small>市場資金總量增加最多，代表用錢砸出來的活絡程度。</small>", unsafe_allow_html=True)
        abs_tabs = st.tabs(["🔥 總覽"] + [f"🔹相較 {p} 日" for p in periods])
        with abs_tabs[0]:
            sort_k = '較5日均額增加' if '較5日均額增加' in m_df.columns else '成交額(百萬)'
            st.dataframe(m_df.sort_values(sort_k, ascending=False).head(50)[[c for c in ['統一代號', '股票名稱', '成交金額日變化率', '成交額(百萬)'] + [f'較{p}日均額增加' for p in periods] if c in m_df.columns]], use_container_width=True, hide_index=True, height=500, column_config={**base_cfg, **{f'較{p}日均額增加': st.column_config.NumberColumn(f"較{p}日增加", format="+%.0f") for p in periods}})
        
        for i, p in enumerate(periods):
            with abs_tabs[i+1]:
                if f'較{p}日均額增加' in m_df.columns:
                    st.dataframe(m_df.sort_values(f'較{p}日均額增加', ascending=False).head(30)[['統一代號', '股票名稱', f'較{p}日均額增加', '成交額(百萬)', f'{p}日均額', '成交金額日變化率', '漲跌幅']], use_container_width=True, hide_index=True, height=400, column_config={**base_cfg, f'較{p}日均額增加': st.column_config.NumberColumn(f"▲較{p}日增加", format="+%.0f"), f'{p}日均額': st.column_config.NumberColumn(f"{p}日均額", format="%.0f"), "漲跌幅": st.column_config.NumberColumn("漲跌幅%", format="%.2f")})

        st.markdown("##### 🚀 出量點火器\n<small>尋找異常放量的股票 (突破或波段發動)。</small>", unsafe_allow_html=True)
        ign_tabs = st.tabs(["🔥 總覽"] + [f"🔹相較 {p} 日" for p in periods])
        with ign_tabs[0]:
            sort_k = '5日爆發倍數' if '5日爆發倍數' in m_df.columns else '成交額(百萬)'
            st.dataframe(m_df.sort_values(sort_k, ascending=False).head(50)[[c for c in ['統一代號', '股票名稱', '成交金額日變化率', '成交額(百萬)'] + [f'{p}日爆發倍數' for p in periods] if c in m_df.columns]], use_container_width=True, hide_index=True, height=500, column_config={**base_cfg, **{f'{p}日爆發倍數': st.column_config.NumberColumn(f"{p}日倍數", format="%.1fx") for p in periods}})

        for i, p in enumerate(periods):
            with ign_tabs[i+1]:
                if f'{p}日爆發倍數' in m_df.columns:
                    st.dataframe(m_df.sort_values(f'{p}日爆發倍數', ascending=False).head(30)[['統一代號', '股票名稱', f'{p}日爆發倍數', '成交額(百萬)', f'{p}日均額', '成交金額日變化率', '漲跌幅']], use_container_width=True, hide_index=True, height=400, column_config={**base_cfg, f'{p}日爆發倍數': st.column_config.NumberColumn("🚀爆發倍數", format="%.1fx"), f'{p}日均額': st.column_config.NumberColumn(f"{p}日均額", format="%.0f"), "漲跌幅": st.column_config.NumberColumn("漲跌幅%", format="%.2f")})

        st.markdown("##### 📈 持續資金水龍頭\n<small>短週期 > 長週期，代表成交金額持續擴張，資金連續進駐。</small>", unsafe_allow_html=True)
        st.dataframe(m_df.sort_values('成交額(百萬)', ascending=False).head(150)[[c for c in ['統一代號', '股票名稱', '資金延續趨勢', '成交額(百萬)', '5日均額', '10日均額', '20日均額', '30日均額'] if c in m_df.columns]], use_container_width=True, hide_index=True, height=600, column_config={"統一代號": "代號", "股票名稱": "名稱", "資金延續趨勢": st.column_config.TextColumn("資金延續狀態", width="medium"), **{k: st.column_config.NumberColumn(n, format="%.0f") for k, n in [("成交額(百萬)","今日成交"), ("5日均額","5日均"), ("10日均額","10日均"), ("20日均額","20日均"), ("30日均額","30日均")]}})

# ==========================================
# 🌟 主渲染入口
# ==========================================
def show_b0_page(DATA_DIR, STOCK_DICT):
    res = get_cached_b0_data(DATA_DIR)
    if not res or res[0].empty: return st.warning("⚠️ 查無成交價檔案。")
        
    df_b0, df_history = res
    d_raw = str(df_b0['股價日期'].iloc[0])
    dt_str = f"{d_raw[:4]}/{d_raw[4:6]}/{d_raw[6:8]}" if len(d_raw) >= 8 else (f"2026/{d_raw[:2]}/{d_raw[2:]}" if len(d_raw) == 4 else d_raw)

    st.markdown("""<div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;"><h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">量價與估值掃描</h2></div>""", unsafe_allow_html=True)
    st.caption(f"資料基準日: **{dt_str}** ｜ 透視全市場資金動能與主力控盤狀態。")
    st.write("---")
    
    # 🚀 Vectorized name mapping
    df_b0['股票名稱'] = df_b0['B0_原始名稱'].replace({'nan': '', 'none': '', 'NaN': ''})
    if STOCK_DICT:
        name_map = {k: v.get('name', '') for k, v in STOCK_DICT.items()}
        df_b0['股票名稱'] = np.where(df_b0['股票名稱'] == '', df_b0['統一代號'].map(name_map).fillna(''), df_b0['股票名稱'])

    render_b0_interactive_dashboard(df_b0, df_history)
