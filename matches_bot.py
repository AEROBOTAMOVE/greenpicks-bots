# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БОТ „АНАЛИЗАТОРЪТ" 📅🧠

Две различни неща, две различни места:

  1) СРЕЩИТЕ ДНЕС  ->  спортните стаи, по направление.
       ⚽ Футбол        стая 5   (FOOTBALL_THREAD_ID)
       🏀 Баскетбол     стая 6   (BASKET_THREAD_ID)
       🏓 Тенис на маса стая 7   (TT_THREAD_ID)
       🏐 Волейбол      стая 8   (VOLLEY_THREAD_ID)
       🥊 Бойни спортове стая 328 (COMBAT_THREAD_ID) — предстоящите боеве и карти
     Там влиза САМО чистият списък със срещи: час, отбори, турнир.
     Никакви новини, никакви прогнози, никакви разсъждения.

  2) АНАЛИЗЪТ И ПРОГНОЗАТА  ->  стая 27 „БОТА ПРЕДРИЧА" (PREDICT_THREAD_ID).
     H2H, форма, острите стрелки, 📰 кръстосан флаг с новините и
     „какво казват числата" — всичко разсъждение живее там.

Забранено за този бот (желязно, пази се в post_room):
   4 Фишове на деня  — САМО човекът-типстер.
  26 Новини          — само news_bot.py.
  КАНАЛЪТ            — този файл няма функция, която да праща в канал.

Двигатели: TheSportsDB (всички спортове) + football-data.org за футбола,
ако има ключ. Бойните спортове идват от ESPN (mma/ufc и mma/pfl, без ключ) —
логиката НЕ е преписана тук, а се взима наготово от predictor.mma_fixtures.
Лимитите се пазят: 2.1 сек между заявки към TheSportsDB,
6.5 сек към football-data. Часовете са Europe/Sofia.
Само сериозни турнири — дребните лиги не влизат никъде.
Всяка прогноза е вероятност от статистика, не гаранция.
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import poster

SOFIA = ZoneInfo("Europe/Sofia")
NL = chr(10)
NL2 = chr(10) + chr(10)
Q1 = chr(8222)    # отваряща българска кавичка
Q2 = chr(8220)    # затваряща българска кавичка

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "-1004426592150")

FOOTBALL_THREAD = (os.environ.get("FOOTBALL_THREAD_ID") or "5").strip()
BASKET_THREAD = (os.environ.get("BASKET_THREAD_ID") or "6").strip()
TT_THREAD = (os.environ.get("TT_THREAD_ID") or "7").strip()
VOLLEY_THREAD = (os.environ.get("VOLLEY_THREAD_ID") or "8").strip()
COMBAT_THREAD = (os.environ.get("COMBAT_THREAD_ID") or "328").strip()
PREDICT_THREAD = (os.environ.get("PREDICT_THREAD_ID") or "27").strip()

# 🔴 ДОБАВЕНИ 18.08.2026 — ЗАРЕДЕНА МИНА, НЕ ЖИВ ДЕФЕКТ.
#
# predictor знае девет стаи по спорт; тук се знаеха ПЕТ. Тенисът (1963) и
# бейзболът (1965) липсваха изцяло. Днес е безвредно, защото ROOM_LISTS е
# изключен и този бот не праща в стаи по спорт — но включи ли се утре, два
# спорта нямаше да получат нищо, а останалите да получат.
#
# Номерата се вливат и от rooms_state.json, точно както в predictor: закован
# списък остарява в мига, в който се роди нова стая.
TENNIS_THREAD = (os.environ.get("TENNIS_THREAD_ID") or "1963").strip()
BASEBALL_THREAD = (os.environ.get("BASEBALL_THREAD_ID") or "1965").strip()


def _stai_ot_sastoyanie():
    """Номерата на стаите от rooms_state.json. Празно при липса или боклук."""
    put = (os.environ.get("ROOMS_STATE_FILE") or "rooms_state.json").strip()
    out = {}
    try:
        with open(put, encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict):
            for sport, zapis in d.items():
                n = (zapis or {}).get("thread")
                if n and int(n) > 0:
                    out[str(sport).strip()] = str(int(n))
    except Exception:                                        # noqa: BLE001
        pass
    return out


_ot_fayla = _stai_ot_sastoyanie()
TENNIS_THREAD = _ot_fayla.get("tennis", TENNIS_THREAD)
BASEBALL_THREAD = _ot_fayla.get("baseball", BASEBALL_THREAD)

# 🚫 Стаята на човека и стаята на новините. Ботът няма работа там.
FORBIDDEN_THREADS = {"4", "26"}
ALLOWED_THREADS = {FOOTBALL_THREAD, BASKET_THREAD, TT_THREAD, VOLLEY_THREAD,
                   COMBAT_THREAD, PREDICT_THREAD,
                   TENNIS_THREAD, BASEBALL_THREAD}
# И всяка стая, родена след последното качване — иначе новият спорт получава
# карти от predictor и мълчание оттук.
ALLOWED_THREADS |= {v for v in _ot_fayla.values()}
ALLOWED_THREADS -= FORBIDDEN_THREADS

SPORTSDB_KEY = os.environ.get("SPORTSDB_KEY") or "123"   # празен env = тест-ключ, не счупен URL
FOOTBALL_DATA_KEY = (os.environ.get("FOOTBALL_DATA_KEY") or "").strip()

API = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"
FD_API = "https://api.football-data.org/v4"

# Колко срещи максимум в една спортна стая. Откакто срещите идват от ESPN, а
# не от TheSportsDB, предлагането скочи от единици на стотици (тенисът на маса
# сам даде 403 за три дни) — таванът вече е това, което пази стаята четима.
# Подредбата преди отрязването е по тежест на турнира, тоест остават силните.
MAX_PER_ROOM = max(3, min(30, int((os.environ.get("MATCHES_PER_ROOM") or "8").strip())))
ANALYSIS_MAX = 3      # колко срещи разнищваме дълбоко (всяка струва заявки)
# Докъде напред гледа стаята на боевете. Галите са седмични — списък само за
# „днес" би мълчал шест дни от седем, затова прозорецът е по-широк.
try:
    COMBAT_DAYS = max(1, min(21, int((os.environ.get("COMBAT_DAYS_AHEAD") or "7").strip())))
except ValueError:
    COMBAT_DAYS = 7

# ПРИОРИТЕТ НА СПОРТОВЕТЕ (заповед на шефа: футболът е ПОСЛЕДЕН)
SPORTS = {
    "combat":      {"thread": COMBAT_THREAD, "emoji": "🥊", "title": "БОЙНИ СПОРТОВЕ",
                    "api": "Fighting", "prio": 95,
                    "head": "предстоящите боеве",
                    "only": "предстоящите боеве и картите"},
    "tabletennis": {"thread": TT_THREAD, "emoji": "🏓", "title": "ТЕНИС НА МАСА",
                    "api": "Table Tennis", "prio": 100},
    "volleyball":  {"thread": VOLLEY_THREAD, "emoji": "🏐", "title": "ВОЛЕЙБОЛ",
                    "api": "Volleyball", "prio": 90},
    "basketball":  {"thread": BASKET_THREAD, "emoji": "🏀", "title": "БАСКЕТБОЛ",
                    "api": "Basketball", "prio": 80},
    "football":    {"thread": FOOTBALL_THREAD, "emoji": "⚽", "title": "ФУТБОЛ",
                    "api": "Soccer", "prio": 10},
}
SPORT_ORDER = ["combat", "tabletennis", "volleyball", "basketball", "football"]

# Тежест на лигите по точно име (TheSportsDB ги пише така).
LEAGUE_WEIGHT = {
    "English Premier League": 10, "UEFA Champions League": 12, "Spanish La Liga": 10,
    "Italian Serie A": 9, "German Bundesliga": 9, "French Ligue 1": 8,
    "UEFA Europa League": 8, "English League Championship": 5,
    "Bulgarian First League": 7,
    "NBA": 10, "Euroleague": 8,
}

# football-data.org състезания (безплатният план)
FD_COMP_WEIGHT = {
    "CL": 12, "PL": 10, "PD": 10, "SA": 9, "BL1": 9, "FL1": 8, "DED": 6,
    "PPL": 6, "ELC": 5, "BSA": 6, "EC": 12, "WC": 12,
}

# Сериозните турнири по спорт (парче от името, малки букви) -> тежест.
# Каквото не влезе тук и не е в LEAGUE_WEIGHT — не влиза в нито една стая.
TOP_LEAGUES = {
    "football": [
        ("uefa champions league", 12), ("champions league", 12), ("world cup", 12),
        ("european championship", 11), ("europa league", 8), ("conference league", 6),
        ("english premier league", 10), ("premier league", 10),
        ("spanish la liga", 10), ("la liga", 10),
        ("italian serie a", 9), ("serie a", 9),
        ("german bundesliga", 9), ("bundesliga", 9),
        ("french ligue 1", 8), ("ligue 1", 8),
        ("nations league", 7), ("copa libertadores", 7),
        ("bulgarian first league", 7), ("efbet league", 7),
        ("eredivisie", 6), ("primeira liga", 6),
    ],
    "basketball": [
        ("wnba", 6), ("nba", 10), ("euroleague", 8), ("eurocup", 6),
        ("basketball champions league", 6), ("aba league", 5),
        ("lega basket serie a", 6), ("liga acb", 6), ("world cup", 9),
        ("eurobasket", 9), ("olympi", 9),
    ],
    "tabletennis": [
        ("wtt", 8), ("ittf", 8), ("world championship", 9),
        ("european championship", 8), ("champions league", 7), ("olympi", 9),
    ],
    "volleyball": [
        ("nations league", 9), ("world championship", 9), ("fivb", 8),
        ("champions league", 8), ("cev", 8), ("european championship", 8),
        ("superlega", 7), ("plusliga", 7), ("olympi", 9),
        ("bulgarian", 6), ("serie a1", 6),
    ],
}

# Каквото съдържа тези думи — отпада преди всичко останало (долни нива, ферми, „конвейерни" лиги).
BLOCK_WORDS = [
    "u17", "u18", "u19", "u20", "u21", "u23", "youth", "junior", "reserve",
    "amateur", "friendly", "friendlies", "regionalliga", "segunda", "serie b",
    "serie c", "liga 2", "liga 3", "ligue 2", "2. bundesliga", "league two",
    "setka", "tt cup", "tt elite", "liga pro", "challenger tour",
]


def esc(x):
    # 🔴 quote=False (11.08.2026). С подразбиращото се True апострофът излиза
    # като &#x27; и Telegram го показва буквално: в стая 27 висеше
    # „FIVB Volleyball Girls&#x27; U17 World Championship". Единственото, което
    # трябва да се екранира в HTML-режима на Telegram, е < > &.
    return html.escape(str(x or ""), quote=False)


def clip(text, limit=3900):
    """Telegram реже над 4096 — по-добре ние да отрежем чисто."""
    if len(text) <= limit:
        return text
    return text[:limit] + NL + "…(отрязано)"


def to_int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def date_bg(now):
    wd = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"][now.weekday()]
    return f"{wd}, {now.day}.{now.month:02d}"


def today_str():
    return datetime.now(timezone.utc).astimezone(SOFIA).strftime("%Y-%m-%d")


# ---------- ПРАЩАНЕ (един-единствен път навън, с пазач) ----------
# 🔴 СУХО ПУСКАНЕ (11.08.2026). Този файл беше ЕДИНСТВЕНИЯТ жив бот без него:
# предсказателят, оценителят, новинарят, съпортът и дневният го имат от седмици.
# Тоест единственият начин да видиш какво праща Анализаторът беше да го оставиш
# да го прати. Бот, който не може да се репетира, се разбира в продукцията —
# а стаята е на хората, не полигон.
# MATCHES_DRY_RUN=1 печата всяко съобщение с номера на стаята и не пуска нищо.
DRY_RUN = (os.environ.get("MATCHES_DRY_RUN") or "").strip() in ("1", "true", "yes", "да")
ROOM_LISTS = (os.environ.get("MATCHES_ROOM_LISTS", "0").strip() == "1")


