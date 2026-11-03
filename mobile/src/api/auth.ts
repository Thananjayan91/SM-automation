import { apiClient } from './client';
import { User, Tenant } from '../types';

export interface LoginResponse {
  user: User;
  tenants: Tenant[];
}

export async function apiLogin(email: string, password: string) {
  return apiClient.request<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function apiLogout() {
  return apiClient.request('/api/v1/auth/logout', {
    method: 'POST',
  });
}

