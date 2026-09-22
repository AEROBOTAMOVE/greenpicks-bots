/* ─────────────────────────────────────────────────────────────
   The Green Room · данните на бота за платформата
   Сървърът тегли дневника на прогнозите и заглавията на новините от
   публичното repo на бота и връща КОМПАКТЕН пакет — само полетата,
   които клиентът трябва да види. Нищо вътрешно (източник на цената,
   модел, служебни полета) не излиза навън.
   Кеш в паметта на функцията: 60 s; при грешка се дава последният добър
   пакет до 10 мин (по-добре малко стар, отколкото празен екран).
   ───────────────────────────────────────────────────────────── */

export const GR_BASE = "https://raw.githubusercontent.com/AEROBOTAMOVE/greenpicks-bots/main/";
export const TZ = "Europe/Sofia";

export const SPORT_BG = Object.freeze({
  football: "Футбол", tennis: "Тенис", basketball: "Баскетбол", tabletennis: "Тенис на маса",
  volleyball: "Волейбол", hockey: "Хокей", baseball: "Бейзбол", mma: "ММА", boxing: "Бокс",
  esports: "Esports", rugby: "Ръгби", amfootball: "Американски футбол",
});
export const SPORT_RED = Object.freeze([
  "football", "tennis", "basketball", "tabletennis", "volleyball", "hockey", "baseball",
  "mma", "boxing", "rugby", "amfootball", "esports",
]);

