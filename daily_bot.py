# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ДНЕВНИЯТ РИТЪМ 🦖 (чист, автоматичен, GitHub Actions)

Режими (DAILY_MODE):
  overview  21:00 — ОБЗОРЪТ НА БОТА: числата за деня, в КАНАЛА.
                    Обзор = какво следихме, НЕ новинарска лента. Затова остава в канала.
  results   23:00 — резултатите на деня: обобщение в КАНАЛА
                    + ЕДИН бот-пост в стая 9 „Резултати и статистика", ясно надписан
                    като деня на БОТА (човекът си има свой пост там).

Пенсиониран режим:
  topnews         — МАХНАТ. Новините НЕ ходят в канала и НЕ ходят в спортните стаи.
                    Всички новини живеят САМО в стая 26 „Новини", разделени по спорт,
                    и се правят от news_bot.py. Тук не дублираме тази логика.
                    Ако стар крон/диспач извика topnews, ботът само го казва и излиза
                    чисто (код 0) — за да няма червен рън.

Карта на стаите (потвърдена):
   4 Фишове на деня       — САМО човекът-типстер. Бот никога.
   5/6/7/8 Футбол/Баскет/Тенис на маса/Волейбол — САМО срещите по направление.
                             Никакви новини, никакви бот-постове оттук.
   9 Резултати и статистика — един бот-пост на ден (пази се със състояние).
  26 Новини                — всички новини (news_bot.py).
  27 БОТА ПРЕДРИЧА         — всички прогнози на бота.

