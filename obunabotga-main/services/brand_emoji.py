"""Brendlar uchun tayyor premium (custom) emoji ID lari.

Manba: bot egasi bergan ro'yxat (@TgEmojis botidan olingan ID lar). Bu ID lar umumiy
Telegram emoji to'plamlariga tegishli: bot egasida Telegram Premium bo'lsa, istalgan bot ularni ishlata oladi.

Ustuvorlik: admin panelda («🏷 Brend emojilari») saqlangan emoji → shu yerdagi tayyor ro'yxat → oddiy emoji.
Kalit — services/canboso.py dagi brend nomi.
"""
from __future__ import annotations

import re

from services import runtime

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
}

# ChatGPT API / Codex mahsulotlari uchun alohida belgi
CODEX_API = "5246801734638002426"
_API = re.compile(r"\bAPI\b|codex", re.I)


def emoji_id(brand: str | None, name: str = "") -> tuple[str | None, str | None]:
    """(custom_emoji_id, oddiy emoji yoki None). Admin saqlagani birinchi, keyin tayyor ro'yxat."""
    if not brand:
        return None, None
    own = runtime.brand_emoji().get(brand)
    if own and own.get("id"):
        return own["id"], own.get("char")
    if brand == "Codex" or (brand == "ChatGPT" and _API.search(name or "")):
        return CODEX_API, None
    return DEFAULT.get(brand), None
