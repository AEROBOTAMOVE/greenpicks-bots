/* ─────────────────────────────────────────────────────────────
   AERO клиент · логиката на крайните точки
   Базата (repo), списъкът с администратори и данните се подават отвън,
   затова целият поток се тества локално без Postgres.
   ───────────────────────────────────────────────────────────── */
import {
  MSG, SESSION_DAYS, LOGIN_WINDOW_MS, LOGIN_MAX_FAILS, REG_WINDOW_MS, REG_MAX_PER_IP,
  PASSWORD_MAX, ACCESS_DAYS, TOKEN_RE,
  normEmail, validEmail, passwordProblem, validDays, parseUntil,
  hashPassword, verifyPassword, newToken, hashToken,
  addDays, registrationUntil, extendUntil, accessState, mePayload, adminRow,
} from "./core.mjs";
import { json, isJsonRequest, readJsonBody, readCookie, sessionCookie, clearCookie } from "./http.mjs";
/* The Green Room · същата доказана логика като AERO клиента (43/43 на живо),
   без индикатора; /api/data връща пакета с прогнозите, резултатите и новините. */

export function makeApi({ repo, adminEmails, data, now = () => new Date() }) {
  let dummyHash = null;
  const dummy = async () => (dummyHash ||= await hashPassword("aero-dummy-password-не-се-ползва"));

  const admins = () => {
    try {
      return adminEmails() || new Set();
    } catch (e) {
      return new Set();
    }
  };

  const guard = (fn) => async (req, ctx) => {
    try {
      return await fn(req, ctx || {});
    } catch (e) {
      console.error("[aero-api]", (e && e.stack) || e);
      return json(500, { error: MSG.internal });
    }
  };

  const onlyMethod = (req, m) => (req.method === m ? null : json(405, { error: MSG.method }, { Allow: m }));

  /** POST + JSON + разчетено тяло · { body } или { res } */
  async function postJson(req) {
    const bad = onlyMethod(req, "POST");
    if (bad) return { res: bad };
    if (!isJsonRequest(req)) return { res: json(415, { error: MSG.needJson }) };
    const b = await readJsonBody(req);
    if (b.error) return { res: b.error };
    return { body: b.value };
  }

  async function currentUser(req, n) {
    const tok = readCookie(req.headers.get("cookie"));
    if (!tok || !TOKEN_RE.test(tok)) return null;
    return repo.getSessionUser(hashToken(tok), n);
  }

  async function startSession(user, n) {
    const token = newToken();
    await repo.createSession(hashToken(token), user.id, n, addDays(n, SESSION_DAYS));
    return sessionCookie(token, SESSION_DAYS * 86400);
  }

  /** { user } за администратор или { res } с 401/403 */
  async function requireAdmin(req, n) {
    const user = await currentUser(req, n);
    if (!user) return { res: json(401, { error: MSG.notLogged, logged_in: false }) };
    const set = admins();
    if (!set.has(normEmail(user.email))) return { res: json(403, { error: MSG.notAdmin }) };
    return { user, set };
  }

  /** Пазач без състезание: броене → запис на опита → повторно броене.
      Всяка заявка брои и собствения си запис, затова едновременни заявки
      не минават тавана (преди: 30 едновременни грешни пароли = 30 проверки).
      Вече блокираният опит не пише ред, за да не расте таблицата при атака. */
  async function takeSlot(subject, kind, since, max, at) {
    if ((await repo.countAttempts(subject, kind, since)) >= max) return false;
    await repo.addAttempt(subject, kind, at);
    return (await repo.countAttempts(subject, kind, since)) <= max;
  }

  /* ── POST /api/register ── */
  const register = guard(async (req, ctx) => {
    const p = await postJson(req);
    if (p.res) return p.res;
    const email = normEmail(p.body.email);
    if (!validEmail(email)) return json(400, { error: MSG.badEmail });
    const pp = passwordProblem(p.body.password);
    if (pp) return json(400, { error: pp });
    const n = now();
    const ip = ctx && ctx.ip ? String(ctx.ip) : "";
    /* всеки опит от IP се брои — и този със зает имейл (409), иначе
       регистрацията е безкрайна проба кои имейли съществуват */
    if (ip && !(await takeSlot(ip, "register", new Date(n.getTime() - REG_WINDOW_MS), REG_MAX_PER_IP, n))) {
      return json(429, { error: MSG.regTooMany }, { "Retry-After": "3600" });
    }
    const passHash = await hashPassword(p.body.password);
    const user = await repo.insertUser({ email, passHash, createdAt: n, accessUntil: registrationUntil(n) });
    if (!user) return json(409, { error: MSG.emailTaken });
    // Реферал: атрибуция + бонус дни за двамата (наградата е дни достъп)
    let regUser = user;
    const refVhod = String((p.body.ref || "")).trim().toUpperCase().slice(0, 12);
    if (refVhod) {
      try {
        const referrer = await repo.potrebitelPoRefKod(refVhod);
        if (referrer && referrer.id !== user.id) {
          await repo.zapishiReferal(user.id, referrer.id);
          regUser = (await repo.setAccessUntil(user.id, extendUntil(user.access_until, REF_BONUS, n))) || user;
          if (referrer.access_until) await repo.setAccessUntil(referrer.id, extendUntil(new Date(referrer.access_until), REF_BONUS, n));
        }
      } catch (e) { /* реферал не бива да чупи регистрацията */ }
    }
    // собствен код за новия
    try { for (let i = 0; i < 5 && !(await repo.refKod(regUser.id)); i++) { const k = genRefKod(); if (!(await repo.potrebitelPoRefKod(k))) await repo.zadaiRefKod(regUser.id, k); } } catch (e) { /* игнор */ }
    await repo.touchLogin(regUser.id, n);
    const cookie = await startSession(regUser, n);
    return json(201, { ok: true, ...mePayload(regUser, admins(), n) }, { "Set-Cookie": cookie });
  });

  /* ── POST /api/login ── */
  const login = guard(async (req, ctx) => {
    const p = await postJson(req);
    if (p.res) return p.res;
    const email = normEmail(p.body.email);
    const pw = typeof p.body.password === "string" ? p.body.password : "";
    if (!validEmail(email) || !pw || pw.length > PASSWORD_MAX) return json(401, { error: MSG.badLogin });
    const n = now();
    /* Ключът е по (IP + имейл), а НЕ само по имейл: така някой не може да
       заключи чужд акаунт, като нарочно бърка паролата му от свой адрес —
       жертвата влиза спокойно от своя адрес. Без IP (рядко) → резерва по имейл. */
    const ip = ctx && ctx.ip ? String(ctx.ip) : "";
    const sub = ip ? ip + "|" + email : email;
    /* опитът се записва ПРЕДИ проверката на паролата; успешният вход го чисти */
    if (!(await takeSlot(sub, "login", new Date(n.getTime() - LOGIN_WINDOW_MS), LOGIN_MAX_FAILS, n))) {
      return json(429, { error: MSG.loginTooMany }, { "Retry-After": "900" });
    }
    const user = await repo.getUserByEmail(email);
    let ok = false;
    if (user) ok = await verifyPassword(pw, user.pass_hash);
    else await verifyPassword(pw, await dummy()); // същото време с и без такъв имейл
    if (!ok) return json(401, { error: MSG.badLogin }); // опитът вече е записан от takeSlot
    await repo.clearAttempts(sub, "login");
    await repo.touchLogin(user.id, n);
    await repo.cleanup(n);
    const cookie = await startSession(user, n);
    return json(200, { ok: true, ...mePayload(user, admins(), n) }, { "Set-Cookie": cookie });
  });

  /* ── POST /api/logout ── */
  const logout = guard(async (req) => {
    const p = await postJson(req);
    if (p.res) return p.res;
    const tok = readCookie(req.headers.get("cookie"));
    if (tok && TOKEN_RE.test(tok)) await repo.deleteSession(hashToken(tok));
    return json(200, { ok: true }, { "Set-Cookie": clearCookie() });
  });

  /* ── GET /api/me ── */
  const me = guard(async (req) => {
    const bad = onlyMethod(req, "GET");
    if (bad) return bad;
    const n = now();
    const user = await currentUser(req, n);
    if (!user) return json(401, { error: MSG.notLogged, logged_in: false });
    return json(200, { logged_in: true, ...mePayload(user, admins(), n) });
  });

  /* ── GET /api/data ── */
  const dataEp = guard(async (req) => {
    const bad = onlyMethod(req, "GET");
    if (bad) return bad;
    const n = now();
    const user = await currentUser(req, n);
    if (!user) return json(401, { error: MSG.notLogged, logged_in: false });
    const st = accessState(user, admins(), n);
    if (!st.active) return json(403, { error: MSG.expired, status: st.status, active: false });
    let bundle;
    try {
      bundle = await data.get();
    } catch (e) {
      console.error("[gr-data]", (e && e.message) || e);
      return json(503, { error: "Данните се обновяват. Опитай пак след минута." });
    }
    return json(200, { ...bundle, me: mePayload(user, admins(), n) });
  });

  /* ── GET /api/admin/users ── */
  const adminUsers = guard(async (req) => {
    const bad = onlyMethod(req, "GET");
    if (bad) return bad;
    const n = now();
    const a = await requireAdmin(req, n);
    if (a.res) return a.res;
    const rows = await repo.listUsers();
    return json(200, { users: rows.map((u) => adminRow(u, a.set, n)), count: rows.length, now: n.toISOString() });
  });

  /* ── POST /api/admin/user ── */
  const adminUser = guard(async (req) => {
    const p = await postJson(req);
    if (p.res) return p.res;
    const n = now();
    const a = await requireAdmin(req, n);
    if (a.res) return a.res;
    const b = p.body;
    const action = String(b.action || "");
    const email = normEmail(b.email);
    if (!validEmail(email)) return json(400, { error: MSG.badEmail });
    const done = (u, status = 200) => json(status, { ok: true, action, user: adminRow(u, a.set, n) });

    if (action === "create") {
      const pp = passwordProblem(b.password);
      if (pp) return json(400, { error: pp });
      let until;
      if (b.until !== undefined && b.until !== null && b.until !== "") {
        until = parseUntil(b.until);
        if (!until) return json(400, { error: MSG.badUntil });
      } else {
        const days = b.days === undefined || b.days === null || b.days === "" ? ACCESS_DAYS : validDays(b.days);
        if (!days) return json(400, { error: MSG.badDays });
        until = addDays(n, days);
      }
      const user = await repo.insertUser({ email, passHash: await hashPassword(b.password), createdAt: n, accessUntil: until });
      if (!user) return json(409, { error: MSG.emailTaken });
      return done(user, 201);
    }

    const known = ["extend", "set_until", "lock", "unlock", "delete", "set_password"];
    if (!known.includes(action)) return json(400, { error: MSG.badAction });
    const target = await repo.getUserByEmail(email);
    if (!target) return json(404, { error: MSG.noUser });

    switch (action) {
      case "extend": {
        const days = validDays(b.days);
        if (!days) return json(400, { error: MSG.badDays });
        return done(await repo.setAccessUntil(target.id, extendUntil(target.access_until, days, n)));
      }
      case "set_until": {
        const until = parseUntil(b.until);
        if (!until) return json(400, { error: MSG.badUntil });
        return done(await repo.setAccessUntil(target.id, until));
      }
      case "lock":
        if (a.set.has(email)) return json(400, { error: MSG.adminNoLock });
        return done(await repo.setLocked(target.id, true));
      case "unlock":
        return done(await repo.setLocked(target.id, false));
      case "set_password": {
        const pp = passwordProblem(b.password);
        if (pp) return json(400, { error: pp });
        const u = await repo.setPassword(target.id, await hashPassword(b.password));
        await repo.deleteUserSessions(target.id); // старите влизания падат
        await repo.clearAttempts(email, "login");
        return done(u);
      }
      case "delete":
        if (email === normEmail(a.user.email)) return json(400, { error: MSG.noSelfDelete });
        if (a.set.has(email)) return json(400, { error: MSG.adminNoDelete }); // админ не се трие
        await repo.deleteUser(target.id);
        await repo.clearAttempts(email, "login");
        return json(200, { ok: true, action, deleted: email });
      default:
        return json(400, { error: MSG.badAction });
    }
  });

  /* ── PUSH известия (VAPID ключове в env; изпращането е от бота) ── */
  const envGet = (name) => { try { return (globalThis.Netlify && globalThis.Netlify.env && globalThis.Netlify.env.get(name)) || (typeof process !== "undefined" && process.env && process.env[name]) || ""; } catch (e) { return ""; } };
  const pushKeyEp = guard(async (req) => {
    const bad = onlyMethod(req, "GET"); if (bad) return bad;
    return json(200, { key: envGet("VAPID_PUBLIC") });
  });
  const pushAboniraiEp = guard(async (req) => {
    const bad = onlyMethod(req, "POST"); if (bad) return bad;
    const n = now();
    const user = await currentUser(req, n);
    if (!user) return json(401, { error: MSG.notLogged, logged_in: false });
    if (!isJsonRequest(req)) return json(415, { error: MSG.needJson });
    const b = await readJsonBody(req); if (b.error) return b.error;
    const sub = b.value && b.value.sub;
    if (!sub || !sub.endpoint) return json(400, { error: "Липсва абонамент." });
    await repo.zapishiAbonament(user.id, String(sub.endpoint).slice(0, 500), JSON.stringify(sub));
    return json(200, { ok: true });
  });

  /* ── РЕФЕРАЛИ ── */
  const REF_BONUS = 7;
  const genRefKod = () => { const a = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"; let s = ""; for (let i = 0; i < 6; i++) s += a[Math.floor(Math.random() * a.length)]; return s; };
  const refEp = guard(async (req) => {
    const bad = onlyMethod(req, "GET"); if (bad) return bad;
    const n = now();
    const user = await currentUser(req, n);
    if (!user) return json(401, { error: MSG.notLogged, logged_in: false });
    let kod = await repo.refKod(user.id);
    for (let i = 0; i < 5 && !kod; i++) { const k = genRefKod(); if (!(await repo.potrebitelPoRefKod(k))) { await repo.zadaiRefKod(user.id, k); kod = await repo.refKod(user.id); } }
    return json(200, { kod: kod || "", bonus: REF_BONUS });
  });

  /* ── ТУРНИР „Зелен фиш" + Модел срещу Тълпата ── */
  const isoDen = (d) => { try { return d.toISOString().slice(0, 10); } catch (e) { return ""; } };
  const maskEmail = (e) => { const s = String(e || ""); const i = s.indexOf("@"); if (i < 1) return "играч"; return s[0] + "***" + s.slice(i); };
  const izhodOtRez = (rez) => {
    const m = /^(\d+)\s*[:\-]\s*(\d+)/.exec(String(rez || "")); if (!m) return null;
    const a = +m[1], b = +m[2]; return a > b ? "1" : a < b ? "2" : "X";
  };
  const izborKod = (s) => { const t = String(s || "").trim(); if (/^1([·.\s]|$)/.test(t)) return "1"; if (/^2([·.\s]|$)/.test(t)) return "2"; if (/^[XХ]([·.\s]|$)/.test(t)) return "X"; return null; };
  const tournirMachove = (bundle) => {
    const pool = (bundle.prognozi || []).concat(bundle.dnes || []);
    const vid = new Set(); const out = [];
    for (const p of pool) {
      if (!p || !p.id || !p.dom || !p.gost || vid.has(p.id)) continue;
      vid.add(p.id);
      out.push({ match_key: p.id, den: p.den || "", sport: p.sport || "", sport_bg: p.sport_bg || "", dom: p.dom, gost: p.gost, liga: p.liga || "", nash: izborKod(p.izbor) });
      if (out.length >= 12) break;
    }
    return out;
  };
  const tournirRez = (bundle) => {
    const map = {};
    for (const r of (bundle.rezultati || [])) { if (r && r.id && r.rezultat) { const o = izhodOtRez(r.rezultat); if (o) map[r.id] = o; } }
    return map;
  };
  const turnirEp = guard(async (req) => {
    const bad = onlyMethod(req, "GET"); if (bad) return bad;
    const n = now();
    const user = await currentUser(req, n);
    if (!user) return json(401, { error: MSG.notLogged, logged_in: false });
    const st = accessState(user, admins(), n);
    if (!st.active) return json(403, { error: MSG.expired, status: st.status, active: false });
    let bundle; try { bundle = await data.get(); } catch (e) { return json(503, { error: "Данните се обновяват. Опитай пак." }); }
    const mach = tournirMachove(bundle);
    const rez = tournirRez(bundle);
    const keys = Object.keys(rez);
    for (const p of await repo.neschetenite(user.id, keys)) { const w = rez[p.match_key]; if (w) await repo.otbelezhi(p.id, p.izbor === w ? 3 : 0); }
    const denOt = isoDen(new Date(n.getTime() - 7 * 86400000));
    const moiMap = {}; for (const m of await repo.moitePredskazania(user.id, denOt)) moiMap[m.match_key] = { izbor: m.izbor, scored: m.scored, points: m.points };
    const tk = mach.map((m) => m.match_key);
    const tълpa = {}; for (const r of await repo.tълpa(tk)) { const c = (tълpa[r.match_key] = tълpa[r.match_key] || { "1": 0, "X": 0, "2": 0 }); if (c[r.izbor] != null) c[r.izbor] = r.n; }
    const tabla = (await repo.turnirTabla(20)).map((t, i) => ({ ime: maskEmail(t.email), poz: i + 1, points: t.points, tochni: t.tochni, obshto: t.obshto }));
    const az = await repo.mojtRedNaTablata(user.id);
    return json(200, {
      mach: mach.map((m) => ({ ...m, moi: moiMap[m.match_key] || null, tълpa: tълpa[m.match_key] || { "1": 0, "X": 0, "2": 0 } })),
      tabla, az: az || { rank: null, points: 0, tochni: 0, obshto: 0 },
    });
  });
  const predskazhiEp = guard(async (req) => {
    const bad = onlyMethod(req, "POST"); if (bad) return bad;
    const n = now();
    const user = await currentUser(req, n);
    if (!user) return json(401, { error: MSG.notLogged, logged_in: false });
    const st = accessState(user, admins(), n);
    if (!st.active) return json(403, { error: MSG.expired, status: st.status, active: false });
    if (!isJsonRequest(req)) return json(415, { error: MSG.needJson });
    const b = await readJsonBody(req); if (b.error) return b.error;
    const v = b.value || {};
    if (!v.match_key || !v.den || !["1", "X", "2"].includes(v.izbor)) return json(400, { error: "Липсва мач или избор." });
    await repo.zapishiPredskazanie(user.id, String(v.match_key).slice(0, 200), String(v.den).slice(0, 10), String(v.sport || "").slice(0, 40), v.izbor);
    return json(200, { ok: true });
  });

  /* ── GET /api/preview — БЕЗ вход. Витрината на честността: реалният трак-рекорд +
     ЕДИН безплатен пик на деня. Останалото стои зад стената (пази бизнеса). ── */
  const previewEp = async (req) => {
    try {
      const bad = onlyMethod(req, "GET"); if (bad) return bad;
      let bundle; try { bundle = await data.get(); } catch (e) { return json(503, { error: "Данните се обновяват. Опитай пак." }); }
      const pr = Array.isArray(bundle.prognozi) ? bundle.prognozi : [];
      const dnes = bundle.dnes || "";
      const dnesPr = pr.filter((k) => k.den === dnes);
      const pool = (dnesPr.length ? dnesPr : pr).slice().sort((a, b) => (b.procent || 0) - (a.procent || 0));
      const f = pool[0] || null;
      const free = f ? { dom: f.dom, gost: f.gost, sport: f.sport, sport_bg: f.sport_bg, liga: f.liga || "", den: f.den, izbor: f.izbor, koef: f.koef, procent: f.procent, zvezdi: f.zvezdi || 0, zashto: f.zashto || "" } : null;
      const stat = (Array.isArray(bundle.statistika) ? bundle.statistika : [])
        .filter((s) => s && s.uspeh != null && (s.n || 0) >= 5)
        .sort((a, b) => (b.n || 0) - (a.n || 0)).slice(0, 4)
        .map((s) => ({ sport_bg: s.sport_bg, uspeh: s.uspeh, n: s.n }));
      const o = bundle.obshto || {};
      return json(200, {
        guest: true,
        track: { uspeh: o.uspeh != null ? o.uspeh : null, n: o.n || 0, dni: o.dni || 30 },
        statistika: stat,
        free,
        broy_dnes: dnesPr.length,
        sporta_dnes: new Set(dnesPr.map((k) => k.sport)).size,
        obshto_prognozi: pr.length,
      }, { "Cache-Control": "public, max-age=120" });
    } catch (e) { return json(500, { error: MSG.internal }); }
  };

  return { register, login, logout, me, data: dataEp, adminUsers, adminUser, turnir: turnirEp, predskazhi: predskazhiEp, ref: refEp, pushKey: pushKeyEp, pushAbonirai: pushAboniraiEp, preview: previewEp };
}
