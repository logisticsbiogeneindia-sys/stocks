"""
/app/streamlit_reports.py

Streamlit app to upload the user's Excel (with columns provided),
clean & compute derived fields, and show interactive reports + CSV exports.

Run:
    pip install -r requirements.txt
    streamlit run /app/streamlit_reports.py

requirements.txt minimal:
streamlit
pandas
plotly
openpyxl
"""

from io import BytesIO
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from datetime import timedelta

st.set_page_config(layout="wide", page_title="Excel Reports Dashboard")

# ---------- Helpers ----------
def clean_column_name(c: str) -> str:
    return (
        str(c)
        .strip()
        .lower()
        .replace("\n", " ")
        .replace("\t", " ")
        .replace(".", "")
        .replace("/", " ")
        .replace("  ", " ")
        .replace(" ", "_")
    )

def load_excel(file_bytes):
    try:
        df = pd.read_excel(file_bytes, sheet_name=0, engine="openpyxl")
    except Exception:
        # fallback: try pandas default
        df = pd.read_excel(file_bytes, sheet_name=0)
    # normalize column names
    df.columns = [clean_column_name(c) for c in df.columns]
    return df

def parse_dates(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def ensure_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def compute_derived(df):
    # Choose monetary amount column
    if "taxable_value" in df.columns:
        df["amount"] = df["taxable_value"]
    elif "purchase_value" in df.columns:
        df["amount"] = df["purchase_value"]
    else:
        # try alternative names from user columns list
        for alt in ["purchase_value", "taxable value", "purchase value"]:
            if alt in df.columns:
                df["amount"] = df[alt]
                break
    # Closing balance to numeric
    if "closing_balance" in df.columns:
        df["closing_balance"] = pd.to_numeric(df["closing_balance"], errors="coerce")
    # delivery_time_days: delivery_date - dispatch_date (fallbacks)
    if "delivery_date" in df.columns and "dispatch_date" in df.columns:
        df["delivery_time_days"] = (df["delivery_date"] - df["dispatch_date"]).dt.days
    else:
        # try other date combos
        if "delivery_date" in df.columns and "goods_recd_date" in df.columns:
            df["delivery_time_days"] = (df["delivery_date"] - df["goods_recd_date"]).dt.days
        else:
            df["delivery_time_days"] = np.nan
    # day names
    for col in ["dispatch_date", "delivery_date", "invoice_date"]:
        if col in df.columns:
            df[f"{col}_day"] = df[col].dt.day_name()
    # safe numeric for amount
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    return df

def filter_df(df, start_date, end_date, customer, brand, item_code):
    ddf = df.copy()
    if "invoice_date" in ddf.columns and start_date:
        ddf = ddf[(ddf["invoice_date"] >= pd.Timestamp(start_date)) & (ddf["invoice_date"] <= pd.Timestamp(end_date))]
    if customer and "customer_name" in ddf.columns:
        ddf = ddf[ddf["customer_name"].isin(customer)]
    if brand and "brand" in ddf.columns:
        ddf = ddf[ddf["brand"].isin(brand)]
    if item_code and "item_code" in ddf.columns:
        ddf = ddf[ddf["item_code"].isin(item_code)]
    return ddf

def df_to_csv_bytes(df):
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b.read()

# ---------- UI ----------
st.title("📊 Excel → Streamlit Reports")
st.caption("Upload your Excel file (columns you listed are supported). App will auto-detect and produce reports.")

upload = st.file_uploader("Upload Excel file (.xlsx/.xls)", type=["xlsx", "xls"], accept_multiple_files=False)

if upload is None:
    st.info("Please upload your Excel file to generate reports. (Use the columns you shared).")
    st.stop()

# Load
with st.spinner("Loading and parsing Excel..."):
    df_raw = load_excel(upload)

# Quick preview & allow column mapping if necessary
st.subheader("Data preview")
st.write("First 5 rows (column names normalized).")
st.dataframe(df_raw.head())

# Parse expected date columns
expected_dates = ["invoice_date", "goods_recd_date", "dispatch_date", "delivery_date"]
# There may be columns containing dots or slightly different names; try to map common variants:
aliases = {
    "invoice_date": ["invoice_date", "invoice date"],
    "goods_recd_date": ["goods_recd_date", "goods recd date", "goods_recd._date"],
    "dispatch_date": ["dispatch_date", "dispatch date"],
    "delivery_date": ["delivery_date", "delivery date"],
    "taxable_value": ["taxable_value", "taxable value"],
    "purchase_value": ["purchase_value", "purchase value", "purchase_value_dollar/inr"],
    "customer_name": ["customer_name", "customer name"],
    "brand": ["brand"],
    "item_code": ["item_code", "item code"],
    "closing_balance": ["closing_balance", "closing balance"],
}

# Try to create canonical columns by detecting known aliases in existing columns
col_map = {}
for canonical, poss in aliases.items():
    for p in poss:
        if p in df_raw.columns:
            col_map[canonical] = p
            break

# Create standardized columns by copying if found
df = df_raw.copy()
for canon, actual in col_map.items():
    if actual in df.columns:
        df[canon] = df[actual]

# Parse dates & numeric
df = parse_dates(df, expected_dates + ["invoice_date"])
df = ensure_numeric(df, ["unit_price_dollar_inr", "unit_price_inr", "purchase_value", "taxable_value", "closing_balance", "amount"])
df = compute_derived(df)

# Sidebar filters
st.sidebar.header("Filters")
min_date = df["invoice_date"].min() if "invoice_date" in df.columns else None
max_date = df["invoice_date"].max() if "invoice_date" in df.columns else None

start_date = st.sidebar.date_input("Start date", value=min_date.date() if pd.notnull(min_date) else None)
end_date = st.sidebar.date_input("End date", value=max_date.date() if pd.notnull(max_date) else None)

# Customer/brand/item selectors (multi-select)
customers = sorted(df["customer_name"].dropna().unique().tolist()) if "customer_name" in df.columns else []
brands = sorted(df["brand"].dropna().unique().tolist()) if "brand" in df.columns else []
items = sorted(df["item_code"].dropna().unique().tolist()) if "item_code" in df.columns else []

sel_customers = st.sidebar.multiselect("Customer(s)", options=customers)
sel_brands = st.sidebar.multiselect("Brand(s)", options=brands)
sel_items = st.sidebar.multiselect("Item code(s)", options=items)

filtered = filter_df(df, start_date, end_date, sel_customers, sel_brands, sel_items)

st.markdown("---")
# KPIs
st.subheader("Key Metrics")
k1, k2, k3, k4 = st.columns(4)
total_invoices = int(filtered.shape[0])
total_amount = filtered["amount"].sum() if "amount" in filtered.columns else 0
avg_delivery = filtered["delivery_time_days"].mean() if "delivery_time_days" in filtered.columns else np.nan
total_closing = filtered["closing_balance"].sum() if "closing_balance" in filtered.columns else 0
k1.metric("Invoices", f"{total_invoices:,}")
k2.metric("Total Amount", f"{total_amount:,.2f}")
k3.metric("Avg Delivery Days", f"{avg_delivery:.1f}" if not np.isnan(avg_delivery) else "N/A")
k4.metric("Total Closing Balance", f"{total_closing:,.2f}")

st.markdown("---")

# Layout: charts left, tables right
col_left, col_right = st.columns((2, 1))

# Time series
with col_left:
    st.subheader("Amount over Time")
    if "invoice_date" in filtered.columns and "amount" in filtered.columns:
        ts = filtered.groupby(pd.Grouper(key="invoice_date", freq="W"))["amount"].sum().reset_index()
        fig = px.line(ts, x="invoice_date", y="amount", title="Weekly Amount")
        st.plotly_chart(fig, use_container_width=True)
        st.download_button("Download time series CSV", data=df_to_csv_bytes(ts), file_name="time_series.csv")
    else:
        st.info("Need 'invoice_date' and 'amount' to show time series.")

    st.subheader("Top Customers")
    if "customer_name" in filtered.columns and "amount" in filtered.columns:
        cust = filtered.groupby("customer_name")["amount"].sum().reset_index().sort_values("amount", ascending=False).head(20)
        fig2 = px.bar(cust, x="amount", y="customer_name", orientation="h", title="Top Customers by Amount")
        st.plotly_chart(fig2, use_container_width=True)
        st.download_button("Download top customers CSV", data=df_to_csv_bytes(cust), file_name="top_customers.csv")
    else:
        st.info("No customer/amount columns found.")

    st.subheader("Delivery Time Distribution")
    if "delivery_time_days" in filtered.columns:
        ddf = filtered.dropna(subset=["delivery_time_days"])
        if not ddf.empty:
            fig3 = px.histogram(ddf, x="delivery_time_days", nbins=30, title="Delivery Time (days)")
            st.plotly_chart(fig3, use_container_width=True)
            st.download_button("Download delivery times CSV", data=df_to_csv_bytes(ddf[["dispatch_date","delivery_date","delivery_time_days","invoice_number"]].dropna()), file_name="delivery_times.csv")
        else:
            st.info("No delivery_time_days data after filtering.")
    else:
        st.info("delivery_time_days not available.")

with col_right:
    st.subheader("Top Items / Inventory")
    if "item_code" in filtered.columns:
        items_df = filtered.groupby("item_code").agg(
            description=("discription" if "discription" in filtered.columns else filtered.columns[0], "first"),
            total_qty_in=("in_qty" if "in_qty" in filtered.columns else "in_qty", "sum") if "in_qty" in filtered.columns else ("in_qty","count"),
            total_qty_out=("out_qty" if "out_qty" in filtered.columns else "out_qty", "sum") if "out_qty" in filtered.columns else ("out_qty","count"),
            closing_balance=("closing_balance", "sum") if "closing_balance" in filtered.columns else (filtered.columns[0], "count"),
            total_amount=("amount", "sum") if "amount" in filtered.columns else (filtered.columns[0], "count"),
        ).reset_index().sort_values("total_amount", ascending=False).head(50)
        st.dataframe(items_df)
        st.download_button("Download items CSV", data=df_to_csv_bytes(items_df), file_name="top_items.csv")
    else:
        st.info("item_code column not found.")

    st.markdown("### Brand Distribution")
    if "brand" in filtered.columns and "amount" in filtered.columns:
        brand_df = filtered.groupby("brand")["amount"].sum().reset_index().sort_values("amount", ascending=False)
        figb = px.pie(brand_df.head(10), names="brand", values="amount", title="Top Brands by Amount")
        st.plotly_chart(figb, use_container_width=True)
        st.download_button("Download brand CSV", data=df_to_csv_bytes(brand_df), file_name="brands.csv")
    else:
        st.info("brand or amount columns not available.")

st.markdown("---")
st.subheader("Dispatch Day vs Delivery Day (heatmap)")
if "dispatch_date_day" in filtered.columns and "delivery_date_day" in filtered.columns:
    pivot = filtered.pivot_table(index="dispatch_date_day", columns="delivery_date_day", values="invoice_number", aggfunc="count", fill_value=0)
    # reorder days
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    pivot = pivot.reindex(index=[d for d in days if d in pivot.index], columns=[d for d in days if d in pivot.columns])
    st.dataframe(pivot)
    st.download_button("Download dispatch-delivery heatmap CSV", data=df_to_csv_bytes(pivot.reset_index()), file_name="dispatch_delivery_heatmap.csv")
    try:
        fig_heat = px.imshow(pivot.values, x=pivot.columns, y=pivot.index, aspect="auto", labels=dict(x="Delivery Day", y="Dispatch Day", color="Count"))
        st.plotly_chart(fig_heat, use_container_width=True)
    except Exception:
        st.info("Could not render heatmap figure; table shown instead.")
else:
    st.info("Need both dispatch_date and delivery_date to build heatmap (columns: dispatch_date_day, delivery_date_day).")

st.markdown("---")
st.subheader("Full filtered data (preview & export)")
st.dataframe(filtered.head(200))
st.download_button("Download filtered data as CSV", data=df_to_csv_bytes(filtered), file_name="filtered_data.csv")

st.markdown("---")
st.subheader("Notes & Tips")
st.markdown(
    """
- Column name normalization: original column names are cleaned (spaces → underscores, lowercased).
- If app doesn't detect your date or amount columns, please ensure they exist and are spelled similarly to: `invoice date`, `dispatch date`, `delivery date`, `taxable value`, `purchase value`, `closing balance`, `customer name`, `brand`, `item code`.
- You can modify and extend the code to add currency conversions, more KPIs, or PDF export.
"""
)

# Small optional section: allow user to download a template of processed columns for mapping
st.sidebar.markdown("---")
if st.sidebar.button("Download sample mapping CSV"):
    sample = pd.DataFrame({
        "expected_column": ["invoice_date","goods_recd_date","dispatch_date","delivery_date","taxable_value","purchase_value","customer_name","brand","item_code","closing_balance","in_qty","out_qty","amount"],
        "example_header_in_excel": ["Invoice Date","Goods Recd. Date","Dispatch Date","Delivery Date","Taxable Value","Purchase Value","Customer name","Brand","Item Code","Closing Balance","In Qty","Out Qty","Taxable Value"]
    })
    st.sidebar.download_button("Download mapping sample", data=df_to_csv_bytes(sample), file_name="column_mapping_sample.csv")

st.success("Reports generated. Use filters on left to refine. Each visible table/chart has a download option.")
