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
| `app.py` | Streamlit UI only: sign-in/sign-up screens, then tabs (Log a sighting / Life list / Sightings). |
| `cerberus/logic.py` | Pure functions (`load_breeds`, `life_list`, `is_lifer`, `sightings_frame`). No I/O. Put new business logic here. |
| `cerberus/backends.py` | `Backend` protocol, with `SupabaseBackend` (real) and `MemoryBackend` (tests and demo mode). Both must behave the same. |
| `data/breeds.csv` | `rank,breed`: AKC 2025 top 100. Adding breeds means adding rows. |
| `supabase/schema.sql` | Source of truth for the DB: tables plus row-level security (RLS) policies. Idempotent. |
| `tests/` | `test_logic.py`, `test_backends.py` (MemoryBackend), `test_supabase_backend.py` (fake client), `test_app.py` (Streamlit `AppTest`, demo mode). |

Backend selection (in `app.py` `make_backend`): `CERBERUS_DEMO=1` forces memory; otherwise Supabase if `st.secrets["supabase"]` has a real url/key, else demo mode.

## Rules and gotchas

- **Never put the Supabase backend in `st.cache_resource` or any shared/global cache.** Each browser session gets its own backend in `st.session_state`; sharing would leak one user's login to another.
- **Only the publishable/anon key is ever used.** Never add the secret/service_role key to the app. Per-user data isolation relies on RLS, not app code.
- **Schema changes:** edit `supabase/schema.sql` (keep it idempotent), add RLS policies for any new table, and tell the owner to run it in the Supabase SQL Editor. Nothing applies migrations automatically.
- **Adding a backend method:** add it to the `Backend` protocol and to **both** `SupabaseBackend` and `MemoryBackend`, with tests for each.
- **Secrets:** `.streamlit/secrets.toml` is git-ignored and holds real keys. Don't read it, print it or commit it. The template is `.streamlit/secrets.example.toml`.
- Supabase auth errors are wrapped in `AuthError`; the UI shows `str(err)`. Data calls that raise `AuthError` (expired session) send the user back to sign-in via `end_session()`.
- `AppTest` widgets are found by `key=` (e.g. `sign_up_email`). Give new form inputs explicit keys.
- Dates are stored and compared as ISO strings (`YYYY-MM-DD`).

## Workflow

- **Pushing to `main` deploys to production** (Streamlit Community Cloud redeploys automatically). Run the tests before every push. For bigger features, prefer a branch and merge once it's tested.
- Commit messages: imperative summary line, e.g. "Add photo upload to sightings".
- **Keep this file current, unprompted.** Before every commit, check whether the change makes anything here wrong or missing (new files, commands, rules, gotchas, roadmap items done). If so, update CLAUDE.md in the same commit. Keep it short and accurate; don't log history here (that's what git is for).
- Git commits use the owner's GitHub noreply email (already configured globally). Don't change git config.
- Keep `README.md` up to date (features, roadmap, architecture) when features change; it's the project's shop window.
- When dependencies change, pin exact versions in `requirements.txt` (Streamlit Cloud installs from it).

## Roadmap ideas (from README)

Photo upload (Supabase Storage), photo breed identification, a sightings map, "stay signed in", more breeds.
