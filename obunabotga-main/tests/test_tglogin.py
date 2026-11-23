"""Telegram sessiyasini botda olish (/sessiya): soxta Telethon mijozi bilan (internet va haqiqiy kalit shart emas).

Ishga tushirish:  python tests/test_tglogin.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1", TELEGRAM_OWNER_ID="777",
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", TG_API_ID="12345", TG_API_HASH="dummyhash", WEBHOOK_URL="https://shop.example.com")

from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.storage.base import StorageKey  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402

from config import settings  # noqa: E402
from database.db import init_db  # noqa: E402
from handlers import sessiya  # noqa: E402
from services import backup, cardbridge, runtime, tglogin  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


class SessionPasswordNeededError(Exception): ...
class PhoneCodeInvalidError(Exception): ...
class PhoneCodeExpiredError(Exception): ...
class PasswordHashInvalidError(Exception): ...
class FloodWaitError(Exception):
    seconds = 125


class FakeClient:
    NEED_2FA = False
    CALLS: list = []

    def __init__(self):
        self.session = NS(save=lambda: "SESSION-STRING-123")
        self.disconnected = False

    async def connect(self): ...
    async def disconnect(self): self.disconnected = True

    async def send_code_request(self, phone):
        FakeClient.CALLS.append(("send_code", phone))
        return NS(phone_code_hash="HASH1")

    async def sign_in(self, phone=None, code=None, phone_code_hash=None, password=None):
        FakeClient.CALLS.append(("sign_in", phone, code, phone_code_hash, password))
        if password is not None:
            if password != "parol":
                raise PasswordHashInvalidError()
            return
        if code == "99999":
            raise PhoneCodeExpiredError()
        if code != "12345":
            raise PhoneCodeInvalidError()
        if FakeClient.NEED_2FA:
            raise SessionPasswordNeededError()


class Msg:
    def __init__(self, text):
        self.text, self.out, self.deleted, self.bot = text, [], False, None

    async def answer(self, text, reply_markup=None): self.out.append(text)
    async def delete(self): self.deleted = True


async def main() -> None:
    await init_db()
    await runtime.load()
    tglogin._make_client = FakeClient
    started = []
    cardbridge.start = lambda bot: started.append(1)
    owner, other = NS(tg_id=777), NS(tg_id=123)
    public = settings.webhook_url
    settings.webhook_url = ""              # 1–4: chatdagi (havolasiz) zaxira usul
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=777, user_id=777))

    # begunaga ko'rinmaydi
    m = Msg("/sessiya")
    await sessiya.start(m, other, state)
    check(not m.out and await state.get_state() is None, "owner bo'lmagan odamga /sessiya javob bermaydi")

    # 1) telefon → kod → tayyor (2FA yo'q)
    m = Msg("/sessiya")
    await sessiya.start(m, owner, state)
    check(await state.get_state() == sessiya.Ses.phone.state and "telefon raqam" in m.out[0], "/sessiya: telefon so'raydi")
    m = Msg("+998 90 123 45 67")
    await sessiya.got_phone(m, owner, state)
    check(("send_code", "+998901234567") in FakeClient.CALLS and "1 2 3 4 5" in m.out[0], "telefon qabul qilindi, kod yuborildi, «bo'sh joy bilan yozing» eslatmasi")
    m = Msg("8 8 8 8 8")
    await sessiya.got_code(m, owner, state)
    check(m.deleted and "noto'g'ri" in m.out[0] and await state.get_state() == sessiya.Ses.code.state, "noto'g'ri kod: xabar o'chirildi, qayta so'raladi")
    m = Msg("1 2 3 4 5")
    await sessiya.got_code(m, owner, state)
    check(("sign_in", "+998901234567", "12345", "HASH1", None) in FakeClient.CALLS, "«1 2 3 4 5» → 12345 (bo'sh joylar olib tashlandi)")
    check(m.deleted and "Sessiya saqlandi" in m.out[-1] and started and await state.get_state() is None, "kod xabari o'chirildi, sessiya saqlandi, ko'prik qayta yoqildi")
    check(runtime.tg_session() == "SESSION-STRING-123", "session bazaga saqlandi va runtime.tg_session() uni beradi")
    check(cardbridge.enabled(), "session bor — ko'prik yoqiladi (TG_SESSION Render'da bo'lmasa ham)")

    # 2) 2FA bor akkaunt
    FakeClient.NEED_2FA = True
    await runtime.set_value("tg_session", None)
    await sessiya.start(Msg("/sessiya"), owner, state)
    await sessiya.got_phone(Msg("+998901234567"), owner, state)
    m = Msg("12345")
    await sessiya.got_code(m, owner, state)
    check(await state.get_state() == sessiya.Ses.password.state and "2FA" in m.out[-1], "2FA bor: parol so'raladi")
    m = Msg("xato")
    await sessiya.got_password(m, owner, state)
    check(m.deleted and "parol noto'g'ri" in m.out[0], "noto'g'ri parol: xabar o'chirildi, qayta so'raladi")
    m = Msg("parol")
    await sessiya.got_password(m, owner, state)
    check(m.deleted and runtime.tg_session() == "SESSION-STRING-123", "to'g'ri parol: xabar o'chirildi, session saqlandi")

    # 3) Telegram cheklovi va noto'g'ri telefon
    class Flood(FakeClient):
        async def send_code_request(self, phone):
            raise FloodWaitError()
    tglogin._make_client = Flood
    await state.clear()
    await sessiya.start(Msg("/sessiya"), owner, state)
    m = Msg("+998901234567")
    await sessiya.got_phone(m, owner, state)
    check("3 daqiqadan keyin" in m.out[0] and await state.get_state() == sessiya.Ses.phone.state, "FloodWait: necha daqiqa kutish aytiladi")
    m = Msg("12")
    await sessiya.got_phone(m, owner, state)
    check("Telefon raqam noto'g'ri" in m.out[0], "noto'g'ri telefon rad etiladi")

    # 4) session zaxira (backup) fayliga tushmaydi
    import gzip, json
    raw, _ = await backup.dump()
    data = json.loads(gzip.decompress(raw))
    keys = {r["key"] for r in data["tables"]["settings"]}
    check("tg_session" not in keys, "Telegram session zaxira faylida YO'Q")
    settings.webhook_url = public          # 5) brauzer orqali kirish: bir martalik havola; kod Telegram chatiga yozilmaydi
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from webapp.server import setup_webapp
    sent = []

    class FakeBot:
        async def send_message(self, chat_id, text, **kw): sent.append((chat_id, text))

    tglogin._make_client = FakeClient
    FakeClient.NEED_2FA = False
    FakeClient.CALLS.clear()
    await runtime.set_value("tg_session", None)
    started.clear()
    m = Msg("/sessiya")
    await sessiya.start(m, owner, state)
    check(any("sessiya/" in str(x) for x in [tglogin._LINKS.keys()]) or tglogin._LINKS, "/sessiya (public_url bor): bir martalik havola yaratildi")
    token = next(iter(tglogin._LINKS))
    app = web.Application()
    setup_webapp(app, FakeBot())
    async with TestClient(TestServer(app)) as cl:
        r = await cl.get(f"/sessiya/{token}")
        check(r.status == 200 and "Kod yuborish" in await r.text() and r.headers.get("Cache-Control") == "no-store", "sahifa ochiladi (no-store)")
        r = await cl.get("/sessiya/yolgon-token")
        check(r.status == 404, "noto'g'ri havola → 404")
        r = await cl.post(f"/sessiya/{token}/do", json={"step": "phone", "value": "+998 90 123 45 67"})
        check((await r.json()) == {"ok": True, "next": "code"} and ("send_code", "+998901234567") in FakeClient.CALLS, "telefon → kod yuborildi")
        r = await cl.post(f"/sessiya/{token}/do", json={"step": "code", "value": "00000"})
        d = await r.json()
        check(d["ok"] is False and "noto'g'ri" in d["error"], "noto'g'ri kod: xato ko'rsatiladi")
        n_send = len([c for c in FakeClient.CALLS if c[0] == "send_code"])
        r = await cl.post(f"/sessiya/{token}/do", json={"step": "code", "value": "99999"})
        d = await r.json()
        check(d["ok"] is False and "YANGI kod yuborildi" in d["error"] and len([c for c in FakeClient.CALLS if c[0] == "send_code"]) == n_send + 1,
              "kod bekor qilinsa — avtomatik YANGI kod yuboriladi")
        r = await cl.post(f"/sessiya/{token}/do", json={"step": "code", "value": "12345"})
        check((await r.json()) == {"ok": True, "next": "done"} and runtime.tg_session() == "SESSION-STRING-123", "to'g'ri kod: sessiya saqlandi")
        check(started and sent and "Sessiya saqlandi" in sent[0][1] and sent[0][0] == 777, "ko'prik qayta yoqildi, ownerga xabar yuborildi")
        r = await cl.post(f"/sessiya/{token}/do", json={"step": "phone", "value": "+998901234567"})
        check(r.status == 404, "havola bir martalik: ishlatilgach yaroqsiz")
    print("\nHAMMASI JOYIDA")


asyncio.run(main())
