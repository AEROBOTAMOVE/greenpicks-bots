#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ВОЛЕЙБОЛ, КОЙТО ХОРАТА МОГАТ ДА ИГРАЯТ 🏐

Един въпрос: коя волейболна среща изобщо стои на витрината, и на каква цена?

ЗАЩО СЪЩЕСТВУВА
64 от 116-те волейболни карти на стаята бяха „FIVB Girls' U17 World
Championship". Стаята работеше, но продаваше непродаваемо: пазар за момичета
до 17 години не съществува при никой букмейкър. Тук се строи ситото, което
държи възрастните турнири и изхвърля юношеските, плюс втори източник на цена
за спорта, при който Pinnacle мълчи по устройство (0 лиги, 0 мача, винаги).

ИЗМЕРЕНО НА ЖИВО 19.08.2026 (всяко число тук е пуснато, не спомнено)
  FIVB VIS, прозорец 19.08 – 02.09 (14 дни), само насрочени (Status=1):
      173 срещи общо
       60  CEV EuroVolley 2026 | Women     <- възрастен, има пазар
       41  FIVB Boys' U17 World Champ.     <- юношески, няма пазар
       26  NORCECA Women Continental
       26  AVC Women Asian Continental
       20  NCVA Men's Final Six            <- американска зонална, няма пазар
  FIVB VIS, прозорец 19.08 – 02.10 (45 дни): 320 срещи, от тях 120 EuroVolley
  (мъже 60 + жени 60) и 41 юношески.

🟢 БЕЗПЛАТНАТА ПОБЕДА: EuroVolley Е В СЪЩИЯ ИЗТОЧНИК.
Питах GetVolleyTournamentList на живо: турнири номер 1470 („CEV EuroVolley
2026 | Men") и 1471 („... | Women") стоят в същия справочник, който
vol_tournaments() вече дърпа. Тоест стаята НЕ иска нов доставчик, нов ключ
или нова заявка — иска само да предпочете тези срещи пред юношеските.
Днешният vol_fixtures() ГИ ВРЪЩА вече; проблемът е само в подредбата.

ЦЕНАТА
Bovada, без ключ, една заявка:
  /services/sports/event/coupon/events/A/description/volleyball?lang=en
Измерено 19.08.2026: 13 събития с двойка цени (moneyline, десетичен формат
готов), от които ТРИ са затворена линия 1.001/11.00 и отпадат (виж
VOL_MIN_CENA по-долу) -> остават 10 годни: 9 EuroVolley Women и 1 юношеско
квалификационно.
Хоризонтът е КЪС: най-далечният мач беше 22.08, тоест 3 дни напред. Затова
цената НЕ може да е единственото сито — среща след седмица е напълно
търгуема, просто още не е отворена.

🔴 ЕДНА ГРЕШКА ОТ ПРЕДИШНАТА ОБИКОЛКА, ОБОРЕНА С ИЗМЕРВАНЕ.
Предишният отчет твърдеше: „/description/volleyball БЕЗ preMatchOnly=true
връща празно". Пуснато днес, един след друг, същата минута:
    с preMatchOnly=true   ->  25 333 байта, 1 група, 12 събития
    без preMatchOnly      -> 120 419 байта, 2 групи, 13 събития
Тоест без филтъра се връща ПОВЕЧЕ, не празно. Ползваме версията без филтъра
и отсяваме започналите сами (по startTime), защото така не изпускаме нищо.

🔴🔴 И ЕДНО ОТКРИТИЕ, ПО-ГОЛЯМО ОТ ЗАДАЧАТА (измерено 19.08.2026).
Портиерът `ISKAM_PAZAR` в predictor.py е включен от днес. Волейболът обаче
НЯМА нито един път до цена: ESPN няма адрес за спорта (dobavi_pazar познава
само baseball/basketball/soccer), а guest слоят на Pinnacle връща нула мача
по волейбол винаги. Пуснато върху КОПИЕ на predictor.py, върху истинските
срещи за 21.08:
    ima_pazar(EuroVolley Women)          -> РЕЖЕ, „няма пазар"
    ima_pazar(Boys U17 World)            -> РЕЖЕ, „няма пазар"
    ima_pazar(NORCECA Continental)       -> РЕЖЕ, „няма пазар"
Тоест днес портиерът не подрежда волейбола — той го МЪЛЧИ ИЗЦЯЛО, всичките
116 карти. Не „юношеските излизат вместо възрастните", а „не излиза нищо".
Със ситото и с цената оттук, върху същото копие и същите срещи:
    портиерът пуска 15 от 20, реже 5 (петте юношески)
    5 от 20 срещи получават ИЗМЕРЕНА цена — 5 от 8-те EuroVolley за деня;
    другите 3 са със затворена линия и НАРОЧНО остават без число.

🔴 ВТОРО, ПО ПЪТЯ: 11 ОТ 67 ДЪРЖАВИ СТИГАТ ДО ЧИТАТЕЛЯ НА ЛАТИНИЦА.
Пуснато срещу bg_name() от predictor.py с всичките 67 кода на FIVB:
    AZE Azerbaijan · CRC Costa Rica · CUR Curacao · CZE Czech Republic
    GUA Guatemala · HKG Hong Kong · IRQ Iraq · NZL New Zealand · OMA Oman
    TTO Trinidad and Tobago · TUR Türkiye
Двете най-болезнени са CZE и TUR, защото BG_NAME ГИ ИМА — но под другите
имена („Czechia" и „Turkey"), а FIVB праща „Czech Republic" и „Türkiye".
Видяно на живо в сухо пускане: картата изписа „Türkiye — Латвия“ и
„Czech Republic — Гърция“. Поправката е в отчета, не тук: BG_NAME е в чужд
файл и не се пипа от този модул.

  python volley_evro.py --selftest   — проверките, без нито една заявка
  python volley_evro.py --zhivo      — истинско питане, с числа за очи
