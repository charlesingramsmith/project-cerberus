""""Keep me signed in": remember a sign-in in a browser cookie for 30 days.

Streamlit forgets everything when a tab is closed. To bring people back signed in,
the app saves their Supabase *refresh token* (a single-use pass that can be swapped
for a fresh sign-in) in a cookie. On the next visit the app reads the cookie with
`st.context.cookies` and swaps the token for a new session.

Streamlit can read cookies but has no way to write them, so this module builds a
tiny script that sets or deletes the cookie in the browser.

Refresh tokens are single use: every swap returns a new one, so the app writes the
new token back each visit. That also restarts the 30 days, so anyone who opens the
app at least once a month stays signed in. (Safari, and every browser on an iPhone,
deletes cookies written by scripts after 7 days, so there it's once a week.)
"""
from __future__ import annotations

import json

COOKIE_NAME = "cerberus_refresh"
MAX_AGE_DAYS = 30
MAX_AGE_SECONDS = MAX_AGE_DAYS * 24 * 60 * 60


def cookie_script(token: str | None) -> str:
    """A <script> that saves `token` in the cookie, or deletes the cookie if it's None.

    Path=/ so it's sent to the whole app (on Streamlit Cloud the app runs under /~/+/).
    SameSite=Lax so other sites can't send it, Secure so it only travels over HTTPS
    (browsers treat http://localhost as secure too).
    """
    max_age = MAX_AGE_SECONDS if token else 0
    # A safely quoted JavaScript string; escaping "<" stops it ever closing the <script>.
    value = json.dumps(token or "").replace("<", "\\u003c")
    return (
        "<script>document.cookie = "
        f'"{COOKIE_NAME}=" + encodeURIComponent({value}) + '
        f'"; Max-Age={max_age}; Path=/; SameSite=Lax; Secure";</script>'
    )
