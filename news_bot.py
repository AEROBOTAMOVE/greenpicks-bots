# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БОТ №1 „НОВИНАРЯТ" 📰   (версия 3: ИСТИНСКИ СИЛНИ НОВИНИ)

ЖЕЛЕЗНИ ПРАВИЛА (заповед на шефа, без изключения):
  1. ВСИЧКИ новини отиват САМО в стая 26 „Новини" (env NEWS_THREAD_ID).
  2. Стаи 5/6/7/8 (Футбол, Баскетбол, Тенис на маса, Волейбол) НЕ получават новини —
     в тях влизат САМО срещите по направление.
  3. КАНАЛЪТ не получава новини — той е за човека-типстер.
  4. Стая 4 „Фишове на деня" е само за човека — бот не пише там.
  5. Вътре в стая 26 новините са РАЗДЕЛЕНИ ПО СПОРТ, в реда
     🏓 Тенис на маса → 🏐 Волейбол → 🏀 Баскетбол → ⚽ Футбол → 🥊 Бойни спортове
     → 📰 Други спортове. Спорт без новини се пропуска мълчаливо.
  6. Тих ден (нищо важно) = НЕ праща нищо. Тишината е злато.
  7. Постът е ЗАГЛАВИЕ + ЕДИН РЕД КОНТЕКСТ + ИЗТОЧНИК + СНИМКА. Нищо друго.
     Без поучения, без „18+", без съвети, без реклама на хазарт.

КАКВО Е НОВО В ТАЗИ ВЕРСИЯ (шефът: „новинарят да е МЕГА ДОБЪР и да дава силни новини"):

  A) ПОДРЕЖДАНЕТО Е ИСТИНСКО, НЕ ПО КЛЮЧОВА ДУМА.
     Всяка история получава РЕЙТИНГ от шест сили:
       • СЪГЛАСИЕ НА ИЗТОЧНИЦИТЕ — една и съща история в 2+ независими издания
         почти винаги Е новината на деня (най-тежката съставка);
       • СВЕЖЕСТ — от преди час тежи повече от вчерашното;
       • ВАЖНОСТ по думи (трансфер, уволнение, финал, титла, контузия…);
       • СПОРТОВЕТЕ НА ШЕФА (футбол, баскет, тенис на маса, волейбол, бойни) — с бонус;
       • БЪЛГАРСКА ДИРЯ (Лудогорец, Пулев, националите…) — с бонус, каналът е български;
       • НАКАЗАНИЯ — класации „Топ 10", коментари/мнения, „гледайте видео", тестове,
         прогнози за залози и магазинарски постове падат надолу или изобщо не тръгват.
     Затова първата новина във всяка секция е най-голямата, а не първата намерена.

  B) 🥊 БОЙНИ СПОРТОВЕ — нова, пълноправна секция (UFC/MMA/бокс/кикбокс/джудо).
     Осем проверени емисии + разпознаване по думи. ВНИМАНИЕ КЪМ „БОКС": думата
     тръгва само ако в заглавието НЯМА друг спорт, и никога при „Boxing Day",
     „box-to-box", „в бокса" (пит-лейн), „бокс офис", „наказателното поле".

  C) ЕДНА ИСТОРИЯ = ЕДИН ПОСТ. Записите се СГРУПИРВАТ преди избора: българското
     заглавие и английското за същото събитие стават една история — взимаме
     българското заглавие, НАЙ-ДОБРАТА снимка от всички източници, и пишем
     „също: Sportal, Dsport". Групата пази и паметта: утре нито един от вариантите
     не тръгва пак (sent_news.json помни ключовете на ВСИЧКИ участници).
     ЧЕСТНА ГРАНИЦА: сравняват се ДУМИ. Затова българското и английското заглавие
     за едно и също събитие („България победи Италия" / „Bulgaria stun Italy") НЕ
     се сливат — за това трябва транслитерация на имената, а тя носи риск да
     изяде истинска новина. Повторенията между БЪЛГАРСКИТЕ сайтове (истинският
     проблем на шефа) се хващат напълно.

  D) КОНТЕКСТЪТ Е ИСТИНСКИ РЕД. Взима се ПЪРВОТО ИЗРЕЧЕНИЕ от описанието на
     емисията, изчистено от боклук; ако то само преразказва заглавието — не се
     пише нищо (по-добре празно, отколкото шум).

  E) КАРТИНКИТЕ остават както шефът ги хареса: sendPhoto по адрес, при отказ
     втора снимка, при отказ чист текст. Новина не се губи заради снимка.

Пуска се от GitHub Actions 3x дневно. Помни пратеното в sent_news.json (комитва се обратно).
Бележка за деплой: файлът е писан БЕЗ обратни наклонени черти (нов ред = NL = chr(10),
regex-границите на думи = LB/RB, кавичките в regex = chr(34)/chr(39)).
Проверка: NEWS_MODE=selftest python news_bot.py   |   пробно: NEWS_DRY_RUN=1 python news_bot.py
Първо пълнене: NEWS_BACKFILL_DAYS=7 (взима до 7 дни назад, таван 14; пак само стая 26).
"""
import html
import json
import os
import re
import sys
import time
import hashlib
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

SOFIA = ZoneInfo("Europe/Sofia")
NL = chr(10)

# Печатът НИКОГА не убива бота: на гол Windows (без PYTHONIOENCODING) конзолен или
# пайпнат рън дава stdout в cp1252/cp1251 и кирилският WARN гърмеше с
# UnicodeEncodeError по средата на selftest-а. Принудително UTF-8 (както е на
# GitHub Actions) + errors=replace: и при най-странната конзола излиза текст, не краш.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")              # групата (-100...)
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")        # каналът — САМО за проверка, НЕ пишем в него
NEWS_THREAD_ID = os.environ.get("NEWS_THREAD_ID", "26") or "26"   # 📰 Новини — ЕДИНСТВЕНАТА стая
NEWS_ROOM_FALLBACK = "26"

# ✅ БЯЛ СПИСЪК: новинарят има право на ТОЧНО ЕДНА стая — 26 „Новини".
# Allowlist вместо blocklist: старият черен списък пускаше 9/27/3/11/328 и всяка
# бъдеща стая, а желязното правило е „новини САМО в 26". Всичко друго пада към 26.
ALLOWED_THREADS = {26}
# 🚫 Известните чужди стаи — поименно, за selftest-а (всяка ТРЯБВА да бъде отказана):
# 1 общ чат, 3 правила, 4 фишове (само човекът), 5/6/7/8 спортните стаи (само срещи),
# 9 резултати, 11 помощ, 27 прогнозите на бота, 328 бойни спортове (само боеве).
FORBIDDEN_THREADS = {1, 3, 4, 5, 6, 7, 8, 9, 11, 27, 328}

# --- граници на дума без обратна наклонена черта -----------------------------
# LB/RB заместват regex-границата на дума: „nba" да не се хваща в „fanbase".
# Заглавията се сравняват в малки букви, затова класът е само малки букви и цифри.
LB = "(?:^|[^0-9a-zа-я])"
RB = "(?:$|[^0-9a-zа-я])"


def wb(word):
    """Цяла дума (двустранна граница)."""
    return LB + word + RB


def wp(word):
    """Начало на дума (само лява граница) — за корени като „трансфер"."""
    return LB + word


# ============================================================ 🥊 БОЙНИ СПОРТОВЕ ==
# Три пласта, защото „бокс" е най-опасната дума в спортната журналистика.
#
# СИЛНИ думи — сами по себе си значат боен спорт, няма как да са друго.
COMBAT_STRONG = "|".join([
    wb("ufc"), wb("mma"), wb("мма"), wb("ммa"), wb("bkfc"), wb("bellator"), wb("pfl"),
    "октагон", "octagon", "смесени бойни", "бойни изкуства", "mixed martial",
    "муай тай", "muay thai", "кикбокс", "kickbox", wb("oktagon"),
    "макгрегър", "mcgregor", "нурмагомедов", wb("khabib"), "хабиб",
    "адесаня", "adesanya", "порие", "poirier", "махачев", "makhachev",
    wb("usyk"), "усик", "тайсън фюри", "tyson fury", "антъни джошуа", "anthony joshua",
    wb("canelo"), "канело", wp("пулев"), "джудо", wb("judo"), "таекуондо", "taekwondo",
    wb("карате"), wb("karate"), wb("сумо"), wb("sumo"), wb("самбо"), wb("sambo"),
    "ju-jitsu", "джиу-джицу", "grappling", "грaплинг",
])

# МЕКИ думи — значат боен спорт САМО ако в заглавието няма друг спорт.
# „Нокаут за Реал Мадрид" първо се хваща от футбола и никога не стига дотук.
COMBAT_SOFT = "|".join([
    wp("бокс"), wb("boxing"), wb("boxer"), wb("boxers"), "на ринга", "в ринга",
    "one championship", wp("нокаут"), wb("knockout"), wb("ко"), wp("нокдаун"),
    wb("fight night"), "боен спорт", wp("гладиатор"),
])

# КАПАНИ — тук думата „бокс/boxing" НИКОГА не значи боен спорт (проверени случаи):
# Boxing Day (футболният кръг след Коледа), box-to-box халф, „в бокса" = пит-лейн
# във Формула 1, „бокс офис", „наказателното поле" (penalty box).
COMBAT_TRAP = "|".join([
    "boxing day", "боксинг дей", "box-to-box", "box to box", "бокс-ту-бокс",
    "box office", "бокс офис", "penalty box", "наказателното поле",
    "в бокса", "от бокса", "към бокса", "боксовете", "пит бокс", "pit box",
    "формула 1", "formula 1", "formula one", "формула едно", wb("f1"),
    "ice box", "боксониера",
])


# 🎯 РАЗПОЗНАВАНЕТО ПО СПОРТ. РЕДЪТ Е ВАЖЕН: специфичните спортове ПРЕДИ футбола
# (волейболният ЦСКА съдържа „волейбол" -> хваща се преди клубното име във football).
#
# ⚠️ ВНИМАНИЕ: полето "thread" вече НЕ е стая 5/6/7/8 — всички стойности сочат към
# стая 26 „Новини". Новини в спортните стаи са ЗАБРАНЕНИ (правило 2). Полето стои
# само за обратна съвместимост (news_showcase.py го чете) и умишлено е пренасочено.
SPORT_ROOMS = {
    "combat":      {"thread": NEWS_THREAD_ID, "title": "🥊 БОЙНИ СПОРТОВЕ — новини",
                    "pat": COMBAT_STRONG},
    "tabletennis": {"thread": NEWS_THREAD_ID, "title": "🏓 ТЕНИС НА МАСА — новини",
                    "pat": "|".join(["тенис на маса", "table tennis", "ping pong", "пинг понг",
                                     wb("wtt"), wb("ittf"), wb("ettu"), "тенисът на маса"])},
    "volleyball":  {"thread": NEWS_THREAD_ID, "title": "🏐 ВОЛЕЙБОЛ — новини",
                    # ⚠️ НЕ слагай голото „volley" — във футбола „stunning volley" е удар с
                    # воле и би откраднал футболни новини в волейболната секция.
                    # 🔴 КОРЕНЪТ, не цялата дума (11.08.2026). Шаблонът търсеше
                    # „волейбол" и пропускаше думите на журналиста:
                    # „капитанът на ВОЛЕЙнационалите", „ЕвроВОЛЕЙ 2026".
                    # Измерено: и трите такива заглавия днес паднаха в „Други".
                    # Кирилското „волей" няма капана на английското volley
                    # („stunning volley") — проверено срещу футболните заглавия.
                    # ⚠️ НЕ голото „волей": то хваща и футболния удар
                    # („стунинг волей от Роналдо") — проверих го и падна.
                    # Затова изброяваме сложните думи поименно.
                    "pat": "|".join(["волейбол", "волейнацион", "евроволей",
                                     "суперволей", "волейна", "волейни",
                                     "volleyball", "siatkow", "pallavolo", wb("vnl"),
                                     wb("cev"), "plusliga", "superlega", "николов", "соколов",
                                     "казийски", "лига на нациите", "beach volley"])},
    "basketball":  {"thread": NEWS_THREAD_ID, "title": "🏀 БАСКЕТБОЛ — новини",
                    # 🔴 Български клубове (11.08.2026): „Балкан Ботевград със
                    # силен трансфер" падаше в „Други спортове", защото нито
                    # „баскет", нито „NBA" го има в заглавието.
                    "pat": "|".join(["баскет", "балкан ботевград", "рилски спортист",
                                     "черно море тича", "левски лукойл",
                                     "basketball", wb("nba"), wb("wnba"), "евролига",
                                     "euroleague", wb("fiba"), "triple-double", "леброн", "lebron",
                                     "йокич", "jokic", "дончич", "doncic", "еврокъп", "eurocup",
                                     "везенков"])},
    "football":    {"thread": NEWS_THREAD_ID, "title": "⚽ ФУТБОЛ — новини",
                    "pat": "|".join(["футбол", "цска", "левски", "лудогорец", "champions league",
                                     "premier league", "la liga", "serie a", "bundesliga",
                                     "ligue 1", "europa league", "лига европа",
                                     wb("uefa"), wb("fifa"), "world cup", "голмайстор", "дузп",
                                     "football", "soccer", "мондиал",
                                     # големите клубове — иначе „Реал Мадрид с трансфер" пада в „Други"
                                     # („интер" и „милан" са с граници: да не хванат „интервю"/„Милано")
                                     "реал мадрид", "барселона", "байерн", "ливърпул", "манчестър",
                                     "арсенал", "челси", "тотнъм", "псж", "ювентус", "атлетико",
                                     "дортмунд", "наполи", "аякс", "бенфика", "лацио", "първа лига",
                                     wb("интер"), wb("милан")])},
}

# ⚽ ФУТБОЛ = САМО НАЙ-ВИСШИТЕ ЛИГИ И ГОЛЕМИТЕ ИСТОРИИ (заповед на шефа).
# Дребни/местни лиги НЕ минават — другите спортове са по-важни.
# Българският връх Е голяма история за български канал, затова е тук.
TOP_FOOTBALL = "|".join([
    "champions league", "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
    "europa league", "световно", "европейско", "мондиал", "national team", "реал мадрид",
    "барселона", "байерн", "ливърпул", "манчестър", "арсенал", "челси", "тотнъм", "псж",
    "ювентус", "интер", "милан", "атлетико", wb("fifa"), wb("uefa"),
    "първа лига", "лудогорец", "цска", "левски", "националния отбор", "националите",
])


def is_combat(text):
    """Боен спорт ли е? Силните думи важат винаги; меките — само без капан.
    Не решава сам дали друг спорт е по-силен — това го прави classify()."""
    t = (text or "").lower()
    if re.search(COMBAT_TRAP, t):
        return False
    return bool(re.search(COMBAT_STRONG, t))


def classify(title):
    """Заглавие -> ключ на спорт или None (обща новина).
    Ред: силни бойни думи → останалите спортове → меки бойни думи."""
    t = (title or "").lower()
    if is_combat(t):
        return "combat"
    for key, room in SPORT_ROOMS.items():
        if key == "combat":
            continue
        if re.search(room["pat"], t):
            return key
    # „бокс/ринг/нокаут" тръгват само когато НИКОЙ друг спорт не се е обадил
    if re.search(COMBAT_SOFT, t) and not re.search(COMBAT_TRAP, t):
        return "combat"
    return None


