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
    # Add more languages here:
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Korean": "ko",
    "Arabic": "ar",
    "Dutch": "nl",
    "Greek": "el",
    "Hindi": "hi",
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

# ----------------------------
# Session state (persist results across reruns)
# ----------------------------
if "last_transcription" not in st.session_state:
    st.session_state.last_transcription = ""
if "last_translation" not in st.session_state:
    st.session_state.last_translation = ""
if "last_language_label" not in st.session_state:
    st.session_state.last_language_label = ""
if "last_output_folder" not in st.session_state:
    st.session_state.last_output_folder = ""
if "has_results" not in st.session_state:
    st.session_state.has_results = False


def create_output_folder(audio_file_name: str) -> str:
    folder_name = os.path.splitext(os.path.basename(audio_file_name))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = os.path.join(results_folder, f"{folder_name}_{timestamp}")
    os.makedirs(output_folder, exist_ok=True)
    return output_folder


def copy_button(text: str, button_label: str, success_msg: str, key: str):
    """
    Streamlit reruns on every button click. Using session_state keeps results.
    This button copies text to clipboard via a tiny JS snippet.
    """
    if st.button(button_label, key=key):
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
# Action: Transcribe
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
        # Transcribe
        result = transcribe(model, temp_file_path, task="transcribe")
        transcription_text = (result.get("text") or "").strip()

        # Save English transcription
        output_file = os.path.join(output_folder, "transcription.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(transcription_text)

        # Persist results so they don't disappear on Copy button reruns
        st.session_state.last_transcription = transcription_text
        st.session_state.last_translation = ""  # reset unless we translate below
        st.session_state.last_language_label = target_language_label
        st.session_state.last_output_folder = output_folder
        st.session_state.has_results = True

        # Translate (optional)
        if target_language_code is not None and transcription_text:
            translation_text = translator.translate(transcription_text, dest=target_language_code).text.strip()

            # Save translation
            translations_folder = os.path.join(output_folder, "Translations")
            os.makedirs(translations_folder, exist_ok=True)
            translation_file = os.path.join(translations_folder, f"{target_language_label}_translation.txt")
            with open(translation_file, "w", encoding="utf-8") as f:
                f.write(translation_text)

            # Persist translation too
            st.session_state.last_translation = translation_text
            st.session_state.last_language_label = target_language_label

    except Exception as e:
        st.error(f"An error occurred: {e}")


# ----------------------------
# Persisted display (survives Copy button reruns)
# ----------------------------
if st.session_state.has_results:
    st.write("### Transcription Result (English)")
    st.text_area(
        "Transcription (English)",
        value=st.session_state.last_transcription,
        height=160,
        key="transcription_area",
        disabled=True,  # make it read-only
    )
    copy_button(
        st.session_state.last_transcription,
        "Copy Transcription",
        "Copied transcription to clipboard.",
        key="copy_transcription_btn",
    )

    if st.session_state.last_translation:
        st.write(f"### Translated Transcription ({st.session_state.last_language_label})")
        st.text_area(
            f"Translation ({st.session_state.last_language_label})",
            value=st.session_state.last_translation,
            height=160,
            key="translation_area",
            disabled=True,  # make it read-only
        )
        copy_button(
            st.session_state.last_translation,
            "Copy Translation",
            "Copied translation to clipboard.",
            key="copy_translation_btn",
        )