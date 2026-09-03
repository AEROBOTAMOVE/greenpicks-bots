# -*- coding: utf-8 -*-
"""ЗАЛОЖИМО ЛИ Е — единственото място, което решава дали прогнозата има пазар.

═══════════════════════════════════════════════════════════════════════════
ЗАЩО СЪЩЕСТВУВА (25.08.2026)
═══════════════════════════════════════════════════════════════════════════

Желязното правило на собственика, дословно:
    „ИСКАМ НАИСТИНА ДА НАТИСНЕШ НАД ВСИЧКИ ПРОГНОЗИ ДА ГИ ИМА В БУКМЕЙКЪРА."
    „НАЛИ ВСИЧКО ЗАЛОЗИ НЕЗАВИСИМО ОТ СПОРТА ГИ ИМА В БЕТ 365 — ИСКАМ ДА Е ТАКА."

Измерено на живо в дневника същия ден: **81 от 737 карти (11%) са юношески
турнири**, за които пазар НЕ СЪЩЕСТВУВА при никой букмейкър:

    FIVB Volleyball Girls' U17 World Championship 2026      64
    2026 NORCECA U17 Boys' Pan American Cup                  7
    Europe Youth Smash - Sweden 2026 · U19 Boys' Singles     4
    Europe Youth Smash · U15 Girls' / U15 Boys' Singles      4
    FIVB Volleyball Boys' U17 World Championship 2026        2

При волейбола това е **42% от всички карти**.

🔴 КАК Е МИНАВАЛО ДОСЕГА. В predictor.py има портиер `ima_pazar` — „карта без
пазар не излиза". Но волейболът е ИЗКЛЮЧЕН от него (19.08.2026), защото
никой източник не му дава цена и портиерът режеше всичките му карти.
През същата тази врата минават и юношеските.

Тоест изключението беше за ЦЕНАТА, а пропусна и ЗАЛОЖИМОСТТА. Две различни
неща: „не мога да проверя цената" не е „няма такъв пазар".

═══════════════════════════════════════════════════════════════════════════
🔴 КАПАНЪТ, КОЙТО ЩЕШЕ ДА УБИЕ ЦЕЛИЯ ТЕНИС
═══════════════════════════════════════════════════════════════════════════

В тениса турнирите се казват `M15 Arad`, `W15 Wanfercee-Baulet`, `M25 Lesa`,
`W35 Krakow`. Това са ПАРИЧНИ НИВА ($15 000, $25 000, $35 000), НЕ ВЪЗРАСТИ.
Ловене на „число след буква" би изтрило целия ITF — а ITF СЕ ТЪРГУВА:
измерено при Pinnacle на 25.08, 29 от 54 тенис мача са именно ITF.

Затова възрастта се лови САМО като „u" + цифри, на граница на дума, и никога
като „m"/„w" + цифри. Проверено срещу ВСИЧКИТЕ 96 различни имена на лиги в
живия дневник — нула невинни жертви.
"""

import io
import os
import sys

# Думите за юношески турнир. Търсят се като ЦЕЛИ ДУМИ, не като подниз:
# „boys" не бива да се хване вътре в друга дума, а кирилицата не се цепи от
# латинските граници на думата — затова цепенето е ръчно, по неписмени знаци.
YUNOSHESKI_DUMI = ("boys", "girls", "youth", "junior", "juniors",
                   "cadet", "cadets", "юноши", "юношески", "девойки")

# Възрастовите групи: „u" и цифри. САМО „u" — „m15"/„w35" са пари, не години.
VAZRAST_BUKVA = "u"
VAZRAST_MIN, VAZRAST_MAX = 10, 23

# ────────────────────────────────────────────── ЧЕРВЕНИЯТ СПИСЪК (02.09.2026)
# Раздел V „RED / MANUAL ONLY OR BLOCKED" от каталога на собственика. Всяка
# редица се търси като ЦЯЛА ДУМА през същия `_dumi`, който ловеше юношите.
#
# Измерено на живия дневник (1225 карти): тези четири режат НУЛА днес.
# Но кошницата на Pinnacle за хокея, питана на живо на 02.09, съдържа
# „World - Club Friendlies" — тоест правилото ще потрябва още щом отворим
# спорт, който взима мачовете си от Pinnacle.
PRIYATELSKI_DUMI = ("friendly", "friendlies", "exhibition", "exhibitions",
                    "приятелски", "приятелска", "приятелско", "контроли")

