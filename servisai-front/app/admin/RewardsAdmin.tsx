"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Close, Gift, Pencil, Plus, Send, Trash, Users } from "../components/icons";
import { api, formatDate, statusMeta, type AdminProduct, type Reward, type RewardGrant, type TopReferrer } from "../lib/api";
import { ErrorText } from "../profil/ui";

export default function RewardsAdmin() {
  const [rewards, setRewards] = useState<Reward[] | null>(null);
  const [grants, setGrants] = useState<RewardGrant[] | null>(null);
  const [top, setTop] = useState<TopReferrer[] | null>(null);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [editing, setEditing] = useState<Reward | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([
      api<Reward[]>("/admin/rewards"),
      api<RewardGrant[]>("/admin/rewards/grants"),
      api<TopReferrer[]>("/admin/referrers"),
      api<AdminProduct[]>("/admin/products"),
    ])
      .then(([r, g, t, p]) => {
        setRewards(r);
        setGrants(g);
        setTop(t);
        setProducts(p);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const toggle = async (r: Reward) => {
    try {
      const updated = await api<Reward>(`/admin/rewards/${r.id}`, {
        method: "PATCH",
        json: { title: r.title, required_friends: r.required_friends, product_id: r.product_id, quantity: r.quantity, is_active: !r.is_active },
      });
      setRewards((list) => list?.map((x) => (x.id === r.id ? updated : x)) ?? null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (r: Reward) => {
    if (!confirm(`“${r.title}” sovg‘asi o‘chirilsinmi?\nAvval berilgan sovg‘alar (buyurtmalar) saqlanib qoladi.`)) return;
    try {
      await api(`/admin/rewards/${r.id}`, { method: "DELETE" });
      setRewards((list) => list?.filter((x) => x.id !== r.id) ?? null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Sovg‘alar</h1>
          <p className="text-sm text-slate-500">Do‘st taklif qilganlarga avtomatik beriladigan bepul servislar</p>
        </div>
        <button
          onClick={() => setEditing("new")}
          className="flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 hover:bg-brand-dark"
        >
          <Plus className="size-4" /> Sovg‘a qo‘shish
        </button>
      </div>

      <div className="rounded-2xl bg-violet-50 px-5 py-4 text-sm leading-relaxed text-violet-900 ring-1 ring-violet-100">
        <b>Qanday ishlaydi:</b> har bir foydalanuvchining shaxsiy havolasi bor (Profil → Do‘stlarni taklif qilish, botda «🎁 Do‘st taklif
        qilish»). Havola orqali yangi odam ro‘yxatdan o‘tsa — do‘st hisoblanadi. Do‘stlar soni shartga yetganda sovg‘a{" "}
        <b>bepul buyurtma</b> sifatida avtomatik beriladi: avtomatik mahsulotda havola darhol, aks holda «Buyurtmalar»da yetkazasiz.
        Yangi qo‘shilgan sovg‘ani shartni avval bajarganlar «Sovg‘ani olish» tugmasi bilan oladi.
      </div>

      {error && <ErrorText text={error} />}

      {!rewards ? (
        <div className="h-32 animate-pulse rounded-3xl bg-white" />
      ) : rewards.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-500">
          Hali sovg‘a yo‘q. Masalan: <b>10 ta do‘st → Gemini Pro</b>
        </div>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {rewards.map((r) => (
            <li key={r.id} className={`rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 ${r.is_active ? "" : "opacity-60"}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-violet-500 to-brand text-white shadow-md shadow-violet-500/25">
                    <Gift className="size-6" />
                  </span>
                  <div>
                    <p className="font-bold">{r.title}</p>
                    <p className="text-sm text-slate-500">
                      <b className="text-slate-800">{r.required_friends} ta do‘st</b> → {r.product_name}
                      {r.quantity > 1 && ` × ${r.quantity}`}
                    </p>
                  </div>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                    r.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {r.is_active ? "Faol" : "O‘chirilgan"}
                </span>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 text-center text-sm">
                <div className="rounded-xl bg-slate-50 py-2">
                  <p className="text-lg font-extrabold">{r.granted_count}</p>
                  <p className="text-xs text-slate-500">berilgan</p>
                </div>
                <div className="rounded-xl bg-slate-50 py-2">
                  <p className="text-lg font-extrabold">{r.eligible_count}</p>
                  <p className="text-xs text-slate-500">shartni bajargan</p>
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <button onClick={() => toggle(r)} className="flex-1 rounded-xl py-2 text-sm font-semibold ring-1 ring-slate-200 hover:ring-brand">
                  {r.is_active ? "O‘chirish" : "Yoqish"}
                </button>
                <button
                  aria-label="Tahrirlash"
                  onClick={() => setEditing(r)}
                  className="grid size-10 place-items-center rounded-xl text-slate-600 ring-1 ring-slate-200 hover:text-brand hover:ring-brand"
                >
                  <Pencil className="size-4.5" />
                </button>
                <button
                  aria-label="O‘chirib tashlash"
                  onClick={() => remove(r)}
                  className="grid size-10 place-items-center rounded-xl text-rose-500 ring-1 ring-slate-200 hover:bg-rose-50 hover:ring-rose-200"
                >
                  <Trash className="size-4.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 sm:p-6">
          <h2 className="text-lg font-bold">Berilgan sovg‘alar</h2>
          {!grants ? (
            <div className="mt-4 h-24 animate-pulse rounded-2xl bg-slate-50" />
          ) : grants.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">Hali hech kimga sovg‘a berilmagan.</p>
          ) : (
            <ul className="mt-4 divide-y divide-slate-100">
              {grants.map((g) => (
                <li key={g.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-3 text-sm">
                  <span className="font-semibold">{g.user_name}</span>
                  {g.user_telegram_username && (
                    <a href={`https://t.me/${g.user_telegram_username}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-brand hover:underline">
                      <Send className="size-3.5" />@{g.user_telegram_username}
                    </a>
                  )}
                  <span className="text-slate-500">— {g.reward_title}</span>
                  <span className="ml-auto flex items-center gap-2">
                    {g.order_status && (
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusMeta[g.order_status].className}`}>
                        {g.order_number} · {statusMeta[g.order_status].label}
                      </span>
                    )}
                    <span className="text-xs text-slate-400">{formatDate(g.created_at)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 sm:p-6">
          <h2 className="flex items-center gap-2 text-lg font-bold">
            <Users className="size-5 text-brand" /> Eng ko‘p taklif qilganlar
          </h2>
          {!top ? (
            <div className="mt-4 h-24 animate-pulse rounded-2xl bg-slate-50" />
          ) : top.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">Hali hech kim do‘st taklif qilmagan.</p>
          ) : (
            <ol className="mt-4 space-y-2">
              {top.map((t, i) => (
                <li key={t.user_id} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2">
                  <span className="grid size-7 place-items-center rounded-full bg-white text-xs font-bold text-slate-600 ring-1 ring-slate-200">{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate text-sm font-semibold">{t.user_name}</span>
                  <span className="text-sm font-bold text-brand">{t.friends} ta</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      {editing && (
        <RewardForm
          reward={editing === "new" ? null : editing}
          products={products}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

const inputCls =
  "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10";

function RewardForm({
  reward,
  products,
  onClose,
  onSaved,
}: {
  reward: Reward | null;
  products: AdminProduct[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [productId, setProductId] = useState(reward?.product_id ?? products[0]?.id ?? "");
  const [friends, setFriends] = useState(String(reward?.required_friends ?? 10));
  const [quantity, setQuantity] = useState(String(reward?.quantity ?? 1));
  const [title, setTitle] = useState(reward?.title ?? "");
  const [active, setActive] = useState(reward?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const product = products.find((p) => p.id === productId);
  const autoTitle = `${friends || "N"} ta do‘st uchun ${product?.name ?? "sovg‘a"}`;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const required = Number(friends);
    const qty = Number(quantity);
    if (!productId) return setError("Mahsulotni tanlang");
    if (!Number.isInteger(required) || required < 1) return setError("Do‘stlar soni kamida 1 bo‘lsin");
    if (!Number.isInteger(qty) || qty < 1) return setError("Soni kamida 1 bo‘lsin");
    setBusy(true);
    setError(null);
    try {
      const body = { title: title.trim() || autoTitle, required_friends: required, product_id: productId, quantity: qty, is_active: active };
      await api(reward ? `/admin/rewards/${reward.id}` : "/admin/rewards", { method: reward ? "PATCH" : "POST", json: body });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:p-8" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <form onSubmit={submit} className="mx-auto w-full max-w-lg rounded-3xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 className="text-lg font-bold">{reward ? "Sovg‘ani tahrirlash" : "Yangi sovg‘a"}</h2>
          <button type="button" aria-label="Yopish" onClick={onClose} className="grid size-9 place-items-center rounded-lg hover:bg-slate-100">
            <Close className="size-5" />
          </button>
        </div>
        <div className="space-y-4 p-6">
          <div className="grid grid-cols-[1fr_auto] items-end gap-3">
            <label className="block">
              <span className="text-sm font-semibold">Necha do‘st taklif qilsa</span>
              <input value={friends} onChange={(e) => setFriends(e.target.value.replace(/\D/g, "").slice(0, 5))} inputMode="numeric" className={`mt-1.5 ${inputCls}`} />
            </label>
            <span className="pb-2.5 text-2xl">→</span>
          </div>
          <label className="block">
            <span className="text-sm font-semibold">Nima beriladi (mahsulot)</span>
            <select value={productId} onChange={(e) => setProductId(e.target.value)} className={`mt-1.5 ${inputCls}`}>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} {p.delivery_mode === "auto" ? `(avtomatik, havolalar: ${p.stock ?? 0})` : "(qo‘lda yetkaziladi)"}
                </option>
              ))}
            </select>
            {product?.delivery_mode === "auto" && (product.stock ?? 0) === 0 && (
              <span className="mt-1 block text-xs text-amber-600">⚠️ Havolalar qolmagan — sovg‘a berilganda uni qo‘lda yetkazasiz.</span>
            )}
          </label>
          <label className="block">
            <span className="text-sm font-semibold">Soni</span>
            <input value={quantity} onChange={(e) => setQuantity(e.target.value.replace(/\D/g, "").slice(0, 3))} inputMode="numeric" className={`mt-1.5 max-w-32 ${inputCls}`} />
          </label>
          <label className="block">
            <span className="text-sm font-semibold">Nomi</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={255} placeholder={autoTitle} className={`mt-1.5 ${inputCls}`} />
            <span className="mt-1 block text-xs text-slate-500">Bo‘sh qolsa: “{autoTitle}”</span>
          </label>
          <label className="flex cursor-pointer items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-brand" />
            <span className="font-semibold">Faol (foydalanuvchilarga ko‘rinadi va beriladi)</span>
          </label>
          {error && <ErrorText text={error} />}
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4">
          <button type="button" onClick={onClose} className="rounded-xl px-5 py-2.5 text-sm font-semibold ring-1 ring-slate-200">
            Bekor qilish
          </button>
          <button disabled={busy} className="rounded-xl bg-brand px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-60">
            {busy ? "Saqlanmoqda..." : "Saqlash"}
          </button>
        </div>
      </form>
    </div>
  );
}
