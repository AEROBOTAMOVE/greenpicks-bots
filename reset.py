# -*- coding: utf-8 -*-
# GREEN PICKS reset (clean slate). This file is ASCII-only; the Bulgarian content
# (HUB / ROOM_PINS / SUPPORT_POST / GROUP_LINK) is imported from setup_hub as DATA.
# Own api() that respects Telegram 429 retry_after so every send/pin completes.
# Wipes messages via Bot API (bot is admin), keeps the forum topic-container ids,
# then reposts HUB (channel) and the role pins (group).
#
# LOCKED 2026-09-01. RESET_MODE has NO default any more (it used to be "all")
# and a real delete needs RESET_POTVARZHDAVAM to equal FRAZA exactly plus a
# cap in RESET_TAVAN. Without the phrase this file is a DRY RUN: it counts and
# prints, it deletes nothing. See "THE LOCK" below.
import os
# FIXED 2026-08-11: this pinned @greenpicks_support_bot into the HUB, the pin of
# room 11 and the support post - all three at once. That bot does not run:
# support_bot.py calls it "the separate bot, IF it ever starts" and support.yml
# says its token is "if ever added to Secrets". The live one is the main bot.
# hub.yml and seed.yml already pass the right handle; only reset.py did not.
os.environ.setdefault("SUPPORT", "@green_picks_info_bot")
import json, sys, time, urllib.request, urllib.parse, urllib.error
import setup_hub as H

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004403334702")
# ------------------------------------------------------------------ THE LOCK
# 2026-09-01. Until today this file had ZERO self-checks and RESET_MODE
# defaulted to "all". Two clicks in GitHub Actions - "Run workflow", then the
# green "Run workflow" - wiped the WHOLE channel AND the WHOLE group, because
# the dropdown already stood on "all". A deleted Telegram message does not
# come back. This is the only action in the project with no way back, and it
# was the only action with no lock.
#
# Three independent keys. A real delete needs all three:
#   1. SCOPE   RESET_MODE must say channel|group|all. Empty = do nothing.
#              "all" is nobody's default any more; it has to be typed.
#   2. PHRASE  RESET_POTVARZHDAVAM must equal FRAZA exactly. Absent = dry run.
#              Present but wrong = REFUSED, because a typo means the owner
#              meant to delete, and turning that into a quiet dry run would
#              look exactly like work that happened.
#   3. CAP     RESET_TAVAN limits deletions for the WHOLE run. Channel and
#              group share ONE counter - a per-chat cap would let scope "all"
#              delete twice the number the owner typed.
FRAZA = "IZTRII VSICHKO"
VALIDNI_OBHVATI = ("channel", "group", "all")
TAVAN_PODRAZBIRANE = 500
TAVAN_MAX = 100000
RESET_YML = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         ".github", "workflows", "reset.yml")


def izbran_obhvat(env_mode=None, argv1=None):
    """The raw scope string. The default is EMPTY - never "all"."""
    return str(env_mode or argv1 or "").strip()


def normalizirai_obhvat(mode):
    """(chats, note). [] = nothing to do. None = refuse, do not guess."""
    m = izbran_obhvat(mode).lower()
    if not m or m in ("nishto", "none", "no", "skip"):
        return ([], "no scope given - nothing to do ('all' is not a default)")
    if m not in VALIDNI_OBHVATI:
        return (None, "unknown scope " + repr(m[:24]) + " - expected "
                + "/".join(VALIDNI_OBHVATI))
    if m == "all":
        return (["channel", "group"], "scope all = channel AND group")
    return ([m], "scope " + m)


def suho_li(potv):
    """(dry_run, refusal). No phrase = dry run. Wrong phrase = refuse."""
    p = str(potv or "").strip()
    if not p:
        return (True, None)
    if p == FRAZA:
        return (False, None)
    return (True, "RESET_POTVARZHDAVAM is set but is not the phrase"
            " - refusing the whole run (nothing was deleted)")


