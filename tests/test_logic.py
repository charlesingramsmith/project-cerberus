from cerberus import logic


def test_top_100_breeds_load_in_rank_order():
    breeds = logic.load_breeds()
    assert len(breeds) == 100
    assert breeds["breed"].is_unique
    assert breeds.iloc[0]["breed"] == "French Bulldog"
    assert list(breeds["rank"]) == list(range(1, 101))


def test_empty_sightings_give_an_empty_life_list():
    life = logic.life_list(logic.load_breeds(), logic.sightings_frame([]))
    assert len(life) == 100
    assert (life["times_seen"] == 0).all()


def test_is_lifer():
    sightings = logic.sightings_frame([{"id": 1, "breed": "Beagle", "seen_on": "2026-11-01"}])
    assert logic.is_lifer(sightings, "Pug")
    assert not logic.is_lifer(sightings, "Beagle")


def test_life_list_tracks_first_seen_and_counts():
    sightings = logic.sightings_frame([
        {"id": 1, "breed": "Pembroke Welsh Corgi", "seen_on": "2026-11-10"},
        {"id": 2, "breed": "Pembroke Welsh Corgi", "seen_on": "2026-11-03"},
        {"id": 3, "breed": "Pug", "seen_on": "2026-11-05"},
    ])
    life = logic.life_list(logic.load_breeds(), sightings).set_index("breed")

    assert life.loc["Pembroke Welsh Corgi", "first_seen"] == "2026-11-03"
    assert life.loc["Pembroke Welsh Corgi", "times_seen"] == 2
    assert life.loc["Pug", "times_seen"] == 1
    assert (life["times_seen"] > 0).sum() == 2


def _sample_life():
    sightings = logic.sightings_frame([
        {"id": 1, "breed": "Beagle", "seen_on": "2026-11-01"},
        {"id": 2, "breed": "Pug", "seen_on": "2026-11-05"},
    ])
    return logic.life_list(logic.load_breeds(), sightings)


def test_filter_life_list_by_collected_or_missing():
    life = _sample_life()
    assert len(logic.filter_life_list(life, "All")) == 100
    assert set(logic.filter_life_list(life, "Collected")["breed"]) == {"Beagle", "Pug"}
    assert len(logic.filter_life_list(life, "Still to find")) == 98


def test_filter_life_list_search_is_case_insensitive_and_literal():
    life = _sample_life()
    assert list(logic.filter_life_list(life, "All", "  beag ")["breed"]) == ["Beagle"]
    assert logic.filter_life_list(life, "Collected", "corgi").empty
    assert logic.filter_life_list(life, "All", "(").empty  # not treated as a regex


def test_recent_first_orders_by_date_then_newest_logged():
    sightings = logic.sightings_frame([
        {"id": 1, "breed": "Pug", "seen_on": "2026-11-05"},
        {"id": 2, "breed": "Beagle", "seen_on": "2026-11-01"},
        {"id": 3, "breed": "Boxer", "seen_on": "2026-11-05"},
    ])
    assert list(logic.recent_first(sightings)["id"]) == [3, 1, 2]
