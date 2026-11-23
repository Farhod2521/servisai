@echo off
chcp 65001 >nul
title TG_SESSION yaratish
echo.
echo  ===== TG_SESSION yaratish (faqat QR-kod) =====
echo.
set PY=
python --version >nul 2>nul && set PY=python
if not defined PY py --version >nul 2>nul && set PY=py
if not defined PY (
  echo  Python topilmadi. python.org dan Python o'rnating ^(o'rnatishda "Add python.exe to PATH" katagini belgilang^),
  echo  keyin shu faylni qayta ikki marta bosing.
  pause
  exit /b 1
)
echo  Kutubxonalar o'rnatilmoqda (1-2 daqiqa)...
%PY% -m pip install --quiet --disable-pip-version-check telethon qrcode
if errorlevel 1 (
  echo  Kutubxonalarni o'rnatib bo'lmadi. Internetni tekshiring.
  pause
  exit /b 1
)
powershell -NoProfile -Command "$t=[IO.File]::ReadAllText('%~f0'); $i=$t.IndexOf([char]10+'#PY'+'START'); [IO.File]::WriteAllText($env:TEMP+'\tg_session_v11.py',$t.Substring($i+1))"
%PY% "%TEMP%\tg_session_v11.py"
del "%TEMP%\tg_session_v11.py" >nul 2>nul
echo.
pause
exit /b 0
#PYSTART
"""TG_SESSION yaratish - faqat QR-kod bilan. KOMPYUTERINGIZDA, bir marta ishlating.

    pip install telethon qrcode
    python tools/make_session.py          (Windows uchun: tools/TG_SESSION_QR.bat ni ikki marta bosing)

API ID / API HASH: https://my.telegram.org -> "API development tools".
Brauzerda QR-kod ochiladi; telefondagi Telegram bilan skanerlaysiz (Sozlamalar > Qurilmalar > Qurilmani ulash).
Bitta telefon yetarli. Natijada uzun matn (StringSession) chiqadi: uni FAQAT Render -> Environment -> TG_SESSION ga qo'ying.
Hech qaerga yubormang, GitHub'ga yozmang: u akkauntingizga kirish kaliti.

Vaqt: har bir QR ~30 soniya amal qiladi (Telegram qoidasi). Dastur uni 25 soniyada yangilaydi va bunda kompyuter
soatiga qaramaydi (o'z sekundomeri bilan sanaydi), shuning uchun Windows soati noto'g'ri bo'lsa ham QR eskirmaydi.
"""
import asyncio
import base64
import getpass
import io
import logging
import os
import subprocess
import tempfile
import time
import webbrowser

from telethon import TelegramClient, events
from telethon.errors import ApiIdInvalidError, FloodWaitError, PasswordHashInvalidError, RPCError, SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.functions.auth import ExportLoginTokenRequest, ImportLoginTokenRequest
from telethon.tl.types import UpdateLoginToken
from telethon.tl.types.auth import LoginTokenMigrateTo, LoginTokenSuccess

TOKEN_WAIT = 25          # soniya: QR shuncha turadi, keyin yangisi (Telegram tokeni ~30 soniya amal qiladi)
NET_ERRORS = (ValueError, ConnectionError, OSError, asyncio.TimeoutError)
log = logging.getLogger("tg_session")


# --------------------------- QR sahifasi ---------------------------

