# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ЗДРАВЕН ПРЕГЛЕД 🩺

Един въпрос, един отговор: РАБОТИ ЛИ ВСИЧКО, и ако не — КОЕ и ЗАЩО.

Не праща нищо. Не пипа нищо. Само чете живото състояние и мери.

Защо съществува: собственикът пита едно и също всеки ден — „защо еди-кой си
спорт е празен". Дотук отговорът искаше ровене в дневника, в тефтера и в
GitHub Actions поотделно. Сега е една команда.

  python zdrave.py            — пълният преглед
  python zdrave.py --kratko   — само редът с присъдата
  python zdrave.py --selftest — проверява САМИЯ преглед (без мрежа)

Чете:
  predict_log.json    — какво е пуснато и какво е отсъдено
  predict_state.json  — черната кутия на последния рън (по спорт)
  GitHub Actions API  — зелени ли са рънoвете (без ключ, публично)

🔴 25.08.2026 — ЗАЩО ТОЗИ ФАЙЛ БЕШЕ ПРЕНАПИСАН.
Оценителят (score.yml) гърмя ТРИ ПЪТИ подред, 33 часа. Резултатите в канала
спряха. Собственикът го откри — не прегледът. А прегледът в същия ден печаташе
„последните 30 рънa в CI: 0 червени" и завършваше с „✅ ВСИЧКО Е ЧИСТО".

Измерено на живо на 25.08 в 05:13Z: `actions/runs?per_page=30` — ОБЩИЯТ списък
на всички workflow-и — върна 26 рутерски рънa, 3 съпорт и 1 hub. Прозорецът
беше 03:15:24 → 05:10:25, тоест 1 ЧАС И 55 МИНУТИ. Рутерът пуска ~14 рънa на
час и залива списъка. Оценителят се пуска 2 пъти на 24 часа. Тоест той НИКОГА
не е попадал в прозореца: прегледът не беше ослепял — той СТРУКТУРНО не можеше
да види провала.

Три независими дефекта се лекуват тук наведнъж:
  1. прозорецът: пита се ПО WORKFLOW (actions/workflows/ИМЕ/runs), не общо;
  2. тихият отказ: `except: return []` правеше аварията неразличима от мира —
     сега има сентинел NEPITAN и „не можах да питам" е ОТДЕЛНО състояние;
  3. присъдата: `cherveni` се смяташе, печаташе се и НИКОГА не влизаше в
     `problemi` — по нито един път червен рън не можеше да оцвети прегледа.

Правилото, което остава: ПРАЗНО ≠ ЧИСТО. Ако кодът не може да различи
„питах и няма" от „не можах да питам", всяка авария изглежда като мир.
"""
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SOFIA = ZoneInfo("Europe/Sofia")
NL = chr(10)
REPO = os.environ.get("ZDRAVE_REPO") or "AEROBOTAMOVE/greenpicks-bots"

# 🔴 СЕНТИНЕЛ „НЕ МОЖАХ ДА ПИТАМ" (25.08.2026).
# НЕ е списък, НЕ е None, НЕ е празно. Точно това уби предишната версия:
# `except Exception: return []` прави отказа на GitHub неразличим от чист CI,
# а после `if rr:` мълчаливо изхвърляше ЦЕЛИЯ раздел — доклад без ред за CI
# се чете като доклад без проблеми в CI.
NEPITAN = object()

# Workflow-ите, които НОСЯТ ПРОДУКТА, и се питат ПООТДЕЛНО.
# Общият списък `actions/runs` е безполезен тук: измерено 25.08.2026 — 30 рънa
# покриват 1.92 часа, защото рутерът пуска ~14 на час. Оценителят гърми на
# всеки ~9 часа и не попада в прозореца НИКОГА.
# pazach.yml е вътре нарочно: пазачът не следи себе си (той няма себе си в
# своя списък), а „не е тръгвал" и „тръгна и е наред" произвеждат едно и също
# нищо. Тук поне се вижда дали ИЗОБЩО върви.
VAZHNI = (
    ("predict.yml", "предсказателят пуска карти"),
    ("score.yml", "оценителят отсъжда и отчита"),
    ("router.yml", "рутерът разнася по стаите"),
    ("daily.yml", "дневният бот и здравният преглед"),
    ("news.yml", "новините"),
    ("matches.yml", "мачовете за деня"),
    ("support.yml", "съпортът и будилникът"),
    ("pazach.yml", "самият пазач"),
)

# Колко минути закъснение на GitHub са допустими НАД собствения крон.
# Измерено върху 55 пускания (12.08.2026): медиана 65 мин, 34 от 55 над час.
# Гратисът е по-голям от медианата НАРОЧНО — пазач, който крещи напразно, се
# научава да се пренебрегва.
GRATIS_MIN = max(15, min(600, int((os.environ.get("ZDRAVE_GRATIS") or "100").strip() or 100)))

# Заключенията, които БРОИМ ЗА ЧЕРВЕНО. Останалите (cancelled, skipped,
# neutral) НЕ са провал, но не са и успех — за тях се пише „не мога да
# преценя", не „наред".
CHERVENI_ZAKL = ("failure", "timed_out", "startup_failure", "action_required")

# Над колко часа застояла черна кутия числата в нея вече не описват днеска.
# Предсказателят пуска на всеки час между 08 и 22 БГ — два пропуснати часа са
# вече дупка, но три са гратисът за закъснелия крон.
STAR_STATE_CH = max(1.0, min(48.0, float((os.environ.get("ZDRAVE_STATE_CH") or "3").strip() or 3)))

# След колко дни приключените записи слизат в архива. Огледало на
# scorer.py:1937 (ARHIV_DNI, по подразбиране 60). Тук се ползва САМО за да се
# обясни празният архив с думи, не с мълчание.
ARHIV_DNI = max(30, min(400, int((os.environ.get("SCORE_ARHIV_DNI") or "60").strip() or 60)))


def vazrast_ch(koga, sega):
    """На колко ЧАСА е този печат на времето. None = не го разбрах.

    Форматът идва от predictor.py:806 — `now.strftime("%Y-%m-%d %H:%M")` в
    българско време. „Не разбрах" НЕ Е „нула часа": връща None, а извикващият
    е длъжен да го каже на глас.
    """
    s = str(koga or "").strip().replace("T", " ")
    for f, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        if len(s) < n:
            continue
        try:
            t = datetime.strptime(s[:n], f)
        except ValueError:
            continue
        return max(0.0, (sega - t.replace(tzinfo=SOFIA)).total_seconds() / 3600.0)
    return None

IME = {
    "football": "⚽ Футбол", "basketball": "🏀 Баскетбол",
    "volleyball": "🏐 Волейбол", "tabletennis": "🏓 Тенис на маса",
    "tennis": "🎾 Тенис", "baseball": "⚾ Бейзбол", "mma": "🥊 ММА",
    "hockey": "🏒 Хокей", "amfootball": "🏈 Амер. футбол",
}

# Спортове, за които ПРАЗНО Е НОРМАЛНО и кога свършва. Пълни се от измерване,
# не от усещане: NHL връща nextStartDate, NFL дава само предсезонни.
# 🔴 РЯДКИ ПО УСТРОЙСТВО (12.08.2026). Спорт, който мълчи ЗАКОНОМЕРНО, не бива
# да пали тревога всеки ден — пазач, който крещи напразно, се научава да се
# пренебрегва, и когато утре гръмне истински, никой не поглежда.
# Измерено върху живия дневник: за 15 дни ММА е дал карти в ЕДИН ден.
# Затова: мълчи ли под тавана в дни, това е състояние, не проблем. Над него —
# вече е проблем и се изписва.
RYADKI = {"mma": (10, "боевете са по няколко на седмица — измерено, карти в"
                      " 1 от 15 дни")}

IZVAN_SEZONA = {
    "hockey": "НХЛ отваря около 15.09 — дотогава източникът връща нула игри",
    "amfootball": "НФЛ дава само предсезонни, а гейтът ги реже нарочно",
}

# 🔴 ЗАТВОРЕНИ (11.08.2026). Не се питат изобщо — предсказателят не ги пуска.
# Списъкът НЕ е закован тук: чете се от самия predictor.py, за да не се
# разминат двата файла. Разминат ли се, прегледът щеше да крещи за спорт,
# който никой не предрича — или да мълчи за спорт, който вали в празна стая.
# 🔴 ДВАТА ТИХИ ОТКАЗА (поправено 25.08.2026).
# Тук стояха два реда, които връщаха отговор, без да са го прочели:
#   • не мога да отворя predictor.py → връщаше ЗАКОВАНОТО {hockey, amfootball},
#     тоест точно това, което докстрингът три реда по-горе обещава да НЕ прави;
#   • маркерът `_izkl_raw = "` го няма (преименуван, преформатиран) → връщаше
#     set(), тоест „нито един спорт не е затворен" — и двата истински
#     затворени спорта падаха в клона „няма данни за последния рън", който не
#     добавя НИЩО в problemi. Тишина и в двете посоки.
# Сега и двата връщат NEPITAN и main() го казва на глас. Същият модел като
# support_bot.py:1391, който вече носи коментара „Празно множество никога не
# значи «няма какво да се провери»".
def zatvoreni():
    _ot_sredata = os.environ.get("PREDICT_IZKL")
    if _ot_sredata is not None:
        return {s.strip() for s in _ot_sredata.split(",") if s.strip()}
    try:
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "predictor.py"), encoding="utf-8-sig") as f:
            src = f.read()
    except Exception:                                        # noqa: BLE001
        return NEPITAN
    marker = "_izkl_raw = " + chr(34)
    i = src.find(marker)
    if i < 0:
        return NEPITAN
    j = src.find(chr(34), i + len(marker))
    return {s.strip() for s in src[i + len(marker):j].split(",") if s.strip()}


_ZATV = zatvoreni()
ZATVORENI_NEYASNO = _ZATV is NEPITAN
ZATVORENI = set() if ZATVORENI_NEYASNO else _ZATV
# ═══════════════ КОГА ТРЪГВА ЗАТВОРЕНИЯТ СПОРТ (пренаписано 25.08.2026)
#
# 🔴 ТУК СТОЕШЕ ЖИВА ЛЪЖА. Заковано пишеше:
#       hockey     -> „тръгва около 15.09, когато НХЛ отваря"
#       amfootball -> „тръгва в началото на септември"
# Измерено живо същия ден от sezon.py, право от източниците:
#       NHL  regularSeasonStartDate = 2026-09-29   ← ДВЕ СЕДМИЦИ по-късно
#       NFL  първи редовен мач      = 2026-09-10
# Тоест прегледът две седмици щеше да обяснява спокойно защо хокеят мълчи,
# докато хокеят вече играе — или обратното, да го чака когато няма какво.
#
# Заковано число, което дублира измерено число, е обречено да се разминава.
# Затова тук вече НЯМА дата: тя се чете от sezon.OTVARYA, където живее
# заедно с източника, от който е взета.
#
# 🔴 И КАПАНЪТ, КОЙТО sezon.py ПЛАТИ ЗА НАС: `nextStartDate` изглежда точно
# като „кога тръгва", но е границата на СЪСЕДНАТА КАЛЕНДАРНА СЕДМИЦА
# (2026-10-06), не началото на сезона. Вярното поле е regularSeasonStartDate.
def _ot_sezon():
    """{кош: (дата, сигурно_ли)} от sezon.OTVARYA. Празно, ако не се зареди."""
    try:
        import sezon as _SZ
        tabl = getattr(_SZ, "OTVARYA", None) or {}
    except Exception:                                        # noqa: BLE001
        return {}
    if not tabl:
        return {}
    # 🔴 САМО ВАЖНИТЕ ПЪРВЕНСТВА. Първата ми версия взимаше най-ранната дата
    # от ВСИЧКИ и излезе „хокеят тръгва на 18.09" — това е NCAA при ЖЕНИТЕ,
    # отбелязано в календара като НЕважно. Истинският хокей за нашия бот е
    # НХЛ: 29.09. Тоест грубото „най-ранното печели" произведе НОВА лъжа на
    # мястото на старата, при това с измерено число — най-опасният вид.
    vazhni = set()
    try:
        for red in (getattr(_SZ, "KALENDAR", None) or []):
            if isinstance(red, dict) and red.get("vazhen"):
                vazhni.add(str(red.get("kod") or ""))
    except Exception:                                        # noqa: BLE001
        vazhni = set()
    out = {}
    for _kod, red in tabl.items():
        if not isinstance(red, dict):
            continue
        if vazhni and str(_kod) not in vazhni:
            continue                     # NCAA при жените не отваря хокея
        kosh, data = red.get("kosh"), str(red.get("data") or "")
        if not kosh or len(data) != 10:
            continue
        # Между ВАЖНИТЕ печели най-ранното: амер. футбол тръгва с NCAA (29.08),
        # не с НФЛ (10.09), и двете са важни за нас.
        if kosh not in out or data < out[kosh][0]:
            out[kosh] = (data, bool(red.get("sigurno")))
    return out


def koga_tragva(kosh, tabl=None):
    """Текстът „тръгва на ...". Никога не изрича дата, която не е измерена."""
    tabl = _ot_sezon() if tabl is None else tabl
    red = tabl.get(str(kosh or ""))
    if not red:
        return "до старта на сезона"
    data, sigurno = red
    d = data[8:10].lstrip("0") + "." + data[5:7]
    return ("тръгва на " + d if sigurno
            else "тръгва около " + d + " (още не е сигурно)")


