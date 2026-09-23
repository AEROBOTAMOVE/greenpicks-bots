# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — „ТОП 5 НА ДЕНЯ" 🔥  (курирана дневна селекция за клиенти)

ЗА КАКВО Е: от целия дневен изход на бота избира 5-те НАЙ-СИЛНИ прогнози и ги
слага в едно примамливо, премиум съобщение за клиентите — вместо да ги залива
с десетки карти. Дава и „доказателството" (успеваемост последни дни) като кука.

🚫 ТОЗИ СКРИПТ НЕ ПРАЩА НИЩО. Само печата (DRY). Пращането се прави от твоята
   съществуваща тръба (poster.py) — по протокол: пращането е БЕЗ път назад.
   Флагът --send само отказва и обяснява. Пътят назад: това е нов файл.

РЕЖИМИ:
  teaser  (по подразбиране) — примамка за НЕплащащи: рекорд + 1 вкус + „още 4 вътре"
                              + призив. НЕ издава петте (пази стойността).
  pylen                     — пълните 5 за плащащите (в стаята на клиентите).

Употреба:
  python top5_dnevno.py                      # teaser за най-скорошния ден с ≥5 карти
  python top5_dnevno.py --rezhim pylen
  python top5_dnevno.py --den 2026-09-05
  python top5_dnevno.py --log predict_log.json --dni 7
