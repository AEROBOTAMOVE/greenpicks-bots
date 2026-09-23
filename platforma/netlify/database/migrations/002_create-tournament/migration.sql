-- Турнир „Зелен фиш" (потребителски прогнози + класация) + реферали.
-- Прилага се автоматично от Netlify преди публикуване.

CREATE TABLE IF NOT EXISTS predictions (
  id         BIGSERIAL   PRIMARY KEY,
  user_id    BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  match_key  TEXT        NOT NULL,                 -- id на пика (den|sport|отбори)
  den        DATE        NOT NULL,
  sport      TEXT        NOT NULL DEFAULT '',
  izbor      TEXT        NOT NULL,                 -- '1' / 'X' / '2'
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  scored     BOOLEAN     NOT NULL DEFAULT FALSE,
  points     INT         NOT NULL DEFAULT 0,
  UNIQUE (user_id, match_key)
);
CREATE INDEX IF NOT EXISTS predictions_match_idx  ON predictions (match_key);
CREATE INDEX IF NOT EXISTS predictions_user_idx   ON predictions (user_id);
CREATE INDEX IF NOT EXISTS predictions_den_idx    ON predictions (den);

-- Реферали: код на всеки потребител + кой кого е довел (наградата = дни достъп,
-- дава се от бота/админа, тук пазим само атрибуцията).
ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_code    TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT REFERENCES users(id);
CREATE UNIQUE INDEX IF NOT EXISTS users_ref_code_idx ON users (ref_code) WHERE ref_code IS NOT NULL;
