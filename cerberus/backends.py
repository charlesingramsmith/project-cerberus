"""Where accounts and sightings live.

- SupabaseBackend: the real thing. Supabase Auth handles accounts and passwords,
  and Postgres row-level security means each user can only touch their own rows.
- MemoryBackend: a stand-in used for tests and for "demo mode" when no Supabase
  keys are configured. Everything is lost when the session ends.

Each Streamlit browser session gets its own backend instance, so one user's
sign-in is never shared with another's.
"""
from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    """A sign-in or sign-up problem that's safe to show the user."""


@dataclass(frozen=True)
class User:
    id: str
    email: str
    username: str


class Backend(Protocol):
    demo: bool

    def sign_up(self, email: str, password: str, username: str) -> User | None:
        """Create an account. Returns the signed-in user, or None if email confirmation is needed."""

    def sign_in(self, email: str, password: str) -> User: ...
    def sign_out(self) -> None: ...
    def list_sightings(self) -> list[dict]: ...

    def add_sighting(self, breed: str, seen_on: date, location: str | None = None,
                     dog_name: str | None = None, notes: str | None = None) -> None: ...

    def delete_sighting(self, sighting_id: int) -> None: ...


def validate_sign_up(email: str, password: str, username: str) -> tuple[str, str]:
    """Check sign-up input and return the cleaned (email, username)."""
    email, username = email.strip().lower(), username.strip()
    if not EMAIL_RE.match(email):
        raise AuthError("That doesn't look like a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if not 3 <= len(username) <= 30:
        raise AuthError("Username must be 3 to 30 characters.")
    return email, username


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _sighting_row(breed: str, seen_on: date, location, dog_name, notes) -> dict:
    return {
        "breed": breed,
        "seen_on": seen_on.isoformat(),
        "location": _clean(location),
        "dog_name": _clean(dog_name),
        "notes": _clean(notes),
    }


# --- Supabase ---------------------------------------------------------------------

class SupabaseBackend:
    demo = False

    def __init__(self, url: str, key: str):
        from supabase import create_client  # imported here so tests don't need network

        self.client = create_client(url, key)
        self._user: User | None = None

    @staticmethod
    def _to_user(sb_user) -> User:
        username = (sb_user.user_metadata or {}).get("username") or sb_user.email.split("@")[0]
        return User(id=sb_user.id, email=sb_user.email, username=username)

    def _require_user(self) -> User:
        if self._user is None:
            raise AuthError("Please sign in first.")
        # get_session() refreshes an expired access token (they last an hour), and the
        # client then sends the fresh token with database queries automatically.
        if self.client.auth.get_session() is None:
            self._user = None
            raise AuthError("Your session has expired. Please sign in again.")
        return self._user

    def sign_up(self, email, password, username):
        email, username = validate_sign_up(email, password, username)
        try:
            res = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {"data": {"username": username}},
            })
        except Exception as err:  # supabase raises several error types; show its message
            raise AuthError(getattr(err, "message", str(err))) from err
        if res.session is None:
            return None  # Supabase sent a confirmation email
        self._user = self._to_user(res.user)
        return self._user

    def sign_in(self, email, password):
        try:
            res = self.client.auth.sign_in_with_password(
                {"email": email.strip().lower(), "password": password}
            )
        except Exception as err:
            raise AuthError(getattr(err, "message", str(err))) from err
        self._user = self._to_user(res.user)
        return self._user

    def sign_out(self):
        try:
            self.client.auth.sign_out()
        finally:
            self._user = None

    def list_sightings(self):
        self._require_user()
        res = (
            self.client.table("sightings")
            .select("id, breed, seen_on, location, dog_name, notes")
            .order("seen_on", desc=True)
            .order("id", desc=True)
            .execute()
        )
        return res.data

    def add_sighting(self, breed, seen_on, location=None, dog_name=None, notes=None):
        user = self._require_user()
        row = _sighting_row(breed, seen_on, location, dog_name, notes)
        self.client.table("sightings").insert({**row, "user_id": user.id}).execute()

    def delete_sighting(self, sighting_id):
        self._require_user()
        self.client.table("sightings").delete().eq("id", sighting_id).execute()


# --- In-memory (tests and demo mode) ---------------------------------------------

class MemoryBackend:
    demo = True

    def __init__(self):
        self._accounts: dict[str, tuple[str, User]] = {}  # email -> (password hash, user)
        self._sightings: list[dict] = []
        self._ids = itertools.count(1)
        self._user: User | None = None

    @staticmethod
    def _hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _require_user(self) -> User:
        if self._user is None:
            raise AuthError("Please sign in first.")
        return self._user

    def sign_up(self, email, password, username):
        email, username = validate_sign_up(email, password, username)
        if email in self._accounts:
            raise AuthError("An account with that email already exists.")
        user = User(id=f"user-{len(self._accounts) + 1}", email=email, username=username)
        self._accounts[email] = (self._hash(password), user)
        self._user = user
        return user

    def sign_in(self, email, password):
        account = self._accounts.get(email.strip().lower())
        if account is None or account[0] != self._hash(password):
            raise AuthError("Invalid login credentials")
        self._user = account[1]
        return self._user

    def sign_out(self):
        self._user = None

    def list_sightings(self):
        user = self._require_user()
        mine = [{k: v for k, v in s.items() if k != "user_id"}
                for s in self._sightings if s["user_id"] == user.id]
        return sorted(mine, key=lambda s: (s["seen_on"], s["id"]), reverse=True)

    def add_sighting(self, breed, seen_on, location=None, dog_name=None, notes=None):
        user = self._require_user()
        row = _sighting_row(breed, seen_on, location, dog_name, notes)
        self._sightings.append({"id": next(self._ids), "user_id": user.id, **row})

    def delete_sighting(self, sighting_id):
        user = self._require_user()
        self._sightings = [s for s in self._sightings
                           if not (s["id"] == sighting_id and s["user_id"] == user.id)]
