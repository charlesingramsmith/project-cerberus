import base64
import re
from datetime import date
from pathlib import Path

import pytest

from cerberus import logic, sketches


def test_breeds_load_top_100_in_rank_order_then_the_rest_a_to_z():
    breeds = logic.load_breeds()
    assert len(breeds) == 141
    assert breeds["breed"].is_unique
    assert breeds.iloc[0]["breed"] == "French Bulldog"
    assert list(breeds["rank"][:100]) == list(range(1, 101))
    rest = breeds[100:]
    assert rest["rank"].isna().all()  # added breeds have no AKC rank
    assert list(rest["breed"]) == sorted(rest["breed"])


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
        assert len(f.readlines()) == 142  # header + one row per breed, no extra names
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
    assert len(life) == 141
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
    assert len(logic.filter_life_list(life, "All")) == 141
    assert set(logic.filter_life_list(life, "Collected")["breed"]) == {"Beagle", "Pug"}
    assert len(logic.filter_life_list(life, "Still to find")) == 139


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
    assert feed[0]["badges"] == []
    assert logic.social_feed(sightings, profiles, {1: ["first-lifer"]})[0]["badges"] == [
        "first-lifer"]


def test_milestone_sightings_find_the_post_that_earned_each_badge():
    listed = set(logic.load_breeds()["breed"])
    ten = sorted(listed)[:10]
    rows = [{"id": i, "user_id": "a", "breed": b, "seen_on": f"2026-01-{i:02d}"}
            for i, b in enumerate(ten, 1)]
    rows += [
        {"id": 11, "user_id": "a", "breed": ten[0], "seen_on": "2026-02-01"},  # a repeat
        {"id": 12, "user_id": "a", "breed": "Cavapoo", "seen_on": "2026-01-05"},  # unverified
        # b logged a Pug later but dated it earlier: that one is b's first lifer
        {"id": 20, "user_id": "b", "breed": "Beagle", "seen_on": "2026-03-02"},
        {"id": 21, "user_id": "b", "breed": "Pug", "seen_on": "2026-03-01"},
    ]
    assert logic.milestone_sightings(rows, listed) == {
        1: ["first-lifer"], 5: ["breeds-5"], 10: ["breeds-10", "pure-10"],
        21: ["first-lifer"]}
    assert logic.milestone_sightings([], listed) == {}

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

def sightings_of(*rows: tuple[str, str]):
    """A sightings frame from (breed, seen_on) pairs."""
    return logic.sightings_frame([{"id": i, "breed": b, "seen_on": d}
                                  for i, (b, d) in enumerate(rows, 1)])


def test_no_sightings_means_no_badges():
    progress = logic.badge_progress(sightings_of())
    assert [p.badge.goal for p in progress] == [1, *range(5, 101, 5), 110, 120, 130, 140, 141]
    assert not any(p.earned for p in progress)
    assert logic.next_badge(progress).badge.name == "First lifer"
    assert logic.next_badge(progress).to_go == 1


def test_first_lifer_badge_is_earned_on_the_first_sighting_date():
    progress = logic.badge_progress(sightings_of(("Pug", "2026-03-02"), ("Pug", "2026-01-05")))
    first = progress[0]
    assert first.earned and first.earned_on == "2026-01-05"  # earliest, not first logged
    assert not progress[1].earned and progress[1].have == 1 and progress[1].to_go == 4


def test_breed_count_badges_date_from_the_nth_new_breed():
    breeds = logic.load_breeds()["breed"].tolist()
    rows = [(breed, f"2026-01-{day:02d}") for day, breed in enumerate(breeds[:12], 1)]
    rows += [(breeds[0], "2026-02-01")] * 5  # repeats don't count towards badges
    progress = {p.badge.key: p for p in logic.badge_progress(sightings_of(*rows))}
    assert progress["breeds-10"].earned_on == "2026-01-10"
    assert not progress["breeds-15"].earned and progress["breeds-15"].to_go == 3
    assert logic.next_badge(list(progress.values())).badge.key == "breeds-15"


def test_collecting_every_breed_earns_every_badge():
    rows = [(b, "2026-05-01") for b in logic.load_breeds()["breed"]]
    progress = logic.badge_progress(sightings_of(*rows))
    assert all(p.earned and p.to_go == 0 for p in progress)
    assert logic.next_badge(progress) is None


