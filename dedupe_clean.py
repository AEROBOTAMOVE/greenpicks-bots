# -*- coding: utf-8 -*-
"""
GREEN PICKS - dedupe_clean.py
ХИРУРГИЧЕН чистач на повтарящи се съобщения. НЕ е reset.py (той трие всичко).

КАКВО НАИСТИНА МОЖЕ Bot API-то (честно, без разкрасяване)
---------------------------------------------------------
Ботът НЕ МОЖЕ да чете история. Няма getChatHistory, няма getMessages, няма
"дай ми последните 200 съобщения". Затова тук се използват двата единствени
трика, с които бот може да ВИДИ съдържанието на съобщение по неговото id:

  1) ОТГОВОР-СОНДА (probe=reply) - пращаме мъничко съобщение с
     reply_parameters -> {"message_id": N}. Отговорът на Telegram съдържа
     полето reply_to_message, а в него е ЦЯЛОТО оригинално съобщение:
     text / caption, from (кой го е пратил), date и message_thread_id (стаята).
     Веднага трием сондата. Това е ЕДИНСТВЕНИЯТ начин бот да научи в коя
     СТАЯ (topic) живее дадено id -> затова е задължителен за форум-групата.
     ЦЕНА: сондата за миг се появява в самата стая (без звук) и се трие.
     Ако id-то не съществува, Telegram връща 400 "message to be replied not
     found" -> значи е изтрито. Това ни дава и картата на живите id-та.

  2) ПРЕПРАЩАНЕ-СОНДА (probe=forward) - forwardMessage към отделен служебен
     чат. Връща целия Message (text/caption), НЕ цапа източника изобщо.
     НО: губи message_thread_id. Затова е добър за КАНАЛА (той няма стаи),
     а за групата - само с изричен DEDUPE_ALLOW_NOTHREAD=1.

КАКВО ОСТАВА НЕВЪЗМОЖНО (казвам го, вместо да го скрия)
  - В КАНАЛ постовете нямат поле from. Значи НЕ може да се докаже, че постът е
    на бота, а не на собственика. Затова channel-режимът иска изричен
    DEDUPE_ALLOW_CHANNEL=1 и по подразбиране е проба.
  - Няма списък на всички закачени (pinned) съобщения. getChat дава само
    ПОСЛЕДНОТО закачено на целия чат. Закачените в отделните стаи не се четат.
    Затова: PROTECT_IDS + правилото "пазим най-новото от всяка група".
  - deleteMessages (пакетно) НЕ казва кои id-та реално са изтрити. За точен
    отчет ползвай DEDUPE_EXACT=1 (трие едно по едно, по-бавно, но честно).
  - Еднаква КАРТИНКА, качена два пъти, получава различен file_unique_id.
    Значи снимки се засичат по ПОДПИСА (caption), не по пиксели.

РЕЖИМИ (env DEDUPE_MODE)
  scan     (по подразбиране) - сканира групата, намира повторения ВЪВ ВСЯКА
           стая поотделно, пази НАЙ-НОВОТО копие, трие по-старите.
  thread   - същото, но само за една стая (DEDUPE_THREAD). С DEDUPE_WIPE=1
           изчиства ЦЯЛАТА стая (само нашите съобщения), без контейнера.
  channel  - сканира канала (няма стаи; иска DEDUPE_ALLOW_CHANNEL=1).
  ids      - трие подаден списък id-та (DEDUPE_IDS или DEDUPE_IDS_FILE).

ЖЕЛЕЗНИ ПРАВИЛА (не се изключват с env)
  - Стая 4 (Фишове на деня) НИКОГА не се пипа. САМО ХОРА.
  - Контейнерите на темите {1,3,4,5,6,7,8,9,10,11,26,27} не се трият никога.
  - Ако стаята на едно id НЕ може да се докаже - id-то НЕ се трие. Недоказаното
    се смята за стая 4. Затваряме се, никога не се отваряме.
  - Най-новото копие от всяка група ОСТАВА. Никога не се трие цяла група.
  - Чуждо (човешко) съобщение не се трие, освен при DEDUPE_ALLOW_HUMAN=1.
  - По подразбиране режимът е ПРОБА. Реално триене само с DEDUPE_DRY=0.

КАК СА ЗАКОВАНИ ТЕЗИ ПРАВИЛА (структурно, не по джентълменско споразумение)
  Има ЕДНО-ЕДИНСТВЕНО място в целия файл, което наистина вика Telegram за
  триене: _telegram_delete(). То отказва да работи, ако не е отворено от
  delete_guarded(), а delete_guarded() пуска само id-та, минали през
  delete_verdict() - чистата логика на вратата (стая 4 / контейнер / защитено /
  недоказана стая). Няма втори път до deleteMessage. Всеки отказ се ПЕЧАТА с
  id-то и причината - мълчанието беше половината от стария бъг.

Файлът е без backtick и без долар+скоба (минава през web-editor-а).
"""
import difflib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

NL = chr(10)

# ---------------------------------------------------------------- настройки
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "-1004426592150")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")

