"use client";

import { useRef } from "react";
import { testimonials } from "./data";
import SectionHeading from "./SectionHeading";
import { ChevronLeft, ChevronRight, Star } from "./icons";

function Stars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }, (_, i) => {
        const fill = Math.min(Math.max(rating - i, 0), 1);
        return (
          <span key={i} className="relative size-4">
            <Star className="absolute inset-0 size-4 text-slate-200" />
            <span className="absolute inset-0 overflow-hidden" style={{ width: `${fill * 100}%` }}>
              <Star className="size-4 text-amber-400" />
            </span>
          </span>
        );
      })}
    </div>
  );
}

export default function Testimonials() {
  const track = useRef<HTMLDivElement>(null);

  const scroll = (dir: 1 | -1) => {
    const el = track.current;
    if (!el) return;
    el.scrollBy({ left: dir * (el.clientWidth / 3 + 8), behavior: "smooth" });
  };

  return (
    <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
      <SectionHeading badge="Foydalanuvchilar fikri" title="Mijozlarimiz biz haqimizda" />

      <div className="relative mt-10">
        <button
          aria-label="Oldingi"
          onClick={() => scroll(-1)}
          className="absolute -left-2 top-1/2 z-10 hidden size-10 -translate-y-1/2 place-items-center rounded-full bg-white shadow-md ring-1 ring-slate-100 hover:text-brand sm:grid"
        >
          <ChevronLeft className="size-5" />
        </button>

        <div
          ref={track}
          className="flex snap-x snap-mandatory gap-5 overflow-x-auto scroll-smooth px-1 pb-4 [scrollbar-width:none] sm:px-12 [&::-webkit-scrollbar]:hidden"
        >
          {testimonials.map((t) => (
            <figure
              key={t.name}
              className="w-[85%] shrink-0 snap-start rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-100 sm:w-[calc(50%-10px)] lg:w-[calc(33.333%-14px)]"
            >
              <div className="flex items-center gap-3">
                <span className={`grid size-11 place-items-center rounded-full text-lg font-semibold text-white ${t.color}`}>
                  {t.name[0]}
                </span>
                <div>
                  <figcaption className="font-semibold">{t.name}</figcaption>
                  <Stars rating={t.rating} />
                </div>
              </div>
              <blockquote className="mt-4 text-sm leading-relaxed text-muted">{t.text}</blockquote>
            </figure>
          ))}
        </div>

        <button
          aria-label="Keyingi"
          onClick={() => scroll(1)}
          className="absolute -right-2 top-1/2 z-10 hidden size-10 -translate-y-1/2 place-items-center rounded-full bg-white shadow-md ring-1 ring-slate-100 hover:text-brand sm:grid"
        >
          <ChevronRight className="size-5" />
        </button>
      </div>
    </section>
  );
}
