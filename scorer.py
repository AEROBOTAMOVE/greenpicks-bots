# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ОЦЕНИТЕЛЯТ 📊

ЗАЩО СЪЩЕСТВУВА
Ботът пускаше прогнози и никой никога не проверяваше дали е познал. Стая 9
„Резултати и статистика" показваше случайни резултати от чужди първенства, а
стая 10 „Печеливши фишове" стоеше празна, защото нямаше кой да я пълни.
Продукт, който твърди „показваме и загубите", а не показва нищо, не е продукт.

КАКВО ПРАВИ
1. Чете predict_log.json — там predictor.py записва всяко свое твърдение:
   кой срещу кого, кого е посочил, с каква вероятност и колко звезди.
2. За всяко неоценено твърдение пита ESPN как е свършил мачът.
3. Пише ДВА поста:
     стая 9  — пълният отчет: познати И сгрешени, с процент за деня и общо
     стая 10 — само познатите, витрина
   Ако няма нито един завършил мач — не пише нищо. Тишината е за предпочитане.
4. Вдига „scored" на оценените, за да не се броят два пъти.

ЖЕЛЕЗНИ ПРАВИЛА
- Пише САМО в стаи 9 и 10. Всяка друга стая се отказва на изхода, преди мрежата.
- Никакви поучения, никакви коефициенти, никакви букмейкъри. Пазач на изхода.
- Загубите НЕ се крият и НЕ се трият. Точно те правят числото достоверно.
- Не е сигурен резултатът → мачът остава неоценен и се пробва пак утре.

ENV:
  BOT_TOKEN, CHAT_ID
  RESULTS_THREAD_ID (9)   ·  WINS_THREAD_ID (10)
  SCORE_DRY_RUN (0/1)     ·  SCORE_LOG_FILE (predict_log.json)
  SCORE_MAX_AGE_DAYS (5)  докога чакаме резултат, преди да се откажем

Файлът е без обратни наклонени черти, без обратни апострофи и без долар-скоба.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NL = chr(10)
SOFIA = ZoneInfo("Europe/Sofia")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = (os.environ.get("CHAT_ID") or "-1004426592150").strip()
CHANNEL_ID = (os.environ.get("CHANNEL_ID") or "-1004403334702").strip()

RESULTS_THREAD = (os.environ.get("RESULTS_THREAD_ID") or "9").strip()
WINS_THREAD = (os.environ.get("WINS_THREAD_ID") or "10").strip()
# Единствените две стаи, в които този файл има право да пише.
# Стая 4 „Фишове на деня": там излиза обзорът КАК СА МИНАЛИ фишовете.
# Поръчка на собственика: „Фишовете на деня трябва и там обзор."
PICKS_THREAD = (os.environ.get("PICKS_THREAD_ID") or "4").strip()
ALLOWED_THREADS = {RESULTS_THREAD, WINS_THREAD, PICKS_THREAD}

LOG_FILE = (os.environ.get("SCORE_LOG_FILE") or "predict_log.json").strip()
DRY_RUN = (os.environ.get("SCORE_DRY_RUN") or "").strip() in ("1", "true", "yes", "да")
MAX_AGE = max(1, min(30, int((os.environ.get("SCORE_MAX_AGE_DAYS") or "5").strip())))

UA = "Mozilla/5.0 (compatible; GreenRoomScorer/1.0)"
ESPN = "https://site.api.espn.com/apis/site/v2/sports"

# Кошница -> (спорт в адреса на ESPN, емоджи)
SPORT_PATH = {
    "football": ("soccer", "⚽"),
    "basketball": ("basketball", "\U0001f3c0"),
    "tennis": ("tennis", "\U0001f3be"),
    "hockey": ("hockey", "\U0001f3d2"),
    "baseball": ("baseball", "⚾"),
    "mma": ("mma", "\U0001f94a"),
    "volleyball": (None, "\U0001f3d0"),      # FIVB, не ESPN — виж по-долу
    "tabletennis": (None, "\U0001f3d3"),     # WTT, не ESPN
}

# СПОРТОВЕ БЕЗ ИЗТОЧНИК НА РЕЗУЛТАТИ.
#
# Тенисът на маса влиза тук след шест измервания на 04.08.2026, не по усещане:
#   1. WTT schedule.json — 1103 единици за събитие 3322, НИТО ЕДНО поле с
#      резултат. Има „ScheduleStatus: Official", тоест мачът се е състоял, но
#      кой е спечелил не пише никъде.
#   2. WTT results/ matches/ draw/ livescore/ matchresults/ medalists/
#      standings — празни или 404.
#   3. WTT статистиката по един ден (GetStatsByPlayer) отговаря, но си
#      ПРОТИВОРЕЧИ: при 40 мача 30% са двойки, в които И ДВАМАТА играчи имат
#      нула загуби, а са играли един срещу друг. Невъзможно.
#   4. TheSportsDB с безплатния ключ вече дава само футбол и мотоспорт.
#   5. ESPN не покрива тенис на маса.
#   6. Sofascore връща 403.
#
# Такава прогноза се затваря веднага след деня си с hit=None и се брои
# отделно. НЕ влиза в процента — измислен резултат е по-лош от липсващ.
NO_RESULT = {"tabletennis"}

# Думи, които НЕ ИЗЛИЗАТ навън. Същият пазач като в другите ботове.
BANNED = ["18+", "залагай отговорно",
          "коеф", "букмейкър", "odds",
          "заложи", "финансов съвет"]


def banned_word(text):
    low = (text or "").lower()
    for w in BANNED:
        if w in low:
            return w
    return None


def http_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def api(method, **params):
    """Bot API с изчакване при 429 — иначе последният пост тихо пада."""
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
                    ra = int(json.loads(body).get("parameters", {}).get("retry_after", 5))
                except Exception:
                    ra = 5
                print("  429 при " + method + " — чакам " + str(ra + 1) + " сек.")
                time.sleep(ra + 1)
                continue
            print(method + " HTTP " + str(e.code) + ": " + body[:150])
            return {}
        except Exception as e:                # noqa: BLE001
            print(method + " FAIL: " + str(e)[:120])
            return {}
    return {}


def post(thread, text):
    """ЕДИНСТВЕНИЯТ изход навън. Пазачът е ТУК, преди мрежата."""
    tid = str(thread or "").strip()
    if tid not in ALLOWED_THREADS:
        print("ОТКАЗ: стая " + tid + " не е на оценителя (само "
              + " и ".join(sorted(ALLOWED_THREADS)) + ").")
        return False
    bad = banned_word(text)
    if bad:
        print("ОТКАЗ: в текста се промъкна забранена дума (" + bad + ").")
        return False
    if DRY_RUN:
        print("--- СУХО, стая " + tid + " ---")
        print(text)
        print("---")
        return True
    p = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
         "disable_web_page_preview": "true"}
    if int(tid) > 1:
        p["message_thread_id"] = tid
    r = api("sendMessage", **p)
    ok = bool(r.get("ok"))
    print(("  пратено в стая " if ok else "  НЕ мина в стая ") + tid)
    return ok


