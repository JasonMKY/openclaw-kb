-- ============================================================================
-- One-time fix: Remove SECURITY DEFINER from public.kb_listing
-- Run this in Supabase SQL Editor if the security scanner reported:
--   "View public.kb_listing is defined with the SECURITY DEFINER property"
--
-- Why: Views with SECURITY DEFINER run with the view owner's privileges and
-- can bypass RLS. Recreating the view as SECURITY INVOKER ensures the view
-- runs as the querying user and RLS on knowledge_bases, profiles, stars,
-- and reviews is enforced.
-- ============================================================================

begin;

drop view if exists public.kb_listing;

create view public.kb_listing
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

commit;

-- Optional: Restrict SELECT to only the roles that need it (recommended).
-- Revoke from public if you use anon/authenticated roles explicitly:
-- revoke all on public.kb_listing from public;
-- grant select on public.kb_listing to anon, authenticated;
