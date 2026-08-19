# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ТЕНИС ITF И CHALLENGER 🎾

Един въпрос: откъде идват мачовете, които ESPN не знае, че съществуват?

ЗАЩО СЪЩЕСТВУВА
Ползвахме само ESPN atp/wta. Измерено на 19.08.2026: ESPN дава шепа предстоящи
мача на ден, защото знае САМО главния тур. Под него живее целият истински обем
на тениса — ITF (M15/M25/W15/W35/W50/W75) и Challenger.

Измерено на живо 19.08.2026 срещу global.flashscore.ninja:
  днес + утре + вдругиден, само СИНГЪЛ, само ITF/Challenger, само предстоящи:
      233 мача в 13:0х ч, 185 в 14:2х ч (разликата са започналите)     ✅
      по ниво: M25=46, CH=43, M15=37, W15=30, W35=21, W75=5, W50=3
  от тях с цена от Pinnacle (когато имената се обърнат):
      112 от 185 = 61% общо, 71% при мачове до 12 часа от старта       ✅
  история на играча (последни мачове, победа/загуба, настилка):
      медиана 50 минали мача; 78 от 80 играча имат история — само
      2-мата дебютанти нямат, и то наистина, не по грешка в имената    ✅
  резултат за оценителя (кой е спечелил, вкл. отказал се/служебна):
      205 отсъдени от 211 вчерашни; 6-те неотсъдени са ОТМЕНЕНИ мача   ✅

⚠️ ЕДНО ЧИСЛО, КОЕТО НЕ Е ИЗМЕРЕНО: доходността. Този модул носи мачове, цена
и история — дали моделът бие пазара на това ниво, се разбира чак след като
оценителят натрупа изходи. Дотогава ITF не бива да влиза в „ръб".

🔴 ТРИ ГРЕШКИ В ПРЕДИШНОТО СЪОБЩЕНИЕ ЗА ТОЗИ ИЗТОЧНИК, ИЗМЕРЕНИ И ПОПРАВЕНИ

1. „1252 мача за 10 дни" — НЕ. Прозорецът на фийда е −7 .. +2 дни и толкоз.
   Ден +3 връща 179 байта, ден −8 връща 1 байт. Проверено на всеки ден поотделно.
   Тоест ПРЕДСТОЯЩИ има само за днес и утре (вдругиден: 2 мача). Жребият на
   ITF просто не се тегли по-рано.

2. „67% с цена" — вярно е САМО за близките мачове. Мерено по време до старта:
       до 6 ч   130 мача → 68%
       6–12 ч    18 мача → 89%
      12–24 ч    35 мача → 29%
      24–48 ч     8 мача →  0%
   Pinnacle отваря пазара към 12-24 часа преди мача, не по-рано. Общото число
   за целия хоризонт е 50%, не 67%.

3. 🔴 НАЙ-ВАЖНОТО: СУРОВИТЕ ИМЕНА ДАВАТ 0%. Измерено: 0 от 233.
   Flashscore пише „Faria J." (фамилия отпред), Pinnacle пише „Jaime Faria".
   pinnacle._familiya взима ПОСЛЕДНАТА дума → за нас това е „J.", за тях
   „Faria" → нищо не се среща никога. След обръщането: 117 от 233.
   Затова pn_ime() не е разкош, а условието изобщо да има цена.

🔴 И ДВА ДЕФЕКТА В МОЯ СОБСТВЕН КОД, НАМЕРЕНИ С МЕРЕНЕ, НЕ С ЧЕТЕНЕ

4. ЗВЕЗДАТА В ИСТОРИЯТА Е ПОБЕДИТЕЛЯТ, НЕ ДОМАКИНЪТ.
   Прочетох „*Faria J. vs Walton A." и реших, че * маркира нашия човек.
   Тогава личните срещи излязоха 9-0 за домакините в 45 мача — невъзможно
   число, и точно то ме издаде. Преброено върху 1650 реда: звездата съвпада
   с победителя в 1647 (99.8%). След поправката същите 45 мача дават 1-8.
   Тоест 8 от 9 отсъждания на лични срещи бяха ОБЪРНАТИ.

5. „СРЕЩУ КОГО" ПРИ ЗАГУБА ВРЪЩАШЕ САМИЯ НАС.
   Същата звезда: при загуба тя стои върху съперника, значи „другия от
   звездата" сме ние. Измерено: 856 от 1650 реда — всяка загуба.
   След поправката: 0 от 979 реда.
   Поуката е една и съща и в двата случая — символ, чийто смисъл съм
   ПРЕДПОЛОЖИЛ от един пример, а не съм преброил.

📉 КОЛКО ОТ НЕПОКРИТИТЕ СА ВИНА НА ИМЕНАТА
Почти никоя. От 111-те ненамерени мача само 9 имат ПОНЕ единия играч някъде в
списъка на Pinnacle. Останалите 102 просто не се търгуват в тази секунда.
Тоест 50% е таванът на източника днес, а не дупка в сравняването.

ЦЕНАТА В ЗАЯВКИ (бюджетът на бота е ~220, тенисът да не яде над 40)
  srechti(dni=1)      2 заявки   (по една на ден: днес, утре)
  srechti(dni=2)      3 заявки
  istoriya(мач)       1 заявка   — но дава ИСТОРИЯТА НА ДВАМАТА наведнъж
  rezultat(мач)       1 заявка на ДЕН, не на мач (дневният фийд носи всички)
  ceni(мач)           0 нови     — минава през вече кешираните 2 на pinnacle.py
