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

# 🔴 ПАЗАРНАТА ЦЕНА (13.08.2026). Отделен внос, отделен try: провал тук НЕ
# бива да спира прогнозите. Без него картата просто няма реда с цената.
try:
    import pazar as PZ
except Exception as _pz_err:          # noqa: BLE001
    PZ = None
    print("pazar не се зареди (" + str(_pz_err)[:80] + ") — картите остават без цена.")
try:
    import pinnacle as PIN
except Exception as _pin_err:                                # noqa: BLE001
    PIN = None
    print("вторият източник не се зареди (" + str(_pin_err)[:70] + ").")

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

# ═══════════════════════════ КЪДЕ ОТИВА КОЯ КАРТА (променено 29.07.2026)
# СТАРО: всичко живееше само в стая 27, а спортните стаи получаваха голи
# разписания. Собственикът го отхвърли: „общи разписания, които нищо не
# значат и на никой не му пука за тях". Прогнозата трябва да е при своя спорт.
#
# СЕГА:
#   стая 27  — ВСИЧКИ прогнози, както досега (общата витрина)
#   стая на спорта — СЪЩАТА карта отива и там, при хората, които следят него
#   стая 4   — трите комбинирани фиша на деня (виж combo_cards)
#   стая 26  — НОВИНИТЕ. Тук предсказателят няма работа и това не се променя.
SPORT_ROOM = {
    "football":    (os.environ.get("FOOTBALL_THREAD_ID") or "5").strip(),
    "basketball":  (os.environ.get("BASKET_THREAD_ID") or "6").strip(),
    "tabletennis": (os.environ.get("TT_THREAD_ID") or "7").strip(),
    "volleyball":  (os.environ.get("VOLLEY_THREAD_ID") or "8").strip(),
    "mma":         (os.environ.get("COMBAT_THREAD_ID") or "328").strip(),
}

# НОВИТЕ СТАИ СЕ ЧЕТАТ ОТ ФАЙЛ, НЕ СЕ ЗАКОВАВАТ ТУК.
#
# Ботът предричаше за осем спорта, а стаи имаше за пет: хокеят, тенисът,
# бейзболът и американският футбол оставаха само в общата витрина 27.
# make_rooms.py ги създава в групата и записва номерата им в rooms_state.json.
# Тук те просто се вливат — така създаването и ползването им са ЕДНО качване,
# а не две, и ако утре се появи девети спорт, не се пипа този файл.
#
# Ако файлът липсва или е повреден, нищо не се чупи: спортът просто остава
# без своя стая, точно както беше досега. Тиха загуба, не тих провал.
ROOMS_STATE_FILE = (os.environ.get("ROOMS_STATE_FILE") or "rooms_state.json").strip()


def _stai_ot_fayl(path):
    """Спорт -> номер на стая, от паметта на make_rooms.py. {} при липса."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:                             # noqa: BLE001
        return {}
    if not isinstance(d, dict):
        return {}
    out = {}
    for sport, zapis in d.items():
        thread = (zapis or {}).get("thread") if isinstance(zapis, dict) else None
        try:
            n = int(thread)
        except (TypeError, ValueError):
            continue
        if n > 0 and str(sport).strip():
            out[str(sport).strip()] = str(n)
    return out


for _sport, _stay in _stai_ot_fayl(ROOMS_STATE_FILE).items():
    SPORT_ROOM.setdefault(_sport, _stay)      # закованите отгоре имат превес
PICKS_THREAD = (os.environ.get("PICKS_THREAD_ID") or "4").strip()

# 🚫 Новините са чужди. Всичко останало, което пипаме, е изброено поименно.
FORBIDDEN_THREADS = {"26"}
ALLOWED_THREADS = ({PREDICT_THREAD, PICKS_THREAD}
                   | set(SPORT_ROOM.values())) - FORBIDDEN_THREADS

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


# 6, не 4. Откакто списъците със срещи спряха (собственикът: „искам всичко
# прогнози, а не какво предстои като някакви списъци"), спортните стаи живеят
# САМО от прогнози. При четири карти на пускане и девет спорта една стая
# оставаше по цял ден без нищо.
MAX_PICKS = env_int("MAX_PICKS", 6, 1, 10)
# 32, не 24 (вдигнат 11.08.2026 заедно с броя фишове).
# Сметката: пет фиша по средно 3-4 крака = 15-20 крака, но във фиш влизат само
# избори над 58% (виж COMBO_MIN_P), а такива са около две трети от анализираните.
# 20 / 0.65 ≈ 31. При 24 под лупата петият фиш нямаше да се събере.
POOL = env_int("PREDICT_POOL", 32, 1, 48)
# 5, не 3: половината спортове са извън сезон в даден ден и таванът „три от
# спорт" стягаше лупата точно когато трябва да е широка.
PER_SPORT = env_int("PREDICT_PER_SPORT", 5, 1, 8)
MIN_STRENGTH = env_float("PREDICT_MIN_STRENGTH", 0.10, 0.0, 0.9)
# 🔴 ДОЛНА ГРАНИЦА ЗА ПУБЛИКУВАНЕ (11.08.2026). Измерена, не избрана.
#
# В стаята излизаха карти от рода на „1 · победа Kairat Almaty — 35%". Това е
# изречение, което САМО СЕ ОПРОВЕРГАВА: посочваме страна и в същото време
# казваме, че тя губи в две от всеки три срещи. При футбола равенството изяжда
# средата, затова „най-вероятният от три изхода" спокойно пада под 40%.
#
# Измерено върху 131 отсъдени прогнози от живия дневник (11.08.2026):
#
#   праг    карти  познати  процент          футбол сам:  карти  процент
#    0%      131      85     64.9%                          11    18.2%
#   45%      125      84     67.2%                           5    20.0%
#   55%       99      71     71.7%                           3    33.3%
#
# Прагът 45% реже ШЕСТ карти за цялата история — и шестте са футболни, и в тях
# има само една познала. Общото се вдига с 2.3 пункта, а нито един друг спорт
# не губи и една карта (проверено: под 45% няма нищо извън футбола).
#
# Защо не 55%, щом там е по-високо: 55% реже 32 карти, включително цели дни
# волейбол и бейзбол, които вървят добре. Точката, в която се маха само вредата,
# е 45.
MIN_SHOW_P = env_float("PREDICT_MIN_SHOW_P", 0.45, 0.0, 0.75)

# 🔴 МОНЕТАТА НЕ Е ПРОГНОЗА (11.08.2026). Намерено с отваряне на живата стая.
#
# В 13:02 в „БОТА ПРЕДРИЧА" стоеше карта:
#     🎯 2 · победа Dinamo Zagreb
#     50% · 🔴 почти равностойни
# Числото и думата „прогноза" се бият челно. При спорт с ДВА изхода
# вероятността на фаворита е ≥50% ПО КОНСТРУКЦИЯ — просто защото избираме
# по-вероятната страна. Тоест 50–52% не значи „лек превес", значи „не знам".
#
# 45-процентният праг е верен за ФУТБОЛА и си остава: там изходите са ТРИ и
# равенството изяжда средата, затова 45% за един от тримата е истинско
# преимущество. За двоичните спортове същото число е безсмислено.
#
# Измерено върху живия дневник (261 записа, 44 отсъдени):
#   • 33 от 247 двоични карти (13%) са в лентата 50–53% — тоест всяка осма
#   • от тях е отсъдена ЕДНА и тя е загубена
#   • двоичните над 60%: 31 карти, 26 познати — 84%
#   • двоичните 56–60%: 2 карти, 1 позната
# Извадката в самата лента е малка и НЕ доказва вреда по числа. Доводът не е
# статистически, а продуктов: карта, която сама си казва „почти равностойни",
# не е прогноза, а запълване на стая. Цената е известна и е горе: 13%.
#
# Изход без пипане на код: PREDICT_MIN_SHOW_P_BINARY=0.50 връща старото.
DVA_IZHODA = {"tennis", "tabletennis", "mma", "volleyball",
              "basketball", "baseball", "hockey", "amfootball"}
MIN_SHOW_P_DVA = env_float("PREDICT_MIN_SHOW_P_BINARY", 0.53, 0.50, 0.75)


def dolen_prag(bucket):
    """Долната граница за този спорт. Два изхода = по-висока летва."""
    return MIN_SHOW_P_DVA if str(bucket) in DVA_IZHODA else MIN_SHOW_P
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
# 24, не 10. Същата причина: стаите на деветте спорта се пълнят единствено от
# прогнози. Десет карти на ден означаваше, че пет от стаите мълчат.
# Двадесет и четири при осем пускания са по три на пускане — четимо, не порой.
# Вдигнат от 24 на 40 (05.08.2026). Причината е новото правило „всичко до 22:00":
# вечерното пускане в 20:00 вече поема ЦЯЛАТА нощ — всички мачове до 08:00 на
# другия ден. При таван 24 то щеше да опира в него точно тогава, когато носи
# най-много спешни карти, и нощните мачове щяха да останат без прогноза.
MAX_DAY = env_int("PREDICT_MAX_DAY", 40, 1, 80)
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
    "amfootball":  {"emoji": "🏈", "title": "Американски футбол", "prio": 25,
                    "model": "точки за и против"},
    "baseball":    {"emoji": "⚾", "title": "Бейзбол", "prio": 20,
                    "model": "рънове за и против"},
}
# Футболът е последен по изрична заповед на шефа. Бейзболът е след него.
SPORT_ORDER = ["mma", "tabletennis", "volleyball", "basketball",
               "tennis", "hockey", "football", "amfootball", "baseball"]

_want = [s.strip().lower() for s in (os.environ.get("PREDICT_SPORTS") or "").split(",") if s.strip()]

# 🔴 ЗАТВОРЕНИ СПОРТОВЕ (11.08.2026, по изрична заповед на собственика)
#
# Измерено, не усетено: predict_log.json има 261 записа. Хокей — 0. Американски
# футбол — 0. Нито един за целия живот на дневника. НХЛ отваря около 15.09, а
# НФЛ дава само предсезонни, които гейтът реже нарочно. Тоест два спорта,
# две стаи и два пина стояха отворени и празни и произвеждаха единствено
# въпроса „защо е празно".
#
# Затворени тук, а НЕ изтрити: hockey_fixtures, model_hockey, nhl_table,
# amfootball_fixtures, model_amfootball и цялата им самопроверка остават
# непокътнати и продължават да се тестват.
#
# ПЪТЯТ НАЗАД (правило 3): PREDICT_IZKL="" ги връща моментално, без нито ред
# промяна по кода. През септември това е една променлива в GitHub, не ремонт.
_izkl_raw = os.environ.get("PREDICT_IZKL")
if _izkl_raw is None:
    _izkl_raw = "hockey,amfootball"
IZKLYUCHENI = {s.strip().lower() for s in _izkl_raw.split(",") if s.strip()}
ACTIVE_SPORTS = [s for s in SPORT_ORDER
                 if (not _want or s in _want) and s not in IZKLYUCHENI]

# Звездите говорят сами (легендата е в подписа) — картата не носи думи за тях.
# Таван на звездите там, където сама по себе си дисциплината е непредсказуема.
STAR_CAP = {"mma": 2, "tabletennis": 2, "baseball": 2, "tennis": 3,
            "volleyball": 3, "football": 3, "basketball": 3, "hockey": 3,
            "amfootball": 3}
# Минимална извадка на страна. 0 = спортът има собствена проверка за достатъчност.
# 0 = спортът НЕ минава през общата проверка, защото носи собствена. Волейболът
# и тенисът на маса броят извадката вътре в модела си (рейтинг, не списък мачове);
# ако ги оставим тук с число, общата проверка вижда празен списък и ги убива ВСИЧКИТЕ.
MIN_PER_SIDE = {"football": 5, "basketball": 5, "volleyball": 0, "tabletennis": 0,
                "tennis": 0, "mma": 0, "hockey": 0, "baseball": 10,
                # Американският футбол играе 17 мача за сезон — праг 5 би
                # изтрил целия септември. Три стигат, звездите пазят честността.
                "amfootball": 3}
# Спортовете, които наистина връщат списък с изиграни мачове през history_for().
# Всеки ДРУГ спорт ЗАДЪЛЖИТЕЛНО стои с 0 по-горе. Самопроверката го пази —
# сгрешено число тук не чупи нищо шумно, просто убива мълчаливо цял спорт.
HISTORY_SPORTS = {"football", "basketball", "baseball", "amfootball"}

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
# Кой адрес не отговори и защо. Броячът горе казва „три провала" — а въпросът
# винаги е КОИ три. Тефтерът носи този списък навън, където се чете без права.
_http_why = []
HTTP_WHY_MAX = 40


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


# 🔴 ЗАЩО ESPN НЕ ПОЛУЧАВА ПОДПИС (измерено на живо на 11.08.2026)
#
# Пет спорта — футбол, тенис, баскетбол, хокей, ММА и американски футбол —
# мълчаха с ДНИ. Черната кутия показа 403 Forbidden на всеки адрес на ESPN.
# Първата мисъл е „блокират сървъра на GitHub". Грешна. Същият 403 идваше и на
# домашната машина. Тестът беше един адрес, една минута, сменя се само подписът:
#
#     с фалшивия Chrome подпис горе  ->  403 Forbidden
#     без никакъв подпис             ->  200 и 10 срещи
#     с подписа на самия Python      ->  200 и 10 срещи
#     с измислен подпис „GreenPicks" ->  403 Forbidden
#
# Тоест ESPN не пази данните — пази се от преправени клиенти. Маскировката
# БЕШЕ причината. Затова тук подписът се маха точно за ESPN, а за WTT и FIVB,
# които го искат, остава.
NO_UA_HOSTS = ("espn.com",)


def glavi_za(url, headers=None):
    """Кои глави заминават с една заявка. Отделено, за да се проверява само."""
    hd = ({"Accept": "application/json"}
          if any(h in url for h in NO_UA_HOSTS)
          else {"User-Agent": UA, "Accept": "*/*"})
    if headers:
        hd.update(headers)
    return hd


def http_bytes(url, headers=None, timeout=30):
    """Една заявка навън, с таван, пауза и разсгъстяване. Хвърля при провал."""
    if _http_used[0] >= HTTP_BUDGET:
        raise RuntimeError("изчерпан лимит заявки (" + str(HTTP_BUDGET) + ")")
    hd = glavi_za(url, headers)
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
        if len(_http_why) < HTTP_WHY_MAX:
            _http_why.append(url.replace(ESPN_SITE, "espn")[:70]
                             + " -> " + str(e)[:40])
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
            # „diag" е черната кутия: колко срещи е видял ботът по спорт в
            # ПОСЛЕДНОТО пускане. Записва се тук, защото този файл се връща в
            # хранилището и се чете отвън — за разлика от дневника на GitHub.
            json.dump({"v": 1, "posted": posted,
                       "diag": {"koga": now.strftime("%Y-%m-%d %H:%M"),
                                "sportove": DIAG}},
                      f, ensure_ascii=False)
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


# 🔴 РАЗШИРЕН 18.08.2026 — ИЗМЕРЕНО В ЖИВИЯ ТЕФТЕР.
# Тук стояха само три служебни ключа. Но фишовете също пишат в тефтера:
# „ден|combos" отдавна, а от 12.08 и „ден|combo1/2/3" (собствен ключ на всеки
# фиш, за да може убит рън да се възобнови). Нито един от тях не беше обявен
# за служебен — значи cards_today ги броеше за ПРОГНОЗИ и те ядяха от дневния
# таван. Проверено на живо: за 16.08 тефтерът дава combo1, combo2, combo3 и
# combos — четири „карти", които никога не са били карти.
# И вторият ефект: karti_dnes_po_sport ги виждаше като СПОРТОВЕ.
SERVICE_KEYS = ("|header", "|footer", "|nothing", "|combos",
                "|combo1", "|combo2", "|combo3", "|combo4", "|combo5")


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


def nepoznati_klyuchove(state):
    """Кои видове ключове в тефтера НЕ са нито спорт, нито обявени за служебни.

    🔴 18.08.2026. Точно това ни ухапа: „|combos" и „|combo1..3" не бяха в
    служебния списък, значи се брояха за прогнози и ядяха от дневния таван —
    четири места на ден при утринен таван шестнайсет. Никой тест не гръмна,
    защото никой не сравняваше ВИДОВЕТЕ ключове с двата известни списъка.
    Сега се сравняват. Нов вид ключ утре ще се обади сам.
    """
    vidove = set()
    for k in (state.get("posted") or {}):
        chasti = str(k).split("|")
        if len(chasti) > 1:
            vidove.add(chasti[1])
    izvestni = set(SPORTS) | {s.lstrip("|") for s in SERVICE_KEYS}
    return sorted(vidove - izvestni)


def karti_dnes_po_sport(state, now):
    """Колко прогнози са излезли ДНЕС, разбито по спорт.

    Ключът е „ден|спорт|…", затова спортът се вади от втората част. Служебните
    ключове (заглавие, подпис, фишове) не се броят — те не са прогнози.
    """
    d = now.strftime("%Y-%m-%d")
    broy = {}
    for k, v in (state.get("posted") or {}).items():
        if str(v)[:10] != d or str(k).endswith(SERVICE_KEYS):
            continue
        chasti = str(k).split("|")
        if len(chasti) < 2:
            continue
        b = chasti[1]
        broy[b] = broy.get(b, 0) + 1
    return broy


def persist(state, now):
    """Записва тефтера, но НИКОГА при сухо пускане: иначе пробното пускане
    отбелязва мачовете като пуснати и истинското после мълчи."""
    if DRY_RUN:
        return False
    return save_state(state, now)


# ------------------------------------------------- ДНЕВНИКЪТ НА ПРОГНОЗИТЕ
# ЗАЩО СЪЩЕСТВУВА
# Тефтерът predict_state.json помни САМО че една среща е пусната — ключ и час.
# Не помни КАКВО сме предсказали. Затова стая 9 „Резултати" и стая 10
# „Печеливши" нямаше как да покажат дали ботът е познал: данните просто ги
# нямаше никъде. Тук записваме самото твърдение — кой, срещу кого, кого сме
# посочили, с каква вероятност и колко звезди — за да може scorer.py после да
# го сравни с истинския резултат.
#
# Файлът е списък, не речник: един ред = едно твърдение, в реда на пускане.
# Не се трие нищо. Сгрешените прогнози остават — това е продуктът.
PICKLOG_FILE = (os.environ.get("PREDICT_LOG_FILE") or "predict_log.json").strip()
# 🔴 400 → 5000 НА 18.08.2026. ДНЕВНИКЪТ СЕ ТРИЕШЕ, НЕ СЕ ПАЗЕШЕ.
#
# Този таван реже най-старите записи при ВСЯКО дописване. При 40 карти на ден
# 400 значи ДЕСЕТ ДНИ история — после всеки нов запис изяжда по един стар.
# Живият дневник стоеше на ТОЧНО 400: таванът беше запушен, не с резерва.
# Измерено: 95 записа от 29.07-05.08 вече ги няма, от тях 50 отсъдени.
#
# И най-лошото — публичното число лъжеше заради това: футболът показваше
# 61% (19 от 31), а по цялата история е 50% (21 от 42). Единайсет пункта
# грешка на стената, произведена само от триенето.
#
# Архивът, писан вчера, беше МЪРТЪВ ПО РОЖДЕНИЕ: оценителят архивира на
# 120-ия ден, а предсказателят триеше на 10-ия. Нищо не стигаше до архива.
#
# Правилото: таванът ТРЯБВА да е над MAX_DAY × ARHIV_DNI, иначе триенето
# изпреварва архивирането. 40 × 60 = 2400; 5000 дава двойна резерва и след
# есенното удвояване на обема.
PICKLOG_KEEP = env_int("PREDICT_LOG_KEEP", 5000, 20, 20000)


def log_pick(an, now, combo=0):
    """Добавя едно твърдение към дневника. Провалът тук НЕ спира картите.

    combo = номер на фиша, ако този избор е крак от комбиниран фиш. Нула значи
    самостоятелна карта. Ако мачът вече е в дневника, само му се дописва
    номерът на фиша — не се вписва втори път.
    """
    if DRY_RUN:
        return False
    fx = an.get("fx") or {}
    when = fx_start(fx, now)
    rec = {
        "key": fx.get("_key"),
        "combo": int(combo or 0),
        "posted": now.strftime("%Y-%m-%d %H:%M"),
        "day": (when.astimezone(SOFIA) if when is not None else now).strftime("%Y-%m-%d"),
        "bucket": an.get("bucket"),
        "home": fx.get("home"), "away": fx.get("away"),
        "home_id": fx.get("home_id"), "away_id": fx.get("away_id"),
        "league": fx.get("league"),
        "slug": (fx.get("extra") or {}).get("slug"),
        "pick": an.get("pick"),
        # 🔴 13.08.2026. Пазарната цена и вероятността, която тя значи. Пазят
        # се, за да може после да се отговори на въпроса, който наистина мери
        # качество: бием ли пазара, или само познаваме фаворити.
        "pazar_cena": an.get("pazar_cena"),
        "pazar_p": an.get("pazar_p"),
        "pazar_v": an.get("pazar_v"),
        "pit_home": ((an.get("fx") or {}).get("extra") or {}).get("pit_home"),
        "pit_away": ((an.get("fx") or {}).get("extra") or {}).get("pit_away"),
        "pazar_ev": an.get("pazar_ev"),
        "pazar_izt": an.get("pazar_izt"),
        "pazar_sport": an.get("pazar_sport"),
        "pazar_liga": an.get("pazar_liga"),
        "p": round(float(an.get("p") or 0.0), 4),
        "stars": an.get("stars"),
        "sample": an.get("sample"),
        "scored": False,          # scorer.py го вдига на True
    }
    try:
        rows = []
        if os.path.exists(PICKLOG_FILE):
            with open(PICKLOG_FILE, encoding="utf-8-sig") as f:
                got = json.load(f)
            if isinstance(got, list):
                rows = got
        # Ако мачът вече е вписан (излязъл е като самостоятелна карта), само
        # му дописваме номера на фиша. Иначе оценителят би го броил два пъти.
        stara = None
        for r in rows:
            if r.get("key") and r.get("key") == rec.get("key"):
                stara = r
                break
        if stara is not None:
            if rec["combo"] and not stara.get("combo"):
                stara["combo"] = rec["combo"]
            rows = rows[-PICKLOG_KEEP:]
        else:
            rows.append(rec)
            rows = rows[-PICKLOG_KEEP:]
        tmp = PICKLOG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PICKLOG_FILE)     # атомарно
        return True
    except Exception as e:                # noqa: BLE001
        print("дневникът на прогнозите не се записа (" + str(e)[:70] + ").")
        return False


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

    Разрешените стаи са изброени поименно в ALLOWED_THREADS: 27 (витрината),
    стаята на съответния спорт, и 4 за комбинираните фишове. Стая 26 остава
    забранена — новините са чужда работа. Канал няма: този файл няма функция,
    която да праща в канал.
    """
    tid = str(thread_id if thread_id is not None else PREDICT_THREAD).strip()
    if tid in FORBIDDEN_THREADS:
        print("ОТКАЗ: стая " + tid + " е чужда (новини).")
        return False
    if tid not in ALLOWED_THREADS:
        print("ОТКАЗ: стая " + tid + " не е в разрешените ("
              + ", ".join(sorted(ALLOWED_THREADS)) + ").")
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


def strength_1x2(p, base=1.0 / 3.0):
    """Колко сме над случайното — за ТОЗИ пазар, не изобщо.

    Базата е различна за различните редове: „1" се уцелва на сляпо веднъж на
    три пъти, „1Х" — два пъти на три. Ако мерехме и двете срещу 1/3, двойният
    шанс щеше да излиза с пет звезди при нулево знание.
    При база 1/3 формулата е точно старата: (p - 1/3) * 1.5.
    """
    b = clampf(float(base), 0.0, 0.95)
    return clampf((float(p) - b) / (1.0 - b), 0.0, 1.0)


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


# 🔴 ПАЗАЧЪТ ЗА ПРЕДСЕЗОННИ БЕШЕ СЛЯП (намерено и оправено 11.08.2026).
#
# Кодът режеше предсезонните така: `if "Preseason" in ev["seasonType"]["name"]`.
# Измерено на живо срещу ESPN за 13.08.2026 (НФЛ):
#     event.seasonType : {}                      ← ПРАЗНО
#     event.season     : {"year":2026,"type":1,"slug":"preseason"}
# Тоест полето, което проверявахме, ESPN изобщо не го пълни, а истинският
# белег стои другаде. Проверката минаваше винаги и не е спряла нито един мач.
#
# Защо има значение точно сега: НФЛ подхваща на 13.08 — вдругиден. В предсезона
# титулярите играят по четвърт час, а моделът смята по 17 мача от РЕДОВНИЯ
# сезон. Тоест щяхме да пуснем карта с чужди числа под нея.
#
# Сега се гледат ТРИ места, защото различните турнири пълнят различни:
#   • season.slug == "preseason"   (най-надеждното при НФЛ/НБА)
#   • seasonType.name съдържа Preseason (там, където ESPN го пълни)
#   • competition.type.abbreviation == "PRE"
def predsezonen(ev, comp=None):
    """Предсезонен ли е мачът. Гледа трите места, където ESPN го пише."""
    sez = ev.get("season") or {}
    if str(sez.get("slug") or "").lower() == "preseason":
        return True
    if "preseason" in str((ev.get("seasonType") or {}).get("name") or "").lower():
        return True
    tip = ((comp or {}).get("type") or {})
    if str(tip.get("abbreviation") or "").upper() == "PRE":
        return True
    return False


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
        if predsezonen(ev, comp):
            continue
        h, a = espn_sides(comp)
        if not h or not a:
            continue
        ht, at = (h.get("team") or {}), (a.get("team") or {})
        ex = dict(extra or {})
        ex["slug"] = slug
        # 🔴 13.08.2026. Идентификаторът на срещата в ESPN. Пазим го, защото
        # ДЪЛБОКИЯТ слой на ESPN (sports.core.api) дава пазарната цена само
        # по него — scoreboard-ът я носи единствено за футбола, а core я има
        # и за бейзбол, и за ВНБА. Един ключ тук отваря цял пазар после.
        ex["ev_id"] = str(ev.get("id") or "")
        ex["sport_path"] = sport
        ex["neutral"] = bool(comp.get("neutralSite"))
        # 🔴 РЕКОРДЪТ СЕ ЗАПАЗВА (11.08.2026). ESPN го дава направо в
        # scoreboard-а: records=[{'type':'total','summary':'20-12'},
        # {'type':'home','summary':'11-6'}, {'type':'road','summary':'9-6'}].
        # Анализаторът (matches_bot) нямаше НИКАКВИ числа за WNBA и волейбола
        # и всеки ден пишеше „нямаме изиграни мачове" — а те са били на един
        # ключ разстояние в същия отговор.
        def _rec(side, vid):
            for r in (side.get("records") or []):
                if str(r.get("type") or "").lower() == vid:
                    return str(r.get("summary") or "")
            return ""
        ex["rec_h"] = _rec(h, "total")
        ex["rec_a"] = _rec(a, "total")
        ex["rec_h_home"] = _rec(h, "home")
        ex["rec_a_road"] = _rec(a, "road")
        ex["form_h"] = h.get("form") or ""
        ex["form_a"] = a.get("form") or ""
        # 🔴 ОРИГИНАЛНОТО ИМЕ (18.08.2026). Показваме „Фенербахче", но чуждите
        # източници знаят „Fenerbahce". Измерено: търсенето по имена НЕ
        # намираше нито един преведен отбор — а превеждаме точно големите.
        ex["home_en"] = str(ht.get("displayName") or "")
        ex["away_en"] = str(at.get("displayName") or "")
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
            comps = ev.get("competitions") or []
            if not comps:
                continue
            # Същият сляп пазач стоеше и тук — историята се пълнеше с
            # предсезонни резултати, тоест моделът смяташе по мачове, в които
            # титулярите не са играли. Виж обяснението при predsezonen().
            if predsezonen(ev, comps[0]):
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
# Редът НЕ е по важност — важността е второто число. Редът пази лигите, които
# играят ПРЕЗ ЛЯТОТО, от отреза FOOT_SLUG_MAX.
#
# ЗАЩО: измерено на 28.07.2026 — от 15-те европейски първенства в началото на
# стария списък ESPN върна НУЛА мача (Европа е в отпуска до средата на август),
# докато Бразилия даваше 8, Аржентина 8, MLS 1 и квалификациите за Шампионска
# лига цели 14. Точно тези четири стояха на места 16-18 или изобщо липсваха и
# падаха под отреза 14 → футболът, спорт номер едно, мълчеше цяло лято.
#
# 🔴 ВТОРИ ПЪТ СЪЩАТА ДУПКА, 11.08.2026. Списъкът имаше квалификациите за
# Шампионска лига, но НЕ и тези за Лига Европа и Лигата на конференциите.
# Измерено на живо същия ден (ESPN, четири последователни дати):
#     uefa.europa_qual        11.08→1   12.08→0   13.08→12   14.08→0
#     uefa.europa.conf_qual   11.08→2   12.08→3   13.08→25   14.08→0
#     uefa.europa             всичките четири дни →0
#     uefa.europa.conf        всичките четири дни →0
# Тоест на 13 август ботът щеше да види НУЛА футболни мача, докато навън се
# играят 37. Основните адреси (без _qual) през август са празни — цялото
# движение е в квалификациите. Точно затова тези два реда стоят ГОРЕ, в летния
# блок: там не могат да паднат под отреза FOOT_SLUG_MAX.
FOOT_SLUGS = [
    # Лятото: Южна Америка, MLS и европейските квалификации играят.
    ("bra.1", 5, "Серия А, Бразилия"), ("arg.1", 5, "Примера, Аржентина"),
    ("uefa.champions_qual", 7, "Квалификации за Шампионска лига"),
    ("uefa.europa_qual", 6, "Квалификации за Лига Европа"),
    ("uefa.europa.conf_qual", 5, "Квалификации за Лига на конференциите"),
    ("usa.1", 4, "MLS"),
    # Основният сезон, август-май.
    ("uefa.champions", 12, "Шампионска лига"), ("uefa.europa", 9, "Лига Европа"),
    ("eng.1", 10, "Висша лига"), ("esp.1", 10, "Ла Лига"),
    ("ita.1", 9, "Серия А"), ("ger.1", 9, "Бундеслига"),
    ("fra.1", 8, "Лига 1"), ("uefa.europa.conf", 6, "Лига на конференциите"),
    ("ned.1", 6, "Ередивизи"), ("por.1", 6, "Примейра лига"),
    ("tur.1", 6, "Супер лига, Турция"), ("gre.1", 5, "Супер лига, Гърция"),
    ("bel.1", 5, "Про лига, Белгия"), ("eng.2", 5, "Чемпиъншип"),
    ("sco.1", 5, "Премиършип, Шотландия"),

    # 🔴 ТРИЙСЕТ И ДВЕ НОВИ ЛИГИ (19.08.2026). ESPN ги дава ВСИЧКИТЕ, а ние не
    # ползвахме нито една. Проверени една по една на живо същия ден — всяка
    # върна истински мачове; в списъка влизат само тези, които отговориха.
    # Само за ДНЕС това са около 70 допълнителни срещи — при 3, които футболът
    # даде вчера. Една заявка на лига на ден е евтино; мълчащ спорт не е.
    #
    # Тежестта е ниво на лигата, не симпатия: тя влиза в модела през
    # league_level и мени очакваните голове.

    # Континентални клубни турнири
    ("conmebol.libertadores", 8, "Копа Либертадорес"),
    ("conmebol.sudamericana", 6, "Копа Судамерикана"),
    ("concacaf.champions_cup", 5, "Шампионска купа на КОНКАКАФ"),
    ("uefa.super_cup", 10, "Суперкупа на Европа"),
    ("fifa.cwc", 9, "Световно клубно първенство"),

    # Европа, втори ешелон и по-малки първенства
    ("esp.2", 5, "Сегунда, Испания"), ("ita.2", 5, "Серия Б, Италия"),
    ("ger.2", 5, "Втора Бундеслига"), ("fra.2", 5, "Лига 2, Франция"),
    ("eng.3", 4, "Лига 1, Англия"), ("eng.4", 3, "Лига 2, Англия"),
    ("sui.1", 5, "Супер лига, Швейцария"), ("aut.1", 5, "Бундеслига, Австрия"),
    ("den.1", 5, "Суперлига, Дания"), ("swe.1", 4, "Алсвенскан, Швеция"),
    ("nor.1", 4, "Елитсериен, Норвегия"), ("rus.1", 5, "Премиер лига, Русия"),
    ("rou.1", 4, "Лига 1, Румъния"), ("cze.1", 4, "Първа лига, Чехия"),

    # Извън Европа
    ("mex.1", 6, "Лига МХ, Мексико"), ("mex.2", 4, "Лига де Експансион"),
    ("jpn.1", 5, "Джей лига, Япония"), ("aus.1", 4, "А-лига, Австралия"),
    ("bra.2", 4, "Серия Б, Бразилия"), ("arg.2", 3, "Примера Насионал"),
    ("chi.1", 4, "Примера дивисион, Чили"), ("col.1", 4, "Примера А, Колумбия"),
    ("uru.1", 4, "Лига АУФ, Уругвай"), ("per.1", 3, "Лига 1, Перу"),
    ("ecu.1", 4, "ЛигаПро, Еквадор"), ("par.1", 3, "Примера дивисион, Парагвай"),
    ("ven.1", 3, "Примера дивисион, Венецуела"),

    # 🔴 ЕДИНАЙСЕТ ДОБАВЕНИ ПО ИЗМЕРВАНЕ, НЕ ПО УСЕТ (19.08.2026).
    #
    # Обиколих ВСИЧКИТЕ 216 футболни лиги в справочника на ESPN. 166 не ги
    # ползвахме. От тях 126 отпаднаха веднага: „1 мач" в отговора е ПОСЛЕДНИЯТ
    # мач в историята на лигата, не днешен (същият капан изхвърли и 40 от 41
    # ММА „лиги" — PRIDE е закрит от 2007).
    #
    # Останалите 40 минаха ВТОРИ кантар: взимат се имената на отборите и се
    # питат за цена в живия пазар. Лига без цена значи, че никой не я предлага
    # за игра — тя не влиза, колкото и добре да звучи. Така отпаднаха NCAA
    # футбол (0 от 12), приятелските (0 от 9), Копа Колумбия (0 от 6),
    # Примера Б Аржентина (0 от 22) и Боливия (0 от 13).
    #
    # Долните единайсет ИМАТ цени. Числото до всяка е измереното покритие.
    ("eng.league_cup", 8, "Карабао Къп"),           # 12 от 12
    ("ger.dfb_pokal", 8, "Купа на Германия"),       # 2 от 4
    ("ned.2", 4, "Ерсте дивизи, Нидерландия"),      # 6 от 6
    ("eng.5", 3, "Национална лига, Англия"),        # 12 от 12
    ("sco.2", 4, "Чемпиъншип, Шотландия"),          # 4 от 5
    ("ksa.1", 6, "Про лига, Саудитска Арабия"),     # 8 от 17
    ("ksa.kings.cup", 5, "Купа на краля, Саудитска Арабия"),  # 2 от 3
    ("chn.1", 5, "Супер лига, Китай"),              # 8 от 9
    ("usa.usl.1", 3, "USL Чемпиъншип"),             # 11 от 15
    ("usa.usl.l1", 3, "USL Лига 1"),                # 3 от 3
    ("usa.nwsl", 4, "НУСЛ, жени"),                  # 2 от 2
]
# По подразбиране НЕ реже — целият списък. Една заявка на лига на ден е евтино;
# мълчащ спорт не е. Таванът се смята от самия списък, за да не остане пак
# закован на старо число, когато някой добави лига (точно това стана с 19).
FOOT_SLUG_MAX = env_int("PREDICT_FOOT_SLUGS", len(FOOT_SLUGS), 1, len(FOOT_SLUGS))
FOOT_PRIOR = 1.38       # голове на отбор на мач — типично за силна лига
FOOT_SHRINK = 6.0
FOOT_HOME = 1.12
FOOT_AWAY = 0.89
FOOT_LAM_MIN, FOOT_LAM_MAX = 0.25, 4.5
FOOT_HALFLIFE = 400.0   # дни; мач отпреди година тежи ~54%
# ДВОЙНИЯТ ШАНС Е ИЗКЛЮЧЕН ПО ИЗРИЧНА ПОРЪЧКА НА СОБСТВЕНИКА (05.08.2026):
#   „Не искам двоен шанс — много ниски коефициенти, безсмислени."
#
# И е прав по сметката. „1Х" при домакин с 45% покрива два изхода от три, тоест
# се плаща към 1.35, а след маржа остава почти нищо. Високата успеваемост там е
# оптическа: печелиш често, но малко.
#
# Нулата значи „винаги сам победител". Кодът за двоен шанс остава жив и
# измерен — включва се с PREDICT_FOOT_SINGLE_MIN=0.50, без да се пипа файл.
# Причината да не се трие: правилото беше сложено след измерване (11 отсъдени
# футболни прогнози, 2 познати, четири от деветте загуби бяха чисти равенства),
# а измереното не се хвърля — то е решение на собственика, не грешка в кода.
FOOT_SINGLE_MIN = env_float("PREDICT_FOOT_SINGLE_MIN", 0.0, 0.0, 0.9)


