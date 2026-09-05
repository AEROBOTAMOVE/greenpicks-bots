# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БУДИЛНИК ЗА ЗАТВОРЕНИТЕ СПОРТОВЕ 🔔

Един въпрос: КОГА тръгват хокеят и американският футбол, колко мача носят в
първата си седмица и колко от тях ще имат цена.

ЗАЩО СЪЩЕСТВУВА
`predictor.py` държи `PREDICT_IZKL="hockey,amfootball"` от 11.08.2026 по
изрична заповед на собственика — двата спорта дадоха 0 карти от 261 записа в
дневника и стаите им стояха празни. Пътят назад е една променлива.
Но НИКОЙ не помни да я върне, а „септември" не е дата.

Този файл е будилникът. Пуска се без нищо да пипа, гледа ИЗТОЧНИЦИТЕ (не
паметта) и казва с числа: тръгва на еди-коя си дата, толкова мача, толкова с
цена. Когато числото стане достатъчно голямо, собственикът маха ключалката.

КАКВО ИЗМЕРВА
  1. Първата дата с ИСТИНСКИ мач (предсезонните се режат — точно както ги
     реже predictor.py, със същата логика).
  2. Мачовете в първите 7 дни от старта.
  3. Колко от тях Pinnacle вече котира — през СЪЩИЯ модул pinnacle.py, който
     ползва самият predictor, тоест числото е това, което ботът ще получи.
  4. Двата дефекта, които ще ухапят точно на 29.09 — вж. по-долу.
  5. Гърми ли ЗАТВОРЕН спорт, който вече играе. (добавено 25.08.2026)

✅ ДЕФЕКТ 1 — hockey_fixtures не пази оригиналното име (измерено 19.08.2026)
   `predictor.hockey_fixtures` връщаше `"extra": {}`. Търсенето на цена в
   `predictor.py` чете `ex.get("home_en") or fx.get("home")` — тоест падаше
   върху ВЕЧЕ ПРЕВЕДЕНОТО име.
   ✅ ОПРАВЕН МЕЖДУВРЕМЕННО. Измерено на живо 25.08.2026 (`python sezon.py`):
   `hockey_fixtures пази home_en=Hurricanes`. Проверката остава — тя е
   единственото, което ще забележи, ако някой го върне назад.

🔴 ДЕФЕКТ 2 — „Rangers" -> „Рейнджърс" убива търсенето (измерено 19.08.2026)
   `BG_NAME` има „Rangers": „Рейнджърс" заради Глазгоу. НХЛ дава само прякора
   („Rangers", не „New York Rangers"), значи картата на футболния клуб хваща
   хокейния отбор. `pinnacle._norm` НЕ маха кирилица (`isalnum()` е вярно за
   българските букви), затова търсим „рейнджърс" в свят, който пише
   „New York Rangers" — и не намираме нищо.
   ИЗМЕРЕНО: 1 от 32 отбора в НХЛ. Малко, но е точно отборът, за когото
   пишат най-много.
   ⚠ ЖИВ, НО ВЕЧЕ НЕ СТРУВА ЦЕНИ (измерено 25.08.2026). Понеже дефект 1 е
   оправен, `hockey_fixtures` подава `home_en` и преводът изобщо не се стига.
   Симулацията с техния пазар върху първата седмица на НХЛ дава
   „0 от 43 мача остават без цена" — беше цялата причина дефект 2 да е червен.
   Тоест дефект 2 е зареден пистолет с празен пълнител: `bg_name` още го прави,
   но пътят до цената вече не минава оттам. Не се маха — маха ли се дефект 1,
   този пак почва да коства.

  python sezon.py             — будилникът (иска мрежа)
  python sezon.py --zhivo     — същото, но с подробностите
  python sezon.py --selftest  — само проверките, БЕЗ мрежа
