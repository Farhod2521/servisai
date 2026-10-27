"use client";

import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { ArrowRight, Bolt, CheckCircle, ChevronRight, Clock, Headset, Shield, Star } from "../../components/icons";
import { useProducts } from "../../lib/products";
import { badgeStyles, catalogCategories, discountPercent, durationText, formatCount, formatPrice, isSoldOut, periodText, productTypes, sellers, stockLabel, toCatalogProduct } from "../catalog-data";
import Linkify from "../../components/Linkify";
import BuyButton from "./BuyButton";

/** `children` — mahsulot ma’lumoti va "Boshqa servislar" orasida turadigan server bo‘limi */
export default function ProductDetail({ id, children }: { id: string; children: ReactNode }) {
  const { products, error, loading } = useProducts();

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-8">
          <div className="h-[420px] animate-pulse rounded-[2rem] bg-white" />
          <div className="h-[480px] animate-pulse rounded-[2rem] bg-white" />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-16 text-center sm:px-6">
        <p className="text-lg font-semibold">Ma’lumotni yuklab bo‘lmadi</p>
        <p className="mt-1 text-sm text-muted">{error}</p>
      </main>
    );
  }

  const found = products!.find((x) => x.id === id);
  if (!found) notFound();

  const p = toCatalogProduct(found);
  const badge = p.badge && badgeStyles[p.badge];
  const discount = discountPercent(p);
  const category = catalogCategories.find((c) => c.id === p.category);
  // Takrorlanmasin (masalan, sotuvchi ham, turi ham "API kredit")
  const chips = [
    ...new Set([sellers.find((s) => s.id === p.seller)?.label, productTypes.find((t) => t.id === p.type)?.label].filter(Boolean)),
  ];
  const others = products!.filter((o) => o.id !== p.id).map(toCatalogProduct);
  const soldOut = isSoldOut(p);
  const stock = stockLabel(p);

  return (
    <>
      <title>{`${p.name} — servisai.uz`}</title>
      <meta name="description" content={p.description} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        <nav className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
          <Link href="/" className="hover:text-brand">Bosh sahifa</Link>
          <ChevronRight className="size-3" />
          <Link href="/mahsulotlar" className="hover:text-brand">Servislar</Link>
          <ChevronRight className="size-3" />
          <span className="text-slate-700">{p.name}</span>
        </nav>

        <div className="mt-5 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-8">
          {/* ---------- Chap: servis haqida ---------- */}
          <div className="min-w-0 space-y-6">
            <section className="relative overflow-hidden rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 sm:p-8">
              <div aria-hidden className="pointer-events-none absolute -right-20 -top-24 size-72 rounded-full bg-violet-200/40 blur-3xl" />
              <div aria-hidden className="pointer-events-none absolute -left-16 bottom-0 size-56 rounded-full bg-sky-200/30 blur-3xl" />

              <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center">
                <div className="relative grid size-28 shrink-0 place-items-center rounded-[1.75rem] bg-gradient-to-br from-[#f7f9fe] via-[#eef3ff] to-[#dfe7ff] ring-1 ring-slate-100 sm:size-32">
                  <div className={`size-20 text-lg drop-shadow-xl sm:size-24 [&>*]:rounded-[1.3rem] ${soldOut ? "grayscale" : ""}`}>{p.logo}</div>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    {category && (
                      <span className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                        {category.icon} {category.label}
                      </span>
                    )}
                    {badge && <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badge.className}`}>{badge.label}</span>}
                    {soldOut && <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-bold text-white">Tugagan</span>}
                  </div>
                  <h1 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">{p.name}</h1>
                  {(p.rating !== undefined || p.sold_count > 0) && (
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
                      {p.rating !== undefined && (
                        <span className="flex items-center gap-1 font-semibold text-slate-800">
                          <Star className="size-4 text-amber-400" /> {p.rating.toFixed(1)}
                        </span>
                      )}
                      {p.sold_count > 0 && <span>({formatCount(p.sold_count)} ta sotib olingan)</span>}
                    </div>
                  )}
                </div>
              </div>

              {p.description && (
                <p className="relative mt-6 whitespace-pre-line text-[17px] leading-relaxed text-slate-600">{p.description}</p>
              )}

              {chips.length > 0 && (
                <div className="relative mt-5 flex flex-wrap gap-2">
                  {chips.map((c) => (
                    <span key={c} className="rounded-lg bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600 ring-1 ring-slate-100">{c}</span>
                  ))}
                </div>
              )}
            </section>

            {p.features.length > 0 && (
              <section className="rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 sm:p-8">
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <h2 className="text-2xl font-bold">Nimalar kiradi?</h2>
                    <p className="mt-1 text-sm text-slate-500">Obuna bilan birga beriladigan imkoniyatlar</p>
                  </div>
                  <span className="hidden rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 sm:inline">
                    {p.features.length} ta imkoniyat
                  </span>
                </div>
                <ul className="mt-6 grid gap-3 sm:grid-cols-2">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-3 rounded-2xl bg-slate-50/80 p-4 text-[15px] text-slate-700 ring-1 ring-slate-100">
                      <CheckCircle className="mt-px size-5 shrink-0 text-emerald-500" />
                      {f}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {p.notes.trim() && (
              <section className="rounded-[2rem] bg-amber-50/70 p-6 ring-1 ring-amber-100 sm:p-8">
                <h2 className="flex items-center gap-2 text-xl font-bold text-amber-950">
                  <span className="grid size-9 place-items-center rounded-xl bg-amber-100 text-lg">⚠️</span> Muhim ma’lumot
                </h2>
                <p className="mt-1 text-sm text-amber-900/70">Sotib olishdan oldin diqqat bilan o‘qing</p>
                <ul className="mt-5 space-y-3">
                  {p.notes
                    .split("\n")
                    .map((line) => line.trim())
                    .filter(Boolean)
                    .map((line) => (
                      <li key={line} className="break-words rounded-2xl bg-white/80 px-4 py-3 text-[15px] leading-relaxed text-slate-700 ring-1 ring-amber-100">
                        <Linkify text={line} />
                      </li>
                    ))}
                </ul>
              </section>
            )}

            <ul className="grid gap-3 sm:grid-cols-3">
              {[
                { icon: Bolt, tone: "bg-violet-50 text-violet-500", title: "Tez faollashtirish", text: "To‘lovdan so‘ng operator tezda faollashtiradi" },
                { icon: Shield, tone: "bg-emerald-50 text-emerald-500", title: "100% ishonchli", text: "Muammo bo‘lsa pul hisobingizga qaytadi" },
                { icon: Headset, tone: "bg-sky-50 text-sky-500", title: "24/7 yordam", text: "Savollaringizga istalgan vaqtda javob" },
              ].map(({ icon: Icon, tone, title, text }) => (
                <li key={title} className="flex gap-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
                  <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${tone}`}>
                    <Icon className="size-5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold">{title}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* ---------- O‘ng: sotib olish ---------- */}
          <aside className="lg:sticky lg:top-24">
            <div
              className={`rounded-[2rem] p-6 ring-1 ${
                soldOut ? "bg-slate-50 ring-slate-200 grayscale" : "bg-white shadow-[0_12px_40px_-12px_rgb(15_40_120/0.18)] ring-slate-100"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  {p.old_price && <p className="text-sm text-slate-400 line-through decoration-rose-400">{formatPrice(p.old_price)} so‘m</p>}
                  <p className="text-[2rem] font-extrabold leading-tight tracking-tight">{formatPrice(p.price)} so‘m</p>
                  <p className="text-sm text-slate-500">{periodText(p.durations[0], p.duration_unit)} muddat uchun</p>
                </div>
                {discount > 0 && (
                  <span className="rounded-xl bg-rose-500 px-2.5 py-1 text-sm font-extrabold text-white shadow-md shadow-rose-500/30">−{discount}%</span>
                )}
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Obuna muddati</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {p.durations.map((d) => (
                      <span key={d} className="rounded-xl bg-brand-soft px-4 py-2 text-sm font-semibold text-brand ring-2 ring-brand">
                        {durationText(d, p.duration_unit)}
                      </span>
                    ))}
                  </div>
                </div>
                {stock && (
                  <span
                    className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
                      soldOut
                        ? "bg-slate-200 text-slate-600"
                        : p.stock !== null && p.stock <= 3
                          ? "bg-amber-50 text-amber-700"
                          : "bg-emerald-50 text-emerald-700"
                    }`}
                  >
                    {stock}
                  </span>
                )}
              </div>

              <div
                className={`mt-4 flex items-center gap-3 rounded-2xl px-4 py-3 text-sm ${
                  p.instant_delivery ? "bg-emerald-50 text-emerald-800" : "bg-sky-50 text-sky-900"
                }`}
              >
                {p.instant_delivery ? <Bolt className="size-5 shrink-0" /> : <Clock className="size-5 shrink-0" />}
                <span>
                  <span className="block text-xs opacity-75">Yetkazib berish</span>
                  <span className="font-semibold">{p.instant_delivery ? "Darhol — xariddan so‘ng avtomatik" : p.delivery_time}</span>
                </span>
              </div>

              {soldOut ? (
                <>
                  <span
                    aria-disabled="true"
                    className="mt-6 flex w-full cursor-not-allowed items-center justify-center rounded-xl bg-slate-800 py-3.5 text-sm font-semibold text-white/90"
                  >
                    Hozircha tugagan
                  </span>
                  <p className="mt-3 text-center text-xs text-slate-500">
                    Tez orada qayta sotuvga chiqadi.{" "}
                    <a href="https://t.me/Boss_uz" target="_blank" rel="noopener noreferrer" className="font-semibold text-slate-700 underline">
                      Admin bilan bog‘lanish
                    </a>
                  </p>
                </>
              ) : (
                <div className="border-t border-slate-100 pt-1 mt-5">
                  <BuyButton productId={p.id} duration={p.durations[0]} price={p.price} stock={p.stock} deliveryTime={p.delivery_time} />
                  <p className="mt-3 text-center text-xs text-slate-500">To‘lov hisobingizdan yechiladi · Hisobni karta orqali to‘ldirasiz</p>
                </div>
              )}
            </div>
          </aside>
        </div>
      </main>

      {children}

      {others.length > 0 && (
        <section className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6">
          <div className="flex items-end justify-between gap-4">
            <h2 className="text-2xl font-bold">Boshqa servislar</h2>
            <Link href="/mahsulotlar" className="flex items-center gap-1 text-sm font-semibold text-brand hover:underline">
              Barchasi <ArrowRight className="size-4" />
            </Link>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {others.map((o) => (
              <Link
                key={o.id}
                href={`/mahsulotlar/${o.id}`}
                className={`flex items-center gap-4 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-100 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-blue-900/5 ${
                  isSoldOut(o) ? "grayscale opacity-70" : ""
                }`}
              >
                <div className="size-16 shrink-0 text-sm">{o.logo}</div>
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{o.name}</p>
                  <p className="text-sm text-slate-500">
                    {isSoldOut(o) ? "Tugagan" : `${formatPrice(o.price)} so‘m / ${durationText(o.durations[0], o.duration_unit)}`}
                  </p>
                </div>
                <ChevronRight className="size-5 text-slate-400" />
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