Данни: TheSportsDB eventsday. Часовете са Europe/Sofia.
Всичко от бота е прогноза от статистика, не гаранция. 18+
"""
import json, os, sys, time, urllib.request, urllib.parse, html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import poster

SOFIA = ZoneInfo("Europe/Sofia")
NL = chr(10)
NL2 = chr(10) + chr(10)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
CHAT_ID = os.environ.get("CHAT_ID", "-1004426592150")
RESULTS_THREAD = os.environ.get("RESULTS_THREAD_ID", "9")    # 9  Резултати и статистика
PREDICT_THREAD = os.environ.get("PREDICT_THREAD_ID", "27")   # 27 БОТА ПРЕДРИЧА
MODE = (os.environ.get("DAILY_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "overview")).strip()
SPORTSDB_KEY = os.environ.get("SPORTSDB_KEY") or "123"
API = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"
STATE_FILE = "daily_state.json"

# 🚫 ЖЕЛЯЗНО: стаите на човека и на срещите. Ботът няма работа там.
FORBIDDEN_THREADS = {"4", "5", "6", "7", "8"}

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

def sofia_now():
    return datetime.now(SOFIA)

def date_bg(now):
    wd = ["понеделник","вторник","сряда","четвъртък","петък","събота","неделя"][now.weekday()]
    return f"{wd}, {now.day}.{now.month:02d}"

# ---------- ПРАЩАНЕ (с пазач за забранените стаи) ----------
def post_channel(text, preview=False):
    return poster.send_message(CHANNEL_ID, text, preview=preview)

def post_room(thread_id, text, preview=False):
    """Единственият път към групата. Забранените стаи се отрязват тук, не по-нагоре."""
    tid = str(thread_id or "").strip()
    if tid in FORBIDDEN_THREADS:
        print(f"ОТКАЗ: стая {tid} е забранена за бота (човешки фишове / само срещи).")
        return False
    if not CHAT_ID:
        print(f"Няма CHAT_ID — пропускам стая {tid}."); return False
    return poster.send_message(CHAT_ID, text, thread_id=tid, preview=preview)

def post_prediction(text, preview=False):
    """Прогнозите на бота ходят САМО в стая 27 „БОТА ПРЕДРИЧА".
    Днес този файл не праща прогнози (те са в matches_bot.py) — ако утре добавим,
    минава оттук, за да не сбърка стаята."""
    return post_room(PREDICT_THREAD, text, preview=preview)

# ---------- СЪСТОЯНИЕ (един бот-пост на ден в стая 9) ----------
def load_state():
    try:
        s = json.load(open(STATE_FILE, encoding="utf-8-sig"))
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        print("state:", str(e)[:80])

def done_today(state, day, key):
    return state.get("date") == day and state.get(key) is True

def mark_done(state, day, key):
    if state.get("date") != day:
        state.clear()
        state["date"] = day
    state[key] = True
    save_state(state)

# ---------- RESULTS (горещите първенства) ----------
def collect_results(now):
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
    return rows

def run_results(now):
    day = now.strftime("%Y-%m-%d")
    state = load_state()
    if done_today(state, day, "results_channel") and done_today(state, day, "results_room9"):
        print("Резултатите за днес вече са пратени — мълча."); return

    rows = collect_results(now)
    if not rows:
        print("няма резултати от топ първенства"); return
    body = NL.join(rows[:12])

    # 1) КАНАЛЪТ — обобщението на деня
    if done_today(state, day, "results_channel"):
        print("Каналът вече има резултатите за днес.")
    else:
        ch = (f"✅ <b>РЕЗУЛТАТИ · горещите първенства</b> · {date_bg(now)}{NL2}"
              f"{body}{NL2}"
              f"🟢 THE GREEN ROOM")
        if post_channel(ch):
            mark_done(state, day, "results_channel")

    # 2) СТАЯ 9 — ЕДИН бот-пост на ден, ясно надписан че е денят на БОТА
    if done_today(state, day, "results_room9"):
        print("Стая 9 вече има бот-поста за днес.")
    else:
        room = (f"🤖 <b>ДЕНЯТ НА БОТА · резултати</b> · {date_bg(now)}{NL2}"
                f"{body}{NL2}"
                f"📌 Това е бот-частта за деня — един пост дневно."
                f"{NL}Постът на човека-типстер е отделен.{NL2}"
                f"⚠️ 18+ · прогноза от статистика, не гаранция{NL}"
                f"🟢 THE GREEN ROOM")
        if post_room(RESULTS_THREAD, room):
            mark_done(state, day, "results_room9")

    print(f"Резултати: {len(rows)} мача.")

# ---------- OVERVIEW (21:00, КАНАЛЪТ) ----------
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
    # утре голямо
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
    parts = [f"📊 <b>ОБЗОРЪТ НА БОТА</b> · {date_bg(now)}{NL}",
             f"Днес следихме <b>{total}</b> мача в <b>{nsports}</b> спорта. 📡"]
    if hot: parts.append(f"✅ Горещ резултат: {hot}")
    if tomorrow_big: parts.append(f"🔜 Утре голямо: {tomorrow_big}")
    parts.append(f"{NL}Честно за деня: не гоним бройка — стойност само там, където числата я дадоха.")
    parts.append("⚠️ 18+ · прогноза от статистика, не гаранция")
    parts.append(f"{NL}😴 Лека вечер. Утре пак сме тук. 🟢 THE GREEN ROOM")
    post_channel(NL.join(parts))
    print("Обзор: пратен.")

# ---------- ПЕНСИОНИРАН РЕЖИМ ----------
def run_retired_topnews():
    print("Режим topnews е МАХНАТ. Новините ходят само в стая 26 Новини "
          "(разделени по спорт) и се правят от news_bot.py.")
    print("Каналът не е новинарска лента — там са човекът-типстер и обзорът.")
    print("Оправи крона: 08:00 повикването отпада, news.yml поема новините.")

def main():
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN"); sys.exit(1)
    now = sofia_now()
    if MODE == "results": run_results(now)
    elif MODE == "overview": run_overview(now)
    elif MODE in ("topnews", "news"):
        run_retired_topnews()          # излизаме чисто, без червен рън
    else:
        print("Непознат режим:", MODE); sys.exit(1)
    print(f"Режим {MODE} — край.")

if __name__ == "__main__":
    main()