def test_badges_have_unique_keys_and_rising_goals():
    for ladder in (logic.BADGES, logic.PUREBRED_BADGES):
        goals = [b.goal for b in ladder]
        assert goals == sorted(set(goals))
    assert len(logic.BADGES_BY_KEY) == len(logic.ALL_BADGES)
    assert all(b.icon in sketches.SKETCHES for b in logic.ALL_BADGES)
    assert {b.track for b in logic.ALL_BADGES} == set(logic.BADGE_TRACKS)
    assert len({b.key for b in logic.BADGES}) == len(logic.BADGES)
    assert len({b.name for b in logic.BADGES}) == len(logic.BADGES)
    assert len({b.icon for b in logic.BADGES}) == len(logic.BADGES)
    assert all(b.icon in sketches.SKETCHES for b in logic.BADGES)  # each has a drawing
    assert all(b.key == f"breeds-{b.goal}" for b in logic.BADGES[1:])  # stable ids
    assert logic.BADGES[0].description == "Spot your first lifer"
    assert logic.BADGES[1].description == "Spot 5 lifers"
    assert logic.PUREBRED_BADGES[0].description == "Spot 10 different purebreds"


def test_last_purebred_badge_is_for_every_verified_breed():
    assert logic.PUREBRED_BADGES[-1].goal == len(logic.load_breeds())


def test_crosses_count_as_lifers_but_not_purebreds():
    rows = [("Beagle", "2026-01-01"), ("Beagle x Pug", "2026-01-02")]
    rows += [(f"Breed {i}", "2026-01-03") for i in range(3)]
    progress = {p.badge.key: p for p in logic.badge_progress(sightings_of(*rows),
                                                             logic.ALL_BADGES)}
    assert progress["breeds-5"].earned and progress["breeds-5"].have == 5
    assert progress["pure-10"].have == 4
    assert logic.lifer_count(sightings_of(*rows), {"Beagle"}) == 2


def test_cross_badges():
    def earned(*rows):
        progress = logic.badge_progress(sightings_of(*rows), logic.CROSS_BADGES)
        return {p.badge.key: p.earned_on for p in progress if p.earned}

    assert earned(("Beagle", "2026-01-01")) == {}
    assert earned(("Beagle x Pug", "2026-01-02")) == {"cross-1": "2026-01-02"}
    # Family reunion: earned when the last of the cross and both its parents is seen
    assert earned(("Beagle x Pug", "2026-01-02"), ("Pug", "2026-01-05"),
                  ("Beagle", "2026-01-03"))["cross-family"] == "2026-01-05"
    poodles = [(f"Poodle x {b}", f"2026-02-0{i}") for i, b in enumerate("ABC", 1)]
    assert earned(*poodles)["cross-poodle-3"] == "2026-02-03"
    assert "cross-poodle-3" not in earned(*poodles[:2], ("A x B", "2026-02-09"))


def test_cross_badge_hints_say_what_to_do_next():
    hints = logic.cross_badge_hints(sightings_of())
    assert set(hints) == {"cross-1", "cross-poodle-3", "cross-family"}
    assert "Labradoodle (Labrador Retriever x Poodle)" in hints["cross-poodle-3"]

    hints = logic.cross_badge_hints(sightings_of(("Beagle x Pug", "2026-01-01"),
                                                 ("Labrador Retriever x Poodle", "2026-01-02"),
                                                 ("Pug", "2026-01-03")))
    assert "cross-1" not in hints  # earned
    assert hints["cross-family"] == "You've spotted a Beagle x Pug: now spot a Beagle."
    assert hints["cross-poodle-3"].startswith("You have 1.")
    assert "Labradoodle" not in hints["cross-poodle-3"]  # already spotted


def test_newly_earned_lists_badges_that_werent_there_before():
    progress = logic.badge_progress(sightings_of(("Pug", "2026-01-01")))
    assert [b.key for b in logic.newly_earned([], progress)] == ["first-lifer"]
    assert logic.newly_earned(["first-lifer"], progress) == []


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


# --- Dog profiles ---------------------------------------------------------------------------

BREEDS = {"Beagle", "Pug"}


