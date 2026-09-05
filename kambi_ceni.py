# -*- coding: utf-8 -*-
"""
KAMBI — КОЕФИЦИЕНТИ ОТ МАСОВА КНИГА, ПО ТУРНИР 🎯

Защо съществува (измерено живо 05.09.2026):

    предсказателят пуска 1472 карти, 829 с коефициент (56%), 643 БЕЗ (44%)
      тенис на маса : 328 карти, 55 с коефициент  ← 273 без
      волейбол      : 233 карти, 72 с коефициент  ← 161 без

А те СА заложими. Каталогът на собственика от bet365 изрежда дословно
«World Table Tennis — Grand Smashes; Champions; Star Contender; Contender;
Feeder». Липсва не пазарът, а ЧИСЛОТО.

🔴 ЗАЩО СПИСЪКЪТ НА KAMBI НЕ СТИГАШЕ. `listView/<спорт>.json` е «предстоящи
скоро», не каталог. Измерено в един и същ миг:

    listView/table_tennis.json   ->  32 събития (всичките Czech Liga Pro)
    дървото group.json           ->  85 събития, вкл. WTT Contender Almaty
    listView/volleyball.json     ->   7 събития
    дървото                      ->  90, вкл. European Championship (61)

Затова тук се пита ДЪРВОТО, вадят се турнирите и всеки се тегли поотделно.
Проверено живо, същия миг:

    volleyball/european_championship__w_  ->  Poland (W) - Serbia (W)  2.65 / 1.42
    volleyball/asian_championship         ->  Iran - India             1.05 / 9.50
    table_tennis/wtt_contender_almaty     ->  Togami - Gauzy           1.40 / 2.72

🔴 ЦЕНАТА Е ЦЯЛО ЧИСЛО × 1000. 1780 значи 1.78. Забравено деление превръща
всяка вероятност в 0.0006 — този капан вече е описан в tt_ligi.py.

🔴 РАЗДЕЛИТЕЛЯТ В ИМЕТО Е „ - ", НЕ „ vs ". И в имената има запетаи
(«Strnad, Jaroslav (1964)»), затова страните се четат от ИЗХОДИТЕ на
пазара (`outcome.label`), а името на събитието служи само за ред.

🔴 СЕНТИНЕЛ, НЕ ПРАЗЕН СПИСЪК. Мрежов отказ връща `NEPITAN`; честно празен
турнир връща []. Слеят ли се, паднал източник се представя за «няма мачове»
— клас дефекти, който в този проект вече е струвал дни мълчание.

🔴 БЮДЖЕТ. Едно питане за дървото на спорт + по едно на турнир, с таван.
Кешът пази САМО успех: празно от провал не бива да заключва спорта за
целия рън.

ПЪТ НАЗАД: `KAMBI_CENI=0` изключва целия модул; всичко се връща както е било.
Проверка: `python kambi_ceni.py --selftest`
"""
import io
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request

# ═════════════════════════════════════════ РЪЧКИТЕ
VKLYUCHENO = (os.environ.get("KAMBI_CENI", "1") or "1").strip() not in (
    "0", "false", "не")
OPERATOR = (os.environ.get("KAMBI_OPERATOR") or "ubuk").strip() or "ubuk"
PAZAR = (os.environ.get("KAMBI_PAZAR") or "BG").strip() or "BG"
try:
    TAVAN_TURNIRI = max(0, min(40, int(
        (os.environ.get("KAMBI_TAVAN_TURNIRI") or "8").strip() or 8)))
except ValueError:
    TAVAN_TURNIRI = 8
try:
    TAIMAUT = max(5, min(60, int((os.environ.get("KAMBI_TAIMAUT") or "20").strip()
                                 or 20)))
except ValueError:
    TAIMAUT = 20

UA = "greenpicks-bot/1.0 (+github.com/AEROBOTAMOVE/greenpicks-bots)"
BAZA = "https://eu-offering-api.kambicdn.com/offering/v2018/" + OPERATOR + "/"
OPASHKA = "?lang=en_GB&market=" + PAZAR + "&client_id=2&channel_id=1"

# 🔴 «НЕ МОЖАХ ДА ПИТАМ» Е ОТГОВОР, РАЗЛИЧЕН ОТ «НЯМА МАЧОВЕ».
NEPITAN = object()

