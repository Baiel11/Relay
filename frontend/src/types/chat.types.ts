import type { User } from './auth.types';

export interface Conversation {
  id: string;
  participant_a: string;
  participant_b: string;
  created_at: string;
  other_user?: User;
  last_message?: Message;
  unread_count?: number;
  is_online?: boolean;
}


export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string;
  content: string;
  created_at: string;
  is_read?: boolean;
}

export interface PagedResult<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}
