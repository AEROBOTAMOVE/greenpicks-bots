# -*- coding: utf-8 -*-
"""ПАЗАЧЪТ — единственото нещо в бота, чиято работа е да ЗАБЕЛЯЗВА мълчанието.

═══════════════════════════════════════════════════════════════════════════
ЗАЩО СЪЩЕСТВУВА (25.08.2026) — измерено, не предположено
═══════════════════════════════════════════════════════════════════════════

Оценителят гърмя ТРИ пъти подред и резултатите в канала спряха за 33 часа.
Собственикът го откри. Не системата.

А системата ИМАШЕ пазач. `zdrave.py` брои червените рънове и на 24.08 в 20:34
— когато score.yml вече беше гръмнал два пъти — написа:

    последните 30 рънa в CI: 0 червени

Не беше повреден. Беше СТРУКТУРНО сляп, и ето числото, което го доказва:
питаше `actions/runs?per_page=30` — общия списък на ВСИЧКИ workflow-и.
Измерено живо на 25.08 в 05:00: тези 30 рънa са 26 рутерски, 3 съпорт и
1 hub, и покриват **1.8 ЧАСА**. Рутерът пуска ~14 рънa на час и залива
списъка. Оценителят гърми на всеки ~9 часа.

Тоест провалът на оценителя НИКОГА не можеше да попадне в прозореца.
Това не е лош късмет. Това е пазач, който гледа в грешната посока.

═══════════════════════════════════════════════════════════════════════════
ТРИТЕ ПРАВИЛА, ПО КОИТО Е ПОСТРОЕН ТОЗИ ФАЙЛ
═══════════════════════════════════════════════════════════════════════════

1. ПИТА СЕ ПО WORKFLOW, НЕ ОБЩО. Всеки workflow има свой прозорец. Един
   бъбрив съсед не бива да заглушава мълчалив.

2. „ПИТАХ И НЯМА" НЕ Е „НЕ МОЖАХ ДА ПИТАМ". Това уби предишния пазач: при
   отказ той връщаше празен списък, а празният списък се четеше като „чисто".
   Тук отказът има собствено име (`NEPITAN`) и сам по себе си е тревога, ако
   се повтори. Няма път, по който този файл да каже „наред", без да е питал.

3. ПРАГЪТ СЕ СМЯТА ОТ CRON-А, НЕ СЕ ЗАБИВА. Разписанието е истината за това
   колко често трябва да се вижда рън. Забит на ръка праг остарява мълчаливо
   в деня, в който някой смени cron-а.

   Към пресметнатия период се добавя ГРАТИС, защото GitHub cron закъснява:
   измерено върху 55 пускания (12.08.2026) — медиана 65 минути.
   ПРЕМЕРЕНО ОТНОВО НА ЖИВО 02.09.2026 върху 74 планирани рънa на шестте
   следени workflow-а: медиана 30 мин, 90-и персентил 158 мин, максимум
   231 мин, 17 от 74 над час. Тоест средата се е ПОДОБРИЛА в средата и е
   ВЛОШИЛА в опашката — а прагът се чупи от опашката, не от медианата.
   Затова гратисът вече не е плосък; виж GRATIS_KRAT по-долу.
   Пазач без този гратис би крещял всяка сутрин и щеше да се научи да бъде
   пренебрегван. А пазач, когото пренебрегват, не е пазач.
"""

import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("PAZACH_REPO") or "AEROBOTAMOVE/greenpicks-bots"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# Тревогата отива в РАБОТНАТА ГРУПА, никога в публичния канал. Читателят на
# канала не бива да вижда, че на бота му е зле — това е разговор между
# собственика и машината.
def kade_pishe(sreda=None):
    """Къде отива тревогата. Празно значи „никъде" и се казва на глас.

    Отделна функция, за да може да се ИЗПИТА. Първата ми версия проверяваше
    това с търсене на текст в собствения файл — а търсеният текст стоеше в
    самата проверка, тоест тя не можеше да падне никога. Този капан ни е
    ухапвал четири пъти; тук се плаща с още шест реда и се затваря.
    """
    sreda = os.environ if sreda is None else sreda
    # 🔴 ВСЯКА СЕ ЧИСТИ ПООТДЕЛНО, преди да се избира. Първата ми версия
    # чистеше СБОРА: `(a or b or "").strip()`. Стойност от празни интервали е
    # истина за Python, тоест печели избора, а после .strip() я прави празна —
    # и тревогата няма къде да излезе, при това мълчаливо. Намерено от
    # собствената проверка две минути след като я написах (25.08.2026).
    for klyuch in ("ADMIN_CHAT_ID", "CHAT_ID"):
        v = str(sreda.get(klyuch) or "").strip()
        if v:
            return v
    return ""


CHAT_ID = kade_pishe()
DRY_RUN = (os.environ.get("PAZACH_DRY_RUN") or "").strip() in ("1", "true", "yes", "да")
STATE_FILE = (os.environ.get("PAZACH_STATE") or "pazach_state.json").strip()

# Колко ПОРЕДНИ провала правят тревога. Един провал може да е мигване на
# GitHub или на чужд източник; два подред вече са състояние.
POREDNI = max(1, min(10, int((os.environ.get("PAZACH_POREDNI") or "2").strip() or 2)))

# Колко пъти подред да не сме успели да ПИТАМЕ, преди това само по себе си
# да стане тревога. Ако не виждаме, не знаем — а да не знаеш е новина.
SLEPI_PODRED = max(1, min(20, int((os.environ.get("PAZACH_SLEPI") or "3").strip() or 3)))

# Колко часа мълчи тревогата, след като веднъж е казана. Без това пазачът
# праща едно и също съобщение на всеки половин час и се превръща в шум.
POCHIVKA_CH = max(1.0, min(48.0, float((os.environ.get("PAZACH_POCHIVKA") or "6").strip() or 6)))

# Измерено върху 55 пускания (12.08.2026): медиана 65 мин закъснение,
# 34 от 55 над час. Гратисът е по-голям от медианата нарочно.
GRATIS_MIN = max(15, min(600, int((os.environ.get("PAZACH_GRATIS") or "100").strip() or 100)))

# 🔴 ЕДИН ГРАТИС ЗА ВСИЧКИ Е ГРЕШЕН — ИЗМЕРЕНО 02.09.2026, не предположено.
#
# Питах живото GitHub API за последните 20 рънa на всеки от шестте следени
# workflow-а и премерих най-дългата ИСТИНСКА пауза между два УСПЕШНИ рънa:
#
#   workflow      период   пауза    нужен гратис (пауза − период)
#   router.yml     10 м      6 м     под нулата (гратисът и без това е излишен)
#   predict.yml    60 м    220 м     160 м   ← три прескочени часови слота
#   news.yml      720 м   1257 м     537 м
#   score.yml     900 м   1334 м     434 м
#   matches.yml  1440 м   2079 м     639 м   ← кронът за 05:30 тръгна в 16:38
#   daily.yml    1440 м   1450 м      10 м   (преди да се счупи наистина)
#
# Тоест нуждата расте с периода: на рутера не му трябва нищо, на дневния бот
# му трябват над десет часа. Един общ гратис не може да служи и на двамата:
# 100 минути вдигат фалшива тревога на четири от шестте (доказано и в самия
# pazach_state.json — на 27.08 в 13:54 е излязла ЕДНА тревога с ПЕТ имена, а
# четири от тях са се оправили сами със следващия успешен рън).
# А общ гратис от 639 минути би позволил на рутера да е мъртъв 11 часа.
#
# Затова гратисът е ПРОПОРЦИОНАЛЕН на периода, с под и таван:
#     гратис = max(GRATIS_MIN, min(GRATIS_TAVAN, GRATIS_KRAT × период))
#
# ЧЕСТНО ЗА ЧИСЛАТА: множителят 3 и таванът 720 са НАГЛАСЕНИ по горните шест
# измервания — това е напасване по 20 точки на workflow, не закон. Държат се
# като най-малките кръгли стойности, които покриват всяко наблюдавано
# закъснение. Запасът е тънък на две места: predict.yml остават 20 минути,
# matches.yml — 81. Четвърти пропуснат часови слот при предсказателя ПАК ще
# вдигне тревога, и това е нарочно.
#
# ПЪТЯТ НАЗАД: PAZACH_GRATIS_KRAT=0 връща точно старото поведение (тогава
# долният праг печели винаги и гратисът пак е плосък GRATIS_MIN). Заключено с
# проверка долу, за да не изгние.
#
# КАКВО БИ ОБЪРНАЛО ИЗБОРА: закъсненията на GitHub скочиха около 26.08.2026
# (преди това matches.yml тръгваше в 05:51–06:03, тоест 21–33 мин закъснение;
# след това — 09:48 до 17:37, тоест 258–727 мин). Върне ли се старият режим,
# множителят трябва да падне обратно, инак мълчанието се крие по-дълго.
GRATIS_KRAT = max(0.0, min(10.0, float(
    (os.environ.get("PAZACH_GRATIS_KRAT") or "3").strip() or 3)))
GRATIS_TAVAN = max(15, min(2880, int(
    (os.environ.get("PAZACH_GRATIS_TAVAN") or "720").strip() or 720)))


