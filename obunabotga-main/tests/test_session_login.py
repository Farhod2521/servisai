"""TG_SESSION yaratish (faqat QR) mantig'ini soxta Telegram bilan tekshiradi. Ishga tushirish: python tests/test_session_login.py"""
from __future__ import annotations

import asyncio
import contextlib
import datetime
import io
import os
import sys
import tempfile
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from telethon import types  # noqa: E402
from telethon import errors  # noqa: E402
from telethon.errors import PasswordHashInvalidError, SessionPasswordNeededError  # noqa: E402
from telethon.tl.functions.auth import ExportLoginTokenRequest, ImportLoginTokenRequest  # noqa: E402

import make_session as ms  # noqa: E402

UTC = datetime.timezone.utc


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def tok(b: bytes):
    return types.auth.LoginToken(expires=datetime.datetime.now(UTC), token=b)


def success():
    return types.auth.LoginTokenSuccess(authorization=types.auth.Authorization(user=types.User(id=1, first_name="T")))


class FakeTelegram:
    """Telegram'ga o'xshash: exports — navbatdagi javoblar. ("scan", b"X") — X tokeni beriladi va birozdan so'ng
    telefon uni skanerlaydi (UpdateLoginToken hodisasi keladi)."""
    api_id, api_hash = 123, "hash"

    def __init__(self, exports, authorized=False, scan_delay=0.02, imports=None):
        self.exports, self.authorized, self.scan_delay = list(exports), authorized, scan_delay
        self.imports = list(imports) if imports is not None else None
        self.import_calls = 0
        self._authorized = None          # Telethon kabi: birinchi javob eslab qolinadi
        self.session = type("S", (), {"dc_id": 2})()
        self.sign_in_errors = []
        self.handlers, self.reconnects, self.switched, self.logged, self.password_ok = [], 0, None, None, None
        self.export_calls = 0

    def add_event_handler(self, cb, _ev):
        self.handlers.append(cb)

    def remove_event_handler(self, cb):
        self.handlers.remove(cb)

    async def _fire_scan(self):
        await asyncio.sleep(self.scan_delay)
        if getattr(self, "authorize_on_scan", False):
            self.authorized = True
        for cb in list(self.handlers):
            await cb(types.UpdateLoginToken())

    async def __call__(self, req):
        if isinstance(req, ExportLoginTokenRequest):
            self.export_calls += 1
            item = self.exports.pop(0) if self.exports else success()
            if isinstance(item, Exception):
                raise item
            if isinstance(item, tuple) and item[0] == "scan":
                asyncio.get_running_loop().create_task(self._fire_scan())
                return tok(item[1])
            return item
        if isinstance(req, ImportLoginTokenRequest):
            self.import_calls += 1
            if not self.imports:
                return success()
            item = self.imports.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        raise AssertionError(req)

    async def _switch_dc(self, dc):
        if getattr(self, "switch_errors", None):
            raise self.switch_errors.pop(0)
        self.switched = dc
        self.session.dc_id = dc

    async def _on_login(self, user):
        self.logged = user

    async def is_user_authorized(self):
        if self._authorized is None:
            self._authorized = self.authorized
        return self._authorized

    async def disconnect(self):
        self.reconnects += 1

    async def connect(self):
        pass

    async def sign_in(self, password=None, **_):
        if self.sign_in_errors:
            raise self.sign_in_errors.pop(0)
        if password != "parol":
            raise PasswordHashInvalidError(request=None)
        self.password_ok = True


def run_qr(client, passwords=("parol",), **kw):
    shown, log, pw = [], [], iter(passwords)
    kw.setdefault("token_wait", 0.3)
    kw.setdefault("after_scan", 0)
    asyncio.run(ms.login_qr(client, lambda _: next(pw), log.append, lambda url, ttl: shown.append((url, ttl)), **kw))
    return shown, log


URL = ms.token_url

