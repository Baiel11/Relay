import { create } from 'zustand';
import type { Conversation, Message } from '../types/chat.types';

interface ChatState {
  conversations: Conversation[];
  activeConversation: Conversation | null;
  messages: Record<string, Message[]>; // conversationId -> Message[]
  isLoadingConversations: boolean;
  isLoadingMessages: boolean;
  
  setConversations: (conversations: Conversation[]) => void;
  setActiveConversation: (conversation: Conversation | null) => void;
  setMessages: (conversationId: string, messages: Message[]) => void;
  addMessage: (conversationId: string, message: Message) => void;
  setIsLoadingConversations: (loading: boolean) => void;
  setIsLoadingMessages: (loading: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  activeConversation: null,
  messages: {},
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
      return {
        messages: {
          ...state.messages,
          [conversationId]: [...currentMessages, message],
        },
      };
    }),

  setIsLoadingConversations: (loading) => set({ isLoadingConversations: loading }),
  setIsLoadingMessages: (loading) => set({ isLoadingMessages: loading }),
}));
