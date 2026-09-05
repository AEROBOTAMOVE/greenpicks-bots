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

# 🔴 РЕДЪТ НА ПАРАМЕТРИТЕ НЕ Е УКРАСА — ИЗМЕРЕН Е (05.09.2026):
#     ?season=2027                        → 🔴 HTTP 500
#     ?season=2027&tournament=runkosarja  → 🔴 HTTP 500
#     ?tournament=runkosarja&season=2027  → 🟢 544 записа
# Питан за целия сезон, сървърът събира всичките си турнири; през септември
# плейофите на новия сезон още не съществуват и сглобяването се пука.
# Затова турнирът се пита ПОИМЕННО и ВИНАГИ пръв.
LIIGA_URL = "https://liiga.fi/api/v2/schedule?tournament=%s&season=%d"
# Турнирите на СМ Лига. Подредени по важност за нас: редовният сезон дава
# почти всичко, плейофите се появяват през март, подготвителните — през
# август. 500 при отделен турнир значи «още го няма», не «изворът отказа».
LIIGA_TURNIRI = ("runkosarja", "playoffs", "valmistavat_ottelut")
CHL_STR = "https://www.chl.hockey/en/schedule"
CHL_URL = "https://www.chl.hockey/api/s3?q=schedule-21ec9dad81abe2e0240460d0-%s.json"
# Последният известен сезонен файл. Ползва се САМО ако страницата не се
# прочете — иначе списъкът се вади от нея, за да не остарее закованото.
CHL_REZERVA = "fc954f6d33272fdf4a8b95bb"
CHL_PREFIX = "schedule-21ec9dad81abe2e0240460d0-"

# Кои лиги са мълчали при последното питане (виж `mylchali()`).
_mylchali = []

