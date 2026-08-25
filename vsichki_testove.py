# -*- coding: utf-8 -*-
"""ПУСКА ВСИЧКИ САМОПРОВЕРКИ. Един изход: наред или не.

═══════════════════════════════════════════════════════════════════════════
ЗАЩО СЪЩЕСТВУВА (25.08.2026)
═══════════════════════════════════════════════════════════════════════════

Лов на слепи петна намери следното: осем модула носят около 460 самопроверки,
които НИТО ЕДИН workflow не изпълнява.

    pazar.py 107 · pinnacle.py 60 · itf.py 61 · azia.py 37
    volley_evro.py 75 · sezon.py 50 · sglasie.py 39 · zdrave.py 71

Пуска се predictor, scorer, router_bot, budilnik и още няколко — а точно
модулите, които държат цените, резултатите от малкия тур и азиатския
бейзбол, вървят непроверени в GitHub.

Самопроверка, която никой не изпълнява, е коментар. Изглежда като защита,
не е защита, и — по-лошо — създава усещане за покритие, каквото няма.

═══════════════════════════════════════════════════════════════════════════
КАК Е ПОСТРОЕН
═══════════════════════════════════════════════════════════════════════════

1. СПИСЪКЪТ НЕ Е ЗАКОВАН. Файловете се откриват от диска по наличие на
   `def selftest`. Закован списък остарява в деня, в който някой добави
   модул — и мълчи за него завинаги.

2. ВСЕКИ В СВОЙ ПРОЦЕС. Модул, който гръмне при внос, не бива да отнесе
   останалите със себе си. Пада един — другите се пускат докрай.

3. МЪЛЧАНИЕТО Е ПРОВАЛ. Ако модулът не отпечата ред със сметка, това НЕ се
   брои за успех. Точно този клас грешка ни е ухапвал: нула прегледани се
   чете като нула проблеми.
"""

import io
import os
import re
import subprocess
import sys

# Файлове, които НЕ се пускат: тези, чийто selftest пипа Telegram или мрежа
# по устройство, и еднократните инструменти. Всеки с причина, не по усет.
PROPUSKAY = {
    "vsichki_testove.py": "този файл",
    "reset.py": "нулира групата — не се пуска в проверка",
    "setup_topics.py": "еднократна настройка",
    "seed_rooms.py": "еднократно засяване",
    "seed_news.py": "еднократно засяване",
    "channel_seed.py": "еднократно засяване",
    "edu_seed.py": "еднократно засяване",
    "make_rooms.py": "иска токен",
    "setup_hub.py": "иска токен",
    "build_brandbook.py": "инструмент, не част от бота",
}

# Редовете, по които се разпознава сметката. Всеки модул пише по своему —
# затова се търсят и трите форми, не една.
BROYACHI = (
    re.compile(r"(\d+)\s+наред,\s*(\d+)\s+счупени"),
    re.compile(r"(\d+)\s+мина\w*,\s*(\d+)\s+падна\w*"),
    re.compile(r"(\d+)\s+проверки,\s*(\d+)\s+червени"),
)


# Формата „минали / общо" — там ВТОРОТО число е СБОРЪТ, не счупените.
# 🔴 ЧЕТАТ СЕ ЧИСЛАТА, НЕ ДУМИТЕ. matches_bot печата „PASS" накрая дори
# когато има паднали: f"SELFTEST: {минали}/{общо} PASS". Тоест „PASS" там е
# част от шаблона, не присъда. Четях ли нея, счупен модул щеше да минава
# за здрав — точно този клас грешка ловим в целия проект.
OT_OBSHTO = (
    re.compile(r"SELFTEST[:\s]+(\d+)\s*/\s*(\d+)"),
)

# Ред „всичко мина" — без второ число, защото го няма.
VSICHKO_MINA = (
    re.compile(r"Всички\s+(\d+)\s+проверки\s+мина"),
)

# Знаци за провал, които важат НЕЗАВИСИМО от сметката. Появи ли се някой,
# модулът е паднал, дори редът със сметката да изглежда чист.
PADNALI_ZNAK = ("ПАДНАЛИ", "FAIL ", "Traceback")


