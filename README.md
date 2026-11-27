# 🐕 Project Cerberus

**[▶ Try it live](https://project-cerberus.streamlit.app)**

**A life list for dog spotters.** Every time you see a dog, log its breed. The first time you log a breed it becomes a *lifer*. The goal is to collect all 141 breeds: the 100 most popular, plus 41 more that Photo ID can recognise.

It's inspired by bird-watching life lists, but for the dogs you pass in the park.

## Features

- **Mobile first**: designed to be used one-handed on a phone while you're out walking, with a bottom tab bar (Spotted!, Social, Life list, Profile, Settings), big tap targets and phone-sized stat cards. On a desktop it shows the same layout in a centred column. Light mode by default, with a **Dark mode** switch in Settings.
- **Its own look**: a pencil-sketch dachshund logo, hand-drawn icons instead of emoji (tabs, badges and more), pastel pistachio green with plum highlights, handwritten headings (Caveat) and a soft rounded body font (Nunito), in light and dark.
- **Accounts**: one tap with **Continue with Google**, or sign up with email and password. **Keep me signed in** remembers you for 30 days. Your email is never shown to other members.
- **Spotted!**: log a sighting in two short steps. **Step 1, the breed**: add an optional photo (one **Add photo** button that takes a picture or picks one from your library, with a preview you can change or remove) and **Photo ID**, a small image model, suggests up to 3 breeds ("Very likely", "Possible" or "Long shot"), each shown with a photo of that breed so you can compare it with yours; tap one, or pick the breed from the searchable list (breeds you haven't collected yet are marked new), then **Continue** (Photo ID says when it isn't sure; the first version knows 114 of the 141 breeds). **Step 2, the details**: your photo and the breed (and whether it's new for your life list), then tag any dog that has a profile by its @username (its name fills in as soon as you tag it), where and when you saw it (the date the photo was taken fills in, with a suggested place name like "Hyde Park, London" from where it was taken, looked up on OpenStreetMap; change either if it's wrong, and some phones and browsers remove these details, so then nothing is filled in), and your post. You can go back to step 1 without losing anything. Can't find the breed? Type it in: it's logged as an **unverified breed** and added to a list of breeds we review for adding to the app (other members can pick it too). Unverified breeds get their own section on the life list and don't count as lifers until they're verified. Spotted a cross? Switch on **It's a cross breed** in step 1 and pick both breeds: it's logged as **Breed A x Breed B**, shown that way in Social, and listed under **Crosses** on your life list (each new cross is a lifer, but only breeds count for badges). Photos are saved smaller and without the GPS location phones store in them, and show in Social when you share your sightings.
- **Lifer celebrations**: a new breed's face floats slowly up the screen in circles, like balloons (both parents' faces for a new cross).
- **Badges**, in three kinds, each with its own hand-drawn icon: **Lifer badges** for your first lifer, then every 5 up to 100 and every 10 after that (Puppy steps, Quarter century, Halfway hound, Top dog … Leader of the pack), counting breeds and crosses; five rarer **Purebred badges** with a plum ring for 10, 25, 50, 100 and all 141 verified breeds; and fun **Cross badges** (Matchmaker, Doodle collector, Family reunion). Your profile shows one kind at a time, with the next badge to earn and a progress bar up front, then all its badges (earned ones in colour), and the life list tells you how many lifers until the next one. When members who share their sightings earn a badge, it shows on that sighting in the Social feed.
- **Life list**: progress towards all 141 breeds, the date you first saw each one and how many times, with a small photo of each breed zoomed in on its face (in colour once you've spotted it), filterable by collected or still to find, and searchable. Tap any breed to open its profile: a photo, a short intro, where it's from, its temperament and a fun fact.
- **Your profile**: a unique username, any breed's photo as your profile picture, your favourite breed, and **dog profiles** for your own dogs (a unique @username, name, breed or cross of two breeds, bio and photo) so they can be tagged in posts, plus a summary of your spotting and every dog you've logged as a card, newest first, with its photo if it has one and its own delete button.
- **Social**: the latest sightings from everyone in the community, newest post first (with the date seen too when it's a different day), with each spotter's name and picture, their photo and the dogs tagged in them. Tap a tagged **@dog** (or look one up with **Find a dog**) to open its page: its profile, every shared sighting it's tagged in and a gallery of their photos. Sharing is on by default: new members are told so in a popup when they join, and can switch it off there or any time in Settings > Privacy.
- **Settings**: your account details and sign out, plus **What's new**: the app's version number and recent updates (from [`CHANGELOG.md`](CHANGELOG.md)), the features coming next (straight from [`ROADMAP.md`](ROADMAP.md)) with a **+1** button on each so you can vote for what you want most, and a box to suggest new features, and the **Privacy policy** and **Terms of use** (also linked from the sign-in screen). A plum dot on the Settings tab tells you when there's an update you haven't seen.
- **Demo mode**: with no database configured, the app still runs, keeping data in memory only.

## Architecture

| Layer | Choice |
|---|---|
| UI | [Streamlit](https://streamlit.io), with a theme in `.streamlit/config.toml` and a small mobile stylesheet in `app.py` |
| Auth | [Supabase Auth](https://supabase.com/docs/guides/auth): Google sign-in (OAuth with PKCE) plus email and password |
| Database | Supabase Postgres, with **row-level security** so users can only write their own rows, and only read others' shared sightings |
| Photos | Supabase Storage: a private bucket, with each member's sighting and dog photos in their own folder |
| Photo ID | A small pretrained image model (MobileNetV3, ImageNet) in ONNX format, run in the app with [ONNX Runtime](https://onnxruntime.ai), so photos never leave the server |
| Data | Pandas |
| Tests | pytest, Streamlit `AppTest` for end-to-end flows, and a fake Supabase client |

```
project-cerberus/
├── app.py                  # Streamlit UI: sign-in screens and the life list
├── cerberus/
│   ├── logic.py            # Pure life-list, lifer, badge and What's new logic
│   ├── backends.py         # SupabaseBackend (real) and MemoryBackend (tests/demo)
│   ├── oauth.py            # Remembers a Google sign-in while the user is at Google
│   ├── photo_id.py         # Photo ID: runs the breed model on a photo
│   └── remember.py         # "Keep me signed in" (browser storage)
├── .streamlit/config.toml  # Theme (colours, fonts, light/dark) and toolbar settings
├── assets/                 # The logo (logo.svg) and app icon (icon.png)
├── legal/                  # Privacy policy and terms of use (shown in the app)
├── docs/                   # Setup guides (Google sign-in, Supabase CLI, reviewing added breeds)
├── data/breeds.csv         # AKC 2025 top 100 (with rank), plus 41 more Photo ID knows
├── data/breed_info.csv     # Each breed's intro, origin, temperament and fun fact
├── data/breed_photos.csv   # A credited, free-licensed photo per breed
├── data/breed_faces.csv    # Where each photo's face is, for small pictures
├── data/photo_id_breeds.csv # Which of the model's dog classes are which of our breeds
├── models/dog_breeds.onnx  # The Photo ID model (22 MB)
├── scripts/                # One-off helpers (breed photos, face crops, exporting the Photo ID model)
├── supabase/schema.sql     # Tables plus row-level security policies
├── CHANGELOG.md            # Version history, shown in Settings > What's new
├── site/                 # The Derlin landing page (derlin.app), built by scripts/build_site.py
├── ROADMAP.md              # The plan; its Now and Next items appear in the app
└── tests/
```

**Security notes**
- The app only ever uses Supabase's *publishable* (anon) key. Postgres row-level security policies in [`supabase/schema.sql`](supabase/schema.sql) enforce that each user can only change their own sightings, profile, votes and suggestions, even if someone calls the API directly. Members can read profiles and the sightings of people who share them (for the Social tab), but never emails or anyone's private sightings. Vote totals come from a database function that returns only counts, never who voted. Photos live in a private Supabase Storage bucket where each member has a folder only they can add to or delete from. Other members can see dog profile photos, and sighting photos only while that sighting is shared; the app shows them through links that expire after an hour. Breeds members add are readable by all members; only the owner (in the dashboard) can mark one rejected. Dog profiles are readable by all members but only their owner can change them; anyone can tag a dog in their own post, and the post's author or the dog's owner can remove a tag.
- Each browser session gets its own Supabase client, so one visitor's sign-in is never shared with another's.
- "Keep me signed in" stores a single-use Supabase refresh token in the browser's local storage for 30 days, via a tiny invisible component. Each visit swaps it for a new one (only while you're using the app, never in the background, so the saved one stays valid), and signing out cancels it. It's never sent with web requests, but scripts on the page can read it, so the box can be unticked on shared computers. (Safari clears script-written storage after 7 days without a visit.)
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
2. In **SQL Editor**, run [`supabase/schema.sql`](supabase/schema.sql) (or apply it with the Supabase CLI: see [docs/supabase-cli.md](docs/supabase-cli.md)).
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
- [x] ➕ 41 more verified breeds, so every breed Photo ID knows can be logged (141 in all)
- [x] Accounts and a hosted database (Supabase)
- [x] Continue with Google
- [x] Keep me signed in for 30 days
- [x] 🆕 "What's new" in Settings: version history, what's coming next, +1 votes and feature suggestions
- [x] 👤 Profiles (username, emoji picture, favourite breed, your dogs) and a 👥 Social feed of everyone's shared sightings
- [x] 🐶 Breed profiles: tap a breed for a photo, intro, origin, temperament and a fun fact
- [x] 🖼️ Breed photos on the life list, and a breed photo as your profile picture
- [x] 🏅 Badges for milestones (first lifer, every 5 breeds to 100, then every 10, up to all 141), on your profile and in Social
- [x] 📸 Your own photo on a sighting (stored in Supabase Storage, shown in Social when shared)
- [x] 📷 Photo ID (first version): add a photo and a small model running in the app suggests the breed (you confirm, or just pick it yourself)
- [x] 🐕 Dog profiles: your dogs get their own @username and profile, and can be tagged in posts; tap a tag to see the dog's page and photos
- [x] ➕ Add your own breeds: typed-in breeds are logged as unverified and reviewed for the app
- [x] Cross breeds: log a dog as Breed A x Breed B, with their own lifers and badges
- [x] 🎨 A new look: pencil-sketch dachshund logo, pistachio and plum colours, new fonts
- [ ] 🔎 Dog identification: a wider project to identify dogs from photos, starting with Photo ID (done)
- [ ] 🧠 Smarter Photo ID: our own model trained on all our breeds plus popular crosses like the Cockapoo
- [ ] 🧠 Opt-in: share your confirmed photos to help train the model
- [ ] 🔊 Sound ID: get a hint from a recorded bark (experimental)
- [x] 📍 Date and place filled in from your photo
- [ ] 📍 Use your current location for a sighting, and a map
- [ ] 👥 More social: comparing life lists, leaderboards
- [ ] 🤝 Friends and private messaging (with blocking and reporting)
- [ ] More breeds, a sightings map
- [x] 🏷️ A brand name (Derlin) and our own web address, derlin.app, with a landing page (`site/`)
- [ ] 📱 Launch a real app: a landing page on our domain, then the app on our own hosting, then the app stores

Inspired by bird ID apps like Merlin, which identify birds from a photo or their song. The full plan, with notes on each item, is in [ROADMAP.md](ROADMAP.md).

## Data source

Breed popularity ranking: [American Kennel Club, Most Popular Dog Breeds of 2025](https://www.akc.org/expert-advice/news/most-popular-dog-breeds-2025/).

Breed photos: [Wikimedia Commons](https://commons.wikimedia.org/), each under a free licence (Creative Commons or public domain). The app credits the photographer and licence under every photo and links to the original. `scripts/fetch_breed_photos.py` picks each breed's main Wikipedia photo and saves the details to `data/breed_photos.csv`. `scripts/face_cropper.py` is a small local tool for framing each photo on the dog's face, saved to `data/breed_faces.csv`.

Breed intros, temperaments and fun facts are written for this project (`data/breed_info.csv`).
