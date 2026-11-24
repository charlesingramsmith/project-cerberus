# Supabase CLI setup (one time, on your PC)

The Supabase CLI is a command-line tool that talks to your Supabase project. Once it's set up, a Claude session can apply changes in `supabase/schema.sql` to the live database for you (it will always ask first), instead of you pasting SQL into the SQL Editor.

You only do this once per computer. Run the commands below in a PowerShell window (Start menu > "PowerShell", or a Terminal tab in the Claude app). **Don't paste your access token or database password into a Claude chat.** The commands ask for them in the terminal or browser and keep them in Windows' own secure storage.

## 1. Install the CLI

On this PC it's already installed (v3.1.0, in `%LOCALAPPDATA%\Programs\supabase`). To install it on another PC, or to update it, download the official release from [Supabase's GitHub releases](https://github.com/supabase/cli/releases) and put `supabase.exe` in that folder. No administrator rights needed.

Pick the version (any `vX.Y.Z` release, not the `config-...` ones; one that's a week or two old is a safe choice):

```powershell
$v = "3.1.0"
```

Download it and Supabase's list of file fingerprints ("checksums") into your Downloads folder:

```powershell
cd $env:USERPROFILE\Downloads; Invoke-WebRequest "https://github.com/supabase/cli/releases/download/v$v/supabase_${v}_windows_amd64.tar.gz" -OutFile supabase.tar.gz; Invoke-WebRequest "https://github.com/supabase/cli/releases/download/v$v/checksums.txt" -OutFile supabase-checksums.txt
```

Check the download matches Supabase's fingerprint (prints `True` if it's genuine; stop if it says `False`):

```powershell
(Get-FileHash supabase.tar.gz -Algorithm SHA256).Hash -eq ((Select-String "supabase_${v}_windows_amd64.tar.gz" supabase-checksums.txt).Line -split ' ')[0].ToUpper()
```

Unpack `supabase.exe` into its folder:

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\Programs\supabase"; tar -xzf supabase.tar.gz -C "$env:LOCALAPPDATA\Programs\supabase" supabase.exe
```

Add that folder to your PATH (the list of places Windows looks for commands). Only needed the first time:

```powershell
[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path','User') + ";$env:LOCALAPPDATA\Programs\supabase", 'User')
```

Close and reopen PowerShell, then check it works (prints the version number):

```powershell
supabase --version
```

(Supabase also offers Scoop and `npx` installs. We don't use them here: Scoop's installer pipes a script from the internet straight into PowerShell, and `npx` needs Node.js, which this PC doesn't have.)

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

If it asks for your **database password** (the one you chose when creating the Supabase project; reset it under Project Settings > Database if you've forgotten), type it into the terminal. The CLI keeps it in Windows' secure storage. Linking also writes a few small files in `supabase/.temp/`, which git ignores.

If `supabase link` complains that `config.toml` is missing, run `supabase init` in the project folder, answer "N" to the questions, then run the link command again and tell Claude, so the new `supabase/config.toml` gets committed.

## 4. Check the connection

This runs a harmless read-only query against the live database and lists the app's tables:

```powershell
supabase db query --remote --read-only "select table_name from information_schema.tables where table_schema = 'public'"
```

You should see `sightings`, `profiles`, `feature_votes` and `feature_suggestions`. That's it: the next time a Claude session changes the schema, it can apply it for you.

## How schema changes are applied

`supabase/schema.sql` stays the single source of truth. It's written to be safe to run again and again ("idempotent"): it creates only what's missing and replaces policies and functions. So applying a change means running the whole file against the linked project:

```powershell
supabase db query --remote --yes -f supabase/schema.sql
```

`--remote` means "the linked live project" and `--yes` confirms you really mean to change it (the CLI refuses live changes without it). This changes the **live production database**, so a Claude session must ask you before every run. You can also run it yourself.

(Supabase also supports a `supabase/migrations/` folder of numbered change files, applied with `supabase db push`. We don't use it: one file you can read top to bottom is simpler, and the app's history lives in git anyway.)

## Notes

- Older CLI versions (v2) used `--linked` instead of `--remote`.
- Never run `supabase db reset` against the live project: it wipes the database.
- The CLI never needs the app's `.streamlit/secrets.toml` and never needs the secret/service_role key.
