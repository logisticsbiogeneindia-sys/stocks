import streamlit as st
import pandas as pd
import os
import re
import hashlib
from datetime import datetime
import pytz
import requests
import base64
import io

# -------------------------
# User Authentication Helpers
# -------------------------

# In-memory user storage (You can replace this with a database for production)
users_db = {
    "admin": {"password": "admin", "role": "admin"}
}

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    if username in users_db:
        return users_db[username]["password"] == hash_password(password)
    return False

def create_user(username: str, password: str, role: str = "user"):
    if username in users_db:
        return "User already exists"
    users_db[username] = {"password": hash_password(password), "role": role}
    return f"User {username} created successfully"

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
# User Authentication (Login & Signup)
# -------------------------

def show_login_page():
    st.title("Login to Biogene India - Inventory Viewer")
    st.markdown("### Please enter your credentials to log in")

    login_form = st.form("Login Form")
    with login_form:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
    if submit_button:
        if check_credentials(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = users_db[username]["role"]
            st.success(f"Welcome {username}!")
        else:
            st.error("Invalid credentials. Please try again.")

def show_signup_page():
    st.title("Sign Up for Biogene India - Inventory Viewer")
    st.markdown("### Create an account")

    signup_form = st.form("Signup Form")
    with signup_form:
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit_button = st.form_submit_button("Sign Up")
        
    if submit_button:
        if new_password != confirm_password:
            st.error("Passwords do not match.")
        elif new_username in users_db:
            st.error(f"Username {new_username} already exists.")
        else:
            result = create_user(new_username, new_password)
            st.success(result)

# -------------------------
# Admin Panel
# -------------------------
def admin_panel():
    if st.session_state.get("role") == "admin":
        st.title("Admin Panel")
        st.markdown("### Create a new user")

        admin_form = st.form("Admin Form")
        with admin_form:
            new_user = st.text_input("New Username")
            new_user_password = st.text_input("New Password", type="password")
            user_role = st.selectbox("Role", ["user", "admin"])
            submit_button = st.form_submit_button("Create User")

        if submit_button:
            result = create_user(new_user, new_user_password, user_role)
            st.success(result)
    else:
        st.error("You must be logged in as admin to access this page.")

# -------------------------
# Inventory Data Load and Display
# -------------------------

UPLOAD_PATH = "Master-Stock Sheet Original.xlsx"
TIMESTAMP_PATH = "timestamp.txt"
FILENAME_PATH = "uploaded_filename.txt"

def load_data_from_github():
    url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{UPLOAD_PATH.replace(' ', '%20')}"
    r = requests.get(url)
    return pd.ExcelFile(io.BytesIO(r.content))

@st.cache_data
def load_data():
    try:
        xl = pd.ExcelFile(UPLOAD_PATH)
    except Exception as e:
        st.error(f"Error loading Excel file: {e}")
        return None
    return xl

def show_inventory_tabs(xl):
    allowed_sheets = [s for s in ["Current Inventory", "Item Wise Current Inventory", "Dispatches"] if s in xl.sheet_names]
    if not allowed_sheets:
        st.error("No valid sheets found in file!")
    else:
        sheet_name = st.sidebar.selectbox("Choose Inventory Type", allowed_sheets)
        df = xl.parse(sheet_name)
        st.success(f"**{sheet_name}** Loaded Successfully!")

        tab1, tab2, tab3, tab4 = st.tabs(["🏠 Local", "🚚 Outstation", "📦 Other", "🔍 Search"])

        # Display Data based on "Check" column
        check_col = find_column(df, ["Check", "Location", "Status", "Type", "StockType"])
        if check_col:
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
                st.subheader("📄 No Inventory Data")
                st.warning("There is no 'Check' column found in the data.")
            with tab2:
                st.subheader("📄 No Dispatch Data")
                st.warning("Please check your inventory for errors or missing columns.")

        # Search Tab
        with tab4:
            st.subheader("🔍 Search Inventory")
            search_df = xl.parse(sheet_name)
            search_performed = False
            search_column = st.text_input("Enter Column Name to Search", "").strip()
            if search_column:
                search_performed = True
                search_results = search_df[search_df.apply(lambda row: row.astype(str).str.contains(search_column, case=False, na=False).any(), axis=1)]
                if search_results.empty:
                    st.warning("No matching records found.")
                else:
                    st.dataframe(search_results)
    
# -------------------------
# Main App Flow
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    page = st.selectbox("Choose a page", ["Login", "Sign Up"])
    if page == "Login":
        show_login_page()
    elif page == "Sign Up":
        show_signup_page()
else:
    st.sidebar.header(f"Welcome {st.session_state.username}")
    
    if st.session_state.role == "admin":
        admin_panel()

    # Upload and view inventory if logged in
    uploaded_file = st.sidebar.file_uploader("Upload Excel File", type=["xlsx", "xls"])

    if uploaded_file:
        with open(UPLOAD_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("File uploaded successfully!")
    
    xl = load_data()
    if xl:
        show_inventory_tabs(xl)

# -------------------------
# Footer
# -------------------------
st.markdown("""
<div class="footer">
    © 2025 Biogene India | Created By Mohit Sharma
</div>
""", unsafe_allow_html=True)
