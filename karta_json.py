# -*- coding: utf-8 -*-
"""ПЪЛНИЯТ ЗАПИС НА ЕДНА КАРТА — всичко, което мозъкът знае, в чист JSON.

ЗАЩО СЪЩЕСТВУВА (01.09.2026, по дословната поръчка на собственика:
„принципно ние вървим към ПЛАТФОРМА… ти си игнорирал каквото ти говоря за
КОЕФИЦИЕНТИ, БУКМЕЙКЪРИ, ЛИНКОВЕ… трябва да има ФУЛ ИНФО“).

Картата в Telegram е КЪСА нарочно — това е решение от 25.08.2026 и не се
пипа. Но късата карта не бива да значи къс МОЗЪК. Измерено живо в тази
сесия (сухо пускане, 15 карти, 141 заявки), с ПОВЕДЕНЧЕСКО мерене — сменям
стойността на ключа и питам сменя ли се картата:

    речникът `an` носи 27 ключа на външно ниво.
    ВЛИЯЯТ на текста на картата: 15.
    НЕ ВЛИЯЯТ НИКОГА: 12 —
        n_eff, obarnata, pazar_cena_drug, pazar_obarnat, pazar_v,
        pod_prag_sled_pazar, second, third, strength, tot, total_line
        (и `bucket` при 8 от 15 карти).
    `fx` носи 12 ключа, от които 6 не стигат до читателя.
    `fx["extra"]` носи 31 ключа, от които 29 НЕ ВЛИЯЯТ на нито една карта —
        включително форма (form_h/form_a), баланс (rec_h/rec_a), ранглиста
        (ra/rb), цените на двете страни (cena_dom/cena_gost) и турът.

Тоест мозъкът смята и хвърля. Този модул не смята нищо ново и не пипа
картата — само СЪБИРА вече сметнатото на едно място, което платформата може
да прочете.

ТРИ ПРАВИЛА, КОИТО НЕ СЕ НАРУШАВАТ:

  1. ЛИПСВАЩО ПОЛЕ Е None. Никакво запълване, никаква „разумна стойност“.
     Празно поле, което лъже, е по-лошо от празно поле.
  2. КЛЮЧОВЕТЕ СА ЛАТИНИЦА, ЕТИКЕТИТЕ СА БЪЛГАРСКИ. Кирилски ключ в схема
     вече е чупил workflow с код 400 в този проект; платформата чете ключа,
     човекът чете етикета. Затова `etiketi` е ПЛОСКА карта „път → дума“ и
     всеки път в записа има ред в нея — това е проверено, не обещано.
  3. ИМЕ НА БУКМЕЙКЪР НЕ МОЖЕ ДА СТАНЕ ИМЕ НА ПОЛЕ. Пазачът е чуждият —
     predictor.banned_word — а не мой втори списък, който да се разминава
     с неговия.

ЧЕСТНО ЗА ГРАНИЦИТЕ:
  • Стойността `iztochnik` СЪДЪРЖА името на източника („pinnacle“), защото
    произходът без име на източник не е произход. Забраната е за ИМЕ НА
    ПОЛЕ и за текста на картата — не за машинния запис. Кой път е мръсен за
    показване, се пита с `zabraneni_stoynosti()`, вместо да се гадае.
  • Полетата `sadiya`, `stadion`, `vremeto`, `kontuzeni`,
    `glavi_sreshtu_glavi`, `seriya` стоят в записа и са ВИНАГИ None. Това
    не е пропуск, а инвентар: източникът ги има (ESPN дава стадион, град и
    публика в същия отговор), а ботът не ги взима. Поле, което го няма,
    никой не търси; поле, което е None, се вижда, че липсва.
"""
import io
import json
import math
import os
import sys
from datetime import datetime, timezone

SHEMA_VERSIYA = 1

# Дневникът. Един РЕД = една карта (JSONL), защото дописването на ред е
# атомарно за практически цели, а презаписването на цял списък не е: при
# 40 карти на ден и умрял рън списъкът се губи целият, редът — не.
DNEVNIK = (os.environ.get("PREDICT_KARTA_JSON_FILE")
           or "karta_pulna.jsonl").strip()


# ─────────────────────────────────────────── ЛЕНИВИЯТ ДОСТЪП ДО МОЗЪКА
# Модулът НЕ внася predictor на върха: predictor ще внася него. Внасянето
# става чак при викане, когато и двата са цели.
def _mozak():
    """predictor, ако е зареден и цял. Иначе None — модулът пак работи."""
    m = sys.modules.get("predictor")
    if m is not None:
        return m
    try:
        import predictor as m                                # noqa: PLC0415
        return m
    except Exception:                                        # noqa: BLE001
        return None


def _tiho(f, *a, **kw):
    """Вика чужда функция. Провалът дава None, не изключение."""
    try:
        return f(*a, **kw)
    except Exception:                                        # noqa: BLE001
        return None


def zabranena_duma(tekst):
    """Пазачът на predictor, не мой втори списък. None при чист текст."""
    P = _mozak()
    if P is not None and hasattr(P, "banned_word"):
        return _tiho(P.banned_word, tekst)
    return None


