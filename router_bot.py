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


def pick_room(text):
    """Връща thread_id на стаята според текста на поста."""
    t = (text or "").lower()
    # РЕДЪТ: специфичните спортове преди футбола (както в Новинаря)
    for tid, pat in [SPORT_ROOMS[2], SPORT_ROOMS[3], SPORT_ROOMS[1], SPORT_ROOMS[0]]:
        if re.search(pat, t):
            return tid
    return ROOM_PICKS   # без разпознат спорт -> 🎯 Пикове на деня


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

    updates = api("getUpdates", offset=offset + 1, timeout=0,
                  allowed_updates='["channel_post"]')
    if updates is None:
        sys.exit(1)
    if not updates:
        print("Няма нови постове.")
        return

    routed = 0
    last_id = offset
    for u in updates:
        last_id = max(last_id, u.get("update_id", 0))
        post = u.get("channel_post")
        if not post:
            continue
        chat = post.get("chat") or {}
        if str(chat.get("id")) != str(CHANNEL_ID):
            continue   # не е нашият канал
        text = post.get("text") or post.get("caption") or ""
        room = pick_room(text)
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
