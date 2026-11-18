-- Project Cerberus database schema.
-- Run once in Supabase: Dashboard > SQL Editor > New query > paste this > Run.
-- Safe to re-run.

create table if not exists public.sightings (
    id          bigint generated always as identity primary key,
    user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
    breed       text not null check (char_length(breed) between 1 and 100),
    seen_on     date not null check (seen_on <= current_date + 1),
    location    text check (char_length(location) <= 200),
    dog_name    text check (char_length(dog_name) <= 100),
    notes       text check (char_length(notes) <= 2000),
    created_at  timestamptz not null default now()
);

create index if not exists sightings_user_breed_idx on public.sightings (user_id, breed);

-- Row level security: signed-in users can only see and change their own sightings.
alter table public.sightings enable row level security;

drop policy if exists "Users can read their own sightings" on public.sightings;
create policy "Users can read their own sightings"
    on public.sightings for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can add their own sightings" on public.sightings;
create policy "Users can add their own sightings"
    on public.sightings for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their own sightings" on public.sightings;
create policy "Users can update their own sightings"
    on public.sightings for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their own sightings" on public.sightings;
create policy "Users can delete their own sightings"
    on public.sightings for delete
    to authenticated
    using ((select auth.uid()) = user_id);


-- +1 votes on upcoming features (Settings > What's new). `feature` is the id the app
-- makes from a roadmap item's title, e.g. "photo-upload". One vote per user per feature.
create table if not exists public.feature_votes (
    user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
    feature     text not null check (char_length(feature) between 1 and 100),
    created_at  timestamptz not null default now(),
    primary key (user_id, feature)
);

alter table public.feature_votes enable row level security;

drop policy if exists "Users can read their own votes" on public.feature_votes;
create policy "Users can read their own votes"
    on public.feature_votes for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can add their own votes" on public.feature_votes;
create policy "Users can add their own votes"
    on public.feature_votes for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can remove their own votes" on public.feature_votes;
create policy "Users can remove their own votes"
    on public.feature_votes for delete
    to authenticated
    using ((select auth.uid()) = user_id);

-- Vote totals for everyone, without revealing who voted: RLS above hides other people's
-- rows, so this function runs as its owner ("security definer") and returns only counts.
create or replace function public.feature_vote_counts()
returns table (feature text, votes bigint)
language sql
stable
security definer
set search_path = ''
as $$
    select v.feature, count(*) from public.feature_votes v group by v.feature;
$$;

revoke execute on function public.feature_vote_counts() from public, anon;
grant execute on function public.feature_vote_counts() to authenticated;


-- Feature ideas sent from Settings > What's new. Users can only see their own; the owner
-- reads them all in the Supabase dashboard (Table Editor > feature_suggestions).
create table if not exists public.feature_suggestions (
    id          bigint generated always as identity primary key,
    user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
    suggestion  text not null check (char_length(suggestion) between 1 and 500),
    created_at  timestamptz not null default now()
);

alter table public.feature_suggestions enable row level security;

drop policy if exists "Users can read their own suggestions" on public.feature_suggestions;
create policy "Users can read their own suggestions"
    on public.feature_suggestions for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can add their own suggestions" on public.feature_suggestions;
create policy "Users can add their own suggestions"
    on public.feature_suggestions for insert
    to authenticated
    with check ((select auth.uid()) = user_id);
