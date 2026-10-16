-- STALCRAFT Market Bot - PostgreSQL Schema (Supabase)
-- Incorporates Patch 1 (Watchlist) and Patch 2 (Names only, multi-module filters_hash)

-- 1. Items table (Static catalog cache)
create table if not exists items (
  item_id text primary key,
  name_ru text not null,
  name_en text,
  category text,
  rank text,
  icon_path text,
  listing_path text,
  source text default 'exbo', -- 'exbo' | 'manual_override'
  tradable boolean default true,
  tradable_checked_at timestamptz,
  updated_at timestamptz default now()
);

create index if not exists idx_items_tradable on items(tradable);

-- 2. Watchlist table (Tracked items selected by human name)
create table if not exists watchlist (
  id bigserial primary key,
  region text not null default 'RU',
  item_id text not null references items(item_id) on delete cascade,
  alias text,
  enabled boolean not null default true,
  poll_interval_min int not null default 5 check (poll_interval_min >= 5),
  history_interval_min int not null default 30 check (history_interval_min >= 5),
  min_roi numeric,
  min_profit_abs numeric,
  max_buy_unit numeric,
  max_capital_share numeric,
  min_confidence real,
  filters jsonb not null default '{}'::jsonb,
  filters_hash text not null default '', -- SHA256 of normalized filters (Patch 2 Section 4)
  note text,
  tradable boolean,
  tradable_checked_at timestamptz,
  backfill_done boolean not null default false,
  last_lots_at timestamptz,
  last_history_at timestamptz,
  next_lots_at timestamptz,
  next_history_at timestamptz,
  added_at timestamptz not null default now(),
  unique (region, item_id, filters_hash)
);

create index if not exists idx_watchlist_enabled on watchlist(region, enabled);
create index if not exists idx_watchlist_next_polls on watchlist(next_lots_at, next_history_at);

-- 3. Lots table (Lifecycle tracking)
create table if not exists lots (
  id bigserial primary key,
  region text not null,
  item_id text not null references items(item_id) on delete cascade,
  fingerprint text not null,
  amount int not null check (amount > 0),
  start_price bigint default 0,
  current_price bigint default 0,
  buyout_price bigint default 0,
  start_time timestamptz,
  end_time timestamptz,
  additional jsonb,
  qlt int,
  segment_key text not null default '',
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  status text not null default 'active', -- 'active' | 'probable_sold' | 'expired_or_cancelled'
  sold_match_confidence real,
  unit_buyout numeric generated always as (buyout_price::numeric / nullif(amount, 0)) stored,
  unique (region, fingerprint)
);

create index if not exists idx_lots_region_item_status on lots(region, item_id, status);
create index if not exists idx_lots_segment_status on lots(segment_key, status);
create index if not exists idx_lots_last_seen on lots(last_seen);

-- 4. Sales table (Historical completed trades)
create table if not exists sales (
  id bigserial primary key,
  region text not null,
  item_id text not null references items(item_id) on delete cascade,
  segment_key text not null default '',
  amount int not null check (amount > 0),
  price bigint not null check (price >= 0),
  unit_price numeric generated always as (price::numeric / nullif(amount, 0)) stored,
  sold_at timestamptz not null,
  additional jsonb,
  additional_hash text not null default '',
  unique (region, item_id, sold_at, price, amount, additional_hash)
);

create index if not exists idx_sales_query on sales(region, item_id, segment_key, sold_at desc);
create index if not exists idx_sales_sold_at on sales(sold_at desc);

-- 5. Hourly / Daily Price Rollups
create table if not exists price_rollups (
  region text not null,
  item_id text not null references items(item_id) on delete cascade,
  segment_key text not null default '',
  bucket timestamptz not null,
  n_sales int not null default 0,
  units_sold numeric not null default 0,
  median_unit numeric not null default 0,
  p25_unit numeric not null default 0,
  p75_unit numeric not null default 0,
  active_lots int not null default 0,
  min_unit_buyout numeric,
  primary key (region, item_id, segment_key, bucket)
);

-- 6. Signals table
create table if not exists signals (
  id bigserial primary key,
  region text not null,
  lot_id bigint references lots(id) on delete set null,
  item_id text not null references items(item_id) on delete cascade,
  segment_key text not null default '',
  created_at timestamptz default now(),
  is_current boolean default true,
  buy_unit_price numeric not null,
  buy_max_unit numeric not null,
  fair_price numeric not null,
  target_sell_unit numeric not null,
  floor_sell_unit numeric not null,
  expected_profit numeric not null,
  profit_floor numeric not null,
  roi numeric not null,
  expected_days_to_sell numeric not null,
  liquidity_units_per_day numeric not null,
  confidence real not null,
  score numeric not null,
  data_age_min numeric not null,
  reasons jsonb not null default '[]'::jsonb,
  caveats jsonb not null default '[]'::jsonb
);

create index if not exists idx_signals_current on signals(region, is_current, score desc);

-- 7. Collector Runs (Health monitoring)
create table if not exists collector_runs (
  id bigserial primary key,
  started_at timestamptz default now(),
  finished_at timestamptz,
  workflow text not null,
  requests int default 0,
  ok int default 0,
  http_400 int default 0,
  http_401 int default 0,
  http_403 int default 0,
  http_429_1015 int default 0,
  http_429_quota int default 0,
  stale_slices int default 0,
  retries int default 0,
  runner_ip_hash text,
  notes jsonb default '{}'::jsonb
);

-- 8. Row-Level Security (RLS) Configuration (Patch 1 Section 8)
alter table items enable row level security;
alter table watchlist enable row level security;
alter table lots enable row level security;
alter table sales enable row level security;
alter table price_rollups enable row level security;
alter table signals enable row level security;
alter table collector_runs enable row level security;

-- Public / Anon can READ items, signals, lots, sales, rollups, watchlist
drop policy if exists "Public read items" on items;
create policy "Public read items" on items for select using (true);

drop policy if exists "Public read signals" on signals;
create policy "Public read signals" on signals for select using (true);

drop policy if exists "Public read lots" on lots;
create policy "Public read lots" on lots for select using (true);

drop policy if exists "Public read sales" on sales;
create policy "Public read sales" on sales for select using (true);

drop policy if exists "Public read rollups" on price_rollups;
create policy "Public read rollups" on price_rollups for select using (true);

drop policy if exists "Public read watchlist" on watchlist;
create policy "Public read watchlist" on watchlist for select using (true);

drop policy if exists "Owner write watchlist" on watchlist;
create policy "Owner write watchlist" on watchlist for all
  using (auth.role() = 'authenticated');

-- Retention Function (Patch 1 Section 7: 180 days sales, 30 days finished lots)
create or replace function prune_old_data(
  retention_days_lots int default 30,
  retention_days_sales int default 180
)
returns table (deleted_lots bigint, deleted_sales bigint) language plpgsql security definer as $$
declare
  v_lots_deleted bigint := 0;
  v_sales_deleted bigint := 0;
begin
  delete from lots
  where status in ('probable_sold', 'expired_or_cancelled')
    and last_seen < now() - (retention_days_lots || ' days')::interval;
  get diagnostics v_lots_deleted = row_count;

  delete from sales
  where sold_at < now() - (retention_days_sales || ' days')::interval;
  get diagnostics v_sales_deleted = row_count;

  return query select v_lots_deleted, v_sales_deleted;
end;
$$;
