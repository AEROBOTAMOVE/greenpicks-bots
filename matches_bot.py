# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БОТ „АНАЛИЗАТОРЪТ" 📅🧠

Две различни неща, две различни места:

  1) СРЕЩИТЕ ДНЕС  ->  спортните стаи, по направление.
       ⚽ Футбол        стая 5   (FOOTBALL_THREAD_ID)
       🏀 Баскетбол     стая 6   (BASKET_THREAD_ID)
       🏓 Тенис на маса стая 7   (TT_THREAD_ID)
       🏐 Волейбол      стая 8   (VOLLEY_THREAD_ID)
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
ако има ключ. Лимитите се пазят: 2.1 сек между заявки към TheSportsDB,
6.5 сек към football-data. Часовете са Europe/Sofia.
Само сериозни турнири — дребните лиги не влизат никъде.
Всяка прогноза е вероятност от статистика, не гаранция. 18+
"""
import html
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
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
PREDICT_THREAD = (os.environ.get("PREDICT_THREAD_ID") or "27").strip()

# 🚫 Стаята на човека и стаята на новините. Ботът няма работа там.
FORBIDDEN_THREADS = {"4", "26"}
ALLOWED_THREADS = {FOOTBALL_THREAD, BASKET_THREAD, TT_THREAD, VOLLEY_THREAD, PREDICT_THREAD}

SPORTSDB_KEY = os.environ.get("SPORTSDB_KEY") or "123"   # празен env = тест-ключ, не счупен URL
FOOTBALL_DATA_KEY = (os.environ.get("FOOTBALL_DATA_KEY") or "").strip()

API = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"
FD_API = "https://api.football-data.org/v4"

MAX_PER_ROOM = 8      # колко срещи максимум в една спортна стая
ANALYSIS_MAX = 3      # колко срещи разнищваме дълбоко (всяка струва заявки)

# ПРИОРИТЕТ НА СПОРТОВЕТЕ (заповед на шефа: футболът е ПОСЛЕДЕН)
SPORTS = {
    "tabletennis": {"thread": TT_THREAD, "emoji": "🏓", "title": "ТЕНИС НА МАСА",
                    "api": "Table Tennis", "prio": 100},
    "volleyball":  {"thread": VOLLEY_THREAD, "emoji": "🏐", "title": "ВОЛЕЙБОЛ",
                    "api": "Volleyball", "prio": 90},
    "basketball":  {"thread": BASKET_THREAD, "emoji": "🏀", "title": "БАСКЕТБОЛ",
                    "api": "Basketball", "prio": 80},
    "football":    {"thread": FOOTBALL_THREAD, "emoji": "⚽", "title": "ФУТБОЛ",
                    "api": "Soccer", "prio": 10},
}
SPORT_ORDER = ["tabletennis", "volleyball", "basketball", "football"]

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
    return html.escape(str(x or ""))


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
    if not CHAT_ID:
        print("Няма CHAT_ID — пропускам.")
        return False
    return poster.send_message(CHAT_ID, clip(text), thread_id=tid, preview=False)


# ---------- ДАННИ ----------
def fetch_json(url, timeout=20, headers=None):
    hd = {"User-Agent": "GreenPicksBot/1.0"}
    if headers:
        hd.update(headers)
    if "thesportsdb.com" in url:
        time.sleep(2.1)    # free ключът е ~30 заявки/мин — дишаме
    req = urllib.request.Request(url, headers=hd)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


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
    for e in get_todays_events(cfg["api"]):
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


def fd_form(team_id):
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
    return st


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
    """Какво казват числата — ЧЕСТНО: вероятност и извадка, никога „сигурен мач"."""
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

    if n < 4:
        return ["🎲 Числата: извадката е твърде малка за оценка. Не гадаем."]
    if abs(edge) < 0.10:
        return [f"🎲 Числата: равностойно ({n} мача извадка) — няма превес, който да оправдае залог.",
                "   Пас също е решение."]
    p = 50.0 + min(15.0, abs(edge) * 30.0)
    side = home if edge > 0 else away
    return [f"🎲 Числата: лек превес за <b>{esc(side)}</b> — около {p:.0f}% срещу {100 - p:.0f}%.",
            f"   База: {n} мача (H2H + форма). Това е вероятност, не сигурен мач."]


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
    head = f"{cfg['emoji']} <b>{cfg['title']} · срещите днес</b> · {date_bg(now)}"
    body = NL.join(fixture_line(fx) for fx in rows)
    tail = ("📌 В тази стая влизат само срещите по направление — нищо друго." + NL
            + f"🧠 Анализът на бота е в {Q1}БОТА ПРЕДРИЧА{Q2}." + NL
            + f"🎯 Фишовете на човека-типстер са в {Q1}Фишове на деня{Q2}." + NL2
            + "⚠️ 18+ · подредба от статистика, не гаранция" + NL
            + "🟢 THE GREEN ROOM")
    return head + NL2 + body + NL2 + tail


