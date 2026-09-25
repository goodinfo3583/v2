# views/b5_page.py
import streamlit as st
import pandas as pd
import os
import glob
import re
import html
import plotly.express as px

# ==========================================
# 🌟 區塊 5 專屬工具函數區 (純運算，無 UI)
# ==========================================

# 💡 效能救星 1：快取最新日期掃描，避免每次換頁重新讀硬碟
@st.cache_data(show_spinner=False, ttl=600)
def get_b5_latest_date(DATA_DIR):
    """掃描最新檔案日期以供標題基準日顯示"""
    global_latest = "0605"
    all_files = glob.glob(os.path.join(DATA_DIR, "*大股東*"))
    for f in all_files:
        match = re.search(r'(\d{8})', os.path.basename(f))
        if match and match.group(1).startswith("202"):
            date_str = match.group(1)[4:]
            if date_str > global_latest:
                global_latest = date_str
    return global_latest

# 💡 效能救星 2：把 6 個級距的龐大合併與運算徹底快取 (並導入極限記憶體瘦身)
@st.cache_data(show_spinner=False, ttl=600)
def process_major_shareholders(DATA_DIR, target_level):
    """通用大戶資料產生器 (純後台版) - 統一處理 1000/800/600/400/200/100 張"""
    files = []
    for ext in ('*.parquet', '*.csv', '*.CSV'):
        files.extend(glob.glob(os.path.join(DATA_DIR, f"*大股東*{ext}")))
    if not files: return pd.DataFrame()
    
    groups = {}
    for f in files:
        m = re.search(r'(\d{8})', os.path.basename(f))
        key = m.group(1) if m else "UNKNOWN"
        groups.setdefault(key, []).append(f)
    
    merged, all_dates_4 = [], []
    target_num = target_level.replace('1千', '1000').replace('千', '000')

    for prefix, fs in sorted(groups.items(), reverse=True):
        chunks = []
        detected_date = None
        
        for f in fs:
            df = None
            if f.endswith('.parquet'):
                try: df = pd.read_parquet(f)
                except Exception: pass
            else:
                for enc in ['utf-8-sig', 'big5', 'cp950', 'utf-8']:
                    try:
                        df = pd.read_csv(f, encoding=enc)
                        break 
                    except: pass
            
            if df is None or df.empty: continue
            
            df.columns = [re.sub(r'[\s\n\r\t\u3000\ufeff]+', '', str(c)) for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            
            c_code = next((c for c in df.columns if '代號' in c or '代碼' in c), None)
            c_name = next((c for c in df.columns if '名稱' in c), None)
            c_date = next((c for c in df.columns if '日期' in c), None)
            
            c_abs = next((c for c in df.columns if (target_level in c or target_num in c) and ('%' in c or '比例' in c) and '增減' not in c and '差' not in c and ('超過' in c or '以上' in c)), None)
            c_delta = next((c for c in df.columns if (target_level in c or target_num in c) and ('增減' in c or '差' in c) and ('超過' in c or '以上' in c)), None)
            
            is_inverted = False
            if not c_abs or not c_delta:
                c_abs = next((c for c in df.columns if (target_level in c or target_num in c) and ('%' in c or '比例' in c) and '增減' not in c and '差' not in c and '以下' in c), None)
                c_delta = next((c for c in df.columns if (target_level in c or target_num in c) and ('增減' in c or '差' in c) and '以下' in c), None)
                if c_abs and c_delta: is_inverted = True 
            
            if not all([c_code, c_name, c_abs, c_delta]): continue
            
            try:
                # 💡 記憶體瘦身：將代號與名稱轉為字串，稍後合併完轉 category
                df['股票代號'] = df[c_code].astype(str).str.extract(r'(\d+)', expand=False)
                df['股票名稱'] = df[c_name].astype(str).str.replace(r'^\d+', '', regex=True).str.strip()
                
                # 💡 記憶體瘦身：讀取時立刻降級為 float32
                raw_abs = pd.to_numeric(df[c_abs].astype(str).str.replace('%', '', regex=False), errors='coerce').astype('float32')
                raw_delta = pd.to_numeric(df[c_delta].astype(str).str.replace('+', '', regex=False).str.replace('%', '', regex=False), errors='coerce').astype('float32')
                
                if is_inverted:
                    df['持股%'] = (100.0 - raw_abs.fillna(100.0)).astype('float32')
                    df['增減%'] = (-1.0 * raw_delta.fillna(0.0)).astype('float32')
                else:
                    df['持股%'] = raw_abs
                    df['增減%'] = raw_delta
                
                if detected_date is None and c_date and not df[c_date].dropna().empty:
                    raw_date = str(df[c_date].dropna().iloc[0]).replace('/', '').replace('-', '').strip()
                    detected_date = raw_date[-4:] if len(raw_date) >= 4 else prefix[-4:]
                
                chunks.append(df[['股票代號', '股票名稱', '持股%', '增減%']].dropna(subset=['股票代號']))
            except: continue
        
        if chunks:
            comb = pd.concat(chunks, ignore_index=True)
            comb = comb.drop_duplicates(subset=['股票代號'], keep='first').reset_index(drop=True)
            
            date_4 = detected_date if detected_date else prefix[-4:]
            comb = comb.rename(columns={'持股%': f"{date_4}持有%", '增減%': f"DELTA_{date_4}"})
            
            if date_4 not in all_dates_4: 
                all_dates_4.append(date_4)
                merged.append(comb)
            else:
                idx = all_dates_4.index(date_4)
                merged[idx] = pd.concat([merged[idx], comb]).drop_duplicates(subset=['股票代號', '股票名稱'], keep='first').reset_index(drop=True)

    if merged:
        master = merged[0]
        for m in merged[1:]: 
            master = pd.merge(master, m, on='股票代號', how='outer', suffixes=('', '_old'))
            if '股票名稱_old' in master.columns:
                master['股票名稱'] = master['股票名稱'].fillna(master['股票名稱_old'])
                master = master.drop(columns=['股票名稱_old'])
                
        sorted_dates_4 = sorted(all_dates_4, reverse=True)
        latest_date_4 = sorted_dates_4[0]
        
        def get_trend(val):
            if pd.isna(val): return "無資料"
            if val >= 1.5: return "🚀 劇增"
            if val >= 1.0: return "🔥 大增"
            if val >= 0.5: return "📈 小增"
            if val > 0:    return "↗️ 微增"
            if val == 0:   return "🔄 持平"
            if val > -0.5: return "↘️ 微減"
            if val > -1.0: return "📉 小減"
            if val > -1.5: return "⚠️ 大減"
            return "🚨 劇減"
            
        # 💡 將分類標籤轉為 category 節省空間
        master['週動態'] = master[f"DELTA_{latest_date_4}"].apply(get_trend).astype('category')
        
        calc_cols = [f"DELTA_{d}" for d in sorted_dates_4[:6] if f"DELTA_{d}" in master.columns]
        master['▼6周增減'] = master[calc_cols].sum(axis=1, min_count=1).astype('float32')
        
        rename_dict = {}
        cols_order = ['股票代號', '股票名稱', '週動態', '▼6周增減']
        if f"{latest_date_4}持有%" in master.columns: cols_order.append(f"{latest_date_4}持有%")
            
        for i, d in enumerate(sorted_dates_4):
            original_delta_col = f"DELTA_{d}"
            if original_delta_col in master.columns:
                new_delta_name = f"▼{d}" if i == 0 else f"{d}"
                rename_dict[original_delta_col] = new_delta_name
                cols_order.append(new_delta_name)
                
        master = master.rename(columns=rename_dict)
        final_df = master[[c for c in cols_order if c in master.columns]].copy()
        
        # 💡 最後才把字串轉為 category，避免 merge 時的衝突
        final_df['股票代號'] = final_df['股票代號'].astype('category')
        final_df['股票名稱'] = final_df['股票名稱'].astype('category')
        
        return final_df.sort_values(by=f"▼{latest_date_4}", ascending=False)
        
    return pd.DataFrame()


# ==========================================
# ⚙️ 後台資料引擎 (Data Engine) 橋接
# ==========================================
def sync_b5_data(DATA_DIR):
    """計算所有級距資料，並寫入 session_state"""
    st.session_state['b5_1000'] = process_major_shareholders(DATA_DIR, '1千')
    st.session_state['b5_800'] = process_major_shareholders(DATA_DIR, '800')
    st.session_state['b5_600'] = process_major_shareholders(DATA_DIR, '600')
    st.session_state['b5_400'] = process_major_shareholders(DATA_DIR, '400')
    st.session_state['b5_200'] = process_major_shareholders(DATA_DIR, '200')
    st.session_state['b5_100'] = process_major_shareholders(DATA_DIR, '100')


# ==========================================
# 🖼️ 局部渲染魔法：UI 與表格的結界
# ==========================================
def apply_b5_market_filters(df, show_etf, show_bond):
    """前端專用過濾器"""
    if df is None or df.empty: return df
    is_etf = df['股票代號'].astype(str).str.startswith('00')
    is_bond = df['股票代號'].astype(str).str.endswith('B') | df['股票名稱'].astype(str).str.contains('債')
    mask = pd.Series(True, index=df.index)
    if not show_etf: mask = mask & ~(is_etf & ~is_bond)
    if not show_bond: mask = mask & ~is_bond
    return df[mask].copy()

# 💡 效能救星 3：將所有勾選與切換 Tab 封裝入 Fragment，杜絕整頁閃爍！
@st.fragment
def render_b5_dashboard(STOCK_DICT):
    filter_c1, filter_c2, _ = st.columns([2, 3, 5])
    show_etf = filter_c1.checkbox("顯示 ETF", value=True, key="b5_global_etf")
    show_bond = filter_c2.checkbox("顯示 債券 / 債券 ETF", value=True, key="b5_global_bond")

    filtered_1000_df = apply_b5_market_filters(st.session_state.get('b5_1000', pd.DataFrame()), show_etf, show_bond)
    filtered_800_df = apply_b5_market_filters(st.session_state.get('b5_800', pd.DataFrame()), show_etf, show_bond)
    filtered_600_df = apply_b5_market_filters(st.session_state.get('b5_600', pd.DataFrame()), show_etf, show_bond)
    filtered_400_df = apply_b5_market_filters(st.session_state.get('b5_400', pd.DataFrame()), show_etf, show_bond)
    filtered_200_df = apply_b5_market_filters(st.session_state.get('b5_200', pd.DataFrame()), show_etf, show_bond)
    filtered_100_df = apply_b5_market_filters(st.session_state.get('b5_100', pd.DataFrame()), show_etf, show_bond)

    tab_long_short, tab_resonance, tab_1000, tab_800, tab_600, tab_400, tab_200, tab_100 = st.tabs([
        "🔹 長短線共振",  
        "🔹 雙引擎共振",
        "🔹 1000張大戶", 
        "🔹 800張大戶", 
        "🔹 600張大戶", 
        "🔹 400張大戶", 
        "🔹 200張大戶",
        "🔹 100張大戶"
    ])

    # ================= TAB 1: 長短線共振 =================
    with tab_long_short:
        st.markdown("#### 長短線大戶籌碼雙向共振榜")
        st.caption("💡 核心邏輯：1000張大戶波段吸籌（6周增）且本週加碼（最新週增），同時聯手 400張短線大戶波段與本週皆同步加碼的強勢共振標的；另外留意分割股票當周會有很大的誤差。")
        
        if not filtered_1000_df.empty and not filtered_400_df.empty:
            df_1k, df_400 = filtered_1000_df.copy(), filtered_400_df.copy()
            
            latest_col_1k = next((c for c in df_1k.columns if c.startswith('▼') and '6周' not in c), None)
            latest_col_400 = next((c for c in df_400.columns if c.startswith('▼') and '6周' not in c), None)
            
            if latest_col_1k and latest_col_400 and '▼6周增減' in df_1k.columns and '▼6周增減' in df_400.columns:
                # 💡 效能救星：不再使用 slow 且耗記憶體的 astype(str).str.replace()，直接用底層 float32 計算！
                cond_1k = (df_1k['▼6周增減'].fillna(0) > 0) & (df_1k[latest_col_1k].fillna(0) > 0)
                base_df = df_1k[cond_1k][['股票代號', '股票名稱', '▼6周增減', latest_col_1k]].copy()
                base_df = base_df.rename(columns={'▼6周增減': '6周增減(一千)', latest_col_1k: f"{latest_col_1k}(一千)"})
                
                cond_400 = (df_400['▼6周增減'].fillna(0) > 0) & (df_400[latest_col_400].fillna(0) > 0)
                df_400_filtered = df_400[cond_400][['股票代號', '▼6周增減', latest_col_400]].copy()
                df_400_filtered = df_400_filtered.rename(columns={'▼6周增減': '6周增減(四百)', latest_col_400: f"{latest_col_400}(四百)"})
                
                resonance_df = pd.merge(base_df, df_400_filtered, on='股票代號', how='inner')
                
                if not resonance_df.empty:
                    if not filtered_600_df.empty:
                        df_600 = filtered_600_df.copy()
                        latest_col_600 = next((c for c in df_600.columns if c.startswith('▼') and '6周' not in c), None)
                        if latest_col_600 and '▼6周增減' in df_600.columns:
                            sub_600 = df_600[['股票代號', '▼6周增減', latest_col_600]].copy()
                            sub_600 = sub_600.rename(columns={'▼6周增減': '6周增減(六百)', latest_col_600: f"{latest_col_600}(六百)"})
                            resonance_df = pd.merge(resonance_df, sub_600, on='股票代號', how='left')
                            
                    if not filtered_800_df.empty:
                        df_800 = filtered_800_df.copy()
                        latest_col_800 = next((c for c in df_800.columns if c.startswith('▼') and '6周' not in c), None)
                        if latest_col_800 and '▼6周增減' in df_800.columns:
                            sub_800 = df_800[['股票代號', '▼6周增減', latest_col_800]].copy()
                            sub_800 = sub_800.rename(columns={'▼6周增減': '6周增減(八百)', latest_col_800: f"{latest_col_800}(八百)"})
                            resonance_df = pd.merge(resonance_df, sub_800, on='股票代號', how='left')

                    # 針對數值欄位填補 0.0，文字欄位保留原本
                    num_cols = resonance_df.select_dtypes(include=['float32', 'float64']).columns
                    resonance_df[num_cols] = resonance_df[num_cols].fillna(0.0)
                    
                    if '股票名稱' in resonance_df.columns: resonance_df = resonance_df.drop_duplicates(subset=['股票代號', '股票名稱'], keep='first')
                    else: resonance_df = resonance_df.drop_duplicates(subset=['股票代號'], keep='first')
                    
                    st.success(f"🔥 極度嚴苛過濾！找到了 **{len(resonance_df)}** 檔同步雙向做多的超級共振標的！")
                    
                    # 💡 畫面防護：統一使用 precision=2，避免 float32 小數點跑版
                    st.dataframe(resonance_df.style.format(precision=2), use_container_width=True, hide_index=True)

                    # --- Treemap 繪圖區塊 ---
                    st.write("---")
                    st.markdown("### 🧩 大股東共振資金聚落板塊")
                    st.caption("過濾出長短線大戶雙向共振名單轉換為產業面積 (排除 ETF/債券)。")
                    
                    if STOCK_DICT:
                        target_color_col = f"{latest_col_1k}(一千)"
                        st.write("")
                        c_opt, c_topn = st.columns([3, 1.5])
                        
                        with c_opt:
                            b5_filter = st.radio("設定排序依據：", ["全部顯示 (預設)", "依 6周增減(一千) 排序", f"依 {target_color_col} 排序"], horizontal=True, key="b5_treemap_filter")
                        with c_topn:
                            top_n = st.selectbox("顯示檔數：", [10, 30, 50, 100], index=2, key="b5_top_n")

                        tm_b5_df = resonance_df.copy()
                        
                        # 💡 效能解放：不需要再做 slow string replace，因為欄位原本就是數字
                        tm_b5_df['數值_6周'] = tm_b5_df['6周增減(一千)']
                        tm_b5_df['數值_最新週'] = tm_b5_df[target_color_col]
                        tm_b5_df['數值_400_最新'] = tm_b5_df[f"{latest_col_400}(四百)"]
                        tm_b5_df['數值_400_6周'] = tm_b5_df['6周增減(四百)']

                        if "6周增減" in b5_filter: tm_b5_df = tm_b5_df.nlargest(top_n, '數值_6周')
                        elif "依 ▼" in b5_filter or "依 最新" in b5_filter or target_color_col in b5_filter: tm_b5_df = tm_b5_df.nlargest(top_n, '數值_最新週')
                        
                        tm_b5_df['產業別'] = tm_b5_df['股票代號'].astype(str).apply(lambda sid: STOCK_DICT.get(sid, {}).get("industry", "ETF / 債券 / 其他"))
                        tm_b5_df['產業別'] = tm_b5_df['產業別'].replace('', 'ETF / 債券 / 其他')
                        
                        b5_excluded_etfs = tm_b5_df[tm_b5_df['產業別'] == 'ETF / 債券 / 其他'].sort_values(by='股票代號').copy()
                        tm_b5_df = tm_b5_df[tm_b5_df['產業別'] != 'ETF / 債券 / 其他']
                        
                        if not tm_b5_df.empty:
                            tm_b5_df['計數'] = 1 
                            today_counts = tm_b5_df['產業別'].value_counts().to_dict()

                            def format_industry_label(industry):
                                t_count = today_counts.get(industry, 0)
                                return f"<b>{industry}</b><br><span style='font-size: 13px;'>{t_count}檔</span>"
                            tm_b5_df['產業別'] = tm_b5_df['產業別'].apply(format_industry_label)

                            tm_b5_df['熱力數值'] = tm_b5_df['數值_最新週']

                            tm_b5_df['千張週增減_格式化'] = tm_b5_df['數值_最新週'].apply(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")
                            tm_b5_df['6周一千_格式化'] = tm_b5_df['數值_6周'].apply(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")
                            tm_b5_df['四百最新_格式化'] = tm_b5_df['數值_400_最新'].apply(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")
                            tm_b5_df['6周四百_格式化'] = tm_b5_df['數值_400_6周'].apply(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")

                            def format_clean_stock_label(row):
                                name = str(row.get('股票名稱', ''))
                                if "6周增減" in b5_filter: return f"<b>{name}</b><br><span style='font-size: 11px; color: #E5E7EB;'>6周: {row.get('6周一千_格式化', '0.00%')}</span>"
                                else: return f"<b>{name}</b><br><span style='font-size: 11px; color: #E5E7EB;'>大戶週增 {row.get('千張週增減_格式化', '0.00%')}</span>"
                                
                            tm_b5_df['顯示名稱'] = tm_b5_df.apply(format_clean_stock_label, axis=1)

                            hover_columns = ['股票代號', '千張週增減_格式化', '6周一千_格式化', '四百最新_格式化', '6周四百_格式化']
                            custom_continuous_scale = [[0.0, "rgba(0, 230, 118, 0.85)"], [0.5, "rgba(30, 41, 59, 0.95)"], [1.0, "rgba(255, 75, 75, 0.85)"]]

                            fig = px.treemap(
                                tm_b5_df, path=[px.Constant("🔥 大股東雙向共振池"), '產業別', '顯示名稱'], 
                                values='計數', color='熱力數值', color_continuous_scale=custom_continuous_scale, 
                                color_continuous_midpoint=0, hover_data=hover_columns
                            )
                            fig.update_coloraxes(showscale=False)
                            fig.update_traces(
                                textinfo="label", textfont=dict(color="white", size=14),
                                marker=dict(line=dict(color='#0B0F19', width=2), pad=dict(t=35, l=10, r=10, b=10)),
                                hovertemplate=(
                                    '<b>%{label}</b><br>股票代號: %{customdata[0]}<br>'
                                    '千張大戶本週: <b>%{customdata[1]}</b><br>千張大戶6週累積: <b>%{customdata[2]}</b><br>'
                                    '----------------<br>400張大戶本週: %{customdata[3]}<br>'
                                    '400張大戶6週累積: <b>%{customdata[4]}</b><br><extra></extra>' 
                                )
                            )
                            fig.update_layout(margin=dict(t=30, l=0, r=0, b=0), height=650, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(family="sans-serif"))
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("⚪ 目前過濾後的名單中沒有一般產業的股票。")

                        # 剔除的 ETF 清單
                        if not b5_excluded_etfs.empty:
                            st.write("")
                            st.markdown("##### 🗑️ 本次已剔除的非一般產業 (ETF / 特別股 / 債券)")
                            st.caption("游標懸停可查看大戶持股明細。")
                            tags_html = ""
                            
                            for _, r in b5_excluded_etfs.iterrows():
                                name, sid = html.escape(str(r.get('股票名稱', '')), quote=True), html.escape(str(r.get('股票代號', '')), quote=True)
                                # 💡 直接存取原本已經是 float 的數值
                                num_6w = float(r.get('6周增減(一千)', 0.0))
                                num_w = float(r.get(target_color_col, 0.0))
                                num_400_w = float(r.get(f"{latest_col_400}(四百)", 0.0))
                                num_400_6w = float(r.get('6周增減(四百)', 0.0))
                                
                                if "6周增減" in b5_filter: d_val, label_text = num_6w, "6周"
                                else: d_val, label_text = num_w, "千張"
                                
                                if d_val > 0: bg_color, border_color, text_color, d_str = "rgba(255, 75, 75, 0.15)", "rgba(255, 75, 75, 0.4)", "#FF4B4B", f"+{d_val:.2f}%"
                                elif d_val < 0: bg_color, border_color, text_color, d_str = "rgba(0, 230, 118, 0.15)", "rgba(0, 230, 118, 0.4)", "#00E676", f"{d_val:.2f}%"
                                else: bg_color, border_color, text_color, d_str = "rgba(30, 41, 59, 0.6)", "#334155", "#94A3B8", "0.00%"
                                
                                tooltip_text = (f"【{name}】&#10;股票代號: {sid}&#10;千張大戶本週: {num_w:+.2f}%&#10;千張大戶6週累積: {num_6w:+.2f}%&#10;"
                                                f"----------------&#10;400張中實戶本週: {num_400_w:+.2f}%&#10;400張中實戶6週累積: {num_400_6w:+.2f}%")
                                
                                tags_html += f"<div title=\"{tooltip_text}\" style=\"background-color: {bg_color}; color: #E2E8F0; border: 1px solid {border_color}; padding: 6px 14px; border-radius: 20px; margin: 5px; display: inline-flex; align-items: center; font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); cursor: help; transition: transform 0.2s;\">{name} ({sid}) <span style='color: {text_color}; font-weight: bold; margin-left: 8px;'>{label_text} {d_str}</span></div>"
                            
                            st.markdown(f"<div style='margin-top: 5px; line-height: 2.4;'>{tags_html}</div>", unsafe_allow_html=True)
                    else:
                        st.info("⚪ 找不到產業字典，無法繪製產業板塊圖。")
                else: st.info("⚪ 條件嚴苛，本週完全沒有同步雙增的標的。")
            else: st.error("⚠️ 資料表欄位解析失敗，請確認前方大戶表中包含 '▼6周增減' 與最新日期。")
        else: st.warning("⚠️ 請確認 1000張 與 400張 資料皆有成功載入。")

    # ================= TAB 2: 雙引擎共振 =================
    with tab_resonance:
        if not filtered_1000_df.empty and not filtered_400_df.empty:
            # 💡 週動態已經是 category，文字過濾可以直接用 pandas 內建
            df1_inc = filtered_1000_df[filtered_1000_df['週動態'].astype(str).str.contains('增', na=False)].copy()
            df2_inc = filtered_400_df[filtered_400_df['週動態'].astype(str).str.contains('增', na=False)].copy()

            df1 = df1_inc.add_suffix(' (千張)').rename(columns={'股票代號 (千張)': '股票代號', '股票名稱 (千張)': '股票名稱'})
            df2 = df2_inc.add_suffix(' (四百)').rename(columns={'股票代號 (四百)': '股票代號', '股票名稱 (四百)': '股票名稱'})

            sync = pd.merge(df1, df2, on=['股票代號', '股票名稱'], how='inner')

            if not sync.empty:
                date_bases = set()
                for c in sync.columns:
                    match = re.search(r'(?:▼)?(\d{4})', c)
                    if match: date_bases.add(match.group(1))

                sorted_dates = sorted(list(date_bases), reverse=True)
                cols_order = ['股票代號', '股票名稱']

                if '週動態 (千張)' in sync.columns: cols_order.append('週動態 (千張)')
                if '週動態 (四百)' in sync.columns: cols_order.append('週動態 (四百)')
                if '▼6周增減 (千張)' in sync.columns: cols_order.append('▼6周增減 (千張)')
                if '▼6周增減 (四百)' in sync.columns: cols_order.append('▼6周增減 (四百)')

                for d in sorted_dates:
                    if f"{d}持有% (千張)" in sync.columns: cols_order.append(f"{d}持有% (千張)")
                    if f"{d}持有% (四百)" in sync.columns: cols_order.append(f"{d}持有% (四百)")
                    
                    if f"▼{d} (千張)" in sync.columns: cols_order.append(f"▼{d} (千張)")
                    elif f"{d} (千張)" in sync.columns: cols_order.append(f"{d} (千張)")
                    
                    if f"▼{d} (四百)" in sync.columns: cols_order.append(f"▼{d} (四百)")
                    elif f"{d} (四百)" in sync.columns: cols_order.append(f"{d} (四百)")

                for c in sync.columns:
                    if c not in cols_order: cols_order.append(c)

                sync = sync[cols_order]
                sort_col = next((c for c in sync.columns if '▼' in c and '千張' in c and '持有' not in c and '6周' not in c), None)
                if sort_col: sync = sync.sort_values(by=sort_col, ascending=False)

                st.success(f"這是強烈的大腿訊號！共有 **{len(sync)}** 檔標的出現大腿雷達共振 (千張與四百張同時增加)！")
                # 💡 統一加上 precision=2 避免跑版
                st.dataframe(sync.style.format(precision=2), use_container_width=True, hide_index=True)
            else: st.info("⚪ 最新一週目前沒有「千張與四百張」同時增加的共振標的。")
        else: st.warning("⚠️ 請確保 1000 張與 400 張資料皆有成功載入。")

    # ================= TAB 3-8: 純資料表格 (皆掛上 style.format 防止跑版) =================
    with tab_1000:
        if not filtered_1000_df.empty: st.dataframe(filtered_1000_df.style.format(precision=2), use_container_width=True, hide_index=True)
        else: st.info("⚪ 暫無 1000張大戶資料。")
    with tab_800:
        if not filtered_800_df.empty: st.dataframe(filtered_800_df.style.format(precision=2), use_container_width=True, hide_index=True)
        else: st.info("⚪ 暫無 800張大戶資料。")
    with tab_600:
        if not filtered_600_df.empty: st.dataframe(filtered_600_df.style.format(precision=2), use_container_width=True, hide_index=True)
        else: st.info("⚪ 暫無 600張大戶資料。")
    with tab_400:
        if not filtered_400_df.empty: st.dataframe(filtered_400_df.style.format(precision=2), use_container_width=True, hide_index=True)
        else: st.info("⚪ 暫無 400張大戶資料。")
    with tab_200:
        if not filtered_200_df.empty: st.dataframe(filtered_200_df.style.format(precision=2), use_container_width=True, hide_index=True)
        else: st.info("⚪ 暫無 200張大戶資料。")
    with tab_100:
        if not filtered_100_df.empty: st.dataframe(filtered_100_df.style.format(precision=2), use_container_width=True, hide_index=True)
        else: st.info("⚪ 暫無 100張大戶資料。")


# ==========================================
# 🖼️ 主頁面渲染入口
# ==========================================
def show_b5_page(DATA_DIR, STOCK_DICT):
    """B5 專屬頁面 UI 渲染"""
    if 'b5_1000' not in st.session_state:
        with st.spinner("⏳ 載入大股東籌碼數據中..."):
            sync_b5_data(DATA_DIR)

    st.write("---")
    st.markdown("<div id='section-5'></div>", unsafe_allow_html=True)
    
    global_latest_date = get_b5_latest_date(DATA_DIR)

    st.markdown(f"""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            大腿動向
        </h2>
        <div style='font-size:13px; color:#00D2FF; font-weight:500; margin-top:8px;'>
            資料基準日 : {global_latest_date[:2]}/{global_latest_date[2:]} 
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 💡 呼叫被 Fragment 保護的互動區塊
    render_b5_dashboard(STOCK_DICT)
