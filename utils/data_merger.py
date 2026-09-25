# utils/data_merger.py
import pandas as pd
import glob
import os
import re

def merge_and_convert_daily_data(data_dir, date_str):
    """
    自動尋找當日碎裂的 CSV，合併清理後存成超高速的 Parquet 格式。
    date_str: 8碼日期字串，例如 '20260828'
    """
    print(f"\n🚀 [資料轉化引擎] 開始整併 {date_str} 的碎裂檔案...")
    
    # ---------------------------------------------------------
    # 🎯 任務 1：處理【成交價】碎裂檔案 (1-300名, 301-600名...)
    # ---------------------------------------------------------
    price_pattern = os.path.join(data_dir, f"{date_str}成交價*.csv")
    price_files = glob.glob(price_pattern)
    
    if price_files:
        df_list = []
        for f in price_files:
            for enc in ['utf-8-sig', 'big5', 'cp950', 'utf-8']:
                try:
                    df = pd.read_csv(f, encoding=enc, header=0, dtype=str)
                    df_list.append(df)
                    break
                except Exception:
                    pass
        
        if df_list:
            master_df = pd.concat(df_list, ignore_index=True)
            master_df.columns = [re.sub(r'[\s\n\r\t\u3000\ufeff]+', '', str(c)) for c in master_df.columns]
            
            c_code = next((c for c in master_df.columns if '代號' in c), None)
            if c_code:
                master_df['統一代號'] = master_df[c_code].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
            numeric_cols = ['成交', '漲跌價', '漲跌幅', '成交張數', '成交額(百萬)', 'PER']
            for col in numeric_cols:
                actual_col = next((c for c in master_df.columns if col in c), None)
                if actual_col:
                    master_df[actual_col] = pd.to_numeric(
                        master_df[actual_col].astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False),
                        errors='coerce'
                    )
            
            if '統一代號' in master_df.columns:
                master_df = master_df.drop_duplicates(subset=['統一代號'], keep='first')
            
            parquet_path = os.path.join(data_dir, f"{date_str}_Merged_成交價.parquet")
            master_df.to_parquet(parquet_path, engine='pyarrow')
            print(f"  ✅ 成功將 {len(price_files)} 個成交價 CSV 整併為: {os.path.basename(parquet_path)}")
            
            # 🔥 縫合成功後，殺掉原本的碎肉檔案，保持資料夾乾淨！
            for f in price_files:
                os.remove(f)

    # ---------------------------------------------------------
    # 🎯 任務 2：處理【外資持股比例】碎裂檔案 (1-300名, 301-600名...)
    # ---------------------------------------------------------
    foreign_pattern = os.path.join(data_dir, f"{date_str}外資持股比例*.csv")
    foreign_files = glob.glob(foreign_pattern)
    
    if foreign_files:
        df_list = []
        for f in foreign_files:
            for enc in ['utf-8-sig', 'big5', 'cp950', 'utf-8']:
                try:
                    df = pd.read_csv(f, encoding=enc, header=0, dtype=str)
                    df_list.append(df)
                    break
                except Exception:
                    pass
        
        if df_list:
            master_df = pd.concat(df_list, ignore_index=True)
            master_df.columns = [re.sub(r'[\s\n\r\t\u3000\ufeff]+', '', str(c)) for c in master_df.columns]
            
            c_code = next((c for c in master_df.columns if '代號' in c), None)
            if c_code:
                master_df['統一代號'] = master_df[c_code].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
            # 外資持股表通常只有一個需要轉數字的欄位
            c_ratio = next((c for c in master_df.columns if '外資持股(%)' in c or '持股比例' in c), None)
            if c_ratio:
                master_df[c_ratio] = pd.to_numeric(
                    master_df[c_ratio].astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False),
                    errors='coerce'
                )
            
            if '統一代號' in master_df.columns:
                master_df = master_df.drop_duplicates(subset=['統一代號'], keep='first')
            
            parquet_path = os.path.join(data_dir, f"{date_str}_Merged_外資持股.parquet")
            master_df.to_parquet(parquet_path, engine='pyarrow')
            print(f"  ✅ 成功將 {len(foreign_files)} 個外資持股 CSV 整併為: {os.path.basename(parquet_path)}")
            
            # 🔥 縫合成功後，殺掉原本的碎肉檔案，保持資料夾乾淨！
            for f in foreign_files:
                os.remove(f)

    print("✨ 當日資料整併與轉換全數完成！\n")

if __name__ == "__main__":
    # 給你手動測試用，這裡隨便寫個日期不會有事，找不到檔案它就不會動
    merge_and_convert_daily_data("../data", "20260904")
