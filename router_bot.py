# -*- coding: utf-8 -*-
"""
GREEN PICKS — БОТ №3 „РУТЕРЪТ" 🚚
СЪРЦЕТО НА СИСТЕМАТА: типстърът поства САМО в канала (@greenpicksbg),
рутерът хваща всеки нов пост и го КОПИРА в правилната стая на групата:
  #Футбол/футболен текст  -> стая ⚽ (5)
  #Баскетбол              -> стая 🏀 (6)
  #ТенисМаса              -> стая 🏓 (7)
  #Волейбол               -> стая 🏐 (8)
  без разпознат спорт     -> стая 🎯 Пикове на деня (4)
Ботът трябва да е админ и в КАНАЛА (за да вижда постовете), и в ГРУПАТА.
Пуска се на всеки 10 мин от GitHub Actions. Помни докъде е стигнал в router_state.json.

⚠️ ДЕЛИ ОПАШКАТА СЪС support_bot.py (същия BOT_TOKEN). Опашката на Telegram е
ЕДНА за бот, а потвърждаването е ГЛОБАЛНО: getUpdates с offset=N трие ВСИЧКИ
ъпдейти под N, независимо чии са и независимо какво пише в allowed_updates.
Докато рутерът минаваше сам, всяко негово потвърждение изяждаше и личните
съобщения до бота — въпросите на хората изчезваха безшумно, без ред в лога.
Затова тук има две правила, огледални на тези в support_bot.py:
  1. ЕДИН РЕЧНИК — искаме СЪЮЗА (channel_post + message + callback_query).
     Два различни списъка на един бот се презаписват и Telegram спира да
     създава ъпдейтите на другия.
  2. ЧУЖДОТО НЕ СЕ МАРКИРА — спираме на ПЪРВОТО лично съобщение и оставяме
     offset-а пред него. Съпортът ще го вземе до 15 минути и опашката тръгва.
Двамата се изчакват. Спре ли единият да се пуска, другият изостава, докато
Telegram сам не изхвърли ъпдейта (24 часа). Не е елегантно, но не губи поща.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
import urllib.parse

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")                    # групата (-100...)
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")  # каналът
STATE_FILE = "router_state.json"

# стаите по спорт (тема-id в групата)
ROOM_PICKS = int(os.environ.get("PICKS_THREAD_ID", "4"))
ROOM_RESULTS = int(os.environ.get("RESULTS_THREAD_ID", "9"))   # ✅ Резултати
ROOM_WINS = int(os.environ.get("WINS_THREAD_ID", "10"))        # 🏆 Печеливши фишове
SPORT_ROOMS = [
    (int(os.environ.get("FOOTBALL_THREAD_ID", "5")),
     r"#футбол|футбол|цска|левски|лудогорец|champions league|premier league|la liga|serie a|bundesliga|голмайстор|football|soccer"),
    (int(os.environ.get("BASKET_THREAD_ID", "6")),
     r"#баскетбол|#баскет|баскет|basketball|\bnba\b|\bwnba\b|евролига|euroleague"),
    (int(os.environ.get("TT_THREAD_ID", "7")),
     r"#тенисмаса|тенис на маса|table tennis|пинг понг"),
    (int(os.environ.get("VOLLEY_THREAD_ID", "8")),
     r"#волейбол|#волей|волейбол|volleyball"),
]

# маркери за РЕЗУЛТАТ (не прогноза!): ✅❌, уцелен/паднал, отчет...
RESULT_PAT = r"✅|❌|уцели|уцелен|паднал|спечелихме|загубихме|не мина|отчет|равносметка|#резултат"
# маркери за ПЕЧЕЛИВШ ФИШ
WIN_PAT = r"✅|спечелихме|печеливш|ударихме|зелен[оа]|\+\s?\d+([.,]\d+)?\s?(ед|лв|unit)|#печеливш"


def api(method, **params):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"{method} HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"{method} FAIL: {e}")
        return None
    if not resp.get("ok"):
        print(f"{method} ERROR:", resp)
        return None
    return resp["result"]


def pick_rooms(text):
    """Връща СПИСЪК от стаи — един пост може да отиде в 2-3 стаи!
    Пример: губещ футболен фиш -> ⚽ + ✅ Резултати;
            печеливш баскет фиш -> 🏀 + ✅ + 🏆."""
    t = (text or "").lower()
    rooms = []
    # 1) всички разпознати спортове (комбо-фиш с 2 спорта -> 2 стаи)
    for tid, pat in [SPORT_ROOMS[2], SPORT_ROOMS[3], SPORT_ROOMS[1], SPORT_ROOMS[0]]:
        if re.search(pat, t) and tid not in rooms:
            rooms.append(tid)
    # 2) резултат/отчет -> и в ✅
    if re.search(RESULT_PAT, t) and ROOM_RESULTS not in rooms:
        rooms.append(ROOM_RESULTS)
    # 3) печеливш фиш -> и в 🏆
    if re.search(WIN_PAT, t) and ROOM_WINS not in rooms:
        rooms.append(ROOM_WINS)
    if not rooms:
        rooms = [ROOM_PICKS]   # без нищо разпознато -> 🎯 Пикове на деня
    return rooms[:3]           # максимум 3 стаи, без спам


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        sys.exit(1)

    offset = 0
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8-sig") as f:
                st = json.load(f)
            offset = int(st.get("offset", 0)) if isinstance(st, dict) else 0
        except (json.JSONDecodeError, OSError, ValueError):
            print("WARN: повреден router state — започвам от 0.")

    # СЪЮЗЪТ, не само channel_post: стесним ли списъка, Telegram спира да създава
    # личните съобщения до бота и съпортът остава без поща (виж главата на файла).
    updates = api("getUpdates", offset=offset + 1, timeout=0,
                  allowed_updates='["channel_post", "message", "callback_query"]')
    if updates is None:
        sys.exit(1)
    if not updates:
        print("Няма нови постове.")
        return

    routed = 0
    last_id = offset
    for u in updates:
        # ЧУЖДОТО НЕ СЕ МАРКИРА. offset-ът е монотонен: потвърдя ли ъпдейт 105,
        # Telegram трие и 104 — включително въпрос на човек, на който съпортът
        # още не е отговорил. „Прескочи, но не маркирай" не съществува в този
        # API, затова СПИРАМ пред първото чуждо съобщение.
        if "message" in u or "callback_query" in u:
            print("Ъпдейт " + str(u.get("update_id", 0)) + " е на съпорта — спирам")
            print("тук, за да не му го изтрия. Offset остава " + str(last_id) + ".")
            break
        last_id = max(last_id, u.get("update_id", 0))
        post = u.get("channel_post")
        if not post:
            continue
        chat = post.get("chat") or {}
        if str(chat.get("id")) != str(CHANNEL_ID):
            continue   # не е нашият канал
        text = post.get("text") or post.get("caption") or ""
        for room in pick_rooms(text):
            res = api("copyMessage", chat_id=CHAT_ID,
                      from_chat_id=CHANNEL_ID,
                      message_id=post.get("message_id"),
                      message_thread_id=room)
            if res is not None:
                routed += 1
                print(f"Пост {post.get('message_id')} -> стая {room}")
            else:
                print(f"Пост {post.get('message_id')} НЕ мина (стая {room}).")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"offset": last_id}, f)
    print(f"Разнесени {routed} поста. Offset={last_id}.")


if __name__ == "__main__":
    main()
