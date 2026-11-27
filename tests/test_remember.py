"""The browser-side script behind "Keep me signed in"."""
from cerberus.remember import (
    CARRY_KEY, MAX_AGE_DAYS, OLD_COOKIE_NAME, SAVED_SIGN_IN_JS, STORAGE_KEY, THEME_KEY_PREFIX,
    THEME_KEY_SUFFIX,
)


def test_script_saves_for_30_days_under_its_storage_key():
    assert MAX_AGE_DAYS == 30
    assert f'const KEY = "{STORAGE_KEY}";' in SAVED_SIGN_IN_JS
    assert f"const MAX_AGE_MS = {MAX_AGE_DAYS} * 24 * 60 * 60 * 1000;" in SAVED_SIGN_IN_JS


def test_script_reports_once_per_session_and_clears_the_old_cookie():
    assert "window.cerberusSavedSignInReportedTo !== session" in SAVED_SIGN_IN_JS
    assert "session, token: readSaved(), theme: readTheme()" in SAVED_SIGN_IN_JS
    assert f"{OLD_COOKIE_NAME}=; Max-Age=0" in SAVED_SIGN_IN_JS
    assert "{{" not in SAVED_SIGN_IN_JS  # the f-string braces all came out single


def test_script_keeps_the_theme_in_streamlits_own_storage_key():
    # Streamlit reads the chosen theme from this key (if an upgrade renames it, the
    # Settings switch stops working: recheck it in the browser).
    assert f'"{THEME_KEY_PREFIX}" + window.location.pathname + "{THEME_KEY_SUFFIX}"' in SAVED_SIGN_IN_JS
    assert 'JSON.stringify("Light")' in SAVED_SIGN_IN_JS  # light by default
    assert f'const CARRY_KEY = "{CARRY_KEY}";' in SAVED_SIGN_IN_JS
    assert "sessionStorage" in SAVED_SIGN_IN_JS  # the sign-in carried over a reload ends with the tab
