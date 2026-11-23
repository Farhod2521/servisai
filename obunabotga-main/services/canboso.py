"""Ta'minotchi: canboso.com (Telegram buyer API).

  GET  /products  — mahsulotlar ro'yxati (narx USD da, nomlar inglizcha)
  GET  /balance   — bizning ta'minotchidagi hamyon qoldig'i
  POST /purchase  — mahsulot sotib olish (har bir so'rovga noyob Idempotency-Key)

Bu modul:
  • katalogni olib, botga O'ZBEKCHA nom/tavsif, SO'M narx (kurs + foyda),
    brend logotipi va kategoriya bilan yozadi;
  • xaridni ta'minotchiga yuboradi va yetkazilgan ma'lumotni qaytaradi.

API kalit faqat .env (CANBOSO_API_KEY) da turadi — kodga yoki GitHub'ga yozilmaydi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Category, DeliveryType, PriceChange, Product, ProductSource
from services import curation, naming, overrides, runtime

log = logging.getLogger("uzshop.canboso")

PREFIX = "cb:"                 # external_id prefiksi — boshqa ta'minotchilar bilan aralashmasin
TIMEOUT = aiohttp.ClientTimeout(total=30)
CBU_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/"
RATE_TTL = 6 * 3600


class SupplierError(Exception):
    """Ta'minotchi bilan ishlashda xato (xabar foydalanuvchiga/adminga ko'rsatilishi mumkin)."""


def _mask(text: str) -> str:
    key = settings.canboso_api_key
    return text.replace(key, "***") if key else text


# ─────────────────────────── Tarmoq ───────────────────────────

async def _request(method: str, path: str, *, params=None, json_body=None, headers=None):
    if not settings.canboso_api_key:
        raise SupplierError("CANBOSO_API_KEY sozlanmagan")
    url = f"{settings.canboso_api_url.rstrip('/')}/{path}"
    hdrs = {"Accept": "application/json", "Accept-Language": "en-US,en;q=0.9", **(headers or {})}   # nomlar inglizcha kelsin
    async with aiohttp.ClientSession(timeout=TIMEOUT) as http:
        async with http.request(method, url, params=params, json=json_body, headers=hdrs) as resp:
            body = await resp.text()
            try:
                data = json.loads(body)
            except ValueError:
                data = None
            return resp.status, data, dict(resp.headers)


async def fetch_products() -> list[dict]:
    try:
        status, data, headers = await _request(
            "GET", "products", params={"key": settings.canboso_api_key}
        )
    except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
        raise SupplierError(f"Ta'minotchiga ulanib bo'lmadi: {_mask(str(ex))}") from ex
    if status == 429:
        raise SupplierError(
            f"Ta'minotchi so'rovlarni cheklab qo'ydi. {headers.get('Retry-After', '?')} soniyadan keyin urinib ko'ring."
        )
    if status in (400, 401) or not isinstance(data, dict) or not data.get("success"):
        msg = data.get("message") if isinstance(data, dict) else None
        raise SupplierError(f"Ta'minotchi katalogni bermadi ({status}): {msg or 'javob noto‘g‘ri'}")
    items = data.get("products")
    if not isinstance(items, list):
        raise SupplierError("Ta'minotchi javobida mahsulotlar ro'yxati yo'q")
    if data.get("walletCurrency") and str(data.get("walletCurrency")).upper() != "USD":
        # Narxni so'mga aylantirish USD ga asoslangan — boshqa valyutada xato narx chiqmasin
        raise SupplierError(f"Kutilmagan valyuta: {data.get('walletCurrency')} (USD kutilgan)")
    return items


async def fetch_balance() -> float | None:
    """Ta'minotchidagi hamyon qoldig'i (USD). Olib bo'lmasa None."""
    try:
        status, data, _ = await _request("GET", "balance", params={"key": settings.canboso_api_key})
    except (aiohttp.ClientError, asyncio.TimeoutError, SupplierError):
        return None
    if status == 200 and isinstance(data, dict) and data.get("success"):
        try:
            return float(data.get("balance"))
        except (TypeError, ValueError):
            return None
    return None


async def balance_line() -> str:
    """Hisobotlar uchun: «💳 Ta'minotchi hamyoni: $12.34» (+ kam bo'lsa ogohlantirish). Kalit yo'q yoki olib bo'lmasa — ''."""
    if not settings.canboso_api_key:
        return ""
    bal = await fetch_balance()
    if bal is None:
        return ""
    line = f"💳 Ta'minotchi hamyoni: <b>${bal:,.2f}</b>"
    if bal < settings.supplier_low_usd:
        line += "\n⚠️ <b>Hamyon kam — to'ldiring, aks holda buyurtmalar bajarilmaydi!</b>"
    return line


_rate_cache: tuple[float, float] = (0.0, 0.0)


async def _rate_cbu(http) -> float:
    async with http.get(CBU_URL) as resp:
        return float(((await resp.json(content_type=None))[0])["Rate"])


async def _rate_nbu(http) -> float:
    async with http.get("https://nbu.uz/exchange-rates/json/") as resp:
        for row in await resp.json(content_type=None):
            if str(row.get("code", "")).upper() == "USD":
                return float(row.get("cb_price") or row.get("nbu_cell_price"))
    raise ValueError("USD topilmadi")


async def _rate_er_api(http) -> float:
    async with http.get("https://open.er-api.com/v6/latest/USD") as resp:
        return float((await resp.json(content_type=None))["rates"]["UZS"])


async def _rate_exchangerate(http) -> float:
    async with http.get("https://api.exchangerate-api.com/v4/latest/USD") as resp:
        return float((await resp.json(content_type=None))["rates"]["UZS"])


# Kurs manbalari: biri ochilmasa keyingisi sinaladi (Render'dan ba'zi saytlar ochilmasligi mumkin)
RATE_SOURCES = [("CBU", _rate_cbu), ("NBU", _rate_nbu), ("open.er-api.com", _rate_er_api), ("exchangerate-api.com", _rate_exchangerate)]
_RATE_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ObunalarBot/1.0)", "Accept": "application/json"}


async def usd_rate() -> float:
    """1 USD necha so'm. Admin/USD_TO_UZS qo'lda bergan kurs ustun; aks holda bir necha manbadan (Markaziy bank va boshqalar)
    olinadi va oxirgi muvaffaqiyatli kurs bazaga saqlanadi (manbalar ochilmasa shu ishlatiladi)."""
    global _rate_cache
    manual = runtime.usd_rate_override()
    if manual > 0:
        return manual
    ts, cached = _rate_cache
    if cached and time.monotonic() - ts < RATE_TTL:
        return cached
    errors: list[str] = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10), headers=_RATE_HEADERS) as http:
        for name, fetch in RATE_SOURCES:
            try:
                rate = float(await fetch(http))
                if not 1000 <= rate <= 100000:
                    raise ValueError("g'alati kurs: %s" % rate)
            except Exception as ex:  # noqa: BLE001
                errors.append("%s: %s" % (name, type(ex).__name__))
                continue
            _rate_cache = (time.monotonic(), rate)
            if runtime.usd_last() != rate:
                await runtime.set_value("usd_last", f"{rate:g}")        # manbalar ochilmay qolsa shu ishlatiladi
            log.info("USD kursi: %s (%s)", rate, name)
            return rate
    log.warning("USD kursi olinmadi: %s", "; ".join(errors))
    fallback = cached or runtime.usd_last()
    if fallback:
        log.warning("Eski kurs ishlatilmoqda: %s", fallback)
        return fallback
    raise SupplierError(
        "USD kursini olib bo'lmadi (%s). Admin panel → 💰 Narx va foyda → 💱 USD kursi ga kursni qo'lda yozing (masalan 12100)."
        % "; ".join(errors)
    )


# ─────────────────────────── Narx ───────────────────────────

