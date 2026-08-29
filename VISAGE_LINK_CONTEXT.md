# Project Visage Link — VSeeFace Integration Context

## Overview
VSeeFace + browser control panel setup for Zero Two VTuber (Darling in the Franxx) with AI chat integration via Python backend.

## Architecture
```
Browser (Control Panel) → WebSocket → Python Backend → UDP/OSC → VSeeFace → Zero Two Avatar
                                                               (renders model + animations)
```

## Project Structure
```
D:/Project ideas 2.1/
├── index.html              # Browser control panel (no 3D rendering)
├── js/
│   ├── main.js             # Button handlers → WebSocket OSC messages  
│   ├── network.js          # WebSocket connection + reconnect logic
│   ├── vseeface_control.js # Emotion → VRM0 blendshape mapping + OSC
│   ├── state.js            # Global state
│   ├── debug.js            # Console logging
│   └── [animations.js, viseme.js, loader.js, scene.js]  # OLD - unused
├── server/
│   ├── __init__.py         # makes server/ a proper Python package
│   ├── server.py           # FastAPI routes
│   ├── chat_handler.py     # WebSocket handler + OSC bridge
│   ├── osc_forwarder.py    # UDP sender to VSeeFace (port 39539)
│   ├── idle_animator.py    # Multi-frequency head sway & breathing math
│   ├── models.py           # LLM config (Ollama)
│   ├── memory.py           # LangMem semantic memory (OPTIONAL)
│   ├── voice_service.py    # GPT-SoVITS TTS
│   ├── voice_config.py     # Voice parameters
│   ├── credentials.py      # API key loading
│   └── README.txt
├── Models/
│   └── zero two.vrm        # 17MB VRM0 model
├── test_osc.py             # Integration test script
├── .venv/                  # Python 3.10 venv
└── VISAGE_LINK_CONTEXT.md  # This file
```

## Current Files (Modified for VSeeFace)

### index.html
- Stripped Three.js/VRM import map and loader
- Pure control panel with emotion buttons + chat input + debug console

### js/vseeface_control.js
- Maps emotion names to VRM0 blendshape names (VRM0 presets):
  - happy → Joy, sad → Sorrow, angry → Angry, blink → Blink
- Sends OSC messages via WebSocket to backend:
  - `/VMC/Ext/Blend/Val "Joy" 0.65` (emotion)
  - `/VMC/Ext/Blend/Apply` (apply)

### js/network.js
- WebSocket connection to `ws://127.0.0.1:8000/ws/chat`
- Added `sendOscMessage()` function for forwarding OSC commands
- Auto-reconnect on disconnect

### server/osc_forwarder.py
- UDP/OSC packet builder for VMC Protocol
- Sends to `127.0.0.1:39539` (VSeeFace VMC receiver port)
- Supports blendshape names and values

### server/chat_handler.py
- Handles both regular WebSocket messages and OSC forward requests
- OSC messages: `{"type": "OSC", "address": "/VMC/Ext/Blend/Val", "args": ["Joy", 0.75]}`
- Decodes base64 audio and sends binary audio frames

## Migration Plan: Unity → VSeeFace

### Phase 1: Browser Control Panel ✓
- [x] Remove Three.js/VRM rendering from index.html
- [x] Create vseeface_control.js for OSC messaging
- [x] Update network.js for WebSocket OSC forwarding
- [x] Strip unnecessary animations.js/viseme.js/loader.js

### Phase 2: Backend OSC Bridge ✓
- [x] Create osc_forwarder.py (UDP OSC → VSeeFace)
- [x] Update chat_handler.py to forward OSC messages
- [x] Handle base64 audio → binary WebSocket frames
- [x] Auto-forward emotions on AI responses

### Phase 3: VSeeFace Setup
- [ ] Download VSeeFace v1.13.38c5 from https://www.vseeface.icu/
- [ ] Load zero two.vrm (VRM0 format - compatible)
- [ ] Enable VMC Protocol Receiver on port 39539
- [ ] Enable "VMC receiver disables tracking" (to use webcam separately)
- [ ] Configure camera, lighting, model position

