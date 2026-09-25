# views/contact_page.py
import streamlit as st
import pandas as pd
import datetime
import os
import base64

# 引入剛剛擴充好的隱形按鈕引擎
from components.nav_manager import render_proxy_buttons

# 💡 效能救星 1：將圖片讀取與轉碼加上快取，避免切換頁面時重複讀取硬碟
@st.cache_data(show_spinner=False)
def get_image_base64(image_path):
    """專屬於此頁面的圖片轉碼微型工具"""
    if os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            mime_type = "image/jpeg" if image_path.lower().endswith('.jpg') else "image/png"
            return f"data:{mime_type};base64,{encoded_string}"
    return ""

# 💡 效能救星 2：把表單與送出動作包進 Fragment。
# 這樣使用者在按下「傳送」的等待期間，側邊欄與導覽列完全不會閃爍或被鎖死！
@st.fragment
def render_contact_form(conn, SHEET_URL):
    with st.form("contact_us_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1: sender_name = st.text_input("您的稱呼 (選填)", placeholder="例如：股市冒險家")
        with c2: sender_email = st.text_input("電子信箱 (選填)", placeholder="若需回覆請務必留下 Email")
            
        message_body = st.text_area("回報內容 / 建議事項*", placeholder="請描述您遇到的問題或建議...", height=120)
        submit_btn = st.form_submit_button("傳送紙條 ✉️", use_container_width=True)
        
        if submit_btn:
            if not message_body.strip():
                st.error("⚠️ 傳送失敗：紙條上似乎空無一字喔！")
            else:
                try:
                    try:
                        # 送出時才去讀取資料庫，並使用 ttl=0 確保拿到最新資料避免覆蓋
                        old_contact_df = conn.read(spreadsheet=SHEET_URL, worksheet="聯絡我們", ttl=0)
                        old_contact_df = old_contact_df.dropna(how="all")
                    except:
                        old_contact_df = pd.DataFrame(columns=["時間", "稱呼", "信箱", "內容"])
                    
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_data = pd.DataFrame([{"時間": now_str, "稱呼": sender_name.strip() if sender_name else "匿名使用者", "信箱": sender_email.strip() if sender_email else "-", "內容": message_body.strip()}])
                    
                    final_contact_df = pd.concat([old_contact_df, new_data], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, worksheet="聯絡我們", data=final_contact_df)
                    
                    st.toast("您的訊息已悄悄送達派對後台...", icon="🦇")
                    st.success("✨ 感謝回報！您的建議是盛宴最棒的點綴。")
                except Exception as e:
                    st.error(f"❌ 傳送失敗，後台連線異常：{str(e)}")


def show_contact_page(conn, SHEET_URL):
    """
    聯絡管家頁面 UI 與資料庫寫入邏輯
    注意：我們把 conn 和 SHEET_URL 當作參數傳遞進來，這樣就不會報錯了！
    """
    st.markdown("<h2 style='color: #00D2FF; text-align: center; margin-top: 30px; text-shadow: 0 0 10px rgba(0,210,255,0.5);'>✉️ 聯絡管家</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        col_img, col_text = st.columns([1.5, 3.5])
        
        with col_img:
            # 📍 終極防呆路徑定位：精準找到 static 資料夾下的 75743.jpg
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            npc_image_path = os.path.join(project_root, "static", "75743.jpg")
            
            img_base64 = get_image_base64(npc_image_path)
            if img_base64:
                st.markdown(
                    f"""
                    <div style="display: flex; justify-content: center; align-items: center; height: 100%; padding: 10px;">
                        <img src="{img_base64}" style="width: 100%; max-width: 220px; border-radius: 50%; border: 1px solid rgba(0, 210, 255, 0.7); box-shadow: 0 0 20px rgba(0, 210, 255, 0.4);">
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            else:
                # 找不到圖片時的備用顯示
                st.markdown("<div style='font-size: 80px; text-align: center; color: #00D2FF;'>🦇</div>", unsafe_allow_html=True)

        with col_text:
            st.markdown(
                """
                <div style="background: linear-gradient(135deg, rgba(0, 210, 255, 0.05) 0%, rgba(0, 210, 255, 0.12) 100%); 
                            padding: 20px 25px; border-radius: 12px; border-left: 2px solid #00D2FF; 
                            border-top: 1px solid rgba(0, 210, 255, 0.2); border-right: 1px solid rgba(0, 210, 255, 0.2); 
                            border-bottom: 1px solid rgba(0, 210, 255, 0.2); box-shadow: 0 8px 25px rgba(0, 210, 255, 0.1); 
                            backdrop-filter: blur(4px); height: 100%; display: flex; align-items: center;">
                    <p style="margin: 0; font-size: 17px; color: #E2E8F0; line-height: 1.8; letter-spacing: 0.5px;">
                        「夜安，股市冒險家。<br>
                        如果您在平台中發現任何系統異常，或是對本平台有任何建議，<br>
                        歡迎將寫好的紙條傳遞到後台交給我處理。😱」
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        st.write("") 
        
        # 💡 呼叫被 Fragment 隔離的表單區塊
        render_contact_form(conn, SHEET_URL)
        
    # 🛑 補上隱藏的傀儡按鈕，避免在聯絡我們頁面時頂部導覽列失效網頁卡死！
    # render_proxy_buttons()
