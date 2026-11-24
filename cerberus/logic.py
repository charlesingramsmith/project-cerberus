"""Pure life-list logic: no database, no Streamlit, easy to test.

A "lifer" is the first time a spotter logs a given breed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BREEDS_CSV = ROOT / "data" / "breeds.csv"
CHANGELOG_MD = ROOT / "CHANGELOG.md"
ROADMAP_MD = ROOT / "ROADMAP.md"
BREED_INFO_CSV = ROOT / "data" / "breed_info.csv"
BREED_PHOTOS_CSV = ROOT / "data" / "breed_photos.csv"

SIGHTING_COLUMNS = ["id", "breed", "seen_on", "location", "dog_name", "notes"]


def load_breeds(csv_path: Path = BREEDS_CSV) -> pd.DataFrame:
    """Breeds ordered by popularity rank, with columns: rank, breed."""
    breeds = pd.read_csv(csv_path)
    breeds["breed"] = breeds["breed"].str.strip()
    return breeds.sort_values(["rank", "breed"]).reset_index(drop=True)


@dataclass(frozen=True)
class BreedProfile:
    """What the life list shows when you open a breed: a photo and a short intro."""
    breed: str
    origin: str
    temperament: str
    intro: str
    fun_fact: str
    image_url: str = ""
    credit: str = ""     # photographer, as named on Wikimedia Commons
    licence: str = ""    # e.g. "CC BY-SA 4.0"
    source: str = ""     # the photo's Commons page (credit and licence details)


THUMB_WIDTH = 120  # px: sharp at ~48px on a phone screen, and only ~5 KB each


def thumbnail_url(image_url: str, width: int = THUMB_WIDTH) -> str:
    """A small version of a Wikimedia Commons photo, for thumbnails.

    Commons serves resized copies at .../thumb/<path>/<width>px-<file name>, so
    "/960px-" addresses just change their width, and full-size originals get the thumb
    form. Any other address is returned unchanged.
    """
    sized = re.sub(r"/\d+px-([^/]+)$", rf"/{width}px-\1", image_url)
    if sized != image_url:
        return sized
    original = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/(\w/\w\w)/([^/]+)$",
                        image_url)
    if not original:
        return image_url
    base, folder, name = original.groups()
    thumb_name = f"{name}.png" if name.lower().endswith(".svg") else name  # SVGs come as PNG
    return f"{base}/thumb/{folder}/{name}/{width}px-{thumb_name}"


def load_breed_profiles(info_csv: Path = BREED_INFO_CSV,
                        photos_csv: Path = BREED_PHOTOS_CSV) -> dict[str, BreedProfile]:
    """{breed: BreedProfile}. Text comes from breed_info.csv (written by hand), photos
    from breed_photos.csv (made by scripts/fetch_breed_photos.py). A breed with no
    photo row still gets its text."""
    info = pd.read_csv(info_csv, dtype=str, keep_default_na=False)
    photos = pd.read_csv(photos_csv, dtype=str, keep_default_na=False)
    rows = info.merge(photos, on="breed", how="left").fillna("")
    return {row["breed"]: BreedProfile(**row) for row in rows.to_dict("records")}


def sightings_frame(rows: list[dict]) -> pd.DataFrame:
    """Turn sighting rows from any backend into a DataFrame with a fixed set of columns."""
    return pd.DataFrame(rows, columns=SIGHTING_COLUMNS)


def is_lifer(sightings: pd.DataFrame, breed: str) -> bool:
    """True if this breed isn't in the spotter's sightings yet."""
    return breed not in set(sightings["breed"])


def life_list(breeds: pd.DataFrame, sightings: pd.DataFrame) -> pd.DataFrame:
    """Every breed with first-seen date and number of sightings (0 if not seen yet)."""
    stats = (
        sightings.groupby("breed")
        .agg(first_seen=("seen_on", "min"), times_seen=("seen_on", "size"))
        .reset_index()
    )
    out = breeds.merge(stats, on="breed", how="left")
    out["times_seen"] = out["times_seen"].fillna(0).astype(int)
    return out.sort_values(["rank", "breed"]).reset_index(drop=True)


LIFE_LIST_FILTERS = ["All", "Collected", "Still to find"]


def filter_life_list(life: pd.DataFrame, show: str = "All", query: str = "") -> pd.DataFrame:
    """Narrow a life list to collected / still-to-find breeds and a case-insensitive search."""
    out = life
    if show == "Collected":
        out = out[out["times_seen"] > 0]
    elif show == "Still to find":
        out = out[out["times_seen"] == 0]
    query = (query or "").strip()
    if query:
        out = out[out["breed"].str.contains(query, case=False, regex=False)]
    return out


def recent_first(sightings: pd.DataFrame) -> pd.DataFrame:
    """Sightings newest first (by date seen, then by when they were logged)."""
    return sightings.sort_values(["seen_on", "id"], ascending=False)


# --- What's new: releases from CHANGELOG.md, upcoming features from ROADMAP.md ----------

@dataclass(frozen=True)
class Release:
    version: str        # "0.6.0"
    date: str           # ISO "YYYY-MM-DD"
    title: str
    changes: tuple[str, ...]


RELEASE_HEADING = re.compile(r"^## (\d+\.\d+\.\d+) - (\d{4}-\d{2}-\d{2})(?: - (.+))?$")


def parse_changelog(text: str) -> list[Release]:
    """Releases in the order the changelog lists them (newest first).

    Each release is a `## <version> - <date> - <title>` heading followed by `- ` bullets.
    Anything else (the intro, other headings) is ignored.
    """
    releases: list[Release] = []
    current: dict | None = None
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("## "):
            if current:
                releases.append(Release(**current))
            match = RELEASE_HEADING.match(line)
            current = None
            if match:
                version, date, title = match.groups()
                current = {"version": version, "date": date, "title": title or "",
                           "changes": ()}
        elif current and line.startswith("- "):
            current["changes"] += (line[2:].strip(),)
    if current:
        releases.append(Release(**current))
    return releases


@dataclass(frozen=True)
class RoadmapItem:
    key: str            # stable id for +1 votes, e.g. "photo-upload"
    title: str          # "Photo upload"
    text: str           # the full line as Markdown, e.g. "**Photo upload** with a sighting"


def _section(text: str, name: str) -> list[str]:
    """The lines under a `## <name>` heading, up to the next `## ` heading."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == name
        elif inside:
            lines.append(line)
    return lines


