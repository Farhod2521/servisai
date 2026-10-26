import { faqs } from "./data";
import SectionHeading from "./SectionHeading";
import { ChevronDown } from "./icons";

export default function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-6xl scroll-mt-20 px-4 pb-20 sm:px-6">
      <SectionHeading badge="Ko‘p so‘raladigan savollar" title="Tez-tez so‘raladigan savollar" />
      <div className="mt-10 grid items-start gap-4 md:grid-cols-2">
        {faqs.map((f) => (
          <details
            key={f.q}
            className="group rounded-2xl bg-white shadow-sm ring-1 ring-slate-100 open:ring-brand/30"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-4 text-sm font-semibold [&::-webkit-details-marker]:hidden">
              {f.q}
              <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" />
            </summary>
            <p className="px-6 pb-5 text-sm leading-relaxed text-muted">{f.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
