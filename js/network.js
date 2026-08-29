import { state } from './state.js';
import { playNextAudio, initAudioContext, stopTtsPlayback } from './viseme.js';

const chatLog = document.getElementById('chat-log');
const inputField = document.getElementById('chat-input');

export function initWebSocket() {
    state.websocket = new WebSocket("ws://127.0.0.1:8000/ws/chat");
    state.websocket.binaryType = "arraybuffer";

    state.websocket.onopen = () => {
        console.log("Connected to Python backend!");
        chatLog.innerText = "System: Connected to backend. VSeeFace control ready.";

        // Expose socket to other modules for OSC forwarding
        window.chatSocket = state.websocket;
    };

    state.websocket.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
            // Receive TTS audios
            state.audioQueue.push(event.data);
            if (!state.isPlaying) {
                playNextAudio();
            }
        } else {
            // Text logs
            const data = JSON.parse(event.data);
            
            if (data.type === "EMPTY") {
                console.log("[ASR] Transcription was blank. Skipping LLM call and resetting voice loop.");
                updateVoiceStatus("Voice Mode", "#aaa", "#333");
                // Reset states
                state.voiceModeActive = document.getElementById('seamless-mode-checkbox')?.checked || false;
                if (window.onTtsFinished) {
                    window.onTtsFinished();
                }
                return;
            }
            
            chatLog.innerText = "Vtuber: " + (data.text || data.value || '');
            
            // Extract and store incoming emotion
            if (data.type === "REPLY" && data.emotion) {
                state.currentEmotion = data.emotion;
            }
        }
    };

    state.websocket.onerror = (error) => {
        console.error("WebSocket error:", error);
        chatLog.innerText = "System: Connection error. Retry in 5s.";
    };

    state.websocket.onclose = () => {
        console.log("WebSocket disconnected. Reconnecting...");
        chatLog.innerText = "System: Disconnected. Retrying...";
        setTimeout(initWebSocket, 5000);
    };
}

export function sendMessage() {
    initAudioContext();
    const message = inputField.value;
    if (message.trim() !== "" && state.websocket.readyState === WebSocket.OPEN) {
        const payload = JSON.stringify({ type: "CHAT", text: message }); // Set type: CHAT explicitly
        state.websocket.send(payload);
        chatLog.innerText = "You: " + message;
        inputField.value = "";
    }
}

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let vadAnimationFrame = null;

// the ui for voice update (connected to index html)
function updateVoiceStatus(text, color = '#aaa', bg = '#333') {
    const statusBtn = document.getElementById('voice-btn');
    if (statusBtn) {
        statusBtn.innerText = text;
        statusBtn.style.color = color;
        statusBtn.style.background = bg;
    }
}

// triggers voice capture recording with automatic Web Audio VAD silence cutoff
let captureStream = null;
async function triggerVoiceCapture() {
    if (state.isPlaying || !state.voiceModeActive) return;
    isRecording = true;
    audioChunks = [];
    updateVoiceStatus("Listening... (Speak now)", "#ffffff", "#ff4444");

    try {
        captureStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(captureStream);

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            if (state.websocket && state.websocket.readyState === WebSocket.OPEN) {
                updateVoiceStatus("Processing speech...", "#ffffff", "#e0a800");
                state.websocket.send(audioBlob);
            } else {
                updateVoiceStatus("Voice Mode", "#aaa", "#333");
            }
            if (!state.seamlessMode) {
                state.voiceModeActive = false;
            }
            captureStream.getTracks().forEach(track => track.stop());
        };
        mediaRecorder.start();

        // Web Audio Voice Activity Detection (VAD)
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioCtx.createMediaStreamSource(captureStream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        let lastSpeakTime = Date.now();
        
        function checkVolume() {
            if (!isRecording) {
                try { audioCtx.close(); } catch (e) {}
                return;
            }
            analyser.getByteTimeDomainData(dataArray);
            let totalDeviation = 0;
            for (let i = 0; i < dataArray.length; i++) {
                totalDeviation += Math.abs(dataArray[i] - 128);
            }
            const averageDeviation = totalDeviation / dataArray.length;
            const volume = averageDeviation / 128.0;

            // Simple volume threshold (0.015 is default, handles ambient noise well)
            if (volume > 0.015) {
                lastSpeakTime = Date.now();
            }

            // If user has been silent for 1.8 seconds, automatically submit audio
            if (Date.now() - lastSpeakTime > 1800) {
                console.log("[VAD] Silence detected. Stopping capture.");
                isRecording = false;
                updateVoiceStatus(state.voiceModeActive && state.seamlessMode ? "Processing speech..." : "Voice Mode", "#ffffff", "#e0a800");
                if (mediaRecorder && mediaRecorder.state === "recording") {
                    mediaRecorder.stop();
                }
                try { audioCtx.close(); } catch (e) {}
                return;
            }

            vadAnimationFrame = requestAnimationFrame(checkVolume);
        }

        checkVolume();

    } catch (err) {
        console.error("[MIC] Voice capture error:", err);
        isRecording = false;
        updateVoiceStatus("Mic Error", "#ff4444", "#333");
    }
}

export function toggleVoiceCapture() {
    initAudioContext();
    
    // If Zero Two is currently speaking, clicking the button interrupts playback and turns off loop
    if (state.isPlaying) {
        state.voiceModeActive = false;
        isRecording = false;
        stopTtsPlayback();
        updateVoiceStatus("Voice Mode", "#aaa", "#333");
        return;
    }

    if (state.seamlessMode) {
        if (state.voiceModeActive) {
            // Deactivate seamless loop
            state.voiceModeActive = false;
            isRecording = false;
            updateVoiceStatus("Voice Mode", "#aaa", "#333");
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.stop();
            }
        } else {
            // Activate seamless loop
            state.voiceModeActive = true;
            triggerVoiceCapture();
        }
    } else {
        // Manual click-to-talk mode
        if (isRecording) {
            isRecording = false;
            state.voiceModeActive = false;
            updateVoiceStatus("Voice Mode", "#aaa", "#333");
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.stop();
            }
        } else {
            state.voiceModeActive = true; // Enable temporarily for this recording
            triggerVoiceCapture();
        }
    }
}

// initialize speech recognition engine and button click listeners
export function initSpeechRecognition() {
    const voiceBtn = document.getElementById('voice-btn');
    if (voiceBtn) {
        voiceBtn.addEventListener('click', toggleVoiceCapture);
    }

    const seamlessCheckbox = document.getElementById('seamless-mode-checkbox');
    if (seamlessCheckbox) {
        state.seamlessMode = seamlessCheckbox.checked;
        seamlessCheckbox.addEventListener('change', (e) => {
            state.seamlessMode = e.target.checked;
            console.log("[Voice Mode] Seamless Mode toggled to:", state.seamlessMode);
            // If they disable seamless mode during active loop, turn off the loop
            if (!state.seamlessMode && state.voiceModeActive) {
                state.voiceModeActive = false;
                isRecording = false;
                updateVoiceStatus("Voice Mode", "#aaa", "#333");
                if (mediaRecorder && mediaRecorder.state === "recording") {
                    mediaRecorder.stop();
                }
            }
        });
    }

    window.onTtsFinished = () => {
        if (state.voiceModeActive && state.seamlessMode) {
            console.log("[PLAYBACK] Finished Speaking. Restarting voice capture loop.");
            triggerVoiceCapture();
        }
    };

    updateVoiceStatus("Voice Mode", "#aaa", "#333");
}