# 🔴 „ii" и „b" НЕ влизат тук. „Liga II" на Румъния е ИСТИНСКА втора
# дивизия и е в каталога (RECURRING | Romania). Самотните белези се търсят
# само в ИМЕ НА ОТБОР, от `rezerven_otbor` по-долу.
REZERVNI_DUMI = ("reserves", "reserve", "reserv", "резерви", "резервен",
                 "reservas", "reserva")

VIRTUALNI_DUMI = ("virtual", "virtuals", "виртуален", "виртуални",
                  "виртуална", "sim", "simulated", "simulation")

# 🔴 „fifa" НЕ влиза — „FIFA Club World Cup" е истински турнир.
# 🔴 „cyber" НЕ влиза — „Moscow Cyber Games" е истински турнир по CS2 и е в
#    живия ни дневник с 2 карти. Ловят се само буквените „e"-простaвки.
SIMULACII_DUMI = ("esoccer", "ebasketball", "etennis", "ehockey",
                  "efootball", "ecricket", "ebasket", "evolleyball")

# Белезите за резервен отбор — САМО в име на ОТБОР, никога в лига.
#
# 🔴 ТУК ИМАШЕ „b", „ii", „2", „c" И ГИ МАХНАХ (02.09.2026), защото ги
# измерих срещу ВСИЧКИТЕ 2052 различни имена в живия дневник:
#
#     «Bonzi B.» «Baker B.» «Sanchez Martinez B.»  тенисисти с ИНИЦИАЛ
#     «Broom C.» «Spyrou C.»                       същото
#     «Manta F.C.»                                 „F.C." се цепи на „f"+„c"
#     «Willem II» «Juan Pablo II»                  ИСТИНСКИ клубове
#
#   8 невинни имена, 11 убити карти — срещу НУЛА истински резервни състава
#   в 1225 карти. Тоест правилото струваше повече, отколкото хващаше.
#
# „ii" е особено коварно: то Е стандартният белег за резерви в немските и
# нидерландските извори („Bayern Munich II"), но е и част от истински имена
# („Willem II"). По само името двете НЕ СЕ РАЗЛИЧАВАТ. Затова остават само
# явните думи; ако някой ден изворът почне да връща „Bayern Munich II",
# ще се хване тогава, с доказателство, а не предварително.
REZERVEN_OTBOR_BELEG = ("reserves", "reserve", "reserv", "резерви",
                        "резервен", "reservas", "reserva")

# Дребният тенис на маса. ИЗКЛЮЧЕН по подразбиране и това е нарочно:
# каталогът го слага в червено („Continuous minor table-tennis events"), но
# собственикът има стоящо нареждане „нищо да не мълчи", а точно тези две
# лиги са ЕДИНСТВЕНИЯТ тенис на маса с измерим коефициент (Smarkets/Kambi).
# Цената, измерена на живия дневник: 26 карти (Czech Liga Pro 16, TT Elite 10).
DREBEN_TT_PARCHETA = ("liga pro", "tt cup", "tt star", "tt elite",
                      "setka cup", "setka", "challenger series tt")
# 🔴 ПУСНАТ ПО ПОДРАЗБИРАНЕ. Първата ми версия беше на "0" и режеше 26 живи
# карти по мое решение — а стоящото нареждане на собственика е „нищо да не
# мълчи". Каталогът дава тези лиги в червено, но това е ПРЕПОРЪКА на
# каталога, не мое право да я приложа мълчаливо. Затова правилото стои
# готово и се включва с PREDICT_DREBEN_TT_REJI=1, когато собственикът каже.
DREBEN_TT_KLYUCH = "PREDICT_DREBEN_TT_REJI"


