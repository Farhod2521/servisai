"use client";

import { useEffect, useState } from "react";
import { Avatar } from "../components/auth/UserMenu";
import { Close, Copy, Send } from "../components/icons";
import Linkify from "../components/Linkify";
import { api, formatDate, statusMeta, topUpStatusMeta, type AdminUserDetail } from "../lib/api";
import { formatPrice } from "../mahsulotlar/catalog-data";
import { ErrorText } from "../profil/ui";

/** Foydalanuvchi kartasi: balans, qancha to‘ldirgan, nima sotib olgan va unga berilgan havolalar */
export default function UserDetailDialog({ userId, onClose }: { userId: number; onClose: () => void }) {
  const [data, setData] = useState<AdminUserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"orders" | "topups">("orders");

  useEffect(() => {
    api<AdminUserDetail>(`/admin/users/${userId}`)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [userId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const u = data?.user;

  return (
    <div
      className="fixed inset-0 z-[70] overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:p-8"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="mx-auto w-full max-w-3xl rounded-3xl bg-white shadow-2xl" role="dialog" aria-label="Foydalanuvchi ma’lumotlari">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5">
          {u ? (
            <div className="flex min-w-0 items-center gap-4">
              <Avatar user={u} className="size-14" />
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-lg font-bold">
                  <span className="truncate">{u.full_name || "—"}</span>
                  {u.is_admin && <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[10px] font-bold text-brand">ADMIN</span>}
                </p>
                <p className="flex flex-wrap gap-x-3 text-sm text-slate-500">
                  {u.telegram_username && (
                    <a href={`https://t.me/${u.telegram_username}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-brand hover:underline">
                      <Send className="size-3.5" /> @{u.telegram_username}
                    </a>
                  )}
                  {u.phone && <span>{u.phone}</span>}
                  {u.email && <span>{u.email}</span>}
                  <span>ID {u.id}</span>
                </p>
                <p className="text-xs text-slate-400">
                  Ro‘yxatdan o‘tgan: {formatDate(u.created_at, false)}
                  {u.last_login_at && ` · Oxirgi kirish: ${formatDate(u.last_login_at)}`}
                </p>
              </div>
            </div>
          ) : (
            <div className="h-14 w-64 animate-pulse rounded-2xl bg-slate-100" />
          )}
          <button aria-label="Yopish" onClick={onClose} className="grid size-9 shrink-0 place-items-center rounded-lg hover:bg-slate-100">
            <Close className="size-5" />
          </button>
        </div>

        <div className="space-y-5 p-6">
          {error && <ErrorText text={error} />}

          {data && (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <Stat label="Hozirgi balans" value={`${formatPrice(data.user.balance)} so‘m`} tone="text-emerald-600" />
                <Stat label="Jami to‘ldirgan" value={`${formatPrice(data.topped_up)} so‘m`} />
                <Stat label="Jami sarflagan" value={`${formatPrice(data.user.total_spent)} so‘m`} hint={`${data.orders.length} ta buyurtma`} />
              </div>

              <p className="rounded-2xl bg-violet-50 px-4 py-3 text-sm text-violet-900">
                👥 Taklif qilgan do‘stlari: <b>{data.friends} ta</b>
                {data.referred_by_name && (
                  <>
                    {" "}· O‘zini <b>{data.referred_by_name}</b> taklif qilgan
                  </>
                )}
              </p>

              <div className="flex gap-2">
                {(
                  [
                    { id: "orders", label: `Xaridlar (${data.orders.length})` },
                    { id: "topups", label: `Hisob to‘ldirishlar (${data.topups.length})` },
                  ] as const
                ).map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
                      tab === t.id ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {tab === "orders" &&
                (data.orders.length === 0 ? (
                  <p className="rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-500">Hali xarid qilmagan.</p>
                ) : (
                  <ul className="space-y-3">
                    {data.orders.map((o) => (
                      <li key={o.id} className="rounded-2xl p-4 ring-1 ring-slate-100">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-semibold">
                            {o.product_name}
                            {o.quantity > 1 && <span className="text-brand"> × {o.quantity}</span>}
                            <span className="font-normal text-slate-400"> · {o.duration_months} oy</span>
                          </p>
                          <span className="font-bold">{formatPrice(o.price)} so‘m</span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                          <span>{o.number}</span>
                          <span>{formatDate(o.created_at)}</span>
                          <span className={`rounded-full px-2 py-0.5 font-semibold ${statusMeta[o.status].className}`}>{statusMeta[o.status].label}</span>
                        </div>
                        {o.delivery_info ? (
                          <div className="mt-3 flex items-start gap-2 rounded-xl bg-emerald-50/70 p-3">
                            <p className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-sm text-emerald-900">
                              <Linkify text={o.delivery_info} />
                            </p>
                            <CopyIcon text={o.delivery_info} />
                          </div>
                        ) : (
                          o.status !== "cancelled" && <p className="mt-2 text-xs text-amber-600">⏳ Hali yetkazilmagan</p>
                        )}
                      </li>
                    ))}
                  </ul>
                ))}

              {tab === "topups" &&
                (data.topups.length === 0 ? (
                  <p className="rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-500">Hisobni to‘ldirmagan.</p>
                ) : (
                  <ul className="divide-y divide-slate-100 rounded-2xl ring-1 ring-slate-100">
                    {data.topups.map((t) => (
                      <li key={t.id} className="flex items-center justify-between gap-3 px-4 py-3">
                        <div>
                          <p className="font-semibold">{formatPrice(t.amount)} so‘m</p>
                          <p className="text-xs text-slate-500">
                            #{t.id} · {formatDate(t.created_at)}
                            {t.admin_note && ` · ${t.admin_note}`}
                          </p>
                        </div>
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${topUpStatusMeta[t.status].className}`}>
                          {topUpStatusMeta[t.status].label}
                        </span>
                      </li>
                    ))}
                  </ul>
                ))}
            </>
          )}
          {!data && !error && <div className="h-48 animate-pulse rounded-2xl bg-slate-50" />}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, hint, tone = "" }: { label: string; value: string; hint?: string; tone?: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 text-xl font-extrabold ${tone}`}>{value}</p>
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

function CopyIcon({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      title="Nusxalash"
      aria-label="Nusxalash"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard ruxsat berilmagan */
        }
      }}
      className="grid size-8 shrink-0 place-items-center rounded-lg bg-white text-emerald-700 ring-1 ring-emerald-200 hover:ring-emerald-400"
    >
      {copied ? <span className="text-xs font-bold">✓</span> : <Copy className="size-4" />}
    </button>
  );
}
