# -*- coding: utf-8 -*-
# GREEN PICKS reset (clean slate). Reuses HUB / ROOM_PINS / api / send_pin from
# setup_hub.py so this file stays ASCII-only and small. Wipes messages via Bot API
# (bot is admin), keeps the forum topic-container ids, then reposts HUB + role pins.
# RESET_MODE = channel | group | all
import os
os.environ.setdefault("SUPPORT", "@greenpicks_support_bot")
import json, sys, time
import setup_hub as H

MODE = (os.environ.get("RESET_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "all")).strip()
KEEP_IDS = {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 26, 27}

def probe_max_id(chat):
    # a few retries so a transient blip does not turn the whole wipe into a no-op
    for attempt in range(3):
        r = H.api("sendMessage", chat_id=chat, text="reset", disable_notification="true")
        if r.get("ok"):
            mid = r["result"]["message_id"]
            H.api("deleteMessage", chat_id=chat, message_id=mid)
            return mid
        print("  probe attempt", attempt + 1, "failed:", str(r)[:120])
        time.sleep(2)
    return 0

def wipe(chat, keep):
    # Returns True only if the chat was reachable (max id probed). False => do NOT
    # post fresh content on top, so we never stack duplicates on an un-wiped chat.
    mx = probe_max_id(chat)
    if not mx:
        print("  WIPE ABORTED: chat unreachable", chat)
        return False
    ids = [i for i in range(1, mx + 1) if i not in keep]
    print("  wipe", chat, "max_id", mx, "to_delete", len(ids), "keep", sorted(keep) if keep else "-")
    deleted = 0
    for j in range(0, len(ids), 100):
        batch = ids[j:j + 100]
        r = H.api("deleteMessages", chat_id=chat, message_ids=json.dumps(batch))
        if not r.get("ok"):
            for i in batch:
                if H.api("deleteMessage", chat_id=chat, message_id=i).get("ok"):
                    deleted += 1
                time.sleep(0.05)
        else:
            deleted += len(batch)
        time.sleep(0.4)
    print("  delete pass done (~", deleted, "reported; Bot API does not confirm exact)")
    return True

def post_hub():
    btn = {"inline_keyboard": [[{"text": "GREEN PICKS chat", "url": H.GROUP_LINK}]]}
    r = H.api("sendMessage", chat_id=H.CHANNEL_ID, text=H.HUB, parse_mode="HTML",
              disable_web_page_preview="true", reply_markup=json.dumps(btn))
    if r.get("ok"):
        H.api("pinChatMessage", chat_id=H.CHANNEL_ID,
              message_id=r["result"]["message_id"], disable_notification="true")
        print("  HUB pinned")
    else:
        print("  HUB fail:", str(r)[:160])

def main():
    if not H.BOT_TOKEN:
        print("Missing BOT_TOKEN"); sys.exit(1)
    if MODE in ("channel", "all"):
        print("== CHANNEL wipe ==")
        if wipe(H.CHANNEL_ID, set()):
            post_hub()
        else:
            print("  CHANNEL post skipped (wipe aborted)")
    if MODE in ("group", "all"):
        if not H.CHAT_ID:
            print("  GROUP skipped: CHAT_ID not set")
        else:
            print("== GROUP wipe (keep topic containers) ==")
            if wipe(H.CHAT_ID, KEEP_IDS):
                for thread, text in H.ROOM_PINS.items():
                    H.send_pin(H.CHAT_ID, text, thread)
                    time.sleep(1.1)
                print("  room pins done")
            else:
                print("  GROUP pins skipped (wipe aborted)")
    print("reset done -", MODE)

if __name__ == "__main__":
    main()
