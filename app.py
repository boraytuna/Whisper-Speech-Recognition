import os
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from googletrans import Translator
from whisper import load_model, transcribe

# ----------------------------
# UI
# ----------------------------
st.title("Whisper Audio Transcription and Translation")
st.write("Upload an audio file, choose a model, and optionally translate the transcription.")

uploaded_file = st.file_uploader(
    "Choose an audio file...",
    type=["mp3", "wav", "m4a", "mp4"],
)

model_size = st.selectbox("Choose model size:", ["tiny", "base", "small", "medium", "large"])

# googletrans needs language CODES (e.g., zh-cn), not names (e.g., "chinese")
LANG_OPTIONS = {
    "None": None,
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Turkish": "tr",
    "Japanese": "ja",
    "Chinese (Simplified)": "zh-cn",
    "Chinese (Traditional)": "zh-tw",
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Korean": "ko",
    "Polish": "pl",
    "Dutch": "nl",
}

target_language_label = st.selectbox("Translate Transcription To", list(LANG_OPTIONS.keys()))
target_language_code = LANG_OPTIONS[target_language_label]

# ----------------------------
# Folders
# ----------------------------
temp_upload_folder = "TempUploads"
results_folder = "Results"
os.makedirs(temp_upload_folder, exist_ok=True)
os.makedirs(results_folder, exist_ok=True)

translator = Translator()


def create_output_folder(audio_file_name: str) -> str:
    folder_name = os.path.splitext(os.path.basename(audio_file_name))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = os.path.join(results_folder, f"{folder_name}_{timestamp}")
    os.makedirs(output_folder, exist_ok=True)
    return output_folder


def copy_button(text: str, button_label: str, success_msg: str):
    """
    Copies `text` to clipboard via a tiny JS snippet.
    Streamlit doesn't provide native clipboard API, so we do it this way.
    """
    if st.button(button_label):
        components.html(
            f"""
            <script>
              navigator.clipboard.writeText({text!r});
            </script>
            """,
            height=0,
            width=0,
        )
        st.success(success_msg)


# ----------------------------
# Action
# ----------------------------
if st.button("Transcribe"):
    if uploaded_file is None:
        st.error("Please upload an audio file.")
        st.stop()

    temp_file_path = os.path.join(temp_upload_folder, uploaded_file.name)
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    model = load_model(model_size)
    output_folder = create_output_folder(uploaded_file.name)

    try:
        result = transcribe(model, temp_file_path, task="transcribe")
        transcription_text = (result.get("text") or "").strip()

        # Save English transcription
        output_file = os.path.join(output_folder, "transcription.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(transcription_text)

        st.write("### Transcription Result (English)")
        st.text_area(
            "Transcription (English)",
            value=transcription_text,
            height=160,
            key="transcription_area",
        )
        copy_button(transcription_text, "Copy Transcription", "Copied transcription to clipboard.")

        # Translate (optional)
        if target_language_code is not None and transcription_text:
            translation_text = translator.translate(transcription_text, dest=target_language_code).text.strip()

            translations_folder = os.path.join(output_folder, "Translations")
            os.makedirs(translations_folder, exist_ok=True)
            translation_file = os.path.join(translations_folder, f"{target_language_label}_translation.txt")
            with open(translation_file, "w", encoding="utf-8") as f:
                f.write(translation_text)

            st.write(f"### Translated Transcription ({target_language_label})")
            st.text_area(
                f"Translation ({target_language_label})",
                value=translation_text,
                height=160,
                key="translation_area",
            )
            copy_button(translation_text, "Copy Translation", "Copied translation to clipboard.")

    except Exception as e:
        st.error(f"An error occurred: {e}")