# weight_backtest_pagy.py
import pandas as pd
import streamlit as st
import re
import os
import datetime

# ==========================================
# 🌟 導入單一 Master 檔案讀取器
# ==========================================
@st.cache_data(show_spinner=False, ttl=3600)
def load_master_features(data_dir="./data", date_str="20261008"):
    """讀取後台預先計算好的全特徵 Master File"""
    file_path = os.path.join(data_dir, f"{date_str}_master_features")
    
    # 支援讀取 Parquet (建議副檔名加上 .parquet)
    if os.path.exists(file_path + ".parquet"):
        file_path += ".parquet"
        
    try:
        df = pd.read_parquet(file_path)
        # 建立統一代號以利後續操作
        if 'stock_code' in df.columns:
            df['統一代號'] = df['stock_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if 'stock_name' in df.columns:
            df['股票名稱'] = df['stock_name'].astype(str)
        return df
    except Exception as e:
        st.error(f"⚠️ 無法讀取 Master 檔案: {e}")
        return pd.DataFrame()

# ==========================================
# 🚀 局部渲染魔法 1：除錯透視鏡 (極簡化版)
# ==========================================
@st.fragment
def render_debug_panel(filtered_df, any_filter_applied):
    """因為所有特徵已在同一張表，直接展示即可，徹底免除 Merge 記憶體消耗"""
    if any_filter_applied:
        st.success(f"✅ 過濾完成！共有 **{len(filtered_df)}** 檔標的符合您的跨模組條件。")
        if st.checkbox("🔬 展開過濾名單", key="debug_mode_chk"):
            # 排除掉系統不需要顯示的索引或隱藏欄位
            cols_to_hide = ['_num']
            display_cols = [c for c in filtered_df.columns if c not in cols_to_hide]
            
            st.write(f"🔍 檢核明細 (共 {len(filtered_df)} 筆)：")
            st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)
            st.session_state['debug_df'] = filtered_df 
    else:
        st.info("👆 請在上方展開模組中至少設定一項條件，目前預設顯示全市場標的。")