def chetitavan(raw):
    """(cap, refusal). Garbage is REFUSED, never silently defaulted."""
    s = str(raw if raw is not None else "").strip()
    if not s:
        return (TAVAN_PODRAZBIRANE, None)
    try:
        n = int(s)
    except (TypeError, ValueError):
        return (None, "RESET_TAVAN is not a number: " + repr(s[:24]))
    if n < 1:
        return (None, "RESET_TAVAN must be 1 or more, got " + str(n))
    if n > TAVAN_MAX:
        print("  RESET_TAVAN " + str(n) + " is over the ceiling "
              + str(TAVAN_MAX) + " - clamped down")
        return (TAVAN_MAX, None)
    return (n, None)


def za_triene(mx, keep, tavan, veche=0):
    """Ids this run may touch: oldest first, minus the kept ones, minus cap."""
    try:
        mx = int(mx)
    except (TypeError, ValueError):
        return []
    pazeni = set(keep or ())
    ids = [i for i in range(1, mx + 1) if i not in pazeni]
    ostava = max(0, int(tavan) - int(veche))
    return ids[:ostava]


def pechati_plan(obhvat, bel, suho, tavan, otkaz):
    """What this run WILL do - printed BEFORE anything is touched."""
    print("=" * 62)
    print("RESET PLAN (printed before anything is touched)")
    if obhvat is None:
        kade = "REFUSED"
    elif not obhvat:
        kade = "nothing"
    else:
        kade = ", ".join(obhvat)
    print("  scope  :", kade, "|", bel)
    print("  action :", ("DRY RUN - counts only, deletes nothing" if suho
                         else "REAL DELETE - THERE IS NO WAY BACK"))
    print("  phrase :", ("absent or wrong -> dry run" if suho else "accepted"))
    print("  cap    :", (tavan if tavan is not None else "REFUSED"),
          "messages for the WHOLE run (channel + group share it)")
    if not suho and obhvat:
        print("  channel:", CHANNEL_ID if "channel" in obhvat else "-")
        print("  group  :", ((CHAT_ID or "(CHAT_ID not set)")
                             if "group" in obhvat else "-"))
    if otkaz:
        print("  REFUSING:", otkaz)
    print("=" * 62)
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

