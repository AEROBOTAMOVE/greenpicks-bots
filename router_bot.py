# -*- coding: utf-8 -*-

"""
GREEN PICKS — БОТ №3 „РУТЕРЪТ" 🚚
СЪРЦЕТО НА СИСТЕМАТА: типстърът поства САМО в канала (@greenpicksbg),
рутерът хваща всеки нов пост и го КОПИРА в правилната стая на групата:
  #Футбол/футболен текст  -> стая ⚽ (5)
  #Баскетбол              -> стая 🏀 (6)
  #ТенисМаса              -> стая 🏓 (7)
  #Волейбол               -> стая 🏐 (8)
  без разпознат спорт     -> стая 🎯 Пикове на деня (4)
Ботът трябва да е админ и в КАНАЛА (за да вижда постовете), и в ГРУПАТА.
Пуска се на всеки 10 мин от GitHub Actions. Помни докъде е стигнал в router_state.json.

⚠️ ДЕЛИ ОПАШКАТА СЪС support_bot.py (същия BOT_TOKEN). Опашката на Telegram е
ЕДНА за бот, а потвърждаването е ГЛОБАЛНО: getUpdates с offset=N трие ВСИЧКИ
ъпдейти под N, независимо чии са и независимо какво пише в allowed_updates.
Докато рутерът минаваше сам, всяко негово потвърждение изяждаше и личните
съобщения до бота — въпросите на хората изчезваха безшумно, без ред в лога.
Затова тук има две правила, огледални на тези в support_bot.py:
  1. ЕДИН РЕЧНИК — искаме СЪЮЗА (channel_post + message + callback_query).
     Два различни списъка на един бот се презаписват и Telegram спира да
     създава ъпдейтите на другия.
  2. ЧУЖДОТО НЕ СЕ МАРКИРА — спираме на ПЪРВОТО лично съобщение и оставяме
     offset-а пред него. Съпортът ще го вземе до 15 минути и опашката тръгва.
Двамата се изчакват. Спре ли единият да се пуска, другият изостава, докато
Telegram сам не изхвърли ъпдейта (24 часа). Не е елегантно, но не губи поща.
"""
import json
import os
import re
import sys
import inspect
import time
import urllib.error
import urllib.request
import urllib.parse

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")                    # групата (-100...)
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")  # каналът
STATE_FILE = "router_state.json"

# стаите по спорт (тема-id в групата)
ROOM_PICKS = int(os.environ.get("PICKS_THREAD_ID", "4"))
ROOM_RESULTS = int(os.environ.get("RESULTS_THREAD_ID", "9"))   # ✅ Резултати
ROOM_WINS = int(os.environ.get("WINS_THREAD_ID", "10"))        # 🏆 Печеливши фишове
SPORT_ROOMS = [
    (int(os.environ.get("FOOTBALL_THREAD_ID", "5")),
     # 🔴 КИРИЛИЦАТА ЛИПСВАШЕ (11.08.2026). Списъкът имаше „champions league"
     # на латиница, но не и „Шампионската лига" — а типстърът пише на български.
     # Измерено с истински постове: „Кой ще гледа Шампионската лига?" отиваше
     # в стаята на фишовете вместо във футбола.
     # „левски" НЕ бива да хваща „Левски Лукойл" — това е баскетболният клуб.
     # Същото за „черно море" срещу „Черно море Тича".
     r"#футбол|футбол|цска|левски(?! лукойл)|лудогорец|ботев|берое|славия|"
     r"черно море(?! тича)|"
     r"шампионска|шампионската лига|лига европа|лига на конференциите|"
     r"висша лига|ла лига|серия а|бундеслига|лига 1|"
     r"champions league|premier league|la liga|serie a|bundesliga|"
     r"голмайстор|football|soccer"),
    (int(os.environ.get("BASKET_THREAD_ID", "6")),
     # Български клубове: „Балкан Ботевград" и „Левски Лукойл" са БАСКЕТБОЛ.
     # pick_rooms пробва баскета ПРЕДИ футбола, затова „Левски Лукойл"
     # не отива при футболния Левски.
     r"#баскетбол|#баскет|баскет|балкан ботевград|рилски спортист|"
     r"левски лукойл|черно море тича|"
     r"basketball|\bnba\b|\bwnba\b|евролига|euroleague"),
    (int(os.environ.get("TT_THREAD_ID", "7")),
     r"#тенисмаса|тенис на маса|table tennis|пинг понг"),
    (int(os.environ.get("VOLLEY_THREAD_ID", "8")),
     r"#волейбол|#волей|волейбол|volleyball"),
]
# Имена за четимост (и за да може самопроверката да ги назове, а не да брои
# индекси в списък — индекс, разменен при редакция, е тих дефект).
ROOM_FOOT, ROOM_BASK, ROOM_TT, ROOM_VOLLEY = (r[0] for r in SPORT_ROOMS)

# 🔴 РАЗДЕЛЕНО 11.08.2026 по изричното правило на собственика:
#   стая 9  „Резултати и статистика" = РАВНОСМЕТКАТА (отчет, процент, обзор)
#   стая 10 „Печеливши фишове"       = ИЗХОДЪТ НА ФИШ (мина / не мина, къде се скъса)
#
# Дотук едно RESULT_PAT ловеше и двете и пращаше всичко в 9. Следствието се
# виждаше в групата: губещ фиш („❌ не мина") влизаше САМО в стая 9 — тоест в
# стаята на статистиката — а стаята на фишовете не научаваше нищо за него.
# Печелившият пък влизаше и в двете. Тоест стая 10 показваше само победите:
# точно „фалшивата успеваемост", която пинът ѝ обещава, че няма да прави.
# Оценителят (scorer.py) беше поправен на 11.08; рутерът мина по същия път сега.
STAT_PAT = r"отчет|равносметка|статистик|успеваемост|обзор|процент|#резултат"
# Изход на фиш — И победата, И загубата. Двете отиват на ЕДНО място: стая 10.
FISH_PAT = (r"✅|❌|уцели|уцелен|паднал|спечелихме|загубихме|не мина|"
            r"печеливш|ударихме|зелен[оа]|\+\s?\d+([.,]\d+)?\s?(ед|лв|unit)|#печеливш")


