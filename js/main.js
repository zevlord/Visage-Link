import { initDebugConsole } from './debug.js';
import { initWebSocket, sendMessage, initSpeechRecognition } from './network.js';
import { sendOscBlendShape, triggerEmotion, resetAllEmotions } from './vseeface_control.js';
import { initAudioContext } from './viseme.js';

// 1. Setup logs
initDebugConsole();

// 2. Initialize WebSocket to backend (chat)
initWebSocket();

// Wake AudioContext on first user interaction to bypass browser autoplay restrictions
['click', 'keydown', 'touchstart'].forEach(evt => {
    document.addEventListener(evt, () => initAudioContext(), { passive: true });
});

// 3. Wire up UI buttons to VSeeFace via OSC
document.getElementById('btn-happy').addEventListener('click', () => triggerEmotion('happy'));
document.getElementById('btn-angry').addEventListener('click', () => triggerEmotion('angry'));
document.getElementById('btn-blink').addEventListener('click', () => triggerEmotion('blink'));
document.getElementById('btn-talk').addEventListener('click', () => triggerEmotion('aa'));
document.getElementById('btn-reset').addEventListener('click', () => resetAllEmotions());

// 4. Chat input
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
sendBtn.addEventListener('click', () => {
    sendMessage(chatInput.value);
    chatInput.value = '';
});
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendBtn.click();
    }
});

// 5. speech recognition module 
initSpeechRecognition();

// 6. Autonomous boredom toggle
const autoChatterCheckbox = document.getElementById('autonomous-mode-checkbox');
if (autoChatterCheckbox) {
    autoChatterCheckbox.addEventListener('change', (e) => {
        if (window.chatSocket && window.chatSocket.readyState === WebSocket.OPEN) {
            window.chatSocket.send(JSON.stringify({
                type: "SET_AUTONOMOUS",
                value: e.target.checked
            }));
        }
    });
}

// 5. Log ready state
console.log('[MAIN] Browser control panel ready — VSeeFace should be receiving OSC on port 39539');
console.log('[MAIN] Model rendering is handled by VSeeFace, not the browser.');