def test_clean_dog_tidies_input():
    assert logic.clean_dog({"username": " @rex_the.lab ", "name": " Rex ", "breed": "Beagle",
                            "bio": "  "}, BREEDS) == {
        "username": "rex_the.lab", "name": "Rex", "breed": "Beagle", "bio": None,
        "photo_path": None}
    assert logic.clean_dog({"username": "mutt", "name": "M", "breed": logic.MIXED_BREED},
                           BREEDS)["breed"] == logic.MIXED_BREED


def test_a_dog_can_be_a_cross_of_two_listed_breeds():
    dog = {"username": "puggle", "name": "Bo", "breed": "Pug x Beagle"}
    assert logic.clean_dog(dog, BREEDS)["breed"] == "Beagle x Pug"  # A to Z
    with pytest.raises(ValueError, match="both"):
        logic.clean_dog({**dog, "breed": "Pug x Unicorn"}, BREEDS)


@pytest.mark.parametrize("dog, message", [
    ({"username": "re", "name": "Rex"}, "3 to 30"),
    ({"username": "rex the lab", "name": "Rex"}, "no spaces"),
    ({"username": "rex", "name": " "}, "name"),
    ({"username": "rex", "name": "x" * 41}, "40"),
    ({"username": "rex", "name": "Rex", "breed": "Unicorn"}, "breed"),
    ({"username": "rex", "name": "Rex", "bio": "x" * 301}, "300"),
])
def test_clean_dog_rejects_bad_input(dog, message):
    with pytest.raises(ValueError, match=message):
        logic.clean_dog(dog, BREEDS)


def test_dog_username_candidates_are_made_from_the_name():
    names = logic.dog_username_candidates("Mr Biscuit!")
    assert [next(names), next(names)] == ["mr_biscuit", "mr_biscuit2"]
    assert next(logic.dog_username_candidates("Bo")) == "bo_"
    assert next(logic.dog_username_candidates("🐶")) == "dog"
    assert all(logic.DOG_USERNAME_RE.match(n) for n in logic.dog_username_candidates("x" * 60))


def test_tagged_names_read_naturally():
    assert logic.tagged_names([]) == ""
    assert logic.tagged_names([{"name": "Rex"}]) == "Rex"
    assert logic.tagged_names([{"name": "Rex"}, {"name": "Bella"}]) == "Rex and Bella"
    assert logic.tagged_names([{"name": n} for n in ("Rex", "Bella", "Max")]) == "Rex, Bella and Max"


def test_tagged_breed_is_used_only_when_the_dogs_agree():
    assert logic.tagged_breed([{"breed": "Pug"}, {"breed": "Pug"}]) == "Pug"
    assert logic.tagged_breed([{"breed": "Pug"}, {"breed": "Beagle"}]) is None
    assert logic.tagged_breed([{"breed": logic.MIXED_BREED}]) is None
    assert logic.tagged_breed([{"breed": None}]) is None
    assert logic.tagged_breed([]) is None


def test_dog_label_and_photo_path():
    assert logic.dog_label({"username": "rex", "name": "Rex", "breed": "Pug"}) == "@rex · Rex (Pug)"
    assert logic.dog_label({"username": "rex", "name": "Rex"}) == "@rex · Rex"
    assert logic.dog_photo_path("u1", "abc") == "u1/dogs/abc.jpg"


# --- Verified and unverified breeds ---------------------------------------------------

def test_clean_breed_uses_the_known_spelling_and_tidies_typed_ones():
    known = ["Labrador Retriever", "Cavapoo"]
    assert logic.clean_breed("labrador  retriever ", known) == "Labrador Retriever"
    assert logic.clean_breed("CAVAPOO", known) == "Cavapoo"
    assert logic.clean_breed("  Sprocker   Spaniel ", known) == "Sprocker Spaniel"
    with pytest.raises(ValueError, match="Pick a breed"):
        logic.clean_breed("   ", known)
    with pytest.raises(ValueError, match="100 characters"):
        logic.clean_breed("x" * 101, known)


def test_only_verified_breeds_are_lifers_or_count_for_badges():
    listed = {"Pug", "Beagle"}
    sightings = sightings_of(("Cavapoo", "2026-01-01"), ("Pug", "2026-02-01"))
    assert not logic.is_lifer(sightings, "Sprocker", listed)
    assert logic.is_lifer(sightings, "Beagle", listed)
    first = logic.badge_progress(sightings, listed=listed)[0]
    assert first.earned_on == "2026-02-01"  # the Pug, not the earlier Cavapoo


