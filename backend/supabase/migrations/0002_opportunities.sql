-- Tender pasa a ser Opportunity. La vista `tenders` deja fuera las adjudicaciones.

alter table tenders rename to opportunities;

alter table opportunities add column if not exists kind text;
alter table opportunities add column if not exists notice text;
alter table opportunities add column if not exists instruments jsonb default '[]';
alter table opportunities add column if not exists summary_en text;
alter table opportunities add column if not exists funder_id text;
alter table opportunities add column if not exists programme_id text;
alter table opportunities add column if not exists call_id text;
alter table opportunities add column if not exists topic_id text;
alter table opportunities add column if not exists type_of_action text;
alter table opportunities add column if not exists mission_ocean boolean default false;
alter table opportunities add column if not exists nuts text[] default '{}';
alter table opportunities add column if not exists budget_total_eur double precision;
alter table opportunities add column if not exists amount_min_eur double precision;
alter table opportunities add column if not exists amount_max_eur double precision;
alter table opportunities add column if not exists cofunding_min real;
alter table opportunities add column if not exists cofunding_max real;
alter table opportunities add column if not exists opens_at timestamptz;
alter table opportunities add column if not exists deadline_model text default 'single';
alter table opportunities add column if not exists deadlines jsonb default '[]';
alter table opportunities add column if not exists status text;
alter table opportunities add column if not exists sea_basins text[] default '{}';
alter table opportunities add column if not exists trl_min smallint;
alter table opportunities add column if not exists trl_max smallint;
alter table opportunities add column if not exists sdgs int[] default '{}';
alter table opportunities add column if not exists eligible_entity_types text[] default '{}';
alter table opportunities add column if not exists eligible_countries text[] default '{}';
alter table opportunities add column if not exists consortium_required boolean;
alter table opportunities add column if not exists consortium_min_partners int;
alter table opportunities add column if not exists consortium_min_countries int;
alter table opportunities add column if not exists analysis jsonb;
alter table opportunities add column if not exists facts jsonb default '[]';
alter table opportunities add column if not exists content_hash text;
alter table opportunities add column if not exists review_status text;

update opportunities
set kind = case type
      when 'grant' then 'grant'
      when 'award' then 'tender'
      else 'tender'
    end,
    notice = case type
      when 'grant' then 'call_for_proposals'
      when 'prior_information_notice' then 'pin'
      when 'award' then 'award_notice'
      else 'contract_notice'
    end
where kind is null or notice is null;

create or replace view tenders as
select * from opportunities
where kind = 'tender' and notice is distinct from 'award_notice';

alter table opportunities enable row level security;

drop policy if exists opportunities_public_read on opportunities;
create policy opportunities_public_read on opportunities
  for select using (notice is distinct from 'award_notice');
