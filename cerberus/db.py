"""SQLite storage for Project Cerberus: spotters, breeds and dog sightings.

A "lifer" is the first time a spotter logs a given breed.
"""
from __future__ import annotations

import csv
import os
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "cerberus.db"
BREEDS_CSV = ROOT / "data" / "breeds.csv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS breeds (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,
    popularity_rank  INTEGER
);

CREATE TABLE IF NOT EXISTS sightings (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    breed_id    INTEGER NOT NULL REFERENCES breeds(id),
    seen_on     TEXT NOT NULL,          -- ISO date, e.g. 2026-11-16
    location    TEXT,
    dog_name    TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sightings_user_breed ON sightings(user_id, breed_id);
"""


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open the database, creating tables and loading the breed list if needed.

    The path defaults to $CERBERUS_DB if set, otherwise data/cerberus.db.
    """
    if db_path is None:
        db_path = os.environ.get("CERBERUS_DB", DEFAULT_DB_PATH)
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    seed_breeds(conn)
    return conn


def seed_breeds(conn: sqlite3.Connection, csv_path: Path = BREEDS_CSV) -> None:
    """Load breeds from the CSV. Safe to re-run: new breeds are added, ranks refreshed."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = [(r["breed"].strip(), int(r["rank"])) for r in csv.DictReader(f)]
    with conn:
        conn.executemany(
            "INSERT INTO breeds (name, popularity_rank) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET popularity_rank = excluded.popularity_rank",
            rows,
        )


# --- Spotters -----------------------------------------------------------------

def get_or_create_user(conn: sqlite3.Connection, username: str) -> sqlite3.Row:
    username = username.strip()
    if not username:
        raise ValueError("Username can't be empty.")
    with conn:
        conn.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM users ORDER BY username").fetchall()


# --- Breeds & sightings -------------------------------------------------------

def list_breeds(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM breeds ORDER BY popularity_rank, name").fetchall()


def is_lifer(conn: sqlite3.Connection, user_id: int, breed_id: int) -> bool:
    """True if this spotter has never logged this breed before."""
    row = conn.execute(
        "SELECT 1 FROM sightings WHERE user_id = ? AND breed_id = ? LIMIT 1",
        (user_id, breed_id),
    ).fetchone()
    return row is None


def log_sighting(
    conn: sqlite3.Connection,
    user_id: int,
    breed_id: int,
    seen_on: date,
    location: str | None = None,
    dog_name: str | None = None,
    notes: str | None = None,
) -> bool:
    """Record a sighting. Returns True if it's a new lifer for this spotter."""
    lifer = is_lifer(conn, user_id, breed_id)
    with conn:
        conn.execute(
            "INSERT INTO sightings (user_id, breed_id, seen_on, location, dog_name, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, breed_id, seen_on.isoformat(), _blank_to_none(location),
             _blank_to_none(dog_name), _blank_to_none(notes)),
        )
    return lifer


def life_list(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    """Every breed, with this spotter's first-seen date and sighting count (0 if not seen)."""
    return conn.execute(
        """
        SELECT b.id, b.name, b.popularity_rank,
               MIN(s.seen_on) AS first_seen,
               COUNT(s.id)    AS times_seen
        FROM breeds b
        LEFT JOIN sightings s ON s.breed_id = b.id AND s.user_id = ?
        GROUP BY b.id
        ORDER BY b.popularity_rank, b.name
        """,
        (user_id,),
    ).fetchall()


def list_sightings(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.id, s.seen_on, b.name AS breed, s.dog_name, s.location, s.notes
        FROM sightings s JOIN breeds b ON b.id = s.breed_id
        WHERE s.user_id = ?
        ORDER BY s.seen_on DESC, s.id DESC
        """,
        (user_id,),
    ).fetchall()


def delete_sighting(conn: sqlite3.Connection, user_id: int, sighting_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM sightings WHERE id = ? AND user_id = ?", (sighting_id, user_id))


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
