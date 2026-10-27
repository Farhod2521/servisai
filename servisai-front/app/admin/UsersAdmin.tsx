"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Avatar } from "../components/auth/UserMenu";
import { ChevronDown, Search, Send, Users, Wallet } from "../components/icons";
import { api, formatDate, type AdminUserList } from "../lib/api";
import { formatPrice } from "../mahsulotlar/catalog-data";
import { ErrorText } from "../profil/ui";
import UserDetailDialog from "./UserDetailDialog";

const PAGE = 50;

const sortOptions = [
  { id: "new", label: "Yangi qo‘shilganlar" },
  { id: "balance", label: "Balansi ko‘p" },
  { id: "spent", label: "Ko‘p xarid qilganlar" },
  { id: "last_login", label: "Oxirgi kirganlar" },
] as const;
type Sort = (typeof sortOptions)[number]["id"];

export default function UsersAdmin() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("new");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<AdminUserList | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Batafsil ko‘rilayotgan foydalanuvchi
  const [openUser, setOpenUser] = useState<number | null>(null);

  // Har harfda so‘rov yubormaslik uchun biroz kutamiz
  useEffect(() => {
    const id = setTimeout(() => {
      setSearch(query.trim());
      setPage(0);
    }, 350);
    return () => clearTimeout(id);
  }, [query]);

  useEffect(() => {
    let alive = true;
    const params = new URLSearchParams({ sort, limit: String(PAGE), offset: String(page * PAGE) });
    if (search) params.set("q", search);
    api<AdminUserList>(`/admin/users?${params}`)
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [search, sort, page]);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Foydalanuvchilar</h1>
        <p className="text-sm text-slate-500">
          Saytga kirgan barcha foydalanuvchilar. Batafsil (to‘ldirishlar, xaridlar, berilgan havolalar) uchun qatorni bosing.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon={<Users className="size-5" />} tone="bg-violet-50 text-violet-600" label="Foydalanuvchilar" value={data ? (search ? `${data.total} ta topildi` : data.total) : "…"} />
        <Stat
          icon={<Wallet className="size-5" />}
          tone="bg-emerald-50 text-emerald-600"
          label="Hisoblardagi jami mablag‘"
          value={data ? `${formatPrice(data.total_balance)} so‘m` : "…"}
        />
        <Stat icon={<Wallet className="size-5" />} tone="bg-brand-soft text-brand" label="Balansi bor" value={data ? `${data.users_with_balance} ta` : "…"} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="relative block min-w-0 flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ism, @username, telefon yoki Telegram ID"
            className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-4 text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
          />
        </label>
        <div className="relative">
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value as Sort);
              setPage(0);
            }}
            aria-label="Saralash"
            className="h-11 appearance-none rounded-xl bg-white pl-4 pr-10 text-sm font-medium ring-1 ring-slate-200 outline-none focus:ring-brand"
          >
            {sortOptions.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 size-4 -translate-y-1/2" />
        </div>
      </div>

      {error && <ErrorText text={error} />}

      <div className="overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ring-slate-100">
        {!data && !error ? (
          <div className="space-y-3 p-5">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded-2xl bg-slate-50" />
            ))}
          </div>
        ) : data && data.items.length === 0 ? (
          <p className="px-6 py-12 text-center text-sm text-slate-500">{search ? "Hech kim topilmadi." : "Hali foydalanuvchilar yo‘q."}</p>
        ) : (
          data && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead className="border-b border-slate-100 bg-slate-50/60 text-xs uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Foydalanuvchi</th>
                    <th className="px-3 py-3 font-semibold">Aloqa</th>
                    <th className="px-3 py-3 text-right font-semibold">Balans</th>
                    <th className="px-3 py-3 text-right font-semibold">Xaridlar</th>
                    <th className="px-3 py-3 font-semibold">Ro‘yxatdan o‘tgan</th>
                    <th className="px-5 py-3 font-semibold">Oxirgi kirish</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((u) => (
                    <tr key={u.id} onClick={() => setOpenUser(u.id)} className="cursor-pointer hover:bg-brand-soft/40">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar user={u} className="size-10" />
                          <div className="min-w-0">
                            <p className="flex items-center gap-2 font-semibold">
                              <button type="button" className="max-w-48 truncate text-left hover:text-brand">
                                {u.full_name || "—"}
                              </button>
                              {u.is_admin && <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[10px] font-bold text-brand">ADMIN</span>}
                            </p>
                            <p className="text-xs text-slate-400">ID {u.id}{u.telegram_id && ` · TG ${u.telegram_id}`}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        {u.telegram_username && (
                          <a
                            href={`https://t.me/${u.telegram_username}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-1.5 text-brand hover:underline"
                          >
                            <Send className="size-3.5" /> @{u.telegram_username}
                          </a>
                        )}
                        {u.phone && <p className="text-slate-600">{u.phone}</p>}
                        {u.email && <p className="max-w-52 truncate text-xs text-slate-500">{u.email}</p>}
                        {!u.telegram_username && !u.phone && !u.email && <span className="text-slate-400">—</span>}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right">
                        <span
                          className={`rounded-lg px-2.5 py-1 font-bold ${
                            u.balance > 0 ? "bg-emerald-50 text-emerald-700" : "text-slate-400"
                          }`}
                        >
                          {formatPrice(u.balance)} so‘m
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right">
                        <p className="font-semibold">{formatPrice(u.total_spent)} so‘m</p>
                        <p className="text-xs text-slate-400">{u.orders_count} ta buyurtma</p>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-slate-600">{formatDate(u.created_at, false)}</td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-600">{u.last_login_at ? formatDate(u.last_login_at) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>

      {data && pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            {page + 1} / {pages} sahifa
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-xl px-4 py-2 font-semibold ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-40"
            >
              Oldingi
            </button>
            <button
              disabled={page + 1 >= pages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-xl px-4 py-2 font-semibold ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-40"
            >
              Keyingi
            </button>
          </div>
        </div>
      )}

      {openUser !== null && <UserDetailDialog userId={openUser} onClose={() => setOpenUser(null)} />}
    </div>
  );
}

function Stat({ icon, tone, label, value }: { icon: ReactNode; tone: string; label: string; value: ReactNode }) {
  return (
    <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
      <div className="flex items-center gap-3">
        <span className={`grid size-10 place-items-center rounded-xl ${tone}`}>{icon}</span>
        <span className="text-sm font-medium text-slate-500">{label}</span>
      </div>
      <p className="mt-3 text-2xl font-extrabold tracking-tight">{value}</p>
    </div>
  );
}
