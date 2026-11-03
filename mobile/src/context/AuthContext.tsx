import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, Tenant } from '../types';
import { apiClient } from '../api/client';
import { apiLogin, apiLogout } from '../api/auth';

interface AuthContextType {
  user: User | null;
  tenants: Tenant[];
  activeTenant: Tenant | null;
  isAuthenticated: boolean;
  serverUrl: string;
  login: (email: string, pass: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  selectTenant: (tenant: Tenant) => void;
  updateServerUrl: (url: string) => void;
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [activeTenant, setActiveTenant] = useState<Tenant | null>(null);
  const [serverUrl, setServerUrl] = useState<string>(apiClient.getBaseUrl());

  const updateServerUrl = (url: string) => {
    setServerUrl(url);
    apiClient.setBaseUrl(url);
  };

  const selectTenant = (tenant: Tenant) => {
    setActiveTenant(tenant);
    apiClient.setTenantId(tenant.id);
  };

  const login = async (email: string, pass: string) => {
    const res = await apiLogin(email, pass);
    if (res.data) {
      setUser(res.data.user);
      setTenants(res.data.tenants || []);
      if (res.data.tenants && res.data.tenants.length > 0) {
        selectTenant(res.data.tenants[0]);
      }
      return { success: true };
    }
    return { success: false, error: res.error || 'Login failed' };
  };

  const logout = async () => {
    await apiLogout();
    setUser(null);
    setTenants([]);
    setActiveTenant(null);
    apiClient.setTenantId(null);
    apiClient.setSessionCookie(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        tenants,
        activeTenant,
        isAuthenticated: !!user,
        serverUrl,
        login,
        logout,
        selectTenant,
        updateServerUrl,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

