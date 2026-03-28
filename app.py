import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io
import supabase

# --- CONFIGURATION ---
# Google AI
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ SYSTEM ERROR: Google API Key missing.")
    st.stop()

# Supabase
try:
    SUPABASE_URL = "https://eeizfajopbpmjsxykgmz.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVlaXpmYWpvcGJwbWpzeHlrZ216Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MzU0NzQsImV4cCI6MjA5MDIxMTQ3NH0.pxnBz7yFfw69l5qR9RoW8rDmvKAkXvs8for_XaS05N0"
    supa_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ DATABASE CONNECTION FAILED: {e}")
    st.stop()

# --- SESSION STATE (Memory) ---
if 'total_credits' not in st.session_state:
    st.session_state.total_credits = 0 
if 'level' not in st.session_state:
    st.session_state.level = 1
if 'badges' not in st.session_state:
    st.session_state.badges = {
        "First Acquisition": False, "High Roller": False, 
        "Asset Manager": False, "Operational": False, "Quartermaster": False
    }

# --- SIDEBAR: SYSTEM STATUS ---
st.sidebar.title("🛡️ Operator Status")
st.sidebar.metric("Clearance Level", st.session_state.level)
st.sidebar.metric("System Credits", st.session_state.total_credits)

# --- MAIN APP ---
st.title("📡 Acquisition Scanner")
st.write("Upload purchase data to catalog assets.")

uploaded_file = st.file_uploader("Select Image File...", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.info("📷 Visual Input")
        st.image(uploaded_file, use_column_width=True)
    
    with col2:
        st.info("🔍 Processing...")
        
        # Image Compression
        try:
            pil_image = Image.open(uploaded_file)
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format='JPEG', quality=85)
            compressed_bytes = img_byte_arr.getvalue()
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
                    # 1. AI SCAN
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    response = model.generate_content([prompt, image_parts[0]])
                    raw_text = response.text.replace("```json", "").replace("```", "").strip()
                    
                    data = json.loads(raw_text)
                    if not isinstance(data, list): data = [data]
                    
                    st.success(f"✅ CATALOGING COMPLETE. {len(data)} items identified.")
                    st.subheader("📦 Inventory Manifest")
                    
                    cols = st.columns(3)
                    
                    items_to_save = []

                    for i, item in enumerate(data):
                        # Extract Data
                        price = float(item.get('price', 0))
                        name = item.get('item_name', 'Unknown')
                        
                        # Determine Rarity
                        if price > 1000: classification = "🟡 EXOTIC"
                        elif price > 200: classification = "🟣 LEGENDARY"
                        elif price > 50: classification = "🔵 RARE"
                        else: classification = "⚪ COMMON"
                        
                        # Prepare Data for Database
                        items_to_save.append({
                            "item_name": name,
                            "merchant": item.get('merchant'),
                            "price": price,
                            "purchase_date": item.get('purchase_date'),
                            "category": item.get('category'),
                            "rarity": classification.split(' ')[-1], # Just the word
                            "image_url": str(uploaded_file.name) # Placeholder
                        })

                        # UI Display
                        with cols[i % 3]:
                            st.markdown(f"### {classification}")
                            st.markdown(f"**{name}**")
                            st.write(f"Cost: ${price}")
                            st.markdown("---")

                    # 2. SAVE TO DATABASE (The New Logic)
                    try:
                        # We are inserting without a user_id for this MVP test
                        result = supa_client.table("items").insert(items_to_save).execute()
                        st.toast(f"💾 {len(items_to_save)} items saved to Vault.", icon="💾")
                    except Exception as db_error:
                        st.warning(f"Display works, but Database Save Failed: {db_error}")
                        st.info("This is likely due to Row Level Security (RLS). We will fix this next.")

                except Exception as e:
                    st.error(f"❌ SYSTEM ERROR: {e}")