# ==========================================
# 🚀 局部渲染魔法 2：計分展示與寫入功能
# ==========================================
@st.fragment
def render_result_and_save_panel():
    if st.session_state.get('score_calculated', False) and 'scored_result' in st.session_state:
        result_df = st.session_state['scored_result']
        st.write("---")
        st.markdown(f"### 🏆 策略計分結果 (共 {len(result_df)} 檔獲取分數)")
        
        if not result_df.empty:
            # 若無產業別欄位給予預設值
            if '產業別' not in result_df.columns:
                result_df['產業別'] = '未分類'
                
            display_df = result_df[['統一代號', '股票名稱', '產業別', '總分', '得分明細']].rename(columns={'統一代號': '股票代號'})
            display_df.insert(0, '寫入追蹤 (本週上限3檔)', False)
            
            st.caption("💡 勾選下方『寫入追蹤』，即可將該檔標的存入歷史模型庫中，並在「建立名單」中觀察。")
            edited_df = st.data_editor(
                display_df,
                column_config={
                    "寫入追蹤 (本週上限3檔)": st.column_config.CheckboxColumn("寫入追蹤", help="勾選欲寫入追蹤系統的標的", default=False),
                    "總分": st.column_config.NumberColumn("總分", format="%.1f")
                },
                disabled=["股票代號", "股票名稱", "產業別", "總分", "得分明細"],
                hide_index=True, use_container_width=True, key="editor_save_track"
            )
            
            selected_rows = edited_df[edited_df['寫入追蹤 (本週上限3檔)'] == True]
            st.write("---")
            col_save1, col_save2 = st.columns([1, 1])
            with col_save1: st.markdown(f"#### 💾 儲存今日策略模型 (已勾選 {len(selected_rows)} 檔)")
            
            with col_save2:
                if st.button("寫入模擬追蹤 (導覽登入)", icon=":material/database:", use_container_width=True, type="primary"):
                    if not st.session_state.get("logged_in", False):
                        st.error("⚠️ 守衛：「寫入追蹤清單需要綁定帳號！正在為您導向登入頁面...」")
                        import time
                        time.sleep(1.5) 
                        st.query_params["page"] = "login"
                        st.rerun()
                    else:
                        username = st.session_state.get("username", "guest")
                        with st.spinner("寫入中..."):
                            try:
                                from streamlit_gsheets import GSheetsConnection
                                conn = st.connection("gsheets", type=GSheetsConnection)
                                SHEET_URL = "https://docs.google.com/spreadsheets/d/1TxHDahg8ul6lmUtDN-7X75cBXbkU0jaZ3M9zg6exBgU/edit?gid=687268023#gid=687268023"                                 
                                track_date = datetime.datetime.now().strftime("%Y-%m-%d")
                                monday_str = (datetime.datetime.now() - datetime.timedelta(days=datetime.datetime.now().weekday())).strftime("%Y-%m-%d")
                                
                                try: old_track = conn.read(spreadsheet=SHEET_URL, worksheet="實驗室模型追蹤", ttl=0).dropna(how="all")
                                except: old_track = pd.DataFrame(columns=['鎖定日期', '代號', '名稱', '鎖定收盤價', '總分', '得分明細', '當下策略特徵', '追蹤狀態', '帳號'])
                                
                                if '帳號' not in old_track.columns: old_track['帳號'] = ""
                                this_week_count = 0
                                
                                if not old_track.empty:
                                    user_mask = old_track['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower() == str(username).strip().lower()
                                    this_week_data = old_track[(pd.to_datetime(old_track['鎖定日期'], errors='coerce') >= pd.to_datetime(monday_str)) & user_mask]
                                    this_week_count = len(this_week_data)
                                    
                                if this_week_count + len(selected_rows) > 3:
                                    st.error(f"冒險者：每週最多只能存取 3 檔標的！您本週已存取 {this_week_count} 檔，已達上限。")
                                else:
                                    save_targets = selected_rows.copy()
                                    save_targets['鎖定日期'] = track_date
                                    save_targets['帳號'] = username 
                                    
                                    # 🚀 高效抓取價格對應 (從 result_df 取)
                                    price_dict = dict(zip(result_df['統一代號'], pd.to_numeric(result_df['成交'].astype(str).str.replace(',', ''), errors='coerce').fillna(0.0)))
                                    
                                    save_targets['鎖定收盤價'] = save_targets['股票代號'].map(price_dict).fillna(0.0)
                                    save_targets['追蹤狀態'] = "追蹤中"
                                    
                                    debug_df_global = st.session_state.get('debug_df', pd.DataFrame())
                                    save_targets['當下策略特徵'] = "無詳細特徵紀錄 (未開啟除錯透視鏡)"
                                    if not debug_df_global.empty:
                                        cols_keep = [c for c in debug_df_global.columns if c not in ['統一代號', '股票名稱', '產業別', '總分', '得分明細']]
                                        for idx, row in save_targets.iterrows():
                                            matched = debug_df_global[debug_df_global['統一代號'] == row['股票代號']]
                                            if not matched.empty:
                                                features = [f"{col}:{str(matched[col].iloc[0])}" for col in cols_keep if str(matched[col].iloc[0]) not in ['nan', 'None', '']]
                                                save_targets.at[idx, '當下策略特徵'] = " | ".join(features)[:1000]
                                                
                                    final_save_df = save_targets[['鎖定日期', '股票代號', '股票名稱', '鎖定收盤價', '總分', '得分明細', '當下策略特徵', '追蹤狀態', '帳號']].rename(columns={'股票代號': '代號', '股票名稱': '名稱'})
                                    final_save_df = final_save_df.drop_duplicates(subset=['鎖定日期', '代號', '帳號'])
                                    
                                    if not old_track.empty:
                                        curr_acc = old_track['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower()
                                        curr_code = old_track['代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                                        for _, r in final_save_df.iterrows():
                                            old_track = old_track[~((old_track['鎖定日期'].astype(str).str.strip() == str(r['鎖定日期']).strip()) & (curr_code == str(r['代號']).strip()) & (curr_acc == str(username).strip().lower()))]
                                            
                                    conn.update(spreadsheet=SHEET_URL, worksheet="實驗室模型追蹤", data=pd.concat([old_track, final_save_df], ignore_index=True))
                                    st.cache_data.clear()
                                    
                                    if 'pending_watchlist_adds' not in st.session_state: st.session_state['pending_watchlist_adds'] = []
                                    st.session_state['pending_watchlist_adds'].extend([f"{r['代號']} {r['名稱']}" for _, r in final_save_df.iterrows() if f"{r['代號']} {r['名稱']}" not in st.session_state['pending_watchlist_adds']])
                                    
                                    st.success(f"✅ 成功將 {len(selected_rows)} 檔標的寫入模型驗證庫！(本週已使用 {this_week_count + len(selected_rows)}/3 扣打)")
                            except Exception as e:
                                st.error(f"❌ 寫入失敗：{e}。請確認 Google Sheets 連線是否正常。")


# ==========================================
# 🌟 主程式 Entry Point
# ==========================================
def show_weight_backtest_page(STOCK_DICT, DATA_DIR="data"):
    # 載入單一 Master File
    master_df = load_master_features(DATA_DIR, "20261008")
    if master_df.empty:
        return
        
    st.markdown("""
    <div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); 
                border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; 
                border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;">
        <h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">
            籌碼選股寶庫
        </h2>
    </div>
    """, unsafe_allow_html=True)
    st.caption("打造專屬於自己的選股邏輯，透過多重條件交集或聯集與大數據計分，找出最具爆發力的潛力股。")
    st.write("---")

    # 1. 第一關：過濾器面版
    col_title, col_reset = st.columns([3, 1])
    with col_title: st.markdown(f"#### 1️⃣ 設定嚴格過濾條件 (目前總候選池共 {len(master_df)} 檔)")
    with col_reset:
        def reset_filters():            
            for k in ['b0_vol', 'b0_amt', 'b0_per', 'b0_explode_ratio', 'b8_day_streak', 'b8_week_streak', 'b8_buy_vol_min', 'b8_top15_money', 'b8_tofu_money', 'b6_amt_min']: 
                st.session_state[f'filter_{k}'] = 0
            
            slider_defaults = {
                'filter_b0_price': (0.0, 25000.0),
                'filter_b0_pct': (-10.0, 10.0),
                'filter_b1_ratio': (0.0, 100.0),
                'filter_b1_5d_chg': (-100.0, 100.0),
                'filter_b1_20d_chg': (-100.0, 100.0),
                'filter_b1_60d_chg': (-100.0, 100.0),
                'filter_b1_120d_chg': (-100.0, 100.0),
                'filter_b4_price_chg': (-10.0, 10.0),
                'filter_b7_hold_pct': (0.0, 100.0),
                'filter_b7_pledge_pct': (0.0, 100.0),
                'filter_b8_tofu_bias': (-30.0, 30.0)
            }
            for k, v in slider_defaults.items():
                st.session_state[k] = v
                
            for k in ['b1_radio', 'b2_radio', 'b3_radio', 'b4_radio']: 
                st.session_state[f'filter_{k}'] = "交集 (必須同時符合勾選的所有特徵)"
                
            for k in ['b1_delta', 'b1_5d', 'b1_20d', 'b1_60d', 'b1_120d', 'b2_1', 'b2_2', 'b2_3', 'b2_4', 'b3_fo_day', 'b3_it_day', 'b3_fo_wk', 'b3_it_wk', 'b6_today', 'b7_6m_inc', 'b8_mom_slope'] + [f'b4_{x}' for x in ['pct_41', 'vol_41', 'pct_42', 'vol_42', 'pct_43', 'vol_43', 'pct_inc_margin', 'pct_inc_short', 'amt_short_dec', 'amt_short_inc', 'acc_margin_dec', 'acc_sbl_dec', 'acc_margin_inc', 'acc_sbl_inc']] + [f'b5_{x}' for x in ['long_short', 'double', '6w_1000', '6w_800', '6w_600', '6w_400']]: 
                st.session_state[f'filter_{k}'] = False
                
            for k in ['b0_vp_status', 'b0_fund_trend', 'b1_multi', 'b2_multi', 'b3_multi', 'b4_multi', 'b5_trend_1000', 'b5_trend_800', 'b5_trend_600', 'b5_trend_400', 'b6_status', 'b7_hold_trend', 'b7_pledge_trend', 'b8_top15_trend', 'b8_tofu_trend', 'b8_mom_period', 'b8_mom_trend']: 
                st.session_state[f'filter_{k}'] = []
                
            st.session_state['filter_b2_top_n'] = st.session_state['filter_b4_top_n'] = 50
        st.button("清空過濾條件", icon=":material/ink_eraser:", on_click=reset_filters, use_container_width=True)

    # ==========================================
    # 面板與過濾條件接收
    # ==========================================
    with st.expander("💰 B0 量價掃描過濾", expanded=False):
        c1, c2 = st.columns(2)
        b0_vol_min = c1.number_input("📈 當日成交張數大於 (張)：", 0, value=0, step=500, key="filter_b0_vol")
        b0_amt_min = c2.number_input("💵 當日成交額大於 (百萬)：", 0.0, value=0.0, step=50.0, key="filter_b0_amt")
        c3, c4 = st.columns(2)
        b0_price_range = c3.slider("🎯 股價區間 (元)：", 0.0, 25000.0, (0.0, 25000.0), 10.0, key="filter_b0_price")
        b0_pct_range = c4.slider("🚀 當日漲跌幅區間 (%)：", -10.0, 10.0, (-10.0, 10.0), 0.5, key="filter_b0_pct")
        c5, c6 = st.columns(2)
        b0_per_max = c5.number_input("⚖️ 本益比 (PER) 小於：", 0.0, value=0.0, step=5.0, key="filter_b0_per")
        b0_exclude_loss = c6.checkbox("🚫 排除虧損公司", key="filter_b0_exclude_loss")
        b0_vp_status = st.multiselect("🎯 可複選量價型態：", ["🚀 放量大漲", "🔒 縮量大漲", "✈️ 平量大漲", "📈 價升量縮", "⚠️ 放量滯漲", "⏸️ 平量滯漲", "📉 縮量小跌", "🛡️ 放量小跌", "🥀 平量價縮", "☠️ 縮量大跌", "🩸 放量大跌", "🕳️ 平量大跌"], key="filter_b0_vp_status")
        c7, c8 = st.columns(2)
        b0_explode_ratio = c7.number_input("🚀 今日成交額大於【5日均額】的倍數：", 0.0, value=0.0, step=0.5, key="filter_b0_explode_ratio")
        b0_fund_trend = c8.multiselect("📈 資金延續狀態：", ["🔥 資金湧入 (延續性強)", "⚡ 單日點火 (需觀察)", "💧 資金退潮 (動能弱)", "⚖️ 震盪換手"], key="filter_b0_fund_trend")
    
    with st.expander("📈 B1 法人動向過濾", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        b1_delta, b1_5d, b1_20d, b1_60d, b1_120d = c1.checkbox("當日△上升 (>0)", key="filter_b1_delta"), c2.checkbox("🔴 5日上榜", key="filter_b1_5d"), c3.checkbox("🟡 20日上榜", key="filter_b1_20d"), c4.checkbox("🟢 60日上榜", key="filter_b1_60d"), c5.checkbox("🔵 120日上榜", key="filter_b1_120d")
        b1_ratio_min, b1_ratio_max = st.slider("法人持股比例區間 (%)：", 0.0, 100.0, (0.0, 100.0), 0.5, key="filter_b1_ratio")
        c_chg1, c_chg2 = st.columns(2)
        with c_chg1: b1_5d_chg, b1_60d_chg = st.slider("5日 ΔChange", -100.0, 100.0, (-100.0, 100.0), 0.5, key="filter_b1_5d_chg"), st.slider("60日 ΔChange", -100.0, 100.0, (-100.0, 100.0), 0.5, key="filter_b1_60d_chg")
        with c_chg2: b1_20d_chg, b1_120d_chg = st.slider("20日 ΔChange", -100.0, 100.0, (-100.0, 100.0), 0.5, key="filter_b1_20d_chg"), st.slider("120日 ΔChange", -100.0, 100.0, (-100.0, 100.0), 0.5, key="filter_b1_120d_chg")
        b1_trend_logic = st.radio("特徵篩選邏輯：", ["交集 (必須同時符合勾選的所有特徵)", "聯集 (符合其中任一特徵即可)"], horizontal=True, key="filter_b1_radio")
        b1_trends = st.multiselect("請選擇要過濾的動態特徵：", ["📈 上升", "📉 下降", "🪜 階梯吸籌", "🛡️ 穩健吸籌", "⚠️ 趨緩", "🚀 衝進🔴5日榜單", "🚀 衝進🟡20日榜單", "🚀 衝進🟢60日榜單", "🚀 衝進🔵120日榜單"], key="filter_b1_multi")

    with st.expander("🚀 B2 法人掃貨過濾", expanded=False):
        b2_top_n = st.slider("👑 排名過濾", 10, 300, 50, 10, key="filter_b2_top_n")
        c1, c2 = st.columns(2)
        b2_1_chk, b2_3_chk = c1.checkbox(f"外資買超佔【5日成交量】(前 {b2_top_n} 名)", key="filter_b2_1"), c1.checkbox(f"外資買超佔【5日發行數】(前 {b2_top_n} 名)", key="filter_b2_3")
        b2_2_chk, b2_4_chk = c2.checkbox(f"投信買超佔【5日成交量】(前 {b2_top_n} 名)", key="filter_b2_2"), c2.checkbox(f"投信買超佔【5日發行數】(前 {b2_top_n} 名)", key="filter_b2_4")
        b2_trend_logic = st.radio("B2 特徵篩選邏輯：", ["交集 (必須同時符合勾選特徵)", "聯集 (符合任一即可)"], horizontal=True, key="filter_b2_radio")
        b2_trend_display_map = {"🔥 強延續": "🔥 強延續", "🔥 持續加碼": "🔥 持續加碼", "🆕 今日突擊卡位": "🆕 今日突擊卡位", "⚠️ 趨緩": "⚠️ 趨緩", "🔄 持平": "🔄 持平", "🔄 今日量縮持平": "🔄 今日量縮持平", "📉 調節洗盤": "📉 調節洗盤", "💤 籌碼沉澱中": "💤 籌碼沉澱中", "🚨 轉賣反轉": "🚨 轉賣反轉", "🚨 劇烈倒貨": "🚨 劇烈倒貨", "⚪ 觀望": "⚪ 觀望"}
        b2_trends = [raw for d in st.multiselect("可複選突擊動態：", list(b2_trend_display_map.values()), key="filter_b2_multi") for raw, desc in b2_trend_display_map.items() if d == desc]

    with st.expander("🔥 B3 法人連買過濾", expanded=False):
        c1, c2, c3, c4 = st.columns([1.2, 1, 1.2, 1])
        b3_fo_day_chk, b3_fo_day_n = c1.checkbox("🌐 外資日連買", key="filter_b3_fo_day"), c2.number_input("連買大於(天)", 1, value=1, step=1, key="filter_b3_fo_day_n", label_visibility="collapsed")
        b3_it_day_chk, b3_it_day_n = c3.checkbox("🏦 投信日連買", key="filter_b3_it_day"), c4.number_input("連買大於(天)", 1, value=1, step=1, key="filter_b3_it_day_n", label_visibility="collapsed")
        c5, c6, c7, c8 = st.columns([1.2, 1, 1.2, 1])
        b3_fo_wk_chk, b3_fo_wk_n = c5.checkbox("🌐 外資週連買", key="filter_b3_fo_wk"), c6.number_input("連買大於(週)", 1, value=1, step=1, key="filter_b3_fo_wk_n", label_visibility="collapsed")
        b3_it_wk_chk, b3_it_wk_n = c7.checkbox("🏦 投信週連買", key="filter_b3_it_wk"), c8.number_input("連買大於(週)", 1, value=1, step=1, key="filter_b3_it_wk_n", label_visibility="collapsed")
        b3_trend_logic = st.radio("B3 特徵篩選邏輯：", ["交集 (必須同時符合勾選特徵)", "聯集 (符合任一即可)"], horizontal=True, key="filter_b3_radio")
        b3_trends = [t.split(" (")[0] for t in st.multiselect("可複選連買動態：", ["🔥 波段認養 (日連買10天以上)", "⚡ 買盤點火 (日連買5~9天)", "🆕 試單觀察 (日連買1~4天)", "👑 長線主控 (週連買10週以上)", "🚀 趨勢加溫 (週連買5~9週)", "🌱 週線發動 (週連買1~4週)"], key="filter_b3_multi")]

    with st.expander("⚔️ B4 資券動向過濾", expanded=False):
        b4_top_n = st.slider("👑 B4 排名過濾", 10, 300, 50, 10, key="filter_b4_top_n")
        c1, c2 = st.columns(2)
        b4_41_pct, b4_42_pct, b4_43_pct, b4_inc_margin_pct, b4_short_dec_amt = c1.checkbox("融資減少幅度", key="filter_b4_pct_41"), c1.checkbox("借券賣出減少幅度", key="filter_b4_pct_42"), c1.checkbox("融券增加幅度", key="filter_b4_pct_43"), c1.checkbox("融資增加幅度", key="filter_b4_pct_inc_margin"), c1.checkbox("借券減少金額", key="filter_b4_amt_short_dec")
        b4_41_vol, b4_42_vol, b4_43_vol, b4_inc_short_pct, b4_short_inc_amt = c2.checkbox("融資減少張數", key="filter_b4_vol_41"), c2.checkbox("借券賣出減少張數", key="filter_b4_vol_42"), c2.checkbox("融券增加張數", key="filter_b4_vol_43"), c2.checkbox("借券賣出增加幅度", key="filter_b4_pct_inc_short"), c2.checkbox("借券增加金額", key="filter_b4_amt_short_inc")
        b4_price_chg = st.slider("設定漲跌幅區間：", -10.0, 10.0, (-10.0, 10.0), 0.5, key="filter_b4_price_chg")
        b4_trend_logic = st.radio("B4 特徵篩選邏輯：", ["交集 (必須同時符合勾選特徵)", "聯集 (符合任一即可)"], horizontal=True, key="filter_b4_radio")
        b4_trend_display_map = {"💥 終極": "💥 終極", "🚀 強軋": "🚀 強軋", "🔥 點火": "🔥 點火", "🔼 進駐": "🔼 進駐", "☠️ 極危": "☠️ 極危", "🚨 高危": "🚨 高危", "⚠️ 初危": "⚠️ 初危"}
        b4_trends = [raw for d in st.multiselect("可複選雷達特徵：", list(b4_trend_display_map.values()), key="filter_b4_multi") for raw, desc in b4_trend_display_map.items() if d == desc]

    with st.expander("🐳 B5 大戶波段過濾", expanded=False):
        c1, c2 = st.columns(2)
        b5_long_short, b5_double = c1.checkbox("🎯 長短線共振", key="filter_b5_long_short"), c2.checkbox("🎯 雙引擎共振", key="filter_b5_double")
        c3, c4, c5, c6 = st.columns(4)
        b5_6w_1000, b5_6w_800, b5_6w_600, b5_6w_400 = c3.checkbox("👑 1000張", key="filter_b5_6w_1000"), c4.checkbox("🦅 800張", key="filter_b5_6w_800"), c5.checkbox("🦉 600張", key="filter_b5_6w_600"), c6.checkbox("🐺 400張", key="filter_b5_6w_400")
        trend_opts = ["🚀 劇增", "🔥 大增", "📈 小增", "↗️ 微增", "🔄 持平", "↘️ 微減", "📉 小減", "⚠️ 大減", "🚨 劇減"]
        c7, c8 = st.columns(2)
        b5_trend_1000, b5_trend_800 = c7.multiselect("👑 1000張大戶週動態：", trend_opts, key="filter_b5_trend_1000"), c8.multiselect("🦅 800張大戶週動態：", trend_opts, key="filter_b5_trend_800")
        c9, c10 = st.columns(2)
        b5_trend_600, b5_trend_400 = c9.multiselect("🦉 600張大戶週動態：", trend_opts, key="filter_b5_trend_600"), c10.multiselect("🐺 400張大戶週動態：", trend_opts, key="filter_b5_trend_400")

    with st.expander("💎 B6 鉅額交易過濾", expanded=False):
        b6_today_chk = st.checkbox("🎯 今日有發生鉅額交易", key="filter_b6_today")
        b6_amt_min = st.slider("💰 鉅額總額大於 (億)：", 0.0, 50.0, 0.0, 0.5, key="filter_b6_amt_min")
        b6_status_chk = st.multiselect("防線狀態：", ["🛡️ 防守成功 (收盤 >= 鉅額均價)", "🚨 跌破防線 (收盤 < 鉅額均價)"], key="filter_b6_status")

    with st.expander("👔 B7 董監動向過濾", expanded=False):
        c1, c2 = st.columns(2)
        b7_hold_pct = c1.slider("🛡️ 董監持股比例區間：", 0.0, 100.0, (0.0, 100.0), 0.5, key="filter_b7_hold_pct")
        b7_pledge_pct = c2.slider("⚠️ 董監質押比例區間：", 0.0, 100.0, (0.0, 100.0), 0.5, key="filter_b7_pledge_pct")
        c3, c4 = st.columns(2)
        b7_hold_trend = c3.multiselect("🛡️ 持股增減動態：", ["🔥 大增", "📈 增", "↗️ 微增", "🔄 持平", "↘️ 微減", "🚨 減/大減"], key="filter_b7_hold_trend")
        b7_pledge_trend = c4.multiselect("⚠️ 質押增減動態：", ["🚨 暴增", "⚠️ 大增", "↗️ 微增", "➖ 持平", "↘️ 微減", "✅ 大減", "🌟 遽減"], key="filter_b7_pledge_trend")
        b7_6m_inc = st.checkbox("🎯 近半年董監波段持股增加 (> 0)", key="filter_b7_6m_inc")


    # ==========================================
    # 執行向量化過濾邏輯 (Vectorized DataFrame Filtering)
    # ==========================================
    mask = pd.Series(True, index=master_df.index)
    any_filter_applied = False

    # --- B0 過濾 ---
    if b0_vol_min > 0: mask &= (master_df['成交張數_num'] >= b0_vol_min); any_filter_applied = True
    if b0_amt_min > 0: mask &= (master_df['今日成交額(萬)'] >= b0_amt_min * 100); any_filter_applied = True
    if b0_price_range[0] > 0 or b0_price_range[1] < 25000: mask &= master_df['成交'].between(*b0_price_range); any_filter_applied = True
    if b0_pct_range[0] > -10 or b0_pct_range[1] < 10: mask &= master_df['漲跌幅'].between(*b0_pct_range); any_filter_applied = True
    if b0_per_max > 0: mask &= (master_df['PER'] > 0) & (master_df['PER'] <= b0_per_max); any_filter_applied = True
    if b0_exclude_loss: mask &= (master_df['PER'] > 0); any_filter_applied = True
    if b0_vp_status: mask &= master_df['B0_量價狀態'].isin(b0_vp_status); any_filter_applied = True
    if b0_explode_ratio > 0: mask &= (master_df['5日爆發倍數'] >= b0_explode_ratio); any_filter_applied = True
    if b0_fund_trend: mask &= master_df['資金延續趨勢'].isin(b0_fund_trend); any_filter_applied = True

    # --- B1 過濾 ---
    if b1_delta: mask &= (master_df['B1_1日△Change'] > 0); any_filter_applied = True
    if b1_5d: mask &= master_df['B1_正向上榜區塊'].astype(str).str.contains('5日'); any_filter_applied = True
    if b1_20d: mask &= master_df['B1_正向上榜區塊'].astype(str).str.contains('20日'); any_filter_applied = True
    if b1_60d: mask &= master_df['B1_正向上榜區塊'].astype(str).str.contains('60日'); any_filter_applied = True
    if b1_120d: mask &= master_df['B1_正向上榜區塊'].astype(str).str.contains('120日'); any_filter_applied = True
    if b1_ratio_min > 0 or b1_ratio_max < 100: mask &= master_df['B1_正向_法人持股(%)'].between(b1_ratio_min, b1_ratio_max); any_filter_applied = True
    if b1_5d_chg[0] > -100 or b1_5d_chg[1] < 100: mask &= master_df['B1_5日△Change'].between(*b1_5d_chg); any_filter_applied = True
    if b1_20d_chg[0] > -100 or b1_20d_chg[1] < 100: mask &= master_df['B1_20日△Change'].between(*b1_20d_chg); any_filter_applied = True
    if b1_60d_chg[0] > -100 or b1_60d_chg[1] < 100: mask &= master_df['B1_60日△Change'].between(*b1_60d_chg); any_filter_applied = True
    if b1_120d_chg[0] > -100 or b1_120d_chg[1] < 100: mask &= master_df['B1_120日△Change'].between(*b1_120d_chg); any_filter_applied = True
    if b1_trends:
        any_filter_applied = True
        is_and = "交集" in b1_trend_logic
        t_mask = pd.Series(True if is_and else False, index=master_df.index)
        for t in b1_trends:
            cond = master_df['B1_法人軌跡動態'].astype(str).str.contains(t)
            t_mask = (t_mask & cond) if is_and else (t_mask | cond)
        mask &= t_mask

    # --- B2 過濾 ---
    b2_mask = pd.Series(False, index=master_df.index)
    if b2_1_chk: b2_mask |= (master_df['B2_外資_當日佔成交(%)'] > 0); any_filter_applied = True
    if b2_2_chk: b2_mask |= (master_df['B2_投信_當日佔成交(%)'] > 0); any_filter_applied = True
    if b2_3_chk: b2_mask |= (master_df['B2_外資_當日佔發行(%)'] > 0); any_filter_applied = True
    if b2_4_chk: b2_mask |= (master_df['B2_投信_當日佔發行(%)'] > 0); any_filter_applied = True
    if any([b2_1_chk, b2_2_chk, b2_3_chk, b2_4_chk]): mask &= b2_mask

    if b2_trends:
        any_filter_applied = True
        is_and = "交集" in b2_trend_logic
        t_mask = pd.Series(True if is_and else False, index=master_df.index)
        b2_dyn_cols = ['B2_外資成交動態', 'B2_投信成交動態', 'B2_外資發行動態', 'B2_投信發行動態']
        for t in b2_trends:
            # 在四大區塊中尋找特徵
            cond = pd.Series(False, index=master_df.index)
            for c in b2_dyn_cols:
                if c in master_df.columns:
                    cond |= master_df[c].astype(str).str.contains(t)
            t_mask = (t_mask & cond) if is_and else (t_mask | cond)
        mask &= t_mask

    # --- B3 過濾 ---
    if b3_fo_day_chk: mask &= (master_df['B3_外資連買日數'] >= b3_fo_day_n); any_filter_applied = True
    if b3_it_day_chk: mask &= (master_df['B3_投信連買日數'] >= b3_it_day_n); any_filter_applied = True
    if b3_fo_wk_chk: mask &= (master_df['B3_外資連買週數'] >= b3_fo_wk_n); any_filter_applied = True
    if b3_it_wk_chk: mask &= (master_df['B3_投信連買週數'] >= b3_it_wk_n); any_filter_applied = True
    if b3_trends:
        any_filter_applied = True
        is_and = "交集" in b3_trend_logic
        t_mask = pd.Series(True if is_and else False, index=master_df.index)
        b3_dyn_cols = ['B3_外資日連買動態', 'B3_投信日連買動態', 'B3_外資週連買動態', 'B3_投信週連買動態']
        for t in b3_trends:
            cond = pd.Series(False, index=master_df.index)
            for c in b3_dyn_cols:
                if c in master_df.columns:
                    cond |= master_df[c].astype(str).str.contains(t)
            t_mask = (t_mask & cond) if is_and else (t_mask | cond)
        mask &= t_mask

    # --- B4 過濾 ---
    b4_mask = pd.Series(False, index=master_df.index)
    if b4_41_pct: b4_mask |= (master_df['B4_融資_當日增減(%)'] < 0); any_filter_applied = True
    if b4_41_vol: b4_mask |= (master_df['B4_融資_當日增減(張)'] < 0); any_filter_applied = True
    if b4_42_pct: b4_mask |= (master_df['B4_借券賣出_當日增減(%)'] < 0); any_filter_applied = True
    if b4_42_vol: b4_mask |= (master_df['B4_借券賣出_當日增減(張)'] < 0); any_filter_applied = True
    if b4_43_pct: b4_mask |= (master_df['B4_融券_當日增減(%)'] > 0); any_filter_applied = True
    if b4_43_vol: b4_mask |= (master_df['B4_融券_當日增減(張)'] > 0); any_filter_applied = True
    if b4_inc_margin_pct: b4_mask |= (master_df['B4_融資_當日增減(%)'] > 0); any_filter_applied = True
    if b4_inc_short_pct: b4_mask |= (master_df['B4_借券賣出_當日增減(%)'] > 0); any_filter_applied = True
    if b4_short_dec_amt: b4_mask |= (master_df['B4_借券賣出_當日增減(萬)'] < 0); any_filter_applied = True
    if b4_short_inc_amt: b4_mask |= (master_df['B4_借券賣出_當日增減(萬)'] > 0); any_filter_applied = True
    if any([b4_41_pct, b4_41_vol, b4_42_pct, b4_42_vol, b4_43_pct, b4_43_vol, b4_inc_margin_pct, b4_inc_short_pct, b4_short_dec_amt, b4_short_inc_amt]): mask &= b4_mask
    
    if b4_price_chg[0] > -10 or b4_price_chg[1] < 10: mask &= master_df['漲跌幅'].between(*b4_price_chg); any_filter_applied = True
    if b4_trends:
        any_filter_applied = True
        is_and = "交集" in b4_trend_logic
        t_mask = pd.Series(True if is_and else False, index=master_df.index)
        for t in b4_trends:
            cond = master_df['B4_融資動態'].astype(str).str.contains(t) | master_df['B4_借券賣出動態'].astype(str).str.contains(t) | master_df['B4_融券動態'].astype(str).str.contains(t)
            t_mask = (t_mask & cond) if is_and else (t_mask | cond)
        mask &= t_mask

    # --- B5 過濾 ---
    if b5_long_short: mask &= master_df['B5_大戶共振_雙增'].notna() & master_df['B5_大戶共振_雙增'].astype(str).str.contains('雙增'); any_filter_applied = True
    if b5_double: mask &= master_df['B5_大戶共振_雙增'].notna() & master_df['B5_大戶共振_雙增'].astype(str).str.contains('雙增'); any_filter_applied = True # 可視需求拆分邏輯
    if b5_6w_1000: mask &= (master_df['B5_1千_6週增減(%)'] > 0); any_filter_applied = True
    if b5_6w_800: mask &= (master_df['B5_800_6週增減(%)'] > 0); any_filter_applied = True
    if b5_6w_600: mask &= (master_df['B5_600_6週增減(%)'] > 0); any_filter_applied = True
    if b5_6w_400: mask &= (master_df['B5_400_6週增減(%)'] > 0); any_filter_applied = True
    if b5_trend_1000: mask &= master_df['B5_1千週動態'].isin(b5_trend_1000); any_filter_applied = True
    if b5_trend_800: mask &= master_df['B5_800週動態'].isin(b5_trend_800); any_filter_applied = True
    if b5_trend_600: mask &= master_df['B5_600週動態'].isin(b5_trend_600); any_filter_applied = True
    if b5_trend_400: mask &= master_df['B5_400週動態'].isin(b5_trend_400); any_filter_applied = True

    # --- B6 過濾 ---
    if b6_today_chk: mask &= master_df['B6_鉅額總額(萬)'].notna(); any_filter_applied = True
    if b6_amt_min > 0: mask &= (master_df['B6_鉅額總額(萬)'] >= b6_amt_min * 10000); any_filter_applied = True
    if b6_status_chk: mask &= master_df['B6_防守價位狀態'].isin(b6_status_chk); any_filter_applied = True

    # --- B7 過濾 ---
    if b7_hold_pct[0] > 0 or b7_hold_pct[1] < 100: mask &= master_df['B7_董監最新持股(%)'].between(*b7_hold_pct); any_filter_applied = True
    if b7_pledge_pct[0] > 0 or b7_pledge_pct[1] < 100: mask &= master_df['B7_最新質押比(%)'].between(*b7_pledge_pct); any_filter_applied = True
    if b7_hold_trend: mask &= master_df['B7_董監持股動態'].isin(b7_hold_trend); any_filter_applied = True
    if b7_pledge_trend: mask &= master_df['B7_質押動態'].isin(b7_pledge_trend); any_filter_applied = True
    if b7_6m_inc: mask &= (master_df['B7_董監近半年增減(%)'] > 0) if 'B7_董監近半年增減(%)' in master_df.columns else True; any_filter_applied = True

    filtered_df = master_df[mask].copy()

    # ==========================================
    # 🌟 呼叫 Fragment 1：除錯透視鏡
    # ==========================================
    render_debug_panel(filtered_df, any_filter_applied)

    st.write("---")

    # ==========================================
    # 2. 第二關：自訂權重計分面板
    # ==========================================
    st.markdown("#### 2️⃣ 設定計分權重 (Weights)")
    st.caption("為各項籌碼動向設定加權分數 (設定為 0 代表不計分，負數代表扣分)")
    with st.expander("⚙️ 展開設定各區塊權重", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown("**法人持股動向**"); w_b1_up, w_b1_down, w_b2, w_b3 = st.number_input("法人正向進榜 (次)", value=1.0, step=0.5), st.number_input("法人衰退進榜 (次)", value=-1.0, step=0.5), st.number_input("法人單日突擊掃貨", value=1.5, step=0.5), st.number_input("法人連續買超", value=2.0, step=0.5)
        with c2: st.markdown("**資券籌碼變化**"); w_b4_good, w_b4_short_dec, w_b4_short_inc, w_b4_price_up = st.number_input("融資減/融券增", value=1.0, step=0.5), st.number_input("借券賣出減少", value=2.0, step=0.5), st.number_input("借券賣出增加", value=-1.5, step=0.5), st.number_input("今日大漲(>3%)", value=1.0, step=0.5)
        with c3: st.markdown("**大戶波段防線**"); w_b5, w_b5_800, w_b5_600, w_b5_400 = st.number_input("千張大戶持股增加", value=2.0, step=0.5), st.number_input("800張大戶持股增加", value=2.0, step=0.5), st.number_input("600張大戶持股增加", value=1.5, step=0.5), st.number_input("400張大戶持股增加", value=1.5, step=0.5)
        with c4: st.markdown("**特定資金與董監防線**"); w_b6, w_b7 = st.number_input("鉅額防守成功", value=1.5, step=0.5), st.number_input("董監增持/質押降", value=1.5, step=0.5)

    # ==========================================
    # 3. 執行計分運算 (Scoring Engine) - 🚀 單表向量化版
    # ==========================================
    if st.button("開始計算權重分數", icon=":material/vital_signs:", use_container_width=True):
        with st.spinner("🧠 籌碼大數據融合計算中..."):
            score_df = filtered_df.copy()
            score_df['總分'] = 0.0
            score_df['得分明細'] = ""

            if w_b1_up != 0 and 'B1_正向上榜區塊' in score_df.columns:
                m = score_df['B1_正向上榜區塊'].notna() & (score_df['B1_正向上榜區塊'] != "")
                score_df.loc[m, '總分'] += w_b1_up
                score_df.loc[m, '得分明細'] += f"[法人正向 +{w_b1_up}] "

            if w_b1_down != 0 and 'B1_負向上榜區塊' in score_df.columns:
                m = score_df['B1_負向上榜區塊'].notna() & (score_df['B1_負向上榜區塊'] != "")
                score_df.loc[m, '總分'] += w_b1_down
                score_df.loc[m, '得分明細'] += f"[法人衰退 {w_b1_down}] "

            if w_b2 != 0:
                m = (score_df['B2_外資_當日佔成交(%)'] > 0) | (score_df['B2_投信_當日佔成交(%)'] > 0)
                score_df.loc[m, '總分'] += w_b2
                score_df.loc[m, '得分明細'] += f"[法人掃貨 +{w_b2}] "

            if w_b3 != 0:
                m = (score_df['B3_外資連買日數'].fillna(0) > 0) | (score_df['B3_投信連買日數'].fillna(0) > 0)
                score_df.loc[m, '總分'] += w_b3
                score_df.loc[m, '得分明細'] += f"[法人連買 +{w_b3}] "

            if w_b4_good != 0:
                m = (score_df['B4_融資_當日增減(%)'].fillna(0) < 0) | (score_df['B4_融券_當日增減(%)'].fillna(0) > 0)
                score_df.loc[m, '總分'] += w_b4_good
                score_df.loc[m, '得分明細'] += f"[資券有利 +{w_b4_good}] "

            if w_b4_short_dec != 0:
                m = (score_df['B4_借券賣出_當日增減(張)'].fillna(0) < 0)
                score_df.loc[m, '總分'] += w_b4_short_dec
                score_df.loc[m, '得分明細'] += f"[借券減少 +{w_b4_short_dec}] "

            if w_b4_short_inc != 0:
                m = (score_df['B4_借券賣出_當日增減(張)'].fillna(0) > 0)
                score_df.loc[m, '總分'] += w_b4_short_inc
                score_df.loc[m, '得分明細'] += f"[借券增加 {w_b4_short_inc}] "

            if w_b4_price_up != 0:
                m = (score_df['漲跌幅'].fillna(0) > 3.0)
                score_df.loc[m, '總分'] += w_b4_price_up
                score_df.loc[m, '得分明細'] += f"[大漲>3% +{w_b4_price_up}] "

            if w_b5 != 0:
                m = score_df['B5_1千_6週增減(%)'].fillna(0) > 0
                score_df.loc[m, '總分'] += w_b5; score_df.loc[m, '得分明細'] += f"[千張大戶 +{w_b5}] "
            if w_b5_800 != 0:
                m = score_df['B5_800_6週增減(%)'].fillna(0) > 0
                score_df.loc[m, '總分'] += w_b5_800; score_df.loc[m, '得分明細'] += f"[800張大戶 +{w_b5_800}] "
            if w_b5_600 != 0:
                m = score_df['B5_600_6週增減(%)'].fillna(0) > 0
                score_df.loc[m, '總分'] += w_b5_600; score_df.loc[m, '得分明細'] += f"[600張大戶 +{w_b5_600}] "
            if w_b5_400 != 0:
                m = score_df['B5_400_6週增減(%)'].fillna(0) > 0
                score_df.loc[m, '總分'] += w_b5_400; score_df.loc[m, '得分明細'] += f"[400張大戶 +{w_b5_400}] "

            if w_b6 != 0 and 'B6_防守價位狀態' in score_df.columns:
                m = score_df['B6_防守價位狀態'].astype(str).str.contains("防守成功")
                score_df.loc[m, '總分'] += w_b6; score_df.loc[m, '得分明細'] += f"[鉅額防守 +{w_b6}] "

            if w_b7 != 0:
                m = (score_df['B7_董監近月增減(%)'].fillna(0) > 0) if 'B7_董監近月增減(%)' in score_df.columns else pd.Series(False, index=score_df.index)
                m2 = (score_df['B7_近月質押增減(%)'].fillna(0) < 0) if 'B7_近月質押增減(%)' in score_df.columns else pd.Series(False, index=score_df.index)
                score_df.loc[m | m2, '總分'] += w_b7
                score_df.loc[m | m2, '得分明細'] += f"[董監增持/質押降 +{w_b7}] "

            st.session_state['scored_result'] = score_df[score_df['總分'] != 0].sort_values(by='總分', ascending=False).reset_index(drop=True).copy()
            st.session_state['score_calculated'] = True

    # ==========================================
    # 🌟 呼叫 Fragment 2：結果展示與存檔按鈕
    # ==========================================
    render_result_and_save_panel()
