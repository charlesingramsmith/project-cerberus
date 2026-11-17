"""Pure life-list logic: no database, no Streamlit, easy to test.

A "lifer" is the first time a spotter logs a given breed.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BREEDS_CSV = Path(__file__).resolve().parent.parent / "data" / "breeds.csv"

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
