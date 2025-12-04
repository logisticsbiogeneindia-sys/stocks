# File: BiogeneStock.py
"""
Streamlit app: robust Excel -> interactive reports
Run: pip install streamlit pandas openpyxl plotly matplotlib (plotly optional)
Then: streamlit run BiogeneStock.py
"""

from io import BytesIO
from datetime import datetime
import pandas as pd
import numpy as np
import streamlit as st

# Try Plotly, fallback to matplotlib
USE_PLOTLY = True
try:
    import plotly.express as px
except Exception:
    USE_PLOTLY = False
    import matplotlib.pyplot as plt

# ---------- Helpers ----------
def clean_column_name(c: str) -> str:
    """Normalize header (help matching messy Excel headers)."""
    return (
        str(c)
        .strip()
        .lower()
        .replace("\n", " ")
        .replace("\t", " ")
        .replace(".", "")
        .replace("/", " ")
        .replace("-", "_")
        .replace("  ", " ")
        .replace(" ", "_")
    )

def safe_get_column(df: pd.DataFrame, target: str, aliases: list = None) -> str | None:
    """
    Return actual column name in df that best matches target or any alias.
    Matching: clean_column_name equality.
    """
    want = clean_column_name(target)
    candidates = [want] + ([clean_column_name(a) for a in (aliases or [])] if aliases else [])
    # build mapping of cleaned->actual
    cleaned_map = {clean_column_name(c): c for c in df.columns}
    for cand in candidates:
        if cand in cleaned_map:
            return cleaned_map[cand]
    return None

def load_excel(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0, engine="openpyxl")
    except Exception:
        df = pd.read_excel(uploaded_file, sheet_name=0)
    # preserve original columns but create a cleaned-name map
    orig_cols = list(df.columns)
    cleaned = [clean_column_name(c) for c in orig_cols]
    df.columns = orig_cols  # keep originals
    return df, {cleaned[i]: orig_cols[i] for i in range(len(orig_cols))}

def try_parse_dates(df, col_names):
    for col in col_names:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

def try_numeric(df, col_names):
    for col in col_names:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def compute_derived(df, mapping):
    # amount preference: taxable_value > purchase_value > purchase_value_dollar/inr
    amt_col = mapping.get("taxable_value") or mapping.get("purchase_value")
    if amt_col and amt_col in df.columns:
        df["amount"] = pd.to_numeric(df[amt_col], errors="coerce").fillna(0)
    else:
        df["amount"] = 0.0

    # closing balance numeric
    if mapping.get("closing_balance") in df.columns:
        df["closing_balance"] = pd.to_numeric(df[mapping["closing_balance"]], errors="coerce")

    # delivery_time_days = delivery_date - dispatch_date (if available)
    dcol = mapping.get("delivery_date")
    discol = mapping.get("dispatch_date")
    goodscol = mapping.get("goods_recd_date")
    if dcol in df.columns and discol in df.columns:
        df["delivery_time_days"] = (pd.to_datetime(df[dcol], errors="coerce") - pd.to_datetime(df[discol], errors="coerce")).dt.days
    elif dcol in df.columns and goodscol in df.columns:
        df["delivery_time_days"] = (pd.to_datetime(df[dcol], errors="coerce") - pd.to_datetime(df[goodscol], errors="coerce")).dt.days
    else:
        df["delivery_time_days"] = np.nan

    # day names
    for orig in ("dispatch_date", "delivery_date", "invoice_date"):
        col = mapping.get(orig)
        if col in df.columns:
            df[f"{orig}_day"] = pd.to_datetime(df[col], errors="coerce").dt.day_name()

    # invoice_date cleaned copy for grouping
    if mapping.get("invoice_date") in df.columns:
        df["_invoice_date"] = pd.to_datetime(df[mapping["invoice_date"]], errors="coerce")
    else:
        df["_invoice_date"] = pd.NaT

    return df

def df_to_csv_bytes(df):
    b = BytesIO()
    df.to_csv(b, index=False)
    b.seek(0)
    return b.read()

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Biogene Stock Reports", layout="wide")
st.title("Biogene Stock — Reports Dashboard (robust)")

upload = st.file_uploader("Upload Excel file (.xls/.xlsx)", type=["xls", "xlsx"], accept_multiple_files=False)
if upload is None:
    st.info("Upload your Excel file to continue. App will autodetect & map messy headers.")
    st.stop()

with st.spinner("Loading Excel..."):
    df_raw, cleaned_map = load_excel(upload)

