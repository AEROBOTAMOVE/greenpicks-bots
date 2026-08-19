# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БУДИЛНИК ЗА ЗАТВОРЕНИТЕ СПОРТОВЕ 🔔

Един въпрос: КОГА тръгват хокеят и американският футбол, колко мача носят в
първата си седмица и колко от тях ще имат цена.

ЗАЩО СЪЩЕСТВУВА
`predictor.py` държи `PREDICT_IZKL="hockey,amfootball"` от 11.08.2026 по
изрична заповед на собственика — двата спорта дадоха 0 карти от 261 записа в
дневника и стаите им стояха празни. Пътят назад е една променлива.
Но НИКОЙ не помни да я върне, а „септември" не е дата.

Този файл е будилникът. Пуска се без нищо да пипа, гледа ИЗТОЧНИЦИТЕ (не
паметта) и казва с числа: тръгва на еди-коя си дата, толкова мача, толкова с
цена. Когато числото стане достатъчно голямо, собственикът маха ключалката.

КАКВО ИЗМЕРВА
  1. Първата дата с ИСТИНСКИ мач (предсезонните се режат — точно както ги
     реже predictor.py, със същата логика).
  2. Мачовете в първите 7 дни от старта.
  3. Колко от тях Pinnacle вече котира — през СЪЩИЯ модул pinnacle.py, който
     ползва самият predictor, тоест числото е това, което ботът ще получи.
  4. Двата дефекта, които ще ухапят точно на 29.09 — вж. по-долу.

🔴 ДЕФЕКТ 1 — hockey_fixtures не пази оригиналното име (измерено 19.08.2026)
   `predictor.hockey_fixtures` връща `"extra": {}`. Търсенето на цена в
   `predictor.py` (ред ~4501) чете `ex.get("home_en") or fx.get("home")` —
   тоест пада върху ВЕЧЕ ПРЕВЕДЕНОТО име.

🔴 ДЕФЕКТ 2 — „Rangers" -> „Рейнджърс" убива търсенето (измерено 19.08.2026)
   `BG_NAME` има „Rangers": „Рейнджърс" заради Глазгоу. НХЛ дава само прякора
   („Rangers", не „New York Rangers"), значи картата на футболния клуб хваща
   хокейния отбор. `pinnacle._norm` НЕ маха кирилица (`isalnum()` е вярно за
   българските букви), затова търсим „рейнджърс" в свят, който пише
   „New York Rangers" — и не намираме нищо.
   ИЗМЕРЕНО: 1 от 32 отбора в НХЛ. Малко, но е точно отборът, за когото
   пишат най-много.

  python sezon.py             — будилникът (иска мрежа)
  python sezon.py --zhivo     — същото, но с подробностите
  python sezon.py --selftest  — само проверките, БЕЗ мрежа
"""
import datetime
import gzip
import json
import sys
import urllib.request
import zlib

# --------------------------------------------------------------- НАСТРОЙКИ
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
NHL = "https://api-web.nhle.com/v1"
TIMEOUT = 30
SEDMICA = 7          # „първа седмица" значи 7 дни, старта включително
HORIZONT = 80        # докъде напред гледаме; НХЛ тръгва след ~6 седмици

# 🔴 ИМЕНАТА НА PINNACLE ЗА ДВАТА СПОРТА (измерено 19.08.2026 през /sports).
# `pinnacle.SPORT_ID` НЯМА нито хокей, нито американски футбол — защото са
# писани, докато двата спорта бяха затворени. Тук се ДОБАВЯТ по време на
# пускане (не се пипа чужд файл), а точният патч за pinnacle.py е в отчета.
#   15 = Football (американският) · 393 мача в момента
#   19 = Hockey                   ·  17 мача в момента
PIN_ID = {"amfootball": 15, "hockey": 19}

# 🔴 ЛИГИТЕ СЪЩЕСТВУВАТ, ПАЗАРЪТ ОЩЕ НЕ (измерено 19.08.2026 през
# /sports/{id}/leagues?all=true&brandId=0):
#   амер. футбол (15): NCAA 198 мача · NFL 174 · NFL Pre Season 16
#   хокей (19):        NHL 3 · NCAA 0 · AHL 0
# Тоест ключът за NCAA хокей ГО ИМА при тях — просто е празен през август.
# „0 с цена" днес значи „рано", а не „никога". Точно тази разлика ни ухапа с
# волейбола, където нулата беше вечна.

# Кой затворен спорт откъде се чете. Редът е редът на печатане.
# „vazhen" значи: тази стая е обещана на читателя и празна карта се вижда.
KALENDAR = [
    {"kod": "nfl", "ime": "🏈 НФЛ", "kosh": "amfootball",
     "izvor": ("espn", "football", "nfl"), "vazhen": True,
     "beleshka": "стая 1967 · predictor го знае вече (amfootball_fixtures)"},
    {"kod": "ncaaf", "ime": "🏈 NCAA амер. футбол", "kosh": "amfootball",
     "izvor": ("espn", "football", "college-football"), "vazhen": True,
     "beleshka": "същата стая · predictor го знае вече (AMF_LEAGUES)"},
    {"kod": "nhl", "ime": "🏒 НХЛ", "kosh": "hockey",
     "izvor": ("nhl", "", ""), "vazhen": True,
     "beleshka": "стая 1961 · predictor го знае вече (hockey_fixtures)"},
    {"kod": "ncaah", "ime": "🏒 NCAA хокей, мъже", "kosh": "hockey",
     "izvor": ("espn", "hockey", "mens-college-hockey"), "vazhen": False,
     "beleshka": "🔴 predictor НЯМА такъв източник — hockey_fixtures чете само НХЛ"},
    {"kod": "ncaahw", "ime": "🏒 NCAA хокей, жени", "kosh": "hockey",
     "izvor": ("espn", "hockey", "womens-college-hockey"), "vazhen": False,
     "beleshka": "🔴 predictor НЯМА такъв източник; и моделът иска таблица, каквато няма"},
]

_zayavki = [0]
_provali = [0]
_zashto = []


def broi_zayavki():
    """Колко заявки е направил ТОЗИ файл. Селфтестът иска да е нула."""
    return _zayavki[0]


def broi_provali():
    """Колко заявки са се провалили. Нула мачове + провал НЕ е „няма сезон"."""
    return _provali[0]


