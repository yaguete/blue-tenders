create table if not exists partner_orgs (
  id text primary key,
  pic text unique,
  name text not null,
  country text,
  nuts text,
  activity_type text,
  sme boolean
);

create table if not exists partner_projects (
  id text primary key,
  source text not null,
  programme_id text,
  topic text,
  title text,
  objective text,
  start_date date,
  end_date date,
  ec_contribution numeric,
  subsectors text[] default '{}',
  url text,
  demo boolean default false
);

create table if not exists partner_participations (
  org_id text references partner_orgs (id),
  project_id text references partner_projects (id),
  role text,
  primary key (org_id, project_id)
);

create table if not exists opportunity_partner_matches (
  opportunity_id text references opportunities (id),
  org_id text references partner_orgs (id),
  score real,
  reasons jsonb,
  primary key (opportunity_id, org_id)
);

create table if not exists funders (
  id text primary key,
  name text not null,
  kind text not null,
  url text,
  summary text,
  instruments jsonb default '[]',
  geographies text[] default '{}',
  subsectors text[] default '{}',
  ticket_min_eur numeric,
  ticket_max_eur numeric,
  is_directory_listed boolean default true,
  last_verified date
);

create table if not exists review_queue (
  id text primary key,
  opportunity_id text,
  reason text not null,
  field text,
  detail text,
  resolved boolean default false,
  created_at timestamptz default now()
);

create table if not exists user_reports (
  id text primary key,
  opportunity_id text,
  field text,
  note text,
  created_at timestamptz default now()
);

create table if not exists field_history (
  id bigserial primary key,
  opportunity_id text,
  field text,
  old_value jsonb,
  new_value jsonb,
  changed_at timestamptz default now()
);

alter table partner_orgs enable row level security;
alter table partner_projects enable row level security;
alter table funders enable row level security;

create policy partner_orgs_read on partner_orgs for select using (true);
create policy partner_projects_read on partner_projects for select using (true);
create policy funders_read on funders for select using (true);
