# Supabase CLI setup (one time, on your PC)

The Supabase CLI is a command-line tool that talks to your Supabase project. Once it's set up, a Claude session can apply changes in `supabase/schema.sql` to the live database for you (it will always ask first), instead of you pasting SQL into the SQL Editor.

You only do this once per computer. Run every command below yourself in a PowerShell window (Start menu > "PowerShell", or a Terminal tab in the Claude app). **Don't paste your access token or database password into a Claude chat.** The commands ask for them in the terminal and keep them in Windows' own secure storage.

## 1. Install Scoop and the Supabase CLI

[Scoop](https://scoop.sh) is a small installer for command-line tools. It installs into your user folder, so it doesn't need administrator rights, and it's the install method Supabase recommends for Windows. (The other option, `npx supabase`, needs Node.js, which isn't installed on this PC.)

Allow PowerShell to run Scoop's install script (only scripts signed or written on this PC, and only for your user):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Download and run Scoop's official installer:

```powershell
Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression
```

Tell Scoop where Supabase publishes its CLI (a "bucket" is a list of apps Scoop can install):

```powershell
scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
```

Install the CLI:

```powershell
scoop install supabase
```

Check it worked (prints a version number like `2.x` or `3.x`):

```powershell
supabase --version
```

Later, to update it: `scoop update supabase`.

## 2. Sign in to Supabase

```powershell
supabase login
```

This opens your browser so you can approve access to your Supabase account. The CLI saves the resulting access token in Windows Credential Manager (not in this project folder), so it is never committed to git.

## 3. Link this project folder to your Supabase project

First move into the project folder:

```powershell
cd C:\Users\charl\code\project-cerberus
```

Find your **project ref**: it's the random-looking part of your Supabase URL (`https://<project-ref>.supabase.co`), also shown in Supabase under Project Settings > General. Then run, swapping in your ref:

```powershell
supabase link --project-ref <your-project-ref>
```

It asks for your **database password** (the one you chose when creating the Supabase project; reset it under Project Settings > Database if you've forgotten). Type it into the terminal. The CLI keeps it in Windows' secure storage. Linking also writes a few small files in `supabase/.temp/`, which git ignores.

If `supabase link` complains that `config.toml` is missing, run `supabase init` in the project folder, answer "N" to the questions, then run the link command again and tell Claude, so the new `supabase/config.toml` gets committed.

## 4. Check the connection

This runs a harmless read-only query against the live database and lists the app's tables:

```powershell
supabase db query --linked "select table_name from information_schema.tables where table_schema = 'public'"
```

You should see `sightings`, `profiles`, `feature_votes` and `feature_suggestions`. That's it: the next time a Claude session changes the schema, it can apply it for you.

## How schema changes are applied

`supabase/schema.sql` stays the single source of truth. It's written to be safe to run again and again ("idempotent"): it creates only what's missing and replaces policies and functions. So applying a change means running the whole file against the linked project:

```powershell
supabase db query --linked -f supabase/schema.sql
```

This changes the **live production database**, so a Claude session must ask you before every run. You can also run it yourself.

(Supabase also supports a `supabase/migrations/` folder of numbered change files, applied with `supabase db push`. We don't use it: one file you can read top to bottom is simpler, and the app's history lives in git anyway.)

## Notes

- Newer CLI versions rename `--linked` to `--remote`. If `--linked` gives an "unknown flag" or "deprecated" message, use `--remote` instead.
- Never run `supabase db reset --linked`: it wipes the live database.
- The CLI never needs the app's `.streamlit/secrets.toml` and never needs the secret/service_role key.
