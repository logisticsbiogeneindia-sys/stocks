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
# Helper Functions
# -------------------------
def normalize(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def find_column(df: pd.DataFrame, candidates: list) -> str | None:
    norm_map = {normalize(col): col for col in df.columns}
    for cand in candidates:
        key = normalize(cand)
        if key in norm_map:
            return norm_map[key]
    return None

# -------------------------
# Authentication Logic
# -------------------------
# Create dummy database for users
users_db = {
    "admin": {
        "password": "admin123", 
        "role": "admin"
    },
    "user1": {
        "password": "user123",
        "role": "user"
    }
}

# -------------------------
# Page Configurations
# -------------------------
st.set_page_config(page_title="Biogene India - Inventory Viewer", layout="wide")

# -------------------------
# Login Functionality
# -------------------------
def login():
    st.subheader("Login")
    username = st.text_input("Username", key="username")
    password = st.text_input("Password", type="password", key="password")
    login_button = st.button("Login")

    if login_button:
        if username in users_db and users_db[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = users_db[username]["role"]
            st.success(f"Welcome {username} ({st.session_state.role})!")
            st.experimental_rerun()
        else:
            st.error("Invalid credentials. Please try again.")

def signup():
    st.subheader("Sign Up")
    username = st.text_input("Username", key="new_username")
    password = st.text_input("Password", type="password", key="new_password")
    confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
    signup_button = st.button("Sign Up")

    if signup_button:
        if password != confirm_password:
            st.error("Passwords do not match!")
        elif username in users_db:
            st.error("Username already exists!")
        else:
            # Add the user to the "database"
            users_db[username] = {"password": password, "role": "user"}
            st.success("Sign up successful. You can now log in!")

def show_login_page():
    page = st.selectbox("Choose a page", ["Login", "Sign Up"])
    if page == "Login":
        login()
    elif page == "Sign Up":
        signup()

# -------------------------
# Admin Panel
# -------------------------
def show_admin_panel():
    # Load Excel Data
    file_path = "your_inventory_file.xlsx"  # Update with the actual file path

    def load_inventory_data():
        try:
            xl = pd.ExcelFile(file_path)
            return xl
        except Exception as e:
            st.error(f"Failed to load the Excel file: {e}")
            return None

    xl = load_inventory_data()
    if xl:
        tab1, tab2, tab3 = st.tabs(["🏠 Local", "🚚 Outstation", "📦 Other"])

        with tab1:
            st.subheader("🏠 Local Inventory")
            st.dataframe(xl.parse("Local Inventory"))  # Ensure the sheet names are correct

        with tab2:
            st.subheader("🚚 Outstation Inventory")
            st.dataframe(xl.parse("Outstation Inventory"))

        with tab3:
            st.subheader("📦 Other Inventory")
            st.dataframe(xl.parse("Other Inventory"))

# -------------------------
# Logout Functionality
# -------------------------
def logout():
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.experimental_rerun()  # Redirect to login page

# -------------------------
# Main App Logic
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    st.sidebar.header(f"Welcome {st.session_state.username}")
    st.sidebar.write(f"Role: {st.session_state.role}")

    # Show Admin Panel
    if st.session_state.role == "admin":
        show_admin_panel()

    # Logout Button
    logout()

else:
    # Show login or signup page if not logged in
    show_login_page()

# -------------------------
# Footer
# -------------------------
st.markdown("""
<div class="footer">
    © 2025 Biogene India | Created By Mohit Sharma
</div>
""", unsafe_allow_html=True)
