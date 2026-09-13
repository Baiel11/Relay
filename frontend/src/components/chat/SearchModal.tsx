import React, { useState, useEffect } from 'react';
import type { User } from '../../types/auth.types';
import { authService } from '../../services/auth.service';
import { useAuthStore } from '../../stores/useAuthStore';
import { Search, X, UserPlus, Loader2 } from 'lucide-react';

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectUser: (user: User) => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({ isOpen, onClose, onSelectUser }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const currentUser = useAuthStore((state) => state.user);

  // Search dynamically per letter with 200ms debounce
  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const users = await authService.searchUsers(trimmed);
        const filtered = currentUser ? users.filter((u) => u.id !== currentUser.id) : users;
        setResults(filtered);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query, currentUser?.id]);

  if (!isOpen) return null;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    setLoading(true);
    try {
      const users = await authService.searchUsers(trimmed);
      const filtered = currentUser ? users.filter((u) => u.id !== currentUser.id) : users;
      setResults(filtered);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/95 animate-fade-in">
      <div className="w-full max-w-md cosmos-card p-6 rounded-3xl relative animate-fade-in">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-widest">START NEW CHAT</h3>
          <button
            onClick={() => {
              setQuery('');
              setResults([]);
              onClose();
            }}
            className="p-1 rounded-lg text-[#666675] hover:text-white hover:bg-[#181820] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSearch} className="mb-4">
          <div className="relative">
            <Search className="absolute left-3.5 top-3 h-4 w-4 text-[#555565]" />
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Type username or email..."
              className="w-full rounded-xl cosmos-input pl-10 pr-10 py-2.5 text-xs"
            />
            {loading && (
              <div className="absolute right-3.5 top-3">
                <Loader2 className="h-4 w-4 animate-spin text-white" />
              </div>
            )}
          </div>
        </form>

        <div className="max-h-60 overflow-y-auto space-y-1.5 pr-1">
          {results.length === 0 && query && !loading && (
            <p className="text-center py-6 text-xs text-[#555565]">No users found matching "{query}"</p>
          )}

          {results.map((user) => (
            <div
              key={user.id}
              onClick={() => {
                onSelectUser(user);
                onClose();
              }}
              className="flex items-center justify-between p-2.5 rounded-xl hover:bg-[#141418] border border-transparent hover:border-[#22222a] cursor-pointer transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-full bg-[#181820] border border-[#2a2a35] flex items-center justify-center font-bold text-xs text-white uppercase">
                  {(user?.username || 'US').slice(0, 2)}
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-white group-hover:text-gray-200 transition-colors">
                    {user?.username || 'User'}
                  </h4>
                  <p className="text-[10px] text-[#666675]">{user?.email || ''}</p>
                </div>
              </div>
              <UserPlus className="h-3.5 w-3.5 text-[#555565] group-hover:text-white transition-colors" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
