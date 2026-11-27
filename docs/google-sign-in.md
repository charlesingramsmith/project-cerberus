# Setting up "Continue with Google"

You do this once, in two dashboards. The code is already in the app. Until these
steps are done, the Google button will show an error from Supabase. Email and
password sign-in keeps working either way.

You'll need your Supabase project's **callback URL**. It looks like
`https://YOUR-PROJECT-REF.supabase.co/auth/v1/callback`. Find it in Supabase under
**Authentication > Sign In / Providers > Google**.

## 1. Google Cloud: get a Client ID and Client Secret

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a
   project (any name, e.g. "Derlin").
2. **APIs & Services > OAuth consent screen** (Google may call it **Google Auth
   Platform > Branding**). This is the screen people see when they sign in.
   - App name: Derlin. Support email: yours.
   - Audience: **External**.
   - Under **Data access**, add only these scopes: `openid`, `.../auth/userinfo.email` and
     `.../auth/userinfo.profile`. These scopes don't need Google to review the app.
   - When it's ready, **Publish** the app so anyone can sign in, not only test users.
3. **APIs & Services > Credentials > Create credentials > OAuth client ID**.
   - Application type: **Web application**.
   - **Authorised JavaScript origins**: `https://app.derlin.app`,
     `https://project-cerberus.streamlit.app` and `http://localhost:8501`.
   - **Authorised redirect URIs**: the Supabase callback URL from above, and nothing else.
     Google sends people to Supabase, and Supabase sends them on to the app.
4. Copy the **Client ID** and **Client Secret**.

## 2. Supabase: turn on Google

1. **Authentication > Sign In / Providers > Google**: switch it on, then paste the
   Client ID and Client Secret, and save.
2. **Authentication > URL Configuration > Redirect URLs**: add both of these
   (the `**` lets the app add `?flow=...` to the end):
   - `https://app.derlin.app/**`
   - `https://project-cerberus.streamlit.app/**`
   - `http://localhost:8501/**`

The Client Secret lives only in Supabase. It never goes in the app or in `secrets.toml`.

## 3. Try it

Run the app locally, click **Continue with Google**, and sign in with Google.
You should land on your life list. Then try it on the live site.

If you land back on the sign-in screen with "That Google sign-in link expired", Supabase
probably didn't accept the return address. Check the Redirect URLs from step 2.
If the app is reached at an unusual address, you can set it in `secrets.toml` (on Render
it's the `SUPABASE_REDIRECT_URL` setting in `render.yaml`):

```toml
[supabase]
redirect_url = "https://project-cerberus.streamlit.app/"
```

## How it fits together

- Signing in with Google for the first time creates the account. The name on the
  life list comes from the Google account.
- If someone already has an email/password account and signs in with Google using
  the same (verified) email, Supabase links the two, so they keep their sightings.
- On Render (app.derlin.app) there's no frame, so the button simply goes to Google.
- Google won't show its sign-in page inside the frame that Streamlit Community Cloud
  puts apps in, and that frame isn't allowed to send the whole tab elsewhere. A small
  script in `app.py` (`SAME_TAB_SIGN_IN_JS`) gets round this by asking the page around
  the frame to go to Google, so everything happens in one tab. If that ever stops
  working, the button falls back to opening Google in a new tab.
