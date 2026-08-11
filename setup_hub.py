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
                             — ПРОГНОЗИТЕ по направление, без новини
   9 Резултати и статистика  — един дневен отчет за типстъра + един за бота
  10 Печеливши фишове
  11 Въпроси и Помощ
  26 Новини                  — ВСИЧКИ новини, подредени по спорт
  27 БОТА ПРЕДРИЧА           — всички прогнози на бота
 328 Бойни спортове          — прогнозите за UFC / ММА / бокс

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


# ── ПАЗАЧЪТ ───────────────────────────────────────────────────────────────────
# Този файл го НЯМАШЕ, а е единственият, който пише ЗАКАЧЕНИ постове — тоест
# най-трайните съобщения в цялата група. И именно той веднъж вече изнесе навън
# „18+" и „залагай отговорно"; тогава текстът беше пренаписан на ръка, но нищо
# не пречеше да се върне. Предсказателят, оценителят и създателят на стаи имат
# такъв пазач от самото начало — тук зееше дупка.
#
# Правилото е просто: съмнителен текст НЕ се праща. По-добре стая без пин,
# отколкото пин, който не бива да е там — пинът се вижда от всеки, завинаги.
BANNED = ["18+", "залагай отговорно",
          "коеф", "букмейкър", "odds",
          "заложи", "финансов съвет"]


