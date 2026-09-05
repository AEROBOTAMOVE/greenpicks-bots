#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ЕВРОПЕЙСКИ ХОКЕЙ 🏒

Един въпрос: кой европейски хокеен мач можем да преценим САМИ, а не да
преповторим цената на пазара?

ЗАЩО СЪЩЕСТВУВА ТОЗИ ФАЙЛ
=========================
Pinnacle дава 37 хокейни мача с коефициенти всеки ден — КХЛ, ВХЛ, Шампионска
хокейна лига, SM Liiga, Metal Ligaen. Ботът не пипаше нито един: `hokey.py`
чете САМО `api-web.nhle.com`, тоест САМО НХЛ, а НХЛ отваря на 29.09.

Но цена без модел е бокс: картата преписва пазара и не носи информация.
Затова тук влизат САМО двете лиги, за които има И РЕЗУЛТАТИ:

  SM Liiga (Финландия)   liiga.fi/api/v2/schedule?season=YYYY
  Шампионска лига        chl.hockey/api/s3?q=schedule-…json

🔴 ЕДНА МОЯ ГРЕШКА, КОЯТО СТОИ ТУК ЗА ПАМЕТ (02.09.2026)
Пуснах `liiga.fi/api/v1/games`, получих HTML и обявих пред собственика, че
„няма безплатен извор за европейски хокей". Версията беше грешната. `v2`
работи, отдавна, и дава история до сезон 1975. Един пропуснат знак в адреса
стана на „невъзможно е".

ИЗМЕРЕНО НА ЖИВО (02.09.2026, всяко число е пуснато, не спомнено)
=================================================================
  SM Liiga сезон 2027:  544 мача, 533 насрочени, 11 изиграни
  SM Liiga сезон 2026:  480 мача, ВСИЧКИТЕ изиграни
  Таблица от двата:     491 мача, 17 отбора, 5.67 гола на мач
  CHL, 13 сезонни файла: 770 изиграни мача, 89 отбора, 5.56 гола на мач
  Насрочените напред:   и двата отбора са в таблицата при всичките проверени
  Pinnacle същия ден:   SM Liiga 5 мача, CHL 6 мача — с коефициент

5.67 и 5.56 гола на мач са точно колкото трябва да е хокей. Ако утре това
число слезе под 3 или мине над 9, значи полетата са се сменили и таблицата
мери нещо друго — затова е проверка, не бележка.

КАКВО НЕ ВЛИЗА И ЗАЩО
=====================
КХЛ, ВХЛ, МХЛ, Metal Ligaen — Pinnacle им дава цени (общо 22 мача), но
резултати няма откъде да се вземат: khl.ru дава 403 на честен подпис,
SofaScore 403, eliteprospects 401, TheSportsDB с безплатния ключ връща пет
лиги общо. Карта без начин да бъде оценена е карта, която не бива да излиза.

ФОРМАТА
=======
`srechti()` връща СЪЩИТЕ полета като `hokey.kosnica()`, за да не се пипа
предсказателят повече от един клон. `tablica()` връща СЪЩАТА форма като
`predictor.nhl_table()`, за да работи `model_hockey` без нито една промяна
в сметките си.

