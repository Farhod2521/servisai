"""Mahsulot qo'llanmasi: admin yozmagan bo'lsa, mahsulot turiga qarab tayyor matn beriladi.

Admin panelda («📖 Qo'llanma») yozilgan matn har doim ustun. Har qator — alohida qadam.
"""
from __future__ import annotations

import re

from database.models import Product
from services import ai_guides, canboso, pricing

# Brend → (xizmat sayti, kirgach nimani tekshirish kerak)
_SITES: dict[str, tuple[str, str]] = {
    "Codex": ("chatgpt.com", "Hisobingizda balans va API kalitlar ko'rinadi"),
    "ChatGPT": ("chatgpt.com", "Yuqori burchakdagi profilingizda «Plus» (yoki «Pro») yozuvi chiqadi, modellar ro'yxati kengayadi"),
    "Claude": ("claude.ai", "Profilingizda «Pro» (yoki «Max») tarifi ko'rinadi, xabarlar limiti oshadi"),
    "Gemini": ("gemini.google.com", "Gemini oynasida «Google AI Pro» (yoki Ultra) yozuvi va qo'shimcha modellar chiqadi"),
    "Grok": ("grok.com", "Profilingizda «SuperGrok» tarifi ko'rinadi, so'rovlar limiti oshadi"),
    "Perplexity": ("perplexity.ai", "Profilingizda «Pro» belgisi chiqadi, Pro qidiruvlar ochiladi"),
    "Cursor": ("cursor.com", "Sozlamalarda (Settings → Account) «Pro» tarifi ko'rinadi"),
    "CapCut": ("capcut.com", "Profilingizda «Pro» (toj) belgisi chiqadi, pullik effekt va shablonlar ochiladi, suv belgisi (watermark) yo'qoladi"),
    "Canva": ("canva.com", "Profilingizda «Canva Pro» yozuvi chiqadi, pullik shablon va rasmlar ochiladi"),
    "Leonardo AI": ("app.leonardo.ai", "Yuqori o'ng burchakda kreditlar (tokenlar) soni ko'rinadi"),
    "ElevenLabs": ("elevenlabs.io", "Profil → Subscription bo'limida tarif va qolgan kreditlar (belgilar) ko'rinadi"),
    "Kling": ("klingai.com", "Yuqori burchakda kreditlar soni va tarifingiz ko'rinadi"),
    "Higgsfield": ("higgsfield.ai", "Profilingizda kreditlar soni va tarifingiz ko'rinadi"),
    "Seedance": ("dreamina.capcut.com", "Profilingizda kreditlar soni ko'rinadi"),
    "Dreamina": ("dreamina.capcut.com", "Profilingizda kreditlar soni ko'rinadi"),
    "Midjourney": ("midjourney.com", "Account sahifasida tarifingiz va tezkor (Fast) soatlaringiz ko'rinadi"),
    "Microsoft 365": ("office.com", "Account → Subscriptions bo'limida Microsoft 365 obunasi ko'rinadi"),
    "Spotify": ("spotify.com", "Hisob (Account) sahifasida «Premium» tarifi ko'rinadi, reklama yo'qoladi"),
    "Suno": ("suno.com", "Yuqori burchakda kreditlaringiz soni ko'rinadi"),
    "Runway": ("runwayml.com", "Hisobingizda kreditlar va tarif ko'rinadi"),
    "HeyGen": ("heygen.com", "Hisobingizda kreditlar va tarif ko'rinadi"),
    "Duolingo": ("duolingo.com", "Profilingizda «Super» belgisi chiqadi, reklama yo'qoladi"),
    "Notion": ("notion.so", "Settings → Plans bo'limida tarifingiz ko'rinadi"),
    "Grammarly": ("grammarly.com", "Hisobingizda «Premium» tarifi ko'rinadi"),
}


def _site(p: Product) -> tuple[str, str]:
    brand = p.brand or ""
    site, check = _SITES.get(brand, ("", ""))
    if not site and p.logo:
        site = p.logo
    return site, check or "Hisobingizda yangi tarif yoki kreditlar ko'rinadi"


