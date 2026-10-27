// Brauzer so‘rovlari Next.js rewrites orqali backendga yo‘naltiriladi (next.config.ts), shuning uchun nisbiy yo‘l
const API_BASE = "/api";
const TOKEN_KEY = "servisai_token";

export type User = {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  avatar_url: string | null;
  telegram_id: number | null;
  telegram_username: string | null;
  has_google: boolean;
  balance: number;
  is_admin: boolean;
  created_at: string;
};

export type OrderStatus = "pending" | "paid" | "processing" | "completed" | "cancelled";

export type OrderEvent = { id: number; status: OrderStatus; note: string | null; created_at: string };

export type Order = {
  id: number;
  number: string;
  product_id: string | null;
  product_name: string;
  /** Nomi tarixiy: son duration_unit birligida */
  duration_months: number;
  duration_unit: DurationUnit;
  quantity: number;
  /** Jami to‘langan summa (narx × soni) */
  price: number;
  status: OrderStatus;
  comment: string | null;
  delivery_info: string | null;
  paid_from_balance: boolean;
  created_at: string;
  updated_at: string;
};

export type OrderDetail = Order & { events: OrderEvent[] };

export type HistoryItem = {
  id: number;
  order_id: number;
  order_number: string;
  product_name: string;
  status: OrderStatus;
  note: string | null;
  created_at: string;
};

export type UserStats = { total_orders: number; active_orders: number; completed_orders: number; total_spent: number };

export type Wallet = {
  balance: number;
  card_number: string | null;
  card_holder: string | null;
  min_amount: number;
  max_amount: number;
  topup_enabled: boolean;
};

export type TopUpStatus = "pending" | "approved" | "rejected";

export type TopUp = {
  id: number;
  amount: number;
  status: TopUpStatus;
  admin_note: string | null;
  created_at: string;
  reviewed_at: string | null;
};

export type Transaction = {
  id: number;
  type: "topup" | "purchase" | "refund";
  amount: number;
  balance_after: number;
  note: string | null;
  order_id: number | null;
  topup_id: number | null;
  created_at: string;
};

export type DurationUnit = "day" | "month";

export type ProductCategory = "chat" | "design" | "code" | "office" | "social" | "other";
export type ProductBadge = "popular" | "sale" | "new" | "api";

export type Product = {
  id: string;
  name: string;
  description: string;
  price: number;
  old_price: number | null;
  durations: number[];
  /** durations birligi: month — oy, day — kun */
  duration_unit: DurationUnit;
  /** Admin yuklagan logo; null — saytdagi standart logo */
  logo_url: string | null;
  category: ProductCategory;
  badge: ProductBadge | null;
  features: string[];
  /** null — cheklanmagan, 0 — tugagan */
  stock: number | null;
  /** Haqiqiy sotuvlar (bekor qilinmagan buyurtmalar) */
  sold_count: number;
  /** Masalan "10 daqiqa – 1 soat" */
  delivery_time: string;
  /** Xariddan so‘ng ma’lumot darhol beriladimi */
  instant_delivery: boolean;
  /** "Muhim ma’lumot": qoidalar, kafolat shartlari */
  notes: string;
};

export type DeliveryMode = "auto" | "manual";

export type AdminProduct = Product & {
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
  /** auto — har xaridorga ro‘yxatdan alohida havola/kod; soni = berilmagan elementlar soni */
  delivery_mode: DeliveryMode;
  /** Boshlang‘ich "sotib olganlar" soni (sold_count = sold_base + haqiqiy xaridlar) */
  sold_base: number;
};

export type DeliveryItem = {
  id: number;
  content: string;
  created_at: string;
  delivered_at: string | null;
  order_id: number | null;
  order_number: string | null;
  user_id: number | null;
  user_name: string | null;
};

/** Yaratish/tahrirlash so‘rovi (id faqat yaratishda yuboriladi) */
export type ProductInput = Omit<AdminProduct, "id" | "created_at" | "updated_at" | "sold_count" | "instant_delivery" | "logo_url"> & { id?: string };

export type AdminStats = {
  users_total: number;
  users_new_7d: number;
  products_active: number;
  products_total: number;
  orders_total: number;
  orders_active: number;
  revenue_total: number;
  revenue_30d: number;
  topups_pending: number;
  /** Javob berilmagan takliflar */
  suggestions_new: number;
};

export type AdminOrder = Order & {
  user_id: number;
  user_name: string;
  user_telegram_username: string | null;
  user_phone: string | null;
};

export type AdminUser = {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  avatar_url: string | null;
  telegram_id: number | null;
  telegram_username: string | null;
  balance: number;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
  orders_count: number;
  total_spent: number;
};

export type AdminUserList = { items: AdminUser[]; total: number; total_balance: number; users_with_balance: number };

