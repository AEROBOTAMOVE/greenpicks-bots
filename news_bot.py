# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БОТ №1 „НОВИНАРЯТ" 📰   (версия С КАРТИНКИ)

ЖЕЛЕЗНИ ПРАВИЛА (заповед на шефа, без изключения):
  1. ВСИЧКИ новини отиват САМО в стая 26 „Новини" (env NEWS_THREAD_ID).
  2. Стаи 5/6/7/8 (Футбол, Баскетбол, Тенис на маса, Волейбол) НЕ получават новини —
     в тях влизат САМО срещите по направление.
  3. КАНАЛЪТ не получава новини — той е за човека-типстер.
  4. Стая 4 „Фишове на деня" е само за човека — бот не пише там.
  5. Вътре в стая 26 новините са РАЗДЕЛЕНИ ПО СПОРТ, в реда
     🏓 Тенис на маса → 🏐 Волейбол → 🏀 Баскетбол → ⚽ Футбол → 📰 Други спортове.
     Спорт без новини се пропуска мълчаливо.
  6. Тих ден (нищо важно) = НЕ праща нищо. Тишината е злато.

НОВОТО В ТАЗИ ВЕРСИЯ (искане на шефа: „новината трябва да е с КАРТИНКА"):
  • Всяка новина е ОТДЕЛЕН ПОСТ СЪС СНИМКА (sendPhoto), а не ред с линк.
    Картинката се вади от самата емисия: media:content / media:thumbnail /
    enclosure / първото <img> в описанието; ако там няма — един евтин опит за
    og:image от страницата на статията; ако и това няма — чист текстов пост.
    Новина НИКОГА не се изпуска заради липсваща/счупена картинка.
  • Подписът е ТЯСЕН (Telegram таван 1024): спорт-емоджи + удебелено заглавие +
    един ред контекст + източник и час.
  • Преди снимките на всеки спорт върви КЪСО заглавие на секцията.
  • ТАВАНИ, за да не става стена: NEWS_PER_SPORT (3), NEWS_MAX_GENERAL (3),
    NEWS_MAX_TOTAL (10 снимки на пускане).
  • ПАМЕТТА Е ЗАСИЛЕНА (шефът виждаше повторения): помни се нормализирано
    заглавие + адрес + адреса на картинката, и се сравнява с последно пратените
    заглавия по общи дълги думи — същата история от друг източник не минава пак.
  • ЗАКОН: български закон забранява реклама на хазарт. Заглавие с име на
    букмейкър се ПРОПУСКА; картинка с букмейкър в адреса не се ползва; емисии с
    хазартен спонсор в кадъра (Дартс PDC) вървят само като текст без визитка.

Пуска се от GitHub Actions 3x дневно. Помни пратеното в sent_news.json (комитва се обратно).
Бележка за деплой: файлът е писан БЕЗ обратни наклонени черти (нов ред = NL = chr(10),
regex-границите на думи = LB/RB, кавичките в regex = chr(34)/chr(39)).
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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")              # групата (-100...)
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")        # каналът — САМО за проверка, НЕ пишем в него
NEWS_THREAD_ID = os.environ.get("NEWS_THREAD_ID", "26") or "26"   # 📰 Новини — ЕДИНСТВЕНАТА стая за новини
NEWS_ROOM_FALLBACK = "26"

# 🚫 Стаи, в които новинарят НЯМА право да пише, дори да го „помолят" през env:
# 4 = Фишове на деня (само човекът), 5/6/7/8 = спортните стаи (само срещи), 1 = общ чат.
FORBIDDEN_THREADS = {1, 4, 5, 6, 7, 8}

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


# 🎯 РАЗПОЗНАВАНЕТО ПО СПОРТ. РЕДЪТ Е ВАЖЕН: специфичните спортове ПРЕДИ футбола
# (волейболният ЦСКА съдържа „волейбол" -> хваща се преди клубното име във football).
#
# ⚠️ ВНИМАНИЕ: полето "thread" вече НЕ е стая 5/6/7/8 — всички стойности сочат към
# стая 26 „Новини". Новини в спортните стаи са ЗАБРАНЕНИ (правило 2). Полето стои
# само за обратна съвместимост (news_showcase.py го чете) и умишлено е пренасочено.
SPORT_ROOMS = {
    "tabletennis": {"thread": NEWS_THREAD_ID, "title": "🏓 ТЕНИС НА МАСА — новини",
                    "pat": "|".join(["тенис на маса", "table tennis", "ping pong", "пинг понг",
                                     wb("wtt"), wb("ittf"), wb("ettu"), "тенисът на маса"])},
    "volleyball":  {"thread": NEWS_THREAD_ID, "title": "🏐 ВОЛЕЙБОЛ — новини",
                    # ⚠️ НЕ слагай голото „volley" — във футбола „stunning volley" е удар с
                    # воле и би откраднал футболни новини в волейболната секция.
                    "pat": "|".join(["волейбол", "volleyball", "siatkow", "pallavolo", wb("vnl"),
                                     wb("cev"), "plusliga", "superlega", "николов", "соколов",
                                     "казийски", "лига на нациите", "beach volley"])},
    "basketball":  {"thread": NEWS_THREAD_ID, "title": "🏀 БАСКЕТБОЛ — новини",
                    "pat": "|".join(["баскет", "basketball", wb("nba"), wb("wnba"), "евролига",
                                     "euroleague", wb("fiba"), "triple-double", "леброн", "lebron",
                                     "йокич", "jokic", "дончич", "doncic", "еврокъп", "eurocup"])},
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
TOP_FOOTBALL = "|".join([
    "champions league", "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
    "europa league", "световно", "европейско", "мондиал", "national team", "реал мадрид",
    "барселона", "байерн", "ливърпул", "манчестър", "арсенал", "челси", "тотнъм", "псж",
    "ювентус", "интер", "милан", "атлетико", wb("fifa"), wb("uefa"),
])


def classify(title):
    """Заглавие -> ключ на спорт или None (обща новина). Пази стария си вид."""
    t = title.lower()
    for key, room in SPORT_ROOMS.items():
        if re.search(room["pat"], t):
            return key
    return None


# 🔗 ВТОРИ СИГНАЛ: разделът в адреса. „Борусия Дортмунд готви трансфер" няма нито една
# футболна дума, но линкът е .../football-sviat/... — така новината отива при ФУТБОЛА
# (и минава през филтъра TOP_FOOTBALL), вместо да цапа „Други спортове".
# Същият ред както горе: специфичните спортове преди футбола.
LINK_SPORT = [
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
SECTION_ORDER = ["tabletennis", "volleyball", "basketball", "football", None]
SECTION_HEAD = {
    "tabletennis": "🏓 ТЕНИС НА МАСА",
    "volleyball": "🏐 ВОЛЕЙБОЛ",
    "basketball": "🏀 БАСКЕТБОЛ",
    "football": "⚽ ФУТБОЛ",
    None: "📰 ДРУГИ СПОРТОВЕ",
}

STATE_FILE = "sent_news.json"
TITLES_FILE = "last_news_titles.json"          # мост към Анализатора (matches_bot.py)
MAX_ITEMS = int(os.environ.get("NEWS_MAX_GENERAL", "3"))   # таван за „Други спортове"
PER_SPORT = int(os.environ.get("NEWS_PER_SPORT", "3"))     # таван за всеки от 4-те спорта
MAX_TOTAL = int(os.environ.get("NEWS_MAX_TOTAL", "10"))    # общ таван снимки на едно пускане
OG_MAX = int(os.environ.get("NEWS_OG_MAX", "6"))           # най-много допълнителни заявки за og:image
SHOW_HEADERS = os.environ.get("NEWS_SECTION_HEADERS", "1") != "0"
VERIFY_IMG = os.environ.get("NEWS_VERIFY_IMG", "1") != "0"
MIN_SCORE = 3          # под този скор обща новина не минава
STATE_KEEP = 1500      # колко ключа помним
SENT_TITLES_KEEP = 300 # колко пратени заглавия помним за сравнение „същата история"
TITLES_KEEP = 200      # колко заглавия подаваме на Анализатора
PER_FEED = 20          # най-много записи, които четем от един източник
MAX_AGE_H = int(os.environ.get("NEWS_MAX_AGE_H", "72"))    # по-стари от това не са „свежи"
TG_LIMIT = 3500        # лимитът на Telegram е 4096 — държим запас за емоджита
TG_HARD = 4000         # аварийна ножица: нито един ТЕКСТОВ пост не тръгва по-дълъг от това
CAPTION_HARD = 1000    # таванът на подпис под снимка е 1024 — държим запас
FETCH_WORKERS = 8      # източниците се дърпат едновременно (иначе 42 бавни адреса = 8 минути)
GAP_PHOTO = 2.0        # пауза между снимките (Telegram пуска ~20 съобщения в минута)
GAP_TEXT = 1.2

# 📡 ИЗТОЧНИЦИ. Трети елемент = подсказка за спорт (специализиран сайт: заглавието
# „Poland beat Italy 3:1" няма думата „волейбол", но източникът я знае).
# "other" = ниша, която НЕ е един от 4-те спорта -> отива в „Други спортове".
# Мъртъв/сменен адрес не е проблем: fetch/parse го прескачат тихо (виж collect_feeds).
#
# ✅ Всички адреси тук са ПРОВЕРЕНИ наживо на 28.07.2026 (връщат истински записи),
# с две изключения, оставени нарочно: ITTF (сега 403 от Cloudflare) и EuroLeague
# (сега 429) — това са каноничните източници и адресът им е верен, просто ни спират;
# от сървъра на GitHub може да минат.
# Отпаднаха при проверката (404 / HTML вместо XML / виснат до таймаут и затова НЕ ги
# слагаме): CEV, Volleyball World, PlusLiga, FIVB, volleyball.bg, bfvolleyball.bg,
# NBA.com, BasketNews, FIBA, HoopsHype, SLAM, bgbasket, WTT, bttf.bg, UEFA, Goal,
# Football365, DartsNews, dnes.bg, sportni.bg, nova.bg, btvsport, topsport.bg,
# novinite.bg, vesti.bg, trud.bg, monitor.bg, standartnews, dnevnik.bg, sportuvai.bg.
FEED_SOURCES = [
    # --- български общи спортни сайтове (носят и волейбол/тенис на маса) ---
    ("Gong", "https://gong.bg/rss", None),
    ("Sportal", "https://www.sportal.bg/rss", None),
    ("Dsport", "https://dsport.bg/rss", None),
    ("Blitz Спорт", "https://blitz.bg/rss/sport", None),
    ("Sportlive", "https://sportlive.bg/rss", None),
    ("Actualno Спорт", "https://www.actualno.com/rss/sport", None),
    ("24 часа Спорт", "https://www.24chasa.bg/rss/sport", None),
    ("Сега Спорт", "https://www.segabg.com/rss/sport", None),
    # --- световни общи ---
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml", None),
    ("Sky Sports", "https://www.skysports.com/rss/12040", None),
    ("ESPN", "https://www.espn.com/espn/rss/news", None),
    ("Guardian Sport", "https://www.theguardian.com/sport/rss", None),
    # --- 🏓 тенис на маса (най-оскъдният спорт — затова и блогове) ---
    ("ETTU", "https://www.ettu.org/rss", "tabletennis"),
    ("TT England", "https://tabletennisengland.co.uk/feed/", "tabletennis"),
    ("Butterfly TT", "https://www.butterflyonline.com/feed/", "tabletennis"),
    ("TableTennisDaily", "https://www.tabletennisdaily.com/forum/forums/-/index.rss", "tabletennis"),
    ("ExpertTT", "https://www.experttabletennis.com/feed/", "tabletennis"),
    ("ITTF", "https://www.ittf.com/feed/", "tabletennis"),
    # --- 🏐 волейбол ---
    ("WorldOfVolley", "https://worldofvolley.com/feed/", "volleyball"),
    ("Volleywood", "https://www.volleywood.net/feed/", "volleyball"),
    ("LegaVolley", "https://www.legavolley.it/feed/", "volleyball"),
    ("Gazzetta Волей", "https://www.gazzetta.it/rss/volley.xml", "volleyball"),
    ("iVolleyMagazine", "https://www.ivolleymagazine.it/feed/", "volleyball"),
    ("VolleyCountry", "https://www.volleycountry.com/feed/", "volleyball"),
    ("VolleyballMag", "https://volleyballmag.com/feed/", "volleyball"),
    ("Volleyverse", "https://volleyverse.com/feed/", "volleyball"),
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
    ("90min", "https://www.90min.com/posts.rss", "football"),
    # --- 🎯 ниши за „Други спортове" ---
    ("Дартс PDC", "https://www.pdc.tv/rss.xml", "other"),
    ("Тенис ESPN", "https://www.espn.com/espn/rss/tennis/news", "other"),
]

# Съвместимост: news_showcase.py прави „for source, url in nb.FEEDS".
FEEDS = [(name, url) for name, url, hint in FEED_SOURCES]
FEED_SPORT = {name: hint for name, url, hint in FEED_SOURCES if hint}

# Форуми, блогове, ревюта и училищни лиги: съдържанието им е разговорно/вечно
# („Barefoot shoes", „How to Beat a Chopper", „When does the season start?").
# Пускаме ги в спорта им, но искаме поне 1 точка — да не пълнят картата с
# дрънканици, когато има истински новини.
FEED_WEAK = {"TableTennisDaily", "Butterfly TT", "ExpertTT", "VolleyCountry",
             "VolleyballMag", "Volleyverse", "NCAA Волейбол", "BallnEurope"}

# 🚫 ЕМИСИИ С ХАЗАРТЕН СПОНСОР В КАДЪРА. Проверено: снимките на PDC са от турнир,
# кръстен на букмейкър — рекламни пана пълнят кадъра. Български закон забранява
# реклама на хазарт, а ние не можем да четем текста в снимката. Затова: без снимка,
# без визитка на линка (тя щеше да извади същата снимка) — само чист текст.
BRAND_RISK_FEEDS = {"Дартс PDC"}

# Сайтове, които връщат ПРАЗНО тяло на бот — няма смисъл да хабим заявка за og:image.
OG_SKIP_MARKS = ["espn"]


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 GreenRoomBot/2.0",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_post(url, data, timeout=25):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "GreenRoomBot/2.0"})
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


BOILER = [" the post ", "continue reading", "read more", "appeared first on",
          "виж още", "прочети още", "още по темата"]


def item_summary(el, title):
    """Един ред контекст изпод заглавието. Празно, ако емисията не дава смислен текст."""
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
            txt = " ".join(txt.split())
            if len(txt) < 30:
                continue
            if low.startswith((title or "").lower()[:40]):
                txt = txt[len(title):].strip(" -–—:·")
                if len(txt) < 30:
                    continue
            return txt
    except Exception:
        pass
    return ""


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
            "User-Agent": "Mozilla/5.0 GreenRoomBot/2.0", "Accept": "image/*,*/*"})
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
def parse_rss(source, raw):
    """RSS <item> и Atom <entry>.
    Връща [{source, title, link, date, imgs, summary}] — новите полета са
    добавка; старите потребители (news_showcase.py) не усещат разлика."""
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
        if title:
            items.append({"source": source, "title": title, "link": link,
                          "date": parse_date(item.findtext("pubDate")),
                          "imgs": image_candidates(item),
                          "summary": item_summary(item, title),
                          "cat": item_category(item)})
    # Atom fallback
    if not items:
        ns = ATOM_NS
        for e in root.iter(ns + "entry"):
            title = clean_title(text_of(e.find(ns + "title")))
            link_el = e.find(ns + "link")
            link = (link_el.get("href") or "").strip() if link_el is not None else ""
            if title:
                items.append({"source": source, "title": title, "link": link,
                              "date": parse_date(e.findtext(ns + "published") or e.findtext(ns + "updated")),
                              "imgs": image_candidates(e),
                              "summary": item_summary(e, title),
                              "cat": item_category(e)})
    return items


def big_words(text):
    return set(re.findall("[а-яa-z]{6,}", text.lower()))


# Ключови думи -> точки (важност).
KEYWORDS = {
    5: [wp("трансфер"), wp("transfer"), wp("уволн"), wp("sacked"), wp("fired"), wp("оставк"),
        wp("почина"), wp("died"), wp("скандал"), wp("scandal"), wp("дисквалиф"), wp("banned")],
    4: [wp("контузи"), wp("injur"), wp("аут за"), wp("ruled out"), wp("финал"), wp("final"),
        wp("титла"), wp("title"), wp("шампион"), wp("champion"), wp("злато"), wp("медал")],
    3: [wp("дерби"), wp("derby"), wp("рекорд"), wp("record"), wp("класик"), wp("clasico"),
        "връща се", wb("return"), wp("дебют"), wp("debut"), wp("полуфинал"), wp("semifinal")],
    2: [wp("побед"), wp("загуб"), wp("равенство"), wb("гол"), wp("голове"), wb("гола"),
        wp("goal"), wb("win"), wb("loss"), wb("draw"), wp("класира")],
}

SPORT_EMOJI = [("футбол|football|soccer|уефа|" + wb("fifa") + "|" + wb("uefa"), "⚽"),
               ("баскет|basket|" + wb("nba"), "🏀"),
               ("тенис на маса|table tennis|пинг понг", "🏓"),
               ("волейбол|volleyball", "🏐"),
               ("тенис|tennis", "🎾"),
               ("дартс|darts", "🎯")]

# Емоджи по секция — резерва, когато заглавието не съдържа името на спорта
# („Полша срази Италия с 3:1" е волейбол, но думата я няма).
ROOM_EMOJI = {"tabletennis": "🏓", "volleyball": "🏐", "basketball": "🏀", "football": "⚽"}


def score_item(title, all_titles, cache=None):
    """Важност по ключови думи + буст, ако друг източник пише за същото.
    cache = {заглавие: множество думи} (само ускорение, поведението е същото)."""
    t = title.lower()
    score = 0
    for pts, words in KEYWORDS.items():
        if any(re.search(w, t) for w in words):
            score = max(score, pts)
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
    """Емоджи за поста: първо от заглавието, после от секцията."""
    e = sport_emoji(c.get("title") or "")
    if e == "📌":
        e = ROOM_EMOJI.get(c.get("room")) or "📌"
    return e


def h(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def route_item(item):
    """Връща (секция, нужен_скор). Първо думите в заглавието, после специализирания източник.
    Секцията е САМО етикет вътре в стая 26 — НЕ е Telegram thread."""
    room = classify(item["title"]) or classify_link(item.get("link"))
    if room is None and item.get("cat"):
        room = classify(item["cat"])
    hint = FEED_SPORT.get(item["source"])
    if hint in SPORT_ROOMS:
        # специализиран източник = нишата е ценна сама по себе си (блоговете — с 1 точка)
        return (room or hint), (1 if item["source"] in FEED_WEAK else 0)
    if room is not None:
        return room, 1
    if hint == "other":
        return None, 1
    return None, MIN_SCORE


def dedup(items, limit):
    """Реже почти еднакви заглавия (2+ общи дълги думи) и връща най-много limit броя."""
    out = []
    for c in items:
        cw = big_words(c["title"])
        if any(len(cw & big_words(t["title"])) >= 2 for t in out):
            continue
        out.append(c)
        if len(out) == limit:
            break
    return out


# ==================================================== ПАМЕТ (без повторения) ==
# Три ключа на новина + сравнение по думи с последно пратените заглавия.
# Точно това лекува оплакването „каналите са пълни с повтарящи се съобщения".
def norm_title(t):
    s = (t or "").lower()
    s = re.sub("[^0-9a-zа-яёA-ZА-Я ]+", " ", s)
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


def item_keys(c):
    """Всички ключове, по които разпознаваме „това вече го пратихме"."""
    out = [title_key(c["title"]), h(c["title"])]      # h(...) = старият формат на паметта
    lk = link_key(c.get("link"))
    if lk:
        out.append(lk)
    return out


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
        except (json.JSONDecodeError, OSError):
            print("WARN: повреден state — започвам начисто.")
    return keys, titles


def store(posted, old_keys, sent_titles):
    """Записва паметта СЛЕД ВСЯКА пратена новина, не само накрая: ако рънърът умре
    по средата, следващото пускане НЕ повтаря вече публикуваното."""
    new_keys = []
    for c in posted:
        new_keys += item_keys(c)
        ik = image_key(c.get("used_img") or "")
        if ik:
            new_keys.append(ik)
    fresh = set(new_keys)
    keys = new_keys + [k for k in old_keys if k not in fresh]
    titles = [c["title"] for c in posted] + sent_titles
    try:
        save_state(keys[:STATE_KEEP], titles[:SENT_TITLES_KEEP])
        return True
    except OSError as e:
        print("WARN: не мога да запиша " + STATE_FILE + ": " + str(e)[:120])
        return False


def save_state(keys, titles):
    data = {"v": 2, "keys": list(keys)[:STATE_KEEP], "titles": titles[:SENT_TITLES_KEEP]}
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)     # атомарно: убит рънър не оставя счупен JSON


# ---------------------------------------------------------------- пращане ---
def news_thread():
    """ЕДИНСТВЕНАТА позволена стая за новини. Пази и от чужда/сбъркана env-стойност:
    стаи 1/4/5/6/7/8 са забранени за новини и падат обратно към 26."""
    tid = str(NEWS_THREAD_ID or "").strip()
    if tid.isdigit() and int(tid) > 1 and int(tid) not in FORBIDDEN_THREADS:
        return int(tid)
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
    if len(caption) > 1024:
        # Аварийно: режем ЧИСТИЯ текст и чак после екранираме — сляпото рязане на
        # готов HTML може да среже таг наполовина и Telegram връща „can not parse entities".
        caption = esc(clip(clean_title(caption), 900))
    return tg_call("sendPhoto", {"chat_id": CHAT_ID, "photo": photo_url, "caption": caption,
                                 "parse_mode": "HTML", "message_thread_id": news_thread()},
                   timeout=45)


# ------------------------------------------------------------ съставяне ----
FOOTER = "🦖 THE GREEN ROOM · 📰 Новини"


def esc(s):
    """Видим текст: Telegram иска екранирани само & < >. Кавичките и апострофите
    остават както са — иначе на екрана излиза суровото &#x27; вместо '."""
    return html.escape(s or "", quote=False)


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
    return "🔥" if c["score"] >= 5 else ("⚡" if c["score"] >= 4 else "▫️")


def link_line(c, clock):
    src = esc(c["source"])
    if is_url(c["link"]):
        return '<a href="' + html.escape(c["link"], quote=True) + '">' + src + " →</a> · " + clock
    return "<i>" + src + "</i> · " + clock


def caption_for(c, clock, title_len=190, sum_len=170):
    """Подпис под снимката. Таван 1024 — държим се под CAPTION_HARD.
    Ред 1: спорт-емоджи + важност + заглавие. Ред 2: един ред контекст. Ред 3: източник и час."""
    head = emoji_for(c) + " " + icon_of(c) + " <b>" + esc(clip(c["title"], title_len)) + "</b>"
    body = ""
    summary = c.get("summary") or ""
    if summary and sum_len > 0:
        body = NL + NL + esc(clip(summary, sum_len))
    cap = head + body + NL + NL + link_line(c, clock)
    if len(cap) > CAPTION_HARD:
        if sum_len > 0:
            return caption_for(c, clock, title_len=title_len, sum_len=0)
        if title_len > 90:
            return caption_for(c, clock, title_len=90, sum_len=0)
        cap = cap[:CAPTION_HARD] + " …"
    return cap


def text_for(c, clock):
    """Резервният ЧИСТ ТЕКСТ, когато няма снимка или Telegram я отказа."""
    parts = [emoji_for(c) + " " + icon_of(c) + " <b>" + esc(clip(c["title"], 300)) + "</b>"]
    summary = c.get("summary") or ""
    if summary:
        parts.append(esc(clip(summary, 300)))
    parts.append(link_line(c, clock))
    return (NL + NL).join(parts)


def section_header(key, count, clock, first):
    word = "новина" if count == 1 else "новини"
    head = "<b>" + esc(SECTION_HEAD.get(key) or "📰 НОВИНИ") + "</b> · " + clock + " · " + str(count) + " " + word
    if first:
        head = head + NL + FOOTER
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
        return source, parse_rss(source, fetch(url))[:PER_FEED], ""
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
def allocate(groups):
    """Таван за всеки спорт + ОБЩ таван, за да не става стена от снимки.
    Реже се от най-ниския приоритет нагоре (редът на шефа: ТТ, волей, баскет, футбол, други)."""
    sections = []
    for key in SECTION_ORDER:
        cap = MAX_ITEMS if key is None else PER_SPORT
        items = dedup(groups.get(key) or [], cap)
        if items:
            sections.append([key, items])
    total = sum(len(items) for key, items in sections)
    while total > MAX_TOTAL and sections:
        cut = False
        for entry in reversed(sections):
            if len(entry[1]) > 1:
                entry[1] = entry[1][:-1]
                total -= 1
                cut = True
                break
        if not cut:
            sections = sections[:MAX_TOTAL]      # всички са по 1 — режем цели секции
            total = len(sections)
            break
    return sections


def strip_cross_dupes(sections):
    """dedup() чисти повторенията ВЪТРЕ в секция. Тук махаме една и съща история,
    паднала в ДВЕ различни секции (напр. „Гърция — Италия" и като волейбол, и като
    „други"). 3+ общи дълги думи = същата история."""
    seen = []
    for entry in sections:
        keep = []
        for c in entry[1]:
            w = big_words(c["title"])
            if any(len(w & s) >= 3 for s in seen):
                continue
            seen.append(w)
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
    for u in (c.get("imgs") or [])[:3]:
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
        print("--- ПРОБЕН ПОСТ (" + way + ", подпис " + str(len(caption)) + " знака) ---")
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
    preview = is_url(c["link"]) and c["source"] not in BRAND_RISK_FEEDS
    if tg_send(text_for(c, clock), preview=preview):
        return True, "текст"
    return False, ""


def main():
    dry = os.environ.get("NEWS_DRY_RUN", "") == "1"
    if not dry and (not BOT_TOKEN or not CHAT_ID):
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)
    # ЗАЩИТА: новини в канала са забранени (правило 3).
    if CHANNEL_ID and str(CHAT_ID).strip() == str(CHANNEL_ID).strip():
        print("СТОП: CHAT_ID сочи към КАНАЛА. Новини в канала са забранени — не пращам нищо.")
        sys.exit(1)

    old_keys, sent_titles = load_state()
    sent_keys = set(old_keys)
    sent_sigs = [big_words(t) for t in sent_titles]

    collected, alive = collect_feeds()
    print("Източници: " + str(alive) + " живи от " + str(len(FEEDS)) + ", записи: " + str(len(collected)) + ".")

    # свежест + махане на еднакви заглавия от различни източници
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_H)
    recent = []
    seen_titles = set()
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
    write_titles(all_titles)
    cache = {t: big_words(t) for t in all_titles}

    skipped_repeat = 0
    skipped_law = 0
    fresh = []
    for c in recent:
        # 1) ПАМЕТ: точно същото заглавие / същият адрес вече е пращано
        if any(k in sent_keys for k in item_keys(c)):
            skipped_repeat += 1
            continue
        # 2) ПАМЕТ: СЪЩАТА ИСТОРИЯ с други думи (3+ общи дълги думи с пратено заглавие)
        mine = cache.get(c["title"]) or big_words(c["title"])
        if any(len(mine & sig) >= 3 for sig in sent_sigs):
            skipped_repeat += 1
            continue
        # 3) ЗАКОН: име на букмейкър в заглавието не се публикува
        if bookie_hit(c["title"]):
            skipped_law += 1
            continue
        c["score"] = score_item(c["title"], all_titles, cache)
        room, need = route_item(c)
        c["room"] = room
        # ⚽ филтър: футбол минава САМО ако е топ-лига/голяма история (или мега-новина score>=4)
        if room == "football" and c["score"] < 4 and not re.search(TOP_FOOTBALL, c["title"].lower()):
            continue
        if c["score"] >= need:
            fresh.append(c)

    fresh.sort(key=lambda x: -x["score"])
    print("Пропуснати като повторение: " + str(skipped_repeat) + ", по закон (хазарт): " + str(skipped_law) + ".")

    groups = {k: [] for k in SECTION_ORDER}
    for c in fresh:
        groups[c["room"]].append(c)

    sections = strip_cross_dupes(allocate(groups))
    chosen = [c for key, items in sections for c in items]
    if not chosen:
        print("Тих ден — нищо важно. Мълчим.")
        return

    got_og = fill_og_images(chosen)
    with_img = sum(1 for c in chosen if c.get("imgs"))
    print("Избрани " + str(len(chosen)) + " новини; със снимка от емисията или og: " +
          str(with_img) + " (og добави " + str(got_og) + ").")

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


if __name__ == "__main__":
    main()
