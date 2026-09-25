# views/watchlist_page.py
import streamlit as st
import json
import re
import time
import pandas as pd
import numpy as np

# ==========================================
# 💾 資料庫存取 (Google Sheets 正式連線版)
# ==========================================
def get_user_watchlist(username, conn, SHEET_URL):
    if not conn or not SHEET_URL: return {}
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="會員名冊", ttl=60)
        if df.empty or '帳號' not in df.columns or 'Watchlist' not in df.columns: return {}
        match = df[df['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower() == str(username).strip().lower()]
        if not match.empty and pd.notna(gs_w := match.iloc[0]['Watchlist']) and str(gs_w).strip() != "":
            data = json.loads(str(gs_w))
            return {s: "" for s in data} if isinstance(data, list) else data
    except Exception: pass
    return {}

def save_user_watchlist(username, watchlist, conn, SHEET_URL):
    if not conn or not SHEET_URL: return st.error("無法連線至資料庫，無法存檔。")
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="會員名冊", ttl=0)
        if df.empty or '帳號' not in df.columns: return
        if 'Watchlist' not in df.columns: df['Watchlist'] = ""
        df['Watchlist'] = df['Watchlist'].astype(object)
        
        idx = df[df['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower() == str(username).strip().lower()].index
        if len(idx) > 0:
            df.at[idx[0], 'Watchlist'] = json.dumps(watchlist, ensure_ascii=False)
            conn.update(spreadsheet=SHEET_URL, worksheet="會員名冊", data=df)
            st.cache_data.clear() 
    except Exception as e: st.error(f"存檔失敗: {e}")

# ==========================================
# 🚀 高效能批次報價引擎
# ==========================================
@st.cache_data(show_spinner=False, ttl=300)
def get_watchlist_quotes(stock_codes):
    import yfinance as yf
    if not stock_codes: return {}
    tickers = [f"{c}.TW" for c in stock_codes] + [f"{c}.TWO" for c in stock_codes]
    try: df = yf.download(tickers, period="5d", progress=False)
    except: return {}
    
    quotes = {}
    if df.empty or 'Close' not in df.columns or 'Volume' not in df.columns: return quotes
    c_df, v_df = df['Close'], df['Volume']
    
    for c in stock_codes:
        tw, two = f"{c}.TW", f"{c}.TWO"
        t_col = tw if tw in c_df.columns else (two if two in c_df.columns else None)
        if not t_col: continue
        
        c_s, v_s = c_df[t_col].dropna(), v_df[t_col].dropna()
        if len(c_s) >= 2 and len(v_s) >= 2:
            c_tdy, c_yst, v_tdy, v_yst = float(c_s.iloc[-1]), float(c_s.iloc[-2]), float(v_s.iloc[-1]), float(v_s.iloc[-2])
            quotes[c] = {"price": c_tdy, "price_pct": (c_tdy - c_yst) / c_yst * 100 if c_yst > 0 else 0, "vol": int(v_tdy / 1000), "vol_pct": (v_tdy - v_yst) / v_yst * 100 if v_yst > 0 else 0, "date": c_s.index[-1].strftime("%Y/%m/%d")}
    return quotes

# ==========================================
# 🚀 獨立渲染魔法區塊一：實驗室模型追蹤 (向量化 + Pure HTML)
# ==========================================
@st.fragment
def render_tab_track(username, conn):
    st.subheader("模型鎖定清單與績效追蹤")
    st.markdown("這裡顯示您從「權重與回測」寫入的標的，方便您每日檢視策略績效。")
    st.markdown("""<style>.track-card{background:rgba(30,41,59,0.4);backdrop-filter:blur(12px);border-radius:12px;border:1px solid rgba(255,255,255,0.1);box-shadow:0 4px 15px rgba(0,0,0,0.3);padding:15px;transition:all 0.3s cubic-bezier(0.25,0.8,0.25,1);}.track-card:hover{background:rgba(30,41,59,0.7);border:1px solid rgba(56,189,248,0.5);transform:translateY(-2px);}.stat-box{background:rgba(15,23,42,0.6);border-radius:8px;padding:8px;text-align:center;border:1px solid rgba(255,255,255,0.05);}.stat-title{font-size:11px;color:#94a3b8;margin-bottom:4px;}.stat-value{font-size:15px;font-weight:bold;}.pos-return{color:#FF4B4B;}.neg-return{color:#00E272;}.neu-return{color:#94A3B8;}</style>""", unsafe_allow_html=True)

    if not conn: return
    try:
        df_track = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1TxHDahg8ul6lmUtDN-7X75cBXbkU0jaZ3M9zg6exBgU/edit?gid=687268023#gid=687268023", worksheet="實驗室模型追蹤", ttl=60)
        if df_track.empty or '帳號' not in df_track.columns: return st.info("尚無追蹤紀錄。請至「權重與回測」過濾標的並點擊寫入。")
        
        user_track = df_track[df_track['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower() == username.strip().lower()].copy()
        if user_track.empty: return st.info("您目前沒有將任何模型標的寫入追蹤喔！")

        # 🚀 極速 Pandas 向量化資料清洗與配對 (修正 Series 防呆機制)
        empty_str_s = pd.Series('', index=user_track.index)
        empty_zero_s = pd.Series(0, index=user_track.index)

        c_code = user_track.get('代號', empty_str_s).astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        u_code = user_track.get('統一代號', empty_str_s).astype(str).str.extract(r'(\d+)')[0].fillna('')
        user_track['純代號'] = np.where(c_code == '', u_code, c_code)
        
        track_quotes = get_watchlist_quotes(user_track['純代號'].replace('', np.nan).dropna().unique().tolist())
        
        p_raw = user_track.get('鎖定收盤價', user_track.get('B0_成交', empty_zero_s))
        user_track['鎖定價'] = pd.to_numeric(p_raw.astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        user_track['最新價'] = user_track['純代號'].map(lambda x: track_quotes.get(x, {}).get('price', None)).fillna(user_track['鎖定價'])
        user_track['報酬'] = np.where(user_track['鎖定價'] > 0, ((user_track['最新價'] - user_track['鎖定價']) / user_track['鎖定價'] * 100), 0.0).round(2)
        
        st.markdown("### 鎖定標的戰情面板")
        # 🚀 用純 HTML Grid 取代 st.columns 迴圈，渲染速度提昇百倍
        cards_html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 15px;">'
        for _, r in user_track.iterrows():
            roi, p_color = r['報酬'], ("255,75,75" if r['報酬'] > 0 else ("0,226,114" if r['報酬'] < 0 else "148,163,184"))
            r_class, sign = ("pos-return", "+") if roi > 0 else (("neg-return", "") if roi < 0 else ("neu-return", ""))
            name = r.get('名稱', r.get('股票名稱', '未知'))
            cards_html += f"""
            <div class="track-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="font-size: 16px; font-weight: bold; color: #fff;"><span style="color: #38BDF8; margin-right: 6px;">{r['純代號']}</span>{name}</div>
                    <div style="font-size: 11px; color: #94a3b8; background: rgba(0,0,0,0.3); padding: 4px 6px; border-radius: 4px;">鎖定: {r.get('鎖定日期', '未知')}</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;">
                    <div class="stat-box"><div class="stat-title">鎖定價</div><div class="stat-value" style="color:#e2e8f0;">{r['鎖定價']:.2f}</div></div>
                    <div class="stat-box"><div class="stat-title">最新價</div><div class="stat-value" style="color:#e2e8f0;">{r['最新價']:.2f}</div></div>
                    <div class="stat-box" style="background:rgba({p_color},0.1); border-color:rgba({p_color},0.3);">
                        <div class="stat-title">報酬</div><div class="stat-value {r_class}">{sign}{roi:.2f}%</div>
                    </div>
                </div>
            </div>"""
        st.markdown(cards_html + "</div><hr style='border-color: #334155; margin: 10px 0 20px 0;'>", unsafe_allow_html=True)
        
        st.markdown("### 原始數據總表")
        display_df = user_track.drop(columns=['帳號', '純代號', '鎖定價', '最新價', '報酬'], errors='ignore').copy()
        loc = display_df.columns.get_loc('鎖定收盤價') + 1 if '鎖定收盤價' in display_df.columns else len(display_df.columns)
        display_df.insert(loc, '最新價格', user_track['最新價'])
        display_df.insert(loc + 1, '區間報酬', user_track['報酬'].apply(lambda x: f"{x:.2f}%"))
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    except Exception as e: st.error(f"讀取追蹤資料時發生錯誤：{e}")

# ==========================================
# 🚀 獨立渲染魔法區塊二：自訂追蹤名單 (元件瘦身版)
# ==========================================
@st.fragment
def render_tab_custom(username, conn, SHEET_URL, STOCK_DICT):
    wl_cache_key = f"wl_cache_{username}"
    if wl_cache_key not in st.session_state: st.session_state[wl_cache_key] = get_user_watchlist(username, conn, SHEET_URL)
    watchlist = st.session_state[wl_cache_key]
    
    for s in list(watchlist.keys()):
        if f"note_{s}" not in st.session_state: st.session_state[f"note_{s}"] = watchlist[s]

    st.subheader(f"新增自訂標的 (目前 {len(watchlist)}/20 檔)")
    c1, c2 = st.columns([3, 1])
    stock_opts = sorted(list({f"{v['id']} {v['name']}" for v in STOCK_DICT.values() if len(str(v['id'])) <= 4})) if STOCK_DICT else []
    new_stock = c1.selectbox("請選擇股票", [""] + stock_opts, key="new_stock_input", label_visibility="collapsed")
    
    if c2.button("加入追蹤", use_container_width=True) and new_stock:
        if len(watchlist) >= 20: st.error("追蹤名單已達 20 檔上限！")
        elif new_stock not in watchlist:
            watchlist[new_stock] = ""; st.session_state[f"note_{new_stock}"] = ""
            st.success(f"已暫存「{new_stock}」，請記得點擊下方「存檔」！"); time.sleep(1); st.rerun()
        else: st.info(f"「{new_stock}」已在名單中囉！")

    st.markdown("<hr style='border-color: #334155; margin: 10px 0;'>", unsafe_allow_html=True)
    stock_codes = [m.group() for s in watchlist.keys() if (m := re.search(r'\d+', s))]
    market_data = get_watchlist_quotes(stock_codes) if stock_codes else {}
    market_date = list(market_data.values())[0]["date"] if market_data else "今日"

    # ==========================
    # 內聯回呼函式優化區
    # ==========================
    def append_quote_to_note(sn, p_code):
        if p_code and p_code in market_data:
            d = market_data[p_code]; nk = f"note_{sn}"
            append_str = f"[{d['date'][5:]}] 收:{d['price']:.2f} 量:{d['vol']:,}張"
            st.session_state[nk] = f"{st.session_state.get(nk, '').strip()}\n{append_str}".strip()
            watchlist[sn] = st.session_state[nk]

    def append_dynamic_to_note(sn, p_code):
        dyn_msg = "⚪ B1未進榜"; disp_dt = market_date[5:] if '/' in market_date else "今日"
        try:
            df_b1 = st.session_state.get('b1_final_df') if st.session_state.get('b1_final_df') is not None else st.session_state.get('my_final_df')
            if df_b1 is not None and not df_b1.empty:
                col_id = next((c for c in ['股票代號', '代號'] if c in df_b1.columns), None)
                if col_id:
                    # 🚀 $O(1)$ 字典查表取代 DataFrame 搜尋
                    b1_dict = df_b1.set_index(col_id).to_dict('index')
                    if str(p_code) in b1_dict:
                        row = b1_dict[str(p_code)]
                        def get_v(keys, excl=[]): return next((str(row[k]) for k in row.keys() if any(x in k for x in keys) and not any(e in k for e in excl) and str(row[k]).lower() not in ['nan','none','']), "-")
                        dyn_msg = f"📌動態:{get_v(['最新動態','狀態動態','動態'],['衰退'])} | 🏷️上榜:{get_v(['今日上榜','原始上榜','上榜'],['衰退'])} | 📊單日△:{get_v(['單日△','精準單日','單日','△'],['衰退'])}"
                        
                        df_down = st.session_state.get('b1_down_final_df')
                        if df_down is not None and not df_down.empty and col_id in df_down.columns:
                            dw_dict = df_down.set_index(col_id).to_dict('index')
                            if str(p_code) in dw_dict:
                                r_dw = dw_dict[str(p_code)]
                                def get_d(keys): return next((str(r_dw[k]) for k in r_dw.keys() if any(x in k for x in keys) and str(r_dw[k]).lower() not in ['nan','none','']), "無")
                                dyn_msg += f"\n  📉提款 🏷️衰退:{get_d(['衰退上榜','提款機','衰退追蹤','衰退'])} | 📊單日△:{get_d(['衰退單日','提款單日','衰退△','單日△','精準單日','△'])}"
        except Exception as e: dyn_msg = f"異常: {e}"
        nk = f"note_{sn}"
        st.session_state[nk] = f"{st.session_state.get(nk, '').strip()}\n[{disp_dt}]\n  {dyn_msg}".strip()
        watchlist[sn] = st.session_state[nk]

    def action_batch(action_type):
        for sn in list(watchlist.keys()):
            p_code = m.group() if (m := re.search(r'\d+', sn)) else None
            if action_type == 'quote': append_quote_to_note(sn, p_code)
            elif action_type == 'dyn': append_dynamic_to_note(sn, p_code)
            elif action_type == 'clear': st.session_state[f"note_{sn}"] = ""; watchlist[sn] = ""
            elif action_type == 'del': del st.session_state[f"note_{sn}"]
        if action_type == 'del':
            watchlist.clear()
            for k in ["selected_watch_stock", "global_search_final"]: st.session_state.pop(k, None)

    # 頂部控制面板
    co1, co2, co3, _ = st.columns([1.5, 1.5, 3.0, 4.0])
    if co1.button("存檔", icon=":material/save:", use_container_width=True, type="primary"):
        with st.spinner("雲端同步中..."):
            for s in list(watchlist.keys()): watchlist[s] = st.session_state.get(f"note_{s}", watchlist[s])
            save_user_watchlist(username, watchlist, conn, SHEET_URL)
        st.success("存檔成功！"); time.sleep(1); st.rerun()

    if co2.button("匯出", icon=":material/download:", use_container_width=True, disabled=not watchlist):
        exp_data = [{"標的名稱": s, "最新價": market_data.get(re.search(r'\d+', s).group() if re.search(r'\d+', s) else "", {}).get("price", ""), "成交量(張)": market_data.get(re.search(r'\d+', s).group() if re.search(r'\d+', s) else "", {}).get("vol", ""), "專屬筆記": st.session_state.get(f"note_{s}", n)} for s, n in watchlist.items()]
        st.download_button("確認匯出", pd.DataFrame(exp_data).to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), f"watchlist_{username}.csv", "text/csv")
    
    if watchlist and market_data: co3.markdown(f"<div style='padding-top:8px; color:#38BDF8; font-weight:bold;'>日期：{market_date}</div>", unsafe_allow_html=True)

    if not watchlist: return st.info("目前還沒有追蹤任何標的，趕快新增一個吧！")

    # 🚀 CSS 優化與佈局瘦身 (9欄 -> 6欄)
    st.markdown("""<style>div[data-testid="stVerticalBlockBorderWrapper"]:has(.sc-mark){background:rgba(30,41,59,0.3)!important;backdrop-filter:blur(12px)!important;border-radius:12px!important;border:1px solid rgba(255,255,255,0.1)!important;margin-bottom:8px!important;transition:all 0.3s!important;}div[data-testid="stVerticalBlockBorderWrapper"]:has(.sc-mark):hover{background:rgba(30,41,59,0.6)!important;border-color:rgba(56,189,248,0.4)!important;}div[data-testid="stVerticalBlockBorderWrapper"]:has(.hr-mark){border:none!important;background:transparent!important;box-shadow:none!important;margin-bottom:-15px!important;}</style>""", unsafe_allow_html=True)
    
    def fmt_c(val, is_p=False, is_v=False): return f"<span style='color:{'#FF4B4B' if val>0 else ('#00E272' if val<0 else '#94A3B8')}; {'font-size:12px;' if is_v else 'font-weight:bold;'}'>({'+' if val>0 else ''}{val:.1f}%)</span>" if is_v else f"<span style='color:{'#FF4B4B' if val>0 else ('#00E272' if val<0 else '#94A3B8')}; font-weight:bold;'>{'+' if val>0 else ''}{val:.2f}{'%' if is_p else ''}</span>"

    c_ratios = [2.5, 4.0, 0.7, 0.7, 0.7, 0.7] # 🚀 欄位大幅縮減
    with st.container(border=True):
        st.markdown("<span class='hr-mark'></span>", unsafe_allow_html=True)
        h = st.columns(c_ratios)
        h[0].markdown("<div style='padding-top:10px; color:#94a3b8; font-size:14px;'>標的資訊</div>", unsafe_allow_html=True)
        hc1, hc2 = h[1].columns([3.4, 0.5])
        hc1.markdown("<div style='padding-top:10px; color:#94a3b8; font-size:14px;'>專屬筆記</div>", unsafe_allow_html=True)
        hc2.button("", icon=":material/ink_eraser:", key="b_clr", help="清空筆記", use_container_width=True, on_click=action_batch, args=('clear',))
        h[2].button("", icon=":material/input:", key="b_q", help="帶入今日行情", use_container_width=True, on_click=action_batch, args=('quote',))
        h[3].button("", icon=":material/psychology:", key="b_d", help="帶入籌碼動態", use_container_width=True, on_click=action_batch, args=('dyn',))
        h[5].button("", icon=":material/delete:", key="b_del", help="移除所有標的", use_container_width=True, on_click=action_batch, args=('del',))

    for s in list(watchlist.keys()):
        nk, p_code = f"note_{s}", (re.search(r'\d+', s).group() if re.search(r'\d+', s) else None)
        ind_lbl = STOCK_DICT.get(p_code, {}).get("industry", "未知") if p_code and STOCK_DICT else "未知"
        d = market_data.get(p_code, {})
        info_html = f"<div style='font-weight:bold; font-size:15px;'>{s}</div><div style='margin:4px 0;'><span style='font-size:11px; background:#1E293B; padding:2px 5px; border-radius:4px; border:1px solid #0369a1; color:#38BDF8;'>{ind_lbl}</span></div>"
        if d: info_html += f"<div style='font-size:14px; margin-top:6px;'>收: {d['price']:.2f} {fmt_c(d['price_pct'], True)}<br>量: {d['vol']:,} {fmt_c(d['vol_pct'], False, True)}</div>"

        with st.container(border=True):
            st.markdown("<span class='sc-mark'></span>", unsafe_allow_html=True)
            cols = st.columns(c_ratios)
            cols[0].markdown(info_html, unsafe_allow_html=True)
            cols[1].text_area("筆記", key=nk, label_visibility="collapsed", placeholder="點此輸入筆記...", height=95)
            
            # 🚀 按鈕區置中對齊
            cols[2].markdown("<div style='padding-top:25px;'>", unsafe_allow_html=True); cols[2].button("", icon=":material/input:", key=f"i_{s}", use_container_width=True, on_click=append_quote_to_note, args=(s, p_code)); cols[2].markdown("</div>", unsafe_allow_html=True)
            cols[3].markdown("<div style='padding-top:25px;'>", unsafe_allow_html=True); cols[3].button("", icon=":material/psychology:", key=f"d_{s}", use_container_width=True, on_click=append_dynamic_to_note, args=(s, p_code)); cols[3].markdown("</div>", unsafe_allow_html=True)
            cols[4].markdown("<div style='padding-top:25px;'>", unsafe_allow_html=True)
            if cols[4].button("", icon=":material/monitoring:", key=f"v_{s}", use_container_width=True):
                st.session_state["selected_watch_stock"] = st.session_state["global_search_final"] = f"{STOCK_DICT[p_code]['id']} {STOCK_DICT[p_code]['name']}" if p_code and STOCK_DICT and p_code in STOCK_DICT else s
                st.rerun()
            cols[4].markdown("</div>", unsafe_allow_html=True)
            cols[5].markdown("<div style='padding-top:25px;'>", unsafe_allow_html=True)
            if cols[5].button("", icon=":material/delete:", key=f"r_{s}", use_container_width=True):
                del watchlist[s]; st.session_state.pop(nk, None)
                if st.session_state.get("selected_watch_stock") == s: st.session_state["selected_watch_stock"] = st.session_state["global_search_final"] = None
                st.rerun()
            cols[5].markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 🎨 畫面渲染主程式
# ==========================================
def show_watchlist_page(STOCK_DICT=None, conn=None, SHEET_URL=None):
    st.markdown("""<div style="background: linear-gradient(90deg, rgba(15,23,42,1) 0%, rgba(14,165,233,0.3) 50%, rgba(15,23,42,1) 100%); border-top: 1px solid #38bdf8; border-bottom: 1px solid #38bdf8; padding: 15px 20px; border-radius: 10px; text-align: center; box-shadow: 0px 0px 20px rgba(56, 189, 248, 0.2); margin-bottom: 20px;"><h2 style="color: #e0f2fe; margin: 0; letter-spacing: 2px; text-shadow: 0 0 15px rgba(56, 189, 248, 0.8);">自選名單</h2></div>""", unsafe_allow_html=True)

    if not st.session_state.get("logged_in", False):
        st.warning("「這區是 VIP 專屬！請先前往登入頁面註冊或出示邀請函。」")
        if st.button("前往登入", key="go_login_from_watchlist"): st.query_params["page"] = "login"; st.rerun()
        return

    username = st.session_state.get("username", "guest")
    tab_track, tab_custom = st.tabs(["🔹 權重回測寶庫", "🔹 自訂追蹤名單"])
    
    with tab_track: render_tab_track(username, conn)
    with tab_custom: render_tab_custom(username, conn, SHEET_URL, STOCK_DICT)

    st.markdown('<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />', unsafe_allow_html=True)
    st.markdown("""<a href="#" id="custom-b2t-btn" style="display: flex; justify-content: center; align-items: center; background-color: rgba(14, 165, 233, 0.1); color: #38bdf8; font-size: 14px; font-weight: bold; padding: 12px; border-radius: 8px; text-decoration: none; margin-top: 40px; margin-bottom: 20px; border: 1px solid rgba(56, 189, 248, 0.3); box-shadow: 0px 4px 6px rgba(0,0,0,0.3); gap: 6px;"><span class="material-symbols-outlined" style="font-size: 20px;">move_up</span>回到頂部</a>""", unsafe_allow_html=True)
    
    import streamlit.components.v1 as components
    components.html("""<script>const p=window.parent;const b=p.document.getElementById('custom-b2t-btn');if(b)b.onclick=e=>{e.preventDefault();[p.document.querySelector('[data-testid="stAppViewContainer"]'),p.document.querySelector('[data-testid="stMain"]'),p.document.documentElement,p].forEach(c=>{if(c)try{c.scrollTo({top:0,behavior:'smooth'})}catch(err){}})};</script>""", height=0, width=0)
