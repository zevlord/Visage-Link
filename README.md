# Visage Link 🎭

**Visage Link** is a modular, local-first interactive 3D AI companion and expression bridge. It connects local AI cognitive models and voice synthesizers with a 3D avatar frontend, using programmatic motion calculations to bring the character to life without needing a camera feed.

Specifically optimized for mid-range GPUs (such as an RTX 4060 laptop), Visage Link uses a **hybrid architecture** that reserves local VRAM for low-latency voice synthesis and butter-smooth 3D rendering, while offloading LLM text generation either to the cloud or a highly optimized local runner.

---

## 🚀 Key Features

*   **🌀 Visage Motion Engine**: Simulates natural human breathing, gaze shifts, and posture programmatically using multi-frequency mathematical waves. No webcam is required to keep the avatar moving naturally.
*   **🎭 Live Expression Mapping**: Decodes AI emotions (e.g., joy, anger, sorrow, neutral) and forwards them directly to VSeeFace blendshapes.
*   **📡 VMC/OSC Bridge**: Communicates with VSeeFace using the industry-standard VMC (Virtual Motion Capture) protocol over a UDP loopback connection.
*   **🗣️ Local Voice Cloning**: Seamlessly integrates with **GPT-SoVITS** to synthesize natural-sounding speech in the avatar's cloned voice.
*   **🧠 Cognitive Memory**: Powered by LangMem, giving the companion long-term episodic and semantic memory retention.
*   **💻 Desktop Subtitle Overlay**: Renders real-time subtitles directly on your Windows desktop for immersive, hands-free interaction.

---

## 🏗️ Architecture

```
                                      +-----------------------------------------+
                                      |                 Browser                 |
                                      |          (Visage Link Panel)            |
                                      +--------------------+--------------------+
                                                           |
                                                (WebSocket / JSON commands)
                                                           v
                                      +--------------------+--------------------+
                                      |             Python Backend              |
                                      |           (Visage Link Core)            |
                                      +---+--------------------+------------+---+
                                          |                    |            |
                         (OSC / UDP port 39539)       (Local HTTP)   (Cloud API)
                                          |                    |            |
                                          v                    v            v
+-----------------------------------------+           +--------+-------+  +----+----+
|                VSeeFace                 |           |   GPT-SoVITS   |  | Open-   |
|         (3D Avatar VRM Rendering)       |           |  (Local TTS)   |  | Router  |
+-----------------------------------------+           +----------------+  +---------+
```

---

## 🛠️ File Structure

*   `index.html` — The main browser control dashboard.
*   `start_vtuber.bat` — One-click launcher script for Windows.
*   `js/` — WebSocket interface, network listeners, and VMC/OSC translation.
*   `server/` — FastAPI core routing, chat handlers, and utility scripts:
    *   `server.py` — Web API endpoints and routes.
    *   `chat_handler.py` — WebSocket manager routing AI prompts, emotions, and audio.
    *   `osc_forwarder.py` — UDP packet encoder translating blendshapes to VSeeFace.
    *   `idle_animator.py` — Multi-frequency mathematical sway and breathing simulator.
    *   `desktop_overlay.py` — Desktop subtitle overlay injector.
*   `Models/` — Repository for VRM0 characters (e.g., `zero_two.vrm`).

---

## 🏁 Quick Start

### 1. Prerequisites
*   Windows 10/11
*   Python 3.10+ (configured inside `.venv/`)
*   [VSeeFace](https://www.vseeface.icu/) (v1.13.38c5 recommended)
*   Conda environment `GPTSovits` configured with [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)

### 2. Configure VSeeFace
1.  Open VSeeFace and load your `.vrm` character.
2.  Go to **Settings** > **General settings**.
3.  Scroll down to **OSC / VMC Protocol** and enable **Receive motion data via VMC protocol**.
4.  Set the port to `39539`.
5.  *(Optional)* Enable **VMC receiver disables tracking** if you want to use the virtual mathematical tracking exclusively.

### 3. Run the Launcher
Simply double-click the Windows batch file:
```bash
start_vtuber.bat
```
This launcher will automatically:
1. Start the GPT-SoVITS voice cloning API server.
2. Start the FastAPI backend and web server.
3. Launch the desktop subtitle overlay.
4. Load the dashboard in your browser.

---

## 🛡️ License & Philosophy
Visage Link is open-source and local-first. We believe in providing fully customizable digital companions where you own your voice data, cognitive history, and avatar assets locally and privately.