# ═══════════════════════ ЕДНА ТРЪБА КЪМ ТЕЛЕГРАМ (429) ════════════════════
# 🔴 ДЕФЕКТ Б, намерен 01.09.2026. Рутерът беше единствената жива тръба в
# проекта, която НЕ четеше parameters.retry_after. Телеграм при 429 казва
# „изчакай N секунди“; старият api() (router_bot.py:92-109) печаташе
# „copyMessage HTTP 429“ и връщаше None — тоест блъскаше и се предаваше.
# Другите го четат от седмици: support_bot.py:776, scorer.py:227,
# predictor.py:1517, poster.py:32. Тук просто липсваше.
#
# И най-лошото: дефект Б умножаваше дефект А. 429 при залп от постове ->
# copyMessage връща None -> старият ред 230 вече беше мръднал offset-а ->
# постът се губи БЕЗВЪЗВРАТНО, а тефтерът пазеше само едно число и не
# оставяше следа какво липсва.
TG_OPITI = int(os.environ.get("TG_OPITI") or "4")            # опита на едно викане
TG_PODRAZBIRANE = int(os.environ.get("TG_PODRAZBIRANE") or "5")   # 429 без число
TG_TAVAN_EDNO = int(os.environ.get("TG_TAVAN_EDNO") or "60")      # таван на едно чакане
TG_TAVAN_OBSHTO = int(os.environ.get("TG_TAVAN_OBSHTO") or "180")  # таван за целия рън

# ШЕВ за самопроверката. Тестът подменя ТУК и вика ИСТИНСКИЯ api(), вместо да
# преписва логиката му. Тест, който преписва кода, не може да гръмне — това
# вече ни е излизало в този проект (фантомният стоп на AERO).
_otvori = urllib.request.urlopen
_ZASPIVANIYA = []       # всяко чакане в секунди — за да бъде ИЗМЕРЕНО
_BEZ_SUN = False        # вдига се САМО от самопроверката


def _spi(sekundi):
    """Едно чакане. Записва се, за да може да бъде проверено, не предположено."""
    _ZASPIVANIYA.append(sekundi)
    if not _BEZ_SUN:
        time.sleep(sekundi)


def retry_after_ot(surovo):
    """Изважда parameters.retry_after от тялото на 429. Няма ли го — 0."""
    try:
        telo = json.loads(surovo) or {}
        return int((telo.get("parameters") or {}).get("retry_after") or 0)
    except Exception:                           # noqa: BLE001
        return 0


def chakane_za_429(surovo):
    """Колко да чакаме: казаното от Телеграм; няма ли — подразбиране; с таван.

    Таванът е срещу абсурдни числа: рънът има 25 минути, а видяно е
    retry_after от часове. По-добре пропуснат опит сега, отколкото убит рън.
    """
    wait = retry_after_ot(surovo)
    if wait <= 0:
        wait = TG_PODRAZBIRANE
    return min(wait, TG_TAVAN_EDNO)


def tryba_chete_429(fn):
    """Дали дадена тръба чете retry_after. Мери ИЗВОРА ѝ, не ѝ вярва.

    Връща True / False / None (неизмерима). Ползва се и на живо, в
    support_hooks(), за да се ОБЯВИ чужда тръба, която блъска при 429.
    """
    if fn is None:
        return None
    try:
        izvor = inspect.getsource(fn)
    except Exception:                           # noqa: BLE001
        # НИЩО тук не бива да гърми: router.yml:71 пуска селфтеста ПРЕДИ рънa,
        # тоест паднал селфтест = спрени карти. Не се измери -> „неизмерима“.
        return None
    return "retry_after" in izvor


