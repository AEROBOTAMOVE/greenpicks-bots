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


def api(method, **params):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"{method} HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"{method} FAIL: {e}")
        return None
    if not resp.get("ok"):
        print(f"{method} ERROR:", resp)
        return None
    return resp["result"]


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
    try:
        return S, S.load_state()
    except Exception as e:                      # noqa: BLE001
        print("паметта на съпорта не се чете (" + str(e)[:70] + ").")
        return S, None


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)

    offset = 0
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8-sig") as f:
                st = json.load(f)
            offset = int(st.get("offset", 0)) if isinstance(st, dict) else 0
        except (json.JSONDecodeError, OSError, ValueError):
            print("WARN: повреден router state — започвам от 0.")

    # СЪЮЗЪТ, не само channel_post: стесним ли списъка, Telegram спира да създава
    # личните съобщения до бота и съпортът остава без поща (виж главата на файла).
    updates = api("getUpdates", offset=offset + 1, timeout=0,
                  allowed_updates='["channel_post", "message", "callback_query"]')
    if updates is None:
        sys.exit(1)
    if not updates:
        print("Няма нови постове.")
        return

    routed = 0
    answered = 0
    last_id = offset
    S, sup_state = support_hooks()
    budget = getattr(S, "MAX_FORWARDS", 25) if S else 0

    for u in updates:
        # ЕДИН ЧЕТЕЦ ЗА ДВЕТЕ РАБОТИ. По-рано тук се СПИРАШЕ пред всяко лично
        # съобщение, за да го остави на съпорта — и точно това го задушаваше
        # (виж support_hooks по-горе). Сега личното се обслужва НА МЯСТО и
        # обхождането продължава, тоест offset-ът върви и опашката не засяда.
        cb = u.get("callback_query")
        msg = u.get("message")
        if cb or msg:
            if S is None:
                print("Ъпдейт " + str(u.get("update_id", 0)) + ": съпортът липсва —")
                print("маркирам го, за да не запуши опашката.")
            else:
                try:
                    if cb:
                        S.handle_callback(cb)
                        answered += 1
                    elif sup_state is not None:
                        text = (msg.get("text") or "").strip().lower()
                        is_cmd = (text == "/o" or text.startswith("/o ")
                                  or text.startswith("/o@"))
                        if is_cmd or S.target_from_card(msg.get("reply_to_message")):
                            S.handle_relay(msg, sup_state)      # отговор от екипа
                        elif (msg.get("chat") or {}).get("type") == "private":
                            if budget > 0:
                                if S.handle_private(msg, sup_state, budget) == 1:
                                    budget -= 1
                                answered += 1
                            else:
                                print("Таванът за предаване е стигнат — спирам да")
                                print("обслужвам, но offset-ът се мести напред.")
                except Exception as e:          # noqa: BLE001
                    # Едно счупено съобщение не бива да спира цялата опашка.
                    print("съпортът се спъна в ъпдейт "
                          + str(u.get("update_id", 0)) + ": " + str(e)[:90])
            last_id = max(last_id, u.get("update_id", 0))
            continue

        last_id = max(last_id, u.get("update_id", 0))
        post = u.get("channel_post")
        if not post:
            continue
        chat = post.get("chat") or {}
        if str(chat.get("id")) != str(CHANNEL_ID):
            continue   # не е нашият канал
        text = post.get("text") or post.get("caption") or ""
        for room in pick_rooms(text):
            res = api("copyMessage", chat_id=CHAT_ID,
                      from_chat_id=CHANNEL_ID,
                      message_id=post.get("message_id"),
                      message_thread_id=room)
            if res is not None:
                routed += 1
                print(f"Пост {post.get('message_id')} -> стая {room}")
            else:
                print(f"Пост {post.get('message_id')} НЕ мина (стая {room}).")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"offset": last_id}, f)

    # Паметта на съпорта (кой какво е питал, дневните тавани) — записва я той,
    # не ние, за да остане форматът на едно място. Без този запис същият човек
    # би получавал един и същи отговор пак и пак.
    if S is not None and sup_state is not None:
        try:
            S.save_state(sup_state)
        except Exception as e:                  # noqa: BLE001
            print("паметта на съпорта не се записа (" + str(e)[:70] + ") —")
            print("следващото минаване може да повтори отговор.")

    print("Разнесени " + str(routed) + " поста, обслужени "
          + str(answered) + " съобщения до бота. Offset=" + str(last_id) + ".")


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

    print("САМОПРОВЕРКА: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   🔴 " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    main()
