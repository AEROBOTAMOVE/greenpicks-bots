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
   измерено върху 55 пускания — медиана 65 минути, 34 от 55 над час.
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
)


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


def dopusk_min(ime, chetec=None):
    """Колко минути мълчание са ДОПУСТИМИ за този workflow. None = не знам.

    Не знам ≠ наред. Извикващият е длъжен да го каже на глас.
    """
    chetec = chetec or _lokalen_yml
    t = chetec(ime)
    if t is None:
        return None
    p = period_min(cron_ot_yml(t))
    if p is None:
        return None
    return p + GRATIS_MIN


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
        d = dopusk_min(ime, chetec)
        sast, red = sadi(ime, opis, rr, d, sega)
        {"cherveno": cherveni, "mulchi": mulchat,
         "neyasno": neyasni, "naredno": naredni}[sast].append(ime + " — " + red)
    return cherveni, mulchat, neyasni, naredni


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

    sast = cheti_sastoyanie()
    # Слепотата е състояние, не липса на състояние: ако три пъти подред не сме
    # могли да питаме, това само по себе си е новина.
    slepi = int(sast.get("slepi_podred") or 0)
    slepi = slepi + 1 if (neyasni and not cherveni and not mulchat) else 0
    sast["slepi_podred"] = slepi

    speshni = list(cherveni) + list(mulchat)
    if slepi >= SLEPI_PODRED:
        speshni.append("пазачът не е могъл да провери " + str(slepi)
                       + " пъти подред — това също е повреда")

    if not speshni:
        print("")
        print("   ✅ всичко важно се вижда и работи"
              if not neyasni else
              "   ⚠️  работи каквото виждам, но има непроверено (виж горе)")
        sast["posleden_obhod"] = sega.isoformat()
        pishi_sastoyanie(sast)
        return 0

    klyuch = "|".join(sorted(t.split(" — ")[0] for t in speshni))
    if not kazvai_li(klyuch, sast, sega):
        print("")
        print("   (същата тревога вече е казана — почивка " + str(POCHIVKA_CH) + " ч)")
        sast["posleden_obhod"] = sega.isoformat()
        pishi_sastoyanie(sast)
        return 1

    t = tekst_trevoga(cherveni, mulchat,
                      neyasni if slepi >= SLEPI_PODRED else [], sega)
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
