import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io
import supabase
import base64
from datetime import date, timedelta

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ SYSTEM ERROR: Google API Key missing from secrets.")
    st.stop()

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supa_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ DATABASE CONNECTION FAILED: {e}")
    st.stop()

# ─────────────────────────────────────────────
#  LEVEL SYSTEM
# ─────────────────────────────────────────────

LEVELS = [
    (0,    "Recruit"),
    (500,  "Operative"),
    (1000, "Specialist"),
    (2000, "Agent"),
    (3500, "Commander"),
    (5000, "Director"),
    (7500, "Executive"),
    (10000,"Sovereign"),
]

def get_level_info(credits: int) -> dict:
    """Return current level number, title, progress to next level."""
    current_lvl  = 1
    current_name = "Recruit"
    current_min  = 0
    next_min     = 500

    for i, (threshold, title) in enumerate(LEVELS):
        if credits >= threshold:
            current_lvl  = i + 1
            current_name = title
            current_min  = threshold
            next_min     = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else None

    if next_min is None:
        progress   = 1.0
        credits_to = 0
        at_max     = True
    else:
        span       = next_min - current_min
        earned     = credits - current_min
        progress   = earned / span if span > 0 else 1.0
        credits_to = next_min - credits
        at_max     = False

    return {
        "level":      current_lvl,
        "title":      current_name,
        "progress":   progress,
        "credits_to": credits_to,
        "at_max":     at_max,
        "next_title": LEVELS[current_lvl][1] if current_lvl < len(LEVELS) else None,
    }

