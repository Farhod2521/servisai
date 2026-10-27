"use client";

import { useCallback, useEffect, useState } from "react";
import { api, formatDate, type Suggestion } from "../lib/api";
import { useAuth } from "./auth/AuthProvider";
import { Close, Lightbulb, MessageIcon, Send } from "./icons";

const MINIMIZED_KEY = "servisai_suggest_minimized";
const OPEN_DELAY_MS = 2500;
const IDEAS = ["Midjourney", "Netflix", "Spotify", "Canva Pro", "YouTube Premium", "Notion"];

function wasMinimized() {
  try {
    return localStorage.getItem(MINIMIZED_KEY) === "1";
  } catch {
    return false;
  }
}

function rememberMinimized(value: boolean) {
  try {
    if (value) localStorage.setItem(MINIMIZED_KEY, "1");
    else localStorage.removeItem(MINIMIZED_KEY);
  } catch {
    /* private rejim */
  }
}

/** O‘ng pastki burchakdagi "Taklifingizni qoldiring" vidjeti: taklif yuborish va admin javoblarini ko‘rish */
export default function SuggestionWidget() {
  const { user, openLogin } = useAuth();
  // hidden — sahifa endi ochildi; open — kartochka; bubble — kichik tugma
  const [mode, setMode] = useState<"hidden" | "open" | "bubble">("hidden");
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [mine, setMine] = useState<Suggestion[]>([]);
  const [showMine, setShowMine] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => setMode(wasMinimized() ? "bubble" : "open"), OPEN_DELAY_MS);
    return () => clearTimeout(id);
  }, []);

  const loadMine = useCallback(() => {
    api<Suggestion[]>("/suggestions/me")
      .then(setMine)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (user) loadMine();
  }, [user, loadMine]);

  const unseen = mine.filter((s) => s.reply && !s.reply_seen).length;

  const minimize = () => {
    rememberMinimized(true);
    setMode("bubble");
  };

  const expand = () => {
    rememberMinimized(false);
    setMode("open");
    if (unseen) setShowMine(true);
  };

  // Javoblar ko‘rilganda belgini olib tashlaymiz
  useEffect(() => {
    if (mode !== "open" || !showMine || !unseen) return;
    api("/suggestions/me/seen", { method: "POST" })
      .then(() => setMine((list) => list.map((s) => (s.reply ? { ...s, reply_seen: true } : s))))
      .catch(() => {});
  }, [mode, showMine, unseen]);

  const submit = async (value: string) => {
    setSending(true);
    setError(null);
    try {
      const created = await api<Suggestion>("/suggestions", { method: "POST", json: { text: value } });
      setMine((list) => [created, ...list]);
      setText("");
      setSent(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  const send = () => {
    const value = text.trim();
    if (value.length < 3) {
      setError("Taklifingizni bir necha so‘z bilan yozing");
      return;
    }
    // Javobni kimga yuborishni bilishimiz uchun avval kirish kerak (Telegram orqali)
    if (!user) openLogin({ onSuccess: () => submit(value) });
    else submit(value);
  };

  const addIdea = (idea: string) => {
    setError(null);
    setText((t) => (t.trim() ? `${t.trim()}, ${idea}` : idea));
  };

  if (mode === "hidden") return null;

  if (mode === "bubble") {
    return (
      <button
        onClick={expand}
        aria-label="Taklif qoldirish"
        className="fixed bottom-5 right-5 z-[60] flex items-center gap-2 rounded-full bg-gradient-to-r from-brand to-violet-600 py-3 pl-4 pr-5 text-sm font-semibold text-white shadow-xl shadow-blue-600/30 transition hover:scale-105"
      >
        <Lightbulb className="size-5" /> Taklif
        {unseen > 0 && (
          <span className="absolute -right-1 -top-1 grid size-5 place-items-center rounded-full bg-rose-500 text-[11px] font-bold ring-2 ring-white">
            {unseen}
          </span>
        )}
      </button>
    );
  }

  return (
    <div
      role="dialog"
      aria-labelledby="suggest-title"
      className="animate-[pop_.35s_cubic-bezier(.2,.9,.3,1.3)] fixed bottom-4 left-4 right-4 z-[60] overflow-hidden rounded-3xl bg-white shadow-2xl shadow-slate-900/20 ring-1 ring-slate-100 sm:left-auto sm:right-5 sm:w-[360px]"
    >
      <div className="relative bg-gradient-to-br from-brand via-[#3b5cff] to-violet-600 px-5 pb-5 pt-4 text-white">
        <div aria-hidden className="absolute -right-8 -top-10 size-32 rounded-full bg-white/15 blur-2xl" />
        <button
          onClick={minimize}
          aria-label="Yopish"
          className="absolute right-3 top-3 grid size-8 place-items-center rounded-full bg-white/15 transition hover:bg-white/25"
        >
          <Close className="size-4" />
        </button>
        <span className="grid size-11 place-items-center rounded-2xl bg-white/20 ring-1 ring-white/30">
          <Lightbulb className="size-6" />
        </span>
        <h2 id="suggest-title" className="mt-3 text-lg font-bold">
          Taklifingizni qoldiring
        </h2>
        <p className="mt-1 text-sm text-white/85">Biz uchun bu juda muhim! Yana qaysi servislarni qo‘shaylik?</p>
      </div>

      <div className="space-y-3 p-4">
        {sent ? (
          <div className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-800">
            <p className="font-semibold">🎉 Rahmat! Taklifingiz yuborildi.</p>
            <p className="mt-1 text-emerald-700/80">Javobni shu yerda va Telegram botda olasiz.</p>
            <button onClick={() => setSent(false)} className="mt-2 font-semibold text-emerald-700 underline">
              Yana yozish
            </button>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5">
              {IDEAS.map((idea) => (
                <button
                  key={idea}
                  type="button"
                  onClick={() => addIdea(idea)}
                  className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200 transition hover:bg-brand-soft hover:text-brand hover:ring-brand/30"
                >
                  + {idea}
                </button>
              ))}
            </div>
            <textarea
              value={text}
              onChange={(e) => {
                setError(null);
                setText(e.target.value);
              }}
              rows={3}
              maxLength={2000}
              placeholder="Masalan: Midjourney va Netflix qo‘shsangiz zo‘r bo‘lardi…"
              className="w-full resize-none rounded-2xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
            />
            {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-600">{error}</p>}
            <button
              onClick={send}
              disabled={sending}
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-brand py-3 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition hover:bg-brand-dark disabled:opacity-60"
            >
              <Send className="size-4" /> {sending ? "Yuborilmoqda..." : user ? "Yuborish" : "Telegram orqali kirib yuborish"}
            </button>
          </>
        )}

        {mine.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <button
              onClick={() => setShowMine((v) => !v)}
              className="flex w-full items-center justify-between text-sm font-semibold text-slate-700"
            >
              <span className="flex items-center gap-2">
                <MessageIcon className="size-4 text-brand" /> Mening takliflarim ({mine.length})
              </span>
              {unseen > 0 && <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[11px] font-bold text-white">{unseen} ta javob</span>}
            </button>
            {showMine && (
              <ul className="mt-3 max-h-56 space-y-2 overflow-y-auto pr-1">
                {mine.map((s) => (
                  <li key={s.id} className="rounded-2xl bg-slate-50 p-3 text-sm">
                    <p className="text-slate-700">{s.text}</p>
                    <p className="mt-1 text-[11px] text-slate-400">{formatDate(s.created_at)}</p>
                    {s.reply ? (
                      <div className="mt-2 rounded-xl bg-white p-2.5 ring-1 ring-brand/15">
                        <p className="text-[11px] font-semibold uppercase tracking-wider text-brand">Javob</p>
                        <p className="mt-0.5 whitespace-pre-wrap text-slate-700">{s.reply}</p>
                      </div>
                    ) : (
                      <p className="mt-1.5 text-xs text-amber-600">⏳ Javob kutilmoqda</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
