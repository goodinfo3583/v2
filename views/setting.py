# views/setting.py
import streamlit as st
import streamlit.components.v1 as components

@st.fragment
def render():
    st.markdown("""
        <h2 style='color:#00D2FF; margin-top:10px;'>設置中心</h2>
        <p style='color:#94A3B8; font-size:14px;'>調整將會自動套用至系統頁面，完成後請點擊下方確認。</p>
        <hr style='margin: 15px 0;'><h4 style='color:#E2E8F0; font-size: 16px;'>外觀與濾鏡</h4>
    """, unsafe_allow_html=True)

    theme_map = {'dark': "暗黑(預設)", 'pink': "鋼鐵褐", 'green': "翡翠綠", 'purple': "月影紫", 'brown': "沙漠棕", 'blue': "天空藍"}
    curr_theme = st.session_state.get('theme', 'dark')
    theme_choice = st.radio("選擇背景主題：", list(theme_map.keys()), format_func=theme_map.get, index=list(theme_map.keys()).index(curr_theme) if curr_theme in theme_map else 0, horizontal=True)
    
    opacity_val = st.slider("背景濾鏡遮罩 (%)", 0, 100, int(st.session_state.get('bg_opacity', 88)))
    perf_mode_val = st.checkbox("開啟極簡效能模式 (關閉動畫、跑馬燈與基礎動畫提升流暢度)", value=st.session_state.get('performance_mode', False))
    
    st.markdown("<hr style='margin: 15px 0;'><h4 style='color:#E2E8F0; font-size: 16px;'>快捷鍵配置</h4>", unsafe_allow_html=True)
    
    # 💡 效能與版面優化：用 List 定義動作、顯示名稱與預設快捷鍵，取代原本手動排版 14 次的臃腫程式碼
    hk_layout = [
        ("NavToB1", "法人動向", "F1"), ("NavToB2", "法人掃貨", "F2"), ("NavToB3", "法人連買", "F3"),
        ("NavToB4", "資券動向", "F4"), ("NavToB5", "大腿動向", "F6"), ("NavToB6", "鉅額交易", "F7"),
        ("NavToB7", "董監動向", "F8"), ("NavToWatchlist", "自選名單", "Alt+L"), ("NavToWeightBacktest", "籌碼過濾", "Alt+Q"),
        ("NavToB0", "量價掃描", "Alt+S"), ("NavToBroker", "券商主力", "Alt+B"), ("NavToNews", "市場消息", "Alt+N"),
        ("登入", "登入", "Escape"), ("NavToSettings", "設置", "Alt+P")
    ]
    
    # 動態反查映射表：從 {key: action} 轉為 {action: key}
    default_hotkeys = {hk[2].lower(): hk[0] for hk in hk_layout}
    rev_map = {v: k for k, v in st.session_state.get('custom_hotkeys', default_hotkeys).items()}
    
    new_hk, cols = {}, st.columns(2)
    for i, (action, label, default) in enumerate(hk_layout):
        # 依序分配左右欄位 (前 7 個左欄，後 7 個右欄)
        with cols[0 if i < 7 else 1]:
            new_hk[action] = st.text_input(label, value=rev_map.get(action, default), key=f"kb_{action}")

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    
    if c1.button("確認", use_container_width=True, type="primary"):
        # 💡 使用 update 一口氣寫入 session_state
        st.session_state.update({
            'theme': theme_choice, 'bg_opacity': opacity_val, 'performance_mode': perf_mode_val,
            'custom_hotkeys': {k.strip().lower(): v for v, k in new_hk.items() if k.strip()}
        })
        st.toast('✅ 設定已成功儲存！')
        st.rerun()
        
    if c2.button("取消", use_container_width=True):
        st.toast('🔄 已恢復為原本設定。')
        st.rerun()
        
    # 💡 JS 程式碼極限壓縮，並維持原本的按鍵擷取、樣式切換功能 (注意保留 window.parent 穿透 iframe)
    components.html("""
    <script>
    setTimeout(() => { window.parent.document.querySelectorAll('input[type="text"]').forEach(i => {
        if(i.dataset.kb) return; i.dataset.kb = "1";
        i.addEventListener('keydown', function(e) {
            e.preventDefault(); e.stopPropagation(); let keys = [];
            if(e.ctrlKey) keys.push('ctrl'); if(e.altKey) keys.push('alt'); if(e.shiftKey) keys.push('shift');
            let k = e.key.toLowerCase(); if(['control','alt','shift','meta','process'].includes(k)) return;
            keys.push(k === ' ' ? 'space' : k);
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(this, keys.join('+'));
            this.dispatchEvent(new Event('input', { bubbles: true }));
        });
        i.addEventListener('focus', () => i.style.boxShadow = '0 0 10px #00D2FF');
        i.addEventListener('blur', () => i.style.boxShadow = 'none');
    })}, 500);
    </script>""", height=0, width=0)
