""""Keep me signed in": remember a sign-in in the browser for 30 days.

Streamlit forgets everything when a tab is closed. To bring people back signed in,
the app saves their Supabase *refresh token* (a single-use pass that can be swapped
for a fresh sign-in) in the browser's local storage, along with an expiry date.

The server can't look in the browser's storage, so SAVED_SIGN_IN_JS runs in the page
as a tiny invisible component (`st.components.v2`). It does two jobs:

1. Once per page load it reports what's saved to Python (an empty string if nothing
   is, or the saved sign-in has expired), as the component's `saved` state.
2. Whenever Python passes `data={"save": token}`, it saves that token with a fresh
   30-day expiry, or deletes the saved sign-in if the token is None.

(The first version used a cookie, but on Streamlit Community Cloud the cookie never
reaches the app, so `st.context.cookies` came back empty.)

Refresh tokens are single use: every swap returns a new one, so the app saves the new
token on each visit, which also restarts the 30 days. Anyone who opens the app at
least once a month stays signed in. (Safari, and every browser on an iPhone, clears
script-written storage after 7 days without a visit, so there it's once a week.)
"""
from __future__ import annotations

MAX_AGE_DAYS = 30
STORAGE_KEY = "cerberus_saved_sign_in"
OLD_COOKIE_NAME = "cerberus_refresh"  # from the first version; deleted on sight

SAVED_SIGN_IN_JS = f"""
const KEY = "{STORAGE_KEY}";
const MAX_AGE_MS = {MAX_AGE_DAYS} * 24 * 60 * 60 * 1000;

function readSaved() {{
  try {{
    const saved = JSON.parse(localStorage.getItem(KEY) || "null");
    if (saved && saved.token && saved.expires > Date.now()) return saved.token;
    localStorage.removeItem(KEY);
  }} catch (err) {{}}
  return "";
}}

export default function ({{ data, setStateValue }}) {{
  if (data && "save" in data) {{
    try {{
      if (data.save) {{
        const expires = Date.now() + MAX_AGE_MS;
        localStorage.setItem(KEY, JSON.stringify({{ token: data.save, expires }}));
      }} else {{
        localStorage.removeItem(KEY);
      }}
    }} catch (err) {{}}  // storage blocked (e.g. some private modes): just don't remember
  }}
  // Report what's saved once per page load; reporting reruns the app.
  if (!window.cerberusSavedSignInReported) {{
    window.cerberusSavedSignInReported = true;
    document.cookie = "{OLD_COOKIE_NAME}=; Max-Age=0; Path=/; SameSite=Lax; Secure";
    setStateValue("saved", readSaved());
  }}
}}
"""
