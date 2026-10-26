import type { ReactNode } from "react";
import {
  Bot,
  Cap,
  CapCutLogo,
  Code,
  Dots,
  GeminiLogo,
  Grid,
  OpenAILogo,
  Video,
} from "./icons";

export type CategoryId = "all" | "chat" | "design" | "code" | "office" | "other";

export const categories: { id: CategoryId; label: string; icon: ReactNode }[] = [
  { id: "all", label: "Barcha servislar", icon: <Grid className="size-6" /> },
  { id: "chat", label: "AI Chatbotlar", icon: <Bot className="size-6" /> },
  { id: "design", label: "Dizayn & Video", icon: <Video className="size-6" /> },
  { id: "code", label: "Kodlash & Dev", icon: <Code className="size-6" /> },
  { id: "office", label: "Ofis & Ta’lim", icon: <Cap className="size-6" /> },
  { id: "other", label: "Boshqa", icon: <Dots className="size-6" /> },
];

export type Product = {
  /** /mahsulotlar/[id] sahifasi uchun */
  id: string;
  name: string;
  description: string;
  price: string;
  duration: string;
  categories: CategoryId[];
  logo: ReactNode;
};

export const products: Product[] = [
  {
    id: "chatgpt-plus",
    name: "ChatGPT Plus",
    description: "GPT-4, DALL-E, Advanced Data Analysis va yana ko‘p imkoniyatlar",
    price: "129 000",
    duration: "1 oy",
    categories: ["chat", "code", "office"],
    logo: (
      <div className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-[#19c39c] to-[#0f9c7c] text-white shadow-lg shadow-emerald-500/30">
        <OpenAILogo className="size-10" />
      </div>
    ),
  },
  {
    id: "gemini-advanced",
    name: "Gemini Advanced",
    description: "Google’ning eng yangi AI modeli, 1.5 Pro, 2TB gacha imkoniyatlar",
    price: "129 000",
    duration: "18 oy",
    categories: ["chat", "office"],
    logo: (
      <div className="grid size-16 place-items-center rounded-2xl bg-white shadow-lg shadow-indigo-500/20 ring-1 ring-slate-100">
        <GeminiLogo className="size-10" />
      </div>
    ),
  },
  {
    id: "capcut-pro",
    name: "CapCut Pro",
    description: "Premium shablonlar, AI video, futajlar, barchasiga kirish",
    price: "69 000",
    duration: "1 oy",
    categories: ["design"],
    logo: (
      <div className="grid size-16 place-items-center rounded-2xl bg-white text-black shadow-lg shadow-slate-400/20 ring-1 ring-slate-100">
        <CapCutLogo className="size-9" />
      </div>
    ),
  },
];

export const testimonials = [
  { name: "Azizbek", text: "ChatGPT Plusni oldim, hammasi zo‘r ishladi. Tez va ishonchli servis!", color: "bg-violet-500", rating: 4.5 },
  { name: "Dilnoza", text: "Claude Pro juda yaxshi, kod yozishda katta yordam beradi. Rahmat!", color: "bg-pink-500", rating: 4.5 },
  { name: "Sardor", text: "CapCut Pro aktivatsiyasi juda tez bo‘ldi. Tavsiya qilaman!", color: "bg-emerald-500", rating: 5 },
  { name: "Malika", text: "Midjourney obunasini bir necha daqiqada faollashtirishdi. Ajoyib!", color: "bg-amber-500", rating: 5 },
  { name: "Jasur", text: "Gemini Advanced narxi bozordagidan arzon. Qo‘llab-quvvatlash ham zo‘r.", color: "bg-sky-500", rating: 4.5 },
];

export const faqs = [
  {
    q: "To‘lovdan keyin qanchada faollashtiriladi?",
    a: "Odatda to‘lov tasdiqlangandan so‘ng 5–15 daqiqa ichida servis faollashtiriladi va ma’lumotlar sizga yuboriladi.",
  },
  {
    q: "Hisoblar rasmiymi?",
    a: "Ha, barcha obunalar rasmiy yo‘l bilan to‘lanadi va to‘liq imkoniyatlarga ega bo‘ladi.",
  },
  {
    q: "Qanday to‘lov usullari mavjud?",
    a: "Click, Payme, Uzcard va Humo orqali qulay to‘lov qilishingiz mumkin.",
  },
  {
    q: "Agar muammo bo‘lsa nima qilish kerak?",
    a: "Telegram orqali 24/7 qo‘llab-quvvatlash xizmatimizga yozing — muammoni tezda hal qilamiz.",
  },
];
