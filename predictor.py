# -*- coding: utf-8 -*-
"""
THE GREEN ROOM — БОТ „ПРЕДСКАЗАТЕЛЯТ" 🧠🔢

Истинска статистическа прогноза. Не усещане, не „сигурен мач" — модел.

ЕДИН ИЗХОД: стая 27 „БОТА ПРЕДРИЧА" (PREDICT_THREAD_ID).
Нищо друго. Този файл физически няма функция за канал, а стая 4 (човешките
фишове) и стая 26 (новините) са заковани като забранени в post_predict().

МОДЕЛИТЕ (само стандартна библиотека — математиката е писана на ръка):
  ⚽ ФУТБОЛ — Поасон.
       Сила в атака и защита на всеки отбор спрямо средното ниво в извадката,
       свити към средното заради малката извадка (Bayes-style shrinkage).
       -> очаквани голове lambda_home / lambda_away (домакинството е включено)
       -> матрица от Поасон -> 1 / X / 2, над 2.5 гола, и двата бележат,
          най-вероятен точен резултат.
  🏀 БАСКЕТБОЛ — темпо и ефективност.
       Отбелязани и допуснати точки за мач -> проекция на двата резултата,
       преднина -> вероятност през логистична крива.
  🏐 ВОЛЕЙБОЛ — модел по сетове.
       Дял спечелени сети -> вероятност за отделен сет -> 3-0 / 3-1 / 3-2.
  🏓 ТЕНИС НА МАСА — Elo от последните мачове.
       Малката извадка и непознатата сила на съперниците свиват разликата.

ЧЕСТНОСТТА Е ПРОДУКТЪТ:
  - Всяка карта носи звезди за увереност, изведени от РЕАЛНАТА извадка и от
    това колко категорични са числата. Малка извадка = ниска увереност, точка.
  - Няма ли достатъчно данни — казваме „твърде малко данни, не гадаем" и
    пропускаме мача. Не си измисляме число.
  - Не дава ли денят нищо убедително — пишем точно това. Мълчанието е злато.
  - Никакви букмейкъри, никакви коефициенти, никакво „заложи сега".
    Публикуваме вероятност, извадка и разсъждение. 18+.

ENV:
  BOT_TOKEN, CHAT_ID            — както при другите ботове
  PREDICT_THREAD_ID  (27)       — единствената разрешена стая
  MAX_PICKS          (3)        — колко карти максимум за едно пускане
  PREDICT_POOL       (10)       — колко срещи гледаме под лупата
  PREDICT_PER_SPORT  (3)        — най-много кандидати от един спорт
  PREDICT_MIN_STRENGTH (0.16)   — прагът „има ли изобщо превес"
  PREDICT_DRY_RUN    (0/1)      — 1 = само печата картите, не праща нищо
  SPORTSDB_KEY, FOOTBALL_DATA_KEY — през matches_bot

Пускане:
  python predictor.py             — истинско пускане (или dry run по env)
  python predictor.py selftest    — само математиката, без мрежа

Бележка за деплой: файлът е писан БЕЗ обратни наклонени черти (нов ред = NL).
Пращаме сами, а не през poster.send_message, защото при 429 ни трябва
retry_after — poster го не връща.
"""
import html
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import matches_bot as MB   # само като библиотека — MB.main() НЕ се вика при import

NL = chr(10)
NL2 = chr(10) + chr(10)
Q1 = chr(8222)     # „
Q2 = chr(8220)     # “
DASH = chr(8211)   # –
RULE = chr(9472) * 18   # ──────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "-1004426592150")
PREDICT_THREAD = (os.environ.get("PREDICT_THREAD_ID") or "27").strip()

# 🚫 Стаята на човека-типстер и стаята на новините. Ботът няма работа там.
FORBIDDEN_THREADS = {"4", "26"}
ALLOWED_THREADS = {PREDICT_THREAD}

DRY_RUN = (os.environ.get("PREDICT_DRY_RUN") or "").strip() in ("1", "true", "yes", "да")


def env_int(name, default, lo, hi):
    try:
        v = int((os.environ.get(name) or "").strip())
    except ValueError:
        v = default
    return max(lo, min(hi, v))


def env_float(name, default, lo, hi):
    try:
        v = float((os.environ.get(name) or "").strip())
    except ValueError:
        v = default
    return max(lo, min(hi, v))


MAX_PICKS = env_int("MAX_PICKS", 3, 1, 5)
POOL = env_int("PREDICT_POOL", 10, 1, 24)
PER_SPORT = env_int("PREDICT_PER_SPORT", 3, 1, 8)
MIN_STRENGTH = env_float("PREDICT_MIN_STRENGTH", 0.16, 0.0, 0.9)
SEND_GAP = 2.2          # секунди между съобщенията — 429 не ни е приятел

# ---------------------------------------------------------------- МОДЕЛНИ КОНСТАНТИ
# Всяка е избрана съзнателно и е записана тук, за да може да бъде оспорена.
MAXG = 10               # докъде смятаме матрицата от Поасон (при lambda<=4.5 остатъкът е нищожен)

FOOT_PRIOR = 1.35       # голове на отбор на мач — типично за силна европейска лига
# Защо изобщо свиваме: при 5 мача грешката на средното е колкото самата разлика
# между отборите. Пет псевдо-мача = при извадка 5 вярваме на половина на данните,
# при извадка 10 — на две трети. Скучно, но честно.
FOOT_SHRINK = 5.0
FOOT_HOME = 1.13        # домакините вкарват ~13% повече от неутралното
FOOT_AWAY = 0.88        # гостите ~12% по-малко (двете заедно пазят общото ниво)
FOOT_LAM_MIN, FOOT_LAM_MAX = 0.25, 4.5

