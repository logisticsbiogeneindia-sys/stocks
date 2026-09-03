import io
import os
import time
import base64
import zipfile
import requests
import pandas as pd
import streamlit as st


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Biogene India ERP Tools",
    page_icon="🏢",
    layout="wide"
)


# =========================================================
# GITHUB SETTINGS FROM STREAMLIT SECRETS
# =========================================================

GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", "")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "")

GITHUB_API = "https://api.github.com"


# =========================================================
# HEADER
# =========================================================

st.title("🏢 Biogene India ERP Tools")
st.caption("SAP Business One Style ERP Utilities")


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("⚙️ Tools")

    tool = st.radio(
        "Select Tool",
        [
            "📊 Brand Wise Excel Splitter",
            "📦 ZIP → Windows EXE Builder"
        ]
    )

    st.divider()

    st.info(
        "GitHub configuration is loaded automatically "
        "from Streamlit Secrets."
    )


# =========================================================
# TOOL 1
# BRAND WISE EXCEL SPLITTER
# =========================================================

if tool == "📊 Brand Wise Excel Splitter":

    st.header("📊 Brand Wise Worksheet Splitter")

    st.write(
        "Upload an Excel file and split it into separate "
        "worksheets based on the **Brand** column."
    )

    uploaded_file = st.file_uploader(
        "Choose Excel File",
        type=["xlsx", "xls"],
        key="excel_upload"
    )

    if uploaded_file is not None:

        try:

            with st.spinner("Reading Excel..."):

                df = pd.read_excel(
                    uploaded_file,
                    dtype=object
                )

            # -------------------------------------------------
            # FIND BRAND COLUMN
            # -------------------------------------------------

            brand_col = None

            for col in df.columns:

                if str(col).strip().lower() == "brand":

                    brand_col = col
                    break

            if brand_col is None:

                st.error(
                    "❌ Brand column not found."
                )

                st.stop()

            # -------------------------------------------------
            # INFORMATION
            # -------------------------------------------------

            st.success(
                f"✅ Brand column found: **{brand_col}**"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Total Rows",
                    f"{len(df):,}"
                )

            with col2:
                unique_brands = (
                    df[brand_col]
                    .fillna("Blank")
                    .nunique()
                )

                st.metric(
                    "Unique Brands",
                    unique_brands
                )

            with col3:

                blank_count = (
                    df[brand_col]
                    .isna()
                    .sum()
                )

                st.metric(
                    "Blank Brand Rows",
                    blank_count
                )

            # -------------------------------------------------
            # PREVIEW
            # -------------------------------------------------

            st.subheader("Preview")

            st.dataframe(
                df.head(20),
                use_container_width=True
            )

            # -------------------------------------------------
            # SPLIT
            # -------------------------------------------------

            if st.button(
                "🚀 Split Workbook",
                type="primary",
                use_container_width=True
            ):

                progress = st.progress(0)

                status = st.empty()

                output = io.BytesIO()

                with pd.ExcelWriter(
                    output,
                    engine="xlsxwriter"
                ) as writer:

                    groups = df.groupby(
                        df[brand_col].fillna("Blank"),
                        sort=True
                    )

                    total = len(groups)

                    used_sheet_names = set()

                    for i, (brand, data) in enumerate(
                        groups,
                        start=1
                    ):

                        sheet_name = str(brand)

                        # Excel invalid characters
                        invalid_chars = [
                            "\\",
                            "/",
                            "*",
                            "[",
                            "]",
                            ":",
                            "?"
                        ]

                        for ch in invalid_chars:

                            sheet_name = (
                                sheet_name.replace(
                                    ch,
                                    "_"
                                )
                            )

                        sheet_name = sheet_name.strip()

                        if not sheet_name:
                            sheet_name = "Blank"

                        sheet_name = sheet_name[:31]

                        # Avoid duplicate sheet names
                        original_name = sheet_name

                        counter = 1

                        while sheet_name in used_sheet_names:

                            suffix = f"_{counter}"

                            sheet_name = (
                                original_name[
                                    :31-len(suffix)
                                ]
                                + suffix
                            )

                            counter += 1

                        used_sheet_names.add(
                            sheet_name
                        )

                        data.to_excel(
                            writer,
                            sheet_name=sheet_name,
                            index=False
                        )

                        progress.progress(
                            i / total
                        )

                        status.write(
                            f"Creating sheet: "
                            f"**{sheet_name}** "
                            f"({i}/{total})"
                        )

                output.seek(0)

                progress.empty()
                status.empty()

                st.success(
                    "✅ Workbook created successfully!"
                )

                st.download_button(
                    label="⬇️ Download Brand Wise Workbook",
                    data=output,
                    file_name="Brand_Wise_Workbook.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-"
                        "officedocument.spreadsheetml.sheet"
                    ),
                    use_container_width=True
                )

        except Exception as e:

            st.error(
                f"❌ Error: {str(e)}"
            )


