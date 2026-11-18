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

SIGHTING_COLUMNS = ["id", "breed", "seen_on", "location", "dog_name", "notes"]


def load_breeds(csv_path: Path = BREEDS_CSV) -> pd.DataFrame:
    """Breeds ordered by popularity rank, with columns: rank, breed."""
    breeds = pd.read_csv(csv_path)
    breeds["breed"] = breeds["breed"].str.strip()
    return breeds.sort_values(["rank", "breed"]).reset_index(drop=True)


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
