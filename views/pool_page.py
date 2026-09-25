# newdaily1820_scrper.py
import time
import random
import pandas as pd
import os
import requests
import glob
from io import StringIO
from datetime import datetime
from selenium.webdriver.common.by import By
from seleniumbase import Driver
import subprocess
import re

# ==========================================
# 1. 基本設定區塊 
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

SAVE_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

today = datetime.now().strftime("%Y%m%d")
taifex_date = datetime.now().strftime("%Y/%m/%d")

print(f"啟動爬蟲系統，目標日期：{today}\n" + "="*40)

# ==========================================
# 🚀 階段一：TWSE 證交所 & TPEx 櫃買中心 API 
# ==========================================
print(">> [階段一] 執行證交所與櫃買中心 API 擷取...")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.tpex.org.tw/',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest'
}

print(f" └─ 🔍 正在向證交所校準「最新交易日」...")
url_cal = f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={today}&response=json"
real_date_str = today 
roc_full_date = f"{int(today[:4]) - 1911}/{today[4:6]}/{today[6:]}" 
roc_month = f"{int(today[:4]) - 1911}/{today[4:6]}" 
res_cal_data = None 

try:
    res_cal = session.get(url_cal, headers=headers, timeout=10, verify=False).json()
    if res_cal.get("stat") == "OK" and "data" in res_cal and len(res_cal["data"]) > 0:
        res_cal_data = res_cal 
        latest_roc_date = res_cal["data"][-1][0]
        parts = latest_roc_date.split('/')
        real_year = int(parts[0]) + 1911
        real_date_str = f"{real_year}{parts[1].zfill(2)}{parts[2].zfill(2)}"
        roc_full_date = latest_roc_date 
        roc_month = f"{parts[0]}/{parts[1].zfill(2)}" 
        print(f"    🎯 校準成功！真實最新交易日為: {real_date_str}")
except Exception as e:
    print(f"    ⚠️ 校準失敗，將使用系統今日日期: {e}")

TWSE_APIS = {
    "大盤上市成交量": url_cal,
    "三大法人買賣超金額": f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?date={real_date_str}&response=json",
    "鉅額交易": f"https://www.twse.com.tw/rwd/zh/block/BFIAUU?date={real_date_str}&selectType=S&response=json",
}

for name, url in TWSE_APIS.items():
    file_path = os.path.join(SAVE_DIR, f"{real_date_str}-{name}.csv")
    print(f" └─ 📡 正在直連抓取: {name}...")
    try:
        if name == "大盤上市成交量" and res_cal_data:
            res = res_cal_data 
        else:
            time.sleep(1.5) 
            res = session.get(url, headers=headers, timeout=10, verify=False).json()
            
        if res.get("stat") == "OK" and "data" in res and len(res["data"]) > 0:
            df = pd.DataFrame(res["data"], columns=res.get("fields", []))
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            print(f"    ✅ 成功存檔！共 {len(df)} 筆資料。")
        else:
            print(f"    ❌ 伺服器回傳無資料。")
    except Exception as e:
        print(f"    ⚠️ 發生錯誤: {e}")

print(f" └─ 📡 正在直連抓取: 大盤上櫃成交量...")
file_path_tpex = os.path.join(SAVE_DIR, f"{real_date_str}-大盤上櫃成交量.csv")

try:
    session.get("https://www.tpex.org.tw/zh-tw/", headers=headers, timeout=5, verify=False)
except: pass

tpex_urls = [
    f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_index/st41_result.php?l=zh-tw&o=json&d={roc_full_date}", 
    f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_index/st41_result.php?l=zh-tw&o=json&d={roc_month}",
    f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_index/st41_result.php?l=zh-tw&o=json"
]

tpex_success = False
for url in tpex_urls:
    time.sleep(1.5) 
    try:
        res = session.get(url, headers=headers, timeout=10, verify=False)
        if res.status_code == 200:
            res_json = res.json()
            if "tables" in res_json and len(res_json["tables"]) > 0 and "data" in res_json["tables"][0]:
                data_list = res_json["tables"][0]["data"]
                if len(data_list) > 0:
                    columns = ["日期", "成交千股", "成交金額(千元)", "成交筆數", "櫃買指數", "漲跌點數"]
                    df = pd.DataFrame(data_list, columns=columns)
                    df.to_csv(file_path_tpex, index=False, encoding='utf-8-sig')
                    print(f"    ✅ 成功存檔！共 {len(df)} 筆資料。")
                    tpex_success = True
                    break
    except Exception: pass 

if not tpex_success:
    print(f"    ❌ 伺服器回傳無資料 (可能是非交易日或伺服器異常)。")

