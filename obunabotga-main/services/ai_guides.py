"""AI obunalar uchun oddiy o'zbekcha qo'llanmalar (ta'minotchi tavsiflari asosida, 2026-11-01).

Har qator — alohida qadam. Faqat ta'minotchi tavsifida yozilgan narsalar aytiladi: o'zimizdan havola yoki qadam o'ylab topilmaydi.
`specific(p, ptype, meta)` mos qo'llanma qatorlarini qaytaradi; mos kelmasa None (u holda umumiy qo'llanma ishlatiladi).
"""
from __future__ import annotations

import re

from database.models import Product
from services import curation

DOCS_VIBI = "https://vibi.top/docs-setup/vi"
USAGE_VIBI = "https://vibi.top/docs-setup/vi/usage"

# «Redeem kod → vibi.top → API kalit» usulidagi paketlar (Claude API, ChatGPT/Codex API: qo'llanma bir xil, faqat nom boshqa)
API_PACKAGE_BRANDS = {"Claude", "ChatGPT", "Codex"}
# Tayyor API kalit beriladigan paketlar (faollashtirish shart emas)
API_KEY_BRANDS = {"Gemini": "Gemini", "Grok": "Grok (xAI)"}

_API = re.compile(r"\bapi\b", re.I)


def _short_warranty(meta: dict, limit_days: float = 30) -> bool:
    d = curation.warranty_days((meta.get("warranty") or "").strip())
    return d is not None and d != float("inf") and d < limit_days


def api_package_steps(brand: str) -> list[str]:
    own = {"Claude": "Claude (Opus, Sonnet, Haiku)", "ChatGPT": "ChatGPT (GPT va Codex)", "Codex": "Codex (GPT)"}.get(brand, brand)
    return [
        "Xariddan so'ng faollashtirish kodi (redeem kod) shu yerda va botda chiqadi — nusxalash tugmasi bor",
        "vibi.top saytiga kiring va ro'yxatdan o'ting (akkauntingiz bo'lsa — shunchaki kiring)",
        "Saytda «Wallet» (hamyon) bo'limini bosing va kodni kiriting — mablag' hisobingizga tushadi",
        "«API Keys» bo'limiga o'tib, yangi kalit (key) yarating",
        "Kalitni dasturingiz, botingiz yoki ilovangizdagi «API key» maydoniga qo'ying",
        f"Bu bitta paket: {own} modellari asosiy, bundan tashqari boshqa mashhur modellar (GPT, Claude, DeepSeek, Qwen, GLM) ham bor — kerakligini o'zingiz tanlaysiz",
        f"Batafsil yo'riqnoma: {DOCS_VIBI}",
        "Kalitni hech kimga bermang va ochiq joyga (GitHub, chat) yozmang — undagi mablag' tez tugab qoladi",
    ]


def api_key_steps(brand: str) -> list[str]:
    label = API_KEY_BRANDS[brand]
    return [
        "Xariddan so'ng tayyor API kalit shu yerda va botda chiqadi — nusxalash tugmasi bor",
        "Kalitni to'g'ridan-to'g'ri dasturingiz yoki ilovangizdagi «API key» maydoniga qo'ying. Saytda faollashtirish yoki kodni o'zgartirish SHART EMAS",
        f"Bitta kalit bilan {label} ning bir nechta modellaridan foydalanasiz — kerakligini o'zingiz tanlaysiz",
        f"Qancha ishlatganingizni shu sahifada kuzatib boring: {USAGE_VIBI}",
        f"Batafsil yo'riqnoma: {DOCS_VIBI}",
        "Kalitni hech kimga bermang va ochiq joyga (GitHub, chat) yozmang — undagi mablag' tez tugab qoladi",
    ]