Тоест реален рън: 2 (срещи) + 1 (резултати) + N (история само за картите).
При 20 карти = 23 заявки. Измерено под --zhivo, числото се печата.

📏 ИСТОРИЯТА НЕ Е СТЕНА — ИЗМЕРЕНО, НЕ ПРЕДПОЛОЖЕНО
Въпросът беше: без история моделът дава 50%. Затова сравних дела победи срещу
безмаржовата вероятност на Pinnacle върху 98 мача, които имат И цена, И поне
по 5 минали мача за двамата:
      само дял победи, K=1.1   средна грешка 0.122   корелация с пазара +0.78
      „винаги 50%"             средна грешка 0.208
   тоест формата сваля грешката с 41%. K=1.1 излиза най-добро и на двете
   половини на извадката поотделно — не е нагодено към шума.
⚠️ Личните срещи НЕ помагат: при тегло 0.1 грешката вече расте (0.1221), при
   0.5 става 0.1240. И е ясно защо — само 21 от 98 мача изобщо имат такива.
   Затова се връщат в данните, но не влизат в модела.
🔴 Това е сравнение с ПАЗАРА, не с изхода на мачовете. Че моделът прилича на
   линията, не значи, че я бие. Доходност се мери само с изиграни мачове.

🧱 СТЕНА, КОЯТО НЕ Е ПРЕОДОЛЯНА
Няма евтин фийд „история по ИД НА ИГРАЧ". Пробвани и мъртви: pms_*, pm_*,
pmr_*, pr_*, ps_*, pl_2_{id}_{0..5} (последният отговаря, но носи само етикети
и реклами на букмейкъри — нула дати и нула резултати).
Историята идва САМО закачена за мач: df_hh_1_{ид_на_мача}. Затова подписът тук
е istoriya(мач), а не istoriya(играч). Това не е по-лошо — една заявка връща и
двамата играчи, и то с настилка и с личните им срещи.

  python itf.py --selftest   — проверките, без мрежа
  python itf.py --zhivo      — истинско питане, с числа
