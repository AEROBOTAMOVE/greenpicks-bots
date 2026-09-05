# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ТЪРГУВАНИЯТ ТЕНИС НА МАСА 🏓💱

Един въпрос: защо 177 карти тенис на маса нямат НИТО ЕДНА пазарна цена?

═══════════════════════════════════════════════════════════════════════════
ЗАЩО СЪЩЕСТВУВА (25.08.2026)
═══════════════════════════════════════════════════════════════════════════

Не защото четенето е счупено. Защото WTT (Champions, Smash, Feeder) ПРОСТО
НЕ СЕ ТЪРГУВА на свободно четимите книги. Безплатно достъпният тенис на маса
и нашият тенис на маса са два различни спорта.

Този модул добавя ТЪРГУВАНИЯ — без да пипа WTT:
    Czech Liga Pro   (Smarkets parent_id 42932772)
    TT Elite Series  (Smarkets parent_id 44792813)
Двете играят по цял ден, всеки ден, и имат книга от два независими източника.

🔴 УКРАИНСКИТЕ ВЕРИГИ НЕ ВЛИЗАТ. Setka Cup / Ukraine Win Cup / TT Cup имат
имена, но нула събития във всичките състояния. Карта без път до присъда е
точно капанът от 04.08 — затова тук ги няма.

═══════════════════════════════════════════════════════════════════════════
ИЗМЕРЕНО НА ЖИВО ДНЕС (25.08.2026, между 17:47 и 18:05 UTC)
═══════════════════════════════════════════════════════════════════════════

СРЕЩИТЕ (Smarkets, parent_id, БЕЗ ключ, чист urllib):
    czech-liga-pro  2026-08-25 : 191 събития (129 свършили, 2 живи,
                                 42 предстоящи, 18 отменени) — 1 заявка, 0.46 с
    tt-elite-series 2026-08-25 : 304 събития (225/3/76/0)     — 1-2 заявки
    czech-liga-pro  2026-08-26 : 150 предстоящи, хоризонт до 23:30 UTC
    tt-elite-series 2026-08-26 : 305 предстоящи

ЦЕНАТА — ДВЕ КНИГИ И ТЕ СЕ ДОПЪЛВАТ, НЕ СЕ ДУБЛИРАТ:
    KAMBI  listView/table_tennis.json : HTTP 200, 92 116 байта, 0.34 с
           54 мача, 54 от 54 с „Match Odds" (100 %), хоризонт ~7 часа
           (до 2026-08-26T00:30Z). Марж ~9.85 %. ДНЕС само Czech Liga Pro.
    SMARKETS quotes                   : 22 от 22 пазара с ДВУСТРАННА книга,
           марж −0.18 % / −0.17 % / +0.12 % — тоест ЧЕСТНА цена.
           🔴 НО: 118 предстоящи днес, а книга има само за 22 = 18.6 %.
           Книгата се отваря ~55-90 мин преди мача.

Оттам и подредбата: Smarkets е ГРЪБНАКЪТ (кой играе, номер, резултат),
Kambi е ШИРОЧИНАТА на цената, Smarkets — ЧЕСТНОСТТА ѝ.

РЕЗУЛТАТЪТ (Smarkets, потвърден върху 6 свършили мача днес):
    45282424 'Jan Szotkowski vs Tadeas Zika'
        WINNER_2_WAY settled : Tadeas Zika = winner
        CORRECT_SCORE settled: 'Tadeas Zika 3 - 1' param=1-3 = winner
        → сетове домакин-гост = 1:3, отсъдено 17:45:13Z при начало 17:30Z
    param-ът е ВИНАГИ домакин-гост по реда в event.name: „3-0" значи
    домакинът бие 3:0, „0-3" — гостът. Проверено на 6 от 6.

═══════════════════════════════════════════════════════════════════════════
🔴 ПЕТТЕ КАПАНА, КОИТО ИЗМЕРИХ САМ ДНЕС
═══════════════════════════════════════════════════════════════════════════

1. pagination_last_id=0 СЕ ПРЕНЕБРЕГВА МЪЛЧАЛИВО.
       ...&pagination_last_id=0 -> HTTP 200, 200 събития, дни ['2026-07-26',
                                   '2026-07-27']  (архивът отпреди месец!)
       ...&pagination_last_id=1 -> HTTP 200, 128 събития, дни ['2026-08-25']
   Никаква грешка. Просто чужд ден. Тук стои ЕДИНИЦА и има проверка за нея.

2. include_hidden=false Е ПО ПОДРАЗБИРАНЕ И КРИЕ ОТСЪДЕНИ МАЧОВЕ.
   Днес: 126 скрити от 495. Взех 12 скрити свършили и попитах пазарите им:
   12 от 12 са `settled`. Тоест скритите СЕ ОТСЪЖДАТ — крие се резултат,
   който съществува. Всяка четвърта карта би висяла без причина.

3. 🔴 ГОДИНАТА В СКОБИ Е ЧОВЕК, НЕ УКРАСА — И ТОВА ОБОРВА ГОТОВАТА КРЪПКА.
   Препоръчаното решение махаше „(\\d{4})" от имената. Днес в Czech Liga Pro
   играят ЕДНОВРЕМЕННО:
       'Jaroslav (1964) Strnad'  и  'Jaroslav (1961) Strnad'
   Махнеш ли годината, двамата стават ЕДИН човек и резултатът на единия
   се лепва на другия. Затова СТРОГИЯТ ключ ПАЗИ годината, а хлабавият я
   маха и се ползва само когато е ЕДНОЗНАЧЕН (точно един кандидат).

4. ДЕН + ДВОЙКА ИМЕНА НЕ Е КЛЮЧ. Преброено върху днешния ден:
       czech-liga-pro : 91 от 191 мача = 47.6 % падат в споделен ключ
       tt-elite-series: 114 от 304     = 37.5 %
       ЧАС + двойка   : 0 сблъсъка в 495 мача
   Днешният ключ на бота (predictor.match_key) е ден|спорт|дом|гост — тоест
   почти половината карти биха се презаписали. ЛЕКЪТ Е БЕЗ ПИПАНЕ НА КОД:
   `extra["vb"]` вече влиза в ключа (predictor.py ред 992) и тук се пълни с
   часа. А `extra["slug"]` вече влиза в дневника (predictor.py ред 1133) —
   там слагаме НОМЕРА на Smarkets и мачването по имена отпада изцяло.

5. ОТМЕНЕНИЯТ МАЧ ИМА ПАЗАРИ В СЪСТОЯНИЕ „live", НЕ „cancelled".
   Проверено: събитие 'Jaroslav (1964) Strnad vs Jan Pleskot', state=cancelled,
   а пазарите му са [('WINNER_2_WAY','live'), ('CORRECT_SCORE','live'), ...].
   Тоест отмяната се чете от СЪБИТИЕТО, не от пазара. 18 такива днес.

═══════════════════════════════════════════════════════════════════════════
🔴 РАЗЛИКАТА „НЯМА" СРЕЩУ „НЕ МОЖАХ ДА ПИТАМ"
═══════════════════════════════════════════════════════════════════════════

Bovada днес връщаше HTTP 200 с празно тяло за ВСИЧКИ спортове, включително
за еталонни. За кода отвън „няма мачове" и „не ме пускат повече" изглеждат
еднакво. Затова тук нулата НИКОГА не се връща сама:

    ZAPUSHENO  — питах и не получих отговор, на който може да се вярва.
                 Обект, не низ (същата поука като scorer.OTLOZHEN).
    []         — питах, изворът е ЖИВ (еталонът отговори), днес няма мачове.
    OTLOZHEN   — мачът е отменен; scorer.py има готов клон за това.
    None       — още не се знае, пробвай пак.

ЕТАЛОНИТЕ са проверени днес:
    Smarkets: вчерашният архив на лигата (винаги пълен, пази се 30 дни)
              -> HTTP 200, 200 събития, дни ['2026-08-24', ...]
    Kambi   : listView/football.json -> HTTP 200, 260 събития
              listView/tennis.json   -> HTTP 200, 295 събития

═══════════════════════════════════════════════════════════════════════════
🔴 БЕЗ ИЗМИСЛЕН СЕТ-РЕЗУЛТАТ
═══════════════════════════════════════════════════════════════════════════

Когато CORRECT_SCORE липсва, а победителят се знае, изкушението е да върнеш
(3,0). НЕ. scorer.verdict() има клон за ТОТАЛ (scorer.py ред 1116-1121):
сборът hs+as_ се сравнява с линия. Измислените три сета биха отсъдили
над/под по число, което никой не е играл. Мълчанието е по-евтино от лъжата —
`rezultat()` връща `POBEDITEL_BEZ_SETOVE` (пак сентинел, не число), а който
не може да го ползва, го третира като None.

═══════════════════════════════════════════════════════════════════════════
ПЪТЯТ НАЗАД (правило 3)
═══════════════════════════════════════════════════════════════════════════

Лигите влизат през ръчка:  TT_LIGI="czech liga pro,tt elite series"
Празна стойност ги изключва НАПЪЛНО, без да се пипа ред код. Вече издадените
карти се затварят по готовия път NO_RESULT / MAX_AGE. Файлът е НОВ — махането
му връща бота точно там, където беше.

  python tt_ligi.py --selftest   — проверките, БЕЗ нито една мрежова заявка
  python tt_ligi.py --mutacii    — доказва, че проверките хапят
  python tt_ligi.py --zhivo      — истинско питане, за очи
