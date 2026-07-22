# -*- coding: utf-8 -*-
"""
GREEN PICKS — HUB + СТАЙНИ ПИНОВЕ (еднократно, Bot API — надеждно)
- Канал: 1 закачен HUB (приветствие + навигация + съпорт), ТЕКСТ (не картинка)
- Стаи: кратък ТЕКСТ пин във всяка + откачва старите welcome-КАРТИЧКИ (unpin)
- Съпорт-пост в 🆘 стая
MODE=hub|rooms|all
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
GROUP_LINK = os.environ.get("GROUP_LINK", "https://t.me/+_oYsaYaVKU80Yjc0")
SUPPORT = os.environ.get("SUPPORT", "@greenpicks_support")
MODE = (os.environ.get("HUB_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "all")).strip()

def api(method, **params):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=25) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(method, "HTTP", e.code, e.read().decode("utf-8","replace")[:160]); return {}
    except Exception as e:
        print(method, "FAIL", e); return {}

FOOT = "🟢 GREEN PICKS · прогноза от статистика, не гаранция · 18+"

HUB = (
"🟢 <b>GREEN PICKS — прогнози на база статистика</b>\n\n"
"Показваме кой мач как стои по числата. Честно.\n"
"📊 Всеки пик е <b>ПРОГНОЗА</b> от статистика — не гаранция, не „сигурен залог“.\n"
"🔒 Нищо не трием. Загубите остават видими завинаги.\n"
"⚠️ 18+ · залагай отговорно · това не е финансов съвет.\n\n"
"<b>Какво тече тук:</b>\n"
"☀️ 08:00 — Топ новина на деня\n"
"🎯 През деня — пикове от типстъра\n"
"✅ Вечер — резултати от горещите първенства\n"
"🌙 20:00 — втора топ новина\n"
"📊 21:00 — Обзорът на бота (числата за деня)\n\n"
f"🆘 <b>Помощ и контакт:</b> {SUPPORT} · или в стая 🆘 Помощ\n"
"👇 Влез в групата и стаите по спорт от бутона."
)

ROOM_PINS = {
    3:  "📌 <b>ПРАВИЛА И НАЧАЛО</b>\nКак работи GREEN PICKS + кодексът. Виж закачените обучителни постове. 18+.",
    4:  "🎯 <b>ПИКОВЕ НА ДЕНЯ</b>\nТук се копира всеки пик от канала. Формат: мач · пазар · коеф · логика.\nПрогноза от статистика, не гаранция.",
    5:  "⚽ <b>ФУТБОЛ</b>\nНовини от топ лиги + мачове. Следим: форма, H2H, стойност.",
    6:  "🏀 <b>БАСКЕТБОЛ</b>\nNBA/Евролига + нощна смяна. Следим: темпо, почивка, контузии.",
    7:  "🏓 <b>ТЕНИС НА МАСА</b>\nСамо сериозни турнири (WTT/ITTF). Ранглисти, H2H. Внимаваме с нагласени.",
    8:  "🏐 <b>ВОЛЕЙБОЛ</b>\nPlusLiga/SuperLega/световна. Сетове, тотал сетове, хендикап.",
    9:  "✅ <b>РЕЗУЛТАТИ И СТАТИСТИКА</b>\nЧестен отчет на всеки пик — зелено печели / червено губи. Нищо не се трие.",
    10: "🏆 <b>ПЕЧЕЛИВШИ ФИШОВЕ</b>\nСамо спечелилите, като витрина. Пълният отчет (и загубите) са в ✅ Резултати.",
    26: "📰 <b>НОВИНИ</b>\nОбщи спортни новини. По-специфичните са в стаите по спорт.",
    27: "📅 <b>МАЧОВЕ ДНЕС</b>\nПрограмата на деня (08:30). Топ мачове с H2H и форма.",
}
SUPPORT_POST = (
"🆘 <b>ПОМОЩ И КОНТАКТ</b>\n\n"
"Въпрос, идея или проблем?\n"
f"✍️ Пиши на екипа: {SUPPORT}\n"
"💬 Или публично тук — отговаряме пред всички.\n\n"
"<b>Често:</b>\n"
"• Пикът е ПРОГНОЗА от статистика, не гаранция.\n"
"• Единица = 1-2% от банката. Дисциплина преди всичко.\n"
"• Показваме и загубите — прозрачност или нищо.\n\n"
"Отговаряме до 24ч. 💚 GREEN PICKS"
)

def send_pin(chat, text, thread=None, unpin_first=False):
    if unpin_first and thread:
        api("unpinAllForumTopicMessages", chat_id=chat, message_thread_id=thread)
    p = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if thread and int(thread) > 1:
        p["message_thread_id"] = thread
    r = api("sendMessage", **p)
    if not r.get("ok"):
        print("  send fail:", str(r)[:100]); return
    mid = r["result"]["message_id"]
    pin = api("pinChatMessage", chat_id=chat, message_id=mid, disable_notification="true")
    print(f"  {'канал' if str(chat)==str(CHANNEL_ID) else 'стая '+str(thread)}: {'закачено' if pin.get('ok') else 'пратено (не закач.)'}")

def main():
    if not BOT_TOKEN: print("Missing BOT_TOKEN"); sys.exit(1)
    if MODE in ("hub", "all"):
        btn = {"inline_keyboard": [[{"text": "💬 Влез в групата и стаите", "url": GROUP_LINK}]]}
        r = api("sendMessage", chat_id=CHANNEL_ID, text=HUB, parse_mode="HTML",
                disable_web_page_preview="true", reply_markup=json.dumps(btn))
        if r.get("ok"):
            api("pinChatMessage", chat_id=CHANNEL_ID, message_id=r["result"]["message_id"], disable_notification="true")
            print("HUB в канала: закачен ✅")
        else:
            print("HUB провал:", str(r)[:120])
    if MODE in ("rooms", "all") and CHAT_ID:
        for thread, text in ROOM_PINS.items():
            send_pin(CHAT_ID, text, thread, unpin_first=True)
            time.sleep(1.2)
        send_pin(CHAT_ID, SUPPORT_POST, 11, unpin_first=False)
        print("Стайни пинове + съпорт: готово.")
    print("HUB setup — край.")

if __name__ == "__main__":
    main()
