import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="Aegis - Personal Inventory", page_icon="🛡️", layout="wide")

# --- CONFIGURATION (SECURE) ---
# This tries to find the key in Streamlit's secure 'Secrets' storage
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ App Configuration Error: API Key not found. Please contact support.")
    st.stop() # Stops the app if the key is missing

# --- MAIN APP ---
st.title("🛡️ AEGIS: Personal Inventory System")
st.write("Snap a photo of your receipt to decrypt your loot.")

# --- FILE UPLOADER ---
uploaded_file = st.file_uploader("Choose a receipt image...", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    # Display the image
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.info("📷 Receipt Preview")
        st.image(uploaded_file, caption='Uploaded Receipt', use_column_width=True)
    
    with col2:
        st.info("🔍 Decryption Progress")
        
        # Prepare image for Gemini
        bytes_data = uploaded_file.getvalue()
        image_parts = [
            {
                "mime_type": uploaded_file.type,
                "data": bytes_data
            }
        ]

        # --- THE PROMPT ---
        prompt = """
        You are a Game Master scanning a receipt for LOOT.
        
        1. Ignore consumables (food, drinks, cleaning supplies) unless they are expensive ($20+).
        2. Find ALL DURABLE GOODS on the receipt.
        3. Return a JSON LIST of items.
        
        Return ONLY valid JSON:
        [
          {
            "item_name": "string",
            "merchant": "string",
            "price": "float",
            "purchase_date": "YYYY-MM-DD",
            "category": "Electronics|Apparel|Home|Groceries|Furniture",
            "warranty_days": "integer (Estimate: Electronics=365, Apparel=90, Home=365, Consumables=0)"
          }
        ]
        """

        # --- SCAN BUTTON ---
        if st.button("Decrypt Loot"):
            with st.spinner("Contacting the Oracle..."):
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    response = model.generate_content([prompt, image_parts[0]])
                    raw_text = response.text.replace("```json", "").replace("```", "").strip()
                    
                    # Parse Data
                    data = json.loads(raw_text)
                    if not isinstance(data, list):
                        data = [data]
                    
                    st.success(f"✅ Scan Complete! Found {len(data)} items.")
                    
                    # --- DISPLAY RESULTS ---
                    st.subheader("📦 Inventory Manifest")
                    
                    # Create columns for grid layout
                    cols = st.columns(3)
                    
                    for i, item in enumerate(data):
                        price = item['price']
                        
                        # Determine Rarity
                        if price > 1000: rarity = "🟡 Exotic"
                        elif price > 200: rarity = "🟣 Legendary"
                        elif price > 50: rarity = "🔵 Rare"
                        else: rarity = "⚪ Common"
                        
                        # Determine Status
                        if item.get('warranty_days', 0) == 0:
                            status = "♻️ CONSUMABLE"
                        else:
                            status = f"🛡️ {item['warranty_days']} Days Warranty"

                        # UI Card
                        col_idx = i % 3
                        with cols[col_idx]:
                            st.markdown(f"### {rarity}")
                            st.markdown(f"**{item['item_name']}**")
                            st.caption(f"Merchant: {item['merchant']}")
                            st.write(f"Price: ${item['price']}")
                            st.write(f"Status: {status}")
                            
                            if status != "♻️ CONSUMABLE":
                                if st.button(f"Verify & Save", key=f"save_{i}"):
                                    st.toast("Item Saved to Vault! (Demo Mode)", icon="✅")
                            st.markdown("---")

                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    st.code(raw_text)
