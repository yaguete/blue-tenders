-- Historial de organizaciones. Reutiliza las tablas de 0003.
-- La ficha las lee en FileStore y en SupabaseStore; no van en load() de la cuenta.

alter table partner_projects add column if not exists acronym text;
alter table partner_projects add column if not exists topic_title text;

alter table partner_participations drop constraint if exists partner_participations_project_id_fkey;
alter table partner_participations
  add constraint partner_participations_project_id_fkey
  foreign key (project_id) references partner_projects (id) on delete cascade;

create index if not exists partner_participations_project_idx
  on partner_participations (project_id);

create table if not exists partner_sources (
  id text primary key,
  etag text,
  last_modified text,
  criteria_hash text,
  content_hash text,
  loaded_at timestamptz,
  since date,
  projects int,
  participations int
);

alter table partner_participations enable row level security;
alter table partner_sources enable row level security;
