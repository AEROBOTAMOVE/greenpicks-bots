#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — РЪГБИ ЮНИЪН 🏉

Един въпрос: кой ръгби мач можем да преценим САМИ, а не да преповторим
цената на пазара?

ЗАЩО СЪЩЕСТВУВА ТОЗИ ФАЙЛ
=========================
Ръгбито беше ЦЯЛ НЕПИТАН СПОРТ. `grep -ril "rugby" --include=*.py` върна
нула файла. А:

  · ESPN дава 25 ръгби лиги на `sports/rugby/{id}/scoreboard`
  · каталогът на собственика го слага в ЗЕЛЕНИЯ списък („top rugby",
    раздел V) и изрежда пет лиги поименно
  · Pinnacle има id=27 „Rugby Union": 13 мача днес, 6 от 6 с цена

Тоест имаме и мачове, и история, и цена — трите неща, без които спорт не
бива да излиза.

ИЗМЕРЕНО НА ЖИВО (02.09.2026, всяко число е пуснато, не спомнено)
=================================================================
Прозорец 05–25.09 напред и 01.01–04.09 назад, петте лиги:

    лига                       напред   изиграни   точки/отбор/мач
    Топ 14, Франция                22         12          30.5
    НПС, Нова Зеландия             19         36          30.6
    Тестови мачове                  4          6          26.9
    Висша лига, Англия              0          8          28.8
    Обединено първенство            0          3          19.5

    Pinnacle същия ден: France Top 14 (6), NPC (4), International (3)

И КОНСТАНТИТЕ НА МОДЕЛА, измерени върху 639 ИЗИГРАНИ мача:
    предимство на домакина   +7.48 точки
    разсейване на разликата  σ = 21.85 точки
    среден сбор              55.3 точки
    домакинът печели         417 от 639 = 65%

🔴 σ = 21.85 Е ГОЛЯМО и това е важно. При американския футбол е 13.5. Тоест
ръгбито е ПО-НЕПРЕДВИДИМО от вида си: разлика от 7 точки при σ 21.85 дава
едва 63% за домакина. Който сложи по-малко σ, ще произведе фалшива
увереност — затова числото стои тук с извадката си.

КОЯ ЛИГА НЕ ВЛИЗА И ЗАЩО
========================
289279 „URBA Top 14" дава 14 мача в прозореца и изглежда точно като
френската. Но това е АМАТЬОРСКО клубно ръгби на Буенос Айрес (Los Matreros,
Alumni, SIC, Newman). Каталогът я няма, а раздел V слага „Amateur/regional
competitions without reliable statistics" в ЧЕРВЕНО. Който добави „всичките
25 лиги на ESPN", внася и нея.

ЗАЩО ИСТОРИЯТА НЕ Е ПО ОТБОРИ
=============================
Обичайният път `/{sport}/{slug}/teams/{id}/schedule` за ръгби връща HTTP 500
(проверено: 12 от 12 заявки, 6 отбора, 3 лиги, два сезона). Затова историята
идва от ДИАПАЗОНЕН scoreboard: ЕДНА заявка на лига носи целия прозорец, а
отборите се вадят от нея. По-евтино е и от работещия път — 3 заявки вместо
по две на мач.