BASK_HCA = 2.5          # домакинско предимство в точки (NBA-ниво, стабилно от години)
BASK_SIGMA = 12.0       # стандартно отклонение на маржа за мач (NBA e ~11-13 точки)
# Логистична крива със същото стандартно отклонение: scale = sigma*sqrt(3)/pi ~ 6.6.
# Проверка: 6 точки преднина -> ~71%, 10 точки -> ~82%. Точно както е в реалността.
BASK_SCALE = BASK_SIGMA * math.sqrt(3.0) / math.pi
BASK_MARGIN_MAX = 25.0
# Свиване към нивото на самата среща (не към NBA, за да не счупим Евролигата).
# При 5 мача шумът в средното е ~5 точки, а истинската разлика в класата ~6 —
# затова четири псевдо-мача, тоест ~55% тежест на данните. Иначе 5 мача правят
# всеки отбор или машина, или трагедия.
BASK_SHRINK = 4.0

VOL_PSEUDO = 3.0        # псевдо-сети от двете страни — пази срещу 5:0 в извадката
VOL_HOME_LOGIT = 0.14   # домакинството на сет (~+3.5 пункта) -> ~+8 пункта на мач
# Таван: сметката приема сетовете за независими, а в реалния мач те са свързани.
# 0.72 на сет = таван ~86% на мач. Над това не се правим на ясновидци.
VOL_PSET_MIN, VOL_PSET_MAX = 0.28, 0.72

TT_K = 24.0             # Elo K — къса памет, защото гледаме само последните мачове
TT_START = 1500.0
TT_UNKNOWN_OPP = 1500.0
TT_SHRINK_N = 8.0       # колкото по-малко мачове, толкова по-свита разликата
TT_P_MIN, TT_P_MAX = 0.10, 0.90

# Минимална извадка на отбор, за да смятаме изобщо
MIN_PER_SIDE = {"football": 4, "basketball": 4, "volleyball": 3, "tabletennis": 4}
RECENT_N_SDB = 5        # TheSportsDB (безплатно) дава последните 5 — това е таванът
RECENT_N_FD = 10        # football-data.org дава сезона -> вземаме последните 10

MODEL_NAME = {
    "football": "Поасон по атака и защита",
    "basketball": "темпо и ефективност",
    "volleyball": "вероятност за сет",
    "tabletennis": "Elo от последните мачове",
}

STAR_WORD = {1: "ниска увереност", 2: "средна увереност", 3: "добра увереност"}


# ---------------------------------------------------------------- ДРЕБНИ ИНСТРУМЕНТИ
def esc(x):
    return html.escape(str(x if x is not None else ""))


def clip(text, limit=3900):
    if len(text) <= limit:
        return text
    return text[:limit] + NL + "…(отрязано)"


def pad(s, n):
    s = str(s if s is not None else "")
    if len(s) > n:
        s = s[:max(1, n - 1)] + "…"
    return s + " " * max(0, n - len(s))


def pct(p):
    return str(int(round(float(p) * 100.0))) + "%"


def to_num(x):
    try:
        if x is None or str(x).strip() == "":
            return None
        return int(float(x))
    except (TypeError, ValueError):
        return None


def mean(xs):
    xs = list(xs)
    return sum(xs) / float(len(xs)) if xs else 0.0


def n_match(n):
    """1 среща, 2 срещи — дребно, но липсата му се вижда веднага."""
    return f"{n} среща" if int(n) == 1 else f"{n} срещи"


def date_bg(now):
    wd = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"][now.weekday()]
    return f"{wd}, {now.day}.{now.month:02d}"


