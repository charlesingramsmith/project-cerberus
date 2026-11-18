# Project Cerberus

A Streamlit app where users log dog sightings and build a "life list" of breeds (like a birding life list). The first sighting of a breed is a **lifer**. Live at https://project-cerberus.streamlit.app. This is a portfolio project, so readable code, tests and the README matter as much as features.

The owner is new to Git and coding. Explain git/deploy steps in plain language and say what each command does.

## Commands (Windows, run from repo root)

```bash
.venv/Scripts/python.exe -m pytest -q                 # run all tests (must pass before commit)
.venv/Scripts/python.exe -m streamlit run app.py      # run locally at http://localhost:8501
.venv/Scripts/python.exe -m pip install -r requirements.txt   # install deps
```

If `.venv` is missing: `python -m venv .venv`, then install the requirements. Python 3.12.

`.claude/settings.json` pre-approves the commands above plus read-only git commands, and blocks reading or editing `.streamlit/secrets.toml`. Personal overrides go in `.claude/settings.local.json` (git-ignored).

## Architecture

| File | Role |
|---|---|
| `app.py` | Streamlit UI only: sign-in/sign-up screens (incl. Continue with Google), then five main tabs shown as a bottom tab bar: Dog ID (log a sighting), Life list (stat cards + breeds), Profile (summary + sightings history), Social (placeholder), Settings (account, sign out). `MOBILE_CSS` holds the mobile styling. |
| `.streamlit/config.toml` | Theme (light and dark) and minimal toolbar. Committed; no secrets. |
| `cerberus/logic.py` | Pure functions (`load_breeds`, `life_list`, `is_lifer`, `sightings_frame`). No I/O. Put new business logic here. |
| `cerberus/backends.py` | `Backend` protocol, with `SupabaseBackend` (real) and `MemoryBackend` (tests and demo mode). Both must behave the same. |
| `cerberus/oauth.py` | `PENDING` store for Google sign-in PKCE verifiers, keyed by a random `?flow=` id. |
| `docs/google-sign-in.md` | Owner's one-time setup for Google Cloud + Supabase. |
| `data/breeds.csv` | `rank,breed`: AKC 2025 top 100. Adding breeds means adding rows. |
| `supabase/schema.sql` | Source of truth for the DB: tables plus row-level security (RLS) policies. Idempotent. |
| `tests/` | `test_logic.py`, `test_backends.py` (MemoryBackend), `test_supabase_backend.py` (fake client), `test_app.py` (Streamlit `AppTest`, demo mode). |

Backend selection (in `app.py` `make_backend`): `CERBERUS_DEMO=1` forces memory; otherwise Supabase if `st.secrets["supabase"]` has a real url/key, else demo mode.

## Rules and gotchas

- **Never put the Supabase backend in `st.cache_resource` or any shared/global cache.** Each browser session gets its own backend in `st.session_state`; sharing would leak one user's login to another.
- **Google sign-in:** returning from Google starts a new Streamlit session (empty `session_state`), so the PKCE verifier waits in `cerberus.oauth.PENDING` (server memory, single-use, 10-minute expiry). It must only ever hold verifiers, never sessions or backends. Google refuses to load inside Streamlit Cloud's iframe, and that iframe's sandbox blocks links from navigating the whole tab, so `SAME_TAB_SIGN_IN_JS` makes a click on the `google_sign_in` button navigate the outer (same-origin) page instead; if that fails, the link opens a new tab. Recheck it in a real browser on the live site if Streamlit Cloud changes its wrapper. Supabase **Redirect URLs** must allow `<app url>/**`. `MemoryBackend` fakes the round trip for demo mode and tests.
- **Only the publishable/anon key is ever used.** Never add the secret/service_role key to the app. Per-user data isolation relies on RLS, not app code.
- **Schema changes:** edit `supabase/schema.sql` (keep it idempotent), add RLS policies for any new table, and tell the owner to run it in the Supabase SQL Editor. Nothing applies migrations automatically.
- **Adding a backend method:** add it to the `Backend` protocol and to **both** `SupabaseBackend` and `MemoryBackend`, with tests for each.
- **Secrets:** `.streamlit/secrets.toml` is git-ignored and holds real keys. Don't read it, print it or commit it. The template is `.streamlit/secrets.example.toml`.
- Supabase auth errors are wrapped in `AuthError`; the UI shows `str(err)`. Data calls that raise `AuthError` (expired session) send the user back to sign-in via `end_session()`.
- `AppTest` widgets are found by `key=` (e.g. `sign_up_email`). Give new form inputs explicit keys.
- Dates are stored and compared as ISO strings (`YYYY-MM-DD`).
- **Mobile first.** Design for a ~375px phone, then check desktop. Avoid `st.sidebar`, `st.columns` for side-by-side items (they stack on phones; use `st.container(horizontal=True)`) and wide `st.dataframe`s (use list rows or bordered cards). Buttons that end a form use `width="stretch"`.
- `MOBILE_CSS` targets Streamlit internals (`data-testid`, `.st-key-<key>` classes, `role="tablist"`), which can change when Streamlit is upgraded: recheck the phone layout after bumping the version. The bottom tab bar (`main_nav` container, labels in `NAV_TABS` are an icon, a line break, then the name) is pinned on all screen sizes; its colours must match `[theme.light]`/`[theme.dark]` `backgroundColor`.
- To check the phone layout: the `cerberus-demo` entry in `.claude/launch.json` runs demo mode on port 8502; view it at 375px wide in light and dark.

## Workflow

- **Pushing to `main` deploys to production** (Streamlit Community Cloud redeploys automatically). Run the tests before every push. Merge a branch into `main` only once it's tested.
- **One session, one branch.** At the start of every session, before editing anything, check `git status` and create a new branch for the task, named after it (e.g. `photo-upload`), from an up-to-date `main`: `git fetch` then `git switch -c <name> origin/main`. If the folder has uncommitted work from another branch, don't switch or stash it (another session may own it): make a separate folder with `git worktree add ../project-cerberus-<name> -b <name> origin/main` and work there. Tell the owner which branch you made and why. Only skip this if the owner says to continue on the current branch.
- Commit messages: an imperative summary line, e.g. "Add photo upload to sightings", then a blank line and **always** a short plain-English explanation of what changed and why (a few lines a non-coder can follow). No summary-only commits, even for small changes.
- **Keep this file current, unprompted.** Before every commit, check whether the change makes anything here wrong or missing (new files, commands, rules, gotchas). If so, update CLAUDE.md in the same commit. Keep it short and accurate; don't log history here (that's what git is for).
- Git commits use the owner's GitHub noreply email (already configured globally). Don't change git config.
- Keep `README.md` up to date (features, roadmap, architecture) when features change; it's the project's shop window.
- When dependencies change, pin exact versions in `requirements.txt` (Streamlit Cloud installs from it).

## Roadmap

`ROADMAP.md` is the source of truth for planned work (Done / Now / Next / Later / Ideas, with approach notes). Read it before starting a feature. When a feature lands, tick it there and update the README's short roadmap summary in the same commit. The big theme is three ways to identify a dog, like Merlin for birds: guided manual ID, photo ID, sound ID.
