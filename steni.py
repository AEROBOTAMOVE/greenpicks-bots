# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — ТРЯБВА ЛИ ДА СЕ ПИПНАТ СТЕНИТЕ? 🧱

Един въпрос, чист от мрежа: РАЗЛИЧАВА ЛИ СЕ някой закачен текст от това,
което вече стои в стаята?

ЗАЩО СЪЩЕСТВУВА
`hub.yml` има крон в 06:30 и той опреснява пиновете. На 13.08.2026 GitHub го
ПРОПУСНА напълно — нула пускания за целия ден. Резултат: двата затворени
спорта останаха със стари пинове, които обещават прогнози. Кодът беше верен,
часовникът не удари.

Изводът е по-широк от хъба: **всеки крон „веднъж на ден" има реален шанс
изобщо да не тръгне.** Мереното за рутера е 6.5 пускания при зададени 144.
Значи важната работа не бива да виси на един ежедневен крон.

КАК ГО ПРАВИ БЕЗ ДА СТРУВА НИЩО
`setup_hub.py` пази в hub_state.json какво е сложил и КАКЪВ Е БИЛ ТЕКСТЪТ.
Тук просто сравняваме: текущите текстове срещу записаните. Нула мрежа, нула
Telegram — само четене на два файла. Затова може да виси на workflow, който
върви често, без да струва почти нищо.

Излиза `nuzhno=1` само когато нещо наистина се е сменило. Тогава workflow-ът
пуска `setup_hub.py rooms`, а той сам решава кое да опресни на място.

  python steni.py            — решава и печата
  python steni.py --selftest — само проверките
"""
import io
import json
import os
import sys

HUB_STATE = (os.environ.get("HUB_STATE_FILE") or "hub_state.json").strip()


def chetiv(path):
    try:
        with io.open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:                                        # noqa: BLE001
        return {}


def zhivi_tekstove():
    """{ключ: текст} — каквото setup_hub БИ сложил сега. None при провал."""
    try:
        import setup_hub as H
    except Exception as e:                                   # noqa: BLE001
        print("не мога да внеса setup_hub (" + str(e)[:60] + ")")
        return None
    try:
        H.vlei_novite_stai()
    except Exception:                                        # noqa: BLE001
        pass
    out = {}
    for thread, text in (H.ROOM_PINS or {}).items():
        out[str(thread)] = text
    out["11-support"] = H.SUPPORT_POST
    return out


def reshi(zhivi, zapisani):
    """(нужно_ли, списък с причини). Чиста функция — тества се без файлове."""
    if zhivi is None:
        # Не можем да прочетем какво трябва да стои. Това НЕ е повод да
        # мълчим: по-добре един излишен рън, отколкото стена, която лъже.
        return True, ["не мога да прочета живите текстове — пускам за всеки случай"]
    prichini = []
    for k, txt in sorted(zhivi.items()):
        star = (zapisani.get(k) or {})
        if not isinstance(star, dict) or "text" not in star:
            prichini.append("стая " + k + ": няма запис какво стои там")
        elif str(star.get("text")) != str(txt):
            prichini.append("стая " + k + ": текстът е сменен")
    # Стая, която е в паметта, но вече я няма в живите — не е повод за рън.
    return (bool(prichini), prichini)


def selftest():
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    Z = {"5": "футбол", "6": "баскет", "11-support": "помощ"}
    ZAP = {k: {"mid": 1, "text": v} for k, v in Z.items()}

    check("всичко съвпада = не пипаме", reshi(Z, ZAP)[0] is False)
    check("сменен текст = пипаме", reshi(dict(Z, **{"5": "нов"}), ZAP)[0] is True)
    check("нова стая без запис = пипаме", reshi(dict(Z, **{"7": "тенис"}), ZAP)[0] is True)
    check("празна памет = пипаме", reshi(Z, {})[0] is True)
    check("нечетими живи текстове = пипаме", reshi(None, ZAP)[0] is True)
    check("изчезнала от живите стая НЕ е повод",
          reshi({"5": "футбол"}, ZAP)[0] is False)
    check("причината се изписва", "текстът е сменен" in
          " ".join(reshi(dict(Z, **{"5": "нов"}), ZAP)[1]))
    check("боклук вместо запис = пипаме", reshi(Z, {"5": "низ", "6": {"text": "баскет"},
                                                    "11-support": {"text": "помощ"}})[0] is True)
    check("запис без text = пипаме", reshi(Z, {"5": {"mid": 1}, "6": {"text": "баскет"},
                                               "11-support": {"text": "помощ"}})[0] is True)
    check("чистата функция не пипа файлове", chetiv("нямаго.json") == {})

    # Живо: текстовете наистина се четат от setup_hub и съпорт-постът е вътре.
    _zh = zhivi_tekstove()
    check("живите текстове се четат", _zh is not None and len(_zh) >= 10)
    check("съпорт-постът има свой ключ", _zh is not None and "11-support" in _zh)
    check("всеки текст е непразен", _zh is not None
          and all(str(v).strip() for v in _zh.values()))
    check("броят проверки е поне 12", ok >= 12)

    print("САМОПРОВЕРКА НА СТЕНИТЕ: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return 0 if not bad else 1


def main():
    if "--selftest" in sys.argv or "selftest" in sys.argv:
        return selftest()
    zhivi = zhivi_tekstove()
    nuzhno, prichini = reshi(zhivi, chetiv(HUB_STATE))
    if nuzhno:
        print("🧱 СТЕНИТЕ ИСКАТ ОПРЕСНЯВАНЕ (" + str(len(prichini)) + "):")
        for p in prichini[:8]:
            print("   • " + p)
    else:
        print("🧱 стените са същите — не пипам нищо")
    izhod = os.environ.get("GITHUB_OUTPUT")
    if izhod:
        with io.open(izhod, "a", encoding="utf-8") as f:
            f.write("nuzhno=" + ("1" if nuzhno else "0") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
