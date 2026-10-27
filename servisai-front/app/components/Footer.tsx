import { Brand } from "./Header";
import { Clock, Instagram, Mail, Send, Youtube } from "./icons";

const ADMIN_TELEGRAM = "https://t.me/Boss_uz";

const categories = ["AI Chatbotlar", "Dizayn & Video", "Kodlash & Dev", "Ofis & Ta’lim", "Boshqa servislar"];
const usefulLinks = [
  { href: "#", label: "Bosh sahifa" },
  { href: "#mahsulotlar", label: "Mahsulotlar" },
  { href: "#faq", label: "FAQ" },
  { href: "#aloqa", label: "Aloqa" },
  { href: "#", label: "Foydalanish shartlari" },
];

export default function Footer() {
  return (
    <footer id="aloqa" className="border-t border-slate-100 bg-white">
      <div className="mx-auto grid max-w-7xl grid-cols-2 gap-x-6 gap-y-10 px-4 py-12 sm:px-6 lg:grid-cols-4">
        <div className="col-span-2 sm:col-span-1">
          <Brand />
          <p className="mt-4 max-w-56 text-sm text-muted">Zamonaviy AI va premium servislar endi O‘zbekistonda.</p>
          <div className="mt-5 flex gap-3">
            {[
              { icon: <Send className="size-4" />, label: "Telegram", href: ADMIN_TELEGRAM },
              { icon: <Instagram className="size-4" />, label: "Instagram", href: "#" },
              { icon: <Youtube className="size-4" />, label: "YouTube", href: "#" },
            ].map((s) => (
              <a
                key={s.label}
                href={s.href}
                aria-label={s.label}
                className="grid size-9 place-items-center rounded-full bg-slate-100 text-slate-700 transition hover:bg-brand hover:text-white"
              >
                {s.icon}
              </a>
            ))}
          </div>
        </div>

        <div>
          <h4 className="font-semibold">Kategoriyalar</h4>
          <ul className="mt-4 space-y-2.5 text-sm text-muted">
            {categories.map((c) => (
              <li key={c}>
                <a href="#mahsulotlar" className="hover:text-brand">{c}</a>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="font-semibold">Foydali havolalar</h4>
          <ul className="mt-4 space-y-2.5 text-sm text-muted">
            {usefulLinks.map((l) => (
              <li key={l.label}>
                <a href={l.href} className="hover:text-brand">{l.label}</a>
              </li>
            ))}
          </ul>
        </div>

        <div className="col-span-2 sm:col-span-1">
          <h4 className="font-semibold">Aloqa</h4>
          <ul className="mt-4 space-y-3 text-sm text-muted">
            <li>
              <a href={ADMIN_TELEGRAM} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 hover:text-brand">
                <Send className="size-4 text-brand" /> Admin
              </a>
            </li>
            <li className="flex items-center gap-3"><Mail className="size-4 text-brand" /> info@servisai.uz</li>
            <li className="flex items-center gap-3"><Clock className="size-4 text-brand" /> Har kuni 24/7</li>
          </ul>
        </div>
      </div>
      <p className="border-t border-slate-100 py-5 text-center text-xs text-muted">
        © 2024 servisai.uz. Barcha huquqlar himoyalangan.
      </p>
    </footer>
  );
}
