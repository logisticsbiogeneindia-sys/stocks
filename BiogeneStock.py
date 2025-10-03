import streamlit as st
import pandas as pd
import os
import re
import base64
import io
import requests
from datetime import datetime
import pytz

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
# Streamlit Configuration
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
# Load secrets and password
# -------------------------
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    PASSWORD = st.secrets["PASSWORD"]
except KeyError:
    st.error("Required secrets are missing. Please check your Streamlit secrets configuration.")
    st.stop()

# -------------------------
# Admin Login Logic (User Authentication)
# -------------------------
def login_user():
    # Simple login form
    st.sidebar.header("🔑 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    
    # Define users and their roles
    users = {
        "admin": {"password": "adminpassword", "role": "Admin"},
        "editor": {"password": "editorpassword", "role": "Editor"},
        "user1": {"password": "user1password", "role": "User"},
        "user2": {"password": "user2password", "role": "User"},
        "user3": {"password": "user3password", "role": "User"},
        "user4": {"password": "user4password", "role": "User"},
        "user5": {"password": "user5password", "role": "User"}
    }

    if username in users and password == users[username]["password"]:
        st.session_state.username = username
        st.session_state.role = users[username]["role"]
        st.success(f"Welcome, {username} ({st.session_state.role})!")
        return True
    elif username:
        st.sidebar.error("Invalid username or password.")
        return False
    return False

# Only allow users with valid login to access the app
if not login_user():
    st.stop()

# -------------------------
# File Management and GitHub Integration
# -------------------------
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

def push_to_github(local_file, remote_path, commit_message="Update file"):
    try:
        with open(local_file, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
        url = f"https://api.github.com/repos/logisticsbiogeneindia-sys/BiogeneIndia/contents/{remote_path}"
        r = requests.get(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}"})
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {"message": commit_message, "content": content, "branch": "main"}
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}"}, json=payload)
        if r.status_code in [200, 201]:
            st.sidebar.success(f"✅ {os.path.basename(local_file)} pushed to GitHub successfully!")
        else:
            st.sidebar.error(f"❌ GitHub push failed for {local_file}: {r.json()}")
    except Exception as e:
        st.sidebar.error(f"Error pushing file {local_file}: {e}")

# -------------------------
# Upload Section (Admin and Editor Access)
# -------------------------
if st.session_state.role in ["Admin", "Editor"]:
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

# -------------------------
# Admin/Editor Role Based Access
# -------------------------
if st.session_state.role == "Admin":
    st.subheader("Admin Dashboard")
    st.write("You can view and modify all data.")
elif st.session_state.role == "Editor":
    st.subheader("Editor Dashboard")
    st.write("You can view and edit certain columns.")

# -------------------------
# Load Excel Data
# -------------------------
@st.cache_data
def load_data_from_github():
    url = f"https://raw.githubusercontent.com/logisticsbiogeneindia-sys/BiogeneIndia/main/{UPLOAD_PATH.replace(' ', '%20')}"
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
# Allowed Sheets
# -------------------------
allowed_sheets = [s for s in xl.sheet_names if s in ["Current Inventory", "Item Wise Current Inventory", "Dispatches"]]
if not allowed_sheets:
    st.error("❌ No valid sheets found in file!")
else:
    sheet_name = st.selectbox("Select Sheet", allowed_sheets)
    df = xl.parse(sheet_name)
    st.dataframe(df)

    # Display data based on user roles
    if st.session_state.role == "Admin":
        st.write("You can modify all data.")
    elif st.session_state.role == "Editor":
        st.write("You can modify certain columns.")

# -------------------------
# Footer
# -------------------------
st.markdown("""<div class="footer">© 2025 Biogene India | Created By Mohit Sharma</div>""", unsafe_allow_html=True)
