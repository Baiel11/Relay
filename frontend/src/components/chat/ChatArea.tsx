import React, { useState, useEffect, useRef } from 'react';
import type { Conversation } from '../../types/chat.types';
import type { User } from '../../types/auth.types';
import { chatService } from '../../services/chat.service';
import { useChatStore } from '../../stores/useChatStore';
import { useWebSocket } from '../../hooks/useWebSocket';
import { Send, MessageSquare, Loader2, Check, CheckCheck } from 'lucide-react';

interface ChatAreaProps {
  conversation: Conversation | null;
  currentUser: User | null;
}

const EMPTY_MESSAGES: any[] = [];

export const ChatArea: React.FC<ChatAreaProps> = ({ conversation, currentUser }) => {
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { isTyping, onlineUsers, clearUnreadCount, setMessages: setStoreMessages, addMessage } = useChatStore();
  const messages = useChatStore((state) =>
    conversation ? state.messages[conversation.id] || EMPTY_MESSAGES : EMPTY_MESSAGES
  );
  const { sendMessageWS, handleUserTypingInput, sendTypingWS, markReadWS } = useWebSocket();

  // Load message history from Postgres when switching conversation
  useEffect(() => {
    if (!conversation) return;

    // Clear unread count for active conversation immediately
    clearUnreadCount(conversation.id);
    markReadWS(conversation.id);

    const fetchMessages = async () => {
      setLoading(true);
      try {
        const data = await chatService.getMessages(conversation.id);
        const items = Array.isArray(data?.items) ? [...data.items].reverse() : [];
        setStoreMessages(conversation.id, items);
      } catch (err) {
        console.error('Failed to load messages:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();
  }, [conversation?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping[conversation?.id || '']]);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    if (conversation) {
      handleUserTypingInput(conversation.id);
    }
    // Auto-resize textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  };

  const handleInputBlur = () => {
    if (conversation) {
      sendTypingWS(conversation.id, false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !conversation || sending) return;

    const text = inputText.trim();
    setInputText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setSending(true);

    try {
      // 1. Send via real-time WebSocket
      const sentViaWS = sendMessageWS(conversation.id, text);
      if (!sentViaWS) {
        // Fallback to REST if WebSocket temporarily disconnected
        const newMessage = await chatService.sendMessage(conversation.id, text);
        addMessage(conversation.id, newMessage);
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      setInputText(text);
    } finally {
      setSending(false);
    }
  };

  if (!conversation) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#050507] text-center p-8 relative">
        <div className="h-12 w-12 rounded-full bg-[#111116] border border-[#22222a] flex items-center justify-center text-white mb-4">
          <MessageSquare className="h-5 w-5 text-[#888898]" />
        </div>
        <h3 className="text-sm font-bold text-white uppercase tracking-widest">No Active Conversation</h3>
        <p className="mt-1 text-xs text-[#666675] max-w-xs">
          Select a chat from the sidebar or start a new conversation.
        </p>
      </div>
    );
  }

  const otherUser = conversation.other_user;
  const otherId = (otherUser?.id || '').toLowerCase();
  const isPartnerOnline = onlineUsers[otherId] ?? conversation.is_online ?? false;
  const isPartnerTyping = isTyping[conversation.id] ?? false;

  return (
    <div className="flex-1 flex flex-col h-full bg-[#050507] relative">
      {/* Top Header */}
      <div className="p-3.5 border-b border-[#1a1a20] flex items-center justify-between bg-[#0a0a0c]">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="h-8 w-8 rounded-full bg-[#181820] border border-[#2a2a35] flex items-center justify-center font-bold text-xs text-white uppercase">
              {(otherUser?.username || 'User').slice(0, 2)}
            </div>
            {/* Dynamic Presence Dot */}
            <div
              className={`absolute bottom-0 right-0 h-2 w-2 rounded-full border border-[#0a0a0c] transition-colors ${
                isPartnerOnline ? 'bg-emerald-500' : 'bg-gray-600'
              }`}
            />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white tracking-wide">{otherUser?.username || 'User'}</h3>
            <p
              className={`text-[10px] font-medium uppercase tracking-wider transition-colors ${
                isPartnerOnline ? 'text-emerald-500' : 'text-[#666675]'
              }`}
            >
              {isPartnerOnline ? 'Online' : 'Offline'}
            </p>
          </div>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-white" />
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center py-12 text-[#555565] text-xs">
            Start the conversation with {otherUser?.username}!
          </div>
        ) : (
          messages.map((msg) => {
            const isMe = msg.sender_id === currentUser?.id;
            return (
              <div
                key={msg.id}
                className={`flex flex-col ${isMe ? 'items-end' : 'items-start'} animate-fade-in`}
              >
                <div
                  className={`max-w-[75%] px-4 py-2.5 rounded-2xl text-xs leading-relaxed ${
                    isMe
                      ? 'bg-white text-black font-medium rounded-br-none'
                      : 'bg-[#141418] border border-[#22222a] text-gray-200 rounded-bl-none'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
                <div className="flex items-center gap-1 mt-1 px-1">
                  <span className="text-[9px] text-[#555565] font-mono">
                    {new Date(msg.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                  {/* Read receipts: single check sent, double check read */}
                  {isMe && (
                    msg.is_read ? (
                      <CheckCheck className="h-3 w-3 text-indigo-400" />
                    ) : (
                      <Check className="h-3 w-3 text-[#555565]" />
                    )
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Live Typing Bubble */}
        {isPartnerTyping && (
          <div className="flex items-center gap-2 text-xs text-indigo-400 italic animate-fade-in pl-1">
            <div className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
            <span>{otherUser?.username} is typing...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="p-3.5 border-t border-[#1a1a20] bg-[#0a0a0c]">
        <form onSubmit={handleSend} className="flex items-end gap-2">
          <div className="flex-1 relative flex flex-col">
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputText}
              onChange={handleInputChange}
              onBlur={handleInputBlur}
              onKeyDown={handleKeyDown}
              placeholder={`Message ${otherUser?.username || ''}... (Enter to send, Shift+Enter for new line)`}
              className="w-full rounded-xl cosmos-input px-4 py-2.5 text-xs placeholder-[#555565] resize-none overflow-y-auto leading-relaxed max-h-[140px]"
            />
            {inputText.length > 500 && (
              <span className="self-end text-[9px] text-[#555565] px-2 pt-0.5">
                {inputText.length} / 20000
              </span>
            )}
          </div>
          <button
            type="submit"
            disabled={!inputText.trim() || sending}
            className="p-2.5 rounded-xl bg-white hover:bg-gray-200 text-black transition-colors disabled:opacity-40 disabled:cursor-not-allowed mb-0.5"
          >
            {sending ? <Loader2 className="h-4 w-4 animate-spin text-black" /> : <Send className="h-4 w-4 text-black" />}
          </button>
        </form>
      </div>
    </div>
  );
};
