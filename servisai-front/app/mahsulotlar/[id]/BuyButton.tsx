"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "../../components/auth/AuthProvider";
import Confetti from "../../components/Confetti";
import { CartFilled, Clock, Close, Copy, Send, Wallet } from "../../components/icons";
import { formatPrice } from "../catalog-data";
import { api, ApiError, type OrderDetail } from "../../lib/api";

// To‘lov tizimi ulanmaguncha to‘lov operator orqali Telegramda amalga oshiriladi
const SUPPORT_URL = "https://t.me/fen1xmedia";
// Backenddagi MAX_ORDER_QUANTITY bilan bir xil
const MAX_QUANTITY = 100;

export default function BuyButton({
  productId,
  duration,
  price,
  stock,
  deliveryTime,
}: {
  productId: string;
  duration: number;
  price: number;
  /** null — cheklanmagan */
  stock: number | null;
  deliveryTime: string;
}) {
  const { user, openLogin, refreshUser } = useAuth();
  const [qtyText, setQtyText] = useState("1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ text: string; topUp: boolean } | null>(null);
  const [order, setOrder] = useState<OrderDetail | null>(null);
  // Avtomatik yetkazilgan ma’lumot modal oynasi (yopilgach qayta ochish mumkin)
  const [showDelivery, setShowDelivery] = useState(true);

  const maxQty = Math.min(stock ?? MAX_QUANTITY, MAX_QUANTITY);
  const qty = Number(qtyText) || 0;
  const overStock = stock !== null && qty > stock;
  const tooMany = stock === null && qty > MAX_QUANTITY;
  const qtyProblem = overStock
    ? `Bazada faqat ${stock} ta bor`
    : tooMany
      ? `Bir buyurtmada ${MAX_QUANTITY} tagacha olish mumkin`
      : qty < 1
        ? "Sonini kiriting"
        : null;
  const total = price * Math.max(qty, 1);

  const setQty = (n: number) => {
    setError(null);
    setQtyText(String(Math.max(1, Math.min(n, maxQty))));
  };

  const createOrder = async (quantity: number) => {
    setBusy(true);
    setError(null);
    try {
      setOrder(
        await api<OrderDetail>("/orders", {
          method: "POST",
          json: { product_id: productId, duration_months: duration, quantity },
        }),
      );
      refreshUser();
    } catch (e) {
      setError({ text: (e as Error).message, topUp: e instanceof ApiError && e.status === 402 });
    } finally {
      setBusy(false);
    }
  };

  const buy = () => {
    if (qtyProblem) return;
    // Kirmagan foydalanuvchi avval tizimga kiradi, so‘ng buyurtma avtomatik yaratiladi
    if (!user) openLogin({ onSuccess: () => createOrder(qty) });
    else createOrder(qty);
  };

  if (order) {
    // Avtomatik mahsulot: buyurtma darhol bajariladi va ma’lumot shu yerda beriladi
    if (order.status === "completed" && order.delivery_info) {
      return (
        <>
          {showDelivery && <DeliveredModal order={order} onClose={() => setShowDelivery(false)} />}
          <div className="mt-5 rounded-2xl bg-gradient-to-br from-emerald-50 to-sky-50 p-4 text-sm ring-1 ring-emerald-100">
            <p className="font-bold text-emerald-900">🎉 Buyurtma {order.number} tayyor!</p>
            <p className="mt-1 text-emerald-800/80">Ma’lumotlar «Buyurtmalarim» bo‘limida va Telegram botda saqlandi.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => setShowDelivery(true)}
                className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white transition hover:bg-emerald-700"
              >
                Ma’lumotni ko‘rish
              </button>
              <Link href="/profil?tab=buyurtmalar" className="rounded-lg bg-white px-4 py-2 font-semibold text-emerald-700 ring-1 ring-emerald-200">
                Buyurtmalarim
              </Link>
            </div>
          </div>
        </>
      );
    }

    return (
      <div className="mt-5 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-900">
        <p className="font-semibold">
          ✅ Buyurtma {order.number} qabul qilindi!{order.quantity > 1 && ` (${order.quantity} ta)`}
        </p>
        <p className="mt-1 text-emerald-800/80">
          {formatPrice(order.price)} so‘m hisobingizdan yechildi. Tez orada ma’lumotlarni «Buyurtmalarim» bo‘limiga va Telegram bot
          orqali yuboramiz.
        </p>
        <p className="mt-3 flex items-center gap-2 rounded-xl bg-white/70 px-3 py-2 font-semibold text-emerald-900">
          <Clock className="size-4 shrink-0" /> Yetkazib berish vaqti: {deliveryTime}
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

  const short = user ? total - user.balance : 0;
  const stepBtn =
    "grid size-11 place-items-center text-xl font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-300 disabled:hover:bg-transparent";

  return (
    <>
      {/* Soni va jami summa */}
      <div className="mt-5 flex items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">Soni</p>
          <div className={`mt-1.5 flex w-fit items-center overflow-hidden rounded-xl ring-1 ${qtyProblem && qty > 0 ? "ring-rose-300" : "ring-slate-200"}`}>
            <button type="button" aria-label="Kamaytirish" onClick={() => setQty(qty - 1)} disabled={qty <= 1} className={stepBtn}>
              −
            </button>
            <input
              value={qtyText}
              onChange={(e) => {
                setError(null);
                setQtyText(e.target.value.replace(/\D/g, "").slice(0, 4));
              }}
              onBlur={() => qty < 1 && setQtyText("1")}
              inputMode="numeric"
              aria-label="Soni"
              className="h-11 w-14 border-x border-slate-200 text-center font-semibold outline-none"
            />
            <button type="button" aria-label="Ko‘paytirish" onClick={() => setQty(qty + 1)} disabled={qty >= maxQty} className={stepBtn}>
              +
            </button>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-slate-500">{qty > 1 ? `${qty} × ${formatPrice(price)} so‘m` : "Jami"}</p>
          <p className="whitespace-nowrap text-xl font-extrabold sm:text-2xl">{formatPrice(total)} so‘m</p>
        </div>
      </div>
      {qtyProblem && qty > 0 && (
        <p className="mt-2 rounded-xl bg-rose-50 px-4 py-2.5 text-sm font-semibold text-rose-600">
          {qtyProblem}. Sonini {maxQty} tagacha kamaytiring.
        </p>
      )}

      {user && (
        <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-50 px-4 py-2.5 text-sm">
          <span className="flex items-center gap-2 text-slate-600">
            <Wallet className="size-4 text-brand" /> Hisobingiz
          </span>
          <span className="font-semibold">{formatPrice(user.balance)} so‘m</span>
        </div>
      )}
      {user && short > 0 && !qtyProblem ? (
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
          disabled={busy || Boolean(qtyProblem)}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-brand py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
        >
          <CartFilled className="size-4.5" />{" "}
          {busy ? "Yuborilmoqda..." : user ? `Hisobdan to‘lab sotib olish${qty > 1 ? ` (${qty} ta)` : ""}` : "Sotib olish"}
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
          {error.text}{" "}
          {error.topUp && (
            <Link href="/profil?tab=hisob" className="font-semibold underline">
              Hisobni to‘ldirish
            </Link>
          )}
        </p>
      )}
    </>
  );
}

/** Avtomatik yetkazilgan buyurtma: konfetti + nusxalanadigan havola(lar) bilan modal oyna */
function DeliveredModal({ order, onClose }: { order: OrderDetail; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const text = order.delivery_info ?? "";
  const items = text.split("\n").filter((l) => l.trim());
  const singleUrl = items.length === 1 && /^https?:\/\//.test(items[0].trim()) ? items[0].trim() : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard ruxsat berilmagan — matnni qo‘lda belgilab olish mumkin */
    }
  };

  return (
    <>
      <Confetti />
      <div
        className="fixed inset-0 z-[90] grid place-items-center overflow-y-auto bg-slate-900/50 p-4 backdrop-blur-sm"
        onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="delivered-title"
          className="animate-[pop_.35s_cubic-bezier(.2,.9,.3,1.3)] w-full max-w-md overflow-hidden rounded-[2rem] bg-white shadow-2xl"
        >
          <div className="relative bg-gradient-to-br from-emerald-400 via-teal-400 to-sky-500 px-6 pb-8 pt-7 text-center text-white">
            <button
              aria-label="Yopish"
              onClick={onClose}
              className="absolute right-4 top-4 grid size-9 place-items-center rounded-full bg-white/20 hover:bg-white/30"
            >
              <Close className="size-5" />
            </button>
            <div className="mx-auto grid size-20 place-items-center rounded-full bg-white/25 text-5xl ring-8 ring-white/10">🎉</div>
            <h2 id="delivered-title" className="mt-4 text-2xl font-extrabold">
              Tabriklaymiz!
            </h2>
            <p className="mt-1 text-white/90">Buyurtmangiz tayyor</p>
          </div>

          <div className="-mt-4 rounded-t-[2rem] bg-white px-6 pb-6 pt-6">
            <p className="flex flex-wrap justify-center gap-x-2 text-center text-sm text-slate-500">
              <span className="font-semibold text-slate-700">{order.product_name}</span>
              {order.quantity > 1 && <span>× {order.quantity}</span>}
              <span>· {order.number}</span>
              <span>· {formatPrice(order.price)} so‘m</span>
            </p>

            <label className="mt-5 block">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                {items.length > 1 ? `Sizning havolalaringiz (${items.length} ta)` : "Sizning havolangiz"}
              </span>
              <textarea
                readOnly
                value={text}
                rows={Math.min(6, Math.max(2, items.length))}
                onFocus={(e) => e.currentTarget.select()}
                className="mt-2 w-full resize-none rounded-2xl border-2 border-dashed border-emerald-200 bg-emerald-50/50 px-4 py-3 font-mono text-sm text-slate-800 outline-none focus:border-emerald-400"
              />
            </label>

            <div className={`mt-3 grid gap-2 ${singleUrl ? "grid-cols-2" : ""}`}>
              <button
                onClick={copy}
                className={`flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold text-white shadow-md transition ${
                  copied ? "bg-emerald-600 shadow-emerald-600/25" : "bg-brand shadow-blue-600/25 hover:bg-brand-dark"
                }`}
              >
                <Copy className="size-4" /> {copied ? "Nusxalandi ✓" : "Nusxalash"}
              </button>
              {singleUrl && (
                <a
                  href={singleUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center rounded-xl py-3 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:ring-brand"
                >
                  Havolani ochish ↗
                </a>
              )}
            </div>

            <p className="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-center text-xs leading-relaxed text-slate-500">
              Bu ma’lumot «Buyurtmalarim» bo‘limida saqlanadi va Telegram botga ham yuborildi.
            </p>

            <div className="mt-4 flex gap-2">
              <Link
                href="/profil?tab=buyurtmalar"
                className="flex-1 rounded-xl py-2.5 text-center text-sm font-semibold text-brand ring-1 ring-brand/30 hover:bg-brand-soft"
              >
                Buyurtmalarim
              </Link>
              <button onClick={onClose} className="flex-1 rounded-xl bg-slate-100 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-200">
                Yopish
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