"""
import json, sys, argparse
from collections import defaultdict

SPORT_BG = {
    "football": "Футбол", "basketball": "Баскетбол", "tennis": "Тенис",
    "tabletennis": "Тенис на маса", "volleyball": "Волейбол", "hockey": "Хокей",
    "baseball": "Бейзбол", "mma": "ММА", "boxing": "Бокс", "esports": "Е-спорт",
    "rugby": "Ръгби", "amfootball": "Ам. футбол",
}
SPORT_IK = {
    "football": "⚽", "basketball": "🏀", "tennis": "🎾", "tabletennis": "🏓",
    "volleyball": "🏐", "hockey": "🏒", "baseball": "⚾", "mma": "🥊",
    "boxing": "🥊", "esports": "🎮", "rugby": "🏉", "amfootball": "🏈",
}
NL = chr(10)


def zvezdi(n):
    n = int(n or 0)
    return "★" * min(3, n) + "☆" * max(0, 3 - min(3, n))


def kachestvo(r):
    """Ранг за 'най-силна': увереност (p) с тежест + звездите. 0..1."""
    p = float(r.get("p") or 0)
    st = int(r.get("stars") or 0)
    return p * 0.72 + (min(3, st) / 3.0) * 0.28


def izbor_kratko(pick):
    """'2 · Yi-Tian YEH' -> 'Yi-Tian YEH'. '1' -> '1'."""
    s = str(pick or "").strip()
    if " · " in s:
        return s.split(" · ", 1)[1]
    return s


def zaredi(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def izbor_na_den(rows, den):
    """Всички ПОСТНАТИ карти за деня, дедупликирани по мач, подредени по качество."""
    vidyani, out = set(), []
    for r in rows:
        if r.get("day") != den:
            continue
        if not r.get("posted"):
            continue
        k = r.get("key") or (str(r.get("home")) + "|" + str(r.get("away")))
        mach = (str(r.get("home")).lower(), str(r.get("away")).lower())
        if mach in vidyani:
            continue
        vidyani.add(mach)
        out.append(r)
    out.sort(key=kachestvo, reverse=True)
    return out


def posleden_den(rows, minimum=5):
    """Най-скорошният ден с поне `minimum` постнати карти."""
    broy = defaultdict(int)
    for r in rows:
        if r.get("posted") and r.get("day"):
            broy[r["day"]] += 1
    godni = sorted([d for d, n in broy.items() if n >= minimum], reverse=True)
    if godni:
        return godni[0]
    dni = sorted(broy.keys(), reverse=True)
    return dni[0] if dni else None


def rekord(rows, den, dni):
    """Успеваемост на ОТСЪДЕНИТЕ карти в прозорец от `dni` дни преди/до деня."""
    from datetime import date
    y, m, d = (int(x) for x in den.split("-"))
    kraj = date(y, m, d)
    ocen = poz = 0
    for r in rows:
        if not r.get("scored") or r.get("hit") is None:
            continue
        dd = r.get("day")
        if not dd:
            continue
        try:
            yy, mm, dyd = (int(x) for x in dd.split("-"))
            razlika = (kraj - date(yy, mm, dyd)).days
        except Exception:
            continue
        if 0 <= razlika < dni:
            ocen += 1
            if r.get("hit") is True:
                poz += 1
    proc = round(100 * poz / ocen) if ocen else None
    return proc, poz, ocen


def red_pik(r, i):
    ik = SPORT_IK.get(r.get("bucket"), "•")
    sp = SPORT_BG.get(r.get("bucket"), r.get("bucket") or "")
    liga = str(r.get("league") or "").split("·")[0].strip()
    p = int(round(float(r.get("p") or 0) * 100))
    return (f"{i}. {ik} <b>{r.get('home')}</b> — <b>{r.get('away')}</b>{NL}"
            f"   ▸ Прогноза: <b>{izbor_kratko(r.get('pick'))}</b>  ·  увереност <b>{p}%</b>  {zvezdi(r.get('stars'))}{NL}"
            f"   <i>{sp}{(' · ' + liga) if liga else ''}</i>")


def teaser(top, den, proc, poz, ocen):
    best = top[0]
    ik = SPORT_IK.get(best.get("bucket"), "•")
    p = int(round(float(best.get("p") or 0) * 100))
    dok = (f"📊 Последни {ocen} отсъдени: <b>{proc}%</b> успеваемост."
           if proc is not None else "📊 Всеки ден — с извадка и причина, без разкрасяване.")
    return (
        f"🔥 <b>ТОП 5 НА ДЕНЯ</b> · {den}{NL}"
        f"{dok}{NL}{NL}"
        f"Днес подбрахме <b>5</b> от целия поток — само най-силните.{NL}"
        f"Ето вкус — безплатният ни фаворит за деня:{NL}{NL}"
        f"{ik} <b>{best.get('home')}</b> — <b>{best.get('away')}</b>{NL}"
        f"▸ <b>{izbor_kratko(best.get('pick'))}</b> · увереност <b>{p}%</b> {zvezdi(best.get('stars'))}{NL}{NL}"
        f"➕ Още <b>4</b> подбрани прогнози чакат вътре.{NL}"
        f"👉 Влез в The Green Room и вземи пълния Топ 5 днес.{NL}"
        f"<i>Анализ, не гаранция. Само 18+. Играй отговорно.</i>"
    )


def pylen(top, den, proc, poz, ocen):
    dok = (f"📊 Последни {ocen} отсъдени: <b>{proc}%</b> ({poz}/{ocen})."
           if proc is not None else "")
    redove = NL.join(red_pik(r, i + 1) for i, r in enumerate(top))
    return (
        f"🔥 <b>ТОП 5 НА ДЕНЯ</b> · {den}{NL}"
        f"{dok}{NL}{NL}"
        f"{redove}{NL}{NL}"
        f"<i>Подбрани по увереност и рейтинг от целия дневен анализ.{NL}"
        f"Анализ, не гаранция. Само 18+. Играй отговорно.</i>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="predict_log.json")
    ap.add_argument("--den", default=None)
    ap.add_argument("--rezhim", choices=["teaser", "pylen"], default="teaser")
    ap.add_argument("--dni", type=int, default=7)
    ap.add_argument("--broy", type=int, default=5)
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()

    if a.send:
        print("🚫 Пращането НЕ е в този скрипт (по протокол — пращането е без път назад)."
              " Копирай текста в poster.py / ръчно.")
        return 2

    rows = zaredi(a.log)
    den = a.den or posleden_den(rows, a.broy)
    if not den:
        print("Няма данни за ден.")
        return 1
    top = izbor_na_den(rows, den)[: a.broy]
    if not top:
        print("Няма постнати карти за", den)
        return 1
    proc, poz, ocen = rekord(rows, den, a.dni)
    txt = teaser(top, den, proc, poz, ocen) if a.rezhim == "teaser" else pylen(top, den, proc, poz, ocen)
    print("──────── DRY (само печат, нищо не е пратено) ────────")
    print(txt)
    print("──────────────────────────────────────────────────")
    print(f"[ден={den} · избрани={len(top)} · режим={a.rezhim} · рекорд={proc}% от {ocen}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