def test_unverified_breeds_lists_your_sightings_of_unlisted_breeds():
    sightings = sightings_of(("Cavapoo", "2026-03-01"), ("Pug", "2026-01-01"),
                             ("Cavapoo", "2026-01-05"), ("Sprocker", "2026-02-01"))
    out = logic.unverified_breeds(sightings, {"Pug"})
    assert out.to_dict("records") == [
        {"breed": "Cavapoo", "first_seen": "2026-01-05", "times_seen": 2},
        {"breed": "Sprocker", "first_seen": "2026-02-01", "times_seen": 1}]


# --- Cross breeds -----------------------------------------------------------------------

def test_cross_name_joins_two_breeds_with_their_usual_spelling():
    known = ["Labrador Retriever", "Poodle"]
    assert logic.cross_name("labrador retriever", " Poodle ", known) == "Labrador Retriever x Poodle"
    assert logic.cross_name("Poodle", "Sprocker  Spaniel", known) == "Poodle x Sprocker Spaniel"
    assert logic.cross_name("Poodle", "Labrador Retriever", known) == "Labrador Retriever x Poodle"
    with pytest.raises(ValueError, match="both breeds"):
        logic.cross_name("Poodle", None, known)
    with pytest.raises(ValueError, match="different"):
        logic.cross_name("Poodle", "POODLE", known)
    with pytest.raises(ValueError, match="one breed in each"):
        logic.cross_name("Poodle", "Beagle x Pug", known)
    with pytest.raises(ValueError, match="100 characters"):
        logic.cross_name("a" * 60, "b" * 60, known)


def test_a_cross_typed_in_one_box_is_tidied_part_by_part():
    known = ["Labrador Retriever", "Poodle"]
    assert logic.clean_breed("labrador retriever X poodle", known) == "Labrador Retriever x Poodle"
    assert logic.clean_breed("Xoloitzcuintli", known) == "Xoloitzcuintli"  # an x, not a cross


def test_cross_parents_and_is_cross():
    assert logic.cross_parents("Beagle x Pug") == ("Beagle", "Pug")
    assert logic.cross_parents("Beagle") is None
    assert logic.cross_parents(None) is None
    assert logic.is_cross("Beagle x Pug") and not logic.is_cross("Shih Tzu")


def test_new_crosses_are_lifers_and_have_their_own_list():
    listed = {"Pug", "Beagle"}
    assert logic.is_lifer(sightings_of(("Pug", "2026-01-01")), "Beagle x Pug", listed)
    sightings = sightings_of(("Beagle x Pug", "2026-01-01"), ("Cavapoo", "2026-01-02"),
                             ("Beagle x Pug", "2026-01-03"))
    assert not logic.is_lifer(sightings, "Beagle x Pug", listed)  # seen already
    assert logic.badge_progress(sightings, listed=listed)[0].earned_on == "2026-01-01"
    assert logic.cross_breeds(sightings).to_dict("records") == [
        {"breed": "Beagle x Pug", "first_seen": "2026-01-01", "times_seen": 2}]
    assert list(logic.unverified_breeds(sightings, listed)["breed"]) == ["Cavapoo"]


def test_crosses_are_never_lifers_when_switched_off(monkeypatch):
    monkeypatch.setattr(logic, "CROSSES_ARE_LIFERS", False)
    assert not logic.is_lifer(sightings_of(("Pug", "2026-01-01")), "Beagle x Pug", {"Pug"})


def test_escape_markdown_neutralises_formatting():
    assert logic.escape_markdown("**Rex** [x](y) :red[z]") == (
        r"\*\*Rex\*\* \[x\]\(y\) \:red\[z\]")
    assert logic.escape_markdown("Hyde Park") == "Hyde Park"
    # An empty optional field from the database (None, which pandas turns into NaN)
    assert logic.escape_markdown(None) == ""
    assert logic.escape_markdown(float("nan")) == ""


# --- Date and place from a photo's metadata ---------------------------------------

def photo_with_details(taken="2025:06:01 14:30:00", gps=((51, 30, 26.4), "N", (0, 7, 39.6), "W")):
    import io

    from PIL import Image

    exif = Image.Exif()
    if taken:
        exif.get_ifd(logic.EXIF_IFD)[logic.DATE_TAKEN] = taken
    if gps:
        lat, lat_ref, lon, lon_ref = gps
        exif.get_ifd(logic.GPS_IFD).update({1: lat_ref, 2: lat, 3: lon_ref, 4: lon})
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "tan").save(out, format="JPEG", exif=exif)
    return out.getvalue()


