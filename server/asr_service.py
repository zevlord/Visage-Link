import os
import tempfile
from faster_whisper import WhisperModel

# Initialize the model on CPU with int8 quantization (fast, low memory footprint)
# Model options: "tiny", "base", "small" ("base" is recommended for speed and accuracy)
print("[ASR] Loading Whisper model...")
model = WhisperModel("base", device="cpu", compute_type="int8")
print("[ASR] Whisper model loaded successfully.")

def transcribe_audio(audio_bytes: bytes) -> str | None:
    """Saves binary audio to a temp file, transcribes it, and cleans up."""
    # 1. Create a temp file to hold the incoming browser audio
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_audio_path = temp_audio.name

    try:
        # 2. Transcribe the audio file
        segments, info = model.transcribe(temp_audio_path, beam_size=5)
        
        # Combine the text segments
        text = " ".join([segment.text for segment in segments]).strip()
        print(f"[ASR] Transcribed: '{text}' (Language: {info.language} with prob: {info.language_probability:.2f})")
        return text
    except Exception as e:
        print(f"[ASR] Transcription failed: {e}")
        return None
    finally:
        # 3. Clean up the temp file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