def ot_sredata(klyuch, po_podrazbirane="0"):
    """Чете ключ от средата и го превръща в да/не. Едно място, за да може
    самопроверката да мине по СЪЩИЯ път, вместо да търси името във файла.

    🔴 Първата ми проверка тук четеше собствения си файл и питаше „има ли
    в него низа «PREDICT_DREBEN_TT_REJI»“ — а самата проверка Е този низ.
    Тоест тя намираше себе си и минаваше винаги. Мутационният тест не можа
    дори да я мутира: низът се срещаше два пъти. Затова четенето е тук.
    """
    return (os.environ.get(klyuch) or po_podrazbirane).strip() in (
        "1", "true", "yes", "да")


DREBEN_TT_REJI = ot_sredata(DREBEN_TT_KLYUCH, "0")

# Спортове, за които изобщо се пита. Празно значи „всички".
# Празно е нарочно: правилото на собственика е „НЕЗАВИСИМО ОТ СПОРТА".
SAMO_ZA = tuple(x for x in
                (os.environ.get("PREDICT_ZALOZHIMO_SPORTOVE") or "").split(",")
                if x.strip())

# Изключено ли е правилото. Оставено през среда, за да може да се спре бързо,
# ако утре се окаже, че реже нещо живо — но по подразбиране РАБОТИ.
VKLYUCHENO = (os.environ.get("PREDICT_ZALOZHIMO") or "1").strip() not in (
    "0", "false", "no", "не")


def _dumi(tekst):
    """Думите в текста, с малки букви. Цепи по всичко, което не е буква/цифра.

    Ръчно, а не с регулярен израз: `\\w` в Python хваща кирилицата, но
    апострофите се пишат по два начина („Boys'" и „Boys’") и точно те делят
    думата. Тук и двата са разделители, тоест „Boys’" дава „boys".
    """
    out, tek = [], []
    for ch in str(tekst or ""):
        if ch.isalnum():
            tek.append(ch.lower())
        elif tek:
            out.append("".join(tek))
            tek = []
    if tek:
        out.append("".join(tek))
    return out


def vazrastova_grupa(duma):
    """Възрастта от дума като „u17". None, ако не е такава.

    🔴 САМО „u". Ако това стане по-хлабаво, „m15" и „w35" — паричните нива в
    тениса — ще започнат да се четат като възрасти и целият ITF ще изчезне.
    """
    d = str(duma or "").lower()
    if len(d) < 3 or d[0] != VAZRAST_BUKVA:
        return None
    ost = d[1:]
    if not ost.isdigit():
        return None
    try:
        n = int(ost)
    except ValueError:
        return None
    return n if VAZRAST_MIN <= n <= VAZRAST_MAX else None


def yunosheski(liga):
    """(юношески_ли, коя дума го издава). Празна дума значи „не"."""
    for d in _dumi(liga):
        if d in YUNOSHESKI_DUMI:
            return (True, d)
        v = vazrastova_grupa(d)
        if v is not None:
            return (True, d)
    return (False, "")


def rezerven_otbor(ime):
    """(резервен_ли, кой белег). САМО за ИМЕ НА ОТБОР, никога за лига.

    🔴 Защо е отделно от лигата: „Liga II" на Румъния е истинска дивизия и е
    в каталога, а „Real Madrid B" е резервен състав. Един и същи белег значи
    две различни неща на двете места, затова се питат на две различни места.

    Белегът трябва да е ПОСЛЕДНАТА дума и името да има поне още една дума —
    инак отбор на име „B" (какъвто няма) или „Ювентус" биха паднали.
    """
    d = _dumi(ime)
    if len(d) < 2:
        return (False, "")
    if d[-1] in REZERVEN_OTBOR_BELEG:
        return (True, d[-1])
    return (False, "")


def cherven(liga):
    """(в_червено_ли, причина). Раздел V от каталога на собственика."""
    d = set(_dumi(liga))
    for dumi_nabor, prichina in (
            (PRIYATELSKI_DUMI, "приятелски/показен мач"),
            (REZERVNI_DUMI, "резервен състав"),
            (VIRTUALNI_DUMI, "виртуален спорт (не е истински мач)"),
            (SIMULACII_DUMI, "симулация, не истински спорт")):
        obshto = d & set(dumi_nabor)
        if obshto:
            return (True, prichina + " (" + sorted(obshto)[0] + ")")
    if DREBEN_TT_REJI:
        nisko = " ".join(_dumi(liga))
        for parche in DREBEN_TT_PARCHETA:
            if parche in nisko:
                return (True, "дребен непрекъснат тенис на маса ("
                        + parche + ") — PREDICT_DREBEN_TT_REJI=0 го връща")
    return (False, "")