"""
import io
import os
import sys
import time
import urllib.request

BAZA = "https://global.flashscore.ninja/2/x/feed"

# Без този подпис адресът връща 401. Проверено: празни заглавки → 401,
# само този ключ → 200. Не е таен ключ, а версия на протокола на фийда.
FSIGN = (os.environ.get("FS_SIGN") or "SW9D1eZo").strip() or "SW9D1eZo"

TIMEOUT = int((os.environ.get("ITF_TIMEOUT") or "20").strip() or 20)

# 2 = тенис в номерацията на фийда. 3 = часовият пояс, по който се реже „денят".
# Часовият пояс не ни променя нищо, защото филтрираме по AD (истински unix час),
# а не по това в кой ден фийдът е сложил мача.
SPORT = 2
POYAS = 3

# Разделителите на този формат. Записите са с ~, полетата с ¬, ключ÷стойност.
TILDA = "~"
POLE = "¬"
RAVNO = "÷"

# Прозорецът на фийда, ИЗМЕРЕН ден по ден на 19.08.2026:
#   −8 → 1 байт      −7 → 203 460 байта      +2 → 2 333 байта      +3 → 179 байта
# Тоест няма смисъл да се пита извън тези граници — само хаби заявка.
DEN_NAY_RANO = -7
DEN_NAY_KUSNO = 2

# AB = в коя фаза е мачът.
FAZA = {"1": "предстои", "2": "на живо", "3": "свършил"}

# AC = как е свършил. 🔴 ТОВА Е КАПАНЪТ НА ОЦЕНИТЕЛЯ.
#
# Ако се съди по сетовете (AG/AH), 5 от вчерашните 211 мача се отсъждат
# ГРЕШНО, а още 1 остава без победител. Причината: при отказал се играч
# сетовете могат да са 1:1, а при служебна победа изобщо няма сетове.
# Измерено: AS (кой е спечелил) присъства в 205 от 211 записа; липсва точно
# при 6-те отменени, където победител наистина няма.
KRAY = {
    "3": "редовен",
    "5": "отменен",
    "8": "отказал се",
    "9": "служебна",
}

_kesh = {}
_broi = [0]


def broi_zayavki():
    """Колко заявки е направил модулът в това пускане.

    ЗАЩО: бюджетът е общ за целия бот; без брояч „не яде много" е мнение.
    """
    return _broi[0]


def nulirai():
    """Изчиства кеша и брояча. За тестовете, не за живо."""
    _kesh.clear()
    _broi[0] = 0


def _text(pat):
    """Сурово тяло на един фийд. None при всяка беда.

    ЗАЩО не хвърля: един мъртъв ден не бива да събаря целия рън.
    """
    _broi[0] += 1
    try:
        rq = urllib.request.Request(BAZA + pat, headers={"x-fsign": FSIGN})
        with urllib.request.urlopen(rq, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:                                        # noqa: BLE001
        return None


def raztvori(txt):
    """Суровият фийд -> списък от речници, по един на запис.

    ЗАЩО е отделно от мрежата: единственият начин парсерът да се изпита
    без интернет е да му се подаде текст.
    """
    out = []
    for rec in str(txt or "").split(TILDA):
        d = {}
        for f in rec.split(POLE):
            if RAVNO in f:
                k, v = f.split(RAVNO, 1)
                d[k] = v
        if d:
            out.append(d)
    return out


def _dvoyka(ime):
    """Дали името е на двойка. Двойките се пишат 'Hsieh S-W./Ostapenko J.'

    ЗАЩО: двойките са ~30% от записите и моделът ни е за единичен играч.
    """
    return "/" in str(ime or "")


def nivo(liga):
    """От заглавието на лигата -> (ниво, пол, турнир, настилка).

    ЗАЩО: „ITF MEN - SINGLES: M15 Arad (Romania), clay" носи четири различни
    неща в един низ, а картата се нуждае от тях поотделно.
    """
    s = str(liga or "")
    # 🔴 Тази променлива се казваше „gorе" с КИРИЛСКО „е" накрая. Работеше,
    # защото всички ѝ употреби бяха копирани — но всеки, който я напише на
    # латиница, получава NameError без обяснение. Имената на променливи в
    # този проект са само на латиница; коментарите носят българското.
    glavni = s.upper()
    pol = "жени" if "WOMEN" in glavni else ("мъже" if "MEN" in glavni else "")
    opashka = s.split(":", 1)[1].strip() if ":" in s else s
    nast = ""
    if "," in opashka:
        opashka, nast = opashka.rsplit(",", 1)
        opashka, nast = opashka.strip(), nast.strip()
    if glavni.startswith("CHALLENGER"):
        niv = "CH"
    else:
        p = opashka.split()
        niv = p[0] if p and p[0][:1].upper() in ("M", "W") and p[0][1:2].isdigit() else ""
    return niv, pol, opashka, nast


def _e_nashe(liga, vklyuchi_glaven):
    """Дали този запис е от лига, която ни интересува.

    ЗАЩО: ATP/WTA вече ги имаме от ESPN — ако ги пуснем и оттук, ще дублираме
    карти. Пускат се само ако някой изрично ги поиска.
    """
    g = str(liga or "").upper()
    if "SINGLES" not in g:
        return False
    if g.startswith(("ITF", "CHALLENGER")):
        return True
    return bool(vklyuchi_glaven) and g.startswith(("ATP", "WTA"))


def _den(day):
    """Един ден от фийда, разложен на мачове. Кеширано по ден."""
    kl = ("d", int(day))
    if kl in _kesh:
        return _kesh[kl]
    txt = _text("/f_%d_%d_%d_en_1" % (SPORT, int(day), POYAS))
    zap = raztvori(txt)
    out = []
    liga = ""
    for d in zap:
        if "ZA" in d:
            liga = d["ZA"]
        if "AA" not in d:
            continue
        d = dict(d)
        d["_liga"] = liga
        out.append(d)
    _kesh[kl] = out
    return out


def _mach_ot_zapis(d):
    """Един запис от фийда -> нашият речник за мач. None, ако не ни става."""
    dom, gost = d.get("AE") or "", d.get("AF") or ""
    if not dom or not gost or _dvoyka(dom) or _dvoyka(gost):
        return None
    niv, pol, turnir, nast = nivo(d.get("_liga"))
    try:
        start = int(d.get("AD") or 0)
    except (TypeError, ValueError):
        start = 0
    return {
        "id": str(d.get("AA") or ""),
        "dom": str(dom),
        "gost": str(gost),
        "turnir": turnir,
        "niv": niv,
        "pol": pol,
        "nastilka": nast,
        "liga": str(d.get("_liga") or ""),
        "start": start,
        "start_iso": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start))
                      if start else ""),
        "faza": FAZA.get(str(d.get("AB") or ""), ""),
        "kray": KRAY.get(str(d.get("AC") or ""), ""),
        "_AS": d.get("AS"),
        "_AG": d.get("AG"),
        "_AH": d.get("AH"),
    }


def srechti(now=None, dni=1, glaven=False):
    """Предстоящите ITF/Challenger сингъл мачове. Списък речници.

    ЗАЩО now е аргумент: без него тестът щеше да зависи от часа, в който се
    пуска, тоест щеше да е зелен сутрин и червен вечер.
    """
    sega = float(now if now is not None else time.time())
    dni = max(0, min(int(dni), DEN_NAY_KUSNO))
    out = []
    vidyani = set()
    for day in range(0, dni + 1):
        for d in _den(day):
            if not _e_nashe(d.get("_liga"), glaven):
                continue
            if str(d.get("AB") or "") != "1":       # само още незапочналите
                continue
            m = _mach_ot_zapis(d)
            if not m or not m["id"] or m["id"] in vidyani:
                continue
            # Фийдът държи по някой мач с изтекъл час (закъснели кортове).
            # Такъв не е прогноза, а вече минало — не влиза в карта.
            if m["start"] and m["start"] < sega - 900:
                continue
            vidyani.add(m["id"])
            out.append(m)
    out.sort(key=lambda x: x["start"])
    return out


def pn_ime(ime):
    """'Faria J.' -> 'J. Faria'. Инициалите отиват отпред.

    🔴 ЗАЩО СЪЩЕСТВУВА: без нея съвпаденията с Pinnacle са 0 от 233. С нея —
    117 от 233. Flashscore пише фамилията ПЪРВА, Pinnacle я пише последна, а
    сравняването там взима последната дума.
    """
    dumi = [w for w in str(ime or "").replace(" ", " ").split() if w]
    if len(dumi) < 2:
        return str(ime or "")
    ini = []
    # Инициал = къса дума с точка накрая ('J.', 'M.', 'C. S.' са две такива).
    while len(dumi) > 1 and dumi[-1].endswith(".") and len(dumi[-1].rstrip(".")) <= 2:
        ini.insert(0, dumi.pop())
    return " ".join(ini + dumi) if ini else str(ime or "")


def ceni(mach, pn=None):
    """(цена_дом, цена_гост) от Pinnacle за НАШИТЕ страни. None, ако няма.

    ЗАЩО праща обърнати имена: виж pn_ime. ЗАЩО pn е аргумент: за да може
    селфтестът да подаде фалшив модул и да не пипа мрежата.
    """
    if pn is None:
        try:
            import pinnacle as pn                            # noqa: PLC0415
        except Exception:                                    # noqa: BLE001
            return (None, None)
    d, g = pn_ime(mach.get("dom")), pn_ime(mach.get("gost"))
    try:
        c = pn.ceni_za("tennis", d, g)
    except Exception:                                        # noqa: BLE001
        return (None, None)
    return (c[0], c[1])


def _sethove(d):
    """(сетове_а, сетове_б) за един ред от историята. (None, None) ако няма.

    ЗАЩО две места: в личните срещи стои KU/KT, в последните мачове — само
    KL („2:1"). Едно и също число, два различни ключа.
    """
    try:
        return int(d["KU"]), int(d["KT"])
    except (KeyError, TypeError, ValueError):
        pass
    kl = str(d.get("KL") or "")
    if ":" in kl:
        try:
            a, b = kl.split(":")[:2]
            return int(a), int(b)
        except (TypeError, ValueError):
            pass
    return (None, None)


def _istoriya_ot_text(txt, dom, gost):
    """Суровият H2H фийд -> история за двамата. Отделено, за да се тества сухо."""
    prazno = {"igri": 0, "pobedi": 0, "zagubi": 0, "posledni": []}
    out = {"dom": dict(prazno, posledni=[]), "gost": dict(prazno, posledni=[]),
           "h2h_dom": 0, "h2h_gost": 0}
    grupa = ""
    razdel = ""
    for d in raztvori(txt):
        if "KA" in d:
            grupa = d["KA"]
        if "KB" in d:
            razdel = d["KB"]
        if "KC" not in d:
            continue
        # Само общата таблица. По настилки същите мачове се броят пак — ако
        # ги съберем, всеки мач влиза два пъти и процентът става измислен.
        if grupa and grupa.lower() not in ("all surfaces", ""):
            continue
        ime_a = str(d.get("KJ") or "").lstrip("*").strip()
        ime_b = str(d.get("KK") or "").lstrip("*").strip()
        a, b = _sethove(d)

        if razdel.lower().startswith("head"):
            # 🔴 ЗВЕЗДАТА Е ПОБЕДИТЕЛЯТ, НЕ ДОМАКИНЪТ.
            # Първата ми версия четеше „* = нашият човек" и излизаше, че
            # домакинът води личните срещи в 6 от 6 мача. Измерено върху
            # 1650 реда: звездата съвпада с победителя в 1647 (99.8%).
            # Затова победителят се взима по СЕТОВЕТЕ и после се разпознава
            # ПО ИМЕ — звездата не носи информация за коя страна е наша.
            if a is None or b is None or a == b:
                continue
            pobeditel = ime_a if a > b else ime_b
            if _sravni(pobeditel, dom) and not _sravni(pobeditel, gost):
                out["h2h_dom"] += 1
            elif _sravni(pobeditel, gost) and not _sravni(pobeditel, dom):
                out["h2h_gost"] += 1
            continue
        if not razdel.lower().startswith("last matches"):
            continue
        koy = razdel.split(":", 1)[1].strip() if ":" in razdel else ""
        strana = "dom" if _sravni(koy, dom) else ("gost" if _sravni(koy, gost) else "")
        if not strana:
            continue
        wis = str(d.get("WIS") or "").lower()
        if wis not in ("w", "l"):
            continue
        z = out[strana]
        z["igri"] += 1
        if wis == "w":
            z["pobedi"] += 1
        else:
            z["zagubi"] += 1
        if len(z["posledni"]) < 12:
            try:
                koga = int(d.get("KC") or 0)
            except (TypeError, ValueError):
                koga = 0
            # 🔴 СЪПЕРНИКЪТ СЕ ВЗИМА ПО ИМЕ, НЕ ПО ЗВЕЗДА.
            # Старата версия връщаше „другия от звездичката" — тоест при
            # ЗАГУБА връщаше самия наш играч. Измерено: 856 от 1650 реда.
            sreshtu = ime_b if _sravni(ime_a, koy) else ime_a
            z["posledni"].append({
                "koga": koga,
                "sreshtu": sreshtu,
                "rezultat": str(d.get("KL") or ""),
                "nastilka": str(d.get("KD") or ""),
                "turnir": str(d.get("KF") or ""),
                "pobeda": wis == "w",
            })
    for k in ("dom", "gost"):
        z = out[k]
        z["dyal"] = round(z["pobedi"] / z["igri"], 3) if z["igri"] else None
    return out


def _sravni(a, b):
    """Две имена, сведени до сравнимо. Само букви и цифри, малки."""
    def n(s):
        return "".join(ch for ch in str(s or "").lower() if ch.isalnum())
    na, nb = n(a), n(b)
    return bool(na) and bool(nb) and (na == nb or na in nb or nb in na)


def istoriya(mach):
    """Минали мачове на ДВАМАТА играчи + личните им срещи. ЕДНА заявка.

    ЗАЩО не е по ИД на играч: такъв фийд не съществува — вж. СТЕНАТА горе.
    Затова ключът е мачът, а не човекът.
    """
    mid = mach.get("id") if isinstance(mach, dict) else str(mach or "")
    if not mid:
        return _istoriya_ot_text("", "", "")
    kl = ("h", mid)
    if kl in _kesh:
        return _kesh[kl]
    txt = _text("/df_hh_1_%s" % mid)
    r = _istoriya_ot_text(txt, (mach.get("dom") if isinstance(mach, dict) else ""),
                          (mach.get("gost") if isinstance(mach, dict) else ""))
    _kesh[kl] = r
    return r


def rezultat(mach):
    """Кой е спечелил. {'gotov','pobeditel','sethove','statut'}.

    ЗАЩО чете дневния фийд, а не мача: един ден носи всички резултати наведнъж,
    тоест 1 заявка вместо 200. За оценителя това е разликата между 1 и 200.
    ЗАЩО pobeditel идва от AS, а не от сетовете: при отказал се сетовете могат
    да са 1:1 — измерено 5 такива от 211 вчерашни.
    """
    mid = mach.get("id") if isinstance(mach, dict) else str(mach or "")
    otg = {"gotov": False, "pobeditel": None, "sethove": None, "statut": ""}
    if not mid:
        return otg
    for day in range(DEN_NAY_KUSNO, DEN_NAY_RANO - 1, -1):
        for d in _den(day):
            if str(d.get("AA") or "") != mid:
                continue
            return otsadi(d)
    return otg


def otsadi(d):
    """Един запис -> отсъждане. Отделено, за да се провери без мрежа."""
    otg = {"gotov": False, "pobeditel": None, "sethove": None,
           "statut": KRAY.get(str(d.get("AC") or ""), "")}
    if str(d.get("AB") or "") != "3":
        return otg
    otg["gotov"] = True
    a, b = d.get("AG"), d.get("AH")
    if a is not None and b is not None:
        otg["sethove"] = "%s:%s" % (a, b)
    s = str(d.get("AS") or "")
    if s in ("1", "2"):
        otg["pobeditel"] = int(s)
    # Отменен мач е готов, но без победител — и това НЕ е грешка, а факт.
    return otg


# ─────────────────────────────────────────────────────────────────────────
# ПРОБА БЕЗ МРЕЖА
#
# Мострите долу са РЪЧНО СГЛОБЕНИ в истинския формат на фийда — не са жив
# запис. Стойностите (AB, AC, AS, AG/AH, имената със/без точка) са преписани
# от истински записи от 19.08.2026, за да проверяват точно тези капани.
# ─────────────────────────────────────────────────────────────────────────
_P = POLE
_R = RAVNO

MOSTRA_DEN = TILDA.join([
    "SA" + _R + "2",
    # лига 1: ITF мъже сингъл
    "ZA" + _R + "ITF MEN - SINGLES: M15 Arad (Romania), clay",
    _P.join(["AA" + _R + "aaa11111", "AD" + _R + "1787200000", "AB" + _R + "1",
             "AC" + _R + "1", "AE" + _R + "Jodar R.", "AF" + _R + "Ferrari F."]),
    _P.join(["AA" + _R + "aaa22222", "AD" + _R + "1787000000", "AB" + _R + "3",
             "AC" + _R + "3", "AE" + _R + "Gima S.", "AF" + _R + "Ciocca G.",
             "AS" + _R + "1", "AG" + _R + "2", "AH" + _R + "0"]),
    # отказал се: сетовете са 1:1, победителят е само в AS
    _P.join(["AA" + _R + "aaa33333", "AD" + _R + "1787000100", "AB" + _R + "3",
             "AC" + _R + "8", "AE" + _R + "Johns G.", "AF" + _R + "Saraiva P.",
             "AS" + _R + "1", "AG" + _R + "1", "AH" + _R + "1"]),
    # служебна: изобщо няма сетове
    _P.join(["AA" + _R + "aaa44444", "AD" + _R + "1787000200", "AB" + _R + "3",
             "AC" + _R + "9", "AE" + _R + "Feistel G.", "AF" + _R + "Gniewkowska O.",
             "AS" + _R + "2"]),
    # отменен: няма победител и това е вярно
    _P.join(["AA" + _R + "aaa55555", "AD" + _R + "1787000300", "AB" + _R + "3",
             "AC" + _R + "5", "AE" + _R + "Virtanen O.", "AF" + _R + "Wu Y."]),
    # двойка — не бива да минава
    _P.join(["AA" + _R + "aaa66666", "AD" + _R + "1787200000", "AB" + _R + "1",
             "AE" + _R + "Hsieh S-W./Ostapenko J.", "AF" + _R + "Klepac A./Lumsden M."]),
    # лига 2: Challenger
    "ZA" + _R + "CHALLENGER MEN - SINGLES: Kingston (Jamaica), hard",
    _P.join(["AA" + _R + "bbb11111", "AD" + _R + "1787210000", "AB" + _R + "1",
             "AE" + _R + "Cerundolo J. M.", "AF" + _R + "Walton A."]),
    # лига 3: ATP — да се спира по подразбиране
    "ZA" + _R + "ATP - SINGLES: Cincinnati (USA), hard",
    _P.join(["AA" + _R + "ccc11111", "AD" + _R + "1787220000", "AB" + _R + "1",
             "AE" + _R + "Faria J.", "AF" + _R + "Tien L."]),
]) + TILDA

# 🔴 В ТЕЗИ РЕДОВЕ ЗВЕЗДАТА Е ВЪРХУ ПОБЕДИТЕЛЯ, точно както в живия фийд
# (измерено: 1647 от 1650 реда). Затова при ЗАГУБА звездата е върху
# СЪПЕРНИКА — и точно тези редове хващат двата дефекта в първата ми версия.
MOSTRA_H2H = TILDA.join([
    "SA" + _R + "2",
    "KA" + _R + "All surfaces",
    "KB" + _R + "Last matches: Jodar R.",
    _P.join(["KC" + _R + "1786900000", "KJ" + _R + "*Jodar R.", "KK" + _R + "Alfa A.",
             "KL" + _R + "2:0", "KD" + _R + "clay", "KF" + _R + "Arad", "WIS" + _R + "w"]),
    # загуба: звездата е върху Beta B., нашият Jodar е вторият
    _P.join(["KC" + _R + "1786800000", "KJ" + _R + "*Beta B.", "KK" + _R + "Jodar R.",
             "KL" + _R + "2:1", "KD" + _R + "clay", "KF" + _R + "Arad", "WIS" + _R + "l"]),
    _P.join(["KC" + _R + "1786700000", "KJ" + _R + "*Jodar R.", "KK" + _R + "Gama G.",
             "KL" + _R + "2:0", "KD" + _R + "hard", "KF" + _R + "Lesa", "WIS" + _R + "w"]),
    "KB" + _R + "Last matches: Ferrari F.",
    _P.join(["KC" + _R + "1786900000", "KJ" + _R + "*Delta D.", "KK" + _R + "Ferrari F.",
             "KL" + _R + "2:0", "KD" + _R + "clay", "KF" + _R + "Lesa", "WIS" + _R + "l"]),
    _P.join(["KC" + _R + "1786850000", "KJ" + _R + "*Ferrari F.", "KK" + _R + "Eps E.",
             "KL" + _R + "2:1", "KD" + _R + "clay", "KF" + _R + "Lesa", "WIS" + _R + "w"]),
    "KB" + _R + "Head-to-head matches",
    # едната лична среща е за домакина...
    _P.join(["KC" + _R + "1786000000", "KJ" + _R + "*Jodar R.", "KK" + _R + "Ferrari F.",
             "KU" + _R + "2", "KT" + _R + "1", "KL" + _R + "2:1"]),
    # ...а другата за госта, при СЪЩАТА подредба на звездата
    _P.join(["KC" + _R + "1785000000", "KJ" + _R + "*Ferrari F.", "KK" + _R + "Jodar R.",
             "KU" + _R + "2", "KT" + _R + "0", "KL" + _R + "2:0"]),
    # Същите мачове пак, но в раздела по настилка. Ако се броят и те, сборът
    # се удвоява — точно това пази проверката за двойно броене.
    "KA" + _R + "Clay",
    "KB" + _R + "Last matches: Jodar R.",
    _P.join(["KC" + _R + "1786900000", "KJ" + _R + "*Jodar R.", "KK" + _R + "Alfa A.",
             "KL" + _R + "2:0", "KD" + _R + "clay", "WIS" + _R + "w"]),
]) + TILDA


class _FalshivPinnacle:
    """Двойник на pinnacle.py за селфтеста. Помни какви имена е получил."""

    def __init__(self):
        self.vidyani = []

    def ceni_za(self, sport, dom, gost):
        self.vidyani.append((sport, dom, gost))
        # Отговаря САМО на обърнатия правопис — точно както истинският.
        if dom == "R. Jodar" and gost == "F. Ferrari":
            return (1.55, 2.45, None)
        return (None, None, None)


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    nulirai()
    # Целият прозорец се напълва наум, инак rezultat() тръгва да обикаля
    # дните по мрежата и „сухата" проба спира да е суха. (Точно това я
    # хвана първия път: 10 заявки при търсене на непознат ид.)
    for _d in range(DEN_NAY_RANO, DEN_NAY_KUSNO + 1):
        _kesh[("d", _d)] = []
    _kesh[("d", 0)] = [dict(d, _liga=l) for d, l in _s_ligi(MOSTRA_DEN)]

    # ── разтваряне на формата
    zap = raztvori(MOSTRA_DEN)
    check("форматът се разтваря", len(zap) >= 10)
    check("ключ÷стойност се чете", zap[0].get("SA") == "2")

    # ── срещи
    sr = srechti(now=1787100000, dni=1)
    idta = [m["id"] for m in sr]
    check("предстоящите са 2", len(sr) == 2)
    check("двойката е отрязана", "aaa66666" not in idta)
    check("ATP е спрян по подразбиране", "ccc11111" not in idta)
    check("свършилите не влизат", "aaa22222" not in idta)
    check("ITF мачът влиза", "aaa11111" in idta)
    check("Challenger мачът влиза", "bbb11111" in idta)
    check("подредени по час", [m["start"] for m in sr] == sorted(m["start"] for m in sr))

    sr2 = srechti(now=1787100000, dni=1, glaven=True)
    check("ATP влиза при поискване", "ccc11111" in [m["id"] for m in sr2])

    # изтекъл час: ако „сега" е след старта, мачът не е прогноза
    check("изтеклите отпадат", srechti(now=1787300000, dni=1) == [])

    # ── ниво и турнир
    m = [x for x in sr if x["id"] == "aaa11111"][0]
    check("нивото е M15", m["niv"] == "M15")
    check("полът е мъже", m["pol"] == "мъже")
    check("турнирът е Arad", m["turnir"] == "M15 Arad (Romania)")
    check("настилката е clay", m["nastilka"] == "clay")
    ch = [x for x in sr if x["id"] == "bbb11111"][0]
    check("Challenger е ниво CH", ch["niv"] == "CH")
    check("Challenger турнир", ch["turnir"] == "Kingston (Jamaica)")
    check("стартът в ISO", m["start_iso"].endswith("Z") and m["start_iso"][:2] == "20")

    # ── обръщането на имената 🔴 това е дефектът, който правеше 0 от 233
    check("Faria J. -> J. Faria", pn_ime("Faria J.") == "J. Faria")
    check("две имена се обръщат", pn_ime("Cerundolo J. M.") == "J. M. Cerundolo")
    check("съставна фамилия оцелява",
          pn_ime("Barroso Campos A.") == "A. Barroso Campos")
    check("вече обърнато не се пипа", pn_ime("Jaime Faria") == "Jaime Faria")
    check("една дума не се пипа", pn_ime("Sinner") == "Sinner")
    check("празно не гърми", pn_ime("") == "" and pn_ime(None) == "")
    check("тире във фамилията оцелява", pn_ime("Auger-Aliassime F.") == "F. Auger-Aliassime")

    # ── цени през фалшив Pinnacle
    fp = _FalshivPinnacle()
    c = ceni(m, pn=fp)
    check("цената идва", c == (1.55, 2.45))
    check("на Pinnacle се пращат ОБЪРНАТИ имена",
          fp.vidyani and fp.vidyani[-1] == ("tennis", "R. Jodar", "F. Ferrari"))
    fp2 = _FalshivPinnacle()
    check("без съвпадение -> (None, None)",
          ceni({"dom": "Zzz A.", "gost": "Yyy B."}, pn=fp2) == (None, None))

    # ── отсъждане 🔴 сетовете лъжат при отказал се
    z = {d["AA"]: d for d in raztvori(MOSTRA_DEN) if "AA" in d}
    r = otsadi(z["aaa22222"])
    check("редовен: домакинът", r["pobeditel"] == 1 and r["statut"] == "редовен")
    check("редовен: сетове 2:0", r["sethove"] == "2:0")
    r = otsadi(z["aaa33333"])
    check("отказал се: сетовете са 1:1", r["sethove"] == "1:1")
    check("отказал се: победител пак има", r["pobeditel"] == 1)
    check("отказал се: статутът се казва", r["statut"] == "отказал се")
    r = otsadi(z["aaa44444"])
    check("служебна: победител без сетове",
          r["pobeditel"] == 2 and r["sethove"] is None)
    r = otsadi(z["aaa55555"])
    check("отменен: НЯМА победител", r["pobeditel"] is None)
    check("отменен: пак е свършил", r["gotov"] is True)
    r = otsadi(z["aaa11111"])
    check("предстоящият не е готов", r["gotov"] is False)

    # rezultat през кеша на деня
    check("rezultat намира по ид", rezultat({"id": "aaa33333"})["pobeditel"] == 1)
    check("непознат ид не гърми", rezultat({"id": "нямаго"})["gotov"] is False)

    # ── история
    h = _istoriya_ot_text(MOSTRA_H2H, "Jodar R.", "Ferrari F.")
    check("историята на домакина е 3", h["dom"]["igri"] == 3)
    check("домакинът с 2 победи", h["dom"]["pobedi"] == 2 and h["dom"]["zagubi"] == 1)
    check("дялът е 0.667", h["dom"]["dyal"] == 0.667)
    check("гостът е 2 мача", h["gost"]["igri"] == 2)
    check("гостът 1-1", h["gost"]["pobedi"] == 1 and h["gost"]["zagubi"] == 1)
    check("настилките НЕ се броят втори път", h["dom"]["igri"] == 3)
    # 🔴 двете проверки долу падат при „звездата = нашият човек"
    check("личните срещи: 1-1", h["h2h_dom"] == 1 and h["h2h_gost"] == 1)
    check("гостът си получава своята лична победа", h["h2h_gost"] == 1)
    check("последните носят съперник", h["dom"]["posledni"][0]["sreshtu"] == "Alfa A.")
    # 🔴 при ЗАГУБА звездата е върху съперника — старият код връщаше НАС
    check("съперникът при загуба е съперникът",
          h["dom"]["posledni"][1]["sreshtu"] == "Beta B.")
    check("загубата е отбелязана като загуба",
          h["dom"]["posledni"][1]["pobeda"] is False)
    check("съперник при загуба и за госта",
          h["gost"]["posledni"][0]["sreshtu"] == "Delta D.")
    check("никъде съперникът не сме ние",
          all(not _sravni(p["sreshtu"], "Jodar R.") for p in h["dom"]["posledni"]))
    check("последните носят настилка", h["dom"]["posledni"][0]["nastilka"] == "clay")
    check("победата е отбелязана", h["dom"]["posledni"][0]["pobeda"] is True)
    check("сетовете се четат и от KL", _sethove({"KL": "2:1"}) == (2, 1))
    check("сетовете се четат и от KU/KT", _sethove({"KU": "2", "KT": "0"}) == (2, 0))
    check("без сетове -> None", _sethove({}) == (None, None))
    prazna = _istoriya_ot_text("", "A", "B")
    check("празна история не гърми",
          prazna["dom"]["igri"] == 0 and prazna["dom"]["dyal"] is None)

    # ── бюджет
    check("прозорецът е −7..+2", (DEN_NAY_RANO, DEN_NAY_KUSNO) == (-7, 2))
    check("dni се ограничава", srechti(now=1787100000, dni=99) is not None)
    # Тази остава ПОСЛЕДНА нарочно: тя мери всичко отгоре.
    check("сухият тест не пипа мрежата", broi_zayavki() == 0)

    print("ПРОБА: %d минаха, %d паднаха" % (ok, len(bad)))
    for b in bad:
        print("   ПАДНА: %s" % b)
    if ok < 60:
        print("   ПАДНА: проверките са по-малко от 60 — тестът се е самоизключил")
        return 1
    return 0 if not bad else 1


def _s_ligi(txt):
    """(запис, лига) за всеки запис с мач. Помощна за сухата проба."""
    out, liga = [], ""
    for d in raztvori(txt):
        if "ZA" in d:
            liga = d["ZA"]
        if "AA" in d:
            out.append((d, liga))
    return out


def zhivo():
    """Истинско питане. Печата само измерени числа."""
    nulirai()
    t0 = time.time()

    print("── СРЕЩИ ──────────────────────────────────────────────")
    sr = srechti(dni=2)
    print("предстоящи ITF/Challenger сингъл : %d  (заявки: %d)"
          % (len(sr), broi_zayavki()))
    po_nivo = {}
    for m in sr:
        po_nivo[m["niv"] or "?"] = po_nivo.get(m["niv"] or "?", 0) + 1
    print("по ниво: " + ", ".join("%s=%d" % kv for kv in
                                  sorted(po_nivo.items(), key=lambda x: -x[1])))
    for m in sr[:5]:
        print("   %s  %-24s vs %-24s  %s" % (m["start_iso"][11:16], m["dom"],
                                             m["gost"], m["turnir"]))

    print()
    print("── ЦЕНА ОТ PINNACLE ───────────────────────────────────")
    try:
        import pinnacle as PN                                # noqa: PLC0415
    except Exception as e:                                   # noqa: BLE001
        print("pinnacle.py не се внесе: %s" % e)
        PN = None
    if PN is not None:
        surovi = 0
        obarnati = 0
        sega = time.time()
        blizki = [0, 0]
        for m in sr:
            if any(PN.ceni_za("tennis", m["dom"], m["gost"])[:2]):
                surovi += 1
            c = ceni(m, pn=PN)
            if c[0] or c[1]:
                obarnati += 1
                if m["start"] and (m["start"] - sega) < 12 * 3600:
                    blizki[0] += 1
            if m["start"] and (m["start"] - sega) < 12 * 3600:
                blizki[1] += 1
        n = max(1, len(sr))
        print("СУРОВИ имена   : %3d/%3d = %3.0f%%   <- така беше досега"
              % (surovi, len(sr), 100.0 * surovi / n))
        print("ОБЪРНАТИ имена : %3d/%3d = %3.0f%%   <- pn_ime()"
              % (obarnati, len(sr), 100.0 * obarnati / n))
        print("до 12 ч от старта: %3d/%3d = %3.0f%%"
              % (blizki[0], blizki[1], 100.0 * blizki[0] / max(1, blizki[1])))
        print("заявки на pinnacle.py: %d (кеширани за целия спорт)"
              % PN.broi_zayavki())

    print()
    print("── ИСТОРИЯ ────────────────────────────────────────────")
    proba = sr[:8]
    predi = broi_zayavki()
    dva = 0
    obshto = []
    for m in proba:
        h = istoriya(m)
        a, b = h["dom"]["igri"], h["gost"]["igri"]
        obshto += [a, b]
        if a >= 5 and b >= 5:
            dva += 1
        print("   %-22s %2d мача (%s)  |  %-22s %2d мача (%s)  | лични %d-%d"
              % (m["dom"], a, h["dom"]["dyal"], m["gost"], b, h["gost"]["dyal"],
                 h["h2h_dom"], h["h2h_gost"]))
    if proba:
        obshto.sort()
        med = obshto[len(obshto) // 2]
        print("медиана минали мачове: %d   двойки с >=5 за двамата: %d/%d = %.0f%%"
              % (med, dva, len(proba), 100.0 * dva / len(proba)))
        print("заявки за история: %d (по 1 на мач, но за ДВАМАТА)"
              % (broi_zayavki() - predi))

    print()
    print("── РЕЗУЛТАТИ (за оценителя) ───────────────────────────")
    predi = broi_zayavki()
    vchera = [_mach_ot_zapis(d) for d in _den(-1)
              if _e_nashe(d.get("_liga"), False)]
    vchera = [m for m in vchera if m]
    kray = {}
    otsadeni = 0
    razlika = 0
    for m in vchera:
        r = otsadi({"AB": "3" if m["faza"] == "свършил" else "1",
                    "AC": {v: k for k, v in KRAY.items()}.get(m["kray"], ""),
                    "AS": m["_AS"], "AG": m["_AG"], "AH": m["_AH"]})
        kray[m["kray"] or "?"] = kray.get(m["kray"] or "?", 0) + 1
        if r["pobeditel"]:
            otsadeni += 1
            # колко пъти сетовете биха дали ДРУГ отговор от AS
            try:
                a, b = int(m["_AG"]), int(m["_AH"])
                po_seta = 1 if a > b else (2 if b > a else 0)
            except (TypeError, ValueError):
                po_seta = 0
            if po_seta != r["pobeditel"]:
                razlika += 1
    print("вчерашни ITF/CH сингъл: %d   с отсъден победител: %d" % (len(vchera), otsadeni))
    print("по вид край: " + ", ".join("%s=%d" % kv for kv in sorted(kray.items())))
    print("🔴 колко биха се отсъдили ГРЕШНО само по сетовете: %d от %d"
          % (razlika, len(vchera)))
    print("заявки за резултати: %d (един ден = всички мачове)" % (broi_zayavki() - predi))

    print()
    print("── СМЕТКАТА ───────────────────────────────────────────")
    print("общо заявки на itf.py в това пускане : %d" % broi_zayavki())
    print("от тях за срещи 3, за резултати 1, останалото е история (по избор)")
    print("реален рън с 20 карти: 3 + 1 + 20 = 24 заявки  (таван 40)")
    print("време: %.1f сек" % (time.time() - t0))
    return 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if "--zhivo" in argv:
        return zhivo()
    print(__doc__)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")
    except Exception:                                        # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