# Show original headers and cleaned mapping for user's reassurance
st.subheader("Column detection")
col1, col2 = st.columns([2, 3])
with col1:
    st.write("Original headers (preview):")
    st.write(list(df_raw.columns)[:40])
with col2:
    st.write("Normalized header keys (cleaned):")
    st.write({k: v for k, v in cleaned_map.items()})

# Build expected mapping using aliases based on user's initial columns list
expected_aliases = {
    "invoice_date": ["invoice date", "invoice_date"],
    "goods_recd_date": ["goods recd date", "goods_recd_date", "goods_received_date"],
    "dispatch_date": ["dispatch date", "dispatch_date"],
    "delivery_date": ["delivery date", "delivery_date"],
    "unit_price_dollar_inr": ["unit price dollar/inr", "unit_price_dollar_inr", "unit_price_dollar_inr"],
    "unit_price_inr": ["unit price inr", "unit_price_inr"],
    "purchase_value": ["purchase value", "purchase_value", "purchase_value_dollar/inr"],
    "taxable_value": ["taxable value", "taxable_value"],
    "item_code": ["item code", "item_code"],
    "discription": ["description", "discription", "discription"],
    "in_qty": ["in qty", "in_qty", "in_quantity"],
    "out_qty": ["out qty", "out_qty", "out_quantity"],
    "closing_balance": ["closing balance", "closing_balance"],
    "customer_name": ["customer name", "customer_name", "customer"],
    "brand": ["brand"],
    "invoice_number": ["invoice number", "invoice_number", "invoice_no"],
    "awb_number": ["awb number", "awb_number"],
    "docket_status": ["docket status", "docket_status"],
    "delivery_date_time": ["delivery date time", "delivery_date_time", "take time to deliver"],
}

# Create mapping of canonical -> actual column names in df (if found)
mapping = {}
for canon, aliases in expected_aliases.items():
    found = safe_get_column(df_raw, canon, aliases)
    if found:
        mapping[canon] = found

# Show mapping and allow user override (if mapping missed something)
st.write("Auto-mapped columns (you can override if wrong):")
mapping_display = {}
for key in sorted(expected_aliases.keys()):
    val = mapping.get(key, "")
    mapping_display[key] = st.text_input(f"{key}", value=val, key=f"map_{key}")

# Update mapping with user overrides
for k, v in mapping_display.items():
    mapping[k] = v.strip() if v else mapping.get(k)

# Apply mapping: create canonical columns in working df where possible
df = df_raw.copy()
for canon, actual in mapping.items():
    if actual and actual in df.columns:
        df[canon] = df[actual]

# Parse and coerce
date_cols = [c for c in ("invoice_date", "goods_recd_date", "dispatch_date", "delivery_date") if mapping.get(c) in df.columns]
df = try_parse_dates(df, date_cols)
num_cols = [c for c in ("unit_price_dollar_inr", "unit_price_inr", "purchase_value", "taxable_value", "closing_balance", "in_qty", "out_qty") if mapping.get(c) in df.columns]
df = try_numeric(df, num_cols)

df = compute_derived(df, mapping)

# Filters sidebar
st.sidebar.header("Filters")
min_date = df["_invoice_date"].min()
max_date = df["_invoice_date"].max()
if pd.isna(min_date) or pd.isna(max_date):
    # fallback to goods_recd_date or dispatch_date if invoice not present
    alt_dates = []
    for alt in ("goods_recd_date", "dispatch_date", "delivery_date"):
        if mapping.get(alt) in df.columns:
            alt_dates.append(df[alt].min())
            alt_dates.append(df[alt].max())
    alt_dates = [d for d in alt_dates if pd.notna(d)]
    if alt_dates:
        min_date = min(alt_dates)
        max_date = max(alt_dates)
    else:
        min_date = datetime.now()
        max_date = datetime.now()

start_date = st.sidebar.date_input("Start date", value=min_date.date() if hasattr(min_date, "date") else datetime.now().date())
end_date = st.sidebar.date_input("End date", value=max_date.date() if hasattr(max_date, "date") else datetime.now().date())

# Selector lists (safe)
cust_col = mapping.get("customer_name")
brand_col = mapping.get("brand")
item_col = mapping.get("item_code")

customers = sorted(df[cust_col].dropna().unique().tolist()) if cust_col in df.columns else []
brands = sorted(df[brand_col].dropna().unique().tolist()) if brand_col in df.columns else []
items = sorted(df[item_col].dropna().unique().tolist()) if item_col in df.columns else []

