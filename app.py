import os
import tempfile
import io

import streamlit as st
from googletrans import Translator
from whisper import load_model, transcribe
from gtts import gTTS

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
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Turkish": "tr",
    "Japanese": "ja",
    "Chinese (Simplified)": "zh-cn",
    "Chinese (Traditional)": "zh-tw",
    "Polish": "pl",
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Korean": "ko",
    "Arabic": "ar",
    "Dutch": "nl",
    "Greek": "el",
    "Hindi": "hi",
}

translator = Translator()

# ----------------------------
# Session state (persist results across reruns)
# ----------------------------
st.session_state.setdefault("last_transcription", "")
st.session_state.setdefault("last_translation", "")
st.session_state.setdefault("last_language_label", "")
st.session_state.setdefault("last_language_code", None)
st.session_state.setdefault("has_results", False)
st.session_state.setdefault("translation_error", "")


def tts_lang_from_googletrans_code(code: str | None) -> str:
    """Map translation codes (googletrans-style) to gTTS language codes."""
    if not code:
        return "en"

    c = code.lower()

    # Chinese: gTTS generally uses "zh"
    if c in ("zh-cn", "zh-tw"):
        return "zh"

    # Some other common normalizations (safe defaults)
    if c.startswith("pt-"):
        return "pt"
    if c.startswith("en-"):
        return "en"
    if c.startswith("es-"):
        return "es"
    if c.startswith("fr-"):
        return "fr"
    if c.startswith("de-"):
        return "de"

    return c


def speak_text(text: str, tts_lang: str, label: str):
    """Generate TTS audio (mp3) and play it in Streamlit."""
    if not text or not text.strip():
        st.warning(f"No {label} text to read.")
        return

    try:
        mp3_fp = io.BytesIO()
        tts = gTTS(text=text.strip(), lang=tts_lang)
        tts.write_to_fp(mp3_fp)

        audio_bytes = mp3_fp.getvalue()
        if not audio_bytes:
            st.error("TTS produced empty audio. This usually means the gTTS request failed.")
            return

        # Safari is picky; use audio/mpeg for mp3
        st.audio(audio_bytes, format="audio/mpeg")

    except Exception as e:
        st.error(f"Text-to-speech failed ({label}): {e}")


def retranslate_from_state():
    """Re-translate using the existing transcription (no Whisper call)."""
    st.session_state.translation_error = ""

    label = st.session_state.target_language_label
    code = LANG_OPTIONS.get(label)

    # If we haven't transcribed yet, nothing to translate.
    if not st.session_state.has_results or not st.session_state.last_transcription.strip():
        st.session_state.last_translation = ""
        st.session_state.last_language_label = ""
        st.session_state.last_language_code = None
        return

    # If user chose None -> clear translation
    if code is None:
        st.session_state.last_translation = ""
        st.session_state.last_language_label = ""
        st.session_state.last_language_code = None
        return

    try:
        transcription_text = st.session_state.last_transcription.strip()
        translation_text = translator.translate(transcription_text, dest=code).text.strip()

        st.session_state.last_translation = translation_text
        st.session_state.last_language_label = label
        st.session_state.last_language_code = code

    except Exception as e:
        st.session_state.last_translation = ""
        st.session_state.last_language_label = ""
        st.session_state.last_language_code = None
        st.session_state.translation_error = str(e)


target_language_label = st.selectbox(
    "Translate Transcription To",
    list(LANG_OPTIONS.keys()),
    key="target_language_label",
    on_change=retranslate_from_state,
)
target_language_code = LANG_OPTIONS[target_language_label]

# ----------------------------
# Action: Transcribe
# ----------------------------
if st.button("Transcribe"):
    if uploaded_file is None:
        st.error("Please upload an audio file.")
        st.stop()

    suffix = os.path.splitext(uploaded_file.name)[1] or ".mp3"
    tmp_path = None

    try:
        # Whisper needs a file path; use a temporary file instead of server folders.
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name

        model = load_model(model_size)
        result = transcribe(model, tmp_path, task="transcribe")
        transcription_text = (result.get("text") or "").strip()

        st.session_state.last_transcription = transcription_text
        st.session_state.has_results = True

        # Reset translation state
        st.session_state.last_translation = ""
        st.session_state.last_language_label = ""
        st.session_state.last_language_code = None
        st.session_state.translation_error = ""

        # Translate immediately based on current dropdown selection
        if target_language_code is not None and transcription_text:
            translation_text = translator.translate(transcription_text, dest=target_language_code).text.strip()
            st.session_state.last_translation = translation_text
            st.session_state.last_language_label = target_language_label
            st.session_state.last_language_code = target_language_code

    except Exception as e:
        st.error(f"An error occurred: {e}")

    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ----------------------------
# Persisted display (survives reruns)
# ----------------------------
if st.session_state.has_results:
    st.write("### Transcription Result (English)")

    st.markdown(
        f"""
        <div style="
            background-color: #1f2933;
            padding: 1rem;
            border-radius: 0.5rem;
            color: #e5e7eb;
            line-height: 1.6;
            white-space: pre-wrap;
            user-select: text;
        ">
        {st.session_state.last_transcription}
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        st.download_button(
            "⬇️ Download",
            data=st.session_state.last_transcription.encode("utf-8"),
            file_name="transcription.txt",
            mime="text/plain; charset=utf-8",
            key="dl_transcription",
            use_container_width=True,
        )
    with c2:
        if st.button("🔊 Listen", key="listen_transcription", use_container_width=True):
            speak_text(st.session_state.last_transcription, "en", "transcription")

    if st.session_state.translation_error:
        st.error(f"Translation failed: {st.session_state.translation_error}")

    if st.session_state.last_translation:
        st.write(f"### Translated Transcription ({st.session_state.last_language_label})")

        st.markdown(
            f"""
            <div style="
                background-color: #1f2933;
                padding: 1rem;
                border-radius: 0.5rem;
                color: #e5e7eb;
                line-height: 1.6;
                white-space: pre-wrap;
                user-select: text;
            ">
            {st.session_state.last_translation}
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            st.download_button(
                "⬇️ Download",
                data=st.session_state.last_translation.encode("utf-8"),
                file_name=f"translation_{st.session_state.last_language_label or 'unknown'}.txt",
                mime="text/plain; charset=utf-8",
                key="dl_translation",
                use_container_width=True,
            )
        with c2:
            if st.button("🔊 Listen", key="listen_translation", use_container_width=True):
                tts_lang = tts_lang_from_googletrans_code(st.session_state.last_language_code)
                speak_text(st.session_state.last_translation, tts_lang, "translation")