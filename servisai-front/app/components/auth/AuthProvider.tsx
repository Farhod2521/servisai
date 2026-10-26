"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, tokenStore, type User } from "../../lib/api";
import LoginModal from "./LoginModal";

type LoginOptions = {
  /** Kirgandan keyin bajariladigan amal (masalan, buyurtma berish) */
  onSuccess?: (user: User) => void;
  /** Tizimdagi foydalanuvchi profiliga Google/Telegram ulash rejimi */
  link?: boolean;
};

type AuthContextValue = {
  user: User | null;
  /** Token tekshirilguncha true — sahifalar "kirmagan" holatni miltillatib ko‘rsatmasligi uchun */
  loading: boolean;
  openLogin: (options?: LoginOptions) => void;
  setSession: (token: string, user: User) => void;
  setUser: (user: User) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth AuthProvider ichida ishlatilishi kerak");
  return ctx;
}

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [login, setLogin] = useState<LoginOptions | null>(null);

  useEffect(() => {
    const check = tokenStore.get()
      ? api<User>("/users/me")
          .then(setUser)
          .catch((e) => {
            if (e instanceof ApiError && e.status === 401) tokenStore.set(null);
          })
      : Promise.resolve();
    check.finally(() => setLoading(false));
  }, []);

  const setSession = useCallback((token: string, u: User) => {
    tokenStore.set(token);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, openLogin: (o = {}) => setLogin(o), setSession, setUser, logout }),
    [user, loading, setSession, logout],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
      {login && (
        <LoginModal
          link={login.link}
          onClose={() => setLogin(null)}
          onSuccess={(u) => {
            setLogin(null);
            login.onSuccess?.(u);
          }}
        />
      )}
    </AuthContext.Provider>
  );
}