KOGA_TRAGVA = {}          # запазено име; истината идва от koga_tragva()


def chetiv(path, po_podrazbirane):
    try:
        with io.open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:                                        # noqa: BLE001
        return po_podrazbirane


def _glavi():
    g = {"Accept": "application/vnd.github+json", "User-Agent": "greenpicks-zdrave"}
    tok = os.environ.get("GITHUB_TOKEN", "")
    if tok:
        g["Authorization"] = "Bearer " + tok
    return g


# 🔴 ТРИТЕ ИЗХОДА, НЕ ДВАТА (25.08.2026).
# Дотук съобщението беше „(GitHub мълчи: <60 знака> — чета локалното)" и НЕ
# КАЗВАШЕ КОЙ ФАЙЛ е паднал — а трите извиквания печатат едно и също.
# Измерено на живо 25.08: predict_log.json → 444684 байта ЕСТЬ,
# predict_state.json → 26640 байта ЕСТЬ, predict_log_arhiv.json → HTTP 404.
# Читателят нямаше как да разбере ЧИЯ история липсва.
# Сега: 404 = „файлът още го няма" (нормално, тихо) е РАЗЛИЧНО от 403/timeout/
# 5xx = „не можах да питам" (сентинел, влиза в ЗА ГЛЕДАНЕ).
def ot_github(path):
    """Чете файл от хранилището. През api, не през raw — raw КЕШИРА и лъже.

    Връща: данните · None при 404 (няма го, това е отговор) · NEPITAN при
    всякакъв друг отказ (това НЕ е отговор и не бива да мълчи).
    """
    import base64
    url = "https://api.github.com/repos/" + REPO + "/contents/" + path + "?ref=main"
    try:
        rq = urllib.request.Request(url, headers=_glavi())
        with urllib.request.urlopen(rq, timeout=30) as r:
            return json.loads(base64.b64decode(json.loads(r.read())["content"]))
    except Exception as e:                                   # noqa: BLE001
        kod = getattr(e, "code", None)
        if kod == 404:
            print("   (" + path + ": още го няма в хранилището — чета локалното)")
            return None
        print("   (НЕ МОЖАХ да питам за " + path + ": " + str(e)[:60] + ")")
        return NEPITAN


def _api(path, timeout=30):
    """Отговорът на GitHub, или NEPITAN при какъвто и да е отказ.

    🔴 НИКОГА не връща празен списък при неуспех.
    """
    url = "https://api.github.com/repos/" + REPO + "/" + path
    try:
        rq = urllib.request.Request(url, headers=_glavi())
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:                                   # noqa: BLE001
        print("   (НЕ МОЖАХ да питам за " + path[:44] + ": " + str(e)[:60] + ")")
        return NEPITAN


def runove_na(ime, broi=10):
    """Последните рънове на ЕДИН workflow. NEPITAN, ако питането се провали."""
    j = _api("actions/workflows/" + ime + "/runs?per_page=" + str(int(broi)))
    if j is NEPITAN or not isinstance(j, dict):
        return NEPITAN
    return j.get("workflow_runs") or []


# ═══════════════════════════════ ⏱️ ПРАГЪТ СЕ СМЯТА ОТ СОБСТВЕНИЯ CRON
#
# Праг, забит на ръка, остарява мълчаливо: сменят крона, прагът остава и
# пазачът или крещи, или спи. Затова се чете от самия .yml.
# „Не разбрах крона" НЕ Е „наред" — връща се None и се казва на глас.
def cron_ot_yml(tekst):
    """Всички cron редове от един workflow файл. Закоментираните НЕ се броят."""
    out = []
    for red in str(tekst or "").split(NL):
        gol = red.strip()
        if gol.startswith("#") or "cron:" not in gol:
            continue
        sled = gol.split("cron:", 1)[1].strip()
        if "#" in sled:                       # '30 10 * * *'   # 13:30 BG
            sled = sled.split("#", 1)[0].strip()
        sled = sled.strip().strip("'").strip('"').strip()
        if sled:
            out.append(sled)
    return out


def _pole(p, gorna):
    """Стойностите, в които едно cron поле пали. Празно = не го разбрах."""
    p = str(p or "").strip()
    if p == "*":
        return list(range(gorna))
    if p.startswith("*/"):
        try:
            k = int(p[2:])
        except ValueError:
            return []
        return list(range(0, gorna, k)) if 0 < k <= gorna else []
    out = []
    for chast in p.split(","):
        chast = chast.strip()
        if "-" in chast:
            try:
                a, b = [int(x) for x in chast.split("-", 1)]
            except ValueError:
                return []
            if not (0 <= a < gorna and 0 <= b < gorna):
                return []
            out += (list(range(a, b + 1)) if a <= b
                    else list(range(a, gorna)) + list(range(0, b + 1)))
            continue
        try:
            v = int(chast)
        except ValueError:
            return []
        if not 0 <= v < gorna:
            return []
        out.append(v)
    return sorted(set(out))


def period_min(cronove):
    """Най-ГОЛЯМАТА законна пауза между две палления, в минути. None = не разбрах.

    Взима се най-голямата, не средната: прагът трябва да мълчи през най-дългата
    ЗАКОННА тишина, инак прегледът крещи всяка нощ. Пример, измерен от живите
    файлове: score.yml има `30 10` и `30 19` UTC → дупките са 9 ч и 15 ч,
    прагът стъпва на 15 ч.
    """
    tochki = set()
    for c in (cronove or []):
        parcheta = str(c or "").split()
        if len(parcheta) < 5:
            continue
        # Ден-от-месеца / месец / ден-от-седмицата, различни от '*', значат
        # рядко разписание, което НЕ мога да сведа до денонощен период.
        if any(x.strip() != "*" for x in parcheta[2:5]):
            return None
        minuti = _pole(parcheta[0], 60)
        chasove = _pole(parcheta[1], 24)
        if not minuti or not chasove:
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
        raz = (t[(i + 1) % len(t)] - t[i]) % (24 * 60)
        nay = max(nay, raz or 24 * 60)
    return nay


def _lokalen_yml(ime):
    """Съдържанието на workflow файла от диска. None, ако го няма."""
    baza = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(baza, ".github", "workflows", ime),
              os.path.join(".github", "workflows", ime)):
        if os.path.exists(p):
            try:
                with io.open(p, encoding="utf-8-sig") as f:
                    return f.read()
            except Exception:                                # noqa: BLE001
                return None
    return None


def dopusk_min(ime, chetec=None):
    """Колко минути мълчание са ДОПУСТИМИ за този workflow. None = не знам."""
    t = (chetec or _lokalen_yml)(ime)
    if t is None:
        return None
    p = period_min(cron_ot_yml(t))
    return None if p is None else p + GRATIS_MIN


def _kogato(r):
    """run_started_at като datetime с часова зона. None, ако не се чете."""
    s = str((r or {}).get("run_started_at") or (r or {}).get("created_at") or "")
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def sadi_workflow(ime, opis, rr, dopusk, sega):
    """Присъдата за ЕДИН workflow. Състоянията са ЧЕТИРИ, не две.

        naredno  — питах, виждам го, работи
        cherveno — питах, виждам го, счупен е
        mulchi   — питах, виждам история, но от много време няма нов рън
        nepitan  — НЕ МОГА да питам, или не знам прага

    Точно липсата на четвъртото уби предишната версия: тя знаеше само „наред"
    и „червено", а истината има и „не знам". Връща речник, за да може и
    отчетът, и присъдата да ползват ЕДНИ И СЪЩИ числа.
    """
    d = {"ime": ime, "opis": opis, "sast": "nepitan", "tekst": "", "kak": "",
         "poredni": 0, "ot_uspeh_ch": None, "posleden_uspeh": "",
         "dopusk_ch": (None if dopusk is None else dopusk / 60.0)}

    def _kaz(sast, kak):
        d["sast"] = sast
        d["kak"] = kak
        d["tekst"] = "%s (%s): %s" % (ime, opis, kak)
        return d

    if rr is NEPITAN:
        return _kaz("nepitan", "НЕ МОЖАХ да питам GitHub — това НЕ значи «наред»")
    if not rr:
        return _kaz("nepitan", "GitHub не върна НИТО ЕДИН рън — не мога да преценя")

    gotovi = [r for r in rr if str(r.get("status") or "") == "completed"]
    for r in gotovi:                       # поредните провали са в НАЧАЛОТО
        if str(r.get("conclusion") or "") in CHERVENI_ZAKL:
            d["poredni"] += 1
        else:
            break
    uspeh = None
    for r in gotovi:
        if str(r.get("conclusion") or "") == "success":
            uspeh = r
            break
    if uspeh is not None:
        d["posleden_uspeh"] = str(uspeh.get("run_started_at") or "")[:16].replace("T", " ")
        k = _kogato(uspeh)
        if k is not None:
            d["ot_uspeh_ch"] = max(0.0, (sega - k).total_seconds() / 3600.0)

    ot = d["ot_uspeh_ch"]
    sufiks = ("" if ot is None else " · последен успех преди %.0f ч" % ot)
    if d["poredni"]:
        return _kaz("cherveno", "%d ПОРЕДНИ провала%s" % (d["poredni"], sufiks))
    if dopusk is None:
        return _kaz("nepitan", "не разбрах крона му — нямам праг, не мога да"
                               " преценя мълчи ли")
    if uspeh is None:
        return _kaz("nepitan", "в последните %d рънa няма НИТО ЕДИН успешен"
                               " — не мога да преценя" % len(rr))
    if ot is not None and ot * 60.0 > dopusk:
        return _kaz("mulchi", "не е успявал от %.0f ч, а по собствения си cron"
                              " дължи на всеки %.0f ч" % (ot, dopusk / 60.0))
    return _kaz("naredno", "наред%s" % sufiks)


