-- Ejecuciones de ingesta, historial que el cron comparte con el API,
-- y el estado de cuenta fuera del disco de la máquina.

create table if not exists ingest_runs (
  id text primary key,
  source text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',
  since date,
  until date,
  raw_count int,
  kept int,
  indexed int,
  unchanged int,
  message text
);

create unique index if not exists ingest_runs_one_open
  on ingest_runs (source)
  where finished_at is null;

alter table opportunities add column if not exists listed boolean default true;

create table if not exists app_profiles (
  user_id text primary key,
  body jsonb not null
);

create table if not exists app_saved (
  id text primary key,
  body jsonb not null
);

create table if not exists app_alerts (
  id text primary key,
  body jsonb not null
);

create table if not exists app_reviews (
  id text primary key,
  body jsonb not null
);

create table if not exists app_reports (
  id text primary key,
  body jsonb not null
);

create table if not exists app_conversations (
  id text primary key,
  body jsonb not null
);

create table if not exists app_usage (
  id text primary key,
  body jsonb not null
);

create table if not exists app_suppressions (
  id text primary key,
  body jsonb not null
);

create table if not exists watched_snapshots (
  page_id text primary key,
  text_hash text not null,
  body text not null,
  fetched_at timestamptz not null default now()
);