def sell_price_uzs(usd: float, rate: float, name: str = "", brand: str = "", warranty: str | None = None) -> tuple[int, int]:
    """(ta'minotchi narxi so'mda, sotuv narxi so'mda). Sotuv narxi yuqoriga yaxlitlanadi.

    Aqlli rejim (sukut): asl narx, kafolat va rasmiy narxga qarab (services/pricing.py). Qo'lda foiz qo'yilsa — bir xil foiz.
    """
    base = usd * rate
    own = runtime.brand_markups().get(brand or "")
    if own is not None:                       # admin shu brendga o'z foizini qo'ygan: tannarx + foiz
        return int(round(base)), clean_uzs(base * (1 + own / 100), base)
    if runtime.pricing_mode() == "tiers":
        return int(round(base)), clean_uzs(base + runtime.tier_markup(usd), base)       # tannarx + qat'iy ustama (mijoz jadvali)
    if runtime.pricing_smart() and name:
        from services import pricing
        price = pricing.sell_usd(usd, name, brand, warranty) * rate
    else:
        price = base * (1 + runtime.markup_percent() / 100)
    return int(round(base)), clean_uzs(price, base)


def clean_uzs(price: float, cost: float = 0) -> int:
    """So'm narxini «yumaloq» qiladi: 48 120 emas 48 000, 4 187 emas 4 200.

    Eng yaqin chiroyli songa yaxlitlanadi; agar bu ta'minotchi narxidan 5% dan kam foyda qoldirsa — yuqoriga.
    """
    step = (100 if price < 10_000 else 500 if price < 50_000 else 1_000 if price < 200_000
            else 5_000 if price < 1_000_000 else 10_000)
    out = int(round(price / step) * step)
    if cost and out < cost * 1.05:
        out = int(math.ceil(cost * 1.05 / step) * step)
    return max(out, step)


# Ta'minotchi narxi (yoki kurs) oshganda bizning narx ham oshadi, lekin FOYDA eng ko'pi bilan shuncha so'm o'sadi
RISE_EXTRA = 5_000


def cap_rise(old_price: int, old_cost: int, new_cost: int, new_price: int) -> int:
    """Narx keskin sakramasin: ta'minotchi narxi oshsa — bizniki oshgan farqqa + ko'pi bilan RISE_EXTRA so'm.

    Masalan, ta'minotchida 1$ → 2$ bo'lsa va hozirgi foydamiz 10 000 so'm bo'lsa, yangi foyda ≤ 15 000 so'm.
    Narx pasaysa yoki ta'minotchi narxi oshmasa — o'zgarmaydi (hisoblangan narx olinadi).
    """
    if not old_price or not old_cost or new_cost <= old_cost:
        return new_price
    limit = old_price + (new_cost - old_cost) + RISE_EXTRA
    return min(new_price, clean_uzs(limit, new_cost))


def pricing_policy() -> str:
    """Narx siyosati belgisi: admin aqlli/oddiy rejimni yoki foizni o'zgartirsa, belgi o'zgaradi (cheklov bekor bo'ladi)."""
    tiers = ",".join(f"{u}:{m}" for u, m in runtime.markup_tiers()) if runtime.pricing_mode() == "tiers" else ""
    brands = ",".join(f"{b}={p:g}" for b, p in sorted(runtime.brand_markups().items()))
    return f"{runtime.pricing_mode()}:{runtime.markup_percent()}:{tiers}:{brands}:v1"


def decide_price(old_price: int, old_cost: int, meta: dict, usd: float, new_cost: int, target: int, policy: str) -> tuple[int, bool]:
    """(narx, hold). Ta'minotchi USD narxi oshsa — cap_rise bilan cheklangan narx; keyingi sinxronlarda
    ta'minotchi narxi va siyosat o'zgarmaguncha shu narx USHLAB TURILADI (har safar 5 000 dan qo'shilib ketmasin)."""
    if policy.startswith("tiers"):         # qat'iy ustama: narx tannarx bilan birga aniq o'zgaradi, cheklov kerak emas
        return target, False
    unchanged = meta.get("usd") == usd and meta.get("pol") == policy
    if unchanged and meta.get("hold") and old_price:
        return max(old_price, clean_uzs(new_cost * 1.08, new_cost)), True
    price = cap_rise(old_price, old_cost, new_cost, target)
    return price, price < target


# ─────────────────────────── Xavfli / nomaqbul mahsulotlar ───────────────────────────
#
# Ta'minotchi ro'yxatida soxta obunachi/layk, ommaviy "toza" akkauntlar, tasdiqlashni
# aylanib o'tish, SMS-kod ijarasi va spam vositalari ham bor. Ular do'konga QO'SHILMAYDI:
# platformalar qoidalariga zid, Telegram botlar uchun ham taqiqlangan va README'dagi
# "sotiladigan mahsulot rasmiy bo'lishi kerak" shartiga to'g'ri kelmaydi.

_BLOCK_NAME = re.compile(
    r"\bbuff\b|\bboost\s*\d|\bfollow(?:er)?s?\b|\bmembers?\b|\bunlock\b|selfie|verif(?:y|ied|ication)"
    r"|blue\s*check|\bchbm\b|dormant|clone|\botp\b|\bspam\b|bypass|login type"
    # «token» faqat akkaunt tokeni ma'nosida bloklanadi — AI kreditlari (ElevenLabs 1M token) qoladi
    r"|\b(?:discord|telegram|steam|session|auth|login)\s+tokens?\b|\btokens?\s+(?:account|login)\b"
    r"|promo code bot|youtube channel|soaked|\bapple id\b|onlyfan|\baccount x\b"
    r"|hotmail|outlook|oauth|^\W*(?:old\s+random\s+)?gmail|\bclaude free\b|was created"
    r"|disney|\bhbo\b|\bhulu\b|prime video|crunchyroll|paramount|peacock|apple tv|\bviu\b|\bwetv\b",
    re.I,
)
_BLOCK_BRANDS = {"gmail", "outlook", "facebook", "tiktok", "x", "reddit", "onlyfans"}

# O'zbekistonda deyarli ishlatilmaydigan yoki mijoz so'ramaydigan servislar — do'konga qo'shilmaydi.
# Ro'yxatni o'zgartirish uchun brend nomini shu yerdan qo'shing yoki olib tashlang.
UNPOPULAR_BRANDS = {
    "YouTube", "iQIYI", "Xbox",                       # kino/o'yin: O'zbekistonda talab yo'q
    "Quizlet", "Scribd", "Kahoot",                               # chet el o'qish servislari
    "Meitu", "Wink", "Xingtu", "BeautyCam", "Locket",            # xitoy/AQSh foto-ilovalari
    "HMA VPN", "Hotspot Shield", "IPVanish", "GPM Login",        # kam ishlatiladigan VPN/brauzerlar
    "AWS", "Kiro", "Wispr Flow", "Manus", "LartAI",   # tor dasturchi vositalari (Railway — do'konda bor)
    "AI vosita",                                                 # Flux, Tryclico, Cuty, Dropshot
    # O'zbekistonda ishlatilmaydi / kerak emas (egasi so'radi): Telegram xizmatlari, YouTube va boshqa begona servislar
    "Telegram", "Discord", "Twitch", "Apple Music", "Skillshare", "Evernote", "Todoist", "Prezi", "Dropbox", "LinkedIn",
}


def is_blocked(name: str, emoji: str = "") -> bool:
    if (emoji or "").lower() in _BLOCK_BRANDS:
        return True
    return bool(_BLOCK_NAME.search(name))


# ─────────────────────────── Brend, logotip, kategoriya ───────────────────────────
#
# (nom regex, ko'rsatiladigan brend, logotip domeni, kategoriya kaliti). Tartib muhim.

