/* ─────────────────────────────────────────────────────────────
   AERO клиент · чистите помощници
   Без база, без мрежа — затова се тестват локално с node.
   Пароли (scrypt + сол), токени, достъп по дати, проверка на входа.
   ───────────────────────────────────────────────────────────── */
import { scrypt as scryptCb, randomBytes, timingSafeEqual, createHash } from "node:crypto";

export const ACCESS_DAYS = 21;            // нова регистрация → 21 дни достъп
export const SESSION_DAYS = 30;           // сесията живее 30 дни
export const DAY_MS = 86400000;
export const LOGIN_WINDOW_MS = 15 * 60 * 1000;
export const LOGIN_MAX_FAILS = 10;        // 10 грешни опита за имейл за 15 мин
export const REG_WINDOW_MS = 60 * 60 * 1000;
export const REG_MAX_PER_IP = 5;          // 5 регистрации от един адрес за час
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 200;
export const DAYS_MAX = 3650;
export const COOKIE_NAME = "gr_s";         // The Green Room (отделно от AERO)
export const ACCESS_TZ = "Europe/Sofia";  // «до дата» = до края на деня по българско време

export const MSG = Object.freeze({
  method: "Този метод не е позволен.",
  needJson: "Заявката трябва да е във формат JSON.",
  badJson: "Невалидни данни в заявката.",
  tooBig: "Заявката е твърде голяма.",
  badEmail: "Невалиден имейл адрес.",
  passShort: "Паролата трябва да е поне 8 знака.",
  passLong: "Паролата е твърде дълга (най-много 200 знака).",
  emailTaken: "Този имейл вече е регистриран. Влез с паролата си.",
  regTooMany: "Твърде много регистрации от този адрес. Опитай пак по-късно.",
  badLogin: "Грешен имейл или парола.",
  loginTooMany: "Твърде много неуспешни опити. Опитай пак след 15 минути.",
  notLogged: "Не си влязъл в профила си.",
  expired: "Достъпът ти изтече. Свържи се с администратора.",
  notAdmin: "Нямаш администраторски права.",
  noUser: "Няма потребител с този имейл.",
  badAction: "Непознато действие.",
  badDays: "Броят дни трябва да е цяло число от 1 до 3650.",
  badUntil: "Невалидна дата. Използвай формат ГГГГ-ММ-ДД (напр. 2026-12-31).",
  adminNoLock: "Администраторите не се заключват.",
  noSelfDelete: "Не можеш да изтриеш собствения си профил.",
  internal: "Вътрешна грешка. Опитай пак след малко.",
});

export const STATUS_BG = Object.freeze({
  admin: "администратор",
  active: "активен",
  expired: "изтекъл",
  locked: "заключен",
});

/* ── вход ── */
export function normEmail(v) {
  return typeof v === "string" ? v.trim().toLowerCase() : "";
}
const EMAIL_RE = /^[^\s@,;:<>()"'\\]+@[^\s@,;:<>()"'\\]+\.[^\s@,;:<>()"'\\.]{2,}$/;
export function validEmail(e) {
  return typeof e === "string" && e.length >= 6 && e.length <= 254 && EMAIL_RE.test(e) && !e.includes("..");
}
/** null ако паролата става, иначе съобщението на български */
export function passwordProblem(p) {
  if (typeof p !== "string" || p.length < PASSWORD_MIN) return MSG.passShort;
  if (p.length > PASSWORD_MAX) return MSG.passLong;
  return null;
}
/** цяло число 1..3650 (приема и "30"), иначе null */
export function validDays(d) {
  const n = typeof d === "string" && d.trim() !== "" ? Number(d.trim()) : d;
  return Number.isInteger(n) && n >= 1 && n <= DAYS_MAX ? n : null;
}
/** ADMIN_EMAILS="a@x.bg, b@y.com" → Set от нормализирани имейли */
export function parseAdminEmails(raw) {
  return new Set(String(raw || "").split(/[,;\s]+/).map(normEmail).filter(validEmail));
}

/** Администраторите като «множество» с has(): sha256 хешове (публичното repo
    не носи имейли в чист вид) + ADMIN_EMAILS от Netlify. */
export function adminSet(hashes = [], envRaw = "") {
  const h = new Set((hashes || []).map((x) => String(x).toLowerCase()));
  const env = parseAdminEmails(envRaw);
  return {
    has: (email) => {
      const e = normEmail(email);
      return !!e && (env.has(e) || h.has(createHash("sha256").update(e).digest("hex")));
    },
  };
}

/* ── пароли · scrypt с отделна случайна сол за всеки ── */
const SCRYPT_N = 16384;
const SCRYPT_R = 8;
const SCRYPT_P = 1;
const SCRYPT_KEYLEN = 64;

