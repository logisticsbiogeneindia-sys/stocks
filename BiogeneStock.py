import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import pytz
import requests
import base64
import io

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

# -------------------------
# Sidebar Login
# -------------------------
st.sidebar.header("Login")

# You can store your username and password as secrets in the Streamlit secrets manager
USER_CREDENTIALS = st.secrets["USER_CREDENTIALS"]  # a dict with 'username' and 'password'

# Create a login form
login_username = st.sidebar.text_input("Username")
login_password = st.sidebar.text_input("Password", type="password")

if login_username and login_password:
    if login_username == USER_CREDENTIALS["username"] and login_password == USER_CREDENTIALS["password"]:
        st.session_state.logged_in = True
        st.sidebar.success("✅ Successfully logged in!")
    else:
        st.session_state.logged_in = False
        st.sidebar.error("❌ Incorrect username or password!")
else:
    st.session_state.logged_in = False

# -------------------------
# Display the logo and message if not logged in
# -------------------------
if not st.session_state.logged_in:
    st.markdown(f"""
    <div style="text-align:center; padding: 50px;">
        {logo_html}
        <h2>Please Log In to Access the Inventory Data</h2>
    </div>
    """, unsafe_allow_html=True)
    st.stop()  # Stops the app from executing further until the user logs in

# -------------------------
# Page Content
# -------------------------
if st.session_state.logged_in:
    # Now the rest of your original code goes here
    st.markdown(f"""
    <div class="navbar">
        {logo_html}
        <h1>📦 Biogene India - Inventory Viewer</h1>
    </div>
    """, unsafe_allow_html=True)

    # -------------------------
    # Sidebar for Inventory Settings
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
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        if password:
            st.sidebar.error("❌ Incorrect password!")

    # Continue with the rest of the original code...
