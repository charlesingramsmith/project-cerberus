# Setting up "Continue with Apple"

The code is already in the app, but the button stays **hidden** until you switch it on
(step 4), because it can't work before Apple and Supabase are set up. Email, password and
Google sign-in keep working either way.

**Why:** the App Store requires Sign in with Apple in any iPhone app that offers Google
sign-in. It only has to be on the iPhone app, but setting it up now means people who join
with Apple on their phone can sign in to the website with the same account later.

**What you need first:** a paid **Apple Developer Program** membership (about £79 a year,
developer.apple.com/programs). Enrolling as an individual can take a day or two to be
approved.

You'll also need your Supabase project's **callback URL**:
`https://YOUR-PROJECT-REF.supabase.co/auth/v1/callback` (Supabase shows it under
**Authentication > Sign In / Providers > Apple**).

## 1. Apple: make the IDs and a key

All in [developer.apple.com/account](https://developer.apple.com/account) >
**Certificates, Identifiers & Profiles**.

1. **Identifiers > +  > App IDs > App**. Description: Derlin. Bundle ID (explicit):
   `app.derlin`. Tick **Sign in with Apple**. Continue, Register.
2. **Identifiers > + > Services IDs**. Description: Derlin web sign-in. Identifier:
   `app.derlin.signin`. Register. Then open it, tick **Sign in with Apple** and press
   **Configure**:
   - Primary App ID: the `app.derlin` one from step 1.
   - Domains and subdomains: `YOUR-PROJECT-REF.supabase.co` (no `https://`).
   - Return URLs: the Supabase callback URL from above.
   - Next, Done, Continue, Save.
3. **Keys > +**. Name: Derlin sign-in. Tick **Sign in with Apple**, Configure, pick the
   `app.derlin` App ID, Save, Continue, Register. **Download the .p8 file** (Apple only
   lets you download it once; keep it somewhere safe, never in the repo). Note the
   **Key ID**.
4. Note your **Team ID** (top right of the developer site, or Membership details).

## 2. Supabase: turn on Apple

1. Supabase > **Authentication > Sign In / Providers > Apple**: switch it on.
2. **Client IDs**: `app.derlin.signin` (the Services ID). When the iPhone app exists, add
   its bundle ID `app.derlin` here too, separated by a comma.
3. **Secret Key (for OAuth)**: Supabase's Apple guide
   (supabase.com/docs/guides/auth/social-login/auth-apple) has a small tool that makes it
   from your Team ID, Key ID, Services ID and the .p8 file. Paste the result and save.
4. Redirect URLs are already set for Google (`https://app.derlin.app/**`), so nothing
   to add there.

**Put a reminder in your calendar for 6 months' time:** Apple makes this secret expire
after 6 months. When it does, Apple sign-in stops working until you make a new one with
the same tool and paste it in again.

## 3. Update the privacy policy

Before switching the button on, the privacy policy must say Apple is used: ask Claude to
"update the privacy policy for Sign in with Apple" (the list is in `legal/README.md`).

## 4. Switch the button on

- **Render (app.derlin.app):** Render dashboard > the **derlin** service > **Environment**
  > **Add environment variable**: key `APPLE_SIGN_IN`, value `1`. Save; Render redeploys
  and the button appears under "Continue with Google".
- **Running locally:** add `apple_sign_in = true` to the `[supabase]` section of
  `.streamlit/secrets.toml`.

To hide it again, set `APPLE_SIGN_IN` to `0` (or delete it).

## Good to know

- People can choose **Hide My Email**: Supabase then gets an `@privaterelay.appleid.com`
  address. That's fine for signing in; their username starts from that address and they
  can change it in Profile.
- Apple only shares someone's name the very first time they sign in.
- The button is plain text ("Continue with Apple"). Apple's design rules ask for its own
  button style with the Apple logo; the iPhone app should use Apple's native button.
