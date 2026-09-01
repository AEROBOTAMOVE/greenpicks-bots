# -*- coding: utf-8 -*-
"""ЕДИН ПАЗАЧ ЗА ВСИЧКИ БОТОВЕ — думите, които не излизат навън.

🔴 ЗАЩО СЪЩЕСТВУВА ТОЗИ ФАЙЛ (01.09.2026).

Оборващ агент намери две неща, всяко по-скъпо от другото:

  1. `scorer.py` държеше СОБСТВЕН списък от СЕДЕМ думи, нито една от които е
     име на букмейкър — а коментарът над него твърдеше „същият пазач като в
     другите ботове“. `predictor.py` държеше петдесет и четири. И точно
     оценителят пише в КАНАЛА. Измерено: „bet365 дава 2.10“, „DraftKings“,
     „Уинбет“, „https://efbet.com“ минаваха през оценителя свободно.

  2. Самото сравнение беше ГОЛ ПОДНИЗ върху `.lower()`. Измерено:
        един интервал по средата разбива 52 от 54 думи
        една точка по средата           54 от 54
        нулев интервал U+200B           54 от 54
        кирилско „е“ вместо латинско    25 от 25
     Тоест „Palms Bet“ — ОФИЦИАЛНИЯТ изпис на български оператор — минаваше.

И обратната посока, също измерена: пазачът убиваше НЕВИННИ карти.
     „Pinnacle Cup V“   е истински турнир по CS2 → цялата карта падаше
     „M15 Coral Gables“ е град в имената на ITF → същото
Пазач, изпитан само в едната посока, е половин пазач.

КАК РАБОТИ

  · и ТЕКСТЪТ, и СПИСЪКЪТ минават през една и съща нормализация
  · махат се невидимите знаци и кирилските двойници на латински букви
  · сравнява се ДВА пъти: както е, и със смачкани разделители
  · преди сравнението падат ИЗКЛЮЧЕНИЯТА (истински имена на турнири и градове)

ПЪТ НАЗАД: `GREENPICKS_PAZACH=0` изключва нормализацията и връща точно старото
сравнение по гол подниз. Списъкът остава пълен.
"""
import os
import unicodedata

VKLYUCHENO = (os.environ.get("GREENPICKS_PAZACH") or "1").strip() not in (
    "0", "false", "no", "не")

# ---------------------------------------------------------------- СПИСЪКЪТ
IMENA = [
    "bet365", "pinnacle", "bwin", "efbet", "winbet", "palmsbet",
    "betano", "1xbet", "betfred", "unibet", "sesame", "pickcenter",
    "fanduel", "draftkings", "betmgm", "caesars", "espnbet", "espn bet",
    "sportsbook", "betway", "ladbrokes", "williamhill", "william hill",
    "betfair", "paddypower", "paddy power", "skybet", "sky bet",
    "betvictor", "coral", "stoiximan", "parimatch", "sportingbet",
    "888sport", "pokerstars", "superbet", "novibet", "bet-at-home",
    "пинакъл", "бет365", "фандуел", "драфткингс", "бетмгм", "бетуей",
    "уилям хил", "бетфеър", "паримач", "ефбет", "уинбет", "палмсбет",
    "бетано", "сезам", "букмекър",
]

DUMI = [
    # 🔴 ГОЛОТО „залагай“ Е ЗАДЪЛЖИТЕЛНО (върнато 01.09.2026).
    # Сглобявайки този списък, написах само фразата „залагай отговорно“ и
    # изгубих голата дума, която старият BANNED_TOKENS имаше. Резултат:
    # проверката „хазартна дума не излиза“ спря да гърми, самопроверката
    # на модела падна в GitHub Actions и предсказателят НЕ ПУСНА нито една
    # карта след 15:50. Един пропуснат низ спря целия бот.
    "залагай", "заложи", "18+", "коеф", "букмейкър", "odds",
    "финансов съвет", "гарантирана печалба", "сигурен залог",
]

ZABRANENI = IMENA + DUMI

# ---------------------------------------------------------------- ИЗКЛЮЧЕНИЯ
# 🔴 ИСТИНСКИ ИМЕНА, които съдържат забранена дума. Всяко е ВИДЯНО в живите
# данни, не измислено. Махат се от текста ПРЕДИ съденето.
#
# Тук се влиза само с доказателство: име на турнир или град, дошло от самия
# източник. Влезе ли име, което не е такова, пазачът се отваря.
IZKLYUCHENIA = [
    "pinnacle cup",      # истински турнир по CS2, идва от източника на еспорта
    "coral gables",      # град във Флорида; ITF пише турнирите с името на града
    "coral springs",     # също град, също ITF
    "coral gable",       # среща се и в единствено число
]

