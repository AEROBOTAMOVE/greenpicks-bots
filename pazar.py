# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ПАЗАРНАТА ЦЕНА 📊

Един въпрос: КОЛКО ПЛАЩА ПАЗАРЪТ за изхода, който ние сочим?

ЗАЩО СЪЩЕСТВУВА
Собственикът: „не искам нищо наум — трябва да намериш начин". Начинът е
ДЪЛБОКИЯТ слой на ESPN, не онзи, който ботът ползва досега.

  site.api.espn.com/.../scoreboard      → коефициенти САМО за футбола
  sports.core.api.espn.com/v2/sports/… → и за бейзбол, и за ВНБА, и с
                                          отваряща, текуща и затваряща цена

Измерено на живо 13.08.2026:
  ⚽ футбол   DraftKings + Bet365      ✅
  ⚾ МЛБ      DraftKings               ✅   (пример: 1.91 / 2.01)
  🏀 ВНБА     DraftKings + Live        ✅
  🎾 ATP · 🥊 UFC · 🏐 волейбол · 🏀 НБА  →  нула доставчика

Тоест три от седемте спорта имат цена. Тези три са 114 от досегашните записи.

КАКВО ПРАВИМ С НЕЯ
Показваме число, НЕ реклама: няма име на оператор, няма линк, няма покана.
Пазарът казва едно, ние казваме друго — читателят вижда и двете и решава сам.
И се записва в дневника, за да може после да се отговори на единствения
въпрос, който мери качество: бием ли пазара, или само познаваме фаворити.

  python pazar.py --selftest   — проверките, без мрежа