def predict_card(picks, now, news_titles):
    parts = [f"🧠 <b>БОТА ПРЕДРИЧА</b> · {date_bg(now)}", ""]
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

        if not st["tot"] and st["hf"] == "?" and st["af"] == "?":
            parts.append("ℹ️ Няма достатъчно история за тази среща — не гадаем.")
        else:
            parts += numbers_say(fx["home"], fx["away"], st)
        parts.append("")

    parts.append("Как се чете това: числата дават вероятност и стойност, не сигурност.")
    parts.append(f"Малка извадка = малко доверие. {Q1}Няма залог{Q2} също е решение.")
    parts.append("📅 Пълните списъци със срещи са в стаите по спорт.")
    parts.append("⚠️ 18+ · прогноза от статистика, не гаранция")
    parts.append("🟢 THE GREEN ROOM")
    return NL.join(parts)


# ---------- ГЛАВНО ----------
def collect():
    """Всички днешни срещи, по кошници, вече прецедени и подредени."""
    buckets = {}

    fd_rows = []
    if FOOTBALL_DATA_KEY:
        try:
            fd_rows = fd_fixtures()
        except Exception as e:
            print("football-data пропадна:", str(e)[:90], "-> fallback TheSportsDB")
    if fd_rows:
        print(f"футбол: {len(fd_rows)} срещи от football-data.org")
        buckets["football"] = fd_rows
    else:
        if FOOTBALL_DATA_KEY:
            print("football-data: няма топ мачове днес -> пробвам TheSportsDB.")
        buckets["football"] = sportsdb_fixtures("football")

    for bucket in ("tabletennis", "volleyball", "basketball"):
        buckets[bucket] = sportsdb_fixtures(bucket)

    for bucket, rows in buckets.items():
        rows.sort(key=lambda fx: -fx["weight"])
        del rows[MAX_PER_ROOM:]
        rows.sort(key=lambda fx: fx["time"] or "99:99")
    return buckets


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)
    if os.environ.get("MATCHES_THREAD_ID"):
        print("Бележка: MATCHES_THREAD_ID е пенсиониран — срещите ходят по спортни стаи, "
              "анализът в стая 27. Стойността се игнорира.")

    now = datetime.now(SOFIA)
    buckets = collect()
    total = sum(len(v) for v in buckets.values())
    if not total:
        print("Няма сериозни срещи днес (или API мълчи) — мълчим и ние.")
        return

    # 1) СРЕЩИТЕ -> спортните стаи, по направление. Само списък, нищо друго.
    sent_rooms = 0
    for bucket in SPORT_ORDER:
        rows = buckets.get(bucket) or []
        if not rows:
            print(f"{bucket}: няма срещи от сериозни турнири — стаята мълчи.")
            continue
        if post_room(SPORTS[bucket]["thread"], room_card(bucket, rows, now)):
            sent_rooms += 1
            print(f"{bucket}: {len(rows)} срещи -> стая {SPORTS[bucket]['thread']}")

    # 2) АНАЛИЗЪТ -> стая 27 „БОТА ПРЕДРИЧА". Разсъждението живее само тук.
    pool = []
    for bucket in SPORT_ORDER:
        for fx in (buckets.get(bucket) or []):
            if fx["home"] and fx["away"]:
                pool.append(fx)
    pool.sort(key=lambda fx: -(fx["prio"] * 100 + fx["weight"]))
    picks = pool[:ANALYSIS_MAX]
    if not picks:
        print("Няма среща с два отбора за анализ — стая 27 мълчи.")
        print(f"Готово: {sent_rooms} спортни стаи.")
        return

    news_titles = load_recent_news_titles()
    for fx in picks:
        fx["stats"] = deep_stats(fx)
    if post_room(PREDICT_THREAD, predict_card(picks, now, news_titles)):
        print(f"Анализ: {len(picks)} срещи -> стая {PREDICT_THREAD}")
    print(f"Готово: {sent_rooms} спортни стаи, {total} срещи общо.")


if __name__ == "__main__":
    main()