"""
import datetime
import json
import os
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TIMEOUT = int((os.environ.get("VOL_TIMEOUT") or "25").strip() or 25)

BOVADA = ("https://www.bovada.lv/services/sports/event/coupon/events/A"
          "/description/volleyball?lang=en")
VIS = "https://www.fivb.org/Vis2009/XmlRequest.asmx?Request="

# Праг по стълбицата: под него смятаме, че пазар няма. 50 пуска възрастните
# национални първенства и купи, реже всичко с възрастова граница и всичко
# зонално. Пипа се отвън, за да може стаята да бъде разхлабена без ново качване.
VOL_PRAG = int((os.environ.get("VOL_PRAG") or "50").strip() or 50)

_kesh = {}
_zayavki = [0]


def broi_zayavki():
    """Колко заявки навън е направил този процес. Пази селфтеста честен."""
    return _zayavki[0]


def _get(url, accept="application/json"):
    """Една заявка навън. Хвърля при провал — викащият решава дали го боли."""
    _zayavki[0] += 1
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8-sig", "replace")


# ============================== ИМЕНАТА
#
# 🔴 ЗАЩО ИМЕТО НЕ СТИГА САМО ПО СЕБЕ СИ (измерено 19.08.2026).
# FIVB казва „Türkiye“ и „Czech Republic“. Витрината казва „Turkey W“ и
# „Czech Republic W". А нашият BG_NAME в predictor.py има ключове „Turkey" и
# „Czechia" — тоест ДВЕТЕ страни, които FIVB изписва иначе, минават непреведени
# и стигат до читателя на латиница. Затова тук всяко име се сплесква до
# СЪЩИНА и чак после се сравнява.
_GENDER_DUMI = {"w", "m", "women", "womens", "woman", "men", "mens", "man",
                "female", "male", "girls", "girl", "boys", "boy", "ladies",
                "femminile", "maschile", "feminine", "masculin"}
_PRAZNI_DUMI = {"and", "the", "of", "national", "nationale", "team", "volleyball",
                "volley", "nt", "republic", "rep"}

# Съкращения, които се разминават между двата източника. Прилагат се ВЪРХУ
# сплесканата същина, не върху отделните думи — иначе „Republic" от
# „Dominican Republic" и от „Czech Republic" се държат различно.
_KANON_ALIAS = {
    "turkiye": "turkey",
    "czechia": "czech",
    "czech": "czech",
    "unitedstates": "usa",
    "us": "usa",
    "usofa": "usa",
    "southkorea": "korea",
    "koreasouth": "korea",
    "chinesetaipei": "taipei",
    "hongkongchina": "hongkong",
    "bosniaherzegovina": "bosnia",
    "northmacedonia": "macedonia",
    "trinidadtobago": "trinidad",
    "greatbritain": "britain",
    "cotedivoire": "ivorycoast",
    "iranislamicrepublic": "iran",
    "dominican": "dominican",
}

# Код на държавата -> латинско име. ИЗМЕРЕН, не съчинен: това са всичките 67
# кода, които FIVB върна за прозореца 19.08 – 02.10.2026.
KOD_IME = {
    "ALG": "Algeria", "ARG": "Argentina", "AUS": "Australia", "AUT": "Austria",
    "AZE": "Azerbaijan", "BEL": "Belgium", "BRA": "Brazil", "BRN": "Bahrain",
    "BUL": "Bulgaria", "CAN": "Canada", "CHI": "Chile", "CHN": "China",
    "COL": "Colombia", "CRC": "Costa Rica", "CRO": "Croatia", "CUB": "Cuba",
    "CUR": "Curacao", "CZE": "Czech Republic", "DEN": "Denmark",
    "DOM": "Dominican Republic", "EGY": "Egypt", "ESP": "Spain", "EST": "Estonia",
    "FIN": "Finland", "FRA": "France", "GER": "Germany", "GRE": "Greece",
    "GUA": "Guatemala", "HKG": "Hong Kong", "HUN": "Hungary", "INA": "Indonesia",
    "IND": "India", "IRI": "Iran", "IRQ": "Iraq", "ISR": "Israel", "ITA": "Italy",
    "JPN": "Japan", "KAZ": "Kazakhstan", "KOR": "Korea", "LAT": "Latvia",
    "MEX": "Mexico", "MKD": "North Macedonia", "MNE": "Montenegro",
    "NED": "Netherlands", "NZL": "New Zealand", "OMA": "Oman", "PAK": "Pakistan",
    "PER": "Peru", "POL": "Poland", "POR": "Portugal", "PUR": "Puerto Rico",
    "QAT": "Qatar", "ROU": "Romania", "SLO": "Slovenia", "SRB": "Serbia",
    "SUI": "Switzerland", "SVK": "Slovakia", "SWE": "Sweden", "THA": "Thailand",
    "TPE": "Chinese Taipei", "TTO": "Trinidad and Tobago", "TUN": "Tunisia",
    "TUR": "Turkiye", "UKR": "Ukraine", "USA": "United States",
    "VEN": "Venezuela", "VIE": "Vietnam",
}

# Български -> латинско. Нужен е, защото vol_fixtures() вече е превел името
# през bg_name() и до нас стига кирилица. Без тази карта търсенето на цена
# щеше да е сляпо за собствените ни срещи.
BG_LAT = {
    "Алжир": "Algeria", "Аржентина": "Argentina", "Австралия": "Australia",
    "Австрия": "Austria", "Азербайджан": "Azerbaijan", "Белгия": "Belgium",
    "Бразилия": "Brazil", "Бахрейн": "Bahrain", "България": "Bulgaria",
    "Канада": "Canada", "Чили": "Chile", "Китай": "China", "Колумбия": "Colombia",
    "Коста Рика": "Costa Rica", "Хърватия": "Croatia", "Куба": "Cuba",
    "Чехия": "Czech Republic", "Дания": "Denmark",
    "Доминиканска република": "Dominican Republic", "Египет": "Egypt",
    "Испания": "Spain", "Естония": "Estonia", "Финландия": "Finland",
    "Франция": "France", "Германия": "Germany", "Гърция": "Greece",
    "Унгария": "Hungary", "Индонезия": "Indonesia", "Индия": "India",
    "Иран": "Iran", "Ирак": "Iraq", "Израел": "Israel", "Италия": "Italy",
    "Япония": "Japan", "Казахстан": "Kazakhstan", "Корея": "Korea",
    "Латвия": "Latvia", "Мексико": "Mexico", "Северна Македония": "North Macedonia",
    "Черна гора": "Montenegro", "Нидерландия": "Netherlands",
    "Нова Зеландия": "New Zealand", "Оман": "Oman", "Пакистан": "Pakistan",
    "Перу": "Peru", "Полша": "Poland", "Португалия": "Portugal",
    "Пуерто Рико": "Puerto Rico", "Катар": "Qatar", "Румъния": "Romania",
    "Словения": "Slovenia", "Сърбия": "Serbia", "Швейцария": "Switzerland",
    "Словакия": "Slovakia", "Швеция": "Sweden", "Тайланд": "Thailand",
    "Тайван": "Chinese Taipei", "Тунис": "Tunisia", "Турция": "Turkiye",
    "Украйна": "Ukraine", "САЩ": "United States", "Венецуела": "Venezuela",
    "Виетнам": "Vietnam", "Норвегия": "Norway", "Исландия": "Iceland",
    "Литва": "Lithuania", "Босна и Херцеговина": "Bosnia and Herzegovina",
}


def _fold(s):
    """„Türkiye“ -> „Turkiye“. Иначе едно и също име се брои за две."""
    d = unicodedata.normalize("NFKD", str(s if s is not None else ""))
    return "".join(c for c in d if not unicodedata.combining(c))


def _dumi(s):
    """Име -> списък думи само от букви и цифри, с малки букви."""
    out, cur = [], []
    for ch in _fold(s).lower():
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


def kanon(ime):
    """Име на отбор -> същина, по която двата източника се срещат.

    ЗАЩО: „France“, „France (W)“, „France W“, „FRA“ и „Франция“ са един и същи
    отбор. Ако не се сведат до една дума, всяка цена се губи безшумно —
    точно този клас провал ни е хапал вече (голият ключ, кирилицата в
    търсенето). Полът НАРОЧНО пада тук: носи го отделно поле, виж kanon_pol.
    """
    s = str(ime if ime is not None else "").strip()
    if not s:
        return ""
    kod = s.upper()
    if len(kod) == 3 and kod.isalpha() and kod in KOD_IME:
        s = KOD_IME[kod]
    elif s in BG_LAT:
        s = BG_LAT[s]
    d = [w for w in _dumi(s) if w not in _GENDER_DUMI and w not in _PRAZNI_DUMI]
    core = "".join(d)
    return _KANON_ALIAS.get(core, core)


def kanon_pol(*teksove):
    """Мъже ('m'), жени ('w') или None, ако текстовете се карат помежду си.

    ЗАЩО МЪЛЧИ ПРИ СПОР: EuroVolley върви ЕДНОВРЕМЕННО при мъже и жени и
    двете „France" се сплескват до една и съща същина. Сгрешен пол значи
    цената на мъжкия мач върху женската карта — тоест публикувано число,
    което няма нищо общо със срещата. По-добре без цена, отколкото с чужда.
    """
    vidyano = set()
    for t in teksove:
        d = set(_dumi(t))
        if str(t or "").strip() in ("w", "m"):
            vidyano.add(str(t).strip())
            continue
        if d & {"women", "womens", "woman", "female", "girls", "girl", "ladies",
                "femminile", "feminine", "w"}:
            vidyano.add("w")
        if d & {"men", "mens", "man", "male", "boys", "boy", "maschile",
                "masculin", "m"}:
            vidyano.add("m")
        # „Women" съдържа „men" САМО като подниз, не като дума — затова горе се
        # гледат цели думи. Тази бележка стои, защото точно този капан вече е
        # хапал стълбицата на тениса на маса („championSHIPS").
    if len(vidyano) == 1:
        return vidyano.pop()
    return None


# ============================== СТЪЛБИЦАТА НА ТУРНИРИТЕ
#
# Сверена срещу ВСИЧКИТЕ 219 имена, които FIVB върна за сезони 2025 и 2026.
# Устроена е като _tt_rang за тениса на маса: по-голямото се гледа първо.
_ZONALNI = {"cavb", "cava", "cazova", "ecva", "nevza", "mevza", "wava", "sca",
            "ncva", "afecavol", "zonal", "zone", "npva", "sea"}


def _vazrast(d):
    """Има ли турнирът възрастова граница. Връща True при U17, U-17, Under 19.

    ЗАЩО ОТДЕЛНА ФУНКЦИЯ: границата се пише по ТРИ начина в един и същи
    справочник — „U17“, „U-17“ (думите се разпадат на „u“ и „17“) и
    „Under 19". Проверено срещу истинските имена: „II Central American U-15
    Women", „CAVA Men's Under 19 Volleyball Championship“, „U19 Boys' Norceca“.
    """
    ts = set(d)
    if ts & {"youth", "junior", "juniors", "juniores", "cadet", "cadets",
             "boys", "boy", "girls", "girl", "school", "schools", "juvenil",
             "juveniles", "infantil", "menores", "jeunes", "giovanili"}:
        return True
    for i, w in enumerate(d):
        if w[:1] == "u" and w[1:].isdigit() and 12 <= int(w[1:]) <= 23:
            return True
        if w == "u" and i + 1 < len(d) and d[i + 1].isdigit() \
                and 12 <= int(d[i + 1]) <= 23:
            return True
        if w == "under" and i + 1 < len(d) and d[i + 1].isdigit() \
                and 12 <= int(d[i + 1]) <= 23:
            return True
    return False


def vol_rang(ime):
    """Колко тежи волейболният турнир. По-голямо = по-вероятно да има пазар.

    ЗАЩО СТЪЛБИЦА, А НЕ САМО ЦЕНА: витрината отваря волейбола едва 3 дни
    напред (измерено — най-далечният мач на 19.08 беше на 22.08). Ако съдим
    само по наличната цена, всяка среща след вдругиден става „непродаваема",
    което е лъжа. Стълбицата казва какво Е търгуемо; цената го потвърждава,
    когато прозорецът я отвори.
    """
    d = _dumi(ime)
    ts = set(d)
    if not d:
        return 0
    if ts & {"test", "sim", "demo"}:
        return 0                       # VNL 2026 - MEN (TEST ONLY) и роднините му
    if _vazrast(d):
        return 10                      # юношеско — тук пазар няма, това е целта
    if "masters" in ts or "veteran" in ts or "veterans" in ts:
        return 12
    if "olympic" in ts or "olympics" in ts:
        return 95
    if "world" in ts and ts & {"championship", "championships"} and "club" not in ts:
        return 90
    if "nations" in ts and "league" in ts:
        return 88                      # VNL — вторият по тежест турнир в спорта
    if "eurovolley" in ts:
        return 85
    if ts & {"european"} and ts & {"championship", "championships"}:
        return 85
    if "world" in ts and "club" in ts:
        return 78
    if "champions" in ts and "league" in ts:
        return 76
    if ts & _ZONALNI:
        # Зоналните са НАД проверката за континентални нарочно: „CAVB Zone IV
        # Men Nations Championship" съдържа и „nations“, и „championship“, а
        # витрина за него няма. Мястото на този ред в редицата Е поправката.
        return 30
    if "continental" in ts and ts & {"championship", "championships"}:
        return 66
    if ts & {"european"} and "league" in ts:
        return 62                      # Golden/Silver/European League
    if "league" in ts or "serie" in ts or "liga" in ts or "superliga" in ts:
        return 58                      # клубни първенства (Италия, Полша, Япония)
    if "cup" in ts or "coppa" in ts or "supercoppa" in ts or "supercopa" in ts:
        return 52
    if "games" in ts:
        return 40                      # многоспортови — пазар има рядко
    if ts & {"championship", "championships"}:
        return 45
    return 35


# ============================== ЦЕНАТА ОТ ВИТРИНАТА
def _bovada_sirovo(force=False):
    """Суровият отговор на витрината. Кешира се — една заявка на пускане."""
    if not force and "bov" in _kesh:
        return _kesh["bov"]
    try:
        d = json.loads(_get(BOVADA) or "null")
    except Exception as e:                                   # noqa: BLE001
        print("   ⚠ волейбол, цена: " + str(e)[:70])
        d = None
    _kesh["bov"] = d if isinstance(d, list) else []
    return _kesh["bov"]


# 🔴 ЗАТВОРЕНАТА ЛИНИЯ ИЗГЛЕЖДА КАТО ЦЕНА (измерено 19.08.2026).
# Три от 13-те събития носеха цена 1.001 (американско -100000) срещу 11.00
# (+1000). Това НЕ е пазар — никой не залага на -100000; така витрината
# казва „линията е затворена". Сурово взето, 1.001 дава 99.9% увереност, а
# след махане на маржа 91.7% — число, което после влиза в дневника като
# „ето какво мисли пазарът" и разваля цялото сравнение „ние срещу пазара".
# Сборът НЕ ги лови: затворените дават 1.0899, а истинските 1.0700–1.0817,
# тоест пресичат се. Лови ги долната граница на самата цена.
# Проверено, че границата не изяжда истински линии: „Hungary W – Poland W"
# стои на 1.014286 (-7000) — крайно, но истинско, и остава.
VOL_MIN_CENA = 1.01


def _ceni_ot_sabitie(ev):
    """Двойката десетични цени за победа в мача. {} ако наборът не е пълен.

    ЗАЩО САМО MONEYLINE: сетовият хендикап и точките се движат по друга
    логика и не могат да се сравнят с нашата вероятност „кой печели мача“.
    """
    out = {}
    for dg in ev.get("displayGroups") or []:
        for mk in dg.get("markets") or []:
            if str(mk.get("description") or "").strip().lower() != "moneyline":
                continue
            if str(((mk.get("period") or {}).get("description")) or "").strip().lower() \
                    not in ("match", "game", ""):
                continue
            for o in mk.get("outcomes") or []:
                k = kanon(o.get("description"))
                try:
                    c = float(((o.get("price") or {}).get("decimal")) or 0)
                except (TypeError, ValueError):
                    continue
                if k and c > VOL_MIN_CENA:
                    out[k] = c
    # Стига ЕДНАТА страна да е затворена линия, СРЕЩАТА отпада — оставащата
    # цена сама по себе си не може да се почисти от маржа.
    return out if len(out) == 2 else {}


def pazar_index(force=False):
    """{(пол, същинаA, същинаB) -> запис}. Един индекс за целия рън.

    Ключът е СОРТИРАНА двойка, защото витрината подрежда домакин и гост по
    своя воля: измерено при Pinnacle, че страните им са обърнати спрямо
    нашите. Сортираната двойка прави подредбата без значение, а самите цени
    се пазят по същина на отбора, не по „дом/гост".
    """
    if not force and "idx" in _kesh:
        return _kesh["idx"]
    idx = {}
    sega_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    for grp in _bovada_sirovo(force) or []:
        if not isinstance(grp, dict):
            continue
        put = grp.get("path") or []
        liga = str((put[0].get("description") if put else "") or "")
        for ev in grp.get("events") or []:
            if ev.get("live"):
                continue
            try:
                start = int(ev.get("startTime") or 0)
            except (TypeError, ValueError):
                start = 0
            if start and start < sega_ms:
                continue               # вече започнал — цената му не е за карта
            ceni = _ceni_ot_sabitie(ev)
            if len(ceni) != 2:
                continue
            imena = [str((c or {}).get("name") or "") for c in ev.get("competitors") or []]
            pol = kanon_pol(liga, *imena) or kanon_pol(*imena)
            a, b = sorted(ceni)
            idx[(pol, a, b)] = {"ceni": ceni, "liga": liga, "start": start,
                                "sabitie": str(ev.get("description") or "")}
    _kesh["idx"] = idx
    return idx


def veroyatnost(cena):
    """Цена -> сурова вероятност. 2.00 значи 50%. None при боклук."""
    try:
        c = float(cena)
    except (TypeError, ValueError):
        return None
    return (1.0 / c) if c > 1.0 else None


def bez_marzh(dom, gost):
    """(p_дом, p_гост) с махнат марж. (None, None) при непълен или абсурден набор.

    ЗАЩО: `1/цена` показва пазара по-уверен, отколкото е — сборът по двата
    изхода е над 100% и разликата е делът на витрината.

    🔴 ЧИСЛОТО ТУК БЕШЕ СГРЕШЕНО ОТ МЕН И Е ПОПРАВЕНО (19.08.2026).
    Първо написах „среден сбор 1.0576, тоест 5.8% отгоре“, без да го измеря.
    Пуснато върху ДЕСЕТТЕ събития с истинска линия (трите затворени изхвърлени):
        1.0700 · 1.0707 · 1.0724 · 1.0739 · 1.0756
        1.0768 · 1.0794 · 1.0811 · 1.0817 · 1.0817
        среден сбор 1.0763  ->  7.6% отгоре
    Тоест волейболът при тази витрина е на нивото на футбола при ESPN (7.4%),
    не на бейзбола (1.9%). Числото има значение: прагът, с който мерим „не сме
    съгласни с пазара", е ДВЕ точки, а тук грешката ми беше почти две.

    Не се пипа сбор под 1 — там „поправката“ би НАДУЛА, вместо да свие
    (същият капан, който в pazar.py е измерен като 4.5 пъти по-лош от болестта).
    """
    a, b = veroyatnost(dom), veroyatnost(gost)
    if a is None or b is None:
        return (None, None)
    sbor = a + b
    if not (1.0 < sbor <= 1.6):
        return (None, None)
    return (round(a / sbor, 4), round(b / sbor, 4))


def cena(dom, gost, pol=None):
    """Цена за срещата от витрината. None, ако я няма. Имена, кодове или кирилица.

    ЗАЩО ТРИТЕ АЗБУКИ: нашите срещи носят българско име (bg_name вече е минал),
    код на държавата (home_id) и латинско име в източника. Функцията приема
    и трите, за да може да се вика отвсякъде, без викащият да превежда.
    """
    a, b = kanon(dom), kanon(gost)
    if not a or not b or a == b:
        return None
    kl = tuple(sorted((a, b)))
    idx = pazar_index()
    nameren = [v for (p, x, y), v in idx.items()
               if (x, y) == kl and (pol is None or p is None or p == pol)]
    if len(nameren) != 1:
        # Нула = няма пазар. Повече от едно = мъжкият и женският мач на същите
        # две държави са отворени едновременно и полът не е казан. Мълчим.
        return None
    z = nameren[0]
    cd, cg = z["ceni"].get(a), z["ceni"].get(b)
    if cd is None or cg is None:
        return None
    pd, pg = bez_marzh(cd, cg)
    return {"dom": cd, "gost": cg, "p_dom": pd, "p_gost": pg,
            "marzh": round((veroyatnost(cd) or 0) + (veroyatnost(cg) or 0) - 1.0, 4),
            "liga": z["liga"], "sabitie": z["sabitie"], "start": z["start"]}


# ============================== СИТОТО
def targuvan_li(sr):
    """Има ли пазар за тази среща. Връща (може_ли, защо) — като ima_pazar().

    Приема речника, който vol_fixtures() връща: home/away (вече на кирилица),
    home_id/away_id (кодове), league и extra.vb (кошницата пол+възраст).
    """
    if not isinstance(sr, dict):
        return False, "не е среща"
    lg = str(sr.get("league") or "")
    ex = sr.get("extra") or {}
    vb = str(ex.get("vb") or "")
    pol = vb[:1] if vb[:1] in ("m", "w") else None
    # Първо цената: тя е доказателство, а не преценка.
    c = (cena(sr.get("home_id"), sr.get("away_id"), pol)
         or cena(sr.get("home"), sr.get("away"), pol))
    if c:
        return True, "цена"
    # После стълбицата: витрината отваря само 3 дни напред, а картата се готви
    # по-рано. Кошницата „юноши" реже втори път, независимо от името.
    if vb.endswith("-you"):
        return False, "юношески турнир"
    r = vol_rang(lg)
    if r >= VOL_PRAG:
        return True, "възрастен турнир (ранг " + str(r) + ")"
    return False, "няма пазар (ранг " + str(r) + ")"


def targuvani(srechti):
    """Отсява волейболните срещи, за които изобщо съществува пазар.

    ЗАЩО НЕ Е ПРОСТО ФИЛТЪР: 64 от 116-те волейболни карти бяха юношески
    световни първенства. Стаята работеше, но продаваше непродаваемо. Тази
    функция е разликата между „бот, който говори" и „бот, който може да бъде
    последван".
    """
    out = []
    for sr in srechti or []:
        ok, _ = targuvan_li(sr)
        if ok:
            out.append(sr)
    return out


def prichini(srechti):
    """{причина -> брой} за целия списък. За очи и за отчет, не за логика."""
    br = {}
    for sr in srechti or []:
        _, z = targuvan_li(sr)
        klyuch = z.split(" (")[0]
        br[klyuch] = br.get(klyuch, 0) + 1
    return br


def granica_na_vitrinata():
    """Докога напред витрината изобщо е отворила. None, ако мълчи.

    ЗАЩО Е ОТДЕЛНА: без нея „няма цена" и „още не е отворено" изглеждат
    еднакво — същият клас провал като „няма пазар" срещу „доставчикът е долу",
    заради който в predictor.py има pazarat_otgovarya(). Тук границата е
    измерима: най-далечният мач, който витрината показва.
    """
    idx = pazar_index()
    if not idx:
        return None
    return max((v.get("start") or 0) for v in idx.values()) or None


def proverka_v_prozoreca(srechti):
    """{турнир -> (срещи, с цена, ранг)} САМО за срещите вътре в прозореца.

    🔴 ТОВА Е ЕДИНСТВЕНОТО МЯСТО, КЪДЕТО СТЪЛБИЦАТА МОЖЕ ДА БЪДЕ ОБОРЕНА.
    Извън прозореца липсата на цена не значи нищо. Вътре в него значи всичко:
    ако турнирът има срещи, а витрината няма нито една, стълбицата греши.

    Измерено 19.08.2026, прозорец до 22.08 16:00 UTC:
        CEV EuroVolley 2026 | Women     15 срещи, 12 с цена   ранг 85  ✅
        FIVB Boys' U17 World Champ.     15 срещи,  0 с цена   ранг 10  ✅
        AVC Women Asian Continental      6 срещи,  0 с цена   ранг 66  ⚠
        NORCECA Women Continental        4 срещи,  0 с цена   ранг 66  ⚠
    Тоест континенталните първенства ОСТАВАТ ПРЕДПОЛОЖЕНИЕ: тази витрина не
    ги предлага. Не ги режем, защото една затворена врата не е всички врати
    (същата грешка вече е правена с волейбола при Pinnacle), но и не ги
    обявяваме за доказани. Който иска само доказаното: VOL_PRAG=76.
    """
    gr = granica_na_vitrinata()
    out = {}
    if not gr:
        return out
    for sr in srechti or []:
        t = _koga_ms(sr.get("when"))
        if t is None or t > gr:
            continue
        lg = str(sr.get("league") or "")
        vb = str((sr.get("extra") or {}).get("vb") or "")
        pol = vb[:1] if vb[:1] in ("m", "w") else None
        n, s, _r = out.get(lg, (0, 0, vol_rang(lg)))
        ima = cena(sr.get("home_id"), sr.get("away_id"), pol) is not None
        out[lg] = (n + 1, s + (1 if ima else 0), _r)
    return out


def _koga_ms(w):
    """„2026-08-21T11:00:00Z" -> милисекунди. None при каквото и да е друго."""
    if isinstance(w, (int, float)):
        return int(w)
    try:
        t = datetime.datetime.strptime(str(w), "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None
    return int(t.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)


# ============================== ЖИВОТО ПИТАНЕ (само за --zhivo)
def _vis(req):
    return ET.fromstring(_get(VIS + urllib.parse.quote(req, safe=""), "*/*"))


def fivb_srechti(d0, dni=14):
    """Нашите волейболни срещи от FIVB за прозорец от dni дни. Само за --zhivo.

    Повтаря това, което vol_fixtures() прави в predictor.py, за да може
    измерването да е независимо от него — не пипаме чужд файл, за да го мерим.
    """
    meta = {}
    for t in _vis('<Request Type="GetVolleyTournamentList" '
                  'Fields="No Title Name Gender"></Request>'):
        meta[str(t.get("No") or "")] = ((t.get("Title") or t.get("Name") or ""),
                                        str(t.get("Gender") or ""))
    d1 = d0 + datetime.timedelta(days=dni - 1)
    req = ('<Request Type="GetVolleyMatchList" Fields="No TeamAName TeamBName '
           'TeamACode TeamBCode DateTimeUtc Status NoTournament"><Filter FirstDate="'
           + d0.isoformat() + '" LastDate="' + d1.isoformat() + '"/></Request>')
    out = []
    for m in _vis(req):
        if str(m.get("Status") or "") != "1":
            continue
        tno = str(m.get("NoTournament") or "")
        tname, gender = meta.get(tno, ("Волейбол", ""))
        pol = "m" if gender == "0" else ("w" if gender == "1" else "")
        vb = (pol + ("-you" if _vazrast(_dumi(tname)) else "-sen")) if pol else ""
        out.append({"home": m.get("TeamAName"), "away": m.get("TeamBName"),
                    "home_id": m.get("TeamACode"), "away_id": m.get("TeamBCode"),
                    "league": tname, "when": m.get("DateTimeUtc"),
                    "extra": {"vb": vb}})
    return out


# ============================== ПРОВЕРКИТЕ
def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # --- същината на имената
    check("„Türkiye“ и „Turkey W“ са един отбор",
          kanon("Türkiye") == kanon("Turkey W") == "turkey")
    check("кодът TUR също е Турция", kanon("TUR") == "turkey")
    check("кирилицата също", kanon("Турция") == "turkey")
    check("„Czech Republic“ и „Czechia“ са един отбор",
          kanon("Czech Republic") == kanon("Czechia") == kanon("CZE") == "czech")
    check("„France (W)“ = „France“ = „FRA“ = „Франция“",
          kanon("France (W)") == kanon("France") == kanon("FRA")
          == kanon("Франция") == "france")
    check("„Dominican Republic“ не се бърка с чехите",
          kanon("Dominican Republic") == "dominican" != kanon("Czech Republic"))
    check("САЩ по трите начина",
          kanon("United States") == kanon("USA") == kanon("САЩ") == "usa")
    check("Босна не се разпада на „and“",
          kanon("Bosnia and Herzegovina") == "bosnia")
    check("празното име няма същина", kanon("") == "" and kanon(None) == "")
    check("непознат клуб оцелява като себе си",
          kanon("Sir Sicoma Monini Perugia") == "sirsicomamoniniperugia")

    # --- полът
    check("женската лига е женска", kanon_pol("Women's European Championship") == "w")
    check("мъжката е мъжка", kanon_pol("CEV EuroVolley 2026 | Men") == "m")
    check("„(W)“ в името стига", kanon_pol("France (W)", "Slovakia (W)") == "w")
    check("спорът мълчи", kanon_pol("Men's League", "France (W)") is None)
    check("без белег — без пол", kanon_pol("CEV EuroVolley 2026") is None)
    check("„Women“ НЕ се чете като „men“",
          kanon_pol("Women's European Volleyball Championship") == "w")

    # --- стълбицата, срещу ИСТИНСКИ имена от справочника
    check("EuroVolley е висок", vol_rang("CEV EuroVolley 2026 | Women") == 85)
    check("световното е по-високо от EuroVolley",
          vol_rang("FIVB Volleyball Men's World Championship 2025")
          > vol_rang("CEV EuroVolley 2026 | Women"))
    check("VNL е между тях",
          vol_rang("CEV EuroVolley 2026 | Men")
          < vol_rang("Men's Volleyball Nations League 2026")
          < vol_rang("FIVB Volleyball Women's World Championship 2025"))
    check("юношеското световно пада най-долу",
          vol_rang("FIVB Volleyball Boys' U17 World Championship 2026") == 10)
    check("Girls' U17 също",
          vol_rang("FIVB Volleyball Girls' U17 World Championship 2026") == 10)
    check("U-15 с тире също се хваща",
          vol_rang("II Central American U-15 Women - Nicaragua 2025") == 10)
    check("„Under 19“ също",
          vol_rang("CAVA Men's Under 19 Volleyball Championship 2025") == 10)
    check("U21 световното пада",
          vol_rang("FIVB Volleyball Men's U21 World Championship 2025") == 10)
    check("тестовият турнир е нула",
          vol_rang("VNL 2026 - MEN (TEST ONLY)") == 0
          and vol_rang("Test Poland Women 2025") == 0)
    check("зоналното НЕ се брои за континентално",
          vol_rang("CAVB Zone IV Men Nations Championship") == 30)
    check("NCVA Final Six е зонално", vol_rang("NCVA Men's Final Six 2026") == 30)
    check("континенталното държи над прага",
          vol_rang("NORCECA Women Continental Championship 2026") == 66)
    check("клубните първенства минават",
          vol_rang("Lega Pallavolo Serie A Femminile 2025/2026") >= VOL_PRAG
          and vol_rang("Men's League 2025 Poland") >= VOL_PRAG)
    check("Шампионската лига минава",
          vol_rang("CEV Champions League Volley") == 76)
    check("Купата на Италия минава", vol_rang("Men Coppa Italia 2026") == 52)
    check("многоспортовите игри падат под прага",
          vol_rang("20th Asian Games Aichi–Nagoya 2026 - Men") < VOL_PRAG)
    check("непознато име взима средното", 30 < vol_rang("Нещо съвсем ново") < 60)
    check("празно име е нула", vol_rang("") == 0 and vol_rang(None) == 0)

    # --- маржът
    _p = bez_marzh(1.111111, 5.75)
    check("маржът се маха и сборът става 1", abs(sum(_p) - 1.0) < 0.001)
    check("фаворитът си остава фаворит", _p[0] > _p[1])
    check("сбор под 1 не се пипа", bez_marzh(2.5, 2.5) == (None, None))
    check("абсурден сбор не се пипа", bez_marzh(1.05, 1.05) == (None, None))
    check("боклук не гърми",
          bez_marzh(None, 2.0) == (None, None) and veroyatnost("абв") is None)

    # --- индексът и цената, с ПОДХВЪРЛЕНИ данни (нула мрежа)
    _staro = _kesh.get("bov")
    _daleche = int((datetime.datetime.now(datetime.timezone.utc).timestamp()
                    + 2 * 86400) * 1000)
    _mina = int((datetime.datetime.now(datetime.timezone.utc).timestamp()
                 - 3600) * 1000)

    def _sab(op, ha, aa, ch, ca, start, live=False):
        return {"description": op, "startTime": start, "live": live,
                "competitors": [{"name": ha}, {"name": ch}],
                "displayGroups": [{"description": "Game Lines", "markets": [
                    {"description": "Moneyline", "period": {"description": "Match"},
                     "outcomes": [{"description": ha, "price": {"decimal": str(aa)}},
                                  {"description": ch, "price": {"decimal": str(ca)}}]}]}]}

    _kesh.pop("idx", None)
    _kesh["bov"] = [{"path": [{"description": "Women's European Volleyball Championship"}],
                     "events": [
                         _sab("France W vs Slovakia W", "France (W)", 1.111111,
                              "Slovakia (W)", 5.75, _daleche),
                         _sab("Turkey W vs Latvia W", "Turkey W", 1.02,
                              "Latvia (W)", 15.0, _daleche),
                         _sab("Zapochnal vs Vtori", "Poland (W)", 1.5,
                              "Italy (W)", 2.5, _mina),
                         _sab("Na zhivo vs Vtori", "Serbia (W)", 1.5,
                              "Austria (W)", 2.5, _daleche, live=True),
                     ]},
                    # 🔴 СЪЩИТЕ ДВЕ ДЪРЖАВИ, ДРУГ ПОЛ. Този запис стои тук само
                    # за да може проверката за пола ДА ПАДНЕ. Първата версия на
                    # самопроверката нямаше мъжки мач и „len(nameren) != 1"
                    # можеше да се смени с „not nameren", без нищо да почервенее
                    # — тоест проверката пазеше нещо, което не се изпитваше.
                    {"path": [{"description": "Men's European Volleyball Championship"}],
                     "events": [
                         _sab("France M vs Slovakia M", "France", 2.10,
                              "Slovakia", 1.72, _daleche),
                     ]},
                    # Затворена линия (1.001 / 11.00) и крайна, но ИСТИНСКА
                    # (1.014286 / 11.00). Първата трябва да падне, втората — не.
                    {"path": [{"description": "Women's European Volleyball Championship"}],
                     "events": [
                         _sab("Serbia W vs Bulgaria W", "Serbia (W)", 1.001,
                              "Bulgaria (W)", 11.0, _daleche),
                         _sab("Hungary W vs Poland W", "Hungary (W)", 11.0,
                              "Poland (W)", 1.014286, _daleche),
                     ]}]
    try:
        _i = pazar_index(force=False)
        check("индексът хвана само незапочналите и неживите", len(_i) == 4)
        check("затворената линия 1.001 НЕ влиза",
              cena("Сърбия", "България", "w") is None)
        check("крайната, но истинска линия ВЛИЗА",
              (cena("Унгария", "Полша", "w") or {}).get("gost") == 1.014286)
        _c = cena("Франция", "Словакия", "w")
        check("цената се намира по кирилица", _c is not None and _c["dom"] == 1.111111)
        check("обърнатата посока дава обърнати цени",
              (cena("Словакия", "Франция", "w") or {}).get("dom") == 5.75)
        check("кодовете също намират цената",
              (cena("FRA", "SVK", "w") or {}).get("gost") == 5.75)
        # Двата пола на едни и същи държави са отворени едновременно.
        check("без казан пол при два пола — МЪЛЧИ",
              cena("Франция", "Словакия") is None)
        check("казаният мъжки пол взима МЪЖКАТА цена",
              (cena("FRA", "SVK", "m") or {}).get("dom") == 2.10)
        check("казаният женски пол взима ЖЕНСКАТА цена",
              (cena("FRA", "SVK", "w") or {}).get("dom") == 1.111111)
        check("„Türkiye“ срещу „Turkey W“ се среща",
              (cena("Türkiye", "Latvia") or {}).get("dom") == 1.02)
        check("махнатият марж е близо до 1",
              abs(_c["p_dom"] + _c["p_gost"] - 1.0) < 0.001)
        check("маржът е положителен и малък", 0.0 < _c["marzh"] < 0.2)
        check("започналият мач няма цена", cena("Poland", "Italy") is None)
        check("живият мач няма цена", cena("Serbia", "Austria") is None)
        check("непознат мач няма цена", cena("Бразилия", "Куба") is None)
        check("същият отбор срещу себе си няма цена", cena("FRA", "FRA") is None)
        check("несъществуващият пол не взима чужда цена",
              cena("Türkiye", "Latvia", "m") is None)
        check("верният пол взима цената",
              cena("Türkiye", "Latvia", "w") is not None)

        # --- ситото върху подхвърлени срещи
        _sr = [
            {"home": "Франция", "away": "Словакия", "home_id": "FRA", "away_id": "SVK",
             "league": "CEV EuroVolley 2026 | Women", "extra": {"vb": "w-sen"}},
            {"home": "Бразилия", "away": "Куба", "home_id": "BRA", "away_id": "CUB",
             "league": "CEV EuroVolley 2026 | Men", "extra": {"vb": "m-sen"}},
            {"home": "Италия", "away": "Полша", "home_id": "ITA", "away_id": "POL",
             "league": "FIVB Volleyball Boys' U17 World Championship 2026",
             "extra": {"vb": "m-you"}},
            {"home": "Египет", "away": "Тунис", "home_id": "EGY", "away_id": "TUN",
             "league": "CAVB Zone IV Men Nations Championship", "extra": {"vb": "m-sen"}},
        ]
        _t = targuvani(_sr)
        check("ситото пуска двете възрастни", len(_t) == 2)
        check("юношеското не минава",
              all("U17" not in s["league"] for s in _t))
        check("зоналното не минава",
              all("Zone" not in s["league"] for s in _t))
        check("причината за цената е „цена“",
              targuvan_li(_sr[0])[1] == "цена")
        check("причината за втория е стълбицата",
              targuvan_li(_sr[1])[1].startswith("възрастен"))
        check("бройката по причини е пълна", sum(prichini(_sr).values()) == 4)
        check("боклук не е среща", targuvan_li(None) == (False, "не е среща"))
        check("празният списък не гърми", targuvani(None) == [] and targuvani([]) == [])
        # 🔴 Кошницата реже ВТОРИ ПЪТ. Ако утре някой юношески турнир се казва
        # само „NORCECA Continental Championship" без възраст в името, рангът
        # му ще е 66 и щеше да мине. Кошницата от FIVB не се лъже от името.
        _skrit = {"home": "Италия", "away": "Полша", "home_id": "ITA", "away_id": "POL",
                  "league": "NORCECA Women Continental Championship 2026",
                  "extra": {"vb": "w-you"}}
        check("скрито юношеско пада по кошницата, не по името",
              targuvan_li(_skrit) == (False, "юношески турнир")
              and vol_rang(_skrit["league"]) >= VOL_PRAG)

        # --- изпитът на стълбицата
        check("часът се чете от FIVB вида",
              _koga_ms("2026-08-21T11:00:00Z") == 1787310000000)
        check("боклук вместо час не гърми",
              _koga_ms("вчера") is None and _koga_ms(None) is None)
        check("границата на витрината е най-далечният мач",
              granica_na_vitrinata() == _daleche)
        _sr2 = [dict(_sr[0], when="2026-08-21T11:00:00Z"),
                dict(_sr[2], when="2026-08-21T11:00:00Z"),
                dict(_sr[1], when="2099-01-01T11:00:00Z")]
        _pv = proverka_v_prozoreca(_sr2)
        check("изпитът гледа само срещите в прозореца", len(_pv) == 2)
        check("EuroVolley минава изпита с цена",
              _pv["CEV EuroVolley 2026 | Women"][1] == 1)
        check("юношеското пада на изпита без цена",
              _pv["FIVB Volleyball Boys' U17 World Championship 2026"][1] == 0)
        check("без витрина няма изпит",
              proverka_v_prozoreca([]) == {})
    finally:
        _kesh.pop("idx", None)
        if _staro is None:
            _kesh.pop("bov", None)
        else:
            _kesh["bov"] = _staro

    check("нула мрежа в самопроверката", broi_zayavki() == 0)
    check("броят проверки е поне 70", ok >= 70)

    print("САМОПРОВЕРКА НА ВОЛЕЙБОЛА: " + str(ok) + " наред, "
          + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


def zhivo():
    """Истинско питане — за очи, не за автомат."""
    dnes = datetime.datetime.now(datetime.timezone.utc).date()

    idx = pazar_index()
    print("ВИТРИНАТА (една заявка)")
    print("   събития с пълна двойка цени: %d" % len(idx))
    _l = {}
    _far = 0
    for (p, _a, _b), v in idx.items():
        _l[(v["liga"], p)] = _l.get((v["liga"], p), 0) + 1
        _far = max(_far, v["start"] or 0)
    for (lg, p), n in sorted(_l.items(), key=lambda kv: -kv[1]):
        print("      %-52s пол:%s  %d" % (str(lg)[:52], p or "?", n))
    if _far:
        _d = datetime.datetime.fromtimestamp(_far / 1000.0, datetime.timezone.utc)
        print("   най-далечният мач: %s (+%d дни)"
              % (_d.strftime("%Y-%m-%d %H:%M"), (_d.date() - dnes).days))

    for dni, etiket in ((1, "ДНЕС"), (14, "14 ДНИ")):
        srechti = fivb_srechti(dnes, dni)
        ok = targuvani(srechti)
        # 🔴 ТУК ИМАШЕ МОЙ СОБСТВЕН ДЕФЕКТ (намерен и махнат 19.08.2026).
        # Първата версия броеше срещите с причина „цena“ — с ЛАТИНСКО „e“ в
        # средата на българска дума. Сравнението не хващаше нищо и числото
        # щеше да е вечна нула. Редът беше презаписан веднага отдолу, тоест
        # мълчаливо мъртъв код — същият клас, който вече е хапал Бейби Ленд.
        s_cena = sum(1 for s in srechti
                     if (cena(s.get("home_id"), s.get("away_id"),
                              (str((s.get("extra") or {}).get("vb") or "")[:1] or None))
                         is not None))
        euro = [s for s in srechti if "EuroVolley" in str(s.get("league") or "")]
        euro_ok = targuvani(euro)
        euro_cena = sum(1 for s in euro
                        if cena(s.get("home_id"), s.get("away_id"),
                                (str((s.get("extra") or {}).get("vb") or "")[:1]
                                 or None)) is not None)
        print("")
        print("%s (%s .. +%d дни)" % (etiket, dnes.isoformat(), dni - 1))
        print("   срещи от FIVB:      %d" % len(srechti))
        print("   оцеляват ситото:    %d  (%d%%)"
              % (len(ok), round(100.0 * len(ok) / max(1, len(srechti)))))
        print("   с ИЗМЕРЕНА цена:    %d" % s_cena)
        print("   EuroVolley:         %d, оцеляват %d, с цена %d"
              % (len(euro), len(euro_ok), euro_cena))
        pr = prichini(srechti)
        for k, n in sorted(pr.items(), key=lambda kv: -kv[1]):
            print("      %-28s %d" % (k, n))
        lg = {}
        for s in srechti:
            key = (str(s.get("league") or "")[:46], targuvan_li(s)[0])
            lg[key] = lg.get(key, 0) + 1
        for (name, keep), n in sorted(lg.items(), key=lambda kv: -kv[1]):
            print("      %s %-46s %d" % ("✅" if keep else "❌", name, n))

        if dni > 1:
            # Единственият честен изпит на стълбицата: вътре в прозореца на
            # витрината липсата на цена вече значи нещо.
            print("")
            print("   ИЗПИТ НА СТЪЛБИЦАТА (само срещи вътре в прозореца)")
            pv = proverka_v_prozoreca(srechti)
            for name, (n, s, r) in sorted(pv.items(), key=lambda kv: -kv[1][0]):
                znak = "✅" if (s > 0) == (r >= VOL_PRAG) else "⚠"
                print("      %s %-44s срещи %-3d с цена %-3d ранг %d"
                      % (znak, name[:44], n, s, r))
            print("      ⚠ = стълбицата казва едно, витрината — друго."
                  " Предположение, не доказателство.")
            # И двата прага, за да се вижда цената на строгостта.
            _strog = [s for s in srechti if vol_rang(str(s.get("league") or "")) >= 76
                      and not str((s.get("extra") or {}).get("vb") or "").endswith("-you")]
            print("   при праг 50 (сега): %d оцеляват · при праг 76 (само"
                  " доказаното ниво): %d" % (len(ok), len(_strog)))

    print("")
    print("заявки общо: %d" % broi_zayavki())
    return 0


if __name__ == "__main__":
    if "--zhivo" in sys.argv:
        sys.exit(zhivo())
    sys.exit(selftest())