# Кои състояния на мач при Шампионската лига значат «предстои».
# Измерено върху 13-те сезонни файла (1519 мача): finished 1413 ·
# not-started 72 · canceled 34. Бял списък, не черен — виж `srechti`.
CHL_PREDSTOYASHTI = {"not-started"}

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
    """Мачовете за един сезон, събрани от всичките турнири.

    None значи „не можах да питам" — и това е ТОЧНО когато МЪЛЧАТ ВСИЧКИТЕ
    турнири. Празен списък значи „питах и няма мачове".

    🔴 РАЗЛИКАТА Е ЦЕНАТА НА ЦЯЛ СПОРТ. Един турнир може да върне 500,
    защото още не съществува (плейофите през септември) — това е нормално и
    не бива да заглушава редовния сезон. Ако бях слял двете, СМ Лига щеше да
    мълчи цял сезон, а дневникът да казва «изворът отказа».
    """
    vz = vzemi if callable(vzemi) else _vzemi
    if sezon in _kesh_sur:
        return _kesh_sur[sezon]
    sabrani, vidyani, otgovori = [], set(), 0
    for turnir in LIIGA_TURNIRI:
        d = vz(LIIGA_URL % (turnir, int(sezon)))
        if not isinstance(d, list):
            continue
        otgovori += 1
        for x in d:
            if not isinstance(x, dict):
                continue
            # 🔴 СЛИВА СЕ САМО ПО ИСТИНСКО `id`. Ключ, който при липсващо
            # поле обявява различни редове за един и същ, трие данни.
            # Първата ми версия ползваше (сезон, id, начало, домакин) и
            # сля шест различни мача в един, щом подложката нямаше id.
            # Измерено живо: всичките 605 записа носят id, и нито едно id
            # не се среща в два турнира — тоест сливането е застраховка, не
            # нужда. Няма id → редът минава. Един повторен мач е по-евтин
            # от един изтрит.
            nid = str(x.get("id") or "").strip()
            if nid:
                if nid in vidyani:
                    continue
                vidyani.add(nid)
            sabrani.append(x)
    if not otgovori:
        return None
    _kesh_sur[sezon] = sabrani
    return sabrani


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
    naideni = re.findall(re.escape(CHL_PREFIX) + r"([0-9a-f]{16,40})", t)
    if not naideni:
        return [CHL_REZERVA], True

    # 🔴 РЕДЪТ Е ПО ВРЕМЕ, НЕ ПО АЗБУКА (05.09.2026).
    #
    # Дотук: `sorted(set(...))` върху шестнайсетични низове, и `hh[-1]` се
    # четеше като «текущият сезон». Измерено върху всичките 13 файла: днес
    # това улучва, защото `fc95…` е близо до върха на скалата. Но нов
    # сезонен файл сортира след него с вероятност около 1 на 100 — тоест с
    # ~99% следващият сезон щеше да започне, а модулът да чете 2026/27
    # завинаги. Без ред в дневника: файлът се чете успешно и връща честни
    # мачове, просто от миналото.
    #
    # Изворът сам казва кой е текущият, в същата страница:
    #     "attachments":{"currentSeason":{"_entityId":"fc954f…"
    # А и редът на срещане в страницата е от новия към стария (проверено за
    # 13 от 13). `sorted()` изхвърляше и двата сигнала.
    red = []
    for x in naideni:                       # реда на страницата: нов → стар
        if x not in red:
            red.append(x)
    red.reverse()                           # договорът: стар → нов
    tekusht = ""
    m = re.search(r'"currentSeason"\s*:\s*\{[^}]*?"_entityId"\s*:\s*'
                  r'"([0-9a-f]{16,40})"', t)
    if m:
        tekusht = m.group(1)
    # Обявеният текущ сезон отива НАКРАЯ — там го търсят двете викащи места.
    # Ако изворът не го обяви (или обяви непознат), остава редът на
    # страницата; ако и той не важи, старото азбучно подреждане.
    if tekusht and tekusht in red:
        red = [x for x in red if x != tekusht] + [tekusht]
    return (red or sorted(set(naideni))), False


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
    # 🔴 БРОИ СЕ ОТГОВОРЪТ, НЕ ПРОВАЛЪТ. Първата ми версия сравняваше
    # `broi_provali()` преди и след — но онзи брояч се вдига САМО от
    # `_vzemi`. Подаден отвън четец (тест или бъдещ извор) не минава през
    # него и пазачът оставаше сляп. Мярката трябва да е МЕСТНА: отговорил
    # ли е поне един източник ПРИ ТОЗИ ИЗГРАД. Същият шаблон като `pitani`
    # при срещите.
    otgovori = 0
    tab = {}
    if liga == "liiga":
        tek = _liiga_sezon(sega)
        # ДВА сезона: миналият пълен носи тежестта, тазгодишният — свежестта.
        for sez in (tek - 1, tek):
            d = liiga_surovo(sez, vzemi)
            if d is not None:
                otgovori += 1
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
            if d is not None:
                otgovori += 1
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
    # 🔴 ПРАЗНОТА, РОДЕНА ОТ ПРОВАЛ, НЕ СЕ КЕШИРА. Дотук редът беше гол и
    # помнеше и `{}` — измерено: подложка, която мълчи веднъж и после
    # отговаря, връщаше празно и на втория, и на третия опит, БЕЗ нова
    # заявка. `model_hockey` при празна таблица връща None, тоест всичките
    # карти на спорта падаха за целия рън с причина «няма история», докато
    # истината беше «изворът падна».
    #
    # Празна таблица в НАЧАЛОТО НА СЕЗОН е честна нула и СЕ кешира — затова
    # се гледа дали ПОНЕ ЕДИН източник е отговорил, а не самата празнота.
    if tab or otgovori:
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
    # 🔴 ПОИМЕННО, НЕ НА БРОЙ. Един брояч за два независими извора значи, че
    # живата лига крие мъртвата: измерено днес, liiga.fi даде HTTP 500 час и
    # половина, `srechti` върна 24 честни срещи само от Шампионската лига и
    # НЕ КАЗА НИЩО. Половин спорт мъртъв, дневникът спокоен.
    mylchali = []

    # ── SM Liiga
    tek = _liiga_sezon(sega)
    d = liiga_surovo(tek, vzemi)
    if d is None:
        mylchali.append("liiga")
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
                # 🔴 `slug` НОСИ ЛИГАТА и стига до дневника. Без него
                # оценителят няма как да разбере от коя лига е мачът —
                # `extra` не се записва целият в дневника.
                # 🔴 И НА ДВЕТЕ МЕСТА. `log_pick` чете `extra["slug"]`;
                # горното ниво е за четците, които гледат срещата пряко.
                # Само горното не стигаше до дневника — измерено.
                "slug": "liiga",
                "extra": {"home_en": dom, "away_en": gost, "slug": "liiga",
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
        # 🔴 ОТГОВОРЪТ Е ОТГОВОР, ДОРИ ПРАЗЕН. Дотук `if m:` броеше успешно
        # прочетен файл без предстоящи мачове за «не можах да питам» — тоест
        # честната нула се маскираше като повреда. Мери се ЧЕТЕНЕТО, не
        # съдържанието.
        if d is None:
            mylchali.append("chl")
        else:
            pitani += 1
        for x in m:
            # 🔴 БЯЛ СПИСЪК, НЕ ЧЕРЕН. Дотук се махаше само «finished» и
            # всичко останало минаваше за предстоящо. Измерено върху 13-те
            # сезонни файла: 34 мача са «canceled» — сезонът 2020 е 32 от 32
            # отменени. Такава карта излиза за мач, който няма да се играе, и
            # виси неоценима завинаги. Черният списък пуска и всяко НОВО
            # състояние, което изворът измисли; белият пуска само познатото.
            if not isinstance(x, dict) or str(x.get("status")) not in CHL_PREDSTOYASHTI:
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
                "slug": "chl",
                "extra": {"home_en": dom, "away_en": gost, "slug": "chl",
                          "evro": "chl", "id": str(x.get("_entityId") or "")},
            })

    if not pitani:
        _mylchali[:] = sorted(set(LIGI))
        return NEPITAN
    # 🔴 ЧАСТИЧНИЯТ ПРОВАЛ СЕ КАЗВА НА ГЛАС. Спортът НЕ се спира — 24
    # истински срещи са по-добри от нула — но мълчалата лига се назовава
    # поименно. Инак «24 днес, 36 утре» изглежда като календар, а е повреда.
    _mylchali[:] = sorted(set(mylchali))
    if mylchali:
        print("    \U0001f3d2 МЪЛЧА: " + ", ".join(
            LIGI.get(k, {}).get("bg", k) for k in _mylchali)
            + " (изворът отказа) — днешните срещи са само от останалите")
    out.sort(key=lambda r: r["when"])
    return out[:TAVAN]