# 🔴 ДВАТА ИЗТОЧНИКА ИСКАТ ПРОТИВОПОЛОЖНИ ПОДПИСИ (измерено 19.08.2026,
# един и същ адрес, четири комбинации, една минута):
#
#   api-web.nhle.com  без подпис -> 403 · с Chrome подпис -> 200 (7 седмици)
#   site.api.espn.com без подпис -> 200 · с Chrome подпис -> 403
#
# Първата ми версия на този файл пращаше „без подпис" навсякъде, защото така
# се оправи ESPN на 11.08. Резултатът: будилникът каза „🏒 НХЛ няма нито един
# мач до 07.11", докато НХЛ тръгва на 29.09 с 43 мача. Тоест поправка за
# единия източник направи ВТОРИЯ ням — и то мълчаливо, с бодра зелена карта.
# `predictor.glavi_za` вече знае това; тук е повторено нарочно, за да не зависи
# будилникът от predictor.py.
BEZ_PODPIS = ("espn.com",)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def glavi_za(url):
    """Кои глави заминават с една заявка. Отделено, за да се тества само."""
    if any(h in str(url) for h in BEZ_PODPIS):
        return {"Accept": "application/json"}
    return {"User-Agent": UA, "Accept": "*/*"}


def _json(url):
    """Взима JSON или None. Нито един провал не бива да събори будилника."""
    _zayavki[0] += 1
    try:
        req = urllib.request.Request(url, headers=glavi_za(url))
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            raw = zlib.decompress(raw)
        return json.loads(raw.decode("utf-8-sig", "replace"))
    except Exception as e:                                   # noqa: BLE001
        _provali[0] += 1
        if len(_zashto) < 6:
            _zashto.append(str(url)[:60] + " -> " + str(e)[:40])
        return None


# ------------------------------------------------------------------ ФИЛТЪР
def predsezonen(ev, comp):
    """Предсезонен ли е мачът по ESPN. Копие на predictor.predsezonen.

    ЗАЩО е копие, а не внасяне: будилникът трябва да се пуска и когато
    predictor.py е счупен — иначе точно в деня, когато нещо гръмне, няма да
    има кой да каже „сезонът е тръгнал".
    """
    if str(((ev or {}).get("season") or {}).get("slug") or "").lower() == "preseason":
        return True
    if "preseason" in str(((ev or {}).get("seasonType") or {}).get("name") or "").lower():
        return True
    if str(((comp or {}).get("type") or {}).get("abbreviation") or "").upper() == "PRE":
        return True
    return False


def espn_sides(comp):
    """Домакин и гост по homeAway, НИКОГА по реда в списъка."""
    h = a = None
    for c in ((comp or {}).get("competitors") or []):
        if c.get("homeAway") == "home":
            h = c
        elif c.get("homeAway") == "away":
            a = c
    return h, a


