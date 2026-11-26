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
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from cerberus import logic
from cerberus.logic import MAX_USERNAME_LENGTH, USERNAME_TAKEN, clean_suggestion
from cerberus.oauth import with_query

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
FEED_LIMIT = 50  # sightings shown in the Social tab
GOOGLE_FAILED = "Google sign-in didn't work. Please try again."
RESUME_FAILED = "You've been signed out. Please sign in again."
RESET_LINK_FAILED = ("That password reset link has expired or was already used. "
                     "Please ask for a new one.")


class AuthError(Exception):
    """A sign-in or sign-up problem that's safe to show the user."""


@dataclass(frozen=True)
class User:
    id: str
    email: str
    username: str


class Backend(Protocol):
    demo: bool
    # True once my_profile() has just made this user's profile (their first visit), so the
    # app can explain sharing. The app sets it back to False after showing that.
    profile_is_new: bool

    def sign_up(self, email: str, password: str, username: str) -> User | None:
        """Create an account. Returns the signed-in user, or None if email confirmation is needed."""

    def sign_in(self, email: str, password: str) -> User: ...

    def start_google_sign_in(self, redirect_to: str) -> tuple[str, str]:
        """Begin "Continue with Google". Returns (Google sign-in URL, PKCE code verifier).

        Google sends the user back to `redirect_to` with `code=...` added.
        """

    def finish_google_sign_in(self, code: str, verifier: str) -> User:
        """Swap the code Google sent back (plus the verifier) for a signed-in user."""

    def refresh_token(self) -> str | None:
        """The signed-in user's current refresh token (for "Keep me signed in"), or None."""

    def resume_session(self, refresh_token: str) -> User:
        """Sign back in with a saved refresh token. Raises AuthError if it's no longer valid."""

    def sign_out(self) -> None:
        """Sign out on this device only; other devices stay signed in."""

    def send_password_reset(self, email: str, redirect_to: str) -> None:
        """Email a link for choosing a new password ("Forgot your password?").

        The link brings the user back to `redirect_to` with `?token_hash=...&type=recovery`.
        Nothing says whether an account exists for that email, so this can't be used to
        find out who's a member. Raises AuthError for a badly formed email address.
        """

    def finish_password_reset(self, token_hash: str) -> User:
        """Sign in with the token from a reset link, so the user can choose a new password.
        Each link works once. Raises AuthError if it's expired or used."""

    def change_password(self, new_password: str) -> None:
        """Set a new password for the signed-in user. Raises AuthError if it's too short."""

    def list_sightings(self) -> list[dict]: ...

    def add_sighting(self, breed: str, seen_on: date, location: str | None = None,
                     dog_name: str | None = None, notes: str | None = None) -> None: ...

    def delete_sighting(self, sighting_id: int) -> None: ...

    def feature_vote_counts(self) -> dict[str, int]:
        """Total +1 votes per upcoming feature, from all users (no names)."""

    def my_feature_votes(self) -> set[str]:
        """The features the signed-in user has given a +1."""

    def set_feature_vote(self, feature: str, voted: bool) -> None:
        """Add (voted=True) or remove the signed-in user's +1 for a feature."""

    def suggest_feature(self, suggestion: str) -> None:
        """Send a feature idea. Raises ValueError if it's empty or too long."""

    def seen_version(self) -> str | None:
        """The newest app update (e.g. "0.6.0") the signed-in user has seen, or None."""

    def mark_version_seen(self, version: str) -> None:
        """Remember that the signed-in user has seen this update (clears the Settings dot)."""

    def my_profile(self) -> dict:
        """The signed-in user's profile, created on first use from their sign-up username.

        If that username is taken, a number is added ("charlie2").
        """

    def save_profile(self, profile: dict) -> dict:
        """Check and save the signed-in user's profile; returns what was saved.

        Raises ValueError for bad input or a username someone else has.
        """

    def social_feed(self, limit: int = FEED_LIMIT) -> list[dict]:
        """Recent sightings from everyone who shares (including you), newest first,
        each with the spotter's username and avatar."""


def _is_duplicate(err: Exception) -> bool:
    """True if Postgres refused a row because a unique value (a username) is taken."""
    return getattr(err, "code", None) == "23505"


def validate_email(email: str) -> str:
    """Check an email address and return it cleaned (trimmed, lower case)."""
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("That doesn't look like a valid email address.")
    return email


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")


