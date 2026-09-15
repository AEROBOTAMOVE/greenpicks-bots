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
  esports: "Киберспорт", rugby: "Ръгби", amfootball: "Американски футбол",
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

/** Пакетът от суровия дневник. Чиста функция — тества се без мрежа. */
export function napraviPaket(log, zaglavia, sega = Date.now()) {
  const dnes = denSofia(sega);
  const vchera = plusDni(dnes, -1);
  const predi7 = plusDni(dnes, -7);
  const predi30 = plusDni(dnes, -30);
  const zapisi = Array.isArray(log) ? log.filter((r) => r && typeof r === "object" && r.home && r.away && r.pick) : [];

  const prognozi = zapisi
    .filter((r) => !r.scored && String(r.day || "") >= vchera)
    .map(kartaZaKlient)
    .sort((a, b) => (a.den + a.pusnata).localeCompare(b.den + b.pusnata));

  const rez = zapisi
    .filter((r) => r.scored && String(r.day || "") >= predi7)
    .map((r) => ({ ...kartaZaKlient(r), poznata: r.hit === true ? true : r.hit === false ? false : null, rezultat: String(r.score || "") }))
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

  return {
    dnes,
    prognozi,
    rezultati: rez,
    statistika,
    obshto: { n: vsichki, poznati, uspeh: vsichki ? Math.round((100 * poznati) / vsichki) : null, dni: 30 },
    novini,
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
    const [log, zag] = await Promise.all([
      tegli(fetchImpl, "predict_log.json", timeoutMs, stamp),
      tegli(fetchImpl, "last_news_titles.json", timeoutMs, stamp).catch(() => []),
    ]);
    return { ...napraviPaket(log, zag, stamp), fetched_utc: new Date(stamp).toISOString() };
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