def post_room(thread_id, text):
    """Единственият изход на бота. Забранените стаи се режат ТУК, не по-нагоре.
    Канал няма — този файл физически не може да прати в канал."""
    tid = str(thread_id or "").strip()
    if tid in FORBIDDEN_THREADS:
        print(f"ОТКАЗ: стая {tid} е забранена (човешки фишове / новини).")
        return False
    if tid not in ALLOWED_THREADS:
        print(f"ОТКАЗ: стая {tid} не е в разрешения списък на Анализатора.")
        return False
    if not tid.isdigit() or int(tid) <= 1:
        print(f"WARN: невалиден thread id {tid} — не пращам.")
        return False
    # Сухото пускане стои СЛЕД пазачите нарочно: така репетицията показва
    # точно каквото би минало и навън, включително кое е било отказано.
    if DRY_RUN:
        print("--- СУХО, стая " + tid + " ---")
        print(clip(text))
        print("---")
        return True
    if not CHAT_ID:
        print("Няма CHAT_ID — пропускам.")
        return False
    return poster.send_message(CHAT_ID, clip(text), thread_id=tid, preview=False)


# ---------- 🔢 ТРИТЕ ЧИСЛА: ВЗЕТИ / МИНАЛИ ФИЛТРИТЕ / ПУБЛИКУВАНИ ----------
# ЗАЩО СЪЩЕСТВУВА (01.09.2026)
#
# Ботът излизаше УСПЕШНО с нула публикации и печаташе едно-единствено
# изречение: Няма сериозни срещи днес (или API мълчи). Тоест ДВЕ различни
# състояния бяха слети в един ред и в един изход 0:
#     а) наистина няма мачове  -> нормално, случва се;
#     б) източникът мълчи      -> счупено, и никой отвън не разбира.
# Дневникът на Actions иска права и изчезва, така че нулата беше неразличима.
#
# ИЗМЕРЕНО НА ЖИВО от тази машина на 01.09.2026: тенисът на маса върна 0 срещи,
# защото липсваше модулът brotli, а самият predictor извика на глас, че това е
# провал на източника. Редът, който ТОЗИ файл отпечата, беше дума по дума
# същият като за празен ден: tabletennis: 0 срещи от ESPN за 1 дни.
#
# Затова всеки източник вече оставя ЧЕТИРИ числа, не едно:
#   vzeti    - колко срещи подаде
#   zaqvki   - колко пъти изобщо посегнахме навън заради него
#   provali  - колко от тези посягания се счупиха
#   grimna   - текстът на изключението, ако е гръмнал
# Присъдата се прави от тях, а не от голото нула.
IZVORI = {}


def vpishi_izvor(bucket, vzeti=0, zaqvki=0, provali=0, grimna=""):
    """Един ред в тефтера. СЪБИРА се, не се презаписва: един спорт може да е
    питан на два двигателя (ESPN, после TheSportsDB) и двата опита се броят."""
    z = IZVORI.setdefault(str(bucket), {"vzeti": 0, "zaqvki": 0,
                                        "provali": 0, "grimna": ""})
    z["vzeti"] += int(vzeti or 0)
    z["zaqvki"] += int(zaqvki or 0)
    z["provali"] += int(provali or 0)
    if grimna and not z["grimna"]:
        z["grimna"] = str(grimna)[:120]
    return z


def prisada(z):
    """ПРОВАЛ / ПРАЗНО / НАРЕД - присъда за ЕДИН източник.

    Редът на правилата е нарочен и е писан по измерване, не по усет:

      1. дошла е поне една среща -> НАРЕД. Изворът е доказано жив, каквото и
         да се е счупило по пътя. Това правило е ПЪРВО нарочно: иначе една
         преименувана вътрешност на predictor щеше да боядисва в червено ден
         с 36 взети футболни срещи.
      2. гръмнал е                -> ПРОВАЛ. Изключение не е празен ден.
      3. нула заявки              -> ПРОВАЛ. Не сме питали, значи нямаме право
         да твърдим, че няма. Тук влиза и случаят, в който броячите липсват.
      4. питали сме и ВСИЧКО се е счупило -> ПРОВАЛ. Точно днешният тенис на
         маса: 1 заявка, 1 счупена, 0 срещи.
      5. питали сме, отговорът е бил здрав, вътре нямаше нищо -> ПРАЗНО.
         Това е ЕДИНСТВЕНОТО състояние, което значи наистина няма мачове."""
    z = z or {}
    vzeti = int(z.get("vzeti") or 0)
    zaqvki = int(z.get("zaqvki") or 0)
    provali = int(z.get("provali") or 0)
    if vzeti > 0:
        opashka = ""
        if z.get("grimna") or provali:
            opashka = " (но " + str(provali) + " счупени заявки)"
        return "НАРЕД", str(vzeti) + " срещи" + opashka
    if z.get("grimna"):
        return "ПРОВАЛ", "източникът гръмна: " + str(z.get("grimna"))[:80]
    if zaqvki <= 0:
        return "ПРОВАЛ", "нула заявки - изворът изобщо не беше питан"
    if provali > 0:
        return "ПРОВАЛ", ("питахме " + str(zaqvki) + " пъти, счупиха се "
                          + str(provali) + " - нулата не е празен ден")
    return "ПРАЗНО", "питахме " + str(zaqvki) + " пъти, отговорът беше празен"


# ПРАГЪТ. Под колко ВЗЕТИ срещи за целия рън обявяваме, че изворът е рухнал.
#
# ИЗМЕРЕНО НА 01.09.2026 от тази машина, ден по ден през същите функции на
# predictor.py, които ботът вика (футбол + баскетбол + волейбол + тенис на
# маса), БЕЗ модула brotli и с половин отминал ден:
#     01.09 -> 24 взети · 02.09 -> 56 · 03.09 -> 30 · 04.09 -> 67
#     бойните спортове отделно: 18 за 7 дни напред
# Най-слабият измерен ден е 24, и то с изключен цял спорт. Работният рън в
# 08:30 има и brotli, и целия ден пред себе си. Затова 5 е достатъчно ниско,
# за да не гърми на слаба неделя, и достатъчно високо, за да хване срутване.
# Числото е КЛЮЧ, не константа - за да се мести без пипане на код.
try:
    MIN_VZETI = max(0, min(500, int((os.environ.get("MATCHES_MIN_VZETI") or "5").strip())))
except ValueError:
    MIN_VZETI = 5

# ПЪТЯТ НАЗАД без редакция на файла: MATCHES_MEK=1 обявява провала на глас,
# но връща зелен изход. Слага се в workflow-а и се маха, когато мине бурята.
MEK = (os.environ.get("MATCHES_MEK") or "").strip() in ("1", "true", "yes", "да")

# 🔴 ЧЕРНАТА КУТИЯ НА МАЧ-БОТА (01.09.2026).
# Тефтерът горе печата три числа и присъда по спорт — и толкова. Изходът на
# Actions иска админски права и изчезва; отвън се вижда само зелено или
# червено на рънa. Проверено живо срещу дървото на `main`: хранилището носи
# budilnik_state.json, predict_state.json, pazach_state.json и още девет —
# `matches_state.json` НЕ СЪЩЕСТВУВАШЕ. Тоест на въпроса «кога публикува
# последно и колко» нямаше отговор отвън, а четирийсет и седем зелени рънa
# не доказваха нито една публикация.
# Похватът е същият като в predictor.py (виж «ЧЕРНАТА КУТИЯ» там): пише се
# атомарно през .tmp и os.replace, за да не остане счупен JSON, ако рънърът
# бъде убит по средата.
# ⚠ Записът е безполезен без стъпката за връщане в matches.yml — затова
# долу в самопроверката се чете самият yml.
STATE_FILE = ((os.environ.get("MATCHES_STATE_FILE") or "").strip()
              or "matches_state.json")


def zapishi_sastoyanie(kod_surov, kod_varnat, publikuvani, preseti, gledani,
                       vzeti, now=None):
    """Тефтерът, но в ХРАНИЛИЩЕТО, не само в дневника на Actions.

    Връща True при успех. НИКОГА не хвърля: загубен запис е лошо, но паднал
    рън СЛЕД като постовете вече са тръгнали е по-лошо.
    """
    zapis = {
        "v": 1,
        "koga": (now or datetime.now(timezone.utc).astimezone(SOFIA)
                 ).strftime("%Y-%m-%d %H:%M"),
        # 🔴 ДВАТА кода, не един. MATCHES_MEK=1 връща 0 върху истински провал;
        # пише ли се само върнатият, мекият режим става невидим отвън — а
        # точно това е случаят, заради който човек отваря кутията.
        "izhod": int(kod_surov or 0),
        "izhod_varnat": int(kod_varnat or 0),
        "mek": bool(MEK),
        "prag": int(MIN_VZETI),
        "chisla": {"vzeti": int(vzeti or 0),
                   "preseti": int(preseti or 0),
                   "publikuvani": int(publikuvani or 0),
                   "gledani": int(gledani or 0)},
        "izvori": {},
    }
    for b in sorted(IZVORI):
        z = IZVORI[b] or {}
        p, zashto = prisada(z)
        zapis["izvori"][b] = {
            "prisada": p,
            "zashto": zashto,
            "vzeti": int(z.get("vzeti") or 0),
            "zaqvki": int(z.get("zaqvki") or 0),
            "provali": int(z.get("provali") or 0),
            "grimna": str(z.get("grimna") or ""),
        }
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(zapis, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, STATE_FILE)   # атомарно: убит рън не оставя счупено
        return True
    except Exception as e:                                   # noqa: BLE001
        print("Тефтерът НЕ се записа (" + str(e)[:70] + ") — постовете вече"
              " са тръгнали, затова това не сваля рънa.")
        return False


def ravnosmetka(publikuvani, preseti=0, gledani=0):
    """ТРИТЕ ЧИСЛА на глас, после присъда. Връща изходния код на целия рън.

    Нула публикации НЕ Е сама по себе си провал. Провал е нула публикации,
    която НЕ МОЖЕМ да обясним с жив и празен извор."""
    vzeti = sum(int((z or {}).get("vzeti") or 0) for z in IZVORI.values())
    provaleni, prazni = [], []
    print("")
    print("=== ТЕФТЕР НА ИЗТОЧНИЦИТЕ ===")
    for b in sorted(IZVORI):
        z = IZVORI[b] or {}
        p, zashto = prisada(z)
        if p == "ПРОВАЛ":
            provaleni.append(b)
        elif p == "ПРАЗНО":
            prazni.append(b)
        print("   %-12s %-7s взети=%-5d заявки=%-4d счупени=%-4d %s"
              % (b, p, int(z.get("vzeti") or 0), int(z.get("zaqvki") or 0),
                 int(z.get("provali") or 0), zashto))
    print("ВЗЕТИ ОТ ИЗТОЧНИКА: " + str(vzeti))
    print("МИНАЛИ ФИЛТРИТЕ:    " + str(int(preseti or 0))
          + ((" (от " + str(gledani) + " разровени)") if gledani else ""))
    print("ПУБЛИКУВАНИ:        " + str(int(publikuvani or 0)))

    kod = 0
    if publikuvani:
        if provaleni:
            print("ЧАСТИЧНО: " + ", ".join(provaleni) + " мълчи по ПРОВАЛ, не по"
                  " празен ден. Публикуваното идва от останалите източници.")
    elif vzeti < MIN_VZETI:
        print("ПРОВАЛ: " + str(vzeti) + " взети срещи при праг " + str(MIN_VZETI)
              + " - това НЕ е празен ден, това е мълчащ източник.")
        kod = 2
    elif provaleni:
        print("ПРОВАЛ: нула публикации, а източниците " + ", ".join(provaleni)
              + " се счупиха - мълчанието НЕ е доказан празен ден.")
        kod = 2
    else:
        print("Нула публикации, но всеки източник беше питан и отговори здраво: "
              + str(vzeti) + " взети, " + str(int(preseti or 0))
              + " минали филтрите"
              + ((", празни днес: " + ", ".join(prazni)) if prazni else "")
              + ". Днес наистина няма какво да се каже - това е"
              " нормално и обяснено, не провал.")
    if kod and MEK:
        print("(мек режим MATCHES_MEK=1: провалът е обявен, рънът остава зелен.)")
        varnat = 0
    else:
        varnat = kod
    # Кутията се пише ВИНАГИ и накрая — тук вече всичко е преброено и
    # присъдено. И двата кода влизат вътре, за да не скрие мекият режим
    # истинския провал от човека, който гледа файла отвън.
    zapishi_sastoyanie(kod, varnat, publikuvani, preseti, gledani, vzeti)
    return varnat


