import streamlit as st
import pandas as pd
import re
import requests
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Inventory Search", layout="wide")
st.title("Inventory Search")

# ---------------------------------------------------------
# GitHub RAW FILE (DO NOT CHANGE THE NAME)
# ---------------------------------------------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/logisticsbiogeneindia-sys/Biogeneindia/main/Master-Stock Sheet Original.xlsx"

# ---------------------------------------------------------
# Load Excel From GitHub
# ---------------------------------------------------------
@st.cache_data(ttl=300)
def load_excel(url):
    r = requests.get(url)
    if r.status_code != 200:
        st.error("❌ Could not load Excel from GitHub.")
        return None
    return BytesIO(r.content)

excel_file = load_excel(GITHUB_RAW_URL)
if not excel_file:
    st.stop()

xl = pd.ExcelFile(excel_file)

# ---------------------------------------------------------
# ALWAYS USE SHEET "MasterSheet"
# ---------------------------------------------------------
MASTER_SHEET_NAME = "MasterSheet"

if MASTER_SHEET_NAME not in xl.sheet_names:
    st.error(f"❌ Sheet '{MASTER_SHEET_NAME}' not found in the Excel file!")
    st.write("Available sheets:", xl.sheet_names)
    st.stop()

df = xl.parse(MASTER_SHEET_NAME)
st.success("✔ Loaded sheet: MasterSheet")

# ---------------------------------------------------------
# Column Finder
# ---------------------------------------------------------
def find_column(df, possible_names):
    for col in df.columns:
        col_clean = re.sub(r'[^A-Za-z0-9]', '', col).lower()
        for name in possible_names:
            name_clean = re.sub(r'[^A-Za-z0-9]', '', name).lower()
            if col_clean == name_clean:
                return col

    for col in df.columns:
        for name in possible_names:
            if name.lower() in col.lower():
                return col

    return None


# Find columns
description_col = find_column(df, ["Description", "Item Description", "Desc"])
itemcode_col = find_column(df, ["Item Code", "ItemCode"])
group_col = find_column(df, ["Group", "Group Name"])
brand_col = find_column(df, ["Brand", "Brand Name"])
balance_col = find_column(df, ["Balance Qty", "Qty", "Quantity"])

# ---------------------------------------------------------
# Balance Qty Filter (default = > 0)
# ---------------------------------------------------------
st.sidebar.header("Filters")
balance_filter = st.sidebar.checkbox("Show only Balance Qty > 0", value=True)

if balance_col and balance_filter:
    df[balance_col] = pd.to_numeric(df[balance_col], errors="coerce")
    df = df[df[balance_col] > 0]

# ---------------------------------------------------------
# Search Box
# ---------------------------------------------------------
search_query = st.text_input("Search (Description / Item Code / Group / Brand)")

def contains_word(text, query):
    if pd.isna(text):
        return False
    pattern = r"\b" + re.escape(query) + r"\b"
    return re.search(pattern, str(text), re.IGNORECASE) is not None

if search_query.strip():
    q = search_query.strip()

    df_filtered = df[
        (df[description_col].apply(lambda x: contains_word(x, q)) if description_col else False)
        | df[itemcode_col].astype(str).str.contains(q, case=False, na=False)
        | df[group_col].astype(str).str.contains(q, case=False, na=False)
        | df[brand_col].astype(str).str.contains(q, case=False, na=False)
    ]
else:
    df_filtered = df

# ---------------------------------------------------------
# Show Results
# ---------------------------------------------------------
if df_filtered.empty:
    st.warning("No matching records found.")
else:
    st.write(f"### 🔍 Results ({len(df_filtered)} rows)")
    st.dataframe(df_filtered, use_container_width=True)

    # Download
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_filtered.to_excel(writer, index=False, sheet_name="Results")

    st.download_button(
        label="📥 Download Results",
        data=output.getvalue(),
        file_name="filtered_inventory.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