sel_customers = st.sidebar.multiselect("Customer(s)", options=customers)
sel_brands = st.sidebar.multiselect("Brand(s)", options=brands)
sel_items = st.sidebar.multiselect("Item Code(s)", options=items)

# Filtering df safely
fdf = df.copy()
if "_invoice_date" in fdf.columns and pd.notna(start_date):
    fdf = fdf[(fdf["_invoice_date"] >= pd.Timestamp(start_date)) & (fdf["_invoice_date"] <= pd.Timestamp(end_date))]
if sel_customers and cust_col in fdf.columns:
    fdf = fdf[fdf[cust_col].isin(sel_customers)]
if sel_brands and brand_col in fdf.columns:
    fdf = fdf[fdf[brand_col].isin(sel_brands)]
if sel_items and item_col in fdf.columns:
    fdf = fdf[fdf[item_col].isin(sel_items)]

# KPIs
st.subheader("Key Metrics")
k1, k2, k3, k4 = st.columns(4)
total_invoices = int(fdf.shape[0])
total_amount = fdf["amount"].sum() if "amount" in fdf.columns else 0.0
avg_delivery = fdf["delivery_time_days"].mean() if "delivery_time_days" in fdf.columns else np.nan
total_closing = fdf["closing_balance"].sum() if "closing_balance" in fdf.columns else 0.0
k1.metric("Invoices", f"{total_invoices:,}")
k2.metric("Total Amount", f"{total_amount:,.2f}")
k3.metric("Avg Delivery Days", f"{avg_delivery:.1f}" if not np.isnan(avg_delivery) else "N/A")
k4.metric("Total Closing Balance", f"{total_closing:,.2f}")

st.markdown("---")
left, right = st.columns((2, 1))

# Time series
with left:
    st.subheader("Amount over Time (weekly)")
    if "_invoice_date" in fdf.columns and "amount" in fdf.columns and fdf["_invoice_date"].notna().any():
        ts = fdf.groupby(pd.Grouper(key="_invoice_date", freq="W"))["amount"].sum().reset_index().rename(columns={"_invoice_date": "invoice_date"})
        if USE_PLOTLY:
            fig = px.line(ts, x="invoice_date", y="amount", title="Weekly Amount")
            st.plotly_chart(fig, use_container_width=True)
        else:
            fig, ax = plt.subplots()
            ax.plot(ts["invoice_date"], ts["amount"])
            ax.set_title("Weekly Amount")
            ax.set_xlabel("Invoice Date")
            ax.set_ylabel("Amount")
            fig.autofmt_xdate()
            st.pyplot(fig)
        st.download_button("Download time series CSV", data=df_to_csv_bytes(ts), file_name="time_series.csv")
    else:
        st.info("Need invoice_date and amount to display time series.")

    st.subheader("Top Customers by Amount")
    if cust_col in fdf.columns and "amount" in fdf.columns:
        topc = fdf.groupby(cust_col)["amount"].sum().reset_index().sort_values("amount", ascending=False).head(20)
        if USE_PLOTLY:
            fig2 = px.bar(topc, x="amount", y=cust_col, orientation="h", title="Top Customers by Amount")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            fig, ax = plt.subplots()
            ax.barh(topc[cust_col], topc["amount"])
            ax.set_title("Top Customers by Amount")
            st.pyplot(fig)
        st.dataframe(topc)
        st.download_button("Download top customers CSV", data=df_to_csv_bytes(topc), file_name="top_customers.csv")
    else:
        st.info("Customer or amount column missing.")

    st.subheader("Delivery Time Distribution")
    if "delivery_time_days" in fdf.columns and fdf["delivery_time_days"].notna().any():
        ddf = fdf.dropna(subset=["delivery_time_days"])
        if USE_PLOTLY:
            fig3 = px.histogram(ddf, x="delivery_time_days", nbins=30, title="Delivery Time (days)")
            st.plotly_chart(fig3, use_container_width=True)
        else:
            fig, ax = plt.subplots()
            ax.hist(ddf["delivery_time_days"].astype(float), bins=30)
            ax.set_title("Delivery Time (days)")
            ax.set_xlabel("Days")
            st.pyplot(fig)
        st.download_button("Download delivery times CSV", data=df_to_csv_bytes(ddf[["invoice_number","dispatch_date","delivery_date","delivery_time_days"]].dropna(how="all")), file_name="delivery_times.csv")
    else:
        st.info("No delivery_time_days data available.")