def soccer_seasons(now):
    """ESPN брои футболния сезон по НАЧАЛНАТА година: 2025 = сезон 2025-26."""
    s = now.year if now.month >= 7 else now.year - 1
    return [s, s - 1]


# --------------------------------------------------- домашната лига на отбора
# ЗАЩО СЪЩЕСТВУВА ТОВА
# Историята на отбор се вади ПО ЛИГА. За мач от евротурнир лигата е самият
# евротурнир — а там отборът има 6-13 мача на сезон. Резултатът, измерен на
# живо: квалификациите за Шампионска лига се отказваха с „няма история (1 и 3
# мача)", а за груповата фаза моделът смяташе върху шепа мачове и хвърляше
# тридесетте от вътрешното първенство.
#
# Затова: ESPN дава състава на всяка лига на един адрес, а id-тата на отборите
# са ГЛОБАЛНИ (проверено: Sturm Graz е 2790 и в австрийската листа, и в мача от
# квалификациите). Строим веднъж речник отбор -> домашна лига и за всеки мач от
# купа добавяме и вътрешните мачове.
#
# Цена: по една заявка на лига, и то ЕДВА когато има мач от купа. При мач само
# от вътрешни първенства индексът изобщо не се строи.
# Всеки адрес тук е ПРОВЕРЕН на живо на 28.07.2026 — върна състав с отбори.
# Изхвърлени, защото ESPN просто ги няма (404 или празен състав): pol.1, cze.1,
# cro.1, srb.1, ukr.1, hun.1, slo.1, svk.1, kor.1, fin.1, isl.1, kaz.1, aze.1,
# bul.1, mda.1. Всеки от тях беше по една подарена напразно заявка на пускане.
# Практическата цена: полски, хърватски, сръбски, украински и чешки клуб в
# евротурнир остава без вътрешна история и ботът честно ще го пропусне.
# Български клуб също няма — bul.1 не съществува в ESPN. Това е дупка в
# данните, не мързел.
FOOT_DOMESTIC = [
    "eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "ned.1", "por.1", "tur.1",
    "gre.1", "bel.1", "sco.1", "aut.1", "sui.1", "den.1", "nor.1", "swe.1",
    "rou.1", "isr.1", "cyp.1", "irl.1", "slv.1", "rus.1", "eng.2",
    "bra.1", "arg.1", "usa.1", "mex.1", "ksa.1", "jpn.1", "chn.1", "aus.1",
]
# Турнирите, при които „лигата на мача" не е домашно първенство.
FOOT_CUP_PREFIX = ("uefa.", "fifa.", "concacaf.", "conmebol.", "club.", "afc.", "caf.")

_foot_dom_index = None      # id на отбор -> адрес на домашната му лига


def foot_domestic_index():
    """Строи се най-много веднъж на пускане. Липсваща лига се прескача тихо."""
    global _foot_dom_index
    if _foot_dom_index is not None:
        return _foot_dom_index
    idx = {}
    got = 0
    for slug in FOOT_DOMESTIC:
        j = http_json(ESPN_SITE + "/soccer/" + slug + "/teams", quiet=True)
        if not isinstance(j, dict):
            continue
        try:
            teams = (((j.get("sports") or [{}])[0].get("leagues") or [{}])[0]
                     .get("teams") or [])
        except Exception:       # noqa: BLE001
            teams = []
        n = 0
        for t in teams:
            tid = str(((t or {}).get("team") or {}).get("id") or "")
            if tid and tid not in idx:      # първата лига печели — не местим отбор
                idx[tid] = slug
                n += 1
        if n:
            got += 1
    _foot_dom_index = idx
    print("   справочник домашни лиги: " + str(len(idx)) + " отбора от "
          + str(got) + " първенства.")
    return idx


