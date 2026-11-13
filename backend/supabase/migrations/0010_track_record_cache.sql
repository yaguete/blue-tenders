-- Historial ya calculado de cada convocatoria. La ficha lo lee;
-- si inputs_hash no coincide, calcula en vivo y no enseña el resultado viejo.

alter table opportunity_partner_matches add column if not exists source text;
alter table opportunity_partner_matches add column if not exists rank int;
alter table opportunity_partner_matches add column if not exists evidence text;
alter table opportunity_partner_matches add column if not exists projects jsonb;

create table if not exists opportunity_track_record (
  opportunity_id text primary key,
  source text not null,
  status text not null,
  total int,
  inputs_hash text,
  computed_at timestamptz,
  loaded_at text,
  since text,
  items jsonb,
  pending boolean default false
);

alter table opportunity_track_record enable row level security;