# 🔴 ДОЛНИЯТ ПРАГ СЛЕДВА КОЙ БУДИ (02.09.2026). Множителят по периода
# оставяше ЕДНА фалшива тревога: predict.yml получаваше 4.0 ч допуск, а
# измерената му най-дълга пауза на 29 паузи е 10.6 ч. Пазачът ПРАЩА, значи
# фалшива тревога тук е мрънкане в стаята.
# Измерено: router.yml е 97% workflow_dispatch (външен будилник) и иска 0
# мин гратис; всички останали са 100% schedule и искат 376–639 мин,
# НЕЗАВИСИМО от периода си. Причината е кой буди, не колко често.
GRATIS_KRON = max(15, min(1200, int(
    (os.environ.get("PAZACH_GRATIS_KRON") or "700").strip() or 700)))
VANSHNI_SABITIYA = ("workflow_dispatch", "repository_dispatch")


def vanshno_budeno(rr, prag=0.5):
    """Буди ли се този workflow ОТВЪН, а не от разписанието на GitHub."""
    if not rr or rr is NEPITAN:
        return False
    n = 0
    for r in rr:
        if str((r or {}).get("event") or "") in VANSHNI_SABITIYA:
            n += 1
    return (float(n) / len(rr)) >= prag


def gratis_min(period, rr=None):
    """Колко минути закъснение се прощават на този workflow.

    Отделна функция, за да може да се ИЗПИТА без мрежа и без yml файлове.
    Неразбран период дава долния праг — «не знам» не бива да отваря прозореца.
    """
    dolen = GRATIS_MIN if vanshno_budeno(rr) else GRATIS_KRON
    try:
        p = float(period)
    except (TypeError, ValueError):
        return dolen
    if p <= 0:
        return dolen
    return int(max(dolen, min(GRATIS_TAVAN, GRATIS_KRAT * p)))

NL = "\n"

# Сентинел: „не можах да питам". НЕ е списък, НЕ е None, НЕ е празно — за да
# не може да се обърка с „питах и е чисто" по никой път.
NEPITAN = object()

# Workflow-ите, които НОСЯТ ПРОДУКТА. Ако някой от тях мълчи, потребителят
# губи нещо видимо. Останалите (setup, seed, rooms, branding) се пускат на
# ръка и мълчанието им е нормално — пазач, който гърми за тях, лъже.
VAZHNI = (
    ("predict.yml", "предсказателят пуска карти"),
    ("score.yml", "оценителят отсъжда и отчита"),
    ("router.yml", "рутерът разнася по стаите"),
    ("daily.yml", "дневният бот и здравният преглед"),
    ("news.yml", "новините"),
    ("matches.yml", "мачовете за деня"),
    # 🔴 ДОБАВЕНИ 05.09.2026 — имаха часовник, но никой не ги гледаше.
    #
    # support.yml не е странична стая: в него вървят budilnik.py (проспал ли
    # е предсказателят), СЪБУЖДАНЕТО на самия predictor.py и пощата на
    # потребителите — на всеки 15 минути. Умре ли, умира и будилникът, а
    # пазачът дотук докладваше «всичките важни се виждат и работят».
    ("support.yml", "съпортът, будилникът и събуждането на предсказателя"),
    ("hub.yml", "подреждането на канала и стаите"),
)

# Workflow-и с часовник, които СЪЗНАТЕЛНО не се гледат — с причината до тях.
# Извинение без причина е забравяне, написано на чисто.
NE_SE_GLEDAT = {
    "pazach.yml": ("това е самият пазач: рънът, който пита, по устройство е "
                   "пресен, тоест проверката щеше да е вечно зелена"),
}


def suh_klyuch(bot, papka=None):
    """Кой ключ за сух режим ЧЕТЕ този бот. Празно, ако няма такъв.

    🔴 ЧЕТЕ СЕ ОТ КОДА, НЕ СЕ ИЗБРОЯВА. Ключ, който само yml-ът познава, е
    мъртва ръчка: слагаш го и нищо не се променя.
    """
    import re as _re
    baza = papka or os.path.dirname(os.path.abspath(__file__))
    try:
        with io.open(os.path.join(baza, bot), encoding="utf-8-sig") as f:
            t = f.read()
    except (OSError, UnicodeDecodeError):
        return ""
    nam = _re.findall(
        r"environ(?:\.get)?\(?\[?\s*[\'\"]([A-Z_0-9]*DRY[A-Z_0-9]*)[\'\"]", t)
    return sorted(set(nam))[0] if nam else ""


def selftest_stypki(papka=None, kod=None):
    """[(файл, стъпка, бот, само_тест, има_сух)] за всяка стъпка със selftest.

    🔴 РАЗЛИКАТА «САМО ТЕСТ» СЕ МЕРИ. Стъпка, която пуска и самия бот, НЕ
    бива да получава сух режим — това би спряло производството. Точно
    router.yml «Събуди оценителя» е такава.
    """
    import re as _re
    bazi = [papka] if papka else [".github/workflows", "../.github/workflows"]
    for baza in bazi:
        if not baza or not os.path.isdir(baza):
            continue
        namereni = []
        for ime in sorted(os.listdir(baza)):
            if not ime.endswith(".yml"):
                continue
            try:
                with io.open(os.path.join(baza, ime), encoding="utf-8") as f:
                    r = f.read().split("\n")
            except (OSError, UnicodeDecodeError):
                continue
            zap = [i for i, l in enumerate(r)
                   if l.strip().startswith("- ")
                   and (len(l) - len(l.lstrip())) == 6] + [len(r)]
            for a, b in zip(zap, zap[1:]):
                blok = r[a:b]
                txt = "\n".join(blok)
                for m in _re.finditer(
                        r"python\s+([a-z_0-9]+\.py)\s+(?:--)?selftest", txt):
                    bot = m.group(1)
                    klyuch = suh_klyuch(bot, kod)
                    if not klyuch:
                        continue
                    zhiv = bool(_re.search(
                        r"python\s+" + _re.escape(bot) + r"\s*($|[^\w\-])(?!.*selftest)",
                        txt, _re.M))
                    ime_st = blok[0].strip()
                    if ime_st.startswith("- name:"):
                        ime_st = ime_st[7:].strip()
                    namereni.append((ime, ime_st[:44], bot, not zhiv,
                                     (klyuch + ":") in txt))
        if namereni:
            return namereni
    return []


def selftest_s_token(papka=None):
    """Стъпки, които пускат САМО самопроверка и въпреки това получават токен.

    🔴 ПО-СИЛНО ОТ СУХИЯ РЕЖИМ. Сух режим има само част от ботовете; липсата
    на токен затваря вратата навън за ВСИЧКИ — `post_predict` връща отказ,
    пращачите не тръгват. Стъпка, която само проверява, няма работа с токен.
    """
    import re as _re
    bazi = [papka] if papka else [".github/workflows", "../.github/workflows"]
    for baza in bazi:
        if not baza or not os.path.isdir(baza):
            continue
        vidyani, losho = 0, []
        for ime in sorted(os.listdir(baza)):
            if not ime.endswith(".yml"):
                continue
            try:
                with io.open(os.path.join(baza, ime), encoding="utf-8") as f:
                    r = f.read().split("\n")
            except (OSError, UnicodeDecodeError):
                continue
            zap = [i for i, l in enumerate(r)
                   if l.strip().startswith("- ")
                   and (len(l) - len(l.lstrip())) == 6] + [len(r)]
            for a, b in zip(zap, zap[1:]):
                blok = r[a:b]
                txt = "\n".join(blok)
                for m in _re.finditer(
                        r"python\s+([a-z_0-9]+\.py)\s+(?:--)?selftest", txt):
                    bot = m.group(1)
                    vidyani += 1
                    zhiv = bool(_re.search(
                        r"python\s+" + _re.escape(bot)
                        + r"\s*($|[^\w\-])(?!.*selftest)", txt, _re.M))
                    if zhiv:
                        continue           # стъпката пуска и самия бот
                    if _re.search(r"^\s+(BOT_TOKEN|SUPPORT_BOT_TOKEN)\s*:",
                                  txt, _re.M):
                        st = blok[0].strip()
                        if st.startswith("- name:"):
                            st = st[7:].strip()
                        losho.append(ime + "/" + st[:40])
        if vidyani:
            return vidyani, losho
    return 0, []


def cronovi_yml(papka=None):
    """Всеки workflow с часовник, прочетен от диска. Празно значи не намерих.

    🔴 ОТКРИВА, НЕ ИЗБРОЯВА. Списък в кода е ръчка, която следващият
    workflow с cron ще подмине — точно това се случи със support.yml.
    """
    import re as _re
    for baza in ([papka] if papka else
                 [".github/workflows", "../.github/workflows"]):
        if not baza or not os.path.isdir(baza):
            continue
        nam = {}
        for ime in sorted(os.listdir(baza)):
            if not ime.endswith(".yml"):
                continue
            try:
                with io.open(os.path.join(baza, ime), encoding="utf-8") as f:
                    t = f.read()
            except Exception:                                # noqa: BLE001
                continue
            cr = _re.findall(r"cron:\s*[\'\"]([^\'\"]+)", t)
            if cr:
                nam[ime] = cr
        if nam:
            return nam
    return {}


def _sega():
    return datetime.now(timezone.utc)