def mylchali():
    """Кои лиги са мълчали при последното питане. Празно = всички говориха.

    Съществува, за да може отчетът да го брои, вместо да разчита на печата.
    Печатът е за човек; броенето е за черната кутия.
    """
    return list(_mylchali)


# ─────────────────────────────────────────────────────────── РЕЗУЛТАТЪТ
def rezultat(zapis, sega=None, vzemi=None):
    """(голове_дом, голове_гост) за ИЗИГРАН мач. None = още няма.

    🔴 СЪЩЕСТВУВА, ЗАЩОТО БЕЗ НЕЯ КАРТИТЕ НЕ МОГАТ ДА СЕ ОЦЕНЯТ. Оценителят
    строи адрес ESPN/{път}/{slug}/scoreboard и сверява по НОМЕР на отбор.
    СМ Лига и Шампионската лига не са от ESPN и нямат такива номера — тоест
    без своя врата всяка европейска хокейна карта остава неоценена ЗАВИНАГИ.
    Намерено живо: картата «Jukurit — Sport» стоеше с `scored=False` и
    оценителят връщаше None.

    🔴 НЕ СЕ ВЯРВА НА ГОЛОВЕТЕ, докато `ended` не е True. При насрочен мач
    полетата са 0-0, а това НЕ значи „домакинът губи" — значи „още не е
    играно". Същият капан има и при коефициентите на Veikkaus, където след
    мача полето се преписва със сетълмент.
    """
    # Празен вход не бива да гърми: следващият ред пипа `zapis` пряко.
    zapis = zapis or {}
    ex = zapis.get("extra") or {}
    # 🔴 `slug` Е РАВНОПРАВЕН ВХОД. Дневникът носи лигата там, а `extra` не
    # се записва целият. Измерено: оценителят даваше (0, 4) за запис, за
    # който тази функция даваше None — защото той вписваше `extra.evro`
    # преди да я извика. Функция, която работи само през един викащ, е
    # счупена; поправката просто още не си е личала.
    lg = str(ex.get("evro") or zapis.get("evro")
             or zapis.get("slug") or "").lower()
    dom = str(zapis.get("home_id") or zapis.get("home") or "").strip()
    gost = str(zapis.get("away_id") or zapis.get("away") or "").strip()
    den = str(zapis.get("day") or "")[:10]
    if not lg or not dom or not gost:
        return None
    sega = sega or _dt.datetime.now(_dt.timezone.utc)

    if lg == "liiga":
        for sez in (_liiga_sezon(sega), _liiga_sezon(sega) - 1):
            d = liiga_surovo(sez, vzemi)
            tochni, blizki = [], []
            for x in (d or []):
                if not x.get("ended"):
                    continue
                if str(x.get("homeTeamName") or "").strip() != dom:
                    continue
                if str(x.get("awayTeamName") or "").strip() != gost:
                    continue
                den_x = str(x.get("start") or "")[:10]
                if den and den_x not in _sasedni(den):
                    continue
                try:
                    g = (int(x.get("homeTeamGoals")),
                         int(x.get("awayTeamGoals")))
                except (TypeError, ValueError):
                    continue
                (tochni if (not den or den_x == den) else blizki).append(g)
            res = _edinstveniyat(tochni, blizki)
            if res is not _NEREShEN:
                return res
        return None

    if lg == "chl":
        hh, _r = chl_hashove(vzemi)
        vz = vzemi if callable(vzemi) else _vzemi
        for hsh in reversed(hh[-2:] or hh):
            tochni, blizki = [], []
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
                if not p:
                    continue
                if p[0] != dom or p[1] != gost:
                    continue
                den_x = str(x.get("startDate") or "")[:10]
                if den and den_x not in _sasedni(den):
                    continue
                (tochni if (not den or den_x == den) else blizki).append(
                    (int(p[2]), int(p[3])))
            res = _edinstveniyat(tochni, blizki)
            if res is not _NEREShEN:
                return res
        return None
    return None


# Отделен белег за «в този сезон/файл не намерих нищо», за да не се бърка с
# «намерих, но е спорно» (и двете иначе биха били None и вторият случай щеше
# да продължи да търси в предишния сезон — точно каквото НЕ бива).
_NEREShEN = object()


