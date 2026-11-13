create table if not exists document_chunks (
  id bigserial primary key,
  opportunity_id text,
  document_url text,
  page int,
  text text,
  embedding vector(1024)
);

create table if not exists conversations (
  id bigserial primary key,
  user_id uuid references auth.users (id) on delete cascade,
  opportunity_id text,
  question text,
  answer text,
  citations jsonb,
  model text,
  created_at timestamptz default now()
);

create table if not exists usage_counters (
  user_id uuid references auth.users (id) on delete cascade,
  day date not null,
  count int default 0,
  primary key (user_id, day)
);

alter table conversations enable row level security;
alter table usage_counters enable row level security;

create policy conversations_own on conversations for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy usage_own on usage_counters for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create index if not exists chunks_opportunity_idx on document_chunks (opportunity_id);
