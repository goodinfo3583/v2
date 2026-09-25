# views/setting.py
import streamlit as st
import streamlit.components.v1 as components

# 💡 效能救星：使用 Fragment 將整個設定面板包裹起來！
# 使用者在調整滑桿、切換 Radio 按鈕或輸入快捷鍵時，都不會再觸發全網頁重整，徹底解決閃爍與卡頓。
@st.fragment
def render():
    # 💡 移除原本的懸浮 CSS (position: fixed, drag-handle)，改為乾淨的全螢幕排版
    st.markdown("<h2 style='color:#00D2FF; margin-top:10px;'>設置中心</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94A3B8; font-size:14px;'>調整將會自動套用至系統頁面，完成後請點擊下方確認。</p>", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("<h4 style='color:#E2E8F0; font-size: 16px;'>外觀與濾鏡</h4>", unsafe_allow_html=True)
    current_theme = st.session_state.get('theme', 'dark')
    current_opacity = int(st.session_state.get('bg_opacity', 88))

    # 🔥 讀取效能模式
    current_perf_mode = st.session_state.get('performance_mode', False)
    
    theme_options = ['dark', 'pink', 'green', 'purple','brown','blue']
    theme_choice = st.radio(
        "選擇背景主題 (將同步切換圖片)：", 
        options=theme_options, 
        format_func=lambda x: {'dark': "暗黑(預設)", 'pink': "鋼鐵褐", 'green': "翡翠綠", 'purple': "月影紫", 'brown':"沙漠棕",'blue': "天空藍"}[x], 
        index=theme_options.index(current_theme) if current_theme in theme_options else 0, 
        horizontal=True
    )
    
    opacity_val = st.slider("背景濾鏡遮罩 (%)", min_value=0, max_value=100, value=current_opacity)

    # 🔥 效能模式勾選框
    perf_mode_val = st.checkbox("開啟極簡效能模式 (關閉動畫、跑馬燈與基礎動畫提升流暢度)", value=current_perf_mode)
    
    st.markdown("---")
    st.markdown("<h4 style='color:#E2E8F0; font-size: 16px;'>快捷鍵配置</h4>", unsafe_allow_html=True)
    
    reverse_map = {v: k for k, v in st.session_state.get('custom_hotkeys', {"F1": "NavToB1", "F2": "NavToB2", "F3": "NavToB3", "F4": "NavToB4", "F5": "NavToB5", "F6": "NavToB6", "F7": "NavToB7", "Alt+L": "NavToWatchlist", "Escape": "登入", "Alt+P":"設置"}).items()}
    
    col1, col2 = st.columns(2)
    new_hotkeys = {}
    with col1:
        new_hotkeys["NavToB1"] = st.text_input("法人動向", value=reverse_map.get("NavToB1", "F1"), key="kb1")
        new_hotkeys["NavToB2"] = st.text_input("法人掃貨", value=reverse_map.get("NavToB2", "F2"), key="kb2")
        new_hotkeys["NavToB3"] = st.text_input("法人連買", value=reverse_map.get("NavToB3", "F3"), key="kb3")
        new_hotkeys["NavToB4"] = st.text_input("資券動向", value=reverse_map.get("NavToB4", "F4"), key="kb4")
        new_hotkeys["NavToB5"] = st.text_input("大腿動向", value=reverse_map.get("NavToB5", "F6"), key="kb5")
        new_hotkeys["NavToB6"] = st.text_input("鉅額交易", value=reverse_map.get("NavToB6", "F7"), key="kb6")
        new_hotkeys["NavToB7"] = st.text_input("董監動向", value=reverse_map.get("NavToB7", "F8"), key="kb7")
    with col2:   
        new_hotkeys["NavToWatchlist"] = st.text_input("自選名單", value=reverse_map.get("NavToWatchlist", "Alt+L"), key="kb_wl")
        new_hotkeys["NavToWeightBacktest"] = st.text_input("籌碼過濾", value=reverse_map.get("NavToWeightBacktest", "Alt+Q"), key="kb_WeightBacktest")
        new_hotkeys["NavToB0"] = st.text_input("量價掃描", value=reverse_map.get("NavToB0", "Alt+S"), key="kb_kb0")
        new_hotkeys["NavToBroker"] = st.text_input("券商主力", value=reverse_map.get("NavToBroker", "Alt+B"), key="kb_kbroker")
        new_hotkeys["NavToNews"] = st.text_input("市場消息", value=reverse_map.get("NavToNews", "Alt+N"), key="kb_kbews")
        new_hotkeys["登入"] = st.text_input("登入", value=reverse_map.get("登入", "escape"), key="kb_login")
        new_hotkeys["NavToSettings"] = st.text_input("設置", value=reverse_map.get("NavToSettings", "Alt+P"), key="kb_set")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # -----------------------------
    # 底部：儲存與取消按鈕 (保留在當前頁面)
    # -----------------------------
    col_ok, col_cancel = st.columns([1, 1])
    with col_ok:
        if st.button("確認", use_container_width=True, type="primary"):
            # 寫入 session_state
            st.session_state['theme'] = theme_choice
            st.session_state['bg_opacity'] = opacity_val
            st.session_state['custom_hotkeys'] = {k.strip().lower(): v for v, k in new_hotkeys.items() if k.strip().lower()}
        
            st.session_state['performance_mode'] = perf_mode_val # 新增：將效能模式的設定存入 session_state
                    
            st.toast('設定已成功儲存！') # 使用 toast 顯示右下角輕量提示，不干擾畫面                  
            st.rerun() # 🚀 只有點擊確認時，才會跳出 Fragment 進行全域重整，立即套用新主題與濾鏡
            
    with col_cancel:
        if st.button("取消", use_container_width=True):
            st.toast('已恢復為原本的設定。')
            st.rerun() # 🚀 放棄修改，強制重刷讀取原本的 Session
            
    # 💡 乾淨的 JS：不再需要尋找 modal 容器，直接綁定頁面上所有的 text input
    keybind_js = """
    <script>
    setTimeout(() => {
        const inputs = window.parent.document.querySelectorAll('input[type="text"]');
        inputs.forEach(input => {
            if(input.dataset.keybound) return;
            input.dataset.keybound = "true";
            input.addEventListener('keydown', function(e) {
                e.preventDefault(); e.stopPropagation();
                let combo = [];
                if (e.ctrlKey) combo.push('ctrl'); if (e.altKey) combo.push('alt'); if (e.shiftKey) combo.push('shift');
                let keyName = e.key.toLowerCase();
                if (['control', 'alt', 'shift', 'meta', 'process'].includes(keyName)) return; 
                if (keyName === ' ') keyName = 'space';
                combo.push(keyName);
                let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                nativeInputValueSetter.call(this, combo.join('+'));
                this.dispatchEvent(new Event('input', { bubbles: true}));
            });
            input.addEventListener('focus', function() { this.style.boxShadow = '0 0 10px #00D2FF'; });
            input.addEventListener('blur', function() { this.style.boxShadow = 'none'; });
        });
    }, 500);
    </script>
    """
    components.html(keybind_js, height=0, width=0)
