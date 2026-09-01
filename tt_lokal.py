# -*- coding: utf-8 -*-
"""tt_lokal.py — историята „победи и загуби“ за двете малки лиги на тениса на маса.

ЗАЩО СЪЩЕСТВУВА
Днешните ни 219 карти за тенис на маса са от WTT (Feeder, Smash, Champions).
Те нямат цена: WTT не се търгува никъде — 646 проверени адреса, затворена врата.
tt_ligi.py вече носи Czech Liga Pro и TT Elite Series, които СЕ търгуват и на
които вече знаем цената. Липсваше само едно: ПРОГНОЗА. predictor.model_tabletennis
стъпва на tt_player(ittf_id) — история от WTT по номер на играч, — а редовете на
tt_ligi нямат такъв номер. Този модул е липсващата брънка: строи същата сводка
(победи/загуби) от МИНАЛИТЕ РЕЗУЛТАТИ на самите две лиги, по ИМЕ.

КАК
Smarkets пази архива на лигата 30 дни. За един ден:
    събития (ended)  ->  пазари WINNER_2_WAY  ->  договори  ->  кой е „winner“
Мерено живо на 01.09.2026 за 2026-08-31, TT Elite Series:
    317 събития, 317 отсъдени пазара, 317 победителя = 100.0 % покритие,
    34 заявки, 38.8 секунди.
Тоест резултатите ГИ ИМА и са пълни; скъп е само пътят до тях.

ЗАЩО ЕДИН ДЕН СТИГА ЗА МНОГО
Тези лиги играят с малък състав и огромен обем. Мерено на три поредни дни:
    TT Elite Series : ~306 мача на ден при ~84 играчи, медиана 8 мача/играч
    Czech Liga Pro  : ~183 мача на ден при ~87 играчи, медиана 4 мача/играч
Значи прозорец от една седмица дава по 30-50 мача на играч в TT Elite и по
20-30 в Czech Liga Pro — повече, отколкото WTT дава за година и половина.

🔴 ТРИ НЕЩА, КОИТО ТОЗИ МОДУЛ НЕ ПРАВИ
1. НЕ гадае по фамилия. Ключът на името е НЕПОДРЕДЕН НАБОР ОТ ВСИЧКИ ДУМИ
   (tt_ligi.klyuch_ime), не последната дума. „Andrienko M.“ не се свежда до
   „m“ и не може да залепне за „Andrienko Pavel“. Виж проверките.
2. НЕ брои мач, чийто победител не съвпада с НИТО ЕДНО от двете имена.
   По-добре с един мач по-малко, отколкото с една победа на грешния човек.
3. НЕ брои днешния ден. Историята върви от ВЧЕРА назад. Днешният ден още не
   е свършил и записан в кеша би останал непълен завинаги; освен това в
   обратна проверка същият ден носи надничане.

ПЪТИЩА НАЗАД (всичките през околната среда, без пипане на код)
    TT_LOKAL_DNI=0        — модулът мълчи изцяло (istoriya връща празно)
    TT_LOKAL_DNI=14       — колко дни назад най-много се гледат
    TT_LOKAL_NOVI=4       — колко НОВИ (нямащи ги в кеша) дни се свалят в
                            ЕДИН процес. Таван на цената: 4 дни ≈ 220 заявки.
    TT_LOKAL_KESH=<път>   — папката на кеша; празно = БЕЗ кеш на диска
    TT_LIGI=""            — изключва самите лиги (ръчката на tt_ligi)
"""

import contextlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import tt_ligi as TTL

# Сентинелите са НА tt_ligi. Не се правят нови: сравнение „is“ през два
# модула работи само ако обектът е един и същ.
ZAPUSHENO = TTL.ZAPUSHENO


def _env_int(ime, stand, dolu, gore):
    try:
        v = int(str(os.environ.get(ime) or "").strip())
    except (TypeError, ValueError):
        return stand
    return max(dolu, min(gore, v))


# Колко дни назад най-много. 0 = модулът мълчи (пътят назад).
DNI = _env_int("TT_LOKAL_DNI", 14, 0, 120)

# Колко НОВИ дни свалям в един процес. Мерено: един ден от двете лиги е
# ~55 заявки и ~65 секунди. Четири дни е ~3.5 минути — толкова, колкото
# струва вече и азиатският бейзбол. Кешът вдига тавана без да плаща.
NOVI = _env_int("TT_LOKAL_NOVI", 4, 0, 60)

# Под толкова мача играчът се смята за непознат. Същият праг, който
# predictor.model_tabletennis вече прилага („под 5 мача“).
MIN_MACHOVE = 5

# Папката на кеша. Празен низ = без диск. Списък, за да е подменяема на
# едно място — и от проверките, и отвън.
_KESH_PAPKA = [os.environ.get("TT_LOKAL_KESH",
                              os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "tt_lokal_kesh"))]

# Паметта: (пръв ден, последен ден) -> указател. Един рън пита за ЕДИН
# прозорец, но за 300+ играча — затова указателят се строи веднъж.
_PAMET = {}

_STAT = {}


def _nulirai_stat():
    _STAT.clear()
    _STAT.update({"dni_kesh": 0, "dni_mrezha": 0, "dni_byudzhet": 0,
                  "dni_zapusheni": 0, "machove": 0, "broeni": 0,
                  "bez_pobeditel": 0, "chuzhd_pobeditel": 0, "bliznaci": 0,
                  "novi_svaleni": 0})


_nulirai_stat()


def statistika():
    """Копие на брояча — за диагностика, не за решения."""
    return dict(_STAT)


def izchisti():
    """Забравя указателя в паметта. Дискът НЕ се пипа."""
    _PAMET.clear()
    _nulirai_stat()


# ───────────────────────────────────────────────────────────────── ДНИТЕ
def _dnes():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _den_str(x):
    """Каквото и да е -> „ГГГГ-ММ-ДД“ или None."""
    if isinstance(x, datetime):
        d = x if x.tzinfo else x.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%Y-%m-%d")
    s = str(x or "")[:10]
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


def _minus(den, k):
    d = datetime.strptime(den, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (d - timedelta(days=k)).strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────── КЕШЪТ НА ДИСКА
def _pat(lk, den):
    p = _KESH_PAPKA[0]
    if not p:
        return None
    return os.path.join(p, str(lk).replace(" ", "_") + "__" + den + ".json")


def kesh_chete(lk, den):
    """Записаният ден или None. НИКОГА не хвърля — кешът е удобство."""
    p = _pat(lk, den)
    if not p or not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("den") != den:
        return None
    m = d.get("m")
    return m if isinstance(m, list) else None


def kesh_pishe(lk, den, redove):
    """Записва деня. Връща True при успех. НИКОГА не хвърля.

    🔴 САМО ЗАВЪРШЕН ДЕН. Днешният ден още тече; записан веднъж, той би
    останал непълен завинаги, а кешът се чете преди мрежата. Същият капан
    като „застоял checkout“ — старото тихо побеждава новото.
    """
    p = _pat(lk, den)
    if not p or den >= _dnes():
        return False
    try:
        os.makedirs(os.path.dirname(p))
    except OSError:
        pass
    tmp = p + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"v": 1, "liga": lk, "den": den, "m": redove,
                       "vzet": datetime.now(timezone.utc)
                       .strftime("%Y-%m-%dT%H:%M:%SZ")},
                      f, ensure_ascii=False)
        os.replace(tmp, p)
    except (OSError, ValueError, TypeError):
        return False
    return True


# ──────────────────────────────────────────────────── ЕДИН ДЕН ОТ МРЕЖАТА
def den_rezultati(lk, den):
    """Свършилите мачове на една лига за един ден.

    Връща списък от [домакин, гост, победител|None, номер, състояние]
    или ZAPUSHENO, ако не съм стигнал до извора.

    🔴 ПАКЕТИ ПО 20. Пробвано живо: 50 събития в една заявка минава, но
    носи 9314 пазара и трае 12.6 с срещу 2.5 с за 20; 100 гърми. Освен
    това Smarkets НЕ УМЕЕ да филтрира по вид пазар — пробвани са
    type_name, market_type, type_domain, state, type_scope и name: и
    шестте връщат едни и същи 3796 пазара за 20 събития. Тоест 190
    пазара на събитие се свалят, за да се вземе ЕДИН. Това е цената.
    """
    ev = TTL._den_sabitiya(lk, den, ("ended", "cancelled"))
    if ev is ZAPUSHENO:
        return ZAPUSHENO
    po_id = {}
    for e in ev:
        if not isinstance(e, dict):
            continue
        a, sep, b = str(e.get("name") or "").partition(" vs ")
        if sep and a.strip() and b.strip():
            po_id[str(e.get("id"))] = (a.strip(), b.strip(), str(e.get("state") or ""))
    ids = list(po_id)
    paz = []
    for i in range(0, len(ids), 20):
        d = TTL._json(TTL._url_pazari(ids[i:i + 20]))
        if not isinstance(d, dict):
            continue
        paz += [m for m in (d.get("markets") or [])
                if isinstance(m, dict)
                and (m.get("market_type") or {}).get("name") == TTL.PAZAR_POBEDITEL
                and m.get("state") == "settled"]
    m2e = {}
    for m in paz:
        m2e[str(m.get("id"))] = str(m.get("event_id"))
    e2w = {}
    for i in range(0, len(paz), 20):
        part = paz[i:i + 20]
        c = TTL._json(TTL._url_kontrakti([m["id"] for m in part]))
        if not isinstance(c, dict):
            continue
        for x in (c.get("contracts") or []):
            if not isinstance(x, dict) or x.get("state_or_outcome") != "winner":
                continue
            eid = m2e.get(str(x.get("market_id")))
            if eid:
                e2w[eid] = str(x.get("name") or "")
    out = []
    for eid in ids:
        a, b, st = po_id[eid]
        out.append([a, b, e2w.get(eid), eid, st])
    return out


