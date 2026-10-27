"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, refStore, tokenStore, type User } from "../../lib/api";
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
  /** Balans kabi o‘zgaruvchan ma’lumotlarni serverdan qayta olish */
  refreshUser: () => Promise<void>;
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

  // Taklif havolasi (?ref=KOD) bilan kelganda kod ro‘yxatdan o‘tishgacha saqlanadi
  useEffect(() => {
    const ref = new URLSearchParams(window.location.search).get("ref");
    if (ref && /^[A-Za-z0-9_]{4,20}$/.test(ref)) refStore.set(ref);
  }, []);

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

  const refreshUser = useCallback(async () => {
    try {
      setUser(await api<User>("/users/me"));
    } catch {
      /* keyingi urinishda yangilanadi */
    }
  }, []);

  // Telegram botda telefon yuborilgandan so‘ng saytga qaytilganda yangi ma’lumot olinadi
  useEffect(() => {
    if (!user) return;
    const onVisible = () => document.visibilityState === "visible" && refreshUser();
    window.addEventListener("focus", onVisible);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("focus", onVisible);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [user, refreshUser]);

  const logout = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, openLogin: (o = {}) => setLogin(o), setSession, setUser, refreshUser, logout }),
    [user, loading, setSession, refreshUser, logout],
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
