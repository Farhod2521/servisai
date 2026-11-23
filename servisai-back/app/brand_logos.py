"""Brend logotiplari — botdagi (ServesAI bot) premium emojilarning rasmlari.

Botda har bir brend tugmasi oldida premium (custom) emoji turadi (obunabotga-main/services/brand_emoji.py).
Saytda ham aynan shu rasmlar ko‘rinishi uchun ularning rasmlari `app/static/brands/<slug>.<ext>` da saqlanadi
va `/api/media/brands/<slug>.<ext>` orqali beriladi. Rasm bo‘lmagan brendlar uchun sayt ikonkasi (favicon) ishlatiladi.
Telegram rasmlarni WEBP (ba’zan JPG) ko‘rinishida beradi.

Rasmlarni qayta yuklash (botda emoji o‘zgarsa yoki yangi brend qo‘shilsa — avval DEFAULT ga ID qo‘shing):

    python -m app.brand_logos          # TELEGRAM_BOT_TOKEN .env da bo‘lishi kerak
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx

from .logos import detect_format

STATIC_DIR = Path(__file__).resolve().parent / "static" / "brands"
URL_PREFIX = "/api/media/brands/"
EXTS = ("webp", "png", "jpg")

# Botdagi services/brand_emoji.py: DEFAULT bilan bir xil (kalit — brend nomi)
DEFAULT: dict[str, str] = {
    # AI
    "Runway": "5307723096952694039", "Canva": "5879982576671657703", "Wispr Flow": "6131833836796912125",
    "Xingtu": "6089237768494392246", "Cursor": "5821051862979189629", "Wink": "6113945650196388135",
    "Freepik": "6174771823150900241", "Gamma": "6082663389039961048", "HeyGen": "6318816857230942976",
    "Higgsfield": "6201693472731176318", "Kling": "5415751828073642505", "Lovable": "6104729848675050039",
    "Manus": "5821054787851919157", "Meitu": "6177045544477662408", "n8n": "6133957427541843855",
    "Perplexity": "5413586627685549158", "Replit": "6105050957609968229", "Suno": "6174584936238947057",
    "Seedance": "5312300458348404781", "Krea": "6321094100430905243", "MiniMax": "6320826657112333009",
    "LartAI": "6147415948082028679", "Qwen": "6059962850498061099", "Kiro": "6060152885621042974",
    "DeepSeek": "6057569608821384517", "ElevenLabs": "5305733994518700539", "Gemini": "5440706056214840396",
    "Grok": "5440892071248431491", "Google VEO": "6134416752819314261", "Claude": "5417984549642601364",
    "ChatGPT": "5246801734638002426", "OpenArt": "6107275003344985788", "Leonardo AI": "6133975818591805751",
    "AI vosita": "6165465672697521810", "Flux": "6165465672697521810", "Clico": "6145211659196572254",
    "DomoAI": "6138877905284898645",
    # Boshqalar
    "Adobe": "6276039919265651685", "Apple Music": "5796444659605574073", "Autodesk": "6305045014531548800",
    "Discord": "5325612636467903082", "Duolingo": "6127504264949408331", "ExpressVPN": "5796153709931009517",
    "Figma": "6127461826377556681", "Quizlet": "6131880321227957937", "HMA VPN": "5796595022115639741",
    "iCloud": "5334955749409834455", "Kahoot": "6129601746588149417", "Kaspersky": "6305455256922758411",
    "GPM Login": "6165960702038122420", "Telegram": "6273877888563421002", "NordVPN": "6174491980261763426",
    "Notion": "5244973676297742666", "Zoom": "6132003848782356725", "Proton": "6303011025394344346",
    "Railway": "6131830684290916405", "Scribd": "6307417520106117902", "Spotify": "5233578612665375810",
    "LinkedIn": "4994784929293271632", "Grammarly": "6145718546941878479", "Surfshark": "6176797656145206338",
    "AdGuard": "6168099638701204037", "Xbox": "5366104999724072406", "iQIYI": "6165677491894624269",
    "Hotspot Shield": "6165844995619170591", "IPVanish": "6167910724564690649", "Coursera": "5821240446403223107",
    "Locket": "6323518738318502361", "Udemy": "6165898059940111443", "Microsoft 365": "6129901376391618660",
    "YouTube": "6089144773862497399", "CapCut": "5246889012668426695",
    # Botda Codex / ChatGPT API mahsulotlari ChatGPT belgisi bilan chiqadi
    "Codex": "5246801734638002426",
}


def slug(brand: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", brand.lower()).strip("-") or "brand"


def logo_url(brand: str) -> str | None:
    """Brendning botdagi logotipi (rasm fayli bo‘lsa) yoki None."""
    if not brand:
        return None
    for ext in EXTS:
        name = f"{slug(brand)}.{ext}"
        if (STATIC_DIR / name).is_file():
            return URL_PREFIX + name
    return None


def is_auto_logo(url: str | None) -> bool:
    """Sinxronlash o‘zi qo‘ygan logo (admin yuklagani emas) — keyingi sinxronlashda yangilanishi mumkin."""
    return not url or url.startswith(URL_PREFIX) or url.startswith("/api/media/logos/brand-")


async def download(token: str) -> int:
    """Telegram Bot API orqali har bir emojining rasmini (thumbnail, WEBP) yuklab oladi."""
    api = f"https://api.telegram.org/bot{token}"
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30) as http:
        ids = sorted(set(DEFAULT.values()))
        resp = (await http.post(f"{api}/getCustomEmojiStickers", json={"custom_emoji_ids": ids})).json()
        if not resp.get("ok"):
            raise SystemExit(f"Telegram xatosi: {resp.get('description')}")
        files: dict[str, bytes] = {}
        for sticker in resp["result"]:
            thumb = sticker.get("thumbnail") or {}
            if not thumb.get("file_id"):
                continue
            info = (await http.get(f"{api}/getFile", params={"file_id": thumb["file_id"]})).json()
            path = (info.get("result") or {}).get("file_path")
            if path:
                files[sticker["custom_emoji_id"]] = (await http.get(f"https://api.telegram.org/file/bot{token}/{path}")).content
    saved = 0
    for brand, cid in DEFAULT.items():
        data = files.get(cid)
        ext = detect_format(data or b"")
        if ext:
            for old in EXTS:
                (STATIC_DIR / f"{slug(brand)}.{old}").unlink(missing_ok=True)
            (STATIC_DIR / f"{slug(brand)}.{ext}").write_bytes(data)
            saved += 1
        else:
            print(f"! {brand}: rasm olinmadi")
    return saved


if __name__ == "__main__":
    from .config import settings

    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN .env da yo‘q")
    print(f"{asyncio.run(download(settings.telegram_bot_token))} ta logo saqlandi → {STATIC_DIR}")
