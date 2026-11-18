# 🐕 Project Cerberus

**[▶ Try it live](https://project-cerberus.streamlit.app)**

**A life list for dog spotters.** Every time you see a dog, log its breed. The first time you log a breed it becomes a *lifer*. The goal is to collect all 100 of the most popular breeds.

It's inspired by bird-watching life lists, but for the dogs you pass in the park.

## Features

- **Mobile first**: designed to be used one-handed on a phone while you're out walking, with a bottom tab bar (Dog ID, Life list, Profile, Social, Settings), big tap targets and phone-sized stat cards. On a desktop it shows the same layout in a centred column. Follows your device's light or dark mode.
- **Accounts**: one tap with **Continue with Google**, or sign up with email and password. **Keep me signed in** remembers you for 30 days. Your email is never shown to other members.
- **Dog ID**: log a sighting by picking the breed (searchable, and breeds you haven't collected yet are marked ✨ new), the date, where you saw it, the dog's name and notes.
- **Lifer celebrations**: a new breed gets balloons 🎉.
- **Life list**: progress towards 100 breeds, the date you first saw each one and how many times, filterable by collected or still to find, and searchable. Tap any breed to open its profile: a photo, a short intro, where it's from, its temperament and a fun fact.
- **Your profile**: a unique username, a dog emoji as your picture, your favourite breed and your own dogs, plus a summary of your spotting and every dog you've logged as a card, newest first, each with its own delete button.
- **Social**: the latest sightings from everyone in the community, with each spotter's name and picture. Sharing is on by default: new members are told so in a popup when they join, and can switch it off there or any time in Settings > Privacy.
- **Settings**: your account details and sign out, plus **What's new**: the app's version number and recent updates (from [`CHANGELOG.md`](CHANGELOG.md)), the features coming next (straight from [`ROADMAP.md`](ROADMAP.md)) with a **+1** button on each so you can vote for what you want most, and a box to suggest new features. An orange dot on the Settings tab tells you when there's an update you haven't seen.
- **Demo mode**: with no database configured, the app still runs, keeping data in memory only.

## Architecture

| Layer | Choice |
|---|---|
| UI | [Streamlit](https://streamlit.io), with a theme in `.streamlit/config.toml` and a small mobile stylesheet in `app.py` |
| Auth | [Supabase Auth](https://supabase.com/docs/guides/auth): Google sign-in (OAuth with PKCE) plus email and password |
| Database | Supabase Postgres, with **row-level security** so users can only write their own rows, and only read others' shared sightings |
| Data | Pandas |
| Tests | pytest, Streamlit `AppTest` for end-to-end flows, and a fake Supabase client |

```
project-cerberus/
├── app.py                  # Streamlit UI: sign-in screens and the life list
├── cerberus/
│   ├── logic.py            # Pure life-list, lifer and What's new logic
│   ├── backends.py         # SupabaseBackend (real) and MemoryBackend (tests/demo)
│   ├── oauth.py            # Remembers a Google sign-in while the user is at Google
│   └── remember.py         # "Keep me signed in" (browser storage)
├── .streamlit/config.toml  # Theme (colours, light/dark) and toolbar settings
├── docs/                   # Setup guides (e.g. Google sign-in)
├── data/breeds.csv         # Top 100 breeds, AKC 2025 popularity ranking
├── data/breed_info.csv     # Each breed's intro, origin, temperament and fun fact
├── data/breed_photos.csv   # A credited, free-licensed photo per breed
├── scripts/                # One-off helpers (e.g. fetching the breed photos)
├── supabase/schema.sql     # Tables plus row-level security policies
├── CHANGELOG.md            # Version history, shown in Settings > What's new
├── ROADMAP.md              # The plan; its Now and Next items appear in the app
└── tests/
```

**Security notes**
- The app only ever uses Supabase's *publishable* (anon) key. Postgres row-level security policies in [`supabase/schema.sql`](supabase/schema.sql) enforce that each user can only change their own sightings, profile, votes and suggestions, even if someone calls the API directly. Members can read profiles and the sightings of people who share them (for the Social tab), but never emails or anyone's private sightings. Vote totals come from a database function that returns only counts, never who voted.
- Each browser session gets its own Supabase client, so one visitor's sign-in is never shared with another's.
- "Keep me signed in" stores a single-use Supabase refresh token in the browser's local storage for 30 days, via a tiny invisible component. Each visit swaps it for a new one, and signing out cancels it. It's never sent with web requests, but scripts on the page can read it, so the box can be unticked on shared computers. (Safari clears script-written storage after 7 days without a visit.)
- Passwords are handled entirely by Supabase Auth and never stored by the app. Google sign-in uses PKCE, so the one-time code Google returns is useless without a secret that never leaves the server.

## Run it locally

You need Python 3.12 or newer.

```bash
git clone https://github.com/charlesingramsmith/project-cerberus.git
cd project-cerberus
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

Without Supabase keys the app starts in **demo mode**. To connect a real database:

1. Create a free project at [supabase.com](https://supabase.com).
2. In **SQL Editor**, run [`supabase/schema.sql`](supabase/schema.sql).
3. In **Authentication > URL Configuration**, set **Site URL** to where the app runs (e.g. `http://localhost:8501`). Email confirmation links go there.
4. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`, then fill in your project URL and **publishable** key (Project Settings > API Keys).
5. Optional: turn on **Continue with Google** by following [docs/google-sign-in.md](docs/google-sign-in.md).

Run the tests with `pytest`.

## Deploy (Streamlit Community Cloud)

1. At [share.streamlit.io](https://share.streamlit.io), sign in with GitHub and create an app from this repo, with `app.py` as the main file.
2. Under **Advanced settings > Secrets**, paste the contents of your `secrets.toml`.
3. Back in Supabase, set **Site URL** to the deployed app's URL.

## Roadmap

- [x] Manual sighting log and life list for the top 100 breeds
- [x] Accounts and a hosted database (Supabase)
- [x] Continue with Google
- [x] Keep me signed in for 30 days
- [x] 🆕 "What's new" in Settings: version history, what's coming next, +1 votes and feature suggestions
- [x] 👤 Profiles (username, emoji picture, favourite breed, your dogs) and a 👥 Social feed of everyone's shared sightings
- [x] 🐶 Breed profiles: tap a breed for a photo, intro, origin, temperament and a fun fact
- [ ] 🧭 "Help me identify": answer a few questions (size, coat, ears) to narrow down the breed
- [ ] 📷 Optional photo with a sighting (Supabase Storage)
- [ ] 📍 Optional location for a sighting (place name or current location)
- [ ] 🤖 Photo ID: breed suggestions from a photo (an image classification model)
- [ ] 🔊 Sound ID: detect a bark from a recording (experimental)
- [ ] 👥 More social: following friends, comparing life lists, leaderboards
- [ ] More breeds, a sightings map, password reset
- [ ] 📱 Launch a real app: home-screen install first, then the app stores

Inspired by bird ID apps like Merlin, which identify birds by description, photo or sound. The full plan, with notes on each item, is in [ROADMAP.md](ROADMAP.md).

## Data source

Breed popularity ranking: [American Kennel Club, Most Popular Dog Breeds of 2025](https://www.akc.org/expert-advice/news/most-popular-dog-breeds-2025/).

Breed photos: [Wikimedia Commons](https://commons.wikimedia.org/), each under a free licence (Creative Commons or public domain). The app credits the photographer and licence under every photo and links to the original. `scripts/fetch_breed_photos.py` picks each breed's main Wikipedia photo and saves the details to `data/breed_photos.csv`.

Breed intros, temperaments and fun facts are written for this project (`data/breed_info.csv`).
