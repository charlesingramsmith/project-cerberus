import pytest

from cerberus import logic


def test_top_100_breeds_load_in_rank_order():
    breeds = logic.load_breeds()
    assert len(breeds) == 100
    assert breeds["breed"].is_unique
    assert breeds.iloc[0]["breed"] == "French Bulldog"
    assert list(breeds["rank"]) == list(range(1, 101))


def test_every_breed_has_a_complete_profile_with_a_credited_photo():
    breeds = set(logic.load_breeds()["breed"])
    profiles = logic.load_breed_profiles()
    assert set(profiles) == breeds  # no missing breeds, and no typos in breed names
    for profile in profiles.values():
        for field in ("origin", "temperament", "intro", "fun_fact", "credit", "licence"):
            assert getattr(profile, field).strip(), f"{profile.breed} has no {field}"
        assert profile.image_url.startswith("https://") and "wikimedia.org" in profile.image_url
        assert profile.source.startswith("https://commons.wikimedia.org/wiki/File:")
        assert "@" not in profile.credit  # never show anyone's email address


def test_breed_profiles_still_load_without_a_photo(tmp_path):
    info = tmp_path / "info.csv"
    info.write_text("breed,origin,temperament,intro,fun_fact\n"
                    'Pug,China,"Charming, loving",A small dog.,A fact.\n', encoding="utf-8")
    photos = tmp_path / "photos.csv"
    photos.write_text("breed,image_url,credit,licence,source\n", encoding="utf-8")
    pug = logic.load_breed_profiles(info, photos)["Pug"]
    assert pug.temperament == "Charming, loving"
    assert pug.image_url == ""


def test_every_breed_has_a_face_crop_inside_the_photo():
    profiles = logic.load_breed_profiles()
    with open(logic.BREED_FACES_CSV, encoding="utf-8") as f:
        assert len(f.readlines()) == 101  # header + one row per breed, no extra names
    for profile in profiles.values():
        assert profile.zoom is not None, f"{profile.breed} has no face crop"
        assert 0 <= profile.face_x <= 100 and 0 <= profile.face_y <= 100, profile.breed
        assert profile.zoom >= 100, profile.breed  # the photo always fills the picture


def test_face_photo_gives_a_sharp_enough_copy_and_its_crop(tmp_path):
    info = tmp_path / "info.csv"
    info.write_text("breed,origin,temperament,intro,fun_fact\nPug,China,Loving,A dog.,A fact.\n",
                    encoding="utf-8")
    photos = tmp_path / "photos.csv"
    photos.write_text("breed,image_url,credit,licence,source\n"
                      "Pug,https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Pug.jpg/960px-Pug.jpg,"
                      "A,CC BY 2.0,https://commons.wikimedia.org/wiki/File:Pug.jpg\n", encoding="utf-8")
    faces = tmp_path / "faces.csv"
    faces.write_text("breed,face_x,face_y,zoom\nPug,22.5,20,250\n", encoding="utf-8")
    pug = logic.load_breed_profiles(info, photos, faces)["Pug"]
    url, css = logic.face_photo(pug)
    assert url.endswith("/330px-Pug.jpg")  # 250% of 56px, twice over = 280px
    assert css == "background-size:250%;background-position:22.5% 20%"
    assert logic.face_photo(pug, box_px=200)[0].endswith("/960px-Pug.jpg")
    # no crop file: no crop, and the app falls back to a plain thumbnail
    plain = logic.load_breed_profiles(info, photos, tmp_path / "missing.csv")["Pug"]
    assert plain.zoom is None and logic.face_photo(plain) is None


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


# --- What's new ----------------------------------------------------------------------

SAMPLE_CHANGELOG = """# Changelog

Intro text that isn't a release.

## 0.2.0 - 2026-11-18 - Accounts
- Create an account.
- Sign in.

## Notes
- Not a release, so ignored.

## 0.1.0 - 2026-11-16
- First release.
"""


def test_parse_changelog_reads_versions_dates_titles_and_changes():
    releases = logic.parse_changelog(SAMPLE_CHANGELOG)
    assert releases == [
        logic.Release("0.2.0", "2026-11-18", "Accounts", ("Create an account.", "Sign in.")),
        logic.Release("0.1.0", "2026-11-16", "", ("First release.",)),
    ]


