# Roadmap

Where Project Cerberus is heading, and why. This is the single source of truth for planned work: `README.md` shows a short summary and `CLAUDE.md` points here.

**How to use this file**
- Tick an item (`[x]`) in the same commit that finishes it, and update the README summary.
- New ideas go under **Ideas** first; move them up when they're ready to be worked on.
- Each bigger item has a short note on the approach so anyone (or any agent) picking it up knows where to start. Keep notes brief: decisions, not history.

## Inspiration: three ways to identify a dog

Bird apps like Merlin let you identify a bird three ways: by answering questions about what you saw, from a photo, or from its song. Cerberus aims for the dog equivalent, so a sighting can be logged even when you don't know the breed.

| Mode | What the user does | Status |
|---|---|---|
| **Manual ID** | Picks the breed from a list (today), or answers a few questions (size, coat, colour, ears) to narrow it down | Breed list done; guided questions planned |
| **Photo ID** | Takes or uploads a photo; the app suggests likely breeds | Planned |
| **Sound ID** | Records a bark; the app detects it's a dog and maybe suggests size/type | Experimental idea |

## Done

- [x] Manual sighting log and life list for the top 100 breeds
- [x] Accounts and a hosted database (Supabase, with row-level security)
- [x] Continue with Google (setup steps in [docs/google-sign-in.md](docs/google-sign-in.md))
- [x] Bottom tab bar: Dog ID, Life list, Profile, Social (placeholder), Settings

## Now

_Nothing in progress. Pick the next item from below._

## Next

- [ ] **Guided manual ID** ("Help me identify"): a short question flow (size, coat length, colour, ear shape, tail) that filters the breed list down to a few candidates.
  - Needs breed traits: add columns to `data/breeds.csv` (or a new `data/breed_traits.csv`). The filtering is pure logic, so it lives in `cerberus/logic.py` with tests.
- [ ] **Photo upload** with a sighting (optional: a sighting can still be logged without one).
  - Supabase Storage bucket with RLS so users only see their own photos. Schema change goes in `supabase/schema.sql`.
  - Phone camera via `st.camera_input` / `st.file_uploader`.
- [ ] **Photo ID**: suggest the top 3 breeds from a photo; the user confirms or picks another.
  - Builds on photo upload. Options to compare: a hosted image-classification API vs. a small pretrained model (e.g. trained on the Stanford Dogs dataset). Watch Streamlit Cloud's memory limits if running a model in-app.
  - Always let the user confirm: the model suggests, the human decides what goes on the life list.
- [ ] Password reset and "stay signed in"

## Later

- [ ] More breeds beyond the top 100 (add rows to `data/breeds.csv`)
- [ ] **Location on a sighting** (optional): where the dog was seen.
  - Simplest start: a free-text place name (e.g. "Hyde Park"). Then add "Use my current location" on phones; Streamlit has no built-in GPS, so this needs a small component that asks the browser for location (with the user's permission). Could also pick a spot on a map.
  - New nullable column(s) on sightings in `supabase/schema.sql` (place name, and optionally latitude/longitude).
  - Private by default: exact spots never appear in the Social feed (see Social below).
- [ ] Map of where you've spotted dogs (builds on location on a sighting)
- [ ] **Social**: an activity feed of other members' sightings (new lifers, recent sightings, their photos), plus following friends, comparing life lists and leaderboards. Fills the Social tab, which is a placeholder today.
  - Today RLS only lets users read their own rows, so sharing must be deliberate: a `profiles` table with a display name (never show emails) and a per-user "share my sightings" setting, off by default. New RLS policies in `supabase/schema.sql` allow reading shared sightings and photos only; nobody can edit anyone else's.
  - Add a follows table so the feed can show everyone who shares or only people you follow.
  - Keep locations coarse or hidden in the feed so it can't reveal where someone walks their dog every day.
  - Later: likes/comments, and reporting or hiding posts.
- [ ] **App updates ("What's new")**: shows recent changes and what's coming next on the roadmap.
  - Read it from the repo so it never goes stale: dated entries from a new `CHANGELOG.md` for "What's new", and the **Now** and **Next** sections of this file for "Coming next". Parsing the Markdown is pure logic in `cerberus/logic.py`, with tests.
  - Lives in the **Settings** tab as a "What's new" section (no 6th tab: the bottom bar is already full on a 375px phone). Optional: a "new" dot on Settings when there's an update the user hasn't seen.
  - Write user-friendly lines ("You can now add a photo"), not developer notes.
- [ ] Installable "Add to Home Screen" app (needs hosting where we control the web app manifest)

## Ideas (not yet committed to)

- **Sound ID (bark ID)**: record a short clip and detect a dog bark. Telling *breeds* apart by bark isn't reliable with current public data, so a realistic first version is "dog detected" plus a rough size guess, used as a hint alongside manual or photo ID. Would use a pretrained audio classifier (e.g. YAMNet, which recognises "dog bark") and `st.audio_input`.
- Mixed-breed / "unknown" sightings that can be identified later.
- Sighting streaks, badges or regional life lists.
