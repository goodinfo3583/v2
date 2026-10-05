# master_etl_pipeline.py
import pandas as pd
import numpy as np
import os
import glob
import re
import json
import requests
from collections import defaultdict

def extract_date_from_name(filename):
    match = re.search(r'(202\d{5})', str(filename))
    return match.group(1) if match else "00000000"

def fetch_github_json_all():
    days_list = [5, 20, 60, 120]
    json_dfs = {}
    account, repo, branch = "goodinfo3583", "DDong_tw-institutional-stocker", "main"
    for d in days_list:
        url = f"https://raw.githubusercontent.com/{account}/{repo}/{branch}/docs/data/top_three_inst_change_{d}_up.json"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                df = pd.DataFrame(res.json())
                if not df.empty:
                    df['stock_code'] = df['code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)
                    df = df.rename(columns={'change': f'B1_{d}日△Change'})
                    df[f'B1_{d}日排名'] = (df.index + 1).astype(int)
                    df[f'B1_{d}日△Change'] = pd.to_numeric(df[f'B1_{d}日△Change'], errors='coerce')
                    json_dfs[d] = df[['stock_code', f'B1_{d}日△Change', f'B1_{d}日排名']]
        except Exception: pass
    return json_dfs

# ==========================================
# 模組一：B0 價格與量能運算
# ==========================================
def process_b0_features(DATA_DIR, OUTPUT_DIR):
    print("▶️ [1/5] 開始處理 B0 基礎量價與多期程均線...")
    files = glob.glob(os.path.join(DATA_DIR, "*成交價*.parquet")) + glob.glob(os.path.join(DATA_DIR, "*成交價*.csv"))
    if not files: return None, None
    
    all_dfs = []
    for f in files:
        try:
            df = pd.read_parquet(f) if f.endswith('.parquet') else pd.read_csv(f, encoding='utf-8-sig', dtype=str)
            df.columns = [re.sub(r'\s+', '', str(c)) for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            
            c_code, date_col = next((c for c in df.columns if '代號' in c), None), next((c for c in df.columns if '日期' in c), None)
            name_col = next((c for c in df.columns if c in ['名稱', '股票名稱', '證券名稱']), None)
            
            if c_code and date_col:
                df['stock_code'] = df[c_code].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df['trade_date'] = df[date_col].astype(str).str.strip()
                df['stock_name'] = df[name_col].astype(str).str.strip() if name_col else ""
                
                vol_col = next((c for c in df.columns if c in ['成交張數', '總量', '成交量', '累積成交張數', '張數']), None)
                df['成交張數_num'] = pd.to_numeric(df[vol_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0) if vol_col else 0
                
                amt_col = next((c for c in df.columns if c in ['成交額(百萬)', '成交金額', '成交額', '總金額']), None)
                df['成交額_num'] = pd.to_numeric(df[amt_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0) if amt_col else 0
                
                for c in ['PER', 'PBR', '成交', '漲跌幅']:
                    if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[,%]', '', regex=True), errors='coerce')
                all_dfs.append(df)
        except Exception: continue

    if not all_dfs: return None, None
    
    combined_df = pd.concat(all_dfs, ignore_index=True)
    combined_df = combined_df[~combined_df['trade_date'].fillna("").astype(str).str.lower().isin(['nan', 'nat', 'none', '', 'null'])]
    combined_df = combined_df.sort_values(by=['stock_code', 'trade_date', '成交張數_num'], ascending=[True, False, False]).drop_duplicates(subset=['stock_code', 'trade_date'], keep='first')
    
    unique_dates = sorted([str(d) for d in combined_df['trade_date'].unique()], reverse=True)
    if not unique_dates: return None, None
    
    latest_date = unique_dates[0]
    date_prefix = latest_date.replace('/', '').replace('-', '')
    df_today = combined_df[combined_df['trade_date'] == latest_date].copy()
    df_today['今日成交額(萬)'] = df_today['成交額_num'] * 100  

    periods = [5, 10, 20, 30, 45, 60, 120, 180, 240]
    for p in periods:
        p_avg = combined_df.groupby('stock_code').head(p).groupby('stock_code').agg(
            **{f'{p}日均量(張)': ('成交張數_num', 'mean'), f'{p}日均額(萬)': ('成交額_num', 'mean'), f'{p}日均價': ('成交', 'mean'), f'實際天數_{p}': ('trade_date', 'count')}
        ).reset_index()
        mask_enough = p_avg[f'實際天數_{p}'] == p
        p_avg.loc[~mask_enough, [f'{p}日均量(張)', f'{p}日均額(萬)', f'{p}日均價']] = np.nan
        p_avg.drop(columns=[f'實際天數_{p}'], inplace=True)
        p_avg[f'{p}日均額(萬)'] = p_avg[f'{p}日均額(萬)'] * 100
        
        df_today = df_today.merge(p_avg, on='stock_code', how='left')
        df_today[f'較{p}日均額增加(萬)'] = df_today['今日成交額(萬)'] - df_today[f'{p}日均額(萬)']
        df_today[f'{p}日爆發倍數'] = (df_today['今日成交額(萬)'] / df_today[f'{p}日均額(萬)'].replace(0, 0.01)).round(2)

    prev_day = combined_df.groupby('stock_code').nth(1).reset_index()[['stock_code', '成交額_num', '成交張數_num', '漲跌幅']]
    df_today = df_today.merge(prev_day.rename(columns={'成交額_num': '昨日成交額', '成交張數_num': '昨日成交量', '漲跌幅': '昨日漲跌幅'}), on='stock_code', how='left')
    df_today['成交金額日變化率(%)'] = ((df_today['成交額_num'] / df_today['昨日成交額'].replace(0, 0.01).fillna(0.01)) - 1) * 100

    tdy_pct, yst_pct = df_today['漲跌幅'].fillna(0), df_today['昨日漲跌幅'].fillna(0)
    tdy_vol, yst_vol, avg_v = df_today['成交張數_num'].fillna(0), df_today['昨日成交量'].fillna(0), df_today['5日均量(張)'].fillna(0)
    
    df_today['B0_特殊型態'] = np.select([(yst_pct >= 4.0) & (yst_vol >= 1000) & (tdy_vol <= yst_vol * 0.5) & (tdy_pct >= -2.0), (avg_v >= 500) & (tdy_vol > 0) & (tdy_vol <= avg_v * 0.3) & (tdy_pct.abs() <= 1.5)], ["🕵️ 昨強今急縮 (洗盤防守)", "💤 極致窒息量 (醞釀表態)"], default="-")
    
    ratio = tdy_vol / avg_v.replace(0, np.nan)
    v_s = np.select([ratio >= 1.5, ratio <= 0.7], ["放量", "縮量"], default="平量")
    p_s = np.select([tdy_pct >= 4.0, tdy_pct > 1.5, tdy_pct >= -1.5, tdy_pct > -4.0], ["大漲", "價升", "滯漲", "小跌"], default="大跌")
    status_map = {"放量大漲":"🚀 放量大漲", "縮量大漲":"🔒 縮量大漲", "平量大漲":"✈️ 平量大漲", "縮量價升":"📈 價升量縮", "放量滯漲":"⚠️ 放量滯漲", "平量滯漲":"⏸ 平量滯漲", "縮量小跌":"📉 縮量小跌", "放量小跌":"🛡️ 放量小跌", "平量小跌":"🥀 平量價縮", "縮量大跌":"☠️ 縮量大跌", "放量大跌":"🩸 放量大跌", "平量大跌":"🕳 平量大跌"}
    df_today['B0_量價狀態'] = pd.Series(v_s + p_s).map(status_map).fillna("⚖ 溫和震盪整理").values

    t_amt, m5, m10, m20 = df_today['今日成交額(萬)'].fillna(0), df_today['5日均額(萬)'].fillna(0), df_today['10日均額(萬)'].fillna(0), df_today['20日均額(萬)'].fillna(0)
    v = (m5 > 0) & (m10 > 0) & (m20 > 0)
    df_today['資金延續趨勢'] = np.select([v & (m5 > m10) & (m10 > m20), v & (t_amt > m5) & (m5 <= m10), v & (m5 < m10) & (m10 < m20), v], ["🔥 資金湧入", "⚡ 單日點火", "💧 資金退潮", "⚖️ 震盪換手"], default="⚪ 資料不足")

    base_cols = ['stock_code', 'stock_name', 'trade_date', '成交', '漲跌幅', 'PER', 'PBR', '成交張數_num', '今日成交額(萬)', '成交金額日變化率(%)', 'B0_量價狀態', 'B0_特殊型態', '資金延續趨勢']
    dynamic_cols = []
    for p in periods: dynamic_cols.extend([f'{p}日均價', f'{p}日均額(萬)', f'{p}日均量(張)', f'較{p}日均額增加(萬)', f'{p}日爆發倍數'])
        
    return df_today[[c for c in (base_cols + dynamic_cols) if c in df_today.columns]].copy(), date_prefix

# ==========================================
# 模組二：B1 法人軌跡與籌碼結構運算
# ==========================================
def process_b1_features(DATA_DIR, target_date):
    # 解決 target_date (如 '1005') 與檔案日期 (如 '20261002') 長度不同導致比對錯誤的 Bug
    clean_target = str(target_date).replace('/', '').replace('-', '')
    if len(clean_target) == 4:
        full_target_date = f"2026{clean_target}" # 補齊為 8 碼 YYYYMMDD
    else:
        full_target_date = clean_target

    print(f"▶️ [2/5] 開始處理 B1 法人軌跡與籌碼結構 (強制對齊基準日: {full_target_date})...")
    
    def align_files_to_target(files):
        valid = [f for f in files if extract_date_from_name(f) <= full_target_date]
        valid = sorted(valid, key=extract_date_from_name, reverse=True)
        if valid and extract_date_from_name(valid[0]) != full_target_date:
            print(f"  ⚠️ 警告: B1 缺乏 {full_target_date} 資料，強行保留 Schema 並填補空值。")
            valid.insert(0, None)
        return valid

    f_up_history = align_files_to_target(glob.glob(os.path.join(DATA_DIR, "*JSON_History.csv")))
    f_down_history = align_files_to_target(glob.glob(os.path.join(DATA_DIR, "*Down_History.csv")))
    f_foreign_ratio = align_files_to_target(glob.glob(os.path.join(DATA_DIR, "*外資持股比例*.parquet")) + glob.glob(os.path.join(DATA_DIR, "*外資持股比例*.csv")))
    
    df_up, df_down, df_fi, d_cols = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), []
    
    for i, file in enumerate(f_up_history[:4]):
        if file is None: continue
        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
            df.columns = [str(c).replace(" ", "").strip() for c in df.columns]
            df['stock_code'] = df['股票代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)
            if i == 0:
                df.rename(columns={'法人持股': 'B1_正向_法人持股(%)', '上榜區塊': 'B1_正向上榜區塊'}, inplace=True)
                df_up, d_cols = df, ['B1_正向_法人持股(%)']
            else:
                col_name, sec_name = f'持股%_{i}', f'區塊_{i}'
                if '上榜區塊' in df.columns:
                    df = df[['stock_code', '法人持股', '上榜區塊']].rename(columns={'法人持股': col_name, '上榜區塊': sec_name})
                else:
                    df = df[['stock_code', '法人持股']].assign(上榜區塊="").rename(columns={'法人持股': col_name, '上榜區塊': sec_name})
                
                if df_up.empty: df_up = df[['stock_code']].copy()
                df_up = pd.merge(df_up, df, on='stock_code', how='outer')
                d_cols.append(col_name)
        except Exception: pass
        
    for i, file in enumerate(f_down_history[:2]):
        if file is None: continue
        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
            df.columns = [str(c).replace(" ", "").strip() for c in df.columns]
            df['stock_code'] = df['股票代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)
            if i == 0:
                df.rename(columns={'法人持股': 'B1_衰退_法人持股(%)', '上榜區塊': 'B1_負向上榜區塊', '累積衰退': 'B1_累積衰退(%)'}, inplace=True)
                df_down = df
            else:
                df_t1 = df[['stock_code', '法人持股']].rename(columns={'法人持股': 'B1_衰退_法人持股(%)_T1'})
                if df_down.empty: df_down = df_t1[['stock_code']].copy()
                df_down = pd.merge(df_down, df_t1, on='stock_code', how='outer')
        except Exception: pass

    for i, file in enumerate(f_foreign_ratio[:2]):
        if file is None: continue
        try:
            df = pd.read_parquet(file) if file.endswith('.parquet') else pd.read_csv(file, encoding='utf-8-sig')
            df.columns = [str(c).replace(" ", "").replace("\n", "").strip() for c in df.columns]
            if i == 0:
                keep = {c: 'stock_code' if '代號' in c else ('B1_外資持股(%)' if '外資持股(%)' in c else ('B1_外資買賣超張數' if '外資買賣超張數' in c else ('B1_投信買賣超張數' if '投信買賣超張數' in c else ('B1_自營買賣超張數' if '自營買賣超張數' in c else ('B1_合計買賣超張數' if '合計買賣超張數' in c else ('B1_外資持有(千張)' if '外資持有(千張)' in c else None)))))) for c in df.columns}
                keep = {k: v for k, v in keep.items() if v}
                df_fi = df.rename(columns=keep)
                df_fi['stock_code'] = df_fi['stock_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)
                for col in keep.values():
                    if col != 'stock_code': df_fi[col] = pd.to_numeric(df_fi[col].astype(str).str.replace(r'[%,\s]', '', regex=True), errors='coerce')
                df_fi = df_fi[list(keep.values())]
            else:
                id_col, val_col = next((c for c in df.columns if '代號' in c), None), next((c for c in df.columns if '外資持股' in c), None)
                if id_col and val_col:
                    df_t1 = df[[id_col, val_col]].rename(columns={id_col: 'stock_code', val_col: 'B1_外資持股(%)_T1'})
                    df_t1['stock_code'] = df_t1['stock_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)
                    df_t1['B1_外資持股(%)_T1'] = pd.to_numeric(df_t1['B1_外資持股(%)_T1'].astype(str).str.replace(r'[%,\s]', '', regex=True), errors='coerce')
                    if df_fi.empty: df_fi = df_t1[['stock_code']].copy()
                    df_fi = pd.merge(df_fi, df_t1, on='stock_code', how='outer')
        except Exception: pass

    dfs = [df for df in [df_up, df_down, df_fi] if not df.empty]
    if not dfs: 
        # 如果極端情況完全沒有歷史檔案，依然產出具有 stock_code 欄位的空表
        master_b1 = pd.DataFrame(columns=['stock_code'])
    else:
        master_b1 = dfs[0]
        for df in dfs[1:]: master_b1 = pd.merge(master_b1, df, on='stock_code', how='outer')

    # 🛡️【終極 Schema 保衛戰】在此一次性注入所有 B1 核心欄位，確保絕對不消失
    core_cols = [
        'B1_正向_法人持股(%)', 'B1_衰退_法人持股(%)', '持股%_1', 'B1_衰退_法人持股(%)_T1',
        'B1_外資持股(%)', 'B1_外資持股(%)_T1', 'B1_外資持有(千張)', 
        'B1_外資買賣超張數', 'B1_投信買賣超張數', 'B1_自營買賣超張數', 'B1_合計買賣超張數'
    ]
    for c in core_cols:
        if c not in master_b1.columns: 
            master_b1[c] = np.nan

    # 開始執行原本的計算邏輯
    master_b1['B1_正向上榜區塊'] = master_b1.get('B1_正向上榜區塊', pd.Series(dtype=str)).fillna("")
    master_b1['B1_負向上榜區塊'] = master_b1.get('B1_負向上榜區塊', pd.Series(dtype=str)).fillna("")
    
    master_b1['B1_總法人持股(%)'] = master_b1['B1_正向_法人持股(%)'].combine_first(master_b1['B1_衰退_法人持股(%)'])
    master_b1['B1_1日△Change'] = master_b1['B1_總法人持股(%)'] - master_b1['持股%_1'].combine_first(master_b1['B1_衰退_法人持股(%)_T1'])

    master_b1['B1_估內資持股(%)'] = (master_b1['B1_總法人持股(%)'] - master_b1['B1_外資持股(%)']).clip(lower=0)
    master_b1['B1_外資1日△Change'] = master_b1['B1_外資持股(%)'] - master_b1['B1_外資持股(%)_T1']

    json_dfs = fetch_github_json_all()
    for d in [5, 20, 60, 120]:
        if d in json_dfs and not json_dfs[d].empty: 
            master_b1 = pd.merge(master_b1, json_dfs[d], on='stock_code', how='left')
        else: 
            master_b1[f'B1_{d}日△Change'] = np.nan
            master_b1[f'B1_{d}日排名'] = np.nan

    master_b1['估算總發行張數'] = np.where(master_b1['B1_外資持股(%)'] > 0, (master_b1['B1_外資持有(千張)'] * 1000) / (master_b1['B1_外資持股(%)'] / 100), np.nan)

    master_b1['B1_法人軌跡動態'] = master_b1.apply(lambda r: "⚠️ 多空交戰 (籌碼分歧)" if str(r.get('B1_正向上榜區塊', '')) and str(r.get('B1_負向上榜區塊', '')) else ("👑 長線吸籌" if '120日' in str(r.get('B1_正向上榜區塊', '')) or '60日' in str(r.get('B1_正向上榜區塊', '')) else ("🔥 波段佈局" if '20日' in str(r.get('B1_正向上榜區塊', '')) else "🚀 短線點火")) if str(r.get('B1_正向上榜區塊', '')) else ("☠️ 長線提款" if '30日' in str(r.get('B1_負向上榜區塊', '')) or '20日' in str(r.get('B1_負向上榜區塊', '')) else "🩸 短線棄守") if str(r.get('B1_負向上榜區塊', '')) else "⚪ 無明顯軌跡", axis=1)

    cols_drop = [c for c in d_cols if c != 'B1_正向_法人持股(%)'] + ['區塊_1', '區塊_2', '區塊_3', 'B1_衰退_法人持股(%)_T1', 'B1_總法人持股(%)_T1', 'B1_外資持股(%)_T1', '持股%_1']
    master_b1.drop(columns=[c for c in cols_drop if c in master_b1.columns], inplace=True, errors='ignore')
    
    return master_b1

# ==========================================
# 模組三：B2/B3 法人佔比與連續買賣運算
# ==========================================
def process_b2_category(files, category_name, base_keyword, short_type, is_sell_only=False):
    if not files: return pd.DataFrame()
    date_files = defaultdict(list)
    for f in files: date_files[extract_date_from_name(f)].append(f)
    sorted_dates = sorted(date_files.keys(), reverse=True)[:10] 
    
    base_df = None
    timeframes = ['當日', '2日', '3日', '5日', '10日', '1個月', '3個月', '半年']
    
    for idx, d in enumerate(sorted_dates):
        daily_dfs = []
        for f in date_files[d]:
            try:
                df = pd.read_csv(f, encoding='utf-8-sig')
                df.columns = [str(c).replace(" ", "").replace("\n", "").strip() for c in df.columns]
                id_col = next((c for c in df.columns if '代號' in c), df.columns[0])
                df = df.rename(columns={id_col: 'stock_code'})
                df['stock_code'] = df['stock_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                daily_dfs.append(df)
            except: continue
                
        if not daily_dfs: continue
        df_combined = pd.concat(daily_dfs, ignore_index=True).drop_duplicates(subset=['stock_code'], keep='first')
        
        col_mapping = {next((c for c in df_combined.columns if tf in c and base_keyword in c), None): f'B2_{category_name}_{tf}佔{short_type}(%)' for tf in timeframes}
        col_mapping = {k: v for k, v in col_mapping.items() if k}
        
        if idx == 0:
            base_df = df_combined[['stock_code'] + list(col_mapping.keys())].rename(columns=col_mapping).copy()
        else:
            if base_df is not None:
                new_codes = df_combined[~df_combined['stock_code'].isin(base_df['stock_code'])][['stock_code']].copy()
                for new_col in col_mapping.values(): new_codes[new_col] = np.nan
                base_df = pd.concat([base_df, new_codes], ignore_index=True)

    if base_df is None or base_df.empty: return pd.DataFrame()
    for c in [c for c in base_df.columns if '(%)' in c]: base_df[c] = pd.to_numeric(base_df[c], errors='coerce')
    
    c_tdy, c_5d = f'B2_{category_name}_當日佔{short_type}(%)', f'B2_{category_name}_5日佔{short_type}(%)'
    def eval_cont(row):
        t, v5 = row.get(c_tdy, np.nan), row.get(c_5d, np.nan)
        if pd.isna(t) and pd.isna(v5): return "⚪ 榜外無動靜"
        if is_sell_only:
            if pd.isna(t) and v5 > 0: return "📈 掉出賣榜 (賣壓減輕)"
            if pd.isna(v5) and t > 0: return "⚠️ 突擊賣榜 (警戒賣壓)"
            if t > 0: return "🚨 賣壓加劇" if t > v5 else "📉 賣壓趨緩"
            return "🔄 持平"
        else:
            if pd.isna(t): return "📉 掉出買榜 (籌碼鬆動)" if v5 > 0 else "📈 掉出賣榜 (賣壓減輕)" if v5 < 0 else "⚪ 榜外無動靜"
            if pd.isna(v5): return "🆕 突擊買榜" if t > 0 else "⚠️ 突擊賣榜" if t < 0 else "🔄 持平"
            if t > 0: return "🔥 轉賣為買 (強力反轉)" if v5 < 0 else "🔥 強延續" if t > v5 else "⚠️ 買盤趨緩"
            if t < 0: return "🚨 轉買為賣 (提防倒貨)" if v5 > 0 else "🚨 劇烈倒貨" if abs(t) > abs(v5) else "📉 調節洗盤"
            return "🔄 持平"
    base_df[f'B2_{category_name}{short_type}動態'] = base_df.apply(eval_cont, axis=1)
    return base_df

def process_institutional_volume(files):
    if not files: return pd.DataFrame()
    all_dfs = []
    for f in files:
        try:
            df = pd.read_parquet(f) if f.endswith('.parquet') else pd.read_csv(f, encoding='utf-8-sig')
            df.columns = [str(c).replace(" ", "").replace("\n", "").strip() for c in df.columns]
            id_col = next((c for c in df.columns if '代號' in c), None)
            if id_col:
                df = df.rename(columns={id_col: 'stock_code'})
                df['stock_code'] = df['stock_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                all_dfs.append(df)
        except: continue
    if not all_dfs: return pd.DataFrame()
    combined = pd.concat(all_dfs, ignore_index=True)
    date_col = next((c for c in combined.columns if '日期' in c), None)
    if date_col:
        combined[date_col] = combined[date_col].astype(str).str.strip()
        combined = combined[combined[date_col] == combined[date_col].max()]
        
    t_cols = {'外資買賣超張數': 'B2_外資買賣超(張)', '投信買賣超張數': 'B2_投信買賣超(張)', '自營買賣超張數': 'B2_自營買賣超(張)', '合計買賣超張數': 'B2_三大法人買賣超(張)'}
    keep, rename = ['stock_code'], {}
    for raw, new in t_cols.items():
        if raw in combined.columns:
            keep.append(raw); rename[raw] = new
            combined[raw] = pd.to_numeric(combined[raw], errors='coerce').fillna(0)
    return combined[keep].rename(columns=rename).copy()

def process_b3_continuous(files):
    if not files: return pd.DataFrame()
    f_day = [f for f in files if "日" in os.path.basename(f) and "週" not in os.path.basename(f)]
    f_week = [f for f in files if "週" in os.path.basename(f) or "wk" in os.path.basename(f).lower()]
    
    def proc_sub(sub_files, is_daily):
        if not sub_files: return pd.DataFrame()
        latest = sorted([extract_date_from_name(f) for f in sub_files], reverse=True)[0]
        latest_files = [f for f in sub_files if extract_date_from_name(f) == latest]
        
        all_dfs = []
        for f in latest_files:
            try:
                df = pd.read_csv(f, encoding='utf-8-sig')
                df.columns = [str(c).replace(" ", "").replace("\n", "").strip() for c in df.columns]
                id_col = next((c for c in df.columns if '代號' in c), df.columns[0])
                df = df.rename(columns={id_col: 'stock_code'})
                df['stock_code'] = df['stock_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                all_dfs.append(df)
            except: continue
        if not all_dfs: return pd.DataFrame()
        combined = pd.concat(all_dfs, ignore_index=True).drop_duplicates(subset=['stock_code'], keep='first')
        
        cols, rename = ['stock_code'], {}
        for inst in ['外資', '投信', '自營商', '三大法人']:
            t_col, v_col, pv_col, pi_col = f"{inst}連續買賣{'日' if is_daily else '週'}數", f"{inst}連續買賣張數", f"{inst}連續買賣佔成交(%)", f"{inst}連續買賣佔發行量(%)"
            if t_col in combined.columns: cols.append(t_col); rename[t_col] = f"B3_{inst}連買{'日' if is_daily else '週'}數"
            if v_col in combined.columns: cols.append(v_col); rename[v_col] = f"B3_{inst}連買{'日' if is_daily else '週'}張數"
            if pv_col in combined.columns: cols.append(pv_col); rename[pv_col] = f"B3_{inst}連買{'日' if is_daily else '週'}佔成交(%)"
            if pi_col in combined.columns: cols.append(pi_col); rename[pi_col] = f"B3_{inst}連買{'日' if is_daily else '週'}佔發行(%)"
                
        df_res = combined[cols].rename(columns=rename).copy()
        
        for inst in ['外資', '投信', '自營商', '三大法人']:
            col = f"B3_{inst}連買{'日' if is_daily else '週'}數"
            if col in df_res.columns:
                df_res[col] = pd.to_numeric(df_res[col], errors='coerce').fillna(0)
                for pct in [f"B3_{inst}連買{'日' if is_daily else '週'}佔成交(%)", f"B3_{inst}連買{'日' if is_daily else '週'}佔發行(%)"]:
                    if pct in df_res.columns: df_res[pct] = pd.to_numeric(df_res[pct], errors='coerce').fillna(0.0)
                conds = [df_res[col] >= 10, df_res[col] >= 5, df_res[col] > 0, df_res[col] <= -10, df_res[col] <= -5, df_res[col] < 0]
                choices = ["🔥 波段認養", "⚡ 買盤點火", "🆕 試單觀察", "☠️ 終極棄養", "🩸 賣盤連環", "📉 試單轉賣"] if is_daily else ["👑 長線主控", "🚀 趨勢加溫", "🌱 週線發動", "🕳 長線棄守", "⚠️ 趨勢破底", "🥀 週線轉弱"]
                df_res[f"B3_{inst}{'日' if is_daily else '週'}連買動態"] = np.select(conds, choices, default="⚪ 無連續動作")
        return df_res

    df_d, df_w = proc_sub(f_day, True), proc_sub(f_week, False)
    if not df_d.empty and not df_w.empty: return pd.merge(df_d, df_w, on='stock_code', how='outer')
    return df_d if not df_d.empty else df_w

def process_b2_b3_features(DATA_DIR):
    print("▶️ [3/5] 開始處理 B2/B3 法人佔比與連續買賣...")
    f_21 = glob.glob(os.path.join(DATA_DIR, "*外資買超佔成交比*.csv")) + glob.glob(os.path.join(DATA_DIR, "*外資賣超佔成交比*.csv"))
    f_22 = glob.glob(os.path.join(DATA_DIR, "*投信買超佔成交比*.csv")) + glob.glob(os.path.join(DATA_DIR, "*投信賣超佔成交比*.csv"))
    f_23 = glob.glob(os.path.join(DATA_DIR, "*外資買超佔發行張數*.csv")) + glob.glob(os.path.join(DATA_DIR, "*外資賣超佔發行張數*.csv"))
    f_24 = glob.glob(os.path.join(DATA_DIR, "*投信買超佔發行張數*.csv")) + glob.glob(os.path.join(DATA_DIR, "*投信賣超佔發行張數*.csv"))
    f_25, f_26 = glob.glob(os.path.join(DATA_DIR, "*外資賣出佔成交比*.csv")), glob.glob(os.path.join(DATA_DIR, "*投信賣出佔成交比*.csv"))
    f_27 = glob.glob(os.path.join(DATA_DIR, "*三大法人買超佔成交比*.csv")) + glob.glob(os.path.join(DATA_DIR, "*三大法人賣超佔成交比*.csv"))
    f_vol = glob.glob(os.path.join(DATA_DIR, "*三大法人累計買超*.parquet")) + glob.glob(os.path.join(DATA_DIR, "*三大法人累計買超*.csv"))
    f_b3 = glob.glob(os.path.join(DATA_DIR, "*連續買*.csv"))
    
    dfs = [
        process_b2_category(f_21, "外資", "買賣超佔成交", "成交", False),
        process_b2_category(f_22, "投信", "買賣超佔成交", "成交", False),
        process_b2_category(f_23, "外資", "買賣超佔發行", "發行", False),
        process_b2_category(f_24, "投信", "買賣超佔發行", "發行", False),
        process_b2_category(f_25, "外資賣出", "賣出佔成交", "成交", True),
        process_b2_category(f_26, "投信賣出", "賣出佔成交", "成交", True),
        process_b2_category(f_27, "三大法人", "買賣超佔成交", "成交", False),
        process_institutional_volume(f_vol),
        process_b3_continuous(f_b3)
    ]
    dfs = [d for d in dfs if not d.empty]
    if not dfs: return None
    
    master_b23 = dfs[0]
    for d in dfs[1:]: master_b23 = pd.merge(master_b23, d, on='stock_code', how='outer')
    
    master_b23 = master_b23.fillna({c: "⚪ 榜外/無資料" for c in master_b23.columns if '動態' in c})
    master_b23 = master_b23.fillna({c: 0.0 for c in master_b23.columns if '連買' in c and ('數' in c or '佔' in c)})
    return master_b23

# ==========================================
# 模組四：B4 資券多空淨值特徵 (融資、借券、融券)
# ==========================================
def process_b4_dynamic_category(files, category_name, val_indicator, unit_suffix):
    if not files: return pd.DataFrame()
    date_files = defaultdict(list)
    for f in files: date_files[extract_date_from_name(f)].append(f)
    sorted_dates = sorted(date_files.keys(), reverse=True)[:10] 
    
    base_df = None
    timeframes = ['當日', '2日', '3日', '5日', '10日', '1個月', '3個月', '半年']
    
    for idx, d in enumerate(sorted_dates):
        daily_dfs = []
        for f in date_files[d]:
            try:
                df = pd.read_csv(f, encoding='utf-8-sig')
                df.columns = [str(c).replace(" ", "").replace("\n", "").strip() for c in df.columns]
                id_col = next((c for c in df.columns if '代號' in c), df.columns[0])
                df = df.rename(columns={id_col: 'stock_code'})
                df['stock_code'] = df['stock_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                daily_dfs.append(df)
            except: continue
            
        if not daily_dfs: continue
        df_combined = pd.concat(daily_dfs, ignore_index=True).drop_duplicates(subset=['stock_code'], keep='first')
        
        col_mapping = {next((c for c in df_combined.columns if tf in c and val_indicator in c), None): f'B4_{category_name}_{tf}增減{unit_suffix}' for tf in timeframes}
        col_mapping = {k: v for k, v in col_mapping.items() if k}
        
        if idx == 0:
            cols_to_keep = ['stock_code'] + [c for c in col_mapping.keys() if c in df_combined.columns]
            base_df = df_combined[cols_to_keep].rename(columns=col_mapping).copy()
        else:
            if base_df is not None:
                new_codes = df_combined[~df_combined['stock_code'].isin(base_df['stock_code'])][['stock_code']].copy()
                for new_col in col_mapping.values(): new_codes[new_col] = np.nan
                base_df = pd.concat([base_df, new_codes], ignore_index=True)

    if base_df is None or base_df.empty: return pd.DataFrame()
    
    for c in [c for c in base_df.columns if '增減' in c]:
        base_df[c] = pd.to_numeric(base_df[c].astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False), errors='coerce')
        
    return base_df

def process_b4_features(DATA_DIR):
    print("▶️ [4/5] 開始處理 B4 信用交易資券籌碼...")
    f_margin_v = glob.glob(os.path.join(DATA_DIR, "*融資*張數*.csv"))
    f_margin_p = glob.glob(os.path.join(DATA_DIR, "*融資*幅度*.csv"))
    f_sbl_v = glob.glob(os.path.join(DATA_DIR, "*借券賣出*張數*.csv"))
    f_sbl_a = glob.glob(os.path.join(DATA_DIR, "*借券賣出*金額*.csv"))
    f_sbl_p = glob.glob(os.path.join(DATA_DIR, "*借券賣出*幅度*.csv"))
    f_short_v = glob.glob(os.path.join(DATA_DIR, "*融券*張數*.csv"))
    f_short_p = glob.glob(os.path.join(DATA_DIR, "*融券*幅度*.csv"))
    
    df_mg_v = process_b4_dynamic_category(f_margin_v, "融資", "張數", "(張)")
    df_mg_p = process_b4_dynamic_category(f_margin_p, "融資", "%", "(%)")
    df_sbl_v = process_b4_dynamic_category(f_sbl_v, "借券賣出", "張數", "(張)")
    df_sbl_a = process_b4_dynamic_category(f_sbl_a, "借券賣出", "萬元", "(萬)")
    df_sbl_p = process_b4_dynamic_category(f_sbl_p, "借券賣出", "%", "(%)")
    df_sh_v = process_b4_dynamic_category(f_short_v, "融券", "張數", "(張)")
    df_sh_p = process_b4_dynamic_category(f_short_p, "融券", "%", "(%)")
    
    dfs = [df for df in [df_mg_v, df_mg_p, df_sbl_v, df_sbl_a, df_sbl_p, df_sh_v, df_sh_p] if not df.empty]
    if not dfs: return None
        
    master_b4 = dfs[0]
    for df in dfs[1:]: master_b4 = pd.merge(master_b4, df, on='stock_code', how='outer')
        
    def get_margin_tag(row):
        v_tdy, v_5d, p_5d = row.get('B4_融資_當日增減(張)', np.nan), row.get('B4_融資_5日增減(張)', np.nan), row.get('B4_融資_5日增減(%)', np.nan)
        if pd.isna(v_tdy) and pd.isna(v_5d): return "⚪ 榜外無動靜"
        if v_tdy > 0: return "📈 散戶大舉進場" if v_tdy > 1000 or (not pd.isna(p_5d) and p_5d > 5) else "⚠️ 融資漸增"
        if v_tdy < 0: return "📉 浮額大洗盤" if v_tdy < -1000 or (not pd.isna(p_5d) and p_5d < -5) else "🛡️ 融資收斂"
        if v_5d > 0: return "⚠️ 融資累積中"
        if v_5d < 0: return "🛡️ 籌碼沉澱"
        return "🔄 持平"

    def get_sbl_tag(row):
        v_tdy, a_5d, p_5d = row.get('B4_借券賣出_當日增減(張)', np.nan), row.get('B4_借券賣出_5日增減(萬)', np.nan), row.get('B4_借券賣出_5日增減(%)', np.nan)
        if pd.isna(v_tdy) and pd.isna(a_5d): return "⚪ 空單休兵"
        if v_tdy > 0: return "⚠️ 空軍大舉佈局" if (not pd.isna(a_5d) and a_5d > 5000) or (not pd.isna(p_5d) and p_5d > 10) else "🚨 借券漸增"
        if v_tdy < 0: return "💥 巨量借券回補" if (not pd.isna(a_5d) and a_5d < -5000) or (not pd.isna(p_5d) and p_5d < -10) else "🔥 緩步回補"
        if a_5d > 0: return "🚨 外資潛伏空單"
        if a_5d < 0: return "🔥 波段回補中"
        return "🔄 持平"

    def get_short_tag(row):
        v_tdy, v_5d, p_5d = row.get('B4_融券_當日增減(張)', np.nan), row.get('B4_融券_5日增減(張)', np.nan), row.get('B4_融券_5日增減(%)', np.nan)
        if pd.isna(v_tdy) and pd.isna(v_5d): return "⚪ 空軍休兵"
        if v_tdy > 0: return "⚠️ 散戶大舉放空" if v_5d > 1000 or (not pd.isna(p_5d) and p_5d > 20) else "🚨 融券漸增"
        if v_tdy < 0: return "💥 融券斷頭回補" if v_5d < -1000 or (not pd.isna(p_5d) and p_5d < -20) else "🔥 融券退場"
        if v_5d > 0: return "🚨 融券累積中"
        if v_5d < 0: return "🔥 波段回補中"
        return "🔄 持平"

    master_b4['B4_融資動態'] = master_b4.apply(get_margin_tag, axis=1)
    master_b4['B4_借券賣出動態'] = master_b4.apply(get_sbl_tag, axis=1)
    master_b4['B4_融券動態'] = master_b4.apply(get_short_tag, axis=1)
    
    master_b4['B4_軋空_融資大減'] = (master_b4.get('B4_融資_5日增減(張)', 0) <= -1000).map({True: '✔️', False: ''})
    master_b4['B4_軋空_借券回補'] = (master_b4.get('B4_借券賣出_5日增減(萬)', 0) <= -1000).map({True: '✔️', False: ''})
    master_b4['B4_軋空_融券大增'] = (master_b4.get('B4_融券_5日增減(張)', 0) >= 500).map({True: '✔️', False: ''})
    master_b4['B4_套牢_融資大增'] = (master_b4.get('B4_融資_5日增減(張)', 0) >= 1000).map({True: '✔️', False: ''})
    master_b4['B4_套牢_借券大增'] = (master_b4.get('B4_借券賣出_5日增減(萬)', 0) >= 1000).map({True: '✔️', False: ''})

    return master_b4

# ==========================================
# 模組五：大一統合併與終極精算 (包含反碎片化與重排序)
# ==========================================
def run_master_pipeline():
    DATA_DIR, OUTPUT_DIR = "./data", "./data_cache"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    df_b0, date_prefix = process_b0_features(DATA_DIR, OUTPUT_DIR)
    
    if df_b0 is None:
        return print("❌ 缺少 B0 基礎檔案，合併失敗。")
        
    print(f"▶ [5/5] 執行大一統合併與防呆淨化 (目標交易日: {date_prefix})...")
    
    df_b1 = process_b1_features(DATA_DIR, target_date=date_prefix)
    df_b23 = process_b2_b3_features(DATA_DIR)
    df_b4 = process_b4_features(DATA_DIR)
    
    drop_targets = ['股票代號', '股票名稱', '證券代號', '證券名稱', '名稱', '日期', '排名']
    for df in [df_b0, df_b1, df_b23, df_b4]:
        if df is not None:
            df.drop(columns=[c for c in drop_targets if c in df.columns], inplace=True, errors='ignore')

    # === 合併主體 ===
    df_master = df_b0.copy()
    if df_b1 is not None: df_master = pd.merge(df_master, df_b1, on='stock_code', how='left')
    if df_b23 is not None: df_master = pd.merge(df_master, df_b23, on='stock_code', how='left')
    if df_b4 is not None: df_master = pd.merge(df_master, df_b4, on='stock_code', how='left')
    
    cols_to_drop = [c for c in df_master.columns if c.endswith('_x') or c.endswith('_y')]
    if cols_to_drop: df_master.drop(columns=cols_to_drop, inplace=True)
    
    vol_mapping = {
        'B1_外資買賣超張數': 'B2_外資買賣超(張)',
        'B1_投信買賣超張數': 'B2_投信買賣超(張)',
        'B1_自營買賣超張數': 'B2_自營買賣超(張)',
        'B1_合計買賣超張數': 'B2_三大法人買賣超(張)'
    }
    for b1_col, b2_col in vol_mapping.items():
        if b1_col in df_master.columns and b2_col in df_master.columns:
            df_master[b1_col] = df_master[b1_col].combine_first(df_master[b2_col])
            df_master.drop(columns=[b2_col], inplace=True)
        elif b2_col in df_master.columns:
            df_master.rename(columns={b2_col: b1_col}, inplace=True)

    # 🛡️ 解決 pandas 效能警告 (Highly fragmented)
    df_master = df_master.copy()

    # === 🚀 最精準的法人金額計算 (單位：萬) ===
    if 'B1_合計買賣超張數' in df_master.columns and '成交' in df_master.columns:
        df_master['B1_1日法人金額(萬)'] = (df_master['B1_合計買賣超張數'] * df_master['成交']) / 10
        
    if '估算總發行張數' in df_master.columns:
        for d in [5, 20, 60, 120]:
            if f'B1_{d}日△Change' in df_master.columns and f'{d}日均價' in df_master.columns:
                df_master[f'B1_{d}日法人金額(萬)'] = (df_master['估算總發行張數'] * (df_master[f'B1_{d}日△Change'] / 100) * df_master[f'{d}日均價']) / 10

    # 🧩 欄位智慧重排 (B0 -> B1 -> B2 -> B3 -> B4)
    base_and_b0 = [c for c in df_master.columns if not re.match(r'^B[1234]_', c)]
    b1_cols = [c for c in df_master.columns if c.startswith('B1_')]
    b2_cols = [c for c in df_master.columns if c.startswith('B2_')]
    b3_cols = [c for c in df_master.columns if c.startswith('B3_')]
    b4_cols = [c for c in df_master.columns if c.startswith('B4_')]
    
    ordered_cols = base_and_b0 + b1_cols + b2_cols + b3_cols + b4_cols
    missing_cols = [c for c in df_master.columns if c not in ordered_cols]
    df_master = df_master[ordered_cols + missing_cols]

    out_parquet, out_csv = f"{OUTPUT_DIR}/{date_prefix}_master_features.parquet", f"{OUTPUT_DIR}/{date_prefix}_master_features.csv"
    df_master.to_parquet(out_parquet, index=False)
    
    # 已經幫你把編碼改回 utf-8-sig 讓你方便使用 Excel 檢查了！
    df_master.to_csv(out_csv, index=False, encoding='utf-8-sig')
    
    print(f"\n🎉 完美大一統 B0~B4 ETL 執行完畢！")
    print(f"📊 總計產生 {len(df_master)} 筆股票資料，已橫跨基礎量價、籌碼軌跡、連續動能與資券軋空等多維度。")
    print(f"📁 檔案已存至：\n  - {out_parquet}\n  - {out_csv}")

if __name__ == "__main__":
    run_master_pipeline()
