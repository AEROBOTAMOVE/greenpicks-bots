# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ВТОРИЯТ ИЗТОЧНИК НА ЦЕНА 📉

Един въпрос: колко плаща пазарът за изходите, за които ESPN мълчи?

ЗАЩО СЪЩЕСТВУВА
ESPN дава цена само за футбол, баскетбол и бейзбол. Това са 123 от 400-те ни
карти. Двата НАЙ-ГОЛЕМИ спорта — волейбол (116) и тенис на маса (114) — плюс
тенисът (40) остават без цена, тоест доходността щеше да се мери на 31% от
продукта, а 69% да останат неизмерими завинаги.

Измерено на живо 18.08.2026 срещу guest слоя на Pinnacle:
  🎾 тенис          37 лиги, всичките с мачове  (ATP, WTA, ITF)   ✅
  🥊 ММА            UFC                                            ✅
  ⚾ бейзбол        МЛБ, Корея, Япония                             ✅
  🏀 баскетбол      12 лиги                                        ✅
  ⚽ футбол         154 лиги                                       ✅
  🏓 тенис на маса  ТЕ НЯМАТ ТОЗИ СПОРТ — 0 лиги, 0 мача, винаги    ❌
  🏐 волейбол       ТЕ НЯМАТ ТОЗИ СПОРТ — 0 лиги, 0 мача, винаги    ❌

🔴 И ЕДНА ГРАНИЦА, КОЯТО НЯМА ДА СЕ ПРЕМИНЕ С ПО-ДОБЪР ИЗТОЧНИК
64 от 116-те ни волейболни карти са „FIVB Girls' U17 World Championship".
Пазар за волейбол при момичета до 17 години НЕ СЪЩЕСТВУВА при никой букмейкър.
Тоест волейболът остава неизмерим не защото не сме търсили, а защото няма
какво да се сравнява. Реалният таван на покритието е около 70% от картите.

ЗАЩО ИМЕННО PINNACLE
Линията му е най-острата в бранша: маржът е 2-3% вместо 5-7%, защото печели от
оборот, а не от разликата. Тоест като еталон за „бием ли пазара" струва повече
от която и да е витрина. Не го рекламираме, не го именуваме пред читателя —
числото влиза в ДНЕВНИКА, картата остава каквато е.

ЦЕНАТА В ЗАЯВКИ
ДВЕ на спорт на пускане, кеширани:
  /sports/{id}/matchups          — кой срещу кого
  /sports/{id}/markets/straight  — цените на всички наведнъж (0.3 сек за 3298)
Измерено: 12 заявки подред минават без ограничение.

  python pinnacle.py --selftest   — проверките, без мрежа
  python pinnacle.py --zhivo      — истинско питане, за очи
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

BAZA = "https://guest.api.arcadia.pinnacle.com/0.1"
TIMEOUT = int((os.environ.get("PIN_TIMEOUT") or "15").strip() or 15)

# Нашите имена на спортове -> техните номера.
#
# 🔴 ДВЕ ПОПРАВКИ НА СОБСТВЕНАТА МИ ПРЕЦЕНКА.
#
# 18.08: изключих волейбола заради 401 на /sports/34/leagues. Грешно —
# адресите, които РЕАЛНО ползваме, връщат 200.
#
# 19.08: но и второто ми обяснение („днес просто няма мачове") е ГРЕШНО.
# Измерено: за волейбол Pinnacle дава matchupCount=0, /matchups=0,
# /markets/straight=0 И /leagues=0 — при това EuroVolley почва след два дни и
# други книги вече го котират. Тоест ТЕ НЯМАТ ТОЗИ СПОРТ, а не че сезонът
# спи. Същото важи и за ТЕНИСА НА МАСА: id 32 дава нула лиги, докато тенисът
# (33) в същата секунда дава 532 мача.
#
# Питат се пак евтино (две заявки), но да се очаква нула — и картите за тези
# два спорта минават през ДРУГ път, не през цена.
SPORT_ID = {
    "tennis": 33,
    "mma": 22,
    "tabletennis": 32,
    "volleyball": 34,
    "baseball": 3,
    "basketball": 4,
    "football": 29,
}

# 🔴 ЧЕСТНИЯТ ТАВАН НА ВОЛЕЙБОЛА (измерено 18.08.2026 върху живия дневник).
#
# 64 от 116-те ни волейболни карти са „FIVB Girls' U17 World Championship",
# останалите — ECVA и NORCECA U17. Това са ЮНОШЕСКИ и малки регионални
# турнири. Никой букмейкър не предлага пазар за волейбол при момичета до 17
# години — и това НЕ е дупка в източника, а липса на пазар изобщо.
#
# Значи: волейболът се пита (евтино е, две заявки), но да се очаква нула. Ако
# някой ден пуснем клубните лиги (старт септември-октомври), тогава ще има.

# Спортове с три изхода. При останалите равен няма.
TRI_IZHODA = {"football"}

_kesh = {}
_broi = [0]


def broi_zayavki():
    """Колко заявки е направил модулът в това пускане."""
    return _broi[0]


