"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Close } from "../components/icons";
import { api, type AdminProduct, type DeliveryMode, type DurationUnit, type ProductBadge, type ProductCategory, type ProductInput } from "../lib/api";
import {
  badgeStyles,
  catalogCategories,
  discountPercent,
  formatPrice,
  isSoldOut,
  stockLabel,
  toCatalogProduct,
} from "../mahsulotlar/catalog-data";

const DURATION_PRESETS = [1, 3, 6, 12, 18, 24];
const DELIVERY_TIME_PRESETS = ["10 daqiqa – 1 soat", "1–3 soat", "24 soatgacha"];

/** "ChatGPT Plus (1 oy)" -> "chatgpt-plus-1-oy" */
function slugify(text: string) {
  return text
    .toLowerCase()
    .replace(/[‘’'`ʻʼ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

const inputCls =
  "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10 disabled:bg-slate-50 disabled:text-slate-500";

export default function ProductForm({
  product,
  takenIds,
  nextSortOrder,
  onClose,
  onSaved,
}: {
  /** null — yangi mahsulot */
  product: AdminProduct | null;
  takenIds: string[];
  nextSortOrder: number;
  onClose: () => void;
  onSaved: (product: AdminProduct) => void;
}) {
  const isNew = product === null;
  const [name, setName] = useState(product?.name ?? "");
  const [id, setId] = useState(product?.id ?? "");
  // Foydalanuvchi ID’ni o‘zi o‘zgartirmaguncha u nomdan avtomatik yasaladi
  const [idTouched, setIdTouched] = useState(!isNew);
  const [description, setDescription] = useState(product?.description ?? "");
  const [price, setPrice] = useState<number | null>(product?.price ?? null);
  const [oldPrice, setOldPrice] = useState<number | null>(product?.old_price ?? null);
  const [durations, setDurations] = useState<number[]>(product?.durations ?? [1]);
  const [durationUnit, setDurationUnit] = useState<DurationUnit>(product?.duration_unit ?? "month");
  const unitWord = durationUnit === "day" ? "kun" : "oy";
  const [customDuration, setCustomDuration] = useState("");
  const [category, setCategory] = useState<ProductCategory>(product?.category ?? "chat");
  const [badge, setBadge] = useState<ProductBadge | "">(product?.badge ?? "");
  const [features, setFeatures] = useState((product?.features ?? []).join("\n"));
  const [sortOrder, setSortOrder] = useState(product?.sort_order ?? nextSortOrder);
  const [isActive, setIsActive] = useState(product?.is_active ?? true);
  // "" — cheklanmagan
  // Logo: yangi tanlangan fayl yoki yuklangan logoni olib tashlash (saqlanganda bajariladi)
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [removeLogo, setRemoveLogo] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const logoInput = useRef<HTMLInputElement>(null);
  const logoPreview = useMemo(() => (logoFile ? URL.createObjectURL(logoFile) : null), [logoFile]);
  useEffect(() => () => void (logoPreview && URL.revokeObjectURL(logoPreview)), [logoPreview]);
  const currentLogo = logoPreview ?? (removeLogo ? null : (product?.logo_url ?? null));
  const [stock, setStock] = useState(product?.stock === null || product?.stock === undefined ? "" : String(product.stock));
  const [soldBase, setSoldBase] = useState(String(product?.sold_base ?? 0));
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>(product?.delivery_mode ?? "manual");
  const [deliveryTime, setDeliveryTime] = useState(product?.delivery_time ?? DELIVERY_TIME_PRESETS[0]);
  const [notes, setNotes] = useState(product?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slug = idTouched ? id : slugify(name);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const toggleDuration = (d: number) =>
    setDurations((list) => (list.includes(d) ? list.filter((x) => x !== d) : [...list, d].sort((a, b) => a - b)));

  const addCustomDuration = () => {
    const d = Number(customDuration);
    if (Number.isInteger(d) && d >= 1 && d <= 366 && !durations.includes(d)) toggleDuration(d);
    setCustomDuration("");
  };

  // Yuborishdan oldingi tekshiruv (backend ham tekshiradi, bu tezkor javob uchun)
  const problem = (() => {
    if (!name.trim()) return "Mahsulot nomini kiriting";
    if (isNew) {
      if (slug.length < 2) return "ID kamida 2 belgidan iborat bo‘lsin";
      if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) return "ID faqat kichik lotin harflari, raqamlar va “-” dan iborat bo‘lsin";
      if (takenIds.includes(slug)) return `“${slug}” ID band, boshqasini tanlang`;
    }
    if (price === null) return "Narxni kiriting";
    if (oldPrice !== null && oldPrice <= price) return "Eski narx hozirgi narxdan katta bo‘lishi kerak";
    if (durations.length === 0) return "Kamida bitta obuna muddatini tanlang";
    if (!deliveryTime.trim()) return "Yetkazib berish vaqtini yozing";
    return null;
  })();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (problem || price === null) {
      setError(problem);
      return;
    }
    const body: ProductInput = {
      name: name.trim(),
      description: description.trim(),
      price,
      old_price: oldPrice,
      durations,
      duration_unit: durationUnit,
      category,
      badge: badge || null,
      features: features
        .split("\n")
        .map((f) => f.trim())
        .filter(Boolean),
      sort_order: sortOrder,
      stock: stock === "" ? null : Number(stock),
      sold_base: Number(soldBase) || 0,
      delivery_mode: deliveryMode,
      delivery_time: deliveryTime.trim(),
      notes: notes.trim(),
      is_active: isActive,
    };
    setBusy(true);
    setError(null);
    try {
      let saved = isNew
        ? await api<AdminProduct>("/admin/products", { method: "POST", json: { ...body, id: slug } })
        : await api<AdminProduct>(`/admin/products/${product.id}`, { method: "PATCH", json: body });
      if (logoFile) {
        const form = new FormData();
        form.append("file", logoFile);
        saved = await api<AdminProduct>(`/admin/products/${saved.id}/logo`, { method: "POST", body: form });
      } else if (removeLogo && saved.logo_url) {
        saved = await api<AdminProduct>(`/admin/products/${saved.id}/logo`, { method: "DELETE" });
      }
      onSaved(saved);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const preview = toCatalogProduct({
    id: slug || "yangi",
    name: name.trim() || "Mahsulot nomi",
    description: description.trim(),
    price: price ?? 0,
    old_price: oldPrice,
    durations: durations.length ? durations : [1],
    duration_unit: durationUnit,
    logo_url: currentLogo,
    category,
    badge: badge || null,
    features: [],
    stock: stock === "" ? null : Number(stock),
    // Haqiqiy xaridlar o‘zgarmaydi, faqat boshlang‘ich son tahrirlanadi
    sold_count: (product ? product.sold_count - product.sold_base : 0) + (Number(soldBase) || 0),
    delivery_time: deliveryTime,
    instant_delivery: deliveryMode === "auto",
    notes,
  });
  const soldOut = isSoldOut(preview);
  const previewStock = stockLabel(preview);
  const discount = discountPercent(preview);

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:p-8" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <form
        onSubmit={submit}
        className="mx-auto w-full max-w-4xl rounded-3xl bg-white shadow-2xl"
        aria-labelledby="product-form-title"
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 id="product-form-title" className="text-lg font-bold">
            {isNew ? "Yangi mahsulot" : `Tahrirlash: ${product.name}`}
          </h2>
          <button type="button" aria-label="Yopish" onClick={onClose} disabled={busy} className="grid size-9 place-items-center rounded-lg hover:bg-slate-100">
            <Close className="size-5" />
          </button>
        </div>

        <div className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1fr)_260px]">
          <div className="space-y-5">
            <Field label="Nomi" required>
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={255} placeholder="Masalan: ChatGPT Plus" className={inputCls} autoFocus />
            </Field>

            <Field
              label="ID (sahifa manzili)"
              hint={isNew ? `Sayt manzili: /mahsulotlar/${slug || "..."}` : "Yaratilgandan keyin o‘zgartirib bo‘lmaydi"}
            >
              <input
                value={slug}
                onChange={(e) => {
                  setIdTouched(true);
                  setId(e.target.value.toLowerCase());
                }}
                disabled={!isNew}
                maxLength={64}
                placeholder="chatgpt-plus"
                className={`${inputCls} font-mono`}
              />
            </Field>

            <Field label="Logo" hint="PNG, JPG yoki WEBP, 2 MB gacha (kvadrat rasm yaxshi ko‘rinadi). Yuklanmasa — standart logo.">
              <div className="flex items-center gap-4">
                <div className="size-16 shrink-0 text-sm">{preview.logo}</div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => logoInput.current?.click()}
                    className="rounded-xl bg-brand-soft px-4 py-2 text-sm font-semibold text-brand ring-1 ring-brand/20 hover:ring-brand"
                  >
                    {currentLogo ? "Boshqa logo" : "Logo yuklash"}
                  </button>
                  {currentLogo && (
                    <button
                      type="button"
                      onClick={() => {
                        setLogoFile(null);
                        setRemoveLogo(true);
                        if (logoInput.current) logoInput.current.value = "";
                      }}
                      className="rounded-xl px-4 py-2 text-sm font-semibold text-rose-600 ring-1 ring-slate-200 hover:bg-rose-50"
                    >
                      Olib tashlash
                    </button>
                  )}
                </div>
                <input
                  ref={logoInput}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="sr-only"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    setLogoError(null);
                    if (!f) return;
                    if (!["image/png", "image/jpeg", "image/webp"].includes(f.type)) {
                      setLogoError("Logo PNG, JPG yoki WEBP bo‘lishi kerak");
                      return;
                    }
                    if (f.size > 2 * 1024 * 1024) {
                      setLogoError("Logo hajmi 2 MB dan oshmasligi kerak");
                      return;
                    }
                    setRemoveLogo(false);
                    setLogoFile(f);
                  }}
                />
              </div>
              {logoError && <p className="mt-1.5 text-xs text-rose-600">{logoError}</p>}
            </Field>

            <Field label="Tavsif" hint="Katalog kartochkasi va servis sahifasida ko‘rinadi">
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder="Servis haqida qisqacha: nimalar beradi, kimlar uchun..."
                className={`${inputCls} resize-y`}
              />
            </Field>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Narx (so‘m)" required>
                <PriceInput value={price} onChange={setPrice} placeholder="200 000" />
              </Field>
              <Field label="Eski narx (so‘m)" hint="Ixtiyoriy — chegirma ko‘rsatish uchun">
                <PriceInput value={oldPrice} onChange={setOldPrice} placeholder="—" />
              </Field>
            </div>

            <Field label="Muddat" required hint="Narx birinchi (eng qisqa) muddat uchun ko‘rsatiladi">
              <div className="mb-2 inline-flex rounded-xl bg-slate-100 p-1">
                {(
                  [
                    { id: "month", label: "Oy" },
                    { id: "day", label: "Kun" },
                  ] as const
                ).map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    aria-pressed={durationUnit === u.id}
                    onClick={() => setDurationUnit(u.id)}
                    className={`rounded-lg px-4 py-1.5 text-sm font-semibold transition ${
                      durationUnit === u.id ? "bg-white text-brand shadow-sm" : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {u.label}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {[...new Set([...DURATION_PRESETS, ...durations])].sort((a, b) => a - b).map((d) => {
                  const on = durations.includes(d);
                  return (
                    <button
                      key={d}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggleDuration(d)}
                      className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                        on ? "bg-brand text-white shadow-md shadow-blue-600/20" : "bg-slate-50 text-slate-600 ring-1 ring-slate-200 hover:ring-brand"
                      }`}
                    >
                      {d} {unitWord}
                    </button>
                  );
                })}
                <span className="flex items-center gap-1">
                  <input
                    value={customDuration}
                    onChange={(e) => setCustomDuration(e.target.value.replace(/\D/g, "").slice(0, 3))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustomDuration();
                      }
                    }}
                    inputMode="numeric"
                    placeholder="boshqa"
                    aria-label={`Boshqa muddat (${unitWord})`}
                    className="w-20 rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand"
                  />
                  <button type="button" onClick={addCustomDuration} className="rounded-xl px-3 py-2 text-sm font-semibold text-brand hover:bg-brand-soft">
                    + qo‘shish
                  </button>
                </span>
              </div>
            </Field>

            {deliveryMode === "auto" ? (
              <div className="rounded-2xl bg-brand-soft/60 px-4 py-3 text-sm text-slate-700">
                <span className="font-semibold">Soni avtomatik:</span> qo‘shilgan havolalar soniga teng
                {product ? ` (hozir ${product.stock ?? 0} ta, sotilgan ${product.sold_count} ta)` : ""}.
              </div>
            ) : (
            <Field
              label="Soni (sotuvda nechta bor)"
              hint={
                (stock === "" ? "Bo‘sh — cheklanmagan. " : stock === "0" ? "0 — saytda “Tugagan”, oq-qora ko‘rinadi. " : "Har xariddan keyin 1 taga kamayadi. ") +
                (product ? `Hozirgacha sotilgan: ${product.sold_count} ta` : "")
              }
            >
              <div className="flex items-center gap-2">
                <input
                  inputMode="numeric"
                  value={stock}
                  onChange={(e) => setStock(e.target.value.replace(/\D/g, "").replace(/^0+(?=\d)/, "").slice(0, 7))}
                  placeholder="Cheklanmagan"
                  className={`${inputCls} max-w-48`}
                />
                {stock !== "" && (
                  <button type="button" onClick={() => setStock("")} className="rounded-xl px-3 py-2 text-sm font-semibold text-slate-500 hover:bg-slate-100">
                    Cheklanmagan qilish
                  </button>
                )}
              </div>
            </Field>
            )}

            <Field
              label="Boshlang‘ich “sotib olganlar” soni"
              hint={`Saytda reyting yonida qavs ichida chiqadi; har bir xarid shu songa qo‘shiladi.${
                product ? ` Haqiqiy xaridlar: ${product.sold_count - product.sold_base} ta → saytda: ${preview.sold_count} ta` : ""
              }`}
            >
              <input
                inputMode="numeric"
                value={soldBase}
                onChange={(e) => setSoldBase(e.target.value.replace(/\D/g, "").replace(/^0+(?=\d)/, "").slice(0, 7))}
                className={`${inputCls} max-w-48`}
              />
            </Field>

            <div className="rounded-2xl bg-slate-50/80 p-4 ring-1 ring-slate-100">
              <p className="text-sm font-semibold">Yetkazib berish</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {(
                  [
                    { id: "manual", title: "Qo‘lda", text: "Admin login/parolni o‘zi yuboradi (CapCut, ChatGPT)" },
                    { id: "auto", title: "Avtomatik", text: "Har xaridorga ro‘yxatdan alohida havola darhol beriladi + konfetti" },
                  ] as const
                ).map((o) => (
                  <button
                    key={o.id}
                    type="button"
                    aria-pressed={deliveryMode === o.id}
                    onClick={() => setDeliveryMode(o.id)}
                    className={`rounded-xl p-3 text-left ring-1 transition ${
                      deliveryMode === o.id ? "bg-white ring-2 ring-brand" : "bg-white/60 ring-slate-200 hover:ring-brand/50"
                    }`}
                  >
                    <span className={`text-sm font-semibold ${deliveryMode === o.id ? "text-brand" : ""}`}>{o.title}</span>
                    <span className="mt-0.5 block text-xs text-slate-500">{o.text}</span>
                  </button>
                ))}
              </div>

              {deliveryMode === "auto" && (
                <p className="mt-3 rounded-xl bg-white px-3.5 py-2.5 text-xs leading-relaxed text-slate-600 ring-1 ring-slate-200">
                  🔗 Havolalarni saqlagandan so‘ng mahsulotlar ro‘yxatidagi <b>“Havolalar”</b> tugmasi orqali qo‘shasiz (har biri alohida
                  qatorda). Har xaridorga bittadan, takrorlanmasdan beriladi. Havola qolmasa, mahsulot “Tugagan” bo‘ladi.
                </p>
              )}

              <div className="mt-4">
                <Field label="Yetkazib berish vaqti" hint={deliveryMode === "auto" ? "Avtomatik mahsulotda saytda “Darhol” deb ko‘rsatiladi" : "Mahsulot sahifasida va xariddan keyin ko‘rsatiladi"}>
                  <input value={deliveryTime} onChange={(e) => setDeliveryTime(e.target.value)} maxLength={64} className={inputCls} />
                  <div className="mt-2 flex flex-wrap gap-2">
                    {DELIVERY_TIME_PRESETS.map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setDeliveryTime(t)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 transition ${
                          deliveryTime === t ? "bg-brand-soft text-brand ring-brand" : "bg-white text-slate-600 ring-slate-200 hover:ring-brand"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </Field>
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-3">
              <Field label="Kategoriya">
                <select value={category} onChange={(e) => setCategory(e.target.value as ProductCategory)} className={inputCls}>
                  {catalogCategories
                    .filter((c) => c.id !== "all")
                    .map((c) => (
                      <option key={c.id} value={c.id}>{c.label}</option>
                    ))}
                </select>
              </Field>
              <Field label="Belgi">
                <select value={badge} onChange={(e) => setBadge(e.target.value as ProductBadge | "")} className={inputCls}>
                  <option value="">Yo‘q</option>
                  {(Object.keys(badgeStyles) as ProductBadge[]).map((b) => (
                    <option key={b} value={b}>{badgeStyles[b].label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Tartib raqami" hint="Kichigi yuqorida">
                <input
                  type="number"
                  min={0}
                  max={10000}
                  value={sortOrder}
                  onChange={(e) => setSortOrder(Math.max(0, Math.min(10000, Math.trunc(Number(e.target.value) || 0))))}
                  className={inputCls}
                />
              </Field>
            </div>

            <Field label="Nimalar kiradi?" hint="Har bir imkoniyat alohida qatorda (servis sahifasida ro‘yxat bo‘lib chiqadi)">
              <textarea
                value={features}
                onChange={(e) => setFeatures(e.target.value)}
                rows={5}
                placeholder={"GPT-4o modeliga kirish\nDALL-E bilan rasm yaratish\n..."}
                className={`${inputCls} resize-y`}
              />
            </Field>

            <Field label="Muhim ma’lumot (qoidalar, kafolat)" hint="Servis sahifasida alohida blokda chiqadi. Har bir qoida alohida qatorda.">
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={4}
                maxLength={3000}
                placeholder={"📱 Faqat 1–2 qurilmada foydalaning\n🛡️ 30 kunlik kafolat"}
                className={`${inputCls} resize-y`}
              />
            </Field>

            <label className="flex cursor-pointer items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm">
              <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="size-4 accent-brand" />
              <span>
                <span className="font-semibold">Saytda ko‘rsatish</span>
                <span className="block text-xs text-slate-500">O‘chirilsa mahsulot katalogdan yashiriladi, lekin o‘chib ketmaydi</span>
              </span>
            </label>
          </div>

          {/* Jonli ko‘rinish */}
          <div className="lg:sticky lg:top-0 lg:self-start">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Saytda shunday ko‘rinadi</p>
            <div className={`rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200 ${soldOut ? "grayscale" : ""}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="size-16 shrink-0 text-sm">{preview.logo}</div>
                <div className="flex flex-col items-end gap-1.5">
                  {preview.badge && (
                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${badgeStyles[preview.badge].className}`}>
                      {badgeStyles[preview.badge].label}
                    </span>
                  )}
                  {discount > 0 && <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[11px] font-bold text-white">-{discount}%</span>}
                </div>
              </div>
              <p className="mt-3 font-bold">{preview.name}</p>
              <p className="mt-1 line-clamp-3 text-sm text-slate-500">{preview.description || "Tavsif..."}</p>
              <p className="mt-3 flex flex-wrap items-baseline gap-x-2">
                <span className="text-lg font-bold">{formatPrice(preview.price)} so‘m</span>
                {preview.old_price && <span className="text-xs text-slate-400 line-through">{formatPrice(preview.old_price)} so‘m</span>}
              </p>
              <p className="text-xs text-slate-400">/ {preview.durations[0]} {unitWord}</p>
              {previewStock && <p className={`mt-2 text-xs font-semibold ${soldOut ? "text-slate-500" : "text-emerald-600"}`}>{previewStock}</p>}
              <div className={`mt-3 rounded-xl py-2.5 text-center text-sm font-semibold text-white ${soldOut ? "bg-slate-400" : "bg-brand"}`}>
                {soldOut ? "Tugagan" : "Sotib olish"}
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-slate-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-end">
          {error && <p className="text-sm text-rose-600 sm:mr-auto">{error}</p>}
          <button type="button" onClick={onClose} disabled={busy} className="rounded-xl px-5 py-2.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50">
            Bekor qilish
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-xl bg-brand px-6 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition hover:bg-brand-dark disabled:opacity-60"
          >
            {busy ? "Saqlanmoqda..." : isNew ? "Mahsulotni qo‘shish" : "Saqlash"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, hint, required, children }: { label: string; hint?: string; required?: boolean; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 text-sm font-semibold">
        {label}
        {required && <span className="text-rose-500"> *</span>}
      </p>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

/** Narxni "200 000" ko‘rinishida yozish uchun maydon */
function PriceInput({ value, onChange, placeholder }: { value: number | null; onChange: (v: number | null) => void; placeholder: string }) {
  return (
    <input
      inputMode="numeric"
      value={value === null ? "" : formatPrice(value)}
      onChange={(e) => {
        const digits = e.target.value.replace(/\D/g, "").slice(0, 10);
        onChange(digits ? Math.min(Number(digits), 1_000_000_000) : null);
      }}
      placeholder={placeholder}
      className={inputCls}
    />
  );
}