def _den(lk, den, mozhe_mrezha=True):
    """Денят от кеша, иначе от мрежата. ZAPUSHENO, ако и двете не станат."""
    got = kesh_chete(lk, den)
    if got is not None:
        _STAT["dni_kesh"] += 1
        return got
    if not mozhe_mrezha:
        _STAT["dni_byudzhet"] += 1
        return ZAPUSHENO
    r = den_rezultati(lk, den)
    if r is ZAPUSHENO:
        _STAT["dni_zapusheni"] += 1
        return ZAPUSHENO
    _STAT["dni_mrezha"] += 1
    kesh_pishe(lk, den, r)
    return r


# ─────────────────────────────────────────────────────────────── ИМЕНАТА
def _dvete_imena(a, b):
    """Двата ключа на един мач или None, ако мачът не различава хората.

    🔴 РАВНИ ХЛАБАВИ КЛЮЧОВЕ = МАЧЪТ СЕ ИЗХВЪРЛЯ. „Jaroslav (1964) Strnad“
    срещу „Jaroslav (1961) Strnad“ са двама различни души и играят един
    срещу друг — но победителят идва като ГОЛ НИЗ от друга заявка и по
    хлабавия ключ той сочи И ДВАМАТА. Тоест точно тук една победа би
    отишла с 50 % вероятност на грешния човек.
    """
    ka = TTL.klyuch_ime(a)
    kb = TTL.klyuch_ime(b)
    if not ka[0] or not kb[0]:
        return None
    if ka[0] == kb[0] or ka[1] == kb[1]:
        return None
    return ka, kb


def _dobavi(ind, strog, hlabav, ime, pobeda):
    z = ind["strog"].get(strog)
    if z is None:
        z = {"w": 0, "l": 0, "ime": ime}
        ind["strog"][strog] = z
    if pobeda:
        z["w"] += 1
    else:
        z["l"] += 1
    ind["hlabav"].setdefault(hlabav, set()).add(strog)


# ───────────────────────────────────────────────────────────── УКАЗАТЕЛЯТ
def istoriya(now=None, dni=None):
    """Указателят победи/загуби за прозореца, който свършва ВЧЕРА.

    Връща {"strog": {...}, "hlabav": {...}, "dni": [...]}  или ZAPUSHENO,
    ако НИТО ЕДИН ден не е успял (нито от кеша, нито от мрежата).
    Празен указател с прочетени дни е ЧЕСТНА нула, не запушване.
    """
    if isinstance(now, datetime):
        posleden = _minus(_den_str(now), 1)
    else:
        posleden = _minus(_den_str(now) or _dnes(), 1)
    n = DNI if dni is None else max(0, min(int(dni), DNI))
    if n <= 0:
        return {"strog": {}, "hlabav": {}, "dni": []}
    parvi = _minus(posleden, n - 1)
    klyuch = (parvi, posleden, tuple(TTL.vklyucheni()))
    if klyuch in _PAMET:
        return _PAMET[klyuch]

    ind = {"strog": {}, "hlabav": {}, "dni": []}
    ligi = TTL.vklyucheni()
    if not ligi:
        _PAMET[klyuch] = ind
        return ind
    nov_byudzhet = NOVI
    uspeli = 0
    for k in range(n):
        den = _minus(posleden, k)
        # Има ли ГО деня в кеша? Ако да — не яде от бюджета.
        v_kesha = all(kesh_chete(lk, den) is not None for lk in ligi)
        mozhe = v_kesha or nov_byudzhet > 0
        izpolzvan = False
        for lk in ligi:
            r = _den(lk, den, mozhe_mrezha=mozhe)
            if r is ZAPUSHENO:
                continue
            izpolzvan = True
            for red in r:
                if not isinstance(red, (list, tuple)) or len(red) < 3:
                    continue
                a, b, pob = red[0], red[1], red[2]
                _STAT["machove"] += 1
                if not pob:
                    _STAT["bez_pobeditel"] += 1
                    continue
                dv = _dvete_imena(a, b)
                if dv is None:
                    _STAT["bliznaci"] += 1
                    continue
                ka, kb = dv
                kp = TTL.klyuch_ime(pob)[1]
                if kp == ka[1]:
                    pobeda_a = True
                elif kp == kb[1]:
                    pobeda_a = False
                else:
                    # 🔴 ПОБЕДИТЕЛ, КОЙТО НЕ Е НИТО ЕДИН ОТ ДВАМАТА.
                    # Не се гадае по фамилия — мачът просто пада.
                    _STAT["chuzhd_pobeditel"] += 1
                    continue
                _dobavi(ind, ka[0], ka[1], a, pobeda_a)
                _dobavi(ind, kb[0], kb[1], b, not pobeda_a)
                _STAT["broeni"] += 1
        if izpolzvan:
            uspeli += 1
            ind["dni"].append(den)
            if not v_kesha and nov_byudzhet > 0:
                nov_byudzhet -= 1
                _STAT["novi_svaleni"] += 1
    if uspeli == 0:
        return ZAPUSHENO
    ind["dni"].sort()
    _PAMET[klyuch] = ind
    return ind


def igrach(ime, now=None, dni=90):
    """Сводката на един играч: {"w": победи, "l": загуби}.

        None       — не го познавам (нула мача в прозореца)
        ZAPUSHENO  — не можах да питам изобщо; това НЕ Е „няма история“

    🔴 СТРОГИЯТ КЛЮЧ ПЪРВО, ХЛАБАВИЯТ САМО КОГАТО СОЧИ ЕДИН ЧОВЕК.
    Хлабавият маха годината — точно тя различава двамата Strnad. Затова
    той се ползва само ако под него стои РОВНО ЕДИН строг ключ.
    """
    ind = istoriya(now, dni)
    if ind is ZAPUSHENO:
        return ZAPUSHENO
    k = TTL.klyuch_ime(ime)
    if not k[0]:
        return None
    z = ind["strog"].get(k[0])
    if z is None:
        kand = ind["hlabav"].get(k[1]) or set()
        if len(kand) != 1:
            return None
        z = ind["strog"].get(next(iter(kand)))
        if z is None:
            return None
    return {"w": int(z["w"]), "l": int(z["l"])}


def stiga(z):
    """Достатъчна ли е сводката за карта. Само речник с 5+ мача минава."""
    if not isinstance(z, dict):
        return False
    try:
        return (int(z.get("w", -1)) + int(z.get("l", -1))) >= MIN_MACHOVE
    except (TypeError, ValueError):
        return False


def _rejting(z):
    """Изгладеният баланс: (w+3)/(w+l+6). Същото изглаждане, което вече
    ползва predictor.model_tabletennis — не измислям второ."""
    return (z["w"] + 3.0) / (z["w"] + z["l"] + 6.0)


