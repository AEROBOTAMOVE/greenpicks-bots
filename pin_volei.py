# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ВТОРА ЦЕНА ЗА ВОЛЕЙБОЛА 🏐📉

Един въпрос: щом Pinnacle пак котира волейбол, защо нашите карти пак нямат цена?

═══════════════════════════════════════════════════════════════════════════
ЗАЩО СЪЩЕСТВУВА (25.08.2026)
═══════════════════════════════════════════════════════════════════════════

Волейболът стоеше на 10% покритие на пазарна цена. Обяснението в pinnacle.py
беше: „ТЕ НЯМАТ ТОЗИ СПОРТ — 0 лиги, 0 мача, ВИНАГИ" (мерено 18-19.08.2026).

ИЗМЕРЕНО НА ЖИВО ДНЕС, 25.08.2026 — това вече НЕ Е ВЯРНО:
    /sports (живо)              -> Volleyball, matchupCount = 10
    /sports/34/matchups         -> 21 мача
    /sports/34/markets/straight -> 255 пазара, moneyline има
Тоест вратата се е отворила сама (EuroVolley почна) и никой не я е проверил
пак. Числото „0 винаги" е било вярно за деня, в който е мерено.

🔴 НО ОТВОРЕНАТА ВРАТА НЕ СТИГА — И ЕТО ТОЧНОТО ЧИСЛО.
Питах pinnacle.ceni_za('volleyball', ...) с имената ТАКИВА, КАКВИТО СА В
ДНЕВНИКА (кирилица) и със същите имена на латиница:

    Унгария     vs Германия   -> (None, None, None)      Hungary vs Germany  -> (8.33, 1.08)
    Полша       vs Словения   -> (None, None, None)      Poland  vs Slovenia -> (1.27, 3.83)
    Швеция      vs Хърватия   -> (None, None, None)      Sweden  vs Croatia  -> (1.31, 3.53)
    Нидерландия vs Испания    -> (None, None, None)      Netherl.vs Spain    -> (1.06, 9.28)
    Czech Rep.  vs Украйна    -> (None, None, None)      Czech   vs Ukraine  -> (1.29, 3.66)

ПЕТ ОТ ПЕТ мълчат на кирилица и ПЕТ ОТ ПЕТ дават цена на латиница. Тоест
цената е БИЛА там през цялото време; заключалката е азбуката. `pinnacle.py`
сравнява по ФАМИЛИЯ (правено за тенисисти) и „Румъния" никога не среща
„Romania".

ЗАЩО НЕ ПИША НОВА КАРТА БЪЛГАРСКО->ЛАТИНСКО
Защото я ИМА: `volley_evro.kanon()` вече свежда „Румъния", „Romania",
„France (W)" и „FRA" до една същина, с махнат пол и с псевдоними
(turkiye->turkey, unitedstates->usa). Този модул СЪБИРА двете половини,
които вече съществуват поотделно: нормализацията на volley_evro и цената на
pinnacle. Нищо от двата файла не се пипа.

═══════════════════════════════════════════════════════════════════════════
🔴 ВТОРАТА ПРИЧИНА: НУЛАТА, КОЯТО ЛЪЖЕ
═══════════════════════════════════════════════════════════════════════════

Днес хванах Bovada (източникът на цена на volley_evro) да прави точно това:

    първо питане        -> 736 341 байта, 147 събития тенис на маса
    следващите четири   -> HTTP 200, тяло „[]", 0 събития
    после и футболът    -> HTTP 200, тяло „[]", 0 събития

Футболът НИКОГА няма нула мача. Тоест източникът е бил запушен (лимит), а е
отговарял с успех и празен списък. За кода отвън „няма пазар" и „не ме пускат
повече" изглеждат ЕДНАКВО.

Затова тук стои `izvor_zhiv()`: пита се и ЕТАЛОНЕН спорт, който винаги има
мачове. Нула волейбол при нула еталон = източникът е мъртъв, мълчи се. Нула
волейбол при жив еталон = честна нула, няма пазар днес.

  python pin_volei.py --selftest   — проверките, БЕЗ мрежа
  python pin_volei.py --zhivo      — истинско питане, за очи