def _plain(markdown: str) -> str:
    """Drop links (keep their text) and code backticks, which mean nothing to users."""
    markdown = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    return markdown.replace("`", "").strip()


def feature_key(title: str) -> str:
    """A short, stable id for a feature: "Guided manual ID" -> "guided-manual-id"."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:100]


def upcoming_features(roadmap: str, sections: tuple[str, ...] = ("Now", "Next")) -> list[RoadmapItem]:
    """Unticked top-level `- [ ]` items from the roadmap's Now and Next sections.

    The indented notes under each item are for developers, so they're left out.
    """
    items = []
    for name in sections:
        for line in _section(roadmap, name):
            if not line.startswith("- [ ] "):
                continue
            text = _plain(line[len("- [ ] "):])
            bold = re.match(r"\*\*(.+?)\*\*", text)
            title = bold.group(1) if bold else text
            items.append(RoadmapItem(key=feature_key(title), title=title, text=text))
    return items


def has_unseen_update(latest: str | None, seen: str | None) -> bool:
    """True if `latest` (e.g. "0.7.0") is newer than the version the user last saw.

    Someone who has never opened Settings (seen is None) hasn't seen any update yet.
    """
    if not latest:
        return False
    try:
        return seen is None or _version(seen) < _version(latest)
    except ValueError:  # a garbled saved version: treat it as unseen
        return True


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


MAX_SUGGESTION_LENGTH = 500


def clean_suggestion(text: str) -> str:
    """Trim a feature suggestion and check its length. Raises ValueError if it can't be sent."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Write your idea first.")
    if len(text) > MAX_SUGGESTION_LENGTH:
        raise ValueError(f"Please keep it under {MAX_SUGGESTION_LENGTH} characters.")
    return text


# --- Profiles and the Social feed ------------------------------------------------------

MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH = 3, 30
# A profile picture ("avatar") is a breed name, shown as that breed's photo. New members
# start with the 🐶 emoji, and the older emoji choices below still work for anyone who
# picked one before breed photos were offered.
AVATARS = ["🐶", "🐕", "🐩", "🦮", "🐕‍🦺", "🐾", "🦴", "🎾", "🐺", "🦊"]
MIXED_BREED = "Mixed breed / other"
MAX_DOGS = 5
MAX_DOG_NAME_LENGTH = 40
USERNAME_TAKEN = "That username is taken. Please choose another."


def new_profile(username: str) -> dict:
    """A brand-new member's profile: sharing is on by default."""
    return {"username": username, "avatar": AVATARS[0], "favourite_breed": None,
            "dogs": [], "share_sightings": True}


def clean_profile(profile: dict, breed_names: set[str] | None = None) -> dict:
    """Check and tidy a profile before saving it. Raises ValueError with a friendly message.

    `breed_names` are the breeds whose photo can be a profile picture (read from
    breeds.csv if not given).
    """
    username = (profile.get("username") or "").strip()
    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        raise ValueError(f"Username must be {MIN_USERNAME_LENGTH} to {MAX_USERNAME_LENGTH} characters.")
    avatar = profile.get("avatar")
    if breed_names is None:
        breed_names = set(load_breeds()["breed"])
    if avatar not in AVATARS and avatar not in breed_names:
        raise ValueError("Pick a profile picture from the list.")
    dogs = []
    for dog in profile.get("dogs") or []:
        name = (dog.get("name") or "").strip()
        breed = dog.get("breed") or None
        if not name and not breed:
            continue  # an empty row: ignore it
        if not name:
            raise ValueError("Give each of your dogs a name.")
        if len(name) > MAX_DOG_NAME_LENGTH:
            raise ValueError(f"Dog names can be up to {MAX_DOG_NAME_LENGTH} characters.")
        dogs.append({"name": name, "breed": breed})
    if len(dogs) > MAX_DOGS:
        raise ValueError(f"You can list up to {MAX_DOGS} dogs.")
    return {"username": username, "avatar": avatar,
            "favourite_breed": profile.get("favourite_breed") or None,
            "dogs": dogs, "share_sightings": bool(profile.get("share_sightings", True))}


def username_candidates(base: str, tries: int = 50):
    """Names to try for a new profile when usernames must be unique: "pat", "pat2", "pat3", ..."""
    base = (base or "").strip()[:MAX_USERNAME_LENGTH - 2]
    base = base.ljust(MIN_USERNAME_LENGTH, "_")  # very short names get padded: "al" -> "al_"
    yield base
    for n in range(2, tries + 1):
        yield f"{base}{n}"


def social_feed(sightings: list[dict], profiles: dict[str, dict]) -> list[dict]:
    """Sightings for the Social tab, each with its spotter's username and avatar.

    `profiles` maps user id -> profile. Sightings from members without a profile, or who
    have switched sharing off, are left out. Order is kept (newest first from the backend).
    """
    feed = []
    for s in sightings:
        who = profiles.get(s["user_id"])
        if who and who.get("share_sightings", True):
            feed.append({**s, "username": who["username"], "avatar": who["avatar"]})
    return feed