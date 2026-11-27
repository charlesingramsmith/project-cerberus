"""SupabaseBackend tests against a small fake client (no network needed)."""
from datetime import date
from types import SimpleNamespace

import pytest

from cerberus import logic
from cerberus.backends import AuthError, SupabaseBackend


class FakeQuery:
    def __init__(self, log, data=None):
        self.log = log
        self.data = data or []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.log.append((name, args, kwargs))
            return self
        return call

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeAuth:
    def __init__(self, needs_confirmation=False):
        self.needs_confirmation = needs_confirmation
        self.session = None

    def _response(self, email, metadata):
        user = SimpleNamespace(id="uuid-1", email=email, user_metadata=metadata)
        self.session = None if self.needs_confirmation else SimpleNamespace(refresh_token="rt-1")
        return SimpleNamespace(user=user, session=self.session)

    def sign_up(self, creds):
        return self._response(creds["email"], creds["options"]["data"])

    def sign_in_with_password(self, creds):
        if creds["password"] != "correct-horse":
            raise RuntimeError("Invalid login credentials")
        return self._response(creds["email"], {"username": "charlie"})

    # "Continue with Google": the real client stashes its PKCE verifier in _storage.
    _storage_key = "sb-auth"

    def sign_in_with_oauth(self, creds):
        self.oauth_creds = creds
        self._storage = SimpleNamespace(get_item=lambda key: {
            "sb-auth-code-verifier": "verifier-123"}.get(key))
        return SimpleNamespace(url="https://project.supabase.co/auth/v1/authorize?provider=google")

    def exchange_code_for_session(self, params):
        if params != {"auth_code": "good-code", "code_verifier": "verifier-123"}:
            raise RuntimeError("invalid flow state")
        user = SimpleNamespace(id="uuid-2", email="pat@gmail.com",
                               user_metadata={"full_name": "Pat Smith"})
        self.session = SimpleNamespace(refresh_token="rt-1")
        return SimpleNamespace(user=user, session=self.session)

    def refresh_session(self, refresh_token):
        if refresh_token != "rt-1":
            raise RuntimeError("Invalid Refresh Token: Already Used")
        user = SimpleNamespace(id="uuid-1", email="charlie@example.com",
                               user_metadata={"username": "charlie"})
        self.session = SimpleNamespace(refresh_token="rt-2")  # single use: a new one each time
        return SimpleNamespace(user=user, session=self.session)

    def get_session(self):
        return self.session

    def sign_out(self, options=None):
        self.sign_out_options = options
        self.session = None

    def update_user(self, attributes):
        self.updated = attributes


def make_backend(rpc_data=None, **auth_kwargs) -> tuple[SupabaseBackend, list]:
    log: list = []

    def rpc(name, *args):
        log.append(("rpc", (name, *args), {}))
        return FakeQuery(log, rpc_data)

    backend = SupabaseBackend.__new__(SupabaseBackend)
    backend.client = SimpleNamespace(auth=FakeAuth(**auth_kwargs),
                                     table=lambda name: FakeQuery(log), rpc=rpc)
    backend._user = None
    backend._meta = {}
    return backend, log


def test_sign_up_stores_username_and_signs_in():
    backend, _ = make_backend()
    user = backend.sign_up("Charlie@Example.com", "correct-horse", "charlie")
    assert user.username == "charlie"
    assert user.email == "charlie@example.com"


def test_sign_up_needing_email_confirmation_returns_none():
    backend, _ = make_backend(needs_confirmation=True)
    assert backend.sign_up("charlie@example.com", "correct-horse", "charlie") is None


def test_supabase_errors_become_auth_errors():
    backend, _ = make_backend()
    with pytest.raises(AuthError, match="Invalid login"):
        backend.sign_in("charlie@example.com", "nope")