# 🔗 ВТОРИ СИГНАЛ: разделът в адреса. „Борусия Дортмунд готви трансфер" няма нито една
# футболна дума, но линкът е .../football-sviat/... — така новината отива при ФУТБОЛА
# (и минава през филтъра TOP_FOOTBALL), вместо да цапа „Други спортове".
# Същият ред както горе: специфичните спортове преди футбола.
LINK_SPORT = [
    ("combat", "|".join([wb("ufc"), wb("mma"), "/mma", "boxing", "/fight", "kickbox", "judo"])),
    ("tabletennis", "|".join(["table-tennis", "tabletennis", "tenis-na-masa", "ping-pong", "pingpong"])),
    ("volleyball", "|".join(["volleyball", "voleybol", "volejbol", "-volley", "/volley", "pallavolo",
                             "siatkowka", "volej"])),
    ("basketball", "|".join(["basketball", "basketbol", wb("basket"), wb("nba"), "evroliga", "euroleague"])),
    ("football", "|".join(["football", "soccer", "futbol", "fudbal"])),
]


def classify_link(link):
    """Адрес -> ключ на спорт или None. Само помощен сигнал, когато заглавието мълчи."""
    u = (link or "").lower()
    if not u:
        return None
    for key, pat in LINK_SPORT:
        if re.search(pat, u):
            return key
    return None


# --- подредбата на постовете в стая 26 (приоритетът на шефа) -----------------
SECTION_ORDER = ["tabletennis", "volleyball", "basketball", "football", "combat", None]
SECTION_HEAD = {
    "tabletennis": "🏓 ТЕНИС НА МАСА",
    "volleyball": "🏐 ВОЛЕЙБОЛ",
    "basketball": "🏀 БАСКЕТБОЛ",
    "football": "⚽ ФУТБОЛ",
    "combat": "🥊 БОЙНИ СПОРТОВЕ",
    None: "📰 ДРУГИ СПОРТОВЕ",
}
# Кой спорт печели, когато една история е разпозната по два начина (по-малкото = по-силно).
ROOM_PRIORITY = {"tabletennis": 0, "volleyball": 1, "basketball": 2, "combat": 3, "football": 4}

STATE_FILE = "sent_news.json"
TITLES_FILE = "last_news_titles.json"          # мост към Анализатора (matches_bot.py)
MAX_ITEMS = int(os.environ.get("NEWS_MAX_GENERAL", "3"))   # таван за „Други спортове"
PER_SPORT = int(os.environ.get("NEWS_PER_SPORT", "3"))     # таван за всеки спорт
MAX_TOTAL = int(os.environ.get("NEWS_MAX_TOTAL", "10"))    # общ таван снимки на едно пускане
OG_MAX = int(os.environ.get("NEWS_OG_MAX", "6"))           # най-много допълнителни заявки за og:image
SHOW_HEADERS = os.environ.get("NEWS_SECTION_HEADERS", "1") != "0"
VERIFY_IMG = os.environ.get("NEWS_VERIFY_IMG", "1") != "0"
MIN_SCORE = 3          # СТАР праг по ключови думи — пази се за news_showcase.py
STATE_KEEP = 2500      # колко ключа помним
SENT_TITLES_KEEP = 400 # колко пратени заглавия помним за сравнение „същата история"
TITLES_KEEP = 200      # колко заглавия подаваме на Анализатора
PER_FEED = 20          # най-много записи, които четем от един източник
MAX_AGE_H = int(os.environ.get("NEWS_MAX_AGE_H", "72"))    # по-стари от това не са „свежи"


def backfill_days():
    """🕰️ BACKFILL за първото пускане: NEWS_BACKFILL_DAYS=N разширява прозореца
    до N дни назад (таван 14), за да се напълни стая 26 с новините от последните
    дни. Всичко останало е СЪЩОТО: дедупе-паметта, праговете, таваните, стая 26.
    Боклук в env (не-число, минус, екзотична цифра) = 0, тоест нормален прозорец."""
    raw = (os.environ.get("NEWS_BACKFILL_DAYS", "") or "").strip()
    if not (raw.isascii() and raw.isdigit()):
        return 0
    try:
        n = int(raw)
    except ValueError:
        return 0
    return min(n, 14)


BACKFILL_DAYS = backfill_days()
if BACKFILL_DAYS > 0:
    MAX_AGE_H = max(MAX_AGE_H, BACKFILL_DAYS * 24)
TG_LIMIT = 3500        # лимитът на Telegram е 4096 — държим запас за емоджита
TG_HARD = 4000         # аварийна ножица: нито един ТЕКСТОВ пост не тръгва по-дълъг от това
CAPTION_HARD = 1000    # таванът на подпис под снимка е 1024 — държим запас
FETCH_WORKERS = 8      # източниците се дърпат едновременно (иначе 50 бавни адреса = 8 минути)
GAP_PHOTO = 2.0        # пауза между снимките (Telegram пуска ~20 съобщения в минута)
GAP_TEXT = 1.2

# Прагове по новата рейтинг-скала (виж rank_story). Пипай ги само с ясна причина.
NEED_SPECIALIST = 1.5   # емисия само за този спорт (ETTU, WorldOfVolley, Sherdog…)
NEED_WEAK = 4.0         # блог/форум в същия спорт — иска повече, за да не пълни картата
NEED_TITLE = 3.0        # спортът е познат по думи в заглавието
NEED_OTHER = float(os.environ.get("NEWS_MIN_RANK", "6.5"))   # „Други спортове" — най-строго
FOOTBALL_BIG = 8.0      # футбол извън топ-лигите минава само с този рейтинг

# 📡 ИЗТОЧНИЦИ. Трети елемент = подсказка за спорт (специализиран сайт: заглавието
# „Poland beat Italy 3:1" няма думата „волейбол", но източникът я знае).
# "other" = ниша, която НЕ е един от петте спорта -> отива в „Други спортове".
# Мъртъв/сменен адрес не е проблем: fetch/parse го прескачат тихо (виж collect_feeds).
#
# ✅ Адресите са ПРОВЕРЕНИ наживо на 28.07.2026 (връщат истински записи), с две
# изключения, оставени нарочно: ITTF (403 от Cloudflare) и EuroLeague (429) — това са
# каноничните източници, адресът им е верен, просто ни спират; от GitHub може да минат.
# Имената са едносрични отпред нарочно: първата дума = ИЗДАТЕЛЯТ (виж publisher()),
# за да не броим „ESPN" и „ESPN NBA" за два независими източника.
FEED_SOURCES = [
    # --- български общи спортни сайтове (носят и волейбол/тенис на маса/бойни) ---
    ("Gong", "https://gong.bg/rss", None),
    ("Sportal", "https://www.sportal.bg/rss", None),
    ("Dsport", "https://dsport.bg/rss", None),
    # 🔴 МАХНАТ 11.08.2026. Отговаря с HTTP 200 и 20 записа — но ВСИЧКИТЕ са
    # от 2009-2010. Прясната дата е на ниво канал, а parse_rss чете само item.
    # Тоест 20 дръпнати записа три пъти дневно за нула новини.
    # ("Blitz Спорт", "https://blitz.bg/rss/sport", None),
    ("Sportlive", "https://sportlive.bg/rss", None),
    ("Actualno Спорт", "https://www.actualno.com/rss/sport", None),
    ("24ч Спорт", "https://www.24chasa.bg/rss/sport", None),
    ("Сега Спорт", "https://www.segabg.com/rss/sport", None),
    # --- световни общи ---
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml", None),
    ("Sky Sports", "https://www.skysports.com/rss/12040", None),
    ("ESPN", "https://www.espn.com/espn/rss/news", None),
    ("Guardian Sport", "https://www.theguardian.com/sport/rss", None),
    # --- 🏓 тенис на маса (най-оскъдният спорт — затова и блогове) ---
    ("ETTU", "https://www.ettu.org/rss", "tabletennis"),
    ("TTEngland", "https://tabletennisengland.co.uk/feed/", "tabletennis"),
    ("Butterfly", "https://www.butterflyonline.com/feed/", "tabletennis"),
    ("TableTennisDaily", "https://www.tabletennisdaily.com/forum/forums/-/index.rss", "tabletennis"),
    # 🔴 МАХНАТ: най-прясната новина е от 09.09.2020.
    # ("ExpertTT", "https://www.experttabletennis.com/feed/", "tabletennis"),
    ("ITTF", "https://www.ittf.com/feed/", "tabletennis"),
    # --- 🏐 волейбол ---
    ("WorldOfVolley", "https://worldofvolley.com/feed/", "volleyball"),
    # 🔴 МАХНАТ: най-прясната новина е от 27.02.2022.
    # ("Volleywood", "https://www.volleywood.net/feed/", "volleyball"),
    ("LegaVolley", "https://www.legavolley.it/feed/", "volleyball"),
    ("Gazzetta Волей", "https://www.gazzetta.it/rss/volley.xml", "volleyball"),
    ("iVolleyMagazine", "https://www.ivolleymagazine.it/feed/", "volleyball"),
    ("VolleyCountry", "https://www.volleycountry.com/feed/", "volleyball"),
    ("VolleyballMag", "https://volleyballmag.com/feed/", "volleyball"),
    # 🔴 МАХНАТ: най-прясната новина е от 23.04.2023.
    # ("Volleyverse", "https://volleyverse.com/feed/", "volleyball"),
    ("NCAA Волейбол", "https://www.ncaa.com/news/volleyball-women/d1/rss.xml", "volleyball"),
    # --- 🏀 баскетбол ---
    ("Eurohoops", "https://www.eurohoops.net/en/feed/", "basketball"),
    ("Sportando", "https://www.sportando.basketball/en/feed", "basketball"),
    ("TalkBasket", "https://www.talkbasket.net/feed", "basketball"),
    ("ESPN NBA", "https://www.espn.com/espn/rss/nba/news", "basketball"),
    ("Yahoo NBA", "https://sports.yahoo.com/nba/rss.xml", "basketball"),
    ("CBS NBA", "https://www.cbssports.com/rss/headlines/nba/", "basketball"),
    ("BallnEurope", "https://www.ballineurope.com/feed/", "basketball"),
    ("EuroLeague", "https://www.euroleaguebasketball.net/euroleague/rss/news/", "basketball"),
    # --- ⚽ футбол (минава само през филтъра TOP_FOOTBALL) ---
    ("BBC Football", "https://feeds.bbci.co.uk/sport/football/rss.xml", "football"),
    ("Guardian Football", "https://www.theguardian.com/football/rss", "football"),
    ("ESPN Soccer", "https://www.espn.com/espn/rss/soccer/news", "football"),
    ("Sky Футбол", "https://www.skysports.com/rss/11095", "football"),
    # 🔴 МАХНАТ: най-прясната новина е от 29.09.2025.
    # ("90min", "https://www.90min.com/posts.rss", "football"),
    # --- 🥊 бойни спортове (ново; всички проверени наживо 28.07.2026) ---
    ("UFC", "https://www.ufc.com/rss/news", "combat"),
    ("ESPN MMA", "https://www.espn.com/espn/rss/mma/news", "combat"),
    ("Sherdog", "https://www.sherdog.com/rss/news.xml", "combat"),
    ("MMAWeekly", "https://www.mmaweekly.com/feed", "combat"),
    ("BloodyElbow", "https://www.bloodyelbow.com/feed/", "combat"),
    ("CombatPress", "https://combatpress.com/feed/", "combat"),
    ("BoxingNewsOnline", "https://www.boxingnewsonline.net/feed/", "combat"),
    ("BoxingNews24", "https://www.boxingnews24.com/feed/", "combat"),
    ("BJPenn", "https://www.bjpenn.com/feed/", "combat"),
    ("LowKickMMA", "https://www.lowkickmma.com/feed/", "combat"),
    # --- 🎯 ниши за „Други спортове" ---
    ("PDC Дартс", "https://www.pdc.tv/rss.xml", "other"),
    ("ESPN Тенис", "https://www.espn.com/espn/rss/tennis/news", "other"),
]

# Съвместимост: news_showcase.py прави „for source, url in nb.FEEDS".
FEEDS = [(name, url) for name, url, hint in FEED_SOURCES]
FEED_SPORT = {name: hint for name, url, hint in FEED_SOURCES if hint}

# Форуми, блогове, ревюта и училищни лиги: съдържанието им е разговорно/вечно
# („Barefoot shoes", „How to Beat a Chopper", „When does the season start?").
# Пускаме ги в спорта им, но с по-висок праг — да не пълнят картата с дрънканици.
FEED_WEAK = {"TableTennisDaily", "Butterfly", "ExpertTT", "VolleyCountry",
             "VolleyballMag", "Volleyverse", "NCAA Волейбол", "BallnEurope",
             "BJPenn", "LowKickMMA", "90min"}

# 🇧🇬 Български източници. Когато една история я има и на български, и на английски,
# постът тръгва с БЪЛГАРСКОТО заглавие (читателите са български).
FEED_BG = {"Gong", "Sportal", "Dsport", "Blitz Спорт", "Sportlive", "Actualno Спорт",
           "24ч Спорт", "Сега Спорт"}
# Колко тежи българското заглавие в рейтинга. Нула = както беше досега.
try:
    NEWS_BG_BONUS = max(0.0, min(6.0, float(os.environ.get("NEWS_BG_BONUS") or "2.0")))
except ValueError:
    NEWS_BG_BONUS = 2.0

# 🚫 ЕМИСИИ С ХАЗАРТЕН СПОНСОР В КАДЪРА. Проверено: снимките на PDC са от турнир,
# кръстен на букмейкър — рекламни пана пълнят кадъра. Български закон забранява
# реклама на хазарт, а ние не можем да четем текста в снимката. Затова: без снимка,
# без визитка на линка (тя щеше да извади същата снимка) — само чист текст.
BRAND_RISK_FEEDS = {"PDC Дартс"}

# Сайтове, които връщат ПРАЗНО тяло на бот — няма смисъл да хабим заявка за og:image.
OG_SKIP_MARKS = ["espn"]


def publisher(source):
    """Издателят зад името на емисията: „ESPN NBA" и „ESPN Soccer" са ЕДИН издател.
    Това пази най-важния сигнал — съгласието между НЕЗАВИСИМИ издания."""
    p = (source or "").strip().lower().split(" ")[0]
    return p or "?"


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 GreenRoomBot/3.0",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_post(url, data, timeout=25):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "GreenRoomBot/3.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def text_of(el):
    """Целият текст на елемента, включително вложените тагове (някои емисии слагат
    <b> направо в <title> — findtext би върнал само първото парче)."""
    if el is None:
        return ""
    return "".join(el.itertext())


def clean_title(raw_title):
    """Маха HTML тагове и двойно кодирани entity-та от заглавието."""
    t = html.unescape((raw_title or "").strip())
    t = re.sub("<[^>]+>", " ", t)
    return " ".join(t.split())


def parse_date(text):
    """RFC822 (RSS pubDate) или ISO (Atom). Неразпознато -> None (новината се пази)."""
    s = (text or "").strip()
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        d = None
    if d is None:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def is_url(s):
    s = (s or "").strip()
    return (s.startswith("http://") or s.startswith("https://")) and (" " not in s)


def resolve_link(link, base=""):
    """ФИЛТЪРЪТ НА АДРЕСИТЕ. Telegram отхвърля ЦЯЛОТО съобщение, ако в него влезе
    a href с релативен адрес — един счупен линк убиваше цял пост.
    Правилата: само абсолютни http/https адреси минават;
      - релативен адрес се залепя за адреса на емисията (urljoin);
      - schemeless (//site/x) се качва на https;
      - чужда схема (itms-apps:, mailto:, javascript:...) = ОТРОВА -> None,
        записът се изхвърля целият;
      - празното си остава празно (новина без линк е безопасна: link_line не прави a href)."""
    s = html.unescape((link or "").strip())
    if not s:
        return ""
    if is_url(s):
        return s
    if s.startswith("//"):
        s = "https:" + s
        return s if is_url(s) else None
    if re.match("[a-z][a-z0-9+.-]*:", s, re.I):
        return None
    if not base:
        return None
    try:
        joined = urllib.parse.urljoin(base, s)
    except Exception:
        return None
    return joined if is_url(joined) else None


