# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БУДИЛНИК ⏰

Един въпрос: ПРОСПА ЛИ предсказателят своя час?

ЗАЩО СЪЩЕСТВУВА
Кронът на GitHub не е часовник, а молба. Измерено върху живите рънове:
закъснява средно 65 минути, а на 06.08.2026 ПРОПУСНА пет от осем пускания.
Тоест в стаята няма карти, никой не е сгрешил и нищо не е червено.

Обичайното лекарство е външен будилник (cron-job.org), но той иска GitHub
токен, въведен в поле. Този файл прави същото БЕЗ никакъв ключ и без външна
услуга: рутерът е в СЪЩАТА concurrency група като предсказателя, значи може да
го събуди, без да се блъскат.

КОЛКО ЧЕСТО ВСЪЩНОСТ — ИЗМЕРЕНО, НЕ ПРЕДПОЛОЖЕНО
Разписанието на рутера е */10, но GitHub го спазва рядко: за 21 дни излизат
6.5 ръна на ден, медианна пауза 74 минути (нула паузи под 15 мин). Тоест
резолюцията на будилника е ОКОЛО ЧАС, не десет минути. Пак си струва: на
измерените дни първата карта се мести от 10:36-13:00 на 08:06-09:31.

КАК РЕШАВА
Чете `diag.koga` от predict_state.json — часът на последното пускане, записан
в СОФИЙСКО време от самия предсказател (predictor.py, ред ~721). Ако сме в
работните часове и от последното пускане са минали повече от тавана — будим.

ЗАЩО ФАЛШИВОТО БУДЕНЕ Е ЕВТИНО
Предсказателят помни какво вече е пуснал (ключът `posted`) и има дневен таван.
Излишен рън не праща дубли — най-многото, което прави, е няколко заявки.
Пропуснатият час обаче е празна стая. Затова при съмнение будим.

ЧАСОВАТА ЗОНА СЕ СМЯТА С zoneinfo, НЕ С TZ
Вече ни е лъгало: `TZ=Europe/Sofia` на рънъра връща UTC мълчаливо.

  python budilnik.py            — решава и печата
  python budilnik.py --selftest — само проверките
