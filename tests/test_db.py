from datetime import date

import pytest

from cerberus import db


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def breed_id(conn, name):
    return conn.execute("SELECT id FROM breeds WHERE name = ?", (name,)).fetchone()["id"]


def test_top_100_breeds_are_loaded(conn):
    breeds = db.list_breeds(conn)
    assert len(breeds) == 100
    assert breeds[0]["name"] == "French Bulldog"
    assert breeds[-1]["popularity_rank"] == 100


def test_reseeding_does_not_duplicate_breeds(conn):
    db.seed_breeds(conn)
    assert len(db.list_breeds(conn)) == 100


def test_usernames_are_unique_ignoring_case(conn):
    a = db.get_or_create_user(conn, "Charlie")
    b = db.get_or_create_user(conn, "  charlie ")
    assert a["id"] == b["id"]


def test_blank_username_rejected(conn):
    with pytest.raises(ValueError):
        db.get_or_create_user(conn, "   ")


def test_first_sighting_is_a_lifer_and_repeats_are_not(conn):
    user = db.get_or_create_user(conn, "charlie")
    beagle = breed_id(conn, "Beagle")

    assert db.log_sighting(conn, user["id"], beagle, date(2026, 11, 1)) is True
    assert db.log_sighting(conn, user["id"], beagle, date(2026, 11, 2)) is False


def test_lifers_are_per_spotter(conn):
    alice = db.get_or_create_user(conn, "alice")
    bob = db.get_or_create_user(conn, "bob")
    pug = breed_id(conn, "Pug")

    db.log_sighting(conn, alice["id"], pug, date(2026, 11, 1))
    assert db.log_sighting(conn, bob["id"], pug, date(2026, 11, 1)) is True


def test_life_list_tracks_first_seen_and_counts(conn):
    user = db.get_or_create_user(conn, "charlie")
    corgi = breed_id(conn, "Pembroke Welsh Corgi")
    db.log_sighting(conn, user["id"], corgi, date(2026, 11, 10), location="Park")
    db.log_sighting(conn, user["id"], corgi, date(2026, 11, 3))

    entry = next(r for r in db.life_list(conn, user["id"]) if r["id"] == corgi)
    assert entry["first_seen"] == "2026-11-03"
    assert entry["times_seen"] == 2
    assert sum(r["times_seen"] > 0 for r in db.life_list(conn, user["id"])) == 1


def test_delete_only_affects_own_sightings(conn):
    alice = db.get_or_create_user(conn, "alice")
    bob = db.get_or_create_user(conn, "bob")
    lab = breed_id(conn, "Labrador Retriever")
    db.log_sighting(conn, alice["id"], lab, date(2026, 11, 1))
    sighting = db.list_sightings(conn, alice["id"])[0]

    db.delete_sighting(conn, bob["id"], sighting["id"])
    assert len(db.list_sightings(conn, alice["id"])) == 1

    db.delete_sighting(conn, alice["id"], sighting["id"])
    assert db.list_sightings(conn, alice["id"]) == []
