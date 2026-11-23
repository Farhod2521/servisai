"""Telegram sessiyasini brauzerda olish: /sessiya/<bir martalik-token>.

Havolani botdagi /sessiya buyrug'i faqat owner'ga beradi (15 daqiqa, bir marta). Sahifada telefon → kod → (bo'lsa) 2FA parol.
Kod Telegram chatiga yozilmaydi, shuning uchun Telegram uni «eskirgan» qilib qo'ymaydi.
"""
from __future__ import annotations

import html
import logging
import time
from collections import defaultdict, deque

from aiohttp import web

from services import cardbridge, tglogin

log = logging.getLogger("uzshop.sessiya_web")

_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'none'"}
_hits: dict[str, deque] = defaultdict(deque)

PAGE = """<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Telegram sessiya</title><style>
body{font-family:system-ui,sans-serif;background:#0f1721;color:#e8eef5;margin:0;padding:20px;display:flex;justify-content:center}
.c{max-width:420px;width:100%}h1{font-size:20px}p{color:#9fb0c3;line-height:1.5}
input{width:100%;box-sizing:border-box;padding:14px;font-size:18px;border-radius:10px;border:1px solid #2c3b4e;background:#16202d;color:#fff;margin:8px 0}
button{width:100%;padding:14px;font-size:17px;border:0;border-radius:10px;background:#2ea043;color:#fff;font-weight:600;margin-top:6px}
button:disabled{opacity:.5}.err{color:#ff7b72;min-height:22px}.ok{color:#3fb950;font-size:18px}.box{display:none}.box.on{display:block}
</style></head><body><div class="c"><h1>🔑 Telegram sessiya</h1>
<div id="s_phone" class="box on"><p>@HUMOcardbot xabarlarini oladigan Telegram akkauntning telefon raqami:</p>
<input id="phone" type="tel" inputmode="tel" placeholder="+998901234567" autocomplete="off"><button onclick="go('phone')">Kod yuborish</button></div>
<div id="s_code" class="box"><p>Telegram ilovasiga kod keldi («Telegram» chatida). Kodni <b>faqat shu yerga</b> yozing. Telegram chatiga, botga yoki boshqa joyga YOZMANG (Telegram bekor qiladi):</p>
<input id="code" type="text" inputmode="numeric" placeholder="12345" autocomplete="off"><button onclick="go('code')">Tasdiqlash</button></div>
<div id="s_password" class="box"><p>Akkauntda 2 bosqichli parol (2FA) bor. Uni yozing:</p>
<input id="password" type="password" autocomplete="off"><button onclick="go('password')">Kirish</button></div>
<div id="s_done" class="box"><p class="ok">✅ Tayyor! Sessiya saqlandi. Telegramdagi botga qayting: «ulandi» xabari keladi. Bu sahifani yopishingiz mumkin.</p></div>
<div class="err" id="err"></div></div><script>
const T=location.pathname.replace(/\\/$/,"");
function show(n){document.querySelectorAll('.box').forEach(b=>b.classList.remove('on'));document.getElementById('s_'+n).classList.add('on')}
async function go(step){const v=document.getElementById(step).value.trim();const e=document.getElementById('err');e.textContent='';
const btn=event.target;btn.disabled=true;try{const r=await fetch(T+'/do',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({step:step,value:v})});
const d=await r.json();if(d.ok){show(d.next)}else{e.textContent=d.error||'Xato'}}catch(x){e.textContent='Ulanish xatosi. Qayta urinib ko\\'ring.'}btn.disabled=false}
</script></body></html>"""


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= 30:
        return False
    q.append(now)
    return True


def _ip(request: web.Request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() or request.remote or "?")[:64]


async def page(request: web.Request) -> web.Response:
    if not _rate_ok(_ip(request)) or tglogin.link_owner(request.match_info["token"]) is None:
        return web.Response(status=404, text="Havola eskirgan yoki noto'g'ri. Botda /sessiya yozib yangisini oling.", headers=_HEADERS)
    return web.Response(text=PAGE, content_type="text/html", headers=_HEADERS)


async def do(request: web.Request) -> web.Response:
    token = request.match_info["token"]
    if not _rate_ok(_ip(request)):
        return web.json_response({"ok": False, "error": "Juda ko'p urinish. Bir daqiqadan keyin urinib ko'ring."}, status=429, headers=_HEADERS)
    owner = tglogin.link_owner(token, count=True)
    if owner is None:
        return web.json_response({"ok": False, "error": "Havola eskirgan. Botda /sessiya yozib yangisini oling."}, status=404, headers=_HEADERS)
    try:
        body = await request.json()
        step, value = str(body.get("step") or ""), str(body.get("value") or "")
    except Exception:  # noqa: BLE001
        return web.json_response({"ok": False, "error": "Noto'g'ri so'rov"}, status=400, headers=_HEADERS)
    try:
        if step == "phone":
            await tglogin.begin(owner, value)
            nxt = "code"
        elif step == "code":
            nxt = "password" if await tglogin.submit_code(owner, value) == "password" else "done"
        elif step == "password":
            await tglogin.submit_password(owner, value)
            nxt = "done"
        else:
            return web.json_response({"ok": False, "error": "Noto'g'ri qadam"}, status=400, headers=_HEADERS)
    except tglogin.LoginError as ex:
        msg = str(ex)
        if step == "code" and "eskirgan" in msg and await tglogin.resend(owner):
            msg = ("Telegram bu kodni bekor qildi (kod boshqa joyga yozilgan bo'lishi mumkin). YANGI kod yuborildi: "
                   "uni faqat shu sahifaga yozing, Telegram chatiga yoki botga yozmang.")
        return web.json_response({"ok": False, "error": msg}, headers=_HEADERS)
    if nxt == "done":
        tglogin.drop_link(token)
        bot = request.app["bot"]
        cardbridge.STATE["connected_at"] = None
        cardbridge.start(bot)
        try:
            await bot.send_message(owner, "✅ <b>Sessiya saqlandi.</b> Ko'prik ishga tushirilmoqda — bir necha soniyada «ulandi» xabari keladi.")
        except Exception:  # noqa: BLE001
            pass
    return web.json_response({"ok": True, "next": nxt}, headers=_HEADERS)


def add_routes(app: web.Application) -> None:
    app.router.add_get("/sessiya/{token}", page)
    app.router.add_post("/sessiya/{token}/do", do)
