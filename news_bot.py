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
CHAT_ID = os.environ.get("CHAT_ID", "")
NEWS_THREAD_ID = os.environ.get("NEWS_THREAD_ID")

SPORT_ROOMS = {
    "tabletennis": {"thread": os.environ.get("TT_THREAD_ID", "7"),        "title": "🏓 ТЕНИС НА МАСА — новини",
                    "pat": r"тенис на маса|table tennis|ping pong|пинг понг|\bwtt\b|\bittf\b"},
    "volleyball":  {"thread": os.environ.get("VOLLEY_THREAD_ID", "8"),    "title": "🏐 ВОЛЕЙБОЛ — новини",
                    "pat": r"волейбол|volleyball|\bvnl\b|\bcev\b|plusliga|superlega|николов|соколов|казийски|лига на нациите"},
    "basketball":  {"thread": os.environ.get("BASKET_THREAD_ID", "6"),    "title": "🏀 БАСКЕТБОЛ — новини",
                    "pat": r"баскет|basketball|\bnba\b|\bwnba\b|евролига|euroleague|\bfiba\b|triple-double|леброн|lebron|йокич|jokic|дончич|doncic"},
    "football":    {"thread": os.environ.get("FOOTBALL_THREAD_ID", "5"),  "title": "⚽ ФУТБОЛ — новини",
                    "pat": r"футбол|цска|левски|лудогорец|champions league|premier league|la liga|serie a|bundesliga|\buefa\b|\bfifa\b|world cup|голмайстор|дузп|football|soccer|мондиал"},
}

TOP_FOOTBALL = r"champions league|premier league|la liga|serie a|bundesliga|ligue 1|europa league|световно|европейско|мондиал|national team|реал мадрид|барселона|байерн|ливърпул|манчестър|арсенал|челси|тотнъм|псж|ювентус|интер|милан|атлетико|\bfifa\b|\buefa\b"

def classify(title):
    t = title.lower()
    for key, room in SPORT_ROOMS.items():
        if re.search(room["pat"], t):
            return key
    return None

STATE_FILE = "sent_news.json"
MAX_ITEMS = 5
MIN_SCORE = 3
STATE_KEEP = 400

FEEDS = [
    ("Gong",      "https://gong.bg/rss"),
    ("Sportal",   "https://www.sportal.bg/rss"),
    ("Dsport",    "https://dsport.bg/rss"),
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
    ("Sky Sports","https://www.skysports.com/rss/12040"),
    ("ESPN",      "https://www.espn.com/espn/rss/news"),
]

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


def tg_send(text, thread_id=None, preview=False):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": (not preview)}
    try:
        tid = str(thread_id if thread_id is not None else (NEWS_THREAD_ID or "")).strip()
        if tid.isdigit() and int(tid) > 1:
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
        if c["room"] == "football":
            if c["score"] < 4 and not re.search(TOP_FOOTBALL, c["title"].lower()):
                continue
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
    sent_now = []

    def make_single(c, label):
        fire = "🔥" if c["score"] >= 5 else ("⚡" if c["score"] >= 4 else sport_emoji(c["title"]))
        safe_t = html.escape(c["title"])
        head = f'{fire} <b>{html.escape(label)}</b> · {now}\n\n{safe_t}'
        if re.match(r"https?://\S+$", c["link"]):
            safe_l = html.escape(c["link"], quote=True)
            head += f'\n\n<a href="{safe_l}">Прочети в {html.escape(c["source"])} →</a>'
        else:
            head += f'\n\n<i>{html.escape(c["source"])}</i>'
        head += "\n\n🦖 GREEN PICKS"
        return head

    for room_key, room in SPORT_ROOMS.items():
        mine = dedup([c for c in fresh if c["room"] == room_key], 2)
        for c in mine:
            if tg_send(make_single(c, room["title"]), thread_id=room["thread"], preview=True):
                sent_now.append(c)
        if mine:
            print(f"{room['title']}: {len(mine)} новини (с превю).")

    general = dedup([c for c in fresh if c["room"] is None], 3)
    for c in general:
        if tg_send(make_single(c, "📰 НОВИНА"), preview=True):
            sent_now.append(c)
    if general:
        print(f"📰 Новини: {len(general)} (с превю).")

    if not sent_now:
        print("Нищо важно — мълчим.")
        return

    sent = ([c["key"] for c in sent_now] + sent)[:STATE_KEEP]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sent, f)
    print(f"Общо пратени {len(sent_now)} новини.")


if __name__ == "__main__":
    main()
