# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ЕЛЕКТРОННИТЕ СПОРТОВЕ 🎮

Един въпрос: може ли нов спорт да влезе в бота С ЦЕНА ОТ ПЪРВИЯ ДЕН?

═══════════════════════════════════════════════════════════════════════════
КАКВО Е ИЗМЕРЕНО ЖИВО (25.08.2026, 16:07 UTC)
═══════════════════════════════════════════════════════════════════════════

    /sports                        -> id 12 „E Sports", matchupCount 47
    /sports/12/matchups            -> 177 записа, от тях 37 СА МАЧ
                                      (140 носят parentId — спешъли Да/Не)
    /sports/12/markets/straight    -> 982 пазара; moneyline период 0 = 78,
                                      от които 34 са за наш мач
    Игрите: CS2 21 мача · League of Legends 13 · Valorant 3
    Хоризонт: от днес 14:58 до 27.08 16:30 — тоест 2 дни напред

🔴 34 ОТ 34. Тримата без цена са ТОЧНО тримата, които вече са започнали
(14:58, 15:14, 15:15 UTC срещу „сега" 16:07). Незапочнали без цена: НУЛА.
Тоест покритието на цената за незапочнал мач е 34 от 34 — число, каквото
нито волейболът (10%), нито тенисът на маса (0%) някога са имали.

🔴 И ЕДНО СЛЕДСТВИЕ, КОЕТО НЕ Е ОЧЕВИДНО: витрината им ЗАДЪРЖА започналите
мачове (в pinnacle.py пише, че ги маха в мига на старта — за електронните
спортове това НЕ е вярно, измерено току-що). Значи филтърът по час е
ЗАДЪЛЖИТЕЛЕН тук, а не украса: без него ботът щеше да пуска карти за мачове,
които вече текат — и точно те щяха да са без цена.

Маржът им: медиана 1.0803 на 34 мача (мин 1.0355, макс 1.1686). Тоест
суровото 1/цена надува с 8.0%: цена 1.18 се чете като 84.7%, а честното
число е 81.1%. По-широко от футбола (7.4%) — електронните спортове са
по-млад пазар. Затова маржът СЕ МАХА, преди числото да влезе в дневника.

═══════════════════════════════════════════════════════════════════════════
🔴 ЗАЩО ТОЗИ ФАЙЛ НЕ ВИКА pinnacle.ceni_za, А ИМА СОБСТВЕНО СЪВПАДАНЕ
═══════════════════════════════════════════════════════════════════════════

`pinnacle.nameri` е писан за ТЕНИСИСТИ: сравнява по ФАМИЛИЯ (последната дума)
и накрая по ПОДНИЗ в двете посоки. И двете правила се чупят тук, измерено:

    ФАМИЛИЯ:  „paiN Academy" -> „academy"
              „ex-MIBR Academy" -> „academy"      ← две различни организации
              „Unicorns of Love Sexy Edition" -> „edition"

    ПОДНИЗ:   pinnacle.nameri("esports", "paiN", "Peladona")
              -> 1634682547 = „paiN Academy vs Peladona"      🔴 ГРЕШНИЯТ МАЧ

Второто е пуснато живо днес и това е ЦЕНАТА НА ГРЕШКАТА: главният състав paiN
играе днес срещу FURIA на 5.05, а академията му играе срещу Peladona на 1.20.
Тоест картата щеше да носи цена, различна ЧЕТИРИ ПЪТИ от истинската — и
нищо в дневника нямаше да го покаже, защото цена ИМА и мачът „съвпада".

Затова тук: НИКАКЪВ ПОДНИЗ и НИКАКВА ФАМИЛИЯ. Сравнява се цялото име,
сведено до същина, плюс шепа ИЗМЕРЕНИ псевдоними. Спор ли има — МЪЛЧИ СЕ.

Обратната половина на същия проблем (измерена живо срещу техните имена):

    NAVI          vs M80             -> pinnacle: None   ← пропуснат мач
    mousesports   vs 9z              -> pinnacle: None   ← пропуснат мач
    PRX           vs Nongshim...     -> pinnacle: None   ← пропуснат мач
    G2 Esports    vs Aurora          -> pinnacle: намира (подниз)
    Team Vitality vs Inner Circle    -> pinnacle: намира (подниз)

Един отбор се пише по три начина: „NAVI", „Na'Vi", „Natus Vincere". Тук
шумовите думи („Team", „Esports", „Gaming", „Club") се махат КАТО ЦЕЛИ ДУМИ,
а трите истински съкращения имат карта. „Academy", „Juniors", „ex-" НЕ СА
шум — те са ДРУГ ОТБОР и се пазят непокътнати.

═══════════════════════════════════════════════════════════════════════════
🔴 ТРИТЕ ИГРИ СА ТРИ СПОРТА
═══════════════════════════════════════════════════════════════════════════

Лигата им се пише „ИГРА - Турнир": „CS2 - BLAST Open Porto",
„League of Legends - LCK", „Valorant - Champions Tour: Pacific".

Че това не е козметика, го доказва един ред от днешните данни:

    9z vs Golden Lions      League of Legends - LRS        1.42 / 2.66
    MOUZ vs 9z              CS2 - BLAST Open Porto         1.45 / 2.77

ЕДНА организация, ДВА различни отбора, ДВЕ различни игри, в един и същи ден.
Смесят ли се, „процентът победи на 9z" е сбор от две несвързани неща.
Същото и с „paiN Academy": играе CS2 срещу Peladona и LoL срещу RMD Gaming.

Затова всеки запис носи `igra` и всяко търсене на цена може да се стесни по
нея. Непозната игра НЕ се сплесква тихо в купчината: `igra` остава празна,
лигата ѝ влиза в `POSLEDNO["ligi_bez_igra"]` и се вижда.

═══════════════════════════════════════════════════════════════════════════
🔴 РАЗЛИКАТА МЕЖДУ „НЯМА" И „НЕ МОЖАХ ДА ПИТАМ"
═══════════════════════════════════════════════════════════════════════════

`pinnacle.machove` връща `{}` и когато спортът е празен, и когато заявката е
паднала — отвън двете изглеждат еднакво. Затова тук се пита и ВИТРИНАТА
(/sports), която обявява СВОЙ брой:

    витрината мълчи (отказ)          -> NEPITAN, не празен списък
    витрината казва 47, а списък 0   -> NEPITAN (разминаване = отказ)
    витрината казва 0 и списък 0     -> [] — честна нула, спортът спи

NEPITAN е ОБЕКТ, не None и не []: този, който го прочете като „чисто", ще
гръмне, вместо да излъже. Точно това уби предишния пазач (виж pazach.py).

  python esport.py --selftest   — проверките, БЕЗ нито една заявка
  python esport.py --zhivo      — истинско питане, за очи
"""
import calendar
import sys
import time

try:
    import pinnacle as _PIN
except Exception:                                            # noqa: BLE001
    _PIN = None

# Техният номер за електронните спортове (измерено 25.08.2026 през /sports).
# `pinnacle.SPORT_ID` няма такъв ключ — добавя се ПРИ ПУСКАНЕ, не се пипа
# чужд файл. Същият похват вече се ползва от sezon.py за хокея.
PIN_ID = 12

# Кошът в предсказателя (и името на стаята).
KOSH = "esports"

# 🔴 КЛЮЧЪТ ПРИ ТЯХ НАРОЧНО НЕ СЕ КАЗВА КАКТО КОША. Прочетено в predictor.py
# (dobavi_pazar, ред ~5312): `if _b in PIN.SPORT_ID and _d and _g:` — тоест
# ЗА ВСЕКИ кош, който присъства в pinnacle.SPORT_ID, предсказателят вика
# `PIN.ceni_za(кош, ...)` ПРЕДИ да стигне до модула на спорта. Регистрираме
# ли се под името „esports", целият този файл става недостижим, а цената ще
# идва от съвпадането по ПОДНИЗ — същото, което днес даде на „paiN" мача на
# „paiN Academy" (5.05 срещу 1.20).
# Затова: при тях сме „esports_pin", в предсказателя — „esports". Двете имена
# НЕ бива да се изравняват.
PIN_KLYUCH = "esports_pin"

# Сентинел: „не можах да питам". НЕ е None, НЕ е [], НЕ е 0 — за да няма как
# да бъде прочетен като отговор.
NEPITAN = object()

# Докъде напред приемаме мач за истински насрочен.
# 🔴 ЧЕСТНО: днес НЯМА нито един запис над 2 дни напред, тоест този праг НЕ Е
# лек за измерена болест — предпазител е. Слага се, защото при БОКСА (id 6) в
# същата секунда стоят „Mike Tyson vs Floyd Mayweather" и „Pacquiao vs
# Mayweather" — спекулативни пазари без дата на мач. Появи ли се такъв и тук,
# по-добре да падне в ситото, отколкото да стане карта.
HORIZONT_DNI = 14

# Шумови думи в имената на отборите. Махат се САМО като ЦЕЛИ ДУМИ и НИКОГА
# последната останала („Team" сам по себе си си остава „team").
#
# 🔴 КОЕ НЕ Е ТУК И ЗАЩО: „academy", „juniors", „youth", „ex" и „b". Те
# изглеждат като опашки, но са ДРУГ ОТБОР. Измерено днес: paiN (главен) играе
# на 5.05, paiN Academy — на 1.20, в един и същи ден. Махнем ли „academy",
# двата стават един и картата взима цената на грешния.
SHUM = {"esports", "esport", "esportsclub", "gaming", "team", "club",
        "org", "gg", "the", "of"}

# Съкращения, които НЯМА как да се получат с махане на шумова дума.
# Всяко е ПУСНАТО срещу техния днешен отговор: лявото не намираше нищо в
# pinnacle, дясното е име, което наистина стои във витрината им днес.
#
#   navi        -> „Natus Vincere"   (pinnacle: None; с картата: намира)
#   mousesports -> „MOUZ"            (pinnacle: None; с картата: намира)
#   prx         -> „Paper Rex"       (pinnacle: None; с картата: намира)
#
# 🔴 СПИСЪКЪТ Е КЪС НАРОЧНО. Измислен псевдоним е ПО-ЛОШ от липсващия:
# липсващият дава мълчание (виждаме „няма цена"), измисленият дава ЧУЖДА
# ЦЕНА, която изглежда наред. Ново име влиза тук само след като е видяно в
# техния отговор — не по спомен как се съкращава отборът.
PSEVDONIMI = {
    "navi": "natusvincere",
    "mousesports": "mouz",
    "prx": "paperrex",
}

# Игрите: техният префикс (сведен до букви и цифри) -> нашият ключ.
# Само измереното днес + „csgo", защото това е СЪЩАТА игра под старото си име
# и същата лига я носи двете.
IGRI = {
    "cs2": "cs2",
    "csgo": "cs2",
    "counterstrike2": "cs2",
    "counterstrike": "cs2",
    "leagueoflegends": "lol",
    "lol": "lol",
    "valorant": "valorant",
}

# Човешките имена на игрите — за карта и за стая.
IGRA_IME = {"cs2": "CS2", "lol": "League of Legends", "valorant": "Valorant"}

# Черната кутия: последното пускане на fixtures(). Отвън не се вижда ЗАЩО
# един спорт мълчи — затова числата се пазят, вместо да изчезнат.
POSLEDNO = {}

_vit_kesh = []


# ─────────────────────────────────────────────────────────── ВРЕМЕ
def _ts(iso):
    """„2026-08-26T14:00:00Z" -> секунди UTC. None при боклук.

    Ръчно, а не през fromisoformat: „Z" не се приема от по-старите Python,
    а calendar.timegm е UTC без нито едно допускане за часова зона. (Вече ни
    е ухапвало: TZ=Europe/Sofia върна UTC мълчаливо.)
    """
    s = str(iso or "").strip()
    if not s:
        return None
    s = s.replace("Z", "").split("+")[0].split(".")[0]
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return calendar.timegm(time.strptime(s, f))
        except ValueError:
            pass
    try:
        return calendar.timegm(time.strptime(s[:10], "%Y-%m-%d"))
    except ValueError:
        return None


def _den(iso):
    """Денят („2026-08-26") от техния час. Празно при боклук."""
    s = str(iso or "").strip()
    return s[:10] if len(s) >= 10 and s[4] == "-" and s[7] == "-" else ""


# ─────────────────────────────────────────────────────────── ИМЕНА
def _stegni(s):
    """Име -> само малки букви и цифри. „paiN Academy" -> „painacademy"."""
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def _dumi(s):
    """Думите на името, сведени поотделно. „ex-MIBR Academy" -> [ex, mibr, academy]."""
    tek, out = "", []
    for ch in str(s or "").lower():
        if ch.isalnum():
            tek += ch
        elif tek:
            out.append(tek)
            tek = ""
    if tek:
        out.append(tek)
    return out


def varianti(ime):
    """Всички ключове, под които този отбор може да се срещне. Празен кортеж при боклук.

    Три слоя, от строгото към хлабавото:
      1. цялото име, сведено до същина          („teamvitality")
      2. същото, без ШУМОВИТЕ ДУМИ              („vitality")
      3. псевдоним от измерената карта          („navi" -> „natusvincere")

    🔴 НИКЪДЕ ПОДНИЗ. Точно подниз даде на „paiN" мача на „paiN Academy".
    Ключът е ЦЯЛОТО име; съкращенията са изброени поименно, не отгатнати.
    """
    cyalo = _stegni(ime)
    if not cyalo:
        return ()
    out = [cyalo]
    d = _dumi(ime)
    bez = [w for w in d if w not in SHUM]
    if not bez:                       # само шум („Team", „The Club") — пази се
        bez = d
    slyapo = "".join(bez)
    if slyapo and slyapo not in out:
        out.append(slyapo)
    for k in list(out):
        p = PSEVDONIMI.get(k)
        if p and p not in out:
            out.append(p)
    return tuple(out)


def _obshti(a, b):
    """Имат ли двете имена общ ключ. Основата на съвпадането."""
    va, vb = varianti(a), varianti(b)
    return bool(set(va) & set(vb))


# ─────────────────────────────────────────────────────────── ИГРИ
def igra_ot_liga(liga):
    """„CS2 - BLAST Open Porto" -> („cs2", „BLAST Open Porto").

    Непозната игра или лига без разделител -> („", цялата лига). Празно, а не
    отгатнато: непозната игра трябва да СЕ ВИДИ, не да падне в общата купчина.
    """
    s = str(liga or "").strip()
    if not s:
        return ("", "")
    if " - " in s:
        prefiks, turnir = s.split(" - ", 1)
    else:
        prefiks, turnir = s, ""
    return (IGRI.get(_stegni(prefiks), ""), turnir.strip() or s)


def po_igra(zapisi):
    """{игра: [запис, ...]}. Непознатите отиват под ключ „"."""
    out = {}
    for z in (zapisi or []):
        if isinstance(z, dict):
            out.setdefault(str(z.get("igra") or ""), []).append(z)
    return out


# ─────────────────────────────────────────────────────────── ИЗВОРЪТ
def broy_ot_vitrina(spisak=None):
    """Колко мача обявява ТЯХНАТА витрина за id 12. int или NEPITAN.

    Това е второто мнение, което дели „няма" от „не можах да питам".
    `spisak` се подава от самопроверката — тогава нито една заявка не тръгва.
    """
    if spisak is None:
        if _vit_kesh:
            return _vit_kesh[0]
        if _PIN is None:
            return NEPITAN
        j = getattr(_PIN, "_j", None)
        if j is None:
            return NEPITAN
        try:
            spisak = j("/sports")
        except Exception:                                    # noqa: BLE001
            spisak = None
        if not isinstance(spisak, list) or not spisak:
            return NEPITAN                     # отказ, НЕ „спортът го няма"
        _vit_kesh.append(_broy_v_spisak(spisak))
        return _vit_kesh[0]
    if not isinstance(spisak, list) or not spisak:
        return NEPITAN
    return _broy_v_spisak(spisak)


def _broy_v_spisak(spisak):
    """Броят за id 12 в отговора на /sports. 0, ако спортът изобщо го няма."""
    for s in spisak:
        if isinstance(s, dict) and s.get("id") == PIN_ID:
            try:
                return max(0, int(s.get("matchupCount") or 0))
            except (TypeError, ValueError):
                return 0
    return 0


def _vzemi():
    """(мачове, цени) от живия Pinnacle. (NEPITAN, NEPITAN) при отказ."""
    if _PIN is None:
        return NEPITAN, NEPITAN
    try:
        _PIN.SPORT_ID.setdefault(PIN_KLYUCH, PIN_ID)
        return _PIN.machove(PIN_KLYUCH), _PIN.pazari(PIN_KLYUCH)
    except Exception:                                        # noqa: BLE001
        return NEPITAN, NEPITAN


# ─────────────────────────────────────────────────────────── УКАЗАТЕЛЯТ
def index(mach, cen=None):
    """{(ключ_дом, ключ_гост): [запис, ...]} от суровите две картинки.

    `mach` е {номер: (дом, гост, лига, старт)} — точно каквото връща
    pinnacle.machove. `cen` е {номер: (дом, гост, равен)} — pinnacle.pazari.
    Подават се ОТВЪН, за да мине цялата самопроверка без нито една заявка.

    🔴 ЕДИН МАЧ ВЛИЗА ПОД ВСИЧКИТЕ СИ КЛЮЧОВЕ. „Natus Vincere vs M80" стои и
    под („natusvincere","m80"). Питането с „NAVI" минава през псевдонима и
    удря същия ключ. Така съвпадането е точно, без нито един подниз.

    🔴 ЧУЖДИТЕ КЛЮЧОВЕ НЕ ВЛИЗАТ. pinnacle.pazari дава 37 ключа, но 3 от тях
    са спешъли („Ще спечели ли Vitality поне една карта?") с СВОЙ номер.
    Указателят тръгва от МАЧОВЕТЕ и взима цената по номер — тоест спешълът
    няма как да се залепи за карта.
    """
    out = {}
    for nomer, red in (mach or {}).items():
        if not isinstance(red, (list, tuple)) or len(red) < 2:
            continue
        dom, gost = red[0], red[1]
        liga = red[2] if len(red) > 2 else ""
        start = red[3] if len(red) > 3 else ""
        vd, vg = varianti(dom), varianti(gost)
        if not vd or not vg or set(vd) & set(vg):
            continue                       # един и същ отбор от двете страни
        c = (cen or {}).get(nomer) or (None, None, None)
        igra, turnir = igra_ot_liga(liga)
        zap = {"nomer": str(nomer), "dom": str(dom), "gost": str(gost),
               "cena_dom": c[0] if len(c) > 0 else None,
               "cena_gost": c[1] if len(c) > 1 else None,
               "liga": str(liga or ""), "turnir": turnir, "igra": igra,
               "start": str(start or ""), "start_ts": _ts(start),
               "den": _den(start)}
        for kd in vd:
            for kg in vg:
                out.setdefault((kd, kg), []).append(zap)
    return out


def _index_ili_vzemi(ind, mach, cen):
    """Указателят: подаденият, или взет от Pinnacle, ако не е подаден.

    🔴 КАПАНЪТ, КОЙТО СЕ ЗАТВАРЯ ТУК. Точно вчера в pin_volei.py се хвана
    модул, чиито 45 проверки минаваха, а `cena(a, b)` без данни връщаше None
    ВИНАГИ — защото си строеше указателя от празни речници. Тоест функцията
    беше жива само за този, който вече знае как се вика; за всеки друг
    изглеждаше като „няма пазар".

    Затова: няма ли подадени данни, ВЗИМАМЕ ГИ. pinnacle кешира — второто
    викане е нула нови заявки.
    """
    if ind is not None:
        return ind
    if mach is None and cen is None:
        mach, cen = _vzemi()
        if mach is NEPITAN:
            mach, cen = {}, {}
    return index(mach or {}, cen or {})


def _stesni(redove, igra, den):
    """Свежда спора до един мач. Празно или един елемент = отговор; повече = спор.

    ИГРАТА е СТРОГА: питаш ли за Valorant, а мачът е CS2, това НЕ е твоят мач
    и се връща празно. Точно затова 9z в LoL не може да вземе цената на 9z в
    CS2 — двата отбора носят едно име и играят в един и същи ден.

    ДЕНЯТ е само РАЗТУРВАЧ НА СПОР, не филтър: нашият ден се смята по София, а
    техният час е UTC, и мач в 01:30 сменя датата. Строг ден би изхвърлял
    верни съвпадения заради часова зона.
    """
    if igra:
        redove = [r for r in redove if r.get("igra") == str(igra)]
    if len(redove) <= 1:
        return redove
    if den:
        s = [r for r in redove if r.get("den") == str(den)[:10]]
        if len(s) == 1:
            return s
    return redove


# ─────────────────────────────────────────────────────────── ЦЕНАТА
def cena(dom, gost, igra=None, den=None, ind=None, mach=None, cen=None):
    """Цената за НАШАТА карта, или None.

    Връща {'dom','gost','nomer','obarnat','liga','turnir','igra','start'}.

    🔴 ОБРЪЩАНЕТО. Домакинът при тях не е задължително нашият домакин — в
    електронните спортове „домакин" често не значи нищо. Намери ли се
    двойката наопаки, цените се РАЗМЕНЯТ и полето 'obarnat' го казва открито.
    Измерено: „paiN vs FURIA" дава (5.05, 1.18), а техният ред е обратният.

    🔴 СПОРЪТ МЪЛЧИ. Един и същ ключ с два различни мача се стеснява по ИГРА
    и по ДЕН; не се ли раздели — връща се None. По-добре без цена, отколкото
    цената на другия мач.
    """
    ind = _index_ili_vzemi(ind, mach, cen)
    vd, vg = varianti(dom), varianti(gost)
    if not vd or not vg or set(vd) & set(vg):
        return None
    napred, nazad = {}, {}
    for kd in vd:
        for kg in vg:
            for r in ind.get((kd, kg), []):
                napred[r["nomer"]] = r
            for r in ind.get((kg, kd), []):
                nazad[r["nomer"]] = r
    # Един и същ мач намерен и в двете посоки значи, че имената не се делят —
    # тогава „обърнат ли е" няма отговор и се мълчи.
    dvusmisleni = set(napred) & set(nazad)
    for n in dvusmisleni:
        napred.pop(n, None)
        nazad.pop(n, None)
    redove = [(r, False) for r in napred.values()] + [(r, True) for r in nazad.values()]
    if not redove:
        return None
    stesneni = _stesni([r for r, _o in redove], igra, den)
    if len(stesneni) != 1:
        return None
    izbran = stesneni[0]
    obarnat = [o for r, o in redove if r["nomer"] == izbran["nomer"]][0]
    cd, cg = izbran["cena_dom"], izbran["cena_gost"]
    if cd is None and cg is None:
        return None                        # мачът е тук, но пазарът е свален
    if obarnat:
        cd, cg = cg, cd
    return {"dom": cd, "gost": cg, "nomer": izbran["nomer"], "obarnat": obarnat,
            "liga": izbran["liga"], "turnir": izbran["turnir"],
            "igra": izbran["igra"], "start": izbran["start"]}


def zatvaryashta(nomer, obarnat=False, cen=None):
    """(дом, гост) при ЗАТВАРЯНЕ за вече знаен номер. NEPITAN при отказ.

    ЗАЩО е тук: без затваряща цена няма CLV, а CLV е единствената мярка, която
    дава отговор за два дни вместо за тридесет и пет. Тенисът остана без нея
    цял месец, защото цената идваше, а НОМЕРЪТ се хвърляше. Тук номерът излиза
    навън от първия ден.

    (None, None) значи „мачът вече не е на витрината" — честен отговор, не
    отказ: щом е тръгнал, няма какво да се презаписва.
    """
    if not nomer:
        return (None, None)
    if cen is NEPITAN:
        return NEPITAN
    if cen is None:
        if _PIN is None:
            return NEPITAN
        _mach, cen = _vzemi()
        if cen is NEPITAN:
            return NEPITAN
    c = (cen or {}).get(str(nomer))
    if not c:
        return (None, None)
    cd = c[0] if len(c) > 0 else None
    cg = c[1] if len(c) > 1 else None
    return (cg, cd) if obarnat else (cd, cg)


# ─────────────────────────────────────────────────────────── СРЕЩИТЕ
def fixtures(mach=None, cen=None, vitrina=None, sega=None,
             napred_dni=HORIZONT_DNI, otstap_min=0, samo_igri=None):
    """Предстоящите мачове. Списък записи, или NEPITAN при отказ на извора.

    Всеки запис: nomer, dom, gost, liga, turnir, igra, start, start_ts, den,
    cena_dom, cena_gost.

    🔴 ТРИТЕ ИЗХОДА (и защо третият не е списък):
        витрината мълчи                     -> NEPITAN
        витрината казва N>0, а мачове 0     -> NEPITAN (разминаване = отказ)
        витрината казва 0 и мачове 0        -> [] честна нула
    """
    if vitrina is None:
        vitrina = broy_ot_vitrina()
    if mach is None and cen is None:
        mach, cen = _vzemi()
    if mach is NEPITAN or vitrina is NEPITAN:
        POSLEDNO.clear()
        POSLEDNO.update({"izhod": "NEPITAN", "prichina": "изворът отказа"})
        return NEPITAN
    mach = mach or {}
    if not mach:
        try:
            obyaveni = int(vitrina)
        except (TypeError, ValueError):
            obyaveni = 0
        POSLEDNO.clear()
        if obyaveni > 0:
            POSLEDNO.update({"izhod": "NEPITAN", "vitrina": obyaveni,
                             "prichina": "витрината обявява мачове, списъкът е празен"})
            return NEPITAN
        POSLEDNO.update({"izhod": "празно", "vitrina": 0, "surovi": 0,
                         "prichina": "честна нула — спортът спи"})
        return []

    if sega is None:
        sega = time.time()
    prag_dolu = float(sega) + float(otstap_min) * 60.0
    prag_gore = float(sega) + float(napred_dni) * 86400.0
    igri_iskani = set(samo_igri) if samo_igri else None

    surovi = zapochnali = daleche = bez_chas = izhvurleni_igri = 0
    ligi_bez_igra, out = [], []
    vidyani = set()
    for nomer, red in mach.items():
        if not isinstance(red, (list, tuple)) or len(red) < 2:
            continue
        surovi += 1
        dom, gost = red[0], red[1]
        liga = red[2] if len(red) > 2 else ""
        start = red[3] if len(red) > 3 else ""
        vd, vg = varianti(dom), varianti(gost)
        if not vd or not vg or set(vd) & set(vg):
            continue
        ts = _ts(start)
        if ts is None:
            bez_chas += 1
            continue
        if ts <= prag_dolu:
            zapochnali += 1
            continue
        if ts > prag_gore:
            daleche += 1
            continue
        igra, turnir = igra_ot_liga(liga)
        if not igra and str(liga or "") not in ligi_bez_igra:
            ligi_bez_igra.append(str(liga or ""))
        if igri_iskani is not None and igra not in igri_iskani:
            izhvurleni_igri += 1
            continue
        c = (cen or {}).get(nomer) or (None, None, None)
        out.append({"nomer": str(nomer), "dom": str(dom), "gost": str(gost),
                    "liga": str(liga or ""), "turnir": turnir, "igra": igra,
                    "start": str(start or ""), "start_ts": ts, "den": _den(start),
                    "cena_dom": c[0] if len(c) > 0 else None,
                    "cena_gost": c[1] if len(c) > 1 else None})
        vidyani.add(str(nomer))
    out.sort(key=lambda z: (z["start_ts"], z["nomer"]))
    POSLEDNO.clear()
    POSLEDNO.update({"izhod": "списък", "vitrina": vitrina, "surovi": surovi,
                     "suredi": len(out), "zapochnali": zapochnali,
                     "daleche": daleche, "bez_chas": bez_chas,
                     "chuzhda_igra": izhvurleni_igri,
                     "ligi_bez_igra": ligi_bez_igra,
                     "s_cena": len([z for z in out if z["cena_dom"] or z["cena_gost"]])})
    return out


# ═══════════════════════════════ САМОПРОВЕРКА
#
# Всичко е ПОВЕДЕНЧЕСКО: подхвърлят се данни и се гледа изходът. Нито една
# проверка не търси текст във файла — игла, застанала в съседния коментар,
# минава и върху счупен файл.
#
# 🔴 ДАННИТЕ СА ИСТИНСКИ. Долният отрязък е СВАЛЕН ЖИВО на 25.08.2026 в 16:07
# UTC от /sports/12/matchups и /markets/straight: истински номера, истински
# имена, истински лиги, истински цени. Точно затова проверките за имената
# значат нещо — те се бият с това, което ТЕ наистина пишат, а не с това,
# което аз си представям, че пишат.
_M = {
    "1634409848": ("Natus Vincere", "M80", "CS2 - BLAST Open Porto", "2026-08-26T14:00:00Z"),
    "1634409847": ("MOUZ", "9z", "CS2 - BLAST Open Porto", "2026-08-27T11:30:00Z"),
    "1634409846": ("Aurora", "G2", "CS2 - BLAST Open Porto", "2026-08-26T09:00:00Z"),
    "1634409845": ("Spirit", "DENDELE", "CS2 - BLAST Open Porto", "2026-08-26T11:30:00Z"),
    "1634713321": ("Vitality", "Inner Circle", "CS2 - BLAST Open Porto", "2026-08-27T09:00:00Z"),
    "1634425739": ("FURIA", "paiN", "CS2 - BLAST Open Porto", "2026-08-26T16:30:00Z"),
    "1634682547": ("paiN Academy", "Peladona", "CS2 - CCT South America Series", "2026-08-25T16:28:14Z"),
    "1634697982": ("RMD Gaming", "paiN Academy", "League of Legends - Circuito Desafiante", "2026-08-25T20:00:00Z"),
    "1634716520": ("ex-MIBR Academy", "Turma do Pagode", "CS2 - ESL Challenger League South America", "2026-08-25T21:00:00Z"),
    "1634659844": ("Paper Rex", "Nongshim RedForce", "Valorant - Champions Tour: Pacific", "2026-08-26T08:00:00Z"),
    "1634729583": ("KT Rolster", "HANJIN BRION", "League of Legends - LCK", "2026-08-26T08:00:00Z"),
    "1634668455": ("9z", "Golden Lions", "League of Legends - LRS", "2026-08-25T20:00:00Z"),
    "1634665872": ("WLGaming", "The ParadOx Invaders", "League of Legends - HLL", "2026-08-25T15:30:00Z"),
    # 🔴 ТОЗИ Е ЗАПОЧНАЛ и е БЕЗ ЦЕНА — не е измислен, свален е така. Тримата
    # без цена днес бяха точно тримата вече започнали.
    "1634659727": ("LODIS", "devils.one", "League of Legends - Rift Legends", "2026-08-25T15:15:37Z"),
}
_C = {
    "1634409848": (1.19, 4.89, None), "1634409847": (1.45, 2.77, None),
    "1634409846": (1.94, 1.88, None), "1634409845": (1.09, 8.47, None),
    "1634713321": (1.11, 7.24, None), "1634425739": (1.18, 5.05, None),
    "1634682547": (3.85, 1.20, None), "1634697982": (3.72, 1.22, None),
    "1634716520": (5.68, 1.09, None), "1634659844": (1.73, 2.13, None),
    "1634729583": (1.25, 3.84, None), "1634668455": (1.42, 2.66, None),
    "1634665872": (1.07, 5.10, None),
    # 🔴 ЧУЖД КЛЮЧ: спешъл („Ще спечели ли ... поне една карта?") със СВОЙ
    # номер, който не е мач. Днес такива има 3 в отговора. Стои тук нарочно —
    # проверката отдолу пази, че не може да стане цена на карта.
    "1634715186": (1.30, 3.40, None),
}
# Витрината им днес: matchupCount = 47 за id 12.
_V = [{"id": 33, "name": "Tennis", "matchupCount": 330},
      {"id": 12, "name": "E Sports", "matchupCount": 47},
      {"id": 32, "name": "Table Tennis", "matchupCount": 0}]

# „Сега" за проверките: 25.08.2026, 16:07 UTC — часът, в който е свалено.
_SEGA = _ts("2026-08-25T16:07:57Z")


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # ═══════ 1. ЕСТЕСТВЕНОТО ИЗВИКВАНЕ (правилото, което ухапа pin_volei)
    # 45 проверки с подадени на ръка данни минаваха, а голото `cena(a, b)`
    # мълчеше винаги. Тук се изпитва ПЪТЯТ, не само сметката. Мрежата е
    # ПОДМЕНЕНА, не пипана — нито една заявка не тръгва.
    _star = sys.modules.get("pinnacle")
    _star_pin = globals().get("_PIN")

    class _FalshivPinnacle(object):
        SPORT_ID = {}
        vikan = [0]

        @staticmethod
        def machove(kl):
            _FalshivPinnacle.vikan[0] += 1
            return dict(_M)

        @staticmethod
        def pazari(kl):
            return dict(_C)

        @staticmethod
        def _j(pat):
            return list(_V)

    try:
        sys.modules["pinnacle"] = _FalshivPinnacle
        globals()["_PIN"] = _FalshivPinnacle
        del _vit_kesh[:]
        _bez = cena("FURIA", "paiN")
        check("естественото извикване НЕ мълчи", _bez is not None)
        check("и връща истинската цена",
              bool(_bez) and _bez.get("dom") == 1.18 and _bez.get("gost") == 5.05)
        check("номерът излиза навън — без него няма CLV",
              bool(_bez) and _bez.get("nomer") == "1634425739")
        check("източникът наистина е питан", _FalshivPinnacle.vikan[0] > 0)
        check("подаденият указател бие взетия", cena("FURIA", "paiN", ind={}) is None)
        check("ключът се регистрира при тях, не се пипа файлът им",
              _FalshivPinnacle.SPORT_ID.get(PIN_KLYUCH) == PIN_ID)
        # 🔴 И НЕ ПОД ИМЕТО НА КОША. Влезе ли „esports" в тяхната карта,
        # predictor.dobavi_pazar ще вика PIN.ceni_za преди този файл и цената
        # ще идва от съвпадането по подниз — това, което дава на paiN мача на
        # paiN Academy. Тази проверка пази ЦЕЛИЯ модул да остане достижим.
        check("кошът НЕ влиза в тяхната карта (иначе файлът е недостижим)",
              KOSH not in _FalshivPinnacle.SPORT_ID and PIN_KLYUCH != KOSH)
        _fx = fixtures(sega=_SEGA)
        check("fixtures без подадени данни връща списък", isinstance(_fx, list) and _fx)
        _zt = zatvaryashta("1634409848")
        check("затварящата се взима по номер без подадени данни", _zt == (1.19, 4.89))
        del _vit_kesh[:]
    finally:
        if _star is None:
            sys.modules.pop("pinnacle", None)
        else:
            sys.modules["pinnacle"] = _star
        globals()["_PIN"] = _star_pin
        del _vit_kesh[:]

    ind = index(_M, _C)

    # ═══════ 2. ИМЕНАТА: трите изписвания на един отбор
    check("NAVI намира Natus Vincere",
          (cena("NAVI", "M80", ind=ind) or {}).get("dom") == 1.19)
    check("пълното име също", (cena("Natus Vincere", "M80", ind=ind) or {}).get("dom") == 1.19)
    check("Na'Vi също", (cena("Na'Vi", "M80", ind=ind) or {}).get("dom") == 1.19)
    check("G2 Esports намира G2",
          (cena("Aurora", "G2 Esports", ind=ind) or {}).get("gost") == 1.88)
    check("Team Vitality намира Vitality",
          (cena("Team Vitality", "Inner Circle", ind=ind) or {}).get("dom") == 1.11)
    check("Team Spirit намира Spirit",
          (cena("Team Spirit", "DENDELE", ind=ind) or {}).get("dom") == 1.09)
    check("mousesports намира MOUZ",
          (cena("mousesports", "9z Team", ind=ind) or {}).get("dom") == 1.45)
    check("PRX намира Paper Rex",
          (cena("PRX", "Nongshim RedForce", ind=ind) or {}).get("dom") == 1.73)
    check("FURIA Esports намира FURIA",
          (cena("FURIA Esports", "paiN", ind=ind) or {}).get("dom") == 1.18)
    check("името с точка (devils.one) се свежда",
          "devilsone" in varianti("Devils One") and "devilsone" in varianti("devils.one"))
    check("шумът се маха само като ЦЯЛА дума: WLGaming оцелява",
          "wlgaming" in varianti("WLGaming"))
    check("само шум не става празно", varianti("Team") and varianti("Team")[0] == "team")
    check("празно име дава празни варианти", varianti("") == () and varianti(None) == ())

    # ═══════ 3. 🔴 КАПАНЪТ paiN / paiN Academy
    # Това е причината този файл да не вика pinnacle.ceni_za. Пуснато живо:
    # pinnacle.nameri("esports","paiN","Peladona") връща мача на АКАДЕМИЯТА.
    check("подниз БИ съвпаднал — ето защо не се ползва",
          "pain" in _stegni("paiN Academy"))
    check("paiN НЕ взима мача на академията",
          cena("paiN", "Peladona", ind=ind) is None)
    check("академията си взима своята цена",
          (cena("paiN Academy", "Peladona", ind=ind) or {}).get("dom") == 3.85)
    check("главният състав си взима СВОЯТА цена (5.05, не 1.20)",
          (cena("paiN", "FURIA", ind=ind) or {}).get("dom") == 5.05)
    check("Academy НЕ е шумова дума", "pain" not in varianti("paiN Academy"))
    check("ex-MIBR Academy не се слива с академия на друг клуб",
          not _obshti("ex-MIBR Academy", "paiN Academy"))

    # ═══════ 4. ОБРЪЩАНЕТО
    o = cena("paiN", "FURIA", ind=ind)
    check("обърнатата двойка се намира", o is not None)
    check("обърнатата се обявява", o and o["obarnat"] is True)
    check("обърнатата РАЗМЕНЯ цените", o and o["dom"] == 5.05 and o["gost"] == 1.18)
    p = cena("FURIA", "paiN", ind=ind)
    check("правата не е обърната", p and p["obarnat"] is False)

    # ═══════ 5. ИГРИТЕ СА РАЗЛИЧНИ СПОРТОВЕ
    check("CS2 се разпознава", igra_ot_liga("CS2 - BLAST Open Porto") == ("cs2", "BLAST Open Porto"))
    check("LoL се разпознава", igra_ot_liga("League of Legends - LCK") == ("lol", "LCK"))
    check("Valorant се разпознава",
          igra_ot_liga("Valorant - Champions Tour: Pacific")[0] == "valorant")
    check("CS:GO е същата игра като CS2", igra_ot_liga("CS:GO - Nemaka")[0] == "cs2")
    check("непозната игра НЕ се отгатва", igra_ot_liga("Dota 2 - The International")[0] == "")
    check("лига без разделител не гърми", igra_ot_liga("Nyakva liga") == ("", "Nyakva liga"))
    check("празна лига не гърми", igra_ot_liga("") == ("", "") and igra_ot_liga(None) == ("", ""))
    # 9z играе LoL срещу Golden Lions И CS2 срещу MOUZ — един и същи ден.
    c9_lol = cena("9z", "Golden Lions", ind=ind)
    c9_cs = cena("MOUZ", "9z", ind=ind)
    check("9z в LoL дава LoL цената", c9_lol and c9_lol["igra"] == "lol" and c9_lol["dom"] == 1.42)
    check("9z в CS2 дава CS2 цената", c9_cs and c9_cs["igra"] == "cs2" and c9_cs["gost"] == 2.77)
    check("двете НЕ са един и същи мач",
          bool(c9_lol) and bool(c9_cs) and c9_lol["nomer"] != c9_cs["nomer"])
    fx = fixtures(_M, _C, vitrina=47, sega=_SEGA)
    # 🔴 НИТО ЕДНО ГОЛО ВЗИМАНЕ ПО КЛЮЧ ОТТУК НАДОЛУ. Мутация „игрите се
    # сливат" вдигна KeyError вместо да даде червено — тоест проверката
    # ПАДНА, вместо да ОБВИНИ, и целият пакет спря на нея. Затова: първо се
    # проверява формата, после се чете от нея, и то с .get.
    check("подадените данни дават СПИСЪК, не сентинел", isinstance(fx, list))
    if not isinstance(fx, list):
        fx = []
    grupi = po_igra(fx)
    check("разделянето по игра дава три купчини",
          set(grupi) == {"cs2", "lol", "valorant"})
    check("CS2 не се смесва с LoL",
          bool(grupi.get("cs2")) and bool(grupi.get("lol"))
          and all(z["igra"] == "cs2" for z in grupi.get("cs2", []))
          and all(z["igra"] == "lol" for z in grupi.get("lol", [])))
    samo_cs = fixtures(_M, _C, vitrina=47, sega=_SEGA, samo_igri=("cs2",))
    check("филтърът по игра работи",
          isinstance(samo_cs, list) and samo_cs
          and all(z["igra"] == "cs2" for z in samo_cs))
    check("и изхвърленото се брои", POSLEDNO.get("chuzhda_igra", 0) > 0)

    # ═══════ 6. СПОРЪТ МЪЛЧИ, ако не се раздели
    # ИЗМИСЛЕНИ ДАННИ (казано на глас): една и съща двойка два пъти. В
    # днешния им отговор такъв случай няма — затова се прави на ръка, вместо
    # да се твърди, че е измерен.
    dvoen_m = {
        "A1": ("Alfa", "Beta", "CS2 - Proba", "2026-08-26T10:00:00Z"),
        "A2": ("Alfa", "Beta", "League of Legends - Proba", "2026-08-27T10:00:00Z"),
    }
    dvoen_c = {"A1": (1.50, 2.50, None), "A2": (3.00, 1.35, None)}
    di = index(dvoen_m, dvoen_c)
    check("спор без разделител МЪЛЧИ", cena("Alfa", "Beta", ind=di) is None)
    check("спорът се решава по ИГРА",
          (cena("Alfa", "Beta", igra="cs2", ind=di) or {}).get("dom") == 1.50)
    check("спорът се решава по ДЕН",
          (cena("Alfa", "Beta", den="2026-08-27", ind=di) or {}).get("dom") == 3.00)
    check("грешна игра не подава чужда цена",
          cena("Alfa", "Beta", igra="valorant", ind=di) is None)

    # ═══════ 7. ЧЕСТНИ ОТКАЗИ
    check("непозната двойка дава None", cena("Fnatic", "Cloud9", ind=ind) is None)
    check("познат отбор с непознат съперник мълчи", cena("MOUZ", "Cloud9", ind=ind) is None)
    check("празни имена дават None", cena("", "", ind=ind) is None)
    check("None имена не гърмят", cena(None, None, ind=ind) is None)
    check("един и същ отбор от двете страни не влиза",
          cena("MOUZ", "mousesports", ind=ind) is None)
    # 🔴 И ОБРАТНАТА ПОСОКА НА СЪЩИЯ ДВОЕН ПЛАСТ (намерено с мутация): горната
    # проверка минава дори с махнат пазач в `cena`, защото `index` не пуска
    # такъв запис да се роди. Затова тук указателят е ОТРОВЕН НАРОЧНО — с
    # ключ, какъвто index никога не би направил — и се гледа само `cena`.
    _otroven = {("mouz", "mousesports"): [
        {"nomer": "Z9", "dom": "MOUZ", "gost": "mousesports",
         "cena_dom": 1.50, "cena_gost": 2.50, "liga": "CS2 - Proba",
         "turnir": "Proba", "igra": "cs2", "start": "2026-08-26T10:00:00Z",
         "start_ts": _ts("2026-08-26T10:00:00Z"), "den": "2026-08-26"}]}
    check("cena пази СВОЯ пласт срещу еднакъв отбор",
          cena("MOUZ", "mousesports", ind=_otroven) is None)
    # 🔴 ТРЕТИЯТ ПЛАСТ: ЕДИН МАЧ, НАМЕРЕН И В ДВЕТЕ ПОСОКИ. Тогава на въпроса
    # „обърнат ли е" НЯМА отговор — а обърнат мач с грешен флаг значи цената на
    # единия отбор върху името на другия. Мълчи се. (И този пласт се изпитва с
    # отровен указател: истинският index не би родил такъв ключ.)
    _rec = {"nomer": "Z8", "dom": "Alfa", "gost": "Beta", "cena_dom": 1.50,
            "cena_gost": 2.50, "liga": "CS2 - Proba", "turnir": "Proba",
            "igra": "cs2", "start": "2026-08-26T10:00:00Z",
            "start_ts": _ts("2026-08-26T10:00:00Z"), "den": "2026-08-26"}
    check("мач, намерен И в двете посоки, МЪЛЧИ",
          cena("Alfa", "Beta",
               ind={("alfa", "beta"): [_rec], ("beta", "alfa"): [_rec]}) is None)
    check("а само в едната посока — дава цена",
          (cena("Alfa", "Beta", ind={("alfa", "beta"): [_rec]}) or {}).get("dom") == 1.50)
    check("започнал мач без цена дава None",
          cena("LODIS", "devils.one", ind=ind) is None)
    check("чуждият ключ (спешъл) не става цена на карта",
          all(r["nomer"] != "1634715186" for rr in ind.values() for r in rr))
    check("цената на спешъла (1.30) не изтича никъде",
          all(r["cena_dom"] != 1.30 for rr in ind.values() for r in rr))

    # ═══════ 8. УСТОЙЧИВОСТ НА УКАЗАТЕЛЯ
    check("празни данни дават празен указател", index({}, {}) == {})
    check("None данни не гърмят", index(None, None) == {})
    check("счупен ред не гърми", index({"9": ("само едно",)}, {"9": (1.5, 2.5, None)}) == {})
    # 🔴 ДВАТА ПЛАСТА СЕ ИЗПИТВАТ ПООТДЕЛНО (намерено с мутация). И `index`, и
    # `cena` пазят срещу „един и същ отбор от двете страни". Махнах пазача в
    # `index` — нищо не мигна, защото вторият пласт го покри. Пласт, който
    # никой не изпитва сам, е пласт, който утре ще падне тихо.
    check("еднакъв отбор от двете страни не влиза в УКАЗАТЕЛЯ",
          index({"Z1": ("MOUZ", "mousesports", "CS2 - Proba", "2026-08-26T10:00:00Z")},
                {"Z1": (1.5, 2.5, None)}) == {})
    check("и различните отбори влизат (пазачът не яде невинни)",
          len(index({"Z2": ("MOUZ", "9z", "CS2 - Proba", "2026-08-26T10:00:00Z")},
                    {"Z2": (1.5, 2.5, None)})) > 0)
    check("мач без цена ВЛИЗА в указателя (за срещите), но без числа",
          any(r["nomer"] == "1634659727" and r["cena_dom"] is None
              for rr in index(_M, {}).values() for r in rr))

    # ═══════ 9. ВРЕМЕТО
    check("часът им се чете", _ts("2026-08-26T14:00:00Z") == 1787752800)
    check("боклук-час дава None", _ts("абв") is None and _ts("") is None and _ts(None) is None)
    check("денят се вади", _den("2026-08-26T14:00:00Z") == "2026-08-26")
    check("боклук-ден дава празно", _den("хххх") == "")
    imena = [(z["dom"], z["gost"]) for z in fx]
    check("вече започналият НЕ влиза в срещите", ("LODIS", "devils.one") not in imena)
    check("и се брои като започнал", POSLEDNO.get("zapochnali", 0) >= 1)
    check("незапочналите влизат", ("Natus Vincere", "M80") in imena)
    check("записът носи старт и лига",
          all(z["start"] and z["liga"] and z["start_ts"] for z in fx))
    check("подредени са по час", [z["start_ts"] for z in fx] == sorted(z["start_ts"] for z in fx))
    dalech = fixtures(_M, _C, vitrina=47, sega=_SEGA, napred_dni=0)
    check("хоризонтът реже далечните", dalech == [] and POSLEDNO.get("daleche", 0) > 0)
    otstap = fixtures(_M, _C, vitrina=47, sega=_SEGA, otstap_min=60)
    check("отстъпът реже започващите след малко",
          isinstance(otstap, list) and len(otstap) < len(fx)
          and all(z["start_ts"] > _SEGA + 3600 for z in otstap))

    # ═══════ 10. „НЯМА" СРЕЩУ „НЕ МОЖАХ ДА ПИТАМ"
    check("витрината се чете", broy_ot_vitrina(_V) == 47)
    check("спорт, който липсва във витрината, е ЧЕСТНА нула",
          broy_ot_vitrina([{"id": 33, "name": "Tennis", "matchupCount": 5}]) == 0)
    check("празен отговор на витрината е СЕНТИНЕЛ", broy_ot_vitrina([]) is NEPITAN)
    check("боклук от витрината е СЕНТИНЕЛ", broy_ot_vitrina("абв") is NEPITAN)
    check("нула мачове при жива витрина е СЕНТИНЕЛ",
          fixtures({}, {}, vitrina=47, sega=_SEGA) is NEPITAN)
    check("нула мачове при нулева витрина е ЧЕСТНА нула",
          fixtures({}, {}, vitrina=0, sega=_SEGA) == [])
    check("мълчаща витрина е СЕНТИНЕЛ",
          fixtures(_M, _C, vitrina=NEPITAN, sega=_SEGA) is NEPITAN)
    # 🔴 ЖИВИЯТ ПЪТ НА ВИТРИНАТА, не само подаденият (намерено с мутация,
    # 25.08.2026). Всички проверки отгоре подават списъка НА РЪКА и минаваха,
    # докато същата функция по живия си път връщаше 0 вместо сентинел при
    # отказ — тоест „източникът мълчи" щеше да се чете като „спортът спи".
    # Точно шаблонът от pazach.py: изпитваха се сентинелите, подадени на ръка,
    # а НЕ функцията, която ги произвежда. Мрежа пак няма — _PIN е подменен.
    _star_pin2 = globals().get("_PIN")

    class _Otkaz(object):
        SPORT_ID = {}

        @staticmethod
        def _j(pat):
            return None                     # точно каквото прави pinnacle при отказ

        @staticmethod
        def machove(kl):
            return {}

        @staticmethod
        def pazari(kl):
            return {}

    try:
        globals()["_PIN"] = _Otkaz
        del _vit_kesh[:]
        check("ЖИВИЯТ път: отказ на витрината е СЕНТИНЕЛ", broy_ot_vitrina() is NEPITAN)
        check("и срещите след него са СЕНТИНЕЛ, не празен списък",
              fixtures(sega=_SEGA) is NEPITAN)
        # 🔴 ВТОРИЯТ ПАЗАЧ СКРИВАШЕ ПЪРВИЯ (намерено с мутация). Пипнах
        # `_vzemi` да връща `{}, {}` при отказ вместо сентинел — и НИТО ЕДНА
        # проверка не мигна, защото витрината се пита ПРЕДИ него и вече беше
        # обявила отказ. Тоест единият дефект се криеше зад другия пазач.
        # Затова тук витрината се ПОДАВА жива (47) и се гледа само `_vzemi`.
        class _Gramva(object):
            SPORT_ID = {}

            @staticmethod
            def _j(pat):
                return list(_V)

            @staticmethod
            def machove(kl):
                raise RuntimeError("изворът гръмна")

            @staticmethod
            def pazari(kl):
                return {}

        globals()["_PIN"] = _Gramva
        del _vit_kesh[:]
        check("гърмящ извор дава СЕНТИНЕЛ, не празно",
              _vzemi()[0] is NEPITAN and _vzemi()[1] is NEPITAN)
        check("и срещите при ЖИВА витрина пак са СЕНТИНЕЛ",
              fixtures(vitrina=47, sega=_SEGA) is NEPITAN)

        globals()["_PIN"] = None
        del _vit_kesh[:]
        check("липсващ pinnacle е СЕНТИНЕЛ, не нула", broy_ot_vitrina() is NEPITAN)
        check("липсващ pinnacle: _vzemi дава СЕНТИНЕЛ",
              _vzemi()[0] is NEPITAN and _vzemi()[1] is NEPITAN)
        check("липсващ pinnacle не дава празен списък срещи",
              fixtures(sega=_SEGA) is NEPITAN)
        check("липсващ pinnacle при ЖИВА витрина също",
              fixtures(vitrina=47, sega=_SEGA) is NEPITAN)
        check("и затварящата цена при липсващ pinnacle е СЕНТИНЕЛ",
              zatvaryashta("1634409848") is NEPITAN)
    finally:
        globals()["_PIN"] = _star_pin2
        del _vit_kesh[:]

    check("сентинелът НЕ Е празен списък", NEPITAN != [] and NEPITAN is not None)
    check("сентинелът не се чете като нула", bool(NEPITAN) is True)
    check("черната кутия казва ЗАЩО мълчи",
          fixtures({}, {}, vitrina=47, sega=_SEGA) is NEPITAN
          and bool(POSLEDNO.get("prichina")))

    # ═══════ 11. ЗАТВАРЯЩАТА ЦЕНА (CLV)
    check("затварящата по номер", zatvaryashta("1634409848", cen=_C) == (1.19, 4.89))
    check("затварящата се обръща, ако мачът е обърнат",
          zatvaryashta("1634409848", obarnat=True, cen=_C) == (4.89, 1.19))
    check("подаден СЕНТИНЕЛ за цени не се чете като речник",
          zatvaryashta("1634409848", cen=NEPITAN) is NEPITAN)
    check("свален мач дава (None, None), не сентинел",
          zatvaryashta("9999", cen=_C) == (None, None))
    check("празен номер дава (None, None)", zatvaryashta(None, cen=_C) == (None, None))

    # ═══════ 12. ЧЕРНАТА КУТИЯ
    fixtures(_M, _C, vitrina=47, sega=_SEGA)
    check("броят суровите", POSLEDNO.get("surovi") == len(_M))
    check("броят подредените", POSLEDNO.get("suredi") == len(fx))
    check("брои и колко имат цена", POSLEDNO.get("s_cena", 0) >= 11)
    _s_dota = fixtures(dict(_M, X1=("Alfa", "Beta", "Dota 2 - The International",
                                    "2026-08-26T10:00:00Z")), _C, vitrina=47, sega=_SEGA)
    check("непозната игра се ВИЖДА, не изчезва тихо",
          isinstance(_s_dota, list) and _s_dota
          and "Dota 2 - The International" in POSLEDNO.get("ligi_bez_igra", []))
    check("непознатата игра НЕ се сплесква в позната купчина",
          set(po_igra(_s_dota if isinstance(_s_dota, list) else [])) ==
          {"cs2", "lol", "valorant", ""})

    check("броят проверки е поне 60", ok >= 60)

    print("САМОПРОВЕРКА НА ESPORT: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


def zhivo():
    """Истинско питане — за очи, не за автомат."""
    if _PIN is None:
        print("🔴 pinnacle.py липсва — не мога да питам")
        return 1
    vit = broy_ot_vitrina()
    print("витрина: " + ("НЕ МОЖАХ ДА ПИТАМ" if vit is NEPITAN else str(vit) + " мача обявени"))
    fx = fixtures()
    if fx is NEPITAN:
        print("🔴 ИЗВОРЪТ ОТКАЗА — " + str(POSLEDNO.get("prichina", "")))
        print("   (това НЕ е „няма мачове“ — картите просто се пропускат)")
        return 1
    print("черна кутия: " + str(POSLEDNO))
    grupi = po_igra(fx)
    for ig in sorted(grupi):
        ime = IGRA_IME.get(ig, "❓ непозната игра")
        redove = grupi[ig]
        s_cena = len([z for z in redove if z["cena_dom"] or z["cena_gost"]])
        print("")
        print("  %s — %d мача, %d с цена" % (ime, len(redove), s_cena))
        for z in redove[:12]:
            c = ("%s / %s" % (z["cena_dom"], z["cena_gost"])
                 if (z["cena_dom"] or z["cena_gost"]) else "БЕЗ ЦЕНА")
            print("     %s  %-24s vs %-24s  %-28s %s"
                  % (z["start"][5:16], str(z["dom"])[:24], str(z["gost"])[:24],
                     str(z["turnir"])[:28], c))
        # Колко НЕ съм показал. „0 находки" твърде често значи „0 прегледани";
        # тук поне се вижда, че списъкът е отрязан за очите, не за сметката.
        if len(redove) > 12:
            print("     ... и още %d, непоказани" % (len(redove) - 12))
    # Пътят, по който предсказателят ще пита: с НАШИТЕ имена, не с техните.
    print("")
    print("  проба с имена, каквито пишем НИЕ:")
    for d, g in (("NAVI", "M80"), ("Team Vitality", "Inner Circle"),
                 ("mousesports", "9z"), ("paiN", "Peladona")):
        c = cena(d, g)
        print("     %-16s vs %-20s -> %s"
              % (d, g, ("%s / %s%s" % (c["dom"], c["gost"], " (обърнат)" if c["obarnat"] else ""))
                 if c else "None"))
    print("")
    print("заявки общо: %d" % _PIN.broi_zayavki())
    return 0


if __name__ == "__main__":
    if "--zhivo" in sys.argv:
        sys.exit(zhivo())
    sys.exit(selftest())
