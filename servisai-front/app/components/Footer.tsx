import { Brand } from "./Header";
import { Clock, Instagram, Mail, Phone, Send, Youtube } from "./icons";

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
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:grid-cols-2 sm:px-6 lg:grid-cols-4">
        <div>
          <Brand />
          <p className="mt-4 max-w-56 text-sm text-muted">Zamonaviy AI va premium servislar endi O‘zbekistonda.</p>
          <div className="mt-5 flex gap-3">
            {[
              { icon: <Send className="size-4" />, label: "Telegram", href: "https://t.me/servisaiuz" },
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

        <div>
          <h4 className="font-semibold">Aloqa</h4>
          <ul className="mt-4 space-y-3 text-sm text-muted">
            <li className="flex items-center gap-3"><Send className="size-4 text-brand" /> @servisaiuz</li>
            <li className="flex items-center gap-3"><Mail className="size-4 text-brand" /> info@servisai.uz</li>
            <li className="flex items-center gap-3"><Phone className="size-4 text-brand" /> +998 90 123 45 67</li>
            <li className="flex items-center gap-3"><Clock className="size-4 text-brand" /> Har kuni 09:00 – 23:00</li>
          </ul>
        </div>
      </div>
      <p className="border-t border-slate-100 py-5 text-center text-xs text-muted">
        © 2024 servisai.uz. Barcha huquqlar himoyalangan.
      </p>
    </footer>
  );
}