def _kind(name: str) -> str:
    n = (name or "").lower()
    if re.search(r"\bapi\b|api\s*kalit", n):
        return "api"
    if re.search(r"kredit|credit|token|\bball\b", n):
        return "credits"
    return "sub"


def _where(site: str, brand: str) -> str:
    return f"{site} saytiga (yoki {brand} ilovasiga)" if site else f"{brand or 'xizmat'} saytiga yoki ilovasiga"


_FAIR = "Parol, email yoki 2FA ni o'zgartirmang va akkauntni boshqalarga bermang — kafolat shunda amal qiladi"


def _specific(p: Product, ptype: str, name: str) -> list[str] | None:
    """Brend va mahsulot xiliga mos aniq qo'llanma (ta'minotchi tavsiflaridan olingan). Topilmasa None."""
    brand = p.brand or ""
    n = name.lower()

    if brand == "Gemini" and ptype == "upgrade_account":
        return [
            "Sotib olishda Gmail akkauntingiz emailini kiriting — shu akkaunt yangilanadi",
            "Buyurtma qo'lda bajariladi, holatini «Buyurtmalar» bo'limida ko'rasiz",
            "Tayyor bo'lgach gemini.google.com ga shu Gmail bilan kiring va «Google AI Pro» chiqqanini tekshiring",
            "Karta ulash shart emas",
        ]
    if brand == "Gemini" and ptype == "account" and not re.search(r"\bapi\b", n):
        return [
            "Xariddan so'ng rasmiy yangilash havolasi shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "Yangilamoqchi bo'lgan Gmail akkauntingizga kiring (shu brauzerda ochiq tursin)",
            "Havolani oching va «Tasdiqlash» (Confirm) tugmasini bosing — paket faollashadi",
            "gemini.google.com da «Google AI Pro» paketi chiqqanini tekshiring. Karta ulash shart emas",
            "Xariddan so'ng darhol faollashtiring: kafolat faqat belgilangan qisqa muddat ichida amal qiladi",
            "Paket bilan Family (oila)ga yana 5 tagacha a'zoni taklif qilish mumkin",
        ]

    if brand == "ChatGPT" and ptype == "account" and "k12" in n:
        return [
            "Xariddan so'ng akkaunt, parol va 2FA kaliti shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "Berilgan yo'riqnoma bo'yicha Workspace (jamoa)ga o'zingiz qo'shilasiz — yo'riqnomani diqqat bilan o'qing",
            "chatgpt.com ga kiring: «Email bilan kirish» ni tanlang, email va parolni kiriting",
            "Tasdiqlash kodi so'ralsa: 2fa.page saytiga o'ting, 2FA kalitini qo'ying — chiqqan kodni (OTP) kiriting. Kod vaqt o'tishi bilan yangilanadi",
            "Ayrim akkauntlarda 2FA yoqilmagan bo'ladi — shunchaki yoqib qo'ying",
            _FAIR,
        ]
    if brand == "Leonardo AI" and ptype == "account":
        steps = [
            "Xariddan so'ng email, Hotmail paroli va token shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "app.leonardo.ai ga o'ting, berilgan email bilan «Continue with Canva» (Canva orqali kirish) ni tanlang",
            "Pochta kodi so'ralsa, token havolasidan tez olasiz; xato chiqsa Outlook saytidan o'zingiz kirib kodni ko'ring",
        ]
        if "8500" in n:
            steps.append("8500 kredit taxminan 60 ta rasm (Nano Banana Pro) yoki 4–5 ta video (15 soniya) uchun yetadi — sarf model va sozlamaga bog'liq")
        return steps + ["Akkaunt ma'lumotlarini o'zgartirmang va boshqalarga bermang — xato chiqishi mumkin"]

    if brand == "ElevenLabs":
        if "redeem" in n:
            return [
                "Xariddan so'ng rasmiy kod emailingizga yuboriladi (shu yerda ham chiqadi)",
                "Kodni xariddan keyin 7 kun ichida ishlating — keyin kuchini yo'qotishi mumkin",
                "elevenlabs.io da akkauntingizga kiring va kodni faollashtirish bo'limiga kiriting",
                "Hisobingizda Creator tarifi va kreditlar chiqqanini tekshiring",
            ]
        if "elevenreader" in n:
            return [
                "Xariddan so'ng sovg'a havolasi shu yerda va botda chiqadi",
                "Havolani oching, ElevenReader akkauntingizga kiring va faollashtiring",
                "Ilovada Ultra tarifi chiqqanini tekshiring",
            ]

    if brand == "Grok" and re.search(r"\(kod\)|\bkod\b", n):
        return [
            "Xariddan so'ng kod (CDK) va to'ldirish (top-up) sayti shu yerda va botda chiqadi",
            "Akkauntingiz BEPUL tarifda bo'lishi kerak. Obunasi bor (Lite, Super, Heavy) akkauntga kodni ishlatmang",
            "To'ldirish saytiga o'ting, kodni kiriting. Sayt so'rasa, cookie oling: grok.com ga kiring → sichqonchaning o'ng tugmasi → «Inspect» → «Application» → «Cookies» → «sso-rw»",
            "Faollashish taxminan 5 daqiqa oladi — sabr qiling. Bitta akkauntga 2 ta kod ishlatmang",
            "15 daqiqada paket chiqmasa — darhol «Yordam»ga yozing",
        ]
    if brand == "Grok" and ptype == "account" and not re.search(r"\bapi\b", n):
        return [
            "Xariddan so'ng Hotmail akkaunti va Grok paroli shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "grok.com ga kiring va berilgan ma'lumot bilan tizimga kiring",
            "Paketingiz hisobda chiqqanini tekshiring",
            _FAIR,
        ]

    return None


