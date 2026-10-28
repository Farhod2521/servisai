"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Announcement, type MyReferral } from "../lib/api";
import { useAuth } from "./auth/AuthProvider";
import { ArrowRight, Close, LinkIcon, Megaphone, UserPlus } from "./icons";

type PublicReward = { id: number; title: string; required_friends: number; product_name: string; quantity: number };

const HIDE_KEY = "servisai_announcement_hidden";
const HIDE_DAYS = 3;
const SHOW_DELAY_MS = 1500;
const REFERRAL_PAGE = "/profil?tab=dostlar";

/** E’lon tahrirlansa yoki boshqasi yoqilsa — yangi versiya darhol ko‘rinadi */
const versionOf = (a: Announcement) => `${a.id}:${a.updated_at}`;

function hiddenNow(a: Announcement) {
  try {
    const saved = JSON.parse(localStorage.getItem(HIDE_KEY) ?? "null") as { v: string; until: number } | null;
    return saved?.v === versionOf(a) && saved.until > Date.now();
  } catch {
    return false;
  }
}

function hideForDays(a: Announcement) {
  try {
    localStorage.setItem(HIDE_KEY, JSON.stringify({ v: versionOf(a), until: Date.now() + HIDE_DAYS * 24 * 60 * 60 * 1000 }));
  } catch {
    /* private rejim — keyingi tashrifda yana chiqadi */
  }
}

/** Matndagi {n} va {product} o‘rniga sovg‘a shartlari qo‘yiladi */
export function fillTemplate(text: string, reward: Pick<PublicReward, "required_friends" | "product_name"> | null) {
  if (!reward) return text;
  return text.replaceAll("{n}", String(reward.required_friends)).replaceAll("{product}", reward.product_name);
}

