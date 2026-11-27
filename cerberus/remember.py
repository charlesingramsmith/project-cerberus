""""Keep me signed in": remember a sign-in in the browser for 30 days.

Streamlit forgets everything when a tab is closed. To bring people back signed in,
the app saves their Supabase *refresh token* (a single-use pass that can be swapped
for a fresh sign-in) in the browser's local storage, along with an expiry date.

The server can't look in the browser's storage, so SAVED_SIGN_IN_JS runs in the page
as a tiny invisible component (`st.components.v2`). It does two jobs:

1. Once per Streamlit session it reports what's saved to Python, as the component's
   `saved` state: `{"session": <id>, "token": <token>}`, with an empty token if
   nothing is saved or the saved sign-in has expired. Python passes its own session id
   in `data["session"]` and ignores a report for another session. A page that stays
   open can outlive its Streamlit session (a phone waking up, a long idle tab): the
   browser then reconnects to a brand-new session and sends it the old report, whose
   token was spent long ago. Tagging each report with its session means the new
   session gets a fresh one instead.
2. Whenever Python passes `data["save"]`, it saves that token with a fresh 30-day
   expiry, or deletes the saved sign-in if the token is None.

It also looks after **light and dark mode**. Streamlit keeps the theme a visitor picked
in local storage under THEME_KEY_PREFIX + the page's path + THEME_KEY_SUFFIX, holding
"Light", "Dark" or "System". The app is light by default, so:

3. On a first visit (nothing saved, or "System") it switches to "Light".
4. Its report also says which theme is saved (`theme`), so the app can match its own
   colours (DARK_CSS in app.py).
5. When Python passes `data["theme"]` (the Settings switch) and it differs, it switches.
   Streamlit has no public way to change theme from code, so `streamlitThemes()` finds
   the switcher Streamlit's own Settings menu uses (inside React's internals) and calls
   it: instant, no reload, and Streamlit saves the choice itself. If a Streamlit upgrade
   hides it, the fallback saves the theme and reloads the page. A reload starts a new
   Streamlit session, so Python also passes `data["carry"]`, the current sign-in
   (`{"token", "remember"}`), kept in the tab's sessionStorage for the reload and handed
   back once in the next report as `carry`.

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
CARRY_KEY = "cerberus_theme_carry"  # sessionStorage: the sign-in kept across a theme reload
# Streamlit's own storage key for the chosen theme (frontend lib/theme "ACTIVE_THEME").
# Recheck it after a Streamlit upgrade: if it changes, the Settings switch stops working.
THEME_KEY_PREFIX = "stActiveTheme-"
THEME_KEY_SUFFIX = "-v2"
THEMES = ("Light", "Dark")

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

const THEME_KEY = "{THEME_KEY_PREFIX}" + window.location.pathname + "{THEME_KEY_SUFFIX}";
const CARRY_KEY = "{CARRY_KEY}";

function readTheme() {{
  try {{
    const theme = JSON.parse(localStorage.getItem(THEME_KEY) || "null");
    if (theme === "Light" || theme === "Dark") return theme;
  }} catch (err) {{}}
  return null;
}}

function streamlitThemes() {{
  // Streamlit's own theme switcher (what its Settings menu uses), found by walking up
  // React's internal tree from the app's root element. Not a public API: if a Streamlit
  // upgrade moves it, this returns null and useTheme falls back to a reload.
  try {{
    const root = document.querySelector('[data-testid="stApp"]');
    const fiberKey = root && Object.keys(root).find(k => k.startsWith("__reactFiber"));
    for (let fiber = fiberKey && root[fiberKey]; fiber; fiber = fiber.return) {{
      const theme = fiber.memoizedProps && fiber.memoizedProps.theme;
      if (theme && typeof theme.setTheme === "function" && theme.availableThemes) return theme;
    }}
  }} catch (err) {{}}
  return null;
}}

function useTheme(theme, carry) {{
  // Switch Streamlit's theme straight away (it saves the choice itself). Only if that
  // isn't possible, save it and reload the page. Returns true if the page reloads.
  const themes = streamlitThemes();
  const wanted = themes && themes.availableThemes.find(t => t.name === "Custom Theme " + theme);
  if (wanted) {{
    try {{
      themes.setTheme(wanted);
      localStorage.setItem(THEME_KEY, JSON.stringify(theme));
      return false;
    }} catch (err) {{}}
  }}
  try {{
    localStorage.setItem(THEME_KEY, JSON.stringify(theme));
    if (carry) sessionStorage.setItem(CARRY_KEY, JSON.stringify(carry));
  }} catch (err) {{
    return false;
  }}
  window.location.reload();
  return true;
}}

function takeCarry() {{
  try {{
    const carry = JSON.parse(sessionStorage.getItem(CARRY_KEY) || "null");
    sessionStorage.removeItem(CARRY_KEY);
    return carry;
  }} catch (err) {{
    return null;
  }}
}}

export default function ({{ data, setStateValue }}) {{
  // Light is the default: a first visit switches to it (even on a dark phone).
  if (!window.cerberusThemeChecked) {{
    window.cerberusThemeChecked = true;
    if (!readTheme() && useTheme("Light")) return;
  }}
  // The Settings switch: change theme (normally instantly; see useTheme).
  if (data && data.theme && data.theme !== readTheme() && useTheme(data.theme, data.carry)) {{
    return;
  }}
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
  if (!window.cerberusOldCookieCleared) {{
    window.cerberusOldCookieCleared = true;
    document.cookie = "{OLD_COOKIE_NAME}=; Max-Age=0; Path=/; SameSite=Lax; Secure";
  }}
  // Report what's saved once per Streamlit session; reporting reruns the app.
  const session = data && data.session;
  if (session && window.cerberusSavedSignInReportedTo !== session) {{
    window.cerberusSavedSignInReportedTo = session;
    setStateValue("saved", {{
      session, token: readSaved(), theme: readTheme() || "Light", carry: takeCarry(),
    }});
  }}
}}
"""
