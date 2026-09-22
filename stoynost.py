# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ЛОВЕЦЪТ НА СТОЙНОСТ, В СЯНКА 💎 (15.09.2026)

Един въпрос: ПЛАЩА ЛИ БЕТАНО ПОВЕЧЕ, ОТКОЛКОТО МАЧЪТ СТРУВА?

ЗАЩО СЪЩЕСТВУВА
Измерено на живия дневник (15.09.2026): публикуваното число вече Е пазарното
(67.2% обявено → 67.2% сбъднато), моделът не бие пазара, ROI = −маржа.
Измерено на цялата оферта същия ден: Бетано плаща СРЕДНО 7.19% под честната
цена на Pinnacle, но ~1.5% от изходите са с EV над +2% — всичките във футбола,
често равен или аутсайдер, които моделът никога не посочва.

Тоест стойност има, но не там, където търси мозъкът. Този файл я търси
директно: сдвоява всеки предстоящ мач Pinnacle × Бетано и записва изходите,
които Бетано надплаща.

В СЯНКА — НИЩО НЕ СЕ ПРАЩА
Файлът няма нито един ред към Telegram. Само пише `stoynost_log.json`:
  · при ПЪРВОТО виждане: коефициентът на Бетано и честната цена на Pinnacle
    (това е «залогът» — по първата видяна цена, не по най-добрата по-късно);
  · при всяко следващо пускане до старта: последната цена на Pinnacle.

КАК СЕ ДОКАЗВА — БЕЗ ДА СЕ ЧАКАТ РЕЗУЛТАТИ
Затварящата цена на Pinnacle е най-добрата оценка на истинската вероятност.
EV_затваряне = p_честна_при_затваряне · к_Бетано_при_откриване − 1.
Среден EV_затваряне > 0 с интервал над нулата при n ≥ 50 = стойността е
истинска. Това е въпрос на дни, не на седмици.

🔴 ЧЕСТНА ЦЕНА — ДВА МЕТОДА, ВЗИМА СЕ ПО-ЛОШИЯТ. Пропорционалният е калибриран
до точка при нашите фаворити (68.3% срещу 68.2%), степенният отчита
пристрастието към аутсайдера. Изход минава само ако И ДВАТА казват EV ≥ прага.

🔴 НАД +15% Е ГРЕШКА, НЕ НАХОДКА. Такава «стойност» почти винаги е грешно
сдвояване или застояла линия (видяно: Бетано 14.50 срещу Pinnacle 4.82).

ENV (всички по избор):
  STOYNOST_VKL        1 (по подразбиране) / 0 — изключва напълно
  STOYNOST_SPORTOVE   football (по подразбиране) — стойността беше само там
  STOYNOST_EV_PRAG    0.02
  STOYNOST_LOG_FILE   stoynost_log.json
  STOYNOST_BET_ZAYAVKI 80 — таван заявки към Бетано на пускане

  python stoynost.py            — сканира, обновява, печата отчета
  python stoynost.py --selftest — проверките, без мрежа
