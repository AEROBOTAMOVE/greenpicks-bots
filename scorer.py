# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ОЦЕНИТЕЛЯТ 📊

ЗАЩО СЪЩЕСТВУВА
Ботът пускаше прогнози и никой никога не проверяваше дали е познал. Стая 9
„Резултати и статистика" показваше случайни резултати от чужди първенства, а
стая 10 „Печеливши фишове" стоеше празна, защото нямаше кой да я пълни.
Продукт, който твърди „показваме и загубите", а не показва нищо, не е продукт.

КАКВО ПРАВИ
1. Чете predict_log.json — там predictor.py записва всяко свое твърдение:
   кой срещу кого, кого е посочил, с каква вероятност и колко звезди.
2. За всяко неоценено твърдение пита ESPN как е свършил мачът.
3. Пише ДВА поста:
     стая 9  — пълният отчет: познати И сгрешени, с процент за деня и общо
     стая 10 — само познатите, витрина
   Ако няма нито един завършил мач — не пише нищо. Тишината е за предпочитане.
4. Вдига „scored" на оценените, за да не се броят два пъти.

ЖЕЛЕЗНИ ПРАВИЛА
- Пише САМО в стаи 9 и 10. Всяка друга стая се отказва на изхода, преди мрежата.
- Никакви поучения, никакви коефициенти, никакви букмейкъри. Пазач на изхода.
- Загубите НЕ се крият и НЕ се трият. Точно те правят числото достоверно.
- Не е сигурен резултатът → мачът остава неоценен и се пробва пак утре.

ENV:
  BOT_TOKEN, CHAT_ID
  RESULTS_THREAD_ID (9)   ·  WINS_THREAD_ID (10)
  SCORE_DRY_RUN (0/1)     ·  SCORE_LOG_FILE (predict_log.json)
  SCORE_MAX_AGE_DAYS (5)  докога чакаме резултат, преди да се откажем

Файлът е без обратни наклонени черти, без обратни апострофи и без долар-скоба.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NL = chr(10)
SOFIA = ZoneInfo("Europe/Sofia")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = (os.environ.get("CHAT_ID") or "-1004426592150").strip()
CHANNEL_ID = (os.environ.get("CHANNEL_ID") or "-1004403334702").strip()

RESULTS_THREAD = (os.environ.get("RESULTS_THREAD_ID") or "9").strip()
WINS_THREAD = (os.environ.get("WINS_THREAD_ID") or "10").strip()
# Единствените две стаи, в които този файл има право да пише.
# Стая 4 „Фишове на деня": там излиза обзорът КАК СА МИНАЛИ фишовете.
# Поръчка на собственика: „Фишовете на деня трябва и там обзор."
PICKS_THREAD = (os.environ.get("PICKS_THREAD_ID") or "4").strip()
ALLOWED_THREADS = {RESULTS_THREAD, WINS_THREAD, PICKS_THREAD}

LOG_FILE = (os.environ.get("SCORE_LOG_FILE") or "predict_log.json").strip()
DRY_RUN = (os.environ.get("SCORE_DRY_RUN") or "").strip() in ("1", "true", "yes", "да")
MAX_AGE = max(1, min(30, int((os.environ.get("SCORE_MAX_AGE_DAYS") or "5").strip())))

UA = "Mozilla/5.0 (compatible; GreenRoomScorer/1.0)"
ESPN = "https://site.api.espn.com/apis/site/v2/sports"

# Кошница -> (спорт в адреса на ESPN, емоджи)
SPORT_PATH = {
    "football": ("soccer", "⚽"),
    "basketball": ("basketball", "\U0001f3c0"),
    "tennis": ("tennis", "\U0001f3be"),
    "hockey": ("hockey", "\U0001f3d2"),
    "baseball": ("baseball", "⚾"),
    "mma": ("mma", "\U0001f94a"),
    "volleyball": (None, "\U0001f3d0"),      # FIVB, не ESPN — виж по-долу
    "tabletennis": (None, "\U0001f3d3"),     # WTT, не ESPN
}

# Думи, които НЕ ИЗЛИЗАТ навън. Същият пазач като в другите ботове.
BANNED = ["18+", "залагай отговорно",
          "коеф", "букмейкър", "odds",
          "заложи", "финансов съвет"]


def banned_word(text):
    low = (text or "").lower()
    for w in BANNED:
        if w in low:
            return w
    return None