# ---------------------------------------------------------------- ЕДИНСТВЕНИЯТ ИЗХОД
def tg_send(text, thread_id):
    """Праща с уважение към 429: чете retry_after и чака, вместо да блъска."""
    payload = {"chat_id": str(CHAT_ID), "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": "true"}
    tid = str(thread_id or "").strip()
    if tid.isdigit() and int(tid) > 1:
        payload["message_thread_id"] = tid
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    for attempt in range(4):
        data = urllib.parse.urlencode(payload).encode()
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=25) as r:
                return bool(json.loads(r.read().decode("utf-8", "replace")).get("ok"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            wait = 0
            try:
                wait = int(((json.loads(raw) or {}).get("parameters") or {}).get("retry_after") or 0)
            except Exception:
                wait = 0
            if e.code == 429 and attempt < 3:
                wait = wait if wait > 0 else 5
                print(f"429 — чакам {wait + 1} сек и пробвам пак")
                time.sleep(wait + 1)
                continue
            print("sendMessage HTTP", e.code, raw[:180])
            return False
        except Exception as ex:
            print("sendMessage FAIL:", str(ex)[:140])
            if attempt < 3:
                time.sleep(3)
                continue
            return False
    return False


def post_predict(text, thread_id=None):
    """ЕДИНСТВЕНИЯТ изход на Предсказателя. Пазачът е ТУК, не по-нагоре.
    Всичко, което този бот произвежда, влиза само в стая 27 „БОТА ПРЕДРИЧА".
    Канал няма — този файл няма функция, която да праща в канал."""
    tid = str(thread_id if thread_id is not None else PREDICT_THREAD).strip()
    if tid in FORBIDDEN_THREADS:
        print(f"ОТКАЗ: стая {tid} е забранена (човешки фишове / новини).")
        return False
    if tid not in ALLOWED_THREADS:
        print(f"ОТКАЗ: стая {tid} не е стаята на Предсказателя ({PREDICT_THREAD}).")
        return False
    if not tid.isdigit() or int(tid) <= 1:
        print(f"WARN: невалиден thread id {tid} — не пращам.")
        return False
    body = clip(text)
    if DRY_RUN:
        print(RULE)
        print(body)
        print(RULE)
        return True
    if not CHAT_ID or not BOT_TOKEN:
        print("Няма BOT_TOKEN/CHAT_ID — пропускам.")
        return False
    return tg_send(body, tid)


# ---------------------------------------------------------------- МАТЕМАТИКА (на ръка)
def poisson_pmf(k, lam):
    """P(X = k) при среден брой lam. Без scipy — exp и factorial от math."""
    if k < 0:
        return 0.0
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def poisson_matrix(lam_h, lam_a, maxg=MAXG):
    """Съвместното разпределение на резултата, нормирано до сума 1."""
    ph = [poisson_pmf(i, lam_h) for i in range(maxg + 1)]
    pa = [poisson_pmf(j, lam_a) for j in range(maxg + 1)]
    total = sum(ph) * sum(pa)
    if total <= 0:
        return [[0.0] * (maxg + 1) for _ in range(maxg + 1)]
    return [[ph[i] * pa[j] / total for j in range(maxg + 1)] for i in range(maxg + 1)]


def logistic(x):
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def logit(p):
    p = min(max(float(p), 1e-6), 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def shrink(sample_mean, prior, n, k):
    """Свиване към средното: при малко мачове вярваме повече на нивото, не на извадката."""
    if n <= 0:
        return float(prior)
    return (float(sample_mean) * n + float(prior) * k) / (n + k)


def clampf(x, lo, hi):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------- ДАННИ
_recent_cache = {}


def sane_record(bucket, gf, ga):
    """Пази срещу боклук в източника (точки, записани като сетове, и подобни)."""
    if gf is None or ga is None or gf < 0 or ga < 0:
        return False
    if bucket == "football":
        return gf <= 15 and ga <= 15
    if bucket == "basketball":
        return 40 <= gf <= 200 and 40 <= ga <= 200
    if bucket == "volleyball":
        return max(gf, ga) <= 3 and (gf + ga) <= 5 and max(gf, ga) >= 2
    if bucket == "tabletennis":
        return max(gf, ga) <= 4 and (gf + ga) <= 7 and max(gf, ga) >= 2
    return True


def sdb_recent(bucket, team_id, team_name, limit=RECENT_N_SDB):
    """Последните мачове на отбор от TheSportsDB, вече нормализирани."""
    out = []
    for e in MB.get_last_events(team_id)[:limit + 3]:
        hs, as_ = to_num(e.get("intHomeScore")), to_num(e.get("intAwayScore"))
        if hs is None or as_ is None:
            continue
        tid = str(team_id or "")
        hid, aid = str(e.get("idHomeTeam") or ""), str(e.get("idAwayTeam") or "")
        if tid and hid == tid:
            is_home = True
        elif tid and aid == tid:
            is_home = False
        elif team_name and e.get("strHomeTeam") == team_name:
            is_home = True
        elif team_name and e.get("strAwayTeam") == team_name:
            is_home = False
        else:
            continue    # не можем да кажем от коя страна е бил — не гадаем
        gf, ga = (hs, as_) if is_home else (as_, hs)
        if not sane_record(bucket, gf, ga):
            continue
        out.append({"gf": gf, "ga": ga, "home": is_home,
                    "date": (e.get("dateEvent") or "")[:10],
                    "opp": (e.get("strAwayTeam") if is_home else e.get("strHomeTeam")) or ""})
        if len(out) >= limit:
            break
    return out


def fd_recent(team_id, limit=RECENT_N_FD):
    """Последните изиграни мачове от football-data.org (по-дълбока история)."""
    data = MB.fd_get(f"/teams/{team_id}/matches?status=FINISHED")
    ms = sorted(data.get("matches") or [], key=lambda m: m.get("utcDate") or "", reverse=True)
    out = []
    for m in ms:
        ft = (m.get("score") or {}).get("fullTime") or {}
        hg, ag = to_num(ft.get("home")), to_num(ft.get("away"))
        if hg is None or ag is None:
            continue
        is_home = (m.get("homeTeam") or {}).get("id") == team_id
        gf, ga = (hg, ag) if is_home else (ag, hg)
        if not sane_record("football", gf, ga):
            continue
        out.append({"gf": gf, "ga": ga, "home": is_home,
                    "date": (m.get("utcDate") or "")[:10],
                    "opp": ((m.get("awayTeam") if is_home else m.get("homeTeam")) or {}).get("name") or ""})
        if len(out) >= limit:
            break
    return out


def recent_for(fx, side):
    """Последните мачове на едната страна, независимо кой двигател е дал срещата."""
    team_id = fx.get("home_id") if side == "home" else fx.get("away_id")
    team_name = fx.get("home") if side == "home" else fx.get("away")
    if not team_id:
        return []
    key = (fx.get("src"), str(team_id))
    if key in _recent_cache:
        return _recent_cache[key]
    try:
        if fx.get("src") == "fd":
            recs = fd_recent(team_id)
        else:
            recs = sdb_recent(fx["bucket"], team_id, team_name)
    except Exception as e:
        print(f"форма {team_name}: {str(e)[:90]}")
        recs = []
    _recent_cache[key] = recs
    return recs


def h2h_for(fx):
    """Директните мачове — само контекст и мъничко доверие, не са в модела."""
    st = {"hw": 0, "dr": 0, "aw": 0, "tot": 0}
    try:
        if fx.get("src") == "fd" and fx.get("fd_id"):
            agg, _ms = MB.fd_h2h(fx["fd_id"])
            ha, aa = (agg.get("homeTeam") or {}), (agg.get("awayTeam") or {})
            st["hw"] = MB.to_int(ha.get("wins"))
            st["aw"] = MB.to_int(aa.get("wins"))
            st["dr"] = MB.to_int(ha.get("draws"))
            st["tot"] = MB.to_int(agg.get("numberOfMatches"), st["hw"] + st["dr"] + st["aw"])
        else:
            evs = MB.get_h2h(fx["home"], fx["away"])
            if evs:
                st["hw"], st["dr"], st["aw"] = MB.h2h_summary(fx["home"], fx["away"], evs)
                st["tot"] = len(evs)
    except Exception as e:
        print(f"h2h {fx.get('home')}: {str(e)[:90]}")
    return st

# ---------------------------------------------------------------- ⚽ ФУТБОЛ (Поасон)
def league_level(all_recs, prior=FOOT_PRIOR):
    """Средно голове на отбор на мач в извадката, свито към разумното ниво."""
    if not all_recs:
        return prior
    n = len(all_recs)
    m = mean(r["gf"] for r in all_recs)
    lvl = shrink(m, prior, n, 20.0)      # 20 псевдо-мача: една вечер не пренаписва нивото
    return clampf(lvl, 0.8, 2.2)


def model_football(hr, ar, lvl):
    n_h, n_a = len(hr), len(ar)
    gf_h, ga_h = mean(r["gf"] for r in hr), mean(r["ga"] for r in hr)
    gf_a, ga_a = mean(r["gf"] for r in ar), mean(r["ga"] for r in ar)

    att_h = shrink(gf_h, lvl, n_h, FOOT_SHRINK) / lvl
    def_h = shrink(ga_h, lvl, n_h, FOOT_SHRINK) / lvl
    att_a = shrink(gf_a, lvl, n_a, FOOT_SHRINK) / lvl
    def_a = shrink(ga_a, lvl, n_a, FOOT_SHRINK) / lvl

    lam_h = clampf(lvl * att_h * def_a * FOOT_HOME, FOOT_LAM_MIN, FOOT_LAM_MAX)
    lam_a = clampf(lvl * att_a * def_h * FOOT_AWAY, FOOT_LAM_MIN, FOOT_LAM_MAX)

    mx = poisson_matrix(lam_h, lam_a)
    p_home = p_draw = p_away = p_over = p_btts = 0.0
    best_p, best_i, best_j = 0.0, 0, 0
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            p = mx[i][j]
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p
            if i + j >= 3:
                p_over += p
            if i >= 1 and j >= 1:
                p_btts += p
            if p > best_p:
                best_p, best_i, best_j = p, i, j
    return {"lam_h": lam_h, "lam_a": lam_a, "p_home": p_home, "p_draw": p_draw,
            "p_away": p_away, "p_over": p_over, "p_btts": p_btts,
            "top_score": (best_i, best_j, best_p), "lvl": lvl,
            "gf_h": gf_h, "ga_h": ga_h, "gf_a": gf_a, "ga_a": ga_a,
            "n_h": n_h, "n_a": n_a}


# ---------------------------------------------------------------- 🏀 БАСКЕТБОЛ
def model_basketball(hr, ar):
    n_h, n_a = len(hr), len(ar)
    pf_h, pa_h = mean(r["gf"] for r in hr), mean(r["ga"] for r in hr)
    pf_a, pa_a = mean(r["gf"] for r in ar), mean(r["ga"] for r in ar)
    # Нивото на самата среща — свиваме към него, за да не разчитаме на 5 мача.
    lvl = (pf_h + pa_h + pf_a + pa_a) / 4.0
    sf_h = shrink(pf_h, lvl, n_h, BASK_SHRINK)
    sa_h = shrink(pa_h, lvl, n_h, BASK_SHRINK)
    sf_a = shrink(pf_a, lvl, n_a, BASK_SHRINK)
    sa_a = shrink(pa_a, lvl, n_a, BASK_SHRINK)
    exp_h = (sf_h + sa_a) / 2.0 + BASK_HCA / 2.0
    exp_a = (sf_a + sa_h) / 2.0 - BASK_HCA / 2.0
    margin = clampf(exp_h - exp_a, -BASK_MARGIN_MAX, BASK_MARGIN_MAX)
    p_home = logistic(margin / BASK_SCALE)
    return {"exp_h": exp_h, "exp_a": exp_a, "total": exp_h + exp_a, "margin": margin,
            "p_home": p_home, "p_away": 1.0 - p_home, "lvl": lvl,
            "pf_h": pf_h, "pa_h": pa_h, "pf_a": pf_a, "pa_a": pa_a,
            "n_h": n_h, "n_a": n_a}


# ---------------------------------------------------------------- 🏐 ВОЛЕЙБОЛ
def set_outcomes(p):
    """Best-of-5 при независими сетове: 3-0 = p^3, 3-1 = 3p^3q, 3-2 = 6p^3q^2."""
    q = 1.0 - p
    return p ** 3, 3.0 * (p ** 3) * q, 6.0 * (p ** 3) * (q ** 2)


def model_volleyball(hr, ar):
    sw_h, sl_h = sum(r["gf"] for r in hr), sum(r["ga"] for r in hr)
    sw_a, sl_a = sum(r["gf"] for r in ar), sum(r["ga"] for r in ar)
    ph = (sw_h + VOL_PSEUDO) / float(sw_h + sl_h + 2.0 * VOL_PSEUDO)
    pa = (sw_a + VOL_PSEUDO) / float(sw_a + sl_a + 2.0 * VOL_PSEUDO)
    p_set = logistic(logit(ph) - logit(pa) + VOL_HOME_LOGIT)
    p_set = clampf(p_set, VOL_PSET_MIN, VOL_PSET_MAX)   # без екстраполация в облаците
    h30, h31, h32 = set_outcomes(p_set)
    a30, a31, a32 = set_outcomes(1.0 - p_set)
    return {"p_set": p_set, "p_home": h30 + h31 + h32, "p_away": a30 + a31 + a32,
            "h": (h30, h31, h32), "a": (a30, a31, a32),
            "sw_h": sw_h, "sl_h": sl_h, "sw_a": sw_a, "sl_a": sl_a,
            "n_h": len(hr), "n_a": len(ar)}


# ---------------------------------------------------------------- 🏓 ТЕНИС НА МАСА (Elo)
def elo_from(recs, k=TT_K, start=TT_START, opp=TT_UNKNOWN_OPP):
    """Elo само от собствените последни резултати. Силата на съперника е
    неизвестна -> приемаме среден съперник и после свиваме разликата."""
    r = float(start)
    for rec in reversed(recs):     # от най-стария към най-новия
        s = 1.0 if rec["gf"] > rec["ga"] else (0.0 if rec["gf"] < rec["ga"] else 0.5)
        e = 1.0 / (1.0 + 10.0 ** ((opp - r) / 400.0))
        r += k * (s - e)
    return r


def model_tabletennis(hr, ar):
    r_h, r_a = elo_from(hr), elo_from(ar)
    n = len(hr) + len(ar)
    factor = n / (n + TT_SHRINK_N) if n > 0 else 0.0
    diff = (r_h - r_a) * factor
    p_home = clampf(1.0 / (1.0 + 10.0 ** (-diff / 400.0)), TT_P_MIN, TT_P_MAX)
    w_h = sum(1 for r in hr if r["gf"] > r["ga"])
    w_a = sum(1 for r in ar if r["gf"] > r["ga"])
    return {"r_h": r_h, "r_a": r_a, "diff": diff, "raw_diff": r_h - r_a, "factor": factor,
            "p_home": p_home, "p_away": 1.0 - p_home,
            "w_h": w_h, "l_h": len(hr) - w_h, "w_a": w_a, "l_a": len(ar) - w_a,
            "n_h": len(hr), "n_a": len(ar)}


# ---------------------------------------------------------------- УВЕРЕНОСТ
def strength_binary(p):
    """Колко далеч от чиста монета е числото: 50% -> 0, 100% -> 1."""
    return clampf(abs(float(p) - 0.5) * 2.0, 0.0, 1.0)


def strength_1x2(p1, px, p2):
    """1/X/2 има три изхода — базата е 1/3, не 1/2."""
    return clampf((max(p1, px, p2) - 1.0 / 3.0) * 1.5, 0.0, 1.0)


def grade(bucket, n_eff, strength):
    """Звездите идват от РЕАЛНАТА извадка и от категоричността. Нищо друго."""
    score = 0.55 * min(1.0, n_eff / 14.0) + 0.45 * min(1.0, strength / 0.40)
    stars = 3 if score >= 0.70 else (2 if score >= 0.45 else 1)
    if n_eff < 8:
        stars = 1
    elif n_eff < 12:
        stars = min(stars, 2)
    if bucket == "tabletennis":
        stars = min(stars, 2)   # непозната сила на съперниците — три звезди не заслужаваме
    return stars


# ---------------------------------------------------------------- АНАЛИЗ НА ЕДНА СРЕЩА
def analyse(fx, lvl_football):
    """Връща готов за карта анализ или (None, причина). Никога не измисля число."""
    bucket = fx["bucket"]
    need = MIN_PER_SIDE.get(bucket, 4)
    hr, ar = recent_for(fx, "home"), recent_for(fx, "away")
    if len(hr) < need or len(ar) < need:
        return None, f"твърде малко данни ({len(hr)} и {len(ar)} мача, трябват по {need})"

    n_eff = float(len(hr) + len(ar))
    rows, extra, why = [], [], []

    if bucket == "football":
        m = model_football(hr, ar, lvl_football)
        rows = [("1 " + fx["home"], m["p_home"]), ("X равен", m["p_draw"]), ("2 " + fx["away"], m["p_away"])]
        extra = [
            f"Над 2.5 гола: <b>{pct(m['p_over'])}</b>  ·  И двата бележат: <b>{pct(m['p_btts'])}</b>",
            f"Очаквани голове: {m['lam_h']:.2f} {DASH} {m['lam_a']:.2f}",
        ]
        why = [
            f"{fx['home']}: {m['gf_h']:.1f} вкарани и {m['ga_h']:.1f} допуснати гола за мач ({m['n_h']} мача)",
            f"{fx['away']}: {m['gf_a']:.1f} вкарани и {m['ga_a']:.1f} допуснати гола за мач ({m['n_a']} мача)",
            f"Средно ниво в извадката: {m['lvl']:.2f} гола на отбор; домакинството е включено в очакваните",
            f"Най-вероятен точен резултат: {m['top_score'][0]}:{m['top_score'][1]} ({pct(m['top_score'][2])})",
        ]
        strength = max(strength_1x2(m["p_home"], m["p_draw"], m["p_away"]),
                       strength_binary(m["p_over"]), strength_binary(m["p_btts"]))

    elif bucket == "basketball":
        m = model_basketball(hr, ar)
        rows = [(fx["home"], m["p_home"]), (fx["away"], m["p_away"])]
        extra = [f"Очаквани точки: {m['exp_h']:.0f} {DASH} {m['exp_a']:.0f} (общо {m['total']:.0f})"]
        why = [
            f"{fx['home']}: {m['pf_h']:.1f} отбелязани и {m['pa_h']:.1f} допуснати точки за мач ({m['n_h']} мача)",
            f"{fx['away']}: {m['pf_a']:.1f} отбелязани и {m['pa_a']:.1f} допуснати точки за мач ({m['n_a']} мача)",
            f"Проекция след свиване на малката извадка: преднина {m['margin']:+.1f} точки за домакина "
            f"(домакинството тежи {BASK_HCA:.1f} т.)",
            f"Преднината става вероятност през логистична крива: {BASK_SIGMA:.0f} точки = едно стандартно отклонение",
        ]
        strength = strength_binary(m["p_home"])

    elif bucket == "volleyball":
        m = model_volleyball(hr, ar)
        rows = [(fx["home"], m["p_home"]), (fx["away"], m["p_away"])]
        fav_home = m["p_home"] >= m["p_away"]
        trio = m["h"] if fav_home else m["a"]
        fav = fx["home"] if fav_home else fx["away"]
        labels = ["3-0", "3-1", "3-2"]
        best = max(range(3), key=lambda i: trio[i])
        extra = [
            f"Вероятност за отделен сет: <b>{pct(m['p_set'] if fav_home else 1.0 - m['p_set'])}</b> за {esc(fav)}",
            f"Разпределение за {esc(fav)}: 3-0 {pct(trio[0])} · 3-1 {pct(trio[1])} · 3-2 {pct(trio[2])}",
            f"Най-вероятен резултат: {labels[best]} за {esc(fav)} ({pct(trio[best])})",
        ]
        why = [
            f"{fx['home']}: {m['sw_h']}:{m['sl_h']} сета в последните {m['n_h']} мача",
            f"{fx['away']}: {m['sw_a']}:{m['sl_a']} сета в последните {m['n_a']} мача",
            "Сметката приема сетовете за независими — при обрат в мача това е приблизително",
        ]
        strength = strength_binary(m["p_home"])

    elif bucket == "tabletennis":
        m = model_tabletennis(hr, ar)
        rows = [(fx["home"], m["p_home"]), (fx["away"], m["p_away"])]
        extra = [f"Elo от последните мачове: {m['r_h']:.0f} срещу {m['r_a']:.0f}"]
        why = [
            f"{fx['home']}: {m['w_h']}-{m['l_h']} в последните {m['n_h']} мача",
            f"{fx['away']}: {m['w_a']}-{m['l_a']} в последните {m['n_a']} мача",
            f"Силата на съперниците е неизвестна — свихме разликата от {m['raw_diff']:+.0f} на {m['diff']:+.0f} точки Elo",
        ]
        strength = strength_binary(m["p_home"])

    else:
        return None, "непознат спорт"

    if strength < MIN_STRENGTH:
        return None, "числата не дават превес"

    return {"fx": fx, "bucket": bucket, "rows": rows, "extra": extra, "why": why,
            "strength": strength, "n_eff": n_eff, "n_h": len(hr), "n_a": len(ar),
            "model": m, "h2h": None}, ""

# ---------------------------------------------------------------- КАРТИТЕ
def prob_block(rows, width=19):
    """Малък подравнен блок — най-четимото нещо в цялата карта."""
    lines = []
    for label, p in rows:
        lines.append(pad(label, width) + pct(p).rjust(4))
    return "<code>" + NL.join(esc(x) for x in lines) + "</code>"


def sample_text(an):
    s = f"извадка: {an['n_h']}+{an['n_a']} мача"
    h = an.get("h2h") or {}
    if h.get("tot"):
        s += f", +{h['tot']} директни"
    return s


def card(an, now):
    fx = an["fx"]
    head = f"{fx['emoji']} <b>{esc(fx['home'])}</b>  🆚  <b>{esc(fx['away'])}</b>"
    sub = []
    if fx.get("league"):
        sub.append(esc(fx["league"]))
    if fx.get("time"):
        sub.append(fx["time"] + " ч.")
    sub.append(date_bg(now))
    parts = [head, "<i>" + " · ".join(sub) + "</i>", "", "🔢 <b>Числата</b>", prob_block(an["rows"])]
    parts += an["extra"]

    why = list(an["why"])
    h = an.get("h2h") or {}
    if h.get("tot"):
        why.append(f"Помежду им, последни {h['tot']}: {h['hw']} - {h['dr']} - {h['aw']}")
    parts += ["", "🧭 <b>Защо</b>"]
    for w in why[:4]:
        parts.append("• " + esc(w))

    stars = an["stars"]
    parts += ["",
              ("⭐" * stars) + f" <b>{STAR_WORD[stars]}</b> · {sample_text(an)}",
              f"📐 {MODEL_NAME.get(an['bucket'], 'статистика')} · ⚠️ 18+ · вероятност, не гаранция"]
    return NL.join(parts)


def header_card(now, count):
    return NL.join([
        f"🧠 <b>БОТА ПРЕДРИЧА</b> · {date_bg(now)}",
        "",
        f"Днес числата казват нещо за <b>{n_match(count)}</b>.",
        "Всяка карта е вероятност от статистика — с извадката и разсъждението отдолу.",
        "",
        "⚠️ 18+ · това не е съвет за залог",
    ])


def footer_card(seen, thin, weak):
    return NL.join([
        "📘 <b>Как се чете</b>",
        "",
        "• Числото е <b>вероятност</b>, не гаранция и не " + Q1 + "сигурен мач" + Q2,
        "• ⭐ малка извадка · ⭐⭐ прилична · ⭐⭐⭐ добра за нашите източници",
        "• Формата е от последните изиграни мачове на отбора, независимо от турнира",
        "• ⚽ Поасон · 🏀 темпо и ефективност · 🏐 сет по сет · 🏓 Elo",
        "",
        f"Днес под лупата: {n_match(seen)} · {thin} с твърде малко данни (не гадаем) · "
        f"{weak} без ясен превес.",
        "Нищо не трием. И сгрешените прогнози остават тук.",
        "",
        "🟢 THE GREEN ROOM",
    ])


def nothing_card(now, seen, thin, weak):
    return NL.join([
        f"🧠 <b>БОТА ПРЕДРИЧА</b> · {date_bg(now)}",
        "",
        "<b>Днес числата не дават нищо убедително.</b>",
        "",
        f"Погледнахме {n_match(seen)} от сериозните турнири:",
        f"   • {thin} с твърде малко данни — не гадаем",
        f"   • {weak} без ясен превес по числата",
        "",
        f"{Q1}Няма прогноза{Q2} също е отговор. Утре пак.",
        "",
        "⚠️ 18+ · вероятност от статистика, не гаранция",
        "🟢 THE GREEN ROOM",
    ])


# ---------------------------------------------------------------- ПОДБОР
def build_pool(buckets):
    """Кръгова подредба по спорт — всеки спорт получава шанс, никой не задръства."""
    per = {}
    for b in MB.SPORT_ORDER:
        rows = [fx for fx in (buckets.get(b) or []) if fx.get("home") and fx.get("away")]
        rows.sort(key=lambda fx: -fx.get("weight", 0))
        per[b] = rows[:PER_SPORT]
    pool, i = [], 0
    while len(pool) < POOL:
        added = False
        for b in MB.SPORT_ORDER:
            lst = per.get(b) or []
            if i < len(lst):
                pool.append(lst[i])
                added = True
                if len(pool) >= POOL:
                    break
        if not added:
            break
        i += 1
    return pool


def choose(cands, limit):
    """Най-уверените напред, но без три поредни карти от един и същи спорт."""
    cands.sort(key=lambda a: -(a["stars"] * 1000.0 + a["strength"] * 100.0))
    picked, used, taken = [], {}, set()
    for a in cands:
        if len(picked) >= limit:
            break
        b = a["bucket"]
        if used.get(b, 0) >= 2 and len(cands) > limit:
            continue
        picked.append(a)
        taken.add(id(a))
        used[b] = used.get(b, 0) + 1
    for a in cands:      # ако разнообразието е оставило празни места — допълваме
        if len(picked) >= limit:
            break
        if id(a) not in taken:
            picked.append(a)
            taken.add(id(a))
    return picked


# ---------------------------------------------------------------- ГЛАВНО
def run():
    now = datetime.now(MB.SOFIA)
    try:
        buckets = MB.collect()
    except Exception as e:
        print("Събирането на срещите пропадна:", str(e)[:140])
        return
    pool = build_pool(buckets)
    if not pool:
        print("Няма срещи от сериозни турнири днес — Предсказателят мълчи.")
        return
    print(f"Под лупата: {n_match(len(pool))}.")

    # Нивото на футбола се смята от ЦЯЛАТА събрана извадка, не от един мач.
    foot_recs = []
    for fx in pool:
        if fx["bucket"] == "football":
            foot_recs += recent_for(fx, "home") + recent_for(fx, "away")
    lvl = league_level(foot_recs)
    if foot_recs:
        print(f"Ниво на футбола в извадката: {lvl:.2f} гола на отбор ({len(foot_recs)} мача).")

    cands, thin, weak, thin_sdb = [], 0, 0, 0
    for fx in pool:
        try:
            an, why_not = analyse(fx, lvl)
        except Exception as e:
            print(f"анализ {fx.get('home')} - {fx.get('away')}: {str(e)[:110]}")
            an, why_not = None, "грешка в данните"
        name = f"{fx.get('home')} - {fx.get('away')}"
        if an is None:
            if "малко данни" in why_not or "грешка" in why_not:
                thin += 1
                if fx.get("src") != "fd":
                    thin_sdb += 1
            else:
                weak += 1
            print(f"  пропускам {name}: {why_not}")
            continue
        an["stars"] = grade(an["bucket"], an["n_eff"], an["strength"])
        cands.append(an)
        print(f"  ✔ {name}: сила {an['strength']:.2f}, {an['stars']} звезди")

    seen = len(pool)
    if thin_sdb:
        # Проверено на 28.07.2026: безплатният ключ на TheSportsDB реже отговорите
        # до 1-3 записа (eventslast дава 1 мач). С такава история никой почтен
        # модел не може да смята — затова мачовете падат, а не се измислят числа.
        print("ПОДСКАЗКА за оператора: " + n_match(thin_sdb) + " паднаха заради тънка история "
              "от TheSportsDB (безплатният ключ връща 1-3 записа). Истинските числа идват от "
              "FOOTBALL_DATA_KEY (безплатен, за футбол) или платен SPORTSDB_KEY.")
    if not cands:
        print("Нищо убедително днес — казваме го честно.")
        post_predict(nothing_card(now, seen, thin, weak))
        return

    picks = choose(cands, MAX_PICKS)
    for a in picks:                       # директните срещи само за избраните — пестим заявки
        a["h2h"] = h2h_for(a["fx"])
        # Директните срещи тежат четвърт мач: често са отпреди години и с други състави.
        # Затова три звезди почти не се случват на тънките безплатни данни — и така трябва.
        a["n_eff"] += 0.25 * (a["h2h"].get("tot") or 0)
        a["stars"] = grade(a["bucket"], a["n_eff"], a["strength"])

    sent = 0
    if post_predict(header_card(now, len(picks))):
        sent += 1
    for a in picks:
        time.sleep(SEND_GAP)
        if post_predict(card(a, now)):
            sent += 1
    time.sleep(SEND_GAP)
    if post_predict(footer_card(seen, thin, weak)):
        sent += 1
    print(f"Готово: {len(picks)} прогнози, {sent} съобщения -> стая {PREDICT_THREAD}"
          + (" (СУХО ПУСКАНЕ — нищо не е пратено)" if DRY_RUN else ""))


# ---------------------------------------------------------------- САМОПРОВЕРКА
def selftest():
    """Само математиката и пазачът. Без мрежа — може да се пуска навсякъде."""
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    s = sum(poisson_pmf(k, 1.5) for k in range(0, 40))
    check("Поасон сумира до 1", abs(s - 1.0) < 1e-9)
    check("Поасон P(0|1.5)=0.2231", abs(poisson_pmf(0, 1.5) - 0.22313016) < 1e-6)
    check("Поасон P(2|2.0)=0.2707", abs(poisson_pmf(2, 2.0) - 0.27067057) < 1e-6)

    mx = poisson_matrix(1.6, 1.2)
    tot = sum(sum(row) for row in mx)
    check("матрицата е нормирана", abs(tot - 1.0) < 1e-9)
    ph = sum(mx[i][j] for i in range(MAXG + 1) for j in range(MAXG + 1) if i > j)
    pd = sum(mx[i][i] for i in range(MAXG + 1))
    pa = sum(mx[i][j] for i in range(MAXG + 1) for j in range(MAXG + 1) if i < j)
    check("1 + X + 2 = 1", abs(ph + pd + pa - 1.0) < 1e-9)
    check("домакинът с повече очаквани голове е фаворит", ph > pa)

    check("логистична(0) = 0.5", abs(logistic(0.0) - 0.5) < 1e-12)
    p6 = logistic(6.0 / BASK_SCALE)
    check("6 точки преднина -> 68-74%", 0.68 < p6 < 0.74)
    p10 = logistic(10.0 / BASK_SCALE)
    check("10 точки преднина -> 79-85%", 0.79 < p10 < 0.85)

    a, b, c = set_outcomes(0.5)
    check("равни сетове -> 50% мач", abs(a + b + c - 0.5) < 1e-12)
    a, b, c = set_outcomes(0.6)
    check("60% на сет -> 68-75% на мач", 0.68 < a + b + c < 0.75)

    r = elo_from([{"gf": 3, "ga": 1}] * 5)
    check("пет победи вдигат Elo", r > TT_START)
    r = elo_from([{"gf": 1, "ga": 3}] * 5)
    check("пет загуби свалят Elo", r < TT_START)

    check("малка извадка = една звезда", grade("football", 6, 0.9) == 1)
    check("тенисът на маса не стига 3 звезди", grade("tabletennis", 40, 0.9) == 2)
    check("голяма извадка + категорично = 3 звезди", grade("football", 20, 0.6) == 3)

    check("свиването пази средното", abs(shrink(3.0, 1.0, 0, 4.0) - 1.0) < 1e-12)
    check("сетовете се проверяват за смисъл", not sane_record("volleyball", 25, 20))
    check("точките не минават за сетове", not sane_record("basketball", 3, 1))

    check("стая 4 е забранена", post_predict("тест", "4") is False)
    check("стая 26 е забранена", post_predict("тест", "26") is False)
    check("стая 5 не е наша", post_predict("тест", "5") is False)

    print(f"САМОПРОВЕРКА: {ok} наред, {len(bad)} счупени")
    for b_ in bad:
        print("   🔴", b_)
    return not bad


def main():
    if len(sys.argv) > 1 and sys.argv[1].strip().lower() in ("selftest", "test", "--selftest"):
        sys.exit(0 if selftest() else 1)
    if not DRY_RUN and (not BOT_TOKEN or not CHAT_ID):
        print("Missing BOT_TOKEN/CHAT_ID (или пусни с PREDICT_DRY_RUN=1)")
        sys.exit(1)
    if DRY_RUN:
        print("СУХО ПУСКАНЕ — картите се печатат, нищо не заминава за Telegram.")
    run()


if __name__ == "__main__":
    main()