def default_guide(p: Product) -> str:
    """Ta'minotchi mahsuloti uchun brend va turiga mos qo'llanma; boshqa mahsulotlarga bo'sh.

    Har qator — alohida qadam. Admin «📖 Qo'llanma» da o'zi yozsa, o'sha ustun.
    """
    if not canboso.is_supplier_product(p):
        return ""
    meta = canboso.product_meta(p)
    ptype = meta.get("type") or "account"
    brand = p.brand or "xizmat"
    site, check = _site(p)
    kind = _kind(canboso.search_name(p))
    where = _where(site, brand)

    spec = ai_guides.specific(p, ptype, meta)            # AI obunalar: ta'minotchi tavsifiga asoslangan oddiy qo'llanma
    if spec:
        return "\n".join(spec)
    if kind != "api":
        spec = _specific(p, ptype, canboso.search_name(p))
        if spec:
            return "\n".join(spec)

    if kind == "api":
        steps = [
            "Xariddan so'ng API kalit (key) shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "Kalitni dasturingiz, bot yoki ilovangizdagi «API key» maydoniga qo'ying",
            "Kalitni hech kimga ko'rsatmang va ochiq joyga (GitHub, chat) yozmang — undagi mablag' tez tugab qoladi",
            "Qancha ishlatganingizni xizmatning o'z sahifasida (Usage / Billing) kuzatib boring",
        ]
    elif ptype == "slot":
        steps = [
            f"Sotib olishda {brand} da ishlatadigan emailingizni to'g'ri kiriting — xato yozsangiz taklif boshqa odamga ketadi",
            "Bir necha daqiqada emailingizga taklif (invite) keladi — «Spam» papkasini ham tekshiring",
            f"Taklifni qabul qiling va {where} o'sha email bilan kiring",
            check,
        ]
    elif ptype == "upgrade_account":
        steps = [
            f"Sotib olishda {brand} akkauntingizning emailini (yoki loginini) kiriting. Akkaunt oldindan ochilgan bo'lishi kerak",
            "Akkauntingiz o'zingizniki bo'lib qoladi — parolingizni chatda yoki boshqalarga yubormang",
            "Buyurtma qo'lda bajariladi, odatda bir necha daqiqada tayyor bo'ladi — holatini «Buyurtmalar» bo'limida ko'rasiz",
            f"Tayyor bo'lgach {where} kiring (kerak bo'lsa chiqib qayta kiring). {check}",
        ]
    else:
        steps = [
            "Xariddan so'ng login va parol shu yerda va botda chiqadi — nusxalash tugmasi bor",
            f"Kirish uchun {where} o'tib, shu login va parol bilan kiring",
            check,
            "Parol va emailni o'zgartirmang, akkauntni boshqalarga bermang va bir vaqtda ko'p qurilmadan kirmang — kafolat shunda amal qiladi",
        ]

    if kind == "credits" and ptype != "slot":
        steps.append("Kreditlar akkauntingizga qo'shiladi: har bir rasm, video yoki ovoz yaratish ma'lum miqdor kredit sarflaydi")
    return "\n".join(x for x in steps if x)