# 1) skanerlanmasa yangi QR, skanerlansa kiriladi
c = FakeTelegram([tok(b"A"), ("scan", b"B"), success()])
shown, log = run_qr(c)
check([u for u, _ in shown] == [URL(b"A"), URL(b"B")] and c.logged is not None and any("skanerlandi" in m for m in log),
      "skanerlanmasa yangi QR chiqadi; skanerlansa kirish tugallanadi")
# 2) Telegram eski tokenni qaytarsa — eskirgan QR yangidek ko'rsatilmaydi
c = FakeTelegram([tok(b"A"), tok(b"A"), tok(b"A"), ("scan", b"B"), success()])
shown, _ = run_qr(c)
check([u for u, _ in shown] == [URL(b"A"), URL(b"B")], "eski token qaytsa — u qayta «yangi» bo'lib ko'rsatilmaydi (AUTH_TOKEN_EXPIRED bo'lmaydi)")
# 3) skanerdan keyin «Request was unsuccessful 6 time(s)» — qayta ulanib, kirishni tugatadi
c = FakeTelegram([("scan", b"A"), ValueError("Request was unsuccessful 6 time(s)"), success()])
shown, log = run_qr(c)
check(c.reconnects == 1 and c.logged is not None and any("Qayta urinilmoqda" in m for m in log)
      and any("ValueError" in m for m in log), "skanerdan keyin tarmoq xatosi — xato nomi ko'rsatiladi, qayta ulanib, kirishni tugatadi")
# 4) javob yo'qolgan, lekin kirish bajarilgan
c = FakeTelegram([ValueError("x")], authorized=True)
run_qr(c)
check(c.reconnects == 0, "kirish aslida bajarilgan bo'lsa — darhol tugaydi")
# 5) hech bo'lmasa — log fayl haqida aniq xabar bilan to'xtaydi
c = FakeTelegram([ValueError("x")] * 4)
try:
    run_qr(c, max_fail=2, max_rounds=2)
    ok = False
except SystemExit as ex:
    ok = "TG_SESSION_log.txt" in str(ex)
check(ok, "bir necha urinishdan keyin ham bo'lmasa — log faylni yuborish haqida aniq xabar bilan to'xtaydi")
# 6) boshqa Telegram serveriga ko'chirish (migratsiya)
c = FakeTelegram([("scan", b"A"), types.auth.LoginTokenMigrateTo(dc_id=4, token=b"m")])
run_qr(c)
check(c.switched == 4 and c.logged is not None, "boshqa Telegram serveriga ko'chirilsa (migratsiya) o'tib, kiradi")
# 7) 2 bosqichli parol (xato parol qayta so'raladi)
c = FakeTelegram([("scan", b"A"), SessionPasswordNeededError(request=None)])
run_qr(c, passwords=("xato", "parol"))
check(c.password_ok is True, "2 bosqichli parol: xato bo'lsa qayta so'raladi, to'g'risi bilan kiriladi")
c = FakeTelegram([("scan", b"A"), SessionPasswordNeededError(request=None)])
try:
    run_qr(c, passwords=("a", "b", "c"))
    ok = False
except SystemExit:
    ok = True
check(ok, "parol 3 marta xato bo'lsa to'xtaydi")
# 8) kompyuter soati noto'g'ri bo'lsa ham ishlaydi (QR vaqti o'z sekundomeri bilan sanaladi)
orig_time = ms.time.time
ms.time.time = lambda: (_ for _ in ()).throw(AssertionError("kompyuter soati ishlatilmasligi kerak"))
try:
    c = FakeTelegram([tok(b"A"), ("scan", b"B"), success()])
    shown, _ = run_qr(c)
    ok = c.logged is not None
finally:
    ms.time.time = orig_time
check(ok, "QR muddati kompyuter soatiga bog'liq emas (Windows soati noto'g'ri bo'lsa ham ishlaydi)")
check(all(0 < ttl <= 25 for _, ttl in run_qr(FakeTelegram([("scan", b"A"), success()]), token_wait=25)[0]),
      "QR 25 soniyadan oshmaydi (Telegram tokeni ~30 soniya yashaydi)")

