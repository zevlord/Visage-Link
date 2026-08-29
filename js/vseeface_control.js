///
// VSeeFace control module — sends OSC messages to VSeeFace's VMC receiver.
// This replaces the browser-based Three.js VRM rendering with OSC control of VSeeFace,
// which handles all avatar rendering, lip sync, hair physics, and idle animations.
//
// OSC target: localhost:39540 (VSeeFace VMC Protocol Receiver)
// BlendShape mapping: matches VRM0 preset names that VSeeFace recognizes.

import { state } from './state.js';

export function sendOscMessage(address, args) {
    if (state.websocket && state.websocket.readyState === WebSocket.OPEN) {
        const payload = JSON.stringify({ type: 'OSC', address, args });
        state.websocket.send(payload);
    } else {
        console.warn('[OSC] WebSocket not connected, cannot send:', address);
    }
}


// VRM0 → VSeeFace blendshape names
const emotionPresets = {
    happy: 'Joy',
    sad: 'Sorrow',
    angry: 'Angry',
    relaxed: 'Fun',
    surprised: 'Surprised',
    blink: 'Blink',
    neutral: 'Neutral',
    // Visemes for lip sync
    aa: 'A',
    ih: 'I',
    ou: 'U',
    ee: 'E',
    oh: 'O'
};

export function sendOscBlendShape(name, value) {
    // Commented out high-frequency log to prevent UI lagging (runs at 60fps)
    // console.log(`[VS] BlendShape: ${name} = ${value}`);
    sendOscMessage('/VMC/Ext/Blend/Val', [name, value]);
}

const emotionRecipes = {
    neutral: [['Neutral', 1.0]],
    joy: [['Neutral', 0.3], ['Joy', 0.65]],
    sorrow: [['Neutral', 0.3], ['Sorrow', 0.65]],
    angry: [['Neutral', 0.2], ['Angry', 0.7]],
    fun: [['Neutral', 0.3], ['Fun', 0.65]],
    surprised: [['Neutral', 0.2], ['Surprised', 0.7]],
    sweet: [['Neutral', 0.6], ['Joy', 0.35]],
    jealous: [['Neutral', 0.3], ['Angry', 0.35], ['Sorrow', 0.25]],
    excited: [['Neutral', 0.2], ['Joy', 0.45], ['Extra', 0.7]],
    flirtatious: [['Neutral', 0.3], ['Joy', 0.4], ['Fun', 0.3]]
};

export function triggerEmotion(emotionName) {
    const name = (emotionName || 'neutral').toLowerCase();
    const recipe = emotionRecipes[name] || emotionRecipes['neutral'];
    console.log(`[VS] Triggering emotion recipe: ${name}`);

    // Clear all emotions not used in this recipe to prevent lingering expressions
    const activeShapes = new Set(recipe.map(item => item[0]));
    const allEmotions = ["Joy", "Sorrow", "Angry", "Fun", "Surprised", "Extra"];
    
    allEmotions.forEach(shape => {
        if (!activeShapes.has(shape)) {
            sendOscBlendShape(shape, 0);
        }
    });

    // Apply recipe shapes
    recipe.forEach(([shape, value]) => {
        sendOscBlendShape(shape, value);
    });

    sendOscApply();
}

export function resetAllEmotions() {
    console.log('[VS] Resetting all blendshapes');
    Object.values(emotionPresets).forEach(name => {
        sendOscBlendShape(name, 0);
    });
    sendOscBlendShape('Neutral', 1.0);
    sendOscApply();
}

export function sendOscApply() {
    sendOscMessage('/VMC/Ext/Blend/Apply', []);
}

// Initialize on module load
console.log('[VS] Control module loaded. Target: 127.0.0.1:39539 (via Python OSC bridge)');
