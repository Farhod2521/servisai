"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Box, Plus, Receipt, Users, Wallet } from "../components/icons";
import { api, formatDate, statusMeta, type AdminOrder, type AdminStats, type TopProduct } from "../lib/api";
import { durationText, formatPrice } from "../mahsulotlar/catalog-data";
import { Card, ErrorText } from "../profil/ui";

type Data = { stats: AdminStats; orders: AdminOrder[]; top: TopProduct[] };

export default function Dashboard({
  onAddProduct,
  onOpenOrders,
  onOpenSuggestions,
}: {
  onAddProduct: () => void;
  onOpenOrders: () => void;
  onOpenSuggestions: () => void;
}) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api<AdminStats>("/admin/stats"),
      api<AdminOrder[]>("/admin/orders?limit=8"),
      api<TopProduct[]>("/admin/top-products"),
    ])
      .then(([stats, orders, top]) => setData({ stats, orders, top }))
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorText text={error} />;
  if (!data) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-3xl bg-white" />
        ))}
      </div>
    );
  }

  const { stats, orders, top } = data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-slate-500">Do‘kon holati bir qarashda</p>
        </div>
        <button
          onClick={onAddProduct}
          className="flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition hover:bg-brand-dark"
        >
          <Plus className="size-4" /> Mahsulot qo‘shish
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={<Wallet className="size-5" />}
          tone="bg-emerald-50 text-emerald-600"
          label="Jami daromad"
          value={`${formatPrice(stats.revenue_total)} so‘m`}
          hint={`Oxirgi 30 kun: ${formatPrice(stats.revenue_30d)} so‘m`}
        />
        <Stat
          icon={<Receipt className="size-5" />}
          tone="bg-sky-50 text-sky-600"
          label="Buyurtmalar"
          value={stats.orders_total}
          hint={`Jarayonda: ${stats.orders_active}`}
        />
        <Stat
          icon={<Users className="size-5" />}
          tone="bg-violet-50 text-violet-600"
          label="Foydalanuvchilar"
          value={stats.users_total}
          hint={`So‘nggi 7 kunda: +${stats.users_new_7d}`}
        />
        <Stat
          icon={<Box className="size-5" />}
          tone="bg-brand-soft text-brand"
          label="Mahsulotlar"
          value={`${stats.products_active} / ${stats.products_total}`}
          hint="Saytda ko‘rinadigan / jami"
        />
      </div>

      {stats.orders_active > 0 && (
        <button
          onClick={onOpenOrders}
          className="flex w-full items-center justify-between gap-3 rounded-2xl bg-brand-soft px-5 py-3 text-left text-sm text-brand ring-1 ring-brand/20 transition hover:ring-brand"
        >
          <span>
            <b>{stats.orders_active} ta</b> buyurtma yetkazilishini kutmoqda
          </span>
          <span className="font-semibold">Yetkazish →</span>
        </button>
      )}

      {stats.suggestions_new > 0 && (
        <button
          onClick={onOpenSuggestions}
          className="flex w-full items-center justify-between gap-3 rounded-2xl bg-amber-50 px-5 py-3 text-left text-sm text-amber-800 ring-1 ring-amber-100 transition hover:ring-amber-300"
        >
          <span>
            💡 <b>{stats.suggestions_new} ta</b> taklif javob kutmoqda
          </span>
          <span className="font-semibold">Javob berish →</span>
        </button>
      )}

      {stats.topups_pending > 0 && (
        <p className="rounded-2xl bg-amber-50 px-5 py-3 text-sm text-amber-800 ring-1 ring-amber-100">
          <b>{stats.topups_pending} ta</b> hisob to‘ldirish so‘rovi tasdiq kutmoqda — ular Telegram bot orqali tasdiqlanadi.
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card
          title="So‘nggi buyurtmalar"
          action={
            <button onClick={onOpenOrders} className="text-sm font-semibold text-brand hover:underline">
              Barchasi →
            </button>
          }
        >
          {orders.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">Hozircha buyurtmalar yo‘q.</p>
          ) : (
            <div className="-mx-5 overflow-x-auto sm:-mx-6">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-5 py-2 font-semibold sm:px-6">Raqam</th>
                    <th className="px-3 py-2 font-semibold">Mijoz</th>
                    <th className="px-3 py-2 font-semibold">Servis</th>
                    <th className="px-3 py-2 text-right font-semibold">Summa</th>
                    <th className="px-3 py-2 font-semibold">Holat</th>
                    <th className="px-5 py-2 font-semibold sm:px-6">Sana</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {orders.map((o) => (
                    <tr key={o.id}>
                      <td className="whitespace-nowrap px-5 py-3 font-semibold sm:px-6">{o.number}</td>
                      <td className="max-w-40 truncate px-3 py-3">{o.user_name}</td>
                      <td className="px-3 py-3">
                        {o.product_name}
                        {o.quantity > 1 && <span className="font-semibold"> × {o.quantity}</span>}{" "}
                        <span className="text-slate-400">· {durationText(o.duration_months, o.duration_unit)}</span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right font-semibold">{formatPrice(o.price)} so‘m</td>
                      <td className="px-3 py-3">
                        <span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${statusMeta[o.status].className}`}>
                          {statusMeta[o.status].label}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-500 sm:px-6">{formatDate(o.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Eng ko‘p sotilganlar">
          {top.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">Hali sotuvlar yo‘q.</p>
          ) : (
            <ol className="space-y-3">
              {top.map((t, i) => (
                <li key={`${t.product_id}-${t.product_name}`} className="flex items-center gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">{t.product_name}</p>
                    <p className="text-xs text-slate-500">{t.orders} ta buyurtma</p>
                  </div>
                  <span className="whitespace-nowrap text-sm font-semibold">{formatPrice(t.revenue)} so‘m</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}

function Stat({ icon, tone, label, value, hint }: { icon: ReactNode; tone: string; label: string; value: ReactNode; hint: string }) {
  return (
    <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
      <div className="flex items-center gap-3">
        <span className={`grid size-10 place-items-center rounded-xl ${tone}`}>{icon}</span>
        <span className="text-sm font-medium text-slate-500">{label}</span>
      </div>
      <p className="mt-3 text-2xl font-extrabold tracking-tight">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{hint}</p>
    </div>
  );
}
