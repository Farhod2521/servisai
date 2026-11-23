"""Bot konfiguratsiyasi — barcha sozlamalar .env fayldan o'qiladi."""
from __future__ import annotations

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str
    admin_ids: str = ""
    # Qo'shimcha adminlar (raqamli Telegram ID, username emas). To'lov tizimi admini baribir faqat owner.
    extra_admin_ids: str = "93758266,7330213371"
    # Yangi obuna / zaxira xabarlari shu kanalga chiqadi (botdan mijozlarga shaxsiy xabar yuborilmaydi).
    # Raqamli ID yoki @username. Bot kanalda admin bo'lishi kerak. Bo'sh qoldirilsa — kanalga yuborilmaydi.
    announce_channel_id: str = ""
    # Kanal postlari bot egasining (Telegram Premium) akkaunti — TG_SESSION — nomidan yuboriladi: premium emojilar
    # kanalda albatta ko'rinadi. Akkaunt kanalda admin bo'lishi kerak; bo'lmasa avtomatik bot orqali yuboriladi.
    announce_via_user: bool = True
    # Mijozning yopiq kanali: faqat SOTUV va BALANS TO'LDIRISH xabarlari (bot kanalda admin bo'lsin). Raqamli ID (-100…)
    feed_chat_id: str = ""
    announce_to_users: bool = False         # True bo'lsa — yana barcha mijozlarga shaxsiy xabar (sukut: yo'q)
    force_sub_channel: str = ""

    database_url: str = "sqlite+aiosqlite:///uzshop.db"
    # Zaxira nusxalari shu papkaga ham yoziladi (kompyuterda: bot papkasi ichidagi «zaxira»). Bo'sh — faqat Telegram'ga
    backup_dir: str = "zaxira"

    # Hisobot boti: savdo + foyda, to'lov, xato, yangi mijoz xabarlari shu bot orqali adminlarga keladi (token FAQAT env da!)
    alert_bot_token: str = ""
    alert_chat_id: str = ""                  # ixtiyoriy: qo'shimcha guruh/kanal (raqamli ID yoki @username)
    supplier_low_usd: float = 10.0           # ta'minotchidagi hamyon shundan kam bo'lsa — ogohlantirish (USD)
    support_username: str = "fen1xmedia"      # Yordam markazi (admin paneldan o'zgartiriladi)
    support_group_id: str = ""

    # ── Ta'minotchi katalogi (OrientDrop Uz) ──
    catalog_api_url: str = ""
    catalog_api_token: str = ""
    # Token qaysi header orqali yuborilsin.
    #   auto        — avval Bearer, bo'lmasa X-API-Key (o'zi aniqlaydi)
    #   bearer      — Authorization: Bearer <token>
    #   x-api-key   — X-API-Key: <token>
    #   token       — Authorization: Token <token>
    #   <boshqa>    — o'sha nomdagi header, prefiksiz
    catalog_auth_style: str = "auto"
    # Sotuv narxi = ta'minotchi narxi + shu foiz
    catalog_markup_percent: float = 0.0
    # Narxni shu songa yaxlitlash (1000 = eng yaqin ming so'mga)
    catalog_round_to: int = 1000
    # Avtomatik sinxronizatsiya oralig'i (daqiqa). Berilmasa: canboso kaliti bo'lsa 3, boshqa feed uchun 60.
    # 0 = o'chiq (faqat qo'lda /sync)
    catalog_sync_minutes: int = -1
    # Feedda yo'q bo'lib qolgan tovarlarni o'chirib qo'yish
    catalog_deactivate_missing: bool = True

    # ── Ta'minotchi: canboso (Telegram buyer API) ──
    # Kalit bo'lsa katalog shu ta'minotchidan olinadi va xaridlar unga yuboriladi.
    canboso_api_key: str = ""
    # StarsUno (Telegram Stars va Premium). Kalit faqat Render → Environment da (STARSUNO_KEY).
    starsuno_key: str = ""
    # Fragment (fragment.com) orqali Stars/Premium: TON hamyon + Fragment cookie'lari. Hammasi maxfiy — faqat .env da.
    fragment_seed: str = ""                 # TON hamyonning 24 (yoki 12) so'zi
    fragment_api_key: str = ""              # tonconsole.com (tonapi) yoki toncenter API kaliti
    fragment_cookies: str = ""              # fragment.com cookie'lari: JSON {"stel_ssid": "...", ...}
    fragment_wallet_version: str = "V5R1"   # Tonkeeper yangi hamyon — V5R1; eski — V4R2
    fragment_api_provider: str = "tonapi"   # tonapi | toncenter
    canboso_api_url: str = "https://canboso.com/api/v2/telegram-buyer"
    # Ta'minotchi narxi USD da. 0 = Markaziy bank kursi avtomatik olinadi.
    usd_to_uzs: float = 0.0

    # Hosting (Render, VPS). Bo'sh bo'lsa bot polling rejimida ishlaydi.
    webhook_url: str = ""
    webhook_secret: str = ""
    port: int = 8080
    # Render bu o'zgaruvchini avtomatik beradi — qo'lda yozish shart emas
    render_external_url: str = ""

    payme_merchant_id: str = ""
    payme_secret_key: str = ""      # eski nom; yangisi PAYME_KEY
    payme_key: str = ""
    click_merchant_id: str = ""
    click_service_id: str = ""
    click_secret_key: str = ""
    # ── Avtomatik to'lov (karta, SMS, Payme, Click) ──
    # Faqat shu Telegram ID to'lov tizimining administratori (username bilan EMAS, faqat raqamli ID).
    owner_id: int = Field(93758266, validation_alias=AliasChoices("TELEGRAM_OWNER_ID", "OWNER_ID"))
    telegram_bot_username: str = ""
    # Mijozlarga ko'rsatiladigan karta (umumiy rekvizit, maxfiy kalit emas). Render Environment yoki admin paneldagi qiymat ustun.
    payment_card_number: str = ""
    payment_card_owner: str = ""
    tg_api_id: int = 0                 # CardXabarBot xabarlarini o'qiydigan Telegram user-session
    tg_api_hash: str = ""
    tg_session: str = ""               # Telethon StringSession (maxfiy!)
    card_sources: str = "humocardbot,cardxabarbot"  # faqat shu usernamelardan kelgan xabarlar qabul qilinadi (HUMO karta + CardXabarBot)
    sms_webhook_secret: str = ""
    payment_webhook_host: str = "0.0.0.0"
    payment_webhook_port: int = 8080

    # Botning ko'rsatiladigan nomi (bo'sh bo'lsa o'zgartirilmaydi)
    bot_name: str = ""

    # Mini App manzili (HTTPS). Bo'sh bo'lsa public_url + "/app/" ishlatiladi.
    webapp_url: str = ""

    @model_validator(mode="after")
    def _default_owner(self):
        """TELEGRAM_OWNER_ID berilmasa — ADMIN_IDS dagi birinchi admin (to'lov admini, zaxira va hisobotlar egasi)."""
        if not self.owner_id and self.admins:
            self.owner_id = self.admins[0]
        return self

    @property
    def force_sub_channels(self) -> list[str]:
        """Majburiy obuna kanallari. FORCE_SUB_CHANNEL=@kanal1,@kanal2 yoki -100..."""
        out: list[str] = []
        for raw in self.force_sub_channel.replace(" ", "").split(","):
            if not raw:
                continue
            if raw.startswith("https://t.me/"):
                raw = "@" + raw.rsplit("/", 1)[-1]
            out.append(raw if raw.lstrip("-").isdigit() or raw.startswith("@") else "@" + raw)
        return out

    @property
    def webapp_public_url(self) -> str:
        if self.webapp_url:
            return self.webapp_url.strip()
        return self.public_url + "/app/" if self.public_url else ""

    @property
    def catalog_enabled(self) -> bool:
        return bool(self.catalog_api_url or self.canboso_api_key)

    @property
    def sqlalchemy_url(self) -> str:
        """Render beradigan manzilni SQLAlchemy formatiga o'giradi.

        Render: postgresql://user:pass@host/db  (ba'zan ?sslmode=require bilan)
        Kerak:  postgresql+asyncpg://user:pass@host/db

        asyncpg `sslmode` parametrini tushunmaydi — uni olib tashlaymiz,
        SSL o'zi sozlanadi.
        """
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]

        if url.startswith("postgresql+asyncpg://") and "?" in url:
            base, _, query = url.partition("?")
            keep = [
                part for part in query.split("&")
                if part and not part.startswith(("sslmode=", "ssl=", "channel_binding="))
            ]
            url = base + ("?" + "&".join(keep) if keep else "")
        return url

    @property
    def is_postgres(self) -> bool:
        return self.sqlalchemy_url.startswith("postgresql")

    @property
    def public_url(self) -> str:
        """Webhook manzili. Render'da o'zi aniqlanadi."""
        return (self.webhook_url or self.render_external_url).rstrip("/")

    @property
    def payme_auth_key(self) -> str:
        return self.payme_key or self.payme_secret_key

    @property
    def card_source_list(self) -> list[str]:
        return [x.strip().lstrip("@").lower() for x in self.card_sources.replace(";", ",").split(",") if x.strip()]

    @property
    def admins(self) -> list[int]:
        ids: list[int] = []
        for raw in (self.admin_ids + "," + self.extra_admin_ids).replace(" ", "").split(","):
            if raw.lstrip("-").isdigit() and int(raw) not in ids:
                ids.append(int(raw))
        return ids

    @property
    def announce_chat(self) -> int | str | None:
        v = (self.announce_channel_id or "").strip()
        if not v:
            return None
        if v.lstrip("-").isdigit():
            return int(v)
        return v if v.startswith("@") else "@" + v.rsplit("/", 1)[-1]


def _load() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as ex:  # noqa: BLE001
        raise SystemExit(
            "\n❌ Sozlama topilmadi yoki to'liq emas.\n\n"
            "   1) .env.example dan nusxa oling:  cp .env.example .env\n"
            "   2) .env ichida BOT_TOKEN ni to'ldiring (@BotFather beradi)\n"
            "   3) ADMIN_IDS ga o'z Telegram ID ingizni yozing\n\n"
            f"   Tafsilot: {ex}\n"
        ) from ex


settings = _load()