"""
import sys

# Нормализацията се взема НА ЗАЕМ от volley_evro — не се преписва. Ако някой
# ден оттам изчезне, тук се вижда веднага, вместо да се клонира трети вариант
# на същата карта и трите да се разминават тихо.
try:
    import volley_evro as _VE
except Exception:                                            # noqa: BLE001
    _VE = None

# Пазарът „(Points)" на Pinnacle е ОБЩО ТОЧКИ, не победител в мача. Има
# същите две имена и същия номер на лига — тоест се лепи за нашата карта като
# че е тя. Публикувана цена от него значи число за съвсем друг въпрос.
TOCHKI = "(points)"

# Еталонът за „жив ли е изворът". Футболът на Pinnacle не пада под стотици
# мача — измерено днес: matchupCount 393 за football (амер.) и 1007 за soccer.
ETALON = "football"


def _kanon(ime):
    """Име -> същина. Само обвивка над volley_evro.kanon."""
    if _VE is None:
        return ""
    try:
        return _VE.kanon(ime)
    except Exception:                                        # noqa: BLE001
        return ""


def _pol(*teksove):
    """Пол от текстове: 'm', 'w' или None при спор/липса."""
    if _VE is None:
        return None
    try:
        return _VE.kanon_pol(*teksove)
    except Exception:                                        # noqa: BLE001
        return None


def izvor_zhiv(broi_volei, broi_etalon):
    """Може ли да се вярва на нулата.

    Нула волейбол + нула еталон  -> изворът е запушен, НЕ е отговор.
    Нула волейбол + жив еталон   -> честна нула, днес няма пазар.

    Мерено 25.08.2026 върху Bovada: HTTP 200 и празен списък за ВСИЧКИ
    спортове, включително футбол — точно случаят, който тази проверка лови.
    """
    try:
        v = int(broi_volei)
        e = int(broi_etalon)
    except (TypeError, ValueError):
        return False
    if v > 0:
        return True
    return e > 0


def index(mach, cen):
    """{същина_дом, същина_гост: [запис, ...]} от суровите две картинки.

    `mach` е {номер: (дом, гост, лига, старт)} — точно каквото връща
    pinnacle.machove. `cen` е {номер: (цена_дом, цена_гост, равен)} — точно
    каквото връща pinnacle.pazari. Подават се ОТВЪН, за да може цялата
    самопроверка да мине без нито една заявка.
    """
    out = {}
    for nomer, red in (mach or {}).items():
        if not isinstance(red, (list, tuple)) or len(red) < 2:
            continue
        dom, gost = red[0], red[1]
        liga = red[2] if len(red) > 2 else ""
        start = red[3] if len(red) > 3 else ""
        # пазарът на точки се изхвърля ТУК, преди да е стигнал до карта
        if TOCHKI in str(dom).lower() or TOCHKI in str(gost).lower():
            continue
        kd, kg = _kanon(dom), _kanon(gost)
        if not kd or not kg or kd == kg:
            continue
        c = (cen or {}).get(nomer)
        if not c:
            continue
        cd = c[0] if len(c) > 0 else None
        cg = c[1] if len(c) > 1 else None
        if cd is None and cg is None:
            continue
        out.setdefault((kd, kg), []).append(
            {"nomer": str(nomer), "dom": cd, "gost": cg,
             "liga": str(liga or ""), "start": str(start or ""),
             "pol": _pol(liga)})
    return out


def _index_ili_vzemi(ind, mach, cen):
    """Индексът: подаденият, или взет от Pinnacle, ако не е подаден.

    🔴 КАПАНЪТ, КОЙТО ЗАТВАРЯ (25.08.2026 вечерта). Дотук и `cena`, и
    `pokritie` пишеха `index(mach or {}, cen or {})` — с ПРАЗНИ речници,
    когато никой не им подаде данни. Тоест естественото извикване
    `cena("Унгария", "Германия")` връщаше None ВИНАГИ, тихо, и изглеждаше
    точно като „няма пазар".

    Проверено живо: и петте проби мълчаха така, докато СЪЩИТЕ данни, подадени
    на ръка, даваха 6 от 7 цени. Функцията беше жива само за този, който вече
    знае как се вика.

    Това е шаблонът, срещу който самият този файл предупреждава в заглавието
    си: „нула, защото няма" и „нула, защото не съм питал" изглеждат еднакво
    отвън. Затова: няма ли подадени данни, ВЗИМАМЕ ГИ.
    pinnacle.machove/pazari са кеширани — второто викане е безплатно.
    """
    if ind is not None:
        return ind
    if mach is None and cen is None:
        try:
            import pinnacle as _PIN
            mach, cen = _PIN.machove("volleyball"), _PIN.pazari("volleyball")
        except Exception:                                    # noqa: BLE001
            mach, cen = {}, {}
    return index(mach or {}, cen or {})


def cena(dom, gost, liga=None, ind=None, mach=None, cen=None):
    """Цената за НАШАТА карта, или None.

    Връща {'dom','gost','liga','start','obarnat'}.

    🔴 ОБРЪЩАНЕТО. Домакинът при тях НЕ е задължително нашият домакин.
    Намери ли се двойката наопаки, цените се РАЗМЕНЯТ — иначе на картата
    „Германия" застава цената на Унгария. Полето 'obarnat' го казва открито.

    🔴 ПОЛЪТ. EuroVolley върви едновременно при мъже и жени и двете „Италия"
    се сплескват до една същина. Има ли две съвпадения и полът не ги разделя —
    МЪЛЧИ. По-добре без цена, отколкото цената на другия мач.
    """
    ind = _index_ili_vzemi(ind, mach, cen)
    kd, kg = _kanon(dom), _kanon(gost)
    if not kd or not kg:
        return None
    obarnat = False
    redove = ind.get((kd, kg))
    if not redove:
        redove = ind.get((kg, kd))
        obarnat = bool(redove)
    if not redove:
        return None
    if len(redove) > 1:
        nash = _pol(liga) if liga else None
        if nash:
            stesneni = [r for r in redove if r.get("pol") == nash]
            if len(stesneni) == 1:
                redove = stesneni
        if len(redove) > 1:
            return None                       # спор, който не се разрешава
    r = redove[0]
    cd, cg = r["dom"], r["gost"]
    if obarnat:
        cd, cg = cg, cd
    return {"dom": cd, "gost": cg, "liga": r["liga"],
            "start": r["start"], "obarnat": obarnat}


def pokritie(karti, ind=None, mach=None, cen=None):
    """(намерени, общо, [липсващите лиги]) за списък карти от дневника."""
    ind = _index_ili_vzemi(ind, mach, cen)
    nam = 0
    lipsa = []
    for k in (karti or []):
        if not isinstance(k, dict):
            continue
        c = cena(k.get("home"), k.get("away"), k.get("league"), ind=ind)
        if c and (c["dom"] is not None or c["gost"] is not None):
            nam += 1
        else:
            lipsa.append(str(k.get("league") or ""))
    return nam, len([k for k in (karti or []) if isinstance(k, dict)]), lipsa


# ═══════════════════════════════ САМОПРОВЕРКА
#
# Всичко тук е ПОВЕДЕНЧЕСКО: подхвърлят се данни и се гледа изходът. Нито
# една проверка не търси текст във файла — иглата, застанала в съседния
# коментар, минава и върху счупен файл.

_M = {
    "1": ("Hungary", "Germany", "European - Championship Women", "2026-08-25T13:00:00Z"),
    "2": ("Hungary (Points)", "Germany (Points)", "European - Championship Women", "2026-08-25T13:00:00Z"),
    "3": ("Sweden", "Croatia", "European - Championship Women", "2026-08-25T17:00:00Z"),
    "4": ("France", "Italy", "European - Championship Women", "2026-08-26T10:00:00Z"),
    "5": ("France", "Italy", "European - Championship Men", "2026-08-26T18:00:00Z"),
    "6": ("Bulgaria", "Czech Republic", "International Friendlies", "2026-08-25T16:00:00Z"),
}
_C = {
    "1": (8.33, 1.08, None), "2": (1.90, 1.90, None), "3": (1.31, 3.53, None),
    "4": (2.00, 1.80, None), "5": (1.50, 2.60, None), "6": (1.20, 4.50, None),
}


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # ═══════ ЕСТЕСТВЕНОТО ИЗВИКВАНЕ (добавено 25.08.2026 вечерта) ═══════
    # 🔴 ЗАЩО Е ТУК. Всичките 45 проверки под този ред подаваха данните на
    # ръка — и минаваха. А `cena("Унгария", "Германия")` БЕЗ данни връщаше
    # None ВИНАГИ, защото индексът се строеше от празни речници. Функцията
    # беше жива само за този, който вече знае как се вика; за всеки друг
    # изглеждаше като „няма пазар".
    # Проверява се ПЪТЯТ, не само сметката. Мрежата е подменена, не пипана.
    _star = sys.modules.get("pinnacle")

    class _FalshivPinnacle(object):
        vikan = [0]

        @staticmethod
        def machove(sport_key):
            _FalshivPinnacle.vikan[0] += 1
            return {"7": ("Hungary", "Germany", "European - Championship Women",
                          "2026-08-25T13:00:00Z")}

        @staticmethod
        def pazari(sport_key):
            return {"7": (8.33, 1.08, None)}

    try:
        sys.modules["pinnacle"] = _FalshivPinnacle
        _bez = cena("Унгария", "Германия")
        check("естественото извикване НЕ мълчи", _bez is not None)
        check("и връща истинската цена",
              bool(_bez) and _bez.get("dom") == 8.33 and _bez.get("gost") == 1.08)
        check("източникът наистина е питан", _FalshivPinnacle.vikan[0] > 0)
        # Подаденият индекс пак бие взетия — иначе тестовете отдолу лъжат.
        check("подаденият индекс се уважава",
              cena("Унгария", "Германия", ind={}) is None)
    finally:
        if _star is None:
            sys.modules.pop("pinnacle", None)
        else:
            sys.modules["pinnacle"] = _star

    check("volley_evro е налице", _VE is not None)

    # --- заетата нормализация наистина работи (ако падне, всичко пада)
    check("кирилица->латиница: Румъния", _kanon("Румъния") == "romania")
    check("кирилица->латиница: Унгария", _kanon("Унгария") == "hungary")
    check("Чехия и Czech Republic са едно", _kanon("Чехия") == _kanon("Czech Republic"))
    check("Turkiye и Turkey са едно", _kanon("Turkiye") == _kanon("Turkey"))
    check("САЩ е usa", _kanon("САЩ") == "usa")
    check("празно име дава празна същина", _kanon("") == "" and _kanon(None) == "")

    ind = index(_M, _C)

    # --- сърцевината: кирилицата вече намира цена
    c = cena("Унгария", "Германия", "CEV EuroVolley 2026 | Women", ind=ind)
    check("кирилица НАМИРА цена", c is not None)
    check("кирилица дава ВЯРНАТА цена дом", c and c["dom"] == 8.33)
    check("кирилица дава ВЯРНАТА цена гост", c and c["gost"] == 1.08)
    check("кирилицата не е обърната", c and c["obarnat"] is False)

    c2 = cena("Hungary", "Germany", "CEV EuroVolley 2026 | Women", ind=ind)
    check("латиница дава същото", c2 and c2["dom"] == 8.33 and c2["gost"] == 1.08)

    # --- обръщането: страните им НЕ са нашите страни
    o = cena("Германия", "Унгария", "CEV EuroVolley 2026 | Women", ind=ind)
    check("обърнатата двойка се намира", o is not None)
    check("обърнатата се обявява", o and o["obarnat"] is True)
    check("обърнатата РАЗМЕНЯ дома", o and o["dom"] == 1.08)
    check("обърнатата РАЗМЕНЯ госта", o and o["gost"] == 8.33)

    # --- пазарът на точки не бива да става цена на мач
    check("точките не влизат в указателя", ("hungarypoints", "germanypoints") not in ind)
    check("точките не се намират като мач",
          cena("Hungary (Points)", "Germany (Points)", None, ind=ind) is None)
    # 🔴 ТАЗИ ПРОВЕРКА БЕШЕ СГРЕШЕНА ОТ МЕН (25.08.2026). Написах „5 ключа",
    # защото извадих само точките от 6-те записа. Но Франция-Италия при мъже и
    # при жени падат в ЕДИН ключ — тоест 4 ключа с 5 записа. Кодът беше прав,
    # иглата ми — не. Затова сега се броят и двете числа поотделно.
    check("ключовете са 4 (Франция-Италия е ЕДИН ключ)", len(ind) == 4)
    check("записите са 5 (6 минус точките)",
          sum(len(v) for v in ind.values()) == 5)
    check("Франция-Италия държи ДВА записа", len(ind[("france", "italy")]) == 2)
    check("цената на точките (1.90) не изтича никъде",
          all(r["dom"] != 1.90 for rr in ind.values() for r in rr))

    # --- полът: две Франции-Италии едновременно
    check("без пол при спор се МЪЛЧИ", cena("Франция", "Италия", None, ind=ind) is None)
    zh = cena("Франция", "Италия", "CEV EuroVolley 2026 | Women", ind=ind)
    check("женската намира женската цена", zh and zh["dom"] == 2.00)
    mzh = cena("Франция", "Италия", "CEV EuroVolley 2026 | Men", ind=ind)
    check("мъжката намира мъжката цена", mzh and mzh["dom"] == 1.50)
    check("женската НЕ взима мъжката цена", zh and zh["dom"] != 1.50)

    # --- честни откази
    check("непозната двойка дава None", cena("Перу", "Чили", None, ind=ind) is None)
    check("празни имена дават None", cena("", "", None, ind=ind) is None)
    check("None имена не гърмят", cena(None, None, None, ind=ind) is None)
    check("един и същ отбор от двете страни не влиза",
          cena("Швеция", "Швеция", None, ind=ind) is None)

    # --- изворът, който лъже с нула
    check("нула волейбол + нула еталон = МЪРТЪВ извор", izvor_zhiv(0, 0) is False)
    check("нула волейбол + жив еталон = честна нула", izvor_zhiv(0, 393) is True)
    check("жив волейбол = жив извор", izvor_zhiv(21, 393) is True)
    check("боклук се брои за мъртъв", izvor_zhiv(None, None) is False)
    check("текст не гърми", izvor_zhiv("абв", "5") is False)

    # --- устойчивост на указателя
    check("празни данни дават празен указател", index({}, {}) == {})
    check("мач без цена не влиза", index(_M, {}) == {})
    check("счупен ред не гърми", index({"9": ("само едно",)}, {"9": (1.5, 2.5, None)}) == {})
    check("None данни не гърмят", index(None, None) == {})

    # --- покритие върху карти във формата на ДНЕВНИКА
    karti = [
        {"home": "Унгария", "away": "Германия", "league": "CEV EuroVolley 2026 | Women"},
        {"home": "Швеция", "away": "Хърватия", "league": "CEV EuroVolley 2026 | Women"},
        {"home": "Доминиканска република", "away": "САЩ",
         "league": "NORCECA Women Continental Championship 2026"},
    ]
    n, obsht, lipsa = pokritie(karti, ind=ind)
    check("покритието брои намерените", n == 2)
    check("покритието брои общо", obsht == 3)
    check("покритието казва КОЯ лига липсва",
          len(lipsa) == 1 and "NORCECA" in lipsa[0])
    check("празен списък не гърми", pokritie([], ind=ind) == (0, 0, []))
    check("боклук в списъка не гърми", pokritie([None, 5], ind=ind)[1] == 0)

    check("броят проверки е поне 35", ok >= 35)

    print("САМОПРОВЕРКА НА PIN_VOLEI: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


def zhivo():
    """Истинско питане — за очи, не за автомат."""
    import json
    import pinnacle as P

    mv = P.machove("volleyball")
    cv = P.pazari("volleyball")
    me = P.machove(ETALON)
    print("волейбол: %d мача, %d с цена | еталон %s: %d мача"
          % (len(mv), len(cv), ETALON, len(me)))
    if not izvor_zhiv(len(mv), len(me)):
        print("🔴 ИЗВОРЪТ Е ЗАПУШЕН — нулата не е отговор, картите се пропускат")
        return 1
    ind = index(mv, cv)
    print("указател: %d двойки (пазарът на точки е изхвърлен)" % len(ind))

    try:
        with open("predict_log.json", encoding="utf-8") as f:
            log = json.load(f)
    except Exception as e:                                   # noqa: BLE001
        print("дневникът не се чете: %s" % e)
        return 0
    karti = [k for k in log if isinstance(k, dict) and k.get("bucket") == "volleyball"]
    dni = sorted({k.get("day") for k in karti})[-2:]
    posl = [k for k in karti if k.get("day") in dni]
    for k in posl:
        c = cena(k.get("home"), k.get("away"), k.get("league"), ind=ind)
        zn = "✅" if c else "❌"
        opis = ("%s / %s%s" % (c["dom"], c["gost"], " (обърнат)" if c["obarnat"] else "")) if c else str(k.get("league"))[:38]
        print("  %s %-24s vs %-24s %s" % (zn, str(k.get("home"))[:24], str(k.get("away"))[:24], opis))
    n, obsht, _l = pokritie(posl, ind=ind)
    print("ПОКРИТИЕ за %s: %d от %d" % (", ".join(dni), n, obsht))
    # 🔴 НУЛА ТУК НЕ ЗНАЧИ СЧУПЕНО. Местният predict_log.json изостава от
    # живия (мерено 25.08.2026: местният свършва на 12.08, живият — на 26.08).
    # Старите дни са почти изцяло FIVB Girls' U17 — турнир, за който пазар
    # НЕ СЪЩЕСТВУВА при никой букмейкър. Затова се казва открито срещу какво
    # е мерено, вместо числото да се чете като присъда за модула.
    if n == 0 and obsht:
        print("   ⚠️  нула, но дневникът тук свършва на %s — виж дали дните не са"
              " стари (U17 няма пазар по устройство)" % (dni[-1] if dni else "?"))
    print("заявки общо: %d" % P.broi_zayavki())
    return 0


if __name__ == "__main__":
    if "--zhivo" in sys.argv:
        sys.exit(zhivo())
    sys.exit(selftest())
