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

# 🎾 МАЛКИЯТ ТЕНИС ТУР (19.08.2026). Предсказателят вече пуска и ITF/Challenger
# карти. ESPN не знае, че тези мачове съществуват — значи без този внос всяка
# такава карта виси до изтичане на срока и се затваря без присъда.
# Отделен try: паднал модул НЕ бива да спира отсъждането на другите спортове.
try:
    import itf as ITF
except Exception as _itf_err:                                # noqa: BLE001
    ITF = None
    print("малкият тенис тур не се зареди (" + str(_itf_err)[:70]
          + ") — ITF картите остават неотсъдени.")

# 🏓 ДВЕТЕ МАЛКИ ЛИГИ НА ТЕНИСА НА МАСА (26.08.2026). tt_ligi.py е готов,
# проверен и качен — но досега беше вързан С НИЩО: оценителят пращаше ЦЯЛАТА
# кошница „tabletennis" към wtt_result(). Измерено на живо върху 4 свършили
# чешки мача: WTT връща None и на четирите, а tt_ligi връща истинските сетове.
# Тоест пусне ли собственикът тези лиги, всяка тяхна карта би висяла вечно.
# Отделен try: липсва ли модулът, WTT картите се отсъждат ТОЧНО както преди.
try:
    import tt_ligi as TTL
except Exception as _ttl_err:                                # noqa: BLE001
    TTL = None
    print("лигите тенис на маса не се заредиха (" + str(_ttl_err)[:70]
          + ") — WTT картите се отсъждат както преди.")

NL = chr(10)
SOFIA = ZoneInfo("Europe/Sofia")
UTC = ZoneInfo("UTC")

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
    # 🔴 ДОБАВЕН 18.08.2026. Липсваше. Днес е безобидно — спортът е
    # затворен до септември — но щом се върне, резултатите му щяха да излизат
    # с подразбиращото се 📌 вместо 🏈, защото sport_emo пада на
    # резервата. Намерен чрез сверка на ВСИЧКИ списъци-по-спорт между трите
    # файла: predictor.SPORTS, scorer.SPORT_BG/SPORT_PATH/SPORT_RED, zdrave.IME.
    "amfootball": ("football", "🏈"),   # ESPN път football/nfl
    # 🎮 ДОБАВЕН 02.09.2026. Еспортът пуска карти от 01.09 (11 в
    # живия дневник) и има СВОЯ врата за резултат от същия ден
    # (sport_result -> esport_result), но нямаше нито емоджи, нито име,
    # нито ред. Мерено: sport_emo(«esports») даваше 📌, а
    # sport_ime(«esports») даваше «ESPORTS» — единственият латински надпис
    # сред девет кирилски. Пътят е None, защото ESPN не знае такъв спорт
    # (HTTP 400) — резултатът идва от esport_rez, не оттук.
    # Емоджито е СЪЩОТО като на предсказателя (predictor.py:671), за да не
    # се разминават картата и присъдата.
    "esports": (None, "🎮"),
    # 🏉 ДОБАВЕН 02.09.2026, ЗАЕДНО СЪС САМИЯ СПОРТ, не след него.
    #
    # Ръгбито тръгна днес (ragbi.py: Топ 14, НПС, тестови мачове, 45
    # предстоящи мача). Без този ред картите му щяха да излизат и НИКОГА да
    # не се оценяват — точно правилото, с което НЕ пуснахме КХЛ и клубния
    # волейбол, нарушено от собствената ни ръка.
    # Пътят е „rugby", защото ESPN го знае така, а `slug` в записа е номерът
    # на лигата (270559 = Топ 14). Отборите се сверяват по НОМЕР — затова
    # ragbi.py слага номера, не имена, в home_id/away_id.
    "rugby": ("rugby", "🏉"),
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

# Думи, които НЕ ИЗЛИЗАТ навън.
#
# 🔴 ТУК СТОЕШЕ НАЙ-СКЪПАТА ДУПКА В ПРОЕКТА (намерена 01.09.2026 от оборващ
# агент). Списъкът беше СЕДЕМ думи и НИТО ЕДНО име на букмейкър, а коментарът
# отгоре твърдеше „същият пазач като в другите ботове“. В predictor.py бяха
# петдесет и четири. И точно ОЦЕНИТЕЛЯТ пише в КАНАЛА (post_channel).
#
# Измерено, един и същ низ през двата пазача:
#       „bet365 дава 2.10“     оценител: None    предсказател: bet365
#       „DraftKings“           оценител: None    предсказател: draftkings
#       „Уинбет“               оценител: None    предсказател: уинбет
#       „https://efbet.com“    оценител: None    предсказател: efbet
#
# Лекът не е „препиши списъка“ — това е точно как се роди дефектът. Лекът е
# ЕДИН файл за всички ботове: zabraneni.py. Разминаването вече не е възможно,
# защото няма два списъка.
try:
    import zabraneni as ZB
except Exception:                                            # noqa: BLE001
    ZB = None

# Резервата е нарочно ПЪЛНА, не съкратена: падне ли вносът, пазачът трябва да
# остане пазач, а не да олекне мълчаливо. Мълчаливото олекване е самият дефект.
BANNED = ["18+", "залагай отговорно", "коеф", "букмейкър", "odds",
          "заложи", "финансов съвет",
          "bet365", "pinnacle", "bwin", "efbet", "winbet", "palmsbet",
          "betano", "1xbet", "betfred", "unibet", "sesame", "pickcenter",
          "fanduel", "draftkings", "betmgm", "caesars", "espnbet",
          "sportsbook", "betway", "ladbrokes", "williamhill", "betfair",
          "paddypower", "skybet", "betvictor", "coral", "stoiximan",
          "parimatch", "sportingbet", "888sport", "pokerstars", "superbet",
          "пинакъл", "бет365", "фандуел", "драфткингс", "бетмгм", "бетуей",
          "уилям хил", "бетфеър", "паримач", "ефбет", "уинбет", "палмсбет",
          "бетано", "сезам", "букмекър"]


def banned_word(text):
    if ZB is not None:
        return ZB.banned_word(text)
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
            # 🔴 ПОРЕДЪТ БЕШЕ ОБЪРНАТ (намерено 25.08.2026). Дотук отложеното
            # се проверяваше ПРЕДИ да се види чий е мачът — а таблото връща
            # цялата лига за деня. Един отложен мач затваряше НАШАТА карта
            # като „отложена", макар тя да е играна и решена. Затова първо
            # се пита „наш ли е", и чак после „какво е станало с него".
            got = {}
            for c in (comp.get("competitors") or []):
                tid = str(((c.get("team") or {}).get("id")) or "")
                try:
                    got[tid] = int(str(c.get("score")))
                except Exception:             # noqa: BLE001
                    got[tid] = None           # отложеният няма резултат
            if hid not in got or aid not in got:
                continue                      # чужд мач — не ни засяга
            if espn_otlozhen(st):
                # НАШИЯТ мач е отложен или отменен — резултат НЯМА да има.
                return OTLOZHEN
            if not st.get("completed"):
                continue                      # още не е свършил
            if got[hid] is None or got[aid] is None:
                continue                      # свършил, но без четим резултат
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


def sofia_den(iso):
    """Датата В СОФИЯ на момент, записан по UTC («2026-08-14T22:00:00Z»).

    ЗАЩО СЪЩЕСТВУВА. Календарният ден на един източник НЕ Е нашият ден.
    Измерено на живо на 02.09.2026 срещу statsapi.mlb.com: от 279 намерени
    МЛБ мача 160 започват в София на ден, СЛЕДВАЩ датата, под която ги дава
    schedule?date=, и само 119 — на същата. Тоест « денят на графика » и
    « нашият ден » се разминават в мнозинството от случаите.

    Празен низ при нечетимо. Празното значи « не знам », а не « друг ден » —
    повикващият трябва да падне към старото поведение, не да изхвърли мача.
    """
    s = str(iso or "").strip()
    if not s:
        return ""
    # Z-то не се маха отделно: s[:19] и без това спира преди него, а и преди
    # « +00:00 ». Мутационен тест на 02.09.2026 махна отделния блок и НУЛА
    # проверки паднаха — два реда украса, които нищо не вършат.
    try:
        t = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:                                  # noqa: BLE001
        return ""
    return t.replace(tzinfo=UTC).astimezone(SOFIA).strftime("%Y-%m-%d")


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
                    # 🔴 ТУК ПАДАШЕ ЦЕЛИЯТ ОЦЕНИТЕЛ (намерено 25.08.2026).
                    # Дотук стоеше `return OTLOZHEN` — сентинел, върнат от
                    # функция, обявена да връща СПИСЪК. Извикващият я обхожда:
                    #     for na, nb, pa, pb in tennis_day(day)
                    # → TypeError: 'object' object is not iterable, и рънът
                    # умираше целият. Резултатите спряха за 3 пускания подред
                    # (score #59, #60, #61 — от 23.08 19:44 до 24.08 19:54).
                    #
                    # И ВТОРА, ПО-ТИХА ГРЕШКА в същия ред: таблото за деня
                    # държи ВСИЧКИ мачове. Един отложен сред тях обявяваше за
                    # отложени и всички НАШИ карти за деня, макар да са
                    # играни. Затова отложеният влиза в списъка с ПРАЗЕН
                    # резултат и се познава ПО ИМЕ, като всеки друг.
                    otl = espn_otlozhen(st)
                    if not otl and not st.get("completed"):
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
                    if otl:
                        # Празният резултат Е знакът „отложен". Никой истински
                        # мач не дава None за сетовете.
                        out.append((a[0], b[0], None, None))
                        continue
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
            # Празният резултат значи отложен — и то ТОЗИ мач, не някой друг
            # от таблото. Главният цикъл затваря записа на едно място.
            if same_team(na, ha) and same_team(nb, hb):
                return OTLOZHEN if pa is None else (pa, pb)
            if same_team(na, hb) and same_team(nb, ha):
                return OTLOZHEN if pa is None else (pb, pa)
    return None


# ═══════════════════════ 🎾 ITF И CHALLENGER: РЕЗУЛТАТ ОТ СВОЯ ФИЙД
#
# ЗАЩО ОТДЕЛНО (19.08.2026): tennis_day() пита САМО ESPN atp/wta таблата.
# Мач от M25 Lesa го няма там и никога няма да го има — тоест tennis_result()
# връща None при всяко пускане, а записът виси, докато MAX_AGE (5 дни) не го
# затвори с „hit: None". Карта без път до присъда не е неутрална: тя изяжда
# ред в дневника и НЕ влиза в процента, с който ботът се отчита.
#
# ЦЕНАТА В ЗАЯВКИ: itf.rezultat() чете ДНЕВНИЯ фийд, не мача — един ден носи
# всички резултати наведнъж и се кешира. Тоест 100 висящи ITF карти струват
# толкова, колкото една.
#
# ЗАЩО ПОБЕДИТЕЛЯТ НЕ СЕ ЧЕТЕ ОТ СЕТОВЕТЕ: при отказал се играч сетовете
# могат да са 1:1, а при служебна победа изобщо няма сетове. Измерено от
# itf.py върху 211 вчерашни мача: по сетовете 5 се отсъждат ГРЕШНО и още 1
# остава без победител; по полето „кой спечели" — 205 от 211, а шестте
# неотсъдени са ОТМЕНЕНИ мачове, където победител наистина няма.
def itf_result(rec):
    """(1,0) или (0,1) за ITF/Challenger. None = още не знаем.

    Връща спечелени МАЧОВЕ, не сетове — единица за победителя. Това стига:
    verdict() чете само кой от двамата има повече, а сетовете при отказал се
    лъжат (виж по-горе).
    """
    if ITF is None:
        return None
    mid = str(rec.get("itf_id") or "")
    if not mid:
        return None
    try:
        r = ITF.rezultat({"id": mid})
    except Exception:                                        # noqa: BLE001
        return None
    if not r.get("gotov"):
        return None                       # още тече или още не е в фийда
    pob = r.get("pobeditel")
    if pob in (1, 2):
        return (1, 0) if pob == 1 else (0, 1)
    # 🔴 ОТМЕНЕНИЯТ МАЧ ПОЛЗВА ЧУЖДИЯ СЕНТИНЕЛ, А НЕ СВОЙ ПЪТ.
    # Фийдът го е обявил за приключил, но победител НЯМА и няма да има.
    # Първо го написах да пипа сам записа (scored/hit/why) — после видях, че
    # в същия файл вече има точно този механизъм за отложените мачове от
    # ESPN. Два начина да се затвори един запис значат два начина да се
    # сгреши. Тук се връща СЪЩИЯТ сентинел и главният цикъл го затваря на
    # едно-единствено място. Измерено от itf.py: 6 от 211 вчерашни мача.
    return OTLOZHEN


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
                                 ht.get("name") or "", at.get("name") or "",
                                 sofia_den(g.get("gameDate"))))
                except Exception:                      # noqa: BLE001
                    continue
    except Exception as e:                             # noqa: BLE001
        print("    MLB мълчи за " + str(day) + " (" + str(e)[:50] + ")")
    _mlb_days[day] = rows
    return rows


def azia_result(rec):
    """(точки_дом, точки_гост) за NPB/KBO, или None, ако още не знаем.

    🔴 ЗАЩО НЕ МИНАВА ПРЕЗ baseball_result: там се пита statsapi sportId=1.
    Измерено 25.08.2026: sportId=31 (NPB) и 32 (KBO) връщат HTTP 200 с
    totalGames=0 дори за минали дни — регистрация на лига има, съдържание
    няма. ESPN baseball/npb и /kbo дават HTTP 400, докато baseball/mlb в
    същия миг дава 200 с 10 събития. Тоест друг източник НЯМА.

    🔴 ДВЕТЕ ИМЕНА СЕ ИСКАТ ЕДНОВРЕМЕННО. azia.istoriya() съпоставя по
    ПОДНИЗ и сама по себе си може да лепне чужд отбор — точно грешката,
    която вече ни ухапа („Atlanta United FC" хващаше „Bury FC"). Затова тук
    се иска И домакинът, И гостът да съвпаднат, И денят.

    ЗАЯВКИ: до 2 (по една за календарния месец на NPB и на KBO), кеширани в
    azia. Вторият отсъден мач от същия месец струва нула.

    МЪЛЧАНИЕТО НЕ Е НУЛА: върне ли None, картата остава неотсъдена — точно
    както преди кръпката. Никога не се връща измислен резултат.
    """
    try:
        import azia
    except Exception as e:                             # noqa: BLE001
        print("    азиатският бейзбол не се зареди (" + str(e)[:50] + ")")
        return None
    ha, hb = rec.get("home"), rec.get("away")
    if not ha or not hb:
        return None
    for day in okolni_dni(rec.get("day")):
        try:
            kogato = datetime.strptime(day, "%Y-%m-%d")
        except Exception:                              # noqa: BLE001
            continue
        try:
            redove = azia.istoriya(ha, kogato, 60)
        except Exception as e:                         # noqa: BLE001
            print("    азия/резултат: " + str(e)[:60])
            return None
        for r in redove:
            if str(r.get("start") or "")[:10] != day:
                continue
            # И ДВАТА отбора, инак подниз-съвпадение лепи чужд мач.
            if not same_team(r.get("protivnik"), hb):
                continue
            za, protiv = r.get("za"), r.get("protiv")
            if za is None or protiv is None:
                continue
            return (za, protiv) if r.get("u_doma") else (protiv, za)
    return None


def baseball_result(rec):
    """(точки дом, точки гост) за МЛБ, или None.

    🔴 ПОПРАВЕНО 02.09.2026 — ПРОЗОРЕЦЪТ ЛЕПЕШЕ МАЧ ОТ СЪЩАТА СЕРИЯ.

    МЯРКАТА, не спомен. Изтеглих живия predict_log.json (1208 записа) и
    сверих всеки отсъден МЛБ запис срещу statsapi.mlb.com:
      · 120 отсъдени МЛБ записа
      · 12 от тях носят резултата на СЪСЕДЕН мач (8 от вчера, 4 от утре)
      · засегнати 16 реда в дневника, от които 4 ПРИСЪДИ СА ОБЪРНАТИ
        (3 фалшиви познавания и 1 незаписано познаване)
    Двойките са проверени поименно: Къбс–Кардиналс на 15.08 е 4:8, а в лога
    стои 3:0 — резултатът от 14.08. Бруърс–Брейвс на 22.08 е 4:1, в лога
    стои 2:1 — от 21.08. В МЛБ същите два отбора играят серия по три дни
    поред, затова ±1 ден намира « същия сблъсък » и на съседния ден.

    ЗАЩО ПРОЗОРЕЦЪТ НЕ СЕ МАХА. schedule?date=D връща и мачове, които в
    София започват на D+1 — нощните. Измерено: 160 такива срещу 119 дневни.
    Махне ли се ден-1, нощните мачове изчезват изцяло.

    ЦЕНАТА НА СТЯГАНЕТО Е НУЛА, И ТЯ Е ИЗМЕРЕНА. И 120-те отсъдени МЛБ
    записа имат ЗАВЪРШЕН мач, чието начало по софийско време пада точно на
    техния ден. Тоест филтърът по софийска дата не оставя неотсъден нито
    един легитимен мач — печели 12, губи 0.

    Празна софийска дата (стар кеш, липсващ gameDate) НЕ отхвърля мача:
    « не знам » не е « друг ден ».
    """
    hid, aid = str(rec.get("home_id") or ""), str(rec.get("away_id") or "")
    ha, hb = rec.get("home"), rec.get("away")
    nash = str(rec.get("day") or "")
    for day in okolni_dni(rec.get("day")):
        for h, a, hs, as_, hn, an, sof in mlb_day(day):
            if sof and nash and sof != nash:
                continue                   # чужд ден по СОФИЙСКО време
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


def tt_liga_klyuch(rec):
    """Ключът на нашата лига за този запис, или None, ако не е наша.

    🔴 РАЗПОЗНАВАНЕТО Е ПО ЛИГАТА, НЕ ПО КОША. Кошницата „tabletennis" носи
    и WTT, и двете малки лиги — кошът не ги различава. Дневникът пише лигата
    така, както я е дал източникът, а източниците лепят подзаглавие след
    средната точка („WTT Feeder Olomouc 2026 · Men's Singles"). Затова се
    пробва целият низ И всяко парче поотделно, но се приема САМО ако самият
    tt_ligi я признае за своя. Нито едно WTT име не съдържа „Czech Liga Pro"
    или „TT Elite Series", тоест по-широкото търсене не може да открадне
    WTT мач — а обратното вече ни е ухапвало (фамилията лепеше чужда цена).
    """
    if TTL is None:
        return None
    s = str(rec.get("league") or "")
    if not s.strip():
        return None
    for p in [s] + s.split("·"):
        p = p.strip()
        if not p:
            continue
        try:
            lk = TTL.liga_klyuch(p)
        except Exception:                                    # noqa: BLE001
            return None
        if lk:
            return lk
    return None


def _tt_liga_forma(r):
    """Само двойка разумни цели числа минава оттук. Всичко друго -> None.

    🔴 ЧУЖДИЯТ МОДУЛ НЕ Е ДОВЕРЕН СЪДИЯ. tt_ligi има ТРИ свои сентинела
    (ZAPUSHENO, OTLOZHEN, POBEDITEL_BEZ_SETOVE) и едно доказано сляпо петно:
    при паднал адрес _nameri_sabitie връща чуканче с name=None ВМЕСТО
    ZAPUSHENO. Сентинелите му при това са ЛЪЖЛИВО ИСТИННИ (__bool__ = True),
    тоест `if not r` не ги хваща, а `hs, as_ = r` в главния цикъл би гръмнало
    и би спряло отсъждането на ВСИЧКИ спортове, не само на този.
    Границите са наши, не преписани: сет-резултат няма равен изход, победи-
    телят има 2, 3 или 4 сета, а сборът не минава 7.
    """
    if isinstance(r, bool) or not isinstance(r, (tuple, list)) or len(r) != 2:
        return None
    hs, as_ = r
    if isinstance(hs, bool) or isinstance(as_, bool):
        return None
    if not isinstance(hs, int) or not isinstance(as_, int):
        return None
    if hs < 0 or as_ < 0 or hs == as_:
        return None
    if max(hs, as_) < 2 or max(hs, as_) > 4 or (hs + as_) > 7:
        return None
    return (hs, as_)


def tt_liga_result(rec):
    """Резултатът за Czech Liga Pro / TT Elite Series. None = още не знаем.

    🔴 ОГЛЕДАЛНАТА СВЕРКА — И СТРУВА НУЛА ЗАЯВКИ.
    Сляпото петно на tt_ligi има втора половина: чуканчето носи name=None,
    а точно името е това, по което се поправя обърнатият запис (Smarkets
    пише страните в свой ред). Тоест при паднал адрес запис с разменени
    страни получава ОГЛЕДАЛНАТА присъда — а тя не гърми, само лъже.

    Затова питаме съдията ДВА ПЪТИ: веднъж както е записано и веднъж с
    разменени страни. Ключът на двойката в tt_ligi е неподреден набор
    (frozenset), значи и двата въпроса стигат до СЪЩОТО събитие и до
    същите адреси — а те са в кеша от първия въпрос, тоест втората заявка
    е нула. Ако съдията вижда името, вторият отговор е точното огледало на
    първия. Ако е сляп, ще върне ЕДНО И СЪЩО и за двете посоки — и тогава
    тук се връща None. None не е нито „познах", нито „сгреших": главният
    цикъл го подминава и пита пак утре.
    """
    if TTL is None:
        return None
    lk = tt_liga_klyuch(rec)
    if lk is None:
        return None                          # не е наша лига — не е наш мач
    # 🔴 ЛИГАТА СЕ ПОДАВА ИЗЧИСТЕНА. tt_ligi познава своята лига само по
    # ЦЯЛОТО име, а дневникът лепи подзаглавие след средната точка
    # („Czech Liga Pro · Men"). Измерено с хартиената мрежа: СЪС суфикса
    # rezultat() връща None, БЕЗ него — (1, 3). Тоест по-широкото
    # разпознаване без това привеждане само би пращало картата в стена:
    # оценителят я взима от WTT и после мълчи. Първата ми версия правеше
    # точно това и проверката я почерви.
    try:
        _ime_lg = TTL.LIGI[lk]["ime"]
    except Exception:                                        # noqa: BLE001
        _ime_lg = rec.get("league")
    rec = dict(rec, league=_ime_lg)
    try:
        r = TTL.rezultat(rec)
    except Exception as e:                                   # noqa: BLE001
        print("    лигите тенис на маса: " + str(e)[:60])
        return None
    # 🔴 ПЪРВО None, ЧАК ПОСЛЕ СЕНТИНЕЛЪТ. Обратният ред е капан: липсва ли
    # TTL.OTLOZHEN, getattr връща None и „r is None" би минало за отменен мач.
    if r is None:
        return None
    _otl = getattr(TTL, "OTLOZHEN", None)
    if _otl is not None and r is _otl:
        return OTLOZHEN
    prav = _tt_liga_forma(r)
    if prav is None:
        return None
    dom, gost = rec.get("home"), rec.get("away")
    if not dom or not gost:
        return None                          # без двете имена няма сверка
    try:
        r2 = TTL.rezultat(dict(rec, home=gost, away=dom))
    except Exception as e:                                   # noqa: BLE001
        print("    лигите тенис на маса (сверка): " + str(e)[:60])
        return None
    obrat = _tt_liga_forma(r2)
    if obrat is None or obrat != (prav[1], prav[0]):
        return None
    return prav


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
    # 🔴 ЧУЖДА ФОРМА НЕ СЪБАРЯ РЪНА (26.08.2026).
    #
    # Викаме се направо с j.get("events") и j.get("results") от мрежата.
    # TheSportsDB отговаря с НИЗ при невалиден идентификатор — при проба
    # с абревиатура „NYR" върна „Invalid Team ID passed". Тогава
    # `for e in "Invalid..."` обхожда БУКВИ и `"I".get(...)` гърми с
    # AttributeError, който убива ЦЕЛИЯ рън на оценителя.
    #
    # Същият клас дефект спря бота за 48 часа на 23-25.08: сентинел,
    # обхождан с разпакетиране. Цената не е едно пропуснато питане, а
    # цял ден без резултати.
    #
    # Пропускаме записа, вместо да гърмим. Глътваме ФОРМА, не изключение —
    # провал от мрежата си остава видим на нивото над нас.
    if not isinstance(sabitiya, (list, tuple)):
        sabitiya = []
    for e in sabitiya:
        if not isinstance(e, dict):
            continue
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


# ═══════════════════════════════════════════════════ 🥊 БОЙНИ СПОРТОВЕ
#
# 🔴 ДОБАВЕНО 12.08.2026 — ММА ПУСКАШЕ КАРТИ, КОИТО НЕ МОЖЕХА ДА БЪДАТ
# ОТСЪДЕНИ НИКОГА.
#
# Измерено в живия дневник: пет записа, НУЛА отсъдени, нула със slug.
# `SDB_SPORT` няма „mma" → резервната врата пада на първия ред; `espn_result`
# иска slug, а ММА-записът няма. И спортът НЕ беше в NO_RESULT, тоест го
# чакахме за нищо: прогнозите висяха, докато срокът ги затвори без присъда.
# Точно дупката, която затворихме за тениса на маса — само че тук никой не я
# беше видял, защото ММА дава карти един ден от петнайсет.
#
# А източникът е СЪЩИЯТ, от който идват и боевете: ESPN. Проверено на живо:
#   /mma/ufc/scoreboard?dates=20260811 → 5 боя, 5 завършили,
#   Joe Kropschot(4687604, winner=True) vs Jon Kunneman(5282317, winner=False)
# — дума по дума записът от дневника, с неговите home_id и away_id.
#
# ЗАЩО СЕ ПИТАТ ТРИ ДАТИ: галите са късна вечер в САЩ, тоест рано сутрин по
# българско. Мач, записан при нас за 12.08, при ESPN стои на 11.08.
# 🔴 РАЗШИРЕНО 13.08.2026 — СЕДЕМТЕ ЛИГИ, СЪЩИТЕ КАТО В ПРЕДСКАЗАТЕЛЯ.
#
# Ако тук стоят по-малко лиги, отколкото предсказателят пуска, боевете от
# липсващите се отсъждат НИКОГА — точно дупката, която затворихме вчера, само
# че отворена наново отстрани. Затова списъкът е един и същ и самопроверката
# го сверява срещу predictor.py, вместо да се надява.
MMA_LIGI = ("ufc", "pfl", "bellator", "rizin", "ksw", "lfa", "cage-warriors")
_mma_kesh = {}


