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

export type CatalogCategory = "chat" | "design" | "code" | "office" | "social" | "other";
export type ProductType = "premium" | "api" | "individual" | "team";
export type Seller = "official" | "warranty" | "api" | "other";
export type Badge = "popular" | "sale" | "new" | "api";
export type Duration = 1 | 18;

export const catalogCategories: { id: CatalogCategory | "all"; label: string; icon: ReactNode }[] = [
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

export const badgeStyles: Record<Badge, { label: string; className: string }> = {
  popular: { label: "Eng ommabop", className: "bg-emerald-50 text-emerald-600" },
  sale: { label: "Chegirma", className: "bg-rose-50 text-rose-500" },
  new: { label: "Yangi", className: "bg-lime-50 text-lime-600" },
  api: { label: "API kredit", className: "bg-sky-50 text-sky-600" },
};

export type CatalogProduct = {
  id: string;
  name: string;
  description: string;
  category: CatalogCategory;
  type: ProductType;
  seller: Seller;
  durations: Duration[];
  price: number;
  oldPrice?: number;
  badge?: Badge;
  rating: number;
  reviews: number;
  sold: number;
  /** Ommaboplik bo‘yicha saralash uchun (kichik = yuqorida) */
  rank: number;
  /** Yangi qo‘shilganlar bo‘yicha saralash uchun (katta = yangi) */
  addedAt: number;
  /** Servis sahifasidagi "Nimalar kiradi" ro‘yxati */
  features: string[];
  logo: ReactNode;
};

/** 1234567 -> "1 234 567" (toLocaleString server/brauzerda turli bo‘shliq qaytarishi mumkin) */
export const formatPrice = (n: number) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
export const formatCount = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1).replace(/\.0$/, "")}K` : String(n));
export const discountPercent = (p: CatalogProduct) => (p.oldPrice ? Math.round((1 - p.price / p.oldPrice) * 100) : 0);

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
};

export const catalogProducts: CatalogProduct[] = [
  { id: "chatgpt-plus", name: "ChatGPT Plus", description: "GPT-4, DALL-E, Advanced Data Analysis va yana ko‘p imkoniyatlar", category: "chat", type: "individual", seller: "official", durations: [1], price: 200000, badge: "popular", rating: 4.9, reviews: 1200, sold: 12500, rank: 1, addedAt: 1, logo: logos.openai,
    features: [
      "GPT-4o va eng yangi OpenAI modellariga kirish",
      "DALL-E bilan rasm yaratish",
      "Advanced Data Analysis — fayl va jadvallarni tahlil qilish",
      "Custom GPT’lar yaratish va ishlatish",
      "Ovozli suhbat rejimi",
      "Bepul versiyaga nisbatan yuqori limitlar",
    ] },
  { id: "gemini-advanced", name: "Gemini Advanced", description: "Google’ning eng yangi AI modeli, 1.5 Pro, 2TB gacha imkoniyatlar", category: "chat", type: "individual", seller: "official", durations: [18], price: 35000, badge: "new", rating: 4.8, reviews: 760, sold: 6100, rank: 3, addedAt: 3, logo: logos.gemini,
    features: [
      "Gemini 1.5 Pro — Google’ning eng kuchli modeli",
      "1 million tokengacha kontekst",
      "2TB Google One bulutli xotirasi",
      "Gmail, Docs va Sheets ichida Gemini",
      "Uzun hujjat va kodlarni tahlil qilish",
      "18 oy davomida to‘liq imkoniyatlar",
    ] },
  { id: "capcut-pro", name: "CapCut Pro", description: "Premium shablonlar, AI video, tafsirlar, barcha funksiyalar", category: "design", type: "individual", seller: "warranty", durations: [1], price: 40000, badge: "popular", rating: 4.7, reviews: 650, sold: 9300, rank: 2, addedAt: 2, logo: logos.capcut,
    features: [
      "Barcha Pro shablon va effektlar",
      "AI video tahrirlash vositalari",
      "Suv belgisisiz eksport",
      "4K sifatda eksport",
      "Avtomatik subtitrlar",
      "Bulutli xotira",
    ] },
];

export const getProduct = (id: string) => catalogProducts.find((p) => p.id === id);

/** Banner uchun suzib turuvchi logolar */
export const bannerLogos = [
  logos.openai,
  // Alohida gradient id: banner mobil ekranda yashiriladi, kartochkadagi logo unga bog‘lanib qolmasin
  <div key="gemini" className={`${tile} bg-white ring-1 ring-slate-100`}>
    <GeminiLogo gradientId="gem-banner" className="size-3/5" />
  </div>,
  logos.capcut,
];
