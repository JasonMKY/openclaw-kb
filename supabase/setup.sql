-- ============================================================================
-- KBHub — Supabase Schema Setup
-- Run this in the Supabase SQL Editor (Dashboard > SQL Editor > New Query)
-- ============================================================================

-- 1. Profiles (auto-created on signup via trigger)
-- ============================================================================
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  display_name text not null,
  handle      text unique not null,
  avatar_url  text,
  created_at  timestamptz default now()
);

alter table public.profiles enable row level security;

drop policy if exists "Anyone can view profiles" on public.profiles;
create policy "Anyone can view profiles"
  on public.profiles for select using (true);

drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile"
  on public.profiles for update using (auth.uid() = id);

-- Auto-create a profile row when a new user signs up
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name, handle)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'display_name', 'User'),
    coalesce(new.raw_user_meta_data ->> 'handle', 'user-' || left(new.id::text, 8))
  );
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();


-- 2. Knowledge Bases (the catalog)
-- ============================================================================
create table if not exists public.knowledge_bases (
  id          uuid primary key default gen_random_uuid(),
  slug        text unique not null,
  name        text not null,
  description text,
  icon        text default '🧠',
  category    text not null,
  tags        text[] default '{}',
  namespace   text not null,
  visibility  text default 'public' check (visibility in ('public', 'unlisted', 'private')),
  author_id   uuid references public.profiles(id) not null,
  bundle_path text not null,
  doc_count   int default 0,
  chunk_count int default 0,
  clone_count int default 0,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

alter table public.knowledge_bases enable row level security;

drop policy if exists "Anyone can view public KBs" on public.knowledge_bases;
create policy "Anyone can view public KBs"
  on public.knowledge_bases for select
  using (visibility = 'public');

drop policy if exists "Authors can view own KBs" on public.knowledge_bases;
create policy "Authors can view own KBs"
  on public.knowledge_bases for select
  using (auth.uid() = author_id);

drop policy if exists "Authenticated users can publish" on public.knowledge_bases;
create policy "Authenticated users can publish"
  on public.knowledge_bases for insert
  with check (auth.uid() = author_id);

drop policy if exists "Authors can update own KBs" on public.knowledge_bases;
create policy "Authors can update own KBs"
  on public.knowledge_bases for update
  using (auth.uid() = author_id);

drop policy if exists "Authors can delete own KBs" on public.knowledge_bases;
create policy "Authors can delete own KBs"
  on public.knowledge_bases for delete
  using (auth.uid() = author_id);


-- 3. Stars
-- ============================================================================
create table if not exists public.stars (
  user_id    uuid references public.profiles(id) on delete cascade,
  kb_id      uuid references public.knowledge_bases(id) on delete cascade,
  created_at timestamptz default now(),
  primary key (user_id, kb_id)
);

alter table public.stars enable row level security;

drop policy if exists "Anyone can view stars" on public.stars;
create policy "Anyone can view stars"
  on public.stars for select using (true);

drop policy if exists "Authenticated users can star" on public.stars;
create policy "Authenticated users can star"
  on public.stars for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can unstar their own" on public.stars;
create policy "Users can unstar their own"
  on public.stars for delete
  using (auth.uid() = user_id);

-- 4b. Clones (track which KBs a user cloned from KBHub)
-- ============================================================================
create table if not exists public.kb_clones (
  user_id    uuid references public.profiles(id) on delete cascade,
  kb_id      uuid references public.knowledge_bases(id) on delete cascade,
  created_at timestamptz default now(),
  primary key (user_id, kb_id)
);

alter table public.kb_clones enable row level security;

drop policy if exists "Users can view their cloned KBs" on public.kb_clones;
drop policy if exists "Users can insert their cloned KBs" on public.kb_clones;
drop policy if exists "Users can update their cloned KBs" on public.kb_clones;

create policy "Users can view their cloned KBs"
  on public.kb_clones for select
  using (auth.uid() = user_id);

create policy "Users can insert their cloned KBs"
  on public.kb_clones for insert
  with check (auth.uid() = user_id);

-- Required for upsert() with onConflict.
create policy "Users can update their cloned KBs"
  on public.kb_clones for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- 4. Reviews
-- ============================================================================
create table if not exists public.reviews (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references public.profiles(id) on delete cascade,
  kb_id      uuid references public.knowledge_bases(id) on delete cascade,
  rating     int check (rating between 1 and 5),
  body       text,
  created_at timestamptz default now(),
  unique (user_id, kb_id)
);

alter table public.reviews enable row level security;

drop policy if exists "Anyone can view reviews" on public.reviews;
create policy "Anyone can view reviews"
  on public.reviews for select using (true);

drop policy if exists "Authenticated users can review" on public.reviews;
create policy "Authenticated users can review"
  on public.reviews for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can delete own reviews" on public.reviews;
create policy "Users can delete own reviews"
  on public.reviews for delete
  using (auth.uid() = user_id);


-- 4c. Add price_cents to knowledge_bases (0 = free, positive = price in cents)
-- ============================================================================
alter table public.knowledge_bases add column if not exists price_cents int default 0;

-- 4d. Add stripe_account_id to profiles (for Stripe Connect payouts)
-- ============================================================================
alter table public.profiles add column if not exists stripe_account_id text;

-- 4e. Purchases (tracks paid KB purchases)
-- ============================================================================
create table if not exists public.kb_purchases (
  id              uuid primary key default gen_random_uuid(),
  buyer_id        uuid references public.profiles(id) on delete cascade not null,
  kb_id           uuid references public.knowledge_bases(id) on delete cascade not null,
  stripe_session_id text,
  amount_cents    int not null,
  fee_cents       int not null,
  status          text default 'pending' check (status in ('pending','completed','refunded')),
  created_at      timestamptz default now(),
  unique (buyer_id, kb_id)
);

alter table public.kb_purchases enable row level security;

drop policy if exists "Buyers can view own purchases" on public.kb_purchases;
create policy "Buyers can view own purchases"
  on public.kb_purchases for select
  using (auth.uid() = buyer_id);

drop policy if exists "Buyers can insert own purchases" on public.kb_purchases;
create policy "Buyers can insert own purchases"
  on public.kb_purchases for insert
  with check (auth.uid() = buyer_id);


-- 5. Helper: increment clone count (called via supabase.rpc)
-- ============================================================================
create or replace function public.increment_clones(kb_id uuid)
returns void as $$
begin
  update public.knowledge_bases
  set clone_count = clone_count + 1,
      updated_at = now()
  where id = kb_id;
end;
$$ language plpgsql security definer;


-- 6. View: KB listing with aggregated star/review counts
-- Uses SECURITY INVOKER so the view runs as the querying user and respects RLS.
-- (SECURITY DEFINER would run as the view owner and bypass RLS — avoid.)
-- To fix an existing DB that has DEFINER, run: supabase/fix_kb_listing_security.sql
-- ============================================================================
create or replace view public.kb_listing
with (security_invoker = on)
as
select
  kb.*,
  p.display_name as author_name,
  p.handle as author_handle,
  coalesce(s.star_count, 0) as star_count,
  coalesce(r.review_count, 0) as review_count,
  coalesce(r.avg_rating, 0) as avg_rating
from public.knowledge_bases kb
join public.profiles p on p.id = kb.author_id
left join (
  select kb_id, count(*) as star_count from public.stars group by kb_id
) s on s.kb_id = kb.id
left join (
  select kb_id, count(*) as review_count, round(avg(rating), 1) as avg_rating
  from public.reviews group by kb_id
) r on r.kb_id = kb.id;


-- 7. Storage bucket for KB bundles
-- ============================================================================
-- NOTE: Run this separately or create the bucket via Supabase Dashboard:
--   Storage > New bucket > Name: "kb-bundles" > Public: ON
--
-- If you want to do it via SQL (requires service_role):
-- insert into storage.buckets (id, name, public) values ('kb-bundles', 'kb-bundles', true);
--
-- Storage policies (run in SQL editor):

-- Allow anyone to download bundles (for cloning)
-- create policy "Public read for kb-bundles"
--   on storage.objects for select
--   using (bucket_id = 'kb-bundles');

-- Allow authenticated users to upload bundles
-- create policy "Authenticated upload for kb-bundles"
--   on storage.objects for insert
--   with check (bucket_id = 'kb-bundles' and auth.role() = 'authenticated');

-- Allow users to delete their own bundles
-- create policy "Owner delete for kb-bundles"
--   on storage.objects for delete
--   using (bucket_id = 'kb-bundles' and auth.uid()::text = (storage.foldername(name))[1]);

-- Actual Storage policies (run in SQL editor)
drop policy if exists "Public read for kb-bundles" on storage.objects;
drop policy if exists "Authenticated upload for kb-bundles" on storage.objects;
drop policy if exists "Authenticated upsert for kb-bundles" on storage.objects;
drop policy if exists "Owner delete for kb-bundles" on storage.objects;

-- Allow anyone to download bundles (for cloning)
create policy "Public read for kb-bundles"
  on storage.objects for select
  to public
  using (bucket_id = 'kb-bundles');

-- Allow authenticated users to upload bundles into their own folder
create policy "Authenticated upload for kb-bundles"
  on storage.objects for insert
  to authenticated
  with check (
    bucket_id = 'kb-bundles'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

-- Upsert requires UPDATE permissions too.
create policy "Authenticated upsert for kb-bundles"
  on storage.objects for update
  to authenticated
  using (
    bucket_id = 'kb-bundles'
    and auth.uid()::text = (storage.foldername(name))[1]
  )
  with check (
    bucket_id = 'kb-bundles'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

-- Allow users to delete their own bundles
create policy "Owner delete for kb-bundles"
  on storage.objects for delete
  to authenticated
  using (
    bucket_id = 'kb-bundles'
    and auth.uid()::text = (storage.foldername(name))[1]
  );
