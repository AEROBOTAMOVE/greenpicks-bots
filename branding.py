# -*- coding: utf-8 -*-
"""
GREEN PICKS — ВИТРИНАТА 🦖 (еднократно, през Bot API — надеждно, без браузър)
MODE=logo     -> слага логото като аватар на КАНАЛА и ГРУПАТА (setChatPhoto)
MODE=welcome  -> праща + закача брандирана welcome-картичка във всяка стая
MODE=all      -> и двете
Ботът трябва да е админ с право „смяна на инфо" (за логото) и „закачане" (за pin).
"""
import json, os, sys, time, mimetypes, urllib.request, urllib.error
import cards

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")                       # групата -100...
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")  # каналът
MODE = (os.environ.get("BRAND_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "all")).strip()

def _api(m): return f"https://api.telegram.org/bot{BOT_TOKEN}/{m}"

def _multipart(method, fields, file_field=None, file_path=None):
    b = "----GPBrand7MA4"
    body = b""
    for k, v in fields.items():
        body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    if file_field and file_path and os.path.exists(file_path):
        fn = os.path.basename(file_path)
        ct = mimetypes.guess_type(file_path)[0] or "image/png"
        with open(file_path, "rb") as f:
            fd = f.read()
        body += f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{fn}\"\r\n".encode()
        body += f"Content-Type: {ct}\r\n\r\n".encode() + fd + b"\r\n"
    body += f"--{b}--\r\n".encode()
    req = urllib.request.Request(_api(method), data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={b}")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(method, "HTTP", e.code, e.read().decode("utf-8", "replace")[:200]); return {}
    except Exception as e:
        print(method, "FAIL", e); return {}

def set_logo(chat_id, name):
    r = _multipart("setChatPhoto", {"chat_id": str(chat_id)}, "photo", "cards_samples/logo.png")
    print(f"Лого {name}: {'OK' if r.get('ok') else 'ПРОВАЛ ' + str(r)[:120]}")

def send_and_pin(chat_id, image, caption, thread_id=None):
    fields = {"chat_id": str(chat_id), "caption": caption[:1024], "parse_mode": "HTML"}
    if thread_id and int(thread_id) > 1:
        fields["message_thread_id"] = str(thread_id)
    r = _multipart("sendPhoto", fields, "photo", image)
    if not r.get("ok"):
        print(f"   welcome провал: {str(r)[:120]}"); return
    mid = r["result"]["message_id"]
    p = _multipart("pinChatMessage", {"chat_id": str(chat_id), "message_id": str(mid),
                                       "disable_notification": "true"})
    print(f"   стая {thread_id}: пратено+{'закачено' if p.get('ok') else 'НЕ закачено'}")

# 🔴 ПОЧИСТЕНО НА 11.08.2026. Тези текстове се РИСУВАТ ВЪРХУ КАРТИНКИ и се
# закачат в стаите — тоест висят на стената завинаги. А в тях стояха:
#   • три забранени думи: „коеф", „Коефициенти", „18+" — същите, които всеки
#     друг бот в проекта реже с banned_word() преди да прати каквото и да е;
#   • старият бранд „GREEN PICKS" на две места, при положение че групата се
#     казва THE GREEN ROOM;
#   • „Моделът ни познава ~68% победители" — число, което НЕ Е измерено никъде
#     в този код. Истинското се чете от дневника и е в стая ✅ Резултати.
# Този файл няма пазач за думи (за разлика от останалите), затова чистото стои
# тук, в самия текст.
#
# стаите: (thread, файл-суфикс, заглавие, подзаглавие, [точки], акцент)
ROOMS = [
    (4, "picks", "ФИШОВЕ НА ДЕНЯ", "Сърцето на THE GREEN ROOM",
     ["Комбинираните фишове на бота", "Всички мачове трябва да познаят",
      "Под всеки фиш стои общата вероятност", "Отчитат се в 🏆 Печеливши фишове"], "green"),
    (5, "foot", "⚽ ФУТБОЛ", "Само топ лиги и големи истории",
     # 🔴 11.08.2026: първият ред обещаваше НОВИНИ. Новинарят има бял списък
     # само стая 26 и черен списък, в който стая 5 изрично влиза — тоест
     # обещание, което кодът физически не може да изпълни. И е върху
     # ЗАКАЧЕНА КАРТИНКА, тоест не се поправя с редакция на текст.
     ["Прогнози от най-висшите лиги", "Числата зад мача: H2H и форма", "Дребните лиги ги режем — тук е качество"], "green"),
    (6, "bask", "🏀 БАСКЕТБОЛ", "NBA · Евролига · и нощните",
     ["Тотали и спредове с контекст", "Умора, почивка, B2B — следим ги", "Нощната смяна отвъд океана"], "blue"),
    (7, "tt", "🏓 ТЕНИС НА МАСА", "Само сериозните турнири (WTT/ITTF)",
     ["Без нагласени лиги", "Ранглисти и H2H", "Честни прогнози, не гаранции"], "blue"),
    (8, "volley", "🏐 ВОЛЕЙБОЛ", "PlusLiga · SuperLega · световна лига",
     ["Сила по точки, не по краен резултат", "Сетове и дължина на мача",
      "Нишата, която малцина следят"], "gold"),
    (9, "res", "✅ РЕЗУЛТАТИ", "Прозрачност или нищо",
     ["Всеки пик се отчита — зелен И червен", "Нищо не се трие, никога", "Дневникът е публичен"], "green"),
    (10, "win", "🏆 ПЕЧЕЛИВШИ ФИШОВЕ", "Зелените моменти",
     ["Тук се отчита всеки фиш на деня", "Колко крака са минали и къде се е скъсал",
      "Без фалшива успеваемост"], "gold"),
    (3, "rules", "📌 ПРАВИЛА И НАЧАЛО", "Картата на къщата",
     ["Как работи THE GREEN ROOM", "Коя стая за какво е",
      "Всичко се отчита — и познатото, и сгрешеното"], "green"),
    # 🔴 ПОПРАВЕНО 11.08.2026. Пишеше „Отговаря човек, не робот" — но ботът
    # отговаря САМ на разпознатите въпроси (support_bot.handle_private вика
    # match_intent и връща готовия отговор, без да ги предава на никого).
    # До човек стига само неразпознатото. В същата стая висеше и текстов пин,
    # който казваше вярното — два пина с противоположни твърдения.
    (11, "help", "🆘 ВЪПРОСИ И ПОМОЩ", "Питай направо",
     ["Пишеш тук или на бота", "Ботът отговаря веднага на честите въпроси",
      "Всичко останало стига до човек"], "blue"),
]

def do_welcome():
    for thread, sfx, title, sub, bullets, acc in ROOMS:
        img = f"cards_samples/w_{sfx}.png"
        cards.room_welcome(title, sub, bullets, acc, img)
        send_and_pin(CHAT_ID, img, f"<b>{title}</b> — {sub}", thread)
        time.sleep(1.5)

def main():
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN"); sys.exit(1)
    os.makedirs("cards_samples", exist_ok=True)
    cards.logo_avatar("cards_samples/logo.png")
    if MODE in ("logo", "all"):
        set_logo(CHANNEL_ID, "канал")
        if CHAT_ID: set_logo(CHAT_ID, "група")
    if MODE in ("welcome", "all"):
        if CHAT_ID: do_welcome()
    print("Витрината — готово.")

if __name__ == "__main__":
    main()
