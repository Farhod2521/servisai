"""Ta’minotchi (canboso) mahsulotlarini tahlil qilish: o‘zbekcha nom, brend, logotip domeni, kategoriya, kafolat.

ServesAI botidagi services/canboso.py dan ko‘chirilgan (bot va sayt bir xil nom/qoidalardan foydalansin).
Tarmoq, narx va xarid — supplier/client.py da.
"""
from __future__ import annotations

import re

from . import naming

PREFIX = "cb:"                 # external_id prefiksi (bot bilan bir xil)


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
        reason = ""
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




# ─────────────────────────── API paketlar (botdagi services/curation.py) ───────────────────────────

def is_api(brand: str, name_en: str) -> bool:
    """API paketmi: nomida «API»; ChatGPT uchun «Codex» ham."""
    return bool(re.search(r"\bapi\b", name_en or "", re.I)) or (brand == "ChatGPT" and bool(re.search(r"\bcodex\b", name_en or "", re.I)))
