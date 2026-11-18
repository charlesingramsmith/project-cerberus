"""Tests for the in-memory backend, which mirrors the Supabase backend's behaviour."""
from datetime import date

import pytest

from cerberus.backends import AuthError, MemoryBackend, validate_sign_up


@pytest.fixture
def backend():
    return MemoryBackend()


@pytest.mark.parametrize("email, password, username", [
    ("not-an-email", "longenough", "charlie"),
    ("a@b.com", "short", "charlie"),
    ("a@b.com", "longenough", "ab"),
    ("a@b.com", "longenough", "x" * 31),
])
def test_sign_up_validation_rejects_bad_input(email, password, username):
    with pytest.raises(AuthError):
        validate_sign_up(email, password, username)


def test_sign_up_normalises_email():
    assert validate_sign_up("  Charlie@Example.COM ", "longenough", " charlie ") == (
        "charlie@example.com", "charlie")


def test_sign_up_then_sign_in(backend):
    user = backend.sign_up("charlie@example.com", "correct-horse", "charlie")
    assert user.username == "charlie"
    backend.sign_out()

    with pytest.raises(AuthError):
        backend.sign_in("charlie@example.com", "wrong-password")
    assert backend.sign_in("Charlie@example.com", "correct-horse") == user


def test_duplicate_email_rejected(backend):
    backend.sign_up("charlie@example.com", "correct-horse", "charlie")
    with pytest.raises(AuthError):
        backend.sign_up("charlie@example.com", "another-pass", "charlie2")


def test_data_requires_sign_in(backend):
    with pytest.raises(AuthError):
        backend.list_sightings()
    with pytest.raises(AuthError):
        backend.add_sighting("Pug", date(2026, 11, 1))


def test_sightings_are_private_to_each_user(backend):
    backend.sign_up("alice@example.com", "password-a", "alice")
    backend.add_sighting("Pug", date(2026, 11, 1), location="  Park ", notes="")
    alice_sighting = backend.list_sightings()[0]
    assert alice_sighting["location"] == "Park"
    assert alice_sighting["notes"] is None
    backend.sign_out()

    backend.sign_up("bob@example.com", "password-b", "bob")
    assert backend.list_sightings() == []
    backend.delete_sighting(alice_sighting["id"])  # bob can't delete alice's sighting
    backend.sign_out()

    backend.sign_in("alice@example.com", "password-a")
    assert len(backend.list_sightings()) == 1
    backend.delete_sighting(alice_sighting["id"])
    assert backend.list_sightings() == []


def test_sightings_listed_newest_first(backend):
    backend.sign_up("charlie@example.com", "correct-horse", "charlie")
    backend.add_sighting("Pug", date(2026, 11, 1))
    backend.add_sighting("Beagle", date(2026, 11, 5))
    assert [s["breed"] for s in backend.list_sightings()] == ["Beagle", "Pug"]


# --- Continue with Google (demo mode pretends to be Google) -------------------------

def google_round_trip(backend, tamper=False):
    from urllib.parse import parse_qs, urlparse

    url, verifier = backend.start_google_sign_in("https://app.example/?flow=abc")
    params = parse_qs(urlparse(url).query)
    assert params["flow"] == ["abc"]  # the return address is kept intact
    code = params["code"][0] + ("x" if tamper else "")
    return backend.finish_google_sign_in(code, verifier)


def test_google_sign_in_creates_an_account_and_signs_in(backend):
    user = google_round_trip(backend)
    assert user.username == "Google User"
    backend.add_sighting("Pug", date(2026, 11, 1))
    assert len(backend.list_sightings()) == 1


def test_google_sign_in_again_is_the_same_account(backend):
    first = google_round_trip(backend)
    backend.sign_out()
    assert google_round_trip(backend) == first


def test_google_sign_in_rejects_a_wrong_code(backend):
    with pytest.raises(AuthError, match="Google"):
        google_round_trip(backend, tamper=True)


def test_google_accounts_have_no_password(backend):
    google_round_trip(backend)
    backend.sign_out()
    with pytest.raises(AuthError):
        backend.sign_in(MemoryBackend.DEMO_GOOGLE_EMAIL, "anything-at-all")


# --- Keep me signed in ----------------------------------------------------------------

def test_refresh_token_only_while_signed_in(backend):
    assert backend.refresh_token() is None
    backend.sign_up("a@example.com", "longenough", "alice")
    assert backend.refresh_token()
    backend.sign_out()
    assert backend.refresh_token() is None


def test_resume_session_signs_back_in_and_rotates_the_token(backend):
    user = backend.sign_up("a@example.com", "longenough", "alice")
    saved = backend.refresh_token()
    backend._user = None  # as if the tab closed (the demo backend keeps its accounts)
    assert backend.resume_session(saved) == user
    assert backend.refresh_token() not in (None, saved)
    backend.list_sightings()  # signed in again


def test_refresh_tokens_are_single_use(backend):
    backend.sign_up("a@example.com", "longenough", "alice")
    saved = backend.refresh_token()
    backend.resume_session(saved)
    with pytest.raises(AuthError):
        backend.resume_session(saved)


def test_sign_out_cancels_the_saved_token(backend):
    backend.sign_up("a@example.com", "longenough", "alice")
    saved = backend.refresh_token()
    backend.sign_out()
    with pytest.raises(AuthError):
        backend.resume_session(saved)


def test_unknown_token_is_rejected(backend):
    with pytest.raises(AuthError):
        backend.resume_session("made-up")


# --- Feature votes and suggestions ----------------------------------------------------

def test_feature_votes_count_everyone_but_track_your_own(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.set_feature_vote("photo-upload", True)
    backend.set_feature_vote("photo-upload", True)  # voting twice still counts once
    backend.sign_out()
    backend.sign_up("b@example.com", "correct-horse", "bobby")
    backend.set_feature_vote("photo-upload", True)
    backend.set_feature_vote("password-reset", True)

    assert backend.feature_vote_counts() == {"photo-upload": 2, "password-reset": 1}
    assert backend.my_feature_votes() == {"photo-upload", "password-reset"}

    backend.set_feature_vote("photo-upload", False)
    assert backend.feature_vote_counts() == {"photo-upload": 1, "password-reset": 1}
    assert backend.my_feature_votes() == {"password-reset"}


def test_suggestions_are_cleaned_and_validated(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.suggest_feature("  Badges for streaks  ")
    assert backend.suggestions == [{"user_id": "user-1", "suggestion": "Badges for streaks"}]
    with pytest.raises(ValueError):
        backend.suggest_feature("   ")


def test_votes_and_suggestions_need_a_sign_in(backend):
    for call in (backend.feature_vote_counts, backend.my_feature_votes,
                 lambda: backend.set_feature_vote("x", True),
                 lambda: backend.suggest_feature("idea")):
        with pytest.raises(AuthError):
            call()

def test_seen_version_is_remembered_per_user(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    assert backend.seen_version() is None
    backend.mark_version_seen("0.7.0")
    backend.sign_out()
    backend.sign_up("b@example.com", "correct-horse", "bobby")
    assert backend.seen_version() is None  # Bobby hasn't seen it
    backend.sign_out()
    backend.sign_in("a@example.com", "correct-horse")
    assert backend.seen_version() == "0.7.0"
    with pytest.raises(AuthError):
        MemoryBackend().seen_version()