def test_photo_details_read_the_date_and_a_rounded_spot():
    from datetime import date

    details = logic.photo_details(photo_with_details())
    assert details.taken_on == date(2025, 6, 1)
    assert details.where == (51.507, -0.128)  # west is negative, rounded to about 100 m


def test_photo_details_handle_south_and_east():
    details = logic.photo_details(photo_with_details(gps=((33, 52, 0), "S", (151, 12, 0), "E")))
    assert details.where == (-33.867, 151.2)


def test_photos_without_metadata_give_no_details():
    assert logic.photo_details(photo_with_details(taken=None, gps=None)) == logic.PhotoDetails()
    assert logic.photo_details(make_image()) == logic.PhotoDetails()
    assert logic.photo_details(b"not a photo") == logic.PhotoDetails()


def test_odd_metadata_is_ignored():
    details = logic.photo_details(photo_with_details(taken="0000:00:00 00:00:00",
                                                     gps=((0, 0, 0), "N", (0, 0, 0), "E")))
    assert details == logic.PhotoDetails()


def test_the_saved_photo_still_has_no_location():
    original = photo_with_details()
    assert logic.photo_details(original).where
    assert logic.photo_details(logic.prepare_photo(original)) == logic.PhotoDetails()


@pytest.mark.parametrize("address, expected", [
    ({"leisure": "Hyde Park", "suburb": "Mayfair", "city": "London"}, "Hyde Park, London"),
    ({"road": "High St", "suburb": "Clapham", "city": "London"}, "Clapham, London"),
    ({"village": "Grasmere", "county": "Cumbria"}, "Grasmere"),
    ({"town": "Ambleside"}, "Ambleside"),
    ({"road": "A591"}, None),
    ({}, None),
])
def test_place_names_are_short(address, expected):
    assert logic.place_name(address) == expected


def test_posted_on_reads_the_day_in_the_members_time_zone():
    assert logic.posted_on("2026-11-27T13:03:37.123456+00:00") == date(2026, 11, 27)
    assert logic.posted_on("2026-07-01T23:30:00Z", "Europe/London") == date(2026, 7, 2)  # BST
    assert logic.posted_on("2026-07-01T23:30:00+00:00", "Not/A_Zone") == date(2026, 7, 1)
    assert logic.posted_on(None) is None and logic.posted_on("soon") is None


def test_celebration_layout_floats_the_breeds_face_or_both_parents():
    pug = logic.celebration_layout("Pug")
    assert len(pug) == logic.FACE_BALLOONS
    assert {face["breed"] for face in pug} == {"Pug"}
    # Spread across the screen, never off its edges, and not rushed
    assert len({face["left"] for face in pug}) == len(pug)
    assert all(0 <= face["left"] <= 90 and face["rise"] >= 2 for face in pug)
    cross = logic.celebration_layout("Beagle x Pug", count=4)
    assert [face["breed"] for face in cross] == ["Beagle", "Pug", "Beagle", "Pug"]


def test_sketches_and_logo_are_crisp_vectors():
    # Blur filters (feTurbulence and friends) made the icons and logo look fuzzy and
    # low-res, so the pencil look is done with plain strokes only.
    from pathlib import Path
    root = Path(__file__).parent.parent
    drawings = [sketches.svg(name) for name in sketches.SKETCHES]
    drawings += [(root / "assets" / f).read_text("utf-8") for f in ("logo.svg", "icon.svg")]
    assert not any("<filter" in d or "filter=" in d for d in drawings)
    mask = base64.b64decode(sketches.data_uri("paw").split(",", 1)[1]).decode()
    assert 'width="96" height="96"' in mask  # big enough that a mask is never stretched up


def test_legal_page_drops_the_title_and_shrinks_headings():
    page = logic.legal_page("# Privacy policy\n\nIntro\n\n## Who\n\nText\n\n### Photos\n")
    assert page == "Intro\n\n#### Who\n\nText\n\n##### Photos"