# ─────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────
defaults = {
    "total_credits": 0,
    "badges": {
        "First Acquisition": False,
        "High Roller":        False,
        "Asset Manager":      False,
        "Operational":        False,
        "Quartermaster":      False,
    },
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def classify_item(price: float) -> str:
    if price > 1000:  return "🟡 EXOTIC"
    elif price > 200: return "🟣 LEGENDARY"
    elif price > 50:  return "🔵 RARE"
    else:             return "⚪ COMMON"


def get_item_emoji(item_name: str, category: str) -> tuple:
    """
    Returns (emoji, bg_color) based on item name and category.
    Checks specific keywords first, falls back to category.
    """
    name = (item_name or "").lower()
    cat  = (category or "").lower()

    # Specific item keywords — checked first
    keywords = {
        # Flowers
        "rose":         ("🌹", "#8B1A1A"),
        "tulip":        ("🌷", "#C2185B"),
        "sunflower":    ("🌻", "#F57F17"),
        "orchid":       ("🌸", "#880E4F"),
        "lily":         ("💐", "#6A1B9A"),
        "daisy":        ("🌼", "#F9A825"),
        "lavender":     ("💜", "#6A1B9A"),
        "bouquet":      ("💐", "#AD1457"),
        "carnation":    ("🌸", "#C2185B"),
        "peony":        ("🌺", "#AD1457"),
        "hydrangea":    ("🌸", "#1565C0"),
        "mums":         ("🌼", "#E65100"),
        "flower":       ("🌸", "#AD1457"),
        "floral":       ("💐", "#AD1457"),
        # Produce
        "banana":       ("🍌", "#F57F17"),
        "apple":        ("🍎", "#B71C1C"),
        "orange":       ("🍊", "#E65100"),
        "lemon":        ("🍋", "#F9A825"),
        "lime":         ("🍋", "#2E7D32"),
        "strawberr":    ("🍓", "#B71C1C"),
        "blueberr":     ("🫐", "#1565C0"),
        "grape":        ("🍇", "#6A1B9A"),
        "watermelon":   ("🍉", "#2E7D32"),
        "pineapple":    ("🍍", "#F57F17"),
        "mango":        ("🥭", "#E65100"),
        "avocado":      ("🥑", "#2E7D32"),
        "broccoli":     ("🥦", "#2E7D32"),
        "carrot":       ("🥕", "#E65100"),
        "tomato":       ("🍅", "#B71C1C"),
        "corn":         ("🌽", "#F9A825"),
        "spinach":      ("🥬", "#2E7D32"),
        "lettuce":      ("🥬", "#2E7D32"),
        "kale":         ("🥬", "#1B5E20"),
        "pepper":       ("🫑", "#2E7D32"),
        "mushroom":     ("🍄", "#795548"),
        "onion":        ("🧅", "#795548"),
        "garlic":       ("🧄", "#795548"),
        "potato":       ("🥔", "#795548"),
        "cucumber":     ("🥒", "#2E7D32"),
        # Dairy
        "milk":         ("🥛", "#1565C0"),
        "egg":          ("🥚", "#F9A825"),
        "butter":       ("🧈", "#F9A825"),
        "yogurt":       ("🥛", "#1565C0"),
        "cheese":       ("🧀", "#F57F17"),
        "cream":        ("🥛", "#1565C0"),
        # Meat
        "chicken":      ("🍗", "#E65100"),
        "beef":         ("🥩", "#B71C1C"),
        "steak":        ("🥩", "#B71C1C"),
        "pork":         ("🥩", "#C62828"),
        "bacon":        ("🥓", "#B71C1C"),
        "salmon":       ("🐟", "#E65100"),
        "shrimp":       ("🍤", "#E65100"),
        "fish":         ("🐟", "#1565C0"),
        "turkey":       ("🦃", "#795548"),
        "sausage":      ("🌭", "#C62828"),
        # Bread
        "bread":        ("🍞", "#795548"),
        "bagel":        ("🥯", "#795548"),
        "muffin":       ("🧁", "#AD1457"),
        "donut":        ("🍩", "#AD1457"),
        "croissant":    ("🥐", "#F57F17"),
        "cake":         ("🎂", "#AD1457"),
        "cookie":       ("🍪", "#795548"),
        "tortilla":     ("🫓", "#F9A825"),
        # Electronics
        "iphone":       ("📱", "#1565C0"),
        "samsung":      ("📱", "#1565C0"),
        "phone":        ("📱", "#1565C0"),
        "laptop":       ("💻", "#263238"),
        "macbook":      ("💻", "#263238"),
        "computer":     ("🖥️", "#263238"),
        "tv":           ("📺", "#1565C0"),
        "television":   ("📺", "#1565C0"),
        "ipad":         ("📱", "#1565C0"),
        "tablet":       ("📱", "#1565C0"),
        "airpods":      ("🎧", "#263238"),
        "headphone":    ("🎧", "#263238"),
        "earbud":       ("🎧", "#263238"),
        "speaker":      ("🔊", "#1565C0"),
        "camera":       ("📷", "#263238"),
        "playstation":  ("🎮", "#1565C0"),
        "xbox":         ("🎮", "#2E7D32"),
        "nintendo":     ("🎮", "#B71C1C"),
        "watch":        ("⌚", "#263238"),
        "printer":      ("🖨️", "#455A64"),
        "router":       ("📡", "#1565C0"),
        "kindle":       ("📖", "#263238"),
        "charger":      ("🔌", "#455A64"),
        # Appliances
        "refrigerator": ("🧊", "#1565C0"),
        "fridge":       ("🧊", "#1565C0"),
        "washer":       ("🫧", "#1565C0"),
        "dryer":        ("🌀", "#455A64"),
        "dishwasher":   ("🫧", "#1565C0"),
        "microwave":    ("📦", "#455A64"),
        "air fryer":    ("🍳", "#E65100"),
        "blender":      ("🫙", "#1565C0"),
        "coffee":       ("☕", "#795548"),
        "toaster":      ("🍞", "#E65100"),
        "vacuum":       ("🌀", "#455A64"),
        "roomba":       ("🤖", "#1565C0"),
        "iron":         ("👔", "#455A64"),
        "hair dryer":   ("💨", "#E65100"),
        # Home
        "mattress":     ("🛏️", "#455A64"),
        "sofa":         ("🛋️", "#795548"),
        "couch":        ("🛋️", "#795548"),
        "desk":         ("🪑", "#795548"),
        "chair":        ("🪑", "#795548"),
        "lamp":         ("💡", "#F9A825"),
        "rug":          ("🪄", "#795548"),
        "curtain":      ("🪟", "#1565C0"),
        "mirror":       ("🪞", "#455A64"),
        "bedding":      ("🛏️", "#1565C0"),
        "towel":        ("🧺", "#1565C0"),
        # Clothing
        "shoes":        ("👟", "#263238"),
        "sneakers":     ("👟", "#263238"),
        "boots":        ("👢", "#795548"),
        "jacket":       ("🧥", "#263238"),
        "coat":         ("🧥", "#263238"),
        "jeans":        ("👖", "#1565C0"),
        "shirt":        ("👕", "#1565C0"),
        "dress":        ("👗", "#AD1457"),
        "hat":          ("🧢", "#263238"),
        "socks":        ("🧦", "#263238"),
        "gloves":       ("🧤", "#263238"),
        # Auto
        "tire":         ("🔧", "#263238"),
        "battery":      ("🔋", "#263238"),
        "oil":          ("🛢️", "#263238"),
        "wiper":        ("🚗", "#263238"),
        "car seat":     ("💺", "#263238"),
        # Health
        "vitamin":      ("💊", "#2E7D32"),
        "supplement":   ("💊", "#2E7D32"),
        "medicine":     ("💊", "#B71C1C"),
        "sunscreen":    ("🧴", "#E65100"),
        # Beverages
        "juice":        ("🧃", "#E65100"),
        "wine":         ("🍷", "#6A1B9A"),
        "beer":         ("🍺", "#F57F17"),
        "coffee":       ("☕", "#795548"),
        "tea":          ("🍵", "#2E7D32"),
        "soda":         ("🥤", "#B71C1C"),
        "water":        ("💧", "#1565C0"),
    }

    # Check specific keywords
    for keyword, (emoji, color) in keywords.items():
        if keyword in name:
            return emoji, color

    # Fall back to category
    category_defaults = {
        "electronics":  ("📱", "#1565C0"),
        "appliances":   ("⚡", "#E65100"),
        "groceries":    ("🛒", "#2E7D32"),
        "flowers":      ("🌸", "#AD1457"),
        "food":         ("🍽️", "#E65100"),
        "clothing":     ("👕", "#263238"),
        "home":         ("🏠", "#795548"),
        "auto":         ("🚗", "#263238"),
        "health":       ("💊", "#2E7D32"),
        "household":    ("🧺", "#455A64"),
        "other":        ("📦", "#455A64"),
    }

    for key, val in category_defaults.items():
        if key in cat:
            return val

    return ("📦", "#455A64")


def extract_json(raw: str) -> list:
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    for start_ch, end_ch in [("[", "]"), ("{", "}")]:
        s = cleaned.find(start_ch)
        e = cleaned.rfind(end_ch)
        if s != -1 and e != -1 and e > s:
            try:
                result = json.loads(cleaned[s:e + 1])
                return result if isinstance(result, list) else [result]
            except json.JSONDecodeError:
                pass
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, list) else [result]
    except json.JSONDecodeError:
        pass
    raise ValueError(
        f"Gemini did not return valid JSON.\n\nRaw preview:\n{raw[:400]}"
    )


