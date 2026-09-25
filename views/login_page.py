# views/login_page.py
import streamlit as st
import time
import os
import pandas as pd
import datetime
import base64

# ==========================================
# 💡 效能救星 1：快取 NPC 圖片轉碼
# ==========================================
@st.cache_data(show_spinner=False)
def get_image_base64(image_path):
    if not os.path.exists(image_path): return ""
    with open(image_path, "rb") as img:
        return f"data:image/{'jpeg' if image_path.lower().endswith('.jpg') else 'png'};base64,{base64.b64encode(img.read()).decode()}"

# ==========================================
# 💡 效能救星 2：Fragment 化登入與註冊表單
# ==========================================
@st.fragment
def render_login_box(conn, SHEET_URL):
    c1, c2 = st.columns([1, 2])
    
    with c1:
        img_b64 = get_image_base64("./static/npc_guard1.png")
        if img_b64: st.markdown(f'<div style="display:flex;justify-content:center;padding:10px;"><img src="{img_b64}" style="width:100%;max-width:250px;border-radius:10px;box-shadow:0 0 15px rgba(0,210,255,0.3);"></div>', unsafe_allow_html=True)
        else: st.warning("找不到守衛圖片")
            
    with c2:
        st.markdown("""<div style='background:rgba(17,22,34,0.8); padding:20px; border-radius:10px; border:1px solid #38BDF8; box-shadow:2px 2px 10px rgba(0,0,0,0.5); margin-bottom:20px;'><h3 style='color:#FFD700; margin-top:0;'>親愛的冒險者：</h3><p style='color:#E2E8F0; font-size:18px; line-height:1.6;'>「請出示你的 <b>邀請函序號</b> ！」<br><span style='font-size:14px; color:#A0AEC0;'>新來的請在名字後加上 <b>/M(男)</b> 或 <b>/F(女)</b> 加上密碼自動造冊...</span><br><span style='font-size:12px; color:#A0AEC0;'>帳號不分大小寫，密碼區分大小寫</span></p></div>""", unsafe_allow_html=True)

        with st.form("login_form"):
            usr = st.text_input("帳號 (Username)").strip()
            pwd = st.text_input("密碼 (Password)", type="password").strip()
            
            if st.form_submit_button("遞交邀請函", use_container_width=True):
                if not usr or not pwd:
                    return st.error("守衛：「名字跟密碼都要寫啊，不然我怎麼認人！」")
                
                usr_lower = usr.lower()
                
                # ==========================================
                # 🌟 分流 A：私服式註冊模式 (/m 或 /f)
                # ==========================================
                if usr_lower.endswith(("/m", "/f")):
                    gender = usr_lower[-1].upper()
                    real_usr = usr_lower[:-2].strip()
                    
                    if not real_usr: return st.error(f"守衛：「別鬧了，/{gender} 前面要寫上名字啊！」")
                    if not conn or not SHEET_URL: return st.error("⚠️ 系統未連線至資料庫，無法造冊。")
                    
                    with st.spinner("守衛翻閱會員名冊中..."):
                        if real_usr in [str(k).lower() for k in st.secrets.get("passwords", {})]:
                            return st.error("守衛：「大膽！這可是站長的名號，不准冒用！」")
                            
                        try:
                            df = conn.read(spreadsheet=SHEET_URL, worksheet="會員名冊", ttl=0)
                            if not df.empty and '帳號' in df.columns and real_usr in df['帳號'].astype(str).str.strip().str.lower().values:
                                return st.error(f"守衛：「『{real_usr}』已經有人用了，換一個吧！」")
                                
                            new_row = pd.DataFrame([{"帳號": real_usr, "密碼": pwd, "性別": gender, "註冊時間": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                            conn.update(spreadsheet=SHEET_URL, worksheet="會員名冊", data=new_row if df.empty else pd.concat([df, new_row], ignore_index=True))
                            st.cache_data.clear()
                            
                            st.success(f"🎉 註冊成功！守衛已記錄 {'男' if gender=='M' else '女'}冒險者『{real_usr}』。請刪除 /{gender} 重新登入！")
                        except Exception as e: st.error(f"❌ 造冊失敗：{e}")

                # ==========================================
                # 🌟 分流 B：正常登入模式
                # ==========================================
                else:
                    success = False
                    # 1. 檢查 Secrets (站長)
                    for k, v in st.secrets.get("passwords", {}).items():
                        if str(k).lower() == usr_lower and str(v) == pwd:
                            success = True; break
                            
                    # 2. 檢查 Google Sheets
                    if not success and conn and SHEET_URL:
                        try:
                            df = conn.read(spreadsheet=SHEET_URL, worksheet="會員名冊", ttl=60)
                            if not df.empty and '帳號' in df.columns and '密碼' in df.columns:
                                if not df[(df['帳號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lower() == usr_lower) & 
                                          (df['密碼'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip() == pwd)].empty:
                                    success = True
                        except Exception as e: st.warning(f"⚠️ 無法連線至資料庫：{e}")

                    # 3. 處理結果
                    if success:
                        st.session_state.update({"logged_in": True, "username": usr_lower})
                        st.success("「驗證成功！大門已開啟，請進...」"); time.sleep(1); st.rerun()
                    else:
                        st.error("守衛：「這張邀請函是假的，或者密碼錯誤！請重新確認！」")


# ==========================================
# 🖼️ 主渲染入口
# ==========================================
def show_login_page(conn=None, SHEET_URL=None):
    if st.session_state.get("logged_in", False):
        st.success(f"歡迎回來，{st.session_state['username']}！您已解鎖最高權限。")
        if st.button("登出系統", use_container_width=True):
            st.session_state.update({"logged_in": False, "username": None})
            st.query_params["page"] = "b1"; st.rerun()
        return

    st.markdown("<br>", unsafe_allow_html=True) 
    render_login_box(conn, SHEET_URL)
