import os
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from googletrans import Translator
from whisper import load_model, transcribe

import io
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
if "translation_error" not in st.session_state:
    st.session_state.translation_error = ""
if "last_language_code" not in st.session_state:
    st.session_state.last_language_code = None

# These are the widget values (so we don't fight Streamlit with `value=...`)
st.session_state.setdefault("transcription_area", "")
st.session_state.setdefault("translation_area", "")

def create_output_folder(audio_file_name: str) -> str:
    folder_name = os.path.splitext(os.path.basename(audio_file_name))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = os.path.join(results_folder, f"{folder_name}_{timestamp}")
    os.makedirs(output_folder, exist_ok=True)
    return output_folder


def save_translation(output_folder: str, language_label: str, translation_text: str):
    translations_folder = os.path.join(output_folder, "Translations")
    os.makedirs(translations_folder, exist_ok=True)
    translation_file = os.path.join(translations_folder, f"{language_label}_translation.txt")
    with open(translation_file, "w", encoding="utf-8") as f:
        f.write(translation_text)


def copy_button_html(text: str, button_label: str, element_id: str):
    safe_text = json.dumps(text)

    html = f"""
    <div style="margin: 0.4rem 0 1.2rem 0;">
      <button
        id="{element_id}"
        style="
          border: 1px solid rgba(34,197,94,0.6);
          background: rgba(34,197,94,0.08);
          color: rgb(134,239,172);
          padding: 0.45rem 0.95rem;
          border-radius: 0.55rem;
          cursor: pointer;
          font-size: 0.95rem;
          transition: background 0.2s ease, transform 0.05s ease;
        "
        onmouseover="this.style.background='rgba(34,197,94,0.18)'"
        onmouseout="this.style.background='rgba(34,197,94,0.08)'"
      >
        {button_label}
      </button>

      <span
        id="{element_id}_msg"
        style="
          margin-left: 0.7rem;
          color: rgb(74,222,128);
          font-weight: 500;
          opacity: 0;
          transition: opacity 0.15s ease;
        "
      ></span>

      <script>
        (function() {{
          const btn = document.getElementById("{element_id}");
          const msg = document.getElementById("{element_id}_msg");
          const textToCopy = {safe_text};

          if (!btn) return;

          btn.addEventListener("click", async () => {{
            try {{
              await navigator.clipboard.writeText(textToCopy);
              msg.textContent = "Copied!";
              msg.style.opacity = 1;
              setTimeout(() => msg.style.opacity = 0, 1300);
            }} catch (e) {{
              try {{
                const ta = document.createElement("textarea");
                ta.value = textToCopy;
                ta.style.position = "fixed";
                ta.style.left = "-9999px";
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);

                msg.textContent = "Copied!";
                msg.style.opacity = 1;
                setTimeout(() => msg.style.opacity = 0, 1300);
              }} catch (e2) {{
                msg.textContent = "Press ⌘+C";
                msg.style.opacity = 1;
                setTimeout(() => msg.style.opacity = 0, 1600);
              }}
            }}
          }});
        }})();
      </script>
    </div>
    """
    components.html(html, height=58)


def tts_lang_from_googletrans_code(code: str | None) -> str:
    """
    Map our translation codes (googletrans-style) to gTTS language codes.
    gTTS doesn't support every locale the same way.
    """
    if not code:
        return "en"

    c = code.lower()

    # Chinese: gTTS generally uses "zh" (and may not like zh-cn/zh-tw)
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

        st.audio(audio_bytes, format="audio/mpeg")

    except Exception as e:
        st.error(f"Text-to-speech failed ({label}): {e}")