print(f" └─ 📡 正在直連抓取: 鉅額交易(櫃)...")
file_path_block = os.path.join(SAVE_DIR, f"{real_date_str}鉅額交易(櫃).csv")
tpex_block_url = f"https://www.tpex.org.tw/web/stock/aftertrading/block_trading/block_trading_result.php?l=zh-tw&o=json&d={roc_full_date}"

try:
    time.sleep(1.5)
    res = session.get(tpex_block_url, headers=headers, timeout=10, verify=False)
    if res.status_code == 200:
        res_json = res.json()
        if "tables" in res_json and len(res_json["tables"]) > 0 and "data" in res_json["tables"][0]:
            data_list = res_json["tables"][0]["data"]
            if len(data_list) > 0:
                fields = res_json["tables"][0].get("fields", ["日期", "代號", "名稱", "成交價", "成交股數", "成交金額", "配對代號"])
                df = pd.DataFrame(data_list, columns=fields)
                df.to_csv(file_path_block, index=False, encoding='utf-8-sig')
                print(f"    ✅ 成功存檔！共 {len(df)} 筆資料。")
            else: print(f"    ❌ 今日櫃買無鉅額交易資料。")
        else: print(f"    ❌ 伺服器回傳無效的鉅額交易資料格式。")
except Exception as e:
    print(f"    ⚠️ 發生錯誤: {e}")

# ==========================================
# 🚀 階段二：TAIFEX 期交所 HTML 扒表術
# ==========================================
print("\n>> [階段二] 執行期交所網頁解析 (TAIFEX)...")
headers = {'User-Agent': 'Mozilla/5.0'}
real_taifex_date = f"{real_date_str[:4]}/{real_date_str[4:6]}/{real_date_str[6:]}"
print(f" └─ 🕒 智慧校準期交所日期為: {real_taifex_date}")

print(" └─ 📡 正在抓取: 臺指選擇權PC比...")
try:
    res = requests.post("https://www.taifex.com.tw/cht/3/pcRatio", data={"queryStartDate": real_taifex_date, "queryEndDate": real_taifex_date}, headers=headers)
    dfs = pd.read_html(StringIO(res.text))
    for df in dfs:
        if '買賣權未平倉量比率%' in df.columns or (isinstance(df.columns, pd.MultiIndex) and '買賣權未平倉量比率%' in [c[-1] for c in df.columns]):
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(-1)
            df.to_csv(os.path.join(SAVE_DIR, f"{today}-臺指選擇權PC比.csv"), index=False, encoding='utf-8-sig')
            print(f"    ✅ 成功存檔！")
            break
except Exception as e: print(f"    ⚠️ 失敗: {e}")

print(" └─ 📡 正在抓取: 三大法人期貨多空單...")
try:
    res = requests.post("https://www.taifex.com.tw/cht/3/futContractsDate", data={"queryDate": real_taifex_date, "queryType": "1"}, headers=headers)
    dfs = pd.read_html(StringIO(res.text))
    for df in dfs:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [f"{c[0]}_{c[1]}" if c[0] != c[1] else c[0] for c in df.columns]
        if df.astype(str).apply(lambda x: x.str.contains('外資').any()).any():
            df.to_csv(os.path.join(SAVE_DIR, f"{today}-三大法人期貨多空.csv"), index=False, encoding='utf-8-sig')
            print(f"    ✅ 成功存檔！")
            break
except Exception as e: print(f"    ⚠️ 失敗: {e}")

print(" └─ 📡 正在抓取: 臺指選擇權行情簡表...")
try:
    payload = {
        "queryType": "2", 
        "queryDate": real_taifex_date, 
        "MarketCode": "0", 
        "commodity_id": "TXO" 
    }
    res = requests.post("https://www.taifex.com.tw/cht/3/optDailyMarketReport", data=payload, headers=headers)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(res.text, 'html.parser')
    tables = soup.find_all('table')
    target_table = None
    for tb in tables:
        if '履約價' in tb.text:
            target_table = str(tb)
            break
            
    if target_table:
        df = pd.read_html(StringIO(target_table))[0]
        if isinstance(df.columns, pd.MultiIndex):
            new_cols = []
            for c in df.columns:
                valid_parts = []
                for part in c:
                    part_str = str(part).strip()
                    if "Unnamed" not in part_str and part_str not in valid_parts:
                        valid_parts.append(part_str)
                new_cols.append("_".join(valid_parts))
            df.columns = new_cols
        
        strike_col = next((col for col in df.columns if '履約價' in col), None)
        if strike_col:
            df[strike_col] = pd.to_numeric(df[strike_col], errors='coerce')
            df = df.dropna(subset=[strike_col])
            
        if not df.empty:
            df.to_csv(os.path.join(SAVE_DIR, f"{today}臺指選擇權行情簡表.csv"), index=False, encoding='utf-8-sig')
            print(f"    ✅ 成功存檔！共抓取 {len(df)} 筆資料。")
        else: print(f"    ❌ 表格內容為空，可能今日尚未結算。")
    else: print(f"    ❌ 找不到包含「履約價」的資料表格。")