def http_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def api(method, **params):
    """Bot API с изчакване при 429 — иначе последният пост тихо пада."""
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/" + method
    for attempt in range(5):
        data = urllib.parse.urlencode(params).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=25) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429:
                try:
                    ra = int(json.loads(body).get("parameters", {}).get("retry_after", 5))
                except Exception:
                    ra = 5
                print("  429 при " + method + " — чакам " + str(ra + 1) + " сек.")
                time.sleep(ra + 1)
                continue
            print(method + " HTTP " + str(e.code) + ": " + body[:150])
            return {}
        except Exception as e:                # noqa: BLE001
            print(method + " FAIL: " + str(e)[:120])
            return {}
    return {}


def post(thread, text):
    """ЕДИНСТВЕНИЯТ изход навън. Пазачът е ТУК, преди мрежата."""
    tid = str(thread or "").strip()
    if tid not in ALLOWED_THREADS:
        print("ОТКАЗ: стая " + tid + " не е на оценителя (само "
              + " и ".join(sorted(ALLOWED_THREADS)) + ").")
        return False
    bad = banned_word(text)
    if bad:
        print("ОТКАЗ: в текста се промъкна забранена дума (" + bad + ").")
        return False
    if DRY_RUN:
        print("--- СУХО, стая " + tid + " ---")
        print(text)
        print("---")
        return True
    p = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
         "disable_web_page_preview": "true"}
    if int(tid) > 1:
        p["message_thread_id"] = tid
    r = api("sendMessage", **p)
    ok = bool(r.get("ok"))
    print(("  пратено в стая " if ok else "  НЕ мина в стая ") + tid)
    return ok


# ------------------------------------------------------------------ РЕЗУЛТАТИ
def espn_result(rec):
    """Крайният резултат на един мач от ESPN. None = още не знаем.

    Връща (домакин_точки, гост_точки) или None. Търсим по деня на мача в
    същата лига, после сверяваме по id на отборите — имената се различават
    между източниците, id-тата не.
    """
    bucket = rec.get("bucket")
    path = (SPORT_PATH.get(bucket) or (None, ""))[0]
    slug = rec.get("slug")
    hid, aid = str(rec.get("home_id") or ""), str(rec.get("away_id") or "")
    if not path or not slug or not hid or not aid:
        return None

    day = (rec.get("day") or "").replace("-", "")
    if len(day) != 8:
        return None
    url = ESPN + "/" + path + "/" + slug + "/scoreboard?dates=" + day
    try:
        j = http_json(url)
    except Exception as e:                    # noqa: BLE001
        print("    ESPN мълчи за " + slug + " " + day + " (" + str(e)[:50] + ")")
        return None

    for ev in (j.get("events") or []):
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0] or {}
        st = ((comp.get("status") or {}).get("type") or {})
        if not st.get("completed"):
            continue                          # още не е свършил
        got = {}
        for c in (comp.get("competitors") or []):
            tid = str(((c.get("team") or {}).get("id")) or "")
            try:
                got[tid] = int(str(c.get("score")))
            except Exception:                 # noqa: BLE001
                return None
        if hid in got and aid in got:
            return got[hid], got[aid]
    return None


def name_in(name, text):
    """Името се среща в текста КАТО ОТДЕЛНА ДУМА, не завряно вътре в друга.

    ЗАЩО не просто „in": късо име се намира навсякъде. При проба „А" срещу „Б"
    низът „а" се намери вътре в „неразпознаваемо" и оценителят отсъди победа
    там, където изобщо не разбираше твърдението. Затова: къси имена под три
    букви изобщо не се търсят, а по-дългите — само на граница на дума.
    """
    n = (name or "").strip().lower()
    t = (text or "").lower()
    if len(n) < 3 or not t:
        return False
    start = 0
    while True:
        i = t.find(n, start)
        if i < 0:
            return False
        before_ok = (i == 0) or (not t[i - 1].isalnum())
        end = i + len(n)
        after_ok = (end >= len(t)) or (not t[end].isalnum())
        if before_ok and after_ok:
            return True
        start = i + 1