MODE = (os.environ.get("DEDUPE_MODE") or "scan").strip().lower()
WINDOW = int(os.environ.get("DEDUPE_WINDOW", "400"))
DRY = (os.environ.get("DEDUPE_DRY", "1").strip() != "0")
SIM = float(os.environ.get("DEDUPE_SIM", "0.94"))
PROBE_KIND = (os.environ.get("DEDUPE_PROBE") or "auto").strip().lower()
PROBE_SLEEP = float(os.environ.get("DEDUPE_PROBE_SLEEP", "1.2"))
MAX_CALLS = int(os.environ.get("DEDUPE_MAX_CALLS", "1200"))
EXACT = (os.environ.get("DEDUPE_EXACT", "0").strip() == "1")
SCRATCH = (os.environ.get("DEDUPE_SCRATCH") or os.environ.get("ADMIN_CHAT_ID") or "").strip()
TARGET_THREAD = int(os.environ.get("DEDUPE_THREAD", "0") or "0")
WIPE = (os.environ.get("DEDUPE_WIPE", "0").strip() == "1")
ALLOW_HUMAN = (os.environ.get("DEDUPE_ALLOW_HUMAN", "0").strip() == "1")
ALLOW_CHANNEL = (os.environ.get("DEDUPE_ALLOW_CHANNEL", "0").strip() == "1")
ALLOW_NOTHREAD = (os.environ.get("DEDUPE_ALLOW_NOTHREAD", "0").strip() == "1")
CONFIRM = (os.environ.get("DEDUPE_CONFIRM") or "").strip().upper()
PLAN_FILE = (os.environ.get("DEDUPE_PLAN_FILE") or "dedupe_plan.json").strip()
MAX_ID_ENV = int(os.environ.get("DEDUPE_MAX_ID", "0") or "0")
MIN_LEN = int(os.environ.get("DEDUPE_MIN_LEN", "12"))

# Контейнерите на форум-темите. Същият списък като reset.py:16.
KEEP_IDS = {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 26, 27}
# Стая 4 = "Фишове на деня" - САМО ХОРА. Ботът никога не трие и не пише там.
FORBIDDEN_THREADS = {4}
ROOM_NAME = {
    1: "Общ чат", 3: "Правила и Начало", 4: "Фишове на деня (САМО ХОРА)",
    5: "Футбол", 6: "Баскетбол", 7: "Тенис на маса", 8: "Волейбол",
    9: "Резултати и статистика", 10: "Печеливши фишове", 11: "Въпроси и Помощ",
    26: "Новини", 27: "БОТА ПРЕДРИЧА",
}

# id-та, които САМИЯТ бот създаде в този рън (сонди). Само те се трият без
# доказана стая - защото ги родихме преди секунда и знаем, че са наши.
_OWN_SCRATCH = set()
# Всеки отказ на вратата, за финалния отчет.
DELETE_REFUSALS = []
# Резе: _telegram_delete работи САМО когато delete_guarded го е отворило.
_GATE = {"open": False}


def room_label(th):
    if th is None:
        return "НЕИЗВЕСТНА стая"
    return ROOM_NAME.get(th, "канал" if th == 0 else "стая " + str(th))


def _thsort(th):
    """Ключ за сортиране, който търпи None (неизвестна стая)."""
    return -1 if th is None else int(th)


def _ids_from_env():
    raw = (os.environ.get("DEDUPE_IDS") or "").replace(",", " ").split()
    out = [int(x) for x in raw if x.strip().lstrip("-").isdigit()]
    path = (os.environ.get("DEDUPE_IDS_FILE") or "").strip()
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = data.get("delete_ids") or []   # приема и dedupe_plan.json
            if isinstance(data, list):
                out += [int(x) for x in data if str(x).lstrip("-").isdigit()]
        except Exception as e:
            print("  ВНИМАНИЕ: не мога да прочета", path, "-", str(e)[:100])
    return sorted(set(out))


def _protect_from_env():
    raw = (os.environ.get("PROTECT_IDS") or "").replace(",", " ").split()
    return set(int(x) for x in raw if x.strip().isdigit())


# ---------------------------------------------------------------- Telegram
CALLS = {"n": 0}
_REPLY_STYLE = {"modern": True}   # reply_parameters -> ако гръмне, стария начин


def api(method, **params):
    """Същата форма като reset.py:18 - уважава 429 parameters.retry_after."""
    CALLS["n"] += 1
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/" + method
    for attempt in range(5):
        data = urllib.parse.urlencode(params).encode()
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429:
                try:
                    ra = int(json.loads(body).get("parameters", {}).get("retry_after", 5))
                except Exception:
                    ra = 5
                print("  429 на", method, "- чакам", ra + 1, "сек")
                time.sleep(ra + 1)
                continue
            return {"ok": False, "code": e.code, "error": body[:200]}
        except Exception as e:
            return {"ok": False, "code": 0, "error": str(e)[:200]}
    return {"ok": False, "code": 429, "error": "429 retries exhausted"}


def get_me():
    r = api("getMe")
    if r.get("ok"):
        return r["result"].get("id"), r["result"].get("username")
    return None, None


def probe_max_id(chat):
    """Най-голямото живо message_id: пращаме и веднага трием. (reset.py:41)"""
    if MAX_ID_ENV > 0:
        return MAX_ID_ENV
    for attempt in range(3):
        r = api("sendMessage", chat_id=chat, text=".", disable_notification="true")
        if r.get("ok"):
            mid = r["result"]["message_id"]
            delete_own(chat, mid)
            return mid
        print("  сонда за max_id, опит", attempt + 1, "не мина:", str(r.get("error"))[:120])
        time.sleep(2)
    return 0


def pinned_id(chat):
    r = api("getChat", chat_id=chat)
    if r.get("ok"):
        pm = (r.get("result") or {}).get("pinned_message") or {}
        if pm.get("message_id"):
            return int(pm["message_id"])
    return 0


# ---------------------------------------------------------------- сонди
def _send_reply(chat, mid, modern):
    p = {"chat_id": chat, "text": ".", "disable_notification": "true"}
    if modern:
        p["reply_parameters"] = json.dumps(
            {"message_id": int(mid), "allow_sending_without_reply": False})
    else:
        p["reply_to_message_id"] = int(mid)
        p["allow_sending_without_reply"] = "false"
    r = api("sendMessage", **p)
    if not r.get("ok"):
        return None, r
    res = r["result"]
    delete_own(chat, res["message_id"])
    return res, r


