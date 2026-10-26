"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useAuth } from "../components/auth/AuthProvider";
import { Wallet as WalletIcon } from "../components/icons";
import { formatPrice } from "../mahsulotlar/catalog-data";
import { api, formatDate, topUpStatusMeta, type TopUp, type Transaction, type Wallet } from "../lib/api";
import { Card, ErrorText } from "./ui";

const QUICK_AMOUNTS = [50000, 100000, 200000, 500000];
// Admin tasdiqlashini kutayotganda holatni shu oraliqda yangilab turamiz
const POLL_MS = 15000;

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

      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand to-[#0b3fd1] p-6 text-white shadow-lg shadow-blue-600/25">
        <div aria-hidden className="absolute -right-10 -top-16 size-56 rounded-full bg-white/10 blur-2xl" />
        <div className="relative flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-2xl bg-white/15">
            <WalletIcon className="size-5" />
          </span>
          <p className="text-sm text-white/80">Hisobingizdagi mablag‘</p>
        </div>
        {wallet ? (
          <p className="relative mt-4 text-3xl font-extrabold sm:text-4xl">{formatPrice(wallet.balance)} so‘m</p>
        ) : (
          <span className="relative mt-4 block h-10 w-48 animate-pulse rounded-lg bg-white/20" />
        )}
        <p className="relative mt-2 text-sm text-white/80">Xaridlar shu hisobdan to‘lanadi.</p>
      </div>

      {wallet && (
        <TopUpForm
          wallet={wallet}
          onCreated={(t) => {
            setTopups((prev) => [t, ...(prev ?? [])]);
          }}
        />
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
  );
}

function TopUpForm({ wallet, onCreated }: { wallet: Wallet; onCreated: (t: TopUp) => void }) {
  const [amount, setAmount] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const preview = useMemo(() => (file?.type.startsWith("image/") ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  if (!wallet.topup_enabled) {
    return (
      <Card title="Hisobni to‘ldirish">
        <p className="text-sm text-slate-500">Hisobni to‘ldirish hozircha mavjud emas. Operatorga murojaat qiling.</p>
      </Card>
    );
  }

  const value = Number(amount.replace(/\D/g, ""));

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
      setMessage({ ok: false, text: "Chek rasmini yuklang" });
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

  const input =
    "mt-1.5 h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10";

  return (
    <Card title="Hisobni to‘ldirish">
      <ol className="space-y-5">
        <li>
          <p className="text-sm font-semibold">1. Quyidagi kartaga pul o‘tkazing</p>
          {wallet.card_number ? (
            <div className="mt-2 flex flex-wrap items-center gap-3 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-lg font-bold tracking-wider">{wallet.card_number}</p>
                {wallet.card_holder && <p className="text-xs text-slate-500">{wallet.card_holder}</p>}
              </div>
              <button
                type="button"
                onClick={copyCard}
                className="rounded-lg bg-white px-3.5 py-2 text-xs font-semibold text-brand ring-1 ring-slate-200 hover:ring-brand"
              >
                {copied ? "Nusxalandi ✓" : "Nusxalash"}
              </button>
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">Karta raqamini operatordan so‘rang.</p>
          )}
        </li>

        <li>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-sm font-semibold">
                2. O‘tkazgan summangiz
                <input
                  value={amount}
                  onChange={(e) => {
                    const n = e.target.value.replace(/\D/g, "");
                    setAmount(n ? formatPrice(Number(n)) : "");
                  }}
                  inputMode="numeric"
                  placeholder="100 000"
                  className={input}
                />
              </label>
              <div className="mt-2 flex flex-wrap gap-2">
                {QUICK_AMOUNTS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => setAmount(formatPrice(q))}
                    className={`rounded-full px-3 py-1.5 text-xs font-semibold ring-1 transition ${
                      value === q ? "bg-brand-soft text-brand ring-brand" : "text-slate-600 ring-slate-200 hover:ring-brand"
                    }`}
                  >
                    {formatPrice(q)}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-sm font-semibold">3. Chek rasmini yuklang</p>
              <label className="mt-1.5 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-200 p-5 text-center transition hover:border-brand">
                {preview ? (
                  // eslint-disable-next-line @next/next/no-img-element -- lokal blob preview
                  <img src={preview} alt="Chek" className="max-h-56 rounded-xl object-contain" />
                ) : (
                  <span className="text-sm text-slate-500">
                    {file ? file.name : "Rasmni tanlash uchun bosing (JPG, PNG, PDF · 10 MB gacha)"}
                  </span>
                )}
                {file && <span className="text-xs font-semibold text-brand">Boshqa fayl tanlash</span>}
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  className="sr-only"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] ?? null);
                  }}
                />
              </label>
            </div>

            <button
              disabled={sending}
              className="w-full rounded-xl bg-brand py-3 text-sm font-semibold text-white shadow-md shadow-blue-600/25 hover:bg-brand-dark disabled:opacity-60"
            >
              {sending ? "Yuborilmoqda..." : "Chekni yuborish"}
            </button>
            {message && (
              <p className={`rounded-xl px-4 py-3 text-sm ${message.ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-600"}`}>
                {message.text}
              </p>
            )}
          </form>
        </li>
      </ol>
    </Card>
  );
}
