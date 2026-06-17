import { useCallback, useEffect, useRef, useState } from 'react';
import { buildChatSocketUrl, serializeApprovalDecision, serializePrompt } from '../api/chatSocket';
import type { MessageBlock, StreamEvent } from '../api/types';
import {
  markApprovalDecision,
  reduceStreamEvent,
  userMessageBlock,
} from '../state/messageBlocks';
import { statusForEvent } from '../state/status';

type ReadyState = 'idle' | 'connecting' | 'open' | 'closed';

type BlockSnapshot = {
  blocks: MessageBlock[];
  sessionId: string | null;
};

type ConnectionSnapshot = {
  banner: StreamEvent | null;
  readyState: ReadyState;
  sessionId: string | null;
  status: string;
};

export function useChatSocket(sessionId: string | null) {
  const socketRef = useRef<WebSocket | null>(null);
  const [blockSnapshot, setBlockSnapshot] = useState<BlockSnapshot>({
    blocks: [],
    sessionId: null,
  });
  const [connectionSnapshot, setConnectionSnapshot] = useState<ConnectionSnapshot>({
    banner: null,
    readyState: 'idle',
    sessionId: null,
    status: '未连接',
  });

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    const socket = new WebSocket(buildChatSocketUrl(sessionId));
    socketRef.current = socket;

    socket.onopen = () => {
      setConnectionSnapshot({
        banner: null,
        readyState: 'open',
        sessionId,
        status: '已连接',
      });
    };

    socket.onmessage = event => {
      let payload: StreamEvent;
      try {
        payload = JSON.parse(event.data) as StreamEvent;
      } catch {
        payload = { type: 'error', content: '无法解析服务端消息' };
      }

      if (payload.type === 'banner') {
        setConnectionSnapshot({
          banner: payload,
          readyState: 'open',
          sessionId,
          status: statusForEvent(payload),
        });
      } else {
        setConnectionSnapshot(current => ({
          banner: current.sessionId === sessionId ? current.banner : null,
          readyState: 'open',
          sessionId,
          status: statusForEvent(payload),
        }));
      }
      setBlockSnapshot(current => {
        const blocks = current.sessionId === sessionId ? current.blocks : [];
        return {
          blocks: reduceStreamEvent(blocks, payload),
          sessionId,
        };
      });
    };

    socket.onclose = () => {
      if (socketRef.current === socket) {
        setConnectionSnapshot(current => ({
          banner: current.sessionId === sessionId ? current.banner : null,
          readyState: 'closed',
          sessionId,
          status: '已断开',
        }));
      }
    };

    return () => {
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
      socket.close();
    };
  }, [sessionId]);

  const sendPrompt = useCallback((content: string) => {
    const trimmed = content.trim();
    const socket = socketRef.current;
    if (!sessionId || !trimmed || !socket || socket.readyState !== WebSocket.OPEN) {
      return false;
    }
    setBlockSnapshot(current => {
      const blocks = current.sessionId === sessionId ? current.blocks : [];
      return {
        blocks: [...blocks, userMessageBlock(trimmed, blocks)],
        sessionId,
      };
    });
    setConnectionSnapshot(current => ({
      banner: current.sessionId === sessionId ? current.banner : null,
      readyState: 'open',
      sessionId,
      status: '等待回复...',
    }));
    socket.send(serializePrompt(trimmed));
    return true;
  }, [sessionId]);

  const sendApprovalDecision = useCallback(
    (approvalId: string, decision: 'approve' | 'reject') => {
      const socket = socketRef.current;
      if (!sessionId || !socket || socket.readyState !== WebSocket.OPEN) {
        return false;
      }
      setBlockSnapshot(current => {
        const blocks = current.sessionId === sessionId ? current.blocks : [];
        return {
          blocks: markApprovalDecision(blocks, approvalId, decision),
          sessionId,
        };
      });
      socket.send(serializeApprovalDecision(approvalId, decision));
      setConnectionSnapshot(current => ({
        banner: current.sessionId === sessionId ? current.banner : null,
        readyState: 'open',
        sessionId,
        status: decision === 'approve' ? '已批准，继续执行...' : '已拒绝',
      }));
      return true;
    },
    [sessionId],
  );

  const clearBlocks = useCallback(() => {
    if (!sessionId) {
      return;
    }
    setBlockSnapshot({
      blocks: [],
      sessionId,
    });
    setConnectionSnapshot(current => ({
      banner: current.sessionId === sessionId ? current.banner : null,
      readyState: current.sessionId === sessionId ? current.readyState : 'idle',
      sessionId,
      status: '已清空',
    }));
  }, [sessionId]);

  const connection =
    connectionSnapshot.sessionId === sessionId
      ? connectionSnapshot
      : {
          banner: null,
          readyState: sessionId ? ('connecting' as const) : ('idle' as const),
          sessionId,
          status: sessionId ? '连接中...' : '未连接',
        };

  return {
    banner: connection.banner,
    blocks: blockSnapshot.sessionId === sessionId ? blockSnapshot.blocks : [],
    clearBlocks,
    readyState: connection.readyState,
    sendApprovalDecision,
    sendPrompt,
    status: connection.status,
  };
}