def probe_reply(chat, mid):
    """Отговор-сонда. Връща оригиналния Message или None ако id-то е мъртво.

    Два капана, заради които има резервен път:
      - по-стар Bot API отговаря с грешка за reply_parameters;
      - още по-стар МЪЛЧАЛИВО игнорира непознатото поле и праща обикновено
        съобщение. Тогава reply_to_message липсва и ВСЯКО id би изглеждало
        мъртво. Затова при първа такава засечка минаваме на стария начин.
    """
    modern = _REPLY_STYLE["modern"]
    res, raw = _send_reply(chat, mid, modern)

    if res is None and modern:
        err = str(raw.get("error", "")).lower()
        if "reply_parameters" in err or "reply parameters" in err:
            print("  този Bot API не приема reply_parameters - минавам на стария начин")
            _REPLY_STYLE["modern"] = False
            res, raw = _send_reply(chat, mid, False)

    if res is None:
        return None                      # най-често: съобщението не съществува

    orig = res.get("reply_to_message")
    if not orig and modern and _REPLY_STYLE["modern"]:
        # Пратено е, но БЕЗ отговор -> полето е било подминато мълчаливо.
        print("  reply_parameters е подминато мълчаливо - минавам на стария начин")
        _REPLY_STYLE["modern"] = False
        res2, _ = _send_reply(chat, mid, False)
        if res2 is not None:
            orig = res2.get("reply_to_message")
    return orig or None


def probe_forward(chat, mid, scratch):
    """Препращане-сонда. Не цапа източника, но НЕ дава message_thread_id."""
    r = api("forwardMessage", chat_id=scratch, from_chat_id=chat,
            message_id=int(mid), disable_notification="true")
    if not r.get("ok"):
        return None
    res = r["result"]
    delete_own(scratch, res["message_id"])
    return res


def author_id(msg):
    """Кой е авторът. None = не може да се докаже (напр. пост в канал)."""
    frm = msg.get("from") or {}
    if frm.get("id"):
        return int(frm["id"])
    org = msg.get("forward_origin") or {}
    su = org.get("sender_user") or {}
    if su.get("id"):
        return int(su["id"])
    ff = msg.get("forward_from") or {}
    if ff.get("id"):
        return int(ff["id"])
    return None


def thread_of(msg):
    """Стаята. В форум General няма message_thread_id -> стая 1."""
    t = msg.get("message_thread_id")
    if t is None:
        return 1
    try:
        return int(t)
    except Exception:
        return 1


def record_thread(msg, kind, is_channel):
    """В коя стая живее съобщението - или None, ако НЕ може да се докаже.

    Каналът няма стаи изобщо -> 0 е структурна истина, не предположение.
    forward-сондата ГУБИ message_thread_id -> в групата това е НЕЗНАНИЕ.
    Старият код пишеше 0 и тук - фалшива 'известна' стая, която минаваше
    покрай преградата за стая 4. Вече е None и вратата отказва."""
    if is_channel:
        return 0
    if kind == "reply":
        return thread_of(msg)
    return None


# ---------------------------------------------------------------- сравняване
def strip_tags(s):
    """Маха HTML тагове. Пипа САМО ако има затварящ таг, за да не изяде '2 < 3'.
    (Telegram връща текста вече без тагове, но подписите ни се градят с <b>.)"""
    if "</" not in (s or ""):
        return s or ""
    out = []
    depth = 0
    for ch in s:
        if ch == "<":
            depth += 1
        elif ch == ">":
            if depth:
                depth -= 1
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def norm(s):
    """Нормализация без regex и без наклонени черти: само букви/цифри + интервал.
    isalnum() хваща и кирилицата, така че 'Арсенал 2:1' и 'АРСЕНАЛ  2 1' съвпадат."""
    out = []
    space = True
    for ch in strip_tags(s or "").lower():
        if ch.isalnum():
            out.append(ch)
            space = False
        elif not space:
            out.append(" ")
            space = True
    return "".join(out).strip()

def content_key(msg):
    """(вид, ключ, видим_текст). None ако няма какво да се сравнява."""
    body = msg.get("text") or msg.get("caption") or ""
    n = norm(body)
    if n:
        return ("text", n, body)
    ph = msg.get("photo") or []
    if ph:
        big = ph[-1]
        for p in ph:
            if (p.get("file_size") or 0) > (big.get("file_size") or 0):
                big = p
        uid = big.get("file_unique_id")
        if uid:
            return ("photo", "photo:" + str(uid), "[снимка без подпис]")
    for kind in ("video", "animation", "document", "sticker", "audio"):
        obj = msg.get(kind)
        if isinstance(obj, dict) and obj.get("file_unique_id"):
            return (kind, kind + ":" + str(obj["file_unique_id"]), "[" + kind + "]")
    return None


def similar(a, b, threshold):
    if threshold >= 1.0:
        return False
    if len(a) < MIN_LEN or len(b) < MIN_LEN:
        return False
    lo, hi = (len(a), len(b)) if len(a) <= len(b) else (len(b), len(a))
    if hi and lo / float(hi) < threshold:
        return False                     # твърде различна дължина - без смисъл
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold


def group_messages(records, threshold):
    """Групира по (стая, вид) -> точен ключ, после близки по SequenceMatcher.
    Връща списък от групи; всяка група е списък записи, сортиран НАЙ-НОВ ПЪРВИ."""
    buckets = {}
    for rec in records:
        buckets.setdefault((rec["thread"], rec["kind"]), []).append(rec)
    groups = []
    for _, items in sorted(buckets.items(),
                           key=lambda kv: (_thsort(kv[0][0]), str(kv[0][1]))):
        exact = {}
        order = []
        for rec in items:
            if rec["key"] not in exact:
                exact[rec["key"]] = []
                order.append(rec["key"])
            exact[rec["key"]].append(rec)
        merged = []
        for k in order:
            placed = False
            if threshold < 1.0 and exact[k][0]["kind"] == "text":
                for g in merged:
                    if similar(g["key"], k, threshold):
                        g["items"] += exact[k]
                        placed = True
                        break
            if not placed:
                merged.append({"key": k, "items": list(exact[k])})
        for g in merged:
            g["items"].sort(key=lambda r: r["id"], reverse=True)
            groups.append(g["items"])
    return groups


