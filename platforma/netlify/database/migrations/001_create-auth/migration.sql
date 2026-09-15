-- AERO клиент · профили, сесии, опити за вход
-- Прилага се автоматично от Netlify преди публикуване.

CREATE TABLE IF NOT EXISTS users (
  id           BIGSERIAL PRIMARY KEY,
  email        TEXT        NOT NULL UNIQUE,
  pass_hash    TEXT        NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  access_until TIMESTAMPTZ NOT NULL,
  locked       BOOLEAN     NOT NULL DEFAULT FALSE,
  last_login   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT        PRIMARY KEY,
  user_id    BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id);
CREATE INDEX IF NOT EXISTS sessions_expires_idx ON sessions (expires_at);

-- kind = 'login' (subject = имейл) или 'register' (subject = IP адрес)
CREATE TABLE IF NOT EXISTS login_attempts (
  id      BIGSERIAL   PRIMARY KEY,
  subject TEXT        NOT NULL,
  kind    TEXT        NOT NULL DEFAULT 'login',
  at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS login_attempts_lookup_idx ON login_attempts (subject, kind, at);