def moduli(papka=None):
    """Имената на модулите със selftest, намерени на диска. Сортирани."""
    papka = papka or os.path.dirname(os.path.abspath(__file__))
    out = []
    try:
        fajlove = sorted(os.listdir(papka))
    except Exception:                                        # noqa: BLE001
        return []
    for f in fajlove:
        if not f.endswith(".py") or f.startswith("backtest"):
            continue
        if f in PROPUSKAY:
            continue
        p = os.path.join(papka, f)
        try:
            with io.open(p, encoding="utf-8") as fh:
                if "def selftest" not in fh.read():
                    continue
        except Exception:                                    # noqa: BLE001
            continue
        out.append(f[:-3])
    return out


def razcheti(izhod):
    """(наред, счупени) от текста. (None, None), ако НЯМА сметка изобщо.

    🔴 None НЕ Е нула. Модул, който не е отпечатал сметка, не е минал —
    той е МЪЛЧАЛ, а мълчанието се брои за провал от извикващия.
    """
    t = str(izhod or "")
    nay = None
    for r in BROYACHI:
        for m in r.finditer(t):
            nay = (int(m.group(1)), int(m.group(2)))     # последната среща
    if nay is None:
        for r in OT_OBSHTO:
            for m in r.finditer(t):
                mina, obshto = int(m.group(1)), int(m.group(2))
                nay = (mina, max(0, obshto - mina))
    if nay is None:
        for r in VSICHKO_MINA:
            for m in r.finditer(t):
                nay = (int(m.group(1)), 0)
    if nay is None:
        return (None, None)
    # Знакът за провал БИЕ сметката: по-добре фалшива тревога, отколкото
    # пропуснат счупен модул.
    if any(z in t for z in PADNALI_ZNAK) and nay[1] == 0:
        return (nay[0], 1)
    return nay


