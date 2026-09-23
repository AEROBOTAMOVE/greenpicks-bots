/* ─────────────────────────────────────────────────────────────
   AERO клиент · заявките към базата (Netlify Database / Postgres)
   sql е tagged template (db.sql от @netlify/database) — всяка стойност
   отива като параметър, никога като текст в заявката.
   Времената идват от кода (now), за да е едно и също часовникът
   при проверка и при запис.
   ───────────────────────────────────────────────────────────── */

const one = (rows) => (Array.isArray(rows) && rows.length ? rows[0] : null);
const ts = (d) => d.toISOString();

export function makeRepo(sql) {
  return {
    async getUserByEmail(email) {
      return one(await sql`
        SELECT id, email, pass_hash, created_at, access_until, locked, last_login
        FROM users WHERE email = ${email}`);
    },

    /** null ако имейлът вече е зает */
    async insertUser({ email, passHash, createdAt, accessUntil }) {
      return one(await sql`
        INSERT INTO users (email, pass_hash, created_at, access_until)
        VALUES (${email}, ${passHash}, ${ts(createdAt)}::timestamptz, ${ts(accessUntil)}::timestamptz)
        ON CONFLICT (email) DO NOTHING
        RETURNING id, email, pass_hash, created_at, access_until, locked, last_login`);
    },

    async setAccessUntil(id, until) {
      return one(await sql`
        UPDATE users SET access_until = ${ts(until)}::timestamptz WHERE id = ${id}
        RETURNING id, email, pass_hash, created_at, access_until, locked, last_login`);
    },

    async setLocked(id, locked) {
      return one(await sql`
        UPDATE users SET locked = ${!!locked} WHERE id = ${id}
        RETURNING id, email, pass_hash, created_at, access_until, locked, last_login`);
    },

    async setPassword(id, passHash) {
      return one(await sql`
        UPDATE users SET pass_hash = ${passHash} WHERE id = ${id}
        RETURNING id, email, pass_hash, created_at, access_until, locked, last_login`);
    },

    async touchLogin(id, at) {
      await sql`UPDATE users SET last_login = ${ts(at)}::timestamptz WHERE id = ${id}`;
    },

    /** сесиите падат с ON DELETE CASCADE */
    async deleteUser(id) {
      await sql`DELETE FROM users WHERE id = ${id}`;
    },

    async listUsers() {
      const rows = await sql`
        SELECT id, email, created_at, access_until, locked, last_login
        FROM users ORDER BY created_at DESC, id DESC`;
      return Array.isArray(rows) ? rows : [];
    },

    async createSession(tokenHash, userId, createdAt, expiresAt) {
      await sql`
        INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
        VALUES (${tokenHash}, ${userId}, ${ts(createdAt)}::timestamptz, ${ts(expiresAt)}::timestamptz)`;
    },

    async getSessionUser(tokenHash, now) {
      return one(await sql`
        SELECT u.id, u.email, u.pass_hash, u.created_at, u.access_until, u.locked, u.last_login
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ${tokenHash} AND s.expires_at > ${ts(now)}::timestamptz`);
    },

    async deleteSession(tokenHash) {
      await sql`DELETE FROM sessions WHERE token_hash = ${tokenHash}`;
    },

    async deleteUserSessions(userId) {
      await sql`DELETE FROM sessions WHERE user_id = ${userId}`;
    },

    async countAttempts(subject, kind, since) {
      const r = one(await sql`
        SELECT COUNT(*)::int AS n FROM login_attempts
        WHERE subject = ${subject} AND kind = ${kind} AND at > ${ts(since)}::timestamptz`);
      return r ? Number(r.n) || 0 : 0;
    },

    async addAttempt(subject, kind, at) {
      await sql`
        INSERT INTO login_attempts (subject, kind, at)
        VALUES (${subject}, ${kind}, ${ts(at)}::timestamptz)`;
    },

    async clearAttempts(subject, kind) {
      await sql`DELETE FROM login_attempts WHERE subject = ${subject} AND kind = ${kind}`;
    },

    /** чистене при вход: изтекли сесии и опити по-стари от ден */
    async cleanup(now) {
      await sql`DELETE FROM sessions WHERE expires_at < ${ts(now)}::timestamptz`;
      await sql`DELETE FROM login_attempts WHERE at < ${ts(new Date(now.getTime() - 86400000))}::timestamptz`;
    },

    /* ── ТУРНИР „Зелен фиш" ── */
    async zapishiPredskazanie(userId, matchKey, den, sport, izbor) {
      await sql`
        INSERT INTO predictions (user_id, match_key, den, sport, izbor)
        VALUES (${userId}, ${matchKey}, ${den}::date, ${sport}, ${izbor})
        ON CONFLICT (user_id, match_key)
        DO UPDATE SET izbor = ${izbor}
        WHERE predictions.scored = FALSE`;
    },
    async moitePredskazania(userId, denOt) {
      return await sql`
        SELECT match_key, izbor, scored, points
        FROM predictions
        WHERE user_id = ${userId} AND den >= ${denOt}::date`;
    },
    async neschetenite(userId, keys) {
      if (!keys || !keys.length) return [];
      return await sql`
        SELECT id, match_key, izbor FROM predictions
        WHERE user_id = ${userId} AND scored = FALSE AND match_key = ANY(${keys})`;
    },
    async otbelezhi(id, points) {
      await sql`UPDATE predictions SET scored = TRUE, points = ${points} WHERE id = ${id}`;
    },
    async tълpa(keys) {
      if (!keys || !keys.length) return [];
      return await sql`
        SELECT match_key, izbor, COUNT(*)::int AS n FROM predictions
        WHERE match_key = ANY(${keys}) GROUP BY match_key, izbor`;
    },
    async turnirTabla(limit) {
      return await sql`
        SELECT u.email,
               COALESCE(SUM(p.points), 0)::int AS points,
               COUNT(*) FILTER (WHERE p.scored)::int AS obshto,
               COUNT(*) FILTER (WHERE p.points > 0)::int AS tochni
        FROM predictions p JOIN users u ON u.id = p.user_id
        GROUP BY u.id, u.email
        HAVING COUNT(*) FILTER (WHERE p.scored) > 0
        ORDER BY points DESC, tochni DESC
        LIMIT ${limit}`;
    },
    async mojtRedNaTablata(userId) {
      const r = one(await sql`
        WITH t AS (
          SELECT user_id, COALESCE(SUM(points),0)::int AS points,
                 COUNT(*) FILTER (WHERE scored)::int AS obshto,
                 COUNT(*) FILTER (WHERE points > 0)::int AS tochni
          FROM predictions GROUP BY user_id
        ), r AS (SELECT user_id, points, obshto, tochni,
                 RANK() OVER (ORDER BY points DESC)::int AS rank FROM t)
        SELECT rank, points, obshto, tochni FROM r WHERE user_id = ${userId}`);
      return r;
    },

    /* ── РЕФЕРАЛИ ── */
    async refKod(userId) {
      const r = one(await sql`SELECT ref_code FROM users WHERE id = ${userId}`);
      return r ? r.ref_code : null;
    },
    async zadaiRefKod(userId, code) {
      await sql`UPDATE users SET ref_code = ${code} WHERE id = ${userId} AND ref_code IS NULL`;
    },
    async potrebitelPoRefKod(code) {
      return one(await sql`SELECT id, access_until FROM users WHERE ref_code = ${code}`);
    },
    async zapishiReferal(newUserId, referrerId) {
      await sql`UPDATE users SET referred_by = ${referrerId} WHERE id = ${newUserId} AND referred_by IS NULL`;
    },

    /* ── PUSH абонаменти ── */
    async zapishiAbonament(userId, endpoint, sub) {
      await sql`
        INSERT INTO push_subs (user_id, endpoint, sub) VALUES (${userId}, ${endpoint}, ${sub}::jsonb)
        ON CONFLICT (endpoint) DO UPDATE SET user_id = ${userId}, sub = ${sub}::jsonb`;
    },
  };
}
