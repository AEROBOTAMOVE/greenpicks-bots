# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — АЗИАТСКИ БЕЙЗБОЛ ⚾ NPB (Япония) · KBO (Корея) · зимните лиги

Един въпрос: къде има бейзболен пазар, който ние още не гледаме?

ЗАЩО СЪЩЕСТВУВА
Гледаме само МЛБ. Pinnacle обаче търгува и японската NPB, и корейската KBO —
значи пазар ИМА, а ние не подаваме нито един мач към него. Този модул е
липсващата половина: СРЕЩИ и РЕЗУЛТАТИ, за да може predictor.py да построи
карта, а pinnacle.py да ѝ сложи цена.

🔴 ПЪРВОТО, КОЕТО ТРЯБВАШЕ ДА СЕ ОБОРИ: statsapi.mlb.com Е ПРАЗЕН ЗА АЗИЯ
statsapi.mlb.com/api/v1/sports ЧЕСТНО обявява sportId 31 „Nippon Professional
Baseball" и 32 „Korean Baseball Organization". Изкушението е да ги подадеш на
/schedule и да обявиш победа. Измерено на 19.08.2026:

    sportId=31 (NPB)  2026-08-12..21 → totalGames 0
    sportId=32 (KBO)  2026-08-12..21 → totalGames 0
    sportId=32 (KBO)  2024-08-10..15 → totalGames 0   ← дори ИСТОРИЯТА е нула
    sportId=31 (NPB)  2014-08-10..15 → totalGames 0

    /api/v1/league?sportId=31 → Central League, seasonState=offseason, season 2014
    /api/v1/league?sportId=32 → KBO,            seasonState=offseason, season 2024
    /api/v1/teams?sportId=31&season=2026 → HTTP 404

Тоест регистрацията на лигата съществува, съдържанието — не. Този sportId е
запис в указател, не източник на данни. Ако някой ден го напълнят, кодът тук
ще стане излишен; докато не го напълнят, той е единственият път.

ЗАТОВА: два РАЗЛИЧНИ източника, по един за всяка страна.
  NPB  npb.jp/games/{година}/schedule_{ММ}_detail.html   — цял месец в HTML
  KBO  koreabaseball.com/ws/Schedule.asmx/GetScheduleList — цял месец в JSON

🔴 ДЕФЕКТ №1, КОЙТО КОСТВА ЧАС: KBO връща 406 без X-Requested-With
Учтивата заявка (Content-Type + Accept: application/json) получава
HTTP 406 Not Acceptable. Заявка изобщо БЕЗ Accept получава 200, но с 3533
байта HTML-грешка вместо данни — тоест мълчалив провал, който изглежда
успешен. Измерено:

    Accept: application/json                 → 406
    Content-Type: application/json           → 406
    без Accept                               → 200, 3533 байта HTML  ← лъже
    + X-Requested-With: XMLHttpRequest       → 200, 272323 байта JSON ✅

Затова заявката НОСИ X-Requested-With и Referer, и затова _kbo_mesec вдига
грешка, ако тялото не почва с JSON — 200 не е доказателство.

🔴 ДЕФЕКТ №2: СТРАНИТЕ СА ОБЪРНАТИ МЕЖДУ ДВЕТЕ ЛИГИ
Двата източника пишат мача в ПРОТИВОПОЛОЖЕН ред и никъде не го казват.
Проверено срещу стадиона, който не може да лъже:

    NPB  8/1: „巨人 7-8 DeNA" на 東京ドома (Токио Доум = дом на 巨人)
         → ПЪРВИЯТ е ДОМАКИН
    KBO  08.01: „한화 4 vs 7 KT" на 수원 (Суон = дом на KT)
         → ПЪРВИЯТ е ГОСТ

Ако това се сбърка, картата казва „1", а числото е за другия — точно класът
грешка, който pinnacle.py вече е плащал веднъж. Двете посоки са закотвени в
селфтеста със стадиона като свидетел, за да не могат да се разменят тихо.

🔴 ДЕФЕКТ №3: npb.jp НЕ СЕ ВЕРИФИЦИРА НА ТАЗИ МАШИНА
https://npb.jp дава CERTIFICATE_VERIFY_FAILED. Не е тяхна вина — локалното
хранилище на тази машина има 38 сертификата, а Windows ROOT дава 7 годни.
http:// не е изход: пренасочва 302 към същия https.
Затова: питаме НОРМАЛНО (с проверка) и само ако проверката се спъне, повтаряме
без нея — публична страница с разписание, без вход и без тайни. Кой път е
ползван се ОТЧИТА в --zhivo, за да не стане мълчаливо понижаване на защитата.

ЗИМНИТЕ ЛИГИ — обратното на Азия: statsapi ГИ ИМА, и то напълно
Не са в npb.jp, не са в KBO. Те са под sportId=17 и там всичко работи.
Измерено на 19.08.2026 (извън сезона им, върху миналата зима):

    sportId=17  2025-12-05..10 → 81 мача, с резултати
    sportId=17  2026-01-05..10 → 47 мача, с резултати

    leagueId  лига                                       сезон 2026
      131     Liga de Beisbol Dominicano   (Доминикана)   preseason
      135     Liga Venezuela Beisbol Prof. (Венецуела)    preseason
      132     Liga Mexicana del Pacifico   (Мексико)      preseason
      133     Liga Roberto Clemente        (Пуерто Рико)  preseason
      162     Caribbean Series             (Карибска)     preseason
      595     Australian Baseball League   (Австралия)    preseason
      119     Arizona Fall League          (САЩ)          preseason

„preseason" значи: сезонът е заведен, мачовете още не са пуснати. Ноември ще
се напълнят сами — кодът вече ги чете, не се пипа нищо.

ЦЕНАТА В ЗАЯВКИ (измерено, не оценено — вж. --zhivo)
  NPB   1 на календарен месец, кеширана
  KBO   1 на календарен месец, кеширана
  зима  1 на извикване (statsapi приема цял диапазон наведнъж)
  цена  1 наша (показалецът) + 1 на pinnacle.py (цените), и двете кеширани
  ОБЩО за пълно пускане на --zhivo: 9 наши + 1 на pinnacle.py

ИЗМЕРЕНО НА 19.08.2026, 11:01 UTC
  срещи за 10 дни напред          97   (NPB 52 · KBO 45)
  завършени мача в двата месеца  365   с точки за двете страни
  днешни срещи с цена             10 от 11  (91%)
  от тях: всеки мач, който Pinnacle ИЗОБЩО показва, се разпознава —
          10 от 10, тоест съвпадението по име е 100%. Единайсетият
          (日本ハム–ソフトバンク) беше вече изигран и Pinnacle го е свалил.

⚠️ КАКВО НЕ Е ПРОВЕРЕНО И НЕ БИВА ДА СЕ ТВЪРДИ
Цените по-горе са ЖИВИ, не предмачови. В 11:01 UTC всичките азиатски мачове
вече течаха (преднина −1.0 до −2.3 часа), затова 1.02 / 15.84 е цена на мач
в осма част, не на мач преди началото. За сравнение МЛБ в същия миг имаше
преднина от +5.5 до +13.6 часа. Тоест: че Pinnacle пуска ПРЕДМАЧОВА линия за
NPB и KBO със същата преднина е ОЧАКВАНЕ, не измерване. Мери се с пускане
преди 05:00 UTC — азиатските мачове почват между 05:00 и 10:00 UTC.

  python azia.py --selftest   — проверките, БЕЗ мрежа
  python azia.py --zhivo      — истинско питане, с числа
