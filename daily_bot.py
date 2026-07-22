# -*- coding: utf-8 -*-
"""
GREEN PICKS — ДНЕВНИЯТ РИТЪМ 🦖 (чист, автоматичен, GitHub Actions)
Режими (DAILY_MODE):
  topnews   08:00 — 4 новини в КАНАЛА (по 1 за всеки спорт: ТТ/волей/баскет/футбол)
  overview  21:00 — ОБЗОРЪТ НА БОТА: числата за деня (готин, честен)
  results   23:00 — резултати от горещите първенства в КАНАЛА + стая ✅
Данни: RSS (през news_bot) + TheSportsDB eventsday. Всичко = прогноза от статистика.
"""
import json, os, sys, time, urllib.request, urllib.parse, html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import poster
import news_bot as nb

SOFIA = ZoneInfo("Europe/Sofia")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
CHAT_ID = os.environ.get("CHAT_ID", "")
RESULTS_THREAD = os.environ.get("RESULTS_THREAD_ID", "9")
MODE = (os.environ.get("DAILY_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "overview")).strip()
SPORTSDB_KEY = os.environ.get("SPORTSDB_KEY") or "123"
API = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"
TN_STATE = "topnews_state.json"

BIG_LEAGUES = ["Premier League","La Liga","Serie A","Bundesliga","Ligue 1","Champions League",
               "Europa League","NBA","Euroleague","Nations League","WTA","ATP"]

def esc(x): return html.escape(str(x or ""))

def fetch_json(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GreenPicksBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("fetch:", str(e)[:80]); return {}

def post_channel(text, preview=False):
    return poster.send_message(CHANNEL_ID, text, preview=preview)

def sofia_now():
    return datetime.now(SOFIA)

def date_bg(now):
    wd = ["понеделник","вторник","сряда","четвъртък","петък","събота","неделя"][now.weekday()]
    return f"{wd}, {now.day}.{now.month:02d}"

def load_tn():
    try: return set(json.load(open(TN_STATE, encoding="utf-8-sig")))
    except Exception: return set()

def save_tn(keys):
    with open(TN_STATE, "w", encoding="utf-8") as f:
        json.dump(list(keys)[:40], f, ensure_ascii=False)

def run_topnews(now):
    collected = []
    for src, url in nb.FEEDS:
        try: collected += nb.parse_rss(src, nb.fetch(url))[:25]
        except Exception as e: print("skip", src, str(e)[:50])
    if not collected:
        print("няма новини"); return
    import re
    titles = [c["title"] for c in collected]
    seen = load_tn()
    # 4 НОВИНИ В КАНАЛА — по ЕДНА за всеки спорт (ред на шефа: ТТ, волей, баскет, футбол)
    SPORTS_ORDER = [("tabletennis", "🏓 ТЕНИС НА МАСА"), ("volleyball", "🏐 ВОЛЕЙБОЛ"),
                    ("basketball", "🏀 БАСКЕТБОЛ"), ("football", "⚽ ФУТБОЛ")]
    sent = 0
    for room_key, label in SPORTS_ORDER:
        cands = [c for c in collected if nb.classify(c["title"]) == room_key]
        cands.sort(key=lambda c: -nb.score_item(c["title"], titles))
        for c in cands:
            key = nb.h(c["title"])
            if key in seen:
                continue
            if room_key == "football":
                if nb.score_item(c["title"], titles) < 4 and not re.search(nb.TOP_FOOTBALL, c["title"].lower()):
                    continue
            body = f"{label} · <b>Новина на деня</b> · {date_bg(now)}\n\n🔥 {esc(c['title'])}"
            if re.match(r"https?://\S+$", c["link"]):
                body += f"\n\n<a href=\"{esc(c['link'])}\">Прочети в {esc(c['source'])} →</a>"
            body += "\n\n🟢 GREEN PICKS · прогноза от статистика"
            if post_channel(body, preview=True):
                seen.add(key); sent += 1
                time.sleep(1.2)
            break
    save_tn(seen)
    print(f"Спорт-новини в канала: {sent} (по 1 на спорт).")

def run_results(now):
    d = now.strftime("%Y-%m-%d")
    rows = []
    for sport in ["Soccer", "Basketball"]:
        data = fetch_json(f"{API}/eventsday.php?d={d}&s={urllib.parse.quote(sport)}")
        for e in (data.get("events") or []):
            lg = e.get("strLeague", "")
            if not any(b.lower() in lg.lower() for b in BIG_LEAGUES): continue
            hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
            if hs in (None, "") or as_ in (None, ""): continue
            emo = "⚽" if sport == "Soccer" else "🏀"
            rows.append(f"{emo} {esc(e.get('strHomeTeam'))} {hs}–{as_} {esc(e.get('strAwayTeam'))} <i>· {esc(lg)}</i>")
        time.sleep(2.1)
    if not rows:
        print("няма резултати от топ първенства"); return
    body = f"✅ <b>РЕЗУЛТАТИ · горещите първенства</b> · {date_bg(now)}\n\n" + "\n".join(rows[:12]) + "\n\n🟢 GREEN PICKS"
    post_channel(body)
    if CHAT_ID:
        poster.send_message(CHAT_ID, body, thread_id=RESULTS_THREAD)
    print(f"Резултати: {len(rows)} мача.")

def run_overview(now):
    today = now.strftime("%Y-%m-%d")
    tmr = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    sports = [("Soccer","⚽"),("Basketball","🏀"),("Tennis","🎾"),("Volleyball","🏐"),
              ("Ice Hockey","🏒"),("Table Tennis","🏓"),("Handball","🤾"),("Baseball","⚾")]
    total = 0; nsports = 0; hot = None
    for skey, emo in sports:
        data = fetch_json(f"{API}/eventsday.php?d={today}&s={urllib.parse.quote(skey)}")
        evs = data.get("events") or []
        if evs: nsports += 1
        total += len(evs)
        for e in evs:
            lg = e.get("strLeague", "")
            hs = e.get("intHomeScore")
            if hs not in (None, "") and any(b.lower() in lg.lower() for b in BIG_LEAGUES) and not hot:
                hot = f"{emo} {esc(e.get('strHomeTeam'))} {hs}–{e.get('intAwayScore')} {esc(e.get('strAwayTeam'))}"
        time.sleep(2.1)
    tomorrow_big = None
    for skey, emo in [("Soccer","⚽"),("Basketball","🏀")]:
        data = fetch_json(f"{API}/eventsday.php?d={tmr}&s={urllib.parse.quote(skey)}")
        for e in (data.get("events") or []):
            if any(b.lower() in (e.get("strLeague") or "").lower() for b in BIG_LEAGUES):
                t = (e.get("strTime") or "")[:5]
                tomorrow_big = f"{emo} {esc(e.get('strHomeTeam'))} — {esc(e.get('strAwayTeam'))}" + (f" ({t})" if t and t!='00:00' else "")
                break
        if tomorrow_big: break
        time.sleep(2.1)
    parts = [f"📊 <b>ОБЗОРЪТ НА БОТА</b> · {date_bg(now)}\n",
             f"Днес следихме <b>{total}</b> мача в <b>{nsports}</b> спорта. 📡"]
    if hot: parts.append(f"✅ Горещ резултат: {hot}")
    if tomorrow_big: parts.append(f"🔜 Утре голямо: {tomorrow_big}")
    parts.append("\nЧестно за деня: не гоним бройка — стойност само там, където числата я дадоха.")
    parts.append("⚠️ 18+ · прогноза от статистика, не гаранция")
    parts.append("\n😴 Лека вечер. Утре в 08:00 пак сме тук. 🟢 GREEN PICKS")
    post_channel("\n".join(parts))
    print("Обзор: пратен.")

def main():
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN"); sys.exit(1)
    now = sofia_now()
    if MODE == "topnews": run_topnews(now)
    elif MODE == "results": run_results(now)
    elif MODE == "overview": run_overview(now)
    else: print("Непознат режим:", MODE); sys.exit(1)
    print(f"Режим {MODE} — край.")

if __name__ == "__main__":
    main()