ПЪТ НАЗАД
=========
`PREDICT_EVROHOKEY=0` изключва целия файл — предсказателят вижда „няма
срещи" и се държи точно както преди 02.09.2026.
"""
import datetime as _dt
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

# ───────────────────────────────────────────────────────────── УСТРОЙСТВО
NASH_KLYUCH = "hockey"
EMOJI = "🏒"

VKLYUCHENO = (os.environ.get("PREDICT_EVROHOKEY") or "1").strip() not in (
    "0", "false", "no", "не")

# 🔴 ЧЕСТЕН ПОДПИС. От 01.09.2026 ESPN дава 403 на празен подпис, а на
# честния — 200. Тук подписът е същият по друга причина: не се преправям на
# браузър пред чужд извор. Който смени този ред с браузърен низ, заобикаля
# защита, а това не се прави в този проект.
UA = "greenpicks-bot/1.0 (+github.com/AEROBOTAMOVE/greenpicks-bots)"
TIMEOUT = int((os.environ.get("EVROHOKEY_TIMEOUT") or "25").strip() or 25)

LIIGA_URL = "https://liiga.fi/api/v2/schedule?season=%d"
CHL_STR = "https://www.chl.hockey/en/schedule"
CHL_URL = "https://www.chl.hockey/api/s3?q=schedule-21ec9dad81abe2e0240460d0-%s.json"
# Последният известен сезонен файл. Ползва се САМО ако страницата не се
# прочете — иначе списъкът се вади от нея, за да не остарее закованото.
CHL_REZERVA = "fc954f6d33272fdf4a8b95bb"
CHL_PREFIX = "schedule-21ec9dad81abe2e0240460d0-"

LIGI = {
    "liiga": {"bg": "СМ Лига, Финландия", "tezhest": 5},
    "chl": {"bg": "Шампионска хокейна лига", "tezhest": 6},
}

# Колко мача трябва да има отбор, за да го смятаме. Същото число като при
# НХЛ (`nhl_table`, `gp < 5: continue`) и по същата причина: Йокерит влезе
# тази есен с ЕДИН мач и 4.00 вкарани — число, което не значи нищо.
MIN_MACHOVE = 5

# Колко часа напред гледаме. Предсказателят си има свой хоризонт; този тук
# е таван на самия извор, за да не се влачи цял сезон в паметта.
CHASOVE = int((os.environ.get("EVROHOKEY_CHASOVE") or "168").strip() or 168)
TAVAN = int((os.environ.get("EVROHOKEY_TAVAN") or "60").strip() or 60)

# 🔴 „НЕ МОЖАХ ДА ПИТАМ" НЕ Е „НЯМА МАЧОВЕ". Същият сентинел като в
# `hokey.py` и по същата причина: паднала мрежа и спокоен вторник изглеждат
# еднакво, ако не се разделят нарочно.
NEPITAN = object()

_zayavki = [0]
_provali = [0]
_kesh_tab = {}
_kesh_sur = {}


def broi_zayavki():
    """Колко заявки е направил ТОЗИ файл. Самопроверката иска нула."""
    return _zayavki[0]


def broi_provali():
    """Колко от тях са се провалили. Нула мача + провал НЕ е честна нула."""
    return _provali[0]


def nuliray():
    """Чисти броячите и кеша. За самопроверката и за втори рън в същия процес."""
    _zayavki[0] = 0
    _provali[0] = 0
    _kesh_tab.clear()
    _kesh_sur.clear()


# ───────────────────────────────────────────────────────────────── МРЕЖА
def _vzemi(url, surovo=False):
    """JSON (или текст) от адрес. None при какъвто и да е провал.

    Провалът СЕ БРОИ. Без този брояч „нула мача" и „изворът падна" се
    сливат в едно и също мълчание — грешката, която в този проект вече е
    струвала цял ден мълчание на един спорт.
    """
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
        t = b.decode("utf-8")
    except UnicodeDecodeError:
        _provali[0] += 1
        return None
    if surovo:
        return t
    try:
        return json.loads(t)
    except ValueError:
        _provali[0] += 1
        return None


# ─────────────────────────────────────────────────────────────── ЧЕТЕНЕ
def _liiga_sezon(sega=None):
    """Кой сезон е „текущият" за liiga.fi. 2027 значи сезон 2026/27.

    Сезонът се брои по годината, в която ЗАВЪРШВА. Разделителната черта е
    юли: мач през август 2026 е от сезон 2027.
    """
    d = (sega or _dt.datetime.now(_dt.timezone.utc))
    return d.year + 1 if d.month >= 7 else d.year


def liiga_surovo(sezon, vzemi=None):
    """Списъкът мачове за един сезон. None значи „не можах да питам"."""
    vz = vzemi if callable(vzemi) else _vzemi
    if sezon in _kesh_sur:
        return _kesh_sur[sezon]
    d = vz(LIIGA_URL % int(sezon))
    if not isinstance(d, list):
        return None
    _kesh_sur[sezon] = d
    return d


def chl_hashove(vzemi=None):
    """Сезонните файлове на CHL, извлечени от самата страница.

    🔴 НЕ СЕ КОВАТ. Хешовете се сменят всеки сезон; закован списък би
    остарял мълчаливо и таблицата щеше да замръзне, без ред в дневника.
    Ако страницата не се прочете, се ползва последният известен — по-добре
    един сезон, отколкото нищо, но това се казва на глас.
    """
    vz = vzemi if callable(vzemi) else _vzemi
    t = vz(CHL_STR, surovo=True)
    if not isinstance(t, str):
        return [CHL_REZERVA], True
    h = sorted(set(re.findall(re.escape(CHL_PREFIX) + r"([0-9a-f]{16,40})", t)))
    if not h:
        return [CHL_REZERVA], True
    return h, False


