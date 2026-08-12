# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ДНЕВНИЯТ РИТЪМ 🦖 (чист, автоматичен, GitHub Actions)

🚫 КАНАЛЪТ Е САМО ЗА ЧОВЕКА. Този бот НЕ пише в канала — никога, в никой режим.
   В канала стои ЕДИН приветствен пост (закачен) и след него публикува само човекът.
   Функцията post_channel е оставена нарочно, но тя ОТКАЗВА и го отпечатва —
   ако утре някой я извика по грешка, нищо не тръгва към канала.
   Стойността не се губи, а живее в ГРУПАТА, в правилната стая.

🔴 ЧАСОВЕТЕ В ТАЗИ ГЛАВА БЯХА ЛЪЖА ДО 11.08.2026. Пишеше „overview 21:00" и
   „results 23:00". Кронът е 0 17 * * * (UTC) = 20:00 бг, а режимът results е
   ПЕНСИОНИРАН и не праща нищо. Същият несъществуващ 21:00 се беше разплодил
   и по стените в стая 9 — една глава, прочетена като истина, ражда още лъжи.

Режими (DAILY_MODE):
  overview  20:00 бг (крон 0 17 UTC) — ПОГЛЕД НАПРЕД: какво предстои утре → стая 9.
                    НЕ Е обзор. Обзорът на деня е на scorer.py — той разполага с
                    отсъдените прогнози, тоест с истината. Този файл дълго време
                    пращаше ВТОРИ обзор в същата стая („Днес следихме N мача") и
                    двата стояха един под друг с различни числа.
                    По ЕДИН бот-пост на ден (състояние в daily_state.json).
  selftest        — проверява пазачите и текстовете, без да праща нищо.

Пенсионирани режими:
  results         — МАХНАТ. Резултатите и равносметките са изцяло на scorer.py:
                    „ДОКЪДЕ СМЕ ДНЕС" около 14:30 и „ФИНИШ НА ДЕНЯ" около 23:30.
                    Стар крон/диспач получава чист изход, без червен рън.
  topnews         — МАХНАТ. Всички новини живеят САМО в стая 26 „Новини",
                    разделени по спорт, и се правят от news_bot.py.
                    Ако стар крон/диспач извика topnews, ботът само го казва
                    и излиза чисто (код 0) — за да няма червен рън.

Карта на стаите (потвърдена):
   КАНАЛЪТ                 — САМО човекът. Бот никога.
   4 Фишове на деня        — САМО човекът-типстер. Бот никога.
   5/6/7/8 Футбол/Баскет/Тенис на маса/Волейбол — САМО срещите по направление.
   9 Резултати и статистика — от ТОЗИ бот само „поглед напред" (20:00), по един
                              на ден. Числата и равносметките са на scorer.py.
  10 Печеливши фишове      — фишовете и как са минали (scorer.py). Този бот не пише там.
  26 Новини                — всички новини (news_bot.py).
  27 БОТА ПРЕДРИЧА         — прогнозите на бота (predictor.py). Този бот не пише там.

Тон: числа, извадка, кратка причина. Без поучения, без съвети, без призиви.

Данни: TheSportsDB eventsday. Часовете са Europe/Sofia.
"""
import json, os, sys, time, urllib.request, urllib.parse, html, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import poster

SOFIA = ZoneInfo("Europe/Sofia")
NL = chr(10)
NL2 = chr(10) + chr(10)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# „or“, не default: празна GitHub-променлива да не изтрие номера и пазача с него.
CHANNEL_ID = (os.environ.get("CHANNEL_ID") or "-1004403334702").strip()
CHAT_ID = (os.environ.get("CHAT_ID") or "-1004426592150").strip()
RESULTS_THREAD = (os.environ.get("RESULTS_THREAD_ID") or "9").strip()    # 9  Резултати и статистика
MODE = ((os.environ.get("DAILY_MODE") or "").strip()
        or (sys.argv[1].strip() if len(sys.argv) > 1 else "")
        or "overview")
SPORTSDB_KEY = os.environ.get("SPORTSDB_KEY") or "123"
API = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"
STATE_FILE = (os.environ.get("DAILY_STATE_FILE") or "daily_state.json").strip()
FORCE = (os.environ.get("DAILY_FORCE", "").strip() == "1")

# 🚫 ЖЕЛЯЗНО: стаите на човека и на срещите. Ботът няма работа там.
FORBIDDEN_THREADS = {"4", "5", "6", "7", "8"}

def forbidden_chats():
    """Чатовете, в които този бот не пише. Каналът е човешки — влиза тук."""
    out = set()
    for x in (CHANNEL_ID, os.environ.get("CHANNEL_ID", "")):
        s = str(x or "").strip()
        if s:
            out.add(s)
    return out

BIG_LEAGUES = ["Premier League","La Liga","Serie A","Bundesliga","Ligue 1","Champions League",
               "Europa League","NBA","Euroleague","Nations League","WTA","ATP"]


def golyama_liga(lg):
    """Голяма ли е лигата. Сравнява по ЦЯЛА ДУМА, не по подниз.

    🔴 12.08.2026. Условието беше `b.lower() in lg.lower()` — чист подниз.
    Измерено на живо срещу TheSportsDB за утре: „NBA" хващаше **WNBA** и три
    женски мача излизаха под етикета „голяма лига". Същият капан дебне при
    всяко ново име, което съдържа старо (NBA/WNBA, Liga/La Liga).
    """
    niz = " " + re.sub(r"[^0-9a-zA-Zа-яА-Я ]+", " ", str(lg or "")).lower() + " "
    for b in BIG_LEAGUES:
        igla = " " + re.sub(r"[^0-9a-zA-Zа-яА-Я ]+", " ", b).lower().strip() + " "
        if igla in niz:
            return True
    return False

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

# ---------- ПРАЩАНЕ (с пазачи) ----------
def post_channel(text, preview=False):
    """ОТКАЗ по устройство. Каналът е на човека — този бот не пише там.
    Оставена е нарочно, за да е ясно защо и да не се върне по невнимание."""
    print("ОТКАЗ: каналът е само за човека. Ботът не публикува там.")
    print("       Обзорът и резултатите отиват в стая 9.")
    return False

def post_room(thread_id, text, preview=False):
    """Единственият път навън. Забранените стаи и каналът се отрязват ТУК."""
    tid = str(thread_id or "").strip()
    if tid in FORBIDDEN_THREADS:
        print(f"ОТКАЗ: стая {tid} е забранена за бота (човешки фишове / само срещи).")
        return False
    if not CHAT_ID:
        print(f"Няма CHAT_ID — пропускам стая {tid}."); return False
    if str(CHAT_ID).strip() in forbidden_chats():
        print("ОТКАЗ: CHAT_ID сочи към канала. Спирам, за да не пише бот в канала.")
        return False
    return poster.send_message(CHAT_ID, text, thread_id=tid, preview=preview)

def post_results_room(text, preview=False):
    """Всичко от този бот (обзор + резултати) ходи САМО в стая 9 „Резултати"."""
    return post_room(RESULTS_THREAD, text, preview=preview)

# ---------- СЪСТОЯНИЕ (един бот-пост на ден) ----------
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
    if FORCE:
        return False
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

def build_results_text(now, rows, limit=12):
    """Текстът за стая 9. Числа и извадка — нищо повече."""
    shown = rows[:limit]
    body = NL.join(shown)
    sample = (f"📌 Извадка: {len(shown)} от {len(rows)} завършени мача в горещите първенства."
              if len(rows) > len(shown)
              else f"📌 Извадка: {len(shown)} завършени мача в горещите първенства.")
    return (f"🤖 <b>ДЕНЯТ НА БОТА · резултати</b> · {date_bg(now)}{NL2}"
            f"{body}{NL2}"
            f"{sample}{NL}"
            f"🟢 THE GREEN ROOM")

def run_retired_results():
    """ПЕНСИОНИРАН на 29.07.2026 — режимът пращаше в стая 9 крайните резултати
    на ЧУЖДИ мачове от горещите първенства. Това не е нито отчет за човека
    типстер, нито отчет за бота — просто списък с чужди срещи, тоест шум точно
    в стаята, която трябва да носи истината за нашите прогнози.

    Днес работата я върши scorer.py: чете дневника на предсказателя, проверява
    как е свършил ВСЕКИ НАШ мач и пише пълния отчет (познати и сгрешени) в
    стая 9, а само познатите — в стая 10.

    Функцията остава, за да не почервенее daily.yml, ако някой я извика по
    навик. Не праща нищо."""
    print("Режим results е МАХНАТ. Резултатите на бота ги прави scorer.py:")
    print("той сравнява НАШИТЕ прогнози с истинския резултат и пише в стая 9")
    print("пълния отчет, а в стая 10 — само познатите. Нищо не е пратено.")
    return 0


def _old_run_results(now):
    day = now.strftime("%Y-%m-%d")
    state = load_state()
    if done_today(state, day, "results_room9"):
        print("Стая 9 вече има бот-поста за днес — мълча."); return

    rows = collect_results(now)
    if not rows:
        print("няма резултати от топ първенства"); return

    if post_room(RESULTS_THREAD, build_results_text(now, rows)):
        mark_done(state, day, "results_room9")
        print(f"Резултати → стая {RESULTS_THREAD}: {len(rows)} мача.")
    else:
        print("Стая 9 не прие поста — състоянието не се маркира.")

# ---------- OVERVIEW (21:00, стая 9) ----------
def collect_overview(now):
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
                tomorrow_big = f"{emo} {esc(e.get('strHomeTeam'))} — {esc(e.get('strAwayTeam'))}" + (f" ({t})" if t and t != "00:00" else "")
                break
        if tomorrow_big: break
        time.sleep(2.1)
    return {"total": total, "nsports": nsports, "hot": hot, "tomorrow": tomorrow_big}

def build_overview_text(now, d):
    """Кратък поглед НАПРЕД за стая 9. Не е обзор — обзорът е на scorer.py.

    ПРЕНАПИСАН 05.08.2026, СЛЕД КАТО ВИДЯХ ГРУПАТА С ОЧИТЕ СИ.
    В стая 9 стояха ДВА обзора един под друг:
      • „📊 ОБЗОР НА ДЕНЯ · 3 познати · 1 сгрешени · 75%"  (scorer.py)
      • „📊 ОБЗОРЪТ НА БОТА · Днес следихме 9 мача в 3 спорта" (този файл)
    Второто е точно езикът, който собственикът забрани: „спри да ми казваш
    какво следихме". И е по-лошо от излишно — два обзора с различни числа в
    една стая карат човека да не вярва на нито един.

    Затова тук вече НЯМА числа за деня. Отчетът е един и е на оценителя, който
    разполага с истината — отсъдените прогнози. Този пост остава само за това,
    което оценителят НЕ знае: какво предстои утре.

    Ако няма какво да се каже за утре, връща празно и постът не тръгва.
    Мълчанието е по-добро от запълване.
    """
    utre = d.get("tomorrow")
    if not utre:
        return ""
    # 🔴 ДАТАТА БЕШЕ ДНЕШНАТА, 11.08.2026. Излизаше „🔜 УТРЕ · вторник, 11.08"
    # — думата казва утре, числото до нея казва днес. Човек чете двете заедно
    # и остава с грешния ден. Същият дефект намерих и в отчета на фишовете
    # („ФИШОВЕТЕ ОТ ВЧЕРА" с днешна дата). Правилото е едно: числото и думата
    # до него не бива да си противоречат.
    utre_den = now + timedelta(days=1)
    return NL.join([
        f"🔜 <b>УТРЕ</b> · {date_bg(utre_den)}{NL}",
        f"{utre}",
        f"{NL}🟢 THE GREEN ROOM",
    ])

def run_overview(now):
    day = now.strftime("%Y-%m-%d")
    state = load_state()
    if done_today(state, day, "overview_room9"):
        print("Обзорът за днес вече е в стая 9 — мълча."); return
    d = collect_overview(now)
    txt = build_overview_text(now, d)
    if not txt:
        mark_done(state, day, "overview_room9")
        print("Няма какво да се каже за утре — мълча. Обзорът е на оценителя.")
        return
    if post_results_room(txt):
        mark_done(state, day, "overview_room9")
        print(f"Поглед напред → стая {RESULTS_THREAD}: пратен.")
    else:
        print("Стая 9 не прие поста — състоянието не се маркира.")

# ---------- ПЕНСИОНИРАН РЕЖИМ ----------
def run_retired_topnews():
    print("Режим topnews е МАХНАТ. Новините ходят само в стая 26 Новини "
          "(разделени по спорт) и се правят от news_bot.py.")
    print("Каналът не е новинарска лента — там пише само човекът.")

# ---------- SELFTEST ----------
def run_selftest():
    ok = 0; bad = []

    def check(name, cond):
        nonlocal ok
        if cond: ok += 1
        else: bad.append(name)

    sent = []
    real_send = poster.send_message
    poster.send_message = lambda *a, **k: (sent.append((a, k)) or True)
    try:
        # 🔴 ДАТАТА ДО ДУМАТА „УТРЕ". Излизаше „🔜 УТРЕ · вторник, 11.08" —
        # думата казва утре, числото казва днес. Проверката ги държи заедно.
        _dn = datetime(2026, 8, 11, 20, 0, tzinfo=SOFIA)
        _txt = build_overview_text(_dn, {"tomorrow": "🏀 В — Г (21:00)"})
        check("утрешният поглед носи УТРЕШНАТА дата", "12.08" in _txt)
        check("утрешният поглед НЕ носи днешната дата", "11.08" not in _txt)
        check("денят от седмицата също е утрешният", "сряда" in _txt)
        check("празното утре не праща нищо",
              build_overview_text(_dn, {"tomorrow": None}) == "")
        check("post_channel отказва", post_channel("тест") is False)
        check("post_channel не праща нищо", len(sent) == 0)
        for t in sorted(FORBIDDEN_THREADS):
            check(f"стая {t} отказана", post_room(t, "тест") is False)
        check("забранените стаи не пращат", len(sent) == 0)
        check("стая 9 приема обзора", post_results_room("тест") is True)
        check("стая 9 приема", post_room(RESULTS_THREAD, "тест") is True)
        check("каналът е в забранените чатове", str(CHANNEL_ID) in forbidden_chats())
    finally:
        poster.send_message = real_send

    now = sofia_now()
    rows = ["⚽ Отбор А 2–1 Отбор Б <i>· Premier League</i>" for _ in range(15)]
    t_res = build_results_text(now, rows)
    t_ovr = build_overview_text(now, {"total": 128, "nsports": 6,
                                      "hot": "⚽ А 2–1 Б", "tomorrow": "🏀 В — Г (21:00)"})
    banned = ["18+", "не гаранция", "не е съвет", "финансов съвет", "решението е твое",
              "залагай отговорно", "коеф", "банка", "единица", "букмейкър",
              "заложи", "залог"]
    for txt, label in ((t_res, "резултати"), (t_ovr, "обзор")):
        low = txt.lower()
        for b in banned:
            check(f"{label}: без „{b}“", b.lower() not in low)
    check("резултати: има извадка", "Извадка" in t_res)
    check("резултати: 12 от 15", "12 от 15" in t_res)
    # ПОСТЪТ ВЕЧЕ НЯМА ЧИСЛА — и това е нарочно (05.08.2026).
    # Дотук тук се проверяваше „обзор: има числа" и се търсеше „128". Но
    # числата на деня са на scorer.py — той има отсъдените прогнози. Този файл
    # праща само поглед НАПРЕД. Старата проверка остана да търси нещо, което
    # съзнателно махнах, вали портиера и събори ЦЕЛИЯ рън.
    # Поуката: смениш ли какво прави една функция, смени и това, което я пази.
    check("поглед напред: говори за утре", "УТРЕ" in t_ovr)
    check("поглед напред: носи мача", "🏀 В — Г (21:00)" in t_ovr)
    check("поглед напред: НЕ отчита труда на бота",
          not any(w in t_ovr.lower() for w in ("следихме", "гледахме", "мача в")))
    check("без мач за утре постът МЪЛЧИ",
          build_overview_text(now, {"total": 9, "nsports": 3}) == "")
    check("празни данни не чупят", build_overview_text(now, {}) == "")

    tmp = STATE_FILE + ".selftest"
    g = {}
    old_state_file = globals()["STATE_FILE"]
    old_force = globals()["FORCE"]
    globals()["STATE_FILE"] = tmp
    globals()["FORCE"] = False        # проверяваме пазача, не насилственото пускане
    try:
        day = now.strftime("%Y-%m-%d")
        check("състояние: празно в началото", done_today(g, day, "results_room9") is False)
        mark_done(g, day, "results_room9")
        check("състояние: пази се", done_today(load_state(), day, "results_room9") is True)
        check("състояние: чужд ключ не се пали", done_today(load_state(), day, "overview_room9") is False)
        globals()["FORCE"] = True
        check("DAILY_FORCE=1 бие пазача", done_today(load_state(), day, "results_room9") is False)
    finally:
        globals()["STATE_FILE"] = old_state_file
        globals()["FORCE"] = old_force
        try: os.remove(tmp)
        except Exception: pass

    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    check("без обратна кавичка", chr(96) not in src)
    check("без долар-скоба", (chr(36) + chr(123)) not in src)
    check("post_channel не вика poster", "poster.send_message" not in src.split("def post_room")[0].split("def post_channel")[1])

    print(f"SELFTEST: {ok} наред, {len(bad)} проблема.")
    for b in bad: print("  ❌", b)
    return 0 if not bad else 1

def main():
    if MODE == "selftest":
        sys.exit(run_selftest())
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN"); sys.exit(1)
    now = sofia_now()
    if MODE == "results":
        run_retired_results()          # работата я върши scorer.py
    elif MODE == "overview": run_overview(now)
    elif MODE in ("topnews", "news"):
        run_retired_topnews()          # излизаме чисто, без червен рън
    else:
        print("Непознат режим:", MODE); sys.exit(1)
    print(f"Режим {MODE} — край.")

if __name__ == "__main__":
    main()