# Нашите кошници -> имената на Kambi. Само спортове, които наистина пускаме.
SPORT = {
    "tabletennis": "table_tennis",
    "volleyball": "volleyball",
    "tennis": "tennis",
    "football": "football",
    "basketball": "basketball",
    "baseball": "baseball",
    "hockey": "ice_hockey",
    "amfootball": "american_football",
    "rugby": "rugby_union",
    "esports": "esports",
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
    rq = urllib.request.Request(url, headers={"User-Agent": UA})
    return otv(rq, timeout=TAIMAUT).read()


def _json(url, otvarach=None):
    """Разчетеният отговор, или NEPITAN при какъвто и да е отказ."""
    try:
        b = _vzemi(url, otvarach)
    except Exception:                                        # noqa: BLE001
        _STAT["provali"] += 1
        return NEPITAN
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:                                        # noqa: BLE001
        _STAT["provali"] += 1
        return NEPITAN


# ═════════════════════════════════════════ ИМЕНАТА
def _sgani(s):
    """Без ударения и без кирилски украси — за сравнение, не за показване."""
    t = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in t if not unicodedata.combining(c))


def dumi(s):
    """Думите с 4+ букви. Инициалите падат сами.

    Четири, а не три: «Ann» се среща в много имена, «Callejon» различава.
    Същият праг като в `pinnacle._dumi4` — нарочно, за да не се разминат
    двата пътя при един и същи мач.
    """
    d = set()
    for w in re.split(r"[\s\-\.,/()]+", _sgani(s).lower()):
        # 🔴 САМО ЛАТИНИЦА И ЦИФРИ. Kambi пише на латиница; кирилско име
        # («Иран») не може да съвпадне с нищо там и само би създало илюзия,
        # че е сравнено. Преводът е работа на викащия — предсказателят има
        # BG_NAME точно за това. Празният отговор тук КАЗВА «преведи ме».
        w = "".join(c for c in w if ("a" <= c <= "z") or c.isdigit())
        if len(w) >= 4:
            d.add(w)
    return d


def _dvoyka_ot_izhodi(bo):
    """(дом, гост) от ИЗХОДИТЕ на пазара, не от името на събитието.

    Името съдържа запетаи («Strnad, Jaroslav (1964)») и цепенето по тях
    руши имена. Изходите носят по едно чисто име всеки.
    """
    oc = [o for o in (bo.get("outcomes") or [])
          if str(o.get("type") or "") != "OT_DRAW"]
    if len(oc) < 2:
        return None
    a = str(oc[0].get("label") or oc[0].get("englishLabel") or "")
    b = str(oc[1].get("label") or oc[1].get("englishLabel") or "")
    return (a, b) if a and b else None


def _koef(o):
    """Kambi дава ЦЯЛО ЧИСЛО × 1000. 1780 значи 1.78."""
    try:
        v = float(o.get("odds"))
    except (TypeError, ValueError):
        return None
    v = v / 1000.0
    return v if 1.0 < v < 1000.0 else None


# ═════════════════════════════════════════ ДЪРВОТО И ТУРНИРИТЕ
def _vazel(n, tyrsen):
    """Възелът на спорта в дървото, заедно с пътя дотам."""
    if not isinstance(n, dict):
        return None
    tk = str(n.get("termKey") or "")
    if tk == tyrsen:
        return n, [tk]
    for c in (n.get("groups") or []):
        r = _vazel(c, tyrsen)
        if r:
            v, p = r
            return v, ([tk] + p if tk else p)
    return None


def turniri(sport, otvarach=None):
    """Пътищата на турнирите с поне едно събитие. NEPITAN при отказ.

    🔴 ПОДРЕДЕНИ ПО БРОЙ СЪБИТИЯ. Таванът реже от опашката, тоест първо се
    харчат заявки за турнирите, които носят най-много мачове.
    """
    kl = ("turniri", sport)
    if kl in _kesh:
        return _kesh[kl]
    ime = SPORT.get(str(sport) or "")
    if not ime:
        return []
    d = _json(BAZA + "group.json" + OPASHKA, otvarach)
    if d is NEPITAN:
        return NEPITAN
    r = _vazel((d or {}).get("group") or d, ime)
    if not r:
        return []
    vazel, _pat = r
    nam = []

    def obhod(n, pat):
        tk = str(n.get("termKey") or "")
        p = pat + [tk] if tk else pat
        deca = n.get("groups") or []
        br = n.get("eventCount") or 0
        if not deca:
            if br:
                nam.append(("/".join(p), int(br)))
            return
        for c in deca:
            obhod(c, p)

    for c in (vazel.get("groups") or []):
        obhod(c, [ime])
    if not nam and (vazel.get("eventCount") or 0):
        nam.append((ime, int(vazel.get("eventCount") or 0)))
    nam.sort(key=lambda x: -x[1])
    _kesh[kl] = nam
    return nam


