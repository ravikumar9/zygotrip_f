'use client';
import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { tokenStore } from '@/services/api';
import { getCurrentUser, login as authLogin, logout as authLogout } from '@/services/auth';
import type { User } from '@/types';

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const token = tokenStore.getAccess();
    const refresh = tokenStore.getRefresh();
    if (!token && !refresh) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const me = await getCurrentUser();
      setUser(me);
    } catch {
      setUser(null);
      tokenStore.clear();
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const authData = await authLogin(email, password);
    setUser(authData.user);
  }, []);

  const logout = useCallback(async () => {
    await authLogout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
      refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

export default AuthContext;
