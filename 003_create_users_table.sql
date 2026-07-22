-- Run this once in the Supabase SQL editor (Supabase → your project →
-- SQL Editor → New query → paste → Run). This adds login accounts for the
-- Grain Monitoring System. It does not touch any existing tables/data.

CREATE TABLE IF NOT EXISTS app_users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL DEFAULT 'viewer'
                  CHECK (role IN ('admin', 'data_entry', 'viewer')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login    TIMESTAMPTZ
);

-- Access levels:
--   admin       — full access, including the Data Entry tab
--   data_entry  — same tabs as admin, including Data Entry
--   viewer      — all reporting tabs, but the Data Entry tab is hidden entirely
--
-- After creating this table, generate your first (admin) account by running
-- tools/hash_password.py on your own computer (see README.md → "Managing
-- user accounts") and pasting the INSERT statement it prints here.

-- If you already created app_users before roles were added, run this once
-- to bring an existing table up to date (safe to run even if already applied):
-- ALTER TABLE app_users DROP CONSTRAINT IF EXISTS app_users_role_check;
-- ALTER TABLE app_users ADD CONSTRAINT app_users_role_check
--     CHECK (role IN ('admin', 'data_entry', 'viewer'));
-- ALTER TABLE app_users ALTER COLUMN role SET DEFAULT 'viewer';
-- UPDATE app_users SET role = 'data_entry' WHERE role = 'staff';
