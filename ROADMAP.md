# Roadmap

Where Project Cerberus is heading, and why. This is the single source of truth for planned work: `README.md` shows a short summary and `CLAUDE.md` points here.

**How to use this file**
- Tick an item (`[x]`) in the same commit that finishes it, and update the README summary.
- New ideas go under **Ideas** first; move them up when they're ready to be worked on.
- Each bigger item has a short note on the approach so anyone (or any agent) picking it up knows where to start. Keep notes brief: decisions, not history.
- Users see the top-level lines under **Now** and **Next** in the app (Settings > What's new) and can +1 them, so write those lines for users. The indented notes stay developer-only. Votes are tied to the **bold** title (or the whole line if there's no bold part), so renaming an item resets its votes.

## Inspiration: identify a dog from a photo or a bark

Bird apps like Merlin identify a bird from a photo or its song. Cerberus aims for the dog equivalent: snap a photo or record a bark and a machine-learning (ML) model suggests the breed. **The model only suggests:** the user always confirms, and can skip it entirely and just pick the breed they saw from the list.

| Mode | What the user does | Status |
|---|---|---|
| **Pick from the list** | Chooses the breed themselves | Done (always available, as the fallback) |
| **Photo ID** | Takes or uploads a photo; the app suggests likely breeds | Next |
| **Sound ID** | Records a bark; the app suggests what it can | Later (experimental) |

A guided question flow ("help me identify": size, coat, ears) was considered and dropped in favour of ML.

## Done