# =============================================================== КАРТИНКИТЕ ===
# Пространства от имена в емисиите + regex-и, писани с chr(34)/chr(39), за да няма
# нито една обратна наклонена черта (изискване на деплой-тръбата).
MEDIA_NS = "{http://search.yahoo.com/mrss/}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

QUOTE = "[" + chr(34) + chr(39) + "]"
NOQUOTE = "[^" + chr(34) + chr(39) + "]"
IMG_SRC_RE = re.compile("<img[^>]+src=" + QUOTE + "(" + NOQUOTE + "+)" + QUOTE, re.I)
OG_TAG_RE = re.compile("<meta[^>]+(?:property|name)=" + QUOTE +
                       "(?:og:image(?::url)?|twitter:image(?::src)?)" + QUOTE + "[^>]*>", re.I)
OG_CONTENT_RE = re.compile("content=" + QUOTE + "(" + NOQUOTE + "+)" + QUOTE, re.I)

# Боклук, доказан от истинските емисии: WordPress емоджи-спрайтове, аватари, броячи.
IMG_JUNK = ["s.w.org/images/core/emoji", "/emoji/", "gravatar.com", "/avatar", "feedburner",
            "feedsportal", "doubleclick", "/pixel", "1x1.", "spacer.gif", "blank.gif",
            "blank.png", "/badge", "button.png", "icon-", "/logo.", "placeholder", "/sprite"]
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")

# ⚖️ ХАЗАРТ: имена на букмейкъри. Заглавие с такова име НЕ се публикува; картинка с
# такова име в адреса НЕ се ползва. Български закон забранява рекламата на хазарт.
BOOKIES = ["bet365", "betfred", "1xbet", "efbet", "winbet", "palmsbet", "betano", "bwin",
           "unibet", "pinnacle", "betway", "ladbrokes", "william hill", "paddy power",
           "sportingbet", "betfair", "8888.bg", "букмейкър", "букмейкъри", "коефициент"]


def clean_url(u):
    u = html.unescape((u or "").strip())
    if u.startswith("//"):
        u = "https:" + u
    return u


def has_img_ext(u):
    path = u.split("?")[0].split("#")[0].lower()
    return path.endswith(IMG_EXT)


def upscale(u):
    """Известни CDN-и дават мънички миниатюри. ДОКАЗАНО: BBC 240x135 -> 1024x576.
    Guardian НЕ се пипа (адресът е подписан и смяната дава 401).
    Написано с низови операции, за да няма обратни наклонени черти в regex."""
    if "ichef.bbci.co.uk" in u and "/cpsprodpb/" in u:
        head, tail = u.split("/cpsprodpb/", 1)
        base, sep, last = head.rpartition("/")
        if sep and last.isdigit():
            return base + "/1024/cpsprodpb/" + tail
    return u


def bookie_hit(text):
    """Име на букмейкър в текст/адрес -> True."""
    t = (text or "").lower()
    return any(b in t for b in BOOKIES)


def image_candidates(el):
    """XML елемент <item>/<entry> -> подредени адреси на снимки (най-широката първа).
    Никога не хвърля. Връща най-много 3 кандидата."""
    cands = []

    def add(u, method, width=0):
        u = clean_url(u)
        if not (u.startswith("http://") or u.startswith("https://")):
            return
        low = u.lower()
        if any(j in low for j in IMG_JUNK):
            return
        if bookie_hit(low):
            return
        cands.append((width, upscale(u), method))

    try:
        for mc in el.iter(MEDIA_NS + "content"):
            kind = (mc.get("medium") or mc.get("type") or "")
            if "image" in kind or not kind:
                try:
                    w = int(mc.get("width") or 0)
                except Exception:
                    w = 0
                add(mc.get("url"), "media:content", w)
        for mt in el.iter(MEDIA_NS + "thumbnail"):
            try:
                w = int(mt.get("width") or 0)
            except Exception:
                w = 0
            add(mt.get("url"), "media:thumbnail", w)
        for en in el.iter("enclosure"):
            if "image" in (en.get("type") or "image"):
                add(en.get("url"), "enclosure", 1)
        for ln in el.iter(ATOM_NS + "link"):
            if (ln.get("rel") or "") == "enclosure" and "image" in (ln.get("type") or ""):
                add(ln.get("href"), "atom:enclosure", 1)
        for im in el.iter("image"):
            add((im.findtext("url") or im.text or ""), "image")
        for tag in ("description", CONTENT_NS + "encoded", ATOM_NS + "content", ATOM_NS + "summary"):
            node = el.find(tag)
            if node is None:
                continue
            raw = html.unescape("".join(node.itertext()) or "")
            for src in IMG_SRC_RE.findall(raw)[:3]:
                add(src, "img-in-body")
    except Exception:
        pass

    cands.sort(key=lambda c: (-c[0], 0 if has_img_ext(c[1]) else 1))
    out = []
    for w, u, method in cands:
        if u not in out:
            out.append(u)
        if len(out) == 3:
            break
    return out


# ============================================================ КОНТЕКСТ-РЕДЪТ ==
BOILER = [" the post ", "continue reading", "read more", "appeared first on",
          "виж още", "прочети още", "още по темата", "следете ни", "абонирайте се",
          "снимка: ", "photo: ", "the post appeared"]

# Съкращения, след чиято точка изречението НЕ свършва („през 2026 г. отборът…").
ABBREV = {"г", "бр", "стр", "др", "т", "проф", "инж", "ул", "мин", "сек", "хил",
          "mr", "mrs", "dr", "st", "vs", "no", "inc", "co", "jr", "sr", "u", "s"}


def strip_lead_source(txt, source):
    """Много емисии започват описанието с името на сайта („WorldOfVolley Türkiye
    won…"). Това не е контекст, а подпис — маха се."""
    s = (txt or "").lstrip()
    name = (source or "").strip()
    if name and s.lower().startswith(name.lower()):
        s = s[len(name):].lstrip(" -–—:·|,")
    return s


def strip_byline(txt):
    """Маха подписа на автора отпред: „(by Steve Hopkins, photo WTT) Eugene Wang…"
    или „By Иван Иванов — текстът…". Това не е контекст, а визитка."""
    s = (txt or "").lstrip()
    if s.startswith("("):
        end = s.find(")")
        if 0 < end < 90:
            inner = s[1:end].lower()
            if "by " in inner or "photo" in inner or "снимка" in inner:
                s = s[end + 1:].lstrip(" -–—:·,")
    low = s.lower()
    if low.startswith("by ") or low.startswith("от "):
        for sep in (" - ", " – ", " — ", " | "):
            p = s.find(sep)
            if 0 < p < 60:
                s = s[p + len(sep):].lstrip()
                break
    return s


def item_summary(el, title, source=""):
    """Суровият описателен текст на записа. Празно, ако емисията не дава смисъл."""
    try:
        for tag in ("description", MEDIA_NS + "description", CONTENT_NS + "encoded",
                    ATOM_NS + "summary", ATOM_NS + "content"):
            node = el.find(tag)
            if node is None:
                continue
            txt = clean_title("".join(node.itertext()))
            if "<" in txt or "&" in txt:
                txt = clean_title(txt)
            low = txt.lower()
            for stop in BOILER:
                pos = low.find(stop)
                if pos > 40:
                    txt = txt[:pos]
                    low = txt.lower()
            txt = strip_byline(strip_lead_source(" ".join(txt.split()), source))
            if len(txt) < 30:
                continue
            low = txt.lower()
            if low.startswith((title or "").lower()[:40]):
                txt = txt[len(title):].strip(" -–—:·")
                if len(txt) < 30:
                    continue
            return txt
    except Exception:
        pass
    return ""


def first_sentence(text, low=45, high=260):
    """ПЪРВОТО изречение — това е редът контекст под заглавието.
    Точката след съкращение („г.", „St.") не брои за край на изречение."""
    s = " ".join((text or "").split())
    if not s:
        return ""
    i = 0
    n = len(s)
    while i < n:
        pos = -1
        for mark in (". ", "! ", "? ", "… ", "; "):
            p = s.find(mark, i)
            if p != -1 and (pos == -1 or p < pos):
                pos = p
        if pos == -1:
            break
        words = re.findall("[a-zа-яё0-9]+", s[:pos].lower())
        prev = words[-1] if words else ""
        if pos + 1 < low or prev in ABBREV or (len(prev) == 1 and not prev.isdigit()):
            i = pos + 1
            continue
        return s[:pos + 1].strip()
    if len(s) > high:
        return s[:high]
    return s


def item_category(el):
    """<category> на записа. ТРЕТИ сигнал за спорта: Sportal дава „Волейбол" дори когато
    заглавието („Дунав Русе привлече диагонала") не съдържа нито една волейболна дума."""
    try:
        cats = []
        for tag in ("category", ATOM_NS + "category"):
            for node in el.iter(tag):
                cats.append(clean_title((node.get("term") or "") + " " + "".join(node.itertext())))
        return " ".join(" ".join(cats).split())[:120]
    except Exception:
        return ""