def parse_espn(j):
    """ESPN scoreboard -> [(дата, дом_en, гост_en)]. Само неиграни, без предсезон.

    ЗАЩО отделно от четенето: така се тества с подхвърлен JSON, без мрежа.
    """
    out = []
    for ev in ((j or {}).get("events") or []):
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0] or {}
        if str(((comp.get("status") or {}).get("type") or {}).get("state") or "").lower() != "pre":
            continue
        if predsezonen(ev, comp):
            continue
        h, a = espn_sides(comp)
        if not h or not a:
            continue
        hn = str(((h.get("team") or {}).get("displayName")) or "")
        an = str(((a.get("team") or {}).get("displayName")) or "")
        if not hn or not an:
            continue
        out.append((str(ev.get("date") or "")[:10], hn, an))
    return out


def parse_nhl(j):
    """НХЛ /schedule -> [(дата, дом_en, гост_en)]. Само редовният сезон.

    ЗАЩО пълното име: /schedule дава placeName + commonName („Florida" +
    „Panthers"), докато /score — от който чете predictor — дава САМО прякора.
    Пълното име е това, което чуждият пазар знае.
    """
    out = []
    for wk in ((j or {}).get("gameWeek") or []):
        for gm in (wk.get("games") or []):
            if gm.get("gameType") == 1:          # предсезонните не носят информация
                continue
            if str(gm.get("gameState") or "").upper() not in ("FUT", "PRE"):
                continue
            h, a = gm.get("homeTeam") or {}, gm.get("awayTeam") or {}
            hn = _nhl_ime(h)
            an = _nhl_ime(a)
            if not hn or not an:
                continue
            out.append((str(wk.get("date") or "")[:10], hn, an))
    return out


def _nhl_ime(t):
    """Пълното английско име на отбор от НХЛ, ако източникът го дава."""
    mesto = str(((t or {}).get("placeName") or {}).get("default") or "").strip()
    kratko = str(((t or {}).get("commonName") or {}).get("default")
                 or ((t or {}).get("name") or {}).get("default") or "").strip()
    if mesto and kratko and not kratko.startswith(mesto):
        return mesto + " " + kratko
    return kratko or str((t or {}).get("abbrev") or "")


# ------------------------------------------------------------------ ЧЕТЕНЕ
def vzemi_espn(sport, slug, ot, do):
    """Всички неиграни срещи на една лига за цял период с ЕДНА заявка.

    ЗАЩО с период: ESPN приема `dates=ГГГГММДД-ГГГГММДД`. Измерено 19.08.2026:
    един адрес върна 455 колежански мача за 57 дни. По ден щеше да са 57
    заявки за същото.
    """
    u = (ESPN + "/" + sport + "/" + slug + "/scoreboard?dates="
         + ot.strftime("%Y%m%d") + "-" + do.strftime("%Y%m%d") + "&limit=1000")
    return parse_espn(_json(u))


def vzemi_nhl(ot, do):
    """Всички редовни мачове на НХЛ за период. Едно повикване носи седмица."""
    out, d = [], ot
    while d <= do:
        out += parse_nhl(_json(NHL + "/schedule/" + d.isoformat()))
        d += datetime.timedelta(days=7)
    # едно и също име може да дойде от две застъпени седмици
    return sorted(set(out))


# ------------------------------------------------------------------ СМЕТКА
def parvi_den(srechi):
    """Най-ранната дата с мач. None, ако няма нито един."""
    dni = sorted({d for d, _h, _a in srechi if d})
    return dni[0] if dni else None


def parva_sedmica(srechi, start, dni=SEDMICA):
    """Срещите в първите `dni` дни от старта, старта включително."""
    if not start:
        return []
    d0 = datetime.date.fromisoformat(start)
    d1 = d0 + datetime.timedelta(days=dni - 1)
    out = []
    for d, h, a in srechi:
        try:
            dd = datetime.date.fromisoformat(d)
        except ValueError:
            continue
        if d0 <= dd <= d1:
            out.append((d, h, a))
    return sorted(out)


def ceni_broi(kosh, srechi, pin):
    """Колко от срещите имат цена при Pinnacle. (с_цена, примери_без_цена).

    ЗАЩО през чуждия модул: това е ТОЧНО кодът, който предсказателят ще
    извика. Собствена реализация тук би измерила друго нещо.
    """
    if pin is None or not srechi:
        return 0, []
    sid = PIN_ID.get(kosh)
    if not sid:
        return 0, []
    pin.SPORT_ID[kosh] = sid          # ключът липсва в pinnacle.py — вж. патча
    s, bez = 0, []
    for _d, h, a in srechi:
        try:
            c = pin.ceni_za(kosh, h, a)
        except Exception:                                    # noqa: BLE001
            c = (None, None, None)
        if c[0] or c[1]:
            s += 1
        elif len(bez) < 3:
            bez.append(h + " - " + a)
    return s, bez


