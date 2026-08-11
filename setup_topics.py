# -*- coding: utf-8 -*-
"""
Еднократен скрипт: създава стаите 📰 Новини и 📅 Мачовете днес в групата
(ботът трябва да е админ с право "Manage Topics") и отпечатва thread_id-тата,
които после слагаме в GitHub vars. Пуска се веднъж, ръчно (workflow_dispatch).
"""
import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

class ApiError(Exception):
    """Читаема Telegram-грешка (напр. 400 chat is not a forum) — не убива печата."""
    pass

def call(method, **params):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
            desc = body.get("description", str(body))
        except Exception:
            desc = "HTTP " + str(e.code)
        raise ApiError(f"{method} ERROR {e.code}: {desc}")
    if not resp.get("ok"):
        raise ApiError(f"{method} ERROR: {resp}")
    return resp["result"]

# Потвърдената карта на стаите (същата като в setup_hub.py / reset.py KEEP_IDS)
ROOM_MAP = (
    (1,   "Общ чат"),
    (3,   "Правила и Начало"),
    # 🔴 ПОПРАВЕНО 11.08.2026: ботът пише там всеки ден (трите фиша).
    (4,   "Фишове на деня — комбинираните фишове на бота и на типстъра"),
    # 🔴 ПОПРАВЕНО 11.08.2026: стаите по спорт носят ПРОГНОЗИТЕ за спорта,
    # не списъци със срещи (predictor.py праща всяка карта и там).
    (5,   "Футбол — прогнозите за футбол"),
    (6,   "Баскетбол — прогнозите за баскетбол"),
    (7,   "Тенис на маса — прогнозите за тенис на маса"),
    (8,   "Волейбол — прогнозите за волейбол"),
    (9,   "Резултати и статистика"),
    (10,  "Печеливши фишове"),
    (11,  "Въпроси и Помощ"),
    (26,  "Новини — всички новини, подредени по спорт"),
    (27,  "БОТА ПРЕДРИЧА — всички прогнози на бота"),
    (328, "Бойни спортове — само боевете"),
)

def print_room_map():
    print("Карта на стаите (потвърдена):")
    for tid, name in ROOM_MAP:
        print("  " + str(tid).rjust(3) + "  " + name)

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID"); sys.exit(1)

    # ПАЗАЧ СРЕЩУ ДУБЛИКАТИ: има ли ВЕЧЕ зададено thread id (дори само едното),
    # отказваме да създаваме каквото и да е и само печатаме картата на стаите.
    news_id = os.environ.get("NEWS_THREAD_ID", "").strip()
    matches_id = os.environ.get("MATCHES_THREAD_ID", "").strip()
    if news_id or matches_id:
        print("ОТКАЗ: стаите вече съществуват — нищо ново няма да се създава.")
        if news_id:
            print("NEWS_THREAD_ID =", news_id)
        if matches_id:
            print("MATCHES_THREAD_ID =", matches_id)
        print_room_map()
        return

    try:
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
    except (urllib.error.HTTPError, ApiError) as e:
        # напр. 400 "chat is not a forum" — печатаме грешката И картата, чак после излизаме
        print("ГРЕШКА:", e)
        print_room_map()
        sys.exit(1)
    print("ГОТОВО! Запиши двете числа в GitHub → Settings → Secrets and variables → Actions → Variables.")
    print_room_map()

if __name__ == "__main__":
    main()