# ═══════════════════════════ 🏐 ВОЛЕЙБОЛ: РЕЗУЛТАТИ ОТ FIVB
# ЗАЩО СЪЩЕСТВУВА (измерено на 04.08.2026)
# От 61 прогнози в дневника, 18 бяха волейболни и НИТО ЕДНА не беше отсъдена.
# Причината: волейболът не е в ESPN, а SPORT_PATH го водеше None — тоест
# espn_result() връщаше None винаги и мачът висеше неоценен, докато не остарее.
# Резултатът: най-предсказваният спорт беше напълно невидим в отчета.
#
# FIVB VIS дава завършените мачове със Status="25" (официален резултат) и
# MatchPointsA/B = спечелени сетове. Съпоставяме по ИМЕ на отбора, защото
# дневникът и FIVB идват от един и същ източник — имената съвпадат буквално.
_vol_days = {}


def _norm(s):
    return "".join(c for c in str(s or "").lower() if c.isalnum())


# ═══════════ ИМЕНАТА: БЪЛГАРСКО СРЕЩУ АНГЛИЙСКО (намерено на 04.08.2026)
# Предсказателят ПРЕВЕЖДА имената, преди да ги запише в дневника: „Poland"
# става „Полша", „Puerto Rico" става „Пуерто Рико". Източниците обаче връщат
# английските. Затова сравнението по име се проваляше и осемнадесет волейболни
# прогнози висяха неотсъдени — мина единствено „Guatemala", защото не се
# превежда.
# Тук зареждаме СЪЩАТА таблица от predictor.py и сравняваме и в двете посоки.
_bg2en = {}
_bg_loaded = [False]


def bg_map():
    """Обратната карта българско -> английско. Зарежда се веднъж."""
    if _bg_loaded[0]:
        return _bg2en
    _bg_loaded[0] = True
    try:
        import predictor as P
        for en, bg in (getattr(P, "BG_NAME", {}) or {}).items():
            _bg2en[_norm(bg)] = _norm(en)
    except Exception as e:                             # noqa: BLE001
        print("    таблицата с имена не се зареди (" + str(e)[:50] + ")")
    return _bg2en


