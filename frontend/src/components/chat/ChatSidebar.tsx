import React from 'react';
import type { Conversation } from '../../types/chat.types';
import type { User } from '../../types/auth.types';
import { Search, LogOut, Shield } from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';

interface ChatSidebarProps {
  conversations: Conversation[];
  activeConversation: Conversation | null;
  currentUser: User | null;
  onSelectConversation: (conversation: Conversation) => void;
  onOpenSearch: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  conversations,
  activeConversation,
  currentUser,
  onSelectConversation,
  onOpenSearch,
}) => {
  const logout = useAuthStore((state) => state.logout);

  return (
    <div className="w-80 md:w-88 flex flex-col h-full bg-[#0a0a0c] border-r border-[#1a1a20] relative z-20">
      {/* Top Profile Header */}
      <div className="p-4 border-b border-[#1a1a20] flex items-center justify-between bg-[#0d0d11]">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-full bg-[#18182f] border border-[#2a2a35] flex items-center justify-center font-bold text-xs text-white uppercase shadow">
            {currentUser?.username.slice(0, 2) || 'ME'}
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h3 className="text-xs font-bold text-white tracking-wide">{currentUser?.username}</h3>
              <Shield className="h-3 w-3 text-gray-400" />
            </div>
            <p className="text-[10px] text-[#666675] truncate max-w-[150px]">{currentUser?.email}</p>
          </div>
        </div>

        <button
          onClick={() => logout()}
          title="Logout"
          className="p-2 rounded-lg text-[#666675] hover:text-red-400 hover:bg-[#14141a] transition-colors"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>

      {/* Search Input Bar */}
      <div className="p-3">
        <button
          onClick={onOpenSearch}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl cosmos-input text-xs text-[#666675] hover:text-gray-300 transition-colors text-left"
        >
          <Search className="h-3.5 w-3.5 text-[#555565]" />
          <span>Search or start a conversation...</span>
        </button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {conversations.length === 0 ? (
          <div className="text-center py-12 px-4">
            <p className="text-xs text-[#555565] font-medium uppercase tracking-wider">No active chats</p>
          </div>
        ) : (
          conversations.map((conv) => {
            const isSelected = activeConversation?.id === conv.id;
            const otherName = conv.other_user?.username || 'User';

            return (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv)}
                className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all ${
                  isSelected
                    ? 'bg-[#141418] border border-[#282834] text-white shadow-md'
                    : 'hover:bg-[#111115] text-[#aaaaaa] border border-transparent'
                }`}
              >
                <div className="relative">
                  <div className="h-9 w-9 rounded-full bg-[#181820] border border-[#2a2a35] flex items-center justify-center font-bold text-xs text-white uppercase">
                    {otherName.slice(0, 2)}
                  </div>
                  <div className="absolute bottom-0 right-0 h-2 w-2 rounded-full bg-emerald-500 border border-[#0a0a0c]" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <h4 className="text-xs font-semibold text-white truncate">{otherName}</h4>
                    <span className="text-[9px] text-[#555565]">
                      {conv.last_message
                        ? new Date(conv.last_message.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : ''}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#666675] truncate">
                    {conv.last_message?.content || 'Direct message'}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
