import React, { useState, useEffect, useRef } from 'react';
import type { Conversation, Message } from '../../types/chat.types';
import type { User } from '../../types/auth.types';
import { chatService } from '../../services/chat.service';
import { Send, MessageSquare, Loader2 } from 'lucide-react';

interface ChatAreaProps {
  conversation: Conversation | null;
  currentUser: User | null;
}

export const ChatArea: React.FC<ChatAreaProps> = ({ conversation, currentUser }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!conversation) return;

    const fetchMessages = async () => {
      setLoading(true);
      try {
        const data = await chatService.getMessages(conversation.id);
        setMessages(data.items.reverse());
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
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !conversation || sending) return;

    const text = inputText;
    setInputText('');
    setSending(true);

    try {
      const newMessage = await chatService.sendMessage(conversation.id, text);
      setMessages((prev) => [...prev, newMessage]);
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

  return (
    <div className="flex-1 flex flex-col h-full bg-[#050507] relative">
      {/* Top Header */}
      <div className="p-3.5 border-b border-[#1a1a20] flex items-center justify-between bg-[#0a0a0c]">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="h-8 w-8 rounded-full bg-[#181820] border border-[#2a2a35] flex items-center justify-center font-bold text-xs text-white uppercase">
              {otherUser?.username.slice(0, 2) || 'U'}
            </div>
            <div className="absolute bottom-0 right-0 h-2 w-2 rounded-full bg-emerald-500 border border-[#0a0a0c]" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white tracking-wide">{otherUser?.username || 'User'}</h3>
            <p className="text-[10px] text-emerald-500 font-medium uppercase tracking-wider">Online</p>
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
                <span className="text-[9px] text-[#555565] mt-1 px-1 font-mono">
                  {new Date(msg.created_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="p-3.5 border-t border-[#1a1a20] bg-[#0a0a0c]">
        <form onSubmit={handleSend} className="flex items-center gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={`Message ${otherUser?.username || ''}...`}
            className="flex-1 rounded-xl cosmos-input px-4 py-2.5 text-xs placeholder-[#555565]"
          />
          <button
            type="submit"
            disabled={!inputText.trim() || sending}
            className="p-2.5 rounded-xl bg-white hover:bg-gray-200 text-black transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {sending ? <Loader2 className="h-4 w-4 animate-spin text-black" /> : <Send className="h-4 w-4 text-black" />}
          </button>
        </form>
      </div>
    </div>
  );
};
