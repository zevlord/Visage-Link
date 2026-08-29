export function addDebugLog(msg, color = '#00ff00') {
    const debugList = document.getElementById('debug-log-list');
    if (!debugList) return;
    const div = document.createElement('div');
    div.style.color = color;
    div.style.marginBottom = '4px';
    div.innerText = msg;
    debugList.appendChild(div);
    debugList.scrollTop = debugList.scrollHeight;
}

export function initDebugConsole() {
    const oldLog = console.log;
    console.log = function(...args) {
        oldLog.apply(console, args);
        addDebugLog(args.join(' '));
    };

    const oldError = console.error;
    console.error = function(...args) {
        oldError.apply(console, args);
        addDebugLog(args.join(' '), '#ff4444');
    };

    window.addEventListener('error', (e) => {
        addDebugLog(`Unhandled Error: ${e.message} at ${e.filename}:${e.lineno}`, '#ff4444');
    });

    window.addEventListener('unhandledrejection', (e) => {
        addDebugLog(`Unhandled Promise Rejection: ${e.reason}`, '#ff4444');
    });
}
