import streamlit as st
import google.generativeai as genai
from PIL import Image
import json

# --- PAGE CONFIG ---
st.set_page_config(page_title="Aegis - Logistics Core", page_icon="🛡️", layout="wide")

# --- CSS FOR MILITARY/TACTICAL LOOK ---
st.markdown("""
<style>
    .big-font {
        font-size:20px !important;
        color: #00FF00; /* Terminal Green */
    }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURATION ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ SYSTEM ERROR: API Key not found.")
    st.stop()

# --- SESSION STATE ---
if 'total_credits' not in st.session_state:
    st.session_state.total_credits = 0 # Changed from XP to Credits
if 'level' not in st.session_state:
    st.session_state.level = 1
if 'streak' not in st.session_state:
    st.session_state.streak = 0
if 'scan_count' not in st.session_state:
    st.session_state.scan_count = 0

# --- SIDEBAR: SYSTEM STATUS ---
st.sidebar.title("🛡️ Operator Status")
st.sidebar.metric("Clearance Level", st.session_state.level)
st.sidebar.metric("System Credits", st.session_state.total_credits)

if st.session_state.streak > 0:
    st.sidebar.markdown(f"### 🔥 {st.session_state.streak} Day Uptime")
else:
    st.sidebar.markdown("### ⚠️ Uptime Critical")

st.sidebar.progress(st.session_state.total_credits % 100) 

# --- MAIN APP ---
st.title("📡 Acquisition Scanner")
st.write("Upload purchase data to catalog assets and consumables.")

if st.session_state.scan_count == 0:
    st.info("📅 **Daily Protocol:** Catalog 1 purchase to maintain system uptime. (+50 Credits)")

uploaded_file = st.file_uploader("Select Image File...", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.info("📷 Visual Input")
        st.image(uploaded_file, use_column_width=True)
    
    with col2:
        st.info("🔍 Processing...")
        
        bytes_data = uploaded_file.getvalue()
        image_parts = [{"mime_type": uploaded_file.type, "data": bytes_data}]

        # MATURE PROMPT
        prompt = """
        You are Aegis, a logistics AI analyzing purchase records.
        
        1. Identify ALL items (Assets and Consumables).
        2. **QUANTITY PROTOCOL:**
           - If value > $50, list each unit separately for tracking.
           - If value < $50, group by item type.
        3. **EXPIRATION PROTOCOL:**
           - Assets (Electronics/Furniture): Calculate "warranty_days".
           - Consumables (Food): Calculate "days_until_spoil" based on average shelf life.
           - General Goods: Set all expiry to 0.
        
        Return ONLY valid JSON:
        [
          {
            "item_name": "string",
            "merchant": "string",
            "price": "float",
            "purchase_date": "YYYY-MM-DD",
            "category": "Electronics|Apparel|Home|Groceries|Furniture",
            "warranty_days": "integer",
            "days_until_spoil": "integer"
          }
        ]
        """

        if st.button("Process Assets"):
            with st.spinner("Analyzing data..."):
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    response = model.generate_content([prompt, image_parts[0]])
                    raw_text = response.text.replace("```json", "").replace("```", "").strip()
                    
                    data = json.loads(raw_text)
                    if not isinstance(data, list):
                        data = [data]
                    
                    # --- TACTICAL GAMIFICATION ---
                    base_credits = 10 
                    
                    if st.session_state.scan_count == 0:
                        st.session_state.streak += 1
                        st.session_state.total_credits += 50 
                        st.toast("🔥 Uptime Extended. +50 Credits.", icon="✅")

                    st.session_state.scan_count += 1
                    
                    st.success(f"✅ CATALOGING COMPLETE. {len(data)} items identified.")
                    st.subheader("📦 Inventory Manifest")
                    
                    cols = st.columns(3)
                    
                    for i, item in enumerate(data):
                        price = item['price']
                        
                        # TACTICAL CLASSIFICATION
                        if price > 1000: 
                            classification = "🟡 CLASS: EXOTIC"
                            credits = 100
                        elif price > 200: 
                            classification = "🟣 CLASS: LEGENDARY"
                            credits = 50
                        elif price > 50: 
                            classification = "🔵 CLASS: RARE"
                            credits = 20
                        else: 
                            classification = "⚪ CLASS: COMMON"
                            credits = 5
                        
                        st.session_state.total_credits += credits
                        
                        # STATUS LOGIC
                        if item.get('days_until_spoil', 0) > 0:
                            status = f"🍎 Spoilage Risk: {item['days_until_spoil']} days"
                        elif item.get('warranty_days', 0) > 0:
                            status = f"🛡️ Warranty Active: {item['warranty_days']} days"
                        else:
                            status = "♻️ General Stock"

                        col_idx = i % 3
                        with cols[col_idx]:
                            st.markdown(f"### {classification}")
                            st.markdown(f"**{item['item_name']}**")
                            st.caption(f"Vendor: {item['merchant']}")
                            st.write(f"Cost: ${item['price']}")
                            st.write(f"Status: {status}")
                            st.write(f"⚡ +{credits} Credits")
                            st.markdown("---")

                    # LEVEL UP
                    new_level = (st.session_state.total_credits // 100) + 1
                    if new_level > st.session_state.level:
                        st.session_state.level = new_level
                        st.balloons()
                        st.toast(f"🎖️ CLEARANCE UPGRADE: Level {new_level}", icon="🎖️")

                except Exception as e:
                    st.error(f"❌ SYSTEM ERROR: {e}")
