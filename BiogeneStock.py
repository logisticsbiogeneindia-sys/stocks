import streamlit as st
import pandas as pd
import re
import requests
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Inventory Search", layout="wide")

st.title("Inventory Search")

# -----------------------------
# GitHub MasterSheet File URL
# -----------------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/mohitsharma123/inv/main/mastersheet.xlsx"

@st.cache_data(ttl=300)
def load_excel_from_github(url):
    response = requests.get(url)
    if response.status_code != 200:
        st.error("❌ GitHub file not found or cannot be loaded.")
        return None
    return BytesIO(response.content)

excel_file = load_excel_from_github(GITHUB_RAW_URL)
if not excel_file:
    st.stop()

xl = pd.ExcelFile(excel_file)

# -----------------------------
# FORCE SELECT ONLY "MasterSheet"
# -----------------------------
MASTER_SHEET_NAME = "MasterSheet"

if MASTER_SHEET_NAME not in xl.sheet_names:
    st.error(f"❌ '{MASTER_SHEET_NAME}' sheet not found in file.")
    st.write("Available sheets:", xl.sheet_names)
    st.stop()

sheet_name = MASTER_SHEET_NAME
st.success(f"✔ Using sheet: **{sheet_name}**")

# Load sheet
df = xl.parse(sheet_name)

# -----------------------------
# FIND IMPORTANT COLUMNS
# -----------------------------
def find_column(df, possible_names):
    for col in df.columns:
        cleaned = re.sub(r"[^A-Za-z0-9]", "", col).lower()
        for target in possible_names:
            target_clean = re.sub(r"[^A-Za-z0-9]", "", target).lower()
            if cleaned == target_clean:
                return col
    for target in possible_names:
        for col in df.columns:
            if target.lower() in col.lower():
                return col
    return None

search_columns = {
    "Description": find_column(df, ["Description", "Desc", "Item Description", "Product Description"]),
    "Item Code": find_column(df, ["Item Code", "ItemCode", "Code"]),
    "Group Name": find_column(df, ["Group", "Group Name", "Category"]),
    "Brand": find_column(df, ["Brand", "Brand Name", "Make"]),
    "Quantity": find_column(df, ["Qty", "Quantity", "Balance Qty", "Available Qty", "Stock"])
}

balance_qty_col = search_columns["Quantity"]

# -----------------------------
# SIDEBAR FILTER FOR BALANCE QTY
# -----------------------------
filter_balance = st.sidebar.checkbox("Show only Balance Qty > 0", value=True)

if balance_qty_col and filter_balance:
    df[balance_qty_col] = pd.to_numeric(df[balance_qty_col], errors="coerce")
    df = df[df[balance_qty_col] > 0]

# -----------------------------
# SEARCH BOX
# -----------------------------
search_query = st.text_input("Search (Description / Item Code / Group / Brand):")

def contains_word(text, query):
    if pd.isna(text):
        return False
    pattern = r"\b" + re.escape(query) + r"\b"
    return re.search(pattern, str(text), flags=re.IGNORECASE) is not None

if search_query.strip():
    s = search_query.strip()

    filtered_df = df[
        df[search_columns["Description"]].apply(lambda x: contains_word(x, s) if search_columns["Description"] else False)
        | df[search_columns["Item Code"]].astype(str).str.contains(s, case=False, na=False)
        | df[search_columns["Group Name"]].astype(str).str.contains(s, case=False, na=False)
        | df[search_columns["Brand"]].astype(str).str.contains(s, case=False, na=False)
    ]
else:
    filtered_df = df

# -----------------------------
# DISPLAY RESULTS
# -----------------------------
if filtered_df.empty:
    st.warning("No matching records found.")
else:
    st.write(f"### 🔍 Results ({len(filtered_df)} rows)")
    st.dataframe(filtered_df, use_container_width=True)

    # Download Excel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"inventory_search_{timestamp}.xlsx"

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        filtered_df.to_excel(writer, index=False, sheet_name="Results")

    st.download_button(
        label="📥 Download Search Result",
        data=buffer.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
