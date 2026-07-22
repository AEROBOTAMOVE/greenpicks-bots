# -*- coding: utf-8 -*-
# GREEN PICKS - NEWS SHOWCASE (one-time demo). Posts EVERYTHING the news bot would
# pick from the current feeds (the last ~1-3 days RSS still holds) - no dedup state,
# no per-room cap of 2 (uses SHOWCASE_CAP). Reuses news_bot for feeds/classify/score/
# patterns (its Bulgarian content lives there). Own sender that respects 429 retry_after.
import os, re, html, time, json, urllib.request, urllib.parse, urllib.error
import news_bot as nb

CAP = int(os.environ.get("SHOWCASE_CAP", "8"))
NL = chr(10)
TOKEN = nb.BOT_TOKEN
CHAT = nb.CHAT_ID

def send(text, thread):
    url = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
    p = {"chat_id": CHAT, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "false"}
    tid = str(thread or "").strip()
    if tid.isdigit() and int(tid) > 1:
        p["message_thread_id"] = int(tid)
    for attempt in range(5):
        try:
            data = urllib.parse.urlencode(p).encode()
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=25) as r:
                return json.loads(r.read()).get("ok", False)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429:
                try:
                    ra = int(json.loads(body).get("parameters", {}).get("retry_after", 5))
                except Exception:
                    ra = 5
                print("  429 - waiting", ra + 1, "s")
                time.sleep(ra + 1)
                continue
            print("HTTP", e.code, body[:120])
            return False
        except Exception as e:
            print("FAIL", str(e)[:100])
            return False
    return False

def is_url(s):
    return (s.startswith("http://") or s.startswith("https://")) and (" " not in s)

def card(c, label):
    icon = nb.sport_emoji(c["title"])
    if c["score"] >= 5:
        icon = "🔥"
    elif c["score"] >= 4:
        icon = "⚡"
    body = icon + " <b>" + html.escape(label) + "</b>" + NL + NL + html.escape(c["title"])
    if is_url(c["link"]):
        body = body + NL + NL + '<a href="' + html.escape(c["link"], quote=True) + '">Прочети в ' + html.escape(c["source"]) + ' →</a>'
    else:
        body = body + NL + NL + '<i>' + html.escape(c["source"]) + '</i>'
    return body + NL + NL + '🦖 GREEN PICKS · витрина'

def main():
    if not TOKEN or not CHAT:
        print("Missing BOT_TOKEN/CHAT_ID"); return
    collected = []
    for source, u in nb.FEEDS:
        try:
            collected += nb.parse_rss(source, nb.fetch(u))[:40]
        except Exception as e:
            print("skip", source, str(e)[:80])
    titles = [c["title"] for c in collected]
    fresh = []
    seen = set()
    for c in collected:
        k = nb.h(c["title"])
        if k in seen:
            continue
        seen.add(k)
        c["score"] = nb.score_item(c["title"], titles)
        c["room"] = nb.classify(c["title"])
        if c["room"] == "football" and c["score"] < 4 and not re.search(nb.TOP_FOOTBALL, c["title"].lower()):
            continue
        need = 1 if c["room"] else nb.MIN_SCORE
        if c["score"] >= need:
            fresh.append(c)
    fresh.sort(key=lambda x: -x["score"])
    total = 0
    for room_key, room in nb.SPORT_ROOMS.items():
        mine = [c for c in fresh if c["room"] == room_key][:CAP]
        for c in mine:
            if send(card(c, room["title"]), room["thread"]):
                total += 1
            time.sleep(2)
        print(room["title"], "count", len(mine))
    general = [c for c in fresh if c["room"] is None][:CAP]
    for c in general:
        if send(card(c, "📰 НОВИНА"), nb.NEWS_THREAD_ID):
            total += 1
        time.sleep(2)
    print("general count", len(general))
    print("SHOWCASE posted", total, "news")

if __name__ == "__main__":
    main()
