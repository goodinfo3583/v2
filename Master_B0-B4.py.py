# master_etl_pipeline.py (B0-B4 拔除 B3 零值偏誤版)
import pandas as pd
import numpy as np
import os
import glob
import re
import json
import requests
import datetime
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
    
    clean_date = latest_date.replace('/', '').replace('-', '')
    if len(clean_date) == 4:
        target_date = str(datetime.datetime.now().year) + clean_date
    elif len(clean_date) >= 8:
        target_date = clean_date[-8:]
        if not target_date.startswith("202"):
            target_date = str(datetime.datetime.now().year) + clean_date[-4:]
    else:
        target_date = str(datetime.datetime.now().year) + clean_date[-4:]
    
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
    status_map = {"放量大漲":"🚀 放量大漲", "縮量大漲":"🔒 縮量大漲", "平量大漲":"✈️ 平量大漲", "縮量價升":"📈 價升量縮", "放量滯漲":"⚠️ 放量滯漲", "平量滯漲":"⏸ 平量滯漲", "縮量小跌":"📉 縮量小跌", "放量小跌":"🛡️ 放量小跌", "平量小跌":"🥀 平量價縮", "縮量大跌":"☠ 縮量大跌", "放量大跌":"🩸 放量大跌", "平量大跌":"🕳 平量大跌"}
    df_today['B0_量價狀態'] = pd.Series(v_s + p_s).map(status_map).fillna("⚖ 溫和震盪整理").values

    t_amt, m5, m10, m20 = df_today['今日成交額(萬)'].fillna(0), df_today['5日均額(萬)'].fillna(0), df_today['10日均額(萬)'].fillna(0), df_today['20日均額(萬)'].fillna(0)
    v = (m5 > 0) & (m10 > 0) & (m20 > 0)
    df_today['資金延續趨勢'] = np.select([v & (m5 > m10) & (m10 > m20), v & (t_amt > m5) & (m5 <= m10), v & (m5 < m10) & (m10 < m20), v], ["🔥 資金湧入", "⚡ 單日點火", "💧 資金退潮", "⚖️ 震盪換手"], default="⚪ 資料不足")

    base_cols = ['stock_code', 'stock_name', 'trade_date', '成交', '漲跌幅', 'PER', 'PBR', '成交張數_num', '今日成交額(萬)', '成交金額日變化率(%)', 'B0_量價狀態', 'B0_特殊型態', '資金延續趨勢']
    dynamic_cols = []
    for p in periods: dynamic_cols.extend([f'{p}日均價', f'{p}日均額(萬)', f'{p}日均量(張)', f'較{p}日均額增加(萬)', f'{p}日爆發倍數'])
        
    return df_today[[c for c in (base_cols + dynamic_cols) if c in df_today.columns]].copy(), target_date

