"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Cart, Close, Logo, Menu, Search } from "./icons";

const links = [
  { href: "/", label: "Bosh sahifa" },
  { href: "/mahsulotlar", label: "Mahsulotlar" },
  { href: "/#afzalliklar", label: "Afzalliklar" },
  { href: "/#faq", label: "FAQ" },
  { href: "#aloqa", label: "Aloqa" },
];

export function Brand() {
  return (
    <Link href="/" className="flex shrink-0 items-center gap-2 text-xl font-bold tracking-tight">
      <Logo className="size-8" />
      <span>
        servis<span className="text-brand">ai</span>.uz
      </span>
    </Link>
  );
}

type HeaderProps = {
  /** Berilsa, headerda qidiruv maydoni ko‘rsatiladi (mahsulotlar sahifasi) */
  search?: { value: string; onChange: (value: string) => void };
  cartCount?: number;
};

export default function Header({ search, cartCount = 0 }: HeaderProps) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  const searchInput = search && (
    <label className="relative block w-full">
      <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
      <input
        type="search"
        value={search.value}
        onChange={(e) => search.onChange(e.target.value)}
        placeholder="Kerakli servisni qidiring... (ChatGPT, Claude, CapCut, Gemini va hkz)"
        className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-4 text-sm outline-none transition placeholder:text-slate-400 focus:border-brand focus:ring-4 focus:ring-brand/10"
      />
    </label>
  );

  return (
    <header className="sticky top-0 z-50 border-b border-slate-100 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6">
        <Brand />

        <nav className="hidden items-center gap-1 lg:flex">
          {links.map((l) => (
            <Link
              key={l.label}
              href={l.href}
              className={`whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${
                pathname === l.href ? "bg-brand-soft text-brand" : "text-slate-700 hover:text-brand"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        {search && <div className="hidden max-w-md flex-1 xl:block">{searchInput}</div>}

        <div className="flex items-center gap-2">
          {!search && (
            <Link
              href="/mahsulotlar"
              aria-label="Qidirish"
              className="grid size-10 place-items-center rounded-lg text-slate-700 hover:bg-slate-100"
            >
              <Search className="size-5" />
            </Link>
          )}
          <button aria-label="Savat" className="relative grid size-10 place-items-center rounded-lg text-brand hover:bg-slate-100">
            <Cart className="size-5" />
            {cartCount > 0 && (
              <span className="absolute right-0.5 top-0.5 grid min-w-4.5 place-items-center rounded-full bg-rose-500 px-1 text-[10px] font-bold leading-4.5 text-white">
                {cartCount}
              </span>
            )}
          </button>
          <a
            href="#"
            className="hidden whitespace-nowrap rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition hover:bg-brand-dark sm:inline-block"
          >
            Tizimga kirish
          </a>
          <a
            href="#"
            className="hidden whitespace-nowrap rounded-lg px-5 py-2.5 text-sm font-semibold text-slate-800 ring-1 ring-slate-200 transition hover:ring-brand 2xl:inline-block"
          >
            Ro‘yxatdan o‘tish
          </a>
          <button
            aria-label="Menyu"
            onClick={() => setOpen((v) => !v)}
            className="grid size-10 place-items-center rounded-lg text-slate-700 hover:bg-slate-100 lg:hidden"
          >
            {open ? <Close className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {/* Planshet/telefonda qidiruv header ostida */}
      {search && <div className="border-t border-slate-100 px-4 py-2.5 sm:px-6 xl:hidden">{searchInput}</div>}

      {open && (
        <nav className="border-t border-slate-100 bg-white px-4 py-3 lg:hidden">
          {links.map((l) => (
            <Link
              key={l.label}
              href={l.href}
              onClick={() => setOpen(false)}
              className={`block rounded-lg px-3 py-2.5 text-sm font-medium hover:bg-brand-soft hover:text-brand ${
                pathname === l.href ? "bg-brand-soft text-brand" : "text-slate-700"
              }`}
            >
              {l.label}
            </Link>
          ))}
          <div className="mt-2 grid grid-cols-2 gap-2">
            <a href="#" className="rounded-lg bg-brand px-3 py-2.5 text-center text-sm font-semibold text-white">
              Tizimga kirish
            </a>
            <a href="#" className="rounded-lg px-3 py-2.5 text-center text-sm font-semibold text-slate-800 ring-1 ring-slate-200">
              Ro‘yxatdan o‘tish
            </a>
          </div>
        </nav>
      )}
    </header>
  );
}
