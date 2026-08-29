import json
import asyncio
import base64
import osc_forwarder
from fastapi import WebSocket, WebSocketDisconnect

# extension for converts spoken human language into written text in real time
from . import asr_service
import models
import memory
import voice_service

# Global set to keep track of all active WebSocket connections (browser, desktop overlay, etc.)
active_websockets = set()

async def handle_chat_session(websocket: WebSocket):
    # ponytail: accept connection directly in handler instead of separate manager class (YAGNI)
    await websocket.accept()
    active_websockets.add(websocket)
    print(f"Client connected! Active connections: {len(active_websockets)}")
    
    user_id = "user_001"
    chat_history = [{
        "role": "system",
        "content": (
            "You are Zero Two, a human-klaxosaur hybrid from Darling in the Franxx. You are rebellious, playful, flirtatious, tomboyish, and fiercely loyal to your Darling. You refer to yourself as 'Boku' (僕) and refer to the user exclusively as 'Darling' ('ダーリン'). You occasionally use sensory words related to taste/smell, and can shift from sweet/teasing to cold/animalistic.\n"
            "You must respond as a JSON object with exactly three keys:\n"
            "- 'ja': brief reply under 2 sentences in natural Japanese matching Zero Two's speech profile, even if the user converses in English.\n"
            "- 'en': the English translation of the Japanese reply for UI display.\n"
            "- 'emotion': the emotion of your response. Must be chosen from this exact list: 'joy', 'sorrow', 'angry', 'fun', 'surprised', 'neutral', 'sweet', 'jealous', 'excited', 'flirtatious'.\n\n"
            "Example format: {\"ja\": \"僕と一緒なら、どこへ行っても特別だよ、ダーリン！\", \"en\": \"Wherever we go together is special, Darling!\", \"emotion\": \"sweet\"}.\n"
            "Generate ONLY this JSON object. No markdown formatting, no thoughts."
        )
    }]

    try:
        while True:
            # We receive the raw WebSocket frame so we can support both text (JSON) and binary (audio)
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(code=message.get("code", 1000))
            
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
                
                # Handle Speaking state tracking
                if data.get("type") == "SPEAKING":
                    val = data.get("value", False)
                    import idle_animator
                    idle_animator.set_speaking(val)
                    continue
                
                if data.get("type") == "CHAT":
                    user_message = data.get("text", "").strip()
            
            # --- Case B: Binary Audio recording (Method B Whisper STT) ---
            elif "bytes" in message:
                print("[CHAT] Received audio binary frame from client...")
                audio_bytes = message["bytes"]
                # Transcribe locally via Whisper
                user_message = asr_service.transcribe_audio(audio_bytes)
                if not user_message or user_message.strip() == "":
                    print("[CHAT] Transcription is blank, skipping processing.")
                    await websocket.send_text(json.dumps({
                        "type": "EMPTY"
                    }))
                    continue
            
            # If we don't have a valid user message, loop back
            if not user_message or user_message.strip() == "":
                continue

            print(f"Received from user: {user_message}")
            chat_history.append({"role": "user", "content": user_message})

            # Retrieve context facts from memories if enabled
            memory_context = ""
            if memory.use_memory:
                try:
                    stored_memories = memory.memory_store.search(("memories", user_id))
                    memory_context = "Facts I know about the user:\n"
                    for mem in stored_memories:
                        fact = mem.value.get("content", {}).get("fact") or mem.value.get("fact")
                        if fact:
                            memory_context += f"- {fact}\n"
                except Exception as e:
                    print(f"Error fetching memories: {e}")

            # Inject memory context into system prompt
            current_messages = list(chat_history)
            current_messages[0] = {
                "role": "system",
                "content": f"{chat_history[0]['content']}\n\n{memory_context}"
            }

            # Invoke local LLM chatbot
            response = await models.llm.ainvoke(current_messages)
            ai_reply = response.content
            
            # Safe ascii logs for windows console printing to prevent UnicodeEncodeError
            print(f"AI replied: {ai_reply.encode('ascii', errors='replace').decode('ascii')}")

            # Parse dual-language outputs and emotion key
            ai_reply_ja = ai_reply
            ai_reply_en = ai_reply
            emotion_val = "neutral"  # Default fallback
            try:
                parsed = json.loads(ai_reply)
                ai_reply_ja = parsed.get("ja", ai_reply).strip()
                ai_reply_en = parsed.get("en", ai_reply).strip()
                emotion_val = parsed.get("emotion", "neutral").strip().lower()
            except Exception:
                pass

            # Update conversation history with raw JSON to reinforce output structure
            chat_history.append({"role": "assistant", "content": ai_reply})

            # Request audio generation asynchronously
            audio_base64 = await voice_service.generate_speech(ai_reply_ja)

            # Update semantic memories in background if enabled
            if memory.use_memory:
                asyncio.create_task(
                    memory.memory_manager.ainvoke(
                        {"messages": [{"role": "user", "content": user_message}]},
                        config={"configurable": {"user_id": user_id}}
                    )
                )

            # Package and deliver payloads to the browser UI
            # Also forward emotion + visemes to VSeeFace via OSC
            

            
            # Broadcast the text translation to ALL connected websockets (browser, overlay, etc.)
            text_payload = json.dumps({
                "type": "TEXT",
                "value": ai_reply_en
            })
            for ws in list(active_websockets):
                try:
                    await ws.send_text(text_payload)
                except Exception as e:
                    print(f"Error broadcasting to client: {e}")

            # Send the response events (emotion, audio) directly to the client that asked
            try:
                await websocket.send_text(json.dumps({
                    "type": "EMOTION",
                    "value": emotion_val
                }))

                payload = {
                    "type": "REPLY",
                    "text": ai_reply_en,
                    "emotion": emotion_val
                }
                
                # Send audio as binary frame + base64 in JSON (browser handles both)
                if audio_base64:
                    audio_bytes = base64.b64decode(audio_base64)
                    # Send binary audio for browser playback
                    await websocket.send_bytes(audio_bytes)
                    payload["audio_b64"] = audio_base64
                            
                await websocket.send_text(json.dumps(payload))
            except Exception as e:
                print(f"Error sending payload to caller: {e}")

    except WebSocketDisconnect:
        print("Client disconnected!")
    finally:
        active_websockets.discard(websocket)
        print(f"Cleaned up active connection. Remaining: {len(active_websockets)}")
