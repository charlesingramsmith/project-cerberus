"""The browser-side script behind "Keep me signed in"."""
from cerberus.remember import MAX_AGE_DAYS, OLD_COOKIE_NAME, SAVED_SIGN_IN_JS, STORAGE_KEY


def test_script_saves_for_30_days_under_its_storage_key():
    assert MAX_AGE_DAYS == 30
    assert f'const KEY = "{STORAGE_KEY}";' in SAVED_SIGN_IN_JS
    assert f"const MAX_AGE_MS = {MAX_AGE_DAYS} * 24 * 60 * 60 * 1000;" in SAVED_SIGN_IN_JS


def test_script_reports_once_per_session_and_clears_the_old_cookie():
    assert "window.cerberusSavedSignInReportedTo !== session" in SAVED_SIGN_IN_JS
    assert 'setStateValue("saved", { session, token: readSaved() })' in SAVED_SIGN_IN_JS
    assert f"{OLD_COOKIE_NAME}=; Max-Age=0" in SAVED_SIGN_IN_JS
    assert "{{" not in SAVED_SIGN_IN_JS  # the f-string braces all came out single