# 9) QR sahifasi: brauzer bir marta ochiladi, keyingi QR shu faylga yoziladi, sahifa o'zi yangilanadi
opened = []
ms._page_path = None
orig_open = webbrowser.open
webbrowser.open = lambda url, *a, **k: opened.append(url) or True
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        ms.show_qr(URL(b"A"), 25)
        first_page = Path(ms._page_path).read_text(encoding="utf-8")
        ms.show_qr(URL(b"B"), 25)
finally:
    webbrowser.open = orig_open
check(len(opened) == 1 and opened[0].startswith("file:///") and opened[0].endswith(".html"), "brauzer bir marta ochiladi")
check(Path(ms._page_path).read_text(encoding="utf-8") != first_page and 'http-equiv="refresh"' in first_page,
      "yangi QR shu sahifaga yoziladi, sahifa o'zi qayta yuklanadi")
check("<svg" in first_page and "<?xml" not in first_page and "Qurilmani ulash" in first_page and "ttl=25" in first_page,
      "sahifada QR (SVG), o'zbekcha yo'riqnoma va qolgan vaqt sanog'i bor")
orig_page = ms.qr_page
ms.qr_page = lambda *a, **k: (_ for _ in ()).throw(PermissionError("band"))
ms._page_path = None
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        ms.show_qr(URL(b"A"), 25)
    ok = True
except Exception:
    ok = False
finally:
    ms.qr_page = orig_page
check(ok and "ochib bo'lmadi" in buf.getvalue() and len(buf.getvalue().splitlines()) > 10,
      "sahifani ochib bo'lmasa: xato chiqmaydi, QR shu oynada ko'rsatiladi")

# 10) sessiya zaxira faylga ham saqlanadi
home = tempfile.mkdtemp()
orig_expand = os.path.expanduser
os.path.expanduser = lambda p: home if p == "~" else orig_expand(p)
try:
    path = ms.backup_session("SESSION-MATNI")
finally:
    os.path.expanduser = orig_expand
check(path.endswith("TG_SESSION.txt") and Path(path).read_text(encoding="utf-8") == "SESSION-MATNI", "sessiya zaxira faylga ham saqlanadi")

# 11) .bat fayl: kod make_session.py bilan bir xil, faqat ASCII, CRLF, faqat QR
bat = (ROOT / "tools" / "TG_SESSION_QR.bat").read_bytes()
py = (ROOT / "tools" / "make_session.py").read_text(encoding="utf-8")
part = bat[bat.index(b"#PYSTART") + len(b"#PYSTART\r\n"):].decode("utf-8").replace("\r\n", "\n")
check(part == py, ".bat ichidagi Python kodi tools/make_session.py bilan bir xil")
check(all(x < 128 for x in bat[bat.index(b"#PYSTART"):]), ".bat ichidagi Python qismi faqat ASCII")
check(b"\r\n" in bat and bat.count(b"\n") == bat.count(b"\r\n"), ".bat faylida Windows qator oxirlari (CRLF)")
check(b"telethon qrcode" in bat and b"send_code_request" not in bat and b"Qanday kirasiz" not in bat,
      ".bat faqat QR bilan ishlaydi (telefon raqam so'ralmaydi)")

# 12) v8: aniq xatolar va Telethon'dagi yashirin muammolar
TIMEOUT = errors.TimedOutError(request=None, message="Timeout")
# 12.1 boshqa serverga o'tgandan keyin xato — AYNI tokenni qayta topshiradi (boshidan export qilmaydi)
c = FakeTelegram([("scan", b"A"), types.auth.LoginTokenMigrateTo(dc_id=4, token=b"m")], imports=[TIMEOUT, success()])
shown, log = run_qr(c)
check(c.logged is not None and c.export_calls == 2 and c.import_calls == 2 and c.switched == 4,
      "serverga o'tgandan keyin xato bo'lsa — o'sha token qayta topshiriladi, kirish tugallanadi")
