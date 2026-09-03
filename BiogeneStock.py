import io
import os
import re
import base64
import zipfile
import requests
import pandas as pd
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Biogene India Tools",
    page_icon="🛠️",
    layout="centered"
)


# ============================================================
# FUNCTIONS
# ============================================================

def safe_sheet_name(name):
    name = str(name)

    for ch in ['\\', '/', '*', '[', ']', ':', '?']:
        name = name.replace(ch, "_")

    name = name.strip()

    if not name:
        name = "Blank"

    return name[:31]


def safe_filename(name):
    name = str(name).strip()

    name = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        name
    )

    if not name:
        name = "Biogene_India_ERP"

    return name


def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🛠️ Biogene India Tools")

tool = st.sidebar.radio(
    "Select Tool",
    [
        "📄 Brand Wise Excel Splitter",
        "🛠️ ZIP → EXE Builder"
    ]
)


# ============================================================
# EXCEL SPLITTER
# ============================================================

if tool == "📄 Brand Wise Excel Splitter":

    st.title(
        "📄 Brand Wise Worksheet Splitter"
    )

    st.write(
        "Upload an Excel file and split it into "
        "worksheets based on the **Brand** column."
    )

    uploaded_file = st.file_uploader(
        "Choose Excel File",
        type=["xlsx", "xls"]
    )

    if uploaded_file is not None:

        try:

            with st.spinner(
                "Reading Excel..."
            ):

                df = pd.read_excel(
                    uploaded_file,
                    dtype=object
                )

        except Exception as e:

            st.error(
                f"❌ Excel read error: {e}"
            )

            st.stop()

        # Find Brand column
        brand_col = None

        for col in df.columns:

            if (
                str(col)
                .strip()
                .lower()
                == "brand"
            ):
                brand_col = col
                break

        if brand_col is None:

            st.error(
                "❌ Brand column not found."
            )

            st.stop()

        st.success(
            f"✅ Found Brand column: {brand_col}"
        )

        st.write(
            f"Rows : **{len(df):,}**"
        )

        st.write(
            f"Unique Brands : **"
            f"{df[brand_col].fillna('Blank').nunique():,}"
            f"**"
        )

        if st.button(
            "Split Workbook",
            type="primary"
        ):

            progress = st.progress(0)

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

                    sheet_name = safe_sheet_name(
                        brand
                    )

                    # Avoid duplicate sheet names
                    original_name = sheet_name
                    counter = 1

                    while sheet_name in used_sheet_names:

                        suffix = f"_{counter}"

                        sheet_name = (
                            original_name[:31 - len(suffix)]
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

            output.seek(0)

            progress.empty()

            st.success(
                "✅ Workbook created successfully!"
            )

            st.download_button(
                label="⬇ Download Workbook",
                data=output,
                file_name="Brand_Wise_Workbook.xlsx",
                mime=(
                    "application/"
                    "vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )


# ============================================================
# ZIP → EXE
# ============================================================

else:

    st.title(
        "🛠️ Biogene India ZIP → EXE Builder"
    )

    st.write(
        "Upload your Biogene India ERP ZIP and "
        "create a Windows Portable EXE."
    )

    st.info(
        "💡 EXE Windows build machine par automatically "
        "banega. Aapko apne PC par Node.js install "
        "karne ki zarurat nahi hai."
    )

    # --------------------------------------------------------
    # GitHub Settings
    # --------------------------------------------------------

    with st.expander(
        "⚙️ Build Configuration",
        expanded=True
    ):

        github_token = st.text_input(
            "GitHub Personal Access Token",
            type="password",
            help=(
                "GitHub Actions ko build start karne ke "
                "liye token required hai."
            )
        )

        github_owner = st.text_input(
            "GitHub Username / Organization",
            value=""
        )

        github_repo = st.text_input(
            "GitHub Repository",
            value=""
        )

        exe_name = st.text_input(
            "EXE Name",
            value="Biogene_India_ERP"
        )

    zip_file = st.file_uploader(
        "Upload Biogene India ZIP",
        type=["zip"],
        key="biogene_zip"
    )

    if zip_file is not None:

        st.success(
            f"✅ ZIP selected: {zip_file.name}"
        )

        st.write(
            f"File size: "
            f"{zip_file.size / (1024 * 1024):.2f} MB"
        )

        build_button = st.button(
            "🚀 Build Windows Portable EXE",
            type="primary"
        )

        if build_button:

            if not github_token:
                st.error(
                    "❌ GitHub Token enter karo."
                )
                st.stop()

            if not github_owner:
                st.error(
                    "❌ GitHub Username/Organization enter karo."
                )
                st.stop()

            if not github_repo:
                st.error(
                    "❌ GitHub Repository enter karo."
                )
                st.stop()

            exe_name = safe_filename(
                exe_name
            )

            # ------------------------------------------------
            # GitHub API
            # ------------------------------------------------

            api_base = (
                "https://api.github.com/repos/"
                f"{github_owner}/{github_repo}"
            )

            headers = github_headers(
                github_token
            )

            # ------------------------------------------------
            # Check repository
            # ------------------------------------------------

            with st.spinner(
                "Checking GitHub repository..."
            ):

                response = requests.get(
                    api_base,
                    headers=headers,
                    timeout=30
                )

            if response.status_code != 200:

                st.error(
                    "❌ GitHub repository access failed."
                )

                st.code(
                    response.text
                )

                st.stop()

            st.success(
                "✅ GitHub repository connected."
            )

            # ------------------------------------------------
            # Convert ZIP to Base64
            # ------------------------------------------------

            with st.spinner(
                "Preparing ZIP..."
            ):

                zip_bytes = (
                    zip_file.getvalue()
                )

                encoded_zip = (
                    base64.b64encode(
                        zip_bytes
                    )
                    .decode("utf-8")
                )

            # ------------------------------------------------
            # Create unique build ID
            # ------------------------------------------------

            import time

            build_id = str(
                int(time.time())
            )

            payload = {
                "event_type": "biogene-build",
                "client_payload": {
                    "zip_base64": encoded_zip,
                    "exe_name": exe_name,
                    "build_id": build_id
                }
            }

            # ------------------------------------------------
            # Trigger GitHub Actions
            # ------------------------------------------------

            st.info(
                "🚀 Windows EXE build start ho raha hai..."
            )

            dispatch_url = (
                api_base
                + "/dispatches"
            )

            response = requests.post(
                dispatch_url,
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code not in [
                200,
                201,
                204
            ]:

                st.error(
                    "❌ Build trigger nahi hua."
                )

                st.code(
                    response.text
                )

                st.stop()

            st.success(
                "✅ Build request successfully sent!"
            )

            st.session_state[
                "build_id"
            ] = build_id

            st.session_state[
                "building"
            ] = True

            st.session_state[
                "github_owner"
            ] = github_owner

            st.session_state[
                "github_repo"
            ] = github_repo

            st.session_state[
                "github_token"
            ] = github_token

            st.rerun()


# ============================================================
# BUILD STATUS
# ============================================================

if (
    st.session_state.get(
        "building",
        False
    )
):

    st.divider()

    st.subheader(
        "🔄 Build Status"
    )

    token = st.session_state.get(
        "github_token"
    )

    owner = st.session_state.get(
        "github_owner"
    )

    repo = st.session_state.get(
        "github_repo"
    )

    api_base = (
        "https://api.github.com/repos/"
        f"{owner}/{repo}"
    )

    headers = github_headers(
        token
    )

    # Get latest workflow runs
    runs_url = (
        api_base
        + "/actions/runs"
        "?per_page=10"
    )

    response = requests.get(
        runs_url,
        headers=headers,
        timeout=30
    )

    if response.status_code == 200:

        runs = response.json().get(
            "workflow_runs",
            []
        )

        if runs:

            latest = runs[0]

            status = latest.get(
                "status"
            )

            conclusion = latest.get(
                "conclusion"
            )

            st.write(
                f"**Status:** `{status}`"
            )

            if status == "completed":

                if conclusion == "success":

                    st.success(
                        "🎉 EXE build successfully completed!"
                    )

                    # ----------------------------------------
                    # Download artifacts
                    # ----------------------------------------

                    run_id = latest.get(
                        "id"
                    )

                    artifact_url = (
                        api_base
                        + f"/actions/runs/"
                        f"{run_id}/artifacts"
                    )

                    artifact_response = (
                        requests.get(
                            artifact_url,
                            headers=headers,
                            timeout=30
                        )
                    )

                    if (
                        artifact_response.status_code
                        == 200
                    ):

                        artifacts = (
                            artifact_response
                            .json()
                            .get(
                                "artifacts",
                                []
                            )
                        )

                        if artifacts:

                            artifact = (
                                artifacts[0]
                            )

                            download_url = (
                                artifact.get(
                                    "archive_download_url"
                                )
                            )

                            download_response = (
                                requests.get(
                                    download_url,
                                    headers=headers,
                                    timeout=120
                                )
                            )

                            if (
                                download_response.status_code
                                == 200
                            ):

                                st.download_button(
                                    label=(
                                        "⬇️ Download "
                                        "Biogene India EXE"
                                    ),
                                    data=(
                                        download_response
                                        .content
                                    ),
                                    file_name=(
                                        "Biogene_India_EXE.zip"
                                    ),
                                    mime=(
                                        "application/zip"
                                    )
                                )

                                st.info(
                                    "Artifact ZIP download "
                                    "hoga. Iske andar generated "
                                    "EXE milega."
                                )

                else:

                    st.error(
                        "❌ EXE build failed."
                    )

                    st.write(
                        f"Conclusion: `{conclusion}`"
                    )

                st.session_state[
                    "building"
                ] = False

            else:

                st.info(
                    "⏳ EXE abhi build ho raha hai..."
                )

                st.progress(
                    50
                )

                if st.button(
                    "🔄 Check Build Again"
                ):

                    st.rerun()

    else:

        st.error(
            "GitHub Actions status read nahi ho saka."
        )