def banned_word(text):
    low = (text or "").lower()
    for w in BANNED:
        if w in low:
            return w
    return None

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
    # 🔴 ТОЗИ ПИН ЛЪЖЕШЕ (поправено 11.08.2026). Пишеше „тук пише САМО
    # човекът-типстер, ботовете нямат достъп" — а в стаята пишат ТРИ бота:
    # predictor.py слага трите фиша на деня, scorer.py отчиташе фишовете,
    # router_bot.py я ползва като резервна стая. Правило на стената, което
    # самият бот нарушава всеки ден, учи хората да не вярват на стената.
    4: block(
        "🎯 <b>ФИШОВЕ НА ДЕНЯ</b>",
        "Комбинираните фишове на бота — по няколко мача, всички трябва да познаят.",
        "Под всеки фиш стои общата вероятност. Отчитат се в 🏆 Печеливши фишове.",
        "Тук пише и човекът-типстер."),
    # ВНИМАНИЕ (поправено 04.08.2026): тези четири текста казваха „тук влизат САМО
    # срещите, прогнозите са в БОТА ПРЕДРИЧА". Собственикът после нареди обратното —
    # „не общи разписания, които нищо не значат; искам всичко прогнози" — и кодът беше
    # сменен: predictor.py праща всяка карта И в стаята на своя спорт (SPORT_ROOM),
    # а списъците със срещи са изключени по подразбиране (MATCHES_ROOM_LISTS=0).
    # Правилата на стената обаче останаха старите и си противоречаха с бота.
    5: block(
        "⚽ <b>ФУТБОЛ</b>",
        "Тук влизат <b>прогнозите за футбол</b>: избор, вероятност, звезди и числата зад мача.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
    6: block(
        "🏀 <b>БАСКЕТБОЛ</b>",
        "Тук влизат <b>прогнозите за баскетбол</b>: избор, очакван резултат, над/под точки.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
    7: block(
        "🏓 <b>ТЕНИС НА МАСА</b>",
        "Тук влизат <b>прогнозите за тенис на маса</b>: избор, най-вероятен резултат, брой геймове.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
    8: block(
        "🏐 <b>ВОЛЕЙБОЛ</b>",
        "Тук влизат <b>прогнозите за волейбол</b>: избор, резултат в сетове, над/под сетове.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
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
        "В спортните стаи новини НЕ влизат — там са прогнозите.",
        "Тих ден = няма пост. Тишината е злато."),
    27: block(
        "🤖 <b>БОТА ПРЕДРИЧА</b>",
        "Тук са <b>всички прогнози на бота</b> — всички спортове на едно място.",
        "Всяка прогноза стои и в стаята на своя спорт."),
    328: block(
        "🥊 <b>БОЙНИ СПОРТОВЕ</b>",
        "Тук влизат <b>прогнозите за бойни спортове</b>: UFC, ММА, бокс — бойци, избор, числата.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
}

# ── НОВИТЕ СТАИ (хокей, тенис, бейзбол, американски футбол) ────────────────────
# Ботът предричаше за осем спорта, а стаи имаше за пет. make_rooms.py създава
# останалите и записва номерата им в rooms_state.json.
#
# ЗАЩО ТЕКСТОВЕТЕ СА ТУК, А НЕ САМО ТАМ: make_rooms.py слага отварящия пост ВЕДНЪЖ,
# при създаването. Оттам нататък пиновете се поддържат от този файл — той е
# мястото, където се пипат всички стайни текстове. Ако новите останеха само в
# make_rooms.py, щяха да са единствените, които hub-ботът не може да опресни.
NOVI_STAI_TEKST = {
    "hockey": block(
        "🏒 <b>ХОКЕЙ</b>",
        "Тук влизат <b>прогнозите за хокей</b>: избор за мача, очаквани голове,"
        " над/под общо голове.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
    "tennis": block(
        "🎾 <b>ТЕНИС</b>",
        "Тук влизат <b>прогнозите за тенис</b>: избор, брой сетове, числата зад мача.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
    "baseball": block(
        "⚾ <b>БЕЙЗБОЛ</b>",
        "Тук влизат <b>прогнозите за бейзбол</b>: избор и очаквани рънове.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
    "amfootball": block(
        "🏈 <b>АМЕРИКАНСКИ ФУТБОЛ</b>",
        "Тук влизат <b>прогнозите за НФЛ и колежанския футбол</b>: избор,"
        " очакван резултат, над/под точки.",
        "Новините са в стая 📰 Новини · всички спортове заедно — в 🤖 БОТА ПРЕДРИЧА."),
}
ROOMS_STATE_FILE = (os.environ.get("ROOMS_STATE_FILE") or "rooms_state.json").strip()


def vlei_novite_stai():
    """Влива създадените стаи в ROOM_PINS. Липсващ файл = нищо не се променя.

    Пази се от две неща, които биха били тихи провали: номер, който вече е зает
    от закована стая (не го презаписваме), и боклук на мястото на номера.
    """
    try:
        with open(ROOMS_STATE_FILE, encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:                             # noqa: BLE001
        return []
    if not isinstance(d, dict):
        return []
    vleti = []
    for sport, zapis in d.items():
        tekst = NOVI_STAI_TEKST.get(str(sport).strip())
        if not tekst or not isinstance(zapis, dict):
            continue
        try:
            n = int(zapis.get("thread"))
        except (TypeError, ValueError):
            continue
        if n > 0 and n not in ROOM_PINS:
            ROOM_PINS[n] = tekst
            vleti.append((str(sport), n))
    return vleti
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
    lоsha = banned_word(text)
    if lоsha:
        print("  ОТКАЗ " + where + ": забранена дума (" + lоsha + ") — не пращам.")
        return
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

def diagnoza(state=None):
    """Свързани ли са каналът и групата — питаме Telegram, не помним.

    ОТГОВОРЪТ СЕ ЗАПИСВА В ТЕФТЕРА, не само се печата. Дневникът на Actions се
    чете само с админски права по API, а страницата му е тежко приложение,
    което не се рендира навсякъде. hub_state.json обаче се връща в хранилището
    от самия работен файл и се чете от всеки — тоест отговорът остава видим.

    ЗАЩО СЪЩЕСТВУВА: собственикът добавя хора в КАНАЛА и се чуди защо не се
    появяват в групата със стаите. Причината не е дефект в бота — каналът и
    групата са ДВА РАЗЛИЧНИ чата в Telegram и добавянето в единия никога не
    добавя в другия. Единственото, което ги свързва като едно, е „дискусионна
    група": тогава под всеки пост в канала излиза бутон за коментари, който
    ВКАРВА човека в групата с едно докосване.

    Свързването НЕ може да го направи бот — в Bot API няма такъв метод. Прави
    се от приложението, от собственика на канала. Затова тук само ПРОВЕРЯВАМЕ
    и казваме състоянието, за да не се гадае.
    """
    kanal = api("getChat", chat_id=CHANNEL_ID).get("result") or {}
    grupa = api("getChat", chat_id=CHAT_ID).get("result") or {} if CHAT_ID else {}
    svurzan = kanal.get("linked_chat_id")
    print("--- ДИАГНОЗА: канал <-> група ---")
    print("  канал : " + str(kanal.get("title") or "?") + "  id " + str(CHANNEL_ID))
    print("  група : " + str(grupa.get("title") or "?") + "  id " + str(CHAT_ID or "-"))
    print("  форум (стаи включени): " + ("да" if grupa.get("is_forum") else "НЕ"))
    print("  канал -> свързана група: " + str(svurzan or "НЯМА"))
    if CHAT_ID and str(svurzan or "") == str(CHAT_ID):
        print("  ✅ СВЪРЗАНИ СА. Под всеки пост в канала има бутон за коментари,")
        print("     който вкарва човека в групата с едно докосване.")
    else:
        print("  ⚠️  НЕ СА СВЪРЗАНИ. Затова добавен в канала човек НЕ влиза в групата.")
        print("     Оправя се РЪЧНО от приложението (бот не може, няма такъв метод):")
        print("     Канала -> Управление -> Дискусия -> избери групата.")
    print("  публично име на групата: @" + str(grupa.get("username") or "няма"))
    print("  връзка-покана в закачения пост: " + GROUP_LINK)
    if isinstance(state, dict):
        state["diag"] = {
            "kanal_id": str(CHANNEL_ID),
            "kanal_ime": str(kanal.get("title") or ""),
            "grupa_id": str(CHAT_ID or ""),
            "grupa_ime": str(grupa.get("title") or ""),
            "grupa_e_forum": bool(grupa.get("is_forum")),
            "grupa_username": str(grupa.get("username") or ""),
            "svurzana_grupa": str(svurzan or ""),
            "svurzani": bool(CHAT_ID and str(svurzan or "") == str(CHAT_ID)),
            "chlenove_kanal": to_int(api("getChatMemberCount",
                                         chat_id=CHANNEL_ID).get("result")),
            "chlenove_grupa": (to_int(api("getChatMemberCount",
                                          chat_id=CHAT_ID).get("result"))
                               if CHAT_ID else None),
        }
    return svurzan


def to_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def selftest():
    """Самопроверка. Този файл я нямаше — а пише най-трайните постове в групата."""
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    # --- пазачът
    check("пазачът лови 18+", banned_word("вход 18+") == "18+")
    check("пазачът лови залагай отговорно",
          banned_word("Залагай Отговорно!") == "залагай отговорно")
    check("пазачът лови коефициент", banned_word("коефициент 1.85") == "коеф")
    check("пазачът лови букмейкър", banned_word("наш букмейкър") == "букмейкър")
    check("пазачът не лови чист текст", banned_word("⚽ ФУТБОЛ · прогнози") is None)
    check("пазачът понася празно", banned_word("") is None and banned_word(None) is None)

    # --- всички закачени текстове са чисти
    for thread, text in ROOM_PINS.items():
        check("стая " + str(thread) + " е чиста", banned_word(text) is None)
        check("стая " + str(thread) + " не е празна", bool(str(text).strip()))
    check("HUB текстът е чист", banned_word(HUB) is None)
    check("съпорт-постът е чист", banned_word(SUPPORT_POST) is None)
    for sport, text in NOVI_STAI_TEKST.items():
        check("новата стая " + sport + " е чиста", banned_word(text) is None)

    # --- застоял текст: стаите вече носят ПРОГНОЗИ, не списъци със срещи
    zastoyali = [t for t in ROOM_PINS.values()
                 if "САМО срещите" in t or "САМО предстоящите" in t]
    check("няма застояли текстове (само срещите)", not zastoyali)

    # --- картата на стаите
    for n in (3, 4, 5, 6, 7, 8, 9, 10, 11, 26, 27, 328):
        check("стая " + str(n) + " има пин", n in ROOM_PINS)
    check("четирите нови спорта имат текст", len(NOVI_STAI_TEKST) == 4)
    for s in ("hockey", "tennis", "baseball", "amfootball"):
        check("има текст за " + s, s in NOVI_STAI_TEKST)

    # --- вливането на новите стаи
    _preди = len(ROOM_PINS)
    check("липсващ файл не влива нищо", vlei_novite_stai() == []
          or len(ROOM_PINS) >= _preди)

    print("САМОПРОВЕРКА НА ХЪБА: " + str(ok) + " наред, " + str(len(bad)) + " счупени")
    for b in bad:
        print("   счупено: " + b)
    return not bad


def main():
    if not BOT_TOKEN: print("Missing BOT_TOKEN"); sys.exit(1)
    state = load_hub_state()

    if MODE in ("diag", "all"):
        try:
            diagnoza(state)
        except Exception as e:      # noqa: BLE001
            print("диагнозата не мина (" + str(e)[:60] + ") — продължавам.")
        if MODE == "diag":
            save_hub_state(state)   # режим diag не пипа нищо друго
            print("Диагнозата е записана в " + HUB_STATE_FILE + ".")
            return

    if MODE in ("hub", "all") and banned_word(HUB):
        # Постът в КАНАЛА не минава през send_pin, значи има свой вход и свой
        # пазач. Без този ред дупката щеше да остане точно там, където се вижда
        # от най-много хора.
        print("ОТКАЗ канал: в HUB текста има забранена дума ("
              + str(banned_word(HUB)) + ") — не пращам.")
    elif MODE in ("hub", "all"):
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
        vleti = vlei_novite_stai()
        if vleti:
            print("Нови стаи от " + ROOMS_STATE_FILE + ": "
                  + ", ".join(s + "=" + str(n) for s, n in vleti))
        else:
            print("Няма нови стаи в " + ROOMS_STATE_FILE
                  + " — работя само със закованите.")
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
    if "--selftest" in sys.argv or os.environ.get("HUB_SELFTEST") == "1":
        sys.exit(0 if selftest() else 1)
    main()