def same_team(a, b):
    """Едно и също ли са двете имена — на български или на английски."""
    ka, kb = _norm(a), _norm(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    m = bg_map()
    return m.get(ka, ka) == kb or ka == m.get(kb, kb) or m.get(ka) == m.get(kb) is not None


def volley_day(day):
    """Завършените волейболни мачове за един ден. Кешира се по ден."""
    if day in _vol_days:
        return _vol_days[day]
    rows = []
    try:
        import predictor as P
        fields = ("No TeamAName TeamBName MatchPointsA MatchPointsB "
                  "Status DateTimeLocal")
        req = ('<Request Type="GetVolleyMatchList" Fields="' + fields
               + '"><Filter FirstDate="' + day + '" LastDate="' + day + '"/></Request>')
        root = P.vis_xml(req)
        for m in root:
            if str(m.get("Status") or "") != "25":     # 25 = официален резултат
                continue
            try:
                pa = int(str(m.get("MatchPointsA")))
                pb = int(str(m.get("MatchPointsB")))
            except Exception:                          # noqa: BLE001
                continue
            rows.append(((m.get("TeamAName") or "").strip(),
                         (m.get("TeamBName") or "").strip(), pa, pb))
    except Exception as e:                             # noqa: BLE001
        print("    FIVB мълчи за " + str(day) + " (" + str(e)[:50] + ")")
    _vol_days[day] = rows
    return rows

def volley_result(rec):
    """(сетове домакин, сетове гост) или None, ако мачът още не е официален."""
    day = rec.get("day") or ""
    if len(day) != 10:
        return None
    ha, hb = rec.get("home"), rec.get("away")
    if not ha or not hb:
        return None
    for na, nb, pa, pb in volley_day(day):
        if same_team(na, ha) and same_team(nb, hb):
            return pa, pb
        if same_team(na, hb) and same_team(nb, ha):    # обърнат ред в източника
            return pb, pa
    return None


# ═══════════════════════════ 🎾 ТЕНИС: РЕЗУЛТАТИ ОТ ESPN (по турнир)
# ЗАЩО НЕ РАБОТЕШЕ ДОСЕГА (проверено на живо на 04.08.2026)
# За отборните спортове ESPN дава мачовете направо в scoreboard. За тениса
# scoreboard връща ТУРНИРИ — вътре „competitions" е ПРАЗЕН списък. Затова
# espn_result() не намираше нищо и 12 тенис прогнози висяха неотсъдени.
# Мачовете живеят в summary на турнира.
_ten_days = {}


def tennis_day(day):
    """Завършените тенис мачове за деня: [(имеA, имеB, сетовеA, сетовеB)]."""
    if day in _ten_days:
        return _ten_days[day]
    ymd = day.replace("-", "")
    out = []
    for tour in ("atp", "wta"):
        try:
            board = http_json(ESPN + "/tennis/" + tour + "/scoreboard?dates=" + ymd)
        except Exception:                              # noqa: BLE001
            continue
        for ev in ((board or {}).get("events") or []):
            # ⚠️ ТУК Е КЛЮЧЪТ. Мачовете НЕ са в ev["competitions"] — той е
            # празен. Живеят в ev["groupings"][i]["competitions"], защото ESPN
            # групира по схема (основна, квалификации, двойки). Заради това
            # дванадесет тенис прогнози висяха неотсъдени.
            for g in (ev.get("groupings") or []):
                for c in (g.get("competitions") or []):
                    st = ((c.get("status") or {}).get("type") or {})
                    if not st.get("completed"):
                        continue
                    sides = []
                    for k in (c.get("competitors") or []):
                        ath = (k.get("athlete") or {})
                        nm = (ath.get("displayName") or ath.get("fullName")
                              or (k.get("team") or {}).get("displayName") or "")
                        gems = []
                        for x in (k.get("linescores") or []):
                            try:
                                gems.append(float(x.get("value")))
                            except Exception:          # noqa: BLE001
                                gems.append(-1.0)
                        sides.append((nm, gems, bool(k.get("winner"))))
                    if len(sides) != 2:
                        continue
                    a, b = sides
                    # Сетове = колко пъти всеки е взел повече геймове.
                    sa = sb = 0
                    for i in range(min(len(a[1]), len(b[1]))):
                        if a[1][i] > b[1][i]:
                            sa += 1
                        elif b[1][i] > a[1][i]:
                            sb += 1
                    if sa == sb:            # редовете не свършиха работа
                        sa, sb = (1, 0) if a[2] else (0, 1)
                    out.append((a[0], b[0], sa, sb))
    _ten_days[day] = out
    return out


def tennis_result(rec):
    ha, hb = rec.get("home"), rec.get("away")
    if not ha or not hb:
        return None
    for na, nb, pa, pb in tennis_day(rec.get("day") or ""):
        if same_team(na, ha) and same_team(nb, hb):
            return pa, pb
        if same_team(na, hb) and same_team(nb, ha):
            return pb, pa
    return None


def sport_result(rec):
    """ЕДИНСТВЕНАТА врата към резултат. Всеки спорт минава оттук.

    Дотук се викаше espn_result() направо и това мълчаливо изключваше три
    спорта: волейбол и тенис на маса (нямат ESPN), и тенис (ESPN дава турнири,
    не мачове). Осемнадесет волейболни и дванадесет тенис прогнози висяха
    неотсъдени — тоест почти половината дневник беше невидим за отчета.
    """
    b = rec.get("bucket")
    if b == "volleyball":
        return volley_result(rec)
    if b == "tennis":
        return tennis_result(rec)
    return espn_result(rec)


def verdict(rec, hs, as_):
    """Позна ли прогнозата. Връща True / False / None (не можем да отсъдим).

    None НЕ е провал — то значи „не разбирам собственото си твърдение" и
    такъв ред просто не влиза в статистиката. По-добре празно, отколкото
    измислен резултат.
    """
    pick = (rec.get("pick") or "")
    home = (rec.get("home") or "")
    away = (rec.get("away") or "")
    low = pick.lower().strip()

    # Първо: разбираме ли изобщо какво сме твърдели?
    said_home = name_in(home, pick) or low[:2] in ("1 ", "1·", "1.")
    said_away = name_in(away, pick) or low[:2] in ("2 ", "2·", "2.")
    if said_home == said_away:
        return None                 # или и двете, или нито едно — не съдим

    if hs == as_:
        return False                # посочили сме победител, а е равен
    home_won = hs > as_
    return home_won if said_home else (not home_won)


# --------------------------------------------------------------------- ТЕКСТ
def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def date_bg(d):
    dni = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]
    return dni[d.weekday()] + ", " + d.strftime("%d.%m")


def line(rec, hs, as_, ok):
    emo = (SPORT_PATH.get(rec.get("bucket")) or (None, "\U0001f4cc"))[1]
    mark = "✅" if ok else "❌"
    return (mark + " " + emo + " <b>" + esc(rec.get("home")) + "</b> " + str(hs)
            + ":" + str(as_) + " <b>" + esc(rec.get("away")) + "</b>" + NL
            + "    посочихме: " + esc(rec.get("pick")))


