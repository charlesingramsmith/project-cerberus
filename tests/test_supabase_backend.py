"""SupabaseBackend tests against a small fake client (no network needed)."""
from datetime import date
from types import SimpleNamespace

import pytest

from cerberus.backends import AuthError, SupabaseBackend


class FakeQuery:
    def __init__(self, log):
        self.log = log

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.log.append((name, args, kwargs))
            return self
        return call

    def execute(self):
        return SimpleNamespace(data=[])


class FakeAuth:
    def __init__(self, needs_confirmation=False):
        self.needs_confirmation = needs_confirmation
        self.session = None

    def _response(self, email, metadata):
        user = SimpleNamespace(id="uuid-1", email=email, user_metadata=metadata)
        self.session = None if self.needs_confirmation else object()
        return SimpleNamespace(user=user, session=self.session)

    def sign_up(self, creds):
        return self._response(creds["email"], creds["options"]["data"])

    def sign_in_with_password(self, creds):
        if creds["password"] != "correct-horse":
            raise RuntimeError("Invalid login credentials")
        return self._response(creds["email"], {"username": "charlie"})

    def get_session(self):
        return self.session

    def sign_out(self):
        self.session = None


def make_backend(**auth_kwargs) -> tuple[SupabaseBackend, list]:
    log: list = []
    backend = SupabaseBackend.__new__(SupabaseBackend)
    backend.client = SimpleNamespace(auth=FakeAuth(**auth_kwargs), table=lambda name: FakeQuery(log))
    backend._user = None
    return backend, log


def test_sign_up_stores_username_and_signs_in():
    backend, _ = make_backend()
    user = backend.sign_up("Charlie@Example.com", "correct-horse", "charlie")
    assert user.username == "charlie"
    assert user.email == "charlie@example.com"


def test_sign_up_needing_email_confirmation_returns_none():
    backend, _ = make_backend(needs_confirmation=True)
    assert backend.sign_up("charlie@example.com", "correct-horse", "charlie") is None


def test_supabase_errors_become_auth_errors():
    backend, _ = make_backend()
    with pytest.raises(AuthError, match="Invalid login"):
        backend.sign_in("charlie@example.com", "nope")


def test_add_sighting_sends_cleaned_row_with_user_id():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.add_sighting("Pug", date(2026, 11, 1), location=" Park ", dog_name="", notes=None)

    insert = next(args[0] for name, args, _ in log if name == "insert")
    assert insert == {"breed": "Pug", "seen_on": "2026-11-01", "location": "Park",
                      "dog_name": None, "notes": None, "user_id": "uuid-1"}


def test_expired_session_asks_user_to_sign_in_again():
    backend, _ = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.client.auth.session = None  # simulate a refresh token that has expired
    with pytest.raises(AuthError, match="expired"):
        backend.list_sightings()