def _edinstveniyat(tochni, blizki):
    """Кой резултат важи: точният ден бие съседния, спорът не се решава.

    🔴 ТОЧНИЯТ ДЕН Е ПЪРВИ И БЕЗУСЛОВЕН. Съседният ден съществува само
    заради часовите зони; той е ДОПУСК, не равностоен източник.

    🔴 ДВАМА КАНДИДАТИ = ОТКАЗ. Измерено живо: HPK — Kärpät играят на 06.03
    (3-2) и на 07.03 (6-3). Стар вид взимаше първия срещнат и лепваше 3-2
    на картата за 07.03 — фалшив резултат с уверен вид. По-добре картата да
    чака, отколкото да бъде оценена по чужд мач.
    """
    if tochni:
        edin = set(tochni)
        return tochni[0] if len(edin) == 1 else None
    if len(blizki) == 1:
        return blizki[0]
    if blizki:
        return None
    return _NEREShEN


def _sasedni(den):
    """Денят и съседните му. Часовите зони местят мача с ден в двете посоки.

    Дневникът пази деня по БЪЛГАРСКО време, а изворите — по свое. Мач в
    02:00 българско е предишният ден във Финландия. Без този допуск част от
    картите остават неоценени, а причината изглежда като „няма резултат".
    """
    try:
        d0 = _dt.date.fromisoformat(str(den)[:10])
    except ValueError:
        return {str(den)[:10]}
    return {(d0 + _dt.timedelta(days=k)).isoformat() for k in (-1, 0, 1)}


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
    # 🔴 ШЕСТ НЕИГРАНИ МАЧА НА «Гг» — с ГОЛОВЕ, точно както ги дава живият
    # извор: насроченият мач носи 0-0, а не празно. Шест е над прага от 5,
    # тоест ако `ended` бъде махнат, «Гг» ВЛИЗА в таблицата и проверката
    # долу почервенява.
    #
    # Преди този ред същата мутация минаваше безшумно: единственият неигран
    # мач беше един, «Вв» падаше по ПРАГА, и проверката «ненаиграният отбор
    # пада» мереше броя, не `ended`. Изречението беше вярно и не проверяваше
    # каквото твърди — най-скъпият вид проверка.
    for _i in range(6):
        _mnogo.append({"ended": False, "homeTeamName": "Гг",
                       "awayTeamName": "Дд",
                       "homeTeamGoals": 0, "awayTeamGoals": 0})

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
        # 🔴 И ТУРНИРНО-ОСЪЗНАТА, по същата причина като сезонната по-горе.
        # Турнирите станаха три; подложка, която дава едни и същи мачове на
        # трите, ги утроява (36 вместо 12) и тестът щеше да измерва
        # собствената си щедрост. Живият извор носи РАЗЛИЧНИ мачове във
        # всеки турнир — измерено: 480 · 60 · 65 записа, нула общи id.
        if "season=2026" in u and "tournament=runkosarja" in u:
            return _mnogo
        return []

    tb = tablica("liiga", _sega, _po_sezon)
    check("таблицата се строи от изиграните", set(tb) == {"Аа", "Бб"})
    check("ненаиграният отбор пада (под прага)", "Вв" not in tb)
    # 🔴 ТОВА мери `ended`, а горното мери прага. Двете изглеждат еднакво и
    # не са: «Гг» има шест неиграни мача — стига му броят, липсва му само
    # това да са ИГРАНИ.
    check("неигран мач не влиза в таблицата, дори да са много",
          "Гг" not in tb and "Дд" not in tb)
    check("прагът е точно 5", MIN_MACHOVE == 5)
    check("броят мачове е верен (12, не 24)", tb["Аа"]["gp"] == 12)
    # 🔴 МЕРИ СЕ СЕЗОНЪТ, НЕ АДРЕСЪТ. Адресите вече са шест (три турнира по
    # два сезона), а въпросът, който тази проверка задава, е «различават ли
    # се сезоните». Отслабването щеше да е да я махна; вярното е да я
    # насоча към това, което винаги е искала да каже.
    check("питани са ДВА различни сезона",
          len({u.split("season=")[-1] for u in _pitani}) == 2)
    check("и трите турнира се питат за всеки сезон", len(_pitani) == 6)
    check("нито един адрес не пита за целия сезон вкупом",
          all("tournament=" in u for u in _pitani))
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

    # ═══ ВРАТАТА ЗА РЕЗУЛТАТ (05.09.2026) ═══════════════════════════
    #
    # Три живи дефекта, всичките намерени с истински мачове, не с четене:
    #   1. адресът за СМ Лига гърмеше с 500 → лигата беше НЯМА
    #   2. съседният ден лепваше ЧУЖД мач → фалшив резултат
    #   3. функцията четеше само `extra.evro` → работеше само през оценителя
    #
    # Всичките проверки тук са ПОВЕДЕНЧЕСКИ и без мрежа.

    def _liiga_stub(mach):
        """Четец-подставка: помни какво са го питали, връща `mach`."""
        pitani = []

        def vz(url, surovo=False):
            pitani.append(url)
            if "tournament=runkosarja" in url:
                return list(mach)
            # Точно като живия сървър: турнир без данни връща 500 → None.
            return None
        return vz, pitani

    _m1 = {"ended": True, "start": "2026-03-06T16:30:00Z", "id": 1,
           "homeTeamName": "HPK", "awayTeamName": "Kärpät",
           "homeTeamGoals": 3, "awayTeamGoals": 2}
    _m2 = {"ended": True, "start": "2026-03-07T16:30:00Z", "id": 2,
           "homeTeamName": "HPK", "awayTeamName": "Kärpät",
           "homeTeamGoals": 6, "awayTeamGoals": 3}
    _m3 = {"ended": False, "start": "2026-03-20T16:30:00Z", "id": 3,
           "homeTeamName": "Ilves", "awayTeamName": "TPS",
           "homeTeamGoals": 0, "awayTeamGoals": 0}

    def _pit(den, dom="HPK", gost="Kärpät", mach=(_m1, _m2, _m3), klyuch="slug"):
        vz, _p = _liiga_stub(mach)
        _kesh_sur.clear()
        z = {"day": den, "home_id": dom, "away_id": gost, klyuch: "liiga"}
        try:
            return rezultat(z, _dt.datetime(2026, 3, 10,
                                            tzinfo=_dt.timezone.utc), vz)
        finally:
            _kesh_sur.clear()

    # ── 1 · ТУРНИРЪТ СЕ ПИТА ПОИМЕННО И ПРЪВ.
    # Измерено живо: `?season=2027` дава 500, `?tournament=…&season=2027`
    # дава 544 записа. Сървърът се пука, като събира турнири, които още не
    # съществуват. Проверява се ПО АДРЕСА, който излиза от модула.
    _vz, _pitani = _liiga_stub([_m1])
    _kesh_sur.clear()
    _d = liiga_surovo(2027, _vz)
    check("СМ Лига пита за поименен турнир",
          all("tournament=" in u for u in _pitani))
    check("турнирът стои ПРЕДИ сезона в адреса",
          all(u.index("tournament=") < u.index("season=") for u in _pitani))
    check("питат се повече от един турнир", len(_pitani) >= 2)
    check("един жив турнир стига за резултат", _d == [_m1])
    # 🔴 И ОБРАТНОТО: 500 при ЕДИН турнир НЕ Е отказ на извора, но 500 при
    # ВСИЧКИТЕ — е. Без тази разлика цял сезон би мълчал като „няма мачове".
    _kesh_sur.clear()
    check("всичките мълчат → None (отказ, не празно)",
          liiga_surovo(2027, lambda u, surovo=False: None) is None)
    _kesh_sur.clear()
    check("отговор с празен списък → празно, НЕ отказ",
          liiga_surovo(2027, lambda u, surovo=False: []) == [])
    _kesh_sur.clear()

    # ── 2 · ТОЧНИЯТ ДЕН БИЕ СЪСЕДНИЯ.
    # Измерено живо: HPK — Kärpät играят на 06.03 (3-2) и 07.03 (6-3).
    # Стар вид даваше 3-2 и на двете карти.
    check("06.03 дава своя резултат", _pit("2026-03-06") == (3, 2))
    check("07.03 дава СВОЯ, не съседния", _pit("2026-03-07") == (6, 3))
    # ── и когато спорът е неразрешим — ОТКАЗ, не догадка.
    # 🔴 ДУПКАТА Е НАРОЧНА: мачове на 06.03 и 08.03, въпрос за 07.03. Само
    # тогава и двата са съседни и точен няма. (Първата ми версия питаше за
    # 08.03 при мачове на 06 и 07 — но 06.03 е на два дни и не е съседен,
    # тоест кандидатът беше един и отговорът верен. Тестът мереше друго.)
    _dupka = ({"ended": True, "start": "2026-03-06T16:30:00Z", "id": 21,
               "homeTeamName": "HPK", "awayTeamName": "Kärpät",
               "homeTeamGoals": 3, "awayTeamGoals": 2},
              {"ended": True, "start": "2026-03-08T16:30:00Z", "id": 22,
               "homeTeamName": "HPK", "awayTeamName": "Kärpät",
               "homeTeamGoals": 6, "awayTeamGoals": 3})
    check("два съседни без точен → отказ",
          _pit("2026-03-07", mach=_dupka) is None)
    check("но точният ден между тях се решава",
          _pit("2026-03-06", mach=_dupka) == (3, 2))
    # ── а допускът ±1 работи, когато няма спор
    check("допускът ±1 хваща самотен мач",
          _pit("2026-03-19", "Ilves", "TPS",
               ({"ended": True, "start": "2026-03-20T16:30:00Z", "id": 9,
                 "homeTeamName": "Ilves", "awayTeamName": "TPS",
                 "homeTeamGoals": 5, "awayTeamGoals": 1},)) == (5, 1))

    # ── 3 · `slug` Е РАВНОПРАВЕН ВХОД.
    # Измерено: оценителят даваше (0,4), а `rezultat` — None за СЪЩИЯ запис,
    # защото четеше само `extra.evro`. Работеше само защото един викащ го
    # подпираше.
    check("работи през slug", _pit("2026-03-06", klyuch="slug") == (3, 2))
    check("работи и през evro", _pit("2026-03-06", klyuch="evro") == (3, 2))
    _kesh_sur.clear()
    _vz2, _ = _liiga_stub([_m1])
    check("работи и през extra.evro",
          rezultat({"day": "2026-03-06", "home_id": "HPK",
                    "away_id": "Kärpät", "extra": {"evro": "liiga"}},
                   _dt.datetime(2026, 3, 10, tzinfo=_dt.timezone.utc),
                   _vz2) == (3, 2))
    _kesh_sur.clear()

    # ── 4 · НЕИЗИГРАН МАЧ НЕ Е 0-0.
    # Живият извор дава `homeTeamGoals: 0, awayTeamGoals: 0, ended: False`
    # за насрочен мач. Прочетено буквално, това е „домакинът не отбеляза".
    check("неизигран мач не дава резултат",
          _pit("2026-03-20", "Ilves", "TPS") is None)

    # ── 5 · ЧУЖДОТО НЕ ВЛИЗА
    check("непозната лига → None",
          rezultat({"day": "2026-03-06", "home_id": "HPK",
                    "away_id": "Kärpät", "slug": "nhl"}) is None)
    check("празен запис → None", rezultat({}) is None)
    check("None вместо запис → None", rezultat(None) is None)
    check("без отбори → None",
          rezultat({"day": "2026-03-06", "slug": "liiga"}) is None)

    # ── 6 · РАЗСЪДНИКЪТ поотделно
    check("точният бие съседния", _edinstveniyat([(1, 0)], [(9, 9)]) == (1, 0))
    check("два различни точни → отказ",
          _edinstveniyat([(1, 0), (2, 0)], []) is None)
    check("два еднакви точни → минават",
          _edinstveniyat([(1, 0), (1, 0)], []) == (1, 0))
    check("един съседен → минава", _edinstveniyat([], [(4, 2)]) == (4, 2))
    check("два съседни → отказ", _edinstveniyat([], [(4, 2), (1, 1)]) is None)
    check("нищо → НЕРЕШЕН (търси в предишния сезон)",
          _edinstveniyat([], []) is _NEREShEN)
    check("НЕРЕШЕН не е None", _NEREShEN is not None)

    # ── 7 · СРЕЩИТЕ НОСЯТ ЛИГАТА В `slug`.
    # 🔴 ЖИВИЯТ ДЕФЕКТ, ОТ КОЙТО ТРЪГНА ВСИЧКО: картата «Jukurit — Sport»
    # стоеше със `slug=None` и не можеше да бъде оценена никога. Проверките
    # по-горе гледат `extra.evro` — но `extra` НЕ СЕ ЗАПИСВА целият в
    # дневника. До оценителя стига `slug`, и точно за него нямаше проверка.
    nuliray()
    _r7 = srechti(_sega, 72, None, _podhvarlen)
    check("всяка среща носи slug", bool(_r7) and all(x.get("slug") for x in _r7))
    check("slug сочи същата лига като extra.evro",
          all(x["slug"] == x["extra"]["evro"] for x in _r7))
    # 🔴 И В `extra` — ОТТАМ ГО ЧЕТЕ `log_pick`. Само горното ниво не
    # стигаше до дневника: измерено живо, картата влизаше със slug=None и
    # падаше в sdb_result, който лепва съседен мач по име.
    check("slug е и в extra (log_pick чете оттам)",
          all((x.get("extra") or {}).get("slug") == x["slug"] for x in _r7))
    check("и двете лиги дават slug",
          {x["slug"] for x in _r7} == {"liiga", "chl"})
    nuliray()

    # ═══ РЕДЪТ НА СЕЗОННИТЕ ФАЙЛОВЕ (05.09.2026) ═══════════════════
    #
    # 🔴 ПОДЛОЖКАТА Е С ПЕТ ХЕША, И АЗБУКАТА В НЕЯ ЛЪЖЕ НАРОЧНО.
    # Досегашната подложка имаше ЕДИН хеш — а проверка с един елемент не
    # може да различи подредба. Тя беше тавтология и точно затова
    # `sorted(...)[-1]` живя незабелязан: измерено живо, азбучно последният
    # днес Е текущият сезон, но само по случайност (~1 на 100 за следващия).
    def _stranica(tekusht, hesove):
        """HTML като на живия извор: обява за текущ сезон + връзки нов→стар."""
        glava = ('corebine.pageSettings = {"attachments":{"currentSeason":'
                 '{"_entityId":"%s","_type":"Season"}}};' % tekusht
                 ) if tekusht else ""
        return glava + "".join('<a href="/x/' + CHL_PREFIX + h + '.json">s</a>'
                               for h in hesove)

    # нов → стар, както ги дава страницата; азбучно последен е "ff…",
    # но обявеният текущ е "0a…" — тоест старият избор би сгрешил.
    _nov_star = ["0a" + "0" * 18, "ee" + "1" * 18, "ff" + "2" * 18,
                 "cc" + "3" * 18, "11" + "4" * 18]
    nuliray()
    _hh, _rez = chl_hashove(
        lambda u, surovo=False: _stranica(_nov_star[0], _nov_star))
    check("обявеният текущ сезон е последният (hh[-1])",
          _hh[-1] == _nov_star[0])
    check("а азбучно последен е ДРУГ (подложката лъже нарочно)",
          sorted(_hh)[-1] != _nov_star[0])
    check("нищо не се губи по пътя", set(_hh) == set(_nov_star))
    check("не се дублира", len(_hh) == len(set(_hh)))
    check("това не е резерва", _rez is False)
    # 🔴 ВТОРИЯТ ОТЗАД Е ВТОРИЯТ НАЙ-НОВ, не случаен. `rezultat` търси в
    # `hh[-2:]`; преди поправката там влизаше сезон 2021 редом с 2026.
    check("вторият отзад е вторият най-нов по страницата",
          _hh[-2] == _nov_star[1])

    # 🔴 И ОБЯВАТА ДА БИЕ РЕДА — с подложка, в която ДВЕТЕ СЕ РАЗЛИЧАВАТ.
    # Първата ми версия слагаше обявения сезон и НАЙ-ОТПРЕД по ред: тогава
    # редът сам даваше верния отговор и стъпалото с обявата не се изпитваше.
    # Мутация «обявата не се слага накрая» ОЦЕЛЯ — тоест проверката
    # съдържаше отговора си. Тук обявеният е ТРЕТИ по ред: само четенето на
    # обявата може да го изкара последен.
    nuliray()
    _hh_ob, _ = chl_hashove(
        lambda u, surovo=False: _stranica(_nov_star[2], _nov_star))
    check("обявата бие реда на страницата", _hh_ob[-1] == _nov_star[2])
    check("а редът сам би дал ДРУГ (подложката ги разделя)",
          _nov_star[2] != _nov_star[0])
    check("изместеният не изчезва", set(_hh_ob) == set(_nov_star))

    # ── без обява: редът на страницата решава (пак нов → стар)
    nuliray()
    _hh2, _ = chl_hashove(lambda u, surovo=False: _stranica("", _nov_star))
    check("без обява последният пак е най-новият по страницата",
          _hh2[-1] == _nov_star[0])
    check("и той пак НЕ Е азбучно последният",
          sorted(_hh2)[-1] != _hh2[-1])

    # ── обявен, но непознат хеш: не се измисля, пада на реда
    nuliray()
    _hh3, _ = chl_hashove(
        lambda u, surovo=False: _stranica("ab" + "9" * 18, _nov_star))
    check("непозната обява не влиза в списъка",
          ("ab" + "9" * 18) not in _hh3)
    check("при непозната обява остава редът на страницата",
          _hh3[-1] == _nov_star[0])

    # ── и резервата пак работи
    nuliray()
    _hh4, _rez4 = chl_hashove(lambda u, surovo=False: None)
    check("мълчаща страница → резерва, казано на глас",
          _hh4 == [CHL_REZERVA] and _rez4 is True)
    nuliray()
    _hh5, _rez5 = chl_hashove(lambda u, surovo=False: "страница без хешове")
    check("страница без хешове → резерва",
          _hh5 == [CHL_REZERVA] and _rez5 is True)
    nuliray()

    # ═══ МЪЛЧАЩАТА ЛИГА СЕ НАЗОВАВА (05.09.2026) ═══════════════════
    #
    # 🔴 Един брояч за два независими извора значи, че живата лига крие
    # мъртвата. Измерено днес: liiga.fi даде HTTP 500 час и половина,
    # `srechti` върна 24 честни срещи само от Шампионската лига и НЕ КАЗА
    # НИЩО. Разликата между 24 и 36 не се виждаше никъде.
    _sega_m = _dt.datetime(2026, 9, 5, 10, 0, tzinfo=_dt.timezone.utc)
    _liiga_edin = [{"ended": False, "started": False, "id": 77,
                    "start": "2026-09-05T14:00:00Z",
                    "homeTeamName": "Аа", "awayTeamName": "Бб"}]
    _chl_edin = [{"status": "not-started", "_entityId": "e1",
                  "startDate": "2026-09-05T15:00:00Z",
                  "teams": {"home": {"name": "Вв"}, "away": {"name": "Гг"}}}]
    _chl_otm = [{"status": "canceled", "_entityId": "e2",
                 "startDate": "2026-09-05T16:00:00Z",
                 "teams": {"home": {"name": "Дд"}, "away": {"name": "Ее"}}}]

    def _dva(liiga_dava, chl_dava):
        """Четец, който дава каквото му кажеш за всяка от двете лиги."""
        def vz(u, surovo=False):
            if surovo:
                return "x" + CHL_PREFIX + "a" * 24 + ".json"
            if "liiga.fi" in u:
                return liiga_dava
            return chl_dava
        return vz

    nuliray()
    _r_m = srechti(_sega_m, 72, None, _dva(None, _chl_edin))
    check("мъртва СМ Лига НЕ спира спорта",
          _r_m is not NEPITAN and len(_r_m) == 1)
    check("но мъртвата лига се НАЗОВАВА", mylchali() == ["liiga"])
    nuliray()
    _r_m2 = srechti(_sega_m, 72, None, _dva(_liiga_edin, None))
    check("и в другата посока", _r_m2 is not NEPITAN and len(_r_m2) == 1)
    check("мъртвата ШХЛ се назовава", mylchali() == ["chl"])
    nuliray()
    _r_m3 = srechti(_sega_m, 72, None, _dva(_liiga_edin, _chl_edin))
    check("двете живи → две срещи", len(_r_m3) == 2)
    check("никой не мълчи → празен списък", mylchali() == [])
    nuliray()
    _r_m4 = srechti(_sega_m, 72, None, _dva(None, None))
    check("двете мъртви → NEPITAN (както досега)", _r_m4 is NEPITAN)
    check("и двете се назовават", sorted(mylchali()) == ["chl", "liiga"])

    # 🔴 ПРАЗЕН ОТГОВОР Е ОТГОВОР. Успешно прочетен файл без предстоящи
    # мачове значи «няма мачове», не «изворът отказа». Дотук `if m:` броеше
    # празния списък за неуспех — същото сливане, обърнато наопаки.
    nuliray()
    _r_p = srechti(_sega_m, 72, None, _dva([], []))
    check("двата празни отговора НЕ са NEPITAN", _r_p is not NEPITAN)
    check("празният отговор не е мълчание", mylchali() == [])
    check("и не ражда срещи от нищото", _r_p == [])

    # 🔴 БЯЛ СПИСЪК, НЕ ЧЕРЕН. Измерено върху 13-те сезонни файла: 34 мача
    # са «canceled». Дотук се махаше само «finished», тоест отмененият
    # излизаше като предстоящ и картата му висеше неоценима завинаги.
    nuliray()
    _r_o = srechti(_sega_m, 72, None, _dva(None, _chl_otm))
    check("ОТМЕНЕН мач не влиза в срещите", _r_o is NEPITAN or len(_r_o) == 0)
    nuliray()
    _r_o2 = srechti(_sega_m, 72, None, _dva(None, _chl_edin + _chl_otm))
    check("отмененият пада, предстоящият остава",
          len(_r_o2) == 1 and _r_o2[0]["home"] == "Вв")
    nuliray()
    _r_o3 = srechti(_sega_m, 72, None,
                    _dva(None, [dict(_chl_otm[0], status="новоизмислено")]))
    check("НЕПОЗНАТО състояние също не влиза (бял списък)",
          _r_o3 is NEPITAN or len(_r_o3) == 0)
    check("белият списък е точно едно състояние",
          CHL_PREDSTOYASHTI == {"not-started"})
    nuliray()

    # ═══ ТАБЛИЦАТА НЕ КЕШИРА ПРОВАЛ (05.09.2026) ═══════════════════
    #
    # 🔴 Измерено: подложка, която мълчи ВЕДНЪЖ и после отговаря, връщаше
    # празна таблица и на втория, и на третия опит, БЕЗ нова заявка.
    # `predictor.model_hockey` при празна таблица връща None — тоест
    # всичките карти на спорта падаха за целия рън с причина «няма
    # история», докато истината беше «изворът падна».
    # 🔴 МЪЛЧИ ПО КЛЮЧ, НЕ ПО БРОЙ. Първата ми версия мълчеше първите N
    # заявки — но `tablica` прави ШЕСТ (три турнира по два сезона) и
    # подложката проговаряше по средата на СЪЩИЯ опит. Тестът мереше
    # собственото си броене, не поведението на кеша.
    _tb_br = [0]
    _tb_nem = [True]

    def _tb_kapriz(_unused=0):
        def vz(u, surovo=False):
            _tb_br[0] += 1
            if _tb_nem[0]:
                return None
            if surovo:
                return "x" + CHL_PREFIX + "b" * 24 + ".json"
            return [{"ended": True, "id": 100 + k,
                     "start": "2026-01-%02dT12:00:00Z" % (k + 1),
                     "homeTeamName": "Аа" if k % 2 else "Бб",
                     "awayTeamName": "Бб" if k % 2 else "Аа",
                     "homeTeamGoals": 3, "awayTeamGoals": 2} for k in range(12)]
        return vz

    nuliray()
    _kesh_tab.clear()
    _tb_br[0] = 0
    _tb_nem[0] = True
    _t1 = tablica("liiga", _sega, _tb_kapriz())
    check("първата таблица е празна (изворът мълчи)", _t1 == {})
    check("и НЕ Е кеширана", "liiga" not in _kesh_tab)
    _tb_nem[0] = False
    _t2 = tablica("liiga", _sega, _tb_kapriz())
    check("вторият опит пита пак и намира отбори", len(_t2) >= 2)
    check("а успехът СЕ кешира", _kesh_tab.get("liiga") == _t2)
    _kesh_tab.clear()
    nuliray()

    # 🔴 И ЧЕСТНАТА ПРАЗНОТА СЕ КЕШИРА. Празна таблица в началото на сезон
    # НЕ е повреда — тя не бива да струва нови заявки всеки път. Затова се
    # сравнява броячът на провалите, а не самата празнота.
    _t3 = tablica("liiga", _sega, lambda u, surovo=False: [])
    check("отговор с празен списък дава празна таблица", _t3 == {})
    check("но ТЯ Е кеширана (честна нула, не повреда)", "liiga" in _kesh_tab)
    _kesh_tab.clear()
    nuliray()

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
