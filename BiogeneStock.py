import streamlit as st
import hashlib
import pandas as pd
import os
import base64
import io
from datetime import datetime

# -------------------------
# User Authentication Helpers
# -------------------------

# In-memory user storage (You can replace this with a database for production)
users_db = {
    "admin": {"password": hashlib.sha256("admin".encode()).hexdigest(), "role": "admin"}
}

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username: str, password: str) -> bool:
    if username in users_db:
        hashed_password = hash_password(password)
        return users_db[username]["password"] == hashed_password
    return False

def create_user(username: str, password: str, role: str = "user"):
    if username in users_db:
        return "User already exists"
    users_db[username] = {"password": hash_password(password), "role": role}
    return f"User {username} created successfully"

# -------------------------
# File Handling Helpers
# -------------------------

def load_data_from_file(file_path: str) -> pd.ExcelFile:
    return pd.ExcelFile(file_path)

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
# Login and Sign Up Pages
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
    st.title("Sign Up")
    st.markdown("### Create a new account")

    signup_form = st.form("Sign Up Form")
    with signup_form:
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit_button = st.form_submit_button("Sign Up")
        
    if submit_button:
        if new_password != confirm_password:
            st.error("Passwords do not match!")
        else:
            result = create_user(new_username, new_password)
            st.success(result)

# -------------------------
# Inventory Viewing and Data Management
# -------------------------

# Load Excel File (Assuming file is already uploaded)
def load_inventory_data(file_path: str):
    return pd.ExcelFile(file_path)

# -------------------------
# Main Page Flow
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
    st.write(f"Logged in as: {st.session_state.username}")
    st.write(f"Role: {st.session_state.role}")

    # Admin Panel Access
    if st.session_state.role == "admin":
        admin_panel()

    # Load Inventory Data if Logged In
    if st.session_state.role in ["admin", "user"]:
        file_path = "your_inventory_file.xlsx"  # Update with the actual path
        if os.path.exists(file_path):
            xl = load_inventory_data(file_path)

            # Show Inventory Tabs
            tab1, tab2, tab3 = st.tabs(["🏠 Local", "🚚 Outstation", "📦 Others"])

            with tab1:
                st.subheader("🏠 Local Inventory")
                # Implement filter logic for Local data
                # Display data (replace with actual filter)
                st.dataframe(xl.parse("Sheet1"))

            with tab2:
                st.subheader("🚚 Outstation Inventory")
                # Implement filter logic for Outstation data
                # Display data (replace with actual filter)
                st.dataframe(xl.parse("Sheet1"))

            with tab3:
                st.subheader("📦 Other Inventory")
                # Implement filter logic for Other data
                # Display data (replace with actual filter)
                st.dataframe(xl.parse("Sheet1"))

    st.markdown("""<div class="footer">© 2025 Biogene India | Created By Mohit Sharma</div>""", unsafe_allow_html=True)
