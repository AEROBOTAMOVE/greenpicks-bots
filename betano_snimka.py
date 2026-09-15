# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — СНИМКАТА НА БЕТАНО 🇧🇬 (15.09.2026)

ЗАЩО: Бетано връща HTTP 403 на сървърите на GitHub (записано от ловеца на
15.09 в 10:49 UTC), а от компютъра в България — HTTP 200. Без това наживо
нито коефициентът на Бетано, нито ловецът, нито котвата работят.

КАКВО ПРАВИ: пуска се на компютъра в България (задача в Windows, всеки час),
тегли предстоящата оферта с НАШИЯ подпис (greenpicks-bot, не браузър) и я
качва като ЕДИН файл, `betano_snimka.json`, в отделния клон `betano-snimka`.
Работилниците в GitHub го свалят и мозъкът/ловецът четат от него.

🔴 ГРАНИЦИ:
  · пише САМО в клона `betano-snimka` (главният клон с кода не се пипа);
    клонът се презаписва — там живее една снимка, не история;
  · празна снимка (0 събития) НЕ се качва — старата сама остарява и
    работилницата спира да я ползва след BETANO_SNIMKA_MAX_MIN;
  · в Telegram не праща нищо; ключ/парола не държи — git ги взима от
    Windows (git credential manager).

ПЪТ НАЗАД: спри задачата в Windows (schtasks /Change /TN "GreenPicks Betano снимка" /DISABLE);
без свежа снимка ботът върви само с Pinnacle, както преди.

  python betano_snimka.py          — снимка + качване
  python betano_snimka.py --suho   — само снимка във файл, без качване
"""
import io
import json
import os
import subprocess
import sys

TUK = os.path.dirname(os.path.abspath(__file__))
if TUK not in sys.path:
    sys.path.insert(0, TUK)

KLON = "betano-snimka"                     # 🔴 единственият клон, в който се пише
REPO = "https://AEROBOTAMOVE@github.com/AEROBOTAMOVE/greenpicks-bots.git"
PAPKA = (os.environ.get("SNIMKA_PAPKA") or "").strip() or os.path.join(
    os.path.dirname(TUK), "GREENPICKS_SNIMKA")
GIT = (os.environ.get("SNIMKA_GIT") or "").strip() or r"C:\Program Files\Git\cmd\git.exe"
# Заявки към Бетано по спорт за една снимка (турнир = 1 заявка). Сборът е
# таванът на натоварването от този компютър на час.
BYUDZHET = {"football": 150, "tennis": 100, "tabletennis": 60, "basketball": 40,
            "hockey": 40, "volleyball": 30, "baseball": 20, "esports": 20,
            "rugby": 15, "amfootball": 15, "mma": 10}


def _git(*args, check=True):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    r = subprocess.run([GIT, "-C", PAPKA] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180, env=env)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (args[0], (r.stderr or r.stdout).strip()[:200]))
    return r


def kachi(koga):
    """Една снимка в клона KLON: първия път init, после amend + принудително пращане."""
    if not os.path.isdir(os.path.join(PAPKA, ".git")):
        _git("init", "-q")
        _git("config", "user.name", "greenpicks-bot")
        _git("config", "user.email", "bot@greenpicks")
        _git("config", "core.autocrlf", "false")
        _git("checkout", "-q", "-b", KLON)
    tek = _git("rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()
    if tek not in (KLON, "HEAD"):
        print("🔴 папката стои на клон «%s», не на «%s» — отказ" % (tek, KLON))
        return 1
    _git("add", "betano_snimka.json")
    ima = _git("rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0
    _git("commit", "-q", *(["--amend"] if ima else []), "-m", "betano snimka " + koga)
    r = _git("push", "-q", "-f", REPO, KLON + ":refs/heads/" + KLON, check=False)
    if r.returncode != 0:
        print("🔴 качването не мина:", (r.stderr or r.stdout).strip()[:200])
        return 1
    print("🟢 качена в клона", KLON)
    return 0


def main():
    suho = "--suho" in sys.argv
    # Настройките се слагат ТУК, преди внасянето — не при внасяне на файла,
    # иначе пакетът с проверките би ги наложил и на другите модули.
    os.environ["BETANO_SNIMKA"] = ""      # пишещият НИКОГА не чете снимка
    os.environ.setdefault("BETANO_TAVAN_TURNIRI", "60")
    import betano as BET
    d = BET.napravi_snimka(list(BYUDZHET), byudzhet=BYUDZHET)
    n = sum(len(v) for v in d["sportove"].values())
    print("снимка %s · %d събития · %s · откази: %s · заявки: %s" % (
        d["koga"], n, ", ".join("%s %d" % (k, len(v)) for k, v in d["sportove"].items()),
        d["otkazi"] or "няма", d.get("statistika")))
    if n == 0:
        print("🔴 празна снимка — НЕ качвам (старата остарява сама)")
        return 1
    os.makedirs(PAPKA, exist_ok=True)
    put = os.path.join(PAPKA, "betano_snimka.json")
    with io.open(put + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(put + ".tmp", put)
    if suho:
        print("СУХО: записано в", put, "— нищо не е качено")
        return 0
    return kachi(d["koga"])


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    check("пише само в клона betano-snimka", KLON == "betano-snimka")
    check("пращането е към refs/heads/KLON, не към главния клон",
          'KLON + ":refs/heads/" + KLON' in src and ('"' + "ma" + "in" + '"') not in src)
    check("адресът не носи ключ", "@github.com" in REPO and ":" not in REPO.split("@")[0][8:])
    check("натоварването е с таван", 0 < sum(BYUDZHET.values()) <= 600)
    _main = src.split("def main(")[1].split("\ndef ")[0]
    check("пишещият не чете снимка",
          ('os.environ["BETANO_SNIMKA"] = ' + '""') in _main
          and _main.index("BETANO_SNIMKA") < _main.index("import betano"))
    check("празна снимка не се качва", "НЕ качвам" in src)
    check("няма път към Telegram", ("api." + "telegram") not in src and ("BOT_" + "TOKEN") not in src)
    print("САМОПРОВЕРКА НА СНИМКАТА: %d наред, %d счупени" % (ok, len(bad)))
    for b in bad:
        print("   🔴", b)
    return 0 if not bad else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
