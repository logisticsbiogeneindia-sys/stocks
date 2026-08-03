import io
import streamlit as st
from openpyxl import load_workbook, Workbook

st.set_page_config(
    page_title="Brand Splitter",
    page_icon="📄"
)

st.title("📄 Brand Wise Worksheet Splitter")

uploaded_file = st.file_uploader(
    "Select Excel Workbook",
    type=["xlsx"]
)

if uploaded_file is not None:

    with st.spinner("Reading workbook..."):
        wb = load_workbook(uploaded_file, data_only=True)

    ws = wb.active

    headers = [
        str(c.value).strip() if c.value else ""
        for c in ws[1]
    ]

    if "Brand" not in headers and "brand" not in [h.lower() for h in headers]:
        st.error("Brand column not found.")
        st.stop()

    brand_col = next(
        i for i, h in enumerate(headers)
        if h.lower() == "brand"
    )

    st.success("Brand column detected.")

    if st.button("Split Workbook"):

        progress = st.progress(0)

        output = Workbook()
        output.remove(output.active)

        sheets = {}

        header = [c.value for c in ws[1]]

        total = ws.max_row - 1

        for r, row in enumerate(
                ws.iter_rows(min_row=2, values_only=True),
                start=1):

            brand = row[brand_col]

            if brand is None or str(brand).strip() == "":
                brand = "Blank"

            name = str(brand).strip()

            for ch in '\\/*[]:?':
                name = name.replace(ch, "_")

            name = name[:31]

            if name not in sheets:
                sh = output.create_sheet(title=name)
                sh.append(header)
                sheets[name] = sh

            sheets[name].append(row)

            if r % 200 == 0 or r == total:
                progress.progress(min(r / total, 1.0))

        bio = io.BytesIO()
        output.save(bio)
        bio.seek(0)

        progress.empty()

        st.success(f"Finished! {len(sheets)} worksheets created.")

        st.download_button(
            "⬇ Download Workbook",
            data=bio,
            file_name="Brand_Wise_Workbook.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
