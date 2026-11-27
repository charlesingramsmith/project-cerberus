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
| **Photo ID** | Takes or uploads a photo; the app suggests likely breeds | Done (first version) |
| **Sound ID** | Records a bark; the app suggests what it can | Later (experimental) |

A guided question flow ("help me identify": size, coat, ears) was considered and dropped in favour of ML.

## Done

- [x] Manual sighting log and life list for the top 100 breeds
- [x] **More breeds** (27 Nov 2026): 41 breeds beyond the top 100, the ones Photo ID knows that we didn't list, so its suggestions for them can be logged (141 in all). They have no AKC rank (`rank` blank in `data/breeds.csv`) and sit after the top 100, A to Z. Left out: the model's "toy terrier" (a mix of small terriers, no single breed) and "Eskimo dog" (its photos look like Siberian Huskies). Badges now go every 10 after 100, with a last one for all 141.
- [x] **Cross breeds** (27 Nov 2026): a "It's a cross breed" switch on Spotted! shows a second breed box; the sighting's `breed` is saved as "Breed A x Breed B" in A to Z order (`logic.cross_name`), so no schema change. The first sighting of each cross is a lifer (owner's choice, one switch `logic.CROSSES_ARE_LIFERS` if they change their mind); crosses aren't added to `user_breeds` (a typed-in parent is). Life list has a **Crosses** section.
- [x] Accounts and a hosted database (Supabase, with row-level security)
- [x] Continue with Google (setup steps in [docs/google-sign-in.md](docs/google-sign-in.md))
- [x] Bottom tab bar: Spotted! (was Dog ID, then Post), Life list, Profile, Social (placeholder), Settings
- [x] "Keep me signed in" for 30 days (refresh token in browser storage, renewed on each visit)
- [x] **What's new** in Settings: version number and history from `CHANGELOG.md`, "Coming next" from this file's Now and Next sections, a +1 vote on each upcoming feature, and a box to suggest features.
- [x] A "new update" dot on the Settings tab, cleared by opening Settings (the version seen is saved to the user's account)
- [x] **Profiles**: unique username, a dog emoji picture, favourite breed and your own dogs (up to 5), in a `profiles` table created on first sign-in.
- [x] **Breed profiles**: tap a breed on the life list to see a photo, a short intro, where it's from, its temperament and a fun fact. Text in `data/breed_info.csv`; credited Wikimedia Commons photos in `data/breed_photos.csv` (made by `scripts/fetch_breed_photos.py`).
- [x] **Breed photos as pictures**: small breed photos on every life-list row (greyed out until spotted), and any breed's photo as your profile picture (shown on your profile and in Social). Each picture is zoomed in on the dog's face, framed by hand with `scripts/face_cropper.py` (saved in `data/breed_faces.csv`; `logic.face_photo` picks a sharp enough copy).
- [x] **Photos on sightings**: an optional photo (phone camera or upload) on each sighting, shown on its card in Profile. `logic.prepare_photo` shrinks it to a 1600px JPEG, turns it the right way up and drops its metadata (GPS); it goes to the private `sighting-photos` Storage bucket at `<user id>/<photo id>.jpg`, with RLS so only the owner can add, read or delete it, and `sightings.photo_path` points at it. Shown via signed links (1 hour).
- [x] **Social feed**: the latest 50 sightings from everyone who shares, with their name and picture. Sharing is on by default (a popup says so on a member's first visit), with an off switch in Settings > Privacy; the "where" field is shown as typed (the log form says so).
- [x] **Dog profiles**: give your dogs a profile (a unique @username, name, breed, bio and photo) and tag any dog in a sighting. Tags and sighting photos show in Social; tapping a tag (or "Find a dog") opens the dog's page: its profile, every shared sighting it's tagged in and a gallery of their photos (`app.dog_page`, `backend.dog_sightings`).
- [x] **Report a post** (27 Nov 2026): a quiet **Report** menu on other members' posts in Social and on dog pages, with four reasons (inappropriate photo, not a dog, spam, something else). It hides the post or dog for the reporter at once; the owner reviews reports with [docs/reviewing-reports.md](docs/reviewing-reports.md) and the daily 8:30 check. `reports` table (members insert and read only their own), `backend.report`/`my_reports`, `logic.REPORT_REASONS`.
  - `dogs` table (owner-only changes, all members read) and `sighting_dogs` tags (you tag in your own sightings; the poster or the dog's owner can remove a tag) in `supabase/schema.sql`. Dog photos go in the owner's folder of the `sighting-photos` bucket at `<user id>/dogs/<id>.jpg`; one Storage policy lets members see dog photos and photos on sightings they can see.
  - The older `profiles.dogs` list (names only) is moved into dog profiles automatically on the member's next visit (`move_listed_dogs_to_profiles` in `app.py`); the column stays for now.
  - Tagging a dog with a known breed and leaving Breed empty logs that breed (`logic.tagged_breed`), and an empty name gets the dogs' names (`logic.tagged_names`), a first step towards posting as a way to identify dogs.
  - Still to do: removing a tag of your dog from someone else's post (the database allows it, there's no button yet), and a shareable link to a dog's page.
- [x] **Add your own breeds**: every breed in `data/breeds.csv` is verified. A breed that isn't listed can be typed into the Spotted! breed picker; it's logged with an "Unverified breed" badge (life list section, Profile, Social) and goes on the shared `user_breeds` list, which other members can pick from and the owner reviews (see [docs/reviewing-breeds.md](docs/reviewing-breeds.md)).
  - Guesses made on 26 Nov 2026, easy to change: unverified breeds don't count as lifers or towards badges (`listed=` in `logic.is_lifer`/`badge_progress`), and an added breed is visible to every member straight away (the owner can tick `rejected` to hide one).
  - Not built: an admin page in the app to review and verify breeds. Verifying is a code change for now (add the breed to the four `data/` breed files).
- [x] **Badges**: milestone badges for your first lifer and then every 5 breeds up to 100, then every 10, plus one for all 141 breeds (26 in all, each named), shown on your profile (earned date, or how many to go), a "next badge" hint on the life list, and a message when you earn one. Pure functions in `cerberus/logic.py` (`BADGES`, `badge_progress`), worked out from sightings each run, so no table. Badges also show in the Social feed on the sighting that earned them (`milestone_sightings`, from the spotters' shared sightings; members who don't share stay out). Show a member's full badge set once member profiles are viewable (More social).
  - 27 Nov 2026 (owner's ask): three tracks in `logic.BADGE_TRACKS`. **Lifer** (`BADGES`, the ladder above) counts lifers, crosses included; **Purebred** (`PUREBRED_BADGES`, 10/25/50/100/141) counts verified breeds only; **Cross** (`CROSS_BADGES`): Matchmaker (first cross), Doodle collector (3 Poodle crosses), Family reunion (a cross and both its parents). Profile shows one track at a time with the next badge up front.
- [x] **Visual refresh**: a pencil-sketch dachshund logo, pastel pistachio green with plum highlights, handwritten Caveat headings and Nunito text, in light and dark. Layout and tabs unchanged.
  - Picked by the owner on 27 Nov 2026 from a mood board (3 logos, 3 pistachio palettes, 3 font pairs). Colours and fonts live in `.streamlit/config.toml`; the matching CSS colour tokens (`--pistachio`, `--plum`, ...) are at the top of `MOBILE_CSS`. The logo is `assets/logo.svg` (pencil look from an SVG filter, light/dark built in) and `assets/icon.png` (the head on a pistachio tile: browser tab icon and the small header logo).
  - Pastel pistachio is too pale for white text, so primary buttons get dark text in `MOBILE_CSS`, and links, the open tab and selected options use a deeper green.
  - Then (27 Nov 2026, owner's ask): no emoji anywhere. Hand-drawn pencil icons (`cerberus/sketches.py`) on the bottom tabs, every badge, ticks, tips and Social posts; a Dark mode switch in Settings, with light as the default (see CLAUDE.md "Light and dark mode").
  - Later, once there's a brand name: a wordmark, illustrations (e.g. pencil sketches for badges or empty states), and maybe a layout refresh.

- [x] **Photo ID** (first version, step 1 of **Dog identification**): add a photo on Spotted! and get up to 3 breed suggestions, each "Very likely" (score 0.7 or more), "Possible" (0.3 or more) or "Long shot"; tap one to fill in the breed. "Not sure" (best guess under 0.3) and "can't see a dog" (the dog classes add up to under 0.5) show a message instead.
  - Model: MobileNetV3Large trained on ImageNet (`models/dog_breeds.onnx`, 22 MB, made by `scripts/export_photo_id_model.py`), run in the app with `onnxruntime` (`cerberus/photo_id.py`, a few milliseconds per photo). `data/photo_id_breeds.csv` maps its 118 dog classes to 114 of our 141 breeds (73 of the top 100, plus the 41 added for it); `logic.breed_guesses` adds up classes per breed and scores them as a share of all dog classes.
  - Tested on 27 Nov 2026 with 376 web photos (4 per breed, 94 of our breeds, from an FCI breeds photo set on GitHub): for the 73 breeds it knows, the right breed was in the top 3 for 98% of photos (top guess 91%). Across all 94 breeds it's about 73%, because it can't suggest the 27 it doesn't know, and for those it sometimes confidently suggests a look-alike. **Smarter Photo ID** (Next) fixes that.
  - The photo stays on our server. Photo ID runs once per photo (cached by the photo's hash in `st.session_state`).
- [x] **Date and place from a photo** (27 Nov 2026, owner's ask): adding a photo on Spotted! fills in **Date seen** from when it was taken and suggests **Where** as a short place name ("Hyde Park, London"). Both can be changed.
  - `logic.photo_details` reads the photo's EXIF (date taken, GPS) from the original upload, before `prepare_photo` strips it. The spot is rounded to about 100 m and sent to OpenStreetMap's free reverse geocoder, Nominatim (`cerberus/places.py`, cached in `app.look_up_place`); `logic.place_name` makes the short name. Only the place name the member keeps is saved, never coordinates (sightings still store free text).
  - Many photos carry no details: screenshots, photos shared through messaging apps, and some phone browsers (iPhone Safari especially) remove the location when a photo is picked. Then nothing is filled in. Nominatim allows about one lookup a second: if the app grows a lot, move to a paid geocoder or our own.

## Now

_Nothing in progress. Pick the next item from below._

## Next

- [ ] **Dog identification**: a bigger project to help you work out which dog you've seen. Its first step, Photo ID, is done.
  - Brainstormed with the owner on 27 Nov 2026. Decisions:
    - **Breed only** for now. Recognising a *particular* dog (matching a photo to a dog profile) waits until members have uploaded lots of dog photos.
    - **Step 1, ready-made model:** use a free, pretrained model that already knows dog breeds (a small MobileNet/EfficientNet-style ImageNet model, which includes about 120 breeds, or a Stanford Dogs model shared on Hugging Face). Map its class names to our `data/breeds.csv` names. Its breed list doesn't fully match ours (e.g. no Cane Corso), so missing breeds simply never get suggested.
    - **Step 2, our own model:** fine-tune the same small model on our exact breed list (free on Google Colab or the owner's PC), adding a few popular UK crosses as extra classes (e.g. Cockapoo, Cavapoo, Labradoodle, Cavachon), picked using the `user_breeds` list. Training happens offline, never in the app.
    - **Runs inside the app** on the Streamlit Cloud server: free, and photos never leave our setup. Keep the model small (about 20 MB, e.g. via ONNX Runtime) because big models (about 350 MB, like ViT) could exceed the free server's memory. Hosted inference (Hugging Face) and in-browser models were considered and set aside for now.
    - **Not sure and mixes:** always show the top 3 with plain labels ("Very likely", "Possible", "Long shot"), no percentages. If even the best guess is weak, or it may not be a dog, say "Not sure, pick the breed yourself". For a mix the top 3 are often its parent breeds; the member chooses one or types the cross as an unverified breed. Nothing is logged without a tap.
    - **Good enough to release:** on about 100 real photos the model hasn't seen (some of the owner's plus breed photos), the right breed is in the top 3 at least 8 times out of 10.
    - **Licences:** check each model's licence before using it. Stanford Dogs is for research use only: fine for this free portfolio app, but recheck before any paid launch (**Launch a real app**).
  - Covers these items rather than repeating them: **Photo ID** (Done), **Smarter Photo ID** (below), **Help train the model with your photos** and **Sound ID** (Later), and the saved "Not sure / Mixed breed" dog ID mechanics in **Ideas** (built once in PR #25, reverted in PR #27, kept in git).
  - Step 1 is live as **Photo ID** (Done). Step 2 is **Smarter Photo ID** (below).
- [ ] **Smarter Photo ID**: Photo ID learns all our breeds, plus popular crosses like the Cockapoo and Labradoodle.
  - Step 2 of **Dog identification** above: fine-tune the same small model on our exact breed list (free on Google Colab or the owner's PC) and add a few popular UK crosses, picked using the `user_breeds` list. Save it as `models/dog_breeds.onnx` with a new `data/photo_id_breeds.csv` (then the class numbers are our own).
  - Training data: a public set with photos for our breeds and their licences checked, later members' opt-in photos (**Help train the model with your photos**). Hold some photos back to test it against the same bar (right breed in the top 3 at least 8 times out of 10).

## Later

- [ ] **Help train the model with your photos** (opt-in): let members share their confirmed sighting photos to improve Photo ID.
  - Builds on Photo ID. A confirmed sighting (photo + the breed the user chose) is a labelled training example.
  - Must be opt-in and separate from the Social sharing switch, with clear wording about how photos are used. Members can withdraw. Check consent and licence wording before collecting anything.
  - Needs a review step: user-chosen breeds can be wrong, so keep only confident or double-checked labels. Retraining happens offline, not in the app.
- [ ] **Sound ID**: record a short bark and get a hint about the dog.
  - Telling *breeds* apart by bark isn't reliable with current public data, so a realistic first version is "dog detected" plus a rough size guess, used alongside Photo ID or the breed picker. A pretrained audio classifier (e.g. YAMNet, which recognises "dog bark") with `st.audio_input`.
- [ ] **Streak badges**: badges for spotting dogs several days or weeks in a row.
  - Add to `logic.BADGES`/`badge_progress` (badges are worked out from sightings, no table). Decide what counts as a streak (days with any sighting?) and whether a streak badge stays once the streak ends.
- [ ] **Location on a sighting** (optional): where the dog was seen.
  - Simplest start: a free-text place name (e.g. "Hyde Park"). Then add "Use my current location" on phones; Streamlit has no built-in GPS, so this needs a small component that asks the browser for location (with the user's permission). Could also pick a spot on a map.
  - New nullable column(s) on sightings in `supabase/schema.sql` (place name, and optionally latitude/longitude).
  - The free-text "where" already exists and is shown in the Social feed as typed. Exact GPS spots should stay private (never shown in Social).
  - Done: a photo's own location suggests the place name (see **Date and place from a photo** in Done).
- [ ] Map of where you've spotted dogs (builds on location on a sighting)
- [ ] **More social**: compare life lists, leaderboards, "new lifer" highlights in the feed, and tapping a name to see that member's profile.
  - Builds on `profiles` and the "Members can read shared sightings" RLS policy. Comparing life lists and leaderboards work best between **Friends** (below).
  - Later: likes/comments. (Reporting posts and dog profiles is done.)
- [ ] **Friends**: add other members as friends, see a friends-only feed and compare life lists with them.
  - Planning: decide mutual friends (request + accept) or one-way follows; mutual is simpler for privacy and is what messaging would need. How do you find someone: by member username, from a post in Social, or an invite link?
  - Builds on `profiles` (member usernames) and the Social feed: a feed filter of "Everyone / Friends". Dog @usernames stay separate: you befriend people, and could later "follow" a dog.
  - Decide how it fits the sharing switch: maybe a third setting, "share with friends only", which needs a new RLS rule on sightings and on the photo Storage policy.
  - New `friendships` table (who asked, who, status) with RLS so only the two members involved can see or change it. Removing a friend should be quiet (no notice).
- [ ] **Messaging**: send a private message to a friend, for example about a dog you both spotted.
  - Planning: friends-only to start (needs **Friends**), which cuts spam. Text only first; photos later. Decide whether it's one-to-one only or group chats too.
  - Safety comes with it, not after: block a member (they can't message you, find you or see your posts), report a message, and a way for the owner to review reports. Blocking should also hide them in Social and Find a dog.
  - New `conversations`/`messages` tables with RLS so only the people in a conversation can read it. Messages are member text, so show them escaped (plain text), like bios.
  - Streamlit has no live updates or push notifications: new messages would show on the next rerun or a refresh button. Realtime chat and notifications fit better after **Launch a real app** (Supabase Realtime and push in a store app). Email alerts would need the domain's email sender.
  - Check privacy-policy and age-rating wording before launch: app stores ask about user-to-user messaging.
**The launch plan, in order** (agreed with the owner on 27 Nov 2026; the three items below give the detail). Each step waits for the one before it:

1. **Pick a name (naming brainstorm first).** Sit down together and brainstorm names before anything else, because the domain, the website and the store listings all use it. See **A brand name**.
2. **Buy the domain** (about £10 a year). A domain is the web address, like `ourname.app`. Buy it from a registrar such as Cloudflare, Porkbun or Namecheap, which are cheap and include privacy for your contact details. See **Our own web address**.
3. **A free one-page website on the domain.** A simple landing page that says what the app is and has a button to open it. Free hosts such as GitHub Pages or Cloudflare Pages can serve it.
4. **Move the app's hosting off Streamlit Cloud** (about £5-7 a month on Render or Railway) so the app itself runs on the domain. Meanwhile, "Add to Home Screen" in a phone's browser already gives an app-like icon as a stopgap. See **Launch a real app**.
5. **A native app, last.** Rebuild the screens as a phone app (for example with React Native) on the same Supabase backend, so members' accounts and sightings carry over. Then publish to Google Play (about £20 once) and the App Store (about £80 a year).

Done so far: the name is **Derlin** (27 Nov 2026), `derlin.app` is bought (Porkbun), and the landing page is built in `site/` (see `docs/landing-page.md`); it goes live once the DNS records are in.

A **privacy policy and terms of use** are drafted in `legal/` (27 Nov 2026) and shown in the app; the landing page can show the same text. Update them at each step (new host, new services), and have them checked before the app stores.

- [ ] **A brand name**: a proper name for the app (it's called Project Cerberus for now).
  - Planning: shortlist names; check each is free as a domain, on the App Store and Google Play, and on social handles; do a quick trademark search (UK IPO, EUIPO, USPTO) for the pet/app classes; ask a few members which they like.
  - Decide whether "Cerberus" stays as the code/project name and only the app's display name changes.
  - The owner chose (27 Nov 2026) to do the visual refresh first under the current name and rework the name later. The dachshund logo can stay; a wordmark follows the name. Do the name before buying a domain (step 1 of the launch plan above).
  - Changing it touches the page title and text in `app.py` (including the sign-in screen under the logo), `README.md`, the Google sign-in consent screen and Supabase email templates.
- [ ] **Our own web address (domain)**: e.g. `<brand>.app` instead of `project-cerberus.streamlit.app`.
  - Planning: pick the name first; choose a registrar (cost per year, renewal price, WHOIS privacy); decide between `.com`, `.app` (HTTPS only, fine for us) or a country domain.
  - Streamlit Community Cloud can't use a custom domain, so a domain mostly pays off together with **Launch a real app** (new hosting). Until then it could redirect to the current address.
  - A domain also gives us an email sender (e.g. Resend or similar with SPF/DKIM records), which is what **password reset** was waiting for (see Ideas), and a `hello@` address for feedback.
  - After moving: add the new address to Supabase **Redirect URLs** and **Site URL**, and to the Google Cloud OAuth client.
- [ ] **Launch a real app**: Cerberus on your phone's home screen, and later in the app stores.
  - First step: an installable "Add to Home Screen" web app. Needs hosting where we control the web app manifest and icons, so it means moving off Streamlit Community Cloud.
  - Then: a store app (iOS and Android). Options to compare: wrapping the web app (e.g. Capacitor) vs. rebuilding the UI natively; Supabase and the RLS rules can stay as they are.
  - Planning: decide on hosting (another Python host such as Render or Fly.io, or a rebuild in a web framework), what it costs per month, and how a deploy works without breaking "Keep me signed in" (saved tokens are tied to the site's address, so members sign in once more after a move). Name and domain should be done first (the visual refresh is done).
  - Store launch checklist: Apple Developer (yearly fee) and Google Play accounts, a privacy policy page (photos, location, sharing), store screenshots and description, an age rating, and account deletion inside the app (both stores require it).
  - Keep the daily user-suggestions check going through launch, and add a way to report problems.
  - **Fix the tab bar height when we move.** Today `MOBILE_CSS` in `app.py` lifts the bottom tab bar by 3rem on screens up to 840px wide so Streamlit Community Cloud's "Hosted with Streamlit" badge doesn't cover the last tabs. Off Community Cloud that badge is gone, so remove the lift (the `@media (max-width: 840px)` block) and the bar sits flush with the bottom again, keeping `env(safe-area-inset-bottom)` for phones with a home bar. Check it at 375px in light and dark.

## Ideas (not yet committed to)

- Password reset by email. Built and removed in Nov 2026 (v0.11.0 to v0.13.1): Supabase only lets you edit the reset email template once custom SMTP is set up, and the owner chose not to set one up yet. The working version is in git (commit e30b98e): the email template links to `{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery`, and the app checks it with `verify_otp` and then asks for a new password. Bring it back once there's an email sender (for example a domain with Resend).
- Mixed-breed / "unknown" sightings that can be identified later (part of **Dog identification**, a good fit for Photo ID). A first version was built and taken out again on 26 Nov 2026 (PR #25, reverted): "Not sure: help me identify it" and "Mixed breed" options on the post form (typed-in breeds came back separately as **Add your own breeds**), an Identify button in Profile, and an "Other dogs" section on the life list, with no schema change. Bring it back with `git revert` of the revert commit when it is time for dog ID.
- Regional life lists.