def post_channel(text):
    """Обзорът отива И В КАНАЛА. Поръчка на собственика (05.08.2026).

    ЗАЩО НЕ МИНАВА ПРЕЗ post(): онзи пише в ГРУПАТА и пазачът му брои стаи.
    Каналът е друг чат, няма стаи и има свой ключ. Затова е отделен път —
    но със СЪЩИЯ пазач за забранени думи, защото каналът се вижда от всички
    и там грешката е най-скъпа.

    Дотук каналът беше „само за човека" и ботовете нямаха работа в него.
    Собственикът промени това за резултатите: „искаме всичко да си е вътре
    след края на деня". Обзорът е равносметка, не реклама — мястото му е там,
    където хората първо гледат.
    """
    if not str(CHANNEL_ID).strip():
        print("  каналът не е зададен — пропускам.")
        return False
    bad = banned_word(text)
    if bad:
        print("ОТКАЗ канал: забранена дума (" + bad + ").")
        return False
    if DRY_RUN:
        print("--- СУХО, КАНАЛ ---")
        print(text)
        print("---")
        return True
    r = api("sendMessage", chat_id=CHANNEL_ID, text=text, parse_mode="HTML",
            disable_web_page_preview="true")
    ok = bool(r.get("ok"))
    print("  обзорът в КАНАЛА: " + ("пратен" if ok else "НЕ мина"))
    return ok


# ------------------------------------------------------------------ РЕЗУЛТАТИ
def espn_result(rec):
    """Крайният резултат на един мач от ESPN. None = още не знаем.

    Връща (домакин_точки, гост_точки) или None. Търсим по деня на мача в
    същата лига, после сверяваме по id на отборите — имената се различават
    между източниците, id-тата не.
    """
    bucket = rec.get("bucket")
    path = (SPORT_PATH.get(bucket) or (None, ""))[0]
    slug = rec.get("slug")
    hid, aid = str(rec.get("home_id") or ""), str(rec.get("away_id") or "")
    if not path or not slug or not hid or not aid:
        return None

    den = rec.get("day") or ""
    if len(den) != 10:
        return None

    # ⚠️ ЧАСОВИТЕ ЗОНИ — намерено на живо на 04.08.2026.
    # Дневникът пази деня на мача по БЪЛГАРСКО време. ESPN подрежда срещите по
    # МЕСТНИЯ ден на състезанието. Мач в 03:00 българско на 31 юли е 20:00 в
    # Ню Йорк на 30 юли — и ESPN го дава под 20260730. Заради това тринадесет
    # американски и южноамерикански прогнози висяха неотсъдени: питахме за
    # грешния ден и получавахме чужди мачове.
    # Затова питаме и предния, и следващия ден. Отборните id-та са уникални,
    # тоест няма опасност да хванем друг мач по погрешка.
    try:
        d0 = datetime.strptime(den, "%Y-%m-%d")
    except Exception:                         # noqa: BLE001
        return None
    dni = [(d0 + timedelta(days=k)).strftime("%Y%m%d") for k in (0, -1, 1)]

    for day in dni:
        url = ESPN + "/" + path + "/" + slug + "/scoreboard?dates=" + day
        try:
            j = http_json(url)
        except Exception:                     # noqa: BLE001
            continue
        for ev in (j.get("events") or []):
            comps = ev.get("competitions") or []
            if not comps:
                continue
            comp = comps[0] or {}
            st = ((comp.get("status") or {}).get("type") or {})
            if not st.get("completed"):
                continue                      # още не е свършил
            got = {}
            for c in (comp.get("competitors") or []):
                tid = str(((c.get("team") or {}).get("id")) or "")
                try:
                    got[tid] = int(str(c.get("score")))
                except Exception:             # noqa: BLE001
                    got = {}
                    break
            if hid in got and aid in got:
                return got[hid], got[aid]
        time.sleep(0.25)
    return None


def name_in(name, text):
    """Името се среща в текста КАТО ОТДЕЛНА ДУМА, не завряно вътре в друга.

    ЗАЩО не просто „in": късо име се намира навсякъде. При проба „А" срещу „Б"
    низът „а" се намери вътре в „неразпознаваемо" и оценителят отсъди победа
    там, където изобщо не разбираше твърдението. Затова: къси имена под три
    букви изобщо не се търсят, а по-дългите — само на граница на дума.
    """
    n = (name or "").strip().lower()
    t = (text or "").lower()
    if len(n) < 3 or not t:
        return False
    start = 0
    while True:
        i = t.find(n, start)
        if i < 0:
            return False
        before_ok = (i == 0) or (not t[i - 1].isalnum())
        end = i + len(n)
        after_ok = (end >= len(t)) or (not t[end].isalnum())
        if before_ok and after_ok:
            return True
        start = i + 1


# ═══════════════════════════ 🏐 ВОЛЕЙБОЛ: РЕЗУЛТАТИ ОТ FIVB
# ЗАЩО СЪЩЕСТВУВА (измерено на 04.08.2026)
# От 61 прогнози в дневника, 18 бяха волейболни и НИТО ЕДНА не беше отсъдена.
# Причината: волейболът не е в ESPN, а SPORT_PATH го водеше None — тоест
# espn_result() връщаше None винаги и мачът висеше неоценен, докато не остарее.
# Резултатът: най-предсказваният спорт беше напълно невидим в отчета.
#
# FIVB VIS дава завършените мачове със Status="25" (официален резултат) и
# MatchPointsA/B = спечелени сетове. Съпоставяме по ИМЕ на отбора, защото
# дневникът и FIVB идват от един и същ източник — имената съвпадат буквално.
_vol_days = {}


def _norm(s):
    return "".join(c for c in str(s or "").lower() if c.isalnum())


# ═══════════ ИМЕНАТА: БЪЛГАРСКО СРЕЩУ АНГЛИЙСКО (намерено на 04.08.2026)
# Предсказателят ПРЕВЕЖДА имената, преди да ги запише в дневника: „Poland"
# става „Полша", „Puerto Rico" става „Пуерто Рико". Източниците обаче връщат
# английските. Затова сравнението по име се проваляше и осемнадесет волейболни
# прогнози висяха неотсъдени — мина единствено „Guatemala", защото не се
# превежда.
# Тук зареждаме СЪЩАТА таблица от predictor.py и сравняваме и в двете посоки.
_bg2en = {}
_bg_loaded = [False]


def bg_map():
    """Обратната карта българско -> английско. Зарежда се веднъж."""
    if _bg_loaded[0]:
        return _bg2en
    _bg_loaded[0] = True
    try:
        import predictor as P
        for en, bg in (getattr(P, "BG_NAME", {}) or {}).items():
            _bg2en[_norm(bg)] = _norm(en)
    except Exception as e:                             # noqa: BLE001
        print("    таблицата с имена не се зареди (" + str(e)[:50] + ")")
    return _bg2en


