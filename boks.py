# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БОКСЪТ 🥊

Един въпрос: има ли спорт, който може да влезе с ЦЕНА още в първия си ден?

═══════════════════════════════════════════════════════════════════════════
ЗАЩО СЪЩЕСТВУВА (25.08.2026)
═══════════════════════════════════════════════════════════════════════════

Всеки досегашен спорт влиза по един и същи път: първо срещите (ESPN, FIVB,
WTT, Flashscore), после — ако изобщо — цената. Тенисът чакаше цена цял месец,
волейболът я получи вчера, тенисът на маса още я няма.

Боксът обръща реда. ESPN НЯМА боксов фийд — проверено на живо ДНЕС, пет
адреса, всичките затворени:
    /sports/boxing/scoreboard            -> 404
    /sports/boxing/boxing/scoreboard     -> 400
    /sports/mma/boxing/scoreboard        -> 400
    /sports/boxing/boxing/news           -> 400
    core/v2/sports/boxing/leagues        -> 400
Но Pinnacle има. Измерено на живо, 25.08.2026, guest слоят без ключ:
    /sports                        -> Boxing, id = 6, matchupCount = 22
    /sports/6/matchups             -> 22 мача, всичките type=matchup,
                                      НУЛА с parentId (няма подмачове)
    /sports/6/markets/straight     -> 23 пазара: 22 moneyline (period 0)
                                      и 1 тотал
    designation-и в moneyline      -> home 22 · away 22 · draw 0

Тоест боксът идва с ЦЕНА ОТ ПЪРВИЯ ДЕН — нещо, което дори тенисът на маса
(114 карти) няма и до днес. Срещите и цената идват от ЕДНА И СЪЩА двойка
заявки, вече кеширани в pinnacle.py.

🔴 МАРЖЪТ, ИЗМЕРЕН НА ЖИВО (25.08.2026, 22 мача)
    сбор 1/цена: медиана 1.0439 · мин 1.0395 · макс 1.0469 · среден 1.0434
Тоест 4.4% отгоре. За сравнение, измереното в pazar.py на 18.08: футбол 7.4%,
баскетбол 4.8%, бейзбол 1.9%. Боксът е по средата — и точно затова суровото
`1/цена` не влиза никъде: вероятността минава през pazar.bez_marzh.

🔴 РАВЕНСТВОТО СЪЩЕСТВУВА В БОКСА, НО НЕ И В ТОЗИ ПАЗАР
Реми е истински изход на боксов мач. Pinnacle обаче не го котира тук: 22 от
22 пазара имат само home и away. Значи двуизходно за СМЕТКАТА, но при
отсъждане реми не е нито познато, нито сгрешено — залогът се връща. Който
добави отсъждане, да не го брои за загуба.

═══════════════════════════════════════════════════════════════════════════
🔴 СИТОТО: „MIKE TYSON СРЕЩУ FLOYD MAYWEATHER" НЕ Е НАСРОЧЕН МАЧ
═══════════════════════════════════════════════════════════════════════════

Сред 22-та записа стои „Mike Tyson vs Floyd Mayweather Jr" със старт
2026-12-04. Тайсън е на 60 години. Това е дългосрочен спекулативен пазар, не
среща — и ако влезе в стаята, ботът пуска карта за бой, който няма да се
състои.

ИЗМЕРЕНО ДНЕС, за да не се гадае по какво се различават:
    isFeatured      -> False при спекулативния, НО и при 9 истински мача
    isHighlighted   -> False при спекулативния, НО и при 9 истински
    ageLimit        -> 17 при спекулативния, НО и при 7 истински
    maxRiskStake    -> 2000 при спекулативния срещу 250 при почти всички
                       (тоест лимитът е ПО-ГОЛЯМ — обратното на очакваното)
    league          -> „Boxing Matches" за ВСИЧКИТЕ 22
Нито един структурен белег не го отделя. Отделя го САМО датата:
    най-далечният ИСТИНСКИ мач  -> 2026-09-05, тоест 11 дни напред
    спекулативният              -> 2026-12-04, тоест 101 дни напред
    пропастта между двете       -> 90 дни

Затова прагът е 45 дни — над двойното на измереното истинско (11) и под
половината на измереното спекулативно (101). ЧЕСТНО: това е избор в средата
на пропастта, а не измерена граница. Голям истински мач, обявен четири месеца
предварително, ЩЕ падне тук. Затова спекулативните не се трият мълчаливо —
`sito` ги връща ПОИМЕННО в отчета си, за да се види кой точно е отпаднал.
Прагът се мени с една константа, без пипане на логика.

🔴 РЕДЪТ НА СИТОТО Е ЧАСТ ОТ ОТГОВОРА. Спекулативните се броят ПРЕДИ
прозореца на деня. Ако беше обратното, Тайсън щеше да падне като „далеч
напред, чака си реда" и числото „колко спекулативни отпаднаха" щеше да е
НУЛА винаги — тоест точно мярката, заради която ситото съществува, щеше да
показва, че ситото не прави нищо.

═══════════════════════════════════════════════════════════════════════════
🔴 ФАМИЛИЯТА: „JR" НЕ Е ФАМИЛИЯ
═══════════════════════════════════════════════════════════════════════════

`pinnacle._familiya` взима последната дума и маха само едно-буквените
инициали. Измерено върху днешните 44 бойци:
    „Floyd Mayweather Jr"  -> „jr"
    „Andy Ruiz Jr"         -> „jr"
Двама РАЗЛИЧНИ бойци с една и съща „фамилия" (2 от 44, 4.5%). Мач на Тайсън
срещу Руис би получил цената на Тайсън срещу Мейуедър — тихо и с вид на успех.

