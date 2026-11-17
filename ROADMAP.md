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

## Now

- [ ] Sign in with Google: built and tested on the `google-sign-in` branch. Before merging, do the one-time Google Cloud + Supabase setup in [docs/google-sign-in.md](docs/google-sign-in.md) and try it locally (otherwise the live button shows an error).

## Next

- [ ] **Guided manual ID** ("Help me identify"): a short question flow (size, coat length, colour, ear shape, tail) that filters the breed list down to a few candidates.
  - Needs breed traits: add columns to `data/breeds.csv` (or a new `data/breed_traits.csv`). The filtering is pure logic, so it lives in `cerberus/logic.py` with tests.
- [ ] **Photo upload** with a sighting.
  - Supabase Storage bucket with RLS so users only see their own photos. Schema change goes in `supabase/schema.sql`.
  - Phone camera via `st.camera_input` / `st.file_uploader`.
- [ ] **Photo ID**: suggest the top 3 breeds from a photo; the user confirms or picks another.
  - Builds on photo upload. Options to compare: a hosted image-classification API vs. a small pretrained model (e.g. trained on the Stanford Dogs dataset). Watch Streamlit Cloud's memory limits if running a model in-app.
  - Always let the user confirm: the model suggests, the human decides what goes on the life list.
- [ ] Password reset and "stay signed in"

## Later

- [ ] More breeds beyond the top 100 (add rows to `data/breeds.csv`)
- [ ] Map of where you've spotted dogs (needs a location on each sighting)
- [ ] Installable "Add to Home Screen" app (needs hosting where we control the web app manifest)

## Ideas (not yet committed to)

- **Sound ID (bark ID)**: record a short clip and detect a dog bark. Telling *breeds* apart by bark isn't reliable with current public data, so a realistic first version is "dog detected" plus a rough size guess, used as a hint alongside manual or photo ID. Would use a pretrained audio classifier (e.g. YAMNet, which recognises "dog bark") and `st.audio_input`.
- Mixed-breed / "unknown" sightings that can be identified later.
- Sighting streaks, badges or regional life lists.