@pytest.mark.parametrize("path", [logic.PRIVACY_MD, logic.TERMS_MD])
def test_legal_pages_are_dated_and_give_a_contact(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# ")
    assert re.search(r"\*\*Last updated: \d{1,2} \w+ \d{4}\*\*", text)
    assert "hello@derlin.app" in text
    assert "[" not in text  # no placeholders or links left to fill in


def test_privacy_policy_names_every_service_the_app_uses():
    text = logic.PRIVACY_MD.read_text(encoding="utf-8")
    for service in ("Supabase", "Render", "Streamlit", "Google", "OpenStreetMap", "Wikimedia"):
        assert service in text


# --- Reports ---------------------------------------------------------------------------

def test_report_reasons_match_the_database_check():
    schema = (Path(__file__).parent.parent / "supabase" / "schema.sql").read_text()
    keys = ", ".join(f"'{k}'" for k in logic.REPORT_REASONS)
    assert f"reason in ({keys})" in schema


def test_check_report_and_hiding_reported_posts():
    logic.check_report("sighting", "spam")
    with pytest.raises(ValueError):
        logic.check_report("sighting", "rude")
    with pytest.raises(ValueError):
        logic.check_report("profile", "spam")
    posts = [{"id": 1}, {"id": 2}, {"id": 3}]
    assert logic.without_reported(posts, {2}) == [{"id": 1}, {"id": 3}]


def test_supabase_settings_come_from_secrets_first_then_the_environment():
    secrets = {"url": "https://a.supabase.co", "key": "sb_publishable_a"}
    environ = {"SUPABASE_URL": "https://b.supabase.co", "SUPABASE_KEY": "sb_publishable_b",
               "SUPABASE_REDIRECT_URL": "https://app.derlin.app/"}
    assert logic.supabase_settings(secrets, environ) == {
        "url": "https://a.supabase.co", "key": "sb_publishable_a",
        "redirect_url": "https://app.derlin.app/"}
    assert logic.supabase_settings({}, environ)["url"] == "https://b.supabase.co"


def test_supabase_settings_leave_out_missing_or_blank_values():
    assert logic.supabase_settings({}, {}) == {}
    assert logic.supabase_settings({"url": " "}, {"SUPABASE_KEY": ""}) == {}


@pytest.mark.parametrize("url, expected", [
    ("https://project-cerberus.streamlit.app/", True),
    ("https://project-cerberus.streamlit.app/~/+/?flow=1", True),
    ("https://app.derlin.app/", False),
    ("https://derlin.onrender.com/", False),
    ("http://localhost:8501/", False),
    ("https://streamlit.app.example.com/", False),
    (None, False),
    ("", False),
])
def test_on_streamlit_cloud(url, expected):
    assert logic.on_streamlit_cloud(url) is expected


# --- Age ---------------------------------------------------------------------------

@pytest.mark.parametrize("year, under_18", [
    (2008, True),   # 18 this year, but maybe not yet
    (2007, False),  # 19 this year: at least 18 now
    (2013, True),
    (None, False),  # not known (joined before sign-up asked)
])
def test_is_under_18_gives_the_benefit_of_the_doubt(year, under_18):
    assert logic.is_under_18(year, this_year=2026) is under_18


@pytest.mark.parametrize("value, message", [
    (None, "year you were born"),
    ("soon", "year you were born"),
    (2027, "year you were born"),
    (1900, "year you were born"),
    (2014, "13 or over"),  # 12 this year: certainly under 13
])
def test_clean_birth_year_rejects_bad_years(value, message):
    with pytest.raises(ValueError, match=message):
        logic.clean_birth_year(value, this_year=2026)


def test_clean_birth_year_lets_in_anyone_who_may_be_13():
    assert logic.clean_birth_year("2013", this_year=2026) == 2013
    assert logic.clean_birth_year(1950, this_year=2026) == 1950


def test_birth_years_are_newest_first_and_include_this_year():
    years = logic.birth_years(this_year=2026)
    assert years[0] == 2026 and years[-1] == 2026 - logic.MAX_AGE
    assert years == sorted(years, reverse=True)


def test_new_profiles_start_private_for_under_18s():
    assert logic.new_profile("teen", 2012, this_year=2026)["share_sightings"] is False
    assert logic.new_profile("adult", 1990, this_year=2026)["share_sightings"] is True
    assert logic.new_profile("unknown")["share_sightings"] is True