def test_add_sighting_sends_cleaned_row_with_user_id():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.add_sighting("Pug", date(2026, 11, 1), location=" Park ", dog_name="", notes=None)

    insert = next(args[0] for name, args, _ in log if name == "insert")
    assert insert == {"breed": "Pug", "seen_on": "2026-11-01", "location": "Park",
                      "dog_name": None, "notes": None, "user_id": "uuid-1"}


def test_expired_session_asks_user_to_sign_in_again():
    backend, _ = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.client.auth.session = None  # simulate a refresh token that has expired
    with pytest.raises(AuthError, match="expired"):
        backend.list_sightings()


def test_google_sign_in_returns_url_and_verifier():
    backend, _ = make_backend()
    url, verifier = backend.start_google_sign_in("https://app.example/?flow=abc")
    assert "provider=google" in url
    assert verifier == "verifier-123"
    assert backend.client.auth.oauth_creds == {
        "provider": "google", "options": {"redirect_to": "https://app.example/?flow=abc"}}


def test_google_sign_in_finishes_with_the_users_google_name():
    backend, _ = make_backend()
    user = backend.finish_google_sign_in("good-code", "verifier-123")
    assert (user.username, user.email) == ("Pat Smith", "pat@gmail.com")
    assert backend.list_sightings() == []  # signed in, so data calls work


def test_failed_google_exchange_becomes_a_friendly_auth_error():
    backend, _ = make_backend()
    with pytest.raises(AuthError, match="Google sign-in didn't work"):
        backend.finish_google_sign_in("stale-code", "verifier-123")


def test_client_does_not_refresh_tokens_in_the_background(monkeypatch):
    # A background refresh after the visitor leaves would spend the token their browser
    # saved for "Keep me signed in".
    import supabase

    made = {}
    monkeypatch.setattr(supabase, "create_client",
                        lambda url, key, options: made.setdefault("options", options))
    SupabaseBackend("https://example.supabase.co", "publishable-key")
    assert made["options"].auto_refresh_token is False


def test_refresh_token_comes_from_the_current_session():
    backend, _ = make_backend()
    assert backend.refresh_token() is None
    backend.sign_in("charlie@example.com", "correct-horse")
    assert backend.refresh_token() == "rt-1"


def test_resume_session_signs_back_in_with_a_saved_token():
    backend, _ = make_backend()
    user = backend.resume_session("rt-1")
    assert user.username == "charlie"
    assert backend.refresh_token() == "rt-2"


def test_used_or_revoked_token_becomes_a_friendly_auth_error():
    backend, _ = make_backend()
    with pytest.raises(AuthError, match="sign in again"):
        backend.resume_session("rt-old")


def test_sign_out_only_ends_this_devices_session():
    backend, _ = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.sign_out()
    assert backend.client.auth.sign_out_options == {"scope": "local"}
    assert backend.refresh_token() is None


def test_vote_counts_come_from_the_counting_function():
    backend, log = make_backend(rpc_data=[{"feature": "photo-upload", "votes": 3}])
    backend.sign_in("charlie@example.com", "correct-horse")
    assert backend.feature_vote_counts() == {"photo-upload": 3}
    assert ("rpc", ("feature_vote_counts",), {}) in log


def test_voting_upserts_and_unvoting_deletes_only_your_row():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.set_feature_vote("photo-upload", True)
    assert ("upsert", ({"user_id": "uuid-1", "feature": "photo-upload"},),
            {"on_conflict": "user_id,feature", "ignore_duplicates": True}) in log

    log.clear()
    backend.set_feature_vote("photo-upload", False)
    assert [entry[0] for entry in log] == ["delete", "eq", "eq"]
    assert ("eq", ("user_id", "uuid-1"), {}) in log


def test_suggestion_is_cleaned_and_sent_with_user_id():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.suggest_feature("  Badges  ")
    insert = next(args[0] for name, args, _ in log if name == "insert")
    assert insert == {"suggestion": "Badges", "user_id": "uuid-1"}