PAGE = """<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta http-equiv="refresh" content="2"><title>Telegram QR-kod</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;background:#f4f6f8;color:#111;text-align:center;margin:0;padding:24px}
.box{display:inline-block;background:#fff;padding:24px 32px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.12)}
svg{width:340px;height:340px;display:block;margin:12px auto}ol{text-align:left;line-height:1.7;font-size:17px;margin:12px 0 0}
#t{font-weight:700;font-size:20px;margin:6px 0}.ok{color:#1a8f3c}.bad{color:#d32f2f}</style></head>
<body><div class="box"><h2>Telegram QR-kod</h2><div id="t" class="ok"></div>__SVG__
<ol><li>Telefonda <b>Telegram</b>ni oching</li><li><b>Sozlamalar &rarr; Qurilmalar &rarr; Qurilmani ulash</b></li>
<li>Kamerani shu QR-kodga to'g'rilang</li><li>Tasdiqlashni bosing</li></ol>
<p style="color:#888">Faqat SHU sahifadagi QR ni skanerlang. Eski oynalar va sahifalarni yoping.<br>QR o'zi yangilanadi.</p></div>
<script>var t0=__T0__,ttl=__TTL__;function tick(){var s=ttl-Math.floor((Date.now()-t0)/1000),e=document.getElementById("t");
if(s>2){e.className="ok";e.textContent="QR amal qiladi: "+s+" soniya"}else{e.className="bad";e.textContent="Yangi QR tayyorlanmoqda, kuting..."}}
tick();setInterval(tick,300);</script></body></html>"""


def qr_page(url, ttl=TOKEN_WAIT, born=None) -> str:
    """QR-kodli HTML sahifa (rasm kutubxonasi shart emas: QR SVG ko'rinishida sahifaning ichida)."""
    import qrcode
    from qrcode.image.svg import SvgPathImage
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(image_factory=SvgPathImage).save(buf)
    svg = buf.getvalue().decode("utf-8")
    svg = svg[svg.index("<svg"):]                      # <?xml ...?> sarlavhasi sahifa ichida kerak emas
    t0 = int((born if born is not None else time.time()) * 1000)
    return PAGE.replace("__SVG__", svg).replace("__T0__", str(t0)).replace("__TTL__", str(int(ttl)))


_page_path = None     # bitta sahifa fayli: QR yangilanganda shu fayl qayta yoziladi, sahifa o'zi qayta yuklanadi


