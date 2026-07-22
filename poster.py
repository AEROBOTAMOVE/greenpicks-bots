# -*- coding: utf-8 -*-
"""
GREEN PICKS — модул за пращане: картинка (от cards.py) + текст, в Telegram.
Общ за всички ботове. sendPhoto (multipart), с graceful fallback към sendMessage.
"""
import json, os, mimetypes, urllib.request, urllib.error

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

def _api(method):
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

def send_message(chat_id, text, thread_id=None, preview=False):
    """Прост текстов пост (HTML)."""
    import urllib.parse
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": (not preview)}
    tid = str(thread_id or "").strip()
    if tid.isdigit() and int(tid) > 1:
        payload["message_thread_id"] = int(tid)
    data = urllib.parse.urlencode(payload).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(_api("sendMessage"), data=data), timeout=25) as r:
            return json.loads(r.read()).get("ok", False)
    except urllib.error.HTTPError as e:
        print("sendMessage HTTP", e.code, e.read().decode("utf-8","replace")[:200]); return False
    except Exception as e:
        print("sendMessage FAIL:", e); return False

def send_photo(chat_id, image_path, caption="", thread_id=None):
    """Праща картинка + подпис (multipart/form-data, чист stdlib)."""
    if not os.path.exists(image_path):
        return send_message(chat_id, caption, thread_id)
    boundary = "----GreenPicksBoundary7MA4YWx"
    tid = str(thread_id or "").strip()
    fields = {"chat_id": str(chat_id), "caption": caption[:1024], "parse_mode": "HTML"}
    if tid.isdigit() and int(tid) > 1:
        fields["message_thread_id"] = tid
    body = b""
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    fname = os.path.basename(image_path)
    ctype = mimetypes.guess_type(image_path)[0] or "image/png"
    with open(image_path, "rb") as f:
        filedata = f.read()
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{fname}\"\r\n".encode()
    body += f"Content-Type: {ctype}\r\n\r\n".encode() + filedata + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(_api("sendPhoto"), data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read()).get("ok", False)
    except urllib.error.HTTPError as e:
        print("sendPhoto HTTP", e.code, e.read().decode("utf-8","replace")[:200])
        return send_message(chat_id, caption, thread_id)   # текст ако картинката пропадне
    except Exception as e:
        print("sendPhoto FAIL:", e)
        return send_message(chat_id, caption, thread_id)
