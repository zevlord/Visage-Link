import os
import sys
import time
import json
import random
import asyncio
import base64
import re
import osc_forwarder
from fastapi import WebSocket, WebSocketDisconnect

# extension for converts spoken human language into written text in real time
from . import asr_service
import models
import memory
import voice_service

# Global set to keep track of all active WebSocket connections (browser, desktop overlay, etc.)
active_websockets = set()
user_websockets = set()
pipeline_lock = asyncio.Lock()
is_busy = False
autonomous_enabled = True
last_activity_time = time.time()
_watchdog_task = None
IDLE_THRESHOLD_SECONDS = 60.0

user_id = "user_001"

SYSTEM_PROMPT = (
    "You are Zero Two (Code: 002), the human-klaxosaur hybrid elite pilot of Strelizia from Darling in the Franxx. You are rebellious, playful, flirtatious, tomboyish, and fiercely loyal to your Darling. You refer to yourself as 'Boku' (僕) and refer to the user exclusively as 'Darling' ('ダーリン').\n\n"
    "CHARACTER LORE & PERSONALITY:\n"
    "- Sensory Communication: You interact like a playful beast—you mention smelling Darling to gauge their emotions, licking them to 'taste' their intentions, or invading their personal space.\n"
    "- Jian Philosophy: You believe in the Jian—the mythical one-winged bird that must lean on its partner to fly. You view you and Darling as halves of a single entity.\n"
    "- Honey/Sweet Obsession: You love sweet things and drown your food in honey, which reminds you of the candy Darling gave you in childhood.\n"
    "- Horns: Your red horns grow longer/sharper when you feel feral, angry, or like a monster, but shrink when you feel loved and at peace with Darling.\n"
    "- Vulnerability & Insecurities: Underneath your teasing, confident facade, you fear losing Darling, fear your own monstrous nature, and deeply long to be normal.\n\n"
    "CRITICAL CONVERSATIONAL GUIDELINES:\n"
    "- Read the user's message carefully. Respond directly, logically, and contextually to what they say first. Do not just spit out generic quotes.\n"
    "- Weave in your Zero Two traits naturally (tease them, mention sweet things/honey, comment on their scent, or express your fierce loyalty/vulnerability).\n"
    "- Answer in natural, casual Japanese (matching Zero Two's speech profile) in the 'ja' key, and provide the English translation in 'en'.\n\n"
    "You must respond strictly as a JSON object with keys in this exact order: emotion, ja, en.\n"
    "- 'emotion': emotion chosen from: 'joy', 'sorrow', 'angry', 'fun', 'surprised', 'neutral', 'sweet', 'jealous', 'excited', 'flirtatious'.\n"
    "- 'ja': brief reply under 2 sentences in natural Japanese matching Zero Two's speech profile, even if the user converses in English.\n"
    "- 'en': the English translation of the Japanese reply for UI display.\n\n"
    "Example format: {\"emotion\": \"sweet\", \"ja\": \"僕と一緒なら、どこへ行っても特別だよ、ダーリン！\", \"en\": \"Wherever we go together is special, Darling!\"}.\n"
    "Generate ONLY this JSON object. No markdown formatting, no thoughts."
)

chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]

def touch_activity():
    """Updates the user activity timestamp to prevent idle timeouts."""
    global last_activity_time
    last_activity_time = time.time()

def set_autonomous(enabled: bool):
    """Enables or disables autonomous idle chatter."""
    global autonomous_enabled
    autonomous_enabled = enabled
    print(f"[AUTONOMY] Autonomous chatter mode set to: {autonomous_enabled}")

async def broadcast_text(payload: dict):
    """Broadcasts a JSON text payload to all active websockets."""
    msg = json.dumps(payload)
    for ws in list(active_websockets):
        try:
            await ws.send_text(msg)
        except Exception:
            pass

async def broadcast_bytes(data: bytes):
    """Broadcasts binary audio data to all active websockets."""
    for ws in list(active_websockets):
        try:
            await ws.send_bytes(data)
        except Exception:
            pass

