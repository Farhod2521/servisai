"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Eye, EyeOff, Pencil, Plus, Search, Trash } from "../components/icons";
import { api, type AdminProduct } from "../lib/api";
import { invalidateProducts } from "../lib/products";
import { badgeStyles, catalogCategories, formatPrice, toCatalogProduct } from "../mahsulotlar/catalog-data";

function StockPill({ stock }: { stock: number | null }) {
  const [text, cls] =
    stock === null
      ? ["Cheklanmagan", "bg-slate-100 text-slate-500"]
      : stock === 0
        ? ["Tugagan", "bg-slate-800 text-white"]
        : [`Qoldi: ${stock} ta`, stock <= 3 ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"];
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${cls}`}>{text}</span>;
}
import { ErrorText } from "../profil/ui";
import DeliveryItemsDialog from "./DeliveryItemsDialog";
import ProductForm from "./ProductForm";

export default function ProductsAdmin({ startWithNew, onNewHandled }: { startWithNew: boolean; onNewHandled: () => void }) {
  const [products, setProducts] = useState<AdminProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  // null — forma yopiq, "new" — yangi mahsulot, aks holda tahrirlanayotgan mahsulot
  const [editing, setEditing] = useState<AdminProduct | "new" | null>(startWithNew ? "new" : null);
  // Havolalar oynasi ochilgan mahsulot id’si
  const [itemsFor, setItemsFor] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    api<AdminProduct[]>("/admin/products")
      .then(setProducts)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  // Dashboard’dagi "Mahsulot qo‘shish" orqali kelganda URL’dagi belgini olib tashlaymiz
  useEffect(() => {
    if (startWithNew) onNewHandled();
  }, [startWithNew, onNewHandled]);

  const saved = (product: AdminProduct) => {
    setProducts((list) => {
      if (!list) return [product];
      const exists = list.some((p) => p.id === product.id);
      const next = exists ? list.map((p) => (p.id === product.id ? product : p)) : [...list, product];
      return next.sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));
    });
    invalidateProducts();
    setEditing(null);
  };

  const toggleActive = async (p: AdminProduct) => {
    setBusyId(p.id);
    setError(null);
    try {
      saved(await api<AdminProduct>(`/admin/products/${p.id}`, { method: "PATCH", json: { is_active: !p.is_active } }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (p: AdminProduct) => {
    if (!confirm(`“${p.name}” mahsuloti butunlay o‘chirilsinmi?\n\nBuyurtmalar tarixi saqlanib qoladi. Vaqtincha yashirish uchun ko‘z tugmasidan foydalaning.`)) {
      return;
    }
    setBusyId(p.id);
    setError(null);
    try {
      await api(`/admin/products/${p.id}`, { method: "DELETE" });
      setProducts((list) => list?.filter((x) => x.id !== p.id) ?? null);
      invalidateProducts();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const q = query.trim().toLowerCase();
  const visible = (products ?? []).filter((p) => !q || p.name.toLowerCase().includes(q) || p.id.includes(q));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Mahsulotlar</h1>
          <p className="text-sm text-slate-500">
            {products ? `${products.length} ta mahsulot · ${products.filter((p) => p.is_active).length} tasi saytda` : "Yuklanmoqda..."}
          </p>
        </div>
        <button
          onClick={() => setEditing("new")}
          className="flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition hover:bg-brand-dark"
        >
          <Plus className="size-4" /> Mahsulot qo‘shish
        </button>
      </div>

      <label className="relative block max-w-sm">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Nomi yoki ID bo‘yicha qidirish"
          className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-4 text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
        />
      </label>

      {error && <ErrorText text={error} />}

      {!products && !error ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-3xl bg-white" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-500">
          {q ? "Hech narsa topilmadi." : "Hali mahsulot yo‘q. Birinchisini qo‘shing!"}
        </div>
      ) : (
        <ul className="space-y-3">
          {visible.map((p) => {
            const category = catalogCategories.find((c) => c.id === p.category);
            const badge = p.badge && badgeStyles[p.badge];
            const busy = busyId === p.id;
            return (
              <li
                key={p.id}
                className={`flex flex-col gap-4 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-100 sm:flex-row sm:items-center ${
                  p.is_active ? "" : "opacity-60"
                } ${p.stock === 0 ? "grayscale" : ""}`}
              >
                <div className="size-14 shrink-0 text-sm">{toCatalogProduct(p).logo}</div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-bold">{p.name}</p>
                    {badge && <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.className}`}>{badge.label}</span>}
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                        p.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {p.is_active ? "Saytda" : "Yashirin"}
                    </span>
                    <StockPill stock={p.stock} />
                    <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700">Sotilgan: {p.sold_count} ta</span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-400">
                    /{p.id} · {category?.label ?? p.category} · {p.durations.join("/")} {p.duration_unit === "day" ? "kun" : "oy"} · tartib {p.sort_order}
                  </p>
                  <p className="mt-1 line-clamp-1 text-sm text-slate-500">{p.description || "Tavsif yozilmagan"}</p>
                </div>

                <div className="flex items-center justify-between gap-4 sm:justify-end">
                  <div className="text-right">
                    <p className="whitespace-nowrap font-bold">{formatPrice(p.price)} so‘m</p>
                    {p.old_price && <p className="text-xs text-slate-400 line-through">{formatPrice(p.old_price)} so‘m</p>}
                  </div>
                  <div className="flex gap-1">
                    {p.delivery_mode === "auto" && (
                      <button
                        type="button"
                        onClick={() => setItemsFor(p.id)}
                        className={`flex h-10 items-center gap-1.5 whitespace-nowrap rounded-xl px-3 text-sm font-semibold ring-1 transition ${
                          (p.stock ?? 0) === 0
                            ? "bg-rose-50 text-rose-600 ring-rose-200 hover:ring-rose-400"
                            : "bg-brand-soft text-brand ring-brand/20 hover:ring-brand"
                        }`}
                      >
                        🔗 Havolalar: {p.stock ?? 0}
                      </button>
                    )}
                    <IconButton label={p.is_active ? "Saytdan yashirish" : "Saytda ko‘rsatish"} disabled={busy} onClick={() => toggleActive(p)}>
                      {p.is_active ? <Eye className="size-4.5" /> : <EyeOff className="size-4.5" />}
                    </IconButton>
                    <IconButton label="Tahrirlash" disabled={busy} onClick={() => setEditing(p)}>
                      <Pencil className="size-4.5" />
                    </IconButton>
                    <IconButton label="O‘chirish" disabled={busy} danger onClick={() => remove(p)}>
                      <Trash className="size-4.5" />
                    </IconButton>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {products && products.some((p) => p.is_active) && (
        <p className="text-xs text-slate-400">
          O‘zgarishlar saytda darhol ko‘rinadi:{" "}
          <Link href="/mahsulotlar" className="font-semibold text-brand hover:underline">
            katalogni ochish
          </Link>
        </p>
      )}

      {itemsFor && products?.find((p) => p.id === itemsFor) && (
        <DeliveryItemsDialog
          product={products.find((p) => p.id === itemsFor)!}
          onClose={() => setItemsFor(null)}
          onStockChange={(stock) => setProducts((list) => list?.map((x) => (x.id === itemsFor ? { ...x, stock } : x)) ?? null)}
        />
      )}

      {editing && (
        <ProductForm
          product={editing === "new" ? null : editing}
          takenIds={(products ?? []).map((p) => p.id)}
          nextSortOrder={Math.max(0, ...(products ?? []).map((p) => p.sort_order)) + 1}
          onClose={() => setEditing(null)}
          onSaved={saved}
        />
      )}
    </div>
  );
}

function IconButton({
  label,
  danger,
  disabled,
  onClick,
  children,
}: {
  label: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={`grid size-10 place-items-center rounded-xl ring-1 ring-slate-200 transition disabled:opacity-50 ${
        danger ? "text-rose-500 hover:bg-rose-50 hover:ring-rose-200" : "text-slate-600 hover:bg-brand-soft hover:text-brand hover:ring-brand/30"
      }`}
    >
      {children}
    </button>
  );
}
