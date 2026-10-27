import type { ReactNode } from "react";
import {
  Bot,
  Box,
  Cap,
  CapCutLogo,
  Code,
  GeminiLogo,
  Grid,
  OpenAILogo,
  Users,
  Video,
} from "../components/icons";
import type { Product, ProductBadge, ProductCategory } from "../lib/api";

// Mahsulotning o‘zi (nom, narx, tavsif...) backenddan keladi va admin paneldan tahrirlanadi.
// Bu faylda faqat ko‘rinishga oid narsalar: kategoriya/belgi nomlari, logolar.

export type ProductType = "premium" | "api" | "individual" | "team";
export type Seller = "official" | "warranty" | "api" | "other";

export const catalogCategories: { id: ProductCategory | "all"; label: string; icon: ReactNode }[] = [
  { id: "all", label: "Barchasi", icon: <Grid className="size-4" /> },
  { id: "chat", label: "AI Chatbotlar", icon: <Bot className="size-4" /> },
  { id: "design", label: "Dizayn & Video", icon: <Video className="size-4" /> },
  { id: "code", label: "Kodlash & Dev", icon: <Code className="size-4" /> },
  { id: "office", label: "Ofis & Ta’lim", icon: <Cap className="size-4" /> },
  { id: "social", label: "Ijtimoiy tarmoqlar", icon: <Users className="size-4" /> },
  { id: "other", label: "Boshqa servislar", icon: <Box className="size-4" /> },
];

export const productTypes: { id: ProductType; label: string; short: string }[] = [
  { id: "premium", label: "Obuna (Premium)", short: "Premium" },
  { id: "api", label: "API kredit", short: "API" },
  { id: "individual", label: "Individual hisob", short: "Individual" },
  { id: "team", label: "Jamoa/Team", short: "Team" },
];

export const sellers: { id: Seller; label: string; short: string }[] = [
  { id: "official", label: "Rasmiy (Official)", short: "Rasmiy" },
  { id: "warranty", label: "Kafolatli hisob", short: "Kafolatli" },
  { id: "api", label: "API kredit", short: "API" },
  { id: "other", label: "Boshqa", short: "Boshqa" },
];

export const badgeStyles: Record<ProductBadge, { label: string; className: string }> = {
  popular: { label: "Eng ommabop", className: "bg-emerald-50 text-emerald-600" },
  sale: { label: "Chegirma", className: "bg-rose-50 text-rose-500" },
  new: { label: "Yangi", className: "bg-lime-50 text-lime-600" },
  api: { label: "API kredit", className: "bg-sky-50 text-sky-600" },
};

/** API mahsuloti + kartochkada ko‘rsatiladigan qo‘shimcha ma’lumotlar */
export type CatalogProduct = Product & {
  logo: ReactNode;
  // Faqat ma’lumoti bor servislar uchun ko‘rsatiladi
  rating?: number;
  type?: ProductType;
  seller?: Seller;
};

/** 3, "day" -> "3 kun"; 1, "month" -> "1 oy" */
export const durationText = (n: number, unit: string) => `${n} ${unit === "day" ? "kun" : "oy"}`;
/** 1, "month" -> "1 oylik"; 1, "day" -> "1 kunlik" */
export const periodText = (n: number, unit: string) => `${n} ${unit === "day" ? "kunlik" : "oylik"}`;