"""
import io
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

VKL = (os.environ.get("STOYNOST_VKL") or "1").strip() in ("1", "true", "yes", "да")
SPORTOVE = [s.strip() for s in (os.environ.get("STOYNOST_SPORTOVE") or "football").split(",")
            if s.strip()]
try:
    EV_PRAG = float(os.environ.get("STOYNOST_EV_PRAG") or 0.02)
except ValueError:
    EV_PRAG = 0.02
EV_TAVAN = 0.15            # над това = грешно сдвояване или застояла линия
try:
    KELLY_FRAC = float(os.environ.get("STOYNOST_KELLY_FRAC") or 0.25)   # частичен Кели (¼)
except ValueError:
    KELLY_FRAC = 0.25
KELLY_TAVAN = 0.05         # никога над 5% от банката на един изход
PROZOREC_MIN = 30          # сдвояване по час: ± минути
KEEP_DAYS = 10             # записите се пазят толкова дни след мача
ZATVARYANE_CHASA = 3.0     # последна точка до толкова часа преди старта = затваряне
LOG_FILE = (os.environ.get("STOYNOST_LOG_FILE") or "stoynost_log.json").strip()
IZHODI = ("1", "2", "Х")
# ⚓ Котвата от betano.py (15.09.2026): +129 футболни мача на цялата оферта,
# 135/135 прочетени двойки верни. ПЪТ НАЗАД: STOYNOST_KOTVA=0.
KOTVA_VKL = (os.environ.get("STOYNOST_KOTVA") or "1").strip() in ("1", "true", "yes", "да")


# ═════════════════════════════════════════ ЧЕСТНАТА ЦЕНА
def _stepenen(imp):
    lo, hi = 0.5, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if sum(p ** k for p in imp) > 1:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    return [p ** k for p in imp]


def chestni(koef):
    """(пропорционални, степенни) вероятности без марж. None при боклук."""
    try:
        k = [float(x) for x in koef]
    except (TypeError, ValueError):
        return None
    if len(k) not in (2, 3) or any(not (1.0 < x < 1000.0) for x in k):
        return None
    imp = [1.0 / x for x in k]
    s = sum(imp)
    if not (1.0 < s < 1.2):          # под 1 — липсва изход; над 1.2 — не е пазар
        return None
    return [p / s for p in imp], _stepenen(imp)


def ev_dvata(p_prop, p_pow, koef):
    """(EV пропорционално, EV степенно) за коефициент koef."""
    return p_prop * koef - 1.0, p_pow * koef - 1.0


def kely(ev, koef, frac=None):
    """Частичен Кели: препоръчан дял от банката за залог с този EV и коефициент.

    Пълният Кели за залог е EV / (к − 1); умножаваме по FRAC (¼ по подразбиране,
    по-плавно и по-устойчиво на грешна оценка), режем на 0 отдолу и на тавана
    отгоре. ev трябва да е ПО-ЛОШИЯТ от двата метода (същата предпазливост).
    """
    frac = KELLY_FRAC if frac is None else frac
    b = float(koef) - 1.0
    if b <= 0 or ev <= 0:
        return 0.0
    return round(max(0.0, min(KELLY_TAVAN, frac * (ev / b))), 4)


def _ms_ot_iso(s):
    try:
        return int(datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp() * 1000)
    except (TypeError, ValueError):
        return None


def _sega_tekst(ms):
    return datetime.fromtimestamp(ms / 1000.0, timezone.utc).strftime("%Y-%m-%d %H:%M")


# ═════════════════════════════════════════ СДВОЯВАНЕТО
def sdvoi(mm, sabitiya, sreshta, sega_ms, pasvat=None, kotva=None, sport="football"):
    """[(mid, (дом, гост, лига, старт_ms), събитие_на_Бетано, обърнато)].

    Само предстоящи мачове и само ЕДНОЗНАЧНИ двойки: имената и на двете страни
    (sreshta) И час в прозореца ±30 мин. Два кандидата = мълчание.
    pasvat(лига_Pinnacle, лига_Бетано) — жени/възраст трябва да съвпадат
    (betano.etiketite_pasvat). Националните отбори носят едно име за мъже и жени.
    """
    po_chas = {}
    for e in sabitiya or ():
        try:
            m = int(e[2]) // 60000
        except (TypeError, ValueError, IndexError):
            continue
        po_chas.setdefault(m, []).append(e)
    out = []
    for mid, zap in (mm or {}).items():
        try:
            a, b, lg, st = zap[0], zap[1], zap[2], zap[3]
        except (TypeError, IndexError):
            continue
        ms = _ms_ot_iso(st)
        if ms is None or ms <= sega_ms:
            continue
        mn = ms // 60000
        kand = []
        for k in range(mn - PROZOREC_MIN, mn + PROZOREC_MIN + 1):
            for e in po_chas.get(k, ()):
                if pasvat and len(e) > 6 and e[6] and not pasvat(str(lg), str(e[6])):
                    continue
                if sreshta(a, str(e[0])) and sreshta(b, str(e[1])):
                    kand.append((e, False))
                elif sreshta(a, str(e[1])) and sreshta(b, str(e[0])):
                    kand.append((e, True))
        if len(kand) == 1:
            out.append((str(mid), (a, b, lg, ms), kand[0][0], kand[0][1]))
        elif not kand and kotva:
            # ⚓ КОТВАТА (betano.kotva, 15.09.2026) — само когато строгото е
            # мълчало напълно; два строги кандидата остават мълчание. Връща
            # цените В НАШИЯ ред, затова събитието се сглобява необърнато и
            # се белязва с 9-и елемент «kotva».
            r = kotva(sport, a, b, ms, lg, sabitiya, sega_ms)
            if r:
                out.append((str(mid), (a, b, lg, ms),
                            (a, b, ms, r[0], r[1], r[2], r[3], r[4], "kotva"), False))
    return out


def kandidati(sport, mm, pazari, sabitiya, sreshta, sega_ms, pasvat=None, kotva=None):
    """Изходите, които Бетано надплаща. Всичко в РЕДА НА PINNACLE."""
    out = []
    for mid, (a, b, lg, ms), e, obr in sdvoi(mm, sabitiya, sreshta, sega_ms, pasvat,
                                             kotva, sport):
        c = (pazari or {}).get(mid)
        if not c or not c[0] or not c[1]:
            continue
        pin = [c[0], c[1]] + ([c[2]] if len(c) > 2 and c[2] else [])
        try:
            bet = ([float(e[4]), float(e[3])] if obr else [float(e[3]), float(e[4])])
            if len(pin) == 3:
                if not e[5]:
                    continue
                bet.append(float(e[5]))
        except (TypeError, ValueError, IndexError):
            continue
        ch = chestni(pin)
        if not ch:
            continue
        p_prop, p_pow = ch
        for i in range(len(pin)):
            ev_p, ev_s = ev_dvata(p_prop[i], p_pow[i], bet[i])
            if ev_p > EV_TAVAN or ev_s > EV_TAVAN:
                continue                           # грешка, не находка
            if min(ev_p, ev_s) < EV_PRAG:
                continue
            out.append({
                "klyuch": sport + "|" + mid + "|" + IZHODI[i], "sport": sport,
                "mid": mid, "i": i, "izhod": IZHODI[i], "dom": a, "gost": b,
                "liga": lg, "bet_liga": str(e[6]) if len(e) > 6 else "",
                "obarnato": bool(obr), "kotva": len(e) > 8 and e[8] == "kotva",
                "start_ms": ms, "bet": round(bet[i], 3),
                "pin": [round(float(x), 3) for x in pin],
                "p_prop": round(p_prop[i], 4), "p_pow": round(p_pow[i], 4),
                "ev": round(min(ev_p, ev_s), 4),
                "kely": kely(min(ev_p, ev_s), bet[i])})
    return out


# ═════════════════════════════════════════ ДНЕВНИКЪТ
def zapishi(log, kands, sega_ms):
    """Първото виждане е залогът и НЕ се презаписва. Връща колко са нови."""
    novi = 0
    for k in kands:
        if k["klyuch"] in log:
            continue
        z = dict(k)
        z.update({"t0_ms": sega_ms, "t0": _sega_tekst(sega_ms),
                  "pin_last": list(k["pin"]), "t_last_ms": sega_ms, "n": 1})
        log[k["klyuch"]] = z
        novi += 1
    return novi


def obnovi(log, pazari_po_sport, sega_ms):
    """Последната цена на Pinnacle за всеки ОЩЕ НЕЗАПОЧНАЛ мач. Колко са обновени."""
    n = 0
    for z in log.values():
        if int(z.get("start_ms") or 0) <= sega_ms:
            continue
        if int(z.get("t_last_ms") or 0) >= sega_ms:
            continue                   # записан в това пускане — точката я има
        c = (pazari_po_sport.get(z.get("sport")) or {}).get(str(z.get("mid")))
        if not c or not c[0] or not c[1]:
            continue
        pin = [c[0], c[1]] + ([c[2]] if len(c) > 2 and c[2] else [])
        if len(pin) != len(z.get("pin") or []):
            continue                   # сменен набор изходи — не е същият пазар
        z["pin_last"] = [round(float(x), 3) for x in pin]
        z["t_last_ms"] = sega_ms
        z["n"] = int(z.get("n") or 0) + 1
        n += 1
    return n


def ev_zatvaryane(z):
    """(EV пропорц., EV степенно) по ПОСЛЕДНАТА цена на Pinnacle, или None.

    Мери се само ако последната точка е: поне 30 мин след откриването (иначе е
    същото пускане) и до ZATVARYANE_CHASA часа преди старта (иначе не е затваряне).
    """
    try:
        t0, tl, st = int(z["t0_ms"]), int(z["t_last_ms"]), int(z["start_ms"])
    except (KeyError, TypeError, ValueError):
        return None
    if tl - t0 < 30 * 60000:
        return None
    if st - tl > ZATVARYANE_CHASA * 3600000 or tl > st:
        return None
    ch = chestni(z.get("pin_last") or [])
    if not ch:
        return None
    i = int(z.get("i") or 0)
    return ev_dvata(ch[0][i], ch[1][i], float(z["bet"]))


def otchet(log, povtori=3000, seed=20260915):
    """Средният EV при затваряне с 95% интервал. Речник; n=0, ако няма какво."""
    # Ключ с «_» е бележка (напр. `_diag`), не залог.
    zap = [z for k, z in log.items() if not str(k).startswith("_") and isinstance(z, dict)]
    vals = []
    for z in zap:
        e = ev_zatvaryane(z)
        if e is not None:
            vals.append(e[0])
    out = {"n": len(vals), "otkriti": len(zap)}
    if not vals:
        return out
    rnd = random.Random(seed)
    b = sorted(sum(rnd.choice(vals) for _ in vals) / len(vals) for _ in range(povtori))
    out.update({"ev_zatv": sum(vals) / len(vals), "lo": b[int(0.025 * povtori)],
                "hi": b[int(0.975 * povtori) - 1],
                "dyal_nad_nula": sum(1 for v in vals if v > 0) / len(vals),
                "ev_otkrivane": sum(float(z.get("ev") or 0) for z in zap) / len(zap)})
    return out


def pochisti(log, sega_ms):
    granica = sega_ms - KEEP_DAYS * 86400000
    for k in [k for k, z in log.items() if not str(k).startswith("_")
              and int((z or {}).get("start_ms") or 0) < granica]:
        log.pop(k, None)
    return len(log)


def zaredi(path=None):
    try:
        with io.open(path or LOG_FILE, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:                                        # noqa: BLE001
        return {}


def zapazi(log, path=None):
    tmp = (path or LOG_FILE) + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(tmp, path or LOG_FILE)


def proba_betano(BET, otvarach=None):
    """ЕДИН честен въпрос към Бетано: какво отговаря на ТАЗИ машина.

    🔴 ЗАЩО (15.09.2026). От 08.09 наживо НИТО ЕДНА от 622 карти не е взела
    цена от Бетано, а три пускания на ловеца в GitHub дадоха празен дневник —
    при 5 находки от първия път на компютъра в София. Дневникът на Actions не
    се чете отвън, затова отговорът се пише тук: код, байтове или грешка.
    Подписът е нашият (BET.UA), не преправен браузър.
    """
    import urllib.error
    import urllib.request
    url = BET.BAZA + "/sport/soccer/" + BET.OPASHKA
    otv = otvarach or urllib.request.urlopen
    rq = urllib.request.Request(url, headers={"User-Agent": BET.UA,
                                              "Accept": "application/json"})
    try:
        r = otv(rq, timeout=20)
        b = r.read()
        kod = getattr(r, "status", None) or getattr(r, "code", None) or "?"
        return "HTTP %s · %d байта" % (kod, len(b or b""))
    except urllib.error.HTTPError as e:
        return "HTTP %s %s" % (e.code, str(e.reason or "")[:40])
    except Exception as e:                                   # noqa: BLE001
        return "грешка %s: %s" % (type(e).__name__, str(e)[:60])


# ═════════════════════════════════════════ ПУСКАНЕ
def main():
    if not VKL:
        print("Ловецът на стойност е изключен (STOYNOST_VKL=0).")
        return 0
    # Отделен процес: бюджетът на Бетано е НАШ, не този на мозъка (24 заявки,
    # 14 турнира, насочени към търсената лига). Тук лига няма — искаме широко.
    os.environ["BETANO_CENI"] = "1"
    os.environ["BETANO_TAVAN_ZAYAVKI"] = (os.environ.get("STOYNOST_BET_ZAYAVKI") or "80").strip()
    os.environ["BETANO_TAVAN_TURNIRI"] = "60"
    try:
        import betano as BET
        import pinnacle as PIN
    except Exception as ex:                                  # noqa: BLE001
        print("🔴 не мога да внеса изворите:", str(ex)[:120])
        return 0
    sega_ms = int(time.time() * 1000)
    log = zaredi()
    pz_po_sport = {}
    vsi_k = []
    # 🔴 БЕЛЕЖКАТА (15.09.2026): какво са казали изворите на ТАЗИ машина.
    diag = {"koga": _sega_tekst(sega_ms) + " UTC", "sportove": {},
            "betano_proba": proba_betano(BET)}
    print("   Бетано отговаря: " + diag["betano_proba"])
    for sport in SPORTOVE:
        if sport not in getattr(PIN, "SPORT_ID", {}) or sport not in getattr(BET, "SPORT", {}):
            print("   %-10s няма го и в двете книги — пропускам" % sport)
            diag["sportove"][sport] = "няма го в двете книги"
            continue
        try:
            mm = PIN.machove(sport)
            pz = PIN.pazari(sport)
            ev = BET.sabitiya(sport, None, None)
        except Exception as ex:                              # noqa: BLE001
            print("   %-10s изворът гръмна: %s" % (sport, str(ex)[:80]))
            diag["sportove"][sport] = "гръмна: " + str(ex)[:80]
            continue
        if ev is getattr(BET, "NEPITAN", object()):
            print("   %-10s Бетано отказа — нищо не се пише за този спорт" % sport)
            diag["sportove"][sport] = {"pinnacle": len(mm or {}), "betano": "отказ"}
            continue
        pz_po_sport[sport] = pz or {}
        k = kandidati(sport, mm, pz, ev, BET.sreshta, sega_ms,
                      getattr(BET, "etiketite_pasvat", None),
                      getattr(BET, "kotva", None) if KOTVA_VKL else None)
        novi = zapishi(log, k, sega_ms)
        vsi_k.extend(k)
        diag["sportove"][sport] = {"pinnacle": len(mm or {}), "pinnacle_ceni": len(pz or {}),
                                   "betano": len(ev or []), "sas_stoynost": len(k), "novi": novi,
                                   "po_kotva": sum(1 for x in k if x.get("kotva"))}
        print("   %-10s Pinnacle %d мача · Бетано %d · със стойност сега %d · нови %d"
              % (sport, len(mm or {}), len(ev or []), len(k), novi))
    try:
        diag["betano_zayavki"] = BET.statistika()
    except Exception:                                        # noqa: BLE001
        pass
    ob = obnovi(log, pz_po_sport, sega_ms)
    pochisti(log, sega_ms)
    log["_diag"] = diag
    try:
        zapazi(log)
    except Exception as ex:                                  # noqa: BLE001
        print("🔴 дневникът не се записа:", str(ex)[:120])
    o = otchet(log)
    print("   обновени %d · в дневника %d" % (ob, o["otkriti"]))
    if o["n"]:
        print("💎 EV при затваряне: %+.2f%% [%+.2f .. %+.2f] · n=%d · над нулата %.0f%% · EV при откриване %+.2f%%"
              % (100 * o["ev_zatv"], 100 * o["lo"], 100 * o["hi"], o["n"],
                 100 * o["dyal_nad_nula"], 100 * o["ev_otkrivane"]))
    else:
        print("💎 още няма мачове със затваряща цена — присъдата чака")
    if vsi_k:
        top = sorted(vsi_k, key=lambda x: x.get("kely") or 0, reverse=True)[:3]
        print("   💰 препоръчан залог (¼ Кели, макс 5%%):")
        for x in top:
            print("      %s %s−%s · Бетано %.2f · EV %+.1f%% · заложи %.1f%% от банката"
                  % (x["izhod"], str(x["dom"])[:16], str(x["gost"])[:16], x["bet"],
                     100 * x["ev"], 100 * (x.get("kely") or 0)))
    return 0


# ═════════════════════════════════════════ САМОПРОВЕРКА
def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # честната цена
    ch = chestni([1.90, 1.90])
    check("равен пазар дава 50/50", ch and abs(ch[0][0] - 0.5) < 1e-9 and abs(ch[1][0] - 0.5) < 1e-6)
    ch = chestni([1.30, 3.60])
    check("двата метода се събират до 1",
          ch and abs(sum(ch[0]) - 1) < 1e-9 and abs(sum(ch[1]) - 1) < 1e-6)
    check("степенният дава на фаворита повече от пропорционалния", ch and ch[1][0] > ch[0][0])
    check("тройка се чете", chestni([2.10, 3.40, 3.50]) is not None)
    check("липсващ изход (сбор под 1) не е пазар", chestni([2.50, 3.00]) is None)
    check("боклук не гърми", chestni(["абв", 2]) is None and chestni([]) is None
          and chestni([0.5, 2.0]) is None)

    sreshta = lambda x, y: x.lower() == y.lower()           # noqa: E731
    sega = _ms_ot_iso("2026-09-15T10:00:00Z")
    mm = {"1": ("Lokomotiv", "Nesebar", "Втора лига", "2026-09-15T16:00:00Z"),
          "2": ("Alfa", "Beta", "Л", "2026-09-15T18:00:00Z"),
          "3": ("Gama", "Delta", "Л", "2026-09-15T08:00:00Z"),      # започнал
          "4": ("Epsilon", "Zeta", "Л", "2026-09-16T18:00:00Z")}
    t16 = _ms_ot_iso("2026-09-15T16:00:00Z")
    t18 = _ms_ot_iso("2026-09-15T18:10:00Z")
    sab = [("Lokomotiv", "Nesebar", t16, 1.90, 4.20, 3.60),
           ("Beta", "Alfa", t18, 2.70, 2.95, 3.40),                  # обърнат
           ("Gama", "Delta", _ms_ot_iso("2026-09-15T08:00:00Z"), 2.0, 2.0, 3.0),
           ("Epsilon", "Zeta", _ms_ot_iso("2026-09-17T18:00:00Z"), 2.0, 2.0, 3.0)]
    d = sdvoi(mm, sab, sreshta, sega)
    ids = sorted(x[0] for x in d)
    check("сдвоява по имена и час", "1" in ids and "2" in ids)
    check("започнал мач не се сдвоява", "3" not in ids)
    check("друг ден не се сдвоява", "4" not in ids)
    check("обърнатите страни се хващат", any(x[0] == "2" and x[3] for x in d))
    pasvat = lambda nash, tehen: ("women" in nash.lower()) == ("жени" in tehen.lower())  # noqa: E731
    mm_z = {"9": ("Wales", "Iceland", "Womens Friendly", "2026-09-15T16:00:00Z")}
    sab_m = [("Wales", "Iceland", t16, 2.0, 3.5, 3.3, "Международни / Приятелски")]
    sab_z = [("Wales", "Iceland", t16, 2.0, 3.5, 3.3, "Международни / Приятелски жени")]
    check("женски мач НЕ взима мъжката цена", not sdvoi(mm_z, sab_m, sreshta, sega, pasvat))
    check("женски мач взима женската цена", len(sdvoi(mm_z, sab_z, sreshta, sega, pasvat)) == 1)
    sab2 = sab + [("Lokomotiv", "Nesebar", t16 + 600000, 1.95, 4.0, 3.5)]
    check("два кандидата = мълчание", "1" not in [x[0] for x in sdvoi(mm, sab2, sreshta, sega)])

    # Мач 2: Pinnacle Алфа 2.60, Бетано я пише ГОСТ на 2.95 (+9.9%). Сгреши ли
    # се посоката, Алфа взима 2.70 (+0.6%) и нищо не минава — затова проверката хапе.
    pz = {"1": (1.68, 5.20, 3.90), "2": (2.60, 2.90, 3.30)}
    k = kandidati("football", mm, pz, sab, sreshta, sega)
    kl = {x["klyuch"]: x for x in k}
    check("Бетано 1.90 срещу Pinnacle 1.68 е стойност", "football|1|1" in kl)
    check("EV е по-лошият от двата метода",
          "football|1|1" in kl and abs(kl["football|1|1"]["ev"]
                                       - min(ev_dvata(chestni([1.68, 5.20, 3.90])[0][0],
                                                      chestni([1.68, 5.20, 3.90])[1][0], 1.90))) < 1e-4)
    check("обърнатият мач сравнява СЪЩИЯ отбор",
          kl.get("football|2|1", {}).get("bet") == 2.95 and "football|2|2" not in kl
          and kl.get("football|2|1", {}).get("obarnato") is True)

    # ── ⚓ котвата (15.09.2026)
    _kv_pit = []

    def _kv(sp, d, g, ms_, lg_, ev_, sg_):
        _kv_pit.append((d, g))
        if (d, g) == ("Rangers", "Celtic"):
            return (2.5, 2.6, 3.4, "Шотландия / Премиършип", "/rc/")
        return None
    mm_k = dict(mm)
    mm_k["7"] = ("Rangers", "Celtic", "Scotland - Premiership", "2026-09-15T16:00:00Z")
    rk = [x for x in sdvoi(mm_k, sab, sreshta, sega, None, _kv, "football") if x[0] == "7"]
    check("котвата допълва, когато строгото мълчи",
          len(rk) == 1 and tuple(rk[0][2][3:6]) == (2.5, 2.6, 3.4) and rk[0][3] is False)
    check("котвата НЕ се пита, когато строгото е намерило", ("Lokomotiv", "Nesebar") not in _kv_pit)
    del _kv_pit[:]
    sdvoi(mm, sab2, sreshta, sega, None, _kv, "football")
    check("два строги кандидата = мълчание, без котва", ("Lokomotiv", "Nesebar") not in _kv_pit)
    kk = {x["klyuch"]: x for x in kandidati("football", mm_k, dict(pz, **{"7": (2.20, 3.40, 3.20)}),
                                            sab, sreshta, sega, None, _kv)}
    check("записът по котва е белязан, строгият — не",
          kk.get("football|7|1", {}).get("kotva") is True
          and kk.get("football|1|1", {}).get("kotva") is False)
    check("без котва — старото поведение",
          "7" not in [x[0] for x in sdvoi(mm_k, sab, sreshta, sega)])
    pz_luda = {"1": (1.68, 5.20, 3.90)}
    sab_luda = [("Lokomotiv", "Nesebar", t16, 1.90, 14.50, 3.60)]
    k2 = kandidati("football", mm, pz_luda, sab_luda, sreshta, sega)
    check("над +15% не се записва", "football|1|2" not in {x["klyuch"] for x in k2})

    # ── частичният Кели
    check("Кели е 0 при неположителен EV", kely(-0.01, 2.0) == 0 and kely(0.0, 2.0) == 0)
    check("Кели расте с EV", kely(0.10, 2.0) > kely(0.04, 2.0) > 0)
    check("Кели = FRAC · EV/(к−1)", abs(kely(0.08, 2.0, 0.25) - 0.02) < 1e-9)
    check("Кели никога над тавана", kely(0.14, 1.10) <= KELLY_TAVAN and kely(5.0, 2.0) == KELLY_TAVAN)
    check("всяка находка носи препоръчан залог", bool(k) and all("kely" in x and x["kely"] >= 0 for x in k))

    # дневникът
    log = {}
    check("първото виждане се записва", zapishi(log, k, sega) == len(k))
    k_druga = [dict(x, bet=9.99) for x in k]
    zapishi(log, k_druga, sega + 3600000)
    check("първото виждане НЕ се презаписва",
          all(z["bet"] != 9.99 for z in log.values()))
    z = log.get("football|1|1")
    if z:
        obnovi(log, {"football": {"1": (1.55, 6.00, 4.20)}}, t16 - 2 * 3600000)
        e = ev_zatvaryane(z)
        check("затварящата се обновява", z["pin_last"][0] == 1.55 and z["n"] == 2)
        check("линия към нас дава по-висок EV при затваряне",
              e is not None and e[0] > z["ev"])
        # Всеки случай се отказва САМО от своя пазач: другият би го пуснал.
        _st = int(z["start_ms"])
        z2 = dict(z, t0_ms=_st - 2 * 3600000, t_last_ms=_st - 2 * 3600000 + 60000)
        check("точка от същото пускане НЕ е затваряне", ev_zatvaryane(z2) is None)
        z3 = dict(z, t0_ms=_st - 12 * 3600000, t_last_ms=_st - 10 * 3600000)
        check("точка 10 ч преди старта НЕ е затваряне", ev_zatvaryane(z3) is None)
        z4 = dict(z, t0_ms=_st - 12 * 3600000, t_last_ms=_st - 2 * 3600000)
        check("открито рано, видяно 2 ч преди старта = затваряне", ev_zatvaryane(z4) is not None)
        obnovi(log, {"football": {"1": (1.55, 6.00)}}, t16 - 3600000)
        check("сменен набор изходи не се обновява", len(z["pin_last"]) == 3)
    else:
        check("записът за Локомотив го има", False)
    o = otchet(log, povtori=200)
    check("отчетът брои измеримите", o["n"] >= 1 and "ev_zatv" in o)
    check("празен дневник не гърми", otchet({})["n"] == 0)
    # ── бележката _diag (15.09.2026)
    log_d = dict(log)
    log_d["_diag"] = {"koga": "x", "betano_proba": "HTTP 403"}
    check("бележката _diag не се брои за залог",
          otchet(log_d, povtori=50)["otkriti"] == otchet(log, povtori=50)["otkriti"])
    pochisti(log_d, sega + 400 * 86400000)
    check("бележката _diag оцелява чистенето", "_diag" in log_d)
    check("и залозите пак се чистят", [k for k in log_d if not k.startswith("_")] == [])

    class _Bet(object):
        BAZA, OPASHKA, UA = "https://www.betano.bg/api", "?x", "greenpicks-bot/1.0 (+test)"
    _vidyano = {}

    def _otv403(rq, timeout=None):
        import urllib.error
        _vidyano["ua"] = rq.get_header("User-agent")
        raise urllib.error.HTTPError(rq.full_url, 403, "Forbidden", {}, None)

    class _Otg(object):
        status = 200

        def read(self):
            return b"{}" * 10
    check("пробата казва кода на отказа", proba_betano(_Bet, _otv403).startswith("HTTP 403"))
    check("пробата пита с НАШИЯ подпис", "greenpicks-bot" in str(_vidyano.get("ua")))
    check("пробата казва и успеха",
          proba_betano(_Bet, lambda rq, timeout=None: _Otg()) == "HTTP 200 · 20 байта")
    check("пробата не гърми при мрежова грешка",
          proba_betano(_Bet, lambda rq, timeout=None: (_ for _ in ()).throw(OSError("няма мрежа")))
          .startswith("грешка OSError"))
    stari = {"x": {"start_ms": sega - 20 * 86400000}}
    check("стари записи се чистят", pochisti(stari, sega) == 0)
    check("по подразбиране само футбол", SPORTOVE == ["football"]
          or bool(os.environ.get("STOYNOST_SPORTOVE")))
    # Думите са разцепени, за да не се намери самата проверка.
    _src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    check("файлът няма път към Telegram",
          all(w not in _src for w in ("api." + "telegram", "send" + "Message",
                                      "BOT_" + "TOKEN", "import " + "requests")))
    print("САМОПРОВЕРКА НА ЛОВЕЦА: %d наред, %d счупени" % (ok, len(bad)))
    for b_ in bad:
        print("   🔴", b_)
    return 0 if not bad else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--selftest" in sys.argv or "selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
