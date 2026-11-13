-- Identificador compartido entre fuentes (expediente, ocid).
-- Sin esta columna la deduplicación solo ve el lote de una ejecución.

alter table opportunities add column if not exists dedupe_key text;

create index if not exists opportunities_dedupe_key_idx
  on opportunities (dedupe_key)
  where dedupe_key is not null;

alter table ingest_runs add column if not exists skipped_eu int;