def _broiachi_na_predictor(P):
    """(заявки, счупени) от предсказателя. Липсват ли - (None, None), а това
    се вписва като гръмване: неизмеримото не бива да минава за празен ден."""
    try:
        return int(P._http_used[0]), int(P._http_fail[0])
    except Exception:                            # noqa: BLE001
        return None, None


# ---------- ДАННИ ----------
# Собствените заявки на този файл (TheSportsDB / football-data). Броят се тук,
# защото ESPN върви през predictor и има свои броячи.
MREZHA = {"zaqvki": 0, "provali": 0}


def fetch_json(url, timeout=20, headers=None):
    # ESPN пуска само непреправени клиенти. Измерено на 11.08.2026: подпис
    # „GreenPicksBot/1.0" -> 403 Forbidden; без подпис -> 200. Същият дефект
    # свали пет спорта в predictor.py и отсъждането в scorer.py.
    hd = ({"Accept": "application/json"} if "espn.com" in url
          else {"User-Agent": "GreenPicksBot/1.0"})
    if headers:
        hd.update(headers)
    if "thesportsdb.com" in url:
        time.sleep(2.1)    # free ключът е ~30 заявки/мин — дишаме
    req = urllib.request.Request(url, headers=hd)
    # Броим ПОСЯГАНЕТО, не успеха: точно разликата между посегнахме и не
    # посегнахме отличава празен ден от мълчащ източник.
    MREZHA["zaqvki"] += 1
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:                            # noqa: BLE001
        MREZHA["provali"] += 1
        raise


def league_weight(bucket, league):
    """0 = не е сериозен турнир -> изобщо не влиза."""
    lg = (league or "").strip()
    if not lg:
        return 0
    low = lg.lower()
    for bad in BLOCK_WORDS:
        if bad in low:
            return 0
    if lg in LEAGUE_WEIGHT:
        return LEAGUE_WEIGHT[lg]
    for frag, w in TOP_LEAGUES.get(bucket, []):
        if frag in low:
            return w
    return 0


def fmt_time_sdb(e):
    """UTC час от TheSportsDB -> български час."""
    t = (e.get("strTime") or "")[:5]
    d = (e.get("dateEvent") or "")[:10]
    if not t or t == "00:00":
        return ""
    try:
        return datetime.fromisoformat(f"{d}T{t}:00+00:00").astimezone(SOFIA).strftime("%H:%M")
    except ValueError:
        return t