# ═════════════════════════════════════════ ЧЕТЕНЕ ОТ GITHUB
def _api(path, timeout=30):
    """Отговорът на GitHub, или NEPITAN при какъвто и да е отказ.

    🔴 НИКОГА не връща празен списък при неуспех. Точно това уби предишния
    пазач: `except: return []` прави аварията неразличима от мира.
    """
    url = "https://api.github.com/repos/" + REPO + "/" + path
    glavi = {"Accept": "application/vnd.github+json",
             "User-Agent": "greenpicks-pazach"}
    tok = os.environ.get("GITHUB_TOKEN", "")
    if tok:
        glavi["Authorization"] = "Bearer " + tok
    try:
        rq = urllib.request.Request(url, headers=glavi)
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:                                   # noqa: BLE001
        print("   (не можах да питам за " + path[:40] + ": " + str(e)[:60] + ")")
        return NEPITAN


def runove_na(ime, broi=10):
    """Последните рънове на ЕДИН workflow. NEPITAN, ако питането се провали."""
    j = _api("actions/workflows/" + ime + "/runs?per_page=" + str(int(broi)))
    if j is NEPITAN:
        return NEPITAN
    if not isinstance(j, dict):
        return NEPITAN
    return j.get("workflow_runs") or []


# ═════════════════════════════════════════ ПРАГЪТ ОТ CRON-А
def _pole_chasove(pole):
    """Часовете, в които едно cron поле пали. Празно = не го разбрах."""
    p = str(pole or "").strip()
    if p == "*":
        return list(range(24))
    if p.startswith("*/"):
        try:
            k = int(p[2:])
        except ValueError:
            return []
        return list(range(0, 24, k)) if 0 < k <= 24 else []
    out = []
    for chast in p.split(","):
        chast = chast.strip()
        if "-" in chast:
            try:
                a, b = [int(x) for x in chast.split("-", 1)]
            except ValueError:
                return []
            if not (0 <= a <= 23 and 0 <= b <= 23):
                return []
            out += list(range(a, b + 1)) if a <= b else (list(range(a, 24)) + list(range(0, b + 1)))
            continue
        try:
            v = int(chast)
        except ValueError:
            return []
        if not 0 <= v <= 23:
            return []
        out.append(v)
    return sorted(set(out))


def period_min(cronove):
    """Най-ГОЛЯМАТА пауза между две палления, в минути. None = не разбрах.

    Взима се най-голямата, не средната: пазачът трябва да мълчи през най-
    дългата законна тишина, инак крещи всяка нощ.
    """
    tochki = set()
    for c in (cronove or []):
        parcheta = str(c or "").split()
        if len(parcheta) < 5:
            continue
        mi, ch = parcheta[0], parcheta[1]
        minuti = []
        if mi == "*":
            minuti = list(range(0, 60, 5))
        elif mi.startswith("*/"):
            try:
                k = int(mi[2:])
            except ValueError:
                continue
            if not 0 < k <= 60:
                continue
            minuti = list(range(0, 60, k))
        else:
            try:
                minuti = [int(x) for x in mi.split(",")]
            except ValueError:
                continue
            if any(not 0 <= m <= 59 for m in minuti):
                continue
        chasove = _pole_chasove(ch)
        if not chasove or not minuti:
            continue
        for h in chasove:
            for m in minuti:
                tochki.add(h * 60 + m)
    if not tochki:
        return None
    t = sorted(tochki)
    if len(t) == 1:
        return 24 * 60
    nay = 0
    for i in range(len(t)):
        sled = t[(i + 1) % len(t)]
        raz = (sled - t[i]) % (24 * 60)
        if raz == 0:
            raz = 24 * 60
        nay = max(nay, raz)
    return nay


def cron_ot_yml(tekst):
    """Всички cron редове от един workflow файл. Закоментираните НЕ се броят."""
    out = []
    for red in str(tekst or "").split("\n"):
        gol = red.strip()
        if gol.startswith("#") or "cron:" not in gol:
            continue
        sled = gol.split("cron:", 1)[1].strip()
        # Изхвърля коментара след стойността: '30 10 * * *'   # 13:30 BG
        if "#" in sled:
            sled = sled.split("#", 1)[0].strip()
        sled = sled.strip().strip("'").strip('"').strip()
        if sled:
            out.append(sled)
    return out


def dopusk_min(ime, chetec=None, rr=None):
    """Колко минути мълчание са ДОПУСТИМИ за този workflow. None = не знам.

    Не знам ≠ наред. Извикващият е длъжен да го каже на глас.
    `rr` са рънoвете — от тях се разбира КОЙ буди workflow-а.
    """
    chetec = chetec or _lokalen_yml
    t = chetec(ime)
    if t is None:
        return None
    p = period_min(cron_ot_yml(t))
    if p is None:
        return None
    return p + gratis_min(p, rr)


def _lokalen_yml(ime):
    """Съдържанието на workflow файла от диска. None, ако го няма."""
    for baza in (".github/workflows", "../.github/workflows"):
        p = os.path.join(baza, ime)
        if os.path.exists(p):
            try:
                with io.open(p, encoding="utf-8") as f:
                    return f.read()
            except Exception:                                # noqa: BLE001
                return None
    return None


# ═════════════════════════════════════════ МЪЛЧАНИЕТО НА ПРОДУКТА
#
# 🔴 ДУПКАТА, КОЯТО ВСИЧКИ ОСТАНАЛИ ПАЗАЧИ ПРОПУСКАТ (25.08.2026).
#
# Дотук този файл питаше: „успя ли workflow-ът". Това е машинен въпрос.
# Продуктовият е друг: „ИЗЛЕЗЕ ЛИ НЕЩО".
#
# Двете се разминават. Видяно в самата самопроверка на предсказателя:
#     ОТКАЗ: в текста се промъкна забранена дума (коеф) — не пращам.
# Такава карта се изхвърля МЪЛЧАЛИВО, а рънът остава ЗЕЛЕН. Същото важи за
# всяка друга причина да не се прати: празен източник, изядена от филтър,
# капнал доставчик. Зелен рън + празна стая = никой не разбира.
#
# Това е точно шаблонът, който вече ни е коствал дни на друг проект:
# будилникът питаше „пускан ли съм?", а не „пускан съм и нищо не излиза".
#
# ПРАГЪТ Е ИЗМЕРЕН, НЕ ИЗМИСЛЕН. Върху живия дневник, 180 истински паузи
# между съседни пускания на карти:
#     медиана 1.2 ч · 90-и персентил 9.7 ч · МАКСИМУМ 20.0 ч
#     над 12 ч: 6 пъти (3.3%) · над 18 ч: 1 път · над 24 ч: НИТО ВЕДНЪЖ
# Затова 22 часа: над всичко наблюдавано, тоест НУЛА фалшиви тревоги върху
# 180 измервания, и под едно денонощие, тоест цял ням ден пак гърми.
# По-нисък праг би викал напразно — а пазач, когото пренебрегват, не е пазач.
TISHINA_CH = max(4.0, min(72.0, float(
    (os.environ.get("PAZACH_TISHINA") or "22").strip() or 22)))

# Дневникът пише часа по БЪЛГАРСКО време, а тук всичко върви по UTC. Разликата
# е +3 през лятото. Не се преструвам, че я знам точно за всяка дата: при праг
# от 22 часа три часа наклон не местят присъдата, и това е записано, за да не
# се приеме после за точност, каквато няма.
BG_NAKLON_CH = 3.0


def posledna_karta(dnevnik):
    """Часът на най-скоро пуснатата карта, в UTC. None, ако не знам.

    Чете полето `posted` („2026-08-25 10:36"). Записи без него се пропускат —
    те са от преди полето да съществува и мълчанието им не е новина.
    """
    nay = None
    for zapis in (dnevnik or []):
        if not isinstance(zapis, dict):
            continue
        s = str(zapis.get("posted") or "").strip()
        if not s:
            continue
        try:
            t = datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            continue
        t = t.replace(tzinfo=timezone.utc) - timedelta(hours=BG_NAKLON_CH)
        if nay is None or t > nay:
            nay = t
    return nay


def tiho_li(posl, sega=None, prag=None):
    """(тихо_ли, текст). Тихо значи: продуктът мълчи по-дълго от допустимото.

    🔴 НЕ ЗНАМ НЕ Е НАРЕД. Липсва ли дневник или час, това само по себе си е
    повод да се каже на глас — не да се приеме за спокойствие.
    """
    sega = sega or _sega()
    prag = TISHINA_CH if prag is None else float(prag)
    if posl is None:
        return (True, "не можах да разбера кога е пусната последната карта")
    chasove = (sega - posl).total_seconds() / 3600.0
    if chasove > prag:
        return (True, "нито една нова карта от %.0f ч (допустимо до %.0f ч)"
                % (chasove, prag))
    return (False, "последна карта преди %.1f ч" % chasove)


