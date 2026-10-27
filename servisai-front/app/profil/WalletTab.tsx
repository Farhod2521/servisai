"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useAuth } from "../components/auth/AuthProvider";
import { ArrowRight, ChevronDown, Clock, CloudUpload, Copy, Headset, Wallet as WalletIcon } from "../components/icons";
import { formatPrice } from "../mahsulotlar/catalog-data";
import { api, formatDate, topUpStatusMeta, type TopUp, type Transaction, type Wallet } from "../lib/api";
import { Card, ErrorText } from "./ui";

const QUICK_AMOUNTS = [50000, 100000, 200000, 500000];
// Admin tasdiqlashini kutayotganda holatni shu oraliqda yangilab turamiz
const POLL_MS = 15000;
const ADMIN_TELEGRAM = "https://t.me/Boss_uz";
const MAX_FILE_MB = 10;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const HISTORY_ID = "hisob-tarixi";

const txLabels: Record<Transaction["type"], string> = {
  topup: "Hisob to‘ldirildi",
  purchase: "Xarid",
  refund: "Qaytarildi",
};

export default function WalletTab() {
  const { refreshUser } = useAuth();
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [topups, setTopups] = useState<TopUp[] | null>(null);
  const [txs, setTxs] = useState<Transaction[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(
    () =>
      Promise.all([api<Wallet>("/wallet"), api<TopUp[]>("/wallet/topups"), api<Transaction[]>("/wallet/transactions")])
        .then(([w, t, x]) => {
          setWallet(w);
          setTopups(t);
          setTxs(x);
          setError(null);
        })
        .catch((e: Error) => setError(e.message)),
    [],
  );

  useEffect(() => {
    reload();
  }, [reload]);

  const hasPending = topups?.some((t) => t.status === "pending") ?? false;
  useEffect(() => {
    if (!hasPending) return;
    const id = setInterval(() => {
      reload();
      refreshUser();
    }, POLL_MS);
    return () => clearInterval(id);
  }, [hasPending, reload, refreshUser]);

  return (
    <div className="space-y-6">
      {error && <ErrorText text={error} />}

      <BalanceHero balance={wallet?.balance ?? null} />

      {wallet && (
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 sm:p-7">
            <TopUpForm wallet={wallet} onCreated={(t) => setTopups((prev) => [t, ...(prev ?? [])])} />
          </div>
          <aside className="space-y-6">
            <ComingSoonCard />
            <InfoCard />
            <WalletFaq wallet={wallet} />
          </aside>
        </div>
      )}

      <Card title="To‘ldirish so‘rovlari">
        {!topups && <div className="h-20 animate-pulse rounded-2xl bg-slate-50" />}
        {topups?.length === 0 && <p className="text-sm text-slate-500">Hali so‘rov yuborilmagan.</p>}
        <ul className="divide-y divide-slate-100">
          {topups?.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{formatPrice(t.amount)} so‘m</p>
                <p className="text-xs text-slate-500">
                  #{t.id} · {formatDate(t.created_at)}
                  {t.admin_note && ` · ${t.admin_note}`}
                </p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${topUpStatusMeta[t.status].className}`}>
                {topUpStatusMeta[t.status].label}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <div id={HISTORY_ID} className="scroll-mt-24">
        <Card title="Hisob tarixi">
          {!txs && <div className="h-20 animate-pulse rounded-2xl bg-slate-50" />}
          {txs?.length === 0 && <p className="text-sm text-slate-500">Hisobda hali harakat bo‘lmagan.</p>}
          <ul className="divide-y divide-slate-100">
            {txs?.map((x) => (
              <li key={x.id} className="flex items-center gap-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">{txLabels[x.type]}</p>
                  <p className="truncate text-xs text-slate-500">
                    {formatDate(x.created_at)}
                    {x.note && ` · ${x.note}`}
                  </p>
                </div>
                <div className="text-right">
                  <p className={`font-bold ${x.amount > 0 ? "text-emerald-600" : "text-slate-800"}`}>
                    {x.amount > 0 ? "+" : "−"}
                    {formatPrice(Math.abs(x.amount))} so‘m
                  </p>
                  <p className="text-xs text-slate-400">Qoldiq: {formatPrice(x.balance_after)}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

/* ---------- Balans banneri ---------- */

function BalanceHero({ balance }: { balance: number | null }) {
  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#1557ff] via-[#2a6bff] to-[#6b9bff] p-6 text-white shadow-xl shadow-blue-600/25 sm:p-8">
      {/* Yumshoq to‘lqinlar */}
      <div aria-hidden className="absolute -bottom-28 right-1/4 h-56 w-[70%] rounded-[50%] bg-white/10" />
      <div aria-hidden className="absolute -bottom-36 right-0 h-56 w-[45%] rounded-[50%] bg-white/10" />
      <div aria-hidden className="absolute -right-16 -top-24 size-72 rounded-full bg-sky-200/20 blur-3xl" />

      <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-5">
          <span className="hidden size-20 shrink-0 place-items-center rounded-3xl bg-white/15 ring-1 ring-white/25 backdrop-blur sm:grid">
            <WalletIcon className="size-9" />
          </span>
          <div>
            <p className="text-sm text-white/85">Hisobingizdagi mablag‘</p>
            {balance === null ? (
              <span className="mt-2 block h-12 w-56 animate-pulse rounded-xl bg-white/20" />
            ) : (
              <p className="mt-1 text-4xl font-extrabold tracking-tight sm:text-5xl">{formatPrice(balance)} so‘m</p>
            )}
            <p className="mt-2 text-sm text-white/85">Xaridlar shu hisobdan to‘lanadi.</p>
          </div>
        </div>
        <button
          onClick={() => document.getElementById(HISTORY_ID)?.scrollIntoView({ behavior: "smooth" })}
          className="flex items-center gap-2 self-start rounded-2xl bg-white/15 px-5 py-3 text-sm font-semibold ring-1 ring-white/40 backdrop-blur transition hover:bg-white/25 sm:self-auto"
        >
          Hisob tarixi <ArrowRight className="size-4" />
        </button>
      </div>
    </div>
  );
}

/* ---------- To‘ldirish formasi ---------- */

/** Karta raqamining boshidan to‘lov tizimini aniqlaydi (yorliq va logotip uchun) */
function cardBrand(number: string) {
  const digits = number.replace(/\D/g, "");
  if (digits.startsWith("8600") || digits.startsWith("5614")) return { name: "UzCard", logo: "UZCARD", className: "text-[#1a4c9c]" };
  if (digits.startsWith("9860")) return { name: "Humo", logo: "HUMO", className: "text-[#0f8a5f]" };
  if (digits.startsWith("4")) return { name: "Visa", logo: "VISA", className: "italic text-[#1a1f71]" };
  if (/^5[1-5]/.test(digits) || /^2[2-7]/.test(digits)) return { name: "Mastercard", logo: "Mastercard", className: "text-[#eb001b]" };
  return { name: "Bank kartasi", logo: null, className: "" };
}

/** Rasmiy logolar (click.uz va cdn.payme.uz dan). Click yozuvi asli oq — yorug‘ fon uchun to‘q nusxasi ishlatiladi */
function ClickPaymeLogos({ height = "h-6" }: { height?: string }) {
  return (
    <span className="flex items-center gap-3">
      {/* eslint-disable-next-line @next/next/no-img-element -- kichik SVG, optimallashtirish shart emas */}
      <img src="/payments/click-dark.svg" alt="Click" className={`${height} w-auto`} />
      {/* eslint-disable-next-line @next/next/no-img-element -- kichik SVG, optimallashtirish shart emas */}
      <img src="/payments/payme.svg" alt="Payme" className={`${height} w-auto`} />
    </span>
  );
}

function StepTitle({ n, children }: { n: number; children: ReactNode }) {
  return (
    <p className="flex items-center gap-2.5 font-semibold">
      <span className="grid size-6 place-items-center rounded-full bg-brand-soft text-xs font-bold text-brand">{n}</span>
      {children}
    </p>
  );
}

function TopUpForm({ wallet, onCreated }: { wallet: Wallet; onCreated: (t: TopUp) => void }) {
  const [amount, setAmount] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const preview = useMemo(() => (file?.type.startsWith("image/") ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  const header = (
    <div>
      <h2 className="text-2xl font-bold">Hisobni to‘ldirish</h2>
      <p className="mt-1 text-slate-500">Qulay usulda balansingizni to‘ldiring va xizmatlardan foydalaning.</p>
    </div>
  );

  if (!wallet.topup_enabled) {
    return (
      <div>
        {header}
        <p className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
          Hisobni to‘ldirish hozircha mavjud emas.{" "}
          <a href={ADMIN_TELEGRAM} target="_blank" rel="noopener noreferrer" className="font-semibold text-brand hover:underline">
            Adminga murojaat qiling
          </a>
          .
        </p>
      </div>
    );
  }

  const value = Number(amount.replace(/\D/g, ""));
  const brand = wallet.card_number ? cardBrand(wallet.card_number) : null;
  // "8600123456789012" -> "8600 1234 5678 9012"
  const cardNumber = wallet.card_number?.replace(/\D/g, "").replace(/(\d{4})(?=\d)/g, "$1 ");

  const pickFile = (f: File | null | undefined) => {
    setMessage(null);
    if (!f) return;
    if (!ACCEPTED.includes(f.type)) {
      setMessage({ ok: false, text: "Chek JPG, PNG, WEBP rasm yoki PDF bo‘lishi kerak" });
      return;
    }
    if (f.size > MAX_FILE_MB * 1024 * 1024) {
      setMessage({ ok: false, text: `Fayl hajmi ${MAX_FILE_MB} MB dan oshmasligi kerak` });
      return;
    }
    setFile(f);
  };

  const copyCard = async () => {
    if (!wallet.card_number) return;
    try {
      await navigator.clipboard.writeText(wallet.card_number.replace(/\s/g, ""));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard ruxsat berilmagan */
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setMessage(null);
    if (value < wallet.min_amount || value > wallet.max_amount) {
      setMessage({ ok: false, text: `Summa ${formatPrice(wallet.min_amount)} – ${formatPrice(wallet.max_amount)} so‘m oralig‘ida bo‘lsin` });
      return;
    }
    if (!file) {
      setMessage({ ok: false, text: "To‘lov chekining rasmini yuklang" });
      return;
    }
    const form = new FormData();
    form.append("amount", String(value));
    form.append("receipt", file);
    setSending(true);
    try {
      const t = await api<TopUp>("/wallet/topups", { method: "POST", body: form });
      onCreated(t);
      setAmount("");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      setMessage({ ok: true, text: "Chek yuborildi! Admin tasdiqlagach, mablag‘ hisobingizga tushadi." });
    } catch (err) {
      setMessage({ ok: false, text: (err as Error).message });
    } finally {
      setSending(false);
    }
  };

  return (
    <form onSubmit={submit} className="min-w-0 space-y-7">
      {header}

      {/* 1. To‘lov usuli */}
      <section>
        <StepTitle n={1}>To‘lov usulini tanlang</StepTitle>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div aria-checked="true" role="radio" className="flex items-start gap-3 rounded-2xl bg-brand-soft/40 p-4 ring-2 ring-brand">
            <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full ring-2 ring-brand">
              <span className="size-2.5 rounded-full bg-brand" />
            </span>
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white text-brand shadow-sm">
              <WalletIcon className="size-5" />
            </span>
            <span>
              <span className="block font-semibold">Bank karta orqali</span>
              <span className="block text-sm text-slate-500">UzCard / Humo</span>
              <span className="block text-xs text-slate-400">Qo‘lda o‘tkazib to‘lash</span>
            </span>
          </div>
          <div
            aria-checked="false"
            aria-disabled="true"
            role="radio"
            title="Tez kunda"
            className="relative flex cursor-not-allowed items-start gap-3 rounded-2xl bg-slate-50/60 p-4 ring-1 ring-slate-200"
          >
            <span className="mt-0.5 size-5 shrink-0 rounded-full ring-2 ring-slate-300" />
            <span className="min-w-0">
              <ClickPaymeLogos />
              <span className="mt-1 block font-semibold text-slate-700">Click va Payme</span>
              <span className="block text-xs text-slate-400">To‘lovlar avtomatik ulanadi</span>
            </span>
            <span className="absolute right-3 top-3 rounded-full bg-violet-100 px-2.5 py-0.5 text-[11px] font-semibold text-violet-700">
              Tez kunda
            </span>
          </div>
        </div>
      </section>

      {/* 2. Summa */}
      <section>
        <StepTitle n={2}>O‘tkazgan summangiz</StepTitle>
        <label className="mt-3 flex h-14 items-center rounded-2xl border border-slate-200 bg-white px-4 transition focus-within:border-brand focus-within:ring-4 focus-within:ring-brand/10">
          <input
            value={amount}
            onChange={(e) => {
              const n = e.target.value.replace(/\D/g, "").slice(0, 10);
              setAmount(n ? formatPrice(Number(n)) : "");
            }}
            inputMode="numeric"
            placeholder="100 000"
            aria-label="Summa"
            className="min-w-0 flex-1 bg-transparent text-lg outline-none"
          />
          <span className="text-slate-500">so‘m</span>
        </label>
        <div className="mt-3 flex flex-wrap gap-2">
          {QUICK_AMOUNTS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setAmount(formatPrice(q))}
              className={`rounded-full px-5 py-2 text-sm font-semibold ring-1 transition ${
                value === q ? "bg-brand-soft text-brand ring-brand" : "bg-white text-slate-600 ring-slate-200 hover:ring-brand"
              }`}
            >
              {formatPrice(q)}
            </button>
          ))}
        </div>
      </section>

      {/* 3. Karta */}
      <section>
        <StepTitle n={3}>To‘lov ma’lumotlari</StepTitle>
        {wallet.card_number && brand ? (
          <div className="mt-3 rounded-2xl bg-slate-50/80 p-2 ring-1 ring-slate-100">
            <div className="flex gap-1 p-1">
              <span className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-brand shadow-sm">{brand.name}</span>
            </div>
            <div className="mt-1 flex items-center gap-4 rounded-xl bg-white p-4 sm:p-5">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm text-slate-500">
                  Karta raqami
                  <button
                    type="button"
                    onClick={copyCard}
                    aria-label="Karta raqamini nusxalash"
                    title="Nusxalash"
                    className={`grid size-7 place-items-center rounded-lg transition ${copied ? "bg-emerald-50 text-emerald-600" : "text-brand hover:bg-brand-soft"}`}
                  >
                    {copied ? <span className="text-xs font-bold">✓</span> : <Copy className="size-4" />}
                  </button>
                  {copied && <span className="text-xs font-semibold text-emerald-600">Nusxalandi</span>}
                </p>
                <p className="mt-1 whitespace-nowrap font-mono text-lg font-bold tracking-[0.1em] sm:text-2xl">{cardNumber}</p>
                {wallet.card_holder && <p className="mt-1 text-sm text-slate-500">{wallet.card_holder}</p>}
              </div>
              {brand.logo && (
                <span className={`hidden shrink-0 rounded-2xl bg-white px-3 py-4 text-center text-sm font-black shadow-sm ring-1 ring-slate-100 sm:block ${brand.className}`}>
                  {brand.logo}
                </span>
              )}
            </div>
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">Karta raqamini adminga yozib so‘rang.</p>
        )}
      </section>

      {/* 4. Chek */}
      <section>
        <StepTitle n={4}>Chek rasmini yuklang</StepTitle>
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            pickFile(e.dataTransfer.files?.[0]);
          }}
          className={`mt-3 flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-5 text-center transition sm:flex-row sm:text-left ${
            dragging ? "border-brand bg-brand-soft/60" : "border-slate-200 hover:border-brand hover:bg-slate-50/60"
          }`}
        >
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element -- lokal blob preview
            <img src={preview} alt="Chek" className="max-h-40 rounded-xl object-contain" />
          ) : (
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-brand-soft text-brand">
              <CloudUpload className="size-6" />
            </span>
          )}
          <span>
            <span className="block text-sm font-semibold text-slate-700">
              {file ? file.name : "Rasmni tanlash uchun bosing yoki bu yerga sudrab tashlang"}
            </span>
            <span className="mt-0.5 block text-xs text-slate-500">
              {file ? "Boshqa fayl tanlash uchun bosing" : `JPG, PNG, PDF • ${MAX_FILE_MB} MB gacha`}
            </span>
          </span>
          <input ref={fileRef} type="file" accept={ACCEPTED.join(",")} className="sr-only" onChange={(e) => pickFile(e.target.files?.[0])} />
        </label>
      </section>

      {message && (
        <p className={`rounded-xl px-4 py-3 text-sm ${message.ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-600"}`}>{message.text}</p>
      )}

      <button
        disabled={sending}
        className="flex w-full items-center justify-center gap-2 rounded-2xl bg-brand py-4 text-base font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-brand-dark disabled:opacity-60"
      >
        {sending ? "Yuborilmoqda..." : "To‘lovni amalga oshirdim"}
        {!sending && <ArrowRight className="size-5" />}
      </button>
    </form>
  );
}

/* ---------- O‘ng ustun ---------- */

function ComingSoonCard() {
  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#eef2ff] via-[#f3f0ff] to-[#e8f0ff] p-6 ring-1 ring-indigo-100">
      {/* Kalendar bezagi */}
      <div aria-hidden className="absolute right-5 top-8 hidden sm:block">
        <div className="relative w-20 rotate-[-6deg] overflow-hidden rounded-2xl bg-white shadow-lg shadow-indigo-900/10 ring-1 ring-indigo-100">
          <div className="h-5 bg-gradient-to-r from-indigo-400 to-violet-400" />
          <div className="grid grid-cols-3 gap-1 p-2">
            {Array.from({ length: 6 }, (_, i) => (
              <span key={i} className={`h-2.5 rounded ${i === 4 ? "bg-violet-300" : "bg-indigo-100"}`} />
            ))}
          </div>
        </div>
        <span className="absolute -bottom-3 -right-3 grid size-9 place-items-center rounded-full bg-white text-indigo-500 shadow-md ring-2 ring-indigo-100">
          <Clock className="size-5" />
        </span>
      </div>

      <span className="inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-700">Tez kunda</span>
      <div className="mt-4">
        <ClickPaymeLogos height="h-8" />
      </div>
      <p className="mt-3 text-lg font-bold">To‘lovlar avtomatik ulanadi</p>
      <p className="mt-2 max-w-[15rem] text-sm text-slate-500">Hisobni bir zumda, chek yuklamasdan to‘ldirish imkoniyati tez orada.</p>
      <span className="mt-4 inline-flex items-center gap-2 rounded-full bg-indigo-100/80 px-3 py-1 text-xs font-semibold text-indigo-700">
        <span className="size-2 animate-pulse rounded-full bg-indigo-500" /> Ishlab chiqilmoqda
      </span>
    </div>
  );
}