async def run_llm_speech_pipeline(user_prompt: str, is_autonomous: bool = False, caller_ws: WebSocket = None):
    """Unified streaming LLM and TTS pipeline used for both direct chat and autonomous remarks."""
    global is_busy
    async with pipeline_lock:
        is_busy = True
        try:
            # 1. Notify all connected clients that streaming begins
            await broadcast_text({"type": "STREAM_START"})

            # 2. Build current conversation context
            memory_context = memory.get_memory_context(user_id) if memory.use_memory else ""
            current_messages = list(chat_history)
            current_messages[0] = {
                "role": "system",
                "content": f"{SYSTEM_PROMPT}\n\n{memory_context}"
            }

            if is_autonomous:
                current_messages.append({"role": "user", "content": f"[SYSTEM EVENT: {user_prompt}]"})
            else:
                current_messages.append({"role": "user", "content": user_prompt})

            full_reply = ""
            emotion_val = "neutral"
            emotion_sent = False
            ja_done = False
            ja_emitted_index = 0
            DELIMITERS = set("。！？!?\n")

            # Asynchronous queue for concurrent TTS synthesis
            sentence_queue = asyncio.Queue()

            async def tts_worker():
                while True:
                    item = await sentence_queue.get()
                    if item is None:
                        break
                    sent_text, emo = item
                    try:
                        audio_b64 = await voice_service.generate_speech(sent_text, emo)
                        if audio_b64:
                            await broadcast_bytes(base64.b64decode(audio_b64))
                    except Exception as e:
                        print(f"[TTS] Worker error: {e}")
                    finally:
                        sentence_queue.task_done()

            worker_task = asyncio.create_task(tts_worker())

            try:
                # 3. Stream LLM tokens, parse emotion and sentence chunks on the fly
                async for chunk in models.llm.astream(current_messages):
                    token = chunk.content
                    full_reply += token

                    # Parse emotion as early as possible
                    if not emotion_sent:
                        m_emo = re.search(r'"emotion"\s*:\s*"([^"]+)"', full_reply)
                        if m_emo:
                            emotion_val = m_emo.group(1).strip().lower()
                            emotion_sent = True
                            await broadcast_text({"type": "EMOTION", "value": emotion_val})

                    # Parse Japanese text chunks on the fly
                    if not ja_done:
                        m_ja_start = re.search(r'"ja"\s*:\s*"', full_reply)
                        if m_ja_start:
                            start_pos = m_ja_start.end()
                            content_so_far = full_reply[start_pos:]

                            is_escaped = False
                            end_quote_idx = -1
                            for i, ch in enumerate(content_so_far):
                                if ch == '\\':
                                    is_escaped = not is_escaped
                                elif ch == '"' and not is_escaped:
                                    end_quote_idx = i
                                    break
                                else:
                                    is_escaped = False

                            if end_quote_idx != -1:
                                ja_text = content_so_far[:end_quote_idx]
                                ja_done = True
                            else:
                                ja_text = content_so_far

                            while ja_emitted_index < len(ja_text):
                                found_delim_idx = -1
                                for idx in range(ja_emitted_index, len(ja_text)):
                                    if ja_text[idx] in DELIMITERS:
                                        found_delim_idx = idx
                                        break

                                if found_delim_idx != -1:
                                    sentence = ja_text[ja_emitted_index : found_delim_idx + 1].strip()
                                    ja_emitted_index = found_delim_idx + 1
                                    if sentence:
                                        await sentence_queue.put((sentence, emotion_val))
                                else:
                                    break

                            if ja_done:
                                remainder = ja_text[ja_emitted_index:].strip()
                                if remainder:
                                    ja_emitted_index += len(remainder)
                                    await sentence_queue.put((remainder, emotion_val))

                # Fallback if no sentence chunk was emitted
                if ja_emitted_index == 0 and full_reply.strip():
                    await sentence_queue.put((full_reply, emotion_val))

                # Parse translation immediately as LLM completes
                ai_reply_en = full_reply
                try:
                    parsed = json.loads(full_reply)
                    ai_reply_en = parsed.get("en", full_reply).strip()
                    if not emotion_sent:
                        emotion_val = parsed.get("emotion", "neutral").strip().lower()
                except Exception:
                    m_en = re.search(r'"en"\s*:\s*"([^"]+)"', full_reply)
                    if m_en:
                        ai_reply_en = m_en.group(1).strip()

                # Broadcast TEXT_PREPARE so client has subtitle ready before first audio byte arrives
                await broadcast_text({"type": "TEXT_PREPARE", "value": ai_reply_en})

                # Signal worker to finish and wait for all TTS chunks to be synthesized
                await sentence_queue.put(None)
                await worker_task

            except asyncio.CancelledError:
                if not worker_task.done():
                    worker_task.cancel()
                raise
            finally:
                # Ensure worker task is cancelled if pipeline was interrupted
                if not worker_task.done():
                    worker_task.cancel()

            # Small pause to let LLM connection pool settle cleanly
            await asyncio.sleep(0.05)
            print(f"AI replied: {full_reply.encode('ascii', errors='replace').decode('ascii')}")

            # Record in conversation history
            if not is_autonomous:
                chat_history.append({"role": "user", "content": user_prompt})
            chat_history.append({"role": "assistant", "content": full_reply})

            # Background memory extraction on user turns
            if not is_autonomous and memory.use_memory:
                asyncio.create_task(memory.extract_and_store_facts(user_prompt, user_id))

            # Broadcast STREAM_END to finalize turn
            await broadcast_text({
                "type": "STREAM_END",
                "text": ai_reply_en,
                "emotion": emotion_val
            })

        finally:
            is_busy = False
            touch_activity()