Затова тук фамилията се смята НАНОВО, с махнати наставки (Jr/Sr/II/III/IV).
`pinnacle.py` не се пипа: неговата фамилия е правена за тенисисти и там
работи; боксът просто не я наследява.

🔴 И ВТОРО: ЕДНА ФАМИЛИЯ, ДВАМА БОЙЦИ В ЕДНА ВЕЧЕР
Измерено днес: 29.08 в 22:30 се бие „Leonard Carillo", а в 23:30 — „Juan
Carillo". Двама различни. Търсене по фамилии не може да ги раздели: двойката
{cardenas, carillo} е единствена и би върнала цената на ГРЕШНИЯ Carillo.
Затова фамилният път се ползва САМО когато фамилията се среща ТОЧНО ВЕДНЪЖ
на цялата витрина. Мълчание вместо цената на друг човек.

═══════════════════════════════════════════════════════════════════════════
🔴 КАКВО ТОЗИ ФАЙЛ НЕ РЕШАВА: ОТСЪЖДАНЕТО
═══════════════════════════════════════════════════════════════════════════

Цена има. Резултат — НЯМА. Проверено на живо днес, седем затворени врати:
петте адреса на ESPN отгоре, плюс TheSportsDB:
    /eventsday.php?d=2026-08-23&s=Fighting -> 3 събития, едното е
        „Rolando Romero vs Teofimo Lopez", лига „Boxing" (id 4445)
    /lookupevent.php?id=2528767            -> strStatus „NS", strResult „",
        intHomeScore null, strHomeTeam null — ДВА ДНИ след мача
Тоест TheSportsDB знае, че мачът съществува, но не знае какво е станало.

Значи: боксът може да пусне карта с честно число, но никой не може да я
отсъди. Това НЕ е недостатък на този файл — той е за срещите и цената — но
е причината, поради която картите му трябва да се обявят за неотсъждаеми
(`scorer.NO_RESULT`), а не да висят вечно като „чакащи резултат". Точно
дефектът, който ММА направи на 12.08, а тенисът на маса — преди това.

  python boks.py --selftest   — проверките, БЕЗ мрежа
  python boks.py --zhivo      — истинско питане, за очи
