import Image from "next/image";
import Link from "next/link";
import heroImage from "@/public/hero.png";
import SectionHeading from "./SectionHeading";
import { ArrowRight, Bolt, CartFilled, Headset, ShieldFilled, Send, Tag, Wallet } from "./icons";

export function PromoBanner() {
  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#0b1d6b] via-[#1238b8] to-[#4b2bd1] px-6 py-10 text-white shadow-2xl shadow-blue-900/20 sm:px-10">
        <Image
          src={heroImage}
          alt=""
          aria-hidden
          sizes="60vw"
          className="pointer-events-none absolute -right-10 top-1/2 hidden h-[160%] w-auto max-w-none -translate-y-1/2 opacity-40 mix-blend-screen md:block"
        />
        <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="max-w-md">
            <h2 className="text-2xl font-bold leading-tight sm:text-3xl">
              Barcha premium servislar endi bir joyda!
            </h2>
            <p className="mt-3 text-sm text-white/80">
              Sizga kerak bo‘lgan AI, dizayn, video, kodlash va boshqa servislarni oson va tez xarid qiling.
            </p>
          </div>
          <Link
            href="/mahsulotlar"
            className="inline-flex shrink-0 items-center gap-2 self-start rounded-xl bg-white px-6 py-3.5 text-sm font-semibold text-[#0b1437] transition hover:bg-blue-50 md:self-auto"
          >
            Barcha mahsulotlarni ko‘rish <ArrowRight className="size-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}

const steps = [
  { icon: <CartFilled className="size-7" />, title: "Kerakli servisni tanlang", text: "O‘zingizga kerak bo‘lgan servis va muddatni tanlang." },
  { icon: <Wallet className="size-7" />, title: "To‘lovni amalga oshiring", text: "Click, Payme, Uzcard, Humo orqali qulay to‘lov qiling." },
  { icon: <Send className="size-7" />, title: "Hisob ma’lumotini oling", text: "Servis hisobingiz tezda faollashtiriladi va ma’lumotlar sizga yuboriladi." },
];

export function HowItWorks() {
  return (
    <section id="qanday" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6">
      <SectionHeading badge="Qanday ishlaydi?" title="Xarid qilish juda oson" subtitle="Atigi 3 qadamda servisni faollashtiring" />
      <div className="mt-12 grid gap-10 md:grid-cols-[1fr_auto_1fr_auto_1fr] md:items-start">
        {steps.map((s, i) => (
          <div key={s.title} className="contents">
            <div className="flex flex-col items-center text-center md:items-start md:text-left">
              <div className="relative">
                <span className="absolute -left-3 -top-3 grid size-7 place-items-center rounded-full bg-brand text-xs font-bold text-white ring-4 ring-background">
                  {i + 1}
                </span>
                <div className="grid size-20 place-items-center rounded-full bg-brand-soft text-brand">{s.icon}</div>
              </div>
              <h3 className="mt-5 font-semibold">{s.title}</h3>
              <p className="mt-2 max-w-60 text-sm leading-relaxed text-muted">{s.text}</p>
            </div>
            {i < steps.length - 1 && (
              <ArrowRight className="mt-14 hidden size-7 text-brand md:block" />
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

const features = [
  { icon: <Bolt className="size-7" />, bg: "bg-orange-50 text-orange-500", title: "Tez faollashtirish", text: "To‘lovdan so‘ng bir necha daqiqada" },
  { icon: <ShieldFilled className="size-7" />, bg: "bg-emerald-50 text-emerald-500", title: "100% ishonchli", text: "Haqiqiy va rasmiy hisoblar" },
  { icon: <Tag className="size-7" />, bg: "bg-rose-50 text-rose-500", title: "Qulay narxlar", text: "Bozordagi eng yaxshi narxlar" },
  { icon: <Headset className="size-7" />, bg: "bg-blue-50 text-brand", title: "24/7 qo‘llab-quvvatlash", text: "Har doim siz bilan a’loqada" },
];

export function Features() {
  return (
    <section id="afzalliklar" className="mx-auto max-w-7xl scroll-mt-20 px-4 pb-20 sm:px-6">
      <SectionHeading badge="Nega bizni tanlashadi?" title="Bizning afzalliklarimiz" />
      <div className="mt-10 grid grid-cols-2 gap-3 sm:gap-5 lg:grid-cols-4">
        {features.map((f) => (
          <div key={f.title} className="flex flex-col items-center rounded-3xl bg-white p-4 text-center shadow-sm ring-1 ring-slate-100 sm:p-7">
            <div className={`grid size-12 place-items-center rounded-full sm:size-14 ${f.bg}`}>{f.icon}</div>
            <h3 className="mt-3 text-sm font-semibold sm:mt-4 sm:text-base">{f.title}</h3>
            <p className="mt-1 text-xs text-muted sm:text-sm">{f.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function CallToAction() {
  return (
    <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
      <div className="flex flex-col items-center justify-between gap-6 rounded-3xl bg-gradient-to-r from-[#e8efff] to-[#eef0ff] px-8 py-10 text-center md:flex-row md:text-left">
        <div className="md:pl-16">
          <h2 className="text-2xl font-bold">Kerakli servisni hoziroq xarid qiling!</h2>
          <p className="mt-1 text-muted">Zamonaviy imkoniyatlar sizni kutmoqda</p>
        </div>
        <Link
          href="/mahsulotlar"
          className="inline-flex items-center gap-2 rounded-xl bg-brand px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/30 transition hover:bg-brand-dark md:mr-16"
        >
          Mahsulotlarni ko‘rish <ArrowRight className="size-4" />
        </Link>
      </div>
    </section>
  );
}
