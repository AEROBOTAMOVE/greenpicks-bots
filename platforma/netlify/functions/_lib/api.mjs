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
    await repo.touchLogin(user.id, n);
    const cookie = await startSession(user, n);
    return json(201, { ok: true, ...mePayload(user, admins(), n) }, { "Set-Cookie": cookie });
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

  return { register, login, logout, me, data: dataEp, adminUsers, adminUser };
}
