"use client";

import { useCallback, useEffect, useState } from "react";
import Confetti from "../components/Confetti";
import { Copy, Gift, Send, Users } from "../components/icons";
import { api, formatDate, type MyReferral } from "../lib/api";
import { ErrorText } from "./ui";

export default function ReferralTab() {
  const [data, setData] = useState<MyReferral | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [claiming, setClaiming] = useState(false);
  const [celebrate, setCelebrate] = useState(false);

  const load = useCallback(() => {
    api<MyReferral>("/referrals/me")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const claim = async () => {
    setClaiming(true);
    setError(null);
    try {
      const r = await api<{ granted: unknown[] }>("/referrals/claim", { method: "POST" });
      if (r.granted.length) setCelebrate(true);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setClaiming(false);
    }
  };

  if (error && !data) return <ErrorText text={error} />;
  if (!data) return <div className="h-96 animate-pulse rounded-3xl bg-white" />;

  const next = data.rewards.find((r) => !r.achieved);
  const claimable = data.rewards.some((r) => r.achieved && !r.granted);
  const shareText = "servisai.uz — premium AI servislar arzon narxda! Shu havola orqali kiring 🎁";

  return (
    <div className="space-y-6">
      {celebrate && <Confetti />}

      {/* Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#7c3aed] via-[#5b5bf7] to-[#1557ff] p-6 text-white shadow-xl shadow-indigo-600/25 sm:p-8">
        <div aria-hidden className="absolute -right-16 -top-20 size-72 rounded-full bg-white/10 blur-2xl" />
        <div aria-hidden className="absolute -bottom-24 left-1/3 size-64 rounded-full bg-fuchsia-300/20 blur-3xl" />
        <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="max-w-lg">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold ring-1 ring-white/25">
              <Gift className="size-4" /> Do‘st taklif qilish
            </span>
            <h2 className="mt-3 text-2xl font-extrabold leading-tight sm:text-3xl">Do‘stlaringizni taklif qiling — premium servislarni tekinga oling!</h2>
            <p className="mt-2 text-sm text-white/85">
              Do‘stingiz havolangiz orqali saytga yoki botga birinchi marta kirsa, u sizga hisoblanadi.
              {next && ` Keyingi sovg‘agacha yana ${next.required_friends - data.friends} ta do‘st qoldi.`}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-4 rounded-2xl bg-white/15 px-5 py-4 ring-1 ring-white/25 backdrop-blur">
            <span className="grid size-12 place-items-center rounded-xl bg-white/20">
              <Users className="size-6" />
            </span>
            <div>
              <p className="text-3xl font-extrabold">{data.friends}</p>
              <p className="text-xs text-white/80">taklif qilgan do‘st</p>
            </div>
          </div>
        </div>
      </div>

      {/* Havolalar */}
      <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 sm:p-6">
        <h3 className="text-lg font-bold">Sizning shaxsiy havolangiz</h3>
        <div className="mt-4 space-y-3">
          {data.bot_link && <LinkRow label="Telegram bot orqali" value={data.bot_link} />}
          <LinkRow label="Sayt orqali" value={data.site_link} />
        </div>
        <a
          href={`https://t.me/share/url?url=${encodeURIComponent(data.bot_link ?? data.site_link)}&text=${encodeURIComponent(shareText)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[#229ED9] px-5 py-3 text-sm font-semibold text-white shadow-md shadow-sky-600/20 transition hover:brightness-110"
        >
          <Send className="size-4" /> Telegram’da do‘stlarga ulashish
        </a>
      </div>

      {/* Sovg‘alar */}
      <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-bold">Sovg‘alar</h3>
          {claimable && (
            <button
              onClick={claim}
              disabled={claiming}
              className="animate-pulse rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-emerald-500/30 hover:animate-none disabled:opacity-60"
            >
              {claiming ? "Berilmoqda..." : "🎁 Sovg‘ani olish"}
            </button>
          )}
        </div>
        {error && <div className="mt-3"><ErrorText text={error} /></div>}
        {data.rewards.length === 0 ? (
          <p className="mt-4 rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-500">Sovg‘alar tez orada e’lon qilinadi.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {data.rewards.map((r) => {
              const pct = Math.min(100, Math.round((data.friends / r.required_friends) * 100));
              return (
                <li
                  key={r.id}
                  className={`rounded-2xl p-4 ring-1 ${
                    r.granted ? "bg-emerald-50/70 ring-emerald-100" : r.achieved ? "bg-amber-50/70 ring-amber-200" : "bg-slate-50/70 ring-slate-100"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <span className="grid size-11 place-items-center rounded-xl bg-white text-xl shadow-sm">{r.granted ? "✅" : r.achieved ? "🎉" : "🎁"}</span>
                      <div>
                        <p className="font-semibold">{r.title}</p>
                        <p className="text-sm text-slate-500">
                          {r.required_friends} ta do‘st → <b className="text-slate-700">{r.product_name}</b>
                          {r.quantity > 1 && ` × ${r.quantity}`}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-bold ${
                        r.granted ? "bg-emerald-100 text-emerald-700" : r.achieved ? "bg-amber-100 text-amber-700" : "bg-white text-slate-600 ring-1 ring-slate-200"
                      }`}
                    >
                      {r.granted ? `Olindi · ${r.order_number ?? ""}` : r.achieved ? "Olish mumkin!" : `${Math.min(data.friends, r.required_friends)} / ${r.required_friends}`}
                    </span>
                  </div>
                  {!r.granted && (
                    <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white ring-1 ring-slate-100">
                      <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-brand transition-all" style={{ width: `${pct}%` }} />
                    </div>
                  )}
                  {r.granted && (
                    <p className="mt-2 text-xs text-emerald-700">Ma’lumotlar «Mening buyurtmalarim» bo‘limida va Telegram botda.</p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Do‘stlar */}
      <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 sm:p-6">
        <h3 className="text-lg font-bold">Taklif qilgan do‘stlaringiz</h3>
        {data.friends_list.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">Hali hech kim yo‘q — havolani do‘stlaringizga yuboring!</p>
        ) : (
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {data.friends_list.map((f, i) => (
              <li key={`${f.name}-${i}`} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
                <span className="grid size-9 place-items-center rounded-full bg-brand text-sm font-bold text-white">{f.name[0]?.toUpperCase()}</span>
                <span className="flex-1 text-sm font-semibold">{f.name}</span>
                <span className="text-xs text-slate-400">{formatDate(f.joined_at, false)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function LinkRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
      <div className="flex items-center gap-2 rounded-xl bg-slate-50 p-1.5 pl-4 ring-1 ring-slate-100">
        <span className="min-w-0 flex-1 truncate font-mono text-sm">{value}</span>
        <button
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(value);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            } catch {
              /* clipboard ruxsat berilmagan */
            }
          }}
          className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition ${
            copied ? "bg-emerald-600 text-white" : "bg-white text-brand ring-1 ring-slate-200 hover:ring-brand"
          }`}
        >
          <Copy className="size-3.5" /> {copied ? "Nusxalandi" : "Nusxalash"}
        </button>
      </div>
    </div>
  );
}
