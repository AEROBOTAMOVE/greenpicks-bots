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

## ЗАЩО СЕ ИСКА И ЧАСЪТ, И ЗАЩО ПРОЗОРЕЦЪТ Е ШИРОК

🔴 ПЪРВАТА МИ МЯРКА МЕРЕШЕ ГРЕШНОТО И Я ОСТАВЯМ ЗАПИСАНА. Тя каза «±30 мин
пази 100% от верните и реже лъжите седем пъти», но сравняваше офертата САМА
СЪС СЕБЕ СИ — там часовете съвпадат по устройство, тоест всеки прозорец пази
100%. Проверка, съдържаща отговора си.

Истинското положение: нашият извор дава ЕДИН час, Betano — ДРУГ. При WTT
Контендер Betano обявява 70-минутна мрежа и после пренаписва всеки час на
реалния ред на масите (измерено живо: 11 от 11 събития мръднаха с 55 до 210
минути за час и три четвърти).

Премерено наново, с ИЗМЕСТЕНИ часове срещу адверсарни двойки:

    спорт          ±30      ±120     ±240     без час
    футбол          3/0     43/0    100/0    100/2
    тенис на маса   3/0     55/3    100/6    100/21
    тенис           0/0     40/0     98/0     98/1
    хокей           0/0     40/0    100/0    100/0
    (чете се «хваща% / лъже%»)

±30 хваща ТРИ процента. ±240 хваща почти всичко и при повечето спортове не
купува нито една лъжа. Затова подразбирането е 240.

Двусмислието (едни и същи двама играят два пъти на ден) се хваща от отказа
при равни кандидати в `ceni_za`, не от тесен прозорец.

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
    # 🔴 БЮДЖЕТ ПО СПОРТ, НЕ СЛЯП ТАВАН (08.09.2026). Измерено живо: таванът
    # от 14 турнира изхвърляше 1085 от 1596 отборни събития (68%) и
    # ВСИЧКИТЕ 43 ИТФ турнира при тениса — тоест точно това, от което идват
    # картите ни. Тук се брои КОЛКО ЗАЯВКИ може да похарчи спортът за целия
    # рън; турнирите се подреждат по търсената лига, тоест харчът е насочен.
    # 0 връща старото поведение (само първите TAVAN_TURNIRI, без насочване).
    TAVAN_ZAYAVKI = max(0, min(400, int(
        (os.environ.get("BETANO_TAVAN_ZAYAVKI") or "24").strip() or 24)))
except ValueError:
    TAVAN_ZAYAVKI = 24
try:
    # Прозорецът в МИНУТИ около обявения от НАС час.
    #
    # 🔴 240, НЕ 30 (поправено 08.09.2026). Първата стойност дойде от мярка,
    # която сравняваше офертата САМА СЪС СЕБЕ СИ — там часовете съвпадат по
    # устройство и всеки прозорец «пази 100%». Проверка, съдържаща отговора
    # си. Премерено с ИЗМЕСТЕНИ часове (55-210 мин, както Betano пренаписва
    # реда на масите при WTT): ±30 хваща 3% от истински изместените, ±120
    # хваща 43%, ±240 хваща 100% и при повечето спортове НЕ купува нито
    # една лъжа. «Без час» вече е скъпо: 21% лъжи при тениса на маса.
    #
    # 0 значи «не гледай часа» и остава като път назад.
    PROZOREC = max(0, min(720, int(
        (os.environ.get("BETANO_PROZOREC") or "240").strip() or 240)))
except ValueError:
    PROZOREC = 240

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
# Колко заявки е похарчил всеки спорт за този рън. Отделно от _STAT, защото
# бюджетът е ПО СПОРТ, а _STAT брои всичко.
_HARCH = {}


def _nulirai_stat():
    _STAT["zayavki"] = 0
    _STAT["provali"] = 0
    _HARCH.clear()


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


