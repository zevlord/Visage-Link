import { state } from './state.js';
import { sendOscBlendShape, sendOscBlendShapesBatch, sendOscApply, resetAllEmotions, triggerEmotion } from './vseeface_control.js';

export const visemeValues = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };

let activeLoopId = null;
let activeSource = null;
let frameCount = 0; // For throttled logging

export function resetVisemes() {
    Object.keys(visemeValues).forEach(k => { visemeValues[k] = 0; });
}

export function initAudioContext() {
    if (!state.audioContext) {
        state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (state.audioContext.state === 'suspended') {
        state.audioContext.resume();
    }
}

export function playNextAudio() {
    console.log(`[ASR] playNextAudio called. Queue size: ${state.audioQueue.length}`);
    if (state.audioQueue.length === 0) {
        state.isPlaying = false;
        activeLoopId = null; // Reset loop token
        resetVisemes();
        
        // If still streaming subsequent sentence chunks from backend, do not reset speaking state/emotions yet
        if (state.isStreaming) {
            console.log("[ASR] Audio queue idle but stream still active. Waiting for next chunk.");
            return;
        }

        // Reset emotions back to Neutral
        resetAllEmotions();
        sendOscBlendShapesBatch({ 'A': 0, 'I': 0, 'U': 0, 'E': 0, 'O': 0 });

        // Reset voice button label
        const voiceBtn = document.getElementById('voice-btn');
        if (voiceBtn && state.voiceModeActive) {
            voiceBtn.innerText = "Voice Mode";
            voiceBtn.style.color = "#aaa";
            voiceBtn.style.background = "#333";
        }

        // Notify server that Zero Two stopped speaking
        if (state.websocket && state.websocket.readyState === WebSocket.OPEN) {
            state.websocket.send(JSON.stringify({ type: "SPEAKING", value: false }));
        }

        // Alert the network listener that audio has finished
        if (window.onTtsFinished) {
            window.onTtsFinished();
        }
        return;
    }

    // If starting a new queue playback, notify server that Zero Two is speaking
    if (!state.isPlaying) {
        if (state.websocket && state.websocket.readyState === WebSocket.OPEN) {
            state.websocket.send(JSON.stringify({ type: "SPEAKING", value: true }));
        }
        // Update voice mode button style to show Zero Two is currently speaking
        const voiceBtn = document.getElementById('voice-btn');
        if (voiceBtn && state.voiceModeActive) {
            voiceBtn.innerText = "Zero Two Speaking...";
            voiceBtn.style.color = "#ffffff";
            voiceBtn.style.background = "#28a745"; // Green indicator
        }
    }

    state.isPlaying = true;
    const audioData = state.audioQueue.shift();

    const loopId = Math.random();
    activeLoopId = loopId;

    initAudioContext();
    if (state.audioContext.state === 'suspended') {
        state.audioContext.resume();
    }

    state.audioContext.decodeAudioData(audioData, (buffer) => {
        console.log("[ASR] Audio decoded successfully. Starting playback.");
        const source = state.audioContext.createBufferSource();
        activeSource = source;
        source.buffer = buffer;

        const analyser = state.audioContext.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        analyser.connect(state.audioContext.destination);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        source.start(0);

        // Activate subtitle at the exact millisecond voice audio starts playing
        if (state.pendingSubtitle) {
            const chatLog = document.getElementById('chat-log');
            if (chatLog) chatLog.innerText = "Vtuber: " + state.pendingSubtitle;
            if (state.websocket && state.websocket.readyState === WebSocket.OPEN) {
                state.websocket.send(JSON.stringify({ type: "SHOW_SUBTITLE", value: state.pendingSubtitle }));
            }
            state.pendingSubtitle = null;
        }

        // Trigger facial expression at the exact millisecond the audio starts playing
        if (state.currentEmotion) {
            triggerEmotion(state.currentEmotion);
        }

        function updateLipSync() {
            if (loopId !== activeLoopId) {
                console.log(`[ASR] Terminated stale lip-sync loop. loopId: ${loopId}, active: ${activeLoopId}`);
                return;
            }
            if (!state.isPlaying) return;
            
            // Use time domain data (amplitude/waveform)
            analyser.getByteTimeDomainData(dataArray);

            let totalDeviation = 0;
            for (let i = 0; i < dataArray.length; i++) {
                totalDeviation += Math.abs(dataArray[i] - 128);
            }
            const averageDeviation = totalDeviation / dataArray.length;

            // Speech signal amplitude is typically 2.0 - 25.0 deviation in 8-bit time domain
            // Apply boost so mouth opens noticeably (0.35 to 1.0)
            const volume = averageDeviation / 18.0;
            const scale = Math.min(Math.max(volume * 1.8, 0.0), 1.0);

            // Log volume metrics every 15 frames (~250ms)
            frameCount++;
            if (frameCount % 15 === 0) {
                console.log(`[ASR] LipSync Active. Deviation: ${averageDeviation.toFixed(1)}, Scale: ${scale.toFixed(2)}`);
            }

            // Simple procedurally simulated vowels
            const time = performance.now() / 1000.0;
            const shapeSelector = Math.floor(time * 5) % 3;

            resetVisemes();
            if (scale > 0.05) {
                if (shapeSelector === 0) {
                    visemeValues.aa = scale * 1.0;
                    visemeValues.ih = scale * 0.2;
                } else if (shapeSelector === 1) {
                    visemeValues.ee = scale * 0.9;
                    visemeValues.ih = scale * 0.4;
                } else {
                    visemeValues.ou = scale * 0.8;
                    visemeValues.oh = scale * 0.5;
                }
            }

            // Send ONE batch OSC message for the standard VRM0 vowels
            sendOscBlendShapesBatch({
                'A': visemeValues.aa,
                'I': visemeValues.ih,
                'U': visemeValues.ou,
                'E': visemeValues.ee,
                'O': visemeValues.oh
            });

            requestAnimationFrame(updateLipSync);
        }

        updateLipSync();

        source.onended = () => {
            if (activeSource === source) {
                activeSource = null;
            }
            resetVisemes();
            sendOscBlendShapesBatch({ 'A': 0, 'I': 0, 'U': 0, 'E': 0, 'O': 0 });
            playNextAudio();
        };
    }, (e) => {
        console.error("Error decoding audio data:", e);
        playNextAudio();
    });
}

export function stopTtsPlayback() {
    state.audioQueue = []; // Clear current queue
    state.isPlaying = false;
    activeLoopId = null;   // Kill lip sync loop
    resetVisemes();
    resetAllEmotions();
    sendOscBlendShapesBatch({ 'A': 0, 'I': 0, 'U': 0, 'E': 0, 'O': 0 });
    
    if (activeSource) {
        try {
            activeSource.stop();
        } catch(e) {}
        activeSource = null;
    }
    
    // Notify server that Zero Two is no longer speaking
    if (state.websocket && state.websocket.readyState === WebSocket.OPEN) {
        state.websocket.send(JSON.stringify({ type: "SPEAKING", value: false }));
    }
}