def wipe(chat, keep, suho=True, tavan=TAVAN_PODRAZBIRANE, broyach=None):
    """(reachable, deleted, capped).

    reachable=False => do NOT post fresh content on an un-wiped chat.
    capped=True     => the ceiling cut the list, so the chat is only HALF
                       wiped and fresh pins must not go on top of it.
    suho=True       => count and print, touch nothing. This is the default on
                       purpose: the safe value has to be the lazy one.
    """
    veche = broyach[0] if broyach else 0
    mx = probe_max_id(chat)
    if not mx:
        print("  WIPE ABORTED: chat unreachable", chat)
        return (False, 0, False)
    vsichki = [i for i in range(1, mx + 1) if i not in set(keep or ())]
    ids = za_triene(mx, keep, tavan, veche)
    capped = len(ids) < len(vsichki)
    print("  chat", chat, "max_id", mx, "candidates", len(vsichki),
          "this run", len(ids), "cap left", max(0, int(tavan) - int(veche)),
          "keep", sorted(keep) if keep else "-")
    if capped:
        print("  CAP REACHED:", len(ids), "of", len(vsichki),
              "- raise RESET_TAVAN or run again. Nothing will be reposted.")
    if broyach:
        broyach[0] = veche + len(ids)
    if suho:
        print("  DRY RUN: deleting nothing. WOULD delete", len(ids),
              "ids, from", (ids[0] if ids else "-"),
              "to", (ids[-1] if ids else "-"))
        return (True, 0, capped)
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
    return (True, deleted, capped)

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
    if "--selftest" in sys.argv or "selftest" in sys.argv:
        return selftest()
    surov = izbran_obhvat(os.environ.get("RESET_MODE"),
                          sys.argv[1] if len(sys.argv) > 1 else "")
    obhvat, bel = normalizirai_obhvat(surov)
    suho, otkaz_f = suho_li(os.environ.get("RESET_POTVARZHDAVAM"))
    tavan, otkaz_t = chetitavan(os.environ.get("RESET_TAVAN"))
    pechati_plan(obhvat, bel, suho, tavan, otkaz_f or otkaz_t)
    if obhvat is None:
        print("REFUSED:", bel)
        return 2
    if otkaz_f:
        print("REFUSED:", otkaz_f)
        return 2
    if otkaz_t:
        print("REFUSED:", otkaz_t)
        return 2
    if not obhvat:
        print("nothing to do -", bel)
        return 0
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN")
        return 1
    broyach = [0]
    if "channel" in obhvat:
        print("== CHANNEL", ("dry run" if suho else "wipe"), "==")
        dostapen, _iztriti, capped = wipe(CHANNEL_ID, set(), suho, tavan, broyach)
        if not dostapen:
            print("  CHANNEL post skipped (wipe aborted)")
        elif suho:
            print("  DRY: the HUB would be reposted and pinned here")
        elif capped:
            print("  CHANNEL post skipped (cap reached - only half wiped)")
        else:
            post_hub()
    if "group" in obhvat:
        if not CHAT_ID:
            print("  GROUP skipped: CHAT_ID not set")
        else:
            print("== GROUP", ("dry run" if suho else "wipe"),
                  "(keep topic containers) ==")
            keep = keep_ids()
            if keep is None:
                print("  GROUP ABORTED: room state unreadable, refusing to wipe")
                print("reset done -", surov)
                return 2
            # The four rooms created later (hockey/tennis/baseball/amfootball)
            # also need their pins back, exactly like the frozen ones. main() of
            # setup_hub calls this; reset.py never did, so after a reset those
            # rooms came back empty - wiped, then left without a pin.
            vleti = H.vlei_novite_stai()
            if vleti:
                print("  pins added for new rooms:", vleti)
            dostapen, _iztriti, capped = wipe(CHAT_ID, keep, suho, tavan, broyach)
            if not dostapen:
                print("  GROUP pins skipped (wipe aborted)")
            elif suho:
                print("  DRY: would repin", len(H.ROOM_PINS) + 1, "room pins")
            elif capped:
                print("  GROUP pins skipped (cap reached - only half wiped)")
            else:
                for thread, text in H.ROOM_PINS.items():
                    send_pin(CHAT_ID, text, thread)
                    time.sleep(1.5)
                send_pin(CHAT_ID, H.SUPPORT_POST, 11)   # help room (kept out of ROOM_PINS)
                print("  room pins done")
    print("reset done -", surov, ("(dry run)" if suho else "(REAL)"),
          "touched", broyach[0], "of at most", tavan)
    return 0


