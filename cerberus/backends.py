"""Where accounts and sightings live.

- SupabaseBackend: the real thing. Supabase Auth handles accounts and passwords,
  and Postgres row-level security means each user can only touch their own rows.
- MemoryBackend: a stand-in used for tests and for "demo mode" when no Supabase
  keys are configured. Everything is lost when the session ends.

Each Streamlit browser session gets its own backend instance, so one user's
sign-in is never shared with another's.
"""
from __future__ import annotations

import base64
import hashlib
import itertools
import re
import secrets
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol

from cerberus import logic
from cerberus.logic import (DOG_USERNAME_TAKEN, MAX_USERNAME_LENGTH, USERNAME_TAKEN,
                            clean_suggestion)
from cerberus.oauth import with_query

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
FEED_LIMIT = 50  # sightings shown in the Social tab
PHOTO_BUCKET = "sighting-photos"  # private Supabase Storage bucket, see supabase/schema.sql
PHOTO_LINK_SECONDS = 3600  # how long a link to view a photo works
GOOGLE_FAILED = "Google sign-in didn't work. Please try again."
RESUME_FAILED = "You've been signed out. Please sign in again."


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

    def sign_up(self, email: str, password: str, username: str,
                birth_year: int | None = None) -> User | None:
        """Create an account. Returns the signed-in user, or None if email confirmation is needed.

        `birth_year` (checked by logic.clean_birth_year) is kept privately with the
        account, never on the profile other members can read.
        """

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

    def list_sightings(self) -> list[dict]:
        """Your own sightings, newest first. Each has `dog_ids`: the dogs tagged in it."""

    def add_sighting(self, breed: str, seen_on: date, location: str | None = None,
                     dog_name: str | None = None, notes: str | None = None,
                     photo_path: str | None = None, dog_ids: list[int] | None = None) -> None:
        """Log a sighting. `photo_path` is what add_photo() returned, if there's a photo;
        `dog_ids` are dog profiles (anyone's) to tag in it."""

    def delete_sighting(self, sighting_id: int) -> None:
        """Delete one of your sightings, and its photo if it has one."""

    def list_user_breeds(self) -> list[str]:
        """Breeds members have added that aren't verified yet (any member's), A to Z.
        Empty if they can't be read (say the table isn't set up yet)."""

    def add_user_breed(self, name: str) -> None:
        """Add a breed that isn't verified to the shared list for the owner to review.
        One that's already there (in any capitals) is left as it is."""

    def add_photo(self, photo: bytes) -> str:
        """Store a sighting photo (a JPEG from logic.prepare_photo) in the signed-in
        user's own folder. Returns its path, to pass to add_sighting()."""

    def photo_urls(self, paths: list[str]) -> dict[str, str]:
        """Links to show photos, by path: your own, dog profile photos, and photos on
        sightings you can see (shared ones). Each works for about an hour. Paths that
        can't be found (or that you may not see) are left out."""

    def list_dogs(self) -> list[dict]:
        """Every member's dog profiles, by username: id, owner_id, owner (their username),
        username, name, breed, bio, photo_path."""

    def add_dog_photo(self, photo: bytes) -> str:
        """Store a dog's profile photo (a JPEG from logic.prepare_photo) in your own
        folder. Returns its path, for the dog's photo_path."""

    def add_dog(self, dog: dict) -> dict:
        """Create a profile for one of your dogs. Raises ValueError for bad input or a
        dog username that's taken. Returns the saved dog, with its id."""

    def update_dog(self, dog_id: int, dog: dict) -> dict:
        """Change one of your dogs' profiles (a replaced photo is deleted)."""

    def delete_dog(self, dog_id: int) -> None:
        """Delete one of your dogs' profiles, its photo, and its tags in posts."""

    def feature_vote_counts(self) -> dict[str, int]:
        """Total +1 votes per upcoming feature, from all users (no names)."""

    def my_feature_votes(self) -> set[str]:
        """The features the signed-in user has given a +1."""

    def set_feature_vote(self, feature: str, voted: bool) -> None:
        """Add (voted=True) or remove the signed-in user's +1 for a feature."""

    def suggest_feature(self, suggestion: str) -> None:
        """Send a feature idea. Raises ValueError if it's empty or too long."""

    def report(self, kind: str, item_id: int, reason: str) -> None:
        """Report a post (kind "sighting") or a dog profile (kind "dog") for the owner to
        review. reason is a key of logic.REPORT_REASONS. Reporting the same thing twice is
        harmless. Raises ValueError for a bad kind or reason, or one that doesn't exist."""

    def my_reports(self) -> dict[str, set[int]]:
        """What the signed-in user has reported: {"sighting": ids, "dog": ids}. Empty if
        reports can't be read (e.g. the table isn't set up yet)."""

    def seen_version(self) -> str | None:
        """The newest app update (e.g. "0.6.0") the signed-in user has seen, or None."""

    def mark_version_seen(self, version: str) -> None:
        """Remember that the signed-in user has seen this update (clears the Settings dot)."""

    def birth_year(self) -> int | None:
        """The year the signed-in user said they were born, or None if never asked."""

    def set_birth_year(self, year: int) -> None:
        """Check and keep the signed-in user's birth year (for Google sign-ups, asked
        after their first sign-in). Raises ValueError for a bad or too-young year."""

    def needs_birth_year(self) -> bool:
        """True for a brand-new member (no profile yet) whose birth year isn't known,
        so the app asks before making their profile. Existing members are never asked."""

    def my_profile(self) -> dict:
        """The signed-in user's profile, created on first use from their sign-up username.

        If that username is taken, a number is added ("charlie2"). A new profile shares
        sightings unless the member may be under 18 (logic.new_profile).
        """

    def save_profile(self, profile: dict) -> dict:
        """Check and save the signed-in user's profile; returns what was saved.

        Raises ValueError for bad input or a username someone else has.
        """

    def social_feed(self, limit: int = FEED_LIMIT) -> list[dict]:
        """Recent sightings from everyone who shares (including you), newest first,
        each with the spotter's username and avatar, its photo_path, its dog_ids and
        "badges": the badges that sighting earned (keys in logic.BADGES_BY_KEY), often
        none."""

    def dog_sightings(self, dog_id: int) -> list[dict]:
        """Every sighting the dog is tagged in that Social would show you (yours while
        you share, and other members' shared ones), newest post first, shaped like
        social_feed posts (without badges)."""


