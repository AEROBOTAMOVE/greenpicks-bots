# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БОТ „ПРЕДСКАЗАТЕЛЯТ" 🧠🔢

ПРОГНОЗА, а не есе. Всяка карта е кратка и започва с това, което моделът
избира, и с колко процента. Обясненията са най-много два реда.

ЕДИН ИЗХОД: стая 27 „БОТА ПРЕДРИЧА" (PREDICT_THREAD_ID).
Стая 4 (човешките фишове) и стая 26 (новините) са заковани като забранени
в post_predict(). Този файл физически няма функция за канал.
Стая 328 „Бойни спортове" НЕ е забранена — тя просто не е стаята на
Предсказателя: там ходят само предстоящите боеве (matches_bot.py), а
прогнозите за тях — като всички останали — излизат в стая 27.

СПОРТОВЕ И ИЗТОЧНИЦИ (всички без ключ, проверени на 28.07.2026):
  🥊 ММА / UFC + PFL   ESPN mma        Elo по боевете + рекорд от кариерата
  🏓 Тенис на маса     WTT / ITTF      процент победи за 18 месеца
  🏐 Волейбол          FIVB VIS (XML)  разигравания -> сет -> мач
  🏀 Баскетбол         ESPN nba/wnba   темпо и ефективност
  🎾 Тенис ATP/WTA     ESPN tennis     ранглиста + форма
  🏒 Хокей NHL         api-web.nhle    Поасон по голове
  ⚽ Футбол            ESPN soccer     Поасон с корекция Диксън-Коулс
  ⚾ Бейзбол MLB       statsapi.mlb    рънове за и против

ЗАЩО СМЕНИХМЕ ИЗТОЧНИЦИТЕ. Безплатният ключ на TheSportsDB връща 1-3
изиграни мача на отбор. С такава история никой модел не може да смята и
затова ботът мълчеше. ESPN дава 38 мача на отбор за сезон (114 за три
сезона), NHL дава 82, FIVB дава хиляди. TheSportsDB остава само като
последна резерва.

БОКС: НЯМА безплатен източник. ESPN няма бокс (четири адреса, всички 400).
Не измисляме — боксът просто липсва, докато не се плати за данни.

ЧЕСТНОСТТА Е ПРОДУКТЪТ:
  - Числото е ВЕРОЯТНОСТ от статистика. Не е гаранция и не е съвет за залог.
  - Звездите идват от реалната извадка. Малка извадка = една звезда и го пишем.
  - Никакви букмейкъри, никакви коефициенти. Пазачът в post_predict реже
    всяко съобщение, в което се е промъкнала такава дума.
  - Нищо не се трие. И сгрешените прогнози остават.
  - Мълчим само когато наистина няма история. Постоянният отказ е дефект.
  - Започнал мач НЕ получава прогноза. Осем пускания на ден значи, че в 19:00
    списъкът още помни мачовете от 13:00 — карта за започнала среща е по-лоша
    от мълчание и се реже в collect_all.
  - Една среща = ЕДНА карта, завинаги. Ключът в тефтера виси на деня на МАЧА,
    не на деня на пускането, затова гала, видяна пет дни предварително, излиза
    веднъж, а не по веднъж на ден.

ENV:
  BOT_TOKEN, CHAT_ID
  PREDICT_THREAD_ID  (27)     единствената разрешена стая
  MAX_PICKS          (4)      колко карти максимум за едно пускане
  PREDICT_POOL       (14)     колко срещи влизат под лупата
  PREDICT_PER_SPORT  (3)      най-много кандидати от един спорт
  PREDICT_MIN_STRENGTH (0.10) прагът „има ли изобщо превес"
  PREDICT_SPORTS     ()       списък с запетаи; празно = всички
  PREDICT_HTTP_BUDGET (220)   таван на заявките за едно пускане
  PREDICT_MAX_DAY    (10)     таван прогнози за ЦЕЛИЯ ден (осем пускания!)
  PREDICT_HORIZON_H  (30)     докъде напред гледаме; по-далечното чака реда си
  PREDICT_LEAD_MIN   (10)     минути преди начало, след които не пускаме карта
  PREDICT_STATE_KEEP (8)      колко дни помни тефтерът
  PREDICT_STATE_FILE (predict_state.json)
  PREDICT_DRY_RUN    (0/1)    1 = само печата картите
  FOOTBALL_DATA_KEY, SPORTSDB_KEY — само за резервата през matches_bot

Пускане:
  python predictor.py             истинско пускане (или сухо по env)
  python predictor.py selftest    само математиката и пазачите, без мрежа

Бележка за деплой: файлът е писан БЕЗ обратни наклонени черти (нов ред = NL)
и без обратни апострофи. Пращаме сами, а не през poster.send_message, защото
при 429 ни трябва retry_after — poster не го връща.

Бележка за workflow: тенисът на маса иска „pip install brotli" (CDN-ът на WTT
винаги отговаря сгъстено с brotli). Няма ли модула — само тенисът на маса
се пропуска с ясен ред в лога, всичко останало работи.
"""
import gzip
import html
import json
import math
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    import matches_bot as MB          # само като резерва — MB.main() НЕ се вика
except Exception as _mb_err:          # noqa: BLE001
    MB = None
    print("matches_bot не се зареди (" + str(_mb_err)[:80] + ") — карам без резервата.")

SOFIA = ZoneInfo("Europe/Sofia")
NL = chr(10)
NL2 = chr(10) + chr(10)
Q1 = chr(8222)     # „
Q2 = chr(8220)     # "
DASH = chr(8211)   # –
RULE = chr(9472) * 18

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "-1004426592150")
PREDICT_THREAD = (os.environ.get("PREDICT_THREAD_ID") or "27").strip()

# 🚫 Стаята на човека-типстер и стаята на новините. Ботът няма работа там.
FORBIDDEN_THREADS = {"4", "26"}
ALLOWED_THREADS = {PREDICT_THREAD}

DRY_RUN = (os.environ.get("PREDICT_DRY_RUN") or "").strip() in ("1", "true", "yes", "да")


def env_int(name, default, lo, hi):
    try:
        v = int((os.environ.get(name) or "").strip())
    except ValueError:
        v = default
    return max(lo, min(hi, v))


def env_float(name, default, lo, hi):
    try:
        v = float((os.environ.get(name) or "").strip())
    except ValueError:
        v = default
    return max(lo, min(hi, v))


MAX_PICKS = env_int("MAX_PICKS", 4, 1, 6)
POOL = env_int("PREDICT_POOL", 14, 1, 40)
PER_SPORT = env_int("PREDICT_PER_SPORT", 3, 1, 8)
MIN_STRENGTH = env_float("PREDICT_MIN_STRENGTH", 0.10, 0.0, 0.9)
HTTP_BUDGET = env_int("PREDICT_HTTP_BUDGET", 220, 10, 900)
TENNIS_SWEEP = env_int("PREDICT_TENNIS_SWEEP", 8, 0, 30)
MMA_DAYS_AHEAD = env_int("PREDICT_MMA_DAYS", 5, 0, 21)
STATE_FILE = (os.environ.get("PREDICT_STATE_FILE") or "predict_state.json").strip()
# Колко минути ПРЕДИ първия съдийски сигнал спираме да пускаме карта. Прогноза
# за започнал мач е по-лоша от мълчание — ботът пуска само неиграни срещи.
LEAD_MIN = env_int("PREDICT_LEAD_MIN", 10, 0, 240)
# Докъде напред гледаме. ММА вижда галата пет дни предварително — карта,
# пусната пет дни по-рано, е забравена, докато боят започне. С осем пускания
# на ден няма нужда да бързаме: срещата се пуска, когато влезе в прозореца.
HORIZON_H = env_int("PREDICT_HORIZON_H", 30, 2, 240)
# Таван за ЦЕЛИЯ ден. Осем пускания по MAX_PICKS биха дали 32 карти — стаята
# не е лента с новини. Тавана го брои тефтерът, не отделното пускане.
MAX_DAY = env_int("PREDICT_MAX_DAY", 10, 1, 40)
# Тефтерът пази толкова дни назад. Трябва да е ПО-ГОЛЯМО от най-далечния
# хоризонт на събирането (ММА гледа 5 дни напред), иначе една гала, пусната
# днес, се забравя и се пуска втори път след три дни.
STATE_KEEP_DAYS = env_int("PREDICT_STATE_KEEP", 8, 3, 40)
SEND_GAP = 2.2          # секунди между съобщенията — 429 не ни е приятел
HTTP_GAP = 0.35         # дишаме между заявките към чуждите API-та

# ---------------------------------------------------------------- СПОРТОВЕТЕ
SPORTS = {
    "mma":         {"emoji": "🥊", "title": "ММА / UFC", "prio": 95,
                    "model": "Elo по боевете + рекорд"},
    "tabletennis": {"emoji": "🏓", "title": "Тенис на маса", "prio": 90,
                    "model": "процент победи"},
    "volleyball":  {"emoji": "🏐", "title": "Волейбол", "prio": 85,
                    "model": "разигравания и сетове"},
    "basketball":  {"emoji": "🏀", "title": "Баскетбол", "prio": 80,
                    "model": "темпо и ефективност"},
    "tennis":      {"emoji": "🎾", "title": "Тенис", "prio": 70,
                    "model": "ранглиста и форма"},
    "hockey":      {"emoji": "🏒", "title": "Хокей", "prio": 60,
                    "model": "Поасон по голове"},
    "football":    {"emoji": "⚽", "title": "Футбол", "prio": 30,
                    "model": "Поасон, Диксън-Коулс"},
    "baseball":    {"emoji": "⚾", "title": "Бейзбол", "prio": 20,
                    "model": "рънове за и против"},
}
# Футболът е последен по изрична заповед на шефа. Бейзболът е след него.
SPORT_ORDER = ["mma", "tabletennis", "volleyball", "basketball",
               "tennis", "hockey", "football", "baseball"]

_want = [s.strip().lower() for s in (os.environ.get("PREDICT_SPORTS") or "").split(",") if s.strip()]
ACTIVE_SPORTS = [s for s in SPORT_ORDER if (not _want or s in _want)]

# Звездите говорят сами (легендата е в подписа) — картата не носи думи за тях.
# Таван на звездите там, където сама по себе си дисциплината е непредсказуема.
STAR_CAP = {"mma": 2, "tabletennis": 2, "baseball": 2, "tennis": 3,
            "volleyball": 3, "football": 3, "basketball": 3, "hockey": 3}
# Минимална извадка на страна. 0 = спортът има собствена проверка за достатъчност.
# 0 = спортът НЕ минава през общата проверка, защото носи собствена. Волейболът
# и тенисът на маса броят извадката вътре в модела си (рейтинг, не списък мачове);
# ако ги оставим тук с число, общата проверка вижда празен списък и ги убива ВСИЧКИТЕ.
MIN_PER_SIDE = {"football": 5, "basketball": 5, "volleyball": 0, "tabletennis": 0,
                "tennis": 0, "mma": 0, "hockey": 0, "baseball": 10}
# Спортовете, които наистина връщат списък с изиграни мачове през history_for().
# Всеки ДРУГ спорт ЗАДЪЛЖИТЕЛНО стои с 0 по-горе. Самопроверката го пази —
# сгрешено число тук не чупи нищо шумно, просто убива мълчаливо цял спорт.
HISTORY_SPORTS = {"football", "basketball", "baseball"}

WEEKDAYS = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]

# 🚨 Думи, които НЕ МОГАТ да напуснат този бот. Българският закон забранява
# рекламата на хазарт; източниците (ESPN summary, football-data CSV) носят
# коефициенти и имена на букмейкъри. Пазачът е на изхода, не на входа.
BANNED_TOKENS = ["bet365", "pinnacle", "bwin", "efbet", "winbet", "palmsbet",
                 "betano", "1xbet", "betfred", "unibet", "sesame", "pickcenter",
                 "коеф", "букмейкър", "odds", "залагай", "заложи"]


# ---------------------------------------------------------------- ДРЕБНИ ИНСТРУМЕНТИ
def esc(x):
    # quote=False нарочно: Telegram иска само &amp; &lt; &gt;. С quote=True
    # апострофът става &#x27; и се вижда като боклук в „Men's Singles".
    return html.escape(str(x if x is not None else ""), quote=False)


def clip(text, limit=3900):
    if len(text) <= limit:
        return text
    return text[:limit] + NL + "…(отрязано)"


def pct(p):
    return str(int(round(float(p) * 100.0))) + "%"


def to_num(x):
    try:
        if x is None or str(x).strip() == "":
            return None
        return int(float(x))
    except (TypeError, ValueError):
        return None


def to_f(x, default=None):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def mean(xs):
    xs = list(xs)
    return sum(xs) / float(len(xs)) if xs else 0.0


def n_match(n):
    return str(n) + (" среща" if int(n) == 1 else " срещи")


def date_bg(now):
    return WEEKDAYS[now.weekday()] + ", " + str(now.day) + "." + ("%02d" % now.month)


# Схемите на турнирите носят празни слотове, докато предният кръг свърши.
# „TBD срещу Тейлър Фриц" не е среща и не бива да стига до карта.
PLACEHOLDERS = ["tbd", "bye", "qualifier", "winner of", "loser of", "to be confirmed", "n/a"]


def is_placeholder(name):
    t = str(name or "").strip().lower()
    if not t:
        return True
    return any(t == p or t.startswith(p) for p in PLACEHOLDERS)


def norm_key(s):
    out = []
    for ch in str(s if s is not None else "").lower():
        if ch.isalnum():
            out.append(ch)
    return "".join(out)


def parse_iso(s):
    """ESPN дава „2026-05-24T15:00Z" (без секунди), FIVB дава без Z изобщо."""
    t = str(s or "").strip()
    if not t:
        return None
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
            try:
                d = datetime.strptime(t[:len(fmt) + 2], fmt)
                break
            except ValueError:
                d = None
        if d is None:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def days_between(iso_date, now):
    d = parse_iso(iso_date)
    if d is None:
        return None
    return (now - d).total_seconds() / 86400.0


def when_label(dt_utc, now):
    """Час по българско, а ако мачът е за друг ден — и денят."""
    if dt_utc is None:
        return ""
    loc = dt_utc.astimezone(SOFIA)
    hm = loc.strftime("%H:%M")
    delta = (loc.date() - now.date()).days
    if delta == 0:
        return hm
    if delta == 1:
        return "утре " + hm
    if delta == -1:
        return "вчера " + hm
    return WEEKDAYS[loc.weekday()] + ", " + str(loc.day) + "." + ("%02d" % loc.month) + " " + hm


def fx_start(fx, now):
    """Кога започва срещата — час със зона, или None ако източникът не е казал.

    Повечето източници дават пълна дата в полето „when". Последната резерва
    (TheSportsDB) дава само „21:30" вече по българско и без ден. Един капан:
    мач в 23:40 UTC днес е 02:40 БЪЛГАРСКО за УТРЕ, а низът пази само часа.
    Затова час преди 05:00, погледнат след обяд, се чете като утрешен."""
    w = fx.get("when")
    if isinstance(w, datetime):
        return w if w.tzinfo is not None else w.replace(tzinfo=timezone.utc)
    t = str(fx.get("time") or "").strip()[:5]
    if len(t) == 5 and t[2] == ":" and t[:2].isdigit() and t[3:].isdigit():
        hh, mm = int(t[:2]), int(t[3:])
        if hh > 23 or mm > 59:
            return None
        loc = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if hh < 5 and now.hour >= 12:
            loc = loc + timedelta(days=1)
        return loc
    return None


def started(fx, now):
    """True = мачът вече тече, свършил е, или започва прекалено скоро.
    Не гадаем: няма ли източникът час, срещата минава напред."""
    s = fx_start(fx, now)
    if s is None:
        return False
    return s <= now + timedelta(minutes=LEAD_MIN)


def too_far(fx, now):
    """True = срещата е още далече. Не я пропускаме — изчакваме я.
    Следващото пускане е след три часа и тя ще влезе в прозореца сама."""
    s = fx_start(fx, now)
    if s is None:
        return False
    return s > now + timedelta(hours=HORIZON_H)


def bg_name(s):
    """Малка карта на имената. Каквото не е в нея, остава както го дава източникът."""
    t = str(s or "").strip()
    return BG_NAME.get(t, t)


