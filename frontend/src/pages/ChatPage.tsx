import React, { useEffect, useState } from 'react';
import { useAuthStore } from '../stores/useAuthStore';
import { useChatStore } from '../stores/useChatStore';
import { chatService } from '../services/chat.service';
import { ChatSidebar } from '../components/chat/ChatSidebar';
import { ChatArea } from '../components/chat/ChatArea';
import { SearchModal } from '../components/chat/SearchModal';
import { useWebSocket } from '../hooks/useWebSocket';
import type { User } from '../types/auth.types';

export const ChatPage: React.FC = () => {
  const { user } = useAuthStore();
  const { conversations, activeConversation, setConversations, setActiveConversation } =
    useChatStore();

  useWebSocket(); // Activate real-time duplex socket transport

  const [isSearchOpen, setIsSearchOpen] = useState(false);


  useEffect(() => {
    if (!user) return;

    let isMounted = true;
    const loadConversations = async () => {
      try {
        const data = await chatService.getConversations();
        if (!isMounted) return;
        const items = Array.isArray(data?.items) ? data.items : [];
        setConversations(items);

        // Ensure activeConversation belongs to current user's conversation list
        const currentActive = useChatStore.getState().activeConversation;
        const activeBelongsToUser = currentActive && items.some((c) => c.id === currentActive.id);

        if (activeBelongsToUser) {
          const fresh = items.find((c) => c.id === currentActive.id);
          if (fresh) setActiveConversation(fresh);
        } else if (items.length > 0) {
          setActiveConversation(items[0]);
        } else {
          setActiveConversation(null);
        }
      } catch (err) {
        console.error('Failed to load conversations:', err);
      }
    };

    loadConversations();
    return () => {
      isMounted = false;
    };
  }, [user?.id, setConversations, setActiveConversation]);

  const handleSelectUserFromSearch = async (targetUser: User) => {
    try {
      const conv = await chatService.createConversation(targetUser.id);
      conv.other_user = targetUser;

      // Add to conversations list if not present
      const currentConvs = useChatStore.getState().conversations;
      if (!currentConvs.some((c) => c.id === conv.id)) {
        setConversations([conv, ...currentConvs]);
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
