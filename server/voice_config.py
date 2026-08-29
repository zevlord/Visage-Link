import os

# Get the base root directory (parent of this 'server' directory)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- GPT-SoVITS CONSTANTS ---
TTS_SERVER_URL = "http://127.0.0.1:9880"
REFERENCE_AUDIO_PATH = os.path.join(BASE_DIR, "voice sample", "zerotwo", "zerotwo-sample_xQT3YE4h.mp3")
PROMPT_TEXT = "今日の夕日きれいだね。私たちで見る景色はいつも特別だよ。ダーリンと一緒だから全部が素敵に見えるな。"
PROMPT_LANGUAGE = "ja"
TEXT_LANGUAGE = "ja"

# --- GPT-SoVITS SAMPLING PARAMETERS ---
# ponytail: fine-tune these to adjust pacing and emotional variation of the cloned voice
SPEED = 0.95                     # Speaking speed multiplier (1.0 = normal, 0.95 = relaxed/human-like)
TEMPERATURE = 0.8                # Randomness control (higher values increase emotional variation, lower values stabilize tone)
TOP_K = 15                       # Limits sampling to top K tokens (reduces output slurs/glitches)
TOP_P = 1                      # Nucleus sampling threshold (retains diverse vocab options)
