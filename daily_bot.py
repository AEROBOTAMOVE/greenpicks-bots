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

Данни: TheSportsDB eventsday.

🔴 ЧАСОВЕТЕ БЯХА ВТОРАТА ЛЪЖА В ТАЗИ ГЛАВА (поправено 01.09.2026).
   Тук пишеше „Часовете са Europe/Sofia“. Не бяха. Единственият часовник,
   който този файл показва — часът на утрешния голям мач — идваше СУРОВ от
   TheSportsDB, а неговото поле strTime е UTC. Измерено на живо срещу
   източника на 01.09.2026 за 02.09 (strTime срещу strTimeLocal):
       Дания 16:30/18:30 = −2 ч (CEST)   Русия 14:00/19:00 = −5 ч (UTC+5)
       Канада 23:00/19:00 = +4 ч (EDT)   САЩ  20:00/15:00 = +5 ч (CDT)
   Осем от девет сравними записа дават ТОЧНО пояса на държавата.
   Тоест датският мач в 19:30 софийско се обявяваше „(16:30)“ — три часа
   по-рано, точно колкото е лятната разлика. Зимата грешката е два часа.
   Днес всеки показан час минава през chas_bg() и ZoneInfo, не през +3.
"""
import json, os, sys, time, urllib.request, urllib.parse, html, re
from datetime import datetime, timedelta, timezone
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

    🔴 12.08.2026. Условието беше просто търсене на подниз в името на лигата.
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

def fetch_json(url, timeout=20, greshki=None):
    """Тегли JSON. При провал ЗАПИСВА СЛЕДА, а не само празно.

    🔴 01.09.2026. Дотук провалът връщаше празен речник — буква по буква
    същото, което връща и здрав източник без мачове. Тоест „питах и не ми
    отговориха“ беше НЕРАЗЛИЧИМО от „питах и няма мачове“. Върху точно тази
    неразличимост стоеше вторият дефект: run_overview маркираше деня „готов“
    и когато източникът е мълчал изцяло, и денят не се наваксваше никога.

    greshki: подаден списък събира по един ред за всяка пропаднала заявка.
    Без него поведението е както преди — заради старите извиквания.
    """
    def _sleda(kakvo):
        if greshki is not None:
            greshki.append(str(kakvo)[:120])
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GreenPicksBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("fetch:", str(e)[:80]); _sleda(str(e)[:80]); return {}
    # 200 с чуждо тяло (списък, низ, null) е ПРОВАЛ, не празен ден. Измерено
    # в този проект: чужд сървър връща 200 с празно тяло, щом лимитът е ударен.
    if not isinstance(d, dict):
        print("fetch: отговорът не е речник:", type(d).__name__)
        _sleda("не е речник: " + type(d).__name__)
        return {}
    return d

# ═══════════════════════════════ ЧАСЪТ: ЕДИН-ЕДИНСТВЕН ИЗТОЧНИК ═══════════
#
# ЗАЩО НЕ ФИКСИРАНО +3: зимата София е UTC+2, лятото UTC+3. Фиксирано число е
# дефект, който спи шест месеца и се събужда в последната неделя на октомври.
# ЗАЩО НЕ ЧАСОВИЯТ ПОЯС ОТ СРЕДАТА: доказано в този проект — променливата на
# средата връща UTC МЪЛЧАЛИВО на рънъра. Поясът се носи в кода, не в средата.
UTC = timezone.utc


def sofia_now():
    """Единственото „сега“ в този файл. Всичко показвано тръгва оттук."""
    return datetime.now(SOFIA)


def v_sofia(dt):
    """Превежда КАКВОТО И ДА Е обозначено време към софийско.

    Гол час без пояс връща None НАРОЧНО. Точно неозначеният час беше дефектът:
    низът „16:30“ не носи в себе си коя земя го е измерила. По-добре без час,
    отколкото с грешен — липсата се вижда, лъжата не.
    """
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None or dt.tzinfo.utcoffset(dt) is None:
        print("час без пояс — не го показвам:", str(dt)[:40])
        return None
    return dt.astimezone(SOFIA)


def chas_bg(dt):
    """ЕДИНСТВЕНИЯТ начин, по който този файл изписва часовник.

    Връща часа по софийско във вида ЧЧ:ММ, или празно — щом часът не се знае.
    """
    d = v_sofia(dt)
    return d.strftime("%H:%M") if d is not None else ""


def utc_v_sofia(data_niz, chas_niz):
    """dateEvent + strTime от TheSportsDB (те са UTC) → момент по софийско.

    Връща обозначен datetime в София, или None, ако низовете не се четат.
    """
    d = str(data_niz or "").strip()[:10]
    t = str(chas_niz or "").strip()[:8]
    if len(d) != 10 or len(t) < 4:
        return None
    if len(t) == 5:
        t = t + ":00"
    try:
        golo = datetime.strptime(d + " " + t, "%Y-%m-%d %H:%M:%S")
    except Exception:                                        # noqa: BLE001
        return None
    return golo.replace(tzinfo=UTC).astimezone(SOFIA)


def sabitie_sofia(e):
    """Кога започва мачът, по софийско. None, ако източникът мълчи за часа.

    Нулевият час в TheSportsDB е ПЛЪНКА за неизвестен час, не полунощ — старият
    код също го криеше. Превърнат наивно, той щеше да се показва като 03:00
    през лятото, тоест изсмукан от пръстите час на мач без обявен час.
    Затова се отсява ПРЕДИ превода, а не след него.
    """
    e = e or {}
    syrov = str(e.get("strTime") or "").strip()
    if syrov[:5] in ("", "00:00"):
        return None
    return utc_v_sofia(e.get("dateEvent"), syrov)


def date_bg(now):
    """Ден от седмицата + дата, ПО СОФИЙСКО. Чужд пояс се превежда, гол — не."""
    d = v_sofia(now)
    if d is None:
        return ""
    wd = ["понеделник","вторник","сряда","четвъртък","петък","събота","неделя"][d.weekday()]
    return f"{wd}, {d.day}.{d.month:02d}"

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

def _nov_den(state, day):
    """Смяна на деня. ПРЕНАСЯ следата за пропуснатите дни през нулирането.

    🔴 01.09.2026. Старото поведение беше голо нулиране — триеше всичко. Тоест
    дори да бяхме записали провал, на следващия ден следата изчезваше и
    наваксване беше невъзможно ПО УСТРОЙСТВО, а не по невнимание.

    Пропуснат = денят е бил ОПИТВАН (има брояч) и нито един ключ не е готов.
    Ден, който изобщо не е опитван, не се брои за пропуснат — иначе списъкът
    би се пълнил с дни, в които машината просто не е тръгвала.
    """
    if state.get("date") == day:
        return state
    star = state.get("date")
    propusnati = [d for d in (state.get("propusnati") or []) if isinstance(d, str)]
    opitvan = any(str(k).endswith("_opiti") for k in state)
    gotov = any(v is True for k, v in state.items() if k != "propusnati")
    if star and opitvan and not gotov and star not in propusnati:
        propusnati.append(star)
    state.clear()
    state["date"] = day
    if propusnati:
        state["propusnati"] = propusnati[-30:]
    return state


def done_today(state, day, key):
    if FORCE:
        return False
    return state.get("date") == day and state.get(key) is True

def mark_done(state, day, key):
    """ГОТОВ — само при ДОКАЗАН успех: приет пост или мълчание на ЗДРАВ източник."""
    _nov_den(state, day)
    state[key] = True
    state.pop(key + "_prichina", None)
    ostavashti = [d for d in (state.get("propusnati") or []) if d != day]
    if ostavashti:
        state["propusnati"] = ostavashti
    else:
        state.pop("propusnati", None)
    save_state(state)

def mark_failed(state, day, key, prichina=""):
    """ОПИТАН И ПРОПАДНАЛ. Не е готов — и това си личи, вместо да се крие.

    🔴 ЗАЩО СЪЩЕСТВУВА (01.09.2026). Живото състояние в хранилището беше
    date 2026-09-01 и overview_room9 true — ЕДИН флаг. По него няма как да се
    различи „пратих поста“ от „източникът падна и се отказах“. А run_overview
    пишеше същото true и в двата случая.

    Пише ИЗРИЧНО False (не липсващ ключ), плюс брояч на опитите и причина.
    done_today иска точно True, тоест False пуска нов опит — денят може да се
    навакса, вместо да бъде обявен за минал.
    """
    _nov_den(state, day)
    state[key] = False
    n = state.get(key + "_opiti")
    state[key + "_opiti"] = (n if isinstance(n, int) and n >= 0 else 0) + 1
    if prichina:
        state[key + "_prichina"] = str(prichina)[:200]
    save_state(state)
    return state[key + "_opiti"]

# ---------- RESULTS (горещите първенства) ----------
def collect_results(now):
    d = now.strftime("%Y-%m-%d")
    rows = []
    for sport in ["Soccer", "Basketball"]:
        data = fetch_json(f"{API}/eventsday.php?d={d}&s={urllib.parse.quote(sport)}")
        for e in (data.get("events") or []):
            lg = e.get("strLeague", "")
            if not golyama_liga(lg): continue
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
    """Събира днешното броене и утрешния голям мач.

    Връща и СМЕТКАТА на заявките: колко са зададени и колко са пропаднали.
    Без нея извикващият не може да различи празен ден от мълчащ източник —
    и точно тази слепота заключваше деня като готов.
    """
    today = now.strftime("%Y-%m-%d")
    tmr = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    greshki = []
    broi = [0]

    def vzemi(url):
        broi[0] += 1
        return fetch_json(url, greshki=greshki)

    sports = [("Soccer","⚽"),("Basketball","🏀"),("Tennis","🎾"),("Volleyball","🏐"),
              ("Ice Hockey","🏒"),("Table Tennis","🏓"),("Handball","🤾"),("Baseball","⚾")]
    total = 0; nsports = 0; hot = None
    for skey, emo in sports:
        data = vzemi(f"{API}/eventsday.php?d={today}&s={urllib.parse.quote(skey)}")
        evs = data.get("events") or []
        if evs: nsports += 1
        total += len(evs)
        for e in evs:
            lg = e.get("strLeague", "")
            hs = e.get("intHomeScore")
            if hs not in (None, "") and golyama_liga(lg) and not hot:
                hot = f"{emo} {esc(e.get('strHomeTeam'))} {hs}–{e.get('intAwayScore')} {esc(e.get('strAwayTeam'))}"
        time.sleep(2.1)

    # 🔴 ДЕНЯТ НА ИЗТОЧНИКА НЕ Е НАШИЯТ ДЕН (01.09.2026). eventsday.php реди
    # мачовете по UTC ден. Щом часът вече се превежда към софийско, мач в
    # 23:30 UTC „утре“ пада в 02:30 бг ВДРУГИДЕН — а постът пише „УТРЕ“.
    # Обратното също е вярно и е стара, невидяна загуба: 22:30 UTC ДНЕС е
    # 01:30 бг УТРЕ, а старият код изобщо не поглеждаше в днешния кош.
    # Затова се четат ДВАТА UTC дни, а минава само това, което по СОФИЙСКО
    # пада утре. Иначе поправката на часа щеше да роди нова лъжа за деня.
    utre_bg = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_big = None
    for skey, emo in [("Soccer","⚽"),("Basketball","🏀")]:
        for den, strogo in ((tmr, False), (today, True)):
            data = vzemi(f"{API}/eventsday.php?d={den}&s={urllib.parse.quote(skey)}")
            for e in (data.get("events") or []):
                if not golyama_liga(e.get("strLeague")):
                    continue
                kogato = sabitie_sofia(e)
                if kogato is None:
                    # Източникът не дава час. От ДНЕШНИЯ кош такъв мач не може
                    # да се твърди за утрешен — пропуска се. От утрешния кош се
                    # приема, както винаги е било, но БЕЗ часовник до него.
                    if strogo:
                        continue
                elif kogato.strftime("%Y-%m-%d") != utre_bg:
                    continue
                t = chas_bg(kogato)
                tomorrow_big = (f"{emo} {esc(e.get('strHomeTeam'))} — "
                                f"{esc(e.get('strAwayTeam'))}"
                                + (f" ({t})" if t else ""))
                break
            if tomorrow_big: break
            time.sleep(2.1)
        if tomorrow_big: break
    return {"total": total, "nsports": nsports, "hot": hot, "tomorrow": tomorrow_big,
            "zayavki": broi[0], "greshki": len(greshki), "prichini": greshki[:3]}

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
    """🔴 „СВЪРШИХ“ И „ОПИТАХ И НЕ СТАНА“ СА РАЗЛИЧНИ НЕЩА (01.09.2026).

    Дотук ВСЕКИ празен изход слагаше готов: паднеше ли източникът, денят се
    заключваше и не се наваксваше никога. Отказаният пост пък не пишеше нищо —
    тоест провалът се пазеше само в дневника на Actions, който не се чете
    отвън. Днес има четири различни изхода и всеки оставя различна следа.
    """
    day = now.strftime("%Y-%m-%d")
    state = load_state()
    if done_today(state, day, "overview_room9"):
        print("Обзорът за днес вече е в стая 9 — мълча."); return
    d = collect_overview(now)
    txt = build_overview_text(now, d)
    greshki = int(d.get("greshki") or 0)
    zayavki = int(d.get("zayavki") or 0)
    otgovorili = zayavki - greshki

    if txt:
        if post_results_room(txt):
            mark_done(state, day, "overview_room9")
            print(f"Поглед напред → стая {RESULTS_THREAD}: пратен.")
        else:
            n = mark_failed(state, day, "overview_room9", "стая 9 не прие поста")
            print(f"Стая 9 не прие поста. Записан е ПРОВАЛ, опит {n} — не готов.")
        return

    # Празно е ЛЕГИТИМНО само ако източникът наистина е отговорил.
    if greshki or otgovorili <= 0:
        prichina = f"източникът падна: {greshki} пропаднали от {zayavki} заявки"
        n = mark_failed(state, day, "overview_room9", prichina)
        print(f"{prichina}. Записан е ПРОВАЛ, опит {n} — не готов.")
        print("Денят остава за наваксване, вместо да бъде обявен за минал.")
        for p in (d.get("prichini") or []):
            print("   причина:", p)
        return

    mark_done(state, day, "overview_room9")
    print(f"Няма какво да се каже за утре ({zayavki} заявки, 0 провала) — мълча.")
    print("Обзорът е на оценителя.")

# ---------- ПЕНСИОНИРАН РЕЖИМ ----------
def run_retired_topnews():
    print("Режим topnews е МАХНАТ. Новините ходят само в стая 26 Новини "
          "(разделени по спорт) и се правят от news_bot.py.")
    print("Каналът не е новинарска лента — там пише само човекът.")

# ---------- SELFTEST ----------
def _proveri_ligi(ck):
    """Пазач за golyama_liga. Викан от run_selftest.

    🔴 12.08.2026. Функцията беше НАПИСАНА и НИКОГА НЕ СЕ ВИКАШЕ — трите
    филтъра още търсеха подниз, тоест „NBA" хващаше WNBA и женски мачове
    излизаха под етикета „голяма лига". Точно класът „защита на хартия".
    Затова тук се проверява И поведението, И че старото търсене го няма.
    Иглите долу са СГЛОБЕНИ от парчета — иначе този докстринг сам би ги
    съдържал и проверката щеше да пада винаги, каквото и да е в кода.
    """
    for lg, ochakvan in (("NBA", True), ("WNBA", False), ("NBA Summer League", True),
                         ("La Liga", True), ("Liga MX", False), ("Serie A", True),
                         ("Serie B", False), ("Premier League", True),
                         ("Champions League", True), ("Euroleague", True),
                         ("ATP", True), ("WTA", True), ("", False), (None, False)):
        ck("лигата " + str(lg) + " -> " + str(ochakvan), golyama_liga(lg) is ochakvan)
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as f:
            src = f.read()
    except Exception:                                        # noqa: BLE001
        src = ""
    ck("подниз-сравнението за лиги го няма",
       ("b.lower() in lg" + ".lower()") not in src)
    ck("подниз-сравнението за лиги го няма и в другия вид",
       ('b.lower() in (e.get("str' + 'League")') not in src)
    ck("филтрите викат golyama_liga", src.count("golyama_liga(") >= 4)


def _proveri_chasa(ck, src):
    """Пазач за ЕДИНСТВЕНИЯ източник на софийско време.

    Числата долу са МЕРЕНИ на живо срещу TheSportsDB на 01.09.2026 за 02.09:
    датски мач strTime 16:30 при strTimeLocal 18:30 (CEST=UTC+2), руски
    14:00/19:00 (UTC+5), канадски 23:00/19:00 (EDT=UTC−4), американски
    20:00/15:00 (CDT=UTC−5). Осем от девет сравними записа дават точно пояса
    на държавата — тоест strTime Е UTC, а постът го обявяваше за софийско.
    """
    zima = utc_v_sofia("2026-01-15", "12:00:00")
    lyato = utc_v_sofia("2026-07-15", "12:00:00")
    ck("януари: 12:00 UTC става 14:00 бг", chas_bg(zima) == "14:00")
    ck("юли: 12:00 UTC става 15:00 бг", chas_bg(lyato) == "15:00")
    ck("зимното изместване е точно 2 часа",
       zima is not None and zima.utcoffset().total_seconds() == 2 * 3600)
    ck("лятното изместване е точно 3 часа",
       lyato is not None and lyato.utcoffset().total_seconds() == 3 * 3600)
    ck("зима и лято НЕ са едно и също изместване",
       zima.utcoffset() != lyato.utcoffset())
    ck("датският мач 16:30 UTC е 19:30 бг",
       chas_bg(utc_v_sofia("2026-09-02", "16:30:00")) == "19:30")
    ck("руският мач 14:00 UTC е 17:00 бг",
       chas_bg(utc_v_sofia("2026-09-02", "14:00:00")) == "17:00")
    ck("късният 23:30 UTC е 02:30 бг",
       chas_bg(utc_v_sofia("2026-09-02", "23:30:00")) == "02:30")
    ck("и пада ВДРУГИДЕН, не на своята UTC дата",
       utc_v_sofia("2026-09-02", "23:30:00").strftime("%Y-%m-%d") == "2026-09-03")
    ck("гол час без пояс не се показва",
       chas_bg(datetime(2026, 7, 1, 12, 0)) == "")
    ck("липсващият час не се показва", chas_bg(None) == "")
    ck("преводът не мести абсолютния момент",
       v_sofia(datetime(2026, 7, 1, 12, 0, tzinfo=UTC)).timestamp()
       == datetime(2026, 7, 1, 12, 0, tzinfo=UTC).timestamp())
    ck("плънката за неизвестен час не ражда час",
       sabitie_sofia({"dateEvent": "2026-07-15", "strTime": "00:00:00"}) is None)
    ck("празният час не ражда час",
       sabitie_sofia({"dateEvent": "2026-07-15", "strTime": ""}) is None)
    ck("истинският час на мач се превежда",
       chas_bg(sabitie_sofia({"dateEvent": "2026-07-15",
                              "strTime": "18:00:00"})) == "21:00")
    ck("счупена дата не чупи", utc_v_sofia("не-дата", "18:00:00") is None)
    ck("date_bg превежда чужд пояс",
       date_bg(datetime(2026, 7, 1, 23, 30, tzinfo=UTC)) == "четвъртък, 2.07")
    ck("date_bg на гол час мълчи",
       date_bg(datetime(2026, 7, 1, 23, 30)) == "")

    # ─────── и че НЯМА ВТОРО място, което си мери или изписва часа само
    _sega = "datetime.now" + "("
    ck("единствен източник на сегашния момент", src.count(_sega) == 1)
    _chas = "strftime(" + chr(34) + "%H:%M" + chr(34) + ")"
    ck("единствено място изписва часовник", src.count(_chas) == 1)
    _syrovo = ("(e.get(" + chr(34) + "strTime" + chr(34) + ") or "
               + chr(34) + chr(34) + ")[:5]")
    ck("суровият strTime вече не се показва", _syrovo not in src)
    ck("няма фиксирано изместване в часове", ("timedelta(" + "hours=") not in src)
    ck("няма utcnow", ("utc" + "now(") not in src)
    ck("поясът е по име",
       ("ZoneInfo(" + chr(34) + "Europe/Sofia" + chr(34) + ")") in src)
    ck("поясът не се чака от средата",
       ("environ[" + chr(34) + "TZ" + chr(34) + "]") not in src
       and ("environ.get(" + chr(34) + "TZ" + chr(34)) not in src)


def _proveri_sastoyanieto(ck):
    """Пазач за разликата между „свърших“ и „опитах и не стана“.

    🔴 Живото състояние в хранилището на 01.09.2026 беше буквално две полета:
    date 2026-09-01 и overview_room9 true. ЕДИН флаг, по който няма как да се
    различи пратен пост от отказ. Тези проверки държат разликата.
    """
    import shutil as _sh
    import tempfile
    papka = tempfile.mkdtemp()
    tmp = os.path.join(papka, "sastoyanie.json")
    star_file = globals()["STATE_FILE"]
    star_force = globals()["FORCE"]
    star_collect = globals()["collect_overview"]
    star_fetch = globals()["fetch_json"]
    real_send = poster.send_message
    real_sleep = time.sleep
    globals()["STATE_FILE"] = tmp
    globals()["FORCE"] = False
    try:
        den = "2026-07-15"
        s = {}
        n1 = mark_failed(s, den, "overview_room9", "източникът падна")
        ck("провалът НЕ пише готов", done_today(s, den, "overview_room9") is False)
        ck("провалът пише изричен НЕ, не липсващ ключ",
           s.get("overview_room9") is False)
        ck("броячът на опитите тръгва от 1", n1 == 1)
        n2 = mark_failed(s, den, "overview_room9", "пак падна")
        n3 = mark_failed(s, den, "overview_room9", "и трети път")
        ck("броячът расте", (n2, n3) == (2, 3))
        ck("причината се пази", "трети" in str(s.get("overview_room9_prichina")))
        ck("провалът стига до диска",
           load_state().get("overview_room9_opiti") == 3)
        mark_done(s, den, "overview_room9")
        ck("успехът след провал пише готов",
           done_today(s, den, "overview_room9") is True)
        ck("успехът маха причината", "overview_room9_prichina" not in s)

        s2 = {}
        mark_failed(s2, "2026-07-15", "overview_room9", "падна")
        mark_failed(s2, "2026-07-16", "overview_room9", "падна пак")
        ck("пропуснатият ден оцелява смяната на деня",
           "2026-07-15" in (s2.get("propusnati") or []))
        ck("новият ден е записан", s2.get("date") == "2026-07-16")
        s3 = {}
        mark_done(s3, "2026-07-15", "overview_room9")
        mark_failed(s3, "2026-07-16", "overview_room9", "падна")
        ck("успелият ден НЕ влиза в пропуснатите",
           "2026-07-15" not in (s3.get("propusnati") or []))
        # Наваксване: ден, който вече стои в списъка на пропуснатите, трябва да
        # излезе оттам, щом бъде свършен — и то САМО той, не целият списък.
        s4 = {"date": "2026-07-16",
              "propusnati": ["2026-07-14", "2026-07-15", "2026-07-16"]}
        mark_done(s4, "2026-07-16", "overview_room9")
        ck("навакcаният ден си тръгва от пропуснатите",
           "2026-07-16" not in (s4.get("propusnati") or []))
        ck("другите пропуснати дни остават",
           (s4.get("propusnati") or []) == ["2026-07-14", "2026-07-15"])
        s5 = {"date": "2026-07-16", "propusnati": ["2026-07-16"]}
        mark_done(s5, "2026-07-16", "overview_room9")
        ck("празният списък се маха, не остава празен",
           "propusnati" not in s5)

        # ───────────────────── run_overview: четирите изхода
        sega = datetime(2026, 7, 15, 20, 0, tzinfo=SOFIA)
        sent = []
        poster.send_message = lambda *a, **k: (sent.append(1) or True)
        time.sleep = lambda *a, **k: None

        def _izchisti():
            try:
                os.remove(tmp)
            except Exception:                                # noqa: BLE001
                pass

        _izchisti()
        globals()["collect_overview"] = lambda now: {
            "total": 0, "nsports": 0, "hot": None, "tomorrow": None,
            "zayavki": 10, "greshki": 10, "prichini": ["нарочен провал"]}
        run_overview(sega)
        st = load_state()
        ck("паднал източник НЕ пише готов", st.get("overview_room9") is False)
        ck("паднал източник вдига брояча", st.get("overview_room9_opiti") == 1)
        ck("паднал източник не праща нищо", len(sent) == 0)
        ck("причината стига до състоянието",
           "падна" in str(st.get("overview_room9_prichina")))

        _izchisti()
        globals()["collect_overview"] = lambda now: {
            "total": 40, "nsports": 5, "hot": None, "tomorrow": None,
            "zayavki": 10, "greshki": 0, "prichini": []}
        run_overview(sega)
        st = load_state()
        ck("здравото мълчание пише готов", st.get("overview_room9") is True)
        ck("здравото мълчание не праща нищо", len(sent) == 0)

        _izchisti()
        poster.send_message = lambda *a, **k: False
        globals()["collect_overview"] = lambda now: {
            "total": 40, "nsports": 5, "hot": None,
            "tomorrow": "🏀 В — Г (21:00)",
            "zayavki": 10, "greshki": 0, "prichini": []}
        run_overview(sega)
        st = load_state()
        ck("отказан пост НЕ пише готов", st.get("overview_room9") is False)
        ck("отказан пост вдига брояча", st.get("overview_room9_opiti") == 1)

        _izchisti()
        sent2 = []
        poster.send_message = lambda *a, **k: (sent2.append(1) or True)
        run_overview(sega)
        st = load_state()
        ck("приетият пост пише готов", st.get("overview_room9") is True)
        ck("приетият пост е точно един", len(sent2) == 1)

        # ───────────── collect_overview: денят на източника не е нашият ден
        globals()["collect_overview"] = star_collect

        def _zima(url, timeout=20, greshki=None):
            if "d=2026-01-16" in url and "Soccer" in url:
                return {"events": [
                    {"strLeague": "Premier League", "strHomeTeam": "Късен",
                     "strAwayTeam": "Мач", "dateEvent": "2026-01-16",
                     "strTime": "23:30:00"},
                    {"strLeague": "Premier League", "strHomeTeam": "Точният",
                     "strAwayTeam": "Мач", "dateEvent": "2026-01-16",
                     "strTime": "18:00:00"}]}
            return {"events": []}

        globals()["fetch_json"] = _zima
        dz = collect_overview(datetime(2026, 1, 15, 20, 0, tzinfo=SOFIA))
        ck("зимата: 18:00 UTC се показва като 20:00",
           "(20:00)" in str(dz.get("tomorrow")))
        ck("суровият UTC час не изтича навън",
           "(18:00)" not in str(dz.get("tomorrow")))
        ck("мачът след полунощ НЕ се обявява за утрешен",
           "Късен" not in str(dz.get("tomorrow")))
        ck("броят заявки се връща", int(dz.get("zayavki") or 0) > 0)
        ck("здравият източник дава 0 провала", int(dz.get("greshki") or 0) == 0)

        def _lyato(url, timeout=20, greshki=None):
            if "d=2026-07-15" in url and "Soccer" in url:
                return {"events": [
                    {"strLeague": "Premier League", "strHomeTeam": "Полунощен",
                     "strAwayTeam": "Мач", "dateEvent": "2026-07-15",
                     "strTime": "22:30:00"}]}
            return {"events": []}

        globals()["fetch_json"] = _lyato
        dl = collect_overview(datetime(2026, 7, 15, 20, 0, tzinfo=SOFIA))
        ck("лятото: 22:30 UTC днес е 01:30 бг утре",
           "(01:30)" in str(dl.get("tomorrow")))
        ck("мачът от ДНЕШНИЯ кош на източника се хваща",
           "Полунощен" in str(dl.get("tomorrow")))

        def _padnal(url, timeout=20, greshki=None):
            if greshki is not None:
                greshki.append("нарочен провал")
            return {}

        globals()["fetch_json"] = _padnal
        dp = collect_overview(datetime(2026, 7, 15, 20, 0, tzinfo=SOFIA))
        ck("всяка пропаднала заявка се брои",
           int(dp.get("greshki") or 0) == int(dp.get("zayavki") or 0) > 0)
        ck("паднал източник не ражда мач за утре", dp.get("tomorrow") is None)

        # ───────────── самият fetch_json, без мрежа
        globals()["fetch_json"] = star_fetch
        g1 = []
        ck("счупен адрес връща празно",
           fetch_json("tova-ne-e-adres", greshki=g1) == {})
        ck("счупеният адрес оставя следа", len(g1) == 1)
        g2 = []
        ck("отговор с чужд тип НЕ е празен ден",
           fetch_json("data:application/json,[1,2,3]", greshki=g2) == {})
        ck("чуждият тип също оставя следа", len(g2) == 1)
        g3 = []
        ck("здравият отговор минава",
           fetch_json("data:application/json," + chr(123) + chr(34) + "events"
                      + chr(34) + ":[]" + chr(125), greshki=g3) == {"events": []})
        ck("здравият отговор не оставя следа", len(g3) == 0)
    finally:
        globals()["STATE_FILE"] = star_file
        globals()["FORCE"] = star_force
        globals()["collect_overview"] = star_collect
        globals()["fetch_json"] = star_fetch
        poster.send_message = real_send
        time.sleep = real_sleep
        _sh.rmtree(papka, ignore_errors=True)


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

    _proveri_ligi(check)
    _proveri_chasa(check, src)
    _proveri_sastoyanieto(check)
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