def iso_to_sofia(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00")).astimezone(SOFIA).strftime("%H:%M")
    except ValueError:
        return ""


def get_todays_events(sport):
    d = today_str()
    try:
        data = fetch_json(f"{API}/eventsday.php?d={d}&s={urllib.parse.quote(sport)}")
        evs = data.get("events") or []
        # отложени/прекратени НЕ влизат в списъка
        return [e for e in evs
                if (e.get("strStatus") or "").lower() not in ("postponed", "cancelled", "canceled")
                and (e.get("strPostponed") or "").lower() != "yes"]
    except Exception as e:
        print(f"eventsday {sport}: {str(e)[:90]}")
        return []


def get_last_events(team_id):
    """Последните изиграни мачове на отбор (форма)."""
    try:
        data = fetch_json(f"{API}/eventslast.php?id={team_id}")
        return data.get("results") or []
    except Exception as e:
        print(f"eventslast {team_id}: {str(e)[:90]}")
        return []


def get_h2h(home, away):
    """Историята помежду им: searchevents по Home_vs_Away (и обратно)."""
    out = []
    for a, b in [(home, away), (away, home)]:
        q = urllib.parse.quote(f"{a}_vs_{b}")
        try:
            data = fetch_json(f"{API}/searchevents.php?e={q}")
            out += data.get("event") or []
        except Exception as e:
            print(f"h2h {a}/{b}: {str(e)[:90]}")
    played = [e for e in out if e.get("intHomeScore") not in (None, "")]
    played.sort(key=lambda e: e.get("dateEvent") or "", reverse=True)
    return played[:5]


def sportsdb_fixtures(bucket):
    """Чистите срещи за един спорт от TheSportsDB, вече прецедени по турнир."""
    cfg = SPORTS[bucket]
    rows = []
    _z0, _p0 = MREZHA["zaqvki"], MREZHA["provali"]
    _surovi = get_todays_events(cfg["api"])
    # ВЗЕТИ е суровото число ПРЕДИ филтъра по турнир. Филтърът е наш избор,
    # а не мълчание на извора - двете не бива да се броят на едно място.
    vpishi_izvor(bucket, vzeti=len(_surovi),
                 zaqvki=MREZHA["zaqvki"] - _z0,
                 provali=MREZHA["provali"] - _p0)
    for e in _surovi:
        w = league_weight(bucket, e.get("strLeague"))
        if w <= 0:
            continue
        rows.append({
            "bucket": bucket, "emoji": cfg["emoji"], "prio": cfg["prio"],
            "home": e.get("strHomeTeam") or "", "away": e.get("strAwayTeam") or "",
            "event": e.get("strEvent") or "", "league": e.get("strLeague") or "",
            "weight": w, "time": fmt_time_sdb(e), "src": "sdb",
            "fd_id": None, "home_id": e.get("idHomeTeam"), "away_id": e.get("idAwayTeam"),
        })
    return rows


# ---------- 🥊 БОЙНИ СПОРТОВЕ (UFC / MMA) ----------
# Логиката НЕ се преписва тук. predictor.py вече дърпа ESPN (без ключ):
#   https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard
#   https://site.api.espn.com/apis/site/v2/sports/mma/pfl/scoreboard
# и я поддържа на едно място (mma_fixtures). Ние само превеждаме реда му
# на езика на Анализатора и го пращаме в стая 328.
def combat_fixtures():
    """Предстоящите боеве от ESPN през predictor.mma_fixtures.

    Вносът е ВЪТРЕ във функцията нарочно: predictor.py на свой ред внася
    matches_bot, а внос на върха би завъртял кръг при зареждане."""
    try:
        import predictor as P
    except Exception as e:                       # noqa: BLE001
        print("бойни спортове: predictor.py не се зареди (" + str(e)[:90]
              + ") — стаята мълчи.")
        vpishi_izvor("combat", grimna="predictor.py не се зареди: " + str(e)[:60])
        return []

    now = datetime.now(SOFIA)
    old_window = getattr(P, "MMA_DAYS_AHEAD", COMBAT_DAYS)
    z0, f0 = _broiachi_na_predictor(P)
    gr = "" if z0 is not None else "броячите на заявки в predictor липсват"
    try:
        P.MMA_DAYS_AHEAD = COMBAT_DAYS
        raw = P.mma_fixtures(now) or []
    except Exception as e:                       # noqa: BLE001
        print("бойни спортове: ESPN мълчи (" + str(e)[:90] + ").")
        vpishi_izvor("combat", grimna="mma_fixtures: " + str(e)[:70])
        return []
    finally:
        P.MMA_DAYS_AHEAD = old_window

    rows = []
    for r in raw:
        when = r.get("when")
        local = when.astimezone(SOFIA) if when is not None else None
        rows.append({
            "bucket": "combat", "emoji": "🥊", "prio": SPORTS["combat"]["prio"],
            "home": r.get("home") or "", "away": r.get("away") or "",
            "event": "", "league": r.get("league") or "",
            "weight": to_int(r.get("weight"), 1),
            "time": local.strftime("%H:%M") if local else "",
            "date": local.strftime("%d.%m") if local else "",
            "sort": local.strftime("%Y-%m-%d %H:%M") if local else "9999",
            "src": "mma", "fd_id": None,
            "home_id": r.get("home_id"), "away_id": r.get("away_id"),
        })
    z1, f1 = _broiachi_na_predictor(P)
    vpishi_izvor("combat", vzeti=len(rows),
                 zaqvki=(z1 - z0) if (z0 is not None and z1 is not None) else 0,
                 provali=(f1 - f0) if (f0 is not None and f1 is not None) else 0,
                 grimna=gr)
    _p, _zashto = prisada(IZVORI.get("combat"))
    print("  combat: " + str(len(rows)) + " боя за " + str(COMBAT_DAYS)
          + " дни напред. [" + _p + ": " + _zashto + "]")
    return rows


# ---------- 📡 СРЕЩИТЕ ОТ ESPN (за всички спортове, не само бойните) ----------
# ЗАЩО СЪЩЕСТВУВА
# Стаите Футбол / Баскетбол / Тенис на маса / Волейбол се пълнеха от
# TheSportsDB. С безплатния ключ той връща ШЕПА записи — същият глад, заради
# който предсказателят дълго мълчеше. Междувременно predictor.py вече дърпа
# ESPN, FIVB и WTT без ключ и ги поддържа на едно място.
#
# Затова тук НЕ се преписва никаква логика: викаме готовите функции на
# предсказателя и само превеждаме реда на езика на Анализатора — точно както
# combat_fixtures прави от самото начало за бойните спортове.
#
# ДНИ НАПРЕД: с MATCHES_DAYS_AHEAD стаята може да се напълни с програмата за
# няколко дни наведнъж (полезно при първо пускане, за да не е празна).
MATCHES_DAYS = max(1, min(10, int((os.environ.get("MATCHES_DAYS_AHEAD") or "1").strip())))

# bucket -> (име на функцията в predictor, вид на датата)
#   "ymd"  = 20260729   ·  "dash" = 2026-07-29
ESPN_SOURCES = {
    "football":    ("football_fixtures", "ymd"),
    "basketball":  ("basketball_fixtures", "ymd"),
    "volleyball":  ("vol_fixtures", "dash"),
    "tabletennis": ("tt_fixtures", "dash"),
}


def espn_rows(bucket):
    """Срещите за един спорт от предсказателя, за MATCHES_DAYS дни напред."""
    if bucket not in ESPN_SOURCES:
        return []
    try:
        import predictor as P
    except Exception as e:                       # noqa: BLE001
        print("  " + bucket + ": predictor.py не се зареди (" + str(e)[:80] + ")")
        vpishi_izvor(bucket, grimna="predictor.py не се зареди: " + str(e)[:60])
        return []

    fname, kind = ESPN_SOURCES[bucket]
    fn = getattr(P, fname, None)
    if fn is None:
        print("  " + bucket + ": " + fname + " липсва в predictor.py")
        vpishi_izvor(bucket, grimna=fname + " липсва в predictor.py")
        return []
    z0, f0 = _broiachi_na_predictor(P)
    gr = "" if z0 is not None else "броячите на заявки в predictor липсват"

    now = datetime.now(SOFIA)
    seen = set()
    rows = []
    for d in range(MATCHES_DAYS):
        day = now + timedelta(days=d)
        stamp = day.strftime("%Y-%m-%d") if kind == "dash" else day.strftime("%Y%m%d")
        try:
            raw = fn(now, stamp) or []
        except Exception as e:                   # noqa: BLE001
            print("  " + bucket + " " + stamp + ": източникът мълчи (" + str(e)[:70] + ")")
            gr = gr or (stamp + ": " + str(e)[:70])
            continue
        for r in raw:
            when = r.get("when")
            local = when.astimezone(SOFIA) if when is not None else None
            home = r.get("home") or ""
            away = r.get("away") or ""
            key = (home.lower(), away.lower(),
                   local.strftime("%Y-%m-%d") if local else str(d))
            if key in seen:
                continue                          # един мач, видян в два дни
            seen.add(key)
            cfg = SPORTS.get(bucket) or {}
            rows.append({
                "bucket": bucket, "emoji": cfg.get("emoji", ""),
                "prio": cfg.get("prio", 0),
                "home": home, "away": away, "event": "",
                "league": r.get("league") or "",
                "weight": to_int(r.get("weight"), 1),
                "time": local.strftime("%H:%M") if local else "",
                "date": local.strftime("%d.%m") if local else "",
                "sort": local.strftime("%Y-%m-%d %H:%M") if local else "9999",
                "src": "espn", "fd_id": None,
                "home_id": r.get("home_id"), "away_id": r.get("away_id"),
                # 🔴 РЕКОРДЪТ ОТ ESPN (11.08.2026). Дотук този бот питаше САМО
                # TheSportsDB за история и форма — а безплатният ключ вече не
                # дава нищо извън футбола. Резултатът: „нямаме изиграни мачове"
                # за всичките девет кандидата, всеки ден. А ESPN връща
                # records=[total 20-12, home 11-6, road 9-6] в СЪЩИЯ отговор,
                # от който вече взимаме срещата.
                "rec_h": (r.get("extra") or {}).get("rec_h") or "",
                "rec_a": (r.get("extra") or {}).get("rec_a") or "",
                "rec_h_home": (r.get("extra") or {}).get("rec_h_home") or "",
                "rec_a_road": (r.get("extra") or {}).get("rec_a_road") or "",
            })
    z1, f1 = _broiachi_na_predictor(P)
    vpishi_izvor(bucket, vzeti=len(rows),
                 zaqvki=(z1 - z0) if (z0 is not None and z1 is not None) else 0,
                 provali=(f1 - f0) if (f0 is not None and f1 is not None) else 0,
                 grimna=gr)
    _p, _zashto = prisada(IZVORI.get(bucket))
    # 🔴 РЕДЪТ В ДНЕВНИКА ВЕЧЕ РАЗЛИЧАВА ДВЕТЕ НУЛИ. Дотук и празният ден, и
    # счупеният източник печатаха една и съща дума по дума фраза.
    print("  " + bucket + ": " + str(len(rows)) + " срещи от ESPN за "
          + str(MATCHES_DAYS) + " дни. [" + _p + ": " + _zashto + "]")
    return rows


# ---------- football-data.org (основен двигател за футбола) ----------
def fd_get(path):
    time.sleep(6.5)   # free tier: 10 заявки/мин — дишаме спокойно
    return fetch_json(FD_API + path, headers={"X-Auth-Token": FOOTBALL_DATA_KEY})


def fd_fixtures():
    """Днешните футболни срещи от топ състезанията. Празен списък = падаме към TheSportsDB."""
    d = today_str()
    data = fd_get(f"/matches?dateFrom={d}&dateTo={d}")
    rows = []
    for m in (data.get("matches") or []):
        # отложен/прекратен мач не е среща за днес
        if m.get("status") not in ("TIMED", "SCHEDULED"):
            continue
        comp = m.get("competition") or {}
        w = FD_COMP_WEIGHT.get(comp.get("code"), 0)
        if w <= 0:
            continue
        rows.append({
            "bucket": "football", "emoji": "⚽", "prio": SPORTS["football"]["prio"],
            "home": (m.get("homeTeam") or {}).get("name") or "",
            "away": (m.get("awayTeam") or {}).get("name") or "",
            "event": "", "league": comp.get("name") or "",
            "weight": w, "time": iso_to_sofia(m.get("utcDate")), "src": "fd",
            "fd_id": m.get("id"),
            "home_id": (m.get("homeTeam") or {}).get("id"),
            "away_id": (m.get("awayTeam") or {}).get("id"),
        })
    return rows


def fd_h2h(match_id):
    try:
        data = fd_get(f"/matches/{match_id}/head2head?limit=10")
        return data.get("aggregates") or {}, data.get("matches") or []
    except Exception as e:
        print("fd_h2h:", str(e)[:90])
        return {}, []


def fd_letters(ms, team_id):
    """W/L/D букви от football-data мачове (ново->старо).
    Мач без резултат (fullTime с None — бъдещ/прекъснат) се прескача, не крашва."""
    s = ""
    for m in ms:
        ft = (m.get("score") or {}).get("fullTime") or {}
        hg, ag = ft.get("home"), ft.get("away")
        if hg is None or ag is None:
            continue
        is_home = (m.get("homeTeam") or {}).get("id") == team_id
        mine, theirs = (hg, ag) if is_home else (ag, hg)
        s += "W" if mine > theirs else ("L" if mine < theirs else "D")
    return s or "?"


def fd_form(team_id):
    try:
        data = fd_get(f"/teams/{team_id}/matches?status=FINISHED")
        # API-то връща старо->ново; ние искаме ПОСЛЕДНИТЕ 5 (ново->старо)
        ms = sorted(data.get("matches") or [],
                    key=lambda m: m.get("utcDate") or "", reverse=True)[:5]
        return fd_letters(ms, team_id)
    except Exception as e:
        print("fd_form:", str(e)[:90])
        return "?"


# ---------- СМЯТАНЕ ----------
def form_string(team_name, events):
    """WWDLW от гледна точка на отбора (най-новото първо)."""
    s = ""
    for e in events[:5]:
        try:
            hs, as_ = int(e["intHomeScore"]), int(e["intAwayScore"])
        except (TypeError, ValueError, KeyError):
            continue
        is_home = e.get("strHomeTeam") == team_name
        mine, theirs = (hs, as_) if is_home else (as_, hs)
        s += "W" if mine > theirs else ("L" if mine < theirs else "D")
    return s or "?"


def h2h_summary(home, away, h2h):
    hw = aw = dr = 0
    for e in h2h:
        try:
            hs, as_ = int(e["intHomeScore"]), int(e["intAwayScore"])
        except (TypeError, ValueError, KeyError):
            continue
        winner = e.get("strHomeTeam") if hs > as_ else (e.get("strAwayTeam") if as_ > hs else None)
        if winner == home:
            hw += 1
        elif winner == away:
            aw += 1
        else:
            dr += 1
    return hw, dr, aw


def deep_stats(fx):
    """H2H + форма за една среща, независимо от двигателя.
    Връща речник с еднакви полета за двата източника."""
    st = {"hw": 0, "dr": 0, "aw": 0, "tot": 0, "last": "", "hf": "?", "af": "?", "goals": []}
    home, away = fx["home"], fx["away"]
    if not home or not away:
        return st

    if fx["src"] == "fd" and fx.get("fd_id"):
        agg, ms = fd_h2h(fx["fd_id"])
        ha = agg.get("homeTeam") or {}
        aa = agg.get("awayTeam") or {}
        st["hw"], st["aw"] = to_int(ha.get("wins")), to_int(aa.get("wins"))
        st["dr"] = to_int(ha.get("draws"))
        st["tot"] = to_int(agg.get("numberOfMatches"), st["hw"] + st["dr"] + st["aw"])
        for m in ms[:5]:
            ft = (m.get("score") or {}).get("fullTime") or {}
            hg, ag = ft.get("home"), ft.get("away")
            if hg is None or ag is None:
                continue
            st["goals"].append(to_int(hg) + to_int(ag))
        for last in ms[:1]:
            ft = (last.get("score") or {}).get("fullTime") or {}
            if ft.get("home") is None or ft.get("away") is None:
                continue
            lh = (last.get("homeTeam") or {}).get("shortName") or (last.get("homeTeam") or {}).get("name")
            la = (last.get("awayTeam") or {}).get("shortName") or (last.get("awayTeam") or {}).get("name")
            st["last"] = (f"{esc(lh)} {to_int(ft.get('home'))}:{to_int(ft.get('away'))} {esc(la)}"
                          f" ({(last.get('utcDate') or '')[:10]})")
        if fx.get("home_id"):
            st["hf"] = fd_form(fx["home_id"])
        if fx.get("away_id"):
            st["af"] = fd_form(fx["away_id"])
        return st

    h2h = get_h2h(home, away)
    if h2h:
        st["hw"], st["dr"], st["aw"] = h2h_summary(home, away, h2h)
        st["tot"] = len(h2h)
        for e in h2h:
            try:
                st["goals"].append(int(e["intHomeScore"]) + int(e["intAwayScore"]))
            except (TypeError, ValueError, KeyError):
                pass
        last = h2h[0]
        st["last"] = (f"{esc(last.get('strHomeTeam'))} {last.get('intHomeScore')}:"
                      f"{last.get('intAwayScore')} {esc(last.get('strAwayTeam'))}"
                      f" ({(last.get('dateEvent') or '')[:10]})")
    if fx.get("home_id"):
        st["hf"] = form_string(home, get_last_events(fx["home_id"]))
    if fx.get("away_id"):
        st["af"] = form_string(away, get_last_events(fx["away_id"]))

    # 🔴 РЕЗЕРВА ОТ ESPN. Ако TheSportsDB не е дал нищо (а за всичко извън
    # футбола вече не дава), ползваме рекорда „20-12", който ESPN връща в
    # същия отговор със срещата. Той не е форма от последните мачове, но е
    # ИЗМЕРЕН баланс победи/загуби — и е безкрайно повече от нищо.
    st["rec_h"] = str(fx.get("rec_h") or "")
    st["rec_a"] = str(fx.get("rec_a") or "")
    st["rec_h_home"] = str(fx.get("rec_h_home") or "")
    st["rec_a_road"] = str(fx.get("rec_a_road") or "")
    return st


def rekord_dvoyka(s):
    """„20-12" -> (20, 12). Празно или чудато -> None."""
    parts = str(s or "").replace("–", "-").split("-")
    if len(parts) < 2:
        return None
    try:
        w, l = int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None
    if w < 0 or l < 0 or (w + l) == 0:
        return None
    return (w, l)


def markers(home, away, st):
    """🎯 ОСТРИТЕ СТРЕЛКИ — факти от данните, не прогнози."""
    out = []
    tot = st["tot"]
    if tot >= 3:
        if st["hw"] >= tot - 1 and st["hw"] > st["aw"]:
            out.append(f"👑 {esc(home)} доминира помежду им: {st['hw']} от {tot}")
        elif st["aw"] >= tot - 1 and st["aw"] > st["hw"]:
            out.append(f"👑 {esc(away)} доминира помежду им: {st['aw']} от {tot}")
    g = st["goals"]
    if len(g) >= 3 and sum(g) / len(g) >= 3.0:
        avg = sum(g) / len(g)
        out.append(f"🧨 Резултатни сблъсъци: средно {avg:.1f} точки/гола на мач")
    for name, f in ((home, st["hf"]), (away, st["af"])):
        if f == "?" or len(f) < 3:
            continue
        if set(f[:3]) == {"W"}:
            streak = len(f) - len(f.lstrip("W"))
            out.append(f"🔥 {esc(name)} лети: {streak} поредни победи")
        elif "L" not in f:
            out.append(f"🛡 {esc(name)} без загуба в последните {len(f)}")
        elif set(f[:3]) == {"L"}:
            out.append(f"🥶 {esc(name)} в криза: 3 поредни загуби")
    return out


def numbers_say(home, away, st):
    """Какво казват числата. ВИНАГИ дава страна и процент.

    РЕШЕНИЕ НА СОБСТВЕНИКА (29.07.2026), взето два пъти и ясно:
    „Това е спортен канал за прогнози. Пишеш каквото може."
    Затова тук вече НЯМА отказ. Дори при празна извадка излиза страна —
    при нула данни това е домакинът, защото домакинското предимство е
    единственото, което знаем със сигурност.

    Честността не изчезва, а се мести в ЧИСЛОТО: при тънка извадка процентът
    е близо до 50 и до него пише на колко мача стъпва. Читателят вижда и
    двете и си преценява сам.
    """
    edge = 0.0
    n = 0
    tot = st["tot"]
    if tot >= 2:
        edge += 0.55 * (st["hw"] - st["aw"]) / tot
        n += tot
    hf, af = st["hf"], st["af"]
    if hf != "?" and af != "?" and len(hf) >= 3 and len(af) >= 3:
        h_rate = (hf.count("W") - hf.count("L")) / len(hf)
        a_rate = (af.count("W") - af.count("L")) / len(af)
        edge += 0.45 * (h_rate - a_rate) / 2.0
        n += len(hf) + len(af)

    # 🔴 ИЗМИСЛЕНОТО ЧИСЛО СИ ОТИДЕ (11.08.2026).
    #
    # Тук стоеше: „лек превес за X — около 54% срещу 46%. База: домакинско
    # предимство". Числото 54 не идва от нищо: в целия проект няма ред, който
    # да е мерил домакинско предимство и да е получил 0.54. Беше кръгло число,
    # написано с увереността на измерено.
    #
    # По-лошо: три реда по-долу СЪЩОТО съобщение пише „при малка извадка
    # прогнозата е несигурна" — тоест картата първо дава процент върху НУЛА
    # мача, после сама си казва да не ѝ вярваш.
    #
    # Този файл е ПРЕГЛЕД, не прогноза (виж заглавието „🔎 ПРЕГЛЕД НА ДЕНЯ").
    # Прогнозите ги дава predictor.py, който при празна извадка си има цяла
    # резервна стълба и казва на какво стъпва. Затова тук се казва истината:
    # нямаме числа за тази среща.
    # 🔴 РЕКОРДЪТ ОТ ESPN (11.08.2026). Дотук при празен TheSportsDB тук се
    # печаташе „нямаме изиграни мачове" — и това беше случаят за ВСИЧКИТЕ
    # девет кандидата, всеки ден. А балансът победи/загуби е в същия отговор.
    rh = rekord_dvoyka(st.get("rec_h"))
    ra = rekord_dvoyka(st.get("rec_a"))
    redove_rek = []
    if rh and ra:
        ph = rh[0] / float(rh[0] + rh[1])
        pa = ra[0] / float(ra[0] + ra[1])
        edge += 0.55 * (ph - pa)
        n += (rh[0] + rh[1]) + (ra[0] + ra[1])
        dom = st.get("rec_h_home")
        gost = st.get("rec_a_road")
        redove_rek = ["📊 Сезонът дотук: <b>" + str(rh[0]) + "-" + str(rh[1])
                      + "</b> срещу <b>" + str(ra[0]) + "-" + str(ra[1]) + "</b>"
                      + (" · у дома " + esc(dom) if dom else "")
                      + (" · на гости " + esc(gost) if gost else "")]

    if n < 1:
        return ["🎲 Числата: за тази среща <b>нямаме изиграни мачове</b> в"
                " източника — няма на какво да стъпи число.",
                "   Прогнозата, ако има такава, излиза в 🤖 БОТА ПРЕДРИЧА."]

    if abs(edge) < 0.02:
        edge = 0.02          # пълно равенство не е отговор — накланяме към домакина

    # Колкото по-малка е извадката, толкова по-близо до 50 е числото.
    doverie = min(1.0, n / 12.0)
    p = 50.0 + min(15.0, abs(edge) * 30.0) * (0.4 + 0.6 * doverie)
    _rek = redove_rek
    # Под 51 не слизаме: „превес за Х — 50% срещу 50%" е изречение, което
    # само по себе си се опровергава. Щом сме посочили страна, числото трябва
    # поне да я подкрепя.
    p = max(51.0, p)
    side = home if edge > 0 else away
    baza = ("База: " + str(n) + " мача (H2H, форма и сезонен баланс)." if n >= 4
            else "База: само " + str(n) + " мача — числото е предпазливо.")
    return (_rek
            + [f"🎲 Числата: превес за <b>{esc(side)}</b> — около {p:.0f}% срещу {100 - p:.0f}%.",
               "   " + baza])


# ---------- 📰 КРЪСТОСАН ФЛАГ С НОВИНИТЕ (само в стая 27) ----------
def load_recent_news_titles():
    """Заглавия от последното пускане на Новинаря — само за 📰 флаг в анализа."""
    if os.path.exists("last_news_titles.json"):
        try:
            with open("last_news_titles.json", encoding="utf-8-sig") as f:
                t = json.load(f)
            return t if isinstance(t, list) else []
        except Exception:
            pass
    return []


GENERIC_WORDS = {"city", "united", "real", "club", "town", "sport", "sporting", "athletic", "olympic"}


def word_start_hit(word, text):
    """Дали думата се среща в началото на дума (без regex, без обратни наклонени)."""
    i = text.find(word)
    while i != -1:
        if i == 0 or not (text[i - 1].isalpha() or text[i - 1].isdigit()):
            return True
        i = text.find(word, i + 1)
    return False


def news_flag(team, titles):
    t = (team or "").lower()
    words = [w for w in t.split() if len(w) >= 5 and w not in GENERIC_WORDS]
    if not words:
        return False
    for title in titles:
        tl = str(title).lower()
        if any(word_start_hit(w, tl) for w in words):
            return True
    return False


# ---------- КАРТИ ----------
def fixture_line(fx):
    t = fx["time"] or "--:--"
    # Боевете не са „днес" — датата е част от реда, иначе часът лъже.
    if fx.get("date"):
        t = fx["date"] + " · " + t
    if fx["home"] and fx["away"]:
        mid = f"<b>{esc(fx['home'])}</b> 🆚 <b>{esc(fx['away'])}</b>"
    else:
        mid = f"<b>{esc(fx['event'] or 'среща')}</b>"
    line = f"{fx['emoji']} {t} · {mid}"
    if fx["league"]:
        line += NL + f"     <i>{esc(fx['league'])}</i>"
    return line


def room_card(bucket, rows, now):
    cfg = SPORTS[bucket]
    what = cfg.get("head") or "срещите днес"
    only = cfg.get("only") or "срещите по направление"
    head = f"{cfg['emoji']} <b>{cfg['title']} · {what}</b> · {date_bg(now)}"
    body = NL.join(fixture_line(fx) for fx in rows)
    tail = (f"📌 В тази стая влизат само {only} — нищо друго." + NL
            + f"🧠 Анализът на бота е в {Q1}БОТА ПРЕДРИЧА{Q2}." + NL
            + f"🎯 Фишовете на човека-типстер са в {Q1}Фишове на деня{Q2}." + NL2
            + "⚠️ подредба от статистика, не гаранция" + NL
            + "🟢 THE GREEN ROOM")
    return head + NL2 + body + NL2 + tail


def predict_card(picks, now, news_titles):
    # 🔴 ЗАГЛАВИЕТО СЕ СМЕНИ (11.08.2026). Стоеше „🧠 БОТА ПРЕДРИЧА" — точно
    # заглавието на КАРТИТЕ на predictor.py, който пише в същата стая 27 осем
    # пъти на ден. Две различни съобщения с едно име, едното с прогноза и
    # процент, другото само с история и форма. Читателят чака избор, а получава
    # преглед — и решава, че ботът се обърква. Този тук НЕ дава избор, затова
    # вече си казва името: преглед, не прогноза.
    parts = [f"🔎 <b>ПРЕГЛЕД НА ДЕНЯ</b> · {date_bg(now)}",
             "<i>числата преди мачовете · прогнозите идват отделно</i>", ""]
    for i, fx in enumerate(picks):
        head = "🔥 <b>СБЛЪСЪКЪТ НА ДЕНЯ</b>" + NL if i == 0 else ""
        head += f"{fx['emoji']} <b>{esc(fx['home'])}</b> 🆚 <b>{esc(fx['away'])}</b>"
        if fx["time"]:
            head += f" · {fx['time']} ч."
        if fx["league"]:
            head += f" · {esc(fx['league'])}"
        parts.append(head)

        st = fx["stats"]
        if st["tot"]:
            parts.append(f"⚔️ Последни {st['tot']}: {esc(fx['home'])} {st['hw']} · "
                         f"Х {st['dr']} · {esc(fx['away'])} {st['aw']}")
        if st["last"]:
            parts.append(f"   Последно: {st['last']}")
        if st["hf"] != "?" or st["af"] != "?":
            parts.append(f"📈 Форма: {esc(fx['home'])} <code>{st['hf']}</code> · "
                         f"{esc(fx['away'])} <code>{st['af']}</code>")
        for m in markers(fx["home"], fx["away"], st):
            parts.append(m)

        flags = [tm for tm in (fx["home"], fx["away"]) if tm and news_flag(tm, news_titles)]
        if flags:
            parts.append(f"📰 Свежа новина около: {esc(', '.join(flags))} — "
                         f"виж стая {Q1}Новини{Q2}.")

        # Прогноза ВИНАГИ. Тук стоеше „няма достатъчно история — не гадаем",
        # което оставяше срещата без нито едно число. Собственикът го отхвърли
        # ясно: каналът е за прогнози. numbers_say сега се справя и с празна
        # извадка — казва страната и колко данни стоят зад числото.
        parts += numbers_say(fx["home"], fx["away"], st)
        parts.append("")

    parts.append("Как се чете това: числата дават вероятност, не сигурност.")
    # 🔴 ПРЕПИСАНО 12.08.2026. Редът твърдеше „при малка извадка прогноза не
    # даваме" — а numbers_say точно над него ВИНАГИ дава страна и процент.
    # Пуснато с n=2: излиза „58% срещу 42% · База: само 2 мача". Тоест
    # едно и също съобщение се опровергаваше през три реда.
    parts.append("Малка извадка = предпазливо число — пише го под самото число.")
    # 🔴 МАХНАТО 11.08.2026. Редът обещаваше „пълните списъци със срещи в
    # стаите по спорт", а те са ИЗКЛЮЧЕНИ (MATCHES_ROOM_LISTS=0 по
    # подразбиране) — тоест сочеше към нещо, което го няма. Ако някой ден
    # списъците се върнат, редът се връща с тях.
    if ROOM_LISTS:
        parts.append("📅 Пълните списъци със срещи са в стаите по спорт.")
    parts.append("⚠️ прогноза от статистика, не гаранция")
    parts.append("🟢 THE GREEN ROOM")
    return NL.join(parts)


# ---------- ГЛАВНО ----------
def collect():
    """Всички днешни срещи, по кошници, вече прецедени и подредени."""
    # Тефтерът се чисти в началото на всяко събиране: стар запис от предишно
    # викане би превърнал днешния провал във вчерашно НАРЕД.
    IZVORI.clear()
    MREZHA["zaqvki"] = 0
    MREZHA["provali"] = 0
    buckets = {}

    # РЕДЪТ НА ИЗТОЧНИЦИТЕ (най-богатият пръв):
    #   1. ESPN / FIVB / WTT през predictor.py — без ключ, дълбоки данни
    #   2. football-data.org — само ако има ключ и само за футбола
    #   3. TheSportsDB — последна резерва; безплатният ключ дава шепа записи
    # Мереното на живо: ESPN дава десетки срещи на ден, TheSportsDB — единици.
    # Затова ESPN е пръв, а не обратното.
    for bucket in ("football", "tabletennis", "volleyball", "basketball"):
        rows = espn_rows(bucket)
        if rows:
            buckets[bucket] = rows
            continue

        if bucket == "football" and FOOTBALL_DATA_KEY:
            try:
                fd_rows = fd_fixtures()
            except Exception as e:               # noqa: BLE001
                print("football-data пропадна:", str(e)[:90])
                fd_rows = []
            if fd_rows:
                print("  футбол: " + str(len(fd_rows)) + " срещи от football-data.org")
                buckets[bucket] = fd_rows
                continue

        print("  " + bucket + ": ESPN мълчи — падам на TheSportsDB.")
        buckets[bucket] = sportsdb_fixtures(bucket)

    # 🥊 Бойните спортове идват от ESPN през predictor.mma_fixtures.
    buckets["combat"] = combat_fixtures()

    for bucket, rows in buckets.items():
        rows.sort(key=lambda fx: -fx["weight"])
        del rows[MAX_PER_ROOM:]
        # Боевете носят и дата („sort"); останалите спортове са само за днес.
        rows.sort(key=lambda fx: fx.get("sort") or fx["time"] or "99:99")
    return buckets


def main():
    if DRY_RUN and not BOT_TOKEN:
        print("СУХО ПУСКАНЕ — съобщенията се печатат, нищо не заминава.")
    elif not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)
    if os.environ.get("MATCHES_THREAD_ID"):
        print("Бележка: MATCHES_THREAD_ID е пенсиониран — срещите ходят по спортни стаи, "
              "анализът в стая 27. Стойността се игнорира.")

    now = datetime.now(SOFIA)
    buckets = collect()
    total = sum(len(v) for v in buckets.values())
    if not total:
        # 🔴 ТУК БЕШЕ ДЕФЕКТЪТ (ред 982-983 преди 01.09.2026). Един ред текст и
        # изход 0 за две различни неща: няма мачове ИЛИ API мълчи. Скобата в
        # самото изречение признаваше, че не знаем кое от двете е - и въпреки
        # това рънът светеше зелено. Сега присъдата се произнася от числата.
        return ravnosmetka(0, preseti=0)

    # 1) СПИСЪЦИТЕ СЪС СРЕЩИ СА СПРЕНИ (29.07.2026).
    # Собственикът беше пределно ясен: „Даваш срещите за деня или някви
    # тъпотии, а не БОТА ПРЕДРИЧА. Искам всичко прогнози, а не какво предстои
    # като някакви списъци."
    # Затова спортните стаи вече получават САМО прогнози — те идват от
    # predictor.py, който праща всяка карта и в стаята на своя спорт.
    # Тук нищо не се праща по стаите. Събирането остава, защото анализът в
    # стая 27 по-долу стъпва на същите срещи.
    # Ако някога програмата пак потрябва: MATCHES_ROOM_LISTS=1.
    sent_rooms = 0
    if ROOM_LISTS:
        for bucket in SPORT_ORDER:
            rows = buckets.get(bucket) or []
            if not rows:
                print(f"{bucket}: няма срещи от сериозни турнири — стаята мълчи.")
                continue
            if post_room(SPORTS[bucket]["thread"], room_card(bucket, rows, now)):
                sent_rooms += 1
                print(f"{bucket}: {len(rows)} срещи -> стая {SPORTS[bucket]['thread']}")
    else:
        print("Списъците със срещи са СПРЕНИ по решение на собственика.")
        print("Спортните стаи получават прогнози от predictor.py.")

    # 2) АНАЛИЗЪТ -> стая 27 „БОТА ПРЕДРИЧА". Разсъждението живее само тук.
    pool = []
    for bucket in SPORT_ORDER:
        # 🥊 Боевете НЕ влизат в тукашния анализ: H2H по имена и „форма" от
        # TheSportsDB нямат смисъл за ММА. Прогнозата за тях идва от
        # predictor.py (model_mma) и пак излиза в стая 27.
        if bucket == "combat":
            continue
        for fx in (buckets.get(bucket) or []):
            if fx["home"] and fx["away"]:
                pool.append(fx)
    pool.sort(key=lambda fx: -(fx["prio"] * 100 + fx["weight"]))

    # 🔴 СРЕЩА БЕЗ ЧИСЛА НЕ ВЛИЗА В ПРЕГЛЕДА (11.08.2026).
    #
    # Прочетох истинския пост, след като добавих сухо пускане. Заглавието
    # обещаваше „числата преди мачовете", а И ТРИТЕ избрани срещи казваха
    # „за тази среща нямаме изиграни мачове в източника". Тоест преглед на
    # деня без нито едно число — всеки ден, в стая 27.
    #
    # Изборът дотук се правеше по важност (prio и тежест), а данните се
    # питаха ЧАК СЛЕД това. Затова победителят често беше най-големият мач,
    # за който не знаем нищо. Сега пробваме надолу по списъка, докато не
    # съберем ANALYSIS_MAX срещи, за които наистина ИМА какво да се каже.
    # Таванът пази заявките: гледаме най-много 3 пъти повече кандидати.
    picks, gledani = [], 0
    for fx in pool:
        if len(picks) >= ANALYSIS_MAX or gledani >= ANALYSIS_MAX * 3:
            break
        gledani += 1
        fx["stats"] = deep_stats(fx)
        st = fx["stats"]
        ima = (to_int(st.get("tot")) >= 2
               or (st.get("hf") not in (None, "?", "") and len(str(st.get("hf"))) >= 3)
               or (st.get("af") not in (None, "?", "") and len(str(st.get("af"))) >= 3)
               # Сезонният баланс от ESPN е също числа — и за повечето спортове
               # е ЕДИНСТВЕНИТЕ, защото TheSportsDB вече мълчи извън футбола.
               or (rekord_dvoyka(st.get("rec_h")) and rekord_dvoyka(st.get("rec_a"))))
        if ima:
            picks.append(fx)
        else:
            print("   пропускам " + str(fx.get("home")) + " - " + str(fx.get("away"))
                  + ": няма изиграни мачове в източника")
    if not picks:
        # Мълчание, а не празен преглед. Стаята получава прогнозите си от
        # predictor.py — този файл няма какво да добави днес.
        print("Нито една среща с данни от " + str(gledani) + " гледани — стая "
              + str(PREDICT_THREAD) + " мълчи. Прегледът без числа е празен преглед.")
        return ravnosmetka(sent_rooms, preseti=len(pool), gledani=gledani)

    news_titles = load_recent_news_titles()
    if post_room(PREDICT_THREAD, predict_card(picks, now, news_titles)):
        sent_rooms += 1
        print(f"Анализ: {len(picks)} срещи -> стая {PREDICT_THREAD}")
    else:
        # Отказаното пращане беше НЕВИДИМО: сметката отдолу броеше само стаите
        # със списъци, а те са спрени - тоест провалът излизаше като нула.
        print("Анализът НЕ замина към стая " + str(PREDICT_THREAD) + ".")
    return ravnosmetka(sent_rooms, preseti=len(pool), gledani=gledani)


