"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "../../components/auth/AuthProvider";
import { CartFilled, Send, Wallet } from "../../components/icons";
import { formatPrice } from "../catalog-data";
import { api, type OrderDetail } from "../../lib/api";

// To‘lov tizimi ulanmaguncha to‘lov operator orqali Telegramda amalga oshiriladi
const SUPPORT_URL = "https://t.me/servisaiuz";

export default function BuyButton({ productId, duration, price }: { productId: string; duration: number; price: number }) {
  const { user, openLogin, refreshUser } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<OrderDetail | null>(null);

  const createOrder = async () => {
    setBusy(true);
    setError(null);
    try {
      setOrder(await api<OrderDetail>("/orders", { method: "POST", json: { product_id: productId, duration_months: duration } }));
      refreshUser();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const buy = () => {
    // Kirmagan foydalanuvchi avval tizimga kiradi, so‘ng buyurtma avtomatik yaratiladi
    if (!user) openLogin({ onSuccess: createOrder });
    else createOrder();
  };

  if (order) {
    return (
      <div className="mt-5 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-900">
        <p className="font-semibold">✅ Buyurtma {order.number} qabul qilindi!</p>
        <p className="mt-1 text-emerald-800/80">
          {formatPrice(order.price)} so‘m hisobingizdan yechildi. Faollashtirish uchun operator siz bilan bog‘lanadi.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            href="/profil?tab=buyurtmalar"
            className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white transition hover:bg-emerald-700"
          >
            Buyurtmalarimni ko‘rish
          </Link>
          <a
            href={SUPPORT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 rounded-lg bg-white px-4 py-2 font-semibold text-emerald-700 ring-1 ring-emerald-200"
          >
            <Send className="size-4" /> Operatorga yozish
          </a>
        </div>
      </div>
    );
  }

  const short = user ? price - user.balance : 0;

  return (
    <>
      {user && (
        <div className="mt-5 flex items-center justify-between rounded-xl bg-slate-50 px-4 py-2.5 text-sm">
          <span className="flex items-center gap-2 text-slate-600">
            <Wallet className="size-4 text-brand" /> Hisobingiz
          </span>
          <span className="font-semibold">{formatPrice(user.balance)} so‘m</span>
        </div>
      )}
      {user && short > 0 ? (
        <>
          <p className="mt-3 text-center text-sm text-rose-600">Hisobingizda yana {formatPrice(short)} so‘m yetishmayapti</p>
          <Link
            href="/profil?tab=hisob"
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-brand py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-brand-dark"
          >
            <Wallet className="size-4.5" /> Hisobni to‘ldirish
          </Link>
        </>
      ) : (
        <button
          onClick={buy}
          disabled={busy}
          className={`${user ? "mt-3" : "mt-5"} flex w-full items-center justify-center gap-2 rounded-xl bg-brand py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-brand-dark disabled:opacity-60`}
        >
          <CartFilled className="size-4.5" /> {busy ? "Yuborilmoqda..." : user ? "Hisobdan to‘lab sotib olish" : "Sotib olish"}
        </button>
      )}
      <a
        href={SUPPORT_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2.5 flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:ring-brand"
      >
        <Send className="size-4" /> Savol bo‘lsa — Telegram
      </a>
      {error && (
        <p className="mt-3 rounded-xl bg-rose-50 px-4 py-2.5 text-sm text-rose-600">
          {error}{" "}
          <Link href="/profil?tab=hisob" className="font-semibold underline">
            Hisobni to‘ldirish
          </Link>
        </p>
      )}
    </>
  );
}