def pin_horizont(kosh, pin):
    """Докъде напред Pinnacle изобщо държи мачове за този спорт (в дни).

    ЗАЩО има значение: „0 с цена" за мач след 40 дни НЕ значи, че пазар няма
    — значи, че още не е отворен. Без това число будилникът лъже.
    """
    if pin is None or kosh not in PIN_ID:
        return None
    pin.SPORT_ID[kosh] = PIN_ID[kosh]
    try:
        st = sorted(v[3] for v in pin.machove(kosh).values() if v[3])
    except Exception:                                        # noqa: BLE001
        return None
    if not st:
        return None
    try:
        posl = datetime.date.fromisoformat(str(st[-1])[:10])
    except ValueError:
        return None
    return (posl - datetime.date.today()).days


# --------------------------------------------------------------- ДЕФЕКТИТЕ
def bug_hockey_extra(P, dni):
    """Пази ли hockey_fixtures оригиналното име. Иска мрежа. -> (наред, текст).

    ЗАЩО с подадени дни, а не с днешната дата: през август hockey_fixtures
    връща празно и проверката би минала фалшиво зелена. Дните идват от вече
    прочетения календар, тоест със сигурност има мач.
    """
    now = datetime.datetime.now(P.SOFIA)
    for d in dni[:4]:
        rows = P.hockey_fixtures(now, d)
        if rows:
            ex = rows[0].get("extra") or {}
            if ex.get("home_en"):
                return True, "hockey_fixtures пази home_en=" + str(ex.get("home_en"))
            return False, ("hockey_fixtures връща extra=" + json.dumps(ex, ensure_ascii=False)
                           + " за " + str(rows[0].get("home")) + " - " + str(rows[0].get("away"))
                           + " (" + str(len(rows)) + " мача на " + d + ")")
    # None значи НЕ ЗНАМ. Зелено тук би било лъжа: през август източникът
    # мълчи по устройство и нищо не е доказано.
    return None, "няма мачове за проба — дефектът НЕ Е проверен, нито оправен"


def zaguba_ot_defekti(P, PIN, srechi):
    """Колко цени губят двата дефекта. -> (загубени, общо, имена).

    ЗАЩО СИМУЛАЦИЯ, а не измерване: Pinnacle отваря хокея два дни преди мача,
    тоест на 19.08 няма НИТО ЕДНА истинска цена за 29.09 и въпросът „колко
    губим" няма как да се измери директно. Затова подхвърляме ТЕХНИЯ пазар с
    НАШИТЕ истински пълни имена от NHL /schedule („Carolina Hurricanes") и
    питаме с имената, които predictor праща ДНЕС.

    Числото е за геометрията на имената, не за парите. Казва се на глас.
    """
    if PIN is None or not srechi:
        return 0, 0, []
    PIN.SPORT_ID["hockey"] = PIN_ID["hockey"]
    st_m, st_p = PIN._kesh.get(("m", 19)), PIN._kesh.get(("p", 19))
    zagubeni, obshto = [], 0
    try:
        PIN._kesh[("m", 19)] = {str(i): (h, a, "NHL", "")
                                for i, (_d, h, a) in enumerate(srechi)}
        PIN._kesh[("p", 19)] = {str(i): (1.85, 1.95, None) for i in range(len(srechi))}
        now = datetime.datetime.now(P.SOFIA)
        for d in sorted({x[0] for x in srechi}):
            for fx in P.hockey_fixtures(now, d):
                obshto += 1
                ex = fx.get("extra") or {}
                c = PIN.ceni_za("hockey",
                                ex.get("home_en") or fx.get("home"),
                                ex.get("away_en") or fx.get("away"))
                if not (c[0] or c[1]):
                    zagubeni.append(str(fx.get("home")) + " - " + str(fx.get("away")))
    finally:
        for k, v in ((("m", 19), st_m), (("p", 19), st_p)):
            if v is None:
                PIN._kesh.pop(k, None)
            else:
                PIN._kesh[k] = v
    return len(zagubeni), obshto, zagubeni


def bug_rangers(P):
    """Изяжда ли BG_NAME хокейните имена. Без мрежа. -> (наред, текст)."""
    lo = []
    for ime in NHL_PRYAKORI:
        prev = P.bg_name(ime)
        if any("А" <= ch <= "я" or ch in "ЁёЍѝЎў" for ch in prev):
            lo.append(ime + " -> " + prev)
    if not lo:
        return True, "нито един прякор от НХЛ не се превежда"
    return False, (str(len(lo)) + " от " + str(len(NHL_PRYAKORI))
                   + " прякора стават кирилица: " + ", ".join(lo))