# ───────────────────────────────────────────────────────────────── СРЕЩИТЕ
def srechti(now=None, tavan=None, dni=None):
    """Днешните срещи, които МОГАТ да станат карта: история за ДВАМАТА И цена.

    Връща редовете точно във формата на predictor (tt_ligi.fixtures ги дава
    така), допълнени в `extra` с цената и с двете сводки. ZAPUSHENO, ако
    срещите не са стигнали — това НЕ Е празен ден.

    🔴 ПОДРЕДБАТА Е ПО РАЗЛИКАТА В БАЛАНСА, НЕ ПО ЧАС. Мерено напред върху
    9326 истински мача (прозорец 14 дни, нула надничане): по-добрият печели
    50.2 % при |Δ рейтинг| под 0.02 и 63.9 % при |Δ| над 0.25. Тоест целият
    ръб седи в срещите с ГОЛЯМА разлика, а таванът и без това реже до
    няколко карти. Ако режем по час, режем случайно.
    """
    if DNI <= 0:
        return []
    try:
        fx = TTL.fixtures()
    except Exception:                                        # noqa: BLE001
        return ZAPUSHENO
    if not isinstance(fx, list):
        return ZAPUSHENO
    try:
        ind = TTL.index_ceni()
    except Exception:                                        # noqa: BLE001
        ind = None
    if not isinstance(ind, dict):
        ind = {}
    out = []
    for f in fx:
        if not isinstance(f, dict):
            continue
        a = igrach(f.get("home"), now, dni if dni is not None else 90)
        b = igrach(f.get("away"), now, dni if dni is not None else 90)
        if not stiga(a) or not stiga(b):
            continue
        ex = dict(f.get("extra") or {})
        c = TTL.cena(f.get("home"), f.get("away"), f.get("league"),
                     kogato=ex.get("start"), ind=ind)
        if not isinstance(c, dict):
            continue                         # 🔴 БЕЗ ЦЕНА НЯМА КАРТА
        ex.update({"cena_dom": c["dom"], "cena_gost": c["gost"],
                   "cena_izvor": c["izvor"], "p_pazar": c["p_dom"],
                   "marzh": c["marzh"],
                   "ist_dom": dict(a), "ist_gost": dict(b),
                   "delta": round(_rejting(a) - _rejting(b), 4)})
        r = dict(f)
        r["extra"] = ex
        out.append(r)
    out.sort(key=lambda x: -abs((x["extra"] or {}).get("delta") or 0.0))
    if tavan is not None and int(tavan) >= 0:
        out = out[:int(tavan)]
    return out


# ══════════════════════════════════════════════════════ ХАРТИЕНАТА МРЕЖА
# Всичко долу е за проверките. Мрежа НЕ се пипа: подменя се САМО
# tt_ligi._MREZHA[0] — единственият шев на целия изход към света.

_F = {}

_SASTAV = {
    "44792813": ["Adam Nowak", "Piotr Nowak", "Kaczynski Piotr",
                 "Grzegorz Marud", "Pawel Adamus", "Artur Kubiak",
                 "Mateusz Sikon", "Jakub Jesiek"],
    "42932772": ["Jaroslav (1964) Strnad", "Jaroslav (1961) Strnad",
                 "Vaclav Kosar", "Erik Mares", "Jan Cernik", "Michal Vesely"],
}

# Ден-отместване -> подменено име на същия човек. Тук се проверява, че
# обърнатият ред на думите НЕ прави втори играч.
_PSEVDONIM = {3: {"Kaczynski Piotr": "Piotr Kaczynski"}}


def _falshiv_den(cid, den):
    """Мачовете на една лига за един ден. Строят се веднъж и се помнят.

    Денят се разпознава по РАЗСТОЯНИЕТО до днес, а не по закована дата —
    иначе проверката би почервеняла на следващия ден. Този файл вече е
    ухапан от точно това (виж коментара в tt_ligi._falshivi_sabitiya).
    """
    kl = (cid, den)
    if kl in _F.setdefault("dni", {}):
        return _F["dni"][kl]
    try:
        k = (datetime.strptime(_dnes(), "%Y-%m-%d")
             - datetime.strptime(den, "%Y-%m-%d")).days
    except ValueError:
        k = -1
    out = []
    if k < 0 or k > 40 or cid not in _SASTAV:
        _F["dni"][kl] = out
        return out
    if k == 0:
        # ДНЕШНИЯТ ден: предстоящи мачове между хора, които ИМАТ история.
        # Пазарът им е „open“, победител няма — точно както в живия извор.
        # 🔴 ЧАСОВЕТЕ СА РАЗЛИЧНИ. С един и същи час подредбата по час е
        # неразличима от подредбата по увереност и мутацията „реже по час“
        # минава невидимо — точно това ме ухапа при първото писане.
        base = cid[-2:] + den.replace("-", "")
        sastav = list(_SASTAV[cid])
        ch = 9
        for i in range(0, len(sastav) - 1, 2):
            a, b = sastav[i], sastav[i + 1]
            if TTL.klyuch_ime(a)[1] == TTL.klyuch_ime(b)[1]:
                continue
            ch += 1
            out.append({"id": base + "U%d" % i, "home": a, "away": b,
                        "pobeditel": None, "state": "upcoming",
                        "hidden": False, "pazar": "open",
                        "chas": "%02d:00:00" % ch})
        # 1. двама непознати — няма история, не бива да стане карта
        out.append({"id": base + "U90", "home": "Neznaen Chovek",
                    "away": "Vtori Neznaen", "pobeditel": None,
                    "state": "upcoming", "hidden": False, "pazar": "open",
                    "chas": "20:00:00"})
        # 2. ЕДИНИЯТ познат, другият не — тук се хваща проверка само за
        #    домакина
        out.append({"id": base + "U91", "home": sastav[0],
                    "away": "Nepoznat Sopernik", "pobeditel": None,
                    "state": "upcoming", "hidden": False, "pazar": "open",
                    "chas": "21:00:00"})
        # 3. двама ПОЗНАТИ, но БЕЗ пазар — тоест без цена. „bez“ значи, че
        #    събитието изобщо няма пазар победител и не е във витрината.
        out.append({"id": base + "U92", "home": sastav[1], "away": sastav[2],
                    "pobeditel": None, "state": "upcoming", "hidden": False,
                    "pazar": "bez", "chas": "22:00:00"})
        _F["dni"][kl] = out
        return out
    sastav = list(_SASTAV[cid])
    psev = _PSEVDONIM.get(k, {})
    n = len(sastav)
    br = 0
    for i in range(n):
        j = (i + 1 + (k % (n - 1))) % n
        if i == j:
            continue
        a, b = sastav[i], sastav[j]
        # близнаците един срещу друг се строят отделно долу
        if TTL.klyuch_ime(a)[1] == TTL.klyuch_ime(b)[1]:
            continue
        pob = a if ((i + k) % 2 == 0) else b
        br += 1
        out.append({"id": cid[-2:] + den.replace("-", "") + "%02d" % br,
                    "home": psev.get(a, a), "away": psev.get(b, b),
                    "pobeditel": psev.get(pob, pob),
                    "state": "ended", "hidden": False, "pazar": "settled"})
    if cid == "42932772":
        base = cid[-2:] + den.replace("-", "")
        # 1. отменен мач — няма отсъден пазар, значи не се брои
        out.append({"id": base + "90", "home": "Michal Vesely",
                    "away": "Erik Mares", "pobeditel": None,
                    "state": "cancelled", "hidden": False, "pazar": "live"})
        # 2. победител, който НЕ е нито един от двамата
        out.append({"id": base + "91", "home": "Vaclav Kosar",
                    "away": "Jan Cernik", "pobeditel": "Nikoi Drug",
                    "state": "ended", "hidden": False, "pazar": "settled"})
        # 3. СКРИТ мач — трябва да се брои (include_hidden=true)
        out.append({"id": base + "92", "home": "Erik Mares",
                    "away": "Vaclav Kosar", "pobeditel": "Erik Mares",
                    "state": "ended", "hidden": True, "pazar": "settled"})
        # 4. двамата Strnad един срещу друг — НЕ бива да се брои
        out.append({"id": base + "93", "home": "Jaroslav (1964) Strnad",
                    "away": "Jaroslav (1961) Strnad",
                    "pobeditel": "Jaroslav (1964) Strnad",
                    "state": "ended", "hidden": False, "pazar": "settled"})
        # 5. свършил, но пазарът още НЕ е отсъден
        out.append({"id": base + "94", "home": "Jan Cernik",
                    "away": "Michal Vesely", "pobeditel": "Jan Cernik",
                    "state": "ended", "hidden": False, "pazar": "live"})
    if cid == "44792813" and k == 1:
        # 6. ПАГИНАЦИЯ: 230 мача на пълнеж, за да има втора страница
        base = cid[-2:] + den.replace("-", "")
        for t in range(230):
            a = "Pylnezh A%03d" % t
            b = "Pylnezh B%03d" % t
            out.append({"id": base + "P%03d" % t, "home": a, "away": b,
                        "pobeditel": a, "state": "ended", "hidden": False,
                        "pazar": "settled"})
    _F["dni"][kl] = out
    return out


def _vsichki_falshivi():
    out = {}
    for kl, redove in (_F.get("dni") or {}).items():
        for r in redove:
            out[r["id"]] = (kl[0], kl[1], r)
    return out


