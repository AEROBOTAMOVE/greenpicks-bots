# -*- coding: utf-8 -*-
"""
GREEN PICKS — БОТ №1 „НОВИНАРЯТ" 📰
Чете RSS от спортни сайтове, избира най-важните новини, праща карта в Telegram.
Пуска се от GitHub Actions 3x дневно. Помни пратеното в sent_news.json (комитва се обратно).
Без важни новини -> НЕ праща нищо (тишината е злато).
"""
import html
import json
import os
import re
import sys
import hashlib
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SOFIA = ZoneInfo("Europe/Sofia")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")            # id на групата (-100...)
NEWS_THREAD_ID = os.environ.get("NEWS_THREAD_ID")  # id на темата 📰 (число)

# 🎯 УМНИЯТ РАЗПРЕДЕЛИТЕЛ: всяка новина отива в СВОЯТА стая.
# РЕДЪТ Е ВАЖЕН: специфичните спортове ПРЕДИ футбола (волейболният ЦСКА
# съдържа „волейбол" -> хваща се преди клубното име във football-шаблона).
# \b = граница на дума (без 'nba' в 'fanbase').
SPORT_ROOMS = {
    "tabletennis": {"thread": os.environ.get("TT_THREAD_ID", "7"),        "title": "🏓 ТЕНИС НА МАСА — новини",
                    "pat": r"тенис на маса|table tennis|ping pong|пинг понг"},
    "volleyball":  {"thread": os.environ.get("VOLLEY_THREAD_ID", "8"),    "title": "🏐 ВОЛЕЙБОЛ — новини",
                    "pat": r"волейбол|volleyball|\bvnl\b|казийски"},
    "basketball":  {"thread": os.environ.get("BASKET_THREAD_ID", "6"),    "title": "🏀 БАСКЕТБОЛ — новини",
                    "pat": r"баскет|basketball|\bnba\b|\bwnba\b|евролига|euroleague|\bfiba\b|triple-double|леброн|lebron|йокич|jokic|дончич|doncic"},
    "football":    {"thread": os.environ.get("FOOTBALL_THREAD_ID", "5"),  "title": "⚽ ФУТБОЛ — новини",
                    "pat": r"футбол|цска|левски|лудогорец|champions league|premier league|la liga|serie a|bundesliga|\buefa\b|\bfifa\b|world cup|голмайстор|дузп|football|soccer|мондиал"},
}

# ⚽ ФУТБОЛ = САМО НАЙ-ВИСШИТЕ ЛИГИ И ГОЛЕМИТЕ ИСТОРИИ (заповед на шефа).
# Дребни/местни лиги НЕ минават — другите спортове са по-важни.
TOP_FOOTBALL = r"champions league|premier league|la liga|serie a|bundesliga|ligue 1|europa league|световно|европейско|мондиал|national team|реал мадрид|барселона|байерн|ливърпул|манчестър|арсенал|челси|тотнъм|псж|ювентус|интер|милан|атлетико|\bfifa\b|\buefa\b"

def classify(title):
    t = title.lower()
    for key, room in SPORT_ROOMS.items():
        if re.search(room["pat"], t):
            return key
    return None   # обща новина -> стая 📰

STATE_FILE = "sent_news.json"
MAX_ITEMS = 5          # максимум новини на пускане
MIN_SCORE = 3          # под този скор не пращаме
STATE_KEEP = 400       # колко хеша помним

# RSS източници (проверени формати; ако някой умре, ботът просто го прескача)
FEEDS = [
    ("Gong",      "https://gong.bg/rss"),
    ("Sportal",   "https://www.sportal.bg/rss"),
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
    ("Sky Sports","https://www.skysports.com/rss/12040"),
    ("ESPN",      "https://www.espn.com/espn/rss/news"),
]

# Ключови думи -> точки (важност). Regex с \b = начало на дума (без "гол" в "голям").
KEYWORDS = {
    5: [r"\bтрансфер", r"\btransfer", r"\bуволн", r"\bsacked", r"\bfired", r"\bоставк", r"\bпочина", r"\bdied", r"\bскандал", r"\bscandal", r"\bдисквалиф", r"\bbanned"],
    4: [r"\bконтузи", r"\binjur", r"\bаут за", r"\bruled out", r"\bфинал", r"\bfinal", r"\bтитла", r"\btitle", r"\bшампион", r"\bchampion"],
    3: [r"\bдерби", r"\bderby", r"\bрекорд", r"\brecord", r"\bкласик", r"\bclasico", r"връща се", r"\breturn\b", r"\bдебют", r"\bdebut"],
    2: [r"\bпобеда", r"\bзагуба", r"\bравенство", r"\bгол\b", r"\bголове", r"\bгола\b", r"\bgoal", r"\bwin\b", r"\bloss\b", r"\bdraw\b"],
}

SPORT_EMOJI = [("футбол|football|soccer|уефа|уеша|fifa|uefa", "⚽"), ("баскет|basket|nba", "🏀"),
               ("тенис на маса|table tennis", "🏓"), ("волейбол|volleyball", "🏐"), ("тенис|tennis", "🎾")]


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GreenPicksBot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_rss(source, raw):
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return items
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title and link:
            items.append({"source": source, "title": title, "link": link})
    # Atom fallback
    if not items:
        ns = "{http://www.w3.org/2005/Atom}"
        for e in root.iter(ns + "entry"):
            title = (e.findtext(ns + "title") or "").strip()
            link_el = e.find(ns + "link")
            link = link_el.get("href") if link_el is not None else ""
            if title and link:
                items.append({"source": source, "title": title, "link": link})
    return items