def _j(pat):
    _broi[0] += 1
    try:
        rq = urllib.request.Request(BAZA + pat, headers={"Accept": "application/json"})
        with urllib.request.urlopen(rq, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:                                        # noqa: BLE001
        return None


def deset(amerikansko):
    """Американска цена -> десетична. -145 значи 1.69, +631 значи 7.31.

    Pinnacle дава САМО американски формат в този слой. Проверено живо:
    ITF мач с -1197 / +631.
    """
    try:
        a = float(amerikansko)
    except (TypeError, ValueError):
        return None
    if a >= 100.0:
        return round(1.0 + a / 100.0, 2)
    if a <= -100.0:
        return round(1.0 + 100.0 / abs(a), 2)
    return None


def _norm(s):
    """Име, сведено до сравнимо: малки букви, само букви и цифри."""
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def _familiya(s):
    """Последната дума на името. Тенисистите се пишат ту с второ име, ту без."""
    d = [w for w in str(s or "").replace("-", " ").split() if w]
    return _norm(d[-1]) if d else ""


def machove(sport_key):
    """{номер: (дом, гост, лига, старт)} за един спорт. Кеширано."""
    sid = SPORT_ID.get(str(sport_key))
    if not sid:
        return {}
    kl = ("m", sid)
    if kl in _kesh:
        return _kesh[kl]
    out = {}
    for x in (_j("/sports/%d/matchups" % sid) or []):
        if not isinstance(x, dict) or x.get("type") != "matchup":
            continue
        # Подматчъпите (сетове, геймове) носят parentId. Искаме само мача.
        if x.get("parentId"):
            continue
        uch = x.get("participants") or []
        if len(uch) < 2:
            continue
        dom = gost = None
        for p in uch:
            if str(p.get("alignment")) == "home":
                dom = p.get("name")
            elif str(p.get("alignment")) == "away":
                gost = p.get("name")
        if dom is None or gost is None:
            dom, gost = uch[0].get("name"), uch[1].get("name")
        if not dom or not gost:
            continue
        out[str(x.get("id"))] = (str(dom), str(gost),
                                 str((x.get("league") or {}).get("name") or ""),
                                 str(x.get("startTime") or ""))
    _kesh[kl] = out
    return out


def pazari(sport_key):
    """{номер: (цена_дом, цена_гост, цена_равен)} за един спорт. Кеширано.

    ЕДНА заявка за целия спорт. Мерено: тенисът дава 3298 пазара за 0.3 сек,
    от които 165 са основните (moneyline за целия мач).
    """
    sid = SPORT_ID.get(str(sport_key))
    if not sid:
        return {}
    kl = ("p", sid)
    if kl in _kesh:
        return _kesh[kl]
    out = {}
    for k in (_j("/sports/%d/markets/straight" % sid) or []):
        if not isinstance(k, dict):
            continue
        # period 0 = целият мач. Сетовете и геймовете не ни трябват.
        if k.get("type") != "moneyline" or k.get("period") != 0:
            continue
        dom = gost = raven = None
        for pr in (k.get("prices") or []):
            d = str(pr.get("designation") or "").lower()
            c = deset(pr.get("price"))
            if d == "home":
                dom = c
            elif d == "away":
                gost = c
            elif d == "draw":
                raven = c
        if dom or gost:
            out[str(k.get("matchupId"))] = (dom, gost, raven)
    _kesh[kl] = out
    return out


def nameri(sport_key, dom, gost):
    """Номерът на нашия мач при тях. None, ако не се намери.

    Три опита, от строгото към хлабавото:
      1. и двете пълни имена съвпадат
      2. и двете фамилии съвпадат  (Pinnacle пише „Janice Tjen", ние —
         понякога „J. Tjen"; ESPN дава ту с, ту без второ име)
      3. едното име се съдържа в другото И в двете посоки

    Разменените страни се приемат: домакин/гост е уговорка, не факт, а при
    тениса „домакин" изобщо не значи нищо.
    """
    mm = machove(sport_key)
    if not mm:
        return None
    nd, ng = _norm(dom), _norm(gost)
    if not nd or not ng or nd == ng:
        return None
    fd, fg = _familiya(dom), _familiya(gost)

    for mid, (a, b, _lg, _st) in mm.items():
        na, nb = _norm(a), _norm(b)
        if {na, nb} == {nd, ng}:
            return mid
    if fd and fg and fd != fg:
        for mid, (a, b, _lg, _st) in mm.items():
            if {_familiya(a), _familiya(b)} == {fd, fg}:
                return mid
    for mid, (a, b, _lg, _st) in mm.items():
        na, nb = _norm(a), _norm(b)
        if not na or not nb:
            continue
        if (((nd in na or na in nd) and (ng in nb or nb in ng))
                or ((nd in nb or nb in nd) and (ng in na or na in ng))):
            return mid
    return None


def ceni_za(sport_key, dom, gost):
    """(цена_дом, цена_гост, цена_равен) за НАШИТЕ имена. Всяка може да е None.

    🔴 СТРАНИТЕ СЕ ВРЪЩАТ ПО НАШАТА УГОВОРКА, не по тяхната. Ако Pinnacle
    държи мача обърнат, цените се разменят обратно — инак картата казва „1",
    а числото е за другия. Точно този клас грешка ни ухапа днес с питчърите.
    """
    mid = nameri(sport_key, dom, gost)
    if not mid:
        return (None, None, None)
    c = pazari(sport_key).get(mid)
    if not c:
        return (None, None, None)
    a, b, _lg, _st = machove(sport_key)[mid]
    if _norm(a) == _norm(gost) or (_familiya(a) and _familiya(a) == _familiya(gost)):
        return (c[1], c[0], c[2])
    return c


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    check("+631 значи 7.31", deset(631) == 7.31)
    check("-1197 значи 1.08", deset(-1197) == 1.08)
    check("+100 значи 2.00", deset(100) == 2.0)
    check("-100 значи 2.00", deset(-100) == 2.0)
    check("между -100 и 100 не е цена", deset(50) is None and deset(-99) is None)
    check("боклук не гърми", deset("абв") is None and deset(None) is None)

    check("волейболът се пита — вратата е отворена", SPORT_ID.get("volleyball") == 34)
    check("тенисът се пита", SPORT_ID.get("tennis") == 33)
    check("само футболът има равен", TRI_IZHODA == {"football"})
    check("непознат спорт не дава мачове", machove("кърлинг") == {})
    check("непознат спорт не дава пазари", pazari("кърлинг") == {})

    check("фамилията е последната дума", _familiya("Janice Tjen") == "tjen")
    check("тирето не чупи фамилията",
          _familiya("Felix Auger-Aliassime") == "aliassime")
    check("празното име няма фамилия", _familiya("") == "" and _familiya(None) == "")

    # Търсенето — с подхвърлени данни, без мрежа.
    _st_m, _st_p = _kesh.get(("m", 33)), _kesh.get(("p", 33))
    try:
        _kesh[("m", 33)] = {
            "111": ("Janice Tjen", "Mirra Andreeva", "WTA Cincinnati", ""),
            "222": ("Carlos Alcaraz", "Jannik Sinner", "ATP", ""),
        }
        _kesh[("p", 33)] = {"111": (6.14, 1.16, None), "222": (2.10, 1.75, None)}
        check("точните имена намират мача", nameri("tennis", "Janice Tjen", "Mirra Andreeva") == "111")
        check("разменените страни също намират",
              nameri("tennis", "Mirra Andreeva", "Janice Tjen") == "111")
        check("само фамилиите намират", nameri("tennis", "J. Tjen", "M. Andreeva") == "111")
        check("непознат мач не намира", nameri("tennis", "Иван", "Драган") is None)
        check("еднакви имена не намират", nameri("tennis", "Tjen", "Tjen") is None)
        check("празно име не намира", nameri("tennis", "", "Andreeva") is None)

        check("цената идва в НАШИЯ ред",
              ceni_za("tennis", "Janice Tjen", "Mirra Andreeva") == (6.14, 1.16, None))
        # 🔴 НАЙ-ВАЖНАТА ПРОВЕРКА В ФАЙЛА. Ако Pinnacle държи мача обърнат,
        # цените ТРЯБВА да се разменят обратно. Инак картата пише „2 · Tjen",
        # а числото до нея е за Андреева.
        check("обърнатият мач връща РАЗМЕНЕНИ цени",
              ceni_za("tennis", "Mirra Andreeva", "Janice Tjen") == (1.16, 6.14, None))
        check("непознат мач не дава цена",
              ceni_za("tennis", "Иван", "Драган") == (None, None, None))
    finally:
        if _st_m is None:
            _kesh.pop(("m", 33), None)
        else:
            _kesh[("m", 33)] = _st_m
        if _st_p is None:
            _kesh.pop(("p", 33), None)
        else:
            _kesh[("p", 33)] = _st_p

    check("кешът е чист след теста", ("m", 33) not in _kesh)
    check("броячът на заявки работи", isinstance(broi_zayavki(), int))
    check("нула мрежа в самопроверката", broi_zayavki() == 0)
    check("броят проверки е поне 25", ok >= 25)

    print("САМОПРОВЕРКА НА PINNACLE: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


def zhivo():
    """Истинско питане — за очи, не за автомат."""
    for sp in ("tennis", "mma", "tabletennis", "baseball", "basketball", "football"):
        mm, pp = machove(sp), pazari(sp)
        s_cena = sum(1 for k in mm if k in pp)
        print("%-13s мачове: %-4d с цена: %-4d" % (sp, len(mm), s_cena))
        for k, (a, b, lg, st) in list(mm.items())[:2]:
            c = pp.get(k)
            if c:
                print("      %-40s %s / %s%s   %s"
                      % ((str(a)[:19] + " - " + str(b)[:19]), c[0], c[1],
                         ("" if c[2] is None else (" / " + str(c[2]))), str(lg)[:26]))
    print("заявки общо: %d" % broi_zayavki())
    return 0


if __name__ == "__main__":
    if "--zhivo" in sys.argv:
        sys.exit(zhivo())
    sys.exit(selftest())
