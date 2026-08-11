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
# Forum topic containers. 328 = "Boyni sportove" (UFC/MMA/boxing) - if it is
# missing here, the next wipe deletes the room itself. Same list as dedupe_clean.
KEEP_IDS = {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 26, 27, 328}
ROOMS_STATE_FILE = (os.environ.get("ROOMS_STATE_FILE") or "rooms_state.json").strip()

def keep_ids():
    """Hard-coded list PLUS every thread id in rooms_state.json.

    FIXED 2026-08-11. The frozen list above went stale the moment make_rooms.py
    created hockey / tennis / baseball / amfootball (threads 1961, 1963, 1965,
    1967). Those ids were not in KEEP_IDS, so a group wipe would have deleted
    the four rooms THEMSELVES - and a deleted forum topic does not come back.
    The very comment above warned about exactly this for room 328 and was still
    not enough: a frozen list only protects what somebody remembered to add.

    Returns None when the file exists but cannot be read. That is deliberate:
    unreadable state must ABORT the wipe, not silently fall back to the short
    list. Missing file is fine - it means no extra rooms were ever created.
    """
    ids = set(KEEP_IDS)
    if not os.path.exists(ROOMS_STATE_FILE):
        return ids
    try:
        with open(ROOMS_STATE_FILE, encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception as e:                                   # noqa: BLE001
        print("  rooms_state.json unreadable (" + str(e)[:80] + ")")
        return None
    if not isinstance(d, dict):
        print("  rooms_state.json is not a dict - refusing to guess")
        return None
    dobaveni = []
    for zapis in d.values():
        try:
            n = int(zapis.get("thread"))
        except (AttributeError, TypeError, ValueError):
            continue
        if n > 0 and n not in ids:
            ids.add(n)
            dobaveni.append(n)
    if dobaveni:
        print("  protected extra rooms from rooms_state.json:", sorted(dobaveni))
    return ids

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
            keep = keep_ids()
            if keep is None:
                print("  GROUP ABORTED: room state unreadable, refusing to wipe")
                print("reset done -", MODE)
                return
            # The four rooms created later (hockey/tennis/baseball/amfootball)
            # also need their pins back, exactly like the frozen ones. main() of
            # setup_hub calls this; reset.py never did, so after a reset those
            # rooms came back empty - wiped, then left without a pin.
            vleti = H.vlei_novite_stai()
            if vleti:
                print("  pins added for new rooms:", vleti)
            if wipe(CHAT_ID, keep):
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