SAMPLE_ROADMAP = """# Roadmap

## Done

- [x] Something finished

## Now

_Nothing in progress._

## Next

- [ ] **Photo upload** with a sighting (optional).
  - Developer note about `supabase/schema.sql`.
- [ ] Password reset ([docs](docs/reset.md) and `code`)

## Later

- [ ] **Social**: not next yet.
"""


def test_upcoming_features_come_from_now_and_next_only():
    items = logic.upcoming_features(SAMPLE_ROADMAP)
    assert [i.title for i in items] == ["Photo upload", "Password reset (docs and code)"]
    assert items[0] == logic.RoadmapItem(
        key="photo-upload", title="Photo upload",
        text="**Photo upload** with a sighting (optional).")
    assert items[1].key == "password-reset-docs-and-code"


def test_feature_key_is_a_simple_slug():
    assert logic.feature_key("Guided manual ID") == "guided-manual-id"
    assert logic.feature_key('  "Keep me" signed-in! ') == "keep-me-signed-in"


def test_the_real_changelog_is_newest_first_with_valid_dates():
    from datetime import date

    releases = logic.parse_changelog(logic.CHANGELOG_MD.read_text(encoding="utf-8"))
    assert releases, "CHANGELOG.md has no releases the app can read"
    versions = [tuple(int(n) for n in r.version.split(".")) for r in releases]
    assert versions == sorted(versions, reverse=True)
    assert len(set(versions)) == len(versions)
    for r in releases:
        date.fromisoformat(r.date)
        assert r.title and r.changes


def test_the_real_roadmap_has_upcoming_features_with_unique_keys():
    items = logic.upcoming_features(logic.ROADMAP_MD.read_text(encoding="utf-8"))
    assert items
    assert len({i.key for i in items}) == len(items)


def test_clean_suggestion():
    assert logic.clean_suggestion("  Badges please  ") == "Badges please"
    with pytest.raises(ValueError):
        logic.clean_suggestion("   ")
    with pytest.raises(ValueError):
        logic.clean_suggestion("x" * (logic.MAX_SUGGESTION_LENGTH + 1))

@pytest.mark.parametrize("latest, seen, expected", [
    ("0.7.0", None, True),       # never opened Settings
    ("0.7.0", "0.6.0", True),
    ("0.10.0", "0.9.0", True),   # compared as numbers, not text
    ("0.7.0", "0.7.0", False),
    ("0.7.0", "0.8.0", False),
    (None, None, False),         # no releases at all
    ("0.7.0", "garbled", True),
])
def test_has_unseen_update(latest, seen, expected):
    assert logic.has_unseen_update(latest, seen) is expected

# --- Profiles and the Social feed ----------------------------------------------------

def test_clean_profile_tidies_and_drops_empty_dog_rows():
    profile = logic.clean_profile({
        "username": "  charlie ", "avatar": "🐩", "favourite_breed": "",
        "dogs": [{"name": " Biscuit ", "breed": "Beagle"}, {"name": "", "breed": None}],
    })
    assert profile == {"username": "charlie", "avatar": "🐩", "favourite_breed": None,
                       "dogs": [{"name": "Biscuit", "breed": "Beagle"}],
                       "share_sightings": True}


@pytest.mark.parametrize("changes, message", [
    ({"username": "ab"}, "3 to 30"),
    ({"avatar": "🐈"}, "picture"),
    ({"dogs": [{"name": "", "breed": "Pug"}]}, "name"),
    ({"dogs": [{"name": "Rex", "breed": None}] * 6}, "up to 5"),
])
def test_clean_profile_rejects_bad_input(changes, message):
    with pytest.raises(ValueError, match=message):
        logic.clean_profile({**logic.new_profile("charlie"), **changes})


def test_username_candidates_add_numbers_and_pad_short_names():
    names = logic.username_candidates("pat")
    assert [next(names) for _ in range(3)] == ["pat", "pat2", "pat3"]
    assert next(logic.username_candidates("al")) == "al_"


