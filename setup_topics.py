# -*- coding: utf-8 -*-
"""
Еднократен скрипт: създава стаите 📰 Новини и 📅 Мачовете днес в групата
(ботът трябва да е админ с право "Manage Topics") и отпечатва thread_id-тата,
които после слагаме в GitHub vars. Пуска се веднъж, ръчно (workflow_dispatch).
"""
import json
import os
import sys
import urllib.request
import urllib.parse

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

def call(method, **params):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read())
    if not resp.get("ok"):
        print(f"{method} ERROR:", resp)
        sys.exit(1)
    return resp["result"]

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID"); sys.exit(1)

    me = call("getMe")
    print("Бот:", me.get("username"))

    t1 = call("createForumTopic", chat_id=CHAT_ID, name="📰 Новини", icon_color=16478047)
    print("NEWS_THREAD_ID =", t1["message_thread_id"])

    t2 = call("createForumTopic", chat_id=CHAT_ID, name="📅 Мачовете днес", icon_color=7322096)
    print("MATCHES_THREAD_ID =", t2["message_thread_id"])

    call("sendMessage", chat_id=CHAT_ID, message_thread_id=t1["message_thread_id"],
         text="📰 Тук Новинарят ще пуска най-важните спортни новини — 3 пъти дневно, само стойностното. 🦖")
    call("sendMessage", chat_id=CHAT_ID, message_thread_id=t2["message_thread_id"],
         text="📅 Тук Анализаторът всяка сутрин ще нарежда топ мачовете: history, форма и какво се говори. 🦖")
    print("ГОТОВО! Запиши двете числа в GitHub -> Settings -> Secrets and variables -> Actions -> Variables.")

if __name__ == "__main__":
    main()
