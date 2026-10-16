-- STALCRAFT Market Bot - PostgreSQL Schema Migration 002 (Patch 3: Auction Terminal)
-- Adds: signal_status, positions, notifications_log, signal_outcomes, item_state, hour_stats

-- 1. Signal Status (User marks: bought / skipped / new)
create table if not exists signal_status (
  id bigserial primary key,
  item_id text not null,
  segment_key text not null default '',
  fingerprint text,
  user_status text not null check (user_status in ('new', 'bought', 'skipped')),
  bought_price numeric,
  bought_amount int,
  marked_at timestamptz default now()
);

create index if not exists idx_signal_status_item on signal_status(item_id, segment_key);

-- 2. Positions (Trading inventory & tracking from purchase to sale)
create table if not exists positions (
  id bigserial primary key,
  item_id text not null,
  name_ru text not null,
  segment_key text not null default '',
  segment_label text default '',
  amount int not null check (amount > 0),
  buy_price_unit numeric not null,
  buy_time timestamptz not null default now(),
  status text not null default 'open' check (status in ('open', 'sold')),
  target_sell_price numeric,
  break_even_price numeric generated always as (buy_price_unit / 0.95) stored,
  sold_price_unit numeric,
  sold_time timestamptz,
  realized_profit numeric,
  notes text
);

create index if not exists idx_positions_status on positions(status, buy_time desc);

-- 3. Notifications Log (History of delivered alerts across channels)
create table if not exists notifications_log (
  id bigserial primary key,
  channel text not null, -- 'telegram' | 'discord'
  sent_at timestamptz not null default now(),
  item_id text not null,
  segment_key text default '',
  buy_price numeric not null,
  target_price numeric not null,
  expected_profit numeric not null,
  roi numeric not null,
  status text not null default 'sent'
);

create index if not exists idx_notifications_log_time on notifications_log(sent_at desc);

-- 4. Signal Outcomes (For Signal Accuracy Panel: Directional Hit & Profit Realizability)
create table if not exists signal_outcomes (
  id bigserial primary key,
  signal_id bigint,
  item_id text not null,
  segment_key text not null default '',
  signal_time timestamptz not null,
  horizon_hours int not null default 24,
  buy_price numeric not null,
  target_sell_price numeric not null,
  direction_hit boolean not null default false,
  profit_realized boolean not null default false,
  actual_median_at_horizon numeric,
  max_real_sale_in_horizon numeric,
  checked_at timestamptz default now()
);

create index if not exists idx_signal_outcomes_horizon on signal_outcomes(horizon_hours, signal_time desc);

-- 5. Item State (Fast 1-row cache per tracked item for instant Catalog & Market tabs)
create table if not exists item_state (
  item_id text primary key,
  updated_at timestamptz not null default now(),
  orderbook_floor numeric default 0,
  depth_below_target int default 0,
  median_24h numeric default 0,
  median_3d numeric default 0,
  median_7d numeric default 0,
  sales_count_24h int default 0,
  sales_count_3d int default 0,
  sparkline_7d jsonb not null default '[]'::jsonb,
  orderbook_ladder jsonb not null default '[]'::jsonb
);

-- 6. Hour Stats (Best trading hour heatmap: Day of Week x Hour)
create table if not exists hour_stats (
  item_id text not null,
  day_of_week int not null check (day_of_week between 0 and 6),
  hour_of_day int not null check (hour_of_day between 0 and 23),
  n_sales int not null default 0,
  avg_unit_price numeric not null default 0,
  median_unit_price numeric not null default 0,
  primary key (item_id, day_of_week, hour_of_day)
);

-- 7. RLS Configuration (Public read, authenticated / service_role write)
alter table signal_status enable row level security;
alter table positions enable row level security;
alter table notifications_log enable row level security;
alter table signal_outcomes enable row level security;
alter table item_state enable row level security;
alter table hour_stats enable row level security;

-- Public / Anon read policies
drop policy if exists "Public read signal_status" on signal_status;
create policy "Public read signal_status" on signal_status for select using (true);

drop policy if exists "Public read positions" on positions;
create policy "Public read positions" on positions for select using (true);

drop policy if exists "Public read notifications_log" on notifications_log;
create policy "Public read notifications_log" on notifications_log for select using (true);

drop policy if exists "Public read signal_outcomes" on signal_outcomes;
create policy "Public read signal_outcomes" on signal_outcomes for select using (true);

drop policy if exists "Public read item_state" on item_state;
create policy "Public read item_state" on item_state for select using (true);

drop policy if exists "Public read hour_stats" on hour_stats;
create policy "Public read hour_stats" on hour_stats for select using (true);

-- Public / Anon write policies for user client actions (marking bought/skipped and managing positions)
drop policy if exists "Public insert signal_status" on signal_status;
create policy "Public insert signal_status" on signal_status for insert with check (true);

drop policy if exists "Public insert positions" on positions;
create policy "Public insert positions" on positions for insert with check (true);

drop policy if exists "Public update positions" on positions;
create policy "Public update positions" on positions for update using (true);
