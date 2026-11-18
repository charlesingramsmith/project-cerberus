"""End-to-end check of the Streamlit app (in demo mode) using Streamlit's test runner."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def at(monkeypatch):
    monkeypatch.setenv("CERBERUS_DEMO", "1")
    app = AppTest.from_file(APP, default_timeout=10).run()
    assert not app.exception
    return app


def click(at: AppTest, label: str) -> AppTest:
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception
    return at


def sign_up(at: AppTest, username="charlie", email="charlie@example.com", password="correct-horse"):
    at.text_input(key="sign_up_username").input(username)
    at.text_input(key="sign_up_email").input(email)
    at.text_input(key="sign_up_password").input(password)
    at.text_input(key="sign_up_confirm").input(password)
    return click(at, "Create account")


def headers(at: AppTest) -> list[str]:
    return [h.value for h in at.header]


def log_breed(at: AppTest, breed_name: str) -> AppTest:
    breed = next(sb for sb in at.selectbox if sb.label == "Breed")
    breed.set_value(breed_name)
    return click(at, "Log sighting")


def test_signed_out_visitors_see_the_sign_in_screen(at):
    assert at.title[0].value == "🐕 Project Cerberus"
    assert any(b.label == "Sign in" for b in at.button)
    assert not at.header  # no life list until signed in


def test_mismatched_passwords_are_rejected(at):
    at.text_input(key="sign_up_username").input("charlie")
    at.text_input(key="sign_up_email").input("charlie@example.com")
    at.text_input(key="sign_up_password").input("correct-horse")
    at.text_input(key="sign_up_confirm").input("different-horse")
    click(at, "Create account")
    assert "don't match" in at.error[0].value


def test_full_journey(at):
    sign_up(at)
    assert "charlie's life list" in headers(at)
    assert at.metric[0].value == "0/100"

    log_breed(at, "Beagle")
    assert "New lifer" in at.success[0].value
    assert at.metric[0].value == "1/100"

    log_breed(at, "Beagle")
    assert "another" in at.info[0].value
    assert at.metric[0].value == "1/100"
    assert at.metric[1].value == "2"

    # Sign out, then back in: sightings are still there
    click(at, "Sign out")
    assert not at.header
    at.text_input(key="sign_in_email").input("charlie@example.com")
    at.text_input(key="sign_in_password").input("correct-horse")
    click(at, "Sign in")
    assert at.metric[1].value == "2"


def test_signed_in_app_has_five_main_tabs(at):
    sign_up(at)
    labels = [t.label.split("\n")[-1] for t in at.tabs]  # drop the icon line
    assert labels == ["Dog ID", "Life list", "Profile", "Social", "Settings"]
    assert headers(at) == ["Dog ID", "charlie's life list", "Your profile", "Social", "Settings"]


def test_profile_summarises_sightings(at):
    sign_up(at)
    log_breed(at, "Beagle")
    assert any("1 lifer from 1 sighting" in c.value for c in at.caption)


def test_wrong_password_shows_an_error(at):
    sign_up(at)
    click(at, "Sign out")
    at.text_input(key="sign_in_email").input("charlie@example.com")
    at.text_input(key="sign_in_password").input("wrong-password")
    click(at, "Sign in")
    assert "Invalid login" in at.error[0].value


def test_sightings_can_be_deleted_from_their_card(at):
    sign_up(at)
    log_breed(at, "Beagle")
    assert at.metric[1].value == "1"

    delete = next(b for b in at.button if b.key and b.key.startswith("delete_"))
    delete.click().run()
    assert not at.exception
    assert at.metric[1].value == "0"
    assert at.metric[0].value == "0/100"


def test_life_list_search(at):
    sign_up(at)
    at.text_input(key="life_search").input("retriever").run()
    assert not at.exception
    rows = "".join(m.value for m in at.markdown)
    assert "Golden Retriever" in rows
    assert "Beagle" not in rows


def google_link(at: AppTest) -> str:
    button = next(b for b in at.get("link_button") if b.proto.label == "Continue with Google")
    return button.proto.url


def returning_from_google(monkeypatch, **params) -> AppTest:
    """A brand-new session, as when Google sends the user back to the app."""
    monkeypatch.setenv("CERBERUS_DEMO", "1")
    app = AppTest.from_file(APP, default_timeout=10)
    for name, value in params.items():
        app.query_params[name] = value
    app.run()
    assert not app.exception
    return app


def test_continue_with_google_signs_in_on_return(at, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    link = google_link(at)
    assert urlparse(link).path == "/"  # Supabase's "<app url>/**" allow list needs the slash
    params = {k: v[0] for k, v in parse_qs(urlparse(link).query).items()}
    assert set(params) == {"flow", "code", "remember"}
    assert params["remember"] == "1"  # "Keep me signed in" is ticked by default

    back = returning_from_google(monkeypatch, **params)
    assert "Google User's life list" in headers(back)
    assert not back.query_params  # the one-time code is cleared from the address bar
    assert back.session_state["remember"] is True
    assert saved_cookie_scripts(back)


def test_google_link_is_reused_across_reruns(at):
    first = google_link(at)
    at.run()
    assert google_link(at) == first


def test_unknown_google_flow_shows_a_message(monkeypatch):
    back = returning_from_google(monkeypatch, flow="made-up", code="demo-123")
    assert "expired" in back.info[0].value
    assert not back.header


def test_cancelled_google_sign_in_shows_a_message(monkeypatch):
    back = returning_from_google(monkeypatch, error="access_denied")
    assert "cancelled" in back.info[0].value



# --- Keep me signed in ----------------------------------------------------------------
# AppTest can't send cookies, so returning visits are covered by the backend tests;
# these check the checkbox and that the app writes (or doesn't write) the cookie.

def saved_cookie_scripts(at: AppTest) -> list[str]:
    from cerberus.remember import COOKIE_NAME

    return [h.proto.body for h in at.get("html")
            if COOKIE_NAME in h.proto.body and "Max-Age=0" not in h.proto.body]


def test_keep_me_signed_in_is_ticked_by_default(at):
    assert at.checkbox(key="keep_signed_in").value is True


def test_signing_in_saves_the_sign_in_to_a_cookie(at):
    sign_up(at)
    assert at.session_state["remember"] is True
    assert len(saved_cookie_scripts(at)) == 1


def test_unticking_keep_me_signed_in_saves_nothing(at):
    at.checkbox(key="keep_signed_in").uncheck().run()
    sign_up(at)
    assert "charlie's life list" in headers(at)
    assert not saved_cookie_scripts(at)


def test_unticking_updates_the_google_link(at):
    from urllib.parse import parse_qs, urlparse

    at.checkbox(key="keep_signed_in").uncheck().run()
    assert parse_qs(urlparse(google_link(at)).query)["remember"] == ["0"]


def test_signing_out_deletes_the_cookie(at):
    sign_up(at)
    click(at, "Sign out")
    assert any("Max-Age=0" in h.proto.body for h in at.get("html"))


# --- Settings: What's new, Coming next, +1 votes and suggestions -----------------------

def vote_buttons(at: AppTest):
    return [b for b in at.button if b.key and b.key.startswith("vote_")]


def test_settings_shows_the_version_and_latest_update(at):
    from cerberus import logic

    sign_up(at)
    latest = logic.parse_changelog(logic.CHANGELOG_MD.read_text(encoding="utf-8"))[0]
    assert f"Version {latest.version}" in [c.value for c in at.caption]
    assert any(f"Version {latest.version}: {latest.title}" in m.value for m in at.markdown)
    assert "Earlier updates" in [e.label for e in at.expander]


def test_coming_next_lists_roadmap_features_with_a_plus_one_each(at):
    from cerberus import logic

    sign_up(at)
    upcoming = logic.upcoming_features(logic.ROADMAP_MD.read_text(encoding="utf-8"))
    assert [b.key for b in vote_buttons(at)] == [f"vote_{i.key}" for i in upcoming]
    assert all(b.label == "+1 · 0" for b in vote_buttons(at))


def test_plus_one_toggles_on_and_off(at):
    sign_up(at)
    key = vote_buttons(at)[0].key
    at.button(key=key).click().run()
    assert not at.exception
    assert at.button(key=key).label == "+1 · 1"
    assert at.button(key=key).proto.type == "primary"  # highlighted: you've voted

    at.button(key=key).click().run()
    assert at.button(key=key).label == "+1 · 0"


def test_suggesting_a_feature(at):
    sign_up(at)
    at.text_area(key="feature_suggestion").input("Badges for streaks")
    click(at, "Send idea")
    assert "Thanks" in at.success[-1].value
    assert at.session_state["backend"].suggestions[0]["suggestion"] == "Badges for streaks"


def test_empty_suggestion_is_rejected(at):
    sign_up(at)
    click(at, "Send idea")
    assert "Write your idea first" in at.error[0].value