# ---------- SELFTEST (без мрежа, без реални пращания) ----------
def _sobstveniyat_izhoden_tekst():
    """Собственият сорс. Проверка, която ГО ЧЕТЕ, не може да бъде подведена от
    променлива, презаписана в паметта по време на теста."""
    with open(os.path.abspath(__file__), encoding="utf-8-sig") as f:
        return f.read()


def _insp_src_na_praga():
    t = _sobstveniyat_izhoden_tekst()
    i = t.find("MIN_VZETI = max(")
    return t[max(0, i - 200):i + 200]


def _insp_src_na_izhoda():
    # 🔴 rfind, НЕ find (01.09.2026). С find търсенето попадаше върху
    # СОБСТВЕНИЯ СИ литерал няколко реда по-горе, а не върху истинския блок
    # накрая на файла. Опашката тогава съдържаше и реда на самата проверка -
    # тоест проверката намираше СЕБЕ СИ и не можеше да падне никога.
    # Мутационният тест го хвана: развалих изхода и selftest остана зелен.
    t = _sobstveniyat_izhoden_tekst()
    i = t.rfind('if __name__ ==')
    return t[i:] if i >= 0 else ""


def selftest():
    results = []

    def check(name, ok):
        results.append((name, bool(ok)))
        print(("PASS " if ok else "FAIL ") + name)

    # 1) Форма с None резултат — прескача се, не крашва, буквите не се губят
    evs = [
        {"intHomeScore": None, "intAwayScore": 2, "strHomeTeam": "Алфа", "strAwayTeam": "Бета"},
        {"intHomeScore": "3", "intAwayScore": "1", "strHomeTeam": "Алфа", "strAwayTeam": "Бета"},
        {"intHomeScore": "0", "intAwayScore": "0", "strHomeTeam": "Гама", "strAwayTeam": "Алфа"},
    ]
    # ══════════════════════════════════════════════════════════════════
    #  🔴 ПРЕГЛЕД БЕЗ ЧИСЛА Е ПРАЗЕН ПРЕГЛЕД (11.08.2026)
    #  Добавих сухо пускане на този файл (беше единственият жив бот без
    #  такова) и прочетох истинския пост. Заглавието обещаваше „числата
    #  преди мачовете", а и ТРИТЕ избрани срещи казваха „нямаме изиграни
    #  мачове". Причината: питахме само TheSportsDB, чийто безплатен ключ
    #  вече не дава нищо извън футбола — а ESPN връща сезонния баланс
    #  в СЪЩИЯ отговор, от който взимаме и самата среща.
    # ══════════════════════════════════════════════════════════════════
    check("рекордът се чете", rekord_dvoyka("20-12") == (20, 12))
    check("тирето може да е дълго", rekord_dvoyka("20–12") == (20, 12))
    check("празният рекорд не гърми", rekord_dvoyka("") is None)
    check("боклук вместо рекорд не гърми", rekord_dvoyka("х-у") is None)
    check("нула мача не е рекорд", rekord_dvoyka("0-0") is None)
    _st_rek = {"tot": 0, "hw": 0, "aw": 0, "dr": 0, "hf": "?", "af": "?",
               "rec_h": "20-12", "rec_a": "12-22",
               "rec_h_home": "11-6", "rec_a_road": "5-14", "goals": []}
    _r = numbers_say("Алфа", "Бета", _st_rek)
    _txt = NL.join(_r)
    check("сезонният баланс излиза в картата", "Сезонът дотук" in _txt)
    check("балансът носи и двата рекорда", "20-12" in _txt and "12-22" in _txt)
    check("по-добрият рекорд води", "Алфа" in _txt)
    check("картата вече НЕ казва нямаме мачове", "нямаме изиграни" not in _txt)
    _prazen = {"tot": 0, "hw": 0, "aw": 0, "dr": 0, "hf": "?", "af": "?",
               "rec_h": "", "rec_a": "", "goals": []}
    check("без НИКАКВИ данни пак се казва честно",
          "нямаме изиграни" in NL.join(numbers_say("Алфа", "Бета", _prazen)))
    # Апострофът изтичаше като &#x27; и стоеше буквално в стаята.
    check("апострофът не изтича", esc("Girls' U17") == "Girls' U17")
    check("острите скоби пак се екранират", esc("<b>") == "&lt;b&gt;")
    check("форма прескача None", form_string("Алфа", evs) == "WD")
    check("форма само None дава ?", form_string("Алфа", [{"intHomeScore": None, "intAwayScore": None}]) == "?")
    check("h2h прескача None", h2h_summary("Алфа", "Бета", evs) == (1, 1, 0))

    ms = [
        {"utcDate": "2026-07-20T18:00:00Z", "score": {"fullTime": {"home": None, "away": None}},
         "homeTeam": {"id": 7}, "awayTeam": {"id": 8}},
        {"utcDate": "2026-07-15T18:00:00Z", "score": {"fullTime": {"home": 2, "away": 0}},
         "homeTeam": {"id": 7}, "awayTeam": {"id": 8}},
        {"utcDate": "2026-07-10T18:00:00Z", "score": {"fullTime": {"home": 1, "away": 3}},
         "homeTeam": {"id": 9}, "awayTeam": {"id": 7}},
    ]
    check("FD форма пази None", fd_letters(ms, 7) == "WW")
    ms2 = sorted(ms, key=lambda m: m.get("utcDate") or "", reverse=True)
    check("FD сортиране ново към старо", ms2[0]["utcDate"].startswith("2026-07-20"))

    # 2) Thread валидация — пазачите на стаите
    check("забранените не са в разрешените", not (FORBIDDEN_THREADS & ALLOWED_THREADS))
    sent = []
    real_send = poster.send_message

    def fake_send(chat_id, text, thread_id=None, preview=False):
        sent.append(str(thread_id))
        return True

    poster.send_message = fake_send
    try:
        check("стая 4 (фишове) отказана", post_room("4", "тест") is False)
        check("стая 26 (новини) отказана", post_room("26", "тест") is False)
        check("чужда стая отказана", post_room("999", "тест") is False)
        check("празен thread отказан", post_room("", "тест") is False)
        ALLOWED_THREADS.add("0x")
        check("нечислов thread отказан без краш", post_room("0x", "тест") is False)
        ALLOWED_THREADS.discard("0x")
        ok_pass = post_room(FOOTBALL_THREAD, "тест")
        check("разрешена стая минава", ok_pass is True and sent == [FOOTBALL_THREAD])
    finally:
        poster.send_message = real_send

    # 🔴 ПАЗАЧ СРЕЩУ ДРЕЙФА НА СТАИТЕ (18.08.2026). predictor знае девет стаи
    # по спорт, тук се знаеха пет — тенисът и бейзболът липсваха изцяло.
    # Списъкът се ЧЕТЕ от predictor.py, не се преписва: препис остарява тихо.
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "predictor.py"), encoding="utf-8-sig") as f:
            _ps = f.read()
        _i = _ps.find("SPORT_ROOM = {")
        _bl = _ps[_i:_ps.find("}", _i)] if _i >= 0 else ""
        # Закованите номера са в кода; новите стаи живеят в
        # rooms_state.json и се вливат в predictor по същия начин.
        # Сверяваме и двете — иначе проверката гледа половин истина.
        _nom = set(re.findall(r'or "(\d+)"', _bl)) | set(_stai_ot_sastoyanie().values())
        check("стаите на predictor се прочетоха", len(_nom) >= 5)
        _lip = sorted(_nom - ALLOWED_THREADS - FORBIDDEN_THREADS)
        check("всяка стая по спорт е позната тук", not _lip)
    except Exception as e:                                   # noqa: BLE001
        check("сверката със стаите на predictor мина", False)
        print("   (" + str(e)[:50] + ")")


    # 3) Часове: UTC -> Европа/София (лятото е UTC+3)
    check("SDB час в български", fmt_time_sdb({"strTime": "18:00:00", "dateEvent": "2026-07-28"}) == "21:00")
    check("FD час в български", iso_to_sofia("2026-07-28T18:00:00Z") == "21:00")
    check("clip реже дългото", len(clip("х" * 5000)) < 4096)

    # 4) Картите: стайна + прогнозна
    now = datetime.now(SOFIA)
    fx = {"bucket": "football", "emoji": "⚽", "prio": 10,
          "home": "Левски", "away": "Атлетик", "event": "", "league": "Тест лига",
          "weight": 5, "time": "21:00", "src": "sdb", "fd_id": None,
          "home_id": None, "away_id": None}
    card1 = room_card("football", [fx], now)
    check("стайна карта носи отборите", "Левски" in card1 and "Атлетик" in card1)
    fx2 = dict(fx)
    fx2["stats"] = {"hw": 3, "dr": 1, "aw": 1, "tot": 5, "last": "Левски 2:1 Атлетик (2026-01-01)",
                    "hf": "WWWLW", "af": "LLDWL", "goals": [3, 4, 2, 5, 1]}
    card2 = predict_card([fx2], now, ["Левски с нов треньор от днес"])
    check("прогнозата носи формата", "WWWLW" in card2)
    check("новина-флаг в анализа", "Свежа новина" in card2)
    check("фалшив новина-флаг мълчи",
          news_flag("Манчестър Сити", ["стадионът вдига капацитета си"]) is False
          and news_flag("Manchester City", ["stadium capacity increased"]) is False)

    # 5) Стрелките
    mk = markers("Левски", "Атлетик", fx2["stats"])
    check("стрелка за серия победи", any("поредни победи" in m for m in mk))
    st_shield = {"hw": 0, "dr": 0, "aw": 0, "tot": 0, "last": "", "hf": "WDWWD", "af": "?", "goals": []}
    mk2 = markers("Тим", "Друг", st_shield)
    check("стрелка без загуба", any("без загуба" in m for m in mk2))

    # 6) Числата + тон-пазач (железните правила)
    # ⚠️ ТЕЗИ ДВЕ ПРОВЕРКИ БЯХА ОБЪРНАТИ НА 29.07.2026.
    # Пазеха старото правило „малко данни = не гадаем" и „равностойно = без
    # прогноза". Собственикът го отхвърли ясно: каналът е за прогнози и
    # ботът пише каквото може. Сега пазят НОВОТО правило: винаги излиза
    # страна и процент, а честността е в числото и в базата под него.
    # 🔴 ОБЪРНАТИ ОТНОВО НА 11.08.2026 — и ето защо това НЕ е връщане назад.
    #
    # Решението на собственика от 29.07 („каналът е за прогнози, ботът пише
    # каквото може") важи за ПРЕДСКАЗАТЕЛЯ и там е спазено: predictor.py има
    # цяла резервна стълба и при празна история пак дава страна, като казва на
    # какво стъпва.
    #
    # ТОЗИ файл обаче не е предсказател. От 11.08 заглавието му е „🔎 ПРЕГЛЕД
    # НА ДЕНЯ" — той показва история и форма, не дава избор. А при нула изиграни
    # мача пишеше „около 54% срещу 46%" — число, което не идва от никакво
    # измерване, и три реда по-долу самото съобщение казваше „при малка извадка
    # прогнозата е несигурна". Един текст, който сам си противоречи.
    #
    # Затова: прегледът казва, че няма числа. Прогнозата си остава при
    # предсказателя.
    st_small = {"hw": 0, "dr": 0, "aw": 0, "tot": 0, "last": "", "hf": "?", "af": "?", "goals": []}
    ns_small = numbers_say("А", "Б", st_small)
    check("празната извадка е призната на глас",
          "нямаме изиграни мачове" in " ".join(ns_small))
    check("празната извадка НЕ измисля процент",
          not any(ch.isdigit() for ch in ns_small[0]))
    check("празната извадка сочи къде е прогнозата",
          "ПРЕДРИЧА" in " ".join(ns_small))
    st_even = {"hw": 2, "dr": 0, "aw": 2, "tot": 4, "last": "", "hf": "?", "af": "?", "goals": []}
    ns_even = numbers_say("А", "Б", st_even)
    check("равностойното ВСЕ ПАК дава страна", "превес за" in ns_even[0])
    check("равностойното не се разкрасява",
          any(str(x) + "%" in ns_even[0] for x in range(50, 56)))
    check("никъде не пише че не гадаем",
          "гадаем" not in (" ".join(ns_small) + " ".join(ns_even)).lower())
    # --- СПИСЪЦИТЕ СЪС СРЕЩИ СА СПРЕНИ. Пазач, за да не се върнат тихо.
    import inspect as _insp
    _main_src = _insp.getsource(main)
    check("списъците по стаи са зад изричен ключ",
          'MATCHES_ROOM_LISTS' in _main_src)
    check("по подразбиране стаите НЕ получават списък",
          os.environ.get("MATCHES_ROOM_LISTS", "0").strip() != "1")

    bad_words = ["18+", "залагай", "не е съвет", "коеф", "букмейк", "банка", "залог", "единица"]
    all_out = (card1 + " " + card2 + " " + " ".join(ns_small) + " " + " ".join(ns_even)).lower()
    check("тонът е чист", not any(b in all_out for b in bad_words))

    # ══════════════════════════════════════════════════════════════════
    #  🔢 ТРИТЕ ЧИСЛА И ПРИСЪДАТА ЗА ИЗТОЧНИКА (01.09.2026)
    #  Дотук нула публикации и нула взети срещи бяха ЕДНО И СЪЩО за бота:
    #  един ред текст и изход 0. Проверките отдолу пазят разликата.
    # ══════════════════════════════════════════════════════════════════
    import contextlib as _ctx
    import io as _io

    check("гръмнал източник е ПРОВАЛ",
          prisada({"vzeti": 0, "zaqvki": 3, "provali": 0, "grimna": "бум"})[0] == "ПРОВАЛ")
    check("нула заявки е ПРОВАЛ, не празен ден",
          prisada({"vzeti": 0, "zaqvki": 0, "provali": 0})[0] == "ПРОВАЛ")
    check("всички заявки счупени е ПРОВАЛ",
          prisada({"vzeti": 0, "zaqvki": 1, "provali": 1})[0] == "ПРОВАЛ")
    check("питан и празен е ПРАЗНО, не провал",
          prisada({"vzeti": 0, "zaqvki": 2, "provali": 0})[0] == "ПРАЗНО")
    check("дошли срещи е НАРЕД",
          prisada({"vzeti": 7, "zaqvki": 2, "provali": 0})[0] == "НАРЕД")
    # Живият извор бие всичко: 36 футболни срещи не бива да почервенеят,
    # защото една вътрешност на predictor се е преименувала.
    check("живият извор бие счупен брояч",
          prisada({"vzeti": 36, "zaqvki": 0, "provali": 4,
                   "grimna": "броячите липсват"})[0] == "НАРЕД")
    check("двете нули имат РАЗЛИЧНИ обяснения",
          prisada({"vzeti": 0, "zaqvki": 1, "provali": 1})[1]
          != prisada({"vzeti": 0, "zaqvki": 2, "provali": 0})[1])
    # Тефтерът СЪБИРА: един спорт минава през два двигателя.
    IZVORI.clear()
    vpishi_izvor("proba", vzeti=2, zaqvki=1)
    vpishi_izvor("proba", vzeti=3, zaqvki=2, provali=1)
    check("тефтерът събира двата опита",
          IZVORI["proba"] == {"vzeti": 5, "zaqvki": 3, "provali": 1, "grimna": ""})

    # ---- прагът е ключ с измерена стойност
    check("прагът е положително число", isinstance(MIN_VZETI, int) and MIN_VZETI > 0)
    check("прагът е под измерения най-слаб ден (24)", MIN_VZETI < 24)
    check("прагът се чете от ключ MATCHES_MIN_VZETI",
          "MATCHES_MIN_VZETI" in _insp_src_na_praga())

    # ---- посягането навън се брои (иначе нула заявки не значи нищо).
    # Адресът е с непознат вид - urllib гърми ПРЕДИ да отвори сокет.
    _z, _p = MREZHA["zaqvki"], MREZHA["provali"]
    try:
        fetch_json("bogus://nyama-takyv-adres")
    except Exception:                            # noqa: BLE001
        pass
    check("посягането навън се брои", MREZHA["zaqvki"] == _z + 1)
    check("счупената заявка се брои", MREZHA["provali"] == _p + 1)

    # ---- липсваща функция в predictor е ПРОВАЛ, не празен ден.
    # Истинският predictor НЕ се внася: подменяме го в sys.modules, за да
    # остане проверката без мрежа и без секунди.
    import types as _types
    _star_pred = sys.modules.get("predictor")
    try:
        sys.modules["predictor"] = _types.ModuleType("predictor")
        IZVORI.clear()
        with _ctx.redirect_stdout(_io.StringIO()):
            _r = espn_rows("football")
        # Записът трябва да СЪЩЕСТВУВА, не само да дава ПРОВАЛ: липсва ли
        # го, източникът изобщо не се появява в тефтера и мълчи невидимо.
        check("липсваща функция в predictor е ПРОВАЛ, не празен ден",
              _r == [] and "football" in IZVORI
              and prisada(IZVORI["football"])[0] == "ПРОВАЛ")
    finally:
        if _star_pred is None:
            sys.modules.pop("predictor", None)
        else:
            sys.modules["predictor"] = _star_pred
    IZVORI.clear()
    # Неизмеримото НЕ бива да минава за нула: липсват ли броячите, връщаме
    # сентинел, а не 0 - защото 0 заявки е твърдение, а не незнание.
    check("липсващите броячи се признават за неизмерими",
          _broiachi_na_predictor(_types.ModuleType("nishto")) == (None, None))

    # ---- събирането чисти вчерашния тефтер (иначе стар запис маскира провал)
    _es, _cf, _sd, _fd = espn_rows, combat_fixtures, sportsdb_fixtures, fd_fixtures
    try:
        globals()["espn_rows"] = lambda b: []
        globals()["combat_fixtures"] = lambda: []
        globals()["sportsdb_fixtures"] = lambda b: []
        globals()["fd_fixtures"] = lambda: []
        vpishi_izvor("stara_stoyka", vzeti=99, zaqvki=1)
        with _ctx.redirect_stdout(_io.StringIO()):
            collect()
        check("събирането чисти вчерашния тефтер", "stara_stoyka" not in IZVORI)
    finally:
        globals()["espn_rows"] = _es
        globals()["combat_fixtures"] = _cf
        globals()["sportsdb_fixtures"] = _sd
        globals()["fd_fixtures"] = _fd
    IZVORI.clear()

    # ---- равносметката: изходният код носи разликата
    _posleden = {}

    def _run_rav(zapisi, publikuvani, preseti=0):
        IZVORI.clear()
        for ime, z in zapisi.items():
            vpishi_izvor(ime, **z)
        _buf = _io.StringIO()
        # 🔴 Тефтерът вече се ЗАПИСВА на диск. Без това пренасочване
        # самопроверката би презаписвала ИСТИНСКИЯ matches_state.json —
        # тест, който мени производството, е по-лош от липсващ тест.
        import shutil as _sh
        import tempfile as _tf
        _star, _d = STATE_FILE, _tf.mkdtemp()
        globals()["STATE_FILE"] = os.path.join(_d, "matches_state.json")
        try:
            with _ctx.redirect_stdout(_buf):
                _kod = ravnosmetka(publikuvani, preseti=preseti)
            _zap = None
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, encoding="utf-8") as _f:
                    _zap = json.load(_f)
            _posleden["zapis"] = _zap
            _posleden["ostatak"] = sorted(x for x in os.listdir(_d)
                                          if x.endswith(".tmp"))
        finally:
            globals()["STATE_FILE"] = _star
            _sh.rmtree(_d, ignore_errors=True)
        return _kod, _buf.getvalue()

    _kod, _txt = _run_rav({}, 0)
    check("нула взети и нула публикации е ПРОВАЛ (изход != 0)", _kod != 0)
    check("провалът се обявява с думата ПРОВАЛ", "ПРОВАЛ" in _txt)
    _kod, _txt = _run_rav({"football": {"vzeti": 40, "zaqvki": 9},
                           "tabletennis": {"vzeti": 0, "zaqvki": 1, "provali": 1}}, 0)
    check("нула публикации при счупен източник е ПРОВАЛ", _kod != 0)
    _kod, _txt = _run_rav({"football": {"vzeti": 40, "zaqvki": 9},
                           "tabletennis": {"vzeti": 0, "zaqvki": 1, "provali": 1}}, 1)
    check("публикуваното при счупен източник е ЧАСТИЧНО, не провал",
          _kod == 0 and "ЧАСТИЧНО" in _txt)
    _kod, _txt = _run_rav({"football": {"vzeti": 40, "zaqvki": 9},
                           "combat": {"vzeti": 0, "zaqvki": 2}}, 0, preseti=12)
    check("нула публикации при жив и празен извор е НОРМАЛНО (изход 0)", _kod == 0)
    check("нормалната нула е ОБЯСНЕНА, не премълчана", "нормално и обяснено" in _txt)
    check("и трите числа се печатат",
          "ВЗЕТИ ОТ ИЗТОЧНИКА" in _txt and "МИНАЛИ ФИЛТРИТЕ" in _txt
          and "ПУБЛИКУВАНИ" in _txt)
    check("тефтерът показва всеки източник поименно",
          "football" in _txt and "combat" in _txt)
    _kod, _txt = _run_rav({"football": {"vzeti": 40, "zaqvki": 9}}, 2)
    check("публикувано е зелено", _kod == 0)
    # Мекият режим е ПЪТЯТ НАЗАД: обявява провала, но не боядисва рънa.
    _sm = MEK
    try:
        globals()["MEK"] = True
        _kod, _txt = _run_rav({}, 0)
        check("мекият режим обявява провала, но пуска зелено",
              _kod == 0 and "ПРОВАЛ" in _txt)
    finally:
        globals()["MEK"] = _sm
    IZVORI.clear()

    # ---- ЧЕРНАТА КУТИЯ: тефтерът в ХРАНИЛИЩЕТО, не само в дневника
    # 🔴 01.09.2026. Трите числа отиваха само в изхода на Actions — той иска
    # админски права и изчезва. Отвън се виждаше зелено или червено и нищо
    # друго, а matches_state.json изобщо НЕ СЪЩЕСТВУВАШЕ в хранилището.
    _kod, _txt = _run_rav({"football": {"vzeti": 40, "zaqvki": 9},
                           "tabletennis": {"vzeti": 0, "zaqvki": 1,
                                           "provali": 1,
                                           "grimna": "brotli липсва"}},
                          3, preseti=7)
    _z = _posleden.get("zapis")
    check("тефтерът се ЗАПИСВА на диск", isinstance(_z, dict))
    _z = _z if isinstance(_z, dict) else {}
    check("записът има версия", _z.get("v") == 1)
    check("записът има час", len(str(_z.get("koga") or "")) >= 16)
    _ch = _z.get("chisla") or {}
    check("записът носи ВЗЕТИ", _ch.get("vzeti") == 40)
    check("записът носи МИНАЛИ ФИЛТРИТЕ", _ch.get("preseti") == 7)
    check("записът носи ПУБЛИКУВАНИ", _ch.get("publikuvani") == 3)
    check("записът носи изходния код", _z.get("izhod") == _kod)
    check("записът носи прага", _z.get("prag") == MIN_VZETI)
    _iz = _z.get("izvori") or {}
    check("записът има ред за всеки източник",
          set(_iz) == {"football", "tabletennis"})
    check("редът носи присъдата",
          (_iz.get("tabletennis") or {}).get("prisada") == "ПРОВАЛ"
          and (_iz.get("football") or {}).get("prisada") == "НАРЕД")
    check("редът носи ЗАЩО",
          len(str((_iz.get("tabletennis") or {}).get("zashto") or "")) > 3)
    check("редът носи и гръмването",
          "brotli" in str((_iz.get("tabletennis") or {}).get("grimna") or ""))
    check("редът носи четирите числа",
          all(k in (_iz.get("football") or {})
              for k in ("vzeti", "zaqvki", "provali", "grimna")))
    check("записът НЕ оставя .tmp след себе си",
          _posleden.get("ostatak") == [])
    # 🔴 МЕКИЯТ РЕЖИМ НЕ БИВА ДА Е НЕВИДИМ ОТВЪН.
    _sm = MEK
    try:
        globals()["MEK"] = True
        _kod, _txt = _run_rav({}, 0)
        _z = _posleden.get("zapis") or {}
        check("мекият режим е ЗАПИСАН като мек", _z.get("mek") is True)
        check("суровият изход остава ненулев при мек режим",
              int(_z.get("izhod") or 0) != 0)
        check("върнатият изход е 0 при мек режим",
              _z.get("izhod_varnat") == 0 and _kod == 0)
    finally:
        globals()["MEK"] = _sm
    # Незаписуем път НЕ бива да сваля рън, чиито постове вече са тръгнали.
    _star = STATE_FILE
    try:
        globals()["STATE_FILE"] = os.path.join("nyama", "takava", "p.json")
        IZVORI.clear()
        vpishi_izvor("football", vzeti=40, zaqvki=9)
        _buf2 = _io.StringIO()
        with _ctx.redirect_stdout(_buf2):
            _k2 = ravnosmetka(2, preseti=2)
        check("незаписуем път НЕ сваля рънa", _k2 == 0)
        check("незаписуемият път се ОБЯВЯВА", "НЕ се записа" in _buf2.getvalue())
    finally:
        globals()["STATE_FILE"] = _star
    IZVORI.clear()

    # 🔴 ВРЪЗКАТА С matches.yml. Записът е безполезен, ако workflow-ът няма
    # право да пише и няма стъпка, която го връща в хранилището. Точно този
    # клас — «кодът може, но пътят навън липсва» — ни ухапа същия ден при
    # PREDICT_QUIET_TO. Затова се чете САМИЯТ yml, а не се вярва на паметта.
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          ".github", "workflows", "matches.yml")
        with open(_p, encoding="utf-8") as _f:
            _yml = _f.read()
        check("matches.yml дава право за запис", "contents: write" in _yml)
        check("matches.yml не е останал само за четене",
              "contents: read" not in _yml)
        # 🔴 СТРУКТУРНО, НЕ ПО РАЗПРЪСНАТИ ДУМИ (01.09.2026). Първата версия
        # търсеше «if: always()» в ЦЕЛИЯ файл и мутацията «махни го от
        # стъпката» ОЦЕЛЯ — защото същите думи стоят и в обяснителния
        # коментар над нея. Измерено: «if: always()» 2 пъти, «git add» 2
        # пъти, «matches_state.json» 3 пъти. Проверка, която брои
        # споменавания, не проверява нищо.
        # Затова тук се реже БЛОКЪТ на стъпката по име (коментарите остават
        # извън него) и се гледа какво има ВЪТРЕ.
        _blok, _redove = "", _yml.split("\n")
        for _i, _r in enumerate(_redove):
            if _r.strip() == "- name: Запази тефтера на мачовете":
                _ot = len(_r) - len(_r.lstrip())
                _blok = _r + "\n"
                for _r2 in _redove[_i + 1:]:
                    if _r2.strip() and (len(_r2) - len(_r2.lstrip())) <= _ot:
                        break
                    _blok += _r2 + "\n"
                break
        check("има стъпка «Запази тефтера на мачовете»", bool(_blok))
        check("тя връща ИМЕННО тефтера", "matches_state.json" in _blok)
        # `git add "$f"`, не голото «git add»: вътре в блока стои и коментарът
        # от 12.08 за `git add a b nyama.json`, който съдържа същите две думи.
        check("тя добавя файла един по един",
              'git add "$f"' in _blok)
        check("тя бута нагоре", "git push" in _blok)
        check("тя се пуска и при паднал бот", "if: always()" in _blok)
        check("тя червенее, ако бутането не мине", "exit 1" in _blok)
        # 🔴 Тази проверка отначало търсеше ВСЯКО споменаване — и падна върху
        # НОВИЯ коментар, който цитира старото твърдение, за да обясни защо
        # вече не важи. Цитат в история НЕ Е действащо твърдение. Затова се
        # търси само редът, който ЗАПОЧВА с него, тоест стои сам за себе си.
        check("старото твърдение «ботът не пише state» не стои като действащо",
              re.search(r"(?m)^# Ботът НЕ пише state файлове", _yml) is None)
    except Exception as _e:                                  # noqa: BLE001
        check("matches.yml се чете за сверка", False)
        print("   " + str(_e)[:70])

    # ---- главното: изходният код НЕ се изхвърля
    _opashka = _insp_src_na_izhoda()
    check("изходният код на main се уважава", "sys.exit(main()" in _opashka)
    check("няма голо викане на main", re.search(r"(?m)^\s+main\(\)\s*$", _opashka) is None)
    check("main връща равносметка, не голо return",
          _main_src.count("return ravnosmetka(") >= 3)
    check("старото сливащо изречение го няма",
          "или API мълчи" not in _main_src)

    fails = [n for n, ok in results if not ok]
    print(f"SELFTEST: {len(results) - len(fails)}/{len(results)} PASS")
    if fails:
        print("Провалени: " + ", ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    # 🔴 Досега изходът на main() се изхвърляше и рънът беше зелен винаги.
    sys.exit(main() or 0)