def obhod(chetec=None, yml=None, sega=None):
    """Присъдите за ВСИЧКИТЕ VAZHNI. [(речник), ...] в реда на VAZHNI.

    `chetec(ime) -> рънове | NEPITAN` и `yml(ime) -> текст | None` се подават
    само от самопроверката; в живота са GitHub и дискът.
    """
    chetec = chetec or runove_na
    sega = sega or datetime.now(timezone.utc)
    return [sadi_workflow(ime, opis, chetec(ime), dopusk_min(ime, yml), sega)
            for ime, opis in VAZHNI]


def kraj_za_visyashti(sc):
    """Изречението след броя висящи. Гради се от ПРИСЪДАТА на score.yml.

    🔴 Числото и думата до него не бива да си противоречат. Дотук тук стоеше
    неусловно обещание „изчистват се на следващото пускане на оценителя" — и то
    се печаташе на 24.08 20:34 с 47 прогнози, в час, в който оценителят вече
    беше гръмнал два пъти. Обещанието се дава САМО ако механизмът е проверен жив.
    """
    sc = sc or {}
    if sc.get("sast") == "naredno":
        return (" (изчистват се на следващото пускане на оценителя, 13:30 и"
                " 22:30 БГ; последният УСПЕШЕН беше "
                + str(sc.get("posleden_uspeh") or "?") + ")")
    if sc.get("sast") == "nepitan" or not sc:
        return (" (НЕ можах да проверя жив ли е оценителят — не обещавам, че"
                " ще се изчистят)")
    ot = sc.get("ot_uspeh_ch")
    return (" — ОЦЕНИТЕЛЯТ НЕ Е МИНАВАЛ УСПЕШНО"
            + ("" if ot is None else " от %.0f ч" % ot)
            + ": тези НЯМА да се изчистят сами")


# ═══════════════════════════════════ 📐 КАЛИБРАЦИЯ (12.08.2026)
#
# Най-важното число за продукт, който продава вероятности: като каже 70%,
# сбъдва ли се 70%? Измерено веднъж на живо върху 279 отсъдени, ботът се
# ПОДЦЕНЯВАШЕ — обещава 63.4%, сбъдва 70.6%. Средният ешелон биеше обещаното
# с над единайсет пункта.
#
# Това не е дефект, който яде пари. Но е разминаване между числото и истината,
# а правилото на собственика е точно това. И е нещо, което не бива да се мери
# веднъж и да се забрави — затова живее тук и излиза при всеки преглед.
#
# НЕ пипаме модела заради него. Числото само се показва; решението е човешко.
KOFI = ((0.45, 0.53), (0.53, 0.60), (0.60, 0.68), (0.68, 0.80), (0.80, 1.01))
KALIB_MIN = 40          # под толкова отсъдени не се произнасяме изобщо
KALIB_PRAG = 8.0        # пунктове разминаване, над които го наричаме проблем


def kalibraciya(log, bucket=None):
    """[(етикет, брой, обещано%, сбъднато%)] + общият ред. Празно = малко данни."""
    ots = [r for r in (log or [])
           if r.get("scored") and r.get("hit") is not None and r.get("p")
           and (bucket is None or r.get("bucket") == bucket)]
    if len(ots) < KALIB_MIN:
        return [], len(ots)
    out = []
    for a2, b2 in KOFI:
        g = [r for r in ots if a2 <= float(r["p"]) < b2]
        if len(g) < 10:
            continue
        out.append(("%d-%d%%" % (a2 * 100, b2 * 100), len(g),
                    100.0 * sum(float(r["p"]) for r in g) / len(g),
                    100.0 * sum(1 for r in g if r["hit"]) / len(g)))
    out.append(("ВСИЧКО", len(ots),
                100.0 * sum(float(r["p"]) for r in ots) / len(ots),
                100.0 * sum(1 for r in ots if r["hit"]) / len(ots)))
    return out, len(ots)