# ==========================================
# 模組二：B1 法人軌跡與籌碼結構運算
# ==========================================
def process_b1_features(DATA_DIR, target_date):
    print(f"▶️️ [2/5] 開始處理 B1 法人軌跡與籌碼結構 (對齊基準日: {target_date})...")
    
    def get_aligned_history(files):
        valid = sorted([f for f in files if extract_date_from_name(f) <= target_date], key=extract_date_from_name, reverse=True)
        if not valid or extract_date_from_name(valid[0]) != target_date:
            return [] 
        return valid

    f_up_history = get_aligned_history(glob.glob(os.path.join(DATA_DIR, "*JSON_History.csv")))
    f_down_history = get_aligned_history(glob.glob(os.path.join(DATA_DIR, "*Down_History.csv")))
    f_foreign_ratio = get_aligned_history(glob.glob(os.path.join(DATA_DIR, "*外資持股比例*.parquet")) + glob.glob(os.path.join(DATA_DIR, "*外資持股比例*.csv")))
    
    df_up, df_down, df_fi, d_cols = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), []
    
    for i, file in enumerate(f_up_history[:4]):
        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
            df.columns = [str(c).replace(" ", "").strip() for c in df.columns]
            df['stock_code'] = df['股票代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)
            if i == 0:
                df.rename(columns={'法人持股': 'B1_正向_法人持股(%)', '上榜區塊': 'B1_正向上榜區塊'}, inplace=True)
                df_up, d_cols = df, ['B1_正向_法人持股(%)']
            else:
                col_name, sec_name = f'持股%_{i}', f'區塊_{i}'
                df = df[['stock_code', '法人持股', '上榜區塊']].rename(columns={'法人持股': col_name, '上榜區塊': sec_name}) if '上榜區塊' in df.columns else df[['stock_code', '法人持股']].assign(上榜區塊="").rename(columns={'法人持股': col_name, '上榜區塊': sec_name})
                df_up = pd.merge(df_up, df, on='stock_code', how='left')
                d_cols.append(col_name)
        except Exception: pass
    for c in d_cols: df_up[c] = pd.to_numeric(df_up[c], errors='coerce')

    for i, file in enumerate(f_down_history[:2]):
        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
            df.columns = [str(c).replace(" ", "").strip() for c in df.columns]
            df['stock_code'] = df['股票代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)
            if i == 0:
                df.rename(columns={'法人持股': 'B1_衰退_法人持股(%)', '上榜區塊': 'B1_負向上榜區塊', '累積衰退': 'B1_累積衰退(%)'}, inplace=True)
                df_down = df
            else:
                df_t1 = df[['stock_code', '法人持股']].rename(columns={'法人持股': 'B1_衰退_法人持股(%)_T1'})
                df_down = pd.merge(df_down, df_t1, on='stock_code', how='left')
        except Exception: pass

    for i, file in enumerate(f_foreign_ratio[:2]):
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
                    df_fi = pd.merge(df_fi, df_t1, on='stock_code', how='left')
        except Exception: pass

    dfs = [df for df in [df_up, df_down, df_fi] if not df.empty]
    if not dfs: return None
    master_b1 = dfs[0]
    for df in dfs[1:]: master_b1 = pd.merge(master_b1, df, on='stock_code', how='outer')

    master_b1['B1_正向上榜區塊'] = master_b1.get('B1_正向上榜區塊', pd.Series(dtype=str)).fillna("")
    master_b1['B1_負向上榜區塊'] = master_b1.get('B1_負向上榜區塊', pd.Series(dtype=str)).fillna("")
    master_b1['B1_總法人持股(%)'] = master_b1.get('B1_正向_法人持股(%)', pd.Series(dtype=float)).combine_first(master_b1.get('B1_衰退_法人持股(%)', pd.Series(dtype=float)))
    
    yesterday_holding = master_b1.get('持股%_1', pd.Series(np.nan, index=master_b1.index)).combine_first(
        master_b1.get('B1_衰退_法人持股(%)_T1', pd.Series(np.nan, index=master_b1.index))
    )
    master_b1['B1_1日△Change'] = np.where(
        master_b1['B1_總法人持股(%)'].notna() & yesterday_holding.notna() & (yesterday_holding > 0),
        master_b1['B1_總法人持股(%)'] - yesterday_holding,
        np.nan
    )

    if 'B1_外資持股(%)' in master_b1.columns:
        master_b1['B1_估內資持股(%)'] = (master_b1['B1_總法人持股(%)'] - master_b1['B1_外資持股(%)']).clip(lower=0)
        if 'B1_外資持股(%)_T1' in master_b1.columns: 
            master_b1['B1_外資1日△Change'] = np.where(
                master_b1['B1_外資持股(%)'].notna() & master_b1['B1_外資持股(%)_T1'].notna() & (master_b1['B1_外資持股(%)_T1'] > 0),
                master_b1['B1_外資持股(%)'] - master_b1['B1_外資持股(%)_T1'],
                np.nan
            )

    json_dfs = fetch_github_json_all()
    for d in [5, 20, 60, 120]:
        if d in json_dfs and not json_dfs[d].empty: master_b1 = pd.merge(master_b1, json_dfs[d], on='stock_code', how='left')
        else: master_b1[f'B1_{d}日△Change'] = master_b1[f'B1_{d}日排名'] = np.nan

    if 'B1_外資持有(千張)' in master_b1.columns and 'B1_外資持股(%)' in master_b1.columns:
        master_b1['估算總發行張數'] = np.where(master_b1['B1_外資持股(%)'] > 0, (master_b1['B1_外資持有(千張)'] * 1000) / (master_b1['B1_外資持股(%)'] / 100), np.nan)

    master_b1['B1_法人軌跡動態'] = master_b1.apply(lambda r: "⚠️ 多空交戰 (籌碼分歧)" if str(r.get('B1_正向上榜區塊', '')) and str(r.get('B1_負向上榜區塊', '')) else ("👑 長線吸籌" if '120日' in str(r.get('B1_正向上榜區塊', '')) or '60日' in str(r.get('B1_正向上榜區塊', '')) else ("🔥 波段佈局" if '20日' in str(r.get('B1_正向上榜區塊', '')) else "🚀 短線點火")) if str(r.get('B1_正向上榜區塊', '')) else ("☠️ 長線提款" if '30日' in str(r.get('B1_負向上榜區塊', '')) or '20日' in str(r.get('B1_負向上榜區塊', '')) else "🩸 短線棄守") if str(r.get('B1_負向上榜區塊', '')) else "⚪ 無明顯軌跡", axis=1)

    cols_drop = [c for c in d_cols if c != 'B1_正向_法人持股(%)'] + ['區塊_1', '區塊_2', '區塊_3', 'B1_衰退_法人持股(%)_T1', 'B1_總法人持股(%)_T1', 'B1_外資持股(%)_T1']
    master_b1.drop(columns=[c for c in cols_drop if c in master_b1.columns], inplace=True)
    return master_b1


# ==========================================
# 模組三：B2/B3 法人佔比與連續買賣運算 (已修正零值偏誤)
# ==========================================
def process_b2_category(files, category_name, base_keyword, short_type, is_sell_only, target_date):
    if not files: return pd.DataFrame()
    date_files = defaultdict(list)
    for f in files: 
        d = extract_date_from_name(f)
        if d <= target_date: date_files[d].append(f)
        
    sorted_dates = sorted(date_files.keys(), reverse=True)[:10] 
    
    if not sorted_dates or sorted_dates[0] != target_date: return pd.DataFrame()
    
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
    for c in [c for c in base_df.columns if '(%)' in c]: base_df[c] = pd.to_numeric(base_df[c], errors='coerce') # 這裡保留NaN，不補0
    
    c_tdy, c_5d = f'B2_{category_name}_當日佔{short_type}(%)', f'B2_{category_name}_5日佔{short_type}(%)'
    def eval_cont(row):
        t, v5 = row.get(c_tdy, np.nan), row.get(c_5d, np.nan)
        if pd.isna(t) and pd.isna(v5): return "⚪ 榜外/無資料"
        if is_sell_only:
            if pd.isna(t) and v5 > 0: return "📈 掉出賣榜 (賣壓減輕)"
            if pd.isna(v5) and t > 0: return "⚠️ 突擊賣榜 (警戒賣壓)"
            if t > 0: return "🚨 賣壓加劇" if t > v5 else "📉 賣壓趨緩"
            return "🔄 持平"
        else:
            if pd.isna(t): return "📉 掉出買榜 (籌碼鬆動)" if v5 > 0 else "📈 掉出賣榜 (賣壓減輕)" if v5 < 0 else "⚪ 榜外/無資料"
            if pd.isna(v5): return "🆕 突擊買榜" if t > 0 else "⚠️ 突擊賣榜" if t < 0 else "🔄 持平"
            if t > 0: return "🔥 轉賣為買 (強力反轉)" if v5 < 0 else "🔥 強延續" if t > v5 else "⚠️ 買盤趨緩"
            if t < 0: return "🚨 轉買為賣 (提防倒貨)" if v5 > 0 else "🚨 劇烈倒貨" if abs(t) > abs(v5) else "📉 調節洗盤"
            return "🔄 持平"
    base_df[f'B2_{category_name}{short_type}動態'] = base_df.apply(eval_cont, axis=1)
    return base_df

def process_institutional_volume(files, target_date):
    valid_files = [f for f in files if extract_date_from_name(f) == target_date]
    if not valid_files: return pd.DataFrame()
    
    all_dfs = []
    for f in valid_files:
        try:
            df = pd.read_parquet(f) if f.endswith('.parquet') else pd.read_csv(f, encoding='utf-8-sig')
            df.columns = [str(c).replace(" ", "").replace("\n", "").strip() for c in df.columns]
            id_col = next((c for c in df.columns if '代號' in c), None)
            if id_col:
                df = df.rename(columns={id_col: 'stock_code'})
                df['stock_code'] = df['stock_code'].astype(str).
