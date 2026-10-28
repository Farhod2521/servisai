"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "./auth/AuthProvider";
import UserMenu, { accountLinksFor } from "./auth/UserMenu";
import { Cart, Close, LogOut, Menu, Search } from "./icons";
import LogoMark from "./LogoMark";
import ThemeToggle from "./ThemeToggle";

const links = [
  { href: "/", label: "Bosh sahifa" },
  { href: "/mahsulotlar", label: "Mahsulotlar" },
  { href: "/#afzalliklar", label: "Afzalliklar" },
  { href: "/#faq", label: "FAQ" },
  { href: "#aloqa", label: "Aloqa" },
];

export function Brand() {
  return (
    <Link href="/" aria-label="servisai.uz — bosh sahifa" className="flex shrink-0 items-center gap-1.5">
      <LogoMark className="h-9 w-auto" preload />
      <span className="text-[1.4rem] font-extrabold tracking-tight text-[#0b1437]">
        servis
        <span className="bg-gradient-to-b from-[#2f8bff] to-[#0b5cff] bg-clip-text text-transparent">ai</span>
        .uz
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
  const { user, openLogin, logout } = useAuth();

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
          <ThemeToggle className="hidden sm:grid" />
          <button aria-label="Savat" className="relative grid size-10 place-items-center rounded-lg text-brand hover:bg-slate-100">
            <Cart className="size-5" />
            {cartCount > 0 && (
              <span className="absolute right-0.5 top-0.5 grid min-w-4.5 place-items-center rounded-full bg-rose-500 px-1 text-[10px] font-bold leading-4.5 text-white">
                {cartCount}
              </span>
            )}
          </button>
          <UserMenu />
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
          <div className="mt-2 border-t border-slate-100 pt-2">
            <ThemeToggle withLabel className="sm:hidden" />
            {user ? (
              <>
                {accountLinksFor(user).map(({ href, label, icon: Icon }) => (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-700 hover:bg-brand-soft hover:text-brand"
                  >
                    <Icon className="size-4.5" /> {label}
                  </Link>
                ))}
                <button
                  onClick={() => {
                    setOpen(false);
                    logout();
                  }}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-rose-600 hover:bg-rose-50"
                >
                  <LogOut className="size-4.5" /> Chiqish
                </button>
              </>
            ) : (
              <button
                onClick={() => {
                  setOpen(false);
                  openLogin();
                }}
                className="w-full rounded-lg bg-brand px-3 py-2.5 text-center text-sm font-semibold text-white"
              >
                Tizimga kirish
              </button>
            )}
          </div>
        </nav>
      )}
    </header>
  );
}