def test_seen_version_comes_from_user_metadata_and_is_saved_there():
    backend, _ = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    assert backend.seen_version() is None
    backend.mark_version_seen("0.7.0")
    assert backend.client.auth.updated == {"data": {"seen_version": "0.7.0"}}
    assert backend.seen_version() == "0.7.0"


def test_seen_version_is_read_back_after_signing_in_again():
    backend, _ = make_backend()
    backend.client.auth.sign_in_with_password = lambda creds: SimpleNamespace(
        user=SimpleNamespace(id="uuid-1", email="charlie@example.com",
                             user_metadata={"username": "charlie", "seen_version": "0.6.0"}),
        session=SimpleNamespace(refresh_token="rt-1"))
    backend.client.auth.session = SimpleNamespace(refresh_token="rt-1")
    backend.sign_in("charlie@example.com", "correct-horse")
    assert backend.seen_version() == "0.6.0"

# --- Profiles and the Social feed -----------------------------------------------------

class Duplicate(Exception):
    code = "23505"  # Postgres "unique value already exists"


def test_list_sightings_asks_for_your_own_rows_only():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.list_sightings()
    assert ("eq", ("user_id", "uuid-1"), {}) in log


def test_existing_profile_is_returned_as_is():
    backend, _ = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    stored = {**logic.new_profile("charlie"), "avatar": "🐩"}
    backend.client.table = lambda name: FakeQuery([], [stored])
    assert backend.my_profile() == stored
    assert not backend.profile_is_new  # it already existed


def test_first_profile_tries_the_next_name_when_one_is_taken():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")

    class TakenOnce(FakeQuery):
        attempts = 0
        row = None  # the row waiting to be inserted

        def insert(self, row):
            self.row = row
            return self

        def execute(self):
            row, self.row = self.row, None
            if row is not None:
                self.log.append(("insert", (row,), {}))
                TakenOnce.attempts += 1
                if TakenOnce.attempts == 1:
                    raise Duplicate()
            return SimpleNamespace(data=[])

    backend.client.table = lambda name: TakenOnce(log)
    assert backend.my_profile()["username"] == "charlie2"
    inserted = [args[0] for name, args, _ in log if name == "insert"]
    assert [r["username"] for r in inserted] == ["charlie", "charlie2"]
    assert all(r["user_id"] == "uuid-1" and r["share_sightings"] for r in inserted)
    assert backend.profile_is_new  # so the app explains sharing


def test_birth_year_goes_in_private_metadata_not_the_profile():
    backend, log = make_backend()
    teen = date.today().year - 15
    backend.sign_up("charlie@example.com", "correct-horse", "charlie", teen)
    assert backend.birth_year() == teen
    backend.my_profile()
    inserted = next(args[0] for name, args, _ in log if name == "insert")
    assert inserted["share_sightings"] is False
    assert "birth_year" not in inserted  # profiles are readable by every member


def test_under_13s_are_refused_before_supabase_is_asked():
    backend, _ = make_backend()
    with pytest.raises(AuthError, match="13 or over"):
        backend.sign_up("kid@example.com", "correct-horse", "kid", date.today().year - 9)
    assert backend.client.auth.session is None


def test_google_members_are_asked_their_birth_year_once():
    backend, _ = make_backend()
    backend.finish_google_sign_in("good-code", "verifier-123")
    backend.client.table = lambda name: FakeQuery([], [])  # no profile yet
    assert backend.needs_birth_year()
    backend.set_birth_year(1990)
    assert backend.client.auth.updated == {"data": {"birth_year": 1990}}
    assert not backend.needs_birth_year()
    assert backend.my_profile()["share_sightings"] is True


def test_existing_members_are_not_asked_their_birth_year():
    backend, _ = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.client.table = lambda name: FakeQuery([], [{"user_id": "uuid-1"}])
    assert not backend.needs_birth_year()