BRANDS: list[tuple[str, str, str, str]] = [
    # ── Qo'shimcha brendlar ──
    (r"codex", "Codex", "chatgpt.com", "ai"),                 # Codex — alohida brend (ChatGPT'dan oldin tekshiriladi)
    (r"\bwindows\b", "Windows", "microsoft.com", "office"),
    (r"open\s*art", "OpenArt", "", "media_ai"),
    (r"leonardo", "Leonardo AI", "", "media_ai"),
    (r"midjourney|\bmj\b", "Midjourney", "midjourney.com", "media_ai"),
    (r"\bsora\b", "Sora", "sora.com", "media_ai"),
    (r"\bpika\b", "Pika", "pika.art", "media_ai"),
    (r"\bflux\b", "Flux", "", "media_ai"),
    (r"domo\s*ai", "DomoAI", "", "media_ai"),
    (r"\bluma\b", "Luma", "lumalabs.ai", "media_ai"),
    (r"hailuo", "Hailuo", "hailuoai.video", "media_ai"),
    (r"\bvidu\b", "Vidu", "vidu.com", "media_ai"),
    (r"hedra", "Hedra", "hedra.com", "media_ai"),
    (r"pixverse", "PixVerse", "pixverse.ai", "media_ai"),
    (r"ideogram", "Ideogram", "ideogram.ai", "media_ai"),
    (r"recraft", "Recraft", "recraft.ai", "media_ai"),
    (r"stability|stable diffusion", "Stability AI", "stability.ai", "media_ai"),
    (r"veed", "VEED", "veed.io", "design"),
    (r"picsart", "Picsart", "picsart.com", "design"),
    (r"filmora|wondershare", "Filmora", "filmora.wondershare.com", "design"),
    (r"notebook\s*lm", "NotebookLM", "notebooklm.google", "ai"),
    (r"\bpoe\b", "Poe", "poe.com", "ai"),
    (r"mistral", "Mistral", "mistral.ai", "ai"),
    (r"kimi|moonshot", "Kimi", "kimi.com", "ai"),
    (r"doubao", "Doubao", "doubao.com", "ai"),
    (r"\bgroq\b", "Groq", "groq.com", "ai"),
    (r"openrouter|open router", "OpenRouter", "openrouter.ai", "ai"),
    (r"hugging\s*face", "Hugging Face", "huggingface.co", "ai"),
    (r"github copilot|gh copilot", "GitHub Copilot", "github.com", "ai_dev"),
    (r"copilot", "Copilot", "copilot.microsoft.com", "ai"),
    (r"windsurf", "Windsurf", "windsurf.com", "ai_dev"),
    (r"\bv0\b", "v0", "v0.dev", "ai_dev"),
    (r"vercel", "Vercel", "vercel.com", "ai_dev"),
    (r"\bcline\b", "Cline", "cline.bot", "ai_dev"),
    (r"\btrae\b", "Trae", "trae.ai", "ai_dev"),
    (r"\bwarp\b", "Warp", "warp.dev", "ai_dev"),
    (r"jetbrains|pycharm|intellij|webstorm", "JetBrains", "jetbrains.com", "ai_dev"),
    (r"prezi", "Prezi", "prezi.com", "office"),
    (r"dropbox", "Dropbox", "dropbox.com", "office"),
    (r"evernote", "Evernote", "evernote.com", "office"),
    (r"todoist", "Todoist", "todoist.com", "office"),
    (r"skillshare", "Skillshare", "skillshare.com", "office"),
    (r"apple music", "Apple Music", "music.apple.com", "fun"),
    (r"twitch", "Twitch", "twitch.tv", "fun"),
    (r"claude", "Claude", "claude.ai", "ai"),
    (r"cursor", "Cursor", "cursor.com", "ai_dev"),
    (r"grok", "Grok", "grok.com", "ai"),
    (r"gemini|google ai|google one|\bgg 5tb", "Gemini", "gemini.google.com", "ai"),
    (r"perplexity", "Perplexity", "perplexity.ai", "ai"),
    (r"lovable", "Lovable", "lovable.dev", "ai_dev"),
    (r"manus", "Manus", "manus.im", "ai"),
    (r"deepseek", "DeepSeek", "deepseek.com", "ai"),
    (r"qwen", "Qwen", "qwen.ai", "ai"),
    (r"kiro", "Kiro", "kiro.dev", "ai"),
    (r"replit", "Replit", "replit.com", "ai_dev"),
    (r"n8n", "n8n", "n8n.io", "ai"),
    (r"railway", "Railway", "railway.com", "ai"),
    (r"wispr", "Wispr Flow", "wisprflow.ai", "ai"),
    (r"chat\s*gpt|\bgpt\b|codex|openai", "ChatGPT", "chatgpt.com", "ai"),
    (r"eleven", "ElevenLabs", "elevenlabs.io", "voice_ai"),
    (r"minimax", "MiniMax", "minimax.io", "voice_ai"),
    (r"suno", "Suno", "suno.com", "voice_ai"),
    (r"heygen", "HeyGen", "heygen.com", "media_ai"),
    (r"akool", "Akool", "akool.com", "media_ai"),
    (r"freepik", "Freepik", "freepik.com", "media_ai"),
    (r"\bkrea\b", "Krea", "krea.ai", "media_ai"),
    (r"runway", "Runway", "runwayml.com", "media_ai"),
    (r"dreamina", "Seedance", "dreamina.capcut.com", "media_ai"),     # Seedance modellari Dreamina nomi bilan sotiladi
    (r"kling", "Kling", "klingai.com", "media_ai"),
    (r"higg", "Higgsfield", "higgsfield.ai", "media_ai"),
    (r"seedance|domo ai", "Seedance", "seed.bytedance.com", "media_ai"),
    (r"\bveo|antigravity", "Google VEO", "antigravity.google", "media_ai"),
    (r"lartai", "LartAI", "", "media_ai"),
    (r"tryclico|cuty|dropshot|flux", "AI vosita", "", "media_ai"),
    (r"canva", "Canva", "canva.com", "design"),
    (r"adobe", "Adobe", "adobe.com", "design"),
    (r"figma", "Figma", "figma.com", "design"),
    (r"capcut", "CapCut", "capcut.com", "design"),
    (r"meitu", "Meitu", "meitu.com", "design"),
    (r"\bwink\b", "Wink", "", "design"),
    (r"xingtu", "Xingtu", "", "design"),
    (r"beautycam", "BeautyCam", "", "design"),
    (r"gamma|beautiful edu", "Gamma", "gamma.app", "design"),
    (r"autodesk", "Autodesk", "autodesk.com", "design"),
    (r"microsoft|office 365|ms365", "Microsoft 365", "office.com", "office"),
    (r"notion", "Notion", "notion.com", "office"),
    (r"zoom", "Zoom", "zoom.us", "office"),
    (r"grammarly", "Grammarly", "grammarly.com", "office"),
    (r"duolingo", "Duolingo", "duolingo.com", "office"),
    (r"quizlet", "Quizlet", "quizlet.com", "office"),
    (r"udemy", "Udemy", "udemy.com", "office"),
    (r"coursera", "Coursera", "coursera.org", "office"),
    (r"scribd", "Scribd", "scribd.com", "office"),
    (r"kahoot", "Kahoot", "kahoot.com", "office"),
    (r"linkedin", "LinkedIn", "linkedin.com", "office"),
    (r"spotify", "Spotify", "spotify.com", "fun"),
    (r"netflix", "Netflix", "netflix.com", "fun"),
    (r"youtube|ytb", "YouTube", "youtube.com", "fun"),
    (r"xbox", "Xbox", "xbox.com", "fun"),
    (r"iqiyi", "iQIYI", "iq.com", "fun"),
    (r"icloud", "iCloud", "icloud.com", "fun"),
    (r"roblox|blox fruits", "Roblox", "roblox.com", "fun"),
    (r"nord\s*vpn", "NordVPN", "nordvpn.com", "vpn"),
    (r"express\s*vpn", "ExpressVPN", "expressvpn.com", "vpn"),
    (r"surfshark", "Surfshark", "surfshark.com", "vpn"),
    (r"proton", "Proton", "proton.me", "vpn"),
    (r"\bhma\b", "HMA VPN", "hidemyass.com", "vpn"),
    (r"hotspot shield", "Hotspot Shield", "hotspotshield.com", "vpn"),
    (r"ipvanish", "IPVanish", "ipvanish.com", "vpn"),
    (r"adguard", "AdGuard", "adguard-vpn.com", "vpn"),
    (r"kaspersky", "Kaspersky", "kaspersky.com", "vpn"),
    (r"gpm login", "GPM Login", "", "vpn"),
    (r"telegram|\btele\b", "Telegram", "telegram.org", "social"),
    (r"discord|server boost", "Discord", "discord.com", "social"),
    (r"locket", "Locket", "", "social"),
    (r"\baws\b|amazon web", "AWS", "aws.amazon.com", "other"),
]
_BRANDS_C = [(re.compile(p, re.I), b, d, c) for p, b, d, c in BRANDS]