# ---------------------------------------------------------------- НОРМАЛИЗАЦИЯ
# Невидими знаци. Един такъв по средата разбиваше всичките 54.
NEVIDIMI = "​‌‍⁠﻿­"

# Кирилски букви, които изглеждат ТОЧНО като латински. Само те — това не е превод.
DVOYNICI = {
    "а": "a", "е": "e", "о": "o", "р": "p",
    "с": "c", "у": "y", "х": "x", "к": "k",
    "м": "m", "т": "t", "в": "b", "н": "h",
    "і": "i", "ј": "j", "ѕ": "s",
}

RAZDELITELI = set(" .-_/\\|*+,:;()[]{}"
                  "–—·•‘’“”„"
                  "'\"")


def _normalno(s):
    """Едно и също лечение за текста и за списъка. Инак не се срещат."""
    t = unicodedata.normalize("NFKC", str(s or "")).lower()
    for z in NEVIDIMI:
        t = t.replace(z, "")
    return "".join(DVOYNICI.get(ch, ch) for ch in t)


def _smachkano(s):
    """Без нито един разделител. Хваща „b e t 3 6 5“ и „p.i.n.n.a.c.l.e“."""
    return "".join(ch for ch in s if ch not in RAZDELITELI)


_KESH = {}


def _spisaci():
    if "z" not in _KESH:
        # 🔴 СМАЧКВАНЕТО ВАЖИ САМО ЗА ИМЕНАТА (намерено при първото пускане).
        #
        # Проверката „обикновена карта минава“ ГРЪМНА и беше права: думата
        # „18+“ смачкана става „18“, а редът „💰 1.85“ смачкан става „185“.
        # Тоест пазачът обяви най-обикновена карта с цена за реклама.
        #
        # Причината не е в числото, а в РАЗЛИЧНАТА ПРИРОДА на двата списъка:
        # имената на букмейкъри са низове, които някой би разредил нарочно, за
        # да минат („P a l m s  B e t“). Думите като „18+“, „odds“, „коеф“ са
        # обикновен език — смачкани се сливат с всичко наоколо.
        #
        # Затова: имената минават през двете сита, думите — само през едното.
        _KESH["z"] = [(w, _normalno(w),
                       _smachkano(_normalno(w)) if w in IMENA else "")
                      for w in ZABRANENI]
        _KESH["i"] = [(_normalno(w), _smachkano(_normalno(w)))
                      for w in IZKLYUCHENIA]
    return _KESH["z"], _KESH["i"]


