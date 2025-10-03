import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import pytz
import requests
import base64
import io
import bcrypt
import sqlite3

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
# Database for Users (SQLite)
# -------------------------
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

# Create users table if not exists
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
""")

def create_user(username, password, role="user"):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed_password, role))
    conn.commit()

def verify_user(username, password):
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
        return user
    return None

def get_user_role(username):
    cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    return user[0] if user else None

# -------------------------
# Sidebar - User Login or Admin Panel
# -------------------------
st.sidebar.header("⚙️ Settings")
role = None
username = st.sidebar.text_input("Username", "")
password = st.sidebar.text_input("Password", type="password")

def user_login():
    global role
    if username and password:
        user = verify_user(username, password)
        if user:
            role = get_user_role(username)
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = role
            st.sidebar.success(f"Welcome {username} ({role})!")
        else:
            st.sidebar.error("Invalid username or password")

def admin_panel():
    st.title("Admin Panel")
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

    if uploaded_file is not None:
        with st.spinner("Uploading file..."):
            with open("Master-Stock Sheet Original.xlsx", "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.sidebar.success(f"File uploaded successfully!")
    
    # Admin can edit any point of data and approve visibility
    df = pd.read_excel("Master-Stock Sheet Original.xlsx")
    st.write("Admin can view and edit data here")

def user_dashboard():
    st.title("User Dashboard")
    df = pd.read_excel("Master-Stock Sheet Original.xlsx")
    st.write("Data is available based on your permissions.")
    # Add filtering, search, etc.

# -------------------------
# Login and Roles
# -------------------------
if "logged_in" in st.session_state and st.session_state.logged_in:
    if st.session_state.role == "admin":
        admin_panel()
    else:
        user_dashboard()
else:
    action = st.sidebar.radio("Choose Action", ["Login", "Sign Up"])
    
    if action == "Login":
        user_login()
    elif action == "Sign Up":
        new_username = st.sidebar.text_input("New Username", "")
        new_password = st.sidebar.text_input("New Password", type="password")
        confirm_password = st.sidebar.text_input("Confirm Password", type="password")
        
        if st.sidebar.button("Create Account"):
            if new_password == confirm_password:
                create_user(new_username, new_password)
                st.sidebar.success(f"User {new_username} created successfully!")
            else:
                st.sidebar.error("Passwords do not match.")
                
# -------------------------
# Data Tabs (Local, Outstation, Others)
# -------------------------
if "logged_in" in st.session_state and st.session_state.logged_in:
    xl = pd.ExcelFile("Master-Stock Sheet Original.xlsx")
    allowed_sheets = xl.sheet_names
    sheet_name = st.selectbox("Select Inventory Sheet", allowed_sheets)
    df = xl.parse(sheet_name)
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Local", "🚚 Outstation", "📦 Other", "🔍 Search"])
    
    check_col = find_column(df, ["Check", "Location", "Status", "Type", "StockType"])

    if check_col:
        check_vals = df[check_col].astype(str).str.strip().str.lower()
        
        with tab1:
            st.subheader("🏠 Local Inventory")
            st.dataframe(df[check_vals == "local"], use_container_width=True)
        
        with tab2:
            st.subheader("🚚 Outstation Inventory")
            st.dataframe(df[check_vals == "outstation"], use_container_width=True)
        
        with tab3:
            st.subheader("📦 Other Inventory")
            st.dataframe(df[~check_vals.isin(["local", "outstation"])], use_container_width=True)
    
    # Search Tab
    with tab4:
        st.subheader("🔍 Search Inventory")
        search_df = df.copy()
        search_term = st.text_input("Search term")
        if search_term:
            search_result = search_df[search_df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]
            if not search_result.empty:
                st.dataframe(search_result)
            else:
                st.warning("No matching results found.")
    
# -------------------------
# Footer
# -------------------------
st.markdown("""
<div class="footer">
    © 2025 Biogene India | Created By Mohit Sharma
</div>
""", unsafe_allow_html=True)
