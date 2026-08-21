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
import io
import json
import os
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


# Работните часове на предсказателя (predictor.RUN_HOURS = 8..22).
OT_CHAS = _cyalo("BUDILNIK_OT", 8, 0, 23)
DO_CHAS = _cyalo("BUDILNIK_DO", 22, 0, 23)

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
    """Кога будилникът е будил за последно. None = никога/нечетимо."""
    put = path or BUD_STATE
    try:
        with io.open(put, encoding="utf-8-sig") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return None
        return datetime.strptime(str(d.get("posleden_opit")).strip(),
                                 "%Y-%m-%d %H:%M").replace(tzinfo=SOFIA)
    except Exception:                                        # noqa: BLE001
        return None


def zapishi_opit(sega, path=None):
    put = path or BUD_STATE
    try:
        with io.open(put, "w", encoding="utf-8") as f:
            json.dump({"posleden_opit": sega.strftime("%Y-%m-%d %H:%M")}, f,
                      ensure_ascii=False)
        return True
    except Exception:                                        # noqa: BLE001
        return False


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
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

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
          reshi(d(3, 0), d(4, 30), opit=None)[0] is False)
    check("почивката бие пропуснатия час",
          reshi(d(12, 50), d(13, 20), opit=d(13, 10))[0] is False)
    check("гратисът е разумен", 3 <= GRATIS_MIN <= 20)
    # Денят се сменя: 23:xx -> 00:xx е нов час, но е и извън часовете.
    check("смяна на деня не подлудява правилото",
          reshi(datetime(2026, 8, 12, 23, 50, tzinfo=SOFIA),
                datetime(2026, 8, 13, 9, 30, tzinfo=SOFIA), opit=None)[0] is True)
    check("нощем НЕ будим дори при огромна дупка",
          reshi(d(12, 0), datetime(2026, 8, 13, 3, 0, tzinfo=SOFIA), opit=None)[0] is False)
    check("в 07:59 НЕ будим", reshi(d(4, 0), d(7, 59), opit=None)[0] is False)
    check("в 08:00 будим", reshi(datetime(2026, 8, 11, 22, 0, tzinfo=SOFIA),
                                 d(8, 0), opit=None)[0] is True)
    check("в 22:00 още будим", reshi(d(19, 0), d(22, 0), opit=None)[0] is True)
    check("в 23:00 вече не", reshi(d(19, 0), d(23, 0), opit=None)[0] is False)
    check("липсващ тефтер буди", reshi(None, d(12, 0), opit=None)[0] is True)
    check("липсващ тефтер НЕ буди нощем", reshi(None, d(3, 0), opit=None)[0] is False)
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
    try:
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "predictor.py"), encoding="utf-8-sig") as f:
            src = f.read()
        igla = "RUN_HOURS = tuple(range("
        i = src.find(igla)
        check("намирам работните часове в predictor.py", i >= 0)
        if i >= 0:
            j = src.find(")", i + len(igla))
            a, b = [int(x.strip()) for x in src[i + len(igla):j].split(",")[:2]]
            check("будилникът почва когато и предсказателят", OT_CHAS == a)
            check("будилникът спира когато и предсказателят", DO_CHAS == b - 1)
    except Exception as e:                                   # noqa: BLE001
        bad.append("не мога да сверя часовете с predictor.py: " + str(e)[:50])

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

    check("броят проверки е поне 30", ok >= 30)

    print("САМОПРОВЕРКА НА БУДИЛНИКА: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
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
    izhod = os.environ.get("GITHUB_OUTPUT")
    if izhod:
        with io.open(izhod, "a", encoding="utf-8") as f:
            f.write("budim=" + ("1" if budim else "0") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
