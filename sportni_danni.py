# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — сървърен теглич на ЖИВИ спортни данни (API-Football).

ЗАЩО: безплатните планове са малки (API-Football 100 заявки/ДЕН). Затова тук
ЕДНА заявка `fixtures?live=all` взима ВСИЧКИ живи мачове наведнъж → пише
`zhivo_futbol.json`, който платформата чете. Всички клиенти четат кеша, не
хабят квота. Ключът НЕ влиза никъде публично — чете се от ../sports_keys.json
(извън repo-то) или от env API_FOOTBALL_KEY (за GitHub Secrets, 24/7).

  python sportni_danni.py            — тегли живите, пише json, печата отчет
  python sportni_danni.py --selftest — проверките, без мрежа
"""
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BAZA = "https://v3.football.api-sports.io"
IZHOD_FILE = os.environ.get("ZHIVO_FILE") or "zhivo_futbol.json"
TAVAN_ZHIVI = 60  # най-много толкова живи мача в изхода (пакетът да е лек)


def klyuch():
    k = os.environ.get("API_FOOTBALL_KEY")
    if k:
        return k.strip()
    for p in ("../sports_keys.json", "sports_keys.json",
              os.path.join(os.path.dirname(__file__), "..", "sports_keys.json")):
        try:
            with io.open(p, encoding="utf-8") as f:
                return str(json.load(f).get("api_football") or "").strip()
        except Exception:  # noqa: BLE001
            continue
    return ""


def _text(v):
    return str(v) if v is not None else ""


def bezopasen(fx):
    """Един жив мач → само безопасни полета за клиента."""
    try:
        f, lg, tm, gl = fx["fixture"], fx["league"], fx["teams"], fx["goals"]
        st = (f.get("status") or {})
        return {
            "dom": _text((tm.get("home") or {}).get("name")),
            "gost": _text((tm.get("away") or {}).get("name")),
            "liga": _text(lg.get("name")) + (" · " + _text(lg.get("country")) if lg.get("country") else ""),
            "gol_dom": gl.get("home"), "gol_gost": gl.get("away"),
            "minuta": st.get("elapsed"), "status": _text(st.get("short")),
            "start": _text(f.get("date")),
        }
    except (KeyError, TypeError):
        return None


def napravi(data):
    """Суровият отговор на API-Football → чист пакет за платформата."""
    resp = (data or {}).get("response") or []
    zhivi = [z for z in (bezopasen(x) for x in resp) if z and z["dom"] and z["gost"]]
    # само наистина живи (има минута или статус в игра), подредени по минута низх.
    igra = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE"}
    zhivi = [z for z in zhivi if z["status"] in igra]
    zhivi.sort(key=lambda z: (z["minuta"] or 0), reverse=True)
    return {"zhivo": zhivi[:TAVAN_ZHIVI],
            "broy": len(zhivi),
            "obnoveno_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}


def tegli_zhivi(k, otvarach=None):
    otv = otvarach or urllib.request.urlopen
    rq = urllib.request.Request(BAZA + "/fixtures?live=all",
                                headers={"x-apisports-key": k, "Accept": "application/json"})
    r = otv(rq, timeout=25)
    return json.loads(r.read().decode("utf-8"))


def zapazi(paket, path=None):
    p = path or IZHOD_FILE
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(paket, f, ensure_ascii=False)
    os.replace(tmp, p)


def main():
    k = klyuch()
    if not k:
        print("🔴 няма API_FOOTBALL_KEY (нито env, нито ../sports_keys.json)")
        return 1
    try:
        data = tegli_zhivi(k)
    except Exception as ex:  # noqa: BLE001
        print("🔴 API-Football не отговори:", str(ex)[:120])
        return 1
    if data.get("errors"):
        print("🔴 API-Football грешка:", str(data.get("errors"))[:200])
        return 1
    paket = napravi(data)
    zapazi(paket)
    print("⚽ живи мачове сега: %d · записани в %s · остатък заявки днес: %s"
          % (paket["broy"], IZHOD_FILE, (data.get("results") is not None and "ок") or "?"))
    for z in paket["zhivo"][:5]:
        print("   %s'  %s %s:%s %s  (%s)" % (z["minuta"], z["dom"][:18],
              z["gol_dom"], z["gol_gost"], z["gost"][:18], z["status"]))
    return 0


def selftest():
    ok, bad = 0, []

    def ch(ime, u):
        nonlocal ok
        (ok := ok + 1) if u else bad.append(ime)

    demo = {"response": [
        {"fixture": {"id": 1, "date": "2026-09-16T15:00:00+00:00", "status": {"short": "2H", "elapsed": 67}},
         "league": {"name": "Premier League", "country": "England"},
         "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}}, "goals": {"home": 2, "away": 1}},
        {"fixture": {"id": 2, "date": "x", "status": {"short": "FT", "elapsed": 90}},  # свършил → не е жив
         "league": {"name": "La Liga", "country": "Spain"},
         "teams": {"home": {"name": "A"}, "away": {"name": "B"}}, "goals": {"home": 0, "away": 0}},
        {"fixture": {"id": 3, "status": {"short": "NS", "elapsed": None}},  # не започнал → не е жив
         "league": {"name": "X"}, "teams": {"home": {"name": "C"}, "away": {"name": "D"}}, "goals": {"home": None, "away": None}}]}
    p = napravi(demo)
    ch("само живите се броят (1 от 3)", p["broy"] == 1 and len(p["zhivo"]) == 1)
    z = p["zhivo"][0]
    ch("живият е верният мач", z["dom"] == "Arsenal" and z["gost"] == "Chelsea")
    ch("резултат и минута", z["gol_dom"] == 2 and z["gol_gost"] == 1 and z["minuta"] == 67)
    ch("лига + държава", z["liga"] == "Premier League · England")
    ch("свършил мач се маха (FT)", all(x["status"] != "FT" for x in p["zhivo"]))
    ch("боклук не гърми", napravi({})["broy"] == 0 and napravi(None)["broy"] == 0
       and bezopasen({}) is None)
    # ключът не е зашит в кода (фрагментът е разцепен, за да не се хване проверката сама)
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    ch("файлът няма зашит ключ", ("ecaa" + "edd4c6a3171cf") not in src)
    print("САМОПРОВЕРКА НА ТЕГЛИЧА: %d наред, %d счупени" % (ok, len(bad)))
    for b in bad:
        print("   🔴", b)
    return 0 if not bad else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(selftest() if ("--selftest" in sys.argv or "selftest" in sys.argv) else main())
