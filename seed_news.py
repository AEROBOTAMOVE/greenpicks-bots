# -*- coding: utf-8 -*-
"""
ЕДНОКРАТЕН ЗАРЕЖДАЧ: изважда новините от RSS фийдовете (те държат последните ~дни),
избира най-доброто с разнообразие по спортове и ги ПУБЛИКУВА В КАНАЛА
една по една, с линк + хаштаг. После рутерът ги разнася по стаите.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
MAX_POSTS = 12

FEEDS = [
    ("Gong",      "https://gong.bg/rss"),
    ("Sportal",   "https://www.sportal.bg/rss"),
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
    ("Sky Sports","https://www.skysports.com/rss/12040"),
    ("ESPN",      "https://www.espn.com/espn/rss/news"),
]

SPORTS = [
    ("#ТенисМаса", "🏓", r"тенис на маса|table tennis|пинг понг"),
    ("#Волейбол",  "🏐", r"волейбол|volleyball|\bvnl\b"),
    ("#Баскетбол", "🏀", r"баскет|basketball|\bnba\b|\bwnba\b|евролига|euroleague|\bfiba\b"),
    ("#Футбол",    "⚽", r"футбол|цска|левски|лудогорец|champions league|premier league|la liga|serie a|bundesliga|голмайстор|football|soccer"),
]

KEYWORDS = {
    5: [r"\bтрансфер", r"\btransfer", r"\bуволн", r"\bпочина", r"\bскандал", r"\bдисквалиф"],
    4: [r"\bконтузи", r"\binjur", r"\bаут за", r"\bфинал", r"\bfinal", r"\bтитла", r"\bшампион", r"\bchampion"],
    3: [r"\bдерби", r"\bderby", r"\bрекорд", r"\brecord", r"\bдебют", r"\breturn\b"],
    2: [r"\bпобеда", r"\bзагуба", r"\bгол\b", r"\bголове", r"\bgoal", r"\bwin\b"],
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GreenPicksBot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def parse_rss(source, raw):
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return items
    for item in root.iter("item"):
        t = (item.findtext("title") or "").strip()
        l = (item.findtext("link") or "").strip()
        if t and l:
            items.append({"source": source, "title": t, "link": l})
    return items


def sport_of(title):
    t = title.lower()
    for tag, emo, pat in SPORTS:
        if re.search(pat, t):
            return tag, emo
    return None, "📌"


def score(title):
    t = title.lower()
    s = 0
    for pts, words in KEYWORDS.items():
        if any(re.search(w, t) for w in words):
            s = max(s, pts)
    return s


def send(text):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": False}
    data = urllib.parse.urlencode(payload).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(api, data=data), timeout=25) as r:
            resp = json.loads(r.read())
        if not resp.get("ok"):
            print("TG ERROR:", resp)
            return False
        return True
    except urllib.error.HTTPError as e:
        print("TG HTTP", e.code, e.read().decode("utf-8", "replace")[:200])
        return False
    except Exception as e:
        print("TG FAIL:", e)
        return False


def main():
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN"); sys.exit(1)

    collected = []
    for src, url in FEEDS:
        try:
            collected += parse_rss(src, fetch(url))[:30]
        except Exception as e:
            print(f"skip {src}: {e}")

    for c in collected:
        c["score"] = score(c["title"])
        c["tag"], c["emo"] = sport_of(c["title"])
    collected.sort(key=lambda x: -x["score"])

    # разнообразие: до 3 на спорт + запълване с общи топ-новини
    chosen, per_sport = [], {}
    seen_words = []
    def is_dup(title):
        cw = {w for w in re.findall(r"[а-яa-z]{6,}", title.lower())}
        return any(len(cw & s) >= 2 for s in seen_words)
    for c in collected:
        if len(chosen) >= MAX_POSTS:
            break
        if is_dup(c["title"]):
            continue
        key = c["tag"] or "general"
        cap = 3 if c["tag"] else 4
        if per_sport.get(key, 0) >= cap:
            continue
        if not c["tag"] and c["score"] < 3:
            continue   # общите само ако са важни
        chosen.append(c)
        per_sport[key] = per_sport.get(key, 0) + 1
        seen_words.append({w for w in re.findall(r"[а-яa-z]{6,}", c["title"].lower())})

    print(f"Избрани {len(chosen)} новини за канала.")
    sent = 0
    for c in chosen:
        tag = f" {c['tag']}" if c["tag"] else ""
        safe_t = html.escape(c["title"])
        safe_l = html.escape(c["link"], quote=True)
        text = (f'{c["emo"]} <b><a href="{safe_l}">{safe_t}</a></b>\n'
                f'<i>{html.escape(c["source"])}</i> · 🦖 GREEN PICKS{tag}')
        if send(text):
            sent += 1
            print(f"OK [{c['tag'] or 'общи'}] {c['title'][:50]}")
        time.sleep(3)   # без флууд
    print(f"Публикувани {sent} новини в канала.")


if __name__ == "__main__":
    main()
