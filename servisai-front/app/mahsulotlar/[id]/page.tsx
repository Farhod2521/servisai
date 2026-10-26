import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Footer from "../../components/Footer";
import Header from "../../components/Header";
import { HowItWorks } from "../../components/Sections";
import { ArrowRight, Bolt, ChevronRight, Headset, Shield, Star } from "../../components/icons";
import BuyButton from "./BuyButton";
import {
  badgeStyles,
  catalogCategories,
  catalogProducts,
  discountPercent,
  formatCount,
  formatPrice,
  getProduct,
  productTypes,
  sellers,
} from "../catalog-data";

export function generateStaticParams() {
  return catalogProducts.map((p) => ({ id: p.id }));
}

export async function generateMetadata({ params }: PageProps<"/mahsulotlar/[id]">): Promise<Metadata> {
  const product = getProduct((await params).id);
  if (!product) return {};
  return {
    title: `${product.name} — servisai.uz`,
    description: product.description,
  };
}

export default async function ProductPage({ params }: PageProps<"/mahsulotlar/[id]">) {
  const p = getProduct((await params).id);
  if (!p) notFound();

  const badge = p.badge && badgeStyles[p.badge];
  const discount = discountPercent(p);
  const category = catalogCategories.find((c) => c.id === p.category)!;
  const seller = sellers.find((s) => s.id === p.seller)!;
  const type = productTypes.find((t) => t.id === p.type)!;
  const others = catalogProducts.filter((o) => o.id !== p.id);

  return (
    <>
      <Header />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        <nav className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
          <Link href="/" className="hover:text-brand">Bosh sahifa</Link>
          <ChevronRight className="size-3" />
          <Link href="/mahsulotlar" className="hover:text-brand">Servislar</Link>
          <ChevronRight className="size-3" />
          <span className="text-slate-700">{p.name}</span>
        </nav>

        <section className="mt-5 grid gap-6 lg:grid-cols-2 lg:gap-10">
          {/* Logo */}
          <div className="relative grid min-h-72 place-items-center overflow-hidden rounded-3xl bg-gradient-to-br from-[#f7f9fe] via-[#eef3ff] to-[#dfe7ff] ring-1 ring-slate-100 lg:min-h-[460px]">
            <div aria-hidden className="absolute -right-10 -top-16 size-80 rounded-full bg-violet-300/30 blur-3xl" />
            <div aria-hidden className="absolute -bottom-20 -left-10 size-72 rounded-full bg-sky-300/40 blur-3xl" />
            <div className="relative size-36 drop-shadow-2xl sm:size-44">{p.logo}</div>
          </div>

          {/* Ma’lumot va xarid */}
          <div className="flex flex-col">
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                {category.icon} {category.label}
              </span>
              {badge && <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badge.className}`}>{badge.label}</span>}
            </div>

            <h1 className="mt-4 text-3xl font-extrabold tracking-tight sm:text-4xl">{p.name}</h1>

            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
              <span className="flex items-center gap-1 font-semibold text-slate-800">
                <Star className="size-4 text-amber-400" /> {p.rating.toFixed(1)}
              </span>
              <span>{formatCount(p.reviews)} ta sharh</span>
              <span>{formatCount(p.sold)}+ sotilgan</span>
            </div>

            <p className="mt-4 leading-relaxed text-slate-600">{p.description}</p>

            <div className="mt-5 flex flex-wrap gap-2">
              {[seller.label, type.label].map((c) => (
                <span key={c} className="rounded-lg bg-slate-50 px-3 py-1.5 text-xs text-slate-600 ring-1 ring-slate-100">{c}</span>
              ))}
            </div>

            <div className="mt-6">
              <p className="text-sm font-semibold">Obuna muddati</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {p.durations.map((d) => (
                  <span key={d} className="rounded-xl bg-brand-soft px-5 py-2.5 text-sm font-semibold text-brand ring-2 ring-brand">
                    {d} oy
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-6 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="text-3xl font-extrabold">{formatPrice(p.price)} so‘m</span>
                {p.oldPrice && <span className="text-sm text-slate-400 line-through">{formatPrice(p.oldPrice)} so‘m</span>}
                {discount > 0 && <span className="rounded-full bg-rose-500 px-2 py-0.5 text-xs font-bold text-white">-{discount}%</span>}
              </div>
              <p className="mt-1 text-sm text-slate-500">{p.durations[0]} oylik obuna uchun</p>

              <BuyButton productId={p.id} duration={p.durations[0]} />
              <p className="mt-3 text-center text-xs text-slate-500">To‘lov: Click, Payme, Uzcard, Humo</p>
            </div>

            <ul className="mt-5 grid gap-3 text-sm text-slate-600 sm:grid-cols-3">
              <li className="flex items-center gap-2"><Bolt className="size-4 text-brand" /> Tez faollashtirish</li>
              <li className="flex items-center gap-2"><Shield className="size-4 text-brand" /> 100% ishonchli</li>
              <li className="flex items-center gap-2"><Headset className="size-4 text-brand" /> 24/7 yordam</li>
            </ul>
          </div>
        </section>

        <section className="mt-12 rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-100 sm:p-8">
          <h2 className="text-2xl font-bold">Nimalar kiradi?</h2>
          <ul className="mt-5 grid gap-3 sm:grid-cols-2">
            {p.features.map((f) => (
              <li key={f} className="flex items-start gap-3 text-slate-700">
                <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-600">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} className="size-3" aria-hidden="true">
                    <path d="m5 12 5 5 9-10" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                {f}
              </li>
            ))}
          </ul>
        </section>
      </main>

      <HowItWorks />

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
                className="flex items-center gap-4 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-100 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-blue-900/5"
              >
                <div className="size-16 shrink-0">{o.logo}</div>
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{o.name}</p>
                  <p className="text-sm text-slate-500">
                    {formatPrice(o.price)} so‘m / {o.durations[0]} oy
                  </p>
                </div>
                <ChevronRight className="size-5 text-slate-400" />
              </Link>
            ))}
          </div>
        </section>
      )}

      <Footer />
    </>
  );
}