function InfoCard() {
  const items = [
    { icon: <Clock className="size-5" />, text: "Chek odatda bir necha daqiqada tekshiriladi va mablag‘ hisobingizga tushadi." },
    {
      icon: <span className="grid size-5 place-items-center rounded-full ring-2 ring-current text-[11px] font-bold">i</span>,
      text: "Pul o‘tkazgandan so‘ng chekni yuklab, «To‘lovni amalga oshirdim» tugmasini bosing.",
    },
    {
      icon: <Headset className="size-5" />,
      text: (
        <>
          Savollar bo‘lsa,{" "}
          <a href={ADMIN_TELEGRAM} target="_blank" rel="noopener noreferrer" className="font-semibold text-brand hover:underline">
            biz bilan bog‘laning
          </a>
          .
        </>
      ),
    },
  ];
  return (
    <div className="rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
      <p className="text-lg font-bold">Ma’lumot</p>
      <ul className="mt-4 space-y-4">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-3 text-sm text-slate-600">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-soft text-brand">{item.icon}</span>
            <span className="pt-2">{item.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function WalletFaq({ wallet }: { wallet: Wallet }) {
  const items = [
    {
      q: "Minimal to‘lov summasi qancha?",
      a: `Eng kamida ${formatPrice(wallet.min_amount)} so‘m, eng ko‘pi bilan ${formatPrice(wallet.max_amount)} so‘m.`,
    },
    {
      q: "Hisob necha vaqtda to‘ldiriladi?",
      a: "Chekni admin tekshirib tasdiqlagach, mablag‘ darhol hisobingizga tushadi. Bu sahifa holatni o‘zi yangilab turadi.",
    },
    {
      q: "Qaysi to‘lov usullarini qabul qilasiz?",
      a: "Hozircha karta orqali o‘tkazma (Click, Payme, Uzum yoki bank ilovasi orqali). Click/Payme orqali avtomatik to‘lov tez kunda.",
    },
    {
      q: "To‘lov tasdiqlanmasa nima qilish kerak?",
      a: "Chek rad etilsa, sababi “To‘ldirish so‘rovlari” ro‘yxatida yoziladi. Savol bo‘lsa, Telegram orqali adminga yozing: @Boss_uz.",
    },
  ];
  return (
    <div className="rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
      <div className="flex items-center justify-between gap-3">
        <p className="text-lg font-bold">Ko‘p so‘raladigan savollar</p>
        <Link href="/#faq" className="flex shrink-0 items-center gap-1 text-sm font-semibold text-brand hover:underline">
          Barchasini ko‘rish <ArrowRight className="size-4" />
        </Link>
      </div>
      <div className="mt-2 divide-y divide-slate-100">
        {items.map((f) => (
          <details key={f.q} className="group py-3">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm text-slate-700 [&::-webkit-details-marker]:hidden">
              {f.q}
              <ChevronDown className="size-4 shrink-0 text-slate-400 transition-transform group-open:rotate-180" />
            </summary>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">{f.a}</p>
          </details>
        ))}
      </div>
    </div>
  );
}