def og_image(page_url, timeout=9):
    """Един допълнителен GET на статията -> og:image. Работи за WordPress сайтове.
    Никога не хвърля; при отказ връща None и новината минава без снимка."""
    try:
        req = urllib.request.Request(page_url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(400000).decode("utf-8", "replace")
    except Exception:
        return None
    for tag in OG_TAG_RE.findall(raw):
        m = OG_CONTENT_RE.search(tag)
        if not m:
            continue
        u = clean_url(m.group(1))
        low = u.lower()
        if u.startswith("http") and not any(j in low for j in IMG_JUNK) and not bookie_hit(low):
            return upscale(u)
    return None


def verify_image(u, timeout=8):
    """Евтина проверка ПРЕДИ да дадем адреса на Telegram: вид и разумен размер.
    При каквато и да е мрежова беля връща True (оптимистично) — Telegram сам ще
    откаже и ние падаме към текст. Иконките (под 10 KB) се режат тук."""
    if not VERIFY_IMG:
        return True
    try:
        req = urllib.request.Request(u, method="HEAD", headers={
            "User-Agent": "Mozilla/5.0 GreenRoomBot/3.0", "Accept": "image/*,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            raw_size = (r.headers.get("Content-Length") or "").strip()
            size = int(raw_size) if raw_size.isdigit() else 0
            if ctype and "image" not in ctype:
                return False
            # size == 0 значи „не знам" (някои CDN-и не дават дължина на HEAD) — не съдим по нея
            if 0 < size < 10000:
                return False
            if size > 9 * 1024 * 1024:
                return False
            return True
    except Exception:
        return True


# ============================================================== ПАРСВАНЕТО ====
def parse_rss(source, raw, base_url=""):
    """RSS <item> и Atom <entry>.
    Връща [{source, title, link, date, imgs, summary, cat}].
    Адресите минават през resolve_link: релативните се абсолютизират срещу адреса
    на емисията, а запис с чужда схема (itms-apps: и т.н.) отпада целият."""
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return items
    for item in root.iter("item"):
        title = clean_title(text_of(item.find("title")))
        link = (item.findtext("link") or "").strip()
        if not is_url(link):
            guid = (item.findtext("guid") or "").strip()
            link = guid if is_url(guid) else link
        link = resolve_link(link, base_url)
        if link is None:
            continue                      # отровен адрес — записът не влиза изобщо
        if title:
            items.append({"source": source, "title": title, "link": link,
                          "date": parse_date(item.findtext("pubDate")),
                          "imgs": image_candidates(item),
                          "summary": item_summary(item, title, source),
                          "cat": item_category(item)})
    # Atom fallback
    if not items:
        ns = ATOM_NS
        for e in root.iter(ns + "entry"):
            title = clean_title(text_of(e.find(ns + "title")))
            link_el = e.find(ns + "link")
            link = (link_el.get("href") or "").strip() if link_el is not None else ""
            link = resolve_link(link, base_url)
            if link is None:
                continue                  # отровен адрес — записът не влиза изобщо
            if title:
                items.append({"source": source, "title": title, "link": link,
                              "date": parse_date(e.findtext(ns + "published") or e.findtext(ns + "updated")),
                              "imgs": image_candidates(e),
                              "summary": item_summary(e, title, source),
                              "cat": item_category(e)})
    return items


# =========================================== ДУМИ, ОТПЕЧАТЪК И „СЪЩАТА ИСТОРИЯ" ==
# Празни думи + ОБЩОСПОРТНИ думи. Общата дума („футбол", „мач", „отбор") НЕ бива да
# слепва две различни истории — затова стои тук и никога не брои за прилика.
STOP_RAW = [
    "който", "която", "което", "които", "след", "преди", "срещу", "заради", "между",
    "около", "според", "въпреки", "затова", "както", "така", "този", "тази", "това",
    "тези", "онзи", "всички", "всичко", "нещо", "няма", "има", "беше", "бяха", "може",
    "могат", "трябва", "иска", "искат", "казва", "каза", "заяви", "обяви", "обявиха",
    "днес", "вчера", "утре", "сега", "вече", "още", "само", "също", "много", "малко",
    "първи", "втори", "трети", "нови", "нова", "ново", "стар", "голям", "голяма",
    "срещата", "мачът", "мача", "мачове", "мачовете", "среща", "срещи", "двубой",
    "двубоя", "отбор", "отбора", "отборът", "отбори", "тим", "тима", "клуб", "клуба",
    "играч", "играча", "играчи", "звезда", "звездата", "треньор", "треньорът",
    "сезон", "сезона", "сезонът", "кръг", "кръга", "лига", "лигата", "турнир",
    "турнира", "шампионат", "първенство", "спорт", "спортни", "новини", "видео",
    "снимки", "футбол", "футболист", "футболен", "баскет", "баскетбол", "волейбол",
    "тенис", "бокс", "боксов", "спортен",
    # етапи и трофеи: ЕТИКЕТИ, не самоличност на историята. Без тях „Бразилия…финал"
    # и „…Final Four в Бразилия" се слепваха в една новина (истински бъг от живия рън).
    "финал", "финала", "финални", "полуфинал", "четвъртфинал", "титла", "титлата",
    "шампион", "медал", "злато", "сребро", "бронз", "купа", "трофей", "победител",
    "победа", "победи", "загуба", "загуби", "класиране", "мач", "гейм", "рунд",
    "that", "this", "with", "from", "have", "has", "will", "would", "could", "about",
    "after", "before", "against", "their", "there", "here", "what", "when", "where",
    "which", "while", "into", "over", "under", "more", "most", "than", "then", "they",
    "them", "your", "you", "and", "but", "for", "not", "are", "was", "were", "been",
    "says", "said", "team", "teams", "club", "clubs", "game", "games", "match",
    "matches", "player", "players", "star", "coach", "season", "league", "sport",
    "sports", "news", "video", "watch", "report", "reports", "update", "live",
    "final", "finals", "semifinal", "quarterfinal", "title", "titles", "champion",
    "champions", "championship", "bronze", "silver", "gold", "medal", "trophy",
    "winner", "winners", "victory", "defeat", "round", "game", "week",
    "ufc", "mma", "nba", "wnba", "fifa", "uefa", "wtt", "ittf", "ettu", "cev", "vnl",
    "fiba", "espn", "euroleague", "евролига",
]
STOP = set(STOP_RAW) | set(w[:6] for w in STOP_RAW)
# Къси, но носещи думи (иначе прагът „поне 4 букви" би ги изхвърлил).
ALLOW_SHORT = {"psg", "цска", "реал", "барса", "юве", "кубрат", "усик"}


def stem(w):
    """Груб корен: първите 6 букви. Език-независимо и достатъчно —
    „манчестър"/„манчестъра" и „transfer"/„transfers" стават една дума."""
    return w[:6]


def toks(text):
    """Отпечатък на заглавието: множество корени на носещите думи.
    Класът пуска и „чужди" букви (Türkiye, Håland), иначе името се чупи на парчета."""
    out = set()
    for w in re.findall("[a-zа-яёà-ÿğışœ0-9]+", (text or "").lower()):
        if w in ALLOW_SHORT:
            out.add(stem(w))
            continue
        if len(w) < 4 or w.isdigit():
            continue
        if w in STOP or stem(w) in STOP:
            continue
        out.add(stem(w))
    return out


def same_story(a, b):
    """Два отпечатъка = една и съща история? (без корпус — по-прощаващата мярка)
    Ползва се за ПАМЕТТА и за последното чистене, където искаме да сме строги
    към повторенията. За СГРУПИРВАНЕТО има по-умна мярка — виж same_story_df."""
    if not a or not b:
        return False
    common = len(a & b)
    if common >= 3:
        return True
    if common >= 2 and common / float(min(len(a), len(b))) >= 0.5:
        return True
    return False


# --- умната мярка: колко РЯДКА е общата дума -------------------------------
# Доказано на живи емисии: „signs", „deal", „final" се срещат в десетки заглавия и
# слепваха несвързани новини („Collin Malcolm signs…" получаваше за източници BBC и
# Sky). Затова общите думи се теглят: рядката дума (име) тежи, честата почти не.
def token_df(items):
    """Колко заглавия съдържат всяка дума в ТОЗИ рън."""
    df = {}
    for c in items:
        for t in (c.get("sig") or set()):
            df[t] = df.get(t, 0) + 1
    return df


def tok_weight(t, df):
    n = df.get(t, 1)
    if n <= 3:
        return 1.0
    if n <= 8:
        return 0.7
    if n <= 20:
        return 0.3
    return 0.08


def same_story_df(a, b, df):
    """Една история ли е — с тегло на общите думи. Две редки имена стигат,
    пет всекидневни думи не стигат."""
    if not a or not b:
        return False
    common = a & b
    if len(common) < 2:
        return False
    w = sum(tok_weight(t, df) for t in common)
    if len(common) >= 3 and w >= 0.9:
        return True
    if len(common) == 2 and w >= 1.4 and len(common) / float(min(len(a), len(b))) >= 0.5:
        return True
    return False


def big_words(text):
    """Стар помощник (news_showcase.py го ползва) — пази се непокътнат."""
    return set(re.findall("[а-яa-z]{6,}", text.lower()))


def is_bg(text):
    """Кирилица в заглавието = българска новина (за избора на представител)."""
    return bool(re.search("[а-яА-Я]", text or ""))


# ==================================================== РЕЙТИНГЪТ (кое е голямо) ==
# Ключови думи -> точки (важност). Основата, върху която лягат другите сили.
KEYWORDS = {
    5: [wp("трансфер"), wp("transfer"), wp("уволн"), wp("sacked"), wp("fired"), wp("оставк"),
        wp("почина"), wp("died"), wp("скандал"), wp("scandal"), wp("дисквалиф"), wp("banned"),
        wp("допинг"), wp("doping"), wp("подписа"), wp("signs"), wp("signed")],
    4: [wp("контузи"), wp("injur"), wp("аут за"), wp("ruled out"), wp("финал"), wp("final"),
        wp("титла"), wp("title"), wp("шампион"), wp("champion"), wp("злато"), wp("медал"),
        wp("рекорд"), wp("record"), wp("оттегл"), wp("retire")],
    3: [wp("дерби"), wp("derby"), wp("класик"), wp("clasico"), "връща се", wb("return"),
        wp("дебют"), wp("debut"), wp("полуфинал"), wp("semifinal"), wp("нокаутира"),
        wp("новият"), wp("новата"), wb("new coach"), wp("сензац")],
    2: [wp("побед"), wp("загуб"), wp("равенство"), wb("гол"), wp("голове"), wb("гола"),
        wp("goal"), wb("win"), wb("beat"), wb("loss"), wb("draw"), wp("класира")],
}

# 🇧🇬 Българска диря — за български канал това е новината, която го засяга пряко.
LOCAL_HOOKS = "|".join([
    "българ", "лудогорец", "цска", "левски", "берое", "ботев", "черно море", "славия",
    "националите", "националния отбор", "пулев", "григор димитров", "везенков",
    "николов", "соколов", "казийски", "стойчев", "тервел", "кубрат",
])

# ⛔ ТВЪРДО ОТПАДА (никога не тръгва): залози, магазин, реклама, тестове.
HARD_DROP = [
    wb("odds"), wp("betting"), "best bets", "bet builder", wp("accumulator"), "free bet",
    wb("tips"), wp("tipster"), wb("prediction"), wb("predictions"), wp("прогноз"),
    wp("залож"), wp("залага"), wp("залаган"), "коефициент",
    wb("shop"), "shop now", wp("discount"), "on sale", wp("разпродажб"), wp("промоци"),
    wb("giveaway"), wp("sponsor"), "partner content", "advertorial", "black friday",
    "gift guide", "buying guide", wb("coupon"), "промо код", wb("unboxing"),
    wb("quiz"), wp("викторина"), "how well do you know", wb("crossword"), wb("puzzle"),
    "best deals", "deal of the", wb("merch"),
]

# ⬇️ НАКАЗАНИЯ (падат надолу, но може да минат, ако историята е огромна).
SOFT_PENALTY = [
    (4.0, "|".join([LB + "(?:топ|top) ?[0-9]+",
                    "[0-9]+ (?:неща|причини|факта|момента|играчи|things|reasons|players|moments|facts|best)",
                    "power rankings", wb("ranked"), "класация на", "the best [0-9]+",
                    "най-добрите [0-9]+", wb("xi"), "team of the week"])),
    (3.0, "|".join([wb("opinion"), wb("column"), wb("columnist"), "мнение на", wp("коментар"),
                    wb("editorial"), "гледна точка", "op-ed", wp("анализ:"), "why "])),
    (3.0, "|".join([wb("watch"), "video:", "видео:", wp("гледайте"), "вижте как", "виж как",
                    "снимки:", wp("галери"), "must-see", wb("highlights"), "хайлайти"])),
    (3.0, "|".join(["where to watch", "how to watch", "къде да гледам", "tv schedule",
                    "по кой канал", "start time", "startlist", "стартов лист",
                    "по тв", "как да гледаме", "как можем да гледаме", "къде да гледаме",
                    "пряко предаване", "директно по", "live stream"])),
    (2.0, "|".join(["you will not believe", wb("shock"), wb("bombshell"), "ето какво",
                    "ето защо", "ето кой", wp("шокира"), "не познахте"])),
    (1.2, "|".join([wp("слух"), wb("rumour"), wb("rumor"), wb("reportedly"), "твърди се",
                    "според медии", wb("gossip"), "може би"])),
    (1.0, "|".join([wb("preview"), wp("предстои"), "какво да очакваме", wb("q&a")])),
]

SPORT_EMOJI = [("футбол|football|soccer|уефа|" + wb("fifa") + "|" + wb("uefa"), "⚽"),
               ("баскет|basket|" + wb("nba"), "🏀"),
               ("тенис на маса|table tennis|пинг понг", "🏓"),
               ("волейбол|volleyball", "🏐"),
               (COMBAT_STRONG, "🥊"),
               ("тенис|tennis", "🎾"),
               ("дартс|darts", "🎯")]

# Емоджи по секция — резерва, когато заглавието не съдържа името на спорта
# („Полша срази Италия с 3:1" е волейбол, но думата я няма).
ROOM_EMOJI = {"tabletennis": "🏓", "volleyball": "🏐", "basketball": "🏀",
              "football": "⚽", "combat": "🥊"}

# Трета резерва за „Други спортове": разделът в адреса или самата емисия.
# („Григор Димитров се оттегли от турнира" няма думата тенис, но линкът е /tennis/.)
LINK_EMOJI = [("table-tennis", "🏓"), ("tenis-na-masa", "🏓"), ("/tennis", "🎾"),
              ("/tenis", "🎾"), ("atp-", "🎾"), ("/darts", "🎯"), ("/darts", "🎯"),
              ("/mma", "🥊"), ("boxing", "🥊"), ("formula", "🏎"), ("/f1", "🏎"),
              ("swimming", "🏊"), ("athletic", "🏃"), ("cycling", "🚴"), ("hockey", "🏒")]
FEED_EMOJI = {"ESPN Тенис": "🎾", "PDC Дартс": "🎯"}

# Емисии на език, който българският читател не чете (италиански). Пазим ги като
# ИЗТОЧНИК (потвърждават чужда история), но рядко да водят поста.
FEED_FOREIGN = {"LegaVolley", "iVolleyMagazine", "Gazzetta Волей"}


def keyword_points(t):
    """Най-високата стойност по ключова дума (0..5)."""
    best = 0
    for pts, words in KEYWORDS.items():
        if pts > best and any(re.search(w, t) for w in words):
            best = pts
    return best


def hard_drop(title):
    """Залози, магазин, реклама, тестове — не тръгват при никакви обстоятелства."""
    t = (title or "").lower()
    if bookie_hit(t):
        return True
    return any(re.search(p, t) for p in HARD_DROP)


# ══════════════════════════════════════════════════════════════════════════
#  🔴 ЕЗИКЪТ, 11.08.2026. Намерено с ОТВАРЯНЕ на стая 26 в Telegram.
#
#  Там висеше това, дословно:
#     „Solè in vista della ripresa: fatta la storia ora bisogna ricominciare
#      Perugia, 07 agosto 2026 Il palazzetto di Perugia sta per riaprire le
#      porte: mercoledì prossimo, 12 agosto, riprende la preparazione…"
#  Цял абзац на ИТАЛИАНСКИ, в българска група, за подновяване на тренировките
#  в залата на Перуджа. Никой български читател няма да го прочете, а дори да
#  можеше — новината не му върши работа.
#
#  Досега езикът се съдеше по ИЗТОЧНИКА (FEED_BG / FEED_FOREIGN). Това е
#  косвено: източник, който никой не е вписал в двата списъка, минава без
#  тежест. LegaVolley беше вписан, но всеки нов италиански или испански фийд
#  ще мине пак. Затова сега езикът се съди по САМИЯ ТЕКСТ.
#
#  Правилото е просто и се проверява с очи:
#    • кирилица       → чете се от групата, води
#    • латиница-английски → минава, но с малка тежест срещу себе си
#    • латиница-НЕанглийски → НЕ ВЛИЗА ИЗОБЩО
#  „НЕанглийски" се разпознава по две независими улики, за да не режем по
#  погрешка: чужд диакритичен знак (à è ñ ü ß …) ИЛИ поне ДВЕ служебни думи,
#  които ги няма в английския (della, für, pour, los, não …).
# ══════════════════════════════════════════════════════════════════════════
KIRILICA = re.compile(r"[а-яА-ЯёЁ]")
CHUZHD_ZNAK = re.compile(r"[àáâãèéêëìíîïòóôõùúûñçüößåæøä]", re.I)
# Границите са LB/RB (виж горе) — файлът не търпи обратни наклонени черти.
# 🔴 РАЗШИРЕН 11.08.2026: старият списък гръмваше ЕДИН път в 825 живи
# заглавия. Липсваха най-честите служебни думи. Тези тук са подбрани да НЕ
# се срещат в английско спортно заглавие — затова ги няма „la", „e", „a".
_CHUZHDI = ("della|dello|delle|degli|nella|nelle|sulla|dalla|questo|questa|"
            "anche|perche|piu|prossimo|riprende|mantiene|non|una|che|nel|"
            "dei|degli|allo|alla|dalle|sono|hanno|dopo|verso|contro|"   # италиански
            "los|las|del|para|segun|pero|este|esta|hacia|desde|sobre|"
            "como|entre|tras|"                                          # испански
            "des|les|pour|avec|dans|cette|ainsi|apres|chez|"            # френски
            "fur|mit|und|beim|vom|zum|nach|uber|gegen|nicht|auch|"      # немски
            "nao|com|mais|pelo|pela")                                   # португалски
CHUZHDA_DUMA = re.compile(LB + "(?:" + _CHUZHDI + ")" + RB, re.I)


def ezik_na(title):
    """Връща 'bg' | 'en' | 'chuzhd'. Съди по текста, не по източника.

    🔴 ПРЕНАПИСАНА СЪЩИЯ ДЕН, 11.08.2026, СЛЕД ИЗМЕРВАНЕ.
    Първата версия работеше НАОПАКИ и го доказах върху живите фийдове:

      УБИВАШЕ английски заглавия заради ударение в СОБСТВЕНО ИМЕ —
        „Source: Barça remain optimistic of signing Rodri"
        „Martínez joins Rashford, Utd teammates at training"
        „Why have Liverpool signed Barcelona captain Ronald Araújo"
        „Arman Tsarukyan meets Maurício Ruffy in UFC 331"
        „Europe Smash 2026, Malmö, 8/8-16"
      осем от осем проби. ESPN Soccer губеше 6 от 19 записа — трансферните
      новини за Барселона, точно това, което групата чака.

      ПУСКАШЕ истински италиански, защото списъкът с думи нямаше най-честите:
        „Perugia mantiene la testa e Trento non molla"
        „Due nuovi professionisti al servizio dei Block Devils"
      четири от четири проби.

    Тоест сигналът, който гърмеше, беше винаги грешен, а верният почти не
    гърмеше. Урок: ударението е в ИМЕТО, не в езика. Собственото име се пише
    с главна буква — затова диакритикът брои само в дума с МАЛКА начална
    буква. И списъкът с думи вече носи наистина честите служебни думи.
    """
    s = str(title or "")
    if KIRILICA.search(s):
        return "bg"
    dumi = len(CHUZHDA_DUMA.findall(s))
    if dumi >= 2:
        return "chuzhd"
    # Диакритик в дума, която НЕ е собствено име (започва с малка буква).
    # „Barça" и „Martínez" минават; „mantiene la città" не.
    malka = False
    for d in re.split(r"[^0-9A-Za-zÀ-ÿ]+", s):
        if d and d[0].islower() and CHUZHD_ZNAK.search(d):
            malka = True
            break
    if malka:
        return "chuzhd"
    # Ударение в име + поне една чужда служебна дума = достатъчно.
    if dumi >= 1 and CHUZHD_ZNAK.search(s):
        return "chuzhd"
    return "en"


def junk_penalty(t):
    """Сборът от наказанията (класация + видео = двойно наказание)."""
    total = 0.0
    for pts, pat in SOFT_PENALTY:
        if re.search(pat, t):
            total += pts
    return total


def source_bonus(nsrc):
    """НАЙ-ТЕЖКАТА СЪСТАВКА: една история в няколко НЕЗАВИСИМИ издания.
    Това е практическото определение за „новината на деня"."""
    if nsrc >= 4:
        return 6.5
    if nsrc == 3:
        return 5.0
    if nsrc == 2:
        return 3.0
    return 0.0


def recency_bonus(age_h):
    """Свежестта. Непозната дата = средно (не наказваме емисия без pubDate)."""
    if age_h is None:
        return 0.6
    if age_h <= 2:
        return 3.0
    if age_h <= 6:
        return 2.2
    if age_h <= 12:
        return 1.4
    if age_h <= 24:
        return 0.8
    if age_h <= 48:
        return 0.2
    return 0.0


def age_hours(date, now=None):
    if date is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - date).total_seconds() / 3600.0)


def rank_story(c, now=None):
    """РЕЙТИНГЪТ на историята. По него се подрежда всяка секция —
    затова първата новина в „ФУТБОЛ" е наистина най-голямата за деня."""
    t = (c.get("title") or "").lower()
    r = float(keyword_points(t))
    r += source_bonus(c.get("nsrc") or 1)
    r += recency_bonus(age_hours(c.get("date"), now))
    r += 1.0 if c.get("room") in ROOM_EMOJI else -0.5
    if re.search(LOCAL_HOOKS, t):
        r += 1.2
    if c.get("imgs"):
        r += 0.4
    r -= junk_penalty(t)
    # 🇧🇬 БЪЛГАРСКОТО ЗАГЛАВИЕ ВОДИ (добавено 11.08.2026).
    #
    # Видяно с очи в стая 26 на 11.08: девет от десет заглавия излизаха на
    # английски — „Jakob Ingebrigtsen returns from injury woe to win historic
    # European 5,000m gold". Групата е българска; заглавие, което читателят не
    # чете, е празно място, колкото и голяма да е новината зад него.
    #
    # FEED_BG вече съществуваше, но се ползваше САМО за избора на представител,
    # когато една и съща история я има на двата езика. Ако българските сайтове
    # изобщо не са я пуснали, английската минаваше напред без никаква тежест
    # срещу себе си. Сега езикът е част от рейтинга, а не само тайбрек.
    #
    # Бонусът е +2.0, не +10: наистина голяма чужда новина още може да води —
    # просто трябва да е наистина голяма.
    # Езикът се съди по САМОТО ЗАГЛАВИЕ (виж дългото обяснение при ezik_na).
    # Източникът остава като допълнителен, по-слаб сигнал — той греши, когато
    # българският сайт е препечатал чужда новина без превод.
    _ez = ezik_na(c.get("title"))
    if _ez == "bg":
        r += NEWS_BG_BONUS
    elif _ez == "chuzhd":
        r -= 99.0            # практически изключване; изрязва се и по-надолу
    if c.get("source") in FEED_BG:
        r += 0.5
    if c.get("source") in FEED_WEAK:
        r -= 1.0
    # 🔴 ТВЪРДА ПОРТА, не наказание (11.08.2026). Тези три фийда издават
    # САМО на италиански — там езикът не е въпрос на преценка по текста, а
    # свойство на самия източник. Измерено на живо: четири техни истории
    # МИНАХА прага 1.5 днес с ранг 1.70-2.10 и не излязоха само защото 241
    # кандидата се биха за 10 места. В тих волейболен ден щяха да излязат.
    # Наказанието от -1.5 просто не стигаше.
    if c.get("source") in FEED_FOREIGN:
        r -= 99.0
    if t.rstrip().endswith("?"):
        r -= 0.8
    if len(c.get("title") or "") < 22:
        r -= 0.6          # огризка от рода на „Match report" — но не наказваме късото ясно заглавие
    return round(r, 2)


def score_item(title, all_titles, cache=None):
    """СТАРИЯТ скор по ключови думи (0..6). Пази се непокътнат, защото
    news_showcase.py го вика; новият подбор минава през rank_story."""
    t = title.lower()
    score = keyword_points(t)
    mine = big_words(t)
    for other in all_titles:
        if other is title:
            continue
        ow = cache.get(other) if cache is not None else None
        if ow is None:
            ow = big_words(other)
        if len(mine & ow) >= 2:
            score += 1
            break
    return score


def sport_emoji(title):
    t = title.lower()
    for pat, emo in SPORT_EMOJI:
        if re.search(pat, t):
            return emo
    return "📌"


def emoji_for(c):
    """Емоджи за поста: заглавие -> секция -> адрес/емисия -> 📌."""
    e = sport_emoji(c.get("title") or "")
    if e != "📌":
        return e
    e = ROOM_EMOJI.get(c.get("room"))
    if e:
        return e
    u = (c.get("link") or "").lower()
    for mark, emo in LINK_EMOJI:
        if mark in u:
            return emo
    return FEED_EMOJI.get(c.get("source")) or "📌"


def h(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def route_item(item):
    """Връща (секция, нужен_рейтинг). Първо думите в заглавието, после специализирания
    източник. Секцията е САМО етикет вътре в стая 26 — НЕ е Telegram thread."""
    room = classify(item["title"]) or classify_link(item.get("link"))
    if room is None and item.get("cat"):
        room = classify(item["cat"])
    hint = FEED_SPORT.get(item["source"])
    if hint in SPORT_ROOMS:
        # специализиран източник = нишата е ценна сама по себе си
        return (room or hint), (NEED_WEAK if item["source"] in FEED_WEAK else NEED_SPECIALIST)
    if room is not None:
        return room, NEED_TITLE
    if hint == "other":
        return None, NEED_TITLE
    return None, NEED_OTHER


# ================================================= СГРУПИРВАНЕ (една история) ==
def rep_key(m):
    """Кой запис представя историята: българският, после този със снимка,
    после силният източник, после по-дългото (по-подробно) заглавие."""
    return (0 if is_bg(m.get("title")) else 1,
            0 if m.get("imgs") else 1,
            0 if m.get("source") not in FEED_WEAK else 1,
            -len(m.get("title") or ""))


def merge_cluster(members):
    """Няколко записа за едно събитие -> ЕДНА история:
    българско заглавие + най-добрата снимка отвсякъде + брой независими издания."""
    ms = sorted(members, key=rep_key)
    rep = dict(ms[0])
    imgs = []
    for m in ms:
        for u in (m.get("imgs") or []):
            if u not in imgs:
                imgs.append(u)
    rep["imgs"] = imgs[:4]
    if not rep.get("summary"):
        for m in ms[1:]:
            if m.get("summary") and is_bg(m["title"]) == is_bg(rep["title"]):
                rep["summary"] = m["summary"]
                break
    # най-свежата дата от групата (историята е толкова свежа, колкото най-новото ѝ съобщение)
    dates = [m.get("date") for m in ms if m.get("date") is not None]
    if dates:
        rep["date"] = max(dates)
    # независими издания + имената на другите (за реда „също: …")
    seen_pub = {publisher(rep["source"])}
    also = []
    for m in ms[1:]:
        p = publisher(m["source"])
        if p in seen_pub:
            continue
        seen_pub.add(p)
        also.append(m["source"])
    rep["nsrc"] = len(seen_pub)
    rep["also"] = also[:2]
    rep["members"] = ms
    rep["sig"] = set()
    for m in ms:
        rep["sig"] |= m.get("sig") or set()
    return rep


def cluster_stories(items):
    """Групира записите по отпечатък. Сравнява се със ЗАРОДИША на групата
    (а не с растящото обединение) — иначе групите щяха да се слепват верижно."""
    df = token_df(items)
    clusters = []
    for c in items:
        placed = False
        for cl in clusters:
            if same_story_df(c.get("sig") or set(), cl["seed"], df):
                cl["members"].append(c)
                placed = True
                break
        if not placed:
            clusters.append({"seed": set(c.get("sig") or set()), "members": [c]})
    return [merge_cluster(cl["members"]) for cl in clusters]


def story_room(story):
    """Секцията на СГРУПИРАНАТА история — ПО ГЛАСОВЕ на участниците.
    Гласът на представителя тежи двойно. „Общ сайт" (None) никога не бие истински
    спорт: така „Гонг" + „WorldOfVolley" дават българско заглавие във ВОЛЕЙБОЛА,
    а един случаен спътник не може сам да завлече новината в чужда секция."""
    members = story.get("members") or [story]
    rep = members[0] if members else story
    rep_room = route_item(rep)[0]
    votes = {}
    needs = {}
    for m in members:
        room, need = route_item(m)
        votes[room] = votes.get(room, 0) + (2 if m is rep else 1)
        if room not in needs or need < needs[room]:
            needs[room] = need
    real = [r for r in votes if r is not None]
    if not real:
        return None, needs.get(None, NEED_OTHER)
    best = None
    best_key = None
    for room in real:
        key = (-votes[room], 0 if room == rep_room else 1, ROOM_PRIORITY.get(room, 98))
        if best_key is None or key < best_key:
            best, best_key = room, key
    return best, needs.get(best, NEED_TITLE)


# ==================================================== ПАМЕТ (без повторения) ==
# Ключове на ВСИЧКИ участници в историята + сравнение по думи с пратените заглавия.
# Точно това лекува оплакването „каналите са пълни с повтарящи се съобщения".
def norm_title(t):
    s = (t or "").lower()
    s = re.sub("[^0-9a-zа-яё ]+", " ", s)
    return " ".join(s.split())


def title_key(t):
    return "t" + h(norm_title(t))


def link_key(u):
    u = (u or "").strip().lower().split("?")[0].split("#")[0]
    for pre in ("https://", "http://"):
        if u.startswith(pre):
            u = u[len(pre):]
    if u.startswith("www."):
        u = u[4:]
    u = u.rstrip("/")
    return ("l" + h(u)) if u else ""


def image_key(u):
    u = (u or "").strip().lower().split("?")[0]
    return ("i" + h(u)) if u else ""


def story_key(sig):
    """Отпечатък на историята като един ключ: четирите най-дълги носещи корена."""
    if not sig:
        return ""
    top = sorted(sig, key=lambda w: (-len(w), w))[:4]
    return "s" + h(" ".join(sorted(top)))


def item_keys(c):
    """Всички ключове, по които разпознаваме „това вече го пратихме" —
    включително ключовете на ДРУГИТЕ източници за същата история."""
    out = []
    for m in (c.get("members") or [c]):
        out.append(title_key(m["title"]))
        out.append(h(m["title"]))          # h(...) = старият формат на паметта
        lk = link_key(m.get("link"))
        if lk:
            out.append(lk)
    sk = story_key(c.get("sig") or toks(c.get("title") or ""))
    if sk:
        out.append(sk)
    seen = set()
    uniq = []
    for k in out:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq


def load_state():
    """Връща (списък ключове НАЙ-НОВИТЕ ОТПРЕД, списък последни пратени заглавия).
    Редът е важен: при рязане до STATE_KEEP пада най-старото, не случайното.
    Разбира и СТАРИЯ формат (плосък списък хешове) — миграцията е безболезнена."""
    keys, titles = [], []
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data, list):
                keys = [s for s in data if isinstance(s, str)]
            elif isinstance(data, dict):
                keys = [s for s in (data.get("keys") or []) if isinstance(s, str)]
                titles = [s for s in (data.get("titles") or []) if isinstance(s, str)]
        except (ValueError, OSError):
            # ValueError покрива и JSONDecodeError (празен/счупен JSON), и
            # UnicodeDecodeError (бинарно повреден файл) — рънът НЕ умира.
            print("WARN: повреден state — започвам начисто.")
    return keys, titles


def store(posted, old_keys, sent_titles):
    """Записва паметта СЛЕД ВСЯКА пратена новина, не само накрая: ако рънърът умре
    по средата, следващото пускане НЕ повтаря вече публикуваното."""
    new_keys = []
    new_titles = []
    for c in posted:
        new_keys += item_keys(c)
        ik = image_key(c.get("used_img") or "")
        if ik:
            new_keys.append(ik)
        # пазим заглавията на ВСИЧКИ източници: утре и английският вариант е „вече пратен"
        for m in (c.get("members") or [c])[:3]:
            if m["title"] not in new_titles:
                new_titles.append(m["title"])
    fresh = set(new_keys)
    keys = new_keys + [k for k in old_keys if k not in fresh]
    seen = set(new_titles)
    titles = new_titles + [t for t in sent_titles if t not in seen]
    try:
        save_state(keys[:STATE_KEEP], titles[:SENT_TITLES_KEEP])
        return True
    except OSError as e:
        print("WARN: не мога да запиша " + STATE_FILE + ": " + str(e)[:120])
        return False


def save_state(keys, titles):
    data = {"v": 3, "keys": list(keys)[:STATE_KEEP], "titles": list(titles)[:SENT_TITLES_KEEP]}
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)     # атомарно: убит рънър не оставя счупен JSON


