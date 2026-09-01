# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ПАЗАРНАТА ЦЕНА 📊

Един въпрос: КОЛКО ПЛАЩА ПАЗАРЪТ за изхода, който ние сочим?

ЗАЩО СЪЩЕСТВУВА
Собственикът: „не искам нищо наум — трябва да намериш начин". Начинът е
ДЪЛБОКИЯТ слой на ESPN, не онзи, който ботът ползва досега.

  site.api.espn.com/.../scoreboard      → коефициенти САМО за футбола
  sports.core.api.espn.com/v2/sports/… → и за бейзбол, и за ВНБА, и с
                                          отваряща, текуща и затваряща цена

Измерено на живо 13.08.2026:
  ⚽ футбол   DraftKings + Bet365      ✅
  ⚾ МЛБ      DraftKings               ✅   (пример: 1.91 / 2.01)
  🏀 ВНБА     DraftKings + Live        ✅
  🎾 ATP · 🥊 UFC · 🏐 волейбол · 🏀 НБА  →  нула доставчика

Тоест три от седемте спорта имат цена. Тези три са 114 от досегашните записи.

КАКВО ПРАВИМ С НЕЯ
Показваме число, НЕ реклама: няма име на оператор, няма линк, няма покана.
Пазарът казва едно, ние казваме друго — читателят вижда и двете и решава сам.
И се записва в дневника, за да може после да се отговори на единствения
въпрос, който мери качество: бием ли пазара, или само познаваме фаворити.

  python pazar.py --selftest   — проверките, без мрежа