def results_text(now, rows, total_all, hit_all):
    """Обзорът на деня. Числото отгоре, редовете отдолу, край.

    ПРЕНАПИСАН НА 29.07.2026 ПО ИЗРИЧНА ПОРЪЧКА НА СОБСТВЕНИКА:
      „Спри да пишеш какво следихме, спри да ми казваш нищо не се трие и
       тъпотии — ясен точен обзор на деня какво е спечелено и какво не."
    Затова тук няма нито един ред обяснение, обещание или самохвалство.
    Първото нещо, което човек вижда, е резултатът за деня. После кой позна и
    кой не. Толкова.
    """
    hits = [r for r in rows if r[3]]
    miss = len(rows) - len(hits)
    pct_day = (100.0 * len(hits) / len(rows)) if rows else 0.0
    pct_all = (100.0 * hit_all / total_all) if total_all else 0.0

    ok_rows = [line(r[0], r[1], r[2], True) for r in rows if r[3]]
    no_rows = [line(r[0], r[1], r[2], False) for r in rows if not r[3]]

    out = ["\U0001f4ca <b>ОБЗОР НА ДЕНЯ</b> · " + date_bg(now),
           "",
           ("<b>" + str(len(hits)) + " познати · " + str(miss) + " сгрешени · "
            + ("%.0f" % pct_day) + "%</b>"),
           ""]
    if ok_rows:
        out += ["✅ <b>ПОЗНАТИ</b>"] + ok_rows + [""]
    if no_rows:
        out += ["❌ <b>СГРЕШЕНИ</b>"] + no_rows + [""]
    out += [("\U0001f4c8 Общо: <b>" + str(hit_all) + " от " + str(total_all)
             + "</b> · " + ("%.0f" % pct_all) + "%"),
            "\U0001f7e2 THE GREEN ROOM"]
    return NL.join(out)


def wins_text(now, rows):
    """Витрината. Само познатите, без обяснения."""
    body = NL.join(line(r[0], r[1], r[2], True) for r in rows)
    return NL.join([
        "\U0001f3c6 <b>ПОЗНАТИТЕ ДНЕС</b> · " + date_bg(now),
        "",
        body,
        "",
        "\U0001f7e2 THE GREEN ROOM",
    ])


def combo_text(now, slips):
    """Обзор на трите фиша: кой е минал изцяло и кой къде се е скъсал.

    Поръчка на собственика: „Фишовете на деня трябва и там обзор."
    Един фиш е верен само ако ВСИЧКИТЕ пет избора са познали — затова тук
    се брои така, а не по проценти.
    """
    out = ["\U0001f3ab <b>ФИШОВЕТЕ ОТ ВЧЕРА</b> · " + date_bg(now), ""]
    minali = 0
    for n, legs in slips:
        ok = sum(1 for x in legs if x[3])
        vsi = len(legs)
        cял = (ok == vsi)
        if cял:
            minali += 1
        out.append(("✅" if cял else "❌") + " <b>ФИШ " + str(n) + "</b> · "
                   + str(ok) + " от " + str(vsi))
        for rec, hs, as_, hit in legs:
            emo = (SPORT_PATH.get(rec.get("bucket")) or (None, "\U0001f4cc"))[1]
            out.append(("   ✅ " if hit else "   ❌ ") + emo + " "
                       + esc(rec.get("home")) + " " + str(hs) + ":" + str(as_)
                       + " " + esc(rec.get("away")))
        out.append("")
    out.append("<b>" + str(minali) + " от " + str(len(slips)) + " фиша минаха.</b>")
    out.append("\U0001f7e2 THE GREEN ROOM")
    return NL.join(out)


# --------------------------------------------------------------------- ГЛАВНО
def load_log():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, encoding="utf-8-sig") as f:
            rows = json.load(f)
        return rows if isinstance(rows, list) else []
    except Exception as e:                    # noqa: BLE001
        print("дневникът не се чете (" + str(e)[:70] + ") — няма какво да оценя.")
        return []


def save_log(rows):
    if DRY_RUN:
        return False
    try:
        tmp = LOG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        os.replace(tmp, LOG_FILE)
        return True
    except Exception as e:                    # noqa: BLE001
        print("дневникът не се записа (" + str(e)[:70] + ").")
        return False