check(any("TimedOutError" in m for m in log) and any("4-serverida" in m for m in log), "haqiqiy xato nomi (TimedOutError) va server raqami ko'rsatiladi")
# 12.2 Telethon «kirilmagan» javobini eslab qolgan bo'lsa ham — qayta tekshiriladi
c = FakeTelegram([ValueError("x")], authorized=True)
c._authorized = False
shown, log = run_qr(c)
check(c.reconnects == 0 and any("tasdiqlandi" in m for m in log), "kirish tekshiruvi har safar qaytadan qilinadi (Telethon eslab qolgan javobga ishonilmaydi)")
# 12.3 bir necha xatodan keyin — yangi QR, qayta skanerlash so'raladi
c = FakeTelegram([("scan", b"A"), TIMEOUT, TIMEOUT, ("scan", b"B"), success()])
shown, log = run_qr(c, max_fail=2)
check([u for u, _ in shown] == [URL(b"A"), URL(b"B")] and c.logged is not None and any("QAYTA skanerlang" in m for m in log),
      "urinishlar tugasa — yangi QR chiqadi va qayta skanerlash so'raladi")
# 12.4 API ID/HASH noto'g'ri — darhol aniq xabar
c = FakeTelegram([errors.ApiIdInvalidError(request=None)])
try:
    run_qr(c)
    ok = False
except SystemExit as ex:
    ok = "TG_API_ID yoki TG_API_HASH" in str(ex)
check(ok, "API ID/HASH noto'g'ri bo'lsa — darhol aniq xabar")
# 12.5 log faylga sessiya yozilmaydi; dastur haqiqiy xato nomlarini so'raydi
src = (ROOT / "tools" / "make_session.py").read_text(encoding="utf-8")
check("raise_last_call_error=True" in src and "log.info(\"%s\", session" not in src and "log.info(session" not in src,
      "haqiqiy xato nomlari yoqilgan; sessiya log faylga yozilmaydi")

# 13) v9: FloodWait — Telegram so'ragan vaqtdan ko'proq kutiladi, AYNAN shu so'rov qaytariladi, qayta ulanilmaydi
FLOOD = errors.FloodWaitError(request=None, capture=0)
c = FakeTelegram([("scan", b"A"), FLOOD, FLOOD, success()])
shown, log = run_qr(c, flood_margin=0)
check(c.logged is not None and c.reconnects == 0 and c.export_calls == 4 and sum("kutishni so'radi" in m for m in log) == 2,
      "skanerdan keyin FloodWait: kutib, shu so'rov qaytariladi, qayta ulanilmaydi, kirish tugallanadi")
c = FakeTelegram([("scan", b"A"), types.auth.LoginTokenMigrateTo(dc_id=4, token=b"m")], imports=[FLOOD, success()])
run_qr(c, flood_margin=0)
check(c.logged is not None and c.import_calls == 2 and c.export_calls == 2, "server o'zgargach FloodWait: o'sha token qayta topshiriladi")
c = FakeTelegram([("scan", b"A")] + [FLOOD] * 5)
try:
    run_qr(c, flood_margin=0, max_floods=3)
    ok = False
except SystemExit as ex:
    ok = "10 daqiqa" in str(ex)
check(ok, "FloodWait cheksiz takrorlansa — aniq xabar bilan to'xtaydi")
src = (ROOT / "tools" / "make_session.py").read_text(encoding="utf-8")
check("flood_sleep_threshold=0" in src, "Telethon FloodWait ni o'zi tez-tez qaytarmaydi (flood_sleep_threshold=0)")

# 14) v10: chuqur tekshiruv
FLOOD0 = errors.FloodWaitError(request=None, capture=0)
# 14.1 parol kiritilayotganda «kuting» va aloqa uzilishi — parol qayta so'ralmaydi, kirish tugallanadi
c = FakeTelegram([("scan", b"A"), SessionPasswordNeededError(request=None)])
c.sign_in_errors = [FLOOD0, ConnectionError("uzildi"), FLOOD0]
asked = []
asyncio.run(ms.login_qr(c, lambda _: asked.append(1) or "parol", lambda m: None, lambda u, t: None,
                        token_wait=0.3, after_scan=0, flood_margin=0))
