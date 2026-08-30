import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { api, setToken, clearToken, getStoredUser, setStoredUser } from '../api/client';
import type { User } from '../types';

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: any) => Promise<User>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(getStoredUser());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('swasthya_setu_token');
    if (token) {
      api.me()
        .then((u: any) => {
          setUser(u.data || u);
          setStoredUser(u.data || u);
        })
        .catch(() => {
          clearToken();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<User> => {
    const res = await api.login({ email, password });
    setToken(res.access_token);
    setUser(res.user);
    setStoredUser(res.user);
    return res.user;
  }, []);

  const register = useCallback(async (data: any): Promise<User> => {
    const res = await api.register(data);
    setToken(res.access_token);
    setUser(res.user);
    setStoredUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    window.location.href = '/login';
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