# 32-та прякора, както ги дава NHL /score (измерено 19.08.2026, 29.09-05.10).
NHL_PRYAKORI = [
    "Avalanche", "Blackhawks", "Blue Jackets", "Blues", "Bruins", "Canadiens",
    "Canucks", "Capitals", "Devils", "Ducks", "Flames", "Flyers",
    "Golden Knights", "Hurricanes", "Islanders", "Jets", "Kings", "Kraken",
    "Lightning", "Mammoth", "Maple Leafs", "Oilers", "Panthers", "Penguins",
    "Predators", "Rangers", "Red Wings", "Sabres", "Senators", "Sharks",
    "Stars", "Wild",
]


# ------------------------------------------------------------------ ИЗХОДЪТ
def _bg(d):
    """2026-09-29 -> 29.09."""
    try:
        return datetime.date.fromisoformat(d).strftime("%d.%m")
    except (ValueError, TypeError):
        return "?"


def zhivo(podrobno=False):
    """Будилникът: чете източниците и печата една карта за собственика."""
    dnes = datetime.date.today()
    do = dnes + datetime.timedelta(days=HORIZONT)
    try:
        import pinnacle as PIN
    except Exception:                                        # noqa: BLE001
        PIN = None

    print("🔔 БУДИЛНИК ЗА ЗАТВОРЕНИТЕ СПОРТОВЕ — " + dnes.strftime("%d.%m.%Y"))
    print("   гледам напред " + str(HORIZONT) + " дни, до " + do.strftime("%d.%m.%Y"))
    print("")

    hor = {}
    for kosh in sorted(PIN_ID):
        hor[kosh] = pin_horizont(kosh, PIN)

    gotovi, hok_dni, hok_srechi = [], [], []
    for sp in KALENDAR:
        vid, sport, slug = sp["izvor"]
        provali_predi = _provali[0]
        if vid == "nhl":
            srechi = vzemi_nhl(dnes, do)
            hok_dni = sorted({d for d, _h, _a in srechi})
        else:
            srechi = vzemi_espn(sport, slug, dnes, do)
        start = parvi_den(srechi)
        sedm = parva_sedmica(srechi, start)
        s_cena, bez = ceni_broi(sp["kosh"], sedm, PIN)
        if vid == "nhl":
            hok_srechi = sedm      # само първата седмица — тя се симулира после
        dyal = (100.0 * s_cena / len(sedm)) if sedm else 0.0
        h = hor.get(sp["kosh"])

        if not start:
            # 🔴 „Нула мача" и „източникът мълчи" изглеждат ЕДНАКВО отвън.
            # Точно това ме подведе първия път: НХЛ даваше 403, а картата
            # спокойно пишеше „няма нито един мач".
            if provali_predi != _provali[0]:
                print("%-24s ❌ ИЗТОЧНИКЪТ МЪЛЧИ (%d провалени заявки) — това НЕ"
                      " значи, че сезон няма" % (sp["ime"], _provali[0] - provali_predi))
            else:
                print("%-24s няма нито един мач до %s" % (sp["ime"], do.strftime("%d.%m")))
            print("")
            continue
        ost = (datetime.date.fromisoformat(start) - dnes).days
        kraj = datetime.date.fromisoformat(start) + datetime.timedelta(days=SEDMICA - 1)
        print("%-24s тръгва %s · след %d дни" % (sp["ime"], _bg(start), ost))
        print("   първа седмица (%s-%s): %d мача · цена за %d (%.0f%%)"
              % (_bg(start), kraj.strftime("%d.%m"), len(sedm), s_cena, dyal))
        # Честната уговорка: нула цена за далечен мач не е липса на пазар.
        if s_cena == 0 and h is not None and ost > h:
            print("   ⏳ Pinnacle държи този спорт само %d дни напред — пазарът"
                  " още не е отворен, числото ще порасне." % h)
        elif bez:
            print("   без цена, примери: " + " · ".join(bez))
        if sp.get("beleshka"):
            print("   " + sp["beleshka"])
        if podrobno:
            for d, hh, aa in sedm[:6]:
                print("      %s  %s - %s" % (_bg(d), hh[:26], aa[:26]))
        gotovi.append((sp, start, len(sedm), s_cena))
        print("")

    # --------- дефектите, които ще ухапят точно на старта
    print("🔴 ДВАТА ДЕФЕКТА ПРЕДИ ОТВАРЯНЕТО")
    try:
        import os
        os.environ.setdefault("PREDICT_IZKL", "")
        import predictor as P
    except Exception as e:                                   # noqa: BLE001
        print("   не мога да заредя predictor.py: " + str(e)[:70])
        P = None
    if P is not None:
        for ime, (ok, txt) in (("1 · hockey_fixtures без home_en", bug_hockey_extra(P, hok_dni)),
                               ("2 · BG_NAME яде хокейните имена", bug_rangers(P))):
            print(("   ⚠ " if ok is None else ("   ✅ " if ok else "   ❌ ")) + ime)
            print("      " + txt)
        z, obshto, imena = zaguba_ot_defekti(P, PIN, hok_srechi)
        if obshto:
            print("   ЦЕНАТА НА ДВАТА ДЕФЕКТА (симулация с техния пазар, наши имена):")
            print("      %d от %d мача в първата седмица на НХЛ остават без цена"
                  % (z, obshto))
            for i in imena[:6]:
                print("        · " + i)
    print("")

    # --------- заповедта
    print("🔓 КАК СЕ ОТВАРЯТ (пътят назад е една променлива)")
    print("   PREDICT_IZKL=\"\"                — връща и двата спорта")
    print("   PREDICT_IZKL=\"hockey\"          — само американският футбол")
    print("   PREDICT_IZKL=\"amfootball\"      — само хокеят")
    naj = [g for g in gotovi if g[0]["vazhen"]]
    if naj:
        prv = min(naj, key=lambda g: g[1])
        print("   Първата дата, на която стая ще е празна без това: "
              + _bg(prv[1]) + " (" + prv[0]["ime"] + ")")
    print("")
    print("заявки: %d мои (%d провалени) + %d на pinnacle"
          % (broi_zayavki(), broi_provali(), (PIN.broi_zayavki() if PIN else 0)))
    for z in _zashto:
        print("   провал: " + z)
    return 0