"""
import datetime
import gzip
import json
import os
import sys
import urllib.request
import zlib

# --------------------------------------------------------------- НАСТРОЙКИ
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
NHL = "https://api-web.nhle.com/v1"
TIMEOUT = 30
SEDMICA = 7          # „първа седмица" значи 7 дни, старта включително
HORIZONT = 80        # докъде напред гледаме; НХЛ тръгва след ~6 седмици

# 🔴 ИМЕНАТА НА PINNACLE ЗА ДВАТА СПОРТА (измерено 19.08.2026 през /sports).
# `pinnacle.SPORT_ID` НЯМА нито хокей, нито американски футбол — защото са
# писани, докато двата спорта бяха затворени. Тук се ДОБАВЯТ по време на
# пускане (не се пипа чужд файл), а точният патч за pinnacle.py е в отчета.
#   15 = Football (американският) · 393 мача в момента
#   19 = Hockey                   ·  17 мача в момента
PIN_ID = {"amfootball": 15, "hockey": 19}

# 🔴 ЛИГИТЕ СЪЩЕСТВУВАТ, ПАЗАРЪТ ОЩЕ НЕ (измерено 19.08.2026 през
# /sports/{id}/leagues?all=true&brandId=0):
#   амер. футбол (15): NCAA 198 мача · NFL 174 · NFL Pre Season 16
#   хокей (19):        NHL 3 · NCAA 0 · AHL 0
# Тоест ключът за NCAA хокей ГО ИМА при тях — просто е празен през август.
# „0 с цена" днес значи „рано", а не „никога". Точно тази разлика ни ухапа с
# волейбола, където нулата беше вечна.

# 🔑 КЛЮЧАЛКАТА, ПРОЧЕТЕНА ПРЕДИ ДА Я ПИПНЕМ (добавено 25.08.2026).
# `zhivo()` по-долу прави `os.environ.setdefault("PREDICT_IZKL", "")`, за да
# може да внесе predictor и да опипа хокейните функции. Страничният ефект: от
# този миг нататък `predictor.IZKLYUCHENI` е ПРАЗНО и всеки, който го попита
# „кой спорт е затворен", получава „никой". Тоест алармата, която пише
# „затворен спорт играе днес", щеше да мълчи ВИНАГИ. Затова истинската
# стойност се снима тук, при внасянето, преди пипането.
_IZKL_PRI_STARTA = os.environ.get("PREDICT_IZKL")

# 📌 ИЗМЕРЕНИТЕ ДАТИ НА ОТВАРЯНЕ (всичките пуснати на 25.08.2026).
#
# ЗАЩО ги има закован списък, щом файлът и без това пита живо: за да има с
# КАКВО да се сравни живото. Здравният преглед (`zdrave.py`, KOGA_TRAGVA)
# твърдеше „хокеят тръгва около 15.09" и „амер. футбол в началото на
# септември". И двете са ПРЕДПОЛОЖЕНИЯ и двете се оказаха неверни:
#   хокеят е 29.09 — 14 дни СЛЕД обявеното 15.09;
#   колежанският футбол е 29.08 — 3 дни ПРЕДИ 1 септември,
#   а НФЛ е 10.09 — 9 дни СЛЕД него. Тоест едната фраза „в началото на
#   септември" покрива две дати, които се разминават помежду си с 12 дни,
#   и бърка посоката и за двете.
# Разминаване между закованото и живото се ПЕЧАТА при всяко пускане.
#
# „kosh" е кошът в predictor (`PREDICT_IZKL`). Пише се ИСТИНСКИЯТ кош дори за
# спорт, който днес не е затворен — това е разликата между запис и украса.
# NBA носи „basketball", а европейският футбол — „football"; днес и двата коша
# са отворени, тоест `veche_v_sezon` мълчи за тях. Затвори ли някой утре
# баскетбола, NBA се обажда САМА, без нито ред нова работа. Ако тук стоеше
# None, редовете щяха да са коментар с кавички — четими, но неспособни да
# гръмнат, а точно това ни ухапа с волейбола.
#
# „sigurno" False значи: числото е най-ранното В ПРОЗОРЕЦА, който съм гледал,
# а не доказаното начало на сезона.
OTVARYA = {
    "nfl": {
        "data": "2026-09-10", "kosh": "amfootball", "sigurno": True,
        "izvor": "ESPN scoreboard nfl 25.08-20.10 (25.08.2026): 93 мача"
                 " season.slug=regular-season, най-ранен 10.09 (1 мач, четвъртък);"
                 " 16 предсезонни от 27.08 се режат. Ден по ден 01.09-14.09:"
                 " 10.09=1, 11.09=1, 13.09=12. ESPN core nfl/seasons/2026/types:"
                 " type=2 start=2026-09-06 — обявено, но ПРАЗНО до 10.09."},
    "ncaaf": {
        "data": "2026-08-29", "kosh": "amfootball", "sigurno": True,
        "izvor": "ESPN scoreboard college-football 25.08-20.11 (25.08.2026):"
                 " 763 мача regular-season, най-ранен 29.08 (7 мача), после"
                 " 30.08=1, 03.09=6, 04.09=8, 05.09=60. Прозорецът 15.08-28.08"
                 " върна 0 мача — а ESPN ДАВА минали мачове (същата заявка за"
                 " Ла Лига 15.08-24.08 върна 16 броя state=post), значи нулата"
                 " е истинска липса, не сляпо петно."},
    "nhl": {
        "data": "2026-09-29", "kosh": "hockey", "sigurno": True,
        "izvor": "api-web.nhle.com/v1/schedule/now (25.08.2026):"
                 " regularSeasonStartDate=2026-09-29, preSeasonStartDate=2026-09-19,"
                 " regularSeasonEndDate=2027-04-10; gameWeek 29.09-05.10 носи 43"
                 " мача, всичките gameType=2, петте на 29.09 са"
                 " FLA@CAR, MTL@TOR, NYR@BOS, VAN@EDM, CHI@VGK."},
    "ncaah": {
        "data": "2026-10-02", "kosh": "hockey", "sigurno": True,
        "izvor": "ESPN scoreboard mens-college-hockey 25.08-20.11 (25.08.2026):"
                 " 342 мача regular-season, най-ранен 02.10."},
    "ncaahw": {
        "data": "2026-09-18", "kosh": "hockey", "sigurno": True,
        "izvor": "ESPN scoreboard womens-college-hockey 25.08-20.11 (25.08.2026):"
                 " 316 мача regular-season, най-ранен 18.09 — тоест жените"
                 " отварят 11 дни ПРЕДИ НХЛ и 14 дни преди мъжкия колеж."},
    # ── ПЕТТЕ НОВИ (02.09.2026). Всяка дата е снета ЖИВО от ESPN в деня
    # на добавянето, с честен подпис; числото до нея е броят събития, който
    # отговорът върна. Догадки няма. „nba" вече го имаше и не се пипа.
    "ncaab": {
        "data": "2026-11-02", "kosh": "basketball", "sigurno": True,
        "izvor": "ESPN scoreboard basketball/mens-college-basketball, питан"
                 " ДЕН ПО ДЕН от 01.11 (02.09.2026): първият ден с мачове е"
                 " 02.11 с 56 мача. 🔴 Този адрес ОТКАЗВА период (404) и"
                 " приема само една дата — виж бележката във vzemi_espn."},
    "gleague": {
        "data": "2026-11-07", "kosh": "basketball", "sigurno": True,
        "izvor": "ESPN scoreboard basketball/nba-development (02.09.2026):"
                 " 10 събития, всичките на 07.11."},
    "nba": {
        "data": "2026-10-20", "kosh": "basketball", "sigurno": True,
        "izvor": "ESPN core basketball/nba/seasons/2027/types (25.08.2026):"
                 " type=1 Preseason 30.09-20.10, type=2 Regular Season"
                 " 20.10.2026-12.04.2027. Scoreboard 25.08-20.11: 55 предсезонни"
                 " от 03.10 и 235 редовни от 20.10. На 25.08: 0 мача."
                 " НЕ Е ЗАТВОРЕН — просто е извън сезон."},
    "evrofutbol": {
        "data": "2026-08-15", "kosh": "football", "sigurno": False,
        "izvor": "ESPN scoreboard soccer (25.08.2026). Прозорец 18.08-01.09:"
                 " eng.1=20, esp.1=25, ita.1=20, ger.1=9, fra.1=18 мача."
                 " Прозорец 15.08-24.08 за esp.1: 16 мача, ВСИЧКИТЕ state=post,"
                 " най-ранен 15.08. Тоест европейският футбол ИГРАЕ СЕГА."
                 " 🔴 15.08 е най-ранният В МОЯ ПРОЗОРЕЦ, не доказаното начало"
                 " на сезона — не съм гледал по-назад. ESPN core дава"
                 " startDate=2026-06-01 за eng.1, което е административно и"
                 " безполезно. Затова sigurno=False. Важното число тук не е"
                 " датата, а че кошът football (в predictor) НЕ Е затворен."},
}


def izkl_ot_yml(chetec=None):
    """Подразбирането на PREDICT_IZKL, ПРОЧЕТЕНО от predict.yml. None = не знам.

    🔴 ЗАЩО СЪЩЕСТВУВА (02.09.2026). Долу стоеше заковано
    {"hockey", "amfootball"} — копие на подразбирането в predictor.py от
    11.08. Същия ден амер. футбол беше ОТВОРЕН (predict.yml вече казва
    'hockey', черната кутия го потвърждава с 6 срещи и излязла карта), а
    стъпката в daily.yml НЕ подава ключа изобщо. Резултат: будилникът
    викаше «ncaaf играе, а кошът е затворен» и връщаше изход 2 — вечно, за
    спорт, който вече работи.
    Копие, което помни, изгнива. Затова тук се ЧЕТЕ живият файл.
    """
    import re as _re
    if chetec is not None:
        t = chetec()
    else:
        t = None
        for baza in (".github/workflows", "../.github/workflows"):
            p = os.path.join(baza, "predict.yml")
            if os.path.exists(p):
                # 🔴 ВГРАДЕНИЯТ open, не io.open (02.09.2026): sezon.py НЕ
                # внася `io`, тоест io.open вдигаше NameError — а долният
                # `except` го преглъщаше и връщаше «не знам». Пазач, който
                # крие собствената си програмна грешка, е по-лош от липсващ.
                # Затова се хваща САМО грешка при ЧЕТЕНЕ; всичко останало
                # гърми на глас.
                try:
                    with open(p, encoding="utf-8-sig") as f:
                        t = f.read()
                except (OSError, UnicodeDecodeError):
                    return None
                break
    if t is None:
        return None
    m = _re.search(r"PREDICT_IZKL:\s*\$\{\{[^}]*\|\|\s*'([^']*)'", t)
    if m:
        return m.group(1)
    m = _re.search(r"^\s*PREDICT_IZKL:\s*(.+)$", t, _re.M)
    if m and "${{" not in m.group(1):
        return m.group(1).strip().strip("'").strip('"')
    if m:
        # редът го има, но без подразбиране -> празно значи «нищо затворено»
        return ""
    return None


def razcheti_izkl(raw, chetec=None):
    """PREDICT_IZKL -> множеството затворени спортове.

    ПРАЗЕН низ значи „нищо не е затворено"; None значи „не ми подадоха
    ключа" — и тогава се пита predict.yml, а не паметта. Двете НЕ са едно
    и също и точно тази разлика решава дали алармата има право да гърми.
    """
    if raw is None:
        ot_yml = izkl_ot_yml(chetec)
        if ot_yml is not None:
            return {s.strip().lower() for s in ot_yml.split(",") if s.strip()}
        return {"hockey", "amfootball"}
    return {s.strip().lower() for s in str(raw).split(",") if s.strip()}


def _proveri_izkl(ck):
    """Пазач за izkl_ot_yml/razcheti_izkl. Викан от selftest.

    🔴 ЗАЩО (02.09.2026). Стъпката «Сезонен будилник» в daily.yml НЕ подаваше
    PREDICT_IZKL, а razcheti_izkl(None) връщаше заковано {"hockey",
    "amfootball"} — копие на подразбирането от 11.08. Същия ден амер. футбол
    беше ОТВОРЕН и будилникът викаше «ncaaf играе, а кошът е затворен»,
    връщайки изход 2 при всяко пускане. Вечна фалшива тревога.
    И втори дефект в самата поправка: първата ѝ версия ползваше io.open, а
    този файл НЕ внася io — NameError се преглъщаше от широк except и
    функцията пак връщаше «не знам». Пазач, който крие собствената си
    програмна грешка.
    """
    # ЧЕТЕНЕТО НА YML-А — поведенчески, с подхвърлен текст
    ck("чете подразбирането от yml",
       izkl_ot_yml(lambda: "  PREDICT_IZKL: ${{ vars.PREDICT_IZKL || 'hockey' }}")
       == "hockey")
    ck("чете и празно подразбиране",
       izkl_ot_yml(lambda: "  PREDICT_IZKL: ${{ vars.PREDICT_IZKL || '' }}") == "")
    ck("чете и закована стойност без ${{ }}",
       izkl_ot_yml(lambda: "  PREDICT_IZKL: hockey,amfootball")
       == "hockey,amfootball")
    ck("ред без подразбиране значи «нищо затворено»",
       izkl_ot_yml(lambda: "  PREDICT_IZKL: ${{ vars.PREDICT_IZKL }}") == "")
    ck("липсващ ред дава «не знам», не празно",
       izkl_ot_yml(lambda: "on: {}") is None)
    ck("липсващ файл дава «не знам»", izkl_ot_yml(lambda: None) is None)

    # РАЗЧИТАНЕТО — трите състояния са РАЗЛИЧНИ
    ck("подаден ключ бие всичко", razcheti_izkl("hockey") == {"hockey"})
    ck("празен низ значи НИЩО затворено", razcheti_izkl("") == set())
    ck("без ключ се пита yml-ът, не паметта",
       razcheti_izkl(None, chetec=lambda: "  PREDICT_IZKL: ${{ v || 'hockey' }}")
       == {"hockey"})
    ck("без ключ и без yml се пада на стария списък",
       razcheti_izkl(None, chetec=lambda: None) == {"hockey", "amfootball"})

    # 🔴 ЖИВИЯТ ФАЙЛ. Ако този ред падне, значи или predict.yml се е сменил,
    # или четенето пак е счупено — и двете искат да се видят веднага.
    zhiv = izkl_ot_yml()
    ck("живият predict.yml се чете наистина (%s)" % repr(zhiv), zhiv is not None)

    # И че поправката на io.open не се е върнала: широк except върху
    # програмна грешка би върнал None вместо да гръмне.
    izv = izkl_ot_yml.__code__.co_names
    ck("не се лови всичко подред", "Exception" not in izv)


def zatvoreni_pri_starta():
    """Кои спортове са били затворени, когато файлът се е внасял."""
    return razcheti_izkl(_IZKL_PRI_STARTA)


# Кой затворен спорт откъде се чете. Редът е редът на печатане.
# „vazhen" значи: тази стая е обещана на читателя и празна карта се вижда.
KALENDAR = [
    {"kod": "nfl", "ime": "🏈 НФЛ", "kosh": "amfootball",
     "izvor": ("espn", "football", "nfl"), "vazhen": True,
     "beleshka": "стая 1967 · predictor го знае вече (amfootball_fixtures)"},
    {"kod": "ncaaf", "ime": "🏈 NCAA амер. футбол", "kosh": "amfootball",
     "izvor": ("espn", "football", "college-football"), "vazhen": True,
     "beleshka": "същата стая · predictor го знае вече (AMF_LEAGUES)"},
    {"kod": "nhl", "ime": "🏒 НХЛ", "kosh": "hockey",
     "izvor": ("nhl", "", ""), "vazhen": True,
     "beleshka": "стая 1961 · predictor го знае вече (hockey_fixtures)"},
    {"kod": "ncaah", "ime": "🏒 NCAA хокей, мъже", "kosh": "hockey",
     "izvor": ("espn", "hockey", "mens-college-hockey"), "vazhen": False,
     "beleshka": "🔴 predictor НЯМА такъв източник — hockey_fixtures чете само НХЛ"},
    {"kod": "ncaahw", "ime": "🏒 NCAA хокей, жени", "kosh": "hockey",
     "izvor": ("espn", "hockey", "womens-college-hockey"), "vazhen": False,
     "beleshka": "🔴 predictor НЯМА такъв източник; и моделът иска таблица, каквато няма"},
    # ── БАСКЕТБОЛ И ТЕНИС (02.09.2026)
    #
    # 🔴 ДОТУК КАЛЕНДАРЪТ ЗНАЕШЕ САМО ДВА СПОРТА. Пет реда, всичките за
    # американски футбол и хокей. Тоест НБА можеше да тръгне, ботът да мълчи,
    # и никой да не предупреди — точно дефектът, срещу който този файл е
    # написан. `predictor.BASK_LEAGUES` държи седем лиги и предсказателят ги
    # пита; будилникът не следеше нито една.
    {"kod": "nba", "ime": "🏀 НБА", "kosh": "basketball",
     "izvor": ("espn", "basketball", "nba"), "vazhen": True,
     "beleshka": "стая на баскетбола · predictor го знае (BASK_LEAGUES)"},
    # 🔴 WNBA, ATP и WTA НАРОЧНО ГИ НЯМА ТУК (обмислено 02.09.2026).
    # Този календар отговаря на въпроса „кога ОТВАРЯ спорт, който сега е
    # затворен". WNBA, ATP и WTA ТЕКАТ — да им сложа дата значи да напиша в
    # полето „отваря на" датата на следващия им мач, което е друго нещо.
    # Ако млъкнат, това е СЧУПЕН ИЗВОР и е работа на здравния преглед
    # (zdrave.py), не на сезонния будилник. Поле, което значи две неща, е
    # поле, което не значи нищо.
    {"kod": "ncaab", "ime": "🏀 NCAA баскетбол, мъже", "kosh": "basketball",
     "izvor": ("espn", "basketball", "mens-college-basketball"), "vazhen": True,
     "beleshka": "тръгва началото на ноември · predictor го знае (BASK_LEAGUES)"},
    {"kod": "gleague", "ime": "🏀 G-лига", "kosh": "basketball",
     "izvor": ("espn", "basketball", "nba-development"), "vazhen": False,
     "beleshka": "в BASK_LEAGUES е, но е тънък пазар — не вдига важна тревога"},
    #
    # 🔴 КОИ НАРОЧНО ГИ НЯМА (за да не се добавят по невнимание утре):
    #   · клубен волейбол (PlusLiga, SuperLega, Efeler…) — НЯМАМЕ извор.
    #     Проверено живо 02.09.2026: FIVB дава 41 турнира напред и НИТО ЕДНА
    #     клубна лига, защото е федерация на националните отбори.
    #   · европейски хокей (КХЛ, CHL, SM Liiga) — Pinnacle дава мачове и
    #     коефициенти, но никой безплатен извор не дава РЕЗУЛТАТИ, значи
    #     картата не може да се оцени.
    #   Ред за тях би бил ВЕЧНА фалшива тревога. Фалшивата тревога уморява
    #   ухото и после истинската не се чува — това вече се е случвало тук.
]

_zayavki = [0]
_provali = [0]
_zashto = []


def broi_zayavki():
    """Колко заявки е направил ТОЗИ файл. Селфтестът иска да е нула."""
    return _zayavki[0]


def broi_provali():
    """Колко заявки са се провалили. Нула мачове + провал НЕ е „няма сезон"."""
    return _provali[0]


