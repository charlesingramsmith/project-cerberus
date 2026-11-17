# 🐕 Project Cerberus

**[▶ Try it live](https://project-cerberus.streamlit.app)**

**A life list for dog spotters.** Every time you see a dog, log its breed. The first time you log a breed it becomes a *lifer*. The goal is to collect all 100 of the most popular breeds.

It's inspired by bird-watching life lists, but for the dogs you pass in the park.

## Features

- **Mobile first**: designed to be used one-handed on a phone while you're out walking, with a bottom tab bar, big tap targets and phone-sized stat cards. On a desktop it shows the same layout in a centred column. Follows your device's light or dark mode.
- **Accounts**: one tap with **Continue with Google**, or sign up with email and password. Each spotter's life list is private to them.
- **Log a sighting**: pick the breed (searchable, and breeds you haven't collected yet are marked ✨ new), the date, where you saw it, the dog's name and notes.
- **Lifer celebrations**: a new breed gets balloons 🎉.
- **Life list**: progress towards 100 breeds, the date you first saw each one and how many times, filterable by collected or still to find, and searchable.
- **Sightings history**: every dog you've logged as a card, newest first, each with its own delete button.
- **Demo mode**: with no database configured, the app still runs, keeping data in memory only.

## Architecture

| Layer | Choice |
|---|---|
| UI | [Streamlit](https://streamlit.io), with a theme in `.streamlit/config.toml` and a small mobile stylesheet in `app.py` |
| Auth | [Supabase Auth](https://supabase.com/docs/guides/auth): Google sign-in (OAuth with PKCE) plus email and password |
| Database | Supabase Postgres, with **row-level security** so users can only read or write their own rows |
| Data | Pandas |
| Tests | pytest, Streamlit `AppTest` for end-to-end flows, and a fake Supabase client |

```
project-cerberus/
├── app.py                  # Streamlit UI: sign-in screens and the life list
├── cerberus/
│   ├── logic.py            # Pure life-list and lifer logic (no I/O)
│   ├── backends.py         # SupabaseBackend (real) and MemoryBackend (tests/demo)
│   └── oauth.py            # Remembers a Google sign-in while the user is at Google
├── .streamlit/config.toml  # Theme (colours, light/dark) and toolbar settings
├── docs/                   # Setup guides (e.g. Google sign-in)
├── data/breeds.csv         # Top 100 breeds, AKC 2025 popularity ranking
├── supabase/schema.sql     # Table plus row-level security policies
└── tests/
```

**Security notes**
- The app only ever uses Supabase's *publishable* (anon) key. Postgres row-level security policies in [`supabase/schema.sql`](supabase/schema.sql) enforce that each user can only touch their own sightings, even if someone calls the API directly.
- Each browser session gets its own Supabase client, so one visitor's sign-in is never shared with another's.
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
- [ ] 🧭 "Help me identify": answer a few questions (size, coat, ears) to narrow down the breed
- [ ] 📷 Photo upload with a sighting (Supabase Storage)
- [ ] 🤖 Photo ID: breed suggestions from a photo (an image classification model)
- [ ] 🔊 Sound ID: detect a bark from a recording (experimental)
- [ ] More breeds, a sightings map, password reset and "stay signed in", installable home-screen app

Inspired by bird ID apps like Merlin, which identify birds by description, photo or sound. The full plan, with notes on each item, is in [ROADMAP.md](ROADMAP.md).

## Data source

Breed popularity ranking: [American Kennel Club, Most Popular Dog Breeds of 2025](https://www.akc.org/expert-advice/news/most-popular-dog-breeds-2025/).
