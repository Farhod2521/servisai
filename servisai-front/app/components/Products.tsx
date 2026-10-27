"use client";

import Link from "next/link";
import { useState } from "react";
import { useProducts } from "../lib/products";
import { type CatalogProduct, discountPercent, durationText, formatPrice, isSoldOut, stockLabel, toCatalogProduct } from "../mahsulotlar/catalog-data";
import { categories, type CategoryId } from "./data";
import { ArrowRight, Bolt, Cart, CheckCircle, Gift, Headset, Shield, Star } from "./icons";

// Bosh sahifada ko‘rsatiladigan servislar soni (tartib admin paneldagi "Tartib raqami" bo‘yicha), qolganlari — katalogda
const LIMIT = 3;
// Kartochkadagi imkoniyatlar soni (admin paneldagi "Nimalar kiradi?" ro‘yxatining boshidan)
const FEATURES_SHOWN = 3;

// Har bir servisning brend rangi: yuqoridagi yorug‘lik va belgi rangi
const accents: Record<string, { glow: string; check: string }> = {
  "chatgpt-plus": { glow: "bg-emerald-200/50", check: "text-emerald-500" },
  "capcut-pro": { glow: "bg-slate-300/50", check: "text-emerald-500" },
  "gemini-advanced": { glow: "bg-violet-200/60", check: "text-violet-500" },
};
const defaultAccent = { glow: "bg-blue-200/50", check: "text-brand" };

const trust = [
  { icon: Bolt, label: "Tez faollashtirish" },
  { icon: Shield, label: "100% ishonchli" },
  { icon: Headset, label: "24/7 qo‘llab-quvvatlash" },
  { icon: Star, label: "Minglab faol mijozlar" },
];

