export interface User {
  id: string;
  email: string;
  username: string;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface MessageResponse {
  detail: string;
}
