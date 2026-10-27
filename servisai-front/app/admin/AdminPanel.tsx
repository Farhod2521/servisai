"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../components/auth/AuthProvider";
import { Box, Chart, Gift, Lightbulb, Receipt, Shield, Users } from "../components/icons";
import Dashboard from "./Dashboard";
import ProductsAdmin from "./ProductsAdmin";
import OrdersAdmin from "./OrdersAdmin";
import RewardsAdmin from "./RewardsAdmin";
import SuggestionsAdmin from "./SuggestionsAdmin";
import UsersAdmin from "./UsersAdmin";

const tabs = [
  { id: "dashboard", label: "Dashboard", icon: Chart },
  { id: "mahsulotlar", label: "Mahsulotlar", icon: Box },
  { id: "buyurtmalar", label: "Buyurtmalar", icon: Receipt },
  { id: "foydalanuvchilar", label: "Foydalanuvchilar", icon: Users },
  { id: "sovgalar", label: "Sovg‘alar", icon: Gift },
  { id: "takliflar", label: "Takliflar", icon: Lightbulb },
] as const;

export type AdminTab = (typeof tabs)[number]["id"];

export default function AdminPanel() {
  const { user, loading, openLogin } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: AdminTab = tabs.find((t) => t.id === params.get("tab"))?.id ?? "dashboard";

  if (loading) return <div className="h-96 animate-pulse rounded-3xl bg-white" />;

  if (!user || !user.is_admin) {
    return (
      <div className="mx-auto max-w-md rounded-3xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-100">
        <div className="mx-auto grid size-14 place-items-center rounded-full bg-brand-soft text-brand">
          <Shield className="size-7" />
        </div>
        <h1 className="mt-4 text-2xl font-bold">{user ? "Ruxsat yo‘q" : "Admin panel"}</h1>
        <p className="mt-2 text-sm text-slate-500">
          {user
            ? "Bu sahifa faqat administratorlar uchun. Telegram ID’ingiz ADMIN_TELEGRAM_IDS ro‘yxatida bo‘lsa, tizimdan chiqib qayta kiring."
            : "Davom etish uchun administrator hisobi bilan tizimga kiring."}
        </p>
        {!user && (
          <button
            onClick={() => openLogin()}
            className="mt-6 w-full rounded-xl bg-brand py-3 text-sm font-semibold text-white shadow-md shadow-blue-600/25 hover:bg-brand-dark"
          >
            Tizimga kirish
          </button>
        )}
      </div>
    );
  }

  const select = (id: AdminTab, extra = "") =>
    router.replace(id === "dashboard" ? pathname : `${pathname}?tab=${id}${extra}`, { scroll: false });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="h-fit rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-100 lg:sticky lg:top-24">
        <p className="px-3 pb-3 pt-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Admin panel</p>
        <nav className="flex gap-1 overflow-x-auto lg:flex-col">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => select(id)}
              className={`flex shrink-0 items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition ${
                tab === id ? "bg-brand-soft text-brand" : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              <Icon className="size-4.5" /> {label}
            </button>
          ))}
        </nav>
      </aside>

      <section className="min-w-0">
        {tab === "dashboard" && <Dashboard onAddProduct={() => select("mahsulotlar", "&yangi=1")} onOpenOrders={() => select("buyurtmalar")} onOpenSuggestions={() => select("takliflar")} />}
        {tab === "mahsulotlar" && (
          <ProductsAdmin startWithNew={params.get("yangi") === "1"} onNewHandled={() => select("mahsulotlar")} />
        )}
        {tab === "buyurtmalar" && <OrdersAdmin />}
        {tab === "foydalanuvchilar" && <UsersAdmin />}
        {tab === "sovgalar" && <RewardsAdmin />}
        {tab === "takliflar" && <SuggestionsAdmin />}
      </section>
    </div>
  );
}