ПЪТ НАЗАД
=========
`PREDICT_RAGBI=0` изключва целия файл.
"""
import datetime as _dt
import io
import json
import os
import sys
import urllib.error
import urllib.request

# ───────────────────────────────────────────────────────────── УСТРОЙСТВО
NASH_KLYUCH = "rugby"
EMOJI = "🏉"

VKLYUCHENO = (os.environ.get("PREDICT_RAGBI") or "1").strip() not in (
    "0", "false", "no", "не")

# 🔴 ЧЕСТЕН ПОДПИС. Не се преправям на браузър пред чужд извор.
UA = "greenpicks-bot/1.0 (+github.com/AEROBOTAMOVE/greenpicks-bots)"
TIMEOUT = int((os.environ.get("RAGBI_TIMEOUT") or "25").strip() or 25)
ESPN = "https://site.api.espn.com/apis/site/v2/sports/rugby"

# (id, тежест, българско име, ред от каталога — доказателството)
LIGI = [
    ("270559", 8, "Топ 14, Франция",
     "RECURRING | France | Top 14; Pro D2"),
    ("267979", 8, "Висша лига, Англия",
     "CORE | England | Premiership Rugby"),
    ("270557", 7, "Обединено първенство",
     "RECURRING | Europe/South Africa | United Rugby Championship"),
    ("289234", 9, "Тестови мачове",
     "RECURRING | International | test matches and tours"),
    ("270563", 5, "НПС, Нова Зеландия",
     "RECURRING | New Zealand | National Provincial Championship"),
]

# 🔴 НАРОЧНО ИЗВЪН СПИСЪКА. Дава 14 мача и изглежда като френската Топ 14,
# но е АМАТЬОРСКО клубно ръгби на Буенос Айрес. Каталогът я няма; раздел V
# я слага в червено. Стои поименно, за да не влезе утре по невнимание.
NE_VLIZAT = {"289279": "URBA Top 14 — аматьорска, Раздел V"}

# ── константите на модела, измерени върху 639 изиграни мача (02.09.2026)
HOME_TOCHKI = float((os.environ.get("RAGBI_HOME") or "7.5").strip() or 7.5)

# 🔴 ЕДНА ЛИГА ОТХВЪРЛЯ ОБЩОТО ЧИСЛО (измерено 05.09.2026, 1107 мача от
# ESPN, неутралните извадени — за ръгби `neutralSite` е нула навсякъде):
#
#     Top 14        287 мача  +8.98  [ +6.90 … +11.07]   7.5 вътре
#     Premiership   186 мача  +7.10  [ +3.97 … +10.23]   7.5 вътре
#     URC           258 мача  +7.69  [ +5.66 …  +9.73]   7.5 вътре
#     Тестови       184 мача  +4.49  [ -0.53 …  +9.51]   7.5 вътре
#     NPC           192 мача  +3.57  [ +0.76 …  +6.39]   7.5 ИЗВЪН ←
#     общо         1107 мача  +6.68  [ +5.36 …  +8.00]
#
# Мени се САМО оборената. За другите четири разлика НЕ Е доказана, а да им
# сложа точковите оценки значи да заменя измерена константа с шум — при
# «Тестови» интервалът е широк десет точки.
#
# НЕ Е ДРЕБНО: 5 от 13-те мача на днешната дъска са от NPC.
HOME_PO_LIGI = {"270563": 3.57}     # NPC (Нова Зеландия)


def home_tochki(lid):
    """Домакинското предимство в точки за тази лига.

    Общото 7.5 важи, докато лигата не го ОБОРИ с интервал. Виж таблицата
    по-горе: това е разлика в ТОЧКИ, не честота на домакински победи.
    """
    return HOME_PO_LIGI.get(str(lid or ""), HOME_TOCHKI)
SIGMA = float((os.environ.get("RAGBI_SIGMA") or "21.85").strip() or 21.85)
# Колко мача трябва да има отбор, за да го смятаме. Ръгбито играе рядко —
# Топ 14 е 26 мача за сезон — затова прагът е 3, не 5 като при хокея.
MIN_MACHOVE = int((os.environ.get("RAGBI_MIN") or "3").strip() or 3)

CHASOVE = int((os.environ.get("RAGBI_CHASOVE") or "168").strip() or 168)
TAVAN = int((os.environ.get("RAGBI_TAVAN") or "40").strip() or 40)
# Колко назад се гледа за история. 300 дни хваща и предишния сезон.
DNI_NAZAD = int((os.environ.get("RAGBI_DNI") or "300").strip() or 300)

# 🔴 „НЕ МОЖАХ ДА ПИТАМ" НЕ Е „НЯМА МАЧОВЕ". Същият сентинел като при хокея.
NEPITAN = object()

_zayavki = [0]
_provali = [0]
_kesh = {}


def broi_zayavki():
    """Колко заявки е направил ТОЗИ файл. Самопроверката иска нула."""
    return _zayavki[0]


def broi_provali():
    """Колко от тях са се провалили."""
    return _provali[0]


def nuliray():
    """Чисти броячите и кеша."""
    _zayavki[0] = 0
    _provali[0] = 0
    _kesh.clear()


# ───────────────────────────────────────────────────────────────── МРЕЖА
def _vzemi(url):
    """JSON от адрес. None при какъвто и да е провал. Провалът СЕ БРОИ."""
    _zayavki[0] += 1
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}),
            timeout=TIMEOUT)
        b = r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        _provali[0] += 1
        return None
    try:
        return json.loads(b.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        _provali[0] += 1
        return None


def _tablo(liga, ot, do, vzemi=None):
    """Едно табло за период. Кеширано: същият прозорец не се пита два пъти.

    🔴 ДИАПАЗОН, НЕ ДЕН. ESPN приема `dates=ГГГГММДД-ГГГГММДД` за ръгбито и
    връща целия прозорец с ЕДНА заявка — измерено: 639 изиграни мача от пет
    лиги с десет заявки. По ден щеше да са стотици.
    """
    vz = vzemi if callable(vzemi) else _vzemi
    k = (str(liga), ot, do)
    if k in _kesh:
        return _kesh[k]
    d = vz(ESPN + "/" + str(liga) + "/scoreboard?dates=" + ot + "-" + do)
    _kesh[k] = d
    return d


# ────────────────────────────────────────────────────────────── ЧЕТЕНЕ
def _sastoyanie(ev):
    return str((((ev or {}).get("status") or {}).get("type") or {}).get("state") or "")


def _strani(ev):
    """(дом, гост, точки_дом, точки_гост, номер_дом, номер_гост). None при липса.

    🔴 НОМЕРАТА СА ЗАДЪЛЖИТЕЛНИ, не украса. Оценителят сверява мача по тях,
    защото „имената се различават между източниците, id-тата не"
    (scorer.rezultat_espn). Карта с име вместо номер излиза и НИКОГА не се
    оценява — а неоценима карта не бива да излиза изобщо.
    Проверено живо: ESPN дава на ръгбито стабилни номера (Bayonne 25912,
    Toulon 25986, Castres 25916, Vannes 289337).
    """
    c = ((ev or {}).get("competitions") or [{}])[0] or {}
    dom = gost = None
    td = tg = None
    nd = ng = ""
    for t in (c.get("competitors") or []):
        tm = t.get("team") or {}
        ime = str((tm.get("displayName") or tm.get("name") or "")).strip()
        nom = str(tm.get("id") or "").strip()
        try:
            s = float(t.get("score"))
        except (TypeError, ValueError):
            s = None
        if t.get("homeAway") == "home":
            dom, td, nd = ime, s, nom
        elif t.get("homeAway") == "away":
            gost, tg, ng = ime, s, nom
    if not dom or not gost or dom == gost:
        return None
    return dom, gost, td, tg, nd, ng


def _kogato(s):
    """ISO низ -> aware datetime. None при боклук."""
    s = str(s or "").strip().replace("Z", "+00:00")
    if not s:
        return None
    try:
        d = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return d.replace(tzinfo=_dt.timezone.utc) if d.tzinfo is None else d


def srechti(sega=None, chasove=None, ime=None, vzemi=None):
    """Насрочените ръгби срещи. NEPITAN = не можах да питам."""
    if not VKLYUCHENO:
        return []
    sega = sega or _dt.datetime.now(_dt.timezone.utc)
    do = sega + _dt.timedelta(hours=int(chasove or CHASOVE))
    prevod = ime if callable(ime) else (lambda x: x)
    ot_s, do_s = sega.strftime("%Y%m%d"), do.strftime("%Y%m%d")
    out, pitani = [], 0
    for lid, tezh, bg, _dok in LIGI:
        d = _tablo(lid, ot_s, do_s, vzemi)
        if d is None:
            continue
        pitani += 1
        for ev in (d.get("events") or []):
            if _sastoyanie(ev) != "pre":
                continue
            s = _strani(ev)
            if not s:
                continue
            dom, gost, _td, _tg, nd, ng = s
            # 🔴 БЕЗ НОМЕРА НЕ СЕ ПУСКА. Мач без номера не може да бъде
            # оценен, а карта, която не може да бъде оценена, не бива да
            # излиза — същото правило, с което не влязоха КХЛ и клубният
            # волейбол.
            if not nd or not ng:
                continue
            w = _kogato(ev.get("date"))
            if w is None or not (sega <= w <= do):
                continue
            out.append({
                "bucket": NASH_KLYUCH, "emoji": EMOJI, "src": "ragbi",
                "home": prevod(dom), "away": prevod(gost),
                # НОМЕРА, не имена — оценителят сверява по тях.
                "home_id": nd, "away_id": ng,
                # `slug` е лигата: scorer строи с него адреса
                # ESPN/rugby/{slug}/scoreboard.
                "slug": lid,
                "league": bg, "weight": tezh,
                "when": w,
                # 🔴 И В `extra` — `log_pick` чете slug ОТТУК, не отгоре.
                # Само горното не стигаше до дневника: измерено живо,
                # всяка ръгби карта влизаше със slug=None и падаше в
                # sdb_result, който сверява по ИМЕ и лепва съседен мач.
                # `hca` е домакинското предимство В ТОЧКИ. Подава се по
                # същия път като `sigma`, защото моделът е общ с амер.
                # футбол, а константите — не. Без него ръгбито смяташе с
                # 2.0 (американското число) вместо с измерените 7.5.
                "extra": {"home_en": dom, "away_en": gost, "slug": lid,
                          "liga_id": lid, "sigma": SIGMA,
                          "hca": home_tochki(lid),
                          "id": str(ev.get("id") or "")},
            })
    if not pitani:
        return NEPITAN
    out.sort(key=lambda r: r["when"])
    return out[:TAVAN]


def istoriya(fx, strana, sega=None, vzemi=None):
    """Изиграните мачове на един отбор. Форма: {gf, ga, home, date}.

    🔴 ЕДНА ЗАЯВКА НА ЛИГА, НЕ НА ОТБОР. Обичайният път
    `/teams/{id}/schedule` за ръгби връща HTTP 500 (12 от 12 проверени).
    Диапазонният scoreboard носи целия прозорец наведнъж и от него се вадят
    и двата отбора — тоест втората страна на мача е БЕЗПЛАТНА.
    """
    ex = (fx or {}).get("extra") or {}
    lid = str(ex.get("liga_id") or fx.get("slug") or "")
    nom = str((fx.get("home_id") if strana == "home"
               else fx.get("away_id")) or "")
    if not lid or not nom:
        return []
    sega = sega or _dt.datetime.now(_dt.timezone.utc)
    ot = (sega - _dt.timedelta(days=DNI_NAZAD)).strftime("%Y%m%d")
    do = sega.strftime("%Y%m%d")
    d = _tablo(lid, ot, do, vzemi)
    if not isinstance(d, dict):
        return []
    out = []
    for ev in (d.get("events") or []):
        if _sastoyanie(ev) != "post":
            continue
        s = _strani(ev)
        if not s:
            continue
        dom, gost, td, tg, nd, ng = s
        if td is None or tg is None:
            continue
        # 🔴 СВЕРЯВА СЕ ПО НОМЕР. По име би се чупило на всяко разминаване
        # между изворите („Castres" срещу „Castres Olympique").
        if nom == nd:
            out.append({"gf": td, "ga": tg, "home": True,
                        "date": str(ev.get("date") or "")[:10]})
        elif nom == ng:
            out.append({"gf": tg, "ga": td, "home": False,
                        "date": str(ev.get("date") or "")[:10]})
    return out


def dostatachno(hr, ar):
    """Има ли с какво да се смята. Прагът е ИЗМЕРЕН, не отгатнат."""
    return len(hr or []) >= MIN_MACHOVE and len(ar or []) >= MIN_MACHOVE


# ───────────────────────────────────────────────────────── САМОПРОВЕРКА
def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    nuliray()

    # ── константите: измерени, не отгатнати
    check("предимството на домакина е измереното", abs(HOME_TOCHKI - 7.5) < 0.01)
    # 🔴 И ЧЕ СТИГА ДО СРЕЩИТЕ. Горният ред пази само СТОЙНОСТТА — той беше
    # верен цяла седмица, докато числото беше мъртва ръчка и ръгбито смяташе
    # с 2.0 (числото на американския футбол). Цената, мерена живо: в 3 от 13
    # мача картата сочеше ДРУГИЯ отбор.
    # ── и по лиги: оборената лига получава СВОЕТО число
    check("NPC получава своето (3.57, измерено на 192 мача)",
          abs(home_tochki("270563") - 3.57) < 0.01)
    check("другите четири получават общото",
          all(abs(home_tochki(k) - HOME_TOCHKI) < 0.01
              for k in ("270559", "267979", "270557", "289234")))
    check("непозната лига пада на общото",
          abs(home_tochki("няма такава") - HOME_TOCHKI) < 0.01)
    check("празна лига пада на общото",
          abs(home_tochki(None) - HOME_TOCHKI) < 0.01)
    check("само ОБОРЕНАТА лига има свое число", len(HOME_PO_LIGI) == 1)
    check("и това е NPC", set(HOME_PO_LIGI) == {"270563"})
    check("разсейването е измереното", abs(SIGMA - 21.85) < 0.01)
    # 🔴 ТАЗИ ПРОВЕРКА Е СМИСЪЛЪТ НА ЦЕЛИЯ ФАЙЛ. σ = 21.85 при американски
    # футбол 13.5 значи, че ръгбито е ЗНАЧИТЕЛНО по-непредвидимо. Сложи ли
    # някой σ = 13, разлика от 7 точки ще даде 70% вместо истинските 63% —
    # фалшива увереност, произведена от една константа.
    check("разсейването е ГОЛЯМО (ръгбито не е амер. футбол)", SIGMA > 18.0)
    check("прагът за извадка е разумен", 2 <= MIN_MACHOVE <= 6)

    # ── лигите
    check("пет лиги", len(LIGI) == 5)
    check("всяка носи доказателство от каталога",
          all(len(x[3]) > 10 for x in LIGI))
    check("номерата са различни", len({x[0] for x in LIGI}) == len(LIGI))
    check("имената са на български",
          all(any("а" <= c <= "я" or "А" <= c <= "Я" for c in x[2])
              for x in LIGI))
    # 🔴 АМАТЬОРСКАТА НЕ Е ВЪТРЕ. Изписана поименно, за да гърми, ако влезе.
    check("URBA Top 14 НЕ е в лигите",
          "289279" not in {x[0] for x in LIGI})
    check("и е записана защо", "289279" in NE_VLIZAT)

    # ── четене на страните
    _ev = {"date": "2026-09-06T15:00Z",
           "status": {"type": {"state": "pre"}},
           "competitions": [{"competitors": [
               {"homeAway": "home", "score": "30",
                "team": {"displayName": "Castres", "id": "25916"}},
               {"homeAway": "away", "score": "17",
                "team": {"displayName": "Vannes", "id": "289337"}}]}]}
    check("домакинът и гостът се четат по homeAway",
          _strani(_ev)[:2] == ("Castres", "Vannes"))
    check("точките се четат", _strani(_ev)[2:4] == (30.0, 17.0))
    check("номерата се четат", _strani(_ev)[4:] == ("25916", "289337"))
    check("състоянието се чете", _sastoyanie(_ev) == "pre")
    check("еднакви имена не минават",
          _strani({"competitions": [{"competitors": [
              {"homeAway": "home", "team": {"displayName": "А"}},
              {"homeAway": "away", "team": {"displayName": "А"}}]}]}) is None)
    check("празното не гърми", _strani({}) is None and _strani(None) is None)
    check("боклук за час не гърми", _kogato("не е дата") is None)

    # ── СРЕЩИТЕ, с подхвърлен извор: НУЛА мрежа
    _sega = _dt.datetime(2026, 9, 5, 12, 0, tzinfo=_dt.timezone.utc)

    # 🔴 ПОДЛОЖКАТА НОСИ НОМЕРА, защото истинският ESPN ги носи и защото
    # оценителят сверява по тях. Номерът е изведен от името, за да е четимо
    # кой е кой, но кодът НЕ вижда името — вижда числото.
    _nomera = {"Castres": "1", "Vannes": "2", "Toulon": "3", "Pau": "4",
               "Bordeaux": "5", "Toulouse": "6", "Racing": "7",
               "Далечен": "8", "Мач": "9"}

    def _tabl(dom, gost, kogа, sast, td=None, tg=None):
        return {"date": kogа, "status": {"type": {"state": sast}},
                "competitions": [{"competitors": [
                    {"homeAway": "home", "score": td,
                     "team": {"displayName": dom,
                              "id": _nomera.get(dom, dom)}},
                    {"homeAway": "away", "score": tg,
                     "team": {"displayName": gost,
                              "id": _nomera.get(gost, gost)}}]}]}

    _dani = {"events": [
        _tabl("Castres", "Vannes", "2026-09-06T15:00Z", "pre"),
        _tabl("Toulon", "Pau", "2026-09-06T17:00Z", "pre"),
        _tabl("Bordeaux", "Toulouse", "2026-08-20T15:00Z", "post", "24", "31"),
        _tabl("Castres", "Bordeaux", "2026-08-13T15:00Z", "post", "35", "12"),
        _tabl("Toulon", "Castres", "2026-08-06T15:00Z", "post", "18", "22"),
        _tabl("Castres", "Pau", "2026-07-30T15:00Z", "post", "28", "20"),
        _tabl("Racing", "Castres", "2026-07-23T15:00Z", "post", "15", "19"),
        _tabl("Далечен", "Мач", "2026-12-30T15:00Z", "pre"),
    ]}

    def _podhvarlen(u):
        return _dani

    nuliray()
    r = srechti(_sega, 72, None, _podhvarlen)
    check("срещите не са NEPITAN", r is not NEPITAN)
    _im = [(x["home"], x["away"]) for x in (r if r is not NEPITAN else [])]
    check("изиграните НЕ влизат", ("Bordeaux", "Toulouse") not in _im)
    check("далечният НЕ влиза (извън прозореца)", ("Далечен", "Мач") not in _im)
    check("насрочените влизат", ("Castres", "Vannes") in _im)
    # 🔴 И ЧЕ НОСЯТ НОМЕРА И ЛИГА — без тях оценителят не може да ги съди.
    check("всеки носи номер на домакина", all(x["home_id"] for x in r))
    check("всеки носи номер на госта", all(x["away_id"] for x in r))
    check("всеки носи slug (лигата) за оценителя", all(x["slug"] for x in r))
    # 🔴 И `hca` — домакинското предимство В ТОЧКИ. Дотук го нямаше и
    # моделът смяташе с 2.0 (числото на амер. футбол) вместо с измерените
    # 7.5. Цената, мерена живо: в 3 от 13 мача картата сочеше ДРУГИЯ отбор.
    check("срещите носят hca", all("hca" in (x.get("extra") or {}) for x in r))
    check("hca е число, не низ",
          all(isinstance((x["extra"]).get("hca"), float) for x in r))
    # 🔴 И В `extra` — ОТТАМ ГО ЧЕТЕ `log_pick` (05.09.2026).
    # Само горното ниво не стигаше до дневника: измерено живо, всяка
    # ръгби карта влизаше със slug=None. Цената НЕ беше «картата виси» —
    # без slug картата пада в sdb_result, който сверява по ИМЕ и може да
    # лепне мач от съседен ден. Фалшива присъда, не липсваща.
    check("slug е и в extra (log_pick чете оттам)",
          all((x.get("extra") or {}).get("slug") == x["slug"] for x in r))
    check("номерът НЕ е името",
          all(x["home_id"] != x["extra"]["home_en"] for x in r))
    check("кошницата е ръгби", all(x["bucket"] == "rugby" for x in r))
    check("всеки знае лигата си", all(x["extra"]["liga_id"] for x in r))
    check("и носи разсейването", all(x["extra"]["sigma"] == SIGMA for x in r))
    check("подредени по час",
          [x["when"] for x in r] == sorted(x["when"] for x in r))
    # ПЕТ лиги × един и същ подхвърлен отговор = всяка среща по пет пъти;
    # това е свойство на подложката, не на кода — затова се брои различното.
    check("различните двойки са две", len(set(_im)) == 2)

    # 🔴 ПРЕВОДАЧЪТ СЕ ВИКА. Без този ред `ime` може да е мъртъв параметър.
    nuliray()
    r2 = srechti(_sega, 72, lambda s: "БГ:" + s, _podhvarlen)
    check("преводачът се вика", all(x["home"].startswith("БГ:") for x in r2))
    check("но home_id остава оригиналното",
          all(not x["home_id"].startswith("БГ:") for x in r2))

    # ── МЪЛЧАЩ ИЗВОР != НУЛА МАЧОВЕ
    nuliray()
    check("нула отговори дават NEPITAN",
          srechti(_sega, 72, None, lambda u: None) is NEPITAN)
    nuliray()
    check("празен отговор е ЧЕСТНА нула",
          srechti(_sega, 72, None, lambda u: {"events": []}) == [])

    # ── ИСТОРИЯТА
    nuliray()
    _fx = {"home_id": "1", "away_id": "2",
           "extra": {"liga_id": "270559"}}
    _h = istoriya(_fx, "home", _sega, _podhvarlen)
    # Подложката дава на Castres ЧЕТИРИ изиграни мача: два у дома
    # (35:12 срещу Bordeaux, 28:20 срещу Pau) и два на гости (22:18 при
    # Toulon, 19:15 при Racing). Числата са изписани дословно, за да гърми,
    # ако четенето на страните се обърне.
    check("историята на домакина се събира", len(_h) == 4)
    check("вкараните са НЕГОВИТЕ, не на противника",
          sorted(x["gf"] for x in _h) == [19.0, 22.0, 28.0, 35.0])
    check("допуснатите са на противника",
          sorted(x["ga"] for x in _h) == [12.0, 15.0, 18.0, 20.0])
    check("двата домакински мача се броят като такива",
          sum(1 for x in _h if x["home"]) == 2)
    check("и двата гостуващи", sum(1 for x in _h if not x["home"]) == 2)
    # 🔴 И ЧЕ ГОСТУВАНЕТО НЕ Е ОБЪРНАТО. При „Toulon 18 : 22 Castres"
    # Castres е ГОСТ и е вкарал 22. Обърнато четене би дало 18 — и моделът
    # би смятал добрия отбор за лош, тихо.
    _gost = [x for x in _h if not x["home"]]
    check("на гости вкараните са неговите",
          sorted(x["gf"] for x in _gost) == [19.0, 22.0])
    check("датите се пазят", all(len(x["date"]) == 10 for x in _h))
    _ha = istoriya(_fx, "away", _sega, _podhvarlen)
    check("отбор без изиграни мачове дава празно", _ha == [])
    check("без лига дава празно",
          istoriya({"home_id": "1", "extra": {}}, "home", _sega,
                   _podhvarlen) == [])
    check("без номер дава празно",
          istoriya({"extra": {"liga_id": "270559"}}, "home", _sega,
                   _podhvarlen) == [])
    # 🔴 И ЧЕ НЕ СЕ СВЕРЯВА ПО ИМЕ. Подава се ИМЕТО вместо номера — ако
    # кодът пак тръгне по имена, това ще върне мачове и ще гръмне.
    check("сверяването по ИМЕ вече не работи (и това е вярно)",
          istoriya({"home_id": "Castres", "extra": {"liga_id": "270559"}},
                   "home", _sega, _podhvarlen) == [])

    # ── ДОСТАТЪЧНОСТ
    check("три и три стигат", dostatachno([1, 2, 3], [1, 2, 3]) is True)
    check("две не стигат", dostatachno([1, 2], [1, 2, 3]) is False)
    check("празно не стига", dostatachno([], [1, 2, 3]) is False)
    check("None не гърми", dostatachno(None, None) is False)

    # ── КЕШЪТ: една заявка на лига, не на отбор
    nuliray()
    _br = [0]

    def _broyach(u):
        _br[0] += 1
        return _dani

    istoriya(_fx, "home", _sega, _broyach)
    istoriya(_fx, "away", _sega, _broyach)
    check("двете страни струват ЕДНА заявка", _br[0] == 1)

    # ── ключът за изключване
    check("модулът е ВКЛЮЧЕН по подразбиране", VKLYUCHENO is True)
    _st = VKLYUCHENO
    try:
        globals()["VKLYUCHENO"] = False
        check("изключен дава празно, не NEPITAN",
              srechti(_sega, 72, None, _podhvarlen) == [])
    finally:
        globals()["VKLYUCHENO"] = _st
    check("ключът е върнат", VKLYUCHENO is _st)

    check("самопроверката не пипна мрежата", broi_zayavki() == 0)

    print("САМОПРОВЕРКА НА РЪГБИТО: %d наред, %d счупени" % (ok, len(bad)))
    for b in bad:
        print("   счупено: " + b)
    return ok, bad


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    _ok, _bad = selftest()
    sys.exit(1 if _bad else 0)