# ---------------------------------------------------------------- пращане ---
def news_thread():
    """ЕДИНСТВЕНАТА позволена стая за новини. БЯЛ СПИСЪК: минава САМО стая 26 —
    всяка друга env-стойност (чужда стая вкл. 328 и всяка бъдеща, празно, не-число,
    отрицателно) пада обратно към 26. Черният списък остава като втори колан.
    isascii() пази от екзотични Unicode-цифри (² минава isdigit, но чупи int),
    а try е коланът: int() НЯМА как да избяга нагоре и да убие пращането."""
    tid = str(NEWS_THREAD_ID or "").strip()
    num = 0
    if tid.isascii() and tid.isdigit():
        try:
            num = int(tid)
        except ValueError:
            num = 0
    if num in ALLOWED_THREADS and num not in FORBIDDEN_THREADS:
        return num
    print("WARN: непозволен NEWS_THREAD_ID " + repr(NEWS_THREAD_ID) + " — падам към стая " + NEWS_ROOM_FALLBACK + ".")
    return int(NEWS_ROOM_FALLBACK)


def tg_call(method, payload, timeout=25, tries=4):
    """Обща тръба към Telegram с уважение към 429. Никога не хвърля нагоре."""
    api = "https://api.telegram.org/bot" + BOT_TOKEN + "/" + method
    for attempt in range(tries):
        try:
            data = urllib.parse.urlencode(payload).encode()
            resp = json.loads(fetch_post(api, data, timeout=timeout))
            if not resp.get("ok"):
                print("TG ERROR " + method + ": " + str(resp)[:220])
                return False
            return True
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429:
                wait = 5
                try:
                    wait = int(json.loads(body).get("parameters", {}).get("retry_after", 5))
                except Exception:
                    wait = 5
                print("429 — чакам " + str(wait + 1) + " сек. и пробвам пак.")
                time.sleep(wait + 1)
                continue
            print("TG HTTP " + method + " " + str(e.code) + ": " + body[:220])
            return False
        except Exception as e:
            print("TG FAIL " + method + ": " + str(e)[:150])
            return False
    return False


def tg_send(text, preview=False):
    """Текстов пост В СТАЯ 26 и НИКЪДЕ другаде."""
    if len(text) > TG_HARD:
        text = text[:TG_HARD - 2] + " …"
    return tg_call("sendMessage", {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": (not preview),
                                   "message_thread_id": news_thread()})


def tg_photo(photo_url, caption):
    """Снимка по АДРЕС (Telegram я тегли сам) + подпис. В СТАЯ 26 и никъде другаде.
    Таймаутът е по-дълъг: Telegram тегли картинката, преди да отговори."""
    if visible_len(caption) > 1024:
        # Аварийно: режем ЧИСТИЯ текст и чак после екранираме — сляпото рязане на
        # готов HTML може да среже таг наполовина и Telegram връща „can not parse entities".
        caption = esc(clip(clean_title(caption), 900))
    return tg_call("sendPhoto", {"chat_id": CHAT_ID, "photo": photo_url, "caption": caption,
                                 "parse_mode": "HTML", "message_thread_id": news_thread()},
                   timeout=45)


# ------------------------------------------------------------ съставяне ----
BRAND = "🟢 THE GREEN ROOM · 📰 Новини"


def esc(s):
    """Видим текст: Telegram иска екранирани само & < >. Кавичките и апострофите
    остават както са — иначе на екрана излиза суровото &#x27; вместо '."""
    return html.escape(s or "", quote=False)


def visible_len(s):
    """Telegram брои ВИДИМИЯ текст, не HTML-а. Адресът вътре в <a href=…> не се
    брои — иначе един дълъг линк изяждаше реда с контекста без причина."""
    return len(re.sub("<[^>]+>", "", s or ""))


def clip(s, n):
    """Реже по дума и слага многоточие. Пази подписа под тавана на Telegram."""
    s = " ".join((s or "").split())
    if len(s) <= n:
        return s
    cut = s[:n]
    sp = cut.rfind(" ")
    if sp > n * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,.;:-–—") + "…"