"""
import io
import json
import os
import sys
import urllib.request

CORE = "https://sports.core.api.espn.com/v2/sports"
# Спортовете, за които ИЗМЕРЕНО има цена. Другите не се питат — заявка без
# отговор е чиста загуба от бюджета.
IMA_PAZAR = {"baseball", "basketball", "soccer"}
_kesh = {}
TIMEOUT = int((os.environ.get("PAZAR_TIMEOUT") or "12").strip() or 12)


def _json(url):
    try:
        rq = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(rq, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:                                        # noqa: BLE001
        return None


def _cena(dyal):
    """Десетичната цена от един дял (homeTeamOdds / awayTeamOdds). None ако няма.

    ESPN държи три снимки: open, current, close. Взимаме ТЕКУЩАТА, защото тя е
    цената в мига, в който картата излиза — тя е сравнимата. „close" е празна,
    докато мачът не е започнал.
    """
    if not isinstance(dyal, dict):
        return None
    for kade in ("current", "open", "close"):
        v = dyal.get(kade)
        if not isinstance(v, dict):
            continue
        ml = v.get("moneyLine")
        if isinstance(ml, dict):
            ml = ml.get("value")
        try:
            c = float(ml)
        except (TypeError, ValueError):
            continue
        # Десетична цена под 1.01 или над 100 е боклук, не оферта.
        if 1.01 <= c <= 100.0:
            return round(c, 2)
    return None


def cena_za(sport_path, liga, ev_id):
    """(цена_домакин, цена_гост, цена_равен) — всяка може да е None."""
    if not ev_id or not liga or sport_path not in IMA_PAZAR:
        return (None, None, None)
    kl = (sport_path, liga, str(ev_id))
    if kl in _kesh:
        return _kesh[kl]
    rez = (None, None, None)
    j = _json("%s/%s/leagues/%s/events/%s/competitions/%s/odds"
              % (CORE, sport_path, liga, ev_id, ev_id))
    for x in ((j or {}).get("items") or []):
        dom = _cena(x.get("homeTeamOdds"))
        gost = _cena(x.get("awayTeamOdds"))
        raven = _cena(x.get("drawOdds"))
        if dom or gost:
            rez = (dom, gost, raven)
            break
    _kesh[kl] = rez
    return rez


# ═══════════════════════════════════ ТЪРСЕНЕ ПО ИМЕНА (13.08.2026)
#
# Не всяка среща идва от ESPN. Бейзболът например се дърпа от statsapi.mlb.com
# и НЯМА ESPN номер — тоест дупката е точно там, където имаме 48 прогнози.
#
# Затова: вадим номера от ESPN scoreboard-а за същия ден, като сверяваме по
# ИМЕНА на отборите. Един запитан адрес на лига-ден (кеширан), после цената.
SITE = "https://site.api.espn.com/apis/site/v2/sports"
_index = {}


def _norm(s):
    """Име, сведено до сравнимо: малки букви, само букви и цифри."""
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def _dumi(s):
    """Множество от думите в името — за частично съвпадение."""
    return {w for w in _norm(s and str(s).lower().replace("-", " ")).split() if w}


def index_za_den(sport_path, liga, ymd):
    """{frozenset(две нормализирани имена): номер} за един ден. Кеширано."""
    kl = (sport_path, liga, ymd)
    if kl in _index:
        return _index[kl]
    idx = {}
    j = _json("%s/%s/%s/scoreboard?dates=%s" % (SITE, sport_path, liga, ymd))
    for e in ((j or {}).get("events") or []):
        for c in (e.get("competitions") or []):
            imena = []
            for x in (c.get("competitors") or []):
                tm = x.get("team") or {}
                imena.append(_norm(tm.get("displayName") or tm.get("name")
                                   or tm.get("shortDisplayName")))
            if len(imena) == 2 and all(imena):
                idx[frozenset(imena)] = str(e.get("id") or "")
    _index[kl] = idx
    return idx


def cena_po_imena(sport_path, liga, ymd, dom, gost):
    """Цената, намерена по имена вместо по номер. (дом, гост, равен).

    🔴 ПИТАТ СЕ ТРИ ДАТИ. ESPN индексира по АМЕРИКАНСКА дата, а мач в 01:40
    българско е още „вчера" при тях. Измерено: Tampa Bay Rays срещу Toronto
    Blue Jays се намира на 18.08 в ESPN, а нашата дата е 19.08 — с една дата
    цената се губеше точно за нощните мачове, а в бейзбола те са половината.
    """
    if sport_path not in IMA_PAZAR or not liga or not ymd:
        return (None, None, None)
    kl = frozenset((_norm(dom), _norm(gost)))
    if len(kl) != 2 or not all(kl):
        return (None, None, None)
    idx = {}
    try:
        from datetime import datetime as _dt, timedelta as _td
        d0 = _dt.strptime(str(ymd), "%Y%m%d")
        dati = [(d0 + _td(days=k)).strftime("%Y%m%d") for k in (0, -1, 1)]
    except ValueError:
        dati = [str(ymd)]
    # 🔴 НЕ СПИРАМЕ НА ПЪРВОТО СЪВПАДЕНИЕ (13.08.2026). Един и същи двубой
    # може да го има в индекса за две дати (нашата и американската), а цена
    # да има само за едната — букмейкърът я пуска по-късно за по-далечните.
    # Измерено: Yankees/Orioles се намира и на 18-и, и на 19-и; на 19-и
    # отговорът е items=0. Затова обхождаме всички дати и връщаме ПЪРВАТА,
    # която наистина дава число.
    ev_id = None
    for den in dati:
        idx = index_za_den(sport_path, liga, den)
        kand = idx.get(kl)
        if not kand:
            continue
        rez = cena_za(sport_path, liga, kand)
        if rez[0] or rez[1]:
            return rez
        ev_id = ev_id or kand
    if not ev_id:
        idx = index_za_den(sport_path, liga, dati[0])
        # Частично съвпадение: „Tampa Bay Rays" срещу „Rays". Търсим двойка,
        # в която И двете наши имена се съдържат в техните (или обратно).
        for k, v in idx.items():
            a, b = tuple(k)
            nd, ng = _norm(dom), _norm(gost)
            if ((nd in a or a in nd) and (ng in b or b in ng)) or                ((nd in b or b in nd) and (ng in a or a in ng)):
                ev_id = v
                break
    if not ev_id:
        return (None, None, None)
    return cena_za(sport_path, liga, ev_id)


def veroyatnost(cena):
    """Цена → вероятност. 2.00 значи 50%. None при боклук."""
    try:
        c = float(cena)
    except (TypeError, ValueError):
        return None
    return (1.0 / c) if c > 1.0 else None


def red_za_karta(nasha_p, cena_nash_izhod):
    """Редът, който излиза на картата. Празен, ако няма цена.

    Никакво име на оператор, никакъв линк, никаква покана — само две числа
    едно до друго. Думите, които пазачът реже, ги няма нарочно.
    """
    pz = veroyatnost(cena_nash_izhod)
    if pz is None:
        return ""
    try:
        nash = float(nasha_p)
    except (TypeError, ValueError):
        return ""
    # 🔴 БЕЗ КОМЕНТАР (изрична поръчка, 13.08.2026): „не казвай кво оценяваме".
    # Само числото. Читателят вижда нашия процент отгоре и пазарната цена тук,
    # и сам вижда къде се разминават. Нашата дума не му трябва.
    _ = nash, pz
    return "📊 Пазар: " + ("%.2f" % float(cena_nash_izhod))


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    check("2.00 значи 50%", abs(veroyatnost(2.0) - 0.5) < 1e-9)
    check("1.25 значи 80%", abs(veroyatnost(1.25) - 0.8) < 1e-9)
    check("цена 1.0 не дава вероятност", veroyatnost(1.0) is None)
    check("боклук не гърми", veroyatnost("абв") is None and veroyatnost(None) is None)

    check("текущата цена се чете",
          _cena({"current": {"moneyLine": {"value": 1.91}}}) == 1.91)
    check("пада на open, ако няма current",
          _cena({"open": {"moneyLine": {"value": 2.4}}}) == 2.4)
    check("плоско число също се чете",
          _cena({"current": {"moneyLine": 1.55}}) == 1.55)
    check("цена под 1.01 се отхвърля",
          _cena({"current": {"moneyLine": {"value": 1.0}}}) is None)
    check("цена над 100 се отхвърля",
          _cena({"current": {"moneyLine": {"value": 250}}}) is None)
    check("празен дял не гърми", _cena({}) is None and _cena(None) is None)
    check("американски формат не се бърка за десетичен",
          _cena({"current": {"moneyLine": {"value": -110}}}) is None)

    check("спорт без пазар не се пита",
          cena_za("tennis", "atp", "123") == (None, None, None))
    check("липсващ номер не се пита",
          cena_za("baseball", "mlb", "") == (None, None, None))

    r = red_za_karta(0.62, 2.00)
    check("редът казва цената", "2.00" in r)
    check("редът е само число", r.count(" ") <= 2)
    check("редът НЕ коментира нашата оценка",
          not any(w in r for w in ("оценяваме", "по-високо", "по-ниско", "колкото")))
    check("еднакъв ред при различна наша оценка",
          red_za_karta(0.51, 2.00) == red_za_karta(0.90, 2.00))
    check("цената се закръгля до два знака", "1.91" in red_za_karta(0.5, 1.9123))
    check("без цена няма ред", red_za_karta(0.62, None) == "")
    check("боклук вместо наша вероятност не гърми",
          red_za_karta("абв", 2.0) == "")

    # 🔴 НАЙ-ВАЖНОТО: редът не бива да носи име на оператор, линк или покана.
    # Пазачът в predictor.py реже точно тези думи, защото българският закон
    # забранява рекламата на хазарт.
    zabraneni = ("draftkings", "bet365", "sportsbook", "http", "залож",
                 "букмейкър", "коеф", "odds", "залагай")
    for nasha, cena in ((0.62, 2.0), (0.40, 2.0), (0.51, 2.0), (0.90, 1.05)):
        red = red_za_karta(nasha, cena).lower()
        for z in zabraneni:
            check("редът е чист от " + z, z not in red)

    # Търсене по имена — без мрежа, с подхвърлен индекс.
    _star = globals().get("index_za_den")
    try:
        globals()["index_za_den"] = lambda s, l, y: {
            frozenset(("tampabayrays", "torontobluejays")): "401"}
        globals()["cena_za"] = lambda s, l, e: ((2.10, 1.75, None)
                                                if e == "401" else (None, None, None))
        check("точното име намира мача",
              cena_po_imena("baseball", "mlb", "20260813",
                            "Tampa Bay Rays", "Toronto Blue Jays")[0] == 2.10)
        check("разменените страни пак намират мача",
              cena_po_imena("baseball", "mlb", "20260813",
                            "Toronto Blue Jays", "Tampa Bay Rays")[0] == 2.10)
        check("късото име също намира",
              cena_po_imena("baseball", "mlb", "20260813",
                            "Rays", "Blue Jays")[0] == 2.10)
        check("мач от предния ден по американско време също се намира",
              cena_po_imena("baseball", "mlb", "20260814",
                            "Tampa Bay Rays", "Toronto Blue Jays")[0] == 2.10)
        check("непознат мач не дава цена",
              cena_po_imena("baseball", "mlb", "20260813", "А", "Б") == (None, None, None))
        check("еднакви имена не дават цена",
              cena_po_imena("baseball", "mlb", "20260813", "Rays", "Rays")
              == (None, None, None))
        check("спорт без пазар не се пита",
              cena_po_imena("tennis", "atp", "20260813", "A", "B") == (None, None, None))
    finally:
        if _star is not None:
            globals()["index_za_den"] = _star

    check("броят проверки е поне 25", ok >= 25)
    print("САМОПРОВЕРКА НА ПАЗАРА: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(selftest())