def specific(p: Product, ptype: str, meta: dict) -> list[str] | None:
    from services import canboso
    brand, n = p.brand or "", canboso.search_name(p).lower()
    is_api = bool(_API.search(n))

    # ── API paketlar ──
    if is_api and brand in API_PACKAGE_BRANDS:
        return api_package_steps(brand)
    if is_api and brand in API_KEY_BRANDS:
        return api_key_steps(brand)
    if is_api and brand == "Cursor":
        return [
            "Xariddan so'ng API kalit shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "Muddat kalitni FAOLLASHTIRGANINGIZDAN boshlab 1 oy; kreditlar shu muddat ichida ishlatiladi",
            "Bu akkaunt emas, API: xato sotib olingan bo'lsa pul qaytarilmaydi, ishlatish bo'yicha o'rgatilmaydi — faqat nima qilishni biladiganlar uchun",
            "Batafsil qo'llanma faylini «Yordam» orqali so'rang",
            "Kalitni hech kimga bermang va ochiq joyga yozmang",
        ]

    # ── Redeem kodlar (rasmiy kod / faollashtirish havolasi): kafolat faollashtirilgach yo'q ──
    if "redeem" in n and not is_api:
        stock_note = "Kod vaqtincha tugagan bo'lsa — buyurtma qabul qilinadi va kod emailingizga yuboriladi (xaridda email so'ralsa, to'g'ri yozing)"
        if brand == "Notion":
            return [
                "Xariddan so'ng rasmiy kod yoki faollashtirish havolasi shu yerda va botda chiqadi",
                "Havolani/kodni faqat o'zingiz faollashtirmoqchi bo'lgan Notion akkauntdan oching",
                "Faollashtirish uchun to'lov usuli (karta) so'raladi; oyiga 300 Notion Credits beriladi",
                stock_note,
                "Faollashtirilgandan keyin kafolat yo'q — kodni xariddan keyin darhol ishlating",
            ]
        if brand == "Perplexity":
            return [
                "Xariddan so'ng 12 oylik Pro paketning faollashtirish kodi (CDK) shu yerda va botda chiqadi",
                "Kodni o'zingiz o'z akkauntingizda faollashtirasiz. Kod faqat YANGI akkauntlar yoki Pro hech ishlatilmagan akkauntlar uchun",
                "Kodga 4000 kredit kirmaydi",
                stock_note,
                "Kod uchun kafolat yo'q: kod qotib qolsa yoki faollashtirishda muammo chiqsa ham qaytarilmaydi — xariddan oldin diqqat bilan o'qing",
            ]
        if brand == "Higgsfield":
            return [
                "Xariddan so'ng rasmiy chegirma kodi shu yerda va botda chiqadi (12 oy, oyiga 600 ball)",
                "Kod sizning akkauntingizga qo'llanadi: Higgsfield'ga kirib faollashtiring",
                "Kodni xariddan keyin 7 kun ichida ishlating — keyin kuchini yo'qotishi va almashtirib berilmasligi mumkin",
                stock_note,
                "Faollashtirilgandan keyin kafolat yo'q",
            ]
        if brand == "Runway":
            return [
                "Xariddan so'ng kupon (kod) shu yerda va botda chiqadi — darhol beriladi",
                "Kodni Runway akkauntingizda faollashtiring: paket 1 yil, har oy 2250 kredit beriladi",
                stock_note,
                "Faollashtirilgandan keyin kafolat yo'q",
            ]
        if brand == "Cursor" and ("bonus" in n or "grok" in n):
            return [
                "Xariddan so'ng havola shu yerda va botda chiqadi",
                "Cursor'da YANGI akkaunt oching (cursor.com) va xariddagi havola orqali shu akkauntga kiring — kredit avtomatik qo'shiladi",
                "Pro+ tarifga o'ting: 1 oy bepul (to'lov jarayonini yakunlash kerak bo'ladi)",
                "So'ng «Access Grok Bot» tugmasi orqali shu email bilan kiring va ko'rsatma bo'yicha Grok Bot'ni o'rnating",
                stock_note,
            ]

    # ── ChatGPT ──
    if brand == "ChatGPT" and re.search(r"pro \$?\s*500|pro \$500", n):
        steps = [
            "Xariddan so'ng akkaunt ma'lumoti shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "Bu rasmiy, pullik ro'yxatdan o'tgan ChatGPT Pro akkaunt (sinov emas) — chatgpt.com ga kiring",
            "Akkaunt buyurtma bo'yicha tayyorlanadi, shuning uchun yetkazish biroz kechikishi mumkin — sabr qiling",
        ]
        if _short_warranty(meta):
            steps.append("Kafolat qisqa bo'lgani uchun xariddan so'ng DARHOL 2FA ni o'zgartiring va barcha qurilmalardan chiqing — begona kirib olmasin. Aks holda kafolat berish qiyin bo'ladi")
        steps.append("Kafolat akkaunt xatolarini qoplaydi, lekin uchinchi tomon dasturlar yoki OpenAI qoidalarini buzish oqibatlarini QOPLAMAYDI")
        return steps
    if brand == "ChatGPT" and re.search(r"pro x\s*(100|200)", n):
        return [
            "Bu tayyor, oldindan faollashtirilgan akkaunt (iOS ilovasi orqali, asl egasi emas) — odatda 30 kun to'liq ishlaydi",
            "Buyurtma 30 daqiqadan 1 soatgacha (zaxira bo'lsa — darhol) bajariladi; mahsulot mashhur bo'lgani uchun ba'zan kechikadi",
            "Tayyor bo'lgach akkaunt ma'lumoti shu yerda va botda chiqadi — chatgpt.com ga kiring",
            "Kafolat uchinchi tomon dasturlar yoki OpenAI qoidalarini buzgan holatlarni QOPLAMAYDI",
        ]
    if brand == "ChatGPT" and (ptype == "slot" or "slot" in n):
        return [
            "Sotib olishda ChatGPT'da ishlatadigan emailingizni TO'G'RI yozing — Workspace taklifi shu emailga boradi",
            "Emailingizga taklif (invite) keladi — «Spam» papkasini ham tekshiring. Taklifni qabul qiling",
            "Xato email yozgan bo'lsangiz — xariddan 2 soat ichida «Yordam»ga yozing, to'g'rilab beramiz",
            "Pul tashlamagan yoki paketdan foydalanmoqchi bo'lmasangiz ham 2 soat ichida xabar bering",
            "Workspace barqaror ishlashi uchun akkauntni tez-tez qo'shish, o'chirish va almashtirish cheklangan. Limit tugagani uchun akkaunt almashtirib berilmaydi",
            "ChatGPT/Gmail akkaunt haqiqatan bloklansa — xato ekranini (skrinshot) «Yordam»ga yuboring, tekshirib beramiz",
        ]
    if brand == "ChatGPT" and ("biznes" in n or "business" in n) and ("umumiy" in n or "shared" in n):
        return [
            "Xariddan so'ng akkaunt (email va nom) shu yerda va botda chiqadi",
            "chatgpt.com ga shu email bilan kiring. Kirishda kod so'ralsa — u emailga boradi: kodni olish uchun «Yordam»ga (administratorga) yozing",
            "FAQAT 1 ta qurilmadan foydalaning; parol va 2FA ni o'zgartirmang — buzilsa kafolat bekor bo'ladi",
            "2 ta Workspace'ni birlashtirmang — kafolat bekor bo'ladi",
            "Codex ishlamaydi. Limit umumiy, shuning uchun ehtiyotkor ishlating",
            "Ma'lumotlar uchun kafolat yo'q: muhim narsalarni saqlab qo'ying, boshqalarning chat va loyihalarini o'chirmang",
            "Plus'dan kuchliroq: limitlar ko'proq, Pro model bor. Xizmat ko'rsatib bo'lmasa — pul qaytariladi",
        ]
    if brand == "ChatGPT" and ptype == "account" and not is_api and "k12" not in n:
        return [
            "Xariddan so'ng sizga email, parol va 2FA kaliti beriladi — shu yerda va botda chiqadi (nusxalash tugmasi bor)",
            "Kirishdan OLDIN OpenAI ning yangi qoidalarini o'qing: openai.com/policies — qoidani buzsangiz kafolat bekor bo'ladi",
            "chatgpt.com saytiga (yoki ChatGPT ilovasiga) kiring va «Email bilan kirish» (Log in with Email) ni tanlang",
            "Berilgan email va parolni kiriting",
            "ChatGPT tasdiqlash kodi (OTP) so'rasa: 2fa.page saytiga o'ting, berilgan 2FA kalitini (Secret) maydonga qo'ying — chiqqan kodni ChatGPT ga yozing",
            "Kod o'zi almashib turadi. Eskirib qolsa — 2fa.page ga qaytib, yangi kodni oling",
            "Parol va 2FA da xato yo'q (tekshirib berilgan) — ularni o'zgartirmang",
            "Codex ishlatmoqchi bo'lsangiz telefon raqamni tasdiqlash so'raladi: o'z raqamingizni yozing yoki raqam ijaraga beruvchi saytdan oling (arzon va oson)",
            "Kafolat sizning xatoingizga tegishli emas: 2FA ni o'zgartirish, noto'g'ri usul, uchinchi tomon dasturlar yoki Codex qoidalarini buzish",
        ]

    # ── Claude (oddiy obuna: akkauntni yangilash) ──
    if brand == "Claude" and ptype == "upgrade_account":
        return [
            "Sotib olishda Claude akkauntingiz ma'lumotini yozing: email | parol | 2FA (bo'lsa) — bir qatorda",
            "Akkaunt kamida 3 oy ishlatilgan bo'lishi kerak — yangi ochilgan akkaunt yoki uzoq ishlatilmagan akkaunt qabul qilinmaydi",
            "Tizim shaxsingizni tasdiqlashni so'rasa — buni o'zingiz bajarasiz",
            "Buyurtma ish vaqtida tezroq bajariladi; tayyor bo'lgach claude.ai ga kiring — tarif yangilangan bo'ladi",
            "Kafolat — obuna paketiga (7 kun). Bloklangan, cheklangan akkauntlar va platforma qoidalarini buzgan holatlarga kafolat yo'q",
        ]

    # ── Gemini ──
    if brand == "Gemini" and (ptype == "slot" or "slot" in n):
        return [
            "Sotib olishda Gmail akkauntingiz nomini (emailini) to'g'ri yozing — Google Family'ga taklif shu emailga boradi",
            "Taklif emailingizga (Gmail) keladi — «Spam» papkasini ham tekshiring. Taklifni qabul qiling: Gemini Pro va 5 TB Google One xotirasi ochiladi",
            "gemini.google.com ga shu Gmail bilan kiring va Pro paket chiqqanini tekshiring",
            "Paketda: tarjima, hujjatlarni qisqartirish, chuqur izlanish (Deep Research), rasm va video yaratish, NotebookLM, Gmail/Docs/Drive bilan ishlash bor",
            "Antigravity ham ishlatsa bo'ladi",
            "Karta ulash shart emas. Xato email yozsangiz taklif boshqa odamga ketadi — ehtiyot bo'ling",
        ]

    # ── Perplexity ──
    if brand == "Perplexity" and ptype == "upgrade_account":
        return [
            "Sotib olishda akkauntingiz ma'lumotini BIR QATORDA shu formatda yozing: login|parol|2fa (2FA bo'lmasa — oxirgisini yozmang)",
            "Magazin akkauntingizni Pro'ga yangilaydi — akkaunt o'zingizniki bo'lib qoladi",
            "Buyurtma qo'lda bajariladi — holatini «Buyurtmalarim» bo'limida ko'rasiz",
            "Tayyor bo'lgach perplexity.ai ga kiring: profilingizda «Pro» belgisi chiqadi",
        ]
    if brand == "Perplexity" and ptype == "account":
        return [
            "Bu tayyor Pro akkaunt — xariddan so'ng taxminan 30 daqiqa ichida beriladi",
            "Akkaunt ma'lumoti shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "perplexity.ai ga kiring: profilingizda «Pro» belgisi chiqadi",
            "Muammo chiqsa «Yordam»ga yozing — kafolat bor",
        ]

    # ── Grok ──
    if brand == "Grok" and "super" in n and ptype == "upgrade_account":
        return [
            "Sotib olishda akkaunt ma'lumotini yozing: email | grok paroli | 2FA (bo'lsa)",
            "Google orqali kirgan bo'lsangiz: avval Grok'dan chiqing va Grok parolini tiklab (reset) yangi parol qo'ying — aks holda akkauntga kirib bo'lmaydi",
            "Yuqori huquqli (admin) akkaunt kerak bo'lsa — buni sotib olishda yozib qoldiring",
            "Buyurtma 1–2 soatda bajariladi, odatda 30 kun to'liq ishlaydi (iOS orqali)",
            "Bu paket Cursor va Grok Super bitta (2 in 1). Kafolat — faqat xizmat paketiga (7 kun), qoida buzilsa kafolat yo'q",
        ]
    if brand == "Grok" and "premium" in n and "bot" in n:
        return [
            "Xariddan so'ng akkaunt ma'lumoti shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "Faqat ishlatish uchun: hech narsani o'zgartirmang",
            "Olgan zahotiyoq kirib tekshiring — o'zgargan joy bo'lsa darhol «Yordam»ga yozing",
        ]

    # ── Higgsfield ──
    if brand == "Higgsfield" and "genjutsu" in n and ptype == "account":
        return [
            "Xariddan so'ng 3 ta narsa beriladi: Higgsfield akkaunti, paroli va OTP havolasi — shu yerda va botda chiqadi",
            "higgsfield.ai ga akkaunt va parol bilan kiring. Kod (OTP) so'ralsa — berilgan OTP havolasini bosib, kodni oling",
            "Genjutsu videosini Motion yoki Swap rejimida yarating. Sifat 720p, video 30 soniyagacha",
            "Bitta video taxminan 20 daqiqa (yoki ko'proq) tayyorlanadi — sahifani yopmang. Juda uzoq cho'zilsa — sahifani yangilang (reload)",
            "Xariddan keyin videoni darhol yarating. Tayyorlanayotgan paytda bir necha marta bosmang — slotni yo'qotishingiz mumkin",
        ]

    # ── Notion ──
    if brand == "Notion" and ptype == "slot":
        return [
            "Sotib olishda Notion akkauntingizning emailini to'g'ri yozing — taklif (invite) shu emailga boradi",
            "Emailingizga (Notion'ga) do'kon Workspace'iga taklif keladi. «Spam» papkasini ham tekshiring",
            "Taklifni qabul qiling — siz Workspace a'zosi bo'lasiz va Business imkoniyatlaridan (AI bilan) foydalanasiz",
            "Muhim: Workspace umumiy. Muhim shaxsiy ma'lumotlaringizni u yerda SAQLAMANG — o'sha joydagi ma'lumotlarga kafolat yo'q",
            "AI limiti Workspace'dagi hamma uchun umumiy, shuning uchun bir kunda tugab qolishi mumkin",
            "Muddat tugagach uzaytirish uchun boshqa Workspace'ga o'tish kerak bo'ladi — fayllaringizni oldindan o'z akkauntingizga ko'chirib qo'ying",
            "Dasturlash (coding) uchun ishlatmang",
        ]
    if brand == "Notion" and ptype == "account":
        return [
            "Xariddan so'ng akkaunt ma'lumoti shu yerda va botda chiqadi (login | parol | email | ID | tiklash emaili)",
            "Kirgach DARHOL parolni o'zgartiring — akkauntni o'zingiznikiga qulflab oling",
            "Bu Education akkaunt (1 yil). Workspace'ni o'zingiz o'chirib yuborsangiz — kafolat qoplamaydi",
            "Kirishda xato chiqsa — akkaunt olingandan keyin 10 DAQIQA ichida «Yordam»ga yozing",
        ]

    # ── CapCut ──
    if brand == "CapCut" and ptype == "account":
        return [
            "Xariddan so'ng email va parol shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "Telefonda: CapCut ilovasida «Email bilan kirish» (Sign in with Email) ni tanlang",
            "Kompyuterda: avval telefonda kiring, keyin QR kodni skanerlang. iPhone: ilovada ME → Scan QR. Android: avval CapCut ni oxirgi versiyaga yangilang",
            "Akkauntni olgach darhol tekshiring. Profilingizda «Pro» belgisi chiqadi, pullik effektlar ochiladi, suv belgisi yo'qoladi",
            "Ko'pi bilan 2 ta qurilmadan kiring. Tez-tez kirib-chiqmang yoki ko'p qurilmadan kirmang — akkaunt buzilishi mumkin",
            "Kirish xatosi uchun oyiga 1 marta kafolat beriladi. Jamoa (Space) dan chiqmang va foydalanuvchi nomini o'zgartirmang",
        ]

    # ── ElevenLabs ──
    if brand == "ElevenLabs" and ("(kod)" in n or "redeem" in n or "code" in n):
        if "creator" in n:
            return [
                "Xariddan so'ng rasmiy faollashtirish kodi shu yerda va botda chiqadi (kerak bo'lsa emailingizga ham yuboriladi)",
                "Kodni xariddan keyin 7 kun ichida ishlating — keyin kuchini yo'qotishi va almashtirib berilmasligi mumkin",
                "elevenlabs.io da akkauntingizga kiring va kodni faollashtiring. Karta so'ralmaydi (ba'zi kodlarda)",
                "Ro'yxatdan o'tishda to'g'ri ma'lumot kiriting — uzoq muddat ishlatish uchun shu yaxshi",
                "Hisobingizda Creator tarifi va kreditlar chiqqanini tekshiring",
            ]
        return [
            "Xariddan so'ng faollashtirish kodi shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "Vibi.pro saytiga kiring va to'g'ri akkauntga kirganingizni tekshiring (kod faollashgach boshqa akkauntga o'tkazib bo'lmaydi)",
            "Kodni sayt ichidagi faollashtirish bo'limiga kiriting — kreditlar hisobingizga qo'shiladi",
            "Har bir kod faqat 1 marta ishlatiladi; faollashgandan keyin qaytarib yoki boshqa akkauntga o'tkazib bo'lmaydi",
            "Kreditlar oy oxirida kuymaydi — qolgani hisobingizda saqlanadi",
            "Kod ishlamasa yoki kredit noto'g'ri qo'shilsa — «Yordam»ga yozing",
        ]

    # ── Runway ──
    if brand == "Runway" and ptype == "upgrade_account":
        return [
            "Sotib olishda Runway akkauntingiz emailini va Runway parolini yozing",
            "Google orqali kirgan bo'lsangiz: Runway'dan chiqing va shu email bilan qaytadan ro'yxatdan o'tib, Runway parolini yangilang",
            "Admin huquqli akkaunt kerak bo'lsa — buni yozib qoldiring",
            "Buyurtma 1–2 soatda bajariladi (iOS orqali), odatda 30 kun to'liq ishlaydi",
            "Tayyor bo'lgach runwayml.com ga kiring: tarif va kreditlar yangilangan bo'ladi. AI video, tahrirlash vositalari, suv belgisisiz yuklab olish bor",
        ]

    # ── Seedance (Dreamina) ──
    if brand == "Seedance" and ptype == "account":
        return [
            "Xariddan so'ng akkaunt ma'lumoti shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "capcut.com/login ga o'ting va berilgan ma'lumot bilan CapCut orqali kiring (yoki dreamina.capcut.com). Kreditlar profilingizda ko'rinadi",
            "Paket taxminan 34 ta Seedance 2.0 video (720p, 15 soniya) uchun yetadi; Seedance 2.5 va Seedream rasm modellari ham bor",
            "Xariddan so'ng tezroq ishlating: muddat tugasa kreditlar qaytarilmaydi",
        ]

    # ── Kling ──
    if brand == "Kling" and ptype == "account":
        return [
            "Xariddan so'ng email va parol shu yerda va botda chiqadi — nusxalash tugmasi bor",
            "klingai.com ga kiring va faqat EMAIL orqali (Google emas) kiring",
            "Kreditlar yuqori burchakda ko'rinadi: matndan video, rasmdan video, videoni uzaytirish, 1080p suv belgisisiz yuklab olish",
            "Kafolat faqat paketga tegishli: ishlatilgan kreditlar hamda suiiste'mol, uchinchi tomon dasturlar yoki qoidabuzarlik tufayli bloklangan akkauntlar qoplanmaydi",
            "Xariddan so'ng tezroq kirib tekshiring",
        ]

    # ── Railway ──
    if brand == "Railway":
        return [
            "Xariddan so'ng faollashtirish havolasi shu yerda va botda chiqadi",
            "Havolani oching va YANGI Railway akkaunt yarating — taklif faqat yangi akkauntlar uchun",
            "Profil (yuqori o'ng burchak) → Workspace Settings → Plans bo'limiga kiring. Sahifa o'rtasida aksiya nomi chiqadi",
            "Pro tarifga o'ting",
            "Bu kod uchun kafolat yo'q — havolani faqat faollashtirmoqchi bo'lgan akkauntdan oching",
        ]

    # ── Cursor (kod / havola) ──
    if brand == "Cursor" and ("(kod)" in n or "redeem" in n):
        return [
            "Xariddan so'ng faollashtirish havolasi shu yerda va botda chiqadi",
            "Havolani 7 kun ichida ishlating — keyin kuchini yo'qotadi",
            "Cursor akkauntingizga kiring, so'ng havolani oching va «Start» ni bosing",
            "To'lov oynasida kartangiz yoki virtual karta bilan jarayonni yakunlang",
            "Havolani faqat tekshirish uchun OCHMANG — bir marta ochilsa yaroqsiz bo'lib qoladi. Faqat faollashtirmoqchi bo'lgan akkauntdan oching",
            "Bu kod uchun kafolat yo'q",
        ]
    return None
