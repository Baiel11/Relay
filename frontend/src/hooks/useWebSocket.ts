import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '../stores/useAuthStore';
import { useChatStore } from '../stores/useChatStore';
import { websocketService } from '../services/websocket.service';
import { authService } from '../services/auth.service';
import type { Message } from '../types/chat.types';

let isDispatcherInitialized = false;
const typingSafetyTimers: Record<string, any> = {};

function initGlobalFrameDispatcher() {
  if (isDispatcherInitialized) return;
  isDispatcherInitialized = true;

  websocketService.setTokenProvider(async () => {
    const currentToken = useAuthStore.getState().accessToken;
    if (currentToken) return currentToken;
    try {
      const data = await authService.refreshToken();
      if (data?.access_token) {
        useAuthStore.getState().setAccessToken(data.access_token);
        return data.access_token;
      }
    } catch {
      // ignore
    }
    return null;
  });

  websocketService.addFrameHandler((frame: any) => {
    const store = useChatStore.getState();

    // A. Incoming Message Broadcast
    if (frame.type === 'message' && frame.data) {
      const msg: Message = frame.data;
      store.addMessage(msg.conversation_id, msg);

      // If message is from partner and current chat is open, immediately mark as read
      const currentUserId = useAuthStore.getState().user?.id;
      if (
        store.activeConversation?.id === msg.conversation_id &&
        msg.sender_id !== currentUserId
      ) {
        websocketService.markRead(msg.conversation_id);
      }
    }

    // B. ACK frame for Sender
    if (frame.type === 'ack' && frame.data?.message) {
      const msg: Message = frame.data.message;
      store.addMessage(msg.conversation_id, msg);
    }

    // C. Individual Presence Status Broadcast
    if (frame.type === 'presence' && frame.data) {
      store.setUserOnline(frame.data.user_id, frame.data.status === 'online');
    }

    // D. Initial snapshot of all currently online users
    if (frame.type === 'presence_sync' && Array.isArray(frame.data?.online_user_ids)) {
      store.setOnlineUsers(frame.data.online_user_ids);
    }

    // E. Partner presence on conversation subscribe
    if (frame.type === 'subscribed' && typeof frame.partner_online === 'boolean') {
      const active = store.activeConversation;
      if (active?.other_user?.id) {
        store.setUserOnline(active.other_user.id, frame.partner_online);
      }
    }

    // F. Typing Indicator Broadcast
    if (frame.type === 'typing' && frame.data) {
      const convId = frame.data.conversation_id;
      const isTyping = Boolean(frame.data.is_typing);
      store.setTyping(convId, isTyping);

      if (typingSafetyTimers[convId]) {
        clearTimeout(typingSafetyTimers[convId]);
      }
      if (isTyping) {
        // Auto-clear after 3.5 seconds in case partner stops without blur
        typingSafetyTimers[convId] = setTimeout(() => {
          useChatStore.getState().setTyping(convId, false);
        }, 3500);
      }
    }

    // G. Unread Badge Counter Update
    if (frame.type === 'unread_update' && frame.data) {
      store.updateUnreadCount(frame.data.conversation_id, frame.data.unread_count);
    }

    // H. Read Receipt Broadcast
    if (frame.type === 'read_receipt' && frame.data) {
      store.markMessagesRead(
        frame.data.conversation_id,
        frame.data.reader_id,
        frame.data.last_read_at
      );
    }
  });
}

export const useWebSocket = () => {
  const typingTimerRef = useRef<any>(null);
  const accessToken = useAuthStore((state) => state.accessToken);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const activeConversationId = useChatStore((state) => state.activeConversation?.id);

  // Initialize singleton frame handler once
  useEffect(() => {
    initGlobalFrameDispatcher();
  }, []);

  // 1. Establish or disconnect WebSocket based on authentication state
  useEffect(() => {
    if (isAuthenticated && accessToken) {
      websocketService.connect(accessToken);
    } else if (!isAuthenticated) {
      websocketService.disconnect();
    }
  }, [isAuthenticated, accessToken]);

  // 2. When active conversation changes, send subscribe and mark_read
  useEffect(() => {
    if (activeConversationId) {
      websocketService.subscribeConversation(activeConversationId);
      websocketService.markRead(activeConversationId);
    }
  }, [activeConversationId]);

  const sendTypingWS = useCallback((conversationId: string, isTyping: boolean) => {
    websocketService.sendTyping(conversationId, isTyping);
  }, []);

  const sendMessageWS = useCallback((conversationId: string, content: string): boolean => {
    const sent = websocketService.sendMessage(conversationId, content);
    if (sent) {
      websocketService.sendTyping(conversationId, false);
    }
    return sent;
  }, []);

  const handleUserTypingInput = useCallback((conversationId: string) => {
    websocketService.sendTyping(conversationId, true);

    if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
    typingTimerRef.current = setTimeout(() => {
      websocketService.sendTyping(conversationId, false);
    }, 2000);
  }, []);

  const markReadWS = useCallback((conversationId: string) => {
    websocketService.markRead(conversationId);
  }, []);

  return {
    sendMessageWS,
    sendTypingWS,
    handleUserTypingInput,
    markReadWS,
    disconnectWS: () => websocketService.disconnect(),
  };
};