# Ta'minotchi tavsifida kafolat shartlari nomdagidan farq qiladigan brendlar (Leonardo: nomda 12H, tavsifda «10 daqiqa»):
# kafolat mahsulotda yozilmaydi — xariddan keyin buyurtmada aniq matn bilan chiqadi
WARRANTY_AFTER_PURCHASE_ONLY = {"Leonardo AI"}
AFTER_PURCHASE_HOURS = {"Leonardo AI": 10 / 60}      # tavsifdagi haqiqiy muddat (10 daqiqa)
AFTER_PURCHASE_NOTE = {
    "Leonardo AI": "Akkaunt olingandan keyin 10 daqiqa ichida kirishda xato chiqsa «Yordam»ga yozing — akkauntni almashtirib beramiz. "
                   "Olgan zahoti kirib tekshiring; ma'lumotlarni o'zgartirmang.",
}

# Havola orqali beriladigan mahsulotlarda havolaga beriladigan kafolat do'kon siyosati bo'yicha shu soatdan oshmaydi
LINK_WARRANTY_CAP_H = {"Gemini": 12}


def _fmt_hours(h: float) -> str:
    return f"{int(h)} soat" if h < 24 else f"{int(round(h / 24))} kun"


def _is_linklike(p: Product, meta: dict) -> bool:
    """Login-parol emas, balki havola / kod / akkauntni yangilash bo'lgan mahsulotmi."""
    n = canboso.search_name(p).lower()
    return (meta.get("type") in ("upgrade_account", "slot") or "(kod)" in n
            or (p.brand == "Gemini" and meta.get("type") == "account" and not re.search(r"\bapi\b", n)))


def _duration(p: Product, w: str) -> str:
    """Kafolat muddati matni («12 soat»); do'kon cheklovi (havola uchun) hisobga olinadi. Muddat yo'q bo'lsa ''."""
    dur = re.sub(r"\s*(to'liq\s+)?kafolat$", "", w).strip()
    cap = LINK_WARRANTY_CAP_H.get(p.brand or "")
    h = pricing.warranty_hours(w)
    if cap and h and h > cap:
        return _fmt_hours(cap)
    return dur


def _sub_months(p: Product) -> int:
    m = pricing.months_of(canboso.plain_name(p))
    return int(m) if m and m >= 1 else 0


def warranty_hours(p: Product) -> float | None:
    """Kafolat necha soat (xariddan boshlab) — buyurtmada qolgan vaqtni ko'rsatish uchun. Muddat noma'lum («to'liq kafolat») bo'lsa None."""
    if not canboso.is_supplier_product(p):
        return None
    if p.brand in AFTER_PURCHASE_HOURS:
        return AFTER_PURCHASE_HOURS[p.brand]
    w = (canboso.product_meta(p).get("warranty") or "").strip()
    if not w or w == "kafolatsiz" or not re.search(r"\d", w):
        return None
    h = pricing.warranty_hours(w)
    cap = LINK_WARRANTY_CAP_H.get(p.brand or "")
    if h and cap and h > cap:
        h = float(cap)
    return h or None