def selftest():
    """Self-checks for THE LOCK. No network, no Telegram, no token needed.

    Every check below exists because a mutation of the guard it watches was
    proven to break it. A guard whose mutation survives is decoration, not a
    guard - it was removed rather than left in to look reassuring.
    """
    ok, bad = 0, []

    def check(ime, uslovie):
        nonlocal ok
        if uslovie:
            ok += 1
        else:
            bad.append(ime)

    # ------------------------------------------------------------ 1. SCOPE
    check("the default scope is empty", izbran_obhvat(None, None) == "")
    check("the default scope is NOT 'all'", izbran_obhvat(None, None) != "all")
    check("env beats argv", izbran_obhvat("group", "all") == "group")
    check("argv is used when env is empty", izbran_obhvat("", "channel") == "channel")
    check("empty scope touches nothing", normalizirai_obhvat("")[0] == [])
    check("'nishto' touches nothing", normalizirai_obhvat("nishto")[0] == [])
    check("no scope is not a refusal, just nothing",
          normalizirai_obhvat("")[0] is not None)
    check("'all' has to be asked for",
          normalizirai_obhvat("all")[0] == ["channel", "group"])
    check("'channel' is only the channel", normalizirai_obhvat("channel")[0] == ["channel"])
    check("'group' is only the group", normalizirai_obhvat("group")[0] == ["group"])
    check("scope is case insensitive",
          normalizirai_obhvat("  ALL ")[0] == ["channel", "group"])
    check("an unknown scope refuses", normalizirai_obhvat("vsichko")[0] is None)
    check("an unknown scope is NOT silently 'all'",
          normalizirai_obhvat("vsichko")[0] != ["channel", "group"])
    check("the refusal says what was expected",
          "expected" in str(normalizirai_obhvat("boklyuk")[1]))

    # ------------------------------------------------------------ 2. PHRASE
    check("no phrase = dry run", suho_li("") == (True, None))
    check("None = dry run", suho_li(None)[0] is True)
    check("the exact phrase unlocks", suho_li(FRAZA)[0] is False)
    check("surrounding spaces are forgiven", suho_li(" " + FRAZA + " ")[0] is False)
    check("a wrong phrase does NOT unlock", suho_li("da, iztrii")[0] is True)
    check("a wrong phrase is refused loudly", bool(suho_li("da")[1]))
    check("wrong case does NOT unlock", suho_li(FRAZA.lower())[0] is True)
    check("a near miss does NOT unlock", suho_li(FRAZA + "!")[0] is True)
    check("'yes' does not unlock", suho_li("yes")[0] is True)
    check("the phrase is not guessable in one word",
          len(FRAZA) >= 8 and " " in FRAZA)

    # ------------------------------------------------------------ 3. CAP
    check("unset cap falls back to the default",
          chetitavan("") == (TAVAN_PODRAZBIRANE, None))
    check("the default cap is finite and modest",
          0 < TAVAN_PODRAZBIRANE <= 5000)
    check("a number is taken as given", chetitavan("7") == (7, None))
    check("garbage in the cap is REFUSED", chetitavan("mnogo")[0] is None)
    check("garbage is not silently the default",
          chetitavan("mnogo")[0] != TAVAN_PODRAZBIRANE)
    check("zero is refused", chetitavan("0")[0] is None)
    check("a negative cap is refused", chetitavan("-5")[0] is None)
    check("above the ceiling is clamped down",
          chetitavan(str(TAVAN_MAX * 2))[0] == TAVAN_MAX)

    # ------------------------------------------------------- 4. THE CAP BITES
    check("the cap really cuts the list", len(za_triene(1000, set(), 10)) == 10)
    check("oldest first, deterministically", za_triene(1000, set(), 3) == [1, 2, 3])
    check("the cap is SHARED across the run", za_triene(1000, set(), 10, 10) == [])
    check("a partly used cap leaves the rest",
          len(za_triene(1000, set(), 10, 7)) == 3)
    check("cap 0 deletes nothing", za_triene(100, set(), 0) == [])
    check("kept ids are never in the list",
          not (set(za_triene(20, {5, 7, 328}, 100)) & {5, 7, 328}))
    check("an unreachable chat yields nothing", za_triene(0, set(), 500) == [])
    check("garbage max_id yields nothing", za_triene(None, set(), 500) == [])

    # --------------------------------------------------- 5. THE ROOMS SURVIVE
    check("room 328 is still hard-coded", 328 in KEEP_IDS)
    check("the hard-coded list is not empty", len(KEEP_IDS) >= 10)
    import tempfile
    import shutil as _sh
    _d = tempfile.mkdtemp()
    _star_rs = globals()["ROOMS_STATE_FILE"]
    try:
        _p = os.path.join(_d, "rs.json")
        with open(_p, "w", encoding="utf-8") as _f:
            _f.write('{"hockey": {"thread": 1961}}')
        globals()["ROOMS_STATE_FILE"] = _p
        check("rooms from the state file are protected", 1961 in (keep_ids() or set()))
        with open(_p, "w", encoding="utf-8") as _f:
            _f.write("{ this is not json")
        check("unreadable room state ABORTS the wipe", keep_ids() is None)
        globals()["ROOMS_STATE_FILE"] = os.path.join(_d, "nyama.json")
        check("a missing state file is fine", keep_ids() == set(KEEP_IDS))
    finally:
        globals()["ROOMS_STATE_FILE"] = _star_rs
        _sh.rmtree(_d, ignore_errors=True)

    # ------------------------------------------------- 6. DRY RUN TOUCHES NOTHING
    _star = (globals()["probe_max_id"], globals()["api"], globals()["time"])

    class _NoSleep(object):
        @staticmethod
        def sleep(_x):
            return None
    vikani = []
    globals()["time"] = _NoSleep
    globals()["probe_max_id"] = lambda chat: 50
    globals()["api"] = lambda method, **kw: (vikani.append(method),
                                             {"ok": True})[1]
    try:
        del vikani[:]
        dostapen, iztriti, capped = wipe("X", set(), True, 10, [0])
        check("a dry run is reachable but deletes nothing",
              dostapen is True and iztriti == 0)
        check("a dry run calls the API zero times", vikani == [])
        check("a dry run reports that the cap bit", capped is True)
        br = [0]
        wipe("X", set(), True, 10, br)
        check("a dry run advances the shared counter too", br[0] == 10)
        br = [0]
        wipe("X", set(), True, 500, br)
        check("under the cap nothing is reported as capped", br[0] == 50)

        del vikani[:]
        br = [0]
        dostapen, iztriti, capped = wipe("X", set(), False, 10, br)
        check("a real run deletes at most the cap", iztriti == 10)
        check("a real run does call the API", "deleteMessages" in vikani)
        check("a real run advances the counter", br[0] == 10)
        del vikani[:]
        _dost, iztriti2, _c = wipe("X", set(), False, 10, br)
        check("the second chat gets nothing once the cap is used up",
              iztriti2 == 0)
        del vikani[:]
        _dost, iztriti3, _c = wipe("X", {i for i in range(1, 51)}, False, 500, [0])
        check("kept ids are never deleted for real", iztriti3 == 0)
        globals()["probe_max_id"] = lambda chat: 0
        dostapen, iztriti, capped = wipe("X", set(), False, 10, [0])
        check("an unreachable chat aborts instead of guessing",
              dostapen is False and iztriti == 0)
    finally:
        (globals()["probe_max_id"], globals()["api"],
         globals()["time"]) = _star

    # ------------------------------------------------------ 7. THE PLAN IS PRINTED
    import io as _io
    _buf, _so = _io.StringIO(), sys.stdout
    try:
        sys.stdout = _buf
        pechati_plan(["channel", "group"], "scope all", False, 7, None)
        pechati_plan([], "nothing", True, 500, None)
    finally:
        sys.stdout = _so
    _t = _buf.getvalue()
    check("the plan warns there is no way back", "NO WAY BACK" in _t)
    check("the plan names the dry run", "DRY RUN" in _t)
    check("the plan prints the cap", " 7 " in _t or "7 messages" in _t)

    # ------------------------------------------------- 8. THE OTHER HALF: THE YML
    try:
        with open(RESET_YML, encoding="utf-8") as _f:
            _y = _f.read()
    except Exception:                                        # noqa: BLE001
        _y = ""
    check("the workflow file is readable", bool(_y))
    check("the workflow no longer defaults to all", "default: 'all'" not in _y)
    check("the workflow default is the harmless one", "default: 'nishto'" in _y)
    check("the workflow asks for the phrase", "RESET_POTVARZHDAVAM" in _y)
    check("the workflow spells the phrase out", FRAZA in _y)
    check("the workflow passes a cap", "RESET_TAVAN" in _y)

    # ---------------------------------------------------------- 9. THE SOURCE
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as _f:
            _s = _f.read()
    except Exception:                                        # noqa: BLE001
        _s = ""
    check("this file is readable", bool(_s))
    # NB: the literal is BUILT, not written out. A check that spells the
    # forbidden string would find ITSELF in the source and fail forever.
    _zabraneno = "else " + chr(34) + "all" + chr(34)
    check("no 'all' fallback survives in the source", _zabraneno not in _s)
    check("the file stayed ASCII", all(ord(c) < 128 for c in _s))
    check("at least 12 checks ran", ok >= 12)

    print("SELFTEST: %d/%d PASS" % (ok, ok + len(bad)))
    for b in bad:
        print("   BROKEN: " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