def _dvoyka(x):
    """(домакин, гост, голове_дом, голове_гост) от запис на CHL. None при липса."""
    tms = x.get("teams") or {}
    dom = str(((tms.get("home") or {}).get("name") or "")).strip()
    gost = str(((tms.get("away") or {}).get("name") or "")).strip()
    sc = ((x.get("results") or {}).get("scores") or {})
    try:
        gd = float(sc.get("home"))
        gg = float(sc.get("away"))
    except (TypeError, ValueError):
        return None
    if not dom or not gost or dom == gost:
        return None
    return dom, gost, gd, gg


# ────────────────────────────────────────────────────────────── ТАБЛИЦА
def _prazen():
    return {"gp": 0.0, "gf": 0.0, "ga": 0.0,
            "hgp": 0.0, "hgf": 0.0, "hga": 0.0,
            "rgp": 0.0, "rgf": 0.0, "rga": 0.0}


def dobavi_mach(tab, dom, gost, gd, gg):
    """Един изигран мач влиза в таблицата и на двата отбора.

    Домакинството се брои ОТДЕЛНО (hgp/hgf/hga срещу rgp/rgf/rga), защото
    точно това дава на модела предимството на домакина. Сбор без разделяне
    би го изял.
    """
    for ime in (dom, gost):
        if ime not in tab:
            tab[ime] = _prazen()
    h, a = tab[dom], tab[gost]
    h["gp"] += 1.0
    h["gf"] += gd
    h["ga"] += gg
    h["hgp"] += 1.0
    h["hgf"] += gd
    h["hga"] += gg
    a["gp"] += 1.0
    a["gf"] += gg
    a["ga"] += gd
    a["rgp"] += 1.0
    a["rgf"] += gg
    a["rga"] += gd
    return tab


def tablica(liga, sega=None, vzemi=None):
    """{отбор: {gp,gf,ga,hgp,hgf,hga,rgp,rgf,rga}} — формата на `nhl_table`.

    Празен речник значи „нямам с какво да смятам" и моделът мълчи. Това НЕ
    е грешка: в началото на сезон таблицата наистина е тънка.
    """
    liga = str(liga or "").lower()
    if liga in _kesh_tab:
        return _kesh_tab[liga]
    tab = {}
    if liga == "liiga":
        tek = _liiga_sezon(sega)
        # ДВА сезона: миналият пълен носи тежестта, тазгодишният — свежестта.
        for sez in (tek - 1, tek):
            d = liiga_surovo(sez, vzemi)
            for x in (d or []):
                if not x.get("ended"):
                    continue
                try:
                    gd = float(x.get("homeTeamGoals"))
                    gg = float(x.get("awayTeamGoals"))
                except (TypeError, ValueError):
                    continue
                dom = str(x.get("homeTeamName") or "").strip()
                gost = str(x.get("awayTeamName") or "").strip()
                if not dom or not gost or dom == gost:
                    continue
                dobavi_mach(tab, dom, gost, gd, gg)
    elif liga == "chl":
        hh, _rez = chl_hashove(vzemi)
        vz = vzemi if callable(vzemi) else _vzemi
        for hsh in hh:
            d = vz(CHL_URL % hsh)
            m = d if isinstance(d, list) else []
            if not m and isinstance(d, dict):
                for k in d:
                    if isinstance(d[k], list) and d[k] and isinstance(d[k][0], dict):
                        m = d[k]
                        break
            for x in m:
                if not isinstance(x, dict) or str(x.get("status")) != "finished":
                    continue
                p = _dvoyka(x)
                if p:
                    dobavi_mach(tab, *p)
    # Тънките отбори падат — виж MIN_MACHOVE и защо е точно 5.
    tab = {k: v for k, v in tab.items() if v["gp"] >= MIN_MACHOVE}
    _kesh_tab[liga] = tab
    return tab


def goleve_na_mach(tab):
    """Средно голове на ОТБОР за мач. Пазач срещу сменени полета."""
    gp = sum(t["gp"] for t in tab.values())
    if not gp:
        return 0.0
    return sum(t["gf"] for t in tab.values()) / gp