BG_NAME = {
    # държави (волейбол, ММА, национални отбори)
    "Bulgaria": "България", "Italy": "Италия", "Poland": "Полша", "France": "Франция",
    "Brazil": "Бразилия", "Japan": "Япония", "USA": "САЩ", "U.S.A.": "САЩ",
    "United States": "САЩ", "Serbia": "Сърбия", "Germany": "Германия",
    "Netherlands": "Нидерландия", "Slovenia": "Словения", "Argentina": "Аржентина",
    "Canada": "Канада", "China": "Китай", "Cuba": "Куба", "Iran": "Иран",
    "Turkey": "Турция", "Ukraine": "Украйна", "Czechia": "Чехия", "Greece": "Гърция",
    "Spain": "Испания", "Portugal": "Португалия", "Belgium": "Белгия",
    "Croatia": "Хърватия", "Romania": "Румъния", "Sweden": "Швеция",
    "Norway": "Норвегия", "Denmark": "Дания", "Finland": "Финландия",
    "Egypt": "Египет", "Tunisia": "Тунис", "Mexico": "Мексико", "Korea": "Корея",
    "Algeria": "Алжир", "Morocco": "Мароко", "Cameroon": "Камерун", "Nigeria": "Нигерия",
    "India": "Индия", "Pakistan": "Пакистан", "Sri Lanka": "Шри Ланка",
    "Bangladesh": "Бангладеш", "Uzbekistan": "Узбекистан", "Thailand": "Тайланд",
    "Chinese Taipei": "Тайван", "Indonesia": "Индонезия", "Philippines": "Филипини",
    "Vietnam": "Виетнам", "Qatar": "Катар", "Bahrain": "Бахрейн", "Israel": "Израел",
    "Estonia": "Естония", "Latvia": "Латвия", "Lithuania": "Литва",
    "Bosnia and Herzegovina": "Босна и Херцеговина", "North Macedonia": "Северна Македония",
    "Montenegro": "Черна гора", "Ireland": "Ирландия", "Iceland": "Исландия",
    "Chile": "Чили", "Colombia": "Колумбия", "Peru": "Перу", "Venezuela": "Венецуела",
    "Australia": "Австралия", "Switzerland": "Швейцария", "Austria": "Австрия",
    "Hungary": "Унгария", "Slovakia": "Словакия", "England": "Англия",
    "Russia": "Русия", "Belarus": "Беларус", "Kazakhstan": "Казахстан",
    "Puerto Rico": "Пуерто Рико", "Dominican Republic": "Доминиканска република",
    # футбол — клубовете, които българинът чете най-често
    "Real Madrid": "Реал Мадрид", "Barcelona": "Барселона",
    "Atletico Madrid": "Атлетико Мадрид", "Manchester City": "Манчестър Сити",
    "Manchester United": "Манчестър Юнайтед", "Liverpool": "Ливърпул",
    "Arsenal": "Арсенал", "Chelsea": "Челси", "Tottenham Hotspur": "Тотнъм",
    "Newcastle United": "Нюкасъл", "Aston Villa": "Астън Вила",
    "West Ham United": "Уест Хем", "Crystal Palace": "Кристъл Палас",
    "Everton": "Евертън", "Bayern Munich": "Байерн Мюнхен",
    "Borussia Dortmund": "Борусия Дортмунд", "RB Leipzig": "РБ Лайпциг",
    "Bayer Leverkusen": "Байер Леверкузен", "Juventus": "Ювентус",
    "Inter Milan": "Интер", "AC Milan": "Милан", "Napoli": "Наполи",
    "AS Roma": "Рома", "Lazio": "Лацио", "Atalanta": "Аталанта",
    "Paris Saint-Germain": "ПСЖ", "Marseille": "Марсилия", "Monaco": "Монако",
    "Lyon": "Лион", "Ajax": "Аякс", "PSV Eindhoven": "ПСВ",
    "Feyenoord": "Файенорд", "Benfica": "Бенфика", "FC Porto": "Порто",
    "Sporting CP": "Спортинг Лисабон", "Galatasaray": "Галатасарай",
    "Fenerbahce": "Фенербахче", "Besiktas": "Бешикташ", "Celtic": "Селтик",
    "Rangers": "Рейнджърс", "Olympiacos": "Олимпиакос", "Panathinaikos": "Панатинайкос",
    "Sevilla": "Севиля", "Real Betis": "Бетис", "Villarreal": "Виляреал",
    "Athletic Club": "Атлетик Билбао", "Real Sociedad": "Реал Сосиедад",
    "Valencia": "Валенсия",
    # баскетбол
    "Los Angeles Lakers": "ЛА Лейкърс", "Boston Celtics": "Бостън Селтикс",
    "Golden State Warriors": "Голдън Стейт", "Denver Nuggets": "Денвър Нъгетс",
    "Milwaukee Bucks": "Милуоки Бъкс", "Miami Heat": "Маями Хийт",
    "New York Knicks": "Ню Йорк Никс", "Chicago Bulls": "Чикаго Булс",
    "Phoenix Suns": "Финикс Сънс", "Dallas Mavericks": "Далас Маверикс",
    "Philadelphia 76ers": "Филаделфия", "Oklahoma City Thunder": "Оклахома Сити",
    "Real Madrid Baloncesto": "Реал Мадрид",
}


# ---------------------------------------------------------------- МРЕЖА
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_http_cache = {}
_http_used = [0]
_http_fail = [0]


def _brotli(raw):
    try:
        import brotli as _br
        return _br.decompress(raw)
    except ImportError:
        pass
    try:
        import brotlicffi as _br2
        return _br2.decompress(raw)
    except ImportError:
        pass
    raise RuntimeError("нужен е модул brotli (pip install brotli)")


def http_bytes(url, headers=None, timeout=30):
    """Една заявка навън, с таван, пауза и разсгъстяване. Хвърля при провал."""
    if _http_used[0] >= HTTP_BUDGET:
        raise RuntimeError("изчерпан лимит заявки (" + str(HTTP_BUDGET) + ")")
    hd = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hd.update(headers)
    time.sleep(HTTP_GAP)
    _http_used[0] += 1
    req = urllib.request.Request(url, headers=hd)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
    if "br" in enc:
        raw = _brotli(raw)
    elif "gzip" in enc:
        raw = gzip.decompress(raw)
    elif "deflate" in enc:
        raw = zlib.decompress(raw)
    return raw


def http_text(url, headers=None, timeout=30):
    key = ("t", url)
    if key in _http_cache:
        return _http_cache[key]
    txt = http_bytes(url, headers, timeout).decode("utf-8-sig", "replace")
    _http_cache[key] = txt
    return txt


def http_json(url, headers=None, timeout=30, quiet=False):
    """Връща None при всякакъв провал — нито един спорт не бива да събори рън."""
    key = ("j", url)
    if key in _http_cache:
        return _http_cache[key]
    try:
        data = json.loads(http_text(url, headers, timeout) or "null")
    except Exception as e:                      # noqa: BLE001
        _http_fail[0] += 1
        if not quiet:
            print("   ⚠ " + url[:78] + " -> " + str(e)[:70])
        data = None
    _http_cache[key] = data
    return data


# ---------------------------------------------------------------- ТЕФТЕРЪТ
def _empty_state():
    return {"v": 1, "posted": {}}


def load_state():
    """Самолекуващ се: счупен или чужд JSON = започваме начисто, без да падаме."""
    try:
        with open(STATE_FILE, encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("posted"), dict):
            return {"v": 1, "posted": dict(d["posted"])}
        if isinstance(d, list):     # мост от най-стар формат: само списък ключове
            return {"v": 1, "posted": {str(k): "" for k in d if isinstance(k, str)}}
        print("тефтерът " + STATE_FILE + " е с непознат вид — започвам начисто.")
    except FileNotFoundError:
        pass
    except Exception as e:          # noqa: BLE001
        print("тефтерът " + STATE_FILE + " е повреден (" + str(e)[:60] + ") — започвам начисто.")
    return _empty_state()


def save_state(state, now):
    """Пазим само последните дни — файлът не бива да расте вечно.
    Прозорецът е по-широк от хоризонта на събирането нарочно (виж
    STATE_KEEP_DAYS): забравен запис = повторена карта."""
    keep = set()
    for i in range(0, STATE_KEEP_DAYS):
        keep.add((now - timedelta(days=i)).strftime("%Y-%m-%d"))
    posted = {k: v for k, v in (state.get("posted") or {}).items() if str(v)[:10] in keep}
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"v": 1, "posted": posted}, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)     # атомарно: убит рън не оставя счупен JSON
        return True
    except Exception as e:              # noqa: BLE001
        print("тефтерът не се записа (" + str(e)[:70] + ") — следващият рън може да повтори.")
        return False


def match_key(fx, now):
    """Ключ на срещата. Стабилен през източниците и през пусканията.

    Датата в ключа е ДЕНЯТ НА МАЧА, не денят на пускането. Така една гала на
    ММА, която се вижда пет дни предварително, получава един и същ ключ на
    всяко пускане и излиза точно веднъж. (Няма ли час, падаме на днешния ден.)
    „vb" отделя мъжете от жените и от юношите: България - Италия при мъжете и
    България - Италия при жените са ДВЕ различни срещи в един и същи ден и без
    тази добавка втората карта мълчаливо се брои за повторение."""
    tag = norm_key((fx.get("extra") or {}).get("vb") or "")
    s = fx_start(fx, now)
    day = (s.astimezone(SOFIA) if s is not None else now).strftime("%Y-%m-%d")
    return (day + "|" + str(fx.get("bucket"))
            + (("|" + tag) if tag else "")
            + "|" + norm_key(fx.get("home"))[:24] + "|" + norm_key(fx.get("away"))[:24])


def already_posted(state, key):
    return key in (state.get("posted") or {})


def mark_posted(state, key, now):
    state.setdefault("posted", {})[key] = now.strftime("%Y-%m-%d %H:%M")


SERVICE_KEYS = ("|header", "|footer", "|nothing")


def posted_today(state, now):
    """Пуснато ли е ВЕЧЕ нещо днес? (осем пускания на ден — трябва да знаем)"""
    d = now.strftime("%Y-%m-%d")
    return any(str(v)[:10] == d for v in (state.get("posted") or {}).values())


def cards_today(state, now):
    """Колко ПРОГНОЗИ са излезли днес. Заглавието и подписът не се броят —
    те не са прогнози и не бива да ядат от дневния таван."""
    d = now.strftime("%Y-%m-%d")
    n = 0
    for k, v in (state.get("posted") or {}).items():
        if str(v)[:10] != d or str(k).endswith(SERVICE_KEYS):
            continue
        n += 1
    return n


def persist(state, now):
    """Записва тефтера, но НИКОГА при сухо пускане: иначе пробното пускане
    отбелязва мачовете като пуснати и истинското после мълчи."""
    if DRY_RUN:
        return False
    return save_state(state, now)


# ---------------------------------------------------------------- ЕДИНСТВЕНИЯТ ИЗХОД
def banned_word(text):
    """Връща първата забранена дума в текста или None. Пазач срещу хазартна реклама."""
    low = str(text or "").lower()
    for w in BANNED_TOKENS:
        if w in low:
            return w
    return None


def tg_send(text, thread_id):
    """Праща с уважение към 429: чете retry_after и чака, вместо да блъска."""
    payload = {"chat_id": str(CHAT_ID), "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": "true"}
    tid = str(thread_id or "").strip()
    if tid.isdigit() and int(tid) > 1:
        payload["message_thread_id"] = tid
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    for attempt in range(4):
        data = urllib.parse.urlencode(payload).encode()
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=25) as r:
                return bool(json.loads(r.read().decode("utf-8", "replace")).get("ok"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            wait = 0
            try:
                wait = int(((json.loads(raw) or {}).get("parameters") or {}).get("retry_after") or 0)
            except Exception:       # noqa: BLE001
                wait = 0
            if e.code == 429 and attempt < 3:
                wait = wait if wait > 0 else 5
                print("429 — чакам " + str(wait + 1) + " сек и пробвам пак")
                time.sleep(wait + 1)
                continue
            print("sendMessage HTTP " + str(e.code) + " " + raw[:180])
            return False
        except Exception as ex:     # noqa: BLE001
            print("sendMessage FAIL: " + str(ex)[:140])
            if attempt < 3:
                time.sleep(3)
                continue
            return False
    return False


def post_predict(text, thread_id=None):
    """ЕДИНСТВЕНИЯТ изход на Предсказателя. Пазачите са ТУК, не по-нагоре.
    Всичко, което този бот произвежда, влиза само в стая 27 „БОТА ПРЕДРИЧА".
    Канал няма — този файл няма функция, която да праща в канал."""
    tid = str(thread_id if thread_id is not None else PREDICT_THREAD).strip()
    if tid in FORBIDDEN_THREADS:
        print("ОТКАЗ: стая " + tid + " е забранена (човешки фишове / новини).")
        return False
    if tid not in ALLOWED_THREADS:
        print("ОТКАЗ: стая " + tid + " не е стаята на Предсказателя (" + PREDICT_THREAD + ").")
        return False
    if not tid.isdigit() or int(tid) <= 1:
        print("WARN: невалиден thread id " + tid + " — не пращам.")
        return False
    bad = banned_word(text)
    if bad:
        print("ОТКАЗ: в текста се промъкна забранена дума (" + bad + ") — не пращам.")
        return False
    body = clip(text)
    if DRY_RUN:
        print(RULE)
        print(body)
        print(RULE)
        return True
    if not CHAT_ID or not BOT_TOKEN:
        print("Няма BOT_TOKEN/CHAT_ID — пропускам.")
        return False
    return tg_send(body, tid)


# ---------------------------------------------------------------- МАТЕМАТИКА (на ръка)
MAXG = 10               # докъде смятаме матрицата от Поасон


def poisson_pmf(k, lam):
    if k < 0:
        return 0.0
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def logistic(x):
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def logit(p):
    p = min(max(float(p), 1e-6), 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def clampf(x, lo, hi):
    return max(lo, min(hi, x))


def shrink(sample_mean, prior, n, k):
    """Свиване към средното: при малко мачове вярваме повече на нивото."""
    if n <= 0:
        return float(prior)
    return (float(sample_mean) * n + float(prior) * k) / (n + k)


def strength_binary(p):
    """Колко далеч от чиста монета е числото: 50% -> 0, 100% -> 1."""
    return clampf(abs(float(p) - 0.5) * 2.0, 0.0, 1.0)


def strength_1x2(p1, px, p2):
    """1/X/2 има три изхода — базата е 1/3, не 1/2."""
    return clampf((max(p1, px, p2) - 1.0 / 3.0) * 1.5, 0.0, 1.0)


# --- Поасон с корекция Диксън-Коулс -------------------------------------------
# Чистият Поасон систематично подценява равенствата 0:0 и 1:1. Корекцията тежи
# само четирите ниски резултата и е причината картата да не изглежда глупаво,
# когато мачът наистина мирише на 1:1.
FOOT_RHO = -0.13


def dc_tau(i, j, lh, la, rho=FOOT_RHO):
    if i == 0 and j == 0:
        return 1.0 - lh * la * rho
    if i == 0 and j == 1:
        return 1.0 + lh * rho
    if i == 1 and j == 0:
        return 1.0 + la * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(lam_h, lam_a, rho=FOOT_RHO, maxg=MAXG):
    """Съвместното разпределение на резултата, нормирано до сума 1."""
    ph = [poisson_pmf(i, lam_h) for i in range(maxg + 1)]
    pa = [poisson_pmf(j, lam_a) for j in range(maxg + 1)]
    m = []
    total = 0.0
    for i in range(maxg + 1):
        row = []
        for j in range(maxg + 1):
            v = ph[i] * pa[j] * max(0.01, dc_tau(i, j, lam_h, lam_a, rho))
            row.append(v)
            total += v
        m.append(row)
    if total <= 0:
        return [[0.0] * (maxg + 1) for _ in range(maxg + 1)]
    return [[v / total for v in row] for row in m]


def matrix_markets(mx, maxg=MAXG):
    """1 / X / 2, над 2.5, и двата бележат, най-вероятен точен резултат."""
    p_home = p_draw = p_away = p_over = p_btts = 0.0
    best_p, best_i, best_j = 0.0, 0, 0
    for i in range(maxg + 1):
        for j in range(maxg + 1):
            p = mx[i][j]
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p
            if i + j >= 3:
                p_over += p
            if i >= 1 and j >= 1:
                p_btts += p
            if p > best_p:
                best_p, best_i, best_j = p, i, j
    return {"p_home": p_home, "p_draw": p_draw, "p_away": p_away,
            "p_over": p_over, "p_btts": p_btts, "top": (best_i, best_j, best_p)}


# --- Надпревара до N точки с разлика 2 (волейбол, тенис на маса) ---------------
def race_prob(p, n=25):
    """Вероятността да спечелиш гейм/сет до n точки с преднина 2,
    ако всяко разиграване печелиш с вероятност p. Точна сметка, не симулация."""
    p = clampf(float(p), 1e-6, 1.0 - 1e-6)
    q = 1.0 - p
    total = 0.0
    for k in range(0, n - 1):           # съперникът стига до n-2 точки
        total += math.comb(n - 1 + k, k) * (p ** n) * (q ** k)
    deuce = math.comb(2 * n - 2, n - 1) * ((p * q) ** (n - 1))
    total += deuce * (p * p) / (p * p + q * q)
    return clampf(total, 0.0, 1.0)


def bo_distribution(p_set, to_win=3, p_last=None):
    """Разпределение на резултата в сетове при „пръв до to_win".
    Последният решаващ сет може да е с друга вероятност (по-къс, по-нервен)."""
    ps = clampf(float(p_set), 1e-6, 1.0 - 1e-6)
    q = 1.0 - ps
    pl = ps if p_last is None else clampf(float(p_last), 1e-6, 1.0 - 1e-6)
    out = []
    for lost in range(0, to_win):
        games = to_win - 1 + lost
        ways = math.comb(games, lost)
        if lost == to_win - 1:          # решаващият сет
            pr = ways * (ps ** (to_win - 1)) * (q ** lost) * pl
        else:
            pr = ways * (ps ** to_win) * (q ** lost)
        out.append((to_win, lost, pr))
    return out


def bo_match_prob(p_set, to_win=3, p_last=None):
    return sum(x[2] for x in bo_distribution(p_set, to_win, p_last))


def invert_bo(p_match, to_win=3):
    """Обратната сметка: от вероятност за МАЧ намираме вероятността за СЕТ.
    Нужна е, когато моделът дава само кой печели, а искаме и как (3-0 / 3-1)."""
    lo, hi = 1e-4, 1.0 - 1e-4
    target = clampf(float(p_match), 1e-4, 1.0 - 1e-4)
    for _ in range(50):
        mid = (lo + hi) / 2.0
        if bo_match_prob(mid, to_win) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# --- Elo ----------------------------------------------------------------------
def elo_expect(ra, rb):
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))


# --- Брадли-Тери: сила по разигравания, коригирана за съперника ----------------
def fit_bt(rows, iters=14, step=1.1, lo=-1.6, hi=1.6):
    """rows = списък от (отбор, съперник, спечелени, загубени, тегло).
    Връща рейтинг в логит-мащаб, центриран около нулата. Пет реда математика,
    но точно те правят разликата между „силен отбор" и „играл със слаби"."""
    data = {}
    for a, b, wf, wa, w in rows:
        if not a or not b or (wf + wa) <= 0:
            continue
        data.setdefault(a, []).append((b, float(wf), float(wa), float(w)))
        data.setdefault(b, []).append((a, float(wa), float(wf), float(w)))
    r = {t: 0.0 for t in data}
    if not r:
        return r
    for _ in range(iters):
        for t, lst in data.items():
            obs = exp = wsum = 0.0
            for opp, wf, wa, w in lst:
                n = wf + wa
                p = logistic(r[t] - r.get(opp, 0.0))
                obs += w * wf
                exp += w * n * p
                wsum += w * n
            if wsum <= 0:
                continue
            r[t] = clampf(r[t] + step * (obs - exp) / (wsum * 0.25), lo, hi)
        m = mean(r.values())
        for t in r:
            r[t] -= m
    return r


# --- Тегло по свежест ---------------------------------------------------------
def decay_weight(iso_date, now, half_life_days):
    """Мач отпреди две години не тежи колкото мач отпреди месец. Точка."""
    d = days_between(iso_date, now)
    if d is None or d < 0:
        return 1.0
    return 0.5 ** (d / float(max(1.0, half_life_days)))


def wstats(recs, now, half_life):
    """Претеглени средни за/против + ефективна извадка."""
    wsum = gf = ga = 0.0
    hw = hgf = hga = 0.0
    aw = agf = aga = 0.0
    for r in recs:
        w = decay_weight(r.get("date"), now, half_life)
        wsum += w
        gf += w * r["gf"]
        ga += w * r["ga"]
        if r.get("home"):
            hw += w
            hgf += w * r["gf"]
            hga += w * r["ga"]
        else:
            aw += w
            agf += w * r["gf"]
            aga += w * r["ga"]
    if wsum <= 0:
        return None
    out = {"n": len(recs), "w": wsum, "gf": gf / wsum, "ga": ga / wsum,
           "wh": hw, "wa": aw}
    out["gf_h"] = (hgf / hw) if hw > 0 else out["gf"]
    out["ga_h"] = (hga / hw) if hw > 0 else out["ga"]
    out["gf_a"] = (agf / aw) if aw > 0 else out["gf"]
    out["ga_a"] = (aga / aw) if aw > 0 else out["ga"]
    return out


def sane_record(bucket, gf, ga):
    """Пази срещу боклук в източника (точки, записани като сетове, и подобни)."""
    if gf is None or ga is None or gf < 0 or ga < 0:
        return False
    if bucket in ("football", "hockey"):
        return gf <= 15 and ga <= 15
    if bucket == "basketball":
        return 30 <= gf <= 200 and 30 <= ga <= 200
    if bucket == "baseball":
        return gf <= 40 and ga <= 40
    if bucket == "volleyball":
        return max(gf, ga) <= 3 and (gf + ga) <= 5 and max(gf, ga) >= 2
    if bucket == "tabletennis":
        return max(gf, ga) <= 4 and (gf + ga) <= 7 and max(gf, ga) >= 2
    return True


# ---------------------------------------------------------------- УВЕРЕНОСТ
def grade(bucket, n_eff, strength):
    """Звездите идват от РЕАЛНАТА извадка и от категоричността. Нищо друго."""
    score = 0.55 * min(1.0, float(n_eff) / 30.0) + 0.45 * min(1.0, float(strength) / 0.40)
    stars = 3 if score >= 0.72 else (2 if score >= 0.45 else 1)
    if n_eff < 10:
        stars = 1
    elif n_eff < 20:
        stars = min(stars, 2)
    return max(1, min(stars, STAR_CAP.get(bucket, 3)))


# ================================================================= ИЗТОЧНИЦИ
ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports"

_hist_cache = {}


def espn_num(s):
    """КАПАН №1 в целия файл. В scoreboard резултатът е низ „2", а в
    teams/{id}/schedule е речник {value: 2}. Един помощник за двете места."""
    if isinstance(s, dict):
        v = s.get("value")
        if v is None:
            v = s.get("displayValue")
        return to_num(v)
    return to_num(s)


def espn_sides(comp):
    """Домакин и гост от competitors[].homeAway — никога от реда в списъка."""
    h = a = None
    for c in (comp.get("competitors") or []):
        if c.get("homeAway") == "home":
            h = c
        elif c.get("homeAway") == "away":
            a = c
    return h, a


def espn_fixtures(sport, slug, ymd, bucket, weight, league_bg, now, extra=None):
    """Днешните срещи на една лига. Взимаме само още неиграните („pre")."""
    j = http_json(ESPN_SITE + "/" + sport + "/" + slug + "/scoreboard?dates=" + ymd)
    if not isinstance(j, dict):
        return []
    lg = (j.get("leagues") or [{}])
    lname = league_bg or ((lg[0] or {}).get("name") if lg else "") or slug
    out = []
    for ev in (j.get("events") or []):
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0] or {}
        st = ((comp.get("status") or {}).get("type") or {})
        if str(st.get("state") or "").lower() != "pre":
            continue
        if "Preseason" in str((ev.get("seasonType") or {}).get("name") or ""):
            continue
        h, a = espn_sides(comp)
        if not h or not a:
            continue
        ht, at = (h.get("team") or {}), (a.get("team") or {})
        ex = dict(extra or {})
        ex["slug"] = slug
        ex["neutral"] = bool(comp.get("neutralSite"))
        ex["form_h"] = h.get("form") or ""
        ex["form_a"] = a.get("form") or ""
        out.append({
            "bucket": bucket, "emoji": SPORTS[bucket]["emoji"], "src": "espn",
            "home": bg_name(ht.get("displayName") or ""), "away": bg_name(at.get("displayName") or ""),
            "home_id": ht.get("id"), "away_id": at.get("id"),
            "league": lname, "weight": weight, "when": parse_iso(ev.get("date")),
            "extra": ex,
        })
    return out