def warranty_public(p: Product) -> str:
    """Xariddan OLDIN mahsulotda ko'rinadigan qisqa kafolat muddati («24 soat kafolat»).

    «Kafolatsiz» yozilmaydi. Tavsifi nomdan farq qiladigan brendlarda (Leonardo) — mahsulotda yo'q, xariddan keyin chiqadi.
    """
    if not canboso.is_supplier_product(p) or (p.brand or "") in WARRANTY_AFTER_PURCHASE_ONLY:
        return ""
    meta = canboso.product_meta(p)
    w = (meta.get("warranty") or "").strip()
    if w == "kafolatsiz":
        return ""
    dur = _duration(p, w) if w else ""
    months = _sub_months(p)
    if p.brand == "Gemini" and months:
        return (f"Havolaga {dur} · " if dur else "") + f"faollashgach {months} oy kafolat"
    return f"{dur} kafolat" if dur else ("To'liq kafolat" if w else "")


def warranty_note(p: Product) -> str:
    """XARIDDAN KEYIN buyurtmada ko'rsatiladigan kafolat matni: admin yozgani, bo'lmasa ta'minotchi muddatidan.

    Masalan «12 soat kafolat» → «12 soat ichida login va parollarni almashtirib olasiz, hech qanday muammo bo'lmaydi».
    """
    if (p.warranty_note or "").strip():
        return p.warranty_note.strip()
    if not canboso.is_supplier_product(p):
        return ""
    meta = canboso.product_meta(p)
    w = (meta.get("warranty") or "").strip()
    if not w or w == "kafolatsiz":
        return ""
    if p.brand in AFTER_PURCHASE_NOTE:
        return AFTER_PURCHASE_NOTE[p.brand]
    dur = _duration(p, w)
    months = _sub_months(p)
    if p.brand == "Gemini" and _is_linklike(p, meta):
        first = f"Havola xariddan so'ng {dur} ichida kafolatli — shu vaqtda ishlatib, Gemini'ni faollashtirib oling. " if dur else ""
        after = (f"Faollashgandan keyin {months} oy davomida kafolat amal qiladi: muammo bo'lsa «Yordam»ga yozing."
                 if months else "Muammo bo'lsa «Yordam»ga yozing.")
        return first + after
    if _is_linklike(p, meta):
        if not dur:
            return "Kafolat to'liq: faollashmasa yoki muammo chiqsa «Yordam»ga yozing — tuzatib yoki almashtirib beramiz."
        return (f"{dur} ichida paket faollashmasa yoki muammo chiqsa «Yordam»ga yozing — tuzatib yoki almashtirib beramiz. "
                "Xariddan so'ng darhol faollashtiring.")
    if p.brand == "ChatGPT":
        # ChatGPT hujjatida parol va 2FA ni o'zgartirmaslik aytilgan («hech narsani o'zgartirish shart emas»)
        keep = " Parol, email va 2FA ni o'zgartirmang — o'zgartirilsa kafolat bekor bo'ladi."
        if not dur:
            return "Kafolat to'liq: kirishda muammo chiqsa «Yordam»ga yozing — login va parolni almashtirib beramiz." + keep
        return (f"{dur} ichida kirishda yoki 2FA da muammo chiqsa «Yordam»ga yozing — login va parolni almashtirib beramiz, "
                "hech qanday muammo bo'lmaydi." + keep)
    if not dur:
        return "Kafolat to'liq: muammo bo'lsa login va parollarni almashtirib olasiz, hech qanday muammo bo'lmaydi."
    return f"{dur} ichida login va parollarni almashtirib olasiz, hech qanday muammo bo'lmaydi."


def has_video(p: Product) -> bool:
    return bool((p.guide_video or "").strip())


def guide_of(p: Product) -> str:
    return (p.guide or "").strip() or default_guide(p)