# 🔴 ДВОЙКИТЕ, КОИТО ДВАТА ПРАВОПИСА ПИШАТ РАЗЛИЧНО. Редът има значение:
# по-дългите съчетания се заменят първи.
FONETIKA = (("dzh", "j"), ("dj", "j"), ("tch", "ch"), ("sch", "sh"),
            ("th", "t"), ("ph", "f"), ("ck", "k"), ("gh", ""), ("kh", "h"))
_GLASNI = re.compile(r"[aeiou]+")
_DVOYNI = re.compile(r"(.)\1+")
_G_PRED_E = re.compile(r"g(?=[ei])")


def skelet(w):
    """Фонетичният скелет на една дума — за сравнение, не за показване.

    Прибира точно местата, където българският и английският правопис на едно
    и също име се разминават: неударената гласна, «th», «дж», «gh», «w».

        sunderland / sandarland   ->  sandarland
        bournemouth / bornemut    ->  barnamat
        chargers / chardzhars     ->  harjars

    🔴 «w» ПАДА, а не става «v». Българското «у» е гласна и се прибира с
    останалите; «Уориърс» никога не носи «в».
    """
    t = str(w or "")
    for a, b in FONETIKA:
        t = t.replace(a, b)
    # «g» пред предна гласна звучи «дж» в английските имена (Chargers, Angeles)
    t = _G_PRED_E.sub("j", t)
    t = t.replace("w", "")
    t = _GLASNI.sub("a", t)          # всяка редица гласни -> една
    return _DVOYNI.sub(r"\1", t)     # двойните съгласни -> една


def blizki(x, y):
    """Две думи са една и съща дума. Три стъпала, от строго към прощаващо.

    🔴 ПРАГЪТ 6 БУКВИ Е ИЗМЕРЕН. По-къс праг слива «Симек» и «Юпа».

    🔴 СКЕЛЕТЪТ СЕ ИСКА ТОЧЕН (08.09.2026). Размито сравнение върху скелети
    умножава двете хлабавини. Мерено на 24 прочетени верни двойки и 3277
    адверсарни: скелетът вдига улова от 62% на 88% срещу +0.3 пункта
    адверсарни лъжи, докато разхлабването на прага до 0.74 дава 79% срещу
    25% лъжи по прочетените — тоест скелетът е по-добрата сделка.

    🔴 ПРАГЪТ 5 БУКВИ ЗА СКЕЛЕТА. По-къс слива твърде много: скелетът и без
    това е загубил гласните.
    """
    if x == y:
        return True
    if len(x) >= 6 and len(y) >= 6 and \
            difflib.SequenceMatcher(None, x, y).ratio() >= 0.85:
        return True
    sx, sy = skelet(x), skelet(y)
    return len(sx) >= 5 and sx == sy


# 🔴 БЕЛЯЗАНИТЕ ЕТИКЕТИ. «Мъже» НЕ е между тях: мъжкото е мълчаливото
# подразбиране в спортното именуване, а женското и възрастовото се пишат.
_ZHENI = re.compile(
    "(\u0436\u0435\u043d\u0438|\u0436\u0435\u043d\u0441\u043a|"
    "\u0434\u0430\u043c\u0438|\u0434\u0430\u043c\u0441\u043a|"
    "women|female|girls|wta|ladies)", re.I)
# 🔴 СУРОВ НИЗ. Първата ми версия беше нормален низ, тоест "\b" ставаше
# BACKSPACE и цялата възрастова половина НИКОГА не се хващаше — U17 минаваше
# за открит турнир. Собствената ми проверка го улови.
_VAZRAST = re.compile(
    r"(\bu-?(1[5-9]|2[0-3])\b|\u044e\u043d\u043e\u0448|"
    r"\u0434\u0435\u0432\u043e\u0439\u043a|youth|junior|cadet)", re.I)


def etiket(tekst):
    """Белязаните етикети в един текст. Празно множество = мъжки/открит.

    Ползва се за ЛИГАТА, не за имената: «Бразилия» е «Бразилия» и в двата
    турнира, а разликата стои в името на състезанието.
    """
    t = str(tekst or "")
    e = set()
    if _ZHENI.search(t):
        e.add("zheni")
    if _VAZRAST.search(t):
        e.add("vazrast")
    return e


