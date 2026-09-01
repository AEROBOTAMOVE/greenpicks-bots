# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — КОЙ Е СПЕЧЕЛИЛ В ЕЛЕКТРОННИТЕ СПОРТОВЕ 🎮

Един въпрос: има ли безплатен извор, който казва ПОИМЕННО кой е спечелил
мачовете, за които esport.py вече взима цена от Pinnacle.

═══════════════════════════════════════════════════════════════════════════
ЗАЩО SMARKETS, А НЕ „някой сайт за еспорт“ (измерено на 01.09.2026)
═══════════════════════════════════════════════════════════════════════════

Обходени са 56 адреса. Почти всички сайтове за електронни спортове, които
човек би изброил наизуст, са зад Cloudflare и връщат 403/1010 на обикновена
заявка: HLTV, bo3.gg, Dotabuff, OpenDota, GosuGamers, draft5.gg, escorenews,
egamersworld, thespike.gg, Leaguepedia (lol.fandom.com), Oddspedia,
Sofascore. Liquipedia — най-обещаващата на хартия — връща 429 с CAPTCHA и
собствените ѝ условия забраняват обхождане; вратата е ЗАТВОРЕНА ОТ ТЯХ.

Smarkets е борса за залози. Това не е „още един сайт с таблици“ — победителят
там не е новина, а СЕТЪЛМЪНТ: по него са платени пари. Затова полето се казва
`state_or_outcome` и има точно две стойности — „winner“ и „loser“.

    /v3/events/?type=csgo_match&state=ended&limit=1000&sort=start_datetime,id
    /v3/events/{id}/markets/            -> пазарът WINNER_2_WAY
    /v3/markets/{id}/contracts/         -> двата отбора ПО ИМЕ + изходът

Измерено на 31.08.2026: 41 завършили мача, 40 с обявен победител (41-вият е
`voided` — мачът е отменен, тоест мълчанието е ЧЕСТНО, а не липса).

СВЕРЕНО СРЕЩУ ВТОРИ ИЗВОР: 91 мача по League of Legends, за които и Smarkets,
и op.gg (GraphQL, без ключ) казват победител — 91 съгласни, 0 несъгласни.

═══════════════════════════════════════════════════════════════════════════
🔴 ФИЛТЪРЪТ ПО ДЕН НЕ Е УКРАСА — БЕЗ НЕГО ИЗВОРЪТ ЛЪЖЕ
═══════════════════════════════════════════════════════════════════════════

Първата версия на този файл вземаше страницата (до 1000 събития, седмици
наред) и търсеше в НЕЯ по имена. Един и същ чифт отбори играе по няколко пъти
в месеца, затова се хващаше НАЙ-СТАРАТА им среща. Сверката срещу op.gg тогава
даде 11 разминавания от 102. Със рязането по [ден−1, ден, ден+1] —
91 от 91, нула разминавания. Числото, което улови дефекта, беше ВТОРИЯТ
ИЗВОР; сам по себе си Smarkets отговаряше уверено и грешно.

Прозорецът е ±1 ден, защото `day` в дневника е по СОФИЯ, а Smarkets пише UTC:
мач в 22:00 UTC е вече „утре" в дневника.

═══════════════════════════════════════════════════════════════════════════
🔴 НИКАКЪВ ПОДНИЗ — СЪЩАТА ЗАБРАНА, КАКТО В esport.py
═══════════════════════════════════════════════════════════════════════════

„paiN" и „paiN Academy" са два отбора. Сравнява се ЦЯЛОТО име, сведено до
същина, плюс махане на шумови думи и шепа ИЗМЕРЕНИ псевдоними. Спор ли има —
МЪЛЧИ СЕ. Проверено: paiN ↮ paiN Academy, MIBR ↮ ex-MIBR Academy,
Spirit ↮ Spirit Academy, B8 ↮ B8 Academy, 1W ↮ 1win Academy.
А диакритиката се маха, защото техният „Grêmio Esports" е нашият „Gremio".

═══════════════════════════════════════════════════════════════════════════
КОЛКО ОТ НАШИТЕ МАЧОВЕ СЕ НАМИРАТ ТАМ (31 живи среща от esport.fixtures())
═══════════════════════════════════════════════════════════════════════════

    CS2                15 от 16   94%
    Dota 2              1 от 1   100%
    League of Legends   5 от 15   33%   ← само големите лиги (LCK/LPL/LEC)
    Valorant            0 от 0     —    ← Smarkets НЯМА valorant_match

Липсващите при LoL са малките регионални лиги (HLL, LFL, Rift Legends, LES,
LRS, LRN, Prime League, Circuito Desafiante). Те ги няма и в op.gg. Затова:
PREDICT_ESPORT_IGRI="cs2" е честната първа стъпка; „lol" ще виси неотсъден в
две трети от случаите, а точно това трови процента на целия спорт.