# ---------------------------------------------------------------- сканиране
def scan(chat, ids, kind, scratch, me_id, is_channel):
    """Обхожда id-тата отгоре надолу и връща (записи, живи, мъртви, спрян)."""
    records, alive, dead, stopped = [], 0, 0, False
    total = len(ids)
    eta = int(total * (PROBE_SLEEP + 0.6))
    print("  сонда:", kind, "| id-та за проверка:", total,
          "| груба сметка за времето: ~" + str(eta // 60), "мин", str(eta % 60), "сек")
    for n, mid in enumerate(ids, 1):
        if CALLS["n"] >= MAX_CALLS:
            print("  СПИРАМ: достигнат таван DEDUPE_MAX_CALLS =", MAX_CALLS)
            stopped = True
            break
        msg = (probe_forward(chat, mid, scratch) if kind == "forward"
               else probe_reply(chat, mid))
        if not msg:
            dead += 1
        else:
            alive += 1
            ck = content_key(msg)
            if ck:
                th = record_thread(msg, kind, is_channel)
                aid = author_id(msg)
                records.append({
                    "id": int(mid),
                    "thread": th,
                    "kind": ck[0],
                    "key": ck[1],
                    "text": (ck[2] or "")[:160],
                    "author": aid,
                    "ours": (aid == me_id) if aid is not None else None,
                    "date": msg.get("date", 0),
                })
        if n % 25 == 0 or n == total:
            print("   ...", n, "/", total, "| живи", alive, "| мъртви", dead,
                  "| извиквания", CALLS["n"])
        time.sleep(PROBE_SLEEP)
    return records, alive, dead, stopped


# ---------------------------------------------------------------- ВРАТАТА
def refuse(mid, why):
    """Отказът ВИНАГИ се вижда. Мълчанието беше половината от бъга."""
    print("  ОТКАЗ ТРИЕНЕ | id", mid, "|", why)
    DELETE_REFUSALS.append((mid, why))


def delete_verdict(mid, thread, protect=None):
    """Чистата логика на вратата - без мрежа, затова е и тествaема.

    Връща (позволено, причина). Редът е нарочен: първо невалидно, после
    собствената сонда, после железните забрани, НАКРАЯ доказателството за стая.
    Липсва ли доказателство -> ОТКАЗ. Никога обратното."""
    try:
        i = int(mid)
    except Exception:
        return False, "невалидно id"
    if i <= 0:
        return False, "невалидно id"
    if i in _OWN_SCRATCH and i not in KEEP_IDS:
        return True, "собствена сонда (наша, родена преди секунда)"
    if i in KEEP_IDS:
        return False, "контейнер на тема - " + room_label(i)
    if protect and i in protect:
        return False, "защитено / закачено (PROTECT_IDS)"
    if thread is None:
        return False, "стаята е НЕДОКАЗАНА (или id-то не съществува) - fail closed"
    try:
        t = int(thread)
    except Exception:
        return False, "стаята е нечетима - fail closed"
    if t in FORBIDDEN_THREADS:
        return False, "стая " + str(t) + " " + room_label(t) + " - ЖЕЛЯЗНО ПРАВИЛО"
    return True, "ok"


def _telegram_delete(chat, ids):
    """ЕДИНСТВЕНОТО място в файла, което наистина вика Telegram за триене.

    Не се вика отвън - само delete_guarded() има право да отвори резето.
    Пакетно deleteMessages по 100, с поединично връщане при провал."""
    if not _GATE["open"]:
        print("  ВЪТРЕШНА ГРЕШКА: опит за триене ИЗВЪН вратата - отказвам.", ids)
        return 0, [int(i) for i in ids]
    done, failed = 0, []
    ids = sorted(set(int(i) for i in ids))
    if EXACT:
        for i in ids:
            r = api("deleteMessage", chat_id=chat, message_id=i)
            if r.get("ok"):
                done += 1
            else:
                failed.append(i)
            time.sleep(0.06)
        return done, failed
    for j in range(0, len(ids), 100):
        batch = ids[j:j + 100]
        r = api("deleteMessages", chat_id=chat, message_ids=json.dumps(batch))
        if r.get("ok"):
            # ЧЕСТНО: пакетното триене НЕ потвърждава кои точно са минали.
            done += len(batch)
        else:
            for i in batch:
                if api("deleteMessage", chat_id=chat, message_id=i).get("ok"):
                    done += 1
                else:
                    failed.append(i)
                time.sleep(0.06)
        time.sleep(0.4)
    return done, failed


def delete_guarded(chat, ids, threads_by_id, protect=None):
    """Единственият вход към триене. Връща (изтрити, пропаднали, откази).

    threads_by_id: id -> стая. ЛИПСВАЩ ключ = недоказана стая = ОТКАЗ."""
    allowed, refused = [], []
    for mid in sorted(set(int(x) for x in ids)):
        okd, why = delete_verdict(mid, (threads_by_id or {}).get(mid), protect)
        if okd:
            allowed.append(mid)
        else:
            refuse(mid, why)
            refused.append((mid, why))
    if not allowed:
        return 0, [], refused
    _GATE["open"] = True
    try:
        done, failed = _telegram_delete(chat, allowed)
    finally:
        _GATE["open"] = False
    for i in allowed:
        _OWN_SCRATCH.discard(i)      # изключението трае точно едно триене
    return done, failed, refused


def delete_own(chat, mid):
    """Триене на НАША сонда. Минава през същата врата, не покрай нея."""
    _OWN_SCRATCH.add(int(mid))
    delete_guarded(chat, [int(mid)], {}, None)


# ---------------------------------------------------------------- отчет
def plan_from_groups(groups, protect):
    """Пази най-новото от всяка група. Връща (план, изтриваеми_id)."""
    plan, victims = [], []
    for items in groups:
        if len(items) < 2:
            continue
        keep = items[0]
        drop = [r for r in items[1:] if r["id"] not in protect]
        if not drop:
            continue
        plan.append({
            "thread": keep["thread"],
            "kind": keep["kind"],
            "keep": keep["id"],
            "delete": [r["id"] for r in drop],
            "text": keep["text"],
        })
        victims += [r["id"] for r in drop]
    plan.sort(key=lambda g: (_thsort(g["thread"]), -g["keep"]))
    return plan, sorted(set(victims))


def guard(ids, protect, threads_by_id):
    """Преглед на плана със СЪЩАТА логика, която пази и самото триене.

    Тук няма втори набор правила - вика delete_verdict, за да е невъзможно
    прегледът и изпълнението да се разминат."""
    safe, blocked = [], []
    for i in sorted(set(int(x) for x in ids)):
        okd, why = delete_verdict(i, (threads_by_id or {}).get(i), protect)
        if okd:
            safe.append(i)
        else:
            print("  ПРЕГРАДА | id", i, "|", why)
            blocked.append((i, why))
    return safe, blocked


def resolve_threads(chat, ids, is_channel):
    """Сондира всяко id, за да се ДОКАЖЕ стаята му. Връща (карта, недоказани).

    Без това режимът ids трие на сляпо - точно това беше дупката, през която
    съобщение от стая 4 можеше да бъде изтрито."""
    if is_channel:
        return dict((int(i), 0) for i in ids), []
    out, unknown = {}, []
    total = len(ids)
    for n, mid in enumerate(ids, 1):
        if CALLS["n"] >= MAX_CALLS:
            print("  СПИРАМ сондирането: таван DEDUPE_MAX_CALLS =", MAX_CALLS)
            unknown += [int(x) for x in ids[n - 1:]]
            break
        msg = probe_reply(chat, mid)
        if not msg:
            unknown.append(int(mid))      # мъртво или недостъпно -> не се пипа
        else:
            out[int(mid)] = thread_of(msg)
        if n % 25 == 0 or n == total:
            print("   ...", n, "/", total, "| доказани стаи", len(out),
                  "| недоказани", len(unknown))
        time.sleep(PROBE_SLEEP)
    return out, unknown


def report(title, plan, victims, blocked, records, deleted, failed, dry):
    print("")
    print("=" * 66)
    print(title)
    print("=" * 66)
    per = {}
    for rec in records:
        d = per.setdefault(rec["thread"], {"scan": 0, "ours": 0, "dupe": 0, "del": 0})
        d["scan"] += 1
        if rec["ours"]:
            d["ours"] += 1
    thread_of_id = dict((r["id"], r["thread"]) for r in records)
    for g in plan:
        d = per.setdefault(g["thread"], {"scan": 0, "ours": 0, "dupe": 0, "del": 0})
        d["dupe"] += len(g["delete"])
    for i in deleted:
        th = thread_of_id.get(i, 0)
        per.setdefault(th, {"scan": 0, "ours": 0, "dupe": 0, "del": 0})["del"] += 1
    for th in sorted(per.keys(), key=_thsort):
        d = per[th]
        name = room_label(th)
        print("  стая", str("?" if th is None else th).rjust(3), name.ljust(30),
              "прочетени", str(d["scan"]).rjust(4),
              "| наши", str(d["ours"]).rjust(4),
              "| повторения", str(d["dupe"]).rjust(4),
              "| изтрити", str(d["del"]).rjust(4))
    print("")
    if not plan and not victims:
        print("  Няма намерени повторения. Нищо за триене.")
    for g in plan[:60]:
        print("  [стая " + str(g["thread"]) + "] пазя " + str(g["keep"]) +
              " | трия " + ", ".join(str(x) for x in g["delete"]))
        print("       " + (g["text"][:90] or "-"))
    if len(plan) > 60:
        print("  ... още", len(plan) - 60, "групи (виж", PLAN_FILE + ")")
    if blocked:
        print("")
        print("  ПРЕГРАДА - НЕ пипам", len(blocked), "id-та:")
        for i, why in blocked[:20]:
            print("     ", i, "-", why)
        if len(blocked) > 20:
            print("      ... още", len(blocked) - 20, "(всеки е изписан по-горе)")
    print("")
    print("  общо кандидати за триене:", len(victims))
    if dry:
        print("  РЕЖИМ ПРОБА - НИЩО НЕ Е ИЗТРИТО.")
        print("  За реално триене: DEDUPE_DRY=0")
    else:
        print("  изтрити (по сметка на Telegram):", len(deleted),
              "| пропаднали:", len(failed))
        if failed:
            print("  пропаднали id-та:", ", ".join(str(x) for x in failed[:30]))
    print("  извиквания към Telegram:", CALLS["n"])


def write_plan(chat, plan, victims, records):
    try:
        with open(PLAN_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "chat": str(chat),
                "mode": MODE,
                "dry": DRY,
                "groups": plan,
                "delete_ids": victims,
                "scanned": len(records),
            }, f, ensure_ascii=False, indent=1)
        print("  планът е записан в", PLAN_FILE,
              "- може да се пусне после с DEDUPE_MODE=ids DEDUPE_IDS_FILE=" + PLAN_FILE)
    except Exception as e:
        print("  не можах да запиша плана:", str(e)[:120])


# ---------------------------------------------------------------- режими
def choose_probe(is_channel):
    kind = PROBE_KIND
    if kind == "auto":
        kind = "forward" if (is_channel and SCRATCH) else "reply"
    if kind == "forward" and not SCRATCH:
        print("  DEDUPE_PROBE=forward иска DEDUPE_SCRATCH (или ADMIN_CHAT_ID). Минавам на reply.")
        kind = "reply"
    if kind == "forward" and not is_channel and not ALLOW_NOTHREAD:
        print("  ОТКАЗ: forward-сондата не вижда стаите, а групата е форум.")
        print("  Или DEDUPE_PROBE=reply, или DEDUPE_ALLOW_NOTHREAD=1 (само за оглед).")
        return None
    if kind == "forward" and not is_channel:
        print("  ВНИМАНИЕ: forward-сондата НЕ дава стая. DEDUPE_ALLOW_NOTHREAD=1 значи")
        print("  само ОГЛЕД - без доказана стая вратата отказва всяко триене в групата.")
    return kind


def run_scan(chat, is_channel, only_thread=None):
    # Първо ПОЛИТИКАТА (без мрежа), чак после Telegram.
    if is_channel and not ALLOW_CHANNEL:
        print("  ОТКАЗ: в канал постовете нямат поле 'from' - НЕ мога да докажа,")
        print("  че постът е на бота, а не на собственика. Пусни с DEDUPE_ALLOW_CHANNEL=1")
        print("  и задължително първо с DEDUPE_DRY=1.")
        return 3
    kind = choose_probe(is_channel)
    if not kind:
        return 2
    if WIPE and only_thread is not None and CONFIRM != "WIPE":
        print("  ОТКАЗ: DEDUPE_WIPE=1 иска и DEDUPE_CONFIRM=WIPE.")
        return 5
    if not DRY and CONFIRM != "DELETE" and not (WIPE and CONFIRM == "WIPE"):
        print("  ОТКАЗ: реалното триене иска DEDUPE_CONFIRM=DELETE (предпазител).")
        return 12

    me_id, me_name = get_me()
    if not me_id:
        print("  getMe не мина - спирам."); return 1
    print("  бот:", "@" + str(me_name), "id", me_id)

    mx = probe_max_id(chat)
    if not mx:
        print("  чатът е недостъпен:", chat, "- спирам."); return 4
    lo = max(1, mx - WINDOW + 1)
    protect = _protect_from_env()
    pin = pinned_id(chat)
    if pin:
        protect.add(pin)
        print("  пазя закаченото съобщение", pin,
              "(Bot API дава само последното закачено - другите пази с PROTECT_IDS)")
    ids = [i for i in range(mx, lo - 1, -1) if i not in KEEP_IDS and i not in protect]
    print("  прозорец:", lo, "..", mx, "| id-та:", len(ids))

    records, alive, dead, stopped = scan(chat, ids, kind, SCRATCH, me_id, is_channel)
    print("  живи", alive, "| мъртви/несъществуващи", dead,
          "| със съдържание", len(records), ("| СПРЯН ПО ТАВАН" if stopped else ""))

    usable = []
    skipped_human, skipped_room4, skipped_unknown = 0, 0, 0
    for r in records:
        if r["thread"] is None:
            skipped_unknown += 1
            continue
        if r["thread"] in FORBIDDEN_THREADS:
            skipped_room4 += 1
            continue
        if only_thread is not None and r["thread"] != only_thread:
            continue
        if r["ours"] is False and not ALLOW_HUMAN:
            skipped_human += 1
            continue
        usable.append(r)
    if skipped_room4:
        print("  стая 4 - прескочени", skipped_room4, "съобщения (само хора, желязно правило)")
    if skipped_unknown:
        print("  НЕДОКАЗАНА стая - прескочени", skipped_unknown, "съобщения.")
        print("  Не мога да докажа, че не са в стая 4, значи не ги пипам.")
    if skipped_human:
        print("  чужди/човешки - прескочени", skipped_human, "съобщения")

    threads_by_id = dict((r["id"], r["thread"]) for r in records)

    if WIPE and only_thread is not None:
        victims = [r["id"] for r in usable]
        plan = [{"thread": only_thread, "kind": "wipe", "keep": 0,
                 "delete": victims, "text": "ПЪЛНО ИЗЧИСТВАНЕ на стая " + str(only_thread)}]
    else:
        groups = group_messages(usable, SIM)
        plan, victims = plan_from_groups(groups, protect)

    victims, blocked = guard(victims, protect, threads_by_id)
    # Планът се подрязва до ОЦЕЛЯЛОТО - иначе dedupe_plan.json щеше да носи
    # преградените id-та нататък към режим ids. Точно това беше преносителят.
    safe_set = set(victims)
    for g in plan:
        g["delete"] = [i for i in g["delete"] if i in safe_set]
    plan = [g for g in plan if g["delete"]]
    write_plan(chat, plan, victims, records)

    deleted, failed = [], []
    if not DRY and victims:
        done, failed, refused = delete_guarded(chat, victims, threads_by_id, protect)
        blocked = blocked + refused
        ref_ids = set(i for i, _ in refused)
        deleted = [i for i in victims if i not in failed and i not in ref_ids]
        if not EXACT:
            print("  бележка: пакетното deleteMessages не потвърждава поединично;",
                  "за точен отчет пусни с DEDUPE_EXACT=1")
    title = ("ОТЧЕТ - " + ("КАНАЛ" if is_channel else "ГРУПА") + " " + str(chat) +
             (" | стая " + str(only_thread) if only_thread is not None else ""))
    report(title, plan, victims, blocked, records, deleted, failed, DRY)
    return 0


def run_ids(chat):
    ids = _ids_from_env()
    if not ids:
        print("  Няма id-та. Подай DEDUPE_IDS='101 102 103' или DEDUPE_IDS_FILE=dedupe_plan.json")
        return 6
    protect = _protect_from_env()
    pin = pinned_id(chat)
    if pin:
        protect.add(pin)
    is_channel = (str(chat) == str(CHANNEL_ID))

    # Преди беше guard(ids, protect, {}) - празна карта на стаите, тоест
    # НУЛА знание, а преградата пускаше незнанието. Така id от стая 4 се триеше.
    # Сега всяко id се сондира и стаята му се ДОКАЗВА, иначе не се пипа.
    if is_channel:
        print("  каналът няма стаи - стая 4 е структурно невъзможна тук.")
    else:
        print("  сондирам всяко id, за да докажа В КОЯ СТАЯ е. Сондата се появява")
        print("  за миг в стаята и веднага се трие. Без доказана стая - не трия.")
    threads_by_id, unknown = resolve_threads(chat, ids, is_channel)
    if unknown:
        print("  недоказани (мъртви/недостъпни/над тавана):", len(unknown))

    safe, blocked = guard(ids, protect, threads_by_id)
    print("  подадени:", len(ids), "| за триене:", len(safe), "| преградени:", len(blocked))
    deleted, failed = [], []
    if not DRY:
        if CONFIRM != "DELETE":
            print("  ОТКАЗ: реалното триене по списък иска DEDUPE_CONFIRM=DELETE.")
            return 7
        done, failed, refused = delete_guarded(chat, safe, threads_by_id, protect)
        blocked = blocked + refused
        ref_ids = set(i for i, _ in refused)
        deleted = [i for i in safe if i not in failed and i not in ref_ids]
    recs = [{"id": i, "thread": threads_by_id.get(i), "ours": None}
            for i in sorted(threads_by_id.keys())]
    report("ОТЧЕТ - СПИСЪК id-та в " + str(chat), [], safe, blocked, recs,
           deleted, failed, DRY)
    return 0


# ---------------------------------------------------------------- самопроверка
def selftest():
    ok, bad = 0, []

    def chk(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    chk("norm-кирилица", norm("Арсенал 2:1 Челси!!") == "арсенал 2 1 челси")
    chk("norm-празно", norm(None) == "")
    chk("norm-интервали", norm("  А   Б  ") == "а б")
    chk("norm-еднакви", norm("<b>Гол!</b>") == norm("ГОЛ"))

    chk("key-текст", content_key({"text": "Здравей"})[0] == "text")
    chk("key-подпис", content_key({"caption": "Здравей"})[1] == norm("Здравей"))
    chk("key-снимка", content_key({"photo": [{"file_unique_id": "AQ"}]})[1] == "photo:AQ")
    chk("key-нищо", content_key({}) is None)

    chk("thread-general", thread_of({}) == 1)
    chk("thread-26", thread_of({"message_thread_id": 26}) == 26)
    chk("author-from", author_id({"from": {"id": 7}}) == 7)
    chk("author-канал", author_id({"sender_chat": {"id": -100}}) is None)

    recs = [
        {"id": 10, "thread": 26, "kind": "text", "key": "гол", "text": "Гол", "ours": True},
        {"id": 12, "thread": 26, "kind": "text", "key": "гол", "text": "Гол", "ours": True},
        {"id": 14, "thread": 26, "kind": "text", "key": "друго", "text": "Друго", "ours": True},
        {"id": 16, "thread": 27, "kind": "text", "key": "гол", "text": "Гол", "ours": True},
    ]
    groups = group_messages(recs, 1.0)
    plan, victims = plan_from_groups(groups, set())
    chk("група-само-в-стаята", len(plan) == 1)
    chk("пази-най-новото", plan and plan[0]["keep"] == 12)
    chk("трие-по-старото", victims == [10])
    chk("не-пипа-друга-стая", 16 not in victims and 14 not in victims)

    chk("norm-маха-тагове", norm("<b>Гол!</b>") == "гол")
    chk("norm-пази-по-малко", norm("2 < 3") == "2 3")

    # Различни СЛЕД нормализация (18 00 срещу 18 30), но много близки.
    near = [
        {"id": 30, "thread": 5, "kind": "text",
         "key": norm("Левски Ботев днес в 18 00 на стадион Герена"), "text": "a", "ours": True},
        {"id": 31, "thread": 5, "kind": "text",
         "key": norm("Левски Ботев днес в 18 30 на стадион Герена"), "text": "b", "ours": True},
    ]
    chk("тестът-е-за-близки", near[0]["key"] != near[1]["key"])
    p2, v2 = plan_from_groups(group_messages(near, 0.94), set())
    chk("почти-еднакви", v2 == [30])
    p3, v3 = plan_from_groups(group_messages(near, 1.0), set())
    chk("SIM=1-само-точни", v3 == [])

    s, b = guard([4, 5, 26, 500, 501], set([501]), {500: 4})
    chk("преграда-контейнери", 4 not in s and 5 not in s and 26 not in s)
    chk("преграда-стая4", 500 not in s)
    chk("преграда-защитени", 501 not in s)
    chk("преграда-пуска-нормалните", s == [])
    s2, b2 = guard([700, 701], set(), {700: 26, 701: 27})
    chk("преграда-не-е-параноична", s2 == [700, 701])
    # ТОЧНАТА стара дупка: режим ids викаше guard с ПРАЗНА карта на стаите
    # и празнотата минаваше за разрешение.
    s3, b3 = guard([900, 901], set(), {})
    chk("преграда-празна-карта-отказва-всичко", s3 == [] and len(b3) == 2)

    # Неизвестна стая (None) не бива да чупи сортиранията в плана/отчета.
    nn = [{"id": 40, "thread": None, "kind": "text", "key": "х", "text": "х", "ours": True},
          {"id": 41, "thread": None, "kind": "text", "key": "х", "text": "х", "ours": True},
          {"id": 42, "thread": 9, "kind": "text", "key": "х", "text": "х", "ours": True}]
    try:
        p4, v4 = plan_from_groups(group_messages(nn, 1.0), set())
        chk("None-стая-не-чупи-сортирането", v4 == [40])
        s4, b4 = guard(v4, set(), dict((r["id"], r["thread"]) for r in nn))
        chk("None-стая-не-се-трие", s4 == [])
    except TypeError:
        chk("None-стая-не-чупи-сортирането", False)

    # ---- ВРАТАТА: чистата логика (без мрежа) ----
    chk("врата-стая4-отказ", delete_verdict(500, 4, set())[0] is False)
    chk("врата-стая4-причина", "4" in delete_verdict(500, 4, set())[1])
    chk("врата-контейнер-отказ", delete_verdict(4, 26, set())[0] is False)
    chk("врата-контейнер-27", delete_verdict(27, 26, set())[0] is False)
    chk("врата-неизвестна-стая", delete_verdict(777, None, set())[0] is False)
    chk("врата-нечетима-стая", delete_verdict(778, "кой знае", set())[0] is False)
    chk("врата-защитено", delete_verdict(779, 26, set([779]))[0] is False)
    chk("врата-нормален-дубликат", delete_verdict(800, 26, set())[0] is True)
    chk("врата-канал-нула", delete_verdict(801, 0, set())[0] is True)
    chk("врата-невалидно", delete_verdict("х", 26, set())[0] is False)

    # forward-сондата в групата НЕ доказва стая -> None, не 0 (старият бъг)
    chk("стая-forward-в-група", record_thread({}, "forward", False) is None)
    chk("стая-reply-4", record_thread({"message_thread_id": 4}, "reply", False) == 4)
    chk("стая-канал", record_thread({}, "forward", True) == 0)

    # ---- ВРАТАТА: доказваме, че до Telegram НЕ се стига ----
    calls = []
    real_api = globals()["api"]
    globals()["api"] = lambda method, **p: (calls.append((method, p)) or {"ok": True})
    try:
        d1, f1, r1 = delete_guarded(-100, [500], {500: 4}, set())
        chk("стая4-НУЛА-извиквания", calls == [] and d1 == 0 and len(r1) == 1)
        del calls[:]
        d2, f2, r2 = delete_guarded(-100, [4], {4: 26}, set())
        chk("контейнер-НУЛА-извиквания", calls == [] and d2 == 0 and len(r2) == 1)
        del calls[:]
        d3, f3, r3 = delete_guarded(-100, [777], {}, set())
        chk("неизвестна-стая-НУЛА-извиквания", calls == [] and d3 == 0 and len(r3) == 1)
        del calls[:]
        d4, f4, r4 = delete_guarded(-100, [800], {800: 26}, set())
        chk("нормален-дубликат-минава", d4 == 1 and r4 == [] and len(calls) == 1)
        chk("минава-през-триещия-метод",
            calls and calls[0][0] in ("deleteMessages", "deleteMessage"))
        del calls[:]
        # смесен списък: минава САМО чистото, останалото пада
        d5, f5, r5 = delete_guarded(-100, [500, 4, 777, 801],
                                    {500: 4, 4: 26, 801: 26}, set())
        chk("смесено-минава-само-чистото", d5 == 1 and len(r5) == 3)
        chk("смесено-не-праща-забраненото",
            len(calls) == 1 and "801" in str(calls[0][1]) and "500" not in str(calls[0][1]))
        del calls[:]
        # резето: никой не може да трие покрай delete_guarded
        dn, fn = _telegram_delete(-100, [900])
        chk("резе-затворено-по-подразбиране", calls == [] and dn == 0 and fn == [900])
        chk("резе-остава-затворено", _GATE["open"] is False)
        del calls[:]
        # собствената сонда се трие (иначе боклук в стаята), но само тя
        _OWN_SCRATCH.add(9001)
        d6, f6, r6 = delete_guarded(-100, [9001], {}, set())
        chk("собствена-сонда-се-трие", d6 == 1 and r6 == [])
        chk("сондата-се-забравя-веднага", 9001 not in _OWN_SCRATCH)
        del calls[:]
        d7, f7, r7 = delete_guarded(-100, [9001], {}, set())
        chk("сонда-втори-път-отказ", calls == [] and d7 == 0 and len(r7) == 1)
    finally:
        globals()["api"] = real_api
        del DELETE_REFUSALS[:]

    chk("сходство-къси", similar("да", "не", 0.9) is False)
    chk("сходство-дълги", similar(norm("едно две три четири пет"),
                                  norm("едно две три четири пет!"), 0.9) is True)

    print("SELFTEST", ok, "/", ok + len(bad), ("OK" if not bad else "ПАДНАЛИ: " + ", ".join(bad)))
    return 0 if not bad else 1


# ---------------------------------------------------------------- вход
def main():
    if "--selftest" in sys.argv or os.environ.get("DEDUPE_SELFTEST") == "1":
        return selftest()
    print("")
    print("GREEN PICKS - хирургичен чистач на повторения")
    print("режим:", MODE, "| прозорец:", WINDOW, "| сходство:", SIM,
          "| проба:", ("ДА - нищо няма да се изтрие" if DRY else "НЕ - ТРИЕ НАИСТИНА"))
    if not BOT_TOKEN:
        print("Липсва BOT_TOKEN"); return 1
    if MODE == "channel":
        return run_scan(CHANNEL_ID, True, None)
    if MODE == "thread":
        if TARGET_THREAD <= 0:
            print("  Задай DEDUPE_THREAD (напр. 26)"); return 8
        if TARGET_THREAD in FORBIDDEN_THREADS:
            print("  ОТКАЗ: стая", TARGET_THREAD, "е САМО ЗА ХОРА. Ботът не я пипа."); return 9
        if not CHAT_ID:
            print("  Липсва CHAT_ID"); return 10
        return run_scan(CHAT_ID, False, TARGET_THREAD)
    if MODE == "ids":
        chat = CHANNEL_ID if (os.environ.get("DEDUPE_TARGET") == "channel") else CHAT_ID
        return run_ids(chat)
    if MODE == "scan":
        if not CHAT_ID:
            print("  Липсва CHAT_ID"); return 10
        return run_scan(CHAT_ID, False, None)
    print("  Непознат DEDUPE_MODE:", MODE, "- позволени: scan | thread | channel | ids")
    return 11


if __name__ == "__main__":
    sys.exit(main())
