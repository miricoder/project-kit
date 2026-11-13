-- Schema 1: users, sign-in, sessions, captures, items, batches, undo entries.
-- docs/spec.md "Data model". v1 migrations are additive only.

CREATE TABLE schema_meta (
  schema_version integer NOT NULL,
  migrated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app_user (
  id bigserial PRIMARY KEY,
  email text NOT NULL UNIQUE,
  tz text NOT NULL DEFAULT 'Europe/Lisbon',
  monthly_budget_cents bigint,
  home_currency text NOT NULL DEFAULT 'EUR',
  seq bigint NOT NULL DEFAULT 0,            -- per-user change counter (updated_seq source)
  next_ref integer NOT NULL DEFAULT 1,      -- refs t12 / e88 / p3 share one counter, never reused
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sign_in_link (
  token_hash text PRIMARY KEY,
  user_email text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sign_in_link_email ON sign_in_link (user_email, created_at);

CREATE TABLE session (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  device_label text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);

CREATE TABLE batch (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
  capture_id uuid NOT NULL UNIQUE,
  applied_at timestamptz NOT NULL DEFAULT now(),
  prompt_version text NOT NULL,
  model text NOT NULL,
  undone_at timestamptz
);

CREATE TABLE capture (
  id uuid PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
  text text NOT NULL CHECK (char_length(text) <= 4000),
  source text NOT NULL CHECK (source IN ('typed', 'paste')),
  captured_at text NOT NULL,
  tz text NOT NULL,
  status text NOT NULL CHECK (status IN ('filed', 'failed', 'note')),
  filed_batch_id bigint REFERENCES batch (id),
  response jsonb,                            -- the stored answer, returned on a repeat
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE trip (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
  ref text NOT NULL,
  name text NOT NULL,
  start_date date NOT NULL,
  end_date date NOT NULL,
  budget_cents bigint,
  rev integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  created_batch_id bigint REFERENCES batch (id),
  updated_seq bigint NOT NULL,
  UNIQUE (user_id, ref)
);

CREATE TABLE task (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
  ref text NOT NULL,
  title text NOT NULL,
  due_date date,
  due_time text,
  done_at timestamptz,
  trip_id bigint REFERENCES trip (id),
  template_key text,
  reminded_at timestamptz,
  rev integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  created_batch_id bigint REFERENCES batch (id),
  updated_seq bigint NOT NULL,
  UNIQUE (user_id, ref)
);

CREATE TABLE expense (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
  ref text NOT NULL,
  amount_cents bigint NOT NULL CHECK (amount_cents > 0),
  date date NOT NULL,
  category text NOT NULL,
  description text NOT NULL,
  trip_id bigint REFERENCES trip (id),
  trip_link text NOT NULL DEFAULT 'none' CHECK (trip_link IN ('named', 'by_date', 'none')),
  rev integer NOT NULL DEFAULT 1,
  deleted_at timestamptz,
  created_batch_id bigint REFERENCES batch (id),
  updated_seq bigint NOT NULL,
  UNIQUE (user_id, ref)
);

CREATE TABLE note (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
  capture_id uuid NOT NULL,
  text text NOT NULL,
  suggestions jsonb NOT NULL DEFAULT '[]',
  updated_seq bigint NOT NULL
);

CREATE TABLE undo_entry (
  id bigserial PRIMARY KEY,
  batch_id bigint NOT NULL REFERENCES batch (id) ON DELETE CASCADE,
  item_kind text NOT NULL,
  item_id bigint NOT NULL,
  inverse_op jsonb NOT NULL,
  after_rev integer NOT NULL
);

CREATE TABLE daily_usage (
  day date NOT NULL,
  user_id bigint NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
  captures integer NOT NULL DEFAULT 0,
  PRIMARY KEY (day, user_id)
);

CREATE TABLE daily_spend (
  day date PRIMARY KEY,
  micro_eur bigint NOT NULL DEFAULT 0
);

CREATE INDEX task_user_seq ON task (user_id, updated_seq);
CREATE INDEX expense_user_seq ON expense (user_id, updated_seq);
CREATE INDEX trip_user_seq ON trip (user_id, updated_seq);
CREATE INDEX note_user_seq ON note (user_id, updated_seq);
CREATE INDEX expense_user_date ON expense (user_id, date);