# Kategoriya: kalit → (nom, emoji, tartib)
CATEGORIES = {
    "ai": ("AI chat", "🤖", 10),
    "ai_dev": ("AI dasturlash", "💻", 15),
    "media_ai": ("AI video va rasm", "🎬", 20),
    "voice_ai": ("AI ovoz va musiqa", "🎙", 25),
    "design": ("Dizayn va montaj", "🎨", 30),
    "office": ("Ofis va o'qish", "📚", 40),
    "fun": ("Kino va musiqa", "🎧", 50),
    "vpn": ("VPN va xavfsizlik", "🔒", 60),
    "social": ("Telegram va Discord", "💬", 70),
    "other": ("Boshqa", "📦", 99),
}


# Eski nomlar: bazada shu nomli bo'lim bo'lsa, yangi bo'lim yaratmasdan nomi almashtiriladi
_LEGACY_CATEGORY_NAMES = {"ai": ["AI chat va API"], "media_ai": ["AI video, rasm va ovoz"]}


def detect_brand(name: str, emoji: str = "") -> tuple[str, str, str]:
    """(brend, logotip domeni, kategoriya kaliti)."""
    for rx, brand, domain, cat in _BRANDS_C:
        if rx.search(name):
            return brand, domain, cat
    return _guess_brand(name, emoji), "", "other"


# Ro'yxatda yo'q yangi mahsulot ham «Boshqa»da nomsiz qolmasin: brend nomi ta'minotchining
# «emoji» maydonidan (u servis nomi bo'ladi) yoki mahsulot nomining birinchi so'zidan olinadi.
# Mijoz harf-belgili aniq brend kartasini ko'radi; keyin BRANDS ga qo'shilsa — rasmiy logotip chiqadi.
_GENERIC_WORDS = {
    "premium", "pro", "plus", "account", "accounts", "full", "new", "vip", "svip", "team", "family", "personal",
    "shared", "private", "business", "basic", "standard", "ultra", "max", "lite", "free", "trial", "month",
    "year", "day", "days", "months", "years", "key", "keys", "code", "codes", "gift", "card", "cards", "invite",
    "subscription", "activation", "student", "edu", "ready", "instant", "auto", "the", "with", "for", "and",
    "ai", "api", "vpn", "web", "app", "pc", "ios", "android", "usa", "global", "unlimited", "credits", "credit",
}


def _guess_brand(name: str, emoji: str = "") -> str:
    hint = re.sub(r"[^a-z0-9]", "", (emoji or "").lower())
    if len(hint) >= 3 and hint.isalpha() and hint not in _GENERIC_WORDS and hint not in _BLOCK_BRANDS:
        return _pretty(hint)
    m = re.match(r"\s*([A-Za-z][A-Za-z0-9]{2,19})\b", name or "")
    if m and m.group(1).lower() not in _GENERIC_WORDS:
        return _pretty(m.group(1))
    return ""


def _pretty(word: str) -> str:
    return word if any(c.isupper() for c in word[1:]) else word.capitalize()


# ─────────────────────────── O'zbekchalash ───────────────────────────

_ACRONYMS = {"api", "vpn", "ai", "vip", "svip", "cdk", "usa", "us", "pc", "ios", "uk", "url", "id", "edu", "k12", "tb", "gb", "gpt", "upi", "hma", "gpm", "aws", "ms", "xai"}
_UNIT = {"w": "hafta", "week": "hafta", "weeks": "hafta", "h": "soat", "hr": "soat", "hrs": "soat", "hour": "soat", "hours": "soat",
         "d": "kun", "day": "kun", "days": "kun",
         "m": "oy", "month": "oy", "months": "oy",
         "y": "yil", "year": "yil", "years": "yil"}
_U = r"(h|hrs?|hours?|d|days?|weeks?|months?|years?|y)"
_N = r"(\d+(?:\s*[-~]\s*\d+)?)"

# Kafolat iboralari — matndan ajratib olinib, oxirida alohida ko'rsatiladi
_WARRANTY_FULL = re.compile(r"\b(?:with\s+)?(?:a\s+)?(?:full|100%?)[\s-]*(?:warranty|guarantee)\b", re.I)
_WARRANTY_NONE = re.compile(
    r"\b(?:with)?(?:out|no|not)\s*[-]?\s*(?:a\s+)?(?:warrant(?:y|ied)|guarantee[d]?)\b"
    r"|\bwarranty\s+not\s+included\b|\bnot\s+guaranteed\b|\bnot\s+warrant(?:y|ied)\b",
    re.I,
)
_WARRANTY_FULL_ANY = re.compile(
    r"\b(?:warranty|guarantee|bh)\s*[-:]?\s*full\b|\bfull[\s-]*(?:time|term|period|duration|life\s*time)?[\s-]*(?:warranty|guarantee|bh)\b|\bbh\s*full\b|\bfull\s*bh\b",
    re.I,
)
_WARRANTY_FULL_N = re.compile(rf"\bfull\s+{_N}\s*-?\s*(months?|weeks?|days?|years?)\s*warranty\b", re.I)
_WARRANTY_AFTER = re.compile(rf"\bwarranty\s*[:\-]?\s*(?:for\s+)?{_N}\s*-?\s*{_U}\b", re.I)
_WARRANTY_BEFORE = re.compile(rf"(?<![\w.]){_N}\s*-?\s*{_U}\s*-?\s*(?:full\s+)?warranty\b", re.I)

_WORDS: list[tuple[str, str]] = [
    (r"\bchat\s*gpt\b", "ChatGPT"), (r"\beleven\s*labs?\b", "ElevenLabs"), (r"\beleven\s*reader\b", "ElevenReader"), (r"\bkling\s*ai\b", "Kling AI"),
    (r"\bhiggs?field\b|\bhigg\b", "Higgsfield"), (r"\bytb\b", "YouTube"), (r"\bms365\b", "Microsoft 365"),
    (r"\bredeem\b", "Redeem-kod"), (r"\btrial\b", "sinov"), (r"\bupgrade\b", "akkauntni yangilash"),
    (r"\bcredits?\b|\bcre\b", "kredit"), (r"\bdevices?\b", "qurilma"), (r"\brandom\b", "tasodifiy"),
    (r"\bpersonal\b", "Shaxsiy"), (r"\bfamily\b|\bfam\b", "Oilaviy"), (r"\bbusiness\b", "Biznes"),
    (r"\bunlimited\b", "Cheksiz"), (r"\bactivation\b", "faollashtirish"), (r"\blink\b", ""),
    (r"\bkey\b", "kalit"), (r"\bcdk\b", "kod"), (r"\bcode\b", "kod"), (r"\baccount\b", "akkaunt"),
    (r"\bofficial\b|\bcheap\b|\bowner\b|\boffers?\b", ""), (r"\bplan\b", "tarif"),
    (r"\binvite\b|\binvitation\b", "taklif"), (r"\bsharing\b|\bshares\b", "ulashma"),
    (r"\bmonthly\b", "oylik"), (r"\bper month\b", "oyiga"), (r"\bbonus\b", "bonus"),
    (r"\bvietnam(?:ese)?\b|\bco viet\b", ""), (r"\bwith\b|\bfor\b|\bhas\b|\bthe\b|\bto\b|\band\b", ""),
    (r"\bget\b", ""), (r"\busers\b", "foydalanuvchi"), (r"\bgenuine\b|\boriginal\b", "haqiqiy"), (r"\bicloud\b", "iCloud"), (r"/day\b", "/kun"),
    (r"\bcan be extended\b", "uzaytiriladigan"), (r"\bgift\b", "sovg'a"), (r"\bshop\b", "do'kon"),
    (r"\(?\s*(?:via\s+|by\s+)?apple\s*pay\s*\)?", " "),
    (r"\blife\s*-?\s*time\b", "umrbod"), (r"\bweekly\b", "haftalik"), (r"\b(?:yearly|annual)\b", "yillik"),
    (r"\bsubscriptions?\b", "obuna"), (r"\b(?:package|pack|bundle)s?\b", "paket"), (r"\bnew\b", "yangi"),
    (r"\bexisting\b", "mavjud"), (r"\byour own\b|\bown\b", "o'zingizning"), (r"\bprivate\b", "shaxsiy"),
    (r"\bshared\b", "umumiy"), (r"\bteam\b", "jamoa"), (r"\bstudents?\b", "talabalar"),
    (r"\beducation(?:al)?\b", "ta'lim"), (r"\binstant(?:ly)?\b", "darhol"), (r"\bauto\b", "avto"),
    (r"\brenew(?:al)?\b", "uzaytirish"), (r"\bpoints?\b", "ball"), (r"\brequests?\b", "so'rov"),
    (r"\bgenerations?\b", "generatsiya"), (r"\bimages?\b", "rasm"), (r"\bvideos?\b", "video"),
    (r"\bminutes?\b|\bmins?\b", "daqiqa"), (r"\bseats?\b", "o'rin"), (r"\bworldwide\b|\bglobal\b", "xalqaro"),
    (r"\bvouchers?\b", "vaucher"), (r"\bcoupons?\b", "kupon"), (r"\bcards?\b", "karta"),
    (r"\bno\s+card\b", "kartasiz"), (r"\bactivate[d]?\b", "faollashtirish"), (r"\bextended\b", "uzaytirilgan"),
    (r"\bfast\b", "tezkor"), (r"\bnon[-\s]?stop\b", "uzluksiz"), (r"\bday\b", "kun"), (r"\bmonth\b", "oy"),
    (r"\byear\b", "yil"), (r"\bweek\b", "hafta"), (r"\bhour\b", "soat"), (r"\bfree\b", "bepul"),
    (r"\bfull\b", "to'liq"), (r"\bin\b|\bof\b|\bon\b|\bat\b|\bby\b|\bor\b|\bis\b", ""),
]


