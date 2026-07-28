# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БОТ №1 „НОВИНАРЯТ" 📰

ЖЕЛЕЗНИ ПРАВИЛА (заповед на шефа, без изключения):
  1. ВСИЧКИ новини отиват САМО в стая 26 „Новини" (env NEWS_THREAD_ID).
  2. Стаи 5/6/7/8 (Футбол, Баскетбол, Тенис на маса, Волейбол) НЕ получават новини —
     в тях влизат САМО срещите по направление.
  3. КАНАЛЪТ не получава новини — той е за човека-типстер.
  4. Стая 4 „Фишове на деня" е само за човека — бот не пише там.
  5. Вътре в стая 26 новините са РАЗДЕЛЕНИ ПО СПОРТ: по един пост на спорт,
     в реда 🏓 Тенис на маса → 🏐 Волейбол → 🏀 Баскетбол → ⚽ Футбол → 📰 Други спортове.
     Спорт без новини се пропуска мълчаливо.
  6. Тих ден (нищо важно) = НЕ праща нищо. Тишината е злато.

Пуска се от GitHub Actions 3x дневно. Помни пратеното в sent_news.json (комитва се обратно).
Бележка за деплой: файлът е писан БЕЗ обратни наклонени черти (нов ред = NL = chr(10),
regex-границите на думи = LB/RB вместо границата на дума).
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
    ("volleyball", "|".join(["volleyball", "voleybol", "volejbol", "-volley", "/volley", "pallavolo"])),
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
MAX_ITEMS = int(os.environ.get("NEWS_MAX_GENERAL", "5"))   # таван за „Други спортове"
PER_SPORT = int(os.environ.get("NEWS_PER_SPORT", "6"))     # таван за всеки от 4-те спорта
MIN_SCORE = 3          # под този скор обща новина не минава
STATE_KEEP = 1200      # колко хеша помним
TITLES_KEEP = 200      # колко заглавия подаваме на Анализатора
PER_FEED = 20          # най-много записи, които четем от един източник
MAX_AGE_H = int(os.environ.get("NEWS_MAX_AGE_H", "72"))    # по-стари от това не са „свежи"
TG_LIMIT = 3500        # лимитът на Telegram е 4096 — държим запас за емоджита
TG_HARD = 4000         # аварийна ножица: нито един пост не тръгва по-дълъг от това
FETCH_WORKERS = 8      # източниците се дърпат едновременно (иначе 42 бавни адреса = 8 минути)

# 📡 ИЗТОЧНИЦИ. Трети елемент = подсказка за спорт (специализиран сайт: заглавието
# „Poland beat Italy 3:1" няма думата „волейбол", но източникът я знае).
# "other" = ниша, която НЕ е един от 4-те спорта -> отива в „Други спортове".
# Мъртъв/сменен адрес не е проблем: fetch/parse го прескачат тихо (виж main).
#
# ✅ Всички адреси тук са ПРОВЕРЕНИ наживо на 28.07.2026 (връщат истински записи),
# с две изключения, оставени нарочно: ITTF (сега 403 от Cloudflare) и EuroLeague
# (сега 429) — това са каноничните източници и адресът им е верен, просто ни спират;
# от сървъра на GitHub може да минат. Отпаднаха (връщаха 404/HTML): CEV, Volleyball
# World, PlusLiga, volleyball.bg, NBA.com, BasketNews, WTT, bttf.bg, UEFA, DartsNews,
# dnes.bg (категорията не е спорт), sportni.bg (виси до таймаут).
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

# Форуми, блогове и ревюта: съдържанието им е разговорно („Barefoot shoes", „Mizuno
# Neo Jump Review"). Пускаме ги в спорта си, но искаме поне 1 точка — да не пълнят
# картата с дрънканици, когато има истински новини.
FEED_WEAK = {"TableTennisDaily", "Butterfly TT", "ExpertTT", "VolleyCountry",
             "VolleyballMag", "Volleyverse", "NCAA Волейбол", "BallnEurope"}

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


def parse_rss(source, raw):
    """RSS <item> и Atom <entry>. Връща [{source, title, link, date}]."""
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
                          "date": parse_date(item.findtext("pubDate"))})
    # Atom fallback
    if not items:
        ns = "{http://www.w3.org/2005/Atom}"
        for e in root.iter(ns + "entry"):
            title = clean_title(text_of(e.find(ns + "title")))
            link_el = e.find(ns + "link")
            link = (link_el.get("href") or "").strip() if link_el is not None else ""
            if title:
                items.append({"source": source, "title": title, "link": link,
                              "date": parse_date(e.findtext(ns + "published") or e.findtext(ns + "updated"))})
    return items


def big_words(text):
    return set(re.findall("[а-яa-z]{6,}", text.lower()))


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


