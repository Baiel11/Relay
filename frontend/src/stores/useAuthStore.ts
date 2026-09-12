import { create } from 'zustand';
import type { User } from '../types/auth.types';
import { authService } from '../services/auth.service';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAccessToken: (token: string | null) => void;
  setUser: (user: User | null) => void;
  login: (token: string, user: User) => void;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,

  setAccessToken: (token) =>
    set({ accessToken: token, isAuthenticated: !!token }),

  setUser: (user) => set({ user }),

  login: (token, user) =>
    set({
      accessToken: token,
      user,
      isAuthenticated: true,
      isLoading: false,
    }),

  logout: async () => {
    try {
      await authService.logout();
    } catch {
      // Ignore logout errors if session expired
    } finally {
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },

  checkAuth: async () => {
    set({ isLoading: true });
    try {
      // First attempt to refresh token via HttpOnly cookie if access token isn't in memory
      if (!useAuthStore.getState().accessToken) {
        const { data } = await authService.refreshToken();
        set({ accessToken: data.access_token });
      }
      const user = await authService.getCurrentUser();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
    }
  },
}));