def _dur(num: str, unit: str) -> str:
    compact = re.sub(r"\s+", "", num)
    return f"{compact} {_UNIT.get(unit.lower(), unit)}"


def _smart_case(s: str) -> str:
    """BUTUNLAY KATTA HARFLI so'zlarni oddiy ko'rinishga keltiradi (API, VPN kabilar qoladi)."""
    out = []
    for w in s.split(" "):
        core = re.sub(r"[^\w]", "", w)
        low = core.lower()
        if low in _ACRONYMS:
            out.append(w.upper() if core.isupper() or low in ("api", "vpn", "ai", "vip", "gpt") else w)
        elif len(core) >= 3 and core.isupper() and core.isalpha():
            out.append(w[:1].upper() + w[1:].lower())
        else:
            out.append(w)
    return " ".join(out)


# Mijozga hech narsa demaydigan, nomni uzaytiradigan tarif so'zlari — nomdan olib tashlanadi
_NOISE = re.compile(r"\bEssentials?\b|\(\s*(?:so\s*beautiful|best\s*price|hot\s*deal|super\s*cheap)\s*\)", re.I)


# Ta'minotchi nomlari ba'zan ruscha keladi: avval inglizchaga o'giriladi (keyin umumiy o'zbekchalash va qoidalar ishlaydi)
_RU: list[tuple[str, str]] = [
    (r"полн\w*\s+гарант\w*", "full warranty"), (r"без\s+гарант\w*", "no warranty"), (r"гарант\w*", "warranty"),
    (r"(?<=\d)\s*мес(?:яц\w*|\.)?(?![а-яё\w])", " months"), (r"(?<![а-яё])месяц\w*", "month"),
    (r"(?<=\d)\s*(?:дн(?:я|ей)|день|сут\w*|д)(?![а-яё\w])", " days"), (r"(?<![а-яё])(?:дн(?:я|ей)|день|сут\w*)(?![а-яё])", "days"),
    (r"(?<=\d)\s*недел\w*", " weeks"), (r"(?<![а-яё])недел\w*", "weeks"),
    (r"(?<=\d)\s*(?:год(?:а)?|лет|г\.?)(?![а-яё\w])", " years"), (r"(?<![а-яё])(?:год(?:а)?|лет)(?![а-яё])", "year"),
    (r"(?<=\d)\s*(?:час(?:а|ов)?|ч)(?![а-яё\w])", " hours"),
    (r"аккаунт\w*|учётн\w*\s+запис\w*|учетн\w*\s+запис\w*", "account"), (r"ключ\w*", "key"), (r"(?<![а-яё])код\w*", "code"),
    (r"кредит\w*", "credits"), (r"подписк\w*", "subscription"), (r"личн\w*", "personal"), (r"семейн\w*", "family"),
    (r"приглашени\w*|инвайт\w*", "invite"), (r"слот\w*", "slot"), (r"активаци\w*", "activation"), (r"пробн\w*", "trial"),
    (r"официальн\w*|оффициальн\w*", "official"), (r"общ(?:ий|ая|ее|ие)\b", "shared"), (r"приватн\w*", "private"),
    (r"командн\w*", "team"), (r"безлимит\w*", "unlimited"), (r"бессрочн\w*|навсегда", "lifetime"), (r"бесплатн\w*", "free"),
    (r"(?<![а-яё])(?:на|для|с|и|в|от|по|шт\.?)(?![а-яё])", " "),
]
_RU_C = [(re.compile(p, re.I), r) for p, r in _RU]
_CYR = re.compile(r"[А-Яа-яЁё]")