def etiketite_pasvat(nash, tehen):
    """Може ли наша лига и техен турнир да са едно и също състезание.

    🔴 БЕЛЯЗАНОТО ТРЯБВА ДА Е И ОТ ДВЕТЕ СТРАНИ ИЛИ ОТ НИТО ЕДНА. Женски мач
    с цена от мъжкия е тиха грешна цена — най-лошият вид, защото картата
    изглежда пълна.
    """
    return etiket(nash) == etiket(tehen)


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
            # 🔴 ПОДЪТ Е 1.02, НЕ 1.00 (08.09.2026). Живо намерен коефициент
            # 1.001 минаваше пазача и се печаташе като «1.00» — число, което
            # се закръгля до едно, не е цена, а «няма пазар» с цифри.
            if c < 1.02:
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


def podredi(turnirite, liga):
    """Турнирите, подредени по близост до ТЪРСЕНАТА лига.

    🔴 ЗАЩО. Дотук се взимаха първите `TAVAN_TURNIRI` в реда на дървото. При
    футбола това са България×3, УЕФА×3, Англия×8 — а картите ни идват от Копа
    Либертадорес, MLS, Аржентина и Бразилия, които падат извън. Насочването
    харчи същите заявки, но по мача, който наистина търсим.
    """
    if not liga:
        return list(turnirite)
    dl = redica(liga)
    if not dl:
        return list(turnirite)

    def tezhest(x):
        di = redica(x[0])
        if not di:
            return 0
        n = sum(1 for a in dl if any(blizki(a, b) for b in di))
        return n
    belyazani = [(tezhest(x), i, x) for i, x in enumerate(turnirite)]
    belyazani.sort(key=lambda y: (-y[0], y[1]))
    return [y[2] for y in belyazani]


def _sabitiya_ot_turnir(put, ime, otvarach=None):
    """Събитията на ЕДИН турнир. Кешира се ПО ТУРНИР, само при успех."""
    kl = ("turnir", put)
    if kl in _kesh:
        return _kesh[kl]
    d = _json(BAZA + put + OPASHKA, otvarach)
    if d is NEPITAN:
        return NEPITAN
    vsi = []
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


def sabitiya(sport, otvarach=None, liga=None):
    """[(дом, гост, начало_мс, коеф_дом, коеф_гост, коеф_равен, лига, път)].

    NEPITAN, ако САМОТО ДЪРВО е отказало. Отказ на отделен турнир не е отказ
    на извора — той се брои и се минава нататък.

    🔴 КЕШЪТ Е ПО ТУРНИР, НЕ ПО СПОРТ (08.09.2026). Дотук спортът се теглеше
    ВЕДНЪЖ и каквото хванеше в първите 14 турнира — това оставаше за целия
    рън. Сега всеки турнир се помни отделно и питанията се ТРУПАТ: втората
    карта от същия спорт ползва свалените и досваля само каквото ѝ трябва.

    🔴 БЮДЖЕТ ПО СПОРТ. `BETANO_TAVAN_ZAYAVKI` казва колко заявки МОЖЕ да
    похарчи този спорт за целия рън. Нула връща старото поведение.
    """
    t = turniri(sport, otvarach)
    if t is NEPITAN:
        return NEPITAN
    if not TAVAN_ZAYAVKI:
        # старият път: първите N в реда на дървото, без насочване
        red = list(t[:TAVAN_TURNIRI])
    else:
        red = podredi(t, liga)
    vsi = []
    for ime, put in red:
        kl = ("turnir", put)
        if kl not in _kesh:
            if TAVAN_ZAYAVKI and _HARCH.get(sport, 0) >= TAVAN_ZAYAVKI:
                continue          # бюджетът за този спорт е свършил
            _HARCH[sport] = _HARCH.get(sport, 0) + 1
        r = _sabitiya_ot_turnir(put, ime, otvarach)
        if r is NEPITAN:
            continue
        vsi.extend(r)
    return vsi