def api(method, **params):
    """ЕДИНСТВЕНАТА тръба на рутера към Телеграм. И getUpdates, и copyMessage."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    for opit in range(TG_OPITI):
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data)
        try:
            with _otvori(req, timeout=25) as r:
                resp = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429 and opit < TG_OPITI - 1:
                wait = chakane_za_429(body)
                if sum(_ZASPIVANIYA) + wait > TG_TAVAN_OBSHTO:
                    print(f"429 при {method}: чаканото минава тавана за рън "
                          f"({TG_TAVAN_OBSHTO} сек) — спирам да чакам. Ъпдейтът")
                    print("остава необработен и offset-ът НЕ го подминава.")
                    return None
                print(f"429 при {method} — чакам {wait} сек (казано от Телеграм).")
                _spi(wait)
                continue
            if e.code == 409:
                # Друг процес чете същата опашка в същия миг. Не повтаряме:
                # offset-ът не е мръднал, след 10 минути пак.
                print(f"409 Conflict при {method} — друг чете опашката сега.")
                return None
            print(f"{method} HTTP {e.code}: {body[:300]}")
            return None
        except Exception as e:                  # noqa: BLE001
            print(f"{method} FAIL: {e}")
            return None
        if not resp.get("ok"):
            print(f"{method} ERROR:", resp)
            return None
        return resp["result"]
    print(f"{method}: {TG_OPITI} опита не стигнаха (429 докрай).")
    return None


def pick_rooms(text):
    """Връща СПИСЪК от стаи — един пост може да отиде в 2-3 стаи!
    Пример: губещ футболен фиш -> ⚽ + 🏆 (изходът му е фишова история);
            равносметка на деня -> ✅ Резултати и статистика."""
    t = (text or "").lower()
    rooms = []
    # 1) всички разпознати спортове (комбо-фиш с 2 спорта -> 2 стаи)
    for tid, pat in [SPORT_ROOMS[2], SPORT_ROOMS[3], SPORT_ROOMS[1], SPORT_ROOMS[0]]:
        if re.search(pat, t) and tid not in rooms:
            rooms.append(tid)
    # 2) равносметка / статистика -> ✅ Резултати и статистика
    if re.search(STAT_PAT, t) and ROOM_RESULTS not in rooms:
        rooms.append(ROOM_RESULTS)
    # 3) изход на фиш, ВСЕ ЕДНО дали е минал -> 🏆 Печеливши фишове
    if re.search(FISH_PAT, t) and ROOM_WINS not in rooms:
        rooms.append(ROOM_WINS)
    if not rooms:
        rooms = [ROOM_PICKS]   # без нищо разпознато -> 🎯 Фишове на деня
    return rooms[:3]           # максимум 3 стаи, без спам


def support_hooks():
    """Закача съпорта към ТАЗИ опашка. Връща (модул, състояние) или (None, None).

    ЗАЩО (намерено на живо на 29.07.2026)
    Опашката на Telegram е ЕДНА на бот и потвърждаването е ГЛОБАЛНО. Досега
    рутерът и съпортът се пускаха поотделно със същия токен и си отстъпваха
    учтиво: рутерът спираше пред първото лично съобщение, съпортът — пред
    първия пост от канала. На теория се изчакват. На практика опашката ЗАПОЧВА
    с пост от канала, значи съпортът се блъскаше в него на първата стъпка и
    offset-ът му НИКОГА не мръдна от нула. Измерено: рутерът беше на ъпдейт
    320389746, съпортът на 0, с нула обработени съобщения — а човек беше писал
    „/start" още в 18:00 и не получи отговор.

    Затова вече има САМО ЕДИН четец: този. Постовете от канала ги разнася сам,
    а личните съобщения подава на съпорта и продължава — без да спира.
    Съпортът се пуска с SUPPORT_POLLING=0 и вече не пипа опашката.
    """
    try:
        import support_bot as S
    except Exception as e:                      # noqa: BLE001
        print("съпортът не се зареди (" + str(e)[:90] + ") — личните съобщения")
        print("ще бъдат само маркирани, за да не задръстят опашката.")
        return None, None
    # ТРЕТАТА ТРЪБА. Съпорт-тръбата не минава през нашия api() — тя си има
    # свой. Не можем да я сменим оттук, но можем да я ИЗМЕРИМ и да обявим,
    # ако блъска при 429. Мълчаливо предположение = точно дефект Б.
    znae = tryba_chete_429(getattr(S, "api", None))
    if znae is False:
        print("⚠ съпорт-тръбата НЕ чете retry_after — при 429 ще блъска.")
    elif znae is None:
        print("⚠ съпорт-тръбата не може да бъде измерена за 429.")
    try:
        return S, S.load_state()
    except Exception as e:                      # noqa: BLE001
        print("паметта на съпорта не се чете (" + str(e)[:70] + ").")
        return S, None


# ═════════════════════════════ ПАМЕТТА НА РУТЕРА ══════════════════════════
# Дотук тефтерът пазеше ЕДНО число: {"offset": 320389819} (прочетено живо на
# 01.09.2026). Тоест ако нещо се загубеше, нямаше и следа, че се е загубило.
# Сега пази и: колко опита има всеки провален ъпдейт, кои стаи вече са
# получили дадения пост, и списък на ПРЕСКОЧЕНИТЕ. Тефтерът се комитва от
# router.yml („Save state“), значи следата се вижда ОТВЪН — логът на Actions
# не се вижда отвън (мерено 11.08.2026).
MAX_OPITI = int(os.environ.get("ROUTER_MAX_OPITI") or "3")
MAX_PROPUSNATI = 20


def prazno_sastoyanie():
    return {"offset": 0, "opiti": {}, "chastichni": {}, "propusnati": []}


def zaredi_sastoyanie(pat=None):
    """Чете тефтера. СТАРИЯТ формат (само offset) се чете без гърмеж."""
    st = prazno_sastoyanie()
    pat = pat or STATE_FILE
    if not os.path.exists(pat):
        return st
    try:
        with open(pat, encoding="utf-8-sig") as f:
            surovo = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        print("WARN: повреден router state — започвам от 0.")
        return st
    if not isinstance(surovo, dict):
        return st
    try:
        st["offset"] = int(surovo.get("offset", 0))
    except (TypeError, ValueError):
        st["offset"] = 0
    if isinstance(surovo.get("opiti"), dict):
        for k, v in surovo["opiti"].items():
            try:
                st["opiti"][str(k)] = int(v)
            except (TypeError, ValueError):
                continue
    if isinstance(surovo.get("chastichni"), dict):
        for k, v in surovo["chastichni"].items():
            if isinstance(v, list):
                st["chastichni"][str(k)] = list(v)
    if isinstance(surovo.get("propusnati"), list):
        st["propusnati"] = surovo["propusnati"][-MAX_PROPUSNATI:]
    return st


def pochisti_sastoyanie(st):
    """Маха бележките за ъпдейти, които вече са минали. Иначе растат вечно."""
    off = st.get("offset", 0)
    for ime in ("opiti", "chastichni"):
        for k in list(st.get(ime) or {}):
            try:
                mine = int(k) <= off
            except (TypeError, ValueError):
                mine = True
            if mine:
                del st[ime][k]
    st["propusnati"] = (st.get("propusnati") or [])[-MAX_PROPUSNATI:]
    return st


def zapishi_sastoyanie(st, pat=None):
    pochisti_sastoyanie(st)
    with open(pat or STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)


# ══════════════════════════════ РАЗНАСЯНЕ НА ПОСТ ═════════════════════════
def raznesi_post(post, veche=()):
    """Копира един пост в стаите му. Връща (наред, доставени_стаи).

    ВЕЧЕ ДОСТАВЕНОТО НЕ СЕ ПРАЩА ПАК. Един пост може да иска три стаи; ако
    втората гръмне, при повторния опит първата НЕ бива да получи дубъл.
    Изтриване в Телеграм е без път назад (правило 3), а дубълът се вижда от
    хората — затова частичната доставка се ПОМНИ, не се гадае.
    """
    text = post.get("text") or post.get("caption") or ""
    mid = post.get("message_id")
    dostaveni = list(veche)
    nared = True
    for room in pick_rooms(text):
        if room in dostaveni:
            print(f"Пост {mid} вече е в стая {room} — не го пращам пак.")
            continue
        res = api("copyMessage", chat_id=CHAT_ID,
                  from_chat_id=CHANNEL_ID,
                  message_id=mid,
                  message_thread_id=room)
        if res is not None:
            dostaveni.append(room)
            print(f"Пост {mid} -> стая {room}")
        else:
            nared = False
            print(f"Пост {mid} НЕ мина (стая {room}).")
    return nared, dostaveni


def obsluji_lichno(u, S, sup_state, budget):
    """Лично съобщение или бутон. Връща (наред, нов_бюджет, обслужени).

    „Наред“ значи РАБОТАТА Е СВЪРШЕНА. Липсващ съпорт, нечетима негова памет
    и изчерпан таван НЕ са свършена работа — старият код ги маркираше за
    обработени и съобщението изчезваше безшумно.
    """
    uid = u.get("update_id", 0)
    cb = u.get("callback_query")
    msg = u.get("message") or {}
    if S is None:
        print("Ъпдейт " + str(uid) + ": съпортът не е зареден — НЕ го обявявам")
        print("за обработен. Ще бъде опитан пак.")
        return False, budget, 0
    try:
        if cb:
            S.handle_callback(cb)
            return True, budget, 1
        if sup_state is None:
            print("Ъпдейт " + str(uid) + ": паметта на съпорта не се чете —")
            print("оставям съобщението, вместо да го изям.")
            return False, budget, 0
        text = (msg.get("text") or "").strip().lower()
        is_cmd = (text == "/o" or text.startswith("/o ")
                  or text.startswith("/o@"))
        if is_cmd or S.target_from_card(msg.get("reply_to_message")):
            S.handle_relay(msg, sup_state)          # отговор от екипа
            return True, budget, 1
        if (msg.get("chat") or {}).get("type") == "private":
            if budget <= 0:
                print("Ъпдейт " + str(uid) + ": таванът за предаване е стигнат —")
                print("оставям го за следващото минаване, вместо да го изям.")
                return False, budget, 0
            if S.handle_private(msg, sup_state, budget) == 1:
                budget -= 1
            return True, budget, 1
        return True, budget, 0      # чуждо съобщение в група — няма работа
    except Exception as e:                      # noqa: BLE001
        # Едно счупено съобщение не бива да спира цялата опашка ЗАВИНАГИ —
        # затова има брояч на опитите, а не сляпо повтаряне.
        print("съпортът се спъна в ъпдейт " + str(uid) + ": " + str(e)[:90])
        return False, budget, 0


def obhodi(updates, st, S=None, sup_state=None, budget=0):
    """Обхожда опашката. ЕДИНСТВЕНОТО място, където offset-ът напредва.

    🔴 ДЕФЕКТ А, намерен 01.09.2026. В старата версия
        router_bot.py:227  last_id = max(last_id, u.get("update_id", 0))
        router_bot.py:230  last_id = max(last_id, u.get("update_id", 0))
    се изпълняваха БЕЗУСЛОВНО: ред 227 — вътре в блока, който току-що е хванал
    изключение на съпорта; ред 230 — ПРЕДИ copyMessage изобщо да е опитан.
    Тоест едно 429 или един мрежов трепет и постът изчезваше завинаги.

    ЗАЩО НЕ САМО „не мърдай при провал“: offset-ът на Телеграм е ВОДОМЕР, не
    списък — потвърдиш ли 101, потвърждаваш и 100. Значи ъпдейт, който гърми
    всеки път, би блокирал опашката ВЕЧНО (безкраен цикъл от преработване).
    Затова три неща заедно:
      1. БАРИЕРА — спираме на първия провал и нищо след него не се пипа.
         Ако продължавахме, следващите биха се обработили СЕГА и ПАК при
         повторението — тоест дубли в стаите.
      2. БРОЯЧ — MAX_OPITI пъти (по един опит на рън, рънът е на 10 мин),
         после ъпдейтът се ПРЕСКАЧА и опашката тръгва.
      3. ОБЯВЯВАНЕ — прескочените влизат в тефтера и в лога с 🔴. Прескочен
         ъпдейт е ЗАГУБА; загуба, която се крие, е втори дефект върху първия.
    """
    routed = 0
    answered = 0
    spryan = None
    novo_propusnati = []
    for u in updates:
        uid = int(u.get("update_id") or 0)
        klyuch = str(uid)
        if u.get("callback_query") or u.get("message"):
            nared, budget, n = obsluji_lichno(u, S, sup_state, budget)
            answered += n
            kakvo = "лично съобщение / бутон"
        else:
            nared = True
            kakvo = "ъпдейт без работа"
            post = u.get("channel_post")
            chat = (post or {}).get("chat") or {}
            if post and str(chat.get("id")) == str(CHANNEL_ID):
                veche = st["chastichni"].get(klyuch) or []
                nared, dostaveni = raznesi_post(post, veche)
                routed += max(0, len(dostaveni) - len(veche))
                kakvo = "пост " + str(post.get("message_id"))
                if nared:
                    st["chastichni"].pop(klyuch, None)
                else:
                    st["chastichni"][klyuch] = dostaveni

        if nared:
            st["offset"] = max(st["offset"], uid)
            st["opiti"].pop(klyuch, None)
            continue

        opit = int(st["opiti"].get(klyuch) or 0) + 1
        st["opiti"][klyuch] = opit
        if opit >= MAX_OPITI:
            belezhka = {
                "update_id": uid,
                "kakvo": kakvo,
                "opiti": opit,
                "koga": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
            }
            st["propusnati"].append(belezhka)
            novo_propusnati.append(belezhka)
            print("🔴 ПРЕСКАЧАМ ъпдейт " + str(uid) + " (" + kakvo + ") след "
                  + str(opit) + " неуспешни опита.")
            print("   НЕ Е обработен. Записан е в " + STATE_FILE + ".")
            st["offset"] = max(st["offset"], uid)
            st["opiti"].pop(klyuch, None)
            st["chastichni"].pop(klyuch, None)
            continue

        spryan = uid
        print("Ъпдейт " + str(uid) + " (" + kakvo + ") не мина — опит "
              + str(opit) + " от " + str(MAX_OPITI) + ".")
        print("   Спирам дотук: offset-ът остава ПРЕД него, за да не се загуби.")
        break

    return {"routed": routed, "answered": answered, "spryan": spryan,
            "propusnati": novo_propusnati, "budget": budget}


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)

    st = zaredi_sastoyanie()
    if st["opiti"]:
        print("Чакащи неуспешни ъпдейти от предишен рън: "
              + ", ".join(k + " (опит " + str(v) + " от " + str(MAX_OPITI) + ")"
                          for k, v in sorted(st["opiti"].items())))

    # СЪЮЗЪТ, не само channel_post: стесним ли списъка, Telegram спира да създава
    # личните съобщения до бота и съпортът остава без поща (виж главата на файла).
    updates = api("getUpdates", offset=st["offset"] + 1, timeout=0,
                  allowed_updates='["channel_post", "message", "callback_query"]')
    if updates is None:
        sys.exit(1)
    if not updates:
        print("Няма нови постове.")
        return

    # ЕДИН ЧЕТЕЦ ЗА ДВЕТЕ РАБОТИ (виж support_hooks по-горе).
    S, sup_state = support_hooks()
    budget = getattr(S, "MAX_FORWARDS", 25) if S else 0
    itog = obhodi(updates, st, S, sup_state, budget)

    zapishi_sastoyanie(st)

    # Паметта на съпорта (кой какво е питал, дневните тавани) — записва я той,
    # не ние, за да остане форматът на едно място. Без този запис същият човек
    # би получавал един и същи отговор пак и пак.
    if S is not None and sup_state is not None:
        try:
            S.save_state(sup_state)
        except Exception as e:                  # noqa: BLE001
            print("паметта на съпорта не се записа (" + str(e)[:70] + ") —")
            print("следващото минаване може да повтори отговор.")

    print("Разнесени " + str(itog["routed"]) + " поста, обслужени "
          + str(itog["answered"]) + " съобщения до бота. Offset="
          + str(st["offset"]) + ".")
    if itog["spryan"] is not None:
        print("Опашката е СПРЯНА пред ъпдейт " + str(itog["spryan"])
              + " — ще бъде опитан пак след 10 минути.")
    if itog["propusnati"]:
        print("🔴 ПРЕСКОЧЕНИ В ТОЗИ РЪН: " + str(len(itog["propusnati"]))
              + ". Виж " + STATE_FILE + ".")


def chetat_se_klyuchove(izvor=None):
    """Кои променливи на средата чете ТОЗИ файл."""
    src = izvor if izvor is not None else open(__file__, encoding="utf-8").read()
    edno = re.findall(r"os\.environ\.get\(\s*[\"\']([A-Z_0-9]+)[\"\']", src)
    dve = re.findall(r"os\.environ\[\s*[\"\']([A-Z_0-9]+)[\"\']", src)
    return set(edno) | set(dve)


def adresni(klyuchove):
    """От прочетените — тези, чиято липса мести СЪОБЩЕНИЕТО, не настройка.

    🔴 ПРАВИЛО, НЕ СПИСЪК. Номерът на стая и адресът на чата решават КЪДЕ
    отива постът; таваните и опитите решават само колко бързо. Първото
    мълчи, когато сгреши — затова само то се изисква.
    """
    return {k for k in klyuchove
            if k.endswith("_THREAD_ID") or k in ("CHAT_ID", "CHANNEL_ID")}


def stypki_s_rutera(papka=None):
    """[(файл, име на стъпка, подадени ключове)] за всяка стъпка, която
    пуска рутера НАИСТИНА (пускането с --selftest не праща никъде)."""
    bazi = [papka] if papka else [".github/workflows", "../.github/workflows"]
    for baza in bazi:
        if not baza or not os.path.isdir(baza):
            continue
        namereni = []
        for ime in sorted(os.listdir(baza)):
            if not ime.endswith(".yml"):
                continue
            # 🔴 io НЕ Е ВНЕСЕН В ТОЗИ ФАЙЛ. Първата редакция ползваше
            # io.open и NameError-ът се глътна от широкия except — функцията
            # обяви НУЛА стъпки, тоест грешка в кода мина за празнота в
            # данните. Точно класът, който тази проверка гони.
            #
            # Затова: голо open, и уловът е САМО за файлови грешки.
            try:
                with open(os.path.join(baza, ime), encoding="utf-8") as f:
                    redove = f.read().split("\n")
            except (OSError, UnicodeDecodeError):
                continue
            zap = [i for i, l in enumerate(redove)
                   if l.strip().startswith("- name:")] + [len(redove)]
            for a, b in zip(zap, zap[1:]):
                blok = redove[a:b]
                puska = any("router_bot.py" in l and "selftest" not in l
                            and l.strip().startswith("run:") for l in blok)
                if not puska:
                    continue
                klyuchove = set()
                for l in blok:
                    m = re.match(r"\s{10}([A-Z_0-9]+)\s*:", l)
                    if m:
                        klyuchove.add(m.group(1))
                namereni.append((ime, blok[0].strip()[:60], klyuchove))
        if namereni:
            return namereni
    return []


def selftest():
    """🔴 ДОБАВЕНА 11.08.2026. Рутерът беше ЕДИНСТВЕНИЯТ жив бот без самопроверка
    — и точно затова разделянето стая 9 / стая 10 му се размина цял ден, докато
    всички останали ботове го получиха. Проверката е чиста: не пипа мрежа.
    """
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # --- 🔴 КОЙТО ПУСКА РУТЕРА, ДЪЛЖИ МУ АДРЕСИТЕ (05.09.2026)
    #
    # predict.yml пускаше router_bot.py без НИТО ЕДИН номер на стая и ботът
    # падаше на заковани резерви 5/6/7/8/4/9/10. Смени ли се стая през vars,
    # router.yml щеше да я уважи, а рутерът от predict.yml щеше да пише в
    # старата — без нито един ред грешка.
    #
    # Проверката ОТКРИВА: чете кои променливи ползва самият файл, отделя
    # адресните от настройките и иска всяка стъпка, която пуска рутера, да
    # ги подава всичките.
    _adr = adresni(chetat_se_klyuchove())
    check("адресните ключове се намират", len(_adr) >= 7)
    check("таваните НЕ се броят за адресни",
          not {k for k in _adr if k.startswith("TG_")})
    _stypki = stypki_s_rutera()
    check("стъпките, които пускат рутера, се намират", len(_stypki) >= 2)
    _lipsi = []
    for _f, _n, _kl in _stypki:
        _m = sorted(_adr - _kl)
        if _m:
            _lipsi.append(_f + " -> " + ", ".join(_m))
    check("никой не пуска рутера без адреси: " + ("; ".join(_lipsi) or "-"),
          not _lipsi)

    # --- разпознаване по спорт
    check("футболът отива в стаята си", ROOM_FOOT in pick_rooms("Лудогорец днес"))
    check("баскетът отива в стаята си", ROOM_BASK in pick_rooms("NBA нощта"))
    check("тенисът на маса отива в стаята си", ROOM_TT in pick_rooms("тенис на маса WTT"))
    check("волейболът отива в стаята си", ROOM_VOLLEY in pick_rooms("волейбол PlusLiga"))
    # 🔴 КИРИЛСКИТЕ ЛИГИ. Типстърът пише на български, а списъкът имаше само
    # „champions league". Измерено: „Кой ще гледа Шампионската лига?" отиваше
    # в стаята на фишовете вместо във футбола.
    for _p in ("Кой ще гледа Шампионската лига?",
               "Квалификации за Лига Европа тази вечер",
               "Ботев Пловдив с нов треньор", "Ла Лига стартира"):
        check("кирилската лига стига до футбола: " + _p[:26],
              ROOM_FOOT in pick_rooms(_p))
    check("Балкан Ботевград е баскетбол",
          ROOM_BASK in pick_rooms("Балкан Ботевград със силен трансфер"))
    check("Левски Лукойл е баскетбол, не футбол",
          ROOM_BASK in pick_rooms("Левски Лукойл с нов играч")
          and ROOM_FOOT not in pick_rooms("Левски Лукойл с нов играч"))
    check("футболният Левски си остава футбол",
          ROOM_FOOT in pick_rooms("Левски победи с 2:0"))
    check("два спорта -> две стаи",
          len([r for r in pick_rooms("комбо: футбол + баскетбол")
               if r in (ROOM_FOOT, ROOM_BASK)]) == 2)
    check("без разпознат спорт -> стаята на фишовете",
          pick_rooms("добро утро на всички") == [ROOM_PICKS])

    # --- САМОТО РАЗДЕЛЯНЕ (заради него е написана тази проверка)
    _gubesht = pick_rooms("❌ фишът не мина, скъса се на третия крак")
    check("ГУБЕЩ фиш стига до стая 10", ROOM_WINS in _gubesht)
    check("губещ фиш НЕ се води статистика", ROOM_RESULTS not in _gubesht)
    _pechelivsh = pick_rooms("✅ спечелихме, и петте крака минаха")
    check("ПЕЧЕЛИВШ фиш стига до стая 10", ROOM_WINS in _pechelivsh)
    check("печеливш фиш НЕ се води статистика", ROOM_RESULTS not in _pechelivsh)
    _stat = pick_rooms("равносметка на деня: 12 от 19, успеваемост 63 процента")
    check("равносметката стига до стая 9", ROOM_RESULTS in _stat)
    check("равносметката НЕ се води фиш", ROOM_WINS not in _stat)
    check("думата отчет води в статистиката",
          ROOM_RESULTS in pick_rooms("отчет за седмицата"))
    # Смесен пост (и разбор, и изход на фиш) има право и на двете стаи.
    _smesen = pick_rooms("равносметка: ❌ първият фиш падна, вторият мина")
    check("смесеният пост стига и до двете", ROOM_RESULTS in _smesen and ROOM_WINS in _smesen)

    # --- предпазители
    check("най-много три стаи",
          len(pick_rooms("равносметка ❌ футбол баскетбол волейбол тенис на маса")) <= 3)
    check("празен текст не гърми", pick_rooms("") == [ROOM_PICKS])
    check("None не гърми", pick_rooms(None) == [ROOM_PICKS])
    # Двата речника не бива да се препокриват по ключова дума — иначе всеки пост
    # би влизал и в двете стаи и разделянето не значи нищо.
    for _d in ("отчет", "равносметка", "успеваемост", "обзор"):
        check(_d + " не е фишова дума", not re.search(FISH_PAT, _d))
    for _d in ("не мина", "паднал", "спечелихме", "печеливш"):
        check(_d + " не е статистическа дума", not re.search(STAT_PAT, _d))

    # ═══════════════ ДЕФЕКТ Б: 429 и retry_after (ИЗМЕРЕНО) ═══════════════
    # Тестът подменя ШЕВА _otvori и вика ИСТИНСКИЯ api(). Не преписва логиката.
    import io as _io
    import tempfile as _tmp

    def _telo(rezultat=True):
        return json.dumps({"ok": True, "result": rezultat}).encode()

    class _Otgovor:
        def __init__(self, telo):
            self._t = telo

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._t

    def _greshka(kod, params=None):
        """Връща ФАБРИКА за грешка, не готова грешка.

        🔴 Намерено на 01.09.2026 в самия този тест: HTTPError.read() изпразва
        буфера си. `[_greshka(...)] * 9` слагаше ЕДИН обект девет пъти, второто
        четене връщаше празно тяло, retry_after ставаше 0 и чакането падаше на
        подразбирането — тоест тестът мереше СЕБЕ СИ, не кода. На живо всяка
        заявка ражда нова грешка, значи трябва и тук.
        """
        telo = {"ok": False, "error_code": kod}
        if params is not None:
            telo["parameters"] = params
        surovo = json.dumps(telo).encode()

        def _napravi():
            return urllib.error.HTTPError(
                "http://t", kod, "err", {}, _io.BytesIO(surovo))
        return _napravi

    def _transport(shema):
        """shema: списък; елемент = грешка за хвърляне или None (=успех)."""
        broi = {"n": 0}

        def _o(req, timeout=0):
            i = broi["n"]
            broi["n"] += 1
            stapka = shema[i] if i < len(shema) else None
            if stapka is not None:
                raise stapka()          # ПРЯСНА грешка, не преизползвана
            return _Otgovor(_telo())
        return _o, broi

    global _otvori, _BEZ_SUN
    _star_otvori, _star_bez = _otvori, _BEZ_SUN
    _BEZ_SUN = True
    try:
        check("таванът на опитите е поне 2 (иначе тестовете долу лъжат)",
              MAX_OPITI >= 2)

        # 🔴 ПРОВЕРКА НА САМАТА ПРОВЕРКА. Ако транспортът връща един и същ
        # HTTPError, второто e.read() е ПРАЗНО и всяко следващо чакане тихо
        # пада на подразбирането — тоест тестовете за 429 биха мерили себе си.
        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, {"retry_after": 60})] * 2)
        api("copyMessage")
        check("тестовият транспорт дава ПРЯСНА грешка всеки път",
              _ZASPIVANIYA[:2] == [60, 60])

        # --- 429: чете ли се retry_after
        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, {"retry_after": 7})])
        _r = api("copyMessage", chat_id=1)
        check("429: чакаме ТОЧНО каквото каза Телеграм (7 сек)",
              _ZASPIVANIYA == [7])
        check("429: след чакането ПРОБВАМЕ ПАК и успяваме",
              _r is True and _br["n"] == 2)

        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, {})])
        api("copyMessage")
        check("429 без retry_after: разумно подразбиране "
              + str(TG_PODRAZBIRANE), _ZASPIVANIYA == [TG_PODRAZBIRANE])

        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, None)])
        api("copyMessage")
        check("429 съвсем без parameters: пак подразбиране",
              _ZASPIVANIYA == [TG_PODRAZBIRANE])

        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, {"retry_after": 3600})])
        api("copyMessage")
        check("429 с абсурдно число: таван " + str(TG_TAVAN_EDNO) + " сек",
              _ZASPIVANIYA == [TG_TAVAN_EDNO])

        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, {"retry_after": 1})] * 10)
        _r = api("copyMessage")
        check("429 докрай: None след точно " + str(TG_OPITI) + " опита, не вечно",
              _r is None and _br["n"] == TG_OPITI)

        # --- таван за целия рън
        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, {"retry_after": 60})] * 9)
        api("copyMessage")
        check("общото чакане не минава тавана за рън ("
              + str(TG_TAVAN_OBSHTO) + " сек)",
              sum(_ZASPIVANIYA) <= TG_TAVAN_OBSHTO)
        _otvori, _br = _transport([_greshka(429, {"retry_after": 10})])
        _r = api("copyMessage")
        check("изчерпан таван за рън: спираме да чакаме, не блъскаме",
              _r is None and _br["n"] == 1
              and sum(_ZASPIVANIYA) <= TG_TAVAN_OBSHTO)

        # --- ВСЯКА ТРЪБА минава през същия помощник
        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, {"retry_after": 3})])
        api("getUpdates", offset=1)
        check("ТРЪБА 1 (getUpdates) уважава 429", _ZASPIVANIYA == [3])

        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(429, {"retry_after": 2})])
        _n, _d = raznesi_post({"message_id": 1, "text": "добро утро"})
        check("ТРЪБА 2 (copyMessage/raznesi_post) уважава 429",
              _ZASPIVANIYA == [2] and _n is True and _d == [ROOM_PICKS])

        # ТРЪБА 3 е съпортът: свой api(), не минава оттук — затова се МЕРИ.
        check("проверчикът на тръби познава тръба, която ЧЕТЕ retry_after",
              tryba_chete_429(api) is True
              or tryba_chete_429(chakane_za_429) is True)

        def _tryba_bez_429(x):
            return x
        check("проверчикът на тръби НЕ е печат: хваща тръба без retry_after",
              tryba_chete_429(_tryba_bez_429) is False)
        check("проверчикът на тръби казва „неизмерима“, не „наред“",
              tryba_chete_429(None) is None)
        try:
            import support_bot as _SB
            check("ТРЪБА 3 (съпортът) чете retry_after",
                  tryba_chete_429(getattr(_SB, "api", None)) is True)
        except Exception as _e:                 # noqa: BLE001
            print("⚠ съпортът не се зареди за проверка ("
                  + str(_e)[:60] + ") — тръба 3 остава НЕИЗМЕРЕНА.")

        # --- не-429 грешки не чакат напразно
        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(409, {})])
        _r = api("copyMessage")
        check("409 Conflict не се блъска повторно",
              _r is None and _br["n"] == 1 and _ZASPIVANIYA == [])
        del _ZASPIVANIYA[:]
        _otvori, _br = _transport([_greshka(400, {})])
        _r = api("copyMessage")
        check("HTTP 400 не чака напразно",
              _r is None and _br["n"] == 1 and _ZASPIVANIYA == [])

        # ═══════════ ДЕФЕКТ А: offset-ът, броячът, бариерата ═══════════════
        del _ZASPIVANIYA[:]
        _post = {"update_id": 500, "channel_post": {
            "message_id": 77, "text": "добро утро",
            "chat": {"id": CHANNEL_ID}}}

        _otvori, _br = _transport([])                    # всичко минава
        _st = prazno_sastoyanie()
        _it = obhodi([_post], _st)
        check("А: при УСПЕХ offset-ът напредва", _st["offset"] == 500)
        check("А: при успех броячът на опитите е чист", _st["opiti"] == {})
        check("А: успешният пост се брои", _it["routed"] == 1)

        _otvori, _br = _transport([_greshka(400, {})] * 9)
        _st = prazno_sastoyanie()
        _it = obhodi([_post], _st)
        check("А: при ПРОВАЛ offset-ът НЕ мърда", _st["offset"] == 0)
        check("А: провалът вдига брояча на 1", _st["opiti"] == {"500": 1})
        check("А: провалът спира опашката пред себе си", _it["spryan"] == 500)

        _st = prazno_sastoyanie()
        for _i in range(MAX_OPITI - 1):
            _otvori, _br = _transport([_greshka(400, {})] * 9)
            obhodi([_post], _st)
        check("А: броячът расте при всеки нов провал",
              _st["opiti"] == {"500": MAX_OPITI - 1} and _st["offset"] == 0)
        _otvori, _br = _transport([_greshka(400, {})] * 9)
        _it = obhodi([_post], _st)
        check("А: след " + str(MAX_OPITI) + " опита ъпдейтът се ПРЕСКАЧА",
              _st["offset"] == 500 and _st["opiti"] == {})
        # Индексът е ЗАЩИТЕН нарочно: празен списък трябва да даде ЧЕРВЕН РЕД
        # С ИМЕ, а не IndexError. Гейтът пада и в двата случая, но само единият
        # казва коя защита е паднала.
        _b0 = (_st["propusnati"] or [{}])[0]
        check("А: прескачането се ОБЯВЯВА в тефтера",
              len(_st["propusnati"]) == 1
              and _b0.get("update_id") == 500
              and _b0.get("opiti") == MAX_OPITI)
        check("А: обявеното казва КАКВО е пропуснато",
              "77" in str(_b0.get("kakvo")))
        check("А: прескачането се обявява и в изхода на рънa",
              len(_it["propusnati"]) == 1)

        # --- БАРИЕРАТА (срещу дубли)
        _post2 = {"update_id": 501, "channel_post": {
            "message_id": 78, "text": "волейбол", "chat": {"id": CHANNEL_ID}}}
        _otvori, _br = _transport([_greshka(400, {})] * 9)
        _st = prazno_sastoyanie()
        _it = obhodi([_post, _post2], _st)
        check("А: БАРИЕРА — след провала следващият НЕ се обработва",
              _br["n"] == 1 and "501" not in _st["opiti"])
        check("А: бариерата не подминава провала",
              _st["offset"] == 0 and _it["spryan"] == 500)

        # --- ЧАСТИЧНА ДОСТАВКА: две стаи, втората гърми
        _post3 = {"update_id": 502, "channel_post": {
            "message_id": 79, "text": "футбол ❌ фишът не мина",
            "chat": {"id": CHANNEL_ID}}}
        check("подготовка: постът наистина иска две стаи",
              len(pick_rooms("футбол ❌ фишът не мина")) == 2)
        _st = prazno_sastoyanie()
        _otvori, _br = _transport([None, _greshka(400, {})])
        obhodi([_post3], _st)
        check("А: частичната доставка се ПОМНИ",
              len(_st["chastichni"].get("502") or []) == 1)
        check("А: частичният пост не мести offset-а", _st["offset"] == 0)
        _dostavena = (_st["chastichni"].get("502") or [None])[0]
        _otvori, _br = _transport([])
        obhodi([_post3], _st)
        check("А: при повторение доставената стая НЕ получава ДУБЪЛ",
              _br["n"] == 1)
        check("А: след пълната доставка следата се чисти",
              _st["offset"] == 502 and _st["chastichni"] == {}
              and _st["opiti"] == {})
        check("А: доставената стая е истинска стая",
              _dostavena in (ROOM_FOOT, ROOM_WINS))

        # --- СЪПОРТ-ТРЪБАТА: провалите ѝ вече не изяждат съобщението
        _msg = {"update_id": 700, "message": {
            "text": "здрасти", "chat": {"id": 1, "type": "private"}}}

        _st = prazno_sastoyanie()
        obhodi([_msg], _st, S=None)
        check("А: липсващ съпорт вече НЕ изяжда съобщението",
              _st["offset"] == 0 and _st["opiti"] == {"700": 1})

        class _SpanatS:
            MAX_FORWARDS = 5

            @staticmethod
            def target_from_card(x):
                return None

            @staticmethod
            def handle_private(m, s, b):
                raise RuntimeError("нарочно счупен за теста")

        _st = prazno_sastoyanie()
        obhodi([_msg], _st, S=_SpanatS, sup_state={}, budget=5)
        check("А: спънат съпорт вече НЕ изяжда съобщението",
              _st["offset"] == 0 and _st["opiti"] == {"700": 1})

        class _DobarS:
            MAX_FORWARDS = 5

            @staticmethod
            def target_from_card(x):
                return None

            @staticmethod
            def handle_private(m, s, b):
                return 1

        _st = prazno_sastoyanie()
        _it = obhodi([_msg], _st, S=_DobarS, sup_state={}, budget=5)
        check("А: обслуженото лично съобщение МЕСТИ offset-а",
              _st["offset"] == 700 and _it["answered"] == 1)

        _st = prazno_sastoyanie()
        obhodi([_msg], _st, S=_DobarS, sup_state={}, budget=0)
        check("А: изчерпаният таван оставя съобщението за следващия рън",
              _st["offset"] == 0 and _st["opiti"] == {"700": 1})

        _st = prazno_sastoyanie()
        obhodi([_msg], _st, S=_DobarS, sup_state=None, budget=5)
        check("А: нечетима памет на съпорта не изяжда съобщението",
              _st["offset"] == 0 and _st["opiti"] == {"700": 1})

        # ═══════════════════ ТЕФТЕРЪТ: четене, чистене, рязане ═════════════
        _pat = os.path.join(_tmp.gettempdir(), "router_state_selftest.json")
        _st = prazno_sastoyanie()
        _st["offset"] = 600
        _st["opiti"] = {"590": 2, "610": 1}
        _st["chastichni"] = {"590": [5], "610": [6]}
        _st["propusnati"] = [{"update_id": i} for i in range(40)]
        zapishi_sastoyanie(_st, _pat)
        _ob = zaredi_sastoyanie(_pat)
        check("тефтер: бележките ПОД offset-а се чистят (не растат вечно)",
              "590" not in _ob["opiti"] and "590" not in _ob["chastichni"])
        check("тефтер: чакащите НАД offset-а оцеляват",
              _ob["opiti"].get("610") == 1
              and _ob["chastichni"].get("610") == [6])
        # ДВЕТЕ СТРАНИ ПООТДЕЛНО. Рязането е на две места (при запис и при
        # четене); едно измерване през двете не доказва нито едното — махнеш
        # ли което и да е, другото го прикрива. Проверено с мутация.
        with open(_pat, encoding="utf-8") as _f:
            _surov = json.load(_f)
        check("тефтер/ЗАПИС: самият ФАЙЛ пази най-много "
              + str(MAX_PROPUSNATI) + " пропуснати",
              len(_surov.get("propusnati") or []) == MAX_PROPUSNATI)
        with open(_pat, "w", encoding="utf-8") as _f:
            json.dump({"offset": 600,
                       "propusnati": [{"update_id": i} for i in range(40)]}, _f)
        _ob2 = zaredi_sastoyanie(_pat)
        check("тефтер/ЧЕТЕНЕ: чужд препълнен файл също се реже до "
              + str(MAX_PROPUSNATI),
              len(_ob2["propusnati"]) == MAX_PROPUSNATI)
        check("тефтер: пропуснатите се режат до " + str(MAX_PROPUSNATI),
              len(_ob["propusnati"]) == MAX_PROPUSNATI)
        check("тефтер: offset-ът се връща цял", _ob["offset"] == 600)

        with open(_pat, "w", encoding="utf-8") as _f:
            _f.write('{"offset": 320389819}')
        _ob = zaredi_sastoyanie(_pat)
        check("тефтер: СТАРИЯТ формат (само offset) се чете без гърмеж",
              _ob["offset"] == 320389819 and _ob["opiti"] == {}
              and _ob["propusnati"] == [])
        with open(_pat, "w", encoding="utf-8") as _f:
            _f.write("{счупен")
        try:
            _ob = zaredi_sastoyanie(_pat)
            _cyalo = _ob["offset"] == 0
        except Exception as _e:                 # noqa: BLE001
            print("   (повреденият тефтер хвърли " + type(_e).__name__ + ")")
            _cyalo = False
        check("тефтер: повреден файл не гърми, а почва от 0", _cyalo)
        try:
            os.remove(_pat)
        except OSError:
            pass
    finally:
        _otvori, _BEZ_SUN = _star_otvori, _star_bez
        del _ZASPIVANIYA[:]

    print("САМОПРОВЕРКА: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   🔴 " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    main()