except Exception as e: print(f"    ⚠️ 失敗: {e}")

# ==========================================
# 🐢 階段三：Goodinfo 模擬點擊瀏覽器 (自動重試版)
# ==========================================
GOODINFO_TARGETS = {
    "外資賣出佔成交比(3日累計排名)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E8%B3%A3%E5%87%BA%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94+%E2%80%93+3%E6%97%A5%40%40%E5%A4%96%E8%B3%87%E8%B3%A3%E5%87%BA%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94%40%40%E5%A4%96%E8%B3%87+%E2%80%93+3%E6%97%A5",
    "外資買超佔成交比(5日累計排名)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E8%B2%B7%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94+%E2%80%93+5%E6%97%A5%40%40%E5%A4%96%E8%B3%87%E8%B2%B7%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94%40%40%E5%A4%96%E8%B3%87+%E2%80%93+5%E6%97%A5",
    "外資買超佔發行張數(5日累計排名)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E8%B2%B7%E8%B6%85%E4%BD%94%E7%99%BC%E8%A1%8C%E5%BC%B5%E6%95%B8+%E2%80%93+5%E6%97%A5%40%40%E5%A4%96%E8%B3%87%E8%B2%B7%E8%B6%85%E4%BD%94%E7%99%BC%E8%A1%8C%E5%BC%B5%E6%95%B8%40%40%E5%A4%96%E8%B3%87+%E2%80%93+5%E6%97%A5",
    "投信買超佔成交比(5日累計排名)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%8A%95%E4%BF%A1%E8%B2%B7%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94+%E2%80%93+5%E6%97%A5%40%40%E6%8A%95%E4%BF%A1%E8%B2%B7%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94%40%40%E6%8A%95%E4%BF%A1+%E2%80%93+5%E6%97%A5",
    "投信賣出佔成交比(5日累計排名)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%8A%95%E4%BF%A1%E8%B3%A3%E5%87%BA%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94+%E2%80%93+5%E6%97%A5%40%40%E6%8A%95%E4%BF%A1%E8%B3%A3%E5%87%BA%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94%40%40%E6%8A%95%E4%BF%A1+%E2%80%93+5%E6%97%A5",
    "投信買超佔發行張數(5日累計排名)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%8A%95%E4%BF%A1%E8%B2%B7%E8%B6%85%E4%BD%94%E7%99%BC%E8%A1%8C%E5%BC%B5%E6%95%B8+%E2%80%93+5%E6%97%A5%40%40%E6%8A%95%E4%BF%A1%E8%B2%B7%E8%B6%85%E4%BD%94%E7%99%BC%E8%A1%8C%E5%BC%B5%E6%95%B8%40%40%E6%8A%95%E4%BF%A1+%E2%80%93+5%E6%97%A5",
    "成交價1-300名(高→低)": "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%88%90%E4%BA%A4%E5%83%B9+%28%E9%AB%98%E2%86%92%E4%BD%8E%29%40%40%E6%88%90%E4%BA%A4%E5%83%B9%40%40%E7%94%B1%E9%AB%98%E2%86%92%E4%BD%8E",
    "成交價301-600名(高→低)": "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%88%90%E4%BA%A4%E5%83%B9+%28%E9%AB%98%E2%86%92%E4%BD%8E%29%40%40%E6%88%90%E4%BA%A4%E5%83%B9%40%40%E7%94%B1%E9%AB%98%E2%86%92%E4%BD%8E",
    "成交價601-900名(高→低)": "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%88%90%E4%BA%A4%E5%83%B9+%28%E9%AB%98%E2%86%92%E4%BD%8E%29%40%40%E6%88%90%E4%BA%A4%E5%83%B9%40%40%E7%94%B1%E9%AB%98%E2%86%92%E4%BD%8E",
    "成交價901-1200名(高→低)": "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%88%90%E4%BA%A4%E5%83%B9+%28%E9%AB%98%E2%86%92%E4%BD%8E%29%40%40%E6%88%90%E4%BA%A4%E5%83%B9%40%40%E7%94%B1%E9%AB%98%E2%86%92%E4%BD%8E",
    "成交價1201-1500名(高→低)": "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%88%90%E4%BA%A4%E5%83%B9+%28%E9%AB%98%E2%86%92%E4%BD%8E%29%40%40%E6%88%90%E4%BA%A4%E5%83%B9%40%40%E7%94%B1%E9%AB%98%E2%86%92%E4%BD%8E",
    "成交價1501-1800名(高→低)": "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%88%90%E4%BA%A4%E5%83%B9+%28%E9%AB%98%E2%86%92%E4%BD%8E%29%40%40%E6%88%90%E4%BA%A4%E5%83%B9%40%40%E7%94%B1%E9%AB%98%E2%86%92%E4%BD%8E",
    "成交價1801-2100名(高→低)": "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%88%90%E4%BA%A4%E5%83%B9+%28%E9%AB%98%E2%86%92%E4%BD%8E%29%40%40%E6%88%90%E4%BA%A4%E5%83%B9%40%40%E7%94%B1%E9%AB%98%E2%86%92%E4%BD%8E",
    "成交價2101-2392名(高→低)": "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E6%88%90%E4%BA%A4%E5%83%B9+%28%E9%AB%98%E2%86%92%E4%BD%8E%29%40%40%E6%88%90%E4%BA%A4%E5%83%B9%40%40%E7%94%B1%E9%AB%98%E2%86%92%E4%BD%8E",
    "外資連續買超(週)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E6%99%BA%E6%85%A7%E9%81%B8%E8%82%A1&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E9%80%A3%E8%B2%B7+%E2%80%93+%E9%80%B1%40%40%E5%A4%96%E8%B3%87%E9%80%A3%E7%BA%8C%E8%B2%B7%E8%B6%85%40%40%E5%A4%96%E8%B3%87%E9%80%A3%E7%BA%8C%E8%B2%B7%E8%B6%85+%E2%80%93+%E9%80%B1",
    "外資連續買超(日)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E6%99%BA%E6%85%A7%E9%81%B8%E8%82%A1&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E9%80%A3%E8%B2%B7+%E2%80%93+%E6%97%A5%40%40%E5%A4%96%E8%B3%87%E9%80%A3%E7%BA%8C%E8%B2%B7%E8%B6%85%40%40%E5%A4%96%E8%B3%87%E9%80%A3%E7%BA%8C%E8%B2%B7%E8%B6%85+%E2%80%93+%E6%97%A5",
    "投信連續買超(週)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E6%99%BA%E6%85%A7%E9%81%B8%E8%82%A1&INDUSTRY_CAT=%E6%8A%95%E4%BF%A1%E9%80%A3%E8%B2%B7+%E2%80%93+%E9%80%B1%40%40%E6%8A%95%E4%BF%A1%E9%80%A3%E7%BA%8C%E8%B2%B7%E8%B6%85%40%40%E6%8A%95%E4%BF%A1%E9%80%A3%E7%BA%8C%E8%B2%B7%E8%B6%85+%E2%80%93+%E9%80%B1",
    "投信連續買超(日)": "https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E6%99%BA%E6%85%A7%E9%81%B8%E8%82%A1&INDUSTRY_CAT=%E6%8A%95%E4%BF%A1%E9%80%A3%E8%B2%B7+%E2%80%93+%E6%97%A5%40%40%E6%8A%95%E4%BF%A1%E9%80%A3%E7%BA%8C%E8%B2%B7%E8%B6%85%40%40%E6%8A%95%E4%BF%A1%E9%80%A3%E7%BA%8C%E8%B2%B7%E8%B6%85+%E2%80%93+%E6%97%A5",
    "三大法人賣超佔成交比(5日累計排名)":"https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E4%B8%89%E5%A4%A7%E6%B3%95%E4%BA%BA%E8%B3%A3%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94+%E2%80%93+5%E6%97%A5%40%40%E4%B8%89%E5%A4%A7%E6%B3%95%E4%BA%BA%E8%B3%A3%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94%40%40%E4%B8%89%E5%A4%A7%E6%B3%95%E4%BA%BA+%E2%80%93+5%E6%97%A5",
    "外資賣超佔成交比(3日累計排名)":"https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E8%B3%A3%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94+%E2%80%93+3%E6%97%A5%40%40%E5%A4%96%E8%B3%87%E8%B3%A3%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94%40%40%E5%A4%96%E8%B3%87+%E2%80%93+3%E6%97%A5",
    "外資持股比例1-300名":"https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E6%8C%81%E8%82%A1%E6%AF%94%E4%BE%8B",
    "外資持股比例301-600名":"https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E6%8C%81%E8%82%A1%E6%AF%94%E4%BE%8B",
    "外資持股比例601-900名":"https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E6%8C%81%E8%82%A1%E6%AF%94%E4%BE%8B",
    "外資持股比例901-1200名":"https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E6%8C%81%E8%82%A1%E6%AF%94%E4%BE%8B",
    "外資持股比例1201-1500名":"https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E6%8C%81%E8%82%A1%E6%AF%94%E4%BE%8B",
    "外資持股比例1501-1800名":"https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E6%8C%81%E8%82%A1%E6%AF%94%E4%BE%8B",
    "外資持股比例1801-2100名":"https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E6%8C%81%E8%82%A1%E6%AF%94%E4%BE%8B",
    "外資持股比例2101-2315名":"https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E5%A4%96%E8%B3%87%E6%8C%81%E8%82%A1%E6%AF%94%E4%BE%8B",
    "三大法人買超佔成交比(5日累計排名)":"https://goodinfo.tw/tw/StockList.asp?RPT_TIME=&MARKET_CAT=%E7%86%B1%E9%96%80%E6%8E%92%E8%A1%8C&INDUSTRY_CAT=%E4%B8%89%E5%A4%A7%E6%B3%95%E4%BA%BA%E8%B2%B7%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94+%E2%80%93+5%E6%97%A5%40%40%E4%B8%89%E5%A4%A7%E6%B3%95%E4%BA%BA%E8%B2%B7%E8%B6%85%E4%BD%94%E6%88%90%E4%BA%A4%E6%AF%94%40%40%E4%B8%89%E5%A4%A7%E6%B3%95%E4%BA%BA+%E2%80%93+5%E6%97%A5",
}