def same_team(a, b):
    """Едно и също ли са двете имена — на български или на английски."""
    ka, kb = _norm(a), _norm(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    m = bg_map()
    return m.get(ka, ka) == kb or ka == m.get(kb, kb) or m.get(ka) == m.get(kb) is not None


def volley_day(day):
    """Завършените волейболни мачове за един ден. Кешира се по ден."""
    if day in _vol_days:
        return _vol_days[day]
    rows = []
    try:
        import predictor as P
        fields = ("No TeamAName TeamBName MatchPointsA MatchPointsB "
                  "Status DateTimeLocal")
        req = ('<Request Type="GetVolleyMatchList" Fields="' + fields
               + '"><Filter FirstDate="' + day + '" LastDate="' + day + '"/></Request>')
        root = P.vis_xml(req)
        for m in root:
            if str(m.get("Status") or "") != "25":     # 25 = официален резултат
                continue
            try:
                pa = int(str(m.get("MatchPointsA")))
                pb = int(str(m.get("MatchPointsB")))
            except Exception:                          # noqa: BLE001
                continue
            rows.append(((m.get("TeamAName") or "").strip(),
                         (m.get("TeamBName") or "").strip(), pa, pb))
    except Exception as e:                             # noqa: BLE001
        print("    FIVB мълчи за " + str(day) + " (" + str(e)[:50] + ")")
    _vol_days[day] = rows
    return rows


def okolni_dni(den):
    """Денят, предишният и следващият. Заради часовите зони (виж espn_result)."""
    try:
        d0 = datetime.strptime(str(den or ""), "%Y-%m-%d")
    except Exception:                                  # noqa: BLE001
        return []
    return [(d0 + timedelta(days=k)).strftime("%Y-%m-%d") for k in (0, -1, 1)]


def volley_result(rec):
    """(сетове домакин, сетове гост) или None, ако мачът още не е официален."""
    ha, hb = rec.get("home"), rec.get("away")
    if not ha or not hb:
        return None
    for day in okolni_dni(rec.get("day")):
        for na, nb, pa, pb in volley_day(day):
            if same_team(na, ha) and same_team(nb, hb):
                return pa, pb
            if same_team(na, hb) and same_team(nb, ha):   # обърнат ред
                return pb, pa
    return None


# ═══════════════════════════ 🎾 ТЕНИС: РЕЗУЛТАТИ ОТ ESPN (по турнир)
# ЗАЩО НЕ РАБОТЕШЕ ДОСЕГА (проверено на живо на 04.08.2026)
# За отборните спортове ESPN дава мачовете направо в scoreboard. За тениса
# scoreboard връща ТУРНИРИ — вътре „competitions" е ПРАЗЕН списък. Затова
# espn_result() не намираше нищо и 12 тенис прогнози висяха неотсъдени.
# Мачовете живеят в summary на турнира.
_ten_days = {}


def tennis_day(day):
    """Завършените тенис мачове за деня: [(имеA, имеB, сетовеA, сетовеB)]."""
    if day in _ten_days:
        return _ten_days[day]
    ymd = day.replace("-", "")
    out = []
    for tour in ("atp", "wta"):
        try:
            board = http_json(ESPN + "/tennis/" + tour + "/scoreboard?dates=" + ymd)
        except Exception:                              # noqa: BLE001
            continue
        for ev in ((board or {}).get("events") or []):
            # ⚠️ ТУК Е КЛЮЧЪТ. Мачовете НЕ са в ev["competitions"] — той е
            # празен. Живеят в ev["groupings"][i]["competitions"], защото ESPN
            # групира по схема (основна, квалификации, двойки). Заради това
            # дванадесет тенис прогнози висяха неотсъдени.
            for g in (ev.get("groupings") or []):
                for c in (g.get("competitions") or []):
                    st = ((c.get("status") or {}).get("type") or {})
                    if not st.get("completed"):
                        continue
                    sides = []
                    for k in (c.get("competitors") or []):
                        ath = (k.get("athlete") or {})
                        nm = (ath.get("displayName") or ath.get("fullName")
                              or (k.get("team") or {}).get("displayName") or "")
                        gems = []
                        for x in (k.get("linescores") or []):
                            try:
                                gems.append(float(x.get("value")))
                            except Exception:          # noqa: BLE001
                                gems.append(-1.0)
                        sides.append((nm, gems, bool(k.get("winner"))))
                    if len(sides) != 2:
                        continue
                    a, b = sides
                    # Сетове = колко пъти всеки е взел повече геймове.
                    sa = sb = 0
                    for i in range(min(len(a[1]), len(b[1]))):
                        if a[1][i] > b[1][i]:
                            sa += 1
                        elif b[1][i] > a[1][i]:
                            sb += 1
                    if sa == sb:            # редовете не свършиха работа
                        sa, sb = (1, 0) if a[2] else (0, 1)
                    out.append((a[0], b[0], sa, sb))
    _ten_days[day] = out
    return out


def tennis_result(rec):
    ha, hb = rec.get("home"), rec.get("away")
    if not ha or not hb:
        return None
    for day in okolni_dni(rec.get("day")):
        for na, nb, pa, pb in tennis_day(day):
            if same_team(na, ha) and same_team(nb, hb):
                return pa, pb
            if same_team(na, hb) and same_team(nb, ha):
                return pb, pa
    return None


# ═══════════════════════════ ⚾ БЕЙЗБОЛ: РЕЗУЛТАТИ ОТ MLB
# ЗАЩО ОТДЕЛНО: предсказателят взима бейзболните срещи от statsapi.mlb, значи
# id-тата в дневника са НА MLB, не на ESPN. Търсенето в ESPN по тези id-та
# никога не съвпадаше и трите бейзболни прогнози висяха неотсъдени.
MLB_API = "https://statsapi.mlb.com/api/v1"
_mlb_days = {}


def mlb_day(day):
    if day in _mlb_days:
        return _mlb_days[day]
    rows = []
    try:
        j = http_json(MLB_API + "/schedule?sportId=1&date=" + day)
        for d in ((j or {}).get("dates") or []):
            for g in (d.get("games") or []):
                st = str((g.get("status") or {}).get("detailedState") or "")
                if st not in ("Final", "Game Over", "Completed Early"):
                    continue
                t = g.get("teams") or {}
                h, a = (t.get("home") or {}), (t.get("away") or {})
                ht, at = (h.get("team") or {}), (a.get("team") or {})
                try:
                    rows.append((str(ht.get("id")), str(at.get("id")),
                                 int(h.get("score")), int(a.get("score")),
                                 ht.get("name") or "", at.get("name") or ""))
                except Exception:                      # noqa: BLE001
                    continue
    except Exception as e:                             # noqa: BLE001
        print("    MLB мълчи за " + str(day) + " (" + str(e)[:50] + ")")
    _mlb_days[day] = rows
    return rows


def baseball_result(rec):
    hid, aid = str(rec.get("home_id") or ""), str(rec.get("away_id") or "")
    ha, hb = rec.get("home"), rec.get("away")
    for day in okolni_dni(rec.get("day")):
        for h, a, hs, as_, hn, an in mlb_day(day):
            if hid and aid and h == hid and a == aid:
                return hs, as_
            if same_team(hn, ha) and same_team(an, hb):
                return hs, as_
    return None


def sport_result(rec):
    """ЕДИНСТВЕНАТА врата към резултат. Всеки спорт минава оттук.

    Дотук се викаше espn_result() направо и това мълчаливо изключваше три
    спорта: волейбол и тенис на маса (нямат ESPN), и тенис (ESPN дава турнири,
    не мачове). Осемнадесет волейболни и дванадесет тенис прогнози висяха
    неотсъдени — тоест почти половината дневник беше невидим за отчета.
    """
    b = rec.get("bucket")
    if b == "volleyball":
        return volley_result(rec)
    if b == "tennis":
        return tennis_result(rec)
    if b == "baseball":
        return baseball_result(rec)
    return espn_result(rec)


def market_code(pick):
    """Кодът на пазара от началото на избора: 1, 2, Х, 1Х, Х2. Празно = няма.

    Чете се ПРЕДИ имената, защото е еднозначен, докато имената не са: избор
    „1Х · Милан или равен" съдържа името на домакина и по имена би минал за
    чиста победа — тоест равенството щеше да се брои за грешка, а точно
    заради равенствата съществува двойният шанс.

    Кирилското Х и латинското X изглеждат еднакво на екрана и различно в
    паметта. Приемат се и двете, за да не зависи присъдата от клавиатурата.
    """
    s = str(pick or "").strip()
    glava = (s.split("·")[0] if "·" in s else s[:2]).strip()
    glava = glava.replace("X", "Х").replace("x", "Х").upper()
    return {"1Х": "1X", "Х1": "1X", "Х2": "X2", "2Х": "X2",
            "Х": "X", "1": "1", "2": "2"}.get(glava, "")


def verdict(rec, hs, as_):
    """Позна ли прогнозата. Връща True / False / None (не можем да отсъдим).

    None НЕ е провал — то значи „не разбирам собственото си твърдение" и
    такъв ред просто не влиза в статистиката. По-добре празно, отколкото
    измислен резултат.

    Редът е: първо кодът на пазара, чак после имената. Обратното вече ни
    подведе веднъж — при двоен шанс имената сочат победител, какъвто не сме
    твърдели.
    """
    pick = (rec.get("pick") or "")
    home = (rec.get("home") or "")
    away = (rec.get("away") or "")
    low = pick.lower().strip()

    kod = market_code(pick)
    if kod == "1":
        return hs > as_
    if kod == "2":
        return as_ > hs
    if kod == "X":
        return hs == as_
    if kod == "1X":
        return hs >= as_            # домакинът или равен
    if kod == "X2":
        return as_ >= hs            # гостът или равен

    # Без код отпред остават имената — старият път, за по-стари записи.
    said_home = name_in(home, pick) or low[:2] in ("1 ", "1·", "1.")
    said_away = name_in(away, pick) or low[:2] in ("2 ", "2·", "2.")
    if said_home == said_away:
        return None                 # или и двете, или нито едно — не съдим

    if hs == as_:
        return False                # посочили сме победител, а е равен
    home_won = hs > as_
    return home_won if said_home else (not home_won)


# --------------------------------------------------------------------- ТЕКСТ
def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def date_bg(d):
    dni = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]
    return dni[d.weekday()] + ", " + d.strftime("%d.%m")