# --------------------------------------------------------------- ПРОВЕРКИТЕ
_PROBA_ESPN = {
    "events": [
        {"date": "2026-09-13T17:00Z", "season": {"slug": "regular-season"},
         "competitions": [{"status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "away", "team": {"displayName": "Dallas Cowboys"}},
                               {"homeAway": "home", "team": {"displayName": "New York Giants"}}]}]},
        {"date": "2026-08-22T17:00Z", "season": {"slug": "preseason"},
         "competitions": [{"status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "home", "team": {"displayName": "Тест Пре"}},
                               {"homeAway": "away", "team": {"displayName": "Тест Гост"}}]}]},
        {"date": "2026-09-14T17:00Z", "season": {"slug": "regular-season"},
         "competitions": [{"status": {"type": {"state": "post"}},
                           "competitors": [
                               {"homeAway": "home", "team": {"displayName": "Изигран"}},
                               {"homeAway": "away", "team": {"displayName": "Изигран 2"}}]}]},
        {"date": "2026-09-20T17:00Z", "season": {"slug": "regular-season"},
         "competitions": [{"status": {"type": {"state": "pre"}},
                           "type": {"abbreviation": "PRE"},
                           "competitors": [
                               {"homeAway": "home", "team": {"displayName": "Втори пре"}},
                               {"homeAway": "away", "team": {"displayName": "Втори гост"}}]}]},
    ]
}