print("\n>> [階段三] 啟動 SeleniumBase (UC 模式) 瀏覽器...")
profile_path = os.path.join(BASE_DIR, "chrome_profile")
if not os.path.exists(profile_path):
    os.makedirs(profile_path)

try:
    driver = Driver(
        uc=True,               
        headless=False,        
        user_data_dir=profile_path,
        no_sandbox=True,
        disable_gpu=True,
        window_size="1920,1080"
    )
    driver.maximize_window()
    driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'Asia/Taipei'})
    driver.execute_cdp_cmd('Emulation.setGeolocationOverride', {'latitude': 25.0330, 'longitude': 121.5654, 'accuracy': 100})
    print(" └─ 🎭 真人環境部署完成：已啟用 Cookie 記憶體與原生 UA！")
except Exception as e:
    print(f"啟動 Chrome 失敗！錯誤細節: {e}")
    exit()

def download_goodinfo(name_suffix, url, index, total_count):
    file_name = f"{today}{name_suffix}.csv"
    file_path = os.path.join(SAVE_DIR, file_name)
    print(f"[{index}/{total_count}] 正在擷取: {file_name}")
    
    if os.path.exists(file_path) and os.path.getsize(file_path) > 100:
        print(f" └─ ⏩ 檔案已存在且完整，自動跳過！")
        return "exist"
        
    try:
        driver.uc_open_with_reconnect(url, reconnect_time=4)
        time.sleep(3) 
        
        is_cf_blocked = False
        CF_KEYWORDS = ["Just a moment", "Cloudflare", "請稍候", "Attention", "驗證"]
        if any(kw in driver.title for kw in CF_KEYWORDS) or "cf-turnstile" in driver.page_source:
            is_cf_blocked = True

        if is_cf_blocked:
            print(f" └─ 🛡️ 遇到 Cloudflare 驗證畫面，啟動自動破盾機制...")
            try:
                driver.uc_gui_click_captcha()
                time.sleep(5)
            except Exception as e:
                print(f" └─ ⚠️ 自動點擊遇障礙: {e}")
            if not any(kw in driver.title for kw in CF_KEYWORDS):
                print(" └─ 🔓 Cloudflare 盾牌已成功擊破！")
        
        from selenium.webdriver.support.ui import Select 
        target_start = None
        match = re.search(r'(\d+)-\d+名', name_suffix)
        if match and match.group(1) != "1": 
            target_start = match.group(1)
            
        expected_rank = target_start if target_start else "1"
            
        if target_start:
            print(f" └─ 🔍 偵測到需要切換名次，自動點擊下拉選單 ({target_start} 名起)...")
            time.sleep(5) 
            target_rank_text = f"{target_start}~"
            try:
                changed = False
                selects = driver.find_elements(By.TAG_NAME, "select")
                for sel in selects:
                    if "~300" in sel.text and "~600" in sel.text:
                        s = Select(sel)
                        if target_rank_text not in s.first_selected_option.text:
                            for opt in s.options:
                                if target_rank_text in opt.text:
                                    s.select_by_visible_text(opt.text)
                                    changed = True
                                    break
                        break
                if changed:
                    print(f" └─ 🖱️ 成功點擊切換名次！等待網頁重新載入...")
                    time.sleep(8) 
            except Exception as e:
                print(f" └─ ⚠️ 無法自動切換選單: {e}")
        
        print(" └─ 等待網頁驗證、略過廣告與表格載入...")
        target_df = None
        
        for attempt in range(3):
            is_verified = False
            for i in range(20): 
                try:
                    html = driver.page_source
                    if i == 15:
                        print(" └─ 🔄 網頁似乎載入卡住，嘗試強制重新整理...")
                        driver.refresh()
                        time.sleep(3)
                        continue
                        
                    tables = pd.read_html(StringIO(html))
                    for df in tables:
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(-1)
                        df.columns = [str(col).strip() for col in df.columns]
                        
                        if '代號' in df.columns or '名稱' in df.columns:
                            if len(df) >= 2: 
                                rank_match = True
                                rank_col = next((c for c in df.columns if '排名' in c), None)
                                if rank_col:
                                    first_rank_val = str(df[rank_col].dropna().iloc[0]).replace(".0", "")
                                    if first_rank_val != expected_rank:
                                        rank_match = False
                                
                                if rank_match:
                                    target_df = df
                                    is_verified = True
                                    break 
                    if is_verified: break 
                except Exception: pass
                time.sleep(1) 
                
            if is_verified:
                print(f" └─ ⚡ 名次驗證通過！成功解析正確的區間表格。")
                break
            else:
                print(f" └─ ⚠️ 資料尚未更新 (或名次不符)，強制重整頁面重試...")
                driver.refresh()
                time.sleep(6)
            
        if target_df is not None:
            if '代號' in target_df.columns:
                target_df = target_df[target_df['代號'] != '代號'] 
            target_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            print(f" └─ ✅ 成功存檔！")
            return "success"
        else:
            print(f" └─ ❌ 失敗！抓不到正確名次的表格")
            return "fail"
            
    except Exception as e:
        print(f" └─ ⚠️ 發生未知的錯誤: {e}")
        return "fail"

