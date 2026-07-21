# -*- coding: utf-8 -*-
"""
GREEN PICKS — БОТ №1 „НОВИНАРЯТ" 📰
Чете RSS от спортни сайтове, избира най-важните новини, праща карта в Telegram.
Пуска се от GitHub Actions 3x дневно. Помни пратеното в sent_news.json (комитва се обратно).
Без важни новини -> НЕ праща нищо (тишината е злато).
"""
import json
import os
import re
import sys
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")            # id на групата (-100...)
NEWS_THREAD_ID = os.environ.get("NEWS_THREAD_ID")  # id на темата 📰 (число)

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

# Ключови думи -> точки (важност)
KEYWORDS = {
    5: ["трансфер", "transfer", "уволн", "sacked", "fired", "оставка", "почина", "died", "скандал", "scandal", "дисквалиф", "banned"],
    4: ["контузия", "injury", "injured", "аут за", "ruled out", "финал", "final", "титла", "title", "шампион", "champion"],
    3: ["дерби", "derby", "рекорд", "record", "класик", "clasico", "връща се", "return", "дебют", "debut"],
    2: ["победа", "загуба", "равенство", "гол", "goal", "win", "loss", "draw"],
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
        if any(w in t for w in words):
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


def tg_send(text):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    if NEWS_THREAD_ID:
        payload["message_thread_id"] = int(NEWS_THREAD_ID)
    data = urllib.parse.urlencode(payload).encode()
    resp = json.loads(fetch_post(api, data))
    if not resp.get("ok"):
        print("TG ERROR:", resp)
        sys.exit(1)


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
        with open(STATE_FILE, encoding="utf-8") as f:
            sent = json.load(f)
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
        if c["score"] >= MIN_SCORE:
            fresh.append(c)

    fresh.sort(key=lambda x: -x["score"])
    # една история = една карта (изрязваме близнаци от други сайтове)
    top = []
    for c in fresh:
        cw = {w for w in re.findall(r"[а-яa-z]{6,}", c["title"].lower())}
        if any(len(cw & {w for w in re.findall(r'[а-яa-z]{6,}', t["title"].lower())}) >= 2 for t in top):
            continue
        top.append(c)
        if len(top) == MAX_ITEMS:
            break

    if not top:
        print("Нищо важно — мълчим.")
        return

    now = datetime.now(timezone.utc).astimezone().strftime("%H:%M")
    lines = [f"📰 <b>ТОП НОВИНИ</b> · {now}", ""]
    medals = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for i, c in enumerate(top):
        fire = "🔥" if c["score"] >= 5 else ("⚡" if c["score"] >= 4 else sport_emoji(c["title"]))
        lines.append(f'{medals[i]} {fire} <a href="{c["link"]}">{c["title"]}</a> <i>({c["source"]})</i>')
    lines += ["", "🦖 GREEN PICKS"]
    tg_send("\n".join(lines))

    sent = ([c["key"] for c in top] + sent)[:STATE_KEEP]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sent, f)
    print(f"Пратени {len(top)} новини.")


if __name__ == "__main__":
    main()