def zalozhimo(liga, bucket=None, otbori=()):
    """(заложимо_ли, причина). Причината е празна, когато е заложимо.

    Пита се ПРЕДИ да се търси цена — това е въпрос за СЪЩЕСТВУВАНЕТО на
    пазара, не за достъпа до него. Турнир при момичета до 17 години няма
    пазар при никой букмейкър, независимо колко източника попитаме.
    """
    if not VKLYUCHENO:
        return (True, "")
    if SAMO_ZA and str(bucket or "") not in SAMO_ZA:
        return (True, "")
    yu, duma = yunosheski(liga)
    if yu:
        return (False, "юношески турнир (" + duma + ") — няма такъв пазар")
    ch, prichina = cherven(liga)
    if ch:
        return (False, prichina)
    for ot in (otbori or ()):
        rez, beleg = rezerven_otbor(ot)
        if rez:
            return (False, "резервен отбор (" + str(ot) + " → «" + beleg
                    + "») — каталогът го дава в червено")
    return (True, "")


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # ---------------------------------------------- цепенето на думи
    check("цепи по интервал", _dumi("Men's Singles") == ["men", "s", "singles"])
    check("правият апостроф е разделител", "boys" in _dumi("Boys' Singles"))
    # 🔴 И КРИВИЯТ АПОСТРОФ. Живите имена ползват „Boys’" с типографски знак;
    # ловене само на правия би пропуснало NORCECA U17 Boys’ Pan American Cup.
    check("кривият апостроф е разделител", "boys" in _dumi("Boys’ Pan American"))
    check("тирето е разделител", _dumi("Europe Smash - Sweden")[:3] == ["europe", "smash", "sweden"])
    check("кирилицата оцелява", "юноши" in _dumi("Купа за юноши"))
    check("празното дава празно", _dumi("") == [] and _dumi(None) == [])

    # ---------------------------------------------- възрастта
    check("u17 е възраст", vazrastova_grupa("u17") == 17)
    check("u15 е възраст", vazrastova_grupa("u15") == 15)
    check("U19 с главна буква също", vazrastova_grupa("U19") == 19)
    # 🔴 НАЙ-ВАЖНИТЕ ЧЕТИРИ ПРОВЕРКИ В ФАЙЛА. Тези имена са ПАРИЧНИ НИВА в
    # тениса, не възрасти. Хванат ли се, целият ITF изчезва — а той се търгува
    # (29 от 54 тенис мача при Pinnacle, мерено 25.08.2026).
    check("m15 НЕ е възраст", vazrastova_grupa("m15") is None)
    check("w15 НЕ е възраст", vazrastova_grupa("w15") is None)
    check("m25 НЕ е възраст", vazrastova_grupa("m25") is None)
    check("w35 НЕ е възраст", vazrastova_grupa("w35") is None)
    check("u99 е извън разумното", vazrastova_grupa("u99") is None)
    check("u5 е извън разумното", vazrastova_grupa("u5") is None)
    check("голото u не е възраст", vazrastova_grupa("u") is None)
    check("ua не е възраст", vazrastova_grupa("ua") is None)
    check("боклук не гърми", vazrastova_grupa(None) is None)

    # ---------------------------------------------- юношеските
    for _l in ("FIVB Volleyball Girls' U17 World Championship 2026",
               "2026 NORCECA U17 Boys’ Pan American Cup",
               "Europe Youth Smash - Sweden 2026 · U19 Boys' Singles",
               "Europe Youth Smash - Sweden 2026 · U15 Girls' Singles",
               "FIVB Volleyball Boys' U17 World Championship 2026"):
        check("юношески: " + _l[:32], yunosheski(_l)[0])

    # 🔴 И ДЕВЕТТЕ, КОИТО НЕ БИВА ДА СЕ ПИПАТ. Взети са дословно от живия
    # дневник, за да не е проверката теоретична.
    for _l in ("ECVA Senior Men’s Volleyball Championship 2026",
               "ECVA Senior Women’s Volleyball Championship 2026",
               "19th Men Pan American Cup 2026",
               "NORCECA Women Continental Championship 2026",
               "CEV EuroVolley 2026 | Women",
               "M15 Arad (Romania) · ITF",
               "W15 Wanfercee-Baulet (Belgium) · ITF",
               "M25 Lesa (Italy) · ITF",
               "W35 Krakow (Poland) · ITF",
               "WTT Champions Yokohama 2026 · Women's Singles",
               "Europe Smash - Sweden 2026 · Men's Singles",
               "Cincinnati Open · ATP",
               "Kingston 2 (Jamaica) - Qualification · Challenger",
               "МЛБ", "WNBA", "MLS"):
        check("НЕ е юношески: " + _l[:32], not yunosheski(_l)[0])

    # 🔴 ЦЯЛА ДУМА, НЕ НАЧАЛО НА ДУМА. Мутация оцеля с търсене по първите три
    # букви — и това е ИСТИНСКА опасност, не теоретична:
    #     „cad" би хванало Cádiz (Ла Лига)
    #     „you" би хванало Youngstown (американски университетски отбор)
    #     „jun" би хванало Junction City
    # Същият капан вече ни е ухапвал на друг проект: голият ключ краде по
    # НАЧАЛО НА ДУМА, а не по цяла дума.
    for _nevinen in ("Cadiz", "Cádiz CF", "Youngstown State", "Junction City",
                     "Giroud Cup", "Juno League", "Boysen Trophy"):
        check("невинен: " + _nevinen, not yunosheski(_nevinen)[0])

    # 🔴 И ЕДИН СЛУЧАЙ, КОЙТО ОСТАВА ЗНАЕН И НЕРЕШЕН: швейцарският клуб
    # „BSC Young Boys" носи думата „Boys" в името си. Тук правилото гледа
    # САМО името на ЛИГАТА, не на отборите, затова днес е безопасно. Приложи
    # ли се някога върху имена на отбори, Young Boys ще бъде блокиран
    # несправедливо. Записано, за да не се открива втори път.
    check("правилото гледа лигата, не отбора",
          zalozhimo("Шампионска лига", "football")[0])

    # ---------------------------------------------- присъдата
    _z, _p = zalozhimo("FIVB Volleyball Girls' U17 World Championship 2026",
                       "volleyball")
    check("юношеският НЕ е заложим", not _z)
    check("причината назовава думата", "u17" in _p or "girls" in _p)
    check("мъжкият е заложим", zalozhimo("ECVA Senior Men’s Volleyball", "volleyball")[0])
    check("ITF е заложим", zalozhimo("M15 Arad (Romania) · ITF", "tennis")[0])
    check("заложимият няма причина", zalozhimo("WNBA", "basketball")[1] == "")
    check("празната лига е заложима", zalozhimo("", "football")[0])
    check("None не гърми", zalozhimo(None, None)[0])

    # 🔴 ПРАВИЛОТО ВАЖИ ЗА ВСИЧКИ СПОРТОВЕ. Собственикът: „НЕЗАВИСИМО ОТ
    # СПОРТА". Празният списък SAMO_ZA е точно това и се заключва тук.
    check("правилото не е стеснено до един спорт", SAMO_ZA == ())
    check("правилото е включено по подразбиране", VKLYUCHENO is True)
    for _b in ("volleyball", "tabletennis", "tennis", "football", None):
        check("важи и за " + str(_b),
              not zalozhimo("Something U17 Boys' Cup", _b)[0])

    # ══════════════════════════ ЧЕРВЕНИЯТ СПИСЪК (раздел V от каталога)
    #
    # 🔴 ИМЕНАТА СА ИЗПИСАНИ ТУК ДОСЛОВНО, а не взети от списъците. Ако бяха
    # взети оттам, махането на дума от списъка щеше да мине незабелязано —
    # проверката щеше да пита самата себе си. Днес точно такава проверка
    # пропусна мутация в друг модул, затова тук е написана наопаки.
    for _lg, _kakvo in (
            ("Club Friendlies", "приятелски"),
            ("World - Club Friendlies", "приятелски с представка"),
            ("International Friendlies", "международни приятелски"),
            ("Приятелски мачове", "приятелски на кирилица"),
            ("Exhibition Match", "показен мач"),
            ("Bundesliga II Reserves", "резерви в името на лигата"),
            ("Virtual Football League", "виртуален"),
            ("eSoccer Battle - 8 mins play", "симулиран футбол"),
            ("FIFA 26 Esoccer Live Arena", "симулация с истинска марка"),
            ("eBasketball H2H GG League", "симулиран баскетбол")):
        check("червено: " + _kakvo + " (" + _lg + ")", not zalozhimo(_lg)[0])

    # И ОБРАТНАТА ПОСОКА — истинските имена, които съдържат опасна сричка.
    # Всяко е ВИДЯНО: „Liga II" е в каталога, „Moscow Cyber Games" е в живия
    # ни дневник с 2 карти, „Virtus" е клуб, „FIFA Club World Cup" е турнир.
    for _lg, _zashto in (
            ("Liga II", "истинска румънска втора дивизия"),
            ("Romania - Liga II", "същата, с представка"),
            ("FIFA Club World Cup", "истински турнир с марката FIFA"),
            ("CS2 · Moscow Cyber Games Qualifier", "истински турнир по CS2"),
            ("Virtus Bologna - Olimpia Milano", "клуб, не «virtual»"),
            ("Germany - Bundesliga", "истинска лига"),
            ("France - Division 1", "истинска лига"),
            ("Russia - Kontinental Hockey League", "истинска лига"),
            ("CEV EuroVolley 2026 | Women", "истинско първенство"),
            ("M15 Coral Gables", "ITF — «coral» не е забранена тук")):
        check("НЕ реже невинното: " + _zashto + " (" + _lg + ")",
              zalozhimo(_lg)[0])

    # ── резервните отбори: белегът важи в ОТБОР, никога в ЛИГА
    check("резервен отбор пада", not zalozhimo(
        "La Liga", None, ("Real Madrid Reserves", "Getafe"))[0])
    check("резервен отбор пада и като втори", not zalozhimo(
        "La Liga", None, ("Getafe", "Barcelona Reserve"))[0])
    check("истинските отбори минават",
          zalozhimo("La Liga", None, ("Real Madrid", "Getafe"))[0])
    check("без списък отбори нищо не се променя", zalozhimo("La Liga")[0])
    check("едносрична дума не е белег за резерва",
          rezerven_otbor("B") == (False, ""))
    check("белегът трябва да е ПОСЛЕДЕН",
          rezerven_otbor("Reserve Team Sofia") == (False, ""))

    # 🔴 ОСЕМТЕ НЕВИННИ. Всяко от тези имена е ВИДЯНО в живия дневник и
    # всяко падаше, докато белезите бяха самотни букви и римски цифри.
    # Стоят тук поименно, за да не се върнат никога тихо.
    for _im in ("Bonzi B.", "Baker B.", "Broom C.", "Spyrou C.",
                "Sanchez Martinez B.", "Manta F.C.", "Willem II",
                "Juan Pablo II", "Milan II", "Bayern Munich II"):
        check("невинно име не е резерва: " + _im,
              rezerven_otbor(_im) == (False, ""))
    check("самотните белези НЕ са в списъка",
          not ({"b", "c", "ii", "2"} & set(REZERVEN_OTBOR_BELEG)))

    # ── дребният тенис на маса: ПУСНАТ по подразбиране, ключът го реже
    #
    # 🔴 Тази двойка е тук, защото първата ми версия имаше обратното
    # подразбиране и режеше 26 живи карти по МОЕ решение. Каталогът е
    # препоръка; кой да мълчи решава собственикът.
    check("дребният тенис на маса МИНАВА по подразбиране",
          zalozhimo("Czech Liga Pro")[0] and zalozhimo("TT Elite Series")[0])
    check("правилото за дребния ТТ е ИЗКЛЮЧЕНО по подразбиране",
          DREBEN_TT_REJI is False)
    _st_tt = DREBEN_TT_REJI
    try:
        globals()["DREBEN_TT_REJI"] = True
        check("с включен ключ дребният ТТ пада",
              not zalozhimo("Czech Liga Pro")[0]
              and not zalozhimo("Setka Cup")[0])
        check("и тогава WTT пак минава",
              zalozhimo("WTT Champions Yokohama 2026 · Men's Singles")[0])
    finally:
        globals()["DREBEN_TT_REJI"] = _st_tt
    check("ключът е върнат както беше", DREBEN_TT_REJI is _st_tt)

    # ── ПЪТЯТ ПРЕЗ СРЕДАТА. Всичко горе подхвърля глобалната; ако кодът
    # четеше друго име на ключ, нито една проверка нямаше да усети. Затова
    # тук се чете САМИЯТ файл и се проверява, че имената съвпадат.
    _stara = os.environ.get(DREBEN_TT_KLYUCH)
    try:
        os.environ[DREBEN_TT_KLYUCH] = "1"
        check("средата наистина се чете (ключът вдига правилото)",
              ot_sredata(DREBEN_TT_KLYUCH, "0") is True)
        os.environ[DREBEN_TT_KLYUCH] = "0"
        check("и наистина се сваля", ot_sredata(DREBEN_TT_KLYUCH, "0") is False)
        os.environ.pop(DREBEN_TT_KLYUCH, None)
        check("без ключ важи подразбирането",
              ot_sredata(DREBEN_TT_KLYUCH, "0") is False)
        check("а подразбиране «1» дава обратното",
              ot_sredata(DREBEN_TT_KLYUCH, "1") is True)
        check("непознат ключ не гърми и дава подразбирането",
              ot_sredata("NYAMA_TAKAV_KLYUCH_12345", "0") is False)
    finally:
        if _stara is None:
            os.environ.pop(DREBEN_TT_KLYUCH, None)
        else:
            os.environ[DREBEN_TT_KLYUCH] = _stara
    check("средата е върната както беше",
          os.environ.get(DREBEN_TT_KLYUCH) == _stara)

    # 🔴 КРЪСТОСАНАТА ПРОВЕРКА. Всичко горе вика ПРОМЕНЛИВАТА, значи ключът
    # можеше да се преименува, yml да спре да го подава и тестът да е зелен.
    # Мутация M8 точно това направи и ОЦЕЛЯ. Тук се пита работният файл: той
    # съдържа ли ТОЧНО това име. Преименува ли се едното, гърми.
    _yml = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        ".github", "workflows", "predict.yml")
    try:
        _txt = open(_yml, encoding="utf-8-sig").read()
    except (OSError, UnicodeDecodeError):
        _txt = ""
    if _txt:
        check("работният файл подава ключа (" + DREBEN_TT_KLYUCH + ")",
              (DREBEN_TT_KLYUCH + ":") in _txt)
        check("и подразбирането в него е «не режи»",
              ("vars." + DREBEN_TT_KLYUCH + " || '0'") in _txt)

    # ── и списъците да не се изпразнят тихо
    check("има думи за приятелски", len(PRIYATELSKI_DUMI) >= 6)
    check("има думи за резерви", len(REZERVNI_DUMI) >= 4)
    check("има думи за виртуални", len(VIRTUALNI_DUMI) >= 4)
    check("има думи за симулации", len(SIMULACII_DUMI) >= 5)
    check("«fifa» НЕ е в думите за симулация — истински турнир",
          "fifa" not in SIMULACII_DUMI)
    check("«cyber» НЕ е в думите за симулация — истински турнир",
          "cyber" not in SIMULACII_DUMI)
    check("«ii» НЕ е в думите за резерви — Liga II е истинска",
          "ii" not in REZERVNI_DUMI)

    print("САМОПРОВЕРКА НА ЗАЛОЖИМОТО: %d наред, %d счупени" % (ok, len(bad)))
    for b in bad:
        print("   счупено: " + b)
    return ok, bad


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _ok, _bad = selftest()
    sys.exit(1 if _bad else 0)