def _falshiva_mrezha(url):
    """Мрежа от хартия. Отговаря по АДРЕС — сгрешен адрес се вижда."""
    _F["vikan"] = _F.get("vikan", 0) + 1
    _F.setdefault("adresi", []).append(url)
    if _F.get("myrtva"):
        return None
    if _F.get("myrtvi_dni"):
        m = re.search(r"pagination_last_start_datetime=([\d-]+)", url)
        if m and m.group(1) in _F["myrtvi_dni"]:
            return None
    if "kambicdn" in url:
        if "football" in url:
            # еталонът: жив спорт с стотици събития
            return {"events": [{"event": {"name": "A - B"}} for _ in range(260)]}
        if _F.get("kambi_prazen"):
            return {"events": []}
        return _kambi_dnes()
    if "/quotes/" in url:
        mids = url.split("/markets/")[1].split("/")[0].split(",")
        vs = _vsichki_falshivi()
        kot = {}
        for mid in mids:
            vid, _s, eid = str(mid).partition("~")
            got = vs.get(eid)
            if vid != "W2W" or not got:
                continue
            r = got[2]
            # 🔴 КОТИРОВКИТЕ СА ПО ДОГОВОР, НЕ ПО ПАЗАР. Сбърка ли се това,
            # цената излиза празна, а не грешна — тоест мълчаливо.
            for ime, of, bd in ((r["home"], 5556, 5263),
                                (r["away"], 4545, 4167)):
                kot["c" + mid + ime[:3]] = {
                    "bids": [{"price": bd, "quantity": 1}],
                    "offers": [{"price": of, "quantity": 1}]}
        return kot
    if "/contracts/" in url:
        mids = url.split("/markets/")[1].split("/")[0].split(",")
        vs = _vsichki_falshivi()
        kon = []
        for mid in mids:
            vid, _s, eid = str(mid).partition("~")
            got = vs.get(eid)
            if not got:
                continue
            r = got[2]
            if vid == "W2W":
                if r["pazar"] != "settled":
                    # 🔴 НЕОТСЪДЕНИЯТ ПАЗАР ИМА ДОГОВОРИ, само че никой не е
                    # „winner“. Иначе мутацията „брои и неотсъдените“ би
                    # изглеждала безобидна, а тя струва ЗАЯВКИ.
                    for ime in (r["home"], r["away"]):
                        kon.append({"id": "c" + mid + ime[:3], "market_id": mid,
                                    "name": ime, "state_or_outcome": "open"})
                    continue
                pisan = False
                for ime in (r["home"], r["away"]):
                    pob = (r["pobeditel"] is not None
                           and TTL.klyuch_ime(ime)[1]
                           == TTL.klyuch_ime(r["pobeditel"])[1])
                    pisan = pisan or pob
                    kon.append({"id": "c" + mid + ime[:3], "market_id": mid,
                                "name": ime,
                                "state_or_outcome": "winner" if pob else "loser"})
                if r["pobeditel"] and not pisan:
                    # чужд победител: договорът носи име, което не е на масата
                    kon.append({"id": "cX" + mid, "market_id": mid,
                                "name": r["pobeditel"],
                                "state_or_outcome": "winner"})
            else:
                # 🔴 ЧУЖДИТЕ ПАЗАРИ СЪЩО ИМАТ „winner“ — и той НЕ Е ИМЕ НА
                # ЧОВЕК. Точно това прави филтъра по WINNER_2_WAY нужен:
                # без него „Over 4.5“ презаписва истинския победител.
                for ime, izh in (("Over 4.5", "winner"), ("Under 4.5", "loser")):
                    kon.append({"id": "c" + mid + ime[:3], "market_id": mid,
                                "name": ime, "state_or_outcome": izh})
        return {"contracts": kon}
    if "/markets/" in url and "/events/" in url:
        ids = url.split("/events/")[1].split("/")[0].split(",")
        vs = _vsichki_falshivi()
        mk = []
        for eid in ids:
            got = vs.get(eid)
            if not got:
                continue
            r = got[2]
            if r["pazar"] != "bez":
                mk.append({"id": "W2W~" + eid, "event_id": eid,
                           "state": r["pazar"],
                           "market_type": {"name": TTL.PAZAR_POBEDITEL}})
            # шумът: същото събитие носи и десетки чужди пазари. Мерено
            # живо: 20 събития -> 3796 пазара, тоест 190 на събитие.
            for t in ("CORRECT_SCORE", "OVER_UNDER", "HANDICAP"):
                mk.append({"id": t[:3] + "~" + eid, "event_id": eid,
                           "state": "settled", "market_type": {"name": t}})
        return {"markets": mk}
    if "/events/?" in url or url.startswith(TTL.SM + "/events/?p2="):
        return _falshivi_sabitiya(url)
    if "/events/" in url:
        eid = url.split("/events/")[1].strip("/")
        vs = _vsichki_falshivi()
        got = vs.get(eid)
        if not got:
            return {"events": []}
        cid, den, r = got
        return {"events": [{"id": eid, "parent_id": cid, "state": r["state"],
                            "name": r["home"] + " vs " + r["away"],
                            "start_date": den,
                            "start_datetime": den + "T"
                            + r.get("chas", "10:00:00") + "Z"}]}
    return None


def _kambi_dnes():
    """Витрината: същите днешни срещи, но с цена на книжаря (odds × 1000)."""
    ev = []
    for cid, lig in (("42932772", "Czech Liga Pro"),
                     ("44792813", "TT Elite Series")):
        for r in _falshiv_den(cid, _dnes()):
            if r["state"] != "upcoming" or r["pazar"] == "bez":
                continue
            ev.append({"event": {"name": r["home"] + " - " + r["away"],
                                 "start": _dnes() + "T"
                                 + r.get("chas", "10:00:00") + "Z",
                                 "path": [{"englishName": "Table Tennis"},
                                          {"englishName": lig}]},
                       "betOffers": [{"criterion": {"label": "Match Odds"},
                                      "outcomes": [
                                          {"label": r["home"], "odds": 1780},
                                          {"label": r["away"], "odds": 1860}]}]})
    return {"events": ev}


def _pitani_pazari():
    """Кои пазари изобщо са питани за договори — по адресите, не по вяра."""
    out = []
    for a in (_F.get("adresi") or []):
        if "/contracts/" not in a:
            continue
        out += a.split("/markets/")[1].split("/")[0].split(",")
    return out


def _pitani_neotsadeni():
    """Колко НЕотсъдени пазара са питани за договори. Трябва да е нула."""
    vs = _vsichki_falshivi()
    n = 0
    for mid in _pitani_pazari():
        vid, _s, eid = str(mid).partition("~")
        got = vs.get(eid)
        if vid == "W2W" and got and got[2]["pazar"] != "settled":
            n += 1
    return n


def _pitani_chuzhdi():
    """Колко ЧУЖДИ (не-победител) пазара са питани. Трябва да е нула."""
    return sum(1 for mid in _pitani_pazari()
               if not str(mid).startswith("W2W~"))


def _falshivi_sabitiya(url):
    """🔴 ТУК СЕ ХВАЩАТ ТИХИТЕ КАПАНИ: скритите изчезват без include_hidden,
    а без втора страница една трета от деня пада мълчаливо."""
    if url.startswith(TTL.SM + "/events/?p2="):
        q = dict(x.split("=", 1) for x in url.split("?", 1)[1].split("&") if "=" in x)
        cid, sast, den, otm = q["parent_id"], q["state"], q["den"], int(q["p2"])
        skriti = q.get("h") == "1"
    else:
        mc = re.search(r"parent_id=(\d+)", url)
        ms = re.search(r"state=(\w+)", url)
        md = re.search(r"pagination_last_start_datetime=([\d-]+)", url)
        ml = re.search(r"pagination_last_id=(\d+)", url)
        if not (mc and ms and md):
            return None
        cid, sast, den, otm = mc.group(1), ms.group(1), md.group(1), 0
        skriti = "include_hidden=true" in url
        if ml and ml.group(1) == "0":
            den = _minus(den, 30)            # архивът, както прави истинският
    ev = []
    for r in _falshiv_den(cid, den):
        if r["state"] != sast:
            continue
        if r["hidden"] and not skriti:
            continue
        ev.append({"id": r["id"], "parent_id": cid, "state": r["state"],
                   "hidden": r["hidden"],
                   "name": r["home"] + " vs " + r["away"],
                   "start_date": den,
                   "start_datetime": den + "T" + r.get("chas", "10:00:00") + "Z"})
    stranica = ev[otm:otm + 200]
    nx = None
    if len(ev) > otm + 200:
        nx = ("?p2=" + str(otm + 200) + "&parent_id=" + cid + "&state=" + sast
              + "&den=" + den + ("&h=1" if skriti else ""))
    return {"events": stranica, "pagination": {"next_page": nx}}


