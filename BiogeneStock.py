import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import pytz
import requests
import base64
import io
from openpyxl import load_workbook

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
# Logo + Title Navbar
# -------------------------
logo_path = "logonew.png"
if os.path.exists(logo_path):
    logo_html = f'<img src="data:image/png;base64,{base64.b64encode(open(logo_path,"rb").read()).decode()}" alt="Logo">'
else:
    logo_html = ""

st.markdown(f"""
<div class="navbar">
    {logo_html}
    <h1>📦 Biogene India - Inventory Viewer</h1>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Sidebar
# -------------------------
st.sidebar.header("⚙️ Settings")
view_option = st.sidebar.radio("Choose View", ["Inventory Viewer", "Full Control"])
inventory_type = st.sidebar.selectbox("Choose Inventory Type", ["Current Inventory", "Item Wise Current Inventory"])
password = st.sidebar.text_input("Enter Password", type="password")
correct_password = st.secrets["PASSWORD"]

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
# GitHub Config
# -------------------------
OWNER = "logisticsbiogeneindia-sys"
REPO = "stocks"
BRANCH = "main"
TOKEN = st.secrets["GITHUB_TOKEN"]
headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}

def check_github_auth():
    r = requests.get("https://api.github.com/user", headers=headers)
    if r.status_code == 200:
        st.sidebar.success(f"🔑 GitHub Auth OK: {r.json().get('login')}")
    else:
        st.sidebar.error(f"❌ GitHub Auth failed: {r.status_code}")

check_github_auth()

def push_to_github(local_file, remote_path, commit_message="Update file"):
    try:
        with open(local_file, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{remote_path}"
        r = requests.get(url, headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {"message": commit_message, "content": content, "branch": BRANCH}
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        if r.status_code in [200, 201]:
            st.sidebar.success(f"✅ {os.path.basename(local_file)} pushed to GitHub successfully!")
        else:
            st.sidebar.error(f"❌ GitHub push failed for {local_file}: {r.json()}")
    except Exception as e:
        st.sidebar.error(f"Error pushing file {local_file}: {e}")

def get_github_file_timestamp():
    try:
        url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/timestamp.txt"
        r = requests.get(url)
        if r.status_code == 200:
            return r.text.strip()
        else:
            return "No GitHub timestamp found."
    except Exception as e:
        return f"Error fetching timestamp: {e}"

github_timestamp = get_github_file_timestamp()
st.markdown(f"🕒 **Last Updated (from GitHub):** {github_timestamp}")

# -------------------------
# Upload & Download Section
# -------------------------
if password == correct_password:
    uploaded_file = st.sidebar.file_uploader("Upload Excel File", type=["xlsx", "xls"])
    if uploaded_file is not None:
        with st.spinner("Uploading file..."):
            with open(UPLOAD_PATH, "wb") as f:
                f.write(uploaded_file.getbuffer())
            timezone = pytz.timezone("Asia/Kolkata")
            upload_time = datetime.now(timezone).strftime("%d-%m-%Y %H:%M:%S")
            save_timestamp(upload_time)
            save_uploaded_filename(uploaded_file.name)
            st.sidebar.success(f"✅ File uploaded at {upload_time}")
            push_to_github(UPLOAD_PATH, "Master-Stock Sheet Original.xlsx", commit_message=f"Uploaded {uploaded_file.name}")
            push_to_github(TIMESTAMP_PATH, "timestamp.txt", commit_message="Updated timestamp")
    if os.path.exists(UPLOAD_PATH):
        with open(UPLOAD_PATH, "rb") as f:
            st.sidebar.download_button(
                label="⬇️ Download Uploaded Excel File",
                data=f,
                file_name=load_uploaded_filename(),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    if password:
        st.sidebar.error("❌ Incorrect password!")

# -------------------------
# Load Excel
# -------------------------
@st.cache_data
def load_data_from_github():
    url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{UPLOAD_PATH.replace(' ', '%20')}"
    r = requests.get(url)
    return pd.ExcelFile(io.BytesIO(r.content))

if not os.path.exists(UPLOAD_PATH):
    try:
        xl = load_data_from_github()
    except Exception as e:
        st.error(f"❌ Error loading Excel from GitHub: {e}")
        st.stop()
else:
    xl = pd.ExcelFile(UPLOAD_PATH)

# -------------------------
# Helper to save sheet safely
# -------------------------
def save_excel_with_sheet(df, path, sheet_name):
    if os.path.exists(path):
        book = load_workbook(path)
        if sheet_name in book.sheetnames:
            std = book[sheet_name]
            book.remove(std)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            writer.book = book
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        df.to_excel(path, sheet_name=sheet_name, index=False)

# -------------------------
# Inventory Viewer
# -------------------------
def show_inventory_viewer():
    allowed_sheets = [s for s in ["Current Inventory", "Item Wise Current Inventory", "Dispatches"] if s in xl.sheet_names]
    if not allowed_sheets:
        st.error("❌ No valid sheets found in file!")
        return
    sheet_name = inventory_type
    df = xl.parse(sheet_name)
    st.success(f"✅ **{sheet_name}** Loaded Successfully!")
    check_col = find_column(df, ["Check", "Location", "Status", "Type", "StockType"])

    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Local", "🚚 Outstation", "📦 Other", "🔍 Search"])
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
        for tab, msg in zip([tab1, tab2], ["No Inventory Data", "No Dispatch Data"]):
            with tab:
                st.subheader("📄 " + msg)
                st.warning("There is no 'Check' column found in the data.")

    # Search Tab
    with tab4:
        st.subheader("🔍 Search Inventory")
        search_sheet = st.selectbox("Select sheet to search", allowed_sheets, index=0)
        search_df = xl.parse(search_sheet)
        item_col = find_column(search_df, ["Item Code", "ItemCode", "SKU", "Product Code"])
        customer_col = find_column(search_df, ["Customer Name", "CustomerName", "Customer", "CustName"])
        brand_col = find_column(search_df, ["Brand", "BrandName", "Product Brand", "Company"])
        remarks_col = find_column(search_df, ["Remarks", "Remark", "Notes", "Comments"])
        awb_col = find_column(search_df, ["AWB", "AWB Number", "Tracking Number"])
        date_col = find_column(search_df, ["Date", "Dispatch Date", "Created On", "Order Date"])

        df_filtered = search_df.copy()
        search_performed = False

        # [Search logic here, same as before...]

        st.dataframe(df_filtered, use_container_width=True, height=600)

# -------------------------
# Full Control Mode
# -------------------------
if view_option == "Full Control":
    if password != correct_password:
        st.warning("🔒 Full Control requires a valid password!")
        st.stop()

    sheet_to_edit = st.selectbox("Select sheet to edit", xl.sheet_names)
    df_edit = xl.parse(sheet_to_edit)
    st.subheader(f"✏️ Editing Sheet: {sheet_to_edit}")

    edited_df = st.data_editor(df_edit, num_rows="dynamic", use_container_width=True, height=600)

    if st.sidebar.button(f"💾 Save Changes to {sheet_to_edit}"):
        with st.spinner("Saving changes..."):
            save_excel_with_sheet(edited_df, UPLOAD_PATH, sheet_to_edit)
            timezone = pytz.timezone("Asia/Kolkata")
            upload_time = datetime.now(timezone).strftime("%d-%m-%Y %H:%M:%S")
            save_timestamp(upload_time)
            push_to_github(UPLOAD_PATH, "Master-Stock Sheet Original.xlsx", commit_message=f"Edited {sheet_to_edit}")
            push_to_github(TIMESTAMP_PATH, "timestamp.txt", commit_message="Updated timestamp")
            xl = pd.ExcelFile(UPLOAD_PATH)
            st.success("✅ Changes saved, pushed to GitHub, and Inventory Viewer updated!")

# -------------------------
# Footer
# -------------------------
st.markdown("""
<div class="footer">
    © 2025 Biogene India | Created By Mohit Sharma
</div>
""", unsafe_allow_html=True)

# Show Inventory Viewer if that view is selected
if view_option == "Inventory Viewer":
    show_inventory_viewer()