def _golyam_fayl(meta):
    """Съдържанието на файл, който contents API е отказал да носи.

    🔴 ЗАЩО СЪЩЕСТВУВА (05.09.2026). contents API реже на 1 МБ и над този
    размер връща 200 OK с `"encoding": "none"` и ПРАЗНО content — тоест
    отговор, който изглежда наред и няма данни. predict_log.json стана
    1 113 544 байта и точно това се случи: пазачът за мълчанието на
    продукта ослепя, без никой да е решавал да го изключва.

    🔴 НЕ ПРЕЗ RAW. raw кешира и може да върне стар файл. `git/blobs/<sha>`
    е същият api, без кеш, с таван 100 МБ, а sha го носи самият отговор на
    contents — и когато не носи съдържание.
    """
    import base64
    sha = str((meta or {}).get("sha") or "").strip()
    if not sha:
        return None
    b = _api("git/blobs/" + sha)
    if b is NEPITAN or not isinstance(b, dict):
        return None
    if str(b.get("encoding") or "") != "base64" or not b.get("content"):
        return None
    try:
        return base64.b64decode(b["content"]).decode("utf-8-sig")
    except Exception:                                        # noqa: BLE001
        return None


def dnevnik_ot_github():
    """Живият дневник. None при какъвто и да е отказ — НЕ празен списък."""
    j = _api("contents/predict_log.json?ref=main")
    if j is NEPITAN or not isinstance(j, dict):
        return None
    try:
        import base64
        suro = j.get("content")
        if suro:
            return json.loads(base64.b64decode(suro).decode("utf-8-sig"))
        # 🔴 ПРАЗНО СЪДЪРЖАНИЕ ПРИ 200 OK = файлът е над 1 МБ.
        t = _golyam_fayl(j)
        if t is None:
            print("   (predict_log.json е %s байта — над тавана на contents,"
                  " и blobs не отговори)" % str(j.get("size")))
            return None
        return json.loads(t)
    except Exception:                                        # noqa: BLE001
        return None


# ═════════════════════════════════════════ ПРИСЪДАТА
def sadi(ime, opis, rr, dopusk, sega=None):
    """(състояние, текст) за един workflow.

    Състоянията са ЧЕТИРИ, не две. Точно затова предишният пазач сгреши:
    той знаеше само „наред" и „червено", а истината има и „не знам".
        naredno   — виждам го и работи
        cherveno  — виждам го и е счупен
        mulchi    — виждам историята, но от много време няма нов рън
        neyasno   — НЕ МОГА ДА ПИТАМ или не знам прага
    """
    sega = sega or _sega()
    if rr is NEPITAN:
        return ("neyasno", opis + ": не можах да питам GitHub")
    if not rr:
        return ("neyasno", opis + ": GitHub не върна нито един рън")

    poredni = 0
    for r in rr:
        z = r.get("conclusion")
        if z is None:              # още върви — не е присъда
            continue
        if z != "success":
            poredni += 1
        else:
            break

    posleden_uspeh = None
    for r in rr:
        if r.get("conclusion") == "success":
            posleden_uspeh = r.get("created_at")
            break

    if poredni >= POREDNI:
        return ("cherveno",
                opis + ": " + str(poredni) + " поредни провала"
                + (" · последен успех " + str(posleden_uspeh)[:16].replace("T", " ")
                   if posleden_uspeh else " · НИТО ЕДИН успех в историята"))

    if dopusk is None:
        return ("neyasno", opis + ": не мога да сметна прага от разписанието")

    if not posleden_uspeh:
        return ("cherveno", opis + ": нито един успешен рън в последните "
                + str(len(rr)))

    try:
        t = datetime.fromisoformat(str(posleden_uspeh).replace("Z", "+00:00"))
    except Exception:                                        # noqa: BLE001
        return ("neyasno", opis + ": не разчетох часа на последния успех")
    minuti = (sega - t).total_seconds() / 60.0
    if minuti > dopusk:
        return ("mulchi",
                opis + ": няма успешен рън от " + ("%.1f" % (minuti / 60.0))
                + " ч (допустимо до " + ("%.1f" % (dopusk / 60.0)) + " ч)")
    if poredni:
        return ("naredno", opis + ": работи (един провал наскоро)")
    return ("naredno", opis + ": работи")


# ═════════════════════════════════════════ ПАМЕТ ЗА ПОЧИВКАТА
def cheti_sastoyanie(path=None):
    p = path or STATE_FILE
    try:
        with io.open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:                                        # noqa: BLE001
        return {}


def pishi_sastoyanie(d, path=None):
    if DRY_RUN:
        return False
    p = path or STATE_FILE
    try:
        with io.open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
        return True
    except Exception as e:                                   # noqa: BLE001
        print("   (не можах да запиша състоянието: " + str(e)[:60] + ")")
        return False


def kazvai_li(klyuch, sast, sega=None, pochivka_ch=None):
    """Да се обади ли за този проблем сега, или още е в почивка."""
    sega = sega or _sega()
    pochivka_ch = POCHIVKA_CH if pochivka_ch is None else pochivka_ch
    posl = (sast.get("kazano") or {}).get(klyuch)
    if not posl:
        return True
    try:
        t = datetime.fromisoformat(str(posl).replace("Z", "+00:00"))
    except Exception:                                        # noqa: BLE001
        return True
    return (sega - t).total_seconds() / 3600.0 >= pochivka_ch