def validate_sign_up(email: str, password: str, username: str) -> tuple[str, str]:
    """Check sign-up input and return the cleaned (email, username)."""
    email, username = validate_email(email), username.strip()
    validate_password(password)
    if not 3 <= len(username) <= MAX_USERNAME_LENGTH:
        raise AuthError(f"Username must be 3 to {MAX_USERNAME_LENGTH} characters.")
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
    profile_is_new = False  # a class default, so backends from before a deploy have it too

    def __init__(self, url: str, key: str):
        from supabase import create_client  # imported here so tests don't need network

        self.client = create_client(url, key)
        self._user: User | None = None
        self._meta: dict = {}  # the signed-in user's Supabase user_metadata

    def _keep(self, sb_user) -> User:
        """Remember who just signed in (and their metadata), and return them as a User."""
        self._meta = dict(sb_user.user_metadata or {})
        return self._to_user(sb_user)

    @staticmethod
    def _to_user(sb_user) -> User:
        meta = sb_user.user_metadata or {}
        # Email sign-ups choose a username; Google accounts bring their name instead.
        username = (meta.get("username") or meta.get("full_name") or meta.get("name")
                    or sb_user.email.split("@")[0])
        return User(id=sb_user.id, email=sb_user.email, username=username[:MAX_USERNAME_LENGTH])

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
        self._user = self._keep(res.user)
        return self._user

    def sign_in(self, email, password):
        try:
            res = self.client.auth.sign_in_with_password(
                {"email": email.strip().lower(), "password": password}
            )
        except Exception as err:
            raise AuthError(getattr(err, "message", str(err))) from err
        self._user = self._keep(res.user)
        return self._user

    def start_google_sign_in(self, redirect_to):
        auth = self.client.auth
        res = auth.sign_in_with_oauth(
            {"provider": "google", "options": {"redirect_to": redirect_to}}
        )
        # The client keeps the verifier it just made in its own storage, but that storage
        # dies with this Streamlit session, so hand it to the caller to keep safe.
        verifier = auth._storage.get_item(f"{auth._storage_key}-code-verifier")
        return res.url, verifier

    def finish_google_sign_in(self, code, verifier):
        try:
            res = self.client.auth.exchange_code_for_session(
                {"auth_code": code, "code_verifier": verifier}
            )
        except Exception as err:
            raise AuthError(GOOGLE_FAILED) from err
        self._user = self._keep(res.user)
        return self._user

    def refresh_token(self):
        if self._user is None:
            return None
        try:
            session = self.client.auth.get_session()
        except Exception:
            return None
        return session.refresh_token if session else None

    def resume_session(self, refresh_token):
        try:
            res = self.client.auth.refresh_session(refresh_token)
        except Exception as err:  # used, revoked or unknown token
            raise AuthError(RESUME_FAILED) from err
        self._user = self._keep(res.user)
        return self._user

    def sign_out(self):
        try:
            # "local" ends just this device's session (and cancels its refresh token),
            # so signing out on a phone doesn't also sign you out on your laptop.
            self.client.auth.sign_out({"scope": "local"})
        finally:
            self._user = None

    # Password reset. Supabase emails a link; its "Reset Password" email template must
    # point the link at this app with the token in the address (see
    # docs/password-reset.md), so the app can check it with verify_otp. That works on
    # any device, even if the server restarted in between, unlike the PKCE code that
    # Google sign-in uses (whose secret only lives in this server's memory).
    def send_password_reset(self, email, redirect_to):
        email = validate_email(email)
        try:
            self.client.auth.reset_password_for_email(email, {"redirect_to": redirect_to})
        except Exception as err:  # e.g. "email rate limit exceeded"
            raise AuthError(getattr(err, "message", str(err))) from err

    def finish_password_reset(self, token_hash):
        try:
            res = self.client.auth.verify_otp({"token_hash": token_hash, "type": "recovery"})
        except Exception as err:
            raise AuthError(RESET_LINK_FAILED) from err
        if res.user is None:
            raise AuthError(RESET_LINK_FAILED)
        self._user = self._keep(res.user)
        return self._user

    def change_password(self, new_password):
        validate_password(new_password)
        self._require_user()
        try:
            self.client.auth.update_user({"password": new_password})
        except Exception as err:  # e.g. "New password should be different from the old password."
            raise AuthError(getattr(err, "message", str(err))) from err

    def list_sightings(self):
        user = self._require_user()
        res = (
            self.client.table("sightings")
            .select("id, breed, seen_on, location, dog_name, notes")
            # RLS also lets members read other people's shared sightings (for Social),
            # so ask for this user's own rows explicitly.
            .eq("user_id", user.id)
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

    def feature_vote_counts(self):
        self._require_user()
        res = self.client.rpc("feature_vote_counts").execute()  # see supabase/schema.sql
        return {row["feature"]: int(row["votes"]) for row in res.data}

    def my_feature_votes(self):
        user = self._require_user()
        res = (self.client.table("feature_votes").select("feature")
               .eq("user_id", user.id).execute())
        return {row["feature"] for row in res.data}

    def set_feature_vote(self, feature, voted):
        user = self._require_user()
        votes = self.client.table("feature_votes")
        if voted:
            # Voting twice is harmless: the (user_id, feature) key already exists, so skip it.
            votes.upsert({"user_id": user.id, "feature": feature},
                         on_conflict="user_id,feature", ignore_duplicates=True).execute()
        else:
            votes.delete().eq("user_id", user.id).eq("feature", feature).execute()

    def suggest_feature(self, suggestion):
        user = self._require_user()
        text = clean_suggestion(suggestion)
        self.client.table("feature_suggestions").insert(
            {"suggestion": text, "user_id": user.id}).execute()

    # The last update a user has seen lives in their Supabase user_metadata, so no table
    # is needed and it follows them to every device. Supabase merges `data` into the
    # existing metadata, so the username is kept.
    def seen_version(self):
        self._require_user()
        return self._meta.get("seen_version")

    def mark_version_seen(self, version):
        self._require_user()
        self.client.auth.update_user({"data": {"seen_version": version}})
        self._meta = {**self._meta, "seen_version": version}

    PROFILE_COLUMNS = "username, avatar, favourite_breed, dogs, share_sightings"

    def my_profile(self):
        user = self._require_user()
        profiles = self.client.table("profiles")
        rows = profiles.select(self.PROFILE_COLUMNS).eq("user_id", user.id).execute().data
        if rows:
            return rows[0]
        for name in logic.username_candidates(user.username):  # first visit: make one
            profile = logic.new_profile(name)
            try:
                profiles.insert({**profile, "user_id": user.id}).execute()
                self.profile_is_new = True
                return profile
            except Exception as err:
                if not _is_duplicate(err):
                    raise
        raise ValueError(USERNAME_TAKEN)

    def save_profile(self, profile):
        user = self._require_user()
        clean = logic.clean_profile(profile)
        try:
            self.client.table("profiles").update(clean).eq("user_id", user.id).execute()
        except Exception as err:
            if _is_duplicate(err):
                raise ValueError(USERNAME_TAKEN) from err
            raise
        return clean

    def social_feed(self, limit=FEED_LIMIT):
        self._require_user()
        # RLS returns your own sightings plus those of members who share.
        rows = (self.client.table("sightings")
                .select("id, user_id, breed, seen_on, location, dog_name, notes")
                .order("seen_on", desc=True).order("id", desc=True).limit(limit)
                .execute().data)
        ids = sorted({r["user_id"] for r in rows})
        profiles = (self.client.table("profiles")
                    .select("user_id, username, avatar, share_sightings")
                    .in_("user_id", ids).execute().data) if ids else []
        return logic.social_feed(rows, {p["user_id"]: p for p in profiles})


# --- In-memory (tests and demo mode) ---------------------------------------------

class MemoryBackend:
    demo = True
    profile_is_new = False

    def __init__(self):
        # email -> (password hash, or None for Google-only accounts; user)
        self._accounts: dict[str, tuple[str | None, User]] = {}
        self._sightings: list[dict] = []
        self._ids = itertools.count(1)
        self._user: User | None = None
        # Single-use refresh tokens, like Supabase's: token -> email.
        self._tokens: dict[str, str] = {}
        self._token: str | None = None
        self._votes: set[tuple[str, str]] = set()  # (user id, feature)
        self.suggestions: list[dict] = []
        self._seen: dict[str, str] = {}  # user id -> newest update they've seen
        self._profiles: dict[str, dict] = {}  # user id -> profile
        # Password reset: single-use tokens (token -> email), and the "emails" that
        # would have been sent, as (to, link), since demo mode can't send real ones.
        self._reset_tokens: dict[str, str] = {}
        self.sent_emails: list[tuple[str, str]] = []

    @staticmethod
    def _hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _signed_in(self, user: User) -> User:
        """Mark `user` as signed in and give them a fresh refresh token."""
        self._tokens.pop(self._token, None)
        self._token = secrets.token_urlsafe(16)
        self._tokens[self._token] = user.email
        self._user = user
        return user

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
        return self._signed_in(user)

    def sign_in(self, email, password):
        account = self._accounts.get(email.strip().lower())
        if account is None or account[0] != self._hash(password):
            raise AuthError("Invalid login credentials")
        return self._signed_in(account[1])

    # Demo mode can't reach Google, so it pretends: the "Google" URL sends the user straight
    # back with a code derived from the verifier, which is checked just like the real thing.
    DEMO_GOOGLE_EMAIL = "demo.google.user@example.com"

    @staticmethod
    def _demo_code(verifier: str) -> str:
        return "demo-" + hashlib.sha256(verifier.encode()).hexdigest()[:16]

    def start_google_sign_in(self, redirect_to):
        verifier = secrets.token_urlsafe(32)
        return with_query(redirect_to, code=self._demo_code(verifier)), verifier

    def finish_google_sign_in(self, code, verifier):
        if code != self._demo_code(verifier):
            raise AuthError(GOOGLE_FAILED)
        email = self.DEMO_GOOGLE_EMAIL
        if email not in self._accounts:  # first time: Google sign-in creates the account
            user = User(id=f"user-{len(self._accounts) + 1}", email=email, username="Google User")
            self._accounts[email] = (None, user)  # no password, so password sign-in can't match
        return self._signed_in(self._accounts[email][1])

    def refresh_token(self):
        return self._token if self._user else None

    def resume_session(self, refresh_token):
        email = self._tokens.pop(refresh_token, None)  # single use, like Supabase's
        if email is None or email not in self._accounts:
            raise AuthError(RESUME_FAILED)
        self._token = None
        return self._signed_in(self._accounts[email][1])

    def sign_out(self):
        self._tokens.pop(self._token, None)
        self._token = None
        self._user = None

    def send_password_reset(self, email, redirect_to):
        email = validate_email(email)
        if email not in self._accounts:  # like Supabase: no email, and no error either
            return
        token = secrets.token_urlsafe(16)
        self._reset_tokens[token] = email
        self.sent_emails.append(
            (email, with_query(redirect_to, token_hash=token, type="recovery")))

    def finish_password_reset(self, token_hash):
        email = self._reset_tokens.pop(token_hash, None)  # each link works once
        if email is None:
            raise AuthError(RESET_LINK_FAILED)
        return self._signed_in(self._accounts[email][1])

    def change_password(self, new_password):
        validate_password(new_password)
        user = self._require_user()
        self._accounts[user.email] = (self._hash(new_password), user)

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

    def feature_vote_counts(self):
        self._require_user()
        return dict(Counter(feature for _, feature in self._votes))

    def my_feature_votes(self):
        user = self._require_user()
        return {feature for user_id, feature in self._votes if user_id == user.id}

    def set_feature_vote(self, feature, voted):
        user = self._require_user()
        if voted:
            self._votes.add((user.id, feature))
        else:
            self._votes.discard((user.id, feature))

    def suggest_feature(self, suggestion):
        user = self._require_user()
        self.suggestions.append({"user_id": user.id, "suggestion": clean_suggestion(suggestion)})

    def seen_version(self):
        return self._seen.get(self._require_user().id)

    def mark_version_seen(self, version):
        self._seen[self._require_user().id] = version

    def _username_taken(self, username: str, by_someone_but: str) -> bool:
        return any(p["username"].lower() == username.lower()
                   for uid, p in self._profiles.items() if uid != by_someone_but)

    def my_profile(self):
        user = self._require_user()
        if user.id not in self._profiles:
            name = next(n for n in logic.username_candidates(user.username)
                        if not self._username_taken(n, user.id))
            self._profiles[user.id] = logic.new_profile(name)
            self.profile_is_new = True
        return dict(self._profiles[user.id])

    def save_profile(self, profile):
        user = self._require_user()
        clean = logic.clean_profile(profile)
        if self._username_taken(clean["username"], user.id):
            raise ValueError(USERNAME_TAKEN)
        self._profiles[user.id] = clean
        return dict(clean)

    def social_feed(self, limit=FEED_LIMIT):
        user = self._require_user()
        visible = [s for s in self._sightings  # like RLS: your own, plus anyone who shares
                   if s["user_id"] == user.id
                   or self._profiles.get(s["user_id"], {}).get("share_sightings")]
        newest = sorted(visible, key=lambda s: (s["seen_on"], s["id"]), reverse=True)[:limit]
        return logic.social_feed(newest, self._profiles)
