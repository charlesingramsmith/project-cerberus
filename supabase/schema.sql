-- Derlin database schema (the code and repo are still called project-cerberus).
-- Apply with the Supabase CLI (see docs/supabase-cli.md):
--   supabase db query --remote --yes -f supabase/schema.sql
-- or paste it into Supabase: Dashboard > SQL Editor > New query > Run.
-- Safe to re-run: keep every statement idempotent.

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


-- Profiles: the public face of each member (Profile tab, and names in the Social feed).
-- The app creates a member's profile the first time they sign in. Never holds emails.
create table if not exists public.profiles (
    user_id          uuid primary key default auth.uid() references auth.users (id) on delete cascade,
    username         text not null check (char_length(username) between 3 and 30),
    -- A breed name (shown as that breed's photo), or an emoji from before photos.
    avatar           text not null default '🐶',
    favourite_breed  text check (char_length(favourite_breed) <= 100),
    -- The member's own dogs: a list of {"name": ..., "breed": ...}, at most 5.
    dogs             jsonb not null default '[]'::jsonb check (
                         case when jsonb_typeof(dogs) = 'array'
                              then jsonb_array_length(dogs) <= 5 else false end),
    -- On by default: sightings appear in everyone's Social feed unless switched off.
    share_sightings  boolean not null default true,
    created_at       timestamptz not null default now()
);

-- Picture names can be breed names, up to 100 characters. (Done as a separate step so it
-- also updates tables created when the limit was 16, for emojis only.)
alter table public.profiles drop constraint if exists profiles_avatar_check;
alter table public.profiles
    add constraint profiles_avatar_check check (char_length(avatar) between 1 and 100);

-- Usernames are unique, ignoring capitals: "Charlie" and "charlie" can't both exist.
create unique index if not exists profiles_username_unique on public.profiles (lower(username));

alter table public.profiles enable row level security;

drop policy if exists "Members can read profiles" on public.profiles;
create policy "Members can read profiles"
    on public.profiles for select
    to authenticated
    using (true);

drop policy if exists "Users can create their own profile" on public.profiles;
create policy "Users can create their own profile"
    on public.profiles for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their own profile" on public.profiles;
create policy "Users can update their own profile"
    on public.profiles for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

-- The Social feed: members can also read the sightings of anyone who shares them.
-- (Together with "read their own" above; nobody can change anyone else's sightings.)
drop policy if exists "Members can read shared sightings" on public.sightings;
create policy "Members can read shared sightings"
    on public.sightings for select
    to authenticated
    using (exists (
        select 1 from public.profiles p
        where p.user_id = sightings.user_id and p.share_sightings
    ));


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


-- Sighting photos (optional). The picture itself lives in the private Storage bucket
-- below; the sighting keeps its path, "<user id>/<photo id>.jpg".
alter table public.sightings add column if not exists photo_path text
    check (char_length(photo_path) <= 200);

-- A private bucket: photos are only reachable through short-lived signed links, never a
-- public URL. The app sends small JPEGs (about 300 KB); the limit is a safety net.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('sighting-photos', 'sighting-photos', false, 5242880, array['image/jpeg'])
on conflict (id) do update
    set public = excluded.public,
        file_size_limit = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;

-- Storage access rules: each member has a folder named after their user id and can only
-- add, see and delete files in it. Who else can see them is set further down, under dog
-- profiles ("Members can see dog and shared sighting photos").
drop policy if exists "Users can add their own sighting photos" on storage.objects;
create policy "Users can add their own sighting photos"
    on storage.objects for insert
    to authenticated
    with check (bucket_id = 'sighting-photos'
                and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "Users can see their own sighting photos" on storage.objects;
create policy "Users can see their own sighting photos"
    on storage.objects for select
    to authenticated
    using (bucket_id = 'sighting-photos'
           and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "Users can delete their own sighting photos" on storage.objects;
create policy "Users can delete their own sighting photos"
    on storage.objects for delete
    to authenticated
    using (bucket_id = 'sighting-photos'
           and (storage.foldername(name))[1] = (select auth.uid())::text);


-- Dog profiles: members' own dogs, each with a unique @username so it can be tagged in
-- posts. Every member can see every dog; only the owner can add, change or delete one.
-- (profiles.dogs above is the older list of names; the app moves those into here.)
create table if not exists public.dogs (
    id          bigint generated always as identity primary key,
    owner_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
    username    text not null check (username ~ '^[A-Za-z0-9_.]{3,30}$'),
    name        text not null check (char_length(name) between 1 and 40),
    breed       text check (char_length(breed) <= 100),
    bio         text check (char_length(bio) <= 300),
    -- "<owner id>/dogs/<photo id>.jpg" in the sighting-photos bucket, or null.
    photo_path  text check (char_length(photo_path) <= 200),
    created_at  timestamptz not null default now()
);

-- Dog usernames are unique, ignoring capitals.
create unique index if not exists dogs_username_unique on public.dogs (lower(username));
create index if not exists dogs_owner_idx on public.dogs (owner_id);

alter table public.dogs enable row level security;

drop policy if exists "Members can read dogs" on public.dogs;
create policy "Members can read dogs"
    on public.dogs for select
    to authenticated
    using (true);

drop policy if exists "Users can add their own dogs" on public.dogs;
create policy "Users can add their own dogs"
    on public.dogs for insert
    to authenticated
    with check ((select auth.uid()) = owner_id);

drop policy if exists "Users can update their own dogs" on public.dogs;
create policy "Users can update their own dogs"
    on public.dogs for update
    to authenticated
    using ((select auth.uid()) = owner_id)
    with check ((select auth.uid()) = owner_id);

drop policy if exists "Users can delete their own dogs" on public.dogs;
create policy "Users can delete their own dogs"
    on public.dogs for delete
    to authenticated
    using ((select auth.uid()) = owner_id);


-- Tags: which dogs appear in which sighting. Anyone can tag any dog in their own
-- sighting; a tag can be removed by whoever posted it or by the dog's owner.
create table if not exists public.sighting_dogs (
    sighting_id  bigint not null references public.sightings (id) on delete cascade,
    dog_id       bigint not null references public.dogs (id) on delete cascade,
    created_at   timestamptz not null default now(),
    primary key (sighting_id, dog_id)
);

create index if not exists sighting_dogs_dog_idx on public.sighting_dogs (dog_id);

alter table public.sighting_dogs enable row level security;

-- You can see a tag when you can see its sighting (yours, or a shared one: the sightings
-- policies above apply inside this check too).
drop policy if exists "Members can read tags on sightings they can see" on public.sighting_dogs;
create policy "Members can read tags on sightings they can see"
    on public.sighting_dogs for select
    to authenticated
    using (exists (select 1 from public.sightings s where s.id = sighting_id));

drop policy if exists "Users can tag dogs in their own sightings" on public.sighting_dogs;
create policy "Users can tag dogs in their own sightings"
    on public.sighting_dogs for insert
    to authenticated
    with check (exists (select 1 from public.sightings s
                        where s.id = sighting_id and s.user_id = (select auth.uid())));

drop policy if exists "Posters and dog owners can remove tags" on public.sighting_dogs;
create policy "Posters and dog owners can remove tags"
    on public.sighting_dogs for delete
    to authenticated
    using (exists (select 1 from public.sightings s
                   where s.id = sighting_id and s.user_id = (select auth.uid()))
           or exists (select 1 from public.dogs d
                      where d.id = dog_id and d.owner_id = (select auth.uid())));


-- Who else can see photos. Dog profile photos: every member. Sighting photos: anyone who
-- can see the sighting, which means members who share have their photos in Social, and
-- switching sharing off makes them private again. (Uploading and deleting stay owner-only,
-- see the policies further up.)
drop policy if exists "Members can see dog and shared sighting photos" on storage.objects;
create policy "Members can see dog and shared sighting photos"
    on storage.objects for select
    to authenticated
    using (bucket_id = 'sighting-photos'
           -- "objects.name" is the file's path; plain "name" would mean the dog's name.
           and (exists (select 1 from public.dogs d where d.photo_path = objects.name)
                or exists (select 1 from public.sightings s
                           where s.photo_path = objects.name)));


-- Breeds members have added. Every breed in data/breeds.csv is verified; a member can
-- also type in a breed that isn't listed when they log a sighting. It's logged as an
-- "Unverified breed", and its name lands here so other members can pick it too and the
-- owner can review the list (Table Editor > user_breeds, or the query in
-- docs/reviewing-breeds.md). To verify one, add it to data/breeds.csv (and the other
-- breed files). To hide one from everyone's breed picker, tick "rejected".
create table if not exists public.user_breeds (
    id          bigint generated always as identity primary key,
    name        text not null check (char_length(name) between 1 and 100),
    added_by    uuid default auth.uid() references auth.users (id) on delete set null,
    rejected    boolean not null default false,
    created_at  timestamptz not null default now()
);

-- One row per breed, ignoring capitals ("Cavapoo" and "cavapoo" are the same breed).
create unique index if not exists user_breeds_name_unique on public.user_breeds (lower(name));

alter table public.user_breeds enable row level security;

drop policy if exists "Members can read added breeds" on public.user_breeds;
create policy "Members can read added breeds"
    on public.user_breeds for select
    to authenticated
    using (not rejected);

drop policy if exists "Members can add breeds" on public.user_breeds;
create policy "Members can add breeds"
    on public.user_breeds for insert
    to authenticated
    with check ((select auth.uid()) = added_by and not rejected);