_PROBA_NHL = {
    "gameWeek": [
        {"date": "2026-09-26", "games": [
            {"gameType": 1, "gameState": "FUT",
             "homeTeam": {"placeName": {"default": "Boston"}, "commonName": {"default": "Bruins"}},
             "awayTeam": {"placeName": {"default": "Buffalo"}, "commonName": {"default": "Sabres"}}}]},
        {"date": "2026-09-29", "games": [
            {"gameType": 2, "gameState": "FUT",
             "homeTeam": {"placeName": {"default": "Carolina"}, "commonName": {"default": "Hurricanes"}},
             "awayTeam": {"placeName": {"default": "Florida"}, "commonName": {"default": "Panthers"}}},
            {"gameType": 2, "gameState": "FINAL",
             "homeTeam": {"placeName": {"default": "New York"}, "commonName": {"default": "Rangers"}},
             "awayTeam": {"placeName": {"default": "New York"}, "commonName": {"default": "Islanders"}}}]},
        {"date": "2026-10-06", "games": [
            {"gameType": 2, "gameState": "FUT",
             "homeTeam": {"placeName": {"default": "New York"}, "commonName": {"default": "Rangers"}},
             "awayTeam": {"placeName": {"default": "Toronto"}, "commonName": {"default": "Maple Leafs"}}}]},
    ]
}


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # --- четенето на ESPN
    e = parse_espn(_PROBA_ESPN)
    check("ESPN: остава само неиграният редовен мач", len(e) == 1)
    check("ESPN: датата е отрязана до деня", e and e[0][0] == "2026-09-13")
    check("ESPN: домакинът е по homeAway, не по реда",
          e and e[0][1] == "New York Giants" and e[0][2] == "Dallas Cowboys")
    check("ESPN: предсезонният по season.slug пада",
          all("Пре" not in x[1] for x in e))
    check("ESPN: предсезонният по type.abbreviation пада",
          all("Втори" not in x[1] for x in e))
    check("ESPN: изиграният пада", all("Изигран" not in x[1] for x in e))
    check("ESPN: празният вход не гърми", parse_espn(None) == [] and parse_espn({}) == [])

    # --- четенето на НХЛ
    n = parse_nhl(_PROBA_NHL)
    check("НХЛ: предсезонният (gameType 1) пада",
          all("Bruins" not in x[1] for x in n))
    check("НХЛ: изиграният (FINAL) пада", len(n) == 2)
    check("НХЛ: пълното име, не прякорът",
          n and n[0][1] == "Carolina Hurricanes" and n[0][2] == "Florida Panthers")
    check("НХЛ: Rangers идва с града", any(x[1] == "New York Rangers" for x in n))
    check("НХЛ: празният вход не гърми", parse_nhl(None) == [] and parse_nhl({}) == [])

    # --- сметката за първата седмица
    check("първият ден е най-ранният", parvi_den(n) == "2026-09-29")
    check("празният списък няма първи ден", parvi_den([]) is None)
    s = parva_sedmica(n, "2026-09-29")
    check("седмицата хваща 29.09", any(x[0] == "2026-09-29" for x in s))
    check("седмицата НЕ хваща 06.10 (осмият ден)",
          all(x[0] != "2026-10-06" for x in s))
    check("седмицата хваща 05.10 (седмият ден)",
          len(parva_sedmica([("2026-10-05", "а", "б")], "2026-09-29")) == 1)
    check("без старт няма седмица", parva_sedmica(n, None) == [])
    check("боклук за дата не гърми",
          parva_sedmica([("нещо", "а", "б")], "2026-09-29") == [])

    # --- имената на НХЛ
    check("името се сглобява от град и прякор",
          _nhl_ime({"placeName": {"default": "Florida"},
                    "commonName": {"default": "Panthers"}}) == "Florida Panthers")
    check("градът не се удвоява",
          _nhl_ime({"placeName": {"default": "Utah"},
                    "commonName": {"default": "Utah Mammoth"}}) == "Utah Mammoth")
    check("само прякор пак върши работа",
          _nhl_ime({"name": {"default": "Capitals"}}) == "Capitals")
    check("съкращението е последна спирка",
          _nhl_ime({"abbrev": "WSH"}) == "WSH")

    # --- Pinnacle: имената, които ще търсим
    try:
        import pinnacle as PIN
    except Exception:                                        # noqa: BLE001
        PIN = None
    check("pinnacle.py се внася", PIN is not None)
    if PIN is not None:
        check("🔴 pinnacle.py НЯМА хокей — затова го добавяме тук",
              "hockey" not in PIN.SPORT_ID or PIN.SPORT_ID.get("hockey") == 19)
        check("американският футбол е 15, хокеят е 19",
              PIN_ID["amfootball"] == 15 and PIN_ID["hockey"] == 19)
        # 🔴 ГЛАВНАТА ПРОВЕРКА В ФАЙЛА. Подхвърляме пазара на Pinnacle точно
        # какъвто е (пълни имена) и питаме два пъти: веднъж с ПРЕВЕДЕНОТО име
        # (каквото predictor праща днес) и веднъж с АНГЛИЙСКОТО (каквото ще
        # праща след патча). Ако първото намери мача, дефект няма. Намира ли
        # само второто — дефектът е доказан БЕЗ да чакаме септември.
        st_m = PIN._kesh.get(("m", 19))
        st_p = PIN._kesh.get(("p", 19))
        try:
            PIN.SPORT_ID["hockey"] = 19
            PIN._kesh[("m", 19)] = {
                "900": ("New York Rangers", "Carolina Hurricanes", "NHL", ""),
            }
            PIN._kesh[("p", 19)] = {"900": (1.85, 1.95, None)}
            kir = PIN.ceni_za("hockey", "Рейнджърс", "Hurricanes")
            ang = PIN.ceni_za("hockey", "Rangers", "Hurricanes")
            check("🔴 кирилицата НЕ намира мача (дефект 2, доказан)",
                  kir == (None, None, None))
            check("английският прякор го намира", ang == (1.85, 1.95, None))
            check("нулата мрежа се пази", broi_zayavki() == 0)
        finally:
            for k, v in ((("m", 19), st_m), (("p", 19), st_p)):
                if v is None:
                    PIN._kesh.pop(k, None)
                else:
                    PIN._kesh[k] = v
        check("кешът е чист след теста", ("m", 19) not in PIN._kesh)

    # --- дефект 2 срещу ЖИВИЯ predictor (пак без мрежа — само речник)
    try:
        import os
        os.environ.setdefault("PREDICT_IZKL", "")
        import predictor as P
    except Exception:                                        # noqa: BLE001
        P = None
    check("predictor.py се внася", P is not None)

    # 🔴 ТЪРСАЧЪТ СЕ ИЗПИТВА В ДВЕТЕ ПОСОКИ, НЕ СРЕЩУ ЖИВИЯ ФАЙЛ.
    # Ако тук стоеше „BG_NAME трябва да е счупен", файлът щеше да ПОЧЕРВЕНЕЕ
    # в деня, в който някой приложи патча — тоест наградата за поправката
    # щеше да е счупен тест. Затова проверяваме, че `bug_rangers` вижда и
    # двете състояния, а живото състояние се ПЕЧАТА, не се съди.
    class _Fake(object):
        def __init__(self, karta):
            self.karta = karta

        def bg_name(self, s):
            return self.karta.get(s, s)

    check("търсачът вижда превода", bug_rangers(_Fake({"Rangers": "Рейнджърс"}))[0] is False)
    check("търсачът мълчи, когато превод няма", bug_rangers(_Fake({}))[0] is True)
    check("търсачът брои колко точно",
          "1 от 32" in bug_rangers(_Fake({"Rangers": "Рейнджърс"}))[1])
    check("латиницата не се брои за превод",
          bug_rangers(_Fake({"Rangers": "Glasgow Rangers"}))[0] is True)

    # Същото и за дефект 1 — с подхвърлен predictor, нула мрежа.
    class _FakeP(object):
        SOFIA = datetime.timezone.utc

        def __init__(self, ex):
            self.ex = ex

        def hockey_fixtures(self, now, d):
            if self.ex is None:
                return []
            return [{"home": "Рейнджърс", "away": "Hurricanes", "extra": self.ex}]

    check("дефект 1: празният extra е ЧЕРВЕН",
          bug_hockey_extra(_FakeP({}), ["2026-09-29"])[0] is False)
    check("дефект 1: home_en е ЗЕЛЕН",
          bug_hockey_extra(_FakeP({"home_en": "New York Rangers"}), ["2026-09-29"])[0] is True)
    check("дефект 1: празният ден е НЕ ЗНАМ, а не зелено",
          bug_hockey_extra(_FakeP(None), ["2026-09-29"])[0] is None)
    check("дефект 1: без дни изобщо е НЕ ЗНАМ",
          bug_hockey_extra(_FakeP({}), [])[0] is None)

    if P is not None:
        r_ok, r_txt = bug_rangers(P)
        print("   живо състояние на дефект 2: " + ("наред — " if r_ok else "ЖИВ — ") + r_txt)

    # 🔴 ПОДПИСИТЕ. Тази проверка съществува, защото точно тук сгреших:
    # един подпис за двата източника направи НХЛ ням, а картата остана зелена.
    check("ESPN пътува БЕЗ подпис",
          "User-Agent" not in glavi_za("https://site.api.espn.com/x"))
    check("НХЛ пътува С подпис",
          glavi_za("https://api-web.nhle.com/v1/schedule/2026-09-29").get("User-Agent") == UA)
    check("Pinnacle също е с подпис (не е ESPN)",
          "User-Agent" in glavi_za("https://guest.api.arcadia.pinnacle.com/0.1/sports"))

    check("календарът има петте реда", len(KALENDAR) == 5)
    check("всеки ред знае коша си",
          all(s["kosh"] in ("hockey", "amfootball") for s in KALENDAR))
    check("всеки ред носи бележка", all(s.get("beleshka") for s in KALENDAR))
    check("трите важни са НФЛ, NCAA футбол и НХЛ",
          [s["kod"] for s in KALENDAR if s["vazhen"]] == ["nfl", "ncaaf", "nhl"])
    check("седмицата е 7 дни", SEDMICA == 7)
    check("нула мрежа в цялата самопроверка", broi_zayavki() == 0)
    check("нула провалени заявки, щом няма заявки", broi_provali() == 0)
    check("броят проверки е поне 40", ok >= 40)

    print("САМОПРОВЕРКА НА SEZON: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(zhivo(podrobno=("--zhivo" in sys.argv)))
