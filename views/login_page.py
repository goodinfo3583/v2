# views/login_page.py
import streamlit as st
import time
import os
import pandas as pd
import datetime
import base64

# ==========================================
# 💡 效能救星 1：快取 NPC 圖片轉碼，避免每次重繪讀取硬碟
# ==========================================
@st.cache_data(show_spinner=False)
def get_image_base64(image_path):
    """專屬於此頁面的圖片轉碼微型工具"""
    if os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            mime_type = "image/jpeg" if image_path.lower().endswith('.jpg') else "image/png"
            return f"data:{mime_type};base64,{encoded_string}"
    return ""

# ==========================================
# 💡 效能救星 2：把整個登入/註冊表單包裝成 Fragment
# ==========================================
@st.fragment
def render_login_box(conn, SHEET_URL):
    col1, col2 = st.columns([1, 2])
    
    with col1:
        npc_path = "./static/npc_guard1.png"
        img_base64 = get_image_base64(npc_path)
        if img_base64:
            st.markdown(
                f"""
                <div style="display: flex; justify-content: center; align-items: center; padding: 10px;">
                    <img src="{img_base64}" style="width: 100%; max-width: 250px; border-radius: 10px; box-shadow: 0 0 15px rgba(0, 210, 255, 0.3);">
                </div>
                """, 
                unsafe_allow_html=True
            )
        else:
            st.warning(f"找不到圖片: {npc_path}")
            
    with col2:
        st.markdown("""
        <div style='background-color: rgba(17, 22, 34, 0.8); padding: 20px; border-radius: 10px; border: 1px solid #38BDF8; box-shadow: 2px 2px 10px rgba(0,0,0,0.5); margin-bottom: 20px;'>
            <h3 style='color: #FFD700; margin-top: 0;'>親愛的冒險者：</h3>
            <p style='color: #E2E8F0; font-size: 18px; line-height: 1.6;'>
                「請出示你的 <b>邀請函序號</b> ！」<br>
                <span style='font-size: 14px; color: #A0AEC0;'>如果是新來的，在名字後面加上 <b>/M (男)</b> 或 <b>/F (女)</b> 並輸入密碼，我就會幫你自動造冊...</span><br>
                <span style='font-size: 12px; color: #A0AEC0;'>帳號不分大小寫，密碼有分大小寫</span>
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            raw_username = st.text_input("帳號 (Username)")
            raw_password = st.text_input("密碼 (Password)", type="password")
            submit = st.form_submit_button("遞交邀請函", use_container_width=True)

            if submit:
                # 去除首尾空白
                clean_user = raw_username.strip()
                clean_pass = raw_password.strip()
                
                if not clean_user or not clean_pass:
                    st.error("守衛：「名字跟密碼都要寫啊，不然我怎麼認人！」")
                else:
                    # 統一將輸入轉小寫，用來判斷後綴和作為最終登入/註冊帳號
                    lower_user = clean_user.lower()
                    
                    # ==========================================
                    # 🌟 邏輯分流 A：RO 私服式註冊模式 (/m 或 /f)
                    # ==========================================
                    if lower_user.endswith("/m") or lower_user.endswith("/f"):
                        
                        # 擷取最後一個字母轉大寫，當作性別 (M 或 F)
                        gender_code = lower_user[-1].upper() 
                        # 擷取真正的帳號名稱 (已經是小寫了)
                        real_user_lower = lower_user[:-2].strip()
                        
                        if not real_user_lower:
                            st.error(f"守衛：「別鬧了，/{gender_code} 前面要寫上你的名字啊！」")
                        elif not conn or not SHEET_URL:
                            st.error("⚠️ 系統尚未連線至資料庫，無法造冊。")
                        else:
                            with st.spinner("守衛正在翻閱會員名冊..."):
                                try:
                                    # 1. 檢查是否冒充站長 (站長密碼表也統一轉小寫比對)
                                    valid_passwords = st.secrets.get("passwords", {})
                                    valid_users_lower = [str(k).lower() for k in valid_passwords.keys()]
                                    if real_user_lower in valid_users_lower:
                                        st.error("守衛：「大膽！這可是站長的名號，不准冒用！」")
                                        st.stop()
                                        
                                    # 2. 讀取 Google Sheets 檢查是否重複註冊 (保持 ttl=0 以防覆蓋)
                                    try:
                                        current_users = conn.read(spreadsheet=SHEET_URL, worksheet="會員名冊", ttl=0)
                                        is_exist = False
                                        if not current_users.empty and '帳號' in current_users.columns:
                                            # 將資料庫中的帳號也轉小寫，確保比對精準
                                            db_users_lower = current_users['帳號'].astype(str).str.strip().str.lower().values
                                            if real_user_lower in db_users_lower:
                                                is_exist = True
                                    except:
                                        current_users = pd.DataFrame()
                                        is_exist = False
                                    
                                    if is_exist:
                                        st.error(f"守衛：「『{real_user_lower}』這個名字已經有人用了，換一個吧！」")
                                    else:
                                        # 3. 寫入新帳號 (統一存入小寫帳號)
                                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        new_data = pd.DataFrame([{
                                            "帳號": real_user_lower,
                                            "密碼": clean_pass,
                                            "性別": gender_code,
                                            "註冊時間": now_str
                                        }])
                                        
                                        if current_users.empty:
                                            final_users = new_data
                                        else:
                                            final_users = pd.concat([current_users, new_data], ignore_index=True)
                                            
                                        conn.update(spreadsheet=SHEET_URL, worksheet="會員名冊", data=final_users)
                                        st.cache_data.clear() # 💡 註冊成功後清空快取，讓下次登入能抓到新名冊
                                        
                                        gender_title = "男冒險者" if gender_code == "M" else "女冒險者"
                                        st.success(f"🎉 註冊成功！守衛已經將 {gender_title}『{real_user_lower}』記錄下來。請刪除帳號後面的 /{gender_code} 重新登入！")
                                except Exception as e:
                                    st.error(f"❌ 造冊失敗，發生了未知的魔法干擾：{e}")

                    # ==========================================
                    # 🌟 邏輯分流 B：正常登入模式
                    # ==========================================
                    else:
                        login_success = False
                        login_user_target = lower_user
                        
                        # 1. 先查 Secrets 保險箱 (不分大小寫比對)
                        try:
                            valid_passwords = st.secrets.get("passwords", {})
                            for secret_user, secret_pass in valid_passwords.items():
                                if str(secret_user).lower() == login_user_target and str(secret_pass) == clean_pass:
                                    login_success = True
                                    break 
                        except:
                            pass
                            
                        # 2. 去 Google Sheets 查「會員名冊」
                        if not login_success and conn and SHEET_URL:
                            try:
                                # 💡 效能救星 3：登入驗證加上 ttl=60，短時間內重複輸入錯誤密碼不會再卡死等 Google 回應！
                                user_df = conn.read(spreadsheet=SHEET_URL, worksheet="會員名冊", ttl=60)
                                if not user_df.empty and '帳號' in user_df.columns and '密碼' in user_df.columns:
                                    
                                    # 🛑 強制轉字串，剃除莫名其妙產生的小數點(.0)，清除首尾空白，再將帳號轉小寫
                                    user_df['帳號'] = user_df['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower()
                                    user_df['密碼'] = user_df['密碼'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                                    
                                    match = user_df[(user_df['帳號'] == login_user_target) & 
                                                    (user_df['密碼'] == clean_pass)]
                                    
                                    if not match.empty:
                                        login_success = True
                            except Exception as e:
                                st.warning(f"⚠️ 無法連線至會員資料庫：{e}")

                        # 處理登入結果
                        if login_success:
                            st.session_state["logged_in"] = True
                            st.session_state["username"] = login_user_target # 顯示統一小寫的帳號
                            st.success("「驗證成功！大門已開啟，請進...」")
                            time.sleep(1.0)
                            st.rerun() # 💡 只有登入成功時，才會重新整理全網頁來解鎖側邊欄
                        else:
                            st.error("守衛：「這張邀請函是假的，或者密碼錯誤！請重新確認！」")

# ==========================================
# 🖼️ 主渲染入口
# ==========================================
def show_login_page(conn=None, SHEET_URL=None):
    # 狀態 1：已經登入 -> 顯示解鎖畫面與登出按鈕
    if st.session_state.get("logged_in", False):
        st.success(f"歡迎回來，{st.session_state['username']}！您已解鎖最高權限。")
        st.markdown("如果您想結束這次的探索，請點擊下方按鈕登出：")
        
        if st.button("登出系統", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["username"] = None
            st.query_params["page"] = "b1"
            st.rerun()
        return

    # 狀態 2：尚未登入 -> NPC 守衛登場！
    st.markdown("<br>", unsafe_allow_html=True) 
    
    # 💡 呼叫被 Fragment 結界保護的登入框
    render_login_box(conn, SHEET_URL)
