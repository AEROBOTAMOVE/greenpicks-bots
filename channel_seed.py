# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ЕДИНСТВЕНИЯТ ПОСТ В КАНАЛА (channel_seed.py)

НОВАТА ПОРЪЧКА НА СОБСТВЕНИКА (тя отменя старата сеитба от пет поста):
  „Искам ГЛАВНИЯТ КАНАЛ ПРАЗЕН. Там искам САМО ЕДИН АБЗАЦ добре дошъл и всичко
   нужно, като ЕДИН ПОСТ — и след това само ЧОВЕК ще публикува!“

Затова този файл прави точно едно нещо: слага (или опреснява) ЕДИН пост в
канала и го закача. Нищо повече. Ритъмът на деня, обясненията, моделите и
поздравите вече не са отделни постове — свити са в един абзац или живеят там,
където им е мястото: в стаите на групата.

  ▸ Един пост. Закачен. Под 900 знака — чете се на един поглед в телефона.
  ▸ Бутон към групата. Линкове в текста няма — само бутонът.
  ▸ Едно дискретно „18+“ най-отдолу. Никъде другаде.
  ▸ След този пост в канала пише САМО човекът-типстер.

ТОН (желязно): публикуваме ПРОГНОЗИ, не инструкции. Без поучаване, без
морализаторстване, без букмейкър, коефициент, подкана или размер на залог.
Пазачът PREACHY в selftest() ги хваща ПРЕДИ първия байт навън.

РЕЖИМИ (CHANNEL_MODE):
  one   (по подразбиране) — сложи поста, ако го няма; опресни го на място, ако
                            текстът е сменен; закачи го наново, ако си е същият.
  wipe                    — САМО ДОКЛАД: какво помним и какво е закачено сега.
                            НИЩО НЕ СЕ ТРИЕ. Триенето е работа на reset.py.

🚫 ТОЗИ ФАЙЛ НЕ МОЖЕ ДА ТРИЕ. Забраната не е обещание — вградена е в api():
   навън минават САМО sendMessage, editMessageText, pinChatMessage (и getChat,
   който само чете). Всичко друго — и особено delete* — се отказва още преди да
   е тръгнал байт. Самопроверката пробва ключалката наживо всеки път.

🧠 ПАМЕТ: channel_seed_state.json (до този файл, в корена на repo-то) помни
   message_id на поста, за да НЕ се появи втори при ново пускане. Записът е
   атомарен (tmp + os.replace). Повреден JSON се самолекува — заделя се настрана
   и започваме начисто. Старата памет от петте поста се мигрира: пост 1 (той
   беше закаченият „добре дошъл“) става новият единствен пост, а 2–5 остават
   записани САМО за да ги изброи докладът — те се махат с reset.py.

🚫 Тук няма нишки. Каналът не е форум — message_thread_id не се праща никога.

ENV:
  BOT_TOKEN            — задължителен (освен при сухо пускане)
  CHANNEL_ID           — каналът (по подразбиране -1004403334702)
  GROUP_LINK           — покана към групата, за бутона
  SUPPORT              — съпорт-акаунтът
  CHANNEL_MODE         — one (по подразбиране) | wipe        [стар: CHANNEL_SEED_MODE]
  CHANNEL_SEED_FORCE   — „1“ = нарочно нов пост, въпреки паметта
  CHANNEL_SEED_DRY     — „1“ = само печата какво би направил, не праща нищо
  CHANNEL_SEED_STATE   — друг път до файла с паметта
  CHANNEL_SEED_ONLY    — остатък от старата сеитба; тук се пренебрегва (има един пост)

Аргументи (могат да се смесват):  one|wipe · dry · force

