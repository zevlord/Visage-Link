import os
import base64
import httpx
import voice_config

def format_text_for_gpt_sovits(text: str) -> str:
    # Retain punctuation for natural pauses in GPT-SoVITS V2, but split lines to prevent cutoffs
    import re
    # ponytail: simplify parsing using a clean regex match to group sentences with punctuation
    lines = re.findall(r'[^。！\?！？\n]+[。！\?！？\n]*', text)
    return "\n".join([line.strip() for line in lines if line.strip()])

async def generate_speech(text: str) -> str | None:
    # Requests audio from local GPT-SoVITS V2 endpoint with natural formatting splits
    formatted_text = format_text_for_gpt_sovits(text)
    try:
        params = {
            "ref_audio_path": os.path.abspath(voice_config.REFERENCE_AUDIO_PATH),
            "prompt_text": voice_config.PROMPT_TEXT,
            "prompt_lang": voice_config.PROMPT_LANGUAGE,
            "text": formatted_text,
            "text_lang": voice_config.TEXT_LANGUAGE,
            "speed_factor": voice_config.SPEED,
            "temperature": voice_config.TEMPERATURE,
            "top_k": voice_config.TOP_K,
            "top_p": voice_config.TOP_P
        }
        async with httpx.AsyncClient() as client:
            tts_response = await client.get(f"{voice_config.TTS_SERVER_URL}/tts", params=params, timeout=30.0)
            if tts_response.status_code == 200:
                return base64.b64encode(tts_response.content).decode("utf-8")
            print(f"Error from GPT-Sovits V2: {tts_response.status_code}")
    except Exception as e:
        print(f"Error calling TTS: {e}")
    return None
