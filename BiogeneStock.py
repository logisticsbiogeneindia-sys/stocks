import io
import streamlit as st
from openpyxl import load_workbook, Workbook

st.set_page_config(page_title="Brand Wise Splitter", layout="centered")

st.title("📄 Brand Wise Worksheet Splitter")

uploaded_file = st.file_uploader(
    "Upload Excel Workbook",
    type=["xlsx"]
)

if uploaded_file:

    wb = load_workbook(uploaded_file)
    ws = wb.active

    headers = [str(c.value).strip() if c.value else "" for c in ws[1]]

    brand_col = None
    for i, h in enumerate(headers):
        if h.lower() == "brand":
            brand_col = i + 1
            break

    if brand_col is None:
        st.error("Brand column not found.")
        st.stop()

    st.success(f"Brand column found (Column {brand_col})")

    if st.button("Split Workbook"):

        out_wb = Workbook()
        out_wb.remove(out_wb.active)

        sheets = {}

        # Header row
        header = [c.value for c in ws[1]]

        total_rows = ws.max_row - 1
        progress = st.progress(0)

        processed = 0

        for row in ws.iter_rows(min_row=2, values_only=True):

            processed += 1

            if total_rows > 0 and processed % 100 == 0:
                progress.progress(min(processed / total_rows, 1.0))

            brand = row[brand_col - 1]

            if brand is None or str(brand).strip() == "":
                brand = "Blank"

            brand = str(brand).strip()

            # Remove invalid worksheet characters
            for ch in '\\/*[]:?':
                brand = brand.replace(ch, "_")

            brand = brand[:31]

            if brand not in sheets:

                sh = out_wb.create_sheet(title=brand)
                sheets[brand] = sh
                sh.append(header)

            sheets[brand].append(row)

        progress.progress(1.0)

        output = io.BytesIO()
        out_wb.save(output)
        output.seek(0)

        st.success(f"Done! Created {len(sheets)} worksheets.")

        st.download_button(
            "⬇ Download Split Workbook",
            data=output,
            file_name="Brand_Wise_Workbook.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
