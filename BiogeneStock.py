import io
import os
import re
import sys
import shutil
import zipfile
import tempfile
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Biogene India Tools",
    page_icon="🛠️",
    layout="centered"
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_filename(name):
    """Make a Windows-safe filename."""
    name = str(name).strip()
    name = re.sub(r'[<>:"/\\|?*]', "_", name)

    if not name:
        name = "Biogene_India_ERP"

    return name


def run_command(command, cwd, log_box=None):
    """
    Run command and stream output into Streamlit.
    """

    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1
        )

        logs = []

        for line in iter(process.stdout.readline, ""):
            line = line.rstrip()

            if line:
                logs.append(line)

                if log_box is not None:
                    log_box.code(
                        "\n".join(logs[-100:]),
                        language="text"
                    )

        process.wait()

        return process.returncode, "\n".join(logs)

    except FileNotFoundError as e:
        return 999, f"Command not found: {e}"

    except Exception as e:
        return 999, str(e)


def find_project_root(folder):
    """
    ZIP ke andar agar ek extra root folder ho,
    to actual project folder detect karta hai.
    """

    folder = Path(folder)

    # Direct project
    project_files = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "main.py",
        "app.py",
        "index.html"
    ]

    for file in project_files:
        if (folder / file).exists():
            return folder

    # One-level nested project
    children = [
        p for p in folder.iterdir()
        if p.is_dir()
    ]

    for child in children:
        for file in project_files:
            if (child / file).exists():
                return child

    return folder


def detect_project_type(project_root):
    """
    Detect Electron / Node / Python / HTML project.
    """

    project_root = Path(project_root)

    package_json = project_root / "package.json"

    if package_json.exists():
        try:
            import json

            with open(package_json, "r", encoding="utf-8") as f:
                package = json.load(f)

            dependencies = {}

            dependencies.update(
                package.get("dependencies", {})
            )

            dependencies.update(
                package.get("devDependencies", {})
            )

            scripts = package.get("scripts", {})

            package_text = str(
                package
            ).lower()

            if (
                "electron" in dependencies
                or "electron-builder" in dependencies
                or "electron" in package_text
                or "electron-builder" in package_text
                or "electron" in str(scripts).lower()
            ):
                return "electron"

            return "node"

        except Exception:
            return "node"

    python_files = [
        "main.py",
        "app.py",
        "run.py",
        "server.py"
    ]

    if any((project_root / f).exists() for f in python_files):
        return "python"

    if (
        (project_root / "requirements.txt").exists()
        or (project_root / "pyproject.toml").exists()
    ):
        return "python"

    if (project_root / "index.html").exists():
        return "html"

    return "unknown"


def find_python_entry(project_root):
    """
    Python entry file detect karega.
    """

    preferred = [
        "main.py",
        "app.py",
        "run.py",
        "server.py"
    ]

    for file in preferred:
        path = project_root / file

        if path.exists():
            return path

    py_files = list(project_root.glob("*.py"))

    if py_files:
        return py_files[0]

    return None


def build_electron(project_root, exe_name, portable, log_box):

    project_root = Path(project_root)

    package_json = project_root / "package.json"

    if not package_json.exists():
        return False, "package.json nahi mila."

    # --------------------------------------------------------
    # Check npm
    # --------------------------------------------------------

    npm_command = "npm.cmd" if os.name == "nt" else "npm"

    npm_check = shutil.which(npm_command)

    if npm_check is None:
        return False, (
            "npm/Node.js available nahi hai. "
            "Electron project ko EXE banane ke liye Node.js/npm "
            "required hai."
        )

    # --------------------------------------------------------
    # Install dependencies
    # --------------------------------------------------------

    st.info("📦 Installing Node dependencies...")

    code, logs = run_command(
        [npm_command, "install"],
        project_root,
        log_box
    )

    if code != 0:
        return False, (
            "npm install failed.\n\n" + logs
        )

    # --------------------------------------------------------
    # Check electron-builder
    # --------------------------------------------------------

    import json

    try:
        with open(package_json, "r", encoding="utf-8") as f:
            package = json.load(f)
    except Exception as e:
        return False, f"package.json read nahi ho saka: {e}"

    dependencies = {}
    dependencies.update(package.get("dependencies", {}))
    dependencies.update(package.get("devDependencies", {}))

    has_builder = "electron-builder" in dependencies

    # --------------------------------------------------------
    # Build command
    # --------------------------------------------------------

    st.info("⚙️ Building Windows EXE...")

    if has_builder:

        command = [
            "npx",
            "electron-builder",
            "--win",
            "--x64"
        ]

    else:

        command = [
            "npx",
            "--yes",
            "electron-builder",
            "--win",
            "--x64"
        ]

    if portable:
        command.append("--portable")

    code, logs = run_command(
        command,
        project_root,
        log_box
    )

    if code != 0:
        return False, (
            "Electron build failed.\n\n" + logs
        )

    # --------------------------------------------------------
    # Find EXE
    # --------------------------------------------------------

    dist_folder = project_root / "dist"

    if not dist_folder.exists():
        return False, "dist folder generate nahi hua."

    exe_files = list(
        dist_folder.rglob("*.exe")
    )

    if not exe_files:
        return False, (
            "Build complete hua lekin EXE nahi mila."
        )

    # Prefer portable EXE
    portable_files = [
        f for f in exe_files
        if "portable" in f.name.lower()
    ]

    if portable and portable_files:
        exe_file = portable_files[0]
    else:
        exe_file = exe_files[0]

    # --------------------------------------------------------
    # Rename EXE
    # --------------------------------------------------------

    desired_name = safe_filename(exe_name)

    new_exe = exe_file.parent / (
        desired_name + ".exe"
    )

    try:
        if exe_file.resolve() != new_exe.resolve():

            if new_exe.exists():
                new_exe.unlink()

            shutil.copy2(
                exe_file,
                new_exe
            )

            exe_file = new_exe

    except Exception:
        pass

    return True, str(exe_file)


