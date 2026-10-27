"use client";

import { useCallback, useEffect, useState } from "react";
import { Close, Send } from "../components/icons";
import Linkify from "../components/Linkify";
import { api, formatDate, statusMeta, type AdminOrder, type OrderStatus } from "../lib/api";
import { durationText, formatPrice } from "../mahsulotlar/catalog-data";
import { ErrorText } from "../profil/ui";

const PAGE = 50;

const filters: { id: string; label: string; statuses: OrderStatus[] }[] = [
  { id: "todo", label: "Yetkazish kerak", statuses: ["paid", "processing"] },
  { id: "done", label: "Bajarilgan", statuses: ["completed"] },
  { id: "cancelled", label: "Bekor qilingan", statuses: ["cancelled"] },
  { id: "all", label: "Barchasi", statuses: [] },
];

export default function OrdersAdmin() {
  const [filter, setFilter] = useState(filters[0]);
  const [page, setPage] = useState(0);
  const [orders, setOrders] = useState<AdminOrder[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<AdminOrder | null>(null);

  const load = useCallback(() => {
    const params = new URLSearchParams({ limit: String(PAGE + 1), offset: String(page * PAGE) });
    filter.statuses.forEach((s) => params.append("status", s));
    api<AdminOrder[]>(`/admin/orders?${params}`)
      .then((list) => {
        setOrders(list);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, [filter, page]);

  useEffect(load, [load]);

  // Keyingi sahifa borligini bilish uchun bittaga ko‘p so‘raymiz
  const hasNext = (orders?.length ?? 0) > PAGE;
  const visible = orders?.slice(0, PAGE);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Buyurtmalar</h1>
        <p className="text-sm text-slate-500">Mijozlar sotib olgan servislar. Qo‘lda yetkaziladiganlariga ma’lumotni shu yerdan yuborasiz.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f.id}
            onClick={() => {
              setFilter(f);
              setPage(0);
              setOrders(null);
            }}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              filter.id === f.id ? "bg-brand text-white shadow-md shadow-blue-600/20" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:ring-brand"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <ErrorText text={error} />}

      {!visible && !error ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-3xl bg-white" />
          ))}
        </div>
      ) : visible?.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-500">
          {filter.id === "todo" ? "🎉 Hamma buyurtmalar yetkazilgan!" : "Buyurtmalar yo‘q."}
        </div>
      ) : (
        <ul className="space-y-3">
          {visible?.map((o) => (
            <li key={o.id} className="flex flex-col gap-4 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-100 sm:flex-row sm:items-center sm:p-5">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-bold">{o.number}</span>
                  <StatusBadge status={o.status} />
                  <span className="text-xs text-slate-400">{formatDate(o.created_at)}</span>
                </div>
                <p className="mt-1.5 font-semibold">
                  {o.product_name}
                  {o.quantity > 1 && <span className="text-brand"> × {o.quantity}</span>}
                  <span className="font-normal text-slate-400"> · {durationText(o.duration_months, o.duration_unit)} · </span>
                  {formatPrice(o.price)} so‘m
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
                  <span>{o.user_name}</span>
                  {o.user_telegram_username && (
                    <a href={`https://t.me/${o.user_telegram_username}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-brand hover:underline">
                      <Send className="size-3.5" /> @{o.user_telegram_username}
                    </a>
                  )}
                  {o.user_phone && <span>{o.user_phone}</span>}
                </p>
                {o.comment && <p className="mt-1 text-sm text-slate-500">💬 {o.comment}</p>}
              </div>
              <button
                onClick={() => setOpen(o)}
                className={`shrink-0 rounded-xl px-5 py-2.5 text-sm font-semibold transition ${
                  o.status === "paid" || o.status === "processing"
                    ? "bg-brand text-white shadow-md shadow-blue-600/20 hover:bg-brand-dark"
                    : "text-slate-700 ring-1 ring-slate-200 hover:ring-brand"
                }`}
              >
                {o.status === "paid" || o.status === "processing" ? "Yetkazish" : "Ko‘rish"}
              </button>
            </li>
          ))}
        </ul>
      )}

      {(page > 0 || hasNext) && (
        <div className="flex justify-end gap-2 text-sm">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="rounded-xl px-4 py-2 font-semibold ring-1 ring-slate-200 disabled:opacity-40">
            Oldingi
          </button>
          <button disabled={!hasNext} onClick={() => setPage((p) => p + 1)} className="rounded-xl px-4 py-2 font-semibold ring-1 ring-slate-200 disabled:opacity-40">
            Keyingi
          </button>
        </div>
      )}

      {open && (
        <DeliverDialog
          order={open}
          onClose={() => setOpen(null)}
          onSaved={(updated) => {
            setOpen(null);
            // Holat filtrga mos kelmay qolsa ro‘yxatdan chiqadi
            setOrders((list) =>
              list
                ?.map((x) => (x.id === updated.id ? { ...x, ...updated } : x))
                .filter((x) => filter.statuses.length === 0 || filter.statuses.includes(x.status)) ?? null,
            );
          }}
        />
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: OrderStatus }) {
  const m = statusMeta[status];
  return <span className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${m.className}`}>{m.label}</span>;
}

function DeliverDialog({ order, onClose, onSaved }: { order: AdminOrder; onClose: () => void; onSaved: (o: AdminOrder) => void }) {
  const [delivery, setDelivery] = useState(order.delivery_info ?? "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editable = order.status !== "cancelled";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const save = async (status: OrderStatus) => {
    if (status === "completed" && !delivery.trim()) {
      setError("Mijozga beriladigan ma’lumotni yozing (masalan: Email | Parol)");
      return;
    }
    if (status === "cancelled" && !confirm(`${order.number} bekor qilinsinmi? ${formatPrice(order.price)} so‘m mijoz hisobiga qaytariladi.`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api<AdminOrder>(`/admin/orders/${order.id}`, {
        method: "PATCH",
        json: { status, note: note.trim() || null, delivery_info: delivery.trim() || null },
      });
      onSaved({ ...order, ...updated });
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[70] overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:p-8"
      onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}
    >
      <div className="mx-auto w-full max-w-xl rounded-3xl bg-white shadow-2xl" role="dialog" aria-labelledby="deliver-title">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 id="deliver-title" className="text-lg font-bold">
            {order.number} <StatusBadge status={order.status} />
          </h2>
          <button aria-label="Yopish" onClick={onClose} disabled={busy} className="grid size-9 place-items-center rounded-lg hover:bg-slate-100">
            <Close className="size-5" />
          </button>
        </div>

        <div className="space-y-5 p-6">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-2xl bg-slate-50 p-4 text-sm">
            <dt className="text-slate-500">Mahsulot</dt>
            <dd className="font-semibold">
              {order.product_name} {order.quantity > 1 && `× ${order.quantity}`} · {durationText(order.duration_months, order.duration_unit)}
            </dd>
            <dt className="text-slate-500">Summa</dt>
            <dd className="font-semibold">{formatPrice(order.price)} so‘m</dd>
            <dt className="text-slate-500">Mijoz</dt>
            <dd>
              {order.user_name}
              {order.user_telegram_username && (
                <a href={`https://t.me/${order.user_telegram_username}`} target="_blank" rel="noopener noreferrer" className="ml-2 text-brand hover:underline">
                  @{order.user_telegram_username}
                </a>
              )}
              {order.user_phone && <span className="ml-2 text-slate-500">{order.user_phone}</span>}
            </dd>
            <dt className="text-slate-500">Sana</dt>
            <dd>{formatDate(order.created_at)}</dd>
            {order.comment && (
              <>
                <dt className="text-slate-500">Izoh</dt>
                <dd>{order.comment}</dd>
              </>
            )}
          </dl>

          {editable ? (
            <>
              <label className="block">
                <span className="text-sm font-semibold">Mijozga beriladigan ma’lumot</span>
                <textarea
                  value={delivery}
                  onChange={(e) => setDelivery(e.target.value)}
                  rows={4}
                  autoFocus
                  placeholder={"Email | Parol\nyoki havola, kod, yo‘riqnoma..."}
                  className="mt-1.5 w-full resize-y rounded-xl border border-slate-200 px-3.5 py-2.5 font-mono text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
                />
                <span className="mt-1 block text-xs text-slate-500">
                  “Bajarildi” bosilganda mijozning «Buyurtmalarim» bo‘limida ko‘rinadi va Telegram botga yuboriladi.
                </span>
              </label>
              <label className="block">
                <span className="text-sm font-semibold">Mijozga izoh (ixtiyoriy)</span>
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={1000}
                  placeholder="Masalan: parolni o‘zgartirmang"
                  className="mt-1.5 h-11 w-full rounded-xl border border-slate-200 px-3.5 text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
                />
              </label>
            </>
          ) : (
            order.delivery_info && (
              <p className="whitespace-pre-wrap break-words rounded-2xl bg-slate-50 p-4 text-sm">
                <Linkify text={order.delivery_info} />
              </p>
            )
          )}

          {error && <ErrorText text={error} />}
        </div>

        {editable && (
          <div className="flex flex-col-reverse gap-2 border-t border-slate-100 px-6 py-4 sm:flex-row sm:items-center">
            <button
              onClick={() => save("cancelled")}
              disabled={busy}
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-rose-600 hover:bg-rose-50 sm:mr-auto"
            >
              Bekor qilish (pul qaytadi)
            </button>
            {order.status === "paid" && (
              <button onClick={() => save("processing")} disabled={busy} className="rounded-xl px-4 py-2.5 text-sm font-semibold ring-1 ring-slate-200 hover:ring-brand">
                Jarayonda
              </button>
            )}
            <button
              onClick={() => save("completed")}
              disabled={busy}
              className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-emerald-600/20 hover:bg-emerald-700 disabled:opacity-60"
            >
              {busy ? "Saqlanmoqda..." : order.status === "completed" ? "Yangilash va qayta yuborish" : "Bajarildi — mijozga yuborish"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
