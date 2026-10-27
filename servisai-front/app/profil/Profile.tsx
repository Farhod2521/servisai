"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../components/auth/AuthProvider";
import { Avatar } from "../components/auth/UserMenu";
import { ArrowRight, Gift, GoogleLogo, History, LogOut, Receipt, Send, UserIcon, Wallet } from "../components/icons";
import { durationText, formatPrice } from "../mahsulotlar/catalog-data";
import {
  api,
  formatDate,
  type AuthConfig,
  statusMeta,
  type HistoryItem,
  type Order,
  type OrderDetail,
  type OrderStatus,
  type User,
  type UserStats,
} from "../lib/api";
import { Card, Empty, ErrorText } from "./ui";
import ReferralTab from "./ReferralTab";
import WalletTab from "./WalletTab";
import Linkify from "../components/Linkify";

const tabs = [
  { id: "profil", label: "Profil", icon: UserIcon },
  { id: "hisob", label: "Hisobim", icon: Wallet },
  { id: "buyurtmalar", label: "Mening buyurtmalarim", icon: Receipt },
  { id: "tarix", label: "Buyurtmalar tarixi", icon: History },
  { id: "dostlar", label: "Do‘stlarni taklif qilish", icon: Gift },
] as const;

type Tab = (typeof tabs)[number]["id"];

export default function Profile() {
  const { user, loading, openLogin, logout } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: Tab = tabs.some((t) => t.id === params.get("tab")) ? (params.get("tab") as Tab) : "profil";

  if (loading) return <div className="h-96 animate-pulse rounded-3xl bg-white" />;

  if (!user) {
    return (
      <div className="mx-auto max-w-md rounded-3xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-100">
        <div className="mx-auto grid size-14 place-items-center rounded-full bg-brand-soft text-brand">
          <UserIcon className="size-7" />
        </div>
        <h1 className="mt-4 text-2xl font-bold">Profilga kirish</h1>
        <p className="mt-2 text-sm text-slate-500">Buyurtmalaringiz va ularning tarixini ko‘rish uchun tizimga kiring.</p>
        <button
          onClick={() => openLogin()}
          className="mt-6 w-full rounded-xl bg-brand py-3 text-sm font-semibold text-white shadow-md shadow-blue-600/25 hover:bg-brand-dark"
        >
          Tizimga kirish
        </button>
      </div>
    );
  }

  const select = (id: Tab) => router.replace(id === "profil" ? pathname : `${pathname}?tab=${id}`, { scroll: false });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="h-fit rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 lg:sticky lg:top-24">
        <div className="flex items-center gap-3">
          <Avatar user={user} className="size-14" />
          <div className="min-w-0">
            <p className="truncate font-bold">{user.full_name}</p>
            <p className="truncate text-xs text-slate-500">{user.email ?? (user.telegram_username && `@${user.telegram_username}`)}</p>
          </div>
        </div>
        <nav className="mt-5 flex gap-1 overflow-x-auto lg:flex-col">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => select(id)}
              className={`flex shrink-0 items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition ${
                tab === id ? "bg-brand-soft text-brand" : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              <Icon className="size-4.5" /> {label}
            </button>
          ))}
          <button
            onClick={logout}
            className="flex shrink-0 items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-rose-600 hover:bg-rose-50 lg:mt-2 lg:border-t lg:border-slate-100 lg:pt-3"
          >
            <LogOut className="size-4.5" /> Chiqish
          </button>
        </nav>
        <BotCard />
      </aside>

      <section className="min-w-0">
        {tab === "profil" && <ProfileTab user={user} onSelect={select} />}
        {tab === "hisob" && <WalletTab />}
        {tab === "buyurtmalar" && <OrdersTab />}
        {tab === "tarix" && <HistoryTab />}
        {tab === "dostlar" && <ReferralTab />}
      </section>
    </div>
  );
}

/* ---------- Umumiy ---------- */

/** Chap menyu ostidagi Telegram bot kartochkasi (bot sozlanmagan bo‘lsa ko‘rsatilmaydi) */
function BotCard() {
  const [bot, setBot] = useState<string | null>(null);

  useEffect(() => {
    api<AuthConfig>("/auth/config")
      .then((c) => setBot(c.telegram_bot_username))
      .catch(() => {});
  }, []);

  if (!bot) return null;

  return (
    <div className="mt-6 hidden rounded-2xl bg-gradient-to-br from-slate-50 to-brand-soft/60 p-4 ring-1 ring-slate-100 lg:block">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-bold">ServisAI Bot</p>
          <p className="mt-1 text-sm leading-snug text-slate-500">Telegram bot orqali ham buyurtma va balansingizni kuzating.</p>
        </div>
        <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#3b8cff] to-brand text-white shadow-lg shadow-blue-600/30">
          <Send className="size-6" />
        </span>
      </div>
      <a
        href={`https://t.me/${bot}`}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-4 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-brand shadow-sm ring-1 ring-brand/30 transition hover:ring-brand"
      >
        Botni ochish <ArrowRight className="size-4" />
      </a>
    </div>
  );
}