def _listed_breeds() -> set[str]:
    """The verified breeds (logic.badge_progress says what counts towards badges)."""
    return set(logic.load_breeds()["breed"])


def _is_duplicate(err: Exception) -> bool:
    """True if Postgres refused a row because a unique value (a username) is taken."""
    return getattr(err, "code", None) == "23505"


def validate_sign_up(email: str, password: str, username: str) -> tuple[str, str]:
    """Check sign-up input and return the cleaned (email, username)."""
    email, username = email.strip().lower(), username.strip()
    if not EMAIL_RE.match(email):
        raise AuthError("That doesn't look like a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if not 3 <= len(username) <= MAX_USERNAME_LENGTH:
        raise AuthError(f"Username must be 3 to {MAX_USERNAME_LENGTH} characters.")
    return email, username


def _checked_birth_year(year) -> int:
    """logic.clean_birth_year, with its message as an AuthError (as sign-up shows those)."""
    try:
        return logic.clean_birth_year(year)
    except ValueError as err:
        raise AuthError(str(err)) from err


def _known_birth_year(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _sighting_row(breed: str, seen_on: date, location, dog_name, notes,
                  photo_path=None) -> dict:
    row = {
        "breed": _checked_breed(breed),
        "seen_on": seen_on.isoformat(),
        "location": _clean(location),
        "dog_name": _clean(dog_name),
        "notes": _clean(notes),
    }
    if photo_path:  # only sent when there is one, so photo-less logging never needs the column
        row["photo_path"] = photo_path
    return row


def _checked_breed(breed: str) -> str:
    """Breeds are 1 to 100 characters (the app tidies them first with logic.clean_breed)."""
    breed = (breed or "").strip()
    if not 1 <= len(breed) <= logic.MAX_BREED_LENGTH:
        raise ValueError(f"A breed must be 1 to {logic.MAX_BREED_LENGTH} characters.")
    return breed


def _sorted_breeds(names) -> list[str]:
    return sorted(names, key=str.lower)


def _with_tags(rows: list[dict], tags: dict[int, list[int]]) -> list[dict]:
    return [{**r, "dog_ids": tags.get(r["id"], [])} for r in rows]


def _check_photo_path(user: User, path: str) -> None:
    """A sighting may only point at a photo in its owner's own folder."""
    if not path.startswith(f"{user.id}/"):
        raise ValueError("That photo isn't yours.")


# --- Supabase ---------------------------------------------------------------------

class SupabaseBackend:
    demo = False
    profile_is_new = False  # a class default, so backends from before a deploy have it too

    def __init__(self, url: str, key: str):
        from supabase import ClientOptions, create_client  # here so tests don't need network

        # No background refreshing. By default the client swaps its refresh token for a
        # new one every hour on a timer, and that timer keeps going on the server after
        # the visitor closes the tab. It spent the token saved in their browser for "Keep
        # me signed in", so coming back failed. Without it, tokens are only swapped while
        # someone is using the app (get_session() does it once the hour is up), and the
        # app saves each new one in the browser straight away.
        self.client = create_client(url, key, ClientOptions(auto_refresh_token=False))
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

    def sign_up(self, email, password, username, birth_year=None):
        email, username = validate_sign_up(email, password, username)
        data = {"username": username}
        if birth_year is not None:
            data["birth_year"] = _checked_birth_year(birth_year)
        try:
            res = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {"data": data},
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

    def list_sightings(self):
        user = self._require_user()
        res = (
            self.client.table("sightings")
            .select("id, breed, seen_on, location, dog_name, notes, photo_path")
            # RLS also lets members read other people's shared sightings (for Social),
            # so ask for this user's own rows explicitly.
            .eq("user_id", user.id)
            .order("seen_on", desc=True)
            .order("id", desc=True)
            .execute()
        )
        return _with_tags(res.data, self._tags([r["id"] for r in res.data]))

    def _tags(self, sighting_ids: list[int]) -> dict[int, list[int]]:
        """sighting id -> tagged dog ids. Tags are extras: if they can't be read (say the
        table isn't set up yet), sightings still show, just without tags."""
        if not sighting_ids:
            return {}
        try:
            rows = (self.client.table("sighting_dogs").select("sighting_id, dog_id")
                    .in_("sighting_id", list(sighting_ids)).execute().data)
        except Exception:
            return {}
        tags: dict[int, list[int]] = {}
        for r in rows:
            tags.setdefault(r["sighting_id"], []).append(r["dog_id"])
        return tags

    def add_sighting(self, breed, seen_on, location=None, dog_name=None, notes=None,
                     photo_path=None, dog_ids=None):
        user = self._require_user()
        if photo_path:
            _check_photo_path(user, photo_path)
        row = _sighting_row(breed, seen_on, location, dog_name, notes, photo_path)
        saved = self.client.table("sightings").insert({**row, "user_id": user.id}).execute().data
        if dog_ids and saved:
            self.client.table("sighting_dogs").insert(
                [{"sighting_id": saved[0]["id"], "dog_id": d} for d in dict.fromkeys(dog_ids)]
            ).execute()

    def delete_sighting(self, sighting_id):
        user = self._require_user()
        rows = (self.client.table("sightings").delete()
                .eq("id", sighting_id).eq("user_id", user.id).execute().data)
        self._remove_photos([r["photo_path"] for r in rows or [] if r.get("photo_path")])

    def list_user_breeds(self):
        self._require_user()
        try:
            rows = self.client.table("user_breeds").select("name").execute().data
        except Exception:  # not set up yet: typed-in breeds still get logged
            return []
        return _sorted_breeds(r["name"] for r in rows)

    def add_user_breed(self, name):
        user = self._require_user()
        try:
            self.client.table("user_breeds").insert(
                {"name": _checked_breed(name), "added_by": user.id}).execute()
        except Exception as err:
            if not _is_duplicate(err):  # someone added it first: that's fine
                raise

    def add_photo(self, photo):
        user = self._require_user()
        path = logic.photo_path(user.id, uuid.uuid4().hex)
        self.client.storage.from_(PHOTO_BUCKET).upload(
            path, photo, {"content-type": "image/jpeg"})
        return path

    def photo_urls(self, paths):
        self._require_user()
        if not paths:
            return {}
        links = self.client.storage.from_(PHOTO_BUCKET).create_signed_urls(
            list(paths), PHOTO_LINK_SECONDS)
        return {link["path"]: link["signedURL"] for link in links
                if link.get("signedURL") and not link.get("error")}

    DOG_COLUMNS = "id, owner_id, username, name, breed, bio, photo_path"

    def list_dogs(self):
        self._require_user()
        dogs = self.client.table("dogs").select(self.DOG_COLUMNS).order("username").execute().data
        owners = sorted({d["owner_id"] for d in dogs})
        names = {p["user_id"]: p["username"] for p in (
            self.client.table("profiles").select("user_id, username")
            .in_("user_id", owners).execute().data if owners else [])}
        return [{**d, "owner": names.get(d["owner_id"], "")} for d in dogs]

    def add_dog_photo(self, photo):
        user = self._require_user()
        path = logic.dog_photo_path(user.id, uuid.uuid4().hex)
        self.client.storage.from_(PHOTO_BUCKET).upload(
            path, photo, {"content-type": "image/jpeg"})
        return path

    def _clean_dog(self, user: User, dog: dict) -> dict:
        clean = logic.clean_dog(dog)
        if clean["photo_path"]:
            _check_photo_path(user, clean["photo_path"])
        return clean

    def add_dog(self, dog):
        user = self._require_user()
        clean = self._clean_dog(user, dog)
        try:
            rows = (self.client.table("dogs").insert({**clean, "owner_id": user.id})
                    .execute().data)
        except Exception as err:
            if _is_duplicate(err):
                raise ValueError(DOG_USERNAME_TAKEN) from err
            raise
        return {**clean, "owner_id": user.id, **(rows[0] if rows else {})}

    def update_dog(self, dog_id, dog):
        user = self._require_user()
        clean = self._clean_dog(user, dog)
        dogs = self.client.table("dogs")
        old = (dogs.select("photo_path").eq("id", dog_id).eq("owner_id", user.id)
               .execute().data)
        if not old:
            raise ValueError("That dog isn't yours.")
        try:
            dogs.update(clean).eq("id", dog_id).eq("owner_id", user.id).execute()
        except Exception as err:
            if _is_duplicate(err):
                raise ValueError(DOG_USERNAME_TAKEN) from err
            raise
        if old[0].get("photo_path") and old[0]["photo_path"] != clean["photo_path"]:
            self._remove_photos([old[0]["photo_path"]])
        return {**clean, "id": dog_id, "owner_id": user.id}

    def delete_dog(self, dog_id):
        user = self._require_user()
        rows = (self.client.table("dogs").delete()
                .eq("id", dog_id).eq("owner_id", user.id).execute().data)
        self._remove_photos([r["photo_path"] for r in rows or [] if r.get("photo_path")])

    def _remove_photos(self, paths: list[str]) -> None:
        if paths:
            try:  # the row is gone either way; a leftover file is only wasted space
                self.client.storage.from_(PHOTO_BUCKET).remove(paths)
            except Exception:
                pass

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

    def report(self, kind, item_id, reason):
        user = self._require_user()
        logic.check_report(kind, reason)
        try:
            self.client.table("reports").insert(
                {"user_id": user.id, f"{kind}_id": item_id, "reason": reason}).execute()
        except Exception as err:
            if not _is_duplicate(err):  # reported before: nothing more to do
                raise

    def my_reports(self):
        user = self._require_user()
        reported = {kind: set() for kind in logic.REPORT_KINDS}
        try:  # reports are extras: if they can't be read, nothing is hidden
            rows = (self.client.table("reports").select("sighting_id, dog_id")
                    .eq("user_id", user.id).execute().data)
        except Exception:
            return reported
        for row in rows:
            for kind in logic.REPORT_KINDS:
                if row.get(f"{kind}_id") is not None:
                    reported[kind].add(row[f"{kind}_id"])
        return reported

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

    # The birth year also lives in user_metadata, not on profiles: other members can read
    # profiles, but only you (and the project owner) can see your own metadata.
    def birth_year(self):
        self._require_user()
        return _known_birth_year(self._meta.get("birth_year"))

    def set_birth_year(self, year):
        self._require_user()
        year = logic.clean_birth_year(year)
        self.client.auth.update_user({"data": {"birth_year": year}})
        self._meta = {**self._meta, "birth_year": year}

    def needs_birth_year(self):
        user = self._require_user()
        if self.birth_year() is not None:
            return False
        try:
            rows = (self.client.table("profiles").select("user_id")
                    .eq("user_id", user.id).limit(1).execute().data)
        except Exception:  # profiles not set up: nothing to protect yet, so don't block
            return False
        return not rows

    PROFILE_COLUMNS = "username, avatar, favourite_breed, dogs, share_sightings"

    def my_profile(self):
        user = self._require_user()
        profiles = self.client.table("profiles")
        rows = profiles.select(self.PROFILE_COLUMNS).eq("user_id", user.id).execute().data
        if rows:
            return rows[0]
        for name in logic.username_candidates(user.username):  # first visit: make one
            profile = logic.new_profile(name, self.birth_year())
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
                .select("id, user_id, breed, seen_on, location, dog_name, notes, photo_path, "
                        "created_at")
                # Newest post first: when it was posted, not the (maybe older) date seen.
                .order("created_at", desc=True).order("id", desc=True).limit(limit)
                .execute().data)
        rows = _with_tags(rows, self._tags([r["id"] for r in rows]))
        ids = sorted({r["user_id"] for r in rows})
        profiles = (self.client.table("profiles")
                    .select("user_id, username, avatar, share_sightings")
                    .in_("user_id", ids).execute().data) if ids else []
        # Which posts earned a badge needs each spotter's earlier sightings too (oldest
        # first, so if the server caps the rows it's the newest that are left off).
        history = (self.client.table("sightings").select("id, user_id, breed, seen_on")
                   .in_("user_id", ids).order("seen_on").order("id")
                   .execute().data) if ids else []
        milestones = logic.milestone_sightings(history, _listed_breeds())
        return logic.social_feed(rows, {p["user_id"]: p for p in profiles}, milestones)

    def dog_sightings(self, dog_id):
        self._require_user()
        try:  # tags are extras: if they can't be read, the dog just has no sightings
            ids = sorted({r["sighting_id"] for r in (
                self.client.table("sighting_dogs").select("sighting_id")
                .eq("dog_id", dog_id).execute().data)})
        except Exception:
            return []
        if not ids:
            return []
        # RLS returns only the ones you can read: yours, plus those of members who share.
        rows = (self.client.table("sightings")
                .select("id, user_id, breed, seen_on, location, dog_name, notes, photo_path, "
                        "created_at")
                .in_("id", ids).order("created_at", desc=True).order("id", desc=True)
                .execute().data)
        rows = _with_tags(rows, self._tags([r["id"] for r in rows]))
        users = sorted({r["user_id"] for r in rows})
        profiles = (self.client.table("profiles")
                    .select("user_id, username, avatar, share_sightings")
                    .in_("user_id", users).execute().data) if users else []
        # Same rule as Social: members who've switched sharing off are left out.
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
        # user id -> birth year. Like Supabase's user_metadata: with the account, not the
        # profile other members can read.
        self._birth_years: dict[str, int] = {}

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

    def sign_up(self, email, password, username, birth_year=None):
        email, username = validate_sign_up(email, password, username)
        if birth_year is not None:
            birth_year = _checked_birth_year(birth_year)
        if email in self._accounts:
            raise AuthError("An account with that email already exists.")
        user = User(id=f"user-{len(self._accounts) + 1}", email=email, username=username)
        self._accounts[email] = (self._hash(password), user)
        if birth_year is not None:
            self._birth_years[user.id] = birth_year
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

    def list_sightings(self):
        user = self._require_user()
        mine = [{k: v for k, v in s.items() if k != "user_id"}
                for s in self._sightings if s["user_id"] == user.id]
        mine = sorted(mine, key=lambda s: (s["seen_on"], s["id"]), reverse=True)
        return _with_tags(mine, self._tags_by_sighting())

    # Dogs and tags are made on first use (like _photos below), so a backend copied from
    # before a deploy (see refresh_stale_backend in app.py) gets them too.
    def _dogs(self) -> dict[int, dict]:
        return self.__dict__.setdefault("dogs", {})  # dog id -> row

    def _tags(self) -> set[tuple[int, int]]:
        return self.__dict__.setdefault("tags", set())  # (sighting id, dog id)

    def _tags_by_sighting(self) -> dict[int, list[int]]:
        tags: dict[int, list[int]] = {}
        for sighting_id, dog_id in sorted(self._tags()):
            tags.setdefault(sighting_id, []).append(dog_id)
        return tags

    def add_sighting(self, breed, seen_on, location=None, dog_name=None, notes=None,
                     photo_path=None, dog_ids=None):
        user = self._require_user()
        if photo_path:
            _check_photo_path(user, photo_path)
        row = _sighting_row(breed, seen_on, location, dog_name, notes, photo_path)
        sighting_id = next(self._ids)
        self._sightings.append({"id": sighting_id, "user_id": user.id, "photo_path": None,
                                "created_at": datetime.now(timezone.utc).isoformat(), **row})
        for dog_id in dog_ids or []:
            if dog_id not in self._dogs():  # like the database's foreign key
                raise ValueError("That dog doesn't exist.")
            self._tags().add((sighting_id, dog_id))

    def delete_sighting(self, sighting_id):
        user = self._require_user()
        mine = [s for s in self._sightings if s["id"] == sighting_id and s["user_id"] == user.id]
        self._sightings = [s for s in self._sightings if s not in mine]
        for s in mine:
            self._photos().pop(s["photo_path"], None)
            self.__dict__["tags"] = {t for t in self._tags() if t[0] != s["id"]}
            self.__dict__["reports"] = [r for r in self._reports()
                                        if r.get("sighting_id") != s["id"]]

    def _user_breeds(self) -> dict[str, dict]:
        """lower-case name -> {name, added_by}, like the user_breeds table (whose unique
        index ignores case). Made on first use, for backends from before a deploy."""
        return self.__dict__.setdefault("user_breeds", {})

    def list_user_breeds(self):
        self._require_user()
        return _sorted_breeds(b["name"] for b in self._user_breeds().values())

    def add_user_breed(self, name):
        user = self._require_user()
        name = _checked_breed(name)
        self._user_breeds().setdefault(name.lower(), {"name": name, "added_by": user.id})

    def _photos(self) -> dict[str, bytes]:
        """path -> JPEG, like the storage bucket. Made on first use, so a backend copied
        from before a deploy (see refresh_stale_backend in app.py) gets one too."""
        return self.__dict__.setdefault("photos", {})

    def add_photo(self, photo):
        user = self._require_user()
        path = logic.photo_path(user.id, uuid.uuid4().hex)
        self._photos()[path] = photo
        return path

    def _may_see_photo(self, user: User, path: str) -> bool:
        """Like the Storage policies: your own files, any dog's photo, and photos on
        sightings you can see (yours, or shared ones)."""
        return (path.startswith(f"{user.id}/")
                or any(d["photo_path"] == path for d in self._dogs().values())
                or any(s["photo_path"] == path and self._can_see(user, s)
                       for s in self._sightings))

    def _can_see(self, user: User, sighting: dict) -> bool:
        return (sighting["user_id"] == user.id
                or bool(self._profiles.get(sighting["user_id"], {}).get("share_sightings")))

    def photo_urls(self, paths):
        user = self._require_user()
        # Demo mode has no file server, so the photo travels inside the link itself.
        photos = self._photos()
        return {p: "data:image/jpeg;base64," + base64.b64encode(photos[p]).decode()
                for p in paths if p in photos and self._may_see_photo(user, p)}

    def list_dogs(self):
        self._require_user()
        return [{**d, "owner": self._profiles.get(d["owner_id"], {}).get("username", "")}
                for d in sorted(self._dogs().values(), key=lambda d: d["username"].lower())]

    def add_dog_photo(self, photo):
        user = self._require_user()
        path = logic.dog_photo_path(user.id, uuid.uuid4().hex)
        self._photos()[path] = photo
        return path

    def _clean_dog(self, user: User, dog: dict, dog_id: int | None = None) -> dict:
        clean = logic.clean_dog(dog)
        if clean["photo_path"]:
            _check_photo_path(user, clean["photo_path"])
        if any(d["username"].lower() == clean["username"].lower()
               for i, d in self._dogs().items() if i != dog_id):
            raise ValueError(DOG_USERNAME_TAKEN)
        return clean

    def _my_dog(self, user: User, dog_id: int) -> dict:
        dog = self._dogs().get(dog_id)
        if dog is None or dog["owner_id"] != user.id:
            raise ValueError("That dog isn't yours.")
        return dog

    def add_dog(self, dog):
        user = self._require_user()
        clean = self._clean_dog(user, dog)
        dog_id = next(self._ids)
        self._dogs()[dog_id] = {"id": dog_id, "owner_id": user.id, **clean}
        return dict(self._dogs()[dog_id])

    def update_dog(self, dog_id, dog):
        user = self._require_user()
        old = self._my_dog(user, dog_id)
        clean = self._clean_dog(user, dog, dog_id)
        if old["photo_path"] and old["photo_path"] != clean["photo_path"]:
            self._photos().pop(old["photo_path"], None)
        self._dogs()[dog_id] = {**old, **clean}
        return dict(self._dogs()[dog_id])

    def delete_dog(self, dog_id):
        user = self._require_user()
        try:
            dog = self._my_dog(user, dog_id)
        except ValueError:
            return  # like a database delete that matches no rows
        self._photos().pop(dog["photo_path"], None)
        del self._dogs()[dog_id]
        self.__dict__["tags"] = {t for t in self._tags() if t[1] != dog_id}
        self.__dict__["reports"] = [r for r in self._reports() if r.get("dog_id") != dog_id]

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

    def _reports(self) -> list[dict]:
        """Rows like the reports table. Made on first use, for backends from before a deploy."""
        return self.__dict__.setdefault("reports", [])

    def report(self, kind, item_id, reason):
        user = self._require_user()
        logic.check_report(kind, reason)
        exists = (any(s["id"] == item_id for s in self._sightings) if kind == "sighting"
                  else item_id in self._dogs())
        if not exists:  # like the database's foreign key
            raise ValueError("That post or dog doesn't exist.")
        key = f"{kind}_id"
        if not any(r["user_id"] == user.id and r.get(key) == item_id for r in self._reports()):
            self._reports().append({"user_id": user.id, key: item_id, "reason": reason,
                                    "reviewed": False})

    def my_reports(self):
        user = self._require_user()
        return {kind: {r[f"{kind}_id"] for r in self._reports()
                       if r["user_id"] == user.id and r.get(f"{kind}_id") is not None}
                for kind in logic.REPORT_KINDS}

    def seen_version(self):
        return self._seen.get(self._require_user().id)

    def mark_version_seen(self, version):
        self._seen[self._require_user().id] = version

    def birth_year(self):
        return self._birth_years.get(self._require_user().id)

    def set_birth_year(self, year):
        self._birth_years[self._require_user().id] = logic.clean_birth_year(year)

    def needs_birth_year(self):
        user = self._require_user()
        return user.id not in self._profiles and self.birth_year() is None

    def _username_taken(self, username: str, by_someone_but: str) -> bool:
        return any(p["username"].lower() == username.lower()
                   for uid, p in self._profiles.items() if uid != by_someone_but)

    def my_profile(self):
        user = self._require_user()
        if user.id not in self._profiles:
            name = next(n for n in logic.username_candidates(user.username)
                        if not self._username_taken(n, user.id))
            self._profiles[user.id] = logic.new_profile(name, self.birth_year())
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
        # Like RLS: your own, plus anyone who shares.
        visible = [s for s in self._sightings if self._can_see(user, s)]
        # Newest post first, like Supabase's created_at order (ids go up as posts are added).
        newest = sorted(visible, key=lambda s: (s.get("created_at", ""), s["id"]),
                        reverse=True)[:limit]
        milestones = logic.milestone_sightings(visible, _listed_breeds())
        return logic.social_feed(_with_tags(newest, self._tags_by_sighting()), self._profiles,
                                 milestones)

    def dog_sightings(self, dog_id):
        user = self._require_user()
        tagged = {sighting_id for sighting_id, tagged_dog in self._tags() if tagged_dog == dog_id}
        visible = [s for s in self._sightings if s["id"] in tagged and self._can_see(user, s)]
        newest = sorted(visible, key=lambda s: (s.get("created_at", ""), s["id"]), reverse=True)
        return logic.social_feed(_with_tags(newest, self._tags_by_sighting()), self._profiles)
