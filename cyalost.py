# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ЦЯЛОСТ 🧬

Един въпрос: ВСИЧКО ЛИ Е ТУК, което трябва да е тук?

ЗАЩО СЪЩЕСТВУВА — заради дефект, който се случи и НЕ гръмна
На 21.08.2026 наложих патч, построен върху копие на хранилището отпреди един
пазач. Патчът мълчаливо ВЪРНА НАЗАД и функцията `slyapa_karta`, и всичките ѝ
проверки. Резултат: 790 зелени самопроверки, а една защита я НЯМАШЕ.

Нито един тест не можеше да го хване — тестовете бяха изтрити заедно с нея.
Открих го случайно, като сверявах живия файл срещу списък в главата си.

Тоест: самопроверката пази ПОВЕДЕНИЕТО на кода, който е налице. Никой не
пазеше самото НАЛИЧИЕ. Този файл е точно това.

КАК РАБОТИ
Държи списък от неща, които ТРЯБВА да съществуват, и проверява, че ги има.
Не гледа какво правят — за това си има самопроверки. Гледа дали ги има.

Разборът е през `ast`, не през търсене на текст: три пъти за един ден се
хванах с игла, която стоеше в собствения ми коментар до проверката, и тя
минаваше върху счупен файл. Коментарите не лъжат разбора.

  python cyalost.py            — проверява и печата
  python cyalost.py --selftest — проверява и себе си