/** 1234567 -> "1 234 567" (toLocaleString server/brauzerda turli bo‘shliq qaytarishi mumkin) */
export const formatPrice = (n: number) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
export const formatCount = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1).replace(/\.0$/, "")}K` : String(n));
/** Admin soni 0 qilib qo‘ygan mahsulot: saytda oq-qora, sotib bo‘lmaydi */
export const isSoldOut = (p: Pick<Product, "stock">) => p.stock === 0;

/** "Qoldi: 5 ta" kabi yozuv; cheklanmagan mahsulot uchun null */
export const stockLabel = (p: Pick<Product, "stock">) =>
  p.stock === null ? null : p.stock === 0 ? "Tugagan" : `Qoldi: ${p.stock} ta`;

export const discountPercent = (p: Pick<Product, "price" | "old_price">) =>
  p.old_price ? Math.round((1 - p.price / p.old_price) * 100) : 0;

/* ---------- Logolar ---------- */

const tile = "grid size-full place-items-center rounded-2xl";

const logos = {
  openai: (
    <div className={`${tile} bg-gradient-to-br from-[#19c39c] to-[#0f9c7c] text-white`}>
      <OpenAILogo className="size-3/5" />
    </div>
  ),
  gemini: (
    <div className={`${tile} bg-white ring-1 ring-slate-100`}>
      <GeminiLogo gradientId="gem-catalog" className="size-3/5" />
    </div>
  ),
  capcut: (
    <div className={`${tile} bg-white text-black ring-1 ring-slate-100`}>
      <CapCutLogo className="size-3/5" />
    </div>
  ),
  // Claude: to‘q sariq fonda oq "quyosh"
  claude: (
    <div className={`${tile} bg-[#d97757]`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.1} strokeLinecap="round" className="size-3/5" aria-hidden="true">
        {Array.from({ length: 12 }, (_, i) => (
          <line key={i} x1="12" y1="12" x2="12" y2={i % 2 ? 3.6 : 1.8} transform={`rotate(${i * 30} 12 12)`} />
        ))}
      </svg>
    </div>
  ),
  // Codex: och binafsha fonda terminal belgisi va yozuv
  codex: (
    <div className="flex size-full flex-col items-center justify-center gap-[6%] rounded-2xl bg-gradient-to-br from-[#f1f2ff] to-[#dfe3ff] ring-1 ring-indigo-100">
      <span className="grid size-[38%] place-items-center rounded-[30%] bg-gradient-to-br from-[#7b8cff] to-[#4f46e5] font-mono text-[0.7em] font-bold leading-none text-white shadow-sm">
        &gt;_
      </span>
      <span className="text-[0.85em] font-semibold leading-none tracking-tight text-[#0b1437]">Codex</span>
    </div>
  ),
};

const fallbackColors = [
  "from-[#4f7cff] to-[#1557ff]",
  "from-[#a855f7] to-[#6d28d9]",
  "from-[#f97316] to-[#ea580c]",
  "from-[#10b981] to-[#047857]",
  "from-[#ec4899] to-[#be185d]",
  "from-[#0ea5e9] to-[#0369a1]",
];

/** Logosi tayyorlanmagan (admin qo‘shgan) mahsulot uchun: nomning bosh harfi, rang id’dan */
export function FallbackLogo({ id, name }: { id: string; name: string }) {
  const hash = [...id].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 0);
  return (
    <div className={`${tile} bg-gradient-to-br text-white ${fallbackColors[hash % fallbackColors.length]}`}>
      <span className="text-[2.2em] font-extrabold leading-none">{(name.trim()[0] ?? "?").toUpperCase()}</span>
    </div>
  );
}

type Extras = Omit<CatalogProduct, keyof Product>;

const extras: Record<string, Extras> = {
  "chatgpt-plus": { logo: logos.openai, rating: 4.9, type: "individual", seller: "official" },
  "gemini-advanced": { logo: logos.gemini, rating: 4.8, type: "individual", seller: "official" },
  "capcut-pro": { logo: logos.capcut, rating: 4.7, type: "individual", seller: "warranty" },
  "claude-api-10m": { logo: logos.claude, type: "api", seller: "api" },
  "claude-api-50m": { logo: logos.claude, type: "api", seller: "api" },
  "claude-api-100m": { logo: logos.claude, type: "api", seller: "api" },
  "codex-api-10m": { logo: logos.codex, type: "api", seller: "api" },
  "codex-api-20m": { logo: logos.codex, type: "api", seller: "api" },
  "codex-api-50m": { logo: logos.codex, type: "api", seller: "api" },
};

/** Build vaqtida oldindan tayyorlanadigan servis sahifalari */
export const knownProductIds = Object.keys(extras);

/** Admin yuklagan logo (rasm kvadratga sig‘diriladi) */
function UploadedLogo({ src, name }: { src: string; name: string }) {
  return (
    <div className={`${tile} overflow-hidden bg-white ring-1 ring-slate-100`}>
      {/* eslint-disable-next-line @next/next/no-img-element -- admin yuklagan rasm, o‘lchami kichik */}
      <img src={src} alt={name} className="size-full object-cover" />
    </div>
  );
}

export function toCatalogProduct(p: Product): CatalogProduct {
  const base = { ...p, ...(extras[p.id] ?? { logo: <FallbackLogo id={p.id} name={p.name} /> }) };
  // Yuklangan logo bo‘lsa — u ustun; aks holda chizilgan yoki harfli standart logo
  return p.logo_url ? { ...base, logo: <UploadedLogo src={p.logo_url} name={p.name} /> } : base;
}

/** Banner uchun suzib turuvchi logolar */
export const bannerLogos = [
  logos.openai,
  // Alohida gradient id: banner mobil ekranda yashiriladi, kartochkadagi logo unga bog‘lanib qolmasin
  <div key="gemini" className={`${tile} bg-white ring-1 ring-slate-100`}>
    <GeminiLogo gradientId="gem-banner" className="size-3/5" />
  </div>,
  logos.capcut,
];
