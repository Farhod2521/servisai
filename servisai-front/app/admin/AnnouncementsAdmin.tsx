"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { AnnouncementCard } from "../components/AnnouncementPopup";
import { Close, Megaphone, Pencil, Plus, Trash } from "../components/icons";
import { api, formatDate, type Announcement, type Reward } from "../lib/api";
import { ErrorText } from "../profil/ui";

export default function AnnouncementsAdmin() {
  const [items, setItems] = useState<Announcement[] | null>(null);
  const [reward, setReward] = useState<Reward | null>(null);
  const [editing, setEditing] = useState<Announcement | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api<Announcement[]>("/admin/announcements"), api<Reward[]>("/admin/rewards")])
      .then(([a, r]) => {
        setItems(a);
        setReward(r.find((x) => x.is_active) ?? null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const toggle = async (a: Announcement) => {
    try {
      await api(`/admin/announcements/${a.id}`, { method: "PATCH", json: { ...bodyOf(a), is_active: !a.is_active } });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (a: Announcement) => {
    if (!confirm(`“${a.title}” e’loni o‘chirilsinmi?`)) return;
    try {
      await api(`/admin/announcements/${a.id}`, { method: "DELETE" });
      setItems((list) => list?.filter((x) => x.id !== a.id) ?? null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const previewReward = reward ? { required_friends: reward.required_friends, product_name: reward.product_name } : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Yangiliklar</h1>
          <p className="text-sm text-slate-500">Saytga kirganda chiqadigan e’lon oynalari</p>
        </div>
        <button
          onClick={() => setEditing("new")}
          className="flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 hover:bg-brand-dark"
        >
          <Plus className="size-4" /> E’lon qo‘shish
        </button>
      </div>

      <div className="rounded-2xl bg-sky-50 px-5 py-4 text-sm leading-relaxed text-sky-900 ring-1 ring-sky-100">
        <b>Qanday ishlaydi:</b> bir vaqtda faqat <b>bitta</b> e’lon faol bo‘ladi — qaysi birini yoqsangiz, saytga kirganlarga o‘sha chiqadi
        (qolganlari o‘zi o‘chadi). Foydalanuvchi «Keyinroq» bossa, 3 kun ko‘rsatilmaydi; e’lonni tahrirlasangiz — hammaga yana chiqadi.
        «Do‘st taklif qiling» turida matndagi <b>{"{n}"}</b> — do‘stlar soni, <b>{"{product}"}</b> — sovg‘a nomi bilan almashadi (Sovg‘alar
        bo‘limidagi faol sovg‘adan).
      </div>

      {error && <ErrorText text={error} />}

      {!items ? (
        <div className="h-32 animate-pulse rounded-3xl bg-white" />
      ) : items.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-500">
          Hali e’lon yo‘q. Masalan: <b>Yangi mahsulot — Claude Pro!</b>
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {items.map((a) => (
            <li key={a.id} className={`rounded-3xl bg-white p-5 shadow-sm ring-1 ${a.is_active ? "ring-emerald-200" : "ring-slate-100"}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  {a.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- admin yuklagan rasm
                    <img src={a.image_url} alt="" className="size-12 shrink-0 rounded-2xl object-cover" />
                  ) : (
                    <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-sky-500 to-brand text-white shadow-md shadow-sky-500/25">
                      <Megaphone className="size-6" />
                    </span>
                  )}
                  <div className="min-w-0">
                    <p className="truncate font-bold">
                      {fillPreview(a.title, previewReward)} {a.highlight && <span className="text-brand">{fillPreview(a.highlight, previewReward)}</span>}
                    </p>
                    <p className="text-xs text-slate-500">
                      {a.kind === "referral" ? "Do‘st taklif qiling" : "Oddiy e’lon"} · {formatDate(a.updated_at)}
                    </p>
                  </div>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                    a.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {a.is_active ? "Saytda chiqmoqda" : "O‘chirilgan"}
                </span>
              </div>
              {(a.subtitle || a.text) && (
                <p className="mt-3 line-clamp-2 text-sm text-slate-500">{fillPreview(a.subtitle || a.text, previewReward)}</p>
              )}
              {a.kind === "referral" && !reward && (
                <p className="mt-2 text-xs text-amber-600">⚠️ Faol sovg‘a yo‘q — bu e’lon saytda chiqmaydi (Sovg‘alar bo‘limida sovg‘ani yoqing).</p>
              )}
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => toggle(a)}
                  className={`flex-1 rounded-xl py-2 text-sm font-semibold ${
                    a.is_active ? "ring-1 ring-slate-200 hover:ring-brand" : "bg-brand text-white hover:bg-brand-dark"
                  }`}
                >
                  {a.is_active ? "O‘chirish" : "Faol qilish"}
                </button>
                <button
                  aria-label="Tahrirlash"
                  onClick={() => setEditing(a)}
                  className="grid size-10 place-items-center rounded-xl text-slate-600 ring-1 ring-slate-200 hover:text-brand hover:ring-brand"
                >
                  <Pencil className="size-4.5" />
                </button>
                <button
                  aria-label="O‘chirib tashlash"
                  onClick={() => remove(a)}
                  className="grid size-10 place-items-center rounded-xl text-rose-500 ring-1 ring-slate-200 hover:bg-rose-50 hover:ring-rose-200"
                >
                  <Trash className="size-4.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <AnnouncementForm
          item={editing === "new" ? null : editing}
          reward={previewReward}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

const bodyOf = (a: Announcement) => ({
  kind: a.kind,
  title: a.title,
  highlight: a.highlight,
  subtitle: a.subtitle,
  text: a.text,
  button_text: a.button_text,
  button_url: a.button_url,
  is_active: a.is_active,
});

const fillPreview = (text: string, reward: { required_friends: number; product_name: string } | null) =>
  reward ? text.replaceAll("{n}", String(reward.required_friends)).replaceAll("{product}", reward.product_name) : text;

const inputCls =
  "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10";

function AnnouncementForm({
  item,
  reward,
  onClose,
  onSaved,
}: {
  item: Announcement | null;
  reward: { required_friends: number; product_name: string } | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState(() =>
    item ? bodyOf(item) : { kind: "custom" as Announcement["kind"], title: "", highlight: "", subtitle: "", text: "", button_text: "", button_url: "", is_active: true },
  );
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));

  // Rasm: yangi tanlangan fayl yoki mavjudini olib tashlash (saqlanganda bajariladi)
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [removeImage, setRemoveImage] = useState(false);
  const imageInput = useRef<HTMLInputElement>(null);
  const imagePreview = useMemo(() => (imageFile ? URL.createObjectURL(imageFile) : null), [imageFile]);
  useEffect(() => () => void (imagePreview && URL.revokeObjectURL(imagePreview)), [imagePreview]);
  const currentImage = imagePreview ?? (removeImage ? null : (item?.image_url ?? null));

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const pickImage = (file: File | undefined) => {
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) return setError("Rasm hajmi 2 MB dan oshmasligi kerak");
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) return setError("Rasm PNG, JPG yoki WEBP bo‘lishi kerak");
    setError(null);
    setImageFile(file);
    setRemoveImage(false);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return setError("Sarlavhani kiriting");
    const url = form.button_url.trim();
    if (form.kind === "custom" && url && !/^(\/\S*|https?:\/\/\S+)$/.test(url))
      return setError("Havola “/mahsulotlar” yoki “https://...” ko‘rinishida bo‘lsin");
    setBusy(true);
    setError(null);
    try {
      let saved = await api<Announcement>(item ? `/admin/announcements/${item.id}` : "/admin/announcements", {
        method: item ? "PATCH" : "POST",
        json: { ...form, button_url: form.kind === "referral" ? "" : url },
      });
      if (imageFile) {
        const body = new FormData();
        body.append("file", imageFile);
        saved = await api<Announcement>(`/admin/announcements/${saved.id}/image`, { method: "POST", body });
      } else if (removeImage && saved.image_url) {
        await api(`/admin/announcements/${saved.id}/image`, { method: "DELETE" });
      }
      onSaved();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const referral = form.kind === "referral";

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:p-8" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="mx-auto grid w-full max-w-6xl grid-cols-1 gap-6 xl:grid-cols-[minmax(0,480px)_minmax(0,1fr)] xl:items-start">
        <form onSubmit={submit} className="w-full rounded-3xl bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
            <h2 className="text-lg font-bold">{item ? "E’lonni tahrirlash" : "Yangi e’lon"}</h2>
            <button type="button" aria-label="Yopish" onClick={onClose} className="grid size-9 place-items-center rounded-lg hover:bg-slate-100">
              <Close className="size-5" />
            </button>
          </div>
          <div className="space-y-4 p-6">
            <div className="grid grid-cols-2 gap-2 rounded-2xl bg-slate-50 p-1.5 text-sm font-semibold">
              {(
                [
                  ["custom", "Oddiy e’lon"],
                  ["referral", "Do‘st taklif qiling"],
                ] as const
              ).map(([kind, label]) => (
                <button
                  key={kind}
                  type="button"
                  onClick={() => set("kind", kind)}
                  className={`rounded-xl py-2 transition ${form.kind === kind ? "bg-white text-brand shadow-sm ring-1 ring-slate-100" : "text-slate-500 hover:text-slate-800"}`}
                >
                  {label}
                </button>
              ))}
            </div>
            {referral && (
              <p className="rounded-xl bg-violet-50 px-3.5 py-2.5 text-xs leading-relaxed text-violet-900">
                Progress (necha do‘st taklif qilgani) va «Taklif havolasini olish» tugmasi avtomatik qo‘shiladi. Matnda <b>{"{n}"}</b> va{" "}
                <b>{"{product}"}</b> ishlating.
              </p>
            )}
            <label className="block">
              <span className="text-sm font-semibold">Sarlavha</span>
              <input value={form.title} onChange={(e) => set("title", e.target.value)} maxLength={255} placeholder="Yangi mahsulot" className={`mt-1.5 ${inputCls}`} />
            </label>
            <label className="block">
              <span className="text-sm font-semibold">Sarlavha davomi (ko‘k rangda)</span>
              <input value={form.highlight} onChange={(e) => set("highlight", e.target.value)} maxLength={255} placeholder="Claude Pro sotuvda!" className={`mt-1.5 ${inputCls}`} />
            </label>
            <label className="block">
              <span className="text-sm font-semibold">Qisqa tavsif</span>
              <input value={form.subtitle} onChange={(e) => set("subtitle", e.target.value)} maxLength={255} placeholder="Faqat shu hafta — 20% chegirma" className={`mt-1.5 ${inputCls}`} />
            </label>
            <label className="block">
              <span className="text-sm font-semibold">Matn</span>
              <textarea value={form.text} onChange={(e) => set("text", e.target.value)} maxLength={2000} rows={3} className={`mt-1.5 resize-y ${inputCls}`} />
            </label>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-semibold">Tugma matni</span>
                <input
                  value={form.button_text}
                  onChange={(e) => set("button_text", e.target.value)}
                  maxLength={64}
                  placeholder={referral ? "Taklif havolasini olish" : "Batafsil"}
                  className={`mt-1.5 ${inputCls}`}
                />
              </label>
              {!referral && (
                <label className="block">
                  <span className="text-sm font-semibold">Tugma havolasi</span>
                  <input value={form.button_url} onChange={(e) => set("button_url", e.target.value)} maxLength={512} placeholder="/mahsulotlar" className={`mt-1.5 ${inputCls}`} />
                </label>
              )}
            </div>
            <div>
              <span className="text-sm font-semibold">Rasm (o‘ng tomonda)</span>
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                {currentImage && (
                  // eslint-disable-next-line @next/next/no-img-element -- oldindan ko‘rish
                  <img src={currentImage} alt="" className="size-14 rounded-xl object-cover ring-1 ring-slate-100" />
                )}
                <button type="button" onClick={() => imageInput.current?.click()} className="rounded-xl px-4 py-2 text-sm font-semibold ring-1 ring-slate-200 hover:ring-brand">
                  {currentImage ? "Boshqa rasm" : "Rasm yuklash"}
                </button>
                {currentImage && (
                  <button
                    type="button"
                    onClick={() => {
                      setImageFile(null);
                      setRemoveImage(true);
                      if (imageInput.current) imageInput.current.value = "";
                    }}
                    className="rounded-xl px-4 py-2 text-sm font-semibold text-rose-600 ring-1 ring-slate-200 hover:bg-rose-50"
                  >
                    Olib tashlash
                  </button>
                )}
                <input ref={imageInput} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => pickImage(e.target.files?.[0])} />
              </div>
              <span className="mt-1 block text-xs text-slate-500">PNG, JPG yoki WEBP, 2 MB gacha. Yuklanmasa — chiroyli bezak chiqadi.</span>
            </div>
            <label className="flex cursor-pointer items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm">
              <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} className="size-4 accent-brand" />
              <span className="font-semibold">Faol — saytda shu e’lon chiqsin (boshqasi o‘chadi)</span>
            </label>
            {error && <ErrorText text={error} />}
          </div>
          <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4">
            <button type="button" onClick={onClose} className="rounded-xl px-5 py-2.5 text-sm font-semibold ring-1 ring-slate-200">
              Bekor qilish
            </button>
            <button disabled={busy} className="rounded-xl bg-brand px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-60">
              {busy ? "Saqlanmoqda..." : "Saqlash"}
            </button>
          </div>
        </form>

        {/* Saytda qanday ko‘rinishi */}
        <div className="pointer-events-none">
          <p className="mb-3 text-center text-sm font-semibold text-white">Saytda shunday ko‘rinadi</p>
          <AnnouncementCard
            item={{ ...form, title: form.title || "Sarlavha", image_url: currentImage }}
            reward={referral ? (reward ?? { required_friends: 10, product_name: "Sovg‘a" }) : null}
            friends={referral ? 3 : 0}
          />
        </div>
      </div>
    </div>
  );
}
