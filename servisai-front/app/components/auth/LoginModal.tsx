"use client";

import { useEffect, useRef, useState } from "react";
import { api, type AuthConfig, type TelegramInit, type TelegramStatus, type TokenResponse, type User } from "../../lib/api";
import { Close, GoogleLogo, Logo, Send } from "../icons";
import { useAuth } from "./AuthProvider";

type GoogleId = {
  initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string }) => void;
  renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
};

declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";

function loadGoogleScript() {
  return new Promise<void>((resolve, reject) => {
    if (window.google?.accounts) return resolve();
    let script = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    if (!script) {
      script = document.createElement("script");
      script.src = GSI_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("Google skriptini yuklab bo‘lmadi")));
  });
}

type Props = { link?: boolean; onClose: () => void; onSuccess: (user: User) => void };

export default function LoginModal({ link, onClose, onSuccess }: Props) {
  const { setSession, setUser } = useAuth();
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [telegram, setTelegram] = useState<TelegramInit | null>(null);
  const googleRef = useRef<HTMLDivElement>(null);

  // Callback’lar Google skripti ichida saqlanib qoladi — eng so‘nggi holatni ref orqali olamiz
  const handlers = useRef({ link, onSuccess, setSession, setUser });
  useEffect(() => {
    handlers.current = { link, onSuccess, setSession, setUser };
  });

  useEffect(() => {
    api<AuthConfig>("/auth/config")
      .then(setConfig)
      .catch(() => setError("Server bilan aloqa yo‘q. Keyinroq urinib ko‘ring."));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);

  // Google tugmasi
  useEffect(() => {
    const clientId = config?.google_client_id;
    if (!clientId) return;
    let cancelled = false;
    loadGoogleScript()
      .then(() => {
        if (cancelled || !googleRef.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async ({ credential }) => {
            const h = handlers.current;
            setBusy(true);
            setError(null);
            try {
              if (h.link) {
                const user = await api<User>("/auth/google/link", { method: "POST", json: { credential } });
                h.setUser(user);
                h.onSuccess(user);
              } else {
                const res = await api<TokenResponse>("/auth/google", { method: "POST", json: { credential } });
                h.setSession(res.access_token, res.user);
                h.onSuccess(res.user);
              }
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          },
        });
        window.google.accounts.id.renderButton(googleRef.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "pill",
          text: "continue_with",
          locale: "uz",
          width: googleRef.current.offsetWidth || 320,
        });
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [config?.google_client_id]);

  // Telegram: bot tasdiqlaguncha holatni so‘rab turamiz
  useEffect(() => {
    if (!telegram) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const res = await api<TelegramStatus>(`/auth/telegram/status/${telegram.token}`);
        if (stopped) return;
        if (res.status === "confirmed" && res.access_token && res.user) {
          const h = handlers.current;
          if (h.link) h.setUser(res.user);
          else h.setSession(res.access_token, res.user);
          h.onSuccess(res.user);
          return;
        }
        if (res.status !== "pending") {
          setTelegram(null);
          setError(res.detail ?? "Kirish amalga oshmadi");
          return;
        }
      } catch {
        /* tarmoq uzilishi — keyingi urinishda davom etamiz */
      }
      timer = setTimeout(poll, 2000);
    };
    timer = setTimeout(poll, 2000);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [telegram]);

  const startTelegram = async () => {
    setError(null);
    // Popup bloklanmasligi uchun oynani darhol (sinxron) ochamiz, havolani keyin beramiz
    const win = window.open("", "_blank");
    try {
      const res = await api<TelegramInit>("/auth/telegram/init", { method: "POST" });
      setTelegram(res);
      if (win) win.location.href = res.bot_url;
    } catch (e) {
      win?.close();
      setError((e as Error).message);
    }
  };

  const loadingConfig = !config && !error;

  return (
    <div className="fixed inset-0 z-[100] grid place-items-center overflow-y-auto bg-slate-950/50 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-title"
        onMouseDown={(e) => e.stopPropagation()}
        className="relative w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl sm:p-8"
      >
        <button
          onClick={onClose}
          aria-label="Yopish"
          className="absolute right-4 top-4 grid size-9 place-items-center rounded-full text-slate-500 hover:bg-slate-100"
        >
          <Close className="size-5" />
        </button>

        <div className="flex flex-col items-center text-center">
          <Logo className="size-12" />
          <h2 id="login-title" className="mt-4 text-2xl font-bold">
            {link ? "Hisobni ulash" : "Tizimga kirish"}
          </h2>
          <p className="mt-1.5 text-sm text-slate-500">
            {link
              ? "Profilingizga qo‘shimcha kirish usulini ulang"
              : "Hisobingiz bo‘lmasa, avtomatik ro‘yxatdan o‘tasiz"}
          </p>
        </div>

        <div className="mt-7 space-y-3">
          {loadingConfig && (
            <>
              <div className="h-11 animate-pulse rounded-full bg-slate-100" />
              <div className="h-11 animate-pulse rounded-full bg-slate-100" />
            </>
          )}

          {config?.google_client_id ? (
            <div className={busy ? "pointer-events-none opacity-60" : ""}>
              <div ref={googleRef} className="flex min-h-11 w-full justify-center" />
            </div>
          ) : (
            config && (
              <button disabled className="flex h-11 w-full items-center justify-center gap-2.5 rounded-full text-sm font-semibold text-slate-400 ring-1 ring-slate-200">
                <GoogleLogo className="size-5 opacity-50" /> Google orqali kirish sozlanmagan
              </button>
            )
          )}

          {config && (
            <button
              onClick={startTelegram}
              disabled={!config.telegram_bot_username || busy}
              className="flex h-11 w-full items-center justify-center gap-2.5 rounded-full bg-[#229ED9] text-sm font-semibold text-white shadow-md shadow-sky-500/25 transition hover:bg-[#1c8cc2] disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"
            >
              <Send className="size-4.5" />
              {config.telegram_bot_username ? "Telegram bot orqali kirish" : "Telegram orqali kirish sozlanmagan"}
            </button>
          )}
        </div>

        {telegram && (
          <div className="mt-5 rounded-2xl bg-sky-50 p-4 text-sm text-sky-900">
            <div className="flex items-center gap-2 font-semibold">
              <span className="size-2 animate-ping rounded-full bg-sky-500" /> Telegramda tasdiqlash kutilmoqda...
            </div>
            <p className="mt-1.5 text-sky-800/80">
              Botda <b>START</b> tugmasini bosing — sahifa avtomatik yangilanadi.
            </p>
            <a
              href={telegram.bot_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 font-semibold text-sky-700 underline underline-offset-2"
            >
              Bot ochilmadimi? Bu yerni bosing
            </a>
          </div>
        )}

        {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-600">{error}</p>}

        <p className="mt-6 text-center text-xs leading-relaxed text-slate-400">
          Davom etish orqali siz foydalanish shartlari va maxfiylik siyosatiga rozilik bildirasiz.
        </p>
      </div>
    </div>
  );
}
