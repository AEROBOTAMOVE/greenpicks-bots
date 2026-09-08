# -*- coding: utf-8 -*-
"""Коефициенти от Betano.bg — БЪЛГАРСКА лицензирана книга (08.09.2026).

## ЗАЩО СЪЩЕСТВУВА

Собственикът иска картите да са ЗАЛОЖИМИ в български къщи, с число. Живото
измерване на дневника (1583 отсъдени карти) казва:

    с коефициент   940 карти · сбъдва 61.4% · обявява 63.7% · доходност -9.1%
    БЕЗ коефициент 643 карти · сбъдва 66.9% · обявява 64.5% · доходност НЕ СЕ ЗНАЕ

Тоест 40% от продукта е НЕИЗМЕРИМ за пари, и точно тази част сбъдва повече.
Без число там не можем нито да кажем «това е печалба», нито «това е загуба».

Pinnacle, ESPN, Smarkets и Kambi заедно не покриват тези мачове. Betano.bg
ги покрива: офертата ѝ, питана на 08.09.2026, дава 1905 събития с пазар
«победител» — включително WTT Контендер Панагюрище, който Kambi няма.

## КАКВО НЕ ПРАВИ

Не се регистрира, не праща ключ, не се преправя на браузър. Подписът е
нашият собствен, същият като при ESPN. Чете се публичната оферта — това е
същото, което прави и всеки посетител на сайта.

## ТРИТЕ КАПАНА, ИЗМЕРЕНИ ПРЕДИ ДА СЕ ПИШЕ КОДЪТ

1. 🔴 ИМЕНАТА НЕ СА В ИЗХОДИТЕ. При футбола пазарът «Краен резултат» дава
   изходи, наречени буквално «1», «X», «2». Първата ми проба четеше оттам
   и получи НУЛА от 426 футболни събития. Имената са в `participants`.

2. 🔴 ТИПЪТ НА ПАЗАРА СЕ КАЗВА РАЗЛИЧНО ВЪВ ВСЕКИ СПОРТ: `HTOH` при тениса
   на маса, `MRES` при футбола, `H2HT` при хокея. Изброяването им ми даде
   нула за шест спорта. Затова пазарът се познава ПО УСТРОЙСТВО: нулев
   хендикап и изходи, които или са точно 1/X/2, или носят имената на
   участниците.

3. 🔴 ТРАНСЛИТЕРАЦИЯТА НЕ СЕ ВРЪЩА ОБРАТНО. Betano пише на кирилица:
   «Carolina» става «Каролина» и обратното дава «karolina», не «carolina».
   Затова буквите, които кирилицата слива, се свиват и от двете страни
   (c и k, y и i, j и i). Измерено: свиването вдига улова от 26% на 29%.

## ЗАЩО СЕ ИСКА И ЧАСЪТ

Адверсарна мерка върху 2432 НАРОЧНО СГРЕШЕНИ двойки (домакин от една среща,
гост от друга, със собствения си час):

    само по име            хваща 100% от верните · пуска  9.6% лъжливи
    име + час ±120 мин     хваща 100%             · пуска  4.2%
    име + час ±30 мин      хваща 100%             · пуска  1.4%

Часът реже лъжите седем пъти БЕЗ да губи нито едно вярно съвпадение.
Затова прозорецът е задължителен, когато викащият знае часа.

ПЪТ НАЗАД: `BETANO_CENI=0` изключва целия източник, без пипане на код.
"""
import difflib
import io
import json
import os
import re
import sys
import unicodedata
import urllib.request

# ═════════════════════════════════════════ РЪЧКИТЕ
VKLYUCHENO = (os.environ.get("BETANO_CENI", "1") or "1").strip() not in (
    "0", "false", "не")
try:
    TAVAN_TURNIRI = max(0, min(60, int(
        (os.environ.get("BETANO_TAVAN_TURNIRI") or "14").strip() or 14)))