function StatusBadge({ status }: { status: OrderStatus }) {
  const m = statusMeta[status];
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${m.className}`}>
      <span className={`size-1.5 rounded-full ${m.dot}`} /> {m.label}
    </span>
  );
}

/* ---------- Profil ---------- */

function ProfileTab({ user, onSelect }: { user: User; onSelect: (tab: Tab) => void }) {
  const { setUser, openLogin } = useAuth();
  const [stats, setStats] = useState<UserStats | null>(null);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [name, setName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone ?? "");
  // Raqam keyinroq kelsa (masalan, Telegram botda yuborilsa) bo‘sh maydonga yoziladi
  const [knownPhone, setKnownPhone] = useState(user.phone);
  if (user.phone !== knownPhone) {
    setKnownPhone(user.phone);
    if (!phone.trim() && user.phone) setPhone(user.phone);
  }
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api<UserStats>("/users/me/stats").then(setStats).catch(() => {});
    api<AuthConfig>("/auth/config")
      .then((c) => setGoogleEnabled(Boolean(c.google_client_id)))
      .catch(() => {});
  }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const updated = await api<User>("/users/me", {
        method: "PATCH",
        json: { full_name: name.trim(), phone: phone.trim() || null },
      });
      setUser(updated);
      setMessage({ ok: true, text: "Ma’lumotlar saqlandi" });
    } catch (err) {
      setMessage({ ok: false, text: (err as Error).message });
    } finally {
      setSaving(false);
    }
  };

  const statItems: { label: string; value: string | number | undefined; tab: Tab }[] = [
    { label: "Balans", value: `${formatPrice(user.balance)} so‘m`, tab: "hisob" },
    { label: "Jami buyurtmalar", value: stats?.total_orders, tab: "buyurtmalar" },
    { label: "Faol buyurtmalar", value: stats?.active_orders, tab: "buyurtmalar" },
    { label: "Bajarilgan", value: stats?.completed_orders, tab: "buyurtmalar" },
  ];

  const input =
    "mt-1.5 h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10";

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {statItems.map((s) => (
          <button
            key={s.label}
            onClick={() => onSelect(s.tab)}
            className="rounded-2xl bg-white p-4 text-left shadow-sm ring-1 ring-slate-100 transition hover:ring-brand"
          >
            <p className="text-xs text-slate-500">{s.label}</p>
            {s.value === undefined ? (
              <span className="mt-2 block h-7 w-16 animate-pulse rounded bg-slate-100" />
            ) : (
              <p className="mt-1 truncate text-xl font-extrabold">{s.value}</p>
            )}
          </button>
        ))}
      </div>

      <Card title="Shaxsiy ma’lumotlar">
        <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Ism familiya
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={255} className={input} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Telefon raqam
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+998 90 123 45 67"
              inputMode="tel"
              className={input}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Email
            <input value={user.email ?? "—"} disabled className={`${input} bg-slate-50 text-slate-500`} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Ro‘yxatdan o‘tgan sana
            <input value={formatDate(user.created_at, false)} disabled className={`${input} bg-slate-50 text-slate-500`} />
          </label>
          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <button
              disabled={saving}
              className="rounded-xl bg-brand px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
            >
              {saving ? "Saqlanmoqda..." : "Saqlash"}
            </button>
            {message && <span className={`text-sm ${message.ok ? "text-emerald-600" : "text-rose-600"}`}>{message.text}</span>}
          </div>
        </form>
      </Card>

      <Card title="Kirish usullari">
        <ul className="divide-y divide-slate-100">
          {(googleEnabled || user.has_google) && (
            <li className="flex items-center gap-3 py-3">
              <GoogleLogo className="size-6" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">Google</p>
                <p className="truncate text-xs text-slate-500">{user.has_google ? user.email : "Ulanmagan"}</p>
              </div>
              {user.has_google ? (
                <span className="text-xs font-semibold text-emerald-600">Ulangan</span>
              ) : (
                <button onClick={() => openLogin({ link: true })} className="text-sm font-semibold text-brand hover:underline">
                  Ulash
                </button>
              )}
            </li>
          )}
          <li className="flex items-center gap-3 py-3">
            <span className="grid size-6 place-items-center rounded-full bg-[#229ED9] text-white">
              <Send className="size-3.5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">Telegram</p>
              <p className="truncate text-xs text-slate-500">
                {user.telegram_id ? (user.telegram_username ? `@${user.telegram_username}` : "Ulangan") : "Ulanmagan"}
              </p>
            </div>
            {user.telegram_id ? (
              <span className="text-xs font-semibold text-emerald-600">Ulangan</span>
            ) : (
              <button onClick={() => openLogin({ link: true })} className="text-sm font-semibold text-brand hover:underline">
                Ulash
              </button>
            )}
          </li>
        </ul>
      </Card>
    </div>
  );
}

/* ---------- Buyurtmalar ---------- */

const statusFilters: { id: OrderStatus | "all"; label: string }[] = [
  { id: "all", label: "Barchasi" },
  { id: "pending", label: statusMeta.pending.label },
  { id: "processing", label: statusMeta.processing.label },
  { id: "completed", label: statusMeta.completed.label },
  { id: "cancelled", label: statusMeta.cancelled.label },
];

const PAGE_SIZE = 10;

function OrdersTab() {
  const [filter, setFilter] = useState<OrderStatus | "all">("all");
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const fetchPage = useCallback(
    (offset: number) => {
      const q = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
      if (filter !== "all") q.set("status", filter);
      return api<{ items: Order[]; total: number }>(`/orders?${q}`);
    },
    [filter],
  );

  useEffect(() => {
    let ignore = false;
    fetchPage(0)
      .then((res) => {
        if (ignore) return;
        setOrders(res.items);
        setTotal(res.total);
      })
      .catch((e: Error) => !ignore && setError(e.message));
    return () => {
      ignore = true;
    };
  }, [fetchPage]);

  const loadMore = async () => {
    try {
      const res = await fetchPage(orders?.length ?? 0);
      setOrders((prev) => [...(prev ?? []), ...res.items]);
      setTotal(res.total);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const replace = (o: Order) => setOrders((prev) => prev?.map((x) => (x.id === o.id ? o : x)) ?? null);

  return (
    <Card title="Mening buyurtmalarim">
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        {statusFilters.map((f) => (
          <button
            key={f.id}
            onClick={() => {
              if (f.id === filter) return;
              setOrders(null);
              setError(null);
              setFilter(f.id);
            }}
            className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
              filter === f.id ? "bg-brand text-white" : "bg-slate-50 text-slate-600 ring-1 ring-slate-200 hover:ring-brand"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-3">
        {error && <ErrorText text={error} />}
        {!orders && !error && [0, 1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-2xl bg-slate-50" />)}
        {orders?.length === 0 && <Empty text={filter === "all" ? "Sizda hali buyurtmalar yo‘q." : "Bu holatdagi buyurtmalar yo‘q."} />}
        {orders?.map((o) => (
          <OrderRow
            key={o.id}
            order={o}
            open={openId === o.id}
            onToggle={() => setOpenId(openId === o.id ? null : o.id)}
            onChange={replace}
          />
        ))}
        {orders && orders.length < total && (
          <button
            onClick={loadMore}
            className="w-full rounded-xl py-2.5 text-sm font-semibold text-brand ring-1 ring-slate-200 hover:ring-brand"
          >
            Yana ko‘rsatish
          </button>
        )}
      </div>
    </Card>
  );
}

function OrderRow({
  order,
  open,
  onToggle,
  onChange,
}: {
  order: Order;
  open: boolean;
  onToggle: () => void;
  onChange: (o: Order) => void;
}) {
  const [detail, setDetail] = useState<OrderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (!open) return;
    api<OrderDetail>(`/orders/${order.id}`)
      .then(setDetail)
      .catch((e: Error) => setError(e.message));
  }, [open, order.id, order.status]);

  const cancel = async () => {
    if (!confirm(`${order.number} buyurtmasini bekor qilasizmi?`)) return;
    setCancelling(true);
    try {
      const d = await api<OrderDetail>(`/orders/${order.id}/cancel`, { method: "POST" });
      setDetail(d);
      onChange(d);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className={`rounded-2xl ring-1 transition ${open ? "ring-brand/40" : "ring-slate-100 hover:ring-slate-200"}`}>
      <button onClick={onToggle} aria-expanded={open} className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 p-4 text-left">
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{order.product_name}</p>
          <p className="mt-0.5 text-xs text-slate-500">
            {order.number} · {formatDate(order.created_at)} · {durationText(order.duration_months, order.duration_unit)}
            {order.quantity > 1 && ` · ${order.quantity} ta`}
          </p>
        </div>
        <p className="font-bold">{formatPrice(order.price)} so‘m</p>
        <StatusBadge status={order.status} />
      </button>

      {open && (
        <div className="border-t border-slate-100 p-4">
          {error && <ErrorText text={error} />}
          {!detail && !error && <div className="h-24 animate-pulse rounded-xl bg-slate-50" />}
          {detail && (
            <div className="grid gap-5 md:grid-cols-[1fr_1fr]">
              <div>
                <p className="text-sm font-semibold">Buyurtma tarixi</p>
                <Timeline
                  items={[...detail.events].reverse().map((e) => ({ id: e.id, status: e.status, note: e.note, date: e.created_at }))}
                />
              </div>
              <div className="space-y-3 text-sm">
                {detail.delivery_info && (
                  <div className="rounded-xl bg-emerald-50 p-3.5">
                    <p className="font-semibold text-emerald-800">Faollashtirish ma’lumotlari</p>
                    <p className="mt-1 whitespace-pre-wrap break-words text-emerald-900">
                      <Linkify text={detail.delivery_info} />
                    </p>
                  </div>
                )}
                {detail.comment && (
                  <div className="rounded-xl bg-slate-50 p-3.5">
                    <p className="font-semibold">Izoh</p>
                    <p className="mt-1 whitespace-pre-wrap text-slate-600">{detail.comment}</p>
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  {detail.product_id && (
                    <Link
                      href={`/mahsulotlar/${detail.product_id}`}
                      className="rounded-lg px-4 py-2 font-semibold text-brand ring-1 ring-slate-200 hover:ring-brand"
                    >
                      Qayta xarid qilish
                    </Link>
                  )}
                  {detail.status === "pending" && (
                    <button
                      onClick={cancel}
                      disabled={cancelling}
                      className="rounded-lg px-4 py-2 font-semibold text-rose-600 ring-1 ring-rose-200 hover:bg-rose-50 disabled:opacity-60"
                    >
                      {cancelling ? "Bekor qilinmoqda..." : "Bekor qilish"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Timeline({
  items,
}: {
  items: { id: number; status: OrderStatus; note: string | null; date: string; title?: React.ReactNode }[];
}) {
  return (
    <ol className="mt-3">
      {items.map((e, i) => (
        <li key={e.id} className="relative flex gap-3 pb-5 last:pb-0">
          {i < items.length - 1 && <span className="absolute left-[5px] top-4 h-full w-px bg-slate-200" />}
          <span className={`relative mt-1.5 size-[11px] shrink-0 rounded-full ring-4 ring-white ${statusMeta[e.status].dot}`} />
          <div className="min-w-0">
            {e.title}
            <p className="text-sm font-semibold">{statusMeta[e.status].label}</p>
            {e.note && <p className="text-sm text-slate-600">{e.note}</p>}
            <p className="mt-0.5 text-xs text-slate-400">{formatDate(e.date)}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

/* ---------- Tarix ---------- */

function HistoryTab() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<HistoryItem[]>("/orders/history?limit=100")
      .then(setItems)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <Card title="Buyurtmalar tarixi">
      {error && <ErrorText text={error} />}
      {!items && !error && <div className="h-48 animate-pulse rounded-2xl bg-slate-50" />}
      {items?.length === 0 && <Empty text="Tarix hozircha bo‘sh." />}
      {items && items.length > 0 && (
        <Timeline
          items={items.map((h) => ({
            id: h.id,
            status: h.status,
            note: h.note,
            date: h.created_at,
            title: (
              <p className="text-xs font-medium text-slate-500">
                {h.order_number} · {h.product_name}
              </p>
            ),
          }))}
        />
      )}
    </Card>
  );
}
