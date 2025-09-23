import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import pytz
import requests
import base64
import io

# Optional: local GPT4All
try:
    from gpt4all import GPT4All
    LOCAL_MODEL_AVAILABLE = True
except:
    LOCAL_MODEL_AVAILABLE = False

# OpenAI import
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except:
    OPENAI_AVAILABLE = False

# -------------------------
# Helpers
# -------------------------
def normalize(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def find_column(df: pd.DataFrame, candidates: list) -> str | None:
    norm_map = {normalize(col): col for col in df.columns}
    for cand in candidates:
        key = normalize(cand)
        if key in norm_map:
            return norm_map[key]
    for cand in candidates:
        key = normalize(cand)
        for norm_col, orig in norm_map.items():
            if key in norm_col or norm_col in key:
                return orig
    return None

# -------------------------
# Config & Styling
# -------------------------
st.set_page_config(page_title="Biogene India - Inventory Viewer", layout="wide")
st.markdown("""
<style>
body {background-color: #f8f9fa; font-family: "Helvetica Neue", sans-serif;}
.navbar { display: flex; align-items: center; background-color: #004a99; padding: 8px 16px; border-radius: 8px; color: white; position: sticky; top: 0; z-index: 1000; }
.navbar img { height: 50px; margin-right: 15px; }
.navbar h1 { font-size: 24px; margin: 0; font-weight: 700; }
.footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #004a99; color: white; text-align: center; padding: 8px; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Logo + Navbar
# -------------------------
logo_path = "logonew.png"
logo_html = f'<img src="data:image/png;base64,{base64.b64encode(open(logo_path,"rb").read()).decode()}" alt="Logo">' if os.path.exists(logo_path) else ""
st.markdown(f'<div class="navbar">{logo_html}<h1>📦 Biogene India - Inventory Viewer</h1></div>', unsafe_allow_html=True)

# -------------------------
# Sidebar
# -------------------------
st.sidebar.header("⚙️ Settings")
inventory_type = st.sidebar.selectbox("Choose Inventory Type", ["Current Inventory", "Item Wise Current Inventory"])
password = st.sidebar.text_input("Enter Password to Upload/Download File", type="password")
correct_password = "426344"

UPLOAD_PATH = "Master-Stock Sheet Original.xlsx"
TIMESTAMP_PATH = "timestamp.txt"
FILENAME_PATH = "uploaded_filename.txt"

def save_timestamp(timestamp):
    with open(TIMESTAMP_PATH, "w") as f:
        f.write(timestamp)

def save_uploaded_filename(filename):
    with open(FILENAME_PATH, "w") as f:
        f.write(filename)

def load_uploaded_filename():
    if os.path.exists(FILENAME_PATH):
        with open(FILENAME_PATH, "r") as f:
            return f.read().strip()
    return "uploaded_inventory.xlsx"

# -------------------------
# Load Excel
# -------------------------
if not os.path.exists(UPLOAD_PATH):
    st.error("❌ Excel file not found locally.")
    st.stop()
else:
    xl = pd.ExcelFile(UPLOAD_PATH)

# -------------------------
# Tabs
# -------------------------
allowed_sheets = [s for s in ["Current Inventory", "Item Wise Current Inventory", "Dispatches"] if s in xl.sheet_names]
if not allowed_sheets:
    st.error("❌ No valid sheets found in file!")
else:
    sheet_name = inventory_type
    df = xl.parse(sheet_name)
    st.success(f"✅ **{sheet_name}** Loaded Successfully!")
    check_col = find_column(df, ["Check", "Location", "Status", "Type", "StockType"])

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Local", "🚚 Outstation", "📦 Other", "🔍 Search", "🤖 AI Query"])

# -------------------------
# Local/Outstation/Other tabs
# -------------------------
if check_col and sheet_name != "Dispatches":
    check_vals = df[check_col].astype(str).str.strip().str.lower()
    with tab1:
        st.subheader("🏠 Local Inventory")
        st.dataframe(df[check_vals == "local"], use_container_width=True, height=600)
    with tab2:
        st.subheader("🚚 Outstation Inventory")
        st.dataframe(df[check_vals == "outstation"], use_container_width=True, height=600)
    with tab3:
        st.subheader("📦 Other Inventory")
        st.dataframe(df[~check_vals.isin(["local", "outstation"])], use_container_width=True, height=600)
else:
    with tab1:
        st.info("Local/Outstation tabs not applicable for this sheet.")

# -------------------------
# Search Tab
# -------------------------
with tab4:
    st.subheader("🔍 Search Inventory")
    search_sheet = st.selectbox("Select sheet to search", allowed_sheets, index=0)
    search_df = xl.parse(search_sheet)
    item_col = find_column(search_df, ["Item Code", "ItemCode", "SKU", "Product Code"])
    customer_col = find_column(search_df, ["Customer Name", "CustomerName", "Customer", "CustName"])
    brand_col = find_column(search_df, ["Brand", "BrandName", "Product Brand", "Company"])
    remarks_col = find_column(search_df, ["Remarks", "Remark", "Notes", "Comments"])
    df_filtered = search_df.copy()
    search_performed = False

    col1, col2, col3 = st.columns(3)
    with col1: search_customer = st.text_input("Search by Customer Name").strip()
    with col2: search_brand = st.text_input("Search by Brand").strip()
    with col3: search_remarks = st.text_input("Search by Remarks").strip()

    if search_customer and customer_col:
        search_performed = True
        df_filtered = df_filtered[df_filtered[customer_col].astype(str).str.contains(search_customer, case=False, na=False)]
    if search_brand and brand_col:
        search_performed = True
        df_filtered = df_filtered[df_filtered[brand_col].astype(str).str.contains(search_brand, case=False, na=False)]
    if search_remarks and remarks_col:
        search_performed = True
        df_filtered = df_filtered[df_filtered[remarks_col].astype(str).str.contains(search_remarks, case=False, na=False)]

    if search_performed:
        if df_filtered.empty:
            st.warning("No matching records found.")
        else:
            st.dataframe(df_filtered, use_container_width=True, height=600)

# -------------------------
# AI Query Tab
# -------------------------
with tab5:
    st.subheader("🤖 Ask AI about your inventory")
    user_question = st.text_input("Enter your question here:")

    if user_question:
        try:
            answer = ""
            # Try OpenAI first
            if OPENAI_AVAILABLE:
                client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content":
                        f"Excel Data (first 100 rows):\n{df.head(100).to_csv(index=False)}\n\nQuestion: {user_question}\nAnswer:"}],
                    temperature=0.2,
                    max_tokens=300
                )
                answer = response.choices[0].message.content
            # Fallback to local GPT4All if OpenAI fails
            elif LOCAL_MODEL_AVAILABLE:
                model = GPT4All("ggml-gpt4all-j-v1.3-groovy.bin")
                prompt = f"Excel Data (first 100 rows):\n{df.head(100).to_csv(index=False)}\n\nQuestion: {user_question}\nAnswer:"
                answer = model.generate(prompt)
            else:
                st.error("No AI available. Either OpenAI key missing or local GPT4All not installed.")
                answer = None

            if answer:
                st.success(answer)

        except Exception as e:
            st.error(f"AI query failed: {e}. Using fallback local AI if available.")
            if LOCAL_MODEL_AVAILABLE:
                model = GPT4All("ggml-gpt4all-j-v1.3-groovy.bin")
                prompt = f"Excel Data (first 100 rows):\n{df.head(100).to_csv(index=False)}\n\nQuestion: {user_question}\nAnswer:"
                fallback_answer = model.generate(prompt)
                st.info(f"Fallback local AI answer:\n{fallback_answer}")

# -------------------------
# Footer
# -------------------------
st.markdown('<div class="footer">© 2025 Biogene India | Created By Mohit Sharma</div>', unsafe_allow_html=True)
