import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="Aegis - Logistics Core", page_icon="🛡️", layout="wide")

# --- CONFIGURATION ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ SYSTEM ERROR: API Key not found.")
    st.stop()

# --- SESSION STATE ---
if 'total_credits' not in st.session_state:
    st.session_state.total_credits = 0 
if 'level' not in st.session_state:
    st.session_state.level = 1
if 'streak' not in st.session_state:
    st.session_state.streak = 0
if 'scan_count' not in st.session_state:
    st.session_state.scan_count = 0
if 'total_items_scanned' not in st.session_state:
    st.session_state.total_items_scanned = 0
if 'badges' not in st.session_state:
    st.session_state.badges = {
        "First Acquisition": False, "High Roller": False, 
        "Asset Manager": False, "Operational": False, "Quartermaster": False
    }

# --- HELPER: IMAGE COMPRESSION ---
def compress_image(image):
    max_size = 1024
    if image.width > max_size:
        ratio = max_size / image.width
        new_height = int(image.height * ratio)
        image = image.resize((max_size, new_height), Image.Resampling.LANCZOS)
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=85)
    return img_byte_arr.getvalue()

# --- FUNCTION: CHECK COMMENDATIONS ---
def check_commendations():
    if st.session_state.scan_count >= 1 and not st.session_state.badges["First Acquisition"]:
        st.session_state.badges["First Acquisition"] = True
        st.toast("🎖️ Commendation Unlocked: First Acquisition", icon="🎖️")
    if st.session_state.total_items_scanned >= 10 and not st.session_state.badges["Asset Manager"]:
        st.session_state.badges["Asset Manager"] = True
        st.toast("🎖️ Commendation Unlocked: Asset Manager", icon="🎖️")
    if st.session_state.level >= 5 and not st.session_state.badges["Quartermaster"]:
        st.session_state.badges["Quartermaster"] = True
        st.toast("🎖️ Commendation Unlocked: Quartermaster", icon="🎖️")

# --- SIDEBAR: SYSTEM STATUS ---
st.sidebar.title("🛡️ Operator Status")
st.sidebar.metric("Clearance Level", st.session_state.level)
st.sidebar.metric("System Credits", st.session_state.total_credits)
if st.session_state.streak > 0:
    st.sidebar.markdown(f"### 🔥 {st.session_state.streak} Day Uptime")
else:
    st.sidebar.markdown("### ⚠️ Uptime Critical")
st.sidebar.progress(st.session_state.total_credits % 100) 

# --- SIDEBAR: COMMENDATIONS ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎖️ Commendations")
cols = st.sidebar.columns(3)
badge_icons = {"First Acquisition": "🎯", "High Roller": "💰", "Asset Manager": "📦", "Operational": "📅", "Quartermaster": "🛡️"}
for i, (name, unlocked) in enumerate(st.session_state.badges.items()):
    with cols[i % 3]:
        icon = badge_icons[name] if unlocked else "🔒"
        st.markdown(f"<div style='text-align:center; font-size: 24px; opacity: {1.0 if unlocked else 0.2}'>{icon}</div>", unsafe_allow_html=True)

# --- MAIN APP ---
st.title("📡 Acquisition Scanner")
st.write("Upload purchase data to catalog assets.")

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
        
        try:
            pil_image = Image.open(uploaded_file)
            compressed_bytes = compress_image(pil_image)
            image_parts = [{"mime_type": "image/jpeg", "data": compressed_bytes}]
        except Exception as e:
            st.error(f"Image Error: {e}")
            st.stop()

        prompt = """
        You are Aegis, a logistics AI. 
        Analyze receipt. Return JSON list. 
        Fields: item_name, merchant, price (float), purchase_date (YYYY-MM-DD), category, warranty_days (int), days_until_spoil (int).
        Separate items over $50. Group items under $50.
        """

        if st.button("Process Assets"):
            with st.spinner("Analyzing data..."):
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    response = model.generate_content([prompt, image_parts[0]])
                    raw_text = response.text.replace("```json", "").replace("```", "").strip()
                    
                    data = json.loads(raw_text)
                    if not isinstance(data, list): data = [data]
                    
                    if st.session_state.scan_count == 0:
                        st.session_state.streak += 1
                        st.session_state.total_credits += 50 

                    st.session_state.scan_count += 1
                    st.session_state.total_items_scanned += len(data)
                    
                    st.success(f"✅ CATALOGING COMPLETE. {len(data)} items identified.")
                    st.subheader("📦 Inventory Manifest")
                    
                    cols = st.columns(3)
                    
                    for i, item in enumerate(data):
                        # SAFE PRICE HANDLING
                        try:
                            price = float(item.get('price', 0))
                        except:
                            price = 0.0

                        if price > 1000: 
                            classification = "🟡 EXOTIC"
                            credits = 100
                            if not st.session_state.badges["High Roller"]:
                                st.session_state.badges["High Roller"] = True
                                st.toast("🎖️ Commendation Unlocked: High Roller", icon="🎖️")
                        elif price > 200: 
                            classification, credits = "🟣 LEGENDARY", 50
                        elif price > 50: 
                            classification, credits = "🔵 RARE", 20
                        else: 
                            classification, credits = "⚪ COMMON", 5
                        
                        st.session_state.total_credits += credits
                        
                        # SAFE STATUS HANDLING
                        spoil = item.get('days_until_spoil', 0)
                        warranty = item.get('warranty_days', 0)

                        if spoil > 0:
                            status = f"🍎 Spoilage Risk: {spoil} days"
                        elif warranty > 0:
                            status = f"🛡️ Warranty Active: {warranty} days"
                        else: status = "♻️ General Stock"

                        with cols[i % 3]:
                            st.markdown(f"### {classification}")
                            st.markdown(f"**{item.get('item_name', 'Unknown')}**")
                            st.caption(f"Vendor: {item.get('merchant', 'Unknown')}")
                            st.write(f"Cost: ${price}")
                            st.write(f"Status: {status}")
                            st.write(f"⚡ +{credits} Credits")
                            st.markdown("---")

                    new_level = (st.session_state.total_credits // 100) + 1
                    if new_level > st.session_state.level:
                        st.session_state.level = new_level
                        st.balloons()
                        st.toast(f"🎖️ CLEARANCE UPGRADE: Level {new_level}", icon="🎖️")

                    check_commendations()

                except Exception as e:
                    st.error(f"❌ SYSTEM ERROR: {e}")
                    st.code(raw_text) # This helps us debug what the AI actually sent