def score_item(title, all_titles):
    t = title.lower()
    score = 0
    for pts, words in KEYWORDS.items():
        if any(re.search(w, t) for w in words):
            score = max(score, pts)
    # буст: подобно заглавие в друг източник (обща дума 6+ букви)
    big_words = {w for w in re.findall(r"[а-яa-z]{6,}", t)}
    for other in all_titles:
        if other is title:
            continue
        ow = {w for w in re.findall(r"[а-яa-z]{6,}", other.lower())}
        if len(big_words & ow) >= 2:
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


def tg_send(text, thread_id=None):
    """Праща карта. Връща True/False — една счупена стая НЕ спира другите."""
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    try:
        tid = str(thread_id if thread_id is not None else (NEWS_THREAD_ID or "")).strip()
        if tid.isdigit() and int(tid) > 1:   # General (1) НЕ се подава като thread
            payload["message_thread_id"] = int(tid)
        elif tid:
            print(f"WARN: невалиден thread id {tid!r} — пращам в General.")
        data = urllib.parse.urlencode(payload).encode()
        resp = json.loads(fetch_post(api, data))
        if not resp.get("ok"):
            print("TG ERROR:", resp)
            return False
        return True
    except urllib.error.HTTPError as e:
        print("TG HTTP", e.code, e.read().decode("utf-8", "replace")[:300])
        return False
    except Exception as e:
        print("TG SEND FAIL:", e)
        return False


def fetch_post(url, data, timeout=20):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "GreenPicksBot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)

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
    sent_set = set(sent)

    collected = []
    for source, url in FEEDS:
        try:
            collected += parse_rss(source, fetch(url))[:25]
        except Exception as e:
            print(f"skip {source}: {e}")

    all_titles = [c["title"] for c in collected]
    # мост към Анализатора: последните заглавия (за 📰 флаг при мачовете)
    with open("last_news_titles.json", "w", encoding="utf-8") as f:
        json.dump(all_titles[:120], f, ensure_ascii=False)
    fresh = []
    for c in collected:
        key = h(c["title"])
        if key in sent_set:
            continue
        c["score"] = score_item(c["title"], all_titles)
        c["key"] = key
        c["room"] = classify(c["title"])
        # ⚽ филтър: футбол минава САМО ако е топ-лига/голяма история (или мега-новина score>=4)
        if c["room"] == "football":
            if c["score"] < 4 and not re.search(TOP_FOOTBALL, c["title"].lower()):
                continue   # дребен футбол = шум, режем го
        # спортна стая = пускаме и по-леки новини (нишата е ценна); обща = само важното
        need = 1 if c["room"] else MIN_SCORE
        if c["score"] >= need:
            fresh.append(c)

    fresh.sort(key=lambda x: -x["score"])

    def dedup(items, limit):
        out = []
        for c in items:
            cw = {w for w in re.findall(r"[а-яa-z]{6,}", c["title"].lower())}
            if any(len(cw & {w for w in re.findall(r'[а-яa-z]{6,}', t["title"].lower())}) >= 2 for t in out):
                continue
            out.append(c)
            if len(out) == limit:
                break
        return out

    now = datetime.now(SOFIA).strftime("%H:%M")
    medals = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    sent_now = []

    def make_card(title_line, items):
        lines = [f"<b>{html.escape(title_line)}</b> · {now}", ""]
        for i, c in enumerate(items):
            fire = "🔥" if c["score"] >= 5 else ("⚡" if c["score"] >= 4 else sport_emoji(c["title"]))
            safe_t = html.escape(c["title"])
            if re.match(r"https?://\S+$", c["link"]):
                safe_l = html.escape(c["link"], quote=True)
                lines.append(f'{medals[i]} {fire} <a href="{safe_l}">{safe_t}</a> <i>({html.escape(c["source"])})</i>')
            else:   # гнил линк -> заглавие без линк, картата ОЦЕЛЯВА
                lines.append(f'{medals[i]} {fire} {safe_t} <i>({html.escape(c["source"])})</i>')
        lines += ["", "🦖 GREEN PICKS"]
        return "\n".join(lines)

    # 1) Спортните стаи — всяка си получава СВОИТЕ новини
    for room_key, room in SPORT_ROOMS.items():
        mine = dedup([c for c in fresh if c["room"] == room_key], 3)
        if not mine:
            continue
        if tg_send(make_card(room["title"], mine), thread_id=room["thread"]):
            sent_now += mine
            print(f"{room['title']}: {len(mine)} новини.")

    # 2) Общата стая 📰 — топ новините без спортна стая
    general = dedup([c for c in fresh if c["room"] is None], MAX_ITEMS)
    if general:
        if tg_send(make_card("📰 ТОП НОВИНИ", general)):
            sent_now += general
            print(f"📰 Новини: {len(general)}.")

    if not sent_now:
        print("Нищо важно — мълчим.")
        return

    sent = ([c["key"] for c in sent_now] + sent)[:STATE_KEEP]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sent, f)
    print(f"Общо пратени {len(sent_now)} новини.")


if __name__ == "__main__":
    main()