### Phase 4: Integration Testing
- [ ] Start Python backend server
- [ ] Start VSeeFace with model loaded
- [ ] Open Chrome control panel
- [ ] Test emotion buttons trigger VSeeFace blendshapes
- [ ] Test chat → AI response → lip sync + emotion

## Current Issues

### 1. Server Module Import Error (CRITICAL)
**Error**: `ERROR: Error loading ASGI app. Attribute "app" not found in module "server"`

**Root Cause**: The `server/` directory lacked `__init__.py` making it not a proper package. Even after adding `__init__.py`, uvicorn still fails because:
- Python 3.10 in venv (`C:\Users\Nikki\AppData\Local\Programs\Python\Python310`)
- Old server processes from previous sessions are still running on port 8000
- Stale `__pycache__` files with compiled Python 3.13 bytecode conflicting

**Current State**: 
- `test_imports.py` passes (imports work correctly)
- `uvicorn server:app` still fails (uvicorn's import mechanism conflicts)
- Old server on port 8000 is still responding to HTTP requests
- OSC test fails with "no close frame received" (old server doesn't have OSC code)

**Fix Attempts**:
1. ✅ Added `server/__init__.py`
2. ✅ Made `memory.py` langmem import optional (Python 3.10 incompatible)
3. ✅ Installed `langgraph`, `langmem`, `langchain_openai`
4. ✅ Cleaned `__pycache__` directory
5. ❌ Could not kill old server processes on port 8000 (different namespace/container)

**Workaround**: The old server is still running and serving HTTP 200, but it doesn't have the OSC forwarding code. Need to kill ALL old processes or use a different port.

### 2. Python Version Conflict
- venv uses Python 3.10 (installed at `C:\Users\Nikki\AppData\Local\Programs\Python\Python310`)
- But `.pyc` files for `cpython-313` exist in `__pycache__`
- `langmem` library requires Python 3.11+ for `typing.NotRequired`

**Fix**: Made langmem import optional — memory features disabled, but core functionality works.

### 3. Port 8000 Conflict
Multiple old server processes from previous sessions are still listening on port 8000. Cannot kill them from this environment (different Windows container/namespace).

## Key Technical Details

### VMC Protocol (OSC) Format
```
/VMC/Ext/Blend/Val (string){name} (float){value}
/VMC/Ext/Blend/Apply
```
BlendShape names (VRM0): Joy, Angry, Sorrow, Fun, Surprised, Blink, Blink_L, Blink_R, Neutral, A, I, U, E, O

### WebSocket Message Format
```json
// OSC forward request:
{"type": "OSC", "address": "/VMC/Ext/Blend/Val", "args": ["Joy", 0.75]}

// Chat request:
{"text": "Hello Zero Two"}
```

### Server Response Format
```json
// Three messages sent per AI response:
{"type": "TEXT", "value": "English reply"}
{"type": "EMOTION", "value": "happy"}
{"type": "REPLY", "text": "English reply", "emotion": "happy", "audio_b64": "..."}
// Plus binary audio frame (if TTS succeeded)
```

## Testing Commands

```bash
# Start server (from project root)
cd "/d/Project ideas 2.1" && source .venv/Scripts/activate
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload

# Test OSC forwarding
python test_osc.py

# Check server is running
curl http://127.0.0.1:8000/

# Check server logs
tail -f /c/Users/Nikki/AppData/Local/Temp/vtuber-server.log
```

## Environment
- Unity: 6000.0.47f1 (Project handsberry exists but NOT active)
- VSeeFace: v1.13.38c5 (needs to be downloaded/installed)
- Python: 3.10 (venv in .venv/)
- Model: zero two.vrm (VRM0, 17MB) at D:/Project ideas 2.1/Models/
- Hardware: RTX 4060 8GB VRAM