def icon_of(c):
    """Топлина на историята: 🔥 голяма, ⚡ силна, ▫️ обикновена."""
    if (c.get("nsrc") or 1) >= 3 or (c.get("rank") or 0) >= 9:
        return "🔥"
    if (c.get("nsrc") or 1) >= 2 or (c.get("rank") or 0) >= 6.5:
        return "⚡"
    return "▫️"


def adds_nothing(title, sentence):
    """Контекстът е излишен, ако само преразказва заглавието."""
    if not sentence:
        return True
    low = sentence.lower().strip()
    tl = (title or "").lower().strip()
    if low.startswith(tl[:40]) or tl.startswith(low[:40]):
        return True
    a = toks(title)
    b = toks(sentence)
    if not a:
        return False
    return (len(a & b) / float(len(a))) >= 0.75


def looks_broken(s):
    """Счупено изречение от самата емисия — не бива да излиза под снимката.
    Истински случай (BoxingNewsOnline): сайтът им реже имената, вързани с линк, и
    описанието им тръгва така: „’s performance … grudge match with , and one…".
    Признаци: не започва с истинска дума с главна буква; висящи запетаи/скоби."""
    t = " ".join((s or "").split())
    if not t:
        return True
    for bad in (" , ", " . ", " ; ", " ) ", " ( ", " и , ", " с , "):
        if bad in t:
            return True
    m = re.search("[0-9a-zа-яёà-ÿ]+", t, re.I)
    if m is None or m.start() > 3:
        return True
    first = m.group(0)
    if len(first) < 2:
        return True
    if first[0].islower():
        return True
    return False


def context_of(c):
    """ЕДИН ред контекст под заглавието — първото смислено изречение от емисията.
    Ако емисията не дава нищо ново, редът остава празен (по-добре, отколкото шум)."""
    raw = c.get("summary") or ""
    cut = raw.find("[…")
    if cut > 40:
        raw = raw[:cut]
    s = first_sentence(raw)
    s = " ".join((s or "").split())
    if len(s) < 35:
        return ""
    if hard_drop(s) or looks_broken(s):
        return ""
    if adds_nothing(c.get("title") or "", s):
        return ""
    return s


def koga_bg(date, now=None):
    """Кога е СТАНАЛА новината, с думи: „днес 17:02" / „вчера 21:17" / „08.08, 21:17".

    🔴 ДОБАВЕНО 11.08.2026. Дотук всеки пост носеше ЕДИН И СЪЩИ печат —
    часът, в който ботът се е събудил (clock се смяташе веднъж за целия рън
    и се подаваше на всяко съобщение). Тоест новина отпреди шест минути и
    новина отпреди три дни изглеждаха еднакво пресни.
    Измерено на живо: от 241 истории над прага, 27 (11%) са на 24-72 часа,
    най-старата на 71 часа — а всичките носеха печат от текущия рън.
    Това е буквално „стара новина, представена като днешна".
    """
    if now is None:
        now = datetime.now(SOFIA)
    if date is None:
        return ""
    try:
        d = date.astimezone(SOFIA)
    except Exception:                                        # noqa: BLE001
        return ""
    dnes = now.date()
    razlika = (dnes - d.date()).days
    chas = d.strftime("%H:%M")
    if razlika <= 0:
        return "днес " + chas
    if razlika == 1:
        return "вчера " + chas
    return d.strftime("%d.%m") + ", " + chas


def link_line(c, clock):
    src = esc(c["source"])
    # Часът на САМАТА новина, не на рънa. Ако липсва — падаме на стария печат,
    # за да не остане редът без нищо.
    koga = koga_bg(c.get("date")) or clock
    if is_url(c.get("link") or ""):
        line = (koga + " · <a href=" + chr(34)
                + html.escape(c["link"], quote=True) + chr(34) + ">"
                + src + "</a>")
    else:
        line = koga + " · <i>" + src + "</i>"
    also = c.get("also") or []
    if also:
        # „също" не казваше какво значи. Значи: и друг издател я е потвърдил.
        line = line + " · потвърдена и от " + esc(", ".join(also[:2]))
    return line


def caption_for(c, clock, title_len=190, sum_len=240):
    """Подпис под снимката: заглавие, ред контекст, източник. Нищо повече.
    Таванът на Telegram е 1024 ВИДИМИ знака — държим се под CAPTION_HARD."""
    head = emoji_for(c) + " " + icon_of(c) + " <b>" + esc(clip(c["title"], title_len)) + "</b>"
    body = ""
    ctx = c.get("context")
    if ctx is None:
        ctx = context_of(c)
        c["context"] = ctx
    if ctx and sum_len > 0:
        body = NL + NL + esc(clip(ctx, sum_len))
    cap = head + body + NL + NL + link_line(c, clock)
    if visible_len(cap) > CAPTION_HARD:
        if sum_len > 120:
            return caption_for(c, clock, title_len=title_len, sum_len=120)
        if sum_len > 0:
            return caption_for(c, clock, title_len=title_len, sum_len=0)
        if title_len > 90:
            return caption_for(c, clock, title_len=90, sum_len=0)
        cap = cap[:CAPTION_HARD] + " …"
    return cap


def text_for(c, clock):
    """Резервният ЧИСТ ТЕКСТ, когато няма снимка или Telegram я отказа."""
    parts = [emoji_for(c) + " " + icon_of(c) + " <b>" + esc(clip(c["title"], 300)) + "</b>"]
    ctx = c.get("context")
    if ctx is None:
        ctx = context_of(c)
        c["context"] = ctx
    if ctx:
        parts.append(esc(clip(ctx, 300)))
    parts.append(link_line(c, clock))
    return (NL + NL).join(parts)


def section_header(key, count, clock, first):
    word = "новина" if count == 1 else "новини"
    head = "<b>" + esc(SECTION_HEAD.get(key) or "📰 НОВИНИ") + "</b> · " + clock + " · " + str(count) + " " + word
    if first:
        head = head + NL + BRAND
    return head


def write_titles(titles):
    """Мост към Анализатора: matches_bot.py чете ПРОСТ списък от заглавия (низове)."""
    if not titles:
        print("WARN: нула събрани заглавия — НЕ пипам " + TITLES_FILE + " (пазя стария мост).")
        return
    try:
        with open(TITLES_FILE, "w", encoding="utf-8") as f:
            json.dump(titles[:TITLES_KEEP], f, ensure_ascii=False)
        print("Мост към Анализатора: " + str(min(len(titles), TITLES_KEEP)) + " заглавия в " + TITLES_FILE + ".")
    except OSError as e:
        print("WARN: не мога да запиша " + TITLES_FILE + ":", e)


# ------------------------------------------------------------- източници ---
def fetch_feed(pair):
    """Един източник -> (име, записи, грешка). Никога не хвърля нагоре."""
    source, url = pair
    try:
        return source, parse_rss(source, fetch(url), url)[:PER_FEED], ""
    except Exception as e:
        return source, [], str(e)[:120]


def collect_feeds():
    """Дърпа всички източници ЕДНОВРЕМЕННО (редът на резултатите е редът на FEEDS,
    затова поведението е същото като едно по едно, само по-бързо)."""
    try:
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
            results = list(ex.map(fetch_feed, FEEDS))
    except Exception as e:
        print("WARN: паралелното дърпане отказа (" + str(e)[:90] + ") — минавам едно по едно.")
        results = [fetch_feed(p) for p in FEEDS]
    collected = []
    alive = 0
    for source, got, err in results:
        if err:
            print("skip " + source + ": " + err)
            continue
        if got:
            alive += 1
        collected += got
    return collected, alive


# -------------------------------------------------------- избор и пращане ---
def dedup(items, limit):
    """Пази най-много limit истории и реже последните близнаци, които са
    оцелели след сгрупирването (различни думи, същото събитие)."""
    out = []
    for c in items:
        sig = c.get("sig") or toks(c["title"])
        if any(same_story(sig, t.get("sig") or toks(t["title"])) for t in out):
            continue
        out.append(c)
        if len(out) == limit:
            break
    return out


def allocate(groups):
    """Раздава MAX_TOTAL места по СИЛА, не по азбучен ред.
    1) Всяка жива секция получава по едно място — нито един спорт не изчезва.
    2) ОСТАНАЛИТЕ места отиват при най-високо оценените истории, в която и секция
       да са. Иначе тенисът на маса (най-бедният на новини) изяждаше местата на
       футбола и бойните, където са големите истории.
    Показването си остава в РЕДА НА ШЕФА — пипаме само кой влиза, не къде стои."""
    ready = []
    for key in SECTION_ORDER:
        cap = MAX_ITEMS if key is None else PER_SPORT
        items = dedup(groups.get(key) or [], cap)
        if items:
            ready.append([key, items])
    if not ready:
        return []
    ready = ready[:MAX_TOTAL]
    chosen = [[key, items[:1]] for key, items in ready]
    left = MAX_TOTAL - len(chosen)
    pool = []
    for idx, entry in enumerate(ready):
        for c in entry[1][1:]:
            pool.append((c.get("rank") or 0.0, idx, c))
    pool.sort(key=lambda p: (-p[0], p[1]))
    for rank, idx, c in pool:
        if left <= 0:
            break
        chosen[idx][1].append(c)
        left -= 1
    for entry in chosen:
        entry[1].sort(key=lambda c: -(c.get("rank") or 0.0))
    return [e for e in chosen if e[1]]


def strip_cross_dupes(sections):
    """dedup() чисти повторенията ВЪТРЕ в секция. Тук махаме една и съща история,
    паднала в ДВЕ различни секции (напр. „Гърция — Италия" и като волейбол, и като
    „други")."""
    seen = []
    for entry in sections:
        keep = []
        for c in entry[1]:
            sig = c.get("sig") or toks(c["title"])
            if any(same_story(sig, s) for s in seen):
                continue
            seen.append(sig)
            keep.append(c)
        entry[1] = keep
    return [e for e in sections if e[1]]


def fill_og_images(items):
    """Един евтин GET на статията за тези без снимка в емисията. Ограничено на OG_MAX."""
    todo = []
    for c in items:
        if c.get("imgs"):
            continue
        if c["source"] in BRAND_RISK_FEEDS:
            continue
        src = c["source"].lower()
        if any(m in src for m in OG_SKIP_MARKS):
            continue
        if is_url(c.get("link") or ""):
            todo.append(c)
        if len(todo) >= OG_MAX:
            break
    if not todo:
        return 0
    got = 0
    try:
        with ThreadPoolExecutor(max_workers=4) as ex:
            found = list(ex.map(lambda c: og_image(c["link"]), todo))
    except Exception:
        found = [og_image(c["link"]) for c in todo]
    for c, u in zip(todo, found):
        if u:
            c["imgs"] = [u]
            got += 1
    return got


def pick_images(c, used_images, sent_keys):
    """ГОДНИТЕ снимки: не са ползвани днес, не са пращани преди, минават проверката.
    Една и съща агенционна снимка не се появява два поста подред — точно това
    изглежда като „повтарящи се съобщения"."""
    if c["source"] in BRAND_RISK_FEEDS:
        return []
    out = []
    for u in (c.get("imgs") or [])[:4]:
        k = image_key(u)
        if not k or k in used_images or k in sent_keys:
            continue
        if not verify_image(u):
            continue
        out.append(u)
    return out


def post_item(c, clock, used_images, sent_keys, dry):
    """Една новина = един пост. Снимка -> (при отказ) втора снимка -> чист текст.
    Връща (успех, начин)."""
    photos = pick_images(c, used_images, sent_keys)
    caption = caption_for(c, clock)
    if dry:
        way = "снимка" if photos else "текст"
        print("--- ПРОБЕН ПОСТ (" + way + ", подпис " + str(len(caption)) + " знака, рейтинг " +
              str(c.get("rank")) + ", източници " + str(c.get("nsrc") or 1) + ") ---")
        print(caption if photos else text_for(c, clock))
        if photos:
            print("IMG: " + photos[0])
            used_images.add(image_key(photos[0]))
            c["used_img"] = photos[0]
        return True, way
    for photo in photos[:2]:
        if tg_photo(photo, caption):
            used_images.add(image_key(photo))
            c["used_img"] = photo
            return True, "снимка"
        print("Снимката отказа — пробвам друга/текст: " + c["title"][:60])
        used_images.add(image_key(photo))     # счупен адрес — да не го въртим пак
        time.sleep(1)
    # Резервата: чист текст. Визитката на линка се пуска САМО ако източникът не е
    # с хазартен спонсор в кадъра (иначе визитката би извадила същата снимка).
    preview = is_url(c.get("link") or "") and c["source"] not in BRAND_RISK_FEEDS
    if tg_send(text_for(c, clock), preview=preview):
        return True, "текст"
    return False, ""


def build_stories(collected, sent_keys, sent_sigs, now):
    """Суровите записи -> подредени истории по секции.
    Тук се случват четирите неща, които правят новинаря добър:
    свежест → закон/боклук → СГРУПИРВАНЕ → рейтинг и памет."""
    cutoff = now - timedelta(hours=MAX_AGE_H)
    recent = []
    seen_titles = set()
    dropped_junk = 0
    for c in collected:
        d = c.get("date")
        if d is not None and d < cutoff:
            continue
        key = h(c["title"])
        if key in seen_titles:
            continue
        seen_titles.add(key)
        c["key"] = key
        recent.append(c)

    all_titles = [c["title"] for c in recent]

    keep = []
    for c in recent:
        if hard_drop(c["title"]):          # залози, магазин, реклама, тестове
            dropped_junk += 1
            continue
        c["sig"] = toks(c["title"])
        keep.append(c)

    # най-новите отпред: те стават зародиш на групата и дават заглавието
    keep.sort(key=lambda c: (c.get("date") or datetime(1970, 1, 1, tzinfo=timezone.utc)), reverse=True)
    stories = cluster_stories(keep)

    skipped_repeat = 0
    fresh = []
    for s in stories:
        if any(k in sent_keys for k in item_keys(s)):
            skipped_repeat += 1
            continue
        if any(same_story(s["sig"], sig) for sig in sent_sigs):
            skipped_repeat += 1
            continue
        room, need = story_room(s)
        s["room"] = room
        s["rank"] = rank_story(s, now)
        # ⚽ футбол минава САМО ако е топ-лига/голяма история
        if room == "football" and s["rank"] < FOOTBALL_BIG and not re.search(TOP_FOOTBALL, s["title"].lower()):
            continue
        if s["rank"] >= need:
            fresh.append(s)

    fresh.sort(key=lambda x: -x["rank"])
    groups = {k: [] for k in SECTION_ORDER}
    for c in fresh:
        groups.setdefault(c["room"], []).append(c)
    sections = strip_cross_dupes(allocate(groups))
    stats = {"recent": len(recent), "stories": len(stories), "junk": dropped_junk,
             "repeat": skipped_repeat, "fresh": len(fresh), "titles": all_titles}
    return sections, stats