# 🔴 ДВАТА ИЗТОЧНИКА ИСКАТ ПРОТИВОПОЛОЖНИ ПОДПИСИ (измерено 19.08.2026,
# един и същ адрес, четири комбинации, една минута):
#
#   api-web.nhle.com  без подпис -> 403 · с Chrome подпис -> 200 (7 седмици)
#   site.api.espn.com без подпис -> 200 · с Chrome подпис -> 403
#
# Първата ми версия на този файл пращаше „без подпис" навсякъде, защото така
# се оправи ESPN на 11.08. Резултатът: будилникът каза „🏒 НХЛ няма нито един
# мач до 07.11", докато НХЛ тръгва на 29.09 с 43 мача. Тоест поправка за
# единия източник направи ВТОРИЯ ням — и то мълчаливо, с бодра зелена карта.
# `predictor.glavi_za` вече знае това; тук е повторено нарочно, за да не зависи
# будилникът от predictor.py.
BEZ_PODPIS = ("espn.com",)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def glavi_za(url):
    """Кои глави заминават с една заявка. Отделено, за да се тества само."""
    if any(h in str(url) for h in BEZ_PODPIS):
        return {"Accept": "application/json"}
    return {"User-Agent": UA, "Accept": "*/*"}


def _json(url):
    """Взима JSON или None. Нито един провал не бива да събори будилника."""
    _zayavki[0] += 1
    try:
        req = urllib.request.Request(url, headers=glavi_za(url))
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            raw = zlib.decompress(raw)
        return json.loads(raw.decode("utf-8-sig", "replace"))
    except Exception as e:                                   # noqa: BLE001
        _provali[0] += 1
        if len(_zashto) < 6:
            _zashto.append(str(url)[:60] + " -> " + str(e)[:40])
        return None


# ------------------------------------------------------------------ ФИЛТЪР
def predsezonen(ev, comp):
    """Предсезонен ли е мачът по ESPN. Копие на predictor.predsezonen.

    ЗАЩО е копие, а не внасяне: будилникът трябва да се пуска и когато
    predictor.py е счупен — иначе точно в деня, когато нещо гръмне, няма да
    има кой да каже „сезонът е тръгнал".
    """
    if str(((ev or {}).get("season") or {}).get("slug") or "").lower() == "preseason":
        return True
    if "preseason" in str(((ev or {}).get("seasonType") or {}).get("name") or "").lower():
        return True
    if str(((comp or {}).get("type") or {}).get("abbreviation") or "").upper() == "PRE":
        return True
    return False


def espn_sides(comp):
    """Домакин и гост по homeAway, НИКОГА по реда в списъка."""
    h = a = None
    for c in ((comp or {}).get("competitors") or []):
        if c.get("homeAway") == "home":
            h = c
        elif c.get("homeAway") == "away":
            a = c
    return h, a


def parse_espn(j):
    """ESPN scoreboard -> [(дата, дом_en, гост_en)]. Само неиграни, без предсезон.

    ЗАЩО отделно от четенето: така се тества с подхвърлен JSON, без мрежа.
    """
    out = []
    for ev in ((j or {}).get("events") or []):
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0] or {}
        if str(((comp.get("status") or {}).get("type") or {}).get("state") or "").lower() != "pre":
            continue
        if predsezonen(ev, comp):
            continue
        h, a = espn_sides(comp)
        if not h or not a:
            continue
        hn = str(((h.get("team") or {}).get("displayName")) or "")
        an = str(((a.get("team") or {}).get("displayName")) or "")
        if not hn or not an:
            continue
        out.append((str(ev.get("date") or "")[:10], hn, an))
    return out


def parse_nhl(j):
    """НХЛ /schedule -> [(дата, дом_en, гост_en)]. Само редовният сезон.

    ЗАЩО пълното име: /schedule дава placeName + commonName („Florida" +
    „Panthers"), докато /score — от който чете predictor — дава САМО прякора.
    Пълното име е това, което чуждият пазар знае.
    """
    out = []
    for wk in ((j or {}).get("gameWeek") or []):
        for gm in (wk.get("games") or []):
            if gm.get("gameType") == 1:          # предсезонните не носят информация
                continue
            if str(gm.get("gameState") or "").upper() not in ("FUT", "PRE"):
                continue
            h, a = gm.get("homeTeam") or {}, gm.get("awayTeam") or {}
            hn = _nhl_ime(h)
            an = _nhl_ime(a)
            if not hn or not an:
                continue
            out.append((str(wk.get("date") or "")[:10], hn, an))
    return out


def nhl_start(j):
    """Обявеното от НХЛ начало на РЕДОВНИЯ сезон. -> „ГГГГ-ММ-ДД" или None.

    🔴 КАПАНЪТ, ЗАРАДИ КОЙТО ФУНКЦИЯТА СЪЩЕСТВУВА (измерено 25.08.2026).
    Първата мисъл е да се вземе `nextStartDate` — звучи точно като „кога
    почва". Не е. Един и същ отговор на /schedule/now в този ден дава:
        regularSeasonStartDate = 2026-09-29   <- вярното
        nextStartDate          = 2026-10-06   <- следващата СЕДМИЦА
        previousStartDate      = 2026-09-22
        preSeasonStartDate     = 2026-09-19
    `nextStartDate` е границата на съседната седмица от календара, не на
    сезона. Взето ли беше то, будилникът щеше да закъснее СЕДЕМ ДНИ — и то
    тихо, с права зелена карта, защото 06.10 е напълно правдоподобна дата
    за начало на НХЛ. Затова се чете САМО regularSeasonStartDate, а
    самопроверката подхвърля и двете полета наведнъж.
    """
    d = str(((j or {}).get("regularSeasonStartDate")) or "")[:10]
    return d if len(d) == 10 else None