print(f"開始執行 Goodinfo 下載任務，共計 {len(GOODINFO_TARGETS)} 個檔案。\n" + "-"*40)

failed_tasks = {} 
success_count = 0

for index, (name_suffix, url) in enumerate(GOODINFO_TARGETS.items()):
    result = download_goodinfo(name_suffix, url, index + 1, len(GOODINFO_TARGETS))
    if result in ["success", "exist"]:
        success_count += 1
    else:
        failed_tasks[name_suffix] = url 
        
    if index < len(GOODINFO_TARGETS) - 1:
        sleep_time = random.uniform(20, 40)
        print(f" └─ [防封鎖] 隨機休息 {sleep_time:.2f} 秒...\n")
        time.sleep(sleep_time)

# 🌟 新增：針對失敗的任務啟動第二次重試機制
if failed_tasks:
    print(f"\n>> 🔄 啟動失敗重試機制！共有 {len(failed_tasks)} 個任務需要重試...")
    for index, (name_suffix, url) in enumerate(failed_tasks.items()):
        download_goodinfo(name_suffix, url, f"Retry-{index+1}", len(failed_tasks))
        time.sleep(random.uniform(15, 30))

driver.quit()

# ==========================================
# 🌟 階段三點五：資料自動整併與 B0 運算引擎
# ==========================================
print("\n>> [階段 3.5] 啟動資料自動整併引擎 (轉換 Parquet 並執行 B0 預先運算)...")