def test_saving_a_taken_username_is_a_friendly_error():
    backend, _ = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")

    class Taken(FakeQuery):
        def execute(self):
            raise Duplicate()

    backend.client.table = lambda name: Taken([])
    with pytest.raises(ValueError, match="taken"):
        backend.save_profile(logic.new_profile("someone"))


def test_social_feed_joins_sightings_with_profiles():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    data = {
        "sightings": [{"id": 2, "user_id": "uuid-9", "breed": "Pug", "seen_on": "2026-11-02"},
                      {"id": 1, "user_id": "uuid-1", "breed": "Beagle", "seen_on": "2026-11-01"}],
        "profiles": [{"user_id": "uuid-9", "username": "pat", "avatar": "🐩", "share_sightings": True},
                     {"user_id": "uuid-1", "username": "charlie", "avatar": "🐶", "share_sightings": False}],
    }
    backend.client.table = lambda name: FakeQuery(log, data[name])
    feed = backend.social_feed()
    assert [(p["breed"], p["username"]) for p in feed] == [("Pug", "pat")]  # charlie stopped sharing
    assert ("in_", ("user_id", ["uuid-1", "uuid-9"]), {}) in log
    assert ("limit", (50,), {}) in log
    assert ("order", ("created_at",), {"desc": True}) in log  # newest post, not date seen
    assert feed[0]["badges"] == ["first-lifer"]  # pat's first verified breed
    assert ("select", ("id, user_id, breed, seen_on",), {}) in log  # spotters' history

# --- Sighting photos ---------------------------------------------------------------

class FakeBucket:
    def __init__(self, log):
        self.log = log

    def upload(self, path, file, options):
        self.log.append(("upload", (path, file, options), {}))

    def create_signed_urls(self, paths, expires_in):
        self.log.append(("sign", (paths, expires_in), {}))
        return [{"path": p, "signedURL": f"https://signed/{p}", "error": None}
                if p.startswith("uuid-1/") else
                {"path": p, "signedURL": None, "error": "Either the object does not exist"}
                for p in paths]

    def remove(self, paths):
        self.log.append(("remove", (paths,), {}))


def with_storage(backend, log, rows=None):
    """Give the fake client a storage bucket, and table queries that return `rows`."""
    buckets = []
    backend.client.storage = SimpleNamespace(
        from_=lambda name: buckets.append(name) or FakeBucket(log))
    backend.client.table = lambda name: FakeQuery(log, rows)
    return buckets


def test_photos_upload_into_the_users_own_folder_of_the_private_bucket():
    backend, log = make_backend()
    buckets = with_storage(backend, log)
    backend.sign_in("charlie@example.com", "correct-horse")
    path = backend.add_photo(b"jpeg-bytes")

    assert buckets == ["sighting-photos"]
    assert path.startswith("uuid-1/") and path.endswith(".jpg")
    assert ("upload", (path, b"jpeg-bytes", {"content-type": "image/jpeg"}), {}) in log

    backend.add_sighting("Pug", date(2026, 11, 1), photo_path=path)
    insert = next(args[0] for name, args, _ in log if name == "insert")
    assert insert["photo_path"] == path


def test_a_sighting_cant_point_at_someone_elses_photo():
    backend, log = make_backend()
    with_storage(backend, log)
    backend.sign_in("charlie@example.com", "correct-horse")
    with pytest.raises(ValueError):
        backend.add_sighting("Pug", date(2026, 11, 1), photo_path="uuid-2/theirs.jpg")


def test_photo_links_are_signed_and_skip_missing_files():
    backend, log = make_backend()
    with_storage(backend, log)
    backend.sign_in("charlie@example.com", "correct-horse")
    links = backend.photo_urls(["uuid-1/a.jpg", "uuid-2/b.jpg"])
    assert links == {"uuid-1/a.jpg": "https://signed/uuid-1/a.jpg"}
    assert ("sign", (["uuid-1/a.jpg", "uuid-2/b.jpg"], 3600), {}) in log
    assert backend.photo_urls([]) == {}


