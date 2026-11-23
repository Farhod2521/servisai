"""To'lov provayderlari.

Har bir provayder `checkout_url()` qaytaradi — foydalanuvchi shu havolaga
o'tib to'laydi. To'lov tasdiqlanishi provayderning webhook'i orqali keladi
(payment_webhook.py). Provayder kalitlari .env ga qo'yilmagan bo'lsa,
`configured` False bo'ladi va bot qo'lda to'lov rejimiga tushadi.

ESLATMA: Payme va Click bilan ishlash uchun YaTT/MChJ sifatida merchant
shartnoma tuzish kerak. Kalitlar kelgach, .env ni to'ldirish kifoya.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from config import settings


@dataclass
class Provider:
    code: str
    title: str
    configured: bool

    def checkout_url(self, payment_id: int, amount_sum: int) -> str | None:
        raise NotImplementedError


class PaymeProvider(Provider):
    def __init__(self):
        super().__init__("payme", "🟢 Payme", bool(settings.payme_merchant_id))

    def checkout_url(self, payment_id: int, amount_sum: int) -> str | None:
        if not self.configured:
            return None
        # Payme summani tiyinda kutadi
        raw = (
            f"m={settings.payme_merchant_id};"
            f"ac.payment_id={payment_id};"
            f"a={amount_sum * 100}"
        )
        token = base64.b64encode(raw.encode()).decode()
        return f"https://checkout.paycom.uz/{token}"


class ClickProvider(Provider):
    def __init__(self):
        super().__init__("click", "🔵 Click", bool(settings.click_service_id))

    def checkout_url(self, payment_id: int, amount_sum: int) -> str | None:
        if not self.configured:
            return None
        return (
            "https://my.click.uz/services/pay"
            f"?service_id={settings.click_service_id}"
            f"&merchant_id={settings.click_merchant_id}"
            f"&amount={amount_sum}"
            f"&transaction_param={payment_id}"
        )


class UzumProvider(Provider):
    """Uzum Bank — merchant kalitlari kelgach to'ldiriladi."""
    def __init__(self):
        super().__init__("uzum", "🟣 Uzum Bank", False)

    def checkout_url(self, payment_id: int, amount_sum: int) -> str | None:
        return None


class ManualProvider(Provider):
    def __init__(self):
        super().__init__("manual", "👤 Admin orqali", True)

    def checkout_url(self, payment_id: int, amount_sum: int) -> str | None:
        return None


PROVIDERS: dict[str, Provider] = {
    p.code: p for p in (PaymeProvider(), ClickProvider(), UzumProvider(), ManualProvider())
}

MIN_TOPUP = 1_000  # so'm
