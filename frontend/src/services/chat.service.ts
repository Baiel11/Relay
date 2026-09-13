import { api } from './api';
import type { Conversation, Message, PagedResult } from '../types/chat.types';

export const chatService = {
  async getConversations(limit = 20, offset = 0): Promise<PagedResult<Conversation>> {
    const response = await api.get<PagedResult<Conversation>>(`/conversations?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  async createConversation(userId: string): Promise<Conversation> {
    const response = await api.post<Conversation>('/conversations', { other_user_id: userId });
    return response.data;
  },


  async getMessages(conversationId: string, limit = 50, offset = 0): Promise<PagedResult<Message>> {
    const response = await api.get<PagedResult<Message>>(
      `/conversations/${conversationId}/messages?limit=${limit}&offset=${offset}`
    );
    return response.data;
  },

  async sendMessage(conversationId: string, content: string): Promise<Message> {
    const response = await api.post<Message>(`/conversations/${conversationId}/messages`, { content });
    return response.data;
  }
};
