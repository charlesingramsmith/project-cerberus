"""Tests for the in-memory backend, which mirrors the Supabase backend's behaviour."""
from datetime import date

import pytest

from cerberus import logic
from cerberus.backends import AuthError, MemoryBackend, validate_sign_up


@pytest.fixture
def backend():
    return MemoryBackend()


@pytest.mark.parametrize("email, password, username", [
    ("not-an-email", "longenough", "charlie"),
    ("a@b.com", "short", "charlie"),
    ("a@b.com", "longenough", "ab"),
    ("a@b.com", "longenough", "x" * 31),
])
def test_sign_up_validation_rejects_bad_input(email, password, username):
    with pytest.raises(AuthError):
        validate_sign_up(email, password, username)


def test_sign_up_normalises_email():
    assert validate_sign_up("  Charlie@Example.COM ", "longenough", " charlie ") == (
        "charlie@example.com", "charlie")


def test_sign_up_then_sign_in(backend):
    user = backend.sign_up("charlie@example.com", "correct-horse", "charlie")
    assert user.username == "charlie"
    backend.sign_out()

    with pytest.raises(AuthError):
        backend.sign_in("charlie@example.com", "wrong-password")
    assert backend.sign_in("Charlie@example.com", "correct-horse") == user


def test_duplicate_email_rejected(backend):
    backend.sign_up("charlie@example.com", "correct-horse", "charlie")
    with pytest.raises(AuthError):
        backend.sign_up("charlie@example.com", "another-pass", "charlie2")


def test_data_requires_sign_in(backend):
    with pytest.raises(AuthError):
        backend.list_sightings()
    with pytest.raises(AuthError):
        backend.add_sighting("Pug", date(2026, 11, 1))


def test_sightings_are_private_to_each_user(backend):
    backend.sign_up("alice@example.com", "password-a", "alice")
    backend.add_sighting("Pug", date(2026, 11, 1), location="  Park ", notes="")
    alice_sighting = backend.list_sightings()[0]
    assert alice_sighting["location"] == "Park"
    assert alice_sighting["notes"] is None
    backend.sign_out()

    backend.sign_up("bob@example.com", "password-b", "bob")
    assert backend.list_sightings() == []
    backend.delete_sighting(alice_sighting["id"])  # bob can't delete alice's sighting
    backend.sign_out()

    backend.sign_in("alice@example.com", "password-a")
    assert len(backend.list_sightings()) == 1
    backend.delete_sighting(alice_sighting["id"])
    assert backend.list_sightings() == []


def test_sightings_listed_newest_first(backend):
    backend.sign_up("charlie@example.com", "correct-horse", "charlie")
    backend.add_sighting("Pug", date(2026, 11, 1))
    backend.add_sighting("Beagle", date(2026, 11, 5))
    assert [s["breed"] for s in backend.list_sightings()] == ["Beagle", "Pug"]


# --- Continue with Google (demo mode pretends to be Google) -------------------------

def google_round_trip(backend, tamper=False):
    from urllib.parse import parse_qs, urlparse

    url, verifier = backend.start_google_sign_in("https://app.example/?flow=abc")
    params = parse_qs(urlparse(url).query)
    assert params["flow"] == ["abc"]  # the return address is kept intact
    code = params["code"][0] + ("x" if tamper else "")
    return backend.finish_google_sign_in(code, verifier)


def test_google_sign_in_creates_an_account_and_signs_in(backend):
    user = google_round_trip(backend)
    assert user.username == "Google User"
    backend.add_sighting("Pug", date(2026, 11, 1))
    assert len(backend.list_sightings()) == 1


def test_google_sign_in_again_is_the_same_account(backend):
    first = google_round_trip(backend)
    backend.sign_out()
    assert google_round_trip(backend) == first


def test_google_sign_in_rejects_a_wrong_code(backend):
    with pytest.raises(AuthError, match="Google"):
        google_round_trip(backend, tamper=True)


