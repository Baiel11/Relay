import { create } from 'zustand';
import type { Conversation, Message } from '../types/chat.types';
import { chatService } from '../services/chat.service';

interface ChatState {
  conversations: Conversation[];
  activeConversation: Conversation | null;
  messages: Record<string, Message[]>; // conversationId -> Message[]
  isTyping: Record<string, boolean>;   // conversationId -> boolean
  onlineUsers: Record<string, boolean>; // userId -> boolean
  isLoadingConversations: boolean;
  isLoadingMessages: boolean;

  setConversations: (conversations: Conversation[]) => void;
  setActiveConversation: (conversation: Conversation | null) => void;
  setMessages: (conversationId: string, messages: Message[]) => void;
  addMessage: (conversationId: string, message: Message) => void;
  setTyping: (conversationId: string, typing: boolean) => void;
  setUserOnline: (userId: string, isOnline: boolean) => void;
  setOnlineUsers: (userIds: string[]) => void;
  updateUnreadCount: (conversationId: string, count: number) => void;
  clearUnreadCount: (conversationId: string) => void;
  markMessagesRead: (conversationId: string, readerId: string, lastReadAt: string) => void;
  setIsLoadingConversations: (loading: boolean) => void;
  setIsLoadingMessages: (loading: boolean) => void;
  reset: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  activeConversation: null,
  messages: {},
  isTyping: {},
  onlineUsers: {},
  isLoadingConversations: false,
  isLoadingMessages: false,

  setConversations: (conversations) => set({ conversations }),

  setActiveConversation: (conversation) => set({ activeConversation: conversation }),

  setMessages: (conversationId, messages) =>
    set((state) => ({
      messages: { ...state.messages, [conversationId]: messages },
    })),

  addMessage: (conversationId, message) =>
    set((state) => {
      const currentMessages = state.messages[conversationId] || [];
      // Avoid duplicate client messages
      if (currentMessages.some((m) => m.id === message.id)) {
        return state;
      }

      const convExists = state.conversations.some((c) => c.id === conversationId);
      let updatedConvs = state.conversations;

      if (convExists) {
        // Move updated conversation to top of list
        const targetConv = state.conversations.find((c) => c.id === conversationId)!;
        const remaining = state.conversations.filter((c) => c.id !== conversationId);
        updatedConvs = [
          {
            ...targetConv,
            last_message: message,
          },
          ...remaining,
        ];
      } else {
        // Newly initiated conversation: fetch fresh conversation list
        chatService.getConversations().then((data) => {
          useChatStore.getState().setConversations(data.items);
        }).catch(console.error);
      }

      const updatedActive =
        state.activeConversation?.id === conversationId
          ? { ...state.activeConversation, last_message: message }
          : state.activeConversation;

      return {
        conversations: updatedConvs,
        activeConversation: updatedActive,
        messages: {
          ...state.messages,
          [conversationId]: [...currentMessages, message],
        },
      };
    }),

  setTyping: (conversationId, typing) =>
    set((state) => ({
      isTyping: { ...state.isTyping, [conversationId]: typing },
    })),

  setUserOnline: (userId, isOnline) =>
    set((state) => {
      const targetId = (userId || '').toLowerCase();
      const updatedConvs = state.conversations.map((c) => {
        if ((c.other_user?.id || '').toLowerCase() === targetId) {
          return { ...c, is_online: isOnline };
        }
        return c;
      });

      const updatedActive =
        state.activeConversation &&
        (state.activeConversation.other_user?.id || '').toLowerCase() === targetId
          ? { ...state.activeConversation, is_online: isOnline }
          : state.activeConversation;

      return {
        onlineUsers: { ...state.onlineUsers, [targetId]: isOnline },
        conversations: updatedConvs,
        activeConversation: updatedActive,
      };
    }),

  setOnlineUsers: (userIds) =>
    set((state) => {
      const onlineMap: Record<string, boolean> = { ...state.onlineUsers };
      userIds.forEach((id) => {
        onlineMap[(id || '').toLowerCase()] = true;
      });

      const updatedConvs = state.conversations.map((c) => {
        const otherId = (c.other_user?.id || '').toLowerCase();
        if (onlineMap[otherId] !== undefined) {
          return { ...c, is_online: onlineMap[otherId] };
        }
        return c;
      });

      const activeOtherId = (state.activeConversation?.other_user?.id || '').toLowerCase();
      const updatedActive =
        state.activeConversation && onlineMap[activeOtherId] !== undefined
          ? { ...state.activeConversation, is_online: onlineMap[activeOtherId] }
          : state.activeConversation;

      return {
        onlineUsers: onlineMap,
        conversations: updatedConvs,
        activeConversation: updatedActive,
      };
    }),

  updateUnreadCount: (conversationId, count) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === conversationId ? { ...c, unread_count: count } : c
      ),
      activeConversation:
        state.activeConversation?.id === conversationId
          ? { ...state.activeConversation, unread_count: count }
          : state.activeConversation,
    })),

  clearUnreadCount: (conversationId) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === conversationId ? { ...c, unread_count: 0 } : c
      ),
      activeConversation:
        state.activeConversation?.id === conversationId
          ? { ...state.activeConversation, unread_count: 0 }
          : state.activeConversation,
    })),

  markMessagesRead: (conversationId, _readerId, lastReadAt) =>
    set((state) => {
      const msgs = state.messages[conversationId];
      if (!msgs) return state;

      const updated = msgs.map((m) => {
        if (!m.is_read && new Date(m.created_at) <= new Date(lastReadAt)) {
          return { ...m, is_read: true };
        }
        return m;
      });

      return {
        messages: {
          ...state.messages,
          [conversationId]: updated,
        },
      };
    }),

  setIsLoadingConversations: (loading) => set({ isLoadingConversations: loading }),
  setIsLoadingMessages: (loading) => set({ isLoadingMessages: loading }),

  reset: () =>
    set({
      conversations: [],
      activeConversation: null,
      messages: {},
      isTyping: {},
      onlineUsers: {},
      isLoadingConversations: false,
      isLoadingMessages: false,
    }),
}));