export default function Products() {
  const { products, loading } = useProducts();
  const [active, setActive] = useState<CategoryId>("all");
  const visible = (products ?? [])
    // Bosh sahifada "Boshqa" ijtimoiy tarmoqlarni ham o‘z ichiga oladi
    .filter((p) => active === "all" || p.category === active || (active === "other" && p.category === "social"))
    .slice(0, LIMIT)
    .map(toCatalogProduct);

  return (
    <section id="mahsulotlar" className="relative isolate mx-auto max-w-7xl scroll-mt-20 px-4 py-12 sm:px-6">
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6 sm:gap-4">
        {categories.map((c) => {
          const isActive = c.id === active;
          return (
            <button
              key={c.id}
              onClick={() => setActive(c.id)}
              className={`flex flex-col items-center gap-2 rounded-2xl px-2 py-4 text-xs font-medium transition sm:text-sm ${
                isActive
                  ? "bg-brand text-white shadow-lg shadow-blue-600/30"
                  : "bg-white text-slate-700 shadow-sm ring-1 ring-slate-100 hover:-translate-y-0.5 hover:text-brand hover:shadow-md"
              }`}
            >
              <span className={isActive ? "text-white" : "text-brand"}>{c.icon}</span>
              {c.label}
            </button>
          );
        })}
      </div>

      {/* Fon bezaklari */}
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-40 -z-10 h-[640px] overflow-hidden">
        <div className="absolute -left-40 bottom-0 size-96 rounded-full bg-blue-100/60 blur-3xl" />
        <div className="absolute -right-32 top-0 size-[28rem] rounded-full bg-indigo-100/50 blur-3xl" />
      </div>

      <div className="mt-16 text-center">
        <span className="inline-flex items-center gap-2 rounded-full bg-brand-soft px-5 py-2 text-sm font-semibold text-brand">
          <Bolt className="size-4" /> Mashhur mahsulotlar
        </span>
        <h2 className="mt-4 text-3xl font-extrabold tracking-tight sm:text-5xl">
          Eng ommabop <span className="text-brand">servislar</span>
        </h2>
        <p className="mt-3 text-slate-500 sm:text-lg">Minglab foydalanuvchilar tanlagan ishonchli xizmatlar</p>
      </div>

      <div className="mx-auto mt-10 grid max-w-6xl grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {loading &&
          [0, 1, 2].map((i) => <div key={i} className="h-[540px] animate-pulse rounded-[2rem] bg-white ring-1 ring-slate-100" />)}
        {visible.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}
        {!loading && visible.length === 0 && (
          <p className="col-span-full py-10 text-center text-muted">Bu kategoriyada hozircha servislar yo‘q.</p>
        )}
      </div>

      <div className="mt-10 text-center">
        <Link
          href="/mahsulotlar"
          className="group inline-flex items-center gap-2.5 rounded-2xl bg-white px-8 py-4 text-base font-semibold text-brand shadow-md shadow-blue-900/5 ring-1 ring-brand/20 transition hover:bg-brand hover:text-white hover:shadow-lg hover:shadow-blue-600/25"
        >
          Barchasini ko‘rish
          {products && products.length > LIMIT && (
            <span className="rounded-full bg-brand-soft px-2 py-0.5 text-xs font-bold text-brand transition group-hover:bg-white/20 group-hover:text-white">
              {products.length} ta
            </span>
          )}
          <ArrowRight className="size-5 transition group-hover:translate-x-1" />
        </Link>
      </div>

      <ul className="mx-auto mt-12 flex max-w-4xl flex-wrap items-center justify-center gap-y-4 text-sm text-slate-600">
        {trust.map(({ icon: Icon, label }, i) => (
          <li key={label} className={`flex items-center gap-2.5 px-6 ${i > 0 ? "sm:border-l sm:border-slate-200" : ""}`}>
            <Icon className="size-5 text-brand" /> {label}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ProductCard({ product: p }: { product: CatalogProduct }) {
  const discount = discountPercent(p);
  const accent = accents[p.id] ?? defaultAccent;
  const features = p.features.slice(0, FEATURES_SHOWN);
  const soldOut = isSoldOut(p);
  const stock = stockLabel(p);

  return (
    <article
      className={`group relative flex flex-col overflow-hidden rounded-[2rem] p-7 ring-1 transition ${
        soldOut
          ? "bg-slate-50 ring-slate-200 grayscale"
          : "bg-white shadow-[0_10px_40px_-12px_rgb(15_40_120/0.12)] ring-slate-100 hover:-translate-y-1 hover:shadow-[0_20px_50px_-12px_rgb(15_40_120/0.2)]"
      }`}
    >
      {/* Servis rangidagi yumshoq yorug‘lik */}
      <div aria-hidden className={`pointer-events-none absolute -right-16 -top-20 h-56 w-80 rotate-[-12deg] rounded-full blur-3xl ${accent.glow}`} />

      <div className="relative flex items-start justify-between gap-3">
        <div className="size-24 shrink-0 text-xl shadow-xl shadow-slate-900/10 [&>*]:rounded-3xl rounded-3xl">{p.logo}</div>
        {soldOut ? (
          <span className="rounded-xl bg-slate-900 px-3 py-1.5 text-sm font-extrabold uppercase tracking-wide text-white">Tugagan</span>
        ) : (
          discount > 0 && (
            <span className="rounded-xl bg-rose-500 px-3 py-1.5 text-sm font-extrabold text-white shadow-lg shadow-rose-500/30">
              −{discount}%
            </span>
          )
        )}
      </div>

      <h3 className="relative mt-6 text-2xl font-bold tracking-tight">{p.name}</h3>
      <p className="relative mt-2 min-h-12 text-[15px] leading-relaxed text-slate-500">{p.description}</p>

      <div className="relative mt-5 flex-1 border-t border-slate-100 pt-5">
        {features.length > 0 && (
          <ul className="space-y-3">
            {features.map((f) => (
              <li key={f} className="flex items-start gap-3 text-sm text-slate-700">
                <CheckCircle className={`mt-px size-5 shrink-0 ${accent.check}`} /> {f}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="relative mt-6 flex items-end justify-between gap-3">
        <div className="min-w-0">
          {/* Chegirmasiz kartochkalar ham bir xil balandlikda turishi uchun joy saqlanadi */}
          <p className="h-6 text-base text-slate-400">
            {p.old_price && <span className="line-through decoration-rose-500 decoration-2">{formatPrice(p.old_price)} so‘m</span>}
          </p>
          <p className="whitespace-nowrap text-[2rem] font-extrabold leading-tight tracking-tight">
            {formatPrice(p.price)} <span className="text-lg font-bold">so‘m</span>
          </p>
          <p className="text-slate-500">/ {durationText(p.durations[0], p.duration_unit)}</p>
        </div>
        {p.old_price && (
          <div className="flex shrink-0 items-center gap-2.5 rounded-2xl bg-emerald-50 px-3.5 py-3 text-emerald-700">
            <Gift className="size-6 shrink-0" />
            <p className="text-[13px] font-semibold leading-tight">
              {formatPrice(p.old_price - p.price)} so‘m
              <br />
              tejaysiz
            </p>
          </div>
        )}
      </div>

      {(stock || p.sold_count > 0) && (
        <div className="relative mt-5 flex items-center justify-between gap-3 text-sm">
          {stock ? (
            <span
              className={`flex items-center gap-2 font-semibold ${
                soldOut ? "text-slate-500" : p.stock !== null && p.stock <= 3 ? "text-amber-600" : "text-emerald-600"
              }`}
            >
              <span className={`size-2 rounded-full ${soldOut ? "bg-slate-400" : "animate-pulse bg-current"}`} />
              {stock}
            </span>
          ) : (
            <span />
          )}
          {p.sold_count > 0 && <span className="text-slate-500">{p.sold_count} ta sotilgan</span>}
        </div>
      )}

      {soldOut ? (
        <span
          aria-disabled="true"
          className="relative mt-4 flex cursor-not-allowed items-center justify-center rounded-2xl bg-slate-800 py-4 text-base font-semibold text-white/90"
        >
          Hozircha tugagan
        </span>
      ) : (
        <Link
          href={`/mahsulotlar/${p.id}`}
          className={`relative flex items-center justify-center gap-2.5 rounded-2xl bg-brand py-4 text-base font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-brand-dark ${
            stock || p.sold_count > 0 ? "mt-4" : "mt-6"
          }`}
        >
          <Cart className="size-5" /> Sotib olish
          <ArrowRight className="absolute right-6 size-5 transition group-hover:translate-x-1" />
        </Link>
      )}
    </article>
  );
}
