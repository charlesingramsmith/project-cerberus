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