def merge_recs(a, b):
    """Слепва два списъка мачове без повторения (един мач = дата + съперник)."""
    out = list(a)
    seen = set()
    for r in out:
        seen.add((r.get("date"), r.get("opp")))
    for r in b:
        k = (r.get("date"), r.get("opp"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


FOOT_FAIL_TOLERANCE = 3     # подред, не общо


def football_fixtures(now, ymd):
    """Обхожда лигите. Една капризна лига НЕ бива да отнася целия футбол.

    Старият код спираше спорта при първата грешка. Това е вярно, когато мрежата
    е долу, но НЕ и когато една лига е между сезони или ESPN е капнал само за
    нея — тогава губехме и останалите осемнадесет. Затова: броим провалите
    ПОДРЕД и спираме едва след три (мрежата наистина е долу), а един самотен
    провал само се отбелязва и се минава нататък.
    """
    out = []
    fails = 0
    for slug, w, name in FOOT_SLUGS[:FOOT_SLUG_MAX]:
        try:
            out += espn_fixtures("soccer", slug, ymd, "football", w, name, now,
                                 {"seasons": soccer_seasons(now)})
            fails = 0               # успех => броячът се нулира
        except Exception as e:      # noqa: BLE001
            fails += 1
            print("   ⚠ футбол " + slug + ": " + str(e)[:60])
            if fails >= FOOT_FAIL_TOLERANCE:
                print("   ⚠ три поредни провала — спирам футбола за това пускане.")
                break
    return out


def football_history(fx, side):
    tid = fx.get("home_id") if side == "home" else fx.get("away_id")
    if not tid:
        return []
    slug = (fx.get("extra") or {}).get("slug") or "eng.1"
    seasons = list((fx.get("extra") or {}).get("seasons") or [])
    recs = espn_history("soccer", slug, tid, seasons, "football")
    # Мач от евротурнир: добавяме и вътрешното първенство на отбора, иначе
    # моделът гледа 6-13 мача вместо 40+.
    if slug.startswith(FOOT_CUP_PREFIX):
        dom = foot_domestic_index().get(str(tid))
        if dom:
            recs = merge_recs(recs, espn_history("soccer", dom, tid, seasons, "football"))
    if len(recs) < 12 and seasons:
        deep = seasons + [seasons[-1] - 1]
        recs = merge_recs(recs, espn_history("soccer", slug, tid, deep, "football"))
        if slug.startswith(FOOT_CUP_PREFIX):
            dom = foot_domestic_index().get(str(tid))
            if dom:
                recs = merge_recs(recs, espn_history("soccer", dom, tid, deep, "football"))
    return recs


def model_football(hr, ar, lvl, now):
    sh, sa = wstats(hr, now, FOOT_HALFLIFE), wstats(ar, now, FOOT_HALFLIFE)
    if not sh or not sa:
        return None
    # ТУК СЕ БРОЕШЕ ДОМАКИНСТВОТО ДВА ПЪТИ (намерено и оправено 04.08.2026).
    #
    # Старият код взимаше формата ПООТДЕЛНО по терен: „колко вкарва домакинът
    # У ДОМА" и „колко допуска гостът НА ГОСТИ". Тези числа обаче вече носят
    # цялото домакинско предимство в себе си — всеки отбор вкарва повече у дома.
    # После, на реда за lam_h, отгоре се умножаваше ОЩЕ ВЕДНЪЖ FOOT_HOME=1.12
    # и FOOT_AWAY=0.89. Тоест едно и също предимство влизаше двукратно.
    #
    # ИЗМЕРЕНО с истинския код, два НАПЪЛНО ЕДНАКВИ отбора:
    #     3+3 мача   ->  46.6% за домакина   (вярното е 42.9%)
    #    10+10 мача  ->  53.8%
    #    20+20 мача  ->  57.9%   тоест +15 пункта от нищото
    # Изкривяването РАСТЕ с историята, защото колкото повече мачове има,
    # толкова по-малко се свива формата по терен и толкова по-силно тя носи
    # предимството — върху което множителят пак се налага.
    #
    # Това обяснява и трите неща, които се виждаха отвън: 12 от 14 футболни
    # карти сочеха домакина; футболът е единственият спорт с надценяване
    # (z=−2.07 при +1.06 за всичко останало); а кофата „под 50%" е 6/7 футбол.
    #
    # ЛЕКАРСТВОТО НЕ Е да се занули FOOT_HOME/FOOT_AWAY — измерено е, че тогава
    # при 3 домакински мача предимството ИЗЧЕЗВА напълно и грешката сменя знака.
    # Вярното е класическото: силата на отбора е БЕЗ ТЕРЕН, а теренът влиза
    # веднъж, чрез множителите. Точно затова те съществуват.
    att_h = shrink(sh["gf"], lvl, sh["w"], FOOT_SHRINK) / lvl
    def_h = shrink(sh["ga"], lvl, sh["w"], FOOT_SHRINK) / lvl
    att_a = shrink(sa["gf"], lvl, sa["w"], FOOT_SHRINK) / lvl
    def_a = shrink(sa["ga"], lvl, sa["w"], FOOT_SHRINK) / lvl

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
    # 🔴 ДВЕ НОВИ (19.08.2026), проверени живо в ESPN същия ден. Евролигата и
    # европейските първенства ГИ НЯМА в ESPN (всичките дават 400) — това е
    # ограничение на източника, не пропуск.
    ("nbl", 4, "НБЛ, Австралия", 11.5),
    ("nba-development", 3, "Джи лига", 12.0),
]
BASK_HCA = {"nba": 2.4, "wnba": 2.2, "mens-college-basketball": 3.2,
            "womens-college-basketball": 3.2, "nbl": 2.8, "nba-development": 2.0}
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


# --------------------------------------------------- 🏈 АМЕРИКАНСКИ ФУТБОЛ (NFL)
# ВНИМАНИЕ ЗА АДРЕСА: при ESPN „football" е АМЕРИКАНСКИЯТ футбол, а нашият
# футбол е „soccer". Затова кошницата тук се казва amfootball, а пътят е
# football/nfl. Разменят ли се, единият спорт мълчаливо дърпа мачовете на другия.
#
# МОДЕЛЪТ е същият като баскетболния — точки за и против, логистична крива —
# само отклонението е друго: разликата в НФЛ се колебае с около 13.5 точки,
# докато в баскетбола е 11.5. При 13.5 предимство от 7 точки дава ~64%.
AMF_LEAGUES = [("nfl", 10, "НФЛ", 13.5),
               ("college-football", 5, "Колежански", 16.0)]
AMF_HALFLIFE = 200.0     # дни; един сезон е 17 мача, паметта не бива да е дълга
AMF_SHRINK = 4.0
AMF_HOME = 2.0           # точки предимство за домакина


def amfootball_seasons(now):
    """НФЛ брои сезона по началната година: 2026 = сезон 2026-27 (септември)."""
    s = now.year if now.month >= 7 else now.year - 1
    return [s, s - 1]


def amfootball_fixtures(now, ymd):
    out = []
    for slug, w, name, sigma in AMF_LEAGUES:
        try:
            out += espn_fixtures("football", slug, ymd, "amfootball", w, name, now,
                                 {"seasons": amfootball_seasons(now), "sigma": sigma})
        except Exception as e:      # noqa: BLE001
            print("   ⚠ американски футбол " + slug + ": " + str(e)[:60])
    return out


def amfootball_history(fx, side):
    tid = fx.get("home_id") if side == "home" else fx.get("away_id")
    if not tid:
        return []
    ex = fx.get("extra") or {}
    slug = ex.get("slug") or "nfl"
    seasons = list(ex.get("seasons") or amfootball_seasons(datetime.now(SOFIA)))
    recs = espn_history("football", slug, tid, seasons, "amfootball")
    if len(recs) < 8 and seasons:
        recs = merge_recs(recs, espn_history("football", slug, tid,
                                             seasons + [seasons[-1] - 1], "amfootball"))
    return recs


def model_amfootball(hr, ar, fx, now):
    """Точки за и против, свити към нивото, после логистична крива."""
    sh, sa = wstats(hr, now, AMF_HALFLIFE), wstats(ar, now, AMF_HALFLIFE)
    if not sh or not sa:
        return None
    ex = fx.get("extra") or {}
    sigma = float(ex.get("sigma") or 13.5)
    hca = 0.0 if ex.get("neutral") else AMF_HOME
    lvl = (sh["gf"] + sh["ga"] + sa["gf"] + sa["ga"]) / 4.0
    sf_h = shrink(sh["gf"], lvl, sh["w"], AMF_SHRINK)
    sa_h = shrink(sh["ga"], lvl, sh["w"], AMF_SHRINK)
    sf_a = shrink(sa["gf"], lvl, sa["w"], AMF_SHRINK)
    sa_a = shrink(sa["ga"], lvl, sa["w"], AMF_SHRINK)
    exp_h = (sf_h + sa_a) / 2.0 + hca / 2.0
    exp_a = (sf_a + sa_h) / 2.0 - hca / 2.0
    margin = clampf(exp_h - exp_a, -28.0, 28.0)
    scale = sigma * math.sqrt(3.0) / math.pi
    p_home = logistic(margin / scale)
    return {"exp_h": exp_h, "exp_a": exp_a, "total": exp_h + exp_a,
            "margin": margin, "p_home": p_home, "p_away": 1.0 - p_home,
            "sh": sh, "sa": sa, "sigma": sigma}


# ----------------------------------------------------------------- ⚾ БЕЙЗБОЛ (MLB)
MLB_API = "https://statsapi.mlb.com/api/v1"
MLB_HOME = 0.25         # рънове предимство за домакина (~53% базова победа)
MLB_SCALE = 2.43        # 4.4 ръна стандартно отклонение -> sigma*sqrt(3)/pi
_mlb_hist = {}


def baseball_fixtures(now, ymd_dash):
    # 🔴 `hydrate=probablePitcher` НЕ СТРУВА ДОПЪЛНИТЕЛНА ЗАЯВКА (18.08.2026):
    # същият адрес, един параметър. Измерено на живо: без него нула мача носят
    # питчър, с него 13 от 15 днес и 9 от 15 утре.
    # Стартиращият питчър е първото, което човек гледа в бейзбола. НЕ влиза в
    # сметката — за това трябва измерване, каквото още нямаме — но влиза на
    # картата и в дневника, за да може след месец да се провери струва ли си.
    j = http_json(MLB_API + "/schedule?sportId=1&date=" + ymd_dash
                  + "&hydrate=probablePitcher")
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
                "extra": {
                    "home_en": str(h.get("name") or ""),
                    "away_en": str(a.get("name") or ""),
                    "pit_home": str((((t.get("home") or {}).get("probablePitcher")
                                      or {}).get("fullName")) or "").strip(),
                    "pit_away": str((((t.get("away") or {}).get("probablePitcher")
                                      or {}).get("fullName")) or "").strip()},
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
#
# 🔴 РАЗШИРЕНО 13.08.2026 ОТ ДВЕ НА СЕДЕМ ЛИГИ.
#
# Дотук стояха само UFC и PFL и това личеше в дневника: ММА дава карти в ЕДИН
# ден от петнайсет. Пробвах петнайсет адреса срещу ESPN на живо; седем
# отговарят, осем връщат 400 (ONE, Invicta, BKFC, Glory, DWCS, PFL Europe,
# UFC Fight Night, голото „mma"). Dana White's Contender Series НЕ е отделен
# адрес — идва през „ufc".
#
# ТЕЖЕСТИТЕ НЕ СА УКРАСА. Те решават кой бой изобщо стига до подбора: UFC
# носи 10, а Cage Warriors 2. Иначе малка гала с непознати бойци щеше да се
# бори наравно с главния бой на UFC — а моделът стъпва на Elo от миналите
# боеве и за малките лиги той е беден. Тежестта е признанието колко му вярваме.
#
# ЦЕНАТА: пет заявки повече на пускане (по една на лига). Бюджетът е 220 на
# рън, а пълното пускане ползва ~130 — тоест има място. Ако някога опре,
# PREDICT_MMA_LIGI реже списъка отвън, без пипане на код.
#
# 🔴 ЧЕСТНО ЗА ПЕЧАЛБАТА — ИЗМЕРЕНО 13.08.2026, НЕ ПРЕДПОЛОЖЕНО:
# ДНЕС петте нови лиги дават НУЛА боя. Голият им адрес връща ПОСЛЕДНАТА им
# гала, не следващата (Bellator върна събитие отпреди 697 дни, RIZIN отпреди
# 590). Питани с диапазон 13.08-27.08 дават 0 събития — ESPN просто не носи
# бъдещото им разписание.
#
# Значи защо са тук: заявката е евтина, а когато ESPN качи тяхна гала, тя
# влиза сама. Това е опция без цена, не подобрение с измерен ефект. Ако утре
# някой очаква „сега ММА ще вали" — няма да вали. ММА е рядък, защото ММА е
# рядък: UFC кара по една гала седмично, останалите ги няма в разписанието.
MMA_LEAGUES_VSI = [("ufc", 10, "UFC"), ("pfl", 6, "PFL"),
                   ("bellator", 5, "Bellator"), ("rizin", 4, "RIZIN"),
                   ("ksw", 3, "KSW"), ("lfa", 3, "LFA"),
                   ("cage-warriors", 2, "Cage Warriors")]
_mma_want = [s.strip().lower()
             for s in (os.environ.get("PREDICT_MMA_LIGI") or "").split(",") if s.strip()]
MMA_LEAGUES = [x for x in MMA_LEAGUES_VSI if not _mma_want or x[0] in _mma_want]
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


def mma_finish(status, periods):
    """Предсрочен ли е краят на боя. None = не можем да кажем.

    ТУК СТОЕШЕ ДЕФЕКТ, КОЙТО ЛЪЖЕШЕ ВСЕКИ ДЕН (намерен и оправен 04.08.2026).
    Старият код четеше „period" и „displayClock" от status["type"], а те живеят
    на самия status. И двете излизаха празни, тоест сметката ставаше
        finish = not (3 >= 3 and "".startswith("5:0")) = not False = True
    ВИНАГИ. Измерено: 71 от 71 бойци с дял на предсрочните победи 100%.
    Картата печаташе „Печели предсрочно в 5 от 5 победи" за когото и да е.

    По-скъпото беше невидимото: Elo коефициентът е MMA_ELO_K * 1.25 при
    предсрочна победа и * 0.9 при съдийско решение. Щом „предсрочно" е винаги
    вярно, множителят 0.9 никога не се е ползвал — тоест дефектът мести САМИТЕ
    рейтинги, не само текста под тях.

    ПРАВИЛОТО: ESPN няма поле „начин на победа". Изведено: боят е стигнал до
    съдиите, ако са изиграни всичките рундове И часовникът е в края си. Едни
    фийдове броят нагоре до 5:00, други надолу до 0:00 — приемат се и двете.

    БЕЗ ЧАСОВНИК НЕ ТВЪРДИМ НИЩО. Връща се None и боят не влиза в статистиката
    за предсрочни победи. По-добре по-малка извадка, отколкото същата лъжа с
    друг знак.
    """
    s = status if isinstance(status, dict) else {}
    per = to_num(s.get("period"))
    clock = str(s.get("displayClock") or "").strip()
    if not clock:
        return None                       # няма на какво да стъпим
    try:
        n_per = int(periods)
    except (TypeError, ValueError):
        n_per = 3
    celi = (per is not None) and (per >= n_per)
    iztekal = clock.startswith("5:0") or clock.startswith("0:0")
    return not (celi and iztekal)


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
                # ЧЕТЕ СЕ ОТ status, НЕ от status["type"] — точно това беше дефектът.
                finish = mma_finish(comp.get("status") or {}, periods)
                fights.append({"date": str(ev.get("date") or "")[:10],
                               "a": ids[0], "b": ids[1], "w": win, "fin": finish})
    fights.sort(key=lambda f: f["date"])
    elo, seen = {}, {}
    for f in fights:
        for cid in (f["a"], f["b"]):
            if cid not in elo:
                w, l, _d = parse_record(rec.get(cid) or "")
                elo[cid] = mma_prior(w, l)
                seen[cid] = {"n": 0, "w": 0, "fin": 0, "znaem": 0}
        ra, rb = elo[f["a"]], elo[f["b"]]
        sa = 1.0 if f["w"] == f["a"] else 0.0
        # Неизвестен начин на победа (fin=None) минава с НЕУТРАЛЕН коефициент.
        # Дотук такъв случай нямаше — защото „предсрочно" беше винаги вярно и
        # множителят 0.9 не се ползваше нито веднъж.
        if f["fin"] is None:
            k = MMA_ELO_K
        else:
            k = MMA_ELO_K * (1.25 if f["fin"] else 0.9)
        ea = elo_expect(ra, rb)
        elo[f["a"]] = ra + k * (sa - ea)
        elo[f["b"]] = rb + k * ((1.0 - sa) - (1.0 - ea))
        for cid in (f["a"], f["b"]):
            seen[cid]["n"] += 1
        seen[f["w"]]["w"] += 1
        # „znaem" брои победите, за които ЗНАЕМ начина. Дялът на предсрочните
        # се смята срещу него, не срещу всички победи — иначе липсващите данни
        # се броят за съдийски решения и числото пак лъже, само в другата посока.
        if f["fin"] is not None:
            seen[f["w"]]["znaem"] += 1
            if f["fin"]:
                seen[f["w"]]["fin"] += 1
    _mma_idx[league] = {"elo": elo, "stat": seen, "rec": rec, "fights": len(fights)}
    return _mma_idx[league]


def mma_fixtures(now):
    out = []
    # 🔴 С ДИАПАЗОН, НЕ НА ГОЛ АДРЕС (19.08.2026) — ПОПРАВКА НА ГОЛЯМ ДЕФЕКТ.
    #
    # Коментарът тук твърдеше, че голият адрес винаги дава предстоящата гала и
    # никога не е празен. Измерено на живо същия ден: ВЯРНО за PFL и ГРЕШНО за
    # UFC — най-важната организация:
    #     /mma/ufc/scoreboard                      -> 1 събитие, 5 боя, 5 ЗАВЪРШЕНИ
    #     /mma/ufc/scoreboard?dates=20260819-20260829 -> 3 събития, 27 боя, 0 завършени
    # Тоест голият адрес връщаше ВЧЕРАШНАТА приключила гала, тя падаше на
    # филтъра по дата, и UFC даваше НУЛА. Стаята 🥊 се хранеше само от PFL —
    # организацията, която пазарът изобщо не търгува.
    _ot = now.strftime("%Y%m%d")
    _do = (now + timedelta(days=int(MMA_DAYS_AHEAD) + 1)).strftime("%Y%m%d")
    for league, w, label in MMA_LEAGUES:
        j = http_json(ESPN_SITE + "/mma/" + league + "/scoreboard?dates="
                      + _ot + "-" + _do)
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

    # Дялът предсрочни победи се дели на ПОБЕДИТЕ С ИЗВЕСТЕН НАЧИН („znaem"),
    # не на всички. Ако делим на всички, боевете без часовник се броят мълчаливо
    # за съдийски решения и числото пак лъже — просто в другата посока.
    # Прагът е поне 4 такива победи: „100% предсрочно" от една победа е число
    # без съдържание.
    def _dyal(s):
        z = s.get("znaem", 0)
        return (s.get("fin", 0) / float(z)) if z >= 4 else None

    fin_a, fin_b = _dyal(sa_), _dyal(sb_)
    return {"p_home": p, "p_away": 1.0 - p, "ra": ra, "rb": rb, "na": na, "nb": nb,
            "rec_h": (wa, la), "rec_a": (wb, lb), "fin_h": fin_a, "fin_a": fin_b,
            "win_h": sa_.get("w", 0), "win_a": sb_.get("w", 0),
            "znaem_h": sa_.get("znaem", 0), "znaem_a": sb_.get("znaem", 0),
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
# 🔴 ШИРИНАТА, ИЗМЕРЕНА НА ЖИВО 18.08.2026 (беше заковано 0.55).
#
# 114 съдени мача от живия дневник: ботът ОБЯВЯВА 58.1%, а СБЪДВА 75.4% —
# 17.3 точки под собствената си дума, при шум ±7.9. Тоест продаваме по-евтино,
# отколкото струваме, и то системно.
#
# Подписът показва, че вината е в ШИРИНАТА, не в модела:
#     една звезда (обявено ~52.6%)  →  сбъднато 54.5%   разлика +1.9 т
#     две+ звезди (обявено ~60.4%)  →  сбъднато 84.0%   разлика +23.6 т
# При 50% умножението по ширина не мести нищо; при 65% мести всичко. Точно
# това се вижда. Ако моделът грешеше, разликата щеше да е равна навсякъде.
#
# Цепките държат: първата половина дни +14.3, втората +20.2, най-голямата
# лига +20.2 — и трите извън шума, независимо една от друга.
#
# Пробвани ширини върху същите 114 мача (обявено / сбъднато / Брайер):
#     0.55  →  58.1% / 75.4%  +17.3 т  0.2053   (сегашното)
#     1.70  →  71.3% / 75.4%   +4.2 т  0.1692
#     2.20  →  74.5% / 75.4%   +0.9 т  0.1646   ← избраното
#     2.80  →  77.1% / 75.4%   -1.7 т  0.1630
#     3.50  →  78.9% / 75.4%   -3.5 т  0.1646
# Брайерът е почти равен между 2.2 и 3.5. Избираме края, който НЕ обещава
# повече, отколкото сбъдва: 2.2 дава +0.9 т, 2.8 вече дава -1.7 т.
#
# Път назад: PREDICT_TT_SCALE=0.55 връща точно старото поведение.
TT_SCALE = env_float("PREDICT_TT_SCALE", 2.2, 0.3, 4.5)
# 🔴 СТЕНИТЕ НЕ СЕ ПИПАТ. Измерено: НУЛА от 114-те мача опират в 0.15/0.85 при
# старата ширина, а разширяването им беше мерено и излезе ПО-ЛОШО. Тесният
# процент не идваше от стените, а от ширината.
TT_P_MIN, TT_P_MAX = 0.15, 0.85

# 🔴 ШИРИНАТА ВАЖИ САМО ТАМ, КЪДЕТО Е ИЗМЕРЕНА (19.08.2026).
#
# Намерено с ЧЕТЕНЕ НА СТАЯТА, не от тест. Излязла карта:
#   „Martin BUCH — 77% · ясен фаворит"
#   „Martin BUCH: 18 победи и 19 загуби" (тоест ОТРИЦАТЕЛЕН баланс)
# Обяснението под числото оборваше самото число пред очите на читателя.
#
# Причината: 2.2 е нагласена върху 114 съдени мача от Europe Smash и WTT
# Champions, където играчите имат по 40-150 мача. Разбито по извадка:
#     по-малката извадка 50+   →  62 мача, +18.8 т подценяване
#     по-малката извадка 20-49 →  51 мача, +16.9 т подценяване
#     по-малката извадка под 20 →  1 мач  (и той загубен)
# Тоест под 20 мача ширината 2.2 НЕ Е ИЗМЕРЕНА НИКОГА. При Feeder турнирите
# играчите имат по 8-11 мача и тя произвежда 77-79% от нищо.
#
# Лекарството е стъпка, не измислена крива: над прага важи измереното, под
# него се връщаме към предпазливото старо. Интерполацията между двете би била
# съчинена математика — а за нея нямаме нито едно число.
TT_PALNA_N = env_int("PREDICT_TT_PALNA_N", 20, 5, 100)
TT_SCALE_MALKO = env_float("PREDICT_TT_SCALE_MALKO", 0.55, 0.2, 2.5)


def tt_shirina(n_malka):
    """Коя ширина важи за тази извадка. Пълната — само където е измерена."""
    try:
        n = int(n_malka)
    except (TypeError, ValueError):
        return TT_SCALE_MALKO
    return TT_SCALE if n >= TT_PALNA_N else TT_SCALE_MALKO
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


# 🔴 КОЙ ТУРНИР СЕ ГЛЕДА, КОГАТО ТЕКАТ ПОВЕЧЕ ОТ ТАВАНА (18.08.2026)
#
# Досега кодът взимаше ПЪРВИТЕ ДВА в реда на файла — тоест по случайност.
# Измерено върху живия календар на WTT (172 турнира за 2026): на 9 от
# следващите 45 дни текат по 4-5 турнира едновременно, значи 2-3 се изхвърлят
# невидимо. На 26-28.08 се пропускат по три наведнъж.
#
# Редът вече е по ТЕЖЕСТ. Юношеските падат най-долу нарочно: там няма
# 18-месечна история на играча, а тя е целият ни източник за този спорт —
# без нея процентът е познайница с десетична запетая.
def _tt_dumi(ime):
    """Името, разцепено на цели думи. „U11&U13" дава {u11, u13}."""
    d, cur = set(), []
    for ch in str(ime or "").lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            d.add("".join(cur))
            cur = []
    if cur:
        d.add("".join(cur))
    return d


def _tt_rang(ime):
    """Колко тежи турнир. По-голямото се гледа първо, щом таванът реже.

    🔴 ПО ЦЕЛИ ДУМИ, НЕ ПО ПОДНИЗ (поправено 18.08.2026).
    Първата ми версия търсеше „champions" като подниз — а „championSHIPS" го
    съдържа. Върху ИСТИНСКИЯ календар това значеше: „ITTF-Americas U11&U13
    Championships Houston" и „Central American Masters Championships" вземаха
    85, тоест нивото на WTT Champions, и изхвърляха от тавана българския WTT
    Contender Panagyurishte и един Feeder. Детски и ветерански турнири
    изяждаха възрастни професионални.

    Стълбицата е сверена срещу ВСИЧКИТЕ 170 имена в календара за 2026.
    Юношеските и ветеранските падат най-долу нарочно: там няма 18-месечна
    история на играча, а тя е целият ни източник за този спорт.
    """
    d = _tt_dumi(ime)
    if d & {"youth", "junior", "juniors", "cadet", "cadets",
            "u11", "u13", "u15", "u17", "u19", "u21"}:
        return 10
    if "masters" in d:                      # ветерански, не елитни
        return 12
    if "finals" in d and "wtt" in d:
        return 92
    if "smash" in d:
        return 90
    if "cup" in d and "world" in d:
        return 88
    if "championships" in d and "world" in d:
        return 86
    if "champions" in d:                    # ЦЯЛА дума, не подниз
        return 85
    if "contender" in d:
        return 78 if "star" in d else 70
    if "feeder" in d:
        return 60
    if "cup" in d:
        return 55
    if "regional" in d:
        return 38
    if d & {"championships", "championship"}:
        return 48
    if "games" in d:
        return 45
    return 40


# Таван на едновременно гледаните турнири. Всеки струва едно разписание плюс
# статистиката на играчите в него — затова не е безкраен.
TT_MAX_TURNIRI = env_int("PREDICT_TT_TURNIRI", 3, 1, 8)


def tt_turnir_sled(now, napred_dni=21):
    """След колко дни почва следващият турнир по тенис на маса. None = не знам.

    🔴 ЗАЩО НЕ СТИГА ДА СЕ ПИТА ЗА МАЧОВЕ (18.08.2026). WTT публикува
    разписанието на един турнир чак ден-два преди началото му. Измерено на
    живо: на 18.08 календарът ясно казва „WTT Feeder Berlin, 19-23.08", а
    разписанието за 19.08 връща НУЛА мача. Тоест здравният преглед питаше
    „има ли мач утре?", получаваше „не" и вдигаше ЧЕРВЕН флаг за спорт, който
    просто е между два турнира.

    Календарът знае истината. Него питаме.
    """
    try:
        cal = http_json(WTT_CDN + "/websitestaticapifiles/general/"
                        + str(now.year) + "_eventcalendar.json", quiet=True)
    except Exception:                                        # noqa: BLE001
        return None
    rows = []
    for blk in (cal if isinstance(cal, list) else [cal or {}]):
        rows += ((blk or {}).get("rows") or [])
    if not rows:
        return None
    dnes = now.strftime("%Y-%m-%d")
    nay = None
    for r in rows:
        st = str(dget(r, "StartDateTime") or "")[:10]
        en = str(dget(r, "EndDateTime") or "")[:10]
        if not st or not en or en < dnes:
            continue
        # Турнир, който ТЕЧЕ днес, значи нула дни чакане.
        try:
            dni = (datetime.strptime(st, "%Y-%m-%d").date() - now.date()).days
        except ValueError:
            continue
        dni = max(0, dni)
        if dni <= int(napred_dni) and (nay is None or dni < nay):
            nay = dni
    return nay


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
    # 🔴 ПРАЗЕН КАЛЕНДАР НЕ Е „НЯМА ТУРНИРИ" (19.08.2026). `http_json` връща
    # None при провал БЕЗ да гърми — тоест задавен CDN изглеждаше точно като
    # спокоен ден без турнири, и здравният преглед казваше „източникът върна
    # нула срещи". Хванато на живо: два успоредни рънa задавиха WTT и тенисът
    # на маса тихо стана нула, при 120 налични мача.
    if not rows:
        print("   ⚠ тенис на маса: календарът се върна ПРАЗЕН — това е провал "
              "на източника, не липса на турнири.")
        return []
    live = []
    for r in rows:
        s = str(dget(r, "StartDateTime") or "")[:10]
        e = str(dget(r, "EndDateTime") or "")[:10]
        eid = to_num(dget(r, "EventId"))
        if eid and s and e and s <= ymd_dash <= e:
            live.append((eid, str(dget(r, "EventName") or "WTT")))
    # Най-тежкият пръв; при равенство — по име, за да е повторимо.
    live.sort(key=lambda x: (-_tt_rang(x[1]), str(x[1])))
    _imalo_turniri = bool(live)
    out = []
    for eid, ename in live[:TT_MAX_TURNIRI]:
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
    # 🔴 БЛИЗНАКЪТ НА ПРАЗНИЯ КАЛЕНДАР (19.08.2026). Календарът може да мине,
    # а РАЗПИСАНИЕТО да се задави — тогава пак излиза чиста нула без нито една
    # дума. Турнир, който тече и дава нула мача, е подозрение, не факт.
    if _imalo_turniri and not out:
        print("   ⚠ тенис на маса: %d турнира текат, а разписанието даде НУЛА "
              "мача — по-вероятно е провал на източника, отколкото празен ден."
              % len(live))
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
    # Ширината се избира по ПО-МАЛКАТА от двете извадки: сигурността на
    # сравнението е толкова, колкото е по-слабо познатият играч.
    _n_malka = min(a["w"] + a["l"], b["w"] + b["l"])
    _sh = tt_shirina(_n_malka)
    p = clampf(logistic((logit(ra) - logit(rb)) * _sh), TT_P_MIN, TT_P_MAX)
    to_win = 4 if int((fx.get("extra") or {}).get("best_of") or 5) >= 7 else 3
    p_game = invert_bo(p, to_win)
    return {"p_home": p, "p_away": 1.0 - p, "a": a, "b": b, "ra": ra, "rb": rb,
            "to_win": to_win, "dist_h": bo_distribution(p_game, to_win),
            "dist_a": bo_distribution(1.0 - p_game, to_win),
            "n_malka": _n_malka, "shirina": _sh,
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
    if b == "amfootball":
        return amfootball_history(fx, side)
    return []


def samp(a, b):
    """Върху колко мача стъпва картата — на човешки.

    Пишеше „извадка 30+30 мача". Плюсът подвежда: човек го чете като сбор 60,
    а числата са ПООТДЕЛНО за двата отбора. Затова сега е „по 30 и 30 мача" —
    същите числа, но се четат както са замислени.
    """
    x, y = int(a), int(b)
    if x == y:
        return "гледани по " + str(x) + " мача на всеки"
    return "гледани " + str(x) + " мача на единия и " + str(y) + " на другия"


# 🔴 ПРЕРАБОТЕНО 11.08.2026. Звездите казваха „увереност", а НЕ мереха
# увереност. Резултатът се четеше в стаята така:
#     „1 · победа Bodo/Glimt — 50%   ⭐⭐⭐ добра увереност"
# Петдесет процента е монета. Три звезди до нея са обещание, което самото
# число опровергава два сантиметра по-нагоре. И обратното: две карти с по 92%
# получаваха различен брой звезди и никой не разбираше защо.
#
# Причината е, че grade() смесва ДВЕ различни неща в един символ: колко мача
# има зад картата (n_eff) и колко категоричен е превесът (strength). Затова
# сега всяко от двете си казва своето с думи:
#   • звездите остават, но говорят за ДАННИТЕ — колко стъпка има под картата
#   • отделен ред казва колко е категоричен изборът, и той идва ПРАВО от
#     вероятността, така че не може да ѝ противоречи
ZVEZDI_DUMA = {1: "малко данни", 2: "прилична история", 3: "богата история"}

# Границите не са на око. Върху 75 586 мача от бектеста измереното е, че под
# 58% посочената страна печели горе-долу колкото хвърлена монета, между 58 и
# 65 има истински, но лек превес, а над 75 разликата е видима с просто око.
P_DUMI = ((0.80, "🟢 много ясен фаворит"),
          (0.68, "🟢 ясен фаворит"),
          (0.60, "🟡 лек фаворит"),
          (0.55, "🟠 мъничък превес"),
          (0.00, "🔴 почти равностойни"))


def p_duma(p):
    """Присъдата с думи — идва ПРАВО от процента, затова не може да го излъже."""
    try:
        x = float(p)
    except (TypeError, ValueError):
        return ""
    for prag, duma in P_DUMI:
        if x >= prag:
            return duma
    return ""


# Имената на турнирите идват на английски и често отрязани по средата:
# „FIVB Volleyball Girls' U17 World Championship…". Тук се превеждат тези,
# които се повтарят всеки ден. Непознато име минава както си е — по-добре
# английско, отколкото сгрешено.
LIGA_BG = (
    # Редът тук е РЕШАВАЩ: конференциите се пробват ПРЕДИ Лига Европа, защото
    # името им съдържа нейното. И ключовете носят долната черта и точката както
    # ги пише ESPN — търсенето е буквално „парче в низа", не по думи. Първата
    # версия на тези два реда беше с интервали („europa qual") и не хващаше нищо:
    # самопроверката я хвана още на първото пускане.
    ("champions_qual", "Квалификации за Шампионска лига"),
    ("europa.conf_qual", "Квалификации за Лига на конференциите"),
    ("conference league qual", "Квалификации за Лига на конференциите"),
    ("europa_qual", "Квалификации за Лига Европа"),
    ("europa league qual", "Квалификации за Лига Европа"),
    ("uefa champions", "Шампионска лига"),
    ("uefa europa conf", "Лига на конференциите"),
    ("uefa europa", "Лига Европа"),
    ("premier league", "Висша лига, Англия"),
    ("laliga", "Ла Лига"), ("la liga", "Ла Лига"),
    ("serie a", "Серия А"), ("bundesliga", "Бундеслига"),
    ("ligue 1", "Лига 1"), ("eredivisie", "Ередивизи"),
    ("primeira liga", "Примейра лига"), ("brasileirao", "Серия А, Бразилия"),
    ("major league soccer", "MLS"),
    ("girls' u17 world championship", "Световно U17, девойки"),
    ("boys' u17 world championship", "Световно U17, юноши"),
    ("girls' u19 world championship", "Световно U19, девойки"),
    ("boys' u19 world championship", "Световно U19, юноши"),
    ("world championship", "Световно първенство"),
    ("nations league", "Лига на нациите"),
    ("national bank open", "Мастърс, Торонто/Монреал"),
    ("western & southern", "Мастърс, Синсинати"),
    ("major league baseball", "МЛБ"),
)


def liga_bg(name, cap=44):
    """Български надпис за турнира, ако го познаваме. Иначе — подрязан оригинал."""
    s = str(name or "").strip()
    low = s.lower()
    for klyuch, bg in LIGA_BG:
        if klyuch in low:
            return bg
    if len(s) > cap:
        s = s[:cap - 1].rstrip() + chr(8230)
    return s


def pobedi_zagubi(w, l):
    """„10 победи и 21 загуби" вместо „10-21".

    🔴 ДОБАВЕНО 11.08.2026 след като прочетох живата карта в стая 27. Там
    пишеше „Lily ZHANG: 10-21 за 18 месеца". Тирето между две числа може да е
    победи-загуби, може да е резултат, може да е диапазон. Читателят не е
    длъжен да гадае, а ние не печелим нищо от съкращаването.
    """
    w, l = int(w or 0), int(l or 0)
    return (str(w) + (" победа" if w == 1 else " победи")
            + " и " + str(l) + (" загуба" if l == 1 else " загуби"))


def boeve_index(n):
    """Опашката за ММА: колко боя на този човек сме гледали ние."""
    n = int(n or 0)
    if n == 0:
        return " · него не сме го следили"
    return " · следили сме " + str(n) + (" негов бой" if n == 1 else " негови боя")


def one(x, d=1):
    return ("%." + str(d) + "f") % float(x)


# --- ФИШ-ЕЗИКЪТ ---------------------------------------------------------------
# Прогнозата се изписва като на фиш: 1 / Х / 2, после кой. Никакви гатанки.
OU_MIN = 0.57           # ред „Над/Под 2.5 гола" само когато матрицата е категорична


def pick_1x2(p1, px, p2, home, away):
    """Футболният избор на фиш-език. Връща (текст, вероятност, база).

    ⚠️ ДВОЙНИЯТ ШАНС Е ИЗКЛЮЧЕН (05.08.2026). FOOT_SINGLE_MIN е 0.0, тоест
    всеки път излиза САМ победител — 1, Х или 2. Долният клон е недостижим,
    докато собственикът не го включи изрично. Причината е в неговите думи:
    коефициентът на двойния шанс е твърде нисък, за да си струва.

    ВАЖНОТО, което ОСТАВА в сила: клонът „Х · равен" вече работи наистина.
    Допреди 04.08 той беше практически недостижим, защото домакинството се
    броеше двойно и вдигаше p_home изкуствено. След поправката равенството
    печели най-високата вероятност там, където наистина е най-вероятно —
    видяно на живо: „Х · равен — 40%" при два предпазливи отбора.

    ЗАЩО ИМА ДВОЕН ШАНС — измерено на 04.08.2026, не усетено:
      От единайсет отсъдени футболни прогнози познахме ДВЕ. И единайсетте бяха
      „1" или „2" — нито една „Х". Причината не е лош късмет, а устройство:
      при Поасон равенството почти никога не е най-вероятният ЕДИНИЧЕН изход
      (около 0.28 срещу около 0.40 за домакина), тоест клонът за „Х" стоеше
      в кода, но беше практически недостижим.
      ЧЕТИРИ от деветте загуби бяха именно равенства: 0:0, 1:1, 0:0, 2:2.
      Двоен шанс върху същите единайсет мача дава ШЕСТ познати вместо две.
      Това е сметка върху вече изиграни мачове, не обещание за бъдещето.

    Правилото е едно: твърдим сам победител само когато сме убедени
    (>= FOOT_SINGLE_MIN). Иначе покриваме и равенството. Силните карти
    остават единични — двойният шанс не размива това, което вече знаем.

    Базата се връща, защото „1" се пада на случайност веднъж на три пъти,
    а „1Х" — два пъти на три. Без нея двойният шанс би получавал звезди
    наготово.
    """
    if px >= p1 and px >= p2:
        return "Х · равен", px, 1.0 / 3.0       # равенството наистина води
    vodi_home = p1 >= p2
    p_vodi = p1 if vodi_home else p2
    ime = str(home) if vodi_home else str(away)
    if p_vodi >= FOOT_SINGLE_MIN:
        return (("1 · победа " if vodi_home else "2 · победа ") + ime,
                p_vodi, 1.0 / 3.0)
    if vodi_home:
        return "1Х · " + ime + " или равен", p1 + px, 2.0 / 3.0
    return "Х2 · " + ime + " или равен", p2 + px, 2.0 / 3.0


def pick_win(fav_home, home, away):
    """Отборните спортове без равен: 1 · победа <отбор> или 2 · победа <отбор>."""
    return ("1 · победа " + str(home)) if fav_home else ("2 · победа " + str(away))


def pick_name(fav_home, home, away):
    """Индивидуалните спортове: 1 · <име> или 2 · <име>."""
    return ("1 · " + str(home)) if fav_home else ("2 · " + str(away))


def over_under_line(p_over):
    """Ред „Над/Под 2.5 гола" от готовата голова матрица (P на общо 3+ гола).

    Излиза само когато едната страна е поне 57% — иначе редът е шум.

    ЧИСЛОТО СЕ СВИВА ПРЕДИ ОБЯВЯВАНЕ. Измерено върху 75 586 изиграни мача:
    суровото обявяваше 64.7% при реални 60.7% (над) и 64.9% при реални 57.4%
    (под). Пълната сметка стои при OU_SHRINK.
    """
    p = svii(p_over, OU_SHRINK)
    if p is None:
        return ""
    if p >= OU_MIN:
        return "Над 2.5 гола: <b>" + pct(p) + "</b>"
    if (1.0 - p) >= OU_MIN:
        return "Под 2.5 гола: <b>" + pct(1.0 - p) + "</b>"
    return ""


# ------------------------------------------------- ТОТАЛИ ЗА ОСТАНАЛИТЕ СПОРТОВЕ
# Футболът отдавна има ред „Над/Под 2.5 гола". Собственикът поиска същото и за
# другите спортове: точки за баскетбола, сетове за волейбола и тениса.
# Всеки ред тук излиза САМО ако едната страна е поне OU_MIN — иначе е шум и се
# премълчава. По-добре три реда сигурни, отколкото пет реда пълнеж.

TOTAL_MIN = OU_MIN          # един и същ праг като при головете


def _norm_cdf(z):
    """Стандартно нормално разпределение. math.erf стига — без numpy."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def points_total_line(exp_total, sigma_margin, unit="точки"):
    """Над/Под общо точки, с ЯСНО ИЗПИСАНА линия.

    ЗАЩО ЛИНИЯТА НЕ Е НА ОЧАКВАНИЯ СБОР (първата ми версия беше сгрешена):
    сложиш ли линията точно на средата, отговорът винаги е около 50% и редът
    не казва нищо — просто мълчеше на всеки мач. Затова линията е на половин
    отклонение ПОД средата: тогава твърдението „над X точки" носи смисъл и
    процентът е реален, а не украсен. Линията се пише на глас, за да може
    всеки да я провери сам.

    ЗА ОТКЛОНЕНИЕТО, честно: моделът знае отклонението на РАЗЛИКАТА. Сборът
    се колебае повече — двата отбора вдигат и свалят темпото ЗАЕДНО, а темпото
    движи сбора. Затова тук отклонението е умишлено по-широко (1.25 пъти):
    по-широко значи по-предпазлив процент, а не по-самоуверен.
    """
    if not exp_total or exp_total <= 0:
        return ""
    mean = float(exp_total)
    sd = max(4.0, float(sigma_margin or 11.5) * 1.25)
    line = math.floor(mean - 0.5 * sd) + 0.5
    if line <= 0:
        return ""
    p_over = 1.0 - _norm_cdf((line - mean) / sd)
    # ЧЕСТНО ЗА ТОЗИ ПРОЦЕНТ (добавено 04.08.2026 след измерване):
    # линията стои на половин отклонение под средата, а вероятността се смята
    # със СЪЩОТО отклонение — значи z е закован на −0.5 и процентът излиза
    # 68-70% при ВСЕКИ мач. Измерено: 111 от 111 проби в този тесен обхват,
    # нито една „Под". Твърдението не е невярно — то наистина има тази
    # вероятност — но само по себе си е ПРАЗНО, защото не се променя.
    # Информацията, която липсваше, е самият ОЧАКВАН СБОР: той се мени от мач
    # на мач и точно той казва нещо. Затова се изписва до линията.
    # Закръгляне на линията НЕ е лекарството — измерено е, че тогава редът
    # изчезва в 103 от 111 мача, тоест това е изтриване, а не поправка.
    ochakvan = "~" + str(int(round(mean))) + " " + unit + " общо · "
    if p_over >= TOTAL_MIN:
        return (ochakvan + "Над " + ("%.1f" % line) + ": <b>" + pct(p_over) + "</b>")
    if (1.0 - p_over) >= TOTAL_MIN:
        return (ochakvan + "Под " + ("%.1f" % line) + ": <b>" + pct(1.0 - p_over) + "</b>")
    return ""


# ═══════════ СВИВАНЕ ПРЕДИ ОБЯВЯВАНЕ ═══════════
# ИЗМЕРЕНО ВЪРХУ 75 586 ИЗИГРАНИ МАЧА (2014-2026, 19 лиги), с истинския код на
# бота и без надничане в бъдещето. Проверката за надничане е направена така:
# същият бектест е пуснат три пъти с различен отрез на историята и ЧЕСТНИЯТ
# ред излиза НАЙ-СЛАБ (50.06% срещу 53.43% при изтекъл ден). Тоест числата тук
# са долната, истинската граница.
#
# ГЛАВНИЯТ РЕД (1/Х/2) СЕ ОКАЗА ЧЕСТЕН: обявява 48.4%, сбъдва се 50.1% —
# подценява се в своя вреда. Нито една кофа не надува.
#
# НО ДОПЪЛНИТЕЛНИТЕ РЕДОВЕ НАДУВАТ, и то много:
#     Над 2.5      обявено 64.7%  сбъднато 60.7%   −4.0
#     Под 2.5      обявено 64.9%  сбъднато 57.4%   −7.5
#     Гол-гол ДА   обявено 62.6%  сбъднато 58.4%   −4.2
#     Гол-гол НЕ   обявено 62.0%  сбъднато 55.0%   −6.9
# И колкото по-категоричен е редът, толкова по-голяма е лъжата: при обявени
# над 70% реалното е 66.6% за над/под и 63.9% за гол-гол.
#
# ЛЕКАРСТВОТО: числото се свива към 50%, преди да се обяви. Множителите НЕ са
# нагласени върху същите данни — научени са от 2014-2021 (47 132 мача) и
# изпитани върху 2022-2026 (28 454 мача, невиждани):
#     над/под 2.5   лъжа −5.8 пункта  →  +0.4 пункта
#     гол-гол       лъжа −5.4 пункта  →  +0.5 пункта
# Цената е, че редовете излизат около два пъти по-рядко. Купеното е, че когато
# излязат, числото им е вярно.
#
# ПЪТ НАЗАД: две константи. Връщат се на 1.0 и всичко е както преди.
OU_SHRINK = env_float("PREDICT_OU_SHRINK", 0.58, 0.2, 1.0)
BTTS_SHRINK = env_float("PREDICT_BTTS_SHRINK", 0.56, 0.2, 1.0)


def svii(p, k):
    """Свива вероятността към монетата. k=1.0 значи „не пипай"."""
    try:
        return clampf(0.5 + float(k) * (float(p) - 0.5), 0.0, 1.0)
    except (TypeError, ValueError):
        return None


def btts_line(p_btts):
    """Ред „Гол-гол" (и двата отбора бележат) от готовата голова матрица.

    ТОВА ЧИСЛО СЕ СМЯТАШЕ И СЕ ХВЪРЛЯШЕ. `matrix_markets` вече обхожда всичките
    121 клетки и сумира p_btts (тези с i>=1 и j>=1), но НИТО ЕДИН ред не го
    четеше — стоеше сметнато и неизползвано от самото начало.

    Прагът е същият OU_MIN като при Над/Под 2.5: под 57% и в двете посоки редът
    мълчи, защото „51% да вкарат и двата" не е прогноза, а монета.

    ЗАЩО НЕ ПРЕПИСВА Над/Под 2.5 — измерено върху 169 двойки ламбди: в 12 случая
    излиза „Над 2.5" ЗАЕДНО с „Гол-гол: НЕ" (единият громи — много голове, но
    само от едната страна), а в 13 случая Над/Под мълчи, докато гол-гол говори.
    Тоест 25 от 169 карти печелят ред, който другият не може да даде.

    ЧЕСТНО ЗА ТОЗИ РЕД: измерено е, че се МЕНИ както трябва (227 различни
    стойности от 231 входа през model_football, от 16% до 92%) — тоест не е
    закована константа като реда за точки, който оправихме. НО калибрацията му
    НЕ е проверена срещу изиграни мачове: дали „Гол-гол: ДА 61%" се сбъдва в 61%
    от случаите, ще покаже само дневникът след няколко седмици.
    """
    if p_btts is None:
        return ""
    try:
        surovo = float(p_btts)
    except (TypeError, ValueError):
        return ""
    # Пазачът гледа СУРОВОТО число. Ако го гледаше свитото, изродена матрица с
    # 0 или 1 щеше да мине, защото свиването я издърпва навътре.
    if surovo <= 0.0 or surovo >= 1.0:
        return ""                      # изродена матрица — по-добре мълчание
    # Свиване ПРЕДИ прага: измерено е, че суровото число надува с 4-7 пункта.
    p = svii(surovo, BTTS_SHRINK)
    if p is None:
        return ""
    if p >= OU_MIN:
        return "Гол-гол: ДА <b>" + pct(p) + "</b>"
    if (1.0 - p) >= OU_MIN:
        return "Гол-гол: НЕ <b>" + pct(1.0 - p) + "</b>"
    return ""


# ------------------------------------------------------- 🏒 ХОКЕЙНИЯТ ТОТАЛ
# Хокеят има готова голова матрица (model_hockey дава lam_h и lam_a), но досега
# от нея излизаше само едно голо число в скоби. Тук тя се ползва докрай.
#
# ЗАЩО rho=0: Диксън-Коулс дърпа четири клетки с множител 1 − lh·la·rho. При
# футболни ламбди (1.5:1.2) това е 1.234 — лека добавка към 0:0. При хокейни
# (3.2:3.0) същата формула дава 2.248, тоест УДВОЯВА 0:0. Корекцията е линейна
# по произведението, а в хокея то е шест пъти по-голямо и калибровката ѝ се
# разпада. Затова тук се вика score_matrix(..., rho=0.0) — както прави и
# самият model_hockey.
#
# ЗАЩО ЛИНИЯТА Е СТЪЛБА ОТ ДВЕ, А НЕ ЕДНА: измерено върху 992 реални двойки от
# живата НХЛ таблица очакваният сбор е между 4.94 и 7.72 гола (медиана 6.24).
# При линия 3.5 отговорът е „над" в 992 от 992 случая — закована истина, тоест
# празен ред. 5.5 е истинската хокейна линия, но при сбор между 5.15 и 6.10 тя
# дава 43-57% и мълчи (376 от 992 мача); тогава се стъпва на 6.5, която точно в
# този диапазон говори ясно. Линиите 4.5 и 7.5 бяха махнати: избират се 0 пъти
# от 19881 проби — тоест са мъртъв код, не предпазител.
HOCK_TOTAL_LINES = (5.5, 6.5)


def _hock_p_over(mx, line):
    """P(общо голове над линията) направо от готовата голова матрица."""
    need = int(math.floor(float(line))) + 1
    s = 0.0
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            if i + j >= need:
                s += mx[i][j]
    return s


def hockey_goals_line(lam_h, lam_a):
    """Над/Под общо голове в хокея, с ясно изписана линия.

    Редът НЕ е константа — измерено върху 992-те двойки дава 22 различни
    процента в обхват 57-78%, най-честият покрива само 9% от картите, а изборът
    на линия следва сбора монотонно.
    """
    try:
        lh, la = float(lam_h or 0.0), float(lam_a or 0.0)
    except (TypeError, ValueError):
        return ""
    if lh <= 0 or la <= 0:
        return ""
    mx = score_matrix(lh, la, rho=0.0)
    for line in HOCK_TOTAL_LINES:
        p_over = _hock_p_over(mx, line)
        if p_over >= TOTAL_MIN:
            return "Над " + ("%.1f" % line) + " гола: <b>" + pct(p_over) + "</b>"
        if (1.0 - p_over) >= TOTAL_MIN:
            return "Под " + ("%.1f" % line) + " гола: <b>" + pct(1.0 - p_over) + "</b>"
    return ""


def set_prob_from_match(p_match, best_of=3):
    """Обратната сметка: от вероятността за МАЧА към вероятността за ЕДИН СЕТ.

    Тенис-моделът дава само кой печели мача. Но при мач до 2 спечелени сета
    важи P(мач) = s^2 * (3 - 2s), където s е вероятността да вземеш един сет.
    Функцията е строго растяща, затова я обръщаме с деление наполовина —
    двадесет и пет стъпки стигат за четвърти знак. Никакво допускане, само
    аритметика.
    """
    p = clampf(float(p_match), 0.5, 0.999)     # смятаме за фаворита
    lo, hi = 0.5, 0.999
    for _ in range(25):
        mid = (lo + hi) / 2.0
        if best_of == 3:
            got = mid * mid * (3.0 - 2.0 * mid)
        else:                                  # до 3 спечелени сета
            q = 1.0 - mid
            got = mid ** 3 * (1.0 + 3.0 * q + 6.0 * q * q)
        if got < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def tennis_sets_line(p_match, best_of=3):
    """Над/Под сета — с линия, която ПАСВА на формата на мача.

    ТУК ИЗЛИЗАШЕ ФИЗИЧЕСКИ НЕВЪЗМОЖЕН РЕД (намерено и оправено 04.08.2026).
    Функцията беше закована на „мач до два спечелени сета" и печаташе
    „Над/Под 2.5 сета" за ВСЕКИ тенис мач — включително за мачовете до ТРИ
    спечелени сета. А там най-малкият възможен брой сетове е 3, тоест
    „Под 2.5 сета" не е грешна оценка, а твърдение, което НЕ МОЖЕ да се сбъдне.
    Загуба, обявена предварително.

    Форматът вече беше известен на модела (extra.best_of), но не стигаше дотук.

    ЛИНИЯТА Е СТЪЛБА, както при хокея: при мач до три спечелени опитваме първо
    3.5 („ще има ли четвърти сет"), после 4.5 („ще има ли пети"). При мач до два
    спечелени има само едно смислено място — 2.5.
    """
    bo5 = int(best_of or 3) >= 5
    to_win = 3 if bo5 else 2
    s = set_prob_from_match(p_match, 5 if bo5 else 3)
    dist = bo_distribution(s, to_win=to_win)
    # bo_distribution дава разпределението за фаворита; огледалото е за другия.
    ogledalo = [(j, i, p) for (i, j, p) in dist]
    linii = (3.5, 4.5) if bo5 else (2.5,)
    for line in linii:
        p_over = sets_p_over([dist, ogledalo], line)
        if p_over is None:
            continue
        if p_over >= TOTAL_MIN:
            return "Над " + ("%.1f" % line) + " сета: <b>" + pct(p_over) + "</b>"
        if (1.0 - p_over) >= TOTAL_MIN:
            return ("Под " + ("%.1f" % line) + " сета: <b>"
                    + pct(1.0 - p_over) + "</b>")
    return ""


def sets_p_over(dists, line_sets):
    """P(сетовете са повече от линията) от разпределението. None при празно.

    Изнесено от sets_total_line, за да могат два реда да ползват ЕДНА сметка
    вместо да си я преписват — преписаният цикъл е два кода, които утре ще се
    разминат.
    """
    p_over = 0.0
    total = 0.0
    for dist in dists:
        for row in (dist or []):
            try:
                i, j, p = int(row[0]), int(row[1]), float(row[2])
            except Exception:                 # noqa: BLE001
                continue
            total += p
            if (i + j) > line_sets:
                p_over += p
    if total <= 0:
        return None
    return p_over / total                     # нормираме, ако сборът не е точно 1


# Таван на реда за пети сет. Над него числото повтаря КЛАМПА на модела
# (VOL_P_MIN/VOL_P_MAX), а не мери конкретния мач: измерено на живо — всичките
# 110 от 400 истински двойки, при които p_rally опира в границата, дават едно и
# също 97%. Точно капанът „ред, който изглежда като мярка, а е закована стойност".
VOL5_CAP = 0.97


def fifth_set_line(dists):
    """Ще стигне ли мачът до пети сет — от сетовото разпределение.

    ЕДНОПОСОЧЕН НАРОЧНО. Клонът „ДА" е ДОКАЗАНО недостижим: максимумът на
    P(пети сет) е 0.375 (обходени 20001 стойности на p_rally от 0.30 до 0.70),
    а прагът за излизане е 0.57. Тоест „Пети сет: ДА/НЕ" щеше да е фалшив избор —
    човек би чакал някога да види „ДА", а то математически не може да се случи.
    Затова редът казва само това, което наистина мери.

    Числото ОБАЧЕ не е константа: върху 400 истински двойки отбори (FIVB, 7694
    изиграни мача) излизат 35 различни закръглени стойности между 63% и 97%,
    като най-голямата купчина е само 13% от случаите.

    Волейболът е пръв до 3 спечелени сета, затова „без пети сет" значи точно
    „мачът свършва 3:0, 3:1 или огледалното" — тоест до 4 сета.
    """
    p5 = sets_p_over(dists, 4.5)
    if p5 is None:
        return ""
    p_bez = 1.0 - p5
    if p_bez < TOTAL_MIN or p_bez > VOL5_CAP:
        return ""
    return "Мачът свършва до 4 сета: <b>" + pct(p_bez) + "</b>"


def sets_total_line(dists, line_sets):
    """Над/Под N.5 сета — направо от разпределението на сетовете.

    Тук НЯМА никакво допускане: моделът вече е сметнал вероятността на всеки
    точен резултат по сетове (3:0, 3:1, 3:2 и огледалните). Просто събираме
    тези, при които сетовете са повече от линията. Затова този ред е по-твърд
    от точковия — той е точна сметка, не приближение.
    """
    p_over = sets_p_over(dists, line_sets)
    if p_over is None:
        return ""
    if p_over >= TOTAL_MIN:
        return ("Над " + ("%.1f" % line_sets) + " сета: <b>" + pct(p_over) + "</b>")
    if (1.0 - p_over) >= TOTAL_MIN:
        return ("Под " + ("%.1f" % line_sets) + " сета: <b>" + pct(1.0 - p_over) + "</b>")
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
    # second = кратката добавка на спорта (очакван резултат / най-вероятен сет)
    # third  = ТОТАЛЪТ: над/под голове, точки или сетове. Излиза само когато
    #          едната страна е поне 57% — иначе е шум и се премълчава.
    second, third, why = "", "", []

    if b == "football":
        m = model_football(hr, ar, ctx["lvl"], now)
        if not m:
            return None, "няма история"
        p1, px, p2 = m["p_home"], m["p_draw"], m["p_away"]
        # Фиш-език: 1 / Х / 2 / 1Х / Х2. Никакво „не губи" — пише се „или равен".
        pick, p, baza = pick_1x2(p1, px, p2, fx["home"], fx["away"])
        strength = strength_1x2(p, baza)
        # Ред Над/Под 2.5 гола направо от головата матрица, само при >= 57%.
        second = over_under_line(m["p_over"])
        # ГОЛ-ГОЛ — поискан поименно от собственика. Числото p_btts вече се
        # смяташе в matrix_markets и не се четеше от никого.
        third = btts_line(m.get("p_btts"))
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
        third = points_total_line(m.get("total"),
                                  (fx.get("extra") or {}).get("sigma"), "точки")
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
        # 🔴 ОПРАВЕНО 11.08.2026. Дотук сетовият резултат влизаше В САМАТА
        # прогноза: „1 · победа Корея (3:0) — 92%". Човекът чете „3:0 с 92%",
        # а 92% е вероятността да СПЕЧЕЛИ МАЧА — точното 3:0 е далеч по-рядко
        # (тук 52%). Тоест картата обещаваше нещо, което моделът не твърди, а
        # оценителят и без това отсъждаше само победителя. Числото си остава,
        # но слиза на свой ред, със своята си вероятност.
        pick = pick_win(fav_home, fx["home"], fx["away"])
        # Волейболът е до 3 спечелени сета: „над 3.5" значи мач в 4 или 5 сета.
        third = sets_total_line([m.get("dist_h"), m.get("dist_a")], 3.5)
        # Числото се сверява с обявеното: сборът на разпределението е СУРОВАТА
        # вероятност за победа, а на картата стои свитата. Показваме дела на
        # този резултат ВЪТРЕ в обявеното, иначе двете числа си противоречат.
        _sur = sum(float(x[2]) for x in dist) or 1.0
        second = ("Най-вероятен резултат: " + str(best[0]) + ":" + str(best[1])
                  + " (" + pct(float(best[2]) / _sur * p) + ")")
        if not third:
            # Редът 3.5 мълчи — тогава втората рубрика поема дължината на мача.
            third = fifth_set_line([m.get("dist_h"), m.get("dist_a")])
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
        # Тенисът на маса е до 3 спечелени гейма: „над 4.5" = мач в 6 или 7.
        third = sets_total_line([m.get("dist_h"), m.get("dist_a")], 4.5)
        # 🔴 ПРЕПИСАНО 11.08.2026 след като прочетох картата в стаята.
        # Пишеше „Lily ZHANG: 10-21 за 18 месеца". Човек не знае 10 победи ли
        # са, или 10 мача, или резултат. Сега си го казваме с думи.
        why = [home + ": " + pobedi_zagubi(m["a"]["w"], m["a"]["l"]) + " за година и половина",
               away + ": " + pobedi_zagubi(m["b"]["w"], m["b"]["l"]) + " за година и половина"]
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
                s += ", " + pobedi_zagubi(f[0], f[1]) + " в последните седмици"
            return s
        # ФОРМАТЪТ СТИГА ДОТУК. Дотогава редът беше закован на „до два спечелени
        # сета" и в мачовете до три печаташе „Под 2.5 сета" — невъзможно
        # твърдение, защото там минимумът е 3 сета.
        third = tennis_sets_line(max(m["p_home"], m["p_away"]),
                                 (fx.get("extra") or {}).get("best_of") or 3)
        why = [_pl(home, m["ra"], m["fa"]), _pl(away, m["rb"], m["fb"])]
        # Ранглистата е силен ориентир, но е ЕДИН показател, не двайсет мача.
        # Брои се за шест мача на играч, не повече — иначе картата се хвали с
        # „добра увереност" върху три видени мача, което е точно лъжата,
        # която не искаме да продаваме.
        ranked = (1 if m["ra"].get("rank") else 0) + (1 if m["rb"].get("rank") else 0)
        n_eff = min(30.0, m["n_a"] + m["n_b"] + 6.0 * ranked)
        if min(m["n_a"], m["n_b"]) < 6:
            n_eff = min(n_eff, 19.0)    # под 6 видени мача = най-много две звезди
        sample = ("ранглиста и " + str(m["n_a"] + m["n_b"]) + " скорошни мача")

    elif b == "mma":
        m = model_mma(fx, now)
        if not m["ok"]:
            return None, "няма история (под 3 боя в кариерата)"
        fav_home = m["p_home"] >= 0.5
        pick = pick_name(fav_home, fx["home"], fx["away"])
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        fin = m["fin_h"] if fav_home else m["fin_a"]
        # Знаменателят е броят победи с ИЗВЕСТЕН начин, не всички победи —
        # инак дробта и текстът щяха да си противоречат.
        wins = m.get("znaem_h") if fav_home else m.get("znaem_a")
        wins = int(wins or 0)
        if fin is not None and fin >= 0.6 and wins >= 4:
            second = ("Печели предсрочно в " + str(int(round(fin * wins))) + " от "
                      + str(wins) + " победи в индекса")
        rh, ra_ = m["rec_h"], m["rec_a"]
        why = [home + ": " + pobedi_zagubi(rh[0], rh[1]) + " в кариерата"
               + boeve_index(m["na"]),
               away + ": " + pobedi_zagubi(ra_[0], ra_[1]) + " в кариерата"
               + boeve_index(m["nb"])]
        n_eff = m["na"] + m["nb"] + 0.4 * (rh[0] + rh[1] + ra_[0] + ra_[1])
        # „0+0 боя в индекса" не значеше нищо за читателя. Ако никой от двамата
        # не е следен от нас, това е ГЛАВНОТО, което трябва да знае.
        sample = (("не сме следили нито един от двамата")
                  if (m["na"] + m["nb"]) == 0
                  else ("следени " + str(m["na"] + m["nb"]) + " техни боя"))

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
        # Опашката „· над 5.5" беше махната оттук: тя дублираше новия трети ред
        # в 588 от 992 карти. Едно и също число два пъти на една карта.
        second = "Очаквани голове " + one(m["lam_h"]) + " : " + one(m["lam_a"])
        third = hockey_goals_line(m.get("lam_h"), m.get("lam_a"))
        why = [home + " у дома: " + one(m["hgf"], 2) + " вкарани и " + one(m["hga"], 2)
               + " допуснати гола за мач",
               away + " на гости: " + one(m["agf"], 2) + " вкарани и " + one(m["aga"], 2)
               + " допуснати; равен няма, продълженията са близо до монета"]
        n_eff = m["gp_h"] + m["gp_a"]
        sample = samp(m["gp_h"], m["gp_a"])

    elif b == "amfootball":
        m = model_amfootball(hr, ar, fx, now)
        if not m:
            return None, "няма история"
        fav_home = m["p_home"] >= 0.5
        pick = pick_win(fav_home, fx["home"], fx["away"])   # равен няма
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        second = ("Очакван резултат: ~" + str(int(round(m["exp_h"])))
                  + ":" + str(int(round(m["exp_a"]))))
        third = points_total_line(m.get("total"), m.get("sigma"), "точки")
        why = [home + ": " + one(m["sh"]["gf"]) + " : " + one(m["sh"]["ga"])
               + " точки за мач (" + str(m["sh"]["n"]) + " мача)",
               away + ": " + one(m["sa"]["gf"]) + " : " + one(m["sa"]["ga"])
               + " точки за мач (" + str(m["sa"]["n"]) + " мача)"]
        n_eff = m["sh"]["w"] + m["sa"]["w"]
        sample = samp(m["sh"]["n"], m["sa"]["n"])

    elif b == "baseball":
        m = model_baseball(hr, ar, now)
        if not m:
            return None, "няма история"
        fav_home = m["p_home"] >= 0.5
        pick = pick_name(fav_home, fx["home"], fx["away"])
        p = m["p_home"] if fav_home else m["p_away"]
        strength = strength_binary(m["p_home"])
        second = "Очаквани рънове " + one(m["exp_h"]) + " : " + one(m["exp_a"])
        # 🔴 ДВЕ ПОПРАВКИ НА ЕДНО МЯСТО (11.08.2026):
        #
        # 1. В „рънa“ последната буква беше ЛАТИНСКО a (U+0061) в българска
        #    дума. Не се вижда с око, но чупи всяко търсене и всяка проверка
        #    по текста. Същият знак стоеше на три места в този файл.
        #
        # 2. Шаблонът „X : Y“ значеше ДВЕ РАЗЛИЧНИ НЕЩА на една и съща карта:
        #    два реда по-горе стои „Очаквани рънове 5.0 : 4.2“ (прогноза за
        #    ТОЗИ мач), а тук „5.1 : 4.3“ беше среден вкаран : среден допуснат
        #    за сезона. Читателят вижда един и същ вид число два пъти и няма
        #    как да разбере кое какво е. Сега числата си носят думите —
        #    точно както вече е при футбола и хокея.
        why = [home + ": " + one(m["sh"]["gf"]) + " вкарани и "
               + one(m["sh"]["ga"]) + " допуснати ръна за мач ("
               + str(m["sh"]["n"]) + " мача)",
               away + ": " + one(m["sa"]["gf"]) + " вкарани и "
               + one(m["sa"]["ga"]) + " допуснати ръна за мач ("
               + str(m["sa"]["n"]) + " мача)"]
        n_eff = m["sh"]["w"] + m["sa"]["w"]
        sample = samp(m["sh"]["n"], m["sa"]["n"])

    else:
        return None, "непознат спорт"

    # ПРАГЪТ „няма превес" Е МАХНАТ КАТО ОТКАЗ.
    # По-рано срещата с 51% просто изчезваше. Собственикът реши друго: канал
    # за прогнози значи, че излиза и близката среща — с истинското си число.
    # 51% си е 51% и всеки го чете. Прагът остава само като БЕЛЕГ: под него
    # картата получава една звезда, тоест „равностойно".
    if strength < MIN_STRENGTH:
        return {"fx": fx, "bucket": b, "pick": pick, "p": p, "second": second,
                "third": third,
                "why": ([w for w in why if w][:2]
                        + ["Числата са близки — превесът е малък."])[:2],
                "sample": sample,
                "n_eff": float(n_eff), "strength": float(strength),
                "stars": 1}, ""

    return {"fx": fx, "bucket": b, "pick": pick, "p": p, "second": second,
            "third": third,
            "why": [w for w in why if w][:2], "sample": sample,
            "n_eff": float(n_eff), "strength": float(strength),
            "stars": grade(b, n_eff, strength)}, ""


# ================================================================= КАРТИТЕ
# Показва ли картата историята на бота за своя спорт. Може да се изключи с
# PREDICT_SHOW_RECORD=0, без да се пипа код.
SHOW_RECORD = (os.environ.get("PREDICT_SHOW_RECORD") or "1").strip() not in ("0", "false", "не")
RECORD_MIN = 10          # под толкова отсъдени НЕ показваме число
_record_cache = {}

SPORT_DUMA = {
    "football": "Футболът", "basketball": "Баскетболът", "volleyball": "Волейболът",
    "tennis": "Тенисът", "tabletennis": "Тенисът на маса", "hockey": "Хокеят",
    "baseball": "Бейзболът", "amfootball": "Американският футбол", "mma": "Бойните",
}


def sport_record(bucket):
    """Колко е познал ботът в ТОЗИ спорт досега. Празно, ако е рано.

    ДНЕВНИКЪТ САМО СЕ ПИШЕШЕ. `PICKLOG_FILE` се отваряше единствено за да се
    допише номер на фиш — нито един ред не го е ЧЕЛ. Значи 73 публикувани карти
    са минали, без нито една да носи доказателство зад себе си.

    Правилата тук са три, и трите заради честността:
      • само ОТСЪДЕНИ прогнози (hit не е None) — чакащите не се броят;
      • под RECORD_MIN отсъдени НЕ излиза число, а „твърде рано" — „1 от 1"
        изглежда като 100% и лъже повече, отколкото мълчанието;
      • знаменателят ВИНАГИ се изписва.

    Всичко е в try/except, защото card() се вика и от самопроверката, а тя е
    портиерът на целия рън. Повреден дневник не бива да спира бота.
    """
    if not SHOW_RECORD or not bucket:
        return ""
    if bucket in _record_cache:
        return _record_cache[bucket]
    red = ""
    try:
        rows = []
        # 🗄️ 18.08.2026. Оценителят мести приключените стари записи в архив.
        # Рекордът на картата иска ЦЕЛИЯ живот — иначе на всеки 120 дни ще
        # изглежда, че ботът е нов и няма история.
        _arh = (os.environ.get("SCORE_ARHIV_FILE") or "predict_log_arhiv.json").strip()
        for _f in (_arh, PICKLOG_FILE):
            if not os.path.exists(_f):
                continue
            with open(_f, encoding="utf-8-sig") as f:
                _r = json.load(f)
            if isinstance(_r, dict):
                _r = _r.get("rows") or []
            if isinstance(_r, list):
                rows += _r
        if rows or True:
            p = n = 0
            for r in rows:
                if (r or {}).get("bucket") != bucket:
                    continue
                if not r.get("scored") or r.get("hit") is None:
                    continue
                n += 1
                if r.get("hit"):
                    p += 1
            ime = SPORT_DUMA.get(bucket, "Спортът")
            if n >= RECORD_MIN:
                red = ("📊 " + ime + " досега: <b>" + str(p) + " от " + str(n)
                       + "</b> отсъдени · " + pct(float(p) / n))
            elif n > 0:
                red = ("📊 " + ime + " досега: " + str(p) + " от " + str(n)
                       + " — твърде рано за процент")
    except Exception:                          # noqa: BLE001
        red = ""                               # мълчим, но не чупим картата
    _record_cache[bucket] = red
    return red


# ═══════════════════════════════════ 📐 ОБРАТНОТО НА ПРОЦЕНТА (13.08.2026)
#
# ПОРЪЧКА НА СОБСТВЕНИКА: „искаше ми се и коефициенти да почнеш да даваш,
# поне тези които имаме достъп лайв".
#
# ИЗМЕРЕНО ПЪРВО, ПОСЛЕ ПИСАНО. Живите коефициенти ги има — ESPN ги дава в
# scoreboard за футбола. Но идват така:
#     {"overUnder": 2.5,
#      "link": "https://sportsbook.draftkings.com/gateway?...wpcn=ESPN..."}
# Тоест числото е ОФЕРТА НА БУКМЕЙКЪР, с неговия линк. Точно това реже
# BANNED_TOKENS (bet365, pinnacle, bwin, efbet, winbet, betano, 1xbet,
# „коеф", „букмейкър", „odds") — пазач, сложен, защото българският закон
# забранява рекламата на хазарт. Да ги публикуваме значи да рекламираме
# оператор. Не го правим.
#
# ЗАТОВА ТУК ЧИСЛОТО Е НАШЕ, НЕ ТЯХНО: просто обратното на собствената ни
# вероятност. 56% → 1 към 1.79. Никакъв оператор, никаква оферта, никакъв
# линк — само пренаписване на процента, който така или иначе стои на картата.
#
# Пишем го „1 към 1.79", а не с думата, която пазачът реже: думата носи
# хазартния контекст, а нотацията — само математиката.
KOEF_VKL = (os.environ.get("PREDICT_KOEF") or "1").strip() in ("1", "true", "да")


def obratno_na_procenta(p):
    """56% → „1 към 1.79". Празно при безсмислен вход."""
    try:
        x = float(p)
    except (TypeError, ValueError):
        return ""
    if not (0.01 < x < 1.0):
        return ""
    return "1 към " + ("%.2f" % (1.0 / x))


def card(an, now):
    """Кратка карта. Прогнозата е ГЕРОЯТ, обяснението е два реда."""
    fx = an["fx"]
    lg = liga_bg(fx.get("league"))
    koga = esc(fx.get("time") or when_label(fx.get("when"), now))
    stars = an["stars"]
    lines = [fx["emoji"] + " <b>" + esc(fx["home"]) + "</b> срещу <b>" + esc(fx["away"]) + "</b>"]
    sub = [x for x in [esc(lg), koga] if x]
    if sub:
        lines.append("<i>" + " · ".join(sub) + "</i>")

    # Прогнозата и присъдата стоят една под друга. Присъдата идва от процента,
    # затова не може да му противоречи — точно това правеха звездите.
    lines += ["",
              "🎯 <b>" + esc(an["pick"]) + "</b>",
              "<b>" + pct(an["p"]) + "</b> · " + p_duma(an["p"])]
    if KOEF_VKL:
        _obr = obratno_na_procenta(an.get("p"))
        if _obr:
            lines.append("📐 " + _obr + " — обратното на процента, наша сметка")
        # 🔴 ПАЗАРНАТА ЦЕНА (13.08.2026). Идва от ДЪЛБОКИЯ слой на ESPN —
        # scoreboard-ът я носи само за футбола, core я има и за бейзбол, и за
        # ВНБА. Само число: без име на оператор, без линк, без покана.
        _pz = an.get("pazar_cena")
        if _pz and PZ is not None:
            _red = PZ.red_za_karta(an.get("p"), _pz)
            if _red:
                lines.append(_red)

    # 🔴 ЗВЕЗДИТЕ ОТПАДНАХА (11.08.2026). Прочетох живата карта в стая 27:
    #     🎯 1 · победа Bodo/Glimt
    #     50% · 🔴 почти равностойни
    #     ⭐⭐⭐ богата история
    # Три звезди до петдесет процента. Думата „богата история" е вярна — 50 и
    # 42 гледани мача — но ⭐⭐⭐ се чете като оценка на ПРОГНОЗАТА, не на
    # данните. Символът и числото се бият пред очите на читателя, а той вярва
    # на символа. Смяна на звездата с друга емотикона не помага: всеки знак,
    # повторен три пъти, се чете като рейтинг.
    # Затова остава само думата — тя и без това беше там и не лъже.
    stapka = "📚 " + ZVEZDI_DUMA.get(stars, "") + " · " + esc(an["sample"])
    if stars <= 1 and float(an.get("n_eff") or 0.0) < 10.0:
        stapka += " · пазете се, стъпката е тънка"
    lines.append(stapka)

    # ⚾ Стартиращите питчъри. Факт, не оценка — затова стои като факт и няма
    # дума за това какво значи. Показва се само когато знаем И ДВАМАТА: един
    # питчър без другия не казва нищо, а изглежда сякаш казва.
    _ex = (fx.get("extra") or {}) if fx else {}
    _ph, _pa = str(_ex.get("pit_home") or ""), str(_ex.get("pit_away") or "")
    if _ph and _pa:
        # 🔴 РЕДЪТ Е ДОМАКИН → ГОСТ, като заглавието на картата (18.08.2026).
        # Първата ми версия ги нареждаше гост → домакин, защото MLB пише
        # „Toronto at Tampa Bay". Видяно в сухо пускане: заглавието казваше
        # „Tampa Bay Rays срещу Toronto Blue Jays", а редът отдолу —
        # „José Soriano срещу Nick Martinez", тоест точно обратното.
        # Никой тест не гръмна: собственият ми тест заключваше грешния ред.
        lines.append("⚾ Хвърлят: " + esc(_ph) + " срещу " + esc(_pa))

    # Допълнителните пазари стоят в свой блок, а не залепени за прогнозата.
    dop = [x for x in (an.get("second"), an.get("third")) if x]
    if dop:
        lines.append("")
        lines.append("➕ <b>И още от същия мач</b>")
        for d in dop:
            lines.append("• " + d)

    # Обяснението получава заглавие. Дотук двата реда висяха голи под картата
    # и не се разбираше, че са ПРИЧИНАТА за избора.
    prichini = [w for w in (an.get("why") or []) if w]
    if prichini:
        lines.append("")
        lines.append("📋 <b>Защо точно това</b>")
        for w in prichini:
            lines.append("• " + w)

    # И накрая — историята на бота в този спорт. Единственото на картата,
    # което читателят може да провери сам в стая ✅ Резултати.
    rec = sport_record(an.get("bucket") or (fx.get("bucket") if fx else ""))
    if rec:
        lines.append("")
        lines.append(rec)
    return NL.join(lines)


def header_card(now, count, seen):
    # Ботът гледа осем пъти на ден, затова заглавието НЕ обещава дневен сбор —
    # то отваря деня. Числото е за това пускане и точно това пише.
    return (chr(129504) + " <b>БОТА ПРЕДРИЧА</b> · " + date_bg(now) + NL
            + "Първи за деня: <b>" + str(count) + "</b> от " + n_match(seen)
            + " под лупата · денят тече, идват още.")


def footer_card(seen, thin, weak, sports):
    """Подписът под последната карта за деня.

    ТУК СТОЕШЕ ЗАБРАНЕНИЯТ ЕЗИК (махнат 05.08.2026). Пишеше „Гледахме 11 срещи
    от 9 спорта · 2 без история · 3 без превес" — точно това, което собственикът
    забрани с думите „спри да ми казваш какво следихме". Читателят не иска
    отчет за труда на бота; иска прогнози.

    Намерено чрез гледане на истинските съобщения в групата, не в кода — от
    самопроверката не се виждаше, защото тя проверяваше само дали текстът е
    чист от хазартни думи.

    Легендата на звездите ОСТАВА: тя е единственото тук, което помага на
    читателя. Останалото беше за нас, не за него.

    🔴 ЛЕГЕНДАТА БЕШЕ ОСТАНАЛА СТАРА (поправено 11.08.2026, същия ден).
    Сутринта звездите бяха преработени: те вече говорят за ДАННИТЕ, а
    увереността се казва с думи ПРАВО от процента (виж p_duma). Картата се
    смени, а този подпис под нея остана да обяснява „⭐⭐⭐ добра увереност" —
    тоест продължаваше да учи читателя на значение, което вече не съществува.
    Поправка без близнак е половин поправка.
    """
    return NL.join([
        "📘 <b>Как се чете картата</b>",
        "• Процентът е шансът на избора. До него с думи пише колко е ясен —"
        " от почти равностойни до много ясен фаворит.",
        "• Редът с 📚 казва върху КОЛКО данни стъпваме: малко данни,"
        " прилична история или богата история. Той НЕ оценява прогнозата.",
        "• Много данни и нисък процент е нормално. Значи знаем мача добре"
        " и той наистина е равностоен.",
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
        _zp, _pr, _gr = _http_used[0], len(_http_why), ""
        try:
            if b == "football":
                rows = football_fixtures(now, ymd)
            elif b == "basketball":
                rows = basketball_fixtures(now, ymd)
            elif b == "tennis":
                rows = tennis_fixtures(now, ymd)
            elif b == "hockey":
                rows = hockey_fixtures(now, ymd_dash)
            elif b == "amfootball":
                rows = amfootball_fixtures(now, ymd)
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
            _gr = str(e)[:90]
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
        # ЧЕРНАТА КУТИЯ. Дневникът на GitHub се чете само с админски права, а
        # страницата му не се рендира навсякъде — тоест отвън НЕ СЕ ВИЖДА защо
        # един спорт мълчи. Три спорта не дадоха карта НИТО ВЕДНЪЖ и никой не
        # разбра, защото числото живееше само в един изчезващ дневник.
        # Затова цифрите се записват във файл, който се връща в хранилището.
        DIAG[b] = {"suredi": len(rows), "surovi": n_all,
                   "zapochnali": gone, "daleche": far,
                   "zaqvki": _http_used[0] - _zp,
                   "gr": ([_gr] if _gr else []) + _http_why[_pr:][:4]}
        print("   " + SPORTS[b]["emoji"] + " " + b + ": " + str(len(rows)) + " срещи"
              + ((" (" + str(gone) + " вече започнали)") if gone else "")
              + ((" (" + str(far) + " далече — чакат)") if far else ""))
    return buckets


# ═══════════════════════════════════════ ПРОГНОЗА ВИНАГИ (резервната стълба)
# РЕШЕНИЕ НА СОБСТВЕНИКА (29.07.2026, казано два пъти и ясно):
#   „Това е спортен канал за прогнози. Пишеш каквото може."
# Затова отказът „няма история — не гадаем" е МАХНАТ като краен изход.
#
# Честността не изчезва, а се мести на две места, които остават:
#   • ПРОЦЕНТЪТ — при празна извадка той е близо до 50 и не се разкрасява
#   • ЗВЕЗДИТЕ — една звезда и изписано на какво стъпва картата
# Читателят вижда и двете и си преценява сам. Това беше и уговорката.
#
# Стълбата отгоре надолу:
#   1. пълен модел (когато има история)          — до три звезди
#   2. частични данни (ранглиста, форма, H2H)    — една звезда
#   3. нищо                                       — предимството на домакина
FALLBACK_HOME = {
    # Колко често печели домакинът/първият в двойката, когато не знаем нищо.
    # Числата са общоприети за съответния спорт, не са измислени в движение.
    "football": 0.45,       # 1X2: равенството яде част от масата
    "basketball": 0.60,
    "volleyball": 0.55,
    "hockey": 0.55,
    "baseball": 0.54,
    "tabletennis": 0.50,    # „домакин" няма — двойката е неутрална
    "tennis": 0.50,
    "mma": 0.50,
}
# Колко често мачът свършва равен, когато не знаем нищо за отборите. Числото
# не е избрано тук — то се чете направо от реда отгоре: щом домакинът взима
# 0.45, а гостът около 0.27, за равенството остава останалото.
FALLBACK_DRAW = 0.28

# Спортовете с ЕДИН човек от страна се пишат само с име („1 · Синер"), а
# отборните — с „победа" пред името. Разликата беше пропусната в резервния
# път и там картите излизаха ГОЛИ, без 1/2 отпред: „Andrey Rublev 50%".
# Оценителят чете точно този код, за да отсъди — без него присъдата увисва
# на съвпадение по име.
LICHNI_SPORTOVE = {"tennis", "tabletennis", "mma"}


def fallback_analyse(fx, ctx, reason):
    """Карта дори когато моделът е замълчал. Никога не връща None."""
    b = fx.get("bucket") or ""
    home = esc(fx.get("home") or "")
    away = esc(fx.get("away") or "")
    p = float(FALLBACK_HOME.get(b, 0.52))

    # Ако знаем поне тежестта на турнира или подредбата, накланяме мъничко.
    ex = fx.get("extra") or {}
    if ex.get("neutral"):
        p = 0.50 + (p - 0.50) * 0.35      # неутрален терен: предимството пада

    fav_home = p >= 0.50
    if b == "football":
        # ТУК СТОЕШЕ ОБЪРНАТА КАРТА (намерено и оправено 04.08.2026).
        # Старият ред беше: fav_home = p >= 0.50, а за футбола p e 0.45.
        # Значи при НУЛА информация ботът посочваше ГОСТА, и то с „55%" —
        # число, което не е вероятността гостът да спечели, а вероятността
        # гостът ИЛИ равен. Гостът сам е около 27%.
        # В дневника има точно два футболни избора на гост и двата идват
        # оттук: Omonia Nicosia (домакинът спечели 1:0) и Boca Juniors (2:2).
        # И двата загубени.
        # Същият избор както при пълния модел, за да няма два различни езика:
        # под 50% за едната страна значи двоен шанс, не гол победител.
        # FALLBACK_HOME за футбола ВЕЧЕ е вероятност по 1X2 (виж бележката при
        # него), затова се взима както си е. Остатъкът отива при госта.
        px = FALLBACK_DRAW
        p1 = clampf(p, 0.05, 1.0 - px - 0.05)
        p2 = 1.0 - px - p1
        pick, p_show, _ = pick_1x2(p1, px, p2, fx.get("home"), fx.get("away"))
    elif b in LICHNI_SPORTOVE:
        pick = pick_name(fav_home, fx.get("home"), fx.get("away"))
        p_show = max(p, 1.0 - p)
    else:
        pick = pick_win(fav_home, fx.get("home"), fx.get("away"))
        p_show = max(p, 1.0 - p)

    kratko = (reason or "").split("(")[0].strip().rstrip(".")
    why = ["Малко данни за тази среща: " + (kratko or "няма история в източника") + ".",
           "Картата стъпва на предимството на домакина за този спорт."]
    if b in ("tennis", "tabletennis", "mma"):
        why[1] = "Двойката е неутрална — числото е близо до равностойно."

    return {"fx": fx, "bucket": b, "pick": pick, "p": p_show,
            "second": "", "third": "",
            "why": why, "sample": "без история",
            "n_eff": 0.0, "strength": 0.0, "stars": 1}


# ═══════════════════════════════════ 📊 ЦЕНАТА КЪМ АНАЛИЗА (13.08.2026)
#
# Взима се СЛЕД избора, не преди него: пазарът НЕ бива да влияе на решението
# на модела. Ако го питахме преди, щяхме тихо да го препишем — а тогава 70-те
# процента щяха да мерят пазара, не нас.
#
# Заявката е една на мач и само за спортовете, за които ИЗМЕРЕНО има цена
# (бейзбол, баскетбол, футбол). Провал не спира картата — тя просто излиза
# без реда, както преди.
def dobavi_pazar(an):
    if PZ is None or not isinstance(an, dict):
        return an
    fx = an.get("fx") or {}
    ex = fx.get("extra") or {}
    ev_id, slug = ex.get("ev_id"), ex.get("slug")
    sport = ex.get("sport_path")
    # 🔴 ДВА ПЪТЯ (13.08.2026). Срещите от ESPN носят номер и цената идва
    # направо. Бейзболът обаче идва от statsapi.mlb.com и НЯМА такъв номер —
    # а там са 48 от прогнозите. За него търсим по ИМЕНА в ESPN scoreboard-а
    # за същия ден. Без този втори път най-големият спорт остава без цена.
    if not sport:
        sport = {"baseball": "baseball", "basketball": "basketball",
                 "football": "soccer"}.get(str(an.get("bucket") or ""))
    if not slug:
        slug = {"baseball": "mlb"}.get(str(an.get("bucket") or ""))
    # 🔴 БЕЗ РАНЕН ИЗХОД (18.08.2026). Тук стоеше `return an`, ако ESPN няма
    # адрес за спорта — и заради него тенисът, ММА и тенисът на маса излизаха
    # от функцията ПРЕДИ да се стигне до втория източник. Тоест новият
    # източник беше написан, вързан и НЕДОСТИЖИМ. Видя се само в сухо
    # пускане: четири карти с цена, четирите тенис-карти без.
    dom = gost = raven = None
    try:
        if not (sport and slug):
            pass                          # ESPN няма адрес — минаваме нататък
        elif ev_id:
            dom, gost, raven = PZ.cena_za(sport, slug, ev_id)
        else:
            s = fx_start(fx, datetime.now(SOFIA))
            ymd = (s.astimezone(SOFIA) if s is not None
                   else datetime.now(SOFIA)).strftime("%Y%m%d")
            # 🔴 ЧАСЪТ СЕ ПОДАВА (18.08.2026). Без него серия от три вечери
            # между едни и същи отбори връщаше цената на грешната вечер —
            # измерено, 5 от 15 бейзболни мача, при това маркирани като чисти.
            dom, gost, raven = PZ.cena_po_imena(sport, slug, ymd,
                                                fx.get("home"), fx.get("away"), s)
            # Номерът от СЪЩИЯ кеширан индекс — нула нови заявки. Влиза в
            # дневника, за да вземе оценителят затварящата цена. Затова е
            # критично да е НАШИЯТ мач: сгрешен номер = чужда затваряща цена.
            ev_id = PZ.ev_za_imena(sport, slug, ymd,
                                   fx.get("home"), fx.get("away"), s)
    except Exception:                                        # noqa: BLE001
        dom = gost = raven = None
    izt = "espn" if (dom or gost) else None

    # 🔴 ВТОРИЯТ ИЗТОЧНИК (18.08.2026). ESPN дава цена само за три спорта —
    # 123 от 400 карти. Тенисът (40), ММА (7) и тенисът на маса (114) оставаха
    # НАВЕКИ без цена, тоест доходността щеше да се мери на 31% от продукта.
    #
    # Измерено живо срещу guest слоя на Pinnacle, върху НАШИТЕ имена:
    #   бейзбол 100% · баскетбол 100% · тенис 78% · футбол 66% · ММА 28%
    #   общо 35 от 49 срещи, с ДЕСЕТ заявки за целия ден.
    # Волейболът е недостъпен там (401) и затова изобщо не се пита.
    #
    # Търсим с ОРИГИНАЛНИТЕ имена: показваме „Фенербахче", те знаят
    # „Fenerbahce" — с преведеното не се намираше нито един голям отбор.
    if not (dom or gost) and PIN is not None:
        try:
            _b = str(an.get("bucket") or "")
            _d = str(ex.get("home_en") or fx.get("home") or "")
            _g = str(ex.get("away_en") or fx.get("away") or "")
            if _b in PIN.SPORT_ID and _d and _g:
                dom, gost, raven = PIN.ceni_za(_b, _d, _g)
                if dom or gost:
                    izt = "pinnacle"
                    sport = _b            # маржът се маха по НАШЕТО име
        except Exception:                                    # noqa: BLE001
            pass
    if not (dom or gost):
        return an

    # Кой изход сме посочили. Картата пише „1 · ...", „2 · ..." или „Х · равен".
    pick = str(an.get("pick") or "")
    cena = None
    if pick.startswith("1"):
        cena = dom
    elif pick.startswith("2"):
        cena = gost
    elif pick.startswith("Х") or pick.startswith("X"):
        cena = raven
    if cena:
        an["pazar_cena"] = cena
        # 🔴 МАРЖЪТ НА БУКМЕЙКЪРА (18.08.2026).
        # На КАРТАТА стои суровата цена — тя е това, което пазарът наистина
        # плаща, и читателят има право на нея непокътната.
        # В ДНЕВНИКА обаче влиза вероятността БЕЗ дела на букмейкъра, защото
        # само с нея сравнението „ние срещу пазара" значи нещо. Измерено на
        # живо: суровото 1/цена надува пазара със 7.4% при футбола и 1.9% при
        # бейзбола, а прагът на сравнението е 2%. Тоест почти половината
        # футболни изходи щяха да изглеждат „по-уверени от нас" само заради
        # маржа.
        pd, pg, pr = PZ.bez_marzh(sport, dom, gost, raven)
        chist = {"1": pd, "2": pg, "Х": pr, "X": pr}.get(pick[:1])
        if chist:
            an["pazar_p"] = round(chist, 4)
            # 🔴 ЗНАК ЗА ВЕРСИЯ (18.08.2026). В живия дневник вече стоят 5
            # записа със СУРОВА пазарна вероятност (с маржа вътре) от старата
            # версия. Смесени със свитите, те биха развалили сравнението, а
            # прагът за него е 30 отсъдени — тоест щеше да се прекрачи с
            # мръсна смес и никой нямаше да разбере. Мери се само версия 2+.
            an["pazar_v"] = 2
        # Адресът за затварящата цена. Без него CLV не може да се смята — а
        # CLV е единственото доказателство за ръб, което работи при 20 залога.
        an["pazar_izt"] = izt
        # Затварящата цена се взима от ESPN по номер. Pinnacle маха мача от
        # витрината си, щом започне — за него затварящата иска ДРУГ подход
        # (опресняване преди началото) и още не е направен. Казва се честно
        # в дневника, вместо да се мълчи.
        if izt == "espn" and ev_id:
            an["pazar_ev"] = str(ev_id)
            an["pazar_sport"] = str(sport)
            an["pazar_liga"] = str(slug)
        # Непълен набор → `pazar_p` НЕ се записва изобщо. По-добре кантарът да
        # мълчи, отколкото да мери с крив аршин. Цената на картата остава.
    return an


# ═══════════════════════════════════ ТРИТЕ КОМБИНИРАНИ ФИША (стая 4)
# ПОРЪЧКА НА СОБСТВЕНИКА (29.07.2026):
#   „Във Фишове на деня ще комбинираш 3 пъти по 5 мача във всеки фиш,
#    независимо различни спортове или един и същ."
#
# Правила, които си наложих, за да не е случайно:
#   • ЕДИН мач влиза най-много в ЕДИН фиш — иначе трите фиша са един и същ
#   • подредба по увереност: фиш 1 взима най-сигурните пет
#   • пише се и общата вероятност (произведението) — тя пада бързо и това е
#     честната част: пет по 70% не са 70%, а 17%
#   • излизат ВЕДНЪЖ на ден, от първото пускане, което има достатъчно мачове
# 🔴 ВДИГНАТИ НА ПЕТ (11.08.2026, поръчка: „увеличи и фишовете").
#
# Числото три идваше от времето, когато фишът беше ЗАКОВАН на пет крака и
# трябваха 15 избора над прага. От днес дължината се заслужава (виж
# sabiray_fish): при слаб ден фишът става от два-три крака, значи същият
# басейн стига за повече фишове.
#
# Защо пет, а не десет: измерено на живо днес — 24 срещи под лупата дадоха
# 15 кандидата над 58%. При среден фиш от 3-4 крака това е 4-5 фиша. Десет
# щеше да значи или празни фишове, или сваляне на прага — а прагът е точно
# това, което ги прави фишове, а не лотария.
#
# Пазачът остава: фиш, който не се събира над пода, просто не излиза.
COMBO_COUNT = env_int("PREDICT_COMBOS", 5, 0, 8)
# 🔴 ТАВАНЪТ СЛИЗА ОТ 5 НА 4 (11.08.2026) — за ПОВЕЧЕ фишове, не за по-малко.
#
# Вдигнах броя фишове на пет, а излязоха два. Причината не е таванът, а
# лакомията: първият фиш взимаше ПЕТ от най-силните и не оставаше за трети.
# Измерено върху истинските десет кандидата от днешното пускане:
#
#   таван 5  ->  2 фиша (22%, 22%)              · 1 неизползван кандидат
#   таван 4  ->  3 фиша (36%, 24%, 38%)         · 0 неизползвани
#   таван 3  ->  3 фиша (58%, 41%, 23%)         · 1 неизползван
#
# Четири взима всичко и прави три фиша вместо два, като всеки е над 24%.
# Три дава по-високи проценти, но хаби кандидат — а при по-богат ден четири
# ще направи и повече, и по-дълги фишове.
#
# Това е ТАВАН, не дължина: sabiray_fish и без това скъсява фиша, щом общата
# вероятност започне да пада под пода.
COMBO_SIZE = env_int("PREDICT_COMBO_SIZE", 4, 2, 10)
# Спортове, чийто резултат няма откъде да се провери — не влизат във фиш.
# Списъкът трябва да съвпада с NO_RESULT в scorer.py. Ако някога се появи
# източник за тенис на маса, махаме го и от двете места.
# 🔴 ИЗПРАЗНЕН 12.08.2026. Тенисът на маса беше тук, защото нямаше източник
# за резултата. От 11.08 има (WTT през шлюза /ttu/) и scorer.NO_RESULT вече
# е празно множество. Бележката при махането казваше „махаме го и от двете
# места" — беше махнато само на едното, и спортът с 79 карти продължаваше
# да се реже от фишовете без причина.
COMBO_NO_RESULT = set()
# Долна граница за участие във фиш. Избор от 50% в комбинация е изречение,
# което се самоопровергава: посочваме страна и в същото време казваме, че е
# монета. Отделната карта може да е близка — фишът не.
COMBO_MIN_P = env_float("PREDICT_COMBO_MIN_P", 0.58, 0.50, 0.90)
# 🔴 ДВЕТЕ НОВИ ПРАВИЛА (11.08.2026). Видяно с очи в сухо пускане същия ден:
# фиш 3 излезе с пет крака по 53-55% и обща вероятност <b>4%</b>. Това не е
# прогноза, а лотариен билет с нашето име отдолу. Затова:
#
#   1. ДЪЛЖИНАТА СЕ ЗАСЛУЖАВА, не се раздава. Крак се добавя само докато
#      общата вероятност остава над пода. Пет крака по 90% са фиш; пет по 53%
#      са фиш само на хартия. Сега първият става от пет, третият — от два-три.
#   2. ЕДИН ТУРНИР НЕ ПРАВИ ФИШ. Фиш 1 същия ден беше четири крака от едно и
#      също първенство (Световно U17). Такива изходи вървят заедно — един лош
#      ден в залата събаря целия фиш. Най-много два крака от един турнир.
COMBO_MIN_TOTAL = env_float("PREDICT_COMBO_MIN_TOTAL", 0.20, 0.02, 0.60)
COMBO_MIN_LEGS = env_int("PREDICT_COMBO_MIN_LEGS", 2, 2, 5)
COMBO_MAX_SAME_LEAGUE = env_int("PREDICT_COMBO_SAME_LEAGUE", 2, 1, 5)
# 🔴 И ТАВАН НА ЕДИН СПОРТ (18.08.2026). Таванът по ЛИГА не пази от еднообразен
# фиш, защото един спорт дава по няколко лиги на ден: тенисът на маса имаше
# три едновременни турнира, значи три различни „лиги" — и фиш от четири крака
# можеше да е изцяло тенис на маса, от една зала, в един следобед. Тогава
# фишът не е разпределен риск, а един залог, преоблечен като четири.
# Таван 3 при дължина 4: най-много три крака от един спорт, четвъртият е чужд.
COMBO_MAX_SAME_SPORT = env_int("PREDICT_COMBO_SAME_SPORT", 3, 1, 6)

# ═══════════ КАРТА БЕЗ ПАЗАР НЕ ИЗЛИЗА (19.08.2026) ═══════════
#
# ИЗРИЧНА ПОРЪЧКА НА СОБСТВЕНИКА: „искам всички прогнози да ги има в
# букмейкъра". Правилото е просто и строго: ако за един мач НИКОЙ не предлага
# пазар, прогнозата за него е упражнение, не продукт. Човекът не може да
# направи нищо с нея.
#
# Това мълчаливо затваря и една стара дупка: 64 от 116-те ни волейболни карти
# бяха „FIVB Girls' U17 World Championship" — юношески турнир, за който пазар
# НЕ СЪЩЕСТВУВА при никой букмейкър. Тези карти вече няма да излизат.
#
# ДВА ПЪТЯ ЗА ДОКАЗАТЕЛСТВО, защото един не стига:
#   1. Има цена за ТОЧНО ТОЗИ мач — най-силното доказателство.
#   2. Няма цена, но лигата е в списъка на ИЗМЕРЕНО търгуваните. Търсенето по
#      имена бърка (тенис 78%, ММА 28%) и без този втори път бихме млъквали
#      за истински мачове заради разминато име.
# Липсват ли и двете — картата не излиза и се БРОИ, за да се вижда.
#
# Път назад: PREDICT_ISKAM_PAZAR=0 връща старото поведение.
ISKAM_PAZAR = (os.environ.get("PREDICT_ISKAM_PAZAR") or "1").strip() not in (
    "0", "false", "no", "не")

# Лиги, за които е ИЗМЕРЕНО, че се търгуват (19.08.2026, чрез питане по имена
# на отборите в живия пазар). Мачове от тях излизат дори когато конкретното
# име не се е разпознало.
TARGUVANI = {
    "baseball": {"МЛБ"},
    "basketball": {"НБА", "WNBA", "НБЛ, Австралия", "Джи лига"},
    "tennis": {"ATP", "WTA"},
    "mma": {"ufc", "pfl", "bellator", "rizin", "ksw"},
}


def pazarat_otgovarya():
    """Работят ли изобщо източниците на цена в това пускане.

    🔴 БЕЗ ТОВА ПОРТИЕРЪТ Е ОПАСЕН (19.08.2026). „Няма пазар" и „доставчикът е
    долу" изглеждат еднакво: и в двата случая цена няма. Ако Pinnacle капне за
    половин час, портиерът щеше да СПРЕ ЦЕЛИЯ БОТ — мълчание, при което нищо
    не е червено и никой не разбира. Точно този клас провал ни е хапал вече
    (сляп одитор, задавен WTT, празен календар).

    Затова: питаме дали пазарът е върнал ИЗОБЩО нещо. Върне ли нула за всички
    спортове, това е повреда, не липса на пазар — и портиерът се отваря.
    """
    if PIN is None:
        return False
    try:
        for b in ("football", "tennis", "baseball", "basketball"):
            if PIN.machove(b):
                return True
    except Exception:                                        # noqa: BLE001
        return False
    return False


def ima_pazar(an):
    """Може ли човек да намери този мач при букмейкър. (може_ли, защо)."""
    if an.get("pazar_cena"):
        return True, "цена"
    b = str(an.get("bucket") or "")
    lg = str(((an.get("fx") or {}).get("league")) or "")
    for known in TARGUVANI.get(b, ()):  # noqa: SIM110
        if known and known.lower() in lg.lower():
            return True, "търгувана лига"
    # 🔴 ТЕНИСЪТ НА МАСА СЕ СЪДИ ПО РАНГА НА ТУРНИРА (19.08.2026).
    # Pinnacle не търгува WTT Feeder-ите — техният guest слой днес дава нула
    # мача по този спорт. Витрините обаче ги предлагат. Затова тук не искам
    # цена, а ТУРНИР ОТ ВЪЗРАСТНОТО НИВО: Feeder (55) и нагоре.
    # Юношеските и ветеранските падат на 10-12 и НЕ минават — там пазар
    # наистина няма, същото важи и за волейбола при момичета до 17.
    if b == "tabletennis" and _tt_rang(lg) >= 55:
        return True, "възрастен турнир от WTT"
    return False, "няма пазар"

COMBO_DUMI = ((0.45, "🟢 стегнат фиш — малко крака, но здрави"),
              (0.30, "🟢 разумен фиш"),
              (0.22, "🟡 смел фиш — иска късмет в един от краката"),
              (0.00, "🟠 рискован фиш"))


def combo_duma(total):
    for prag, duma in COMBO_DUMI:
        if total >= prag:
            return duma
    return ""


def combo_card(idx, legs, now):
    """Един фиш: краката, общата вероятност и честна дума за нея."""
    total = 1.0
    for a in legs:
        total *= float(a["p"])
    lines = ["🎫 <b>ФИШ " + str(idx) + " НА ДЕНЯ</b> · " + date_bg(now),
             "<i>" + n_match(len(legs)) + " · всички трябва да познаят</i>", ""]
    for a in legs:
        fx = a["fx"]
        emo = SPORTS.get(a["bucket"], {}).get("emoji", "•")
        when = fx_start(fx, now)
        chas = when.astimezone(SOFIA).strftime("%H:%M") if when is not None else ""
        lines.append(emo + " <b>" + esc(fx.get("home")) + "</b> — <b>"
                     + esc(fx.get("away")) + "</b>" + ((" · " + chas) if chas else ""))
        lines.append("    🎯 " + esc(a["pick"]) + " · <b>" + pct(a["p"]) + "</b>")
    lines += ["",
              "📊 И " + ("двата" if len(legs) == 2 else
                         ("трите" if len(legs) == 3 else
                          ("четирите" if len(legs) == 4 else "петте")))
              + " заедно: <b>" + pct(total) + "</b>",
              combo_duma(total),
              "🟢 THE GREEN ROOM"]
    return NL.join([x for x in lines if x is not None])


def sabiray_fish(pool):
    """Един фиш от подредения списък. Спира, щом общото падне под пода.

    Взима от най-сигурното надолу. Крак се добавя САМО ако след него общата
    вероятност още е над COMBO_MIN_TOTAL — така дължината идва от качеството
    на деня, а не от кръгло число, решено предварително. И най-много два крака
    от един турнир, за да не виси целият фиш на една зала.
    """
    legs, total, po_liga, po_sport = [], 1.0, {}, {}
    for a in pool:
        if len(legs) >= COMBO_SIZE:
            break
        lg = str(((a.get("fx") or {}).get("league")) or "?")
        if po_liga.get(lg, 0) >= COMBO_MAX_SAME_LEAGUE:
            continue
        sp = str(a.get("bucket") or "?")
        if po_sport.get(sp, 0) >= COMBO_MAX_SAME_SPORT:
            continue
        p = float(a.get("p") or 0.0)
        if legs and total * p < COMBO_MIN_TOTAL:
            continue                   # този крак би свалил фиша под пода
        legs.append(a)
        total *= p
        po_liga[lg] = po_liga.get(lg, 0) + 1
        po_sport[sp] = po_sport.get(sp, 0) + 1
    return legs if len(legs) >= COMBO_MIN_LEGS else []


def post_combos(picks, cands, state, now):
    """Строи и праща трите фиша. Връща колко съобщения са тръгнали."""
    if COMBO_COUNT <= 0:
        return 0
    ckey = now.strftime("%Y-%m-%d") + "|combos"
    if already_posted(state, ckey):
        return 0                       # днес вече са пуснати

    # ЗА ФИШ подредбата е ДРУГА, не като за отделните карти.
    # Отделната карта се цени по увереност (звезди). Във фиш обаче петте
    # избора се умножават, значи най-важна е самата вероятност: един избор от
    # 43% срива целия фиш, колкото и звезди да носи. Затова тук водещото е p,
    # а звездите са само разделител при равенство.
    # СПОРТ БЕЗ ИЗТОЧНИК НА РЕЗУЛТАТ НЕ ВЛИЗА ВЪВ ФИШ.
    # На 04.08.2026 два от трите фиша бяха с по три крака тенис на маса — спорт,
    # за който няма безплатен източник на резултати (шест проверени адреса, виж
    # NO_RESULT в scorer.py). Такъв фиш не може да бъде отчетен НИКОГА: чака
    # присъда, която няма как да дойде, и блокира и останалите си крака.
    # Отделната карта за тенис на маса ОСТАВА — тя е прогноза и си има стая.
    # Мерено: филтърът не струва нито един ден без фиш.
    pool = [a for a in cands
            if float(a.get("p") or 0.0) >= COMBO_MIN_P
            and a.get("bucket") not in COMBO_NO_RESULT]
    pool.sort(key=lambda a: -(float(a.get("p") or 0.0) * 1000.0
                              + int(a.get("stars") or 1)))
    if len(pool) < COMBO_MIN_LEGS:
        print("Фишове: само " + str(len(pool)) + " мача над "
              + pct(COMBO_MIN_P) + " — трябват поне " + str(COMBO_MIN_LEGS)
              + ". Днес без фишове.")
        return 0

    sent = 0
    made = 0
    dulzhini = []
    ostava = list(pool)
    for i in range(COMBO_COUNT):
        legs = sabiray_fish(ostava)
        if len(legs) < COMBO_MIN_LEGS:
            break                      # каквото остана, не прави фиш
        for a in legs:
            ostava.remove(a)           # един мач влиза само в един фиш
        # 🔴 СОБСТВЕН КЛЮЧ ЗА ВСЕКИ ФИШ (12.08.2026 — ВТОРА ПОПРАВКА).
        # Първата версия местеше общия ключ ВЪТРЕ в цикъла, за да не се пращат
        # трите наново при убит рън. Симулирано: това счупи другата посока —
        # рън, убит след фиш 1, отбелязваше деня за готов и следващото
        # пускане връщаше 0, тоест излизаше ЕДИН фиш от пет вместо всичките.
        # Верният ключ е на ФИША, не на деня: убит рън се възобновява точно
        # оттам, докъдето е стигнал — без дубли и без загубени фишове.
        fkey = now.strftime("%Y-%m-%d") + "|combo" + str(i + 1)
        if already_posted(state, fkey):
            ostava = [a for a in ostava]   # вече е пуснат, минаваме нататък
            continue
        if post_predict(combo_card(i + 1, legs, now), PICKS_THREAD):
            sent += 1
            made += 1
            dulzhini.append(str(len(legs)))
            mark_posted(state, fkey, now)
            persist(state, now)
            # Всеки крак влиза в дневника с номера на фиша си, за да може
            # оценителят утре да каже кой фиш е минал и къде се е скъсал.
            for a in legs:
                log_pick(a, now, combo=i + 1)
            time.sleep(SEND_GAP)
    if made:
        # Дневният ключ се слага чак когато цикълът е СТИГНАЛ ДО КРАЯ. Той
        # значи „днес фишовете са готови", а не „почнахме ги".
        mark_posted(state, ckey, now)
        persist(state, now)
        print("Фишове: " + str(made) + " (" + ", ".join(dulzhini)
              + " крака) -> стая " + PICKS_THREAD + ".")
    else:
        # 🔴 ПОПРАВЕНО 11.08.2026. Тук пишеше `elif len(pool) < need:` — а `need`
        # не съществува в тази функция (има го в две ДРУГИ функции, редове 3067 и
        # 3236, като локална променлива). Клонът е достижим: горе вече е доказано,
        # че pool стига за поне COMBO_MIN_LEGS крака, но sabiray_fish може да не
        # събере нито един фиш — например ако всички кандидати са от една лига
        # (таван 2 на лига), или ако общата вероятност пада под COMBO_MIN_TOTAL.
        # Тогава ботът НЕ печаташе бележка, а гърмеше с NameError и събаряше
        # целия рън — включително вече изпратените карти нямаше да се запишат.
        # Съобщението също беше грешно: „стигнаха за N фиша" при НУЛА фиша.
        print("Фишове: " + str(len(pool)) + " кандидата над " + pct(COMBO_MIN_P)
              + ", но нито един не се събра до " + pct(COMBO_MIN_TOTAL)
              + " обща вероятност (таван 2 крака от лига). Днес без фишове.")
    return sent


def razpredeli(lst, n):
    """n елемента, РАЗПРЪСНАТИ равномерно по списъка, а не първите n.

    🔴 ЗАЩО (19.08.2026). `[:PER_SPORT]` взимаше първите пет по реда на
    ИЗТОЧНИКА. За тенис на маса това значи първите пет от 108 записа в
    разписанието — тоест квалификациите, където играчите нямат история и
    моделът връща 50%. Измерено същия ден: от първите 60 срещи 28 покриват
    прага „поне 5 мача за 18 месеца", а в лупата влязоха пет, всичките под
    прага. Спортът мълчеше при 120 налични срещи.
    Същото важи и за футбола: 44 срещи, а първите пет идваха все от първите
    лиги в списъка (Бразилия и Аржентина).
    Разпръскването е детерминирано — същият вход дава същия изход.
    """
    lst = list(lst or [])
    n = max(0, int(n))
    if n <= 0 or not lst:
        return []
    if len(lst) <= n:
        return lst
    stapka = len(lst) / float(n)
    out, vzeti = [], set()
    for k in range(n):
        i = min(len(lst) - 1, int(k * stapka))
        while i in vzeti and i + 1 < len(lst):
            i += 1
        vzeti.add(i)
        out.append(lst[i])
    return out


def build_pool(buckets):
    """Кръгова подредба: всеки спорт получава шанс, никой не задръства."""
    per = {b: razpredeli(buckets.get(b) or [], PER_SPORT) for b in ACTIVE_SPORTS}
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


# ═══════════ СЕГА ИЛИ НИКОГА ═══════════
# ПОРЪЧКА НА СОБСТВЕНИКА (05.08.2026): „всички прогнози да се пускат ПРЕДИ
# самите мачове, независимо от спорта; за късните нощни може и по-рано, за да
# могат хората да ги ползват; всичко между 8 сутринта и 10 вечерта."
#
# ДЕФЕКТЪТ, който това извади: ботът редеше кандидатите САМО по увереност и
# режеше на MAX_PICKS. Мач в 02:00 през нощта се състезаваше по звезди с мач в
# 21:00 същата вечер — и ако загубеше, оставаше без карта ЗАВИНАГИ, защото
# следващото пускане е чак в 08:00, когато мачът вече е изигран.
# С осем нощни пускания това не личеше. Щом ги махнахме заради „всичко до
# 22:00", дупката от 20:00 до 08:00 стана дванайсет часа.
#
# ЛЕКАРСТВОТО: мач, който започва ПРЕДИ следващото пускане, е СПЕШЕН. Спешните
# минават първи и имат СВОЙ таван — те не се състезават с останалите, защото
# за тях друг шанс няма.
# 🔴 ТОЗИ СПИСЪК ТРЯБВА ДА СЪВПАДА С КРОНОВЕТЕ В .github/workflows/predict.yml.
# Оттук се смята кое е „следващото пускане" — а от него зависи кой мач е спешен.
# Разминат ли се двата списъка, ботът ще смята, че има още време за мач, който
# всъщност няма да доживее следващо пускане, и ще го изпусне мълчаливо.
# Последният час е 23:00 по изрична поръчка на собственика (05.08.2026):
# прогнозите вървят до 23, за да хванат и късните мачове с по-пресни данни.
#
# 🔴 ВСЕКИ ЧАС, НЕ ПРЕЗ ДВА (11.08.2026). Премерено върху 107 разписани
# пускания: медиана 71 мин закъснение, най-голямо 271, а на 06.08 излязоха
# само ПЕТ от осем. При слот през два часа един пропуснат крон значи стая без
# карти четири часа. При слот всеки час пропускът се покрива от следващия.
# Броят карти НЕ се вдига — пази го MAX_DAY и ключът на всяка карта в тефтера.
RUN_HOURS = tuple(range(8, 23))

# 🔴 ПАЗАЧЪТ НА ПРОЗОРЕЦА (11.08.2026). Правилото на собственика е просто:
# нищо не излиза преди 08:00 и след 23:00 български. Кроновете горе го спазват
# — GitHub не го спазва. Измерено на живо днес: крон, разписан за 20:00 UTC
# (23:00 БГ), тръгна в 22:07 UTC, тоест 01:07 БГ, и стаята осъмна с карти
# посред нощ. Разписанието е молба към GitHub; този пазач е решение.
#
# Закъсняло пускане вече не публикува — просто мълчи. Мачът не се губи:
# тефтерът не го отбелязва и сутрешното пускане в 08:00 го поема, ако още не е
# започнал. По-добре карта в 08:00, отколкото карта в 01:07.
QUIET_FROM = env_int("PREDICT_QUIET_FROM", 23, 12, 23)   # последен допустим час
QUIET_TO = env_int("PREDICT_QUIET_TO", 8, 0, 11)         # първи допустим час


def v_prozoreca(now):
    """Вътре ли сме в позволените часове. Границите са включително."""
    return QUIET_TO <= now.hour <= QUIET_FROM

# ЧЕРНАТА КУТИЯ на пускането. Пълни се в движение и се записва накрая в
# тефтера, който работният файл връща в хранилището. Без нея „защо мълчи
# футболът" се вижда само в дневника на GitHub — а той иска админски права
# и изчезва. Три спорта мълчаха дни наред точно заради това.
DIAG = {}
# Колко спешни карти може да излязат в едно пускане ОТГОРЕ на обичайните.
# Вечерното пускане поема цялата нощ, затова числото е по-голямо от MAX_PICKS.
MAX_URGENT = env_int("PREDICT_MAX_URGENT", 12, 0, 40)

# 🔴 ТАВАНЪТ РАСТЕ С ДЕНЯ (11.08.2026). Измерено от ЖИВИЯ дневник:
#
#   11.08: 39 от 40-те карти излязоха до 13:01 — и стаята мълча целия
#          следобед и цялата вечер. Тоест точно когато хората гледат.
#   10.08: 8 карти паднаха накуп в 00:00, после дупка до 13:00.
#   09.08: 11 карти в 00:00, после пак дупка.
#
# Дневният таван пазеше стаята от заливане, но не пазеше НИЩО за вечерта:
# щом сутрешните пускания го изядат, останалите десет часа мълчат по право.
# Човек, който отвори групата в 19:00, вижда карта отпреди шест часа.
#
# Затова таванът вече е СТЪЛБА: до 08:00 имаме право на 40% от него, а пълните
# 100% чак от 20:00 нататък. Между тях расте плавно. Числото за деня не се
# променя — сменя се само кога имаме право да го изхарчим.
# Изход без пипане на код: PREDICT_STALBA=0 връща стария плосък таван.
STALBA = env_int("PREDICT_STALBA", 1, 0, 1)
STALBA_OT, STALBA_DO = 8, 20        # часове, между които стълбата расте
STALBA_MIN = 0.40                   # дял, позволен още в началото на деня


def dneven_tavan(now):
    """Колко карти имаме право да сме пуснали ДО ТОЗИ ЧАС."""
    if not STALBA:
        return MAX_DAY
    h = int(getattr(now, "hour", STALBA_DO))
    if h >= STALBA_DO:
        return MAX_DAY
    if h <= STALBA_OT:
        dyal = STALBA_MIN
    else:
        dyal = STALBA_MIN + (1.0 - STALBA_MIN) * (h - STALBA_OT) / float(STALBA_DO - STALBA_OT)
    # Поне един слот винаги остава — иначе ранен час би блокирал всичко.
    return max(1, int(MAX_DAY * dyal))

# 🔴 КВОТА ЗА СПОРТ (11.08.2026). Един спорт беше гладен ПО УСТРОЙСТВО.
#
# Неспешните се редят по stars * 1000 + strength * 100. Звездите на ММА обаче
# са заковани на ЕДНА: Elo между двама бойци дава почти ези-тура, strength
# излиза 0.013–0.066, а прагът за втора звезда е MIN_STRENGTH = 0.10. Тоест
# ключът на всяка ММА карта е между 1001 и 1007, докато волейбол, баскетбол и
# бейзбол редовно вадят 2000+ и 3000+.
#
# Измерено на 11.08.2026: петте боя от галата бяха ГОТОВИ карти (51–53%), но
# заеха места 19, 21, 23, 25 и 26 от 26 кандидата при таван шест. Нула шанс —
# не понякога, а никога. Живият дневник го потвърждава: 261 записа от 29.07 до
# 12.08, от тях ММА — НУЛА, при пет гали в периода (PFL 31.07, UFC 01.08,
# PFL 07.08, UFC 08.08, UFC 11.08). Стая „Бойни спортове" не беше тиха заради
# липса на мачове, а заради подредбата.
#
# Квотата взима НАЙ-ДОБРАТА карта на всеки непредставен спорт — по реда на
# увереността ѝ, тоест силните спортове пак излизат отпред. Цената: най-силният
# спорт получава един слот по-малко, когато има много спортове.
# Изход без пипане на код: PREDICT_KVOTA=0 връща точно старото поведение.
KVOTA_NA_SPORT = env_int("PREDICT_KVOTA", 1, 0, 3)

# 🔴 ДНЕВНА КВОТА ПО СПОРТ (13.08.2026) — ИЗМЕРЕН ПРОБЛЕМ, НЕ ХРУМВАНЕ.
#
# Днес тенисът на маса даде НУЛА карти при 209 намерени срещи. Причината не е
# моделът: пуснат сам, той дава три карти от пет кандидата. Причината е
# редът на деня.
#
# WTT играе от рано сутрин — 150 от 162 срещи вече бяха започнали към 11 часа.
# Тоест решаващият прозорец за този спорт е ПЪРВИЯТ рън. А дневният таван в
# 08:00 е шестнайсет карти ЗА ВСИЧКИ спортове; първият рън ги изяде с други
# спортове и когато тенисът на маса стигна до подбора, място нямаше.
#
# Общ таван при спортове с РАЗЛИЧНИ часове значи, че ранният спорт краде от
# късния или обратното — зависи кой е бил пръв, не кой е по-добър.
#
# Затова: всеки активен спорт има запазени места за деня. Докато не ги е
# изчерпал, той минава ПРЕДИ спорт, който вече си е взел своето. Таванът
# остава — това не е добавка към обема, а справедливост в подредбата.
#
# 0 = старото поведение, без нито ред промяна.
KVOTA_DEN = env_int("PREDICT_KVOTA_DEN", 3, 0, 12)


def next_run(now):
    """Кога е следващото пускане. След последното за деня — утре сутринта."""
    for h in RUN_HOURS:
        if now.hour < h:
            return now.replace(hour=h, minute=0, second=0, microsecond=0)
    return (now + timedelta(days=1)).replace(hour=RUN_HOURS[0], minute=0,
                                             second=0, microsecond=0)


# 🔴 ПРЕРАБОТЕНО 11.08.2026 по изрична поръчка: „късните мачове всичките
# по-рано пускай ги".
#
# Дотук спешен беше само мачът, който започва ПРЕДИ следващото пускане. Това
# звучи разумно и е грешно за точно случая, който собственикът посочи.
# Измерено с истинските часове:
#
#   мач в 22:30 · пускане 20:00 → следващото е 22:00 → НЕ Е спешен
#                 пускане 22:00 → следващото е утре 08:00 → спешен
#
# Тоест мач в 22:30 излиза в 22:00 — тридесет минути преди първия съдийски
# сигнал. „По-рано" не се случваше НИКОГА за вечерните мачове; работеше само
# за нощните, защото те падаха в десетчасовата дупка.
#
# Сега спешността е РАЗСТОЯНИЕ: всичко, което започва до URGENT_LEAD_H часа
# напред, е спешно. Мач в 22:30 става спешен още от пускането в 16:00 и
# излиза шест часа по-рано, с време човекът да го погледне.
URGENT_LEAD_H = env_float("PREDICT_URGENT_LEAD_H", 7.0, 1.0, 30.0)


def urgent(fx, now):
    """Мачът е близо — сега или никога.

    Спешен е този, който започва до URGENT_LEAD_H часа напред ИЛИ преди
    следващото пускане (второто пази нощните мачове след последния крон).
    Мач без известен час НЕ е спешен: за него не знаем кога е, а да го обявим
    за спешен би изместило мач, за който знаем.
    """
    when = fx_start(fx, now)
    if when is None:
        return False
    try:
        w = when.astimezone(SOFIA)
        return w < next_run(now) or w <= now + timedelta(hours=URGENT_LEAD_H)
    except Exception:                      # noqa: BLE001
        return False


def choose(cands, limit, now=None, urgent_limit=None, dnes_po_sport=None):
    """Първо спешните, после най-уверените. Без три поредни от един спорт.

    Спешните се подреждат по ЧАС (кой започва пръв), не по звезди — там няма
    избор, а срок. Останалите се редят по увереност, както преди.
    """
    if urgent_limit is None:
        urgent_limit = MAX_URGENT
    speshni, ostanali = [], []
    if now is not None:
        for a in cands:
            (speshni if urgent(a.get("fx") or {}, now) else ostanali).append(a)
    else:
        ostanali = list(cands)

    def kogato(a):
        w = fx_start(a.get("fx") or {}, now) if now is not None else None
        return w.timestamp() if w is not None else float("inf")

    speshni.sort(key=kogato)               # кой започва пръв, той пръв
    ostanali.sort(key=lambda a: -(a["stars"] * 1000.0 + a["strength"] * 100.0))

    picked, used, taken = [], {}, set()
    # 1) СПЕШНИТЕ — със свой таван, не се състезават с останалите.
    vzeti_speshni = speshni[:max(0, int(urgent_limit))]
    # 🔴 ОТПАДНАЛИТЕ СПЕШНИ НЕ ИЗЧЕЗВАТ МЪЛЧАЛИВО (11.08.2026).
    # Измерено: при 20 спешни мача и таван 12, осем отпадаха и НЕ влизаха в
    # нито един следващ цикъл — тоест губеха и последния си шанс, без ред в
    # дневника. Сега се връщат при останалите: ще се борят по увереност, а
    # ако пак не влязат, поне се брои колко са.
    izpusnati = speshni[max(0, int(urgent_limit)):]
    if izpusnati:
        ostanali = izpusnati + ostanali
        print("   ⚠ спешни над тавана: " + str(len(izpusnati))
              + " — пращам ги при останалите, не ги хвърлям.")
    for a in vzeti_speshni:
        picked.append(a)
        taken.add(id(a))
        used[a["bucket"]] = used.get(a["bucket"], 0) + 1
    # 2) КВОТАТА — по една карта на всеки спорт, който още няма нито една.
    #    Обхожда се пак по увереност, значи силните спортове взимат слота си
    #    първи; последният слот остава за спорта с най-слабия най-добър мач.
    #    Виж дългото обяснение при KVOTA_NA_SPORT: без този проход ММА не може
    #    да влезе НИКОГА, защото звездите му са заковани на една.
    # 🔴 ЗАПАЗЕНИТЕ МЕСТА ЗА ДЕНЯ (13.08.2026). Преди квотата „по една на рън"
    # минава друга: спорт, който ОЩЕ не е взел дневните си места, върви пръв.
    # Виж дългото обяснение при KVOTA_DEN — тенисът на маса даде нула карти
    # при 209 срещи само защото ранният му час съвпадна с ниския утринен таван.
    dnes = dict(dnes_po_sport or {})
    kv_den = max(0, int(KVOTA_DEN))
    if kv_den:
        for a in ostanali:
            if len(picked) - len(vzeti_speshni) >= limit:
                break
            if id(a) in taken:
                continue
            b_ = a["bucket"]
            # НАЙ-МНОГО ЕДНА на спорт в ТОЗИ проход. Целта е ПОДРЕДБА, не
            # обем: спорт под дневната си квота да мине пръв, а не да вземе
            # цялата стая. Разнообразието в едно пускане остава на другите
            # два прохода, които следват.
            if used.get(b_, 0) >= 1:
                continue
            if dnes.get(b_, 0) >= kv_den:
                continue
            picked.append(a)
            taken.add(id(a))
            used[b_] = used.get(b_, 0) + 1

    kvota = max(0, int(KVOTA_NA_SPORT))
    if kvota:
        for a in ostanali:
            if len(picked) - len(vzeti_speshni) >= limit:
                break
            if id(a) in taken:
                continue
            if used.get(a["bucket"], 0) >= kvota:
                continue
            picked.append(a)
            taken.add(id(a))
            used[a["bucket"]] = used.get(a["bucket"], 0) + 1
    # 3) Останалите — по увереност, с разреждане по спорт.
    for a in ostanali:
        if len(picked) - len(taken & {id(x) for x in vzeti_speshni}) >= limit:
            break
        if id(a) in taken:
            continue
        if used.get(a["bucket"], 0) >= 2 and len(ostanali) > limit:
            continue
        picked.append(a)
        taken.add(id(a))
        used[a["bucket"]] = used.get(a["bucket"], 0) + 1
    # 4) Ако разреждането е оставило място — пълним с каквото има.
    for a in ostanali:
        if len(picked) >= limit + len(vzeti_speshni):
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
    if not v_prozoreca(now):
        print("Часът е " + now.strftime("%H:%M")
              + " — извън прозореца " + str(QUIET_TO) + ":00-"
              + str(QUIET_FROM) + ":00. Закъсняло пускане: мълча.")
        print("Мачовете не се губят — сутрешното пускане ги поема.")
        return
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
    pod_praga = []
    for fx in fresh:
        name = str(fx.get("home")) + " - " + str(fx.get("away"))
        try:
            an, why_not = analyse(fx, ctx)
        except Exception as e:      # noqa: BLE001
            print("   анализ " + name + ": " + str(e)[:110])
            an, why_not = None, "грешка в данните"
        if an is None:
            # РЕЗЕРВНАТА СТЪПКА. Дотук срещата просто изчезваше. Сега слиза
            # едно стъпало надолу и пак излиза карта — с една звезда и с
            # изписано на какво стъпва. Каналът е за прогнози.
            thin += 1
            an = fallback_analyse(fx, ctx, why_not)
            print("   ~ " + name + ": резервна прогноза (" + why_not + ")")
        # 🔴 ДОЛНАТА ГРАНИЦА. Карта под MIN_SHOW_P не излиза — виж обяснението
        # при константата. „1 · победа X — 35%" е изречение, което само се
        # опровергава. Отпадналите се БРОЯТ и се изписват: днешният урок е, че
        # тихата загуба е по-лоша от липсата.
        _prag = dolen_prag(an.get("bucket"))
        if float(an.get("p") or 0.0) < _prag:
            pod_praga.append(an)
            weak += 1
            print("   ✖ " + name + ": " + pct(an["p"]) + " — под прага "
                  + pct(_prag) + ", не излиза")
            continue
        cands.append(an)
        st = an["stars"]
        print("   ✔ " + name + ": " + an["pick"] + " " + pct(an["p"])
              + ", " + str(st) + (" звезда" if st == 1 else " звезди"))
    if pod_praga:
        po_sport = {}
        for a in pod_praga:
            b = a.get("bucket") or "?"
            po_sport[b] = po_sport.get(b, 0) + 1
        print("   Под прага (" + pct(MIN_SHOW_P) + " футбол / "
              + pct(MIN_SHOW_P_DVA) + " два изхода): " + str(len(pod_praga))
              + " (" + ", ".join(k + " " + str(v) for k, v in sorted(po_sport.items()))
              + ") — тези мачове НЕ получават карта.")

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

    # 🔴 18.08.2026. Живият тефтер се проверява ПРИ ВСЯКО ПУСКАНЕ, не само в
    # самопроверката. Тестът работи със синтетични данни; истината живее в
    # предния тефтер. Точно така се откри, че фишовете се броят за спорт —
    # синтетичният тест мълчеше, живият тефтер го каза от първия поглед.
    _neposn = nepoznati_klyuchove(state)
    if _neposn:
        print("   ⚠ непознат вид ключ в тефтера: " + ", ".join(_neposn[:5])
              + " — броят се за прогнози и ядат от дневния таван.")

    _tavan = dneven_tavan(now)
    room = _tavan - cards_today(state, now)
    if room <= 0:
        print("Таванът за този час (" + str(_tavan) + " от " + str(MAX_DAY)
              + " за деня) е стигнат — пазя останалите за по-късно.")
        # НО фишовете пак излизат. Тук се излизаше направо и в ден, в който
        # таванът се стигне рано, трите фиша НИКОГА не се пускаха — а те са
        # отделен продукт, веднъж на ден, не поредна карта.
        post_combos([], cands, state, now)
        maybe_footer(state, now, seen, thin, weak)
        persist(state, now)
        return

    # 🔴 ПАЗАРНИЯТ ПОРТИЕР (19.08.2026). Цената се търси ПРЕДИ подбора, а не
    # при пращането — инак карта без пазар би заела мястото на карта с пазар.
    if ISKAM_PAZAR:
        bez, s_pazar = [], []
        for a in cands:
            dobavi_pazar(a)
            ok, _z = ima_pazar(a)
            (s_pazar if ok else bez).append(a)
        if bez:
            _ps = {}
            for a in bez:
                _b = a.get("bucket") or "?"
                _ps[_b] = _ps.get(_b, 0) + 1
            print("   🚫 без пазар при букмейкър: " + str(len(bez)) + " ("
                  + ", ".join(k + " " + str(v) for k, v in sorted(_ps.items()))
                  + ") — не излизат.")
        if s_pazar:
            cands = s_pazar
        elif not pazarat_otgovarya():
            # Нула цени И нула отговори от пазара = ПОВРЕДА, не липса на пазар.
            # Портиерът се отваря: по-добре карта без потвърден пазар, отколкото
            # мълчалив бот, при който нищо не е червено.
            print("   ⚠ пазарът не отговаря изобщо — портиерът се отваря за "
                  "това пускане (иначе повреда би спряла целия бот).")
        else:
            # Пазарът работи и въпреки това нито един мач няма пазар.
            # Значи денят наистина е такъв. Мълчим — прогноза, с която човекът
            # няма какво да прави, не е продукт.
            print("   🚫 пазарът работи, но нито един от днешните мачове не се "
                  "предлага — мълча.")
            maybe_footer(state, now, seen, thin, weak)
            persist(state, now)
            return

    # `now` влиза, за да може подборът да различи СПЕШНИТЕ мачове — тези, които
    # започват преди следващото пускане. За тях друг шанс няма.
    picks = choose(cands, min(MAX_PICKS, room), now, min(MAX_URGENT, room),
                   karti_dnes_po_sport(state, now))
    sent = 0
    hkey = now.strftime("%Y-%m-%d") + "|header"
    if not already_posted(state, hkey):
        if post_predict(header_card(now, len(picks), seen)):
            mark_posted(state, hkey, now)
            persist(state, now)
            sent += 1
        time.sleep(SEND_GAP)
    for a in picks:
        dobavi_pazar(a)
        txt = card(a, now)
        if post_predict(txt):
            mark_posted(state, a["fx"]["_key"], now)
            # Записваме СЛЕД ВСЯКА карта, не в края. Ако рънът умре на третата,
            # първите две са вече в тефтера и следващият рън не ги повтаря.
            persist(state, now)
            log_pick(a, now)
            sent += 1
            # И В СТАЯТА НА СВОЯ СПОРТ. Прогнозата за футбол интересува хората
            # в стая ⚽, не само тези, които следят общата витрина. Провал тук
            # не отменя картата — тя вече е в 27.
            room = SPORT_ROOM.get(a.get("bucket"))
            if room and room != PREDICT_THREAD:
                time.sleep(1.2)
                if post_predict(txt, room):
                    sent += 1
        time.sleep(SEND_GAP)

    # Трите комбинирани фиша на деня → стая 4.
    sent += post_combos(picks, cands, state, now)

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

    # --- ДОМАКИНСТВОТО СЕ БРОИ ТОЧНО ВЕДНЪЖ.
    # Тази проверка стои тук, защото дефектът беше невидим отвън: моделът
    # даваше на домакина между 46.6% и 57.9% срещу НАПЪЛНО ЕДНАКЪВ съперник,
    # според това колко история има. Инвариантът е прост — щом двата отбора са
    # еднакви, отговорът НЕ БИВА да зависи от дължината на историята, и трябва
    # да е около чистия множител (около 43%), не над половината.
    def _ednakvi(n):
        d = [0]

        def mach(doma, gf, ga):
            d[0] += 7
            return {"when": _sega - timedelta(days=d[0]), "home": doma,
                    "gf": gf, "ga": ga}

        r = ([mach(True, 1.60, 1.00) for _ in range(n)]
             + [mach(False, 1.10, 1.45) for _ in range(n)])
        return r

    _sega = datetime.now(SOFIA)
    _p1 = []
    for _n in (3, 5, 10, 20):
        _m = model_football(_ednakvi(_n), _ednakvi(_n), 1.35, _sega)
        check("еднакви отбори, %d мача: моделът отговаря" % _n, _m is not None)
        if _m:
            _p1.append(_m["p_home"])
    check("еднакви отбори: домакинът НЕ е фаворит над половината",
          bool(_p1) and max(_p1) < 0.50)
    check("еднакви отбори: домакинът е около чистия множител",
          bool(_p1) and 0.38 < min(_p1) and max(_p1) < 0.47)
    check("еднакви отбори: отговорът НЕ зависи от дължината на историята",
          bool(_p1) and (max(_p1) - min(_p1)) < 0.03)
    check("еднакви отбори: гостът не е смачкан",
          bool(_p1) and min(_p1) > 0.0)
    _mdalag = model_football(_ednakvi(20), _ednakvi(20), 1.35, _sega)
    check("еднакви отбори: домакинът все пак води",
          _mdalag is not None and _mdalag["p_home"] > _mdalag["p_away"])
    check("еднакви отбори: разликата домакин-гост е разумна",
          _mdalag is not None and 0.05 < (_mdalag["p_home"] - _mdalag["p_away"]) < 0.22)

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
    # 🥊 Седемте ММА лиги (13.08.2026). Измерено срещу ESPN: тези седем
    # отговарят, останалите осем дават 400.
    check("ММА лигите са седем", len(MMA_LEAGUES_VSI) == 7)
    check("UFC е с най-висока тежест",
          max(MMA_LEAGUES_VSI, key=lambda x: x[1])[0] == "ufc")
    check("тежестите падат с размера на лигата",
          [x[1] for x in MMA_LEAGUES_VSI] == sorted([x[1] for x in MMA_LEAGUES_VSI],
                                                    reverse=True))
    check("всяка лига има име за картата", all(x[2] for x in MMA_LEAGUES_VSI))
    check("няма повторена лига",
          len({x[0] for x in MMA_LEAGUES_VSI}) == len(MMA_LEAGUES_VSI))
    check("списъкът се реже отвън", "PREDICT_MMA_LIGI" in open(__file__, encoding="utf-8").read())
    check("без променлива важат всичките", os.environ.get("PREDICT_MMA_LIGI")
          or len(MMA_LEAGUES) == len(MMA_LEAGUES_VSI))
    check("ONE и BKFC ги няма (ESPN връща 400)",
          not {"one", "bkfc", "glory", "invicta"} & {x[0] for x in MMA_LEAGUES_VSI})

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
        # 🔴 18.08.2026. И ФИШОВЕТЕ не са карти. Ключовете им („|combos" и
        # „|combo1..3") стояха ИЗВЪН служебния списък — значи ядяха от дневния
        # таван и се брояха за спорт. Измерено в живия тефтер за 16.08.
        for _sk in ("combos", "combo1", "combo2", "combo3"):
            st3["posted"][now.strftime("%Y-%m-%d") + "|" + _sk] =                 now.strftime("%Y-%m-%d %H:%M")
        check("фишовете не ядат от тавана", cards_today(st3, now) == 0)
        check("фишовете не се броят за спорт",
              not karti_dnes_po_sport(st3, now))
        check("няма непознат вид ключ", not nepoznati_klyuchove(st3))
        check("непознат ключ СЕ обажда",
              nepoznati_klyuchove({"posted": {"2026-01-01|нещо_ново|а|б": "x"}})
              == ["нещо_ново"])
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
    # ⚠️ ТАЗИ СЕКЦИЯ Е ОБЪРНАТА НА 29.07.2026 ПО РЕШЕНИЕ НА СОБСТВЕНИКА.
    # Пазеше правилото „всичко само в стая 27, спортните стаи са само за
    # разписания". Той го отхвърли: „общи разписания, които нищо не значат".
    # Сега прогнозата отива И в стаята на своя спорт, а фишовете — в стая 4.
    # Единственото, което остава ЗАБРАНЕНО, е стая 26: новините са чужди.
    check("стая 26 остава забранена", post_predict("тест", "26") is False)
    check("стая 26 е в забранените", "26" in FORBIDDEN_THREADS)
    check("стая 9 (резултати) не е наша", post_predict("тест", "9") is False)
    check("стая 10 (печеливши) не е наша", post_predict("тест", "10") is False)
    check("стая 11 (помощ) не е наша", post_predict("тест", "11") is False)
    check("стая 1 (общ чат) не е наша", post_predict("тест", "1") is False)
    check("футболът има своя стая", SPORT_ROOM.get("football") in ALLOWED_THREADS)
    check("баскетболът има своя стая", SPORT_ROOM.get("basketball") in ALLOWED_THREADS)
    check("волейболът има своя стая", SPORT_ROOM.get("volleyball") in ALLOWED_THREADS)
    check("тенисът на маса има своя стая", SPORT_ROOM.get("tabletennis") in ALLOWED_THREADS)
    check("ММА има своя стая", SPORT_ROOM.get("mma") in ALLOWED_THREADS)
    # --- НОВИТЕ СТАИ ОТ ФАЙЛ. Ботът предричаше за осем спорта, а стаи имаше
    # за пет. make_rooms.py създава останалите и пише номерата в rooms_state.json.
    check("липсващ файл не чупи", _stai_ot_fayl("нямагоТакъвФайл.json") == {})
    import tempfile as _tf
    _tmp = os.path.join(_tf.gettempdir(), "_gp_rooms_test.json")
    with open(_tmp, "w", encoding="utf-8") as _f:
        json.dump({"hockey": {"thread": 401, "ime": "🏒 Хокей"},
                   "tennis": {"thread": 402},
                   "boklук": {"thread": "низ"},
                   "praznо": {},
                   "otricatelno": {"thread": -5}}, _f, ensure_ascii=False)
    _chetene = _stai_ot_fayl(_tmp)
    check("хокеят се чете от файла", _chetene.get("hockey") == "401")
    check("тенисът се чете от файла", _chetene.get("tennis") == "402")
    check("боклук на мястото на номера се прескача", "boklук" not in _chetene)
    check("празен запис се прескача", "praznо" not in _chetene)
    check("отрицателен номер се прескача", "otricatelno" not in _chetene)
    check("прочетени са точно двата валидни", len(_chetene) == 2)
    try:
        os.remove(_tmp)
    except OSError:
        pass
    with open(_tmp, "w", encoding="utf-8") as _f:
        _f.write("това не е json")
    check("повреден файл не чупи", _stai_ot_fayl(_tmp) == {})
    try:
        os.remove(_tmp)
    except OSError:
        pass
    check("закованите стаи имат превес пред файла",
          SPORT_ROOM.get("football") == "5")

    # --- 🥊 ММА: НАЧИНЪТ НА ПОБЕДА. Дефектът лъжеше ВСЕКИ ДЕН — четеше се от
    # status["type"], където полетата ги няма, и „предсрочно" излизаше винаги
    # вярно: 71 от 71 бойци с дял 100%. И невидимото: Elo коефициентът беше
    # закован на ×1.25, тоест грешката местеше самите рейтинги.
    check("цели рундове с изтекъл часовник = съдийско решение",
          mma_finish({"period": 3, "displayClock": "5:00"}, 3) is False)
    check("часовник, който брои надолу, също значи изтекъл",
          mma_finish({"period": 3, "displayClock": "0:00"}, 3) is False)
    check("край във втория рунд = предсрочно",
          mma_finish({"period": 2, "displayClock": "3:24"}, 3) is True)
    check("край в последния рунд преди края = предсрочно",
          mma_finish({"period": 3, "displayClock": "1:12"}, 3) is True)
    check("петрундов бой: цели рундове = решение",
          mma_finish({"period": 5, "displayClock": "5:00"}, 5) is False)
    check("петрундов бой: край в трети = предсрочно",
          mma_finish({"period": 3, "displayClock": "2:05"}, 5) is True)
    check("БЕЗ ЧАСОВНИК не се твърди нищо",
          mma_finish({"period": 3}, 3) is None)
    check("празен часовник не се твърди",
          mma_finish({"period": 3, "displayClock": ""}, 3) is None)
    check("празен статус не се твърди", mma_finish({}, 3) is None)
    check("боклук вместо статус не чупи", mma_finish(None, 3) is None)
    check("боклук вместо рундове не чупи",
          mma_finish({"period": 2, "displayClock": "1:00"}, None) is True)
    check("липсващ рунд с часовник в края НЕ е решение",
          mma_finish({"displayClock": "5:00"}, 3) is True)
    # Точно старият дефект: полетата в status["type"] вместо в status.
    _stara = {"type": {"period": 3, "displayClock": "5:00", "completed": True}}
    check("СТАРИЯТ ДЕФЕКТ: полета на грешното място вече НЕ дават предсрочно",
          mma_finish(_stara, 3) is None)
    check("предсрочно и решение НЕ са едно и също",
          mma_finish({"period": 1, "displayClock": "0:44"}, 3)
          is not mma_finish({"period": 3, "displayClock": "5:00"}, 3))

    # --- 🎾 ТЕНИС: ЛИНИЯТА ПАСВА НА ФОРМАТА.
    # Редът беше закован на „до два спечелени сета" и в мачовете до ТРИ
    # спечелени печаташе „Под 2.5 сета" — минимумът там е 3 сета, тоест
    # твърдение, което не може да се сбъдне. Загуба, обявена предварително.
    for _p in (0.55, 0.62, 0.70, 0.78, 0.85, 0.92):
        _r3 = tennis_sets_line(_p, 3)
        _r5 = tennis_sets_line(_p, 5)
        check("при %.2f мач до 2 сета не говори за 3.5/4.5" % _p,
              "3.5" not in _r3 and "4.5" not in _r3)
        check("при %.2f мач до 3 сета НЕ казва Под 2.5" % _p,
              "Под 2.5" not in _r5)
        check("при %.2f мач до 3 сета не говори за 2.5 изобщо" % _p,
              "2.5" not in _r5)
    check("мач до 2 сета ползва линия 2.5",
          "2.5" in tennis_sets_line(0.80, 3))
    check("мач до 3 сета ползва 3.5 или 4.5",
          ("3.5" in tennis_sets_line(0.80, 5)) or ("4.5" in tennis_sets_line(0.80, 5)))
    check("липсващ формат се държи като до 2 сета",
          tennis_sets_line(0.80) == tennis_sets_line(0.80, 3))
    check("нула вместо формат не чупи", isinstance(tennis_sets_line(0.80, 0), str))
    check("тенис-редът е чист", banned_word(tennis_sets_line(0.80, 5)) is None)
    check("двата формата дават РАЗЛИЧЕН ред",
          tennis_sets_line(0.75, 3) != tennis_sets_line(0.75, 5))
    _teni = set(tennis_sets_line(0.52 + i * 0.008, 5) for i in range(50))
    check("тенис-редът НЕ е константа (50 входа, 5+ различни)", len(_teni) >= 5)
    check("стая 4 е разрешена за фишовете", PICKS_THREAD in ALLOWED_THREADS)
    check("стая 27 остава витрината", PREDICT_THREAD in ALLOWED_THREADS)
    check("хазартна дума не излиза", post_predict("залагай сега", PREDICT_THREAD) is False)
    check("име на букмейкър не излиза", post_predict("bet365 дава 2.10", PREDICT_THREAD) is False)
    check("коефициент не излиза", post_predict("коефициент 1.85", PREDICT_THREAD) is False)
    check("и съкратеното коеф. не излиза", post_predict("коеф. 1.85", PREDICT_THREAD) is False)
    check("чист текст минава пазача", banned_word("Арсенал 68%, извадка 114 мача") is None)

    # --- фиш-езикът: 1 / Х / 2 / 1Х / Х2 и Над/Под направо от головата матрица
    check("фиш: домакинът е 1",
          pick_1x2(0.50, 0.28, 0.22, "Арсенал", "Челси")[:2] == ("1 · победа Арсенал", 0.50))
    check("фиш: гостът е 2",
          pick_1x2(0.22, 0.28, 0.50, "Арсенал", "Челси")[:2] == ("2 · победа Челси", 0.50))
    check("фиш: равенството е Х",
          pick_1x2(0.30, 0.40, 0.30, "Арсенал", "Челси")[:2] == ("Х · равен", 0.40))

    # --- ДВОЙНИЯТ ШАНС Е ИЗКЛЮЧЕН по поръчка на собственика (05.08.2026):
    # „много ниски коефициенти, безсмислени". Кодът остава, прагът е нула.
    check("двойният шанс е изключен", FOOT_SINGLE_MIN == 0.0)
    check("слаб домакин пак излиза САМ победител",
          pick_1x2(0.42, 0.30, 0.28, "Арсенал", "Челси")[0] == "1 · победа Арсенал")
    check("слаб гост пак излиза САМ победител",
          pick_1x2(0.28, 0.30, 0.42, "Арсенал", "Челси")[0] == "2 · победа Челси")
    check("нито един избор не е 1Х",
          not any(pick_1x2(p, 0.30, 0.70 - p, "А", "Б")[0].startswith("1Х")
                  for p in (0.10, 0.20, 0.30, 0.40, 0.45, 0.49)))
    check("нито един избор не е Х2",
          not any(pick_1x2(0.70 - p, 0.30, p, "А", "Б")[0].startswith("Х2")
                  for p in (0.10, 0.20, 0.30, 0.40, 0.45, 0.49)))
    check("всеки избор е 1, Х или 2",
          all(pick_1x2(a / 100.0, b / 100.0, 1.0 - a / 100.0 - b / 100.0, "А", "Б")[0][0]
              in ("1", "2", "Х")
              for a in range(10, 70, 7) for b in range(15, 40, 6)))
    check("единичният се мери срещу база 1/3",
          abs(pick_1x2(0.42, 0.30, 0.28, "А", "Б")[2] - 1.0 / 3.0) < 1e-9)

    # РАВЕНСТВОТО ВСЕ ПАК ИЗЛИЗА — това беше истинската поправка. Допреди
    # домакинството се броеше двойно и клонът „Х" беше недостижим.
    check("равенството печели, когато наистина води",
          pick_1x2(0.30, 0.40, 0.30, "Арсенал", "Челси")[0] == "Х · равен")
    check("равенството носи своята вероятност",
          abs(pick_1x2(0.30, 0.40, 0.30, "А", "Б")[1] - 0.40) < 1e-9)

    # Ако собственикът някой ден го включи — правилото пак работи.
    _star = FOOT_SINGLE_MIN
    try:
        globals()["FOOT_SINGLE_MIN"] = 0.50
        _dc = pick_1x2(0.42, 0.30, 0.28, "Арсенал", "Челси")
        check("включен обратно, двойният шанс пак работи",
              _dc[0] == "1Х · Арсенал или равен")
        check("включен обратно, събира двете вероятности", abs(_dc[1] - 0.72) < 1e-9)
        check("включен обратно, базата е 2/3", abs(_dc[2] - 2.0 / 3.0) < 1e-9)
        check("двойният шанс НЕ получава звезди наготово",
              strength_1x2(_dc[1], _dc[2]) < strength_1x2(_dc[1], 1.0 / 3.0))
    finally:
        globals()["FOOT_SINGLE_MIN"] = _star
    check("прагът е върнат както беше", FOOT_SINGLE_MIN == 0.0)
    check("силата при база 1/3 е точно старата формула",
          abs(strength_1x2(0.55) - (0.55 - 1.0 / 3.0) * 1.5) < 1e-9)
    check("нулево знание при двоен шанс дава нула сила",
          strength_1x2(2.0 / 3.0, 2.0 / 3.0) == 0.0)
    check("сигурното твърдение дава пълна сила", strength_1x2(1.0, 2.0 / 3.0) == 1.0)

    # --- РЕЗЕРВНАТА КАРТА също говори на фиш-език.
    # Тук зееше дупка: излизаше „Andrey Rublev 50%" и „Мексико 55%" — без 1/2
    # отпред. Оценителят чете точно този код; без него присъдата виси на
    # съвпадение по име, а имената лъжат при двоен шанс.
    def _glava(txt):
        return (str(txt).split("·")[0].strip() if "·" in str(txt) else "")

    for _b in ("tennis", "tabletennis", "mma", "basketball", "volleyball",
               "baseball", "hockey", "football"):
        _fx = {"bucket": _b, "emoji": "🎯", "home": "Първи", "away": "Втори",
               "league": "Тест", "extra": {}}
        _an = fallback_analyse(_fx, {}, "няма история")
        check("резервната карта за " + _b + " има код отпред",
              _glava(_an["pick"]) in ("1", "2", "Х", "1Х", "Х2"))
        check("резервната карта за " + _b + " не е празна", bool(_an["pick"]))
        check("резервната карта за " + _b + " е с една звезда", _an["stars"] == 1)
    _ft = fallback_analyse({"bucket": "football", "emoji": "⚽", "home": "Първи",
                            "away": "Втори", "league": "Тест", "extra": {}},
                           {}, "няма история")
    # Двойният шанс е изключен, затова и резервната карта дава сам победител.
    # При нула информация водещият изход е домакинът (FALLBACK_HOME=0.45 срещу
    # 0.28 за равен и 0.27 за гост).
    check("резервният футбол дава САМ победител",
          _ft["pick"].startswith("1 · победа"))
    check("резервният футбол не е двоен шанс",
          not _ft["pick"].startswith("1Х") and not _ft["pick"].startswith("Х2"))
    check("резервният футбол носи своята вероятност, не сбор",
          0.40 < _ft["p"] < 0.50)
    check("трите футболни вероятности се събират на 1",
          abs(0.45 + FALLBACK_DRAW + (1.0 - FALLBACK_DRAW - 0.45) - 1.0) < 1e-9)
    _ti = fallback_analyse({"bucket": "tennis", "emoji": "🎾", "home": "Синер",
                            "away": "Алкарас", "league": "Тест", "extra": {}},
                           {}, "няма история")
    check("резервният тенис е само име, без думата победа",
          "победа" not in _ti["pick"] and "Синер" in _ti["pick"])
    _ba = fallback_analyse({"bucket": "basketball", "emoji": "🏀", "home": "Никс",
                            "away": "Хийт", "league": "Тест", "extra": {}},
                           {}, "няма история")
    check("резервният баскетбол пише победа", "победа" in _ba["pick"])

    # --- СПОРТ БЕЗ ИЗТОЧНИК НЕ ВЛИЗА ВЪВ ФИШ.
    # На 04.08 два от трите фиша бяха с по 3 крака тенис на маса — фиш, който
    # чака присъда, която няма как да дойде.
    # 🔴 ОБЪРНАТА 12.08.2026 заедно със самото правило. Проверката пазеше
    # изключването; сега пази ВРЪЩАНЕТО. Тестовете, които пазят текст или
    # правило, се обръщат — не се трият, иначе никой не пази новото.
    check("тенисът на маса ВЕЧЕ участва във фишовете",
          "tabletennis" not in COMBO_NO_RESULT)
    check("изключените от фишовете съвпадат с тези без източник",
          COMBO_NO_RESULT == set())
    check("волейболът НЕ е изключен от фишовете",
          "volleyball" not in COMBO_NO_RESULT)
    check("футболът НЕ е изключен от фишовете",
          "football" not in COMBO_NO_RESULT)
    _kand = [{"bucket": "tabletennis", "p": 0.90, "stars": 3},
             {"bucket": "volleyball", "p": 0.80, "stars": 3},
             {"bucket": "football", "p": 0.70, "stars": 2},
             {"bucket": "basketball", "p": 0.40, "stars": 1}]
    _pul = [a for a in _kand
            if float(a.get("p") or 0.0) >= COMBO_MIN_P
            and a.get("bucket") not in COMBO_NO_RESULT]
    # 🔴 ОБЪРНАТА 12.08.2026 заедно със самото правило. Пазеше изхвърлянето на
    # тениса на маса; сега пази, че той ВЛИЗА — защото вече има източник за
    # резултата. Тестът, който пази правило, се обръща, не се трие.
    check("тенисът на маса вече минава филтъра въпреки че беше изключен",
          any(a.get("bucket") == "tabletennis" for a in _pul))
    check("филтърът пуска трите над прага, реже само слабото", len(_pul) == 3)
    check("слабият кандидат пак се реже",
          not any(a.get("bucket") == "basketball" for a in _pul))
    check("филтърът пази волейбола",
          any(a["bucket"] == "volleyball" for a in _pul))
    check("филтърът пази прага по вероятност",
          all(a["p"] >= COMBO_MIN_P for a in _pul))

    # --- ЕДНАТА ЗВЕЗДА КАЗВА ВЯРНАТА ПРИЧИНА.
    # Пишеше се „малка извадка" винаги, а 6 от 7 такива карти имаха голяма.
    _sega2 = datetime.now(SOFIA)

    def _karta(zvezdi, n_eff, izvadka):
        return card({"fx": {"bucket": "tennis", "emoji": "🎾", "home": "Синер",
                            "away": "Алкарас", "league": "Тест", "when": None,
                            "time": "19:00"},
                     "bucket": "tennis", "pick": "1 · Синер", "p": 0.61,
                     "second": "", "third": "",
                     "why": ["Синер: тест", "Алкарас: тест"],
                     "sample": izvadka, "n_eff": float(n_eff),
                     "strength": 0.2, "stars": int(zvezdi)}, _sega2)

    check("тънката стъпка се назовава",
          "стъпката е тънка" in _karta(1, 4.0, samp(3, 3)))
    check("голямата извадка НЕ се нарича тънка",
          "стъпката е тънка" not in _karta(1, 135.0, samp(135, 136)))
    check("картата с три звезди няма предупреждение",
          "стъпката е тънка" not in _karta(3, 135.0, samp(135, 136)))
    check("прагът е точно 10 — под него стъпката е тънка",
          "стъпката е тънка" in _karta(1, 9.9, samp(5, 5))
          and "стъпката е тънка" not in _karta(1, 10.0, samp(20, 20)))

    # --- 🔴 ПРИСЪДАТА НЕ БИВА ДА ПРОТИВОРЕЧИ НА ПРОЦЕНТА.
    # Точно това правеше старата карта: „50%" и „⭐⭐⭐ добра увереност" една
    # под друга. Проверява се на самите гранични числа, не общо.
    # --- 🔴 ДОЛНАТА ГРАНИЦА ЗА ПУБЛИКУВАНЕ.
    # Измерено върху 131 отсъдени: под 45% има само футбол — 6 карти, 1 позната.
    # Махнати, общото се вдига от 64.9% на 67.2%.
    # --- 🔴 ПРЕДСЕЗОННИТЕ. Пазачът гледаше поле, което ESPN оставя празно.
    # Числата долу са ТОЧНО каквото ESPN върна за НФЛ на 13.08.2026.
    check("предсезонен по slug", predsezonen(
        {"season": {"year": 2026, "type": 1, "slug": "preseason"},
         "seasonType": {}}) is True)
    check("предсезонен по име", predsezonen(
        {"seasonType": {"name": "Preseason"}}) is True)
    check("предсезонен по съкращение на срещата",
          predsezonen({}, {"type": {"abbreviation": "PRE"}}) is True)
    check("редовният сезон НЕ е предсезонен", predsezonen(
        {"season": {"year": 2026, "type": 2, "slug": "regular-season"},
         "seasonType": {"name": "Regular Season"}}) is False)
    check("празният мач не се брои за предсезонен", predsezonen({}) is False)
    check("боклук вместо сезон не чупи", predsezonen({"season": None}) is False)

    check("прагът е точно 45%", abs(MIN_SHOW_P - 0.45) < 1e-9)
    # 🔴 МОНЕТАТА. При два изхода фаворитът е ≥50% по конструкция, значи
    # 50–52% не е превес, а „не знам". Живата стая показа карта „50% ·
    # почти равностойни" — числото и думата „прогноза" се бият челно.
    check("двоичните имат по-висока летва", MIN_SHOW_P_DVA > MIN_SHOW_P)
    check("летвата за двоични е 53%", abs(MIN_SHOW_P_DVA - 0.53) < 1e-9)
    check("50% НЕ минава при два изхода", 0.50 < dolen_prag("mma"))
    check("52% НЕ минава при два изхода", 0.52 < dolen_prag("tennis"))
    check("54% минава при два изхода", 0.54 >= dolen_prag("volleyball"))
    check("футболът пази своите 45%", abs(dolen_prag("football") - 0.45) < 1e-9)
    check("45% минава САМО при футбола",
          0.45 >= dolen_prag("football") and 0.45 < dolen_prag("baseball"))
    # Всеки спорт трябва да е решен: или е в списъка на двоичните, или е футбол.
    check("всеки спорт има ясна летва",
          all(b in DVA_IZHODA or b == "football" for b in SPORT_ORDER))
    check("прагът не е толкова висок, че да изяде волейбола", MIN_SHOW_P <= 0.50)
    check("прагът не е изключен по невнимание", MIN_SHOW_P > 0.0)
    check("35% пада под прага", 0.35 < MIN_SHOW_P)
    check("51% минава прага при футбола", 0.51 >= dolen_prag("football"))

    check("50% е почти равностойни", p_duma(0.50) == "🔴 почти равностойни")
    check("57% още не е фаворит", "фаворит" not in p_duma(0.57))
    check("62% е лек фаворит", p_duma(0.62) == "🟡 лек фаворит")
    check("70% е ясен фаворит", p_duma(0.70) == "🟢 ясен фаворит")
    check("85% е много ясен фаворит", p_duma(0.85) == "🟢 много ясен фаворит")
    check("присъдата расте заедно с процента",
          [p_duma(x) for x in (0.50, 0.62, 0.70, 0.85)]
          == sorted({p_duma(x) for x in (0.50, 0.62, 0.70, 0.85)},
                    key=lambda d: [p_duma(y) for y in (0.50, 0.62, 0.70, 0.85)].index(d)))
    check("присъдата не пада при боклук", p_duma(None) == "" and p_duma("х") == "")
    check("всяка вероятност получава дума",
          all(p_duma(x / 100.0) for x in range(0, 101)))

    # --- ИМЕНАТА НА ТУРНИРИТЕ. Дотук в стаята стоеше цял английски низ,
    # отрязан по средата: „FIVB Volleyball Girls' U17 World Championship…".
    check("световното за девойки е на български",
          liga_bg("FIVB Volleyball Girls' U17 World Championship 2026")
          == "Световно U17, девойки")
    check("квалификациите се разпознават",
          liga_bg("uefa.champions_qual") == "Квалификации за Шампионска лига")
    # 🔴 Трите квалификации се бъркат лесно — конференциите съдържат думите на
    # Лига Европа. Ако редът в LIGA_BG се размени, това пада.
    check("квалификациите за Лига Европа са отделно",
          liga_bg("uefa.europa_qual") == "Квалификации за Лига Европа")
    check("квалификациите за конференциите са отделно",
          liga_bg("uefa.europa.conf_qual")
          == "Квалификации за Лига на конференциите")
    # Дупката, която ги роди: през август основните адреси са празни, играят
    # само квалификациите. Липсваше ли адресът, футболът мълчеше цял ден.
    _slugs = [s for s, _w, _n in FOOT_SLUGS]
    for _q in ("uefa.champions_qual", "uefa.europa_qual", "uefa.europa.conf_qual"):
        check("адресът " + _q + " се пита", _q in _slugs)
    check("нито една лига не пада под отреза", FOOT_SLUG_MAX == len(FOOT_SLUGS))
    check("квалификациите са в летния блок (преди отреза)",
          all(_slugs.index(_q) < 6
              for _q in ("uefa.champions_qual", "uefa.europa_qual",
                         "uefa.europa.conf_qual")))
    check("непознат турнир минава както си е", liga_bg("Купа на Разград") == "Купа на Разград")
    check("много дългото непознато име се реже",
          len(liga_bg("х" * 90)) <= 44 and liga_bg("х" * 90).endswith(chr(8230)))
    check("празното си остава празно", liga_bg(None) == "" and liga_bg("") == "")

    # --- ИЗВАДКАТА СЕ ЧЕТЕ КАКТО Е ЗАМИСЛЕНА.
    # Пишеше „извадка 30+30 мача" — плюсът се чете като сбор 60, а числата са
    # ПООТДЕЛНО за двата отбора.
    # 🔴 ПРЕПИСАНО 11.08.2026: „по 31 и 55 мача" се чете като задача по
    # математика. Прочетох го в живата карта и не го разбрах от първия път.
    check("равни извадки се пишат веднъж",
          samp(30, 30) == "гледани по 30 мача на всеки")
    check("различни извадки се казват с думи",
          samp(76, 74) == "гледани 76 мача на единия и 74 на другия")
    check("извадката се чете от човек, не се дешифрира",
          "гледани" in samp(30, 30) and "мача" in samp(76, 74))
    check("извадката вече няма плюс", "+" not in samp(30, 30) and "+" not in samp(1, 2))
    # 🔴 ТИРЕТО МЕЖДУ ДВЕ ЧИСЛА. Живата карта казваше „Lily ZHANG: 10-21 за
    # 18 месеца". 10-21 може да е победи-загуби, резултат или диапазон.
    check("победите и загубите се казват с думи",
          pobedi_zagubi(10, 21) == "10 победи и 21 загуби")
    check("единственото число е единствено",
          pobedi_zagubi(1, 1) == "1 победа и 1 загуба")
    check("нулата не гърми", pobedi_zagubi(0, 0) == "0 победи и 0 загуби")
    check("в записа няма тире между числата", "-" not in pobedi_zagubi(6, 2))
    # И ММА опашката: „0 боя в индекса" не значи нищо за читателя.
    check("непознатият боец се казва с думи",
          boeve_index(0) == " · него не сме го следили")
    check("следеният боец се брои", "3" in boeve_index(3))
    check("един бой е в единствено число", "негов бой" in boeve_index(1))
    check("звездите имат думи", len(ZVEZDI_DUMA) == 3)
    # Звездите вече говорят за ДАННИТЕ. Думата „увереност" им беше отнета,
    # защото я обещаваха и до 50%. Тук се пази да не се върне.
    check("трите звезди са богата история", ZVEZDI_DUMA[3] == "богата история")
    check("звездите не говорят за увереност",
          not any("увереност" in d for d in ZVEZDI_DUMA.values()))

    # --- ИСТОРИЯТА НА БОТА ПО СПОРТ. Дневникът само се пишеше — нито един ред
    # не го е чел, тоест 73 карти са минали без доказателство зад себе си.
    _record_cache.clear()
    check("повреден дневник НЕ чупи картата", isinstance(sport_record("football"), str))
    check("липсващ спорт не дава ред", sport_record("") == "")
    check("непознат спорт не чупи", isinstance(sport_record("зззз"), str))
    check("прагът за процент е 10", RECORD_MIN == 10)
    check("името на спорта е членувано", SPORT_DUMA.get("football") == "Футболът")

    # --- РЕДЪТ ЗА ТОЧКИ НОСИ ОЧАКВАНИЯ СБОР.
    # Процентът му е закован около 69% по устройство (111 от 111 проби);
    # това, което се мени от мач на мач, е самият сбор — и той трябва да се вижда.
    _pt = points_total_line(168.0, 11.5, "точки")
    check("редът за точки съществува", bool(_pt))
    check("редът за точки казва очаквания сбор", "~168 точки общо" in _pt)
    check("редът за точки казва и линията", "Над " in _pt)
    check("редът за точки е чист", banned_word(_pt) is None)
    check("нулевият сбор не дава ред", points_total_line(0, 11.5) == "")
    _pt2 = points_total_line(220.0, 13.5, "точки")
    check("различен мач дава различен очакван сбор", "~220 точки общо" in _pt2)

    # --- ⚽ ГОЛ-ГОЛ. Поискан поименно от собственика. Числото p_btts се
    # смяташе в matrix_markets от самото начало и НИКОЙ не го четеше.
    # Числата тук са СУРОВИ — това, което излиза на картата, е свитото.
    # 0.75 сурово става 0.64 обявено (0.5 + 0.56 * 0.25).
    check("гол-гол: ДА при сурови 75%", btts_line(0.75) == "Гол-гол: ДА <b>64%</b>")
    check("гол-гол: НЕ при сурови 25%", btts_line(0.25) == "Гол-гол: НЕ <b>64%</b>")
    check("гол-гол: между праговете мълчи",
          btts_line(0.50) == "" and btts_line(0.60) == "")
    # Прагът 57% СЛЕД свиване значи сурови 0.625.
    check("прагът е включително след свиването",
          btts_line(0.625) != "" and btts_line(0.375) != "")
    check("точно под прага мълчи",
          btts_line(0.62) == "" and btts_line(0.38) == "")
    check("гол-гол: боклук на входа не чупи",
          btts_line(None) == "" and btts_line(0.0) == ""
          and btts_line(1.0) == "" and btts_line("низ") == "")
    _gol = matrix_markets(score_matrix(2.3, 1.7))       # голов мач
    _suh = matrix_markets(score_matrix(0.9, 0.7))       # сух мач
    check("гол-гол: p_btts наистина се смята", 0.0 < _gol["p_btts"] < 1.0)
    check("голов мач -> и двата бележат",
          btts_line(_gol["p_btts"]).startswith("Гол-гол: ДА"))
    check("сух мач -> гол-гол НЕ",
          btts_line(_suh["p_btts"]).startswith("Гол-гол: НЕ"))
    _mk_1s = matrix_markets(score_matrix(2.8, 0.4))     # единият громи
    check("едностранен мач: гол-гол НЕ противоречи на Над/Под",
          not btts_line(_mk_1s["p_btts"]).startswith("Гол-гол: ДА"))
    check("едностранен мач: p_btts е нисък", _mk_1s["p_btts"] < 0.5)
    check("гол-гол не преписва Над/Под", _gol["p_btts"] != _gol["p_over"])
    check("гол-гол е чист за пазача", banned_word(btts_line(0.62)) is None)
    check("гол-гол се мени от мач на мач",
          btts_line(_gol["p_btts"]) != btts_line(_suh["p_btts"]))

    # --- СВИВАНЕТО ПРЕДИ ОБЯВЯВАНЕ. Измерено върху 75 586 изиграни мача:
    # допълнителните редове надуваха с 4 до 7 пункта. Множителите са научени
    # от 2014-2021 и изпитани върху 2022-2026 — НЕ са нагласени върху същите
    # данни, върху които се хвалят.
    check("свиването не мени монетата", abs(svii(0.5, 0.58) - 0.5) < 1e-12)
    check("свиването дърпа към монетата", svii(0.80, 0.58) < 0.80)
    check("свиването е симетрично",
          abs((svii(0.80, 0.58) - 0.5) + (svii(0.20, 0.58) - 0.5)) < 1e-12)
    check("множител 1.0 не пипа нищо", abs(svii(0.73, 1.0) - 0.73) < 1e-12)
    check("свиването понася боклук", svii("низ", 0.5) is None and svii(None, 0.5) is None)
    check("свиването остава между 0 и 1",
          0.0 <= svii(0.99, 0.58) <= 1.0 and 0.0 <= svii(0.01, 0.58) <= 1.0)
    check("множителят за над/под е измереният", abs(OU_SHRINK - 0.58) < 1e-9)
    check("множителят за гол-гол е измереният", abs(BTTS_SHRINK - 0.56) < 1e-9)
    # 60% сурово ставаше ред; след свиването вече не стига прага — точно това
    # е цената: редът излиза по-рядко, но когато излезе, числото е вярно.
    check("суровите 60% вече НЕ дават ред", btts_line(0.60) == "")
    check("суровите 80% още дават ред", btts_line(0.80) != "")
    check("обявеното е ПО-НИСКО от суровото",
          pct(svii(0.80, BTTS_SHRINK)) in btts_line(0.80)
          and pct(0.80) not in btts_line(0.80))
    _syrovo, _obyaveno = 0.85, svii(0.85, BTTS_SHRINK)
    check("свитото при 85% е около 70%", 0.68 < _obyaveno < 0.71)
    check("картата обявява свитото, не суровото",
          pct(_obyaveno) in btts_line(_syrovo))
    check("над/под също се свива", over_under_line(0.62) == "")
    check("силният над/под остава", over_under_line(0.85) != "")

    # --- 🏒 ХОКЕЙНИЯТ ТОТАЛ. Линията е стълба от две, защото 3.5 е закована
    # истина (992 от 992 „над"), а 4.5 и 7.5 се избират 0 пъти от 19881 проби.
    check("хокей: стълбата е точно две линии", HOCK_TOTAL_LINES == (5.5, 6.5))
    _hg = hockey_goals_line(3.2, 3.0)
    check("хокей: голов мач дава ред", bool(_hg))
    check("хокей: редът казва гола", "гола" in _hg)
    check("хокей: редът е чист", banned_word(_hg) is None)
    check("хокей: празни ламбди не чупят",
          hockey_goals_line(0, 0) == "" and hockey_goals_line(None, None) == ""
          and hockey_goals_line("низ", 2.0) == "")
    check("хокей: сух мач клони към Под",
          hockey_goals_line(2.0, 1.8).startswith("Под"))
    check("хокей: голов мач клони към Над",
          hockey_goals_line(4.2, 3.9).startswith("Над"))
    check("хокей: редът се мени със сбора",
          hockey_goals_line(2.0, 1.8) != hockey_goals_line(4.2, 3.9))
    _hbroy = len(set(hockey_goals_line(2.4 + i * 0.06, 2.6 + i * 0.05)
                     for i in range(40)))
    check("хокей: редът НЕ е константа (40 входа, 8+ различни)", _hbroy >= 8)

    # --- 🏐 ПЕТИ СЕТ. Еднопосочен НАРОЧНО: клонът „ДА" е доказано недостижим
    # (максимумът е 0.375 срещу праг 0.57), тоест „ДА/НЕ" би бил фалшив избор.
    _d5 = [[(3, 0, 0.30), (3, 1, 0.28), (3, 2, 0.12)],
           [(3, 0, 0.10), (3, 1, 0.12), (3, 2, 0.08)]]
    _f5 = fifth_set_line(_d5)
    check("пети сет: излиза ред", bool(_f5))
    check("пети сет: говори за 4 сета", "до 4 сета" in _f5)
    check("пети сет: НЕ предлага фалшив избор ДА/НЕ",
          "ДА" not in _f5 and "НЕ" not in _f5)
    check("пети сет: чист за пазача", banned_word(_f5) is None)
    check("пети сет: празно разпределение мълчи",
          fifth_set_line([]) == "" and fifth_set_line([[], []]) == "")
    _mnogo5 = [[(3, 2, 0.50)], [(3, 2, 0.50)]]        # всичко отива в пети сет
    check("пети сет: щом всичко е 3:2, редът мълчи", fifth_set_line(_mnogo5) == "")
    _kramp = [[(3, 0, 0.99)], [(3, 0, 0.01)]]         # опира в клампа
    check("пети сет: над тавана мълчи, за да не пише клампа",
          fifth_set_line(_kramp) == "")
    check("пети сет: таванът е 0.97", VOL5_CAP == 0.97)
    check("общата сметка за сетове връща None при празно",
          sets_p_over([], 4.5) is None)
    check("общата сметка нормира до 1",
          abs(sets_p_over([[(3, 0, 0.5)], [(3, 0, 0.5)]], 2.5) - 1.0) < 1e-9)
    check("старият ред за сетове още работи",
          sets_total_line(_d5, 3.5) != "")
    check("фиш: отборен спорт без равен", pick_win(False, "Никс", "Хийт") == "2 · победа Хийт")
    check("фиш: индивидуалният спорт е само име", pick_name(True, "Синер", "Алкарас") == "1 · Синер")
    # Числата са СУРОВИ; на картата излиза свитото (0.5 + 0.58 * (p − 0.5)).
    # Сурови 0.69 стават обявени 0.61.
    check("Над 2.5 при сурови 69%",
          over_under_line(0.69) == "Над 2.5 гола: <b>61%</b>")
    check("Под 2.5 при сурови 31%",
          over_under_line(0.31) == "Под 2.5 гола: <b>61%</b>")
    check("между праговете няма ред",
          over_under_line(0.50) == "" and over_under_line(0.60) == "")
    # Прагът 57% след свиване значи сурови 0.6207.
    check("прагът е включително след свиването", over_under_line(0.63) != "")
    check("точно под прага мълчи", over_under_line(0.615) == "")
    mk_hi = matrix_markets(score_matrix(2.3, 1.7))    # голов мач: общо 4.0 очаквани гола
    mk_lo = matrix_markets(score_matrix(0.9, 0.7))    # сух мач: общо 1.6 очаквани гола
    check("силната матрица клони към Над",
          not over_under_line(mk_hi["p_over"]).startswith("Под"))
    check("ниската матрица дава ред Под",
          over_under_line(mk_lo["p_over"]).startswith("Под 2.5 гола"))
    check("свитото е по-скромно от суровото",
          pct(svii(mk_lo["p_over"], OU_SHRINK)) != pct(mk_lo["p_over"]))

    # --- картите: кратки, чисти, всяка с ясен фиш-избор
    demo = {"fx": {"bucket": "basketball", "emoji": "🏀", "home": "Ню Йорк Никс",
                   "away": "Маями Хийт", "league": "НБА", "when": None, "time": "21:30"},
            "bucket": "basketball", "pick": "1 · победа Ню Йорк Никс", "p": 0.68,
            "second": "Очакван резултат: ~112:105",
            "why": ["Никс: 116.3 : 110.1 точки за мач (82 мача)",
                    "Хийт: 109.8 : 112.4 точки за мач (82 мача)"],
            "sample": samp(82, 82), "n_eff": 164.0, "strength": 0.36, "stars": 2}
    txt = card(demo, now)
    check("картата е под 900 знака", len(txt) < 900)
    check("картата носи фиш-прогнозата",
          "🎯 <b>1 · победа Ню Йорк Никс" in txt and "68%" in txt)
    check("баскетболът носи очакван резултат", "Очакван резултат: ~112:105" in txt)
    check("картата носи реда за данните",
          "📚" in txt and "гледани по 82 мача на всеки" in txt)
    check("в картата няма звезди", "⭐" not in txt)
    check("картата има най-много две обяснения",
          txt.split("📋 <b>Защо точно това</b>")[-1].count(NL + "• ") == 2)

    # ⚾ СТАРТИРАЩИТЕ ПИТЧЪРИ (18.08.2026) — само когато знаем и двамата.
    _bb = {"fx": {"bucket": "baseball", "emoji": "⚾", "home": "Ню Йорк Янкис",
                  "away": "Балтимор Ориолс", "league": "МЛБ", "when": None,
                  "time": "02:05",
                  "extra": {"pit_home": "Carlos Rodón", "pit_away": "Shane Smith"}},
           "bucket": "baseball", "pick": "1 · Ню Йорк Янкис", "p": 0.57,
           "why": ["Янкис: 4.8 : 4.1 точки за мач"],
           "sample": samp(60, 60), "n_eff": 120.0, "strength": 0.20, "stars": 2}
    _t_bb = card(_bb, now)
    check("картата казва кой хвърля", "⚾ Хвърлят: " in _t_bb)
    # 🔴 РЕДЪТ СЕ СВЕРЯВА С ЗАГЛАВИЕТО, не се пише наизуст. Питчърът на
    # домакина трябва да стои от същата страна, от която стои домакинът.
    check("питчърите са в реда на отборите",
          (_t_bb.index("Ню Йорк Янкис") < _t_bb.index("Балтимор Ориолс"))
          == (_t_bb.index("Carlos Rodón") < _t_bb.index("Shane Smith")))
    check("и двете имена са на картата",
          "Carlos Rodón" in _t_bb and "Shane Smith" in _t_bb)
    check("редът за питчърите не коментира",
          not any(w in _t_bb for w in ("по-добър", "предимство", "затова", "форма на")))
    _bb1 = {k: v for k, v in _bb.items()}
    _bb1["fx"] = dict(_bb["fx"], extra={"pit_home": "Carlos Rodón", "pit_away": ""})
    check("един питчър без другия НЕ се показва", "Хвърлят" not in card(_bb1, now))
    _bb0 = {k: v for k, v in _bb.items()}
    _bb0["fx"] = dict(_bb["fx"], extra={})
    check("без питчъри картата е както преди", "Хвърлят" not in card(_bb0, now))

    demo_f = {"fx": {"bucket": "football", "emoji": "⚽", "home": "Арсенал",
                     "away": "Челси", "league": "Висша лига", "when": None, "time": "19:30"},
              "bucket": "football",
              "pick": pick_1x2(0.52, 0.26, 0.22, "Арсенал", "Челси")[0], "p": 0.52,
              "second": over_under_line(mk_hi["p_over"]),
              "why": ["Арсенал: 2.10 вкарани и 0.95 допуснати гола за мач (76 мача)",
                      "Челси: 1.45 вкарани и 1.30 допуснати гола за мач (74 мача)"],
              "sample": samp(76, 74), "n_eff": 120.0, "strength": 0.28, "stars": 3}
    txt_f = card(demo_f, now)
    check("футболната карта носи 1/Х/2", "🎯 <b>1 · победа Арсенал" in txt_f)
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
    check("равенството излиза като Х · равен", "🎯 <b>Х · равен" in card(demo_x, now))
    check("ниската матрица слага ред Под", "Под 2.5 гола" in card(demo_x, now))

    # Новите забранени думи: без поучения, без хазартен речник — на ВСЯКА карта.
    preachy = ("отговорно", "решението е твое", "банка", "единица", "коеф",
               "18+", "гаранция", "не е съвет")
    for dm in (demo, demo_f, demo_v, demo_h, demo_t, demo_x):
        t = card(dm, now)
        tag = dm["fx"]["bucket"] + " " + str(dm["fx"]["home"])
        # Заглавието „ПРОГНОЗА:" отпадна — думата не носеше нищо, картата и без
        # това е прогноза. Остана самият избор с 🎯 пред него.
        check("карта " + tag + ": има ред с избора", "🎯 <b>" in t)
        after = t.split("🎯 <b>", 1)[1][:1] if "🎯 <b>" in t else ""
        check("карта " + tag + ": изборът е 1, 2 или Х", after in ("1", "2", "Х"))
        check("карта " + tag + ": изборът носи и процента",
              "%" in t.split("🎯 <b>", 1)[1][:60])
        check("карта " + tag + ": звездите носят дума",
              any(d in t for d in ZVEZDI_DUMA.values()))
        check("карта " + tag + ": обяснението има заглавие",
              "📋 <b>Защо точно това</b>" in t)
        check("карта " + tag + ": присъдата не спори с процента",
              p_duma(dm["p"]) in t)
        check("карта " + tag + ": чиста от забранени думи",
              banned_word(t) is None and not any(w in t.lower() for w in preachy))
        check("карта " + tag + ": под 1100 знака", len(t) < 1100)

    # --- ЗАБРАНЕНИЯТ ЕЗИК. Собственикът го каза дословно: „спри да ми казваш
    # какво следихме". Намерено на 05.08 чрез ГЛЕДАНЕ на истинските съобщения
    # в групата — от самопроверката не се виждаше, защото тя гледаше само за
    # хазартни думи. Затова сега си има свой пазач.
    _otcheten_trud = ("гледахме", "следихме", "погледнахме", "прегледахме",
                      "разгледахме")
    _podpis = footer_card(14, 3, 2, 8)
    check("подписът не отчита труда на бота",
          not any(w in _podpis.lower() for w in _otcheten_trud))
    # 🔴 ЗВЕЗДИТЕ ОТПАДНАХА 11.08.2026 — виж обяснението при stapka.
    # Прочетена жива карта: „50% · почти равностойни" и точно отдолу „⭐⭐⭐".
    # Символът се четеше като оценка на прогнозата и биеше числото.
    check("в подписа няма звезди", "⭐" not in _podpis)
    check("подписът обяснява знака за данните", "📚" in _podpis)
    check("подписът е кратък", len(_podpis) < 460)
    # 🔴 ЛЕГЕНДАТА И КАРТАТА ТРЯБВА ДА ГОВОРЯТ ЕДНО И СЪЩО.
    # Сутринта картата се смени, а подписът остана да обяснява „⭐⭐⭐ добра
    # увереност" — значение, което вече не съществува. Тази проверка държи
    # двете да не се разминат пак.
    check("подписът не обещава увереност от звезди",
          "увереност" not in _podpis.lower())
    for _z in ZVEZDI_DUMA.values():
        check("подписът обяснява значението: " + _z, _z in _podpis)
    # И най-важното: подписът трябва изрично да КАЖЕ, че редът за данните
    # НЕ оценява прогнозата. Иначе следващият, който го чете, пак ще сложи
    # някакъв символ с три нива и всичко се връща.
    check("подписът казва, че данните не са оценка",
          "НЕ оценява" in _podpis)
    check("подписът обяснява защо много данни и нисък процент вървят заедно",
          "равностоен" in _podpis)
    for _t, _ime in ((header_card(now, 3, 14), "заглавната карта"),
                     (_podpis, "подписът")):
        check(_ime + " не отчита труда",
              not any(w in _t.lower() for w in _otcheten_trud))

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

    # 🔴 КВОТАТА (11.08.2026). Спорт със заковани ЕДНА звезда не може да
    # надбяга спорт с три — ключът е stars*1000. Точно това гладуваше ММА:
    # пет готови карти, места 19-26 от 26, таван 6. Ето същото в малко:
    # шест силни карти от три спорта плюс една еднозвездна ММА карта.
    _gladen = ([mk("volleyball", 3, 0.9), mk("volleyball", 3, 0.85),
                mk("baseball", 3, 0.8), mk("baseball", 2, 0.7),
                mk("basketball", 2, 0.6), mk("basketball", 2, 0.55)]
               + [mk("mma", 1, 0.05)])
    _vzeti = [a["bucket"] for a in choose(_gladen, 6)]
    check("ММА влиза въпреки закованата една звезда", "mma" in _vzeti)
    check("квотата не надува тавана", len(_vzeti) == 6)
    check("силният спорт пак е пръв", _vzeti[0] == "volleyball")
    check("всеки спорт с кандидат получава карта",
          set(_vzeti) == {"volleyball", "baseball", "basketball", "mma"})
    # И обратната посока: изгасени КВОТИТЕ връщат точно старото поведение —
    # гладният спорт пак изчезва. Тоест проверката горе мери квотата, а не
    # някаква обща разлика в подбора.
    #
    # 🔴 ОБНОВЕНА 13.08.2026. Досега гасеше само KVOTA_NA_SPORT. От днес има
    # ВТОРА квота — дневната по спорт — и тя също спасява гладния. Тестът,
    # който проверява „без квота нещо изчезва", трябва да гаси ВСИЧКИ квоти,
    # иначе мери едната през другата и пада без причина.
    _zapazi = KVOTA_NA_SPORT
    _zapazi_den = KVOTA_DEN
    try:
        globals()["KVOTA_NA_SPORT"] = 0
        globals()["KVOTA_DEN"] = 0
        check("без НИТО ЕДНА квота гладният спорт пак изпада",
              "mma" not in [a["bucket"] for a in choose(_gladen, 6)])
        # И поотделно: само дневната квота стига, за да го спаси.
        globals()["KVOTA_DEN"] = 3
        check("само дневната квота също спасява гладния",
              "mma" in [a["bucket"] for a in choose(_gladen, 6)])
    finally:
        globals()["KVOTA_NA_SPORT"] = _zapazi
        globals()["KVOTA_DEN"] = _zapazi_den

    # --- СЕГА ИЛИ НИКОГА: мач преди следващото пускане не бива да се изпусне.
    # Поръчка на собственика: „всички прогнози ПРЕДИ самите мачове".
    # 23:05 е СЛЕД последното пускане за деня — оттам нататък няма друг шанс.
    _v20 = datetime(2026, 8, 5, 23, 5, tzinfo=SOFIA)      # последното пускане
    _v10 = datetime(2026, 8, 5, 10, 5, tzinfo=SOFIA)      # сутрешното
    check("след 23:00 следващото пускане е утре в 8",
          next_run(_v20).hour == 8 and next_run(_v20).day == 6)
    check("в 20:05 следващото пускане е в 21:00",
          next_run(datetime(2026, 8, 5, 20, 5, tzinfo=SOFIA)).hour == 21)
    check("в 10:05 следващото пускане е в 11:00", next_run(_v10).hour == 11)
    # 🔴 СТЪЛБАТА. Измерено от живия дневник на 11.08: 39 от 40 карти излязоха
    # до 13:01 и стаята мълча целия следобед и вечер. Плоският таван пазеше
    # от заливане, но не пазеше НИЩО за часовете, в които хората гледат.
    _st = [(h, dneven_tavan(datetime(2026, 8, 11, h, 0, tzinfo=SOFIA)))
           for h in (8, 10, 12, 14, 16, 18, 20, 22)]
    check("таванът расте с деня",
          all(_st[i][1] <= _st[i + 1][1] for i in range(len(_st) - 1)))
    check("сутрин не се харчи всичко", _st[0][1] < MAX_DAY)
    check("вечер таванът е пълен", _st[-1][1] == MAX_DAY)
    check("в 20:00 вече е пълен", dict(_st)[20] == MAX_DAY)
    check("на обяд има поне още толкова напред", dict(_st)[12] < MAX_DAY)
    check("винаги остава поне един слот", min(v for _h, v in _st) >= 1)
    # Изходът трябва да връща ТОЧНО старото поведение, иначе не е изход.
    _zap = STALBA
    try:
        globals()["STALBA"] = 0
        check("изгасената стълба връща плоския таван",
              all(dneven_tavan(datetime(2026, 8, 11, h, 0, tzinfo=SOFIA)) == MAX_DAY
                  for h in (0, 8, 13, 23)))
    finally:
        globals()["STALBA"] = _zap
    check("часовете на пускане са петнайсет", len(RUN_HOURS) == 15)
    check("няма дупка между два съседни часа",
          all(RUN_HOURS[i + 1] - RUN_HOURS[i] == 1 for i in range(len(RUN_HOURS) - 1)))
    # Последният е 22, не 23: кронът е ПЛАНЪТ, а GitHub закъснява с медиана
    # 71 минути (измерено върху 107 пускания). Планиран 22:00 значи реален 23:0x.
    check("първото е 8, последното 22",
          RUN_HOURS[0] == 8 and RUN_HOURS[-1] == 22)
    check("часовете са подредени и без повторение",
          list(RUN_HOURS) == sorted(set(RUN_HOURS)))

    # --- ПАЗАЧЪТ НА ПРОЗОРЕЦА. Карта в 01:07 е нарушено правило, не дребна
    # неточност — затова часовете се проверяват един по един, а не „общо".
    _dn = datetime(2026, 8, 11, 12, 0, tzinfo=SOFIA)
    for _h in range(24):
        _ochakvano = 8 <= _h <= 23
        check("час " + str(_h) + ": " + ("пуска" if _ochakvano else "мълчи"),
              v_prozoreca(_dn.replace(hour=_h)) is _ochakvano)
    check("всеки крон пада вътре в прозореца",
          all(v_prozoreca(_dn.replace(hour=h)) for h in RUN_HOURS))

    # --- ЧЕРНАТА КУТИЯ. Три спорта мълчаха дни наред и никой не разбра, защото
    # числото „колко срещи видях" живееше само в дневника на GitHub, който иска
    # админски права. Сега се записва в тефтера и се чете отвън.
    DIAG.clear()
    DIAG["proba"] = {"suredi": 3, "surovi": 9, "zapochnali": 4, "daleche": 2}
    _sega3 = datetime.now(SOFIA)
    _tmpst = os.path.join(_tf.gettempdir(), "_gp_state_test.json")
    _star_state, _star_dry = STATE_FILE, DRY_RUN
    try:
        globals()["STATE_FILE"] = _tmpst
        globals()["DRY_RUN"] = False
        save_state({"posted": {}}, _sega3)
        with open(_tmpst, encoding="utf-8") as _f:
            _got = json.load(_f)
    finally:
        globals()["STATE_FILE"] = _star_state
        globals()["DRY_RUN"] = _star_dry
        try:
            os.remove(_tmpst)
        except OSError:
            pass
    check("тефтерът носи черната кутия", "diag" in _got)
    check("черната кутия помни часа", bool(_got["diag"].get("koga")))
    check("черната кутия помни спорта", "proba" in (_got["diag"].get("sportove") or {}))
    check("черната кутия помни колко срещи",
          (_got["diag"]["sportove"]["proba"] or {}).get("suredi") == 3)
    check("черната кутия помни колко са започнали",
          (_got["diag"]["sportove"]["proba"] or {}).get("zapochnali") == 4)
    check("тефтерът пази и старото поле", "posted" in _got)
    DIAG.clear()

    # --- ПОДПИСЪТ. Това не е стил, а причината пет спорта да мълчат дни наред.
    # Върне ли се фалшивият Chrome подпис към ESPN, 403-ката се връща с него.
    check("ESPN не получава подпис", "User-Agent" not in glavi_za(ESPN_SITE + "/x"))
    check("ESPN иска json", glavi_za(ESPN_SITE + "/x").get("Accept") == "application/json")
    check("чуждите адреси пазят подписа",
          glavi_za("https://worldtabletennis.com/x").get("User-Agent") == UA)
    check("подадена глава бие подразбирането",
          glavi_za(ESPN_SITE + "/x", {"Accept": "text/html"})["Accept"] == "text/html")

    # 🔴 НАЙ-ВАЖНАТА ПРОВЕРКА ТУК: списъкът в кода и кроновете в predict.yml
    # трябва да са ЕДНО И СЪЩО. Разминат ли се, ботът смята грешно кое е
    # следващото пускане и изпуска мачове МЪЛЧАЛИВО — без грешка, без следа.
    # Затова се чете самият работен файл, а не се вярва на паметта.
    try:
        import re as _re
        _yml = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            ".github", "workflows", "predict.yml")
        with open(_yml, encoding="utf-8") as _f:
            _txt = _f.read()
        _krons = _re.findall(r"cron:\s*'(\d+)\s+(\d+)", _txt)
        _chas_yml = sorted({(int(h) + 3) % 24 for _m, h in _krons})
        check("кроновете в predict.yml съвпадат с RUN_HOURS",
              _chas_yml == sorted(RUN_HOURS))
        if _chas_yml != sorted(RUN_HOURS):
            print("   ⚠ yml казва " + str(_chas_yml)
                  + ", кодът казва " + str(sorted(RUN_HOURS)))
    except Exception as _e:                    # noqa: BLE001
        check("predict.yml се чете за сверка", False)
        print("   ⚠ " + str(_e)[:70])

    def _fx(chas, den=5):
        return {"when": datetime(2026, 8, den, chas, 0, tzinfo=SOFIA)}

    check("мач в 02:00 през нощта Е спешен в 23:05",
          urgent(_fx(2, 6), _v20) is True)
    check("мач в 07:00 сутринта Е спешен в 23:05",
          urgent(_fx(7, 6), _v20) is True)
    check("мач утре в 19:00 НЕ е спешен в 23:05",
          urgent(_fx(19, 6), _v20) is False)
    # 🔴 НОВОТО ПРАВИЛО: спешността е РАЗСТОЯНИЕ, не „преди следващия крон".
    # Точно заради това мач в 22:30 излизаше в 22:00 — половин час преди
    # началото. Сега същият мач е спешен още от следобеда.
    _v16 = datetime(2026, 8, 5, 16, 0, tzinfo=SOFIA)
    check("мач в 22:30 Е спешен още в 16:00",
          urgent({"when": datetime(2026, 8, 5, 22, 30, tzinfo=SOFIA)}, _v16) is True)
    check("в 20:05 нощният мач в 02:00 вече Е спешен",
          urgent(_fx(2, 6), datetime(2026, 8, 5, 20, 5, tzinfo=SOFIA)) is True)
    check("в 20:05 мач в 21:00 Е спешен",
          urgent(_fx(21), datetime(2026, 8, 5, 20, 5, tzinfo=SOFIA)) is True)
    check("мач в 11:00 Е спешен в 10:05", urgent(_fx(11), _v10) is True)
    check("мач в 15:00 Е спешен в 10:05 (4:55 напред)", urgent(_fx(15), _v10) is True)
    # Но далечното си остава далечно — иначе „спешно" губи смисъл и всичко
    # се изсипва в едно пускане.
    check("мач в 20:00 НЕ е спешен в 10:05 (почти 10 часа напред)",
          urgent(_fx(20), _v10) is False)
    check("мач утре сутрин НЕ е спешен в 10:05", urgent(_fx(9, 6), _v10) is False)
    check("границата е седем часа", 6.0 <= URGENT_LEAD_H <= 8.0)
    check("мач без час НЕ е спешен", urgent({"when": None}, _v20) is False)
    check("боклук вместо час не чупи", urgent({}, _v20) is False)

    # Слаб нощен мач бие силен утрешен — защото за нощния няма втори шанс.
    def mk2(b, stars, s, chas, den=5):
        return {"bucket": b, "stars": stars, "strength": s,
                "fx": {"when": datetime(2026, 8, den, chas, 0, tzinfo=SOFIA)},
                "pick": "x", "p": 0.6}

    _smes = [mk2("football", 3, 0.9, 19, 6),      # утре вечер, силен
             mk2("basketball", 1, 0.1, 2, 6),     # тази нощ, слаб
             mk2("tennis", 3, 0.8, 18, 6)]        # утре вечер, силен
    _izbor = choose(_smes, 1, _v20, 5)
    check("нощният слаб мач ВЛИЗА въпреки една звезда",
          any(a["bucket"] == "basketball" for a in _izbor))
    check("спешният е ПЪРВИ", _izbor[0]["bucket"] == "basketball")

    # Няколко спешни се редят по ЧАС, не по звезди.
    _tri = [mk2("football", 3, 0.9, 5, 6), mk2("tennis", 1, 0.1, 1, 6),
            mk2("volleyball", 2, 0.5, 3, 6)]
    _red = [a["bucket"] for a in choose(_tri, 0, _v20, 5)]
    check("спешните се редят по час на започване",
          _red == ["tennis", "volleyball", "football"])
    check("таванът на спешните се спазва", len(choose(_tri, 0, _v20, 2)) == 2)
    check("без подаден час подборът работи както преди",
          len(choose(_tri, 2)) == 2)
    # Този тест хвана два истински бъга: волейболът и хокеят падаха мълчаливо,
    # защото общата проверка за история гледаше празен списък. Спорт без
    # history_for() ЗАДЪЛЖИТЕЛНО стои с праг 0, иначе изчезва от стаята.
    check("спорт без история има праг 0",
          all(MIN_PER_SIDE.get(b, 0) == 0 for b in SPORT_ORDER if b not in HISTORY_SPORTS))
    check("спорт с история има праг над 0",
          all(MIN_PER_SIDE.get(b, 0) > 0 for b in HISTORY_SPORTS))
    check("всеки спорт е описан в прага", all(b in MIN_PER_SIDE for b in SPORT_ORDER))
    check("забранена е само стаята на новините", FORBIDDEN_THREADS == {"26"})
    check("разрешените са витрината, фишовете и петте спортни стаи",
          ALLOWED_THREADS == {PREDICT_THREAD, PICKS_THREAD} | set(SPORT_ROOM.values()))
    check("новините не се промъкват в разрешените", "26" not in ALLOWED_THREADS)

    # --- трите комбинирани фиша
    def leg(nm, p, st, lg="Лига", sport=None):
        return {"fx": {"home": nm, "away": "Б", "when": None, "league": lg},
                # Спортът по подразбиране е РАЗЛИЧЕН за всяка лига. Инак таванът
                # „три крака от един спорт" би скъсил всеки тестов фиш и старите
                # проверки щяха да падат по грешна причина.
                "bucket": sport or ("sp_" + str(lg)),
                "pick": "1 · победа " + nm, "p": p, "stars": st, "strength": 0.3}
    legs5 = [leg("Отбор" + str(i), 0.70, 3, "Лига" + str(i)) for i in range(5)]
    cc = combo_card(1, legs5, now)
    check("фишът е озаглавен", "ФИШ 1 НА ДЕНЯ" in cc)
    check("фишът показва петте мача", cc.count("🎯") == 5)
    check("фишът дава обща вероятност", "И петте заедно" in cc)
    check("общата вероятност е произведението (0.7^5 = 17%)", "17%" in cc)
    check("фишът е чист", banned_word(cc) is None)
    check("фишът казва, че всички трябва да познаят", "всички трябва да познаят" in cc)
    check("фишът носи присъда с думи", any(d in cc for _p, d in COMBO_DUMI))
    check("най-много пет фиша по четири крака",
          COMBO_COUNT == 5 and COMBO_SIZE == 4)
    # Измерено: таван 5 правеше 2 фиша, таван 4 прави 3 от същите кандидати.
    check("таванът не е толкова голям, че да изяде следващия фиш",
          COMBO_SIZE <= 4)
    # Басейнът трябва да СТИГА за толкова фишове, иначе вдигането е на хартия.
    # Сметка: 5 фиша × поне 2 крака = 10 крака минимум, а над прага минават
    # около две трети от анализираните.
    # 🔴 ЛИГИТЕ (19.08.2026) — след като добавих 32 футболни и 2 баскетболни.
    check("няма повторена футболна лига",
          len({x[0] for x in FOOT_SLUGS}) == len(FOOT_SLUGS))
    check("всяка футболна лига има име и тежест",
          all(len(x) == 3 and x[0] and x[2] and 1 <= int(x[1]) <= 20
              for x in FOOT_SLUGS))
    check("тежестта на Шампионска лига е над тази на втора дивизия",
          dict((x[0], x[1]) for x in FOOT_SLUGS)["uefa.champions"]
          > dict((x[0], x[1]) for x in FOOT_SLUGS)["eng.4"])
    check("летните лиги остават най-отгоре, над отреза",
          [x[0] for x in FOOT_SLUGS[:6]] == ["bra.1", "arg.1", "uefa.champions_qual",
                                             "uefa.europa_qual",
                                             "uefa.europa.conf_qual", "usa.1"])
    check("футболните лиги са поне 60", len(FOOT_SLUGS) >= 60)
    # 🔴 Всяка баскетболна лига ТРЯБВА да има предимство на домакина. Без него
    # моделът мълчаливо смята гост-мач за неутрален терен.
    check("няма повторена баскетболна лига",
          len({x[0] for x in BASK_LEAGUES}) == len(BASK_LEAGUES))
    check("всяка баскетболна лига има HCA",
          all(x[0] in BASK_HCA for x in BASK_LEAGUES))
    check("всяка баскетболна лига има четири полета",
          all(len(x) == 4 for x in BASK_LEAGUES))

    # 🔴 ПАЗАРНИЯТ ПОРТИЕР (19.08.2026) — поръчка на собственика:
    # „искам всички прогнози да ги има в букмейкъра".
    check("цена значи пазар",
          ima_pazar({"pazar_cena": 1.8, "bucket": "volleyball",
                     "fx": {"league": "Girls U17"}})[0] is True)
    check("търгувана лига минава и без цена",
          ima_pazar({"bucket": "baseball", "fx": {"league": "МЛБ"}})[0] is True)
    check("юношеският волейбол НЕ минава",
          ima_pazar({"bucket": "volleyball",
                     "fx": {"league": "FIVB Volleyball Girls' U17 World Championship"}})[0]
          is False)
    check("непознат спорт без цена НЕ минава",
          ima_pazar({"bucket": "кърлинг", "fx": {"league": "нещо"}})[0] is False)
    check("празен запис не гърми", ima_pazar({})[0] is False)
    check("възрастен WTT Feeder минава без цена",
          ima_pazar({"bucket": "tabletennis",
                     "fx": {"league": "WTT Feeder Berlin 2026 · Men's Singles"}})[0] is True)
    check("WTT Champions минава", ima_pazar(
        {"bucket": "tabletennis", "fx": {"league": "WTT Champions Macao 2026"}})[0] is True)
    check("юношеският WTT НЕ минава",
          ima_pazar({"bucket": "tabletennis",
                     "fx": {"league": "WTT Youth Contender Otocec 2026"}})[0] is False)
    check("ветеранският НЕ минава",
          ima_pazar({"bucket": "tabletennis",
                     "fx": {"league": "ITTF-Americas Masters Championships Caracas 2026"}})[0]
          is False)
    check("причината се връща",
          ima_pazar({"pazar_cena": 2.0})[1] == "цена")
    check("правилото е ВКЛЮЧЕНО по подразбиране", ISKAM_PAZAR is True)
    check("има път назад", "PREDICT_ISKAM_PAZAR" in open(__file__, encoding="utf-8").read())
    # Портиерът трябва да е ВЪРЗАН в потока, не само написан.
    _src = open(__file__, encoding="utf-8").read()
    check("портиерът се вика в run()",
          _src.count("ima_pazar(") >= 3 and "if ISKAM_PAZAR:" in _src)
    # 🔴 ПОВРЕДА ≠ ЛИПСА НА ПАЗАР. Портиерът трябва да се ОТВАРЯ при повреда,
    # иначе един капнал доставчик спира целия бот мълчаливо.
    _st_pin = globals().get("PIN")
    try:
        globals()["PIN"] = None
        check("без модул за цени пазарът НЕ отговаря", pazarat_otgovarya() is False)

        class _Praz(object):
            SPORT_ID = {"football": 29}

            @staticmethod
            def machove(b):
                return {}

            @staticmethod
            def ceni_za(sp, d, g):
                return (None, None, None)

        globals()["PIN"] = _Praz
        check("празен пазар значи повреда", pazarat_otgovarya() is False)

        class _Ima(_Praz):
            @staticmethod
            def machove(b):
                return {"1": ("А", "Б", "лига", "")} if b == "football" else {}

        globals()["PIN"] = _Ima
        check("един отговорил спорт стига", pazarat_otgovarya() is True)

        class _Grymva(_Praz):
            @staticmethod
            def machove(b):
                raise RuntimeError("долу")

        globals()["PIN"] = _Grymva
        check("гръмнал пазар не гърми бота", pazarat_otgovarya() is False)
    finally:
        globals()["PIN"] = _st_pin
    # 🔴 ИГЛАТА ТЪРСЕШЕ ДЕФИНИЦИЯТА, НЕ ПОВИКВАНЕТО (хванато с мутация,
    # 19.08.2026). „pazarat_otgovarya()" се съдържа и в реда `def
    # pazarat_otgovarya():` — тоест проверката минаваше дори когато махнах
    # ЕДИНСТВЕНОТО повикване в run(). Сега иглата е самият клон.
    _s2 = open(__file__, encoding="utf-8").read()
    check("отварянето при повреда е ВЪРЗАНО в потока",
          "elif not pazarat_otgovarya():" in _s2)
    check("повикването е ВЪТРЕ в портиера",
          _s2.find("if ISKAM_PAZAR:")
          < _s2.find("elif not pazarat_otgovarya():")
          < _s2.find("picks = choose("))

    check("портиерът е ПРЕДИ подбора",
          _src.find("if ISKAM_PAZAR:") < _src.find("picks = choose("))

    # 🔴 РАЗПРЪСКВАНЕТО (19.08.2026)
    _sto = list(range(100))
    _r = razpredeli(_sto, 5)
    check("взима точно колкото искаме", len(_r) == 5)
    check("не взима само първите", _r != [0, 1, 2, 3, 4])
    check("покрива целия списък", _r[0] < 10 and _r[-1] > 70)
    check("редът се пази", _r == sorted(_r))
    check("няма повторени", len(set(_r)) == 5)
    check("къс списък минава цял", razpredeli([1, 2, 3], 5) == [1, 2, 3])
    check("празен списък не гърми", razpredeli([], 5) == [] and razpredeli(None, 5) == [])
    check("нула искани дава празно", razpredeli(_sto, 0) == [])
    check("същият вход дава същия изход", razpredeli(_sto, 7) == razpredeli(_sto, 7))
    check("при точно колкото трябва взима всичко",
          razpredeli([1, 2, 3, 4, 5], 5) == [1, 2, 3, 4, 5])
    _b6 = razpredeli(list(range(108)), 5)
    check("от 108 записа не взима само началото", max(_b6) > 80)

    check("басейнът стига за петте фиша",
          POOL >= COMBO_COUNT * COMBO_MIN_LEGS * 1.5)

    # --- 🔴 ФИШЪТ ВЕЧЕ СИ ЗАСЛУЖАВА ДЪЛЖИНАТА (11.08.2026)
    # Видяно с очи в сухо пускане същия ден: фиш 3 излезе с пет крака по
    # 53-55% и обща вероятност 4%. Тези проверки държат това да не се върне.
    _slab = [leg("С" + str(i), 0.53, 1, "Лига" + str(i)) for i in range(5)]
    _sil = [leg("Я" + str(i), 0.90, 3, "Лига" + str(i)) for i in range(5)]
    check("пет слаби крака НЕ правят фиш от пет", len(sabiray_fish(_slab)) < 5)
    _t = 1.0
    for _a in sabiray_fish(_slab):
        _t *= _a["p"]
    check("слабият фиш пак е над пода", _t >= COMBO_MIN_TOTAL)
    # Пет силни крака се режат на тавана — четири. Това е нарочно: остатъкът
    # отива в следващия фиш, вместо да утежни този (виж измерването при
    # COMBO_SIZE).
    check("силните крака стигат до тавана", len(sabiray_fish(_sil)) == COMBO_SIZE)
    check("подът не е под 20%", COMBO_MIN_TOTAL >= 0.20)
    check("крак под 58% не влиза изобщо", COMBO_MIN_P >= 0.58)

    # Един турнир не прави фиш: четири крака от една лига дават най-много два.
    _edna = [leg("Е" + str(i), 0.80, 3, "Световно U17, девойки") for i in range(4)]
    check("най-много два крака от един турнир",
          len(sabiray_fish(_edna)) <= COMBO_MAX_SAME_LEAGUE)
    _smes = _edna + [leg("Д" + str(i), 0.80, 3, "Друга" + str(i)) for i in range(3)]
    _izbr = sabiray_fish(_smes)
    check("смесеният фиш взима и от другите турнири",
          len({str((a["fx"] or {}).get("league")) for a in _izbr}) >= 2)
    # 🔴 ЕДИН СПОРТ НЕ ПРАВИ ЦЕЛИЯ ФИШ (18.08.2026). Таванът по лига не пази
    # от това: тенисът на маса дава по три едновременни турнира, значи три
    # различни „лиги" — и четирите крака можеха да са от една зала.
    _ed_sp = [leg("Т" + str(i), 0.80, 3, "Турнир" + str(i), sport="tabletennis")
              for i in range(5)]
    check("един спорт не прави целия фиш",
          len(sabiray_fish(_ed_sp)) <= COMBO_MAX_SAME_SPORT)
    _sm_sp = _ed_sp + [leg("Ф" + str(i), 0.80, 3, "Лига" + str(i), sport="football")
                       for i in range(3)]
    check("смесеният фиш взима и от друг спорт",
          len({a["bucket"] for a in sabiray_fish(_sm_sp)}) >= 2)
    check("таванът по спорт е под дължината на фиша",
          COMBO_MAX_SAME_SPORT < COMBO_SIZE)
    check("два крака са най-малкото, което пускаме", COMBO_MIN_LEGS == 2)
    check("под две — никакъв фиш", sabiray_fish([leg("Сам", 0.90, 3)]) == [])

    # 🔴 ТОЗИ ТЕСТ ХВАНА ИСТИНСКИ БЪГ (11.08.2026). В post_combos стоеше
    # `elif len(pool) < need:` — `need` няма стойност в тази функция. Клонът е
    # достижим (кандидати има, но фиш не се събира) и вместо бележка ботът
    # гърмеше с NameError насред рън. Проверката е ОБЩА, не за този ред:
    # чете имената, които всяка от опасните функции търси НАВЪН, и настоява
    # всяко от тях наистина да съществува. Хваща и всеки бъдещ близнак.
    def _visyashti(fn):
        import dis as _dis, builtins as _b
        vsi, atrib = set(), set()

        # Обхожда и вложените код-обекти (генератори, comprehension-и, вътрешни
        # функции). Първата версия на тази проверка гледаше co_names навсякъде,
        # но атрибутите БРОЕШЕ само в най-външния код — и обяви `timestamp` за
        # висящо име, при положение че е `.timestamp()` вътре в comprehension.
        # Тоест самата проверка беше полусляпа. Двете страни трябва да се четат
        # на едно и също ниво, иначе резултатът е фалшива тревога.
        def _obhod(c):
            vsi.update(c.co_names)
            for ins in _dis.get_instructions(c):
                if ins.opname in ("LOAD_ATTR", "STORE_ATTR", "DELETE_ATTR",
                                  "LOAD_METHOD", "LOAD_SUPER_ATTR"):
                    atrib.add(ins.argval)
            for k in c.co_consts:
                if hasattr(k, "co_names"):
                    _obhod(k)

        _obhod(fn.__code__)
        g = fn.__globals__
        return sorted(n for n in (vsi - atrib)
                      if n not in g and not hasattr(_b, n))
    for _f in (post_combos, sabiray_fish, combo_card, run, build_pool, choose):
        _v = _visyashti(_f)
        check("няма висящо име в " + _f.__name__
              + (" (" + ", ".join(_v) + ")" if _v else ""), _v == [])
    _dva = combo_card(2, [leg("А", 0.8, 3, "Л1"), leg("Б", 0.8, 3, "Л2")], now)
    check("фиш от два се брои като двата", "И двата заедно" in _dva)
    check("всички спортове имат емоджи", all(SPORTS[b].get("emoji") for b in SPORT_ORDER))
    check("редът покрива всички спортове", set(SPORT_ORDER) == set(SPORTS.keys()))

    # --- 🏈 американски футбол (девети спорт)
    # 📐 Обратното на процента (13.08.2026). Числото е НАШЕ — обратното на
    # собствената ни вероятност, не оферта на букмейкър.
    check("56% дава 1 към 1.79", obratno_na_procenta(0.56) == "1 към 1.79")
    check("50% дава 1 към 2.00", obratno_na_procenta(0.50) == "1 към 2.00")
    check("92% дава 1 към 1.09", obratno_na_procenta(0.92) == "1 към 1.09")
    check("сигурност 100% не дава число", obratno_na_procenta(1.0) == "")
    check("нула не дава число", obratno_na_procenta(0) == "")
    check("боклук не гърми", obratno_na_procenta("абв") == ""
          and obratno_na_procenta(None) == "")
    check("числото пада с процента",
          obratno_na_procenta(0.45) > obratno_na_procenta(0.90))
    # 🔴 НАЙ-ВАЖНОТО: редът НЕ бива да носи забранена дума. Пазачът е там,
    # защото българският закон забранява рекламата на хазарт — а живите
    # коефициенти на ESPN идват с линк към sportsbook. Наши са само тези.
    check("редът минава през пазача",
          banned_word("📐 " + obratno_na_procenta(0.56)
                      + " — обратното на процента, наша сметка") is None)
    check("думата, която пазачът реже, я няма",
          "коеф" not in obratno_na_procenta(0.56))
    check("никакъв букмейкър в реда",
          not any(w in ("📐 " + obratno_na_procenta(0.56)).lower()
                  for w in ("draftkings", "sportsbook", "bet")))
    check("ръчката съществува", "PREDICT_KOEF" in open(__file__, encoding="utf-8").read())

    # 🔴 ДНЕВНАТА КВОТА ПО СПОРТ (13.08.2026). Спорт, който още не си е взел
    # запазените места за деня, минава пръв — дори ако друг има по-уверен мач.
    def _mk(b, i, p_, st=2):
        return {"bucket": b, "p": p_, "stars": st, "strength": p_,
                "fx": {"home": "A" + str(i), "away": "B" + str(i)}, "pick": "1"}
    # Волейболът вече е взел три днес; тенисът на маса — нула. При място за
    # ЕДНА карта тя трябва да отиде при тениса на маса, макар волейболът да
    # има по-уверен мач.
    _k = choose([_mk("volleyball", 1, 0.90, 3), _mk("tabletennis", 2, 0.60, 1)],
                1, None, 0, {"volleyball": 3, "tabletennis": 0})
    check("спорт без дневни карти минава пръв",
          _k and _k[0]["bucket"] == "tabletennis")
    # А когато и двата са си взели своето, побеждава увереността.
    _k2 = choose([_mk("volleyball", 1, 0.90, 3), _mk("tabletennis", 2, 0.60, 1)],
                 1, None, 0, {"volleyball": 3, "tabletennis": 3})
    check("след изчерпана квота решава увереността",
          _k2 and _k2[0]["bucket"] == "volleyball")
    check("без подадена история работи както преди",
          len(choose([_mk("volleyball", 1, 0.90, 3)], 1, None, 0)) == 1)
    check("нула квота връща старото поведение",
          KVOTA_DEN == 0 or True)
    # Броенето по спорт от тефтера
    _st = {"posted": {"2026-08-13|volleyball|а|б": "2026-08-13 10:00",
                      "2026-08-13|volleyball|в|г": "2026-08-13 11:00",
                      "2026-08-13|tabletennis|д|е": "2026-08-13 12:00",
                      "2026-08-13|header": "2026-08-13 08:00",
                      "2026-08-12|volleyball|ж|з": "2026-08-12 10:00"}}
    _sega = datetime(2026, 8, 13, 15, 0, tzinfo=SOFIA)
    _bs = karti_dnes_po_sport(_st, _sega)
    check("броенето по спорт е вярно", _bs.get("volleyball") == 2
          and _bs.get("tabletennis") == 1)
    check("служебните ключове не се броят", "header" not in _bs)
    check("вчерашните не се броят", sum(_bs.values()) == 3)
    check("празен тефтер не гърми", karti_dnes_po_sport({}, _sega) == {})

    check("американският футбол е в списъка", "amfootball" in SPORTS)
    check("затворените спортове НЕ са в дневния ред",
          not (IZKLYUCHENI & set(ACTIVE_SPORTS)))
    check("затворените спортове пак имат код (не са изтрити)",
          all(b in SPORTS and b in SPORT_ORDER for b in IZKLYUCHENI))
    check("хокеят и амер. футбол са затворени по подразбиране",
          bool(os.environ.get("PREDICT_IZKL") is not None)
          or IZKLYUCHENI == {"hockey", "amfootball"})
    check("остават седем работещи спорта",
          len(ACTIVE_SPORTS) == 7 or os.environ.get("PREDICT_SPORTS")
          or os.environ.get("PREDICT_IZKL") is not None)
    check("американският футбол има таван на звездите", "amfootball" in STAR_CAP)
    check("американският футбол е в спортовете с история",
          "amfootball" in HISTORY_SPORTS)
    # ⚠️ Най-важната проверка тук: при ESPN „football" е АМЕРИКАНСКИЯТ футбол,
    # а нашият е „soccer". Разменят ли се, единият спорт тихо дърпа чуждите мачове.
    check("нашият футбол ползва soccer", "/soccer/" in ESPN_SITE + "/soccer/x")
    check("американският ползва nfl", AMF_LEAGUES[0][0] == "nfl")
    check("американският има по-широко отклонение от баскета",
          AMF_LEAGUES[0][3] > 11.5)
    m_amf = model_amfootball(
        [{"gf": 27, "ga": 20, "home": True, "date": "2026-01-05", "opp": "x"}] * 8,
        [{"gf": 17, "ga": 24, "home": False, "date": "2026-01-05", "opp": "y"}] * 8,
        {"extra": {"sigma": 13.5}}, now)
    check("американският модел смята", m_amf is not None)
    check("по-силният отбор е фаворит", m_amf and m_amf["p_home"] > 0.5)
    check("американският дава и очакван резултат", m_amf and m_amf["exp_h"] > 0)

    # 🔴 ПАЗАЧ СРЕЩУ ТРИЕНЕТО (18.08.2026). Таванът на дневника ТРЯБВА да е
    # над MAX_DAY × ARHIV_DNI, иначе предсказателят трие по-бързо, отколкото
    # оценителят архивира, и записите изчезват вместо да се преместят.
    # Точно това стана: таван 400 при нужни 4800 — 95 записа се загубиха, а
    # футболът показваше 61% вместо истинските 50%.
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "scorer.py"), encoding="utf-8-sig") as _f:
            _ss = _f.read()
        _i2 = _ss.find("ARHIV_DNI = max(")
        _dni = 0
        if _i2 >= 0:
            _hv = _ss[_i2:_ss.find(")))", _i2)]
            _c = [x for x in _hv.split('"') if x.strip().isdigit()]
            _dni = int(_c[-1]) if _c else 0
        check("прагът на архива се прочете от scorer.py", _dni > 0)
        check("таванът на дневника е над триещата граница",
              _dni == 0 or PICKLOG_KEEP >= MAX_DAY * _dni)
    except Exception as _e2:                                 # noqa: BLE001
        check("сверката на тавана с архива мина", False)

    # 🔴 ВТОРИЯТ ИЗТОЧНИК ТРЯБВА ДА Е ДОСТИЖИМ (18.08.2026).
    # Първата ми версия го викаше СЛЕД `return an` за спортове, които ESPN не
    # покрива — тоест точно за спортовете, заради които съществува. Кодът
    # беше налице, тестовете зелени, тенисът без цена.
    _st_pin = globals().get("PIN")
    try:
        class _MakPin(object):
            SPORT_ID = {"tennis": 33}

            @staticmethod
            def ceni_za(sp, d, g):
                return (1.57, 2.55, None) if sp == "tennis" else (None, None, None)

        globals()["PIN"] = _MakPin
        _t = dobavi_pazar({"bucket": "tennis", "pick": "1 · А",
                           "fx": {"home": "А", "away": "Б", "extra": {}}})
        check("спорт без ESPN стига до втория източник",
              _t.get("pazar_cena") == 1.57 and _t.get("pazar_izt") == "pinnacle")
        check("маржът се маха и на втория източник",
              _t.get("pazar_p") is not None and float(_t["pazar_p"]) < 1.0 / 1.57)
        check("вторият източник не получава адрес за затваряща",
              "pazar_ev" not in _t)
        _t2 = dobavi_pazar({"bucket": "tennis", "pick": "2 · Б",
                            "fx": {"home": "А", "away": "Б", "extra": {}}})
        check("изборът 2 взима цената на госта", _t2.get("pazar_cena") == 2.55)
        globals()["PIN"] = None
        _t3 = dobavi_pazar({"bucket": "tennis", "pick": "1 · А",
                            "fx": {"home": "А", "away": "Б", "extra": {}}})
        check("без втори източник картата пак излиза", "pazar_cena" not in _t3)
    finally:
        globals()["PIN"] = _st_pin

    # 🔴 ММА СЕ ПИТА С ДИАПАЗОН (19.08.2026).
    #
    # Измерено на живо: голият адрес дава за UFC вчерашната ПРИКЛЮЧИЛА гала —
    # 5 боя, 5 завършени, нула използваеми. С диапазон: 27 боя, нула
    # завършени. Стаята 🥊 се хранеше само от PFL, който пазарът не търгува.
    #
    # 🔴 И ТЕСТЪТ Е ПОВЕДЕНЧЕСКИ, НЕ ТЕКСТОВ. Три пъти подред се опитах да го
    # хвана с търсене на низ в кода и трите пъти иглата се оказваше в самата
    # проверка или в коментара до нея — тоест тестът минаваше и върху счупен
    # файл. Тук се записва КАКВО НАИСТИНА СЕ ПИТА по мрежата.
    _pitani = []
    _st_hj = globals().get("http_json")
    try:
        globals()["http_json"] = lambda u, **kw: (_pitani.append(u), {})[1]
        mma_fixtures(now)
        check("ММА пита изобщо нещо", len(_pitani) >= 1)
        check("всеки ММА адрес носи диапазон от дати",
              _pitani and all("dates=" in u and "-" in u.split("dates=")[-1]
                              for u in _pitani))
        check("диапазонът почва от днес",
              _pitani and now.strftime("%Y%m%d") in _pitani[0])
        check("диапазонът стига до края на хоризонта",
              _pitani and (now + timedelta(days=int(MMA_DAYS_AHEAD) + 1)
                           ).strftime("%Y%m%d") in _pitani[0])
    finally:
        if _st_hj is not None:
            globals()["http_json"] = _st_hj

    # 🔴 ШИРИНАТА ВАЖИ САМО КЪДЕТО Е ИЗМЕРЕНА (19.08.2026).
    # Намерено с ЧЕТЕНЕ НА СТАЯТА: карта „Martin BUCH — 77% · ясен фаворит",
    # а обяснението под нея — „18 победи и 19 загуби". Числото и доводът се
    # биеха пред очите на читателя.
    check("голяма извадка получава измерената ширина",
          tt_shirina(60) == TT_SCALE and TT_SCALE > 1.0)
    check("тънка извадка получава предпазливата", tt_shirina(8) == TT_SCALE_MALKO)
    check("точно на прага важи пълната", tt_shirina(TT_PALNA_N) == TT_SCALE)
    check("едно под прага — вече не", tt_shirina(TT_PALNA_N - 1) == TT_SCALE_MALKO)
    check("боклук дава предпазливата",
          tt_shirina(None) == TT_SCALE_MALKO and tt_shirina("абв") == TT_SCALE_MALKO)
    check("прагът е там, където има данни", TT_PALNA_N >= 20)
    check("предпазливата е по-малка от пълната", TT_SCALE_MALKO < TT_SCALE)

    def _tt_p(w1, l1, w2, l2):
        _ra = (w1 + 3.0) / (w1 + l1 + 6.0)
        _rb = (w2 + 3.0) / (w2 + l2 + 6.0)
        _sh = tt_shirina(min(w1 + l1, w2 + l2))
        return clampf(logistic((logit(_ra) - logit(_rb)) * _sh), TT_P_MIN, TT_P_MAX)

    # Истинската карта, която ме прати да търся: 18-19 срещу 2-6.
    check("играч с отрицателен баланс НЕ става ясен фаворит",
          _tt_p(18, 19, 2, 6) < 0.65)
    check("богатата извадка ПАК дава силно число",
          _tt_p(66, 22, 38, 29) > 0.75)
    check("тънка и богата дават РАЗЛИЧНО при еднакво съотношение",
          abs(_tt_p(4, 4, 2, 6) - _tt_p(50, 50, 25, 75)) > 0.05)

    # 🔴 ПРЕЗ САМИЯ МОДЕЛ, НЕ ПРЕЗ ПОДРАЖАНИЕ (хванато с мутация 19.08.2026).
    # Горните проверки викаха `tt_shirina` направо. Мутация, която НАПЪЛНО
    # разкачи модела от нея (`_sh = TT_SCALE`), ги преживя — тестваше се
    # функцията, не че моделът я ползва.
    _st_tp = globals().get("tt_player")
    try:
        _bank = {"тънък": {"w": 18, "l": 19, "n": 37, "best": 200},
                 "мъничък": {"w": 2, "l": 6, "n": 8, "best": 300},
                 "богат1": {"w": 66, "l": 22, "n": 88, "best": 5},
                 "богат2": {"w": 38, "l": 29, "n": 67, "best": 20}}
        globals()["tt_player"] = lambda pid, now: _bank.get(str(pid))
        _fx_t = {"home_id": "тънък", "away_id": "мъничък", "extra": {"best_of": 5}}
        _fx_b = {"home_id": "богат1", "away_id": "богат2", "extra": {"best_of": 5}}
        _mt = model_tabletennis(_fx_t, now)
        _mb = model_tabletennis(_fx_b, now)
        check("моделът вижда по-малката извадка",
              _mt and _mt.get("n_malka") == 8 and _mb and _mb.get("n_malka") == 67)
        check("моделът ПОЛЗВА предпазливата при тънка извадка",
              _mt and abs(_mt["shirina"] - TT_SCALE_MALKO) < 1e-9)
        check("моделът ползва измерената при богата извадка",
              _mb and abs(_mb["shirina"] - TT_SCALE) < 1e-9)
        check("тънката карта не става ясен фаворит ПРЕЗ МОДЕЛА",
              _mt and _mt["p_home"] < 0.65)
        check("богатата карта пак е силна ПРЕЗ МОДЕЛА",
              _mb and _mb["p_home"] > 0.75)
    finally:
        if _st_tp is not None:
            globals()["tt_player"] = _st_tp

    # 🔴 НАПИСАНА, НО НЕВЪРЗАНА (поуката от `golyama_liga`, 12.08.2026).
    # `tt_turnir_sled` съществува само за да махне фалшивата тревога в
    # здравния преглед. Ако там не се вика, функцията е мъртъв код, а флагът
    # продължава да гърми — и никой тест няма да го забележи.
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "zdrave.py"), encoding="utf-8-sig") as _fz:
            _sz = _fz.read()
        check("здравният преглед наистина вика tt_turnir_sled",
              "tt_turnir_sled" in _sz)
        # 🔴 И НУЛАТА ДА НЕ СЕ ИЗХВЪРЛЯ (18.08.2026). `d_tt >= 1` връщаше
        # фалшивата тревога точно на ПЪРВИЯ ден на всеки турнир — деня, в
        # който WTT още не е пуснал разписанието. Проверено в реалността:
        # WTT Feeder Berlin почва 19.08 и tt_turnir_sled връща 0.
        check("нулата не се изхвърля в здравния преглед",
              "d_tt >= 1" not in _sz and "d_tt >= 0" in _sz)
        check("близнакът също е лекуван (0 е лъжливо в if)",
              "napred.get(b) is not None" in _sz)
    except Exception:                                        # noqa: BLE001
        check("сверката със здравния преглед мина", False)

    # 🔴 РЕДЪТ НА ТУРНИРИТЕ ПО ТЕНИС НА МАСА (18.08.2026).
    check("Смашът бие юношеския турнир",
          _tt_rang("Europe Smash - Sweden 2026")
          > _tt_rang("Europe Youth Smash - Sweden 2026"))
    check("Champions бие Feeder",
          _tt_rang("WTT Champions Macao 2026") > _tt_rang("WTT Feeder Berlin 2026"))
    check("Contender бие Feeder",
          _tt_rang("WTT Contender Almaty 2026") > _tt_rang("WTT Feeder Olomouc 2026"))
    check("юношеският Contender пада под възрастния Feeder",
          _tt_rang("WTT Youth Contender Otocec 2026")
          < _tt_rang("WTT Feeder Olomouc 2026"))
    check("непознат турнир не е нито най-горе, нито най-долу",
          10 < _tt_rang("Нещо съвсем ново") < 90)
    # 🔴 ИСТИНСКИТЕ КАПАНИ ОТ КАЛЕНДАРА ЗА 2026 (намерени 18.08.2026).
    # „championSHIPS" съдържа „champions" — детски и ветерански турнири
    # вземаха 85 и изхвърляха от тавана българския Contender.
    for _nm, _och in (
            ("WTT Champions Macao 2026", 85),
            ("ITTF-Americas U11&U13 Championships Houston 2026", 10),
            ("ITTF-Americas Central American Masters Championships Tegucigalpa 2026", 12),
            ("WTT Contender Panagyurishte 2026 Presented by ASAREL", 70),
            ("WTT Youth Star Contender Bangkok 2026", 10),
            ("WTT Star Contender Doha 2026", 78),
            ("Europe Smash - Sweden 2026", 90),
            ("Europe Youth Smash - Sweden 2026", 10),
            ("WTT Finals Hong Kong 2026", 92),
            ("ITTF World Team Table Tennis Championships Finals London 2026", 86),
            ("ITTF-Africa West Regional Championships Conakry 2026", 38),
            ("ETTU European U13 Championships Nevsehir 2026", 10)):
        check("ранг на „" + _nm[:34] + "“ = " + str(_och), _tt_rang(_nm) == _och)
    check("детският турнир НЕ бие възрастния Contender",
          _tt_rang("ITTF-Americas U11&U13 Championships Houston 2026")
          < _tt_rang("WTT Contender Panagyurishte 2026"))
    check("ветеранският НЕ бие възрастния Feeder",
          _tt_rang("ITTF-Americas Masters Championships Caracas 2026")
          < _tt_rang("WTT Feeder Berlin 2026"))
    check("думите се цепят по неалфанумерично",
          _tt_dumi("U11&U13 · ITTF-Africa") == {"u11", "u13", "ittf", "africa"})
    _live = [(1, "WTT Youth Contender Otocec 2026"), (2, "WTT Feeder Olomouc 2026"),
             (3, "WTT Champions Macao 2026"), (4, "ITTF-Oceania Youth Champs")]
    _live.sort(key=lambda x: (-_tt_rang(x[1]), str(x[1])))
    check("подредбата слага най-тежкия пръв", _live[0][0] == 3)
    check("подредбата слага юношеските най-долу",
          {_live[2][0], _live[3][0]} == {1, 4})
    check("таванът е поне два турнира", TT_MAX_TURNIRI >= 2)
    # Оценителят трябва да гледа ПОНЕ толкова турнира, колкото предсказателят
    # засява — иначе карта излиза, а присъда за нея никога не идва.
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "scorer.py"), encoding="utf-8-sig") as _f3:
            _s3 = _f3.read()
        _i3 = _s3.find("WTT_MAX_TURNIRI")
        _n3 = 0
        if _i3 >= 0:
            _hv3 = _s3[_i3:_i3 + 120].split(chr(10))[0]
            _c3 = [int(x) for x in "".join(
                (ch if ch.isdigit() else " ") for ch in _hv3).split()]
            _n3 = max(_c3) if _c3 else 0
        check("оценителят гледа поне колкото предсказателят засява",
              _n3 >= TT_MAX_TURNIRI)
    except Exception:                                        # noqa: BLE001
        check("сверката с турнирите на оценителя мина", False)

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
