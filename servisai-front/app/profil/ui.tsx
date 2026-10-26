import Link from "next/link";
import type { ReactNode } from "react";

export function Card({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold">{title}</h2>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-200 px-6 py-10 text-center">
      <p className="text-sm text-slate-500">{text}</p>
      <Link href="/mahsulotlar" className="mt-4 inline-block rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-dark">
        Servislarni ko‘rish
      </Link>
    </div>
  );
}

export function ErrorText({ text }: { text: string }) {
  return <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-600">{text}</p>;
}