def imena_na_den(j, den):
    """Мачовете на ESPN за точно този ден — ИЗИГРАНИ ИЛИ НЕ. -> [„дом - гост"].

    ЗАЩО не се ползва `parse_espn`: тя нарочно държи само неиграните („pre"),
    защото будилникът гледа НАПРЕД. Алармата „затворен спорт играе ДНЕС"
    пита обратното и трябва да гърми и в 23:00, когато мачът е свършил и
    state вече е „post". Мерено с `parse_espn` алармата млъква точно в мига
    на първия начален удар — тоест в деня, за който е направена.
    Предсезонните пак падат: те не значат „сезонът е тръгнал".
    """
    out = []
    for ev in ((j or {}).get("events") or []):
        if str(ev.get("date") or "")[:10] != den:
            continue
        comps = ev.get("competitions") or []
        comp = (comps[0] or {}) if comps else {}
        if predsezonen(ev, comp):
            continue
        h, a = espn_sides(comp)
        hn = str(((h or {}).get("team") or {}).get("displayName") or "")
        an = str(((a or {}).get("team") or {}).get("displayName") or "")
        out.append((hn + " - " + an) if (hn and an) else str(ev.get("name") or "мач"))
    return out


def nhl_imena_na_den(j, den):
    """Мачовете на НХЛ за точно този ден — изиграни или не. Без предсезонните."""
    out = []
    for wk in ((j or {}).get("gameWeek") or []):
        if str(wk.get("date") or "")[:10] != den:
            continue
        for gm in (wk.get("games") or []):
            if gm.get("gameType") == 1:
                continue
            out.append(_nhl_ime(gm.get("homeTeam") or {}) + " - "
                       + _nhl_ime(gm.get("awayTeam") or {}))
    return out


def _nhl_ime(t):
    """Пълното английско име на отбор от НХЛ, ако източникът го дава."""
    mesto = str(((t or {}).get("placeName") or {}).get("default") or "").strip()
    kratko = str(((t or {}).get("commonName") or {}).get("default")
                 or ((t or {}).get("name") or {}).get("default") or "").strip()
    if mesto and kratko and not kratko.startswith(mesto):
        return mesto + " " + kratko
    return kratko or str((t or {}).get("abbrev") or "")


# ------------------------------------------------------------------ ЧЕТЕНЕ
def vzemi_espn(sport, slug, ot, do, dnes=None):
    """Неиграните срещи за период + мачовете ДНЕС. -> (срещи, [днешни]).

    ЗАЩО с период: ESPN приема `dates=ГГГГММДД-ГГГГММДД`. Измерено 19.08.2026:
    един адрес върна 455 колежански мача за 57 дни. По ден щеше да са 57
    заявки за същото.

    ЗАЩО двойка: днешните се вадят от СЪЩИЯ отговор (добавено 25.08.2026).
    Алармата не струва нито една допълнителна заявка — иначе петте реда на
    календара щяха да станат десет заявки вместо пет.
    """
    u = (ESPN + "/" + sport + "/" + slug + "/scoreboard?dates="
         + ot.strftime("%Y%m%d") + "-" + do.strftime("%Y%m%d") + "&limit=1000")
    j = _json(u)
    # 🔴 ДВА АДРЕСА ОТКАЗВАТ ПЕРИОД (намерено живо 02.09.2026).
    #
    #   mens-college-basketball  ?dates=20261115           →  10 мача
    #   mens-college-basketball  ?dates=20261115-20261130  →  404
    #   womens-college-basketball — същото
    #
    # За nfl, nhl, nba, wnba, nbl и футбола периодът работи и носи по 455
    # мача с ЕДНА заявка, затова той остава пръв. Но без този отстъп новият
    # ред „NCAA баскетбол" в календара би давал ВЕЧЕН провал — а провал,
    # който вали всеки ден, спира да се чете, и точно така се губи
    # истинската тревога.
    #
    # Един ден стига за целта: будилникът пита „играе ли ДНЕС затворен
    # спорт", не „колко мача има за два месеца". Цената е нула допълнителни
    # заявки в нормалния случай — вторият опит се прави САМО след празен
    # отговор от периода.
    if not j:
        _den = (dnes or ot)
        j = _json(ESPN + "/" + sport + "/" + slug + "/scoreboard?dates="
                  + _den.strftime("%Y%m%d") + "&limit=1000")
        if j:
            print("   ℹ %s/%s не приема период — питах за един ден (%s)."
                  % (sport, slug, _den.isoformat()))
    return parse_espn(j), imena_na_den(j, (dnes or ot).isoformat())


def vzemi_nhl(ot, do, dnes=None):
    """Редовните мачове на НХЛ за период. -> (срещи, [днешни], обявен_старт).

    Едно повикване носи седмица. Обявеният старт се снема от първия отговор,
    който изобщо го носи — нула допълнителни заявки.
    """
    out, d, dnesni, dekl = [], ot, set(), None
    den = (dnes or ot).isoformat()
    while d <= do:
        j = _json(NHL + "/schedule/" + d.isoformat())
        out += parse_nhl(j)
        # застъпени седмици връщат един и същ мач два пъти — затова множество
        dnesni |= set(nhl_imena_na_den(j, den))
        dekl = dekl or nhl_start(j)
        d += datetime.timedelta(days=7)
    # едно и също име може да дойде от две застъпени седмици
    return sorted(set(out)), sorted(dnesni), dekl


# ------------------------------------------------------------------ СМЕТКА
def parvi_den(srechi):
    """Най-ранната дата с мач. None, ако няма нито един."""
    dni = sorted({d for d, _h, _a in srechi if d})
    return dni[0] if dni else None


def parva_sedmica(srechi, start, dni=SEDMICA):
    """Срещите в първите `dni` дни от старта, старта включително."""
    if not start:
        return []
    d0 = datetime.date.fromisoformat(start)
    d1 = d0 + datetime.timedelta(days=dni - 1)
    out = []
    for d, h, a in srechi:
        try:
            dd = datetime.date.fromisoformat(d)
        except ValueError:
            continue
        if d0 <= dd <= d1:
            out.append((d, h, a))
    return sorted(out)


def ceni_broi(kosh, srechi, pin):
    """Колко от срещите имат цена при Pinnacle. (с_цена, примери_без_цена).

    ЗАЩО през чуждия модул: това е ТОЧНО кодът, който предсказателят ще
    извика. Собствена реализация тук би измерила друго нещо.
    """
    if pin is None or not srechi:
        return 0, []
    sid = PIN_ID.get(kosh)
    if not sid:
        return 0, []
    pin.SPORT_ID[kosh] = sid          # ключът липсва в pinnacle.py — вж. патча
    s, bez = 0, []
    for _d, h, a in srechi:
        try:
            c = pin.ceni_za(kosh, h, a)
        except Exception:                                    # noqa: BLE001
            c = (None, None, None)
        if c[0] or c[1]:
            s += 1
        elif len(bez) < 3:
            bez.append(h + " - " + a)
    return s, bez


def pin_horizont(kosh, pin):
    """Докъде напред Pinnacle изобщо държи мачове за този спорт (в дни).

    ЗАЩО има значение: „0 с цена" за мач след 40 дни НЕ значи, че пазар няма
    — значи, че още не е отворен. Без това число будилникът лъже.
    """
    if pin is None or kosh not in PIN_ID:
        return None
    pin.SPORT_ID[kosh] = PIN_ID[kosh]
    try:
        st = sorted(v[3] for v in pin.machove(kosh).values() if v[3])
    except Exception:                                        # noqa: BLE001
        return None
    if not st:
        return None
    try:
        posl = datetime.date.fromisoformat(str(st[-1])[:10])
    except ValueError:
        return None
    return (posl - datetime.date.today()).days


def alarma_zatvoreni(kalendar, dnesni, zatvoreni):
    """Кои ЗАТВОРЕНИ спортове играят ДНЕС. -> [(име, кош, [мачове])].

    Това е алармата, поръчана на 25.08.2026. Гърми на ЖИВИ данни: не пита
    календара кога СЕ ОЧАКВА да тръгне спортът, а източника има ли мач днес.
    """
    out = []
    for sp in kalendar:
        if sp.get("kosh") not in zatvoreni:
            continue
        m = sorted(dnesni.get(sp.get("kod")) or [])
        if m:
            out.append((sp.get("ime"), sp.get("kosh"), m))
    return out


def veche_v_sezon(zatvoreni, dnes):
    """Кой ЗАТВОРЕН спорт вече Е в сезон според ИЗМЕРЕНИТЕ дати. -> [(код, дата)].

    ЗАЩО ВТОРА аларма, щом първата гледа живо: първата зависи от това
    източникът да проговори. Замълчи ли (403, срив, празен отговор), тя дава
    нула и мълчанието изглежда точно като спокойствие — грешката, която вече
    е правена в този файл с НХЛ. Тази втора не пита никого: датата е закована
    и календарът просто минава покрай нея. За да млъкне и тя, трябва някой да
    изтрие числото — тоест нарочно, не случайно.
    """
    out = []
    for kod in sorted(OTVARYA):
        r = OTVARYA[kod] or {}
        if r.get("kosh") and r.get("kosh") in zatvoreni and str(r.get("data")) <= str(dnes):
            out.append((kod, r.get("data")))
    return out


def sverka_data(kod, izmereno):
    """Живото съвпада ли със закованото. -> (наред, текст). None = не знам.

    ЗАЩО не се съди с падащ тест: датите на лигите мърдат по устройство
    (НХЛ мести старта, колежът добавя мач в чужбина). Тест, който червенее
    при местене, учи хората да го заобикалят. Затова разминаването се ПЕЧАТА
    на всяко пускане и остава на човек да реши.
    """
    r = OTVARYA.get(kod)
    if not r:
        return None, "няма закована дата за " + str(kod)
    if not izmereno:
        return None, "източникът не даде дата — закованото остава " + str(r.get("data"))
    if str(izmereno) == str(r.get("data")):
        dop = "" if r.get("sigurno") else " (закованото е ПРЕДПОЛОЖЕНИЕ)"
        return True, "закованото " + _bg(r.get("data")) + " съвпада с живото" + dop
    return False, ("закованото " + _bg(r.get("data")) + " РАЗМИНАВА с живото "
                   + _bg(izmereno) + " — мерено 25.08.2026, провери източника")