# ═══════════════════════════════════ 📊 СРЕЩУ ПАЗАРА (13.08.2026)
#
# Единственият въпрос, който отличава истински бот от познавач на фаворити:
# когато пазарът казва 55%, а ние казваме 62% — кой е прав?
#
# Мери се така: взимат се само прогнозите, които имат И наша вероятност, И
# пазарна. Разделят се на две купчини — там, където сме БИЛИ ПО-СМЕЛИ от
# пазара, и там, където сме били по-предпазливи. После се гледа коя купчина
# е сбъднала повече от обещаното си.
#
# Ако сме прави, когато се разминаваме с пазара, имаме ръб. Ако не сме —
# просто повтаряме пазара с шум отгоре, а това е скъпо нищо.
#
# Измервателят се пише ПРЕДИ данните, за да не се нагажда после към тях.
# ═══════════════════════════════════ 💰 ПАРИТЕ (25.08.2026)
#
# ЗАЩО СА ТУК, А НЕ В КАНАЛА. На 25.08 разделът „💰 Струва ли си" излезе от
# съобщенията в стаята — и с право: „средна цена 1.76" е коефициент под друга
# дума, а „доходност при равен залог" е възвръщаемост на залог. Каналът
# твърди, че не е за залози, и това правило се спазва.
#
# Но да изчезнат СЪВСЕМ значеше две загуби наведнъж: собственикът губи
# единственото число, което отговаря на „струва ли си", а dohodnost() и
# clv_text() остават мъртви във файла — портата за цялост ги хвана точно така.
#
# Затова живеят ТУК. Прегледът се чете от собственика, не от публиката, и се
# връща в хранилището като zdrave.txt. Правилото на продукта не е нарушено:
# то пази СТАЯТА, не тефтера.
#
# 🔴 И ЕДНО, КОЕТО ЛИПСВАШЕ В ОРИГИНАЛА: ИНТЕРВАЛЪТ. dohodnost() връща
# „−15.5%" голо. Измерено на живо същия ден: истинският интервал на това
# число е [−29.4 .. −1.6], а на по-ранните 46 карти беше [−36.5 .. +11.3] —
# тоест числото не отговаряше на нищо, а изглеждаше като отговор.
# Число без интервал не може да бъде оспорено.
def _interval(vals):
    """(средно, долу, горе) при 95%. (0,0,0) при по-малко от две стойности."""
    vals = [float(v) for v in (vals or [])]
    if len(vals) < 2:
        return (0.0, 0.0, 0.0)
    m = sum(vals) / len(vals)
    sd = (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
    se = 1.96 * sd / (len(vals) ** 0.5)
    return (m, m - se, m + se)


def kolko_oshte(vals, efekt=0.05):
    """Колко залога трябват, за да се докаже ръб от `efekt`. 0 = не знам."""
    vals = [float(v) for v in (vals or [])]
    if len(vals) < 3 or efekt <= 0:
        return 0
    m = sum(vals) / len(vals)
    sd = (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
    if sd <= 0:
        return 0
    return int((1.96 * sd / efekt) ** 2)


def parite(log):
    """Редовете за парите. Празно, ако оценителят не се зарежда.

    Сметките НЕ се преписват тук — викат се тези на оценителя, за да има
    ЕДНО място, където се смятат. Добавя се само интервалът, който им липсва.
    """
    out = []
    try:
        import scorer as SC
    except Exception as e:                                   # noqa: BLE001
        return ["  (оценителят не се зареди: " + str(e)[:50] + ")"]

    rows = list(log or [])
    try:
        red, n = SC.dohodnost(rows)
    except Exception as e:                                   # noqa: BLE001
        return ["  (доходността гръмна: " + str(e)[:50] + ")"]
    if not red:
        return ["  %d отсъдени с проверена цена — трябват поне %d"
                % (n, getattr(SC, "DOHOD_MIN", 40))]
    out += list(red)

    # Интервалът се смята от СЪЩИТЕ редове, по които оценителят е смятал.
    g = [r for r in rows if r.get("hit") is not None and r.get("pazar_cena")
         and int(r.get("pazar_v") or 0) >= 2]
    vals = [(float(r["pazar_cena"]) - 1.0 if r.get("hit") else -1.0) for r in g]
    m, lo, hi = _interval(vals)
    out.append("  %-27s %+.1f%% .. %+.1f%%" % ("а честно, интервалът е",
                                               100.0 * lo, 100.0 * hi))
    if lo <= 0 <= hi:
        out.append("  %-27s %s" % ("присъда",
                                   "нулата е ВЪТРЕ — още не може да се твърди"))
    else:
        out.append("  %-27s %s" % ("присъда",
                                   "ПЕЧЕЛИ" if lo > 0 else "ГУБИ"))
    for ef in (0.05, 0.10):
        n_tr = kolko_oshte(vals, ef)
        if n_tr:
            out.append("  %-27s %d (имаме %d)"
                       % ("за ръб от %+.0f%% трябват" % (100 * ef), n_tr, len(g)))
    try:
        cl, cn = SC.clv_text(rows)
        if cl:
            out += list(cl)
            cvals = [float(r["pazar_clv"]) for r in rows
                     if r.get("pazar_clv") is not None
                     and int(r.get("pazar_v") or 0) >= 2]
            cm, clo, chi = _interval(cvals)
            out.append("  %-27s %+.2f .. %+.2f точки"
                       % ("интервалът на движението", 100.0 * clo, 100.0 * chi))
        else:
            out.append("  %d записа с движение — трябват поне %d"
                       % (cn, getattr(SC, "CLV_MIN", 20)))
    except Exception as e:                                   # noqa: BLE001
        out.append("  (движението гръмна: " + str(e)[:50] + ")")
    return out


# ═══════════════════════════════ 🎯 ЛИГИТЕ, КОИТО НИ БИЯТ (25.08.2026)
#
# ЗАЩО: калибрацията дотук се мереше по СПОРТ. Спорт обаче не е еднородно
# нещо. Измерено на живо същия ден върху 696 отсъдени:
#
#   ECVA Senior Men's Volleyball   n=15  обявява 66%  сбъдва 33%  −33 т
#   MLS                            n=11  обявява 57%  сбъдва 36%  −21 т
#   WTT Feeder Berlin · Мъже       n=25  обявява 68%  сбъдва 52%  −16 т
#
# Волейболът като цяло изглежда честен (−3.7 т, вътре в шума). Вътре в него
# обаче се крие лига, която греши с ТРИЙСЕТ И ТРИ точки — карибски
# микрофедерации, където сме обявявали и 92% и сме губили. Средното я скрива.
#
# 🔴 И ОБРАТНОТО СЪЩО: Europe Smash Жени n=34 обявява 59%, сбъдва 88% (+29 т).
# Подценяването не боли по джоба, но е същото разминаване между дума и истина.
#
# ПРАГЪТ Е ШУМЪТ, НЕ КРЪГЛО ЧИСЛО. Лига с 10 мача и 15 точки разлика е шум;
# лига с 60 мача и 15 точки не е. Затова се сравнява със собствения ѝ шум.
LIGA_MIN = max(8, min(60, int(
    (os.environ.get("ZDRAVE_LIGA_MIN") or "12").strip() or 12)))


def _shum(p, n):
    """95% шум около дял p при n наблюдения."""
    n = max(1, int(n or 0))
    p = min(max(float(p or 0.0), 0.0), 1.0)
    return 1.96 * ((p * (1.0 - p) / n) ** 0.5)


def krivi_ligi(log, minimum=None):
    """[(лига, n, обявено, сбъднато, разлика)] — САМО извън собствения си шум.

    Подредени от най-надценяващата към най-подценяващата: първо тези, които
    обещават повече, отколкото сбъдват, защото те лъжат читателя в неговия
    ущърб.
    """
    minimum = LIGA_MIN if minimum is None else int(minimum)
    po_liga = {}
    for r in (log or []):
        if not isinstance(r, dict):
            continue
        if r.get("hit") is None or not r.get("p"):
            continue
        po_liga.setdefault(str(r.get("league") or "?"), []).append(r)
    out = []
    for ime, g in po_liga.items():
        if len(g) < minimum:
            continue
        try:
            ob = sum(float(x["p"]) for x in g) / len(g)
        except (TypeError, ValueError):
            continue
        sb = sum(1 for x in g if x.get("hit")) / float(len(g))
        if abs(sb - ob) > _shum(ob, len(g)):
            out.append((ime, len(g), ob, sb, sb - ob))
    out.sort(key=lambda t: t[4])
    return out


# ═══════════════════════════════ 🚫 НЕЗАЛОЖИМИТЕ (25.08.2026)
#
# Желязното правило на собственика: „ИСКАМ НАИСТИНА ДА НАТИСНЕШ НАД ВСИЧКИ
# ПРОГНОЗИ ДА ГИ ИМА В БУКМЕЙКЪРА." Пазарът за юношески турнири НЕ
# СЪЩЕСТВУВА при никой букмейкър — нито за момичета до 17, нито за кадети.
#
# Измерено на живо 25.08.2026: 73 от 174 волейболни карти (42%) са юношески,
# от които 64 са само FIVB Girls' U17. Тоест правилото е нарушено при четири
# от всеки десет волейболни карти — тихо, откакто съществува.
#
# 🔴 ТОВА НЕ Е ДЕФЕКТ В ПРОГНОЗИТЕ. Те са честни: обявяват 76%, сбъдват 73%.
# Дефектът е, че не могат да се играят — а продуктът обещава, че могат.
# Затова тук само се БРОИ и се казва; решението кой турнир отпада е човешко.
YUNOSHESKI = ("u17", "u18", "u16", "u19", "u20", "u21", "u23",
              "girls", "boys", "youth", "junior", "cadet", "юнош")
YUNOSHESKI_PRAG = max(5, min(90, int(
    (os.environ.get("ZDRAVE_YUNOSHESKI") or "15").strip() or 15)))


def yunosheski_li(liga):
    """Юношески ли е турнирът, по името му."""
    l = str(liga or "").lower()
    return any(d in l for d in YUNOSHESKI)


def nezalozhimi(log, bucket=None):
    """(брой, общо, [(лига, брой)]) за юношеските турнири."""
    g = [r for r in (log or [])
         if isinstance(r, dict) and (bucket is None or r.get("bucket") == bucket)]
    yu = {}
    for r in g:
        if yunosheski_li(r.get("league")):
            k = str(r.get("league") or "?")
            yu[k] = yu.get(k, 0) + 1
    return (sum(yu.values()), len(g),
            sorted(yu.items(), key=lambda t: -t[1]))


PAZAR_MIN = 30          # под толкова двойки не се произнасяме


def sreshtu_pazara(log):
    """(редове за печат, брой сравними). Празно, ако още няма данни."""
    # 🔴 САМО ВЕРСИЯ 2+ (18.08.2026). Версия 1 записваше суровото `1/цена`, в
    # което седи делът на букмейкъра: измерено 7.4% при футбола, 1.9% при
    # бейзбола. Прагът тук е 2% — тоест старите записи са изкривени с повече
    # от цялата ширина на самия праг. Не се смесват.
    dvoyki = [r for r in (log or [])
              if r.get("scored") and r.get("hit") is not None
              and r.get("p") and r.get("pazar_p")
              and int(r.get("pazar_v") or 0) >= 2]
    if len(dvoyki) < PAZAR_MIN:
        return [], len(dvoyki)
    smeli = [r for r in dvoyki if float(r["p"]) > float(r["pazar_p"]) + 0.02]
    plahi = [r for r in dvoyki if float(r["p"]) < float(r["pazar_p"]) - 0.02]
    ednakvi = len(dvoyki) - len(smeli) - len(plahi)
    out = []
    for ime, g in (("по-смели от пазара", smeli), ("по-предпазливи", plahi)):
        if len(g) < 10:
            continue
        sbd = 100.0 * sum(1 for r in g if r["hit"]) / len(g)
        nash = 100.0 * sum(float(r["p"]) for r in g) / len(g)
        paz = 100.0 * sum(float(r["pazar_p"]) for r in g) / len(g)
        out.append("   %-20s %3d · ние %.0f%% · пазарът %.0f%% · сбъдна се %.0f%%"
                   % (ime, len(g), nash, paz, sbd))
    out.append("   %-20s %3d" % ("почти еднакви", ednakvi))
    return out, len(dvoyki)


def koga_pak(sportove, now, napred_dni=7):
    """{спорт: след колко дни има мач}. Празно, ако няма или не се чете.

    Пита самия предсказател, не измисля. Всяка грешка е тишина, не тревога —
    целта е да НЕ вдигаме фалшив флаг, а не да гадаем календари.
    """
    out = {}
    try:
        import predictor as P
    except Exception:                                        # noqa: BLE001
        return out
    fn = {"volleyball": lambda d: P.vol_fixtures(d, d.strftime("%Y-%m-%d")),
          "tabletennis": lambda d: P.tt_fixtures(d, d.strftime("%Y-%m-%d")),
          "tennis": lambda d: P.tennis_fixtures(d, d.strftime("%Y%m%d")),
          "basketball": lambda d: P.basketball_fixtures(d, d.strftime("%Y%m%d")),
          "football": lambda d: P.football_fixtures(d, d.strftime("%Y%m%d")),
          "baseball": lambda d: P.baseball_fixtures(d, d.strftime("%Y-%m-%d")),
          "mma": lambda d: P.mma_fixtures(d)}
    for b in sportove:
        # 🔴 ТЕНИСЪТ НА МАСА СЕ ПИТА ПО КАЛЕНДАР, НЕ ПО РАЗПИСАНИЕ (18.08.2026).
        # WTT пуска разписанието ден-два преди турнира. Питането „има ли мач
        # утре" връщаше НЕ, макар календарът да казва „турнир от утре" — и
        # прегледът гърмеше червено за спорт в най-обикновена пауза.
        if b == "tabletennis":
            try:
                d_tt = P.tt_turnir_sled(now, napred_dni)
            except Exception:                                # noqa: BLE001
                d_tt = None
            # 🔴 НУЛАТА Е ОТГОВОР, НЕ ЛИПСА (поправено 18.08.2026).
            # Тук стоеше `>= 1` и изхвърляше 0 — а 0 значи „турнир ТЕЧЕ днес".
            # Точно на ПЪРВИЯ ден на всеки турнир WTT още не е пуснал
            # разписанието, тоест мачове няма, а календарът вече казва защо.
            # Изхвърлената нула връщаше фалшивата тревога, заради която
            # цялата функция е написана.
            if d_tt is not None and d_tt >= 0:
                out[b] = d_tt
            continue
        f = fn.get(b)
        if not f:
            continue
        for k in range(1, max(1, int(napred_dni)) + 1):
            try:
                if f(now + timedelta(days=k)):
                    out[b] = k
                    break
            except Exception:                                # noqa: BLE001
                break
    return out


def main():
    kratko = "--kratko" in sys.argv
    now = datetime.now(SOFIA)
    dnes = now.strftime("%Y-%m-%d")
    vchera_den = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    problemi = []
    nepitani = []          # какво НЕ можах да проверя. Не е „чисто".

    log = ot_github("predict_log.json")
    if log is NEPITAN:
        nepitani.append("predict_log.json от GitHub — чета локалното копие,"
                        " което може да е старо")
        log = None
    if log is None:
        log = chetiv("predict_log.json", [])
    # 🗄️ 18.08.2026. Приключените стари записи вече живеят в архив, за да не
    # расте горещият дневник без таван. Статистиката обаче иска ЦЕЛИЯ живот —
    # иначе успеваемостта ще се „нулира" на всеки 120 дни без причина.
    # 🔴 25.08.2026: трите случая се разделят. Дотук редът „(плюс N архивни
    # записа)" се печаташе САМО при непразен архив — тоест „няма архив" и
    # „архивът се загуби" звучаха еднакво: тишина. А коментарът горе казва
    # точно защо това е скъпо.
    arhiv = ot_github("predict_log_arhiv.json")
    if arhiv is NEPITAN:
        nepitani.append("predict_log_arhiv.json — статистиката долу е върху"
                        " ОТРЯЗАН живот и няма как да знам с колко")
        arhiv = None
    if arhiv is None:
        arhiv = chetiv("predict_log_arhiv.json", [])
    if isinstance(arhiv, list) and arhiv:
        log = arhiv + list(log or [])
        print("   (плюс " + str(len(arhiv)) + " архивни записа)")
    else:
        print("   (архив: 0 записа — приключените отиват там след"
              " " + str(ARHIV_DNI) + " дни)")
    st = ot_github("predict_state.json")
    if st is NEPITAN:
        nepitani.append("predict_state.json от GitHub — черната кутия долу е"
                        " локална и може да е от друг рън")
        st = None
    if st is None:
        st = chetiv("predict_state.json", {})
    if not isinstance(st, dict):
        st = {}
    diag = (st.get("diag") or {}).get("sportove") or {}
    koga = (st.get("diag") or {}).get("koga") or "?"

    # 🔴 ЧЕРНАТА КУТИЯ МОЖЕ ДА Е ЗАСТОЯЛА (25.08.2026).
    # `koga` се четеше и се ПЕЧАТАШЕ — и това беше всичко. Никъде не се
    # сравняваше с „сега". Тоест целият преглед по-долу стъпваше върху `diag`,
    # без изобщо да е питал на колко дни е.
    # Доказано на живо с подхвърлен predict_state.json от преди 3 дни и
    # `surovi: 40` за всеки спорт: изходът обвиняваше ФИЛТРИТЕ за седем спорта
    # („има срещи, няма карти"), при положение че предсказателят е мъртъв.
    # Не е зелено, но сочи в грешната посока, а това струва същото.
    state_star_ch = vazrast_ch(koga, now)
    diag_e_star = state_star_ch is not None and state_star_ch > STAR_STATE_CH
    if diag_e_star:
        problemi.append("черната кутия е от преди %.0f ч (последен рън на"
                        " предсказателя: %s) — числата «срещи/празно» долу"
                        " описват ТОГАВА, не сега" % (state_star_ch, koga))
    elif state_star_ch is None and koga != "?":
        nepitani.append("не разбрах датата на последния рън («" + str(koga)[:24]
                        + "») — не знам на колко часа са числата долу")

    if ZATVORENI_NEYASNO:
        problemi.append("НЕ МОГА да прочета кои спортове са затворени"
                        " (predictor.py / маркерът _izkl_raw) — долу всички се"
                        " съдят като отворени")

    redove = []
    # Кой спорт има мачове НАПРЕД. Пълни се само за спортовете, които днес са
    # празни — иначе е излишна заявка. Стойността е „след колко дни".
    napred = {}

    # ---------- 1. ПО СПОРТ ----------
    # Първо: за кои спортове изворът е празен днес? Само тях питаме напред.
    _diag = diag or {}
    _prazni = [b for b in IME
               if b not in ZATVORENI and (_diag.get(b) or {}).get("surovi") == 0]
    if _prazni:
        napred = koga_pak(_prazni, now)

    for b in sorted(IME, key=lambda x: IME[x]):
        if b in ZATVORENI:
            redove.append("%-17s %-46s %s"
                          % (IME[b], "затворен — " + koga_tragva(b), "—"))
            continue
        dnesni = [r for r in log if r.get("bucket") == b
                  and str(r.get("posted") or "")[:10] == dnes]
        # 🔴 12.08.2026. Тук беше ФАЛШИВАТА ТРЕВОГА. Броеше се само по деня на
        # ПУБЛИКУВАНЕ — а картата за днешен мач често излиза ВЧЕРА (хоризонтът
        # е 30 часа). Измерено на живо: тенисът на маса имаше четири карти за
        # днешните си мачове, пуснати вчера в 11:04, и прегледът пишеше „0
        # карти днес, източникът даде 209 срещи — филтрите изядоха всичко".
        # Спорт, който си е свършил работата, се обявяваше за счупен.
        za_dnes = [r for r in log if r.get("bucket") == b
                   and str(r.get("day") or "")[:10] == dnes]
        ots = [r for r in log if r.get("bucket") == b
               and r.get("scored") and r.get("hit") is not None]
        poz = sum(1 for r in ots if r.get("hit"))
        d = diag.get(b) or {}
        surovi = d.get("surovi")
        gr = d.get("gr") or []

        posledna = ""
        for r in log:
            if r.get("bucket") == b:
                d = str(r.get("posted") or r.get("day") or "")[:10]
                if len(d) == 10 and d > posledna:
                    posledna = d

        if dnesni:
            sast = "%d карти днес" % len(dnesni)
            if za_dnes and len(za_dnes) != len(dnesni):
                sast += " (%d за днешните мачове)" % len(za_dnes)
        elif za_dnes:
            sast = ("%d карти за днешните мачове — пуснати предния ден"
                    % len(za_dnes))
        elif b in IZVAN_SEZONA:
            sast = "празно — " + IZVAN_SEZONA[b]
        elif b in RYADKI:
            tavan, zashto = RYADKI[b]
            dni_bez = 999
            if posledna:
                try:
                    dni_bez = (now.date()
                               - datetime.strptime(posledna, "%Y-%m-%d").date()).days
                except ValueError:
                    dni_bez = 999
            sast = "празно — " + zashto
            if dni_bez > tavan:
                sast = "празно от %d дни — това вече е много" % dni_bez
                problemi.append(IME[b] + ": %d дни без нито една карта (таван %d)"
                                % (dni_bez, tavan))
        # 🔴 `napred.get(b)` беше ЛЪЖЛИВО за стойност 0 — тоест дори след
        # поправката горе клонът пак щеше да се прескача точно за деня, в
        # който турнирът почва. Двата дефекта са БЛИЗНАЦИ и се лекуват заедно.
        elif surovi == 0 and napred.get(b) is not None:
            # 🔴 ПАУЗА, НЕ ПОВРЕДА (18.08.2026). Измерено: FIVB дава нула мача
            # за 16, 17 и 18 август, а от 19-и — 5, 5, 12, 12. WTT има 100
            # турнира, активни днес нула, следващият от края на ноември.
            # Тоест източникът работи, а спортът е в пауза между сериите.
            # Прегледът не може да различи двете по мълчанието — затова пита
            # НАПРЕД. Има ли мачове след днес, това е календар, не дефект.
            _d = napred[b]
            sast = ("пауза — турнирът почва днес, разписанието още не е пуснато"
                    if _d == 0 else
                    "пауза — мачове има от утре" if _d == 1
                    else "пауза — следващите мачове са след %d дни" % _d)
        # 🔴 ЗАСТОЯЛАТА КУТИЯ НЕ СЪДИ (25.08.2026). Двата клона долу обвиняват
        # ИЗТОЧНИКА и ФИЛТРИТЕ по числото `surovi`. То идва от последния УСПЕШЕН
        # рън на предсказателя. Умре ли предсказателят, числото замръзва и
        # прегледът почва да сочи в грешната посока — шест реда „филтрите изядоха
        # всичко", докато истината е „никой не е питал от три дни".
        elif diag_e_star:
            sast = "не знам — черната кутия е от преди %.0f ч" % state_star_ch
        elif surovi == 0:
            # 🔴 12.08.2026. Тук пак крещеше напразно. „Нула срещи" се чете от
            # ПОСЛЕДНИЯ рън — а последният рън на деня е в 22:00, когато
            # футболът наистина няма какво да предложи за оставащите два часа.
            # Спорт, който вече си е свършил работата днес, не е счупен.
            # Гърми само ако е мълчал И вчера: тогава дупката е реална.
            vchera = [r for r in log if r.get("bucket") == b
                      and str(r.get("posted") or "")[:10] == vchera_den]
            if dnesni or za_dnes or vchera:
                sast = ("източникът е празен в последния рън, но спортът"
                        " е давал карти")
            else:
                sast = "празно — източникът върна нула срещи"
                problemi.append(IME[b] + ": източникът е празен, а не е извън"
                                " сезон, и няма карти нито днес, нито вчера")
        elif surovi:
            sast = "0 карти днес, но източникът даде %s срещи" % surovi
            problemi.append(IME[b] + ": има срещи, няма карти — филтрите изядоха"
                            " всичко (и нито една не е пусната предния ден)")
        else:
            # 🔴 25.08.2026: този клон беше НЯМА. „Няма данни за последния рън"
            # се печаташе и не влизаше никъде — а той значи, че черната кутия
            # НЯМА запис за този спорт, тоест прегледът НЕ ЗНАЕ. Не знам ≠ наред.
            sast = "няма данни за последния рън — НЕ мога да преценя"
            nepitani.append(IME[b] + ": черната кутия няма запис за него")

        procent = ("%d от %d · %d%%" % (poz, len(ots), round(100.0 * poz / len(ots)))
                   if ots else "още нищо отсъдено")
        redove.append("%-17s %-46s %s" % (IME[b], sast, procent))
        for g in gr[:1]:
            problemi.append(IME[b] + ": " + str(g)[:70])

    # ---------- 2. CI, ПО WORKFLOW ----------
    # 🔴 25.08.2026. Дотук тук стоеше ЕДНО питане към общия списък и три реда
    # аритметика, чийто резултат (`cherveni`) НИКОГА не влизаше в `problemi` —
    # смяташе се, печаташе се и толкоз. Тоест дори прозорецът да беше идеален,
    # червен рън пак не можеше да оцвети прегледа. А при `--kratko` дори не се
    # печаташе, защото целият блок е зад `if not kratko`.
    ci = obhod(sega=now.astimezone(timezone.utc))
    ci_po = {d["ime"]: d for d in ci}
    for d in ci:
        if d["sast"] == "cherveno":
            problemi.append(d["tekst"])
        elif d["sast"] == "mulchi":
            problemi.append(d["tekst"])
        elif d["sast"] == "nepitan":
            nepitani.append(d["tekst"])

    # ---------- 3. ВИСЯЩИ ----------
    vis = [r for r in log if not r.get("scored")]
    star = [r for r in vis if str(r.get("day") or "")[:10] < dnes]
    bez = [r for r in log if r.get("scored") and r.get("hit") is None]
    # 🔴 УСПОКОЕНИЕ, КОЕТО НЕ Е ПРОВЕРЕНО, Е ЛЪЖА (25.08.2026).
    # Дотук тук пишеше „изчистват се на следващото пускане на оценителя, 13:30 и
    # 22:30 БГ" — обещание за механизъм, който никой не беше питал жив ли е.
    # Живият zdrave.txt от 24.08 20:34 носи точно този ред с 47 прогнози, в час,
    # в който оценителят вече беше гръмнал два пъти. Числото само расте, а
    # изречението обещава разписание.
    # Второ, по-тихо: `posl_scorer` помнеше само КОГА е ТРЪГНАЛ рънът, не дали
    # е УСПЯЛ — тоест гърмящ оценител щеше да се цитира като успокоение.
    # Сега изречението се гради от ПРИСЪДАТА на score.yml, и то от ПОСЛЕДНИЯ
    # УСПЕХ, не от последния старт.
    kraj = kraj_za_visyashti(ci_po.get("score.yml"))
    if star:
        problemi.append("%d прогнози от МИНАЛИ дни още чакат резултат%s" % (len(star), kraj))
    if bez:
        problemi.append("%d прогнози са затворени БЕЗ присъда%s" % (len(bez), kraj))

    # ---------- ОТЧЕТ ----------
    if not kratko:
        print("")
        print("🩺 ЗДРАВЕН ПРЕГЛЕД · " + now.strftime("%d.%m.%Y %H:%M"))
        print("   последен рън на предсказателя: " + str(koga))
        print("")
        print("%-17s %-46s %s" % ("СПОРТ", "СЪСТОЯНИЕ ДНЕС", "УСПЕВАЕМОСТ"))
        print("-" * 92)
        for r in redove:
            print(r)
        print("")
        ots_vs = [r for r in log if r.get("scored") and r.get("hit") is not None]
        poz_vs = sum(1 for r in ots_vs if r.get("hit"))
        print("ОБЩО: %d записа · %d отсъдени · %d познати%s"
              % (len(log), len(ots_vs), poz_vs,
                 (" · %d%%" % round(100.0 * poz_vs / len(ots_vs))) if ots_vs else ""))
        print("      висящи: %d (от минали дни: %d) · без присъда: %d"
              % (len(vis), len(star), len(bez)))
        print("")
        # 🔴 CI РАЗДЕЛЪТ ВЕЧЕ НЕ МОЖЕ ДА ИЗЧЕЗНЕ (25.08.2026).
        # Дотук той стоеше зад `if rr:` — при отказ на GitHub `runove()` връщаше
        # [] и ЦЕЛИЯТ раздел се изпаряваше без нито една дума. Доклад без ред за
        # CI се чете като доклад без проблеми в CI. Сега всеки от VAZHNI има
        # СВОЙ ред винаги, включително „не можах да питам".
        znak = {"naredno": "✅", "cherveno": "🔴", "mulchi": "🟠", "nepitan": "❔"}
        print("CI ПО WORKFLOW (питани поотделно, не през общия списък):")
        for d in ci:
            prag = ("праг: не знам" if d["dopusk_ch"] is None
                    else "праг %.0f ч" % d["dopusk_ch"])
            print("   %s %-13s %-56s %s"
                  % (znak.get(d["sast"], "?"), d["ime"], d["kak"][:56], prag))
        print("")

    # ---------- 5. СРЕЩУ ПАЗАРА ----------
    # ---------- КРИВИТЕ ЛИГИ И НЕЗАЛОЖИМИТЕ (25.08.2026) ----------
    _krivi = krivi_ligi(log)
    _nadu = [t for t in _krivi if t[4] < 0]
    if not kratko:
        print("\U0001f3af ЛИГИТЕ ИЗВЪН ШУМА · средното по спорт ги крие")
        if not _krivi:
            print("   няма нито една лига с %d+ отсъдени извън собствения си шум"
                  % LIGA_MIN)
        for ime, n, ob, sb, d in _krivi[:8]:
            print("   %-44s n=%-4d %4.0f%% → %4.0f%%  %+5.1f т"
                  % (ime[:44], n, 100.0 * ob, 100.0 * sb, 100.0 * d))
        print("")
    for ime, n, ob, sb, d in _nadu[:3]:
        problemi.append("%s: обявява %.0f%%, сбъдва %.0f%% на %d мача (%+.0f т,"
                        " извън шума)" % (ime[:40], 100.0 * ob, 100.0 * sb, n,
                                          100.0 * d))

    _yu, _vs, _spis = nezalozhimi(log)
    _dyal = (100.0 * _yu / _vs) if _vs else 0.0
    if not kratko:
        print("\U0001f6ab НЕЗАЛОЖИМИ · юношески турнири, за които няма пазар")
        print("   %d от %d карти = %.0f%% (праг %d%%)"
              % (_yu, _vs, _dyal, YUNOSHESKI_PRAG))
        for ime, n in _spis[:5]:
            print("   %-52s %d" % (ime[:52], n))
        print("")
    if _dyal > YUNOSHESKI_PRAG:
        problemi.append("%.0f%% от картите са юношески турнири (%d от %d) —"
                        " за тях НЯМА пазар при никой букмейкър"
                        % (_dyal, _yu, _vs))

    if not kratko:
        print("\U0001f4b0 ПАРИТЕ · струва ли си (само тук, не в стаята)")
        for _r in parite(log):
            print(_r)
        print("")

    pz_redove, n_pz = sreshtu_pazara(log)
    s_cena = sum(1 for r in log if r.get("pazar_cena"))
    if not kratko:
        print("📊 СРЕЩУ ПАЗАРА · когато се разминаваме, кой е прав?")
        if not pz_redove:
            print("   %d прогнози с пазарна цена · %d вече отсъдени"
                  % (s_cena, n_pz))
            print("   трябват поне %d отсъдени с цена, за да има смисъл"
                  % PAZAR_MIN)
        else:
            for r in pz_redove:
                print(r)
        print("")

    # ---------- 4. КАЛИБРАЦИЯ ----------
    kal, n_kal = kalibraciya(log)
    if not kratko:
        print("📐 КАЛИБРАЦИЯ · като каже X%, сбъдва ли се X%?")
        if not kal:
            print("   още малко данни: %d отсъдени, трябват поне %d"
                  % (n_kal, KALIB_MIN))
        else:
            print("   %-12s %6s %9s %10s %8s" % ("обявено", "брой", "обещава",
                                                 "сбъдва", "разлика"))
            for etiket, br, obe, sbd in kal:
                print("   %-12s %6d %8.1f%% %9.1f%% %+7.1f"
                      % (etiket, br, obe, sbd, sbd - obe))
        print("")

    # Спорт, който НАДЦЕНЯВА себе си, е по-опасен от такъв, който се подценява:
    # човекът плаща вниманието си по обявеното число. Затова тук гърми само
    # отрицателната посока, и то при достатъчно данни.
    for b in sorted(IME):
        if b in ZATVORENI:
            continue
        k, n_b = kalibraciya(log, b)
        if not k:
            continue
        _, br, obe, sbd = k[-1]
        if sbd - obe < -KALIB_PRAG:
            problemi.append("%s: обещава %.0f%%, сбъдва %.0f%% (%d отсъдени)"
                            " — надценява се" % (IME[b], obe, sbd, br))

    # ---------- ПРИСЪДАТА ----------
    # 🔴 ПРИСЪДАТА ИЗРЕЖДА КАКВО Е ПИТАЛА, НЕ КАКВО Е ПРОВЕРИЛА (25.08.2026).
    # Дотук последният ред беше буквално: „✅ ВСИЧКО Е ЧИСТО — няма празен спорт
    # без причина, няма висящи, НЯМА ЧЕРВЕНИ РЪНOВЕ." Изречението твърдеше точно
    # това, което кодът никога не беше проверявал: `cherveni` се смяташе, но не
    # влизаше в `problemi` по нито един път. Доказано с хамут: два подхвърлени
    # червени scorer рънa → прегледът пак завършваше с „ВСИЧКО Е ЧИСТО".
    # Сега зеленото носи БРОЯ на проверените, а „не можах" има собствен блок.
    proveren_ci = sum(1 for d in ci if d["sast"] != "nepitan")
    if nepitani:
        print("❔ НЕ МОЖАХ ДА ПРОВЕРЯ (%d) — това НЕ Е «чисто»:" % len(nepitani))
        for n in nepitani:
            print("   • " + n)
        print("")
    if problemi:
        print("🔴 ЗА ГЛЕДАНЕ (%d):" % len(problemi))
        for p in problemi:
            print("   • " + p)
        return 1
    if nepitani:
        # Слепотата НЕ Е зелено. Нула видимост не е „непроверено" — тя е провал
        # на самия преглед и излиза със същия код, с който излиза и находка.
        print("⚠️  НЯМА НАМЕРЕНИ ПРОБЛЕМИ, НО %d неща останаха НЕПРОВЕРЕНИ —"
              " не мога да кажа «чисто»." % len(nepitani))
        return 1
    print("✅ ЧИСТО ПО ТОВА, КОЕТО ПИТАХ: %d от %d workflow-а в CI · %d спорта ·"
          " %d висящи от минали дни · %d без присъда."
          % (proveren_ci, len(VAZHNI), len(IME) - len(ZATVORENI), len(star), len(bez)))
    if ZATVORENI:
        print("   (затворени до сезона: "
              + ", ".join(IME.get(x, x) for x in sorted(ZATVORENI)) + ")")
    return 0


# ═══════════════════════════════════════════ 🧪 САМОПРОВЕРКА
#
# 🔴 25.08.2026. Дотук файлът, чиято ЕДИНСТВЕНА работа е да отсъжда здравето,
# нямаше НИТО ЕДНА самопроверка. Единственият външен пазач бяха две текстови
# игли в predictor.py:8598 — 3 реда от 488.
# Тестовете тук са ПОВЕДЕНЧЕСКИ: подхвърлят се рънове и yml-текст, гледа се
# ИЗХОДЪТ. Текстова игла, чиято копа сено е съседният коментар, минава и на
# счупен файл — това ни ухапа четири пъти в този проект.
def _run(zakl, chasa_nazad, sega, status="completed"):
    t = sega - timedelta(hours=chasa_nazad)
    return {"name": "x", "status": status, "conclusion": zakl,
            "run_started_at": t.strftime("%Y-%m-%dT%H:%M:%SZ")}


def _suh_pregled(chetec, argv=None, log=None, st=None):
    """Пуска ЦЕЛИЯ main() БЕЗ мрежа и БЕЗ дискови файлове. → (изход, код).

    Смисълът е един: дефектът, който уби 33 часа, живееше между функциите —
    червеното се смяташе вярно и после не стигаше до присъдата. Проверка на
    парче не би го хванала. Затова тук се пуска целият преглед.
    """
    now = datetime.now(SOFIA)
    dnes = now.strftime("%Y-%m-%d")
    otvoreni = [b for b in IME if b not in ZATVORENI]
    if log is None:
        log = [{"bucket": b, "posted": dnes + " 10:00", "day": dnes,
                "scored": False} for b in otvoreni]
    if st is None:
        st = {"diag": {"koga": now.strftime("%Y-%m-%d %H:%M"),
                       "sportove": {b: {"surovi": 5, "gr": []} for b in otvoreni}}}
    pazi = {k: globals()[k] for k in ("ot_github", "chetiv", "runove_na", "koga_pak")}
    star_argv, star_out = sys.argv, sys.stdout
    buf = io.StringIO()
    try:
        globals()["ot_github"] = lambda p: (log if p == "predict_log.json" else
                                            st if p == "predict_state.json" else None)
        globals()["chetiv"] = lambda p, po_podrazbirane: po_podrazbirane
        globals()["runove_na"] = lambda ime, broi=10: chetec(ime)
        globals()["koga_pak"] = lambda *a, **k: {}
        sys.argv = list(argv or ["zdrave.py"])
        sys.stdout = buf
        kod = main()
    finally:
        sys.stdout, sys.argv = star_out, star_argv
        globals().update(pazi)
    return buf.getvalue(), kod


def _selftest_koga(check):
    """Проверките за датата на отваряне."""
    _t = {"hockey": ("2026-09-29", True), "amfootball": ("2026-09-10", True),
          "basketball": ("2026-10-20", False)}
    check("сигурната дата се изрича точно",
          koga_tragva("hockey", _t) == "тръгва на 29.09")
    check("и втората също", koga_tragva("amfootball", _t) == "тръгва на 10.09")
    # 🔴 НЕСИГУРНОТО СЕ КАЗВА КАТО НЕСИГУРНО. Прегледът няма право да звучи
    # по-уверено от източника си.
    check("несигурната се обявява за несигурна",
          "не е сигурно" in koga_tragva("basketball", _t))
    check("непознатият кош не измисля дата",
          koga_tragva("кърлинг", _t) == "до старта на сезона")
    check("празният кош не гърми", koga_tragva("", _t) == "до старта на сезона")
    check("None не гърми", koga_tragva(None, _t) == "до старта на сезона")

    # 🔴 НАЙ-РАННАТА ПОБЕЖДАВА. Един кош има няколко първенства (НХЛ и АХЛ са
    # хокей) — спортът тръгва с ПЪРВОТО, не с последното.
    _tabl = _ot_sezon()
    check("таблицата се чете от sezon", isinstance(_tabl, dict))
    if _tabl.get("hockey"):
        check("хокеят вече НЕ е „около 15.09\"",
              "15.09" not in koga_tragva("hockey", _tabl))
        check("хокеят носи измерена дата",
              koga_tragva("hockey", _tabl).startswith("тръгва на"))
        # 🔴 И Е НХЛ, НЕ NCAA ПРИ ЖЕНИТЕ. Втората ми версия сгреши точно тук.
        check("хокеят е НХЛ (29.09), не NCAA жени (18.09)",
              "29.09" in koga_tragva("hockey", _tabl))
    if _tabl.get("amfootball"):
        # Тук обратно: NCAA Е важен и отваря пръв.
        check("амер. футбол тръгва с NCAA (29.08)",
              "29.08" in koga_tragva("amfootball", _tabl))

    # Старото име остава, но празно — за да гръмне всеки, който още го чете.
    check("старата закована таблица е празна", KOGA_TRAGVA == {})


def _selftest_ligi(check):
    """Проверките за кривите лиги и незаложимите."""
    def _r(liga, p, hit, bucket="volleyball"):
        return {"league": liga, "p": p, "hit": hit, "bucket": bucket,
                "scored": True}

    # Лига с 20 мача, обявява 80%, сбъдва 30% — далеч извън всякакъв шум.
    _losha = [_r("Лоша лига", 0.80, i < 6) for i in range(20)]
    # 🔴 ИНДЕКСИРАНЕ БЕЗ ПРОВЕРКА СЪБАРЯ ЦЕЛИЯ ПАКЕТ. Първата ми версия
    # пишеше `_r1[0][4] < 0` направо — и при мутация „нищо не е криво"
    # получих IndexError вместо „счупено", тоест изгубих и присъдата, и
    # всички проверки надолу. Трети път днес същият урок; тук се затваря.
    _r1 = krivi_ligi(_losha, 12)
    check("надуващата лига се хваща",
          len(_r1) == 1 and _r1[0][0] == "Лоша лига")
    check("разликата е отрицателна", bool(_r1) and _r1[0][4] < 0)
    check("броят е верен", bool(_r1) and _r1[0][1] == 20)

    # Лига, която сбъдва точно каквото обявява — не бива да се хваща.
    _dobra = [_r("Добра лига", 0.60, i < 12) for i in range(20)]
    check("честната лига НЕ се хваща", krivi_ligi(_dobra, 12) == [])

    # 🔴 ДВА РАЗЛИЧНИ ПАЗАЧА, И ТОВА ЛИЧИ ТУК.
    # Първата ми версия на този тест беше сгрешена: сложих 8 мача с 25 точки
    # разлика и очаквах да се хванат при праг 5. Не се хванаха — и с право:
    # при 8 мача шумът е ±30 точки, тоест 25 са ШУМ. Прагът за БРОЯ и прагът
    # за ШУМА са различни неща и трябва да минат и двата.
    _malka = [_r("Малка лига", 0.75, False) for i in range(8)]
    check("под прага за брой не се произнасяме", krivi_ligi(_malka, 12) == [])
    check("над прага за брой, и извън шума — хваща се",
          krivi_ligi(_malka, 5) != [])
    # А същият брой, но ВЪТРЕ в шума, пак не се произнася.
    _shumna = [_r("Шумна лига", 0.75, i < 4) for i in range(8)]
    check("вътре в шума не се произнася дори над прага за брой",
          krivi_ligi(_shumna, 5) == [])

    # Подценяващата също се хваща, но идва ПОСЛЕ надуващата.
    _pod = [_r("Подценяваща", 0.40, i < 18) for i in range(20)]
    _r2 = krivi_ligi(_losha + _pod, 12)
    check("хващат се и двете посоки", len(_r2) == 2)
    check("надуващата е ПЪРВА",
          len(_r2) == 2 and _r2[0][4] < 0 and _r2[1][4] > 0)

    check("празният дневник не гърми", krivi_ligi([], 12) == [])
    check("None не гърми", krivi_ligi(None, 12) == [])
    check("неотсъдените не влизат",
          krivi_ligi([{"league": "х", "p": 0.9, "hit": None}] * 30, 12) == [])
    check("шумът пада с растежа на извадката", _shum(0.5, 400) < _shum(0.5, 25))

    # ---------------------------------------------- незаложимите
    check("U17 се разпознава", yunosheski_li("FIVB Girls' U17 World Championship"))
    check("Boys се разпознава", yunosheski_li("NORCECA U17 Boys Pan American Cup"))
    check("junior се разпознава", yunosheski_li("ITF Junior Cup"))
    # 🔴 ГЛАВНАТА: мъжкият турнир НЕ Е юношески. Прекалено широко ловене би
    # обявило половината продукт за незаложим и щеше да се научи да се пренебрегва.
    check("мъжкият турнир НЕ е юношески",
          not yunosheski_li("ECVA Senior Men's Volleyball Championship"))
    check("Champions НЕ е юношески", not yunosheski_li("WTT Champions Yokohama"))
    check("празното НЕ е юношеско", not yunosheski_li("") and not yunosheski_li(None))

    _sm = ([_r("FIVB Girls' U17", 0.7, True) for _ in range(6)]
           + [_r("Мъжка лига", 0.7, True) for _ in range(4)])
    _y, _v, _s = nezalozhimi(_sm)
    check("юношеските се броят", _y == 6 and _v == 10)
    check("и се изброяват по име", bool(_s) and _s[0][0] == "FIVB Girls' U17")
    check("без юношески дава нула",
          nezalozhimi([_r("Мъжка лига", 0.7, True)])[0] == 0)
    check("празното не гърми", nezalozhimi([]) == (0, 0, []))


def _selftest_parite(check):
    """Проверките за парите. Отделно, за да се четат."""
    # 🔴 ПОВЕДЕНЧЕСКИ, НЕ ТЕКСТОВИ. Подхвърлят се редове и се гледа изходът.
    def _r(hit, cena, clv=None, v=2):
        d = {"hit": hit, "pazar_cena": cena, "pazar_v": v, "scored": True}
        if clv is not None:
            d["pazar_clv"] = clv
        return d

    check("малка извадка казва колко липсват",
          any("трябват поне" in x for x in parite([_r(True, 2.0)] * 3)))

    _rav = [_r(True, 2.0) for _ in range(30)] + [_r(False, 2.0) for _ in range(30)]
    _iz = parite(_rav)
    check("равната монета дава ред за доходност",
          any("доходност при равен залог" in x for x in _iz))
    # 🔴 ГЛАВНАТА: числото НЕ БИВА да излиза без интервала си.
    check("интервалът задължително придружава числото",
          any("интервалът е" in x for x in _iz))
    check("присъдата се произнася", any("присъда" in x for x in _iz))
    check("при нула вътре не се твърди нищо",
          any("нулата е ВЪТРЕ" in x for x in _iz))
    check("казва колко още трябват", any("за ръб от" in x for x in _iz))

    _pech = [_r(True, 3.0) for _ in range(50)]
    check("ясната печалба се нарича печалба",
          any("ПЕЧЕЛИ" in x for x in parite(_pech)))
    _gub = [_r(False, 2.0) for _ in range(50)]
    check("ясната загуба се нарича загуба",
          any("ГУБИ" in x for x in parite(_gub)))

    check("интервалът на две еднакви е нула",
          _interval([1.0, 1.0])[1] == _interval([1.0, 1.0])[2])
    check("едно число няма интервал", _interval([1.0]) == (0.0, 0.0, 0.0))
    check("празното няма интервал", _interval([]) == (0.0, 0.0, 0.0))
    check("по-разсеяното иска повече залози",
          kolko_oshte([1.0, -1.0] * 20, 0.05) > kolko_oshte([0.1, -0.1] * 20, 0.05))
    check("по-малкият ръб иска повече залози",
          kolko_oshte([1.0, -1.0] * 20, 0.03) > kolko_oshte([1.0, -1.0] * 20, 0.10))
    check("без разсейване не гърми", kolko_oshte([1.0] * 10, 0.05) == 0)
    check("боклук не гърми", kolko_oshte([], 0.05) == 0 and kolko_oshte(None) == 0)


def selftest():
    dobri = []
    losho = []

    def check(ime, uslovie):
        (dobri if uslovie else losho).append(ime)

    sega = datetime(2026, 8, 25, 6, 0, tzinfo=timezone.utc)

    # ── 1. СЪРЦЕТО: „не можах да питам" НЕ Е „питах и няма" ──────────────
    d = sadi_workflow("score.yml", "оценителят", NEPITAN, 900, sega)
    _selftest_koga(check)
    _selftest_ligi(check)
    _selftest_parite(check)
    check("отказът на GitHub дава nepitan, не naredno", d["sast"] == "nepitan")
    check("отказът се КАЗВА с думи", "НЕ МОЖАХ" in d["tekst"])
    d = sadi_workflow("score.yml", "оценителят", [], 900, sega)
    check("празен отговор НЕ е «наред»", d["sast"] == "nepitan")

    # ── 2. ТРИТЕ ПОРЕДНИ ПРОВАЛА (истинският случай от 25.08) ────────────
    rr = [_run("failure", 10, sega), _run("failure", 19, sega),
          _run("failure", 34, sega), _run("success", 43, sega),
          _run("success", 52, sega)]
    d = sadi_workflow("score.yml", "оценителят", rr, 900 + GRATIS_MIN, sega)
    check("три поредни провала се броят като три", d["poredni"] == 3)
    check("три поредни провала дават ЧЕРВЕНО", d["sast"] == "cherveno")
    check("казва откога няма успех", d["ot_uspeh_ch"] is not None
          and 42.9 < d["ot_uspeh_ch"] < 43.1)

    # ── 3. МЪЛЧАНИЕТО е отделно от провала ───────────────────────────────
    d = sadi_workflow("score.yml", "оценителят", [_run("success", 40, sega)],
                      900 + GRATIS_MIN, sega)
    check("успех отвъд прага = мълчи", d["sast"] == "mulchi")
    d = sadi_workflow("score.yml", "оценителят", [_run("success", 3, sega)],
                      900 + GRATIS_MIN, sega)
    check("пресен успех = наред", d["sast"] == "naredno")

    # ── 4. НЕДОВЪРШЕН РЪН не е нито успех, нито провал ───────────────────
    d = sadi_workflow("m.yml", "мачове",
                      [_run(None, 0.1, sega, status="in_progress"),
                       _run("success", 2, sega)], 24 * 60 + GRATIS_MIN, sega)
    check("тичащ рън не се брои за провал", d["poredni"] == 0
          and d["sast"] == "naredno")
    d = sadi_workflow("m.yml", "мачове", [_run("cancelled", 1, sega)],
                      24 * 60 + GRATIS_MIN, sega)
    check("cancelled не е успех, но и не е провал", d["sast"] == "nepitan"
          and d["poredni"] == 0)

    # ── 5. ПРАГЪТ идва от собствения cron, не е забит ────────────────────
    check("score: 10:30 и 19:30 → най-дългата пауза е 15 ч",
          period_min(["30 10 * * *", "30 19 * * *"]) == 15 * 60)
    check("router: */10 → 10 минути", period_min(["*/10 * * * *"]) == 10)
    check("daily: един крон → 24 часа", period_min(["0 17 * * *"]) == 24 * 60)
    check("news: 05/11/17 → 12 часа",
          period_min(["0 5 * * *", "0 11 * * *", "0 17 * * *"]) == 12 * 60)
    check("support: 7,22,37,52 всеки час → 15 минути",
          period_min(["7,22,37,52 * * * *"]) == 15)
    check("неразбираем крон НЕ дава число", period_min(["каквото и да е"]) is None)
    check("седмичен крон НЕ се свежда до денонощие",
          period_min(["0 5 * * 1"]) is None)
    check("празен списък НЕ дава нула", period_min([]) is None)
    check("гратисът се добавя над периода",
          dopusk_min("x.yml", lambda i: "  - cron: '30 10 * * *'\n"
                                        "  - cron: '30 19 * * *'\n")
          == 15 * 60 + GRATIS_MIN)
    check("закоментиран cron НЕ се брои",
          cron_ot_yml("# - cron: '0 1 * * *'\n  - cron: '0 2 * * *'")
          == ["0 2 * * *"])
    check("липсващ yml → няма праг", dopusk_min("nyama.yml", lambda i: None) is None)

    # ── 6. ЖИВИТЕ .yml ФАЙЛОВЕ се четат наистина ─────────────────────────
    # Ако някой преименува workflow или махне крона, това пада ТУК, а не в
    # деня, в който прегледът е трябвало да гръмне.
    bez_prag = [ime for ime, _ in VAZHNI if dopusk_min(ime) is None]
    check("всеки от VAZHNI има разбираем cron на диска (%s)" % (bez_prag or "—"),
          not bez_prag)
    check("оценителят е в списъка на важните",
          "score.yml" in [i for i, _ in VAZHNI])
    check("прагът на score.yml е измерен, не забит",
          dopusk_min("score.yml") == 15 * 60 + GRATIS_MIN)

    # ── 7. ОБХОДЪТ: отказ на едно място не заличава останалите ───────────
    def _chetec(ime):
        if ime == "score.yml":
            return [_run("failure", 10, sega), _run("failure", 19, sega),
                    _run("failure", 34, sega), _run("success", 43, sega)]
        if ime == "news.yml":
            return NEPITAN
        return [_run("success", 0.5, sega)]
    o = obhod(chetec=_chetec, sega=sega)
    check("обходът връща по един ред за всеки важен", len(o) == len(VAZHNI))
    po = {x["ime"]: x for x in o}
    check("червеният се вижда", po["score.yml"]["sast"] == "cherveno")
    check("непитаният се вижда ОТДЕЛНО", po["news.yml"]["sast"] == "nepitan")
    check("здравите не се заразяват", po["router.yml"]["sast"] == "naredno")

    # ── 8. УСПОКОЕНИЕТО се дава само върху проверен механизъм ────────────
    t = kraj_za_visyashti(po["score.yml"])
    check("мъртъв оценител НЕ обещава изчистване",
          "изчистват се" not in t and "НЯМА да се изчистят" in t)
    t2 = kraj_za_visyashti(sadi_workflow("score.yml", "о",
                                         [_run("success", 3, sega)],
                                         15 * 60 + GRATIS_MIN, sega))
    check("жив оценител ОБЕЩАВА изчистване", "изчистват се" in t2)
    check("живото обещание цитира УСПЕХ, не старт", "УСПЕШЕН" in t2)
    t3 = kraj_za_visyashti(sadi_workflow("score.yml", "о", NEPITAN, 900, sega))
    check("непитан оценител НЕ обещава нищо",
          "изчистват се" not in t3 and "НЕ можах" in t3)

    # ── 9. ВЪЗРАСТТА на черната кутия се СМЯТА, не само се печата ────────
    sof = datetime(2026, 8, 25, 8, 0, tzinfo=SOFIA)
    v = vazrast_ch("2026-08-22 08:01", sof)
    check("три дни застой се мерят като ~72 ч", v is not None and 71.9 < v < 72.1)
    check("пресен печат е малко часове",
          0 <= (vazrast_ch("2026-08-25 07:30", sof) or -1) < 1)
    check("неразбираема дата НЕ е нула часа", vazrast_ch("?", sof) is None)
    check("празно НЕ е нула часа", vazrast_ch("", sof) is None)

    # ── 10. ПИТА СЕ ПО WORKFLOW, НЕ ПРЕЗ ОБЩИЯ СПИСЪК ────────────────────
    # 🔴 Тази проверка НЕ търси текст. Текстова игла („actions/runs го няма")
    # би паднала върху ЧИСТ файл, защото низът стои в собствения ми коментар
    # горе — точно копата сено, в която живее иглата. Затова се ЛОВИ АДРЕСЪТ,
    # който функцията наистина иска от GitHub.
    pitani = []
    _star_api = globals()["_api"]
    try:
        globals()["_api"] = lambda p, timeout=30: (pitani.append(p) or
                                                   {"workflow_runs": []})
        runove_na("score.yml", 10)
    finally:
        globals()["_api"] = _star_api
    check("адресът е на КОНКРЕТНИЯ workflow",
          len(pitani) == 1 and pitani[0].startswith("actions/workflows/score.yml/runs"))
    check("общият списък actions/runs НЕ се пита",
          not any(p.startswith("actions/runs") for p in pitani))

    # ── 11. ТИХИТЕ ВРЪЩАНИЯ, доказани чрез ПОВЕДЕНИЕ ─────────────────────
    _star = globals().get("__file__")
    try:
        globals()["__file__"] = os.path.join(os.path.dirname(os.path.abspath(_star)),
                                             "nyama_takuv_predictor_dir", "z.py")
        z = zatvoreni()
    finally:
        globals()["__file__"] = _star
    check("нечетим predictor НЕ ражда закованото {hockey, amfootball}",
          z is NEPITAN)
    check("сентинелът не е празно множество", z is not set() and z != set())
    check("NEPITAN не е празен списък", NEPITAN != [] and NEPITAN is not None)
    check("NEPITAN не е фалшив по булев тест", bool(NEPITAN))

    # ── 12. ЦЕЛИЯТ ПРЕГЛЕД: червен рън ОЦВЕТЯВА присъдата ────────────────
    # Това е дефектът, който уби 33 часа: `cherveni` се смяташе, печаташе се и
    # НИКОГА не влизаше в problemi. Тук се пуска ЦЕЛИЯТ main() без мрежа.
    # Часовете са спрямо ИСТИНСКОТО сега, защото main() гледа истинския
    # часовник — инак тестът щеше да мине сутрин и да падне вечер.
    r_sega = datetime.now(timezone.utc)

    def _chetec_r(ime):
        if ime == "score.yml":
            return [_run("failure", 10, r_sega), _run("failure", 19, r_sega),
                    _run("failure", 34, r_sega), _run("success", 43, r_sega)]
        return [_run("success", 0.05, r_sega)]

    izhod, kod = _suh_pregled(_chetec_r)
    check("червеният оценител вкарва ред в ЗА ГЛЕДАНЕ",
          "ЗА ГЛЕДАНЕ" in izhod and "score.yml" in izhod)
    check("червеният оценител дава ИЗХОДЕН КОД 1", kod == 1)
    check("при червено НЕ се печата «ЧИСТО»", "ЧИСТО" not in izhod)
    check("CI разделът се вижда в отчета", "CI ПО WORKFLOW" in izhod)

    izhod2, kod2 = _suh_pregled(lambda i: [_run("success", 0.05, r_sega)])
    check("всичко зелено дава изходен код 0", kod2 == 0)
    check("зеленото БРОИ какво е питало",
          "ЧИСТО ПО ТОВА, КОЕТО ПИТАХ" in izhod2
          and ("%d от %d" % (len(VAZHNI), len(VAZHNI))) in izhod2)

    izhod3, kod3 = _suh_pregled(lambda i: NEPITAN)
    check("нула видимост НЕ е зелено", kod3 == 1)
    check("нула видимост се КАЗВА", "НЕ МОЖАХ ДА ПРОВЕРЯ" in izhod3)
    check("нула видимост НЕ печата «ЧИСТО»", "ЧИСТО" not in izhod3)

    # ── 13. --kratko вече не крие червеното ─────────────────────────────
    izhod4, kod4 = _suh_pregled(_chetec_r, argv=["zdrave.py", "--kratko"])
    check("--kratko пак показва червения оценител",
          kod4 == 1 and "score.yml" in izhod4)

    # ── 14. ЗАСТОЯЛАТА КУТИЯ НЕ СОЧИ В ГРЕШНАТА ПОСОКА ──────────────────
    # Стар predict_state.json дава ЗДРАВИ числа (`surovi: 40`) от последния
    # успешен рън. „Стар surovi + нула нови карти" изкарваше шест реда
    # „филтрите изядоха всичко" — и собственикът тръгваше да търси прага,
    # докато предсказателят беше мъртъв от три дни.
    _star_den = (datetime.now(SOFIA) - timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    _otv = [b for b in IME if b not in ZATVORENI]
    izhod5, kod5 = _suh_pregled(
        lambda i: [_run("success", 0.05, r_sega)],
        log=[],
        st={"diag": {"koga": _star_den,
                     "sportove": {b: {"surovi": 40, "gr": []} for b in _otv}}})
    check("застоялата кутия се КАЗВА", "черната кутия е от преди" in izhod5)
    check("застоялата кутия НЕ обвинява филтрите",
          "филтрите изядоха" not in izhod5)
    check("застоялата кутия дава изходен код 1", kod5 == 1)
    # И обратната посока: пресен печат ПАК обвинява филтрите, когато трябва.
    izhod6, _ = _suh_pregled(
        lambda i: [_run("success", 0.05, r_sega)],
        log=[],
        st={"diag": {"koga": datetime.now(SOFIA).strftime("%Y-%m-%d %H:%M"),
                     "sportove": {b: {"surovi": 40, "gr": []} for b in _otv}}})
    check("пресният печат ПАК обвинява филтрите (проверка и в двете посоки)",
          "филтрите изядоха" in izhod6)

    print("🧪 САМОПРОВЕРКА НА ЗДРАВНИЯ ПРЕГЛЕД: %d наред, %d счупени"
          % (len(dobri), len(losho)))
    for x in losho:
        print("   ❌ " + x)
    return 0 if not losho else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv or "selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
