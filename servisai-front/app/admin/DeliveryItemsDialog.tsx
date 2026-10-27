"use client";

import { useCallback, useEffect, useState } from "react";
import { Close, Trash } from "../components/icons";
import { api, formatDate, type AdminProduct, type DeliveryItem } from "../lib/api";
import { invalidateProducts } from "../lib/products";
import { ErrorText } from "../profil/ui";

/** Avtomatik mahsulotning havola/kodlar ro‘yxati: qo‘shish, berilmaganlarni o‘chirish, kimga berilganini ko‘rish */
export default function DeliveryItemsDialog({
  product,
  onClose,
  onStockChange,
}: {
  product: AdminProduct;
  onClose: () => void;
  onStockChange: (stock: number) => void;
}) {
  const [tab, setTab] = useState<"available" | "delivered">("available");
  const [items, setItems] = useState<DeliveryItem[] | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const load = useCallback(() => {
    api<DeliveryItem[]>(`/admin/products/${product.id}/items?state=${tab}`)
      .then(setItems)
      .catch((e: Error) => setError(e.message));
  }, [product.id, tab]);

  useEffect(load, [load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);

  const add = async () => {
    if (lines.length === 0) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const r = await api<{ added: number; skipped: number; stock: number }>(`/admin/products/${product.id}/items`, {
        method: "POST",
        json: { lines },
      });
      setText("");
      setInfo(`${r.added} ta qo‘shildi${r.skipped ? `, ${r.skipped} ta takror/bo‘sh qator o‘tkazib yuborildi` : ""}. Endi sotuvda: ${r.stock} ta.`);
      onStockChange(r.stock);
      invalidateProducts();
      if (tab === "available") load();
      else setTab("available");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (item: DeliveryItem) => {
    if (!confirm(`Bu element o‘chirilsinmi?\n\n${item.content}`)) return;
    setError(null);
    try {
      await api(`/admin/products/${product.id}/items/${item.id}`, { method: "DELETE" });
      setItems((list) => list?.filter((x) => x.id !== item.id) ?? null);
      onStockChange(Math.max(0, (product.stock ?? 1) - 1));
      invalidateProducts();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[70] overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:p-8"
      onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}
    >
      <div className="mx-auto w-full max-w-2xl rounded-3xl bg-white shadow-2xl" role="dialog" aria-labelledby="items-title">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <h2 id="items-title" className="text-lg font-bold">🔗 Havolalar — {product.name}</h2>
            <p className="text-xs text-slate-500">Har bir xaridorga ro‘yxatdan bittadan, takrorlanmasdan beriladi</p>
          </div>
          <button aria-label="Yopish" onClick={onClose} disabled={busy} className="grid size-9 place-items-center rounded-lg hover:bg-slate-100">
            <Close className="size-5" />
          </button>
        </div>

        <div className="space-y-5 p-6">
          {product.delivery_mode !== "auto" && (
            <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
              ⚠️ Bu mahsulot hozir <b>qo‘lda</b> yetkaziladi. Havolalar avtomatik berilishi uchun mahsulotni tahrirlab, “Yetkazib berish: Avtomatik”
              ni tanlang.
            </p>
          )}

          <div>
            <label className="text-sm font-semibold" htmlFor="items-input">
              Yangi havolalar qo‘shish
            </label>
            <textarea
              id="items-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              placeholder={"Har bir havola alohida qatorda:\nhttps://one.google.com/...1\nhttps://one.google.com/...2"}
              className="mt-1.5 w-full resize-y rounded-xl border border-slate-200 px-3.5 py-2.5 font-mono text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
            />
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="text-xs text-slate-500">{lines.length} ta qator</span>
              <button
                onClick={add}
                disabled={busy || lines.length === 0}
                className="rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/20 hover:bg-brand-dark disabled:opacity-50"
              >
                {busy ? "Qo‘shilmoqda..." : `${lines.length || ""} ta qo‘shish`}
              </button>
            </div>
          </div>

          {info && <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{info}</p>}
          {error && <ErrorText text={error} />}

          <div>
            <div className="flex gap-2">
              {(
                [
                  { id: "available", label: `Berilmagan (${product.stock ?? 0})` },
                  { id: "delivered", label: "Berilganlar" },
                ] as const
              ).map((t) => (
                <button
                  key={t.id}
                  onClick={() => {
                    setItems(null);
                    setTab(t.id);
                  }}
                  className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
                    tab === t.id ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="mt-3 max-h-80 overflow-y-auto rounded-2xl ring-1 ring-slate-100">
              {!items ? (
                <div className="h-24 animate-pulse bg-slate-50" />
              ) : items.length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-slate-500">
                  {tab === "available" ? "Berilmagan havola yo‘q — mahsulot “Tugagan” ko‘rinadi." : "Hali hech kimga berilmagan."}
                </p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {items.map((item) => (
                    <li key={item.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                      <span className="min-w-0 flex-1 truncate font-mono" title={item.content}>
                        {item.content}
                      </span>
                      {tab === "available" ? (
                        <button
                          aria-label="O‘chirish"
                          title="O‘chirish"
                          onClick={() => remove(item)}
                          className="grid size-8 shrink-0 place-items-center rounded-lg text-rose-500 hover:bg-rose-50"
                        >
                          <Trash className="size-4" />
                        </button>
                      ) : (
                        <span className="shrink-0 text-right text-xs text-slate-500">
                          <span className="font-semibold text-slate-700">{item.user_name ?? "—"}</span>
                          {item.order_number && ` · ${item.order_number}`}
                          <br />
                          {item.delivered_at && formatDate(item.delivered_at)}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