"""
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SOFIA = ZoneInfo("Europe/Sofia")
STATE_FILE = (os.environ.get("PREDICT_STATE_FILE") or "predict_state.json").strip()


def _cyalo(ime, po_podrazbirane, dolna, gorna):
    try:
        n = int(str(os.environ.get(ime) or "").strip())
    except (TypeError, ValueError):
        return po_podrazbirane
    return max(dolna, min(gorna, n))


# Работните часове на предсказателя.
#
# 🔴 ОТ КЛЮЧОВЕТЕ, НЕ ОТ ТЕКСТА (02.09.2026). Дотук самопроверката тук
# ЧЕТЕШЕ predictor.py като текст и търсеше низа „RUN_HOURS = tuple(range(“.
# В деня, в който часовете станаха подвижни (решение на собственика:
# „без ограничения в часовете“), този низ изчезна и будилникът гръмна —
# 146 наред, 1 счупено, без нито един истински дефект.
#
# Сега двамата четат ЕДНИ И СЪЩИ ключове от средата, а workflow-ът им е
# същият. Разминаване по устройство не може да има.
_QT = _cyalo("PREDICT_QUIET_TO", 8, 0, 11)
_QF = _cyalo("PREDICT_QUIET_FROM", 23, 12, 23)


def _granici(qt, qf):
    """(първи, последен работен час) от прозореца на предсказателя.

    🔴 ПРАВИЛОТО Е НА ЕДНО МЯСТО (02.09.2026). Дотук то стоеше вграденo в
    двата реда по-долу, а самопроверката го ПРЕПИСВАШЕ, за да го сравни със
    себе си — тоест сверяваше препис с препис. Сега тестът вика тази функция:
    развали ли се тя, проверката пада.

    Предсказателят пуска в целия прозорец при пълен ден, инак без последния
    час (той е гратис за закъснял крон).
    """
    return qt, (qf if (qt == 0 and qf == 23) else qf - 1)


_PALEN = (_QT == 0 and _QF == 23)
OT_CHAS = _cyalo("BUDILNIK_OT", _granici(_QT, _QF)[0], 0, 23)
DO_CHAS = _cyalo("BUDILNIK_DO", _granici(_QT, _QF)[1], 0, 23)

# ═══════════════════════════════════════════════════════════════════════════
#  🔌 РЪЧКА, КОЯТО НЕ СТИГА ДО ПРОЦЕСА, Е МЪРТВА (02.09.2026, измерено)
#
#  budilnik.py чете PREDICT_QUIET_TO и PREDICT_QUIET_FROM (двата реда горе).
#  Измерено в тази сесия с grep по живите workflow-и:
#     predict.yml:299-300  подава и двете на ПРЕДСКАЗАТЕЛЯ
#     router.yml:158-162   стъпката «Проспа ли предсказателя или оценителя»
#                          има env САМО BUDILNIK_OCENITEL — нито една от двете
#  Тоест: вдигне ли собственикът денонощния режим, предсказателят тръгва в
#  0-23, а будилникът остава на 8-22 и няма да го събуди нито веднъж между
#  23:00 и 07:59. Точно същият дефект вече беше намерен в predict.yml.
#
#  Тук той се ОТКРИВА, не се поправя: поправката е два реда в router.yml, а
#  този файл не пипа чужди файлове. Резултатът излиза като ⚠ НЕСВЕРЕНО, не
#  като счупено — червената самопроверка спира ЦЕЛИЯ рутер (виж по-долу).
#
#  🔴 СПИСЪКЪТ НЕ СЕ ПИТА КАКВО ДА ТЪРСИ. Ядрото се изброява на ДРУГО място —
#  в двата реда горе, които наистина четат ключовете, — и самопроверката ги
#  сверява с този списък. Махне ли се ключ само от списъка, проверката пада.
# ═══════════════════════════════════════════════════════════════════════════
RYACHKI = ("PREDICT_QUIET_FROM", "PREDICT_QUIET_TO")


def _stapki(tekst):
    """Текстът на workflow, нарязан на блокове по «- name:». Списък от низове."""
    redove = str(tekst or "").split(chr(10))
    nachala = [i for i, r in enumerate(redove)
               if r.strip().startswith("- name:")]
    blokove = []
    for k, i in enumerate(nachala):
        kraj = nachala[k + 1] if k + 1 < len(nachala) else len(redove)
        blokove.append(chr(10).join(redove[i:kraj]))
    return blokove


def _goliyat_budilnik(blok):
    """Пуска ли този блок budilnik.py БЕЗ --selftest."""
    for r in str(blok or "").split(chr(10)):
        s = r.strip()
        if s.startswith("#"):
            continue
        if s.startswith("run:"):
            s = s[4:].strip()
        if s == "python budilnik.py":
            return True
    return False


def ryachkite_v_router(tekst, ryachki=None):
    """Кои ръчки НЕ стигат до будилника през този текст на router.yml.

    Връща сортиран списък с липсващите, [] когато всичко е подадено, и
    None когато изобщо няма стъпка, която да пуска голия budilnik.py.

    🔴 СЕНТИНЕЛ, НЕ ПРАЗЕН СПИСЪК: «не намирам стъпката» не е «всичко е наред».
    🔴 РЕЖЕ БЛОКА И ГЛЕДА ВЪТРЕ, не търси низ в целия файл: ключът, споменат в
       съседен коментар или в друга стъпка, НЕ се брои за подаден.
    """
    ryachki = RYACHKI if ryachki is None else ryachki
    for blok in _stapki(tekst):
        if not _goliyat_budilnik(blok):
            continue
        dadeni = set()
        for r in blok.split(chr(10)):
            s = r.strip()
            if s.startswith("#") or ":" not in s:
                continue
            ime = s.split(":", 1)[0].strip()
            if ime and ime.replace("_", "").isalnum() and ime.isupper():
                dadeni.add(ime)
        return sorted(k for k in ryachki if k not in dadeni)
    return None

# Таванът. Пусканията са на час, но закъсняват неравномерно: рън, закъснял с
# 10 мин, следван от рън, закъснял със 70, дава 120 минути разстояние БЕЗ да е
# пропуснат нито един. Затова 90 не е „час и половина за красота" — под него
# будилникът щеше да гърми по нормални дни.
TAVAN_MIN = _cyalo("BUDILNIK_TAVAN", 90, 20, 600)

# 🔴 ВТОРО ПРАВИЛО: ПРОПУСНАТ ЧАС (21.08.2026).
#
# Таванът от 90 минути пази от ЛЪЖЛИВА тревога и си върши работата:
# измерено върху живите пускания, нормалните паузи са медиана 66 минути,
# най-дълга 68 — тоест НУЛА от тях го прекрачват.
#
# Но той отговаря на грешния въпрос. Предсказателят има крон ВСЕКИ ЧАС.
# Пропусне ли GitHub един (случи се днес в 09:00), стаята мълчи 91 минути,
# преди някой да забележи — при положение че СЛЕД ДЕСЕТ МИНУТИ вече се
# знае, че часът е пропуснат.
#
# Затова: ако сме в работните часове, минали са поне ГРАТИС минути от
# началото на часа, и последното пускане е било в ПРЕДИШЕН час — будим.
# Това е точно намерението на разписанието, само че проверено, вместо
# оставено на доверие.
#
# Цената е най-много едно допълнително пускане на час — а излишният рън не
# праща дубли (предсказателят помни какво е пуснал) и струва няколко
# заявки. Празната стая струва повече.
GRATIS_MIN = _cyalo("BUDILNIK_GRATIS", 12, 3, 45)


def posleden_run(path=None):
    """Кога предсказателят е пускал за последно. None = не знаем."""
    put = path or STATE_FILE
    try:
        with io.open(put, encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:                                        # noqa: BLE001
        return None
    if not isinstance(d, dict):
        return None
    koga = ((d.get("diag") or {}) if isinstance(d.get("diag"), dict) else {}).get("koga")
    if not koga:
        return None
    for vid in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(koga).strip(), vid).replace(tzinfo=SOFIA)
        except ValueError:
            continue
    return None


BUD_STATE = (os.environ.get("BUDILNIK_STATE_FILE") or "budilnik_state.json").strip()
# Колко да НЕ будим пак след опит. Ако предсказателят падне по средата, той не
# записва тефтера си — тоест дупката остава и будилникът щеше да го вика пак
# след десет минути, и пак, и пак. Спирачка: един опит на половин час.
POCHIVKA_MIN = _cyalo("BUDILNIK_POCHIVKA", 30, 10, 240)


def posleden_opit(path=None):
    """Кога будилникът е будил ПРЕДСКАЗАТЕЛЯ за последно. None = никога."""
    return _chas(cheti_sast(path).get("posleden_opit"))


def zapishi_opit(sega, path=None):
    """Отбелязва опит за предсказателя, БЕЗ да трие останалото в тефтера.

    🔴 ЧЕТЕ-МЕНИ-ПИШИ, НЕ ПРЕЗАПИСВАЙ (25.08.2026).
    Дотук тук стоеше json.dump с ЦЯЛ НОВ речник върху стария. Докато в тефтера
    живееше само този ключ, това беше безобидно. От днес в него живеят и
    марките на равносметките (ravnosmetki), и опитите за оценителя (ocenitel).
    Презапис би ги изтривал при ВСЯКО будене на предсказателя — тоест пазачът
    срещу дублирана равносметка щеше да губи паметта си по няколко пъти на ден
    и да мълчи за това. Самопроверката „буденето на предсказателя НЕ трие
    марките“ пази точно тук.
    """
    sast = cheti_sast(path)
    sast["posleden_opit"] = sega.strftime("%Y-%m-%d %H:%M")
    return pishi_sast(sast, path)


# ═══════════════════════════════════════════════════════════════════════════
#  🗒️ ТЕФТЕРЪТ Е ЕДИН, А ПИСАЧИТЕ СА ТРИМА (25.08.2026)
#
#  budilnik_state.json се пише от рутера, от съпорта и (от днес) от оценителя.
#  Затова всеки запис е ЧЕТЕ-МЕНИ-ПИШИ, не презапис, и всяко четене понася
#  боклук, без да гърми. Файлът се връща в хранилището от router.yml и
#  support.yml (виж списъка в стъпката „Save state“).
#
#  Тримата НЕ се блъскат по устройство: router.yml, support.yml, predict.yml и
#  score.yml са в ЕДНА concurrency група (greenpicks-state, cancel-in-progress:
#  false), тоест вървят един след друг, не едновременно.
# ═══════════════════════════════════════════════════════════════════════════


def _chas(s):
    """„2026-08-25 22:47“ -> datetime в софийска зона. Кривото дава None."""
    for vid in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(s).strip(), vid).replace(tzinfo=SOFIA)
        except (ValueError, TypeError):
            continue
    return None


def cheti_sast(path=None):
    """Целият тефтер като речник. Липса или боклук = празен, без гърмеж."""
    put = path or BUD_STATE
    try:
        with io.open(put, encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:                                        # noqa: BLE001
        return {}
    return d if isinstance(d, dict) else {}


def pishi_sast(sast, path=None):
    """Записва целия тефтер. През .tmp — прекъснат запис не оставя огризка."""
    put = path or BUD_STATE
    try:
        tmp = put + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(sast, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, put)
        return True
    except Exception:                                        # noqa: BLE001
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  🛡️ ПАЗАЧЪТ СРЕЩУ ПОВТОРЕНА РАВНОСМЕТКА (25.08.2026)
#
#  ЗАЩО ЖИВЕЕ ТУК, А НЕ В scorer.py
#  Оценителят няма НИТО ЕДНА марка за пратено съобщение (единственият му пазач
#  е combo_done, и той е за фишове). Измерено офлайн на 25.08: пет вечерни
#  пускания на main() дават 15 съобщения, от които 10 са БУКВА ПО БУКВА едни и
#  същи („🏁 ФИНИШ НА ДЕНЯ“ в стая 9 и в канала) и 5 са „🧾 ДОСЕГА ОБЩО“.
#  Досега това не личеше, защото оценителят се пуска два пъти на ден. От днес
#  рутерът може да го буди — и без пазач каналът получава равносметка на всеки
#  рън.
#
#  Логиката стои в будилника, защото:
#    • тефтерът е СЪЩИЯТ (budilnik_state.json) и вече се връща в хранилището;
#    • самият будилник трябва да знае дали равносметката е излязла, за да не
#      буди напразно — тоест и без оценителя щеше да му трябва;
#    • тук се проверява с мутация в тази самопроверка, а scorer.py е зает.
#  scorer.py я вика през try/except: липсва ли будилникът, оценителят праща
#  както досега. Провалът е към ШУМ, не към ТИШИНА — мълчалива равносметка е
#  точно аварията, срещу която строим.
#
#  КАКВО ПАЗИ И В ДВЕТЕ ПОСОКИ
#    ✖ същият текст втори път  → ключът вече съществува → мълчи
#    ✖ да млъкне завинаги      → ключът носи ОТПЕЧАТЪКА на текста; смени ли се
#                                число, ключът е нов и съобщението излиза
#  Тоест не е „веднъж на ден“, а „веднъж на СЪДЪРЖАНИЕ“, с таван на броя.
#
#  ОТПЕЧАТЪКЪТ МАХА ЧАСА, И ТО САМО ОТ ПЪРВИЯ РЕД. Проверено в scorer.py:
#  „📊 ОБЗОР · нд 23.08, 22:30“ (chas_bg, ред 1231) и „🕒 ДОКЪДЕ СМЕ ДНЕС ·
#  нд 23.08, 14:07“ (ред 1757) носят часа само в заглавието; „🏁 ФИНИШ НА
#  ДЕНЯ“ и „🧾 ДОСЕГА ОБЩО“ нямат час изобщо. Ако чистехме HH:MM в ЦЕЛИЯ
#  текст, два различни обзора, които се различават само по началните часове на
#  мачовете, щяха да получат ЕДИН отпечатък — тоест вторият щеше да изчезне.
#  Затова ножът реже един ред, не целия текст.
# ═══════════════════════════════════════════════════════════════════════════

# Колко РАЗЛИЧНИ съобщения от един вид, за един ден и за един адрес.
# Три е избрано, не отгатнато: вечерният прозорец на оценителя е 20:00-04:59
# (девет часа) и в него числата мърдат най-много два-три пъти — късните мачове
# идват на вълни. Четвърто съобщение за същия ден е шум, не новина.
RAVN_TAVAN = _cyalo("SCORE_RAVN_TAVAN", 3, 1, 12)
# 🔴 ОБЗОРЪТ Е ДРУГО НЕЩО И ТАВАНЪТ МУ Е ДРУГ (25.08.2026, измерено).
# Равносметките (финиш, междинна, досега) са СНИМКА на едно и също нещо в
# различни моменти — там 3 е точно. Обзорът е ИНКРЕМЕНТАЛЕН: всяко пускане
# изрежда мачовете, отсъдени В НЕГО, тоест ново съдържание по устройство.
# С таван 3 пет пускания с нови присъди дадоха съобщения само на първите три —
# четвъртата вълна резултати изчезваше. Затова тук таванът НЕ е мярка за
# приличие, а горна граница срещу подивял цикъл: реалният таван е 2 крона + 4
# будения = 6 пускания на ден, значи 8 не бие никога, но спира безкрайното.
RAVN_TAVAN_OBZOR = _cyalo("SCORE_RAVN_TAVAN_OBZOR", 8, 1, 40)
# Колко дни назад се помнят марките. По-широко от нуждата — забравена марка =
# повторено съобщение. Осем дни при ~10 марки на ден е нищожен файл.
RAVN_DNI = _cyalo("SCORE_RAVN_DNI", 8, 2, 60)

_CHAS_RE = re.compile(r"\d{1,2}:\d{2}")


def ravn_otpechatak(text):
    """Отпечатък на равносметката БЕЗ часа в първия ред."""
    redove = str(text if text is not None else "").split(chr(10))
    redove[0] = _CHAS_RE.sub("", redove[0])
    return hashlib.sha1(chr(10).join(redove).encode("utf-8")).hexdigest()[:12]


def ravn_klyuch(den, vid, adres, text):
    """„2026-08-25|finish|staya|ab12cd34ef56“ — денят е ПЪРВ, за да се реже."""
    return "|".join([str(den), str(vid), str(adres), ravn_otpechatak(text)])


def ravn_marki(sast):
    m = (sast or {}).get("ravnosmetki")
    return m if isinstance(m, dict) else {}


def ravn_tavan(vid):
    """Таванът по вид. Обзорът е инкрементален — виж коментара горе."""
    return RAVN_TAVAN_OBZOR if str(vid) == "obzor" else RAVN_TAVAN


def ravn_reshi(sast, den, vid, adres, text, tavan=None):
    """(праща_ли, ключ, пореден, защо). Чиста функция — без файлове и мрежа."""
    tavan = ravn_tavan(vid) if tavan is None else tavan
    kl = ravn_klyuch(den, vid, adres, text)
    marki = ravn_marki(sast)
    if kl in marki:
        return False, kl, 0, ("същият текст вече е пратен в "
                              + str(marki.get(kl)) + " — мълча")
    pref = "|".join([str(den), str(vid), str(adres)]) + "|"
    veche = sum(1 for k in marki if str(k).startswith(pref))
    if veche >= tavan:
        return False, kl, veche + 1, ("таван " + str(tavan) + " съобщения за "
                                      + pref[:-1] + " — мълча")
    return True, kl, veche + 1, ("ново съдържание, " + str(veche + 1)
                                 + "-то за деня")


def ravn_otbelezhi(sast, klyuch, sega):
    """Марката се слага САМО СЛЕД успешно пращане, не преди него.

    Обратното е дефектът, който днес седи в combo_done на оценителя (ред 3833
    маркира, ред 3846 праща): падне ли пращането, съобщението е изгубено
    завинаги, защото марката твърди, че е минало.
    """
    m = dict(ravn_marki(sast))
    m[str(klyuch)] = sega.strftime("%Y-%m-%d %H:%M")
    sast["ravnosmetki"] = m
    return sast


def izrezhi_stari(sast, sega, dni=None):
    """Реже марките и опитите, по-стари от dni дни. Тефтерът не расте вечно."""
    dni = RAVN_DNI if dni is None else dni
    granica = (sega - timedelta(days=dni)).strftime("%Y-%m-%d")
    sast["ravnosmetki"] = {k: v for k, v in ravn_marki(sast).items()
                           if str(k)[:10] >= granica}
    oc = (sast or {}).get("ocenitel")
    oc = oc if isinstance(oc, dict) else {}
    sast["ocenitel"] = {k: v for k, v in oc.items() if str(k)[:10] >= granica}
    return sast


# ═══════════════════════════════════════════════════════════════════════════
#  ⏰ БУДИЛНИК И ЗА ОЦЕНИТЕЛЯ (25.08.2026)
#
#  ПОВОДЪТ, ДОСЛОВНО: „СЧУПИ СЕ РЕЗУЛТАТИ И СТАТИСТИКА КАНАЛ СПРЯ ДА ГИ ДАВА“.
#
#  ИЗМЕРЕНО ПРЕЗ api.github.com в тази сесия — 56 планови ръна на score.yml от
#  29.07 до 25.08, всеки отнесен към НАЙ-БЛИЗКИЯ предишен план:
#
#    план 13:30 БГ  n=27  закъснение мин 15 · медиана 41 · 90-и 329 · макс 415
#    план 22:30 БГ  n=28  закъснение мин 14 · медиана 40 · 90-и 171 · макс 546
#    планове без НИТО ЕДИН рън: 0 от 55
#    ПРОВАЛИ: 15 от 56 (27%), сред тях три от последните пет
#
#  Оттук две неща, и двете различни от предсказателя:
#  1. Кронът на оценителя НЕ ПРОПУСКА — той ЗАКЪСНЯВА и ПАДА. Затова правилото
#     „пропуснат час“ (GRATIS_MIN) тук няма смисъл: часове няма, има два
#     прозореца на ден.
#  2. Собственикът иска резултати в 14:00 и 23:00. Медианата ги дава в 14:11 и
#     23:10, но 90-ият процентил — в 18:59 и 01:21. Будилник, който пали в
#     14:15 и 23:15, изпреварва крона в 37% (10 от 27) и 46% (13 от 28) от
#     дните и превръща обещания час в изпълнен.
#
#  ЗАЩО ТАВАНЪТ Е 2, А НЕ 10
#  Измерено в тази сесия: budilnik.py се пуска 41.1 пъти на ден (рутер 4.3 +
#  съпорт 36.9), медианна пауза 34 мин. Но СЪБУДИ-стъпката е само в router.yml
#  — тоест истинските поводи в един прозорец са ~1 на ден. Таван 2 стига за
#  „падна, пробвай пак“ и е горната граница на щетата, ако пазачът в scorer.py
#  още не е сложен: най-много две излишни равносметки на прозорец. Вдигни го с
#  BUDILNIK_OC_TAVAN, щом кръпката е в scorer.py.
#
#  🔴 ПЪТЯТ НАЗАД, ПРЕДИ ДЕЙСТВИЕТО: BUDILNIK_OCENITEL.
#  Празно или каквото и да е освен 1/true/yes/да = целият този будилник е
#  МЪРТЪВ: не решава, не пише в тефтера, а изходът ocenitel е винаги 0, тоест
#  стъпката в router.yml не се пуска. Изключването е една дума в един ред от
#  router.yml, без пипане на код. Точно затова е и по подразбиране ИЗКЛЮЧЕН:
#  support.yml също вика budilnik.py, но НЯМА стъпка за оценителя — вдигне ли
#  се знамето там, будилникът щеше да отбелязва опити, които никой не изпълнява,
#  и рутерът щеше да мълчи заради изчерпан таван. Пазач, който създава
#  пропусната тревога, вече ни е горял.
# ═══════════════════════════════════════════════════════════════════════════

OC_VKL = (os.environ.get("BUDILNIK_OCENITEL") or "").strip().lower() in (
    "1", "true", "yes", "да")


def _chas_min(ime, po_podrazbirane):
    """„14:15“ -> 855 минути от полунощ. Кривото пада на подразбиращото се."""
    def razbor(s):
        try:
            h, m = str(s).strip().split(":")
            n = int(h) * 60 + int(m)
        except (ValueError, TypeError, AttributeError):
            return None
        return n if 0 <= n < 1440 else None
    n = razbor(os.environ.get(ime) if ime else None)
    return n if n is not None else razbor(po_podrazbirane)


def _mm(n):
    return "%02d:%02d" % (int(n) // 60, int(n) % 60)


# Прозорците. Началата са 45 мин след плановете (13:30 и 22:30) — над двете
# медиани (41 и 40) и под 90-ите процентили (329 и 171). Краищата опират в
# самия оценител: scorer.py ред 3712-3713 праща „ДОКЪДЕ СМЕ“ при 11-19 ч и
# „ФИНИШ“ при 20-04 ч, а 05:00-10:59 е МЪРТВА ЗОНА, в която той не праща нищо.
# Будене в мъртвата зона е рън без съобщение — затова прозорците не я допират.
OC_OBED_OT = _chas_min("BUDILNIK_OC_OBED_OT", "14:15")
OC_OBED_DO = _chas_min("BUDILNIK_OC_OBED_DO", "19:59")
OC_VECHER_OT = _chas_min("BUDILNIK_OC_VECHER_OT", "23:15")
OC_VECHER_DO = _chas_min("BUDILNIK_OC_VECHER_DO", "04:59")
OC_TAVAN = _cyalo("BUDILNIK_OC_TAVAN", 2, 1, 8)
OC_POCHIVKA = _cyalo("BUDILNIK_OC_POCHIVKA", 45, 10, 240)
# Колко минути една вече излязла равносметка държи будилника затворен. Без
# горна граница тук пазачът щеше да пази и ОБРАТНАТА посока: равносметка,
# излязла в 23:20 с 12 неотсъдени мача, щеше да затвори прозореца до сутринта.
# След OC_SVEZHO минути будилникът пробва пак, а какво ще излезе решава
# пазачът по СЪДЪРЖАНИЕ: не се ли е сменило число — пак мълчи.
OC_SVEZHO = _cyalo("BUDILNIK_OC_SVEZHO", 90, 15, 600)
# Аварийно: буди дори без пазач в scorer.py. Стои изключено — виж портиера.
OC_BEZ_PAZACH = (os.environ.get("BUDILNIK_OC_BEZ_PAZACH") or "").strip() in (
    "1", "true", "yes", "да")
# Вратата, която кръпката за оценителя добавя. Търси се в ЖИВИЯ файл.
OC_IGLA = "prati_ravnosmetka"


def pazachat_e_v_scorera(put=None):
    """True / False / None. Има ли scorer.py пазач срещу повторена равносметка.

    🔴 ТРИ СТОЙНОСТИ, НЕ ДВЕ. „Не мога да прочета файла" НЕ Е „няма пазач":
    точно това сливане уби предишен пазач в този проект (pazach.py, сентинелът
    NEPITAN — „except: return []" направи аварията неразличима от мира).
    """
    p = put or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "scorer.py")
    try:
        with io.open(p, encoding="utf-8-sig") as f:
            return OC_IGLA in f.read()
    except Exception:                                        # noqa: BLE001
        return None


def oc_budi_li(sega, sast, scorer_put=None):
    """Портиерът + решението. Това вика main(); reshi_ocenitel остава чиста.

    🔴 ЗАЩО ПОРТИЕР, А НЕ ДОВЕРИЕ. Кръпката за scorer.py не се прилага от
    тази армия (файлът е зает). Тръгне ли будилникът пръв, всяко будене
    праща една и съща равносметка пак — 15 съобщения за пет пускания, 12
    дословни повторения, измерено. Затова тук се ПРОВЕРЯВА, не се вярва.
    Отказът е към ТИШИНА НА БУДИЛНИКА, не към тишина на бота: двата крона на
    score.yml си вървят, губи се само изпреварването.
    """
    if not OC_BEZ_PAZACH:
        ima = pazachat_e_v_scorera(scorer_put)
        if ima is not True:
            return False, ("scorer.py "
                           + ("не се чете" if ima is None
                              else "още няма пазач срещу повторена равносметка")
                           + " — НЕ будя, за да не залея канала (сложи "
                           + "krapka_scorer_pazach.py или вдигни "
                           + "BUDILNIK_OC_BEZ_PAZACH=1)")
    return reshi_ocenitel(sega, sast)


def oc_prozorec(sega):
    """(„obed“ | „vecher“ | „“, денят на равносметката).

    Денят НЕ е винаги календарният: след полунощ вечерният прозорец още
    принадлежи на ВЧЕРА — точно както scorer.py смята деня на ред 3714
    (now.hour < 5 -> вчера). Ключ по календарния ден щеше да пусне вчерашния
    финиш втори път в 00:30.
    """
    m = sega.hour * 60 + sega.minute
    if OC_OBED_OT <= m <= OC_OBED_DO:
        return "obed", sega.strftime("%Y-%m-%d")
    if m >= OC_VECHER_OT:
        return "vecher", sega.strftime("%Y-%m-%d")
    if m <= OC_VECHER_DO:
        return "vecher", (sega - timedelta(days=1)).strftime("%Y-%m-%d")
    return "", sega.strftime("%Y-%m-%d")


def oc_opiti(sast, den, vid):
    """(колко опита в този прозорец, кога е последният)."""
    oc = (sast or {}).get("ocenitel")
    oc = oc if isinstance(oc, dict) else {}
    z = oc.get(str(den) + "|" + str(vid))
    z = z if isinstance(z, dict) else {}
    n = z.get("opiti")
    return (n if isinstance(n, int) and n >= 0 else 0), _chas(z.get("posleden"))


def oc_zapishi_opit(sast, sega):
    """Отбелязва опит ПРЕДИ пускането — падне ли оценителят, пак се брои."""
    vid, den = oc_prozorec(sega)
    if not vid:
        return sast
    oc = (sast or {}).get("ocenitel")
    oc = dict(oc) if isinstance(oc, dict) else {}
    n, _ = oc_opiti(sast, den, vid)
    oc[den + "|" + vid] = {"opiti": n + 1,
                           "posleden": sega.strftime("%Y-%m-%d %H:%M")}
    sast["ocenitel"] = oc
    return sast


def reshi_ocenitel(sega, sast=None, tavan=None, pochivka=None, svezho=None):
    """(будим_ли, обяснение). Чиста функция — тества се без файлове и мрежа."""
    sast = {} if sast is None else sast
    tavan = OC_TAVAN if tavan is None else tavan
    pochivka = OC_POCHIVKA if pochivka is None else pochivka
    svezho = OC_SVEZHO if svezho is None else svezho

    vid, den = oc_prozorec(sega)
    if not vid:
        return False, ("извън прозорците на оценителя (" + _mm(OC_OBED_OT)
                       + "-" + _mm(OC_OBED_DO) + " и " + _mm(OC_VECHER_OT)
                       + "-" + _mm(OC_VECHER_DO) + "), сега е "
                       + sega.strftime("%H:%M"))

    # 1) Излязла ли е вече равносметката за ТОЗИ прозорец и колко отдавна.
    #    Обедният прозорец ражда „ДОКЪДЕ СМЕ“ (mezhdinna), вечерният — „ФИНИШ“.
    ravn_vid = "mezhdinna" if vid == "obed" else "finish"
    pref = den + "|" + ravn_vid + "|staya|"
    kogi = [_chas(v) for k, v in ravn_marki(sast).items()
            if str(k).startswith(pref)]
    kogi = [k for k in kogi if k is not None]
    if kogi:
        posl = max(kogi)
        ot_neya = int((sega - posl).total_seconds() // 60)
        if 0 <= ot_neya < svezho:
            return False, ("равносметката за " + den + " (" + vid
                           + ") излезе преди " + str(ot_neya)
                           + " мин — спя (свежо " + str(svezho) + " мин)")

    n, posleden = oc_opiti(sast, den, vid)
    if n >= tavan:
        return False, ("изчерпах " + str(tavan) + " опита за " + den + "|"
                       + vid + " — спя")
    if posleden is not None:
        ot_opita = int((sega - posleden).total_seconds() // 60)
        if 0 <= ot_opita < pochivka:
            return False, ("будих оценителя преди " + str(ot_opita)
                           + " мин — чакам (почивка " + str(pochivka) + " мин)")
    return True, ("прозорец " + vid + " за " + den + ", опит "
                  + str(n + 1) + " от " + str(tavan) + " — будя")


# 🔴 СЕНТИНЕЛ, ДОБАВЕН 12.08.2026 — ПОПРАВКА НА ОПАСЕН ДЕФЕКТ.
#
# Досега `opit=None` значеше ДВЕ различни неща: „не съм ти го подал, прочети
# го от диска" и „няма минал опит". Заради първото самопроверката четеше
# ЖИВИЯ budilnik_state.json — с часове, ЗАКОВАНИ за 12.08.
#
# Измерено: помете се всяка минута от денонощието — 179 минути, в които
# самопроверката пада. И понеже стъпката „Самопроверка на будилника" е ПРЕДИ
# самото будене, файлът повече не се променя: рутерът остава ТРАЙНО ЧЕРВЕН,
# опашката на Telegram не се чете, съпортът мълчи. Не до полунощ — завинаги.
#
# Сега: `opit=None` значи „няма минал опит"; дискът се чете само когато
# аргументът изобщо не е подаден. Чистата функция не докосва файлове.
_NEPODADEN = object()


def reshi(posleden, sega, ot=None, do=None, tavan=None, opit=_NEPODADEN,
          pochivka=None):
    """(будим_ли, обяснение). Чиста функция — тества се без файлове и мрежа."""
    ot = OT_CHAS if ot is None else ot
    do = DO_CHAS if do is None else do
    tavan = TAVAN_MIN if tavan is None else tavan

    if not (ot <= sega.hour <= do):
        return False, ("извън работните часове (" + str(ot) + "-" + str(do)
                       + "), сега е " + sega.strftime("%H:%M"))
    if posleden is None:
        # Тефтерът липсва или е нечетим. Това НЕ е повод за тишина: точно
        # тогава е най-вероятно предсказателят изобщо да не е тръгвал.
        budim, zashto = _s_pochivka(sega, -1, tavan, opit, pochivka)
        return budim, (zashto if not budim
                       else "тефтерът не се чете — будя, вместо да гадая")
    if posleden > sega + timedelta(minutes=5):
        # Час от бъдещето значи объркана зона или ръчно пипнат файл.
        return True, ("последното пускане е в бъдещето ("
                      + posleden.strftime("%H:%M") + ") — будя")
    minuti = int((sega - posleden).total_seconds() // 60)
    # ПРОПУСНАТ ЧАС — виж дългото обяснение при GRATIS_MIN.
    # Гледаме календарния час, не разстоянието: пускане в 08:58 и „сега 09:14"
    # са само 16 минути, но часът 09 вече е пропуснат.
    if (sega.minute >= GRATIS_MIN
            and (posleden.date(), posleden.hour) != (sega.date(), sega.hour)):
        budim, zashto = _s_pochivka(sega, minuti, tavan, opit, pochivka)
        return budim, (zashto if not budim
                       else ("часът " + sega.strftime("%H") + " е пропуснат ("
                             + str(sega.minute) + " мин след началото му, "
                             + "последното пускане е в "
                             + posleden.strftime("%H:%M") + ") — будя"))
    if minuti <= tavan:
        return False, ("последното пускане е преди " + str(minuti)
                       + " мин — в срок, спя")
    return _s_pochivka(sega, minuti, tavan, opit, pochivka)


def _s_pochivka(sega, minuti, tavan, opit, pochivka):
    """Дупката е реална. Но будили ли сме наскоро без резултат?"""
    pochivka = POCHIVKA_MIN if pochivka is None else pochivka
    if opit is _NEPODADEN:
        opit = posleden_opit()
    if opit is not None:
        ot_opita = int((sega - opit).total_seconds() // 60)
        if 0 <= ot_opita < pochivka:
            return False, ("дупка от " + str(minuti) + " мин, но будих преди "
                           + str(ot_opita) + " мин — чакам ("
                           + "почивка " + str(pochivka) + " мин)")
    return True, ("последното пускане е преди " + str(minuti)
                  + " мин (таван " + str(tavan) + ") — будя")


def selftest():
    # ═══════════════════════════════════════════════════════════════════════
    #  🔴 ТРИ СЪСТОЯНИЯ, НЕ ДВЕ (02.09.2026 — ИЗМЕРЕНО НА ЖИВО).
    #
    #  Стъпката «Самопроверка на будилника и предсказателя» (router.yml:75-78)
    #  е БЛОКИРАЩА: падне ли, следващите стъпки се ПРЕСКАЧАТ. Измерено през
    #  api.github.com в тази сесия, рутерът на 27.08 в 23:10 / 23:15 / 23:20 /
    #  23:25:
    #      Самопроверка на будилника и предсказателя  →  failure
    #      Проспа ли предсказателя или оценителя      →  skipped
    #      Събуди предсказателя                       →  skipped
    #      Събуди оценителя                           →  skipped
    #  Тоест едно червено тук спира ЧАСОВНИКА на целия бот. Следата в тефтера:
    #  вечерните прозорци 27, 28 и 29.08 нямат НИТО ЕДИН опит (3 от 7 нощи), а
    #  равносметките за тези дни са само по една — от закъснелия крон в 23:37,
    #  00:12 и 00:52. За сравнение: в нощите с жив будилник марките са точно в
    #  23:15 и 00:45, тоест двата му опита.
    #
    #  Затова разликата:
    #    · счупено  = дефект В ТОЗИ ФАЙЛ или РАЗЧЕТЕНО разминаване с друг —
    #                 изход 1, стъпката пада, и това е правилно;
    #    · НЕСВЕРЕНО = чужд файл не се чете или котвата в него е сменена —
    #                 ⚠ в дневника, изход 0. Чужд refactor не бива да спира
    #                 часовника; същият сентинел вече пази pazachat_e_v_scorera
    #                 («не мога да прочета» НЕ Е «няма пазач»).
    #
    #  Пазачът срещу украса: сверките се БРОЯТ. Изчезне ли цял блок, броят на
    #  ОПИТАНИТЕ пада и проверката по-долу гърми — «0 несверени» вече не може
    #  да значи «0 погледнати».
    # ═══════════════════════════════════════════════════════════════════════
    ok, bad, warn = 0, [], []
    sverki = {"opitani": 0}

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    def sverka_zapochva():
        sverki["opitani"] += 1

    def nesverimo(prichina):
        warn.append(prichina)

    d = lambda h, m: datetime(2026, 8, 12, h, m, tzinfo=SOFIA)     # noqa: E731

    # --- решението
    check("в срок = не будим", reshi(d(12, 0), d(12, 30), opit=None)[0] is False)
    # 🔴 ОБЪРНАТА, НЕ ИЗТРИТА (21.08.2026). Пазеше СТАРОТО поведение: дупка
    # от 80 минути е под тавана 90, значи спим. Но пускане в 12:00 и „сега
    # 13:20" значи, че кронът за 13 часа е трябвало да гръмне до 13:12 и НЕ
    # е гръмнал. Чакането още 10 минути не носи нищо освен тишина.
    check("пропуснат час буди, макар дупката да е под тавана",
          reshi(d(12, 0), d(13, 20), opit=None)[0] is True)
    check("но НЕ преди гратиса — часът още може да дойде",
          reshi(d(12, 0), d(13, 5), opit=None)[0] is False)
    check("прескочен час буди", reshi(d(12, 0), d(13, 40), opit=None)[0] is True)
    check("два прескочени часа будят", reshi(d(10, 0), d(12, 30), opit=None)[0] is True)

    # 🔴 ПРОПУСНАТИЯТ ЧАС — новото правило (21.08.2026).
    check("същият час, малка дупка = спим",
          reshi(d(12, 5), d(12, 40), opit=None)[0] is False)
    check("нов час, но преди гратиса = спим",
          reshi(d(12, 50), d(13, 3), opit=None)[0] is False)
    check("нов час след гратиса = будим",
          reshi(d(12, 50), d(13, 20), opit=None)[0] is True)
    check("причината казва КОЙ час е пропуснат",
          "13" in reshi(d(12, 50), d(13, 20), opit=None)[1]
          and "пропуснат" in reshi(d(12, 50), d(13, 20), opit=None)[1])
    check("извън работните часове НЕ будим дори при пропуснат час",
          reshi(d(3, 0), d(4, 30), opit=None)[0]
          is (OT_CHAS <= 4 <= DO_CHAS))
    check("почивката бие пропуснатия час",
          reshi(d(12, 50), d(13, 20), opit=d(13, 10))[0] is False)
    check("гратисът е разумен", 3 <= GRATIS_MIN <= 20)
    # Денят се сменя: 23:xx -> 00:xx е нов час, но е и извън часовете.
    check("смяна на деня не подлудява правилото",
          reshi(datetime(2026, 8, 12, 23, 50, tzinfo=SOFIA),
                datetime(2026, 8, 13, 9, 30, tzinfo=SOFIA), opit=None)[0] is True)
    check("извън прозореца НЕ будим дори при огромна дупка",
          reshi(d(12, 0), datetime(2026, 8, 13, 3, 0, tzinfo=SOFIA),
                opit=None)[0] is (OT_CHAS <= 3 <= DO_CHAS))
    # 🔴 ЧАСОВЕТЕ СЛЕДВАТ КЛЮЧОВЕТЕ (02.09.2026). Тези проверки заковаваха
    # 07:59 / 23:00 / 03:00 — тоест денонощният режим ги чупеше, без нито
    # един истински дефект. Сега питат ПРАВИЛОТО: буди се в работния час,
    # не се буди извън него, каквито и да са границите.
    _b_izvun = None
    for _hh in range(24):
        if not (OT_CHAS <= _hh <= DO_CHAS):
            _b_izvun = _hh
            break
    check("в 07:59 НЕ будим",
          reshi(d(4, 0), d(7, 59), opit=None)[0] is (OT_CHAS <= 7))
    check("в 08:00 будим", reshi(datetime(2026, 8, 11, 22, 0, tzinfo=SOFIA),
                                 d(8, 0), opit=None)[0] is True)
    check("в 22:00 още будим", reshi(d(19, 0), d(22, 0), opit=None)[0] is True)
    check("в 23:00 будим само ако е в прозореца",
          reshi(d(19, 0), d(23, 0), opit=None)[0] is (DO_CHAS >= 23))
    check("липсващ тефтер буди", reshi(None, d(12, 0), opit=None)[0] is True)
    check("липсващ тефтер буди само в работен час",
          reshi(None, d(3, 0), opit=None)[0] is (OT_CHAS <= 3 <= DO_CHAS))
    # И правилото в чист вид: извън прозореца НЕ се буди, какъвто и да е той.
    if _b_izvun is not None:
        check("извън прозореца не се буди изобщо",
              reshi(None, d(_b_izvun, 0), opit=None)[0] is False)
    else:
        check("при денонощен режим няма час без будене",
              OT_CHAS == 0 and DO_CHAS == 23)
    check("час от бъдещето буди", reshi(d(15, 0), d(12, 0), opit=None)[0] is True)
    check("една минута напред НЕ е бъдеще", reshi(d(12, 1), d(12, 0), opit=None)[0] is False)

    # Обяснението винаги казва нещо, и то на български.
    for p, s in ((d(12, 0), d(12, 30)), (d(12, 0), d(14, 0)), (None, d(12, 0))):
        _, zashto = reshi(p, s, opit=None)
        check("обяснението е непразно", len(zashto) > 10)

    # --- границата е ТОЧНО на тавана, не около него
    # 🔴 И ТАЗИ Е ОБЪРНАТА по същата причина: 13:30 е половин час след като
    # часът 13 е пропуснат. Границата „точно на тавана" вече не решава сама.
    check("точно на тавана, но с пропуснат час — будим",
          reshi(d(12, 0), d(13, 30), opit=None)[0] is True)
    check("в СЪЩИЯ час таванът пак е границата",
          reshi(d(12, 0), d(12, 59), opit=None)[0] is False)
    check("една минута над тавана буди", reshi(d(12, 0), d(13, 31), opit=None)[0] is True)

    # --- четенето на тефтера
    check("боклук вместо тефтер не гърми", posleden_run("нямаго.json") is None)
    tmp = os.path.join(os.environ.get("TEMP") or ".", "_budilnik_test.json")
    try:
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump({"diag": {"koga": "2026-08-12 09:15"}}, f)
        r = posleden_run(tmp)
        check("часът се чете от тефтера", r is not None and r.hour == 9 and r.minute == 15)
        check("часът е в софийска зона", r is not None and r.utcoffset() is not None)
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump({"diag": {}}, f)
        check("празен diag не гърми", posleden_run(tmp) is None)
        with io.open(tmp, "w", encoding="utf-8") as f:
            f.write("това не е JSON")
        check("счупен JSON не гърми", posleden_run(tmp) is None)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

    # --- часовете съвпадат с тези на предсказателя. Разминат ли се, будилникът
    #     или ще мълчи в работен час, или ще буди в забранен.
    sverka_zapochva()
    src = None
    try:
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "predictor.py"), encoding="utf-8-sig") as f:
            src = f.read()
    except Exception as e:                                   # noqa: BLE001
        nesverimo("часовете с predictor.py: " + str(e)[:50])
    if src is not None:
        # 🔴 СВЕРЯВА СЕ ПО КЛЮЧОВЕТЕ, НЕ ПО ТЕКСТА (02.09.2026).
        # Старата проверка търсеше низ в predictor.py и гръмна в деня, в
        # който часовете станаха подвижни. Сега пита за ПРАВИЛОТО.
        # Котвата пак е текст, затова липсата ѝ е ⚠, а не червено.
        if not ("_PROZORETS" in src and "QUIET_TO <= h <= QUIET_FROM" in src):
            nesverimo("не намирам правилото за прозореца в predictor.py")
        check("будилникът почва когато и предсказателят", OT_CHAS == _QT)
        check("будилникът спира когато и предсказателят",
              DO_CHAS == _granici(_QT, _QF)[1])
        check("при денонощен режим будилникът също е денонощен",
              (OT_CHAS == 0 and DO_CHAS == 23) if _PALEN else True)

    # --- правилото за границите, проверено САМО, и то без препис
    check("денонощен прозорец дава денонощен будилник", _granici(0, 23) == (0, 23))
    check("стандартният прозорец спира час по-рано", _granici(8, 23) == (8, 22))
    check("подвижното начало се пренася", _granici(3, 21) == (3, 20))
    check("гратисът е САМО при непълен ден", _granici(0, 22) == (0, 21))

    # --- СПИРАЧКАТА. Без нея паднал предсказател се буди на всеки 10 минути
    # до безкрай. Тества се с изрично подаден „последен опит", за да не пипа
    # файлове: чиста функция, чист тест.
    check("скорошен опит спира будене",
          reshi(d(12, 0), d(14, 0), opit=d(13, 50))[0] is False)
    check("стар опит НЕ спира будене",
          reshi(d(12, 0), d(14, 0), opit=d(13, 0))[0] is True)
    check("точно на почивката вече будим",
          reshi(d(12, 0), d(14, 0), opit=d(13, 30))[0] is True)
    check("без нито един опит будим",
          reshi(d(12, 0), d(14, 0), opit=None, pochivka=30)[0] is True)
    check("опит от бъдещето не спира будене",
          reshi(d(12, 0), d(14, 0), opit=d(15, 0))[0] is True)
    check("спирачката важи и при липсващ тефтер",
          reshi(None, d(14, 0), opit=d(13, 50))[0] is False)
    check("обяснението казва, че сме будили",
          "будих преди" in reshi(d(12, 0), d(14, 0), opit=d(13, 50))[1])
    # Спирачката НЕ бива да спира, когато няма дупка — тогава причината е
    # „в срок", не „почивка". Иначе логът щеше да лъже защо мълчим.
    check("в срок не се обяснява с почивка",
          "будих преди" not in reshi(d(12, 0), d(12, 30), opit=d(12, 25))[1])

    # --- записът на опита
    tmp2 = os.path.join(os.environ.get("TEMP") or ".", "_budilnik_opit.json")
    try:
        check("опитът се записва", zapishi_opit(d(14, 0), tmp2) is True)
        r2 = posleden_opit(tmp2)
        check("записаният опит се чете", r2 is not None and r2.hour == 14)
        with io.open(tmp2, "w", encoding="utf-8") as f:
            f.write("боклук")
        check("счупен файл на опита не гърми", posleden_opit(tmp2) is None)
    finally:
        try:
            os.remove(tmp2)
        except OSError:
            pass

    # 🔴 ПАЗАЧ СРЕЩУ ВЪРНАТИЯ ДЕФЕКТ. Самопроверката не бива да зависи от
    # живия budilnik_state.json. Подхвърляме отровен файл и искаме СЪЩИЯ
    # резултат. Върне ли се четенето от диска, тази проверка пада.
    _star = BUD_STATE
    try:
        _otr = os.path.join(os.environ.get("TEMP") or ".", "_budilnik_otrova.json")
        with io.open(_otr, "w", encoding="utf-8") as f:
            json.dump({"posleden_opit": d(13, 20).strftime("%Y-%m-%d %H:%M")}, f)
        globals()["BUD_STATE"] = _otr
        check("отровен тефтер НЕ мени решението (прескочен час)",
              reshi(d(12, 0), d(13, 40), opit=None)[0] is True)
        check("отровен тефтер НЕ мени решението (в срок)",
              reshi(d(12, 0), d(12, 30), opit=None)[0] is False)
    finally:
        globals()["BUD_STATE"] = _star
        try:
            os.remove(_otr)
        except OSError:
            pass

    # ═══════════════════════════════════════════════════════════════════
    #  🛡️ ПАЗАЧЪТ И БУДИЛНИКЪТ НА ОЦЕНИТЕЛЯ (25.08.2026)
    #
    #  Всяка проверка тук пази ЕДНА от двете посоки:
    #    ✖ да НЕ излезе една и съща равносметка два пъти
    #    ✖ да НЕ млъкне завинаги, ако след ранното съобщение дойдат резултати
    #  Четирите изрично надписани МУТАЦИИ доказват, че проверките имат зъби:
    #  всяка счупва по едно от правилата и иска СЧУПЕНИЯТ да се провали там,
    #  където истинският минава. Проверка, оцеляла собствената си мутация, е
    #  украса — това вече ни е горяло.
    # ═══════════════════════════════════════════════════════════════════════
    _ok_predi_pazacha = ok

    # --- тефтерът: чете се без гърмеж, пише се БЕЗ да трие чуждото
    tmp3 = os.path.join(os.environ.get("TEMP") or ".", "_budilnik_sast.json")
    try:
        try:
            os.remove(tmp3)
        except OSError:
            pass
        check("липсващ тефтер дава празен речник", cheti_sast(tmp3) == {})
        with io.open(tmp3, "w", encoding="utf-8") as f:
            f.write("това не е JSON")
        check("боклук вместо тефтер дава празен речник", cheti_sast(tmp3) == {})
        with io.open(tmp3, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)
        check("списък вместо речник дава празен речник", cheti_sast(tmp3) == {})
        check("тефтерът се записва",
              pishi_sast({"ravnosmetki": {"2026-08-25|finish|staya|aa": "x"},
                          "ocenitel": {"2026-08-25|vecher": {"opiti": 1}}},
                         tmp3) is True)
        check("записаното се чете обратно",
              cheti_sast(tmp3).get("ravnosmetki", {}).get(
                  "2026-08-25|finish|staya|aa") == "x")

        # 🔴 МУТАЦИЯ 1 — ПРЕЗАПИСВАЩИЯТ ЗАПИС.
        # Старият zapishi_opit слагаше ЦЯЛ НОВ речник върху стария. Тук се
        # пуска точно той и се иска марките да ИЗЧЕЗНАТ, докато новият ги пази.
        def _star_zapishi_opit(sega, put):
            with io.open(put, "w", encoding="utf-8") as g:
                json.dump({"posleden_opit": sega.strftime("%Y-%m-%d %H:%M")},
                          g, ensure_ascii=False)
            return True
        _star_zapishi_opit(d(14, 0), tmp3)
        check("МУТАЦИЯ: презаписващият запис ТРИЕ марките",
              cheti_sast(tmp3).get("ravnosmetki") in (None, {}))
        pishi_sast({"ravnosmetki": {"2026-08-25|finish|staya|aa": "x"},
                    "ocenitel": {"2026-08-25|vecher": {"opiti": 1}}}, tmp3)
        check("истинският запис НЕ трие марките",
              zapishi_opit(d(14, 0), tmp3) is True
              and cheti_sast(tmp3).get("ravnosmetki", {}).get(
                  "2026-08-25|finish|staya|aa") == "x")
        check("и все пак записва часа на опита",
              posleden_opit(tmp3) is not None and posleden_opit(tmp3).hour == 14)
        check("и не трие опитите за оценителя",
              cheti_sast(tmp3).get("ocenitel", {}).get(
                  "2026-08-25|vecher", {}).get("opiti") == 1)
    finally:
        try:
            os.remove(tmp3)
        except OSError:
            pass

    # --- отпечатъкът: часът в ПЪРВИЯ ред не е съдържание, всичко друго е
    _t1 = "\U0001f552 <b>ДОКЪДЕ СМЕ ДНЕС</b> · вт 25.08, 14:07" + chr(10) + "От 40 пуснати днес 9 имат резултат."
    _t2 = "\U0001f552 <b>ДОКЪДЕ СМЕ ДНЕС</b> · вт 25.08, 18:41" + chr(10) + "От 40 пуснати днес 9 имат резултат."
    _t3 = "\U0001f552 <b>ДОКЪДЕ СМЕ ДНЕС</b> · вт 25.08, 14:07" + chr(10) + "От 40 пуснати днес 21 имат резултат."
    _t4 = "\U0001f3c1 <b>ФИНИШ НА ДЕНЯ</b> · вт 25.08" + chr(10) + "мач в 20:30" + chr(10) + "край"
    _t5 = "\U0001f3c1 <b>ФИНИШ НА ДЕНЯ</b> · вт 25.08" + chr(10) + "мач в 21:30" + chr(10) + "край"
    check("същият текст дава същия отпечатък",
          ravn_otpechatak(_t1) == ravn_otpechatak(_t1))
    check("само сменен ЧАС в заглавието НЕ е ново съдържание",
          ravn_otpechatak(_t1) == ravn_otpechatak(_t2))
    check("сменено ЧИСЛО е ново съдържание",
          ravn_otpechatak(_t1) != ravn_otpechatak(_t3))
    # Ножът реже САМО първия ред. Иначе два обзора, различаващи се единствено
    # по началните часове на мачовете, щяха да се слеят и вторият да изчезне.
    check("час на ВТОРИ ред си остава съдържание",
          ravn_otpechatak(_t4) != ravn_otpechatak(_t5))
    check("празен текст не гърми", len(ravn_otpechatak("")) == 12)
    check("None не гърми", len(ravn_otpechatak(None)) == 12)
    check("отпечатъкът е кратък и стабилен",
          ravn_otpechatak(_t1) == ravn_otpechatak(_t1)[:12])
    check("денят стои ПРЪВ в ключа, за да се реже по него",
          ravn_klyuch("2026-08-25", "finish", "staya", _t4)[:10] == "2026-08-25")

    # --- ПОСОКА 1: една и съща равносметка НЕ излиза два пъти
    _s = {}
    _prat, _kl, _por, _z = ravn_reshi(_s, "2026-08-25", "finish", "staya", _t4)
    check("първият път равносметката излиза", _prat is True and _por == 1)
    ravn_otbelezhi(_s, _kl, d(23, 20))
    _prat2, _kl2, _, _z2 = ravn_reshi(_s, "2026-08-25", "finish", "staya", _t4)
    check("вторият път СЪЩИЯТ текст мълчи", _prat2 is False)
    check("ключът е същият", _kl2 == _kl)
    check("обяснението казва, че вече е пратено", "вече е пратен" in _z2)
    check("марката носи часа на пращането", _s["ravnosmetki"][_kl][:10] == "2026-08-12")

    # Стаята и каналът са ОТДЕЛНИ адреси: мине ли стаята, а каналът не, една
    # обща марка щеше да погребе канала завинаги.
    check("марката за стаята НЕ запушва канала",
          ravn_reshi(_s, "2026-08-25", "finish", "kanal", _t4)[0] is True)
    check("марката за днес НЕ запушва утре",
          ravn_reshi(_s, "2026-08-26", "finish", "staya", _t4)[0] is True)
    check("марката за финиша НЕ запушва ДОСЕГА ОБЩО",
          ravn_reshi(_s, "2026-08-25", "dosega", "staya", _t4)[0] is True)

    # --- ПОСОКА 2: пазачът НЕ млъква завинаги, щом числото се смени
    _prat3, _kl3, _por3, _z3 = ravn_reshi(_s, "2026-08-25", "finish", "staya", _t5)
    check("сменено съдържание пак излиза", _prat3 is True)
    check("и е второто за деня", _por3 == 2)
    check("новият ключ е различен от стария", _kl3 != _kl)
    ravn_otbelezhi(_s, _kl3, d(23, 50))
    _t6 = _t5 + chr(10) + "още един ред"
    _prat4, _kl4, _por4, _ = ravn_reshi(_s, "2026-08-25", "finish", "staya", _t6)
    check("трето различно съдържание още излиза", _prat4 is True and _por4 == 3)
    ravn_otbelezhi(_s, _kl4, d(23, 55))
    _t7 = _t6 + chr(10) + "и още един"
    check("ЧЕТВЪРТОТО вече е спряно от тавана",
          ravn_reshi(_s, "2026-08-25", "finish", "staya", _t7)[0] is False)
    check("причината е таванът, не повторение",
          "таван" in ravn_reshi(_s, "2026-08-25", "finish", "staya", _t7)[3])
    check("но таванът важи ЗА ТОЗИ адрес, не за канала",
          ravn_reshi(_s, "2026-08-25", "finish", "kanal", _t7)[0] is True)
    # Повторенията НЕ ядат от тавана — иначе три опита да се прати един и същ
    # текст щяха да изчерпят правото на РЕАЛНО обновяване.
    _s2 = {}
    _p, _k, _, _ = ravn_reshi(_s2, "2026-08-25", "finish", "staya", _t4)
    for _ in range(5):
        ravn_otbelezhi(_s2, _k, d(23, 20))
    check("петкратното маркиране на СЪЩИЯ текст е една марка",
          len(ravn_marki(_s2)) == 1)
    check("тоест таванът не е изяден от повторения",
          ravn_reshi(_s2, "2026-08-25", "finish", "staya", _t5)[0] is True)

    # 🔴 МУТАЦИЯ 2 — ПАЗАЧ БЕЗ ПАМЕТ (маха се проверката „ключът вече е тук“).
    def _bez_pamet(sast, den, vid, adres, text):
        return True
    check("МУТАЦИЯ: пазач без памет праща същия текст пак",
          _bez_pamet(_s, "2026-08-25", "finish", "staya", _t4) is True
          and ravn_reshi(_s, "2026-08-25", "finish", "staya", _t4)[0] is False)

    # 🔴 МУТАЦИЯ 3 — КЛЮЧ БЕЗ ОТПЕЧАТЪК (тоест „веднъж на ден“).
    # Точно това е половиният пазач: спира дубъла и създава ПРОПУСНАТОТО.
    def _sliap_reshi(sast, den, vid, adres, text):
        return ("|".join([str(den), str(vid), str(adres)])
                not in [str(k).rsplit("|", 1)[0] for k in ravn_marki(sast)])
    check("МУТАЦИЯ: ключ без отпечатък онемява при сменено число",
          _sliap_reshi(_s2, "2026-08-25", "finish", "staya", _t5) is False
          and ravn_reshi(_s2, "2026-08-25", "finish", "staya", _t5)[0] is True)

    # Таванът на ОБЗОРА е отделен и по-широк — иначе четвъртата вълна
    # резултати за деня изчезва. Мерено на живо върху кръпнатия оценител.
    check("обзорът има свой, по-широк таван", ravn_tavan("obzor") > ravn_tavan("finish"))
    check("равносметките делят общия таван",
          ravn_tavan("finish") == ravn_tavan("dosega") == ravn_tavan("mezhdinna")
          == RAVN_TAVAN)
    _s6 = {}
    _iz = 0
    for _i in range(RAVN_TAVAN_OBZOR + 2):
        _txt = "📊 <b>ОБЗОР</b> · вт 25.08, 20:00" + chr(10) + "мач номер " + str(_i)
        _p6, _k6, _, _ = ravn_reshi(_s6, "2026-08-25", "obzor", "staya", _txt)
        if _p6:
            _iz += 1
            ravn_otbelezhi(_s6, _k6, d(20, 0))
    check("обзорът стига до своя таван, не до тесния", _iz == RAVN_TAVAN_OBZOR)
    check("и таванът на обзора е поне колкото пусканията за ден (6)",
          RAVN_TAVAN_OBZOR >= 6)

    # --- рязането: тефтерът не расте вечно, но и не забравя вчера
    _s3 = {"ravnosmetki": {"2026-08-25|finish|staya|aa": "2026-08-25 23:20",
                           "2026-08-01|finish|staya|bb": "2026-08-01 23:20",
                           "2026-08-24|dosega|staya|cc": "2026-08-24 23:20"},
           "ocenitel": {"2026-08-25|vecher": {"opiti": 1},
                        "2026-08-01|obed": {"opiti": 2}}}
    izrezhi_stari(_s3, datetime(2026, 8, 25, 23, 59, tzinfo=SOFIA), dni=8)
    check("старата марка е отрязана", "2026-08-01|finish|staya|bb" not in ravn_marki(_s3))
    check("вчерашната марка ОСТАВА", "2026-08-24|dosega|staya|cc" in ravn_marki(_s3))
    check("днешната марка остава", "2026-08-25|finish|staya|aa" in ravn_marki(_s3))
    check("режат се и опитите на оценителя",
          "2026-08-01|obed" not in _s3["ocenitel"]
          and "2026-08-25|vecher" in _s3["ocenitel"])
    check("рязане на празен тефтер не гърми",
          izrezhi_stari({}, d(12, 0)) is not None)
    check("боклук в марките не гърми",
          ravn_marki({"ravnosmetki": "не съм речник"}) == {})

    # --- прозорците на оценителя
    check("14:15 е в обедния прозорец", oc_prozorec(d(14, 15))[0] == "obed")
    check("14:14 още не е", oc_prozorec(d(14, 14))[0] == "")
    check("19:59 е последната минута на обеда", oc_prozorec(d(19, 59))[0] == "obed")
    check("20:00 не е в никой прозорец", oc_prozorec(d(20, 0))[0] == "")
    check("23:15 е във вечерния", oc_prozorec(d(23, 15))[0] == "vecher")
    check("23:14 още не е", oc_prozorec(d(23, 14))[0] == "")
    check("04:59 още е вечерният", oc_prozorec(d(4, 59))[0] == "vecher")
    check("05:00 вече не е — там оценителят не праща НИЩО",
          oc_prozorec(d(5, 0))[0] == "")
    check("мъртвата зона 05:00-10:59 не е прозорец",
          all(oc_prozorec(d(h, 30))[0] == "" for h in (5, 6, 7, 8, 9, 10)))
    check("12:00 не е прозорец — кронът още не е закъснял",
          oc_prozorec(d(12, 0))[0] == "")
    check("21:00 не е прозорец", oc_prozorec(d(21, 0))[0] == "")
    # 🔴 ДЕНЯТ СЛЕД ПОЛУНОЩ Е ВЧЕРАШНИЯТ — както го смята и самият оценител.
    check("в 00:30 денят е ВЧЕРАШНИЯТ",
          oc_prozorec(datetime(2026, 8, 13, 0, 30, tzinfo=SOFIA))[1] == "2026-08-12")
    check("в 23:30 денят е днешният", oc_prozorec(d(23, 30))[1] == "2026-08-12")
    check("23:30 и 00:30 са ЕДИН И СЪЩ прозорец",
          oc_prozorec(d(23, 30)) == oc_prozorec(
              datetime(2026, 8, 13, 0, 30, tzinfo=SOFIA)))
    check("прозорците не се застъпват",
          OC_VECHER_DO < OC_OBED_OT <= OC_OBED_DO < OC_VECHER_OT)
    check("обедният свършва преди вечерта на оценителя", OC_OBED_DO < 20 * 60)
    check("вечерният започва след 20:00", OC_VECHER_OT >= 20 * 60)
    check("кривият час пада на подразбиращия се",
          _chas_min("НЯМА_ТАКАВА_ПРОМЕНЛИВА", "14:15") == 855)
    check("часът се чете като минути", _mm(855) == "14:15" and _mm(299) == "04:59")

    # --- решението будим ли оценителя
    check("празен тефтер в прозореца буди", reshi_ocenitel(d(14, 20), {})[0] is True)
    check("извън прозореца не буди", reshi_ocenitel(d(12, 0), {})[0] is False)
    check("причината назовава прозорците",
          "прозорците на оценителя" in reshi_ocenitel(d(12, 0), {})[1])
    _s4 = {}
    oc_zapishi_opit(_s4, d(14, 20))
    check("опитът се брои", oc_opiti(_s4, "2026-08-12", "obed")[0] == 1)
    check("почивката спира второто будене веднага",
          reshi_ocenitel(d(14, 30), _s4)[0] is False)
    check("причината е почивката",
          "будих оценителя преди" in reshi_ocenitel(d(14, 30), _s4)[1])
    check("след почивката будим пак", reshi_ocenitel(d(15, 10), _s4)[0] is True)
    oc_zapishi_opit(_s4, d(15, 10))
    check("вторият опит се брои", oc_opiti(_s4, "2026-08-12", "obed")[0] == 2)
    check("таванът 2 спира третия", reshi_ocenitel(d(16, 30), _s4)[0] is False)
    check("причината е изчерпан таван",
          "изчерпах" in reshi_ocenitel(d(16, 30), _s4)[1])
    check("но вечерният прозорец е СВОБОДЕН — таванът е на прозорец",
          reshi_ocenitel(d(23, 30), _s4)[0] is True)
    check("опит извън прозорец не се записва",
          oc_zapishi_opit({}, d(12, 0)) == {})
    check("боклук в опитите не гърми",
          oc_opiti({"ocenitel": "не съм речник"}, "2026-08-12", "obed") == (0, None))
    check("боклук в брояча не гърми",
          oc_opiti({"ocenitel": {"2026-08-12|obed": {"opiti": "три"}}},
                   "2026-08-12", "obed")[0] == 0)

    # --- ВРЪЗКАТА ПАЗАЧ ↔ БУДИЛНИК, И ТЯ В ДВЕТЕ ПОСОКИ
    _s5 = {"ravnosmetki": {"2026-08-12|finish|staya|aa": "2026-08-12 23:20"}}
    check("прясна равносметка спира буденето",
          reshi_ocenitel(d(23, 40), _s5)[0] is False)
    check("причината е излязлата равносметка",
          "излезе преди" in reshi_ocenitel(d(23, 40), _s5)[1])
    # 🔴 МУТАЦИЯ 4 — МАРКАТА КАТО ВЕЧНА СПИРАЧКА.
    # Пазач срещу ФАЛШИВА тревога, който създава ПРОПУСНАТА: равносметка,
    # излязла в 23:20 с неотсъдени мачове, затваря прозореца до сутринта.
    check("МУТАЦИЯ: вечна спирачка не буди никога",
          reshi_ocenitel(datetime(2026, 8, 13, 2, 0, tzinfo=SOFIA), _s5,
                         svezho=100000)[0] is False)
    check("истинската спирачка пуска пак след като изстине",
          reshi_ocenitel(datetime(2026, 8, 13, 2, 0, tzinfo=SOFIA), _s5)[0] is True)
    check("обедната равносметка НЕ спира вечерния прозорец",
          reshi_ocenitel(d(23, 40),
                         {"ravnosmetki": {"2026-08-12|mezhdinna|staya|aa":
                                          "2026-08-12 23:20"}})[0] is True)
    check("равносметка САМО в канала не спира буденето (стаята е мярката)",
          reshi_ocenitel(d(23, 40),
                         {"ravnosmetki": {"2026-08-12|finish|kanal|aa":
                                          "2026-08-12 23:20"}})[0] is True)

    # --- ПОРТИЕРЪТ: без пазач в scorer.py не се буди изобщо
    tmp4 = os.path.join(os.environ.get("TEMP") or ".", "_budilnik_scorer.py")
    try:
        with io.open(tmp4, "w", encoding="utf-8") as f:
            f.write("def prati_ravnosmetka(now, den, vid, text, k):\n    pass\n")
        check("пазачът се разпознава в scorer.py",
              pazachat_e_v_scorera(tmp4) is True)
        with io.open(tmp4, "w", encoding="utf-8") as f:
            f.write("def main():\n    pass\n")
        check("липсата му се разпознава", pazachat_e_v_scorera(tmp4) is False)
        # 🔴 СЕНТИНЕЛ: „не можах да прочета" НЕ Е „няма пазач".
        check("нечетимият файл дава None, не False",
              pazachat_e_v_scorera(os.path.join(tmp4, "нямаго.py")) is None)
        with io.open(tmp4, "w", encoding="utf-8") as f:
            f.write("def main():\n    pass\n")
        check("без пазач НЕ будим дори в прозореца",
              oc_budi_li(d(14, 20), {}, tmp4)[0] is False)
        check("и причината го казва",
              "няма пазач" in oc_budi_li(d(14, 20), {}, tmp4)[1])
        check("нечетимият scorer.py също не буди",
              oc_budi_li(d(14, 20), {}, os.path.join(tmp4, "нямаго.py"))[0] is False)
        with io.open(tmp4, "w", encoding="utf-8") as f:
            f.write("def prati_ravnosmetka(a, b, c, d, e):\n    pass\n")
        check("С пазач будим както преди",
              oc_budi_li(d(14, 20), {}, tmp4) == reshi_ocenitel(d(14, 20), {}))
        check("портиерът не отменя прозорците",
              oc_budi_li(d(12, 0), {}, tmp4)[0] is False)
        check("нито тавана",
              oc_budi_li(d(14, 20),
                         {"ocenitel": {"2026-08-12|obed": {"opiti": 9}}},
                         tmp4)[0] is False)
    finally:
        try:
            os.remove(tmp4)
        except OSError:
            pass

    # --- прозорците са сверени с ЖИВИЯ scorer.py, не с паметта ми.
    # Разминат ли се, будилникът или ще буди в мъртвата зона (рън без нито едно
    # съобщение), или ще пали обедния прозорец, когато оценителят вече праща
    # ФИНИШ — тоест окончателна равносметка по средата на деня.
    sverka_zapochva()
    _ssrc = None
    try:
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "scorer.py"), encoding="utf-8-sig") as f:
            _ssrc = f.read()
    except Exception as e:                                   # noqa: BLE001
        nesverimo("прозорците със scorer.py: " + str(e)[:60])
    if _ssrc is not None:
        _a = _b = _c = _dd = None
        try:
            _i = _ssrc.find("vecher = now.hour >= ")
            if _i >= 0:
                _red = _ssrc[_i:_ssrc.find(chr(10), _i)]
                _a = int(_red.split(">= ")[1].split(" ")[0])
                _b = int(_red.split("< ")[-1].strip())
                _j = _ssrc.find(chr(10) + "    obed = ", _i)
                if _j >= 0:
                    _red2 = _ssrc[_j + 1:_ssrc.find(chr(10), _j + 1)]
                    _c = int(_red2.split("= ")[1].split(" ")[0])
                    _dd = int(_red2.split("< ")[-1].strip())
        except Exception as e:                               # noqa: BLE001
            _a = _b = _c = _dd = None
            nesverimo("прозорците в scorer.py не се разчитат: " + str(e)[:60])
        # Котвата е ЧУЖД изходен текст. Смени ли се, това е ⚠ — не червено:
        # червеното тук прескача цялото будене (виж главата горе).
        if _a is None or _b is None:
            nesverimo("не намирам вечерния прозорец в scorer.py")
        else:
            check("вечерният будилник е ВЪТРЕ във вечерта на оценителя",
                  OC_VECHER_OT >= _a * 60 and OC_VECHER_DO < _b * 60)
        if _c is None or _dd is None:
            nesverimo("не намирам обедния прозорец в scorer.py")
        else:
            check("обедният будилник е ВЪТРЕ в обяда на оценителя",
                  OC_OBED_OT >= _c * 60 and OC_OBED_DO < _dd * 60)

    # ═══════════════════════════════════════════════════════════════════
    #  🔌 РЪЧКИТЕ: СТИГАТ ЛИ ДО ПРОЦЕСА (02.09.2026)
    #
    #  Първо СПИСЪКЪТ се сверява с кода, после ФУНКЦИЯТА се проверява върху
    #  нарочно скроени текстове, и чак накрая се гледа живият router.yml.
    #  Обратният ред би бил проверка, която пита самата себе си.
    # ═══════════════════════════════════════════════════════════════════
    _ok_predi_ryachkite = ok
    try:
        with io.open(os.path.abspath(__file__), encoding="utf-8-sig") as f:
            _moyat = f.read()
        _chetat = sorted(set(re.findall(r'_cyalo\("(PREDICT_[A-Z_]+)"', _moyat)))
        check("списъкът с ръчки е същият като ключовете, които наистина чета",
              _chetat == sorted(RYACHKI) and len(_chetat) >= 2)
    except Exception as _e:                                  # noqa: BLE001
        bad.append("не мога да прочета собствения си файл: " + str(_e)[:50])

    _polen = (chr(10).join([
        "      - name: Проспа ли предсказателя или оценителя",
        "        id: budilnik",
        "        env:",
        "          BUDILNIK_OCENITEL: '1'",
        "          PREDICT_QUIET_TO: x",
        "          PREDICT_QUIET_FROM: y",
        "        run: python budilnik.py",
        "      - name: Друга стъпка",
        "        run: echo 1"]))
    _bez = _polen.replace("          PREDICT_QUIET_TO: x" + chr(10), "")
    _prazen = _polen.replace("          PREDICT_QUIET_TO: x" + chr(10), "").replace(
        "          PREDICT_QUIET_FROM: y" + chr(10), "")
    check("пълната стъпка не крие ръчки", ryachkite_v_router(_polen) == [])
    check("липсващата ръчка се вижда",
          ryachkite_v_router(_bez) == ["PREDICT_QUIET_TO"])
    check("липсват ли и двете, се виждат и двете",
          ryachkite_v_router(_prazen) == sorted(RYACHKI))
    check("без стъпка за голия будилник връща СЕНТИНЕЛ, не празен списък",
          ryachkite_v_router("") is None
          and ryachkite_v_router(_polen.replace(
              "        run: python budilnik.py", "        run: echo нищо"))
          is None)
    # 🔴 ключът в КОМЕНТАР до кода не е подаден ключ. Точно това вече е
    # минавало незабелязано: проверка, търсеща низ, докато низът стои в
    # обяснението до него.
    check("ключ в коментар НЕ се брои за подаден",
          ryachkite_v_router(_prazen.replace(
              "        env:",
              "        env:" + chr(10)
              + "          # PREDICT_QUIET_TO и PREDICT_QUIET_FROM идват тук"))
          == sorted(RYACHKI))
    # 🔴 ключът в ДРУГА стъпка също не е подаден на будилника.
    check("ключ в чужда стъпка НЕ се брои за подаден",
          ryachkite_v_router(_prazen.replace(
              "        run: echo 1",
              "        env:" + chr(10) + "          PREDICT_QUIET_TO: x"
              + chr(10) + "        run: echo 1")) == sorted(RYACHKI))
    # 🔴 стъпката със --selftest НЕ е стъпката, която буди.
    _samo_test = chr(10).join([
        "      - name: Самопроверка",
        "        env:",
        "          PREDICT_QUIET_TO: x",
        "          PREDICT_QUIET_FROM: y",
        "        run: |",
        "          python budilnik.py --selftest"])
    check("стъпката със --selftest не се брои за будеща",
          ryachkite_v_router(_samo_test) is None)
    check("а същата стъпка + гол будилник се мери по ГОЛИЯ",
          ryachkite_v_router(_samo_test + chr(10) + _prazen)
          == sorted(RYACHKI))
    # 🔴 МУТАЦИЯ 5 — ТЪРСЕНЕ В ЦЕЛИЯ ТЕКСТ вместо в блока. Точно това е
    # проверката, която съдържа собствения си отговор: коментарът я лъже.
    def _sliapo(tekst):
        return sorted(k for k in RYACHKI if (k + ":") not in tekst)
    _lazhliv = _prazen.replace(
        "        env:",
        "        env:" + chr(10)
        + "          # PREDICT_QUIET_TO: и PREDICT_QUIET_FROM: са коментар")
    check("МУТАЦИЯ: търсене в целия текст обявява коментара за подаден ключ",
          _sliapo(_lazhliv) == [] and ryachkite_v_router(_lazhliv)
          == sorted(RYACHKI))

    # --- и чак сега ЖИВИЯТ router.yml
    sverka_zapochva()
    _rsrc = None
    try:
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  ".github", "workflows", "router.yml"),
                     encoding="utf-8-sig") as f:
            _rsrc = f.read()
    except Exception as _e:                                  # noqa: BLE001
        nesverimo("ръчките в router.yml: " + str(_e)[:60])
    if _rsrc is not None:
        _lipsvat = ryachkite_v_router(_rsrc)
        if _lipsvat is None:
            nesverimo("в router.yml няма стъпка, която пуска голия budilnik.py")
        elif _lipsvat:
            nesverimo("МЪРТВА РЪЧКА: router.yml НЕ подава на будилника "
                      + ", ".join(_lipsvat)
                      + " — predict.yml ги подава на предсказателя, тоест "
                      + "денонощният режим ще важи за него, но не и за "
                      + "будилника (той ще спре на " + str(DO_CHAS) + ":59)")

    # ═══════════════════════════════════════════════════════════════════
    #  📤 ИЗХОДЪТ КЪМ WORKFLOW-А. Двата реда budim= и ocenitel= са ЕДИНСТВЕНАТА
    #  връзка между това решение и стъпките, които го изпълняват. Изчезне ли
    #  редът за оценителя, рънът е ЗЕЛЕН и не буди никого — мълчание, което
    #  отвън не се вижда. Дотук нито една проверка не пипаше main().
    # ═══════════════════════════════════════════════════════════════════
    _dir = os.environ.get("TEMP") or "."
    _po = os.path.join(_dir, "_budilnik_izhod.txt")
    _ps = os.path.join(_dir, "_budilnik_glavno_ps.json")
    _pb = os.path.join(_dir, "_budilnik_glavno_bs.json")
    _st_state, _st_bud, _st_vkl = STATE_FILE, BUD_STATE, OC_VKL
    _imashe_izhod = "GITHUB_OUTPUT" in os.environ
    _star_izhod = os.environ.get("GITHUB_OUTPUT")
    _st_argv = list(sys.argv)
    try:
        with io.open(_ps, "w", encoding="utf-8") as f:
            json.dump({"diag": {"koga": "2000-01-01 00:00"}}, f)
        globals()["STATE_FILE"] = _ps
        globals()["BUD_STATE"] = _pb
        globals()["OC_VKL"] = False
        os.environ["GITHUB_OUTPUT"] = _po
        sys.argv = ["budilnik.py"]

        # 🔴 МУТАЦИЯ 6 — MAIN БЕЗ РЕДА ЗА ОЦЕНИТЕЛЯ. Същото твърдение, счупен
        # производител: липсва ли редът, проверката ТРЯБВА да падне.
        def _osakaten_izhod(put):
            with io.open(put, "a", encoding="utf-8") as g:
                g.write("budim=0" + chr(10))
        with io.open(_po, "w", encoding="utf-8") as f:
            f.write("")
        _osakaten_izhod(_po)
        with io.open(_po, encoding="utf-8") as f:
            _txt = f.read()
        check("МУТАЦИЯ: изход без ocenitel= не минава проверката",
              "budim=" in _txt and "ocenitel=" not in _txt)

        with io.open(_po, "w", encoding="utf-8") as f:
            f.write("predi=1" + chr(10))
        # 🔴 ТИХО. main() печата решението си; пуснат ВЪТРЕ в самопроверката,
        # той би сложил в дневника на рутера втори ред «спя», който изглежда
        # като истинското решение за този рън. Дневникът и без това се чете
        # трудно — два реда за едно и също са капан за следващия.
        _shum = io.StringIO()
        _star_out = sys.stdout
        try:
            sys.stdout = _shum
            _izh = main()
        finally:
            sys.stdout = _star_out
        with io.open(_po, encoding="utf-8") as f:
            _txt = f.read()
        check("истинският main пише budim= в GITHUB_OUTPUT", "budim=" in _txt)
        check("истинският main пише и ocenitel=", "ocenitel=" in _txt)
        check("изходът се ДОПИСВА, не се презаписва", "predi=1" in _txt)
        check("main връща 0", _izh == 0)
        check("при изключен будилник за оценителя изходът е точно 0",
              "ocenitel=0" in _txt)
        check("изходът е точно два реда, не повече",
              sum(1 for _r in _txt.split(chr(10))
                  if _r.startswith(("budim=", "ocenitel="))) == 2)
        check("стойностите са само 0 или 1",
              all(_r.split("=")[1] in ("0", "1")
                  for _r in _txt.split(chr(10))
                  if _r.startswith(("budim=", "ocenitel="))))
        # без GITHUB_OUTPUT main() не бива да гърми — така се пуска локално
        del os.environ["GITHUB_OUTPUT"]
        _star_out = sys.stdout
        try:
            sys.stdout = io.StringIO()
            _bez_izhod = main()
        finally:
            sys.stdout = _star_out
        check("без GITHUB_OUTPUT main() пак минава", _bez_izhod == 0)
        check("и пак печата решение", "спя" in _shum.getvalue()
              or "БУДЯ" in _shum.getvalue())
    except Exception as _e:                                  # noqa: BLE001
        bad.append("main() гърми в самопроверката: " + str(_e)[:70])
    finally:
        globals()["STATE_FILE"] = _st_state
        globals()["BUD_STATE"] = _st_bud
        globals()["OC_VKL"] = _st_vkl
        sys.argv = _st_argv
        if _imashe_izhod:
            os.environ["GITHUB_OUTPUT"] = _star_izhod
        else:
            os.environ.pop("GITHUB_OUTPUT", None)
        for _p in (_po, _ps, _pb, _pb + ".tmp"):
            try:
                os.remove(_p)
            except OSError:
                pass

    # ═══════════════════════════════════════════════════════════════════
    #  📏 ПРОЗОРЕЦЪТ ТРЯБВА ДА ПОБИРА СОБСТВЕНИЯ СИ ТАВАН (02.09.2026)
    #  Измерено в живия тефтер: и в 11 от 11 прозореца таванът 2 се изчерпва —
    #  обедът в 15:50, вечерта в 00:45, тоест точно първи опит + почивка 45
    #  мин + свежо 90 мин. Вдигне ли някой почивката или свежото, вторият опит
    #  става недостижим и таванът мълчаливо пада на 1.
    # ═══════════════════════════════════════════════════════════════════
    _obed_dyl = OC_OBED_DO - OC_OBED_OT
    _vech_dyl = (1440 - OC_VECHER_OT) + OC_VECHER_DO
    check("обедният прозорец побира тавана при тази почивка",
          _obed_dyl >= (OC_TAVAN - 1) * OC_POCHIVKA)
    check("вечерният прозорец побира тавана при тази почивка",
          _vech_dyl >= (OC_TAVAN - 1) * OC_POCHIVKA)
    check("свежото не изяжда целия обеден прозорец", OC_SVEZHO < _obed_dyl)
    check("свежото не изяжда целия вечерен прозорец", OC_SVEZHO < _vech_dyl)
    # И на живо: първи опит в началото, втори след свежото — както е измерено.
    _s7 = {}
    oc_zapishi_opit(_s7, d(14, 15))
    _s7 = ravn_otbelezhi(_s7, ravn_klyuch("2026-08-12", "mezhdinna", "staya",
                                          "текст"), d(14, 16))
    check("вторият опит идва СЛЕД свежото, не след почивката",
          reshi_ocenitel(d(15, 30), _s7)[0] is False
          and reshi_ocenitel(d(15, 50), _s7)[0] is True)

    # 🔴 ДОЛНА ГРАНИЦА НА БРОЯ, НЕ НА ЗЕЛЕНОТО. Пропадне ли блокът по-горе
    # заради ранен return или сгрешен отстъп, тази проверка го издава — иначе
    # „0 счупени“ щеше да значи „0 прегледани“.
    check("пазачът добави поне 60 свои проверки", ok - _ok_predi_pazacha >= 60)
    check("ръчките и изходът добавиха поне 20 свои проверки",
          ok - _ok_predi_ryachkite >= 20)
    # 🔴 СВЕРКИТЕ СЕ БРОЯТ. Иначе «0 несверени» щеше да значи «0 погледнати»:
    # изчезне ли цял блок, тук пада броят на ОПИТАНИТЕ, не на успелите.
    check("и трите сверки с чужди файлове са ОПИТАНИ", sverki["opitani"] == 3)

    check("броят проверки е поне 130", ok >= 130)

    print("САМОПРОВЕРКА НА БУДИЛНИКА: " + str(ok) + " наред, " + str(len(bad))
          + " счупени, " + str(len(warn)) + " несверени")
    for b in bad:
        print("   счупено: " + b)
    for w in warn:
        print("   ⚠ НЕСВЕРЕНО (не спира рутера): " + w)
    return 0 if not bad else 1


def main():
    if "--selftest" in sys.argv or "selftest" in sys.argv:
        return selftest()
    sega = datetime.now(SOFIA)
    posleden = posleden_run()
    budim, zashto = reshi(posleden, sega, opit=None)
    if budim:
        # Записваме ПРЕДИ пускането, не след него. Падне ли предсказателят по
        # средата, опитът пак е отбелязан и спирачката важи.
        zapishi_opit(sega)
    print(("⏰ БУДЯ ПРЕДСКАЗАТЕЛЯ: " if budim else "😴 спя: ") + zashto)

    # ⏰ И ОЦЕНИТЕЛЯТ — отделен прозорец, отделен таван, отделен ключ в тефтера.
    # По подразбиране ИЗКЛЮЧЕН: пали се само там, където има кой да изпълни
    # решението (router.yml). Виж дългото обяснение при OC_VKL.
    oc_budim = False
    if OC_VKL:
        sast = cheti_sast()
        oc_budim, oc_zashto = oc_budi_li(sega, sast)
        if oc_budim:
            # Пак ПРЕДИ пускането: падне ли оценителят, опитът е отбелязан и
            # почивката важи. Рязането върви със записа, не с отделен рън.
            sast = oc_zapishi_opit(sast, sega)
            sast = izrezhi_stari(sast, sega)
            pishi_sast(sast)
        print(("⏰ БУДЯ ОЦЕНИТЕЛЯ: " if oc_budim else "😴 оценителят спи: ")
              + oc_zashto)
    else:
        print("😴 оценителят: будилникът му е ИЗКЛЮЧЕН (BUDILNIK_OCENITEL)")

    izhod = os.environ.get("GITHUB_OUTPUT")
    if izhod:
        with io.open(izhod, "a", encoding="utf-8") as f:
            f.write("budim=" + ("1" if budim else "0") + "\n")
            f.write("ocenitel=" + ("1" if oc_budim else "0") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
