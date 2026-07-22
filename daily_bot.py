# -*- coding: utf-8 -*-
"""
GREEN PICKS — ДНЕВНИЯТ РИТЪМ 🦖 (напълно автоматичен, GitHub Actions)
Режими (DAILY_MODE): morning · overview · midday · night · goodnight
  08:00 morning   — Добро утро от GREEN PICKS + колко мача днес
  08:15 overview  — ОБЗОР НА ДЕНЯ: акценти по спортове + топ новини
  14:00 midday    — КАКВО СЛЕДВА: вечерните мачове
  22:00 night     — НОЩНА СМЯНА: баскетбол/късни мачове
  22:30 goodnight — Чао до утре + какво предстои утре
Данни: TheSportsDB eventsday (всички спортове) + новини от last_news_titles.json.
Постове в КАНАЛА (лицето на GREEN PICKS).
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import poster

SOFIA = ZoneInfo("Europe/Sofia")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
CHAT_ID = os.environ.get("CHAT_ID", "")
MODE = (os.environ.get("DAILY_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "overview")).strip()
SPORTSDB_KEY = os.environ.get("SPORTSDB_KEY") or "123"
API = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"

SPORTS = [
    ("Soccer", "⚽", "Футбол"), ("Basketball", "🏀", "Баскетбол"),
    ("Tennis", "🎾", "Тенис"), ("Volleyball", "🏐", "Волейбол"),
    ("Table Tennis", "🏓", "Тенис на маса"), ("Ice Hockey", "🏒", "Хокей"),
    ("Handball", "🤾", "Хандбал"), ("Baseball", "⚾", "Бейзбол"),
    ("American Football", "🏈", "Ам. футбол"), ("Rugby", "🏉", "Ръгби"),
    ("Fighting", "🥊", "Бойни спортове"), ("Motorsport", "🏎️", "Мотоспорт"),
    ("Cricket", "🏏", "Крикет"), ("Darts", "🎯", "Дартс"),
]
import re
BIG = ["Champions League","Premier League","La Liga","Serie A","Bundesliga","Ligue 1","Europa League",
       "Euroleague","Nations League","World Cup","Grand Slam","Wimbledon","Roland Garros",
       "US Open","Australian Open","Stanley Cup","Super Bowl","UEFA"]
BIG_WORD = re.compile(r"\b(NBA|WNBA|NHL|MLB|NFL|ATP|WTA|VNL|WTT|FIFA)\b")
def is_big(e):
    lg = (e.get("strLeague") or "")
    return any(b.lower() in lg.lower() for b in BIG) or bool(BIG_WORD.search(lg))


def fetch_json(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GreenPicksBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("fetch:", str(e)[:80]); return {}


def events_for(date_str, sports=None):
    out = {}
    for skey, emo, bg in (sports or SPORTS):
        data = fetch_json(f"{API}/eventsday.php?d={date_str}&s={urllib.parse.quote(skey)}")
        evs = data.get("events") or []
        evs = [e for e in evs if (e.get("strStatus") or "").lower() not in ("postponed","cancelled","canceled")]
        if evs:
            out[skey] = evs
        time.sleep(2.1)
    return out


def ev_time(e):
    t = (e.get("strTime") or "")[:5]; d = (e.get("dateEvent") or "")[:10]
    if not t or t == "00:00":
        return None
    try:
        return datetime.fromisoformat(f"{d}T{t}:00+00:00").astimezone(SOFIA)
    except ValueError:
        return None


def esc(x):
    import html
    return html.escape(str(x or ""))


def highlights(evmap, when_filter=None, limit=8):
    rows = []
    for skey, evs in evmap.items():
        emo = next((e for s,e,b in SPORTS if s == skey), "•")
        for e in evs:
            t = ev_time(e)
            if when_filter and not when_filter(t):
                continue
            h, a = e.get("strHomeTeam"), e.get("strAwayTeam")
            name = f"{esc(h)} — {esc(a)}" if h and a else esc(e.get("strEvent", "?"))
            lg = esc(e.get("strLeague", ""))
            rows.append((is_big(e), t or datetime.max.replace(tzinfo=SOFIA), emo, name, lg))
    rows.sort(key=lambda r: (not r[0], r[1]))
    lines = []
    for big, t, emo, name, lg in rows[:limit]:
        ts = t.strftime("%H:%M") if t != datetime.max.replace(tzinfo=SOFIA) else "—"
        star = "🔥 " if big else ""
        lines.append(f"{emo} {star}<b>{name}</b> · {ts}" + (f" · {lg}" if lg else ""))
    return lines


def load_news(n=5):
    try:
        titles = json.load(open("last_news_titles.json", encoding="utf-8"))
        return [esc(t) for t in titles[:n]]
    except Exception:
        return []


def counts(evmap):
    total = sum(len(v) for v in evmap.values())
    per = sorted(((skey, len(v)) for skey, v in evmap.items()), key=lambda x: -x[1])
    return total, per


def sport_bg(skey):
    return next((b for s,e,b in SPORTS if s == skey), skey)
def sport_emo(skey):
    return next((e for s,e,b in SPORTS if s == skey), "•")


def post(text, image=None):
    if image:
        return poster.send_photo(CHANNEL_ID, image, text)
    return poster.send_message(CHANNEL_ID, text)


def main():
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN"); sys.exit(1)
    os.makedirs("cards_samples", exist_ok=True)
    now = datetime.now(SOFIA)
    today = now.strftime("%Y-%m-%d")
    wd = ["понеделник","вторник","сряда","четвъртък","петък","събота","неделя"][now.weekday()]
    date_bg = f"{wd}, {now.day}.{now.month:02d}"

    if MODE == "morning":
        ev = events_for(today)
        total, per = counts(ev)
        top3 = " · ".join(f"{sport_emo(s)}{n}" for s, n in per[:4]) if per else "—"
        txt = (f"☀️ <b>Добро утро от GREEN PICKS!</b> 🦖\n"
               f"<i>{date_bg}</i>\n\n"
               f"Днес на масата: <b>{total}</b> мача в <b>{len(per)}</b> спорта.\n"
               f"{top3}\n\n"
               f"Кафето е горещо, следим пазара за теб. 📊\n"
               f"В 08:15 — обзор на деня.")
        try:
            import cards
            img = cards.morning_card(date_bg, total, len(per), "cards_samples/_morning.png")
            post(txt, img)
        except Exception as e:
            print("morning card:", e); post(txt)

    elif MODE == "overview":
        ev = events_for(today)
        hl = highlights(ev, limit=8)
        news = load_news(4)
        parts = [f"📋 <b>ОБЗОР НА ДЕНЯ</b> · {date_bg}\n"]
        if hl:
            parts.append("<b>🎯 Мачове за гледане:</b>")
            parts += hl
        if news:
            parts.append("\n<b>📰 Топ новини:</b>")
            parts += [f"• {t}" for t in news]
        parts.append("\n🦖 GREEN PICKS · следим целия ден")
        post("\n".join(parts))

    elif MODE == "midday":
        ev = events_for(today)
        def evening(t): return t is None or t.hour >= 17
        hl = highlights(ev, when_filter=evening, limit=8)
        parts = [f"⏭️ <b>КАКВО СЛЕДВА</b> · тази вечер\n"]
        if hl:
            parts += hl
        else:
            parts.append("Спокойна вечер — малко мачове.")
        parts.append("\n🦖 GREEN PICKS")
        post("\n".join(parts))

    elif MODE == "night":
        ev = events_for(today, sports=[("Basketball","🏀","Баскетбол"),("Ice Hockey","🏒","Хокей"),
                                        ("American Football","🏈","Ам. футбол"),("Baseball","⚾","Бейзбол")])
        def late(t): return t is None or t.hour >= 21 or t.hour <= 6
        hl = highlights(ev, when_filter=late, limit=7)
        parts = [f"🌙 <b>НОЩНА СМЯНА</b> · отвъд океана\n"]
        if hl:
            parts.append("Докато BG спи, топката се върти:")
            parts += hl
        else:
            parts.append("Тиха нощ — без големи нощни мачове.")
        parts.append("\n🦖 GREEN PICKS")
        post("\n".join(parts))

    elif MODE == "goodnight":
        tmr = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        ev = events_for(tmr, sports=[s for s in SPORTS if s[0] in ("Soccer","Basketball","Tennis","Volleyball")])
        hl = highlights(ev, limit=4)
        parts = [f"🌙 <b>Чао до утре!</b> 🦖\n",
                 "Днешните резултати са в стаите. Утре пак сме на линия.\n"]
        if hl:
            parts.append("<b>Утре ни очаква:</b>")
            parts += hl
        parts.append("\nЛека нощ. 💚 GREEN PICKS")
        post("\n".join(parts))

    else:
        print("Непознат режим:", MODE); sys.exit(1)
    print(f"Режим {MODE} — пратено.")


if __name__ == "__main__":
    main()