except ValueError:
    TAVAN_TURNIRI = 14
try:
    TAIMAUT = max(5, min(60, int(
        (os.environ.get("BETANO_TAIMAUT") or "20").strip() or 20)))
except ValueError:
    TAIMAUT = 20
try:
    # Прозорецът в МИНУТИ. 0 значи «не гледай часа» — губи седем пъти повече
    # лъжливи съвпадения и затова НЕ е подразбирането.
    PROZOREC = max(0, min(360, int(
        (os.environ.get("BETANO_PROZOREC") or "30").strip() or 30)))
except ValueError:
    PROZOREC = 30

UA = "greenpicks-bot/1.0 (+github.com/AEROBOTAMOVE/greenpicks-bots)"
BAZA = "https://www.betano.bg/api"
OPASHKA = "?req=la,s,stnf,c,mb"

# 🔴 «НЕ МОЖАХ ДА ПИТАМ» Е ОТГОВОР, РАЗЛИЧЕН ОТ «НЯМА МАЧОВЕ».
NEPITAN = object()

# Нашите кошници -> пътищата на Betano. Проверени живо на 08.09.2026:
# всеки от тях върна поне един турнир.
SPORT = {
    "tabletennis": "table-tennis",
    "tennis": "tennis",
    "volleyball": "volleyball",
    "hockey": "ice-hockey",
    "basketball": "basketball",
    "football": "soccer",
    "baseball": "baseball",
    "mma": "mma",
    "amfootball": "american-football",
    "esports": "esports",
    # 🔴 РЪГБИ НЯМА. Питано живо на 08.09.2026 с «rugby» и «ragbi» —
    # и двата пътя връщат нула турнира. Не се обявява спорт, който изворът
    # не дава: това би било мълчание под чуждо име.
}

_kesh = {}
_STAT = {"zayavki": 0, "provali": 0}


def _nulirai_stat():
    _STAT["zayavki"] = 0
    _STAT["provali"] = 0


def statistika():
    """Копие на брояча — за диагностика, не за решения."""
    return dict(_STAT)


def _vzemi(url, otvarach=None):
    """Суровият отговор. Хвърля при отказ — уловът е при викащия."""
    _STAT["zayavki"] += 1
    otv = otvarach or urllib.request.urlopen
    rq = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept": "application/json"})
    return otv(rq, timeout=TAIMAUT).read()


def _json(url, otvarach=None):
    """Разчетеният отговор, или NEPITAN при какъвто и да е отказ."""
    try:
        b = _vzemi(url, otvarach)
    except Exception:                                        # noqa: BLE001
        _STAT["provali"] += 1
        return NEPITAN
    try:
        return json.loads(b.decode("utf-8", "replace"))
    except Exception:                                        # noqa: BLE001
        _STAT["provali"] += 1
        return NEPITAN


# ═════════════════════════════════════════ ИМЕНАТА
# Кирилица -> латиница. Не е официалната транслитерация: целта не е красив
# правопис, а СРАВНЕНИЕ.
TABLICA = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sht", "ъ": "a",
    "ь": "", "ю": "yu", "я": "ya", "ы": "y", "э": "e", "ё": "e",
}

# 🔴 БУКВИТЕ, КОИТО КИРИЛИЦАТА СЛИВА. «Carolina» -> «Каролина» -> «karolina»:
# c и k стават едно. Свиването се прилага И НА ДВЕТЕ страни, иначе не помага.
SVIVANE = {"c": "k", "q": "k", "x": "ks", "w": "v", "y": "i", "j": "i"}

# 🔴 ОБЩИТЕ ДУМИ НЕ РАЗЛИЧАВАТ НИЩО. Измерено адверсарно: «Team Nemesis»
# съвпадаше с «Теам Фалцонс» по думата «team». Списъкът е в СВИТ вид,
# защото се сравнява СЛЕД свиването («теам» -> «team», «сити» -> «kiti»).
OBSHTI = set("""
team teams esports esport gaming games klub club united sporting sport
sports real kiti akademiia akademiya women womens men mens junior juniors
youth reserve reserves national federation liga league kup cup open masters
series tour hokei futbol basket volei tenis maski zenski
""".split())


