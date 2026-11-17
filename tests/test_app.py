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
    assert at.header[0].value == "charlie's life list"
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

    params = {k: v[0] for k, v in parse_qs(urlparse(google_link(at)).query).items()}
    assert set(params) == {"flow", "code"}

    back = returning_from_google(monkeypatch, **params)
    assert back.header[0].value == "Google User's life list"
    assert not back.query_params  # the one-time code is cleared from the address bar


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
