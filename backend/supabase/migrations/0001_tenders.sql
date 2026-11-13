create extension if not exists vector;

create table if not exists tenders (
  id            text primary key,
  source_id     text not null,
  external_id   text not null,
  url           text not null,
  type          text not null default 'tender',
  title         text not null,
  title_en      text,
  description   text,
  buyer         jsonb,
  country       text,
  region        text,
  cpv           text[] default '{}',
  budget        jsonb,
  published_at  date,
  deadline_at   timestamptz,
  language      text,
  documents     jsonb default '[]',
  vertical      text,
  subsectors    text[] default '{}',
  relevance     real,
  assessment    jsonb,
  raw           jsonb,
  embedding     vector(1024),
  search        tsvector generated always as (
                  to_tsvector('simple', coalesce(title_en, title) || ' ' || coalesce(description, ''))
                ) stored,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now(),
  unique (source_id, external_id)
);

create index if not exists tenders_search_idx on tenders using gin (search);
create index if not exists tenders_subsectors_idx on tenders using gin (subsectors);
create index if not exists tenders_vertical_deadline_idx on tenders (vertical, deadline_at);
create index if not exists tenders_country_idx on tenders (country);