# 🔴 ОТЛОЖЕН МАЧ НЕ Е „ЧАКАЩ РЕЗУЛТАТ" (19.08.2026).
#
# Намерено с четене на живия дневник: „Braga — Gil Vicente" от 16.08 висеше
# ТРЕТИ ДЕН в „чакат резултат". Мачът е STATUS_POSTPONED — резултат няма и
# няма да има. Оценителят обаче гледаше САМО полето `completed` и затова го
# питаше слепешком всеки ден, докато възрастовата граница го затвори.
#
# Два разхода от това: излишни заявки, и — по-лошо — числото „чакат резултат"
# в дневната равносметка лъже читателя, че нещо предстои.
#
# Затова: отложеното и отмененото се разпознават и картата се затваря ЧЕСТНО,
# без присъда. Мач, който не се е състоял, не е нито познат, нито сгрешен.
OTLOZHENI = ("postponed", "canceled", "cancelled", "suspended", "forfeit",
             "abandoned")
# Сентинел, а не гол низ: „ОТЛОЖЕН" като текст може случайно да се сравни с
# нещо друго, обект — не може. Същата поука като с _NEPODADEN в будилника.
OTLOZHEN = object()


def espn_otlozhen(st):
    """Отложен/отменен ли е мачът според ESPN. st е status.type."""
    if not isinstance(st, dict):
        return False
    t = (str(st.get("name") or "") + " " + str(st.get("state") or "")
         + " " + str(st.get("description") or "")).lower()
    return any(d in t for d in OTLOZHENI)


def _mma_gala(liga, ymd):
    """Боевете от една гала. Кеширано по (лига, дата) — не питаме два пъти."""
    kl = (liga, ymd)
    if kl in _mma_kesh:
        return _mma_kesh[kl]
    j = http_json(ESPN + "/mma/" + liga + "/scoreboard?dates=" + ymd)
    idx = {}
    if isinstance(j, dict):
        for ev in (j.get("events") or []):
            for comp in (ev.get("competitions") or []):
                st = ((comp.get("status") or {}).get("type") or {})
                if not st.get("completed"):
                    continue
                cs = comp.get("competitors") or []
                if len(cs) != 2:
                    continue
                ids = [str(c.get("id") or "") for c in cs]
                if not all(ids):
                    continue
                # Кой е победил. ESPN дава winner=True на единия; ако и двамата
                # са False (равен/отменен), не отсъждаме — по-добре мълчание,
                # отколкото измислена присъда.
                pob = [i for i, c in enumerate(cs) if c.get("winner") is True]
                if len(pob) != 1:
                    continue
                idx[frozenset(ids)] = (ids[pob[0]], ids)
    _mma_kesh[kl] = idx
    return idx


def mma_result(rec):
    """(точки_домакин, точки_гост) за бой. 1:0 или 0:1 — няма резултат в бокса.

    Връща None при незавършил бой, равен, отменен или ненамерен.
    """
    dom, gost = str(rec.get("home_id") or ""), str(rec.get("away_id") or "")
    if not dom or not gost:
        return None
    den = str(rec.get("day") or "")[:10]
    if len(den) != 10:
        return None
    try:
        d0 = datetime.strptime(den, "%Y-%m-%d")
    except ValueError:
        return None
    klyuch = frozenset((dom, gost))
    for otместване in (0, -1, 1):
        ymd = (d0 + timedelta(days=otместване)).strftime("%Y%m%d")
        for liga in MMA_LIGI:
            idx = _mma_gala(liga, ymd)
            if klyuch in idx:
                pobeditel, _ = idx[klyuch]
                return (1, 0) if pobeditel == dom else (0, 1)
    return None


def esport_result(rec):
    """(точки_дом, точки_гост) за електронните спортове, или None.

    1:0 или 0:1 — при CS2/LoL/Dota 2 картата е чиста победа, както при ММА.

    🔴 ЗАЩО НЕ МИНАВА ПРЕЗ PINNACLE. Цената идва оттам, резултатът — не:
    /matchups/{id}/settlements, /results и /score дават 404, а
    /settlements?sportId=12 дава 204 с празно тяло (и за футбола 29 също,
    тоест не е защото няма мачове). Освен това Pinnacle ИЗХВЪРЛЯ мача от
    витрината, щом свърши. Затова изворът е ДРУГ: Smarkets — борса, където
    победителят не е новина, а сетълмънт, по който са платени пари.

    Измерено на 01.09.2026: 41 техни завършили мача на 31.08, 40 с обявен
    победител (41-вият е отменен). Сверено срещу втори независим извор
    (op.gg): 91 мача по LoL, 91 съгласни, 0 несъгласни.

    ЗАЯВКИ: 1–3 за списъка на деня (кешира се по игра и ден) + 2 за самия
    мач. Вторият отсъден мач от същия ден струва две заявки.

    🔴 ПОКРИТИЕТО НЕ Е ЕДНАКВО ПО ИГРИ (31 живи среща, 01.09.2026):
    CS2 15 от 16, Dota 2 1 от 1, League of Legends 5 от 15 (само големите
    лиги), Valorant 0 — Smarkets НЯМА такъв тип събитие. Затова стойността
    PREDICT_ESPORT_IGRI="cs2" е честната първа стъпка: карта, за която няма
    път до присъда, виси вечно и трови процента на целия спорт (същият урок
    като с ITF при тениса).

    МЪЛЧАНИЕТО НЕ Е НУЛА: None значи „не можах да отсъдя", картата остава
    неотсъдена — точно както преди кръпката. Измислен изход не се връща.
    """
    try:
        import esport_rez
    except Exception as e:                             # noqa: BLE001
        print("    еспорт/резултат не се зареди (" + str(e)[:50] + ")")
        return None
    dom, gost = rec.get("home"), rec.get("away")
    if not dom or not gost:
        return None
    # Играта се пише в дневника от log_pick. Липсва ли (стар запис), тя се
    # чете от името на лигата — предсказателят го сглобява като
    # „CS2 · BLAST Open Porto". Не се ГАДАЕ: няма ли и там, се мълчи.
    igra = str(rec.get("igra") or "")
    if not igra:
        glava = str(rec.get("league") or "").split("·")[0].strip().lower()
        igra = {"cs2": "cs2", "counter-strike 2": "cs2",
                "league of legends": "lol", "dota 2": "dota2"}.get(glava, "")
    if not igra:
        return None
    for day in okolni_dni(rec.get("day")):
        try:
            r = esport_rez.rezultat(dom, gost, day, igra)
        except Exception as e:                         # noqa: BLE001
            print("    еспорт/резултат: " + str(e)[:60])
            return None
        if r is not None:
            return r
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
        # 🔴 ЕДНА КОШНИЦА, ДВА ИЗТОЧНИКА (19.08.2026). ATP/WTA идват от ESPN,
        # ITF/Challenger — от своя фийд. Разпознават се по `src`; `itf_id` е
        # втората врата, защото един от двата белега стига, а и двата се
        # пишат от едно и също място в predictor.log_pick.
        # Старите тенис записи нямат нито едно от двете и си минават по
        # стария път — тоест вграждането не пипа нищо, което вече работи.
        if str(rec.get("src") or "") == "itf" or rec.get("itf_id"):
            return itf_result(rec)
        return tennis_result(rec)
    if b == "baseball":
        # 🔴 ЕДНА КОШНИЦА, ДВА ИЗТОЧНИКА — както при тениса. МЛБ идва от
        # statsapi, NPB/KBO от azia.py. Разпознават се по `src`, който
        # predictor.log_pick вече записва. Старите бейзболни записи нямат
        # src="azia" и си минават по стария път непокътнати.
        if str(rec.get("src") or "") == "azia":
            return azia_result(rec)
        return baseball_result(rec)
    if b == "tabletennis":
        # 🔴 ЕДНА КОШНИЦА, ДВА ИЗТОЧНИКА — както при тениса и бейзбола.
        # WTT си остава при wtt_result; Czech Liga Pro и TT Elite Series ги
        # знае САМО tt_ligi. Разпознава се по ЛИГАТА на записа, не по коша:
        # кошът е един за трите. Липсва ли модулът, tt_liga_klyuch връща
        # None и всичко минава по стария път — доказано с проверка.
        if tt_liga_klyuch(rec):
            return tt_liga_result(rec)
        return wtt_result(rec)
    if b == "mma":
        return mma_result(rec)
    if b == "esports":
        # 🎮 СОБСТВЕНА ВРАТА (01.09.2026). Дотук всяка еспорт карта падаше в
        # espn_result(), а ESPN не знае такъв спорт: sport 'esports' е
        # „invalid" (HTTP 400, мерено). Тоест присъда нямаше как да излезе.
        return esport_result(rec)
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


def total_line(pick):
    """Линията от избор „Над 2.5 гола" / „Под 8.5 рънове". None = не е тотал.

    Приема САМО линия на половинка. Цяло число (Над 8) би значело, че сборът
    може да падне ТОЧНО на линията, а тогава изходът не е нито да, нито не —
    и присъдата би била измислена. Предсказателят и без това пуска само
    половинки, но проверката стои тук, защото тук се произнася присъдата.
    """
    s = str(pick or "").strip()
    low = s.lower()
    if not (low.startswith("над ") or low.startswith("под ")):
        return None
    parche = s.split()[1] if len(s.split()) > 1 else ""
    try:
        ln = float(parche.replace(",", "."))
    except (TypeError, ValueError):
        return None
    if abs(ln - int(ln)) < 0.4:
        return None                  # цяла линия — не се отсъжда
    return ln


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

    # 🔴 ТОТАЛЪТ СЕ ОТСЪЖДА ПО СБОРА (19.08.2026). От днес един мач може да
    # даде ВТОРА карта — над/под линията на пазара. Без този клон тя падаше в
    # пътя по имена, там не намираше нито домакин, нито гост, и се връщаше
    # None: картата излиза в стаята, а статистиката не я вижда НИКОГА.
    # Линията е винаги на половинка (виж pinnacle.polovinka), затова равен
    # изход няма — сборът е или над нея, или под нея.
    ln = total_line(pick)
    if ln is not None:
        try:
            sbor = float(hs) + float(as_)
        except (TypeError, ValueError):
            return None
        return sbor > ln if pick.strip().lower().startswith("над") else sbor < ln

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
def mn(n, edn, mno):
    """Думата СЛЕД числото: единствено при точно 1, множествено иначе.

    ЕДНО МЯСТО ЗА ЦЕЛИЯ ФАЙЛ (26.08.2026). Дотук всяко съобщение си пишеше
    собствен клон „if x == 1“ — и точно затова половината ги нямаха.
    Финишът печаташе „От 1 пуснати днес 1 имат резултат.“, а редът точно
    под него („⏳ 1 чака мача си“) беше верен. Двата реда са писани от един
    и същи човек в един и същи ден; разликата е само дали се е сетил.

    НУЛАТА Е МНОЖЕСТВЕНО на български: „0 карти“, не „0 карта“. Затова
    сравнението е с 1, а не „по-голямо от 1“.

    Не-число НЕ гърми — държи се като множествено. Крива дума е по-евтина
    от паднало съобщение: това се вика в градежа на текст, който тръгва към
    Telegram, и изключение тук би изяло ЦЯЛАТА равносметка.
    """
    try:
        edno = (int(n) == 1)
    except (TypeError, ValueError):
        edno = False
    return edn if edno else mno


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def date_bg(d):
    dni = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]
    return dni[d.weekday()] + ", " + d.strftime("%d.%m")


DNI_KRATKI = ["пн", "вт", "ср", "чт", "пт", "сб", "нд"]