"""
import io
import json
import os
import sys
import urllib.request

CORE = "https://sports.core.api.espn.com/v2/sports"
# Спортовете, за които ИЗМЕРЕНО има цена. Другите не се питат — заявка без
# отговор е чиста загуба от бюджета.
IMA_PAZAR = {"baseball", "basketball", "soccer"}
_kesh = {}
TIMEOUT = int((os.environ.get("PAZAR_TIMEOUT") or "12").strip() or 12)


def _json(url):
    try:
        rq = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(rq, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:                                        # noqa: BLE001
        return None


def _cena(dyal):
    """Десетичната цена от един дял (homeTeamOdds / awayTeamOdds). None ако няма.

    ESPN държи три снимки: open, current, close. Взимаме ТЕКУЩАТА, защото тя е
    цената в мига, в който картата излиза — тя е сравнимата. „close" е празна,
    докато мачът не е започнал.
    """
    if not isinstance(dyal, dict):
        return None
    for kade in ("current", "open", "close"):
        v = dyal.get(kade)
        if not isinstance(v, dict):
            continue
        ml = v.get("moneyLine")
        if isinstance(ml, dict):
            ml = ml.get("value")
        try:
            c = float(ml)
        except (TypeError, ValueError):
            continue
        # Десетична цена под 1.01 или над 100 е боклук, не оферта.
        if 1.01 <= c <= 100.0:
            return round(c, 2)
    return None


def _amerikanski(v):
    """Американска цена -> десетична. -145 значи 1.69, +310 значи 4.10.

    ЗАЩО СЪЩЕСТВУВА (18.08.2026). ESPN дава РАВНИЯ във футбола САМО така:
    `drawOdds = {"moneyLine": 310.0}` — плоско число, без open/current/close.
    Измерено на живо: 38 от 38 футболни мача. Тоест без този четец равният
    липсва ВИНАГИ, а без равния маржът на букмейкъра не може да се махне.

    ОТДЕЛНА функция, не разхлабване на `_cena`: там проверката „американски
    формат не се бърка за десетичен" пази вложения път и остава непокътната.
    """
    try:
        a = float(v)
    except (TypeError, ValueError):
        return None
    if a >= 100.0:
        return round(1.0 + a / 100.0, 2)
    if a <= -100.0:
        return round(1.0 + 100.0 / abs(a), 2)
    return None


def _cena_pak(dyal):
    """Първо вложената десетична, после плоското американско число на върха.

    Сверено на живо 18.08.2026: 94 от 94 дяла домакин/гост дават ЕДНО И СЪЩО
    число по двата пътя, НУЛА разминавания. Тоест падането назад не мени цена,
    а само запълва дупка.
    """
    c = _cena(dyal)
    if c is not None:
        return c
    if isinstance(dyal, dict):
        return _amerikanski(dyal.get("moneyLine"))
    return None


def cena_za(sport_path, liga, ev_id):
    """(цена_домакин, цена_гост, цена_равен) — всяка може да е None."""
    if not ev_id or not liga or sport_path not in IMA_PAZAR:
        return (None, None, None)
    kl = (sport_path, liga, str(ev_id))
    if kl in _kesh:
        return _kesh[kl]
    rez = (None, None, None)
    j = _json("%s/%s/leagues/%s/events/%s/competitions/%s/odds"
              % (CORE, sport_path, liga, ev_id, ev_id))
    for x in ((j or {}).get("items") or []):
        dom = _cena_pak(x.get("homeTeamOdds"))
        gost = _cena_pak(x.get("awayTeamOdds"))
        raven = _cena_pak(x.get("drawOdds"))
        if dom or gost:
            rez = (dom, gost, raven)
            break
    _kesh[kl] = rez
    return rez


# ═══════════════════════════════════ ТЪРСЕНЕ ПО ИМЕНА (13.08.2026)
#
# Не всяка среща идва от ESPN. Бейзболът например се дърпа от statsapi.mlb.com
# и НЯМА ESPN номер — тоест дупката е точно там, където имаме 48 прогнози.
#
# Затова: вадим номера от ESPN scoreboard-а за същия ден, като сверяваме по
# ИМЕНА на отборите. Един запитан адрес на лига-ден (кеширан), после цената.
SITE = "https://site.api.espn.com/apis/site/v2/sports"
_index = {}


def _norm(s):
    """Име, сведено до сравнимо: малки букви, само букви и цифри."""
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def _dumi(s):
    """Множество от думите в името — за частично съвпадение."""
    return {w for w in _norm(s and str(s).lower().replace("-", " ")).split() if w}


# 🔴 ПРОЗОРЕЦЪТ ОКОЛО НАЧАЛОТО (18.08.2026) — ПОПРАВКА НА ЧЕРВЕН ДЕФЕКТ.
#
# В МЛБ едни и същи два отбора играят серия по 3-4 вечери. Ключът за търсене
# беше само двете имена, а обхождането на три дати връщаше ПЪРВАТА, която дава
# число. Тоест щом днешният мач още няма цена (нормално, пускат я късно), се
# връщаше цената на ВЧЕРАШНИЯ мач между същите отбори — с други питчъри, друг
# ден — и се записваше с pazar_v=2, тоест като годна за мерилото.
#
# Измерено през живия `dobavi_pazar`: 5 от 15 мача на 19.08 получаваха цена от
# чуждо събитие. Отделно ev_za_imena сочеше ЧУЖД номер за 15 от 15.
#
# Сега индексът носи и часа, а изборът е НАЙ-БЛИЗКИЯТ до нашето начало, и то
# само ако е в прозореца. Без начало (не го знаем) — държим се както преди,
# защото друго няма.
PROZOREC_CH = float((os.environ.get("PAZAR_PROZOREC") or "6").strip() or 6)


def _chas(iso):
    """ISO низ -> aware datetime. None при боклук."""
    from datetime import datetime as _dt, timezone as _tz
    t = str(iso or "").strip().replace("Z", "+00:00")
    for vid in ("%Y-%m-%dT%H:%M%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return _dt.strptime(t, vid)
        except ValueError:
            continue
    try:
        return _dt.fromisoformat(t)
    except (ValueError, TypeError):
        return None


def _razlika_ch(a_iso, kogato):
    """Разлика в часове между събитие и нашето начало. None ако не се знае."""
    if kogato is None:
        return None
    a = _chas(a_iso)
    if a is None:
        return None
    try:
        if a.tzinfo is None or kogato.tzinfo is None:
            return None
        return abs((a - kogato).total_seconds()) / 3600.0
    except (TypeError, ValueError):
        return None


def index_za_den(sport_path, liga, ymd):
    """{frozenset(две нормализирани имена): (номер, час)} за един ден. Кеширано."""
    kl = (sport_path, liga, ymd)
    if kl in _index:
        return _index[kl]
    idx = {}
    j = _json("%s/%s/%s/scoreboard?dates=%s" % (SITE, sport_path, liga, ymd))
    for e in ((j or {}).get("events") or []):
        for c in (e.get("competitions") or []):
            imena = []
            for x in (c.get("competitors") or []):
                tm = x.get("team") or {}
                imena.append(_norm(tm.get("displayName") or tm.get("name")
                                   or tm.get("shortDisplayName")))
            if len(imena) == 2 and all(imena):
                idx[frozenset(imena)] = (str(e.get("id") or ""),
                                         str(e.get("date") or ""))
    _index[kl] = idx
    return idx


def _kandidati(sport_path, liga, ymd, dom, gost):
    """[(номер, час)] — всички събития от трите дати, които пасват по имена."""
    kl = frozenset((_norm(dom), _norm(gost)))
    try:
        from datetime import datetime as _dt, timedelta as _td
        d0 = _dt.strptime(str(ymd), "%Y%m%d")
        dati = [(d0 + _td(days=k)).strftime("%Y%m%d") for k in (0, -1, 1)]
    except ValueError:
        dati = [str(ymd)]
    out, vid = [], set()
    for den in dati:
        idx = index_za_den(sport_path, liga, den)
        k = idx.get(kl)
        if k and k[0] and k[0] not in vid:
            vid.add(k[0])
            out.append(k)
    if out:
        return out
    # Частично съвпадение: „Tampa Bay Rays" срещу „Rays". И двете наши имена
    # да се съдържат в техните (или обратно), в която и да е посока.
    nd, ng = _norm(dom), _norm(gost)
    for den in dati:
        for kk, v in index_za_den(sport_path, liga, den).items():
            a, b = tuple(kk)
            if (((nd in a or a in nd) and (ng in b or b in ng))
                    or ((nd in b or b in nd) and (ng in a or a in ng))):
                if v and v[0] and v[0] not in vid:
                    vid.add(v[0])
                    out.append(v)
    return out


def _izbor(kand, kogato):
    """Кой от кандидатите е НАШИЯТ мач. [(номер, час)] подредени по близост.

    С известно начало: само тези в прозореца, най-близкият пръв.
    Без начало: всички, в реда на намиране — друго не можем да направим.
    """
    if kogato is None:
        return [k[0] for k in kand]
    s_ch = []
    for ev, iso in kand:
        d = _razlika_ch(iso, kogato)
        if d is None:
            continue
        if d <= PROZOREC_CH:
            s_ch.append((d, ev))
    s_ch.sort()
    return [ev for _d, ev in s_ch]


def cena_po_imena(sport_path, liga, ymd, dom, gost, kogato=None):
    """Цената, намерена по имена вместо по номер. (дом, гост, равен).

    🔴 ПИТАТ СЕ ТРИ ДАТИ. ESPN индексира по АМЕРИКАНСКА дата, а мач в 01:40
    българско е още „вчера" при тях. Без това цената се губеше точно за
    нощните мачове, а в бейзбола те са половината.

    🔴 И СЕ СВЕРЯВА ЧАСЪТ (18.08.2026). Иначе серия от три вечери между едни и
    същи отбори дава цената на ГРЕШНАТА вечер — измерено, 5 от 15 мача.
    """
    if sport_path not in IMA_PAZAR or not liga or not ymd:
        return (None, None, None)
    if len(frozenset((_norm(dom), _norm(gost)))) != 2 or not (_norm(dom) and _norm(gost)):
        return (None, None, None)
    for ev in _izbor(_kandidati(sport_path, liga, ymd, dom, gost), kogato):
        rez = cena_za(sport_path, liga, ev)
        if rez[0] or rez[1]:
            return rez
    return (None, None, None)


def ev_za_imena(sport_path, liga, ymd, dom, gost, kogato=None):
    """Номерът на НАШАТА среща, намерен по имена. None, ако не се намери.

    Ползва СЪЩИЯ кеширан индекс като cena_po_imena — извикана веднага след
    нея, не струва нито една нова заявка. Номерът влиза в дневника, за да може
    оценителят после да вземе затварящата цена. Затова е КРИТИЧНО да е нашият
    мач: сгрешен номер значи затваряща цена на чужда среща.
    """
    if sport_path not in IMA_PAZAR or not liga or not ymd:
        return None
    if len(frozenset((_norm(dom), _norm(gost)))) != 2 or not (_norm(dom) and _norm(gost)):
        return None
    r = _izbor(_kandidati(sport_path, liga, ymd, dom, gost), kogato)
    return r[0] if r else None

def veroyatnost(cena):
    """Цена → вероятност. 2.00 значи 50%. None при боклук."""
    try:
        c = float(cena)
    except (TypeError, ValueError):
        return None
    return (1.0 / c) if c > 1.0 else None


# ============================== МАРЖЪТ НА БУКМЕЙКЪРА (18.08.2026)
#
# `1/цена` НЕ Е вероятността на пазара. Букмейкърът зарежда цените така, че
# сборът по всички изходи да е НАД 100% — разликата е неговият дял.
#
# Измерено на живо, 18.08.2026, 50 събития:
#   футбол      сбор 1.0738  (1.0557 – 1.0885)  ->  7.4% отгоре
#   бейзбол     сбор 1.0192  (1.0173 – 1.0211)  ->  1.9% отгоре
#   баскетбол   сбор 1.0476                     ->  4.8% отгоре
#
# Тоест суровото `1/цена` показва пазара по-уверен, отколкото е — до 3.4 точки
# на изход при футбола. А прагът, с който мерим „не сме съгласни с пазара", е
# ДВЕ точки. Без тази поправка кантарът е крив, преди да е претеглил първия път.
#
# НОРМАЛИЗИРАМЕ САМО ПРИ ПЪЛЕН НАБОР. Ако липсва изход, сборът пада ПОД 1 и
# деленето би НАДУЛО останалите вместо да ги свие. Измерено при липсващ равен:
# сбор 0.8151 средно — „поправката" щеше да е 4.5 пъти по-лоша от болестта.
# „soccer" е името на ESPN, „football" — нашето. Един и същи спорт,
# две азбуки: вторият източник (pinnacle.py) ползва нашето.
IZHODI = {"soccer": 3, "football": 3}


def bez_marzh(sport_path, dom, gost, raven=None):
    """(p_дом, p_гост, p_равен) с махнат марж. (None,None,None) при непълен набор."""
    n = IZHODI.get(str(sport_path or ""), 2)
    p = []
    for c in [dom, gost, raven][:n]:
        v = veroyatnost(c)
        if v is None:
            return (None, None, None)
        p.append(v)
    sbor = sum(p)
    # Сбор ПОД 1 значи липсващ изход въпреки проверката; над 1.6 значи боклук.
    # И в двата случая по-добре без число, отколкото с грешно число.
    if not (1.0 < sbor <= 1.6):
        return (None, None, None)
    out = [round(v / sbor, 4) for v in p]
    return tuple(out + [None] * (3 - len(out)))


# ============================== ЗАТВАРЯЩАТА ЦЕНА (18.08.2026)
#
# Единственото доказателство за ръб, което не зависи от късмет.
#
# 69% познати не значи нищо само по себе си: фаворит на цена 1.30, познат в
# 69% от случаите, ГУБИ пари. Въпросът не е „колко често сме прави", а „движи
# ли се пазарът към нас, след като сме казали".
#
# Затова: цената при ПУСКАНЕ вече се пази. Тук се взима цената при ЗАТВАРЯНЕ —
# последната, преди мачът да тръгне. Ако нашият избор е поевтинял между двете,
# пазарът е дошъл при нас. Това се нарича CLV и по него професионалистите се
# съдят помежду си, защото работи и при 20 залога, докато „процент познати"
# иска стотици.
#
# ESPN пази трите снимки в един и същ дял: open, current, close. Затова
# затварящата НЕ струва нов вид заявка — само още едно питане, СЛЕД мача.
def _cena_close(dyal):
    """САМО затварящата цена. None, ако още я няма (мачът не е започнал)."""
    if not isinstance(dyal, dict):
        return None
    v = dyal.get("close")
    if not isinstance(v, dict):
        return None
    ml = v.get("moneyLine")
    if isinstance(ml, dict):
        ml = ml.get("value")
    try:
        c = float(ml)
    except (TypeError, ValueError):
        return _amerikanski(v.get("moneyLine")
                            if not isinstance(v.get("moneyLine"), dict) else None)
    if 1.01 <= c <= 100.0:
        return round(c, 2)
    return _amerikanski(ml)


def cena_zatvarayashta(sport_path, liga, ev_id):
    """(дом, гост, равен) при ЗАТВАРЯНЕ. Всяка може да е None."""
    if not ev_id or not liga or sport_path not in IMA_PAZAR:
        return (None, None, None)
    kl = ("close", sport_path, liga, str(ev_id))
    if kl in _kesh:
        return _kesh[kl]
    rez = (None, None, None)
    j = _json("%s/%s/leagues/%s/events/%s/competitions/%s/odds"
              % (CORE, sport_path, liga, ev_id, ev_id))
    for x in ((j or {}).get("items") or []):
        dom = _cena_close(x.get("homeTeamOdds"))
        gost = _cena_close(x.get("awayTeamOdds"))
        raven = _cena_close(x.get("drawOdds"))
        if dom or gost:
            rez = (dom, gost, raven)
            break
    _kesh[kl] = rez
    return rez


# ============================== РАВНИЯТ ПРИ ЗАТВАРЯНЕ (25.08.2026)
#
# 🔴 ЧЕРВЕН ДЕФЕКТ: РАВНИЯТ НИКОГА НЕ ПОЛУЧАВАШЕ ЗАТВАРЯЩА ЦЕНА.
#
# `_cena_close` иска дял с ключ „close". Домакинът и гостът го имат, щом
# книгата се затвори. РАВНИЯТ НЕ ГО ИМА НИКОГА — ESPN го дава само като плоско
# американско число на върха: `drawOdds = {"moneyLine": 250.0}`, нищо друго.
#
# Измерено на живо 25.08.2026 върху 40 ЗАВЪРШЕНИ футболни мача (eng.1, esp.1,
# ita.1, ger.1, fra.1, por.1 …):
#   равният има собствен „close"        →   0 от 40
#   равният е плоско американско число  →  40 от 40
# Тоест `cena_zatvarayashta("soccer", "eng.1", "401879318")` връщаше
# (3.7, 2.05, None) — два крака от три. Без третия сборът пада ПОД 1, а
# `bez_marzh` нарочно отказва непълен набор → маржът НЕ СЕ МАХАШЕ при
# затварянето и двойният шанс не се смяташе изобщо.
#
# 🔴 ЗАЩО ЧИСЛОТО СЕ ДАВА С ЕТИКЕТ, А НЕ МЪЛЧАЛИВО.
# Това плоско число Е СЪЩОТО, което `cena_za` чете като ТЕКУЩА цена. Никъде не
# пише, че е снимката от съдийския сигнал. Измерено същия ден обаче: при
# завършен мач `current` СЪВПАДА с `close` 40 от 40 пъти и при домакина, и при
# госта — тоест ESPN замразява текущата в мига на затварянето, и плоският
# равен, прочетен СЛЕД края, е замразен в същия миг. „Значи" не е „доказано":
# за самия равен няма втора снимка, с която да се сравни. Затова числото се
# връща, но НОСИ КАКВО Е.
#
# 🔴 И ЕДНО ИЗМЕРВАНЕ, КОЕТО ОБОРИ АЛТЕРНАТИВАТА.
# Възражението „close за двамата + снимка за равния дава несвързан набор, вземи
# целия набор от Pinnacle" е проверено на същите 40 мача и ОТХВЪРЛЕНО:
#   сбор 1/close_дом + 1/close_гост + 1/плосък_равен
#     средно 1.0559, обхват [1.0407 .. 1.0903], 40 от 40 вътре в бандата
# Това е точно измереният футболен обръч (18.08 мерено 1.0738). Смесеният
# набор Е свързан — маржът върху него значи нещо.
VID_CLOSE = "close"      # истинска затваряща снимка на ESPN
VID_SNIMKA = "snimka"    # замразената текуща — НЕ се обявява за затваряща


def _raven_snimka(dyal):
    """Плоското американско число на върха. None, ако дялът има истински „close".

    🔴 ОТДЕЛНА ФУНКЦИЯ, А НЕ РАЗХЛАБВАНЕ НА `_cena_close`. Ако тя падаше назад
    към плоското число, мач, който ОЩЕ НЕ Е ЗАПОЧНАЛ, щеше да върне цена и
    оценителят щеше да запише `pazar_close` преди затварянето — заковавайки
    средата на деня като затваряща завинаги. Строгостта там пази дом и гост.
    """
    if not isinstance(dyal, dict):
        return None
    if isinstance(dyal.get("close"), dict):
        return None                       # има истинска — тук не се месим
    ml = dyal.get("moneyLine")
    if isinstance(ml, dict):
        return None                       # вложено значи друг път, не плоско
    return _amerikanski(ml)


def cena_zatvarayashta_vid(sport_path, liga, ev_id):
    """((дом, гост, равен), (вид_дом, вид_гост, вид_равен)) при ЗАТВАРЯНЕ.

    Видът е VID_CLOSE (истинска затваряща снимка) или VID_SNIMKA (замразената
    текуща — единственото, което ESPN дава за равния). None срещу липсваща цена.

    🔴 ЕТИКЕТЪТ Е ВЪРНАТА СТОЙНОСТ, НЕ РЕД В ДОКУМЕНТАЦИЯТА. Затова
    `cena_zatvarayashta` остава непокътната: който иска равния при затваряне,
    минава оттук и НЯМА КАК да не види, че третият крак е снимка. Етикет,
    написан само в коментар, първият извикващ го подминава.

    🔴 ПАЗАЧЪТ: снимката се дава САМО след като книгата е затворена — тоест
    само ако домакинът или гостът вече имат истински „close". Преди старта тук
    няма равен и записът остава без затваряща цена, вместо да получи цената от
    средата на деня.
    """
    prazno = ((None, None, None), (None, None, None))
    if not ev_id or not liga or sport_path not in IMA_PAZAR:
        return prazno
    kl = ("closevid", sport_path, liga, str(ev_id))
    if kl in _kesh:
        return _kesh[kl]
    rez = prazno
    j = _json("%s/%s/leagues/%s/events/%s/competitions/%s/odds"
              % (CORE, sport_path, liga, ev_id, ev_id))
    for x in ((j or {}).get("items") or []):
        dom = _cena_close(x.get("homeTeamOdds"))
        gost = _cena_close(x.get("awayTeamOdds"))
        if not (dom or gost):
            continue                      # книгата още не е затворена
        raven, vid_r = _cena_close(x.get("drawOdds")), VID_CLOSE
        if raven is None:
            raven, vid_r = _raven_snimka(x.get("drawOdds")), VID_SNIMKA
        rez = ((dom, gost, raven),
               (VID_CLOSE if dom is not None else None,
                VID_CLOSE if gost is not None else None,
                vid_r if raven is not None else None))
        break
    _kesh[kl] = rez
    return rez


# ============================== ЗАТВАРЯЩАТА ОТ PINNACLE (25.08.2026)
#
# 🔴 73 КАРТИ БЕЗ НИТО ЕДИН ПЪТ ДО ЗАТВАРЯЩА ЦЕНА.
# Сверено на живо в дневника на хранилището 25.08.2026 (predict_log.json,
# sha db04f50, 737 записа):
#   pazar_izt = "espn"      134 записа · 134 от тях с pazar_ev  → имат път
#   pazar_izt = "pinnacle"   73 записа ·   0 от тях с pazar_ev  → НЯМАТ път
#   pazar_izt = "vitrina"    20 записа                          → няма път
# От 73-те без път: тенис 43, футбол 9, баскетбол 8, бейзбол 8, ММА 5. Тоест
# най-силният ни спорт нямаше как да бъде измерен по CLV.
#
# 🔴 „ЗАТВАРЯЩА" ТУК ЗНАЧИ „ПОСЛЕДНАТА ПРЕДИ НАЧАЛОТО", И ТОВА Е ЧЕСТНО.
# Pinnacle няма поле „close" — има само текущата цена. Но маха мача от
# витрината в мига, в който той тръгне: след старта `pazari()` не го намира и
# тук се връща празно. Това не е недостатък, който заобикаляме — то Е пазачът.
# Опресняване след началото не може да презапише нищо, защото няма какво да
# върне. Затова числото, което оцелява в дневника, е последното преди старта.
def cena_zatvarayashta_pin(sport_key, mid, obarnat=False):
    """(дом, гост, равен) от Pinnacle по ВЕЧЕ ЗНАЕН номер. Празно след старта.

    `sport_key` е НАШЕТО име („tennis", „football"…), не пътят на ESPN.
    `mid` и `obarnat` идват от `pinnacle.nomer_strana`, записани при пускането.
    Страните се връщат в НАШИЯ ред — размяната живее в `cena_po_nomer`, за да е
    ЕДНА за двата пътя.

    Нула нови заявки при топъл кеш; две на спорт при студен.
    """
    if not mid:
        return (None, None, None)
    try:
        import pinnacle as PIN
    except Exception:                                        # noqa: BLE001
        return (None, None, None)
    try:
        c = PIN.cena_po_nomer(sport_key, mid, bool(obarnat))
    except Exception:                                        # noqa: BLE001
        return (None, None, None)
    return tuple(c) if isinstance(c, (tuple, list)) and len(c) == 3 else (None, None, None)


NIKOY = ""


def pat_do_zatvaryane(zapis):
    """По кой път ТОЗИ запис може да получи затваряща цена: "espn"/"pinnacle"/"".

    Празният низ е ОТГОВОР, не грешка: 20-те „vitrina" записа и всеки pinnacle
    запис без номер нямат път и трябва да се видят като такива, вместо
    извикващият да гадае и да хаби заявка напразно.

    🔴 РЕДЪТ НА ДВАТА КЛОНА Е СЪЩЕСТВЕН. Бейзболът и баскетболът ги има И при
    ESPN, И при Pinnacle. Ако ESPN се питаше пръв, номер на Pinnacle щеше да
    влезе в ESPN адрес — тоест затваряща цена на СЪВСЕМ ЧУЖД мач, тихо и с вид
    на успех. Затова се съди по етикета `pazar_izt`, а не по спорта.

    🔴 СПОРТЪТ НА PINNACLE СЕ ЧЕТЕ И ОТ `bucket`. Измерено в живия дневник
    25.08.2026: всичките 73 pinnacle записа имат `pazar_sport: null`, а
    `bucket` носи името („tennis", „football"…). Без това падане назад
    функцията щеше да казва „никой" за 73 от 73.
    """
    if not isinstance(zapis, dict):
        return NIKOY
    ev = str(zapis.get("pazar_ev") or "").strip()
    sport = str(zapis.get("pazar_sport") or "").strip()
    liga = str(zapis.get("pazar_liga") or "").strip()
    izt = str(zapis.get("pazar_izt") or "").strip().lower()
    if izt == "pinnacle":
        if not ev:
            return NIKOY
        kl = sport or str(zapis.get("bucket") or "").strip()
        if not kl:
            return NIKOY
        try:
            import pinnacle as PIN
        except Exception:                                    # noqa: BLE001
            return NIKOY
        return "pinnacle" if kl in PIN.SPORT_ID else NIKOY
    if izt and izt != "espn":
        return NIKOY                      # „vitrina" и всеки бъдещ трети
    # Празен етикет = запис отпреди 18.08, когато източникът не се пишеше.
    if ev and liga and sport in IMA_PAZAR:
        return "espn"
    return NIKOY


def dvizhenie(nasha_cena, close_cena):
    """Колко се е преместил пазарът към нас. Положително = дошъл е при нас.

    Смята се във ВЕРОЯТНОСТИ, не в цени: разликата между 1.20 и 1.15 не е
    същата като между 5.00 и 4.95, макар и двете да са „пет стотинки".
    """
    a, b = veroyatnost(nasha_cena), veroyatnost(close_cena)
    if a is None or b is None:
        return None
    return round(b - a, 4)


def red_za_karta(nasha_p, cena_nash_izhod):
    """Редът, който излиза на картата. Празен, ако няма цена.

    Никакво име на оператор, никакъв линк, никаква покана — само две числа
    едно до друго. Думите, които пазачът реже, ги няма нарочно.
    """
    pz = veroyatnost(cena_nash_izhod)
    if pz is None:
        return ""
    try:
        nash = float(nasha_p)
    except (TypeError, ValueError):
        return ""
    # 🔴 БЕЗ КОМЕНТАР (изрична поръчка, 13.08.2026): „не казвай кво оценяваме".
    # Само числото. Читателят вижда нашия процент отгоре и пазарната цена тук,
    # и сам вижда къде се разминават. Нашата дума не му трябва.
    _ = nash, pz
    return "📊 Пазар: " + ("%.2f" % float(cena_nash_izhod))


# ═══════════════════ ИЗТОЧНИКЪТ И ЛИНКЪТ КЪМ МАЧА (01.09.2026)
#
# ДВА КЛЮЧА, И ДВАТА ИЗКЛЮЧЕНИ ПО ПОДРАЗБИРАНЕ. Решението е на собственика,
# не мое — включва се с променлива на средата, не с редакция на код:
#
#   PAZAR_IZTOCHNIK=1  →  „📊 Пазар: 1.85 (ESPN)“            ниво (б)
#   PAZAR_LINK=1       →  добавя и адрес на САМИЯ мач        ниво (в)
#
# 🔴 ИМЕ НА БУКМЕЙКЪР НЕ СЕ ПИШЕ, В НИКАКВА АЗБУКА.
# Проверено на живо с predictor.banned_word: „Pinnacle“ се спира, „Пинакъл“
# МИНАВА. Това не е разрешение — пазачът мери БУКВИ, а забраната е за НЕЩО.
# Затова тук се назовава само ESPN (медия, не оператор), а записите от
# Pinnacle излизат БЕЗ етикет и БЕЗ адрес. Мълчанието е отговорът.
#
# 🔴 И ЕДНО, КОЕТО СОБСТВЕНИКЪТ ТРЯБВА ДА ЗНАЕ, ПРЕДИ ДА ВКЛЮЧИ PAZAR_LINK.
# Сверено в тази сесия със свалена страница: самата страница на мача при ESPN
# съдържа „draftkings“ 51 пъти, „bet365“ 2 пъти и „odds“ 97 пъти. Нашият ред
# е чист, но адресът води при тях. Това е негов избор, не наш — затова ключът
# стои изключен и нищо не се мени, докато той не каже.
PAZAR_LINK_VKL = (os.environ.get("PAZAR_LINK") or "0").strip() in ("1", "true", "да")
PAZAR_IZT_VKL = (os.environ.get("PAZAR_IZTOCHNIK") or "0").strip() in ("1", "true", "да")


def _bezopasen_slug(s):
    """Само букви, цифри и - . _ — иначе празно. Чуждо име не влиза в адрес."""
    t = str(s or "").strip().lower()
    if not t:
        return ""
    return t if all(ch.isalnum() or ch in "-._" for ch in t) else ""


def link_kam_macha(zapis):
    """Адресът на САМИЯ мач при ESPN, или „“ когато такъв не се сглобява.

    🔴 ИЗМЕРЕНО НА ЖИВО 01.09.2026 — истински номер срещу измислен:
        soccer      /soccer/match/_/gameId/401908124  → 200 · измислен → 404
        baseball    /mlb/game/_/gameId/401878657      → 200 · измислен → 404
        basketball  /nba/game/_/gameId/401902644      → 200 · измислен → 404
    Тоест правилото НЕ Е „по спорта“: футболът ползва думата match и пътя
    soccer, а другите — думата game и пътя на ЛИГАТА (mlb, nba). Сверено, че
    /baseball/game/… и /basketball/game/… дават 404. Затова двата клона.

    Само ESPN. Pinnacle НЯМА проверим адрес: същия ден техният сайт върна 200
    и ЕДИН И СЪЩ отговор от 14258 байта за истински номер, за нулев номер и за
    пълна безсмислица — тоест кодът 200 там не доказва нищо и не бива да се
    приема за доказателство.
    """
    z = zapis if isinstance(zapis, dict) else {}
    if pat_do_zatvaryane(z) != "espn":
        return ""
    ev = str(z.get("pazar_ev") or "").strip()
    if not ev.isdigit():
        return ""
    sport = _bezopasen_slug(z.get("pazar_sport"))
    liga = _bezopasen_slug(z.get("pazar_liga"))
    if sport == "soccer":
        return "https://www.espn.com/soccer/match/_/gameId/" + ev
    if not liga:
        return ""
    return "https://www.espn.com/" + liga + "/game/_/gameId/" + ev


def red_za_karta_puln(nasha_p, cena_nash_izhod, zapis=None):
    """Редът за картата с толкова, колкото ключовете разрешават.

    С двата ключа изключени връща ТОЧНО каквото връща red_za_karta — тоест
    закачането ѝ вместо старата функция не мени нито един знак, докато
    собственикът не реши. Това е пътят назад: изключи ключа, върни се.
    """
    red = red_za_karta(nasha_p, cena_nash_izhod)
    if not red:
        return ""
    if PAZAR_IZT_VKL:
        izt = str((zapis or {}).get("pazar_izt") or "").strip().lower()
        if izt == "espn":
            red += " (ESPN)"
    if PAZAR_LINK_VKL:
        adres = link_kam_macha(zapis or {})
        if adres:
            red += " · " + adres
    return red


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    check("2.00 значи 50%", abs(veroyatnost(2.0) - 0.5) < 1e-9)
    check("1.25 значи 80%", abs(veroyatnost(1.25) - 0.8) < 1e-9)
    check("цена 1.0 не дава вероятност", veroyatnost(1.0) is None)
    check("боклук не гърми", veroyatnost("абв") is None and veroyatnost(None) is None)

    check("текущата цена се чете",
          _cena({"current": {"moneyLine": {"value": 1.91}}}) == 1.91)
    check("пада на open, ако няма current",
          _cena({"open": {"moneyLine": {"value": 2.4}}}) == 2.4)
    check("плоско число също се чете",
          _cena({"current": {"moneyLine": 1.55}}) == 1.55)
    check("цена под 1.01 се отхвърля",
          _cena({"current": {"moneyLine": {"value": 1.0}}}) is None)
    check("цена над 100 се отхвърля",
          _cena({"current": {"moneyLine": {"value": 250}}}) is None)
    check("празен дял не гърми", _cena({}) is None and _cena(None) is None)
    check("американски формат не се бърка за десетичен",
          _cena({"current": {"moneyLine": {"value": -110}}}) is None)

    check("американско +310 значи 4.10", _amerikanski(310) == 4.10)
    check("американско -145 значи 1.69", _amerikanski(-145) == 1.69)
    check("американско +100 значи 2.00", _amerikanski(100) == 2.0)
    check("между -100 и 100 не е американско",
          _amerikanski(50) is None and _amerikanski(-99) is None)
    check("боклук вместо американско не гърми",
          _amerikanski("абв") is None and _amerikanski(None) is None)
    check("плоският равен на ESPN се чете", _cena_pak({"moneyLine": 310.0}) == 4.10)
    check("вложената десетична бие плоската",
          _cena_pak({"moneyLine": -145, "current": {"moneyLine": {"value": 1.70}}}) == 1.70)
    check("_cena остава строга за вложеното американско",
          _cena({"current": {"moneyLine": {"value": -110}}}) is None)

    _b = bez_marzh("soccer", 1.69, 4.50, 4.10)
    check("маржът се маха при пълен набор", abs(sum(_b) - 1.0) < 0.001)
    check("редът на трите се пази", _b[0] > _b[2] > _b[1])
    check("свива, не надува", _b[0] < veroyatnost(1.69))
    check("нашето име на футбола също е тройка",
          bez_marzh("football", 1.69, 4.50, None) == (None, None, None)
          and bez_marzh("football", 1.69, 4.50, 4.10)[2] is not None)
    check("липсващ равен = футболът НЕ се пипа",
          bez_marzh("soccer", 1.69, 4.50, None) == (None, None, None))
    # 🔴 РЕДЪТ ОТДОЛУ НЕ Е ИЗЛИШЕН (18.08.2026). Горният минава и когато
    # липсващият изход просто се ПРЕСКОЧИ, защото тогава сборът пада под 1 и
    # го спира ДРУГИЯТ пазач. При тежък фаворит обаче два изхода вече дават
    # сбор над 1 (0.909 + 0.100) и прескачането минава невидимо. Мутация,
    # която сменя `return` с `continue`, оцеляваше без този ред.
    check("липсващ равен не се заобикаля и при тежък фаворит",
          bez_marzh("soccer", 1.10, 10.0, None) == (None, None, None))
    _b2 = bez_marzh("baseball", 1.91, 2.01)
    check("двупосочният се нормализира без равен",
          abs(_b2[0] + _b2[1] - 1.0) < 0.001 and _b2[2] is None)
    check("равният се пренебрегва при двупосочен",
          bez_marzh("baseball", 1.91, 2.01, 4.0) == _b2)
    check("сбор под 1 не се пипа", bez_marzh("baseball", 2.5, 2.5) == (None, None, None))
    check("абсурден сбор не се пипа", bez_marzh("baseball", 1.05, 1.05) == (None, None, None))
    check("боклук вместо цена не гърми",
          bez_marzh("baseball", None, 2.0) == (None, None, None))

    check("затварящата се чете", _cena_close({"close": {"moneyLine": {"value": 1.65}}}) == 1.65)
    check("текущата НЕ минава за затваряща",
          _cena_close({"current": {"moneyLine": {"value": 1.65}}}) is None)
    check("отварящата НЕ минава за затваряща",
          _cena_close({"open": {"moneyLine": {"value": 1.65}}}) is None)
    check("американска затваряща също се чете",
          _cena_close({"close": {"moneyLine": 310.0}}) == 4.10)
    check("празен дял не гърми",
          _cena_close({}) is None and _cena_close(None) is None)
    check("боклук в затварящата не гърми",
          _cena_close({"close": {"moneyLine": "абв"}}) is None)

    check("поевтиняване значи пазарът е дошъл при нас",
          dvizhenie(2.00, 1.80) > 0)
    check("поскъпване значи пазарът се е отдалечил",
          dvizhenie(2.00, 2.20) < 0)
    check("същата цена значи нула движение", dvizhenie(2.00, 2.00) == 0)
    check("движението се мери във вероятности, не в стотинки",
          dvizhenie(1.20, 1.15) != dvizhenie(5.00, 4.95))
    check("липсваща цена не дава движение",
          dvizhenie(None, 1.8) is None and dvizhenie(1.8, None) is None)

    check("затварящата не се пита за спорт без пазар",
          cena_zatvarayashta("tennis", "atp", "123") == (None, None, None))
    check("затварящата не се пита без номер",
          cena_zatvarayashta("baseball", "mlb", "") == (None, None, None))

    check("спорт без пазар не се пита",
          cena_za("tennis", "atp", "123") == (None, None, None))
    check("липсващ номер не се пита",
          cena_za("baseball", "mlb", "") == (None, None, None))

    r = red_za_karta(0.62, 2.00)
    check("редът казва цената", "2.00" in r)
    check("редът е само число", r.count(" ") <= 2)
    check("редът НЕ коментира нашата оценка",
          not any(w in r for w in ("оценяваме", "по-високо", "по-ниско", "колкото")))
    check("еднакъв ред при различна наша оценка",
          red_za_karta(0.51, 2.00) == red_za_karta(0.90, 2.00))
    check("цената се закръгля до два знака", "1.91" in red_za_karta(0.5, 1.9123))
    check("без цена няма ред", red_za_karta(0.62, None) == "")
    check("боклук вместо наша вероятност не гърми",
          red_za_karta("абв", 2.0) == "")

    # 🔴 НАЙ-ВАЖНОТО: редът не бива да носи име на оператор, линк или покана.
    # Пазачът в predictor.py реже точно тези думи, защото българският закон
    # забранява рекламата на хазарт.
    zabraneni = ("draftkings", "bet365", "sportsbook", "http", "залож",
                 "букмейкър", "коеф", "odds", "залагай")
    for nasha, cena in ((0.62, 2.0), (0.40, 2.0), (0.51, 2.0), (0.90, 1.05)):
        red = red_za_karta(nasha, cena).lower()
        for z in zabraneni:
            check("редът е чист от " + z, z not in red)

    # ── ЛИНКЪТ КЪМ МАЧА (01.09.2026)
    _fb = {"pazar_izt": "espn", "pazar_ev": "401908124",
           "pazar_sport": "soccer", "pazar_liga": "eng.league_cup"}
    _bb = {"pazar_izt": "espn", "pazar_ev": "401878657",
           "pazar_sport": "baseball", "pazar_liga": "mlb"}
    check("футболът ползва пътя soccer и думата match",
          link_kam_macha(_fb) == "https://www.espn.com/soccer/match/_/gameId/401908124")
    check("бейзболът ползва пътя на ЛИГАТА и думата game",
          link_kam_macha(_bb) == "https://www.espn.com/mlb/game/_/gameId/401878657")
    # 🔴 МУТАЦИИТЕ: всяка от тях трябва да върне празно, не крив адрес.
    check("Pinnacle няма адрес",
          link_kam_macha(dict(_fb, pazar_izt="pinnacle")) == "")
    check("витрината няма адрес",
          link_kam_macha(dict(_fb, pazar_izt="vitrina")) == "")
    check("без номер няма адрес", link_kam_macha(dict(_fb, pazar_ev=None)) == "")
    check("номер, който не е число, няма адрес",
          link_kam_macha(dict(_fb, pazar_ev="401x/../зло")) == "")
    check("чужд знак в лигата не влиза в адрес",
          link_kam_macha(dict(_bb, pazar_liga="mlb/../evil")) == "")
    check("не-речник не гърми", link_kam_macha("абв") == "")
    check("спорт без пазар няма адрес",
          link_kam_macha(dict(_fb, pazar_sport="tennis", pazar_liga="atp")) == "")

    # ИЗКЛЮЧЕНИТЕ КЛЮЧОВЕ НЕ МЕНЯТ НИЩО — това е пътят назад.
    if not PAZAR_LINK_VKL and not PAZAR_IZT_VKL:
        check("с изключени ключове редът е дословно старият",
              red_za_karta_puln(0.62, 2.00, _fb) == red_za_karta(0.62, 2.00))
    check("без цена няма ред и в пълния вид",
          red_za_karta_puln(0.62, None, _fb) == "")

    # 🔴 И ПЪЛНИЯТ РЕД МИНАВА ПАЗАЧА. Списъкът е същият като по-долу, но без
    # „http“: на ниво (в) адресът Е самата поръчка и не може да е забранен.
    _bez_http = ("draftkings", "bet365", "sportsbook", "залож", "букмейкър",
                 "коеф", "odds", "залагай", "pinnacle", "пинакъл")
    for _z in (_fb, _bb):
        _r = (red_za_karta_puln(0.62, 2.00, _z) + " "
              + link_kam_macha(_z)).lower()
        for _w in _bez_http:
            check("пълният ред е чист от " + _w, _w not in _r)

    # Търсене по имена — без мрежа, с подхвърлен индекс.
    _star = globals().get("index_za_den")
    _star_cena = globals().get("cena_za")
    try:
        # 🔴 ДВА мача между СЪЩИТЕ отбори в две поредни вечери — точно случаят,
        # който днес връщаше цената на грешния. 401 е нашият (19.08 16:35Z),
        # 400 е вчерашният (18.08 22:40Z) и САМО ТОЙ има цена.
        globals()["index_za_den"] = lambda s, l, y: {
            frozenset(("tampabayrays", "torontobluejays")):
                (("401", "2026-08-19T16:35Z") if y == "20260819"
                 else ("400", "2026-08-18T22:40Z"))}
        globals()["cena_za"] = lambda s, l, e: ((2.10, 1.75, None)
                                                if e == "400" else (None, None, None))
        from datetime import datetime as _D, timezone as _TZ
        _nash = _D(2026, 8, 19, 16, 35, tzinfo=_TZ.utc)     # нашият мач
        _vcher = _D(2026, 8, 18, 22, 40, tzinfo=_TZ.utc)    # вчерашният

        # 🔴 СЪРЦЕВИНАТА НА ПОПРАВКАТА. Без известен час — старото поведение:
        # взима каквото има цена. С известен час — НЕ взима чужда вечер.
        check("без известен час се държим както преди",
              cena_po_imena("baseball", "mlb", "20260819",
                            "Tampa Bay Rays", "Toronto Blue Jays")[0] == 2.10)
        check("с нашия час НЕ взима цената на вчерашния мач",
              cena_po_imena("baseball", "mlb", "20260819", "Tampa Bay Rays",
                            "Toronto Blue Jays", _nash) == (None, None, None))
        check("с вчерашния час взима вчерашната цена",
              cena_po_imena("baseball", "mlb", "20260819", "Tampa Bay Rays",
                            "Toronto Blue Jays", _vcher)[0] == 2.10)
        check("номерът е на НАШИЯ мач, не на съседния",
              ev_za_imena("baseball", "mlb", "20260819", "Tampa Bay Rays",
                          "Toronto Blue Jays", _nash) == "401")
        check("номерът за вчерашния час е на вчерашния мач",
              ev_za_imena("baseball", "mlb", "20260819", "Tampa Bay Rays",
                          "Toronto Blue Jays", _vcher) == "400")
        check("час извън прозореца не намира нищо",
              ev_za_imena("baseball", "mlb", "20260819", "Tampa Bay Rays",
                          "Toronto Blue Jays",
                          _D(2026, 8, 25, 16, 35, tzinfo=_TZ.utc)) is None)
        check("прозорецът е поне 4 часа", PROZOREC_CH >= 4.0)
        check("часът се чете и с Z, и с отместване",
              _chas("2026-08-19T16:35Z") is not None
              and _chas("2026-08-19T16:35:00+03:00") is not None)
        check("боклук вместо час не гърми", _chas("абв") is None and _chas(None) is None)

        check("точното име намира мача",
              cena_po_imena("baseball", "mlb", "20260813",
                            "Tampa Bay Rays", "Toronto Blue Jays")[0] == 2.10)
        check("разменените страни пак намират мача",
              cena_po_imena("baseball", "mlb", "20260813",
                            "Toronto Blue Jays", "Tampa Bay Rays")[0] == 2.10)
        check("късото име също намира",
              cena_po_imena("baseball", "mlb", "20260813",
                            "Rays", "Blue Jays")[0] == 2.10)
        check("мач от предния ден по американско време също се намира",
              cena_po_imena("baseball", "mlb", "20260814",
                            "Tampa Bay Rays", "Toronto Blue Jays")[0] == 2.10)
        check("непознат мач не дава цена",
              cena_po_imena("baseball", "mlb", "20260813", "А", "Б") == (None, None, None))
        check("еднакви имена не дават цена",
              cena_po_imena("baseball", "mlb", "20260813", "Rays", "Rays")
              == (None, None, None))
        check("спорт без пазар не се пита",
              cena_po_imena("tennis", "atp", "20260813", "A", "B") == (None, None, None))
        check("номерът се вади и без известен час",
              ev_za_imena("baseball", "mlb", "20260813",
                          "Tampa Bay Rays", "Toronto Blue Jays") is not None)
        check("непознат мач не дава номер",
              ev_za_imena("baseball", "mlb", "20260813", "А", "Б") is None)
    finally:
        # Подхвърленото се ВРЪЩА. Иначе след самопроверка в същия процес
        # живият `cena_za` остава макет и цените изчезват мълчаливо.
        if _star is not None:
            globals()["index_za_den"] = _star
        if _star_cena is not None:
            globals()["cena_za"] = _star_cena

    # ═════════ РАВНИЯТ ПРИ ЗАТВАРЯНЕ (25.08.2026) — ПОВЕДЕНЧЕСКИ
    check("плоският равен се чете като снимка", _raven_snimka({"moneyLine": 250.0}) == 3.5)
    check("дял с истински close НЕ минава за снимка",
          _raven_snimka({"close": {"moneyLine": {"value": 3.2}}, "moneyLine": 250.0}) is None)
    check("вложеното moneyLine не е плоска снимка",
          _raven_snimka({"moneyLine": {"value": 3.5}}) is None)
    check("боклук вместо снимка не гърми",
          _raven_snimka({}) is None and _raven_snimka(None) is None
          and _raven_snimka({"moneyLine": "абв"}) is None)
    check("двата вида носят РАЗЛИЧНИ думи", VID_CLOSE != VID_SNIMKA)

    # Подхвърля се СУРОВИЯТ отговор на ESPN, точно както изглежда живо:
    # дом и гост с „close", равният САМО с плоско американско число.
    _star_json = globals().get("_json")
    try:
        def _mak(dc, gc, rp, rc=None):
            h = {"current": {"moneyLine": {"value": 3.7}}}
            a = {"current": {"moneyLine": {"value": 2.05}}}
            d = {}
            if dc is not None:
                h["close"] = {"moneyLine": {"value": dc}}
            if gc is not None:
                a["close"] = {"moneyLine": {"value": gc}}
            if rp is not None:
                d["moneyLine"] = rp
            if rc is not None:
                d["close"] = {"moneyLine": {"value": rc}}
            return {"items": [{"homeTeamOdds": h, "awayTeamOdds": a, "drawOdds": d}]}

        # ЗАВЪРШЕН мач — точно формата на Chelsea at Fulham, мерен на 25.08.
        globals()["_json"] = lambda u: _mak(3.7, 2.05, 250.0)
        _kesh.clear()
        _c, _v = cena_zatvarayashta_vid("soccer", "eng.1", "401879318")
        check("равният при затваряне ВЕЧЕ ГО ИМА", _c[2] == 3.5)
        check("домакинът и гостът си остават затварящи", _c[:2] == (3.7, 2.05))
        check("видът на равния е СНИМКА, не затваряща",
              _v == (VID_CLOSE, VID_CLOSE, VID_SNIMKA))
        # 🔴 СЛЕДСТВИЕТО, ЗАРАДИ КОЕТО ВСИЧКО ТОВА СЕ ПРАВИ. Без третия крак
        # сборът падаше под 1 и `bez_marzh` отказваше — маржът не се махаше.
        _bz = bez_marzh("soccer", _c[0], _c[1], _c[2])
        # 🔴 ПЪЛНОТАТА СЕ ПИТА ПРЕДИ СМЯТАНЕТО (25.08.2026). Първият вид на
        # тези два реда събаряше целия пакет с TypeError, щом равният го нямаше —
        # тоест проверката, която пази поправката, скриваше всичко след себе
        # си. Мерено с мутация: 1 гръмнала вместо 2 счупени.
        _pln = all(v is not None for v in _bz)
        check("маржът ВЕЧЕ се маха при затваряне",
              _pln and abs(sum(_bz) - 1.0) < 0.001)
        check("двойният шанс се смята при затваряне",
              _pln and 0.0 < (_bz[0] + _bz[2]) < 1.0)
        # 🔴 ПАЗАЧЪТ. Преди книгата да е затворена НЯМА равен — иначе средата
        # на деня щеше да се закове като затваряща цена.
        globals()["_json"] = lambda u: _mak(None, None, 250.0)
        _kesh.clear()
        check("преди затварянето снимката НЕ се дава",
              cena_zatvarayashta_vid("soccer", "eng.1", "1")
              == ((None, None, None), (None, None, None)))
        # Ако ESPN някога даде истинска затваряща за равния, тя бие снимката.
        globals()["_json"] = lambda u: _mak(3.7, 2.05, 250.0, 3.2)
        _kesh.clear()
        _c3, _v3 = cena_zatvarayashta_vid("soccer", "eng.1", "3")
        check("истинската затваряща на равния бие снимката",
              _c3[2] == 3.2 and _v3[2] == VID_CLOSE)
        # Старата функция НЕ Е ПИПАНА: строгият смисъл остава непокътнат.
        globals()["_json"] = lambda u: _mak(3.7, 2.05, 250.0)
        _kesh.clear()
        check("cena_zatvarayashta остава строга за равния",
              cena_zatvarayashta("soccer", "eng.1", "401879318") == (3.7, 2.05, None))
    finally:
        if _star_json is not None:
            globals()["_json"] = _star_json
        _kesh.clear()

    # ═════════ ЗАТВАРЯЩАТА ОТ PINNACLE (25.08.2026) — ПОВЕДЕНЧЕСКИ
    # Витрината се подхвърля цяла, за да не се пипа мрежата. Номерът и цената
    # са ИСТИНСКИ, свалени живо същия ден: ITF Men Taipei R1.
    import types as _types
    _star_pin = sys.modules.get("pinnacle")
    try:
        _fal = _types.ModuleType("pinnacle")
        _fal.SPORT_ID = {"tennis": 33, "football": 29, "baseball": 3, "mma": 22}
        _vitr = {"1634713719": (2.57, 1.48, None)}

        def _cpn(sk, mid, obarnat=False):
            c = _vitr.get(str(mid))
            if not c:
                return (None, None, None)
            return (c[1], c[0], c[2]) if obarnat else c
        _fal.cena_po_nomer = _cpn
        sys.modules["pinnacle"] = _fal

        check("цената по знаен номер идва от Pinnacle",
              cena_zatvarayashta_pin("tennis", "1634713719") == (2.57, 1.48, None))
        check("обърнатият запис връща страните в НАШИЯ ред",
              cena_zatvarayashta_pin("tennis", "1634713719", True) == (1.48, 2.57, None))
        # 🔴 ПАЗАЧЪТ: щом мачът е тръгнал, него го няма на витрината → празно,
        # нищо не се презаписва. Точно това прави числото „последното преди старта".
        check("мач, махнат от витрината, не дава цена",
              cena_zatvarayashta_pin("tennis", "999999999") == (None, None, None))
        check("без номер изобщо не се пита",
              cena_zatvarayashta_pin("tennis", None) == (None, None, None)
              and cena_zatvarayashta_pin("tennis", "") == (None, None, None))

        check("espn запис върви по espn",
              pat_do_zatvaryane({"pazar_izt": "espn", "pazar_ev": "401908124",
                                 "pazar_sport": "soccer",
                                 "pazar_liga": "eng.league_cup"}) == "espn")
        # 🔴 73 от 73 живи pinnacle записа имат `pazar_sport: null`.
        check("pinnacle запис без pazar_sport върви по bucket",
              pat_do_zatvaryane({"pazar_izt": "pinnacle", "pazar_ev": "1634713719",
                                 "pazar_sport": None, "bucket": "tennis"}) == "pinnacle")
        # 🔴 РЕДЪТ: бейзболът го има при ДВАТА източника. Номер на Pinnacle,
        # пратен по ESPN адрес, дава затваряща цена на съвсем чужд мач.
        check("pinnacle бейзбол НЕ се праща по пътя на ESPN",
              pat_do_zatvaryane({"pazar_izt": "pinnacle", "pazar_ev": "77",
                                 "pazar_sport": "baseball",
                                 "pazar_liga": "mlb"}) == "pinnacle")
        check("pinnacle без номер няма път",
              pat_do_zatvaryane({"pazar_izt": "pinnacle", "pazar_ev": None,
                                 "bucket": "tennis"}) == "")
        check("непознат за Pinnacle спорт няма път",
              pat_do_zatvaryane({"pazar_izt": "pinnacle", "pazar_ev": "5",
                                 "bucket": "cricket"}) == "")
        check("трети източник (vitrina) няма път — и това е ОТГОВОР",
              pat_do_zatvaryane({"pazar_izt": "vitrina", "pazar_ev": "5",
                                 "pazar_sport": "volleyball",
                                 "pazar_liga": "x"}) == "")
        check("espn спорт без пазар няма път",
              pat_do_zatvaryane({"pazar_izt": "espn", "pazar_ev": "5",
                                 "pazar_sport": "tennis",
                                 "pazar_liga": "atp"}) == "")
        check("празен запис няма път и не гърми",
              pat_do_zatvaryane({}) == "" and pat_do_zatvaryane(None) == ""
              and pat_do_zatvaryane("абв") == "")
        check("стар запис без етикет пак върви по espn",
              pat_do_zatvaryane({"pazar_ev": "1", "pazar_sport": "baseball",
                                 "pazar_liga": "mlb"}) == "espn")
    finally:
        # Подхвърленият модул се маха. Инак живият pinnacle остава макет за
        # целия процес и цените на ВСИЧКИ следващи модули изчезват мълчаливо.
        if _star_pin is not None:
            sys.modules["pinnacle"] = _star_pin
        else:
            sys.modules.pop("pinnacle", None)

    # Срещу ИСТИНСКИЯ pinnacle.py — за да гръмне, ако спорт изчезне оттам.
    # Само четене на SPORT_ID; `pat_do_zatvaryane` не пипа мрежата.
    check("тенисът и ММА наистина имат път до Pinnacle",
          pat_do_zatvaryane({"pazar_izt": "pinnacle", "pazar_ev": "1",
                             "bucket": "tennis"}) == "pinnacle"
          and pat_do_zatvaryane({"pazar_izt": "pinnacle", "pazar_ev": "1",
                                 "bucket": "mma"}) == "pinnacle")

    check("броят проверки е поне 133", ok >= 133)
    print("САМОПРОВЕРКА НА ПАЗАРА: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(selftest())