/** «ГГГГ-ММ-ДД» по София за даден момент */
export function denSofia(ms, tz = TZ) {
  try {
    const p = {};
    for (const x of new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" })
      .formatToParts(new Date(ms))) p[x.type] = x.value;
    return `${p.year}-${p.month}-${p.day}`;
  } catch (e) {
    return new Date(ms).toISOString().slice(0, 10);
  }
}
export function plusDni(den, n) {
  const d = new Date(den + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

const num = (v) => {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
};

/** Коефициентът за клиента: на Бетано, ако го има (българската книга), иначе пазарният. */
export function koef(r) {
  const b = num(r.betano_cena);
  if (b && b > 1.0 && b < 1000) return Math.round(b * 100) / 100;
  const c = num(r.pazar_cena);
  if (c && c > 1.0 && c < 1000) return Math.round(c * 100) / 100;
  return null;
}

/** Една карта, както я вижда клиентът — само тези полета. */
export function kartaZaKlient(r) {
  const p = num(r.p);
  return {
    id: String(r.key || "") + "|" + String(r.combo || 0),
    sport: String(r.bucket || ""),
    sport_bg: SPORT_BG[r.bucket] || String(r.bucket || ""),
    liga: String(r.league || ""),
    dom: String(r.home || ""),
    gost: String(r.away || ""),
    izbor: String(r.pick || ""),
    procent: p && p > 0 && p < 1 ? Math.round(p * 100) : null,
    koef: koef(r),
    zvezdi: Number.isInteger(r.stars) ? r.stars : null,
    den: String(r.day || ""),
    pusnata: String(r.posted || ""),
    fish: Number(r.combo) > 0 ? Number(r.combo) : 0,
  };
}

/** Показаният процент на клиента — суровата вероятност на мозъка, СВИТА към
    реалната успеваемост на спорта, ако спортът се надценява (виж napraviPaket).
    Без карта за калибрация (kalibr) връща суровия процент — старото поведение. */
export function pokazanProcent(r, kalibr) {
  const p = num(r.p);
  if (!(p > 0 && p < 1)) return null;
  const f = (kalibr && kalibr[r.bucket]) || 1;
  return Math.round(Math.min(0.99, p * f) * 100);
}

/** «Защо тази прогноза» — едно-две изречения от това, което ботът знае
    (вид на избора, сила, колко мача са гледани). Нищо вътрешно. */
export function zashto(r, kalibr) {
  const s = String(r.pick || "").trim();
  const pct = pokazanProcent(r, kalibr) || 0;
  let a;
  const m = /^([12])\s*·\s*(.+)$/.exec(s);
  if (m) {
    a = "Очакваме победа за " + m[2].trim().replace(/^победа\s+(за\s+)?/i, "") + (pct >= 72 ? " — ясен фаворит по форма и ниво."
      : pct >= 60 ? " — има предимство по форма и ниво." : " — равностоен мач с лек превес.");
  } else if (/^Над\s/i.test(s)) a = "Очакваме открит мач: " + s.charAt(0).toLowerCase() + s.slice(1) + ".";
  else if (/^Под\s/i.test(s)) a = "Очакваме затворен мач: " + s.charAt(0).toLowerCase() + s.slice(1) + ".";
  else if (/^(1[ХX]|[ХX]2|12)(\s|·|$)/.test(s)) a = "Двоен шанс — по-сигурният избор за този мач.";
  else if (/^[ХX](\s|·|$)/.test(s)) a = "Очакваме равностоен мач, който завършва наравно.";
  else a = "Нашият избор е „" + s + "“.";
  // Основата се показва САМО ако е за гледани мачове/боеве — без «пазар»,
  // «надценка», «индекс» или признания, че история няма.
  const sm0 = String(r.sample || "").trim().replace(/\.$/, "");
  // БЯЛ списък (не черен): пуска се САМО чист кирилски текст + числа за гледани
  // мачове/боеве; всичко с латиница, символи, цени или пунктуация се отхвърля.
  const sm = /^[А-Яа-яЁё\s\d]{1,60}$/.test(sm0) && /мач|бо[йя]|двубо/i.test(sm0)
    && !/пазар|надценк|индекс|не сме|без история/i.test(sm0) ? sm0 : "";
  const zv = r.stars === 3 ? "Три звезди — сред най-силните избори за деня."
    : r.stars === 2 ? "Две звезди — стабилен избор." : r.stars === 1 ? "Една звезда — по-смел избор." : "";
  const b = [sm ? sm.charAt(0).toUpperCase() + sm.slice(1) + "." : "", zv].filter(Boolean).join(" ");
  return (a + (b ? " " + b : "")).trim();
}

/** Една находка на ловеца, както я вижда клиентът — само безопасни числа. */
export function stoynostKlient(z) {
  const izbor = { "1": z.dom, "2": z.gost, "Х": "Равен", "X": "Равен" }[z.izhod] || String(z.izhod || "");
  return {
    dom: String(z.dom || ""), gost: String(z.gost || ""),
    liga: String(z.liga || ""), sport: String(z.sport || ""),
    sport_bg: SPORT_BG[z.sport] || String(z.sport || ""),
    izhod: String(z.izhod || ""), izbor: String(izbor || ""),
    koef: Math.round((Number(z.bet) || 0) * 100) / 100,
    ev: Math.round((Number(z.ev) || 0) * 1000) / 1000,
    kely: Math.round((Number(z.kely) || 0) * 1000) / 1000,
    start_ms: Number(z.start_ms) || 0,
  };
}

/** Пакетът от суровия дневник. Чиста функция — тества се без мрежа. */
export function napraviPaket(log, zaglavia, sega = Date.now(), stoynostLog = null, zhivoLog = null, newsFull = null) {
  const dnes = denSofia(sega);
  const vchera = plusDni(dnes, -1);
  const predi7 = plusDni(dnes, -7);
  const predi30 = plusDni(dnes, -30);
  const zapisi = Array.isArray(log) ? log.filter((r) => r && typeof r === "object" && r.home && r.away && r.pick) : [];

  // 🔴 ЧЕСТНОСТ В ПРОЦЕНТИТЕ (22.09.2026). Спорт, който ОБЯВЯВА повече, отколкото
  // СБЪДВА (пазачът го хваща: хокей 66%→56%, «надценява се»; волей/CS2 в малки
  // извадки), сваля ПОКАЗАНИЯ процент към реалната си успеваемост. Вътрешната
  // вероятност на мозъка НЕ се пипа — ловецът на стойност я ползва; коригира се само
  // числото, което чете клиентът, и думите в «защо». Честно калибриран спорт остава
  // непроменен (фактор 1). Праг: ≥20 отсъдени и надценка ≥4 пункта, за да не гони шум.
  // Път назад: махни блока `kalibr` и подмяната на `procent`/аргумента на `zashto`.
  const _ks = {};
  for (const r of zapisi) {
    if (!r.scored || String(r.day || "") < predi30 || (r.hit !== true && r.hit !== false)) continue;
    const s = r.bucket || "drugi";
    _ks[s] = _ks[s] || { n: 0, poznati: 0, sump: 0 };
    _ks[s].n += 1; _ks[s].sump += (num(r.p) || 0);
    if (r.hit === true) _ks[s].poznati += 1;
  }
  const kalibr = {};
  for (const s in _ks) {
    const x = _ks[s]; const u = x.poznati / x.n; const pbar = x.sump / x.n;
    kalibr[s] = (x.n >= 20 && pbar > 0 && pbar - u >= 0.04) ? Math.max(0.6, Math.min(1, u / pbar)) : 1;
  }

  const prognozi = zapisi
    .filter((r) => !r.scored && String(r.day || "") >= vchera)
    .map((r) => ({ ...kartaZaKlient(r), procent: pokazanProcent(r, kalibr), zashto: zashto(r, kalibr) }))
    .sort((a, b) => (a.den + a.pusnata).localeCompare(b.den + b.pusnata));

  // ФИШОВЕТЕ: краката с един и същ номер в един и същ ден (последните 7 дни)
  const fm = new Map();
  for (const r of zapisi) {
    const n = Number(r.combo) || 0;
    if (!n || String(r.day || "") < predi7) continue;
    const kl = r.day + "#" + n;
    if (!fm.has(kl)) fm.set(kl, { den: String(r.day), nomer: n, kraka: [] });
    const k = { ...kartaZaKlient(r), procent: pokazanProcent(r, kalibr), zashto: zashto(r, kalibr) };
    if (r.scored) { k.poznata = r.hit === true ? true : r.hit === false ? false : null; k.rezultat = String(r.score || ""); }
    fm.get(kl).kraka.push(k);
  }
  const fishove = [...fm.values()].filter((f) => f.kraka.length >= 2).map((f) => {
    const ks = f.kraka.map((k) => k.koef);
    const koefF = ks.length && ks.every((x) => x > 1) ? Math.round(ks.reduce((a, b) => a * b, 1) * 100) / 100 : null;
    const status = f.kraka.some((k) => k.poznata === false) ? "nepoznat"
      : f.kraka.every((k) => k.poznata === true) ? "poznat" : "v_igra";
    return { ...f, koef: koefF, status };
  }).sort((a, b) => (b.den + String(b.nomer).padStart(3, "0")).localeCompare(a.den + String(a.nomer).padStart(3, "0")));

  const rez = zapisi
    .filter((r) => r.scored && String(r.day || "") >= predi7)
    .map((r) => ({ ...kartaZaKlient(r), procent: pokazanProcent(r, kalibr), poznata: r.hit === true ? true : r.hit === false ? false : null, rezultat: String(r.score || "") }))
    .sort((a, b) => (b.den + b.pusnata).localeCompare(a.den + a.pusnata))
    .slice(0, 400);                     // пакетът да остане лек (7 дни, най-много 400)

  const st = {};
  let vsichki = 0, poznati = 0;
  for (const r of zapisi) {
    if (!r.scored || String(r.day || "") < predi30 || (r.hit !== true && r.hit !== false)) continue;
    const s = r.bucket || "drugi";
    st[s] = st[s] || { sport: s, sport_bg: SPORT_BG[s] || s, n: 0, poznati: 0 };
    st[s].n += 1;
    vsichki += 1;
    if (r.hit === true) { st[s].poznati += 1; poznati += 1; }
  }
  const statistika = Object.values(st)
    .map((x) => ({ ...x, uspeh: x.n ? Math.round((100 * x.poznati) / x.n) : null }))
    .sort((a, b) => b.n - a.n);

  const novini = (Array.isArray(zaglavia) ? zaglavia : [])
    .filter((t) => typeof t === "string" && t.trim())
    .slice(0, 40)
    .map((t) => t.trim().slice(0, 300));

  // 📰 БОГАТИ НОВИНИ: заглавие + СНИМКА + линк + източник + спорт (от news_bot.py,
  // снимките идват от самите новини/RSS). Само https адреси — сигурност.
  const httpsOk = (u) => (typeof u === "string" && /^https:\/\/[^"'<>\s]+$/i.test(u)) ? u : "";
  const novini_full = (Array.isArray(newsFull) ? newsFull : [])
    .filter((n) => n && typeof n === "object" && typeof n.title === "string" && n.title.trim())
    .slice(0, 40)
    .map((n) => ({
      title: n.title.trim().slice(0, 200),
      image: httpsOk(n.image),
      link: httpsOk(n.link),
      source: String(n.source || "").slice(0, 40),
      sport: String(n.sport || "").slice(0, 20),
      summary: String(n.summary || "").slice(0, 220),
    }));

  // 💎 СТОЙНОСТ: находките на ловеца (Betano над честната цена) — само предстоящи,
  // безопасни числа, подредени по EV. Отделно от прогнозите (стойността е другаде).
  const svog = stoynostLog && typeof stoynostLog === "object" ? stoynostLog : {};
  const stoynost = Object.entries(svog)
    .filter(([k, z]) => !String(k).startsWith("_") && z && typeof z === "object"
      && Number(z.start_ms) > sega && Number(z.ev) > 0 && Number(z.bet) > 1)
    .map(([, z]) => stoynostKlient(z))
    .sort((a, b) => b.ev - a.ev)
    .slice(0, 12);

  // НА ЖИВО: живите мачове от sportni_danni.py (API-Football) — вече безопасни.
  const zhivo = (zhivoLog && Array.isArray(zhivoLog.zhivo))
    ? zhivoLog.zhivo.filter((z) => z && z.dom && z.gost).slice(0, 30) : [];

  return {
    dnes,
    prognozi,
    fishove,
    rezultati: rez,
    statistika,
    obshto: { n: vsichki, poznati, uspeh: vsichki ? Math.round((100 * poznati) / vsichki) : null, dni: 30 },
    novini,
    novini_full,
    stoynost,
    zhivo,
    sportove: SPORT_RED.map((s) => ({ sport: s, sport_bg: SPORT_BG[s] })),
  };
}

async function tegli(fetchImpl, pat, timeoutMs, stamp) {
  const r = await fetchImpl(GR_BASE + pat + "?t=" + stamp, { cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
  if (!r.ok) throw new Error("HTTP " + r.status + " " + pat);
  return JSON.parse(await r.text());
}

/** get() → { ...пакет, fetched_utc, cached, age_ms, stale? } */
export function makeDataSource({
  fetchImpl = (...a) => fetch(...a),
  clock = () => Date.now(),
  ttlMs = 60000,
  staleMs = 600000,
  timeoutMs = 9000,
} = {}) {
  let cached = null;
  let cachedAt = 0;
  let inflight = null;

  async function load() {
    const stamp = clock();
    const [log, zag, svog, zhivo, nfull] = await Promise.all([
      tegli(fetchImpl, "predict_log.json", timeoutMs, stamp),
      tegli(fetchImpl, "last_news_titles.json", timeoutMs, stamp).catch(() => []),
      tegli(fetchImpl, "stoynost_log.json", timeoutMs, stamp).catch(() => ({})),
      tegli(fetchImpl, "zhivo_futbol.json", timeoutMs, stamp).catch(() => ({})),
      tegli(fetchImpl, "news_full.json", timeoutMs, stamp).catch(() => []),
    ]);
    return { ...napraviPaket(log, zag, stamp, svog, zhivo, nfull), fetched_utc: new Date(stamp).toISOString() };
  }

  return {
    async get() {
      const t = clock();
      if (cached && t - cachedAt < ttlMs) return { ...cached, cached: true, age_ms: t - cachedAt };
      if (!inflight) {
        inflight = load()
          .then((b) => { cached = b; cachedAt = clock(); return b; })
          .finally(() => { inflight = null; });
      }
      try {
        const b = await inflight;
        return { ...b, cached: false, age_ms: 0 };
      } catch (e) {
        if (cached && t - cachedAt < staleMs) return { ...cached, cached: true, stale: true, age_ms: t - cachedAt };
        throw e;
      }
    },
  };
}