def line(rec, hs, as_, ok):
    emo = (SPORT_PATH.get(rec.get("bucket")) or (None, "\U0001f4cc"))[1]
    mark = "✅" if ok else "❌"
    return (mark + " " + emo + " <b>" + esc(rec.get("home")) + "</b> " + str(hs)
            + ":" + str(as_) + " <b>" + esc(rec.get("away")) + "</b>" + NL
            + "    посочихме: " + esc(rec.get("pick")))


def bez_text(bez):
    """Един ред за прогнозите, които никой източник не може да отсъди.

    Мълчанието тук би било по-удобно, но собственикът щеше да брои картите в
    стая 7 и да не ги намира в обзора. По-добре да пише защо.
    """
    if not bez:
        return []
    out = []
    for b, n in sorted(bez.items()):
        emo = (SPORT_PATH.get(b) or (None, "\U0001f4cc"))[1]
        ime = {"tabletennis": "тенис на маса"}.get(b, b)
        out.append(emo + " " + ime + ": <b>" + str(n) + "</b> без официален "
                   + ("резултат" if n == 1 else "резултат"))
    return out + [""]


# Име на спорта на български + реда, в който се показва. Редът е по значение
# за канала, не по азбука — футболът и баскетболът водят.
SPORT_BG = {
    "football": "ФУТБОЛ", "basketball": "БАСКЕТБОЛ", "volleyball": "ВОЛЕЙБОЛ",
    "tennis": "ТЕНИС", "tabletennis": "ТЕНИС НА МАСА", "hockey": "ХОКЕЙ",
    "baseball": "БЕЙЗБОЛ", "amfootball": "АМЕРИКАНСКИ ФУТБОЛ", "mma": "БОЙНИ",
}
SPORT_RED = ["football", "basketball", "volleyball", "tennis", "hockey",
             "baseball", "amfootball", "tabletennis", "mma"]


def sport_ime(b):
    return SPORT_BG.get(b) or str(b or "друго").upper()


def sport_emo(b):
    return (SPORT_PATH.get(b) or (None, "\U0001f4cc"))[1]


def po_red(kluchove):
    """Спортовете в постоянен ред. Непознат спорт отива накрая, по азбука."""
    znam = [b for b in SPORT_RED if b in kluchove]
    drugi = sorted(b for b in kluchove if b not in SPORT_RED)
    return znam + drugi


def kratak_red(rec, hs, as_, ok):
    """Един мач в един ред. Без емоджи на спорта — то е в заглавието на групата."""
    return ("  " + ("✅" if ok else "❌") + " <b>" + esc(rec.get("home")) + "</b> "
            + str(hs) + ":" + str(as_) + " <b>" + esc(rec.get("away")) + "</b>" + NL
            + "      " + esc(rec.get("pick")))


def obshto_po_sport(vsichki):
    """Успеваемостта ДОСЕГА, по спорт. Само отсъдените, с изписан знаменател.

    Взима се от ЦЕЛИЯ дневник, не от днешното — иначе числото скача всеки ден
    и не значи нищо. Спорт под 5 отсъдени НЕ получава процент: „1 от 1 = 100%"
    е число, което заблуждава повече, отколкото информира.
    """
    broy = {}
    for r in (vsichki or []):
        if not r.get("scored") or r.get("hit") is None:
            continue
        b = r.get("bucket") or "друго"
        d = broy.setdefault(b, [0, 0])
        d[1] += 1
        if r.get("hit"):
            d[0] += 1
    return broy