def compress_image(uploaded_file) -> Image.Image:
    img = Image.open(uploaded_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    return img


def urgency_label(days: int) -> tuple:
    if days <= 0:    return "🔴", "EXPIRED",  "#FF4B4B"
    elif days <= 3:  return "🟠", "CRITICAL", "#FF8C00"
    elif days <= 7:  return "🟡", "WARNING",  "#FFD700"
    elif days <= 30: return "🔵", "MONITOR",  "#1E90FF"
    else:            return "🟢", "SECURE",   "#00C851"


def fetch_all_items() -> list:
    try:
        result = (
            supa_client
            .table("items")
            .select("*")
            .order("id", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        st.error(f"Failed to load vault: {e}")
        return []


def compute_days_left(purchase_date_str: str, warranty_days: int) -> int:
    try:
        purchased = date.fromisoformat(str(purchase_date_str))
        expiry    = purchased + timedelta(days=warranty_days)
        return (expiry - date.today()).days
    except Exception:
        return warranty_days


def check_badge_unlocks(items: list):
    total_items = len(items)
    total_value = sum(float(i.get("price", 0)) for i in items)
    has_rare    = any(i.get("rarity") in ("RARE", "LEGENDARY", "EXOTIC") for i in items)
    badges      = st.session_state.badges

    if total_items >= 1 and not badges["First Acquisition"]:
        badges["First Acquisition"] = True
        st.toast("🏅 Badge Unlocked: First Acquisition!", icon="🏅")
    if total_value >= 500 and not badges["High Roller"]:
        badges["High Roller"] = True
        st.toast("🏅 Badge Unlocked: High Roller!", icon="🏅")
    if total_items >= 10 and not badges["Asset Manager"]:
        badges["Asset Manager"] = True
        st.toast("🏅 Badge Unlocked: Asset Manager!", icon="🏅")
    if has_rare and not badges["Operational"]:
        badges["Operational"] = True
        st.toast("🏅 Badge Unlocked: Operational!", icon="🏅")
    if total_items >= 25 and not badges["Quartermaster"]:
        badges["Quartermaster"] = True
        st.toast("🏅 Badge Unlocked: Quartermaster!", icon="🏅")

    st.session_state.badges = badges


def save_items_to_db(items_to_save: list, source_name: str) -> bool:
    try:
        supa_client.table("items").insert(items_to_save).execute()
        st.toast(
            f"💾 {len(items_to_save)} item(s) from {source_name} saved to Vault.",
            icon="💾"
        )
        check_badge_unlocks(fetch_all_items())
        return True
    except Exception as db_error:
        st.warning(f"Display works but database save failed: {db_error}")
        st.info(
            "Fix: Supabase → SQL Editor → run:\n"
            "ALTER TABLE public.items DISABLE ROW LEVEL SECURITY;"
        )
        return False


def display_items(data: list, purchase_date_default: str, source_name: str) -> list:
    st.success(f"✅ CATALOGING COMPLETE — {len(data)} item(s) identified.")
    st.subheader("📦 Inventory Manifest")

    cols           = st.columns(3)
    items_to_save  = []
    credits_earned = 0

    for i, item in enumerate(data):
        price          = float(item.get("price", 0))
        name           = item.get("item_name", "Unknown")
        merchant       = item.get("merchant", "Unknown")
        purchase_date  = item.get("purchase_date", purchase_date_default)
        category       = item.get("category", "General")
        warranty_days  = int(item.get("warranty_days", 0))
        days_to_spoil  = int(item.get("days_until_spoil", 0))

        # Override with knowledge base data if available — more accurate than Gemini guess
        kb_match = lookup_knowledge_base(name)
        if kb_match:
            if kb_match.get("warranty_days") is not None:
                warranty_days = int(kb_match["warranty_days"])
            if kb_match.get("days_until_spoil") is not None:
                days_to_spoil = int(kb_match["days_until_spoil"])
        classification = classify_item(price)
        rarity_word    = classification.split(" ")[-1]
        item_credits   = 10 + max(0, int(price - 50))
        credits_earned += item_credits

        items_to_save.append({
            "item_name":        name,
            "merchant":         merchant,
            "price":            price,
            "purchase_date":    purchase_date,
            "category":         category,
            "rarity":           rarity_word,
            "warranty_days":    warranty_days,
            "days_until_spoil": days_to_spoil,
            "image_url":        source_name,
        })

        with cols[i % 3]:
            st.markdown(f"### {classification}")
            st.markdown(f"**{name}**")
            st.write(f"📍 {merchant}")
            st.write(f"💰 ${price:.2f}")
            if warranty_days > 0:
                days_left = compute_days_left(purchase_date, warranty_days)
                emoji, label, _ = urgency_label(days_left)
                st.write(f"🛡️ Warranty: {warranty_days}d {emoji} {label}")
            if days_to_spoil > 0:
                emoji, label, _ = urgency_label(days_to_spoil)
                st.write(f"⏳ Spoils in: {days_to_spoil}d {emoji} {label}")
            st.markdown("---")

    st.session_state.total_credits += credits_earned
    return items_to_save


def lookup_knowledge_base(item_name: str) -> dict:
    """
    Check product_knowledge table for exact or partial match.
    Returns dict with warranty_days and days_until_spoil if found.
    Returns None if no match found.
    """
    if not item_name:
        return None
    try:
        # Try to find a keyword match in the item name
        keywords_result = supa_client.table("product_knowledge").select("*").execute()
        if not keywords_result.data:
            return None

        item_lower = item_name.lower()
        best_match = None

        for row in keywords_result.data:
            keyword = (row.get("item_keyword") or "").lower()
            if keyword and keyword in item_lower:
                # Prefer longer keyword matches (more specific)
                if best_match is None or len(keyword) > len(best_match.get("item_keyword", "")):
                    best_match = row

        return best_match
    except Exception:
        return None


def build_prompt(source_type: str) -> str:
    base = """
You are Aegis, an expert logistics and consumer protection AI.

Analyze the receipt and return ONLY a valid JSON array. No prose, no markdown, no explanation.

Each element must have these exact fields:
  "item_name"        : string (specific product name)
  "merchant"         : string (store or company name)
  "price"            : float (number only, no $ symbol, 0 if not found)
  "purchase_date"    : string (YYYY-MM-DD, use today if not visible)
  "category"         : string (Electronics, Groceries, Flowers, Clothing, Appliances, Food, Auto, Home, Health, Household, Other)
  "warranty_days"    : integer (0 for food/perishables)
  "days_until_spoil" : integer (0 for non-perishables)

SMART GROUPING RULES — critical:

ALWAYS give an item its OWN entry if ANY of these are true:
- It is perishable (food, flowers, produce, meat, dairy) — even if under $1
- It costs more than $10
- It has a warranty
- It has a known spoil date

ONLY group items if ALL of these are true:
- Non-perishable (cleaning supplies, paper goods, personal care, household items)
- Under $10 each
- No warranty
- No spoil date
Group these as "Household Supplies (N items)" with category "Household", warranty_days=0, days_until_spoil=0

WARRANTY RULES:
- Smartphones, laptops, TVs, appliances, headphones, gaming consoles, furniture: 365 days
- Clothing and shoes: 30 days
- Food, groceries, flowers, perishables: 0
- Unknown electronics: 365
- Everything else with no visible warranty: 0

SPOILAGE RULES — use precise knowledge:
Flowers: Roses=7, Tulips=5, Sunflowers=6, Lilies=7, Orchids=14, Mixed bouquet=6, Any cut flowers=7
Produce: Bananas=5, Apples=21, Berries=5, Grapes=7, Leafy greens=5, Broccoli=7, Carrots=21, Tomatoes=5, Avocados=2, Citrus=14
Dairy: Milk=7, Yogurt=14, Hard cheese=21, Soft cheese=7, Butter=30, Eggs=21
Meat: Raw chicken=2, Raw beef/pork=3, Raw fish=1, Deli meat=5, Bacon=7
Bread: Fresh bread=5, Pastries=2, Bagels=5
Prepared food: Leftovers=3, Deli prepared=3
Canned goods, frozen food, chips, snacks sealed: days_until_spoil=0

Output ONLY the JSON array. Nothing else.
    """.strip()

    if source_type == "pdf":
        return base + "\n\nThis is a PDF document — warranty certificate, invoice, insurance policy, or emailed receipt."
    else:
        return base + "\n\nThis is a receipt image. Extract all items purchased."


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────

lvl_info = get_level_info(st.session_state.total_credits)

st.sidebar.title("🛡️ AEGIS")
st.sidebar.caption("Your purchases, protected.")
st.sidebar.divider()

# Level display — clean single block
st.sidebar.markdown(
    f"""
    <div style='text-align:center;padding:10px 0'>
        <div style='font-size:13px;color:gray;letter-spacing:0.08em;text-transform:uppercase'>
            Clearance Level
        </div>
        <div style='font-size:32px;font-weight:700;line-height:1.1'>
            {lvl_info['level']}
        </div>
        <div style='font-size:15px;font-weight:500;color:#D4A017;letter-spacing:0.05em'>
            {lvl_info['title'].upper()}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Progress bar to next level
if lvl_info["at_max"]:
    st.sidebar.progress(1.0, text="MAX LEVEL ACHIEVED")
else:
    st.sidebar.progress(
        lvl_info["progress"],
        text=f"{lvl_info['credits_to']} credits to {lvl_info['next_title']}"
    )

# Credits — single clean display
st.sidebar.markdown(
    f"""
    <div style='text-align:center;padding:8px 0 4px'>
        <div style='font-size:11px;color:gray;letter-spacing:0.08em;text-transform:uppercase'>
            System Credits
        </div>
        <div style='font-size:22px;font-weight:600'>
            {st.session_state.total_credits:,}
        </div>
        <div style='font-size:11px;color:gray'>
            +10 per item scanned · +$1 per dollar over $50
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.divider()
st.sidebar.subheader("🏅 Badges")
for badge, earned in st.session_state.badges.items():
    icon = "✅" if earned else "🔒"
    st.sidebar.write(f"{icon} {badge}")

# ─────────────────────────────────────────────
#  NAVIGATION
# ─────────────────────────────────────────────
st.sidebar.divider()
page = st.sidebar.radio(
    "Navigation",
    ["📡 Scanner", "📄 PDF Scanner", "⚠️ Expiry Alerts", "🗄️ Vault"],
    label_visibility="collapsed"
)

# ═══════════════════════════════════════════════
#  PAGE 1 — IMAGE SCANNER
# ═══════════════════════════════════════════════
if page == "📡 Scanner":
    st.title("📡 Acquisition Scanner")
    st.caption("Upload a receipt photo to catalog your assets and track warranties.")

    uploaded_file = st.file_uploader(
        "Select receipt image...", type=["jpg", "png", "jpeg"]
    )

    if uploaded_file is not None:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.info("📷 Visual Input")
            st.image(uploaded_file, use_column_width=True)

        with col2:
            st.info("🔍 Ready to process")

            if st.button("⚡ Process Assets", use_container_width=True):
                with st.spinner("Analyzing receipt..."):

                    try:
                        pil_image = compress_image(uploaded_file)
                    except Exception as e:
                        st.error(f"Image Error: {e}")
                        st.stop()

                    try:
                        model    = genai.GenerativeModel("gemini-2.5-flash")
                        response = model.generate_content(
                            [build_prompt("image"), pil_image]
                        )
                        raw_text = response.text
                    except Exception as e:
                        st.error(f"❌ AI Error: {e}")
                        st.stop()

                    try:
                        data = extract_json(raw_text)
                    except ValueError as parse_err:
                        st.error(f"❌ SYSTEM ERROR: {parse_err}")
                        with st.expander("Raw AI response (debug)"):
                            st.code(raw_text)
                        st.stop()

                    items_to_save = display_items(
                        data, str(date.today()), uploaded_file.name
                    )
                    save_items_to_db(items_to_save, uploaded_file.name)

# ═══════════════════════════════════════════════
#  PAGE 2 — PDF SCANNER
# ═══════════════════════════════════════════════
elif page == "📄 PDF Scanner":
    st.title("📄 Document Scanner")
    st.caption(
        "Upload old warranty certificates, invoices, insurance policies, "
        "or emailed receipts as PDFs. Aegis extracts everything automatically."
    )

    st.info(
        "💡 This is your unfair advantage. Scan documents you received months "
        "or years ago — recover warranties you didn't know you still had."
    )

    uploaded_pdf = st.file_uploader(
        "Select PDF document...", type=["pdf"]
    )

    if uploaded_pdf is not None:
        st.success(f"📄 Document loaded: {uploaded_pdf.name}")
        file_size = len(uploaded_pdf.getvalue()) / 1024
        st.caption(f"File size: {file_size:.1f} KB")

        if st.button("⚡ Scan Document", use_container_width=True):
            with st.spinner("Reading document..."):

                # Read PDF bytes and encode as base64
                pdf_bytes  = uploaded_pdf.getvalue()
                pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

                # Send to Gemini as a document part
                try:
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    response = model.generate_content([
                        {
                            "parts": [
                                {
                                    "inline_data": {
                                        "mime_type": "application/pdf",
                                        "data":      pdf_base64,
                                    }
                                },
                                {
                                    "text": build_prompt("pdf")
                                }
                            ]
                        }
                    ])
                    raw_text = response.text
                except Exception as e:
                    st.error(f"❌ AI Error: {e}")
                    st.stop()

                try:
                    data = extract_json(raw_text)
                except ValueError as parse_err:
                    st.error(f"❌ SYSTEM ERROR: {parse_err}")
                    with st.expander("Raw AI response (debug)"):
                        st.code(raw_text)
                    st.stop()

                items_to_save = display_items(
                    data, str(date.today()), uploaded_pdf.name
                )
                save_items_to_db(items_to_save, uploaded_pdf.name)

# ═══════════════════════════════════════════════
#  PAGE 3 — EXPIRY ALERTS
# ═══════════════════════════════════════════════
elif page == "⚠️ Expiry Alerts":
    st.title("⚠️ Expiry Alerts")
    st.caption("Everything expiring soon — warranties and perishables.")

    all_items = fetch_all_items()

    if not all_items:
        st.info("No items in vault yet. Scan a receipt to get started.")
        st.stop()

    alerts = []

    for item in all_items:
        name          = item.get("item_name", "Unknown")
        merchant      = item.get("merchant", "Unknown")
        price         = float(item.get("price", 0))
        purchase_date = item.get("purchase_date")
        warranty_days = int(item.get("warranty_days") or 0)
        days_to_spoil = int(item.get("days_until_spoil") or 0)

        if warranty_days > 0 and purchase_date:
            days_left = compute_days_left(purchase_date, warranty_days)
            if days_left <= 30:
                alerts.append({
                    "name":     name,
                    "merchant": merchant,
                    "price":    price,
                    "type":     "Warranty",
                    "days":     days_left,
                    "category": item.get("category", ""),
                })

        if days_to_spoil > 0 and days_to_spoil <= 7:
            alerts.append({
                "name":     name,
                "merchant": merchant,
                "price":    price,
                "type":     "Perishable",
                "days":     days_to_spoil,
                "category": item.get("category", ""),
            })

    alerts.sort(key=lambda x: x["days"])

    if not alerts:
        st.success("✅ All clear. Nothing expiring in the next 30 days.")
    else:
        expired_count  = sum(1 for a in alerts if a["days"] <= 0)
        critical_count = sum(1 for a in alerts if 0 < a["days"] <= 3)
        warning_count  = sum(1 for a in alerts if 3 < a["days"] <= 7)
        monitor_count  = sum(1 for a in alerts if 7 < a["days"] <= 30)
        at_risk_value  = sum(a["price"] for a in alerts)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("🔴 Expired",  expired_count)
        m2.metric("🟠 Critical", critical_count)
        m3.metric("🟡 Warning",  warning_count)
        m4.metric("🔵 Monitor",  monitor_count)
        m5.metric("💰 At Risk",  f"${at_risk_value:,.2f}")

        st.divider()

        for alert in alerts:
            urgency_emoji, label, color = urgency_label(alert["days"])
            days_text = (
                "EXPIRED"
                if alert["days"] <= 0
                else f"{alert['days']} day{'s' if alert['days'] != 1 else ''} left"
            )
            item_emoji, emoji_color = get_item_emoji(
                alert.get("name", ""), alert.get("category", "")
            )

            c0, c1, c2, c3, c4 = st.columns([1, 3, 2, 2, 2])
            with c0:
                st.markdown(
                    f"<div style='width:40px;height:40px;background:{emoji_color}22;"
                    f"border:1px solid {emoji_color}55;border-radius:10px;"
                    f"display:flex;align-items:center;justify-content:center;"
                    f"font-size:20px;margin-top:4px'>{item_emoji}</div>",
                    unsafe_allow_html=True
                )
            with c1:
                st.markdown(f"**{alert['name']}**")
                st.caption(f"📍 {alert['merchant']}")
            with c2:
                st.write(f"💰 ${alert['price']:.2f}")
            with c3:
                icon = "🛡️" if alert["type"] == "Warranty" else "🥗"
                st.write(f"{icon} {alert['type']}")
            with c4:
                st.markdown(
                    f"<span style='color:{color};font-weight:600'>"
                    f"{urgency_emoji} {days_text}</span>",
                    unsafe_allow_html=True,
                )
            st.divider()

# ═══════════════════════════════════════════════
#  PAGE 4 — VAULT
# ═══════════════════════════════════════════════
elif page == "🗄️ Vault":
    st.title("🗄️ The Vault")
    st.caption("Every asset you have ever cataloged.")

    all_items = fetch_all_items()

    if not all_items:
        st.info("Vault is empty. Scan a receipt to add your first asset.")
        st.stop()

    # ── Summary metrics ─────────────────────────────────────────
    total_value    = sum(float(i.get("price", 0)) for i in all_items)
    warranty_count = sum(1 for i in all_items if int(i.get("warranty_days") or 0) > 0)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Assets",   len(all_items))
    m2.metric("Total Value",    f"${total_value:,.2f}")
    m3.metric("Under Warranty", warranty_count)

    st.divider()

    # ── SMART ROW: Expiring This Week ───────────────────────────
    expiring = []
    for item in all_items:
        warranty_days = int(item.get("warranty_days") or 0)
        days_to_spoil = int(item.get("days_until_spoil") or 0)
        purchase_date = item.get("purchase_date")

        if warranty_days > 0 and purchase_date:
            days_left = compute_days_left(purchase_date, warranty_days)
            if 0 <= days_left <= 7:
                expiring.append({**item, "days": days_left, "type": "Warranty"})

        if days_to_spoil > 0 and days_to_spoil <= 7:
            expiring.append({**item, "days": days_to_spoil, "type": "Perishable"})

    expiring.sort(key=lambda x: x["days"])

    st.subheader("🔴 Expiring This Week")
    if not expiring:
        st.success("✅ Nothing expiring this week — all clear.")
    else:
        for item in expiring:
            emoji, label, color = urgency_label(item["days"])
            icon = "🛡️" if item["type"] == "Warranty" else "🥗"
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{item.get('item_name', 'Unknown')}**")
                st.caption(f"📍 {item.get('merchant', '—')}")
            with c2:
                st.write(f"{icon} {item['type']} · ${float(item.get('price',0)):.2f}")
            with c3:
                st.markdown(
                    f"<span style='color:{color};font-weight:600'>{emoji} {item['days']}d left</span>",
                    unsafe_allow_html=True
                )
            st.divider()

    # ── SMART ROW: High Value Assets ────────────────────────────
    st.subheader("💎 High Value Assets")
    high_value = sorted(
        [i for i in all_items if float(i.get("price", 0)) >= 50],
        key=lambda x: float(x.get("price", 0)),
        reverse=True
    )[:5]

    if not high_value:
        st.info("No high value items yet — items over $50 appear here.")
    else:
        for item in high_value:
            price         = float(item.get("price", 0))
            warranty_days = int(item.get("warranty_days") or 0)
            purchase_date = item.get("purchase_date")
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            with c1:
                st.markdown(f"**{item.get('item_name', 'Unknown')}**")
                st.caption(f"📍 {item.get('merchant', '—')} · {item.get('category', '—')}")
            with c2:
                st.write(classify_item(price))
            with c3:
                st.write(f"💰 ${price:.2f}")
            with c4:
                if warranty_days > 0 and purchase_date:
                    days_left = compute_days_left(purchase_date, warranty_days)
                    emoji, _, _ = urgency_label(days_left)
                    st.write(f"🛡️ {emoji} {days_left}d")
                else:
                    st.write("🛡️ —")
            st.divider()

    # ── SMART ROW: Recently Added ───────────────────────────────
    st.subheader("⚡ Recently Added")
    recent = all_items[:5]
    if not recent:
        st.info("No items yet.")
    else:
        for item in recent:
            price         = float(item.get("price", 0))
            days_to_spoil = int(item.get("days_until_spoil") or 0)
            warranty_days = int(item.get("warranty_days") or 0)
            purchase_date = item.get("purchase_date")
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            with c1:
                st.markdown(f"**{item.get('item_name', 'Unknown')}**")
                st.caption(f"📍 {item.get('merchant', '—')} · {item.get('category', '—')}")
            with c2:
                st.write(classify_item(price))
            with c3:
                st.write(f"💰 ${price:.2f}")
            with c4:
                if warranty_days > 0 and purchase_date:
                    days_left = compute_days_left(purchase_date, warranty_days)
                    emoji, _, _ = urgency_label(days_left)
                    st.write(f"🛡️ {emoji} {days_left}d")
                elif days_to_spoil > 0:
                    emoji, _, _ = urgency_label(days_to_spoil)
                    st.write(f"⏳ {emoji} {days_to_spoil}d")
                else:
                    st.write("—")
            st.divider()

    # ── SMART ROW: Perishables ──────────────────────────────────
    st.subheader("🥗 Perishables")
    perishables = sorted(
        [i for i in all_items if int(i.get("days_until_spoil") or 0) > 0],
        key=lambda x: int(x.get("days_until_spoil") or 0)
    )
    if not perishables:
        st.info("No perishables tracked yet.")
    else:
        for item in perishables:
            days_to_spoil = int(item.get("days_until_spoil") or 0)
            emoji, label, color = urgency_label(days_to_spoil)
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{item.get('item_name', 'Unknown')}**")
                st.caption(f"📍 {item.get('merchant', '—')}")
            with c2:
                st.write(f"💰 ${float(item.get('price', 0)):.2f}")
            with c3:
                st.markdown(
                    f"<span style='color:{color};font-weight:600'>{emoji} {days_to_spoil}d left</span>",
                    unsafe_allow_html=True
                )
            st.divider()

    # ── FULL REGISTRY ───────────────────────────────────────────
    st.subheader("🗄️ Full Registry")
    rarity_order = {"EXOTIC": 0, "LEGENDARY": 1, "RARE": 2, "COMMON": 3}
    sorted_all = sorted(
        all_items,
        key=lambda x: rarity_order.get(x.get("rarity", "COMMON"), 3),
    )
    for item in sorted_all:
        price         = float(item.get("price", 0))
        warranty_days = int(item.get("warranty_days") or 0)
        days_to_spoil = int(item.get("days_until_spoil") or 0)
        purchase_date = item.get("purchase_date")
        item_emoji, emoji_color = get_item_emoji(
            item.get("item_name", ""), item.get("category", "")
        )
        c0, c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 2, 2, 2])
        with c0:
            st.markdown(
                f"<div style='width:40px;height:40px;background:{emoji_color}22;"
                f"border:1px solid {emoji_color}55;border-radius:10px;"
                f"display:flex;align-items:center;justify-content:center;"
                f"font-size:20px;margin-top:4px'>{item_emoji}</div>",
                unsafe_allow_html=True
            )
        with c1:
            st.markdown(f"**{item.get('item_name', 'Unknown')}**")
            st.caption(f"📍 {item.get('merchant', '—')} · {item.get('category', '—')}")
        with c2:
            st.write(classify_item(price))
        with c3:
            st.write(f"💰 ${price:.2f}")
        with c4:
            if warranty_days > 0 and purchase_date:
                days_left = compute_days_left(purchase_date, warranty_days)
                emoji, _, _ = urgency_label(days_left)
                st.write(f"🛡️ {emoji} {days_left}d")
            else:
                st.write("🛡️ —")
        with c5:
            if days_to_spoil > 0:
                emoji, _, _ = urgency_label(days_to_spoil)
                st.write(f"⏳ {emoji} {days_to_spoil}d")
            else:
                st.write("⏳ —")
        st.divider()