"""
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone

SM = "https://api.smarkets.com/v3"
KAMBI = ("https://eu-offering-api.kambicdn.com/offering/v2018/ubuk/listView/"
         "%s.json?lang=en_GB&market=GB&client_id=2&channel_id=1")

# Ръчката от правило 3. Празно = лигите са изключени, кодът остава нетронат.
_RACHKA = os.environ.get("TT_LIGI", "czech liga pro,tt elite series")

# Лигите. Ключът е това, което пише в rec["league"], сведено до долен регистър.
LIGI = {
    "czech liga pro": {
        "cid": "42932772",
        "ime": "Czech Liga Pro",
        "slug": "czech-liga-pro",
        "kambi": "Czech Liga Pro",
    },
    "tt elite series": {
        "cid": "44792813",
        "ime": "TT Elite Series",
        "slug": "tt-elite-series",
        "kambi": "TT Elite Series",
    },
}

def klyuch_liga_svobodna(ime):
    """Ключ за лига, която НЕ Е в закования `LIGI`. Малки букви, без шум.

    🔴 Съществува, защото `LIGI` е закован речник с две местни лиги, а Kambi
    носи и трети турнир (WTT Contender Almaty, измерено живо 02.09.2026).
    Дотук третият падаше мълчаливо. Ключът НЕ бива да съвпадне с познат:
    познатите се разпознават по-горе и не стигат дотук, но ако някой ден
    добави лига в `LIGI` със същото име, стесняването по `liga_key` ще
    работи и за нея — затова нормализацията е същата, а не измислена нова.
    """
    s = " ".join(str(ime or "").lower().split())
    return s or "table tennis"


# Еталонният спорт на Kambi: 260 футболни и 295 тенис събития, мерено днес.
# Футболът не пада под стотици мача; нула футбол значи запушена врата.
ETALON_KAMBI = "football"

# Пазарите, които изобщо ни трябват. Едно събитие носи 60+ пазара (мерено:
# 45282429 даде WINNER_2_WAY, CORRECT_SCORE и ~58 OVER_UNDER/HANDICAP).
# Питането на всичките е 60 заявки за две числа.
PAZAR_POBEDITEL = "WINNER_2_WAY"
PAZAR_SETOVE = "CORRECT_SCORE"

# Прозорецът, в който два записа за една двойка се смятат за един и същ мач.
# Мерено: 2 двойки (TT Elite) и 64 (Czech Liga Pro) за 30 дни играят пак в
# рамките на 45 минути — тоест по-тесен прозорец не е нужен, а по-широк лъже.
PROZOREC_SEK = 45 * 60


class _Sentinel(object):
    """Сентинел, а не гол низ. „ZAPUSHENO" като текст може случайно да се
    сравни с име на отбор; обект — не може. Същата поука като scorer.OTLOZHEN
    и _NEPODADEN в будилника."""

    __slots__ = ("ime",)

    def __init__(self, ime):
        self.ime = ime

    def __repr__(self):
        return "<" + self.ime + ">"

    def __bool__(self):
        # 🔴 ЛЪЖЛИВО ПРАЗЕН НАРОЧНО. `if not fixtures():` е най-естественият
        # начин някой да го напише, а запушен извор НЕ Е празен списък.
        # Затова сентинелът е ИСТИНЕН: `if not x` не го хваща и повикващият
        # е принуден да го сравни изрично.
        return True


ZAPUSHENO = _Sentinel("ZAPUSHENO")
OTLOZHEN = _Sentinel("OTLOZHEN")
POBEDITEL_BEZ_SETOVE = _Sentinel("POBEDITEL_BEZ_SETOVE")


# ───────────────────────────────────────────────────────── МРЕЖА (един шев)
# 🔴 ЦЕЛИЯТ ИЗХОД КЪМ СВЕТА МИНАВА ПРЕЗ ЕДНА ФУНКЦИЯ. Не заради красота, а
# защото само така самопроверката може да мине по ИСТИНСКИЯ път — същия,
# който тръгва от `fixtures()` без нито един аргумент — вместо да подава
# готови речници на вътрешни сметки. Модул с 45 зелени проверки, чиято
# главна функция връща None винаги, вече е хващан в тази къща.
# 🔴 КАЗВАМЕ КАКВО УМЕЕМ ДА ЧЕТЕМ (измерено на живо на 01.09.2026).
#
# Днес тенисът на маса излезе „0 срещи“. В predictor.py календарът на WTT се
# връща с Content-Encoding: br, а модул brotli няма — тялото е нечетимо.
# Измерено срещу самия CDN, четири различни молби, същият адрес:
#     нищо не искаме (urllib праща identity) -> 200, br, 6044 байта
#     Accept-Encoding: gzip, deflate         -> 200, br, 6044 байта
#     Accept-Encoding: identity              -> 200, br, 6044 байта
#     Range: bytes=0-100000                  -> 206, br, 6044 байта
# Там молбата НЕ помага: файлът е Azure блоб (x-ms-blob-type: BlockBlob),
# записан вече сгъстен, главата е закована и Vary липсва. WTT без brotli е
# затворена врата — и това НЕ е нещо, което този модул може да поправи.
#
# ТУК обаче същото измерване излезе обратно, и то е причината за кръпката:
#     Smarkets срещи : без молба 113 124 байта · с „gzip, deflate“ 7 273 (−94%)
#     Kambi цени     : без молба  83 199 байта · с „gzip, deflate“ 6 530 (−92%)
# Затова молбата се праща. В нея НЯМА „br“ — не защото brotli е лош, а защото
# НЕ УМЕЕМ да го отворим, а глава, която не разбираме, трябва да стане
# МЪЛЧАНИЕ, не празен отговор. Виж _razsgasti.
#
# ПЪТ НАЗАД: TT_LIGI_ISKAME=identity връща точно старото питане.
ISKAME = (os.environ.get("TT_LIGI_ISKAME") or "gzip, deflate").strip()


def _razsgasti(surovo, ce):
    """Сурови байтове + глава Content-Encoding -> четими байтове.

    🔴 ХВЪРЛЯ при глава, която НЕ УМЕЕМ. Нарочно. Старият ред беше
    `if r.headers.get("Content-Encoding") == "gzip"` — точно, чувствително към
    главни букви сравнение — и всичко друго минаваше НЕПИПНАТО към json.loads.
    Измерено срещу истински сървър на 127.0.0.1 преди кръпката:
        „GZIP“    -> None (мълчание)
        „gzip, “  -> None
        „deflate“ -> None
        „br“      -> None
    Четири различни повода дават едно и също: нечетим отговор изглежда точно
    като празен ден. Тук такъв отговор гърми, _http_json връща None, а
    fixtures() го превръща в ZAPUSHENO — сентинел, който не е празен списък.
    """
    import gzip
    import zlib
    e = str(ce or "").lower().strip()
    if not e or "identity" in e:
        return surovo
    if "gzip" in e:
        return gzip.decompress(surovo)
    if "deflate" in e:
        try:
            return zlib.decompress(surovo)
        except zlib.error:              # някои сървъри пращат СУРОВ deflate
            return zlib.decompress(surovo, -zlib.MAX_WBITS)
    raise ValueError("не умея Content-Encoding: " + e[:30])


def _http_json(url, timeout=25):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"Accept-Encoding": ISKAME})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = _razsgasti(r.read(), r.headers.get("Content-Encoding"))
        return json.loads(b.decode("utf-8"))
    except Exception:                                        # noqa: BLE001
        return None


_PROBA_TYALO = {"ok": True, "n": 7}


def _proba_sgastyavane():
    """Истински сървър на 127.0.0.1 — какво ИЗЛИЗА от _http_json.

    🔴 БЕЗ ДАТА И БЕЗ МРЕЖА НАВЪН. Проверката не пита „стои ли редът в
    кода“, а вдига сървър, който отговаря с шест различни глави, и гледа
    какво се връща. Заковани дати вече са падали два пъти в тази къща —
    тук часовникът изобщо не участва.

    Връща (прочетено, премълчано, каквото сме поискали).
    """
    import gzip as _gz
    import threading
    import zlib as _zl
    from http.server import BaseHTTPRequestHandler, HTTPServer

    tyalo = json.dumps(_PROBA_TYALO).encode("utf-8")
    sluchai = {
        "/a": ("(няма)", tyalo),
        "/b": ("gzip", _gz.compress(tyalo)),
        "/c": ("GZIP", _gz.compress(tyalo)),
        "/d": ("gzip, ", _gz.compress(tyalo)),
        "/e": ("deflate", _zl.compress(tyalo)),
        "/f": ("br", b"\x1b\x0e\x00\xf8\x25\x14"),
    }
    vidyano = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            ce, telo = sluchai[self.path]
            vidyano["iskano"] = self.headers.get("Accept-Encoding") or ""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            if ce != "(няма)":
                self.send_header("Content-Encoding", ce)
            self.send_header("Content-Length", str(len(telo)))
            self.end_headers()
            self.wfile.write(telo)

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    baza = "http://127.0.0.1:" + str(srv.server_address[1])
    chete, tisho = {}, {}
    try:
        for pat, (ce, _t) in sluchai.items():
            got = _http_json(baza + pat, timeout=5)
            if got is None:
                tisho[ce] = None
            else:
                chete[ce] = got
    finally:
        srv.shutdown()
        srv.server_close()
    return chete, tisho, vidyano.get("iskano", "")


_MREZHA = [_http_json]          # списък, за да е подменяем на едно място
_KESH = {}                      # url -> (кога, отговор)
KESH_SEK = 120                  # един рън е под минута; повторно питане е хабене
_BROYACH = {"zayavki": 0, "kesh": 0}


def _json(url, kesh_sek=None):
    """Питане с кеш. Един отговор носи всички мачове — не се пита втори път."""
    sek = KESH_SEK if kesh_sek is None else kesh_sek
    sega = time.time()
    got = _KESH.get(url)
    if got is not None and sek and (sega - got[0]) < sek:
        _BROYACH["kesh"] += 1
        return got[1]
    d = _MREZHA[0](url)
    _BROYACH["zayavki"] += 1
    if d is not None:
        _KESH[url] = (sega, d)
    return d


def izchisti_kesh():
    _KESH.clear()
    _BROYACH["zayavki"] = 0
    _BROYACH["kesh"] = 0


# ───────────────────────────────────────────────────── АДРЕСИ (за мутациите)
def _url_den(cid, den, sast):
    """Един ден от една лига в едно състояние.

    🔴 pagination_last_id=1, НЕ 0. С нула Smarkets мълчаливо връща архива от
    преди месец — HTTP 200, никаква грешка, чужд ден. Измерено днес.
    🔴 include_hidden=true задължително: 126 от 495 днешни събития са скрити
    и 12 от 12 проверени скрити са ОТСЪДЕНИ.
    """
    return (SM + "/events/?parent_id=" + str(cid) + "&state=" + str(sast) +
            "&sort=start_datetime,id&limit=200&include_hidden=true"
            "&pagination_last_start_datetime=" + str(den) + "T00:00:00Z"
            "&pagination_last_id=1")


def _url_pazari(ids):
    return SM + "/events/" + ",".join(str(x) for x in ids) + "/markets/"


def _url_kontrakti(mids):
    return SM + "/markets/" + ",".join(str(x) for x in mids) + "/contracts/"


def _url_kotirovki(mids):
    return SM + "/markets/" + ",".join(str(x) for x in mids) + "/quotes/"


def _url_kambi(sport="table_tennis"):
    return KAMBI % sport


# ─────────────────────────────────────────────────────────────────── ИМЕНАТА
_GODINA = re.compile(r"\(\s*(\d{4})\s*\)")
_TITLA = re.compile(r"\b(senior|junior|jnr|snr|jr|sr)\b", re.I)


def _pochisti(ime):
    s = unicodedata.normalize("NFKD", str(ime or ""))
    return s.encode("ascii", "ignore").decode()


def klyuch_ime(ime):
    """Име -> (СТРОГ, ХЛАБАВ). И двата са НЕПОДРЕДЕНИ набори от думи.

    Наборът, а не „последната дума", защото Smarkets пише и „Kaczynski Piotr"
    (фамилията ОТПРЕД) до „Grzegorz Marud" в едно и също събитие — видяно
    днес в събитие 159890845. Сравнението по последна дума би обявило
    „Piotr" за фамилия.

    🔴 СТРОГИЯТ ПАЗИ ГОДИНАТА. 'Jaroslav (1964) Strnad' и 'Jaroslav (1961)
    Strnad' играят в един и същи ден в Czech Liga Pro — измерено днес. Махнеш
    ли годината, двамата стават един човек.
    ХЛАБАВИЯТ я маха, за да може името от друга книга (Kambi пише „Marek
    Senior Sedlak", Smarkets — „Marek Sedlak") да намери своя мач. Ползва се
    само когато сочи ЕДИН кандидат.
    """
    s = _pochisti(ime)
    god = _GODINA.findall(s)
    gol = _GODINA.sub(" ", s)
    gol = _TITLA.sub(" ", gol)
    dumi = re.sub(r"[^A-Za-z ]", " ", gol).lower().split()
    if not dumi:
        return (), ()
    hlabav = tuple(sorted(dumi))
    strog = tuple(sorted(dumi + god))
    return strog, hlabav


def dvoika(dom, gost, strogo=True):
    """Двойката като ключ. None, ако някое от имената е празно или двете
    сочат един и същ човек (тогава мачът не е мач)."""
    a = klyuch_ime(dom)[0 if strogo else 1]
    b = klyuch_ime(gost)[0 if strogo else 1]
    if not a or not b or a == b:
        return None
    return frozenset((a, b))


def _chas(iso):
    """ISO с Z -> aware datetime. None при боклук."""
    t = str(iso or "").strip()
    if not t:
        return None
    try:
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _dnes():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def liga_klyuch(ime):
    """Нашето име на лига -> ключ в LIGI. None, ако не е наша."""
    t = re.sub(r"\s+", " ", _pochisti(ime).strip().lower())
    if t in LIGI:
        return t
    for k, v in LIGI.items():
        if v["slug"] == t.replace(" ", "-") or v["kambi"].lower() == t:
            return k
    return None


def vklyucheni():
    """Кои лиги са включени според ръчката. Празна ръчка = нито една."""
    imena = [x.strip().lower() for x in str(_RACHKA or "").split(",") if x.strip()]
    return [k for k in LIGI if k in imena]


# ─────────────────────────────────────────────────── ЖИВ ЛИ Е ИЗВОРЪТ
def izvor_zhiv(broi, broi_etalon):
    """Може ли да се вярва на нулата.

    Нула наши + нула еталон -> изворът е запушен. НЕ Е отговор.
    Нула наши + жив еталон  -> честна нула, днес няма мачове.
    """
    try:
        n = int(broi)
        e = int(broi_etalon)
    except (TypeError, ValueError):
        return False
    if n > 0:
        return True
    return e > 0


def _etalon_smarkets(lk):
    """Вчерашният архив на лигата. Пази се 30 дни -> винаги пълен.
    Мерено днес: HTTP 200, 200 събития. Нула оттам = вратата е затворена."""
    vchera = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    cid = LIGI[lk]["cid"]
    d = _json(_url_den(cid, vchera, "ended"), kesh_sek=600)
    if not isinstance(d, dict):
        return 0
    return len(d.get("events") or [])


def _etalon_kambi():
    d = _json(_url_kambi(ETALON_KAMBI), kesh_sek=600)
    if not isinstance(d, dict):
        return 0
    return len(d.get("events") or [])


# ───────────────────────────────────────────────────────────── СЪБИТИЯТА
_SASTOYANIYA = ("ended", "live", "upcoming", "cancelled")


def _den_sabitiya(lk, den, sastoyania=_SASTOYANIYA):
    """Всички събития на една лига за един ден. ZAPUSHENO, ако не стигнах.

    Пагинация: `limit=200` е таван, а TT Elite дава 304 за днес — тоест без
    втората страница една трета от деня изчезва тихо.
    """
    cid = LIGI[lk]["cid"]
    out = []
    stignah = False
    for sast in sastoyania:
        url = _url_den(cid, den, sast)
        for _ in range(12):
            d = _json(url)
            if not isinstance(d, dict):
                break
            stignah = True
            sab = d.get("events") or []
            out += [e for e in sab
                    if isinstance(e, dict) and str(e.get("start_date")) == den]
            if sab and str(sab[-1].get("start_date") or "") > den:
                break
            nx = (d.get("pagination") or {}).get("next_page")
            if not nx:
                break
            url = SM + "/events/" + str(nx)
    if not stignah:
        return ZAPUSHENO
    if not out and not izvor_zhiv(0, _etalon_smarkets(lk)):
        return ZAPUSHENO
    return out


# ────────────────────────────────────────────────────────────── СРЕЩИТЕ
def fixtures(den=None, ligi=None):
    """Предстоящите срещи: начало, лига, имена. БЕЗ подадени данни работи.

    Връща списък от речници във формата на predictor.py (bucket/home/away/
    league/when/extra), за да може да влезе в пула без преводач.

    ZAPUSHENO, ако НИТО ЕДНА лига не е отговорила — това не е празен ден.
    """
    den = str(den or _dnes())[:10]
    kl = list(ligi) if ligi else vklyucheni()
    if not kl:
        return []                       # ръчката е свалена — нарочна тишина
    out = []
    zhivi = 0
    for lk in kl:
        if lk not in LIGI:
            continue
        ev = _den_sabitiya(lk, den, ("upcoming", "live"))
        if ev is ZAPUSHENO:
            continue
        zhivi += 1
        for e in ev:
            ime = str(e.get("name") or "")
            a, sep, b = ime.partition(" vs ")
            if not sep or not a.strip() or not b.strip():
                continue
            kt = _chas(e.get("start_datetime"))
            if kt is None:
                continue
            out.append({
                "bucket": "tabletennis",
                "emoji": "\U0001f3d3",
                "src": "ttligi",
                "home": a.strip(),
                "away": b.strip(),
                "league": LIGI[lk]["ime"],
                "when": kt,
                "weight": 8,
                "extra": {
                    # 🔴 НОМЕРЪТ ВЛИЗА В ДНЕВНИКА ПРЕЗ ГОТОВА ВРАТА.
                    # predictor.log_pick пише rec["slug"] = extra["slug"]
                    # (predictor.py ред 1133). Оттам rezultat() чете ПРАВО по
                    # номер и мачването по имена отпада изцяло.
                    "slug": str(e.get("id")),
                    "sm_id": str(e.get("id")),
                    # 🔴 ЧАСЪТ ВЛИЗА В КЛЮЧА ПРЕЗ ГОТОВА ВРАТА.
                    # predictor.match_key слага extra["vb"] в ключа
                    # (predictor.py ред 992). Без него 47.6 % от днешните
                    # мачове на Czech Liga Pro падат в споделен ключ.
                    "vb": kt.strftime("%H%M"),
                    "liga_key": lk,
                    "best_of": 5,       # CORRECT_SCORE е 3-0/3-1/3-2 -> 5
                    "start": kt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            })
    if not out and zhivi == 0:
        return ZAPUSHENO
    out.sort(key=lambda x: x["when"])
    return out


# ────────────────────────────────────────────────────────────────── ЦЕНАТА
def _chestni(a, b):
    """Две десетични цени -> (P(a), P(b), марж). None при боклук."""
    try:
        a = float(a)
        b = float(b)
    except (TypeError, ValueError):
        return None
    if a <= 1.0 or b <= 1.0:
        return None
    ov = 1.0 / a + 1.0 / b
    if ov <= 0:
        return None
    return (1.0 / a) / ov, (1.0 / b) / ov, ov - 1.0


def ceni_kambi():
    """Kambi: една заявка, целият списък. Речник по хлабава двойка.

    🔴 `odds` е ЦЯЛО ЧИСЛО × 1000. 1780 значи 1.78. Забравено деление
    превръща всяка цена в 1780 и всяка вероятност в 0.0006.
    🔴 Разделителят в `event.name` е „ - ", НЕ „ vs ". И в него се среща
    „Nohejl, Vaclav (2005)" — с ЗАПЕТАЯ. Не се цепи по запетая. Затова
    имената се вземат от ИЗХОДИТЕ (`outcome.label`), които днес са 108 от
    108 точно по две думи, а името на събитието се ползва само за реда.
    """
    d = _json(_url_kambi())
    if not isinstance(d, dict):
        return ZAPUSHENO
    ev = d.get("events") or []
    if not ev and not izvor_zhiv(0, _etalon_kambi()):
        return ZAPUSHENO
    ind = {}
    for it in ev:
        if not isinstance(it, dict):
            continue
        e = it.get("event") or {}
        pat = " / ".join(str(p.get("englishName") or "")
                         for p in (e.get("path") or []))
        lk = None
        for k, v in LIGI.items():
            if v["kambi"].lower() in pat.lower():
                lk = k
                break
        # 🔴 НЕПОЗНАТАТА ЛИГА ВЕЧЕ НЕ ПАДА (02.09.2026).
        #
        # Тук стоеше `if lk is None: continue`, а `LIGI` е закован речник с
        # ДВЕ местни лиги. Значи всеки турнир извън тях се хвърляше мълчаливо.
        # Измерено живо същия ден: Kambi носи ТРИ турнира по тенис на маса —
        # Czech Republic 150, TT Elite Series 135 и WTT Contender Almaty 2 —
        # и третият падаше тук. А точно WTT е спортът, в който 319 наши карти
        # имат само 49 коефициента (15%).
        #
        # Сега непознатата лига влиза с ИСТИНСКОТО си име от пътя. Известните
        # две запазват точните си ключове, за да не се счупи стесняването по
        # `liga_key` в `cena_za`. Непознат ключ там просто не стеснява — тоест
        # кандидатите остават всички за тази двойка имена, което е вярното
        # поведение, когато не знаем лигата.
        if lk is None:
            _chasti = [str(p.get("englishName") or "").strip()
                       for p in (e.get("path") or [])]
            _chasti = [c for c in _chasti if c and c.lower() != "table tennis"]
            _ime_lg = _chasti[0] if _chasti else "Table Tennis"
            lk = klyuch_liga_svobodna(_ime_lg)
            _lg_ime = _ime_lg
        else:
            _lg_ime = LIGI[lk]["ime"]
        ime = str(e.get("name") or "")
        a, sep, b = ime.partition(" - ")
        if not sep:
            continue
        for bo in (it.get("betOffers") or []):
            if not isinstance(bo, dict):
                continue
            if str((bo.get("criterion") or {}).get("label") or "") != "Match Odds":
                continue
            izh = bo.get("outcomes") or []
            if len(izh) != 2:
                continue                     # три изхода в двоен пазар = чужд пазар
            ceni = []
            for o in izh:
                try:
                    ceni.append((str(o.get("label") or ""), float(o["odds"]) / 1000.0))
                except (TypeError, ValueError, KeyError):
                    ceni = []
                    break
            if len(ceni) != 2:
                continue
            # Редът: домакинът е този, чието име стои първо в event.name.
            dk = klyuch_ime(a)[1]
            obarnat = klyuch_ime(ceni[0][0])[1] != dk
            dom = ceni[1] if obarnat else ceni[0]
            gost = ceni[0] if obarnat else ceni[1]
            dv = dvoika(dom[0], gost[0], strogo=False)
            if dv is None:
                continue
            ind.setdefault(dv, []).append({
                "dom_ime": dom[0], "gost_ime": gost[0],
                "dom": dom[1], "gost": gost[1],
                "liga": _lg_ime, "liga_key": lk,
                "start": str(e.get("start") or ""),
                "izvor": "kambi", "nomer": None,
            })
    return ind


def ceni_smarkets(den=None):
    """Smarkets: честната цена от борсата. Речник по хлабава двойка.

    Четири стъпки: събития -> пазари -> договори -> котировки.
    🔴 Котировките са речник по CONTRACT_ID, НЕ по market_id.
    🔴 КОЕФИЦИЕНТ = 10000 / price. offers[0] = с колко може да заложиш,
    bids[0] = с колко може да предложиш. ЧЕСТНАТА е средата:
    2/(1/back + 1/lay). Проверка, че формулата е вярна: маржът по средата
    излиза −0.18 % / −0.17 % / +0.12 % (мерено днес), докато само по offers
    дава +10.1 %, а само по bids −10.5 %. Тоест средата се самопроверява.
    """
    den = str(den or _dnes())[:10]
    ind = {}
    stignah = False
    for lk in vklyucheni():
        ev = _den_sabitiya(lk, den, ("upcoming", "live"))
        if ev is ZAPUSHENO:
            continue
        stignah = True
        po_id = {}
        for e in ev:
            a, sep, b = str(e.get("name") or "").partition(" vs ")
            if sep and a.strip() and b.strip():
                po_id[str(e.get("id"))] = (a.strip(), b.strip(), e, lk)
        idlist = list(po_id)
        pazari = []
        for i in range(0, len(idlist), 20):
            d = _json(_url_pazari(idlist[i:i + 20]))
            if not isinstance(d, dict):
                continue
            pazari += [m for m in (d.get("markets") or [])
                       if isinstance(m, dict)
                       and (m.get("market_type") or {}).get("name") == PAZAR_POBEDITEL]
        kon, kot = {}, {}
        for i in range(0, len(pazari), 20):
            mids = [m["id"] for m in pazari[i:i + 20]]
            d = _json(_url_kontrakti(mids))
            for x in (d or {}).get("contracts", []):
                kon.setdefault(str(x.get("market_id")), []).append(x)
            q = _json(_url_kotirovki(mids))
            if isinstance(q, dict):
                kot.update(q)
        for m in pazari:
            cs = kon.get(str(m.get("id"))) or []
            if len(cs) != 2:
                continue
            sr = {}
            for x in cs:
                q = kot.get(str(x.get("id"))) or {}
                bd = (q.get("bids") or [None])[0]
                of = (q.get("offers") or [None])[0]
                if not bd or not of:
                    sr = {}
                    break
                try:
                    back = 10000.0 / float(of["price"])
                    lay = 10000.0 / float(bd["price"])
                except (TypeError, ValueError, KeyError, ZeroDivisionError):
                    sr = {}
                    break
                if back <= 1.0 or lay <= 1.0:
                    sr = {}
                    break
                sr[str(x.get("name") or "")] = 2.0 / (1.0 / back + 1.0 / lay)
            if len(sr) != 2:
                continue
            got = po_id.get(str(m.get("event_id")))
            if not got:
                continue
            a, b, e, lk2 = got
            ak, bk = klyuch_ime(a)[1], klyuch_ime(b)[1]
            ca = cb = None
            for nm, c in sr.items():
                if klyuch_ime(nm)[1] == ak:
                    ca = c
                elif klyuch_ime(nm)[1] == bk:
                    cb = c
            if ca is None or cb is None:
                continue
            dv = dvoika(a, b, strogo=False)
            if dv is None:
                continue
            ind.setdefault(dv, []).append({
                "dom_ime": a, "gost_ime": b, "dom": ca, "gost": cb,
                "liga": LIGI[lk2]["ime"], "liga_key": lk2,
                "start": str(e.get("start_datetime") or ""),
                "izvor": "smarkets", "nomer": str(e.get("id")),
            })
    if not ind and not stignah:
        return ZAPUSHENO
    return ind


def index_ceni(den=None):
    """Двете книги в един указател. Smarkets отпред (честната цена).

    ZAPUSHENO само ако И ДВЕТЕ мълчат — една жива книга е достатъчна.
    """
    k = ceni_kambi()
    s = ceni_smarkets(den)
    if k is ZAPUSHENO and s is ZAPUSHENO:
        return ZAPUSHENO
    ind = {}
    for izvor in (s, k):
        if izvor is ZAPUSHENO or not isinstance(izvor, dict):
            continue
        for dv, red in izvor.items():
            ind.setdefault(dv, []).extend(red)
    return ind


def cena(dom, gost, liga=None, kogato=None, ind=None):
    """Цената по НАШИТЕ имена. None = няма. ZAPUSHENO = не можах да питам.

    Без подаден указател си го взима сам — тоест `cena("Erik Mares",
    "Jan Cernik")` работи от само себе си.

    🔴 ПРИ ДВА КАНДИДАТА БЕЗ ЧАС СЕ МЪЛЧИ. Една двойка играе по 2-3 пъти в
    същия ден (47.6 % от Czech Liga Pro днес). Подхвърлянето на „първия"
    лепва чужда цена на почти всяка втора карта.
    """
    if ind is None:
        ind = index_ceni()
    if ind is ZAPUSHENO:
        return ZAPUSHENO
    if not isinstance(ind, dict):
        return None
    dv = dvoika(dom, gost, strogo=False)
    if dv is None:
        return None
    kand = list(ind.get(dv) or [])
    if liga:
        lk = liga_klyuch(liga)
        if lk:
            stesneno = [r for r in kand if r.get("liga_key") == lk]
            if stesneno:
                kand = stesneno
    if not kand:
        return None
    cel = _chas(kogato)
    if len(kand) > 1:
        if cel is None:
            return None                      # без час НЕ гадаем
        with_t = [(r, _chas(r.get("start"))) for r in kand]
        with_t = [(r, t) for r, t in with_t if t is not None]
        if not with_t:
            return None
        with_t.sort(key=lambda x: abs((x[1] - cel).total_seconds()))
        if abs((with_t[0][1] - cel).total_seconds()) > PROZOREC_SEK:
            return None
        kand = [with_t[0][0]]
    elif cel is not None:
        t = _chas(kand[0].get("start"))
        if t is not None and abs((t - cel).total_seconds()) > PROZOREC_SEK:
            return None
    r = kand[0]
    nash = klyuch_ime(dom)[1]
    obarnat = klyuch_ime(r["dom_ime"])[1] != nash
    d = r["gost"] if obarnat else r["dom"]
    g = r["dom"] if obarnat else r["gost"]
    ch = _chestni(d, g)
    if ch is None:
        return None
    return {
        "dom": round(d, 4), "gost": round(g, 4),
        "p_dom": round(ch[0], 4), "p_gost": round(ch[1], 4),
        "marzh": round(ch[2], 4),
        "izvor": r["izvor"], "nomer": r["nomer"], "liga": r["liga"],
        "start": r["start"], "obarnat": bool(obarnat),
    }


# ───────────────────────────────────────────────────────────── РЕЗУЛТАТЪТ
def _setove_ot_sabitie(eid):
    """Сетовете на едно събитие по номер. Два адреса, нищо повече.

    🔴 Питат се САМО двата пазара, които ни трябват. Едно събитие носи 60+
    пазара (мерено на 45282429); питането на договорите им е 60 заявки за
    две числа.
    """
    d = _json(_url_pazari([eid]))
    if not isinstance(d, dict):
        return ZAPUSHENO
    mk = [m for m in (d.get("markets") or []) if isinstance(m, dict)]
    setove = [m for m in mk
              if (m.get("market_type") or {}).get("name") == PAZAR_SETOVE
              and m.get("state") == "settled"]
    if setove:
        c = _json(_url_kontrakti([setove[0]["id"]]))
        if not isinstance(c, dict):
            return ZAPUSHENO
        for x in (c.get("contracts") or []):
            if x.get("state_or_outcome") != "winner":
                continue
            p = str((x.get("contract_type") or {}).get("param") or "")
            if "-" not in p:
                continue
            try:
                hs, as_ = [int(z) for z in p.split("-", 1)]
            except (TypeError, ValueError):
                continue
            return (hs, as_)
        return None
    pob = [m for m in mk
           if (m.get("market_type") or {}).get("name") == PAZAR_POBEDITEL
           and m.get("state") == "settled"]
    if pob:
        # 🔴 ЗНАЕМ ПОБЕДИТЕЛЯ, НЕ ЗНАЕМ СЕТОВЕТЕ. Не се подхвърля 3-0:
        # scorer.verdict() съди тотала по СБОРА (scorer.py ред 1116-1121) и
        # измислените сетове биха отсъдили над/под по число, което никой не е
        # играл. Връща се сентинел — повикващият решава дали може да го ползва.
        return POBEDITEL_BEZ_SETOVE
    return None                              # пазарите още не са отсъдени


def pobeditel(eid):
    """Името на победителя по номер на събитие. None = още не се знае."""
    d = _json(_url_pazari([eid]))
    if not isinstance(d, dict):
        return ZAPUSHENO
    pob = [m for m in (d.get("markets") or []) if isinstance(m, dict)
           and (m.get("market_type") or {}).get("name") == PAZAR_POBEDITEL
           and m.get("state") == "settled"]
    if not pob:
        return None
    c = _json(_url_kontrakti([pob[0]["id"]]))
    if not isinstance(c, dict):
        return ZAPUSHENO
    for x in (c.get("contracts") or []):
        if x.get("state_or_outcome") == "winner":
            return str(x.get("name") or "") or None
    return None


def _nameri_sabitie(rec):
    """Записът -> събитието на Smarkets. Сентинел или None при неуспех."""
    eid = str(rec.get("slug") or rec.get("sm_id") or "").strip()
    if eid.isdigit():
        # 🔴 НОМЕРЪТ НЕ СТИГА — ТРЯБВА И ИМЕТО. CORRECT_SCORE е
        # ДОМАКИН-ГОСТ по реда в event.name; без името карта, записана
        # с обърнати страни, получава ОГЛЕДАЛНАТА присъда. Живо на
        # 25.08: 6 от 6 вчерашни мача връщаха ЕДНО И СЪЩО число за
        # двете посоки. Заявката вече се правеше заради отмяната —
        # само името се изхвърляше.
        e = {"id": eid, "state": None, "name": None, "_po_nomer": True}
        d = _json(SM + "/events/" + eid + "/")
        if isinstance(d, dict):
            sab = (d.get("events") or [None])[0]
            if isinstance(sab, dict):
                e["name"] = sab.get("name")
                e["state"] = sab.get("state")
        return e
    lk = liga_klyuch(rec.get("league"))
    if lk is None or lk not in vklyucheni():
        return None
    den = str(rec.get("day") or "")[:10]
    if not den:
        return None
    dv = dvoika(rec.get("home"), rec.get("away"), strogo=True)
    dvh = dvoika(rec.get("home"), rec.get("away"), strogo=False)
    if dv is None:
        return None
    ev = _den_sabitiya(lk, den)
    if ev is ZAPUSHENO:
        return ZAPUSHENO
    strogi, hlabavi = [], []
    for e in ev:
        a, sep, b = str(e.get("name") or "").partition(" vs ")
        if not sep:
            continue
        if dvoika(a, b, strogo=True) == dv:
            strogi.append(e)
        elif dvh is not None and dvoika(a, b, strogo=False) == dvh:
            hlabavi.append(e)
    kand = strogi
    if not kand:
        # 🔴 ХЛАБАВИЯТ КЛЮЧ САМО КОГАТО Е ЕДНОЗНАЧЕН. Той е този, който
        # изравнява 'Jaroslav (1964) Strnad' и 'Jaroslav (1961) Strnad' —
        # тоест точно там, където може да сбърка човека, се мълчи.
        if len(hlabavi) != 1:
            return None
        kand = hlabavi
    if len(kand) > 1:
        cel = _chas(rec.get("start"))
        if cel is None:
            return None                      # без час НЕ гадаем
        red = [(e, _chas(e.get("start_datetime"))) for e in kand]
        red = [(e, t) for e, t in red if t is not None]
        if not red:
            return None
        red.sort(key=lambda x: abs((x[1] - cel).total_seconds()))
        if abs((red[0][1] - cel).total_seconds()) > PROZOREC_SEK:
            return None
        kand = [red[0][0]]
    return kand[0]


def rezultat(rec):
    """Кой е спечелил, като СЕТОВЕ (домакин, гост).

        (hs, as_)             — знае се
        OTLOZHEN              — мачът е отменен; scorer.py има готов клон
        POBEDITEL_BEZ_SETOVE  — знае се кой, не се знае с колко
        ZAPUSHENO             — не можах да питам; НЕ Е „няма"
        None                  — още не се знае, пробвай пак

    Работи и само по `rec["slug"]` (номера на Smarkets), и по лига+ден+час.
    """
    if not isinstance(rec, dict):
        return None
    e = _nameri_sabitie(rec)
    if e is ZAPUSHENO:
        return ZAPUSHENO
    if not e:
        return None
    # 🔴 ОТМЯНАТА СЕ ЧЕТЕ ОТ СЪБИТИЕТО, НЕ ОТ ПАЗАРА. Проверено днес:
    # отменено събитие има пазари в състояние „live", не „cancelled".
    if e.get("state") == "cancelled":
        return OTLOZHEN
    r = _setove_ot_sabitie(e["id"])
    if r is ZAPUSHENO or r is POBEDITEL_BEZ_SETOVE:
        return r
    if not r:
        return None
    hs, as_ = r
    # Ако картата е записана с обърнати страни спрямо книгата, обръщаме.
    ime = str(e.get("name") or "")
    a, sep, b = ime.partition(" vs ")
    if sep and rec.get("home"):
        nash = klyuch_ime(rec.get("home"))[1]
        if nash and klyuch_ime(a)[1] != nash and klyuch_ime(b)[1] == nash:
            hs, as_ = as_, hs
    if max(hs, as_) < 2 or max(hs, as_) > 4 or (hs + as_) > 7:
        return None                          # боклук, не резултат
    return (hs, as_)


# ══════════════════════════════════════════════════════════════ ПРОВЕРКИТЕ
# Всичко тук е ПОВЕДЕНЧЕСКО: подхвърля се мрежа и се гледа изходът. Нито една
# проверка не търси текст във файла — игла, застанала в съседния коментар,
# минава и върху счупен файл.

_FALSHIVI = {}


def _falshiva_mrezha(url):
    """Мрежа от хартия. Отговаря по АДРЕС — затова сгрешен адрес се вижда."""
    _FALSHIVI["vikan"] = _FALSHIVI.get("vikan", 0) + 1
    _FALSHIVI.setdefault("adresi", []).append(url)
    if _FALSHIVI.get("myrtva"):
        return None
    if "kambicdn" in url:
        if "football" in url:
            return {"events": [{"event": {"name": "A - B"}} for _ in range(260)]}
        if _FALSHIVI.get("kambi_prazen"):
            return {"events": []}
        return _KAMBI_TEST
    if "/quotes/" in url:
        return _KOTIROVKI_TEST
    if "/contracts/" in url:
        mid = url.split("/markets/")[1].split("/")[0]
        return {"contracts": [x for x in _KONTRAKTI_TEST
                              if str(x["market_id"]) in mid.split(",")]}
    if "/markets/" in url and "/events/" in url:
        ids = url.split("/events/")[1].split("/")[0].split(",")
        return {"markets": [m for m in _PAZARI_TEST if str(m["event_id"]) in ids]}
    if "/events/?" in url:
        return _falshivi_sabitiya(url)
    if "/events/" in url:
        eid = url.split("/events/")[1].strip("/")
        return {"events": [e for e in _SABITIYA_TEST if str(e["id"]) == eid]}
    return None


def _falshivi_sabitiya(url):
    """🔴 ТУК СЕ ХВАЩАТ ДВАТА ТИХИ КАПАНА. Отговорът зависи от параметрите:
    без include_hidden скритите изчезват, а с pagination_last_id=0 се връща
    ВЧЕРАШНИЯТ ден — точно както прави истинският Smarkets."""
    cid = re.search(r"parent_id=(\d+)", url)
    sast = re.search(r"state=(\w+)", url)
    den = re.search(r"pagination_last_start_datetime=([\d-]+)", url)
    lid = re.search(r"pagination_last_id=(\d+)", url)
    if not (cid and sast and den):
        return None
    iskan = den.group(1)
    if lid and lid.group(1) == "0":
        iskan = "2026-07-26"                 # архивът, както прави истинският
    # 🔴 ЕТАЛОНЪТ ПИТА ЗА ВЧЕРА ПО ИСТИНСКИЯ КАЛЕНДАР (поправено 01.09.2026).
    #
    # _etalon_smarkets смята `vchera` от datetime.now() — тоест иска ден,
    # който подхвърлените събития (всичките от 2026-08-25) нямат. Резултат:
    # еталонът излиза МЪРТЪВ, izvor_zhiv връща False и всеки празен ден се
    # обявява за ZAPUSHENO вместо за честна нула.
    #
    # Проверката „празен ден при жив еталон = празен списък" падаше всеки
    # ден СЛЕД 26.08 — тестът беше закован за деня, в който е писан. Това е
    # ВТОРИЯТ такъв в този файл; първият беше при цената.
    #
    # Живият код е ВЕРЕН и не се пипа: празен резултат + жив еталон = [],
    # празен резултат + мъртъв еталон = ZAPUSHENO. Тук само подставената
    # мрежа се научава да отговаря на еталона, както би отговорил истинският.
    _vchera = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    if iskan == _vchera and sast.group(1) == "ended":
        iskan = "2026-08-25"                 # архивът е жив, каквото и да е днес
    ev = [e for e in _SABITIYA_TEST
          if str(e["parent_id"]) == cid.group(1)
          and e["state"] == sast.group(1)
          and e["start_date"] == iskan]
    if "include_hidden=true" not in url:
        ev = [e for e in ev if not e.get("hidden")]
    return {"events": ev, "pagination": {}}


_SABITIYA_TEST = [
    # Czech Liga Pro (42932772) — днес
    {"id": "1001", "parent_id": "42932772", "state": "ended", "hidden": False,
     "name": "Jan Szotkowski vs Tadeas Zika", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T17:30:00Z"},
    {"id": "1002", "parent_id": "42932772", "state": "ended", "hidden": True,
     "name": "Skrit Hrac vs Vtori Hrac", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T17:35:00Z"},
    # 🔴 ЕДНА ДВОЙКА, ДВА МАЧА В ЕДИН ДЕН — 47.6 % от днешните са такива
    {"id": "1003", "parent_id": "42932772", "state": "ended", "hidden": False,
     "name": "Erik Mares vs Jan Cernik", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T12:00:00Z"},
    {"id": "1004", "parent_id": "42932772", "state": "upcoming", "hidden": False,
     "name": "Erik Mares vs Jan Cernik", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T18:00:00Z"},
    # 🔴 ДВАМА РАЗЛИЧНИ ХОРА С ЕДНО ИМЕ И РАЗЛИЧНА ГОДИНА — видени днес
    {"id": "1005", "parent_id": "42932772", "state": "ended", "hidden": False,
     "name": "Jaroslav (1964) Strnad vs Vaclav Kosar", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T13:00:00Z"},
    {"id": "1006", "parent_id": "42932772", "state": "ended", "hidden": False,
     "name": "Jaroslav (1961) Strnad vs Vaclav Kosar", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T14:00:00Z"},
    {"id": "1007", "parent_id": "42932772", "state": "cancelled", "hidden": False,
     "name": "Michal Vesely vs Daniel Tuma", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T15:00:00Z"},
    # свършил, но с отсъден САМО победител (без CORRECT_SCORE)
    {"id": "1008", "parent_id": "42932772", "state": "ended", "hidden": False,
     "name": "Samo Pobeditel vs Bez Setove", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T16:00:00Z"},
    # вчерашният архив = еталонът
    {"id": "0901", "parent_id": "42932772", "state": "ended", "hidden": False,
     "name": "Vcheraf Hrac vs Vtori Vcheraf", "start_date": "2026-08-24",
     "start_datetime": "2026-08-24T10:00:00Z"},
    {"id": "0701", "parent_id": "42932772", "state": "ended", "hidden": False,
     "name": "Arhiven Hrac vs Star Sopernik", "start_date": "2026-07-26",
     "start_datetime": "2026-07-26T10:00:00Z"},
    # TT Elite Series (44792813)
    {"id": "2001", "parent_id": "44792813", "state": "upcoming", "hidden": False,
     "name": "Jacek Zelezik vs Andrzej Krezel", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T17:55:00Z"},
    {"id": "2002", "parent_id": "44792813", "state": "ended", "hidden": False,
     "name": "Grzegorz Marud vs Kaczynski Piotr", "start_date": "2026-08-25",
     "start_datetime": "2026-08-25T11:00:00Z"},
    {"id": "0902", "parent_id": "44792813", "state": "ended", "hidden": False,
     "name": "Vcheraf Polyak vs Vtori Polyak", "start_date": "2026-08-24",
     "start_datetime": "2026-08-24T10:00:00Z"},
]

_PAZARI_TEST = [
    {"id": "9101", "event_id": "1001", "state": "settled",
     "market_type": {"name": "WINNER_2_WAY"}},
    {"id": "9102", "event_id": "1001", "state": "settled",
     "market_type": {"name": "CORRECT_SCORE"}},
    {"id": "9199", "event_id": "1001", "state": "settled",
     "market_type": {"name": "OVER_UNDER"}},
    {"id": "9103", "event_id": "1002", "state": "settled",
     "market_type": {"name": "CORRECT_SCORE"}},
    {"id": "9104", "event_id": "1003", "state": "settled",
     "market_type": {"name": "CORRECT_SCORE"}},
    {"id": "9105", "event_id": "1004", "state": "open",
     "market_type": {"name": "WINNER_2_WAY"}},
    {"id": "9106", "event_id": "1005", "state": "settled",
     "market_type": {"name": "CORRECT_SCORE"}},
    {"id": "9107", "event_id": "1006", "state": "settled",
     "market_type": {"name": "CORRECT_SCORE"}},
    {"id": "9108", "event_id": "1007", "state": "live",
     "market_type": {"name": "CORRECT_SCORE"}},
    {"id": "9109", "event_id": "1008", "state": "settled",
     "market_type": {"name": "WINNER_2_WAY"}},
    {"id": "9110", "event_id": "2001", "state": "open",
     "market_type": {"name": "WINNER_2_WAY"}},
    {"id": "9111", "event_id": "2002", "state": "settled",
     "market_type": {"name": "CORRECT_SCORE"}},
]


def _cs(mid, ime_a, ime_b, pobeden_param):
    out = []
    for p in ("3-0", "3-1", "3-2", "0-3", "1-3", "2-3"):
        kdo = ime_a if p.startswith("3") else ime_b
        out.append({"id": "c" + mid + p, "market_id": mid,
                    "name": kdo + " 3 - " + p.replace("3-", "").replace("-3", ""),
                    "contract_type": {"param": p},
                    "state_or_outcome": "winner" if p == pobeden_param else "loser"})
    return out


_KONTRAKTI_TEST = (
    [{"id": "4101", "market_id": "9101", "name": "Jan Szotkowski",
      "state_or_outcome": "loser", "contract_type": {}},
     {"id": "4102", "market_id": "9101", "name": "Tadeas Zika",
      "state_or_outcome": "winner", "contract_type": {}}]
    + _cs("9102", "Jan Szotkowski", "Tadeas Zika", "1-3")
    + _cs("9103", "Skrit Hrac", "Vtori Hrac", "3-0")
    + _cs("9104", "Erik Mares", "Jan Cernik", "3-2")
    + _cs("9106", "Jaroslav (1964) Strnad", "Vaclav Kosar", "3-0")
    + _cs("9107", "Jaroslav (1961) Strnad", "Vaclav Kosar", "0-3")
    + _cs("9111", "Grzegorz Marud", "Kaczynski Piotr", "3-1")
    + [{"id": "4109", "market_id": "9109", "name": "Samo Pobeditel",
        "state_or_outcome": "winner", "contract_type": {}},
       {"id": "4110", "market_id": "9109", "name": "Bez Setove",
        "state_or_outcome": "loser", "contract_type": {}},
       {"id": "4105", "market_id": "9105", "name": "Erik Mares",
        "state_or_outcome": "open", "contract_type": {}},
       {"id": "4106", "market_id": "9105", "name": "Jan Cernik",
        "state_or_outcome": "open", "contract_type": {}},
       {"id": "4111", "market_id": "9110", "name": "Jacek Zelezik",
        "state_or_outcome": "open", "contract_type": {}},
       {"id": "4112", "market_id": "9110", "name": "Andrzej Krezel",
        "state_or_outcome": "open", "contract_type": {}}]
)

# price 5263 -> 1.90 (back) ; 4237 -> 2.36 (lay) ; средата = 2.11
_KOTIROVKI_TEST = {
    "4105": {"bids": [{"price": 4237, "quantity": 1}],
             "offers": [{"price": 5263, "quantity": 1}]},
    "4106": {"bids": [{"price": 4717, "quantity": 1}],
             "offers": [{"price": 5747, "quantity": 1}]},
    "4111": {"bids": [{"price": 3000, "quantity": 1}],
             "offers": [{"price": 3500, "quantity": 1}]},
    "4112": {"bids": [{"price": 6000, "quantity": 1}],
             "offers": [{"price": 7500, "quantity": 1}]},
}

_KAMBI_TEST = {"events": [
    {"event": {"name": "Roman Hudeczek - Michal Chalupa",
               "start": "2026-08-25T18:00:00Z",
               "path": [{"englishName": "Table Tennis"},
                        {"englishName": "Czech Republic"},
                        {"englishName": "Czech Liga Pro"}]},
     "betOffers": [{"criterion": {"label": "Match Odds"},
                    "outcomes": [{"label": "Roman Hudeczek", "odds": 1780},
                                 {"label": "Michal Chalupa", "odds": 1860}]}]},
    # изходите обърнати спрямо реда в името — книгата не пази нашия ред
    {"event": {"name": "Erik Mares - Jan Cernik",
               "start": "2026-08-25T18:00:00Z",
               "path": [{"englishName": "Table Tennis"},
                        {"englishName": "Czech Liga Pro"}]},
     "betOffers": [{"criterion": {"label": "Match Odds"},
                    "outcomes": [{"label": "Jan Cernik", "odds": 1700},
                                 {"label": "Erik Mares", "odds": 1970}]}]},
    # чужд пазар с три изхода — не бива да влиза в двоен
    {"event": {"name": "Trima Igracha - Chetvarti Igrach",
               "start": "2026-08-25T18:00:00Z",
               "path": [{"englishName": "Czech Liga Pro"}]},
     "betOffers": [{"criterion": {"label": "Match Odds"},
                    "outcomes": [{"label": "Trima Igracha", "odds": 1500},
                                 {"label": "Chetvarti Igrach", "odds": 2500},
                                 {"label": "Trima Igracha - G1", "odds": 1900}]}]},
    # 🔴 ЧУЖДА ЛИГА — ВЕЧЕ ВЛИЗА (02.09.2026). Дотук коментарът гласеше
    # „не е наша, не влиза" и точно това беше дефектът: Kambi носи и WTT,
    # а ситото го хвърляше. Записът остава като подложка за новото.
    {"event": {"name": "Chuzhd Igrach - Vtori Chuzhd",
               "start": "2026-08-25T18:00:00Z",
               "path": [{"englishName": "TT Cup"}]},
     "betOffers": [{"criterion": {"label": "Match Odds"},
                    "outcomes": [{"label": "Chuzhd Igrach", "odds": 1500},
                                 {"label": "Vtori Chuzhd", "odds": 2500}]}]},
]}


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    star_mr, star_ra = _MREZHA[0], globals()["_RACHKA"]
    _MREZHA[0] = _falshiva_mrezha
    globals()["_RACHKA"] = "czech liga pro,tt elite series"
    _FALSHIVI.clear()
    izchisti_kesh()
    try:
        # ═══ 1. ЕСТЕСТВЕНОТО ИЗВИКВАНЕ — БЕЗ НИТО ЕДИН АРГУМЕНТ ═══
        # 🔴 ЗАЩО СТОИ ПЪРВО. Днес в тази къща е хванат модул с 45 зелени
        # проверки, чиято главна функция връща None ВИНАГИ, защото си строеше
        # указателя от празни речници. Тези проверки минават по СЪЩИЯ път,
        # по който ще мине ботът; подменена е само мрежата.
        fx = fixtures("2026-08-25")
        check("fixtures() БЕЗ данни връща срещи", isinstance(fx, list) and len(fx) > 0)
        check("fixtures() наистина пита извора", _FALSHIVI.get("vikan", 0) > 0)
        check("срещата носи начало", all(f.get("when") is not None for f in fx))
        check("срещата носи лига", all(f.get("league") for f in fx))
        check("срещата носи ДВЕ имена",
              all(f.get("home") and f.get("away") for f in fx))
        check("срещата носи НОМЕРА (иначе резултатът гада по имена)",
              all((f.get("extra") or {}).get("slug", "").isdigit() for f in fx))
        check("срещата носи ЧАСА в extra['vb'] (иначе ключът се презаписва)",
              all(re.fullmatch(r"\d{4}", (f.get("extra") or {}).get("vb") or "")
                  for f in fx))
        check("кошницата е tabletennis", all(f["bucket"] == "tabletennis" for f in fx))
        check("срещите са подредени по час",
              [f["when"] for f in fx] == sorted(f["when"] for f in fx))
        check("свършилите НЕ влизат в предстоящите",
              all(str((f.get("extra") or {}).get("slug")) != "1001" for f in fx))
        check("отмененият НЕ влиза в предстоящите",
              all(str((f.get("extra") or {}).get("slug")) != "1007" for f in fx))
        check("и двете лиги дават срещи",
              len(set(f["league"] for f in fx)) == 2)

        c = cena("Roman Hudeczek", "Michal Chalupa")
        check("cena() БЕЗ указател НЕ мълчи", isinstance(c, dict))
        check("cena() дава цената на домакина", c and abs(c["dom"] - 1.78) < 1e-6)
        check("cena() дава цената на госта", c and abs(c["gost"] - 1.86) < 1e-6)
        check("🔴 odds Е ДЕЛЕНО НА 1000 (1780 -> 1.78)", c and c["dom"] < 20)
        check("честната вероятност е между 0 и 1", c and 0.0 < c["p_dom"] < 1.0)
        check("вероятностите се събират на 1",
              c and abs(c["p_dom"] + c["p_gost"] - 1.0) < 1e-9)
        check("маржът е обявен и е положителен при книжаря",
              c and 0.05 < c["marzh"] < 0.20)
        check("източникът е назован", c and c["izvor"] in ("kambi", "smarkets"))

        r = rezultat({"slug": "1001", "home": "Jan Szotkowski", "away": "Tadeas Zika"})
        check("rezultat() БЕЗ друго освен номер отсъжда", r == (1, 3))

        # ═══ 2. ИМЕНАТА ═══
        check("наборът, не последната дума: 'Kaczynski Piotr' = 'Piotr Kaczynski'",
              klyuch_ime("Kaczynski Piotr")[1] == klyuch_ime("Piotr Kaczynski")[1])
        check("🔴 СТРОГИЯТ ПАЗИ ГОДИНАТА: (1964) != (1961)",
              klyuch_ime("Jaroslav (1964) Strnad")[0]
              != klyuch_ime("Jaroslav (1961) Strnad")[0])
        check("хлабавият маха годината",
              klyuch_ime("Jaroslav (1964) Strnad")[1]
              == klyuch_ime("Jaroslav Strnad")[1])
        check("Senior/Junior не правят друг човек",
              klyuch_ime("Marek Senior Sedlak")[1] == klyuch_ime("Marek Sedlak")[1])
        check("диакритиките се свеждат",
              klyuch_ime("Václav Kosař")[1] == klyuch_ime("Vaclav Kosar")[1])
        check("празно име дава празен ключ",
              klyuch_ime("")[0] == () and klyuch_ime(None)[0] == ())
        check("двойката с празно име е None", dvoika("", "Zika") is None)
        check("един и същ човек от двете страни не е мач",
              dvoika("Tadeas Zika", "Zika Tadeas") is None)
        check("двойката е неподредена",
              dvoika("A Bb", "C Dd") == dvoika("C Dd", "A Bb"))

        # ═══ 3. ЛИГИТЕ И РЪЧКАТА ═══
        check("нашето име на лига се разпознава",
              liga_klyuch("Czech Liga Pro") == "czech liga pro")
        check("slug-ът също", liga_klyuch("czech-liga-pro") == "czech liga pro")
        check("чужда лига не е наша", liga_klyuch("WTT Feeder Olomouc") is None)
        check("украинските вериги ГИ НЯМА", liga_klyuch("Setka Cup") is None)
        check("None лига не гърми", liga_klyuch(None) is None)
        globals()["_RACHKA"] = ""
        check("🔴 ПЪТЯТ НАЗАД: празна ръчка изключва всичко", vklyucheni() == [])
        check("празна ръчка -> нула срещи, не сентинел", fixtures("2026-08-25") == [])
        globals()["_RACHKA"] = "czech liga pro"
        check("една лига в ръчката = една лига", vklyucheni() == ["czech liga pro"])
        globals()["_RACHKA"] = "czech liga pro,tt elite series"

        # ═══ 4. ДВАТА ТИХИ КАПАНА В АДРЕСА ═══
        u = _url_den("42932772", "2026-08-25", "ended")
        check("🔴 pagination_last_id=1, НЕ 0", "pagination_last_id=1" in u)
        check("🔴 include_hidden=true", "include_hidden=true" in u)
        check("sort е точно start_datetime,id", "sort=start_datetime,id" in u)
        izchisti_kesh()
        ev = _den_sabitiya("czech liga pro", "2026-08-25", ("ended",))
        check("денят е ДНЕШНИЯТ, не архивът",
              isinstance(ev, list) and all(e["start_date"] == "2026-08-25" for e in ev))
        check("🔴 СКРИТИЯТ мач се вижда (12 от 12 скрити днес са ОТСЪДЕНИ)",
              isinstance(ev, list) and any(e["id"] == "1002" for e in ev))
        check("отсъждам и скрития",
              rezultat({"slug": "1002", "home": "Skrit Hrac", "away": "Vtori Hrac"})
              == (3, 0))

        # ═══ 5. ЕДНА ДВОЙКА, ДВА МАЧА В ЕДИН ДЕН ═══
        bez_chas = {"league": "Czech Liga Pro", "day": "2026-08-25",
                    "home": "Erik Mares", "away": "Jan Cernik"}
        check("🔴 БЕЗ ЧАС при два мача се МЪЛЧИ", rezultat(bez_chas) is None)
        s_chas = dict(bez_chas, start="2026-08-25T12:00:00Z")
        check("с час се намира ВЕРНИЯТ мач", rezultat(s_chas) == (3, 2))
        dalech = dict(bez_chas, start="2026-08-25T03:00:00Z")
        check("час извън прозореца НЕ лепва чужд мач", rezultat(dalech) is None)
        # 🔴 ДАТАТА СЕ ЗАКОВАВА (26.08.2026). Дотук тези две проверки викаха
        # cena() БЕЗ указател, тоест index_ceni() питаше за ДНЕШНИЯ ден. Всички
        # подхвърлени събития са от 2026-08-25 — значи проверката минаваше САМО
        # в деня, в който е писана. На 26.08 празният ден дава СЕНТИНЕЛА
        # ZAPUSHENO (не можах да питам), а не None, и проверката падна.
        # Съседните ѝ подават "day": "2026-08-25" изрично; тези две — не.
        _ind25 = index_ceni("2026-08-25")
        check("указателят за 25.08 не е сентинел", isinstance(_ind25, dict))
        check("🔴 цената при два мача БЕЗ ЧАС МЪЛЧИ",
              cena("Erik Mares", "Jan Cernik", "Czech Liga Pro", ind=_ind25) is None)
        check("същата двойка С ЧАС СИ ИМА цена",
              isinstance(cena("Erik Mares", "Jan Cernik", "Czech Liga Pro",
                              kogato="2026-08-25T18:00:00Z", ind=_ind25), dict))

        # ═══ 6. ДВАМАТА СЪС СЪЩОТО ИМЕ ═══
        check("(1964) взима СВОЯ резултат",
              rezultat({"league": "Czech Liga Pro", "day": "2026-08-25",
                        "home": "Jaroslav (1964) Strnad", "away": "Vaclav Kosar"})
              == (3, 0))
        check("(1961) взима СВОЯ резултат",
              rezultat({"league": "Czech Liga Pro", "day": "2026-08-25",
                        "home": "Jaroslav (1961) Strnad", "away": "Vaclav Kosar"})
              == (0, 3))
        check("🔴 БЕЗ ГОДИНА при двама еднакви се МЪЛЧИ",
              rezultat({"league": "Czech Liga Pro", "day": "2026-08-25",
                        "home": "Jaroslav Strnad", "away": "Vaclav Kosar"}) is None)

        # ═══ 7. ОБЪРНАТИ СТРАНИ ═══
        check("обърнатият запис ОБРЪЩА сетовете",
              rezultat({"slug": "1001", "home": "Tadeas Zika",
                        "away": "Jan Szotkowski"}) == (3, 1))
        ob = cena("Michal Chalupa", "Roman Hudeczek")
        check("обърнатата цена се обявява", ob and ob["obarnat"] is True)
        check("обърнатата РАЗМЕНЯ цените",
              ob and abs(ob["dom"] - 1.86) < 1e-6 and abs(ob["gost"] - 1.78) < 1e-6)
        pr = cena("Roman Hudeczek", "Michal Chalupa")
        check("правата НЕ е обявена за обърната", pr and pr["obarnat"] is False)
        check("Kambi изходите могат да са обърнати спрямо името",
              (cena("Erik Mares", "Jan Cernik", kogato="2026-08-25T18:00:00Z") or {})
              .get("dom") is not None)

        # ═══ 8. ЧЕСТНИТЕ ОТКАЗИ ═══
        check("отмененият дава OTLOZHEN",
              rezultat({"slug": "1007", "home": "Michal Vesely",
                        "away": "Daniel Tuma"}) is OTLOZHEN)
        check("🔴 БЕЗ ИЗМИСЛЕН 3-0: само победител -> сентинел",
              rezultat({"slug": "1008", "home": "Samo Pobeditel",
                        "away": "Bez Setove"}) is POBEDITEL_BEZ_SETOVE)
        check("но победителят СЕ ЗНАЕ по име", pobeditel("1008") == "Samo Pobeditel")
        check("неотсъденият дава None",
              rezultat({"slug": "1004", "home": "Erik Mares",
                        "away": "Jan Cernik"}) is None)
        check("непознат мач дава None",
              rezultat({"league": "Czech Liga Pro", "day": "2026-08-25",
                        "home": "Nikoy Nikoev", "away": "Vtori Nikoy"}) is None)
        check("чужда лига не се отсъжда тук",
              rezultat({"league": "WTT Feeder Olomouc", "day": "2026-08-25",
                        "home": "A B", "away": "C D"}) is None)
        check("боклук вместо запис не гърми", rezultat(None) is None
              and rezultat(5) is None and rezultat({}) is None)
        check("непозната двойка няма цена", cena("Nikoy Nikoev", "Vtori Nikoy") is None)
        check("празни имена нямат цена", cena("", "") is None)
        check("None имена не гърмят", cena(None, None) is None)

        # ═══ 9. ЧУЖДИТЕ ПАЗАРИ ═══
        ik = ceni_kambi()
        check("указателят на Kambi се строи", isinstance(ik, dict) and len(ik) > 0)
        check("🔴 ТРИ ИЗХОДА в двоен пазар НЕ влизат (това е ГЕЙМ 1, не мач)",
              dvoika("Trima Igracha", "Chetvarti Igrach", strogo=False) not in ik)
        # 🔴 ОБЪРНАТИ (02.09.2026). Дотук доказваха, че ЧУЖДАТА лига НЕ
        # влиза — и точно това беше дефектът. `LIGI` е закован речник с две
        # местни лиги, а Kambi носи и трети турнир: измерено живо същия ден,
        # WTT Contender Almaty с 2 мача и цени 1.13/5.00 и 2.10/1.65.
        # Тоест ситото изхвърляше единствения WTT коефициент, който изобщо
        # имаме — в спорта, където 319 карти носят само 49 цени.
        # Проверките не са махнати; сменена е посоката им.
        check("чуждата лига ВЕЧЕ влиза в указателя",
              dvoika("Chuzhd Igrach", "Vtori Chuzhd", strogo=False) in ik)
        check("и носи името си, не закованото",
              any(r["liga"] == "TT Cup" for v in ik.values() for r in v))
        check("и ключът е изведен от него",
              any(r["liga_key"] == "tt cup"
                  for v in ik.values() for r in v))
        check("Kambi дава трите наши двойки", len(ik) == 3)
        # 🔴 А ТРИТЕ ИЗХОДА ПАК НЕ ВЛИЗАТ. Отварянето на лигата НЕ бива да
        # отвори и чуждия вид пазар — това са две различни сита.
        check("три изхода пак НЕ влизат",
              dvoika("Trima Igracha", "Chetvarti Igrach", strogo=False) not in ik)

        # ═══ 9б. НЕПОЗНАТАТА ЛИГА — самото пресяване
        check("свободният ключ е малки букви без шум",
              klyuch_liga_svobodna("  WTT   Contender  Almaty ")
              == "wtt contender almaty")
        check("празното дава име, не гърми",
              klyuch_liga_svobodna("") == "table tennis")
        check("None не гърми", klyuch_liga_svobodna(None) == "table tennis")
        # 🔴 И НЕ СЪВПАДА С ПОЗНАТИТЕ. Ако съвпаднеше, стесняването по
        # liga_key в `cena` щеше да смеси турнирите — а точно то пази двойка,
        # която играе по три пъти на ден, от чужда цена.
        for _pk in LIGI:
            check("свободният ключ не е «" + _pk + "»",
                  klyuch_liga_svobodna("WTT Contender Almaty") != _pk)

        # ═══ 10. ЧЕСТНАТА ЦЕНА ОТ БОРСАТА ═══
        izchisti_kesh()
        s = ceni_smarkets("2026-08-25")
        check("Smarkets дава указател", isinstance(s, dict) and len(s) > 0)
        red = (s.get(dvoika("Erik Mares", "Jan Cernik", strogo=False)) or [None])[0]
        check("🔴 КОЕФИЦИЕНТ = 10000/price, средата на back и lay",
              red and abs(red["dom"] - 2.105) < 0.01)
        check("другата страна също", red and abs(red["gost"] - 1.905) < 0.02)
        if red:
            ov = 1.0 / red["dom"] + 1.0 / red["gost"]
            check("🔴 маржът по средата е ~0 (борса, не книжар)", abs(ov - 1.0) < 0.01)
        check("Smarkets носи НОМЕРА на събитието", red and red["nomer"] == "1004")
        check("Smarkets е ПРЕДИ Kambi в общия указател",
              (index_ceni("2026-08-25").get(
                  dvoika("Erik Mares", "Jan Cernik", strogo=False)) or [{}])[0]
              .get("izvor") == "smarkets")

        # ═══ 11. РАЗЛИКАТА „НЯМА" СРЕЩУ „НЕ МОЖАХ ДА ПИТАМ" ═══
        check("сентинелите са ОБЕКТИ, не низове",
              not isinstance(ZAPUSHENO, str) and not isinstance(OTLOZHEN, str)
              and not isinstance(POBEDITEL_BEZ_SETOVE, str))
        check("сентинелите са РАЗЛИЧНИ обекти",
              len({id(ZAPUSHENO), id(OTLOZHEN), id(POBEDITEL_BEZ_SETOVE)}) == 3)
        check("🔴 сентинелът НЕ Е лъжливо празен (`if not x` не го изяжда)",
              bool(ZAPUSHENO) is True and bool(OTLOZHEN) is True)
        check("сентинелът се вижда в дневник", "ZAPUSHENO" in repr(ZAPUSHENO))
        check("нула наши + нула еталон = МЪРТЪВ извор", izvor_zhiv(0, 0) is False)
        check("нула наши + жив еталон = честна нула", izvor_zhiv(0, 260) is True)
        check("живи наши = жив извор", izvor_zhiv(191, 260) is True)
        check("боклук се брои за мъртъв", izvor_zhiv(None, None) is False)
        check("текст не гърми", izvor_zhiv("абв", "5") is False)

        izchisti_kesh()
        _FALSHIVI["myrtva"] = True
        check("🔴 мъртва мрежа -> fixtures() дава ZAPUSHENO, НЕ []",
              fixtures("2026-08-25") is ZAPUSHENO)
        check("мъртва мрежа -> cena() дава ZAPUSHENO, НЕ None",
              cena("Roman Hudeczek", "Michal Chalupa") is ZAPUSHENO)
        check("мъртва мрежа -> rezultat() дава ZAPUSHENO, НЕ None",
              rezultat({"slug": "1001", "home": "Jan Szotkowski",
                        "away": "Tadeas Zika"}) is ZAPUSHENO)
        check("мъртва мрежа -> _den_sabitiya дава ZAPUSHENO",
              _den_sabitiya("czech liga pro", "2026-08-25") is ZAPUSHENO)
        _FALSHIVI.pop("myrtva", None)
        izchisti_kesh()
        _FALSHIVI["kambi_prazen"] = True
        ik2 = ceni_kambi()
        check("празен Kambi при ЖИВ еталон = честна нула, не сентинел",
              isinstance(ik2, dict) and ik2 == {})
        check("еталонът наистина е питан",
              any("football" in a for a in _FALSHIVI.get("adresi") or []))
        _FALSHIVI.pop("kambi_prazen", None)
        izchisti_kesh()
        check("празен ден при жив еталон = празен списък, не сентинел",
              _den_sabitiya("czech liga pro", "2026-08-20", ("ended",)) == [])

        # ═══ 12. ПЕСТЕНЕ НА ЗАЯВКИ ═══
        izchisti_kesh()
        fixtures("2026-08-25")
        p1 = _BROYACH["zayavki"]
        fixtures("2026-08-25")
        p2 = _BROYACH["zayavki"]
        check("🔴 вторият въпрос НЕ пита пак (един отговор носи всички мачове)",
              p2 == p1 and _BROYACH["kesh"] > 0)
        check("първото питане е малко заявки (2 лиги × 2 състояния)", p1 <= 6)
        izchisti_kesh()
        rezultat({"slug": "1001", "home": "Jan Szotkowski", "away": "Tadeas Zika"})
        check("🔴 отсъждането по номер е ≤ 3 заявки, не 60",
              _BROYACH["zayavki"] <= 3)

        # ═══ 13. УСТОЙЧИВОСТ ═══
        check("боклук в указателя не гърми", cena("A B", "C D", ind={}) is None)
        check("сентинел за указател се предава нататък",
              cena("A B", "C D", ind=ZAPUSHENO) is ZAPUSHENO)
        check("развален час не гърми", _chas("не-е-час") is None and _chas("") is None)
        check("часът се чете с Z", _chas("2026-08-25T17:30:00Z") is not None)
        check("честната вероятност отказва боклук",
              _chestni(0, 2) is None and _chestni("а", "б") is None)
        check("честната вероятност отказва цена под 1", _chestni(0.5, 2.0) is None)

        # ═══ 14. КАКВО УМЕЕМ ДА ПРОЧЕТЕМ ═══
        # 🔴 ПОВЕДЕНЧЕСКА, НЕ ТЕКСТОВА. Вдига се истински сървър на
        # 127.0.0.1 и се пита какво ИЗЛИЗА от _http_json, не дали някакъв ред
        # стои в кода. Никаква дата, никаква мрежа навън.
        _chete, _tisho, _iskano = _proba_sgastyavane()
        check("чете НЕсгъстен отговор", _chete.get("(няма)") == _PROBA_TYALO)
        check("чете gzip", _chete.get("gzip") == _PROBA_TYALO)
        check("чете GZIP с ГЛАВНИ букви", _chete.get("GZIP") == _PROBA_TYALO)
        check("чете „gzip, “ със запетая", _chete.get("gzip, ") == _PROBA_TYALO)
        check("чете deflate", _chete.get("deflate") == _PROBA_TYALO)
        # 🔴 СЪРЦЕТО НА КРЪПКАТА: нечетимото НЕ бива да прилича на
        # празен ден. Ако тук някой върне {} или [], тенисът на маса пак ще
        # става тихо на нула — точно както стана днес.
        check("нечетимият br е МЪЛЧАНИЕ (None), не празен отговор",
              "br" in _tisho and _tisho["br"] is None and "br" not in _chete)
        _tok = [x.strip().lower() for x in _iskano.split(",")]
        check("молбата стига до сървъра и иска gzip", "gzip" in _tok)
        check("молбата НЕ обещава br, който не умеем да отворим",
              "br" not in _tok)

        check("броят проверки е поне 80", ok >= 80)
    finally:
        _MREZHA[0] = star_mr
        globals()["_RACHKA"] = star_ra
        _FALSHIVI.clear()
        izchisti_kesh()

    print("САМОПРОВЕРКА НА TT_LIGI: " + str(ok) + " наред, "
          + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


# ═════════════════════════════════════════════════════════════════ МУТАЦИИ
# Проверка, която не може да падне, е украса. Всяка мутация тук е ИСТИНСКА
# грешка, която някой би написал — и всяка трябва да бъде хваната.
def mutacii():
    import io
    import contextlib

    g = globals()
    opiti = []

    def _bez_1000():
        d = _json(_url_kambi())
        ind = {}
        for it in (d or {}).get("events") or []:
            e = it.get("event") or {}
            pat = " ".join(str(p.get("englishName") or "") for p in (e.get("path") or []))
            if "Czech Liga Pro" not in pat and "TT Elite" not in pat:
                continue
            a, sep, b = str(e.get("name") or "").partition(" - ")
            if not sep:
                continue
            for bo in it.get("betOffers") or []:
                if (bo.get("criterion") or {}).get("label") != "Match Odds":
                    continue
                o = bo.get("outcomes") or []
                if len(o) != 2:
                    continue
                dv = dvoika(o[0].get("label"), o[1].get("label"), strogo=False)
                if dv is None:
                    continue
                # 🐛 забравеното деление на 1000
                ind.setdefault(dv, []).append({
                    "dom_ime": o[0]["label"], "gost_ime": o[1]["label"],
                    "dom": float(o[0]["odds"]), "gost": float(o[1]["odds"]),
                    "liga": "Czech Liga Pro", "liga_key": "czech liga pro",
                    "start": str(e.get("start") or ""), "izvor": "kambi",
                    "nomer": None})
        return ind
    opiti.append(("ceni_kambi забравя деленето на 1000 (1780 вместо 1.78)",
                  "ceni_kambi", _bez_1000))

    def _bez_skriti(cid, den, sast):
        return (SM + "/events/?parent_id=" + str(cid) + "&state=" + str(sast) +
                "&sort=start_datetime,id&limit=200"
                "&pagination_last_start_datetime=" + str(den) + "T00:00:00Z"
                "&pagination_last_id=1")
    opiti.append(("_url_den изпуска include_hidden (скритите изчезват)",
                  "_url_den", _bez_skriti))

    def _nula(cid, den, sast):
        return (SM + "/events/?parent_id=" + str(cid) + "&state=" + str(sast) +
                "&sort=start_datetime,id&limit=200&include_hidden=true"
                "&pagination_last_start_datetime=" + str(den) + "T00:00:00Z"
                "&pagination_last_id=0")
    opiti.append(("_url_den праща pagination_last_id=0 (връща архива)",
                  "_url_den", _nula))

    def _bez_godina(ime):
        s = _pochisti(ime)
        gol = _TITLA.sub(" ", _GODINA.sub(" ", s))
        d = tuple(sorted(re.sub(r"[^A-Za-z ]", " ", gol).lower().split()))
        return (d, d)      # 🐛 строгият губи годината -> двамата стават един
    opiti.append(("klyuch_ime маха годината (двама Strnad стават един)",
                  "klyuch_ime", _bez_godina))

    def _izmislen_30(eid):
        r = _setove_ot_sabitie_ORIG(eid)
        return (3, 0) if r is POBEDITEL_BEZ_SETOVE else r
    opiti.append(("_setove_ot_sabitie подхвърля 3-0 при само победител",
                  "_setove_ot_sabitie", _izmislen_30))

    def _nula_e_otgovor(broi, broi_etalon):
        try:
            return int(broi) >= 0        # 🐛 нулата минава за честен отговор
        except (TypeError, ValueError):
            return False
    opiti.append(("izvor_zhiv брои запушването за честна нула",
                  "izvor_zhiv", _nula_e_otgovor))

    def _bez_obrashtane(dom, gost, liga=None, kogato=None, ind=None):
        r = _cena_ORIG(dom, gost, liga, kogato, ind)
        if isinstance(r, dict):
            r = dict(r, dom=r["gost"], gost=r["dom"])   # 🐛 обърнати страни
        return r
    opiti.append(("cena разменя домакин и гост", "cena", _bez_obrashtane))

    def _parvi_kandidat(rec):
        if not isinstance(rec, dict):
            return None
        eid = str(rec.get("slug") or rec.get("sm_id") or "").strip()
        if eid.isdigit():
            return {"id": eid, "state": None, "name": None, "_po_nomer": True}
        lk = liga_klyuch(rec.get("league"))
        if lk is None or lk not in vklyucheni():
            return None
        dv = dvoika(rec.get("home"), rec.get("away"), strogo=True)
        ev = _den_sabitiya(lk, str(rec.get("day") or "")[:10])
        if dv is None or ev is ZAPUSHENO:
            return None
        for e in ev:                       # 🐛 взима ПЪРВИЯ, без да пита часа
            a, sep, b = str(e.get("name") or "").partition(" vs ")
            if sep and dvoika(a, b, strogo=True) == dv:
                return e
        return None
    opiti.append(("_nameri_sabitie взима ПЪРВИЯ мач на двойката, без часа",
                  "_nameri_sabitie", _parvi_kandidat))

    def _bez_ime_po_nomer(rec):
        if isinstance(rec, dict):
            eid = str(rec.get("slug") or rec.get("sm_id") or "").strip()
            if eid.isdigit():
                # 🐛 по номер не се взима ИМЕТО -> страните не се изправят
                return {"id": eid, "state": None, "name": None,
                        "_po_nomer": True}
        return _nameri_sabitie_ORIG(rec)
    opiti.append(("_nameri_sabitie по номер не взима името "
                  "(обърнатата карта получава огледална присъда)",
                  "_nameri_sabitie", _bez_ime_po_nomer))

    def _gadae_bez_chas(dom, gost, liga=None, kogato=None, ind=None):
        r = _cena_ORIG(dom, gost, liga, kogato, ind)
        if r is not None:
            return r
        ind2 = index_ceni() if ind is None else ind
        if not isinstance(ind2, dict):
            return r
        dv = dvoika(dom, gost, strogo=False)
        kand = list(ind2.get(dv) or []) if dv else []
        if not kand:
            return r
        # 🐛 без час подхвърля ПЪРВИЯ кандидат
        return _cena_ORIG(dom, gost, liga, kand[0].get("start"), ind2)
    opiti.append(("cena без час подхвърля ПЪРВИЯ кандидат",
                  "cena", _gadae_bez_chas))

    def _kesh_izklyuchen(url, kesh_sek=None):
        return _MREZHA[0](url)             # 🐛 без кеш — всяко питане е ново
    opiti.append(("_json без кеш (всеки въпрос е нова заявка)",
                  "_json", _kesh_izklyuchen))

    def _samo_tochno_gzip(surovo, ce):
        """Старото сравнение: точно „gzip“, чувствително към главни букви."""
        import gzip as _g
        if str(ce or "") == "gzip":
            return _g.decompress(surovo)
        return surovo

    opiti.append(("_razsgasti пак сравнява ТОЧНО „gzip“ (GZIP/deflate замлъкват)",
                  "_razsgasti", _samo_tochno_gzip))

    def _praznoto_vmesto_mylchanie(surovo, ce):
        """Нечетимата глава се преструва на празен отговор вместо да гърми."""
        e = str(ce or "").lower()
        if not e or "identity" in e:
            return surovo
        if "gzip" in e:
            import gzip as _g
            return _g.decompress(surovo)
        if "deflate" in e:
            import zlib as _z
            return _z.decompress(surovo)
        return b"{}"

    opiti.append(("_razsgasti връща празно {} вместо да мълчи при br",
                  "_razsgasti", _praznoto_vmesto_mylchanie))

    opiti.append(("ISKAME обещава br, който не умеем да отворим",
                  "ISKAME", "br, gzip"))

    g["_setove_ot_sabitie_ORIG"] = g["_setove_ot_sabitie"]
    g["_cena_ORIG"] = g["cena"]
    g["_nameri_sabitie_ORIG"] = g["_nameri_sabitie"]

    tih = io.StringIO()
    with contextlib.redirect_stdout(tih):
        osnova = selftest()
    if osnova != 0:
        print("МУТАЦИИ: НЕ МОГА ДА ЗАПОЧНА — чистата самопроверка вече е червена.")
        print(tih.getvalue())
        return 1

    ulov, propusk = 0, []
    for opis, ime, kryp in opiti:
        star = g[ime]
        g[ime] = kryp
        try:
            t = io.StringIO()
            with contextlib.redirect_stdout(t):
                rez = selftest()
        finally:
            g[ime] = star
        if rez != 0:
            ulov += 1
            parva = [l.strip() for l in t.getvalue().splitlines()
                     if l.strip().startswith("счупено:")]
            print("  ✅ ХВАНАТА: " + opis)
            print("       -> " + (parva[0] if parva else "?"))
        else:
            propusk.append(opis)
            print("  ❌ ПРОПУСНАТА: " + opis)
    g.pop("_setove_ot_sabitie_ORIG", None)
    g.pop("_cena_ORIG", None)
    g.pop("_nameri_sabitie_ORIG", None)
    print("МУТАЦИИ: " + str(ulov) + " хванати от " + str(len(opiti)))
    for p in propusk:
        print("   пропусната: " + p)
    return 0 if not propusk else 1


# ══════════════════════════════════════════════════════════════════ НА ЖИВО
def zhivo(den=None):
    """Истинско питане — за очи, не за автомат."""
    izchisti_kesh()
    den = str(den or _dnes())[:10]
    print("═" * 74)
    print("TT_LIGI НА ЖИВО · " + datetime.now(timezone.utc)
          .strftime("%Y-%m-%d %H:%M:%SZ") + " · ден " + den)
    print("ръчка TT_LIGI = " + repr(_RACHKA) + " -> " + str(vklyucheni()))
    print("═" * 74)

    fx = fixtures(den)
    if fx is ZAPUSHENO:
        print("🔴 ЗАПУШЕНО — не можах да питам. Това НЕ Е „няма мачове“.")
        return 1
    print("СРЕЩИ (предстоящи и живи): " + str(len(fx)))
    po_liga = {}
    for f in fx:
        po_liga[f["league"]] = po_liga.get(f["league"], 0) + 1
    for k, v in sorted(po_liga.items()):
        print("   " + str(v) + "  " + k)
    if fx:
        print("   хоризонт: " + fx[0]["when"].strftime("%H:%M") + "Z -> "
              + fx[-1]["when"].strftime("%H:%M") + "Z")

    ind = index_ceni(den)
    if ind is ZAPUSHENO:
        print("🔴 ЦЕНАТА Е ЗАПУШЕНА — и двете книги мълчат.")
        ind = {}
    s_cena, izvori = 0, {}
    for f in fx:
        c = cena(f["home"], f["away"], f["league"],
                 kogato=(f["extra"] or {}).get("start"), ind=ind)
        if isinstance(c, dict):
            s_cena += 1
            izvori[c["izvor"]] = izvori.get(c["izvor"], 0) + 1
            f["_c"] = c
    print("С ЦЕНА: " + str(s_cena) + " от " + str(len(fx))
          + (" = %.1f%%" % (100.0 * s_cena / len(fx)) if fx else "")
          + " | по извор: " + str(izvori))
    for f in fx[:5]:
        c = f.get("_c")
        red = ("   " + f["when"].strftime("%H:%M") + "Z  " + f["home"]
               + "  vs  " + f["away"] + "  [" + f["league"] + "] #"
               + str((f["extra"] or {}).get("slug")))
        if c:
            red += ("\n        " + c["izvor"] + ": " + str(c["dom"]) + " / "
                    + str(c["gost"]) + "  -> P(дом)=%.1f%%  марж=%.2f%%"
                    % (100 * c["p_dom"], 100 * c["marzh"]))
        else:
            red += "\n        цена: НЯМА"
        print(red)

    print("─" * 74)
    print("ОТСЪЖДАНЕ на вече свършили мачове:")
    otsadeni = 0
    proba = []
    for lk in vklyucheni():
        ev = _den_sabitiya(lk, den, ("ended",))
        if ev is ZAPUSHENO:
            print("   🔴 " + lk + ": ЗАПУШЕНО")
            continue
        proba += [(lk, e) for e in ev[-3:]]
    for lk, e in proba:
        a, _sep, b = str(e.get("name") or "").partition(" vs ")
        # 1) по НОМЕР (както ще стане, ако картата е родена оттук)
        r1 = rezultat({"slug": str(e["id"]), "home": a, "away": b})
        # 2) по ИМЕНА+ЧАС (както ще стане за карта, родена другаде)
        r2 = rezultat({"league": LIGI[lk]["ime"], "day": den, "home": a, "away": b,
                       "start": e.get("start_datetime")})
        pob = pobeditel(str(e["id"]))
        if isinstance(r1, tuple):
            otsadeni += 1
        sav = "✔ СЪВПАДАТ" if r1 == r2 else "✗ РАЗМИНАВАТ СЕ"
        print("   #" + str(e["id"]) + " " + str(e.get("name"))
              + " (" + str(e.get("start_datetime")) + ")")
        print("       по номер: " + str(r1) + " | по имена+час: " + str(r2)
              + " | " + sav + " | победител: " + str(pob))
    print("отсъдени: " + str(otsadeni) + " от " + str(len(proba)))
    print("ЗАЯВКИ ОБЩО: " + str(_BROYACH["zayavki"])
          + " | спестени от кеша: " + str(_BROYACH["kesh"]))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--selftest" in a:
        sys.exit(selftest())
    if "--mutacii" in a:
        sys.exit(mutacii())
    if "--zhivo" in a:
        d = None
        for i, x in enumerate(a):
            if x == "--den" and i + 1 < len(a):
                d = a[i + 1]
        sys.exit(zhivo(d))
    if "--dokumentaciya" in a:
        print(__doc__)
        sys.exit(0)
    # 🔴 ГОЛОТО ПУСКАНЕ Е САМОПРОВЕРКА, както в pazar.py. Печатането на
    # документацията излиза с код 0 и БЕЗ ред със сметка — тоест отвън
    # счупен и здрав модул изглеждат еднакво.
    sys.exit(selftest())
