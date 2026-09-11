import { state } from './state.js';
import { sendOscBlendShape, sendOscApply, resetAllEmotions, triggerEmotion } from './vseeface_control.js';

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
            
            // Use time domain data (amplitude/waveform) instead of frequency data
            // Speech energy is concentrated in a tiny fraction of frequency bins, 
            // causing frequency averages to register near 0.
            analyser.getByteTimeDomainData(dataArray);

            let totalDeviation = 0;
            for (let i = 0; i < dataArray.length; i++) {
                // Time domain values range from 0 to 255, with silence centered at 128.
                totalDeviation += Math.abs(dataArray[i] - 128);
            }
            const averageDeviation = totalDeviation / dataArray.length;

            const volume = averageDeviation / 128.0; // Max deviation is 128
            const scale = Math.min(volume * 5.0, 1.0);  // Boost scale for expressive mouth shapes

            // Log volume metrics every 10 frames (~160ms) to ensure visibility on short sentences
            frameCount++;
            if (frameCount % 10 === 0) {
                console.log(`[ASR] LipSync Active. Volume Deviation: ${averageDeviation.toFixed(1)}, Scale: ${scale.toFixed(2)}`);
            }

            // Simple procedurally simulated vowels
            const time = performance.now() / 1000.0;
            const shapeSelector = Math.floor(time * 4) % 3;

            resetVisemes();
            if (shapeSelector === 0) {
                visemeValues.aa = scale * 0.9;
                visemeValues.ih = scale * 0.2;
            } else if (shapeSelector === 1) {
                visemeValues.ee = scale * 0.8;
                visemeValues.ih = scale * 0.4;
            } else {
                visemeValues.ou = scale * 0.7;
                visemeValues.oh = scale * 0.3;
            }

            // Send visemes to VSeeFace via OSC (supports VRM0, VRM1, and custom name styles)
            // 1. VRM0 standard uppercase
            sendOscBlendShape('A', visemeValues.aa);
            sendOscBlendShape('I', visemeValues.ih);
            sendOscBlendShape('U', visemeValues.ou);
            sendOscBlendShape('E', visemeValues.ee);
            sendOscBlendShape('O', visemeValues.oh);
            
            // 2. VRM1 standard lowercase
            sendOscBlendShape('aa', visemeValues.aa);
            sendOscBlendShape('ih', visemeValues.ih);
            sendOscBlendShape('ou', visemeValues.ou);
            sendOscBlendShape('ee', visemeValues.ee);
            sendOscBlendShape('oh', visemeValues.oh);

            // 3. Lowercase single letters fallback
            sendOscBlendShape('a', visemeValues.aa);
            sendOscBlendShape('i', visemeValues.ih);
            sendOscBlendShape('u', visemeValues.ou);
            sendOscBlendShape('e', visemeValues.ee);
            sendOscBlendShape('o', visemeValues.oh);

            sendOscApply();

            requestAnimationFrame(updateLipSync);
        }

        updateLipSync();

        source.onended = () => {
            if (activeSource === source) {
                activeSource = null;
            }
            resetVisemes();
            
            // Reset VRM0
            sendOscBlendShape('A', 0);
            sendOscBlendShape('I', 0);
            sendOscBlendShape('U', 0);
            sendOscBlendShape('E', 0);
            sendOscBlendShape('O', 0);

            // Reset VRM1
            sendOscBlendShape('aa', 0);
            sendOscBlendShape('ih', 0);
            sendOscBlendShape('ou', 0);
            sendOscBlendShape('ee', 0);
            sendOscBlendShape('oh', 0);

            // Reset lowercase fallbacks
            sendOscBlendShape('a', 0);
            sendOscBlendShape('i', 0);
            sendOscBlendShape('u', 0);
            sendOscBlendShape('e', 0);
            sendOscBlendShape('o', 0);

            sendOscApply();
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
