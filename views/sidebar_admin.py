# views/sidebar_admin.py
import io
import os
import pandas as pd
import streamlit as st
from views.b1_page import fetch_github_json_down

def render_global_admin_sidebar(DATA_DIR):
    with st.sidebar.expander("🛠️ 站長快照總管 (全站儲存)", expanded=False):
        admin_pw = st.text_input("解鎖全站快照功能", type="password", key="global_admin_pw_input")
        expected_pw = st.secrets["passwords"]["b1_admin"]
        
        if admin_pw == expected_pw:
            st.success("🔓 驗證成功！")
            snap_date = st.date_input("選擇資料基準日(通常為今日)", key="admin_snap_date")
            date_str = snap_date.strftime("%Y%m%d")
            
            st.markdown("---")
            
            # ==========================================
            # 👁️ 記憶體監視器 (全市場大表)
            # ==========================================
            master_df = st.session_state.get('b8_master_dataframe')
            if master_df is None or master_df.empty:
                master_df = st.session_state.get('debug_df')
                
            if master_df is not None and not master_df.empty:
                st.info(f"📊 記憶體狀態：已捕捉大表 **{len(master_df)}** 檔")
            else:
                st.warning("⚠️ 記憶體尚未捕捉大表 (請先至回測頁面產生數據)")

            # ==========================================
            # 📥 1. B1 法人動向歷史快照下載區
            # ==========================================
            st.markdown("<div style='font-size:14px; font-weight:bold; color:#38BDF8; margin-top:10px;'>📈 B1 法人動向快照下載</div>", unsafe_allow_html=True)
            
            # --- 正向籌碼數據彙總 ---
            json_dfs = st.session_state.get('b1_json_dfs', {})
            all_snap_up = []
            for d in [5, 20, 60, 120]:
                if d in json_dfs and isinstance(json_dfs[d], pd.DataFrame) and not json_dfs[d].empty:
                    temp = json_dfs[d][['股票代號', '股票名稱', '法人持股']].copy()
                    temp['上榜區塊'] = f"{d}日"
                    all_snap_up.append(temp)
            
            snap_grouped_up = pd.DataFrame()
            if all_snap_up:
                snap_df_up = pd.concat(all_snap_up, ignore_index=True)
                snap_grouped_up = snap_df_up.groupby(['股票代號', '股票名稱']).agg({
                    '法人持股': 'max', '上榜區塊': lambda x: ",".join(set(x))
                }).reset_index()

            # --- 負向衰退數據彙總 ---
            current_down_dfs = fetch_github_json_down()
            all_snap_down = []
            for d in [5, 10, 20, 30]:
                if d in current_down_dfs and isinstance(current_down_dfs[d], pd.DataFrame) and not current_down_dfs[d].empty:
                    temp = current_down_dfs[d].copy()
                    temp['上榜區塊'] = f"{d}日衰退"
                    all_snap_down.append(temp)

            snap_grouped_down = pd.DataFrame()
            if all_snap_down:
                snap_df_down = pd.concat(all_snap_down, ignore_index=True)
                snap_grouped_down = snap_df_down.groupby(['股票代號', '股票名稱']).agg({
                    '法人持股': 'max', '上榜區塊': lambda x: ",".join(set(x)), '累積衰退': 'first'
                }).reset_index()

            col_b1_up, col_b1_down = st.columns(2)
            with col_b1_up:
                if not snap_grouped_up.empty:
                    csv_b1_up = snap_grouped_up.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        label=f"🟢 B1 正向 ({len(snap_grouped_up)}檔)",
                        data=csv_b1_up,
                        file_name=f"{date_str}_JSON_History.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.caption("⚪ 無 B1 正向資料")

            with col_b1_down:
                if not snap_grouped_down.empty:
                    csv_b1_down = snap_grouped_down.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        label=f"🔴 B1 負向 ({len(snap_grouped_down)}檔)",
                        data=csv_b1_down,
                        file_name=f"{date_str}_Down_History.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.caption("⚪ 無 B1 負向資料")

            # ==========================================
            # 📥 2. 全市場特徵大表下載區 (CSV / Parquet)
            # ==========================================
            st.markdown("---")
            st.markdown("<div style='font-size:14px; font-weight:bold; color:#00E272;'>📥 全市場特徵大表下載</div>", unsafe_allow_html=True)
            
            if master_df is not None and not master_df.empty:
                col_down1, col_down2 = st.columns(2)
                
                with col_down1:
                    csv_buffer = master_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        label=f"💾 下載 CSV ({len(master_df)}檔)",
                        data=csv_buffer,
                        file_name=f"Master_Snapshot_{date_str}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                with col_down2:
                    clean_master_df = master_df.copy()
                    for col in clean_master_df.columns:
                        if clean_master_df[col].dtype == object:
                            clean_master_df[col] = clean_master_df[col].astype(str)
                            
                    parquet_buffer = io.BytesIO()
                    clean_master_df.to_parquet(parquet_buffer, index=False)
                    st.download_button(
                        label=f"📦 下載 Parquet ({len(master_df)}檔)",
                        data=parquet_buffer.getvalue(),
                        file_name=f"Master_Snapshot_{date_str}.parquet",
                        mime="application/octet-stream",
                        use_container_width=True
                    )
            else:
                st.caption("*(尚未產生全市場大表，請先至回測頁面篩選或產生數據)*")

        elif admin_pw != "":
            st.error("❌ 密碼錯誤")