def results_text(now, rows, total_all, hit_all, bez=None, vsichki=None):
    """Обзорът на деня — ПОДРЕДЕН ПО СПОРТ.

    ПРЕНАПИСАН 05.08.2026 ПО ИЗРИЧНА ПОРЪЧКА НА СОБСТВЕНИКА:
      „Искам всичко да е доста по-ясно. Най-добре е да ги разделиш на спортове,
       като са по единични. За всеки спорт какво е излязло."

    Дотук обзорът беше две купчини — всички познати заедно, всички сгрешени
    заедно. При петнайсет мача от шест спорта това е списък, не обзор: човек
    не може да види кой спорт го носи и кой го тегли надолу. А точно това е
    единственото, което има значение.

    Сега всеки спорт е свой блок със свое число, а най-отдолу стои
    успеваемостта ДОСЕГА по спортове — от целия дневник, не от днешния ден.

    Правилото за знаменателя остава: винаги се изписва „N от M". Процент без
    знаменател е реклама.
    """
    hits = [r for r in rows if r[3]]
    miss = len(rows) - len(hits)
    pct_day = (100.0 * len(hits) / len(rows)) if rows else 0.0
    pct_all = (100.0 * hit_all / total_all) if total_all else 0.0

    # Днешното, групирано по спорт. ЕДИН МАЧ СЕ ПОКАЗВА ВЕДНЪЖ.
    #
    # Дневникът съдържа дубликати: същата среща, вписана в два поредни дни
    # (мачът е бил пренасрочен, а ключът за „вече публикувано" носи деня).
    # Досега не си личеше, защото обзорът беше една дълга купчина. Щом го
    # подредих по спорт, „Rafael Jodar 0:2 Taylor Fritz" излезе два пъти един
    # под друг — пред очите на хората. Пазачът е тук, а не в дневника, защото
    # обзорът е мястото, което се чете; истинската поправка е в предсказателя.
    grupi = {}
    vidyani = set()
    for rec, hs, as_, ok in rows:
        kl = (str(rec.get("home") or "").strip().lower(),
              str(rec.get("away") or "").strip().lower(),
              str(hs), str(as_))
        if kl in vidyani:
            continue
        vidyani.add(kl)
        grupi.setdefault(rec.get("bucket") or "друго", []).append((rec, hs, as_, ok))

    out = ["\U0001f4ca <b>ОБЗОР НА ДЕНЯ</b> · " + date_bg(now),
           "",
           ("<b>" + str(len(hits)) + " познати · " + str(miss) + " сгрешени · "
            + ("%.0f" % pct_day) + "%</b>"),
           ""]

    for b in po_red(list(grupi)):
        redove = grupi[b]
        p = sum(1 for x in redove if x[3])
        out.append(sport_emo(b) + " <b>" + sport_ime(b) + "</b> · "
                   + str(p) + " от " + str(len(redove)))
        # Познатите първи — човек чете отгоре надолу и първо иска доброто.
        for x in sorted(redove, key=lambda y: not y[3]):
            out.append(kratak_red(x[0], x[1], x[2], x[3]))
        out.append("")

    out += bez_text(bez or {})

    # Успеваемостта ДОСЕГА, по спорт. Това е числото, което казва нещо.
    tabl = obshto_po_sport(vsichki)
    if tabl:
        out.append("\U0001f4c8 <b>ДОСЕГА ПО СПОРТОВЕ</b>")
        for b in po_red(list(tabl)):
            p, n = tabl[b]
            red = ("  " + sport_emo(b) + " " + sport_ime(b).capitalize()
                   + ": <b>" + str(p) + " от " + str(n) + "</b>")
            if n >= 5:
                red += " · " + ("%.0f" % (100.0 * p / n)) + "%"
            else:
                red += " · рано за процент"
            out.append(red)
        out.append("")

    # ДОЛНАТА ЧЕРТА. Собственикът поиска изрично общия брой И ЗАГУБЕНИТЕ —
    # дотук отдолу стоеше само „N от M · X%" и загубите трябваше да се смятат
    # наум. Продуктът е прозрачност: числото, което боли, се изписва.
    zagubeni_all = max(0, total_all - hit_all)
    out += ["\U0001f4ca <b>ОБЩО ДОСЕГА</b>",
            ("  ✅ познати: <b>" + str(hit_all) + "</b>"),
            ("  ❌ загубени: <b>" + str(zagubeni_all) + "</b>"),
            ("  📋 отсъдени общо: <b>" + str(total_all) + "</b> · "
             + ("%.0f" % pct_all) + "%"),
            "",
            "\U0001f7e2 THE GREEN ROOM"]
    return NL.join(out)


def wins_text(now, rows):
    """Витрината. Само познатите — също подредени по спорт."""
    grupi = {}
    for rec, hs, as_, ok in rows:
        grupi.setdefault(rec.get("bucket") or "друго", []).append((rec, hs, as_, ok))
    parts = []
    for b in po_red(list(grupi)):
        parts.append(sport_emo(b) + " <b>" + sport_ime(b) + "</b> · "
                     + str(len(grupi[b])))
        for x in grupi[b]:
            parts.append(kratak_red(x[0], x[1], x[2], True))
        parts.append("")
    body = NL.join(parts).rstrip()
    if not body:
        body = NL.join(line(r[0], r[1], r[2], True) for r in rows)
    return NL.join([
        "\U0001f3c6 <b>ПОЗНАТИТЕ ДНЕС</b> · " + date_bg(now),
        "",
        body,
        "",
        "\U0001f7e2 THE GREEN ROOM",
    ])


def leg_score(rec):
    """Резултатът на вече отсъден крак — от записаното в дневника.

    Краката на един фиш свършват в различни дни и се отсъждат в различни
    пускания. Затова резултатът не се държи в паметта на текущия рън, а се
    чете от полето „score", което scorer-ът е записал, когато го е отсъдил.
    Липсва ли — пише се въпросителна, не измислено число.
    """
    s = str(rec.get("score") or "")
    if ":" in s:
        a, b = s.split(":")[:2]
        try:
            return int(a.strip()), int(b.strip())
        except ValueError:
            pass
    return "?", "?"


def combo_text(now, slips):
    """Обзор на трите фиша: кой е минал изцяло и кой къде се е скъсал.

    Поръчка на собственика: „Фишовете на деня трябва и там обзор."
    Един фиш е верен само ако ВСИЧКИТЕ пет избора са познали — затова тук
    се брои така, а не по проценти.
    """
    out = ["\U0001f3ab <b>ФИШОВЕТЕ ОТ ВЧЕРА</b> · " + date_bg(now), ""]
    minali = 0
    for n, legs in slips:
        ok = sum(1 for x in legs if x[3])
        vsi = len(legs)
        cял = (ok == vsi)
        if cял:
            minali += 1
        out.append(("✅" if cял else "❌") + " <b>ФИШ " + str(n) + "</b> · "
                   + str(ok) + " от " + str(vsi))
        for rec, hs, as_, hit in legs:
            emo = (SPORT_PATH.get(rec.get("bucket")) or (None, "\U0001f4cc"))[1]
            out.append(("   ✅ " if hit else "   ❌ ") + emo + " "
                       + esc(rec.get("home")) + " " + str(hs) + ":" + str(as_)
                       + " " + esc(rec.get("away")))
        out.append("")
    out.append("<b>" + str(minali) + " от " + str(len(slips)) + " фиша минаха.</b>")
    out.append("\U0001f7e2 THE GREEN ROOM")
    return NL.join(out)


# --------------------------------------------------------------------- ГЛАВНО
def load_log():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, encoding="utf-8-sig") as f:
            rows = json.load(f)
        return rows if isinstance(rows, list) else []
    except Exception as e:                    # noqa: BLE001
        print("дневникът не се чете (" + str(e)[:70] + ") — няма какво да оценя.")
        return []


def save_log(rows):
    if DRY_RUN:
        return False
    try:
        tmp = LOG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        os.replace(tmp, LOG_FILE)
        return True
    except Exception as e:                    # noqa: BLE001
        print("дневникът не се записа (" + str(e)[:70] + ").")
        return False


