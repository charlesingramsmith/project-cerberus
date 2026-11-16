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
