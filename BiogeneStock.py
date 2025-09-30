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
# Load Data (other parts unchanged)
# -------------------------
def load_data_from_github():
    url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{UPLOAD_PATH.replace(' ', '%20')}"
    r = requests.get(url)
    return pd.ExcelFile(io.BytesIO(r.content))

# -------------------------
# Search Tab
# -------------------------
with tab4:
    st.subheader("🔍 Search Inventory")
    search_sheet = st.selectbox("Select sheet to search", allowed_sheets, index=0)
    search_df = xl.parse(search_sheet)

    # Columns for search
    item_col = find_column(search_df, ["Item Code", "ItemCode", "SKU", "Product Code"])
    customer_col = find_column(search_df, ["Customer Name", "CustomerName", "Customer", "CustName"])
    brand_col = find_column(search_df, ["Brand", "BrandName", "Product Brand", "Company"])
    remarks_col = find_column(search_df, ["Remarks", "Remark", "Notes", "Comments"])
    awb_col = find_column(search_df, ["AWB", "AWB Number", "Tracking Number"])
    date_col = find_column(search_df, ["Date", "Dispatch Date", "Created On", "Order Date"])
    description_col = find_column(search_df, ["Item Discription", "Item Description", "Description"])

    df_filtered = search_df.copy()
    search_performed = False

    # Display search fields based on the selected sheet
    if search_sheet == "Current Inventory":
        col1, col2, col3 = st.columns(3)
        with col1:
            search_customer = st.text_input("Search by Customer Name", value="")
        with col2:
            search_brand = st.text_input("Search by Brand", value="")
        with col3:
            search_remarks = st.text_input("Search by Remarks", value="")

        if customer_col:
            customer_suggestions = search_df[customer_col].dropna().unique()
            search_customer = st.selectbox("Select Customer Name", customer_suggestions, index=0)

        if brand_col:
            brand_suggestions = search_df[brand_col].dropna().unique()
            search_brand = st.selectbox("Select Brand", brand_suggestions, index=0)

        if remarks_col:
            remarks_suggestions = search_df[remarks_col].dropna().unique()
            search_remarks = st.selectbox("Select Remarks", remarks_suggestions, index=0)

        if search_customer and customer_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[customer_col].astype(str).str.contains(search_customer, case=False, na=False)]
        if search_brand and brand_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[brand_col].astype(str).str.contains(search_brand, case=False, na=False)]
        if search_remarks and remarks_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[remarks_col].astype(str).str.contains(search_remarks, case=False, na=False)]

    elif search_sheet == "Item Wise Current Inventory":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            search_item = st.text_input("Search by Item Code", value="")
        with col2:
            search_description = st.text_input("Search by Item Description", value="")
        with col3:
            search_customer = st.text_input("Search by Customer Name", value="")
        with col4:
            search_brand = st.text_input("Search by Brand", value="")

        # Autocomplete/Suggestions for "Item Code"
        if item_col:
            item_suggestions = search_df[item_col].dropna().unique()
            search_item = st.selectbox("Select Item Code", item_suggestions.tolist(), index=0)

        # Autocomplete/Suggestions for "Item Description"
        if description_col:
            description_suggestions = search_df[description_col].dropna().unique()
            search_description = st.selectbox("Select Item Description", description_suggestions.tolist(), index=0)

        # Autocomplete/Suggestions for "Customer Name"
        if customer_col:
            customer_suggestions = search_df[customer_col].dropna().unique()
            search_customer = st.selectbox("Select Customer Name", customer_suggestions.tolist(), index=0)

        # Autocomplete/Suggestions for "Brand"
        if brand_col:
            brand_suggestions = search_df[brand_col].dropna().unique()
            search_brand = st.selectbox("Select Brand", brand_suggestions.tolist(), index=0)

        if remarks_col:
            remarks_suggestions = search_df[remarks_col].dropna().unique()
            search_remarks = st.selectbox("Select Remarks", remarks_suggestions.tolist(), index=0)

        if search_item and item_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[item_col].astype(str).str.contains(search_item, case=False, na=False)]
        if search_description and description_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[description_col].astype(str).str.contains(search_description, case=False, na=False)]
        if search_customer and customer_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[customer_col].astype(str).str.contains(search_customer, case=False, na=False)]
        if search_brand and brand_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[brand_col].astype(str).str.contains(search_brand, case=False, na=False)]
        if search_remarks and remarks_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[remarks_col].astype(str).str.contains(search_remarks, case=False, na=False)]

    elif search_sheet == "Dispatches":
        col1, col2, col3 = st.columns(3)
        with col1:
            date_range = st.date_input("Select Date Range", [])
        with col2:
            search_awb = st.text_input("Search by AWB Number", value="")
        with col3:
            search_customer = st.text_input("Search by Customer Name", value="")

        if date_range and len(date_range) == 2 and date_col:
            start, end = date_range
            search_performed = True
            df_filtered[date_col] = pd.to_datetime(df_filtered[date_col], errors="coerce")
            df_filtered = df_filtered[(df_filtered[date_col] >= pd.to_datetime(start)) & (df_filtered[date_col] <= pd.to_datetime(end))]
        if search_awb and awb_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[awb_col].astype(str).str.contains(search_awb, case=False, na=False)]
        if search_customer and customer_col:
            search_performed = True
            df_filtered = df_filtered[df_filtered[customer_col].astype(str).str.contains(search_customer, case=False, na=False)]

    if search_performed:
        if df_filtered.empty:
            st.warning("No matching records found.")
        else:
            st.dataframe(df_filtered, use_container_width=True, height=600)


# ------------------------- # Footer # ------------------------- st.markdown(""" <div class="footer"> © 2025 Biogene India | Created By Mohit Sharma </div> """, unsafe_allow_html=True)