function scryptAsync(pw, salt, keylen, opts) {
  return new Promise((resolve, reject) => {
    scryptCb(pw, salt, keylen, opts, (err, key) => (err ? reject(err) : resolve(key)));
  });
}
function prep(pw) {
  return String(pw).normalize("NFKC");
}
export async function hashPassword(pw) {
  const salt = randomBytes(16);
  const key = await scryptAsync(prep(pw), salt, SCRYPT_KEYLEN, {
    N: SCRYPT_N, r: SCRYPT_R, p: SCRYPT_P, maxmem: 64 * 1024 * 1024,
  });
  return ["scrypt", SCRYPT_N, SCRYPT_R, SCRYPT_P, salt.toString("base64url"), key.toString("base64url")].join("$");
}
export async function verifyPassword(pw, stored) {
  if (typeof pw !== "string" || typeof stored !== "string") return false;
  const parts = stored.split("$");
  if (parts.length !== 6 || parts[0] !== "scrypt") return false;
  const N = Number(parts[1]);
  const r = Number(parts[2]);
  const p = Number(parts[3]);
  if (![N, r, p].every(Number.isInteger) || N < 1024 || N > 1048576 || (N & (N - 1)) !== 0 || r < 1 || r > 32 || p < 1 || p > 16) return false;
  const salt = Buffer.from(parts[4], "base64url");
  const want = Buffer.from(parts[5], "base64url");
  if (salt.length < 8 || want.length < 16) return false;
  let got;
  try {
    got = await scryptAsync(prep(pw), salt, want.length, { N, r, p, maxmem: 256 * N * r + 4 * 1024 * 1024 });
  } catch (e) {
    return false;
  }
  return got.length === want.length && timingSafeEqual(got, want);
}

/* ── токени · 32 случайни байта; в базата отива само sha256 ── */
export const TOKEN_RE = /^[A-Za-z0-9_-]{43}$/;
export function newToken() {
  return randomBytes(32).toString("base64url");
}
export function hashToken(token) {
  return createHash("sha256").update(String(token)).digest("hex");
}

/* ── дати ── */
export function toDate(v) {
  if (v instanceof Date) return isNaN(v.getTime()) ? null : v;
  if (v === null || v === undefined || v === "") return null;
  const d = new Date(v);
  return isNaN(d.getTime()) ? null : d;
}
export function iso(v) {
  const d = toDate(v);
  return d ? d.toISOString() : null;
}
export function addDays(date, days) {
  return new Date(toDate(date).getTime() + days * DAY_MS);
}
export function registrationUntil(now) {
  return addDays(now, ACCESS_DAYS);
}
/** удължаване: от по-късното между «сега» и текущия край */
export function extendUntil(current, days, now) {
  const cur = toDate(current);
  const base = Math.max(cur ? cur.getTime() : 0, toDate(now).getTime());
  return new Date(base + days * DAY_MS);
}

/** отместване на часовата зона в минути за даден момент (Sofia: +120 / +180) */
export function zoneOffsetMin(date, tz = ACCESS_TZ) {
  try {
    const dtf = new Intl.DateTimeFormat("en-US", {
      timeZone: tz, hourCycle: "h23",
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    const p = {};
    for (const x of dtf.formatToParts(date)) p[x.type] = x.value;
    const asUtc = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
    return Math.round((asUtc - Math.floor(date.getTime() / 1000) * 1000) / 60000);
  } catch (e) {
    return 120;
  }
}
/** 23:59:59.999 местно време на дадения ден, върнато като момент в UTC */
export function endOfDayInZone(y, mo, d, tz = ACCESS_TZ) {
  const local = Date.UTC(y, mo - 1, d, 23, 59, 59, 999);
  let utc = local - zoneOffsetMin(new Date(local), tz) * 60000;
  utc = local - zoneOffsetMin(new Date(utc), tz) * 60000;
  return new Date(utc);
}
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const ISO_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,3})?)?(Z|[+-]\d{2}:\d{2})$/;
/** "2026-12-31" → края на деня по София · или пълен ISO с часова зона · иначе null */
export function parseUntil(v) {
  if (typeof v !== "string") return null;
  const s = v.trim();
  const m = DATE_RE.exec(s);
  if (m) {
    const y = +m[1];
    const mo = +m[2];
    const d = +m[3];
    const probe = new Date(Date.UTC(y, mo - 1, d));
    if (probe.getUTCFullYear() !== y || probe.getUTCMonth() !== mo - 1 || probe.getUTCDate() !== d) return null;
    if (y < 2000 || y > 2100) return null;
    return endOfDayInZone(y, mo, d);
  }
  if (ISO_RE.test(s)) {
    const dt = new Date(s);
    if (isNaN(dt.getTime())) return null;
    const y = dt.getUTCFullYear();
    return y < 2000 || y > 2100 ? null : dt;
  }
  return null;
}

/* ── достъпът ── */
/** admin · active · status · days_left · администраторите никога не се заключват */
export function accessState(user, admins, now) {
  const admin = !!(admins && admins.has(normEmail(user && user.email)));
  if (admin) return { admin: true, active: true, status: "admin", days_left: null };
  const until = toDate(user && user.access_until);
  const t = toDate(now).getTime();
  if (user && user.locked) return { admin: false, active: false, status: "locked", days_left: 0 };
  if (!until || until.getTime() <= t) return { admin: false, active: false, status: "expired", days_left: 0 };
  return { admin: false, active: true, status: "active", days_left: Math.ceil((until.getTime() - t) / DAY_MS) };
}
/** отговорът на /api/me (и на вход / регистрация) */
export function mePayload(user, admins, now) {
  const st = accessState(user, admins, now);
  return {
    email: user.email,
    admin: st.admin,
    active: st.active,
    status: st.status,
    days_left: st.days_left,
    access_until: iso(user.access_until),
    registered: iso(user.created_at),
    message: st.active ? null : MSG.expired,
  };
}
/** ред в списъка на администратора */
export function adminRow(user, admins, now) {
  const st = accessState(user, admins, now);
  return {
    email: user.email,
    registered: iso(user.created_at),
    access_until: iso(user.access_until),
    status: st.status,
    status_bg: STATUS_BG[st.status],
    active: st.active,
    days_left: st.days_left,
    last_login: iso(user.last_login),
    locked: !!user.locked,
    admin: st.admin,
  };
}