def test_deleting_a_sighting_removes_its_photo_too():
    backend, log = make_backend()
    with_storage(backend, log, rows=[{"id": 7, "photo_path": "uuid-1/a.jpg"}])
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.delete_sighting(7)
    assert ("eq", ("user_id", "uuid-1"), {}) in log
    assert ("remove", (["uuid-1/a.jpg"],), {}) in log


# --- Dog profiles and tags ----------------------------------------------------------------

def tables(backend, log, data):
    """Table queries return data[table name] (empty if not given)."""
    backend.client.table = lambda name: (log.append(("table", (name,), {}))
                                         or FakeQuery(log, data.get(name)))


def test_tagged_dogs_are_saved_with_the_new_sighting():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    tables(backend, log, {"sightings": [{"id": 42}]})
    backend.add_sighting("Pug", date(2026, 11, 1), dog_ids=[3, 5, 3])
    inserts = [args[0] for name, args, _ in log if name == "insert"]
    assert inserts[1] == [{"sighting_id": 42, "dog_id": 3}, {"sighting_id": 42, "dog_id": 5}]
    assert ("table", ("sighting_dogs",), {}) in log


def test_sightings_come_with_their_tags():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    tables(backend, log, {"sightings": [{"id": 1}, {"id": 2}],
                          "sighting_dogs": [{"sighting_id": 2, "dog_id": 7}]})
    assert [s["dog_ids"] for s in backend.list_sightings()] == [[], [7]]


def test_sightings_still_load_if_tags_cant_be_read():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")

    def table(name):
        if name == "sighting_dogs":
            raise RuntimeError("relation does not exist")
        return FakeQuery(log, [{"id": 1}])
    backend.client.table = table
    assert backend.list_sightings() == [{"id": 1, "dog_ids": []}]


def test_dogs_are_listed_with_their_owners_username():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    tables(backend, log, {"dogs": [{"id": 1, "owner_id": "uuid-9", "username": "rex"}],
                          "profiles": [{"user_id": "uuid-9", "username": "pat"}]})
    assert backend.list_dogs() == [{"id": 1, "owner_id": "uuid-9", "username": "rex",
                                    "owner": "pat"}]


class DuplicateError(Exception):
    code = "23505"


def test_a_taken_dog_username_is_a_friendly_error():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")

    class Taken(FakeQuery):
        def execute(self):
            raise DuplicateError("duplicate key value violates unique constraint")
    backend.client.table = lambda name: Taken(log)
    with pytest.raises(ValueError, match="taken"):
        backend.add_dog({"username": "rex", "name": "Rex"})


def test_editing_a_dog_only_touches_your_own_and_removes_a_replaced_photo():
    backend, log = make_backend()
    with_storage(backend, log, rows=[{"photo_path": "uuid-1/dogs/old.jpg"}])
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.update_dog(4, {"username": "rex", "name": "Rex", "photo_path": "uuid-1/dogs/new.jpg"})
    assert ("eq", ("owner_id", "uuid-1"), {}) in log
    assert ("remove", (["uuid-1/dogs/old.jpg"],), {}) in log
    with pytest.raises(ValueError):
        backend.update_dog(4, {"username": "rex", "name": "Rex", "photo_path": "uuid-2/x.jpg"})


def test_social_feed_includes_photos_and_tags():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    tables(backend, log, {
        "sightings": [{"id": 2, "user_id": "uuid-9", "breed": "Pug", "seen_on": "2026-11-02",
                       "photo_path": "uuid-9/p.jpg"}],
        "profiles": [{"user_id": "uuid-9", "username": "pat", "avatar": "🐩",
                      "share_sightings": True}],
        "sighting_dogs": [{"sighting_id": 2, "dog_id": 7}]})
    post = backend.social_feed()[0]
    assert post["photo_path"] == "uuid-9/p.jpg" and post["dog_ids"] == [7]