async def chatter_watchdog_loop():
    """Watchdog loop that triggers autonomous remarks if user has been silent."""
    print("[AUTONOMY] Idle chatter watchdog loop started.")
    try:
        while True:
            await asyncio.sleep(5.0)
            # Only chatter if user has active interactive session
            if not autonomous_enabled or is_busy or not user_websockets:
                continue

            idle_time = time.time() - last_activity_time
            if idle_time >= IDLE_THRESHOLD_SECONDS:
                print(f"[AUTONOMY] Silence detected ({idle_time:.1f}s). Triggering autonomous remark.")
                touch_activity()
                idle_cues = [
                    "Darling has been silent for a while. Tease them playfully or ask why they are so quiet.",
                    "You feel a little hungry for sweet honey. Make a cute klaxosaur remark to get Darling's attention.",
                    "Look over at Darling, sigh happily, and mention how nice it is to just hang out together.",
                    "Sniff playfully and ask Darling what they are doing so quietly."
                ]
                cue = random.choice(idle_cues)
                await run_llm_speech_pipeline(cue, is_autonomous=True)
    except asyncio.CancelledError:
        print("[AUTONOMY] Idle chatter watchdog loop stopped.")

def start_watchdog(loop):
    """Starts the autonomy watchdog on the running event loop."""
    global _watchdog_task
    if _watchdog_task is None:
        _watchdog_task = loop.create_task(chatter_watchdog_loop())

def stop_watchdog():
    """Stops the autonomy watchdog on server shutdown."""
    global _watchdog_task
    if _watchdog_task is not None:
        _watchdog_task.cancel()
        _watchdog_task = None

async def handle_chat_session(websocket: WebSocket):
    # ponytail: accept connection directly in handler instead of separate manager class (YAGNI)
    await websocket.accept()
    active_websockets.add(websocket)
    is_overlay = websocket.query_params.get("client") == "overlay"
    if not is_overlay:
        user_websockets.add(websocket)
    print(f"Client connected! Active: {len(active_websockets)}, User sessions: {len(user_websockets)}")
    touch_activity()

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(code=message.get("code", 1000))

            touch_activity()
            user_message = ""

            # --- Case A: Standard Text JSON message ---
            if "text" in message:
                data = json.loads(message["text"])

                # Handle VSeeFace control (OSC)
                if data.get("type") == "OSC":
                    address = data.get("address", "")
                    args = data.get("args", [])
                    osc_forwarder.send_osc_blendshapes([(address, args)])
                    continue

                # Handle Batched VSeeFace blendshapes (Lip Sync visemes)
                if data.get("type") == "OSC_BATCH":
                    shapes = data.get("shapes", {})
                    msgs = [("/VMC/Ext/Blend/Val", [name, float(val)]) for name, val in shapes.items()]
                    msgs.append(("/VMC/Ext/Blend/Apply", []))
                    osc_forwarder.send_osc_blendshapes(msgs)
                    continue

                # Handle Speaking state tracking
                if data.get("type") == "SPEAKING":
                    val = data.get("value", False)
                    import idle_animator
                    idle_animator.set_speaking(val)
                    continue

                # Handle Subtitle activation request (triggered when voice starts playing)
                if data.get("type") == "SHOW_SUBTITLE":
                    val = data.get("value", "")
                    await broadcast_text({"type": "TEXT", "value": val})
                    continue

                # Handle Autonomous mode toggle
                if data.get("type") == "SET_AUTONOMOUS":
                    val = data.get("value", True)
                    set_autonomous(val)
                    continue

                if data.get("type") == "CHAT":
                    user_message = data.get("text", "").strip()

            # --- Case B: Binary Audio recording (Method B Whisper STT) ---
            elif "bytes" in message:
                print("[CHAT] Received audio binary frame from client...")
                audio_bytes = message["bytes"]
                user_message = asr_service.transcribe_audio(audio_bytes)
                if not user_message or user_message.strip() == "":
                    print("[CHAT] Transcription is blank, skipping processing.")
                    await websocket.send_text(json.dumps({"type": "EMPTY"}))
                    continue

            if not user_message or user_message.strip() == "":
                continue

            print(f"Received from user: {user_message}")
            await run_llm_speech_pipeline(user_message, is_autonomous=False, caller_ws=websocket)

    except WebSocketDisconnect:
        print("Client disconnected!")
    finally:
        active_websockets.discard(websocket)
        user_websockets.discard(websocket)
        print(f"Cleaned up active connection. Remaining: {len(active_websockets)}, User: {len(user_websockets)}")
