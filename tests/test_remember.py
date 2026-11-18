"""The cookie script behind "Keep me signed in"."""
from cerberus.remember import COOKIE_NAME, MAX_AGE_SECONDS, cookie_script


def test_saving_a_token_sets_a_30_day_cookie_for_the_whole_app():
    script = cookie_script("token-abc")
    assert f'"{COOKIE_NAME}=" + encodeURIComponent("token-abc")' in script
    assert MAX_AGE_SECONDS == 30 * 24 * 60 * 60
    assert f"Max-Age={MAX_AGE_SECONDS}" in script
    for attribute in ("Path=/", "SameSite=Lax", "Secure"):
        assert attribute in script


def test_no_token_deletes_the_cookie():
    assert "Max-Age=0" in cookie_script(None)


def test_token_cannot_break_out_of_the_script():
    script = cookie_script('"</script><script>alert(1)//')
    assert script.count("</script>") == 1
    assert script.count("<script>") == 1