def test_adding_a_breed_sends_it_with_user_id_and_ignores_duplicates():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.add_user_breed("Cavapoo")
    assert ("insert", ({"name": "Cavapoo", "added_by": "uuid-1"},), {}) in log

    class Taken(FakeQuery):
        def execute(self):
            raise DuplicateError("duplicate key value violates unique constraint")
    backend.client.table = lambda name: Taken(log)
    backend.add_user_breed("cavapoo")  # someone added it first: no error


def test_added_breeds_are_listed_a_to_z_and_missing_table_gives_none():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.client.table = lambda name: FakeQuery(log, [{"name": "cavapoo"},
                                                        {"name": "Aussiedoodle"}])
    assert backend.list_user_breeds() == ["Aussiedoodle", "cavapoo"]

    class Missing(FakeQuery):
        def execute(self):
            raise RuntimeError("relation user_breeds does not exist")
    backend.client.table = lambda name: Missing(log)
    assert backend.list_user_breeds() == []


def test_a_dogs_page_lists_the_shared_sightings_it_is_tagged_in():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    tables(backend, log, {
        "sighting_dogs": [{"sighting_id": 2, "dog_id": 7}, {"sighting_id": 3, "dog_id": 7}],
        "sightings": [{"id": 3, "user_id": "uuid-8", "breed": "Pug", "seen_on": "2026-11-03"},
                      {"id": 2, "user_id": "uuid-9", "breed": "Pug", "seen_on": "2026-11-02",
                       "photo_path": "uuid-9/p.jpg"}],
        "profiles": [{"user_id": "uuid-9", "username": "pat", "avatar": "Pug",
                      "share_sightings": True},
                     {"user_id": "uuid-8", "username": "sam", "avatar": "Pug",
                      "share_sightings": False}]})
    posts = backend.dog_sightings(7)
    assert [(p["id"], p["username"]) for p in posts] == [(2, "pat")]  # sam stopped sharing
    assert ("eq", ("dog_id", 7), {}) in log
    assert ("in_", ("id", [2, 3]), {}) in log
    assert ("order", ("created_at",), {"desc": True}) in log


def test_a_dogs_page_is_empty_if_tags_cant_be_read():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")

    class Missing(FakeQuery):
        def execute(self):
            raise RuntimeError("relation sighting_dogs does not exist")
    backend.client.table = lambda name: Missing(log)
    assert backend.dog_sightings(7) == []


# --- Reports ---------------------------------------------------------------------------

def test_a_report_is_sent_with_user_id_and_a_repeat_is_ignored():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.report("dog", 7, "not_a_dog")
    insert = next(args[0] for name, args, _ in log if name == "insert")
    assert insert == {"user_id": "uuid-1", "dog_id": 7, "reason": "not_a_dog"}

    class Taken(FakeQuery):
        def execute(self):
            raise DuplicateError("duplicate key value violates unique constraint")
    backend.client.table = lambda name: Taken(log)
    backend.report("dog", 7, "spam")  # no error
    with pytest.raises(ValueError):
        backend.report("dog", 7, "rude")


def test_my_reports_reads_only_your_own_and_survives_a_missing_table():
    backend, log = make_backend()
    backend.sign_in("charlie@example.com", "correct-horse")
    backend.client.table = lambda name: FakeQuery(log, [
        {"sighting_id": 3, "dog_id": None}, {"sighting_id": None, "dog_id": 7}])
    assert backend.my_reports() == {"sighting": {3}, "dog": {7}}
    assert ("eq", ("user_id", "uuid-1"), {}) in log

    def missing(name):
        raise RuntimeError("relation public.reports does not exist")
    backend.client.table = missing
    assert backend.my_reports() == {"sighting": set(), "dog": set()}
