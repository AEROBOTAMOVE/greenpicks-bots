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

    log = ot_github("predict_log.json")
    if log is None:
        log = chetiv("predict_log.json", [])
    # 🗄️ 18.08.2026. Приключените стари записи вече живеят в архив, за да не
    # расте горещият дневник без таван. Статистиката обаче иска ЦЕЛИЯ живот —
    # иначе успеваемостта ще се „нулира" на всеки 120 дни без причина.
    arhiv = ot_github("predict_log_arhiv.json")
    if arhiv is None:
        arhiv = chetiv("predict_log_arhiv.json", [])
    if isinstance(arhiv, list) and arhiv:
        log = arhiv + list(log or [])
        print("   (плюс " + str(len(arhiv)) + " архивни записа)")
    st = ot_github("predict_state.json")
    if st is None:
        st = chetiv("predict_state.json", {})
    diag = (st.get("diag") or {}).get("sportove") or {}
    koga = (st.get("diag") or {}).get("koga") or "?"

    problemi = []
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

    # ---------- 5. СРЕЩУ ПАЗАРА ----------
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