def pusni(ime, papka=None, timeout=180):
    """(наред, счупени, бележка) за един модул. Свой процес."""
    papka = papka or os.path.dirname(os.path.abspath(__file__))
    try:
        r = subprocess.run(
            [sys.executable, "-c", "import %s as M; M.selftest()" % ime],
            cwd=papka, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return (None, None, "заби над %d сек" % timeout)
    except Exception as e:                                   # noqa: BLE001
        return (None, None, "не можах да го пусна: " + str(e)[:60])
    izh = (r.stdout or "") + (r.stderr or "")
    ok, bad = razcheti(izh)
    if ok is None:
        posl = [l for l in izh.strip().split("\n") if l.strip()]
        return (None, None, "не отпечата сметка"
                + ((" · " + posl[-1][:70]) if posl else ""))
    if r.returncode != 0 and not bad:
        return (ok, bad, "сметката е чиста, но изходът е %d" % r.returncode)
    return (ok, bad, "")


def main():
    imena = moduli()
    if not imena:
        print("🔴 НЕ НАМЕРИХ НИТО ЕДИН МОДУЛ СЪС SELFTEST — това само по себе"
              " си е повреда.")
        return 1
    print("🧪 ВСИЧКИ САМОПРОВЕРКИ · %d модула" % len(imena))
    print("=" * 62)
    obshto_ok = obshto_bad = 0
    padnali = []
    for ime in imena:
        ok, bad, bel = pusni(ime)
        if ok is None:
            padnali.append((ime, bel))
            print("   🔴 %-16s %s" % (ime, bel))
            continue
        obshto_ok += ok
        obshto_bad += bad
        znak = "🔴" if (bad or bel) else "  "
        print("   %s %-16s %4d наред · %d счупени%s"
              % (znak, ime, ok, bad, (" · " + bel) if bel else ""))
        if bad or bel:
            padnali.append((ime, "%d счупени" % bad if bad else bel))
    print("=" * 62)
    print("   ОБЩО: %d проверки · %d счупени · %d модула проблемни"
          % (obshto_ok, obshto_bad, len(padnali)))
    if padnali:
        print("")
        print("🔴 ЗА ОПРАВЯНЕ:")
        for ime, z in padnali:
            print("   • %s — %s" % (ime, z))
        return 1
    return 0


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # ---------------------------------------------- четенето на сметката
    check("чете „наред/счупени\"", razcheti("САМОПРОВЕРКА: 891 наред, 0 счупени")
          == (891, 0))
    check("чете „минаха/паднаха\"", razcheti("ПРОБА: 61 минаха, 0 паднаха")
          == (61, 0))
    check("чете „проверки/червени\"", razcheti("✅ 37 проверки, 0 червени")
          == (37, 0))
    check("вижда и счупените", razcheti("х: 100 наред, 7 счупени") == (100, 7))
    # 🔴 ГЛАВНАТА: мълчанието НЕ Е нула.
    check("липсваща сметка НЕ е нула", razcheti("нищо смислено") == (None, None))
    check("празното НЕ е нула", razcheti("") == (None, None))
    check("None НЕ е нула", razcheti(None) == (None, None))
    check("чете SELFTEST 63 / 63 OK", razcheti("SELFTEST 63 / 63 OK") == (63, 0))
    check("чете SELFTEST: 44/44 PASS", razcheti("SELFTEST: 44/44 PASS") == (44, 0))
    check("от сбора вади падналите", razcheti("SELFTEST 60 / 63 x") == (60, 3))
    check("чете реда всичко мина",
          razcheti("Всички 198 проверки минаха.") == (198, 0))
    # 🔴 НАЙ-ВАЖНАТА: думата PASS не бива да прикрива паднали.
    check("думата PASS не спасява паднал модул",
          razcheti("FAIL нещо\nSELFTEST: 43/44 PASS")[1] >= 1)
    check("падналите бият чистата сметка",
          razcheti("ПАДНАЛИ (2): a, b\nВсички 198 проверки минаха.")[1] >= 1)
    check("трасето бие чистата сметка",
          razcheti("Traceback (most recent call last):\nx: 10 наред, 0 счупени")[1] >= 1)
    check("чистият изход си остава чист", razcheti("x: 10 наред, 0 счупени") == (10, 0))
    check("всеки знак за провал е низ",
          all(isinstance(z, str) and z for z in PADNALI_ZNAK))

    check("взима се ПОСЛЕДНАТА сметка",
          razcheti("а: 5 наред, 0 счупени\nб: 9 наред, 2 счупени") == (9, 2))

    # ---------------------------------------------- откриването
    import tempfile
    import shutil
    d = tempfile.mkdtemp()
    try:
        with io.open(os.path.join(d, "ima.py"), "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0, []\n")
        with io.open(os.path.join(d, "nyama.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        with io.open(os.path.join(d, "backtest_x.py"), "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0, []\n")
        with io.open(os.path.join(d, "reset.py"), "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0, []\n")
        m = moduli(d)
        check("намира модул със selftest", "ima" in m)
        check("пропуска модул без selftest", "nyama" not in m)
        check("пропуска изследователските", "backtest_x" not in m)
        check("пропуска изрично изключените", "reset" not in m)
        check("списъкът е подреден", m == sorted(m))
        check("празна папка дава празен списък",
              moduli(os.path.join(d, "nyama_takava")) == [])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ---------------------------------------------- списъкът на пропуснатите
    check("всеки пропуснат има ПРИЧИНА",
          all(isinstance(v, str) and len(v) > 3 for v in PROPUSKAY.values()))
    check("самият файл е пропуснат", "vsichki_testove.py" in PROPUSKAY)
    # 🔴 Ако този списък почне да расте, покритието пада мълчаливо.
    check("пропуснатите са малко", len(PROPUSKAY) <= 14)

    # ---------------------------------------------- истинските модули
    nashi = moduli()
    for zadalzhitelen in ("predictor", "scorer", "pazar", "pinnacle",
                          "sglasie", "pazach", "cyalost"):
        check("открит е " + zadalzhitelen, zadalzhitelen in nashi)
    check("намерени са поне десет модула", len(nashi) >= 10)

    print("САМОПРОВЕРКА НА ПУСКАЧА: %d наред, %d счупени" % (ok, len(bad)))
    for b in bad:
        print("   счупено: " + b)
    return ok, bad


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--selftest" in sys.argv:
        _ok, _bad = selftest()
        sys.exit(1 if _bad else 0)
    sys.exit(main())