def main():
    dry = os.environ.get("NEWS_DRY_RUN", "") == "1"
    if not dry and (not BOT_TOKEN or not CHAT_ID):
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)
    # ЗАЩИТА: новини в канала са забранени (правило 3).
    if CHANNEL_ID and str(CHAT_ID).strip() == str(CHANNEL_ID).strip():
        print("СТОП: CHAT_ID сочи към КАНАЛА. Новини в канала са забранени — не пращам нищо.")
        sys.exit(1)

    if BACKFILL_DAYS > 0:
        print("BACKFILL: прозорецът е разширен до " + str(BACKFILL_DAYS) +
              " дни назад (еднократно пълнене на стая 26; паметта и праговете важат).")

    old_keys, sent_titles = load_state()
    sent_keys = set(old_keys)
    sent_sigs = [toks(t) for t in sent_titles]

    collected, alive = collect_feeds()
    print("Източници: " + str(alive) + " живи от " + str(len(FEEDS)) + ", записи: " + str(len(collected)) + ".")

    now = datetime.now(timezone.utc)
    sections, stats = build_stories(collected, sent_keys, sent_sigs, now)
    write_titles(stats["titles"])
    print("Свежи записи: " + str(stats["recent"]) + " -> истории след сгрупиране: " + str(stats["stories"]) +
          " (боклук/залози: " + str(stats["junk"]) + ", вече пращани: " + str(stats["repeat"]) +
          ", минали прага: " + str(stats["fresh"]) + ").")

    chosen = [c for key, items in sections for c in items]
    if not chosen:
        print("Тих ден — нищо важно. Мълчим.")
        return

    got_og = fill_og_images(chosen)
    with_img = sum(1 for c in chosen if c.get("imgs"))
    multi = sum(1 for c in chosen if (c.get("nsrc") or 1) >= 2)
    print("Избрани " + str(len(chosen)) + " новини; със снимка: " + str(with_img) +
          " (og добави " + str(got_og) + "); потвърдени от 2+ издания: " + str(multi) + ".")

    clock = datetime.now(SOFIA).strftime("%H:%M")
    used_images = set()
    posted = []
    photos = 0
    texts = 0
    first = True
    for key, items in sections:
        if SHOW_HEADERS:
            head = section_header(key, len(items), clock, first)
            if dry:
                print("--- ПРОБНО ЗАГЛАВИЕ НА СЕКЦИЯ ---")
                print(head)
            else:
                tg_send(head, preview=False)
                time.sleep(GAP_TEXT)
        first = False
        for c in items:
            ok, way = post_item(c, clock, used_images, sent_keys, dry)
            if ok:
                posted.append(c)
                if way == "снимка":
                    photos += 1
                else:
                    texts += 1
                if not dry:
                    store(posted, old_keys, sent_titles)     # памет след ВСЯКА новина
            if not dry:
                time.sleep(GAP_PHOTO if way == "снимка" else GAP_TEXT)
        print(str(SECTION_HEAD.get(key)) + " -> новини: " + str(len(items)) + ".")

    if not posted:
        print("Нищо не тръгна (Telegram отказа всичко). Паметта не се пипа.")
        return

    if not dry:
        store(posted, old_keys, sent_titles)     # и накрая, за всеки случай

    print("Готово: " + str(len(posted)) + " новини (" + str(photos) + " със снимка, " +
          str(texts) + " текст), всичко в стая " + str(news_thread()) + " 📰.")


# ================================================================ SELFTEST ====
def make_item(title, source="Gong", link="", summary="", date=None, imgs=None):
    return {"source": source, "title": title, "link": link, "summary": summary,
            "cat": "", "date": date, "imgs": list(imgs or []), "sig": toks(title)}