def sabitiya(sport, otvarach=None):
    """[(дом, гост, начало, коеф_дом, коеф_гост)] за спорта. NEPITAN при отказ.

    🔴 КЕШИРА СЕ САМО УСПЕХ. Празно от провал би заключило спорта за целия
    рън и би се представило за «няма мачове».
    """
    kl = ("sab", sport)
    if kl in _kesh:
        return _kesh[kl]
    t = turniri(sport, otvarach)
    if t is NEPITAN:
        return NEPITAN
    if not t:
        return []
    nam = []
    otkazi = 0
    for pat, _br in t[:TAVAN_TURNIRI]:
        d = _json(BAZA + "listView/" + pat + ".json" + OPASHKA, otvarach)
        if d is NEPITAN:
            otkazi += 1
            continue
        for e in ((d or {}).get("events") or []):
            ev = e.get("event") or {}
            for bo in (e.get("betOffers") or []):
                dv = _dvoyka_ot_izhodi(bo)
                if not dv:
                    continue
                oc = [o for o in (bo.get("outcomes") or [])
                      if str(o.get("type") or "") != "OT_DRAW"]
                c1, c2 = _koef(oc[0]), _koef(oc[1])
                if not (c1 and c2):
                    continue
                nam.append((dv[0], dv[1], str(ev.get("start") or ""), c1, c2))
                break
    if otkazi and not nam:
        return NEPITAN            # всичко падна — това НЕ е «няма мачове»
    _kesh[kl] = nam
    return nam


def ceni_za(sport, dom, gost, otvarach=None):
    """(коеф_дом, коеф_гост) или None. NEPITAN, ако изворът е отказал.

    🔴 СЪВПАДЕНИЕТО ИСКА И ДВЕТЕ СТРАНИ. Една обща фамилия е свързала чужд
    мач в този проект и преди («Bury FC» срещу «Sporting Kansas City»).
    """
    ev = sabitiya(sport, otvarach)
    if ev is NEPITAN:
        return NEPITAN
    h, a = dumi(dom), dumi(gost)
    if not (h and a):
        return None
    for A, B, _st, c1, c2 in ev:
        da, db = dumi(A), dumi(B)
        if (h & da) and (a & db):
            return (c1, c2)
        if (h & db) and (a & da):
            return (c2, c1)       # обърнати страни — връщаме В НАШИЯ ред
    return None