with right:
    st.subheader("Top Items / Inventory")
    if item_col in fdf.columns:
        # aggregate safely
        agg_cols = {}
        if "discription" in fdf.columns:
            agg_cols["description"] = ("discription", "first")
        if "in_qty" in fdf.columns:
            agg_cols["total_in_qty"] = ("in_qty", "sum")
        if "out_qty" in fdf.columns:
            agg_cols["total_out_qty"] = ("out_qty", "sum")
        if "closing_balance" in fdf.columns:
            agg_cols["closing_balance"] = ("closing_balance", "sum")
        if "amount" in fdf.columns:
            agg_cols["total_amount"] = ("amount", "sum")
        # build groupby agg dict
        if agg_cols:
            grouped = fdf.groupby(item_col).agg(**agg_cols).reset_index().sort_values("total_amount", ascending=False) if "total_amount" in agg_cols else fdf.groupby(item_col).size().reset_index(name="count").sort_values("count", ascending=False)
        else:
            grouped = fdf[item_col].value_counts().reset_index().rename(columns={"index": item_col, item_col: "count"})
        st.dataframe(grouped.head(200))
        st.download_button("Download items CSV", data=df_to_csv_bytes(grouped), file_name="top_items.csv")
    else:
        st.info("Item code column not found.")

    st.markdown("### Brand distribution")
    if brand_col in fdf.columns and "amount" in fdf.columns:
        brand_df = fdf.groupby(brand_col)["amount"].sum().reset_index().sort_values("amount", ascending=False)
        if USE_PLOTLY:
            figb = px.pie(brand_df.head(10), names=brand_col, values="amount", title="Top Brands by Amount")
            st.plotly_chart(figb, use_container_width=True)
        else:
            fig, ax = plt.subplots()
            ax.pie(brand_df["amount"].head(10), labels=brand_df[brand_col].head(10), autopct="%1.1f%%")
            ax.set_title("Top Brands")
            st.pyplot(fig)
        st.download_button("Download brand CSV", data=df_to_csv_bytes(brand_df), file_name="brands.csv")
    else:
        st.info("Brand or amount column missing.")

st.markdown("---")
st.subheader("Dispatch Day vs Delivery Day (pivot)")
if "dispatch_date_day" in fdf.columns and "delivery_date_day" in fdf.columns:
    pivot = fdf.pivot_table(index="dispatch_date_day", columns="delivery_date_day", values=mapping.get("invoice_number") or mapping.get("invoice_number", ""), aggfunc="count", fill_value=0)
    # reorder days
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    pivot = pivot.reindex(index=[d for d in days if d in pivot.index], columns=[d for d in days if d in pivot.columns])
    st.dataframe(pivot)
    st.download_button("Download pivot CSV", data=df_to_csv_bytes(pivot.reset_index()), file_name="dispatch_delivery_heatmap.csv")
    if USE_PLOTLY:
        try:
            heat = px.imshow(pivot.values, x=pivot.columns, y=pivot.index, labels=dict(x="Delivery Day", y="Dispatch Day", color="Count"), aspect="auto")
            st.plotly_chart(heat, use_container_width=True)
        except Exception:
            st.info("Could not render heatmap figure; table shown instead.")
else:
    st.info("Dispatch/Delivery day columns missing. Ensure mapping for dispatch_date and delivery_date.")

st.markdown("---")
st.subheader("Filtered data preview & download")
st.dataframe(fdf.head(300))
st.download_button("Download filtered data", data=df_to_csv_bytes(fdf), file_name="filtered_data.csv")

st.markdown("---")
st.subheader("Notes")
st.markdown(
    """
- If a chart/table shows 'missing column', open the auto-mapped list above and paste the exact column header from your Excel to the corresponding field, then re-run/filter.
- This app is defensive: it won't crash when headers are messy or missing — it will show info messages and allow manual mapping.
- For large files (>50k rows) consider increasing Streamlit's data frame allowance or pre-aggregating before upload.
"""
)

st.success("Reports ready. Use sidebar filters and mapping inputs to refine detection.")

# Minimal suggested next actions (two short options)
st.markdown("**Next:**")
st.markdown("**a.** Add currency conversion (USD↔INR) and show amounts in chosen currency.") 
st.markdown("**b.** Generate requirements.txt + Dockerfile for deployment.")
