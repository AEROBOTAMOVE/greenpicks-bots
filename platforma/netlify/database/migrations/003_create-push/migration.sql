-- Push абонаменти (PWA web-push). Изпращането е от бота с VAPID ключовете.
CREATE TABLE IF NOT EXISTS push_subs (
  id         BIGSERIAL   PRIMARY KEY,
  user_id    BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  endpoint   TEXT        NOT NULL UNIQUE,
  sub        JSONB       NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS push_subs_user_idx ON push_subs (user_id);
