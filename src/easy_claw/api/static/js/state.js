export const state = {
    ws: null,
    currentAssistant: null,
    currentAssistantRaw: '',
    modelName: '',
    workspace: '',
    version: '',
    sessionId: '',
    turnCount: 0,
    totalTokens: {},
    sessions: [],
};

export function resetConversationState() {
    state.currentAssistant = null;
    state.currentAssistantRaw = '';
    state.turnCount = 0;
    state.totalTokens = {};
}