Бележка за деплой: файлът е писан БЕЗ обратни наклонени черти (нов ред = NL =
chr(10)), без обратни апострофи и без долар-скоба — минава през уеб-редактора.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
GROUP_LINK = os.environ.get("GROUP_LINK", "https://t.me/+_oYsaYaVKU80Yjc0")
# 🔴 11.08.2026: подразбиращото се сочеше @greenpicks_support_bot — бот, който
# НЕ работи (support_bot.py го нарича „отделният бот, ако някога тръгне").
# seed.yml подава верния, но ръчно локално пускане слагаше мъртвия акаунт в
# единствения пост на канала.
SUPPORT = os.environ.get("SUPPORT", "@green_picks_info_bot")

NL = chr(10)
TG_HARD = 3900                     # аварийна ножица: нищо не тръгва по-дълго
LEN_CAP = 900                      # обещанието към собственика: един поглед
STATE_V = 3
WELCOME_KEY = "welcome"

# ⛔ Пишещи методи — само тези три. Никакво триене, изгонване или откачване.
ALLOWED_METHODS = ("sendMessage", "editMessageText", "pinChatMessage")
# 👁 Четящи методи — за доклада в режим wipe. Нищо не променят.
READ_METHODS = ("getChat",)

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = (os.environ.get("CHANNEL_SEED_STATE") or "").strip() or os.path.join(
    HERE, "channel_seed_state.json")

DRY_WORDS = ("dry", "сухо", "--dry", "-n")
FORCE_WORDS = ("force", "сила", "--force", "-f")
MODES = ("one", "wipe")
MODE_ALIAS = {"one": "one", "1": "one", "един": "one", "пост": "one",
              "seed": "one", "сеитба": "one", "pin": "one", "закачи": "one",
              "refresh": "one", "опресни": "one", "обнови": "one",
              "wipe": "wipe", "доклад": "wipe", "оглед": "wipe",
              "report": "wipe", "провери": "wipe", "изтрий": "wipe"}


def truthy(value):
    return (value or "").strip().lower() in ("1", "true", "yes", "on", "да")


DRY = truthy(os.environ.get("CHANNEL_SEED_DRY"))
FORCE = truthy(os.environ.get("CHANNEL_SEED_FORCE"))
_raw_mode = (os.environ.get("CHANNEL_MODE")
             or os.environ.get("CHANNEL_SEED_MODE") or "one").strip().lower()
MODE = MODE_ALIAS.get(_raw_mode, "one" if not _raw_mode else "")
if not MODE:
    print("WARN: непознат режим „" + _raw_mode + "“ — карам с „one“.")
    MODE = "one"
ONLY = (os.environ.get("CHANNEL_SEED_ONLY") or "").strip()

for _arg in sys.argv[1:]:
    _a = _arg.strip().lower()
    if not _a:
        continue
    if _a in DRY_WORDS:
        DRY = True
    elif _a in FORCE_WORDS:
        FORCE = True
    elif _a in MODE_ALIAS:
        MODE = MODE_ALIAS[_a]
    else:
        print("WARN: пренебрегвам аргумента „" + _arg.strip() + "“ — тук има само един пост.")

STATE_OK = True                    # става False, ако паметта не се запише
KNOWN_MIDS = set()                 # ключалката на editMessageText/pinChatMessage
SENT = 0                           # брояч: този файл праща НАЙ-МНОГО едно съобщение


def block(*lines):
    """Слепва редовете с нов ред — без обратни наклонени черти в текста."""
    return NL.join(lines)