/** Bosh sahifadagi faol e’lon oynasi (admin «Yangiliklar»da qaysi birini yoqsa — o‘sha, 3 kunda bir marta) */
export default function AnnouncementPopup() {
  const { user, loading, openLogin } = useAuth();
  const router = useRouter();
  const [item, setItem] = useState<Announcement | null>(null);
  const [reward, setReward] = useState<PublicReward | null>(null);
  const [friends, setFriends] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (loading) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    (async () => {
      const active = await api<Announcement | null>("/announcements/active").catch(() => null);
      if (!active || hiddenNow(active)) return;
      let first: PublicReward | null = null;
      let count = 0;
      if (active.kind === "referral") {
        // Faol sovg‘a bo‘lmasa yoki foydalanuvchi uni allaqachon olgan bo‘lsa — ko‘rsatilmaydi
        first = (await api<PublicReward[]>("/referrals/rewards").catch(() => []))[0] ?? null;
        if (!first) return;
        if (user) {
          const me = await api<MyReferral>("/referrals/me").catch(() => null);
          if (me?.rewards.find((r) => r.id === first?.id)?.granted) return;
          count = me?.friends ?? 0;
        }
      }
      if (!alive) return;
      setItem(active);
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
    if (!open || !item) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        hideForDays(item);
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, item]);

  if (!open || !item) return null;

  const later = () => {
    hideForDays(item);
    setOpen(false);
  };

  const action = () => {
    later();
    if (item.kind === "referral") {
      // Kirmagan bo‘lsa — Telegram orqali kiradi, so‘ng do‘stlar sahifasiga o‘tadi
      if (user) router.push(REFERRAL_PAGE);
      else openLogin({ onSuccess: () => router.push(REFERRAL_PAGE) });
    } else if (item.button_url.startsWith("/")) {
      router.push(item.button_url);
    } else if (item.button_url) {
      window.open(item.button_url, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div
      className="fixed inset-0 z-[80] grid grid-cols-1 place-items-center overflow-y-auto bg-slate-900/45 p-4 backdrop-blur-sm"
      onMouseDown={(e) => e.target === e.currentTarget && later()}
    >
      <AnnouncementCard item={item} reward={reward} friends={friends} onAction={action} onClose={later} />
    </div>
  );
}

/** E’lon oynasining o‘zi — saytda ham, admin oldindan ko‘rishida ham shu ishlatiladi */
export function AnnouncementCard({
  item,
  reward,
  friends = 0,
  onAction,
  onClose,
}: {
  item: Pick<Announcement, "kind" | "title" | "highlight" | "subtitle" | "text" | "button_text" | "image_url">;
  reward: Pick<PublicReward, "required_friends" | "product_name"> | null;
  friends?: number;
  onAction?: () => void;
  onClose?: () => void;
}) {
  const fill = (text: string) => fillTemplate(text, reward);
  const referral = item.kind === "referral";
  const total = reward?.required_friends ?? 0;
  const dots = Math.min(total, 20);
  const filled = Math.min(friends, total);
  const filledDots = total ? Math.round((filled / total) * dots) : 0;
  const buttonText = item.button_text || (referral ? "Taklif havolasini olish" : "");

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="announcement-title"
      className="animate-[pop_.35s_cubic-bezier(.2,.9,.3,1.3)] relative grid w-full max-w-3xl grid-cols-1 overflow-hidden rounded-[2rem] bg-white shadow-2xl md:grid-cols-[minmax(0,1fr)_330px]"
    >
      <button
        onClick={onClose}
        aria-label="Yopish"
        className="absolute right-4 top-4 z-10 grid size-9 place-items-center rounded-full bg-white/70 text-slate-500 backdrop-blur transition hover:bg-slate-100 hover:text-slate-800"
      >
        <Close className="size-5" />
      </button>

      {/* Matn */}
      <div className="order-2 p-7 sm:p-9 md:order-1">
        <h2 id="announcement-title" className="text-3xl font-extrabold leading-tight tracking-tight sm:text-[2.1rem]">
          {fill(item.title)}
          {item.highlight && (
            <>
              <br />
              <span className="text-brand">{fill(item.highlight)}</span>
            </>
          )}
        </h2>
        {item.subtitle && <p className="mt-3 text-lg font-semibold text-slate-700">{fill(item.subtitle)}</p>}
        {item.text && <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-500">{fill(item.text)}</p>}

        {referral && total > 0 && (
          <>
            <p className="mt-6 text-sm font-semibold text-slate-700">
              {filled} / {total} do‘st
            </p>
            <div className="mt-2.5 flex flex-wrap gap-2" aria-hidden>
              {Array.from({ length: dots }, (_, i) => (
                <span key={i} className={`size-3.5 rounded-full ${i < filledDots ? "bg-brand shadow-sm shadow-blue-600/40" : "bg-slate-200"}`} />
              ))}
            </div>
          </>
        )}

        {buttonText && (
          <button
            onClick={onAction}
            className="mt-7 flex w-full items-center justify-center gap-2.5 rounded-2xl bg-brand py-4 text-base font-semibold text-white shadow-lg shadow-blue-600/30 transition hover:bg-brand-dark sm:max-w-xs"
          >
            {referral ? <LinkIcon className="size-5" /> : null}
            {buttonText}
            {referral ? null : <ArrowRight className="size-5" />}
          </button>
        )}
        <button onClick={onClose} className={`w-full text-sm font-semibold text-brand hover:underline sm:max-w-xs ${buttonText ? "mt-3" : "mt-7"}`}>
          {buttonText ? "Keyinroq" : "Yopish"}
        </button>
      </div>

      {/* O‘ng tomon: yuklangan rasm yoki bezak */}
      <div aria-hidden className="keep-light relative order-1 h-60 overflow-hidden bg-gradient-to-br from-[#eef2ff] via-[#f3efff] to-[#e3ecff] md:order-2 md:h-auto">
        {item.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- admin yuklagan rasm, o‘lchami oldindan noma’lum
          <img src={item.image_url} alt="" className="absolute inset-0 size-full object-cover" />
        ) : referral ? (
          <GiftArt />
        ) : (
          <MegaphoneArt />
        )}
      </div>
    </div>
  );
}

function Glow() {
  return (
    <>
      <div className="absolute left-1/2 top-1/2 size-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/70 blur-3xl" />
      <div className="absolute bottom-0 left-1/2 h-24 w-56 -translate-x-1/2 rounded-full bg-indigo-200/60 blur-2xl" />
      <Sparkle className="absolute left-[34%] top-[14%] size-4 text-fuchsia-400" />
      <Sparkle className="absolute right-[30%] top-[38%] size-5 text-sky-400" />
      <Sparkle className="absolute bottom-[22%] left-[24%] size-3 text-violet-400" />
    </>
  );
}

/** Sovg‘a qutisi, yulduz va do‘stlar */
function GiftArt() {
  return (
    <div className="absolute inset-0">
      <Glow />
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

      <div className="absolute bottom-[7%] left-1/2 w-28 -translate-x-1/2 md:bottom-[14%] md:w-44">
        <div className="absolute -top-[95%] left-1/2 w-[85%] -translate-x-1/2 drop-shadow-[0_10px_25px_rgba(99,102,241,0.45)]">
          <Star id="promo-star" />
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
  );
}

/** Oddiy e’lon uchun: karnay va yulduzlar */
function MegaphoneArt() {
  return (
    <div className="absolute inset-0">
      <Glow />
      <div className="absolute right-[14%] top-[14%] w-14 rotate-12 drop-shadow-[0_8px_18px_rgba(99,102,241,0.4)] md:w-20">
        <Star id="ann-star" />
      </div>
      <span className="absolute left-1/2 top-1/2 grid size-28 -translate-x-1/2 -translate-y-1/2 -rotate-12 place-items-center rounded-[2rem] bg-gradient-to-br from-[#4f9cff] via-[#6d5dfc] to-[#c05cff] text-white shadow-2xl shadow-indigo-600/40 md:size-36">
        <Megaphone className="size-1/2" />
      </span>
    </div>
  );
}

function Star({ id }: { id: string }) {
  return (
    <svg viewBox="0 0 100 100" className="w-full">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4f9cff" />
          <stop offset="0.55" stopColor="#6d5dfc" />
          <stop offset="1" stopColor="#c05cff" />
        </linearGradient>
      </defs>
      <path d="M50 2C53 30 70 47 98 50 70 53 53 70 50 98 47 70 30 53 2 50 30 47 47 30 50 2Z" fill={`url(#${id})`} />
    </svg>
  );
}

function Sparkle({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 0c.7 6.4 5.6 11.3 12 12-6.4.7-11.3 5.6-12 12-.7-6.4-5.6-11.3-12-12C6.4 11.3 11.3 6.4 12 0Z" />
    </svg>
  );
}