check(c.password_ok is True and len(asked) == 1, "2 bosqichli parolda «kuting»/aloqa uzilishi: parol bir marta so'raladi, kirish tugallanadi")
# 14.2 server almashish yarim qolsa — avval to'g'ri serverga o'tadi, keyin tokenni topshiradi
c = FakeTelegram([("scan", b"A"), types.auth.LoginTokenMigrateTo(dc_id=4, token=b"m")])
c.switch_errors = [FLOOD0]
run_qr(c, flood_margin=0)
check(c.logged is not None and c.session.dc_id == 4 and c.export_calls == 2, "server almashish yarim qolsa — avval 4-serverga o'tib, so'ng tokenni topshiradi")

# 14.3 TASODIFIY SINOV: 1500 xil xato aralashmasi — dastur hech qachon tushunarsiz xato bilan yiqilmaydi
import random
orig_sleep = asyncio.sleep


async def fast_sleep(_t=0, *a, **k):
    await orig_sleep(0)

ms.asyncio.sleep = fast_sleep
outcomes = {"ok": 0, "exit": 0}
try:
    for seed in range(1500):
        rnd = random.Random(seed)
        pool = [lambda: tok(bytes([rnd.randrange(3)])), lambda: ("scan", b"S"), lambda: FLOOD0,
                lambda: errors.TimedOutError(request=None, message="Timeout"), lambda: ValueError("x"),
                lambda: ConnectionError("x"), lambda: types.auth.LoginTokenMigrateTo(dc_id=rnd.choice([1, 4, 5]), token=b"m"),
                lambda: errors.AuthTokenExpiredError(request=None), lambda: SessionPasswordNeededError(request=None)]
        script = [rnd.choice(pool)() for _ in range(rnd.randrange(1, 14))] + [("scan", b"Z"), success()]
        imports = [rnd.choice([success(), FLOOD0, errors.TimedOutError(request=None, message="T"), ValueError("x")])
                   for _ in range(rnd.randrange(0, 4))] + [success()]
        c = FakeTelegram(script, authorized=rnd.random() < 0.1, scan_delay=0, imports=imports)
        c.sign_in_errors = [rnd.choice([FLOOD0, ConnectionError("x")]) for _ in range(rnd.randrange(0, 3))]
        c.switch_errors = [FLOOD0] if rnd.random() < 0.2 else []
        try:
            asyncio.run(ms.login_qr(c, lambda _: "parol", lambda m: None, lambda u, t: None,
                                    token_wait=0.05, after_scan=0, flood_margin=0))
            outcomes["ok"] += 1
        except SystemExit:
            outcomes["exit"] += 1
finally:
    ms.asyncio.sleep = orig_sleep
check(outcomes["ok"] + outcomes["exit"] == 1500, "1500 tasodifiy holat: dastur hech qachon tushunarsiz xato bilan yiqilmaydi")
check(outcomes["ok"] >= 1400, "1500 tasodifiy holatning %d tasida kirish muvaffaqiyatli tugallandi (qolgani aniq xabar bilan)" % outcomes["ok"])

# 14.4 BUTUN DASTUR (main) boshidan oxirigacha: ulanish xatosi, API qiymatlari tekshiruvi, natija
import builtins
import subprocess


class MainClient(FakeTelegram):
    instances = []

    def __init__(self, session, api_id, api_hash, **kw):
        super().__init__([("scan", b"A"), success()], scan_delay=0)
        self.api_id, self.api_hash, self.kw, self.connects = api_id, api_hash, kw, 0
        MainClient.instances.append(self)
        self.session = type("S", (), {"dc_id": 2, "save": lambda _s: "1BVtsOK-SESSION"})()

    async def connect(self):
        self.connects += 1
        if self.connects == 1:
            raise ConnectionError("birinchi ulanish o'xshamadi")

    async def get_me(self):
        return types.User(id=1, first_name="Renax", username="renax")


