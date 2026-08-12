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

Чете:
  predict_log.json    — какво е пуснато и какво е отсъдено
  predict_state.json  — черната кутия на последния рън (по спорт)
  GitHub Actions API  — зелени ли са рънoвете (без ключ, публично)
"""
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SOFIA = ZoneInfo("Europe/Sofia")
NL = chr(10)
REPO = os.environ.get("ZDRAVE_REPO") or "AEROBOTAMOVE/greenpicks-bots"

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
def zatvoreni():
    _ot_sredata = os.environ.get("PREDICT_IZKL")
    if _ot_sredata is not None:
        return {s.strip() for s in _ot_sredata.split(",") if s.strip()}
    try:
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "predictor.py"), encoding="utf-8-sig") as f:
            src = f.read()
    except Exception:                                        # noqa: BLE001
        return {"hockey", "amfootball"}
    marker = "_izkl_raw = " + chr(34)
    i = src.find(marker)
    if i < 0:
        return set()
    j = src.find(chr(34), i + len(marker))
    return {s.strip() for s in src[i + len(marker):j].split(",") if s.strip()}


ZATVORENI = zatvoreni()
KOGA_TRAGVA = {"hockey": "тръгва около 15.09, когато НХЛ отваря",
               "amfootball": "тръгва в началото на септември, с редовния сезон"}


def chetiv(path, po_podrazbirane):
    try:
        with io.open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:                                        # noqa: BLE001
        return po_podrazbirane


def ot_github(path):
    """Чете файл от хранилището. През api, не през raw — raw КЕШИРА и лъже."""
    import base64
    url = "https://api.github.com/repos/" + REPO + "/contents/" + path + "?ref=main"
    try:
        rq = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(rq, timeout=30) as r:
            return json.loads(base64.b64decode(json.loads(r.read())["content"]))
    except Exception as e:                                   # noqa: BLE001
        print("   (GitHub мълчи: " + str(e)[:60] + " — чета локалното)")
        return None


def runove():
    url = "https://api.github.com/repos/" + REPO + "/actions/runs?per_page=30"
    try:
        rq = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(rq, timeout=30) as r:
            return json.loads(r.read()).get("workflow_runs") or []
    except Exception:                                        # noqa: BLE001
        return []


def main():
    kratko = "--kratko" in sys.argv
    now = datetime.now(SOFIA)
    dnes = now.strftime("%Y-%m-%d")

    log = ot_github("predict_log.json")
    if log is None:
        log = chetiv("predict_log.json", [])
    st = ot_github("predict_state.json")
    if st is None:
        st = chetiv("predict_state.json", {})
    diag = (st.get("diag") or {}).get("sportove") or {}
    koga = (st.get("diag") or {}).get("koga") or "?"

    problemi = []
    redove = []

    # ---------- 1. ПО СПОРТ ----------
    for b in sorted(IME, key=lambda x: IME[x]):
        if b in ZATVORENI:
            redove.append("%-17s %-46s %s"
                          % (IME[b], "затворен — "
                             + KOGA_TRAGVA.get(b, "до старта на сезона"),
                             "—"))
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
        elif surovi == 0:
            sast = "празно — източникът върна нула срещи"
            problemi.append(IME[b] + ": източникът е празен, а не е извън сезон")
        elif surovi:
            sast = "0 карти днес, но източникът даде %s срещи" % surovi
            problemi.append(IME[b] + ": има срещи, няма карти — филтрите изядоха"
                            " всичко (и нито една не е пусната предния ден)")
        else:
            sast = "няма данни за последния рън"

        procent = ("%d от %d · %d%%" % (poz, len(ots), round(100.0 * poz / len(ots)))
                   if ots else "още нищо отсъдено")
        redove.append("%-17s %-46s %s" % (IME[b], sast, procent))
        for g in gr[:1]:
            problemi.append(IME[b] + ": " + str(g)[:70])

    # ---------- 2. ВИСЯЩИ ----------
    vis = [r for r in log if not r.get("scored")]
    star = [r for r in vis if str(r.get("day") or "")[:10] < dnes]
    bez = [r for r in log if r.get("scored") and r.get("hit") is None]
    # Тези двете се затварят от ПЪРВОТО следващо пускане на оценителя — той
    # отваря наново затворените без източник и отсъжда висящите. Затова тук
    # пише и КОГА, вместо да звучи като авария.
    posl_scorer = ""
    for w in runove():
        if str(w.get("name", "")).startswith("scorer"):
            posl_scorer = str(w.get("run_started_at") or "")[:16].replace("T", " ")
            break
    # 🔴 ПОПРАВЕНО 12.08.2026. Пишеше „13:30 и 22:30 UTC" — а кроновете в
    # score.yml са `30 10` и `30 19` UTC, тоест 13:30 и 22:30 БЪЛГАРСКО.
    # Разлика от три часа в собствения ми диагностичен текст.
    kraj = " (изчистват се на следващото пускане на оценителя, 13:30 и 22:30 БГ"
    kraj += "; последното беше " + posl_scorer + ")" if posl_scorer else ")"
    if star:
        problemi.append("%d прогнози от МИНАЛИ дни още чакат резултат%s" % (len(star), kraj))
    if bez:
        problemi.append("%d прогнози са затворени БЕЗ присъда%s" % (len(bez), kraj))

    # ---------- 3. CI ----------
    rr = runove()
    cherveni = [w for w in rr if w.get("conclusion") not in ("success", None)]

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
        if rr:
            print("      последните %d рънa в CI: %d червени" % (len(rr), len(cherveni)))
            for w in cherveni[:3]:
                print("         🔴 %s · %s" % (w.get("name", "")[:26], w.get("run_started_at", "")))
        print("")

    if problemi:
        print("🔴 ЗА ГЛЕДАНЕ (%d):" % len(problemi))
        for p in problemi:
            print("   • " + p)
        return 1
    print("✅ ВСИЧКО Е ЧИСТО — няма празен спорт без причина, няма висящи, няма червени рънoве.")
    if ZATVORENI:
        print("   (затворени до сезона: "
              + ", ".join(IME.get(x, x) for x in sorted(ZATVORENI)) + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
