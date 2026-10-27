"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { User } from "../../lib/api";
import { formatPrice } from "../../mahsulotlar/catalog-data";
import { Gift, History, LogOut, Receipt, Shield, UserIcon, Wallet } from "../icons";
import { useAuth } from "./AuthProvider";

export function Avatar({
  user,
  className = "size-9",
}: {
  user: Pick<User, "full_name" | "email" | "avatar_url">;
  className?: string;
}) {
  const initials = (user.full_name || user.email || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
  return user.avatar_url ? (
    // eslint-disable-next-line @next/next/no-img-element -- tashqi (Google) rasm, optimallashtirish shart emas
    <img src={user.avatar_url} alt="" referrerPolicy="no-referrer" className={`${className} shrink-0 rounded-full object-cover`} />
  ) : (
    <span className={`${className} grid shrink-0 place-items-center rounded-full bg-brand text-sm font-bold text-white`}>{initials}</span>
  );
}

export const accountLinks = [
  { href: "/profil", label: "Profil", icon: UserIcon },
  { href: "/profil?tab=hisob", label: "Hisobim", icon: Wallet },
  { href: "/profil?tab=buyurtmalar", label: "Mening buyurtmalarim", icon: Receipt },
  { href: "/profil?tab=tarix", label: "Buyurtmalar tarixi", icon: History },
  { href: "/profil?tab=dostlar", label: "Do‘stlarni taklif qilish", icon: Gift },
];

/** Adminlar uchun menyuga "Admin panel" ham qo‘shiladi */
export const accountLinksFor = (user: User) =>
  user.is_admin ? [...accountLinks, { href: "/admin", label: "Admin panel", icon: Shield }] : accountLinks;

/** Headerdagi "Tizimga kirish" tugmasi yoki kirgan foydalanuvchi menyusi */
export default function UserMenu() {
  const { user, loading, openLogin, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  if (loading) return <span className="hidden h-10 w-32 animate-pulse rounded-lg bg-slate-100 sm:block" />;

  if (!user) {
    return (
      <button
        onClick={() => openLogin()}
        className="hidden whitespace-nowrap rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition hover:bg-brand-dark sm:inline-block"
      >
        Tizimga kirish
      </button>
    );
  }

  return (
    <div ref={ref} className="relative hidden sm:block">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full py-1 pl-1 pr-3 ring-1 ring-slate-200 transition hover:ring-brand"
      >
        <Avatar user={user} className="size-8" />
        <span className="max-w-32 truncate text-sm font-semibold">{user.full_name.split(" ")[0]}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-60 overflow-hidden rounded-2xl bg-white py-2 shadow-xl ring-1 ring-slate-100">
          <div className="border-b border-slate-100 px-4 pb-2.5 pt-1">
            <p className="truncate text-sm font-semibold">{user.full_name}</p>
            <p className="truncate text-xs text-slate-500">
              {user.email ?? (user.telegram_username ? `@${user.telegram_username}` : user.phone)}
            </p>
            <Link
              href="/profil?tab=hisob"
              onClick={() => setOpen(false)}
              className="mt-2 flex items-center justify-between rounded-lg bg-brand-soft px-3 py-2 text-xs font-semibold text-brand"
            >
              <span>Balans</span>
              <span>{formatPrice(user.balance)} so‘m</span>
            </Link>
          </div>
          {accountLinksFor(user).map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-brand-soft hover:text-brand"
            >
              <Icon className="size-4.5" /> {label}
            </Link>
          ))}
          <button
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="flex w-full items-center gap-3 border-t border-slate-100 px-4 py-2.5 text-sm text-rose-600 hover:bg-rose-50"
          >
            <LogOut className="size-4.5" /> Chiqish
          </button>
        </div>
      )}
    </div>
  );
}