# =========================================================
# TOOL 2
# ZIP → WINDOWS EXE
# =========================================================

elif tool == "📦 ZIP → Windows EXE Builder":

    st.header("📦 ZIP → Windows Portable EXE Builder")

    st.write(
        "Upload your Biogene India ERP project ZIP. "
        "The project will be sent to a Windows GitHub Actions "
        "runner to build a portable EXE."
    )

    # -----------------------------------------------------
    # CHECK SECRETS
    # -----------------------------------------------------

    missing = []

    if not GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")

    if not GITHUB_OWNER:
        missing.append("GITHUB_OWNER")

    if not GITHUB_REPO:
        missing.append("GITHUB_REPO")

    if missing:

        st.error(
            "❌ Streamlit Secrets incomplete."
        )

        st.warning(
            "Missing: " + ", ".join(missing)
        )

        st.code(
            '''GITHUB_TOKEN = "github_pat_xxxxxxxxx"
GITHUB_OWNER = "your-github-username"
GITHUB_REPO = "your-build-repository"''',
            language="toml"
        )

        st.stop()

    st.success(
        f"✅ GitHub connected: "
        f"{GITHUB_OWNER}/{GITHUB_REPO}"
    )

    # -----------------------------------------------------
    # ZIP UPLOAD
    # -----------------------------------------------------

    zip_file = st.file_uploader(
        "Upload ERP ZIP File",
        type=["zip"],
        key="erp_zip"
    )

    exe_name = st.text_input(
        "EXE Name",
        value="Biogene-India-ERP",
        help="Name of the generated Windows EXE"
    )

    # -----------------------------------------------------
    # BUILD BUTTON
    # -----------------------------------------------------

    if zip_file is not None:

        zip_size_mb = (
            len(zip_file.getvalue())
            / (1024 * 1024)
        )

        st.info(
            f"ZIP Size: **{zip_size_mb:.2f} MB**"
        )

        if zip_size_mb > 20:

            st.warning(
                "⚠️ ZIP is larger than 20 MB. "
                "The current transfer method may not be "
                "suitable for very large projects."
            )

        if st.button(
            "🚀 Build Windows Portable EXE",
            type="primary",
            use_container_width=True
        ):

            # -------------------------------------------------
            # READ ZIP
            # -------------------------------------------------

            zip_bytes = zip_file.getvalue()

            # -------------------------------------------------
            # BASE64
            # -------------------------------------------------

            encoded_zip = base64.b64encode(
                zip_bytes
            ).decode("utf-8")

            # -------------------------------------------------
            # BUILD ID
            # -------------------------------------------------

            build_id = str(
                int(time.time())
            )

            # -------------------------------------------------
            # GITHUB API HEADERS
            # -------------------------------------------------

            headers = {
                "Authorization":
                    f"Bearer {GITHUB_TOKEN}",

                "Accept":
                    "application/vnd.github+json",

                "X-GitHub-Api-Version":
                    "2022-11-28"
            }

            # -------------------------------------------------
            # DISPATCH WORKFLOW
            # -------------------------------------------------

            dispatch_url = (
                f"{GITHUB_API}/repos/"
                f"{GITHUB_OWNER}/"
                f"{GITHUB_REPO}/dispatches"
            )

            payload = {

                "event_type":
                    "biogene-build",

                "client_payload": {

                    "zip_base64":
                        encoded_zip,

                    "exe_name":
                        exe_name,

                    "build_id":
                        build_id
                }
            }

            st.write("### 1️⃣ Sending project to Windows Builder...")

            try:

                response = requests.post(
                    dispatch_url,
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                if response.status_code not in [200, 201, 204]:

                    st.error(
                        "❌ GitHub build trigger failed."
                    )

                    st.code(
                        response.text
                    )

                    st.stop()

                st.success(
                    "✅ Windows build started."
                )

            except Exception as e:

                st.error(
                    f"❌ GitHub connection error: {e}"
                )

                st.stop()

            # -------------------------------------------------
            # WAIT FOR ACTION
            # -------------------------------------------------

            st.write(
                "### 2️⃣ Building Windows EXE..."
            )

            progress = st.progress(0)

            status = st.empty()

            found_run = None

            max_attempts = 60

            for attempt in range(
                max_attempts
            ):

                try:

                    runs_url = (
                        f"{GITHUB_API}/repos/"
                        f"{GITHUB_OWNER}/"
                        f"{GITHUB_REPO}/"
                        f"actions/runs"
                    )

                    params = {
                        "per_page": 10
                    }

                    runs_response = requests.get(
                        runs_url,
                        headers=headers,
                        params=params,
                        timeout=30
                    )

                    if (
                        runs_response.status_code
                        == 200
                    ):

                        runs = (
                            runs_response
                            .json()
                            .get(
                                "workflow_runs",
                                []
                            )
                        )

                        for run in runs:

                            created_at = (
                                run.get(
                                    "created_at",
                                    ""
                                )
                            )

                            if (
                                build_id
                                in str(
                                    run.get(
                                        "display_title",
                                        ""
                                    )
                                )
                            ):

                                found_run = run
                                break

                        # Fallback: newest run
                        if found_run is None and runs:

                            latest = runs[0]

                            created = (
                                latest.get(
                                    "created_at",
                                    ""
                                )
                            )

                            found_run = latest

                    if found_run:

                        run_status = (
                            found_run.get(
                                "status"
                            )
                        )

                        conclusion = (
                            found_run.get(
                                "conclusion"
                            )
                        )

                        progress_value = min(
                            0.95,
                            0.05
                            + (
                                attempt
                                / max_attempts
                            ) * 0.90
                        )

                        progress.progress(
                            progress_value
                        )

                        status.write(
                            f"Build Status: "
                            f"**{run_status}**"
                        )

                        if (
                            run_status
                            == "completed"
                        ):

                            if conclusion == "success":

                                break

                            else:

                                st.error(
                                    "❌ Windows EXE build failed."
                                )

                                run_url = (
                                    found_run
                                    .get(
                                        "html_url",
                                        ""
                                    )
                                )

                                if run_url:
                                    st.write(
                                        f"GitHub Actions Run: "
                                        f"{run_url}"
                                    )

                                st.stop()

                except Exception:
                    pass

                time.sleep(5)

            # -------------------------------------------------
            # CHECK BUILD
            # -------------------------------------------------

            if not found_run:

                st.error(
                    "❌ Build run was not detected."
                )

                st.stop()

            conclusion = (
                found_run.get(
                    "conclusion"
                )
            )

            if conclusion != "success":

                st.error(
                    "❌ EXE build failed."
                )

                st.stop()

            progress.progress(1.0)

            status.write(
                "✅ Windows EXE build completed!"
            )

            # -------------------------------------------------
            # DOWNLOAD ARTIFACT
            # -------------------------------------------------

            st.write(
                "### 3️⃣ Preparing EXE download..."
            )

            run_id = found_run.get(
                "id"
            )

            artifacts_url = (
                f"{GITHUB_API}/repos/"
                f"{GITHUB_OWNER}/"
                f"{GITHUB_REPO}/"
                f"actions/runs/"
                f"{run_id}/artifacts"
            )

            try:

                artifacts_response = (
                    requests.get(
                        artifacts_url,
                        headers=headers,
                        timeout=30
                    )
                )

                if (
                    artifacts_response
                    .status_code != 200
                ):

                    st.error(
                        "❌ Could not get build artifact."
                    )

                    st.code(
                        artifacts_response.text
                    )

                    st.stop()

                artifacts = (
                    artifacts_response
                    .json()
                    .get(
                        "artifacts",
                        []
                    )
                )

                if not artifacts:

                    st.error(
                        "❌ No EXE artifact found."
                    )

                    st.stop()

                artifact = artifacts[0]

                artifact_id = artifact.get(
                    "id"
                )

                download_url = (
                    f"{GITHUB_API}/repos/"
                    f"{GITHUB_OWNER}/"
                    f"{GITHUB_REPO}/"
                    f"actions/artifacts/"
                    f"{artifact_id}/zip"
                )

                st.write(
                    "Downloading build..."
                )

                artifact_response = (
                    requests.get(
                        download_url,
                        headers=headers,
                        timeout=120
                    )
                )

                if (
                    artifact_response
                    .status_code != 200
                ):

                    st.error(
                        "❌ Could not download artifact."
                    )

                    st.stop()

                st.success(
                    "🎉 EXE is ready!"
                )

                st.download_button(
                    label="⬇️ Download Windows EXE",
                    data=artifact_response.content,
                    file_name=(
                        f"{exe_name}.zip"
                    ),
                    mime="application/zip",
                    use_container_width=True
                )

                st.info(
                    "ZIP download ke andar Windows "
                    "Portable EXE milega."
                )

            except Exception as e:

                st.error(
                    f"❌ Artifact download error: {e}"
                )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Biogene India ERP • SAP Business One Style ERP"
)