def retranslate_from_state():
    """
    Called when the language dropdown changes.
    Re-translate using the existing transcription (no Whisper call).
    """
    st.session_state.translation_error = ""

    label = st.session_state.target_language_label
    code = LANG_OPTIONS.get(label)

    # If we haven't transcribed yet, nothing to translate.
    if not st.session_state.has_results or not st.session_state.last_transcription.strip():
        st.session_state.last_translation = ""
        st.session_state.last_language_label = ""
        return

    # If user chose None -> clear translation
    if code is None:
        st.session_state.last_translation = ""
        st.session_state.last_language_label = ""
        st.session_state.translation_area = ""   # <-- ADD THIS
        return

    try:
        transcription_text = st.session_state.last_transcription.strip()
        translation_text = translator.translate(transcription_text, dest=code).text.strip()

        # Save to the existing output folder from the last transcription run
        output_folder = st.session_state.last_output_folder or results_folder
        save_translation(output_folder, label, translation_text)

        st.session_state.last_translation = translation_text
        st.session_state.last_language_label = label
        st.session_state.last_language_code = code
        st.session_state.translation_area = translation_text  # <-- ADD THIS

    except Exception as e:
        st.session_state.last_translation = ""
        st.session_state.last_language_label = ""
        st.session_state.translation_error = str(e)
        st.session_state.translation_area = ""  # <-- ADD THIS


# Language dropdown with on_change callback (THIS is the fix)
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

        # Persist results
        st.session_state.last_transcription = transcription_text
        st.session_state.transcription_area = transcription_text  # <-- ADD THIS
        st.session_state.last_output_folder = output_folder
        st.session_state.has_results = True

        # Reset translation
        st.session_state.last_translation = ""
        st.session_state.last_language_label = ""
        st.session_state.translation_error = ""
        st.session_state.translation_area = ""  # <-- ADD THIS

        # Translate immediately based on current dropdown selection
        if target_language_code is not None and transcription_text:
            translation_text = translator.translate(transcription_text, dest=target_language_code).text.strip()
            save_translation(output_folder, target_language_label, translation_text)

            st.session_state.last_translation = translation_text
            st.session_state.last_language_label = target_language_label
            st.session_state.last_language_code = target_language_code
            st.session_state.translation_area = translation_text  # <-- ADD THIS

    except Exception as e:
        st.error(f"An error occurred: {e}")


# ----------------------------
# Persisted display (survives reruns)
# ----------------------------
if st.session_state.has_results:
    st.write("### Transcription Result (English)")
    # keep widget state in sync with our stored result
    st.session_state["transcription_area"] = st.session_state.last_transcription
    st.text_area(
        "Transcription (English)",
        key="transcription_area",
        height=140,
        disabled=True,
    )
    copy_button_html(
        st.session_state.last_transcription,
        "Copy Transcription",
        element_id="copy_transcription_btn",
    )

    st.download_button(
        "Download Transcription (.txt)",
        data=st.session_state.last_transcription,
        file_name="transcription.txt",
        mime="text/plain",
    )

    if st.button("🔊 Read Transcription"):
        speak_text(
            st.session_state.last_transcription,
            "en",
            "transcription",
        )

    if st.session_state.translation_error:
        st.error(f"Translation failed: {st.session_state.translation_error}")

    if st.session_state.last_translation:
        st.write(f"### Translated Transcription ({st.session_state.last_language_label})")
        # keep widget state in sync with our stored result
        st.session_state["translation_area"] = st.session_state.last_translation

        st.text_area(
            f"Translation ({st.session_state.last_language_label})",
            key="translation_area",
            height=140,
            disabled=True,
        )
        copy_button_html(
            st.session_state.last_translation,
            "Copy Translation",
            element_id="copy_translation_btn",
        )

        st.download_button(
            "Download Translation (.txt)",
            data=st.session_state.last_translation,
            file_name=f"translation_{st.session_state.last_language_label or 'unknown'}.txt",
            mime="text/plain",
        )
        
        if st.button("🔊 Read Translation"):
            tts_lang = tts_lang_from_googletrans_code(
                st.session_state.last_language_code
            )
            speak_text(
                st.session_state.last_translation,
                tts_lang,
                "translation",
            )