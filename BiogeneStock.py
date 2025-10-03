import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import pytz
import requests
import base64
import io
import hashlib

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
# Load the user database (Excel file)
users_df = pd.read_excel("users.xlsx")

# Helper function to hash the password
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Authenticate user credentials
def authenticate(username: str, password: str):
    user = users_df[users_df['Username'] == username]
    if not user.empty:
        stored_password = user.iloc[0]['Password']
        if stored_password == hash_password(password):
            return user.iloc[0]['Role']
    return None

# Admin control to add users (SignUp)
def signup_form():
    st.sidebar.header("Admin User Management")
    new_user_name = st.sidebar.text_input("New Username")
    new_user_password = st.sidebar.text_input("New Password", type="password")
    new_user_role = st.sidebar.selectbox("New User Role", ["User", "Editor", "Admin"])

    if st.sidebar.button("Create User"):
        # Check if the username already exists
        if new_user_name in users_df['Username'].values:
            st.sidebar.error("Username already exists!")
        else:
            # Add new user to Excel file
            new_user_data = pd.DataFrame({
                "Username": [new_user_name],
                "Password": [hash_password(new_user_password)],
                "Role": [new_user_role]
            })
            users_df = pd.concat([users_df, new_user_data], ignore_index=True)
            users_df.to_excel("users.xlsx", index=False)
            st.sidebar.success(f"New user {new_user_name} created with role {new_user_role}")

# Login Form
def login_form():
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        role = authenticate(username, password)
        if role:
            st.session_state.role = role
            st.session_state.username = username
            st.sidebar.success(f"Welcome {username} ({role})")
        else:
            st.sidebar.error("Invalid username or password")

# Check if user is logged in, if not show the login form
if "role" not in st.session_state:
    login_form()

# Admin access to sign up new users
if st.session_state.get("role") == "Admin":
    signup_form()

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
inventory_type = st.sidebar.selectbox("Choose Inventory Type", ["Current Inventory", "Item Wise Current Inventory"])
password = st.sidebar.text_input("Enter Password to Upload/Download File", type="password")
correct_password = st.secrets["PASSWORD"]  # Storing password in Streamlit secrets

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
REPO = "BiogeneIndia"
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

# -------------------------
# GitHub Push Function
# -------------------------
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

# -------------------------
# GitHub Timestamp
# -------------------------
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
                mime="application/vnd.ms-excel"
            )

# -------------------------
# Sheet Parsing and Display
# -------------------------
if os.path.exists(UPLOAD_PATH):
    xl = pd.ExcelFile(UPLOAD_PATH)
    sheet_names = xl.sheet_names
    sheet_name = st.selectbox("Select Sheet", sheet_names)

    df = xl.parse(sheet_name)
    st.dataframe(df)
    
    # Role-based access control logic
    if "role" in st.session_state:
        if st.session_state.role == "Admin":
            st.write("You are an Admin. You can modify all data.")
        elif st.session_state.role == "Editor":
            st.write("You are an Editor. You can edit certain data.")
        elif st.session_state.role == "User":
            st.write("You are a User. You can view data only.")

# Footer
st.markdown("""<div class="footer">© 2025 Biogene India | Created By Mohit Sharma</div>""", unsafe_allow_html=True)