# ══════════════════════════════════════════════════════════════ ПРОВЕРКИТЕ
def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    g = globals()
    star_mr = TTL._MREZHA[0]
    star_ra = TTL.__dict__["_RACHKA"]
    star_kesh = _KESH_PAPKA[0]
    star_dni, star_novi = g["DNI"], g["NOVI"]
    TTL._MREZHA[0] = _falshiva_mrezha
    TTL.__dict__["_RACHKA"] = "czech liga pro,tt elite series"
    _KESH_PAPKA[0] = ""                      # проверките НЕ пипат диска
    g["DNI"], g["NOVI"] = 14, 60
    _F.clear()
    TTL.izchisti_kesh()
    izchisti()
    try:
        # ═══ 1. ЕСТЕСТВЕНОТО ИЗВИКВАНЕ — БЕЗ НИТО ЕДИН АРГУМЕНТ ═══
        # 🔴 СТОИ ПЪРВО. В тази къща е хващан модул с 45 зелени проверки,
        # чиято главна функция връща None винаги. Тези проверки минават по
        # СЪЩИЯ път, по който ще мине ботът; подменена е само мрежата.
        z = igrach("Erik Mares")
        check("igrach() БЕЗ дата и БЕЗ данни дава сводка", isinstance(z, dict))
        check("igrach() наистина пита извора", _F.get("vikan", 0) > 0)
        check("сводката носи победи и загуби",
              isinstance(z, dict) and "w" in z and "l" in z)
        check("победите са цяло число", isinstance(z, dict)
              and isinstance(z["w"], int) and not isinstance(z["w"], bool))
        check("загубите са цяло число", isinstance(z, dict)
              and isinstance(z["l"], int) and not isinstance(z["l"], bool))
        check("сводката не е празна", isinstance(z, dict) and (z["w"] + z["l"]) > 0)
        check("непознат играч дава None", igrach("Nikoi Nikoev") is None)
        check("празно име дава None", igrach("") is None)
        check("None за име дава None", igrach(None) is None)
        check("боклук за име дава None", igrach("!!! ??? 123") is None)

        # ═══ 2. ИСТОРИЯТА КАТО ЦЯЛО ═══
        ind = istoriya()
        check("istoriya() връща указател", isinstance(ind, dict))
        check("указателят има строг слой", isinstance(ind.get("strog"), dict))
        check("указателят има хлабав слой", isinstance(ind.get("hlabav"), dict))
        check("указателят изброява прочетените дни",
              isinstance(ind.get("dni"), list) and len(ind["dni"]) > 0)
        check("днешният ден НЕ влиза в историята", _dnes() not in ind["dni"])
        check("дните са подредени", ind["dni"] == sorted(ind["dni"]))
        check("прозорецът не надхвърля DNI", len(ind["dni"]) <= DNI)
        check("има десетки играчи", len(ind["strog"]) > 10)
        _sw = sum(v["w"] for v in ind["strog"].values())
        _sl = sum(v["l"] for v in ind["strog"].values())
        check("🔴 всяка победа има точно една загуба насреща", _sw == _sl)
        check("сборът победи+загуби е два пъти броените мачове",
              _sw + _sl == 2 * _STAT["broeni"])
        check("вторият въпрос НЕ пита мрежата пак (указателят се помни)",
              (lambda v0: (istoriya() is not None
                           and _F.get("vikan", 0) == v0))(_F.get("vikan", 0)))

        # ═══ 3. ИМЕНАТА — ТУК СЕ ЛЕПИ ЧУЖД ЗАПИС ═══
        n1 = igrach("Adam Nowak")
        n2 = igrach("Piotr Nowak")
        check("двама с обща ФАМИЛИЯ съществуват поотделно",
              isinstance(n1, dict) and isinstance(n2, dict))
        check("🔴 общата фамилия НЕ ги слива в един запис",
              TTL.klyuch_ime("Adam Nowak")[0] != TTL.klyuch_ime("Piotr Nowak")[0])
        check("„Andrienko M.“ НЕ се свежда до „m“",
              TTL.klyuch_ime("Andrienko M.")[0] != ("m",)
              and "andrienko" in TTL.klyuch_ime("Andrienko M.")[0])
        check("🔴 „Andrienko M.“ и „Andrienko Pavel“ са различни ключове",
              TTL.klyuch_ime("Andrienko M.")[0]
              != TTL.klyuch_ime("Andrienko Pavel")[0])
        check("обърнатият ред на думите е СЪЩИЯТ човек",
              igrach("Kaczynski Piotr") == igrach("Piotr Kaczynski"))
        check("🔴 двамата Strnad са ДВА отделни записа",
              len([k for k in ind["strog"] if "strnad" in k]) == 2)
        check("двамата Strnad не се сдвояват по хлабав ключ",
              igrach("Jaroslav Strnad") is None)
        check("но с годината се намират",
              isinstance(igrach("Jaroslav (1964) Strnad"), dict))
        check("диакритиките не правят нов човек",
              igrach("Václav Kosař") == igrach("Vaclav Kosar"))

        # ═══ 4. КОЕ НЕ СЕ БРОИ ═══
        check("мач без отсъден победител не се брои", _STAT["bez_pobeditel"] > 0)
        check("🔴 чужд победител НЕ се приписва на никого",
              _STAT["chuzhd_pobeditel"] > 0)
        check("мач между двама с еднакъв хлабав ключ се изхвърля",
              _STAT["bliznaci"] > 0)
        check("изхвърлените са по-малко от преброените",
              _STAT["bez_pobeditel"] + _STAT["chuzhd_pobeditel"]
              + _STAT["bliznaci"] < _STAT["broeni"])
        # 🔴 ТОЧНО ПО ЕДИН ЧУЖД ПОБЕДИТЕЛ НА ДЕН — толкова са подхвърлени.
        # Числото, не „повече от нула“: без филтъра по WINNER_2_WAY всяко
        # събитие носи и „Over 4.5“ като победител и това число избухва.
        check("🔴 чуждите победители са ТОЧНО колкото са подхвърлени",
              _STAT["chuzhd_pobeditel"] == len(ind["dni"]))
        check("🔴 за договори се питат САМО отсъдени пазари (цената е в заявки)",
              _pitani_neotsadeni() == 0)
        check("🔴 за договори се питат САМО пазарите победител",
              _pitani_chuzhdi() == 0)
        check("броените + изхвърлените = всички видени",
              _STAT["broeni"] + _STAT["bez_pobeditel"] + _STAT["chuzhd_pobeditel"]
              + _STAT["bliznaci"] == _STAT["machove"])

        # ═══ 5. СКРИТИТЕ И ПАГИНАЦИЯТА ═══
        _adr = list(_F.get("adresi") or [])
        check("🔴 иска се include_hidden (иначе скритите изчезват)",
              any("include_hidden=true" in a for a in _adr))
        check("🔴 pagination_last_id е 1, не 0 (иначе идва архивът)",
              all("pagination_last_id=0" not in a for a in _adr))
        check("🔴 втората страница се иска (иначе една трета пада тихо)",
              any("p2=200" in a for a in _adr))
        _p = igrach("Pylnezh A000")
        check("играч само от втората страница СЕ намира", isinstance(_p, dict))

        # ═══ 6. ЗАПУШЕНО НЕ Е НУЛА ═══
        izchisti()
        TTL.izchisti_kesh()
        _F["myrtva"] = True
        r = istoriya()
        check("🔴 мъртъв извор дава ZAPUSHENO, не празен указател",
              r is ZAPUSHENO)
        check("🔴 igrach при мъртъв извор дава ZAPUSHENO, не None",
              igrach("Erik Mares") is ZAPUSHENO)
        check("ZAPUSHENO НЕ минава за сводка", not stiga(igrach("Erik Mares")))
        check("ZAPUSHENO е лъжливо истинен (не се хваща с „if not“)",
              bool(ZAPUSHENO) is True)
        _F["myrtva"] = False
        izchisti()
        TTL.izchisti_kesh()

        # един ЕДИНСТВЕН мъртъв ден не убива прозореца
        _F["myrtvi_dni"] = {_minus(_dnes(), 2)}
        r = istoriya()
        check("един мъртъв ден НЕ прави целия прозорец запушен",
              isinstance(r, dict) and len(r["dni"]) > 0)
        check("мъртвият ден не влиза в списъка с прочетените",
              isinstance(r, dict) and _minus(_dnes(), 2) not in r["dni"])
        _F.pop("myrtvi_dni", None)
        izchisti()
        TTL.izchisti_kesh()

        # ═══ 7. РЪЧКИТЕ И ПЪТЯТ НАЗАД ═══
        g["DNI"] = 0
        izchisti()
        r0 = istoriya()
        check("🔴 TT_LOKAL_DNI=0 изключва модула напълно",
              isinstance(r0, dict) and r0["strog"] == {} and r0["dni"] == [])
        check("при изключен модул igrach мълчи с None", igrach("Erik Mares") is None)
        g["DNI"] = 14
        izchisti()
        TTL.izchisti_kesh()

        TTL.__dict__["_RACHKA"] = ""
        izchisti()
        r1 = istoriya()
        check("🔴 свалената ръчка на tt_ligi изключва и този модул",
              isinstance(r1, dict) and r1["strog"] == {})
        TTL.__dict__["_RACHKA"] = "czech liga pro,tt elite series"
        izchisti()
        TTL.izchisti_kesh()

        # ═══ 8. БЮДЖЕТЪТ НА НОВИТЕ ДНИ ═══
        g["NOVI"] = 2
        izchisti()
        TTL.izchisti_kesh()
        r2 = istoriya(dni=10)
        check("🔴 бюджетът реже броя НОВИ дни (2 поискани, 2 взети)",
              isinstance(r2, dict) and len(r2["dni"]) == 2)
        check("бюджетът брои и отказаните дни",
              _STAT["dni_byudzhet"] > 0)
        g["NOVI"] = 60
        izchisti()
        TTL.izchisti_kesh()

        # ═══ 9. ПРОЗОРЕЦЪТ ═══
        izchisti()
        ra = istoriya(dni=3)
        check("по-къс прозорец дава по-малко дни", len(ra["dni"]) == 3)
        izchisti()
        rb = istoriya(dni=6)
        check("по-дълъг прозорец дава повече мачове",
              sum(v["w"] + v["l"] for v in rb["strog"].values())
              > sum(v["w"] + v["l"] for v in ra["strog"].values()))
        check("по-дългият прозорец не губи играчи",
              set(ra["strog"]) <= set(rb["strog"]))
        izchisti()
        _vch = datetime.now(timezone.utc) - timedelta(days=1)
        rc = istoriya(now=_vch, dni=3)
        check("подадена дата мести прозореца назад",
              rc["dni"][-1] == _minus(_dnes(), 2))
        check("подадената дата не влиза в собствения си прозорец",
              _den_str(_vch) not in rc["dni"])
        izchisti()

        # ═══ 10. ПРАГЪТ ═══
        check("stiga() отхвърля None", not stiga(None))
        check("stiga() отхвърля ZAPUSHENO", not stiga(ZAPUSHENO))
        check("stiga() отхвърля 4 мача", not stiga({"w": 2, "l": 2}))
        check("stiga() приема 5 мача", stiga({"w": 5, "l": 0}))
        check("stiga() отхвърля боклук", not stiga({"w": "три", "l": 1}))
        check("прагът е точно 5", MIN_MACHOVE == 5)
        check("🔴 балансът е ИЗГЛАДЕН: 5-0 тежи по-малко от 50-0",
              _rejting({"w": 5, "l": 0}) < _rejting({"w": 50, "l": 0}))
        check("изглаждането не пуска нито 0, нито 1",
              0.0 < _rejting({"w": 0, "l": 40}) and _rejting({"w": 40, "l": 0}) < 1.0)
        check("равен баланс дава точно 0.5", abs(_rejting({"w": 7, "l": 7}) - 0.5) < 1e-9)

        # ═══ 11. КЕШЪТ НА ДИСКА ═══
        check("без папка кешът мълчи вместо да гърми",
              kesh_chete("czech liga pro", _minus(_dnes(), 1)) is None)
        check("без папка записът връща False",
              kesh_pishe("czech liga pro", _minus(_dnes(), 1), []) is False)
        import tempfile
        _tmp = tempfile.mkdtemp(prefix="tt_lokal_")
        _KESH_PAPKA[0] = _tmp
        _vch1 = _minus(_dnes(), 1)
        check("записът в истинска папка успява",
              kesh_pishe("czech liga pro", _vch1, [["A", "B", "A", "1", "ended"]]))
        check("записаното се чете обратно",
              kesh_chete("czech liga pro", _vch1) == [["A", "B", "A", "1", "ended"]])
        check("🔴 ДНЕШНИЯТ ден НЕ се записва (би останал непълен завинаги)",
              kesh_pishe("czech liga pro", _dnes(), [["A", "B", "A", "1", "e"]])
              is False)
        check("непопитан ден не се измисля",
              kesh_chete("czech liga pro", _minus(_dnes(), 9)) is None)
        izchisti()
        TTL.izchisti_kesh()
        _v0 = _F.get("vikan", 0)
        istoriya(dni=1)
        check("🔴 денят от кеша НЕ се сваля повторно",
              _STAT["dni_kesh"] >= 1)
        _KESH_PAPKA[0] = ""
        try:
            for _f in os.listdir(_tmp):
                os.remove(os.path.join(_tmp, _f))
            os.rmdir(_tmp)
        except OSError:
            pass

        # ═══ 12. СРЕЩИТЕ, КОИТО МОГАТ ДА СТАНАТ КАРТА ═══
        izchisti()
        TTL.izchisti_kesh()
        sr = srechti()
        check("srechti() БЕЗ аргументи връща срещи",
              isinstance(sr, list) and len(sr) > 0)
        check("всяка среща е в кошницата tabletennis",
              all(x["bucket"] == "tabletennis" for x in sr))
        check("всяка среща носи двете имена",
              all(x.get("home") and x.get("away") for x in sr))
        check("всяка среща носи начало", all(x.get("when") is not None for x in sr))
        check("всяка среща носи номера на Smarkets",
              all(str((x.get("extra") or {}).get("slug", "")).isdigit()
                  or (x.get("extra") or {}).get("slug") for x in sr))
        check("🔴 всяка среща носи ЦЕНА за двете страни",
              all((x["extra"].get("cena_dom") or 0) > 1.0
                  and (x["extra"].get("cena_gost") or 0) > 1.0 for x in sr))
        check("цената носи и източника си",
              all(x["extra"].get("cena_izvor") in ("smarkets", "kambi")
                  for x in sr))
        check("пазарната вероятност е между 0 и 1",
              all(0.0 < (x["extra"].get("p_pazar") or -1.0) < 1.0 for x in sr))
        check("🔴 всяка среща носи история за ДВАМАТА",
              all(stiga(x["extra"].get("ist_dom"))
                  and stiga(x["extra"].get("ist_gost")) for x in sr))
        check("🔴 играч БЕЗ история не става карта",
              all("Neznaen" not in x["home"] for x in sr))
        _slug = lambda x: str((x.get("extra") or {}).get("slug") or "")  # noqa: E731
        _fxs = TTL.fixtures()
        check("капан-срещите ГИ ИМА в извора (проверката не е празна)",
              sum(1 for x in _fxs if _slug(x).endswith(("U91", "U92"))) == 4)
        check("🔴 среща с история само за ЕДИНИЯ не става карта",
              all(not _slug(x).endswith("U91") for x in sr))
        check("🔴 среща БЕЗ цена не става карта",
              all(not _slug(x).endswith("U92") for x in sr))
        check("подредбата е по |разлика в баланса|, най-голямата отпред",
              [abs(x["extra"]["delta"]) for x in sr]
              == sorted((abs(x["extra"]["delta"]) for x in sr), reverse=True))
        check("таванът реже",
              len(srechti(tavan=1)) == 1 and len(srechti(tavan=0)) == 0)
        check("таванът реже ОТГОРЕ (най-уверената остава)",
              srechti(tavan=1)[0]["home"] == sr[0]["home"])
        g["DNI"] = 0
        izchisti()
        check("🔴 TT_LOKAL_DNI=0 спира и срещите", srechti() == [])
        g["DNI"] = 14
        izchisti()
        TTL.izchisti_kesh()
        _F["myrtva"] = True
        check("🔴 при мъртъв извор srechti дава ZAPUSHENO, не празен списък",
              srechti() is ZAPUSHENO)
        _F["myrtva"] = False
        izchisti()
        TTL.izchisti_kesh()

        # ═══ 13. ФОРМАТЪТ НА ЕДИН ДЕН ═══
        izchisti()
        TTL.izchisti_kesh()
        d1 = den_rezultati("czech liga pro", _minus(_dnes(), 1))
        check("den_rezultati връща списък", isinstance(d1, list) and d1)
        check("всеки ред е с 5 полета",
              all(isinstance(r, list) and len(r) == 5 for r in d1))
        check("номерът на събитието пътува в реда",
              all(str(r[3]).strip() for r in d1))
        check("състоянието пътува в реда",
              all(r[4] in ("ended", "cancelled") for r in d1))
        check("отмененият мач е БЕЗ победител",
              all(r[2] is None for r in d1 if r[4] == "cancelled"))
        check("има и мачове С победител", any(r[2] for r in d1))
        _F["myrtva"] = True
        TTL.izchisti_kesh()
        check("🔴 den_rezultati при мъртва мрежа дава ZAPUSHENO",
              den_rezultati("czech liga pro", _minus(_dnes(), 1)) is ZAPUSHENO)
        _F["myrtva"] = False
        TTL.izchisti_kesh()

    finally:
        TTL._MREZHA[0] = star_mr
        TTL.__dict__["_RACHKA"] = star_ra
        _KESH_PAPKA[0] = star_kesh
        g["DNI"], g["NOVI"] = star_dni, star_novi
        _F.clear()
        TTL.izchisti_kesh()
        izchisti()

    for b in bad:
        print("счупено: " + b)
    print("tt_lokal: " + str(ok) + " минаха, " + str(len(bad)) + " паднаха.")
    return 0 if not bad else 1