def ima_go(sport, dom, gost, otvarach=None):
    """Има ли изобщо такъв мач при масовата книга. None при отказ."""
    r = ceni_za(sport, dom, gost, otvarach)
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

    check("коефициентът се дели на 1000", _koef({"odds": 1780}) == 1.78)
    check("боклучав коефициент пада", _koef({"odds": "х"}) is None)
    check("коефициент под 1.00 пада", _koef({"odds": 900}) is None)
    check("липсващ коефициент пада", _koef({}) is None)

    check("думите са с 4+ букви", dumi("S. Doumbia") == {"doumbia"})
    check("запетаята не руши име",
          dumi("Strnad, Jaroslav (1964)") == {"strnad", "jaroslav", "1964"})
    check("ударенията се свалят", "genevesarvette" not in dumi("Genève"))
    check("кирилица не дава думи", dumi("Иран") == set())

    _bo = {"outcomes": [{"label": "Iran", "odds": 1050},
                        {"label": "India", "odds": 9500}]}
    check("страните идват от изходите", _dvoyka_ot_izhodi(_bo) == ("Iran", "India"))
    check("равният не се брои за страна",
          _dvoyka_ot_izhodi({"outcomes": [
              {"label": "A", "odds": 2000},
              {"label": "X", "odds": 3000, "type": "OT_DRAW"},
              {"label": "B", "odds": 2500}]}) == ("A", "B"))
    check("един изход не прави двойка",
          _dvoyka_ot_izhodi({"outcomes": [{"label": "A", "odds": 2000}]}) is None)

    # --- подложен извор, нула мрежа
    DYRVO = json.dumps({"group": {"termKey": "", "groups": [
        {"termKey": "volleyball", "name": "Volleyball", "eventCount": 90,
         "groups": [
             {"termKey": "european_championship__w_", "eventCount": 2},
             {"termKey": "asian_championship", "eventCount": 3},
             {"termKey": "prazen", "eventCount": 0}]},
        {"termKey": "table_tennis", "name": "Table Tennis", "eventCount": 1,
         "groups": [{"termKey": "wtt_contender_almaty", "eventCount": 1}]}]}})
    SPISAK = {
        "volleyball/european_championship__w_": json.dumps({"events": [
            {"event": {"name": "Poland (W) - Serbia (W)",
                       "start": "2026-09-06T13:00:00Z"},
             "betOffers": [{"outcomes": [
                 {"label": "Poland (W)", "odds": 2650},
                 {"label": "Serbia (W)", "odds": 1420}]}]}]}),
        "volleyball/asian_championship": json.dumps({"events": [
            {"event": {"name": "Iran - India", "start": "2026-09-06T01:00:00Z"},
             "betOffers": [{"outcomes": [
                 {"label": "Iran", "odds": 1050},
                 {"label": "India", "odds": 9500}]}]}]}),
        "table_tennis/wtt_contender_almaty": json.dumps({"events": [
            {"event": {"name": "Shunsuke Togami - Simon Gauzy",
                       "start": "2026-09-06T07:30:00Z"},
             "betOffers": [{"outcomes": [
                 {"label": "Shunsuke Togami", "odds": 1400},
                 {"label": "Simon Gauzy", "odds": 2720}]}]}]}),
    }

    class _Otg(object):
        def __init__(self, t):
            self._t = t.encode("utf-8")

        def read(self):
            return self._t

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    pitani = []

    def podlozhka(rq, timeout=None):
        u = rq.full_url if hasattr(rq, "full_url") else str(rq)
        pitani.append(u)
        if "group.json" in u:
            return _Otg(DYRVO)
        for pat, telo in SPISAK.items():
            if "listView/" + pat + ".json" in u:
                return _Otg(telo)
        return _Otg('{"events": []}')

    _kesh.clear()
    _nulirai_stat()
    t = turniri("volleyball", podlozhka)
    check("турнирите се намират в дървото", len(t) == 2)
    check("празният турнир не влиза",
          not [x for x in t if x[0].endswith("prazen")])
    check("подредени по брой събития", t[0][1] >= t[1][1])
    check("пътят е пълен",
          t[0][0].startswith("volleyball/"))

    ev = sabitiya("volleyball", podlozhka)
    check("събитията се събират от ВСИЧКИ турнири", len(ev) == 2)
    check("коефициентите са разделени",
          any(abs(c1 - 2.65) < 1e-9 for _a, _b, _s, c1, _c2 in ev))

    check("цената се намира по фамилии",
          ceni_za("volleyball", "Poland", "Serbia", podlozhka) == (2.65, 1.42))
    check("обърнатите страни се връщат В НАШИЯ ред",
          ceni_za("volleyball", "Serbia", "Poland", podlozhka) == (1.42, 2.65))
    check("непознат мач дава None",
          ceni_za("volleyball", "Никой", "Другият", podlozhka) is None)
    # 🔴 ЕДНАТА СТРАНА НЕ СТИГА. «Poland» го има, «Brazil» — не. Обща
    # фамилия вече е лепила чужд мач в този проект; затова се иска И ДВЕТЕ.
    check("съвпадение само по ЕДНАТА страна НЕ минава",
          ceni_za("volleyball", "Poland", "Brazil", podlozhka) is None)
    check("и в обратния ред също не минава",
          ceni_za("volleyball", "Brazil", "Serbia", podlozhka) is None)
    check("ima_go казва да", ima_go("volleyball", "Iran", "India", podlozhka) is True)
    check("ima_go казва не", ima_go("volleyball", "Iran", "Полша", podlozhka) is False)

    _kesh.clear()
    check("WTT СЕ НАМИРА — заради това е целият модул",
          ceni_za("tabletennis", "Shunsuke Togami", "Simon Gauzy",
                  podlozhka) == (1.4, 2.72))

    # 🔴 ПРОВАЛЪТ НЕ Е «НЯМА МАЧОВЕ»
    def padashta(rq, timeout=None):
        raise urllib.error.URLError("мрежата я няма")

    _kesh.clear()
    _nulirai_stat()
    check("паднало дърво дава сентинел", turniri("volleyball", padashta) is NEPITAN)
    check("паднал извор дава сентинел",
          sabitiya("volleyball", padashta) is NEPITAN)
    check("и цената носи сентинела",
          ceni_za("volleyball", "Poland", "Serbia", padashta) is NEPITAN)
    check("ima_go при отказ дава None",
          ima_go("volleyball", "Poland", "Serbia", padashta) is None)
    check("провалите се броят", statistika()["provali"] >= 1)

    # провал СЛЕД успешно дърво: част от турнирите падат, но има мачове
    _kesh.clear()
    sostoyanie = {"n": 0}

    def polovin(rq, timeout=None):
        u = rq.full_url if hasattr(rq, "full_url") else str(rq)
        if "group.json" in u:
            return podlozhka(rq, timeout)
        sostoyanie["n"] += 1
        if sostoyanie["n"] == 1:
            raise urllib.error.URLError("един турнир падна")
        return podlozhka(rq, timeout)

    ev2 = sabitiya("volleyball", polovin)
    check("един паднал турнир НЕ трие останалите",
          isinstance(ev2, list) and len(ev2) == 1)

    # 🔴 ПАДНАХА ВСИЧКИТЕ — ТОВА НЕ Е «НЯМА МАЧОВЕ». Първата ми проверка
    # мереше «един падна» и мутацията «махни сентинела» остана зелена.
    _kesh.clear()

    def vsichki_padat(rq, timeout=None):
        u = rq.full_url if hasattr(rq, "full_url") else str(rq)
        if "group.json" in u:
            return podlozhka(rq, timeout)
        raise urllib.error.URLError("всеки турнир пада")

    check("всички паднали турнири дават СЕНТИНЕЛ, не празно",
          sabitiya("volleyball", vsichki_padat) is NEPITAN)
    check("и този провал НЕ влиза в кеша",
          ("sab", "volleyball") not in _kesh)

    # кешът пази само успех
    _kesh.clear()
    _nulirai_stat()
    sabitiya("volleyball", padashta)
    check("провалът НЕ влиза в кеша", ("sab", "volleyball") not in _kesh)
    ev3 = sabitiya("volleyball", podlozhka)
    check("след провала се пита ПАК", isinstance(ev3, list) and len(ev3) == 2)

    # непознат спорт
    _kesh.clear()
    check("непознат спорт дава празно", turniri("кегли", podlozhka) == [])
    check("и цена за него няма",
          ceni_za("кегли", "А", "Б", podlozhka) is None)

    # ръчката
    check("ръчката се чете", isinstance(VKLYUCHENO, bool))
    check("таванът е разумен", 0 <= TAVAN_TURNIRI <= 40)
    check("операторът не е празен", bool(OPERATOR))

    # никаква мрежа не е пипана
    check("самопроверката НЕ пипна мрежата",
          all(u.startswith("https://eu-offering-api.kambicdn.com/")
              for u in pitani))

    print("САМОПРОВЕРКА НА KAMBI: " + str(ok) + " наред, " + str(len(bad))
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
    for _sp in ("tabletennis", "volleyball"):
        _t = turniri(_sp)
        _e = sabitiya(_sp)
        print("%-14s турнири: %s · събития с коефициент: %s"
              % (_sp,
                 "НЕ МОЖАХ" if _t is NEPITAN else len(_t),
                 "НЕ МОЖАХ" if _e is NEPITAN else len(_e)))
        if isinstance(_e, list):
            for _x in _e[:5]:
                print("   %-28s %-28s %.2f / %.2f"
                      % (str(_x[0])[:28], str(_x[1])[:28], _x[3], _x[4]))
    print("заявки: %d (провалени %d)" % (statistika()["zayavki"],
                                         statistika()["provali"]))
