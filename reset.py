# -*- coding: utf-8 -*-
# GREEN PICKS reset (clean slate). This file is ASCII-only; the Bulgarian content
# (HUB / ROOM_PINS / SUPPORT_POST / GROUP_LINK) is imported from setup_hub as DATA.
# Own api() that respects Telegram 429 retry_after so every send/pin completes.
# Wipes messages via Bot API (bot is admin), keeps the forum topic-container ids,
# then reposts HUB (channel) and the role pins (group). RESET_MODE = channel|group|all
import os
os.environ.setdefault("SUPPORT", "@greenpicks_support_bot")
import json, sys, time, urllib.request, urllib.parse, urllib.error
import setup_hub as H

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
MODE = (os.environ.get("RESET_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "all")).strip()
KEEP_IDS = {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 26, 27}

def api(method, **params):
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
                print("  429 on", method, "- waiting", ra + 1, "s")
                time.sleep(ra + 1)
                continue
            print(method, "HTTP", e.code, body[:140])
            return {"ok": False, "error": body[:140]}
        except Exception as e:
            return {"ok": False, "error": str(e)[:140]}
    return {"ok": False, "error": "429 retries exhausted"}

def probe_max_id(chat):
    for attempt in range(3):
        r = api("sendMessage", chat_id=chat, text="reset", disable_notification="true")
        if r.get("ok"):
            mid = r["result"]["message_id"]
            api("deleteMessage", chat_id=chat, message_id=mid)
            return mid
        print("  probe attempt", attempt + 1, "failed:", str(r)[:120])
        time.sleep(2)
    return 0

def wipe(chat, keep):
    # True only if reachable; False => do NOT post fresh content on an un-wiped chat.
    mx = probe_max_id(chat)
    if not mx:
        print("  WIPE ABORTED: chat unreachable", chat)
        return False
    ids = [i for i in range(1, mx + 1) if i not in keep]
    print("  wipe", chat, "max_id", mx, "to_delete", len(ids), "keep", sorted(keep) if keep else "-")
    deleted = 0
    for j in range(0, len(ids), 100):
        batch = ids[j:j + 100]
        r = api("deleteMessages", chat_id=chat, message_ids=json.dumps(batch))
        if not r.get("ok"):
            for i in batch:
                if api("deleteMessage", chat_id=chat, message_id=i).get("ok"):
                    deleted += 1
                time.sleep(0.05)
        else:
            deleted += len(batch)
        time.sleep(0.4)
    print("  delete pass done (~", deleted, "reported; Bot API does not confirm exact)")
    return True

def send_pin(chat, text, thread=None):
    p = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if thread and int(thread) > 1:
        p["message_thread_id"] = thread
    r = api("sendMessage", **p)
    if not r.get("ok"):
        print("  room", thread, "SEND FAIL:", str(r)[:100]); return
    mid = r["result"]["message_id"]
    pin = api("pinChatMessage", chat_id=chat, message_id=mid, disable_notification="true")
    print("  room", thread, ("pinned" if pin.get("ok") else "posted (not pinned)"))

def post_hub():
    btn = {"inline_keyboard": [[{"text": "GREEN PICKS chat", "url": H.GROUP_LINK}]]}
    r = api("sendMessage", chat_id=CHANNEL_ID, text=H.HUB, parse_mode="HTML",
            disable_web_page_preview="true", reply_markup=json.dumps(btn))
    if r.get("ok"):
        api("pinChatMessage", chat_id=CHANNEL_ID,
            message_id=r["result"]["message_id"], disable_notification="true")
        print("  HUB pinned")
    else:
        print("  HUB fail:", str(r)[:160])

def main():
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN"); sys.exit(1)
    if MODE in ("channel", "all"):
        print("== CHANNEL wipe ==")
        if wipe(CHANNEL_ID, set()):
            post_hub()
        else:
            print("  CHANNEL post skipped (wipe aborted)")
    if MODE in ("group", "all"):
        if not CHAT_ID:
            print("  GROUP skipped: CHAT_ID not set")
        else:
            print("== GROUP wipe (keep topic containers) ==")
            if wipe(CHAT_ID, KEEP_IDS):
                for thread, text in H.ROOM_PINS.items():
                    send_pin(CHAT_ID, text, thread)
                    time.sleep(1.5)
                send_pin(CHAT_ID, H.SUPPORT_POST, 11)   # help room (kept out of ROOM_PINS)
                print("  room pins done")
            else:
                print("  GROUP pins skipped (wipe aborted)")
    print("reset done -", MODE)

if __name__ == "__main__":
    main()