answers = iter(["abc", "1234567", "qisqa", "0123456789abcdef0123456789abcdef"])
saved_env = {k: os.environ.pop(k, None) for k in ("TG_API_ID", "TG_API_HASH")}
home2 = tempfile.mkdtemp()
patches = [(ms, "TelegramClient", MainClient), (ms, "show_qr", lambda *a, **k: None), (builtins, "input", lambda _p="": next(answers)),
           (subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("clip yo'q"))),
           (os.path, "expanduser", lambda p, _o=os.path.expanduser: home2 if p == "~" else _o(p)), (ms.asyncio, "sleep", fast_sleep),
           (ms, "TOKEN_WAIT", 0.2)]
olds = [(o, n, getattr(o, n)) for o, n, _ in patches]
for o, n, v in patches:
    setattr(o, n, v)
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        asyncio.run(ms.main())
    ok = True
except BaseException as ex:  # noqa: BLE001
    ok = repr(ex)
finally:
    for o, n, v in olds:
        setattr(o, n, v)
    for k, v in saved_env.items():
        if v is not None:
            os.environ[k] = v
out = buf.getvalue()
mc = MainClient.instances[-1] if MainClient.instances else None
check(ok is True, "butun dastur (main) boshidan oxirigacha xatosiz ishladi %s" % ("" if ok is True else ok))
check("faqat raqamlardan" in out and "32 ta belgidan" in out and mc.api_id == 1234567, "noto'g'ri API ID/HASH yozilsa — tushuntirib, qayta so'raydi")
check("qayta urinilmoqda" in out and mc.connects == 2, "Telegram'ga birinchi ulanish o'xshamasa — qayta ulanadi")
check(mc.kw.get("raise_last_call_error") is True and mc.kw.get("flood_sleep_threshold") == 0, "klient to'g'ri sozlamalar bilan yaratiladi")
check("ULANDI!" in out and "1BVtsOK-SESSION" in out and "Quyidagi matnni nusxalang" in out, "oxirida ULANDI! va sessiya matni chiqadi (clip bo'lmasa ham)")
check((Path(home2) / "TG_SESSION.txt").read_text(encoding="utf-8") == "1BVtsOK-SESSION", "sessiya zaxira faylga yozildi")
log_txt = (Path(home2) / "TG_SESSION_log.txt").read_text(encoding="utf-8") if (Path(home2) / "TG_SESSION_log.txt").exists() else ""
check("1BVtsOK-SESSION" not in log_txt and "0123456789abcdef0123456789abcdef" not in log_txt, "log faylda sessiya ham, API HASH ham yo'q")

# 15) v11: skanerdan keyin export doim «kuting» desa ham — kirish allaqachon bajarilgani aniqlanadi (haqiqiy holat)
FLOOD3 = errors.FloodWaitError(request=None, capture=0)
c = FakeTelegram([("scan", b"A")] + [FLOOD3] * 30)
c.authorize_on_scan = True
shown, log = run_qr(c, flood_margin=0)
check(any("tasdiqlandi" in m for m in log) and c.export_calls == 1 and not any("kutishni so'radi" in m for m in log),
      "telefon tasdiqlagan zahoti kirish aniqlanadi — Telegram'dan qayta so'ralmaydi, «kuting» bo'lmaydi")
c = FakeTelegram([("scan", b"A"), FLOOD3, FLOOD3])
c.authorize_on_scan = False
orig_is = ms.is_authorized
calls = {"n": 0}


async def late_auth(cl):
    calls["n"] += 1
    return calls["n"] >= 3          # 2 marta «hali yo'q», keyin ulanadi


ms.is_authorized = late_auth
try:
    shown, log = run_qr(c, flood_margin=0)
finally:
    ms.is_authorized = orig_is
check(any("tasdiqlandi" in m for m in log) and c.export_calls == 3, "«kuting» paytida ham har safar kirish bajarilgani tekshiriladi")
print("\n✅ TG_SESSION yaratish testlari o'tdi")