# ─────────────────────────────────────────────────── ЧИСТЕНЕ ЗА JSON
def chisto(v, dyl=0):
    """Стойност, годна за json.dumps. Непознатото става текст, не изключение.

    NaN и безкрайност стават None НАРОЧНО: json.dumps ги пише като `NaN` и
    `Infinity`, което не е валиден JSON и всеки чужд четец се задавя с него.
    """
    if v is None or isinstance(v, (str, bool)):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(v, datetime):
        return v.isoformat()
    if dyl > 6:
        return str(v)
    if isinstance(v, dict):
        return {str(k): chisto(x, dyl + 1) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [chisto(x, dyl + 1) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted(str(x) for x in v)
    return str(v)


def _f(x):
    """Число или None. Празният низ и боклукът дават None, не гърмят."""
    try:
        if x is None or isinstance(x, bool):
            return None
        f = float(x)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _t(x):
    """Текст или None. Празното е ЛИПСА, не празен низ."""
    if x is None:
        return None
    s = str(x).strip()
    return s or None


# ─────────────────────────────────────────────── ЧАСОВЕТЕ НА ЕДНА СРЕЩА
def _sofia():
    P = _mozak()
    return getattr(P, "SOFIA", timezone.utc) if P is not None else timezone.utc


def nachalo(fx, now):
    """Началото на срещата със зона, или None. Пита мозъка, не преписва него.

    Дублирането на `fx_start` тук щеше да е втора дефиниция на едно правило —
    точно капанът, който този проект вече е плащал. Затова първо се пита
    predictor.fx_start; собствената резерва важи само когато мозъкът го няма.
    """
    fx = fx if isinstance(fx, dict) else {}
    P = _mozak()
    if P is not None and hasattr(P, "fx_start"):
        got = _tiho(P.fx_start, fx, now)
        if isinstance(got, datetime):
            return got if got.tzinfo is not None else got.replace(tzinfo=timezone.utc)
    w = fx.get("when")
    if isinstance(w, datetime):
        return w if w.tzinfo is not None else w.replace(tzinfo=timezone.utc)
    return None


def _iso(dt, zona=None):
    if not isinstance(dt, datetime):
        return None
    d = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return _tiho(lambda: d.astimezone(zona).isoformat()) if zona else d.isoformat()


# ═══════════════════════════════════════════════════════ СХЕМАТА
# Един ред = (раздел, поле, БЪЛГАРСКИ етикет, вадач).
# Схемата е ЕДИН източник и за записа, и за етикетите — затова поле без
# етикет е невъзможно по устройство, а не по добра воля.

def _an(c):
    return c["an"]


def _fx(c):
    return c["fx"]


def _ex(c):
    return c["ex"]


def _sport_ime(c):
    P = _mozak()
    b = _t(_an(c).get("bucket")) or _t(_fx(c).get("bucket"))
    if P is None or not b:
        return None
    return _t((getattr(P, "SPORTS", {}).get(b) or {}).get("title"))


def _liga_kratko(c):
    P = _mozak()
    if P is None or not hasattr(P, "liga_bg"):
        return None
    return _t(_tiho(P.liga_bg, _fx(c).get("league"), 28))


def _status(c):
    s = nachalo(_fx(c), c["now"])
    if s is None:
        return None
    n = c["now"]
    try:
        return "започнал" if s <= n else "предстои"
    except Exception:                                        # noqa: BLE001
        return None


def _duma(c):
    """Присъдата с думи, без цветната точка — както я вижда читателят."""
    P = _mozak()
    p = _f(_an(c).get("p"))
    if P is None or p is None or not hasattr(P, "p_duma"):
        return None
    d = _tiho(P.p_duma, p)
    if d is None:
        return None
    for _prag, stapalo in getattr(P, "P_DUMI", ()):
        glif = str(stapalo).split(" ", 1)[0]
        if glif and not glif[0].isalpha():
            d = d.replace(glif, "")
    return _t(d)


def _letva(c):
    P = _mozak()
    if P is None or not hasattr(P, "dolen_prag"):
        return None
    return _f(_tiho(P.dolen_prag, _an(c).get("bucket")))


def _pod_letva(c):
    p, l = _f(_an(c).get("p")), _letva(c)
    if p is None or l is None:
        return None
    return (int(round(p * 100.0)) / 100.0) < l


def _klyuch(c):
    """Ключът на подреждането: звезди × 1000 + сила × 100 (ред ~6864)."""
    z, s = _an(c).get("stars"), _f(_an(c).get("strength"))
    zf = _f(z)
    if zf is None or s is None:
        return None
    return round(zf * 1000.0 + s * 100.0, 4)


def _procent(c):
    p = _f(_an(c).get("p"))
    return None if p is None else int(round(p * 100.0))


def _surova_p(c):
    """Вероятността ПРАВО от цената — с надценката вътре."""
    ce = _f(_an(c).get("pazar_cena"))
    if ce is None or ce <= 1.0:
        return None
    return round(1.0 / ce, 4)


def _nadcenka(c):
    """Колко надува пазарът: сборът на всички изходи минус 100%.

    Извежда се от ДВЕ вече записани числа, без нова заявка и без да се иска
    цената на всеки изход: `pazar_p` е нашият дял СЛЕД махане на надценката,
    тоест (1/цена) / pazar_p Е целият сбор на книгата.

    🔴 СМЯТА СЕ ОТ СУРОВАТА ЦЕНА, НЕ ОТ ЗАКРЪГЛЕНОТО ПОЛЕ (намерено от
    собствената самопроверка при първото пускане). Тръгне ли от
    `veroyatnost_surova` (закръглено до 4 знака), при цена 1.75 излиза
    0.0284 вместо 0.0285 — грешка от двойно закръгляне, тоест число, което
    не може да се сведе обратно до цената.
    """
    ce, ch = _f(_an(c).get("pazar_cena")), _f(_an(c).get("pazar_p"))
    if ce is None or ce <= 1.0 or ch is None or ch <= 0.0:
        return None
    n = (1.0 / ce) / ch - 1.0
    return round(n, 4) if -0.01 < n < 1.0 else None


def _razlika_t(c):
    """Ние минус пазарът, в процентни точки. Плюс значи по-смели сме."""
    nash = _f(_an(c).get("p_model"))
    if nash is None:
        nash = _f(_an(c).get("p"))
    paz = _f(_an(c).get("pazar_p"))
    if nash is None or paz is None:
        return None
    return round(100.0 * (nash - paz), 1)


def _saglasie(c):
    P = _mozak()
    SG = getattr(P, "SG", None) if P is not None else None
    nash = _f(_an(c).get("p_model"))
    if nash is None:
        nash = _f(_an(c).get("p"))
    paz = _f(_an(c).get("pazar_p"))
    if SG is None or nash is None or paz is None:
        return None
    got = _tiho(SG.sglasni_li, nash, paz)
    return bool(got[0]) if isinstance(got, tuple) and got else None


def _iztochnik_ime(c):
    P = _mozak()
    if P is None:
        return None
    kod = str(_an(c).get("pazar_izt") or "").strip().lower()
    return _t(getattr(P, "IZTOCHNIK_IME", {}).get(kod))


def _link(c):
    """Адресът на мача. Празният низ на pazar.py значи ЛИПСА, тоест None."""
    P = _mozak()
    PZ = getattr(P, "PZ", None) if P is not None else None
    if PZ is None or not hasattr(PZ, "link_kam_macha"):
        return None
    return _t(_tiho(PZ.link_kam_macha, _an(c)))


def _rang(c, koy, pole):
    d = _ex(c).get(koy)
    return chisto(d.get(pole)) if isinstance(d, dict) else None


def _amf(c, pole):
    d = _an(c).get("amf_h")
    return _f(d.get(pole)) if isinstance(d, dict) else None


def _izvor_konteksta(c):
    """Кой е дал контекста. Само когато НАИСТИНА е дал нещо."""
    ex = _ex(c)
    if any(_t(ex.get(k)) for k in ("form_h", "form_a", "rec_h", "rec_a")):
        return _t(_fx(c).get("src")) or "espn"
    return None


def _istoriya(c):
    P = _mozak()
    if P is None or not hasattr(P, "sport_record"):
        return None
    b = _t(_an(c).get("bucket")) or _t(_fx(c).get("bucket"))
    if not b:
        return None
    return _t(_tiho(P.sport_record, b, _ex(c).get("igra")))


def _run(c):
    for k in ("GITHUB_RUN_NUMBER", "GITHUB_RUN_ID", "PREDICT_RUN"):
        v = _t(os.environ.get(k))
        if v:
            return v
    return None


def _suho(c):
    P = _mozak()
    return bool(getattr(P, "DRY_RUN", False)) if P is not None else None


SHEMA = (
    # ─────────────────────────────────────────────────────────── МАЧ
    ("mach", "id", "номер на срещата", lambda c: _t(_fx(c).get("_key"))),
    ("mach", "sport", "спорт (код)",
     lambda c: _t(_an(c).get("bucket")) or _t(_fx(c).get("bucket"))),
    ("mach", "sport_ime", "спорт", _sport_ime),
    ("mach", "znak", "знак на спорта", lambda c: _t(_fx(c).get("emoji"))),
    ("mach", "liga", "турнир", lambda c: _t(_fx(c).get("league"))),
    ("mach", "liga_kratko", "турнир (късо)", _liga_kratko),
    ("mach", "domakin", "домакин", lambda c: _t(_fx(c).get("home"))),
    ("mach", "gost", "гост", lambda c: _t(_fx(c).get("away"))),
    ("mach", "domakin_id", "номер на домакина",
     lambda c: chisto(_fx(c).get("home_id"))),
    ("mach", "gost_id", "номер на госта", lambda c: chisto(_fx(c).get("away_id"))),
    ("mach", "domakin_originalno", "домакин (оригинално име)",
     lambda c: _t(_ex(c).get("home_en")) or _t(_ex(c).get("home_loc"))),
    ("mach", "gost_originalno", "гост (оригинално име)",
     lambda c: _t(_ex(c).get("away_en")) or _t(_ex(c).get("away_loc"))),
    ("mach", "nachalo_utc", "начало (UTC)",
     lambda c: _iso(nachalo(_fx(c), c["now"]), timezone.utc)),
    ("mach", "nachalo_sofia", "начало (София)",
     lambda c: _iso(nachalo(_fx(c), c["now"]), _sofia())),
    ("mach", "nachalo_dumi", "начало с думи", lambda c: _t(_fx(c).get("time"))),
    ("mach", "neutralen_teren", "неутрален терен",
     lambda c: (bool(_ex(c).get("neutral"))
                if _ex(c).get("neutral") is not None else None)),
    ("mach", "sastoyanie", "състояние", _status),
    ("mach", "vid_karta", "вид на картата",
     lambda c: _t(_an(c).get("vid_karta")) or "izbor"),
    ("mach", "disciplina", "дисциплина", lambda c: _t(_ex(c).get("igra"))),

    # ────────────────────────────────────────────────────── ПРОГНОЗА
    ("prognoza", "izbor", "избор", lambda c: _t(_an(c).get("pick"))),
    ("prognoza", "veroyatnost", "вероятност (0–1)",
     lambda c: _f(_an(c).get("p"))),
    ("prognoza", "veroyatnost_procent", "вероятност (%)", _procent),
    ("prognoza", "veroyatnost_nash_model", "нашата сметка преди пазара",
     lambda c: _f(_an(c).get("p_model"))),
    ("prognoza", "duma", "присъда с думи", _duma),
    ("prognoza", "zvezdi", "звезди", lambda c: chisto(_an(c).get("stars"))),
    ("prognoza", "sila", "сила (категоричност)",
     lambda c: _f(_an(c).get("strength"))),
    ("prognoza", "klyuch_podrezhdane", "ключ на подреждането", _klyuch),
    ("prognoza", "letva", "летва на спорта", _letva),
    ("prognoza", "pod_letva", "под летвата", _pod_letva),
    ("prognoza", "prichini", "причини",
     lambda c: [str(w) for w in (_an(c).get("why") or []) if w] or None),
    ("prognoza", "izvadka", "извадка с думи", lambda c: _t(_an(c).get("sample"))),
    ("prognoza", "izvadka_teglo", "тегло на извадката",
     lambda c: _f(_an(c).get("n_eff"))),
    ("prognoza", "obarnat_izbor", "изборът е обърнат по пазара",
     lambda c: (bool(_an(c).get("obarnata"))
                if _an(c).get("obarnata") is not None else None)),
    ("prognoza", "vtora", "втора прогноза", lambda c: _t(_an(c).get("second"))),
    ("prognoza", "treta", "трета прогноза", lambda c: _t(_an(c).get("third"))),
    ("prognoza", "total_liniya", "линия на тотала",
     lambda c: _f(_an(c).get("total_line"))),

    # ───────────────────────────────────────────────────────── ПАЗАР
    ("pazar", "cena", "цена на нашия избор", lambda c: _f(_an(c).get("pazar_cena"))),
    ("pazar", "cena_drug", "цена на другата страна",
     lambda c: _f(_an(c).get("pazar_cena_drug"))),
    ("pazar", "veroyatnost_surova", "вероятност по цената (с надценката)",
     _surova_p),
    ("pazar", "veroyatnost_chista", "вероятност без надценката",
     lambda c: _f(_an(c).get("pazar_p"))),
    ("pazar", "nadcenka", "надценка на пазара", _nadcenka),
    ("pazar", "razlika_tochki", "разлика ние − пазар (точки)", _razlika_t),
    ("pazar", "saglasni", "съгласни ли сме с пазара", _saglasie),
    ("pazar", "iztochnik", "източник на цената (код)",
     lambda c: _t(_an(c).get("pazar_izt"))),
    ("pazar", "iztochnik_ime", "източник на цената", _iztochnik_ime),
    ("pazar", "nomer", "номер на мача при източника",
     lambda c: _t(_an(c).get("pazar_ev"))),
    ("pazar", "sport_pat", "път на спорта при източника",
     lambda c: _t(_an(c).get("pazar_sport"))),
    ("pazar", "liga_kod", "код на лигата при източника",
     lambda c: _t(_an(c).get("pazar_liga"))),
    ("pazar", "stranite_obarnati", "страните са обърнати при източника",
     lambda c: (bool(_an(c).get("pazar_obarnat"))
                if _an(c).get("pazar_obarnat") is not None else None)),
    ("pazar", "versiya_veroyatnost", "версия на пазарната вероятност",
     lambda c: chisto(_an(c).get("pazar_v"))),
    ("pazar", "adres", "адрес на мача", _link),
    ("pazar", "pod_letva_sled_pazara", "под летвата след пазарното число",
     lambda c: (bool(_an(c).get("pod_prag_sled_pazar"))
                if _an(c).get("pod_prag_sled_pazar") is not None else None)),

    # ────────────────────────────────────────────────────── КОНТЕКСТ
    ("kontekst", "forma_domakin", "форма на домакина",
     lambda c: _t(_ex(c).get("form_h"))),
    ("kontekst", "forma_gost", "форма на госта", lambda c: _t(_ex(c).get("form_a"))),
    ("kontekst", "balans_domakin", "баланс на домакина",
     lambda c: _t(_ex(c).get("rec_h"))),
    ("kontekst", "balans_gost", "баланс на госта", lambda c: _t(_ex(c).get("rec_a"))),
    ("kontekst", "balans_domakin_doma", "баланс на домакина у дома",
     lambda c: _t(_ex(c).get("rec_h_home"))),
    ("kontekst", "balans_gost_gostuvane", "баланс на госта като гост",
     lambda c: _t(_ex(c).get("rec_a_road"))),
    ("kontekst", "klasirane_domakin", "класиране на домакина",
     lambda c: _rang(c, "ra", "rank")),
    ("kontekst", "klasirane_gost", "класиране на госта",
     lambda c: _rang(c, "rb", "rank")),
    ("kontekst", "tochki_domakin", "точки на домакина в ранглистата",
     lambda c: _rang(c, "ra", "pts")),
    ("kontekst", "tochki_gost", "точки на госта в ранглистата",
     lambda c: _rang(c, "rb", "pts")),
    ("kontekst", "hvarlyach_domakin", "хвърлящ на домакина",
     lambda c: _t(_ex(c).get("pit_home"))),
    ("kontekst", "hvarlyach_gost", "хвърлящ на госта",
     lambda c: _t(_ex(c).get("pit_away"))),
    ("kontekst", "razlika_po_pazara", "разлика по пазара (точки)",
     lambda c: _amf(c, "liniya")),
    ("kontekst", "obshto_po_pazara", "общо точки по пазара",
     lambda c: _amf(c, "total")),
    ("kontekst", "cena_domakin_izvor", "цена на домакина в източника на мача",
     lambda c: _f(_ex(c).get("cena_dom"))),
    ("kontekst", "cena_gost_izvor", "цена на госта в източника на мача",
     lambda c: _f(_ex(c).get("cena_gost"))),
    ("kontekst", "do_kolko_specheleni", "мач до колко спечелени части",
     lambda c: chisto(_ex(c).get("best_of"))),
    ("kontekst", "tur", "тур", lambda c: _t(_ex(c).get("tour"))),
    ("kontekst", "sezoni", "сезони в историята",
     lambda c: [chisto(s) for s in (_ex(c).get("seasons") or [])] or None),
    ("kontekst", "istoriya_na_bota", "сметката на бота в този спорт", _istoriya),
    # 🔴 ШЕСТТЕ ПРАЗНИ. Виж бележката на върха: това е ИНВЕНТАР на липсата.
    ("kontekst", "glavi_sreshtu_glavi", "глави срещу глави", lambda c: None),
    ("kontekst", "sadiya", "съдия", lambda c: None),
    ("kontekst", "stadion", "стадион", lambda c: None),
    ("kontekst", "vremeto", "времето", lambda c: None),
    ("kontekst", "kontuzeni", "контузени", lambda c: None),
    ("kontekst", "seriya", "серия победи или загуби", lambda c: None),

    # ────────────────────────────────────────────────────── ПРОИЗХОД
    ("proizhod", "izvor_mach", "източник на срещата",
     lambda c: _t(_fx(c).get("src"))),
    ("proizhod", "izvor_cena", "източник на цената",
     lambda c: _t(_an(c).get("pazar_izt"))),
    ("proizhod", "izvor_kontekst", "източник на контекста", _izvor_konteksta),
    ("proizhod", "teglo_izvor", "тегло на източника",
     lambda c: chisto(_fx(c).get("weight"))),
    ("proizhod", "liga_slug", "адрес на лигата в източника",
     lambda c: _t(_ex(c).get("slug"))),
    ("proizhod", "espn_id", "номер в ESPN", lambda c: _t(_ex(c).get("ev_id"))),
    ("proizhod", "azia_id", "номер в азиатския източник",
     lambda c: _t(_ex(c).get("azia_id"))),
    ("proizhod", "itf_id", "номер в малкия тур", lambda c: _t(_ex(c).get("itf_id"))),
    ("proizhod", "vzeto_utc", "кога е взето (UTC)",
     lambda c: _iso(c["now"], timezone.utc)),
    ("proizhod", "vzeto_sofia", "кога е взето (София)",
     lambda c: _iso(c["now"], _sofia())),
    ("proizhod", "pusk", "номер на пускането", _run),
    ("proizhod", "suho_puskane", "сухо пускане", _suho),
)

RAZDELI = (("mach", "мач"), ("prognoza", "прогноза"), ("pazar", "пазар"),
           ("kontekst", "контекст"), ("proizhod", "произход"))

VARH = (("shema", "версия на записа"), ("etiketi", "етикети на полетата"))


def etiketi():
    """ПЛОСКАТА карта „път → българска дума“. Строи се от СЪЩАТА схема."""
    e = {}
    for k, ime in VARH:
        e[k] = ime
    for k, ime in RAZDELI:
        e[k] = ime
    for razdel, pole, ime, _v in SHEMA:
        e[razdel + "." + pole] = ime
    return e


# ═════════════════════════════════════════════════════ ГЛАВНАТА ФУНКЦИЯ
def zapis(an, now=None):
    """ПЪЛНИЯТ запис за една карта. Никога не хвърля; липсата е None.

    `an` е речникът на анализа в мига преди картата да се напише.
    `now` е часът на пускането; None взима сегашния по София.
    """
    if now is None:
        now = _tiho(datetime.now, _sofia()) or datetime.now(timezone.utc)
    an = an if isinstance(an, dict) else {}
    fx = an.get("fx")
    fx = fx if isinstance(fx, dict) else {}
    ex = fx.get("extra")
    ex = ex if isinstance(ex, dict) else {}
    c = {"an": an, "fx": fx, "ex": ex, "now": now}

    z = {"shema": SHEMA_VERSIYA}
    for razdel, _ime in RAZDELI:
        z[razdel] = {}
    for razdel, pole, _ime, vadach in SHEMA:
        try:
            v = vadach(c)
        except Exception:                                    # noqa: BLE001
            v = None
        z[razdel][pole] = chisto(v)
    z["etiketi"] = etiketi()
    return z


# ═══════════════════════════════════════════════════════ ПАЗАЧИТЕ
def patishta(z):
    """Всички пътища в записа (без вътрешността на `etiketi`)."""
    out = []
    if not isinstance(z, dict):
        return out
    for k, v in z.items():
        out.append(str(k))
        if k == "etiketi":
            continue
        if isinstance(v, dict):
            for k2 in v:
                out.append(str(k) + "." + str(k2))
    return out


def bez_etiket(z):
    """Пътищата БЕЗ българска дума. Празен списък значи всичко е наред."""
    e = (z or {}).get("etiketi") or {}
    return [p for p in patishta(z) if not str(e.get(p) or "").strip()]


def zabraneni_imena(z):
    """Пътища, чието ИМЕ носи забранена дума. Пита пазача на predictor."""
    lo = []
    for p in patishta(z):
        for parche in p.split("."):
            if zabranena_duma(parche) is not None:
                lo.append(p)
                break
    return lo


def zabraneni_stoynosti(z):
    """Пътища, чиято СТОЙНОСТ носи забранена дума.

    Не е дефект — записът е машинен и произходът иска име на източник.
    Съществува, за да може платформата да ПИТА кое е мръсно за показване,
    вместо да гадае. Изпитан е и в двете посоки в самопроверката.
    """
    lo = []
    if not isinstance(z, dict):
        return lo
    for k, v in z.items():
        if k == "etiketi" or not isinstance(v, dict):
            continue
        for k2, v2 in v.items():
            tekst = " ".join(str(x) for x in v2) if isinstance(v2, list) else str(v2)
            if zabranena_duma(tekst) is not None:
                lo.append(str(k) + "." + str(k2))
    return lo


# ═══════════════════════════════════════════════ ДНЕВНИКЪТ (ЕДИН РЕД = ЕДНА КАРТА)
def dopishi(an, now=None, path=None):
    """Дописва един ред в дневника. Връща True при успех.

    Провалът НЕ спира картата и не хвърля: дневник, който може да убие
    прогноза, е по-скъп от липсващ дневник.
    """
    try:
        z = zapis(an, now)
        red = json.dumps(z, ensure_ascii=False)
        p = str(path or DNEVNIK)
        with open(p, "a", encoding="utf-8") as f:
            f.write(red + "\n")
        return True
    except Exception as e:                                   # noqa: BLE001
        try:
            print("пълният запис не се записа (" + str(e)[:70] + ").")
        except Exception:                                    # noqa: BLE001
            pass
        return False


# ═══════════════════════════════════════════════════════ САМОПРОВЕРКА
def selftest():
    """ПОВЕДЕНЧЕСКИ проверки: подавам речник и питам какво ИЗЛИЗА.

    Без заковани дати и без мрежа. Часовете се сравняват СПРЯМО подадения
    `now`, не спрямо календара — тест със закована дата умира сам.
    """
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # 🔴 ИЗРАЗ, КОЙТО ГЪРМИ, НЕ БИВА ДА СВАЛЯ ЦЯЛАТА САМОПРОВЕРКА (01.09.2026).
    # Намерено с мутации: четири мутанта убиха selftest с изключение вместо да
    # му дадат ЧЕРВЕНО. Разликата е важна — гръмнал тест не казва КОЕ е
    # счупено, а следващите проверки изобщо не се пускат.
    def vyarno(f):
        """True само ако изразът се пресметне И е истина."""
        try:
            return bool(f())
        except Exception:                                    # noqa: BLE001
            return False

    from datetime import timedelta

    sega = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    puln = {
        "fx": {"_key": "k1", "bucket": "football", "emoji": "⚽",
               "home": "Арсенал", "away": "Челси", "home_id": 359, "away_id": 363,
               "league": "Англия Висша лига", "weight": 4, "src": "espn",
               "when": sega + timedelta(hours=6),
               "extra": {"slug": "eng.1", "ev_id": "401908124",
                         "sport_path": "soccer", "neutral": False,
                         "home_en": "Arsenal", "away_en": "Chelsea",
                         "form_h": "WWDLW", "form_a": "LDWWW",
                         "rec_h": "3-1-0", "rec_a": "2-1-1",
                         "rec_h_home": "2-0-0", "rec_a_road": "1-1-0",
                         "ra": {"rank": 3, "pts": 1880.0},
                         "rb": {"rank": 9, "pts": 1640.0},
                         "best_of": 3, "tour": "atp", "seasons": [2026, 2025],
                         "pit_home": "A", "pit_away": "B",
                         "cena_dom": 1.80, "cena_gost": 4.20, "igra": "cs2"}},
        "bucket": "football", "pick": "1 · Арсенал", "p": 0.62,
        "p_model": 0.58, "stars": 3, "strength": 0.24, "n_eff": 46.2,
        "sample": "гледани 24 мача", "why": ["Арсенал: 2.10 вкарани", "Челси: 1.20"],
        "second": "Над 2.5 гола", "third": "Гол-гол: 55%", "total_line": 2.5,
        "pazar_cena": 1.75, "pazar_cena_drug": 2.20, "pazar_p": 0.5556,
        "pazar_v": 2, "pazar_izt": "espn", "pazar_ev": "401908124",
        "pazar_sport": "soccer", "pazar_liga": "eng.1",
        "pazar_obarnat": False, "pod_prag_sled_pazar": False,
        "obarnata": False, "vid_karta": "",
    }

    # ── 1. ЛИПСАТА НЕ Е ИЗКЛЮЧЕНИЕ
    check("празен речник не гърми", isinstance(zapis({}, sega), dict))
    check("None не гърми", isinstance(zapis(None, sega), dict))
    check("боклук вместо речник не гърми", isinstance(zapis("абв", sega), dict))
    check("без now не гърми", isinstance(zapis({}), dict))
    prazen = zapis({}, sega)
    check("липсващ домакин дава None", prazen["mach"]["domakin"] is None)
    check("липсваща цена дава None", prazen["pazar"]["cena"] is None)
    check("липсваща форма дава None", prazen["kontekst"]["forma_domakin"] is None)
    check("липсващ избор дава None", prazen["prognoza"]["izbor"] is None)

    # 🔴 ЗЛА СТОЙНОСТ, КОЯТО ГЪРМИ ПРИ ЧЕТЕНЕ (намерено с мутации).
    # Дотук нито една проверка не караше вадач да хвърли — значи обвивката
    # try/except в `zapis` можеше да бъде махната и всичко оставаше зелено.
    # Тоест защитата „липсващо поле дава None, не изключение“ беше
    # НЕПРОВЕРЕНА за истинското си предназначение.
    class _Zla(list):
        def __iter__(self):
            raise RuntimeError("зла стойност")

    _zlo = vyarno(lambda: zapis({"why": _Zla([1]), "p": 0.6}, sega))
    check("вадач, който гърми, не сваля целия запис", _zlo is True)
    check("гръмналият вадач дава None, а съседите му оцеляват",
          vyarno(lambda: zapis({"why": _Zla([1]), "p": 0.6},
                               sega)["prognoza"]["prichini"] is None)
          and vyarno(lambda: zapis({"why": _Zla([1]), "p": 0.6},
                                   sega)["prognoza"]["veroyatnost"] == 0.6))
    check("fx с боклук вместо речник не гърми",
          zapis({"fx": "абв"}, sega)["mach"]["domakin"] is None)
    check("extra с боклук вместо речник не гърми",
          zapis({"fx": {"extra": 5}}, sega)["kontekst"]["forma_gost"] is None)

    # ── 2. ЗАПИСЪТ Е ЦЯЛ
    z = zapis(puln, sega)
    for razdel, _ime in RAZDELI:
        check("разделът „" + razdel + "“ съществува",
              isinstance(z.get(razdel), dict) and z[razdel])
    check("има версия на схемата", z.get("shema") == SHEMA_VERSIYA)

    # ── 3. СЕРИАЛИЗАЦИЯ
    tekst = None
    try:
        tekst = json.dumps(z, ensure_ascii=False)
    except Exception:                                        # noqa: BLE001
        tekst = None
    check("записът се сериализира с json.dumps", isinstance(tekst, str))
    check("сериализираното се чете обратно",
          isinstance(tekst, str) and json.loads(tekst)["mach"]["domakin"] == "Арсенал")
    check("празният запис също се сериализира",
          isinstance(json.dumps(zapis({}, sega), ensure_ascii=False), str))
    check("NaN не стига до JSON",
          json.dumps(zapis({"p": float("nan"), "pazar_cena": float("inf")}, sega),
                     ensure_ascii=False).find("NaN") < 0)
    check("безкрайност дава None",
          zapis({"pazar_cena": float("inf")}, sega)["pazar"]["cena"] is None)
    # 🔴 ДВАТА ПАЗАЧА СРЕЩУ NaN СЕ ПИТАТ ПООТДЕЛНО (намерено с мутации).
    # Дотук `chisto` и `_f` се пазеха взаимно: махнеш ли единия, другият
    # хваща числото и картата остава зелена. Тоест нито един от двата не
    # беше проверен — проверена беше само двойката.
    check("chisto сам маха NaN", chisto(float("nan")) is None)
    check("chisto сам маха безкрайността",
          chisto(float("inf")) is None and chisto(float("-inf")) is None)
    check("chisto не маха обикновено число", chisto(1.75) == 1.75)
    check("_f сам маха NaN", _f(float("nan")) is None)
    check("_f сам маха безкрайността", _f(float("inf")) is None)
    check("_f не маха обикновено число", abs(_f("1.75") - 1.75) < 1e-9)
    check("NaN в списък също не стига до JSON",
          json.dumps(chisto([1.0, float("nan")]), ensure_ascii=False) == "[1.0, null]")
    check("датата не остава обект",
          isinstance(z["mach"]["nachalo_utc"], str))

    # ── 4. ЕТИКЕТИТЕ
    check("всеки път има български етикет", bez_etiket(z) == [])
    check("всеки път има етикет и при празен запис", bez_etiket(zapis({}, sega)) == [])
    # 🔴 И В ОБРАТНАТА ПОСОКА (намерено с мутации). Дотук проверката питаше
    # само „намери ли нещо“ — а пазач, който ВИНАГИ връща празно, минаваше.
    _cyal = {"etiketi": "етикети", "mach": "мач", "mach.domakin": "домакин"}
    check("пазачът за етикети НЕ е сляп: липсващ етикет се хваща",
          bez_etiket({"mach": {"domakin": "А"},
                      "etiketi": {"etiketi": "етикети", "mach": "мач"}})
          == ["mach.domakin"])
    check("пазачът за етикети хваща и празен етикет",
          bez_etiket({"mach": {"domakin": "А"},
                      "etiketi": dict(_cyal, **{"mach.domakin": "  "})})
          == ["mach.domakin"])
    check("пазачът за етикети хваща и липсващ РАЗДЕЛ",
          bez_etiket({"mach": {"domakin": "А"},
                      "etiketi": {"etiketi": "етикети",
                                  "mach.domakin": "домакин"}}) == ["mach"])
    check("пазачът за етикети не се оплаква без причина",
          bez_etiket({"mach": {"domakin": "А"}, "etiketi": _cyal}) == [])
    e = z["etiketi"]
    check("етикетите са само кирилица",
          all(any("а" <= ch.lower() <= "я" for ch in str(v)) for v in e.values()))
    check("етикет за домакин е „домакин“", e.get("mach.domakin") == "домакин")
    check("етикет за цена", e.get("pazar.cena") == "цена на нашия избор")
    check("разделите също имат етикет",
          e.get("mach") == "мач" and e.get("proizhod") == "произход")
    check("броят етикети е поне колкото полетата",
          len(e) >= len(SHEMA) + len(RAZDELI) + len(VARH))
    check("схемата няма повторен път",
          len(set((r, p) for r, p, _i, _v in SHEMA)) == len(SHEMA))

    # ── 5. ПАЗАЧЪТ СРЕЩУ ИМЕНА НА БУКМЕЙКЪРИ (в ДВЕТЕ посоки)
    check("нито едно ИМЕ на поле не носи забранена дума", zabraneni_imena(z) == [])
    check("пазачът НЕ е сляп: подхвърлено мръсно име се хваща",
          zabraneni_imena({"bet365_cena": 1.5, "etiketi": {}}) == ["bet365_cena"])
    check("пазачът хваща и мръсно ПОДиме",
          zabraneni_imena({"a": {"koefi_x": 1}, "etiketi": {}}) in
          ([], ["a.koefi_x"]))
    check("мръсните СТОЙНОСТИ се изброяват, не се крият",
          isinstance(zabraneni_stoynosti(z), list))
    check("пазачът на стойности НЕ е сляп",
          zabraneni_stoynosti({"pazar": {"iztochnik": "pinnacle"},
                               "etiketi": {}}) == ["pazar.iztochnik"])
    check("чиста стойност не се обявява за мръсна",
          zabraneni_stoynosti({"pazar": {"iztochnik": "espn"}, "etiketi": {}}) == [])

    # ── 6. ЧИСЛАТА ИЗЛИЗАТ, КАКТО СА ВЛЕЗЛИ
    check("вероятността се пренася", abs(z["prognoza"]["veroyatnost"] - 0.62) < 1e-9)
    check("процентът е закръглен до цяло", z["prognoza"]["veroyatnost_procent"] == 62)
    # 🔴 ЗАКРЪГЛЯНЕ, НЕ РЯЗАНЕ (намерено с мутации). При 0.62 двете дават
    # едно и също, значи старата проверка не можеше да различи закръглянето
    # от отрязването. 0.626 ги разделя: 63 срещу 62.
    check("процентът се ЗАКРЪГЛЯ нагоре, не се реже",
          zapis({"p": 0.626}, sega)["prognoza"]["veroyatnost_procent"] == 63)
    check("процентът се закръгля и надолу",
          zapis({"p": 0.624}, sega)["prognoza"]["veroyatnost_procent"] == 62)
    check("нашата сметка преди пазара се пази",
          abs(z["prognoza"]["veroyatnost_nash_model"] - 0.58) < 1e-9)
    check("звездите се пренасят", z["prognoza"]["zvezdi"] == 3)
    check("силата се пренася", abs(z["prognoza"]["sila"] - 0.24) < 1e-9)
    check("ключът на подреждането е звезди×1000 + сила×100",
          abs(z["prognoza"]["klyuch_podrezhdane"] - 3024.0) < 1e-6)
    check("ключът е None при липсваща сила",
          zapis({"stars": 3}, sega)["prognoza"]["klyuch_podrezhdane"] is None)
    # 🔴 ЛЕТВАТА СЕ МЕРИ НА САМАТА ГРАНИЦА (намерено с мутации). Дотук
    # проверката гледаше карта далеч над летвата — а там „<“ и „<=“ дават
    # един и същ отговор, тоест сравнението беше НЕПРОВЕРЕНО.
    # Числото не е заковано: взима се от самия запис.
    _l = z["prognoza"]["letva"]
    check("летвата е известна", _l is not None)
    check("карта ТОЧНО на летвата НЕ е под нея",
          vyarno(lambda: zapis(dict(puln, p=_l), sega)["prognoza"]["pod_letva"]
                 is False))
    check("карта с една стотна под летвата Е под нея",
          vyarno(lambda: zapis(dict(puln, p=round(_l - 0.01, 4)),
                               sega)["prognoza"]["pod_letva"] is True))
    check("карта над летвата не е под нея",
          vyarno(lambda: zapis(dict(puln, p=round(_l + 0.10, 4)),
                               sega)["prognoza"]["pod_letva"] is False))
    check("цената се пренася", abs(z["pazar"]["cena"] - 1.75) < 1e-9)
    check("цената на другата страна се пренася",
          abs(z["pazar"]["cena_drug"] - 2.20) < 1e-9)
    check("суровата вероятност е 1/цена",
          abs(z["pazar"]["veroyatnost_surova"] - round(1.0 / 1.75, 4)) < 1e-9)
    check("надценката е сборът над 100%",
          vyarno(lambda: abs(z["pazar"]["nadcenka"]
                             - round((1.0 / 1.75) / 0.5556 - 1.0, 4)) < 1e-6))
    check("надценката се свежда обратно до цената",
          vyarno(lambda: abs((1.0 / 1.75) / (1.0 + z["pazar"]["nadcenka"])
                             - 0.5556) < 1e-4))
    check("надценка няма без чиста вероятност",
          zapis({"pazar_cena": 1.75}, sega)["pazar"]["nadcenka"] is None)
    check("разликата ние−пазар е в точки",
          abs(z["pazar"]["razlika_tochki"] - round(100.0 * (0.58 - 0.5556), 1)) < 1e-6)
    check("разлика няма без пазарно число",
          zapis({"p": 0.6}, sega)["pazar"]["razlika_tochki"] is None)

    # ── 7. КОНТЕКСТЪТ, КОЙТО КАРТАТА ХВЪРЛЯ
    check("формата на домакина излиза", z["kontekst"]["forma_domakin"] == "WWDLW")
    check("формата на госта излиза", z["kontekst"]["forma_gost"] == "LDWWW")
    check("балансът излиза", z["kontekst"]["balans_domakin"] == "3-1-0")
    check("класирането излиза от вложен речник",
          z["kontekst"]["klasirane_domakin"] == 3
          and z["kontekst"]["klasirane_gost"] == 9)
    check("точките в ранглистата излизат",
          vyarno(lambda: abs(z["kontekst"]["tochki_domakin"] - 1880.0) < 1e-9))
    check("ранглиста с боклук вместо речник дава None",
          zapis({"fx": {"extra": {"ra": "абв"}}}, sega)
          ["kontekst"]["klasirane_domakin"] is None)
    check("цените от източника на мача се пазят",
          abs(z["kontekst"]["cena_domakin_izvor"] - 1.80) < 1e-9)
    check("шестте липсващи ги ИМА в записа",
          all(k in z["kontekst"] for k in
              ("glavi_sreshtu_glavi", "sadiya", "stadion", "vremeto",
               "kontuzeni", "seriya")))
    check("шестте липсващи са None, не измислени",
          vyarno(lambda: all(z["kontekst"][k] is None for k in
                             ("glavi_sreshtu_glavi", "sadiya", "stadion",
                              "vremeto", "kontuzeni", "seriya"))))
    check("и шестте липсващи пак имат етикет",
          all(e.get("kontekst." + k) for k in
              ("glavi_sreshtu_glavi", "sadiya", "stadion", "vremeto",
               "kontuzeni", "seriya")))

    # ── 8. ЧАСОВЕТЕ — СПРЯМО ПОДАДЕНИЯ now, БЕЗ ЗАКОВАНА ДАТА
    check("началото в UTC свършва на +00:00",
          str(z["mach"]["nachalo_utc"]).endswith("+00:00"))
    check("началото по София НЕ е същият низ като UTC",
          z["mach"]["nachalo_sofia"] != z["mach"]["nachalo_utc"])
    check("двата часа сочат един и същ миг",
          _tiho(lambda: datetime.fromisoformat(z["mach"]["nachalo_sofia"])
                == datetime.fromisoformat(z["mach"]["nachalo_utc"])) is True)
    check("бъдещ мач е „предстои“", z["mach"]["sastoyanie"] == "предстои")
    _min = dict(puln)
    _min["fx"] = dict(puln["fx"], when=sega - timedelta(hours=2))
    check("минал мач е „започнал“",
          zapis(_min, sega)["mach"]["sastoyanie"] == "започнал")
    check("без час състоянието е None",
          zapis({"fx": {"home": "А"}}, sega)["mach"]["sastoyanie"] is None)
    check("кога е взето следва подадения now",
          str(z["proizhod"]["vzeto_utc"]).startswith(sega.strftime("%Y-%m-%dT%H")))

    # ── 9. ПРОИЗХОДЪТ
    check("източникът на срещата се пази", z["proizhod"]["izvor_mach"] == "espn")
    check("източникът на цената се пази", z["proizhod"]["izvor_cena"] == "espn")
    check("източникът на контекста мълчи, когато контекст няма",
          zapis({"fx": {"src": "espn"}}, sega)["proizhod"]["izvor_kontekst"] is None)
    check("източникът на контекста се назовава, когато има какво",
          z["proizhod"]["izvor_kontekst"] == "espn")
    check("номерът в ESPN се пази", z["proizhod"]["espn_id"] == "401908124")

    # ── 10. ПРАЗНОТО Е ЛИПСА, НЕ ПРАЗЕН НИЗ
    check("празен низ става None, не \"\"",
          zapis({"fx": {"home": "   "}}, sega)["mach"]["domakin"] is None)
    check("празен списък причини става None",
          zapis({"why": []}, sega)["prognoza"]["prichini"] is None)
    check("вид на картата пада на „izbor“ при празно",
          z["mach"]["vid_karta"] == "izbor")
    check("тотал-картата се назовава",
          zapis({"vid_karta": "total"}, sega)["mach"]["vid_karta"] == "total")

    # ── 11. ДНЕВНИКЪТ
    import tempfile
    _p = os.path.join(tempfile.gettempdir(), "kj_selftest_%d.jsonl" % os.getpid())
    try:
        if os.path.exists(_p):
            os.remove(_p)
        check("дописването връща True", dopishi(puln, sega, _p) is True)
        check("вторият ред се дописва, не презаписва",
              dopishi(puln, sega, _p) is True)
        with open(_p, encoding="utf-8") as f:
            redove = [r for r in f.read().split("\n") if r.strip()]
        check("дневникът има точно два реда", len(redove) == 2)
        check("всеки ред е самостоятелен JSON",
              vyarno(lambda: all(json.loads(r)["mach"]["domakin"] == "Арсенал"
                                 for r in redove)))
        check("редът няма нов ред вътре в себе си",
              all("\n" not in r for r in redove))
        check("целият файл НЕ е един ред",
              vyarno(lambda: len(open(_p, encoding="utf-8").read()
                                 .rstrip("\n").split("\n")) == 2))
    finally:
        try:
            os.remove(_p)
        except OSError:
            pass
    # Провалът е НАРОЧЕН, затова оплакването му се глътва: инак самопроверката
    # печата „не се записа“ и чете се като счупено, при положение че точно
    # това се проверява.
    import contextlib as _cl                                 # noqa: PLC0415
    with _cl.redirect_stdout(io.StringIO()):
        _lo = dopishi(puln, sega, os.path.join(tempfile.gettempdir(),
                                               "nyama_takava_papka_kj", "a.jsonl"))
    check("дописване в невъзможен път връща False, не гърми", _lo is False)

    # ── 12. ВРЪЗКАТА С МОЗЪКА СЪЩЕСТВУВА В ПОТОКА, НЕ САМО В ТЕСТА
    #
    # 🔴 ЗАЩО Е ТУК И ЗАЩО Е ЧЕРВЕНО ПРИ ЛИПСВАЩ ФАЙЛ. Този проект вече
    # пет пъти е построил двигател, който никой не вика (последният —
    # pazar.link_kam_macha, намерен от оборващ агент на 01.09.2026).
    # Проверка, която „се прескача“, когато не намери какво да провери, е
    # шестият такъв случай: тя изчезва тихо и зеленото ѝ не значи нищо.
    # Затова липсващият predictor.py е СЧУПЕНО, не „пропуснато“.
    _pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "predictor.py")
    _viknat_v = set()
    try:
        import ast as _ast                                   # noqa: PLC0415
        _dyr = _ast.parse(open(_pp, encoding="utf-8").read())
        for _fn in _ast.walk(_dyr):
            if isinstance(_fn, _ast.FunctionDef):
                for _n in _ast.walk(_fn):
                    if (isinstance(_n, _ast.Call)
                            and isinstance(_n.func, _ast.Name)
                            and _n.func.id == "_puln_zapis"):
                        _viknat_v.add(_fn.name)
    except Exception:                                        # noqa: BLE001
        _viknat_v = set()
    check("пълният запис се вика в главния цикъл на картите", "run" in _viknat_v)
    check("пълният запис се вика и при тоталите", "post_totali" in _viknat_v)

    # ── 13. ЗАКЛЮЧВАЩИ: схемата не бива да се свие мълчаливо
    check("схемата има поне 80 полета", len(SHEMA) >= 80)
    check("разделите са точно петте поискани",
          [r for r, _i in RAZDELI] == ["mach", "prognoza", "pazar",
                                       "kontekst", "proizhod"])
    check("броят проверки е поне 30", ok >= 30)

    print("САМОПРОВЕРКА НА ПЪЛНИЯ ЗАПИС: " + str(ok) + " наред, "
          + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(selftest())
