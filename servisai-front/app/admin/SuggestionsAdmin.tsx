"use client";

import { useCallback, useEffect, useState } from "react";
import { Lightbulb, Send } from "../components/icons";
import { api, formatDate, type AdminSuggestion } from "../lib/api";
import { ErrorText } from "../profil/ui";

const filters = [
  { id: "new", label: "Javob kutmoqda" },
  { id: "answered", label: "Javob berilgan" },
  { id: "all", label: "Barchasi" },
] as const;
type Filter = (typeof filters)[number]["id"];

export default function SuggestionsAdmin() {
  const [filter, setFilter] = useState<Filter>("new");
  const [items, setItems] = useState<AdminSuggestion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<AdminSuggestion[]>(`/admin/suggestions?state=${filter}`)
      .then(setItems)
      .catch((e: Error) => setError(e.message));
  }, [filter]);

  useEffect(load, [load]);

  const replied = (updated: AdminSuggestion) =>
    setItems((list) =>
      (list ?? [])
        .map((x) => (x.id === updated.id ? updated : x))
        // "Javob kutmoqda" ro‘yxatidan javob berilgani chiqib ketadi
        .filter((x) => filter !== "new" || !x.reply),
    );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Takliflar</h1>
        <p className="text-sm text-slate-500">
          Mijozlar qaysi servislarni qo‘shishni so‘rayapti. Javobingiz mijozga Telegram botda va saytdagi vidjetda boradi.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f.id}
            onClick={() => {
              setItems(null);
              setFilter(f.id);
            }}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              filter === f.id ? "bg-brand text-white shadow-md shadow-blue-600/20" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:ring-brand"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <ErrorText text={error} />}

      {!items && !error ? (
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-3xl bg-white" />
          ))}
        </div>
      ) : items?.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-500">
          {filter === "new" ? "🎉 Hamma takliflarga javob berilgan!" : "Takliflar yo‘q."}
        </div>
      ) : (
        <ul className="space-y-3">
          {items?.map((s) => (
            <SuggestionCard key={s.id} item={s} onReplied={replied} />
          ))}
        </ul>
      )}
    </div>
  );
}

function SuggestionCard({ item, onReplied }: { item: AdminSuggestion; onReplied: (s: AdminSuggestion) => void }) {
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(!item.reply);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    if (text.trim().length < 3) {
      setError("Javobni yozing");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api<AdminSuggestion>(`/admin/suggestions/${item.id}/reply`, { method: "POST", json: { text: text.trim() } });
      setText("");
      setEditing(false);
      onReplied(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-amber-50 text-amber-600">
          <Lightbulb className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="font-semibold">{item.user_name}</span>
            {item.user_telegram_username && (
              <a
                href={`https://t.me/${item.user_telegram_username}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-brand hover:underline"
              >
                <Send className="size-3.5" />@{item.user_telegram_username}
              </a>
            )}
            <span className="text-xs text-slate-400">
              #{item.id} · {formatDate(item.created_at)}
            </span>
          </div>
          <p className="mt-2 whitespace-pre-wrap break-words text-slate-800">{item.text}</p>

          {item.reply && !editing && (
            <div className="mt-3 rounded-2xl bg-brand-soft/50 p-3 ring-1 ring-brand/10">
              <p className="text-xs font-semibold text-brand">
                Javob · {item.replied_by ?? "Admin"}
                {item.replied_at && ` · ${formatDate(item.replied_at)}`}
                {item.reply_seen && " · ✓ ko‘rildi"}
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{item.reply}</p>
              <button onClick={() => setEditing(true)} className="mt-2 text-xs font-semibold text-brand hover:underline">
                Qayta javob yozish
              </button>
            </div>
          )}

          {editing && (
            <div className="mt-3">
              <textarea
                value={text}
                onChange={(e) => {
                  setError(null);
                  setText(e.target.value);
                }}
                rows={3}
                maxLength={2000}
                placeholder="Javobingiz… (masalan: Rahmat! Midjourney tez orada qo‘shiladi)"
                className="w-full resize-y rounded-2xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
              {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
              <div className="mt-2 flex justify-end gap-2">
                {item.reply && (
                  <button onClick={() => setEditing(false)} className="rounded-xl px-4 py-2 text-sm font-semibold ring-1 ring-slate-200">
                    Bekor qilish
                  </button>
                )}
                <button
                  onClick={send}
                  disabled={busy}
                  className="flex items-center gap-2 rounded-xl bg-brand px-5 py-2 text-sm font-semibold text-white shadow-md shadow-blue-600/20 hover:bg-brand-dark disabled:opacity-60"
                >
                  <Send className="size-4" /> {busy ? "Yuborilmoqda..." : "Javob yuborish"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}
