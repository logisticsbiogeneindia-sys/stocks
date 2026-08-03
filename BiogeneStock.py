import io
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Brand Wise Splitter",
    page_icon="📄",
    layout="centered"
)

st.title("📄 Brand Wise Worksheet Splitter")
st.write("Upload an Excel file and split it into worksheets based on the **Brand** column.")

uploaded_file = st.file_uploader(
    "Choose Excel File",
    type=["xlsx", "xls"]
)

if uploaded_file is not None:

    with st.spinner("Reading Excel..."):
        df = pd.read_excel(uploaded_file, dtype=object)

    # Find Brand column (case-insensitive)
    brand_col = None
    for col in df.columns:
        if str(col).strip().lower() == "brand":
            brand_col = col
            break

    if brand_col is None:
        st.error("❌ Brand column not found.")
        st.stop()

    st.success(f"✅ Found Brand column: {brand_col}")

    st.write(f"Rows : **{len(df):,}**")
    st.write(f"Unique Brands : **{df[brand_col].fillna('Blank').nunique()}**")

    if st.button("Split Workbook"):

        progress = st.progress(0)

        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

            groups = df.groupby(df[brand_col].fillna("Blank"), sort=True)

            total = len(groups)

            for i, (brand, data) in enumerate(groups, start=1):

                sheet_name = str(brand)

                for ch in ['\\', '/', '*', '[', ']', ':', '?']:
                    sheet_name = sheet_name.replace(ch, "_")

                sheet_name = sheet_name[:31]

                data.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

                progress.progress(i / total)

        output.seek(0)

        progress.empty()

        st.success("✅ Workbook created successfully!")

        st.download_button(
            label="⬇ Download Workbook",
            data=output,
            file_name="Brand_Wise_Workbook.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