def ceni_za(sport, dom, gost, nachalo=None, otvarach=None, liga=None):
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
    ev = sabitiya(sport, otvarach, liga)
    if ev is NEPITAN:
        return NEPITAN
    if not (redica(dom) and redica(gost)):
        return None
    kand = []
    for zap in ev:
        A, B, st = zap[0], zap[1], zap[2]
        # 🔴 ПОЛ И ВЪЗРАСТ. Турнирът на Betano е zap[6]; нашата лига идва
        # отвън. Разминат ли се белязаните етикети, това не е нашият мач.
        #
        # 🔴 ПРЕЗ ФУНКЦИЯТА, НЕ НА РЪКА. Първата ми версия сравняваше двете
        # множества направо тук и остави `etiketite_pasvat` МЪРТВА — родена
        # и незакачена в същия час. Собственият ми проверчик за цялост я
        # хвана. Правилото трябва да живее НА ЕДНО място.
        if liga and not etiketite_pasvat(liga, str(zap[6] or "")):
            continue
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


def ima_go(sport, dom, gost, nachalo=None, otvarach=None, liga=None):
    """Заложим ли е мачът в българската книга. None при отказ на извора."""
    r = ceni_za(sport, dom, gost, nachalo, otvarach, liga)
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
    # ── 🔴 ФОНЕТИЧНИЯТ СКЕЛЕТ (08.09.2026)
    #
    # Мерено на 24 ПРОЧЕТЕНИ верни двойки и 3277 адверсарни: скелетът вдига
    # улова от 62% на 88% срещу +0.3 пункта адверсарни лъжи. Разхлабването
    # на прага до 0.74 дава 79% срещу 25% лъжи — по-лошата сделка.
    #
    # 🔴 ПРОВЕРКИТЕ СА ПО ДВОЙКИ, КОИТО СЪМ ЧЕЛ. Скелет, изпитан със
    # съчинени думи, доказва аритметика, не съвпадане на имена.
    check("неударената гласна се прибира",
          skelet("sunderland") == skelet("sandarland"))
    check("«th» става «t»", skelet("bournemouth") == skelet("bornemut"))
    check("«gh» пада", skelet("brighton") == skelet("braitan"))
    check("«дж» и «g» пред «e» се срещат",
          skelet("khargers") == skelet("khardzhars"))
    check("«w» ПАДА, не става «v»", "v" not in skelet("warriors"))
    check("двойните съгласни се свиват", skelet("tigerr") == skelet("tiger"))
    # 🔴 И ОТРИЦАТЕЛНА КОНТРОЛА: скелетът НЕ слива всичко.
    check("различни имена дават РАЗЛИЧНИ скелети",
          skelet("liverpool") != skelet("levski"))
    check("и още едно", skelet("arsenal") != skelet("barcelona"))
    check("скелетът на къса дума не се ползва",
          not blizki("abc", "adc"))

    # прочетените двойки, през целия матчър
    check("Съндърланд се среща", sreshta("Sunderland", "Съндърланд"))
    check("Борнемут се среща", sreshta("Bournemouth", "Борнемут"))
    check("Брайтън се среща", sreshta("Brighton", "Брайтън"))
    check("Ривър Плейт се среща", sreshta("River Plate", "Ривър Плейт"))
    check("Лос Анджелис Чарджърс се среща",
          sreshta("Los Angeles Chargers", "Лос Анджелис Чарджърс"))
    check("Каролина Хърикейнс се среща",
          sreshta("Carolina Hurricanes", "Каролина Хърикейнс"))
    # 🔴 ПРОЧЕТЕНИ РАЗЛИЧНИ: тук съвпадение е ЛЪЖА.
    check("Копа Олимпия НЕ е Олимпиакос",
          not sreshta("Club Olimpia", "Олимпиакос"))
    check("Брага НЕ е Брайтън", not sreshta("Braga", "Брайтън"))
    check("Орегон Бийвърс НЕ е Чикаго Беърс",
          not sreshta("Oregon State Beavers", "Чикаго Беърс"))
    check("Мартин Бух НЕ е Витолд Бучински",
          not sreshta("Martin BUCH", "Витолд Бучински"))
    check("Феликс Льобрюн НЕ е Гжегож Фелкел",
          not sreshta("Felix LEBRUN", "Гжегож Фелкел"))

    # 🔴 ЕДИНСТВЕНАТА ИЗМЕРЕНА ЛЪЖА И ЗАЩО НЕ БОЛИ. «Golden State Valkyries»
    # и «Golden State Warriors» СЕ СРЕЩАТ с «Голдън Стейт Уориърс» — два
    # отбора от един град. Силата им е РАВНА, а `ceni_za` отказва при равни
    # кандидати; тоест двусмислието дава МЪЛЧАНИЕ, не грешна цена.
    check("двата отбора от един град наистина се сливат по име",
          sreshta("Golden State Valkyries", "Голдън Стейт Уориърс")
          and sreshta("Golden State Warriors", "Голдън Стейт Уориърс"))
    check("но силата им е РАВНА",
          sila("Golden State Valkyries", "Голдън Стейт Уориърс")
          == sila("Golden State Warriors", "Голдън Стейт Уориърс"))
    _kesh.clear()
    _dvusm = {"data": {"blocks": [{"events": [
        {"participants": [{"name": "Голдън Стейт Уориърс"},
                          {"name": "Финикс Сънс"}],
         "startTime": 1788850800000, "url": "/koefitsienti/a/1/",
         "markets": [{"handicap": 0.0, "selections": [
             {"name": "Голдън Стейт Уориърс", "price": 1.70},
             {"name": "Финикс Сънс", "price": 2.10}]}]},
        {"participants": [{"name": "Голдън Стейт Валкирии"},
                          {"name": "Далас Уингс"}],
         "startTime": 1788850800000, "url": "/koefitsienti/b/2/",
         "markets": [{"handicap": 0.0, "selections": [
             {"name": "Голдън Стейт Валкирии", "price": 3.10},
             {"name": "Далас Уингс", "price": 1.31}]}]}]}]}}
    _dv_darvo = {"data": {"regionGroups": [{"regions": [
        {"name": "САЩ", "leagues": [
            {"name": "НБА", "url": "/sport/x/1/"}]}]}]}}

    def _dv_otv(rq, timeout=None):
        u = rq.full_url
        pitani.append(u)
        telo = _dvusm if "/sport/x/1/" in u else _dv_darvo

        class F(object):
            def read(self_inner):
                return json.dumps(telo).encode("utf-8")

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return F()

    # 🔴 ПРОТИВНИКЪТ РАЗПЛИТА ДВУСМИСЛИЕТО. Двата отбора от един град се
    # сливат по име, но срещу РАЗЛИЧНИ противници — тогава едната двойка
    # съвпада и по двете страни, а другата не.
    _dv1 = ceni_za("basketball", "Golden State Warriors", "Phoenix Suns",
                   1788850800000, _dv_otv)
    check("противникът разплита двата отбора от един град",
          isinstance(_dv1, tuple) and abs(_dv1[0] - 1.70) < 1e-9)
    _kesh.clear()
    _dv2 = ceni_za("basketball", "Golden State Valkyries", "Dallas Wings",
                   1788850800000, _dv_otv)
    check("и другият отбор води до ДРУГАТА цена",
          isinstance(_dv2, tuple) and abs(_dv2[0] - 3.10) < 1e-9)
    _kesh.clear()
    # 🔴 А КОГАТО И ПРОТИВНИКЪТ Е ЕДИН — ОТКАЗ, не гадаене.
    _dv_ednakvi = {"data": {"blocks": [{"events": [
        {"participants": [{"name": "Голдън Стейт Уориърс"},
                          {"name": "Финикс Сънс"}],
         "startTime": 1788850800000, "url": "/koefitsienti/a/1/",
         "markets": [{"handicap": 0.0, "selections": [
             {"name": "Голдън Стейт Уориърс", "price": 1.70},
             {"name": "Финикс Сънс", "price": 2.10}]}]},
        {"participants": [{"name": "Голдън Стейт Валкирии"},
                          {"name": "Финикс Меркурий"}],
         "startTime": 1788850800000, "url": "/koefitsienti/b/2/",
         "markets": [{"handicap": 0.0, "selections": [
             {"name": "Голдън Стейт Валкирии", "price": 3.10},
             {"name": "Финикс Меркурий", "price": 1.31}]}]}]}]}}

    def _dv_otv2(rq, timeout=None):
        u = rq.full_url
        pitani.append(u)
        telo = _dv_ednakvi if "/sport/x/1/" in u else _dv_darvo

        class F(object):
            def read(self_inner):
                return json.dumps(telo).encode("utf-8")

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return F()

    check("две неразличими срещи дават МЪЛЧАНИЕ, не грешна цена",
          ceni_za("basketball", "Golden State Warriors", "Phoenix Suns",
                  1788850800000, _dv_otv2) is None)
    _kesh.clear()

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
    # 🔴 ИЗМЕСТЕН ЧАС СЕ ПРИЕМА, ДАЛЕЧЕН — НЕ. Betano пренаписва реда на
    # масите с 55-210 минути; ±30 хващаше 3% от истински изместените.
    _kesh.clear()
    check("час, изместен с 3 часа, ВСЕ ПАК дава цена",
          isinstance(ceni_za("tabletennis", "Tomas Regner", "Adam Svoboda",
                             1788850800000 + 3 * 3600000, dvoen), tuple))
    _kesh.clear()
    check("но час от друг ДЕН не дава",
          ceni_za("tabletennis", "Tomas Regner", "Adam Svoboda",
                  1788850800000 + 26 * 3600000, dvoen) is None)
    _kesh.clear()
    check("и прозорецът наистина е широк", PROZOREC >= 120)
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

    # ── 🔴 БЮДЖЕТЪТ, КЕШЪТ ПО ТУРНИР И НАСОЧВАНЕТО ПО ЛИГА (08.09.2026)
    #
    # Измерено живо: старият таван от 14 турнира изхвърляше 1085 от 1596
    # отборни събития (68%) и ВСИЧКИТЕ 43 ИТФ турнира при тениса. Първите 14
    # футболни турнира са България×3, УЕФА×3, Англия×8 — а картите ни идват
    # от Копа Либертадорес, MLS, Аржентина, Бразилия.
    _kesh.clear()
    _HARCH.clear()
    _mn_pit = []
    _mn_darvo = {"data": {"regionGroups": [{"regions": [
        {"name": "Англия", "leagues": [
            {"name": "Висша лига", "url": "/sport/x/anglia/"}]},
        {"name": "Южна Америка", "leagues": [
            {"name": "Копа Либертадорес", "url": "/sport/x/libertadores/"}]},
        {"name": "САЩ", "leagues": [
            {"name": "МЛС", "url": "/sport/x/mls/"}]}]}]}}

    def _mn_liga(dom, gost, cena):
        return {"data": {"blocks": [{"events": [
            {"participants": [{"name": dom}, {"name": gost}],
             "startTime": 1788850800000, "url": "/koefitsienti/x/1/",
             "markets": [{"handicap": 0.0, "selections": [
                 {"name": dom, "price": cena},
                 {"name": gost, "price": 2.00}]}]}]}]}}

    def _mnogo(rq, timeout=None):
        u = rq.full_url
        _mn_pit.append(u)
        if "/anglia/" in u:
            telo = _mn_liga("Арсенал Лондон", "Челси Лондон", 1.70)
        elif "/libertadores/" in u:
            telo = _mn_liga("Палмейрас Сао Пауло", "Бока Хуниорс", 1.80)
        elif "/mls/" in u:
            telo = _mn_liga("Интер Маями", "Орландо Сити", 1.90)
        else:
            telo = _mn_darvo

        class F(object):
            def read(self_inner):
                return json.dumps(telo).encode("utf-8")

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return F()

    # 🔴 НАСОЧВАНЕТО: с лига «Копа Либертадорес» нейният турнир трябва да е
    # ПЪРВИ в реда, а не осми зад английските дивизии.
    _t3 = [("Англия / Висша лига", "/a/"),
           ("Южна Америка / Копа Либертадорес", "/b/"),
           ("САЩ / МЛС", "/c/")]
    check("насочването слага търсената лига ПЪРВА",
          podredi(_t3, "Копа Либертадорес, Южна Америка")[0][1] == "/b/")
    check("и другата лига дава друг ред",
          podredi(_t3, "МЛС, САЩ")[0][1] == "/c/")
    check("без лига редът НЕ се пипа",
          [x[1] for x in podredi(_t3, None)] == ["/a/", "/b/", "/c/"])
    check("непозната лига също не чупи реда",
          len(podredi(_t3, "Нещо, което го няма")) == 3)

    # 🔴 БЮДЖЕТЪТ: с бюджет 1 се тегли САМО първият турнир.
    _kesh.clear()
    _HARCH.clear()
    del _mn_pit[:]
    _st_tz = TAVAN_ZAYAVKI
    try:
        globals()["TAVAN_ZAYAVKI"] = 1
        _r1 = ceni_za("football", "Palmeiras", "Boca Juniors",
                      1788850800000, _mnogo, "Копа Либертадорес")
        check("с бюджет 1 насочената лига ВСЕ ПАК се намира",
              isinstance(_r1, tuple) and abs(_r1[0] - 1.80) < 1e-9)
        check("и е похарчена точно една заявка за турнир",
              _HARCH.get("football") == 1)
        # другата лига НЕ може да се стигне — бюджетът е свършил
        check("а мач от НЕтърсената лига остава ненамерен",
              ceni_za("football", "Inter Miami", "Orlando City",
                      1788850800000, _mnogo, "Копа Либертадорес") is None)
    finally:
        globals()["TAVAN_ZAYAVKI"] = _st_tz

    # 🔴 КЕШЪТ Е ПО ТУРНИР И СЕ ТРУПА: втора карта от друга лига досваля само
    # своя турнир, а вече свалените не се теглят пак.
    _kesh.clear()
    _HARCH.clear()
    del _mn_pit[:]
    _a = ceni_za("football", "Palmeiras", "Boca Juniors",
                 1788850800000, _mnogo, "Копа Либертадорес")
    _sled_prva = len(_mn_pit)
    _b2 = ceni_za("football", "Inter Miami", "Orlando City",
                  1788850800000, _mnogo, "МЛС")
    check("втората карта също се намира",
          isinstance(_b2, tuple) and abs(_b2[0] - 1.90) < 1e-9)
    check("дървото НЕ се тегли втори път",
          sum(1 for u in _mn_pit if "/sport/soccer/" in u) == 1)
    check("а вече свалените турнири не се теглят пак",
          len(set(_mn_pit)) == len(_mn_pit))
    _kesh.clear()
    _HARCH.clear()

    # ── 🔴 ПОЛ И ВЪЗРАСТ (08.09.2026)
    #
    # Националните отбори носят ЕДНО И СЪЩО име за мъже и жени. Живо: Betano
    # държи 241 женски събития, 742 мъжки и 4 двойки с еднакви имена и
    # РАЗЛИЧЕН етикет. Информацията я имаме в ЛИГАТА, липсваше сравнението.
    check("женското се разпознава на български",
          "zheni" in etiket("CSV жени, Южна Америка"))
    check("и на английски",
          "zheni" in etiket("CSV Women South American Championship"))
    check("и «girls» брои", "zheni" in etiket("FIVB Girls U17 World Cup"))
    check("възрастта се разпознава",
          "vazrast" in etiket("FIVB Volleyball Girls' U17 World Championship"))
    check("и «юноши» брои", "vazrast" in etiket("Юноши до 19, Испания"))
    # 🔴 «МЪЖЕ» НЕ Е БЕЛЯЗАН. Мъжкото е мълчаливото подразбиране; ако беше
    # белязано, всяка мъжка лига без думата «мъже» щеше да се разминава.
    check("«мъже» НЕ е белязан етикет",
          etiket("Men's South American Cup") == set())
    check("открита лига няма етикет", etiket("Чешка професионална лига") == set())
    check("празното няма етикет", etiket(None) == set())
    check("женска среща женска", etiketite_pasvat(
        "CSV Women South American Championship", "Международни / ... жени"))
    check("мъжка среща открита", etiketite_pasvat(
        "Men's South American Cup", "Международни / South American Champ"))
    # 🔴 РАЗМИНАТИТЕ СЕ ОТКАЗВАТ — в двете посоки.
    check("мъжка НЕ среща женска", not etiketite_pasvat(
        "Men's South American Cup", "Международни / ... жени"))
    check("женска НЕ среща мъжка", not etiketite_pasvat(
        "CSV Women South American Championship", "Международни / мъже"))
    check("U17 НЕ среща открита", not etiketite_pasvat(
        "FIVB Girls U17 World Championship", "Международни / жени"))

    # поведенчески, през целия път
    _kesh.clear()
    _et_darvo = {"data": {"regionGroups": [{"regions": [
        {"name": "Международни", "leagues": [
            {"name": "Южноамериканско жени", "url": "/sport/x/zheni/"}]}]}]}}
    _et_liga = {"data": {"blocks": [{"events": [
        {"participants": [{"name": "Бразилия"}, {"name": "Венецуела"}],
         "startTime": 1788850800000, "url": "/koefitsienti/x/1/",
         "markets": [{"handicap": 0.0, "selections": [
             {"name": "Бразилия", "price": 1.20},
             {"name": "Венецуела", "price": 4.50}]}]}]}]}}

    def _et_otv(rq, timeout=None):
        u = rq.full_url
        pitani.append(u)
        telo = _et_liga if "/zheni/" in u else _et_darvo

        class F(object):
            def read(self_inner):
                return json.dumps(telo).encode("utf-8")

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return F()

    check("женска наша лига ВЗИМА цена от женския турнир",
          isinstance(ceni_za("volleyball", "Бразилия", "Венецуела",
                             1788850800000, _et_otv,
                             "CSV Women South American Championship"), tuple))
    _kesh.clear()
    check("🔴 МЪЖКА наша лига НЕ взима цена от женския турнир",
          ceni_za("volleyball", "Бразилия", "Венецуела", 1788850800000,
                  _et_otv, "Men's South American Cup") is None)
    _kesh.clear()
    check("без подадена лига пазачът мълчи (старото поведение)",
          isinstance(ceni_za("volleyball", "Бразилия", "Венецуела",
                             1788850800000, _et_otv), tuple))
    _kesh.clear()

    # ── 🔴 ПОДЪТ НА ЦЕНАТА
    # Живо намерен коефициент 1.001 минаваше стария пазач (>1.0) и се
    # печаташе като «1.00» — число, което се закръгля до едно, не е цена.
    _pod = {"participants": [{"name": "Tomas Regner"},
                             {"name": "Adam Svoboda"}],
            "markets": [{"handicap": 0.0, "selections": [
                {"name": "Tomas Regner", "price": 1.001},
                {"name": "Adam Svoboda", "price": 20.0}]}]}
    check("коефициент 1.001 НЕ е цена", koef_ot_sabitie(_pod) == {})
    _pod["markets"][0]["selections"][0]["price"] = 1.02
    check("а 1.02 е", koef_ot_sabitie(_pod) != {})

    # ── ръчките
    check("бюджетът е в разумни граници", 0 <= TAVAN_ZAYAVKI <= 400)
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
