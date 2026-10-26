"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import Header from "../components/Header";
import { Cart, ChevronDown, ChevronRight, Grid, Heart, ListIcon, Star } from "../components/icons";
import {
  badgeStyles,
  bannerLogos,
  catalogCategories,
  catalogProducts,
  discountPercent,
  formatCount,
  formatPrice,
  productTypes,
  sellers,
  type CatalogCategory,
  type CatalogProduct,
} from "./catalog-data";

const sortOptions = [
  { id: "popular", label: "Ommabop" },
  { id: "cheap", label: "Arzonroq" },
  { id: "expensive", label: "Qimmatroq" },
  { id: "rating", label: "Reyting bo‘yicha" },
  { id: "new", label: "Yangilari" },
] as const;
type SortId = (typeof sortOptions)[number]["id"];


export default function Catalog() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<CatalogCategory | "all">("all");
  const [sort, setSort] = useState<SortId>("popular");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [favorites, setFavorites] = useState<Set<string>>(new Set());

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: catalogProducts.length };
    for (const p of catalogProducts) counts[p.category] = (counts[p.category] ?? 0) + 1;
    return counts;
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = catalogProducts.filter(
      (p) =>
        (category === "all" || p.category === category) &&
        (!q || p.name.toLowerCase().includes(q) || p.description.toLowerCase().includes(q)),
    );
    const sorters: Record<SortId, (a: CatalogProduct, b: CatalogProduct) => number> = {
      popular: (a, b) => a.rank - b.rank,
      cheap: (a, b) => a.price - b.price,
      expensive: (a, b) => b.price - a.price,
      rating: (a, b) => b.rating - a.rating || b.reviews - a.reviews,
      new: (a, b) => b.addedAt - a.addedAt,
    };
    return list.sort(sorters[sort]);
  }, [query, category, sort]);

  const resetFilters = () => {
    setQuery("");
    setCategory("all");
  };

  const toggleFavorite = (id: string) =>
    setFavorites((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const activeCategory = catalogCategories.find((c) => c.id === category)!;
  // Mahsuloti yo‘q kategoriyalar ko‘rsatilmaydi
  const shownCategories = catalogCategories.filter((c) => categoryCounts[c.id]);

  return (
    <>
      <Header search={{ value: query, onChange: setQuery }} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        {/* Banner */}
        <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#f7f9fe] via-[#eef3ff] to-[#dfe7ff] px-5 py-6 ring-1 ring-slate-100 sm:px-8 sm:py-7">
          <FloatingLogos />
          <div className="relative">
            <nav className="flex items-center gap-1.5 text-xs text-slate-500">
              <Link href="/" className="hover:text-brand">Bosh sahifa</Link>
              <ChevronRight className="size-3" />
              <span>Servislar</span>
            </nav>
            <h1 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-5xl">
              {category === "all" ? "Barcha servislar" : activeCategory.label}
            </h1>
            <p className="mt-3 max-w-xl text-sm text-slate-600 sm:text-base lg:max-w-md">
              Zamonaviy AI va premium servislarni bir joyda. Tez, ishonchli va arzon narxda.
            </p>
          </div>

          <div className="relative -mx-5 mt-6 flex gap-3 overflow-x-auto px-5 pb-1 [scrollbar-width:none] sm:-mx-8 sm:px-8 [&::-webkit-scrollbar]:hidden">
            {shownCategories.map((c) => {
              const active = category === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setCategory(c.id)}
                  className={`flex shrink-0 items-center gap-2 rounded-xl px-5 py-3 text-sm font-medium transition ${
                    active
                      ? "bg-brand text-white shadow-lg shadow-blue-600/25"
                      : "bg-white text-slate-700 shadow-sm ring-1 ring-slate-100 hover:text-brand"
                  }`}
                >
                  {c.id !== "all" && c.icon}
                  {c.label}
                  <span className={active ? "text-white/80" : "text-slate-400"}>({categoryCounts[c.id] ?? 0})</span>
                </button>
              );
            })}
          </div>
        </section>

        {/* Toolbar */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <p className="font-semibold">
            {visible.length} ta mahsulot topildi
            {query.trim() && <span className="font-normal text-muted"> “{query.trim()}” bo‘yicha</span>}
          </p>

          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-slate-600 sm:inline">Saralash:</span>
            <div className="relative">
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortId)}
                className="h-11 appearance-none rounded-xl bg-white pl-4 pr-10 text-sm font-medium shadow-sm ring-1 ring-slate-200 outline-none focus:ring-brand"
              >
                {sortOptions.map((o) => (
                  <option key={o.id} value={o.id}>{o.label}</option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 size-4 -translate-y-1/2" />
            </div>
            <div className="hidden rounded-xl bg-white p-1 shadow-sm ring-1 ring-slate-200 sm:flex">
              {(["grid", "list"] as const).map((v) => (
                <button
                  key={v}
                  aria-label={v === "grid" ? "Katak ko‘rinish" : "Ro‘yxat ko‘rinish"}
                  onClick={() => setView(v)}
                  className={`grid size-9 place-items-center rounded-lg transition ${view === v ? "bg-brand-soft text-brand" : "text-slate-500 hover:text-brand"}`}
                >
                  {v === "grid" ? <Grid className="size-4.5" /> : <ListIcon className="size-4.5" />}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Mahsulotlar */}
        {visible.length > 0 ? (
          <div className={view === "grid" ? "mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" : "mt-5 space-y-4"}>
            {visible.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                view={view}
                favorite={favorites.has(p.id)}
                onFavorite={() => toggleFavorite(p.id)}
              />
            ))}
          </div>
        ) : (
          <div className="mt-5 rounded-3xl bg-white px-6 py-16 text-center ring-1 ring-slate-100">
            <p className="text-lg font-semibold">Hech narsa topilmadi</p>
            <p className="mt-1 text-sm text-muted">Boshqa so‘z bilan qidirib ko‘ring.</p>
            <button onClick={resetFilters} className="mt-5 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white">
              Barcha servislarni ko‘rsatish
            </button>
          </div>
        )}
      </main>
    </>
  );
}

/* ---------- Kichik komponentlar ---------- */

function ProductCard({
  product: p,
  view,
  favorite,
  onFavorite,
}: {
  product: CatalogProduct;
  view: "grid" | "list";
  favorite: boolean;
  onFavorite: () => void;
}) {
  const discount = discountPercent(p);
  const badge = p.badge && badgeStyles[p.badge];
  const durationLabel = `${p.durations.join("/")} oy`;
  const sellerLabel = sellers.find((s) => s.id === p.seller)!.short;
  const typeLabel = productTypes.find((t) => t.id === p.type)!.short;

  const heart = (
    <button
      aria-label={favorite ? "Sevimlilardan olib tashlash" : "Sevimlilarga qo‘shish"}
      aria-pressed={favorite}
      onClick={onFavorite}
      className={`grid size-8 place-items-center rounded-full transition hover:bg-rose-50 ${favorite ? "text-rose-500" : "text-slate-500"}`}
    >
      <Heart className="size-5" fill={favorite ? "currentColor" : "none"} />
    </button>
  );

  const badges = (
    <div className="flex flex-col items-end gap-1.5">
      {badge && <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${badge.className}`}>{badge.label}</span>}
      {discount > 0 && <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[11px] font-bold text-white">-{discount}%</span>}
    </div>
  );

  const chips = (
    <div className="flex flex-wrap gap-1.5">
      {[sellerLabel, typeLabel, durationLabel].map((c) => (
        <span key={c} className="rounded-md bg-slate-50 px-2 py-1 text-[11px] text-slate-500 ring-1 ring-slate-100">{c}</span>
      ))}
    </div>
  );

  const price = (
    <div>
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-xl font-bold">{formatPrice(p.price)} so‘m</span>
        {p.oldPrice && <span className="text-xs text-slate-400 line-through">{formatPrice(p.oldPrice)} so‘m</span>}
      </p>
      <p className="text-xs text-slate-400">/ {p.durations[0]} oy</p>
    </div>
  );

  const stats = (
    <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
      <span className="flex items-center gap-1">
        <Star className="size-4 text-amber-400" /> {p.rating.toFixed(1)} ({formatCount(p.reviews)})
      </span>
      <span>{formatCount(p.sold)}+ sotilgan</span>
    </div>
  );

  const href = `/mahsulotlar/${p.id}`;

  const buy = (
    <Link
      href={href}
      className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand py-3 text-sm font-semibold text-white transition hover:bg-brand-dark active:scale-[0.98]"
    >
      <Cart className="size-4.5" /> Sotib olish
    </Link>
  );

  if (view === "list") {
    return (
      <article className="flex flex-col gap-5 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 transition hover:shadow-lg hover:shadow-blue-900/5 sm:flex-row sm:items-center">
        <Link href={href} className="size-20 shrink-0">{p.logo}</Link>
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-bold"><Link href={href} className="hover:text-brand">{p.name}</Link></h3>
            {badge && <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${badge.className}`}>{badge.label}</span>}
            {discount > 0 && <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[11px] font-bold text-white">-{discount}%</span>}
          </div>
          <p className="text-sm text-slate-500">{p.description}</p>
          {chips}
        </div>
        <div className="flex shrink-0 flex-col gap-3 sm:w-56">
          <div className="flex items-start justify-between">
            {price}
            {heart}
          </div>
          {stats}
          {buy}
        </div>
      </article>
    );
  }

  return (
    <article className="flex flex-col rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-100 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-blue-900/5">
      <div className="flex items-start justify-between gap-2">
        <Link href={href} className="size-[72px] shrink-0">{p.logo}</Link>
        <div className="flex items-start gap-1">
          {badges}
          {heart}
        </div>
      </div>
      <h3 className="mt-4 font-bold"><Link href={href} className="hover:text-brand">{p.name}</Link></h3>
      <p className="mt-1 line-clamp-2 min-h-10 text-sm text-slate-500">{p.description}</p>
      <div className="mt-3">{chips}</div>
      <div className="mt-4 flex-1">{price}</div>
      <div className="mt-3">{stats}</div>
      <div className="mt-3">{buy}</div>
    </article>
  );
}

const floatPositions = [
  "right-[30%] top-8 size-20 -rotate-6",
  "right-[16%] top-4 size-20 rotate-3",
  "right-6 top-10 size-20 rotate-6",
];

function FloatingLogos() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 hidden lg:block">
      <div className="absolute -right-10 -top-16 size-80 rounded-full bg-violet-300/30 blur-3xl" />
      <div className="absolute right-1/4 -top-10 size-60 rounded-full bg-sky-300/30 blur-3xl" />
      {bannerLogos.map((logo, i) => (
        <div key={i} className={`absolute drop-shadow-xl ${floatPositions[i]}`}>
          {logo}
        </div>
      ))}
    </div>
  );
}