# ══════════════════════════════════════════════════════════════ МУТАЦИИТЕ
def mutacii():
    g = globals()
    opiti = []

    def _fam_klyuch(ime):
        """🐛 сравнение по ПОСЛЕДНА ДУМА (фамилията лепи чужд запис)"""
        s = TTL._pochisti(ime)
        d = re.sub(r"[^A-Za-z ]", " ", s).lower().split()
        if not d:
            return (), ()
        return (d[-1],), (d[-1],)
    opiti.append(("името се свежда до ФАМИЛИЯТА (Andrienko M. -> andrienko)",
                  "TTL.klyuch_ime", _fam_klyuch))

    def _bez_bliznaci(a, b):
        """🐛 мач между двама с еднакъв хлабав ключ ВЛИЗА"""
        ka, kb = TTL.klyuch_ime(a), TTL.klyuch_ime(b)
        if not ka[0] or not kb[0] or ka[0] == kb[0]:
            return None
        return ka, kb
    opiti.append(("_dvete_imena пуска двамата Strnad един срещу друг",
                  "_dvete_imena", _bez_bliznaci))

    def _hlabav_vinagi(ime, now=None, dni=90):
        """🐛 хлабавият ключ се ползва и когато сочи ДВАМА"""
        ind = istoriya(now, dni)
        if ind is ZAPUSHENO:
            return ZAPUSHENO
        k = TTL.klyuch_ime(ime)
        if not k[0]:
            return None
        z = ind["strog"].get(k[0])
        if z is None:
            kand = sorted(ind["hlabav"].get(k[1]) or set())
            if not kand:
                return None
            z = ind["strog"].get(kand[0])
        return {"w": int(z["w"]), "l": int(z["l"])} if z else None
    opiti.append(("igrach взима ПЪРВИЯ при двусмислен хлабав ключ",
                  "igrach", _hlabav_vinagi))

    def _bez_skriti(cid, den, sast):
        """🐛 include_hidden пада — скритите мачове изчезват"""
        return (TTL.SM + "/events/?parent_id=" + str(cid) + "&state=" + str(sast) +
                "&sort=start_datetime,id&limit=200"
                "&pagination_last_start_datetime=" + str(den) + "T00:00:00Z"
                "&pagination_last_id=1")
    opiti.append(("_url_den изпуска include_hidden (скритите изчезват)",
                  "TTL._url_den", _bez_skriti))

    def _bez_stranica(lk, den, sastoyania=None):
        """🐛 само първата страница — една трета от деня пада тихо"""
        cid = TTL.LIGI[lk]["cid"]
        out, stignah = [], False
        for sast in (sastoyania or ("ended", "live", "upcoming", "cancelled")):
            d = TTL._json(TTL._url_den(cid, den, sast))
            if not isinstance(d, dict):
                continue
            stignah = True
            out += [e for e in (d.get("events") or [])
                    if isinstance(e, dict) and str(e.get("start_date")) == den]
        return out if stignah else ZAPUSHENO
    opiti.append(("_den_sabitiya чете само първата страница",
                  "TTL._den_sabitiya", _bez_stranica))

    def _prazno_vmesto_zapusheno(lk, den, mozhe_mrezha=True):
        """🐛 запушен ден се прави на празен ден"""
        r = _den_ORIG(lk, den, mozhe_mrezha)
        return [] if r is ZAPUSHENO else r
    opiti.append(("_den връща празен ден вместо ZAPUSHENO",
                  "_den", _prazno_vmesto_zapusheno))

    def _pishe_i_dnes(lk, den, redove):
        """🐛 днешният, още непълен ден влиза в кеша"""
        p = _pat(lk, den)
        if not p:
            return False
        try:
            os.makedirs(os.path.dirname(p))
        except OSError:
            pass
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"v": 1, "liga": lk, "den": den, "m": redove}, f,
                          ensure_ascii=False)
        except (OSError, ValueError, TypeError):
            return False
        return True
    opiti.append(("kesh_pishe записва и ДНЕШНИЯ (непълен) ден",
                  "kesh_pishe", _pishe_i_dnes))

    def _vklyuchva_dnes(now=None, dni=None):
        """🐛 прозорецът почва от ДНЕС — надничане в обратната проверка"""
        star = g["_minus"]
        g["_minus"] = lambda den, k: star(den, 0) if k == 1 else star(den, k - 1)
        try:
            return _istoriya_ORIG(now, dni)
        finally:
            g["_minus"] = star
    opiti.append(("istoriya включва ДНЕШНИЯ ден (надничане)",
                  "istoriya", _vklyuchva_dnes))

    def _prag_nula(z):
        """🐛 прагът пада — играч с 1 мач минава за познат"""
        return isinstance(z, dict)
    opiti.append(("stiga приема всякаква сводка (прагът 5 пада)",
                  "stiga", _prag_nula))

    def _bez_zapusheno(now=None, dni=None):
        """🐛 нула прочетени дни се обявява за честна нула"""
        r = _istoriya_ORIG(now, dni)
        return {"strog": {}, "hlabav": {}, "dni": []} if r is ZAPUSHENO else r
    opiti.append(("istoriya прави ZAPUSHENO на празен указател",
                  "istoriya", _bez_zapusheno))

    def _bez_byudzhet(now=None, dni=None):
        """🐛 бюджетът на новите дни се игнорира"""
        star = g["NOVI"]
        g["NOVI"] = 10 ** 6
        try:
            return _istoriya_ORIG(now, dni)
        finally:
            g["NOVI"] = star
    opiti.append(("istoriya не спазва бюджета TT_LOKAL_NOVI",
                  "istoriya", _bez_byudzhet))

    def _pobeditel_vinagi_dom(lk, den, mozhe_mrezha=True):
        """🐛 при непознат победител се подхвърля домакинът"""
        r = _den_ORIG(lk, den, mozhe_mrezha)
        if r is ZAPUSHENO:
            return r
        out = []
        for x in r:
            y = list(x)
            if y[2] and TTL.klyuch_ime(y[2])[1] not in (TTL.klyuch_ime(y[0])[1],
                                                        TTL.klyuch_ime(y[1])[1]):
                y[2] = y[0]
            out.append(y)
        return out
    opiti.append(("чуждият победител се приписва на домакина",
                  "_den", _pobeditel_vinagi_dom))

    def _neotsadeni_broyat(lk, den):
        """🐛 брои се и пазар, който още НЕ е отсъден"""
        ev = TTL._den_sabitiya(lk, den, ("ended", "cancelled"))
        if ev is ZAPUSHENO:
            return ZAPUSHENO
        po_id = {}
        for e in ev:
            a, sep, b = str(e.get("name") or "").partition(" vs ")
            if sep and a.strip() and b.strip():
                po_id[str(e.get("id"))] = (a.strip(), b.strip(),
                                           str(e.get("state") or ""))
        ids = list(po_id)
        paz = []
        for i in range(0, len(ids), 20):
            d = TTL._json(TTL._url_pazari(ids[i:i + 20]))
            if isinstance(d, dict):
                paz += [m for m in (d.get("markets") or [])
                        if isinstance(m, dict)
                        and (m.get("market_type") or {}).get("name")
                        == TTL.PAZAR_POBEDITEL]        # без state == settled
        m2e = {str(m.get("id")): str(m.get("event_id")) for m in paz}
        e2w = {}
        for i in range(0, len(paz), 20):
            c = TTL._json(TTL._url_kontrakti([m["id"] for m in paz[i:i + 20]]))
            for x in (c or {}).get("contracts", []):
                if x.get("state_or_outcome") == "winner":
                    eid = m2e.get(str(x.get("market_id")))
                    if eid:
                        e2w[eid] = str(x.get("name") or "")
        return [[po_id[e][0], po_id[e][1], e2w.get(e), e, po_id[e][2]] for e in ids]
    opiti.append(("den_rezultati брои и НЕотсъдените пазари",
                  "den_rezultati", _neotsadeni_broyat))

    def _chuzhd_pazar(lk, den):
        """🐛 взима се първият пазар на събитието, какъвто и да е"""
        ev = TTL._den_sabitiya(lk, den, ("ended", "cancelled"))
        if ev is ZAPUSHENO:
            return ZAPUSHENO
        po_id = {}
        for e in ev:
            a, sep, b = str(e.get("name") or "").partition(" vs ")
            if sep:
                po_id[str(e.get("id"))] = (a.strip(), b.strip(),
                                           str(e.get("state") or ""))
        ids = list(po_id)
        paz = []
        for i in range(0, len(ids), 20):
            d = TTL._json(TTL._url_pazari(ids[i:i + 20]))
            if isinstance(d, dict):
                paz += [m for m in (d.get("markets") or [])
                        if isinstance(m, dict) and m.get("state") == "settled"]
        m2e = {str(m.get("id")): str(m.get("event_id")) for m in paz}
        e2w = {}
        for i in range(0, len(paz), 20):
            c = TTL._json(TTL._url_kontrakti([m["id"] for m in paz[i:i + 20]]))
            for x in (c or {}).get("contracts", []):
                if x.get("state_or_outcome") == "winner":
                    eid = m2e.get(str(x.get("market_id")))
                    if eid:
                        e2w[eid] = str(x.get("name") or "")
        return [[po_id[e][0], po_id[e][1], e2w.get(e), e, po_id[e][2]] for e in ids]
    opiti.append(("den_rezultati не филтрира по WINNER_2_WAY",
                  "den_rezultati", _chuzhd_pazar))

    def _bez_cena(now=None, tavan=None, dni=None):
        """🐛 срещата става карта и БЕЗ цена"""
        if DNI <= 0:
            return []
        fx = TTL.fixtures()
        if not isinstance(fx, list):
            return ZAPUSHENO
        ind = TTL.index_ceni()
        if not isinstance(ind, dict):
            ind = {}
        out = []
        for f in fx:
            a = igrach(f.get("home"), now, dni if dni is not None else 90)
            b = igrach(f.get("away"), now, dni if dni is not None else 90)
            if not stiga(a) or not stiga(b):
                continue
            ex = dict(f.get("extra") or {})
            c = TTL.cena(f.get("home"), f.get("away"), f.get("league"),
                         kogato=ex.get("start"), ind=ind)
            if isinstance(c, dict):
                ex.update({"cena_dom": c["dom"], "cena_gost": c["gost"],
                           "cena_izvor": c["izvor"], "p_pazar": c["p_dom"],
                           "marzh": c["marzh"]})
            ex.update({"ist_dom": dict(a), "ist_gost": dict(b),
                       "delta": round(_rejting(a) - _rejting(b), 4)})
            r = dict(f)
            r["extra"] = ex
            out.append(r)
        out.sort(key=lambda x: -abs((x["extra"] or {}).get("delta") or 0.0))
        return out[:int(tavan)] if tavan is not None else out
    opiti.append(("srechti пуска среща БЕЗ цена", "srechti", _bez_cena))

    def _samo_domakina(now=None, tavan=None, dni=None):
        """🐛 иска се история само за ДОМАКИНА"""
        if DNI <= 0:
            return []
        fx = TTL.fixtures()
        if not isinstance(fx, list):
            return ZAPUSHENO
        ind = TTL.index_ceni()
        if not isinstance(ind, dict):
            ind = {}
        out = []
        for f in fx:
            a = igrach(f.get("home"), now, dni if dni is not None else 90)
            b = igrach(f.get("away"), now, dni if dni is not None else 90)
            if not stiga(a):
                continue                     # 🐛 гостът не се пита
            if not isinstance(b, dict):
                b = {"w": 0, "l": 0}
            ex = dict(f.get("extra") or {})
            c = TTL.cena(f.get("home"), f.get("away"), f.get("league"),
                         kogato=ex.get("start"), ind=ind)
            if not isinstance(c, dict):
                continue
            ex.update({"cena_dom": c["dom"], "cena_gost": c["gost"],
                       "cena_izvor": c["izvor"], "p_pazar": c["p_dom"],
                       "marzh": c["marzh"], "ist_dom": dict(a),
                       "ist_gost": dict(b),
                       "delta": round(_rejting(a) - _rejting(b), 4)})
            r = dict(f)
            r["extra"] = ex
            out.append(r)
        out.sort(key=lambda x: -abs((x["extra"] or {}).get("delta") or 0.0))
        return out[:int(tavan)] if tavan is not None else out
    opiti.append(("srechti иска история само за единия",
                  "srechti", _samo_domakina))

    def _po_chas(now=None, tavan=None, dni=None):
        """🐛 подредбата е по ЧАС — таванът реже случайно"""
        r = _srechti_ORIG(now, None, dni)
        if not isinstance(r, list):
            return r
        r.sort(key=lambda x: x["when"])
        return r[:int(tavan)] if tavan is not None else r
    opiti.append(("srechti подрежда по час, не по увереност",
                  "srechti", _po_chas))

    def _bez_izglazhdane(z):
        """🐛 балансът без изглаждане: 5-0 става 1.00 като 50-0"""
        n = z["w"] + z["l"]
        return 0.5 if n <= 0 else z["w"] / float(n)
    opiti.append(("_rejting без изглаждане (5-0 тежи колкото 50-0)",
                  "_rejting", _bez_izglazhdane))

    g["_igrach_ORIG"] = g["igrach"]
    g["_srechti_ORIG"] = g["srechti"]
    g["_istoriya_ORIG"] = g["istoriya"]
    g["_den_ORIG"] = g["_den"]

    tih = io.StringIO()
    with contextlib.redirect_stdout(tih):
        osnova = selftest()
    if osnova != 0:
        print("МУТАЦИИ: НЕ МОГА ДА ЗАПОЧНА — чистата самопроверка е червена.")
        print(tih.getvalue())
        return 1

    def _vzemi(ime):
        if ime.startswith("TTL."):
            return TTL.__dict__[ime[4:]]
        return g[ime]

    def _sloji(ime, v):
        if ime.startswith("TTL."):
            TTL.__dict__[ime[4:]] = v
        else:
            g[ime] = v

    ulov, propusk = 0, []
    for opis, ime, kryp in opiti:
        star = _vzemi(ime)
        _sloji(ime, kryp)
        try:
            t = io.StringIO()
            with contextlib.redirect_stdout(t):
                rez = selftest()
        except Exception as e:                                # noqa: BLE001
            rez, t = 1, io.StringIO("счупено: ГРЪМНА " + str(e)[:70])
        finally:
            _sloji(ime, star)
        if rez != 0:
            ulov += 1
            parva = [l.strip() for l in t.getvalue().splitlines()
                     if l.strip().startswith("счупено:")]
            print("  ✅ ХВАНАТА: " + opis)
            print("       -> " + (parva[0] if parva else "?"))
        else:
            propusk.append(opis)
            print("  ❌ ПРОПУСНАТА: " + opis)
    for k in ("_igrach_ORIG", "_istoriya_ORIG", "_den_ORIG", "_srechti_ORIG"):
        g.pop(k, None)
    print("МУТАЦИИ: " + str(ulov) + " хванати от " + str(len(opiti)))
    for p in propusk:
        print("   пропусната: " + p)
    return 0 if not propusk else 1