export type AdminUserDetail = {
  user: AdminUser;
  /** Taklif qilgan do‘stlari soni va o‘zini kim taklif qilgani */
  friends: number;
  referred_by_name: string | null;
  /** Tasdiqlangan to‘ldirishlar yig‘indisi */
  topped_up: number;
  topups: { id: number; amount: number; status: TopUpStatus; admin_note: string | null; created_at: string }[];
  orders: Order[];
};

export type TopProduct = { product_id: string | null; product_name: string; orders: number; revenue: number };

export const topUpStatusMeta: Record<TopUpStatus, { label: string; className: string }> = {
  pending: { label: "Tekshirilmoqda", className: "bg-amber-50 text-amber-700" },
  approved: { label: "Tasdiqlandi", className: "bg-emerald-50 text-emerald-700" },
  rejected: { label: "Rad etildi", className: "bg-rose-50 text-rose-600" },
};

export type AuthConfig = { google_client_id: string | null; telegram_bot_username: string | null };

export type TokenResponse = { access_token: string; user: User };

export type TelegramInit = { token: string; bot_url: string; expires_in: number };

export type TelegramStatus = {
  status: "pending" | "confirmed" | "expired" | "error";
  detail: string | null;
  access_token: string | null;
  user: User | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const tokenStore = {
  get: () => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token: string | null) => {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* private rejim — token faqat shu sessiyada qoladi */
    }
  },
};

const REF_KEY = "servisai_ref";

/** Taklif havolasidagi kod (?ref=KOD): ro‘yxatdan o‘tguncha brauzerda saqlanadi */
export const refStore = {
  get: () => {
    try {
      return localStorage.getItem(REF_KEY);
    } catch {
      return null;
    }
  },
  set: (code: string | null) => {
    try {
      if (code) localStorage.setItem(REF_KEY, code);
      else localStorage.removeItem(REF_KEY);
    } catch {
      /* private rejim */
    }
  },
};

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const token = tokenStore.get();
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(json !== undefined && { "Content-Type": "application/json" }),
      ...(token && { Authorization: `Bearer ${token}` }),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    let message = "Xatolik yuz berdi, qaytadan urinib ko‘ring";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      /* JSON emas */
    }
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const statusMeta: Record<OrderStatus, { label: string; className: string; dot: string }> = {
  pending: { label: "To‘lov kutilmoqda", className: "bg-amber-50 text-amber-700", dot: "bg-amber-500" },
  paid: { label: "To‘landi", className: "bg-sky-50 text-sky-700", dot: "bg-sky-500" },
  processing: { label: "Faollashtirilmoqda", className: "bg-violet-50 text-violet-700", dot: "bg-violet-500" },
  completed: { label: "Bajarildi", className: "bg-emerald-50 text-emerald-700", dot: "bg-emerald-500" },
  cancelled: { label: "Bekor qilindi", className: "bg-slate-100 text-slate-500", dot: "bg-slate-400" },
};

const pad = (n: number) => String(n).padStart(2, "0");

/** "2026-10-26T12:50:26Z" -> "26.10.2026, 17:50" (foydalanuvchi vaqt zonasida) */
export function formatDate(iso: string, withTime = true) {
  const d = new Date(iso);
  const date = `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
  return withTime ? `${date}, ${pad(d.getHours())}:${pad(d.getMinutes())}` : date;
}

/* ---------- Do‘st taklif qilish ---------- */

export type MyReward = {
  id: number;
  title: string;
  required_friends: number;
  product_id: string;
  product_name: string;
  quantity: number;
  achieved: boolean;
  granted: boolean;
  order_number: string | null;
};

export type MyReferral = {
  code: string;
  site_link: string;
  bot_link: string | null;
  friends: number;
  friends_list: { name: string; joined_at: string }[];
  rewards: MyReward[];
};

export type Reward = {
  id: number;
  title: string;
  required_friends: number;
  product_id: string;
  product_name: string;
  quantity: number;
  is_active: boolean;
  granted_count: number;
  eligible_count: number;
  created_at: string;
};

export type RewardGrant = {
  id: number;
  user_id: number;
  user_name: string;
  user_telegram_username: string | null;
  reward_title: string;
  order_id: number | null;
  order_number: string | null;
  order_status: OrderStatus | null;
  created_at: string;
};

export type TopReferrer = { user_id: number; user_name: string; user_telegram_username: string | null; friends: number };

/* ---------- Takliflar ---------- */

export type Suggestion = {
  id: number;
  text: string;
  reply: string | null;
  replied_at: string | null;
  reply_seen: boolean;
  created_at: string;
};

export type AdminSuggestion = Suggestion & {
  user_id: number;
  user_name: string;
  user_telegram_username: string | null;
  replied_by: string | null;
};
