# Moving the app to app.derlin.app (Render)

Step 4 of the launch plan: the app leaves Streamlit Community Cloud and runs on
**Render** (render.com) at **app.derlin.app**. The landing page stays at `derlin.app`
(GitHub Pages), and its button will point at the app.

You do the sign-up, payment and DNS steps (they're your accounts). The code is ready:
`render.yaml` in the repo tells Render how to install and start the app.

**Cost:** Render's **Starter** plan, $7 a month (about £5.50), billed to your card
monthly. The workspace itself ("Hobby") is free. Render's free plan exists, but it
falls asleep after 15 minutes with nobody using it and takes about a minute to wake,
so members would often meet a loading screen.

**Why app.derlin.app?** `derlin.app` already shows the landing page, which is good
for people who've never heard of Derlin. A sub-address for the app keeps both, and
each can move to a different host later without disturbing the other.

## 1. Make a Render account (5 minutes)

1. Go to [render.com](https://render.com) and click **Get Started**.
2. Choose **GitHub** to sign up. This links Render to your GitHub account.
3. When Render asks which repositories it may see, pick **Only select repositories**
   and choose `project-cerberus`.
4. Add a payment card under **Workspace Settings > Billing** (Render asks for it
   when you pick a paid plan anyway).

## 2. Create the app from the Blueprint (10 minutes)

A "Blueprint" is Render's word for a settings file in the repo (`render.yaml`).

1. In the Render dashboard click **New > Blueprint**.
2. Pick the `project-cerberus` repository, branch `main`.
3. Render shows one service called **derlin** and asks for two values. Copy them from
   your `.streamlit/secrets.toml` on your PC (or Streamlit Cloud's **Secrets** box):
   - `SUPABASE_URL`: the `url` line (`https://...supabase.co`).
   - `SUPABASE_KEY`: the `key` line. It must be the **publishable** key
     (`sb_publishable_...` or the old "anon" key), never the secret one.
4. Click **Apply**. Render installs everything and starts the app. The first build
   takes about 5 minutes; watch the **Logs** tab.
5. When it says **Live**, open the address Render gives it (something like
   `https://derlin.onrender.com`) and check the app loads. Signing in with email
   works straight away; Google sign-in needs step 4 below.

From now on Render redeploys by itself whenever `main` changes, just like Streamlit
Cloud. If the app ever gets stuck: **Manual Deploy > Restart service**.

## 3. Point app.derlin.app at Render (5 minutes, then a wait)

1. In Render, open the **derlin** service > **Settings > Custom Domains**.
   `app.derlin.app` should already be listed (from `render.yaml`). If not, click
   **Add Custom Domain** and type `app.derlin.app`.
2. Render shows a **CNAME** target, like `derlin.onrender.com`. Copy it.
3. In **Porkbun**: **Account > Domain Management**, find `derlin.app` and click **DNS**.
   Add a record:
   - **Type:** `CNAME`
   - **Host:** `app`
   - **Answer:** the target you copied (e.g. `derlin.onrender.com`)
   - Leave TTL as it is, click **Add**.

   Don't touch the existing A and `www` records: they're the landing page.
4. Back in Render click **Verify**. It can take a few minutes (rarely an hour). Render
   then sets up the padlock (HTTPS) certificate itself. `.app` addresses only open over
   HTTPS, so the address works once the certificate is ready.

## 4. Let Google sign-in return to the new address (5 minutes)

Google sends people back through Supabase, so Supabase must trust the new address.

1. **Supabase > Authentication > URL Configuration**:
   - **Redirect URLs**: add `https://app.derlin.app/**`. Keep the Streamlit one for now,
     so both addresses work during the move.
   - **Site URL** (where email confirmation links go): change it to
     `https://app.derlin.app` once you're happy the new address works.
2. **Google Cloud > APIs & Services > Credentials**, open the OAuth client: under
   **Authorised JavaScript origins** add `https://app.derlin.app`. Leave
   **Authorised redirect URIs** alone (that's Supabase's own address and hasn't changed).
3. Try **Continue with Google** at https://app.derlin.app.

## 5. Tell Claude it's working

Then Claude does the switch-over in one change:

- the landing page button (and the README) point at `https://app.derlin.app`,
- the privacy policy names Render instead of Streamlit as the host,
- a What's new entry tells members the new address.

Members sign in once more at the new address (each web address keeps its own
"Keep me signed in" and light/dark choice). Their sightings, badges and photos are all
in Supabase, so nothing else changes. Leave the Streamlit Cloud app running for a few
weeks so old links still work, then delete it at share.streamlit.io.

## Good to know

- **Memory:** the Starter plan has 512 MB. Photo ID's model and Streamlit fit, but if
  Render's **Metrics** tab shows memory near the limit or the **Events** tab says
  "out of memory", move up to **Standard** ($25 a month, 2 GB) in **Settings > Instance Type**.
- **Region:** Frankfurt, Render's closest to the UK.
- **Logs:** the **Logs** tab shows the app's errors, which helps when something breaks.
- **Settings in `render.yaml`:** changing that file and pushing to `main` updates the
  service. The two Supabase values live only in Render (**Environment** tab), never in git.