МЪЛЧАНИЕТО НЕ Е НУЛА: върне ли се None, картата остава неотсъдена — точно
както преди. Никога не се връща измислен изход.
"""
import datetime as _dt
import json
import unicodedata
import urllib.parse
import urllib.request

BAZA = "https://api.smarkets.com"
TIMEOUT = 12
STRANICI = 8               # горна граница на обхода, за да не виси никога

# Нашият ключ за игра -> техният тип събитие. Няма valorant при тях.
TIPOVE = {"cs2": "csgo_match",
          "lol": "league_of_legends_match",
          "dota2": "dota_2_match"}

# Думи, които НЕ различават отбор. „Academy", „Juniors", „ex-" ги НЯМА тук —
# те са ДРУГ отбор. „cs" е тук заради техния „DENDELE CS" срещу нашия
# „DENDELE" (измерено на 01.09.2026).
SHUM = {"esports", "esport", "esportsclub", "gaming", "team", "club",
        "org", "gg", "the", "of", "cs"}

# Съкращения, които НЯМА как да се получат с махане на шумова дума. Всяко е
# ПУСНАТО срещу техния днешен отговор (01.09.2026):
#   1w      -> „1WIN"            (без него: None; с него: намира)
#   pcific  -> „WRAITH PCIFIC"   (без него: None; с него: намира)
#   lp      -> „largadosypelados"(без него: None; с него: намира)
# 🔴 СПИСЪКЪТ Е КЪС НАРОЧНО. Измислен псевдоним е ПО-ЛОШ от липсващия:
# липсващият дава мълчание, измисленият дава ЧУЖД победител.
PSEVDONIMI = {
    "navi": "natusvincere",
    "mousesports": "mouz",
    "prx": "paperrex",
    "1w": "1win",
    "pcific": "wraithpcific",
    "lp": "largadosypelados",
}

_kesh_den = {}
_kesh_pob = {}
BROY = [0]                 # колко заявки е пуснал този процес — за отчета


# ─────────────────────────────────────────────────────────── ИЗВОРЪТ
def _j(pat):
    rq = urllib.request.Request(BAZA + pat,
                                headers={"Accept": "application/json"})
    BROY[0] += 1
    with urllib.request.urlopen(rq, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


# ─────────────────────────────────────────────────────────── ИМЕНАТА
def _bezudar(s):
    """Маха диакритиката: „Grêmio" -> „Gremio", „Honvéd" -> „Honved"."""
    n = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch for ch in n if not unicodedata.combining(ch))


def _stegni(s):
    return "".join(ch for ch in _bezudar(s).lower() if ch.isalnum())


def _dumi(s):
    tek, out = "", []
    for ch in _bezudar(s).lower():
        if ch.isalnum():
            tek += ch
        elif tek:
            out.append(tek)
            tek = ""
    if tek:
        out.append(tek)
    return out


def varianti(ime):
    """Ключовете, под които отборът може да се срещне. Празно при боклук."""
    cyalo = _stegni(ime)
    if not cyalo:
        return ()
    out = [cyalo]
    d = _dumi(ime)
    bez = [w for w in d if w not in SHUM] or d
    sl = "".join(bez)
    if sl and sl not in out:
        out.append(sl)
    for k in list(out):
        p = PSEVDONIMI.get(k)
        if p and p not in out:
            out.append(p)
    return tuple(out)


def _sasht(a, b):
    va, vb = varianti(a), varianti(b)
    return bool(set(va) & set(vb))


# ─────────────────────────────────────────────────────────── ДЕНЯТ
def dni(igra, den):
    """Завършилите техни мачове в [ден−1, ден+1]. Списък (празен = няма).

    Кешира се по (игра, ден): вторият отсъден мач от същия ден струва нула
    заявки. При отказ на извора се връща празен списък — викащият го чете
    като „не намерих", а не като „няма победител".
    """
    tip = TIPOVE.get(igra)
    if not tip:
        return []
    klyuch = (tip, den)
    if klyuch in _kesh_den:
        return _kesh_den[klyuch]
    try:
        d0 = _dt.datetime.strptime(str(den or ""), "%Y-%m-%d")
    except ValueError:
        return []
    okolo = {(d0 + _dt.timedelta(days=k)).strftime("%Y-%m-%d")
             for k in (-1, 0, 1)}
    kray = (d0 + _dt.timedelta(days=1)).strftime("%Y-%m-%d")
    surovi = []
    q = {"type": tip, "state": "ended", "limit": "1000",
         "sort": "start_datetime,id"}
    for _ in range(STRANICI):
        try:
            j = _j("/v3/events/?" + urllib.parse.urlencode(q))
        except Exception:                                    # noqa: BLE001
            break
        ev = j.get("events") or []
        surovi.extend(ev)
        if ev and str(ev[-1].get("start_date") or "") > kray:
            break
        nx = (j.get("pagination") or {}).get("next_page")
        if not nx:
            break
        # 🔴 with_new_type=False в техния next_page вдига Cloudflare (403).
        # Махането му е ЗАДЪЛЖИТЕЛНО, инак обходът спира на втората страница.
        q = {k: v[0] for k, v in
             urllib.parse.parse_qs(urllib.parse.urlparse(nx).query).items()
             if k != "with_new_type"}
    out = [e for e in surovi
           if str(e.get("start_date") or "") in okolo]
    _kesh_den[klyuch] = out
    return out


# ─────────────────────────────────────────────────────────── ПОБЕДИТЕЛЯТ
def pobeditel(event_id):
    """Името на победителя за едно тяхно събитие, или None.

    None значи: няма пазар „победител", не е сетълнат, отменен е (voided),
    или изходите не са точно един победител и един губещ. Всичко това е
    мълчание, не изход.
    """
    eid = str(event_id or "")
    if not eid:
        return None
    if eid in _kesh_pob:
        return _kesh_pob[eid]
    ime = None
    try:
        ms = (_j("/v3/events/" + eid + "/markets/").get("markets") or [])
        mid = None
        for m in ms:
            if (m.get("market_type") or {}).get("name") == "WINNER_2_WAY":
                mid = m.get("id")
                break
        if mid:
            ks = (_j("/v3/markets/" + str(mid) + "/contracts/")
                  .get("contracts") or [])
            pob = [k for k in ks if k.get("state_or_outcome") == "winner"]
            zag = [k for k in ks if k.get("state_or_outcome") == "loser"]
            if len(pob) == 1 and len(zag) == 1:
                ime = str(pob[0].get("name") or "") or None
    except Exception:                                        # noqa: BLE001
        ime = None
    _kesh_pob[eid] = ime
    return ime


def _v_prozoreca(e, den):
    """В прозореца [ден−1, ден+1] ли е събитието. Втора ключалка на деня.

    🔴 ЗАЩО ДВА ПЪТИ. Първата ключалка е в `dni`. Тя обаче реже СПИСЪКА, а
    списъкът може да дойде и отвън (подхвърлен от проверка) или от кеш, пълнен
    за друг ден. Точно това пропускане даде 11 грешни победителя от 102 при
    сверката срещу op.gg: страницата носи седмици, а един чифт отбори играе
    по няколко пъти — и се взимаше най-старата им среща.
    """
    try:
        d0 = _dt.datetime.strptime(str(den or ""), "%Y-%m-%d")
    except ValueError:
        return False
    okolo = {(d0 + _dt.timedelta(days=k)).strftime("%Y-%m-%d")
             for k in (-1, 0, 1)}
    return str(e.get("start_date") or "") in okolo


def rezultat(dom, gost, den, igra, spisak=None):
    """(1, 0) / (0, 1) ПО НАШИЯ РЕД дом–гост, или None.

    ИСКАТ СЕ И ДВАТА ОТБОРА едновременно, И денят. Един отбор не стига:
    точно това лепна „Bury FC" на „Atlanta United FC" при футбола.

    `spisak` се подава от самопроверката — тогава нито една заявка не тръгва.
    """
    vd, vg = set(varianti(dom)), set(varianti(gost))
    if not vd or not vg or vd & vg:
        return None
    redove = dni(igra, den) if spisak is None else spisak
    for e in redove:
        if not isinstance(e, dict) or not _v_prozoreca(e, den):
            continue
        nm = str(e.get("name") or "")
        if " vs " not in nm:
            continue
        a, b = [x.strip() for x in nm.split(" vs ", 1)]
        va, vb = set(varianti(a)), set(varianti(b))
        if not ((vd & va and vg & vb) or (vd & vb and vg & va)):
            continue
        p = pobeditel(e.get("id"))
        if not p:
            return None
        vp = set(varianti(p))
        if vp & vd:
            return (1, 0)
        if vp & vg:
            return (0, 1)
        return None                    # победител, който не е нито един от двата
    return None


# ─────────────────────────────────────────────────────────── ПРОВЕРКИ
def selftest():
    """Проверки БЕЗ мрежа. Всяка е с мутация, която я поваля."""
    lo, ne = [], []

    def check(ime, uslovie):
        (lo if uslovie else ne).append(ime)

    # Имената: капанът „paiN"
    check("paiN != paiN Academy", not _sasht("paiN", "paiN Academy"))
    check("MIBR != ex-MIBR Academy", not _sasht("MIBR", "ex-MIBR Academy"))
    check("Spirit != Spirit Academy", not _sasht("Spirit", "Spirit Academy"))
    check("B8 != B8 Academy", not _sasht("B8", "B8 Academy"))
    check("1W != 1win Academy", not _sasht("1W", "1win Academy"))
    # Имената: това, което ТРЯБВА да съвпада (всяко е живо мерено)
    check("Nemesis = Team Nemesis", _sasht("Nemesis", "Team Nemesis"))
    check("Gremio = Grêmio Esports", _sasht("Gremio", "Grêmio Esports"))
    check("DENDELE = DENDELE CS", _sasht("DENDELE", "DENDELE CS"))
    check("Bilibili = Bilibili Gaming", _sasht("Bilibili", "Bilibili Gaming"))
    check("1W = 1WIN", _sasht("1W", "1WIN"))
    check("Hanwha Life = Hanwha Life Esports",
          _sasht("Hanwha Life", "Hanwha Life Esports"))
    check("празно име не съвпада с нищо", not _sasht("", "MOUZ"))
    # Игрите
    check("valorant НЯМА тип при тях", "valorant" not in TIPOVE)
    check("трите игри имат тип", len(TIPOVE) == 3)
    # Денят
    check("грешна дата -> празно", dni("cs2", "не-дата") == [])
    check("непозната игра -> празно", dni("valorant", "2026-08-31") == [])
    # Сентинелът
    check("непозната игра -> None", rezultat("A", "B", "2026-08-31", "x") is None)
    check("еднакви имена -> None",
          rezultat("MOUZ", "MOUZ", "2026-08-31", "cs2", spisak=[]) is None)
    # 🔴 ДЕНЯТ. Подхвърлен списък => нула заявки. Същият чифт отбори играе
    # два пъти: веднъж В прозореца, веднъж далеч преди него. Взима се само
    # този от прозореца, а далечният не дава изход изобщо.
    _kesh_pob["близък"] = "MOUZ"
    _kesh_pob["далечен"] = "Spirit"
    blizuk = {"id": "близък", "start_date": "2026-08-30", "name": "MOUZ vs Spirit"}
    dalechen = {"id": "далечен", "start_date": "2026-08-02", "name": "MOUZ vs Spirit"}
    check("мач от прозореца се отсъжда",
          rezultat("MOUZ", "Spirit", "2026-08-31", "cs2",
                   spisak=[blizuk]) == (1, 0))
    check("мач ИЗВЪН прозореца се пропуска",
          rezultat("MOUZ", "Spirit", "2026-08-31", "cs2",
                   spisak=[dalechen]) is None)
    check("далечният не бие близкия",
          rezultat("MOUZ", "Spirit", "2026-08-31", "cs2",
                   spisak=[dalechen, blizuk]) == (1, 0))
    check("обърнат ред дом-гост се обръща и в изхода",
          rezultat("Spirit", "MOUZ", "2026-08-31", "cs2",
                   spisak=[blizuk]) == (0, 1))
    _kesh_pob["чужд"] = "FaZe"
    check("чужд победител -> None",
          rezultat("MOUZ", "Spirit", "2026-08-31", "cs2",
                   spisak=[{"id": "чужд", "start_date": "2026-08-31",
                            "name": "MOUZ vs Spirit"}]) is None)
    _kesh_pob["празен"] = None
    check("несетълнат мач -> None",
          rezultat("MOUZ", "Spirit", "2026-08-31", "cs2",
                   spisak=[{"id": "празен", "start_date": "2026-08-31",
                            "name": "MOUZ vs Spirit"}]) is None)
    for k in ("близък", "далечен", "чужд", "празен"):
        _kesh_pob.pop(k, None)
    # 🔴 РЕДЪТ СЪС СМЕТКАТА Е ЗАДЪЛЖИТЕЛЕН (01.09.2026).
    # vsichki_testove.py чете ЧИСЛА, не думи — модул без този ред се
    # брои за „проблемен", колкото и зелен да е. Форматът е същият като
    # при boks.py и esport.py, за да го хване същият четец.
    print("САМОПРОВЕРКА НА ESPORT_REZ: " + str(len(lo)) + " наред, "
          + str(len(ne)) + " счупени")
    for _x in ne:
        print("   счупено: " + str(_x))
    return not ne


def zhivo(den=None):
    """Живо мерене: колко от вчерашните им мачове имат обявен победител."""
    if den is None:
        den = (_dt.datetime.now(_dt.timezone.utc)
               - _dt.timedelta(days=1)).strftime("%Y-%m-%d")
    for igra in TIPOVE:
        ev = [e for e in dni(igra, den) if str(e.get("start_date")) == den]
        s = sum(1 for e in ev if pobeditel(e.get("id")))
        print("  %-6s %s: %d мача, %d с победител" % (igra, den, len(ev), s))
    print("  заявки: " + str(BROY[0]))


if __name__ == "__main__":
    selftest()
    zhivo()