"""
import ast
import io
import os
import sys

TUK = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════ КАКВО ТРЯБВА ДА Е ТУК
#
# Всеки ред е нещо, което е било СЧУПЕНО или ЗАГУБЕНО веднъж. Списъкът не е
# опис на кода — той е списък от белези. Затова расте само когато нещо ни
# ухапе, а не когато добавим функция.
ZADALZHITELNI = {
    # ── ЗАЛОЖИМОСТТА (25.08.2026). Собственикът: „ЮНОШИ НЕ ИСКАМЕ."
    # 81 от 737 карти бяха юношески турнири, при волейбола 42%. Изчезне ли
    # това, те се връщат тихо — портиерът за цена не ги лови по име.
    "zalozhimo.py": [
        ("zalozhimo", "юношески турнир не излиза, независимо от спорта",
         "25.08.2026 — блокира 81 карти в 6 лиги, нула невинни от 96 проверени"),
        ("yunosheski", "разпознаването по ЦЯЛА дума, не по начало",
         "25.08.2026 — „cad\" би хванало Cádiz, „you\" би хванало Youngstown"),
        ("vazrastova_grupa", "възраст САМО от „u\"+цифри",
         "25.08.2026 — M15/W15/M25/W35 са ПАРИЧНИ нива; хванат ли се, ITF умира"),
    ],
    # ── ВОЛЕЙБОЛНАТА ЦЕНА (25.08.2026). Заключалката беше азбуката:
    # „Унгария" никога не среща „Hungary". 0 от 5 станаха 5 от 5.
    "pin_volei.py": [
        ("cena", "цена за волейболна карта по НАШИТЕ имена", "25.08.2026"),
        ("index", "указателят име→цена, строен веднъж", "25.08.2026"),
        ("_index_ili_vzemi", "няма подадени данни → ВЗИМА ГИ, не мълчи",
         "25.08.2026 — празният указател правеше всяко викане да връща None"),
        ("izvor_zhiv", "разлика между „няма пазар\" и „не ме пускат\"",
         "25.08.2026 — Bovada връща HTTP 200 с празно тяло при лимит"),
    ],
    # ── ПУСКАЧЪТ (25.08.2026). Осем модула с ~460 проверки не се пускаха от
    # нито един workflow. Изчезне ли този файл, покритието пада тихо обратно.
    "vsichki_testove.py": [
        ("moduli", "намира модулите САМ по диска, за да не остарее списък",
         "25.08.2026"),
        ("razcheti", "чете сметката по ЧИСЛАТА, не по думите",
         "25.08.2026 — matches_bot пише „PASS\" и когато има паднали"),
        ("pusni", "всеки модул в СВОЙ процес — един паднал не отнася другите",
         "25.08.2026"),
    ],
    # ── СЪГЛАСИЕТО (25.08.2026). Пазарът се оказа по-точен от модела ни:
    # Брайер наш 0.2405 срещу пазарен 0.2128, и в двете половини на дневника.
    # Там, където сме по-смели от него, сбъдваемостта пада на 34% при обявени
    # 57%. Този файл смесва двете числа и с това вади парите от −17.7% на
    # −8.1%. Изчезне ли, ботът тихо се връща към по-лошото число.
    # 🔴 НЕ Е в NE_BIVA_MARTVI, докато predictor.py не го вика — списъкът за
    # мъртви щеше да гърми за файл, който още чака да бъде свързан.
    "sglasie.py": [
        ("smesi", "числото на картата: нашето, претеглено с пазарното",
         "25.08.2026 — без пазар връща нашето НЕПОКЪТНАТО (340 от 728 карти)"),
        ("obrasta_li", "сместа сменя ли страната на избора",
         "25.08.2026 — тук се печелят парите: 34% познати стават 66%"),
        ("sglasni_li", "разликата с пазара, СЪС ЗНАК", "25.08.2026"),
        ("duma", "редът на картата — факт, без име на букмейкър", "25.08.2026"),
    ],
    # ── ПАЗАЧЪТ (25.08.2026). Оценителят гърмя 33 часа и НИКОЙ не разбра.
    # Здравният преглед през това време пишеше „0 червени", защото питаше
    # общия списък на рънoвете, а рутерът го залива (30 рънa = 1.8 часа).
    # Пазачът е единственото нещо, чиято работа е да ЗАБЕЛЯЗВА мълчанието —
    # изчезне ли някоя от тези функции, ботът пак може да умре тихо.
    "pazach.py": [
        ("kade_pishe", "тревогата отива в работната група, не в публичния канал",
         "25.08.2026 — и всяка стойност се чисти ПООТДЕЛНО: празни интервали"
         " печелеха избора и заглушаваха тревогата"),
        ("runove_na", "пита ПО WORKFLOW, не общия списък",
         "25.08.2026 — общият списък покрива 1.8 ч и провалът не влиза в него"),
        ("period_min", "прагът се смята от cron-а, не се забива на ръка",
         "25.08.2026 — забит праг остарява в деня, в който сменят разписанието"),
        ("dopusk_min", "допустимото мълчание за всеки workflow", "25.08.2026"),
        ("sadi", "ЧЕТИРИ състояния, не две — има и „не знам\"",
         "25.08.2026 — предишният пазач знаеше само наред/червено"),
        ("obhod", "минава през всички важни workflow-и", "25.08.2026"),
        ("kazvai_li", "почивка между еднакви тревоги",
         "25.08.2026 — пазач, който повтаря, се научава да бъде пренебрегван"),
        ("tekst_trevoga", "съобщението до собственика", "25.08.2026"),
        # ── МЪЛЧАНИЕТО НА ПРОДУКТА (25.08.2026). Зелен рън + празна стая е
        # авария, която никой друг пазач не вижда: картата може да се изхвърли
        # мълчаливо (забранена дума, капнал източник), а рънът да остане зелен.
        ("posledna_karta", "кога е излязла последната карта наистина",
         "25.08.2026 — прагът 22 ч е измерен на 180 паузи, максимумът е 20 ч"),
        ("tiho_li", "мълчи ли продуктът по-дълго от допустимото",
         "25.08.2026 — „не знам\" е тревога, не спокойствие"),
        ("dnevnik_ot_github", "четецът на дневника: None при отказ, НЕ празно",
         "25.08.2026"),
        ("reshi", "решението, отделено от печатането, за да може да се изпита",
         "25.08.2026 — дупката оцеля до вечерта, защото беше вътре в main()"),
        ("tg_send", "гласът на пазача", "25.08.2026"),
    ],
    "predictor.py": [
        # име, за какво служи, кога/защо е добавено в списъка
        ("slyapa_karta", "карта без история, спореща с пазара, не излиза",
         "21.08.2026 — патч от старо копие я върна назад мълчаливо"),
        ("ima_pazar", "портиерът: карта без пазар не излиза", "19.08.2026"),
        ("pazarat_otgovarya", "разлика между „няма пазар\" и „доставчикът е долу\"",
         "19.08.2026 — без него един капнал доставчик спира целия бот"),
        ("razpredeli", "лупата гледа целия списък, не само началото",
         "19.08.2026 — тенисът на маса мълчеше при 120 налични срещи"),
        ("tt_shirina", "ширината важи само където е измерена",
         "19.08.2026 — 77% от играч с отрицателен баланс"),
        ("_tt_rang", "турнирите се подреждат по тежест",
         "18.08.2026 — детски турнири изяждаха професионалните"),
        ("_tt_dumi", "цепене на цели думи, не подниз",
         "18.08.2026 — „championSHIPS\" съдържа „champions\""),
        ("dobavi_pazar", "цената влиза в картата и в дневника", "13.08.2026"),
        ("cena_red", "цената СЕ ВИЖДА на картата, не само в дневника",
         "01.09.2026 — 512 от 1082 карти носеха цена и НИТО ЕДНА не я показваше"),
        ("itf_fixtures", "малкият тенис тур", "19.08.2026"),
        ("post_totali", "втора прогноза от същия мач", "19.08.2026"),
        ("build_pool", "кръговата подредба по спорт", "основа"),
        ("sabiray_fish", "фишът", "основа"),
    ],
    "scorer.py": [
        ("espn_otlozhen", "отложен мач не виси вечно",
         "19.08.2026 — карта висеше трети ден за отложен мач"),
        ("hvani_zatvaryashta", "затварящата цена за CLV", "18.08.2026"),
        ("dohodnost", "доходност при равен залог",
         "18.08.2026 — процент познати не значи печалба"),
        ("clv_text", "движението на пазара след като кажем", "18.08.2026"),
        ("itf_result", "присъда за малкия тенис тур",
         "19.08.2026 — карта без път до присъда виси вечно"),
        ("otvori_nanovo", "втори шанс за неотсъдените", "12.08.2026"),
        ("arhiviray", "архивът", "18.08.2026"),
    ],
    "pazar.py": [
        ("bez_marzh", "маржът на букмейкъра се маха",
         "18.08.2026 — суровото 1/цена надуваше пазара със 7.4%"),
        ("_amerikanski", "американският формат на равния",
         "18.08.2026 — 38 от 38 футболни мача"),
        ("_razlika_ch", "сверка на ЧАСА при търсене по имена",
         "18.08.2026 — цената идваше от вчерашния мач в серията"),
        ("cena_zatvarayashta", "затварящата цена", "18.08.2026"),
    ],
    "budilnik.py": [
        ("reshi", "решението будим ли", "основа"),
        ("_s_pochivka", "спирачка срещу щорм", "12.08.2026"),
    ],
    "pinnacle.py": [
        ("ceni_za", "цена по имена, със страните в НАШИЯ ред",
         "18.08.2026 — техните страни са обърнати спрямо нашите"),
        ("totali", "тоталите от същия отговор", "19.08.2026"),
    ],
}

# Константи, чиято ЛИПСА е тиха. Число, върнато на старата стойност, не гърми.
KONSTANTI = {
    "zalozhimo.py": [
        ("YUNOSHESKI_DUMI", "думите за юношески турнир, търсени като цели"),
        ("VAZRAST_BUKVA", "САМО „u\" — не „m\" и не „w\""),
    ],
    "vsichki_testove.py": [
        ("PADNALI_ZNAK", "знаци за провал, които бият чистата сметка"),
        ("PROPUSKAY", "кои файлове не се пускат и ЗАЩО"),
    ],
    "sglasie.py": [
        ("TEGLO", "колко тежи нашето число: 0.25 измерено, през среда"),
        ("BEZRAZLICHNO", "под 2 точки разлика не си говорим"),
    ],
    "pazach.py": [
        # 25.08.2026 — сентинелът е сърцето: `except: return []` уби предишния
        # пазач, защото направи аварията неразличима от мира.
        ("NEPITAN", "сентинел: „не можах да питам\" не е „питах и няма\""),
        ("VAZHNI", "кои workflow-и носят продукта"),
        ("POREDNI", "колко поредни провала правят тревога"),
        ("GRATIS_MIN", "гратис за закъснението на GitHub cron: медиана 65 мин"),
        ("TISHINA_CH", "колко часа мълчание на продукта са допустими: 22"),
    ],
    "predictor.py": [
        ("BEZ_ISTORIA_RAZLIKA", "прагът за сляпа карта"),
        ("TT_PALNA_N", "под колко мача ширината е предпазлива"),
        ("TT_SCALE_MALKO", "предпазливата ширина"),
        ("COMBO_MAX_SAME_SPORT", "таван на един спорт във фиш"),
        ("ISKAM_PAZAR", "правилото карта без пазар не излиза"),
        ("TARGUVANI", "измерено търгуваните лиги"),
        ("CENA_VKL", "ключът за цената: ВКЛЮЧЕН по подразбиране"),
        ("IZTOCHNIK_VKL", "ключът за името на източника: ИЗКЛЮЧЕН"),
        ("IZTOCHNIK_IME", "имената на източниците, сверявани с пазача"),
        ("CENA_OPASHKA", "думата какво значи числото — през нея се изпитва пазачът"),
    ],
    "budilnik.py": [
        ("GRATIS_MIN", "колко след началото на часа се брои за пропуснат"),
        ("TAVAN_MIN", "таванът на дупката"),
    ],
    "scorer.py": [
        ("OTLOZHEN", "сентинелът за отложен мач"),
        ("OTLOZHENI", "думите, по които се разпознава"),
    ],
}


def imena_v(path):
    """Всички имена на функции и присвоявания на най-горно ниво във файла."""
    try:
        with io.open(path, encoding="utf-8-sig") as f:
            d = ast.parse(f.read())
    except Exception as e:                                   # noqa: BLE001
        return None, str(e)[:80]
    fn, konst = set(), set()
    for n in ast.walk(d):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    konst.add(t.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            konst.add(n.target.id)
    return (fn, konst), None


_KESH_VIK = {}


def vsichki_vikania(path):
    """{име: колко пъти се вика} — извън selftest и извън собствената дефиниция.

    🔴 ЕДНО МИНАВАНЕ, НЕ ЕДНО НА ИМЕ. Първата ми версия обхождаше дървото за
    ВСЯКО търсено име и при predictor.py (403 KB, 8000 реда) това отнемаше
    минути. Сега дървото се обхожда веднъж и се кешира.
    """
    # 🔴 КЛЮЧЪТ Е ПЪТ + СЪДЪРЖАНИЕ (хванато от собствената ми самопроверка).
    # Първата версия кешираше само по път. Тестът пише три пъти в един и
    # същ временен файл с РАЗЛИЧНО съдържание и получаваше първия разбор и
    # трите пъти — тоест две проверки мереха стар файл.
    try:
        with io.open(path, "rb") as f:
            surov = f.read()
    except Exception:                                        # noqa: BLE001
        return None
    kl = (path, len(surov), hash(surov))
    if kl in _KESH_VIK:
        return _KESH_VIK[kl]
    try:
        d = ast.parse(surov.decode("utf-8-sig"))
    except Exception:                                        # noqa: BLE001
        _KESH_VIK[kl] = None
        return None
    # Кои редове са ВЪТРЕ в selftest — тестовете не се броят за кворум.
    test_redove = set()
    for n in ast.walk(d):
        if isinstance(n, ast.FunctionDef) and n.name == "selftest":
            for m in ast.walk(n):
                if hasattr(m, "lineno"):
                    test_redove.add(m.lineno)
    # И кои редове са вътре в дефиницията на всяка функция — за да не броим
    # рекурсивното повикване като употреба отвън.
    svoi = {}
    for n in ast.walk(d):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            svoi[n.name] = {m.lineno for m in ast.walk(n) if hasattr(m, "lineno")}
    # 🔴 И ПОВИКВАНИЯТА ПРЕЗ МОДУЛ (хванато с мутация 21.08.2026).
    # Първата версия броеше само голи имена — `bez_marzh(...)`. Между
    # модулите обаче повикването изглежда `PZ.bez_marzh(...)`, тоест
    # ast.Attribute, и не се броеше НИКОГА. Заради това разкачването на
    # `pazar.bez_marzh` от предсказателя мина невидимо.
    broi = {}
    for n in ast.walk(d):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Name):
            ime, vid = n.func.id, "golo"
        elif isinstance(n.func, ast.Attribute):
            ime, vid = n.func.attr, "modul"
        else:
            continue
        if True:
            ln = getattr(n, "lineno", -1)
            if ln in test_redove:
                continue
            if ln in svoi.get(ime, ()):
                continue
            k2 = (ime, vid)
            broi[k2] = broi.get(k2, 0) + 1
    _KESH_VIK[kl] = broi
    return broi


def vikat_li(path, ime, samo_modul=False):
    """Колко пъти името се вика извън дефиницията си и извън selftest.

    samo_modul=True брои САМО повикванията през модул (`PZ.име(...)`).
    -1 при нечетим файл.
    """
    b = vsichki_vikania(path)
    if b is None:
        return -1
    if samo_modul:
        return b.get((ime, "modul"), 0)
    return b.get((ime, "golo"), 0) + b.get((ime, "modul"), 0)

def provери():
    """[(файл, име, какво липсва)] — празно значи всичко е на място."""
    lipsvat = []
    for fajl, spisak in sorted(ZADALZHITELNI.items()):
        p = os.path.join(TUK, fajl)
        if not os.path.exists(p):
            lipsvat.append((fajl, "—", "самият файл липсва"))
            continue
        got, gr = imena_v(p)
        if got is None:
            lipsvat.append((fajl, "—", "не се разбира: " + str(gr)))
            continue
        fn, _k = got
        for ime, za_kakvo, koga in spisak:
            if ime not in fn:
                lipsvat.append((fajl, ime, za_kakvo + "  [" + koga + "]"))
    for fajl, spisak in sorted(KONSTANTI.items()):
        p = os.path.join(TUK, fajl)
        if not os.path.exists(p):
            continue
        got, _gr = imena_v(p)
        if got is None:
            continue
        _f, konst = got
        for ime, za_kakvo in spisak:
            if ime not in konst:
                lipsvat.append((fajl, ime, "константа: " + za_kakvo))
    return lipsvat


# Функции, които СЪЩЕСТВУВАТ, но не се викат никъде — мъртъв код.
NE_BIVA_MARTVI = {
    # И двете се викат от predictor.py от 25.08.2026. Спре ли викането,
    # юношеските се връщат и волейболът пак остава без цена — тихо.
    "zalozhimo.py": ["zalozhimo"],
    "pin_volei.py": ["cena", "index", "_index_ili_vzemi"],
    # Пазач, който не се вика, е файл. Тези трябва да се ползват НАИСТИНА.
    "pazach.py": ["obhod", "sadi", "kazvai_li", "tekst_trevoga", "dopusk_min",
                  "reshi", "tiho_li", "posledna_karta", "dnevnik_ot_github"],
    "predictor.py": ["slyapa_karta", "ima_pazar", "pazarat_otgovarya",
                     "razpredeli", "tt_shirina", "_tt_rang", "itf_fixtures",
                     "post_totali"],
    "scorer.py": ["espn_otlozhen", "hvani_zatvaryashta", "dohodnost", "clv_text"],
    "pazar.py": ["bez_marzh", "_amerikanski", "_razlika_ch"],
}


def martvi():
    """[(файл, име)] — съществува, но НИКОЙ файл не го вика извън теста.

    🔴 ТЪРСИ СЕ ВЪВ ВСИЧКИ ФАЙЛОВЕ (хванато от собствената ми самопроверка).
    Първата версия гледаше само файла, в който функцията е дефинирана, и
    обяви `pazar.bez_marzh` за мъртва — при положение че тя се вика от
    predictor.py. Точно ОБРАТНАТА грешка на тази, срещу която е този файл:
    фалшива тревога вместо пропусната.
    """
    # 🔴 ГОЛОТО ПОВИКВАНЕ СЕ БРОИ САМО В СОБСТВЕНИЯ ФАЙЛ (мутация 21.08.2026).
    # Иначе функция със СЪЩОТО ИМЕ в друг файл маскира мъртвата: `bez_marzh`
    # съществува и в pazar.py, и в volley_evro.py, и втората поддържаше
    # първата „жива", след като я разкачих от предсказателя.
    # През модул (`PZ.bez_marzh`) се брои навсякъде — точно така изглежда
    # истинското междумодулно повикване.
    vsichki = [os.path.join(TUK, f) for f in sorted(os.listdir(TUK))
               if f.endswith(".py") and not f.startswith(("backtest_", "build_"))]
    out = []
    for fajl, imena in sorted(NE_BIVA_MARTVI.items()):
        svoyat = os.path.join(TUK, fajl)
        if not os.path.exists(svoyat):
            continue
        for ime in imena:
            zhiva = vikat_li(svoyat, ime) > 0 or any(
                vikat_li(p, ime, samo_modul=True) > 0
                for p in vsichki if p != svoyat)
            if not zhiva:
                out.append((fajl, ime))
    return out


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    got, gr = imena_v(os.path.join(TUK, "cyalost.py"))
    check("собственият файл се разбира", got is not None)
    check("разборът намира собствените функции",
          got is not None and "provери" in got[0] and "martvi" in got[0])
    check("разборът намира константи",
          got is not None and "ZADALZHITELNI" in got[1])

    # Подхвърлен файл без нужното — проверката ТРЯБВА да го хване.
    import tempfile
    d = tempfile.mkdtemp(prefix="cyalost-")
    p = os.path.join(d, "проба.py")
    io.open(p, "w", encoding="utf-8").write("def nesto():\n    return 1\n")
    got2, _ = imena_v(p)
    check("чужд файл се разбира", got2 is not None and "nesto" in got2[0])
    check("липсващото име НЕ се намира", got2 is not None and "slyapa_karta" not in got2[0])

    io.open(p, "w", encoding="utf-8").write("def a():\n    pass\ndef b():\n    a()\n")
    check("викана функция се брои", vikat_li(p, "a") == 1)
    check("невикана функция дава нула", vikat_li(p, "b") == 0)
    io.open(p, "w", encoding="utf-8").write(
        "def a():\n    pass\ndef selftest():\n    a()\n")
    check("повикване САМО в теста НЕ се брои", vikat_li(p, "a") == 0)
    io.open(p, "w", encoding="utf-8").write("def a(:\n")
    check("счупен файл не гърми", imena_v(p)[0] is None and vikat_li(p, "a") == -1)

    check("списъкът покрива поне пет файла", len(ZADALZHITELNI) >= 5)

    # ─────────────── ДВОЙНИЦИТЕ (25.08.2026)
    # 🔴 ПОВЕДЕНЧЕСКИ: пише се временен файл и се гледа какво излиза.
    import tempfile as _tf
    _d = _tf.mkdtemp()
    def _pishi(ime, tekst):
        p = os.path.join(_d, ime)
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write(tekst)
        return p
    _chist = _pishi("chist.py", "A = 1\nB = 2\ndef f():\n    A = 9\n    return A\n")
    check("чистият файл няма двойници", dvoynici(_chist) == [])
    check("преприсвояване ВЪТРЕ в функция не е двойник",
          not any(i == "A" for i, _, _ in dvoynici(_chist)))
    _dv = _pishi("dv.py", "A = 1\nB = 2\nA = 3\n")
    _r = dvoynici(_dv)
    check("дублирана константа се хваща", len(_r) == 1 and _r[0][0] == "A")
    check("и се казват ДВАТА реда", _r[0][1] == 1 and _r[0][2] == 3)
    _df = _pishi("df.py", "def g():\n    return 1\ndef g():\n    return 2\n")
    check("дублирана функция се хваща",
          any(i == "g" for i, _, _ in dvoynici(_df)))
    _if = _pishi("if.py", "import os\nif os.name == 'nt':\n    X = 1\nelse:\n    X = 2\n")
    check("клоните на if НЕ са двойници", dvoynici(_if) == [])
    check("липсващ файл не гърми", dvoynici(os.path.join(_d, "nyama.py")) == [])
    _losh = _pishi("losh.py", "def (((\n")
    check("счупен файл не гърми", dvoynici(_losh) == [])
    check("обходът връща и името на файла",
          all(len(t) == 4 for t in vsichki_dvoynici([_dv])))
    check("обходът пропуска несъществуващите",
          vsichki_dvoynici([os.path.join(_d, "nyama.py")]) == [])
    import shutil as _sh
    _sh.rmtree(_d, ignore_errors=True)

    # 🔴 И НАЙ-ВАЖНОТО: САМИТЕ НАШИ ФАЙЛОВЕ да са чисти СЕГА.
    _nashi = vsichki_dvoynici()
    check("нашите файлове нямат двойници: " + str(_nashi[:3]), not _nashi)
    check("всеки ред носи ЗАЩО е в списъка",
          all(len(r) == 3 and r[1] and r[2]
              for sp in ZADALZHITELNI.values() for r in sp))
    # 🔴 КЪДЕ СПИРА И КЪДЕ САМО ДОКЛАДВА (21.08.2026).
    #
    # В предсказателя и оценителя цялостта е ПОРТИЕР — липсва ли защита,
    # по-добре мълчание, отколкото крива карта.
    #
    # В РУТЕРА обаче спирането е КАСКАДА: той разнася опашката на Telegram,
    # обслужва съпорта И носи будилника. Падне ли, предсказателят не се буди
    # изобщо и целият бот замлъква заради едно липсващо име.
    #
    # Тази проверка пази решението да не бъде върнато обратно по невнимание.
    _wf = os.path.join(TUK, ".github", "workflows")
    if os.path.isdir(_wf):
        def _stapka(fajl):
            try:
                with io.open(os.path.join(_wf, fajl), encoding="utf-8") as f:
                    redove = f.read().split(chr(10))
            except Exception:                                # noqa: BLE001
                return None
            for i, r in enumerate(redove):
                if "cyalost.py" in r:
                    # Гледаме БЛОКА на стъпката: пет реда назад стигат.
                    blok = chr(10).join(redove[max(0, i - 5):i + 1])
                    return "continue-on-error" in blok
            return None
        _r = _stapka("router.yml")
        _p = _stapka("predict.yml")
        _s = _stapka("score.yml")
        check("рутерът пуска цялостта", _r is not None)
        check("рутерът САМО ДОКЛАДВА (не спира каскадно)", _r is True)
        check("предсказателят пуска цялостта", _p is not None)
        check("предсказателят СПИРА при нарушена цялост", _p is False)
        check("оценителят пуска цялостта", _s is not None)
        check("оценителят СПИРА при нарушена цялост", _s is False)

    check("броят проверки е поне 10", ok >= 10)

    lip = provери()
    mrt = martvi()
    check("нищо задължително не липсва (%d)" % len(lip), not lip)
    check("няма мъртъв код (%d)" % len(mrt), not mrt)
    for f, i, z in lip:
        bad.append("ЛИПСВА %s :: %s — %s" % (f, i, z))
    for f, i in mrt:
        bad.append("МЪРТЪВ %s :: %s" % (f, i))

    print("САМОПРОВЕРКА НА ЦЯЛОСТТА: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


# ═══════════════════════════════ 👯 ДВОЙНИЦИТЕ (25.08.2026)
#
# ЗАЩО СЪЩЕСТВУВА, платено със собствена грешка същия ден:
# написах `DVA_IZHODA = (...)` с шест спорта, без да видя, че такава константа
# ВЕЧЕ живее осемдесет реда по-горе — с ОСЕМ спорта. Python не казва нищо:
# втората просто презаписва първата. Последицата беше тиха и грозна —
# dolen_prag() почна да връща футболната летва 45% за хокея и амер. футбол
# вместо 53%, тоест два спорта щяха да пускат карти под собствения си праг.
#
# Хвана го случайно съществуваща проверка. „Случайно" не е стратегия.
#
# Тук се лови по устройство: два top-level израза с едно и също име в един
# файл. Проверява се САМО най-горното ниво — вътре в функция преприсвояването
# е нормално, а `if/else` клоните нарочно дефинират едно и също име по два
# начина, затова те не се броят.
def dvoynici(path):
    """[(име, ред_първи, ред_втори)] за top-level имена, дефинирани два пъти."""
    try:
        with io.open(path, encoding="utf-8") as f:
            drvo = ast.parse(f.read())
    except Exception:                                        # noqa: BLE001
        return []
    vidyani, dubli = {}, []
    for vazel in drvo.body:                # САМО най-горното ниво
        imena = []
        if isinstance(vazel, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            imena = [vazel.name]
        elif isinstance(vazel, ast.Assign):
            imena = [t.id for t in vazel.targets if isinstance(t, ast.Name)]
        elif isinstance(vazel, ast.AnnAssign) and isinstance(vazel.target, ast.Name):
            imena = [vazel.target.id]
        for ime in imena:
            if ime.startswith("_") and ime.endswith("_"):
                continue                   # __all__ и подобни се пипат нарочно
            if ime in vidyani:
                dubli.append((ime, vidyani[ime], getattr(vazel, "lineno", 0)))
            else:
                vidyani[ime] = getattr(vazel, "lineno", 0)
    return dubli


def vsichki_dvoynici(fajlove=None):
    """[(файл, име, ред1, ред2)] за всички наши файлове."""
    if fajlove is None:
        fajlove = sorted(set(list(ZADALZHITELNI) + list(KONSTANTI)
                             + list(NE_BIVA_MARTVI)))
    out = []
    for f in fajlove:
        if not os.path.exists(f):
            continue
        for ime, r1, r2 in dvoynici(f):
            out.append((f, ime, r1, r2))
    return out


def main():
    if "--selftest" in sys.argv or "selftest" in sys.argv:
        return selftest()
    lip, mrt = provери(), martvi()
    dvo = vsichki_dvoynici()
    if not lip and not mrt and not dvo:
        n = sum(len(v) for v in ZADALZHITELNI.values()) + \
            sum(len(v) for v in KONSTANTI.values())
        print("🧬 ЦЯЛОСТТА Е ЗАПАЗЕНА — всичките " + str(n)
              + " белега са на място, нула мъртви.")
        return 0
    print("🔴 ЦЯЛОСТТА Е НАРУШЕНА:")
    for f, i, z in lip:
        print("   ЛИПСВА  %-14s %-22s %s" % (f, i, z))
    for f, i in mrt:
        print("   МЪРТЪВ  %-14s %s — съществува, но никой не го вика" % (f, i))
    for f, i, r1, r2 in dvo:
        print("   ДВОЙНИК %-14s %s — дефинирано на ред %d и пак на ред %d;"
              " второто презаписва първото МЪЛЧАЛИВО" % (f, i, r1, r2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
