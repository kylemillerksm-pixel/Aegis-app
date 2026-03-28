import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io
import supabase

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

# Google AI
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ SYSTEM ERROR: Google API Key missing from secrets.")
    st.stop()

# Supabase — BOTH keys must live in st.secrets, never hardcoded
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supa_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ DATABASE CONNECTION FAILED: {e}")
    st.stop()

# ─────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────
if 'total_credits' not in st.session_state:
    st.session_state.total_credits = 0
if 'level' not in st.session_state:
    st.session_state.level = 1
if 'badges' not in st.session_state:
    st.session_state.badges = {
        "First Acquisition": False,
        "High Roller": False,
        "Asset Manager": False,
        "Operational": False,
        "Quartermaster": False
    }

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def classify_item(price: float) -> str:
    """Return rarity label based on price."""
    if price > 1000:
        return "🟡 EXOTIC"
    elif price > 200:
        return "🟣 LEGENDARY"
    elif price > 50:
        return "🔵 RARE"
    else:
        return "⚪ COMMON"


def extract_json(raw: str) -> list:
    """
    Robustly extract a JSON list from Gemini's response.
    Handles:
      - ```json ... ``` fences
      - ``` ... ``` fences
      - Bare JSON with surrounding prose
      - Single dict instead of list
    Raises ValueError with a clear message if nothing parses.
    """
    # Strip common markdown fences
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    # First attempt — try the whole cleaned string
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, list) else [result]
    except json.JSONDecodeError:
        pass

    # Second attempt — find the first [ ... ] block in the response
    start = cleaned.find("[")
    end   = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end + 1])
            return result if isinstance(result, list) else [result]
        except json.JSONDecodeError:
            pass

    # Third attempt — find the first { ... } block (single item)
    start = cleaned.find("{")
    end   = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end + 1])
            return [result]
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Gemini did not return valid JSON. Raw response preview:\n\n{raw[:300]}"
    )


def compress_image(uploaded_file) -> Image.Image:
    """Open and return a PIL Image from the uploaded file."""
    pil_image = Image.open(uploaded_file)
    # Convert RGBA/palette images to RGB so JPEG save works
    if pil_image.mode in ("RGBA", "P"):
        pil_image = pil_image.convert("RGB")
    return pil_image


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.title("🛡️ Operator Status")
st.sidebar.metric("Clearance Level", st.session_state.level)
st.sidebar.metric("System Credits",  st.session_state.total_credits)

# ─────────────────────────────────────────────
#  MAIN UI
# ─────────────────────────────────────────────
st.title("📡 Acquisition Scanner")
st.write("Upload a receipt image to catalog your assets.")

uploaded_file = st.file_uploader(
    "Select Image File...", type=["jpg", "png", "jpeg"]
)

if uploaded_file is not None:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.info("📷 Visual Input")
        st.image(uploaded_file, use_column_width=True)

    with col2:
        st.info("🔍 Ready to process")

        if st.button("⚡ Process Assets"):
            with st.spinner("Analyzing receipt..."):

                # ── 1. Prepare image ──────────────────────────
                try:
                    pil_image = compress_image(uploaded_file)
                except Exception as e:
                    st.error(f"Image Error: {e}")
                    st.stop()

                # ── 2. Build prompt ───────────────────────────
                # Explicit JSON-only instruction reduces prose wrapping
                prompt = """
You are Aegis, a logistics AI that analyzes purchase receipts.

Return ONLY a valid JSON array — no prose, no markdown fences, no explanation.

Each element must have these exact fields:
  "item_name"       : string
  "merchant"        : string
  "price"           : float (number only, no $ symbol)
  "purchase_date"   : string (YYYY-MM-DD, use today if not visible)
  "category"        : string (e.g. Electronics, Groceries, Clothing)
  "warranty_days"   : integer (0 if no warranty applies)
  "days_until_spoil": integer (0 if item does not spoil)

Rules:
- Items over $50: create one entry per item.
- Items under $50: you may group them into a single "Misc Items" entry.
- If a field is not visible on the receipt, make a reasonable estimate.
- Output ONLY the JSON array. Nothing else.
                """.strip()

                # ── 3. Call Gemini ────────────────────────────
                # Pass pil_image directly — SDK handles encoding correctly
                try:
                    model    = genai.GenerativeModel("gemini-2.5-flash")
                    response = model.generate_content([prompt, pil_image])
                    raw_text = response.text
                except Exception as e:
                    st.error(f"❌ AI Error: {e}")
                    st.stop()

                # ── 4. Parse JSON safely ──────────────────────
                try:
                    data = extract_json(raw_text)
                except ValueError as parse_err:
                    st.error(f"❌ SYSTEM ERROR: {parse_err}")
                    with st.expander("Raw AI response (for debugging)"):
                        st.code(raw_text)
                    st.stop()

                # ── 5. Display results ────────────────────────
                st.success(f"✅ CATALOGING COMPLETE — {len(data)} item(s) identified.")
                st.subheader("📦 Inventory Manifest")

                cols        = st.columns(3)
                items_to_save = []
                credits_earned = 0

                for i, item in enumerate(data):
                    price          = float(item.get("price", 0))
                    name           = item.get("item_name", "Unknown")
                    merchant       = item.get("merchant", "Unknown")
                    purchase_date  = item.get("purchase_date")
                    category       = item.get("category", "General")
                    warranty_days  = int(item.get("warranty_days", 0))
                    days_to_spoil  = int(item.get("days_until_spoil", 0))
                    classification = classify_item(price)
                    rarity_word    = classification.split(" ")[-1]

                    # Credits: 10 base + 1 per dollar over $50
                    item_credits = 10 + max(0, int(price - 50))
                    credits_earned += item_credits

                    items_to_save.append({
                        "item_name":       name,
                        "merchant":        merchant,
                        "price":           price,
                        "purchase_date":   purchase_date,
                        "category":        category,
                        "rarity":          rarity_word,
                        "warranty_days":   warranty_days,
                        "days_until_spoil":days_to_spoil,
                        "image_url":       uploaded_file.name,
                    })

                    with cols[i % 3]:
                        st.markdown(f"### {classification}")
                        st.markdown(f"**{name}**")
                        st.write(f"📍 {merchant}")
                        st.write(f"💰 ${price:.2f}")
                        if warranty_days > 0:
                            st.write(f"🛡️ Warranty: {warranty_days}d")
                        if days_to_spoil > 0:
                            st.write(f"⏳ Spoils in: {days_to_spoil}d")
                        st.markdown("---")

                # ── 6. Update session credits ─────────────────
                st.session_state.total_credits += credits_earned
                st.sidebar.metric(
                    "System Credits",
                    st.session_state.total_credits,
                    delta=f"+{credits_earned}"
                )

                # ── 7. Save to Supabase ───────────────────────
                try:
                    result = supa_client.table("items").insert(items_to_save).execute()
                    st.toast(
                        f"💾 {len(items_to_save)} item(s) saved to Vault.",
                        icon="💾"
                    )
                except Exception as db_error:
                    st.warning(f"Display works but database save failed: {db_error}")
                    st.info(
                        "Check Row Level Security (RLS) in Supabase. "
                        "Your anon key may not have INSERT permission on the items table."
                    )
