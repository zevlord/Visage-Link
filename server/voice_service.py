import os
import base64
import httpx
import voice_config

def format_text_for_gpt_sovits(text: str) -> str:
    # Normalize English 'Darling' / 'darling' to Japanese Katakana for authentic anime pronunciation
    import re
    cleaned = re.sub(r'(?i)\bdarling\b', 'ダーリン', text)
    # Retain punctuation for natural pauses in GPT-SoVITS V2, but split lines to prevent cutoffs
    # ponytail: simplify parsing using a clean regex match to group sentences with punctuation
    lines = re.findall(r'[^。！\?！？\n]+[。！\?！？\n]*', cleaned)
    return "\n".join([line.strip() for line in lines if line.strip()])

# Base path for voice samples
VOICE_SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice sample", "zerotwo")

EMOTION_VOICE_MAP = {
    "neutral": {
        "audio": "zerotwo-sample_xQT3YE4h.wav",
        "prompt": "君の能力は多分まだ眠っているだけだよ。僕なら引き出してあげられる。君は僕のつのを見ても怖がらなかったね。"
    },
    "joy": {
        "audio": "zerotwo-sample_xQT3YE4h.wav",  # Fallback from broken laugh sample
        "prompt": "君の能力は多分まだ眠っているだけだよ。僕なら引き出してあげられる。君は僕のつのを見ても怖がらなかったね。"
    },
    "fun": {
        "audio": "zerotwo-sample_xQT3YE4h.wav",  # Fallback from broken laugh sample
        "prompt": "君の能力は多分まだ眠っているだけだよ。僕なら引き出してあげられる。君は僕のつのを見ても怖がらなかったね。"
    },
    "excited": {
        "audio": "ZT Excited vocals.mp3",
        "prompt": "君を味合わせて、今から君が僕のダーリンだ！"
    },
    "surprised": {
        "audio": "ZT Excited vocals.mp3",
        "prompt": "君を味合わせて、今から君が僕のダーリンだ！"
    },
    "sorrow": {
        "audio": "zerotwo-sample_xQT3YE4h.wav",  # Fallback from broken cry sample
        "prompt": "君の能力は多分まだ眠っているだけだよ。僕なら引き出してあげられる。君は僕のつのを見ても怖がらなかったね。"
    },
    "flirtatious": {
        "audio": "zerotwo-sample_xQT3YE4h.wav",
        "prompt": "君の能力は多分まだ眠っているだけだよ。僕なら引き出してあげられる。君は僕のつのを見ても怖がらなかったね。"
    },
    "jealous": {
        "audio": "zt annoyed.mp3",
        "prompt": "わずらしいなそういうの、ストレリチアに乗ってればわかりあえるじゃないか"
    },
    "angry": {
        "audio": "zt annoyed.mp3",
        "prompt": "わずらしいなそういうの、ストレリチアに乗ってればわかりあえるじゃないか"
    },
    "sweet": {
        "audio": "zerotwo-sample_xQT3YE4h.wav",
        "prompt": "君の能力は多分まだ眠っているだけだよ。僕なら引き出してあげられる。君は僕のつのを見ても怖がらなかったね。"
    }
}

async def generate_speech(text: str, emotion: str = "neutral") -> str | None:
    # Requests audio from local GPT-SoVITS V2 endpoint with dynamic reference mapping
    formatted_text = format_text_for_gpt_sovits(text)
    
    emotion_key = emotion.lower() if emotion else "neutral"
    config = EMOTION_VOICE_MAP.get(emotion_key, EMOTION_VOICE_MAP["neutral"])
    ref_audio_path = os.path.abspath(os.path.join(VOICE_SAMPLE_DIR, config["audio"]))
    prompt_text = config["prompt"]
    
    print(f"[TTS] Generating speech with emotion: '{emotion_key}' using reference: '{config['audio']}'")
    
    try:
        params = {
            "ref_audio_path": ref_audio_path,
            "prompt_text": prompt_text,
            "prompt_lang": voice_config.PROMPT_LANGUAGE,
            "text": formatted_text,
            "text_lang": voice_config.TEXT_LANGUAGE,
            "speed_factor": voice_config.SPEED,
            "temperature": voice_config.TEMPERATURE,
            "top_k": voice_config.TOP_K,
            "top_p": voice_config.TOP_P
        }
        async with httpx.AsyncClient() as client:
            tts_response = await client.get(f"{voice_config.TTS_SERVER_URL}/tts", params=params, timeout=90.0)
            if tts_response.status_code == 200:
                return base64.b64encode(tts_response.content).decode("utf-8")
            print(f"Error from GPT-Sovits V2: {tts_response.status_code}")
    except Exception as e:
        print(f"Error calling TTS: {e}")
    return None