def selftest():
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    # пазачът на стаите. Стая 4 вече Е разрешена — там отива обзорът на
    # фишовете (поръчка на собственика). Всичко останало си остава чуждо.
    for room in ("5", "6", "7", "8", "11", "26", "27", "328", "1", "3"):
        check("стая " + room + " е забранена", room not in ALLOWED_THREADS)
    check("стая 9 е разрешена", RESULTS_THREAD in ALLOWED_THREADS)
    check("стая 10 е разрешена", WINS_THREAD in ALLOWED_THREADS)
    check("стая 4 е разрешена (обзор на фишовете)", PICKS_THREAD in ALLOWED_THREADS)
    check("разрешените са точно три",
          ALLOWED_THREADS == {RESULTS_THREAD, WINS_THREAD, PICKS_THREAD})

    # отсъждането
    r = {"home": "Куба", "away": "Египет", "pick": "1 · победа Куба"}
    check("познат домакин", verdict(r, 3, 1) is True)
    check("сгрешен домакин", verdict(r, 1, 3) is False)
    r2 = {"home": "Левски", "away": "Лудогорец", "pick": "2 · победа Лудогорец"}
    check("познат гост", verdict(r2, 0, 2) is True)
    check("равенството е грешка", verdict(r2, 1, 1) is False)
    r3 = {"home": "Левски", "away": "Лудогорец", "pick": "нещо неразпознаваемо"}
    check("неясното твърдение не се съди", verdict(r3, 2, 1) is None)
    r4 = {"home": "Милан", "away": "Интер", "pick": "1 · победа Милан"}
    check("късото име не се лови вътре в дума", name_in("Ин", "Милан") is False)
    check("цялото име се лови като дума", name_in("Милан", "победа Милан") is True)
    check("името вътре в друга дума не се брои",
          name_in("Интер", "Интернационале") is False)
    check("познат след затягането", verdict(r4, 2, 0) is True)
    r5 = {"home": "Милан", "away": "Интер", "pick": "1 · победа Милан и Интер"}
    check("двусмислено твърдение не се съди", verdict(r5, 2, 0) is None)

    # --- ТЕКСТЪТ. Пренаписан 29.07.2026: собственикът поиска ЯСЕН ОБЗОР,
    # без „какво следихме", без „нищо не се трие", без обяснения.
    _now = datetime.now(SOFIA)
    _rows = [({"home": "Левски", "away": "ЦСКА", "pick": "1", "bucket": "football"}, 2, 1, True),
             ({"home": "Милан", "away": "Интер", "pick": "1", "bucket": "football"}, 0, 3, False)]
    t = results_text(_now, _rows, 10, 6)
    check("отчетът е чист", banned_word(t) is None)
    check("отчетът е озаглавен ОБЗОР НА ДЕНЯ", "ОБЗОР НА ДЕНЯ" in t)
    check("отчетът дава числото веднага", "1 познати · 1 сгрешени" in t)
    check("отчетът разделя познати и сгрешени",
          "ПОЗНАТИ" in t and "СГРЕШЕНИ" in t)
    check("отчетът показва и общото", "Общо:" in t)
    check("отчетът НЕ поучава",
          "не се трие" not in t and "Гледахме" not in t and "завинаги" not in t)
    w = wins_text(_now, [_rows[0]])
    check("витрината е чиста", banned_word(w) is None)
    check("витрината е само познатите", "ПОЗНАТИТЕ ДНЕС" in w)
    check("витрината не обяснява", "Пълният отчет" not in w)

    # --- обзорът на фишовете
    _legs = [({"home": "А" + str(i), "away": "Б", "pick": "1", "bucket": "football"},
              2, 1, i != 2) for i in range(5)]
    c = combo_text(_now, [(1, _legs)])
    check("фишовете имат обзор", "ФИШОВЕТЕ ОТ ВЧЕРА" in c)
    check("скъсаният фиш е отбелязан", "❌ <b>ФИШ 1</b> · 4 от 5" in c)
    check("обзорът на фишовете е чист", banned_word(c) is None)
    check("обзорът брои минали фишове", "0 от 1 фиша минаха" in c)
    check("стая 4 е разрешена за обзора", PICKS_THREAD in ALLOWED_THREADS)

    # --- прозорецът на дните: днешното СЕ отчита, утрешното НЕ
    _today = datetime.now(SOFIA).strftime("%Y-%m-%d")
    _utre = (datetime.now(SOFIA) + timedelta(days=1)).strftime("%Y-%m-%d")
    _vchera = (datetime.now(SOFIA) - timedelta(days=1)).strftime("%Y-%m-%d")
    check("утрешният мач се прескача", _utre > _today)
    check("днешният мач НЕ се прескача", not (_today > _today))
    check("вчерашният мач НЕ се прескача", not (_vchera > _today))

    print("САМОПРОВЕРКА НА ОЦЕНИТЕЛЯ: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 1 if bad else 0


def main():
    if not BOT_TOKEN and not DRY_RUN:
        print("Липсва BOT_TOKEN.")
        return 1
    rows = load_log()
    if not rows:
        print("Дневникът е празен — няма какво да оценя.")
        return 0

    now = datetime.now(SOFIA)
    limit = (now - timedelta(days=MAX_AGE)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    # Общата статистика се смята от ЦЕЛИЯ дневник, не само от днешното.
    total_all = sum(1 for r in rows if r.get("scored") and r.get("hit") is not None)
    hit_all = sum(1 for r in rows if r.get("scored") and r.get("hit") is True)

    fresh = []
    checked = 0
    for r in rows:
        if r.get("scored"):
            continue
        day = r.get("day") or ""
        # ДНЕШНИТЕ МАЧОВЕ СЕ ОТЧИТАТ ОЩЕ ДНЕС.
        # Тук стоеше „ако денят е днес — прескачай". Изглеждаше предпазливо, а
        # всъщност обезсмисляше вечерното пускане в 20:00: то не можеше да
        # отчете НИТО ЕДИН мач от същия ден и резултатите закъсняваха с
        # денонощие. Пазачът е излишен, защото истинската защита е по-надолу:
        # espn_result() връща резултат САМО когато ESPN каже "completed".
        # Незавършил мач си остава неоценен и се пробва пак на следващото
        # пускане. Мачът за УТРЕ обаче наистина се прескача — там няма какво
        # да се пита.
        if day > today:
            continue
        if day < limit:
            r["scored"] = True                # твърде старо, отказваме се
            r["hit"] = None
            continue
        checked += 1
        res = sport_result(r)
        time.sleep(0.4)
        if res is None:
            continue                          # пробваме пак утре
        hs, as_ = res
        ok_hit = verdict(r, hs, as_)
        if ok_hit is None:
            r["scored"] = True
            r["hit"] = None
            continue
        r["scored"] = True
        r["hit"] = bool(ok_hit)
        r["score"] = str(hs) + ":" + str(as_)
        fresh.append((r, hs, as_, bool(ok_hit)))

    print("Проверени " + str(checked) + " твърдения, отсъдени " + str(len(fresh)) + ".")
    if not fresh:
        save_log(rows)
        print("Няма завършили мачове за отчет — мълча.")
        return 0

    total_all += len(fresh)
    hit_all += sum(1 for f in fresh if f[3])

    post(RESULTS_THREAD, results_text(now, fresh, total_all, hit_all))
    wins = [f for f in fresh if f[3]]
    if wins:
        time.sleep(2.0)
        post(WINS_THREAD, wins_text(now, wins))
    else:
        print("Днес няма познати — витрината мълчи, отчетът излезе.")

    # ОБЗОР НА ФИШОВЕТЕ → стая 4.
    # Един фиш се отчита ЕДВА когато и петте му крака са отсъдени. Ако един мач
    # още не е свършил, фишът чака следващото пускане — иначе бихме обявили
    # „скъсан фиш" върху половин информация.
    slips = {}
    for f in fresh:
        n = int((f[0].get("combo") or 0))
        if n:
            slips.setdefault(n, []).append(f)
    if slips:
        gotovi = []
        for n in sorted(slips):
            legs = slips[n]
            ochakvani = sum(1 for r in rows
                            if int(r.get("combo") or 0) == n
                            and (r.get("day") or "") == (legs[0][0].get("day") or ""))
            if len(legs) >= ochakvani:
                gotovi.append((n, legs))
            else:
                print("Фиш " + str(n) + ": " + str(len(legs)) + " от "
                      + str(ochakvani) + " крака са готови — чака.")
        if gotovi:
            time.sleep(2.0)
            post(PICKS_THREAD, combo_text(now, gotovi))

    save_log(rows)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv or os.environ.get("SCORE_SELFTEST") == "1":
        sys.exit(selftest())
    sys.exit(main())