# ══════════════════════════════════════════════════════════════════ НА ЖИВО
def zhivo(dni=None):
    """Истинско питане — за очи, не за автомат."""
    izchisti()
    TTL.izchisti_kesh()
    t0 = time.time()
    print("═" * 74)
    print("TT_LOKAL НА ЖИВО · "
          + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"))
    print("DNI=%d NOVI=%d кеш=%s лиги=%s"
          % (DNI, NOVI, _KESH_PAPKA[0] or "НЯМА", TTL.vklyucheni()))
    print("═" * 74)
    ind = istoriya(dni=dni)
    if ind is ZAPUSHENO:
        print("🔴 ЗАПУШЕНО — нито един ден не мина.")
        return 1
    print("дни: %d %s" % (len(ind["dni"]),
                          (ind["dni"][0] + " .. " + ind["dni"][-1]) if ind["dni"] else ""))
    print("играчи: %d | броени мачове: %d" % (len(ind["strog"]), _STAT["broeni"]))
    print("изхвърлени: без победител %d, чужд победител %d, близнаци %d"
          % (_STAT["bez_pobeditel"], _STAT["chuzhd_pobeditel"], _STAT["bliznaci"]))
    n5 = sum(1 for v in ind["strog"].values() if v["w"] + v["l"] >= MIN_MACHOVE)
    print("с поне %d мача: %d от %d" % (MIN_MACHOVE, n5, len(ind["strog"])))
    fx = TTL.fixtures()
    if fx is ZAPUSHENO:
        print("🔴 срещите са запушени")
        return 1
    dva = 0
    for f in fx:
        if stiga(igrach(f["home"])) and stiga(igrach(f["away"])):
            dva += 1
    print("ДНЕШНИ СРЕЩИ: %d | с история за ДВАМАТА: %d (%.1f%%)"
          % (len(fx), dva, 100.0 * dva / max(1, len(fx))))
    print("заявки: %d | от кеша на tt_ligi: %d | %.0f сек"
          % (TTL._BROYACH["zayavki"], TTL._BROYACH["kesh"], time.time() - t0))
    for f in fx[:5]:
        a, b = igrach(f["home"]), igrach(f["away"])
        print("   %s  %s (%s) vs %s (%s)"
              % (f["when"].strftime("%H:%M"), f["home"], a, f["away"], b))
    return 0


if __name__ == "__main__":
    _a = sys.argv[1:]
    if "--mutacii" in _a:
        sys.exit(mutacii())
    if "--zhivo" in _a:
        _d = None
        for _i, _x in enumerate(_a):
            if _x == "--dni" and _i + 1 < len(_a):
                _d = int(_a[_i + 1])
        sys.exit(zhivo(_d))
    if "--dokumentaciya" in _a:
        print(__doc__)
        sys.exit(0)
    sys.exit(selftest())
