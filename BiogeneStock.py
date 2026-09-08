import streamlit as st
from pathlib import Path
import tempfile

from short_video_creator import Settings, create_short

st.set_page_config(
    page_title="AI Short Video Creator",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Short Video Creator")
st.write("Create Shorts with automatic AI captions and background videos.")

uploaded_video = st.file_uploader(
    "Upload Main Video",
    type=["mp4", "mov", "mkv", "avi", "webm"]
)

uploaded_background = st.file_uploader(
    "Upload Background Video",
    type=["mp4", "mov", "mkv", "avi", "webm"]
)

font_size = st.slider(
    "Caption Font Size",
    min_value=40,
    max_value=180,
    value=120
)

if st.button("🚀 Create Short", type="primary"):

    if uploaded_video is None:
        st.error("Please upload a main video.")
        st.stop()

    if uploaded_background is None:
        st.error("Please upload a background video.")
        st.stop()

    with tempfile.TemporaryDirectory() as temp_dir:

        temp = Path(temp_dir)

        input_video = temp / uploaded_video.name
        background_dir = temp / "backgrounds"
        output_dir = temp / "output"

        background_dir.mkdir()
        output_dir.mkdir()

        input_video.write_bytes(uploaded_video.getbuffer())

        background_file = background_dir / uploaded_background.name
        background_file.write_bytes(
            uploaded_background.getbuffer()
        )

        output_file = output_dir / "short.mp4"

        try:
            with st.spinner("🎬 Creating your short..."):

                result = create_short(
                    input_video=str(input_video),
                    output_path=str(output_file),
                    backgrounds_dir=str(background_dir),
                    settings=Settings(
                        font_size=font_size
                    )
                )

            st.success("✅ Short created successfully!")

            st.video(str(result))

            with open(result, "rb") as f:
                st.download_button(
                    "⬇️ Download Short",
                    f,
                    file_name="short.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            st.error(f"Video creation failed: {e}")