- [x] Manual sighting log and life list for the top 100 breeds
- [x] Accounts and a hosted database (Supabase, with row-level security)
- [x] Continue with Google (setup steps in [docs/google-sign-in.md](docs/google-sign-in.md))
- [x] Bottom tab bar: Post (was Dog ID), Life list, Profile, Social (placeholder), Settings
- [x] "Keep me signed in" for 30 days (refresh token in browser storage, renewed on each visit)
- [x] **What's new** in Settings: version number and history from `CHANGELOG.md`, "Coming next" from this file's Now and Next sections, a +1 vote on each upcoming feature, and a box to suggest features.
- [x] A "new update" dot on the Settings tab, cleared by opening Settings (the version seen is saved to the user's account)
- [x] **Profiles**: unique username, a dog emoji picture, favourite breed and your own dogs (up to 5), in a `profiles` table created on first sign-in.
- [x] **Breed profiles**: tap a breed on the life list to see a photo, a short intro, where it's from, its temperament and a fun fact. Text in `data/breed_info.csv`; credited Wikimedia Commons photos in `data/breed_photos.csv` (made by `scripts/fetch_breed_photos.py`).
- [x] **Breed photos as pictures**: small breed photos on every life-list row (greyed out until spotted), and any breed's photo as your profile picture (shown on your profile and in Social). Each picture is zoomed in on the dog's face, framed by hand with `scripts/face_cropper.py` (saved in `data/breed_faces.csv`; `logic.face_photo` picks a sharp enough copy).
- [x] **Photos on sightings**: an optional photo (phone camera or upload) on each sighting, shown on its card in Profile. `logic.prepare_photo` shrinks it to a 1600px JPEG, turns it the right way up and drops its metadata (GPS); it goes to the private `sighting-photos` Storage bucket at `<user id>/<photo id>.jpg`, with RLS so only the owner can add, read or delete it, and `sightings.photo_path` points at it. Shown via signed links (1 hour).
- [x] **Social feed**: the latest 50 sightings from everyone who shares, with their name and picture. Sharing is on by default (a popup says so on a member's first visit), with an off switch in Settings > Privacy; the "where" field is shown as typed (the log form says so).
- [x] **Dog profiles**: give your dogs a profile (a unique @username, name, breed, bio and photo) and tag any dog in a sighting. Tags and sighting photos show in Social; "Find a dog" shows a dog's profile and its latest posts.
  - `dogs` table (owner-only changes, all members read) and `sighting_dogs` tags (you tag in your own sightings; the poster or the dog's owner can remove a tag) in `supabase/schema.sql`. Dog photos go in the owner's folder of the `sighting-photos` bucket at `<user id>/dogs/<id>.jpg`; one Storage policy lets members see dog photos and photos on sightings they can see.
  - The older `profiles.dogs` list (names only) is moved into dog profiles automatically on the member's next visit (`move_listed_dogs_to_profiles` in `app.py`); the column stays for now.
  - Tagging a dog with a known breed and leaving Breed empty logs that breed (`logic.tagged_breed`), a first step towards posting as a way to identify dogs.
  - Still to do: removing a tag of your dog from someone else's post (the database allows it, there's no button yet), a dog's page reachable by tapping its tag, and a feed of more than the latest 50 posts for a dog.
- [x] **Dogs that aren't on the list**: post a dog as "Not sure: help me identify it", a mixed breed, or a breed the app doesn't list (typed in). Not-sure dogs show "🔍 Not identified yet" and get an **Identify** button in Profile (`set_sighting_breed`); identifying one can make it a lifer. Mixed and unlisted breeds show under **Other dogs** on the life list. Only listed breeds count for lifers and badges. No schema change: the breed column just holds `logic.UNIDENTIFIED` ("Unidentified"), `logic.MIXED` ("Mixed breed") or the typed name. Unlisted names typed in show which breeds to add next (`data/breeds.csv`).
- [x] **Badges**: milestone badges for your first lifer and 10/25/50/100 breeds, shown on your profile (earned date, or how many to go), a "next badge" hint on the life list, and a message when you earn one. Pure functions in `cerberus/logic.py` (`BADGES`, `badge_progress`), worked out from sightings each run, so no table. Show them to others once member profiles are viewable (More social).

## Now

_Nothing in progress. Pick the next item from below._

## Next

- [ ] **Photo ID**: snap or upload a photo of the dog and get the top 3 likely breeds. Tap one to log it, or skip and pick the breed yourself.
  - Photo is optional: a sighting can always be logged without one, and the breed picker stays on the Post tab.
  - Photo capture and storage are done (see **Photos on sightings** above). Next is the model; it can run on the photo before the sighting is logged, then the same photo is saved with it.
  - Model options to compare: a hosted image-classification API vs. a small pretrained model fine-tuned on dog breeds (e.g. the Stanford Dogs dataset). Watch Streamlit Cloud's memory limits if running a model in-app.
  - Always let the user confirm: the model suggests, the human decides what goes on the life list.

## Later

- [ ] **Help train the model with your photos** (opt-in): let members share their confirmed sighting photos to improve Photo ID.
  - Builds on Photo ID. A confirmed sighting (photo + the breed the user chose) is a labelled training example.
  - Must be opt-in and separate from the Social sharing switch, with clear wording about how photos are used. Members can withdraw. Check consent and licence wording before collecting anything.
  - Needs a review step: user-chosen breeds can be wrong, so keep only confident or double-checked labels. Retraining happens offline, not in the app.
- [ ] **Sound ID**: record a short bark and get a hint about the dog.
  - Telling *breeds* apart by bark isn't reliable with current public data, so a realistic first version is "dog detected" plus a rough size guess, used alongside Photo ID or the breed picker. A pretrained audio classifier (e.g. YAMNet, which recognises "dog bark") with `st.audio_input`.
- [ ] **Streak badges**: badges for spotting dogs several days or weeks in a row.
  - Add to `logic.BADGES`/`badge_progress` (badges are worked out from sightings, no table). Decide what counts as a streak (days with any sighting?) and whether a streak badge stays once the streak ends.
- [ ] **Visual redesign**: a proper look for Cerberus (logo, colours, fonts, illustration style).
  - Starts with a brainstorming session on branding: mood boards, a few colour palettes for light and dark mode, logo ideas. Then update `.streamlit/config.toml`, `MOBILE_CSS` and the bottom tab bar together, and check at 375px in light and dark.
- [ ] More breeds beyond the top 100 (add rows to `data/breeds.csv`)
- [ ] **Location on a sighting** (optional): where the dog was seen.
  - Simplest start: a free-text place name (e.g. "Hyde Park"). Then add "Use my current location" on phones; Streamlit has no built-in GPS, so this needs a small component that asks the browser for location (with the user's permission). Could also pick a spot on a map.
  - New nullable column(s) on sightings in `supabase/schema.sql` (place name, and optionally latitude/longitude).
  - The free-text "where" already exists and is shown in the Social feed as typed. Exact GPS spots should stay private (never shown in Social).
- [ ] Map of where you've spotted dogs (builds on location on a sighting)
- [ ] **More social**: follow friends, compare life lists, leaderboards, "new lifer" highlights and photos in the feed, and tapping a name to see that member's profile.
  - Builds on `profiles` and the "Members can read shared sightings" RLS policy. A follows table lets the feed show everyone or only people you follow.
  - Later: likes/comments, and reporting or hiding posts.
- [ ] **Launch a real app**: Cerberus on your phone's home screen, and later in the app stores.
  - First step: an installable "Add to Home Screen" web app. Needs hosting where we control the web app manifest and icons, so it means moving off Streamlit Community Cloud.
  - Then: a store app (iOS and Android). Options to compare: wrapping the web app (e.g. Capacitor) vs. rebuilding the UI natively; Supabase and the RLS rules can stay as they are.
  - **Fix the tab bar height when we move.** Today `MOBILE_CSS` in `app.py` lifts the bottom tab bar by 3rem on screens up to 840px wide so Streamlit Community Cloud's "Hosted with Streamlit" badge doesn't cover the last tabs. Off Community Cloud that badge is gone, so remove the lift (the `@media (max-width: 840px)` block) and the bar sits flush with the bottom again, keeping `env(safe-area-inset-bottom)` for phones with a home bar. Check it at 375px in light and dark.

## Ideas (not yet committed to)

- Password reset by email. Built and removed in Nov 2026 (v0.11.0 to v0.13.1): Supabase only lets you edit the reset email template once custom SMTP is set up, and the owner chose not to set one up yet. The working version is in git (commit e30b98e): the email template links to `{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery`, and the app checks it with `verify_otp` and then asks for a new password. Bring it back once there's an email sender (for example a domain with Resend).
- **Community ID**: other members suggest a breed for "Not identified yet" posts in Social (shared photos already show there). Needs a suggestions table with RLS, and a way for the poster to accept one (`set_sighting_breed`). Photo ID could suggest a breed for them too.
- Regional life lists.
