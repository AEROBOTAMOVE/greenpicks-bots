# -*- coding: utf-8 -*-
"""
GREEN PICKS — БОТ №2 „АНАЛИЗАТОРЪТ" 📅
Всяка сутрин: взима днешните мачове (футбол + баскетбол), избира топ 3-4,
за всеки вади: ⚔️ H2H (как са завършили срещите им), 📈 форма (последни 5),
📰 има ли свежа новина около отборите. Праща карта в темата 📅.
Данни: TheSportsDB (безплатен ключ). Пуска се от GitHub Actions.
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SOFIA = ZoneInfo("Europe/Sofia")

def esc(x):
    return html.escape(str(x or ""))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
MATCHES_THREAD_ID = os.environ.get("MATCHES_THREAD_ID")
SPORTSDB_KEY = os.environ.get("SPORTSDB_KEY") or "123"   # празен env = тест-ключ, не счупен URL
FOOTBALL_DATA_KEY = (os.environ.get("FOOTBALL_DATA_KEY") or "").strip()  # football-data.org

API = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"
FD_API = "https://api.football-data.org/v4"

FD_COMP_WEIGHT = {  # football-data.org competitions (free tier)
    "CL": 12, "PL": 10, "PD": 10, "SA": 9, "BL1": 9, "FL1": 8, "DED": 6,
    "PPL": 6, "ELC": 5, "BSA": 6, "EC": 12, "WC": 12,
}

# Тежест на лигите (кои мачове са "големи"). Останалите лиги = 1 точка.
LEAGUE_WEIGHT = {
    "English Premier League": 10, "UEFA Champions League": 12, "Spanish La Liga": 10,
    "Italian Serie A": 9, "German Bundesliga": 9, "French Ligue 1": 8,
    "UEFA Europa League": 8, "English League Championship": 5,
    "Bulgarian First League": 7,  # нашата :)
    "NBA": 10, "Euroleague": 8,
}
MAX_MATCHES = 5

# ПРИОРИТЕТ НА СПОРТОВЕТЕ (заповед на шефа: футболът е ПОСЛЕДЕН!)
# (спорт в API-то, емоджи, приоритет — по-голямо = по-напред)
SPORTS = [
    ("Table Tennis", "🏓", 100),
    ("Volleyball",   "🏐", 90),
    ("Basketball",   "🏀", 80),
    ("Handball",     "🤾", 70),
    ("Ice Hockey",   "🏒", 65),
    ("Tennis",       "🎾", 60),
    ("Darts",        "🎯", 55),
    ("Snooker",      "🎱", 50),
    ("MMA",          "🥊", 45),
    ("Boxing",       "🥊", 45),
    ("Soccer",       "⚽", 10),   # на опашката!
]


import time

def fetch_json(url, timeout=20, headers=None):
    hd = {"User-Agent": "GreenPicksBot/1.0"}
    if headers:
        hd.update(headers)
    if "thesportsdb.com" in url:
        time.sleep(2.1)   # free ключът е ~30 заявки/мин — дишаме
    req = urllib.request.Request(url, headers=hd)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# ---------- football-data.org (основен двигател за футбол) ----------

def fd_get(path):
    time.sleep(6.5)  # free tier: 10 заявки/мин — дишаме спокойно
    return fetch_json(FD_API + path, headers={"X-Auth-Token": FOOTBALL_DATA_KEY})


def fd_matches_today():
    d = today_str()
    data = fd_get(f"/matches?dateFrom={d}&dateTo={d}")
    # само предстоящи: отложен/прекратен мач НЕ е „МАЧ НА ДЕНЯ"
    return [m for m in (data.get("matches") or [])
            if m.get("status") in ("TIMED", "SCHEDULED")]


def fd_h2h(match_id):
    try:
        data = fd_get(f"/matches/{match_id}/head2head?limit=10")
        agg = data.get("aggregates") or {}
        matches = data.get("matches") or []
        return agg, matches
    except Exception as e:
        print("fd_h2h:", e)
        return {}, []


def fd_form(team_id, team_name):
    try:
        data = fd_get(f"/teams/{team_id}/matches?status=FINISHED")
        # API-то връща старо->ново; ние искаме ПОСЛЕДНИТЕ 5 (ново->старо)
        ms = sorted(data.get("matches") or [],
                    key=lambda m: m.get("utcDate") or "", reverse=True)[:5]
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
    except Exception as e:
        print("fd_form:", e)
        return "?"


def run_football_data():
    """Пълният анализ през football-data.org. Връща редовете на картата или None."""
    matches = [m for m in fd_matches_today()
               if (m.get("competition") or {}).get("code") in FD_COMP_WEIGHT]
    if not matches:
        return None
    matches.sort(key=lambda m: -FD_COMP_WEIGHT.get((m.get("competition") or {}).get("code"), 0))
    top = matches[:MAX_MATCHES]

    news_titles = load_recent_news_titles()
    weekday = ["понеделник","вторник","сряда","четвъртък","петък","събота","неделя"][datetime.now(SOFIA).weekday()]
    lines = [f"📅 <b>МАЧОВЕТЕ ДНЕС</b> · {weekday}", ""]

    for i, m in enumerate(top):
        raw_home = (m.get("homeTeam") or {}).get("name", "?")
        raw_away = (m.get("awayTeam") or {}).get("name", "?")
        home, away = esc(raw_home), esc(raw_away)
        comp = esc((m.get("competition") or {}).get("name", ""))
        t = ""
        try:
            t = datetime.fromisoformat((m.get("utcDate") or "").replace("Z", "+00:00")).astimezone(SOFIA).strftime("%H:%M")
        except ValueError:
            pass
        title = "🔥 <b>МАЧ НА ДЕНЯ</b>\n" if i == 0 else ""
        head = f"{title}⚽ <b>{home}</b> 🆚 <b>{away}</b>"
        if t:
            head += f" · {t} ч."
        if comp:
            head += f" · {comp}"
        lines.append(head)

        agg, h2h_matches = fd_h2h(m.get("id"))
        if agg:
            ha = (agg.get("homeTeam") or {})
            aa = (agg.get("awayTeam") or {})
            lines.append(f"⚔️ Последни {agg.get('numberOfMatches', '?')}: "
                         f"{home} {ha.get('wins', '?')} · Х {ha.get('draws', '?')} · {away} {aa.get('wins', '?')}")
        if h2h_matches:
            last = h2h_matches[0]
            ft = (last.get("score") or {}).get("fullTime") or {}
            lines.append(f"   Последно: {esc((last.get('homeTeam') or {}).get('shortName','?'))} "
                         f"{ft.get('home','?')}:{ft.get('away','?')} "
                         f"{esc((last.get('awayTeam') or {}).get('shortName','?'))} ({(last.get('utcDate') or '')[:10]})")

        hf = fd_form((m.get("homeTeam") or {}).get("id"), home)
        af = fd_form((m.get("awayTeam") or {}).get("id"), away)
        if hf != "?" or af != "?":
            lines.append(f"📈 Форма: {home} <code>{hf}</code> · {away} <code>{af}</code>")

        flags = [tm for tm in (raw_home, raw_away) if news_flag(tm, news_titles)]
        if flags:
            lines.append(f"📰 Свежа новина около: {esc(', '.join(flags))} — виж стая 📰!")
        lines.append("")

    lines.append("🎯 Пикът на деня — в канала. 🦖 GREEN PICKS")
    return lines


def today_str():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def get_todays_events(sport):
    d = today_str()
    try:
        data = fetch_json(f"{API}/eventsday.php?d={d}&s={urllib.parse.quote(sport)}")
        evs = data.get("events") or []
        # отложени/прекратени НЕ влизат в картата
        return [e for e in evs
                if (e.get("strStatus") or "").lower() not in ("postponed", "cancelled", "canceled")
                and (e.get("strPostponed") or "").lower() != "yes"]
    except Exception as e:
        print(f"eventsday {sport}: {e}")
        return []


def get_last_events(team_id):
    """Последните изиграни мачове на отбор (форма)."""
    try:
        data = fetch_json(f"{API}/eventslast.php?id={team_id}")
        return data.get("results") or []
    except Exception as e:
        print(f"eventslast {team_id}: {e}")
        return []


def get_h2h(home, away):
    """Историята помежду им: searchevents по 'Home_vs_Away' (и обратно)."""
    out = []
    for a, b in [(home, away), (away, home)]:
        q = urllib.parse.quote(f"{a}_vs_{b}")
        try:
            data = fetch_json(f"{API}/searchevents.php?e={q}")
            out += data.get("event") or []
        except Exception as e:
            print(f"h2h {a}/{b}: {e}")
    # само изиграни (с резултат), най-новите първи
    played = [e for e in out if e.get("intHomeScore") not in (None, "")]
    played.sort(key=lambda e: e.get("dateEvent") or "", reverse=True)
    return played[:5]


def form_string(team_name, events):
    """WWDLW от гледна точка на отбора."""
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
        home_side = e.get("strHomeTeam")
        winner = home_side if hs > as_ else (e.get("strAwayTeam") if as_ > hs else None)
        if winner == home:
            hw += 1
        elif winner == away:
            aw += 1
        else:
            dr += 1
    return hw, dr, aw


def score_event(e):
    w = LEAGUE_WEIGHT.get(e.get("strLeague", ""), 1)
    return e.get("_prio", 0) * 100 + w   # спортът тежи ПОВЕЧЕ от лигата


def markers(home, away, h2h, home_events, away_events):
    """🎯 ОСТРИТЕ СТРЕЛКИ — факти, не прогнози. Палят се когато данните позволяват."""
    out = []
    hw, dr, aw = h2h_summary(home, away, h2h)
    tot = hw + dr + aw
    if tot >= 3:
        if hw >= tot - 1 and hw > aw:
            out.append(f"👑 {home} доминира помежду им: {hw} от {tot}")
        elif aw >= tot - 1 and aw > hw:
            out.append(f"👑 {away} доминира помежду им: {aw} от {tot}")
        # головитост на сблъсъците (където има резултати)
        goals = []
        for e in h2h:
            try:
                goals.append(int(e["intHomeScore"]) + int(e["intAwayScore"]))
            except (TypeError, ValueError, KeyError):
                pass
        if len(goals) >= 3 and sum(goals) / len(goals) >= 3.0:
            out.append(f"🧨 Голелейни сблъсъци: средно {sum(goals)/len(goals):.1f} на мач")
    for name, evs in ((home, home_events), (away, away_events)):
        f = form_string(name, evs)
        if len(f) >= 3:
            if set(f[:3]) == {"W"}:
                streak = len(f) - len(f.lstrip("W"))
                out.append(f"🔥 {name} лети: {streak} поредни победи")
            elif "L" not in f:
                out.append(f"🛡 {name} без загуба в последните {len(f)}")
            elif set(f[:3]) == {"L"}:
                out.append(f"🥶 {name} в криза: 3 поредни загуби")
    return [m for m in out if m]


def load_recent_news_titles():
    """Заглавия от последното пускане на Новинаря (ако файлът е наличен) — за 📰 флаг."""
    titles = []
    if os.path.exists("last_news_titles.json"):
        try:
            with open("last_news_titles.json", encoding="utf-8") as f:
                titles = json.load(f)
        except Exception:
            pass
    return titles


GENERIC_WORDS = {"city", "united", "real", "club", "town", "sport", "sporting", "athletic", "olympic"}

def news_flag(team, titles):
    t = team.lower()
    words = [w for w in re.split(r"\s+", t) if len(w) >= 5 and w not in GENERIC_WORDS]
    if not words:
        return False
    for title in titles:
        tl = title.lower()
        if any(re.search(r"\b" + re.escape(w), tl) for w in words):
            return True
    return False


def tg_send(text):
    """Праща картата. Връща True/False — грешка при пращане НЕ пуска втора карта."""
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    try:
        tid = str(MATCHES_THREAD_ID or "").strip()
        if tid.isdigit() and int(tid) > 1:
            payload["message_thread_id"] = int(tid)
        elif tid:
            print(f"WARN: невалиден MATCHES_THREAD_ID {tid!r} — пращам в General.")
        data = urllib.parse.urlencode(payload).encode()
        req = urllib.request.Request(api, data=data)
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
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


def fmt_time(e):
    """UTC час от TheSportsDB -> български час."""
    t = (e.get("strTime") or "")[:5]
    d = (e.get("dateEvent") or "")[:10]
    if not t or t == "00:00":
        return ""
    try:
        dt = datetime.fromisoformat(f"{d}T{t}:00+00:00").astimezone(SOFIA)
        return dt.strftime("%H:%M")
    except ValueError:
        return t


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)

    # Основен двигател: football-data.org (ако има ключ)
    if FOOTBALL_DATA_KEY:
        fd_lines = None
        try:
            fd_lines = run_football_data()
        except Exception as e:
            print("football-data пропадна:", e, "→ fallback TheSportsDB")
        if fd_lines:
            # пращането е ИЗВЪН try-а на данните: грешка тук НЕ пуска втора карта
            if tg_send("\n".join(fd_lines)):
                print("football-data: карта пратена.")
            return
        print("football-data: няма топ мачове днес → пробвам TheSportsDB.")

    all_events = []
    for sport, emo, prio in SPORTS:
        for e in get_todays_events(sport):
            # ⚽ КАЧЕСТВО: футбол влиза САМО от познатите топ-лиги (без третодивизионни)
            if sport == "Soccer" and e.get("strLeague") not in LEAGUE_WEIGHT:
                continue
            e["_emoji"] = emo
            e["_prio"] = prio
            all_events.append(e)

    if not all_events:
        print("Няма мачове днес (или API мълчи).")
        return

    all_events.sort(key=score_event, reverse=True)
    top = all_events[:MAX_MATCHES]

    news_titles = load_recent_news_titles()
    weekday = ["понеделник","вторник","сряда","четвъртък","петък","събота","неделя"][datetime.now(SOFIA).weekday()]
    lines = [f"📅 <b>МАЧОВЕТЕ ДНЕС</b> · {weekday}", ""]

    for i, e in enumerate(top):
        home, away = e.get("strHomeTeam") or "", e.get("strAwayTeam") or ""
        league = esc(e.get("strLeague", ""))
        t = fmt_time(e)
        title = "🔥 <b>СБЛЪСЪКЪТ НА ДЕНЯ</b>\n" if i == 0 else ""
        if home and away:
            head = f'{title}{e["_emoji"]} <b>{esc(home)}</b> 🆚 <b>{esc(away)}</b>'
        else:   # събития без два отбора (дартс, ММА карти, турнири)
            head = f'{title}{e["_emoji"]} <b>{esc(e.get("strEvent", "?"))}</b>'
        if t:
            head += f" · {t}"
        if league:
            head += f" · {league}"
        lines.append(head)

        h2h, h_ev, a_ev = [], [], []
        if home and away:
            h2h = get_h2h(home, away)
            if h2h:
                hw, dr, aw = h2h_summary(home, away, h2h)
                lines.append(f"⚔️ Последни {len(h2h)}: {esc(home)} {hw} · Х {dr} · {esc(away)} {aw}")
                last = h2h[0]
                lines.append(f"   Последно: {esc(last.get('strHomeTeam'))} {last.get('intHomeScore')}:{last.get('intAwayScore')} {esc(last.get('strAwayTeam'))} ({(last.get('dateEvent') or '')[:10]})")

            h_ev = get_last_events(e.get("idHomeTeam")) if e.get("idHomeTeam") else []
            a_ev = get_last_events(e.get("idAwayTeam")) if e.get("idAwayTeam") else []
            hf, af = form_string(home, h_ev), form_string(away, a_ev)
            if hf != "?" or af != "?":
                lines.append(f"📈 Форма: {esc(home)} <code>{hf}</code> · {esc(away)} <code>{af}</code>")

            for m in markers(home, away, h2h, h_ev, a_ev):
                lines.append(esc(m))

        flags = [tm for tm in (home, away) if tm and news_flag(tm, news_titles)]
        if flags:
            lines.append(f"📰 Свежа новина около: {esc(', '.join(flags))} — виж стая 📰!")
        lines.append("")

    lines.append("🎯 Пикът на деня — в канала. 🦖 GREEN PICKS")
    if tg_send("\n".join(lines)):
        print(f"Пратени {len(top)} мача.")


if __name__ == "__main__":
    main()