def merge_to_parquet_keep_csv(save_dir, date_str):
    price_files = glob.glob(os.path.join(save_dir, f"{date_str}*成交價*.csv"))
    foreign_files = glob.glob(os.path.join(save_dir, f"{date_str}*外資持股*.csv"))
    
    if not price_files or not foreign_files:
        print(" └─ ⚠️ 找不到足夠的 CSV 檔案可供合併。請確認爬蟲是否有抓到資料。")
        return

    try:
        df_price = pd.concat([pd.read_csv(f) for f in price_files], ignore_index=True)
        df_foreign = pd.concat([pd.read_csv(f) for f in foreign_files], ignore_index=True)

        df_price['代號'] = df_price['代號'].astype(str)
        df_foreign['代號'] = df_foreign['代號'].astype(str)

        # === 修改點：分別輸出兩個各自合併後的總 CSV 檔案 ===
        price_csv_filename = f"{date_str}_全部成交價_合併.csv"
        price_csv_path = os.path.join(save_dir, price_csv_filename)
        df_price.to_csv(price_csv_path, index=False, encoding='utf-8-sig')
        print(f" └─ ✅ CSV 獨立合併成功！已生成: {price_csv_filename}")
        
        foreign_csv_filename = f"{date_str}_全部外資持股比例_合併.csv"
        foreign_csv_path = os.path.join(save_dir, foreign_csv_filename)
        df_foreign.to_csv(foreign_csv_path, index=False, encoding='utf-8-sig')
        print(f" └─ ✅ CSV 獨立合併成功！已生成: {foreign_csv_filename}")
        # ===============================================

        foreign_parquet_filename = f"{date_str}_外資持股比例.parquet"
        foreign_parquet_path = os.path.join(save_dir, foreign_parquet_filename)
        df_foreign.to_parquet(foreign_parquet_path, engine='pyarrow', index=False)
        print(f" └─ ✅ Parquet 獨立合併成功！已生成: {foreign_parquet_filename}")

        cols_to_use = df_foreign.columns.difference(df_price.columns).tolist() + ['代號']
        df_merged = pd.merge(df_price, df_foreign[cols_to_use], on='代號', how='left')

        parquet_filename = f"{date_str}_Merged_成交價.parquet"
        parquet_path = os.path.join(save_dir, parquet_filename)
        df_merged.to_parquet(parquet_path, engine='pyarrow', index=False)
        print(f" └─ ✅ 原始合併成功！已生成: {parquet_filename}")
        
        # 🚀 執行 B0 專屬預算處理 (解放前端記憶體) 🚀
        print(" └─ ⚙️ 正在預先計算 B0 盤面結構與多週期均量...")
        all_files = glob.glob(os.path.join(save_dir, "*_Merged_成交價.parquet"))
        if not all_files: return
        
        all_dfs = []
        for f in all_files:
            df = pd.read_parquet(f)
            df.columns = [re.sub(r'[\s\n\r\t\u3000\ufeff]+', '', str(c)) for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            
            c_code = next((c for c in df.columns if '代號' in c), None)
            date_col = next((c for c in df.columns if '日期' in c), None)
            name_col = next((c for c in df.columns if c in ['名稱', '股票名稱', '證券名稱']), None)
            
            if c_code and date_col:
                df['統一代號'] = df[c_code].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df['標準日期'] = df[date_col].astype(str).str.strip()
                df['B0_原始名稱'] = df[name_col].astype(str).str.strip() if name_col else ""
                
                vol_col = next((c for c in df.columns if c in ['成交張數', '總量', '成交量', '累積成交張數', '張數']), None)
                df['成交張數_num'] = pd.to_numeric(df[vol_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0) if vol_col else 0
                df['成交張數'] = df['成交張數_num'] 

                amt_col = next((c for c in df.columns if c in ['成交額(百萬)', '成交金額', '成交額', '總金額']), None)
                df['成交額_num'] = pd.to_numeric(df[amt_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0) if amt_col else 0
                df['成交額(百萬)'] = df['成交額_num']
                
                if 'PER' in df.columns: df['PER'] = pd.to_numeric(df['PER'].astype(str).str.replace(',', ''), errors='coerce')
                if '成交' in df.columns: df['成交'] = pd.to_numeric(df['成交'].astype(str).str.replace(',', ''), errors='coerce')
                if '漲跌幅' in df.columns: df['漲跌幅'] = pd.to_numeric(df['漲跌幅'].astype(str).str.replace(',', '').str.replace('%', ''), errors='coerce')
                all_dfs.append(df)

        combined_df = pd.concat(all_dfs, ignore_index=True)
        if '統一代號' in combined_df.columns: combined_df['統一代號'] = combined_df['統一代號'].fillna("").astype(str)
        combined_df['標準日期'] = combined_df['標準日期'].fillna("").astype(str)
        
        invalid_dates = ['nan', 'nat', 'none', '', '']
        combined_df = combined_df[~combined_df['標準日期'].str.lower().str.strip().isin(invalid_dates)]
        combined_df = combined_df.sort_values(by=['統一代號', '標準日期', '成交張數_num'], ascending=[True, True, False])
        combined_df = combined_df.drop_duplicates(subset=['統一代號', '標準日期'], keep='first')
        
        valid_dates = sorted([str(d) for d in combined_df['標準日期'].unique()], reverse=True)
        if not valid_dates: return
        latest_date = valid_dates[0]
        
        df_today = combined_df[combined_df['標準日期'] == latest_date].copy()
        sorted_df = combined_df.sort_values(by=['統一代號', '標準日期'], ascending=[True, False])
        
        periods = [5, 10, 20, 30, 45]
        for p in periods:
            top_p_df = sorted_df.groupby('統一代號').head(p)
            p_avg = top_p_df.groupby('統一代號').agg(
                **{f'{p}日均量': ('成交張數_num', 'mean'), f'{p}日均額': ('成交額_num', 'mean')}
            ).reset_index()
            df_today = pd.merge(df_today, p_avg, on='統一代號', how='left')
            df_today[f'{p}日均量'] = df_today[f'{p}日均量'].round(0)
            df_today[f'{p}日均額'] = df_today[f'{p}日均額'].round(2)

        df_today['股價日期'] = latest_date
        
        prev_day_df = sorted_df.groupby('統一代號').nth(1).reset_index()
        prev_day_df = prev_day_df[['統一代號', '成交額_num', '成交張數_num', '漲跌幅']].rename(columns={
            '成交額_num': '昨日成交額', '成交張數_num': '昨日成交量', '漲跌幅': '昨日漲跌幅'
        })
        
        df_today = pd.merge(df_today, prev_day_df, on='統一代號', how='left')
        safe_prev_amt = df_today['昨日成交額'].replace(0, 0.01).fillna(0.01)
        df_today['成交金額日變化率'] = ((df_today['成交額_num'] / safe_prev_amt) - 1) * 100  

        def get_special_pattern(row):
            today_pct = row.get('漲跌幅', 0)
            today_vol = row.get('成交張數_num', 0)
            yesterday_pct = row.get('昨日漲跌幅', 0)
            yesterday_vol = row.get('昨日成交量', 0)
            avg_v = row.get('5日均量', 0)
            if pd.isna(today_pct): today_pct = 0
            if pd.isna(yesterday_pct): yesterday_pct = 0
            if yesterday_pct >= 4.0 and yesterday_vol >= 1000:
                if today_vol <= (yesterday_vol * 0.5) and today_pct >= -2.0:
                    return "🕵️ 昨強今急縮 (洗盤防守)"
            if avg_v >= 500 and today_vol > 0:
                if today_vol <= (avg_v * 0.3) and abs(today_pct) <= 1.5:
                    return "💤 極致窒息量 (醞釀表態)"
            return "-"

        df_today['B0_特殊型態'] = df_today.apply(get_special_pattern, axis=1)

        def get_vp_status(row):
            pct = row.get('漲跌幅', 0)
            if pd.isna(pct): pct = 0
            vol = row.get('成交張數_num', 0)
            avg_v = row.get('5日均量', 0)
            if avg_v == 0 or vol == 0: return "⚪ 無明顯動能"
            ratio = vol / avg_v
            if ratio >= 1.5: v_stat = "放量"
            elif ratio <= 0.7: v_stat = "縮量"
            else: v_stat = "平量"
            if pct >= 4.0: p_stat = "大漲"
            elif pct > 1.5: p_stat = "價升"
            elif pct >= -1.5: p_stat = "滯漲"
            elif pct > -4.0: p_stat = "小跌"
            else: p_stat = "大跌"
            comb = f"{v_stat}{p_stat}"
            mapping = {
                "放量大漲": "🚀 放量大漲 (量價齊升，持續看漲)", "縮量大漲": "🔒 縮量大漲 (鎖倉高控盤，延續上漲)", "平量大漲": "✈️ 平量大漲 (一致看漲無拋壓，加速上漲)",
                "縮量價升": "📈 價升量縮 (量價背離，下方承接看拉高)", "放量滯漲": "⚠️ 放量滯漲 (拋壓增大，即將見頂反轉)", "平量滯漲": "⏸️ 平量滯漲 (拋壓增大，高位見頂)",
                "縮量小跌": "📉 縮量小跌 (主力洗盤止跌，擇機進場)", "放量小跌": "🛡️ 放量小跌 (見底信號，越跌越買反轉)", "平量小跌": "🥀 平量價縮 (下跌中繼，弱反彈信號)",
                "縮量大跌": "☠️ 縮量大跌 (一致看空無承接，加速下跌)", "放量大跌": "🩸 放量大跌 (跟風砸盤，高位出貨持續跌)", "平量大跌": "🕳️ 平量大跌 (一致看空無承接，加速下跌)"
            }
            return mapping.get(comb, "⚖️ 溫和震盪整理")

        df_today['B0_量價狀態'] = df_today.apply(get_vp_status, axis=1)

        # 👉 產出極致輕量化的結果檔
        df_today.to_parquet(os.path.join(save_dir, "B0_latest_calculated.parquet"), index=False)
        lite_history = combined_df[['統一代號', '標準日期', '漲跌幅']].copy()
        lite_history.to_parquet(os.path.join(save_dir, "B0_lite_history.parquet"), index=False)
        print(" └─ 🏆 B0 預算完成！產出 B0_latest_calculated.parquet 與 B0_lite_history.parquet")
        
    except Exception as e:
        print(f" └─ ❌ 合併過程發生錯誤: {e}")
merge_to_parquet_keep_csv(SAVE_DIR, today)=