# --------------------------------------------------------------- ДЕФЕКТИТЕ
def bug_hockey_extra(P, dni):
    """Пази ли hockey_fixtures оригиналното име. Иска мрежа. -> (наред, текст).

    ЗАЩО с подадени дни, а не с днешната дата: през август hockey_fixtures
    връща празно и проверката би минала фалшиво зелена. Дните идват от вече
    прочетения календар, тоест със сигурност има мач.
    """
    now = datetime.datetime.now(P.SOFIA)
    for d in dni[:4]:
        rows = P.hockey_fixtures(now, d)
        if rows:
            ex = rows[0].get("extra") or {}
            if ex.get("home_en"):
                return True, "hockey_fixtures пази home_en=" + str(ex.get("home_en"))
            return False, ("hockey_fixtures връща extra=" + json.dumps(ex, ensure_ascii=False)
                           + " за " + str(rows[0].get("home")) + " - " + str(rows[0].get("away"))
                           + " (" + str(len(rows)) + " мача на " + d + ")")
    # None значи НЕ ЗНАМ. Зелено тук би било лъжа: през август източникът
    # мълчи по устройство и нищо не е доказано.
    return None, "няма мачове за проба — дефектът НЕ Е проверен, нито оправен"


def zaguba_ot_defekti(P, PIN, srechi):
    """Колко цени губят двата дефекта. -> (загубени, общо, имена).

    ЗАЩО СИМУЛАЦИЯ, а не измерване: Pinnacle отваря хокея два дни преди мача,
    тоест на 19.08 няма НИТО ЕДНА истинска цена за 29.09 и въпросът „колко
    губим" няма как да се измери директно. Затова подхвърляме ТЕХНИЯ пазар с
    НАШИТЕ истински пълни имена от NHL /schedule („Carolina Hurricanes") и
    питаме с имената, които predictor праща ДНЕС.

    Числото е за геометрията на имената, не за парите. Казва се на глас.
    """
    if PIN is None or not srechi:
        return 0, 0, []
    PIN.SPORT_ID["hockey"] = PIN_ID["hockey"]
    st_m, st_p = PIN._kesh.get(("m", 19)), PIN._kesh.get(("p", 19))
    zagubeni, obshto = [], 0
    try:
        PIN._kesh[("m", 19)] = {str(i): (h, a, "NHL", "")
                                for i, (_d, h, a) in enumerate(srechi)}
        PIN._kesh[("p", 19)] = {str(i): (1.85, 1.95, None) for i in range(len(srechi))}
        now = datetime.datetime.now(P.SOFIA)
        for d in sorted({x[0] for x in srechi}):
            for fx in P.hockey_fixtures(now, d):
                obshto += 1
                ex = fx.get("extra") or {}
                c = PIN.ceni_za("hockey",
                                ex.get("home_en") or fx.get("home"),
                                ex.get("away_en") or fx.get("away"))
                if not (c[0] or c[1]):
                    zagubeni.append(str(fx.get("home")) + " - " + str(fx.get("away")))
    finally:
        for k, v in ((("m", 19), st_m), (("p", 19), st_p)):
            if v is None:
                PIN._kesh.pop(k, None)
            else:
                PIN._kesh[k] = v
    return len(zagubeni), obshto, zagubeni


def bug_rangers(P):
    """Изяжда ли BG_NAME хокейните имена. Без мрежа. -> (наред, текст)."""
    lo = []
    for ime in NHL_PRYAKORI:
        prev = P.bg_name(ime)
        if any("А" <= ch <= "я" or ch in "ЁёЍѝЎў" for ch in prev):
            lo.append(ime + " -> " + prev)
    if not lo:
        return True, "нито един прякор от НХЛ не се превежда"
    return False, (str(len(lo)) + " от " + str(len(NHL_PRYAKORI))
                   + " прякора стават кирилица: " + ", ".join(lo))


# 32-та прякора, както ги дава NHL /score (измерено 19.08.2026, 29.09-05.10).
NHL_PRYAKORI = [
    "Avalanche", "Blackhawks", "Blue Jackets", "Blues", "Bruins", "Canadiens",
    "Canucks", "Capitals", "Devils", "Ducks", "Flames", "Flyers",
    "Golden Knights", "Hurricanes", "Islanders", "Jets", "Kings", "Kraken",
    "Lightning", "Mammoth", "Maple Leafs", "Oilers", "Panthers", "Penguins",
    "Predators", "Rangers", "Red Wings", "Sabres", "Senators", "Sharks",
    "Stars", "Wild",
]


# ------------------------------------------------------------------ ИЗХОДЪТ
def _bg(d):
    """2026-09-29 -> 29.09."""
    try:
        return datetime.date.fromisoformat(d).strftime("%d.%m")
    except (ValueError, TypeError):
        return "?"


def zhivo(podrobno=False):
    """Будилникът: чете източниците и печата една карта за собственика."""
    dnes = datetime.date.today()
    do = dnes + datetime.timedelta(days=HORIZONT)
    try:
        import pinnacle as PIN
    except Exception:                                        # noqa: BLE001
        PIN = None

    print("🔔 БУДИЛНИК ЗА ЗАТВОРЕНИТЕ СПОРТОВЕ — " + dnes.strftime("%d.%m.%Y"))
    print("   гледам напред " + str(HORIZONT) + " дни, до " + do.strftime("%d.%m.%Y"))
    print("")

    hor = {}
    for kosh in sorted(PIN_ID):
        hor[kosh] = pin_horizont(kosh, PIN)

    gotovi, hok_dni, hok_srechi = [], [], []
    dnesni, nhl_dekl = {}, None
    for sp in KALENDAR:
        vid, sport, slug = sp["izvor"]
        provali_predi = _provali[0]
        if vid == "nhl":
            srechi, dnes_m, nhl_dekl = vzemi_nhl(dnes, do, dnes)
            hok_dni = sorted({d for d, _h, _a in srechi})
        else:
            srechi, dnes_m = vzemi_espn(sport, slug, dnes, do, dnes)
        dnesni[sp["kod"]] = dnes_m
        start = parvi_den(srechi)
        sedm = parva_sedmica(srechi, start)
        s_cena, bez = ceni_broi(sp["kosh"], sedm, PIN)
        if vid == "nhl":
            hok_srechi = sedm      # само първата седмица — тя се симулира после
        dyal = (100.0 * s_cena / len(sedm)) if sedm else 0.0
        h = hor.get(sp["kosh"])

        if not start:
            # 🔴 „Нула мача" и „източникът мълчи" изглеждат ЕДНАКВО отвън.
            # Точно това ме подведе първия път: НХЛ даваше 403, а картата
            # спокойно пишеше „няма нито един мач".
            if provali_predi != _provali[0]:
                print("%-24s ❌ ИЗТОЧНИКЪТ МЪЛЧИ (%d провалени заявки) — това НЕ"
                      " значи, че сезон няма" % (sp["ime"], _provali[0] - provali_predi))
            else:
                print("%-24s няма нито един мач до %s" % (sp["ime"], do.strftime("%d.%m")))
            print("")
            continue
        ost = (datetime.date.fromisoformat(start) - dnes).days
        kraj = datetime.date.fromisoformat(start) + datetime.timedelta(days=SEDMICA - 1)
        print("%-24s тръгва %s · след %d дни" % (sp["ime"], _bg(start), ost))
        print("   първа седмица (%s-%s): %d мача · цена за %d (%.0f%%)"
              % (_bg(start), kraj.strftime("%d.%m"), len(sedm), s_cena, dyal))
        sv_ok, sv_txt = sverka_data(sp["kod"], start)
        print("   " + ("📌 " if sv_ok else ("⚠ " if sv_ok is None else "🔴 ")) + sv_txt)
        if vid == "nhl" and nhl_dekl:
            print("   НХЛ обявява regularSeasonStartDate=" + nhl_dekl
                  + " · nextStartDate НЕ Е това (вж. nhl_start)")
        # Честната уговорка: нула цена за далечен мач не е липса на пазар.
        if s_cena == 0 and h is not None and ost > h:
            print("   ⏳ Pinnacle държи този спорт само %d дни напред — пазарът"
                  " още не е отворен, числото ще порасне." % h)
        elif bez:
            print("   без цена, примери: " + " · ".join(bez))
        if sp.get("beleshka"):
            print("   " + sp["beleshka"])
        if podrobno:
            for d, hh, aa in sedm[:6]:
                print("      %s  %s - %s" % (_bg(d), hh[:26], aa[:26]))
        gotovi.append((sp, start, len(sedm), s_cena))
        print("")

    # --------- дефектите, които ще ухапят точно на старта
    print("🔴 ДВАТА ДЕФЕКТА ПРЕДИ ОТВАРЯНЕТО")
    try:
        import os
        os.environ.setdefault("PREDICT_IZKL", "")
        import predictor as P
    except Exception as e:                                   # noqa: BLE001
        print("   не мога да заредя predictor.py: " + str(e)[:70])
        P = None
    if P is not None:
        for ime, (ok, txt) in (("1 · hockey_fixtures без home_en", bug_hockey_extra(P, hok_dni)),
                               ("2 · BG_NAME яде хокейните имена", bug_rangers(P))):
            print(("   ⚠ " if ok is None else ("   ✅ " if ok else "   ❌ ")) + ime)
            print("      " + txt)
        z, obshto, imena = zaguba_ot_defekti(P, PIN, hok_srechi)
        if obshto:
            print("   ЦЕНАТА НА ДВАТА ДЕФЕКТА (симулация с техния пазар, наши имена):")
            print("      %d от %d мача в първата седмица на НХЛ остават без цена"
                  % (z, obshto))
            for i in imena[:6]:
                print("        · " + i)
    print("")

    # --------- алармата: затворен спорт, който вече играе
    zatv = zatvoreni_pri_starta()
    trevoga = alarma_zatvoreni(KALENDAR, dnesni, zatv)
    v_sezon = veche_v_sezon(zatv, dnes.isoformat())
    print("⏰ ЗАТВОРЕН ЛИ Е СПОРТ, КОЙТО ВЕЧЕ ИГРАЕ?")
    print("   ключалката държи: " + (", ".join(sorted(zatv)) if zatv else "нищо"))
    for ime, kosh, m in trevoga:
        print("   🔴🔴 ГЪРМИ · %s (%s) има %d мача ДНЕС, а стаята е затворена"
              % (ime, kosh, len(m)))
        for x in m[:4]:
            print("        · " + x)
    for kod, d in v_sezon:
        print("   🔴 ГЪРМИ · %s е в сезон от %s по ИЗМЕРЕНАТА дата, а кошът"
              " %s е затворен" % (kod, _bg(d), OTVARYA[kod]["kosh"]))
    if not trevoga and not v_sezon:
        naj_blizo = sorted((r["data"], k) for k, r in OTVARYA.items()
                           if r.get("kosh") and r["kosh"] in zatv
                           and str(r["data"]) > dnes.isoformat())
        print("   не · нито един затворен спорт няма мач днес"
              + ((" · пръв е %s на %s" % (naj_blizo[0][1], _bg(naj_blizo[0][0])))
                 if naj_blizo else ""))
    print("")

    # --------- заповедта
    print("🔓 КАК СЕ ОТВАРЯТ (пътят назад е една променлива)")
    print("   PREDICT_IZKL=\"\"                — връща и двата спорта")
    print("   PREDICT_IZKL=\"hockey\"          — само американският футбол")
    print("   PREDICT_IZKL=\"amfootball\"      — само хокеят")
    naj = [g for g in gotovi if g[0]["vazhen"]]
    if naj:
        prv = min(naj, key=lambda g: g[1])
        print("   Първата дата, на която стая ще е празна без това: "
              + _bg(prv[1]) + " (" + prv[0]["ime"] + ")")
    print("")
    print("заявки: %d мои (%d провалени) + %d на pinnacle"
          % (broi_zayavki(), broi_provali(), (PIN.broi_zayavki() if PIN else 0)))
    for z in _zashto:
        print("   провал: " + z)
    # 2 значи „затворен спорт вече играе" — будилникът е свършил работата си.
    return 2 if (trevoga or v_sezon) else 0