def test_google_accounts_have_no_password(backend):
    google_round_trip(backend)
    backend.sign_out()
    with pytest.raises(AuthError):
        backend.sign_in(MemoryBackend.DEMO_GOOGLE_EMAIL, "anything-at-all")


# --- Keep me signed in ----------------------------------------------------------------

def test_refresh_token_only_while_signed_in(backend):
    assert backend.refresh_token() is None
    backend.sign_up("a@example.com", "longenough", "alice")
    assert backend.refresh_token()
    backend.sign_out()
    assert backend.refresh_token() is None


def test_resume_session_signs_back_in_and_rotates_the_token(backend):
    user = backend.sign_up("a@example.com", "longenough", "alice")
    saved = backend.refresh_token()
    backend._user = None  # as if the tab closed (the demo backend keeps its accounts)
    assert backend.resume_session(saved) == user
    assert backend.refresh_token() not in (None, saved)
    backend.list_sightings()  # signed in again


def test_refresh_tokens_are_single_use(backend):
    backend.sign_up("a@example.com", "longenough", "alice")
    saved = backend.refresh_token()
    backend.resume_session(saved)
    with pytest.raises(AuthError):
        backend.resume_session(saved)


def test_sign_out_cancels_the_saved_token(backend):
    backend.sign_up("a@example.com", "longenough", "alice")
    saved = backend.refresh_token()
    backend.sign_out()
    with pytest.raises(AuthError):
        backend.resume_session(saved)


def test_unknown_token_is_rejected(backend):
    with pytest.raises(AuthError):
        backend.resume_session("made-up")


# --- Feature votes and suggestions ----------------------------------------------------

