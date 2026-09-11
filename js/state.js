export const state = {
    // Audio & Lip-sync queue
    audioQueue: [],
    isPlaying: false,
    isStreaming: false,
    pendingSubtitle: null,
    currentEmotion: 'neutral',
    audioContext: null,
    websocket: null,
    voiceModeActive: false,
    seamlessMode: false
};
