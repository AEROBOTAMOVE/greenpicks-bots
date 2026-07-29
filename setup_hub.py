# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — HUB + СТАЙНИ ПИНОВЕ (еднократно, Bot API — надеждно)

- КАНАЛ: 1 закачен HUB (какво тече тук + навигация + съпорт), ТЕКСТ (не картинка).
         В канала има фишовете на човека-типстер, обзорът в 21:00 и резултатите.
         НОВИНИ В КАНАЛА НЯМА — те живеят в стая 26 „Новини".
- СТАИ:  кратък ТЕКСТ пин във всяка + откачва старите welcome-КАРТИЧКИ (unpin).
- Съпорт-пост в стая 11 „Въпроси и Помощ".

Потвърдена карта на стаите (проверена наживо):
   1 Общ чат
   3 Правила и Начало
   4 Фишове на деня          — САМО човекът-типстер, бот никога
   5 Футбол · 6 Баскетбол · 7 Тенис на маса · 8 Волейбол
                             — САМО срещите по направление, без новини
   9 Резултати и статистика  — един дневен отчет за типстъра + един за бота
  10 Печеливши фишове
  11 Въпроси и Помощ
  26 Новини                  — ВСИЧКИ новини, подредени по спорт
  27 БОТА ПРЕДРИЧА           — всички прогнози на бота
 328 Бойни спортове          — САМО предстоящите боеве и карти (UFC / ММА / бокс)

