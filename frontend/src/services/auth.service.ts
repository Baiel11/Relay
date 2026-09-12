import { api } from './api';
import type { LoginRequest, LoginResponse, RegisterRequest, User } from '../types/auth.types';

export const authService = {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await api.post<LoginResponse>('/auth/login', credentials);
    return response.data;
  },

  async register(data: RegisterRequest): Promise<User> {
    const response = await api.post<User>('/auth/register', data);
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },


  async logout(): Promise<void> {
    await api.post('/auth/logout');
  },

  async logoutAll(): Promise<void> {
    await api.post('/auth/logout-all');
  },

  async searchUsers(query: string): Promise<User[]> {
    const response = await api.get<{ items: User[] }>(`/users/search?q=${encodeURIComponent(query)}`);
    return response.data.items;
  },

  async refreshToken(): Promise<{ data: LoginResponse }> {
    return await api.post<LoginResponse>('/auth/refresh', {});
  }
};

