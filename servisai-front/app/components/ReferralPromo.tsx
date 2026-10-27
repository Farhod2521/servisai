"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type MyReferral } from "../lib/api";
import { useAuth } from "./auth/AuthProvider";
import { Close, LinkIcon, UserPlus } from "./icons";

type PublicReward = { id: number; title: string; required_friends: number; product_name: string; quantity: number };

const HIDE_KEY = "servisai_ref_promo_hidden_until";
const HIDE_DAYS = 3;
const SHOW_DELAY_MS = 1500;
const REFERRAL_PAGE = "/profil?tab=dostlar";

function hiddenNow() {
  try {
    return Number(localStorage.getItem(HIDE_KEY) ?? 0) > Date.now();
  } catch {
    return false;
  }
}

function hideForDays() {
  try {
    localStorage.setItem(HIDE_KEY, String(Date.now() + HIDE_DAYS * 24 * 60 * 60 * 1000));
  } catch {
    /* private rejim — keyingi tashrifda yana chiqadi */
  }
}

/** Bosh sahifadagi "N ta do‘stingizni taklif qiling" oynasi (faol sovg‘a bo‘lsa, 3 kunda bir marta) */
export default function ReferralPromo() {
  const { user, loading, openLogin } = useAuth();
  const router = useRouter();
  const [reward, setReward] = useState<PublicReward | null>(null);
  const [friends, setFriends] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (loading || hiddenNow()) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    (async () => {
      const rewards = await api<PublicReward[]>("/referrals/rewards").catch(() => []);
      const first = rewards[0];
      if (!first) return;
      let count = 0;
      if (user) {
        const me = await api<MyReferral>("/referrals/me").catch(() => null);
        // Bu sovg‘ani allaqachon olgan bo‘lsa — ko‘rsatilmaydi
        if (me?.rewards.find((r) => r.id === first.id)?.granted) return;
        count = me?.friends ?? 0;
      }
      if (!alive) return;
      setReward(first);
      setFriends(count);
      timer = setTimeout(() => alive && setOpen(true), SHOW_DELAY_MS);
    })();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [user, loading]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        hideForDays();
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open || !reward) return null;

  const later = () => {
    hideForDays();
    setOpen(false);
  };

  const getLink = () => {
    hideForDays();
    setOpen(false);
    // Kirmagan bo‘lsa — Telegram orqali kiradi, so‘ng do‘stlar sahifasiga o‘tadi
    if (user) router.push(REFERRAL_PAGE);
    else openLogin({ onSuccess: () => router.push(REFERRAL_PAGE) });
  };

  const total = reward.required_friends;
  const dots = Math.min(total, 20);
  const filled = Math.min(friends, total);
  const filledDots = Math.round((filled / total) * dots);

  return (
    <div
      className="fixed inset-0 z-[80] grid grid-cols-1 place-items-center overflow-y-auto bg-slate-900/45 p-4 backdrop-blur-sm"
      onMouseDown={(e) => e.target === e.currentTarget && later()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="ref-promo-title"
        className="animate-[pop_.35s_cubic-bezier(.2,.9,.3,1.3)] relative grid w-full max-w-3xl grid-cols-1 overflow-hidden rounded-[2rem] bg-white shadow-2xl md:grid-cols-[minmax(0,1fr)_330px]"
      >
        <button
          onClick={later}
          aria-label="Yopish"
          className="absolute right-4 top-4 z-10 grid size-9 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
        >
          <Close className="size-5" />
        </button>

        {/* Matn */}
        <div className="order-2 p-7 sm:p-9 md:order-1">
          <h2 id="ref-promo-title" className="text-3xl font-extrabold leading-tight tracking-tight sm:text-[2.1rem]">
            {total} ta do‘stingizni
            <br />
            <span className="text-brand">taklif qiling</span>
          </h2>
          <p className="mt-3 text-lg font-semibold text-slate-700">
            {reward.product_name} akkauntini <span className="font-extrabold text-brand">BEPUL</span> oling!
          </p>
          <p className="mt-3 text-sm leading-relaxed text-slate-500">
            Do‘stlaringiz havolangiz orqali ro‘yxatdan o‘tsin — {total} ta taklifdan so‘ng sovg‘angizni qo‘lga kiriting.
          </p>

          <p className="mt-6 text-sm font-semibold text-slate-700">
            {filled} / {total} do‘st
          </p>
          <div className="mt-2.5 flex flex-wrap gap-2" aria-hidden>
            {Array.from({ length: dots }, (_, i) => (
              <span key={i} className={`size-3.5 rounded-full ${i < filledDots ? "bg-brand shadow-sm shadow-blue-600/40" : "bg-slate-200"}`} />
            ))}
          </div>

          <button
            onClick={getLink}
            className="mt-7 flex w-full items-center justify-center gap-2.5 rounded-2xl bg-brand py-4 text-base font-semibold text-white shadow-lg shadow-blue-600/30 transition hover:bg-brand-dark sm:max-w-xs"
          >
            <LinkIcon className="size-5" /> Taklif havolasini olish
          </button>
          <button onClick={later} className="mt-3 w-full text-sm font-semibold text-brand hover:underline sm:max-w-xs">
            Keyinroq
          </button>
        </div>

        {/* Bezak: sovg‘a qutisi, yulduz va do‘stlar */}
        <div aria-hidden className="relative order-1 h-60 overflow-hidden bg-gradient-to-br from-[#eef2ff] via-[#f3efff] to-[#e3ecff] md:order-2 md:h-auto">
          <div className="absolute left-1/2 top-1/2 size-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/70 blur-3xl" />
          <div className="absolute bottom-0 left-1/2 h-24 w-56 -translate-x-1/2 rounded-full bg-indigo-200/60 blur-2xl" />

          {/* Do‘st kartochkalari */}
          {[
            "left-[14%] top-[16%] size-14 -rotate-6",
            "right-[12%] top-[10%] size-16 rotate-6",
            "left-[8%] top-[52%] size-12 rotate-3",
            "right-[10%] top-[50%] size-14 -rotate-3",
          ].map((pos) => (
            <span key={pos} className={`absolute grid place-items-center rounded-2xl bg-white/90 text-brand shadow-lg shadow-indigo-900/10 ring-1 ring-white ${pos}`}>
              <UserPlus className="size-1/2" />
            </span>
          ))}

          {/* Uchqunlar */}
          <Sparkle className="absolute left-[34%] top-[14%] size-4 text-fuchsia-400" />
          <Sparkle className="absolute right-[30%] top-[38%] size-5 text-sky-400" />
          <Sparkle className="absolute left-[24%] bottom-[22%] size-3 text-violet-400" />

          {/* Sovg‘a qutisi va yulduz */}
          <div className="absolute bottom-[7%] left-1/2 w-28 -translate-x-1/2 md:bottom-[14%] md:w-44">
            <div className="absolute -top-[95%] left-1/2 w-[85%] -translate-x-1/2 drop-shadow-[0_10px_25px_rgba(99,102,241,0.45)]">
              <svg viewBox="0 0 100 100" className="w-full">
                <defs>
                  <linearGradient id="promo-star" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#4f9cff" />
                    <stop offset="0.55" stopColor="#6d5dfc" />
                    <stop offset="1" stopColor="#c05cff" />
                  </linearGradient>
                </defs>
                <path d="M50 2C53 30 70 47 98 50 70 53 53 70 50 98 47 70 30 53 2 50 30 47 47 30 50 2Z" fill="url(#promo-star)" />
              </svg>
            </div>
            {/* Qopqoq */}
            <div className="relative z-10 mx-auto h-7 w-[108%] -translate-x-[3.7%] rounded-lg bg-gradient-to-b from-white to-indigo-100 shadow-md ring-1 ring-white">
              <span className="absolute inset-y-0 left-1/2 w-5 -translate-x-1/2 bg-gradient-to-b from-[#6d8bff] to-[#4f6bff]" />
            </div>
            {/* Quti */}
            <div className="relative h-16 rounded-b-xl bg-gradient-to-b from-[#f5f7ff] to-[#c9d6ff] shadow-xl shadow-indigo-900/15 ring-1 ring-white md:h-28">
              <span className="absolute inset-y-0 left-1/2 w-5 -translate-x-1/2 bg-gradient-to-b from-[#5b7dff] to-[#3f5ef0]" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Sparkle({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 0c.7 6.4 5.6 11.3 12 12-6.4.7-11.3 5.6-12 12-.7-6.4-5.6-11.3-12-12C6.4 11.3 11.3 6.4 12 0Z" />
    </svg>
  );
}