def test_feature_votes_count_everyone_but_track_your_own(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.set_feature_vote("photo-upload", True)
    backend.set_feature_vote("photo-upload", True)  # voting twice still counts once
    backend.sign_out()
    backend.sign_up("b@example.com", "correct-horse", "bobby")
    backend.set_feature_vote("photo-upload", True)
    backend.set_feature_vote("password-reset", True)

    assert backend.feature_vote_counts() == {"photo-upload": 2, "password-reset": 1}
    assert backend.my_feature_votes() == {"photo-upload", "password-reset"}

    backend.set_feature_vote("photo-upload", False)
    assert backend.feature_vote_counts() == {"photo-upload": 1, "password-reset": 1}
    assert backend.my_feature_votes() == {"password-reset"}


def test_suggestions_are_cleaned_and_validated(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.suggest_feature("  Badges for streaks  ")
    assert backend.suggestions == [{"user_id": "user-1", "suggestion": "Badges for streaks"}]
    with pytest.raises(ValueError):
        backend.suggest_feature("   ")


def test_votes_and_suggestions_need_a_sign_in(backend):
    for call in (backend.feature_vote_counts, backend.my_feature_votes,
                 lambda: backend.set_feature_vote("x", True),
                 lambda: backend.suggest_feature("idea")):
        with pytest.raises(AuthError):
            call()

def test_seen_version_is_remembered_per_user(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    assert backend.seen_version() is None
    backend.mark_version_seen("0.7.0")
    backend.sign_out()
    backend.sign_up("b@example.com", "correct-horse", "bobby")
    assert backend.seen_version() is None  # Bobby hasn't seen it
    backend.sign_out()
    backend.sign_in("a@example.com", "correct-horse")
    assert backend.seen_version() == "0.7.0"
    with pytest.raises(AuthError):
        MemoryBackend().seen_version()

# --- Profiles and the Social feed -----------------------------------------------------

def test_first_profile_uses_the_sign_up_username_and_shares_by_default(backend):
    backend.sign_up("a@example.com", "correct-horse", "charlie")
    assert backend.my_profile() == {"username": "charlie", "avatar": "🐶",
                                    "favourite_breed": None, "dogs": [],
                                    "share_sightings": True}


def test_profile_is_new_only_when_my_profile_makes_it(backend):
    backend.sign_up("a@example.com", "correct-horse", "charlie")
    assert not backend.profile_is_new
    backend.my_profile()
    assert backend.profile_is_new
    backend.profile_is_new = False  # the app does this once it has told them
    backend.my_profile()
    assert not backend.profile_is_new


def this_year_minus(n: int) -> int:
    return date.today().year - n


def test_under_18s_start_with_sharing_off(backend):
    backend.sign_up("a@example.com", "correct-horse", "teen", this_year_minus(15))
    assert backend.birth_year() == this_year_minus(15)
    assert backend.my_profile()["share_sightings"] is False


def test_adults_start_with_sharing_on(backend):
    backend.sign_up("a@example.com", "correct-horse", "adult", 1990)
    assert backend.my_profile()["share_sightings"] is True


def test_under_13s_cant_sign_up(backend):
    with pytest.raises(AuthError, match="13 or over"):
        backend.sign_up("a@example.com", "correct-horse", "kid", this_year_minus(10))
    with pytest.raises(AuthError):  # and no account was made
        backend.sign_in("a@example.com", "correct-horse")


def test_new_members_without_a_birth_year_are_asked_once(backend):
    backend.sign_up("a@example.com", "correct-horse", "pat")  # as after Google sign-in
    assert backend.needs_birth_year()
    with pytest.raises(ValueError, match="13 or over"):
        backend.set_birth_year(this_year_minus(12))
    backend.set_birth_year(this_year_minus(14))
    assert not backend.needs_birth_year()
    assert backend.my_profile()["share_sightings"] is False


def test_members_with_a_profile_are_never_asked(backend):
    backend.sign_up("a@example.com", "correct-horse", "pat")
    backend.my_profile()  # joined before sign-up asked
    assert not backend.needs_birth_year()
    with pytest.raises(AuthError):
        MemoryBackend().needs_birth_year()


def test_usernames_are_unique_ignoring_capitals(backend):
    backend.sign_up("a@example.com", "correct-horse", "charlie")
    backend.my_profile()
    backend.sign_out()
    backend.sign_up("b@example.com", "correct-horse", "Charlie")
    assert backend.my_profile()["username"] == "Charlie2"  # first name was taken
    with pytest.raises(ValueError, match="taken"):
        backend.save_profile({**backend.my_profile(), "username": "CHARLIE"})


def test_save_profile_stores_the_cleaned_profile(backend):
    backend.sign_up("a@example.com", "correct-horse", "charlie")
    saved = backend.save_profile({**backend.my_profile(), "favourite_breed": "Beagle",
                                  "dogs": [{"name": " Biscuit ", "breed": None}]})
    assert saved["dogs"] == [{"name": "Biscuit", "breed": None}]
    assert backend.my_profile() == saved


def test_social_feed_shows_sharers_but_life_lists_stay_private(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.my_profile()
    backend.add_sighting("Pug", date(2026, 11, 1), location="Hyde Park")
    backend.sign_out()
    backend.sign_up("b@example.com", "correct-horse", "bobby")
    backend.my_profile()
    backend.add_sighting("Beagle", date(2026, 11, 2))

    feed = backend.social_feed()
    assert [(p["breed"], p["username"]) for p in feed] == [("Beagle", "bobby"), ("Pug", "alice")]
    assert feed[1]["location"] == "Hyde Park"
    assert [s["breed"] for s in backend.list_sightings()] == ["Beagle"]  # only your own

    backend.sign_out()
    backend.sign_in("a@example.com", "correct-horse")
    backend.save_profile({**backend.my_profile(), "share_sightings": False})
    assert [p["username"] for p in backend.social_feed()] == ["bobby"]  # alice hidden, even to herself


def test_feed_marks_the_sighting_that_earned_a_badge(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.my_profile()
    backend.add_sighting("Pug", date(2026, 11, 1))
    backend.add_sighting("Pug", date(2026, 11, 2))
    backend.add_sighting("Cavapoo", date(2026, 10, 1))  # unverified: no badge
    feed = backend.social_feed()
    assert [(p["breed"], p["badges"]) for p in feed] == [  # newest post first
        ("Cavapoo", []), ("Pug", []), ("Pug", ["first-lifer"])]


def test_social_feed_is_in_posting_order_not_date_seen(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.my_profile()
    backend.add_sighting("Pug", date(2026, 11, 20))
    backend.add_sighting("Beagle", date(2026, 6, 1))  # posted later, from an older photo
    feed = backend.social_feed()
    assert [p["breed"] for p in feed] == ["Beagle", "Pug"]
    assert all(p["created_at"] for p in feed)


def test_profiles_and_feed_need_a_sign_in(backend):
    for call in (backend.my_profile, backend.social_feed,
                 lambda: backend.save_profile(logic.new_profile("charlie"))):
        with pytest.raises(AuthError):
            call()

def test_a_breed_photo_can_be_saved_as_your_picture(backend):
    backend.sign_up("a@example.com", "correct-horse", "charlie")
    backend.save_profile({**backend.my_profile(), "avatar": "Beagle"})
    assert backend.my_profile()["avatar"] == "Beagle"

# --- Sighting photos ---------------------------------------------------------------

def test_a_sighting_can_have_a_photo(backend):
    backend.sign_up("a@example.com", "longenough", "alice")
    path = backend.add_photo(b"jpeg-bytes")
    assert path.startswith("user-1/") and path.endswith(".jpg")
    backend.add_sighting("Pug", date(2026, 11, 1), photo_path=path)
    backend.add_sighting("Beagle", date(2026, 11, 2))

    by_breed = {s["breed"]: s for s in backend.list_sightings()}
    assert by_breed["Pug"]["photo_path"] == path
    assert by_breed["Beagle"]["photo_path"] is None
    links = backend.photo_urls([path, "user-1/missing.jpg"])
    assert list(links) == [path]
    assert links[path].startswith("data:image/jpeg;base64,")


def test_photos_show_to_others_only_while_their_owner_shares(backend):
    backend.sign_up("a@example.com", "longenough", "alice")
    backend.my_profile()
    path = backend.add_photo(b"jpeg-bytes")
    backend.add_sighting("Pug", date(2026, 11, 1), photo_path=path)
    secret = backend.add_photo(b"not-on-any-sighting")
    backend.sign_out()

    backend.sign_up("b@example.com", "longenough", "bob")
    backend.my_profile()
    assert [p["photo_path"] for p in backend.social_feed()] == [path]
    assert list(backend.photo_urls([path, secret])) == [path]  # a loose file stays private
    with pytest.raises(ValueError):  # can't attach someone else's photo to your sighting
        backend.add_sighting("Pug", date(2026, 11, 1), photo_path=path)

    backend.sign_out()
    backend.sign_in("a@example.com", "longenough")
    backend.save_profile({**backend.my_profile(), "share_sightings": False})
    backend.sign_out()
    backend.sign_in("b@example.com", "longenough")
    assert backend.photo_urls([path]) == {}


def test_deleting_a_sighting_deletes_its_photo(backend):
    backend.sign_up("a@example.com", "longenough", "alice")
    path = backend.add_photo(b"jpeg-bytes")
    backend.add_sighting("Pug", date(2026, 11, 1), photo_path=path)
    backend.delete_sighting(backend.list_sightings()[0]["id"])
    assert backend.photo_urls([path]) == {}


def test_photos_need_a_sign_in(backend):
    with pytest.raises(AuthError):
        backend.add_photo(b"jpeg-bytes")
    with pytest.raises(AuthError):
        backend.photo_urls(["user-1/a.jpg"])


# --- Dog profiles and tags ----------------------------------------------------------------

def add_member(backend, name):
    backend.sign_up(f"{name}@example.com", "longenough", name)
    backend.my_profile()


def test_dogs_have_unique_usernames_ignoring_capitals(backend):
    add_member(backend, "alice")
    rex = backend.add_dog({"username": "@Rex", "name": " Rex ", "breed": "Beagle"})
    assert rex["username"] == "Rex" and rex["name"] == "Rex" and rex["owner_id"] == "user-1"
    backend.sign_out()
    add_member(backend, "bobby")
    with pytest.raises(ValueError, match="taken"):
        backend.add_dog({"username": "rex", "name": "Another Rex"})
    dogs = backend.list_dogs()
    assert [(d["username"], d["owner"]) for d in dogs] == [("Rex", "alice")]


def test_only_the_owner_can_change_or_delete_a_dog(backend):
    add_member(backend, "alice")
    rex = backend.add_dog({"username": "rex", "name": "Rex"})
    backend.sign_out()
    add_member(backend, "bobby")
    with pytest.raises(ValueError, match="isn't yours"):
        backend.update_dog(rex["id"], {"username": "rex", "name": "Stolen"})
    backend.delete_dog(rex["id"])  # quietly does nothing, like a database delete
    assert [d["name"] for d in backend.list_dogs()] == ["Rex"]

    backend.sign_out()
    backend.sign_in("alice@example.com", "longenough")
    backend.update_dog(rex["id"], {"username": "rexy", "name": "Rex", "bio": "Good boy"})
    assert backend.list_dogs()[0]["username"] == "rexy"
    assert backend.list_dogs()[0]["bio"] == "Good boy"


def test_anyone_can_tag_any_dog_and_everyone_who_sees_the_post_sees_the_tag(backend):
    add_member(backend, "alice")
    rex = backend.add_dog({"username": "rex", "name": "Rex"})
    backend.sign_out()
    add_member(backend, "bobby")
    backend.add_sighting("Beagle", date(2026, 11, 1), dog_ids=[rex["id"]])
    backend.add_sighting("Pug", date(2026, 11, 2))
    assert [s["dog_ids"] for s in backend.list_sightings()] == [[], [rex["id"]]]
    backend.sign_out()
    backend.sign_in("alice@example.com", "longenough")
    assert [p["dog_ids"] for p in backend.social_feed()] == [[], [rex["id"]]]
    with pytest.raises(ValueError):
        backend.add_sighting("Pug", date(2026, 11, 2), dog_ids=[999])


def test_deleting_a_dog_removes_its_photo_and_tags(backend):
    add_member(backend, "alice")
    photo = backend.add_dog_photo(b"jpeg")
    assert photo.startswith("user-1/dogs/")
    rex = backend.add_dog({"username": "rex", "name": "Rex", "photo_path": photo})
    backend.add_sighting("Beagle", date(2026, 11, 1), dog_ids=[rex["id"]])
    backend.delete_dog(rex["id"])
    assert backend.list_dogs() == []
    assert backend.list_sightings()[0]["dog_ids"] == []
    assert backend.photo_urls([photo]) == {}


def test_dog_photos_are_seen_by_every_member_and_replaced_photos_are_deleted(backend):
    add_member(backend, "alice")
    old = backend.add_dog_photo(b"old")
    rex = backend.add_dog({"username": "rex", "name": "Rex", "photo_path": old})
    backend.sign_out()
    add_member(backend, "bobby")
    assert list(backend.photo_urls([old])) == [old]
    with pytest.raises(ValueError):  # your dog can't use someone else's photo
        backend.add_dog({"username": "bob_dog", "name": "B", "photo_path": old})
    backend.sign_out()
    backend.sign_in("alice@example.com", "longenough")
    new = backend.add_dog_photo(b"new")
    backend.update_dog(rex["id"], {"username": "rex", "name": "Rex", "photo_path": new})
    assert list(backend.photo_urls([old, new])) == [new]


def test_dogs_need_a_sign_in(backend):
    for call in (backend.list_dogs, lambda: backend.add_dog_photo(b"x"),
                 lambda: backend.add_dog({"username": "rex", "name": "Rex"})):
        with pytest.raises(AuthError):
            call()


def test_added_breeds_are_shared_and_ignore_capitals(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.add_user_breed("Cavapoo")
    backend.add_user_breed("cavapoo")  # already there: kept as first spelled
    backend.add_user_breed("Aussiedoodle")
    backend.sign_out()
    backend.sign_up("b@example.com", "correct-horse", "bobby")
    assert backend.list_user_breeds() == ["Aussiedoodle", "Cavapoo"]
    with pytest.raises(ValueError):
        backend.add_user_breed("x" * 101)


def test_sightings_can_be_of_a_typed_in_breed_but_not_an_empty_one(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.add_sighting("Cavapoo", date(2026, 11, 1))
    assert backend.list_sightings()[0]["breed"] == "Cavapoo"
    with pytest.raises(ValueError):
        backend.add_sighting("  ", date(2026, 11, 1))


def test_a_dogs_page_shows_only_sightings_social_would_show(backend):
    add_member(backend, "alice")
    rex = backend.add_dog({"username": "rex", "name": "Rex"})
    backend.add_sighting("Pug", date(2026, 11, 1), dog_ids=[rex["id"]])
    backend.add_sighting("Pug", date(2026, 11, 2))  # not tagged
    backend.sign_out()
    add_member(backend, "bobby")
    backend.add_sighting("Pug", date(2026, 11, 3), dog_ids=[rex["id"]])
    backend.save_profile({**backend.my_profile(), "share_sightings": False})
    backend.sign_out()
    add_member(backend, "carol")
    backend.add_sighting("Pug", date(2026, 11, 4), dog_ids=[rex["id"]])

    posts = backend.dog_sightings(rex["id"])
    assert [p["username"] for p in posts] == ["carol", "alice"]  # newest first; bobby doesn't share
    assert all(p["dog_ids"] == [rex["id"]] for p in posts)
    assert backend.dog_sightings(999) == []


# --- Reports ---------------------------------------------------------------------------

def test_reports_are_kept_per_member_and_only_once(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.add_sighting("Pug", date(2026, 11, 1))
    rex = backend.add_dog({"username": "rex", "name": "Rex"})
    sighting_id = backend.list_sightings()[0]["id"]
    backend.sign_out()

    backend.sign_up("b@example.com", "correct-horse", "bobby")
    assert backend.my_reports() == {"sighting": set(), "dog": set()}
    backend.report("sighting", sighting_id, "not_a_dog")
    backend.report("sighting", sighting_id, "spam")  # twice is harmless
    backend.report("dog", rex["id"], "photo")
    assert backend.my_reports() == {"sighting": {sighting_id}, "dog": {rex["id"]}}
    assert len(backend._reports()) == 2
    backend.sign_out()

    backend.sign_in("a@example.com", "correct-horse")  # someone else's reports stay theirs
    assert backend.my_reports() == {"sighting": set(), "dog": set()}


def test_a_report_needs_a_real_reason_and_thing(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.add_sighting("Pug", date(2026, 11, 1))
    sighting_id = backend.list_sightings()[0]["id"]
    with pytest.raises(ValueError):
        backend.report("sighting", sighting_id, "rude")
    with pytest.raises(ValueError):
        backend.report("profile", sighting_id, "spam")
    with pytest.raises(ValueError):
        backend.report("dog", 999, "spam")


def test_deleting_a_post_or_dog_removes_its_reports(backend):
    backend.sign_up("a@example.com", "correct-horse", "alice")
    backend.add_sighting("Pug", date(2026, 11, 1))
    rex = backend.add_dog({"username": "rex", "name": "Rex"})
    sighting_id = backend.list_sightings()[0]["id"]
    backend.report("sighting", sighting_id, "spam")
    backend.report("dog", rex["id"], "spam")
    backend.delete_sighting(sighting_id)
    backend.delete_dog(rex["id"])
    assert backend.my_reports() == {"sighting": set(), "dog": set()}


def test_reports_need_a_sign_in(backend):
    for call in (backend.my_reports, lambda: backend.report("sighting", 1, "spam")):
        with pytest.raises(AuthError):
            call()
