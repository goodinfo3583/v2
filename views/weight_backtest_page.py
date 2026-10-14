# views/weight_backtest_page.py
import pandas as pd
import streamlit as st
import re
import os
import glob
import datetime
import urllib.parse

# ==========================================
# 🌟 導入 HF Parquet 讀取器 (供 B8 新功能使用)
# ==========================================
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_parquet_from_hf(file_name):
    HF_BASE_URL = "https://huggingface.co/datasets/goodinfo3583/tw-broker-parquet/resolve/main"
    url = f"{HF_BASE_URL}/{urllib.parse.quote(file_name)}"
    try: return pd.read_parquet(url)
    except Exception: return pd.DataFrame()

# ==========================================
# 🌟 讀取 Master Features Parquet (供 B0~B7 全新過濾使用)
# ==========================================
@st.cache_data(show_spinner=False, ttl=3600)
def load_master_features():
    file_path = "20261013_master_features.parquet"
    if os.path.exists(file_path):
        df = pd.read_parquet(file_path)
        # 統一清理代號格式
        if 'stock_code' in df.columns:
            df['統一代號'] = df['stock_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        elif '股票代號' in df.columns:
            df['統一代號'] = df['股票代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        return df
    return pd.DataFrame()

try: from views.b0_page import sync_b0_data
except ImportError:
    def sync_b0_data(DATA_DIR): pass

try: from views.sidebar import ensure_b1_to_b5_loaded
except ImportError:
    def ensure_b1_to_b5_loaded(DATA_DIR): pass

try: from views.b6_page import sync_b6_data
except ImportError:
    def sync_b6_data(DATA_DIR): pass

try: from views.b7_page import sync_b7_data, sync_pledge_data, sync_pledge_history_data
except ImportError:
    def sync_b7_data(DATA_DIR): pass
    def sync_pledge_data(DATA_DIR): pass
    def sync_pledge_history_data(DATA_DIR): pass

try: from views.broker_page import sync_b8_data
except ImportError:
    def sync_b8_data(): pass

# ==========================================
# 🌟 萬能鑰匙：對接全站暫存變數
# ==========================================
KEY_MAP = {
    'b0_price': ['b0_price'], 'b1_final_df': ['b1_final_df', 'my_final_df'], 'b1_down_final_df': ['b1_down_final_df'],
    'b1_foreign_df': ['b1_foreign_df'], 'b2_1': ['b2_1', 'df_blk2_1'], 'b2_2': ['b2_2', 'df_blk2_2'],
    'b2_3': ['b2_3', 'df_blk2_3'], 'b2_4': ['b2_4', 'df_blk2_4'], 'b3_main': ['b3_main', 'df_blk3_main'],
    'b4_margin_pct': ['b4_margin_pct', 'df_margin_pct'], 'b4_short_pct': ['b4_short_pct', 'df_short_pct'],
    'b4_margin_plus_pct': ['b4_margin_plus_pct', 'df_margin_plus_pct'], 'b4_margin_vol': ['b4_margin_vol', 'df_margin_vol'],
    'b4_short_vol': ['b4_short_vol', 'df_short_vol'], 'b4_margin_plus_vol': ['b4_margin_plus_vol', 'df_margin_plus_vol'],
    'b4_margin_inc_pct': ['b4_margin_inc_pct', 'df_margin_inc_pct'], 'b4_short_inc_pct': ['b4_short_inc_pct', 'df_short_inc_pct'],
    'b4_margin_inc_vol': ['b4_margin_inc_vol', 'df_margin_inc_vol'], 'b4_short_inc_vol': ['b4_short_inc_vol', 'df_short_inc_vol'],
    'b4_short_inc_amt': ['b4_short_inc_amt', 'df_short_inc_amt'], 'b4_short_dec_amt': ['b4_short_dec_amt', 'df_short_dec_amt'],
    'b5_1000': ['b5_1000', 'df_blk5_1000', 'df_blk5'], 'b5_800': ['b5_800', 'df_blk5_800'],
    'b5_600': ['b5_600', 'df_blk5_600'], 'b5_400': ['b5_400', 'df_blk5_400'],
    'b5_resonance': ['b5_resonance', 'df_b5_resonance', 'df_resonance', 'df_長短線共振'], 'b5_double': ['b5_double', 'df_b5_double', 'df_double', 'df_雙向共振'],
    'b6_today': ['b6_today', 'b6_today_df'], 'b6_hist': ['b6_hist', 'b6_hist_matrix'],
    'b7_main': ['b7_main', 'df_blk7_main', 'df_b7_main'], 'b7_pledge': ['b7_pledge', 'df_pledge', 'df_b7_pledge'],
    'b7_pledge_history': ['b7_pledge_history', 'df_pledge_history', 'df_b7_pledge_history'], 'b8_summary': ['b8_summary_df']
}

def clean_stock_id(df):
    if not df.empty:
        col_id = '股票代號' if '股票代號' in df.columns else ('代號' if '代號' in df.columns else None)
        if col_id: df['統一代號'] = df[col_id].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    return df

def get_df(primary_key):
    for k in KEY_MAP.get(primary_key, [primary_key]):
        df = st.session_state.get(k)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return clean_stock_id(df.copy())
    return pd.DataFrame()

# ==========================================
# 🚀 局部渲染魔法 1：除錯透視鏡 (保留原始功能)
# ==========================================
def merge_debug_data(base_df, source_df, col_map, prefix=""):
    if source_df.empty: return base_df
    rename_dict = {k: f"{prefix}{v}" for k, v in col_map.items() if k in source_df.columns}
    if not rename_dict: return base_df
    cols_to_extract = ['統一代號'] + list(rename_dict.keys())
    return pd.merge(base_df, source_df[cols_to_extract].rename(columns=rename_dict).drop_duplicates(subset=['統一代號']), on='統一代號', how='left')

@st.fragment
def render_debug_panel(filtered_df, any_filter_applied, dynamic_price_col_b6):
    if any_filter_applied:
        st.success(f"✅ 過濾完成！共有 **{len(filtered_df)}** 檔標的符合您的跨模組條件。")
        if st.checkbox("🔬 展開過濾名單", key="debug_mode_chk"):
            debug_df = filtered_df.copy()
            
            # 1. B0 量價
            df_b0 = get_df('b0_price')
            if not df_b0.empty and '成交額(百萬)' in df_b0.columns and '5日均額' in df_b0.columns:
                safe_avg = pd.to_numeric(df_b0['5日均額'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).replace(0, 0.01)
                df_b0['今日爆發倍數'] = (pd.to_numeric(df_b0['成交額(百萬)'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) / safe_avg).round(2)
            debug_df = merge_debug_data(debug_df, df_b0, {
                '股價日期': '股價日期', '成交': '成交', '漲跌幅': '漲跌幅', '成交張數': '成交張數', '成交額(百萬)': '成交額(百萬)',
                'PER': 'PER', '5日均額': '5日均額(百萬)', 'B0_量價狀態': '量價狀態', '成交金額日變化率': '金額日變化率(%)', 
                '今日爆發倍數': '爆發倍數(X)', '資金延續趨勢': '資金延續趨勢'
            }, prefix="B0_")

            # 2. B1 法人
            debug_df = merge_debug_data(debug_df, get_df('b1_final_df'), {'今日上榜':'今日上榜', '△':'△', '法人持股':'法人持股', '最新動態':'最新動態', '5日ΔChange':'5日ΔChange', '20日ΔChange':'20日ΔChange', '60日ΔChange':'60日ΔChange', '120日ΔChange':'120日ΔChange'})
            df_b1_for = get_df('b1_foreign_df')
            if not df_b1_for.empty:
                for_cols = sorted([c for c in df_b1_for.columns if c.startswith('外資持股_')], reverse=True)
                if for_cols:
                    df_b1_for['外資持股比'] = pd.to_numeric(df_b1_for[for_cols[0]], errors='coerce').apply(lambda x: f"{x:.2f}" if pd.notna(x) else None)
                    debug_df = merge_debug_data(debug_df, df_b1_for, {'外資持股比': '外資持股比'})
            if '法人持股' in debug_df.columns: 
                debug_df['法人持股'] = debug_df['法人持股'].apply(lambda x: None if pd.isna(x) or str(x).strip() in ['0', '0.0', '0.00', '未進榜'] else x)

            # 3. B2 突擊
            for k, n in zip(['b2_1', 'b2_2', 'b2_3', 'b2_4'], ['外資成交動態', '投信成交動態', '外資發行動態', '投信發行動態']):
                debug_df = merge_debug_data(debug_df, get_df(k), {'今日短動態': f"B2_{n}"})

            # 4. B3 連買
            df_b3 = get_df('b3_main')
            if not df_b3.empty:
                df_b3['B3_組合'] = df_b3['連買類型'].astype(str) + "(" + df_b3['連買週期數'].astype(str) + ")-" + df_b3['狀態動態'].astype(str)
                debug_df = pd.merge(debug_df, df_b3.groupby('統一代號')['B3_組合'].apply(lambda x: " | ".join(x)).reset_index().rename(columns={'B3_組合': 'B3_連買狀態'}), on='統一代號', how='left')

            # 5. B4 資券雷達與變化
            debug_df = merge_debug_data(debug_df, clean_stock_id(st.session_state.get('b4_squeeze_radar', {}).get('df', pd.DataFrame())), {'軋空評估': '軋空評估'})
            debug_df = merge_debug_data(debug_df, clean_stock_id(st.session_state.get('b4_risk_radar', {}).get('df', pd.DataFrame())), {'套牢評估': '套牢評估'})
            
            b4_dict = {'b4_margin_pct': '融資減幅', 'b4_margin_vol': '融資減張', 'b4_short_pct': '借券減幅', 'b4_short_vol': '借券減張', 'b4_margin_plus_pct': '融券增幅', 'b4_margin_plus_vol': '融券增張', 'b4_margin_inc_pct': '融資增幅', 'b4_short_inc_pct': '借券增幅'}
            for k, label in b4_dict.items():
                df_tmp = get_df(k)
                if not df_tmp.empty:
                    col_today = next((c for c in df_tmp.columns if '當日' in c and ('%' in c or '張' in c)), next((c for c in df_tmp.columns if '當日' in c), None))
                    if col_today: debug_df = merge_debug_data(debug_df, df_tmp, {col_today: f"B4_{label}_當日"})

            # 6. B5 大戶波段
            for k, l in zip(['b5_1000', 'b5_800', 'b5_600', 'b5_400'], ['B5_1000張', 'B5_800張', 'B5_600張', 'B5_400張']):
                df_tmp = get_df(k)
                latest_col = next((c for c in df_tmp.columns if c.startswith('▼') and '6周' not in c), None) if not df_tmp.empty else None
                if latest_col: debug_df = merge_debug_data(debug_df, df_tmp, {'週動態': f'{l}_週動態', latest_col: f'{l}_最新週', '▼6周增減': f'{l}_6周'})

            # 7. B6 鉅額
            df_b6 = get_df('b6_today')
            if not df_b6.empty:
                b6_map = {'總額(億)': 'B6_總額(億)', '▼收盤價': 'B6_收盤價'}
                if dynamic_price_col_b6 in df_b6.columns: b6_map[dynamic_price_col_b6] = 'B6_成交均價'
                debug_df = merge_debug_data(debug_df, df_b6, b6_map)

            # 8. B7 董監
            debug_df = merge_debug_data(debug_df, get_df('b7_pledge'), {'全體 董監 持股 (%)': 'B7_董監持股%', '全體 董監 質押 (%)': 'B7_董監質押%'})
            debug_df = merge_debug_data(debug_df, get_df('b7_main'), {'近月增減%': 'B7_持股近月增減%', '動態': 'B7_持股動態', '▼近半年增減%': 'B7_持股近半年增減%'})
            debug_df = merge_debug_data(debug_df, get_df('b7_pledge_history'), {'近月質押增減(%)': 'B7_質押近月增減%', '動態': 'B7_質押動態'})

            # 9. B8 券商大數據 (Parquet)
            df_b8_sum = get_df('b8_summary')
            if not df_b8_sum.empty: debug_df = merge_debug_data(debug_df, df_b8_sum, {'連買日數':'B8_日連買', '連買週數':'B8_週連買', '近期買超總張數':'B8_囤貨張數'})
            
            df_top15 = clean_stock_id(fetch_parquet_from_hf("scan__依主力Top15買超張數排行_復刻三竹.parquet"))
            if not df_top15.empty:
                if '最新日買超張數' in df_top15.columns and '最新均價' in df_top15.columns: df_top15['B8_斥資(億)'] = (df_top15['最新日買超張數'] * df_top15['最新均價'] * 1000 / 100000000).round(2)
                debug_df = merge_debug_data(debug_df, df_top15, {'主力連買動態': 'B8_主力連買動態', 'B8_斥資(億)': 'B8_斥資(億)'})

            df_tofu = clean_stock_id(fetch_parquet_from_hf("scan_依股價乖離率吃豆腐排行.parquet"))
            if not df_tofu.empty:
                if '主力囤貨(張)' in df_tofu.columns and '主力成本' in df_tofu.columns: df_tofu['B8_吃貨斥資(萬)'] = (df_tofu['主力囤貨(張)'] * df_tofu['主力成本'] * 1000 / 10000).round(0)
                debug_df = merge_debug_data(debug_df, df_tofu, {'乖離率(%)': 'B8_乖離率(%)', '吃豆腐動態': 'B8_吃豆腐動態', 'B8_吃貨斥資(萬)': 'B8_吃貨斥資(萬)'})

            df_mom = clean_stock_id(fetch_parquet_from_hf("momentum_latest.parquet"))
            if not df_mom.empty: debug_df = merge_debug_data(debug_df, df_mom, {'今日上榜期程': 'B8_上榜期程', '最新動態': 'B8_集中度動態', '單日Δ': 'B8_單日Δ', '5日Δ': 'B8_5日Δ'})
            
            st.write(f"🔍 檢核明細 (共 {len(debug_df)} 筆)：")
            st.dataframe(debug_df, use_container_width=True, hide_index=True)
            st.session_state['debug_df'] = debug_df 
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
                                    
                                    # 🚀 高效抓取價格對應
                                    df_b0_price = get_df('b0_price')
                                    price_dict = dict(zip(df_b0_price['統一代號'], pd.to_numeric(df_b0_price['成交'].astype(str).str.replace(',', ''), errors='coerce').fillna(0.0))) if not df_b0_price.empty else {}
                                    
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
# 🌟 動態過濾器 UI 渲染引擎 (B0 ~ B7)
# ==========================================
def render_dynamic_column_filter(df, col, prefix, active_dynamic_filters):
    """依照欄位屬性(數值 or 類別)自動生成過濾 UI，並將結果存入 active_dynamic_filters"""
    st.markdown(f"**{col}**")
    if pd.api.types.is_numeric_dtype(df[col]):
        c1, c2 = st.columns(2)
        # 利用 Streamlit >= 1.25 的 value=None 特性，不強制填入數值
        min_v = c1.number_input("最小值", value=None, key=f"dyn_filter_min_{prefix}_{col}")
        max_v = c2.number_input("最大值", value=None, key=f"dyn_filter_max_{prefix}_{col}")
        if min_v is not None:
            active_dynamic_filters.append(('num_min', col, min_v))
        if max_v is not None:
            active_dynamic_filters.append(('num_max', col, max_v))
    else:
        # 類別型：拉出所有不重複的選項供多選
        uniq_vals = [x for x in df[col].dropna().unique() if str(x).strip() != '']
        uniq_vals = sorted(list(set(str(x) for x in uniq_vals)))
        sel_v = st.multiselect("選擇符合的條件：", uniq_vals, key=f"dyn_filter_in_{prefix}_{col}")
        if sel_v:
            active_dynamic_filters.append(('cat_in', col, sel_v))
    st.write("---")


# ==========================================
# 🌟 主程式 Entry Point
# ==========================================
def show_weight_backtest_page(STOCK_DICT, DATA_DIR="data"):
    if 'b0_price' not in st.session_state: sync_b0_data(DATA_DIR)
    ensure_b1_to_b5_loaded(DATA_DIR)
    if 'b6_today_df' not in st.session_state: sync_b6_data(DATA_DIR)
    if 'b7_main' not in st.session_state: sync_b7_data(DATA_DIR)
    if 'b7_pledge' not in st.session_state: sync_pledge_data(DATA_DIR)
    if 'b7_pledge_history' not in st.session_state: sync_pledge_history_data(DATA_DIR)
    sync_b8_data() 
    
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

    # 0. 載入全域 Parquet 檔案與建立候選池
    master_df = load_master_features()

    pool_dict = {}
    if STOCK_DICT:
        for v in STOCK_DICT.values():
            if sid := str(v.get("id", "")).strip(): pool_dict[sid] = {"統一代號": sid, "股票名稱": v.get("name", ""), "產業別": v.get("industry", "未分類")}
                
    for key in ['b1_final_df', 'b2_1', 'b2_2', 'b2_3', 'b2_4', 'b4_margin_pct', 'b4_short_pct', 'b4_margin_plus_pct', 'b4_margin_inc_pct', 'b4_short_inc_pct']:
        df_tmp = get_df(key)
        if not df_tmp.empty:
            for sid, sname in zip(df_tmp['統一代號'], df_tmp.get('股票名稱', ['']*len(df_tmp))):
                if sid not in pool_dict: pool_dict[sid] = {"統一代號": sid, "股票名稱": str(sname), "產業別": "ETF/基金/其他"}

    base_df = pd.DataFrame(list(pool_dict.values()))
    if base_df.empty: return st.warning("⚠️ 無法建立候選池，請確認資料庫狀態。")

    # ==========================================
    # 1. 第一關：嚴格過濾器面板 (重構區)
    # ==========================================
    col_title, col_reset = st.columns([3, 1])
    with col_title: st.markdown(f"#### 1️⃣ 設定嚴格過濾條件 (目前總候選池共 {len(base_df)} 檔)")
    
    with col_reset:
        def reset_filters():
            # 清除所有動態生成的過濾器 key
            for key in list(st.session_state.keys()):
                if key.startswith("dyn_filter_"):
                    del st.session_state[key]
            
            # 清除 B8 特定過濾器與原始架構的其他殘留
            for k in ['b8_day_streak', 'b8_top15_money', 'b8_tofu_money']: 
                st.session_state[f'filter_{k}'] = 0
            st.session_state['filter_b8_tofu_bias'] = (-30.0, 30.0)
            st.session_state['filter_b8_mom_logic'] = "交集 (必須同時符合勾選期程)"
            for k in ['b8_tofu_trend', 'b8_mom_period', 'b8_mom_trend']: 
                st.session_state[f'filter_{k}'] = []
            st.session_state['filter_b8_mom_slope'] = False
            
        st.button("清空過濾條件", icon=":material/ink_eraser:", on_click=reset_filters, use_container_width=True)

    filtered_df = base_df.copy()
    any_filter_applied = False
    
    # 準備蒐集所有區塊動態觸發的條件: list of tuple ('num_min'/'num_max'/'cat_in', col_name, value)
    active_dynamic_filters = []

    if master_df.empty:
        st.warning("⚠️ 找不到 20261013_master_features.parquet，動態過濾功能無法完全啟用。")

    # --- 取出日期的字串 (用於維持版面標題一致性) ---
    df_b0 = get_df('b0_price')
    b0_latest_date_str = "2026/10/13"
    if not df_b0.empty and '股價日期' in df_b0.columns:
        date_raw = str(df_b0['股價日期'].iloc[0]).strip()
        parts = date_raw.replace("-", "/").split("/")
        b0_latest_date_str = f"2026/{parts[0].zfill(2)}/{parts[1].zfill(2)}" if len(parts) == 2 else (pd.to_datetime(date_raw).strftime("%Y/%m/%d") if pd.to_datetime(date_raw).year >= 2000 else f"2026/{pd.to_datetime(date_raw).strftime('%m/%d')}")

    b1_latest_date_str = f"{str(st.session_state.get('b1_sorted_dates', ['00000000'])[0])[:4]}/{str(st.session_state.get('b1_sorted_dates', ['00000000'])[0])[4:6]}/{str(st.session_state.get('b1_sorted_dates', ['00000000'])[0])[6:]}" if st.session_state.get('b1_sorted_dates') else "2026/10/13"
    
    b2_latest_date_str = next((c.replace("成交比%", "") for c in get_df('b2_1').columns if "成交比%" in c), "未知")
    if len(b2_latest_date_str) == 4: b2_latest_date_str = f"2026/{b2_latest_date_str[:2]}/{b2_latest_date_str[2:]}"
    
    dates = [d for _, d in st.session_state.get('b3_data', {}).values() if d and d != "00000000"]
    b3_latest_date_str = f"2026/{max(dates)[4:6]}/{max(dates)[6:]}" if dates else "2026/10/13"
    
    b4_latest_date_str = st.session_state.get('b4_squeeze_radar', {}).get('date', "2026/10/13")
    
    df_1k = get_df('b5_1000')
    b5_latest_date_str = f"2026/{col.replace('▼', '')[:2]}/{col.replace('▼', '')[2:]}" if (col := next((c for c in df_1k.columns if c.startswith('▼') and '6周' not in c), None)) else "2026/10/13"

    dynamic_price_col_b6 = st.session_state.get('b6_dynamic_price_col')
    b6_latest_date_str = f"2026/{date_part[:2]}/{date_part[2:]}" if dynamic_price_col_b6 and "▼" in dynamic_price_col_b6 and len(date_part := dynamic_price_col_b6.split(' ')[0].replace('▼', '')) == 4 else "2026/10/13"

    df_b7_tmp = get_df('b7_main')
    valid_m = [m for m in [c.replace('持股%', '') for c in df_b7_tmp.columns if '持股%' in c] if re.match(r'^\d{2}M\d{2}$|^\d{4,6}$', m)]
    b7_latest_date_str = f"20{sorted(valid_m, reverse=True)[0].split('M')[0]}/{sorted(valid_m, reverse=True)[0].split('M')[1]}" if valid_m and 'M' in sorted(valid_m, reverse=True)[0] else (f"{sorted(valid_m, reverse=True)[0][:4]}/{sorted(valid_m, reverse=True)[0][4:]}" if valid_m else "2026/10")

    # ---------------------------
    # B0 模組 (量價過濾)
    # ---------------------------
    b0_cols_explicit = [
        '成交', '漲跌幅', 'PER', 'PBR', '成交張數_num', '今日成交額(萬)', '成交金額日變化率(%)',
        'B0_量價狀態', 'B0_特殊型態', '資金延續趨勢', '5日均價', '5日均額(萬)', '5日均量(張)',
        '較5日均額增加(萬)', '5日爆發倍數', '10日均價', '10日均額(萬)', '10日均量(張)', '較10日均額增加(萬)',
        '10日爆發倍數', '20日均價', '20日均額(萬)', '20日均量(張)', '較20日均額增加(萬)', '20日爆發倍數',
        '30日均價', '30日均額(萬)', '30日均量(張)', '較30日均額增加(萬)', '30日爆發倍數', '45日均價',
        '45日均額(萬)', '45日均量(張)', '較45日均額增加(萬)', '45日爆發倍數', '60日均價', '60日均額(萬)',
        '60日均量(張)', '較60日均額增加(萬)', '60日爆發倍數', '120日均價', '120日均額(萬)', '120日均量(張)',
        '較120日均額增加(萬)', '120日爆發倍數', '180日均價', '180日均額(萬)', '180日均量(張)',
        '較180日均額增加(萬)', '180日爆發倍數', '240日均價', '240日均額(萬)', '240日均量(張)',
        '較240日均額增加(萬)', '240日爆發倍數'
    ]
    with st.expander(f"💰 B0 量價掃描過濾 (資料基準日: {b0_latest_date_str})", expanded=False):
        if not master_df.empty:
            sel_b0 = st.multiselect("📌 選擇要啟用的過濾欄位：", [c for c in b0_cols_explicit if c in master_df.columns], key="dyn_filter_sel_b0")
            for col in sel_b0:
                render_dynamic_column_filter(master_df, col, "B0", active_dynamic_filters)

    # ---------------------------
    # B1 模組 (法人動向過濾)
    # ---------------------------
    b1_cols_explicit = [
        'B1_正向_法人持股(%)', 'B1_正向上榜區塊', 'B1_衰退_法人持股(%)', 'B1_負向上榜區塊', 'B1_累積衰退(%)',
        'B1_外資買賣超張數', 'B1_投信買賣超張數', 'B1_自營買賣超張數', 'B1_合計買賣超張數', 'B1_外資持有(千張)',
        'B1_外資持股(%)', 'B1_總法人持股(%)', 'B1_1日△Change', 'B1_估內資持股(%)', 'B1_外資1日△Change',
        'B1_5日△Change', 'B1_5日排名', 'B1_20日△Change', 'B1_20日排名', 'B1_60日△Change', 'B1_60日排名',
        'B1_120日△Change', 'B1_120日排名', 'B1_5日前一日排名', 'B1_20日前一日排名', 'B1_60日前一日排名',
        'B1_120日前一日排名', 'B1_5日△排名', 'B1_20日△排名', 'B1_60日△排名', 'B1_120日△排名', 'B1_法人軌跡動態',
        'B1_1日法人金額(萬)', 'B1_5日法人金額(萬)', 'B1_20日法人金額(萬)', 'B1_60日法人金額(萬)', 'B1_120日法人金額(萬)'
    ]
    with st.expander(f"📈 B1 法人動向過濾 (資料基準日: {b1_latest_date_str})", expanded=False):
        if not master_df.empty:
            sel_b1 = st.multiselect("📌 選擇要啟用的過濾欄位：", [c for c in b1_cols_explicit if c in master_df.columns], key="dyn_filter_sel_b1")
            for col in sel_b1:
                render_dynamic_column_filter(master_df, col, "B1", active_dynamic_filters)

    # ---------------------------
    # B2 模組 (法人掃貨過濾)
    # ---------------------------
    with st.expander(f"🚀 B2 法人掃貨過濾 (資料基準日: {b2_latest_date_str})", expanded=False):
        if not master_df.empty:
            b2_cols = [c for c in master_df.columns if str(c).startswith('B2_')]
            sel_b2 = st.multiselect("📌 選擇要啟用的過濾欄位：", b2_cols, key="dyn_filter_sel_b2")
            for col in sel_b2:
                render_dynamic_column_filter(master_df, col, "B2", active_dynamic_filters)

    # ---------------------------
    # B3 模組 (法人連買過濾)
    # ---------------------------
    with st.expander(f"🔥 B3 法人連買過濾 (資料基準日: {b3_latest_date_str})", expanded=False):
        if not master_df.empty:
            b3_cols = [c for c in master_df.columns if str(c).startswith('B3_')]
            sel_b3 = st.multiselect("📌 選擇要啟用的過濾欄位：", b3_cols, key="dyn_filter_sel_b3")
            for col in sel_b3:
                render_dynamic_column_filter(master_df, col, "B3", active_dynamic_filters)

    # ---------------------------
    # B4 模組 (資券動向過濾)
    # ---------------------------
    with st.expander(f"⚔️ B4 資券動向過濾 (資料基準日: {b4_latest_date_str})", expanded=False):
        if not master_df.empty:
            b4_cols = [c for c in master_df.columns if str(c).startswith('B4_')]
            sel_b4 = st.multiselect("📌 選擇要啟用的過濾欄位：", b4_cols, key="dyn_filter_sel_b4")
            for col in sel_b4:
                render_dynamic_column_filter(master_df, col, "B4", active_dynamic_filters)

    # ---------------------------
    # B5 模組 (大腿動向過濾)
    # ---------------------------
    with st.expander(f"🐳 B5 大腿動向過濾 (資料基準日: {b5_latest_date_str})", expanded=False):
        if not master_df.empty:
            b5_cols = [c for c in master_df.columns if str(c).startswith('B5_')]
            sel_b5 = st.multiselect("📌 選擇要啟用的過濾欄位：", b5_cols, key="dyn_filter_sel_b5")
            for col in sel_b5:
                render_dynamic_column_filter(master_df, col, "B5", active_dynamic_filters)

    # ---------------------------
    # B6 模組 (鉅額交易過濾)
    # ---------------------------
    with st.expander(f"💎 B6 鉅額交易過濾 (資料基準日: {b6_latest_date_str})", expanded=False):
        if not master_df.empty:
            b6_cols = [c for c in master_df.columns if str(c).startswith('B6_')]
            sel_b6 = st.multiselect("📌 選擇要啟用的過濾欄位：", b6_cols, key="dyn_filter_sel_b6")
            for col in sel_b6:
                render_dynamic_column_filter(master_df, col, "B6", active_dynamic_filters)

    # ---------------------------
    # B7 模組 (董監動向過濾)
    # ---------------------------
    with st.expander(f"👔 B7 董監動向過濾 (資料基準月: {b7_latest_date_str})", expanded=False):
        if not master_df.empty:
            b7_cols = [c for c in master_df.columns if str(c).startswith('B7_')]
            sel_b7 = st.multiselect("📌 選擇要啟用的過濾欄位：", b7_cols, key="dyn_filter_sel_b7")
            for col in sel_b7:
                render_dynamic_column_filter(master_df, col, "B7", active_dynamic_filters)

    # ---------------------------
    # 🏢 B8 模組 (券商主力與動能過濾) - 依照指示保留原樣
    # ---------------------------
    b8_latest_date_str = st.session_state.get('b8_latest_date', '最新交易日').replace('-', '/') 
    with st.expander(f"🏢 B8 券商主力與動能過濾 (資料基準日: {b8_latest_date_str})", expanded=False):
        c1, c2 = st.columns(2)
        b8_day_streak = c1.number_input("🔴 分點連買大於等於 (天)：", 0, value=0, step=1, key="filter_b8_day_streak")
        b8_top15_money = c2.number_input("主力斥資大於 (億)：", 0.0, value=0.0, step=0.5, key="filter_b8_top15_money")
        c3, c4 = st.columns(2)
        b8_tofu_bias = c3.slider("乖離率區間 (%)：", -30.0, 30.0, (-30.0, 30.0), 1.0, key="filter_b8_tofu_bias")
        b8_tofu_money = c4.number_input("吃貨斥資大於 (萬)：", 0.0, value=0.0, step=100.0, key="filter_b8_tofu_money")
        b8_tofu_trend = st.multiselect("吃豆腐動態 (可複選)：", ["🎯 成本保衛戰 (極佳吃豆腐點)", "🔥 主力已拉開獲利 (追高風險)", "🩸 主力套牢中 (防守失敗)", "🚀 脫離成本區"], key="filter_b8_tofu_trend")
        b8_mom_logic = st.radio("今日上榜期程篩選邏輯：", ["交集 (必須同時符合勾選期程)", "聯集 (符合任一期程即可)"], horizontal=True, key="filter_b8_mom_logic")
        c5, c6 = st.columns(2)
        b8_mom_period = c5.multiselect("今日上榜期程：", ["單日", "5日", "10日", "20日", "30日"], key="filter_b8_mom_period")
        b8_mom_trend = c6.multiselect("集中度最新動態：", ["↗️ 溫和吃貨", "➡️ 橫盤震盪", "⚠️ 大戶跳車 (警戒)", "🚀 籌碼急凍 (強勢吸籌)"], key="filter_b8_mom_trend")
        b8_mom_slope = st.checkbox("📈 單日 Δ > 5日 Δ > 10日 Δ (集中度動能斜率向上)", key="filter_b8_mom_slope")


    # ==========================================
    # 🌟 執行過濾邏輯：套用全域 Master 檔案篩選
    # ==========================================
    if active_dynamic_filters and not master_df.empty:
        any_filter_applied = True
        mask = pd.Series(True, index=master_df.index)
        
        for f_type, col, val in active_dynamic_filters:
            if f_type == 'num_min':
                mask &= (pd.to_numeric(master_df[col], errors='coerce') >= val)
            elif f_type == 'num_max':
                mask &= (pd.to_numeric(master_df[col], errors='coerce') <= val)
            elif f_type == 'cat_in':
                mask &= master_df[col].astype(str).isin(val)

        valid_stock_ids = master_df[mask]['統一代號'].astype(str).unique()
        filtered_df = filtered_df[filtered_df['統一代號'].isin(valid_stock_ids)]

    # 執行 B8 (既有的 HF Parquet) 過濾
    if b8_day_streak > 0 or b8_top15_money > 0:
        if not (df_t15 := clean_stock_id(fetch_parquet_from_hf("scan__依主力Top15買超張數排行_復刻三竹.parquet"))).empty:
            any_filter_applied = True; mask = pd.Series(True, index=df_t15.index)
            if b8_top15_money > 0 and '最新日買超張數' in df_t15.columns and '最新均價' in df_t15.columns: mask &= ((df_t15['最新日買超張數'] * df_t15['最新均價'] * 1000 / 100000000) >= b8_top15_money)
            if b8_day_streak > 0 and '主力連買動態' in df_t15.columns: mask &= (df_t15['主力連買動態'].astype(str).str.extract(r'連\s*(\d+)\s*買')[0].fillna(0).astype(int) >= b8_day_streak)
            filtered_df = filtered_df[filtered_df['統一代號'].isin(df_t15[mask]['統一代號'].astype(str).unique())]
            
    if b8_tofu_bias[0] > -30 or b8_tofu_bias[1] < 30 or b8_tofu_trend or b8_tofu_money > 0:
        if not (df_tofu := clean_stock_id(fetch_parquet_from_hf("scan_依股價乖離率吃豆腐排行.parquet"))).empty:
            any_filter_applied = True; mask = pd.Series(True, index=df_tofu.index)
            if '乖離率(%)' in df_tofu.columns: mask &= df_tofu['乖離率(%)'].between(*b8_tofu_bias)
            if b8_tofu_money > 0 and '主力囤貨(張)' in df_tofu.columns and '主力成本' in df_tofu.columns: mask &= ((df_tofu['主力囤貨(張)'] * df_tofu['主力成本'] * 1000 / 10000) >= b8_tofu_money)
            if b8_tofu_trend and '吃豆腐動態' in df_tofu.columns: mask &= df_tofu['吃豆腐動態'].isin(b8_tofu_trend)
            filtered_df = filtered_df[filtered_df['統一代號'].isin(df_tofu[mask]['統一代號'].astype(str).unique())]
            
    if b8_mom_period or b8_mom_trend or b8_mom_slope:
        if not (df_mom := clean_stock_id(fetch_parquet_from_hf("momentum_latest.parquet"))).empty:
            any_filter_applied = True; mask = pd.Series(True, index=df_mom.index)
            if b8_mom_period and '今日上榜期程' in df_mom.columns:
                is_and = "交集" in b8_mom_logic
                p_mask = pd.Series(True, index=df_mom.index) if is_and else pd.Series(False, index=df_mom.index)
                for p in b8_mom_period: p_mask = (p_mask & df_mom['今日上榜期程'].astype(str).str.contains(p, na=False)) if is_and else (p_mask | df_mom['今日上榜期程'].astype(str).str.contains(p, na=False))
                mask &= p_mask
            if b8_mom_trend and '最新動態' in df_mom.columns: mask &= df_mom['最新動態'].isin(b8_mom_trend)
            if b8_mom_slope and all(c in df_mom.columns for c in ['單日Δ', '5日Δ', '10日Δ']): mask &= (df_mom['單日Δ'] > df_mom['5日Δ']) & (df_mom['5日Δ'] > df_mom['10日Δ'])
            filtered_df = filtered_df[filtered_df['統一代號'].isin(df_mom[mask]['統一代號'].astype(str).unique())]

    # ==========================================
    # 🌟 呼叫 Fragment 1：除錯透視鏡
    # ==========================================
    render_debug_panel(filtered_df, any_filter_applied, dynamic_price_col_b6)

    st.write("---")

    # ==========================================
    # 2. 第二關：自訂權重計分面板 (保留原始計分邏輯與變數對接)
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
    # 3. 執行計分運算 (Scoring Engine) - 🚀 向量化加速版
    # ==========================================
    df_b1_raw = get_df('b1_final_df')

    if st.button("開始計算權重分數", icon=":material/vital_signs:", use_container_width=True):
        with st.spinner("🧠 籌碼大數據融合計算中..."):
            score_df = filtered_df.copy()
            score_df['總分'], score_df['得分明細'] = 0.0, ""

            def apply_score(df_key, weight, rule_name):
                if weight == 0 or (df := get_df(df_key)).empty: return
                mask = score_df['統一代號'].isin(df['統一代號'].unique())
                score_df.loc[mask, '總分'] += weight
                score_df.loc[mask, '得分明細'] += f"[{rule_name} {'+' if weight > 0 else ''}{weight}] "

            if not df_b1_raw.empty and w_b1_up != 0 and '上榜數量' in df_b1_raw.columns:
                valid = df_b1_raw[pd.to_numeric(df_b1_raw['上榜數量'], errors='coerce').fillna(0) > 0]
                if not valid.empty:
                    score_df = score_df.merge(valid[['統一代號', '上榜數量']].drop_duplicates(subset=['統一代號']), on='統一代號', how='left')
                    mask = score_df['上榜數量'].notna()
                    if mask.any():
                        cnt = score_df.loc[mask, '上榜數量'].astype(int)
                        score_df.loc[mask, '總分'] += cnt * w_b1_up
                        score_df.loc[mask, '得分明細'] += "[法人正向" + cnt.astype(str) + "次 +" + (cnt * w_b1_up).astype(str) + "] "
                    score_df.drop(columns=['上榜數量'], inplace=True)

            apply_score('b1_down_final_df', w_b1_down, "法人衰退")
            for k in ['b2_1', 'b2_2', 'b2_3', 'b2_4']: apply_score(k, w_b2, "法人掃貨")
            apply_score('b3_main', w_b3, "法人連買")
            for k in ['b4_margin_pct', 'b4_margin_plus_pct', 'b4_margin_vol', 'b4_margin_plus_vol']: apply_score(k, w_b4_good, "資券有利")
            for k in ['b4_short_pct', 'b4_short_vol', 'b4_short_dec_amt']: apply_score(k, w_b4_short_dec, "借券減少")
            for k in ['b4_short_inc_pct', 'b4_short_inc_vol', 'b4_short_inc_amt']: apply_score(k, w_b4_short_inc, "借券增加")
            
            if w_b4_price_up != 0 and not (df_b0_price := get_df('b0_price')).empty and '漲跌幅' in df_b0_price.columns:
                mask = score_df['統一代號'].isin(df_b0_price[pd.to_numeric(df_b0_price['漲跌幅'].astype(str).str.replace('%', ''), errors='coerce').fillna(0) > 3.0]['統一代號'].unique())
                score_df.loc[mask, '總分'] += w_b4_price_up
                score_df.loc[mask, '得分明細'] += f"[大漲>3% {'+' if w_b4_price_up > 0 else ''}{w_b4_price_up}] "

            apply_score('b5_1000', w_b5, "千張大戶"); apply_score('b5_800', w_b5_800, "800張大戶"); apply_score('b5_600', w_b5_600, "600張大戶"); apply_score('b5_400', w_b5_400, "400張大戶")
            
            if w_b6 != 0 and not (df_b6 := get_df('b6_today')).empty and dynamic_price_col_b6 in df_b6.columns:
                df_b6['is_suc'] = df_b6.apply(lambda r: float(str(r.get('▼收盤價', '0')).replace(',', '')) >= (sum([float(p) for p in str(r.get(dynamic_price_col_b6, '0')).split(' / ')]) / len(str(r.get(dynamic_price_col_b6, '0')).split(' / '))) if str(r.get(dynamic_price_col_b6, '')) else False, axis=1)
                mask = score_df['統一代號'].isin(df_b6[df_b6['is_suc']]['統一代號'].unique())
                score_df.loc[mask, '總分'] += w_b6; score_df.loc[mask, '得分明細'] += f"[鉅額防守 {'+' if w_b6 > 0 else ''}{w_b6}] "

            if w_b7 != 0:
                if not (df_b7_main := get_df('b7_main')).empty and '近月增減%' in df_b7_main.columns:
                    mask = score_df['統一代號'].isin(df_b7_main[pd.to_numeric(df_b7_main['近月增減%'], errors='coerce') > 0]['統一代號'].unique())
                    score_df.loc[mask, '總分'] += w_b7; score_df.loc[mask, '得分明細'] += f"[董監增持 {'+' if w_b7 > 0 else ''}{w_b7}] "
                if not (df_b7_hist := get_df('b7_pledge_history')).empty and '近月質押增減(%)' in df_b7_hist.columns:
                    mask = score_df['統一代號'].isin(df_b7_hist[pd.to_numeric(df_b7_hist['近月質押增減(%)'], errors='coerce') < 0]['統一代號'].unique())
                    score_df.loc[mask, '總分'] += w_b7; score_df.loc[mask, '得分明細'] += f"[質押下降 {'+' if w_b7 > 0 else ''}{w_b7}] "

            st.session_state['scored_result'] = score_df[score_df['總分'] != 0].sort_values(by='總分', ascending=False).reset_index(drop=True).copy()
            st.session_state['score_calculated'] = True

    # ==========================================
    # 🌟 呼叫 Fragment 2：結果展示與存檔按鈕
    # ==========================================
    render_result_and_save_panel()
