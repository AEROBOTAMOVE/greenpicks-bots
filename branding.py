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
CHAT_ID = os.environ.get("CHAT_ID", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
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

ROOMS = [
    (4, "picks", "ПИКОВЕ НА ДЕНЯ", "Сърцето на GREEN PICKS",
     ["Тук излизат пиковете на типстъра", "Формат: мач · пазар · коеф · логика",
      "Всеки пик се копира в стаята на спорта", "Стойност, без спам"], "green"),
    (5, "foot", "ФУТБОЛ", "Само топ лиги и големи истории",
     ["Новини от най-висшите лиги", "Мач-прегледи с H2H и форма", "Дребните лиги ги режем — тук е качество"], "green"),
    (6, "bask", "БАСКЕТБОЛ", "NBA · Евролига · и нощните",
     ["Тотали и спредове с контекст", "Умора, почивка, B2B — следим ги", "Нощната смяна отвъд океана"], "blue"),
    (7, "tt", "ТЕНИС НА МАСА", "Само сериозните турнири (WTT/ITTF)",
     ["Без нагласени лиги", "Ранглисти и H2H", "Честни прогнози, не гаранции"], "blue"),
    (8, "volley", "ВОЛЕЙБОЛ", "PlusLiga · SuperLega · световна лига",
     ["Моделът ни познава ~68% победители", "Сетове, точки, деривативи", "Нишата, която малцина следят"], "gold"),
    (9, "res", "РЕЗУЛТАТИ", "Прозрачност или нищо",
     ["Всеки пик се отчита — зелен И червен", "Нищо не се трие, никога", "Дневникът е публичен"], "green"),
    (10, "win", "ПЕЧЕЛИВШИ ФИШОВЕ", "Зелените моменти",
     ["Печелившите с изплащане в единици", "Честен трак-рекорд", "Без фалшива успеваемост"], "gold"),
    (3, "rules", "ПРАВИЛА И НАЧАЛО", "Картата на къщата + кодексът",
     ["Как работи GREEN PICKS", "Кодексът: банка, единица, дисциплина", "18+ · залагането е развлечение"], "green"),
    (11, "help", "ВЪПРОСИ И ПОМОЩ", "От основи до напреднали",
     ["Речник и стъпка-по-стъпка залагане", "Коефициенти и марж обяснени", "Няма глупави въпроси"], "blue"),
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