def banned_word(text):
    """Първата забранена дума в текста, или None.

    Връща ОРИГИНАЛНАТА дума от списъка, не нормализираната — тя отива в
    дневника и човек трябва да я разпознае.
    """
    if not text:
        return None
    if not VKLYUCHENO:
        low = str(text).lower()
        for w in ZABRANENI:
            if w in low:
                return w
        return None
    zab, izk = _spisaci()
    t = _normalno(text)
    s = _smachkano(t)
    # Изключенията падат ПЪРВИ и от двата вида текст.
    for ni, si in izk:
        t = t.replace(ni, " ")
        s = s.replace(si, " ")
    for w, nw, sw in zab:
        if nw and nw in t:
            return w
        if sw and sw in s:
            return w
    return None


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # ------------------------------------------------ хваща ли изобщо
    check("хваща голо име", banned_word("bet365") == "bet365")
    check("хваща в изречение", banned_word("цената при bwin е 2.10") == "bwin")
    check("хваща с главни букви", banned_word("DraftKings") == "draftkings")
    check("хваща кирилица", banned_word("Уинбет дава повече") == "уинбет")
    check("хваща в адрес", banned_word("https://efbet.com/x") == "efbet")
    check("хваща стара дума", banned_word("залагай отговорно") is not None)
    # 🔴 ТОЧНО НИЗЪТ, КОЙТО СВАЛИ ПРОИЗВОДСТВОТО.
    check("голото „залагай“ се хваща", banned_word("залагай сега") == "залагай")
    check("и вътре в изречение", banned_word("хайде, залагай днес") is not None)

    # ------------------------------------------------ 🔴 ЗАОБИКАЛЯНИЯТА
    # Всяко от тези МИНАВАШЕ през стария пазач. Измерено, не предположено.
    check("интервал по средата", banned_word("Palms Bet") is not None)
    check("интервал в bet 365", banned_word("bet 365") is not None)
    check("точка по средата", banned_word("p.i.n.n.a.c.l.e") is not None)
    check("тире по средата", banned_word("draft-kings") is not None)
    check("нулев интервал", banned_word("bet​365") is not None)
    check("мек пренос", banned_word("bet­365") is not None)
    check("кирилско е", banned_word("bеt365") is not None)
    check("кирилско а и о", banned_word("betаnо") is not None)
    check("разредено с интервали", banned_word("W I N B E T") is not None)
    check("българско с интервал", banned_word("Уин бет") is not None)
    check("Еф бет с интервал", banned_word("Еф бет") is not None)
    check("точки в българското", banned_word("П.и.н.а.к.ъ.л") is not None)

    # ------------------------------------------------ 🔴 ОБРАТНАТА ПОСОКА
    # Пазач, изпитан само в едната посока, е половин пазач. Всяко от тези е
    # ИСТИНСКО име от живите данни и НЕ бива да пада.
    check("турнирът Pinnacle Cup минава",
          banned_word("Pinnacle Cup V") is None)
    check("и с продължение", banned_word("Pinnacle Cup V · CS2") is None)
    check("градът Coral Gables минава",
          banned_word("M15 Coral Gables") is None)
    check("Coral Springs минава", banned_word("W35 Coral Springs") is None)
    check("Бетис не се блокира", banned_word("Реал Бетис — Севиля") is None)
    check("Betis на латиница също", banned_word("Real Betis") is None)
    check("Тибет не се блокира", banned_word("Тибет") is None)
    check("обет не се блокира", banned_word("обет") is None)
    check("обикновена карта минава",
          banned_word("⚽ Арсенал — Челси · 1 · 62% · 💰 1.85") is None)
    check("празното не гърми",
          banned_word("") is None and banned_word(None) is None)

    # 🔴 НО изключението НЕ Е отворена врата: същият низ с истинско име пада.
    check("изключението не крие друго име",
          banned_word("Pinnacle Cup V, цени от bet365") == "bet365")
    check("и Coral Gables не крие друго",
          banned_word("M15 Coral Gables · winbet") == "winbet")
    check("самото pinnacle БЕЗ турнира пак пада",
          banned_word("цена от pinnacle") == "pinnacle")
    # 🔴 ЧИСЛАТА. Тази проверка се роди от истинско гръмване: „18+“ смачкано
    # става „18“ и обявяваше „💰 1.85“ за реклама. Всяка от долните е ред,
    # който ботът печата всеки ден.
    check("цена 1.85 не е реклама", banned_word("💰 1.85") is None)
    check("цена 1.18 не е реклама", banned_word("💰 1.18") is None)
    check("процент 18% не е реклама", banned_word("вероятност 18%") is None)
    check("резултат 18:5 не е реклама", banned_word("18:5") is None)
    check("но истинското 18+ пада", banned_word("само за 18+") == "18+")
    check("и предупреждението пада",
          banned_word("залагай отговорно") is not None)
    # Смачкването пази ИМЕНАТА, не думите — това е самото правило.
    check("разреденото ИМЕ пада", banned_word("P a l m s B e t") is not None)
    check("разредената ДУМА минава (нарочно)", banned_word("o d d s") is None)

    # ------------------------------------------------ списъкът
    check("списъкът е голям", len(ZABRANENI) >= 50)
    check("няма празни думи", all(str(w).strip() for w in ZABRANENI))
    check("няма дублирани", len(ZABRANENI) == len(set(ZABRANENI)))
    # 🔴 Изключение, което НЕ съдържа забранена дума, е излишно и подвежда:
    # чете се като „тази дума е позволена“, а тя изобщо не е била забранена.
    check("всяко изключение съдържа забранена дума",
          all(any(_normalno(z) in _normalno(i) for z in ZABRANENI)
              for i in IZKLYUCHENIA))

    # ------------------------------------------------ пътят назад
    global VKLYUCHENO
    _staro = VKLYUCHENO
    try:
        VKLYUCHENO = False
        check("ключът връща стария гол подниз",
              banned_word("Palms Bet") is None)
        check("но списъкът си работи", banned_word("bet365") == "bet365")
    finally:
        VKLYUCHENO = _staro
    check("и се връща след теста", VKLYUCHENO is _staro)
    check("след връщането пак хваща интервала",
          banned_word("Palms Bet") is not None)

    print("SELFTEST: %d/%d PASS" % (ok, ok + len(bad)))
    for b in bad:
        print("   FAIL: " + b)
    return ok, bad


if __name__ == "__main__":
    _o, _b = selftest()
    raise SystemExit(1 if _b else 0)