def latinica(s):
    """Свито латинско изписване. За сравнение, не за показване."""
    t = unicodedata.normalize("NFKD", str(s or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = "".join(TABLICA.get(c, c) for c in t)
    return "".join(SVIVANE.get(c, c) for c in t)


def redica(s):
    """Отличителните думи В РЕД. Редът пази коя е последната (фамилията)."""
    r = []
    for w in re.split(r"[\s\-\.,/()]+", latinica(s)):
        w = "".join(c for c in w if ("a" <= c <= "z") or c.isdigit())
        if len(w) >= 4 and w not in OBSHTI:
            r.append(w)
    return r


def blizki(x, y):
    """Две думи са една и съща дума. Размитото важи само за дълги думи.

    🔴 ПРАГЪТ 6 БУКВИ Е ИЗМЕРЕН. По-къс праг слива «Симек» и «Юпа».
    """
    if x == y:
        return True
    if len(x) >= 6 and len(y) >= 6:
        return difflib.SequenceMatcher(None, x, y).ratio() >= 0.85
    return False


def sreshta(a, b):
    """Едно и също име ли са. Иска отличителна дума, не коя да е."""
    ra, rb = redica(a), redica(b)
    if not (ra and rb):
        return False
    return any(blizki(x, y) for x in ra for y in rb)


def sila(a, b):
    """Колко думи си съвпадат — за избор между няколко кандидата."""
    ra, rb = redica(a), redica(b)
    n = sum(1 for x in ra if any(blizki(x, y) for y in rb))
    # Съвпадението по ПОСЛЕДНАТА дума (фамилията) тежи повече.
    if ra and rb and blizki(ra[-1], rb[-1]):
        n += 1
    return n


# ═════════════════════════════════════════ РАЗЧИТАНЕТО НА СЪБИТИЕТО
def imena_ot_sabitie(ev):
    """(дом, гост) от УЧАСТНИЦИТЕ. None, ако няма имена.

    🔴 НЕ ОТ `selection.name`. При «Краен резултат» там пише «1», «X», «2» —
    измерено живо на 426 футболни събития, всичките се губеха.
    """
    ev = ev or {}
    uch = ev.get("participants") or []
    if len(uch) >= 2:
        a = str(uch[0].get("name") or "").strip()
        b = str(uch[1].get("name") or "").strip()
        if a and b:
            return (a, b)
    ime = str(ev.get("name") or "")
    for razd in (" - ", " – ", " vs ", " — "):
        if razd in ime:
            a, b = ime.split(razd, 1)
            a, b = a.strip(), b.strip()
            if a and b:
                return (a, b)
    return None


def koef_ot_sabitie(ev):
    """{«1», «2», «Х»} от пазара «победител». Празно, ако няма такъв.

    🔴 ПАЗАРЪТ СЕ ПОЗНАВА ПО УСТРОЙСТВО, НЕ ПО ИМЕ НА ТИП. Типът се казва
    HTOH (тенис на маса), MRES (футбол), H2HT (хокей) — изброяването им ми
    върна нула за шест спорта. Тук се иска: нулев хендикап, два или три
    изхода, коефициенти над 1.00, и изходи, които СА 1/X/2 или носят
    имената на участниците.
    """
    ev = ev or {}
    im = imena_ot_sabitie(ev)
    for m in (ev.get("markets") or []):
        try:
            if float(m.get("handicap") or 0) != 0.0:
                continue
        except (TypeError, ValueError):
            continue
        izh = m.get("selections") or []
        if not 2 <= len(izh) <= 3:
            continue
        ceni, etiketi = [], []
        dobre = True
        for s in izh:
            try:
                c = float(s.get("price") or 0)
            except (TypeError, ValueError):
                dobre = False
                break
            if c <= 1.0:
                dobre = False
                break
            ceni.append(c)
            etiketi.append(str(s.get("name") or "").strip())
        if not dobre:
            continue
        # 🔴 «Х» е КИРИЛСКО в българския изход. Свежда се до латинско X.
        cheti = [e.replace("Х", "X").upper() for e in etiketi]
        if set(cheti) <= {"1", "X", "2"} and "1" in cheti and "2" in cheti:
            d = dict(zip(cheti, ceni))
            r = {"1": d["1"], "2": d["2"]}
            if "X" in d:
                r["Х"] = d["X"]
            return r
        if len(izh) == 2 and im:
            # 🔴 ПО ИМЕ, НЕ ПО РЕД. Обърнат ред не бива да обръща цените.
            if sreshta(etiketi[0], im[0]) and sreshta(etiketi[1], im[1]):
                return {"1": ceni[0], "2": ceni[1]}
            if sreshta(etiketi[0], im[1]) and sreshta(etiketi[1], im[0]):
                return {"1": ceni[1], "2": ceni[0]}
    return {}


# ═════════════════════════════════════════ ОФЕРТАТА
def turniri(sport, otvarach=None):
    """[(име, път)] на турнирите. NEPITAN при отказ.

    🔴 КЕШИРА СЕ САМО УСПЕХ. Празно от провал би заключило спорта за целия
    рън — грешка, която този проект вече е плащал при Pinnacle и ITF.
    """
    kl = ("turniri", sport)
    if kl in _kesh:
        return _kesh[kl]
    put = SPORT.get(str(sport) or "")
    if not put:
        return []
    d = _json(BAZA + "/sport/" + put + "/" + OPASHKA, otvarach)
    if d is NEPITAN:
        return NEPITAN
    grupi = ((d or {}).get("data") or {}).get("regionGroups") or []
    nam = []
    for G in grupi:
        for R in (G.get("regions") or []):
            for L in (R.get("leagues") or []):
                u = str(L.get("url") or "")
                if u:
                    nam.append(("%s / %s" % (R.get("name"), L.get("name")), u))
    _kesh[kl] = nam
    return nam


def sabitiya(sport, otvarach=None):
    """[(дом, гост, начало_мс, коеф_дом, коеф_гост, коеф_равен, лига, път)].

    NEPITAN, ако САМОТО ДЪРВО е отказало. Отказ на отделен турнир не е отказ
    на извора — той се брои и се минава нататък.
    """
    kl = ("sab", sport)
    if kl in _kesh:
        return _kesh[kl]
    t = turniri(sport, otvarach)
    if t is NEPITAN:
        return NEPITAN
    vsi = []
    for ime, put in t[:TAVAN_TURNIRI]:
        d = _json(BAZA + put + OPASHKA, otvarach)
        if d is NEPITAN:
            continue
        for b in (((d or {}).get("data") or {}).get("blocks") or []):
            for ev in (b.get("events") or []):
                im = imena_ot_sabitie(ev)
                if not im:
                    continue
                k = koef_ot_sabitie(ev)
                if not k:
                    continue
                try:
                    st = int(ev.get("startTime") or 0)
                except (TypeError, ValueError):
                    st = 0
                vsi.append((im[0], im[1], st, k.get("1"), k.get("2"),
                            k.get("Х"), ime, str(ev.get("url") or "")))
    _kesh[kl] = vsi
    return vsi


def ceni_za(sport, dom, gost, nachalo=None, otvarach=None):
    """(коеф_дом, коеф_гост, коеф_равен, лига, път) или None. NEPITAN при отказ.

    🔴 СЪВПАДЕНИЕТО ИСКА И ДВЕТЕ СТРАНИ. Една обща фамилия вече е свързала
    чужд мач в този проект («Bury FC» срещу «Sporting Kansas City»).

    🔴 ЧАСЪТ Е ЗАДЪЛЖИТЕЛЕН, КОГАТО ГО ЗНАЕМ. Мерено адверсарно на 2432
    нарочно сгрешени двойки: без час минават 9.6% лъжливи, с ±30 минути —
    1.4%, БЕЗ да се губи нито едно вярно съвпадение.

    🔴 ПРИ РАВНИ КАНДИДАТИ СЕ ОТКАЗВА. Два еднакво добри мача значи, че не
    знаем кой е нашият; тиха грешна цена е по-лоша от липсваща.
    """
    if not VKLYUCHENO:
        return None
    ev = sabitiya(sport, otvarach)
    if ev is NEPITAN:
        return NEPITAN
    if not (redica(dom) and redica(gost)):
        return None
    kand = []
    for zap in ev:
        A, B, st = zap[0], zap[1], zap[2]
        if PROZOREC and nachalo and st:
            try:
                if abs(int(st) - int(nachalo)) > PROZOREC * 60000:
                    continue
            except (TypeError, ValueError):
                pass
        if sreshta(dom, A) and sreshta(gost, B):
            kand.append((sila(dom, A) + sila(gost, B),
                         (zap[3], zap[4], zap[5], zap[6], zap[7])))
        elif sreshta(dom, B) and sreshta(gost, A):
            # обърнати страни — връщаме В НАШИЯ ред; равният си остава равен
            kand.append((sila(dom, B) + sila(gost, A),
                         (zap[4], zap[3], zap[5], zap[6], zap[7])))
    if not kand:
        return None
    kand.sort(key=lambda x: -x[0])
    if len(kand) > 1 and kand[0][0] == kand[1][0] and kand[0][1] != kand[1][1]:
        return None
    return kand[0][1]


def ima_go(sport, dom, gost, nachalo=None, otvarach=None):
    """Заложим ли е мачът в българската книга. None при отказ на извора."""
    r = ceni_za(sport, dom, gost, nachalo, otvarach)
    if r is NEPITAN:
        return None
    return bool(r)


# ═════════════════════════════════════════ САМОПРОВЕРКА
def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    pitani = []

    def lazhliv(otgovor):
        def otv(rq, timeout=None):
            pitani.append(rq.full_url if hasattr(rq, "full_url") else str(rq))

            class F(object):
                def read(self_inner):
                    return json.dumps(otgovor).encode("utf-8")

                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *a):
                    return False
            return F()
        return otv

    def otkaz(rq, timeout=None):
        raise urllib.request.URLError("няма мрежа")

    # ── транслитерацията
    # 🔴 ТЕСТЪТ ТВЪРДИ СХОДИМОСТ, НЕ КОНКРЕТЕН НИЗ. Свиването превръща и
    # «ch» в «kh» — грозно, но СИМЕТРИЧНО: «Fruchart» и «Фручарт» стигат до
    # едно и също. Значението е в срещането, не в правописа. Първата ми
    # проверка искаше «fruchart» и падна върху собственото си очакване.
    check("двата правописа на едно име се сливат",
          latinica("Fruchart") == latinica("Фручарт") != "")
    check("и при отборите", latinica("Carolina") == latinica("Каролина"))
    check("но РАЗЛИЧНИ имена НЕ се сливат",
          latinica("Fruchart") != latinica("Регнер"))
    check("ударенията падат", latinica("Skellefteå") == "skelleftea")
    check("латиницата минава непокътната по значещото",
          "svoboda" in latinica("Adam Svoboda"))

    # ── отличителните думи
    check("късите думи падат", "hc" not in redica("HC Davos"))
    check("общите думи падат", redica("Team Nemesis") == ["nemesis"])
    check("общата дума не прави съвпадение",
          not sreshta("Team Nemesis", "Team Falcons"))
    check("истинското име прави съвпадение",
          sreshta("Tomas Regner", "Томас Регнер"))
    check("едностранното име се хваща",
          sreshta("KooKoo Kouvola", "КооКоо"))
    check("празното име не среща нищо", not sreshta("", "Regner"))
    # 🔴 ДВОЙКАТА Е ИЗБРАНА ДА МИНАВА ПРАГА. «simek»/«supa» дават 0.44 и
    # падат така или иначе — тестът минаваше и с махнат пазач. «petro» и
    # «petrov» дават 0.91: с пазача са различни, без него се сливат.
    check("късата дума НЕ се слива с по-дългата",
          not blizki("petro", "petrov"))
    check("а дългите се сливат", blizki("petrov", "petrovv"))
    check("дългите се сравняват размито", blizki("holovatiuk", "holovatyuk"))

    # ── имената от събитието
    # 🔴 ТРИТЕ ПЪТЯ НОСЯТ РАЗЛИЧНИ ИМЕНА НАРОЧНО. С еднакви имена махането
    # на първия път остава невидимо и мутацията минава зелена.
    _ev = {"participants": [{"name": "ПЪРВИ Дом"},
                            {"name": "ПЪРВИ Гост"}],
           "name": "ВТОРИ Дом - ВТОРИ Гост"}
    check("имената идват ПЪРВО от участниците",
          imena_ot_sabitie(_ev) == ("ПЪРВИ Дом",
                                    "ПЪРВИ Гост"))
    check("без тях се цепи името на събитието",
          imena_ot_sabitie({"name": "ВТОРИ Дом - ВТОРИ Гост"})
          == ("ВТОРИ Дом", "ВТОРИ Гост"))
    check("без нищо няма имена", imena_ot_sabitie({}) is None)

    # ── коефициентите
    # 🔴 ЕТИКЕТИТЕ СА 1/X/2, А ИМЕНАТА СА ДРУГИ — точно както при футбола.
    _tri = {"participants": [{"name": "ЦСКА 1948"},
                             {"name": "Дунав Русе"}],
            "markets": [{"handicap": 0.0, "name": "Краен резултат",
                         "selections": [{"name": "1", "price": 1.4},
                                        {"name": "Х", "price": 5.0},
                                        {"name": "2", "price": 8.0}]}]}
    check("триизходният пазар се чете по ЕТИКЕТ",
          koef_ot_sabitie(_tri) == {"1": 1.4, "2": 8.0, "Х": 5.0})
    # 🔴 ОБЪРНАТ РЕД: тук четене «по ред» дава ГРЕШНИЯ отговор, а по име —
    # верния. С подредени изходи двете съвпадат и мутацията остава зелена.
    _dva = {"participants": [{"name": "Tomas Regner"}, {"name": "Adam Svoboda"}],
            "markets": [{"handicap": 0.0, "name": "Победител",
                         "selections": [{"name": "Adam Svoboda", "price": 1.55},
                                        {"name": "Tomas Regner", "price": 2.40}]}]}
    check("двуизходният пазар се чете ПО ИМЕ, не по ред",
          koef_ot_sabitie(_dva) == {"1": 2.40, "2": 1.55})
    # 🔴 ХЕНДИКАПЪТ Е ПЪРВИ И ИМЕНАТА МУ СЪВПАДАТ. Първата ми проверка
    # ползваше имена «A B»/«C D», които падат като прекалено къси — тоест
    # връщаше празно и БЕЗ пазача. Мутацията «приемай хендикап» оставаше
    # зелена. Тук хендикапният пазар е напълно разпознаваем и единственото,
    # което го отхвърля, е самият пазач.
    _hcp = {"participants": [{"name": "Tomas Regner"}, {"name": "Adam Svoboda"}],
            "markets": [
                {"handicap": -1.5, "name": "Хендикап", "selections": [
                    {"name": "Tomas Regner", "price": 2.90},
                    {"name": "Adam Svoboda", "price": 1.40}]},
                {"handicap": 0.0, "name": "Победител", "selections": [
                    {"name": "Adam Svoboda", "price": 1.55},
                    {"name": "Tomas Regner", "price": 2.40}]}]}
    check("хендикапният пазар се прескача, взима се «победител»",
          koef_ot_sabitie(_hcp) == {"1": 2.40, "2": 1.55})
    check("а само с хендикап няма коефициент",
          koef_ot_sabitie({"participants": _hcp["participants"],
                           "markets": _hcp["markets"][:1]}) == {})
    check("коефициент 1.00 не се приема",
          koef_ot_sabitie({"participants": [{"name": "Tomas Regner"},
                                            {"name": "Adam Svoboda"}],
                           "markets": [{"handicap": 0.0, "selections": [
                               {"name": "Tomas Regner", "price": 1.0},
                               {"name": "Adam Svoboda", "price": 2.0}]}]}) == {})
    check("пазар без нашия мач не дава нищо", koef_ot_sabitie({}) == {})

    # ── сентинелът
    _kesh.clear()
    check("отказът на дървото е NEPITAN",
          turniri("tabletennis", otkaz) is NEPITAN)
    check("отказът НЕ се кешира", ("turniri", "tabletennis") not in _kesh)
    _kesh.clear()
    check("отказът стига до събитията",
          sabitiya("tabletennis", otkaz) is NEPITAN)
    _kesh.clear()
    check("и до цените", ceni_za("tabletennis", "A Bcde", "F Ghij",
                                 None, otkaz) is NEPITAN)
    _kesh.clear()
    check("непознат спорт не пипа мрежата", turniri("krikett") == [])
    check("ръгбито НЕ се обявява за покрито", "rugby" not in SPORT)

    # ── целият път, върху подложка
    _kesh.clear()
    _dyrvo = {"data": {"regionGroups": [{"regions": [
        {"name": "Чехия", "leagues": [
            {"name": "Лига Про", "url": "/sport/x/1/"}]}]}]}}
    _liga = {"data": {"blocks": [{"events": [
        {"participants": [{"name": "Томас Регнер"},
                          {"name": "Адам Свобода"}],
         "startTime": 1788850800000, "url": "/koefitsienti/x/1/",
         "markets": [{"handicap": 0.0, "selections": [
             {"name": "Томас Регнер", "price": 2.40},
             {"name": "Адам Свобода", "price": 1.55}]}]}]}]}}

    def dvoen(rq, timeout=None):
        u = rq.full_url
        pitani.append(u)
        telo = _liga if "/sport/x/1/" in u else _dyrvo

        class F(object):
            def read(self_inner):
                return json.dumps(telo).encode("utf-8")

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return F()

    _r = ceni_za("tabletennis", "Tomas Regner", "Adam Svoboda",
                 1788850800000, dvoen)
    check("латинското име среща кирилското през целия път",
          isinstance(_r, tuple) and abs(_r[0] - 2.40) < 1e-9)
    check("и гостът е на мястото си",
          isinstance(_r, tuple) and abs(_r[1] - 1.55) < 1e-9)
    check("лигата се назовава",
          isinstance(_r, tuple) and "Лига" in str(_r[3]))
    check("пътят до фиша се пази",
          isinstance(_r, tuple) and str(_r[4]).startswith("/koefitsienti/"))
    _kesh.clear()
    _o = ceni_za("tabletennis", "Adam Svoboda", "Tomas Regner",
                 1788850800000, dvoen)
    check("обърнатите страни връщат ОБЪРНАТИ коефициенти",
          isinstance(_o, tuple) and abs(_o[0] - 1.55) < 1e-9
          and abs(_o[1] - 2.40) < 1e-9)
    _kesh.clear()
    check("чужд час НЕ дава цена",
          ceni_za("tabletennis", "Tomas Regner", "Adam Svoboda",
                  1788850800000 + 3 * 3600000, dvoen) is None)
    _kesh.clear()
    check("непознат мач не дава цена",
          ceni_za("tabletennis", "Ivan Petrov", "Georgi Dimov",
                  1788850800000, dvoen) is None)
    _kesh.clear()
    check("една позната страна НЕ стига",
          ceni_za("tabletennis", "Tomas Regner", "Georgi Dimov",
                  1788850800000, dvoen) is None)
    # 🔴 ДВА ЕДНАКВО ДОБРИ КАНДИДАТА = ОТКАЗ. Без този тест мутацията
    # «не отказвай при двусмислие» оставаше зелена: нищо не строеше две
    # еднакво силни съвпадения.
    _kesh.clear()
    _dve = {"data": {"blocks": [{"events": [
        {"participants": [{"name": "Томас Регнер"},
                          {"name": "Адам Свобода"}],
         "startTime": 1788850800000, "url": "/koefitsienti/a/1/",
         "markets": [{"handicap": 0.0, "selections": [
             {"name": "Томас Регнер", "price": 2.40},
             {"name": "Адам Свобода", "price": 1.55}]}]},
        {"participants": [{"name": "Томас Регнер"},
                          {"name": "Адам Свобода"}],
         "startTime": 1788850800000, "url": "/koefitsienti/b/2/",
         "markets": [{"handicap": 0.0, "selections": [
             {"name": "Томас Регнер", "price": 3.10},
             {"name": "Адам Свобода", "price": 1.31}]}]}]}]}}

    def dva(rq, timeout=None):
        u = rq.full_url
        pitani.append(u)
        telo = _dve if "/sport/x/1/" in u else _dyrvo

        class F(object):
            def read(self_inner):
                return json.dumps(telo).encode("utf-8")

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return F()

    check("два еднакво добри мача НЕ дават цена — отказва се",
          ceni_za("tabletennis", "Tomas Regner", "Adam Svoboda",
                  1788850800000, dva) is None)

    _kesh.clear()
    check("ima_go казва ДА за познат мач",
          ima_go("tabletennis", "Tomas Regner", "Adam Svoboda",
                 1788850800000, dvoen) is True)
    _kesh.clear()
    check("ima_go казва НЕ ЗНАМ при отказ",
          ima_go("tabletennis", "Tomas Regner", "Adam Svoboda",
                 1788850800000, otkaz) is None)

    # ── ръчките
    check("прозорецът е в разумни граници", 0 <= PROZOREC <= 360)
    check("таванът е в разумни граници", 0 <= TAVAN_TURNIRI <= 60)
    check("подписът е нашият, не преправен браузър",
          "greenpicks-bot" in UA and "Mozilla" not in UA)
    check("самопроверката НЕ пипна чужд сайт",
          all(u.startswith("https://www.betano.bg/") for u in pitani))
    check("броячът е броил", statistika()["zayavki"] > 0)

    print("САМОПРОВЕРКА НА BETANO: "
          + str(ok) + " наред, " + str(len(bad))
          + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    if "--selftest" in sys.argv or "selftest" in sys.argv:
        sys.exit(selftest())
    # Живо пускане: само измерва и печата. Нищо не праща, нищо не записва.
    for _sp in ("tabletennis", "hockey", "football"):
        _t = turniri(_sp)
        _e = sabitiya(_sp)
        print("%-13s турнири: %s · събития с коефициент: %s"
              % (_sp,
                 "НЕ МОЖАХ" if _t is NEPITAN else len(_t),
                 "НЕ МОЖАХ" if _e is NEPITAN else len(_e)))
        if isinstance(_e, list):
            for _x in _e[:4]:
                print("   %-26s %-26s %.2f / %.2f"
                      % (str(_x[0])[:26], str(_x[1])[:26], _x[3], _x[4]))
    print("заявки: %d (провалени %d)"
          % (statistika()["zayavki"], statistika()["provali"]))
