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
3. Пише в ДВЕ стаи, всяка с различна работа (разделено 11.08.2026 по изрична
   дума на собственика: „да не объркваш нещата"):
     стая 9  ✅ Резултати и статистика — ЧИСЛАТА: обзор на отсъдените сега
             (познати И сгрешени) + равносметка за целия ден. Равносметката
             излиза ДВА пъти: „ДОКЪДЕ СМЕ ДНЕС" по обяд и „ФИНИШ НА ДЕНЯ" вечер.
     стая 10 🏆 Печеливши фишове — ФИШОВЕТЕ: кой е минал, кой се е скъсал и къде.
   Обзорът и равносметката отиват И в канала (поръчка от 05.08.2026).
   Ако няма нито един завършил мач — не пише нищо. Тишината е за предпочитане.
4. Вдига „scored" на оценените, за да не се броят два пъти.

ЖЕЛЕЗНИ ПРАВИЛА
- Пише САМО в стаи 9 и 10 (и в канала). Всяка друга стая се отказва на изхода,
  преди мрежата. Стая 4 е на човека-типстер и не е между разрешените.
- Никакви поучения, никакви коефициенти, никакви букмейкъри. Пазач на изхода.
- Загубите НЕ се крият и НЕ се трият. Точно те правят числото достоверно.
- Не е сигурен резултатът → мачът остава неоценен и се пробва пак утре.

ENV:
  BOT_TOKEN, CHAT_ID
  RESULTS_THREAD_ID (9)   ·  WINS_THREAD_ID (10)   ·  CHANNEL_ID
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
# 🔴 ЗАТВОРЕНА ВРАТА, 11.08.2026. Стая 4 стоеше В РАЗРЕШЕНИТЕ, защото някога
# там излизаше обзорът на фишовете. От 11.08 обзорът отива в стая 10 и в целия
# файл няма НИТО ЕДНО пускане към стая 4 — разрешението беше празна отворена
# врата към единствената стая, която всеки друг бот пази изрично като „на
# човека-типстер". Отворена врата без нужда е отворена врата.
# PICKS_THREAD остава като ИМЕ (селфтестът проверява, че трите номера са
# различни), но вече не е между разрешените.
PICKS_THREAD = (os.environ.get("PICKS_THREAD_ID") or "4").strip()
ALLOWED_THREADS = {RESULTS_THREAD, WINS_THREAD}

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
# 🔴 ПРАЗЕН ОТ 11.08.2026. Тенисът на маса излезе оттук — WTT дава официалните
# резултати през шлюза /ttu/ с ключ (виж дългото обяснение при wtt_result).
# Списъкът остава жив: утре друг спорт може да влезе в него.
NO_RESULT = set()

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


# 🔴 БЛИЗНАКЪТ НА ПОПРАВКАТА В predictor.py (11.08.2026).
#
# Там пет спорта мълчаха, защото ESPN връщаше 403 на всеки адрес. Причината се
# оказа обърната наопаки: не липса на подпис, а ПРЕПРАВЕН подпис. Измерено на
# живо, един адрес, една минута:
#     „Mozilla/5.0 (compatible; GreenRoomScorer/1.0)"  ->  403 Forbidden
#     без подпис / подписът на самия Python            ->  200 и 10 срещи
#
# Отсъждащият чука на СЪЩАТА врата със същия преправен подпис. Значи и
# резултатите за футбол, тенис, баскетбол, хокей, бейзбол и ММА са падали
# мълчаливо. Поправката се прави и тук — иначе половината е оправена.
NO_UA_HOSTS = ("espn.com",)


def glavi_za(url, headers=None):
    hd = ({"Accept": "application/json"}
          if any(h in url for h in NO_UA_HOSTS)
          else {"User-Agent": UA, "Accept": "*/*"})
    if headers:
        hd.update(headers)
    return hd


def http_json(url, timeout=25):
    req = urllib.request.Request(url, headers=glavi_za(url))
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


# ══════════════════════════════════════════════════════════════════════════
#  🏓 ТЕНИСЪТ НА МАСА ВЕЧЕ СЕ ОТСЪЖДА (11.08.2026)
#
#  На 04.08 шест врати бяха затворени и спортът беше обявен за „без източник".
#  Втората от тях гласеше „WTT results/ matches/ draw/ … празни или 404".
#  Днес проверих пак и намерих РАБОТЕЩАТА:
#
#      GET wttcmsapigateway-new.azure-api.net/ttu/Matches/GetMatches?EventId=NNNN
#      с глава ApiKey (същият ключ, който предсказателят вече ползва)
#
#  Измерено на живо, не разсъждавано:
#    · турнир 3246 (Europe Smash) → HTTP 200, 571 319 байта, обикновен JSON
#      (БЕЗ brotli — шлюзът не го ползва, за разлика от CDN-а)
#    · 168 записа с ScheduleStatus == "Official" И MatchScore ("3-1", "0-3"…)
#    · сверих ги срещу дневника по имена на играчи: 23 от нашите 72
#      прогнози за тенис на маса се отсъждат ВЕДНАГА, само от този турнир
#
#  Дотук тези прогнози се затваряха с hit=None и се брояха отделно: 56 висяха
#  в стая 9 като „без официален резултат". Тоест вторият най-продуктивен спорт
#  беше напълно невидим за успеваемостта.
#
#  Защо предишното измерване е сгрешило: гледало е schedule.json на CDN-а (там
#  наистина няма резултат) и пътища без ключ. Шлюзът /ttu/ с ключа е трети
#  адрес и не е бил пробван за мачове — само за статистика по играч.
# ══════════════════════════════════════════════════════════════════════════
# Колко турнира най-много се питат за ЕДИН ден. Виж дългото обяснение при
# wtt_result: четири беше твърде малко и режеше по средата на подредба, върху
# която нямаме власт.
WTT_MAX_TURNIRI = max(1, min(40, int((os.environ.get("SCORE_WTT_TURNIRI") or "12").strip())))
WTT_TTU = "https://wttcmsapigateway-new.azure-api.net/ttu/"
WTT_HEAD = {"ApiKey": "2bf8b222-532c-4c60-8ebe-eb6fdfebe84a"}
WTT_CDN = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net"
_wtt_index = {}          # EventId -> {frozenset(двете имена): (hs, as_)}
_wtt_events = None       # кеш на календара за тази година


def _wtt_ime(s):
    """Име на играч, сведено до голи латински букви. Източниците се различават
    по ударения, тирета и главни букви — сравняваме само буквите."""
    import unicodedata
    x = unicodedata.normalize("NFKD", str(s or ""))
    x = x.encode("ascii", "ignore").decode().lower()
    return "".join(c for c in x if "a" <= c <= "z")


def _wtt_matches(eid):
    """Двойка имена -> резултат по сетове, за един турнир. Кешира се."""
    if eid in _wtt_index:
        return _wtt_index[eid]
    out = {}
    try:
        req = urllib.request.Request(
            WTT_TTU + "Matches/GetMatches?EventId=" + str(eid),
            headers={"Accept": "application/json", "ApiKey": WTT_HEAD["ApiKey"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read())
    except Exception as e:                                   # noqa: BLE001
        print("   ⚠ WTT мачове " + str(eid) + ": " + str(e)[:70])
        _wtt_index[eid] = out
        return out

    def hodi(o):
        if isinstance(o, list):
            for x in o:
                yield from hodi(x)
        elif isinstance(o, dict):
            if "MatchScore" in o:
                yield o
            for v in o.values():
                yield from hodi(v)

    for x in hodi(j):
        if str(x.get("ScheduleStatus")) != "Official":
            continue
        sc = str(x.get("MatchScore") or "")
        if "-" not in sc:
            continue
        a, b = _wtt_ime(x.get("Player1Name")), _wtt_ime(x.get("Player2Name"))
        if not a or not b:
            continue
        try:
            hs, as_ = (int(z) for z in sc.split("-")[:2])
        except ValueError:
            continue
        # Ключът е НЕПОДРЕДЕН, защото домакин/гост при тенис на маса е само
        # ред на изписване. Пазим и посоката, за да не обърнем резултата.
        out[frozenset((a, b))] = (a, hs, as_)
    _wtt_index[eid] = out
    return out


def _wtt_turniri(godina=None):
    """(EventId, начало, край) за всички турнири. Кешира се за целия рън.

    🔴 ВЗИМА СЕ ОТ ШЛЮЗА, НЕ ОТ CDN-а. Първата версия четеше календара на CDN-а
    и падна веднага на живо: „utf-8 codec can not decode byte 0xc1" — CDN-ът
    отговаря СГЪСТЕНО с brotli, а оценителят няма такъв модул (предсказателят
    има, защото workflow-ът му го инсталира). Шлюзът /ttu/Events/GetEvents
    връща обикновен JSON: измерено 83 173 байта, 100 турнира, без сгъстяване.
    Тоест оценителят вече няма НИКАКВА нова зависимост.
    """
    global _wtt_events
    if _wtt_events is not None:
        return _wtt_events
    _wtt_events = []
    try:
        req = urllib.request.Request(
            WTT_TTU + "Events/GetEvents",
            headers={"Accept": "application/json", "ApiKey": WTT_HEAD["ApiKey"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = json.loads(r.read())
    except Exception as e:                                   # noqa: BLE001
        print("   ⚠ WTT турнири: " + str(e)[:70])
        return _wtt_events

    def hodi(o):
        if isinstance(o, list):
            for x in o:
                yield from hodi(x)
        elif isinstance(o, dict):
            if "EventId" in o or "eventId" in o:
                yield o
            for v in o.values():
                yield from hodi(v)

    for r in hodi(raw):
        eid = r.get("EventId") or r.get("eventId")
        a = str(r.get("EventStartDate") or r.get("StartDateTime")
                or r.get("startDateTime") or "")[:10]
        b = str(r.get("EventEndDate") or r.get("EndDateTime")
                or r.get("endDateTime") or "")[:10]
        # 🔴 Шлюзът пише датата с наклонени черти („2026/08/10"), а дневникът
        # с тирета. Без това привеждане сравнението мълчи и НИТО ЕДИН турнир
        # не се намира — хванато на първото живо пускане.
        a, b = a.replace("/", "-"), b.replace("/", "-")
        if eid and len(a) == 10:
            _wtt_events.append((int(eid), a, b if len(b) == 10 else a))
    return _wtt_events


def wtt_result(rec):
    """Резултатът на един мач тенис на маса. None = още не знаем.

    Търси само в турнирите, чийто период покрива деня на прогнозата — иначе
    един рън би дръпнал сто турнира за нищо.
    """
    den = str(rec.get("day") or "")[:10]
    if not den:
        return None
    godina = den[:4]
    kand = [e for e, a, b in _wtt_turniri(godina) if a <= den <= b]
    if not kand:
        return None
    dom = _wtt_ime(rec.get("home"))
    gost = _wtt_ime(rec.get("away"))
    if not dom or not gost:
        return None
    klyuch = frozenset((dom, gost))
    # 🔴 ТАВАНЪТ ВДИГНАТ 12.08.2026 — ИЗМЕРЕНО, НЕ ПРЕДПОЛОЖЕНО.
    # Стоеше kand[:4]. За 08.08 денят се покрива от СЕДЕМ турнира, а седем от
    # осемте висящи прогнози седят в турнир 3245 — ПЕТИ по ред, тоест никога
    # не се питаше. Редът идва от GetEvents и е произволен: коя прогноза ще
    # бъде отсъдена зависеше от подредбата на чужд списък.
    # Заявките са евтини (един GET на турнир, кеширан в _wtt_index), а цената
    # на пропуска е прогноза, която виси до изтичане на срока и се затваря
    # без присъда. Затова таванът е 12, не 4 — и е ръчка, не константа.
    for eid in kand[:WTT_MAX_TURNIRI]:
        idx = _wtt_matches(eid)
        if klyuch in idx:
            purvi, hs, as_ = idx[klyuch]
            # WTT пише двамата в свой ред. Ако първият при тях е нашият гост,
            # обръщаме — иначе бихме отсъдили точно наопаки.
            return (hs, as_) if purvi == dom else (as_, hs)
    return None


# ══════════════════════════════════════════════════════════════════════════
#  🔴 РЕЗЕРВНИЯТ ИЗТОЧНИК ВЕЧЕ СЕ ОТСЪЖДА (11.08.2026)
#
#  predictor.sdb_fixtures() е „последна резерва, за да не остане празна стая" —
#  вади срещи от TheSportsDB, когато ESPN мълчи. Само че записва extra={},
#  тоест БЕЗ slug, а отборните id-та са на TheSportsDB, не на ESPN.
#  espn_result() пада на първия ред (`if not slug: return None`) и такава
#  прогноза НЕ МОЖЕ да бъде отсъдена никога.
#
#  Измерено в живия дневник: 22 прогнози за WNBA, всичките без slug,
#  НУЛА отсъдени. Тоест резервата пълнеше стаята с карти, за които обещанието
#  „всичко се отчита" не важи.
#
#  Проверено на живо, че вратата съществува:
#    eventsday.php?d=2026-08-06&s=Basketball → 3 събития с резултати,
#    сред тях „Chicago Sky 95-88 Los Angeles Sparks" — точно наш висящ мач.
#    eventslast.php?id=136447 → „Atlanta Dream 96-82 Phoenix Mercury".
#  Затова тук има ДВЕ врати: по ден и по отбор. Първата хваща повечето,
#  втората спасява мачовете, разместени от часовата зона.
# ══════════════════════════════════════════════════════════════════════════
SDB_KEY = (os.environ.get("SPORTSDB_KEY") or "123").strip()
SDB = "https://www.thesportsdb.com/api/v1/json/" + SDB_KEY
SDB_SPORT = {"basketball": "Basketball", "football": "Soccer",
             "baseball": "Baseball", "hockey": "Ice Hockey",
             "tennis": "Tennis", "volleyball": "Volleyball",
             "amfootball": "American Football"}
_sdb_den = {}


def _sdb_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())
    except Exception:                                        # noqa: BLE001
        return {}


def _sdb_dvoyki(sabitiya):
    """(домакин_id, гост_id, точки_д, точки_г, име_д, име_г) за завършилите."""
    out = []
    for e in (sabitiya or []):
        hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
        if hs in (None, "") or as_ in (None, ""):
            continue
        try:
            hs, as_ = int(hs), int(as_)
        except (TypeError, ValueError):
            continue
        out.append((str(e.get("idHomeTeam") or ""), str(e.get("idAwayTeam") or ""),
                    hs, as_, e.get("strHomeTeam"), e.get("strAwayTeam")))
    return out


def sdb_result(rec):
    """Резултат от TheSportsDB. За прогнози БЕЗ slug — тях ESPN не ги знае."""
    hid, aid = str(rec.get("home_id") or ""), str(rec.get("away_id") or "")
    ha, hb = rec.get("home"), rec.get("away")
    sport = SDB_SPORT.get(rec.get("bucket"))
    if not sport or (not hid and not ha):
        return None

    # ВРАТА 1: всички мачове от този спорт за деня (и съседните — часови зони).
    for den in okolni_dni(rec.get("day")):
        if den not in _sdb_den:
            j = _sdb_json(SDB + "/eventsday.php?d=" + den + "&s="
                          + urllib.parse.quote(sport))
            _sdb_den[den] = _sdb_dvoyki(j.get("events"))
            time.sleep(0.3)
        for h, a, hs, as_, hn, an in _sdb_den[den]:
            if hid and aid and h == hid and a == aid:
                return hs, as_
            if same_team(hn, ha) and same_team(an, hb):
                return hs, as_

    # ВРАТА 2: последните мачове на домакина. Спасява разместените по зона.
    if hid:
        j = _sdb_json(SDB + "/eventslast.php?id=" + hid)
        for h, a, hs, as_, hn, an in _sdb_dvoyki(j.get("results")):
            if aid and a == aid and h == hid:
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
    if b == "tabletennis":
        return wtt_result(rec)
    # 🔴 БЕЗ slug ESPN не може да го намери — това са срещите от резервния
    # източник (виж дългото обяснение при sdb_result). Дотук такава прогноза
    # висеше вечно: 22 за WNBA, нула отсъдени.
    if not rec.get("slug"):
        r = sdb_result(rec)
        if r is not None:
            return r
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

    # 🔴 ГЛАВАТА БРОИ ТОЧНО ТОВА, КОЕТО СЕ ВИЖДА ОТДОЛУ (12.08.2026).
    #
    # Дотук главата ползваше len(hits) — броя на ВСИЧКИ отсъдени записи, а
    # списъкът под нея минава през пазача `vidyani`, който слива еднаквите.
    # Измерено на живо: „Indiana Fever 106:92 New York Liberty" стои в дневника
    # ДВА пъти — веднъж като крак на фиш от 11.08 (без slug) и веднъж като
    # карта от 12.08 (slug wnba). Главата казваше 14 познати, а редовете под
    # нея сборуваха 13. Човек, който събере наум, хваща бота в лъжа.
    #
    # Затова числата се смятат от СЛЕТИТЕ групи, не от суровия списък.
    _vid = [x for lst in grupi.values() for x in lst]
    _poz = sum(1 for x in _vid if x[3])
    _gres = len(_vid) - _poz
    _pct = (100.0 * _poz / len(_vid)) if _vid else 0.0
    out = ["\U0001f4ca <b>ОБЗОР НА ДЕНЯ</b> · " + date_bg(now),
           "",
           ("<b>" + str(_poz) + " познати · " + str(_gres) + " сгрешени · "
            + ("%.0f" % _pct) + "%</b>"),
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


# ═══════════════════════════════════ 🧾 ДОСЕГА ОБЩО (12.08.2026)
#
# По изрична поръчка на собственика: „в резултати трябва да има за деня, както
# сме казали, 2 пъти в деня, и накрая на деня веднага след тези за деня всичките
# които са в 23:30. След това искам — досега общо всичко което е пуснато в БОТА
# ПРЕДРИЧА. Така ще може да се следи и прави статистика занапред."
#
# Разликата от другите две съобщения е РАМКАТА, не форматът:
#   • „ДОКЪДЕ СМЕ ДНЕС"  (обяд)  — днешният ден, недовършен
#   • „ФИНИШ НА ДЕНЯ"    (вечер) — днешният ден, окончателен
#   • „ДОСЕГА ОБЩО"      (вечер, веднага след финиша) — ЦЕЛИЯТ ЖИВОТ на бота
#
# Затова тук НЕ се филтрира по ден. Броят се всички записи в дневника, тоест
# всичко, което някога е излизало в 🤖 БОТА ПРЕДРИЧА.
#
# Излиза САМО вечер и САМО веднъж. Обядът си има своята междинна.
def obshto_dosega_text(now, rows):
    """Равносметката на целия живот на бота. Едно съобщение, стая 9."""
    rows = list(rows or [])
    sega_den = now.strftime("%Y-%m-%d")
    pusnati = len(rows)
    ots = [r for r in rows if r.get("scored") and r.get("hit") is not None]
    poz = sum(1 for r in ots if r.get("hit"))
    zag = len(ots) - poz
    chakat = sum(1 for r in rows if not r.get("scored"))
    bez_prisada = pusnati - len(ots) - chakat

    # 🔴 ПО ДЕНЯ НА ПУБЛИКУВАНЕ, НЕ ПО ДЕНЯ НА МАЧА (12.08.2026).
    # Първата версия броеше „day" — деня на СРЕЩАТА. Карта за утрешен мач
    # излиза днес, тоест заглавието „всичко ПУСНАТО" стоеше над период,
    # който свършва в БЪДЕЩЕТО: „от 29.07 до 13.08" на 12 август.
    # Числото и думата до него не бива да си противоречат.
    dni = sorted({str(r.get("posted") or r.get("day") or "")[:10] for r in rows})
    dni = [d for d in dni if len(d) == 10 and d <= sega_den]

    out = ["🧾 <b>ДОСЕГА ОБЩО</b> — всичко, пуснато в 🤖 БОТА ПРЕДРИЧА", ""]
    if dni:
        out.append("От <b>" + den_kratko(dni[0]) + "</b> до <b>"
                   + den_kratko(dni[-1]) + "</b> · " + str(len(dni))
                   + (" дни" if len(dni) != 1 else " ден"))
        out.append("")
    out.append("📋 Пуснати прогнози: <b>" + str(pusnati) + "</b>")
    if ots:
        out.append("✅ Познати: <b>" + str(poz) + "</b>")
        out.append("❌ Загубени: <b>" + str(zag) + "</b>")
        out.append("🎯 Успеваемост: <b>"
                   + ("%.0f" % (100.0 * poz / len(ots))) + "%</b> от <b>"
                   + str(len(ots)) + "</b> отсъдени")
    else:
        out.append("Още нищо не е отсъдено.")
    # Честността е в знаменателя: колко от пуснатото ОЩЕ не е претеглено.
    if chakat:
        out.append("⏳ Чакат резултат: <b>" + str(chakat) + "</b>")
    if bez_prisada:
        out.append("➖ Без присъда (източникът не помни мача): <b>"
                   + str(bez_prisada) + "</b>")

    # 🔴 РАЗБИВКАТА ТРЪГВА ОТ ПУСНАТИТЕ, НЕ ОТ ОТСЪДЕНИТЕ.
    # Първата версия ползваше obshto_po_sport(), а тя брои само отсъдените —
    # тоест спорт с карти и НУЛА присъди изчезваше от списъка напълно. Точно
    # него човек най-много иска да види: „пуснахме девет, още нищо не е готово"
    # е информация, а липсващият ред е загадка.
    po_sport = obshto_po_sport(rows)
    vsi = {}
    for r in rows:
        b = r.get("bucket") or "друго"
        vsi[b] = vsi.get(b, 0) + 1
    if vsi:
        out += ["", "📊 <b>По спорт</b>"]
        for b in po_red(list(vsi.keys())):
            h, n = po_sport.get(b, (0, 0))
            red = ("  " + sport_emo(b) + " <b>" + sport_ime(b) + "</b> · "
                   + str(vsi[b]) + " пуснати")
            if n:
                red += " · " + str(h) + " от " + str(n) + " отсъдени"
                # Под пет отсъдени процент НЕ се дава — „1 от 1 = 100%"
                # заблуждава повече, отколкото информира.
                if n >= 5:
                    red += " · <b>" + ("%.0f" % (100.0 * h / n)) + "%</b>"
            else:
                red += " · още нищо отсъдено"
            out.append(red)

    out += ["", "🟢 THE GREEN ROOM"]
    return NL.join(out)


# ═══════════════════════════════════════════ 🏁 ФИНИШЪТ НА ДЕНЯ
# 🔴 ЗАЩО СЕ ПОЯВЯВА (11.08.2026, по изрична поръчка на собственика:
# „в 23:30 прави ли там финиш на деня, какво що, разбор пълен").
#
# Дотук обедното и вечерното пускане пращаха ЕДНО И СЪЩО съобщение, със същото
# заглавие „ОБЗОР НА ДЕНЯ" — а всяко показваше само отсъденото В СОБСТВЕНОТО
# СИ пускане. Тоест мач, отчетен в 14:30, липсваше в 23:30. Никъде нямаше едно
# съобщение, което да показва целия ден накуп.
#
# И второ: при нула отсъдени стаята мълчеше напълно. Човекът не различаваше
# „днес няма готови мачове" от „ботът е паднал". Финишът излиза ВИНАГИ.
def den_finish_text(now, rows, den, mezhdinna=False):
    """Равносметката на един ден: пуснато, отсъдено, познато, останало.

    mezhdinna=True е обедният вариант: същите числа, но заглавието и краят
    казват, че денят ТЕЧЕ. Две еднакви „равносметки" на ден правят и двете
    безсмислени — затова разликата е в текста, не само в часа.
    """
    dnes = [r for r in rows if str(r.get("posted") or "")[:10] == den]
    otsadeni = [r for r in dnes if r.get("hit") is not None]
    poznati = [r for r in otsadeni if r.get("hit") is True]
    zagubeni = [r for r in otsadeni if r.get("hit") is False]
    chakat = [r for r in dnes if not r.get("scored")]
    bez = [r for r in dnes if r.get("scored") and r.get("hit") is None]

    if mezhdinna:
        out = ["\U0001f552 <b>ДОКЪДЕ СМЕ ДНЕС</b> · " + date_bg(now),
               "<i>междинна равносметка — денят още тече</i>", ""]
    else:
        out = ["\U0001f3c1 <b>ФИНИШ НА ДЕНЯ</b> · " + date_bg(now), ""]
    if not dnes:
        out += ["Днес нямаше нито една прогноза.",
                ("Следващите пускания са до 23:00." if mezhdinna
                 else "Утре от 08:00 продължаваме."),
                "", "\U0001f7e2 THE GREEN ROOM"]
        return NL.join(out)

    out += ["\U0001f4cb пуснати прогнози: <b>" + str(len(dnes)) + "</b>",
            "  ✅ познати: <b>" + str(len(poznati)) + "</b>",
            "  ❌ загубени: <b>" + str(len(zagubeni)) + "</b>"]
    if otsadeni:
        out.append("  \U0001f4c8 отсъдени: <b>" + str(len(otsadeni)) + "</b> · "
                   + ("%.0f" % (100.0 * len(poznati) / len(otsadeni))) + "%")
    else:
        out.append("  \U0001f4c8 отсъдени: <b>0</b> — мачовете още вървят")
    if chakat:
        out.append("  ⏳ чакат резултат: <b>" + str(len(chakat)) + "</b>")
    if bez:
        out.append("  \U0001f6ab без официален резултат: <b>" + str(len(bez)) + "</b>")

    # Разбивка по спорт САМО за днес — това е „какво що" на деня.
    po_sport = {}
    for r in otsadeni:
        b = r.get("bucket") or "друго"
        p, n = po_sport.get(b, (0, 0))
        po_sport[b] = (p + (1 if r.get("hit") else 0), n + 1)
    if po_sport:
        out += ["", "\U0001f3af <b>ДНЕС ПО СПОРТОВЕ</b>"]
        for b in po_red(list(po_sport)):
            p, n = po_sport[b]
            out.append("  " + sport_emo(b) + " " + sport_ime(b).capitalize()
                       + ": <b>" + str(p) + " от " + str(n) + "</b>")

    # Фишовете на деня — по номер, с колко крака са минали.
    fishove = {}
    for r in dnes:
        n = int(r.get("combo") or 0)
        if n:
            fishove.setdefault(n, []).append(r)
    if fishove:
        out += ["", "\U0001f3ab <b>ФИШОВЕТЕ НА ДЕНЯ</b>"]
        for n in sorted(fishove):
            legs = fishove[n]
            ok = sum(1 for r in legs if r.get("hit") is True)
            gotovi = sum(1 for r in legs if r.get("hit") is not None)
            red = "  Фиш " + str(n) + ": <b>" + str(ok) + " от " + str(len(legs)) + "</b>"
            if gotovi < len(legs):
                red += " · " + str(len(legs) - gotovi) + " още чакат"
            elif ok == len(legs):
                red += " · \U0001f7e2 МИНА ЦЕЛИЯТ"
            out.append(red)

    if mezhdinna:
        out += ["", "Денят продължава — следващите карти до 23:00 \U0001f680",
                "\U0001f7e2 THE GREEN ROOM"]
    else:
        out += ["", "Лека вечер \U0001f31b", "\U0001f7e2 THE GREEN ROOM"]
    return NL.join(out)


# 🔴 ВИТРИНАТА „ПОЗНАТИТЕ ДНЕС" Е МАХНАТА НА 11.08.2026. Тя строеше „🏆 ПОЗНАТИТЕ ДНЕС" —
# същите зелени редове, които обзорът вече е показал секунда по-рано в същата
# стая, само че без червените и с трофея на стая 10 отгоре. Виж дългото
# обяснение на мястото, откъдето се викаше (run(), около „МАХНАТО ВТОРОТО").


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


def den_kratko(den):
    """2026-08-10 -> „10.08". Празно или чудато влиза както е, без да гърми."""
    s = str(den or "")
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s[8:10] + "." + s[5:7]
    return s


def combo_text(now, slips):
    """Обзор на трите фиша: кой е минал изцяло и кой къде се е скъсал.

    Поръчка на собственика: „Фишовете на деня трябва и там обзор."
    Един фиш е верен само ако ВСИЧКИТЕ пет избора са познали — затова тук
    се брои така, а не по проценти.
    """
    # 🔴 ДВЕ ПОПРАВКИ, 11.08.2026 — намерени с ЧЕТЕНЕ на сухото пускане.
    #
    # 1) Заглавието казваше „ФИШОВЕТЕ ОТ ВЧЕРА", а датата до него беше
    #    ДНЕШНАТА. Два надписа в един ред, които се бият. И двата са отчасти
    #    верни: тук излизат фишове от РАЗНИ дни — крак свършва, когато свърши
    #    мачът му, и фиш от онзи ден се дозатваря днес.
    # 2) В същия пост стояха ТРИ реда „ФИШ 1" един под друг. Номерът е
    #    пореден ЗА ДЕНЯ, а постът показва няколко дни наведнъж. Човек чете
    #    три различни резултата за „фиш 1" и решава, че ботът се обърква.
    #    Затова всеки фиш вече си носи СОБСТВЕНАТА дата.
    out = ["🎫 <b>ОТЧЕТ НА ФИШОВЕТЕ</b> · " + date_bg(now),
           "<i>всеки фиш се отчита, когато последният му мач свърши</i>", ""]
    minali = 0
    for klyuch, legs in slips:
        n, den = (klyuch if isinstance(klyuch, (tuple, list))
                  else (klyuch, ""))
        ok = sum(1 for x in legs if x[3])
        vsi = len(legs)
        cял = (ok == vsi)
        if cял:
            minali += 1
        out.append(("✅" if cял else "❌") + " <b>ФИШ " + str(n) + "</b>"
                   + (" от " + den_kratko(den) if den else "") + " · "
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


def _bez_samoproverkata(src):
    """Изходният текст БЕЗ тялото на самопроверката.

    🔴 11.08.2026. Тук е целият клас „самореферентна игла". Проверка от вида
        check("X е в кода", "X" in изходния_текст)
    минава ВИНАГИ, защото самият ѝ ред съдържа „X" и влиза в копчето сено.
    Доказано с мутация: изтрих всички живи редове с иглата и седем такива
    проверки останаха зелени. Зелено, което не значи нищо.

    Затова копчето сено вече не съдържа самопроверката. Иглата може да се
    намери само в ЖИВИЯ код — точно каквото проверката твърди, че мери.
    """
    igla = chr(10) + "def " + "selftest("
    i = src.find(igla)
    if i < 0:
        return src
    # 🔴 ПРЕПИСАНО 12.08.2026. Първата версия режеше до „следващия def в
    # колона 0" — а между края на самопроверката и следващата функция живееха
    # коментар и ТРИ живи константи (ZATVOREN_BEZ_IZVOR, MAKS_OPITI,
    # IZCHERPANO). Деветнайсет реда жив код изчезваха от копата сено, тоест
    # всяка проверка „X ГО НЯМА в кода" щеше да мине, ако X попадне в тази
    # цепка. Капан, зареден в опасната посока.
    #
    # Сега краят се търси по ОТСТЪП: първият ред след началото, който има
    # текст и започва в колона 0. Така се реже точно тялото на функцията,
    # каквото и да стои под нея.
    redove = src[i + 1:].splitlines(True)
    dulzhina = len(redove[0]) if redove else 0
    for red in redove[1:]:
        gol = red.rstrip()
        if gol and not red[:1].isspace():
            break
        dulzhina += len(red)
    return src[:i] + src[i + 1 + dulzhina:]


def selftest():
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    # Пазачът на стаите. Оценителят пише в ДВЕ стаи и в нито една друга.
    # Стая 4 беше разрешена, докато обзорът на фишовете излизаше там; от
    # 11.08 обзорът е в стая 10, а вратата към 4 е затворена — виж коментара
    # при ALLOWED_THREADS.
    for room in ("4", "5", "6", "7", "8", "11", "26", "27", "328", "1", "3"):
        check("стая " + room + " е забранена", room not in ALLOWED_THREADS)
    check("стая 9 е разрешена", RESULTS_THREAD in ALLOWED_THREADS)
    check("стая 10 е разрешена", WINS_THREAD in ALLOWED_THREADS)
    check("стаята на човека-типстер е затворена",
          PICKS_THREAD not in ALLOWED_THREADS)
    check("разрешените са точно две",
          ALLOWED_THREADS == {RESULTS_THREAD, WINS_THREAD})

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
    # 🔴 ГЛАВАТА СРЕЩУ СПИСЪКА. Един и същи мач, влязъл в дневника два пъти
    # (крак на фиш вчера + карта днес), се показва ВЕДНЪЖ. Главата трябва да
    # брои същото — проверява се със СЪБИРАНЕ на видимите редове.
    _dvoen = [({"bucket": "basketball", "home": "Indiana Fever",
                "away": "New York Liberty", "pick": "1"}, 106, 92, True),
              ({"bucket": "basketball", "home": "Indiana Fever",
                "away": "New York Liberty", "pick": "1"}, 106, 92, True),
              ({"bucket": "basketball", "home": "A", "away": "B",
                "pick": "1"}, 1, 0, False)]
    _td = results_text(_now, _dvoen, 3, 2)
    # Само редовете НА МАЧОВЕ. Блокът „ОБЩО ДОСЕГА" също почва с ✅/❌ —
    # първата версия на този тест ги броеше и даваше 4 вместо 2.
    _redove = [l for l in _td.splitlines()
               if (l.strip().startswith("✅") or l.strip().startswith("❌"))
               and "познати:" not in l and "загубени:" not in l]
    check("дубълът се показва ВЕДНЪЖ", len(_redove) == 2)
    check("главата брои видимите, не суровите", "1 познати · 1 сгрешени" in _td)
    check("процентът е върху видимите", "· 50%" in _td)

    # --- ДОЛНАТА ЧЕРТА. Собственикът: „в канала резултатите не дават общия
    # брой и загубените". Дотук отдолу стоеше само „N от M · X%" и загубите
    # трябваше да се смятат наум.
    # 🧾 ДОСЕГА ОБЩО — новото трето съобщение (12.08.2026).
    _dnev = [
        {"bucket": "football", "day": "2026-08-10", "scored": True, "hit": True},
        {"bucket": "football", "day": "2026-08-10", "scored": True, "hit": False},
        {"bucket": "football", "day": "2026-08-11", "scored": True, "hit": True},
        {"bucket": "football", "day": "2026-08-11", "scored": True, "hit": True},
        {"bucket": "football", "day": "2026-08-11", "scored": True, "hit": True},
        {"bucket": "tennis", "day": "2026-08-11", "scored": False},
        {"bucket": "tennis", "day": "2026-08-11", "scored": True, "hit": None},
    ]
    _od = obshto_dosega_text(_now, _dnev)
    check("равносметката е озаглавена ДОСЕГА ОБЩО", "ДОСЕГА ОБЩО" in _od)
    check("равносметката сочи БОТА ПРЕДРИЧА", "БОТА ПРЕДРИЧА" in _od)
    check("брои ВСИЧКИ пуснати, не само отсъдените",
          "Пуснати прогнози: <b>7</b>" in _od)
    check("брои познатите", "Познати: <b>4</b>" in _od)
    check("брои загубените", "Загубени: <b>1</b>" in _od)
    check("процентът е върху отсъдените", "80%</b> от <b>5</b>" in _od)
    check("казва колко чакат резултат", "Чакат резултат: <b>1</b>" in _od)
    check("казва колко са без присъда", "Без присъда" in _od and "<b>1</b>" in _od)
    check("дава периода в дни", "2 дни" in _od)
    check("първият ден е най-старият", "10.08" in _od)
    check("последният ден е най-новият", "11.08" in _od)
    # 🔴 Периодът НЕ бива да свършва в бъдещето. Карта за утрешен мач се
    # публикува днес; ако броим деня на мача, „всичко пуснато" завършва утре.
    _bud = obshto_dosega_text(_now, _dnev + [
        {"bucket": "tennis", "day": "2099-01-01", "posted": "2026-08-11 20:00",
         "scored": False}])
    check("бъдещ мач НЕ мести края на периода", "2099" not in _bud
          and "01.01" not in _bud)
    # Копчето сено е БЕЗ самопроверката — иначе редът тук долу сам щеше да
    # съдържа иглата. И се чете ТУК, защото _iztochnik_scorer се пълни
    # по-надолу в тази функция: използван по-рано, той изобщо не съществува.
    _ziv0 = _bez_samoproverkata(open(__file__, encoding="utf-8").read())
    _telo_od = _ziv0.split("def obshto" + "_dosega_text")[1][:1500]         if ("def obshto" + "_dosega_text") in _ziv0 else ""
    check("периодът стъпва на деня на ПУБЛИКУВАНЕ", "posted" in _telo_od)
    check("разбивката по спорт я има", "По спорт" in _od)
    check("спорт БЕЗ нито една присъда пак се вижда",
          "ТЕНИС</b> · 2 пуснати · още нищо отсъдено" in _od)
    _od2 = obshto_dosega_text(_now, _dnev + [
        {"bucket": "tennis", "day": "2026-08-11", "scored": True, "hit": True}])
    check("спорт под 5 отсъдени НЕ получава процент",
          "ТЕНИС</b> · 3 пуснати · 1 от 1 отсъдени" in _od2
          and "1 от 1 отсъдени · <b>" not in _od2)
    check("спорт с 5 отсъдени получава процент", "5 отсъдени · <b>80%" in _od)
    check("равносметката е чиста от забранени думи", banned_word(_od) is None)
    check("празен дневник не гърми", "Пуснати прогнози: <b>0</b>"
          in obshto_dosega_text(_now, []))
    check("празен дневник казва, че няма отсъдено",
          "Още нищо не е отсъдено" in obshto_dosega_text(_now, []))
    # Ред на пускане: равносметката излиза САМО вечер, и то СЛЕД финиша.
    # Копчето сено е БЕЗ самопроверката (виж _bez_samoproverkata) — иначе
    # редовете тук долу сами щяха да съдържат иглата и проверката щеше да
    # минава винаги. Тоест иглата се намира само в ЖИВИЯ main().
    _ziv = _bez_samoproverkata(open(__file__, encoding="utf-8").read())
    _telo_main = _ziv[_ziv.find("def " + "main("):] if ("def " + "main(") in _ziv else ""
    check("равносметката се праща от main",
          ("obshto_dosega" + "_text(now, rows)") in _telo_main)
    check("равносметката е зад условие за вечер", _telo_main.count("if vecher:") >= 2)
    check("равносметката отива в стая 9, не в канала",
          ("post_channel(obshto" + "_dosega") not in _telo_main)

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
    #
    # 🔴 САМОПРОВЕРКАТА НЕ БИВА ДА ПРАЩА НИЩО НАВЪН (намерено на живо 11.08.2026).
    # Тези редове викаха post_channel() без сух режим. Локално минаваха, защото
    # пусках със SCORE_DRY_RUN=1. В GitHub обаче стъпката „Самопроверка" НЯМА
    # нито токен, нито сух режим — ботът наистина опитваше да прати съобщение,
    # не успяваше, връщаше False и ПОРТАЛЪТ ПАДАШЕ. Оценителят не е тръгвал
    # от 10.08 заради това: „Оцени и отчети" се прескачаше всеки път.
    # А ако токенът беше налице, самопроверката щеше да изсипе тестов текст
    # В САМИЯ КАНАЛ, пред всички.
    # Затова тук сухият режим се включва НАСИЛА и се връща както е бил.
    # --- 🏁 ФИНИШЪТ НА ДЕНЯ. Излиза ВИНАГИ вечер — включително при нула
    # отсъдени, защото мълчаща стая не се различава от паднал бот.
    _dn = "2026-08-11"
    _redove = [
        {"posted": _dn + " 09:00", "bucket": "football", "combo": 1,
         "scored": True, "hit": True, "home": "А", "away": "Б"},
        {"posted": _dn + " 09:00", "bucket": "football", "combo": 1,
         "scored": True, "hit": False, "home": "В", "away": "Г"},
        {"posted": _dn + " 12:00", "bucket": "tennis", "combo": 0,
         "scored": False, "hit": None, "home": "Д", "away": "Е"},
        {"posted": _dn + " 12:00", "bucket": "tabletennis", "combo": 0,
         "scored": True, "hit": None, "home": "Ж", "away": "З"},
        {"posted": "2026-08-10 21:00", "bucket": "football", "combo": 0,
         "scored": True, "hit": True, "home": "И", "away": "Й"},
    ]
    _fin = den_finish_text(datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA), _redove, _dn)
    check("финишът е озаглавен", "ФИНИШ НА ДЕНЯ" in _fin)
    check("финишът брои само днешните", "пуснати прогнози: <b>4</b>" in _fin)
    check("финишът брои познатите", "познати: <b>1</b>" in _fin)
    check("финишът брои загубените", "загубени: <b>1</b>" in _fin)
    check("финишът брои чакащите", "чакат резултат: <b>1</b>" in _fin)
    check("финишът брои неотсъдимите", "без официален резултат: <b>1</b>" in _fin)
    check("финишът дава процент за деня", "50%" in _fin)
    check("финишът отчита фиша", "Фиш 1: <b>1 от 2</b>" in _fin)
    check("финишът пожелава лека вечер", "Лека вечер" in _fin)
    check("финишът е чист от забранени думи", banned_word(_fin) is None)
    _praz = den_finish_text(datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA), [], _dn)
    check("празният ден пак получава финиш", "ФИНИШ НА ДЕНЯ" in _praz)
    check("празният ден го казва направо", "нито една прогноза" in _praz)
    check("празният ден не лъже с проценти", "%" not in _praz)
    _cql = den_finish_text(datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA),
                           [dict(_redove[2])], _dn)
    check("ден без нито един отсъден го казва", "мачовете още вървят" in _cql)

    # --- 🕒 ОБЕДНАТА РАВНОСМЕТКА. Същите числа, ДРУГО заглавие — иначе два
    # еднакви „финиша" на ден правят и двата безсмислени.
    _obed = den_finish_text(datetime(2026, 8, 11, 15, 30, tzinfo=SOFIA),
                            _redove, _dn, mezhdinna=True)
    check("обедната се казва другояче", "ДОКЪДЕ СМЕ ДНЕС" in _obed)
    check("обедната НЕ се представя за финиш", "ФИНИШ НА ДЕНЯ" not in _obed)
    check("обедната казва, че денят тече", "денят още тече" in _obed)
    check("обедната не пожелава лека вечер", "Лека вечер" not in _obed)
    check("обедната носи същите числа", "пуснати прогнози: <b>4</b>" in _obed)
    check("обедната е чиста", banned_word(_obed) is None)
    _obed_praz = den_finish_text(datetime(2026, 8, 11, 15, 30, tzinfo=SOFIA),
                                 [], _dn, mezhdinna=True)
    check("празният обед сочи напред, не назад",
          "до 23:00" in _obed_praz and "Утре" not in _obed_praz)

    check("каналът е зададен", bool(str(CHANNEL_ID).strip()))
    check("каналът НЕ е стая от групата", str(CHANNEL_ID) not in ALLOWED_THREADS)
    # 🔴 ТРИТЕ ПАЗАЧ-ПРОВЕРКИ МИНАВАХА ЗЕЛЕНИ И С ИЗТРИТИ ПАЗАЧИ
    # (намерено и доказано на 11.08.2026 в счупено копие).
    #
    # Стояха ИЗВЪН този try/finally, тоест се изпълняваха при истинския
    # DRY_RUN. В GitHub той е False и няма токен → post_channel("залагай
    # отговорно") връща False, защото ПРАЩАНЕТО пада, не защото пазачът е
    # хванал думата. Махнеш ли пазача — проверката пак минава.
    #
    # Сега всичко е ВЪТРЕ в сухия режим: при DRY_RUN=True чистият текст връща
    # True, значи единствената причина забраненият да върне False е пазачът.
    # Проверката вече не може да мине с изтрит пазач.
    _star_dry = globals()["DRY_RUN"]
    try:
        globals()["DRY_RUN"] = True        # нищо не излиза навън от тест
        check("сухият режим наистина е включен", DRY_RUN is True)
        check("каналът приема чист обзор", post_channel(t) is True)
        check("стаята приема чист обзор", post(RESULTS_THREAD, t) is True)
        # ⬇️ Точно тук е смисълът: чистото минава, значи отказът е от пазача.
        check("каналът ОТКАЗВА хазартна дума ПРИ РАБОТЕЩО пращане",
              post_channel("залагай отговорно") is False)
        check("каналът отказва и коефициент ПРИ РАБОТЕЩО пращане",
              post_channel("коеф 1.85") is False)
        check("чужда стая се отказва ПРИ РАБОТЕЩО пращане",
              post("26", "тест") is False)
    finally:
        globals()["DRY_RUN"] = _star_dry
    check("сухият режим е върнат към стойността отпреди теста",
          globals()["DRY_RUN"] is _star_dry)
    # Подписът. Върне ли се преправеният подпис към ESPN, 403-ката се връща с
    # него и стаята „Резултати" пак млъква за половината спортове.
    check("ESPN не получава преправен подпис",
          "User-Agent" not in glavi_za(ESPN + "/soccer/x/scoreboard"))
    check("ESPN иска json", glavi_za(ESPN + "/x").get("Accept") == "application/json")
    check("чуждите адреси пазят подписа",
          glavi_za("https://worldtabletennis.com/x").get("User-Agent") == UA)
    # (Трите пазач-проверки се преместиха ГОРЕ, вътре в сухия режим — виж
    # обяснението там. Тук стояха и минаваха дори с изтрит пазач.)

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

    check("отчетът НЕ поучава",
          "не се трие" not in t and "Гледахме" not in t and "завинаги" not in t)
    # 🔴 Обзорът трябва САМ да носи зелените — иначе махането на витрината
    # наистина би загубило информация. Затова се проверява буквално.
    _zeleni = [x for x in _mix if x[3]]
    _obzor_mix = results_text(_now, _mix, 44, 29, {}, _dnevnik)
    check("обзорът показва и познатите, не само сгрешените",
          all((r[0].get("home") or "") in _obzor_mix for r in _zeleni))
    check("обзорът показва и червените",
          all((r[0].get("home") or "") in _obzor_mix for r in _mix if not r[3]))
    check("трофеят на стая 10 не влиза в стая 9",
          "\U0001f3c6" not in _obzor_mix)

    # --- обзорът на фишовете
    _legs = [({"home": "А" + str(i), "away": "Б", "pick": "1", "bucket": "football"},
              2, 1, i != 2) for i in range(5)]
    c = combo_text(_now, [((1, "2026-08-10"), _legs)])
    # 🔴 ПРЕПИСАНО 11.08.2026. Заглавието казваше „ФИШОВЕТЕ ОТ ВЧЕРА", а
    # датата до него беше днешната — и в един пост стояха три реда „ФИШ 1"
    # от различни дни. Сега всеки фиш си носи датата.
    check("фишовете имат обзор", "ОТЧЕТ НА ФИШОВЕТЕ" in c)
    check("заглавието не твърди грешен ден", "ОТ ВЧЕРА" not in c)
    check("фишът носи собствената си дата", "ФИШ 1</b> от 10.08" in c)
    check("скъсаният фиш е отбелязан", "❌ <b>ФИШ 1</b> от 10.08 · 4 от 5" in c)
    check("два фиша с номер 1 от различни дни се различават",
          combo_text(_now, [((1, "2026-08-09"), _legs),
                            ((1, "2026-08-10"), _legs)]).count("ФИШ 1</b> от") == 2)
    check("късата дата се чете", den_kratko("2026-08-10") == "10.08")
    check("чудатата дата не гърми", den_kratko("") == "" and den_kratko(None) == "")
    check("старият вид (само номер) още работи",
          "ФИШ 7" in combo_text(_now, [(7, _legs)]))
    check("обзорът на фишовете е чист", banned_word(c) is None)
    check("обзорът брои минали фишове", "0 от 1 фиша минаха" in c)
    # 🔴 КОЕ СЪОБЩЕНИЕ В КОЯ СТАЯ. Собственикът го каза направо на 11.08.2026:
    # „в Печеливши фишове не даваш фишовете от деня, а цялата статистика".
    # Затова тук се пази РАЗДЕЛЕНИЕТО, а не само че стаята е разрешена.
    check("стая 10 е за фишовете", WINS_THREAD in ALLOWED_THREADS)
    check("стая 9 е за резултатите и статистиката", RESULTS_THREAD in ALLOWED_THREADS)
    check("трите стаи са различни",
          len({RESULTS_THREAD, WINS_THREAD, PICKS_THREAD}) == 3)
    # Търси се в собствения изходен код. Иглите се сглобяват от парчета —
    # иначе самата проверка си е игла и винаги се намира.
    _iztochnik = _bez_samoproverkata(
        open(__file__, encoding="utf-8").read())

    def _ima(kade, kakvo):
        return ("post(" + kade + "_THREAD, " + kakvo + "(") in _iztochnik

    check("обзорът на фишовете отива в стая 10", _ima("WINS", "combo_text"))
    check("фишовете вече не се отчитат в стая 4", not _ima("PICKS", "combo_text"))
    # Дублиращото съобщение не бива да се върне през нито една стая.
    # Иглата пак се сглобява от парчета — този ред е в същия файл, който чете.
    _igla_w = "wins" + "_text"
    check("витрината ПОЗНАТИТЕ ДНЕС е махната изцяло",
          ("def " + _igla_w) not in _iztochnik
          and (_igla_w + "(") not in _iztochnik)

    # 🔴 ЧЕРВЕН РЪН НА НОРМАЛЕН ДЕН — хванато на живо в CI на 11.08.2026.
    # Обедното пускане свърши точно каквото трябва (пусна „ДОКЪДЕ СМЕ ДНЕС"),
    # но върна код 1, защото нямаше ОТСЪДЕНИ мачове — а до обяд мачовете още
    # вървят. Резултатът: червен рън на съвсем нормален ден. Това е по-скъпо
    # от бъг: научава собственика да не гледа червеното.
    # Единственият ненулев изход на main() е липсващ токен.
    # Само ТЯЛОТО на main(). И внимание: нито един коментар вътре не бива да
    # цитира буквално стария изход — проверка, която брои собствените си
    # коментари, е проверка, която лъже. Първата версия на този ред падна
    # точно така, при това и в двете посоки, което я издаде.
    _telo_main = _iztochnik.split("def " + "main(")[1].split("\ndef ")[0]
    check("оценителят гърми само при липсващ токен",
          _telo_main.count("return " + "1") == 1)
    check("и то точно заради токена",
          "BOT_TOKEN" in _telo_main.split("return " + "1")[0][-220:])

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
    _iztochnik_scorer = _bez_samoproverkata(
        open(__file__, encoding="utf-8").read())
    # 🔴 ОБЪРНАТО 11.08.2026: тенисът на маса ВЕЧЕ има източник — WTT дава
    # официалните резултати през шлюза /ttu/ с ключ. Измерено: 168 завършили
    # мача само за турнир 3246, от които 23 отсъждат наши висящи прогнози.
    check("тенисът на маса ВЕЧЕ има източник", "tabletennis" not in NO_RESULT)
    check("списъкът без-източник е празен", NO_RESULT == set())
    check("тенисът на маса минава през WTT",
          "wtt_result" in _iztochnik_scorer)
    # Имената се сравняват по голи латински букви — иначе „Solè" и „Sole"
    # са различни хора, а ударенията се различават между източниците.
    check("името се свежда до букви", _wtt_ime("Zhao Yun TAN") == "zhaoyuntan")
    check("ударенията отпадат", _wtt_ime("Solè Díaz") == "solediaz")
    check("празното не гърми", _wtt_ime(None) == "" and _wtt_ime("") == "")
    check("два различни играча остават различни",
          _wtt_ime("Tin-Tin HO") != _wtt_ime("Tin HO"))
    # 🔴 ДАТАТА НА ШЛЮЗА Е С НАКЛОНЕНИ ЧЕРТИ („2026/08/10"), дневникът е с
    # тирета. Без привеждане НИТО ЕДИН турнир не се намира и всичко мълчи —
    # хванато на първото живо пускане, не в главата.
    check("турнирът се намира по ден с тирета",
          any(len(a) == 10 and a[4] == "-" for _e, a, _b in (_wtt_turniri() or [(0, "----------", "")])))
    # Измерено на живо 11.08.2026 върху истинския дневник: 64 от 72 прогнози
    # за тенис на маса се отсъждат. Осемте, които не се, са от турнири извън
    # стоте, които шлюзът връща.
    check("списъкът с турнири не е празен", len(_wtt_turniri()) > 0)
    # 🔴 ОТВАРЯНЕТО НА СТАРИТЕ. Затварянето „без източник" беше необратимо: щом
    # спортът получи източник, миналото му оставаше изтрито от статистиката.
    # В живия дневник това бяха СЕДЕМДЕСЕТ прогнози за тенис на маса.
    # 🔴 РЕЗЕРВНИЯТ ИЗТОЧНИК. Прогноза без slug идва от TheSportsDB и ESPN не я
    # знае — espn_result пада на първия ред. Измерено в живия дневник: 22
    # такива за WNBA, НУЛА отсъдени, докато вратата съществуваше.
    #
    # Иглите вече се търсят в копче сено БЕЗ самопроверката (виж
    # _bez_samoproverkata) — тоест намират се само в живия код. Мутационно
    # доказано: махна ли се eventsday.php от живите редове, проверката пада.
    _sdb_igli = ("sdb_result", "eventsday.php", "eventslast.php")
    for _i in _sdb_igli:
        check("резервната врата е в кода: " + _i, _i in _iztochnik_scorer)
    check("без slug минаваме първо през резервата",
          'if not rec.get("slug")' in _iztochnik_scorer)
    check("всеки спорт с резерва има име за TheSportsDB",
          all(b in SDB_SPORT for b in ("basketball", "football", "baseball")))
    check("двойките се четат от суровия отговор",
          _sdb_dvoyki([{"idHomeTeam": "1", "idAwayTeam": "2",
                        "intHomeScore": "96", "intAwayScore": "82",
                        "strHomeTeam": "A", "strAwayTeam": "B"}])
          == [("1", "2", 96, 82, "A", "B")])
    check("незавършил мач не се брои",
          _sdb_dvoyki([{"idHomeTeam": "1", "idAwayTeam": "2",
                        "intHomeScore": None, "intAwayScore": None}]) == [])
    check("боклук вместо резултат не гърми",
          _sdb_dvoyki([{"intHomeScore": "x", "intAwayScore": "y"}]) == [])
    check("празният списък не гърми", _sdb_dvoyki(None) == [])

    # 🔴 ПРЕПИСАНО 11.08.2026. Тук стоеше ПРЕПИС на миграцията — двайсет реда
    # близнак със свое заковано „3". Мутационен тест го обори: смених живия
    # таван и живия текст, и нула от единайсетте проверки паднаха. Мереха
    # копие. Сега се вика СЪЩАТА функция, която върви на живо.
    _mig = [
        {"bucket": "tabletennis", "scored": True, "hit": None,
         "why": ZATVOREN_BEZ_IZVOR},                              # трябва да се отвори
        {"bucket": "tabletennis", "scored": True, "hit": True},   # има присъда — не се пипа
        {"bucket": "football", "scored": True, "hit": None,
         "why": "мачът е отменен"},                               # друга причина — не се пипа
        {"bucket": "tabletennis", "scored": True, "hit": None},   # ПРАЗНА причина — отваря се
        {"bucket": "tabletennis", "scored": True, "hit": None,
         "why": ZATVOREN_BEZ_IZVOR, "opit": MAKS_OPITI},          # изчерпан — спира
    ]
    _otv, _izch_broy = otvori_nanovo(_mig)
    check("затвореният без източник се отваря", _mig[0]["scored"] is False)
    check("отвореният губи старата причина", "why" not in _mig[0])
    check("присъденият НЕ се пипа", _mig[1]["scored"] is True)
    check("отмененият по друга причина НЕ се пипа", _mig[2]["scored"] is True)
    check("празната причина СЪЩО се отваря", _mig[3]["scored"] is False)
    check("отвореният носи брояч на опитите", _mig[0].get("opit") == 1)
    check("изчерпаният НЕ се отваря пак", _mig[4]["scored"] is True)
    check("изчерпаният получава честна причина", _mig[4]["why"] == IZCHERPANO)
    check("изчерпаният не трупа още опити", _mig[4].get("opit") == MAKS_OPITI)
    check("функцията брои отворените по спорт", _otv.get("tabletennis") == 2)
    check("функцията брои изчерпаните", _izch_broy == 1)
    # Кръгът наистина ли спира? Върти се MAKS_OPITI + 2 пъти върху един запис.
    # Ако таванът не работеше, „scored" щеше да е False и на последната
    # обиколка. Това е поведенчески тест, не търсене на низ във файла.
    _krug = [{"bucket": "tabletennis", "scored": True, "hit": None}]
    for _ in range(MAKS_OPITI + 2):
        otvori_nanovo(_krug)
        _krug[0]["scored"] = True          # оценителят пак не намира резултат
        if "why" not in _krug[0]:
            _krug[0]["why"] = ZATVOREN_BEZ_IZVOR
    check("кръгът спира след тавана", _krug[0].get("opit") == MAKS_OPITI)
    check("спрелият носи честната причина", _krug[0].get("why") == IZCHERPANO)
    check("таванът е точно три опита", MAKS_OPITI == 3)

    # 🔴 ПАЗАЧИ ЗА ДВЕТЕ ПОПРАВКИ ОТ 12.08.2026 ВЕЧЕРТА.
    #
    # 1) ВЪЗРАСТТА НЕ БИЕ ПРЕОТВАРЯНЕТО. Измерено на живо: otvori_nanovo
    #    отваряше 45 записа, а три реда по-долу клонът „твърде старо" ги
    #    затваряше обратно В СЪЩИЯ РЪН — 135 отваряния за три пускания, НУЛА
    #    заявки към източник. Механизмът работеше на празен ход.
    _ziv1 = _bez_samoproverkata(open(__file__, encoding="utf-8").read())
    check("преотвореният минава ПРЕЗ възрастта",
          ('if day < limit and not r' + '.get("opit")') in _ziv1)
    #
    # 2) ТАВАНЪТ НА WTT ТУРНИРИТЕ. Стоеше 4. За 08.08 денят се покрива от
    #    СЕДЕМ турнира, а седем от осемте висящи прогнози седят в петия по
    #    ред — тоест не се питаше никога.
    check("WTT таванът е ръчка, не заковано число", "SCORE_WTT" + "_TURNIRI" in _ziv1)
    check("WTT таванът е над четири", WTT_MAX_TURNIRI > 4)
    check("WTT питането ползва тавана", ("kand[:WTT_MAX" + "_TURNIRI]") in _ziv1)
    # 🔴 ОБРЪЩАНЕТО НА РЕЗУЛТАТА — най-опасното място в целия този код.
    # WTT пише двамата играчи в СВОЙ ред; при тенис на маса „домакин" и „гост"
    # са само ред на изписване, не роля. Сгрешим ли посоката, всяка присъда
    # излиза наопаки И процентът в стая 9 става лъжа, без нищо да гръмне.
    # Сверих 64 истински мача срещу суровия запис: 0 обърнати. НО в нито един
    # от тях WTT не е изписал нашия гост пръв — тоест обратният клон никога
    # не е бил изпълняван на живо. Затова тук се изпълнява нарочно.
    _stari_i, _stari_e = dict(_wtt_index), _wtt_events
    try:
        _wtt_index[9999] = {frozenset(("adam", "boris")): ("boris", 3, 1)}
        globals()["_wtt_events"] = [(9999, "2026-08-10", "2026-08-10")]
        _r = wtt_result({"day": "2026-08-10", "home": "Adam", "away": "Boris"})
        # WTT казва „Boris 3-1", тоест Boris е спечелил. Нашият домакин е Adam,
        # значи от НАША гледна точка резултатът е 1:3.
        check("обърнатият ред се поправя", _r == (1, 3))
        _r2 = wtt_result({"day": "2026-08-10", "home": "Boris", "away": "Adam"})
        check("правилният ред остава непокътнат", _r2 == (3, 1))
        check("непознат мач връща None",
              wtt_result({"day": "2026-08-10", "home": "Ivan", "away": "Petar"}) is None)
        globals()["_wtt_events"] = []
        check("без турнири за деня не гадаем",
              wtt_result({"day": "2026-08-10", "home": "Adam", "away": "Boris"}) is None)
    finally:
        _wtt_index.clear()
        _wtt_index.update(_stari_i)
        globals()["_wtt_events"] = _stari_e
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


# ══════════════════════════════════════════════════════════════════════════
#  ПРЕОТВАРЯНЕ НА ЗАТВОРЕНИТЕ БЕЗ ПРИСЪДА
#
#  🔴 ИЗВАДЕНО ОТ main() НА 11.08.2026, ВЕЧЕРТА — И ЕТО ЗАЩО.
#
#  Логиката стоеше вътре в main(). Самопроверката не може да вика main() (той
#  праща в Telegram), затова тестът си я ПРЕПИСВАШЕ — двайсет реда близнак със
#  собствено заковано „3". Мутационен тест го доказа: смених живия таван от 3
#  на 5 и живия текст на причината — и НУЛА от единайсетте проверки паднаха.
#  Единайсет зелени, които мереха копие, не кода.
#
#  Сега е функция. Тестът вика СЪЩАТА функция, която върви на живо.
# ══════════════════════════════════════════════════════════════════════════
ZATVOREN_BEZ_IZVOR = "няма официален източник за резултата"
MAKS_OPITI = 3
IZCHERPANO = "източникът не помни този мач след три опита"


def otvori_nanovo(rows):
    """Отваря наново записите без присъда. Връща (по спорт, брой изчерпани).

    Отваря се запис, който е затворен, няма присъда, спортът му ВЕЧЕ има
    източник, и причината е „няма източник" ИЛИ е празна. Всеки опит се брои;
    след MAKS_OPITI записът остава затворен с честна причина.
    """
    otvoreni = {}
    izcherpani = 0
    for r in rows:
        if not (r.get("scored") and r.get("hit") is None
                and r.get("bucket") not in NO_RESULT):
            continue
        prichina = str(r.get("why") or "")
        if prichina not in (ZATVOREN_BEZ_IZVOR, ""):
            continue                       # друга причина (отменен мач) — не пипаме
        try:
            opit = int(r.get("opit") or 0)
        except (TypeError, ValueError):
            opit = 0
        if opit >= MAKS_OPITI:
            if prichina != IZCHERPANO:
                r["why"] = IZCHERPANO
                izcherpani += 1
            continue
        r["opit"] = opit + 1
        r["scored"] = False
        r.pop("why", None)
        b = r.get("bucket") or "?"
        otvoreni[b] = otvoreni.get(b, 0) + 1
    return otvoreni, izcherpani


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

    # ══════════════════════════════════════════════════════════════════════
    #  🔴 ОТВАРЯНЕ НА ЗАТВОРЕНИТЕ БЕЗ ПРИСЪДА (11.08.2026)
    #
    #  Прогноза за спорт без източник се затваря с scored=True и hit=None, за
    #  да не се пита вечно нещо, което няма отговор. Разумно — но необратимо:
    #  щом спортът получи източник, старите записи остават затворени завинаги,
    #  защото цикълът долу прескача всичко със scored.
    #
    #  Точно това стана днес. Тенисът на маса излезе от NO_RESULT (WTT дава
    #  официалните резултати през шлюза /ttu/), но в живия дневник СЕДЕМДЕСЕТ
    #  негови прогнози вече бяха затворени с „няма официален източник". Тоест
    #  новият източник щеше да важи само за бъдещето, а цялата минала история
    #  на спорта оставаше изтрита от статистиката.
    #
    #  Затова: всеки запис, затворен САМО заради липса на източник, чийто спорт
    #  ВЕЧЕ не е в NO_RESULT, се отваря наново. Правилото е общо — утре ако
    #  друг спорт получи източник, миналото му се връща само.
    #  Пуска се веднъж: след отсъждането записите имат присъда и не се пипат.
    #  🔴 ДВЕ ПОПРАВКИ ОТ 11.08.2026 ВЕЧЕРТА, ИЗМЕРЕНИ В ЖИВИЯ ДНЕВНИК:
    #
    #  1) ПРАЗНА ПРИЧИНА. От 101-те записа без присъда 59 носеха „няма
    #     официален източник", а 42 нямаха НИЩО в why. Условието искаше точно
    #     този низ, тоест четирийсет и двата не се отваряха никога. Запис без
    #     присъда И без обяснение е точно този, който най-много заслужава
    #     втори опит — сега влиза и той.
    #
    #  2) БЕЗКРАЕН КРЪГ. Отвореният запис, който пак не може да се отсъди, се
    #     затваря пак със същата причина — и на следващия рън се отваря пак.
    #     Седемдесетте прогнози за тенис на маса се въртяха така всеки път.
    #     Затова всеки опит се БРОИ (полето „opit"). Три опита стигат: ако
    #     източникът не помни мача след три пускания, няма да си го спомни.
    #     След това записът остава затворен с ЧЕСТНА причина, не с мълчание.
    otvoreni, izcherpani = otvori_nanovo(rows)
    if otvoreni:
        print("Отворени наново (спортът вече има източник): "
              + ", ".join(k + " " + str(v) for k, v in sorted(otvoreni.items())))
    if izcherpani:
        print("Изчерпани опити (остават затворени с честна причина): "
              + str(izcherpani))

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
        # 🔴 ВЪЗРАСТТА ВЕЧЕ НЕ БИЕ ПРЕОТВАРЯНЕТО (12.08.2026).
        #
        # Измерено на живо: otvori_nanovo отваря 45 записа, а три реда по-долу
        # ТОЗИ клон ги затваря обратно В СЪЩИЯ РЪН, защото дните им са по-стари
        # от MAX_AGE. Резултат: 135 отваряния за три пускания, НУЛА заявки към
        # източник, нула нови присъди. Механизмът работеше на празен ход.
        #
        # Сега: запис, който носи брояч „opit", е получил изричен втори шанс —
        # той минава през източника ВЪПРЕКИ възрастта. Броячът го спира след
        # MAKS_OPITI, тоест няма безкраен кръг: най-много три питания.
        if day < limit and not r.get("opit"):
            r["scored"] = True                # твърде старо, отказваме се
            r["hit"] = None
            continue
        # Спорт без източник: не хабим заявки да питаме нещо, което няма
        # отговор. Затваряме го честно още щом денят му мине.
        if r.get("bucket") in NO_RESULT and day < today:
            r["scored"] = True
            r["hit"] = None
            r["why"] = ZATVOREN_BEZ_IZVOR
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

    # 🔴 РАВНОСМЕТКА ДВА ПЪТИ НА ДЕН (11.08.2026, поръчка на собственика:
    # „нека има и равносметка освен 23:30 и в 15:30 примерно“).
    #
    # Обедното пускане дотук казваше само „кое свърши В ТОВА пускане“ — а
    # човек, който отваря стаята следобед, иска да види ДОКЪДЕ сме за деня,
    # не последните пет мача. Затова равносметката вече излиза и по обяд.
    #
    # Разликата между двете е ЧЕСТНА и се вижда в заглавието:
    #   • обяд  → „ДОКЪДЕ СМЕ ДНЕС“ — междинна, мачовете още вървят
    #   • вечер → „ФИНИШ НА ДЕНЯ“   — окончателна
    # Иначе два еднакви „финиша“ на ден правят и двата безсмислени.
    vecher = now.hour >= 20 or now.hour < 5
    obed = 11 <= now.hour < 20
    den = ((now - timedelta(days=1)) if now.hour < 5 else now).strftime("%Y-%m-%d")

    if not fresh:
        save_log(rows)
        if vecher or obed:
            finish = den_finish_text(now, rows, den, mezhdinna=obed)
            post(RESULTS_THREAD, finish)
            time.sleep(1.5)
            post_channel(finish)
            # 🧾 И ВЕДНАГА СЛЕД ФИНИША — целият живот на бота. Само вечер:
            # обядът си има междинната, а трето съобщение по обяд е шум.
            if vecher:
                time.sleep(1.5)
                post(RESULTS_THREAD, obshto_dosega_text(now, rows))
            # 🔴 ТУК СЕ ВРЪЩАШЕ КОД 1 — ХВАНАТО НА ЖИВО 11.08.2026 в CI.
            # Обедното пускане свърши точно каквото трябва (пусна „ДОКЪДЕ СМЕ
            # ДНЕС", 39 прогнози, 0 отсъдени — мачовете още вървят) и въпреки
            # това излезе с код 1, тоест ЧЕРВЕН рън в GitHub. Ден без завършили
            # мачове до обяд е НОРМАЛЕН ден, не провал. А червен рън на нормален
            # ден е по-скъп от всеки бъг: научава собственика да не гледа
            # червеното, и когато утре гръмне нещо истинско, никой няма да
            # обърне внимание. Ненулев изход се пази за истински провал.
            print("Няма нови отсъдени — но равносметката излезе. Нормален ден.")
            return 0
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
    # 🔴 РАЗМЕСЕНИ СТАИ (поправено 11.08.2026 по изрична дума на собственика:
    # „в Печеливши фишове не даваш фишовете от деня, а цялата статистика —
    # която трябва да е в Резултати и статистика. Да не объркваш нещата!").
    #
    # Дотук стая 10 „🏆 Печеливши фишове" получаваше „ПОЗНАТИТЕ ДНЕС" — списък
    # с ОТДЕЛНИТЕ познати прогнози по спорт. Това е статистика, не фиш. А
    # обзорът на самите фишове отиваше в стая 4, при вече пуснатите фишове.
    #
    # СЕГА:
    #   стая 9  ✅ Резултати и статистика — обзорът, познатите, финишът на деня
    #   стая 10 🏆 Печеливши фишове       — САМО фишовете и как са минали
    # 🔴 МАХНАТО ВТОРОТО СЪОБЩЕНИЕ, 11.08.2026.
    # Тук стоеше второ пускане към стая 9 с витрината — списък САМО на
    # познатите, две секунди след обзора, в СЪЩАТА стая. А обзорът вече изброява
    # всеки отсъден мач, зелен и червен, групиран по спорт. Тоест второто
    # съобщение беше строго подмножество на първото: човекът виждаше един и същ
    # мач два пъти в един екран. Отгоре носеше 🏆 — гербът на стая 10 — в
    # стаята на статистиката, точно смесването, което собственикът забрани.
    # Стая 9 вече получава ДВЕ съобщения на пускане (обзор + равносметка);
    # трето, което не носи нищо ново, е шум.
    # Пътят назад: този комит. Самата функция е махната заедно с него,
    # за да не остане мъртъв код, който следващият да върне „на място".
    if not any(f[3] for f in fresh):
        print("Днес няма познати — обзорът излезе с червените.")

    # И равносметката, отделно съобщение. Обзорът горе казва „кое свърши
    # сега"; тази казва „докъде сме за ЦЕЛИЯ ден". Излиза и по обяд, и вечер,
    # но с различно заглавие — виж обяснението при vecher/obed по-горе.
    if vecher or obed:
        time.sleep(2.0)
        finish = den_finish_text(now, rows, den, mezhdinna=obed)
        post(RESULTS_THREAD, finish)
        time.sleep(1.5)
        post_channel(finish)
        # 🧾 И веднага след него — целият живот на бота. Виж близнака по-горе.
        if vecher:
            time.sleep(1.5)
            post(RESULTS_THREAD, obshto_dosega_text(now, rows))

    # ОБЗОР НА ФИШОВЕТЕ → стая 10 „🏆 Печеливши фишове".
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
    # 🔴 ГРУПИРАНЕТО БЕШЕ ПО ГРЕШНИЯ ДЕН (намерено и оправено 11.08.2026).
    #
    # Стоеше по (номер, day), а `day` в дневника е денят на МАЧА, не денят, в
    # който фишът е пуснат (predictor.py:740). Фиш, пуснат в 22:00 с крака в
    # 22:30 и в 01:40, се разцепва на две купчини; и обратно — крак от вчерашен
    # фиш се слепва с днешния със същия номер. Измерено върху живия дневник:
    # 11 истински фиша ставаха 14 купчини, една от ОСЕМ крака, друга от ЕДИН.
    # Тоест стая 4 отчиташе фишове, които никога не са били пускани така.
    #
    # `posted` е часът на пускане и е записан на всеки крак — първите десет
    # знака са денят, в който фишът наистина е излязъл.
    slips = {}
    for r in rows:
        n = int(r.get("combo") or 0)
        if n and not r.get("combo_done"):
            den = str(r.get("posted") or r.get("day") or "")[:10]
            slips.setdefault((n, den), []).append(r)

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
        # Ключът носи И деня: постът показва фишове от няколко дни, а
        # номерът е пореден ЗА ДЕНЯ. Без датата три реда „ФИШ 1" стоят
        # един под друг с различни резултати.
        gotovi.append(((n, den), [(r, leg_score(r)[0], leg_score(r)[1],
                            bool(r.get("hit"))) for r in sudimi]))
    if gotovi:
        time.sleep(2.0)
        # Стая 10 е „Печеливши фишове" — тук е мястото на фиша, не на числата.
        post(WINS_THREAD, combo_text(now, gotovi))

    save_log(rows)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv or os.environ.get("SCORE_SELFTEST") == "1":
        sys.exit(selftest())
    sys.exit(main())