def espn_history(sport, slug, team_id, seasons, bucket):
    """Изиграните мачове на отбор за дадени сезони. ТУК резултатът е речник."""
    ck = ("h", sport, slug, str(team_id), tuple(seasons))
    if ck in _hist_cache:
        return _hist_cache[ck]
    recs = []
    for s in seasons:
        j = http_json(ESPN_SITE + "/" + sport + "/" + slug + "/teams/"
                      + str(team_id) + "/schedule?season=" + str(s), quiet=True)
        if not isinstance(j, dict):
            continue
        for ev in (j.get("events") or []):
            if "Preseason" in str((ev.get("seasonType") or {}).get("name") or ""):
                continue
            comps = ev.get("competitions") or []
            if not comps:
                continue
            me = opp = None
            for c in (comps[0].get("competitors") or []):
                if str((c.get("team") or {}).get("id") or "") == str(team_id):
                    me = c
                else:
                    opp = c
            if not me or not opp:
                continue
            gf, ga = espn_num(me.get("score")), espn_num(opp.get("score"))
            if gf is None or ga is None:
                continue
            if not sane_record(bucket, gf, ga):
                continue
            recs.append({"gf": gf, "ga": ga,
                         "home": me.get("homeAway") == "home",
                         "date": str(ev.get("date") or "")[:10],
                         "opp": str((opp.get("team") or {}).get("id") or "")})
    _hist_cache[ck] = recs
    return recs


# ----------------------------------------------------------------- ⚽ ФУТБОЛ
# ESPN няма българска лига (bul.1 -> 400, в справочника от 220 адреса няма BUL).
# Затова тук няма български клубове. Това е ограничение на данните, не мързел.
FOOT_SLUGS = [
    ("uefa.champions", 12, "Шампионска лига"), ("uefa.europa", 9, "Лига Европа"),
    ("eng.1", 10, "Висша лига"), ("esp.1", 10, "Ла Лига"),
    ("ita.1", 9, "Серия А"), ("ger.1", 9, "Бундеслига"),
    ("fra.1", 8, "Лига 1"), ("uefa.europa.conf", 6, "Лига на конференциите"),
    ("ned.1", 6, "Ередивизи"), ("por.1", 6, "Примейра лига"),
    ("tur.1", 6, "Супер лига, Турция"), ("gre.1", 5, "Супер лига, Гърция"),
    ("bel.1", 5, "Про лига, Белгия"), ("eng.2", 5, "Чемпиъншип"),
    ("sco.1", 5, "Премиършип, Шотландия"), ("bra.1", 5, "Серия А, Бразилия"),
    ("arg.1", 5, "Примера, Аржентина"), ("usa.1", 4, "MLS"),
]
FOOT_SLUG_MAX = env_int("PREDICT_FOOT_SLUGS", 14, 1, 18)
FOOT_PRIOR = 1.38       # голове на отбор на мач — типично за силна лига
FOOT_SHRINK = 6.0
FOOT_HOME = 1.12
FOOT_AWAY = 0.89
FOOT_LAM_MIN, FOOT_LAM_MAX = 0.25, 4.5
FOOT_HALFLIFE = 400.0   # дни; мач отпреди година тежи ~54%


def soccer_seasons(now):
    """ESPN брои футболния сезон по НАЧАЛНАТА година: 2025 = сезон 2025-26."""
    s = now.year if now.month >= 7 else now.year - 1
    return [s, s - 1]


def football_fixtures(now, ymd):
    out = []
    for slug, w, name in FOOT_SLUGS[:FOOT_SLUG_MAX]:
        try:
            out += espn_fixtures("soccer", slug, ymd, "football", w, name, now,
                                 {"seasons": soccer_seasons(now)})
        except Exception as e:      # noqa: BLE001
            print("   ⚠ футбол " + slug + ": " + str(e)[:60])
            break                   # изчерпан лимит или мрежа долу — спираме спорта
    return out


def football_history(fx, side):
    tid = fx.get("home_id") if side == "home" else fx.get("away_id")
    if not tid:
        return []
    slug = (fx.get("extra") or {}).get("slug") or "eng.1"
    seasons = list((fx.get("extra") or {}).get("seasons") or [])
    recs = espn_history("soccer", slug, tid, seasons, "football")
    if len(recs) < 12 and seasons:
        recs = espn_history("soccer", slug, tid, seasons + [seasons[-1] - 1], "football")
    return recs


def model_football(hr, ar, lvl, now):
    sh, sa = wstats(hr, now, FOOT_HALFLIFE), wstats(ar, now, FOOT_HALFLIFE)
    if not sh or not sa:
        return None
    # Домакинската и гостуващата форма поотделно, свити към общата на отбора —
    # при 3 мача у дома не вярваме на 3 мача у дома.
    gf_h = shrink(sh["gf_h"], sh["gf"], sh["wh"], 5.0)
    ga_h = shrink(sh["ga_h"], sh["ga"], sh["wh"], 5.0)
    gf_a = shrink(sa["gf_a"], sa["gf"], sa["wa"], 5.0)
    ga_a = shrink(sa["ga_a"], sa["ga"], sa["wa"], 5.0)

    att_h = shrink(gf_h, lvl, sh["w"], FOOT_SHRINK) / lvl
    def_h = shrink(ga_h, lvl, sh["w"], FOOT_SHRINK) / lvl
    att_a = shrink(gf_a, lvl, sa["w"], FOOT_SHRINK) / lvl
    def_a = shrink(ga_a, lvl, sa["w"], FOOT_SHRINK) / lvl

    lam_h = clampf(lvl * att_h * def_a * FOOT_HOME, FOOT_LAM_MIN, FOOT_LAM_MAX)
    lam_a = clampf(lvl * att_a * def_h * FOOT_AWAY, FOOT_LAM_MIN, FOOT_LAM_MAX)
    mk = matrix_markets(score_matrix(lam_h, lam_a))
    mk.update({"lam_h": lam_h, "lam_a": lam_a, "sh": sh, "sa": sa, "lvl": lvl})
    return mk


def league_level(all_recs, now):
    if not all_recs:
        return FOOT_PRIOR
    m = mean(r["gf"] for r in all_recs)
    return clampf(shrink(m, FOOT_PRIOR, len(all_recs), 40.0), 0.8, 2.2)


# ----------------------------------------------------------------- 🏀 БАСКЕТБОЛ
# NBA спи от средата на април до края на септември. WNBA носи лятото,
# NCAA носи ноември-март. Затова са изброени и четирите.
BASK_LEAGUES = [
    ("nba", 10, "НБА", 11.5), ("wnba", 7, "WNBA", 10.5),
    ("mens-college-basketball", 4, "NCAA, мъже", 11.5),
    ("womens-college-basketball", 3, "NCAA, жени", 12.5),
]
BASK_HCA = {"nba": 2.4, "wnba": 2.2, "mens-college-basketball": 3.2,
            "womens-college-basketball": 3.2}
BASK_SHRINK = 6.0
BASK_MARGIN_MAX = 26.0
BASK_HALFLIFE = 220.0


def bask_seasons(now, league):
    """ESPN брои баскетболния сезон по КРАЙНАТА година: 2026 = сезон 2025-26."""
    if league == "wnba":
        s = now.year
    else:
        s = now.year + 1 if now.month >= 10 else now.year
    return [s, s - 1]


def basketball_fixtures(now, ymd):
    out = []
    for slug, w, name, sigma in BASK_LEAGUES:
        try:
            out += espn_fixtures("basketball", slug, ymd, "basketball", w, name, now,
                                 {"seasons": bask_seasons(now, slug), "sigma": sigma,
                                  "hca": BASK_HCA.get(slug, 2.5)})
        except Exception as e:      # noqa: BLE001
            print("   ⚠ баскетбол " + slug + ": " + str(e)[:60])
            break
    return out


def basketball_history(fx, side):
    tid = fx.get("home_id") if side == "home" else fx.get("away_id")
    if not tid:
        return []
    ex = fx.get("extra") or {}
    return espn_history("basketball", ex.get("slug") or "nba", tid,
                        list(ex.get("seasons") or []), "basketball")


def model_basketball(hr, ar, fx, now):
    sh, sa = wstats(hr, now, BASK_HALFLIFE), wstats(ar, now, BASK_HALFLIFE)
    if not sh or not sa:
        return None
    ex = fx.get("extra") or {}
    sigma = float(ex.get("sigma") or 11.5)
    hca = 0.0 if ex.get("neutral") else float(ex.get("hca") or 2.5)
    lvl = (sh["gf"] + sh["ga"] + sa["gf"] + sa["ga"]) / 4.0
    sf_h = shrink(sh["gf"], lvl, sh["w"], BASK_SHRINK)
    sa_h = shrink(sh["ga"], lvl, sh["w"], BASK_SHRINK)
    sf_a = shrink(sa["gf"], lvl, sa["w"], BASK_SHRINK)
    sa_a = shrink(sa["ga"], lvl, sa["w"], BASK_SHRINK)
    exp_h = (sf_h + sa_a) / 2.0 + hca / 2.0
    exp_a = (sf_a + sa_h) / 2.0 - hca / 2.0
    margin = clampf(exp_h - exp_a, -BASK_MARGIN_MAX, BASK_MARGIN_MAX)
    # Логистична крива със същото стандартно отклонение като маржа:
    # scale = sigma*sqrt(3)/pi. При 11.5 точки: 6 т. преднина -> ~71%.
    scale = sigma * math.sqrt(3.0) / math.pi
    p_home = logistic(margin / scale)
    return {"exp_h": exp_h, "exp_a": exp_a, "total": exp_h + exp_a, "margin": margin,
            "p_home": p_home, "p_away": 1.0 - p_home, "sh": sh, "sa": sa, "hca": hca}


# ----------------------------------------------------------------- 🎾 ТЕНИС
TENNIS_TOURS = [("atp", "ATP"), ("wta", "WTA")]
TEN_K = 0.80            # тежест на разликата в точки от ранглистата
TEN_FLOOR = 120.0       # база за некласиран играч
TEN_FORM_K = 0.30
TEN_P_MIN, TEN_P_MAX = 0.12, 0.88
_ten_rank = {}
_ten_form = {}


def tennis_rankings(tour):
    if tour in _ten_rank:
        return _ten_rank[tour]
    out = {}
    j = http_json(ESPN_SITE + "/tennis/" + tour + "/rankings")
    for grp in ((j or {}).get("rankings") or []):
        for row in (grp.get("ranks") or []):
            ath = row.get("athlete") or {}
            aid = str(ath.get("id") or "")
            if aid:
                out[aid] = {"rank": to_num(row.get("current")),
                            "pts": to_f(row.get("points"), 0.0) or 0.0,
                            "name": ath.get("displayName") or ""}
    _ten_rank[tour] = out
    return out


def _tennis_singles(j, want_pre):
    """Общ разбор: events[] са ТУРНИРИ, competitions[] са мачовете."""
    rows = []
    for ev in ((j or {}).get("events") or []):
        tname = ev.get("name") or ""
        for grp in (ev.get("groupings") or []):
            disc = str((grp.get("grouping") or {}).get("displayName") or "")
            if "Doubles" in disc or "Singles" not in disc:
                continue
            for comp in (grp.get("competitions") or []):
                st = ((comp.get("status") or {}).get("type") or {})
                state = str(st.get("state") or "").lower()
                if want_pre and state != "pre":
                    continue
                if (not want_pre) and not st.get("completed"):
                    continue
                cs = comp.get("competitors") or []
                if len(cs) != 2:
                    continue
                rows.append((tname, disc, comp, cs))
    return rows


def tennis_fixtures(now, ymd):
    out = []
    seen = set()
    for tour, label in TENNIS_TOURS:
        try:
            ranks = tennis_rankings(tour)
            j = http_json(ESPN_SITE + "/tennis/" + tour + "/scoreboard?dates=" + ymd)
        except Exception as e:      # noqa: BLE001
            print("   ⚠ тенис " + tour + ": " + str(e)[:60])
            break
        for tname, disc, comp, cs in _tennis_singles(j, True):
            cid = str(comp.get("id") or "")
            if not cid or cid in seen:
                continue          # ЕДИН мач = ЕДИН запис; таблото дава цялата схема
            seen.add(cid)
            a, b = cs[0], cs[1]
            ida, idb = str(a.get("id") or ""), str(b.get("id") or "")
            na = ((a.get("athlete") or {}).get("displayName") or "").strip()
            nb = ((b.get("athlete") or {}).get("displayName") or "").strip()
            if not na or not nb:
                continue
            best = to_num(((comp.get("format") or {}).get("regulation") or {}).get("periods")) or 3
            ra, rb = ranks.get(ida) or {}, ranks.get(idb) or {}
            top = min(ra.get("rank") or 999, rb.get("rank") or 999)
            out.append({
                "bucket": "tennis", "emoji": "🎾", "src": "espn_tennis",
                "home": na, "away": nb, "home_id": ida, "away_id": idb,
                "league": tname + " · " + label,
                "weight": 9 if top <= 10 else (7 if top <= 30 else (6 if top <= 100 else 4)),
                "when": parse_iso(comp.get("date") or comp.get("startDate")),
                "extra": {"tour": tour, "best_of": 5 if best == 5 else 3,
                          "ra": ra, "rb": rb},
            })
    return out


