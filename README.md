最近開發了宅宅『股市派對-韭菜盒子』籌碼分析工具，整合了台灣市場的籌碼變化、籌碼分析、大戶(腿)動向與統計表格，一起成為千張大戶吧。歡迎教學研究參考與交流：https://3dafaram3583.streamlit.app/



專案架構goodinfo3583/trace3dafaram-

📁 專案根目錄/

│

├── 📄test\_web.py                   #  主程式 (main)(Router \& 初始化)

│                                # 負責: 連線資料庫、讀取 Session、根據點擊把冒險者帶到對應的包廂(views)。

├── 📄newdaily1820\_scraper.py #爬蟲每日法人買賣超資料、法人掃貨、法人連買、鉅額交易(證券交易所、櫃買中心、Goodinfo)

│

├── 📄newdaily2200\_scraper.py #爬蟲每日 融資餘額 法人 資券動向(證券交易所、櫃買中心、Goodinfo)

│

├── 📄saturday1230\_scraper.py #爬蟲每周大股東變化 大腿動向(神秘金字塔、Goodinfo)

│

├── 📄company\_month\_scraper.py #爬蟲每月董監變化 (Goodinfo)

│

├── 📄requirements.txt

│

├── 📄README.md

│

├── 📁 components/               # 裝潢與基礎設施 (UI 組件)

│   ├── 📄 nav\_manager.py        # 導航管家 (頂部 JS 導覽列、全站共用隱形按鈕)

│   └── 📄 style\_manager.py      # 視覺設計 (CSS 樣式、跑馬燈特效)

│

├── 📁 utils/                    #  工具箱 (純邏輯與資料處理)

│   └── 📄 data\_utils.py         # 讀取 CSV、清理代號、轉換格式等防呆小幫手\*\*\*

│

├── 📁 views/                    #  獨立頁面 (各個獨立的頁面專屬包廂邏輯)

│   ├── 📄 news\_page.py          # 市場消息

│   ├── 📄 broker\_page.py       # 券商分點

│   ├── 📄 contact\_page.py       # 聯絡我們 (寫入 G-Sheets)

│   ├── 📄 login\_page.py         # 登入頁面

│   ├── 📄 sidebar.py            # 側邊視窗欄位

│   ├── 📄 watchlist\_page.py     # 使用者自訂追蹤清單 (寫入 G-Sheets)

│   ├── 📄 weight\_backtest\_page.py   # 權重自訂篩選 (自訂權重與連結追蹤清單頁面寫入 G-Sheets)

│   ├── 📄 pool\_page.py          # 觀察名單 (大數據計分、樹狀圖、歷史回測、 寫入 G-Sheets)

│   ├── 📄 b1\_page.py            # 區塊 1 法人動向

│   ├── 📄 b2\_page.py            # 區塊 2 法人掃貨

│   ├── 📄 b3\_page.py            # 區塊 3 法人連買

│   ├── 📄 b4\_page.py            # 區塊 4 資券動向

│   ├── 📄 b5\_page.py            # 區塊 5 大腿動向

│   ├── 📄 b6\_page.py            # 區塊 6 鉅額交易

│   ├── 📄 b7\_page.py            # 區塊 7 董監動向

│   └── 📄 setting.py             # 設置中心(瀏覽者自訂網站顏色、CSS及背景圖片)

│

└── 📁 static/                   # 🖼️ 圖片倉庫 (靜態資源、icon、npc圖片、各種圖片倉庫)

│   └── 📄 75743.jpg             # 管家圖片等

└── 📁 image/                   # 🖼️ 圖片 (主視覺背景圖、城市圖)

│   └── 📄 派對盛宴邀請.png

│

│

│

│

└── 📁 data/         #存放所有基礎資料、爬蟲資料

│

│

└── 📁 History\_Archive/         #存放過往基礎資料、爬蟲資料