def build_python(project_root, exe_name, log_box):

    project_root = Path(project_root)

    entry = find_python_entry(
        project_root
    )

    if entry is None:
        return False, "Python entry file nahi mila."

    # --------------------------------------------------------
    # Check PyInstaller
    # --------------------------------------------------------

    pyinstaller = shutil.which(
        "pyinstaller"
    )

    if pyinstaller is None:

        # Try python -m PyInstaller
        python_exe = sys.executable

        st.info(
            "📦 PyInstaller check/install ho raha hai..."
        )

        code, logs = run_command(
            [
                python_exe,
                "-m",
                "PyInstaller",
                "--version"
            ],
            project_root,
            log_box
        )

        if code != 0:

            st.info(
                "PyInstaller install kiya ja raha hai..."
            )

            code, logs = run_command(
                [
                    python_exe,
                    "-m",
                    "pip",
                    "install",
                    "pyinstaller"
                ],
                project_root,
                log_box
            )

            if code != 0:
                return False, (
                    "PyInstaller install nahi ho saka.\n\n"
                    + logs
                )

        pyinstaller_command = [
            python_exe,
            "-m",
            "PyInstaller"
        ]

    else:

        pyinstaller_command = [
            pyinstaller
        ]

    # --------------------------------------------------------
    # Build
    # --------------------------------------------------------

    st.info(
        f"⚙️ Building Python EXE: {entry.name}"
    )

    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    command = (
        pyinstaller_command
        + [
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            safe_filename(exe_name),
            str(entry)
        ]
    )

    code, logs = run_command(
        command,
        project_root,
        log_box
    )

    if code != 0:
        return False, (
            "PyInstaller build failed.\n\n"
            + logs
        )

    exe_file = (
        dist_dir
        / (safe_filename(exe_name) + ".exe")
    )

    if not exe_file.exists():

        exe_files = list(
            dist_dir.glob("*.exe")
        )

        if not exe_files:
            return False, (
                "Build complete hua lekin EXE nahi mila."
            )

        exe_file = exe_files[0]

    return True, str(exe_file)


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
# TOOL 1 — EXCEL SPLITTER
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

        # ----------------------------------------------------
        # Find Brand column
        # ----------------------------------------------------

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

            progress = st.progress(
                0
            )

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

                for i, (brand, data) in enumerate(
                    groups,
                    start=1
                ):

                    sheet_name = str(
                        brand
                    )

                    for ch in [
                        "\\",
                        "/",
                        "*",
                        "[",
                        "]",
                        ":",
                        "?"
                    ]:

                        sheet_name = (
                            sheet_name
                            .replace(ch, "_")
                        )

                    if not sheet_name.strip():
                        sheet_name = "Blank"

                    sheet_name = (
                        sheet_name[:31]
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
                file_name=(
                    "Brand_Wise_Workbook.xlsx"
                ),
                mime=(
                    "application/"
                    "vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )


# ============================================================
# TOOL 2 — ZIP TO EXE
# ============================================================

else:

    st.title(
        "🛠️ ZIP → Windows EXE Builder"
    )

    st.write(
        "Upload your Biogene India project ZIP and "
        "build a Windows EXE."
    )

    st.warning(
        "⚠️ ZIP ke andar buildable project hona chahiye. "
        "Electron project ke liye Node.js/npm aur "
        "Python project ke liye Python/PyInstaller "
        "required ho sakte hain."
    )

    zip_file = st.file_uploader(
        "Upload Biogene India ZIP",
        type=["zip"],
        key="exe_zip"
    )

    if zip_file is not None:

        st.success(
            f"✅ ZIP selected: {zip_file.name}"
        )

        default_name = Path(
            zip_file.name
        ).stem

        exe_name = st.text_input(
            "EXE File Name",
            value=default_name
        )

        build_mode = st.selectbox(
            "Build Mode",
            [
                "Portable EXE",
                "Normal EXE"
            ]
        )

        portable = (
            build_mode
            == "Portable EXE"
        )

        if st.button(
            "🚀 Build EXE",
            type="primary"
        ):

            # ------------------------------------------------
            # Temporary working directory
            # ------------------------------------------------

            work_dir = Path(
                tempfile.mkdtemp(
                    prefix="biogene_exe_"
                )
            )

            extract_dir = (
                work_dir / "project"
            )

            extract_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            try:

                # --------------------------------------------
                # Save uploaded ZIP
                # --------------------------------------------

                zip_path = (
                    work_dir / "project.zip"
                )

                with open(
                    zip_path,
                    "wb"
                ) as f:

                    f.write(
                        zip_file.getbuffer()
                    )

                st.info(
                    "📦 Extracting ZIP..."
                )

                # --------------------------------------------
                # Extract safely
                # --------------------------------------------

                with zipfile.ZipFile(
                    zip_path,
                    "r"
                ) as z:

                    # Zip Slip protection
                    for member in z.infolist():

                        target = (
                            extract_dir
                            / member.filename
                        )

                        target_resolved = (
                            target.resolve()
                        )

                        if not str(
                            target_resolved
                        ).startswith(
                            str(
                                extract_dir.resolve()
                            )
                        ):

                            raise Exception(
                                "Unsafe ZIP path detected."
                            )

                    z.extractall(
                        extract_dir
                    )

                # --------------------------------------------
                # Find actual project root
                # --------------------------------------------

                project_root = (
                    find_project_root(
                        extract_dir
                    )
                )

                st.write(
                    f"📁 Project folder: "
                    f"`{project_root}`"
                )

                # --------------------------------------------
                # Detect type
                # --------------------------------------------

                project_type = (
                    detect_project_type(
                        project_root
                    )
                )

                if project_type == "electron":

                    st.success(
                        "🟢 Project type detected: "
                        "Electron"
                    )

                elif project_type == "node":

                    st.warning(
                        "🟡 Project type detected: "
                        "Node.js"
                    )

                elif project_type == "python":

                    st.success(
                        "🟢 Project type detected: "
                        "Python"
                    )

                elif project_type == "html":

                    st.warning(
                        "🟡 HTML project detected. "
                        "HTML ko directly EXE banane ke "
                        "liye Electron wrapper required hai."
                    )

                else:

                    st.error(
                        "❌ Project type detect nahi hua."
                    )

                    st.info(
                        "ZIP mein package.json, main.py, "
                        "app.py, requirements.txt ya "
                        "index.html hona chahiye."
                    )

                    st.stop()

                # --------------------------------------------
                # Build log
                # --------------------------------------------

                st.subheader(
                    "📋 Build Log"
                )

                log_box = st.empty()

                # --------------------------------------------
                # BUILD
                # --------------------------------------------

                if project_type == "electron":

                    success, result = (
                        build_electron(
                            project_root,
                            exe_name,
                            portable,
                            log_box
                        )
                    )

                elif project_type == "python":

                    success, result = (
                        build_python(
                            project_root,
                            exe_name,
                            log_box
                        )
                    )

                else:

                    success = False

                    result = (
                        "Node/HTML project ko "
                        "automatic EXE packaging ke liye "
                        "Electron configuration required hai."
                    )

                # --------------------------------------------
                # RESULT
                # --------------------------------------------

                if success:

                    exe_path = Path(
                        result
                    )

                    if not exe_path.exists():

                        st.error(
                            "❌ EXE file locate nahi hui."
                        )

                    else:

                        st.success(
                            "🎉 EXE successfully created!"
                        )

                        st.write(
                            f"**EXE:** `{exe_path.name}`"
                        )

                        with open(
                            exe_path,
                            "rb"
                        ) as f:

                            exe_data = f.read()

                        st.download_button(
                            label=(
                                "⬇️ Download EXE"
                            ),
                            data=exe_data,
                            file_name=(
                                exe_path.name
                            ),
                            mime=(
                                "application/"
                                "vnd.microsoft.portable-executable"
                            )
                        )

                else:

                    st.error(
                        "❌ EXE build failed."
                    )

                    st.code(
                        result,
                        language="text"
                    )

            except zipfile.BadZipFile:

                st.error(
                    "❌ Invalid ZIP file."
                )

            except Exception as e:

                st.error(
                    f"❌ Error: {e}"
                )

            finally:

                # --------------------------------------------
                # Cleanup
                # --------------------------------------------

                try:

                    shutil.rmtree(
                        work_dir,
                        ignore_errors=True
                    )

                except Exception:
                    pass
