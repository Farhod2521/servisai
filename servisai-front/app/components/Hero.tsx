import Image from "next/image";
import heroImage from "@/public/hero.png";
import { ArrowRight, Bolt, Headset, Play, Shield } from "./icons";

export default function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-[#f7f9fd] via-[#e6eefd] to-[#eef6fd]">
      {/* Konteynerdan o‘ngdagi bo‘sh joy rasmning o‘ng cheti ranglari bilan to‘ldiriladi */}
      <div className="absolute inset-y-0 right-0 hidden w-1/2 bg-gradient-to-b from-[#5783fd] via-[#4675fd] via-45% to-[#d0e3fc] xl:block" />

      {/* Keng ekranda rasm konteyner eniga moslanadi (dizayndagidek), kichik ekranda xira fon */}
      <div className="absolute inset-y-0 left-1/2 w-full -translate-x-1/2 xl:max-w-7xl">
        <Image
          src={heroImage}
          alt="AI servislar: ChatGPT, Claude, Gemini, CapCut, Midjourney"
          fill
          preload
          sizes="(min-width: 1280px) 1280px, 100vw"
          className="object-cover object-[70%_center] opacity-40 xl:object-right xl:opacity-100 xl:[mask-image:linear-gradient(to_right,transparent,black_6%,black_94%,transparent)]"
        />
      </div>
      {/* Mobil uchun matn o‘qilishi oson bo‘lsin */}
      <div className="absolute inset-0 bg-gradient-to-r from-white/90 via-white/60 to-transparent xl:hidden" />
      {/* Qorong‘i rejimda matn rasm ustida o‘qilishi uchun */}
      <div className="absolute inset-0 hidden bg-gradient-to-r from-[#0b1020] via-[#0b1020]/85 via-45% to-transparent to-75% dark:block" />

      <div className="relative mx-auto flex min-h-[460px] max-w-7xl items-center px-4 py-16 sm:px-6 md:min-h-[520px] lg:min-h-[560px] xl:aspect-[1859/846] xl:min-h-0 xl:py-0">
        <div className="max-w-xl">
          <span className="inline-block rounded-full bg-white/80 px-4 py-1.5 text-xs font-semibold text-brand shadow-sm ring-1 ring-blue-100">
            Raqamli servislar bir joyda
          </span>

          <h1 className="mt-5 text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl lg:text-[56px]">
            Zamonaviy AI va Premium servislar endi{" "}
            <span className="text-brand">O‘zbekistonda</span>
          </h1>

          <p className="mt-5 max-w-md text-base leading-relaxed text-muted">
            ChatGPT, Claude, Gemini, CapCut, Midjourney va yana ko‘plab premium servislarni tez,
            ishonchli va arzon narxda xarid qiling.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#mahsulotlar"
              className="inline-flex items-center gap-2 rounded-xl bg-brand px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/30 transition hover:bg-brand-dark"
            >
              Mahsulotlarni ko‘rish <ArrowRight className="size-4" />
            </a>
            <a
              href="#qanday"
              className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3.5 text-sm font-semibold text-brand shadow-sm ring-1 ring-slate-200 transition hover:ring-brand"
            >
              <Play className="size-5" /> Qanday ishlaydi?
            </a>
          </div>

          <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-medium text-slate-700">
            <li className="flex items-center gap-2">
              <Bolt className="size-4 text-brand" /> Tez faollashtirish
            </li>
            <li className="flex items-center gap-2">
              <Shield className="size-4 text-brand" /> 100% ishonchli
            </li>
            <li className="flex items-center gap-2">
              <Headset className="size-4 text-brand" /> 24/7 qo‘llab-quvvatlash
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
