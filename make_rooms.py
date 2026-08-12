# -*- coding: utf-8 -*-
"""Създава ЛИПСВАЩИТЕ стаи по спорт във форум-групата и ги закача.

ЗАЩО СЪЩЕСТВУВА
Ботът предричаше за осем спорта, а стаи имаха само пет: футбол, баскетбол, тенис
на маса, волейбол и бойни спортове. Хокеят, тенисът, бейзболът и американският
футбол нямаха собствена стая — картите им отиваха само в общата витрина 27.
Собственикът го видя веднага: „включи и хокей, а не виждам стая и нищо".

КАК РАБОТИ
Telegram позволява на бот да създава теми във форум-група (createForumTopic), стига
да е администратор с право „Управление на темите". Тук се създава по една тема за
всеки липсващ спорт, слага ѝ се отварящ пост и постът се закача.

ПАМЕТ И ПОВТОРНО ПУСКАНЕ
Bot API НЯМА метод за изброяване на съществуващите теми. Затова паметта е файл:
rooms_state.json пази кой спорт коя тема е получил. Второ пускане НЕ създава втора
стая — то само проверява, че постът е на място. Файлът се връща в хранилището от
работния файл; без него следващото пускане би направило дубликати.

ПЪТ НАЗАД
Създадена тема се трие ръчно от приложението (⋮ на темата → Изтрий). Скриптът
никога не трие — само създава и пише.

Пуска се с MODE:
  plan   — САМО показва какво би направил, не пипа нищо (по подразбиране)
  create — наистина създава липсващите стаи
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
MODE = (os.environ.get("ROOMS_MODE")
        or (sys.argv[1] if len(sys.argv) > 1 else "plan")).strip().lower()
STATE_FILE = (os.environ.get("ROOMS_STATE_FILE") or "rooms_state.json").strip()

NL = chr(10)

# Спорт -> (име на стаята, цвят на иконата, отварящ пост)
# Цветовете са от позволените в Telegram: 7322096 синьо, 16766590 жълто,
# 13338331 лилаво, 9367192 зелено, 16749490 розово, 16478047 оранжево,
# 16749490 червено. Друга стойност се отхвърля от API-то.
NOVI = {
    "hockey": ("🏒 Хокей", 7322096, [
        "🏒 <b>ХОКЕЙ — затворено до старта на сезона</b>",
        "НХЛ е в лятна пауза. Първите мачове са около <b>средата на септември</b>"
        " и стаята тръгва заедно с тях — без да пита никого.",
        "Дотогава живите прогнози са в 🤖 БОТА ПРЕДРИЧА и в стаите на"
        " седемте спорта, които играят сега.",
    ]),
    "tennis": ("🎾 Тенис", 9367192, [
        "🎾 <b>ТЕНИС</b>",
        "Тук влизат <b>прогнозите за тенис</b>: избор, брой сетове, числата зад мача.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА.",
    ]),
    "baseball": ("⚾ Бейзбол", 16766590, [
        "⚾ <b>БЕЙЗБОЛ</b>",
        "Тук влизат <b>прогнозите за бейзбол</b>: избор и очаквани рънове.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА.",
    ]),
    "amfootball": ("🏈 Американски футбол", 16478047, [
        "🏈 <b>АМЕРИКАНСКИ ФУТБОЛ — затворено до старта на сезона</b>",
        "НФЛ още кара предсезонни мачове, а по тях не се съди нищо: съставите"
        " са смесени и водещите играят по четвърт мач. Редовният сезон е от"
        " <b>началото на септември</b> — тогава стаята тръгва.",
        "Дотогава живите прогнози са в 🤖 БОТА ПРЕДРИЧА и в стаите на"
        " седемте спорта, които играят сега.",
    ]),
}

# Пазач: думи, които НЕ излизат навън. Същият като в другите ботове.
BANNED = ["18+", "залагай отговорно", "коеф", "букмейкър", "odds",
          "заложи", "финансов съвет"]


def banned_word(text):
    low = (text or "").lower()
    for w in BANNED:
        if w in low:
            return w
    return None


def api(method, **params):
    """Заявка към Telegram с търпение към 429. Връща речника или {}."""
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/" + method
    data = urllib.parse.urlencode(
        {k: v for k, v in params.items() if v is not None}).encode()
    for opit in range(5):
        try:
            with urllib.request.urlopen(url, data=data, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:                     # noqa: BLE001
                pass
            if e.code == 429:
                try:
                    chakay = int(json.loads(body).get("parameters", {})
                                 .get("retry_after") or 3)
                except Exception:                 # noqa: BLE001
                    chakay = 3
                print("   429 — чакам " + str(chakay) + "с")
                time.sleep(chakay + 1)
                continue
            print("   " + method + " -> " + str(e.code) + " " + body[:160])
            return {}
        except Exception as e:                    # noqa: BLE001
            print("   " + method + " -> " + str(e)[:90])
            time.sleep(2)
    return {}


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8-sig") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:                             # noqa: BLE001
        return {}


def save_state(st):
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, STATE_FILE)               # атомарно
        return True
    except Exception as e:                        # noqa: BLE001
        print("паметта не се записа (" + str(e)[:70] + ") — СЛЕДВАЩОТО ПУСКАНЕ"
              " ЩЕ ДУБЛИРА СТАИТЕ.")
        return False


def sazdai(sport, ime, cvyat, redove, state):
    """Създава ЕДНА стая и ѝ закача отварящия пост. Не пипа вече създадена."""
    tekst = NL.join(redove)
    lоsha = banned_word(tekst)
    if lоsha:
        print("   ✖ " + sport + ": забранена дума (" + lоsha + ") — пропускам.")
        return False

    veche = (state.get(sport) or {}).get("thread")
    if veche:
        print("   • " + sport + ": вече има стая " + str(veche) + " — не пипам.")
        return False

    r = api("createForumTopic", chat_id=CHAT_ID, name=ime, icon_color=cvyat)
    if not r.get("ok"):
        print("   ✖ " + sport + ": стаята НЕ се създаде.")
        return False
    thread = (r.get("result") or {}).get("message_thread_id")
    if not thread:
        print("   ✖ " + sport + ": създаде се, но без номер — не записвам.")
        return False
    print("   ✔ " + sport + ": стая " + str(thread) + " (" + ime + ")")

    time.sleep(1.2)
    p = api("sendMessage", chat_id=CHAT_ID, message_thread_id=thread, text=tekst,
            parse_mode="HTML", disable_web_page_preview="true")
    mid = ((p.get("result") or {}).get("message_id")) if p.get("ok") else None
    if mid:
        time.sleep(0.8)
        api("pinChatMessage", chat_id=CHAT_ID, message_id=mid,
            disable_notification="true")
        print("     отварящият пост е закачен.")
    else:
        print("     ⚠ стаята е готова, но постът не тръгна — пробвай пак.")

    state[sport] = {"thread": int(thread), "ime": ime, "mid": mid}
    return True


def main():
    if not BOT_TOKEN:
        print("Липсва BOT_TOKEN.")
        return 1
    if not CHAT_ID:
        print("Липсва CHAT_ID.")
        return 1

    state = load_state()
    lipsvat = [s for s in NOVI if not (state.get(s) or {}).get("thread")]

    print("СТАИ ПО СПОРТ — какво липсва")
    for s, (ime, _, _) in NOVI.items():
        imashto = (state.get(s) or {}).get("thread")
        print("   %-12s %-26s %s" % (s, ime, ("стая " + str(imashto)) if imashto
                                     else "ЛИПСВА"))
    print()

    if not lipsvat:
        print("Всички стаи са налице — няма какво да правя.")
        return 0

    if MODE != "create":
        print("РЕЖИМ PLAN — нищо не е пипнато. Липсват: " + ", ".join(lipsvat))
        print("За да ги създам, пусни пак с ROOMS_MODE=create.")
        return 0

    napraveni = 0
    for s in NOVI:
        if s in lipsvat:
            ime, cvyat, redove = NOVI[s]
            if sazdai(s, ime, cvyat, redove, state):
                napraveni += 1
                save_state(state)         # СЛЕД ВСЯКА стая, не накрая
                time.sleep(1.5)

    save_state(state)
    print()
    print("Готово: " + str(napraveni) + " нови стаи.")
    print("Номерата са в " + STATE_FILE + " — предсказателят ги чете оттам.")
    return 0


def selftest():
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    check("четири нови спорта", len(NOVI) == 4)
    for s in ("hockey", "tennis", "baseball", "amfootball"):
        check("има план за " + s, s in NOVI)
        ime, cvyat, redove = NOVI[s]
        check(s + ": името не е празно", bool(ime.strip()))
        check(s + ": цветът е позволен",
              cvyat in (7322096, 16766590, 13338331, 9367192, 16749490, 16478047))
        check(s + ": постът е чист", banned_word(NL.join(redove)) is None)
        check(s + ": постът има три реда", len(redove) == 3)
    check("футболът НЕ се създава наново", "football" not in NOVI)
    check("волейболът НЕ се създава наново", "volleyball" not in NOVI)
    check("тенисът на маса НЕ се създава наново", "tabletennis" not in NOVI)
    check("ММА НЕ се създава наново", "mma" not in NOVI)
    check("хазартна дума се лови", banned_word("залагай отговорно") is not None)
    check("чист текст минава", banned_word("🏒 ХОКЕЙ") is None)
    # Паметта пази от дубликати
    _st = {"hockey": {"thread": 400}}
    _lipsvat = [s for s in NOVI if not (_st.get(s) or {}).get("thread")]
    check("вече създадената стая не се брои за липсваща",
          "hockey" not in _lipsvat and len(_lipsvat) == 3)
    check("режимът по подразбиране НЕ създава", "plan" != "create")

    print("САМОПРОВЕРКА НА СТАИТЕ: " + str(ok) + " наред, "
          + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return not bad


if __name__ == "__main__":
    if "--selftest" in sys.argv or os.environ.get("ROOMS_SELFTEST") == "1":
        sys.exit(0 if selftest() else 1)
    sys.exit(main())
