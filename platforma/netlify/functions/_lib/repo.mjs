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
  };
}
