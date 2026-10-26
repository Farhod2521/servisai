"use client";

import Link from "next/link";
import { useState } from "react";
import { categories, products, type CategoryId } from "./data";
import SectionHeading from "./SectionHeading";

export default function Products() {
  const [active, setActive] = useState<CategoryId>("all");
  const visible = active === "all" ? products : products.filter((p) => p.categories.includes(active));

  return (
    <section id="mahsulotlar" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-12 sm:px-6">
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6 sm:gap-4">
        {categories.map((c) => {
          const isActive = c.id === active;
          return (
            <button
              key={c.id}
              onClick={() => setActive(c.id)}
              className={`flex flex-col items-center gap-2 rounded-2xl px-2 py-4 text-xs font-medium transition sm:text-sm ${
                isActive
                  ? "bg-brand text-white shadow-lg shadow-blue-600/30"
                  : "bg-white text-slate-700 shadow-sm ring-1 ring-slate-100 hover:-translate-y-0.5 hover:text-brand hover:shadow-md"
              }`}
            >
              <span className={isActive ? "text-white" : "text-brand"}>{c.icon}</span>
              {c.label}
            </button>
          );
        })}
      </div>

      <div className="mt-16">
        <SectionHeading
          badge="Mashhur mahsulotlar"
          title="Eng ommabop servislar"
          subtitle="Minglab foydalanuvchilar tanlagan xizmatlar"
        />
      </div>

      <div className="mx-auto mt-10 grid max-w-4xl grid-cols-1 gap-5 sm:grid-cols-3">
        {visible.map((p) => (
          <article
            key={p.name}
            className="flex flex-col items-center rounded-3xl bg-white p-6 text-center shadow-sm ring-1 ring-slate-100 transition hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-900/5"
          >
            {p.logo}
            <h3 className="mt-5 font-semibold">{p.name}</h3>
            <p className="mt-2 flex-1 text-xs leading-relaxed text-muted">{p.description}</p>
            <p className="mt-5 text-xl font-bold">
              {p.price} <span className="text-sm font-semibold">so‘m</span>
            </p>
            <p className="text-xs text-muted">/ {p.duration}</p>
            <Link
              href={`/mahsulotlar/${p.id}`}
              className="mt-5 w-full rounded-xl bg-brand py-3 text-sm font-semibold text-white transition hover:bg-brand-dark"
            >
              Sotib olish
            </Link>
          </article>
        ))}
        {visible.length === 0 && (
          <p className="col-span-full py-10 text-center text-muted">Bu kategoriyada hozircha servislar yo‘q.</p>
        )}
      </div>
    </section>
  );
}