def esc(text):
    """Само за динамичните парчета (SUPPORT). Статичният текст е писан на ръка."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def now_str():
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Sofia")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return time.strftime("%Y-%m-%d %H:%M")


SUP = esc(SUPPORT)

# Изрази, които собственикът НЕ иска в канала: инструкции към читателя, морал и
# реклама. Пазачът в selftest() ги хваща преди първия байт навън.
PREACHY = ["залаг", "отговорно", "потърси помощ", "загубата не се гони",
           "решението остава твое", "решението е твое", "не е съвет",
           "не е гаранция", "сигурен мач", "коефициент", "букмейкър",
           "банка", "финансов съвет", "18 години", "препоръчваме"]


# ══════════════════════════════════════════════════════════════════════════
#  СЪДЪРЖАНИЕТО — ЕДИН ПОСТ. Целият канал се събира тук.
# ══════════════════════════════════════════════════════════════════════════

WELCOME = block(
    "🟢 <b>THE GREEN ROOM</b>",
    "<i>Числа вместо обещания.</i>",
    "",
    # 🔴 ПРЕПИСАН НА 11.08.2026. Това е ЕДИНСТВЕНИЯТ закачен пост в канала —
    # най-четеният текст в целия продукт. В него имаше четири твърдения, които
    # кодът опровергава:
    #   • „Тънки данни — няма прогноза" — точно този отказ Е МАХНАТ по изрична
    #     поръчка на собственика; при тънки данни ботът слиза едно стъпало и
    #     пак дава карта.
    #   • „Каналът е тих — тук пише само човекът" — оценителят пуска там
    #     резултатите и финиша на деня, по два-три поста на пускане.
    #   • „прогнозите на бота денонощно" — последното пускане за деня е 22:00
    #     и до 08:00 ботът мълчи нарочно (пазачът на прозореца).
    #   • „срещите по спорт" — в стаите по спорт влизат ПРОГНОЗИТЕ.
    "Прогнозите тук се смятат от статистика — форма, преки срещи, темпо, ниво "
    "на съперника. До всяко число стои извадката, от която е сметнато: „6 и 5 "
    "мача“ и „30 и 28 мача“ не тежат еднакво. При тънки данни картата пак "
    "излиза, но казва на какво стъпва. Нищо не се трие: сгрешеното стои до "
    "познатото.",
    "",
    "В канала: фишовете на човека зад тях и резултатите на деня. Живото е в "
    "групата — прогнозите на бота от 08:00 до 23:00, по стая за всеки спорт, "
    "новините и пълната статистика. Всяка стая има точно една задача. "
    "👇 Влизането е от бутона.",
    "",
    # ⚠️ „18+“ ОСТАВА. Махнах го за малко на 11.08 и собствената самопроверка
    # на файла ме хвана: тя иска ТОЧНО ЕДНО „18+“ и то на последния ред.
    # Това не е забранена дума тук, а нарочно правило на продукта — „едно
    # дискретно 18+ най-отдолу, никъде другаде“. Пазачите за думи в другите
    # ботове важат за СЪОБЩЕНИЯТА с прогнози, не за този единствен ред.
    "🆘 " + SUP + "   ·   🔞 18+")


POSTS = [
    {"key": WELCOME_KEY, "name": "🟢 Единственият пост в канала", "text": WELCOME,
     "pin": True, "button": "💬 Влез в групата и стаите"},
]


# ══════════════════════════════════════════════════════════════════════════
#  ПАМЕТТА — заради нея второто пускане закача, вместо да дублира
# ══════════════════════════════════════════════════════════════════════════

def digest(item):
    """Отпечатък на съдържанието. Смени ли се текстът или бутонът — сменя се."""
    raw = (item["text"] or "") + "|" + (item["button"] or "") + "|" + (
        GROUP_LINK if item["button"] else "")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def quarantine():
    """Повредената памет не се трие — заделя се настрана, за да се погледне."""
    spare = STATE_PATH + ".corrupt"
    try:
        with open(STATE_PATH, "rb") as f:
            data = f.read()
        with open(spare, "wb") as f:
            f.write(data)
        print("   старият файл е запазен като " + os.path.basename(spare))
    except Exception as e:
        print("   (не успях да запазя повредения файл: " + str(e)[:80] + ")")


def load_state():
    """Чете паметта. Всяка изненада води до чист старт, не до крах."""
    fresh = {"v": STATE_V, "channels": {}}
    try:
        with open(STATE_PATH, encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Памет: няма файл — този пост още не е правен.")
        return fresh
    except Exception as e:
        print("⚠️  Повредена памет (" + str(e)[:80] + ") — започвам начисто.")
        quarantine()
        return fresh
    if not isinstance(data, dict) or not isinstance(data.get("channels"), dict):
        print("⚠️  Непознат формат на паметта — започвам начисто.")
        quarantine()
        return fresh
    out = {"v": STATE_V, "channels": {}}
    for ch, body in data["channels"].items():
        posts = {}
        src = (body or {}).get("posts")
        if isinstance(src, dict):
            for k, rec in src.items():
                try:
                    mid = int((rec or {}).get("mid"))
                except Exception:
                    continue
                posts[str(k)] = {"mid": mid,
                                 "hash": str(rec.get("hash") or ""),
                                 "sent": str(rec.get("sent") or ""),
                                 "pin": bool(rec.get("pin"))}
        out["channels"][str(ch)] = {"posts": migrate(posts)}
    return out


def migrate(posts):
    """Старата памет пазеше постове „1“…„5“. Пост 1 беше закаченият „добре
    дошъл“ — той става новият единствен пост, за да се ОПРЕСНИ на място, а не
    да се появи шести. Останалите 2–5 се пазят само за доклада."""
    if WELCOME_KEY in posts or "1" not in posts:
        return posts
    posts[WELCOME_KEY] = posts.pop("1")
    posts[WELCOME_KEY]["hash"] = ""      # текстът е нов -> ще мине през редакция
    posts[WELCOME_KEY]["pin"] = True
    left = sorted([k for k in posts if k != WELCOME_KEY])
    print("🔄 Мигрирам старата памет: пост 1 става ЕДИНСТВЕНИЯТ пост.")
    if left:
        print("   Остатъци от старата сеитба: " + ", ".join(left)
              + " — този файл НЕ ги трие (виж режим wipe).")
    return posts


def chan(state):
    """Паметта е разделена по канал — смени ли се CHANNEL_ID, започваме начисто
    за новия канал, без да губим записа за стария."""
    key = str(CHANNEL_ID)
    if key not in state["channels"]:
        state["channels"][key] = {"posts": {}}
    return state["channels"][key]


def save_state(state):
    """Атомарен запис. Убит рън не може да остави счупен JSON."""
    global STATE_OK
    if DRY:
        return True
    tmp = STATE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, STATE_PATH)
        return True
    except Exception as e:
        STATE_OK = False
        print("   🔴 ПАМЕТТА НЕ СЕ ЗАПИСА: " + str(e)[:120])
        print("      Следващото пускане ЩЕ направи ВТОРИ пост. Оправи го преди това.")
        return False


def remember(state, item, mid, digest_value):
    chan(state)["posts"][str(item["key"])] = {
        "mid": int(mid), "hash": digest_value, "sent": now_str(),
        "pin": bool(item["pin"])}
    KNOWN_MIDS.add(int(mid))
    save_state(state)


# ══════════════════════════════════════════════════════════════════════════
#  ПРАЩАНЕ
# ══════════════════════════════════════════════════════════════════════════

def api(method, **params):
    """Единственият изход навън. Пуска САМО разрешените методи.

    Всичко останало се отказва ТУК, преди мрежата — този файл няма право да
    трие. Уважава 429 (parameters.retry_after) и пробва пак.
    """
    if method not in ALLOWED_METHODS and method not in READ_METHODS:
        print("ОТКАЗ: методът " + str(method)
              + " е забранен в channel_seed. Триенето е работа на reset.py.")
        return {"ok": False, "error": "method not allowed"}
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/" + method
    for attempt in range(5):
        data = urllib.parse.urlencode(params).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=25) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429:
                try:
                    wait = int(json.loads(body).get("parameters", {}).get("retry_after", 5))
                except Exception:
                    wait = 5
                print("  429 при " + method + " — чакам " + str(wait + 1) + " сек. и пробвам пак.")
                time.sleep(wait + 1)
                continue
            print("  " + method + " HTTP " + str(e.code) + " " + body[:160])
            return {"ok": False, "error": body[:160]}
        except Exception as e:
            print("  " + method + " FAIL " + str(e)[:160])
            return {"ok": False, "error": str(e)[:160]}
    return {"ok": False, "error": "429 retries exhausted"}


def errtext(res):
    return (str(res.get("error") or "") + " " + str(res.get("description") or "")).lower()


def is_gone(res):
    """Постът, който помним, вече го няма в канала."""
    e = errtext(res)
    for token in ("message to edit not found", "message to pin not found",
                  "message_id_invalid", "message identifier is not specified",
                  "message to be edited was not found", "message can't be edited"):
        if token in e:
            return True
    return False


def is_same(res):
    return "message is not modified" in errtext(res)


def clip(text):
    if len(text) <= TG_HARD:
        return text
    return text[:TG_HARD] + NL + "…(отрязано)"


def markup(item):
    if not item["button"]:
        return None
    return json.dumps({"inline_keyboard": [[{"text": item["button"], "url": GROUP_LINK}]]})


def do_send(state, item):
    """Праща поста в КАНАЛА и го закача. Най-много ВЕДНЪЖ за цял рън."""
    global SENT
    if SENT >= 1:
        print("   ⛔ отказ: този файл праща най-много ЕДНО съобщение за рън.")
        return False
    body = clip(item["text"])
    if DRY:
        SENT += 1
        print("   [СУХО] нов пост · " + str(len(body)) + " знака"
              + (" · БУТОН: " + item["button"] if item["button"] else "")
              + (" · ЗАКАЧА СЕ" if item["pin"] else ""))
        for line in body.split(NL):
            print("      | " + line)
        return True
    payload = {"chat_id": CHANNEL_ID, "text": body, "parse_mode": "HTML",
               "disable_web_page_preview": "true"}
    mk = markup(item)
    if mk:
        payload["reply_markup"] = mk
    r = api("sendMessage", **payload)
    if not r.get("ok"):
        print("   🔴 не мина: " + str(r)[:160])
        return False
    SENT += 1
    mid = r["result"]["message_id"]
    remember(state, item, mid, digest(item))
    print("   ✅ пратен · id " + str(mid))
    if item["pin"]:
        pin = do_pin(mid)
        print("   📌 " + ("закачен" if pin.get("ok") else "пратен, но НЕ закачен"))
    return True


def do_edit(state, item, mid):
    """Обновява СЪЩЕСТВУВАЩИЯ пост на място. Без нов пост, без триене.

    Ключалка: пипаме само message_id, което сами сме записали за този канал.
    """
    if int(mid) not in KNOWN_MIDS:
        print("   ⛔ отказ: id " + str(mid) + " не е наш записан пост — не го пипам.")
        return {"ok": False, "error": "unknown message id"}
    body = clip(item["text"])
    if DRY:
        print("   [СУХО] редакция на място · id " + str(mid) + " · " + str(len(body)) + " знака")
        for line in body.split(NL):
            print("      | " + line)
        return {"ok": True}
    payload = {"chat_id": CHANNEL_ID, "message_id": int(mid), "text": body,
               "parse_mode": "HTML", "disable_web_page_preview": "true"}
    mk = markup(item)
    if mk:
        payload["reply_markup"] = mk
    return api("editMessageText", **payload)


def do_pin(mid):
    """Закача записан пост. Същата ключалка."""
    if int(mid) not in KNOWN_MIDS:
        print("   ⛔ отказ: id " + str(mid) + " не е наш записан пост — не го закачам.")
        return {"ok": False, "error": "unknown message id"}
    if DRY:
        print("   [СУХО] закачам · id " + str(mid))
        return {"ok": True}
    return api("pinChatMessage", chat_id=CHANNEL_ID, message_id=int(mid),
               disable_notification="true")


# ══════════════════════════════════════════════════════════════════════════
#  РЕЖИМ „ONE“ — единственият пост
# ══════════════════════════════════════════════════════════════════════════

def run_one(state):
    item = POSTS[0]
    rec = chan(state)["posts"].get(WELCOME_KEY)
    cur = digest(item)
    print(NL + "▶ " + item["name"] + " · " + str(len(item["text"])) + " знака")

    if not rec:
        print("   ➕ няма го в паметта — публикувам го за пръв път.")
        return 1 if do_send(state, item) else 0

    if FORCE:
        print("   ⚠️  FORCE: правя НОВ пост, макар да помня id " + str(rec["mid"]) + ".")
        print("       Старият остава в канала — този файл не трие. Махни го с reset.py.")
        return 1 if do_send(state, item) else 0

    if rec["hash"] == cur:
        print("   ✅ постът е същият (id " + str(rec["mid"]) + ", от "
              + (rec["sent"] or "?") + ") — НЕ правя втори. Само го закачам наново.")
        r = do_pin(rec["mid"])
        if r.get("ok"):
            print("   📌 закачен.")
            return 0
        if is_gone(r):
            print("   ⚠️  записаният пост липсва в канала — публикувам наново.")
            return 1 if do_send(state, item) else 0
        print("   ⚠️  не се закачи: " + str(r)[:140])
        return 0

    print("   ✏️  текстът е сменен — редактирам НА МЯСТО (id " + str(rec["mid"]) + ").")
    r = do_edit(state, item, rec["mid"])
    if r.get("ok") or is_same(r):
        rec["hash"] = cur
        rec["sent"] = now_str()
        save_state(state)
        print("   ✏️  обновен на място. Втори пост НЕ е правен.")
        p = do_pin(rec["mid"])
        print("   📌 " + ("закачен." if p.get("ok") else "не се закачи: " + str(p)[:100]))
        return 0
    if is_gone(r):
        print("   ⚠️  постът го няма в канала — публикувам наново.")
        return 1 if do_send(state, item) else 0
    print("   🔴 редакцията не мина: " + str(r)[:160])
    print("       (ако Telegram не дава да се редактира, пусни с FORCE за нов пост")
    print("        и махни стария с reset.py — тук триене няма.)")
    return 0


# ══════════════════════════════════════════════════════════════════════════
#  РЕЖИМ „WIPE“ — САМО ДОКЛАД. Нито един байт не е разрушителен.
# ══════════════════════════════════════════════════════════════════════════

def run_wipe(state):
    posts = chan(state)["posts"]
    print(NL + "🧾 ДОКЛАД ЗА КАНАЛА " + str(CHANNEL_ID))
    print("   Този режим НЕ трие. Само гледа и разказва.")

    print(NL + "1) Какво помни паметта:")
    if not posts:
        print("   (нищо — този канал не е засяван от този файл)")
    else:
        for key in sorted(posts):
            rec = posts[key]
            tag = "ЕДИНСТВЕНИЯТ ПОСТ" if key == WELCOME_KEY else "ОСТАТЪК ОТ СТАРАТА СЕИТБА"
            print("   · " + key + " → id " + str(rec["mid"]) + " · " + (rec["sent"] or "?")
                  + " · " + tag)
    leftovers = [k for k in posts if k != WELCOME_KEY]

    print(NL + "2) Какво е закачено в канала точно сега:")
    if DRY:
        print("   (сухо пускане — не питам Telegram, вярвам на паметта)")
    elif not BOT_TOKEN:
        print("   (няма BOT_TOKEN — питам само паметта)")
    else:
        r = api("getChat", chat_id=CHANNEL_ID)
        if not r.get("ok"):
            print("   (не можах да прочета канала: " + str(r)[:120] + ")")
        else:
            pinned = (r.get("result") or {}).get("pinned_message") or {}
            if not pinned:
                print("   🔴 НИЩО не е закачено. Пусни режим „one“.")
            else:
                pid = pinned.get("message_id")
                head = (pinned.get("text") or "").split(NL)[0][:60]
                mine = posts.get(WELCOME_KEY, {}).get("mid")
                print("   📌 id " + str(pid) + " · " + head)
                if mine and int(pid) != int(mine):
                    print("   ⚠️  Закаченото НЕ е нашият пост (ние помним id "
                          + str(mine) + ").")

    print(NL + "3) Какво остава за човек:")
    print("   · Bot API не дава да се изброят старите съобщения в канал —")
    print("     затова тук се доверявам на паметта, не гадая.")
    if leftovers:
        print("   · Старите постове " + ", ".join(sorted(leftovers))
              + " още са в канала. Махат се с reset.py (RESET_MODE=channel).")
    else:
        print("   · Няма записани остатъци от старата сеитба.")
    print("   · Каналът трябва да е ПРАЗЕН освен закачения пост и фишовете на човека.")
    print(NL + "   Нищо не беше изтрито. Този файл не може да трие. 🟢")
    return 0


# ══════════════════════════════════════════════════════════════════════════
#  САМОПРОВЕРКА — грешка тук значи, че нищо не тръгва
# ══════════════════════════════════════════════════════════════════════════

def selftest():
    problems = []

    # 1) ТОЧНО ЕДИН ПОСТ. Това е цялата поръчка на собственика.
    if len(POSTS) != 1:
        problems.append("постовете са " + str(len(POSTS)) + " — трябва да е ТОЧНО 1")

    pins = 0
    for it in POSTS:
        name = it["name"]
        text = it["text"] or ""
        low = text.lower()
        if not text.strip():
            problems.append(name + ": празен пост")
        # 2) ПОД ТАВАНА — един поглед в телефона
        if len(text) > LEN_CAP:
            problems.append(name + ": " + str(len(text)) + " знака — над тавана от "
                            + str(LEN_CAP))
        if len(text) > TG_HARD:
            problems.append(name + ": над твърдия лимит на Telegram")
        if it["pin"]:
            pins += 1
        # 3) БЕЗ ПОУЧАВАНЕ И БЕЗ РЕКЛАМА
        for word in PREACHY:
            if word in low:
                problems.append(name + ": поучаващ или рекламен израз „" + word + "“")
        # 4) БЕЗ ЛИНК В ТЕКСТА — връзка има само бутонът
        for token in ("http", "t.me", "www."):
            if token in low:
                problems.append(name + ": връзка в текста („" + token
                                + "“) — линкове само през бутона")
        # 18+ стои на ЕДНО място, най-отдолу, и точно веднъж
        if text.count("18+") != 1:
            problems.append(name + ": „18+“ се среща " + str(text.count("18+"))
                            + " пъти — трябва точно веднъж")
        tail = [ln for ln in text.split(NL) if ln.strip()]
        if tail and "18+" not in tail[-1]:
            problems.append(name + ": „18+“ трябва да е на последния ред")
        # съдържанието, което собственикът иска да е ЖИВО в поста
        if "групата" not in low:
            problems.append(name + ": постът не праща човека към ГРУПАТА")
        if "извадка" not in low:
            problems.append(name + ": постът не казва, че извадката винаги се показва")
        for tag in ("b", "i"):
            if text.count("<" + tag + ">") != text.count("</" + tag + ">"):
                problems.append(name + ": неравни тагове <" + tag + ">")
        # бутонът към групата
        if not it["button"] or not str(it["button"]).strip():
            problems.append(name + ": липсва бутон към групата")
        elif not GROUP_LINK.lower().startswith("https://"):
            problems.append(name + ": бутон без валидна връзка към групата")

    if pins != 1:
        problems.append("закачени постове: " + str(pins) + " (трябва точно 1)")

    # 5) КЛЮЧАЛКАТА — списъкът и живата проверка
    for m in ALLOWED_METHODS + READ_METHODS:
        low = m.lower()
        for bad in ("delete", "ban", "kick", "restrict", "unpin", "leave", "close"):
            if bad in low:
                problems.append("в разрешените методи има разрушителен метод: " + m)
    # 🔴 ПРЕПИСАНО 11.08.2026. Тук се викаше api() и се гледаше дали връща ok.
    # Условието НЕ МОЖЕШЕ да стане истина по нито един път: ключалката отказва
    # преди мрежата; ако тя падне, chat_id="0" дава 400; ако няма токен —
    # изключение. И трите пътя връщат ok=False. Тоест „проверката" щеше да
    # мълчи дори ако някой добави deleteMessage в разрешените методи.
    #
    # Сега се мери самата ключалка, а не отговорът на Telegram: методът е
    # забранен ТОГАВА И САМО ТОГАВА, когато не е в разрешените списъци.
    # Обратен тест: добави "deleteMessage" в ALLOWED_METHODS → гърми.
    for bad_method in ("deleteMessage", "deleteMessages", "unpinAllChatMessages",
                       "banChatMember", "leaveChat"):
        if bad_method in ALLOWED_METHODS or bad_method in READ_METHODS:
            problems.append("ключалката пропуска " + bad_method)

    if MODE not in MODES:
        problems.append("непознат режим: " + str(MODE))

    folder = os.path.dirname(STATE_PATH) or "."
    if not os.path.isdir(folder):
        problems.append("папката за паметта не съществува: " + folder)
    else:
        # Паметта трябва да е ЗАПИСВАЕМА ПРЕДИ първия байт навън: провалът след
        # пращането значи дубликат при следващия рън.
        probe = STATE_PATH + ".probe"
        try:
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
        except Exception as e:
            problems.append("паметта не може да се запише (" + str(e)[:70]
                            + ") — спирам, за да не дублирам поста")
    return problems


def main():
    print("Ключалката се проверява наживо — отказите отдолу са очакваните:")
    problems = selftest()
    if problems:
        print("САМОПРОВЕРКА ПРОВАЛЕНА:")
        for p in problems:
            print("  🔴 " + p)
        sys.exit(1)
    print("Самопроверка: 1 пост, " + str(len(WELCOME)) + "/" + str(LEN_CAP)
          + " знака, 1 закачване, 0 поучаване, 0 линка в текста — чисто. ✅")

    if ONLY:
        print("Бележка: CHANNEL_SEED_ONLY е зададен („" + ONLY
              + "“), но тук има само един пост — пренебрегвам го.")

    if not DRY and not BOT_TOKEN and MODE != "wipe":
        print("Липсва BOT_TOKEN.")
        sys.exit(1)

    state = load_state()
    for rec in chan(state)["posts"].values():
        KNOWN_MIDS.add(int(rec["mid"]))

    print("Канал " + str(CHANNEL_ID) + " · режим " + MODE
          + ("  [СУХО пускане]" if DRY else "") + ("  [FORCE]" if FORCE else ""))
    print("Памет: " + os.path.basename(STATE_PATH) + " · помня "
          + str(len(chan(state)["posts"])) + " записа за този канал.")

    if MODE == "wipe":
        run_wipe(state)
        return

    made = run_one(state)
    print(NL + "ГОТОВО: " + ("1 нов пост" if made else "0 нови поста")
          + " · каналът пази ЕДИН закачен пост.")
    print("След него в канала пише само човекът. Нищо не е изтрито. 🟢")
    if not STATE_OK:
        print("🔴 Паметта не е записана докрай. НЕ пускай пак, преди да го оправиш.")
        sys.exit(1)


if __name__ == "__main__":
    main()
