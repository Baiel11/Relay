import React, { useEffect, useState } from 'react';
import { useAuthStore } from '../stores/useAuthStore';
import { useChatStore } from '../stores/useChatStore';
import { chatService } from '../services/chat.service';
import { ChatSidebar } from '../components/chat/ChatSidebar';
import { ChatArea } from '../components/chat/ChatArea';
import { SearchModal } from '../components/chat/SearchModal';
import type { User } from '../types/auth.types';

export const ChatPage: React.FC = () => {
  const { user } = useAuthStore();
  const { conversations, activeConversation, setConversations, setActiveConversation } =
    useChatStore();

  const [isSearchOpen, setIsSearchOpen] = useState(false);

  useEffect(() => {
    const loadConversations = async () => {
      try {
        const data = await chatService.getConversations();
        setConversations(data.items);
        if (data.items.length > 0 && !activeConversation) {
          setActiveConversation(data.items[0]);
        }
      } catch (err) {
        console.error('Failed to load conversations:', err);
      }
    };

    loadConversations();
  }, []);

  const handleSelectUserFromSearch = async (targetUser: User) => {
    try {
      const conv = await chatService.createConversation(targetUser.id);
      conv.other_user = targetUser;

      // Add to conversations list if not present
      if (!conversations.some((c) => c.id === conv.id)) {
        setConversations([conv, ...conversations]);
      }
      setActiveConversation(conv);
    } catch (err) {
      console.error('Failed to create/get conversation:', err);
    }
  };

  return (
    <div className="flex h-screen w-screen bg-[#090d16] overflow-hidden">
      {/* Sidebar Navigation & Chat list */}
      <ChatSidebar
        conversations={conversations}
        activeConversation={activeConversation}
        currentUser={user}
        onSelectConversation={setActiveConversation}
        onOpenSearch={() => setIsSearchOpen(true)}
      />

      {/* Main Chat Thread Area */}
      <ChatArea conversation={activeConversation} currentUser={user} />

      {/* Search User Modal */}
      <SearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onSelectUser={handleSelectUserFromSearch}
      />
    </div>
  );
};
