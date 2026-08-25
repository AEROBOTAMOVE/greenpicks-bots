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


def zalozhimo(liga, bucket=None):
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

    print("САМОПРОВЕРКА НА ЗАЛОЖИМОТО: %d наред, %d счупени" % (ok, len(bad)))
    for b in bad:
        print("   счупено: " + b)
    return ok, bad


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _ok, _bad = selftest()
    sys.exit(1 if _bad else 0)
