# views/sidebar_admin.py
import io
import pandas as pd
import streamlit as st
from views.b1_page import fetch_github_json_down

# 💡 效能救星：Fragment 化！輸入密碼與選擇日期時，全網頁不會再閃爍或重整
@st.fragment
def render_global_admin_sidebar(DATA_DIR):
    with st.sidebar.expander("🛠️ 站長快照總管 (全站儲存)", expanded=False):
        admin_pw = st.text_input("解鎖全站快照功能", type="password", key="global_admin_pw_input")
        if not admin_pw: return
        
        if admin_pw != st.secrets["passwords"]["b1_admin"]:
            return st.error("❌ 密碼錯誤")
            
        st.success("🔓 驗證成功！")
        date_str = st.date_input("選擇資料基準日", key="admin_snap_date").strftime("%Y%m%d")
        st.markdown("---")
        
        # ==========================================
        # 👁️ 記憶體監視器 (全市場大表)
        # ==========================================
        m_df = st.session_state.get('b8_master_dataframe')
        if m_df is None or m_df.empty: m_df = st.session_state.get('debug_df')
        
        if m_df is not None and not m_df.empty: st.info(f"📊 記憶體狀態：已捕捉大表 **{len(m_df)}** 檔")
        else: st.warning("⚠️ 記憶體尚未捕捉大表 (請先至回測頁面產生數據)")

        # ==========================================
        # 📥 1. B1 法人動向歷史快照下載區
        # ==========================================
        st.markdown("<div style='font-size:14px; font-weight:bold; color:#38BDF8; margin-top:10px;'>📈 B1 法人動向快照下載</div>", unsafe_allow_html=True)
        
        # 🚀 Pandas 向量化瘦身：將數十行的 for 迴圈與 append 濃縮為兩行 List Comprehension
        j_dfs, d_dfs = st.session_state.get('b1_json_dfs', {}), fetch_github_json_down()
        
        up_list = [j_dfs[d][['股票代號', '股票名稱', '法人持股']].assign(上榜區塊=f"{d}日") for d in [5, 20, 60, 120] if isinstance(j_dfs.get(d), pd.DataFrame) and not j_dfs[d].empty]
        dn_list = [d_dfs[d].assign(上榜區塊=f"{d}日衰退") for d in [5, 10, 20, 30] if isinstance(d_dfs.get(d), pd.DataFrame) and not d_dfs[d].empty]

        df_up = pd.concat(up_list, ignore_index=True).groupby(['股票代號', '股票名稱']).agg({'法人持股': 'max', '上榜區塊': lambda x: ",".join(set(x))}).reset_index() if up_list else pd.DataFrame()
        df_dn = pd.concat(dn_list, ignore_index=True).groupby(['股票代號', '股票名稱']).agg({'法人持股': 'max', '上榜區塊': lambda x: ",".join(set(x)), '累積衰退': 'first'}).reset_index() if dn_list else pd.DataFrame()

        c1, c2 = st.columns(2)
        with c1:
            if not df_up.empty: st.download_button(f"🟢 正向 ({len(df_up)})", df_up.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), f"{date_str}_JSON_History.csv", "text/csv", use_container_width=True)
            else: st.caption("⚪ 無正向資料")
        with c2:
            if not df_dn.empty: st.download_button(f"🔴 負向 ({len(df_dn)})", df_dn.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), f"{date_str}_Down_History.csv", "text/csv", use_container_width=True)
            else: st.caption("⚪ 無負向資料")

        # ==========================================
        # 📥 2. 全市場特徵大表下載區 (CSV / Parquet)
        # ==========================================
        st.markdown("<hr style='margin:10px 0;'><div style='font-size:14px; font-weight:bold; color:#00E272;'>📥 全市場特徵大表下載</div>", unsafe_allow_html=True)
        
        if m_df is not None and not m_df.empty:
            c3, c4 = st.columns(2)
            c3.download_button(f"💾 CSV ({len(m_df)})", m_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), f"Master_{date_str}.csv", "text/csv", use_container_width=True)
            
            # 🚀 記憶體轉型最佳化：使用 select_dtypes 取代對所有 columns 進行迴圈判斷
            p_df = m_df.copy()
            obj_cols = p_df.select_dtypes(include=['object']).columns
            p_df[obj_cols] = p_df[obj_cols].astype(str)
            
            buf = io.BytesIO()
            p_df.to_parquet(buf, index=False)
            c4.download_button(f"📦 Parquet ({len(m_df)})", buf.getvalue(), f"Master_{date_str}.parquet", "application/octet-stream", use_container_width=True)
        else:
            st.caption("*(尚未產生全市場大表，請先至回測頁面篩選)*")