def run_selftest():
    ok = 0
    bad = []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    # --- 1. ДЕПЛОЙ-ПРАВИЛАТА НА ФАЙЛА ---
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    check("без обратна кавичка", chr(96) not in src)
    check("без обратна наклонена черта", chr(92) not in src)
    check("без долар-скоба", (chr(36) + chr(123)) not in src)

    # --- 2. СТАЯТА ---
    check("стая 26 е позволена", news_thread() == 26)
    check("белият списък е точно стая 26", ALLOWED_THREADS == {26})
    check("бял и черен списък не се допират", not (ALLOWED_THREADS & FORBIDDEN_THREADS))
    check("328 (бойни спортове) е в черния списък", 328 in FORBIDDEN_THREADS)
    for t in sorted(FORBIDDEN_THREADS):
        globals()["NEWS_THREAD_ID"] = str(t)
        check("стая " + str(t) + " е отказана", news_thread() == 26)
    for t in ("2", "999"):
        globals()["NEWS_THREAD_ID"] = t
        check("непозната стая " + t + " е отказана (allowlist)", news_thread() == 26)
    globals()["NEWS_THREAD_ID"] = "26"

    # --- 3. 🥊 БОЙНИТЕ СПОРТОВЕ И КАПАНИТЕ НА „БОКС" ---
    combat_yes = ["UFC 320: Анкалаев срещу Гускоу", "Макгрегър обяви завръщане в октагона",
                  "Усик защити титлата си", "Кубрат Пулев с нов съперник",
                  "Bellator returns to Dublin", "Кикбокс турнир в София",
                  "Boxing: Fury eyes final fight", "Джудо: злато за България"]
    for t in combat_yes:
        check("боен спорт: " + t[:28], classify(t) == "combat")
    combat_no = [("Арсенал и Челси в дерби на Boxing Day", "football"),
                 ("Box-to-box халфът на Ливърпул подписа нов договор", "football"),
                 ("Ферари прибра болида в бокса", None),
                 ("Нокаут за Реал Мадрид преди финала", "football"),
                 ("НБА: Йокич с трипъл-дабъл", "basketball"),
                 ("Волейболистите ни с победа", "volleyball")]
    for t, want in combat_no:
        check("НЕ е боен спорт: " + t[:28], classify(t) == want)

    # --- 4. БОКЛУК И НАКАЗАНИЯ ---
    for t in ["Прогноза за мача Реал - Барселона", "Best bets for Sunday",
              "QUIZ: How well do you know the NBA?", "Shop now: new kits on sale",
              "Коефициенти за финала"]:
        check("твърдо отпада: " + t[:26], hard_drop(t) is True)
    for t in ["Реал Мадрид продаде звездата си", "Лудогорец с нов треньор"]:
        check("НЕ отпада: " + t[:26], hard_drop(t) is False)
    check("класация се наказва", junk_penalty("топ 10 гола на кръга") >= 4.0)
    check("видео се наказва", junk_penalty("гледайте видео: най-доброто") >= 3.0)
    check("нормалното не се наказва", junk_penalty("лудогорец подписа с нападател") == 0.0)

    # --- 5. „СЪЩАТА ИСТОРИЯ" ---
    a = toks("Лудогорец подписа с бразилски нападател")
    b = toks("Бразилски нападател подписа с Лудогорец")
    c2 = toks("Левски загуби от Ботев Пловдив")
    check("същата история се хваща", same_story(a, b) is True)
    check("различните истории не се слепват", same_story(a, c2) is False)
    check("общоспортната дума не слепва", same_story(toks("Мачът на отбора беше тежък"),
                                                     toks("Отборът игра тежък мач")) is False)
    check("два езика не се сливат (знаем го)",
          same_story(toks("Волейболистите на България победиха Италия"),
                     toks("Bulgaria stun Italy in five sets")) is False)

    # --- 6. СГРУПИРВАНЕ: два източника = един пост ---
    it1 = make_item("Реал Мадрид представи новия си нападател", source="Gong", link="https://gong.bg/1")
    it2 = make_item("Real Madrid unveil new striker", source="BBC Sport", link="https://bbc.co.uk/2",
                    imgs=["https://img.bbc.co.uk/a.jpg"])
    it3 = make_item("Реал Мадрид представи новия нападател на клуба", source="Sportal",
                    link="https://sportal.bg/3", imgs=["https://sportal.bg/x.jpg"])
    stories = cluster_stories([it1, it2, it3])
    bgstory = [s for s in stories if is_bg(s["title"])]
    check("двата български записа стават един", len(stories) == 2)
    check("представителят е български и брои 2 издания",
          bool(bgstory) and is_bg(bgstory[0]["title"]) and bgstory[0]["nsrc"] == 2)
    check("снимката се наследява от групата", bool(bgstory) and len(bgstory[0]["imgs"]) >= 1)
    check("другите източници се помнят", bool(bgstory) and bgstory[0]["also"] == ["Gong"])
    check("ключовете покриват всички варианти",
          bool(bgstory) and title_key(it3["title"]) in item_keys(bgstory[0]))

    # --- 6б. ФАЛШИВОТО СЛЕПВАНЕ (истински бъг от живия рън) ---
    # „signs"/„deal" се срещат в десетки заглавия — не са доказателство за една история.
    # (истинският рън е стотици заглавия — затова корпусът тук е реалистично голям:
    #  „signs" и „deal" трябва да са ЧЕСТИ думи, за да ги обезсили тегленето)
    names = ["Malcolm", "Everton", "Larkin", "Tenorio", "Willis", "Hunter", "Vargas",
             "Kovacs", "Petrov", "Dimitrov", "Ivanov", "Novak", "Sanchez", "Ferreira",
             "Okafor", "Berger", "Lindqvist", "Yilmaz", "Moretti", "Duarte", "Nowak",
             "Hansen", "Costa", "Nagy"]
    noise = [make_item(n + " signs a two-year deal with the champions", source="Eurohoops")
             for n in names]
    noisy = cluster_stories(noise)
    check("честите думи не слепват новини", len(noisy) == len(noise))
    twins = cluster_stories([
        make_item("Анкалаев нокаутира Гускоу в Абу Даби", source="Gong"),
        make_item("Анкалаев нокаутира Гускоу и защити титлата", source="Sportal")])
    check("редките имена слепват правилно", len(twins) == 1 and twins[0]["nsrc"] == 2)

    # --- 6в. СЕКЦИЯТА НЕ СЕ ОТВЛИЧА ОТ СЛУЧАЕН СПЪТНИК ---
    vol_rep = make_item("Bulgaria beat Italy in the VNL semifinal", source="WorldOfVolley",
                        imgs=["https://wov.com/z.jpg"])
    tt_stray = make_item("Some other story from a blog", source="Butterfly")
    hijack = merge_cluster([vol_rep, tt_stray])
    check("спътникът не краде секцията", story_room(hijack)[0] == "volleyball")

    # --- 7. РЕЙТИНГ: голямото бие дребното ---
    now = datetime.now(timezone.utc)
    big = make_item("Лудогорец уволни треньора си", source="Gong", date=now)
    big["nsrc"] = 3
    big["room"] = "football"
    small = make_item("Топ 10 гола от кръга", source="90min", date=now - timedelta(hours=40))
    small["nsrc"] = 1
    small["room"] = "football"
    check("голямата новина бие класацията", rank_story(big, now) > rank_story(small, now) + 5)
    check("класацията пада под прага", rank_story(small, now) < NEED_TITLE
          or junk_penalty(small["title"].lower()) >= 4.0)
    fresh_i = make_item("Барселона подписа с защитник", date=now)
    old_i = make_item("Барселона подписа с защитник", date=now - timedelta(hours=50))
    check("свежото бие старото", rank_story(fresh_i, now) > rank_story(old_i, now))

    # --- 🇧🇬 БЪЛГАРСКОТО ЗАГЛАВИЕ ВОДИ.
    # Стая 26 излизаше с девет от десет заглавия на английски. Езикът вече е
    # част от рейтинга — при иначе еднакви новини българската минава напред.
    _bg = make_item("Лудогорец подписа с нападател", date=now)
    _bg["source"] = "Gong"
    _en = make_item("Лудогорец подписа с нападател", date=now)
    _en["source"] = "BBC Sport"
    check("българският източник води при равни други",
          rank_story(_bg, now) > rank_story(_en, now))
    # 🔴 ПРЕПИСАНО 11.08.2026: бонусът вече е за ЕЗИКА НА ЗАГЛАВИЕТО, не за
    # източника. Двете новини горе са с ЕДНО И СЪЩО българско заглавие, значи
    # и двете взимат езиковия бонус — остава само малката тежест на източника.
    check("източникът тежи, но малко",
          abs((rank_story(_bg, now) - rank_story(_en, now)) - 0.5) < 0.01)
    _lat = make_item("Ludogorets signs a striker", date=now)
    _lat["source"] = "BBC Sport"
    check("кирилското заглавие бие латинското",
          rank_story(_bg, now) - rank_story(_lat, now) >= NEWS_BG_BONUS - 0.01)
    # --- ЕЗИКОВИЯТ СЪДИЯ (заради италианската новина в стая 26)
    check("кирилица се разпознава", ezik_na("Лудогорец подписа") == "bg")
    check("английското минава за английско", ezik_na("Mavericks place bounty") == "en")
    # Точното заглавие, което висеше в стая 26 на 11.08 — с ударението.
    check("италианското се хваща по диакритика",
          ezik_na("Solè in vista della ripresa: fatta la storia") == "chuzhd")
    check("италианското се хваща и без диакритика",
          ezik_na("Il palazzetto della citta prossimo alla riapertura") == "chuzhd")
    check("испанското се хваща",
          ezik_na("Valencia cede al pivot para los partidos del grupo") == "chuzhd")
    check("немското се хваща",
          ezik_na("Bayern und Dortmund mit neuen Spielern") == "chuzhd")
    check("едно съвпадение НЕ стига (за да не режем английско)",
          ezik_na("Los Angeles Lakers sign a new guard") == "en")
    check("празното не гърми", ezik_na("") == "en" and ezik_na(None) == "en")
    _it = make_item("Solè in vista della ripresa: fatta la storia", date=now)
    _it["source"] = "LegaVolley"
    check("чуждоезичната новина пада на дъното",
          rank_story(_it, now) < rank_story(_lat, now) - 50)
    check("бонусът може да се изключи с променлива", 0.0 <= NEWS_BG_BONUS <= 6.0)
    # Но не е чек в бланко. Измерено на 11.08.2026 с истинските числа:
    #   „Лудогорец подписа с нападател" (ключ 5) от BBC  -> 10.2
    #   „Контузия в дублиращия отбор"   (ключ 4) от Gong -> 10.0
    # Тоест ЕДНА степен по-силна ключова дума стига чуждата новина да мине
    # напред въпреки бонуса. Езикът тежи, но не решава сам.
    _chuzhda_silna = make_item("Лудогорец подписа с нападател", date=now)
    _chuzhda_silna["source"] = "BBC Sport"
    _bg_slaba = make_item("Контузия в дублиращия отбор", date=now)
    _bg_slaba["source"] = "Gong"
    check("по-силната чужда новина още бие по-слабата българска",
          rank_story(_chuzhda_silna, now) > rank_story(_bg_slaba, now))
    # ⚠️ НАМЕРЕНО ПЪТЬОМ, НЕ ОПРАВЕНО: keyword_points дава ЕДНО И СЪЩО число (4)
    # на „спечели Шампионска лига" и на „контузия в дублиращия отбор". Тоест
    # таблицата с ключови думи не различава финал от дребна контузия. Това е
    # отделен дефект в подбора, не в езиковия бонус — записан, за да не се губи.
    check("таблицата с думи още не различава финал от контузия",
          keyword_points("реал мадрид спечели шампионска лига")
          == keyword_points("контузия в дублиращия отбор"))

    # --- 8. КОНТЕКСТ-РЕДЪТ ---
    check("първо изречение",
          first_sentence("Отборът обяви новината официално в понеделник вечерта. После добави още.")
          == "Отборът обяви новината официално в понеделник вечерта.")
    check("късото първо изречение се допълва",
          first_sentence("Ето какво стана. Треньорът напусна още в понеделник сутринта.")
          .startswith("Ето какво стана. Треньорът"))
    check("точка след съкращение не реже",
          "и веднага смени треньора" in
          first_sentence("Новият собственик на клуба пое управлението през 2026 г. и веднага смени треньора."))
    check("преразказът се маха",
          adds_nothing("Лудогорец уволни треньора си", "Лудогорец уволни треньора си след загубата") is True)
    check("истинският контекст остава",
          adds_nothing("Лудогорец уволни треньора си",
                       "Решението падна след трето поредно домакинско равенство в Разград.") is False)
    # счупеното описание на емисията (истински случай от BoxingNewsOnline)
    broken = "’s performance against Prenga has drawn concern ahead of a match with , and one icon advised him."
    check("счупеното изречение се хваща", looks_broken(broken) is True)
    check("здравото изречение минава",
          looks_broken("Решението падна след трето поредно домакинско равенство в Разград.") is False)
    check("счупеното не влиза в поста",
          context_of({"title": "Boxing icon pleads with Joshua", "summary": broken}) == "")
    check("телевизионната програма се наказва",
          junk_penalty("университатя - левски по тв: как можем да гледаме реванша") >= 3.0)

    # --- 9. ПОСТЪТ: форма, таван, забранени думи ---
    demo = make_item("Лудогорец уволни старши треньора след загубата в Разград",
                     source="Gong", link="https://gong.bg/news/1",
                     summary="Решението е взето след трето поредно домакинско равенство. Отборът е трети.",
                     imgs=["https://gong.bg/a.jpg"], date=now)
    demo["nsrc"] = 3
    demo["also"] = ["Sportal", "Dsport"]
    demo["room"] = "football"
    demo["rank"] = rank_story(demo, now)
    cap = caption_for(demo, "09:12")
    check("подписът е под тавана", visible_len(cap) <= CAPTION_HARD)
    check("подписът има заглавие", "Лудогорец уволни" in cap)
    check("подписът има контекст", "трето поредно" in cap)
    # 🔴 ПРЕПИСАНИ 11.08.2026 заедно с реда. Постът вече носи часа на САМАТА
    # новина („днес 17:02" / „вчера 21:17" / „08.08, 21:17"), не часа на рънa —
    # иначе новина отпреди три дни изглежда като отпреди минута.
    check("подписът има източник", "Gong" in cap)
    check("подписът носи КОГА е новината", "днес" in cap or "вчера" in cap)
    check("подписът НЕ носи часа на рънa", "09:12" not in cap)
    check("подписът казва какво значи вторият източник",
          "потвърдена и от Sportal, Dsport" in cap)
    # И самата функция за времето, в трите си форми:
    from datetime import datetime as _dt
    _n = _dt(2026, 8, 11, 20, 0, tzinfo=SOFIA)
    check("днешната новина се казва днес",
          koga_bg(_dt(2026, 8, 11, 17, 2, tzinfo=SOFIA), _n) == "днес 17:02")
    check("вчерашната се казва вчера",
          koga_bg(_dt(2026, 8, 10, 21, 17, tzinfo=SOFIA), _n) == "вчера 21:17")
    check("по-старата носи дата",
          koga_bg(_dt(2026, 8, 8, 21, 17, tzinfo=SOFIA), _n) == "08.08, 21:17")
    check("липсващата дата не гърми", koga_bg(None, _n) == "")

    # ══════════════════════════════════════════════════════════════════
    #  🔴 ЕЗИКОВИЯТ СЪДИЯ РАБОТЕШЕ НАОПАКИ — измерено върху живите фийдове
    #  СЪЩИЯ ДЕН, в който беше добавен. Убиваше английски заглавия заради
    #  ударение в СОБСТВЕНО ИМЕ (Barça, Martínez, Araújo, Malmö) и пускаше
    #  истински италиански, защото списъкът нямаше честите служебни думи.
    #  Тези проверки държат двете посоки едновременно.
    # ══════════════════════════════════════════════════════════════════
    for _en in ("Source: Barca remain optimistic of signing Rodri",
                "Martínez joins Rashford, Utd teammates at training",
                "Why have Liverpool signed Barcelona captain Ronald Araújo",
                "How will Bruno Guimarães fit in Arsenal midfield?",
                "José Montanha Ready To Finally Unleash The Monster",
                "Europe Smash 2026, Malmö, 8/8-16",
                "Matt Anderson and Fiancée Are Expecting A Boy",
                "Los Angeles Lakers sign a new guard"):
        check("английското оцелява: " + _en[:34], ezik_na(_en) != "chuzhd")
    for _it in ("Perugia mantiene la testa e Trento non molla",
                "Solè in vista della ripresa: fatta la storia",
                "Il palazzetto della citta prossimo alla riapertura",
                "Valencia cede al pivot para los partidos del grupo",
                "Bayern und Dortmund mit neuen Spielern"):
        check("чуждото се хваща: " + _it[:34], ezik_na(_it) == "chuzhd")
    check("кирилицата води", ezik_na("Лудогорец подписа") == "bg")

    # 🔴 ВОЛЕЙБОЛЪТ падаше в „Други": шаблонът искаше цялата дума „волейбол",
    # а журналистът пише „волейнационалите" и „Евроволей".
    check("волейнационалите са волейбол",
          classify("Капитанът на волейнационалите: Има предстартова треска") == "volleyball")
    check("Евроволей е волейбол",
          classify("Бленджини направи промени за Евроволей 2026") == "volleyball")
    # ⚠️ И обратното: футболният волей НЕ бива да става волейбол.
    check("футболният волей не е волейбол",
          classify("Стунинг волей от Роналдо срещу Сити") != "volleyball")
    check("красив волей не е волейбол",
          classify("Красив волей от Меси за 2:0") != "volleyball")
    # Български баскетболни клубове — падаха в „Други".
    check("Балкан Ботевград е баскетбол",
          classify("Балкан Ботевград със силен трансфер") == "basketball")
    check("Левски Лукойл е баскетбол, не футбол",
          classify("Левски Лукойл с нов играч") == "basketball")
    check("голямата новина е 🔥", icon_of(demo) == "🔥")
    banned = ["18+", "не е съвет", "решението е твое", "залагай отговорно", "от банката",
              "коефициент", "букмейкър", "заложи", "залог", "отговорна игра"]
    for txt, label in ((cap, "подпис"), (text_for(demo, "09:12"), "текст"),
                       (section_header("combat", 2, "09:12", True), "заглавие на секция")):
        low = txt.lower()
        for b in banned:
            check(label + ": без „" + b + "“", b not in low)
    long_item = make_item("Т" * 400, source="Gong", link="https://gong.bg/x",
                          summary="Д" * 900, date=now)
    check("дългият подпис пак е под тавана",
          visible_len(caption_for(long_item, "09:12")) <= CAPTION_HARD)
    # дълъг адрес НЕ бива да изяжда реда с контекста (беше бъг: броеше се HTML-ът)
    longlink = make_item("Лудогорец смени треньора си преди мача с Левски", source="Gong",
                         link="https://www.gong.bg/futbol-bulgaria/" + ("dulga-chast-ot-adresa-" * 12),
                         summary="Клубът обяви решението късно снощи, час след третото поредно равенство.",
                         date=now)
    check("дългият адрес не яде контекста", "късно снощи" in caption_for(longlink, "09:12"))
    check("подписът с дълъг адрес е под тавана",
          visible_len(caption_for(longlink, "09:12")) <= CAPTION_HARD)
    check("името на сайта се маха от контекста",
          strip_lead_source("WorldOfVolley Türkiye won the title", "WorldOfVolley")
          == "Türkiye won the title")
    check("тенисът получава емоджи по адреса",
          emoji_for({"title": "Григор се оттегли от турнира", "room": None,
                     "link": "https://www.actualno.com/tennis/x", "source": "Actualno Спорт"}) == "🎾")

    # --- 10. ПАМЕТТА: една история не тръгва два пъти ---
    tmp = STATE_FILE + ".selftest"
    old_file = globals()["STATE_FILE"]
    globals()["STATE_FILE"] = tmp
    try:
        story = merge_cluster([it1, it3])
        story["used_img"] = "https://sportal.bg/x.jpg"
        save_state([], [])
        store([story], [], [])
        keys2, titles2 = load_state()
        sent = set(keys2)
        check("паметта помни историята", any(k in sent for k in item_keys(story)))
        check("паметта помни английския вариант", title_key(it3["title"]) in sent)
        check("паметта помни заглавия", len(titles2) >= 1)
        sigs = [toks(t) for t in titles2]
        again = merge_cluster([make_item("Реал Мадрид представи новия си нападател")])
        check("повторението се хваща по думи", any(same_story(again["sig"], s) for s in sigs))
    finally:
        globals()["STATE_FILE"] = old_file
        for suffix in ("", ".tmp"):
            try:
                os.remove(tmp + suffix)
            except Exception:
                pass

    # --- 11. СЕКЦИИТЕ ---
    check("редът на секциите е на шефа",
          SECTION_ORDER == ["tabletennis", "volleyball", "basketball", "football", "combat", None])
    check("всяка секция има заглавие", all(k in SECTION_HEAD for k in SECTION_ORDER))
    check("бойните имат емисии", len([1 for n, u, hint in FEED_SOURCES if hint == "combat"]) >= 8)
    check("издателят е един за ESPN", publisher("ESPN NBA") == publisher("ESPN Soccer"))
    check("два различни издателя се броят", publisher("Gong") != publisher("BBC Sport"))
    check("таванът на общия брой", MAX_TOTAL >= 1 and PER_SPORT >= 1)

    # раздаването на местата: всяка секция по едно, останалите — на най-силните
    def ranked(title, rank, room):
        it = make_item(title, source="Gong", date=now)
        it["rank"] = rank
        it["room"] = room
        return it
    groups_demo = {
        "tabletennis": [ranked("ТТ новина едно", 5.0, "tabletennis"),
                        ranked("ТТ новина две", 4.0, "tabletennis"),
                        ranked("ТТ новина три", 3.5, "tabletennis")],
        "football": [ranked("Футбол голяма новина", 13.0, "football"),
                     ranked("Футбол втора новина", 11.0, "football"),
                     ranked("Футбол трета новина", 10.0, "football")],
    }
    old_total = globals()["MAX_TOTAL"]
    globals()["MAX_TOTAL"] = 4
    try:
        alloc = dict((k, v) for k, v in allocate(groups_demo))
        check("всяка секция получава поне едно място", len(alloc.get("tabletennis") or []) >= 1)
        check("силните вземат останалите места", len(alloc.get("football") or []) == 3)
        check("общият таван се спазва", sum(len(v) for v in alloc.values()) == 4)
        check("секцията е подредена по сила",
              (alloc.get("football") or [{}])[0]["rank"] == 13.0)
    finally:
        globals()["MAX_TOTAL"] = old_total
    check("подписът на автора се маха",
          strip_byline("(by Steve Hopkins, photo WTT) Eugene Wang won the singles")
          == "Eugene Wang won the singles")

    # --- 12. ЦЯЛАТА ТРЪБА НА СУХО ---
    feed_items = [
        make_item("Волейболистите на България победиха Италия с 3:1", source="Gong",
                  link="https://gong.bg/v1", date=now,
                  summary="Тимът ни изостава в първия гейм, но обръща мача след смяна в разпределението. Следва Полша."),
        make_item("България победи Италия с 3:1 във волейбола", source="Sportal",
                  link="https://sportal.bg/v2", date=now, imgs=["https://sportal.bg/a.jpg"]),
        make_item("Прогноза: кой ще спечели финала", source="Gong", link="https://gong.bg/p", date=now),
        make_item("UFC 320: Анкалаев нокаутира Гускоу в първия рунд", source="Sherdog",
                  link="https://sherdog.com/u1", date=now, imgs=["https://sherdog.com/b.jpg"],
                  summary="Титлата остава в Дагестан след 84 секунди игра. Следващият съперник още не е обявен."),
    ]
    secs, st = build_stories(feed_items, set(), [], now)
    keys_out = [k for k, items in secs]
    check("волейболът стига до секцията си", "volleyball" in keys_out)
    check("бойните стигат до секцията си", "combat" in keys_out)
    check("прогнозата е изхвърлена", st["junk"] >= 1)
    vol = [items for k, items in secs if k == "volleyball"][0]
    check("двата волейболни записа са ЕДНА новина", len(vol) == 1)
    check("българското заглавие печели", is_bg(vol[0]["title"]))
    check("волейболът има 2 източника", vol[0]["nsrc"] == 2)
    check("волейболът наследи снимката", len(vol[0]["imgs"]) >= 1)

    # --- 13. АДРЕСИТЕ: само http/https; релативните се залепят; отровата отпада ---
    check("абсолютният адрес минава",
          resolve_link("https://a.bg/x", "https://a.bg/rss") == "https://a.bg/x")
    check("релативният се абсолютизира",
          resolve_link("/bg/news/1", "https://site.bg/rss") == "https://site.bg/bg/news/1")
    check("релативен без наклонена черта също",
          resolve_link("news/2", "https://site.bg/rss/") == "https://site.bg/rss/news/2")
    check("schemeless се качва на https",
          resolve_link("//cdn.site.bg/i", "") == "https://cdn.site.bg/i")
    check("чуждата схема е отрова", resolve_link("itms-apps://apple.com/app", "https://a.bg/rss") is None)
    check("javascript-схемата е отрова", resolve_link("javascript:void(0)", "https://a.bg/rss") is None)
    check("празният линк остава празен", resolve_link("", "https://a.bg/rss") == "")
    check("релативен без база отпада", resolve_link("bg/news", "") is None)
    rss_demo = ("<rss><channel>" +
                "<item><title>Релативна новина</title><link>/bg/n1</link></item>" +
                "<item><title>Отровна новина</title><link>itms-apps://x</link></item>" +
                "<item><title>Нормална новина</title><link>https://site.bg/n3</link></item>" +
                "</channel></rss>")
    parsed = parse_rss("Тест", rss_demo, "https://site.bg/rss")
    check("parse_rss абсолютизира релативния линк",
          any(p["link"] == "https://site.bg/bg/n1" for p in parsed))
    check("parse_rss изхвърля отровния запис изцяло",
          all("Отровна" not in p["title"] for p in parsed) and len(parsed) == 2)
    check("parse_rss пази нормалния запис",
          any(p["link"] == "https://site.bg/n3" for p in parsed))

    # --- 14. BACKFILL: първото пълнене на стаята ---
    old_env = os.environ.get("NEWS_BACKFILL_DAYS")
    try:
        os.environ["NEWS_BACKFILL_DAYS"] = "5"
        check("backfill чете дните", backfill_days() == 5)
        os.environ["NEWS_BACKFILL_DAYS"] = "99"
        check("backfill има таван 14", backfill_days() == 14)
        os.environ["NEWS_BACKFILL_DAYS"] = "боклук"
        check("backfill гълта боклук", backfill_days() == 0)
        os.environ["NEWS_BACKFILL_DAYS"] = "-3"
        check("backfill гълта минус", backfill_days() == 0)
        os.environ["NEWS_BACKFILL_DAYS"] = ""
        check("празният backfill = нормален прозорец", backfill_days() == 0)
    finally:
        if old_env is None:
            os.environ.pop("NEWS_BACKFILL_DAYS", None)
        else:
            os.environ["NEWS_BACKFILL_DAYS"] = old_env

    # --- 15. СЧУПЕНОТО СЪСТОЯНИЕ И ОТРОВНИЯТ THREAD ID НЕ УБИВАТ РЪНА ---
    tmp2 = STATE_FILE + ".selftest2"
    old_sf = globals()["STATE_FILE"]
    globals()["STATE_FILE"] = tmp2
    try:
        with open(tmp2, "w", encoding="utf-8") as f:
            f.write("{счупен json")
        k3, t3 = load_state()
        check("счупеният state дава чисто начало", k3 == [] and t3 == [])
        with open(tmp2, "w", encoding="utf-8") as f:
            f.write("")
        k4, t4 = load_state()
        check("празният state дава чисто начало", k4 == [] and t4 == [])
    finally:
        globals()["STATE_FILE"] = old_sf
        try:
            os.remove(tmp2)
        except Exception:
            pass
    globals()["NEWS_THREAD_ID"] = chr(178)     # ² : минава isdigit, чупи int
    check("екзотичната Unicode-цифра пада към 26", news_thread() == 26)
    globals()["NEWS_THREAD_ID"] = "26"

    print("SELFTEST: " + str(ok) + " наред, " + str(len(bad)) + " проблема.")
    for b in bad:
        print("  ❌ " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    if os.environ.get("NEWS_MODE", "") == "selftest" or "--selftest" in sys.argv:
        sys.exit(run_selftest())
    main()