def selftest():
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    # пазачът на стаите. Стая 4 вече Е разрешена — там отива обзорът на
    # фишовете (поръчка на собственика). Всичко останало си остава чуждо.
    for room in ("5", "6", "7", "8", "11", "26", "27", "328", "1", "3"):
        check("стая " + room + " е забранена", room not in ALLOWED_THREADS)
    check("стая 9 е разрешена", RESULTS_THREAD in ALLOWED_THREADS)
    check("стая 10 е разрешена", WINS_THREAD in ALLOWED_THREADS)
    check("стая 4 е разрешена (обзор на фишовете)", PICKS_THREAD in ALLOWED_THREADS)
    check("разрешените са точно три",
          ALLOWED_THREADS == {RESULTS_THREAD, WINS_THREAD, PICKS_THREAD})

    # отсъждането
    r = {"home": "Куба", "away": "Египет", "pick": "1 · победа Куба"}
    check("познат домакин", verdict(r, 3, 1) is True)
    check("сгрешен домакин", verdict(r, 1, 3) is False)
    r2 = {"home": "Левски", "away": "Лудогорец", "pick": "2 · победа Лудогорец"}
    check("познат гост", verdict(r2, 0, 2) is True)
    check("равенството е грешка", verdict(r2, 1, 1) is False)
    r3 = {"home": "Левски", "away": "Лудогорец", "pick": "нещо неразпознаваемо"}
    check("неясното твърдение не се съди", verdict(r3, 2, 1) is None)
    r4 = {"home": "Милан", "away": "Интер", "pick": "1 · победа Милан"}
    check("късото име не се лови вътре в дума", name_in("Ин", "Милан") is False)
    check("цялото име се лови като дума", name_in("Милан", "победа Милан") is True)
    check("името вътре в друга дума не се брои",
          name_in("Интер", "Интернационале") is False)
    check("познат след затягането", verdict(r4, 2, 0) is True)
    r5 = {"home": "Милан", "away": "Интер", "pick": "победа Милан и Интер"}
    check("двусмислено твърдение без код не се съди", verdict(r5, 2, 0) is None)

    # --- ДВОЙНИЯТ ШАНС. Кодът отпред е присъдата, не имената.
    check("кодът чете 1", market_code("1 · победа Милан") == "1")
    check("кодът чете 2", market_code("2 · победа Интер") == "2")
    check("кодът чете Х", market_code("Х · равен") == "X")
    check("кодът чете 1Х", market_code("1Х · Милан или равен") == "1X")
    check("кодът чете Х2", market_code("Х2 · Интер или равен") == "X2")
    check("латинското X се приема като кирилско",
          market_code("1X · Милан или равен") == "1X")
    check("текст без код дава празно", market_code("победа Милан") == "")
    check("празният избор дава празно", market_code("") == "")
    dc1 = {"home": "Милан", "away": "Интер", "pick": "1Х · Милан или равен"}
    check("1Х печели при победа на домакина", verdict(dc1, 2, 0) is True)
    check("1Х ПЕЧЕЛИ ПРИ РАВЕН", verdict(dc1, 1, 1) is True)
    check("1Х губи при победа на госта", verdict(dc1, 0, 2) is False)
    dc2 = {"home": "Милан", "away": "Интер", "pick": "Х2 · Интер или равен"}
    check("Х2 печели при победа на госта", verdict(dc2, 0, 2) is True)
    check("Х2 печели при равен", verdict(dc2, 1, 1) is True)
    check("Х2 губи при победа на домакина", verdict(dc2, 2, 0) is False)
    x0 = {"home": "Милан", "away": "Интер", "pick": "Х · равен"}
    check("чистото Х печели само при равен", verdict(x0, 1, 1) is True)
    check("чистото Х губи при победа", verdict(x0, 2, 1) is False)
    # Тук беше дупката: по имена „1Х · Милан или равен" съдържа „Милан" и
    # равенството 1:1 щеше да мине за ГРЕШКА.
    check("равенството при 1Х НЕ е грешка", verdict(dc1, 1, 1) is not False)

    # --- ТЕКСТЪТ. Пренаписан 29.07.2026: собственикът поиска ЯСЕН ОБЗОР,
    # без „какво следихме", без „нищо не се трие", без обяснения.
    _now = datetime.now(SOFIA)
    _rows = [({"home": "Левски", "away": "ЦСКА", "pick": "1", "bucket": "football"}, 2, 1, True),
             ({"home": "Милан", "away": "Интер", "pick": "1", "bucket": "football"}, 0, 3, False)]
    t = results_text(_now, _rows, 10, 6)
    check("отчетът е чист", banned_word(t) is None)
    check("отчетът е озаглавен ОБЗОР НА ДЕНЯ", "ОБЗОР НА ДЕНЯ" in t)
    check("отчетът дава числото веднага", "1 познати · 1 сгрешени" in t)

    # --- ДОЛНАТА ЧЕРТА. Собственикът: „в канала резултатите не дават общия
    # брой и загубените". Дотук отдолу стоеше само „N от M · X%" и загубите
    # трябваше да се смятат наум.
    check("обзорът има раздел ОБЩО ДОСЕГА", "ОБЩО ДОСЕГА" in t)
    check("обзорът изписва познатите", "познати: <b>6</b>" in t)
    check("обзорът изписва ЗАГУБЕНИТЕ", "загубени: <b>4</b>" in t)
    check("обзорът изписва отсъдените общо", "отсъдени общо: <b>10</b>" in t)
    check("загубените са разликата", (10 - 6) == 4)
    _t0 = results_text(_now, _rows, 0, 0)
    check("нула отсъдени не чупи", "загубени: <b>0</b>" in _t0)
    _tvs = results_text(_now, _rows, 7, 7)
    check("без загуби пише нула, не мълчи", "загубени: <b>0</b>" in _tvs)

    # --- КАНАЛЪТ. Обзорът отива и там, но по свой път и със свой пазач.
    check("каналът е зададен", bool(str(CHANNEL_ID).strip()))
    check("каналът НЕ е стая от групата", str(CHANNEL_ID) not in ALLOWED_THREADS)
    check("каналът приема чист обзор", post_channel(t) is True)
    check("каналът ОТКАЗВА хазартна дума",
          post_channel("залагай отговорно") is False)
    check("каналът отказва и коефициент", post_channel("коеф 1.85") is False)

    # --- ОБЗОРЪТ Е ПОДРЕДЕН ПО СПОРТ (поръчка на собственика, 05.08.2026).
    # Дотук беше две купчини — всички познати заедно, всички сгрешени заедно.
    # При петнайсет мача от шест спорта това е списък, не обзор.
    _mix = [({"home": "Левски", "away": "ЦСКА", "pick": "1", "bucket": "football"}, 2, 1, True),
            ({"home": "Милан", "away": "Интер", "pick": "1", "bucket": "football"}, 0, 3, False),
            ({"home": "Куба", "away": "Перу", "pick": "1", "bucket": "volleyball"}, 3, 0, True),
            ({"home": "Никс", "away": "Хийт", "pick": "1", "bucket": "basketball"}, 99, 90, True)]
    _dnevnik = [{"bucket": "volleyball", "scored": True, "hit": True} for _ in range(12)]
    _dnevnik += [{"bucket": "volleyball", "scored": True, "hit": False}]
    _dnevnik += [{"bucket": "football", "scored": True, "hit": True} for _ in range(2)]
    _dnevnik += [{"bucket": "football", "scored": True, "hit": False} for _ in range(9)]
    _dnevnik += [{"bucket": "hockey", "scored": True, "hit": True}]
    _dnevnik += [{"bucket": "tabletennis", "scored": True, "hit": None}]
    _t3 = results_text(_now, _mix, 44, 29, {}, _dnevnik)
    check("обзорът има блок за футбола", "ФУТБОЛ" in _t3)
    check("обзорът има блок за волейбола", "ВОЛЕЙБОЛ" in _t3)
    check("обзорът има блок за баскетбола", "БАСКЕТБОЛ" in _t3)
    check("всеки блок носи своето число", "ФУТБОЛ</b> · 1 от 2" in _t3)
    check("волейболният блок е 1 от 1", "ВОЛЕЙБОЛ</b> · 1 от 1" in _t3)
    check("футболът е преди волейбола (постоянен ред)",
          _t3.index("ФУТБОЛ") < _t3.index("ВОЛЕЙБОЛ"))
    check("има таблица ДОСЕГА ПО СПОРТОВЕ", "ДОСЕГА ПО СПОРТОВЕ" in _t3)
    check("волейболът досега е 12 от 13", "12 от 13" in _t3)
    check("волейболът досега е 92%", "92%" in _t3)
    check("футболът досега е 2 от 11", "2 от 11" in _t3)
    check("футболът досега е 18%", "18%" in _t3)
    check("малката извадка НЕ получава процент",
          "1 от 1</b> · рано за процент" in _t3)
    check("неотсъденото НЕ влиза в таблицата", "ТЕНИС НА МАСА</b>: " not in _t3)
    check("обзорът по спортове е чист", banned_word(_t3) is None)
    check("познатите са преди сгрешените в блока",
          _t3.index("Левски") < _t3.index("Милан"))
    check("знаменателят винаги е изписан", " от " in _t3)
    check("празен дневник не чупи таблицата",
          isinstance(results_text(_now, _mix, 4, 3, {}, []), str))
    check("липсващ дневник не чупи",
          isinstance(results_text(_now, _mix, 4, 3), str))
    check("подредбата на спортовете е постоянна",
          po_red(["tennis", "football", "volleyball"]) == ["football", "volleyball", "tennis"])
    check("непознат спорт отива накрая",
          po_red(["зззз", "football"]) == ["football", "зззз"])
    check("името на спорта е на български", sport_ime("hockey") == "ХОКЕЙ")
    check("непознат спорт пак получава име", sport_ime("нещо") == "НЕЩО")
    # Дубликат: същият мач, същият резултат, вписан два пъти в дневника.
    _dubl = _mix + [({"home": "Левски", "away": "ЦСКА", "pick": "1",
                      "bucket": "football"}, 2, 1, True)]
    _td = results_text(_now, _dubl, 44, 29, {}, _dnevnik)
    check("дублираният мач се показва ВЕДНЪЖ", _td.count("Левски") == 1)
    check("дублирането не мени числото на блока", "ФУТБОЛ</b> · 1 от 2" in _td)
    check("различен резултат за същия мач НЕ е дубликат",
          results_text(_now, _mix + [({"home": "Левски", "away": "ЦСКА",
                                       "pick": "1", "bucket": "football"},
                                      3, 0, True)], 44, 29, {}, _dnevnik)
          .count("Левски") == 2)

    _w3 = wins_text(_now, [x for x in _mix if x[3]])
    check("витрината също е по спорт", "ФУТБОЛ" in _w3 and "ВОЛЕЙБОЛ" in _w3)
    check("витрината е чиста", banned_word(_w3) is None)
    check("отчетът НЕ поучава",
          "не се трие" not in t and "Гледахме" not in t and "завинаги" not in t)
    w = wins_text(_now, [_rows[0]])
    check("витрината е чиста", banned_word(w) is None)
    check("витрината е само познатите", "ПОЗНАТИТЕ ДНЕС" in w)
    check("витрината не обяснява", "Пълният отчет" not in w)

    # --- обзорът на фишовете
    _legs = [({"home": "А" + str(i), "away": "Б", "pick": "1", "bucket": "football"},
              2, 1, i != 2) for i in range(5)]
    c = combo_text(_now, [(1, _legs)])
    check("фишовете имат обзор", "ФИШОВЕТЕ ОТ ВЧЕРА" in c)
    check("скъсаният фиш е отбелязан", "❌ <b>ФИШ 1</b> · 4 от 5" in c)
    check("обзорът на фишовете е чист", banned_word(c) is None)
    check("обзорът брои минали фишове", "0 от 1 фиша минаха" in c)
    check("стая 4 е разрешена за обзора", PICKS_THREAD in ALLOWED_THREADS)

    # --- ФИШЪТ СЕ СГЛОБЯВА ОТ ЦЕЛИЯ ДНЕВНИК, НЕ ОТ ЕДИН РЪН.
    # Дотук списъкът се строеше само от отсъдените В ТОЗИ рън, а крак от минал
    # рън има scored=True и се прескача — тоест фиш от пет крака се отчиташе
    # само ако и петте мача свършат между две пускания. Никога не се случи.
    check("резултатът на крак се чете от дневника",
          leg_score({"score": "2:1"}) == (2, 1))
    check("липсващият резултат не се измисля",
          leg_score({}) == ("?", "?"))
    check("счупеният резултат не се измисля",
          leg_score({"score": "не знам"}) == ("?", "?"))

    def _sglobi(redove):
        """Същата логика като в main: групиране по (номер, ден)."""
        s = {}
        for r in redove:
            n = int(r.get("combo") or 0)
            if n and not r.get("combo_done"):
                s.setdefault((n, str(r.get("day") or "")), []).append(r)
        return s

    _star = [{"combo": 1, "day": "2026-08-01", "scored": True, "hit": True, "score": "2:0"},
             {"combo": 1, "day": "2026-08-01", "scored": True, "hit": False, "score": "0:1"}]
    _nov = [{"combo": 1, "day": "2026-08-02", "scored": True, "hit": True, "score": "3:1"}]
    _s = _sglobi(_star + _nov)
    check("два дни с фиш №1 НЕ се сливат", len(_s) == 2)
    check("вчерашният фиш пази двата си крака", len(_s[(1, "2026-08-01")]) == 2)
    check("днешният фиш е отделен", len(_s[(1, "2026-08-02")]) == 1)
    _chaka = _sglobi([{"combo": 2, "day": "2026-08-01", "scored": True, "hit": True},
                      {"combo": 2, "day": "2026-08-01", "scored": False}])
    _legs = _chaka[(2, "2026-08-01")]
    check("фиш с незавършил крак се разпознава",
          any(not x.get("scored") for x in _legs))
    check("отчетеният фиш не се брои пак",
          _sglobi([{"combo": 3, "day": "2026-08-01", "scored": True,
                    "hit": True, "combo_done": True}]) == {})
    check("самостоятелната карта не е фиш",
          _sglobi([{"combo": 0, "day": "2026-08-01", "scored": True}]) == {})
    check("липсващото поле combo не чупи (старите 55 записа)",
          _sglobi([{"day": "2026-08-01", "scored": True}]) == {})

    # --- прозорецът на дните: днешното СЕ отчита, утрешното НЕ
    _today = datetime.now(SOFIA).strftime("%Y-%m-%d")
    _utre = (datetime.now(SOFIA) + timedelta(days=1)).strftime("%Y-%m-%d")
    _vchera = (datetime.now(SOFIA) - timedelta(days=1)).strftime("%Y-%m-%d")
    check("утрешният мач се прескача", _utre > _today)
    check("днешният мач НЕ се прескача", not (_today > _today))
    check("вчерашният мач НЕ се прескача", not (_vchera > _today))

    # --- спортът без източник. Измерено 04.08.2026: шест адреса, нула
    # резултата, а статистиката по ден си противоречи в 30% от мачовете.
    check("тенисът на маса е обявен за без източник", "tabletennis" in NO_RESULT)
    check("волейболът НЕ е без източник", "volleyball" not in NO_RESULT)
    check("тенисът НЕ е без източник", "tennis" not in NO_RESULT)
    check("футболът НЕ е без източник", "football" not in NO_RESULT)
    _b = bez_text({"tabletennis": 5})
    check("редът за без-източник казва броя", "<b>5</b>" in NL.join(_b))
    check("редът за без-източник назовава спорта",
          "тенис на маса" in NL.join(_b))
    check("без-източник не се появява, когато няма такива", bez_text({}) == [])
    _t2 = results_text(_now, _rows, 10, 6, {"tabletennis": 3})
    check("обзорът показва без-източник", "без официален" in _t2)
    check("обзорът с без-източник е чист", banned_word(_t2) is None)
    check("без-източник НЕ разваля процента", "1 познати · 1 сгрешени" in _t2)
    check("обзорът без такива не пише за тях", "без официален" not in t)

    print("САМОПРОВЕРКА НА ОЦЕНИТЕЛЯ: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 1 if bad else 0


def main():
    if not BOT_TOKEN and not DRY_RUN:
        print("Липсва BOT_TOKEN.")
        return 1
    rows = load_log()
    if not rows:
        print("Дневникът е празен — няма какво да оценя.")
        return 0

    now = datetime.now(SOFIA)
    limit = (now - timedelta(days=MAX_AGE)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    # Общата статистика се смята от ЦЕЛИЯ дневник, не само от днешното.
    total_all = sum(1 for r in rows if r.get("scored") and r.get("hit") is not None)
    hit_all = sum(1 for r in rows if r.get("scored") and r.get("hit") is True)

    fresh = []
    checked = 0
    bez_izvor = {}
    for r in rows:
        if r.get("scored"):
            continue
        day = r.get("day") or ""
        # ДНЕШНИТЕ МАЧОВЕ СЕ ОТЧИТАТ ОЩЕ ДНЕС.
        # Тук стоеше „ако денят е днес — прескачай". Изглеждаше предпазливо, а
        # всъщност обезсмисляше вечерното пускане в 20:00: то не можеше да
        # отчете НИТО ЕДИН мач от същия ден и резултатите закъсняваха с
        # денонощие. Пазачът е излишен, защото истинската защита е по-надолу:
        # espn_result() връща резултат САМО когато ESPN каже "completed".
        # Незавършил мач си остава неоценен и се пробва пак на следващото
        # пускане. Мачът за УТРЕ обаче наистина се прескача — там няма какво
        # да се пита.
        if day > today:
            continue
        if day < limit:
            r["scored"] = True                # твърде старо, отказваме се
            r["hit"] = None
            continue
        # Спорт без източник: не хабим заявки да питаме нещо, което няма
        # отговор. Затваряме го честно още щом денят му мине.
        if r.get("bucket") in NO_RESULT and day < today:
            r["scored"] = True
            r["hit"] = None
            r["why"] = "няма официален източник за резултата"
            bez_izvor[r.get("bucket")] = bez_izvor.get(r.get("bucket"), 0) + 1
            continue
        checked += 1
        res = sport_result(r)
        time.sleep(0.4)
        if res is None:
            continue                          # пробваме пак утре
        hs, as_ = res
        ok_hit = verdict(r, hs, as_)
        if ok_hit is None:
            r["scored"] = True
            r["hit"] = None
            continue
        r["scored"] = True
        r["hit"] = bool(ok_hit)
        r["score"] = str(hs) + ":" + str(as_)
        fresh.append((r, hs, as_, bool(ok_hit)))

    print("Проверени " + str(checked) + " твърдения, отсъдени " + str(len(fresh)) + ".")
    if not fresh:
        save_log(rows)
        print("Няма завършили мачове за отчет — мълча.")
        return 0

    total_all += len(fresh)
    hit_all += sum(1 for f in fresh if f[3])

    obzor = results_text(now, fresh, total_all, hit_all, bez_izvor, rows)
    post(RESULTS_THREAD, obzor)
    # И В КАНАЛА. Поръчка на собственика: „искаме всичко да си е вътре след
    # края на деня". Провалът тук НЕ отменя поста в стаята — той вече е минал.
    time.sleep(1.5)
    post_channel(obzor)
    wins = [f for f in fresh if f[3]]
    if wins:
        time.sleep(2.0)
        post(WINS_THREAD, wins_text(now, wins))
    else:
        print("Днес няма познати — витрината мълчи, отчетът излезе.")

    # ОБЗОР НА ФИШОВЕТЕ → стая 4.
    #
    # ТУК ФИШЪТ НЕ МОЖЕШЕ ДА БЪДЕ ОТЧЕТЕН ИЗОБЩО (намерено и оправено 04.08.2026).
    #
    # Списъкът се строеше САМО от `fresh` — краката, отсъдени в ТОЗИ рън. Но крак,
    # отсъден в предишен рън, има scored=True и се прескача още в началото на
    # цикъла, тоест никога не влиза във `fresh`. Условието „всичките пет крака
    # наведнъж" значеше на практика „и петте мача да свършат между две пускания
    # на оценителя". При две пускания на ден това не се случва почти никога и
    # стая 4 не е получила НИТО ЕДИН обзор на фиш.
    #
    # Сега фишът се сглобява от ЦЕЛИЯ дневник, по двойката (номер, ден). Денят е
    # задължителен: номерата 1-3 се повтарят всеки ден и без него трите фиша от
    # понеделник биха се слели с трите от вторник.
    # Отчетеният фиш се маркира с combo_done, за да не излиза пак.
    slips = {}
    for r in rows:
        n = int(r.get("combo") or 0)
        if n and not r.get("combo_done"):
            slips.setdefault((n, str(r.get("day") or "")), []).append(r)

    gotovi = []
    for klyuch in sorted(slips, key=lambda k: (k[1], k[0])):
        n, den = klyuch
        legs = slips[klyuch]
        chakat = [r for r in legs if not r.get("scored")]
        if chakat:
            print("Фиш " + str(n) + " (" + den + "): " + str(len(chakat))
                  + " от " + str(len(legs)) + " крака чакат резултат.")
            continue
        sudimi = [r for r in legs if r.get("hit") is not None]
        for r in legs:
            r["combo_done"] = True          # приключен, независимо от изхода
        if not sudimi:
            print("Фиш " + str(n) + " (" + den + "): нито един крак не се отсъжда"
                  " — няма какво да отчета.")
            continue
        gotovi.append((n, [(r, leg_score(r)[0], leg_score(r)[1],
                            bool(r.get("hit"))) for r in sudimi]))
    if gotovi:
        time.sleep(2.0)
        post(PICKS_THREAD, combo_text(now, gotovi))

    save_log(rows)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv or os.environ.get("SCORE_SELFTEST") == "1":
        sys.exit(selftest())
    sys.exit(main())