def h(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def route_item(item):
    """Връща (стая, нужен_скор). Първо думите в заглавието, после специализирания източник.
    Стаята е САМО етикет за секцията в стая 26 — НЕ е Telegram thread."""
    room = classify(item["title"]) or classify_link(item.get("link"))
    hint = FEED_SPORT.get(item["source"])
    if hint in SPORT_ROOMS:
        # специализиран източник = нишата е ценна сама по себе си (форумите — с 1 точка)
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


# ---------------------------------------------------------------- пращане ---
def news_thread():
    """ЕДИНСТВЕНАТА позволена стая за новини."""
    tid = str(NEWS_THREAD_ID or "").strip()
    if tid.isdigit() and int(tid) > 1 and int(tid) not in FORBIDDEN_THREADS:
        return int(tid)
    print("WARN: непозволен NEWS_THREAD_ID " + repr(NEWS_THREAD_ID) + " — падам към стая " + NEWS_ROOM_FALLBACK + ".")
    return int(NEWS_ROOM_FALLBACK)


def tg_send(text, preview=False):
    """Праща В СТАЯ 26 и НИКЪДЕ другаде. Уважава 429. Грешка не спира другите постове."""
    if len(text) > TG_HARD:
        text = text[:TG_HARD - 2] + " …"
    api = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": (not preview),
               "message_thread_id": news_thread()}
    for attempt in range(4):
        try:
            data = urllib.parse.urlencode(payload).encode()
            resp = json.loads(fetch_post(api, data))
            if not resp.get("ok"):
                print("TG ERROR:", resp)
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
            print("TG HTTP", e.code, body[:300])
            return False
        except Exception as e:
            print("TG SEND FAIL:", e)
            return False
    return False


# ------------------------------------------------------------ съставяне ----
FOOTER = "🦖 THE GREEN ROOM · 📰 Новини"


def esc(s):
    """Видим текст: Telegram иска екранирани само & < >. Кавичките и апострофите
    остават както са — иначе на екрана излиза суровото &#x27; вместо '."""
    return html.escape(s or "", quote=False)


def item_line(c):
    icon = "🔥" if c["score"] >= 5 else ("⚡" if c["score"] >= 4 else "▫️")
    line = icon + " " + esc(c["title"])
    if is_url(c["link"]):
        line = line + NL + "     " + '<a href="' + html.escape(c["link"], quote=True) + '">' + esc(c["source"]) + " →</a>"
    else:
        line = line + NL + "     <i>" + esc(c["source"]) + "</i>"
    return line


def section_posts(key, items, clock):
    """Един спорт -> списък от (текст, новините вътре). Реже на втори пост при нужда."""
    head_txt = SECTION_HEAD.get(key) or "📰 НОВИНИ"
    base = len(head_txt) + len(FOOTER) + 40

    def render(part_no, chunk):
        title = "<b>" + esc(head_txt) + "</b> · " + clock
        if part_no > 1:
            title = title + " · част " + str(part_no)
        body = (NL + NL).join(item_line(x) for x in chunk)
        return title + NL + NL + body + NL + NL + FOOTER

    out = []
    chunk = []
    size = base
    for c in items:
        add = len(item_line(c)) + 2
        if chunk and size + add > TG_LIMIT:
            out.append((render(len(out) + 1, chunk), chunk))
            chunk = []
            size = base
        chunk.append(c)
        size += add
    if chunk:
        out.append((render(len(out) + 1, chunk), chunk))
    return out


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


def load_state():
    sent = []
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8-sig") as f:
                sent = json.load(f)
            if not isinstance(sent, list):
                sent = []
        except (json.JSONDecodeError, OSError):
            print("WARN: повреден state — започвам начисто.")
            sent = []
    return [s for s in sent if isinstance(s, str)]


def main():
    dry = os.environ.get("NEWS_DRY_RUN", "") == "1"
    if not dry and (not BOT_TOKEN or not CHAT_ID):
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)
    # ЗАЩИТА: новини в канала са забранени (правило 3).
    if CHANNEL_ID and str(CHAT_ID).strip() == str(CHANNEL_ID).strip():
        print("СТОП: CHAT_ID сочи към КАНАЛА. Новини в канала са забранени — не пращам нищо.")
        sys.exit(1)

    sent = load_state()
    sent_set = set(sent)

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

    fresh = []
    for c in recent:
        if c["key"] in sent_set:
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

    groups = {k: [] for k in SECTION_ORDER}
    for c in fresh:
        groups[c["room"]].append(c)

    clock = datetime.now(SOFIA).strftime("%H:%M")
    posted = []
    posts = 0
    for key in SECTION_ORDER:
        cap = MAX_ITEMS if key is None else PER_SPORT
        items = dedup(groups.get(key) or [], cap)
        if not items:
            continue
        parts = section_posts(key, items, clock)
        single = (len(parts) == 1 and len(items) == 1)
        for text, part_items in parts:
            if dry:
                print("--- ПРОБЕН ПОСТ (" + str(len(text)) + " знака) ---")
                print(text)
                posted += part_items
                posts += 1
                continue
            if tg_send(text, preview=single):
                posted += part_items
                posts += 1
            time.sleep(1.5)
        print(SECTION_HEAD.get(key) + " -> новини: " + str(len(items)) + ", постове: " + str(len(parts)) + ".")

    if not posted:
        print("Тих ден — нищо важно. Мълчим.")
        return

    if not dry:
        sent = ([c["key"] for c in posted] + sent)[:STATE_KEEP]
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(sent, f)
    print("Готово: " + str(len(posted)) + " новини в " + str(posts) + " поста, всичко в стая " + str(news_thread()) + " 📰.")


if __name__ == "__main__":
    main()