def tennis_form(tour, now):
    """Форма от миналите табла: няколко дни назад, с махане на дубликатите.
    Не е Elo — Elo иска цялата мрежа мачове и не се събира в един рън."""
    if tour in _ten_form:
        return _ten_form[tour]
    wl, seen = {}, set()
    for i in range(1, TENNIS_SWEEP + 1):
        d = (now - timedelta(days=i * 4)).strftime("%Y%m%d")
        try:
            j = http_json(ESPN_SITE + "/tennis/" + tour + "/scoreboard?dates=" + d, quiet=True)
        except Exception:           # noqa: BLE001
            break
        for _t, _d, comp, cs in _tennis_singles(j, False):
            cid = str(comp.get("id") or "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            for c in cs:
                pid = str(c.get("id") or "")
                if not pid:
                    continue
                rec = wl.setdefault(pid, [0, 0])
                if c.get("winner"):
                    rec[0] += 1
                else:
                    rec[1] += 1
    _ten_form[tour] = wl
    return wl


def model_tennis(fx, now):
    ex = fx.get("extra") or {}
    ra, rb = ex.get("ra") or {}, ex.get("rb") or {}
    form = tennis_form(ex.get("tour") or "atp", now) if TENNIS_SWEEP else {}
    fa = form.get(str(fx.get("home_id"))) or [0, 0]
    fb = form.get(str(fx.get("away_id"))) or [0, 0]
    pa, pb = float(ra.get("pts") or 0.0), float(rb.get("pts") or 0.0)
    rank_term = TEN_K * (math.log(pa + TEN_FLOOR) - math.log(pb + TEN_FLOOR))
    wa = (fa[0] + 2.0) / (fa[0] + fa[1] + 4.0)
    wb = (fb[0] + 2.0) / (fb[0] + fb[1] + 4.0)
    form_term = TEN_FORM_K * (logit(wa) - logit(wb))
    p = logistic(rank_term + form_term)
    if int(ex.get("best_of") or 3) == 5:
        # Пет сета = по-малко шум, фаворитът печели по-често. Монотонно разтягане.
        p = logistic(logit(p) * 1.25)
    p = clampf(p, TEN_P_MIN, TEN_P_MAX)
    n_a, n_b = fa[0] + fa[1], fb[0] + fb[1]
    ok_a = bool(ra.get("rank")) or n_a >= 3
    ok_b = bool(rb.get("rank")) or n_b >= 3
    return {"p_home": p, "p_away": 1.0 - p, "ra": ra, "rb": rb,
            "fa": fa, "fb": fb, "n_a": n_a, "n_b": n_b, "ok": ok_a and ok_b}


# ----------------------------------------------------------------- 🏒 ХОКЕЙ (NHL)
NHL_WEB = "https://api-web.nhle.com/v1"
_nhl_tab = {}


def hockey_fixtures(now, ymd_dash):
    j = http_json(NHL_WEB + "/score/" + ymd_dash)
    if not isinstance(j, dict):
        return []
    out = []
    for g in (j.get("games") or []):
        if str(g.get("gameState") or "").upper() not in ("FUT", "PRE"):
            continue
        if to_num(g.get("gameType")) == 1:      # предсезонните не носят информация
            continue
        h, a = g.get("homeTeam") or {}, g.get("awayTeam") or {}
        hn = (h.get("name") or {}).get("default") or h.get("abbrev") or ""
        an = (a.get("name") or {}).get("default") or a.get("abbrev") or ""
        if not hn or not an:
            continue
        out.append({
            "bucket": "hockey", "emoji": "🏒", "src": "nhl",
            "home": bg_name(hn), "away": bg_name(an),
            "home_id": h.get("abbrev"), "away_id": a.get("abbrev"),
            "league": "НХЛ", "weight": 7, "when": parse_iso(g.get("startTimeUTC")),
            "extra": {},
        })
    if not out:
        sch = http_json(NHL_WEB + "/schedule/" + ymd_dash, quiet=True)
        nxt = (sch or {}).get("nextStartDate")
        if nxt:
            print("   хокей: извън сезон, следващи мачове от " + str(nxt) + ".")
    return out


def nhl_table():
    """Едно повикване = всичко, което Поасон иска за 32 отбора."""
    if _nhl_tab:
        return _nhl_tab
    j = http_json(NHL_WEB + "/standings/now")
    for row in ((j or {}).get("standings") or []):
        ab = ((row.get("teamAbbrev") or {}).get("default") or "").strip()
        gp = to_f(row.get("gamesPlayed"), 0.0) or 0.0
        if not ab or gp < 5:
            continue
        _nhl_tab[ab] = {
            "gp": gp, "gf": to_f(row.get("goalFor"), 0.0) or 0.0,
            "ga": to_f(row.get("goalAgainst"), 0.0) or 0.0,
            "hgp": to_f(row.get("homeGamesPlayed"), 0.0) or 0.0,
            "hgf": to_f(row.get("homeGoalsFor"), 0.0) or 0.0,
            "hga": to_f(row.get("homeGoalsAgainst"), 0.0) or 0.0,
            "rgp": to_f(row.get("roadGamesPlayed"), 0.0) or 0.0,
            "rgf": to_f(row.get("roadGoalsFor"), 0.0) or 0.0,
            "rga": to_f(row.get("roadGoalsAgainst"), 0.0) or 0.0,
        }
    return _nhl_tab


def _rate(num, den, fallback):
    return (num / den) if den and den > 0 else fallback


def model_hockey(fx):
    tab = nhl_table()
    h = tab.get(str(fx.get("home_id") or ""))
    a = tab.get(str(fx.get("away_id") or ""))
    if not h or not a:
        return None
    lvl = mean([_rate(t["gf"], t["gp"], 3.0) for t in tab.values()]) or 3.05
    att_h = _rate(h["hgf"], h["hgp"], _rate(h["gf"], h["gp"], lvl)) / lvl
    def_a = _rate(a["rga"], a["rgp"], _rate(a["ga"], a["gp"], lvl)) / lvl
    att_a = _rate(a["rgf"], a["rgp"], _rate(a["gf"], a["gp"], lvl)) / lvl
    def_h = _rate(h["hga"], h["hgp"], _rate(h["ga"], h["gp"], lvl)) / lvl
    lam_h = clampf(lvl * att_h * def_a, 1.4, 5.5)
    lam_a = clampf(lvl * att_a * def_h, 1.4, 5.5)
    mk = matrix_markets(score_matrix(lam_h, lam_a, rho=0.0))
    # В хокея НЯМА равен. Продълженията и наказателните удари са близо до монета,
    # затова делим масата на равенството наполовина и го казваме на глас.
    ph = mk["p_home"] + mk["p_draw"] / 2.0
    tot = lam_h + lam_a
    p_over = 0.0
    mx = score_matrix(lam_h, lam_a, rho=0.0)
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            if i + j >= 6:
                p_over += mx[i][j]
    return {"p_home": ph, "p_away": 1.0 - ph, "lam_h": lam_h, "lam_a": lam_a,
            "total": tot, "p_over55": p_over, "gp_h": h["gp"], "gp_a": a["gp"],
            "p_draw_reg": mk["p_draw"],
            "hgf": _rate(h["hgf"], h["hgp"], lvl), "hga": _rate(h["hga"], h["hgp"], lvl),
            "agf": _rate(a["rgf"], a["rgp"], lvl), "aga": _rate(a["rga"], a["rgp"], lvl)}


# ----------------------------------------------------------------- ⚾ БЕЙЗБОЛ (MLB)
MLB_API = "https://statsapi.mlb.com/api/v1"
MLB_HOME = 0.25         # рънове предимство за домакина (~53% базова победа)
MLB_SCALE = 2.43        # 4.4 рънa стандартно отклонение -> sigma*sqrt(3)/pi
_mlb_hist = {}


def baseball_fixtures(now, ymd_dash):
    j = http_json(MLB_API + "/schedule?sportId=1&date=" + ymd_dash)
    out = []
    for day in ((j or {}).get("dates") or []):
        for g in (day.get("games") or []):
            if str((g.get("status") or {}).get("detailedState") or "") not in (
                    "Scheduled", "Pre-Game", "Warmup"):
                continue
            t = g.get("teams") or {}
            h, a = (t.get("home") or {}).get("team") or {}, (t.get("away") or {}).get("team") or {}
            if not h.get("name") or not a.get("name"):
                continue
            out.append({
                "bucket": "baseball", "emoji": "⚾", "src": "mlb",
                "home": bg_name(h.get("name")), "away": bg_name(a.get("name")),
                "home_id": h.get("id"), "away_id": a.get("id"),
                "league": "МЛБ", "weight": 5, "when": parse_iso(g.get("gameDate")),
                "extra": {},
            })
    return out


def baseball_history(fx, side):
    tid = fx.get("home_id") if side == "home" else fx.get("away_id")
    if not tid:
        return []
    if tid in _mlb_hist:
        return _mlb_hist[tid]
    now = datetime.now(SOFIA)
    start = str(now.year) + "-03-01"
    j = http_json(MLB_API + "/schedule?sportId=1&teamId=" + str(tid)
                  + "&startDate=" + start + "&endDate=" + now.strftime("%Y-%m-%d"), quiet=True)
    recs = []
    for day in ((j or {}).get("dates") or []):
        for g in (day.get("games") or []):
            if str((g.get("status") or {}).get("detailedState") or "") != "Final":
                continue
            t = g.get("teams") or {}
            hh, aa = t.get("home") or {}, t.get("away") or {}
            hs, as_ = to_num(hh.get("score")), to_num(aa.get("score"))
            if hs is None or as_ is None:
                continue
            is_home = str(((hh.get("team") or {}).get("id"))) == str(tid)
            gf, ga = (hs, as_) if is_home else (as_, hs)
            if not sane_record("baseball", gf, ga):
                continue
            recs.append({"gf": gf, "ga": ga, "home": is_home,
                         "date": str(g.get("gameDate") or "")[:10], "opp": ""})
    _mlb_hist[tid] = recs
    return recs


def model_baseball(hr, ar, now):
    sh, sa = wstats(hr, now, 200.0), wstats(ar, now, 200.0)
    if not sh or not sa:
        return None
    exp_h = (sh["gf"] + sa["ga"]) / 2.0 + MLB_HOME / 2.0
    exp_a = (sa["gf"] + sh["ga"]) / 2.0 - MLB_HOME / 2.0
    margin = clampf(exp_h - exp_a, -3.5, 3.5)
    p = logistic(margin / MLB_SCALE)
    return {"p_home": p, "p_away": 1.0 - p, "exp_h": exp_h, "exp_a": exp_a,
            "margin": margin, "sh": sh, "sa": sa}


# ----------------------------------------------------------------- 🥊 ММА / UFC
# ESPN НЯМА бокс (проверени четири адреса, всички 400). Тук има само ММА.
MMA_LEAGUES = [("ufc", 10, "UFC"), ("pfl", 6, "PFL")]
MMA_YEARS = 3
MMA_ELO_K = 24.0
MMA_P_MAX = 0.78        # мачмейкърите правят равностойни двойки; 90% = счупен модел
_mma_idx = {}


def parse_record(s):
    """„13-2-0" -> (13, 2, 0). Носи ЦЯЛАТА кариера, включително извън UFC."""
    parts = [to_num(x) for x in str(s or "").split("-")]
    parts = [p for p in parts if p is not None]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def mma_prior(w, l):
    """Рейтинг само от рекорда — за дебютантите, които ги няма в индекса."""
    n = w + l
    if n <= 0:
        return 1500.0
    rate = clampf(w / float(n), 0.05, 0.95)
    return 1500.0 + 200.0 * (rate - 0.5) * 2.0 * min(1.0, n / 12.0)


def mma_index(league, now):
    """Elo върху всички битки от последните години. Едно повикване на година."""
    if league in _mma_idx:
        return _mma_idx[league]
    fights, rec = [], {}
    for y in range(now.year, now.year - MMA_YEARS, -1):
        j = http_json(ESPN_SITE + "/mma/" + league + "/scoreboard?dates=" + str(y), quiet=True)
        for ev in ((j or {}).get("events") or []):
            for comp in (ev.get("competitions") or []):
                st = ((comp.get("status") or {}).get("type") or {})
                if not st.get("completed"):
                    continue
                cs = comp.get("competitors") or []
                if len(cs) != 2:
                    continue
                ids, win = [], None
                for c in cs:
                    cid = str(c.get("id") or "")
                    ids.append(cid)
                    r = (c.get("records") or [{}])
                    rec[cid] = (r[0] or {}).get("summary") or rec.get(cid) or ""
                    if c.get("winner"):
                        win = cid
                if not all(ids) or win is None:
                    continue
                periods = to_num(((comp.get("format") or {}).get("regulation") or {}).get("periods")) or 3
                per = to_num(st.get("period")) or periods
                clock = str(st.get("displayClock") or "")
                # Няма поле „начин на победа". Изведено правило: пълни рундове с
                # часовник 5:00 = съдийско решение, всичко друго = предсрочен край.
                finish = not (per >= periods and clock.startswith("5:0"))
                fights.append({"date": str(ev.get("date") or "")[:10],
                               "a": ids[0], "b": ids[1], "w": win, "fin": finish})
    fights.sort(key=lambda f: f["date"])
    elo, seen = {}, {}
    for f in fights:
        for cid in (f["a"], f["b"]):
            if cid not in elo:
                w, l, _d = parse_record(rec.get(cid) or "")
                elo[cid] = mma_prior(w, l)
                seen[cid] = {"n": 0, "w": 0, "fin": 0}
        ra, rb = elo[f["a"]], elo[f["b"]]
        sa = 1.0 if f["w"] == f["a"] else 0.0
        k = MMA_ELO_K * (1.25 if f["fin"] else 0.9)
        ea = elo_expect(ra, rb)
        elo[f["a"]] = ra + k * (sa - ea)
        elo[f["b"]] = rb + k * ((1.0 - sa) - (1.0 - ea))
        for cid in (f["a"], f["b"]):
            seen[cid]["n"] += 1
        seen[f["w"]]["w"] += 1
        if f["fin"]:
            seen[f["w"]]["fin"] += 1
    _mma_idx[league] = {"elo": elo, "stat": seen, "rec": rec, "fights": len(fights)}
    return _mma_idx[league]


def mma_fixtures(now):
    out = []
    for league, w, label in MMA_LEAGUES:
        # БЕЗ ?dates= — голият адрес връща СЛЕДВАЩАТА гала и никога не е празен.
        j = http_json(ESPN_SITE + "/mma/" + league + "/scoreboard")
        if not isinstance(j, dict):
            continue
        for ev in (j.get("events") or []):
            when = parse_iso(ev.get("date"))
            if when is None:
                continue
            ahead = (when - now).total_seconds() / 86400.0
            if ahead < -0.5 or ahead > MMA_DAYS_AHEAD:
                continue
            card = ev.get("name") or label
            for n, comp in enumerate(ev.get("competitions") or []):
                st = ((comp.get("status") or {}).get("type") or {})
                if st.get("completed"):
                    continue
                cs = comp.get("competitors") or []
                if len(cs) != 2:
                    continue
                names, ids, recs = [], [], []
                for c in cs:
                    ath = c.get("athlete") or {}
                    names.append((ath.get("displayName") or "").strip())
                    ids.append(str(c.get("id") or ""))
                    recs.append(((c.get("records") or [{}])[0] or {}).get("summary") or "")
                if not all(names) or not all(ids):
                    continue
                div = str((comp.get("type") or {}).get("abbreviation") or "")
                # Режем ИМЕТО на галата, не категорията — иначе картата свършва
                # с „Heavyw…" и зрителят не научава в коя категория е боят.
                short = card if len(card) <= 30 else (card[:29] + chr(8230))
                out.append({
                    "bucket": "mma", "emoji": "🥊", "src": "mma",
                    "home": names[0], "away": names[1],
                    "home_id": ids[0], "away_id": ids[1],
                    "league": short + ((" · " + div) if div else ""),
                    "weight": w + (3 if n == 0 else (1 if n == 1 else 0)),
                    "when": when,
                    "extra": {"league": league, "rec_h": recs[0], "rec_a": recs[1],
                              "rounds": to_num(((comp.get("format") or {}).get("regulation") or {}).get("periods")) or 3},
                })
    return out


def model_mma(fx, now):
    ex = fx.get("extra") or {}
    idx = mma_index(ex.get("league") or "ufc", now)
    elo, stat = idx["elo"], idx["stat"]
    ida, idb = str(fx.get("home_id")), str(fx.get("away_id"))
    wa, la, _ = parse_record(ex.get("rec_h"))
    wb, lb, _ = parse_record(ex.get("rec_a"))
    ra = elo.get(ida, mma_prior(wa, la))
    rb = elo.get(idb, mma_prior(wb, lb))
    na = (stat.get(ida) or {}).get("n", 0)
    nb = (stat.get(idb) or {}).get("n", 0)
    p = elo_expect(ra, rb)
    # Клетката е малка, вариациите огромни. Свиваме към монетата и слагаме таван.
    p = 0.5 + (p - 0.5) * clampf((min(na, nb) + 2.0) / 8.0, 0.35, 1.0)
    p = clampf(p, 1.0 - MMA_P_MAX, MMA_P_MAX)
    sa_, sb_ = stat.get(ida) or {}, stat.get(idb) or {}
    # Дялът предсрочни победи се показва само при поне 4 победи в индекса.
    # „100% предсрочно" от една победа е число без съдържание.
    fin_a = (sa_.get("fin", 0) / float(sa_["w"])) if sa_.get("w", 0) >= 4 else None
    fin_b = (sb_.get("fin", 0) / float(sb_["w"])) if sb_.get("w", 0) >= 4 else None
    return {"p_home": p, "p_away": 1.0 - p, "ra": ra, "rb": rb, "na": na, "nb": nb,
            "rec_h": (wa, la), "rec_a": (wb, lb), "fin_h": fin_a, "fin_a": fin_b,
            "win_h": sa_.get("w", 0), "win_a": sb_.get("w", 0),
            "ok": (wa + la) >= 3 and (wb + lb) >= 3}


# ----------------------------------------------------------------- 🏐 ВОЛЕЙБОЛ (FIVB)
# 🚨 НАЙ-ВАЖНОТО ТУК: TeamACode/TeamBCode е кодът на ДЪРЖАВАТА, нищо повече.
# Проверено на живо: същият код ALG стои този сезон и в „CAVB Boys' U18
# Championship", и в „CAVB Girls' U18 Championship", и в „CAVB Zone I Men
# National". Ако рейтингът се води само по кода, мъжете, жените и юношите
# влизат в ЕДНА сила за държавата и публикуваният процент е боклук.
# Затова ключът е (КОШНИЦА, КОД), а кошницата идва от турнира.
VIS = "https://www.fivb.org/Vis2009/XmlRequest.asmx?Request="
VOL_DECOYS = {"1170", "1482", "1586", "1592", "1735", "1736"}
VOL_HALFLIFE = 500.0
VOL_P_MIN, VOL_P_MAX = 0.40, 0.60
VOL_MIN_ROWS = 60           # под толкова мача в кошницата не смятаме нищо
VOL_THIN_ROWS = 250         # под толкова — най-много една звезда

# Думи, които правят турнира ЮНОШЕСКИ. Липсата им НЕ е доказателство за мъже —
# затова има и втора проверка по Type и по „U19"/„Under 19".
VOL_YOUTH = {"youth", "junior", "juniors", "juniores", "cadet", "cadets", "boys", "boy",
             "girls", "girl", "school", "schools", "juvenil", "juveniles", "infantil",
             "menores", "jeunes", "giovanili", "sub", "kids", "minime", "minimes"}
# Турнири, при които възрастта или полът НЕ се разчитат уверено -> изхвърляме ги.
VOL_AMBIG = {"universiade", "university", "student", "students", "mixed", "test", "sim",
             "demo", "snow"}
VOL_MEN = {"men", "mens", "man", "male", "masculin", "masculino", "masculine", "maschile",
           "hommes", "messieurs", "boys", "boy"}
VOL_WOMEN = {"women", "womens", "woman", "female", "femenino", "feminino", "feminine",
             "feminin", "femminile", "femmes", "dames", "ladies", "girls", "girl"}
# Общи думи в имената на клубовете. Махат се, за да остане само същината.
VOL_GENERIC = {"volleyball", "volley", "voleibol", "voley", "volei", "vb", "vc", "club",
               "clube", "cs", "sc", "sport", "sports", "sporting", "team", "de", "du",
               "des", "la", "le", "les", "el", "los", "the", "of", "and", "d", "di", "da",
               "del", "der", "und", "e", "national", "nationale"}
VOL_BUCKET_BG = {"m-sen": "мъже", "w-sen": "жени", "m-you": "юноши", "w-you": "девойки"}

_vol_rating = {}    # (кошница, код) -> сила по Брадли-Тери
_vol_count = {}     # (кошница, код) -> изиграни мачове В ТАЗИ кошница
_vol_ident = {}     # (кошница, код) -> отпечатък на отбора (име, държава)
_vol_comp = {}      # (кошница, код) -> коя свързана група
_vol_rows = {}      # кошница -> брой мачове, влезли в напасването
_vol_meta = {}      # номер на турнир -> {"name":..., "bucket":...}
_vol_meta_done = [False]
_vol_fit_done = [False]


def vis_xml(req):
    url = VIS + urllib.parse.quote(req, safe="")
    txt = http_text(url, timeout=180)
    return ET.fromstring(txt)


def vol_fold(s):
    """„Espérance" -> „Esperance". Иначе едно и също име се брои за две."""
    d = unicodedata.normalize("NFKD", str(s if s is not None else ""))
    return "".join(c for c in d if not unicodedata.combining(c))


def vol_tokens(s):
    out, cur = [], []
    for ch in vol_fold(s).lower():
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


def vol_bucket(name, gender, ttype):
    """Кошница „пол + възраст" от данните на турнира. None = НЕ сме сигурни,
    а тогава мачът изобщо не влиза в рейтинга. По-добре мълчание от измислица.

    Полът идва от полето Gender на VIS (0 = мъже, 1 = жени). 2 означава
    смесени игри (Панамерикански, Азиатски и т.н. — мъжете и жените са В ЕДИН
    турнир) и се изхвърля. Възрастта идва от името, защото Type НЕ я носи:
    юношески турнири се срещат под почти всеки Type."""
    tk = vol_tokens(name)
    ts = set(tk)
    if ts & VOL_AMBIG:
        return None
    g = str(gender if gender is not None else "").strip()
    sex = "m" if g == "0" else ("w" if g == "1" else None)
    if sex is None:
        return None
    men, wom = bool(ts & VOL_MEN), bool(ts & VOL_WOMEN)
    if men and wom:
        return None
    if (men and sex == "w") or (wom and sex == "m"):
        return None                     # полето и името се карат -> не гадаем
    youth = bool(ts & VOL_YOUTH) or str(ttype if ttype is not None else "").strip() == "16"
    if not youth:
        for i, w in enumerate(tk):
            if w[:1] == "u" and w[1:].isdigit() and 12 <= int(w[1:]) <= 23:
                youth = True
            elif w == "under" and i + 1 < len(tk) and tk[i + 1].isdigit() and int(tk[i + 1]) <= 23:
                youth = True
    return sex + ("-you" if youth else "-sen")


def vol_ident(name):
    """Отпечатък на отбора: (същина на името, код на държавата от скобите).
    Кошницата пази мъже/жени/юноши, но кодът се преизползва и за РАЗЛИЧНИ
    клубове в една и съща кошница — проверено на живо: PAD е и „Sonepar
    Padova", и „Port Autonome de Douala (CMR)"; AHL е и „Al-Ahli (BRN)",
    и „Al Ahly (EGY)"; KPC е и „Kenya Pipeline", и „Kenya Ports Authority".
    Отпечатъкът ги разделя, вместо да ги слее в един измислен рейтинг."""
    s = str(name if name is not None else "")
    core, tag, depth, buf = [], "", 0, []
    for ch in s:
        if ch == "(":
            depth += 1
            buf = []
        elif ch == ")":
            if depth == 1:
                t = "".join(buf).strip()
                if len(t) == 3 and t.isalpha():
                    tag = t.lower()
            depth = max(0, depth - 1)
        elif depth > 0:
            buf.append(ch)
        else:
            core.append(ch)
    tk = [("st" if w == "saint" else w) for w in vol_tokens("".join(core))]
    return "".join(w for w in tk if w not in VOL_GENERIC), tag


def vol_same_team(a, b):
    """Един и същи отбор ли са двата отпечатъка? Спонсорът се сменя всеки сезон
    („Sir Susa Vim Perugia" / „Sir Sicoma Monini Perugia"), затова приемаме и
    когато едното име се съдържа в другото. Различна държава в скобите = НЕ."""
    if not a or not b or len(a) < 2 or len(b) < 2:
        return False
    ca, ta = str(a[0] or ""), str(a[1] or "")
    cb, tb = str(b[0] or ""), str(b[1] or "")
    if ta and tb and ta != tb:
        return False
    if not ca or not cb:
        return False
    return ca == cb or ca in cb or cb in ca


def vol_tournaments():
    """Справочник турнири: име + кошница. Едно повикване за целия рън."""
    if _vol_meta_done[0]:
        return _vol_meta
    _vol_meta_done[0] = True
    try:
        root = vis_xml('<Request Type="GetVolleyTournamentList" '
                       'Fields="No Title Name Season Gender Type"></Request>')
        for t in root:
            no = t.get("No") or ""
            nm = t.get("Title") or t.get("Name") or ""
            if no:
                _vol_meta[no] = {"name": nm,
                                 "bucket": vol_bucket(nm, t.get("Gender"), t.get("Type"))}
    except Exception as e:      # noqa: BLE001
        print("   ⚠ волейбол, справочник турнири: " + str(e)[:60])
    return _vol_meta


def vol_fixtures(now, ymd_dash):
    # КАПАН: правилните имена са FirstDate/LastDate. DateFrom/DateTo се ПРЕНЕБРЕГВАТ
    # мълчаливо и сървърът връща целия архив от 28 000 реда.
    req = ('<Request Type="GetVolleyMatchList" Fields="No TeamAName TeamBName TeamACode '
           'TeamBCode DateTimeUtc Status NoTournament City"><Filter FirstDate="'
           + ymd_dash + '" LastDate="' + ymd_dash + '"/></Request>')
    try:
        root = vis_xml(req)
    except Exception as e:      # noqa: BLE001
        print("   ⚠ волейбол: " + str(e)[:70])
        return []
    n = to_num(root.get("NbItems"))
    if n is not None and n > 400:
        print("   ⚠ волейбол: филтърът по дата не е сработил (" + str(n) + " реда) — пропускам.")
        return []
    meta = vol_tournaments()
    out, no_bucket = [], 0
    for m in root:
        if str(m.get("Status") or "") != "1":       # 1 = насрочен, още не е игран
            continue
        ca, cb = (m.get("TeamACode") or "").strip(), (m.get("TeamBCode") or "").strip()
        na, nb = (m.get("TeamAName") or "").strip(), (m.get("TeamBName") or "").strip()
        tno = str(m.get("NoTournament") or "")
        if not ca or not cb or not na or not nb or tno in VOL_DECOYS:
            continue
        t = meta.get(tno) or {}
        tname = t.get("name") or "Волейбол"
        if tname.strip().upper().startswith(("TEST", "SIM")):
            continue
        vb = t.get("bucket")
        if not vb:
            # Без ясна кошница (пол/възраст) няма и с какво да сравняваме.
            no_bucket += 1
            continue
        out.append({
            "bucket": "volleyball", "emoji": "🏐", "src": "fivb",
            "home": bg_name(na), "away": bg_name(nb),
            "home_id": ca, "away_id": cb,
            "league": tname, "weight": 8, "when": parse_iso(m.get("DateTimeUtc")),
            "extra": {"vb": vb, "id_h": vol_ident(na), "id_a": vol_ident(nb)},
        })
    if no_bucket:
        print("   волейбол: " + str(no_bucket)
              + " срещи без ясна кошница (пол/възраст) — пропуснати.")
    return out


def vol_fit(raw):
    """raw = (кошница, кодA, отпечатъкA, кодB, отпечатъкB, точкиA, точкиB, тегло).
    Прави три неща и всяко от тях спира по един начин да се излъже:
      1) отсява редовете, в които кодът очевидно е ДРУГ отбор;
      2) напасва Брадли-Тери ОТДЕЛНО за всяка кошница — иначе центрирането
         около нулата смесва мъже, жени и юноши в един мащаб;
      3) реже отборите на свързани групи: две сили, между които няма НИТО
         една верига от изиграни мачове, не са сравними и не се сравняват."""
    _vol_rating.clear()
    _vol_count.clear()
    _vol_ident.clear()
    _vol_comp.clear()
    _vol_rows.clear()

    seen = {}
    for b, ca, ia, cb, ib, _pa, _pb, _w in raw:
        for c, i in ((ca, ia), (cb, ib)):
            d = seen.setdefault((b, c), {})
            d[i] = d.get(i, 0) + 1
    for k, d in seen.items():
        _vol_ident[k] = max(d.items(), key=lambda kv: (kv[1], len(kv[0][0])))[0]

    by_bucket = {}
    for b, ca, ia, cb, ib, pa, pb, w in raw:
        ka, kb = (b, ca), (b, cb)
        if not vol_same_team(ia, _vol_ident.get(ka)):
            continue
        if not vol_same_team(ib, _vol_ident.get(kb)):
            continue
        by_bucket.setdefault(b, []).append((ka, kb, pa, pb, w))
        _vol_count[ka] = _vol_count.get(ka, 0) + 1
        _vol_count[kb] = _vol_count.get(kb, 0) + 1

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for b, rows in by_bucket.items():
        _vol_rows[b] = len(rows)
        _vol_rating.update(fit_bt(rows))
        for ka, kb, _pa, _pb, _w in rows:
            ra, rb = find(ka), find(kb)
            if ra != rb:
                parent[ra] = rb
    for k in list(_vol_rating):
        _vol_comp[k] = find(k)
    return _vol_rating, _vol_count


def vol_ratings(now):
    """Сила по РАЗИГРАВАНИЯ, коригирана за съперника (Брадли-Тери).
    Точките по сетове са несравнимо по-малко шумни от 3-0 / 3-1.
    Ключът е (кошница, код) — виж бележката в началото на секцията."""
    if _vol_fit_done[0]:
        return _vol_rating, _vol_count
    _vol_fit_done[0] = True             # падне ли заявката, не я повтаряме 5 пъти
    meta = vol_tournaments()
    if not meta:
        return _vol_rating, _vol_count
    first = (now - timedelta(days=3 * 365)).strftime("%Y-%m-%d")
    fields = ("No TeamACode TeamBCode TeamAName TeamBName MatchPointsA MatchPointsB NbSets "
              "DateTimeLocal Status NoTournament PointsTeamASet1 PointsTeamASet2 "
              "PointsTeamASet3 PointsTeamASet4 PointsTeamASet5 PointsTeamBSet1 "
              "PointsTeamBSet2 PointsTeamBSet3 PointsTeamBSet4 PointsTeamBSet5")
    req = ('<Request Type="GetVolleyMatchList" Fields="' + fields + '"><Filter FirstDate="'
           + first + '" LastDate="' + now.strftime("%Y-%m-%d") + '"/></Request>')
    try:
        root = vis_xml(req)
    except Exception as e:      # noqa: BLE001
        print("   ⚠ волейбол, история: " + str(e)[:70])
        return _vol_rating, _vol_count
    raw, seen, skipped = [], set(), 0
    for m in root:
        if str(m.get("Status") or "") != "25":      # 25 = официален резултат
            continue
        mid = m.get("No") or ""
        if mid in seen:
            continue
        seen.add(mid)
        tno = str(m.get("NoTournament") or "")
        if tno in VOL_DECOYS:
            continue
        b = (meta.get(tno) or {}).get("bucket")
        if not b:
            skipped += 1                # неясен пол/възраст -> ИЗВЪН напасването
            continue
        ca, cb = (m.get("TeamACode") or "").strip(), (m.get("TeamBCode") or "").strip()
        if not ca or not cb:
            continue
        ia, ib = vol_ident(m.get("TeamAName")), vol_ident(m.get("TeamBName"))
        if not ia[0] or not ib[0]:
            continue
        d = str(m.get("DateTimeLocal") or "")[:10]
        yr = to_num(d[:4])
        if yr is None or yr < 1990 or yr > now.year:      # архивът носи и 0202 / 2568
            continue
        pa = pb = 0
        for i in range(1, 6):
            x = to_num(m.get("PointsTeamASet" + str(i)))
            y = to_num(m.get("PointsTeamBSet" + str(i)))
            if x is not None and y is not None:
                pa += x
                pb += y
        if pa + pb < 50:
            continue
        w = decay_weight(d, now, VOL_HALFLIFE)
        raw.append((b, ca, ia, cb, ib, pa, pb, w))
    vol_fit(raw)
    kept = sum(_vol_rows.values())
    print("   волейбол: " + str(kept) + " изиграни мача в извадката ("
          + ", ".join(VOL_BUCKET_BG.get(b, b) + " " + str(n)
                      for b, n in sorted(_vol_rows.items())) + "; "
          + str(len(raw) - kept) + " отпаднали по отпечатък, "
          + str(skipped) + " без ясна кошница).")
    return _vol_rating, _vol_count


def model_volleyball(fx, now):
    ex = fx.get("extra") or {}
    b = ex.get("vb")
    if not b:
        return None                     # без кошница НЕ гадаем (резервният източник)
    r, cnt = vol_ratings(now)
    ka, kb = (b, str(fx.get("home_id"))), (b, str(fx.get("away_id")))
    if ka not in r or kb not in r:
        return None
    if _vol_rows.get(b, 0) < VOL_MIN_ROWS:
        return None                     # кошницата е празна -> няма от какво да смятаме
    # Същият код, но ДРУГ отбор (PAD = и Падова, и Дуала) -> мълчим.
    if not vol_same_team(ex.get("id_h"), _vol_ident.get(ka)):
        return None
    if not vol_same_team(ex.get("id_a"), _vol_ident.get(kb)):
        return None
    # Двете сили трябва да са от една свързана група. Клуб от Серия А и
    # национален отбор никога не са се срещали — разликата им е измислица.
    if _vol_comp.get(ka) != _vol_comp.get(kb):
        return None
    p_rally = clampf(logistic(r[ka] - r[kb]), VOL_P_MIN, VOL_P_MAX)
    p_set = race_prob(p_rally, 25)
    p5 = race_prob(0.5 + (p_rally - 0.5) * 0.7, 15)     # тайбрекът е по-нервен
    dist = bo_distribution(p_set, 3, p5)
    dist_a = bo_distribution(1.0 - p_set, 3, 1.0 - p5)
    # Сметката приема разиграванията за НЕЗАВИСИМИ. В истински мач те не са:
    # сервис-серии, смени на посоката и нерви правят обратите по-чести,
    # отколкото чистата вероятност допуска. Затова свиваме към монетата.
    p_home = 0.5 + (sum(x[2] for x in dist) - 0.5) * 0.92
    return {"p_home": clampf(p_home, 0.08, 0.92), "p_away": clampf(1.0 - p_home, 0.08, 0.92),
            "p_rally": p_rally, "p_set": p_set, "dist_h": dist, "dist_a": dist_a,
            "n_h": cnt.get(ka, 0), "n_a": cnt.get(kb, 0), "vb": b,
            "thin": _vol_rows.get(b, 0) < VOL_THIN_ROWS}


# ----------------------------------------------------------------- 🏓 ТЕНИС НА МАСА (WTT)
WTT_CDN = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net"
WTT_TTU = "https://wttcmsapigateway-new.azure-api.net/ttu/"
# Ключът стои открито в главния JS на worldtabletennis.com. Само за /ttu/ —
# ранглистата иска и подправени Origin/Referer и затова НЕ я пипаме.
WTT_HEAD = {"ApiKey": "2bf8b222-532c-4c60-8ebe-eb6fdfebe84a"}
TT_SCALE = 0.55
TT_P_MIN, TT_P_MAX = 0.15, 0.85
_tt_stats = {}


def dget(d, *names):
    """Полетата на WTT идват ту с долни черти, ту с главни букви."""
    if not isinstance(d, dict):
        return None
    low = {str(k).lower().replace("_", ""): v for k, v in d.items()}
    for n in names:
        k = str(n).lower().replace("_", "")
        if k in low:
            return low[k]
    return None


def _unwrap(x):
    while isinstance(x, list) and x:
        x = x[0]
    return x if isinstance(x, dict) else {}


def tt_fixtures(now, ymd_dash):
    try:
        cal = http_json(WTT_CDN + "/websitestaticapifiles/general/"
                        + str(now.year) + "_eventcalendar.json")
    except Exception as e:      # noqa: BLE001
        print("   ⚠ тенис на маса: " + str(e)[:80])
        return []
    rows = []
    for blk in (cal if isinstance(cal, list) else [cal or {}]):
        rows += ((blk or {}).get("rows") or [])
    live = []
    for r in rows:
        s = str(dget(r, "StartDateTime") or "")[:10]
        e = str(dget(r, "EndDateTime") or "")[:10]
        eid = to_num(dget(r, "EventId"))
        if eid and s and e and s <= ymd_dash <= e:
            live.append((eid, str(dget(r, "EventName") or "WTT")))
    out = []
    for eid, ename in live[:2]:
        sch = http_json(WTT_CDN + "/websitecacheddata/" + str(eid)
                        + "/schedule/schedule.json", quiet=True)
        units = []
        for blk in (sch if isinstance(sch, list) else [sch or {}]):
            units += (((blk or {}).get("Competition") or {}).get("Unit") or [])
        for u in units:
            sub = str(dget(u, "SubEvent") or "")
            if "Singles" not in sub:
                continue        # двойките искат отделен рейтинг на двойката
            starts = ((dget(u, "StartList") or {}).get("Start") or [])
            people = []
            for st in starts:
                ath = ((((st or {}).get("Competitor") or {}).get("Composition") or {})
                       .get("Athlete") or [])
                a = _unwrap(ath)
                code = str(a.get("Code") or "")
                desc = a.get("Description") or {}
                nm = " ".join(x for x in [desc.get("GivenName"), desc.get("FamilyName")] if x)
                if code and nm.strip():
                    people.append((code, nm.strip()))
            if len(people) < 2:
                continue        # финалите стоят празни, докато полуфиналите свършат
            out.append({
                "bucket": "tabletennis", "emoji": "🏓", "src": "wtt",
                "home": people[0][1], "away": people[1][1],
                "home_id": people[0][0], "away_id": people[1][0],
                "league": ename + " · " + sub, "weight": 8,
                "when": parse_iso(str(dget(u, "StartDate") or "")),
                "extra": {"best_of": to_num(dget(u, "MaxGamesPerIndividualMatch")) or 5},
            })
    return out


def tt_player(ittf_id, now):
    """Бърза сводка за 18 месеца: мачове, победи, загуби. Пълната история е
    30-45 секунди на играч и не влиза в един рън — това е съзнателен избор."""
    pid = str(ittf_id)
    if pid in _tt_stats:
        return _tt_stats[pid]
    start = (now - timedelta(days=548)).strftime("%Y-%m-%d")
    j = http_json(WTT_TTU + "Stats/Players/GetStatsByPlayer?StartDate=" + start
                  + "&EndDate=" + now.strftime("%Y-%m-%d") + "&IttfId=" + pid,
                  headers=WTT_HEAD, quiet=True)
    d = _unwrap(j)
    if isinstance(j, dict) and isinstance(j.get("Result"), (list, dict)):
        d = _unwrap(j.get("Result"))
    w = to_num(dget(d, "total_wins", "totalWins"))
    l = to_num(dget(d, "total_losses", "totalLosses"))
    n = to_num(dget(d, "total_matches", "totalMatches"))
    if w is None or l is None:
        out = None
    else:
        out = {"w": w, "l": l, "n": n if n is not None else (w + l),
               "best": to_num(dget(d, "best_rank", "bestRank"))}
    _tt_stats[pid] = out
    return out


def model_tabletennis(fx, now):
    a = tt_player(fx.get("home_id"), now)
    b = tt_player(fx.get("away_id"), now)
    if not a or not b:
        return None
    ra = (a["w"] + 3.0) / (a["w"] + a["l"] + 6.0)
    rb = (b["w"] + 3.0) / (b["w"] + b["l"] + 6.0)
    p = clampf(logistic((logit(ra) - logit(rb)) * TT_SCALE), TT_P_MIN, TT_P_MAX)
    to_win = 4 if int((fx.get("extra") or {}).get("best_of") or 5) >= 7 else 3
    p_game = invert_bo(p, to_win)
    return {"p_home": p, "p_away": 1.0 - p, "a": a, "b": b, "ra": ra, "rb": rb,
            "to_win": to_win, "dist_h": bo_distribution(p_game, to_win),
            "dist_a": bo_distribution(1.0 - p_game, to_win),
            "ok": (a["w"] + a["l"]) >= 5 and (b["w"] + b["l"]) >= 5}


# ----------------------------------------------------------------- ПОСЛЕДНА РЕЗЕРВА
def sdb_fixtures(bucket):
    """TheSportsDB е последна резерва: безплатният ключ дава 1-3 изиграни мача
    и точно затова ботът мълчеше. Държим го само да не остане празна стая."""
    if MB is None:
        return []
    try:
        rows = MB.sportsdb_fixtures(bucket)
    except Exception as e:      # noqa: BLE001
        print("   ⚠ резерва " + bucket + ": " + str(e)[:60])
        return []
    out = []
    for r in rows:
        out.append({
            "bucket": bucket, "emoji": SPORTS[bucket]["emoji"], "src": "sdb",
            "home": bg_name(r.get("home")), "away": bg_name(r.get("away")),
            "home_id": r.get("home_id"), "away_id": r.get("away_id"),
            "league": r.get("league") or "", "weight": max(1, to_num(r.get("weight")) or 1),
            "when": None, "time": r.get("time") or "", "extra": {},
        })
    return out


def sdb_history(fx, side):
    if MB is None:
        return []
    tid = fx.get("home_id") if side == "home" else fx.get("away_id")
    name = fx.get("home") if side == "home" else fx.get("away")
    if not tid:
        return []
    out = []
    try:
        evs = MB.get_last_events(tid)
    except Exception:           # noqa: BLE001
        return []
    for e in evs:
        hs, as_ = to_num(e.get("intHomeScore")), to_num(e.get("intAwayScore"))
        if hs is None or as_ is None:
            continue
        hid, aid = str(e.get("idHomeTeam") or ""), str(e.get("idAwayTeam") or "")
        if hid == str(tid):
            is_home = True
        elif aid == str(tid):
            is_home = False
        elif e.get("strHomeTeam") == name:
            is_home = True
        elif e.get("strAwayTeam") == name:
            is_home = False
        else:
            continue
        gf, ga = (hs, as_) if is_home else (as_, hs)
        if not sane_record(fx["bucket"], gf, ga):
            continue
        out.append({"gf": gf, "ga": ga, "home": is_home,
                    "date": str(e.get("dateEvent") or "")[:10], "opp": ""})
    return out


# ================================================================= АНАЛИЗ
def history_for(fx, side):
    if fx.get("src") == "sdb":
        return sdb_history(fx, side)
    b = fx["bucket"]
    if b == "football":
        return football_history(fx, side)
    if b == "basketball":
        return basketball_history(fx, side)
    if b == "baseball":
        return baseball_history(fx, side)
    return []


def samp(a, b):
    return "извадка " + str(int(a)) + "+" + str(int(b)) + " мача"


def one(x, d=1):
    return ("%." + str(d) + "f") % float(x)


# --- ФИШ-ЕЗИКЪТ ---------------------------------------------------------------
# Прогнозата се изписва като на фиш: 1 / Х / 2, после кой. Никакви гатанки.
OU_MIN = 0.57           # ред „Над/Под 2.5 гола" само когато матрицата е категорична


def pick_1x2(p1, px, p2, home, away):
    """Футболният избор на фиш-език. Връща (текст, вероятност)."""
    if p1 >= px and p1 >= p2:
        return "1 · победа " + str(home), p1
    if p2 >= px and p2 >= p1:
        return "2 · победа " + str(away), p2
    return "Х · равен", px


def pick_win(fav_home, home, away):
    """Отборните спортове без равен: 1 · победа <отбор> или 2 · победа <отбор>."""
    return ("1 · победа " + str(home)) if fav_home else ("2 · победа " + str(away))


def pick_name(fav_home, home, away):
    """Индивидуалните спортове: 1 · <име> или 2 · <име>."""
    return ("1 · " + str(home)) if fav_home else ("2 · " + str(away))


def over_under_line(p_over):
    """Ред „Над/Под 2.5 гола" от готовата голова матрица (P на общо 3+ гола).
    Излиза само когато едната страна е поне 57% — иначе редът е шум."""
    p = float(p_over)
    if p >= OU_MIN:
        return "Над 2.5 гола: <b>" + pct(p) + "</b>"
    if (1.0 - p) >= OU_MIN:
        return "Под 2.5 гола: <b>" + pct(1.0 - p) + "</b>"
    return ""


def analyse(fx, ctx):
    """Връща (анализ, причина). Кратък изход: избор, вероятност, две причини."""
    now = ctx["now"]
    b = fx["bucket"]
    need = MIN_PER_SIDE.get(b, 4)
    hr = ar = []
    if need > 0:
        hr, ar = history_for(fx, "home"), history_for(fx, "away")
        if len(hr) < need or len(ar) < need:
            return None, ("няма история (" + str(len(hr)) + " и " + str(len(ar))
                          + " мача, трябват по " + str(need) + ")")

    home, away = esc(fx["home"]), esc(fx["away"])
    second, why = "", []

    if b == "football":
        m = model_football(hr, ar, ctx["lvl"], now)
        if not m:
            return None, "няма история"
        p1, px, p2 = m["p_home"], m["p_draw"], m["p_away"]
        # Фиш-език: 1 / Х / 2, никакво „не губи". Равен най-вероятен = Х.
        pick, p = pick_1x2(p1, px, p2, fx["home"], fx["away"])
        strength = strength_1x2(p1, px, p2)
        # Ред Над/Под 2.5 гола направо от головата матрица, само при >= 57%.
        second = over_under_line(m["p_over"])
        why = [home + ": " + one(m["sh"]["gf"], 2) + " вкарани и " + one(m["sh"]["ga"], 2)
               + " допуснати гола за мач (" + str(m["sh"]["n"]) + " мача)",
               away + ": " + one(m["sa"]["gf"], 2) + " вкарани и " + one(m["sa"]["ga"], 2)
               + " допуснати гола за мач (" + str(m["sa"]["n"]) + " мача)"]
        n_eff = m["sh"]["w"] + m["sa"]["w"]
        sample = samp(m["sh"]["n"], m["sa"]["n"])

    elif b == "basketball":
        m = model_basketball(hr, ar, fx, now)
        if not m:
            return None, "няма история"
        fav_home = m["p_home"] >= 0.5
        pick = pick_win(fav_home, fx["home"], fx["away"])   # в баскетбола няма Х
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        second = ("Очакван резултат: ~" + str(int(round(m["exp_h"])))
                  + ":" + str(int(round(m["exp_a"]))))
        why = [home + ": " + one(m["sh"]["gf"]) + " : " + one(m["sh"]["ga"])
               + " точки за мач (" + str(m["sh"]["n"]) + " мача)",
               away + ": " + one(m["sa"]["gf"]) + " : " + one(m["sa"]["ga"])
               + " точки за мач (" + str(m["sa"]["n"]) + " мача)"]
        n_eff = m["sh"]["w"] + m["sa"]["w"]
        sample = samp(m["sh"]["n"], m["sa"]["n"])

    elif b == "volleyball":
        m = model_volleyball(fx, now)
        if not m:
            return None, "няма история"
        if min(m["n_h"], m["n_a"]) < 6:
            return None, "няма история (" + str(m["n_h"]) + " и " + str(m["n_a"]) + " мача)"
        fav_home = m["p_home"] >= 0.5
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        dist = m["dist_h"] if fav_home else m["dist_a"]
        best = max(dist, key=lambda x: x[2])
        # Най-вероятният сетов резултат влиза в самата прогноза: „(3:1)".
        pick = (pick_win(fav_home, fx["home"], fx["away"])
                + " (" + str(best[0]) + ":" + str(best[1]) + ")")
        rate = m["p_rally"] if fav_home else 1.0 - m["p_rally"]
        kosh = VOL_BUCKET_BG.get(m.get("vb"), m.get("vb"))
        why = [(home if fav_home else away) + " печели " + one(rate * 100.0)
               + "% от разиграванията срещу този съперник",
               "Сила по точки, а не по 3-0/3-1, и само при " + str(kosh)
               + " — мъже, жени и юноши не се смесват"]
        n_eff = min(m["n_h"], m["n_a"])
        if m.get("thin"):
            n_eff = min(n_eff, 9.0)     # тънка кошница = най-много една звезда
        sample = samp(m["n_h"], m["n_a"])

    elif b == "tabletennis":
        m = model_tabletennis(fx, now)
        if not m:
            return None, "няма история"
        if not m["ok"]:
            return None, "няма история (под 5 мача за 18 месеца)"
        fav_home = m["p_home"] >= 0.5
        pick = pick_name(fav_home, fx["home"], fx["away"])
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        dist = m["dist_h"] if fav_home else m["dist_a"]
        best = max(dist, key=lambda x: x[2])
        second = ("Най-вероятен резултат: <b>" + str(best[0]) + ":" + str(best[1]) + "</b>")
        why = [home + ": " + str(m["a"]["w"]) + "-" + str(m["a"]["l"]) + " за 18 месеца",
               away + ": " + str(m["b"]["w"]) + "-" + str(m["b"]["l"]) + " за 18 месеца"]
        n_eff = (m["a"]["w"] + m["a"]["l"] + m["b"]["w"] + m["b"]["l"]) / 2.0
        sample = samp(m["a"]["w"] + m["a"]["l"], m["b"]["w"] + m["b"]["l"])

    elif b == "tennis":
        m = model_tennis(fx, now)
        if not m["ok"]:
            return None, "няма история (некласиран и без изиграни мачове)"
        fav_home = m["p_home"] >= 0.5
        pick = pick_name(fav_home, fx["home"], fx["away"])
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        def _pl(nm, r, f):
            s = nm
            if r.get("rank"):
                s += ": №" + str(r["rank"]) + " в ранглистата"
            else:
                s += ": извън първите 150"
            if (f[0] + f[1]) >= 3:      # 0-1 не е форма, а шум — не го пишем
                s += ", " + str(f[0]) + "-" + str(f[1]) + " в последните седмици"
            return s
        why = [_pl(home, m["ra"], m["fa"]), _pl(away, m["rb"], m["fb"])]
        # Ранглистата е силен ориентир, но е ЕДИН показател, не двайсет мача.
        # Брои се за шест мача на играч, не повече — иначе картата се хвали с
        # „добра увереност" върху три видени мача, което е точно лъжата,
        # която не искаме да продаваме.
        ranked = (1 if m["ra"].get("rank") else 0) + (1 if m["rb"].get("rank") else 0)
        n_eff = min(30.0, m["n_a"] + m["n_b"] + 6.0 * ranked)
        if min(m["n_a"], m["n_b"]) < 6:
            n_eff = min(n_eff, 19.0)    # под 6 видени мача = най-много две звезди
        sample = ("ранглиста + " + str(m["n_a"]) + "+" + str(m["n_b"]) + " скорошни мача")

    elif b == "mma":
        m = model_mma(fx, now)
        if not m["ok"]:
            return None, "няма история (под 3 боя в кариерата)"
        fav_home = m["p_home"] >= 0.5
        pick = pick_name(fav_home, fx["home"], fx["away"])
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        fin = m["fin_h"] if fav_home else m["fin_a"]
        wins = m["win_h"] if fav_home else m["win_a"]
        if fin is not None and fin >= 0.6:
            second = ("Печели предсрочно в " + str(int(round(fin * wins))) + " от "
                      + str(wins) + " победи в индекса")
        rh, ra_ = m["rec_h"], m["rec_a"]
        why = [home + ": " + str(rh[0]) + "-" + str(rh[1]) + " в кариерата, "
               + str(m["na"]) + " боя в индекса",
               away + ": " + str(ra_[0]) + "-" + str(ra_[1]) + " в кариерата, "
               + str(m["nb"]) + " боя в индекса"]
        n_eff = m["na"] + m["nb"] + 0.4 * (rh[0] + rh[1] + ra_[0] + ra_[1])
        sample = str(m["na"]) + "+" + str(m["nb"]) + " боя в индекса"

    elif b == "hockey":
        m = model_hockey(fx)
        if not m:
            return None, "няма история"
        fav_home = m["p_home"] >= 0.5
        # Моделът дели равенството от редовното време наполовина (продължения =
        # монета), затова изборът е 1/2 и важи ЗА МАЧА, не за редовното време.
        pick = pick_win(fav_home, fx["home"], fx["away"]) + " (в мача)"
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        second = ("Очаквани голове " + one(m["lam_h"]) + " : " + one(m["lam_a"])
                  + " · над 5.5: " + pct(m["p_over55"]))
        why = [home + " у дома: " + one(m["hgf"], 2) + " вкарани и " + one(m["hga"], 2)
               + " допуснати гола за мач",
               away + " на гости: " + one(m["agf"], 2) + " вкарани и " + one(m["aga"], 2)
               + " допуснати; равен няма, продълженията са близо до монета"]
        n_eff = m["gp_h"] + m["gp_a"]
        sample = samp(m["gp_h"], m["gp_a"])

    elif b == "baseball":
        m = model_baseball(hr, ar, now)
        if not m:
            return None, "няма история"
        fav_home = m["p_home"] >= 0.5
        pick = pick_name(fav_home, fx["home"], fx["away"])
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        second = "Очаквани рънове " + one(m["exp_h"]) + " : " + one(m["exp_a"])
        why = [home + ": " + one(m["sh"]["gf"]) + " : " + one(m["sh"]["ga"])
               + " рънa за мач (" + str(m["sh"]["n"]) + " мача)",
               away + ": " + one(m["sa"]["gf"]) + " : " + one(m["sa"]["ga"])
               + " рънa за мач (" + str(m["sa"]["n"]) + " мача)"]
        n_eff = m["sh"]["w"] + m["sa"]["w"]
        sample = samp(m["sh"]["n"], m["sa"]["n"])

    else:
        return None, "непознат спорт"

    if strength < MIN_STRENGTH:
        return None, "числата не дават превес (" + pct(p) + ")"

    return {"fx": fx, "bucket": b, "pick": pick, "p": p, "second": second,
            "why": [w for w in why if w][:2], "sample": sample,
            "n_eff": float(n_eff), "strength": float(strength),
            "stars": grade(b, n_eff, strength)}, ""


# ================================================================= КАРТИТЕ
def card(an, now):
    """Кратка карта. Прогнозата е ГЕРОЯТ, обяснението е два реда."""
    fx = an["fx"]
    lg = str(fx.get("league") or "")
    if len(lg) > 46:
        lg = lg[:45] + "…"
    sub = [x for x in [esc(lg), esc(fx.get("time") or when_label(fx.get("when"), now))] if x]
    stars = an["stars"]
    lines = [fx["emoji"] + " <b>" + esc(fx["home"]) + "</b> 🆚 <b>" + esc(fx["away"]) + "</b>"]
    if sub:
        lines.append("<i>" + " · ".join(sub) + "</i>")
    star_line = ("⭐" * stars) + " · " + esc(an["sample"])
    if stars <= 1:
        star_line += " · малка извадка"
    lines += ["",
              "🎯 <b>ПРОГНОЗА: " + esc(an["pick"]) + " · " + pct(an["p"]) + "</b>",
              star_line]
    if an.get("second"):
        lines.append("↔️ " + an["second"])
    lines.append("")
    for w in an["why"]:
        lines.append("• " + w)
    return NL.join(lines)


def header_card(now, count, seen):
    # Ботът гледа осем пъти на ден, затова заглавието НЕ обещава дневен сбор —
    # то отваря деня. Числото е за това пускане и точно това пише.
    return (chr(129504) + " <b>БОТА ПРЕДРИЧА</b> · " + date_bg(now) + NL
            + "Първи за деня: <b>" + str(count) + "</b> от " + n_match(seen)
            + " под лупата · денят тече, идват още.")


def footer_card(seen, thin, weak, sports):
    return NL.join([
        "📘 ⭐ малка извадка · ⭐⭐ прилична · ⭐⭐⭐ добра",
        ("Гледахме " + n_match(seen) + " от " + str(sports) + " спорта · " + str(thin)
         + " без история · " + str(weak) + " без превес."),
        "🟢 THE GREEN ROOM",
    ])


def nothing_card(now, seen, thin, weak):
    return NL.join([
        chr(129504) + " <b>БОТА ПРЕДРИЧА</b> · " + date_bg(now),
        "",
        "<b>Днес няма прогнози.</b>",
        "Погледнахме " + n_match(seen) + ": " + str(thin) + " без история, "
        + str(weak) + " без превес по числата.",
    ])


# ================================================================= ПОДБОР
def collect_all(now):
    ymd = now.strftime("%Y%m%d")
    ymd_dash = now.strftime("%Y-%m-%d")
    buckets = {}
    for b in ACTIVE_SPORTS:
        rows = []
        try:
            if b == "football":
                rows = football_fixtures(now, ymd)
            elif b == "basketball":
                rows = basketball_fixtures(now, ymd)
            elif b == "tennis":
                rows = tennis_fixtures(now, ymd)
            elif b == "hockey":
                rows = hockey_fixtures(now, ymd_dash)
            elif b == "baseball":
                rows = baseball_fixtures(now, ymd_dash)
            elif b == "mma":
                rows = mma_fixtures(now)
            elif b == "volleyball":
                rows = vol_fixtures(now, ymd_dash)
            elif b == "tabletennis":
                rows = tt_fixtures(now, ymd_dash)
        except Exception as e:      # noqa: BLE001
            print("   ⚠ " + b + ": " + str(e)[:90])
            rows = []
        if not rows and b in ("football", "basketball", "volleyball", "tabletennis"):
            rows = sdb_fixtures(b)
            if rows:
                print("   " + b + ": " + str(len(rows)) + " срещи от резервата TheSportsDB.")
        rows = [r for r in rows
                if not is_placeholder(r.get("home")) and not is_placeholder(r.get("away"))]
        # Пазачът на часа. Осем пускания на ден значи, че в 19:00 списъкът още
        # съдържа мачовете от 13:00 — а прогноза за започнал мач е по-лоша от
        # мълчание. Режем всичко, което тръгва до LEAD_MIN минути.
        n_all = len(rows)
        rows = [r for r in rows if not started(r, now)]
        gone = n_all - len(rows)
        n_near = len(rows)
        rows = [r for r in rows if not too_far(r, now)]
        far = n_near - len(rows)
        rows.sort(key=lambda fx: -fx.get("weight", 0))
        buckets[b] = rows
        print("   " + SPORTS[b]["emoji"] + " " + b + ": " + str(len(rows)) + " срещи"
              + ((" (" + str(gone) + " вече започнали)") if gone else "")
              + ((" (" + str(far) + " далече — чакат)") if far else ""))
    return buckets


def build_pool(buckets):
    """Кръгова подредба: всеки спорт получава шанс, никой не задръства."""
    per = {b: (buckets.get(b) or [])[:PER_SPORT] for b in ACTIVE_SPORTS}
    order = sorted(ACTIVE_SPORTS, key=lambda b: -SPORTS[b]["prio"])
    pool, i = [], 0
    while len(pool) < POOL:
        added = False
        for b in order:
            lst = per.get(b) or []
            if i < len(lst):
                pool.append(lst[i])
                added = True
                if len(pool) >= POOL:
                    break
        if not added:
            break
        i += 1
    return pool


def choose(cands, limit):
    """Най-уверените напред, но без три поредни карти от един спорт."""
    cands.sort(key=lambda a: -(a["stars"] * 1000.0 + a["strength"] * 100.0))
    picked, used, taken = [], {}, set()
    for a in cands:
        if len(picked) >= limit:
            break
        if used.get(a["bucket"], 0) >= 2 and len(cands) > limit:
            continue
        picked.append(a)
        taken.add(id(a))
        used[a["bucket"]] = used.get(a["bucket"], 0) + 1
    for a in cands:
        if len(picked) >= limit:
            break
        if id(a) not in taken:
            picked.append(a)
            taken.add(id(a))
    return picked


def maybe_footer(state, now, seen, thin, weak):
    """Подписът и легендата затварят ДЕНЯ, а не всяко пускане.
    Пуска се веднъж, от вечерното пускане, и само ако денят е имал карти —
    иначе стаята получава осем подписа на ден."""
    fkey = now.strftime("%Y-%m-%d") + "|footer"
    if now.hour < 21 or already_posted(state, fkey) or not posted_today(state, now):
        return False
    if post_predict(footer_card(seen, thin, weak, len(ACTIVE_SPORTS))):
        mark_posted(state, fkey, now)
        persist(state, now)
        return True
    return False


# ================================================================= ГЛАВНО
def run():
    now = datetime.now(SOFIA)
    state = load_state()
    print("Спортове: " + ", ".join(ACTIVE_SPORTS))
    buckets = collect_all(now)
    pool = build_pool(buckets)
    total = sum(len(v) for v in buckets.values())
    if not pool:
        print("Няма нито една среща от сериозните турнири — мълчим.")
        maybe_footer(state, now, 0, 0, 0)
        persist(state, now)
        return

    fresh, seen_keys, seen_pairs = [], set(), set()
    for fx in pool:
        k = match_key(fx, now)
        if already_posted(state, k):
            print("   ⏭ вече е пусната: " + str(fx.get("home")) + " - " + str(fx.get("away")))
            continue
        # Двойката отбори БЕЗ датата. Бейзболът играе по два мача в един ден
        # срещу същия съперник (а сериите вървят и през полунощ по българско),
        # и моделът няма как да ги различи: същите отбори, същата статистика,
        # една и съща карта. Един и същ противник = НАЙ-МНОГО ЕДНА карта на
        # пускане. Втората среща не се губи — тя чака следващото пускане,
        # когато първата вече е в тефтера и не ѝ прави компания.
        pair = k.split("|", 1)[1]
        if k in seen_keys or pair in seen_pairs:
            print("   ⏭ дубликат в списъка: " + str(fx.get("home")) + " - " + str(fx.get("away")))
            continue
        seen_keys.add(k)
        seen_pairs.add(pair)
        fx["_key"] = k
        fresh.append(fx)
    if not fresh:
        print("Всичко от днешния списък вече е пуснато — мълча (без повторения).")
        maybe_footer(state, now, 0, 0, 0)
        persist(state, now)
        return
    print("Под лупата: " + n_match(len(fresh)) + " от " + str(total) + " събрани.")

    # Нивото на футбола се смята от ЦЯЛАТА събрана извадка, не от един мач.
    foot = []
    for fx in fresh:
        if fx["bucket"] == "football":
            foot += football_history(fx, "home") + football_history(fx, "away")
    ctx = {"now": now, "lvl": league_level(foot, now)}
    if foot:
        print("Ниво на футбола в извадката: " + one(ctx["lvl"], 2)
              + " гола на отбор (" + str(len(foot)) + " мача).")

    cands, thin, weak = [], 0, 0
    for fx in fresh:
        name = str(fx.get("home")) + " - " + str(fx.get("away"))
        try:
            an, why_not = analyse(fx, ctx)
        except Exception as e:      # noqa: BLE001
            print("   анализ " + name + ": " + str(e)[:110])
            an, why_not = None, "грешка в данните"
        if an is None:
            if "превес" in why_not:
                weak += 1
            else:
                thin += 1
            print("   пропускам " + name + ": " + why_not)
            continue
        cands.append(an)
        print("   ✔ " + name + ": " + an["pick"] + " " + pct(an["p"])
              + ", " + str(an["stars"]) + " звезди")

    seen = len(fresh)
    if not cands:
        # „Днес няма прогнози" се казва НАЙ-МНОГО ВЕДНЪЖ и не преди обяд:
        # в 04:00 денят още не е започнал и такава карта е само шум.
        nkey = now.strftime("%Y-%m-%d") + "|nothing"
        if now.hour >= 12 and not posted_today(state, now) and not already_posted(state, nkey):
            if post_predict(nothing_card(now, seen, thin, weak)):
                mark_posted(state, nkey, now)   # подпис не слагаме — картата си е подпис
        else:
            print("Нищо ново убедително — мълча.")
            maybe_footer(state, now, seen, thin, weak)
        persist(state, now)
        return

    room = MAX_DAY - cards_today(state, now)
    if room <= 0:
        print("Дневният таван (" + str(MAX_DAY) + " прогнози) е стигнат — мълча до утре.")
        maybe_footer(state, now, seen, thin, weak)
        persist(state, now)
        return

    picks = choose(cands, min(MAX_PICKS, room))
    sent = 0
    hkey = now.strftime("%Y-%m-%d") + "|header"
    if not already_posted(state, hkey):
        if post_predict(header_card(now, len(picks), seen)):
            mark_posted(state, hkey, now)
            persist(state, now)
            sent += 1
        time.sleep(SEND_GAP)
    for a in picks:
        if post_predict(card(a, now)):
            mark_posted(state, a["fx"]["_key"], now)
            # Записваме СЛЕД ВСЯКА карта, не в края. Ако рънът умре на третата,
            # първите две са вече в тефтера и следващият рън не ги повтаря.
            persist(state, now)
            sent += 1
        time.sleep(SEND_GAP)
    if maybe_footer(state, now, seen, thin, weak):
        sent += 1
    persist(state, now)
    print("Готово: " + str(len(picks)) + " прогнози, " + str(sent) + " съобщения -> стая "
          + PREDICT_THREAD + "; " + str(_http_used[0]) + " заявки, " + str(_http_fail[0])
          + " провала" + (" (СУХО ПУСКАНЕ — нищо не е пратено)" if DRY_RUN else ""))


# ================================================================= САМОПРОВЕРКА
def selftest():
    """Математиката, пазачите и тефтерът. Без мрежа — може да се пуска навсякъде."""
    global STATE_FILE
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    # --- Поасон и Диксън-Коулс
    check("Поасон сумира до 1", abs(sum(poisson_pmf(k, 1.5) for k in range(0, 40)) - 1.0) < 1e-9)
    check("Поасон P(0|1.5)", abs(poisson_pmf(0, 1.5) - 0.22313016) < 1e-6)
    check("Поасон P(2|2.0)", abs(poisson_pmf(2, 2.0) - 0.27067057) < 1e-6)
    mx = score_matrix(1.6, 1.2)
    check("матрицата е нормирана", abs(sum(sum(r) for r in mx) - 1.0) < 1e-9)
    mk = matrix_markets(mx)
    check("1 + X + 2 = 1", abs(mk["p_home"] + mk["p_draw"] + mk["p_away"] - 1.0) < 1e-9)
    check("повече очаквани голове = фаворит", mk["p_home"] > mk["p_away"])
    plain = matrix_markets(score_matrix(1.6, 1.2, rho=0.0))
    check("Диксън-Коулс вдига равенствата", mk["p_draw"] > plain["p_draw"])
    check("всички клетки са положителни", min(min(r) for r in mx) >= 0.0)

    # --- логистика и баскетбол
    check("логистична(0) = 0.5", abs(logistic(0.0) - 0.5) < 1e-12)
    sc = 11.5 * math.sqrt(3.0) / math.pi
    check("6 точки преднина -> 68-74%", 0.68 < logistic(6.0 / sc) < 0.74)
    check("10 точки преднина -> 79-86%", 0.79 < logistic(10.0 / sc) < 0.86)

    # --- надпревара до N и best-of
    check("равни разигравания -> 50% сет", abs(race_prob(0.5, 25) - 0.5) < 1e-9)
    check("равни разигравания -> 50% гейм", abs(race_prob(0.5, 11) - 0.5) < 1e-9)
    check("55% разигравания -> голям превес в сета", 0.75 < race_prob(0.55, 25) < 0.90)
    check("надпреварата расте с p", race_prob(0.52, 25) > race_prob(0.51, 25))
    check("равни сетове -> 50% мач", abs(bo_match_prob(0.5, 3) - 0.5) < 1e-12)
    check("60% на сет -> 68-75% на мач", 0.68 < bo_match_prob(0.6, 3) < 0.75)
    d = bo_distribution(0.62, 3)
    check("разпределението сумира до мача", abs(sum(x[2] for x in d) - bo_match_prob(0.62, 3)) < 1e-12)
    check("3-0 е по-често от 3-2 при силен фаворит", d[0][2] > d[2][2])
    check("обратната сметка се връща вярно", abs(bo_match_prob(invert_bo(0.72, 3), 3) - 0.72) < 1e-6)
    check("best-of-7 има четири изхода", len(bo_distribution(0.6, 4)) == 4)

    # --- Elo, Брадли-Тери, свиване, свежест
    check("Elo при равни е 50%", abs(elo_expect(1500.0, 1500.0) - 0.5) < 1e-12)
    check("Elo +200 е ~76%", 0.74 < elo_expect(1700.0, 1500.0) < 0.78)
    r = fit_bt([("A", "B", 60, 40, 1.0), ("A", "C", 60, 40, 1.0), ("B", "C", 52, 48, 1.0)])
    check("Брадли-Тери подрежда силата", r["A"] > r["B"] > r["C"])
    check("Брадли-Тери е центриран", abs(sum(r.values())) < 1e-6)
    check("свиването пази средното", abs(shrink(3.0, 1.0, 0, 4.0) - 1.0) < 1e-12)
    check("свиването тегли към извадката", shrink(3.0, 1.0, 100, 4.0) > 2.8)
    now = datetime(2026, 7, 28, 12, 0, tzinfo=SOFIA)
    check("днешният мач тежи 1", abs(decay_weight("2026-07-28", now, 400.0) - 1.0) < 0.02)
    check("мач отпреди 400 дни тежи ~0.5", abs(decay_weight("2025-06-24", now, 400.0) - 0.5) < 0.05)
    ws = wstats([{"gf": 2, "ga": 1, "home": True, "date": "2026-07-01"},
                 {"gf": 0, "ga": 3, "home": False, "date": "2026-07-10"}], now, 400.0)
    check("претеглените средни работят", ws and 0.9 < ws["gf"] < 1.1 and ws["n"] == 2)
    check("домакинските мачове се броят отделно", ws["wh"] > 0 and ws["wa"] > 0)

    # --- 🏐 волейбол: ЕДИН код на държава, ТРИ различни отбора
    # Това е бъгът, който се хвана на живо: кодът ALG стои този сезон и в
    # „CAVB Boys' U18", и в „CAVB Girls' U18", и в „CAVB Zone I Men". Ако
    # рейтингът се води само по кода, мъже, жени и юноши стават една сила.
    check("мъжки турнир -> кошница мъже",
          vol_bucket("CAVB Zone I Men Nations Championship", "0", "20") == "m-sen")
    check("юноши U18 -> кошница юноши",
          vol_bucket("CAVB Boys' U18 Championship 2026", "0", "10") == "m-you")
    check("девойки U18 -> кошница девойки",
          vol_bucket("CAVB Girls' U18 Championship 2026", "1", "10") == "w-you")
    check("женски турнир -> кошница жени",
          vol_bucket("Women's Volleyball Nations League 2026", "1", "1") == "w-sen")
    check("Under 19 се разчита и с думи",
          vol_bucket("FIVB Volleyball Under 19 World Championship", "0", "1") == "m-you")
    check("смесените игри нямат кошница", vol_bucket("XVI Pan-American Games", "2", "1") is None)
    check("името срещу полето -> без кошница",
          vol_bucket("Women's World Championship", "0", "1") is None)
    check("студентските игри са неясна възраст",
          vol_bucket("30th Summer Universiade 2019 - Men", "0", "17") is None)

    vraw = []
    for _i in range(40):
        vraw.append(("m-sen", "ALG", ("algeria", ""), "TUN", ("tunisia", ""), 100, 70, 1.0))
        vraw.append(("m-sen", "TUN", ("tunisia", ""), "EGY", ("egypt", ""), 85, 85, 1.0))
        vraw.append(("w-sen", "ALG", ("algeria", ""), "TUN", ("tunisia", ""), 70, 100, 1.0))
        vraw.append(("w-sen", "TUN", ("tunisia", ""), "EGY", ("egypt", ""), 85, 85, 1.0))
        vraw.append(("m-you", "ALG", ("algeria", ""), "TUN", ("tunisia", ""), 85, 85, 1.0))
        vraw.append(("m-you", "TUN", ("tunisia", ""), "EGY", ("egypt", ""), 85, 85, 1.0))
    for _i in range(6):     # PAD = Порт Аутоном Дуала (CMR), истинският носител
        vraw.append(("m-sen", "PAD", ("portautonomedouala", "cmr"), "TUN", ("tunisia", ""),
                     100, 60, 1.0))
    for _i in range(3):     # PAD = и Сонепар Падова, СЪЩИЯТ код, друг клуб
        vraw.append(("m-sen", "PAD", ("soneparpadova", ""), "TUN", ("tunisia", ""),
                     60, 100, 1.0))
    for _i in range(4):     # двойка, която не се среща с никого другиго
        vraw.append(("m-sen", "AAA", ("alpha", ""), "BBB", ("beta", ""), 100, 60, 1.0))
    vr, vc = vol_fit(vraw)
    check("волейбол: мъже, жени и юноши са ТРИ отделни ключа",
          ("m-sen", "ALG") in vr and ("w-sen", "ALG") in vr and ("m-you", "ALG") in vr)
    check("волейбол: една държава НЕ дели един рейтинг",
          vr[("m-sen", "ALG")] > 0.1 and vr[("w-sen", "ALG")] < -0.1
          and abs(vr[("m-you", "ALG")]) < 0.02)
    check("волейбол: извадката се брои по кошници",
          vc[("m-sen", "ALG")] == 40 and vc[("w-sen", "ALG")] == 40
          and vc[("m-you", "ALG")] == 40)
    check("волейбол: всяка кошница е центрирана сама за себе си",
          abs(sum(v for k, v in vr.items() if k[0] == "m-you")) < 1e-6
          and abs(sum(v for k, v in vr.items() if k[0] == "m-sen")) < 1e-6)
    check("волейбол: чужд клуб под същия код отпада от напасването",
          _vol_ident[("m-sen", "PAD")] == ("portautonomedouala", "cmr")
          and vc[("m-sen", "PAD")] == 6)
    check("волейбол: несвързаните отбори са в отделна група",
          _vol_comp[("m-sen", "AAA")] != _vol_comp[("m-sen", "ALG")])
    check("волейбол: спонсорът не прави нов отбор",
          vol_same_team(("sirsusaperugia", ""), ("sirsusaperugiavolley", "")))
    check("волейбол: различна държава = различен отбор",
          not vol_same_team(("alahly", "egy"), ("alahli", "brn")))
    check("волейбол: ударенията не цепят отбора",
          vol_ident("Espérance Sportive Tunis")[0] == vol_ident("Esperance Sportive Tunis")[0])

    _vol_fit_done[0] = True             # моделът да смята от таблицата горе, без мрежа
    vfx = {"bucket": "volleyball", "home_id": "ALG", "away_id": "TUN",
           "extra": {"vb": "m-sen", "id_h": ("algeria", ""), "id_a": ("tunisia", "")}}

    def vcopy(**kw):
        f = dict(vfx)
        f["extra"] = dict(vfx["extra"])
        for k, v in kw.items():
            if k in ("vb", "id_h", "id_a"):
                f["extra"][k] = v
            else:
                f[k] = v
        return f

    mv, mw = model_volleyball(vfx, now), model_volleyball(vcopy(vb="w-sen"), now)
    check("волейбол: моделът смята в своята кошница", mv is not None and mv["p_home"] > 0.5)
    check("волейбол: същите два кода при жените дават ОБРАТЕН отговор",
          mw is not None and mw["p_home"] < 0.5)
    check("волейбол: юношите не наследяват силата на мъжете",
          abs((model_volleyball(vcopy(vb="m-you"), now) or {}).get("p_home", 0.0) - 0.5) < 0.01)
    check("волейбол: несвързани отбори не се сравняват",
          model_volleyball(vcopy(away_id="AAA", id_a=("alpha", "")), now) is None)
    check("волейбол: друг отбор под същия код не получава прогноза",
          model_volleyball(vcopy(home_id="PAD", id_h=("soneparpadova", "")), now) is None)
    check("волейбол: без кошница няма прогноза", model_volleyball(vcopy(vb=""), now) is None)
    check("волейбол: мъжкият и женският мач не са един ключ",
          match_key({"bucket": "volleyball", "home": "България", "away": "Италия",
                     "extra": {"vb": "m-sen"}}, now)
          != match_key({"bucket": "volleyball", "home": "България", "away": "Италия",
                        "extra": {"vb": "w-sen"}}, now))
    vol_fit([])
    _vol_fit_done[0] = False

    # --- проверки за смисъл и звезди
    check("сетовете се проверяват за смисъл", not sane_record("volleyball", 25, 20))
    check("точките не минават за сетове", not sane_record("basketball", 3, 1))
    check("хокеят приема 4:3", sane_record("hockey", 4, 3))
    check("малка извадка = една звезда", grade("football", 6, 0.9) == 1)
    check("ММА не стига 3 звезди", grade("mma", 90, 0.9) == 2)
    check("тенисът на маса не стига 3 звезди", grade("tabletennis", 90, 0.9) == 2)
    check("голяма извадка + категорично = 3 звезди", grade("football", 120, 0.6) == 3)
    check("звездите никога не са под 1", grade("football", 0, 0.0) == 1)

    # --- разбор на чужди полета
    check("резултат-речник (история)", espn_num({"value": 2.0, "displayValue": "2"}) == 2)
    check("резултат-низ (табло)", espn_num("3") == 3)
    check("празен резултат е None", espn_num("") is None)
    check("рекорд 13-2-0", parse_record("13-2-0") == (13, 2, 0))
    check("рекорд без черта", parse_record("") == (0, 0, 0))
    check("непобеден е по-силен", mma_prior(15, 0) > mma_prior(8, 7))
    # --- пазачът на часа: започнал мач не получава прогноза
    noon = datetime(2026, 7, 28, 12, 0, tzinfo=SOFIA)
    check("мач след два часа минава",
          not started({"when": noon + timedelta(hours=2)}, noon))
    check("мач отпреди час е отрязан",
          started({"when": noon - timedelta(hours=1)}, noon))
    check("мач, който тръгва в момента, е отрязан",
          started({"when": noon + timedelta(minutes=1)}, noon))
    check("мач без час минава напред (не гадаем)", not started({"when": None}, noon))
    check("часът-низ вечерта минава", not started({"when": None, "time": "21:30"}, noon))
    check("часът-низ сутринта е отрязан", started({"when": None, "time": "09:15"}, noon))
    check("22:00 гледано в 23:00 е отрязано",
          started({"when": None, "time": "22:00"},
                  datetime(2026, 7, 28, 23, 0, tzinfo=SOFIA)))
    check("след полунощ, гледано вечерта, е утрешно",
          not started({"when": None, "time": "01:30"},
                      datetime(2026, 7, 28, 20, 0, tzinfo=SOFIA)))
    check("боклук вместо час не чупи пазача",
          not started({"when": None, "time": "не-час"}, noon))
    check("мач след пет дни изчаква реда си",
          too_far({"when": noon + timedelta(days=5)}, noon))
    check("мач довечера не е далече", not too_far({"when": noon + timedelta(hours=8)}, noon))
    check("мач без час не се смята за далечен", not too_far({"when": None}, noon))
    check("наивна дата се чете като UTC", fx_start({"when": datetime(2026, 7, 28, 10, 0)},
                                                   noon).tzinfo is not None)

    check("часът е по българско време (лято = UTC+3)",
          when_label(datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc), noon) == "15:00")
    check("часът е по българско време (зима = UTC+2)",
          when_label(datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
                     datetime(2026, 1, 28, 14, 0, tzinfo=SOFIA)) == "14:00")

    check("ISO без секунди", parse_iso("2026-05-24T15:00Z") is not None)
    check("ISO без часова зона", parse_iso("2026-06-10T13:00:00") is not None)
    check("боклук в датата е None", parse_iso("не-дата") is None)
    check("ключът чисти пунктуацията", norm_key("Ман. Сити!") == "мансити")

    # --- тефтерът
    old_state = STATE_FILE
    STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest_state.json")
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write("{това не е JSON")
        st = load_state()
        check("счупен тефтер не сваля бота", st == _empty_state())
        fx = {"bucket": "football", "home": "Арсенал", "away": "Челси"}
        k = match_key(fx, now)
        check("непусната среща не е в тефтера", not already_posted(st, k))
        mark_posted(st, k, now)
        check("пусната среща се помни", already_posted(st, k))
        check("тефтерът се записва", save_state(st, now))
        check("тефтерът се чете обратно", already_posted(load_state(), k))
        st2 = load_state()
        st2["posted"]["2020-01-01|x|a|b"] = "2020-01-01 10:00"
        save_state(st2, now)
        check("старите записи се чистят", "2020-01-01|x|a|b" not in load_state()["posted"])
        check("ключът е еднакъв при второ смятане", match_key(fx, now) == k)
        # Ключът виси на ДЕНЯ НА МАЧА: гала след три дни е една и съща среща,
        # погледната днес и погледната утре — иначе излиза по веднъж на ден.
        far = {"bucket": "mma", "home": "Джонс", "away": "Аспинол",
               "when": now + timedelta(days=3)}
        check("бъдещ мач има един ключ през дните",
              match_key(far, now) == match_key(far, now + timedelta(days=1)))
        check("ключът носи датата на мача",
              match_key(far, now).startswith((now + timedelta(days=3)).strftime("%Y-%m-%d")))
        # --- дневният таван брои прогнози, не служебни съобщения
        st3 = _empty_state()
        mark_posted(st3, now.strftime("%Y-%m-%d") + "|header", now)
        mark_posted(st3, now.strftime("%Y-%m-%d") + "|footer", now)
        check("заглавие и подпис не ядат от тавана", cards_today(st3, now) == 0)
        check("но денят вече е започнал", posted_today(st3, now))
        mark_posted(st3, "x|football|алфа|бета", now)
        check("прогнозата се брои", cards_today(st3, now) == 1)
        check("вчерашните не се броят днес",
              cards_today(st3, now + timedelta(days=1)) == 0)
        check("два различни дни са два ключа",
              match_key(far, now) != match_key({"bucket": "mma", "home": "Джонс",
                                                "away": "Аспинол", "when": now}, now))
        # Двойката без датата пази от близнаци: два мача на един и същи
        # съперник (бейзболна серия) имат РАЗЛИЧНИ ключове, но ЕДНА двойка.
        g1 = {"bucket": "baseball", "home": "Редс", "away": "Гардиънс",
              "when": now + timedelta(hours=2)}
        g2 = {"bucket": "baseball", "home": "Редс", "away": "Гардиънс",
              "when": now + timedelta(hours=26)}
        k1, k2 = match_key(g1, now), match_key(g2, now)
        check("два мача с един съперник имат два ключа", k1 != k2)
        check("но една и съща двойка", k1.split("|", 1)[1] == k2.split("|", 1)[1])
    finally:
        try:
            os.remove(STATE_FILE)
        except OSError:
            pass
        STATE_FILE = old_state

    # --- пазачите на изхода
    check("стая 4 е забранена", post_predict("тест", "4") is False)
    check("стая 26 е забранена", post_predict("тест", "26") is False)
    check("стая 5 не е наша", post_predict("тест", "5") is False)
    # 🥊 Стая 328 „Бойни спортове" е за списъка с боеве (matches_bot.py).
    # Прогнозите — включително за ММА — остават в стая 27.
    check("стая 328 не е изходът на Предсказателя", post_predict("тест", "328") is False)
    check("стая 328 НЕ е в забранените", "328" not in FORBIDDEN_THREADS)
    check("стая 328 НЕ е в разрешените", "328" not in ALLOWED_THREADS)
    check("ММА прогнозите пак ходят в стаята на Предсказателя",
          "mma" in SPORTS and ALLOWED_THREADS == {PREDICT_THREAD})
    check("хазартна дума не излиза", post_predict("залагай сега", PREDICT_THREAD) is False)
    check("име на букмейкър не излиза", post_predict("bet365 дава 2.10", PREDICT_THREAD) is False)
    check("коефициент не излиза", post_predict("коефициент 1.85", PREDICT_THREAD) is False)
    check("и съкратеното коеф. не излиза", post_predict("коеф. 1.85", PREDICT_THREAD) is False)
    check("чист текст минава пазача", banned_word("Арсенал 68%, извадка 114 мача") is None)

    # --- фиш-езикът: 1 / Х / 2 и Над/Под направо от головата матрица
    check("фиш: домакинът е 1",
          pick_1x2(0.50, 0.28, 0.22, "Арсенал", "Челси") == ("1 · победа Арсенал", 0.50))
    check("фиш: гостът е 2",
          pick_1x2(0.22, 0.28, 0.50, "Арсенал", "Челси") == ("2 · победа Челси", 0.50))
    check("фиш: равенството е Х",
          pick_1x2(0.30, 0.40, 0.30, "Арсенал", "Челси") == ("Х · равен", 0.40))
    check("фиш: отборен спорт без равен", pick_win(False, "Никс", "Хийт") == "2 · победа Хийт")
    check("фиш: индивидуалният спорт е само име", pick_name(True, "Синер", "Алкарас") == "1 · Синер")
    check("Над 2.5 при 61%", over_under_line(0.61) == "Над 2.5 гола: <b>61%</b>")
    check("Под 2.5 при 39% отгоре", over_under_line(0.39) == "Под 2.5 гола: <b>61%</b>")
    check("между праговете няма ред", over_under_line(0.50) == "" and over_under_line(0.56) == "")
    check("прагът 57% е включително", over_under_line(0.57) != "")
    mk_hi = matrix_markets(score_matrix(2.3, 1.7))    # голов мач: общо 4.0 очаквани гола
    mk_lo = matrix_markets(score_matrix(0.9, 0.7))    # сух мач: общо 1.6 очаквани гола
    check("силната матрица дава ред Над",
          mk_hi["p_over"] >= 0.57 and over_under_line(mk_hi["p_over"]).startswith("Над 2.5 гола"))
    check("ниската матрица дава ред Под",
          over_under_line(mk_lo["p_over"]).startswith("Под 2.5 гола"))

    # --- картите: кратки, чисти, всяка с ясен фиш-избор
    demo = {"fx": {"bucket": "basketball", "emoji": "🏀", "home": "Ню Йорк Никс",
                   "away": "Маями Хийт", "league": "НБА", "when": None, "time": "21:30"},
            "bucket": "basketball", "pick": "1 · победа Ню Йорк Никс", "p": 0.68,
            "second": "Очакван резултат: ~112:105",
            "why": ["Никс: 116.3 : 110.1 точки за мач (82 мача)",
                    "Хийт: 109.8 : 112.4 точки за мач (82 мача)"],
            "sample": samp(82, 82), "n_eff": 164.0, "strength": 0.36, "stars": 2}
    txt = card(demo, now)
    check("картата е под 700 знака", len(txt) < 700)
    check("картата носи фиш-прогнозата",
          "ПРОГНОЗА: 1 · победа Ню Йорк Никс" in txt and "68%" in txt)
    check("баскетболът носи очакван резултат", "Очакван резултат: ~112:105" in txt)
    check("картата носи звезди и извадка", "⭐⭐" in txt and "извадка 82+82" in txt)
    check("картата има най-много две обяснения", txt.count(NL + "• ") == 2)

    demo_f = {"fx": {"bucket": "football", "emoji": "⚽", "home": "Арсенал",
                     "away": "Челси", "league": "Висша лига", "when": None, "time": "19:30"},
              "bucket": "football",
              "pick": pick_1x2(0.52, 0.26, 0.22, "Арсенал", "Челси")[0], "p": 0.52,
              "second": over_under_line(mk_hi["p_over"]),
              "why": ["Арсенал: 2.10 вкарани и 0.95 допуснати гола за мач (76 мача)",
                      "Челси: 1.45 вкарани и 1.30 допуснати гола за мач (74 мача)"],
              "sample": samp(76, 74), "n_eff": 120.0, "strength": 0.28, "stars": 3}
    txt_f = card(demo_f, now)
    check("футболната карта носи 1/Х/2", "ПРОГНОЗА: 1 · победа Арсенал" in txt_f)
    check("силната матрица слага ред Над/Под в картата", "Над 2.5 гола" in txt_f)

    demo_v = {"fx": {"bucket": "volleyball", "emoji": "🏐", "home": "Полша",
                     "away": "Италия", "league": "Лига на нациите", "when": None, "time": "18:00"},
              "bucket": "volleyball", "pick": "1 · победа Полша (3:1)", "p": 0.63,
              "second": "",
              "why": ["Полша печели 52.4% от разиграванията срещу този съперник"],
              "sample": samp(40, 40), "n_eff": 40.0, "strength": 0.26, "stars": 2}
    demo_h = {"fx": {"bucket": "hockey", "emoji": "🏒", "home": "Бостън",
                     "away": "Едмънтън", "league": "НХЛ", "when": None, "time": "02:00"},
              "bucket": "hockey", "pick": "2 · победа Едмънтън (в мача)", "p": 0.58,
              "second": "Очаквани голове 2.8 : 3.2 · над 5.5: 48%",
              "why": ["Бостън у дома: 2.90 вкарани и 3.05 допуснати гола за мач"],
              "sample": samp(82, 82), "n_eff": 164.0, "strength": 0.16, "stars": 2}
    demo_t = {"fx": {"bucket": "tabletennis", "emoji": "🏓", "home": "Хуго Калдерано",
                     "away": "Дан Цю", "league": "WTT", "when": None, "time": "12:40"},
              "bucket": "tabletennis", "pick": "1 · Хуго Калдерано", "p": 0.64,
              "second": "Най-вероятен резултат: <b>3:1</b>",
              "why": ["Хуго Калдерано: 44-12 за 18 месеца"],
              "sample": samp(56, 41), "n_eff": 48.0, "strength": 0.28, "stars": 2}
    demo_x = {"fx": {"bucket": "football", "emoji": "⚽", "home": "Хетафе",
                     "away": "Осасуна", "league": "Ла Лига", "when": None, "time": "22:00"},
              "bucket": "football", "pick": pick_1x2(0.31, 0.38, 0.31, "Хетафе", "Осасуна")[0],
              "p": 0.38, "second": over_under_line(mk_lo["p_over"]),
              "why": ["Хетафе: 0.90 вкарани и 0.85 допуснати гола за мач (70 мача)"],
              "sample": samp(70, 72), "n_eff": 110.0, "strength": 0.10, "stars": 1}
    check("равенството излиза като Х · равен", "ПРОГНОЗА: Х · равен" in card(demo_x, now))
    check("ниската матрица слага ред Под", "Под 2.5 гола" in card(demo_x, now))

    # Новите забранени думи: без поучения, без хазартен речник — на ВСЯКА карта.
    preachy = ("отговорно", "решението е твое", "банка", "единица", "коеф",
               "18+", "гаранция", "не е съвет")
    for dm in (demo, demo_f, demo_v, demo_h, demo_t, demo_x):
        t = card(dm, now)
        tag = dm["fx"]["bucket"] + " " + str(dm["fx"]["home"])
        check("карта " + tag + ": има ред ПРОГНОЗА", "ПРОГНОЗА: " in t)
        after = t.split("ПРОГНОЗА: ", 1)[1][:1] if "ПРОГНОЗА: " in t else ""
        check("карта " + tag + ": изборът е 1, 2 или Х", after in ("1", "2", "Х"))
        check("карта " + tag + ": чиста от забранени думи",
              banned_word(t) is None and not any(w in t.lower() for w in preachy))
        check("карта " + tag + ": под 900 знака", len(t) < 900)

    check("заглавната карта е кратка", len(header_card(now, 3, 14)) < 200)
    for service in (header_card(now, 3, 14), footer_card(14, 3, 2, 8),
                    nothing_card(now, 9, 5, 4)):
        check("служебният текст е чист: " + service[:24],
              banned_word(service) is None and not any(w in service.lower() for w in preachy))

    # --- подбор
    def mk(b, stars, s):
        return {"bucket": b, "stars": stars, "strength": s, "fx": {}, "pick": "x", "p": 0.6}
    got = choose([mk("football", 1, 0.2), mk("mma", 2, 0.5), mk("tennis", 3, 0.4)], 2)
    check("подборът взима най-уверените", [a["bucket"] for a in got] == ["tennis", "mma"])
    many = [mk("mma", 2, 0.5) for _ in range(9)]
    check("подборът не надхвърля тавана", len(choose(many, 4)) == 4)
    check("подборът дава разнообразие", [a["bucket"] for a in choose(
        [mk("mma", 2, 0.5), mk("mma", 2, 0.5), mk("mma", 2, 0.5), mk("tennis", 2, 0.4)],
        3)].count("mma") == 2)
    # Този тест хвана два истински бъга: волейболът и хокеят падаха мълчаливо,
    # защото общата проверка за история гледаше празен списък. Спорт без
    # history_for() ЗАДЪЛЖИТЕЛНО стои с праг 0, иначе изчезва от стаята.
    check("спорт без история има праг 0",
          all(MIN_PER_SIDE.get(b, 0) == 0 for b in SPORT_ORDER if b not in HISTORY_SPORTS))
    check("спорт с история има праг над 0",
          all(MIN_PER_SIDE.get(b, 0) > 0 for b in HISTORY_SPORTS))
    check("всеки спорт е описан в прага", all(b in MIN_PER_SIDE for b in SPORT_ORDER))
    check("забранените стаи са точно две", FORBIDDEN_THREADS == {"4", "26"})
    check("разрешената стая е една", ALLOWED_THREADS == {PREDICT_THREAD})
    check("всички спортове имат емоджи", all(SPORTS[b].get("emoji") for b in SPORT_ORDER))
    check("редът покрива всички спортове", set(SPORT_ORDER) == set(SPORTS.keys()))

    print("САМОПРОВЕРКА: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b_ in bad:
        print("   🔴 " + b_)
    return not bad


def main():
    if len(sys.argv) > 1 and sys.argv[1].strip().lower() in ("selftest", "test", "--selftest"):
        sys.exit(0 if selftest() else 1)
    if not DRY_RUN and (not BOT_TOKEN or not CHAT_ID):
        print("Missing BOT_TOKEN/CHAT_ID (или пусни с PREDICT_DRY_RUN=1)")
        sys.exit(1)
    if DRY_RUN:
        print("СУХО ПУСКАНЕ — картите се печатат, нищо не заминава за Telegram.")
    run()


if __name__ == "__main__":
    main()
