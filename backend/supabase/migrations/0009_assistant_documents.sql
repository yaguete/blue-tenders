-- Documentos que lee el asistente. Solo texto por página: el PDF no se guarda.
-- El borrado de cuenta lo hace la API. user_id es text porque la demo local no es un uuid.

create table if not exists document_files (
  id text primary key,
  opportunity_id text not null default '',
  document_url text not null,
  name text,
  kind text,
  access text,
  status text not null,
  pages int,
  error text,
  fetched_at timestamptz,
  programme_id text,
  version text
);

create unique index if not exists document_files_key
  on document_files (opportunity_id, document_url);

create table if not exists document_pages (
  id text primary key,
  file_id text not null references document_files (id) on delete cascade,
  page int not null,
  heading text,
  text text not null
);

create index if not exists document_pages_file_idx on document_pages (file_id, page);

create table if not exists assistant_messages (
  id text primary key,
  conversation_id text not null,
  user_id text not null,
  opportunity_id text,
  role text not null,
  text text not null,
  citations jsonb,
  model text,
  input_tokens int,
  output_tokens int,
  cache_read_tokens int,
  cache_write_tokens int,
  cost_usd double precision,
  latency_ms int,
  created_at timestamptz not null default now()
);

create index if not exists assistant_messages_conversation_idx
  on assistant_messages (conversation_id, created_at);

create index if not exists assistant_messages_user_idx on assistant_messages (user_id);

create table if not exists assistant_uploads (
  id text primary key,
  user_id text not null,
  conversation_id text,
  name text not null,
  pages int,
  expires_at timestamptz not null
);

create table if not exists assistant_upload_pages (
  id text primary key,
  upload_id text not null references assistant_uploads (id) on delete cascade,
  page int not null,
  heading text,
  text text not null
);

alter table assistant_messages enable row level security;
alter table assistant_uploads enable row level security;
alter table assistant_upload_pages enable row level security;

create policy assistant_messages_own on assistant_messages
  for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
create policy assistant_uploads_own on assistant_uploads
  for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
create policy assistant_upload_pages_own on assistant_upload_pages
  for all using (
    exists (
      select 1 from assistant_uploads
      where assistant_uploads.id = upload_id and assistant_uploads.user_id = auth.uid()::text
    )
  )
  with check (
    exists (
      select 1 from assistant_uploads
      where assistant_uploads.id = upload_id and assistant_uploads.user_id = auth.uid()::text
    )
  );