# --------------------------------------------------------------- ПРОВЕРКИТЕ
_PROBA_ESPN = {
    "events": [
        {"date": "2026-09-13T17:00Z", "season": {"slug": "regular-season"},
         "competitions": [{"status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "away", "team": {"displayName": "Dallas Cowboys"}},
                               {"homeAway": "home", "team": {"displayName": "New York Giants"}}]}]},
        {"date": "2026-08-22T17:00Z", "season": {"slug": "preseason"},
         "competitions": [{"status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "home", "team": {"displayName": "Тест Пре"}},
                               {"homeAway": "away", "team": {"displayName": "Тест Гост"}}]}]},
        {"date": "2026-09-14T17:00Z", "season": {"slug": "regular-season"},
         "competitions": [{"status": {"type": {"state": "post"}},
                           "competitors": [
                               {"homeAway": "home", "team": {"displayName": "Изигран"}},
                               {"homeAway": "away", "team": {"displayName": "Изигран 2"}}]}]},
        {"date": "2026-09-20T17:00Z", "season": {"slug": "regular-season"},
         "competitions": [{"status": {"type": {"state": "pre"}},
                           "type": {"abbreviation": "PRE"},
                           "competitors": [
                               {"homeAway": "home", "team": {"displayName": "Втори пре"}},
                               {"homeAway": "away", "team": {"displayName": "Втори гост"}}]}]},
    ]
}

_PROBA_NHL = {
    "gameWeek": [
        {"date": "2026-09-26", "games": [
            {"gameType": 1, "gameState": "FUT",
             "homeTeam": {"placeName": {"default": "Boston"}, "commonName": {"default": "Bruins"}},
             "awayTeam": {"placeName": {"default": "Buffalo"}, "commonName": {"default": "Sabres"}}}]},
        {"date": "2026-09-29", "games": [
            {"gameType": 2, "gameState": "FUT",
             "homeTeam": {"placeName": {"default": "Carolina"}, "commonName": {"default": "Hurricanes"}},
             "awayTeam": {"placeName": {"default": "Florida"}, "commonName": {"default": "Panthers"}}},
            {"gameType": 2, "gameState": "FINAL",
             "homeTeam": {"placeName": {"default": "New York"}, "commonName": {"default": "Rangers"}},
             "awayTeam": {"placeName": {"default": "New York"}, "commonName": {"default": "Islanders"}}}]},
        {"date": "2026-10-06", "games": [
            {"gameType": 2, "gameState": "FUT",
             "homeTeam": {"placeName": {"default": "New York"}, "commonName": {"default": "Rangers"}},
             "awayTeam": {"placeName": {"default": "Toronto"}, "commonName": {"default": "Maple Leafs"}}}]},
    ]
}


# Отговорът на api-web.nhle.com/v1/schedule/now, свален на 25.08.2026 и
# орязан. Четирите дати са ТОЧНО както ги върна източникът — това е капанът
# от `nhl_start`, замразен, за да не може да се сбърка пак.
_PROBA_NHL_SEGA = {
    "regularSeasonStartDate": "2026-09-29",
    "preSeasonStartDate": "2026-09-19",
    "nextStartDate": "2026-10-06",
    "previousStartDate": "2026-09-22",
    "regularSeasonEndDate": "2027-04-10",
    "gameWeek": [
        {"date": "2026-09-29", "games": [
            {"gameType": 2, "gameState": "FINAL",
             "homeTeam": {"placeName": {"default": "Carolina"},
                          "commonName": {"default": "Hurricanes"}},
             "awayTeam": {"placeName": {"default": "Florida"},
                          "commonName": {"default": "Panthers"}}},
            {"gameType": 1, "gameState": "FUT",
             "homeTeam": {"placeName": {"default": "Boston"},
                          "commonName": {"default": "Bruins"}},
             "awayTeam": {"placeName": {"default": "Buffalo"},
                          "commonName": {"default": "Sabres"}}}]},
        {"date": "2026-09-30", "games": [
            {"gameType": 2, "gameState": "FUT",
             "homeTeam": {"placeName": {"default": "Philadelphia"},
                          "commonName": {"default": "Flyers"}},
             "awayTeam": {"placeName": {"default": "Pittsburgh"},
                          "commonName": {"default": "Penguins"}}}]},
    ],
}