MODE=hub|rooms|all
Бележка за деплой: файлът е писан БЕЗ обратни наклонени черти (нов ред = NL = chr(10)).
Внимание: reset.py прави „import setup_hub as H" и ползва H.api, H.send_pin, H.HUB,
H.ROOM_PINS, H.SUPPORT_POST, H.GROUP_LINK, H.BOT_TOKEN, H.CHAT_ID, H.CHANNEL_ID —
тези имена не се преименуват.
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
GROUP_LINK = os.environ.get("GROUP_LINK", "https://t.me/+_oYsaYaVKU80Yjc0")
SUPPORT = os.environ.get("SUPPORT") or "@green_picks_info_bot"
MODE = (os.environ.get("HUB_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "all")).strip()

NL = chr(10)

def block(*lines):
    """Слепва редовете с нов ред — без обратни наклонени черти в текста."""
    return NL.join(lines)

def api(method, **params):
    """Една заявка към Telegram, която ИЗЧАКВА при 429.

    ЗАЩО СЪЩЕСТВУВА ТОЗИ ЦИКЪЛ (намерено на живо на 28.07.2026)
    Подреждането пише в 12 стаи, а всяка стая струва ТРИ заявки: откачване на
    стария пин, пращане и закачане. Тридесет и шест заявки за половин минута
    минават над лимита на Telegram и той започва да връща 429. Старият код
    само печаташе грешката и продължаваше — резултатът беше, че последната
    стая в реда, 328 „Бойни спортове", остана със стария си пин, а рънът се
    отчете като успешен. Тих провал.

    Сега чакаме толкова, колкото Telegram каже (parameters.retry_after), и
    опитваме пак. Същото, което reset.py прави отдавна.
    """
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/" + method
    for attempt in range(5):
        data = urllib.parse.urlencode(params).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=25) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429:
                try:
                    ra = int(json.loads(body).get("parameters", {}).get("retry_after", 5))
                except Exception:
                    ra = 5
                print("  429 при " + method + " — чакам " + str(ra + 1) + " сек и пробвам пак")
                time.sleep(ra + 1)
                continue
            print(method, "HTTP", e.code, body[:160])
            return {}
        except Exception as e:
            print(method, "FAIL", e)
            return {}
    print(method, "— пет пъти 429 подред, отказвам се")
    return {}

FOOT = "🟢 THE GREEN ROOM"

HUB = block(
"🟢 <b>THE GREEN ROOM — прогнози на база статистика</b>",
"",
"Показваме кой мач как стои по числата. Честно.",
"📊 Всеки фиш е <b>ПРОГНОЗА</b> от статистика.",
"🔒 Нищо не трием. Загубите остават видими завинаги.",
"",
"<b>Какво тече в КАНАЛА:</b>",
"🎯 През деня — фишовете на типстъра (човека)",
"📊 21:00 — Обзорът на бота: числата за деня",
"✅ Вечер — резултатите на деня",
"📌 Новини в канала НЯМА — всички новини са в групата, стая 📰 Новини.",
"",
"<b>Какво има в ГРУПАТА (стаите):</b>",
"📰 Новини — всички новини, подредени по спорт",
"⚽ 🏀 🏓 🏐 🥊 Спортните стаи — само срещите и боевете по направление",
"🤖 БОТА ПРЕДРИЧА — прогнозите и анализите на бота",
"✅ Резултати и статистика · 🏆 Печеливши фишове · 🆘 Въпроси и Помощ",
"",
"🆘 <b>Помощ и контакт:</b> " + SUPPORT + " · или в стая 🆘 Въпроси и Помощ",
"👇 Влез в групата и стаите по спорт от бутона."
)
# thread -> кратък закачен текст (потвърдената карта на стаите)
ROOM_PINS = {
    3: block(
        "📌 <b>ПРАВИЛА И НАЧАЛО</b>",
        "Как работи The Green Room: стаите, форматът на фишовете, прозрачността.",
        "Виж закачените обучителни постове."),
    4: block(
        "🎯 <b>ФИШОВЕ НА ДЕНЯ</b>",
        "Тук пише <b>САМО човекът-типстер</b>. Ботовете нямат достъп до тази стая.",
        "Формат: мач · прогноза · логика."),
    5: block(
        "⚽ <b>ФУТБОЛ</b>",
        "Тук влизат <b>САМО срещите</b> по футбол: час, отбори, турнир.",
        "Новините са в стая 📰 Новини · анализите и прогнозите — в 🤖 БОТА ПРЕДРИЧА."),
    6: block(
        "🏀 <b>БАСКЕТБОЛ</b>",
        "Тук влизат <b>САМО срещите</b> по баскетбол (NBA/Евролига): час, отбори, турнир.",
        "Новините са в стая 📰 Новини · анализите и прогнозите — в 🤖 БОТА ПРЕДРИЧА."),
    7: block(
        "🏓 <b>ТЕНИС НА МАСА</b>",
        "Тук влизат <b>САМО срещите</b> по тенис на маса (WTT/ITTF): час, играчи, турнир.",
        "Новините са в стая 📰 Новини · анализите и прогнозите — в 🤖 БОТА ПРЕДРИЧА."),
    8: block(
        "🏐 <b>ВОЛЕЙБОЛ</b>",
        "Тук влизат <b>САМО срещите</b> по волейбол: час, отбори, турнир.",
        "Новините са в стая 📰 Новини · анализите и прогнозите — в 🤖 БОТА ПРЕДРИЧА."),
    9: block(
        "✅ <b>РЕЗУЛТАТИ И СТАТИСТИКА</b>",
        "Всеки ден по два отчета: 🎯 един за фишовете на типстъра и 🤖 един за бота.",
        "Зелено печели / червено губи. Нищо не се трие."),
    10: block(
        "🏆 <b>ПЕЧЕЛИВШИ ФИШОВЕ</b>",
        "Витрина само на спечелилите.",
        "Пълният отчет — със загубите — е в ✅ Резултати и статистика."),
    11: block(
        "🆘 <b>ВЪПРОСИ И ПОМОЩ</b>",
        "Питай тук — отговаряме пред всички.",
        "Личен контакт: " + SUPPORT + " · виж и закачения съпорт-пост."),
    26: block(
        "📰 <b>НОВИНИ</b>",
        "<b>ВСИЧКИ новини са тук</b> и са подредени по спорт:",
        "🏓 Тенис на маса · 🏐 Волейбол · 🏀 Баскетбол · ⚽ Футбол · 📰 Други спортове.",
        "В спортните стаи новини НЕ влизат — там са само срещите.",
        "Тих ден = няма пост. Тишината е злато."),
    27: block(
        "🤖 <b>БОТА ПРЕДРИЧА</b>",
        "Тук са <b>всички прогнози и анализи на бота</b>: H2H, форма, числата зад мача."),
    328: block(
        "🥊 <b>БОЙНИ СПОРТОВЕ</b>",
        "Тук влизат <b>САМО предстоящите боеве и картите</b>: UFC, ММА, бокс — дата, час, бойци.",
        "Новините са в стая 📰 Новини · анализите и прогнозите — в 🤖 БОТА ПРЕДРИЧА."),
}
SUPPORT_POST = block(
"🆘 <b>ВЪПРОСИ И ПОМОЩ</b>",
"",
"Въпрос, идея или проблем?",
"✍️ Пиши на бота: " + SUPPORT,
"Той отговаря веднага на честите въпроси, а всичко останало предава на екипа.",
"💬 Или публично тук — така отговорът остава видим за всички.",
"",
"<b>Често:</b>",
"• Фишът е ПРОГНОЗА от статистика, не гаранция.",
"• Показваме и загубите — прозрачност или нищо.",
"• Новините са в стая 📰 Новини · срещите — в стаята на своя спорт.",
"",
"💚 The Green Room"
)

# ------------------------------------------------------- ПАМЕТ НА ПОДРЕЖДАНЕТО
# ЗАЩО СЪЩЕСТВУВА
# Дотук всяко пускане пишеше НОВ пост във всяка стая и го закачаше. Три
# пускания = три еднакви поста в дванадесет стаи. Собственикът го видя и каза
# право: „искам по един път в началото и това е, после само резултати и
# новини". Затова тук помним какво сме сложили и къде.
#
# Правилото е просто:
#   няма записан пост          -> пращаме и закачаме
#   има го и текстът е СЪЩИЯТ  -> НЕ пишем нищо, само се уверяваме, че е закачен
#   има го, но текстът е нов   -> ОПРЕСНЯВАМЕ го на място (editMessageText)
# Така подреждането може да се пуска колкото пъти искаш, без да трупа.
HUB_STATE_FILE = (os.environ.get("HUB_STATE_FILE") or "hub_state.json").strip()


def load_hub_state():
    try:
        with open(HUB_STATE_FILE, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:                     # noqa: BLE001
        print("паметта на подреждането е повредена (" + str(e)[:60] + ") — почвам чисто.")
        return {}


def save_hub_state(st):
    try:
        tmp = HUB_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
        os.replace(tmp, HUB_STATE_FILE)        # атомарно
        return True
    except Exception as e:                     # noqa: BLE001
        print("паметта не се записа (" + str(e)[:60] + ") — следващото пускане ще дублира.")
        return False


def send_pin(chat, text, thread=None, unpin_first=False, state=None, key=None):
    """Слага (или опреснява) ЕДИН пост в стая. Не трупа при повторно пускане."""
    where = "канал" if str(chat) == str(CHANNEL_ID) else "стая " + str(thread)
    st = state if isinstance(state, dict) else None
    k = str(key if key is not None else thread)
    prev = (st or {}).get(k) or {}
    mid = prev.get("mid")

    def do_pin(message_id):
        return api("pinChatMessage", chat_id=chat, message_id=message_id,
                   disable_notification="true").get("ok")

    # 1) Познат пост със същия текст — нищо ново не пишем.
    if mid and prev.get("text") == text:
        print("  " + where + ": постът вече е там — " +
              ("закачен" if do_pin(mid) else "не успях да го закача"))
        return

    # 2) Познат пост, но текстът се е сменил — опресняваме НА МЯСТО.
    if mid:
        p = {"chat_id": chat, "message_id": mid, "text": text,
             "parse_mode": "HTML", "disable_web_page_preview": "true"}
        r = api("editMessageText", **p)
        if r.get("ok"):
            if st is not None:
                st[k] = {"mid": mid, "text": text}
            print("  " + where + ": постът е опреснен на място — " +
                  ("закачен" if do_pin(mid) else "не успях да го закача"))
            return
        print("  " + where + ": старият пост не се опресни (изтрит?) — пращам нов.")

    # 3) Нищо не знаем (или старият е изчезнал) — нов пост.
    if unpin_first and thread:
        api("unpinAllForumTopicMessages", chat_id=chat, message_thread_id=thread)
    p = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if thread and int(thread) > 1:
        p["message_thread_id"] = thread
    r = api("sendMessage", **p)
    if not r.get("ok"):
        print("  send fail:", str(r)[:100]); return
    new_mid = r["result"]["message_id"]
    if st is not None:
        st[k] = {"mid": new_mid, "text": text}
    print("  " + where + ": " + ("закачено" if do_pin(new_mid) else "пратено (не закач.)"))

def main():
    if not BOT_TOKEN: print("Missing BOT_TOKEN"); sys.exit(1)
    state = load_hub_state()

    if MODE in ("hub", "all"):
        # Каналът също се помни: инак всяко пускане трупаше по един HUB.
        btn = {"inline_keyboard": [[{"text": "💬 Влез в групата и стаите", "url": GROUP_LINK}]]}
        prev = state.get("channel") or {}
        mid = prev.get("mid")
        done = False
        if mid and prev.get("text") == HUB:
            api("pinChatMessage", chat_id=CHANNEL_ID, message_id=mid,
                disable_notification="true")
            print("HUB в канала: вече е там — само го закачам")
            done = True
        elif mid:
            r = api("editMessageText", chat_id=CHANNEL_ID, message_id=mid, text=HUB,
                    parse_mode="HTML", disable_web_page_preview="true",
                    reply_markup=json.dumps(btn))
            if r.get("ok"):
                state["channel"] = {"mid": mid, "text": HUB}
                api("pinChatMessage", chat_id=CHANNEL_ID, message_id=mid,
                    disable_notification="true")
                print("HUB в канала: опреснен на място")
                done = True
            else:
                print("HUB: старият пост не се опресни — пращам нов.")
        if not done:
            r = api("sendMessage", chat_id=CHANNEL_ID, text=HUB, parse_mode="HTML",
                    disable_web_page_preview="true", reply_markup=json.dumps(btn))
            if r.get("ok"):
                new_mid = r["result"]["message_id"]
                state["channel"] = {"mid": new_mid, "text": HUB}
                api("pinChatMessage", chat_id=CHANNEL_ID, message_id=new_mid,
                    disable_notification="true")
                print("HUB в канала: закачен")
            else:
                print("HUB провал:", str(r)[:120])

    if MODE in ("rooms", "all") and CHAT_ID:
        for thread, text in ROOM_PINS.items():
            send_pin(CHAT_ID, text, thread, unpin_first=True, state=state)
            time.sleep(1.2)
        # съпорт-постът идва последен в стая 11 => той остава закаченият там.
        # Свой ключ, за да не се бие с обикновения пин на същата стая.
        send_pin(CHAT_ID, SUPPORT_POST, 11, unpin_first=False,
                 state=state, key="11-support")
        print("Стайни пинове + съпорт: готово.")

    save_hub_state(state)
    print("HUB setup — край.")

if __name__ == "__main__":
    main()