def den_dumi(den):
    """„2026-08-23" -> „нд 23.08". Празно или чудато влиза както е, без да гърми.

    Кратък ден, защото заглавието трябва да се хване с един поглед, а
    „неделя, 23.08" изяжда една трета от първия ред на телефона.
    """
    s = str(den or "")
    try:
        d = datetime.strptime(s[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return den_kratko(s)
    return DNI_KRATKI[d.weekday()] + " " + d.strftime("%d.%m")


def chas_bg(now):
    """„нд 23.08, 22:30" — денят И ЧАСЪТ на това пускане.

    🔴 ДЕФЕКТ A (25.08.2026). Обзорът излиза два пъти на ден, с РАЗЛИЧНИ мачове
    вътре, а заглавието му беше „ОБЗОР НА ДЕНЯ · неделя, 23.08" и в двата
    случая. Човек вижда две съобщения с едно заглавие и различни числа и решава,
    че ботът се повтаря или брои двойно.

    Проверих сметката, преди да пипна текста: главата на обзора се смята от
    `grupi`, тоест от подадените `fresh` — отсъдените В ТОВА ПУСКАНЕ. Числото
    ВИНАГИ е било за пускането. Лъжеше надписът „НА ДЕНЯ", не сметката. Затова
    сметката остава недокосната, а заглавието спира да обещава ден и започва да
    казва кое пускане е. Часовникът е един за целия канал — софийски.
    """
    return DNI_KRATKI[now.weekday()] + " " + now.strftime("%d.%m, %H:%M")


def line(rec, hs, as_, ok):
    emo = (SPORT_PATH.get(rec.get("bucket")) or (None, "\U0001f4cc"))[1]
    mark = "✅" if ok else "❌"
    return (mark + " " + emo + " <b>" + esc(rec.get("home")) + "</b> " + str(hs)
            + ":" + str(as_) + " <b>" + esc(rec.get("away")) + "</b>" + NL
            + "    посочихме: " + esc(rec.get("pick")))


# Под този брой CLV е шум, не сигнал. Двайсет е долната граница, при която
# средното движение изобщо започва да значи нещо.
CLV_MIN = max(10, min(200, int((os.environ.get("SCORE_CLV_MIN") or "20").strip() or 20)))
# Доходността е по-шумна от CLV: тя зависи и от резултатите, не само от
# движението на цената. Затова прагът ѝ е по-висок.
DOHOD_MIN = max(20, min(500, int((os.environ.get("SCORE_DOHOD_MIN") or "40").strip() or 40)))


def bez_red(n, ime=""):
    """ЕДИН ред за прогнозите, които никой източник не може да отсъди.

    🔴 ДЕФЕКТ C (25.08.2026). Дотук пишеше „🏓 тенис на маса: 2 без официален
    резултат" — по един ред на спорт, на канцеларски език, и не казваше НИЩО
    за това какво прави тази бройка с процента отгоре. Читателят го чете и не
    знае броим ли ги за загубени, или не ги броим.

    Сега редът носи и причината, и последицата, и е ЕДИН — тук, за да е
    еднакъв и в обзора, и във финиша, и в равносметката. Смени ли се тук,
    сменя се и на трите места; няма как две съобщения да обясняват едно и
    също нещо с различни думи.
    """
    n = int(n or 0)
    if n <= 0:
        return []
    # ДВА КЪСИ РЕДА, НЕ ЕДИН ДЪЛЪГ. С името на спорта единият ред става 75
    # знака и телефонът го пренася на три; така са два по 38 и не се пренасят.
    return ["\U0001f6ab " + str(n) + mn(n, " мач", " мача")
            + ((" на " + ime) if ime else "") + " без резултат",
            "   източникът не " + mn(n, "го", "ги") + " дава — не "
            + mn(n, "го", "ги") + " броим"]


def bez_text(bez):
    """Редът за неотсъдимите по спорт -> ЕДИН ред общо.

    Спортът се назовава само когато е ЕДИН. При няколко изброяването връща
    същите шест реда, от които бягаме — а сборът казва същото.
    """
    if not bez:
        return []
    obshto = sum(int(n or 0) for n in bez.values())
    ime = ""
    if len(bez) == 1:
        b = list(bez)[0]
        ime = {"tabletennis": "тенис на маса"}.get(b, sport_ime(b).lower())
    return bez_red(obshto, ime)


# Име на спорта на български + реда, в който се показва. Редът е по значение
# за канала, не по азбука — футболът и баскетболът водят.
SPORT_BG = {
    "football": "ФУТБОЛ", "basketball": "БАСКЕТБОЛ", "volleyball": "ВОЛЕЙБОЛ",
    "tennis": "ТЕНИС", "tabletennis": "ТЕНИС НА МАСА", "hockey": "ХОКЕЙ",
    "baseball": "БЕЙЗБОЛ", "amfootball": "АМЕРИКАНСКИ ФУТБОЛ", "mma": "БОЙНИ",
    # Дословно заглавието на стаята при предсказателя (predictor.py:671:
    # «Електронни спортове»), за да чете човек едно и също име в двете
    # съобщения. Показва се през .capitalize().
    "esports": "ЕЛЕКТРОННИ СПОРТОВЕ",
    "rugby": "РЪГБИ",
}
SPORT_RED = ["football", "basketball", "volleyball", "tennis", "hockey",
             "baseball", "amfootball", "tabletennis", "mma", "esports",
             "rugby"]


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
    """Един мач с ЕДИН избор — на ЕДИН ред.

    Дотук бяха два реда: мачът, а под него изборът с шест интервала отстъп.
    При четиринайсет мача това са двайсет и осем реда за нещо, което се чете
    наведнъж.
    """
    return (("✅" if ok else "❌") + " <b>" + esc(rec.get("home")) + "</b> "
            + str(hs) + ":" + str(as_) + " <b>" + esc(rec.get("away")) + "</b>"
            + " · " + esc(rec.get("pick")))


def broy_machove(redove):
    """Колко РАЗЛИЧНИ мача има в списъка — не колко прогнози.

    Един мач с два пазара е ЕДИН мач. Нужен е, за да знае обзорът колко
    остават извън тавана, без да брои редове.
    """
    vidyani = set()
    for rec, hs, as_, _ok in (redove or []):
        vidyani.add((str(rec.get("home") or "").strip().lower(),
                     str(rec.get("away") or "").strip().lower(),
                     str(hs), str(as_)))
    return len(vidyani)


def mach_redove(redove, maks=None):
    """Списъкът мачове: ЕДИН МАЧ — ЕДИН БЛОК, колкото и пазара да имаме.

    🔴 `maks` РЕЖЕ ПО МАЧОВЕ, НЕ ПО РЕДОВЕ (25.08.2026). Мач с два пазара
    заема два реда; рязане по редове би оставило мач наполовина — с име
    отгоре и без изборите отдолу. Затова таванът брои блокове.

    🔴 ДЕФЕКТ B (25.08.2026). Пазачът срещу дубликати в обзора (виж
    results_text) държи ИЗБОРА в ключа си — и с право: без него вторият пазар
    изчезваше и от списъка, и от числото, тоест пазач срещу повторение
    произвеждаше изчезване. Но следствието се четеше в стаята така:

        Nashville SC 3:2 Columbus Crew
           1 · победа Nashville SC
        Nashville SC 3:2 Columbus Crew
           Над 2.5 гола

    Един мач, изписан целият два пъти. Сметката е вярна, показването не е.
    Затова тук — и САМО тук, в показването — редовете се сливат по МАЧ:
    еднакви домакин, гост и резултат отиват в един блок, а изборите се нижат
    под него. Числото отгоре не се пипа: то продължава да брои ПРОГНОЗИ,
    защото прогнозата е това, което сме казали, и всяка си има своя присъда.

    Редът е този, в който са дошли. Не подреждам познатите отпред: при пет
    мача това не пести нищо, а бот, който сам подрежда собствените си
    резултати с доброто нагоре, прави витрина, не обзор.
    """
    poredno, po_mach = [], {}
    for rec, hs, as_, ok in redove:
        kl = (str(rec.get("home") or "").strip().lower(),
              str(rec.get("away") or "").strip().lower(), str(hs), str(as_))
        if kl not in po_mach:
            po_mach[kl] = []
            poredno.append(kl)
        po_mach[kl].append((rec, hs, as_, ok))
    if maks is not None and maks >= 0:
        poredno = poredno[:maks]
    out = []
    for kl in poredno:
        grupa = po_mach[kl]
        if len(grupa) == 1:
            out.append(kratak_red(*grupa[0]))
            continue
        rec, hs, as_, _ = grupa[0]
        out.append("<b>" + esc(rec.get("home")) + "</b> " + str(hs) + ":"
                   + str(as_) + " <b>" + esc(rec.get("away")) + "</b>")
        out.append("   " + " · ".join(
            (("✅" if ok else "❌") + " " + esc(r.get("pick")))
            for r, _h, _a, ok in grupa))
    return out


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


# Колко мача обзорът изрежда. Над този брой излишните се БРОЯТ, не се крият.
#
# 🔴 Собственикът, 25.08.2026, дословно: „РАЗБОРА НА ДЕНЯ ДАВАШ И ВСИЧКИТЕ
# МАЧОВЕ В СЪОБЩЕНИЕТО — ТОВА Е УЖАСНО НЕ ГО ПРАВИ — ХУБАВО ГОТИНО СТЕГНАТО
# ОБЗОРЧЕ В ЧАСОВЕТЕ КОИТО СЪМ ТИ КАЗАЛ."
#
# Измерено на този файл ПРЕДИ промяната, с 39 отсъдени мача от пет спорта:
# обзорът е 109 реда и 4046 знака по сметката на Telegram. Таванът е 4096 —
# бяхме на петдесет знака от това съобщението да не излезе ИЗОБЩО.
#
# Границата е ТВЪРДА и е двоична нарочно: или всички мачове от пускането, или
# нито един. Всяко „покажи най-добрите пет" е избор, а избор, направен от бота
# върху собствените му резултати, е витрина. Пускане с три отсъдени мача не е
# това, от което собственикът се оплака — то си е обзорче.
# 🔴 БЕШЕ 5 И ЗАРАДИ ТОВА СПИСЪКЪТ ИЗЧЕЗНА СЪВСЕМ (върнато 25.08.2026).
# Обикновено пускане отсъжда 10–40 прогнози, тоест прагът 5 не се достигаше
# почти никога и обзорът оставаше без нито един мач. Собственикът поиска
# краткост, но не и слепота: „искам си всичко което си имаше и да се вижда".
#
# Сега редът е ЕДИН на мач (виж kratak_red — беше два), значи 24 мача са 24
# реда. Мине ли ги, излишните се преброяват на глас, вместо да се премълчат.
OBZOR_MAKS_MACHOVE = max(0, min(60, int(
    (os.environ.get("SCORE_OBZOR_MACHOVE") or "24").strip() or 24)))


def results_text(now, rows, total_all, hit_all, bez=None, vsichki=None):
    """Обзорът на ЕДНО пускане: колко излязоха, колко познахме, по кой спорт.

    ПРЕНАПИСАН 25.08.2026. Сметката е същата до последния знак — пипнат е само
    градежът на текста. Какво се смени и защо:

      A) Заглавието носи ЧАСА на пускането вместо голата дата (виж chas_bg).
      B) Мач с два пазара се изписва в ЕДИН блок (виж mach_redove).
      C) Неотсъдимите получават причина И последица (виж bez_red).
      + Списъкът мач по мач пада, щом пускането мине OBZOR_MAKS_MACHOVE.

    Поръчката на собственика от 05.08.2026 („раздели ги на спортове, за всеки
    спорт какво е излязло") се СПАЗВА — всичките спортове си остават, но на по
    един ред вместо на цял блок с мачове под него.

    🔴 ЛАЙФТАЙМ РАЗБИВКАТА ИЗЛИЗА ОТТУК. „ДОСЕГА ПО СПОРТОВЕ" и „ОБЩО ДОСЕГА"
    се повтаряха дума по дума в 🧾 ДОСЕГА ОБЩО три секунди по-късно, в същата
    стая. Тук остава ЕДИН лайфтайм ред и той е БЕЗ процент: процентът в това
    съобщение е за днешното пускане, а два процента на един екран се четат
    като спор, не като две числа.

    `vsichki` (целият дневник) вече не се ползва тук. Приема се, за да не
    гръмнат старите повиквания, и защото лайфтаймът си има собствено
    съобщение, което го казва по-подробно.
    """
    # Днешното, групирано по спорт. ЕДИН МАЧ СЕ ПОКАЗВА ВЕДНЪЖ.
    #
    # Дневникът съдържа дубликати: същата среща, вписана в два поредни дни
    # (мачът е бил пренасрочен, а ключът за „вече публикувано" носи деня).
    # Пазачът е тук, а не в дневника, защото обзорът е мястото, което се чете;
    # истинската поправка е в предсказателя.
    grupi = {}
    vidyani = set()
    for rec, hs, as_, ok in rows:
        # 🔴 И ИЗБОРЪТ ВЛИЗА В КЛЮЧА (19.08.2026). Един мач може да даде ДВЕ
        # различни карти: победителя и тотала. Без избора в ключа пазачът ги
        # смяташе за един и същи ред и ГЪЛТАШЕ втория — той излиза в стаята, а
        # в обзора го няма и в числото го няма. Тоест пазач срещу повторение
        # произвеждаше изчезване. Истинският дубликат (същият мач, същият
        # избор, същият резултат) си остава слят — затова и трите са в ключа.
        #
        # 25.08.2026: ключът НЕ Е ПИПАН. Двойното ИЗПИСВАНЕ на мача се лекува
        # в показването (mach_redove), не в броенето.
        kl = (str(rec.get("home") or "").strip().lower(),
              str(rec.get("away") or "").strip().lower(),
              str(rec.get("pick") or "").strip().lower(),
              str(hs), str(as_))
        if kl in vidyani:
            continue
        vidyani.add(kl)
        grupi.setdefault(rec.get("bucket") or "друго", []).append((rec, hs, as_, ok))

    # 🔴 ГЛАВАТА БРОИ ТОЧНО ТОВА, КОЕТО СЕ ВИЖДА ОТДОЛУ (12.08.2026).
    # Дотук главата ползваше суровия списък, а показаното минава през пазача
    # `vidyani`. Главата казваше 14 познати, а редовете под нея сборуваха 13.
    # Затова числата се смятат от СЛЕТИТЕ групи, не от суровия списък.
    _vid = [x for lst in grupi.values() for x in lst]
    _poz = sum(1 for x in _vid if x[3])
    _gres = len(_vid) - _poz
    _pct = (100.0 * _poz / len(_vid)) if _vid else 0.0

    # ЗНАМЕНАТЕЛЯТ ИДВА ПРЪВ И ЗАГУБАТА СЕ ИЗПИСВА С ДУМА.
    # „21 познати" горе и знаменателят три реда по-долу се четат като 21 от
    # каквото окото хване първо. „21 от 39" не може да се обърне.
    out = ["\U0001f4ca <b>ОБЗОР</b> · " + chas_bg(now), "",
           ("<b>" + str(_poz) + " от " + str(len(_vid)) + "</b> · "
            + str(_gres) + mn(_gres, " сгрешена", " сгрешени")
            + " · <b>" + ("%.0f" % _pct) + "%</b>")]

    # Кои дни покрива това пускане. Второ разграничение между двете дневни
    # пускания, и то се СМЯТА от записите, не се пише на ръка.
    _dni = sorted({str(x[0].get("day") or "")[:10] for x in _vid})
    _dni = [d for d in _dni if len(d) == 10]
    if len(_dni) > 1:
        out.append("мачове от " + den_kratko(_dni[0]) + " до " + den_kratko(_dni[-1]))
    out.append("")

    for b in po_red(list(grupi)):
        redove = grupi[b]
        p = sum(1 for x in redove if x[3])
        out.append(sport_emo(b) + " " + sport_ime(b).capitalize() + " <b>"
                   + str(p) + " от " + str(len(redove)) + "</b>")

    _bez = bez_text(bez or {})
    if _bez:
        out += [""] + _bez

    # Списъкът мач по мач. Реже се по МАЧОВЕ и излишните се казват на глас —
    # премълчан остатък е по-лош от дълъг списък: читателят не знае, че има
    # още, и решава, че мачът му просто липсва.
    if _vid:
        _vsichki_m = broy_machove(_vid)
        out += [""] + mach_redove(_vid, OBZOR_MAKS_MACHOVE)
        _ostavat = _vsichki_m - min(_vsichki_m, OBZOR_MAKS_MACHOVE)
        if _ostavat > 0:
            out.append("… и още " + str(_ostavat)
                       + mn(_ostavat, " мач", " мача"))

    # ЕДИНСТВЕНИЯТ лайфтайм ред тук, и той без процент. Стои, защото обзорът
    # отива и в канала, а 🧾 ДОСЕГА ОБЩО — само в стая 9.
    out += ["", "\U0001f4c8 Досега общо: <b>" + str(hit_all) + " от "
            + str(total_all) + "</b>",
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
# ============================== ЗАТВАРЯЩАТА ЦЕНА (18.08.2026)
#
# 69% познати не отговаря на въпроса, който има значение. Фаворит на 1.30,
# познат в 69% от случаите, ГУБИ пари. Единственият честен въпрос е: движи ли
# се пазарът КЪМ нас, след като сме казали?
#
# Предсказателят вече пази цената при ПУСКАНЕ и адреса на срещата. Тук, в мига
# на присъдата, се взима цената при ЗАТВАРЯНЕ. Разликата между двете е CLV — и
# тя работи при двайсет залога, докато „процент познати" иска стотици.
#
# ЕДНА заявка на запис, само за записи, които изобщо имат цена (три спорта).
def hvani_zatvaryashta(r):
    """Записва pazar_close и pazar_clv. True, ако е добавено нещо ново."""
    if not r.get("pazar_cena") or r.get("pazar_close") is not None:
        return False
    ev, sp, lg = r.get("pazar_ev"), r.get("pazar_sport"), r.get("pazar_liga")
    if not (ev and sp and lg):
        return False
    try:
        import pazar as PZ
    except Exception:                                        # noqa: BLE001
        return False
    try:
        dom, gost, raven = PZ.cena_zatvarayashta(sp, lg, ev)
    except Exception:                                        # noqa: BLE001
        return False
    pick = str(r.get("pick") or "")
    cena = (dom if pick.startswith("1")
            else gost if pick.startswith("2")
            else raven if pick[:1] in ("Х", "X") else None)
    if not cena:
        return False
    r["pazar_close"] = cena
    # Движението се мери във ВЕРОЯТНОСТИ. Пет стотинки при 1.20 и пет при
    # 5.00 са различни неща и събирането им би било безсмислица.
    dv = PZ.dvizhenie(r.get("pazar_cena"), cena)
    if dv is not None:
        r["pazar_clv"] = dv
    return True


def dohodnost(rows, minimum=None):
    """(редове, брой) — истинската доходност при РАВЕН залог. Празно при малка извадка.

    Това е единственият ред, който отговаря на въпроса „струва ли си".
    Процентът познати НЕ отговаря: фаворит на 1.30, познат в 69% от случаите,
    връща 0.69 x 1.30 = 0.897, тоест ГУБИ 10 стотинки на лев.

    Смята се на равен залог от 1, защото всяко друго разпределение е избор,
    който ние нямаме право да правим вместо човека.
    """
    minimum = DOHOD_MIN if minimum is None else minimum
    g = [r for r in (rows or [])
         if r.get("hit") is not None and r.get("pazar_cena")
         and int(r.get("pazar_v") or 0) >= 2]
    if len(g) < minimum:
        return [], len(g)
    vlozheno = float(len(g))
    varnato = sum((float(r["pazar_cena"]) if r.get("hit") else 0.0) for r in g)
    roi = 100.0 * (varnato - vlozheno) / vlozheno
    sr_cena = sum(float(r["pazar_cena"]) for r in g) / len(g)
    poz = sum(1 for r in g if r.get("hit"))
    out = ["  %-27s %3d" % ("мача с цена", len(g)),
           "  %-27s %3d · %.0f%%" % ("познати", poz, 100.0 * poz / len(g)),
           "  %-27s %.2f" % ("средна цена", sr_cena),
           "  %-27s %+.1f%%" % ("доходност при равен залог", roi)]
    return out, len(g)


def pokritie(rows):
    """(с цена, всички отсъдени) — за да не се крие обхватът на числото."""
    ots = [r for r in (rows or []) if r.get("hit") is not None]
    sc = [r for r in ots if r.get("pazar_cena") and int(r.get("pazar_v") or 0) >= 2]
    return len(sc), len(ots)


def clv_text(rows, minimum=None):
    """Редовете за CLV. Празно, докато извадката е малка."""
    minimum = CLV_MIN if minimum is None else minimum
    g = [r for r in (rows or [])
         if r.get("pazar_clv") is not None and int(r.get("pazar_v") or 0) >= 2]
    if len(g) < minimum:
        return [], len(g)
    kum = [r for r in g if float(r["pazar_clv"]) > 0]
    ot = [r for r in g if float(r["pazar_clv"]) < 0]
    sr = sum(float(r["pazar_clv"]) for r in g) / len(g)
    out = ["  %-27s %3d" % ("пазарът дойде при нас", len(kum)),
           "  %-27s %3d" % ("пазарът се отдалечи", len(ot)),
           "  %-27s %+.2f точки" % ("средно движение", 100.0 * sr)]
    return out, len(g)


def obshto_dosega_text(now, rows):
    """Равносметката на целия живот на бота. Едно съобщение, стая 9.

    СВИТА ДО ЧЕТИРИ РЕДА (25.08.2026) по дословна поръчка на собственика:
        „КРАТКО КОЛКО МАЧА КОЛКО СПЕЧЕЛЕНИ КОЛКО ЗАГУБИЛ И ПРОЦЕНТ И ТВА Е."

    🔴 КАКВО ОТПАДА — казано, не премълчано. Беше 23 реда / 751 знака:
      • таблицата „По спорт" (7 реда) — кой спорт колко е познал за целия
        живот. ТОВА Е ИСТИНСКА ЗАГУБА: обзорът брои САМО деня, тоест
        всеживотното число по спорт вече не се вижда НИКЪДЕ. Връща се с
        една дума, ако собственикът го поиска обратно.
      • редът „Когато не сме съгласни с пазара" (3 реда).
      • редът за периода („от 05.08 до 25.08 · 21 дни").
      • редът за мачовете без резултат и обяснението му.
      Сметките НЕ са пипани — само печатането.

    ЗАЩО ЧЕТИРИ, А НЕ ДВА: „696 с резултат" без „743 пуснати" крие
    знаменателя, а точно той пази числото от разкрасяване. Едното без
    другото е половин истина.
    """
    rows = list(rows or [])
    pusnati = len(rows)
    ots = [r for r in rows if r.get("scored") and r.get("hit") is not None]
    poz = sum(1 for r in ots if r.get("hit"))
    zag = len(ots) - poz

    if not ots:
        return NL.join([
            "\U0001f9fe <b>ДОСЕГА ОБЩО</b>",
            "",
            "Още нищо не е отсъдено — " + str(pusnati)
            + mn(pusnati, " чака мача си.", " чакат мачовете си."),
            "",
            "\U0001f7e2 THE GREEN ROOM"])

    # Периодът е СБИТ до „от <дата>", защото един ред е по-евтин от два.
    # 🔴 СТЪПВА НА ДЕНЯ НА ПУБЛИКУВАНЕ (`posted`), НЕ НА ДЕНЯ НА МАЧА.
    # Първата ми свита версия взе `day` и счупи стара, права поправка: карта
    # за утрешен мач се публикува днес, а карта с крив ден (виждали сме 2099)
    # би опънала периода в бъдещето или миналото. „Всичко, пуснато досега" се
    # мери по ПУСКАНЕТО. Хванато от собствената стара проверка.
    dni = sorted(str(r.get("posted") or "")[:10] for r in rows
                 if len(str(r.get("posted") or "")) >= 10)
    ot = ""
    if dni:
        ot = " · от " + dni[0][8:10].lstrip("0") + "." + dni[0][5:7]

    return NL.join([
        "\U0001f9fe <b>ДОСЕГА ОБЩО</b>" + ot,
        "",
        "<b>" + str(pusnati) + "</b> " + mn(pusnati, "пусната", "пуснати")
        + " · <b>" + str(len(ots)) + "</b> с резултат",
        "✅ <b>" + str(poz) + "</b> " + mn(poz, "позната", "познати")
        + " · ❌ <b>" + str(zag) + "</b> " + mn(zag, "загубена", "загубени")
        + " · <b>" + ("%.0f" % (100.0 * poz / len(ots))) + "%</b>",
        "",
        "\U0001f7e2 THE GREEN ROOM"])

def den_finish_text(now, rows, den, mezhdinna=False, bez_sportove=False):
    """Равносметката на един ден: пуснато, отсъдено, познато, останало.

    mezhdinna=True е обедният вариант: същите числа, но заглавието и краят
    казват, че денят ТЕЧЕ. Две еднакви „равносметки" на ден правят и двете
    безсмислени — затова разликата е в текста, не само в часа.

    ПРЕНАПИСАН 25.08.2026 — текстът, не сметката:

      • ЗНАМЕНАТЕЛЯТ ИДВА ПРЪВ. Дотук пишеше „пуснати ДНЕС: 62", после
        „познати: 17", а истинският знаменател (27 отсъдени) идваше три реда
        по-долу. Човек чете 17 от 62 и разбира 27%. Сега е едно изречение:
        „От 62 пуснати днес 27 имат резултат" — обръщането е невъзможно.

      • ТОВА СЪОБЩЕНИЕ ВЕЧЕ НЯМА ПРОЦЕНТ. Едно съобщение — един измерител.
        Финишът брои по деня на ПУБЛИКУВАНЕ, обзорът по деня на МАЧА; двата
        процента са верни поотделно и се бият пред очите на човека, когато
        излязат един под друг за пет секунди. Процентът остава ЕДИН и е в
        обзора. Числата, които БОЛЯТ (сгрешените), си остават тук — те са
        изрична поръчка на собственика и не мърдат.

      • ЗАГЛАВИЕТО НОСИ ДЕНЯ, ЗА КОЙТО Е. Дотук стоеше date_bg(now): в 01:00
        след полунощ `den` е вчера, а надписът показваше днес.
    """
    dnes = [r for r in rows if str(r.get("posted") or "")[:10] == den]
    otsadeni = [r for r in dnes if r.get("hit") is not None]
    poznati = [r for r in otsadeni if r.get("hit") is True]
    zagubeni = [r for r in otsadeni if r.get("hit") is False]
    chakat = [r for r in dnes if not r.get("scored")]
    bez = [r for r in dnes if r.get("scored") and r.get("hit") is None]

    if mezhdinna:
        out = ["\U0001f552 <b>ДОКЪДЕ СМЕ ДНЕС</b> · " + den_dumi(den) + ", "
               + now.strftime("%H:%M"),
               "<i>обедна снимка — денят още тече</i>", ""]
    else:
        out = ["\U0001f3c1 <b>ФИНИШ НА ДЕНЯ</b> · " + den_dumi(den), ""]
    if not dnes:
        out += ["Днес нямаше нито една прогноза.",
                ("Следващите пускания са до 23:00." if mezhdinna
                 else "Утре от 08:00 продължаваме."),
                "", "\U0001f7e2 THE GREEN ROOM"]
        return NL.join(out)

    out.append("От <b>" + str(len(dnes)) + "</b> "
               + mn(len(dnes), "пусната", "пуснати") + " днес <b>"
               + str(len(otsadeni)) + "</b> "
               + mn(len(otsadeni), "има", "имат") + " резултат.")
    if otsadeni:
        out.append("✅ познахме <b>" + str(len(poznati)) + "</b> · ❌ сгрешихме <b>"
                   + str(len(zagubeni)) + "</b>")
    else:
        out.append(mn(len(dnes),
                      "Още не е отсъдена — мачът още не е дошъл.",
                      "Нито един още не е отсъден — мачовете им още"
                      " не са дошли."))
    if chakat:
        out.append("⏳ " + str(len(chakat))
                   + mn(len(chakat), " чака мача си", " чакат мачовете си"))
    out += bez_red(len(bez))

    # Присъдите, дошли ДНЕС, но за карти, пуснати ПО-РАНО. Без този ред
    # човекът чете „0 имат резултат" и решава, че оценителят не работи — а той
    # тъкмо е отсъдил шест мача, просто пуснати предния ден. И трите школи в
    # спора искаха да падне; оставям го, защото е ЕДИНСТВЕНИЯТ мост между това
    # съобщение (брои по ден на пускане) и обзора (брои по ден на мача).
    # Махна ли го, двете числа продължават да се разминават, само че вече без
    # обяснение — това е криене, не скъсяване.
    _rano = [r for r in rows
             if r.get("hit") is not None
             and str(r.get("day") or "")[:10] == den
             and str(r.get("posted") or "")[:10] != den]
    if _rano:
        out.append("\U0001f5c2 плюс <b>" + str(sum(1 for r in _rano if r.get("hit")))
                   + " от " + str(len(_rano)) + "</b> "
                   + mn(len(_rano), "по-раншна карта, отсъдена днес",
                        "по-раншни карти, отсъдени днес"))

    # Разбивка по спорт САМО за днес — това е „какво що" на деня.
    # Заглавието „ДНЕС ПО СПОРТОВЕ" отпада: редът „⚽ Футбол 4 от 7" се обяснява
    # сам, а надпис над три реда е ред, платен за нищо.
    po_sport = {}
    for r in otsadeni:
        b = r.get("bucket") or "друго"
        p, n = po_sport.get(b, (0, 0))
        po_sport[b] = (p + (1 if r.get("hit") else 0), n + 1)
    # 🔴 НЕ Я ПОКАЗВАЙ, АКО ОБЗОРЪТ ТОКУ-ЩО Я Е ПОКАЗАЛ (26.08.2026).
    #
    # Обзорът брои отсъденото В ТОВА ПУСКАНЕ, финишът — за ЦЕЛИЯ ДЕН. И двете
    # са верни, но пристигат на 2.0 секунди разстояние в едни и същи два
    # адреса и читателят вижда „⚽ Футбол 1 от 3", после „⚽ Футбол 1 от 5".
    #
    # Същият дефект вече е бил решен за ПРОЦЕНТА (махнат от финиша по същата
    # причина). Дробите по спорт са останали — това е близнакът му.
    #
    # Когато обзор НЯМА (пускане без нови присъди), финишът е единственото
    # съобщение и разбивката остава. Нула изгубена информация.
    if po_sport and not bez_sportove:
        out.append("")
        for b in po_red(list(po_sport)):
            p, n = po_sport[b]
            out.append(sport_emo(b) + " " + sport_ime(b).capitalize() + " <b>"
                       + str(p) + " от " + str(n) + "</b>")

    # Фишовете на деня — по номер, с колко крака са минали.
    #
    # 🔴 ЗНАМЕНАТЕЛЯТ НА ФИША НЕ Е ПИПАН. „2 от 4 · 1 още чака" изглежда като
    # грешка (четвъртият крак още не е игран) и в спора се предлагаше да стане
    # „2 от 3". Това е промяна в СМЕТКАТА, не в текста, и тя вдига процентите
    # на фишовете — тоест изглежда като разкрасяване. Не се промъква тук.
    # Сменена е само думата: „крака", за да се вижда от какво е дробта.
    fishove = {}
    for r in dnes:
        n = int(r.get("combo") or 0)
        if n:
            fishove.setdefault(n, []).append(r)
    if fishove:
        out.append("")
        for n in sorted(fishove):
            legs = fishove[n]
            ok = sum(1 for r in legs if r.get("hit") is True)
            gotovi = sum(1 for r in legs if r.get("hit") is not None)
            red = ("\U0001f3ab Фиш " + str(n) + ": <b>" + str(ok) + " от "
                   + str(len(legs)) + "</b> " + mn(len(legs), "крак", "крака"))
            if gotovi < len(legs):
                ost = len(legs) - gotovi
                red += " · " + str(ost) + mn(ost, " крак още чака",
                                             " крака още чакат")
            elif ok == len(legs):
                red += " · \U0001f7e2 МИНА ЦЕЛИЯТ"
            out.append(red)

    if mezhdinna:
        out += ["", "Още карти до 23:00 \U0001f680", "\U0001f7e2 THE GREEN ROOM"]
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
    # 🔴 ДВЕ ЧИСЛА В ЕДНО ИЗРЕЧЕНИЕ, ВСЯКО СЪС СВОЯТА ДУМА (26.08.2026):
    # ЧИСЛИТЕЛЯТ носи глагола („1 от 3 фиша МИНА“, не „минаха“),
    # ЗНАМЕНАТЕЛЯТ носи съществителното („2 от 1 ФИШ“). Дотук и двете
    # бяха заковани в множествено: „0 от 1 фиша минаха.“
    # Нулата получава СВОЕ изречение — „0 от 1 фиш минаха“ е вярно по
    # правило и нечетимо на глас.
    if minali == 0:
        out.append("<b>Нито един "
                   + mn(len(slips), "фиш",
                        "от " + str(len(slips)) + " фиша")
                   + " не мина.</b>")
    else:
        out.append("<b>" + str(minali) + " от " + str(len(slips)) + " "
                   + mn(len(slips), "фиш", "фиша") + " "
                   + mn(minali, "мина", "минаха") + ".</b>")
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


# ═══════════════════════════════════ 🗄️ АРХИВЪТ (18.08.2026)
#
# ИЗМЕРЕНО, НЕ ПРЕДПОЛОЖЕНО: 460 байта на запис, 18.6 записа на ден. Наесен
# обемът се удвоява (връщат се хокеят и амер. футбол, тръгват НБА и евролигите).
#   след  3 месеца ·  3 616 записа ·  1.6 MB
#   след 12 месеца · 13 870 записа ·  6.1 MB
#   след 24 месеца · 27 479 записа · 12.0 MB
#
# А файлът се ЧЕТЕ И ЗАПИСВА ЦЯЛ при всеки рън — 30 пъти на ден, всеки път
# нов комит в хранилището. Това не е „някой ден проблем", а сигурен.
#
# Затова: приключените записи, по-стари от ARHIV_DNI, се местят в отделен
# файл. Горещият дневник остава малък и бърз. Архивът е append-only и НЕ се
# чете от оценяването — само от статистиката, която го иска цял.
#
# Нищо не се губи. Това е преместване, не чистене.
ARHIV_FILE = (os.environ.get("SCORE_ARHIV_FILE") or "predict_log_arhiv.json").strip()
# 🔴 120 → 60 НА 18.08.2026. Две причини, и двете измерени.
# 1) Таванът на дневника трябва да е над MAX_DAY × ARHIV_DNI. При 120 дни и
#    40 карти това е 4800 — на ръба на всяка разумна граница. При 60 е 2400.
# 2) При 120 дни архивиращият код НЯМАШЕ да се пусне нито веднъж до 03.12 —
#    тоест щеше да стои непроверен в бой още 107 дни. При 60 тръгва наесен.
ARHIV_DNI = max(30, min(400, int((os.environ.get("SCORE_ARHIV_DNI") or "60").strip())))


def cheti_arhiv():
    """Архивните записи. Празно при липса или боклук — статистиката не спира."""
    try:
        with open(ARHIV_FILE, encoding="utf-8-sig") as f:
            r = json.load(f)
        return r if isinstance(r, list) else []
    except Exception:                         # noqa: BLE001
        return []


def cyal_dnevnik(rows=None):
    """Архивът + горещият дневник. За статистика, която иска ЦЕЛИЯ живот."""
    return cheti_arhiv() + list(rows if rows is not None else load_log())


def arhiviray(rows, now):
    """Мести приключените стари записи в архива. Връща (горещи, преместени).

    Мести се САМО запис, който е приключен (scored) — висящите остават, докато
    не получат присъда, колкото и стари да са. Иначе архивът щеше да поглъща
    точно това, което още чакаме.
    """
    granica = (now - timedelta(days=ARHIV_DNI)).strftime("%Y-%m-%d")
    stari, goreshti = [], []
    for r in rows:
        den = str(r.get("posted") or r.get("day") or "")[:10]
        (stari if (r.get("scored") and len(den) == 10 and den < granica)
         else goreshti).append(r)
    if not stari or DRY_RUN:
        return rows, 0
    try:
        vsi = cheti_arhiv() + stari
        tmp = ARHIV_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(vsi, f, ensure_ascii=False, indent=1)
        os.replace(tmp, ARHIV_FILE)
    except Exception as e:                    # noqa: BLE001
        # Архивът не се записа — НЕ пипаме горещия дневник. По-добре голям
        # файл, отколкото изгубени записи.
        print("архивът не се записа (" + str(e)[:60] + ") — оставям всичко.")
        return rows, 0
    return goreshti, len(stari)


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


# 🔴 РЕДОСЛЕДЪТ СЕ ПРОВЕРЯВА БЕЗОПАСНО (25.08.2026).
# `.index()` ХВЪРЛЯ ValueError, когато низът липсва — и с това събаря ЦЯЛАТА
# самопроверка, скривайки всичко след себе си. Намерено при мутация: махнах
# списъка мач по мач и вместо „счупено: списъкът изчезна" получих трасе,
# тоест ЗАГУБИХ и присъдата, и всички проверки надолу.
# `predi()` първо пита ИМА ЛИ ГИ и чак после — в какъв ред са.
def predi(tekst, parvo, vtoro):
    """True, ако `parvo` стои ПРЕДИ `vtoro`. False, ако някой липсва."""
    t = str(tekst or "")
    if parvo not in t or vtoro not in t:
        return False
    return t.index(parvo) < t.index(vtoro)


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

    # --- ТОТАЛЪТ (втората карта от същия мач, 19.08.2026)
    check("линията се чете от избора", total_line("Над 2.5 гола") == 2.5)
    check("линията се чете и при Под", total_line("Под 8.5 рънове") == 8.5)
    check("трицифрената линия се чете", total_line("Над 167.5 точки") == 167.5)
    check("цяла линия НЕ се отсъжда", total_line("Над 8 рънове") is None)
    check("победа не е тотал", total_line("1 · победа Милан") is None)
    check("празното не е тотал", total_line("") is None and total_line(None) is None)
    check("боклук след думата не е тотал", total_line("Над много гола") is None)
    tn = {"home": "Левски", "away": "ЦСКА", "pick": "Над 2.5 гола"}
    check("над 2.5 печели при 2:1", verdict(tn, 2, 1) is True)
    check("над 2.5 губи при 1:1", verdict(tn, 1, 1) is False)
    check("над 2.5 губи при 0:0", verdict(tn, 0, 0) is False)
    tp = {"home": "Левски", "away": "ЦСКА", "pick": "Под 2.5 гола"}
    check("под 2.5 печели при 1:1", verdict(tp, 1, 1) is True)
    check("под 2.5 губи при 2:1", verdict(tp, 2, 1) is False)
    tb = {"home": "A", "away": "B", "pick": "Под 8.5 рънове"}
    check("под 8.5 печели при 4:4", verdict(tb, 4, 4) is True)
    check("под 8.5 губи при 5:4", verdict(tb, 5, 4) is False)
    tk = {"home": "A", "away": "B", "pick": "Над 167.5 точки"}
    check("над 167.5 печели при 90:80", verdict(tk, 90, 80) is True)
    check("над 167.5 губи при 84:83", verdict(tk, 84, 83) is False)
    # 🔴 ИМЕТО НЕ БИВА ДА ПРЕХВАЩА ТОТАЛА. Ако някой ден отбор се казва с дума,
    # която влиза в текста на тотала, присъдата пак трябва да е по СБОРА.
    tx = {"home": "Над", "away": "Под", "pick": "Над 2.5 гола"}
    check("тоталът се съди по сбора, не по имената", verdict(tx, 3, 0) is True)

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
    # 🔴 ОБЪРНАТИ 25.08.2026 (ДЕФЕКТ A). Дотук проверката ПАЗЕШЕ заглавието
    # „ОБЗОР НА ДЕНЯ" — точно надписа, който излизаше два пъти на ден с
    # различни мачове под него и с число само за собственото си пускане.
    # Проверката не се трие: обръща се и вече пази, че този надпис го НЯМА.
    check("заглавието вече НЕ обещава цял ден", "ОБЗОР НА ДЕНЯ" not in t)
    check("заглавието носи ЧАСА на пускането",
          "<b>ОБЗОР</b> · " in t and _now.strftime(", %H:%M") in t)
    check("отчетът дава знаменателя веднага", "<b>1 от 2</b>" in t)
    check("отчетът изписва и сгрешените", "1 сгрешена" in t)
    check("езикът е български и в единствено число",
          "1 сгрешени" not in t and "2 сгрешена" not in
          results_text(_now, _rows + [({"home": "Х", "away": "У", "pick": "1",
                                        "bucket": "football"}, 0, 1, False)],
                       10, 6))
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
               and "познахме" not in l and "познати" not in l]
    check("дубълът се показва ВЕДНЪЖ", len(_redove) == 2)
    check("главата брои видимите, не суровите", "<b>1 от 2</b>" in _td)
    check("процентът е върху видимите", "· <b>50%</b>" in _td)

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
    # 🔴 ОБЪРНАТА 25.08.2026: заглавието вече не сочи стаята. То заемаше
    # половин ред от петте, а читателят на стая 9 знае къде е.
    check("заглавието вече не сочи стаята", "БОТА ПРЕДРИЧА" not in _od)
    check("но си остава озаглавена", "ДОСЕГА ОБЩО" in _od)
    # 🔴 ОБЪРНАТА: същото число, друг градеж — „От 7 пуснати" стана „7 пуснати".
    check("брои ВСИЧКИ пуснати, не само отсъдените", "<b>7</b> пуснати" in _od)
    # Помощникът срещу събарянето — изпитан, преди да се разчита на него.
    check("вижда верния ред", predi("абв", "а", "в"))
    check("вижда обърнатия ред", not predi("абв", "в", "а"))
    # 🔴 ГЛАВНОТО: липсващият низ дава False, НЕ трасе.
    check("липсващият първи не гърми", predi("абв", "я", "в") is False)
    check("липсващият втори не гърми", predi("абв", "а", "я") is False)
    check("празният текст не гърми", predi("", "а", "б") is False)
    check("None не гърми", predi(None, "а", "б") is False)

    # 🔴 ЗНАМЕНАТЕЛЯТ ПАК Е ПРЪВ — правилото от 25.08 сутринта се пази.
    # „7 пуснати" стои ПРЕДИ „5 с резултат", и двете преди познатите.
    check("знаменателят стои ПРЕДИ числителя",
          predi(_od, "пуснати", "с резултат")
          and predi(_od, "с резултат", "познати"))
    check("брои познатите", "<b>4</b> познати" in _od)
    check("брои загубените", "<b>1</b> загубена" in _od)
    check("процентът е върху отсъдените",
          "<b>5</b> с резултат" in _od and "<b>80%</b>" in _od)
    # 🔴 ОБЪРНАТА: редът „колко чакат" отпадна с поръчката за четири числа.
    # Чакащите СЕ БРОЯТ както преди — просто не се обявяват тук. Виждат се в
    # междинната и във финиша на деня.
    check("редът за чакащите вече го няма", "чака мача си" not in _od)
    # 🔴 И ЕДИНСТВЕНОТО ЧИСЛО НА БЪЛГАРСКИ. „1 загубени" е грешно.
    check("едно е ЗАГУБЕНА, не загубени", "<b>1</b> загубени" not in _od)
    _mn = obshto_dosega_text(_now, [{"scored": True, "hit": False,
                                     "posted": "2026-08-10 12:00"}
                                    for _ in range(3)])
    check("три са ЗАГУБЕНИ", "<b>3</b> загубени" in _mn)
    _edn = obshto_dosega_text(_now, [{"scored": True, "hit": True,
                                      "posted": "2026-08-10 12:00"}])
    check("една е ПОЗНАТА", "<b>1</b> позната" in _edn)
    # 🔴 ОБЪРНАТИ 25.08.2026: редовете „без резултат" и „периодът в дни"
    # отпаднаха с поръчката за четири числа. Мачовете без резултат СЕ БРОЯТ
    # както преди — просто вече не се обявяват отделно.
    check("редът за мачове без резултат вече го няма",
          "мач без резултат" not in _od)
    check("периодът в дни вече го няма", "2 дни" not in _od)
    # А началната дата ОСТАВА — тя казва откога изобщо съществува ботът.
    # 🔴 ДАТАТА ИСКА `posted`, А ФИКСТУРАТА `_dnev` НЯМА ТАКОВА ПОЛЕ.
    # Това НЕ Е дефект — записи без час на пускане просто не дават период.
    # Проверява се със собствена фикстура, за да е ясно КАКВО се изпитва.
    _sp = obshto_dosega_text(_now, [
        {"scored": True, "hit": True, "posted": "2026-08-10 12:00"},
        {"scored": True, "hit": True, "posted": "2026-08-11 12:00"}])
    check("началната дата е най-старата", "10.08" in _sp)
    check("крайната дата вече не се изписва", "11.08" not in _sp)
    # 🔴 И ПАК СТЪПВА НА ПУБЛИКУВАНЕТО, НЕ НА МАЧА. Карта за мач през 2099,
    # пусната днес, не бива да мести периода — стара, права поправка, която
    # първата ми свита версия счупи и собствената ѝ проверка я хвана.
    _b99 = obshto_dosega_text(_now, [
        {"scored": True, "hit": True, "day": "2099-01-01",
         "posted": "2026-08-10 12:00"}])
    check("бъдещ мач НЕ мести периода", "2099" not in _b99 and "10.08" in _b99)
    check("запис без час на пускане не дава период",
          "· от " not in obshto_dosega_text(_now, [{"scored": True, "hit": True}]))
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
    _telo_od = _ziv0.split("def obshto" + "_dosega_text")[1][:3000]         if ("def obshto" + "_dosega_text") in _ziv0 else ""
    check("периодът стъпва на деня на ПУБЛИКУВАНЕ", "posted" in _telo_od)
    # 🔴 ЧЕТИРИТЕ ПРОВЕРКИ ПОД ТОЗИ РЕД СА ОБЪРНАТИ (25.08.2026), НЕ ТРИТИ.
    # Пазеха разбивката по спорт в равносметката — заедно с правилото „под 5
    # отсъдени НЕ получава процент", което беше добро правило и се помни.
    # Собственикът поръча четири числа и нищо повече.
    #
    # 🔴 ЧЕСТНО ЗА ЗАГУБАТА: всеживотната сметка ПО СПОРТ вече не се вижда
    # НИКЪДЕ в стаята — обзорът брои само деня. Числата ги има в здравния
    # преглед, който чете собственикът. Публиката ги губи.
    check("равносметката вече НЕ носи разбивка по спорт", "По спорт" not in _od)
    check("и не изрежда отделните спортове",
          "ТЕНИС</b>" not in _od and "ФУТБОЛ</b>" not in _od)
    _od2 = obshto_dosega_text(_now, _dnev + [
        {"bucket": "tennis", "day": "2026-08-11", "scored": True, "hit": True}])
    check("нито при малка извадка", "1 от 1 отсъдени" not in _od2)
    check("нито при голяма", "5 отсъдени · <b>80%" not in _od)
    # А ЕДИНСТВЕНИЯТ процент в нея е общият — не по спорт.
    check("процентът е точно един", _od.count("%") == 1)
    check("равносметката е чиста от забранени думи", banned_word(_od) is None)
    # 🔴 ОБЪРНАТА 25.08.2026: празният дневник вече не изрежда нули, а казва
    # с думи, че няма нищо. Нула, изписана като статистика, изглежда като
    # резултат; изречението не изглежда.
    check("празен дневник не гърми и не изрежда нули",
          "0 пуснати" not in obshto_dosega_text(_now, []))
    check("празен дневник казва, че няма отсъдено",
          "Още нищо не е отсъдено" in obshto_dosega_text(_now, []))
    # Ред на пускане: равносметката излиза САМО вечер, и то СЛЕД финиша.
    # Копчето сено е БЕЗ самопроверката (виж _bez_samoproverkata) — иначе
    # редовете тук долу сами щяха да съдържат иглата и проверката щеше да
    # минава винаги. Тоест иглата се намира само в ЖИВИЯ main().
    _ziv = _bez_samoproverkata(open(__file__, encoding="utf-8").read())
    _telo_main = _ziv[_ziv.find("def " + "main("):] if ("def " + "main(") in _ziv else ""
    # 🔴 ОБНОВЕНА 18.08.2026. Подписът се смени: равносметката вече получава
    # ЦЕЛИЯ живот (архив + горещ дневник), не само горещия. Тестът, който
    # пази извикването, се обновява с него — иначе пази вчерашния подпис.
    check("равносметката се праща от main",
          ("obshto_dosega" + "_text(now, cyal_dnevnik(rows))") in _telo_main)
    check("равносметката гледа и архива", "cyal_dnev" + "nik(rows)" in _telo_main)
    check("равносметката е зад условие за вечер", _telo_main.count("if vecher:") >= 2)
    check("равносметката отива в стая 9, не в канала",
          ("post_channel(obshto" + "_dosega") not in _telo_main)

    # 🔴 ОБЪРНАТИ 25.08.2026. Четирите реда „ОБЩО ДОСЕГА" излизат от обзора —
    # те се повтаряха дума по дума в 🧾 ДОСЕГА ОБЩО три секунди по-късно, в
    # СЪЩАТА стая. Проверките не се трият: сега пазят, че блокът го няма ТУК,
    # а веднага след тях стои проверка, че числата ги ИМА ТАМ. Загубено число
    # без нов дом е изтриване; тези имат дом и той се проверява.
    check("лайфтайм блокът излезе от обзора", "ОБЩО ДОСЕГА" not in t)
    check("обзорът не изрежда лайфтайм познати/загубени",
          "познати: <b>6</b>" not in t and "загубени: <b>4</b>" not in t)
    check("остава ЕДИН лайфтайм ред, с двете числа",
          "Досега общо: <b>6 от 10</b>" in t)
    check("лайфтайм редът е БЕЗ процент — процентът е за пускането",
          t.count("%") == 1)
    check("загубените са разликата", (10 - 6) == 4)
    # 🔴 ОБЪРНАТА 25.08.2026 — само по ФОРМАТА, не по смисъл. Числата са
    # същите; редът стана „✅ <b>6</b> познати · ❌ <b>4</b> загубени · 60%".
    _lt = obshto_dosega_text(
        _now, [{"scored": True, "hit": True} for _ in range(6)]
        + [{"scored": True, "hit": False} for _ in range(4)])
    check("лайфтайм познати живеят в равносметката", "<b>6</b> познати" in _lt)
    check("лайфтайм загубени живеят в равносметката", "<b>4</b> загубени" in _lt)
    check("и процентът е верен", "<b>60%</b>" in _lt)
    _t0 = results_text(_now, _rows, 0, 0)
    check("нула отсъдени не чупи", "Досега общо: <b>0 от 0</b>" in _t0)
    _tvs = results_text(_now, _rows, 7, 7)
    check("без загуби пише двете числа, не мълчи",
          "Досега общо: <b>7 от 7</b>" in _tvs)

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
    # 🔴 ДВЕТЕ СЪОБЩЕНИЯ НЕ БИВА ДА СИ ПРОТИВОРЕЧАТ (26.08.2026).
    # Поведенческа проверка: строим ДВАТА варианта и гледаме какво излиза.
    _fin_bez = den_finish_text(datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA),
                               _redove, _dn, bez_sportove=True)
    check("финишът СЪС спортове ги показва", " от " in _fin)
    check("финишът БЕЗ спортове не показва нито един спортов ред",
          not any(_l.strip().startswith(sport_emo(_b))
                  for _b in ("football", "volleyball", "tennis", "tabletennis",
                             "baseball", "basketball")
                  for _l in _fin_bez.split(NL)))
    check("но пуснатите и отсъдените си остават и в двата",
          "пуснати" in _fin_bez and "пуснати" in _fin)
    check("махането САМО скъсява — нищо ново не се появява",
          len(_fin_bez) < len(_fin))
    check("финишът е озаглавен", "ФИНИШ НА ДЕНЯ" in _fin)
    check("финишът брои само днешните", "От <b>4</b> пуснати днес" in _fin)
    check("финишът брои познатите", "познахме <b>1</b>" in _fin)
    check("финишът брои сгрешените", "сгрешихме <b>1</b>" in _fin)
    check("финишът брои чакащите", "1 чака мача си" in _fin)
    check("финишът брои неотсъдимите",
          "1 мач без резултат" in _fin and "не го броим" in _fin)
    # 🔴 ОБЪРНАТА 25.08.2026. Дотук проверката ИСКАШЕ процент във финиша.
    # Финишът брои по деня на ПУБЛИКУВАНЕ, обзорът по деня на МАЧА — двата
    # процента са верни поотделно и се бият пред очите на човека, когато
    # излязат един под друг за пет секунди. Процентът остава ЕДИН и е в
    # обзора; тук остават броевете, включително този, който боли.
    check("финишът НЕ дава процент — процентът е само в обзора", "%" not in _fin)
    check("но финишът пак изписва сгрешените",
          "❌ сгрешихме" in _fin)
    check("знаменателят във финиша идва ПРЪВ",
          predi(_fin, "имат резултат", "познахме"))
    check("финишът отчита фиша", "Фиш 1: <b>1 от 2</b>" in _fin)
    check("финишът пожелава лека вечер", "Лека вечер" in _fin)
    check("финишът е чист от забранени думи", banned_word(_fin) is None)
    _praz = den_finish_text(datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA), [], _dn)
    check("празният ден пак получава финиш", "ФИНИШ НА ДЕНЯ" in _praz)
    check("празният ден го казва направо", "нито една прогноза" in _praz)
    check("празният ден не лъже с проценти", "%" not in _praz)
    # 🔴 ОБЪРНАТА 26.08.2026, НЕ ИЗТРИТА. Стоеше с ЕДНА карта и искаше
    # „мачовете им още не са дошли“ — тоест ЗАКЛЮЧВАШЕ дефекта:
    # множествено число при единица. Затова светеше зелена всеки ден,
    # докато стаята четеше крив български. Сега тук стоят ДВЕ карти и
    # проверката пази МНОЖЕСТВЕНОТО; единицата получава своя проверка.
    _cql = den_finish_text(datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA),
                           [dict(_redove[2]), dict(_redove[2])], _dn)
    check("ден без нито един отсъден го казва",
          "мачовете им още не са дошли" in _cql)
    _cql1 = den_finish_text(datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA),
                            [dict(_redove[2])], _dn)
    check("а при ЕДНА карта го казва в единствено число",
          "мачът още не е дошъл" in _cql1 and "мачовете им" not in _cql1)

    # --- 🕒 ОБЕДНАТА РАВНОСМЕТКА. Същите числа, ДРУГО заглавие — иначе два
    # еднакви „финиша" на ден правят и двата безсмислени.
    _obed = den_finish_text(datetime(2026, 8, 11, 15, 30, tzinfo=SOFIA),
                            _redove, _dn, mezhdinna=True)
    check("обедната се казва другояче", "ДОКЪДЕ СМЕ ДНЕС" in _obed)
    check("обедната НЕ се представя за финиш", "ФИНИШ НА ДЕНЯ" not in _obed)
    check("обедната казва, че денят тече", "денят още тече" in _obed)
    check("обедната не пожелава лека вечер", "Лека вечер" not in _obed)
    check("обедната носи същите числа", "От <b>4</b> пуснати днес" in _obed)
    check("обедната казва, че е снимка, не край", "обедна снимка" in _obed)
    check("обедната също няма процент", "%" not in _obed)
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
        # 🔴 ОБЪРНАТА (02.09.2026): «коеф» е разрешена по нареждане на
        # собственика. Доказваме същото с дума, която ОСТАВА забранена.
        check("каналът ПРИЕМА коефициент ПРИ РАБОТЕЩО пращане",
              post_channel("коефициент 1.85") is True)
        check("но отказва «букмейкър» ПРИ РАБОТЕЩО пращане",
              post_channel("букмейкър 1.85") is False)
        check("и отказва име на оператор ПРИ РАБОТЕЩО пращане",
              post_channel("bet365 1.85") is False)
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
    # 🔴 ПОРЪЧКАТА НА СОБСТВЕНИКА ОТ 05.08.2026 ОСТАВА В СИЛА: всеки спорт
    # със своето число. Смени се само дрехата — един ред вместо цял блок.
    check("обзорът има ред за футбола", "⚽ Футбол" in _t3)
    check("обзорът има ред за волейбола", "🏐 Волейбол" in _t3)
    check("обзорът има ред за баскетбола", "🏀 Баскетбол" in _t3)
    check("всеки ред носи своето число", "Футбол <b>1 от 2</b>" in _t3)
    check("волейболният ред е 1 от 1", "Волейбол <b>1 от 1</b>" in _t3)
    check("футболът е преди волейбола (постоянен ред)",
          predi(_t3, "Футбол", "Волейбол"))
    # 🔴 ОБЪРНАТИ 25.08.2026. Лайфтайм таблицата „ДОСЕГА ПО СПОРТОВЕ" излиза от
    # обзора, защото 🧾 ДОСЕГА ОБЩО я повтаря дословно секунди по-късно в
    # същата стая. Не се трие ЧИСЛОТО — трие се ПОВТОРЕНИЕТО. Затова всяка
    # обърната проверка си има близнак, който намира същото число в другото
    # съобщение, построено от СЪЩИЯ дневник.
    _dos = obshto_dosega_text(_now, _dnevnik)
    check("лайфтайм таблицата излезе от обзора", "ДОСЕГА ПО СПОРТОВЕ" not in _t3)
    check("волейболът вече НЕ е поотделно в равносметката",
          "12 от 13 отсъдени" not in _dos)
    # 🔴 ПЕТТЕ ПРОВЕРКИ ПОД ТОЗИ РЕД СА ОБЪРНАТИ (25.08.2026), НЕ ТРИТИ.
    # Дотук пазеха таблицата „По спорт" в равносметката. Собственикът я махна
    # с дословна поръчка: „КРАТКО КОЛКО МАЧА КОЛКО СПЕЧЕЛЕНИ КОЛКО ЗАГУБИЛ И
    # ПРОЦЕНТ И ТВА Е." Сега пазят, че равносметката Е КЪСА — а сметките, които
    # ги захранваха, СТОЯТ непокътнати и се пазят другаде.
    check("равносметката вече НЕ носи таблица по спорт",
          "По спорт" not in _dos and "ВОЛЕЙБОЛ" not in _dos)
    check("и НЕ носи процент по спорт", "92%" not in _dos and "18%" not in _dos)
    # А четирите числа, които собственикът поиска, ТРЯБВА да ги има.
    check("равносметката носи пуснатите", "пуснати" in _dos)
    check("носи отсъдените", "с резултат" in _dos)
    check("носи познати и загубени",
          "познати" in _dos and "загубени" in _dos)
    check("носи процента", _dos.count("%") == 1)
    # 🔴 И Е НАИСТИНА КЪСА. Заковано число тук е нарочно: то е обещанието.
    check("равносметката е под осем реда", len(_dos.split(NL)) <= 8)
    check("обзорът по спортове е чист", banned_word(_t3) is None)
    # 🔴 ОБЪРНАТА 25.08.2026 И НАПРАВЕНА ПОВЕДЕНЧЕСКА. Старата версия
    # твърдеше, че познатите се подреждат отпред — но подаваше Левски (познат)
    # ПРЕДИ Милан (сгрешен), тоест щеше да мине и без никакво подреждане.
    # Зелено, което не мери нищо. Сега подавам сгрешения ПРЪВ и искам редът да
    # се ЗАПАЗИ: бот, който сам вдига собствените си познати нагоре, прави
    # витрина, не обзор.
    _obraten = [({"home": "Милан", "away": "Интер", "pick": "1",
                  "bucket": "football"}, 0, 3, False),
                ({"home": "Левски", "away": "ЦСКА", "pick": "1",
                  "bucket": "football"}, 2, 1, True)]
    _tob = results_text(_now, _obraten, 44, 29)
    check("списъкът НЕ подрежда познатите отпред",
          predi(_tob, "Милан", "Левски"))
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
    # 🔴 ПАЗАЧ СРЕЩУ РАЗМИНАВАНЕ (18.08.2026). Три файла държат по един списък
    # със спортове. Разминат ли се, спортът тихо губи име, емоджи или ред в
    # отчета — точно така amfootball липсваше в SPORT_PATH и щеше да излезе с
    # 📌 наесен. Списъкът се ЧЕТЕ от predictor.py, не се преписва тук.
    # 🔴 ПАЗАЧЪТ СЪДЪРЖАШЕ СОБСТВЕНИЯ СИ ОТГОВОР (намерено 02.09.2026).
    # Дотук редът беше:
    #     _sp = {m for m in SPORT_BG if (...) in _blok}
    # тоест множеството се ПРЕЦЕЖДАШЕ през SPORT_BG и после се питаше дали
    # е подмножество на SPORT_BG. Спорт, който липсва тук, никога не влиза
    # в _sp — значи никога не може да гръмне. Проверката «всеки спорт има
    # българско име» беше УКРАСА: измерено на 02.09 тя даваше зелено, докато
    # еспортът от 01.09 излизаше като «кабарче Esports» — единственият
    # латински надпис сред девет кирилски.
    # ОБЪРНАТА: списъкът се чете от predictor.py и се пита дали ТОЙ се
    # покрива от нашите три карти. Тогава липсващият спорт е този, който
    # гърми.
    #
    # 🥊 ЕДИНСТВЕНОТО ИЗКЛЮЧЕНИЕ. Боксът е в SPORT_ORDER на предсказателя, но
    # НЯМА врата за резултат тук — няма нито boxing_result, нито клон в
    # sport_result. Име без присъда е точно украсата, която ловим: картата
    # ще излиза красиво и ще виси неотсъдена. Затова боксът стои неназован
    # НАРОЧНО, а самото изключение се доказва отделно, малко по-долу — ако
    # някой му напише врата, изключението пада и спортът трябва да получи име.
    _BEZ_PRISYADA = {"boxing"}
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "predictor.py"), encoding="utf-8-sig") as f:
            _psrc = f.read()
        _i = _psrc.find("SPORT_ORDER = [")
        _blok = _psrc[_i:_psrc.find("]", _i)] if _i >= 0 else ""
        # Имената се вадят от ТЕКСТА на чуждия файл, не се прецеждат през
        # нашите карти — това е цялата разлика.
        import re as _re
        _sp = set(_re.findall('"([a-z]+)"', _blok))
        _iskani = _sp - _BEZ_PRISYADA
        check("списъкът със спортове се прочете от predictor", len(_sp) >= 10)
        check("всеки спорт има път и емоджи", not (_iskani - set(SPORT_PATH)))
        check("всеки спорт има ред в отчета", not (_iskani - set(SPORT_RED)))
        check("всеки спорт има българско име", not (_iskani - set(SPORT_BG)))
        check("изключенията са спортове, а не измислени думи",
              not (_BEZ_PRISYADA - _sp))
        check("изключението е едно-единствено", len(_BEZ_PRISYADA) <= 1)
    except Exception as e:                                   # noqa: BLE001
        bad.append("не мога да сверя списъците със спортове: " + str(e)[:40])
    check("непознат спорт пак получава име", sport_ime("нещо") == "НЕЩО")
    # Дубликат: същият мач, същият резултат, вписан два пъти в дневника.
    _dubl = _mix + [({"home": "Левски", "away": "ЦСКА", "pick": "1",
                      "bucket": "football"}, 2, 1, True)]
    _td = results_text(_now, _dubl, 44, 29, {}, _dnevnik)
    check("дублираният мач се показва ВЕДНЪЖ", _td.count("Левски") == 1)
    check("дублирането не мени числото на реда", "Футбол <b>1 от 2</b>" in _td)
    # 🔴 ДВЕТЕ КАРТИ ОТ ЕДИН МАЧ НЕ СЕ СЛИВАТ. Победителят и тоталът са
    # различни твърдения — всяко със своя присъда и свое място в числото.
    _dve = _mix + [({"home": "Левски", "away": "ЦСКА", "pick": "Над 2.5 гола",
                     "bucket": "football"}, 2, 1, True)]
    _td2 = results_text(_now, _dve, 44, 29, {}, _dnevnik)
    # 🔴 ОБЪРНАТА 25.08.2026 (ДЕФЕКТ B). Дотук проверката ПАЗЕШЕ това, че мачът
    # се изписва ДВА ПЪТИ — веднъж за победителя, веднъж за тотала. Точно това
    # човекът чете като „ботът се повтаря". Сега пази обратното: един мач —
    # един блок, ДВАТА избора вътре. И веднага под нея стои проверката, че
    # СМЕТКАТА не е пипната: двата пазара пак се броят за две прогнози.
    check("мачът с два пазара се изписва ВЕДНЪЖ", _td2.count("Левски") == 1)
    check("но и двата избора се виждат",
          "Над 2.5 гола" in _td2 and _td2.count("✅") >= 2)
    check("двете карти пак броят като ДВЕ", "Футбол <b>2 от 3</b>" in _td2)
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
    # 🔴 ОБЪРНАТА 26.08.2026. Искаше „0 от 1 фиша минаха“ — при ЕДИН фиш
    # това е крив български и проверката точно него пазеше. Нулата
    # вече си има изречение, в което няма какво да се сгреши.
    check("обзорът брои минали фишове", "Нито един фиш не мина." in c)
    check("нулата при няколко фиша ги брои",
          "Нито един от 2 фиша не мина." in combo_text(
              _now, [((1, "2026-08-09"), _legs),
                     ((2, "2026-08-10"), _legs)]))
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

    # 🔴 ОБНОВЕНА 26.08.2026. Пътят се смени: main вече не вика post()
    # направо, а през combo_prati — затова иглата гледа двете му части.
    check("отчетът на фишовете отива в стая 10",
          ("post(WINS" + "_THREAD, text)") in _iztochnik)
    check("отчетът се сглобява от combo_text",
          ("combo" + "_text(now, gotovi)") in _iztochnik)
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

    # --- 🔴 МАРКАТА СЛЕД ПРАЩАНЕТО, НЕ ПРЕДИ НЕГО (26.08.2026).
    # Дотук main() вдигаше марката на всеки крак ПРЕДИ post(): паднеше ли
    # пращането, отчетът на фиша беше изгубен завинаги, защото марката
    # твърдеше, че е минал. Проверките пазят И ДВЕТЕ посоки: марка без
    # успех (загуба) и вечен опит без таван (наводнение).
    _l1 = [{"combo": 1, "scored": True, "hit": True}]
    check("провалено пращане НЕ маркира фиша",
          combo_marki(False, _l1) == (0, 1)
          and not _l1[0].get("combo_done"))
    check("проваленото пращане брои опита", _l1[0].get("combo_opiti") == 1)
    _l2 = [{"combo": 1, "scored": True, "hit": True}]
    check("успешното пращане маркира фиша",
          combo_marki(True, _l2) == (1, 0)
          and _l2[0].get("combo_done") is True)
    _l3 = [{"combo": 1, "scored": True, "hit": True, "combo_opiti": 3}]
    combo_marki(True, _l3)
    check("успехът изчиства брояча на опитите", "combo_opiti" not in _l3[0])
    # И ОБРАТНАТА ПОСОКА: опитите НЕ са безкрайни.
    _l4 = [{"combo": 1, "scored": True, "hit": True}]
    for _i in range(COMBO_OPITI - 1):
        combo_marki(False, _l4)
    check("преди тавана кракът още чака нов опит",
          COMBO_OPITI == 1 or (not _l4[0].get("combo_done")
                               and _l4[0].get("combo_opiti") == COMBO_OPITI - 1))
    combo_marki(False, _l4)
    check("на тавана оценителят се предава, не опитва вечно",
          _l4[0].get("combo_done") is True)
    check("таванът на опитите е ръчка, не заковано число",
          ("SCORE_COMBO" + "_OPITI") in _iztochnik)
    check("таванът на отчетите е ръчка, не заковано число",
          ("SCORE_COMBO" + "_TAVAN") in _iztochnik)
    # Отчетът е ИНКРЕМЕНТАЛЕН: таванът му НЕ бива да е този на
    # равносметките (3), иначе четвъртият фиш за деня изчезва мълчаливо.
    check("таванът на отчетите е над този на равносметките", COMBO_TAVAN >= 8)

    # --- И РЕДЪТ В ЖИВИЯ main(), не само в чистата функция.
    # Копчето сено е БЕЗ самопроверката, тоест иглата се намира само в
    # живия код (виж _bez_samoproverkata).
    _opashka = _iztochnik.split("if gotovi:")[-1]
    check("main вече не вдига марката на фиша сам",
          ("combo" + "_done\"] = True") not in _opashka)
    check("марките падат през combo_marki", ("combo" + "_marki(") in _opashka)
    check("пращането стои ПРЕД марките",
          ("combo" + "_prati(") in _opashka
          and ("combo" + "_marki(") in _opashka
          and _opashka.index("combo" + "_prati(")
          < _opashka.index("combo" + "_marki("))
    # Вратата на фиша ползва СЪЩИЯ втори тефтер като равносметката.
    _telo_cp = _iztochnik.split("def combo" + "_prati(")[-1][:3000]
    check("отчетът минава през пазача на будилника",
          "ravn_reshi(" in _telo_cp and "ravn_otbelezhi(" in _telo_cp)
    check("сухото пускане не заключва истинския отчет",
          "DRY_RUN" in _telo_cp.split("ravn_otbelezhi(")[0])

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
    # 🥊 ММА — вратата, отворена на 12.08.2026. Дотук спортът пускаше карти,
    # които НЕ МОГАТ да бъдат отсъдени: пет записа, нула присъди, нула slug.
    # Тестът работи върху подхвърлена гала, БЕЗ мрежа.
    _stara_gala = globals().get("_mma_gala")
    try:
        globals()["_mma_gala"] = lambda liga, ymd: (
            {frozenset(("111", "222")): ("111", ["111", "222"])}
            if (liga == "ufc" and ymd == "20260811") else {})
        _b = {"bucket": "mma", "day": "2026-08-12", "home_id": "111", "away_id": "222"}
        check("боят се намира и в предния ден", mma_result(_b) == (1, 0))
        check("победата на домакина е 1:0", mma_result(_b)[0] > mma_result(_b)[1])
        _b2 = dict(_b, home_id="222", away_id="111")
        check("обърнатите бойци дават обърнат резултат", mma_result(_b2) == (0, 1))
        check("непознат бой не се отсъжда",
              mma_result(dict(_b, home_id="999")) is None)
        check("бой без id не се отсъжда", mma_result({"bucket": "mma",
                                                      "day": "2026-08-12"}) is None)
        check("бой без ден не се отсъжда",
              mma_result({"bucket": "mma", "home_id": "111", "away_id": "222"}) is None)
        check("боклук вместо ден не гърми",
              mma_result(dict(_b, day="абв")) is None)
        # Равен или отменен бой: ESPN дава winner=False и на двамата. По-добре
        # мълчание, отколкото измислена присъда.
        globals()["_mma_gala"] = lambda liga, ymd: {}
        check("равен/отменен бой не се отсъжда", mma_result(_b) is None)
    finally:
        if _stara_gala is not None:
            globals()["_mma_gala"] = _stara_gala
    check("ММА минава през своята врата",
          ('if b == "mma"' in _iztochnik_scorer
           and "return mma" + "_result(rec)" in _iztochnik_scorer))
    check("ММА НЕ е обявен за спорт без източник", "mma" not in NO_RESULT)
    check("питат се седем лиги", len(MMA_LIGI) == 7)
    # 🎮 ЕЛЕКТРОННИТЕ СПОРТОВЕ. Нито една от тези проверки не пуска заявка:
    # всяка спира ПРЕДИ мрежата — на липсващо име, на непозната игра или на
    # счупен ден. Врата без проверка е врата, за която узнаваш, че е зазидана,
    # чак когато цяла стая е висяла седмица неотсъдена.
    check("еспортът минава през своята врата",
          ('if b == "esports"' in _iztochnik_scorer
           and "return esport" + "_result(rec)" in _iztochnik_scorer))
    check("esports НЕ е обявен за спорт без източник",
          "esports" not in NO_RESULT)
    _e = {"bucket": "esports", "src": "esport", "day": "2026-08-31",
          "igra": "cs2", "league": "CS2 · Проба"}
    check("еспорт без имена не се отсъжда",
          esport_result(dict(_e, home="", away="")) is None)
    check("еспорт без гост не се отсъжда",
          esport_result(dict(_e, home="MOUZ", away="")) is None)
    check("еспорт с боклук вместо ден не гърми",
          esport_result(dict(_e, home="MOUZ", away="G2", day="абв")) is None)
    check("еспорт без игра и без разпознаваема лига мълчи",
          esport_result(dict(_e, home="MOUZ", away="G2", igra="",
                             league="Esports · Проба")) is None)
    # 🔴 VALORANT НЯМА ИЗВОР. Оставено нарочно като проверка, а не като
    # коментар: сложи ли се някога valorant в картата, тази проверка ще падне
    # и ще накара някого да ИЗМЕРИ, вместо да предположи, че работи.
    check("valorant се разпознава като БЕЗ извор",
          esport_result(dict(_e, home="LOUD", away="MIBR", igra="",
                             league="Valorant · Champions Tour")) is None)

    # 🔴 СВЕРКА С ПРЕДСКАЗАТЕЛЯ. Пусне ли той лига, която оценителят не пита,
    # боевете от нея висят вечно. Списъкът се чете от неговия код, не се
    # преписва — препис се разминава мълчаливо.
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "predictor.py"), encoding="utf-8-sig") as f:
            _psrc = f.read()
        _marker = "MMA_LEAGUES_VSI = ["
        _i = _psrc.find(_marker)
        _blok = _psrc[_i:_psrc.find("]", _i)] if _i >= 0 else ""
        _pl = {m for m in MMA_LIGI if ('"' + m + '"') in _blok}
        check("оценителят пита ВСЯКА лига, която предсказателят пуска",
              _i >= 0 and len(_pl) == len(MMA_LIGI))
        _lipsva = [x for x in ("ufc", "pfl", "bellator", "rizin", "ksw", "lfa",
                               "cage-warriors") if ('"' + x + '"') not in _blok]
        check("нито една лига не е само от едната страна", not _lipsva)
    except Exception as e:                                   # noqa: BLE001
        bad.append("не мога да сверя ММА лигите с predictor.py: " + str(e)[:40])

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
    # 🔴 ЧУЖДАТА ФОРМА — ПОВЕДЕНЧЕСКИ, НЕ ПО ТЕКСТ (26.08.2026).
    # Проверката пита какво ИЗЛИЗА, а не дали нещо е вързано в кода.
    # Старият пазач за сентинела беше зелен върху счупен файл точно
    # защото проверяваше връзването, а смъртта ставаше по-рано.
    check("низ вместо списък не гърми (истинският отговор на SDB)",
          _sdb_dvoyki("Invalid Team ID passed") == [])
    check("речник вместо списък не гърми", _sdb_dvoyki({"a": 1}) == [])
    check("списък от низове не гърми", _sdb_dvoyki(["abc", "def"]) == [])
    check("число не гърми", _sdb_dvoyki(42) == [])
    check("списък с речник И боклук взима само речника",
          _sdb_dvoyki([{"idHomeTeam": "1", "idAwayTeam": "2",
                        "intHomeScore": "3", "intAwayScore": "1"}, "боклук"])
          == [("1", "2", 3, 1, None, None)])

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

    # 💰 ДОХОДНОСТ И CLV (18.08.2026)
    def _z(hit, cena, clv=None, v=2):
        d = {"scored": True, "hit": hit, "pazar_cena": cena, "pazar_v": v,
             "bucket": "baseball", "p": 0.55, "pazar_p": 0.54}
        if clv is not None:
            d["pazar_clv"] = clv
        return d

    check("малка извадка мълчи", dohodnost([_z(True, 2.0)] * 5)[0] == [])
    # Равен залог, цена 2.00, точно половината познати -> нула доходност.
    _rav = [_z(True, 2.0) for _ in range(20)] + [_z(False, 2.0) for _ in range(20)]
    _rd, _rn = dohodnost(_rav)
    check("40 залога стигат за число", _rn == 40 and _rd != [])
    check("цена 2.00 и 50% познати дават НУЛА",
          any("+0.0%" in x or "-0.0%" in x for x in _rd))
    # 69% познати на цена 1.30 ГУБИ — това е целият смисъл на реда.
    _slab = [_z(True, 1.30) for _ in range(69)] + [_z(False, 1.30) for _ in range(31)]
    _sd, _ = dohodnost(_slab)
    check("69% на цена 1.30 излиза ОТРИЦАТЕЛНО",
          any("-" in x and "доходност" in x for x in _sd))
    check("същите 69% не са отрицателни на цена 1.60",
          not any("-" in x and "доходност" in x
                  for x in dohodnost([_z(True, 1.60) for _ in range(69)]
                                     + [_z(False, 1.60) for _ in range(31)])[0]))
    check("стар запис без знак за версия не се брои",
          dohodnost([_z(True, 2.0, None, 1) for _ in range(60)])[1] == 0)
    check("запис без цена не се брои",
          dohodnost([dict(_z(True, 2.0), pazar_cena=None) for _ in range(60)])[1] == 0)

    check("малка извадка за CLV мълчи", clv_text([_z(True, 2.0, 0.03)] * 3)[0] == [])
    _cl, _cn = clv_text([_z(True, 2.0, 0.03) for _ in range(15)]
                        + [_z(False, 2.0, -0.01) for _ in range(10)])
    check("CLV брои двете посоки", _cn == 25
          and any("15" in x for x in _cl) and any("10" in x for x in _cl))
    check("средното движение се изписва в точки",
          any("точки" in x for x in _cl))
    check("CLV пренебрегва запис без движение",
          clv_text([_z(True, 2.0) for _ in range(40)])[1] == 0)

    # 🔴 НОВИЯТ РАЗДЕЛ ДА НЕ УБИВА СЪОБЩЕНИЕТО. Портиерът реже цялото
    # съобщение при една забранена дума. Ако утре някой напише „коефициент"
    # в реда за доходността, вечерната равносметка спира ЦЯЛАТА — мълчаливо.
    _sekcia = " ".join(dohodnost([_z(True, 2.0) for _ in range(30)]
                                 + [_z(False, 2.0) for _ in range(30)])[0]
                       + clv_text([_z(True, 2.0, 0.02) for _ in range(30)])[0])
    check("разделът за доходността минава през портиера",
          banned_word(_sekcia) is None)
    check("разделът наистина има какво да каже", len(_sekcia) > 40)

    check("обхватът брои и отсъдените без цена",
          pokritie([_z(True, 2.0), {"scored": True, "hit": True}]) == (1, 2))
    check("невисящите не влизат в обхвата",
          pokritie([{"scored": False}]) == (0, 0))

    # 🔴 ЗАТВАРЯЩАТА ЦЕНА — БЕЗ МРЕЖА, С ПОДХВЪРЛЕН ПАЗАР.
    #
    # Първата ми версия на тези проверки минаваше, защото ИСТИНСКАТА заявка към
    # ESPN за измислен номер връщаше нищо. Тоест тестът беше зелен по грешна
    # причина И правеше мрежово повикване насред самопроверката. Мутация,
    # която маха пазача „вече хваната", го преживя без да мигне.
    try:
        import pazar as _PZ
    except Exception:                                        # noqa: BLE001
        _PZ = None
    check("пазарът се внася", _PZ is not None)
    if _PZ is not None:
        _star_z = _PZ.cena_zatvarayashta
        try:
            _PZ.cena_zatvarayashta = lambda sp, lg, ev: (1.80, 2.10, 3.40)
            _nov = {"pazar_cena": 2.00, "pazar_ev": "1", "pazar_sport": "baseball",
                    "pazar_liga": "mlb", "pick": "1 · Домакин"}
            check("затварящата се хваща",
                  hvani_zatvaryashta(_nov) is True and _nov.get("pazar_close") == 1.80)
            check("поевтиняването дава положително движение",
                  float(_nov.get("pazar_clv") or 0) > 0)
            _ima = {"pazar_cena": 2.00, "pazar_close": 1.95, "pazar_ev": "1",
                    "pazar_sport": "baseball", "pazar_liga": "mlb", "pick": "1 · А"}
            check("вече хваната НЕ се пипа втори път",
                  hvani_zatvaryashta(_ima) is False and _ima["pazar_close"] == 1.95)
            _g2 = {"pazar_cena": 2.00, "pazar_ev": "1", "pazar_sport": "baseball",
                   "pazar_liga": "mlb", "pick": "2 · Гост"}
            hvani_zatvaryashta(_g2)
            check("изборът 2 взима цената на ГОСТА", _g2.get("pazar_close") == 2.10)
            _gx = {"pazar_cena": 2.00, "pazar_ev": "1", "pazar_sport": "soccer",
                   "pazar_liga": "x", "pick": "Х · равен"}
            hvani_zatvaryashta(_gx)
            check("изборът Х взима цената на РАВЕНСТВОТО",
                  _gx.get("pazar_close") == 3.40)
            _gp = {"pazar_cena": 2.00, "pazar_ev": "1", "pazar_sport": "baseball",
                   "pazar_liga": "mlb", "pick": "Над 8.5 рънa"}
            check("непознат избор не получава чужда цена",
                  hvani_zatvaryashta(_gp) is False and "pazar_close" not in _gp)
            check("без цена при пускане не се търси затваряща",
                  hvani_zatvaryashta({"pazar_ev": "1", "pazar_sport": "baseball",
                                      "pazar_liga": "mlb", "pick": "1 · А"}) is False)
            check("без адрес не се търси затваряща",
                  hvani_zatvaryashta({"pazar_cena": 2.0, "pick": "1 · А"}) is False)
        finally:
            _PZ.cena_zatvarayashta = _star_z

    # 🔴 ОТЛОЖЕН МАЧ (19.08.2026) — намерено с четене на живия дневник:
    # „Braga — Gil Vicente" от 16.08 висеше ТРЕТИ ДЕН в „чакат резултат",
    # а мачът е отложен и резултат няма да има.
    check("отложеното се разпознава",
          espn_otlozhen({"name": "STATUS_POSTPONED"}) is True)
    check("отмененото се разпознава",
          espn_otlozhen({"name": "STATUS_CANCELED"}) is True)
    check("прекъснатото се разпознава",
          espn_otlozhen({"description": "Suspended"}) is True)
    check("завършеното НЕ е отложено",
          espn_otlozhen({"name": "STATUS_FINAL", "state": "post"}) is False)
    check("предстоящото НЕ е отложено",
          espn_otlozhen({"name": "STATUS_SCHEDULED", "state": "pre"}) is False)
    check("боклук не гърми",
          espn_otlozhen(None) is False and espn_otlozhen("низ") is False)
    check("сентинелът е обект, не низ", not isinstance(OTLOZHEN, str))
    # 🔴 НАЙ-ВАЖНОТО: клонът трябва да е ВЪРЗАН в главния цикъл. Без него
    # сентинелът стига до разопаковането на резултата и рънът ГРЪМВА.
    #
    # ПРОВЕРКАТА Е ПРЕЗ РАЗБОР НА КОДА, НЕ ПРЕЗ ТЪРСЕНЕ НА ТЕКСТ. Три пъти
    # днес се хванах в един и същи капан: иглата, която търся, стоеше в
    # собствения ми коментар до нея, и проверката падаше върху ЧИСТ файл.
    # Разборът вижда СТРУКТУРАТА — коментарите не го лъжат.
    import ast as _ast
    _dyrvo = _ast.parse(open(__file__, encoding="utf-8").read())
    _sravnenia, _prichini = [], []
    for _n in _ast.walk(_dyrvo):
        if isinstance(_n, _ast.Compare):
            _l, _r = _n.left, (_n.comparators or [None])[0]
            if (isinstance(_l, _ast.Name) and _l.id == "res"
                    and isinstance(_r, _ast.Name) and _r.id == "OTLOZHEN"):
                _sravnenia.append(_n.lineno)
        if isinstance(_n, _ast.Constant) and isinstance(_n.value, str)                 and "отложен или отменен" in _n.value:
            _prichini.append(_n.lineno)
    _razopakovane = [_n.lineno for _n in _ast.walk(_dyrvo)
                     if isinstance(_n, _ast.Assign)
                     and isinstance(_n.targets[0], _ast.Tuple)
                     and isinstance(_n.value, _ast.Name) and _n.value.id == "res"]
    check("отложеното се сравнява някъде в кода", len(_sravnenia) >= 1)
    check("сравнението е ПРЕДИ разопаковането на резултата",
          bool(_sravnenia) and bool(_razopakovane)
          and min(_sravnenia) < min(_razopakovane))
    check("затварянето слага честна причина", len(_prichini) >= 1)

    # ══════════════════════════════════════════════════════════════════════
    # 🔴 КРАШЪТ, КОЙТО УБИ ОЦЕНИТЕЛЯ ЗА 33 ЧАСА (23-25.08.2026)
    #
    # tennis_day() е обявена да връща СПИСЪК, а връщаше сентинела OTLOZHEN,
    # щом в таблото за деня има ПОНЕ ЕДИН отложен мач — чий да е. Извикващият
    # я обхожда:  for na, nb, pa, pb in tennis_day(day)
    # → TypeError: object is not iterable, и целият рън умираше. score.yml
    # гръмна три пъти подред: #59, #60, #61 (23.08 19:44 - 24.08 19:54).
    #
    # ЗАЩО НИТО ЕДНА ОТ 377-те ПРОВЕРКИ НЕ ГО ХВАНА (измерено днес): едно-
    # единственото място, което пипаше tennis_day(), му подаваше ден
    # „1999-01-01". Пуснах го с шпионин върху http_json: 6 истински заявки
    # до ESPN, всяка с НУЛА събития. Тоест тялото на цикъла не се изпълняваше
    # НИТО ВЕДНЪЖ и клонът за отложен мач беше недостижим.
    #
    # Затова тук мрежата се ПОДХВЪРЛЯ: таблото е наше, отговорът е известен,
    # нищо не излиза навън и клонът се стига при всяко пускане.
    _TEN_DEN, _TEN_YMD = "2026-08-24", "20260824"
    _GOTOV = {"name": "STATUS_FINAL", "state": "post", "completed": True}
    _OTLOZH = {"name": "STATUS_POSTPONED", "state": "post", "completed": False}

    def _igrach(ime, gemove, pobedil):
        return {"athlete": {"displayName": ime},
                "linescores": [{"value": g} for g in gemove],
                "winner": pobedil}

    def _ten_mach(ia, ib, ga, gb, stat, pobedil=1):
        return {"status": {"type": stat},
                "competitors": [_igrach(ia, ga, pobedil == 1),
                                _igrach(ib, gb, pobedil == 2)]}

    def _ten_tablo(machove):
        # Както ESPN наистина ги дава: ev["competitions"] е ПРАЗЕН, мачовете
        # живеят в ev["groupings"][i]["competitions"].
        return {"events": [{"competitions": [],
                            "groupings": [{"competitions": list(machove)}]}]}

    def _otb_mach(hid, aid, hs, as_, stat):
        return {"competitions": [{"status": {"type": stat}, "competitors": [
            {"team": {"id": hid}, "score": hs},
            {"team": {"id": aid}, "score": as_}]}]}

    # 🔴 ЧУЖДИЯТ ОТЛОЖЕН МАЧ СТОИ ПЪРВИ. Точно този ред събори бота: старият
    # код се предаваше на първия отложен и никога не стигаше до нашия.
    _TABLO_TENIS = _ten_tablo([
        _ten_mach("Джокович", "Медведев", [], [], _OTLOZH, pobedil=0),
        _ten_mach("Алкарас", "Синер", [6, 6], [4, 3], _GOTOV)])
    _TABLO_OTBORI = {"events": [
        _otb_mach("777", "778", None, None, _OTLOZH),
        _otb_mach("111", "222", "2", "1", _GOTOV)]}
    _PITANI = []

    def _falshiva_mreza(url, timeout=25):
        """ESPN без ESPN. Пази и КАКВО е било питано — тестът да не е празен."""
        _PITANI.append(url)
        if "/tennis/atp/" in url and _TEN_YMD in url:
            return _TABLO_TENIS
        if "/soccer/" in url and _TEN_YMD in url:
            return _TABLO_OTBORI
        return {"events": []}

    def _bez_grum(mysal):
        """Стойността — или знакът „ГРЪМНА". Крашът трябва да е ЧЕРВЕНА
        проверка, не трасе: трасето събаря самопроверката и скрива всичко
        след себе си. Измерено на 25.08.2026: мутацията „return OTLOZHEN"
        в tennis_day уби ЦЕЛИЯ пакет с TypeError вместо да даде „счупено" —
        девет проверки просто изчезнаха. С този помощник същата мутация дава
        девет ЧЕРВЕНИ реда."""
        try:
            return mysal()
        except Exception as _e:                              # noqa: BLE001
            return "ГРЪМНА: " + type(_e).__name__

    _star_http = globals()["http_json"]
    globals()["http_json"] = _falshiva_mreza
    _ten_days.clear()
    try:
        _spisak = tennis_day(_TEN_DEN)
        # 🔴 БЕЗ len() ВЪРХУ НЕПРОВЕРЕНО. Мутацията „return OTLOZHEN" прави
        # _spisak обект без дължина — len() би хвърлил и би отнесъл ЦЯЛАТА
        # самопроверка, скривайки всичко след себе си (същият капан като
        # .index()). Затова първо „списък ли е", и чак после — колко е дълъг.
        _bezopasen = _spisak if isinstance(_spisak, list) else []
        check("тенис-таблото връща СПИСЪК, не сентинела",
              isinstance(_spisak, list))
        check("в списъка влизат И ДВАТА мача — изиграният и отложеният",
              len(_bezopasen) == 2)
        # ⬇️ ТОЧНО ТОВА ПАДАШЕ ЖИВО: разопаковането на върнатото.
        _grumna = ""
        try:
            for _na, _nb, _pa, _pb in tennis_day(_TEN_DEN):
                pass
        except TypeError as _e:                              # noqa: BLE001
            _grumna = str(_e)[:60]
        check("обхождането на върнатото НЕ гърми", _grumna == "")
        check("отложеният влиза с ПРАЗЕН резултат — това е знакът му",
              [(_x[2], _x[3]) for _x in _bezopasen if _x[0] == "Джокович"]
              == [(None, None)])
        _nash = {"bucket": "tennis", "home": "Алкарас", "away": "Синер",
                 "day": _TEN_DEN, "pick": "1 · Алкарас"}
        check("нашият изигран мач се отсъжда ВЪПРЕКИ чуждия отложен",
              _bez_grum(lambda: tennis_result(_nash)) == (2, 0))
        check("и през главната врата sport_result излиза същото",
              _bez_grum(lambda: sport_result(_nash)) == (2, 0))
        check("обърнатият ред дава обърнат резултат",
              _bez_grum(lambda: tennis_result(
                  dict(_nash, home="Синер", away="Алкарас"))) == (0, 2))
        check("НАШИЯТ отложен мач връща сентинела",
              _bez_grum(lambda: tennis_result(
                  {"bucket": "tennis", "home": "Джокович",
                   "away": "Медведев", "day": _TEN_DEN,
                   "pick": "1 · Джокович"})) is OTLOZHEN)
        # ── СЪЩИЯТ КАПАН ПРИ ОТБОРНИТЕ СПОРТОВЕ. Таблото носи цялата лига
        # за деня; проверката „отложен ли е" трябва да дойде СЛЕД „наш ли е".
        _otb = {"bucket": "football", "slug": "eng.1", "home_id": "111",
                "away_id": "222", "day": _TEN_DEN, "pick": "1 · Домакин"}
        check("чужд отложен мач НЕ затваря нашата отборна карта",
              _bez_grum(lambda: espn_result(_otb)) == (2, 1))
        check("и отборната карта излиза същата през sport_result",
              _bez_grum(lambda: sport_result(_otb)) == (2, 1))
        check("НАШИЯТ отложен отборен мач връща сентинела",
              _bez_grum(lambda: espn_result(
                  dict(_otb, home_id="777", away_id="778"))) is OTLOZHEN)
        # Проверка срещу празен тест: подхвърленото табло трябва НАИСТИНА
        # да е било питано — и двете, тенис и отборно. Нула прегледани се
        # чете като нула проблеми, а това вече ни е хапало.
        check("подхвърленото тенис табло НАИСТИНА е питано",
              any("/tennis/" in _u for _u in _PITANI))
        check("подхвърленото отборно табло НАИСТИНА е питано",
              any("/soccer/" in _u for _u in _PITANI))
    finally:
        globals()["http_json"] = _star_http
        _ten_days.clear()

    # 🗄️ Архивът. Мести се само ПРИКЛЮЧЕНО; висящото остава, колкото и старо.
    _sega_a = datetime(2026, 8, 18, tzinfo=SOFIA)
    _r = [{"posted": "2026-01-05 10:00", "scored": True, "hit": True},
          {"posted": "2026-01-07 10:00", "scored": False},
          {"posted": "2026-08-17 10:00", "scored": True, "hit": True}]
    _st = DRY_RUN
    try:
        globals()["DRY_RUN"] = True          # без запис по диска
        _g, _n = arhiviray(_r, _sega_a)
        check("при сухо пускане нищо не се мести", _n == 0 and len(_g) == 3)
    finally:
        globals()["DRY_RUN"] = _st
    _star_p = str(ARHIV_DNI)
    check("прагът е разумен", 30 <= ARHIV_DNI <= 400)
    check("архивът е отделен файл", ARHIV_FILE != LOG_FILE)
    check("липсващ архив не гърми", isinstance(cheti_arhiv(), list))

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
    # ═══════════ 🏓 ДВЕТЕ МАЛКИ ЛИГИ: ИМА ЛИ ПЪТ ДО ПРИСЪДА (26.08.2026)
    #
    # Мрежа НЕ се пипа: подменя се САМО tt_ligi._MREZHA[0] — единственият шев
    # към света — и през проверката минава ИСТИНСКИЯТ път: разпределяне по
    # лига, tt_ligi.rezultat, огледалната сверка и накрая verdict().
    check("лигите тенис на маса са вързани в оценителя", TTL is not None)
    check("разпределянето е по ЛИГА, не по кош",
          "tt_liga_klyuch(rec)" in _iztochnik_scorer
          and "return tt_liga_result(rec)" in _iztochnik_scorer)
    check("WTT си остава на своя път", "return wtt_result(rec)" in _iztochnik_scorer)
    if TTL is not None:
        _tt_star_mr = TTL._MREZHA[0]
        _tt_star_ev = globals().get("_wtt_events")
        _tt_star_ttl = globals().get("TTL")
        try:
            TTL._MREZHA[0] = TTL._falshiva_mrezha
            TTL.izchisti_kesh()
            TTL._FALSHIVI.clear()
            # WTT да не пипа мрежата в тази обиколка: празен календар значи
            # „няма турнир за деня" и wtt_result излиза преди първата заявка.
            globals()["_wtt_events"] = []

            def _tt_rec(h, a, lg="Czech Liga Pro", pick=None, **kw):
                r = {"bucket": "tabletennis", "home": h, "away": a,
                     "league": lg, "day": "2026-08-25",
                     "pick": pick if pick else ("1 · " + h)}
                r.update(kw)
                return r

            # Хартиената книга казва: „Jan Szotkowski vs Tadeas Zika" = 1-3.
            check("свършил чешки мач се отсъжда",
                  sport_result(_tt_rec("Jan Szotkowski", "Tadeas Zika")) == (1, 3))
            # 🔴 ОБЪРНАТИЯТ ЗАПИС. Присъдата трябва да Е огледална, защото
            # огледален е ВЪПРОСЪТ — а не да е същата.
            check("обърнатият запис получава обърната присъда",
                  sport_result(_tt_rec("Tadeas Zika", "Jan Szotkowski")) == (3, 1))
            check("обърнатият запис по НОМЕР също не е огледален",
                  sport_result(_tt_rec("Tadeas Zika", "Jan Szotkowski",
                                       slug="1001")) == (3, 1)
                  and sport_result(_tt_rec("Jan Szotkowski", "Tadeas Zika",
                                           slug="1001")) == (1, 3))
            check("полската лига минава по същия път",
                  sport_result(_tt_rec("Grzegorz Marud", "Kaczynski Piotr",
                                       "TT Elite Series")) == (3, 1))
            check("подзаглавието след средната точка не крие лигата",
                  sport_result(_tt_rec("Jan Szotkowski", "Tadeas Zika",
                                       "Czech Liga Pro · Men")) == (1, 3))
            check("отмененият мач връща сентинела за отложен",
                  sport_result(_tt_rec("Michal Vesely", "Daniel Tuma")) is OTLOZHEN)
            # 🔴 ЗНАЕ СЕ КОЙ, НЕ СЕ ЗНАЕ С КОЛКО. Чуждият сентинел НЕ бива да
            # стигне до главния цикъл: там го чака „hs, as_ = res".
            check("победител без сетове не става присъда",
                  sport_result(_tt_rec("Samo Pobeditel", "Bez Setove")) is None)
            check("непознат мач не се отсъжда",
                  sport_result(_tt_rec("Nyakoy Nikoy", "Vtori Nikoy")) is None)
            # Присъдата стига до verdict() в ДВЕТЕ посоки.
            _tt_p = _tt_rec("Jan Szotkowski", "Tadeas Zika")
            check("сгрешен избор = невярно", verdict(_tt_p, 1, 3) is False)
            check("познат избор = вярно",
                  verdict(dict(_tt_p, pick="2 · Tadeas Zika"), 1, 3) is True)

            # 🔴 ЗАПУШЕН ИЗВОР НЕ Е „НЯМА". Мъртва мрежа -> ZAPUSHENO, а той е
            # ЛЪЖЛИВО ИСТИНЕН обект: без този пласт „hs, as_ = res" гърми.
            TTL.izchisti_kesh()
            TTL._FALSHIVI["myrtva"] = True
            check("мъртва мрежа не ражда присъда",
                  sport_result(_tt_rec("Jan Szotkowski", "Tadeas Zika")) is None)
            check("мъртва мрежа не ражда и „отложен“",
                  sport_result(_tt_rec("Michal Vesely", "Daniel Tuma"))
                  is not OTLOZHEN)
            TTL._FALSHIVI.pop("myrtva", None)
            TTL.izchisti_kesh()

            # 🔴 БЛИЗНАКЪТ. Паднал САМО адресът на самото събитие: tt_ligi
            # връща чуканче с name=None и НЕ може да поправи посоката —
            # тоест дава ЕДИН И СЪЩ отговор за двете страни. Първо се
            # доказва, че лъжата наистина идва оттам, после че тук спира.
            _sliap_adres = TTL.SM + "/events/1001/"

            def _sliapa(url):
                if url == _sliap_adres:
                    return None
                return TTL._falshiva_mrezha(url)

            TTL._MREZHA[0] = _sliapa
            TTL.izchisti_kesh()
            _s1 = TTL.rezultat({"slug": "1001", "home": "Jan Szotkowski",
                                "away": "Tadeas Zika", "day": "2026-08-25"})
            TTL.izchisti_kesh()
            _s2 = TTL.rezultat({"slug": "1001", "home": "Tadeas Zika",
                                "away": "Jan Szotkowski", "day": "2026-08-25"})
            check("сляпото петно наистина дава ЕДНО И СЪЩО за двете посоки",
                  _s1 == (1, 3) and _s2 == (1, 3))
            TTL.izchisti_kesh()
            check("оценителят НЕ приема сляпата присъда",
                  sport_result(_tt_rec("Tadeas Zika", "Jan Szotkowski",
                                       slug="1001")) is None)
            TTL.izchisti_kesh()
            check("сляпата присъда не минава и в правилната посока",
                  sport_result(_tt_rec("Jan Szotkowski", "Tadeas Zika",
                                       slug="1001")) is None)
            TTL._MREZHA[0] = TTL._falshiva_mrezha
            TTL.izchisti_kesh()

            # 🔴 WTT НЕ СМЕЕ ДА МИНЕ ОТТУК. Мери се с брояча на хартиената
            # мрежа: WTT запис не бива да я докосне НИТО ВЕДНЪЖ.
            TTL._FALSHIVI["vikan"] = 0
            _wtt_lg = "WTT Feeder Olomouc 2026 · Men's Singles"
            _wtt_rec = {"bucket": "tabletennis", "home": "Adam", "away": "Boris",
                        "day": "2026-08-25", "league": _wtt_lg,
                        "pick": "1 · Adam"}
            check("WTT картата НЕ тръгва към лигите",
                  tt_liga_klyuch(_wtt_rec) is None)
            check("WTT картата не се отсъжда от лигите",
                  _bez_grum(lambda: sport_result(_wtt_rec)) is None)
            # 🔴 И ОБРАТНОТО, ЗАЩОТО ЕДНАТА ПОЛОВИНА НЕ Е ПРОВЕРКА.
            # „Не влиза в лигите" и „стига до своя съдия" са две различни
            # твърдения: разпределяне, което праща ВСИЧКО към лигите, минава
            # първото (лигите връщат None) и убива WTT — измерено с мутация,
            # която оцеля точно тук. Затова се подхвърля един мач в указателя
            # на WTT (мрежа НЕ се пипа) и се иска присъдата да излезе ОТТАМ.
            _wtt_index[9998] = {frozenset(("adam", "boris")): ("adam", 3, 1)}
            globals()["_wtt_events"] = [(9998, "2026-08-25", "2026-08-25")]
            check("WTT картата стига до своя съдия",
                  _bez_grum(lambda: sport_result(_wtt_rec)) == (3, 1))
            globals()["_wtt_events"] = []
            _wtt_index.pop(9998, None)
            check("WTT картата не докосва мрежата на лигите",
                  TTL._FALSHIVI.get("vikan") == 0)
            check("запис без лига не тръгва към лигите",
                  tt_liga_klyuch({"bucket": "tabletennis"}) is None)
            check("чужда лига тенис на маса не тръгва към нашите",
                  tt_liga_klyuch({"league": "TT Cup"}) is None)

            # 🔴 ЛИПСВАЩИЯТ МОДУЛ. Частичното качване НЕ бива да убива бота:
            # без tt_ligi всичко трябва да върви по стария път, а не да гърми.
            globals()["TTL"] = None
            check("липсващ модул: разпознаването мълчи",
                  tt_liga_klyuch(_tt_rec("Jan Szotkowski", "Tadeas Zika")) is None)
            check("липсващ модул: съдията мълчи",
                  tt_liga_result(_tt_rec("Jan Szotkowski", "Tadeas Zika")) is None)
            check("липсващ модул: оценителят работи както преди",
                  _bez_grum(lambda: sport_result(
                      _tt_rec("Jan Szotkowski", "Tadeas Zika"))) is None)
            globals()["TTL"] = _tt_star_ttl

            # 🔴 КАПАНЪТ В СОБСТВЕНАТА МИ ПОПРАВКА. Редът
            # „r is getattr(TTL, 'OTLOZHEN', None)" изглежда невинно: липсва
            # ли сентинелът у чуждия модул, getattr връща None и ВСЯКО „още
            # не знам" би минало за отменен мач — тоест картата се затваря
            # ЗАВИНАГИ вместо да се пита утре. Затова None се хваща ПЪРВИ.
            # Ето подставка без сентинел, за да не е това само разсъждение.
            class _TTL_bez_sentinel(object):
                LIGI = {"czech liga pro": {"ime": "Czech Liga Pro"}}

                @staticmethod
                def liga_klyuch(ime):
                    return "czech liga pro"

                @staticmethod
                def rezultat(rec):
                    return None

            globals()["TTL"] = _TTL_bez_sentinel
            check("липсващ чужд сентинел не прави „не знам“ на „отменен“",
                  tt_liga_result(_tt_rec("A", "B")) is None)
            globals()["TTL"] = _tt_star_ttl

            # Формата: всичко, което не е двойка разумни цели числа, е „не знам".
            check("сентинелът не минава за резултат",
                  _tt_liga_forma(TTL.ZAPUSHENO) is None
                  and _tt_liga_forma(TTL.POBEDITEL_BEZ_SETOVE) is None)
            check("равен сет-резултат не съществува",
                  _tt_liga_forma((2, 2)) is None)
            check("боклук не минава за резултат",
                  _tt_liga_forma((5, 0)) is None and _tt_liga_forma((1, 0)) is None
                  and _tt_liga_forma("3-1") is None and _tt_liga_forma(None) is None
                  and _tt_liga_forma((True, False)) is None
                  and _tt_liga_forma((3, 2, 1)) is None
                  and _tt_liga_forma((3.0, 2.0)) is None
                  and _tt_liga_forma((4, 4)) is None)
            check("истинска двойка минава",
                  _tt_liga_forma((3, 2)) == (3, 2)
                  and _tt_liga_forma([1, 3]) == (1, 3))
        finally:
            TTL._MREZHA[0] = _tt_star_mr
            TTL.izchisti_kesh()
            TTL._FALSHIVI.clear()
            globals()["_wtt_events"] = _tt_star_ev
            globals()["TTL"] = _tt_star_ttl

    check("волейболът НЕ е без източник", "volleyball" not in NO_RESULT)
    check("тенисът НЕ е без източник", "tennis" not in NO_RESULT)

    # ═════════════════ 🎾 ITF И CHALLENGER: ИМА ЛИ ПЪТ ДО ПРИСЪДА
    #
    # Мрежа НЕ се пипа: подменя се САМО itf._text (входът от мрежата) и през
    # проверката минава истинският парсер и истинското отсъждане.
    check("малкият тенис тур е вързан и в оценителя", ITF is not None)
    if ITF is not None:
        _i_star = ITF._text
        try:
            ITF.nulirai()
            ITF._text = lambda pat: ITF.MOSTRA_DEN

            def _i_rec(mid, pick="1 · А"):
                return {"bucket": "tennis", "src": "itf", "itf_id": mid,
                        "home": "А", "away": "Б", "day": "2026-08-19",
                        "pick": pick, "league": "M15 Arad (Romania) · ITF"}

            check("редовен мач се отсъжда", sport_result(_i_rec("aaa22222")) == (1, 0))
            # 🔴 КАПАНЪТ. При отказал се сетовете в мострата са 1:1 — по тях
            # победител НЕ се вижда. Полето „кой спечели" го знае.
            # Измерено от itf.py върху 211 вчерашни мача: по сетовете 5 се
            # отсъждат ГРЕШНО и още 1 остава без победител.
            check("отказал се: сетовете са 1:1, но победител ИМА",
                  sport_result(_i_rec("aaa33333")) == (1, 0))
            check("служебна победа без сетове пак се отсъжда",
                  sport_result(_i_rec("aaa44444")) == (0, 1))
            # 🔴 ОТМЕНЕНИЯТ МАЧ ВРЪЩА ЧУЖДИЯ СЕНТИНЕЛ, НЕ СВОЙ ИЗМИСЛЕН ПЪТ.
            # Така главният цикъл го затваря на ЕДНО място — същото, което
            # затваря и отложените мачове от ESPN.
            check("отменен мач връща сентинела за отложен",
                  sport_result(_i_rec("aaa55555")) is OTLOZHEN)
            # Още незапочналият мач се пита пак утре, не се затваря.
            check("предстоящият мач НЕ се затваря",
                  sport_result(_i_rec("aaa11111")) is None)
            # Присъдата стига до verdict() в двете посоки.
            check("познат избор = вярно", verdict(_i_rec("aaa22222"), 1, 0) is True)
            check("сгрешен избор = невярно",
                  verdict(_i_rec("aaa22222", "2 · Б"), 1, 0) is False)
            # 🔴 БЕЗ БЕЛЕГ ЗАПИСЪТ ТРЯБВА ДА ТРЪГНЕ ПО СТАРИЯ ПЪТ.
            # Инак вграждането би пренасочило и старите ATP/WTA записи към
            # фийд, който не ги знае — тоест би счупило работещото.
            # 🔴 ТАЗИ ПРОВЕРКА ТВЪРДЕШЕ НЕЩО, КОЕТО НЕ ИЗПИТВАШЕ
            # (поправено 25.08.2026). Дотук подаваше ден „1999-01-01" и
            # чакаше None. Измерено с шпионин върху http_json днес: 6 заявки
            # до ESPN, всяка с 0 събития — значи tennis_day не влизаше в
            # тялото си нито веднъж. И по ДВАТА възможни пътя (през ESPN и
            # през малкия тур) отговорът щеше да е None, тоест проверката не
            # можеше да почервенее НИКОГА, каквото и да се счупи в
            # разпределянето. Отгоре на това хабеше 6 мрежови заявки.
            # Сега мачът СЪЩЕСТВУВА в подхвърленото табло и се мери накъде
            # тръгва записът: старият — към ESPN, белязаният — към фийда.
            _star_http2 = globals()["http_json"]
            _PITANI2 = []

            def _mreza2(url, timeout=25):
                _PITANI2.append(url)
                if "/tennis/atp/" in url and _TEN_YMD in url:
                    return _TABLO_TENIS
                return {"events": []}

            globals()["http_json"] = _mreza2
            _ten_days.clear()
            try:
                check("стар тенис запис минава през ESPN, не през малкия тур",
                      _bez_grum(lambda: sport_result(
                          {"bucket": "tennis", "home": "Алкарас",
                           "away": "Синер", "day": _TEN_DEN,
                           "pick": "1 · Алкарас"})) == (2, 0)
                      and len(_PITANI2) > 0)
                _dosega2 = len(_PITANI2)
                check("запис с белег ITF изобщо НЕ пита ESPN",
                      _bez_grum(lambda: sport_result(_i_rec("aaa22222")))
                      == (1, 0) and len(_PITANI2) == _dosega2)
            finally:
                globals()["http_json"] = _star_http2
                _ten_days.clear()
            check("без номер на мач малкият тур мълчи, а не гърми",
                  itf_result({"bucket": "tennis", "src": "itf"}) is None)
        finally:
            ITF._text = _i_star
            ITF.nulirai()
    check("футболът НЕ е без източник", "football" not in NO_RESULT)
    _b = bez_text({"tabletennis": 5})
    check("редът за без-източник казва броя", "5 мача" in NL.join(_b))
    check("редът за без-източник назовава спорта",
          "тенис на маса" in NL.join(_b))
    # 🔴 ДЕФЕКТ C. Дотук пишеше „5 без официален резултат" — канцеларски език,
    # който не казва какво прави тази бройка с процента отгоре.
    check("редът казва ПРИЧИНАТА", "източникът не ги дава" in NL.join(_b))
    check("редът казва и ПОСЛЕДИЦАТА", "не ги броим" in NL.join(_b))
    check("старата канцелария я няма", "без официален" not in NL.join(_b))
    check("един мач говори в единствено число",
          "1 мач без резултат" in NL.join(bez_red(1))
          and "не го броим" in NL.join(bez_red(1)))
    check("без-източник не се появява, когато няма такива", bez_text({}) == [])
    check("нула без-източник мълчи и на едро", bez_red(0) == [])

    # ══════════════════════════════════════════════════════════════════════
    # 🔴 ГРАНИЧНИЯТ СЛУЧАЙ ЕДНА КАРТА (26.08.2026)
    #
    # Тихата вечер е най-честият ден, в който бот с малко карти пише за себе
    # си — и точно тя беше счупена: „От 1 пуснати днес 1 имат резултат.“
    # Редът ПОД нея („⏳ 1 чака мача си“) беше верен, защото някой се е сетил
    # ТАМ. Оттук нататък се сеща mn(), не човекът.
    #
    # Всяка проверка е с ЕДНА карта И с повече от една: поправка само за
    # единицата чупи множественото, и обратно. Тествай в ДВЕТЕ посоки.
    _1d = "2026-08-11"
    _1now = datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA)

    def _kt(hit=None, scored=True, combo=0, posted=_1d):
        return {"home": "A", "away": "B", "pick": "1",
                "bucket": "football", "posted": posted + " 09:00",
                "day": _1d, "scored": scored, "hit": hit,
                "combo": combo, "score": "1:0"}

    check("mn дава единствено САМО при 1", mn(1, "мач", "мача") == "мач")
    check("mn при нула е множествено", mn(0, "мач", "мача") == "мача")
    check("mn при две е множествено", mn(2, "мач", "мача") == "мача")
    check("mn не гърми на боклук", mn(None, "мач", "мача") == "мача"
          and mn("х", "мач", "мача") == "мача")

    _f1 = den_finish_text(_1now, [_kt(True)], _1d)
    check("една карта е ПУСНАТА, не пуснати", "1</b> пусната днес" in _f1)
    check("една карта ИМА, не имат", "1</b> има резултат." in _f1)
    check("при една карта множественото го няма", "пуснати днес" not in _f1)
    _f4 = den_finish_text(_1now, [_kt(True)] * 4, _1d)
    check("четири карти пак са ПУСНАТИ", "4</b> пуснати днес" in _f4
          and "4</b> имат резултат." in _f4)
    _f10 = den_finish_text(_1now, [_kt(True)] + [_kt(None, scored=False)] * 3,
                           _1d)
    check("двете числа в реда се броят поотделно",
          "4</b> пуснати днес" in _f10 and "1</b> има резултат." in _f10)

    _fc = den_finish_text(_1now, [_kt(None, scored=False)], _1d)
    check("една чакаща не е нито един", "Нито един" not in _fc)
    check("една чакаща говори за СВОЯ мач", "мачът още не е дошъл" in _fc)
    check("една чакаща пак си има пясъчния часовник", "1 чака мача си" in _fc)
    _fc2 = den_finish_text(_1now, [_kt(None, scored=False)] * 2, _1d)
    check("две чакащи си остават в множествено",
          "Нито един още не е отсъден" in _fc2
          and "2 чакат мачовете си" in _fc2)

    _fr = den_finish_text(_1now, [_kt(True), _kt(True, posted="2026-08-10")], _1d)
    check("една по-раншна карта е ЕДНА",
          "по-раншна карта, отсъдена днес" in _fr)
    _fr2 = den_finish_text(_1now, [_kt(True)]
                           + [_kt(True, posted="2026-08-10")] * 2, _1d)
    check("две по-раншни карти са МНОЖЕСТВО",
          "по-раншни карти, отсъдени днес" in _fr2)

    _fk = den_finish_text(_1now, [_kt(True, combo=1)], _1d)
    check("фиш с ЕДИН крак пише крак", "1</b> крак" in _fk
          and "крака" not in _fk)
    _fk3 = den_finish_text(_1now, [_kt(True, combo=1)] * 3, _1d)
    check("фиш с три крака пише крака", "3</b> крака" in _fk3)
    _fk_ch = den_finish_text(_1now, [_kt(True, combo=1),
                                     _kt(None, scored=False, combo=1)], _1d)
    check("един недоигран крак чака в единствено", "1 крак още чака" in _fk_ch)

    _o1 = obshto_dosega_text(_1now, [_kt(True)])
    check("ДОСЕГА ОБЩО: една е ПУСНАТА", "1</b> пусната · " in _o1)
    _o3 = obshto_dosega_text(_1now, [_kt(True)] * 3)
    check("ДОСЕГА ОБЩО: три са ПУСНАТИ", "3</b> пуснати · " in _o3)
    _oc = obshto_dosega_text(_1now, [_kt(None, scored=False)])
    check("ДОСЕГА ОБЩО: една чакаща чака СВОЯ мач", "1 чака мача си." in _oc)
    _oc2 = obshto_dosega_text(_1now, [_kt(None, scored=False)] * 2)
    check("ДОСЕГА ОБЩО: две чакащи са в множествено",
          "2 чакат мачовете си." in _oc2)

    def _lg(hit):
        return (_kt(hit), 1, 0, hit)
    _c1 = combo_text(_1now, [((1, _1d), [_lg(True)])])
    check("ЕДИН фиш мина — в единствено", "1 от 1 фиш мина." in _c1)
    _c3 = combo_text(_1now, [((1, _1d), [_lg(True)]),
                             ((2, _1d), [_lg(False)]),
                             ((3, _1d), [_lg(False)])])
    check("един от три фиша пак е МИНА, не минаха", "1 от 3 фиша мина." in _c3)
    _c32 = combo_text(_1now, [((1, _1d), [_lg(True)]),
                              ((2, _1d), [_lg(True)]),
                              ((3, _1d), [_lg(False)])])
    check("два от три фиша МИНАХА", "2 от 3 фиша минаха." in _c32)
    _c0 = combo_text(_1now, [((1, _1d), [_lg(False)])])
    check("нула минали фиша не се пишат с дроб",
          "Нито един фиш не мина." in _c0 and "0 от 1 фиш" not in _c0)

    _r1 = results_text(_1now, [(_kt(True), 1, 0, True),
                               (_kt(False), 0, 1, False)], 10, 6)
    check("обзорът с една сгрешена пак е в единствено", "1 сгрешена" in _r1)
    check("една без-източник карта е един МАЧ",
          "1 мач без резултат" in NL.join(bez_red(1)))
    check("две без-източник карти са МАЧА",
          "2 мача без резултат" in NL.join(bez_red(2)))
    # ══════════════════════════════════════════════════════════════════════
    _t2 = results_text(_now, _rows, 10, 6, {"tabletennis": 3})
    check("обзорът показва без-източник", "без резултат" in _t2)
    check("обзорът с без-източник е чист", banned_word(_t2) is None)
    check("без-източник НЕ разваля процента", "<b>1 от 2</b>" in _t2)
    check("обзорът без такива не пише за тях", "без резултат" not in t)

    # ══════════════════════════════════════════════════════════════════════
    # 🔴 НОВИЯТ ТЕКСТ НА ЧЕТИРИТЕ СЪОБЩЕНИЯ (25.08.2026)
    #
    # Всичко тук е ПОВЕДЕНЧЕСКО: мери се върху ПОСТРОЕНИЯ текст, не върху
    # изходния код. Тоест иглата не може да живее в коментара до проверката —
    # копата сено е низът, който Telegram би получил.
    def _vidimo(_s):
        """Текстът, както го чете човек: без HTML таговете."""
        _o, _v = [], True
        for _ch in _s:
            if _ch == "<":
                _v = False
            elif _ch == ">":
                _v = True
            elif _v:
                _o.append(_ch)
        return "".join(_o)

    # --- ТАВАНЪТ. Измерено на този файл ПРЕДИ промяната, с 39 отсъдени мача
    # от пет спорта: обзорът е 109 реда и 4046 знака по сметката на Telegram,
    # при таван 4096. Бяхме на петдесет знака от това съобщението изобщо да не
    # излезе. Това е причината промяната да съществува и затова се пази.
    _mn_plan = [("football", 6, 13), ("volleyball", 6, 9), ("tabletennis", 5, 8),
                ("tennis", 2, 5), ("baseball", 2, 4)]
    _mn, _br = [], 0
    for _b, _p, _n in _mn_plan:
        for _k in range(_n):
            _br += 1
            _mn.append(({"home": "Домакин " + str(_br), "away": "Гост " + str(_br),
                         "pick": "1 · победа Домакин " + str(_br), "bucket": _b,
                         "day": "2026-08-2" + str(1 + (_k % 3))}, 3, 2, _k < _p))
    _tmn = results_text(_now, _mn, 389, 270, {"tabletennis": 2}, _dnevnik)
    # 🔴 ТРИТЕ ПРОВЕРКИ ПОД ТОЗИ РЕД СА ОБЪРНАТИ, НЕ ТРИТИ (25.08.2026).
    # Дотук пазеха, че при 39 мача списъкът ПАДА целият. Собственикът поиска
    # обратното същия ден: „искам си всичко което си имаше и да се вижда."
    # Затова сега пазят, че списъкът СЕ ПОЯВЯВА, но с таван — и че таванът
    # държи съобщението в границите на Telegram.
    check("обзорът при 39 мача има глава под 20 реда",
          len(_tmn.split(NL)[0:1] + [x for x in _tmn.split(NL)
                                     if x.startswith("\u26bd") or x.startswith("\U0001f3c0")
                                     or x.startswith("\U0001f3d0")]) <= 20)
    # Таванът на Telegram е 4096 знака. Списъкът вече го приближава, затова
    # проверката пази ИСТИНСКАТА граница, а не старата тясна.
    check("обзорът при 39 мача пак е под тавана на Telegram",
          len(_tmn.encode("utf-16-le")) // 2 < 4000)
    check("обзорът при 39 мача ВЕЧЕ изрежда мачовете",
          "Домакин 7" in _tmn)
    # 🔴 И казва на глас колко е премълчал. Премълчан остатък е по-лош от
    # дълъг списък: читателят не знае, че има още, и мисли, че мачът му липсва.
    check("излишните се броят на глас",
          ("и още" in _tmn) or ("Домакин 30" in _tmn))
    check("но числата по спортове остават всичките",
          "Футбол <b>6 от 13</b>" in _tmn and "Волейбол <b>6 от 9</b>" in _tmn
          and "Тенис на маса <b>5 от 8</b>" in _tmn
          and "Тенис <b>2 от 5</b>" in _tmn and "Бейзбол <b>2 от 4</b>" in _tmn)
    check("главата на голямото пускане е вярна", "<b>21 от 39</b>" in _tmn)
    check("голямото пускане казва от кои дни са мачовете",
          "мачове от 21.08 до 23.08" in _tmn)
    # Границата държи и в другата посока: точно на тавана списъкът СЕ вижда.
    # ─────────────── СПИСЪКЪТ Е ВЪРНАТ (25.08.2026)
    check("таванът е достатъчен за обикновено пускане", OBZOR_MAKS_MACHOVE >= 15)
    check("броячът брои МАЧОВЕ, не прогнози",
          broy_machove([(dict(home="А", away="Б", pick="1"), 1, 0, True),
                        (dict(home="А", away="Б", pick="Над 2.5"), 1, 0, False)]) == 1)
    check("два различни мача са два", broy_machove(
        [(dict(home="А", away="Б"), 1, 0, True),
         (dict(home="В", away="Г"), 2, 1, True)]) == 2)
    check("празното е нула", broy_machove([]) == 0 and broy_machove(None) == 0)
    _mnogo = [(dict(home="Д%d" % i, away="Г%d" % i, pick="1 · Д%d" % i), 1, 0, True)
              for i in range(40)]
    _r = mach_redove(_mnogo, 24)
    check("таванът реже списъка", len(_r) == 24)
    check("без таван нищо не се реже", len(mach_redove(_mnogo)) == 40)
    check("таван нула дава празно", mach_redove(_mnogo, 0) == [])
    # 🔴 МАЧ С ДВА ПАЗАРА НЕ БИВА ДА СЕ РАЗЦЕПИ ОТ ТАВАНА.
    _dva = [(dict(home="А", away="Б", pick="1 · А"), 3, 2, True),
            (dict(home="А", away="Б", pick="Над 2.5"), 3, 2, False),
            (dict(home="В", away="Г", pick="1 · В"), 1, 0, True)]
    _rr = mach_redove(_dva, 1)
    check("при таван 1 излиза ЦЕЛИЯТ първи мач", len(_rr) == 2)
    check("и вторият мач го няма", not any("В" in x and "Г" in x for x in _rr))
    _t40 = results_text(_now, _mn * 20, 389, 270)
    check("при много мачове списъкът СЕ ПОЯВЯВА",
          "✅" in _t40 or "❌" in _t40)

    _tmalko = results_text(_now, _mn[:OBZOR_MAKS_MACHOVE], 389, 270)
    check("пускане до тавана още изрежда мачовете си",
          "Домакин 1" in _tmalko and "Домакин 5" in _tmalko)
    _tedin_nad = results_text(_now, _mn[:OBZOR_MAKS_MACHOVE + 1], 389, 270)
    # ОБЪРНАТА (25.08.2026): дотук пазеше, че един мач над тавана пуска
    # списъка ЦЕЛИЯ. Сега пази, че той ОСТАВА, реже се и остатъкът се казва.
    check("един мач над тавана НЕ поваля списъка",
          "Домакин 1" in _tedin_nad)
    check("и излишният се брои", "и още 1 мач" in _tedin_nad)

    # --- ДЕФЕКТ A: две пускания в един ден вече не носят едно заглавие.
    _sut = results_text(datetime(2026, 8, 23, 13, 30, tzinfo=SOFIA), _mn, 389, 270)
    _vech = results_text(datetime(2026, 8, 23, 22, 30, tzinfo=SOFIA), _mn, 389, 270)
    check("двете пускания в един ден имат РАЗЛИЧНИ заглавия",
          _sut.split(NL)[0] != _vech.split(NL)[0])
    check("заглавието казва часа, не само деня",
          "13:30" in _sut.split(NL)[0] and "22:30" in _vech.split(NL)[0])

    # --- ДЕФЕКТ B: един мач, два пазара, ЕДИН блок — а числото пак брои две.
    _dvap = [({"home": "Nashville SC", "away": "Columbus Crew", "bucket": "football",
               "pick": "1 · победа Nashville SC", "day": "2026-08-23"}, 3, 2, True),
             ({"home": "Nashville SC", "away": "Columbus Crew", "bucket": "football",
               "pick": "Над 2.5 гола", "day": "2026-08-23"}, 3, 2, True)]
    _tb = results_text(_now, _dvap, 10, 6)
    check("мачът с два пазара се изписва ВЕДНЪЖ", _tb.count("Columbus Crew") == 1)
    check("двата избора стоят на един ред под мача",
          "победа Nashville SC · ✅ Над 2.5 гола" in _tb)
    check("а сметката пак ги брои за ДВЕ прогнози", "<b>2 от 2</b>" in _tb)
    # Различен резултат = различен мач, не се слива.
    _trazl = results_text(_now, [_dvap[0], ({"home": "Nashville SC",
                                            "away": "Columbus Crew",
                                            "bucket": "football", "pick": "1",
                                            "day": "2026-08-23"}, 1, 0, True)],
                          10, 6)
    check("същите отбори с ДРУГ резултат си остават два реда",
          "3:2" in _trazl and "1:0" in _trazl)

    # --- ДЕФЕКТ C: причина и последица, и в трите съобщения.
    check("обзорът обяснява неотсъдимите",
          "източникът не ги дава" in _tmn and "не ги броим" in _tmn)
    check("финишът обяснява неотсъдимите по СЪЩИЯ начин",
          "източникът не го дава" in _fin and "не го броим" in _fin)
    check("канцеларската фраза го няма никъде",
          "без официален" not in _tmn and "без официален" not in _fin
          and "без официален" not in _od)

    # --- ЕДНО СЪОБЩЕНИЕ, ЕДИН ИЗМЕРИТЕЛ. Три процента за пет секунди в една
    # стая се четат като спор. Обзорът дава процента; финишът дава броеве.
    check("обзорът има ТОЧНО един процент", _tmn.count("%") == 1)
    check("финишът няма нито един процент", "%" not in _fin)
    check("обедната няма нито един процент", "%" not in _obed)

    # --- ЗНАМЕНАТЕЛЯТ ИДВА ПРЪВ. Живият финиш пишеше „пуснати ДНЕС: 62",
    # после „познати: 17", а знаменателят 27 идваше три реда по-долу.
    _fin62 = den_finish_text(datetime(2026, 8, 11, 23, 30, tzinfo=SOFIA),
                             [{"posted": "2026-08-11 09:00", "bucket": "football",
                               "scored": (i < 27), "hit": (True if i < 17
                                                           else (False if i < 27
                                                                 else None)),
                               "home": "А" + str(i), "away": "Б" + str(i)}
                              for i in range(62)], "2026-08-11")
    check("знаменателите се четат в правилния ред",
          predi(_fin62, "62", "27") and predi(_fin62, "27", "17"))
    check("и сгрешените са изписани с дума", "сгрешихме <b>10</b>" in _fin62)

    # --- ЧИСЛОТО И ДУМАТА ДО НЕГО НЕ СИ ПРОТИВОРЕЧАТ. Сборът на познати и
    # сгрешени трябва да е точно знаменателят, изписан отляво на същия ред.
    import re as _re
    _mm = _re.search(r"<b>(\d+) от (\d+)</b> · (\d+) сгрешен", _tmn)
    check("сгрешените са точно разликата до знаменателя",
          bool(_mm) and int(_mm.group(1)) + int(_mm.group(3)) == int(_mm.group(2)))
    _mp = _re.search(r"<b>(\d+) от (\d+)</b>[^%]*<b>(\d+)%</b>", _tmn)
    check("процентът отговаря на дробта пред него",
          bool(_mp) and abs(round(100.0 * int(_mp.group(1)) / int(_mp.group(2)))
                            - int(_mp.group(3))) <= 1)

    # --- НЕ ОБЕЩАВАМЕ НЕЩО, КОЕТО ГО НЯМА. В спора и трите школи пишеха
    # „мач по мач е в стая ✅ Резултати" — а тази стая получава точно това
    # съобщение. Указател към самия себе си е обещание без адрес.
    check("обзорът не праща човека към списък, който не съществува",
          "Мач по мач" not in _tmn and "закачен" not in _tmn
          and "ТАБЛО" not in _tmn)

    # --- ПОРТИЕРЪТ ВЪРХУ ВСИЧКИТЕ ПЕТ ГОТОВИ ТЕКСТА.
    for _ime, _txt in (("обзор-голям", _tmn), ("обзор-малък", _tmalko),
                       ("финиш", _fin62), ("обед", _obed), ("равносметка", _od)):
        check("новият текст минава портиера: " + _ime, banned_word(_txt) is None)

    # --- ДЪЛЖИНИ И СТЕНИ. Ред над 80 видими знака се пренася на телефона по
    # три пъти; тогава „12 реда" на масата са 20 в ръката.
    check("финишът се събира в 22 реда", len(_fin62.split(NL)) <= 22)
    check("обедната се събира в 22 реда", len(_obed.split(NL)) <= 22)
    check("равносметката се събира в 30 реда", len(_od.split(NL)) <= 30)
    check("нито един ред не е стена",
          max(len(_vidimo(_l)) for _l in
              (_tmn + NL + _fin62 + NL + _obed + NL + _od).split(NL)) <= 80)

    # --- ЧУЖДАТА ЦЕНА ИЗЛИЗА ОТ РАВНОСМЕТКАТА. „средна цена 1.76" е среден
    # коефициент под друга дума, а „доходност при равен залог" е възвръщаемост
    # на залог — в канал, който твърди, че не е за залози. СМЕТКИТЕ остават:
    # dohodnost() и clv_text() не са пипани, спира само печатането им.
    _spari = [{"scored": True, "hit": (k % 2 == 0), "pazar_cena": 2.0,
               "pazar_v": 2, "pazar_clv": 0.02, "bucket": "baseball",
               "p": 0.60, "pazar_p": 0.54, "posted": "2026-08-11 10:00"}
              for k in range(80)]
    _odp = obshto_dosega_text(_now, _spari)
    check("равносметката вече не печата цена и доходност",
          "средна цена" not in _odp and "доходност" not in _odp
          and "Струва ли си" not in _odp)
    check("но сметката за доходност още работи във файла",
          dohodnost(_spari)[1] == 80)
    # 🔴 ОБЪРНАТА 25.08.2026. Разделът „Когато не сме съгласни с пазара"
    # отпадна заедно с таблицата по спорт — собственикът поиска четири числа.
    # ЧЕСТНО ЗА ЗАГУБАТА: това беше единственото място в СТАЯТА, което казваше
    # че пазарът често е по-прав от нас. Числото не изчезва — живее в
    # здравния преглед, който чете собственикът, — но публиката вече не го
    # вижда. Казвам го, не го крия.
    check("разделът срещу пазара вече НЕ е в равносметката",
          "Когато не сме съгласни с пазара" not in _odp)
    check("равносметката с пазарни числа пак минава портиера",
          banned_word(_odp) is None)

    # ══════════════════════════════════════════════════════════════════════
    #  ПАЗАЧЪТ СРЕЩУ ПОВТОРЕНА РАВНОСМЕТКА — ИЗПИТВА СЕ ПОВЕДЕНИЕ (26.08.2026)
    #
    #  УРОКЪТ ОТ КРАША НА 24.08: старата проверка за сентинела OTLOZHEN беше
    #  ЗЕЛЕНА върху счупен файл, защото гледаше ВРЪЗВАНЕТО (има ли такъв ред в
    #  главния цикъл), а убийството ставаше две стаи по-рано. Затова тук нищо
    #  не се търси в текста: пътят СЕ ВИКА и се гледа какво излиза от другата
    #  страна — включително самата main(), с временен дневник и закован
    #  часовник. Върне ли някой пращането на голото post(), долният блок
    #  почервенява.
    # ══════════════════════════════════════════════════════════════════════
    import tempfile
    _ok_predi_ravn = ok
    _bud_t = _bud_modul()
    check("будилникът се внася и носи целия слой ravn_*", _bud_t is not None)
    if _bud_t is not None:
        check("будилникът вижда пазача в ЖИВИЯ scorer.py",
              _bud_t.pazachat_e_v_scorera() is True)
        _tmp_r = os.path.join(tempfile.gettempdir(), "_scorer_ravn_selftest.json")
        _star_r_file = globals()["RAVN_SAST_FILE"]
        _star_r_dry = globals()["DRY_RUN"]
        _star_post = globals()["post"]
        _star_kanal = globals()["post_channel"]
        _star_bud = globals()["_bud_modul"]
        _prateni = []

        def _lazhepost(thread, text):
            _prateni.append(("staya", str(thread), text))
            return True

        def _lazhekanal(text):
            _prateni.append(("kanal", "", text))
            return True

        try:
            try:
                os.remove(_tmp_r)
            except OSError:
                pass
            globals()["RAVN_SAST_FILE"] = _tmp_r
            globals()["DRY_RUN"] = False
            globals()["post"] = _lazhepost
            globals()["post_channel"] = _lazhekanal
            ravn_zabravi()
            _t0 = datetime(2026, 8, 25, 23, 40, tzinfo=SOFIA)
            _dn = "2026-08-25"
            _fin1 = ("ФИНИШ НА ДЕНЯ · пн 25.08" + chr(10)
                     + "От 40 пуснати днес 12 имат резултат.")
            check("равносметката излиза първия път",
                  prati_ravnosmetka(_t0, _dn, "finish", "staya", _fin1)[0] is True)
            check("и наистина е стигнала до стаята",
                  len(_prateni) == 1 and _prateni[0][0] == "staya")
            check("стигна до СТАЯ 9, не другаде", _prateni[0][1] == RESULTS_THREAD)
            # МУТАЦИЯ 1: същият текст втори път
            check("МУТАЦИЯ: същият текст втори път МЪЛЧИ",
                  prati_ravnosmetka(_t0, _dn, "finish", "staya", _fin1)[0] is False)
            check("и НЕ е пратен втори път", len(_prateni) == 1)
            # МУТАЦИЯ 2 (обратната посока): сменено число
            _fin2 = _fin1.replace("12 имат", "13 имат")
            check("МУТАЦИЯ обратно: сменено число ИЗЛИЗА",
                  prati_ravnosmetka(_t0, _dn, "finish", "staya", _fin2)[0] is True)
            check("и то стигна до стаята", len(_prateni) == 2)
            # само ЧАСЪТ в първия ред не е ново съдържание
            _mezh = ("ДОКЪДЕ СМЕ ДНЕС · пн 25.08, 14:07" + chr(10)
                     + "От 40 пуснати днес 12 имат резултат.")
            check("междинната излиза",
                  prati_ravnosmetka(_t0, _dn, "mezhdinna", "staya",
                                    _mezh)[0] is True)
            check("само друг ЧАС в заглавието не е ново съдържание",
                  prati_ravnosmetka(_t0, _dn, "mezhdinna", "staya",
                                    _mezh.replace("14:07", "14:31"))[0] is False)
            # ДВА АДРЕСА = ДВА КЛЮЧА
            _n_predi = len(_prateni)
            check("каналът получава СЪЩИЯ текст, глътнат в стаята",
                  prati_ravnosmetka(_t0, _dn, "finish", "kanal", _fin2)[0] is True)
            check("и е стигнал точно до КАНАЛА",
                  len(_prateni) == _n_predi + 1 and _prateni[-1][0] == "kanal"
                  and _prateni[-1][2] == _fin2)
            check("вторият път и каналът мълчи",
                  prati_ravnosmetka(_t0, _dn, "finish", "kanal",
                                    _fin2)[0] is False)
            # СЪСТОЯНИЕТО ОЦЕЛЯВА МЕЖДУ РЪНОВЕ
            check("тефтерът е записан на диска", os.path.exists(_tmp_r))
            ravn_zabravi()                      # все едно е НОВ рън
            check("нов рън с празна памет пак мълчи",
                  prati_ravnosmetka(_t0, _dn, "finish", "staya",
                                    _fin2)[0] is False)
            _marki_predi = len(_bud_t.ravn_marki(ravn_sast(_bud_t)))
            with open(_tmp_r, encoding="utf-8-sig") as _f:
                _disk_predi = _f.read()
            # МУТАЦИЯ 3: СУХО ПУСКАНЕ НЕ ОТБЕЛЯЗВА НИЩО
            globals()["DRY_RUN"] = True
            ravn_zabravi()
            _n_predi = len(_prateni)
            _suh = "текст, невиждан досега — само за сухата проба"
            check("сухо пускане: съобщението пак излиза",
                  prati_ravnosmetka(_t0, _dn, "obzor", "staya", _suh)[0] is True)
            check("сухо пускане: стигна до стаята", len(_prateni) == _n_predi + 1)
            with open(_tmp_r, encoding="utf-8-sig") as _f:
                _disk_sled = _f.read()
            check("МУТАЦИЯ: сухо пускане НЕ пипа тефтера на диска",
                  _disk_sled == _disk_predi)
            check("сухо пускане не пипа и тефтера в паметта",
                  len(_bud_t.ravn_marki(ravn_sast(_bud_t))) == _marki_predi)
            check("затова сухата проба НЕ заключва истинското съобщение",
                  prati_ravnosmetka(_t0, _dn, "obzor", "staya", _suh)[0] is True)
            # МУТАЦИЯ 3 обратно: мокрото пускане ОТБЕЛЯЗВА
            globals()["DRY_RUN"] = False
            ravn_zabravi()
            check("МУТАЦИЯ обратно: мокрото пускане излиза",
                  prati_ravnosmetka(_t0, _dn, "obzor", "staya", _suh)[0] is True)
            with open(_tmp_r, encoding="utf-8-sig") as _f:
                _disk_mokro = _f.read()
            check("и тефтерът на диска СЕ промени", _disk_mokro != _disk_predi)
            ravn_zabravi()
            check("и оттук нататък мълчи",
                  prati_ravnosmetka(_t0, _dn, "obzor", "staya", _suh)[0] is False)
            # ПАДНАЛО ПРАЩАНЕ НЕ СЕ МАРКИРА
            globals()["post"] = lambda thread, text: False
            ravn_zabravi()
            _padnal = "равносметка, чието пращане пада"
            check("паднало пращане връща False",
                  prati_ravnosmetka(_t0, _dn, "dosega", "staya",
                                    _padnal)[0] is False)
            globals()["post"] = _lazhepost
            ravn_zabravi()
            check("паднало пращане НЕ слага марка — пробва се пак",
                  prati_ravnosmetka(_t0, _dn, "dosega", "staya",
                                    _padnal)[0] is True)
            # ── 🎫 И ВРАТАТА НА ФИША, В СЪЩИЯ ВРЕМЕНЕН ТЕФТЕР ─────────
            # Пращането е подставено, тефтерът е временен: нищо не тръгва
            # навън и живият budilnik_state.json не се пипа.
            ravn_zabravi()
            _fh1 = "🎫 ОТЧЕТ НА ФИШОВЕТЕ" + chr(10) + "✅ ФИШ 1 · 2 от 2"
            _n0 = len(_prateni)
            check("отчетът на фиша излиза първия път",
                  combo_prati(_t0, _dn, _fh1)[0] is True)
            check("и стигна до СТАЯ 10",
                  len(_prateni) == _n0 + 1
                  and _prateni[-1][1] == WINS_THREAD)
            # МУТАЦИЯ: същият отчет втори път. Вторият тефтер го спира —
            # НО връща „маркирай", иначе кракът се опитва вечно.
            ravn_zabravi()
            check("същият отчет втори път НЕ се праща",
                  combo_prati(_t0, _dn, _fh1)[0] is True
                  and len(_prateni) == _n0 + 1)
            # ОБРАТНАТА ПОСОКА: нов фиш в текста = нов отпечатък = ИЗЛИЗА.
            ravn_zabravi()
            _fh2 = _fh1 + chr(10) + "❌ ФИШ 2 · 1 от 3"
            check("новият отчет ИЗЛИЗА, не се глътва",
                  combo_prati(_t0, _dn, _fh2)[0] is True
                  and len(_prateni) == _n0 + 2)
            # ПАДНАЛО ПРАЩАНЕ: без марка, за да се пробва пак.
            globals()["post"] = lambda thread, text: False
            ravn_zabravi()
            _fh3 = _fh2 + chr(10) + "❌ ФИШ 3 · 0 от 4"
            check("паднал отчет на фиша НЕ дава марка",
                  combo_prati(_t0, _dn, _fh3)[0] is False)
            globals()["post"] = _lazhepost
            ravn_zabravi()
            check("и затова се праща пак на следващия рън",
                  combo_prati(_t0, _dn, _fh3)[0] is True
                  and len(_prateni) == _n0 + 3)
            # БЕЗ БУДИЛНИК — ПРАЩА КАКТО ПРЕДИ (провал към шум, не към тишина)
            globals()["_bud_modul"] = lambda: None
            _n_fish = len(_prateni)
            check("без будилник и отчетът на фиша пак излиза",
                  combo_prati(_t0, _dn, "фиш без пазач")[0] is True
                  and len(_prateni) == _n_fish + 1)
            _n_predi = len(_prateni)
            check("без будилник оценителят пак праща",
                  prati_ravnosmetka(_t0, _dn, "finish", "staya",
                                    _fin2)[0] is True)
            check("и съобщението наистина излиза",
                  len(_prateni) == _n_predi + 1)
            globals()["_bud_modul"] = _star_bud
        finally:
            globals()["_bud_modul"] = _star_bud
            globals()["RAVN_SAST_FILE"] = _star_r_file
            globals()["DRY_RUN"] = _star_r_dry
            globals()["post"] = _star_post
            globals()["post_channel"] = _star_kanal
            ravn_zabravi()
            try:
                os.remove(_tmp_r)
            except OSError:
                pass
        check("подставените пращачи са върнати",
              globals()["post"] is _star_post
              and globals()["post_channel"] is _star_kanal)
        check("сухият режим е върнат както си беше",
              globals()["DRY_RUN"] is _star_r_dry)

        # ══════════════════════════════════════════════════════════════════
        #  МИНАВА ЛИ main() ПРЕЗ ВРАТАТА. Пазач, който съществува, но не е
        #  вързан, е украса. Затова main() СЕ ПУСКА наистина — временен
        #  дневник, закован часовник, подставени пращачи — и се гледа КОЙ е
        #  бил викан. Голото post() за равносметка тук е ЧЕРВЕНО.
        # ══════════════════════════════════════════════════════════════════
        _s_log = globals()["LOG_FILE"]
        _s_arh = globals()["ARHIV_FILE"]
        _s_dt = globals()["datetime"]
        _s_time = globals()["time"]
        _s_pr = globals()["prati_ravnosmetka"]
        _s_post = globals()["post"]
        _s_kanal = globals()["post_channel"]
        _s_dry = globals()["DRY_RUN"]
        _s_sport = globals()["sport_result"]
        _s_zatv = globals()["hvani_zatvaryashta"]
        _vikani, _golo = [], []
        _tmp_log = os.path.join(tempfile.gettempdir(), "_scorer_main_selftest.json")
        _tmp_arh = os.path.join(tempfile.gettempdir(), "_scorer_arhiv_selftest.json")

        class _Chasovnik(_s_dt):
            @classmethod
            def now(cls, tz=None):
                return _s_dt(2026, 8, 25, 23, 40, tzinfo=SOFIA)

        class _BezSan(object):
            @staticmethod
            def sleep(n):
                return None

        def _shpionin(now, den, vid, adres, text):
            _vikani.append((vid, adres))
            return True, "шпионин"

        _red = {"day": "2026-08-25", "posted": "2026-08-25 12:00",
                "home": "Куба", "away": "Египет", "pick": "1 · победа Куба",
                "bucket": "futbol", "sport": "Футбол", "league": "Тест"}
        try:
            globals()["LOG_FILE"] = _tmp_log
            globals()["ARHIV_FILE"] = _tmp_arh
            globals()["DRY_RUN"] = True          # нищо не се пише по диска
            globals()["datetime"] = _Chasovnik
            globals()["time"] = _BezSan
            globals()["prati_ravnosmetka"] = _shpionin
            globals()["post"] = lambda thread, text: (_golo.append(("staya", text))
                                                      or True)
            globals()["post_channel"] = lambda text: (_golo.append(("kanal", text))
                                                      or True)
            globals()["hvani_zatvaryashta"] = lambda r: False
            # 1) ВЕЧЕР БЕЗ НОВИ ПРИСЪДИ: финиш в стаята, финиш в канала, досега.
            _gotov = dict(_red)
            _gotov.update({"scored": True, "hit": True, "score": "2:0"})
            with open(_tmp_log, "w", encoding="utf-8") as _f:
                json.dump([_gotov], _f, ensure_ascii=False)
            check("main() върна 0 на вечер без нови присъди", main() == 0)
            check("вечер без присъди: ТРИ равносметки през вратата",
                  len(_vikani) == 3)
            check("финишът отива в стаята", ("finish", "staya") in _vikani)
            check("финишът отива И в канала", ("finish", "kanal") in _vikani)
            check("ДОСЕГА ОБЩО отива в стаята", ("dosega", "staya") in _vikani)
            check("нито една равносметка не мина ПОКРАЙ пазача", _golo == [])
            # 2) ВЕЧЕР С НОВИ ПРИСЪДИ: и обзорът минава през вратата.
            del _vikani[:]
            del _golo[:]
            globals()["sport_result"] = lambda r: (2, 0)
            _viss = dict(_red)
            with open(_tmp_log, "w", encoding="utf-8") as _f:
                json.dump([_viss], _f, ensure_ascii=False)
            check("main() върна 0 с нови присъди", main() == 0)
            check("с нови присъди: ПЕТ равносметки през вратата",
                  len(_vikani) == 5)
            check("обзорът отива в стаята", ("obzor", "staya") in _vikani)
            check("обзорът отива И в канала", ("obzor", "kanal") in _vikani)
            check("и тук нищо не мина покрай пазача", _golo == [])
            # 3) 🎫 ФИШЪТ В ЖИВИЯ main(): марка САМО след успешно пращане.
            # Тук дневникът се ЗАПИСВА наистина (DRY_RUN=False, временен
            # файл), за да се прочете ОТ ДИСКА какво е останало — иначе
            # тестът мери паметта си, не поведението.
            _s_bud2 = globals()["_bud_modul"]
            _s_tok2 = globals()["BOT_TOKEN"]
            try:
                globals()["_bud_modul"] = lambda: None
                # DRY_RUN=False, за да пише save_log — а без подставен
                # токен main() би излязъл с 1 още на първия ред.
                globals()["BOT_TOKEN"] = "podstaven-za-testa"
                globals()["DRY_RUN"] = False
                # 🔴 ВСЕКИ РЪН ТУК ПОЛУЧАВА ПОНЕ ЕДНА НОВА ПРИСЪДА.
                # main() се връща РАНО (при not fresh), ако в ръна няма
                # нито един новоотсъден мач — блокът на фиша изобщо не се
                # стига. Затова 3б и 3в добавят по един пресен ред.
                _kraka = []
                for _i in (1, 2):
                    _k = dict(_red)
                    _k.update({"combo": 1, "league": "Тест" + str(_i)})
                    _kraka.append(_k)
                # 3а) ПРАЩАНЕТО ПАДА → без марка, но с брояч на опита.
                del _golo[:]
                with open(_tmp_log, "w", encoding="utf-8") as _f:
                    json.dump(_kraka, _f, ensure_ascii=False)
                globals()["post"] = lambda thread, text: (
                    _golo.append(("staya", text)) or False)
                check("main() върна 0 и при паднал отчет на фиш", main() == 0)
                check("отчетът на фиша Е бил опитан", len(_golo) == 1)
                with open(_tmp_log, encoding="utf-8") as _f:
                    _sled = json.load(_f)
                check("паднало пращане НЕ маркира краката в дневника",
                      len(_sled) == 2
                      and not any(x.get("combo_done") for x in _sled))
                check("но опитът е записан в дневника",
                      all(x.get("combo_opiti") == 1 for x in _sled))
                # 3б) СЪЩИЯТ ДНЕВНИК, СЕГА ПРАЩАНЕТО МИНАВА.
                del _golo[:]
                with open(_tmp_log, "w", encoding="utf-8") as _f:
                    json.dump(_sled + [dict(_red)], _f, ensure_ascii=False)
                globals()["post"] = lambda thread, text: (
                    _golo.append(("staya", text)) or True)
                check("main() върна 0 при успешен отчет", main() == 0)
                check("отчетът е пратен пак — нищо не се е загубило",
                      len(_golo) == 1)
                with open(_tmp_log, encoding="utf-8") as _f:
                    _sled2 = json.load(_f)
                _kr2 = [x for x in _sled2 if x.get("combo")]
                check("успешното пращане маркира краката",
                      len(_kr2) == 2 and all(x.get("combo_done") for x in _kr2))
                check("и броячът на опитите е изчистен",
                      not any("combo_opiti" in x for x in _kr2))
                # 3в) ТРЕТИ РЪН: отчетеният фиш вече не излиза.
                del _golo[:]
                with open(_tmp_log, "w", encoding="utf-8") as _f:
                    json.dump(_sled2 + [dict(_red)], _f, ensure_ascii=False)
                check("main() върна 0 на трети рън", main() == 0)
                check("отчетеният фиш НЕ излиза втори път", _golo == [])
            finally:
                globals()["_bud_modul"] = _s_bud2
                globals()["BOT_TOKEN"] = _s_tok2
                globals()["DRY_RUN"] = True
        finally:
            globals()["LOG_FILE"] = _s_log
            globals()["ARHIV_FILE"] = _s_arh
            globals()["datetime"] = _s_dt
            globals()["time"] = _s_time
            globals()["prati_ravnosmetka"] = _s_pr
            globals()["post"] = _s_post
            globals()["post_channel"] = _s_kanal
            globals()["DRY_RUN"] = _s_dry
            globals()["sport_result"] = _s_sport
            globals()["hvani_zatvaryashta"] = _s_zatv
            for _p in (_tmp_log, _tmp_arh):
                try:
                    os.remove(_p)
                except OSError:
                    pass
        check("дневникът е върнат на живия", globals()["LOG_FILE"] is _s_log)
        check("часовникът е върнат", globals()["datetime"] is _s_dt)
        check("вратата е върната на истинската",
              globals()["prati_ravnosmetka"] is _s_pr)

    # ДОЛНА ГРАНИЦА НА БРОЯ, НЕ НА ЗЕЛЕНОТО. Пропадне ли блокът заради ранен
    # изход или сгрешен отстъп, тази проверка го издава — иначе 0 счупени
    # щеше да значи 0 прегледани.
    check("пазачът на равносметките добави поне 35 свои проверки",
          ok - _ok_predi_ravn >= 35)

    # ======================================================================
    #  🔴 ±1 ДЕН И СЕРИЯТА  (измерено на живо 02.09.2026)
    #  Виж дългото обяснение в baseball_result. Тук се заковават И ДВЕТЕ
    #  посоки: чуждият ден да НЕ влиза, а нощният мач под вчерашната дата на
    #  графика да ВЛИЗА. Спечели ли само едната, поправката е половин.
    # ======================================================================
    _ok_predi_serii = ok

    check("22:00 UTC на 14-ти е вече 15-ти в София",
          sofia_den("2026-08-14T22:00:00Z") == "2026-08-15")
    check("18:20 UTC на 14-ти още е 14-ти в София",
          sofia_den("2026-08-14T18:20:00Z") == "2026-08-14")
    check("софийската дата НЕ е първите десет знака на низа",
          sofia_den("2026-08-14T23:30:00Z") != "2026-08-14")
    check("празното дава празно, не днешна дата",
          sofia_den("") == "" and sofia_den(None) == "")
    check("боклукът дава празно и не гърми", sofia_den("вчера") == "")
    check("без Z пак се чете", sofia_den("2026-08-14T22:00:00") == "2026-08-15")
    check("редът на прозореца е свой, вчера, утре",
          okolni_dni("2026-08-25") == ["2026-08-25", "2026-08-24", "2026-08-26"])

    _s_mlb_kesh = dict(_mlb_days)
    _s_hj = globals()["http_json"]
    try:
        def _mlb_falshiv(sast):
            def _f(url, timeout=25):
                return {"dates": [{"games": [
                    {"gameDate": "2026-08-14T23:10:00Z",
                     "status": {"detailedState": sast},
                     "teams": {
                         "home": {"team": {"id": 1, "name": "Алфа"}, "score": 5},
                         "away": {"team": {"id": 2, "name": "Бета"}, "score": 3}}}]}]}
            return _f

        globals()["http_json"] = _mlb_falshiv("Final")
        _mlb_days.clear()
        _red = mlb_day("2026-08-14")
        check("МЛБ редът има седем полета",
              len(_red) == 1 and len(_red[0]) == 7)
        check("седмото поле е СОФИЙСКАТА дата, не датата на графика",
              _red[0][6] == "2026-08-15")
        check("МЛБ редът пази номера и точките",
              _red[0][0] == "1" and _red[0][2] == 5 and _red[0][3] == 3)
        globals()["http_json"] = _mlb_falshiv("In Progress")
        _mlb_days.clear()
        check("незавършеният мач не влиза в деня", mlb_day("2026-08-14") == [])
        globals()["http_json"] = _s_hj

        # -- СЕРИЯТА: същите два отбора на два поредни дни
        _mlb_days.clear()
        _mlb_days["2026-08-14"] = [("112", "138", 3, 0, "Chicago Cubs",
                                    "St. Louis Cardinals", "2026-08-14")]
        _mlb_days["2026-08-15"] = [("112", "138", 4, 8, "Chicago Cubs",
                                    "St. Louis Cardinals", "2026-08-15")]
        _mlb_days["2026-08-16"] = []
        _mlb_days["2026-08-13"] = []
        _kabs15 = {"day": "2026-08-15", "home": "Chicago Cubs",
                   "away": "St. Louis Cardinals", "home_id": "112",
                   "away_id": "138", "pick": "1 · Chicago Cubs"}
        check("серията НЕ лепи вчерашния мач (Къбс 15.08 е 4:8, не 3:0)",
              baseball_result(_kabs15) == (4, 8))
        check("серията НЕ лепи утрешния мач (Къбс 14.08 е 3:0)",
              baseball_result(dict(_kabs15, day="2026-08-14")) == (3, 0))
        check("точно това обръщаше присъдата",
              verdict(_kabs15, 3, 0) is True and verdict(_kabs15, 4, 8) is False)

        # -- ОБРАТНАТА ПОСОКА: нощният мач стои под ВЧЕРАШНАТА дата на графика
        _mlb_days.clear()
        _mlb_days["2026-08-14"] = [("111", "147", 5, 2, "Boston Red Sox",
                                    "New York Yankees", "2026-08-15")]
        _mlb_days["2026-08-15"] = []
        _mlb_days["2026-08-16"] = []
        _nosht = {"day": "2026-08-15", "home": "Boston Red Sox",
                  "away": "New York Yankees", "home_id": "111",
                  "away_id": "147", "pick": "1 · Boston Red Sox"}
        check("нощният мач под вчерашната дата на графика СЕ намира",
              baseball_result(_nosht) == (5, 2))

        # -- чужд софийски ден: и по номер, и по име
        _mlb_days.clear()
        _mlb_days["2026-08-20"] = [("158", "134", 7, 1, "Milwaukee Brewers",
                                    "Pittsburgh Pirates", "2026-08-20")]
        _mlb_days["2026-08-21"] = []
        _mlb_days["2026-08-22"] = []
        _chuzhd = {"day": "2026-08-21", "home": "Milwaukee Brewers",
                   "away": "Pittsburgh Pirates", "home_id": "158",
                   "away_id": "134", "pick": "1 · Milwaukee Brewers"}
        check("чуждият софийски ден НЕ се отсъжда по номер",
              baseball_result(_chuzhd) is None)
        check("чуждият софийски ден НЕ се отсъжда и по име",
              baseball_result(dict(_chuzhd, home_id="", away_id="")) is None)

        # -- « не знам » не е « друг ден »: празна дата пази старото поведение
        _mlb_days["2026-08-20"] = [("158", "134", 7, 1, "Milwaukee Brewers",
                                    "Pittsburgh Pirates", "")]
        check("празната софийска дата НЕ изхвърля мача",
              baseball_result(_chuzhd) == (7, 1))

        # -- двойна програма: два мача същия ден пак дават резултат
        _mlb_days.clear()
        _mlb_days["2026-08-23"] = [
            ("120", "143", 2, 1, "Washington Nationals",
             "Philadelphia Phillies", "2026-08-23"),
            ("120", "143", 6, 4, "Washington Nationals",
             "Philadelphia Phillies", "2026-08-23")]
        _mlb_days["2026-08-22"] = []
        _mlb_days["2026-08-24"] = []
        check("двойната програма пак дава резултат",
              baseball_result({"day": "2026-08-23",
                               "home": "Washington Nationals",
                               "away": "Philadelphia Phillies",
                               "home_id": "120", "away_id": "143",
                               "pick": "1 · Washington Nationals"}) == (2, 1))

        # -- своят ден се пита ПРЪВ, дори когато съседният също съвпада
        _mlb_days.clear()
        _mlb_days["2026-08-25"] = [("133", "136", 1, 9, "Athletics",
                                    "Seattle Mariners", "2026-08-25")]
        _mlb_days["2026-08-24"] = [("133", "136", 9, 1, "Athletics",
                                    "Seattle Mariners", "2026-08-25")]
        _mlb_days["2026-08-26"] = []
        check("своят ден се пита пръв",
              baseball_result({"day": "2026-08-25", "home": "Athletics",
                               "away": "Seattle Mariners", "home_id": "133",
                               "away_id": "136",
                               "pick": "1 · Athletics"}) == (1, 9))
    finally:
        globals()["http_json"] = _s_hj
        _mlb_days.clear()
        _mlb_days.update(_s_mlb_kesh)
    check("мрежата е върната на истинската",
          globals()["http_json"] is _s_hj)

    # -- 🏐 ЗАКЛЮЧВАЩО ЗА ВОЛЕЙБОЛА (измерено 02.09.2026, не пипано)
    #  В живия дневник 53 от 219 волейболни записа носят сетов резултат В
    #  САМАТА прогноза — и ВСИЧКИТЕ 53 са пуснати до 11.08.2026 01:07.
    #  След 12.08 такъв запис няма нито един (0 от 168). Предсказателят го е
    #  извадил на 11.08 (виж predictor.py, « ОПРАВЕНО 11.08.2026 »). Тоест
    #  картата вече не обещава точен резултат и няма какво да се стяга тук.
    #  Проверката заковава ЧЕТИМОТО ОТ ОЦЕНИТЕЛЯ поведение: върне ли се
    #  някога сетовият резултат в текста, присъдата пак е по ПОБЕДИТЕЛЯ.
    _vol = {"pick": "2 · победа Корея (3:0)", "home": "Тайван",
            "away": "Корея", "bucket": "volleyball"}
    check("волейбол: сетовете в текста не менят присъдата по победител",
          verdict(_vol, 1, 3) is True)
    check("волейбол: същата карта пада, щом победителят е друг",
          verdict(_vol, 3, 1) is False)

    check("блокът за серията добави поне 20 свои проверки",
          ok - _ok_predi_serii >= 20)



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
# Под колко двойки „наша + пазарна вероятност" НЕ казваме нищо в стаята.
# По-високо от прага в диагностиката: там гледам аз, тук гледа човек.
PAZAR_MIN_KARTA = max(20, min(500, int((os.environ.get("SCORE_PAZAR_MIN") or "40").strip())))

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


# ══════════════════════════════════════════════════════════════════════════
#  ВРАТАТА КЪМ ПАЗАЧА СРЕЩУ ПОВТОРЕНА РАВНОСМЕТКА (26.08.2026)
#
#  ИЗМЕРЕНО ОФЛАЙН, НЕ ПРЕДПОЛОЖЕНО: main() пусната пет пъти с подменен
#  часовник дава 15 съобщения, от които 10 са ДОСЛОВНИ копия (ФИНИШ НА ДЕНЯ
#  към стая 9 и към канала, ДОСЕГА ОБЩО към стая 9). Единственият пазач в
#  целия файл е combo_done, и той е за фишовете. Досега това не личеше,
#  защото оценителят се пускаше два пъти на ден; от днес будилникът може да
#  го буди и без пазач каналът получава равносметка на всеки рън.
#
#  Решението и тефтерът живеят в budilnik.py (ravn_reshi / ravn_otbelezhi).
#  Тук е само вратата. Внасянето е през try/except: липсва ли будилникът,
#  оценителят праща КАКТО ПРЕДИ. Провалът е към шум, не към тишина — мълчалива
#  равносметка е точно аварията, срещу която строим.
#
#  ДВА АДРЕСА = ДВА КЛЮЧА. Финишът отива и в стая 9, и в канала със същия
#  текст. Един ключ за двата щеше да глътне второто пращане и каналът щеше да
#  остане без равносметка — обратната авария на тази, която лекуваме.
#
#  ПРИ СУХО ПУСКАНЕ (SCORE_DRY_RUN=1) НЕ СЕ ОТБЕЛЯЗВА НИЩО. Иначе една проба
#  на човек заключва истинското вечерно съобщение.
# ══════════════════════════════════════════════════════════════════════════

# Тефтерът. Празно = този на будилника (budilnik_state.json). Самопроверката
# го подменя с временен файл, за да мери ЖИВИЯ път, а не свое копие.
RAVN_SAST_FILE = (os.environ.get("SCORE_RAVN_FILE") or "").strip() or None

_RAVN_SAST = []          # кеш за рън: тефтерът се чете веднъж


def _bud_modul():
    """Будилникът или None. Липсва ли — оценителят праща както преди.

    Не стига `import budilnik` да мине: стар будилник без слоя ravn_* щеше да
    гръмне с AttributeError по средата на пращането. Проверява се, че всичките
    пет врати ги има, и чак тогава се вярва.
    """
    try:
        import budilnik
    except Exception:                                        # noqa: BLE001
        return None
    for ime in ("ravn_reshi", "ravn_otbelezhi", "izrezhi_stari",
                "cheti_sast", "pishi_sast"):
        if not callable(getattr(budilnik, ime, None)):
            return None
    return budilnik


def ravn_zabravi():
    """Забравя заредения тефтер: нов рън, нов прочит. За самопроверката."""
    del _RAVN_SAST[:]


def ravn_sast(b=None):
    """Тефтерът, четен ВЕДНЪЖ на рън."""
    if not _RAVN_SAST:
        b = _bud_modul() if b is None else b
        _RAVN_SAST.append(b.cheti_sast(RAVN_SAST_FILE) if b is not None else {})
    return _RAVN_SAST[0]


def ravn_adres_prati(adres, text):
    """Пращането по адрес: kanal -> каналът, всичко друго -> стая 9."""
    if str(adres) == "kanal":
        return bool(post_channel(text))
    return bool(post(RESULTS_THREAD, text))


def prati_ravnosmetka(now, den, vid, adres, text):
    """ЕДИНСТВЕНАТА врата за петте равносметки. Връща (пратено_ли, защо).

    vid:   obzor · finish · mezhdinna · dosega
    adres: staya (стая 9) · kanal
    Марката се слага САМО СЛЕД УСПЕШНО пращане. Обратното е дефектът, който
    седи в combo_done: падне ли пращането, съобщението е изгубено завинаги,
    защото марката твърди, че е минало.
    """
    b = _bud_modul()
    if b is None:
        print("  будилникът липсва — пращам БЕЗ пазач (" + str(vid) + "/"
              + str(adres) + ")")
        return ravn_adres_prati(adres, text), "няма будилник"
    sast = ravn_sast(b)
    mozhe, klyuch, _poreden, zashto = b.ravn_reshi(sast, den, vid, adres, text)
    if not mozhe:
        print("  ПАЗАЧ " + str(vid) + "/" + str(adres) + ": " + str(zashto))
        return False, zashto
    if not ravn_adres_prati(adres, text):
        return False, "пращането не мина — БЕЗ марка, за да се пробва пак"
    if DRY_RUN:
        return True, "сухо пускане — не отбелязвам нищо"
    b.ravn_otbelezhi(sast, klyuch, now)
    b.izrezhi_stari(sast, now)
    if not b.pishi_sast(sast, RAVN_SAST_FILE):
        print("  тефтерът НЕ се записа — следващият рън може да повтори.")
    return True, zashto


# ══════════════════════════════════════════════════════════════════════════
#  🎫 ВРАТАТА КЪМ ОТЧЕТА НА ФИШОВЕТЕ (26.08.2026) — БЛИЗНАКЪТ НА ГОРНАТА
#
#  ДЕФЕКТЪТ, ПРОЧЕТЕН В ЖИВИЯ ФАЙЛ: main() слагаше марката на всеки крак
#  ЧЕТИРИНАЙСЕТ РЕДА ПРЕДИ пращането в стая 10. Падне ли пращането —
#  мрежа, забранена дума, затворена стая — марката вече е в дневника и
#  save_log() я записва. Отчетът на този фиш е изгубен ЗАВИНАГИ: следващият
#  рън прескача краката, защото марката твърди, че са отчетени. Точно
#  обратното на prati_ravnosmetka, направена ден по-рано.
#
#  СЕГА: марката пада САМО след успешно пращане.
#
#  ОБРАТНАТА ОПАСНОСТ И КАК Е ЗАТВОРЕНА
#  Без марка следващият рън пробва пак. Това ражда два нови риска:
#
#    1) БЕЗКРАЕН ОПИТ. Пада ли пращането ВИНАГИ (забранена дума в текста,
#       затворена стая, спрян бот), кракът би се опитвал до края на
#       дневника. Затова всеки неуспех вдига combo_opiti и на COMBO_OPITI-я
#       отказ фишът се затваря с гръмък ред. Броячът се чисти при успех,
#       за да не се сумират отделни лоши дни.
#
#    2) ДУБЛИРАН ОТЧЕТ. Мине ли пращането, но отговорът се загуби (или
#       save_log падне), марката липсва и следващият рън праща СЪЩИЯ текст.
#       Затова пращането минава през ВТОРИ, независим тефтер — пазача на
#       будилника, по отпечатък на текста. Двата тефтера са РАЗЛИЧНИ файла
#       (predict_log.json и budilnik_state.json): за дубъл трябва да паднат
#       И ДВАТА записа.
#
#  ЧЕСТНО ЗА ГРАНИЦАТА: „пратено, но отговорът се загуби" НЕ се различава
#  от „не е пратено" от нашата страна — не пазим номера на съобщението,
#  за да го сверим. Затова изборът е съзнателен и е същият като на
#  равносметката: провалът е към ШУМ (един повторен отчет, който се вижда
#  и се трие), не към ТИШИНА (изгубен отчет, който никой не забелязва).
# ══════════════════════════════════════════════════════════════════════════

# Колко РАЗЛИЧНИ отчета на фишове за един ден. Не е мярка за приличие, а
# горна граница срещу подивял цикъл: реалният таван е 2 крона + 4 будения =
# 6 пускания на ден, тоест 12 не бие никога. Отчетът на фишовете е
# ИНКРЕМЕНТАЛЕН — всеки нов дозатворен фиш дава НОВ текст — затова ниският
# таван на равносметките (3) тук би ЯЛ отчети. Същата разлика, заради която
# обзорът има свой таван 8.
COMBO_TAVAN = max(1, min(40, int((os.environ.get("SCORE_COMBO_TAVAN")
                                  or "12").strip() or "12")))
# След колко неуспешни опита фишът се предава. Пет при ~6 пускания на ден
# значи „цял ден се опитва"; после мълчи, вместо да опитва вечно.
COMBO_OPITI = max(1, min(50, int((os.environ.get("SCORE_COMBO_OPITI")
                                  or "5").strip() or "5")))


def combo_prati(now, den, text):
    """Отчетът на фишовете в стая 10. Връща (да_се_маркира_ли, защо).

    Марката се слага от combo_marki СЛЕД този изход, никога преди него.
    """
    b = _bud_modul()
    if b is None:
        # Липсва ли будилникът, оценителят праща както преди — без втория
        # тефтер. Провалът е към шум, не към тишина.
        if post(WINS_THREAD, text):
            return True, "пратено БЕЗ пазач (будилникът липсва)"
        return False, "пращането не мина — БЕЗ марка, за да се пробва пак"
    sast = ravn_sast(b)
    mozhe, klyuch, _poreden, zashto = b.ravn_reshi(sast, den, "fish",
                                                   "staya10", text,
                                                   tavan=COMBO_TAVAN)
    if not mozhe:
        # Пазачът помни ТОЧНО този текст (или таванът е стигнат). Ново
        # пращане би дало дубъл, а нов опит утре — вечен цикъл. Затова:
        # без пращане, НО С МАРКА.
        print("  ПАЗАЧ фиш: " + str(zashto))
        return True, zashto
    if not post(WINS_THREAD, text):
        return False, "пращането не мина — БЕЗ марка, за да се пробва пак"
    if DRY_RUN:
        # Една проба на човек не бива да заключва истинския отчет.
        return True, "сухо пускане — не отбелязвам нищо"
    b.ravn_otbelezhi(sast, klyuch, now)
    b.izrezhi_stari(sast, now)
    if not b.pishi_sast(sast, RAVN_SAST_FILE):
        print("  тефтерът НЕ се записа — вторият пазач на фиша е сляп.")
    return True, zashto


def combo_marki(prateno, legs, tavan=None):
    """Слага марките СЛЕД изхода на пращането. Чиста: без мрежа и файлове.

    Връща (затворени, оставени_за_нов_опит).
    """
    tavan = COMBO_OPITI if tavan is None else tavan
    zatvoreni, ostavat = 0, 0
    for r in legs:
        if prateno:
            r["combo_done"] = True
            r.pop("combo_opiti", None)
            zatvoreni += 1
            continue
        n = int(r.get("combo_opiti") or 0) + 1
        r["combo_opiti"] = n
        if n >= tavan:
            r["combo_done"] = True      # предавам се, за да не опитвам вечно
            zatvoreni += 1
        else:
            ostavat += 1
    return zatvoreni, ostavat


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
    # 🗄️ Приключените стари записи излизат от горещия дневник. Виж дългото
    # обяснение при ARHIV_DNI: 12 MB за две години, четени и записвани 30 пъти
    # на ден. Мести се само приключено — висящото остава, колкото и старо да е.
    rows, _preseleni = arhiviray(rows, now)
    if _preseleni:
        print("Архивирани " + str(_preseleni) + " приключени записа → "
              + ARHIV_FILE + " (горещият дневник остава " + str(len(rows)) + ").")

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
        # 🔴 ОТЛОЖЕН/ОТМЕНЕН — затваря се ВЕДНАГА, без присъда (19.08.2026).
        # Без този клон записът се питаше слепешком дни наред („Braga — Gil
        # Vicente", 3 дни), а числото „чакат резултат" лъжеше, че предстои
        # нещо. Мач, който не се е състоял, не е нито познат, нито сгрешен.
        if res == OTLOZHEN:
            r["scored"] = True
            r["hit"] = None
            r["why"] = "мачът е отложен или отменен"
            continue
        hs, as_ = res
        ok_hit = verdict(r, hs, as_)
        if ok_hit is None:
            r["scored"] = True
            r["hit"] = None
            continue
        r["scored"] = True
        r["hit"] = bool(ok_hit)
        r["score"] = str(hs) + ":" + str(as_)
        # Мачът е свършил -> затварящата цена вече съществува. Сега е ЕДИН-
        # СТВЕНИЯТ момент, в който може да се вземе: после записът се архивира.
        try:
            if hvani_zatvaryashta(r):
                time.sleep(0.3)
        except Exception:                                    # noqa: BLE001
            pass
        fresh.append((r, hs, as_, bool(ok_hit)))

    print("Проверени " + str(checked) + mn(checked, " твърдение", " твърдения")
          + mn(len(fresh), ", отсъдено ", ", отсъдени ") + str(len(fresh)) + ".")

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
    # Видът на равносметката за пазача: обяд ражда ДОКЪДЕ СМЕ, вечер ФИНИШ.
    # Будилникът търси точно тези две думи, за да знае дали е излязла.
    vid_ravn = "mezhdinna" if obed else "finish"

    if not fresh:
        save_log(rows)
        if vecher or obed:
            finish = den_finish_text(now, rows, den, mezhdinna=obed)
            prati_ravnosmetka(now, den, vid_ravn, "staya", finish)
            time.sleep(1.5)
            prati_ravnosmetka(now, den, vid_ravn, "kanal", finish)
            # 🧾 И ВЕДНАГА СЛЕД ФИНИША — целият живот на бота. Само вечер:
            # обядът си има междинната, а трето съобщение по обяд е шум.
            if vecher:
                time.sleep(1.5)
                prati_ravnosmetka(now, den, "dosega", "staya",
                                  obshto_dosega_text(now, cyal_dnevnik(rows)))
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
    prati_ravnosmetka(now, den, "obzor", "staya", obzor)
    # И В КАНАЛА. Поръчка на собственика: „искаме всичко да си е вътре след
    # края на деня". Провалът тук НЕ отменя поста в стаята — той вече е минал.
    time.sleep(1.5)
    prati_ravnosmetka(now, den, "obzor", "kanal", obzor)
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
        # bez_sportove=True: обзорът горе вече показа разбивката по спорт за
        # ТОВА пускане. Два реда „⚽ Футбол N от M" с различни знаменатели на
        # 2 секунди разстояние четат като грешка. Виж бележката в самата
        # функция. В другия клон (без обзор) флагът НЕ се подава.
        finish = den_finish_text(now, rows, den, mezhdinna=obed,
                                 bez_sportove=True)
        prati_ravnosmetka(now, den, vid_ravn, "staya", finish)
        time.sleep(1.5)
        prati_ravnosmetka(now, den, vid_ravn, "kanal", finish)
        # 🧾 И веднага след него — целият живот на бота. Виж близнака по-горе.
        if vecher:
            time.sleep(1.5)
            prati_ravnosmetka(now, den, "dosega", "staya",
                              obshto_dosega_text(now, cyal_dnevnik(rows)))

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
                  + " от " + str(len(legs)) + mn(len(legs), " крак", " крака")
                  + mn(len(chakat), " чака", " чакат") + " резултат.")
            continue
        sudimi = [r for r in legs if r.get("hit") is not None]
        if not sudimi:
            # НЯМА КАКВО ДА СЕ ПРАЩА, значи няма и какво да се загуби —
            # само тук марката може да падне веднага. Навсякъде другаде
            # тя чака изхода на пращането (виж combo_prati).
            for r in legs:
                r["combo_done"] = True
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
        # 🔴 МАРКАТА ПАДА СЛЕД ПРАЩАНЕТО, НЕ ПРЕДИ НЕГО (26.08.2026).
        # Дотук r["combo" + "_done"] се вдигаше четиринайсет реда по-горе,
        # преди post(). Виж дългото обяснение при combo_prati.
        # Стая 10 е „Печеливши фишове" — тук е мястото на фиша, не на числата.
        _zasegnati = [x for _kl, _lg in gotovi for x in slips[_kl]]
        prateno, zashto = combo_prati(now, today, combo_text(now, gotovi))
        _zatv, _ost = combo_marki(prateno, _zasegnati)
        if not prateno:
            print("Отчетът на фишовете НЕ мина (" + str(zashto) + "): "
                  + str(_ost) + " крака остават БЕЗ марка за нов опит, "
                  + str(_zatv) + " се предават след " + str(COMBO_OPITI)
                  + " опита.")

    save_log(rows)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv or os.environ.get("SCORE_SELFTEST") == "1":
        sys.exit(selftest())
    sys.exit(main())