def test_social_feed_adds_names_and_skips_people_who_dont_share():
    sightings = [{"id": 1, "user_id": "a", "breed": "Pug"},
                 {"id": 2, "user_id": "b", "breed": "Beagle"},
                 {"id": 3, "user_id": "c", "breed": "Boxer"}]  # c has no profile
    profiles = {"a": {"username": "alice", "avatar": "🐶", "share_sightings": True},
                "b": {"username": "bobby", "avatar": "🐩", "share_sightings": False}}
    feed = logic.social_feed(sightings, profiles)
    assert [(p["breed"], p["username"], p["avatar"]) for p in feed] == [("Pug", "alice", "🐶")]

# --- Breed thumbnails and photo profile pictures -------------------------------------

COMMONS = "https://upload.wikimedia.org/wikipedia/commons"


@pytest.mark.parametrize("url, small", [
    # already a resized copy: just change the width
    ("https://thumb.wikimedia.org/wikipedia/commons/thumb/1/18/Dog.jpg/960px-Dog.jpg",
     "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/18/Dog.jpg/120px-Dog.jpg"),
    # a full-size original: switch to the resized form
    (f"{COMMONS}/b/bd/Golden_Retriever.jpg", f"{COMMONS}/thumb/b/bd/Golden_Retriever.jpg/120px-Golden_Retriever.jpg"),
    # SVG drawings come back as PNG
    (f"{COMMONS}/a/ab/Pug.svg", f"{COMMONS}/thumb/a/ab/Pug.svg/120px-Pug.svg.png"),
    # anything else is left alone
    ("https://example.com/dog.jpg", "https://example.com/dog.jpg"),
    ("", ""),
])
def test_thumbnail_url(url, small):
    assert logic.thumbnail_url(url) == small


def test_every_breed_photo_gets_a_small_thumbnail():
    for profile in logic.load_breed_profiles().values():
        if profile.image_url:
            assert "/120px-" in logic.thumbnail_url(profile.image_url), profile.breed


def test_a_breed_can_be_a_profile_picture_but_other_text_cannot():
    base = logic.new_profile("charlie")
    assert logic.clean_profile({**base, "avatar": "Cavalier King Charles Spaniel"})["avatar"] \
        == "Cavalier King Charles Spaniel"
    assert logic.clean_profile({**base, "avatar": "🦊"})["avatar"] == "🦊"  # older emoji picks
    with pytest.raises(ValueError, match="picture"):
        logic.clean_profile({**base, "avatar": "Cat"})

# --- Sighting photos ---------------------------------------------------------------

def make_image(size=(4000, 3000), orientation=None, gps=False, fmt="JPEG") -> bytes:
    import io

    from PIL import Image

    img = Image.new("RGB", size, "tan")
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation  # "rotate me" note, as phones write it
    if gps:
        exif[0x8825] = {2: (51.0, 30.0, 0.0)}  # GPS latitude
    out = io.BytesIO()
    img.save(out, format=fmt, exif=exif)
    return out.getvalue()


def open_image(data: bytes):
    import io

    from PIL import Image

    return Image.open(io.BytesIO(data))


def test_photos_are_shrunk_to_a_small_jpeg():
    photo = logic.prepare_photo(make_image((4000, 3000)))
    img = open_image(photo)
    assert img.format == "JPEG"
    assert img.size == (logic.PHOTO_MAX_SIDE, 1200)


def test_small_photos_are_not_enlarged():
    assert open_image(logic.prepare_photo(make_image((800, 600), fmt="PNG"))).size == (800, 600)


def test_photos_are_turned_the_right_way_up():
    # Orientation 6 = "turn 90°": a 4000x3000 sensor image is really a portrait photo.
    img = open_image(logic.prepare_photo(make_image((4000, 3000), orientation=6)))
    assert img.size == (1200, logic.PHOTO_MAX_SIDE)


def test_photo_metadata_such_as_gps_is_removed():
    original = make_image(gps=True)
    assert open_image(original).getexif().get_ifd(0x8825)  # the test photo has a GPS spot
    assert not open_image(logic.prepare_photo(original)).getexif()


def test_files_that_are_not_photos_are_refused():
    with pytest.raises(ValueError, match="doesn't look like a photo"):
        logic.prepare_photo(b"definitely not a jpeg")


def test_photo_paths_start_with_the_owners_folder():
    assert logic.photo_path("uuid-1", "abc") == "uuid-1/abc.jpg"