# Един ден от ESPN с ТРИ различни мача: изигран редовен, предсезонен и утрешен.
# Изиграният е сърцето на пробата — точно него `parse_espn` изхвърля.
_PROBA_ESPN_DNES = {
    "events": [
        {"date": "2026-08-29T16:00Z", "season": {"slug": "regular-season"},
         "competitions": [{"status": {"type": {"state": "post"}},
                           "competitors": [
                               {"homeAway": "home",
                                "team": {"displayName": "Ohio State Buckeyes"}},
                               {"homeAway": "away",
                                "team": {"displayName": "Texas Longhorns"}}]}]},
        {"date": "2026-08-29T20:00Z", "season": {"slug": "preseason"},
         "competitions": [{"status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "home", "team": {"displayName": "Пре Дом"}},
                               {"homeAway": "away", "team": {"displayName": "Пре Гост"}}]}]},
        {"date": "2026-08-30T16:00Z", "season": {"slug": "regular-season"},
         "competitions": [{"status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "home", "team": {"displayName": "Утре Дом"}},
                               {"homeAway": "away", "team": {"displayName": "Утре Гост"}}]}]},
    ]
}


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # --- четенето на ESPN
    e = parse_espn(_PROBA_ESPN)
    check("ESPN: остава само неиграният редовен мач", len(e) == 1)
    check("ESPN: датата е отрязана до деня", e and e[0][0] == "2026-09-13")
    check("ESPN: домакинът е по homeAway, не по реда",
          e and e[0][1] == "New York Giants" and e[0][2] == "Dallas Cowboys")
    check("ESPN: предсезонният по season.slug пада",
          all("Пре" not in x[1] for x in e))
    check("ESPN: предсезонният по type.abbreviation пада",
          all("Втори" not in x[1] for x in e))
    check("ESPN: изиграният пада", all("Изигран" not in x[1] for x in e))
    check("ESPN: празният вход не гърми", parse_espn(None) == [] and parse_espn({}) == [])

    # --- четенето на НХЛ
    n = parse_nhl(_PROBA_NHL)
    check("НХЛ: предсезонният (gameType 1) пада",
          all("Bruins" not in x[1] for x in n))
    check("НХЛ: изиграният (FINAL) пада", len(n) == 2)
    check("НХЛ: пълното име, не прякорът",
          n and n[0][1] == "Carolina Hurricanes" and n[0][2] == "Florida Panthers")
    check("НХЛ: Rangers идва с града", any(x[1] == "New York Rangers" for x in n))
    check("НХЛ: празният вход не гърми", parse_nhl(None) == [] and parse_nhl({}) == [])

    # --- сметката за първата седмица
    check("първият ден е най-ранният", parvi_den(n) == "2026-09-29")
    check("празният списък няма първи ден", parvi_den([]) is None)
    s = parva_sedmica(n, "2026-09-29")
    check("седмицата хваща 29.09", any(x[0] == "2026-09-29" for x in s))
    check("седмицата НЕ хваща 06.10 (осмият ден)",
          all(x[0] != "2026-10-06" for x in s))
    check("седмицата хваща 05.10 (седмият ден)",
          len(parva_sedmica([("2026-10-05", "а", "б")], "2026-09-29")) == 1)
    check("без старт няма седмица", parva_sedmica(n, None) == [])
    check("боклук за дата не гърми",
          parva_sedmica([("нещо", "а", "б")], "2026-09-29") == [])

    # --- 🔴 КАПАНЪТ nextStartDate (добавено 25.08.2026)
    # Пробата носи ЧЕТИРИ дати наведнъж, защото сбъркването им е безшумно:
    # всяка от тях е правдоподобно „начало на НХЛ".
    check("НХЛ: стартът е regularSeasonStartDate",
          nhl_start(_PROBA_NHL_SEGA) == "2026-09-29")
    check("🔴 НХЛ: стартът НЕ Е nextStartDate (щеше да закъснее 7 дни)",
          nhl_start(_PROBA_NHL_SEGA) != _PROBA_NHL_SEGA["nextStartDate"])
    check("🔴 НХЛ: стартът НЕ Е preSeasonStartDate (щеше да подрани 10 дни)",
          nhl_start(_PROBA_NHL_SEGA) != _PROBA_NHL_SEGA["preSeasonStartDate"])
    check("НХЛ: стартът НЕ Е previousStartDate",
          nhl_start(_PROBA_NHL_SEGA) != _PROBA_NHL_SEGA["previousStartDate"])
    check("НХЛ: без поле няма старт",
          nhl_start({}) is None and nhl_start(None) is None)
    check("НХЛ: пресечена дата не минава за старт",
          nhl_start({"regularSeasonStartDate": "2026"}) is None)

    # --- мачовете ДНЕС (основата на алармата)
    d0 = "2026-08-29"
    dn = imena_na_den(_PROBA_ESPN_DNES, d0)
    check("ДНЕС: изиграният мач СЕ БРОИ", dn == ["Ohio State Buckeyes - Texas Longhorns"])
    # 🔴 Без тази проверка новата функция може тихо да е втори `parse_espn`.
    check("🔴 ДНЕС: `parse_espn` НЕ го вижда — двете мерят различно",
          all("Ohio State" not in x[1] for x in parse_espn(_PROBA_ESPN_DNES)))
    check("ДНЕС: предсезонният не се брои за сезон",
          all("Пре" not in x for x in dn))
    check("ДНЕС: утрешният не е днешен", all("Утре" not in x for x in dn))
    check("ДНЕС: чужд ден дава празно", imena_na_den(_PROBA_ESPN_DNES, "2026-09-09") == [])
    check("ДНЕС: празният вход не гърми",
          imena_na_den(None, d0) == [] and imena_na_den({}, d0) == [])

    hn = nhl_imena_na_den(_PROBA_NHL_SEGA, "2026-09-29")
    check("ДНЕС/НХЛ: изиграният (FINAL) СЕ БРОИ",
          hn == ["Carolina Hurricanes - Florida Panthers"])
    check("ДНЕС/НХЛ: предсезонният (gameType 1) не се брои",
          all("Bruins" not in x for x in hn))
    check("ДНЕС/НХЛ: чужд ден дава празно",
          nhl_imena_na_den(_PROBA_NHL_SEGA, "2026-10-06") == [])
    check("ДНЕС/НХЛ: празният вход не гърми",
          nhl_imena_na_den(None, d0) == [] and nhl_imena_na_den({}, d0) == [])

    # --- ключалката: липсваща променлива и празна променлива НЕ са едно
    # 🔴 ОБЪРНАТА 02.09.2026, не изтрита. Дотук тук се заковаваше, че
    # липсващата променлива значи {"hockey","amfootball"} — копие на
    # подразбирането от 11.08. Същия ден амер. футбол беше ОТВОРЕН
    # (predict.yml вече казва «hockey»), а копието държеше будилника
    # да вика «затворен спорт играе» вечно. Сега липсващата променлива
    # значи «питай живия predict.yml», и САМО ако и той мълчи — старият
    # списък. Намерението е същото: липсващо и празно НЕ са едно.
    check("ключалка: липсваща променлива пита ЖИВИЯ yml",
          razcheti_izkl(None, chetec=lambda: "PREDICT_IZKL: ${{ v || 'hockey' }}") == {"hockey"})
    check("ключалка: без ключ И без yml = старият списък",
          razcheti_izkl(None, chetec=lambda: None)
          == {"hockey", "amfootball"})
    check("🔴 ключалка: ПРАЗЕН низ = нищо затворено (не е същото като липсваща)",
          razcheti_izkl("") == set())
    check("ключалка: един спорт", razcheti_izkl("hockey") == {"hockey"})
    check("ключалка: интервали и главни букви се търпят",
          razcheti_izkl(" Hockey , AmFootball ") == {"hockey", "amfootball"})

    # --- 🔔 АЛАРМАТА: затворен спорт с мач ДНЕС
    tr = alarma_zatvoreni(KALENDAR, {"ncaaf": ["A - B", "C - D"]}, {"amfootball"})
    check("🔔 АЛАРМА: затворен спорт с мач днес ГЪРМИ", len(tr) == 1)
    check("🔔 АЛАРМА: носи и самите мачове, не само брой",
          tr and tr[0][2] == ["A - B", "C - D"] and tr[0][1] == "amfootball")
    check("АЛАРМА: отворен спорт с мач днес МЪЛЧИ",
          alarma_zatvoreni(KALENDAR, {"ncaaf": ["A - B"]}, set()) == [])
    check("АЛАРМА: затворен спорт БЕЗ мач днес мълчи",
          alarma_zatvoreni(KALENDAR, {}, {"amfootball", "hockey"}) == [])
    check("АЛАРМА: чужд кош не гърми (хокей играе, но е отворен)",
          alarma_zatvoreni(KALENDAR, {"nhl": ["X - Y"]}, {"amfootball"}) == [])
    check("АЛАРМА: празен списък мачове не се брои за мач",
          alarma_zatvoreni(KALENDAR, {"nhl": []}, {"hockey"}) == [])

    # --- втората аларма: по ИЗМЕРЕНАТА дата, без да пита никого
    check("дата-аларма: на 25.08 колежанският футбол ОЩЕ не е в сезон",
          ("ncaaf", "2026-08-29") not in veche_v_sezon({"amfootball"}, "2026-08-25"))
    check("🔔 дата-аларма: на 29.08 колежанският футбол ГЪРМИ",
          ("ncaaf", "2026-08-29") in veche_v_sezon({"amfootball"}, "2026-08-29"))
    check("дата-аларма: на 29.09 хокеят ГЪРМИ",
          ("nhl", "2026-09-29") in veche_v_sezon({"hockey"}, "2026-09-29"))
    # 🔴 ТУК СБЪРКАХ АЗ, НЕ КОДЪТ (25.08.2026). Написах „на 28.09 хокеят още
    # мълчи" по памет — че хокеят значи НХЛ. Проверката падна и ме прати да
    # погледна: NCAA хокей за ЖЕНИ отваря на 18.09, ЕДИНАЙСЕТ дни преди НХЛ,
    # и е в същия кош „hockey". Тоест кошът е в сезон от 18.09, а не от 29.09.
    # Числото не е от паметта ми: ESPN womens-college-hockey, прозорец
    # 25.08-20.11, 316 мача regular-season, най-ранен 18.09.
    # За СТАИТЕ това още не значи карти — `predictor` няма такъв източник
    # (виж бележката при ncaahw в КАЛЕНДАРА). Затова редът е vazhen=False,
    # но датата остава закована: кошът отваря тогава.
    check("дата-аларма: на 17.09 целият кош хокей още мълчи",
          veche_v_sezon({"hockey"}, "2026-09-17") == [])
    check("🔴 дата-аларма: на 18.09 жените отварят коша ПРЕДИ НХЛ",
          veche_v_sezon({"hockey"}, "2026-09-18") == [("ncaahw", "2026-09-18")])
    check("дата-аларма: на 29.09 в коша хокей вече има ДВА отворени спорта",
          veche_v_sezon({"hockey"}, "2026-09-29")
          == [("ncaahw", "2026-09-18"), ("nhl", "2026-09-29")])
    check("дата-аларма: празна ключалка не гърми никога",
          veche_v_sezon(set(), "2027-01-01") == [])
    # 🔴 Това доказва, че редовете за NBA и евро футбола НЕ СА украса: щом
    # кошът им попадне в ключалката, те се обаждат по същия път.
    check("🔴 затвори ли се football, евро футболът се обажда САМ",
          veche_v_sezon({"football"}, "2026-08-25") == [("evrofutbol", "2026-08-15")])
    check("днес нито баскетболът, нито футболът са затворени -> мълчат",
          veche_v_sezon({"hockey", "amfootball"}, "2026-08-25") == [])
    check("затвори ли се basketball, NBA мълчи до 20.10 и гърми на 20.10",
          veche_v_sezon({"basketball"}, "2026-10-19") == []
          and veche_v_sezon({"basketball"}, "2026-10-20") == [("nba", "2026-10-20")])

    # --- сверката закованото срещу живото
    check("сверка: съвпадението е зелено", sverka_data("nhl", "2026-09-29")[0] is True)
    check("сверка: разминаването е червено и носи ДВЕТЕ дати",
          sverka_data("nhl", "2026-10-06")[0] is False
          and "29.09" in sverka_data("nhl", "2026-10-06")[1]
          and "06.10" in sverka_data("nhl", "2026-10-06")[1])
    check("🔴 сверка: МЪЛЧАЩ източник е НЕ ЗНАМ, а не разминаване",
          sverka_data("nhl", None)[0] is None)
    check("сверка: непознат код е НЕ ЗНАМ", sverka_data("нещо", "2026-09-29")[0] is None)
    check("сверка: несигурната дата се казва на глас",
          "ПРЕДПОЛОЖЕНИЕ" in sverka_data("evrofutbol", "2026-08-15")[1])
    check("сверка: сигурната дата НЕ се обявява за предположение",
          "ПРЕДПОЛОЖЕНИЕ" not in sverka_data("nhl", "2026-09-29")[1])

    # --- закованите дати: цялост
    check("всеки ред от календара има закована дата",
          all(s["kod"] in OTVARYA for s in KALENDAR))
    check("всяка закована дата е истинска дата",
          all(datetime.date.fromisoformat(r["data"]) for r in OTVARYA.values()))
    check("всяка закована дата носи източник с числа",
          all(len(str(r.get("izvor") or "")) > 40 for r in OTVARYA.values()))
    check("измереното 25.08.2026: НХЛ 29.09, НФЛ 10.09, колежът 29.08",
          OTVARYA["nhl"]["data"] == "2026-09-29"
          and OTVARYA["nfl"]["data"] == "2026-09-10"
          and OTVARYA["ncaaf"]["data"] == "2026-08-29")
    check("всеки кош в закованото е познат кош",
          all(r["kosh"] in ("hockey", "amfootball", "basketball", "football")
              for r in OTVARYA.values()))

    # --- имената на НХЛ
    check("името се сглобява от град и прякор",
          _nhl_ime({"placeName": {"default": "Florida"},
                    "commonName": {"default": "Panthers"}}) == "Florida Panthers")
    check("градът не се удвоява",
          _nhl_ime({"placeName": {"default": "Utah"},
                    "commonName": {"default": "Utah Mammoth"}}) == "Utah Mammoth")
    check("само прякор пак върши работа",
          _nhl_ime({"name": {"default": "Capitals"}}) == "Capitals")
    check("съкращението е последна спирка",
          _nhl_ime({"abbrev": "WSH"}) == "WSH")

    # --- Pinnacle: имената, които ще търсим
    try:
        import pinnacle as PIN
    except Exception:                                        # noqa: BLE001
        PIN = None
    check("pinnacle.py се внася", PIN is not None)
    if PIN is not None:
        check("🔴 pinnacle.py НЯМА хокей — затова го добавяме тук",
              "hockey" not in PIN.SPORT_ID or PIN.SPORT_ID.get("hockey") == 19)
        check("американският футбол е 15, хокеят е 19",
              PIN_ID["amfootball"] == 15 and PIN_ID["hockey"] == 19)
        # 🔴 ГЛАВНАТА ПРОВЕРКА В ФАЙЛА. Подхвърляме пазара на Pinnacle точно
        # какъвто е (пълни имена) и питаме два пъти: веднъж с ПРЕВЕДЕНОТО име
        # (каквото predictor праща днес) и веднъж с АНГЛИЙСКОТО (каквото ще
        # праща след патча). Ако първото намери мача, дефект няма. Намира ли
        # само второто — дефектът е доказан БЕЗ да чакаме септември.
        st_m = PIN._kesh.get(("m", 19))
        st_p = PIN._kesh.get(("p", 19))
        try:
            PIN.SPORT_ID["hockey"] = 19
            PIN._kesh[("m", 19)] = {
                "900": ("New York Rangers", "Carolina Hurricanes", "NHL", ""),
            }
            PIN._kesh[("p", 19)] = {"900": (1.85, 1.95, None)}
            kir = PIN.ceni_za("hockey", "Рейнджърс", "Hurricanes")
            ang = PIN.ceni_za("hockey", "Rangers", "Hurricanes")
            check("🔴 кирилицата НЕ намира мача (дефект 2, доказан)",
                  kir == (None, None, None))
            check("английският прякор го намира", ang == (1.85, 1.95, None))
            check("нулата мрежа се пази", broi_zayavki() == 0)
        finally:
            for k, v in ((("m", 19), st_m), (("p", 19), st_p)):
                if v is None:
                    PIN._kesh.pop(k, None)
                else:
                    PIN._kesh[k] = v
        check("кешът е чист след теста", ("m", 19) not in PIN._kesh)

    # --- дефект 2 срещу ЖИВИЯ predictor (пак без мрежа — само речник)
    try:
        import os
        os.environ.setdefault("PREDICT_IZKL", "")
        import predictor as P
    except Exception:                                        # noqa: BLE001
        P = None
    check("predictor.py се внася", P is not None)

    # 🔴 ТЪРСАЧЪТ СЕ ИЗПИТВА В ДВЕТЕ ПОСОКИ, НЕ СРЕЩУ ЖИВИЯ ФАЙЛ.
    # Ако тук стоеше „BG_NAME трябва да е счупен", файлът щеше да ПОЧЕРВЕНЕЕ
    # в деня, в който някой приложи патча — тоест наградата за поправката
    # щеше да е счупен тест. Затова проверяваме, че `bug_rangers` вижда и
    # двете състояния, а живото състояние се ПЕЧАТА, не се съди.
    class _Fake(object):
        def __init__(self, karta):
            self.karta = karta

        def bg_name(self, s):
            return self.karta.get(s, s)

    check("търсачът вижда превода", bug_rangers(_Fake({"Rangers": "Рейнджърс"}))[0] is False)
    check("търсачът мълчи, когато превод няма", bug_rangers(_Fake({}))[0] is True)
    check("търсачът брои колко точно",
          "1 от 32" in bug_rangers(_Fake({"Rangers": "Рейнджърс"}))[1])
    check("латиницата не се брои за превод",
          bug_rangers(_Fake({"Rangers": "Glasgow Rangers"}))[0] is True)

    # Същото и за дефект 1 — с подхвърлен predictor, нула мрежа.
    class _FakeP(object):
        SOFIA = datetime.timezone.utc

        def __init__(self, ex):
            self.ex = ex

        def hockey_fixtures(self, now, d):
            if self.ex is None:
                return []
            return [{"home": "Рейнджърс", "away": "Hurricanes", "extra": self.ex}]

    check("дефект 1: празният extra е ЧЕРВЕН",
          bug_hockey_extra(_FakeP({}), ["2026-09-29"])[0] is False)
    check("дефект 1: home_en е ЗЕЛЕН",
          bug_hockey_extra(_FakeP({"home_en": "New York Rangers"}), ["2026-09-29"])[0] is True)
    check("дефект 1: празният ден е НЕ ЗНАМ, а не зелено",
          bug_hockey_extra(_FakeP(None), ["2026-09-29"])[0] is None)
    check("дефект 1: без дни изобщо е НЕ ЗНАМ",
          bug_hockey_extra(_FakeP({}), [])[0] is None)

    if P is not None:
        r_ok, r_txt = bug_rangers(P)
        print("   живо състояние на дефект 2: " + ("наред — " if r_ok else "ЖИВ — ") + r_txt)

    # 🔴 ПОДПИСИТЕ. Тази проверка съществува, защото точно тук сгреших:
    # един подпис за двата източника направи НХЛ ням, а картата остана зелена.
    check("ESPN пътува БЕЗ подпис",
          "User-Agent" not in glavi_za("https://site.api.espn.com/x"))
    check("НХЛ пътува С подпис",
          glavi_za("https://api-web.nhle.com/v1/schedule/2026-09-29").get("User-Agent") == UA)
    check("Pinnacle също е с подпис (не е ESPN)",
          "User-Agent" in glavi_za("https://guest.api.arcadia.pinnacle.com/0.1/sports"))

    # 🔴 КАЛЕНДАРЪТ ПОРАСНА 5 → 11 (02.09.2026). Дотук знаеше САМО два
    # спорта — американски футбол и хокей. Тоест НБА можеше да тръгне, ботът
    # да мълчи, и никой да не предупреди; точно дефектът, срещу който този
    # файл съществува. Проверките са ПРЕНАСОЧЕНИ, не изтрити: старите три
    # важни трябва да ги има и досега, плюс новите.
    check("календарът има поне осем реда", len(KALENDAR) >= 8)
    check("всеки ред знае коша си",
          all(s["kosh"] in ("hockey", "amfootball", "basketball")
              for s in KALENDAR))
    check("всеки ред носи бележка", all(s.get("beleshka") for s in KALENDAR))
    check("кодовете са различни",
          len({s["kod"] for s in KALENDAR}) == len(KALENDAR))
    # 🔴 ИМЕНАТА СА ИЗПИСАНИ ДОСЛОВНО, а не взети от KALENDAR — инак махането
    # на ред щеше да мине незабелязано, защото проверката щеше да пита
    # самата себе си. Днес такава проверка вече пропусна мутация в друг файл.
    _vazhni = [s["kod"] for s in KALENDAR if s["vazhen"]]
    for _k in ("nfl", "ncaaf", "nhl"):
        check("старият важен ред " + _k + " е още там", _k in _vazhni)
    for _k in ("nba", "ncaab"):
        check("новият важен ред " + _k + " е добавен", _k in _vazhni)
    for _k in ("wnba", "atp", "wta"):
        check("текущата лига " + _k + " НЕ е в сезонния календар",
              _k not in {s["kod"] for s in KALENDAR})
    check("баскетболът вече се следи",
          any(s["kosh"] == "basketball" for s in KALENDAR))
    check("тенисът НЕ е в сезонния календар (тече, не отваря)",
          not any(s["kosh"] == "tennis" for s in KALENDAR))
    # И че НЕ сме добавили спорт без извор — това би било вечна тревога.
    check("няма ред за клубен волейбол (нямаме извор)",
          not any(s["kosh"] == "volleyball" for s in KALENDAR))
    check("няма ред за европейски хокей (нямаме резултати)",
          not any("кхл" in str(s["ime"]).lower() or "khl" in str(s["kod"]).lower()
                  for s in KALENDAR))
    check("седмицата е 7 дни", SEDMICA == 7)
    check("нула мрежа в цялата самопроверка", broi_zayavki() == 0)
    check("нула провалени заявки, щом няма заявки", broi_provali() == 0)
    # Долна граница на БРОЯ: проверка, която тихо се самоизключи (върнат
    # рано `if`, изяден блок), се вижда само тук. Числото е измереното на
    # 25.08.2026 след добавянето на алармата — 50 стари + 39 нови.
    _proveri_izkl(check)
    check("броят проверки е поне 118", ok >= 118)

    print("САМОПРОВЕРКА НА SEZON: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(zhivo(podrobno=("--zhivo" in sys.argv)))
