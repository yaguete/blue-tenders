create table if not exists plans (
  id text primary key,
  name text not null
);

insert into plans (id, name) values ('free', 'Free')
on conflict (id) do nothing;

create table if not exists org_profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  name text,
  entity_type text,
  country text,
  subsectors text[] default '{}',
  size text,
  trl int,
  role text,
  pic text
);

create table if not exists subscriptions (
  user_id uuid primary key references auth.users (id) on delete cascade,
  plan_id text references plans (id) default 'free'
);

create table if not exists saved_opportunities (
  user_id uuid references auth.users (id) on delete cascade,
  opportunity_id text,
  note text,
  created_at timestamptz default now(),
  primary key (user_id, opportunity_id)
);

create table if not exists saved_searches (
  id text primary key,
  user_id uuid references auth.users (id) on delete cascade,
  email text not null,
  filters jsonb not null,
  cadence text not null check (cadence in ('daily', 'weekly')),
  consent_at timestamptz not null,
  last_sent_at timestamptz,
  unsubscribe_token text not null
);

create table if not exists email_suppressions (
  id text primary key,
  created_at timestamptz default now()
);

alter table org_profiles enable row level security;
alter table saved_opportunities enable row level security;
alter table saved_searches enable row level security;

create policy profiles_own on org_profiles for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy saved_own on saved_opportunities for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy alerts_own on saved_searches for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