# ═════════════════════════════════════════ ГЛАСЪТ
def tg_send(text):
    """Праща в РАБОТНАТА ГРУПА. Празно връщане значи, че НЕ е пратено."""
    if DRY_RUN:
        print("--- СУХО, щеше да отиде в групата ---")
        print(text)
        print("---")
        return True
    if not BOT_TOKEN or not CHAT_ID:
        print("   🔴 няма BOT_TOKEN или CHAT_ID — тревогата НЯМА КЪДЕ да излезе")
        return False
    try:
        data = json.dumps({"chat_id": CHAT_ID, "text": text,
                           "parse_mode": "HTML",
                           "disable_web_page_preview": True}).encode("utf-8")
        rq = urllib.request.Request(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(rq, timeout=30) as r:
            return bool(json.loads(r.read()).get("ok"))
    except Exception as e:                                   # noqa: BLE001
        print("   (Telegram отказа: " + str(e)[:80] + ")")
        return False


def tekst_trevoga(cherveni, mulchat, neyasni, sega=None):
    """Съобщението до собственика. Кратко: какво, откога, какво да направи."""
    sega = sega or _sega()
    bg = sega + timedelta(hours=3)
    out = ["\U0001f6a8 <b>ПАЗАЧЪТ</b> · " + bg.strftime("%d.%m %H:%M"), ""]
    if cherveni:
        out.append("<b>СЧУПЕНО:</b>")
        for t in cherveni:
            out.append("• " + t)
        out.append("")
    if mulchat:
        out.append("<b>МЪЛЧИ:</b>")
        for t in mulchat:
            out.append("• " + t)
        out.append("")
    if neyasni:
        out.append("<b>НЕ МОГА ДА ПРОВЕРЯ:</b>")
        for t in neyasni:
            out.append("• " + t)
        out.append("")
    out.append("<i>Actions → провалилия се workflow → последния рън.</i>")
    return NL.join(out)


# ═════════════════════════════════════════ ГЛАВНОТО
def obhod(chetec=None, pitach=None, sega=None):
    """(червени, мълчат, неясни, наредни) — по един ред текст за всеки."""
    sega = sega or _sega()
    pitach = pitach or runove_na
    cherveni, mulchat, neyasni, naredni = [], [], [], []
    for ime, opis in VAZHNI:
        rr = pitach(ime)
        # Рънoвете отиват и в допуска: от тях се вижда дали workflow-ът се
        # буди отвън (и стига тесен праг) или разчита на GitHub (и иска широк).
        d = dopusk_min(ime, chetec, rr)
        sast, red = sadi(ime, opis, rr, d, sega)
        {"cherveno": cherveni, "mulchi": mulchat,
         "neyasno": neyasni, "naredno": naredni}[sast].append(ime + " — " + red)
    return cherveni, mulchat, neyasni, naredni


def reshi(cherveni, mulchat, neyasni, slepi_predi=0, tishina=None):
    """(спешни, брояч_слепота, всички_слепи). Без мрежа, без файлове.

    Отделена от main() на 25.08.2026, защото поправката ѝ трябваше да може да
    се ИЗПИТА. Дотук решението живееше вътре в печатащата функция и никой
    тест не го достигаше — точно затова дупката оцеля до вечерта.
    """
    cherveni = list(cherveni or [])
    mulchat = list(mulchat or [])
    neyasni = list(neyasni or [])
    vsichki_slepi = len(neyasni) >= len(VAZHNI) > 0
    slepi = (int(slepi_predi or 0) + 1) if neyasni else 0
    speshni = cherveni + mulchat
    # Мълчанието на ПРОДУКТА влиза наравно със счупеното на машината: и двете
    # значат, че на читателя не му излиза нищо.
    if tishina:
        speshni = speshni + [str(tishina)]
    if vsichki_slepi:
        speshni = speshni + ["пазачът НЕ ВИЖДА НИЩО — нито един от "
                             + str(len(VAZHNI))
                             + " workflow-а не можа да бъде питан"]
    elif slepi >= SLEPI_PODRED:
        speshni = speshni + ["пазачът не е могъл да провери част от "
                             "workflow-ите " + str(slepi) + " пъти подред"]
    return speshni, slepi, vsichki_slepi


def main():
    sega = _sega()
    print("\U0001f6e1️  ПАЗАЧЪТ · " + (sega + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M")
          + " българско")
    cherveni, mulchat, neyasni, naredni = obhod(sega=sega)

    for ime, red in (("СЧУПЕНО", cherveni), ("МЪЛЧИ", mulchat),
                     ("НЕ МОГА ДА ПРОВЕРЯ", neyasni), ("наред", naredni)):
        if red:
            print("")
            print("   " + ime + ":")
            for t in red:
                print("      " + t)

    # Мълчанието на продукта — питане номер седем, след шестте за workflow-ите.
    _tih = None
    _dn = dnevnik_ot_github()
    if _dn is None:
        _tih = "не можах да прочета дневника, за да видя излиза ли нещо"
    else:
        _t, _txt = tiho_li(posledna_karta(_dn), sega)
        print("")
        print("   продуктът: " + _txt)
        if _t:
            _tih = "предсказателят е зелен, но " + _txt

    sast = cheti_sastoyanie()
    speshni, slepi, vsichki_slepi = reshi(cherveni, mulchat, neyasni,
                                          int(sast.get("slepi_podred") or 0),
                                          _tih)
    sast["slepi_podred"] = slepi
    # 🔴 ТРИ ДЕФЕКТА В ТОЗИ БЛОК, НАМЕРЕНИ ОТ ЛОВ НА СЪЩИЯ ДЕН (25.08.2026).
    # Написах файла срещу „тих отказ, който се чете като наред" — и оставих
    # точно такъв в собствения му край.
    #
    # 1) ПЪЛНАТА СЛЕПОТА ИЗЛИЗАШЕ ЗЕЛЕНА. Ако и шестте workflow-а са
    #    неразпитваеми, `cherveni` и `mulchat` са празни, `speshni` е празен —
    #    и функцията печаташе успокоение и връщаше 0. Нула проверени се четеше
    #    като нула проблеми. Сега пълната слепота е ВЕДНАГА тревога: тя не е
    #    липса на новина, тя Е новината.
    # 2) БРОЯЧЪТ СЕ НУЛИРАШЕ ОТ ЧУЖДА ПРИЧИНА. `slepi` падаше на 0, щом само
    #    едно нещо е червено — тоест частична слепота, придружена от червено,
    #    не се натрупваше никога. Сега брои слепотата САМА ЗА СЕБЕ СИ.
    # 3) УСПОКОЕНИЕТО ЛЪЖЕШЕ ПО ДУМИ. „всичко важно се вижда и работи" се
    #    печаташе и когато нищо не е видяно.
    # Решението живее в reshi() — отделно от печатането, за да може да се
    # изпита без мрежа, без файлове и без Telegram.
    if not speshni:
        print("")
        if neyasni:
            print("   ⚠️  работи каквото ВИДЯХ (%d от %d); за останалите не знам"
                  % (len(naredni), len(VAZHNI)))
        else:
            print("   ✅ всичките %d важни се виждат и работят" % len(VAZHNI))
        sast["posleden_obhod"] = sega.isoformat()
        pishi_sastoyanie(sast)
        # Частичната слепота не е зелено. Изход 2 значи „не знам", различен и
        # от 0 (наред), и от 1 (счупено) — за да може разписанието да реши.
        return 0 if not neyasni else 2

    klyuch = "|".join(sorted(t.split(" — ")[0] for t in speshni))
    if not kazvai_li(klyuch, sast, sega):
        print("")
        print("   (същата тревога вече е казана — почивка " + str(POCHIVKA_CH) + " ч)")
        sast["posleden_obhod"] = sega.isoformat()
        pishi_sastoyanie(sast)
        return 1

    t = tekst_trevoga(cherveni, mulchat + ([_tih] if _tih else []),
                      neyasni if (vsichki_slepi or slepi >= SLEPI_PODRED)
                      else [], sega)
    if tg_send(t):
        sast.setdefault("kazano", {})[klyuch] = sega.isoformat()
        print("")
        print("   \U0001f4e3 тревогата е изпратена в групата")
    else:
        print("")
        print("   🔴 тревогата НЕ можа да излезе — оставям я неказана, за да")
        print("      се опита пак на следващия обход")
    sast["posleden_obhod"] = sega.isoformat()
    pishi_sastoyanie(sast)
    return 1


# ═════════════════════════════════════════ САМОПРОВЕРКА
def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    T0 = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)

    # ---------------------------------------------- 🔴 НИКОЙ С ЧАСОВНИК ДА
    # НЕ ОСТАНЕ НЕГЛЕДАН (05.09.2026). Дотук VAZHNI беше шест имена, а
    # часовник имаха девет: support.yml (на 15 мин, с будилника и
    # събуждането на предсказателя), hub.yml и pazach.yml.
    _cr = cronovi_yml()
    check("workflow-ите с часовник се намират", len(_cr) >= 6)
    _gledani = {i for i, _o in VAZHNI}
    _zabraveni = sorted(set(_cr) - _gledani - set(NE_SE_GLEDAT))
    check("никой с часовник не е забравен: " + (", ".join(_zabraveni) or "-"),
          not _zabraveni)
    check("всяко извинение носи причина",
          all(len(str(v)) > 20 for v in NE_SE_GLEDAT.values()))
    check("не се извинява нещо, което ГЛЕДАМЕ",
          not (set(NE_SE_GLEDAT) & _gledani))
    check("съпортът е сред важните", "support.yml" in _gledani)
    check("всеки важен има написано какво прави",
          all(len(str(o)) > 5 for _i, o in VAZHNI))
    check("няма повторено име", len(_gledani) == len(VAZHNI))

    # ---------------------------------------------- 🔴 САМОПРОВЕРКА БЕЗ СУХ
    # РЕЖИМ (05.09.2026). Две проверки, които искат УСПЕХ от вратата навън,
    # счупиха рутера за ДВА ДНИ: 400 ръна, нула успешни. Стъпката няма env
    # блок, DRY_RUN е угасен, вратата отказва. Поправих проверките в кода;
    # това е втората ключалка — стъпката да не МОЖЕ да прати нищо.
    _ss = selftest_stypki()
    check("стъпките със самопроверка се намират", len(_ss) >= 5)
    _bez = ["%s/%s" % (f, s) for f, s, _b, samo, ima in _ss if samo and not ima]
    check("всяка САМО-тестова стъпка е в сух режим: "
          + ("; ".join(_bez)[:80] or "-"), not _bez)
    # 🔴 И ОБРАТНОТО: стъпка, която пуска и самия бот, НЕ бива да е суха —
    # това би спряло производството.
    _suhi_zhivi = ["%s/%s" % (f, s) for f, s, _b, samo, ima in _ss
                   if not samo and ima]
    check("производствена стъпка НЕ е суха: "
          + ("; ".join(_suhi_zhivi)[:60] or "-"), not _suhi_zhivi)
    # 🔴 И ПО-СИЛНОТО ПРАВИЛО: само-тестова стъпка БЕЗ ТОКЕН. Сух режим има
    # само част от ботовете; липсата на токен затваря вратата за всички.
    _vid, _s_tok = selftest_s_token()
    check("стъпките със самопроверка се виждат (за токена)", _vid >= 10)
    check("нито една само-тестова стъпка няма токен: "
          + ("; ".join(_s_tok)[:70] or "-"), not _s_tok)
    check("ключът за сух режим се чете от КОДА",
          suh_klyuch("predictor.py") == "PREDICT_DRY_RUN"
          and suh_klyuch("scorer.py") == "SCORE_DRY_RUN"
          and suh_klyuch("nyama_takav_fayl.py") == "")

    # ---------------------------------------------- 🔴 ДНЕВНИКЪТ НАД 1 МБ
    # (05.09.2026). contents API реже на 1 048 576 байта и над това връща
    # 200 OK с празно content. predict_log.json стана 1 113 544 байта и
    # dnevnik_ot_github() почна да връща None — тоест пазачът за мълчанието
    # на продукта беше изключен, без никой да го е изключвал.
    import base64 as _b64
    _telo = _b64.b64encode('[{"day": "2026-09-05"}]'.encode("utf-8")).decode()
    _st_api = globals()["_api"]
    _pitani = []
    try:
        def _fake(path, timeout=30):
            _pitani.append(path)
            if path.startswith("contents/"):
                return {"size": 1113544, "encoding": "none", "content": "",
                        "sha": "abc123"}
            if path == "git/blobs/abc123":
                return {"size": 1113544, "encoding": "base64", "content": _telo}
            return NEPITAN
        globals()["_api"] = _fake
        _d = dnevnik_ot_github()
        check("голям дневник СЕ ЧЕТЕ през blobs", isinstance(_d, list) and len(_d) == 1)
        check("и blobs наистина е питан", "git/blobs/abc123" in _pitani)
        # малък файл НЕ бива да минава през blobs — това е излишна заявка
        _pitani[:] = []
        def _malak(path, timeout=30):
            _pitani.append(path)
            return {"size": 42, "encoding": "base64", "content": _telo,
                    "sha": "abc123"}
        globals()["_api"] = _malak
        _d2 = dnevnik_ot_github()
        check("малък файл се чете направо", isinstance(_d2, list) and len(_d2) == 1)
        check("и blobs НЕ се пита излишно",
              not [p for p in _pitani if p.startswith("git/blobs")])
        # 🔴 ПРАЗЕН sha: смисълът на реда е ДА НЕ СЕ ХОДИ до blobs. Първата
        # ми версия гледаше само резултата и мутацията «махни проверката за
        # sha» остана ЗЕЛЕНА — подложката отговаряше еднакво на всеки адрес.
        _pitani[:] = []
        globals()["_api"] = lambda path, timeout=30: (
            _pitani.append(path) or {"size": 1113544, "encoding": "none",
                                     "content": "", "sha": ""})
        check("празно без sha дава None, НЕ празен списък",
              dnevnik_ot_github() is None)
        check("и при празен sha към blobs НЕ се ходи",
              not [p for p in _pitani if p.startswith("git/blobs")])
        # 🔴 БЛОБ С ЧУЖДА КОДИРОВКА: съдържанието Е валиден base64, но
        # blobs казва, че кодировката е друга. Без пазача функцията би
        # върнала данни от нещо, което не е обявено за base64. Първата ми
        # подложка връщаше НЕвалиден base64 и външният except я хващаше —
        # тоест мерех except-а, не пазача.
        def _blob_s(kodirovka):
            def _f(path, timeout=30):
                if path.startswith("git/blobs"):
                    return {"encoding": kodirovka, "content": _telo}
                return {"size": 9, "encoding": "none", "content": "", "sha": "z"}
            return _f

        globals()["_api"] = _blob_s("utf-8")
        check("чужда кодировка НЕ се декодира",
              _golyam_fayl({"sha": "z"}) is None)
        globals()["_api"] = _blob_s("base64")
        check("а обявеният base64 СЕ декодира",
              str(_golyam_fayl({"sha": "z"}) or "").strip().startswith("["))
        # boklučav base64 пак дава None (външният пазач също работи)
        def _bokluk(path, timeout=30):
            if path.startswith("contents/"):
                return {"size": 9, "encoding": "none", "content": "", "sha": "z"}
            return {"encoding": "base64", "content": "не-base64!!"}
        globals()["_api"] = _bokluk
        check("боклучав base64 дава None", dnevnik_ot_github() is None)
        globals()["_api"] = lambda path, timeout=30: NEPITAN
        check("отказ на API дава None", dnevnik_ot_github() is None)
    finally:
        globals()["_api"] = _st_api

    def run(kogato, zakl):
        return {"created_at": kogato, "conclusion": zakl}

    # ---------------------------------------------- прагът от cron-а
    check("два пъти дневно дава най-дълга пауза",
          period_min(["30 10 * * *", "30 19 * * *"]) == 15 * 60)
    check("на всеки 3 часа дава 180 мин",
          period_min(["0 */3 * * *"]) == 180)
    check("веднъж дневно дава 24 часа",
          period_min(["0 5 * * *"]) == 24 * 60)
    check("списък от часове се разбира",
          period_min(["0 1,4,7,10,13,16,19,22 * * *"]) == 180)
    check("боклук не дава праг",
          period_min(["абв"]) is None and period_min([]) is None)
    check("непълен cron не дава праг", period_min(["30 10"]) is None)

    check("cron се вади от yml",
          cron_ot_yml("on:\n  schedule:\n    - cron: '30 10 * * *'\n") == ["30 10 * * *"])
    check("коментарът след стойността не влиза",
          cron_ot_yml("    - cron: '0 4 * * *'   # 07:00 BG") == ["0 4 * * *"])
    # 🔴 МУТАЦИЯТА, КОЯТО ТОВА ПАЗИ: ако закоментираните редове се броят,
    # прагът се смята по разписание, което НЕ Е ЖИВО. Пазачът тогава мълчи
    # през дупки, които са истински.
    check("закоментиран cron НЕ се брои",
          cron_ot_yml("    # - cron: '0 * * * *'\n    - cron: '0 6 * * *'") == ["0 6 * * *"])

    # ------------------------- ГРАТИСЪТ ПО ПЕРИОД (02.09.2026, измерено живо)
    # 🔴 ЗАКЛЮЧВАТ ИЗМЕРЕНОТО. Всяка от долните проверки пада, ако някой върне
    # плоския гратис или пренастрои множителя така, че живите паузи пак да
    # вдигат тревога. Изпитва се ПОВЕДЕНИЕТО (присъдата на sadi() върху
    # истински измерени паузи), не текстът и не броят споменавания.
    # 🔴 ОБЪРНАТИ 02.09.2026, не изтрити. Долният праг вече зависи от
    # будителя, затова «долният праг» се пита ДВА пъти — веднъж за външно
    # будения, веднъж за кронския. Намерението е същото.
    _v20 = [{"event": "workflow_dispatch"} for _ in range(20)]
    _k20 = [{"event": "schedule"} for _ in range(20)]
    check("къс период, външно буден → тесният под",
          gratis_min(10, _v20) == GRATIS_MIN)
    check("къс период, кронски → широкият под",
          gratis_min(10, _k20) == GRATIS_KRON)
    check("часовият период взима множителя", gratis_min(60, _v20) == 180)
    check("дневният период удря тавана", gratis_min(1440) == GRATIS_TAVAN)
    check("гратисът не намалява с периода",
          gratis_min(10) <= gratis_min(60) <= gratis_min(720) <= gratis_min(1440))
    check("боклучав период дава долния праг",
          gratis_min(None, _v20) == GRATIS_MIN
          and gratis_min("абв", _v20) == GRATIS_MIN
          and gratis_min(0, _v20) == GRATIS_MIN
          and gratis_min(-5, _v20) == GRATIS_MIN)
    check("боклучав период при кронски дава ШИРОКИЯ под",
          gratis_min(None, _k20) == GRATIS_KRON
          and gratis_min("абв", _k20) == GRATIS_KRON)

    # 🔴 ПЪТЯТ НАЗАД Е ЗАКЛЮЧЕН: множител 0 връща точно старото плоско
    # поведение. Без тази проверка обещанието в коментара горе е само дума.
    _st_krat = globals()["GRATIS_KRAT"]
    try:
        globals()["GRATIS_KRAT"] = 0.0
        check("множител 0 връща плоския гратис",
              gratis_min(10, _v20) == gratis_min(1440, _v20) == GRATIS_MIN)
        check("множител 0 при кронски дава широкия под",
              gratis_min(10, _k20) == gratis_min(1440, _k20) == GRATIS_KRON)
    finally:
        globals()["GRATIS_KRAT"] = _st_krat
    check("множителят се върна както си беше",
          globals()["GRATIS_KRAT"] == _st_krat and gratis_min(60, _v20) == 180)

    # 🔴 ПРАГЪТ НАИСТИНА МИНАВА ПРЕЗ gratis_min(). Мутацията, която това пази:
    # `p + gratis_min(p)` обратно на `p + GRATIS_MIN` — фалшивите тревоги се
    # връщат, а всички стари проверки остават зелени.
    _yml1h = lambda i: "on:\n  schedule:\n    - cron: '0 * * * *'\n"  # noqa: E731
    check("прагът се смята с гратиса по период",
          dopusk_min("х.yml", _yml1h, _v20) == 60 + 180)

    # ── ГРАТИСЪТ СЛЕДВА КОЙ БУДИ (02.09.2026) ───────────────────────────
    # Измерено на 30 рънa: router.yml е 97% workflow_dispatch и иска 0 мин
    # гратис; predict.yml е 100% schedule, върви на всеки час, и иска 576
    # мин. Периодът НЕ обяснява това — будителят го обяснява. Старото
    # правило даваше на predict 4.0 ч допуск при измерена пауза 10.6 ч,
    # тоест ЕДНА фалшива тревога на 29 паузи — а пазачът ПРАЩА.
    check("външно будените се разпознават", vanshno_budeno(_v20) is True)
    check("кронските НЕ минават за външно будени",
          vanshno_budeno(_k20) is False)
    check("празен списък не е външно буден", vanshno_budeno([]) is False)
    check("непитаният не е външно буден", vanshno_budeno(NEPITAN) is False)
    check("смес под прага не е външно будена",
          vanshno_budeno(_v20[:9] + _k20[:11]) is False)
    check("двата пода се РАЗЛИЧАВАТ", GRATIS_KRON > GRATIS_MIN)
    check("широкият под покрива измерените 639 мин", GRATIS_KRON >= 639)
    check("широкият под НЕ ослепява пазача", GRATIS_KRON <= 900)
    check("часовият кронски получава над 10.6 ч",
          dopusk_min("х.yml", _yml1h, _k20) > 10.6 * 60)
    # 4.0 ч ТОЧНО (60 период + 180 множител), затова <=, не <. Първата
    # версия писа < и падна с една минута — числото се проверява, не се помни.
    check("същият, но външно буден, получава НАЙ-МНОГО 4 ч",
          dopusk_min("х.yml", _yml1h, _v20) <= 4 * 60)
    check("без рънoве се пада на ШИРОКИЯ под",
          dopusk_min("х.yml", _yml1h, None)
          == dopusk_min("х.yml", _yml1h, _k20))

    # 🔴 ПРЕЗ ОБХОДА, не само по функцията. Всичките проверки горе викат
    # gratis_min/dopusk_min ПРЯКО — значи мутация «обходът спира да подава
    # рънoвете» би ги минала, а пътят обход → рънoве → праг остава неизпитан.
    _sega_o = _sega()

    # ЕДНА И СЪЩА ВЪЗРАСТ (300 мин), различен само БУДИТЕЛЯТ. Външно буденият
    # има праг 240 мин → МЪЛЧИ; кронският има 760 мин → НАРЕД. Ако обходът
    # спре да подава рънoвете, двата стават еднакви и проверката гърми.
    # (Първата версия правеше външния на 5 мин — тогава и двата бяха «наред»
    # и проверката не можеше да различи нищо. Обърнато очакване.)
    # 🔴 `created_at`, НЕ `run_started_at`. sadi() чете първото (ред 489);
    # първата версия подаваше второто и всичките подхвърлени рънoве излизаха
    # «нито един успешен» — тоест тестът мереше липсващо поле, не правилото.
    def _star(sabitie):
        _t = (_sega_o - timedelta(minutes=300)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return [dict(sabitie, status="completed", conclusion="success",
                     created_at=_t, run_started_at=_t) for _ in range(20)]

    def _pit_v(_i):
        return _star(_v20[0])

    def _pit_k(_i):
        return _star(_k20[0])

    _ca, _ma, _na, _ra = obhod(_yml1h, _pit_v, _sega_o)
    _cb, _mb, _nb, _rb = obhod(_yml1h, _pit_k, _sega_o)
    check("обходът ПОДАВА рънoвете на прага",
          len(_ma) > 0 and len(_mb) == 0)

    # ИЗМЕРЕНО НА ЖИВО 02.09.2026: (workflow, период в мин, най-дълга истинска
    # пауза между два УСПЕШНИ рънa в последните 20). Числата са наблюдения, не
    # желания — само daily.yml е бил наистина счупен и той се хваща по ДРУГИЯ
    # път (поредни провали), не по мълчанието.
    _izmereno = (("router.yml", 10, 6), ("predict.yml", 60, 220),
                 ("news.yml", 720, 1257), ("score.yml", 900, 1334),
                 ("matches.yml", 1440, 2079), ("daily.yml", 1440, 1450))
    for _ime, _per, _pauza in _izmereno:
        _dop = _per + gratis_min(_per)
        _uspeh = [run("2026-08-25T12:00:00Z", "success")]
        # Пауза, която НАИСТИНА се е случила и е свършила с успешен рън, не
        # бива да е тревога. Часът на «сега» се мести така, че от последния
        # успех да са минали точно толкова минути, колкото е измерената пауза.
        _s, _ = sadi(_ime, "х", _uspeh, _dop, T0 + timedelta(minutes=_pauza))
        check("измерената пауза на " + _ime + " НЕ е тревога", _s == "naredno")
        # Но двойно по-дълга тишина ПАК се хваща — прозорецът не е отворен.
        _s, _ = sadi(_ime, "х", _uspeh, _dop, T0 + timedelta(minutes=2 * _dop))
        check("двойна тишина на " + _ime + " Е тревога", _s == "mulchi")
        # 🔴 ОБРАТНАТА ПОСОКА (въпросът, който сам си зададох и премерих):
        # никой прозорец не бива да е толкова широк, че истинско мълчание да
        # мине незабелязано повече от 36 часа. Това е таванът на цената, която
        # плащаме за тишината — записан като проверка, не като надежда.
        check("прозорецът на " + _ime + " не надхвърля 36 ч", _dop <= 36 * 60)

    # 🔴 ШИРОКИЯТ ПРОЗОРЕЦ НЕ ОСЛЕПЯВА ПЪТЯ ЗА СЧУПЕНОТО. Точно това е живият
    # случай на 02.09.2026: daily.yml има 7 поредни провала и се хваща червено
    # независимо от това колко е широк прагът за мълчание.
    _sedem = [run("2026-09-01T19:47:00Z", "failure")] * 7 + [
        run("2026-08-25T17:34:00Z", "success")]
    _s, _t = sadi("daily.yml", "дневният", _sedem, 36 * 60,
                  datetime(2026, 9, 2, 13, 0, tzinfo=timezone.utc))
    check("седем поредни провала са червено и при най-широкия праг",
          _s == "cherveno" and "7 поредни провала" in _t)

    # ------------------------------- ПРОИЗХОДЪТ НА СЕНТИНЕЛА (25.08.2026)
    # 🔴 ТАЗИ ГРУПА Е ДОБАВЕНА, ЗАЩОТО МУТАЦИЯ ОЦЕЛЯ. Долните проверки
    # изпитваха sadi() със сентинел, подаден на ръка — но НИКОЯ не изпитваше
    # функцията, която го произвежда. Смяна на `return NEPITAN` с `return []`
    # вътре в runove_na минаваше през всичките 40 проверки. Тоест пазачът
    # можеше да умре точно по начина, заради който е построен, и да остане
    # зелен. Изпитва се ПРОИЗХОДЪТ, не само употребата.
    # Първо САМАТА мрежова функция. Останалите проверки я подменят, тоест
    # никога не влизат в нейния except — и мутация точно там оцеля (25.08).
    # Затова тук се чупи МРЕЖАТА, а _api остава истинската.
    _star_open = urllib.request.urlopen

    def _padashta(*a, **k):
        raise OSError("мрежата я няма")

    try:
        urllib.request.urlopen = _padashta
        check("паднала мрежа дава СЕНТИНЕЛ от _api",
              _api("actions/workflows/score.yml/runs") is NEPITAN)
        check("и обходът го вижда като сентинел",
              runove_na("score.yml") is NEPITAN)
    finally:
        urllib.request.urlopen = _star_open
    check("мрежата се върна както си беше",
          urllib.request.urlopen is _star_open)

    _star_api = globals()["_api"]
    try:
        globals()["_api"] = lambda p, timeout=30: NEPITAN
        check("отказът на мрежата дава СЕНТИНЕЛ, не празен списък",
              runove_na("score.yml") is NEPITAN)
        globals()["_api"] = lambda p, timeout=30: {"workflow_runs": []}
        _r = runove_na("score.yml")
        check("истинско празно дава СПИСЪК", isinstance(_r, list) and not _r)
        globals()["_api"] = lambda p, timeout=30: {"workflow_runs": [run("2026-08-25T11:00:00Z", "success")]}
        check("нормалният отговор дава редовете", len(runove_na("score.yml")) == 1)
        globals()["_api"] = lambda p, timeout=30: ["не е речник"]
        check("отговор с грешна форма е СЕНТИНЕЛ", runove_na("score.yml") is NEPITAN)
        globals()["_api"] = lambda p, timeout=30: None
        check("празен отговор е СЕНТИНЕЛ", runove_na("score.yml") is NEPITAN)
    finally:
        globals()["_api"] = _star_api
    check("_api се върна както си беше", globals()["_api"] is _star_api)

    # ---------------------------------------------- „не можах да питам"
    # 🔴 СЪРЦЕТО НА ФАЙЛА. Предишният пазач умря точно тук.
    s, t = sadi("score.yml", "оценителят", NEPITAN, 900, T0)
    check("отказът НЕ се чете като наред", s == "neyasno")
    check("отказът го казва с думи", "не можах да питам" in t)
    s, t = sadi("score.yml", "оценителят", [], 900, T0)
    check("празен отговор НЕ е наред", s == "neyasno")

    # ---------------------------------------------- поредните провали
    trima = [run("2026-08-25T11:00:00Z", "failure"),
             run("2026-08-25T02:00:00Z", "failure"),
             run("2026-08-24T17:00:00Z", "failure"),
             run("2026-08-24T08:00:00Z", "success")]
    s, t = sadi("score.yml", "оценителят", trima, 900, T0)
    check("три поредни провала са ЧЕРВЕНО", s == "cherveno")
    check("броят на провалите се изписва", "3 поредни провала" in t)

    edin = [run("2026-08-25T11:00:00Z", "failure"),
            run("2026-08-25T02:00:00Z", "success")]
    s, _ = sadi("score.yml", "оценителят", edin, 900, T0)
    check("един провал НЕ вдига тревога", s == "naredno")

    varvi = [run("2026-08-25T11:50:00Z", None),
             run("2026-08-25T11:00:00Z", "success")]
    s, _ = sadi("score.yml", "оценителят", varvi, 900, T0)
    check("рън, който още върви, не е провал", s == "naredno")

    # ---------------------------------------------- мълчанието
    star = [run("2026-08-23T11:00:00Z", "success")]
    s, t = sadi("score.yml", "оценителят", star, 15 * 60, T0)
    check("48 ч без рън при праг 15 ч е МЪЛЧАНИЕ", s == "mulchi")
    check("мълчанието казва колко часа", " ч (допустимо до " in t)
    s, _ = sadi("score.yml", "оценителят",
                [run("2026-08-25T09:00:00Z", "success")], 15 * 60, T0)
    check("пресен успех е наред", s == "naredno")

    # 🔴 БЕЗ ПРАГ НЕ СЕ ОБЯВЯВА „НАРЕД". „Не знам" е трето състояние.
    s, t = sadi("score.yml", "оценителят", star, None, T0)
    check("без праг състоянието е НЕЯСНО", s == "neyasno")
    check("и си го признава", "не мога да сметна прага" in t)

    check("нито един успех е червено",
          sadi("x.yml", "х", [run("2026-08-25T11:00:00Z", None)], 900, T0)[0] != "naredno")

    # ---------------------------------------------- обходът, без мрежа
    def fake_chetec(ime):
        return "on:\n  schedule:\n    - cron: '30 10 * * *'\n    - cron: '30 19 * * *'\n"

    def fake_pitach_dobre(ime):
        return [run("2026-08-25T11:00:00Z", "success")]

    def fake_pitach_zle(ime):
        return trima if ime == "score.yml" else [run("2026-08-25T11:00:00Z", "success")]

    def fake_pitach_slyap(ime):
        return NEPITAN

    c, m, n, nr = obhod(fake_chetec, fake_pitach_dobre, T0)
    check("здрав обход не дава нищо червено", not c and not m and not n)
    check("здрав обход брои всички важни", len(nr) == len(VAZHNI))

    c, m, n, nr = obhod(fake_chetec, fake_pitach_zle, T0)
    check("счупеният се хваща в обхода", len(c) == 1 and "score.yml" in c[0])
    check("останалите остават наредни", len(nr) == len(VAZHNI) - 1)

    c, m, n, nr = obhod(fake_chetec, fake_pitach_slyap, T0)
    # 🔴 МУТАЦИЯТА: върне ли `_api` празен списък вместо NEPITAN, тук ще излязат
    # нула неясни и обходът ще изглежда чист при пълна слепота.
    check("пълната слепота дава САМО неясни",
          len(n) == len(VAZHNI) and not c and not m and not nr)

    # ------------------------- МЪЛЧАНИЕТО НА ПРОДУКТА (25.08.2026)
    _T = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)

    def _k(chas):
        return {"posted": chas}

    check("намира най-скорошната карта",
          posledna_karta([_k("2026-08-24 10:00"), _k("2026-08-25 09:00"),
                          _k("2026-08-23 20:00")])
          == datetime(2026, 8, 25, 6, 0, tzinfo=timezone.utc))
    check("записи без час се пропускат",
          posledna_karta([{"day": "2026-08-25"}, _k("2026-08-25 09:00")])
          is not None)
    check("боклучав час не гърми", posledna_karta([_k("абв")]) is None)
    check("празен дневник не дава час", posledna_karta([]) is None)
    check("None не гърми", posledna_karta(None) is None)

    check("прясната карта НЕ е мълчание",
          not tiho_li(datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc), _T)[0])
    check("денонощие мълчание Е тревога",
          tiho_li(datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc), _T)[0])
    check("и се казва с часове",
          " ч (допустимо до" in tiho_li(
              datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc), _T)[1])
    # 🔴 ГЛАВНАТА: „не знам" НЕ Е „наред".
    check("липсващият час е тревога, не спокойствие", tiho_li(None, _T)[0])
    check("прагът е над наблюдавания максимум от 20 ч", TISHINA_CH >= 21.0)
    check("прагът е под денонощие", TISHINA_CH <= 24.0)

    # 🔴 ДОГОВОРЪТ НА ЧЕТЕЦА. Мутация показа, че `return []` вместо `return
    # None` при отказ ОЦЕЛЯВА — защото празният списък пак стига до „не знам"
    # и пак вдига тревога. Тоест днес е безобидно. НО договорът пак се
    # заключва: следващият, който напише `if not _dn: продължавай тихо`, ще
    # възкреси точно шаблона, срещу който е построен целият файл.
    # Изпитва се ПРОИЗХОДЪТ, не само употребата — същият урок, платен два пъти.
    _st_api = globals()["_api"]
    try:
        globals()["_api"] = lambda p, timeout=30: NEPITAN
        check("отказът дава None, НЕ празен списък",
              dnevnik_ot_github() is None)
        globals()["_api"] = lambda p, timeout=30: {"content": ""}
        check("празно съдържание дава None", dnevnik_ot_github() is None)
        globals()["_api"] = lambda p, timeout=30: ["не е речник"]
        check("отговор с грешна форма дава None", dnevnik_ot_github() is None)
        import base64 as _b64
        globals()["_api"] = lambda p, timeout=30: {
            "content": _b64.b64encode(b'[{"posted": "2026-08-25 09:00"}]').decode()}
        _d = dnevnik_ot_github()
        check("истинският отговор дава списък",
              isinstance(_d, list) and len(_d) == 1)
    finally:
        globals()["_api"] = _st_api
    check("_api се върна както си беше", globals()["_api"] is _st_api)

    # Мълчанието влиза в спешните наравно със счупеното.
    _sp, _sl, _vsl = reshi([], [], [], 0, "продуктът мълчи")
    check("мълчанието само по себе си вдига тревога", len(_sp) == 1)
    check("и текстът му стига дотам", "мълчи" in " ".join(_sp))
    _sp2, _, _ = reshi(["а.yml — счупено"], [], [], 0, "продуктът мълчи")
    check("мълчанието се добавя КЪМ счупеното", len(_sp2) == 2)
    _sp3, _, _ = reshi([], [], [], 0, None)
    check("без мълчание нищо не се добавя", not _sp3)

    # ------------------------- РЕШЕНИЕТО (добавено 25.08.2026 след лов)
    _vs = [str(i) + ".yml — не можах" for i in range(len(VAZHNI))]
    # 🔴 ГЛАВНАТА: нула проверени НЕ Е нула проблеми.
    _sp, _sl, _vsl = reshi([], [], _vs, 0)
    check("пълната слепота вдига тревога ВЕДНАГА", _sp and _vsl)
    check("и го казва с думи", any("НЕ ВИЖДА НИЩО" in t for t in _sp))
    check("не чака трети обход", _sl == 1 and len(_sp) == 1)

    _sp, _sl, _vsl = reshi([], [], ["едно.yml — не можах"], 0)
    check("частичната слепота не вдига тревога веднага", not _sp)
    check("но се брои", _sl == 1 and not _vsl)
    _sp, _sl, _ = reshi([], [], ["едно.yml — не можах"], SLEPI_PODRED - 1)
    check("след достатъчно обходи вече вдига", bool(_sp))

    # 🔴 БРОЯЧЪТ НЕ СЕ НУЛИРА ОТ ЧУЖДА ПРИЧИНА. Дотук едно червено го
    # изтриваше и частичната слепота не се натрупваше никога.
    _sp, _sl, _ = reshi(["нещо.yml — счупено"], [], ["друго.yml — не можах"], 4)
    check("червеното НЕ нулира брояча на слепотата", _sl == 5)
    check("и червеното пак е в спешните",
          any("счупено" in t for t in _sp))

    _sp, _sl, _vsl = reshi([], [], [], 7)
    check("чистият обход нулира брояча", _sl == 0)
    check("чистият обход няма спешни", not _sp and not _vsl)
    _sp, _, _ = reshi(["а.yml — счупено"], ["б.yml — мълчи"], [], 0)
    check("червено и мълчание влизат заедно", len(_sp) == 2)

    # ---------------------------------------------- почивката
    sast = {"kazano": {"score.yml": "2026-08-25T10:00:00+00:00"}}
    check("прясно казаното мълчи", not kazvai_li("score.yml", sast, T0, 6))
    check("след почивката пак се обажда", kazvai_li("score.yml", sast, T0, 1))
    check("неказаното се казва", kazvai_li("predict.yml", sast, T0, 6))
    check("счупена дата не заглушава",
          kazvai_li("x", {"kazano": {"x": "абв"}}, T0, 6))

    # ---------------------------------------------- текстът
    t = tekst_trevoga(["score.yml — оценителят: 3 поредни провала"], [], [], T0)
    check("тревогата се вижда като тревога", "ПАЗАЧЪТ" in t)
    check("тревогата казва кое е счупено", "score.yml" in t and "СЧУПЕНО" in t)
    check("тревогата казва къде да се гледа", "Actions" in t)
    check("празните раздели не се изписват", "МЪЛЧИ" not in t)
    t2 = tekst_trevoga([], [], ["daily.yml — не можах да питам"], T0)
    check("неясното си има свой раздел", "НЕ МОГА ДА ПРОВЕРЯ" in t2)

    # 🔴 ПОВЕДЕНЧЕСКИ, НЕ ТЕКСТОВИ. Мутацията, която пазят: разменѝ реда на
    # двата ключа и тревогата тръгва към ПУБЛИЧНИЯ канал вместо към групата.
    check("админската стая бие общата",
          kade_pishe({"ADMIN_CHAT_ID": "-100админ", "CHAT_ID": "-100обща"}) == "-100админ")
    check("без админска се пада на общата",
          kade_pishe({"CHAT_ID": "-100обща"}) == "-100обща")
    check("без нито една е празно — тоест НИКЪДЕ",
          kade_pishe({}) == "")
    check("празният низ не се брои за стая",
          kade_pishe({"ADMIN_CHAT_ID": "  ", "CHAT_ID": "-100обща"}) == "-100обща")

    print("САМОПРОВЕРКА НА ПАЗАЧА: %d наред, %d счупени" % (ok, len(bad)))
    for b in bad:
        print("   счупено: " + b)
    return ok, bad


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--selftest" in sys.argv:
        _ok, _bad = selftest()
        sys.exit(1 if _bad else 0)
    sys.exit(main())
