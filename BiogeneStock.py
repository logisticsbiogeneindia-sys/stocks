import io
from copy import copy

import streamlit as st
from openpyxl import load_workbook, Workbook

st.set_page_config(page_title="Excel Workbook Splitter", layout="wide")

st.title("📄 Excel Workbook Splitter")
st.write("Split a workbook into multiple worksheets based on any column.")

uploaded_file = st.file_uploader(
    "Upload Excel Workbook",
    type=["xlsx"]
)

if uploaded_file:

    wb = load_workbook(uploaded_file)
    ws = wb.active

    headers = []

    for cell in ws[1]:
        headers.append("" if cell.value is None else str(cell.value).strip())

    if not headers:
        st.error("No headers found.")
        st.stop()

    split_column = st.selectbox(
        "Select column to split by",
        headers
    )

    if st.button("Split Workbook"):

        split_col = headers.index(split_column) + 1

        new_wb = Workbook()
        new_wb.remove(new_wb.active)

        sheets = {}

        header = list(ws[1])

        for row in ws.iter_rows(min_row=2):

            value = row[split_col - 1].value

            if value is None or str(value).strip() == "":
                sheet_name = "Blank"
            else:
                sheet_name = str(value).strip()

            for ch in ['\\', '/', '*', '[', ']', ':', '?']:
                sheet_name = sheet_name.replace(ch, "_")

            sheet_name = sheet_name[:31]

            if sheet_name not in sheets:

                sh = new_wb.create_sheet(sheet_name)
                sheets[sheet_name] = sh

                # Copy Header
                for c, cell in enumerate(header, start=1):

                    n = sh.cell(row=1, column=c)
                    n.value = cell.value

                    if cell.has_style:
                        n.font = copy(cell.font)
                        n.fill = copy(cell.fill)
                        n.border = copy(cell.border)
                        n.alignment = copy(cell.alignment)
                        n.number_format = cell.number_format
                        n.protection = copy(cell.protection)

            sh = sheets[sheet_name]
            new_row = sh.max_row + 1

            for c, cell in enumerate(row, start=1):

                n = sh.cell(row=new_row, column=c)
                n.value = cell.value

                if cell.has_style:
                    n.font = copy(cell.font)
                    n.fill = copy(cell.fill)
                    n.border = copy(cell.border)
                    n.alignment = copy(cell.alignment)
                    n.number_format = cell.number_format
                    n.protection = copy(cell.protection)

        # Copy column widths
        for sh in new_wb.worksheets:
            for col, dim in ws.column_dimensions.items():
                sh.column_dimensions[col].width = dim.width

        output = io.BytesIO()
        new_wb.save(output)
        output.seek(0)

        st.success(f"Created {len(sheets)} worksheets.")

        st.download_button(
            "⬇ Download Split Workbook",
            data=output,
            file_name="Split_Workbook.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
