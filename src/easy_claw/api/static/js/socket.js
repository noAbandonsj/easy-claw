export function buildWsUrl(resumeSessionId) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    let url = protocol + '//' + location.host + '/ws/chat';
    if (resumeSessionId) {
        url += '?session_id=' + encodeURIComponent(resumeSessionId);
    }
    return url;
}

export function connectChat({ resumeSessionId, onOpen, onClose, onMessage }) {
    const socket = new WebSocket(buildWsUrl(resumeSessionId));
    socket.onopen = onOpen;
    socket.onclose = onClose;
    socket.onmessage = event => {
        onMessage(JSON.parse(event.data));
    };
    return socket;
}

export function disconnectChat(socket) {
    if (socket && socket.readyState !== WebSocket.CLOSED) {
        socket.close();
    }
}
