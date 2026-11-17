# Visage Link

A local-first, real-time AI avatar system. Visage Link connects a conversational LLM, a local voice-cloning model, and a 3D VRM avatar renderer into a single low-latency pipeline — and animates the avatar programmatically, without a webcam.

The project targets a single consumer GPU with 8 GB of VRAM. Rather than running everything locally at full size, it splits the workload: voice synthesis and avatar rendering stay on the GPU, while LLM inference runs on a lean local model or is delegated to a hosted endpoint. Every architectural decision in this repository comes out of that constraint.

---

## Architecture

```
Browser control panel (index.html, js/)
        │  WebSocket / JSON
        ▼
FastAPI backend (:8000)  ── server/
   ├── chat_handler.py    streaming LLM pipeline, sentence chunker, autonomous chatter
   ├── memory.py          dual-source retrieval memory (SQLite + embeddings)
   ├── voice_service.py   GPT-SoVITS TTS client
   ├── asr_service.py     Faster-Whisper speech-to-text
   ├── idle_animator.py   procedural gaze, breathing, posture
   ├── osc_forwarder.py   VMC/OSC over UDP → :39539
   └── desktop_overlay.py Win32 subtitle overlay
        │
        ├──► VSeeFace        VRM avatar rendering, blendshapes, spring bones
        ├──► GPT-SoVITS      local voice cloning (HTTP :9880)
        ├──► Ollama          LLM inference (OpenAI-compatible, :11434)
        └──► Ollama          nomic-embed-text embeddings for memory
```

---

## Core engineering

### Streaming generation with parallel speech synthesis

A conventional request/response loop is unusable for spoken interaction: the user waits for the full text, then the full audio, then playback begins. Visage Link streams the LLM response token by token (`astream`), splits the output at sentence boundaries, and pushes each completed sentence onto an `asyncio.Queue` consumed by a separate TTS worker. Synthesis of sentence *n+1* overlaps with playback of sentence *n*, so the first words reach the user in a fraction of the time a full-response pipeline would take.

### Dual-source retrieval memory without a vector database

Long-term context is handled in-process rather than with an external vector store, which would compete for the same limited VRAM:

- **Embeddings** — `nomic-embed-text` (768-dimensional) served by the local Ollama instance.
- **Storage** — vectors are stored as raw binary BLOBs (`ndarray.tobytes()`) in SQLite tables `knowledge_chunks` and `user_facts`. No Chroma, no FAISS, no server to keep alive.
- **Retrieval** — one query embedding per turn, scanned concurrently against canonical character knowledge and episodic user facts via NumPy cosine similarity, each with its own top-k and relevance threshold. Matches are injected into the system prompt as separate context blocks.
- **Learning** — a background task extracts durable facts from user messages and indexes them without blocking the response.

### Procedural animation engine

No face tracking is required. `idle_animator.py` generates bone rotations mathematically and broadcasts them over VMC:

- **Gaze** — a random Euler target is held for 2.0–4.5 s, then re-rolled. Yaw ±0.16 rad, pitch −0.08 to +0.05 rad, roll ±0.04 rad.
- **Interpolation** — lerp toward the target (`0.06` per tick) clamped to a maximum angular speed of `0.18` rad/s, which prevents visible snapping when the target changes.
- **Breathing** — non-harmonic sine overlay on three axes (`sin(t·1.1)`, `sin(t·1.5)`, `cos(t·0.8)`) so the loop never repeats mechanically.
- **Posture** — static anti-T-pose rotations on the upper arms, converted from Euler to Unity-compatible quaternions in YXZ order.

See [`ANIMATION_SYSTEM.md`](ANIMATION_SYSTEM.md) for the formulas and tuning parameters.

### VMC/OSC bridge

Avatar state is transmitted with the VMC protocol over UDP loopback, so the renderer stays a completely separate process:

```
/VMC/Ext/Blend/Val  <blendshape name> <value>
/VMC/Ext/Blend/Apply
```

Emotions detected in the model's structured output are mapped to VRM0 blendshapes (`Joy`, `Angry`, `Sorrow`, `Fun`, `Surprised`, `Blink`, `A`, `I`, `U`, `E`, `O`) and forwarded alongside the audio response.

### Autonomous idle behaviour

A backend watchdog detects silence beyond a configurable threshold and triggers a spontaneous in-character utterance, interrupted immediately by any user input. This keeps the avatar present rather than inert during pauses.

---

## Requirements

- Windows 10/11
- Python 3.10+
- [Ollama](https://ollama.com/) with a chat model (default: `qwen2.5`) and `nomic-embed-text`
- [VSeeFace](https://www.vseeface.icu/) with VMC protocol reception enabled
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) for local voice cloning (optional — text-only mode works without it)

```bash
pip install -r requirements.txt
```

---

## Quick start

1. **Start the LLM and embedding server**

   ```bash
   ollama serve
   ollama pull qwen2.5
   ollama pull nomic-embed-text
   ```

2. **Configure VSeeFace** — load your own `.vrm` model, open *Settings → General → OSC / VMC Protocol*, enable **Receive motion data via VMC protocol**, and set the port to `39539`.

3. **Run the backend**

   ```bash
   python -m uvicorn server:app --host 127.0.0.1 --port 8000
   ```

   On Windows, `start_vtuber.bat` launches the voice server, the backend, and the subtitle overlay in one step.

4. **Open the control panel** at <http://127.0.0.1:8000/>.

---

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | — | Only needed if you switch `server/models.py` to a hosted endpoint |

Model, TTS endpoint, and voice parameters live in `server/models.py` and `server/voice_config.py`.

Persona, lore, and reference voice are local assets and are **not** included in this repository. To run your own character:

- Place a VRM0 model in `Models/`.
- Replace `server/knowledge/zerotwo_lore.md` with your own knowledge file, or remove it to run without retrieval.
- Adjust the system prompt in `server/chat_handler.py` and the reference audio in `server/voice_config.py`.

---

## Project structure

```
index.html                 control panel
css/, js/                  WebSocket client, OSC translation, viseme code
server/
  server.py                FastAPI app, static mounts, /ws/chat
  chat_handler.py          streaming pipeline, sentence chunking, watchdog
  memory.py                SQLite retrieval memory
  voice_service.py         GPT-SoVITS client
  voice_config.py          voice parameters
  asr_service.py           Faster-Whisper transcription
  idle_animator.py         procedural animation
  osc_forwarder.py         UDP VMC sender
  desktop_overlay.py       Win32 subtitle overlay
  models.py                LLM client configuration
  knowledge/               retrieval source documents
tests/                     import, OSC, mouth-shape, and pipeline tests
```

---

## Tests

```bash
python tests/test_imports.py            # module integrity
python tests/test_osc.py                # VMC packet delivery
python tests/test_stream_pipeline.py    # sentence chunking and TTS queueing
```

---

## Notes

This is a personal engineering exercise in latency and resource budgeting on constrained hardware, not a packaged product. The bundled sample persona is a placeholder demonstrating the retrieval and animation pipeline; character models, cloned voices, and lore belong to their respective rights holders and are deliberately excluded from this repository.

## License

MIT — see [LICENSE](LICENSE).