"""
import calendar
import sys
import time

# Нашето име на спорта (влиза като bucket) и техният номер.
NASH_KLYUCH = "boxing"
PIN_ID = 6

# Еталонът за „жив ли е изворът". Мерено 25.08.2026: soccer дава 967 мача.
# Нула бокс при нула еталон значи запушен извор, а не празен ден.
ETALON = "football"

# 🔴 СЕНТИНЕЛ „НЕ МОЖАХ ДА ПИТАМ".
# НЕ е списък, НЕ е None, НЕ е празно. Празният списък се чете като „днес
# няма мачове" и картата за спорта просто не излиза — тоест падналата мрежа
# изглежда точно като спокоен ден. Всеки, който вика fixtures/cena, е длъжен
# да сравни с `is NEPITAN` ПРЕДИ да гледа дължината.
NEPITAN = object()

# Отвъд толкова дни напред мачът се брои за спекулативен пазар, не за среща.
# Измерено 25.08.2026: истинските стигат до 11 дни, спекулативният е на 101.
SPEKULA_DNI = 45.0

# Под толкова секунди до първия гонг вече не е прогноза. Същото число като
# PREDICT_LEAD_MIN=10 в предсказателя.
LEAD_SEK = 600.0

# Наставки, които НЕ са фамилия. „V" нарочно го няма: рискът да отреже
# истинско име е по-голям от ползата.
SUFIKSI = ("jr", "jnr", "sr", "snr", "ii", "iii", "iv")


def _modul(ime):
    """Модул по име или None.

    През `__import__`, за да може самопроверката да подмени записа в
    sys.modules и нито една проверка да не пипне мрежата.
    """
    try:
        return __import__(str(ime))
    except Exception:                                        # noqa: BLE001
        return None


def registrirai(pin=None):
    """Вписва бокса в pinnacle.SPORT_ID. True, ако ключът е там.

    🔴 ЕДИНСТВЕНОТО СТРАНИЧНО ДЕЙСТВИЕ НА ТОЗИ ФАЙЛ — и то е нарочно.

    `pinnacle.machove/pazari` тръгват от SPORT_ID; няма ли „boxing" там, те
    връщат {} БЕЗ да са питали. Същият ключ отваря и другите две врати, които
    вече съществуват и не се пипат:
        predictor.dobavi_pazar   ->  `if _b in PIN.SPORT_ID: PIN.ceni_za(...)`
        pazar.pat_do_zatvaryane  ->  `„pinnacle" if kl in PIN.SPORT_ID`
    Тоест с този един ключ боксът получава и цена при пускане, и ЗАТВАРЯЩА
    цена, тоест CLV — без нито ред промяна в чужд файл.

    Вписва се само със `setdefault`: сложи ли някой ден pinnacle.py свой номер
    за бокса, неговият печели. Постоянното място на този ред е в самия
    pinnacle.py („boxing": 6); тук стои, защото този файл няма право да го
    пипа.
    """
    pin = pin if pin is not None else _modul("pinnacle")
    if pin is None:
        return False
    karta = getattr(pin, "SPORT_ID", None)
    if not isinstance(karta, dict):
        return False
    karta.setdefault(NASH_KLYUCH, PIN_ID)
    return NASH_KLYUCH in karta


def _norm(s):
    """Име, сведено до сравнимо: малки букви, само букви и цифри."""
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def familiya(s):
    """Фамилията БЕЗ наставки. Празно при боклук.

    „Floyd Mayweather Jr" -> „mayweather"   (pinnacle._familiya дава „jr")
    „Andy Ruiz Jr"        -> „ruiz"         (pinnacle._familiya дава „jr")
    „M. M."               -> „m"            (никога празно, докато има дума:
                                             празната фамилия съвпада с ВСИЧКИ)
    """
    d = [w for w in str(s or "").replace("-", " ").split() if w]
    while len(d) > 1:
        posl = str(d[-1]).strip(".,").lower()
        if len(posl) <= 1 or posl in SUFIKSI:
            d.pop()
            continue
        break
    return _norm(d[-1]) if d else ""


def epoh(iso):
    """ISO час -> секунди от епохата. None при липса или боклук.

    Pinnacle пише „2026-08-26T07:00:00Z" в matchups и „...+00:00" в markets.
    И двете са UTC; разчитат се без чужди библиотеки, за да не зависи ситото
    от инсталация.
    """
    t = str(iso or "").strip().replace(" ", "T")
    if not t:
        return None
    if t.endswith("Z"):
        t = t[:-1]
    opashka = t[10:]
    for znak in ("+", "-"):
        if znak in opashka:
            t = t[:10] + opashka.split(znak)[0]
            break
    if "." in t:
        t = t.split(".")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return float(calendar.timegm(time.strptime(t, fmt)))
        except ValueError:
            continue
    return None


def dni_napred(iso, sega=None):
    """Колко ДНИ напред е този старт. None, ако дата няма."""
    ts = epoh(iso)
    if ts is None:
        return None
    return (ts - float(sega if sega is not None else time.time())) / 86400.0


def chisti_p(cena_dom, cena_gost):
    """(p_дом, p_гост) с махнат марж, взето на заем от pazar.bez_marzh.

    Не се преписва: маржът е измерен и обяснен там, а два преписа на едно
    правило са начин единият да се поправи, а другият да остане крив.
    Името тук е РАЗЛИЧНО нарочно — `bez_marzh` съществува в два файла и
    едноименната функция вече е маскирала мъртъв код веднъж (виж cyalost.py).

    (None, None) без pazar.py — числото се пропуска, не се измисля.
    """
    pz = _modul("pazar")
    if pz is None or not hasattr(pz, "bez_marzh"):
        return (None, None)
    try:
        p = pz.bez_marzh(NASH_KLYUCH, cena_dom, cena_gost)
    except Exception:                                        # noqa: BLE001
        return (None, None)
    if not isinstance(p, (list, tuple)) or len(p) < 2:
        return (None, None)
    return (p[0], p[1])


def surovi(pin=None):
    """(мачове, цени) от Pinnacle, или NEPITAN.

    мачове = {номер: (дом, гост, лига, старт)} — точно каквото дава
    pinnacle.machove. цени = {номер: (дом, гост, равен)} — pinnacle.pazari.
    ДВЕ заявки за целия спорт, кеширани; трета САМО ако боксът върне нула.

    🔴 НУЛА МАЧОВЕ Е ДВА РАЗЛИЧНИ ОТГОВОРА. pinnacle._j гълта всяка мрежова
    грешка и връща None, а machove превръща None в {} — тоест паднала мрежа и
    празен ден изглеждат еднакво отвън. Затова при нула се пита ЕТАЛОНЕН
    спорт, който никога не е празен. Нула бокс + нула еталон = запушен извор.
    """
    pin = pin if pin is not None else _modul("pinnacle")
    if pin is None:
        return NEPITAN
    if not registrirai(pin):
        return NEPITAN
    try:
        mm = pin.machove(NASH_KLYUCH)
        cc = pin.pazari(NASH_KLYUCH)
    except Exception:                                        # noqa: BLE001
        return NEPITAN
    if not isinstance(mm, dict) or not isinstance(cc, dict):
        return NEPITAN
    if not mm:
        try:
            et = pin.machove(ETALON)
        except Exception:                                    # noqa: BLE001
            return NEPITAN
        if not isinstance(et, dict) or not et:
            return NEPITAN
    return (mm, cc)


def prazen_otchet():
    """Отчетът на ситото, преди да е минал един запис."""
    return {"vsichko": 0, "schupeni": 0, "bez_data": 0, "spekulativni": [],
            "zapochnali": 0, "izvan": 0, "bez_cena": 0, "godni": 0}


def sito(mach, cen, sega=None, dni=None):
    """(годни, отчет). ЧИСТА функция — нито една заявка вътре.

    `dni=None` значи БЕЗ прозорец: остават всички истински мачове, колкото и
    напред да са. `dni=1` значи „днес и утре" и е това, което иска картата.

    Отчетът брои ВСЯКО отпадане поотделно, а спекулативните ги връща и
    ПОИМЕННО — числото „колко отпаднаха" без имената им не може да бъде
    оспорено от никого.
    """
    s = float(sega if sega is not None else time.time())
    otchet = prazen_otchet()
    godni = []
    for nomer, red in sorted((mach or {}).items()):
        otchet["vsichko"] += 1
        if not isinstance(red, (list, tuple)) or len(red) < 2:
            otchet["schupeni"] += 1
            continue
        dom, gost = str(red[0] or ""), str(red[1] or "")
        liga = str(red[2] or "") if len(red) > 2 else ""
        iso = str(red[3] or "") if len(red) > 3 else ""
        if not _norm(dom) or not _norm(gost) or _norm(dom) == _norm(gost):
            otchet["schupeni"] += 1
            continue
        d = dni_napred(iso, s)
        if d is None:
            otchet["bez_data"] += 1
            continue
        # 🔴 ПЪРВО СПЕКУЛАТИВНИТЕ, чак после прозорецът на деня. Защо —
        # виж заглавието: обратният ред обезсмисля самата мярка.
        if d > SPEKULA_DNI:
            otchet["spekulativni"].append((dom, gost, round(d, 1), iso))
            continue
        if d * 86400.0 < LEAD_SEK:
            otchet["zapochnali"] += 1
            continue
        if dni is not None and d > float(dni):
            otchet["izvan"] += 1
            continue
        c = (cen or {}).get(str(nomer))
        cd = c[0] if isinstance(c, (list, tuple)) and len(c) > 0 else None
        cg = c[1] if isinstance(c, (list, tuple)) and len(c) > 1 else None
        # И двете цени са условие, не удобство: с една страна маржът не може
        # да се махне, а суровото 1/цена надува пазара с измерените 4.4%.
        if cd is None or cg is None:
            otchet["bez_cena"] += 1
            continue
        pd, pg = chisti_p(cd, cg)
        godni.append({
            "id": str(nomer), "dom": dom, "gost": gost, "liga": liga,
            "start": iso, "start_ts": epoh(iso), "dni": round(d, 3),
            "cena_dom": cd, "cena_gost": cg, "p_dom": pd, "p_gost": pg,
        })
    godni.sort(key=lambda x: x["start_ts"])
    otchet["godni"] = len(godni)
    return godni, otchet


def fixtures_s_otchet(sega=None, dni=None, pin=None, mach=None, cen=None):
    """(годни, отчет) или NEPITAN. Тук живее ЕДИНСТВЕНОТО питане."""
    if mach is None and cen is None:
        sur = surovi(pin)
        if sur is NEPITAN:
            return NEPITAN
        mach, cen = sur
    return sito(mach or {}, cen or {}, sega, dni)


def fixtures(sega=None, dni=None, pin=None, mach=None, cen=None):
    """Предстоящите боксови мачове С ЦЕНА. NEPITAN = не можах да питам.

    🔴 ГОЛОТО `fixtures()` ТРЯБВА ДА РАБОТИ. Днес в този проект хванахме
    модул, чиито 45 проверки минаваха, а естественото извикване връщаше None
    ВИНАГИ, защото си строеше указателя от празни речници. Затова: не са ли
    подадени данни, ВЗИМАТ СЕ — и точно този път се изпитва в самопроверката.
    """
    r = fixtures_s_otchet(sega, dni, pin, mach, cen)
    return NEPITAN if r is NEPITAN else r[0]


def index(mach, cen):
    """Списък записи за търсене по имена. Строи се веднъж, ползва се много.

    Тук НЕ се сее ситото: ситото казва кой мач става за КАРТА, а указателят
    отговаря на друг въпрос — „каква е цената на тази двойка имена". Мач,
    който вече е започнал, пак има цена, и опресняването я иска.
    """
    out = []
    for nomer, red in sorted((mach or {}).items()):
        if not isinstance(red, (list, tuple)) or len(red) < 2:
            continue
        dom, gost = str(red[0] or ""), str(red[1] or "")
        if not _norm(dom) or not _norm(gost) or _norm(dom) == _norm(gost):
            continue
        c = (cen or {}).get(str(nomer))
        cd = c[0] if isinstance(c, (list, tuple)) and len(c) > 0 else None
        cg = c[1] if isinstance(c, (list, tuple)) and len(c) > 1 else None
        if cd is None and cg is None:
            continue
        out.append({"id": str(nomer), "dom": dom, "gost": gost,
                    "liga": str(red[2] or "") if len(red) > 2 else "",
                    "start": str(red[3] or "") if len(red) > 3 else "",
                    "cena_dom": cd, "cena_gost": cg,
                    "nd": _norm(dom), "ng": _norm(gost),
                    "fd": familiya(dom), "fg": familiya(gost)})
    return out


def _index_ili_vzemi(ind, mach, cen, pin=None):
    """Указателят: подаденият, или взет от Pinnacle. NEPITAN при отказ."""
    if ind is not None:
        return ind
    if mach is None and cen is None:
        sur = surovi(pin)
        if sur is NEPITAN:
            return NEPITAN
        mach, cen = sur
    return index(mach or {}, cen or {})


def _otgovor(r, nd, fd):
    """Записът, върнат в НАШИЯ ред на страните. None, ако не се разпознава.

    🔴 ДОМАКИНЪТ ПРИ ТЯХ НЕ Е НАШИЯТ ДОМАКИН. В бокса „home" е чиста
    уговорка. Намери ли се двойката наопаки, цените се РАЗМЕНЯТ, а полето
    „obarnat" го казва открито — то влиза в дневника и по-късно затварящата
    цена се взима със същия флаг, без ново сверяване на имена.
    """
    if nd and nd == r["nd"]:
        obarnat = False
    elif nd and nd == r["ng"]:
        obarnat = True
    elif fd and fd == r["fd"]:
        obarnat = False
    elif fd and fd == r["fg"]:
        obarnat = True
    else:
        return None
    cd, cg = r["cena_dom"], r["cena_gost"]
    if obarnat:
        cd, cg = cg, cd
    return {"dom": cd, "gost": cg, "nomer": r["id"], "liga": r["liga"],
            "start": r["start"], "obarnat": obarnat}


def cena(dom, gost, ind=None, mach=None, cen=None, pin=None):
    """Цената за НАШИТЕ две имена. None = няма. NEPITAN = не можах да питам.

    Два пътя, от строгото към хлабавото, и ДВАТА мълчат при спор:
      1. пълните имена съвпадат (нашият случай: имената идват оттам буквално)
      2. фамилиите съвпадат — но САМО ако всяка от двете се среща ТОЧНО
         ВЕДНЪЖ на цялата витрина

    Второто условие го наложи измерване, не предпазливост: на 29.08.2026 се
    бият „Leonard Carillo" и „Juan Carillo". Двойката {cardenas, carillo} е
    единствена и без проверката би върнала цената на другия Carillo.
    """
    ind = _index_ili_vzemi(ind, mach, cen, pin)
    if ind is NEPITAN:
        return NEPITAN
    nd, ng = _norm(dom), _norm(gost)
    if not nd or not ng or nd == ng:
        return None

    tochni = [r for r in ind if {r["nd"], r["ng"]} == {nd, ng}]
    if len(tochni) == 1:
        return _otgovor(tochni[0], nd, familiya(dom))
    if len(tochni) > 1:
        return None                      # спор, който не се разрешава

    fd, fg = familiya(dom), familiya(gost)
    if not fd or not fg or fd == fg:
        return None
    broi = {}
    for r in ind:
        broi[r["fd"]] = broi.get(r["fd"], 0) + 1
        broi[r["fg"]] = broi.get(r["fg"], 0) + 1
    if broi.get(fd, 0) != 1 or broi.get(fg, 0) != 1:
        return None                      # фамилия, която носят двама
    po_fam = [r for r in ind if {r["fd"], r["fg"]} == {fd, fg}]
    if len(po_fam) != 1:
        return None
    return _otgovor(po_fam[0], nd, fd)


# ═══════════════════════════════ САМОПРОВЕРКА
#
# Всичко е ПОВЕДЕНЧЕСКО: подхвърлят се данни и се гледа изходът. Нито една
# проверка не търси текст във файла — игла, застанала в съседния коментар,
# минава и върху счупен файл.
#
# Данните НЕ са измислени: имената, часовете и цените са свалените на живо
# на 25.08.2026, а американските котировки са минали през pinnacle.deset
# (-836 -> 1.12, +567 -> 6.67 и така нататък).

_M = {
    "1": ("Moses Itauma", "Filip Hrgovic", "Boxing Matches", "2026-08-29T20:00:00Z"),
    "2": ("Mike Tyson", "Floyd Mayweather Jr", "Boxing Matches", "2026-12-04T04:00:00Z"),
    "3": ("Ramon Cardenas", "Leonard Carillo", "Boxing Matches", "2026-08-29T22:30:00Z"),
    "4": ("Najee Lopez", "Juan Carillo", "Boxing Matches", "2026-08-29T23:30:00Z"),
    "5": ("Damian Knyba", "Andy Ruiz Jr", "Boxing Matches", "2026-09-05T00:30:00Z"),
    "6": ("Nikita Tszyu", "Ben Mahoney", "Boxing Matches", ""),
    "7": ("Vegas Larfield", "Jubert Buhat", "Boxing Matches", "2026-08-25T04:00:00Z"),
    "8": ("Sam Noakes", "Denys Berinchyk", "Boxing Matches", "2026-08-29T18:00:00Z"),
    "9": ("само едно име",),
    "10": ("Kirra Ruston", "Saundre Simmons", "Boxing Matches", "2026-08-26T07:30:00Z"),
    "11": ("Terri Harper", "Miranda Reyes", "Boxing Matches", "2026-08-29T17:30:00Z"),
}
_C = {
    "1": (1.12, 6.67, None), "2": (6.97, 1.11, None), "3": (1.13, 6.18, None),
    "4": (1.15, 5.67, None), "5": (3.24, 1.36, None), "6": (1.17, 5.41, None),
    "7": (1.18, 5.13, None), "9": (1.50, 2.50, None), "10": (1.15, 5.83, None),
    # 🔴 ЕДНОСТРАННА ЦЕНА. Среща се при затворена линия. Без нея мутацията
    # „cd is None ИЛИ cg is None" -> „И" минаваше през всичките проверки:
    # мач с ЕДНА страна щеше да стане карта, а маржът не може да се махне
    # от една цена — тоест числото на картата щеше да е сурово, надуто с
    # измерените 4.4%.
    "11": (1.30, None, None),
}
# „Сега" за проверките: 25.08.2026, 16:00 UTC. Закован, за да не е тестът
# зелен сутрин и червен вечер.
_T0 = epoh("2026-08-25T16:00:00Z")


class _FalshivPinnacle(object):
    """Pinnacle без мрежа. Брои дали изобщо е бил питан."""

    SPORT_ID = {"tennis": 33}
    vikan = [0]

    @staticmethod
    def machove(klyuch):
        _FalshivPinnacle.vikan[0] += 1
        if klyuch == NASH_KLYUCH:
            return dict(_M)
        return {"x": ("A", "B", "", "")}

    @staticmethod
    def pazari(klyuch):
        return dict(_C) if klyuch == NASH_KLYUCH else {}


def _rechnik(x):
    """x, ако е речник; иначе {}.

    🔴 САМО ЗА ПРОВЕРКИТЕ, и заради конкретна мутация. NEPITAN е обикновен
    обект, тоест `bool(NEPITAN)` е ИСТИНА — значи „bool(c) and c.get(...)"
    пропуска сентинела нататък и вдига AttributeError. Мутация, която
    СЪБАРЯ пакета, казва по-малко от мутация, която дава „счупено": не се
    вижда КОЯ защита е паднала.
    """
    return x if isinstance(x, dict) else {}


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # ───────────────────────────────────────────────────────── ЧАСЪТ
    check("ISO с Z се разчита", epoh("2026-08-26T07:00:00Z") is not None)
    check("ISO с отместване се разчита",
          epoh("2026-08-29T23:30:00+00:00") == epoh("2026-08-29T23:30:00Z"))
    check("гола дата се разчита", epoh("2026-08-26") is not None)
    check("празно няма час", epoh("") is None and epoh(None) is None)
    check("боклук няма час", epoh("вчера следобед") is None)
    check("дните напред се броят вярно",
          abs(dni_napred("2026-08-26T16:00:00Z", _T0) - 1.0) < 1e-6)
    check("минал час дава отрицателни дни",
          dni_napred("2026-08-24T16:00:00Z", _T0) < 0)
    check("без дата няма дни", dni_napred("", _T0) is None)

    # ──────────────────────────────── ФАМИЛИЯТА (сърцевината на находката)
    check("Jr не е фамилия", familiya("Floyd Mayweather Jr") == "mayweather")
    check("Jr не е фамилия и втория път", familiya("Andy Ruiz Jr") == "ruiz")
    check("двамата Jr НЕ се сливат в едно",
          familiya("Floyd Mayweather Jr") != familiya("Andy Ruiz Jr"))
    check("III също не е фамилия", familiya("George Foreman III") == "foreman")
    check("обикновената фамилия си остава", familiya("Mike Tyson") == "tyson")
    check("инициалът в началото не пречи", familiya("F. Hrgovic") == "hrgovic")
    check("тирето разделя — взима се последната",
          familiya("Barrera-Gomez") == "gomez")
    check("само инициали не дават ПРАЗНО", familiya("M. M.") != "")
    check("празно дава празно", familiya("") == "" and familiya(None) == "")

    # ─────────────────────────────────────────────────── РЕГИСТРАЦИЯТА
    _k = {"tennis": 33}

    class _Nosi(object):
        SPORT_ID = _k

    check("боксът се вписва в картата", registrirai(_Nosi) is True)
    check("и наистина е там с верния номер", _k.get(NASH_KLYUCH) == PIN_ID)

    _chuzhd = {"boxing": 99}

    class _Chuzhd(object):
        SPORT_ID = _chuzhd

    registrirai(_Chuzhd)
    check("чуждият номер НЕ се презаписва", _chuzhd["boxing"] == 99)

    class _Bez(object):
        pass

    check("модул без карта дава False", registrirai(_Bez) is False)
    check("липсващ модул не гърми", _modul("нямаТакъвМодулНикъде") is None)

    # ──────────────────────────────── СЕНТИНЕЛЪТ „НЕ МОЖАХ ДА ПИТАМ"
    class _Padnal(object):
        SPORT_ID = {}

        @staticmethod
        def machove(klyuch):
            raise OSError("мрежата я няма")

        @staticmethod
        def pazari(klyuch):
            return {}

    check("паднала мрежа дава СЕНТИНЕЛ", surovi(_Padnal) is NEPITAN)

    class _BezKarta(object):
        pass

    check("pinnacle без SPORT_ID дава СЕНТИНЕЛ", surovi(_BezKarta) is NEPITAN)

    class _Zapushen(object):
        SPORT_ID = {}

        @staticmethod
        def machove(klyuch):
            return {}

        @staticmethod
        def pazari(klyuch):
            return {}

    check("нула бокс + нула еталон = СЕНТИНЕЛ", surovi(_Zapushen) is NEPITAN)

    class _ChestnaNula(object):
        SPORT_ID = {}

        @staticmethod
        def machove(klyuch):
            return {} if klyuch == NASH_KLYUCH else {"y": ("A", "B", "", "")}

        @staticmethod
        def pazari(klyuch):
            return {}

    _cn = surovi(_ChestnaNula)
    check("нула бокс + жив еталон = ЧЕСТНА НУЛА",
          _cn is not NEPITAN and _cn[0] == {})

    class _Boklyuk(object):
        SPORT_ID = {}

        @staticmethod
        def machove(klyuch):
            return ["не е речник"]

        @staticmethod
        def pazari(klyuch):
            return {}

    check("отговор с грешна форма е СЕНТИНЕЛ", surovi(_Boklyuk) is NEPITAN)
    check("отказът стига до fixtures, не се губи",
          fixtures(pin=_Padnal) is NEPITAN)
    check("отказът НЕ се чете като празен списък",
          fixtures(pin=_Padnal) != [])
    check("отказът стига и до cena",
          cena("Mike Tyson", "Ben Mahoney", pin=_Padnal) is NEPITAN)

    # ────────────────────── ЕСТЕСТВЕНОТО ИЗВИКВАНЕ (без нито един аргумент)
    # 🔴 ЗАЩО Е ТУК. Днес в този проект хванахме модул с 45 зелени проверки,
    # чието голо извикване връщаше None винаги. Изпитва се ПЪТЯТ, не само
    # сметката. Мрежата е ПОДМЕНЕНА, не пипана.
    _star = sys.modules.get("pinnacle")
    _FalshivPinnacle.vikan[0] = 0
    _FalshivPinnacle.SPORT_ID = {"tennis": 33}
    try:
        sys.modules["pinnacle"] = _FalshivPinnacle
        _bez = fixtures(sega=_T0)
        check("голото fixtures() НЕ мълчи",
              isinstance(_bez, list) and len(_bez) > 0)
        check("голото fixtures() наистина е питало",
              _FalshivPinnacle.vikan[0] > 0)
        check("и е вписало бокса по пътя",
              _FalshivPinnacle.SPORT_ID.get(NASH_KLYUCH) == PIN_ID)
        _bc = _rechnik(cena("Moses Itauma", "Filip Hrgovic"))
        check("голото cena() НЕ мълчи", bool(_bc))
        check("голото cena() дава истинската цена",
              _bc.get("dom") == 1.12 and _bc.get("gost") == 6.67)
        check("номерът излиза навън — без него няма CLV",
              _bc.get("nomer") == "1")
        check("подаденият указател бие взетия",
              cena("Moses Itauma", "Filip Hrgovic", ind=[]) is None)
    finally:
        if _star is None:
            sys.modules.pop("pinnacle", None)
        else:
            sys.modules["pinnacle"] = _star

    # ─────────────────────────────────────────────────────────── СИТОТО
    godni, o = sito(_M, _C, _T0, None)
    check("ситото брои ВСИЧКО, което е дошло", o["vsichko"] == 11)
    check("годните са 5", o["godni"] == 5 and len(godni) == 5)
    # 🔴 НИТО ЕДНО [0] БЕЗ „ИМА ЛИ ГО". Първата версия на тези три реда
    # четеше spekulativni[0] направо — и три от осемте мутации не даваха
    # „счупено", а СЪБАРЯХА целия файл с IndexError. Паднал пакет казва
    # по-малко от паднала проверка: не се вижда КОЕ се е счупило.
    _spek = o["spekulativni"]
    check("спекулативният е ТОЧНО един", len(_spek) == 1)
    check("и това е Тайсън", bool(_spek) and _spek[0][0] == "Mike Tyson")
    check("спекулативният си носи дните напред",
          bool(_spek) and _spek[0][2] > 100)
    check("спекулативният НЕ е сред годните",
          all(g["dom"] != "Mike Tyson" for g in godni))
    check("без дата отпада и се брои", o["bez_data"] == 1)
    check("започналият отпада и се брои", o["zapochnali"] == 1)
    check("без цена отпада и се брои", o["bez_cena"] == 2)
    check("едностранната цена НЕ става карта",
          all(g["dom"] != "Terri Harper" for g in godni))
    check("счупеният ред отпада и се брои", o["schupeni"] == 1)
    check("сборът на отпадналите плюс годните дава всичко",
          o["godni"] + o["bez_data"] + o["zapochnali"] + o["bez_cena"]
          + o["schupeni"] + o["izvan"] + len(o["spekulativni"]) == o["vsichko"])
    check("годните са подредени по час",
          all(godni[i]["start_ts"] <= godni[i + 1]["start_ts"]
              for i in range(len(godni) - 1)))
    check("най-близкият е първи",
          bool(godni) and godni[0]["dom"] == "Kirra Ruston")

    godni1, o1 = sito(_M, _C, _T0, 1)
    check("прозорецът от 1 ден оставя един", o1["godni"] == 1)
    check("и това е утрешният",
          bool(godni1) and godni1[0]["dom"] == "Kirra Ruston")
    # 🔴 ТАЗИ ИГЛА БЕШЕ СГРЕШЕНА ОТ МЕН (25.08.2026). Написах „4" — четирите
    # годни, паднали заради прозореца. Живото пускане показа 5: мачът БЕЗ
    # ЦЕНА също е отвъд прозореца и пада ТУК, преди да се стигне до цената
    # му. Кодът беше прав, иглата ми — не. Затова сега се броят и двете
    # числа, и се вижда, че при тесен прозорец „без цена" е нула по
    # устройство, а не защото цените изведнъж са се появили.
    check("останалите са ИЗВЪН, не изчезнали", o1["izvan"] == 6)
    check("при тесен прозорец „без цена\" е нула по устройство",
          o1["bez_cena"] == 0)
    # 🔴 МУТАЦИЯТА, КОЯТО ТОВА ПАЗИ: разменят ли се двете проверки, Тайсън
    # пада като „извън прозореца" и броят на спекулативните става НУЛА —
    # тоест мярката би казвала, че ситото не лови нищо.
    check("прозорецът НЕ изяжда спекулативния",
          len(o1["spekulativni"]) == 1)

    check("празни данни дават празен отчет, не гърмят",
          sito({}, {}, _T0)[1]["vsichko"] == 0)
    check("None данни не гърмят", sito(None, None, _T0)[0] == [])
    check("отчетът има всички графи",
          set(prazen_otchet()) == {"vsichko", "schupeni", "bez_data",
                                   "spekulativni", "zapochnali", "izvan",
                                   "bez_cena", "godni"})

    # ────────────────────────────────────────────── ЦЕНАТА И МАРЖЪТ
    g1 = [g for g in godni if g["dom"] == "Moses Itauma"]
    check("годният носи цените", bool(g1) and g1[0]["cena_dom"] == 1.12)
    check("годният носи и вероятностите",
          bool(g1) and g1[0]["p_dom"] is not None)
    if g1 and g1[0]["p_dom"] is not None:
        _s = g1[0]["p_dom"] + g1[0]["p_gost"]
        check("маржът е махнат — сборът е 1", abs(_s - 1.0) < 0.002)
        check("има какво да се маха (суровото не е 1)",
              abs(1.0 / 1.12 + 1.0 / 6.67 - 1.0) > 0.03)
        check("фаворитът е с по-голяма вероятност",
              g1[0]["p_dom"] > g1[0]["p_gost"])
        check("вероятността не е сурова", g1[0]["p_dom"] < 1.0 / 1.12)
    else:
        bad.append("маржът не можа да се провери — липсва pazar")

    _star_pz = sys.modules.get("pazar")
    try:
        class _BezPazar(object):
            pass

        sys.modules["pazar"] = _BezPazar
        check("без pazar вероятността е None, не измислена",
              chisti_p(1.12, 6.67) == (None, None))
        _bp, _bo = sito(_M, _C, _T0, None)
        check("но цената остава",
              bool(_bp) and _bp[0]["cena_dom"] is not None
              and _bp[0]["p_dom"] is None)
        check("и броят годни не се мени от липсата на pazar",
              _bo["godni"] == 5)
    finally:
        if _star_pz is None:
            sys.modules.pop("pazar", None)
        else:
            sys.modules["pazar"] = _star_pz

    # ──────────────────────────────────────────────── ТЪРСЕНЕ ПО ИМЕНА
    ind = index(_M, _C)
    check("указателят пропуска счупения и безценовия",
          len(ind) == 9 and all(r["nd"] for r in ind))
    # Указателят е ПО-ХЛАБАВ от ситото нарочно: за карта трябват две
    # цени, за справка „каква е цената" стига и една.
    _edna = cena("Terri Harper", "Miranda Reyes", ind=ind)
    check("едностранната цена ОСТАВА в указателя",
          bool(_edna) and _edna["dom"] == 1.30 and _edna["gost"] is None)
    c = cena("Moses Itauma", "Filip Hrgovic", ind=ind)
    check("пълните имена намират", c is not None)
    check("и дават верните цени", c and c["dom"] == 1.12 and c["gost"] == 6.67)
    check("не е обърнато", c and c["obarnat"] is False)
    o2 = cena("Filip Hrgovic", "Moses Itauma", ind=ind)
    check("обърнатата двойка се намира", o2 is not None)
    check("обърнатата се обявява", o2 and o2["obarnat"] is True)
    check("обърнатата РАЗМЕНЯ цените",
          o2 and o2["dom"] == 6.67 and o2["gost"] == 1.12)
    check("фамилният път работи при уникална фамилия",
          _rechnik(cena("M. Itauma", "F. Hrgovic", ind=ind)).get("dom") == 1.12)

    # 🔴 ДВАМАТА CARILLO — измерено 25.08.2026: 29.08 в 22:30 и в 23:30
    check("двамата Carillo НЕ се бъркат",
          cena("Ramon Cardenas", "Juan Carillo", ind=ind) is None)
    check("и обратната посока също мълчи",
          cena("Najee Lopez", "Leonard Carillo", ind=ind) is None)
    check("но ТОЧНИТЕ имена си работят",
          _rechnik(cena("Najee Lopez", "Juan Carillo", ind=ind)).get("dom") == 1.15)
    # 🔴 ДВАМАТА „JR" — с чуждата фамилия и двамата са „jr"
    check("Тайсън срещу Руис НЕ взима цената на Мейуедър",
          cena("Mike Tyson", "Andy Ruiz Jr", ind=ind) is None)
    check("Тайсън срещу Мейуедър пак си има цена",
          _rechnik(cena("Mike Tyson", "Floyd Mayweather Jr", ind=ind)).get("dom") == 6.97)

    check("непозната двойка мълчи", cena("Иван", "Драган", ind=ind) is None)
    check("празни имена мълчат", cena("", "", ind=ind) is None)
    check("None имена не гърмят", cena(None, None, ind=ind) is None)
    check("един и същ боец от двете страни не влиза",
          cena("Mike Tyson", "Mike Tyson", ind=ind) is None)
    check("празен указател мълчи",
          cena("Mike Tyson", "Ben Mahoney", ind=[]) is None)
    check("указател от нищо е празен", index({}, {}) == [])
    check("указател без цени е празен", index(_M, {}) == [])
    check("None данни не чупят указателя", index(None, None) == [])

    check("броят проверки е поне 60", ok >= 60)

    print("САМОПРОВЕРКА НА BOKS: " + str(ok) + " наред, "
          + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


def zhivo():
    """Истинско питане — за очи, не за автомат."""
    pin = _modul("pinnacle")
    if pin is None:
        print("🔴 pinnacle.py го няма — нищо не може да се пита")
        return 1
    r = fixtures_s_otchet(dni=None)
    if r is NEPITAN:
        print("🔴 НЕ МОЖАХ ДА ПИТАМ. Това НЕ е „днес няма мачове\".")
        return 1
    godni, o = r
    print("🥊 БОКС от Pinnacle (id %d) · %s"
          % (PIN_ID, time.strftime("%d.%m.%Y %H:%M UTC", time.gmtime())))
    print("   дойдоха %d · счупени %d · без дата %d · започнали %d · без цена %d"
          % (o["vsichko"], o["schupeni"], o["bez_data"],
             o["zapochnali"], o["bez_cena"]))
    print("   СПЕКУЛАТИВНИ (над %g дни напред): %d"
          % (SPEKULA_DNI, len(o["spekulativni"])))
    for d, g, dni, iso in o["spekulativni"]:
        print("      ❌ %-22s vs %-22s  %s  (%.0f дни напред)"
              % (d[:22], g[:22], iso[:10], dni))
    print("   ОСТАВАТ СЛЕД СИТОТО: %d" % o["godni"])
    for m in godni:
        p = ""
        if m["p_dom"] is not None and m["p_gost"] is not None:
            p = "   %4.1f%% / %4.1f%%" % (m["p_dom"] * 100.0, m["p_gost"] * 100.0)
        print("      ✅ %-22s vs %-22s  %s  %5.2f / %5.2f%s"
              % (m["dom"][:22], m["gost"][:22], m["start"][:16],
                 m["cena_dom"], m["cena_gost"], p))
    # Прозорците, които картата наистина ползва. Нови заявки НЯМА — кешът на
    # pinnacle е топъл от първото питане.
    for dni in (1, 3):
        rr = fixtures_s_otchet(dni=dni)
        if rr is NEPITAN:
            continue
        print("   прозорец %d ден(а): %d мача (%d чакат реда си)"
              % (dni, rr[1]["godni"], rr[1]["izvan"]))
    try:
        print("   заявки общо: %d" % pin.broi_zayavki())
    except Exception:                                        # noqa: BLE001
        pass
    return 0


# Вписването става ПРИ ВНОС, за да работи и `predictor.dobavi_pazar`, който
# гледа `bucket in pinnacle.SPORT_ID` и не знае за този файл. Виж registrirai.
registrirai()

if __name__ == "__main__":
    if "--zhivo" in sys.argv:
        sys.exit(zhivo())
    sys.exit(selftest())