def ru_to_en(text: str) -> str:
    """Ruscha nom/matnni inglizchaga yaqinlashtiradi («ChatGPT Plus 1 месяц гарантия 30 дней» → «ChatGPT Plus 1 month warranty 30 days»).
    Kirill harfi bo'lmasa — o'zgarmaydi."""
    if not text or not _CYR.search(text):
        return text
    for rx, rep in _RU_C:
        text = rx.sub(rep, text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _drop_cyrillic(name: str) -> str:
    """O'girilmay qolgan ruscha so'zlarni do'kondagi nomdan olib tashlaydi (nom bo'sh qolmasa)."""
    if not _CYR.search(name or ""):
        return name
    out = re.sub(r"\S*[А-Яа-яЁё]\S*", " ", name)
    out = re.sub(r"\s{2,}", " ", out).strip(" -,:|")
    return out if len(out) >= 3 else name


def uz_name(raw: str) -> tuple[str, str]:
    """Ta'minotchi nomini o'zbekchaga o'giradi. (nom, kafolat matni) qaytaradi."""
    s = re.sub(r"[​-‏⁠﻿]", "", raw)
    s = re.sub(r"[^\w\s.,\-+/()\[\]$%:~&'’#|!]", " ", s)       # emoji va belgilar
    s = s.replace("–", "-").replace("—", "-")
    s = _smart_case(re.sub(r"\s+", " ", s).strip())

    warranty = ""

    def grab(text: str) -> str:
        nonlocal warranty
        m = _WARRANTY_FULL_ANY.search(text)       # «warranty full», «full time warranty», «full BH» — muddatdan oldin tekshiriladi
        if m and not _WARRANTY_FULL_N.search(text):
            warranty = warranty or "to'liq kafolat"
            text = text[:m.start()] + " " + text[m.end():]
        m = _WARRANTY_NONE.search(text)
        if m:
            warranty = warranty or "kafolatsiz"
            text = text[:m.start()] + " " + text[m.end():]
        m = _WARRANTY_AFTER.search(text)
        if m:
            warranty = warranty or f"{_dur(m.group(1), m.group(2))} kafolat"
            text = text[:m.start()] + " " + text[m.end():]
        m = _WARRANTY_FULL_N.search(text)
        if m:
            warranty = warranty or f"{_dur(m.group(1), m.group(2))} to'liq kafolat"
            text = text[:m.start()] + " " + text[m.end():]
        m = _WARRANTY_FULL.search(text)
        if m:
            warranty = warranty or "to'liq kafolat"
            text = text[:m.start()] + " " + text[m.end():]
        m = _WARRANTY_BEFORE.search(text)
        if m:
            warranty = warranty or f"{_dur(m.group(1), m.group(2))} kafolat"
            text = text[:m.start()] + " " + text[m.end():]
        return text

    s = grab(s)
    s = re.sub(r"\bwarranty\b|\bguarantee[d]?\b", " ", s, flags=re.I)
    s = _NOISE.sub(" ", s)          # mijozga tushunarsiz tarif so'zlari («Essential»)

    # Muddatlar
    s = re.sub(rf"(?<![\w.]){_N}\s*-?\s*(months?|years?|weeks?|days?|hours?|hrs?)\b", lambda m: _dur(m.group(1), m.group(2)), s, flags=re.I)
    s = re.sub(r"(?<![\w.])(\d+)\s*([dDyY])\b", lambda m: _dur(m.group(1), m.group(2)), s)
    s = re.sub(r"(?<![\w.])(\d+)\s*[mM]\s+kredit", r"\1 mln kredit", s)
    s = re.sub(r"\b(\d+)\s*M\s+credit", r"\1 mln kredit", s, flags=re.I)
    s = re.sub(r"\[\s*(cdk|key)\s*\]", lambda m: "Kod" if m.group(1).lower() == "cdk" else "Kalit", s, flags=re.I)

    s = re.sub(r"(?<=\d)\s*cre\b", " kredit", s, flags=re.I)                  # «80cre» → «80 kredit»
    if re.search(r"credit|\bcre\b|kredit", s, re.I):                         # «700~1k credit» → «700-1000 kredit»
        s = re.sub(r"(?<![\w.])(\d+)\s*k\b", lambda m: str(int(m.group(1)) * 1000), s, flags=re.I)
        s = re.sub(r"(?<=\d)\s*~\s*(?=\d)", "-", s)
    s = re.sub(r"\b(?:your\s+)?own\s+e-?mail\b", "o'z emailingizga", s, flags=re.I)      # «Own Email» -> «o'z emailingizga»
    for pat, rep in _WORDS:
        s = re.sub(pat, rep, s, flags=re.I)
    s = re.sub(r"(?i)\bRedeem-kod\s+kod\b", "Redeem-kod", s)                           # «Redeem Code» -> «Redeem-kod»

    s = re.sub(r"(?i)\bkod\s+Redeem-kod", "Redeem-kod", s)
    s = re.sub(r"(?<![\w'’])(?:a|an)(?![\w'’])", " ", s)                   # inglizcha artikllar (kichik harfda)
    s = re.sub(r"\b(\d+ (?:oy|kun|yil))\s+\1\b", r"\1", s)    # "1 yil 1 yil"
    s = re.sub(r"\(\s*\)|\[\s*\]", " ", s)
    s = re.sub(r"(?:^|\s)[/|](?=\s|$)", " ", s)                        # yolg'iz «/» yoki «|» belgilari
    s = re.sub(r"\s*[-,:]\s*(?=[-,:]|$)", " ", s)          # osilib qolgan tire/vergul
    s = re.sub(r"^\s*[-,:]\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -,:|")
    m = re.match(r"(?i)^kod\s+(.+)$", s)
    if m and not re.search(r"(?i)redeem", s):
        s = f"{m.group(1)} (kod)"
    if s:
        s = s[0].upper() + s[1:]
    return s[:200], warranty


# Brend bo'yicha eng qisqa muddat (kun): CapCut — kamida 7 kunlik obuna; soatlik/1–6 kunlik tariflar ko'rsatilmaydi
MIN_DAYS: dict[str, int] = {}     # egasi qarori: muddat bo'yicha cheklov yo'q


def duration_days(name: str) -> float | None:
    """Nomdagi muddat kunda («12 soat» → 0.5, «7 kun» → 7, «1 oy» → 30). Topilmasa None."""
    m = re.search(r"(?<![\w.])(\d+)\s*(soat|kun|hafta|oy|yil)\b", name or "", re.I)
    if not m:
        return None
    return int(m.group(1)) * {"soat": 1 / 24, "kun": 1, "hafta": 7, "oy": 30, "yil": 365}[m.group(2).lower()]


def no_warranty_banned(brand: str, warranty: str) -> bool:
    """CapCut: kafolatsiz tariflar do'konga qo'yilmaydi (hisob tez uchib ketadi, mijoz norozi)."""
    return False                       # egasi qarori: kafolatsiz tariflar ham chiqadi


def too_short(brand: str, name: str) -> bool:
    need = MIN_DAYS.get(brand)
    d = duration_days(name) if need else None
    return d is not None and d < need


_KNOWN_KEYS = {"productId", "name", "price", "availability", "productType", "purchaseRequirements", "emoji"}


def warranty_from_text(text: str) -> str:
    """Erkin matndan kafolat iborasini topadi («30 days warranty», «full warranty», «no warranty»). Topilmasa ''."""
    text = ru_to_en(text)
    m = _WARRANTY_NONE.search(text)
    if m:
        return "kafolatsiz"
    if _WARRANTY_FULL_ANY.search(text) and not _WARRANTY_FULL_N.search(text):
        return "to'liq kafolat"
    for rx, fmt in ((_WARRANTY_AFTER, "{} kafolat"), (_WARRANTY_FULL_N, "{} to'liq kafolat"), (_WARRANTY_BEFORE, "{} kafolat")):
        m = rx.search(text)
        if m:
            return fmt.format(_dur(m.group(1), m.group(2)))
    return "to'liq kafolat" if _WARRANTY_FULL.search(text) else ""


def raw_warranty(raw: dict) -> str:
    """Nomda kafolat yozilmagan bo'lsa — ta'minotchi javobidagi boshqa matn maydonlaridan qidiradi (tavsif, izoh…)."""
    for k, v in raw.items():
        if k in _KNOWN_KEYS:
            continue
        texts = [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, list) else []
        for t in texts:
            w = warranty_from_text(t)
            if w:
                return w
    return ""


def raw_texts(raw: dict) -> list[str]:
    """Ta'minotchi javobidagi qo'shimcha matnlar (tavsif, yo'riqnoma...): asosiy maydonlardan tashqari. Admin ko'rishi uchun."""
    out: list[str] = []
    for k, v in raw.items():
        if k in _KNOWN_KEYS:
            continue
        vals = [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, list) else []
        out += [f"{k}: {x.strip()}" for x in vals if x.strip()]
    return out


def kind_label(ptype: str) -> str:
    return {
        "account": "Tayyor akkaunt / kod",
        "slot": "Slot (emailingizga taklif yuboriladi)",
        "upgrade_account": "Sizning akkauntingiz yangilanadi",
    }.get(ptype, "Raqamli mahsulot")


def build_description(ptype: str, warranty: str, need: str | None) -> str:
    lines = [f"Turi: {kind_label(ptype)}"]
    if warranty:
        lines.append(f"Kafolat: {warranty}")
    if ptype == "account":
        lines.append("Xariddan so'ng ma'lumotlar darhol beriladi")
    else:
        lines.append("Buyurtma qo'lda bajariladi — holatini «Buyurtmalar» bo'limida ko'rasiz")
    if need == "email":
        lines.append("Sotib olishda email manzilingiz so'raladi")
    elif need == "accounts":
        lines.append("Sotib olishda akkaunt (email yoki login) so'raladi")
    return "\n".join(lines)


# ─────────────────────────── Tahlil ───────────────────────────

def parse_item(raw: dict) -> dict:
    pid = str(raw.get("productId") or "").strip()
    name_en = ru_to_en(str(raw.get("name") or "").strip())          # ruscha nom bo'lsa — inglizchaga
    if not pid or not name_en:
        raise ValueError("productId yoki nom yo'q")
    try:
        usd = float((raw.get("price") or {}).get("amount"))
    except (TypeError, ValueError):
        raise ValueError(f"{pid}: narx noto'g'ri") from None
    if usd <= 0:
        raise ValueError(f"{pid}: narx noldan katta bo'lishi kerak")
    try:
        available = int((raw.get("availability") or {}).get("available") or 0)
    except (TypeError, ValueError):
        available = 0

    ptype = str(raw.get("productType") or "account")
    req = raw.get("purchaseRequirements") or {}
    need = "email" if req.get("customerEmail") else "accounts" if req.get("customerAccounts") else None
    fixed = req.get("quantityFixed")

    brand, domain, cat = detect_brand(name_en, str(raw.get("emoji") or ""))
    name, warranty = uz_name(name_en)
    name = _drop_cyrillic(name)
    warranty = warranty or raw_warranty(raw)
    if brand:        # «Capcut» → «CapCut», «chatgpt» → «ChatGPT»
        name = re.sub(rf"(?<![\w]){re.escape(brand)}(?![\w])", brand, name, flags=re.I)
    if brand in UNPOPULAR_BRANDS:
        reason = "Kerak emas brend (%s)" % brand
    elif is_blocked(name_en, str(raw.get("emoji") or "")):
        reason = "Taqiqlangan turdagi mahsulot"
    elif too_short(brand, name):
        reason = "Muddati juda qisqa"
    elif no_warranty_banned(brand, warranty):
        reason = "CapCut: kafolatsiz tariflar qo'yilmaydi"
    else:
        reason = curation.reject_reason(brand, name_en, warranty, duration_days(name)) or ""
    return {
        "external_id": PREFIX + pid,
        "name": name or name_en[:200],
        "usd": usd,
        "available": max(available, 0),
        "type": ptype,
        "need": need,
        "fixed_qty": int(fixed) if isinstance(fixed, int) and fixed > 0 else None,
        "brand": brand,
        "logo": domain,
        "category": cat,
        "warranty": warranty,
        "description": build_description(ptype, warranty, need),
        "blocked": bool(reason),
        "reason": reason,
        "name_en": name_en,
        "clean": naming.own_name(brand, name or name_en[:200], ptype),     # ta'minotchi so'zlarisiz nom (qoidalar/qo'llanma shundan o'qiydi)
        "title": naming.restyle(naming.own_name(brand, name or name_en[:200], ptype)),   # do'kondagi o'z uslubidagi nom
        "info": raw_texts(raw),
    }


# ─────────────────────────── Sinxronizatsiya ───────────────────────────

async def _category(s: AsyncSession, key: str, cache: dict) -> Category:
    if key in cache:
        return cache[key]
    name, emoji, order = CATEGORIES[key]
    cat = await s.scalar(select(Category).where(Category.name_uz == name))
    if not cat:
        for old in _LEGACY_CATEGORY_NAMES.get(key, []):
            cat = await s.scalar(select(Category).where(Category.name_uz == old))
            if cat:
                cat.name_uz = name
                break
    if not cat:
        cat = Category(emoji=emoji, name_uz=name, sort_order=order)
        s.add(cat)
        await s.flush()
    cache[key] = cat
    return cat


# Fon sinxronlashida mahsulot ro'yxatdan shuncha marta KETMA-KET tushib qolsagina yashiriladi
MISSING_GRACE = 2
# Ro'yxat oldingi faol mahsulotlarning shu ulushidan kam bo'lsa — ta'minotchi javobi gumon (xato yoki
# vaqtincha noto'liq), hech narsa yashirilmaydi
SUSPICIOUS_RATIO = 0.5
_missing: dict[str, int] = {}


async def sync(s: AsyncSession, items: list[dict] | None = None, auto: bool = False):
    """Katalogni ta'minotchidan olib bazaga yozadi. catalog_sync.SyncResult qaytaradi.

    auto=True (har 3 daqiqada fonda) — ehtiyotkor rejim: ro'yxatdan bir marta tushib qolgan mahsulot
    darhol yashirilmaydi va gumon darajada qisqa ro'yxat qabul qilinmaydi. Qo'lda /sync — darhol.
    """
    from services.catalog_sync import SyncResult

    result = SyncResult()
    if items is None:
        items = await fetch_products()
    if not items:
        result.errors.append("Ta'minotchi bo'sh ro'yxat qaytardi — hech narsa o'zgartirilmadi")
        return result

    rate = await usd_rate()
    existing = {
        p.external_id: p
        for p in await s.scalars(
            select(Product).where(Product.source == ProductSource.API, Product.external_id.like(PREFIX + "%"))
        )
    }
    cats: dict = {}
    seen: set[str] = set()
    now = datetime.utcnow()
    first_run = not existing        # bo'sh bazaga birinchi yuklash — hech kimga «yangi» xabari bormaydi
    fresh: list[Product] = []       # yangi qo'shilganlar (id flush'dan keyin ma'lum bo'ladi)
    restocked: list[tuple[Product, int, int]] = []

    force = runtime.api_force()            # admin qo'lda qo'shgan mahsulotlar: qoidalarga qaramasdan chiqadi
    catalog: dict[str, dict] = {}          # admin «API'dan qo'shish» ekrani uchun
    for raw in items:
        try:
            it = parse_item(raw)
        except ValueError as ex:
            result.skipped += 1
            result.errors.append(str(ex))
            continue
        forced = it["external_id"] in force
        reason = it["reason"]
        if not reason and not forced and it["brand"] not in curation.BASE_BRANDS and it["brand"] not in curation.EXTRA_BRANDS:
            reason = "Do'kon menyusida bu brend yo'q (qo'shsangiz paydo bo'ladi)"
        shown = forced or not reason
        mine = existing.get(it["external_id"])
        if mine is not None and "hidden" in overrides.locked(mine):
            shown, reason = False, reason or "Admin olib tashlagan"
        catalog[it["external_id"]] = {
            "name": it["title"], "raw": it["name_en"], "usd": it["usd"], "brand": it["brand"] or "", "warranty": it["warranty"],
            "available": it["available"], "shown": shown, "reason": reason, "price": 0, "info": it.get("info") or [],
        }
        if it["blocked"] and not forced:
            result.skipped += 1
            continue
        if it["external_id"] in seen:
            continue
        seen.add(it["external_id"])

        supplier_price, price = sell_price_uzs(it["usd"], rate, it["name"], it["brand"], it["warranty"])
        catalog[it["external_id"]]["price"] = price
        cat = await _category(s, it["category"], cats)
        product = existing.get(it["external_id"])
        hold = False
        if product is not None:         # ta'minotchi narxi oshsa — bizniki sakramaydi (foyda ≤ +5 000 so'm)
            price, hold = decide_price(product.price, product.supplier_price, product_meta(product),
                                       it["usd"], supplier_price, price, pricing_policy())
        meta = json.dumps(
            {"type": it["type"], "need": it["need"], "fixed_qty": it["fixed_qty"],
             "warranty": it["warranty"], "usd": it["usd"], "pol": pricing_policy(), "hold": hold, "raw": it["name_en"], "uz": it["clean"]},
            ensure_ascii=False,
        )
        fields = {
            "category_id": cat.id, "emoji": CATEGORIES[it["category"]][1], "name": it["title"],
            "description": it["description"], "price": price, "supplier_price": supplier_price,
            "stock_qty": it["available"], "brand": it["brand"] or None, "logo": it["logo"] or None,
            "supplier_data": meta, "is_active": it["available"] > 0,
        }
        if product is None:
            new_p = Product(
                delivery_type=DeliveryType.MANUAL, unlimited=False, source=ProductSource.API,
                external_id=it["external_id"], image_url=None, synced_at=now, **fields,
            )
            s.add(new_p)
            result.created += 1
            if fields["is_active"] and not first_run:
                fresh.append(new_p)
            continue
        lock = overrides.locked(product)
        if "hidden" in lock:
            fields["is_active"] = False
        old_stock = (product.stock_qty or 0) if product.is_active else 0
        old_price, old_supplier = product.price, product.supplier_price
        changed = False
        for attr, value in fields.items():
            if attr in lock:          # admin qo'lda o'zgartirgan maydon (narx, nom, tavsif, emoji)
                continue
            if getattr(product, attr) != value:
                setattr(product, attr, value)
                changed = True
        if old_price and product.price != old_price:
            s.add(PriceChange(product_id=product.id, product_name=product.name, old_price=old_price,
                              new_price=product.price, old_supplier=old_supplier,
                              new_supplier=product.supplier_price, source="sync"))
            result.price_changes.append({"id": product.id, "name": product.name, "old": old_price, "new": product.price})
        if auto and product.is_active and "hidden" not in lock and (product.stock_qty or 0) > old_stock:
            restocked.append((product, old_stock, product.stock_qty or 0))
        if changed:
            product.synced_at = now      # o'zgarmagan qatorga tegmaymiz — har 3 daqiqada bazani qayta yozmaslik uchun
        result.updated += changed
        result.unchanged += not changed

    curation.CATALOG.clear()
    curation.CATALOG.update(catalog)

    # Ro'yxatdan chiqqan yoki endi filtrdan o'tmaydigan mahsulotlar — o'chirilmaydi, yashiriladi
    for ext_id in seen:
        _missing.pop(ext_id, None)
    active = [e for e, p in existing.items() if p.is_active]
    soldout = [e for e, p in existing.items() if not p.is_active and p.stock_qty == 0]   # ta'minotchida bor, lekin tugagan
    gone = [e for e in active + soldout if e not in seen]
    if auto and len(active) >= 10 and len(seen) < SUSPICIOUS_RATIO * len(active):
        log.warning("canboso: ro'yxat gumon darajada qisqa (%d / %d) — hech narsa yashirilmadi", len(seen), len(active))
        result.errors.append("Ta'minotchi ro'yxati gumon darajada qisqa — mahsulotlar yashirilmadi")
        gone = []
    for ext_id in gone:
        if auto:
            _missing[ext_id] = _missing.get(ext_id, 0) + 1
            if _missing[ext_id] < MISSING_GRACE:
                continue                 # birinchi marta tushib qoldi — bir oz kutamiz
        _missing.pop(ext_id, None)
        product = existing[ext_id]
        product.is_active = False
        product.stock_qty = None         # ro'yxatdan chiqqan: do'konda ko'rsatilmaydi (0 — «ta'minotchida bor, lekin tugagan»)
        result.deactivated += 1

    await s.execute(delete(PriceChange).where(PriceChange.created_at < now - timedelta(days=30)))
    await s.commit()
    if auto:
        result.events = notify_events(fresh, restocked)
    log.info("canboso: +%d ~%d =%d -%d (tashlandi %d), kurs %.2f",
             result.created, result.updated, result.unchanged, result.deactivated, result.skipped, rate)
    return result


def notify_events(fresh: list[Product], restocked: list[tuple[Product, int, int]]) -> list[dict]:
    """Mijozlarga xabar beriladigan hodisalar. Faqat obuna turlari (API kalit/kreditlar emas), zaxira kamida
    runtime.notify_min() ta oshganda; bir mahsulotga COOLDOWN ichida ikkinchi marta yozilmaydi."""
    if not runtime.notify_enabled():
        return []
    now, min_add = time.time(), runtime.notify_min()
    out: list[dict] = []
    for p in fresh:
        if _notifiable(p) and _cooled(p.id, now):
            out.append({"id": p.id, "kind": "new", "added": p.stock_qty or 0, "stock": p.stock_qty or 0})
    for p, old, new in restocked:
        if (old == 0 or new - old >= min_add) and _notifiable(p) and _cooled(p.id, now):
            out.append({"id": p.id, "kind": "restock", "added": new - old, "stock": new})
    for ev in out:
        _notified[ev["id"]] = now
    return out


NOTIFY_COOLDOWN = 30 * 60
_notified: dict[int, float] = {}


def _cooled(pid: int, now: float) -> bool:
    return now - _notified.get(pid, 0) >= NOTIFY_COOLDOWN


def _notifiable(p: Product) -> bool:
    return not re.search(r"\bAPI\b|kredit|credit|token", p.name or "", re.I)


async def reprice_all(s: AsyncSession) -> int:
    """Foyda foizi yoki kurs o'zgarganda narxlarni darhol qayta hisoblaydi (API so'rovisiz).

    Admin qo'lda narx qo'ygan mahsulotlarga tegilmaydi.
    """
    rate = await usd_rate()
    n = 0
    for p in await s.scalars(
        select(Product).where(Product.source == ProductSource.API, Product.external_id.like(PREFIX + "%"))
    ):
        usd = product_meta(p).get("usd")
        if not usd or "price" in overrides.locked(p):
            continue
        # narx qoidalari sodda nomdan o'qiydi («Kling Standard 1 oy»), do'kondagi ko'rinishdan emas («… · 1 oylik»)
        supplier_price, price = sell_price_uzs(float(usd), rate, plain_name(p), p.brand or "", product_meta(p).get("warranty"))
        meta = product_meta(p)
        price, hold = decide_price(p.price, p.supplier_price, meta, float(usd), supplier_price, price, pricing_policy())
        meta["pol"], meta["hold"] = pricing_policy(), hold
        p.supplier_data = json.dumps(meta, ensure_ascii=False)
        if p.price != price or p.supplier_price != supplier_price:
            p.price, p.supplier_price = price, supplier_price
            n += 1
    await s.commit()
    return n


# ─────────────────────────── Xarid ───────────────────────────

def product_meta(product: Product) -> dict:
    try:
        return json.loads(product.supplier_data or "{}")
    except ValueError:
        return {}


def search_name(product: Product) -> str:
    """Qoidalar va qo'llanmalar uchun matn: do'kondagi nom + ta'minotchining asl (inglizcha) nomi."""
    meta = product_meta(product)
    return f"{product.name or ''} {meta.get('uz', '')} {meta.get('raw', '')}"


def plain_name(product: Product) -> str:
    """Muddat/kredit/brend kabilarni nomdan o'qish uchun: «Brend Tarif 1 oy (kod)» ko'rinishidagi sodda nom (do'kon uslubisiz)."""
    return product_meta(product).get("uz") or product.name or ""


def is_supplier_product(product: Product) -> bool:
    return product.source == ProductSource.API and (product.external_id or "").startswith(PREFIX)


_LABELS = {"user": "Login", "password": "Parol", "verifyEmail": "Tasdiqlash emaili", "email": "Email",
           "code": "Kod", "key": "Kalit", "link": "Havola", "url": "Havola", "token": "Token",
           "note": "Izoh", "twoFA": "2FA", "2fa": "2FA"}


def _fmt_entry(x) -> str:
    if isinstance(x, dict):
        return "\n".join(f"{_LABELS.get(k, k)}: {v}" for k, v in x.items() if v not in (None, ""))
    return str(x)


def format_delivery(delivery) -> str:
    """Ta'minotchi bergan ma'lumotni (akkauntlar, kodlar...) o'qiladigan matnga aylantiradi."""
    if not delivery:
        return ""
    if isinstance(delivery, (str, int, float)):
        return str(delivery)
    parts: list[str] = []
    for key, val in delivery.items():
        if isinstance(val, list):
            parts += [e for e in (_fmt_entry(x) for x in val) if e]
        elif isinstance(val, dict):
            parts.append(_fmt_entry(val))
        elif val not in (None, ""):
            parts.append(f"{_LABELS.get(key, key)}: {val}")
    return "\n\n".join(parts)


@dataclass
class PurchaseResult:
    kind: str                # "ok" | "failed" | "unknown"
    content: str = ""
    message: str = ""
    completed: bool = False  # ta'minotchi buyurtmani tugatdimi (slot/upgrade'lar keyinroq)
    order_code: str = ""


async def purchase(
    external_id: str, quantity: int, idempotency_key: str,
    email: str | None = None, accounts: list[str] | None = None,
) -> PurchaseResult:
    """Ta'minotchidan xarid qiladi.

    "failed"  — xarid O'TMAGAN, pulni qaytarish xavfsiz.
    "unknown" — natija noma'lum (tarmoq uzildi / jarayonda) — pulni qaytarmang,
                adminga xabar bering, Idempotency-Key bilan qayta tekshirish mumkin.
    """
    body: dict = {
        "key": settings.canboso_api_key,
        "product_id": external_id[len(PREFIX):] if external_id.startswith(PREFIX) else external_id,
        "quantity": quantity,
    }
    if email:
        body["customer_email"] = email
    if accounts:
        body["customer_accounts"] = accounts

    last_err = ""
    for attempt in range(3):           # bir xil kalit bilan qayta yuborish xavfsiz
        try:
            status, data, _ = await _request(
                "POST", "purchase", json_body=body, headers={"Idempotency-Key": idempotency_key}
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
            last_err = _mask(str(ex)) or type(ex).__name__
            await asyncio.sleep(2 * (attempt + 1))
            continue

        msg = (data or {}).get("message", "") if isinstance(data, dict) else ""
        if status == 200 and isinstance(data, dict) and data.get("success"):
            order = data.get("order") or {}
            content = format_delivery(data.get("delivery"))
            return PurchaseResult(
                "ok", content=content, completed=str(order.get("status")) == "completed" and bool(content),
                order_code=str(order.get("orderCode") or ""),
            )
        if status == 409 and "progress" in msg.lower():
            last_err = msg
            await asyncio.sleep(2 * (attempt + 1))
            continue
        if status in (400, 401, 404, 409, 429, 503):
            return PurchaseResult("failed", message=msg or f"Ta'minotchi xatosi ({status})")
        last_err = f"HTTP {status} {msg}".strip()
        await asyncio.sleep(2 * (attempt + 1))

    return PurchaseResult("unknown", message=last_err or "javob kelmadi")