# ─────────────────────────────────────────────────────────────── СРЕЩИ
def _kogato(s):
    """ISO низ -> aware datetime. None при боклук."""
    s = str(s or "").strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        d = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return d


def srechti(sega=None, chasove=None, ime=None, vzemi=None):
    """Насрочените европейски хокейни срещи. NEPITAN = не можах да питам.

    `ime` е преводачът на предсказателя (име -> българско име), подаван
    точно както при `hokey.kosnica`. None значи „остави имената както са".
    """
    if not VKLYUCHENO:
        return []
    sega = sega or _dt.datetime.now(_dt.timezone.utc)
    do = sega + _dt.timedelta(hours=int(chasove or CHASOVE))
    prevod = ime if callable(ime) else (lambda x: x)
    out = []
    pitani = 0

    # ── SM Liiga
    tek = _liiga_sezon(sega)
    d = liiga_surovo(tek, vzemi)
    if d is not None:
        pitani += 1
        for x in d:
            if x.get("ended") or x.get("started"):
                continue
            w = _kogato(x.get("start"))
            if w is None or not (sega <= w <= do):
                continue
            dom = str(x.get("homeTeamName") or "").strip()
            gost = str(x.get("awayTeamName") or "").strip()
            if not dom or not gost or dom == gost:
                continue
            out.append({
                "bucket": NASH_KLYUCH, "emoji": EMOJI, "src": "liiga",
                "home": prevod(dom), "away": prevod(gost),
                "home_id": dom, "away_id": gost,
                "league": LIGI["liiga"]["bg"],
                "weight": LIGI["liiga"]["tezhest"],
                "when": w,
                "extra": {"home_en": dom, "away_en": gost,
                          "evro": "liiga", "id": str(x.get("id") or "")},
            })

    # ── Шампионска лига
    hh, _rez = chl_hashove(vzemi)
    vz = vzemi if callable(vzemi) else _vzemi
    if hh:
        d = vz(CHL_URL % hh[-1])
        m = d if isinstance(d, list) else []
        if not m and isinstance(d, dict):
            for k in d:
                if isinstance(d[k], list) and d[k] and isinstance(d[k][0], dict):
                    m = d[k]
                    break
        if m:
            pitani += 1
        for x in m:
            if not isinstance(x, dict) or str(x.get("status")) == "finished":
                continue
            w = _kogato(x.get("startDate"))
            if w is None or not (sega <= w <= do):
                continue
            tms = x.get("teams") or {}
            dom = str(((tms.get("home") or {}).get("name") or "")).strip()
            gost = str(((tms.get("away") or {}).get("name") or "")).strip()
            if not dom or not gost or dom == gost:
                continue
            out.append({
                "bucket": NASH_KLYUCH, "emoji": EMOJI, "src": "chl",
                "home": prevod(dom), "away": prevod(gost),
                "home_id": dom, "away_id": gost,
                "league": LIGI["chl"]["bg"],
                "weight": LIGI["chl"]["tezhest"],
                "when": w,
                "extra": {"home_en": dom, "away_en": gost,
                          "evro": "chl", "id": str(x.get("_entityId") or "")},
            })

    if not pitani:
        return NEPITAN
    out.sort(key=lambda r: r["when"])
    return out[:TAVAN]


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

    # ── таблицата: аритметиката, без нито една заявка
    t = {}
    dobavi_mach(t, "А", "Б", 3, 2)
    check("двата отбора влизат", set(t) == {"А", "Б"})
    check("домакинът брои вкараните", t["А"]["gf"] == 3 and t["А"]["ga"] == 2)
    check("гостът брои огледално", t["Б"]["gf"] == 2 and t["Б"]["ga"] == 3)
    check("домакинството се брои ОТДЕЛНО",
          t["А"]["hgp"] == 1 and t["А"]["rgp"] == 0)
    check("гостуването също", t["Б"]["rgp"] == 1 and t["Б"]["hgp"] == 0)
    dobavi_mach(t, "Б", "А", 1, 4)
    check("вторият мач се натрупва", t["А"]["gp"] == 2 and t["Б"]["gp"] == 2)
    check("сега и двамата имат по едно домакинство",
          t["А"]["hgp"] == 1 and t["Б"]["hgp"] == 1)
    check("сборът на вкараните е сборът на допуснатите",
          sum(x["gf"] for x in t.values()) == sum(x["ga"] for x in t.values()))
    check("голове на мач се смята",
          abs(goleve_na_mach(t) - (3 + 2 + 1 + 4) / 4.0) < 1e-9)
    check("празна таблица дава нула, не гърми", goleve_na_mach({}) == 0.0)

    # ── четенето на сезона
    check("август е от следващия сезон",
          _liiga_sezon(_dt.datetime(2026, 8, 15, tzinfo=_dt.timezone.utc)) == 2027)
    check("януари е от същия",
          _liiga_sezon(_dt.datetime(2027, 1, 15, tzinfo=_dt.timezone.utc)) == 2027)
    check("юли вече е новият сезон",
          _liiga_sezon(_dt.datetime(2026, 7, 1, tzinfo=_dt.timezone.utc)) == 2027)
    check("юни е още старият",
          _liiga_sezon(_dt.datetime(2026, 6, 30, tzinfo=_dt.timezone.utc)) == 2026)

    # ── часовете
    check("Z се чете като UTC",
          _kogato("2026-09-05T14:00:00Z").tzinfo is not None)
    check("часът е верен", _kogato("2026-09-05T14:00:00Z").hour == 14)
    check("боклукът не гърми", _kogato("не е дата") is None)
    check("празното не гърми", _kogato("") is None and _kogato(None) is None)

    # ── СРЕЩИТЕ, с подхвърлен извор: НУЛА мрежа
    _sega = _dt.datetime(2026, 9, 5, 12, 0, tzinfo=_dt.timezone.utc)
    _liiga = [
        {"id": 1, "start": "2026-09-05T14:00:00Z", "ended": False,
         "started": False, "homeTeamName": "Jukurit", "awayTeamName": "Sport"},
        {"id": 2, "start": "2026-09-05T14:00:00Z", "ended": True,
         "started": True, "homeTeamName": "TPS", "awayTeamName": "HIFK",
         "homeTeamGoals": 3, "awayTeamGoals": 1},
        {"id": 3, "start": "2026-11-30T14:00:00Z", "ended": False,
         "started": False, "homeTeamName": "Ilves", "awayTeamName": "JYP"},
        {"id": 4, "start": "2026-09-05T14:00:00Z", "ended": False,
         "started": True, "homeTeamName": "Lukko", "awayTeamName": "KalPa"},
    ]
    _chl = [
        {"_entityId": "x1", "startDate": "2026-09-05T18:00:00.000Z",
         "status": "not-started",
         "teams": {"home": {"name": "Rögle"}, "away": {"name": "Pilsen"}}},
        {"_entityId": "x2", "startDate": "2026-09-03T18:00:00.000Z",
         "status": "finished",
         "teams": {"home": {"name": "Pilsen"}, "away": {"name": "Rögle"}},
         "results": {"scores": {"home": 2, "away": 5}}},
    ]

    def _podhvarlen(u, surovo=False):
        if surovo:
            return "…" + CHL_PREFIX + "aaaaaaaaaaaaaaaa" + ".json…"
        if "liiga.fi" in u:
            return _liiga
        if "chl.hockey" in u:
            return _chl
        return None

    nuliray()
    r = srechti(_sega, 72, None, _podhvarlen)
    check("срещите не са NEPITAN", r is not NEPITAN)
    imena = [(x["home"], x["away"]) for x in (r if r is not NEPITAN else [])]
    check("изиграният мач НЕ влиза", ("TPS", "HIFK") not in imena)
    check("започналият мач НЕ влиза", ("Lukko", "KalPa") not in imena)
    check("далечният мач НЕ влиза (извън прозореца)",
          ("Ilves", "JYP") not in imena)
    check("насроченият влиза", ("Jukurit", "Sport") in imena)
    check("и от Шампионската лига влиза", ("Rögle", "Pilsen") in imena)
    check("точно два мача", len(imena) == 2)
    check("кошницата е хокей", all(x["bucket"] == "hockey" for x in r))
    check("всеки носи час", all(x["when"] is not None for x in r))
    check("всеки носи лига на български",
          all(x["league"] in (LIGI["liiga"]["bg"], LIGI["chl"]["bg"]) for x in r))
    check("всеки знае от коя лига е",
          all(x["extra"]["evro"] in ("liiga", "chl") for x in r))
    check("подредени са по час",
          [x["when"] for x in r] == sorted(x["when"] for x in r))
    check("home_id е името, с което се търси в таблицата",
          all(x["home_id"] == x["extra"]["home_en"] for x in r))

    # 🔴 ПРЕВОДАЧЪТ СЕ ВИКА. Без този ред `ime` може да е мъртъв параметър —
    # шаблонът „построено, но не свързано", ударил осем пъти в този проект.
    nuliray()
    r2 = srechti(_sega, 72, lambda s: "БГ:" + s, _podhvarlen)
    check("преводачът се вика за домакина",
          all(x["home"].startswith("БГ:") for x in r2))
    check("преводачът се вика за госта",
          all(x["away"].startswith("БГ:") for x in r2))
    check("но home_id ОСТАВА оригиналното име",
          all(not x["home_id"].startswith("БГ:") for x in r2))

    # ── МЪЛЧАЩ ИЗВОР != НУЛА МАЧОВЕ
    nuliray()
    check("нула отговори дават NEPITAN",
          srechti(_sega, 72, None, lambda u, surovo=False: None) is NEPITAN)
    nuliray()
    _prazni = srechti(_sega, 72, None,
                      lambda u, surovo=False: ("…" if surovo else []))
    check("празен отговор е ЧЕСТНА нула, не NEPITAN",
          _prazni is not NEPITAN and _prazni == [])

    # ── таблицата от подхвърлени данни
    nuliray()
    _mnogo = []
    for i in range(6):
        _mnogo.append({"ended": True, "homeTeamName": "Аа", "awayTeamName": "Бб",
                       "homeTeamGoals": 3, "awayTeamGoals": 2})
        _mnogo.append({"ended": True, "homeTeamName": "Бб", "awayTeamName": "Аа",
                       "homeTeamGoals": 2, "awayTeamGoals": 3})
    _mnogo.append({"ended": False, "homeTeamName": "Аа", "awayTeamName": "Вв"})

    # 🔴 ПОДЛОЖКАТА Е СЕЗОННО-ОСЪЗНАТА, и това не е дребно. `tablica` чете
    # ДВА сезона (миналият за тежест, тазгодишният за свежест). Първата ми
    # версия връщаше едни и същи данни за двата и мачовете се удвоиха —
    # тестът щеше да мине с 24 и никой нямаше да разбере, че сезоните не се
    # различават. Тук сезон 2026 носи мачовете, а 2027 е празен.
    _pitani = []

    def _po_sezon(u, surovo=False):
        if surovo:
            return None
        _pitani.append(u)
        return _mnogo if "season=2026" in u else []

    tb = tablica("liiga", _sega, _po_sezon)
    check("таблицата се строи от изиграните", set(tb) == {"Аа", "Бб"})
    check("ненаиграният отбор пада (под прага)", "Вв" not in tb)
    check("прагът е точно 5", MIN_MACHOVE == 5)
    check("броят мачове е верен (12, не 24)", tb["Аа"]["gp"] == 12)
    check("питани са ДВА различни сезона",
          len({u for u in _pitani}) == 2)
    check("и единият е миналият, другият текущият",
          any("season=2026" in u for u in _pitani)
          and any("season=2027" in u for u in _pitani))
    check("голове на мач е разумно за хокей",
          2.0 <= goleve_na_mach(tb) <= 4.0)

    nuliray()
    check("непозната лига дава празно, не гърми",
          tablica("нещо", _sega, lambda u, surovo=False: None) == {})

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

    # ── и КОИ ЛИГИ НАРОЧНО ГИ НЯМА
    check("КХЛ я няма (няма извор за резултати)", "khl" not in LIGI)
    check("ВХЛ я няма", "vhl" not in LIGI)
    check("Metal Ligaen я няма", "metal" not in LIGI)
    check("точно две лиги", len(LIGI) == 2)

    # ── нула мрежа в цялата самопроверка
    check("самопроверката не пипна мрежата", broi_zayavki() == 0)

    print("САМОПРОВЕРКА НА ЕВРОХОКЕЯ: %d наред, %d счупени" % (ok, len(bad)))
    for b in bad:
        print("   счупено: " + b)
    return ok, bad


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    _ok, _bad = selftest()
    sys.exit(1 if _bad else 0)