def show_qr(url, ttl=TOKEN_WAIT) -> None:
    """QR-kodni ko'rsatadi: brauzerda katta sahifa (o'zi yangilanadi); bo'lmasa shu oynaning o'zida. Hech qachon yiqilmaydi."""
    global _page_path
    try:
        first = _page_path is None
        if first:
            _page_path = os.path.join(tempfile.gettempdir(), "tg_qr_%d.html" % int(time.time() * 1000))
        tmp = _page_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(qr_page(url, ttl))
        os.replace(tmp, _page_path)                       # sahifa yarim yozilgan holda ko'rinmaydi
        if first:
            print("QR-kod brauzerda ochilmoqda...")
            if not webbrowser.open("file:///" + _page_path.replace("\\", "/").lstrip("/")):
                print("Brauzer ochilmadi. Shu faylni qo'lda oching:", _page_path)
        return
    except Exception as ex:
        print("QR sahifasini ochib bo'lmadi (%s). QR shu oynada chiqariladi:" % type(ex).__name__)
    try:
        import qrcode
        qr = qrcode.QRCode(border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        print("QR ni ko'rsatib bo'lmadi. Havola:", url)


# --------------------------- Kirish ---------------------------

def describe(ex) -> str:
    """Xatoning haqiqiy nomi va matni (qisqa)."""
    return "%s: %s" % (type(ex).__name__, str(ex).split(" (caused by")[0][:160])


async def two_step(client, ask_password, say, flood_margin=2, max_extra=10) -> None:
    """2 bosqichli parol (3 urinish). Telegram "kuting" desa yoki aloqa uzilsa - kutib, SHU parolni qayta yuboradi."""
    pw, asked, extra = None, 0, 0
    while True:
        if pw is None:
            if asked >= 3:
                raise SystemExit("Parol 3 marta noto'g'ri. Qayta boshlang.")
            pw = ask_password("2 bosqichli parol (yozganingiz ko'rinmaydi): ")
            asked += 1
        try:
            await client.sign_in(password=pw)
            return
        except PasswordHashInvalidError:
            say("Parol noto'g'ri, qayta kiriting.")
            pw = None
        except FloodWaitError as ex:
            extra += 1
            if extra > max_extra:
                raise SystemExit("Telegram juda ko'p kutish so'radi (%s). 10 daqiqa kutib, qayta boshlang." % describe(ex))
            wait = int(getattr(ex, "seconds", 3) or 0) + flood_margin
            say("Telegram %d soniya kutishni so'radi - kutilmoqda..." % wait)
            await asyncio.sleep(wait)
        except NET_ERRORS as ex:
            extra += 1
            log.exception("Parol yuborishda xato")
            if extra > max_extra:
                raise SystemExit("Telegram bilan aloqa barqaror emas (%s). Internetni tekshiring yoki VPN yoqing." % describe(ex))
            say("Aloqa xatosi (%s), qayta urinilmoqda..." % describe(ex))
            await reconnect(client)
            await asyncio.sleep(2)


async def is_authorized(client) -> bool:
    """Kirish bajarilganmi - har safar QAYTADAN tekshiradi (Telethon birinchi javobni eslab qoladi, shuni tozalaymiz)."""
    try:
        client._authorized = None
    except Exception:
        pass
    try:
        return bool(await client.is_user_authorized())
    except Exception:
        return False


async def reconnect(client) -> None:
    try:
        await client.disconnect()
    except Exception:
        pass
    try:
        await client.connect()
    except Exception:
        pass


def token_url(token: bytes) -> str:
    return "tg://login?token=" + base64.urlsafe_b64encode(token).decode("utf-8").rstrip("=")


async def wait_for_scan(client, seconds) -> bool:
    """Telegram "QR skanerlandi" xabarini kutadi. True - skanerlandi, False - vaqt tugadi."""
    scanned = asyncio.Event()

    async def handler(_update):
        scanned.set()

    client.add_event_handler(handler, events.Raw(UpdateLoginToken))
    try:
        await asyncio.wait_for(scanned.wait(), seconds)
        return True
    except asyncio.TimeoutError:
        return False
    finally:
        client.remove_event_handler(handler)


async def login_qr(client, ask_password, say, show, token_wait=TOKEN_WAIT, max_fail=4, max_rounds=4, flood_margin=2, max_floods=12,
                   after_scan=1.5) -> None:
    """QR-kod bilan kirish (Telegram ilovalaridagi usul):
    token olinadi -> QR ko'rsatiladi -> skanerlanishi kutiladi (25 soniya, o'z sekundomeri bilan) ->
    skanerlansa token qayta so'raladi va kirish tugallanadi; skanerlanmasa yangi token olinadi.
    Akkaunt boshqa Telegram serverida bo'lsa (LoginTokenMigrateTo) o'sha serverga o'tib, tokenni o'sha yerda topshiradi;
    xato bo'lsa AYNAN shu tokenni qayta topshiradi (boshidan boshlamaydi). Har xatoda kirish aslida bajarilganini
    qayta tekshiradi. Bir necha urinishdan keyin ham bo'lmasa - yangi QR chiqadi (qayta skanerlash kerak)."""
    fails, rounds, pending, floods = 0, 0, None, 0   # pending: boshqa serverda topshirilishi kerak bo'lgan token
    seen = {}                                    # token -> birinchi ko'rilgan payt (sekundomer, kompyuter soatiga bog'liq emas)
    while True:
        try:
            if pending is not None:
                dc_id, token = pending
                if getattr(getattr(client, "session", None), "dc_id", dc_id) != dc_id:   # o'tish yarim qolgan bo'lsa
                    await client._switch_dc(dc_id)
                res = await client(ImportLoginTokenRequest(token))
            else:
                res = await client(ExportLoginTokenRequest(client.api_id, client.api_hash, []))
            if isinstance(res, LoginTokenMigrateTo):
                say("Akkauntingiz Telegram'ning %d-serverida. O'sha serverga o'tilmoqda..." % res.dc_id)
                pending = (res.dc_id, res.token)
                await client._switch_dc(res.dc_id)
                res = await client(ImportLoginTokenRequest(res.token))
            pending = None
            fails = 0
        except SessionPasswordNeededError:
            say("QR skanerlandi. Akkauntda 2 bosqichli parol bor.")
            await two_step(client, ask_password, say, flood_margin)
            return
        except FloodWaitError as ex:
            # Telegram "N soniya kuting" dedi. Skanerdan keyin bu ko'pincha kirish ALLAQACHON bajarilganini bildiradi
            # (telefon tasdiqlagan zahoti sessiya ulanadi) - avval shuni tekshiramiz
            if await is_authorized(client):
                say("Kirish tasdiqlandi.")
                return
            # bo'lmasa: ko'proq kutamiz va AYNAN shu so'rovni qaytaramiz (qayta ulanmaymiz)
            floods += 1
            if floods > max_floods:
                raise SystemExit("Telegram juda ko'p kutish so'radi (%s). 10 daqiqa kutib, qayta boshlang." % describe(ex))
            wait = int(getattr(ex, "seconds", 3) or 0) + flood_margin
            say("Telegram %d soniya kutishni so'radi - kutilmoqda..." % wait)
            log.info("FloodWait %s s (pending=%s)", getattr(ex, "seconds", "?"), pending is not None)
            await asyncio.sleep(wait)
            continue
        except ApiIdInvalidError:
            raise SystemExit("TG_API_ID yoki TG_API_HASH noto'g'ri. my.telegram.org dagi qiymatlarni tekshirib, qayta boshlang.")
        except (RPCError,) + NET_ERRORS as ex:
            log.exception("So'rov xatosi (pending=%s)", pending is not None)
            if await is_authorized(client):          # javob yo'qolgan, lekin kirish bajarilgan
                say("Kirish tasdiqlandi.")
                return
            fails += 1
            say("Xato: %s" % describe(ex))
            if fails < max_fail:
                say("Qayta urinilmoqda... (%d/%d)" % (fails, max_fail))
                await reconnect(client)
                await asyncio.sleep(3)
                continue
            rounds += 1
            fails, pending = 0, None
            if rounds >= max_rounds:
                raise SystemExit("Kirish tugallanmadi (%s). Ish stolidagi TG_SESSION_log.txt faylini yuboring "
                                 "(unda maxfiy kalit yo'q)." % describe(ex))
            say("Bu urinish tugallanmadi. Yangi QR chiqadi - uni QAYTA skanerlang. (%d/%d)" % (rounds, max_rounds))
            await reconnect(client)
            continue
        if isinstance(res, LoginTokenSuccess):
            on_login = getattr(client, "_on_login", None)
            if on_login:
                await on_login(res.authorization.user)
            return
        now = time.monotonic()
        first = seen.setdefault(res.token, now)
        if now - first > token_wait + 15:           # Telegram eski tokenni qaytaraversa - yangi deb hisoblaymiz
            first = seen[res.token] = now
        left = token_wait - (now - first)
        if left < min(3, token_wait / 2):           # shu token tugay deb qoldi: eskirgan QR ko'rsatilmaydi, yangisini kutamiz
            await asyncio.sleep(min(2, token_wait / 4))
            continue
        show(token_url(res.token), int(left))
        say("QR tayyor (%d soniya). Telefonda skanerlang..." % int(left))
        if await wait_for_scan(client, left):
            say("QR skanerlandi, kirish tugallanmoqda...")
            await asyncio.sleep(after_scan)
            if await is_authorized(client):          # telefon tasdiqlagan zahoti sessiya ulangan bo'ladi
                say("Kirish tasdiqlandi.")
                return
        # skanerlansa ham, vaqt tugasa ham - keyingi aylanishda token qayta so'raladi:
        # skanerlangan bo'lsa Telegram "muvaffaqiyat" qaytaradi, aks holda yangi token (yangi QR) beradi


def setup_log() -> str:
    """Xatolar va Telethon xabarlari faylga yoziladi (maxfiy kalitlarsiz). Fayl yo'lini qaytaradi."""
    for folder in (os.path.join(os.path.expanduser("~"), "Desktop"), os.path.expanduser("~"), tempfile.gettempdir()):
        path = os.path.join(folder, "TG_SESSION_log.txt")
        try:
            logging.basicConfig(filename=path, filemode="w", level=logging.INFO, encoding="utf-8",
                                format="%(asctime)s %(levelname)s %(name)s: %(message)s")
            return path
        except Exception:
            continue
    return ""


def backup_session(session) -> str:
    """Sessiyani faylga ham saqlaydi (oyna yopilib ketsa yo'qolmasin). Fayl yo'lini qaytaradi, bo'lmasa bo'sh qator."""
    for folder in (os.path.join(os.path.expanduser("~"), "Desktop"), os.path.expanduser("~")):
        try:
            path = os.path.join(folder, "TG_SESSION.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(session)
            return path
        except Exception:
            continue
    return ""


def ask_api_id() -> int:
    v = (os.environ.get("TG_API_ID") or "").strip()
    while not v.isdigit():
        if v:
            print("TG_API_ID faqat raqamlardan iborat (my.telegram.org dagi App api_id). Qayta kiriting.")
        v = input("TG_API_ID (raqam): ").strip()
    return int(v)


def ask_api_hash() -> str:
    v = (os.environ.get("TG_API_HASH") or "").strip()
    while not (len(v) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in v)):
        if v:
            print("TG_API_HASH 32 ta belgidan iborat (0-9, a-f). my.telegram.org dagi App api_hash ni to'liq nusxalang.")
        v = input("TG_API_HASH: ").strip()
    return v


async def connect_or_exit(client, say, tries=3, pause=3) -> None:
    for i in range(1, tries + 1):
        try:
            await client.connect()
            return
        except Exception as ex:
            log.exception("Ulanishda xato")
            if i == tries:
                raise SystemExit("Telegram'ga ulanib bo'lmadi (%s). Internetni tekshiring yoki VPN yoqib qayta urining." % describe(ex))
            say("Telegram'ga ulanib bo'lmadi (%s), qayta urinilmoqda... (%d/%d)" % (describe(ex), i, tries))
            await asyncio.sleep(pause)


async def main() -> None:
    print()
    print("Obunalar boti: TG_SESSION yaratish (v11, faqat QR-kod)")
    api_id = ask_api_id()
    api_hash = ask_api_hash()
    log_path = setup_log()
    # raise_last_call_error: umumiy "Request was unsuccessful" o'rniga Telegram'ning haqiqiy xatosi ko'rinadi;
    # flood_sleep_threshold=0: "kuting" xabarini Telethon o'zi tez-tez qaytarmaydi, kutishni login_qr bajaradi
    client = TelegramClient(StringSession(), api_id, api_hash, raise_last_call_error=True, flood_sleep_threshold=0)
    if log_path:
        print("Log fayl: %s" % log_path)
    await connect_or_exit(client, print)
    log.info("Ulandi: DC %s", getattr(client.session, "dc_id", "?"))
    try:
        print()
        print("Telefonda: Telegram > Sozlamalar > Qurilmalar > Qurilmani ulash > kompyuter ekranidagi QR-kodni skanerlang")
        print("(Faqat brauzerdagi OXIRGI QR ni skanerlang. Eski oynalarni yoping.)")
        try:
            await login_qr(client, getpass.getpass, print, show_qr)
        except SystemExit:
            raise
        except Exception as ex:
            log.exception("Kutilmagan xato")
            raise SystemExit("Kutilmagan xato (%s). Ish stolidagi TG_SESSION_log.txt faylini yuboring (unda maxfiy kalit yo'q)."
                             % describe(ex))
        session = client.session.save()
        print()
        print("ULANDI!")
        saved = backup_session(session)
        try:
            me = await client.get_me()
            print("Akkaunt: %s (@%s)" % (me.first_name or "", me.username or "-"))
        except Exception:
            pass
        try:
            subprocess.run("clip", input=session.encode(), check=True)
            print("TG_SESSION nusxalandi. Render > Environment > TG_SESSION ga Ctrl+V qiling.")
        except Exception:
            print("Quyidagi matnni nusxalang:")
        if saved:
            print("Zaxira fayl: %s  (Render'ga qo'ygach shu faylni O'CHIRIB tashlang)" % saved)
        print()
        print(session)
        print()
        print("DIQQAT: bu matn akkauntingiz kaliti. Hech kimga bermang, GitHub'ga yozmang.")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