"""
import io
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

NPB_URL = "https://npb.jp/games/%d/schedule_%02d_detail.html"
KBO_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList"
KBO_REF = "https://www.koreabaseball.com/Schedule/Schedule.aspx"
STATSAPI = "https://statsapi.mlb.com/api/v1/schedule"

TIMEOUT = int((os.environ.get("AZIA_TIMEOUT") or "25").strip() or 25)

# И Токио, и Сеул са UTC+9 и НЯМАТ лятно време. Затова една константа стига;
# ако някога въведат лятно време, това място ще е лъжата.
IZTOK = timezone(timedelta(hours=9))

# Зимните лиги под sportId=17. Числата са проверени на живо, не преписани.
ZIMNI_LIGI = {
    131: "Доминиканска лига",
    135: "Венецуелска лига",
    132: "Мексиканска тихоокеанска лига",
    133: "Пуерториканска лига",
    162: "Карибска серия",
    595: "Австралийска лига",
    119: "Аризонска есенна лига",
}

# Японското кратко име (както npb.jp го пише в таблицата) -> името у Pinnacle.
#
# ЗАЩО пълната форма, а не късата: Pinnacle пише мачовете с пълното име
# („Hiroshima Toyo Carp"), а фючърсите с късото („Hiroshima Carp"). Търсачката
# в pinnacle.py има правило „едното се съдържа в другото", тоест пълното име
# хваща и двете, а късото — само едното. Значи пълното е по-евтиният избор.
NPB_IMENA = {
    "巨人": "Yomiuri Giants",
    "DeNA": "Yokohama Bay Stars",
    "阪神": "Hanshin Tigers",
    "広島": "Hiroshima Toyo Carp",
    "中日": "Chunichi Dragons",
    "ヤクルト": "Tokyo Yakult Swallows",
    "ソフトバンク": "Fukuoka Softbank Hawks",
    "日本ハム": "Hokkaido Nippon Ham Fighters",
    "ロッテ": "Chiba Lotte Marines",
    "楽天": "Tohoku Rakuten Golden Eagles",
    "西武": "Saitama Seibu Lions",
    "オリックス": "Orix Buffaloes",
}

# Корейското кратко име -> името у Pinnacle. Латинските (LG, KT, KIA, SSG, NC)
# идват от източника вече на латиница; кирилица/хангъл не влиза в търсенето.
KBO_IMENA = {
    "LG": "LG Twins",
    "두산": "Doosan Bears",
    "삼성": "Samsung Lions",
    "롯데": "Lotte Giants",
    "한화": "Hanwha Eagles",
    "KT": "KT Wiz",
    "KIA": "Kia Tigers",
    "NC": "NC Dinos",
    "SSG": "SSG Landers",
    "키움": "Kiwoom Heroes",
}

_kesh = {}
_broi = [0]
_ssl_padna = [False]


def broi_zayavki():
    """Колко заявки е направил модулът в това пускане.

    ЗАЩО: „евтино е" е мнение. Числото е проверка.
    """
    return _broi[0]


def _vzemi(url, data=None, headers=None):
    """Сурови байтове от адрес, с брояч на заявките.

    ЗАЩО отделно от urlopen: всяко пускане трябва да може да каже колко
    заявки е струвало, а и SSL-отстъплението за npb.jp живее на едно място.
    """
    _broi[0] += 1
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT).read()
    except urllib.error.URLError as e:
        # Само за счупена ВЕРИГА НА ДОВЕРИЕ и само за публична страница без
        # вход. Всяка друга грешка минава нагоре непокътната.
        if not isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            raise
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        _ssl_padna[0] = True
        _broi[0] += 1
        return urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx).read()


def ssl_otstapleno():
    """Ползван ли е непроверен SSL в това пускане.

    ЗАЩО: понижаване на защитата, което не се вижда, се превръща в навик.
    """
    return _ssl_padna[0]


def _utc(godina, mesec, den, chas, minuta):
    """Местен азиатски час -> UTC низ. И Токио, и Сеул са UTC+9 без лятно време."""
    t = datetime(godina, mesec, den, chas, minuta, tzinfo=IZTOK)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cifra(s):
    """Числото в парче HTML, или None. ЗАЩО: незапочнал мач дава `&nbsp;`."""
    t = re.sub(r"<[^>]+>", "", str(s or "")).replace("\xa0", " ").strip()
    return int(t) if re.fullmatch(r"\d+", t) else None


# Буквеният код на всеки отбор във връзките /scores/ГГГГ/ММДД/дом-гост-N/.
# НЕ е преписан отникъде: изведен е от 15 съвпадения на отбор върху августовската
# таблица, всичките единодушни (l и m имат по 14 — играли са с мач по-малко).
NPB_KOD = {
    "db": "DeNA", "g": "巨人", "t": "阪神", "s": "ヤクルト",
    "c": "広島", "d": "中日", "f": "日本ハム", "h": "ソフトバンク",
    "e": "楽天", "m": "ロッテ", "l": "西武", "b": "オリックス",
}
_NPB_OBRATNO = {v: k for k, v in NPB_KOD.items()}


def _npb_zaglavka(html):
    """{(ММДД, код_дом, код_гост): (точки_дом, точки_гост)} от лентата най-горе.

    🔴 ДЕФЕКТ №8, видян само защото сравних с Pinnacle: месечната таблица
    НЕ пуска днешния резултат веднага. На 19.08 в 10:59 UTC мачът
    日本ハム–ソフトバンク вече беше свършил 8-7 („試合終了" в лентата), но
    редът в таблицата още стоеше с `&nbsp;`. Тоест rezultat() за днешните
    мачове щеше да мълчи с часове.
    Лентата в СЪЩАТА страница го знае веднага — значи поправката е безплатна:
    нула нови заявки, само още едно четене на вече свалените байтове.
    """
    izlaz = {}
    glava = html[:html.find("</header>")] if "</header>" in html else html[:20000]
    for kutiya in re.findall(r'<div class="score_box">.*?</a>', glava, re.S):
        vr = re.search(r'href="/scores/\d{4}/(\d{4})/([a-z]+)-([a-z]+)-\d+/"', kutiya)
        rez = re.search(r'class="score">\s*(\d+)\s*-\s*(\d+)\s*<', kutiya)
        sast = re.search(r'class="state">(.*?)</div>', kutiya, re.S)
        # „試合終了" = мачът е свършил. Без него числото е ТЕКУЩО, не крайно —
        # точно капанът, който KBO ни постави с онези 0-0.
        if not (vr and rez and sast and "試合終了" in sast.group(1)):
            continue
        izlaz[(vr.group(1), vr.group(2), vr.group(3))] = (int(rez.group(1)),
                                                          int(rez.group(2)))
    return izlaz


def parse_npb(html, godina, mesec):
    """HTML на месечната таблица на npb.jp -> списък мачове.

    ЗАЩО е отделна от мрежата: селфтестът трябва да закотви реда на страните
    (първият е ДОМАКИН) без да пита никого.
    """
    igri = []
    tekushta = None
    zaglavka = _npb_zaglavka(html)
    for parche in re.split(r"<tr", html):
        m = re.search(r'id="date(\d{2})(\d{2})"', parche)
        if m:
            tekushta = (int(m.group(1)), int(m.group(2)))
        t1 = re.search(r'class="team1">([^<]*)<', parche)
        t2 = re.search(r'class="team2">([^<]*)<', parche)
        if not (t1 and t2 and tekushta):
            continue
        mm, dd = tekushta
        chas = re.search(r'class="time">(\d{1,2}):(\d{2})<', parche)
        h, mi = (int(chas.group(1)), int(chas.group(2))) if chas else (18, 0)
        s1 = _cifra((re.search(r'class="score1">(.*?)</div>', parche, re.S) or [None, ""])[1])
        s2 = _cifra((re.search(r'class="score2">(.*?)</div>', parche, re.S) or [None, ""])[1])
        myasto = re.search(r'class="place">([^<]*)<', parche)
        vrazka = re.search(r'href="(/scores/\d{4}/\d{4}/[^"]+)"', parche)
        # npb.jp обвива резултата във връзка към протокола ЕДВА след края —
        # текущият мач стои с `&nbsp;` в тази таблица. Изискваме и връзката,
        # за да не зависим само от това, че цифра значи „свършил".
        priklyuchil = bool(vrazka) and s1 is not None and s2 is not None
        # 🔴 ПЪРВИЯТ Е ДОМАКИН. Свидетелят е стадионът: „巨人 7-8 DeNA" се
        # играе на 東京ドーム, който е домът на 巨人.
        dom_kratko, gost_kratko = t1.group(1).strip(), t2.group(1).strip()
        # Днешният завършил мач го знае само лентата — таблицата изостава.
        if not priklyuchil:
            ot_lentata = zaglavka.get(("%02d%02d" % (mm, dd),
                                       _NPB_OBRATNO.get(dom_kratko, ""),
                                       _NPB_OBRATNO.get(gost_kratko, "")))
            if ot_lentata:
                s1, s2 = ot_lentata
                priklyuchil = True
        igri.append({
            "sport": "baseball",
            "liga": "NPB",
            "liga_bg": "Япония NPB",
            "dom": NPB_IMENA.get(dom_kratko, dom_kratko),
            "gost": NPB_IMENA.get(gost_kratko, gost_kratko),
            "dom_rod": dom_kratko,
            "gost_rod": gost_kratko,
            "start": _utc(godina, mm, dd, h, mi),
            "myasto": (myasto.group(1).strip() if myasto else ""),
            "tochki_dom": s1 if priklyuchil else None,
            "tochki_gost": s2 if priklyuchil else None,
            "gotov": priklyuchil,
            "id": (vrazka.group(1).strip("/").replace("/", "-") if vrazka
                   else "npb-%04d%02d%02d-%s-%s" % (godina, mm, dd, dom_kratko, gost_kratko)),
        })
    return igri


def parse_kbo(payload, godina):
    """JSON от GetScheduleList -> списък мачове.

    ЗАЩО е отделна от мрежата: тук живее ОБРАТНИЯТ ред на страните и той
    трябва да се държи от тест, а не от памет.
    """
    igri = []
    tekushta = None
    for red in (payload.get("rows") or []):
        kletki = red.get("row") or []
        po_klas = {}
        for k in kletki:
            kl = k.get("Class")
            if kl and kl not in po_klas:
                po_klas[kl] = k.get("Text") or ""
        if "day" in po_klas:
            d = re.search(r"(\d{2})\.(\d{2})", po_klas["day"])
            if d:
                tekushta = (int(d.group(1)), int(d.group(2)))
        if not tekushta or "play" not in po_klas:
            continue
        igra = po_klas["play"]
        imena = re.findall(r"<span[^>]*>([^<0-9][^<]*)</span>", igra)
        imena = [i.strip() for i in imena if i.strip() and i.strip() != "vs"]
        if len(imena) < 2:
            continue
        rez = re.findall(r'<span class="(?:win|lose|same)">(\d+)</span>', igra)
        # 🔴 ДЕФЕКТ №4, хванат чак от живото пускане: „0 vs 0" НЕ значи завършил.
        # Мач, който тече в момента, се пише със същите <span class="same">0</span>
        # като истинско равенство. Първото живо пускане обяви 3 текущи мача за
        # завършени с 0-0 — тоест 3 фалшиви резултата щяха да влязат в модела.
        # Верният свидетел е клетката „relay": section=REVIEW се появява само
        # след края; преди старта стои START_PIT; докато тече — празно.
        relay = po_klas.get("relay", "")
        priklyuchil = "section=REVIEW" in relay
        chas = re.search(r"(\d{1,2}):(\d{2})", po_klas.get("time", ""))
        h, mi = (int(chas.group(1)), int(chas.group(2))) if chas else (18, 30)
        mm, dd = tekushta
        opashka = [(k.get("Text") or "").strip() for k in kletki]
        myasto = opashka[-2] if len(opashka) >= 2 else ""
        beleg = opashka[-1] if opashka else ""
        # 🔴 ПЪРВИЯТ Е ГОСТ — обратно на NPB. Свидетелят пак е стадионът:
        # „한화 4 vs 7 KT" се играе на 수원, който е домът на KT.
        gost_kratko, dom_kratko = imena[0], imena[1]
        otmenen = "취소" in beleg or "연기" in beleg
        nomer = re.search(r"gameId=(\w+)", relay)
        igri.append({
            "sport": "baseball",
            "liga": "KBO",
            "liga_bg": "Корея KBO",
            "dom": KBO_IMENA.get(dom_kratko, dom_kratko),
            "gost": KBO_IMENA.get(gost_kratko, gost_kratko),
            "dom_rod": dom_kratko,
            "gost_rod": gost_kratko,
            "start": _utc(godina, mm, dd, h, mi),
            "myasto": myasto,
            "tochki_dom": int(rez[1]) if (priklyuchil and len(rez) == 2) else None,
            "tochki_gost": int(rez[0]) if (priklyuchil and len(rez) == 2) else None,
            "gotov": priklyuchil and len(rez) == 2,
            "teche": bool(rez) and not priklyuchil and not otmenen,
            "otmenen": otmenen,
            "id": ("kbo-" + nomer.group(1)) if nomer else
                  ("kbo-%04d%02d%02d-%s-%s" % (godina, mm, dd, gost_kratko, dom_kratko)),
        })
    return igri


def _npb_mesec(godina, mesec):
    """Мачовете на NPB за един календарен месец. Кеширано."""
    kl = ("npb", godina, mesec)
    if kl in _kesh:
        return _kesh[kl]
    # 🔴 КЕШИРА СЕ САМО УСПЕХ (05.09.2026). Дотук `except` даваше празен
    # списък и той влизаше в кеша — тоест едно кихване на мрежата изтриваше
    # месеца за ЦЕЛИЯ рън. Измерено живо: 138 мача → 0, и мрежата не се пита
    # повторно (заявки остават 1 на три викания).
    #
    # 🔴 ПРАЗНО ОТ УСПЕХ СЕ КЕШИРА: месец без мачове (междусезоние) е
    # честна нула и не бива да струва заявка всеки път. Разликата е дали е
    # хвърлено изключение, не колко дълъг е списъкът.
    try:
        html = _vzemi(NPB_URL % (godina, mesec)).decode("utf-8", "replace")
        igri = parse_npb(html, godina, mesec)
    except Exception:                                        # noqa: BLE001
        return []
    _kesh[kl] = igri
    return igri


def _kbo_mesec(godina, mesec):
    """Мачовете на KBO за един календарен месец. Кеширано.

    ЗАЩО проверява дали тялото е JSON: без X-Requested-With сървърът връща
    HTTP 200 с HTML-грешка. Мълчаливият провал е по-скъп от шумния.
    """
    kl = ("kbo", godina, mesec)
    if kl in _kesh:
        return _kesh[kl]
    telo = urllib.parse.urlencode({
        "leId": 1, "srIdList": "0,9,6",
        "seasonId": godina, "gameMonth": "%02d" % mesec, "teamId": "",
    }).encode()
    glavi = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",   # 🔴 без този ред: 406
        "Referer": KBO_REF,
    }
    # 🔴 КЕШИРА СЕ САМО УСПЕХ — виж обяснението при `_npb_mesec`.
    try:
        suro = _vzemi(KBO_URL, data=telo, headers=glavi).decode("utf-8", "replace").lstrip("﻿").strip()
        if not suro.startswith("{"):
            raise ValueError("KBO върна не-JSON (%d байта) — липсва X-Requested-With?" % len(suro))
        igri = parse_kbo(json.loads(suro), godina)
    except Exception:                                        # noqa: BLE001
        return []
    _kesh[kl] = igri
    return igri


def _mesetsi(ot, do):
    """Кои (година, месец) двойки покриват периода. ЗАЩО: месецът е единицата
    на двата източника, тоест заявките се броят в месеци, не в дни."""
    # Часовият пояс се маха: сравняваме КАЛЕНДАРНИ месеци, а смесването на
    # naive и aware дати гърми — и гръмна на първото живо пускане.
    do = datetime(do.year, do.month, 1)
    vidyani, t = [], datetime(ot.year, ot.month, 1)
    while t <= do:
        if (t.year, t.month) not in vidyani:
            vidyani.append((t.year, t.month))
        t = datetime(t.year + (t.month == 12), t.month % 12 + 1, 1)
    return vidyani


def srechti(now=None, dni=3, ot_sega=True):
    """Мачовете в NPB и KBO от `now` за `dni` дни напред.

    ЗАЩО подписът е (now, dni): същият, който predictor.py вече ползва за
    останалите спортове, за да може да се включи без нов слой.
    ЗАЩО има ot_sega: с True се вадят само още неиграните (това иска картата);
    с False влиза и вече започналото ДНЕС — иначе покритието с цена не може да
    се измери честно, понеже Pinnacle държи линия точно за днешния ден.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    kray = now + timedelta(days=dni)
    ot = now if ot_sega else now.replace(hour=0, minute=0, second=0, microsecond=0)
    izlaz = []
    for g, m in _mesetsi(ot, kray):
        izlaz.extend(_npb_mesec(g, m))
        izlaz.extend(_kbo_mesec(g, m))
    vut = []
    for i in izlaz:
        t = datetime.strptime(i["start"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if ot <= t <= kray:
            vut.append(i)
    return sorted(vut, key=lambda x: x["start"])


def rezultat(mach):
    """Крайният резултат на един мач: (точки_дом, точки_гост) или (None, None).

    ЗАЩО приема целия мач, а не номер: и двата източника носят резултата в
    същия ред, от който е дошла срещата — втора заявка не е нужна.
    """
    if isinstance(mach, dict) and mach.get("gotov"):
        return (mach.get("tochki_dom"), mach.get("tochki_gost"))
    if not isinstance(mach, dict):
        return (None, None)
    t = datetime.strptime(mach["start"], "%Y-%m-%dT%H:%M:%SZ")
    zareden = (_npb_mesec(t.year, t.month) if mach.get("liga") == "NPB"
               else _kbo_mesec(t.year, t.month))
    for i in zareden:
        if i["id"] == mach.get("id") and i.get("gotov"):
            return (i["tochki_dom"], i["tochki_gost"])
    return (None, None)


def istoriya(otbor, now=None, broy=10):
    """Последните завършени мачове на отбор, с точки ЗА и ПРОТИВ.

    ЗАЩО съществува: моделът се храни от форма, не от имена. Взима се от вече
    свалените месеци, тоест обикновено струва НУЛА нови заявки.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    tarsen = str(otbor or "").lower()
    minal = datetime(now.year, now.month, 1) - timedelta(days=1)
    vsички = []
    for g, m in ((minal.year, minal.month), (now.year, now.month)):
        vsички.extend(_npb_mesec(g, m))
        vsички.extend(_kbo_mesec(g, m))
    red = []
    for i in vsички:
        if not i.get("gotov"):
            continue
        imena = [str(i.get(k, "")).lower() for k in ("dom", "gost", "dom_rod", "gost_rod")]
        if not any(tarsen and (tarsen in n or n in tarsen) for n in imena if n):
            continue
        u_doma = tarsen in (i["dom"] or "").lower() or tarsen in (i["dom_rod"] or "").lower()
        za = i["tochki_dom"] if u_doma else i["tochki_gost"]
        protiv = i["tochki_gost"] if u_doma else i["tochki_dom"]
        red.append({
            "start": i["start"], "liga": i["liga"], "u_doma": u_doma,
            "protivnik": i["gost"] if u_doma else i["dom"],
            "za": za, "protiv": protiv, "pobeda": za > protiv,
        })
    return sorted(red, key=lambda x: x["start"], reverse=True)[:broy]


def zimni(now=None, dni=3):
    """Мачовете в зимните лиги (Доминикана, Венецуела, Мексико, Пуерто Рико…).

    ЗАЩО е тук, а не в отделен файл: те са същият спорт и същата дупка в
    покритието — просто statsapi ги дава наготово, за разлика от Азия.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    kray = now + timedelta(days=dni)
    # 🔴 ДЕФЕКТ №5, също от живото пускане: БЕЗ hydrate=team отговорът НЯМА
    # leagueId и всичките 81 мача се сляха в една безименна „Зимна лига".
    # hydrate е безплатен — същата заявка, само по-пълна.
    u = "%s?sportId=17&hydrate=team&startDate=%s&endDate=%s" % (
        STATSAPI, now.strftime("%Y-%m-%d"), kray.strftime("%Y-%m-%d"))
    try:
        d = json.loads(_vzemi(u).decode("utf-8", "replace"))
    except Exception:
        return []
    izlaz = []
    for den in d.get("dates", []):
        for g in den.get("games", []):
            lid = ((g.get("teams", {}).get("home", {}).get("team", {}) or {}).get("league", {}) or {}).get("id")
            dom = g["teams"]["home"]
            gost = g["teams"]["away"]
            gotov = str(g.get("status", {}).get("abstractGameState", "")) == "Final"
            izlaz.append({
                "sport": "baseball",
                "liga": "WIN%s" % (lid or ""),
                "liga_bg": ZIMNI_LIGI.get(lid, "Зимна лига"),
                "dom": dom["team"]["name"],
                "gost": gost["team"]["name"],
                "start": g.get("gameDate"),
                "tochki_dom": dom.get("score") if gotov else None,
                "tochki_gost": gost.get("score") if gotov else None,
                "gotov": gotov,
                "id": "win-%s" % g.get("gamePk"),
            })
    return sorted(izlaz, key=lambda x: x["start"] or "")


def _norm(s):
    """Име, сведено до сравнимо. Същото правило като в pinnacle.py."""
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def _pin_machove():
    """{номер: (дом, гост, лига)} за бейзбола у Pinnacle — БЕЗ сляпото петно.

    🔴 ДЕФЕКТ №7, И ТОЙ Е В ЧУЖД ФАЙЛ: pinnacle.machove() изхвърля всеки
    мач с parentId, защото при тениса parentId значи „подмач" (сет, гейм).
    За NPB и KBO обаче Pinnacle слага parentId на САМИЯ мач, а посоченият
    родител дори не е в отговора. Измерено на 19.08.2026 върху /sports/3:

        MLB          13 мача, ВСИЧКИТЕ без parentId
        KBO           5 мача, ВСИЧКИТЕ с parentId  ← изхвърлят се
        NPB           5 мача, ВСИЧКИТЕ с parentId  ← изхвърлят се
        Chinese Taipei 2 мача, без parentId

    Тоест pinnacle.py е 100% сляп точно за двете лиги, заради които този файл
    съществува. Верният разделител не е parentId, а `units`: „Regular" и
    „Sets" са цели мачове, а „Games", „Corners", „Bookings" са подпазари.

    Затова тук държим СОБСТВЕН показалец — една заявка — и азиатският бейзбол
    работи ВЕДНАГА, без да се пипа чужд файл. Патчът за pinnacle.py е описан в
    отчета; докато не влезе, този показалец е изходът.
    """
    if "pin" in _kesh:
        return _kesh["pin"]
    out = {}
    try:
        d = json.loads(_vzemi("https://guest.api.arcadia.pinnacle.com/0.1"
                              "/sports/3/matchups",
                              headers={"Accept": "application/json"}))
    except Exception:
        d = []
    for x in (d or []):
        if not isinstance(x, dict) or x.get("type") != "matchup":
            continue
        # Разделителят е units, НЕ parentId. Тук е цялата поправка.
        if x.get("units") not in ("Regular", "Sets"):
            continue
        dom = gost = None
        for p in (x.get("participants") or []):
            if str(p.get("alignment")) == "home":
                dom = p.get("name")
            elif str(p.get("alignment")) == "away":
                gost = p.get("name")
        if dom and gost:
            out[str(x.get("id"))] = (str(dom), str(gost),
                                     str((x.get("league") or {}).get("name") or ""))
    _kesh["pin"] = out
    return out


def s_ceni(mach_ove, ceni=None):
    """Слага цена от Pinnacle на всеки мач; връща (списък, брой_с_цена).

    ЗАЩО не вика pinnacle.py отвътре в srechti: срещите трябва да се вадят и
    когато пазарът мълчи. Цената е добавка, не условие.
    ЗАЩО показалецът е наш, а цените — техни: сляпото петно е само в
    machove(); pazari() не филтрира по parentId, тоест цените за азиатските
    мачове ВЕЧЕ са в отговора му и втора заявка не е нужна.
    """
    # `ceni` се подава наготово само от селфтеста — той няма право на мрежа.
    if ceni is None:
        try:
            import pinnacle
            ceni = pinnacle.pazari("baseball")
        except Exception:
            ceni = {}
    pm = _pin_machove()
    s_cena = 0
    for m in mach_ove:
        nd, ng = _norm(m["dom"]), _norm(m["gost"])
        d = g = None
        for mid, (a, b, _lg) in pm.items():
            na, nb = _norm(a), _norm(b)
            pryako = (nd in na or na in nd) and (ng in nb or nb in ng)
            obratno = (nd in nb or nb in nd) and (ng in na or na in ng)
            if not (pryako or obratno):
                continue
            c = ceni.get(mid)
            if not c:
                continue
            # 🔴 Страните се връщат по НАШАТА уговорка. Ако Pinnacle държи
            # мача обърнат, цените се разменят обратно.
            d, g = (c[0], c[1]) if pryako else (c[1], c[0])
            break
        m["cena_dom"], m["cena_gost"] = d, g
        if d and g:
            s_cena += 1
    return (mach_ove, s_cena)


# ---------------------------------------------------------------- ПРОВЕРКИ --

# Истински откъси, свалени на 19.08.2026. Не са измислени: пазят точния ред на
# страните и точния стадион, който го доказва.
PROBA_NPB = """
<header>
 <div class="score_box"><a href="/scores/2026/0801/f-h-19/"><div>
   <div class="score">8-7</div>
   <div class="state">（エスコンＦ）試合終了</div></div></a></div>
 <div class="score_box"><a href="/scores/2026/0801/t-s-17/"><div>
   <div class="score">3-1</div>
   <div class="state">（京セラD大阪）7回表</div></div></a></div>
</header>
<tr id="date0801" class=""> <th class="saturday" rowspan="6">8/1</th>
 <td> <div class="team1">巨人</div> <a href="/scores/2026/0801/g-db-15/">
 <div class="score1">7</div> <div class="state">-</div> <div class="score2">8</div>
 </a> <div class="team2">DeNA</div> </td>
 <td> <div class="place">東京ドーム</div> <div class="time">18:00</div> </td></tr>
<tr class=""> <td> <div class="team1">阪神</div>
 <div class="score1">&nbsp;</div> <div class="state">-</div> <div class="score2">&nbsp;</div>
 <div class="team2">ヤクルト</div> </td>
 <td> <div class="place">甲子園</div> <div class="time">14:00</div> </td></tr>
<tr class=""> <td> <div class="team1">日本ハム</div>
 <div class="score1">&nbsp;</div> <div class="state">-</div> <div class="score2">&nbsp;</div>
 <div class="team2">ソフトバンク</div> </td>
 <td> <div class="place">エスコンＦ</div> <div class="time">18:00</div> </td></tr>
"""

PROBA_KBO = {"rows": [
    {"row": [
        {"Text": "08.01(토)", "Class": "day"},
        {"Text": "<b>18:00</b>", "Class": "time"},
        {"Text": "<span>한화</span><em><span class=\"lose\">4</span>"
                 "<span>vs</span><span class=\"win\">7</span></em><span>KT</span>",
         "Class": "play"},
        {"Text": "<a href='/Schedule/GameCenter/Main.aspx?gameDate=20260801&"
                 "gameId=20260801HHKT0&section=REVIEW'>리뷰</a>", "Class": "relay"},
        {"Text": "KN-T", "Class": None},
        {"Text": "", "Class": None}, {"Text": "수원", "Class": None},
        {"Text": "-", "Class": None}]},
    {"row": [
        {"Text": "<b>18:00</b>", "Class": "time"},
        {"Text": "<span>삼성</span><em><span>vs</span></em>"
                 "<span>롯데</span>", "Class": "play"},
        {"Text": "", "Class": "relay"}, {"Text": "MS-T", "Class": None},
        {"Text": "", "Class": None}, {"Text": "사직", "Class": None},
        {"Text": "폭염취소", "Class": None}]},
    # ТЕКУЩ мач, свален на 19.08.2026 в 10:52 UTC. Изглежда точно като
    # завършило равенство 0-0 — това е капанът от дефект №4.
    {"row": [
        {"Text": "08.19(수)", "Class": "day"},
        {"Text": "<b>19:00</b>", "Class": "time"},
        {"Text": "<span>KT</span><em><span class=\"same\">0</span>"
                 "<span>vs</span><span class=\"same\">0</span></em><span>LG</span>",
         "Class": "play"},
        {"Text": "", "Class": "relay"}, {"Text": "SPO-T", "Class": None},
        {"Text": "", "Class": None}, {"Text": "잠실", "Class": None},
        {"Text": "-", "Class": None}]},
]}

# 🔴 ДЕФЕКТ №9, НАМЕРЕН 25.08.2026: САМАТА ПРИЧИНА ЗА ТОЗИ ФАЙЛ БЕШЕ БЕЗ ПАЗАЧ.
#
# _pin_machove() дели целите мачове от подпазарите по `units`, а НЕ по
# parentId — точно това е заобикалянето на сляпото петно в pinnacle.py и
# единствената причина azia.py да вижда цени. Проверките за s_ceni() обаче
# подпъхваха готов _kesh["pin"] и НИКОГА не минаваха през самия показалец.
# Тоест редът с `units` нямаше НИТО ЕДНА проверка.
#
# Измерено на живо ДНЕС, 25.08.2026 в 11:17 UTC, срещу /sports/3/matchups
# (471 сурови записа):
#     MLB                            12 мача, 0 от 12 с parentId
#     Nippon Professional Baseball    6 мача, 6 от 6 с parentId  ← всичките
#     Korea Professional Baseball     5 мача, 5 от 5 с parentId  ← всичките
#     pinnacle.machove() вижда от тези 11 азиатски: 0
#     pinnacle.ceni_za() за утрешен NPB мач: (None, None, None)
#
# Значи: върне ли някой филтъра на parentId (интуитивното, което И ДНЕС стои
# в pinnacle.py), azia.py губи 100% от цените МЪЛЧАЛИВО — а 37-те проверки
# оставаха зелени. Долният откъс пази ФОРМАТА на живия отговор.
PROBA_PIN = [
    # NPB: цял мач, но С parentId — записът, който pinnacle.py изхвърля.
    {"type": "matchup", "id": 1601, "units": "Regular", "parentId": 1600,
     "league": {"name": "Nippon Professional Baseball"},
     "participants": [{"name": "Hanshin Tigers", "alignment": "home"},
                      {"name": "Tokyo Yakult Swallows", "alignment": "away"}]},
    # KBO: същото, С parentId.
    {"type": "matchup", "id": 1602, "units": "Regular", "parentId": 1599,
     "league": {"name": "Korea Professional Baseball"},
     "participants": [{"name": "KT Wiz", "alignment": "home"},
                      {"name": "Hanwha Eagles", "alignment": "away"}]},
    # МЛБ: цял мач БЕЗ parentId — че показалецът не чупи работещото.
    {"type": "matchup", "id": 1603, "units": "Regular", "parentId": None,
     "league": {"name": "MLB"},
     "participants": [{"name": "Cincinnati Reds", "alignment": "home"},
                      {"name": "Cleveland Guardians", "alignment": "away"}]},
    # ПОДПАЗАР: не е мач и НЕ бива да влиза, макар да прилича.
    {"type": "matchup", "id": 1604, "units": "Games", "parentId": 1601,
     "league": {"name": "Nippon Professional Baseball"},
     "participants": [{"name": "Hanshin Tigers", "alignment": "home"},
                      {"name": "Tokyo Yakult Swallows", "alignment": "away"}]},
    # Чужд вид запис — трябва да се пренебрегне.
    {"type": "special", "id": 1605, "units": "Regular", "parentId": None,
     "league": {"name": "Nippon Professional Baseball"},
     "participants": [{"name": "Кой ще спечели", "alignment": "home"},
                      {"name": "Друг", "alignment": "away"}]},
]


def selftest():
    """Проверките без нито една заявка. Червено тук значи: не докладвай."""
    ok = []

    def p(ime, uslovie):
        ok.append((ime, bool(uslovie)))

    n = parse_npb(PROBA_NPB, 2026, 8)
    p("NPB: три мача от пробата", len(n) == 3)
    # 🔴 Дефект №8, закотвен в ДВЕТЕ посоки — точно това е капанът с пазача,
    # който гърми само в едната.
    p("NPB: лентата допълва днешния ЗАВЪРШИЛ мач (8-7)",
      n[2]["gotov"] and n[2]["tochki_dom"] == 8 and n[2]["tochki_gost"] == 7)
    p("NPB: лентата НЕ допълва ТЕКУЩ мач (3-1 в 7回表 се пренебрегва)",
      n[1]["gotov"] is False and n[1]["tochki_dom"] is None)
    # 🔴 Закотвяне на реда: стадионът е свидетелят, не паметта ми.
    p("NPB: ПЪРВИЯТ е ДОМАКИН (巨人 на 東京ドーム)",
      n[0]["dom"] == "Yomiuri Giants" and n[0]["myasto"] == "東京ドーム")
    p("NPB: гостът е вторият", n[0]["gost"] == "Yokohama Bay Stars")
    p("NPB: резултатът стои по страни (7-8)",
      n[0]["tochki_dom"] == 7 and n[0]["tochki_gost"] == 8 and n[0]["gotov"])
    p("NPB: незапочнал мач НЯМА измислен резултат",
      n[1]["tochki_dom"] is None and n[1]["gotov"] is False)
    p("NPB: 18:00 в Токио е 09:00 UTC", n[0]["start"] == "2026-08-01T09:00:00Z")
    p("NPB: 14:00 в Токио е 05:00 UTC", n[1]["start"] == "2026-08-01T05:00:00Z")
    p("NPB: имената са преведени за Pinnacle", n[1]["dom"] == "Hanshin Tigers")
    p("NPB: датата се пренася на ред без свой id",
      n[1]["start"][:10] == "2026-08-01")

    k = parse_kbo(PROBA_KBO, 2026)
    p("KBO: три мача от пробата", len(k) == 3)
    # 🔴 Дефект №4, закотвен: текущ мач НЕ Е завършил, дори да пише 0-0.
    p("KBO: ТЕКУЩ мач 0-0 НЕ се брои за завършил",
      k[2]["gotov"] is False and k[2]["teche"] is True
      and k[2]["tochki_dom"] is None and k[2]["tochki_gost"] is None)
    p("KBO: id-то идва от gameId на източника", k[0]["id"] == "kbo-20260801HHKT0")
    # 🔴 Закотвяне на ОБРАТНИЯ ред: 수원 е домът на KT, значи KT е домакин.
    p("KBO: ПЪРВИЯТ е ГОСТ (한화 гостува на KT в 수원)",
      k[0]["dom"] == "KT Wiz" and k[0]["gost"] == "Hanwha Eagles"
      and k[0]["myasto"] == "수원")
    p("KBO: резултатът следва размяната (KT 7, Hanwha 4)",
      k[0]["tochki_dom"] == 7 and k[0]["tochki_gost"] == 4)
    p("KBO: 18:00 в Сеул е 09:00 UTC", k[0]["start"] == "2026-08-01T09:00:00Z")
    p("KBO: отмененият мач е отбелязан и без резултат",
      k[1]["otmenen"] and not k[1]["gotov"] and k[1]["tochki_dom"] is None)
    p("KBO: имената са преведени за Pinnacle",
      k[1]["dom"] == "Lotte Giants" and k[1]["gost"] == "Samsung Lions")

    # Двете лиги НЕ бива да съвпадат по ред — това е целият дефект №2.
    p("Двата източника пазят РАЗЛИЧЕН ред на страните",
      parse_npb(PROBA_NPB, 2026, 8)[0]["dom_rod"] == "巨人"
      and parse_kbo(PROBA_KBO, 2026)[0]["gost_rod"] == "한화")

    p("Месеците покриват прескок на границата",
      _mesetsi(datetime(2026, 8, 30), datetime(2026, 9, 2)) == [(2026, 8), (2026, 9)])
    p("Месеците не се дублират",
      _mesetsi(datetime(2026, 8, 1), datetime(2026, 8, 9)) == [(2026, 8)])

    # Кешът се пълни ПРЕДИ rezultat(): незавършен мач кара rezultat() да иде
    # за месеца, а селфтестът няма право да пипа мрежата. Този ред е дефект,
    # който сам селфтестът хвана — първото пускане отчете 1 заявка вместо 0.
    _kesh[("npb", 2026, 8)] = n
    _kesh[("kbo", 2026, 8)] = k
    _kesh[("npb", 2026, 7)] = []
    _kesh[("kbo", 2026, 7)] = []

    p("rezultat() на готов мач", rezultat(n[0]) == (7, 8))
    p("rezultat() не гадае за незапочнал", rezultat(n[1]) == (None, None))
    p("rezultat() понася боклук", rezultat(None) == (None, None))

    h = istoriya("Yomiuri Giants", now=datetime(2026, 8, 15, tzinfo=timezone.utc))
    p("istoriya(): намира отбора у дома", len(h) == 1 and h[0]["u_doma"])
    p("istoriya(): точки ЗА/ПРОТИВ по правилната страна",
      h[0]["za"] == 7 and h[0]["protiv"] == 8 and h[0]["pobeda"] is False)
    hg = istoriya("Yokohama Bay Stars", now=datetime(2026, 8, 15, tzinfo=timezone.utc))
    p("istoriya(): същият мач, обърнат за госта",
      len(hg) == 1 and hg[0]["za"] == 8 and hg[0]["protiv"] == 7 and hg[0]["pobeda"])
    p("istoriya(): непознат отбор дава празно",
      istoriya("Няма такъв", now=datetime(2026, 8, 15, tzinfo=timezone.utc)) == [])
    p("istoriya() не струва нови заявки", broi_zayavki() == 0)
    _kesh.clear()

    # Сляпото петно на pinnacle.py, закотвено: ако някой ден го поправят,
    # този тест ще падне и ще каже, че показалецът тук вече е излишен.
    _kesh["pin"] = {"1": ("Hanshin Tigers", "Tokyo Yakult Swallows", "NPB")}
    proba = [{"dom": "Hanshin Tigers", "gost": "Tokyo Yakult Swallows"},
             {"dom": "Tokyo Yakult Swallows", "gost": "Hanshin Tigers"},
             {"dom": "Няма", "gost": "Такъв"}]
    p("s_ceni(): без цени нищо не се измисля",
      s_ceni(proba, ceni={})[1] == 0 and proba[0]["cena_dom"] is None)
    p("s_ceni(): цената сяда по НАШИТЕ страни, и в двете посоки",
      s_ceni(proba, ceni={"1": (1.80, 2.05, None)})[1] == 2
      and proba[0]["cena_dom"] == 1.80 and proba[1]["cena_dom"] == 2.05)
    p("s_ceni(): непознат мач остава без цена", proba[2]["cena_dom"] is None)
    _kesh.pop("pin", None)

    # ── ПАЗАЧ ЗА САМИЯ ПОКАЗАЛЕЦ (дефект №9, 25.08.2026) ──────────────
    # Дотук _pin_machove() не се пускаше НИТО ВЕДНЪЖ: кешът се подпъхваше.
    # Тук се подменя САМО входът от мрежата (_vzemi), тоест заявка няма, а
    # целият показалец се изпълнява наистина.
    _kesh.pop("pin", None)
    _star_vzemi = globals()["_vzemi"]
    _vikani = []

    def _lazhliv_vzemi(url, data=None, headers=None):
        _vikani.append(url)
        return json.dumps(PROBA_PIN).encode("utf-8")

    globals()["_vzemi"] = _lazhliv_vzemi
    try:
        _kesh.pop("pin", None)
        pm = _pin_machove()
        _ligi = [lg for (_d, _g, lg) in pm.values()]
        # 🔴 УБИЙЦАТА НА МУТАЦИЯТА: върне ли се филтърът на parentId, тези
        # два записа изчезват и точно тази проверка става червена.
        p("показалецът ПАЗИ мач с parentId (иначе NPB и KBO изчезват)",
          "Nippon Professional Baseball" in _ligi
          and "Korea Professional Baseball" in _ligi)
        p("показалецът ХВЪРЛЯ подпазара (units=Games не е мач)",
          len(pm) == 3 and "1604" not in pm and "1605" not in pm)
        # 🔴 БЕЗ .get() ТУК ЦЕЛИЯТ ПАКЕТ ГЪРМИ (намерено с мутация M1,
        # 25.08.2026): върне ли се филтърът на parentId, запис 1601 го няма
        # и голото pm["1601"] вдига KeyError — селфтестът пада с Traceback и
        # скрива всяка проверка след себе си. Иска се ЧЕРВЕНО, не гръм.
        _npb = pm.get("1601") or ("", "", "")
        p("показалецът чете страните по alignment, не по реда",
          _npb[0] == "Hanshin Tigers" and _npb[1] == "Tokyo Yakult Swallows")
        p("показалецът струва ЕДНА заявка и после се кешира",
          len(_vikani) == 1 and _pin_machove() is pm and len(_vikani) == 1)
        # Целият път от край до край, БЕЗ подпъхнат кеш — това е начинът,
        # по който s_ceni() работи в живото пускане.
        _dnes = [{"dom": "Hanshin Tigers", "gost": "Tokyo Yakult Swallows"},
                 {"dom": "KT Wiz", "gost": "Hanwha Eagles"}]
        _, _sc = s_ceni(_dnes, ceni={"1601": (1.80, 2.05, None),
                                     "1602": (1.55, 2.44, None)})
        p("s_ceni() стига до цена през ИСТИНСКИЯ показалец",
          _sc == 2 and _dnes[0]["cena_dom"] == 1.80
          and _dnes[1]["cena_gost"] == 2.44)
    finally:
        globals()["_vzemi"] = _star_vzemi
        _kesh.pop("pin", None)

    p("Зимните лиги са седем и имат български имена", len(ZIMNI_LIGI) == 7
      and ZIMNI_LIGI[131] == "Доминиканска лига")
    p("Всичките 12 японски отбора са преведени", len(NPB_IMENA) == 12)
    p("Всичките 10 корейски отбора са преведени", len(KBO_IMENA) == 10)
    # 🔴 КЕШЪТ НЕ ПОМНИ ПРОВАЛ (05.09.2026).
    #
    # Дотук `except` даваше празен списък и той влизаше в кеша — тоест едно
    # кихване на мрежата изтриваше месеца за ЦЕЛИЯ рън и го обявяваше като
    # «няма мачове». Измерено живо: 138 мача → 0, и мрежата НЕ се питаше
    # повторно (заявки остават 1 на три викания).
    #
    # Това беше ТРИНАЙСЕТИЯТ случай от този клас в проекта за един ден.
    _kk_star = dict(_kesh)
    _kk_vz = globals().get("_vzemi")
    _kk_broi = [0]
    try:
        _kesh.clear()

        def _kk_kapriz(url, **kw):
            """Пада ПЪРВИЯ път, после връща истинската проба. Брои виканията."""
            _kk_broi[0] += 1
            if _kk_broi[0] == 1:
                raise RuntimeError("проба: мрежата падна веднъж")
            return PROBA_NPB.encode("utf-8")

        globals()["_vzemi"] = _kk_kapriz
        _a = _npb_mesec(2026, 8)
        _b = _npb_mesec(2026, 8)
        _c = _npb_mesec(2026, 8)
        p("кешът НЕ помни провала: вторият опит пита пак",
          len(_a) == 0 and len(_b) > 0)
        p("и наистина е нова заявка", _kk_broi[0] == 2)
        p("а успехът СЕ кешира (третият не пита)",
          len(_c) == len(_b) and _kk_broi[0] == 2)
        # 🔴 ПРАЗНО ОТ УСПЕХ СЕ КЕШИРА. Месец без мачове е ЧЕСТНА нула
        # и не бива да струва заявка всеки път. Разликата е дали е хвърлено
        # изключение, не колко дълъг е списъкът.
        _kesh.clear()
        _kk_broi[0] = 0
        def _kk_prazna(url, **kw):
            """Празна, но УСПЕШНА страница. Брои — инак тестът мери себе си.
            (Първата ми версия беше lambda без брояч и проверката падна:
             асертирах «една заявка», а броячът стоеше на нула.)"""
            _kk_broi[0] += 1
            return b"<html></html>"

        globals()["_vzemi"] = _kk_prazna
        _d = _npb_mesec(2026, 8)
        _e = _npb_mesec(2026, 8)
        p("честната нула се кешира", _d == [] and _e == [] and _kk_broi[0] == 1)
    finally:
        if _kk_vz is not None:
            globals()["_vzemi"] = _kk_vz
        _kesh.clear()
        _kesh.update(_kk_star)
    p("подставката е върната", globals().get("_vzemi") is _kk_vz)

    p("Селфтестът НЕ е пипал мрежата", broi_zayavki() == 0)

    for ime, dobre in ok:
        print(("  ✅ " if dobre else "  ❌ ") + ime)
    lo = sum(1 for _, d in ok if not d)
    # Долна граница на БРОЯ: тест, който тихо е спрял да се пуска, е по-лош
    # от падащ тест.
    if len(ok) < 47:
        print("❌ Проверките са само %d — някоя е изчезнала." % len(ok))
        return 1
    print("%s %d проверки, %d червени" % ("✅" if not lo else "❌", len(ok), lo))
    return 1 if lo else 0


def zhivo():
    """Истинско питане, с числа. ЗАЩО: „работи" без изход е нищо."""
    now = datetime.now(timezone.utc)
    print("⚾ АЗИАТСКИ БЕЙЗБОЛ — живо, %s UTC" % now.strftime("%Y-%m-%d %H:%M"))

    m = srechti(now, dni=10)
    npb = [x for x in m if x["liga"] == "NPB"]
    kbo = [x for x in m if x["liga"] == "KBO"]
    print("\n📅 СРЕЩИ за 10 дни напред: %d  (NPB %d · KBO %d)"
          % (len(m), len(npb), len(kbo)))
    print("   заявки дотук: %d   непроверен SSL: %s"
          % (broi_zayavki(), "ДА (npb.jp)" if ssl_otstapleno() else "не"))
    for x in m[:6]:
        print("   %s  %-28s %-28s  %s" % (x["start"][:16], x["dom"], x["gost"], x["liga"]))

    otmeneni = [x for x in kbo if x.get("otmenen")]
    print("   отменени в KBO: %d" % len(otmeneni))

    predi = broi_zayavki()
    minali = []
    for g, mn in _mesetsi(now - timedelta(days=20), now):
        minali.extend([i for i in _npb_mesec(g, mn) if i["gotov"]])
        minali.extend([i for i in _kbo_mesec(g, mn) if i["gotov"]])
    print("\n🏁 РЕЗУЛТАТИ: %d завършени мача в свалените месеци (+%d заявки)"
          % (len(minali), broi_zayavki() - predi))
    for x in minali[-3:]:
        print("   %s  %s %d-%d %s" % (x["start"][:10], x["dom"],
                                      x["tochki_dom"], x["tochki_gost"], x["gost"]))

    predi = broi_zayavki()
    prob = (npb[0]["dom"] if npb else (kbo[0]["dom"] if kbo else "LG Twins"))
    h = istoriya(prob, now=now, broy=5)
    print("\n📈 ИСТОРИЯ на %s: %d мача (+%d заявки)"
          % (prob, len(h), broi_zayavki() - predi))
    for x in h:
        print("   %s  %s %d:%d срещу %s" % (x["start"][:10],
              "дома " if x["u_doma"] else "гости", x["za"], x["protiv"], x["protivnik"]))

    # 🔴 ДЕФЕКТ №6 — в собствената ми мярка, не в кода. Първото пускане обяви
    # „0 от 97 срещи получиха цена (0%)" и това е ЧЕСТНО число за грешния
    # въпрос. Pinnacle държи линия само за близкия ден, а srechti() изхвърля
    # вече започналото — тоест двете множества нямаше как да се пресекат.
    # Верният въпрос е: от мачовете, за които пазарът ИЗОБЩО има линия днес,
    # колко разпознаваме по име?
    predi = broi_zayavki()
    dnes = [x for x in srechti(now, dni=1, ot_sega=False)
            if x["start"][:10] == now.strftime("%Y-%m-%d")]
    _, s_c = s_ceni(dnes)
    try:
        import pinnacle
        pin = pinnacle.broi_zayavki()
    except Exception:
        pin = 0
    d_npb = [x for x in dnes if x["liga"] == "NPB"]
    d_kbo = [x for x in dnes if x["liga"] == "KBO"]
    print("\n💰 ЦЕНА ОТ ПАЗАРА (днешният ден — единственият, за който Pinnacle "
          "държи линия)")
    print("   %d от %d ДНЕШНИ срещи получиха цена (%.0f%%)"
          % (s_c, len(dnes), 100.0 * s_c / len(dnes) if dnes else 0))
    print("   NPB %d/%d · KBO %d/%d   (+%d наши заявки, %d на pinnacle.py)"
          % (sum(1 for x in d_npb if x.get("cena_dom")), len(d_npb),
             sum(1 for x in d_kbo if x.get("cena_dom")), len(d_kbo),
             broi_zayavki() - predi, pin))
    for x in dnes:
        print("   %-30s %-30s  %s / %s" % (x["dom"], x["gost"],
              x.get("cena_dom") or "—", x.get("cena_gost") or "—"))
    napred = [x for x in m if x["start"][:10] > now.strftime("%Y-%m-%d")]
    print("   за следващите дни (%d мача) пазарът още МЪЛЧИ — линията излиза "
          "в деня на мача" % len(napred))

    predi = broi_zayavki()
    z = zimni(now, dni=10)
    print("\n❄️ ЗИМНИ ЛИГИ сега: %d мача (+%d заявка)" % (len(z), broi_zayavki() - predi))
    zm = zimni(datetime(2025, 12, 5, tzinfo=timezone.utc), dni=5)
    print("   контролно за 05-10.12.2025: %d мача, %d с резултат"
          % (len(zm), sum(1 for x in zm if x["gotov"])))
    po_ligi = {}
    for x in zm:
        po_ligi[x["liga_bg"]] = po_ligi.get(x["liga_bg"], 0) + 1
    for k, v in sorted(po_ligi.items(), key=lambda t: -t[1]):
        print("      %-32s %d" % (k, v))

    print("\n🧾 ОБЩО ЗАЯВКИ: %d наши + %d на pinnacle.py" % (broi_zayavki(), pin))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass
    arg = sys.argv[1] if len(sys.argv) > 1 else "--selftest"
    sys.exit(zhivo() if arg == "--zhivo" else selftest())
