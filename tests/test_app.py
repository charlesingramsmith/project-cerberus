"""End-to-end check of the Streamlit app (in demo mode) using Streamlit's test runner."""
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from cerberus import logic

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def at(monkeypatch):
    monkeypatch.setenv("CERBERUS_DEMO", "1")
    app = AppTest.from_file(APP, default_timeout=10).run()
    assert not app.exception
    return app


def click(at: AppTest, label: str) -> AppTest:
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception
    return at


def sign_up(at: AppTest, username="charlie", email="charlie@example.com", password="correct-horse"):
    at.text_input(key="sign_up_username").input(username)
    at.text_input(key="sign_up_email").input(email)
    at.text_input(key="sign_up_password").input(password)
    at.text_input(key="sign_up_confirm").input(password)
    return click(at, "Create account")


def headers(at: AppTest) -> list[str]:
    return [h.value for h in at.header]


def log_breed(at: AppTest, breed_name: str) -> AppTest:
    """Spotted! in its two steps: pick the breed and Continue, then post."""
    at.selectbox(key="sighting_breed").set_value(breed_name)
    click(at, "Continue")
    return click(at, "Spotted!")


def test_signed_out_visitors_see_the_sign_in_screen(at):
    assert at.title[0].value == "Project Cerberus"  # the logo (assets/logo.svg) sits above it
    assert any(b.label == "Sign in" for b in at.button)
    assert not at.header  # no life list until signed in


def test_mismatched_passwords_are_rejected(at):
    at.text_input(key="sign_up_username").input("charlie")
    at.text_input(key="sign_up_email").input("charlie@example.com")
    at.text_input(key="sign_up_password").input("correct-horse")
    at.text_input(key="sign_up_confirm").input("different-horse")
    click(at, "Create account")
    assert "don't match" in at.error[0].value


def test_full_journey(at):
    sign_up(at)
    assert "charlie's life list" in headers(at)
    assert at.metric[1].value == "0/141"

    log_breed(at, "Beagle")
    assert "New lifer" in at.success[0].value
    assert at.metric[1].value == "1/141"

    log_breed(at, "Beagle")
    assert "another" in at.info[0].value
    assert at.metric[1].value == "1/141"
    assert at.metric[2].value == "2"

    # Sign out, then back in: sightings are still there
    click(at, "Sign out")
    assert not at.header
    at.text_input(key="sign_in_email").input("charlie@example.com")
    at.text_input(key="sign_in_password").input("correct-horse")
    click(at, "Sign in")
    assert at.metric[2].value == "2"


def test_signed_in_app_has_five_main_tabs(at):
    sign_up(at)
    labels = [t.label for t in at.tabs]
    assert labels == ["Spotted!", "Life list", "Profile", "Social", "Settings"]
    assert headers(at) == ["Spotted a dog?", "charlie's life list", "Your profile", "Social", "Settings"]


def badge_cards(at: AppTest) -> str:
    return next(m.value for m in at.markdown if "cerb-badges" in m.value)


def test_first_lifer_earns_a_badge(at):
    sign_up(at)
    assert "Badges (0/34)" in [h.value for h in at.subheader]
    assert "Next up</div><b>First lifer</b>" in "".join(m.value for m in at.markdown)
    assert any("Next badge" in c.value and "First lifer" in c.value for c in at.caption)

    log_breed(at, "Beagle")
    assert "Badge earned: **First lifer**" in at.success[1].value
    assert "Badges (1/34)" in [h.value for h in at.subheader]
    assert "Earned" in badge_cards(at)
    assert any("Puppy steps" in c.value and "4 more lifers" in c.value for c in at.caption)

    log_breed(at, "Pug")  # a second lifer: no new badge to celebrate
    assert len(at.success) == 1


def test_profile_summarises_sightings(at):
    sign_up(at)
    log_breed(at, "Beagle")
    assert any("1 lifer from 1 sighting" in c.value for c in at.caption)


def test_wrong_password_shows_an_error(at):
    sign_up(at)
    click(at, "Sign out")
    at.text_input(key="sign_in_email").input("charlie@example.com")
    at.text_input(key="sign_in_password").input("wrong-password")
    click(at, "Sign in")
    assert "Invalid login" in at.error[0].value


def test_sightings_can_be_deleted_from_their_card(at):
    sign_up(at)
    log_breed(at, "Beagle")
    assert at.metric[2].value == "1"

    delete = next(b for b in at.button if b.key and b.key.startswith("delete_"))
    delete.click().run()
    assert not at.exception
    assert at.metric[2].value == "0"
    assert at.metric[1].value == "0/141"


def test_life_list_search(at):
    sign_up(at)
    at.text_input(key="life_search").input("retriever").run()
    assert not at.exception
    rows = "".join(m.value for m in at.markdown)
    assert "Golden Retriever" in rows
    assert "Beagle" not in rows


def test_life_list_rows_open_a_breed_profile(at):
    sign_up(at)
    at.text_input(key="life_search").input("pug").run()
    rows = "".join(m.value for m in at.markdown)
    assert '<details class="cerb-breed">' in rows  # tapping the row opens the profile
    assert "Fun fact:" in rows and "Temperament:" in rows
    assert "via Wikimedia Commons" in rows  # every photo is credited
    assert 'loading="lazy"' in rows  # photos only download when a breed is opened


def test_page_styles_contain_no_html_tags():
    """st.html silently drops a whole <style> block if it contains another HTML tag
    (even inside a CSS comment), which would undo all of the mobile styling."""
    import re
    source = Path(APP).read_text(encoding="utf-8")
    for css in re.findall(r"<style>(.*?)</style>", source, flags=re.S):
        assert "<" not in css


def test_tab_bar_matches_the_theme_backgrounds():
    """The bottom tab bar paints its own background, so it must use the same colours as
    [theme.light] and [theme.dark] in .streamlit/config.toml, or it shows as a stripe."""
    import tomllib
    root = Path(APP).parent
    theme = tomllib.loads((root / ".streamlit" / "config.toml").read_text("utf-8"))["theme"]
    source = Path(APP).read_text(encoding="utf-8")
    light, dark = theme["light"]["backgroundColor"], theme["dark"]["backgroundColor"]
    assert f"background: {light};  /* matches [theme.light]" in source
    assert f"background: {dark}; }}  /* [theme.dark] */" in source


def test_logo_files_exist():
    root = Path(APP).parent
    assert (root / "assets" / "logo.svg").is_file()  # header and sign-in screen
    assert (root / "assets" / "icon.png").is_file()  # browser tab icon


def google_link(at: AppTest) -> str:
    button = next(b for b in at.get("link_button") if b.proto.label == "Continue with Google")
    return button.proto.url


def returning_from_google(monkeypatch, **params) -> AppTest:
    """A brand-new session, as when Google sends the user back to the app."""
    monkeypatch.setenv("CERBERUS_DEMO", "1")
    app = AppTest.from_file(APP, default_timeout=10)
    for name, value in params.items():
        app.query_params[name] = value
    app.run()
    assert not app.exception
    return app


def test_continue_with_google_signs_in_on_return(at, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    link = google_link(at)
    assert urlparse(link).path == "/"  # Supabase's "<app url>/**" allow list needs the slash
    params = {k: v[0] for k, v in parse_qs(urlparse(link).query).items()}
    assert set(params) == {"flow", "code", "remember"}
    assert params["remember"] == "1"  # "Keep me signed in" is ticked by default

    back = returning_from_google(monkeypatch, **params)
    assert "Google User's life list" in headers(back)
    assert not back.query_params  # the one-time code is cleared from the address bar
    assert back.session_state["remember"] is True


def test_google_link_is_reused_across_reruns(at):
    first = google_link(at)
    at.run()
    assert google_link(at) == first


def test_unknown_google_flow_shows_a_message(monkeypatch):
    back = returning_from_google(monkeypatch, flow="made-up", code="demo-123")
    assert "expired" in back.info[0].value
    assert not back.header


def test_cancelled_google_sign_in_shows_a_message(monkeypatch):
    back = returning_from_google(monkeypatch, error="access_denied")
    assert "cancelled" in back.info[0].value



# --- Keep me signed in ----------------------------------------------------------------
# AppTest can't run the browser-side component (cerberus/remember.py), so FakeBrowser
# stands in for it: it holds what the browser has saved, reports it once per Streamlit
# session (tagged with that session's id), and saves whatever the app passes in
# `data["save"]`, just like SAVED_SIGN_IN_JS.

class FakeBrowser:
    def __init__(self):
        self.saved = ""
        self.theme = "Light"
        self.carry = None  # a sign-in kept in the tab across a theme switch's reload
        self.reloads = 0
        self.instant_switch = True  # False: Streamlit's switcher wasn't found, so it reloads
        self.reported = None  # the component's last report; None until it has made one
        self.last_session = None  # the session id the app passed on its latest run

    def component(self, name, js):
        return self.mount

    def mount(self, *, key, data, on_saved_change):
        from types import SimpleNamespace

        self.last_session = data["session"]
        if data.get("theme") and data["theme"] != self.theme:  # like useTheme()
            self.theme = data["theme"]
            if not self.instant_switch:
                self.carry = data.get("carry")
                self.reloads += 1
                return SimpleNamespace(saved=self.reported)
        if "save" in data:
            self.saved = data["save"] or ""
        return SimpleNamespace(saved=self.reported)

    def report(self, app: AppTest):
        """The component reports what's saved to the app's current session, which reruns it."""
        self.reported = {"session": self.last_session, "token": self.saved,
                         "theme": self.theme, "carry": self.carry}
        self.carry = None  # handed over once
        app.run()
        assert not app.exception

    def open_app(self, backend=None) -> AppTest:
        """Load the page: the first run, then the rerun from the component's report."""
        self.reported = None
        app = AppTest.from_file(APP, default_timeout=10)
        if backend is not None:  # the same Supabase project, as on the real site
            app.session_state["backend"] = backend
        app.run()
        self.report(app)
        return app

    def reconnect(self, backend) -> AppTest:
        """The page stayed open but its Streamlit session ended (a phone waking up, a
        long idle tab): the browser reconnects to a fresh session and hands it the
        report it made to the old one. The component then reports again."""
        app = AppTest.from_file(APP, default_timeout=10)
        app.session_state["backend"] = backend
        app.run()
        assert not app.header  # the old report isn't used, so nothing stale is tried
        self.report(app)
        return app


@pytest.fixture
def browser(monkeypatch):
    import streamlit.components.v2 as components_v2

    monkeypatch.setenv("CERBERUS_DEMO", "1")
    fake = FakeBrowser()
    monkeypatch.setattr(components_v2, "component", fake.component)
    return fake


def test_keep_me_signed_in_is_ticked_by_default(at):
    assert at.checkbox(key="keep_signed_in").value is True


def test_coming_back_later_signs_you_straight_in(browser):
    first_visit = browser.open_app()
    sign_up(first_visit)
    saved = browser.saved
    assert saved  # the refresh token is saved in the browser

    # Close the tab and come back: a brand-new session with nothing in session_state.
    backend = first_visit.session_state["backend"]
    later = browser.open_app(backend)
    assert "charlie's life list" in headers(later)
    assert browser.saved not in ("", saved)  # tokens are single use, so the new one is saved


def test_a_page_that_outlives_its_session_still_signs_you_back_in(browser):
    first_visit = browser.open_app()
    sign_up(first_visit)
    backend = first_visit.session_state["backend"]
    # While the page is open, the hour is up and the token is swapped for a new one;
    # the app saves it. The component's first report still holds the old, spent token.
    backend.resume_session(browser.saved)
    first_visit.run()
    later = browser.reconnect(backend)
    assert "charlie's life list" in headers(later)


def test_unticking_keep_me_signed_in_saves_nothing(browser):
    app = browser.open_app()
    app.checkbox(key="keep_signed_in").uncheck().run()
    sign_up(app)
    assert "charlie's life list" in headers(app)
    assert browser.saved == ""


def test_signing_out_forgets_the_saved_sign_in(browser):
    app = browser.open_app()
    sign_up(app)
    click(app, "Sign out")
    assert browser.saved == ""


def test_dead_saved_sign_in_is_forgotten(browser):
    browser.saved = "expired-or-revoked"
    app = browser.open_app()
    assert not app.header  # still on the sign-in screen
    assert browser.saved == ""


def dark_colours_on(app: AppTest) -> bool:
    return any("--pistachio: #A9C985" in str(h.proto) for h in app.get("html"))


def test_light_mode_is_the_default(browser):
    app = browser.open_app()
    sign_up(app)
    assert browser.theme == "Light" and not dark_colours_on(app)
    app.session_state["main_tab"] = "Settings"
    app.run()
    assert app.toggle(key="dark_mode").value is False


def open_settings(app: AppTest):
    app.session_state["main_tab"] = "Settings"
    app.run()


def test_dark_mode_switch_changes_theme_straight_away(browser):
    app = browser.open_app()
    sign_up(app)
    open_settings(app)
    app.toggle(key="dark_mode").set_value(True).run()
    assert browser.theme == "Dark" and browser.reloads == 0
    assert dark_colours_on(app) and "Settings" in [t.label for t in app.tabs]
    app.toggle(key="dark_mode").set_value(False).run()
    assert browser.theme == "Light" and not dark_colours_on(app)


def test_dark_mode_switch_falls_back_to_a_reload_and_keeps_you_signed_in(browser):
    browser.instant_switch = False  # e.g. a Streamlit upgrade moved its theme switcher
    app = browser.open_app()
    app.checkbox(key="keep_signed_in").uncheck().run()  # even without "Keep me signed in"
    sign_up(app)
    open_settings(app)
    app.toggle(key="dark_mode").set_value(True).run()
    assert browser.theme == "Dark" and browser.reloads == 1
    assert browser.saved == ""  # the sign-in only rides along with the reload

    reloaded = browser.open_app(app.session_state["backend"])  # the page reloads
    assert "charlie's life list" in headers(reloaded)
    assert dark_colours_on(reloaded)
    assert browser.saved == ""  # still not remembered for next time
    open_settings(reloaded)
    assert reloaded.toggle(key="dark_mode").value is True


def test_unticking_updates_the_google_link(at):
    from urllib.parse import parse_qs, urlparse

    at.checkbox(key="keep_signed_in").uncheck().run()
    assert parse_qs(urlparse(google_link(at)).query)["remember"] == ["0"]


# --- Settings: What's new, Coming next, +1 votes and suggestions -----------------------

def vote_buttons(at: AppTest):
    return [b for b in at.button if b.key and b.key.startswith("vote_")]


def test_settings_shows_the_version_and_latest_update(at):
    from cerberus import logic

    sign_up(at)
    latest = logic.parse_changelog(logic.CHANGELOG_MD.read_text(encoding="utf-8"))[0]
    assert f"Version {latest.version}" in [c.value for c in at.caption]
    assert any(f"Version {latest.version}: {latest.title}" in m.value for m in at.markdown)
    assert "Earlier updates" in [e.label for e in at.expander]


def test_coming_next_lists_roadmap_features_with_a_plus_one_each(at):
    from cerberus import logic

    sign_up(at)
    upcoming = logic.upcoming_features(logic.ROADMAP_MD.read_text(encoding="utf-8"))
    assert [b.key for b in vote_buttons(at)] == [f"vote_{i.key}" for i in upcoming]
    assert all(b.label == "+1 · 0" for b in vote_buttons(at))


def test_plus_one_toggles_on_and_off(at):
    sign_up(at)
    key = vote_buttons(at)[0].key
    at.button(key=key).click().run()
    assert not at.exception
    assert at.button(key=key).label == "+1 · 1"
    assert at.button(key=key).proto.type == "primary"  # highlighted: you've voted

    at.button(key=key).click().run()
    assert at.button(key=key).label == "+1 · 0"


def test_suggesting_a_feature(at):
    sign_up(at)
    at.text_area(key="feature_suggestion").input("Badges for streaks")
    click(at, "Send idea")
    assert "Thanks" in at.success[-1].value
    assert at.session_state["backend"].suggestions[0]["suggestion"] == "Badges for streaks"


def test_empty_suggestion_is_rejected(at):
    sign_up(at)
    click(at, "Send idea")
    assert "Write your idea first" in at.error[0].value


# --- New-update dot on Settings --------------------------------------------------------

def latest_version() -> str:
    from cerberus import logic

    return logic.parse_changelog(logic.CHANGELOG_MD.read_text(encoding="utf-8"))[0].version


def dot_shown(at: AppTest) -> bool:
    return any("new-update-dot" in h.proto.body for h in at.get("html"))


def open_tab(at: AppTest, label: str) -> AppTest:
    at.session_state["main_tab"] = next(t for t in at.tabs if t.label.endswith(label)).label
    at.run()
    assert not at.exception
    return at


def test_settings_dot_shows_until_settings_is_opened(at):
    sign_up(at)
    assert dot_shown(at)

    open_tab(at, "Settings")
    assert not dot_shown(at)
    assert any(":violet-badge[New]" in m.value for m in at.markdown)  # the update is marked

    open_tab(at, "Spotted!")
    assert not dot_shown(at)  # stays gone once seen
    assert at.session_state["backend"].seen_version() == latest_version()


# --- Profiles and the Social tab -------------------------------------------------------

def test_editing_your_profile(at):
    sign_up(at)
    at.text_input(key="profile_username").input("charlie_spotter")
    at.selectbox(key="profile_favourite").set_value("Beagle")
    at.button(key="save_profile").click().run()
    assert not at.exception
    assert "Profile saved" in at.success[0].value
    assert "charlie_spotter's life list" in headers(at)
    assert any("Beagle" in m.value for m in at.markdown)


def test_a_taken_username_is_refused(at):
    sign_up(at, username="alice", email="alice@example.com")
    click(at, "Sign out")
    sign_up(at, username="bobby", email="bobby@example.com")
    at.text_input(key="profile_username").input("ALICE")
    at.button(key="save_profile").click().run()
    assert "taken" in at.error[0].value


def feed_html(at: AppTest) -> str:
    return "".join(m.value for m in at.markdown if "cerb-post" in m.value)


def test_social_shows_everyones_shared_sightings(at):
    sign_up(at, username="alice", email="alice@example.com")
    at.selectbox(key="sighting_breed").set_value("Pug")
    click(at, "Continue")
    next(t for t in at.text_input if t.label == "Where").input("Hyde <Park>")
    click(at, "Spotted!")
    click(at, "Sign out")
    sign_up(at, username="bobby", email="bobby@example.com")
    log_breed(at, "Beagle")

    open_tab(at, "Social")
    feed = feed_html(at)
    assert "alice" in feed and "Pug" in feed
    assert "Hyde &lt;Park&gt;" in feed  # shown as typed, but safely escaped
    assert "bobby</b> (you)" in feed


def test_badges_show_in_the_social_feed(at):
    sign_up(at)
    log_breed(at, "Beagle")  # first lifer: earns a badge
    log_breed(at, "Beagle")  # a repeat: no badge
    open_tab(at, "Social")
    feed = feed_html(at)
    assert feed.count("Earned the <b>First lifer</b> badge") == 1


def test_feed_shows_the_post_date_and_an_older_date_seen(at):
    import datetime as dt
    sign_up(at)
    log_breed(at, "Beagle")
    at.session_state["backend"].add_sighting("Pug", dt.date(2026, 3, 9))  # from an old photo
    open_tab(at, "Social")
    feed = feed_html(at)
    assert feed.index("Pug") < feed.index("Beagle")  # posted last, so on top
    assert feed.count("Seen ") == 1 and "Seen 9 Mar 2026" in feed


def test_switching_sharing_off_hides_your_sightings(at):
    sign_up(at)
    log_breed(at, "Beagle")
    at.toggle(key="share_sightings").set_value(False).run()
    assert not at.exception
    open_tab(at, "Social")
    assert "Beagle" not in feed_html(at)
    assert "No sightings yet" in at.info[0].value

def test_new_members_are_told_their_sightings_are_shared(at):
    sign_up(at)
    assert "Social" in " ".join(m.value for m in at.markdown)
    assert at.button(key="notice_keep_sharing")
    click(at, "Keep sharing")  # closes it, and it doesn't come back
    assert not [b for b in at.button if b.key == "notice_keep_sharing"]
    assert at.toggle(key="share_sightings").value


def test_new_members_can_turn_sharing_off_from_the_popup(at):
    sign_up(at)
    click(at, "Turn sharing off")
    assert not [b for b in at.button if b.key == "notice_stop_sharing"]
    assert at.toggle(key="share_sightings").value is False


# --- After a deploy -----------------------------------------------------------------------

def test_changed_helper_files_are_reloaded_without_signing_anyone_out(at):
    """Like a Streamlit Cloud deploy: cerberus/ files change while the server keeps running."""
    import os
    import sys
    import time

    sign_up(at)
    log_breed(at, "Beagle")
    old_logic, old_backend = sys.modules["cerberus.logic"], at.session_state["backend"]
    path = Path(old_logic.__file__)
    before = path.stat()
    try:
        os.utime(path, (before.st_atime, time.time() + 5))  # "the deploy just rewrote it"
        at.run()
        assert not at.exception
        assert sys.modules["cerberus.logic"] is not old_logic  # the new code was loaded
        backend = at.session_state["backend"]
        assert type(backend) is not type(old_backend)  # rebuilt from the new class...
        assert type(backend).__module__ == "cerberus.backends"
        assert "charlie's life list" in headers(at)  # ...and still signed in
        assert at.metric[2].value == "1"  # with the sighting kept
    finally:
        os.utime(path, (before.st_atime, before.st_mtime))

# --- Breed thumbnails and photo profile pictures ------------------------------------------

def test_life_list_rows_show_a_small_breed_photo(at):
    sign_up(at)
    log_breed(at, "Beagle")
    rows = "".join(m.value for m in at.markdown if "cerb-breed" in m.value)
    assert rows.count('class="thumb"') == 141
    # zoomed in on the dog's face (data/breed_faces.csv), with a tick on breeds you've seen
    assert rows.count('<span class="thumb"><span class="face" style="background-image:url(') == 141
    assert "background-size:" in rows and '<span class="tick">' in rows


def test_choosing_a_breed_photo_as_your_profile_picture(at):
    sign_up(at)
    at.selectbox(key="profile_avatar").set_value("Beagle")
    at.button(key="save_profile").click().run()
    assert not at.exception
    assert "Profile saved" in at.success[0].value
    pictures = [m.value for m in at.markdown if 'class="me-avatar pic"' in m.value]
    assert pictures and 'aria-label="Beagle"' in pictures[0]

    log_breed(at, "Pug")
    open_tab(at, "Social")
    assert 'class="avatar pic"><span class="face"' in feed_html(at)  # shown next to your posts too

def test_picking_a_breed_previews_the_picture_before_saving(at):
    sign_up(at)
    at.selectbox(key="profile_avatar").set_value("Beagle").run()
    previews = [m.value for m in at.markdown if 'class="me-avatar pic"' in m.value]
    assert previews and 'aria-label="Beagle"' in previews[-1]


def test_sighting_photos_show_on_their_card_in_profile(at):
    from datetime import date

    sign_up(at)
    assert at.get("file_uploader")  # the optional photo on the Spotted! form
    backend = at.session_state["backend"]
    path = backend.add_photo(b"jpeg-bytes")
    backend.add_sighting("Pug", date(2026, 11, 1), photo_path=path)
    log_breed(at, "Beagle")  # no photo

    open_tab(at, "Profile")
    photos = [m.value for m in at.markdown if "sighting-photo" in m.value]
    assert len(photos) == 1
    assert 'alt="Your photo of a Pug"' in photos[0]


def test_photo_pickers_are_one_button_outside_the_forms(at):
    sign_up(at)
    uploaders = at.get("file_uploader")
    # Spotted! and "Add a dog": each is one "Add photo" button (styled in MOBILE_CSS) ...
    ids = " ".join(u.proto.id for u in uploaders)
    assert "sighting_photo" in ids and "dog_new_photo" in ids
    for u in uploaders:
        assert u.proto.label_visibility.value == u.proto.label_visibility.COLLAPSED
        # ... outside the form, so a picked photo shows a preview straight away
        assert not u.proto.form_id
    assert 'st-key-photo_pick_' in Path(APP).read_text(encoding="utf-8")


def test_sightings_without_a_location_show_in_profile(at):
    """A missing location is None; next to sightings that have one, pandas makes it NaN."""
    from datetime import date

    sign_up(at)
    backend = at.session_state["backend"]
    backend.add_sighting("Pug", date(2026, 11, 1), None)
    backend.add_sighting("Beagle", date(2026, 11, 2), "Hyde Park")  # mixed: None becomes NaN
    open_tab(at, "Profile")
    assert not at.exception
    assert any("**Pug**" in m.value and "nan" not in m.value for m in at.markdown)


# --- Dog profiles and tags ----------------------------------------------------------------

def add_dog(at: AppTest, name: str, username: str = "", breed: str | None = None) -> AppTest:
    at.text_input(key="dog_new_name").input(name)
    at.text_input(key="dog_new_username").input(username)
    if breed:
        at.selectbox(key="dog_new_breed").set_value(breed)
    return click(at, "Add dog")


def test_adding_a_dog_profile(at):
    sign_up(at)
    add_dog(at, "Mr Biscuit", breed="Beagle")  # no username: one is made from the name
    assert "@mr_biscuit saved." in at.success[0].value
    text = " ".join(m.value for m in at.markdown)
    assert "**@mr_biscuit**" in text and "My dog: @mr_biscuit" in text
    assert at.expander  # and an "Edit @mr_biscuit" section

    add_dog(at, "Other", username="MR_BISCUIT")
    assert "taken" in at.error[0].value


def test_tagging_a_dog_fills_in_its_name_and_shows_in_social(at):
    sign_up(at, username="alice", email="alice@example.com")
    add_dog(at, "Rex", username="rex", breed="Pug")
    click(at, "Sign out")
    sign_up(at, username="bobby", email="bobby@example.com")
    rex_id = at.session_state["backend"].list_dogs()[0]["id"]
    at.selectbox(key="sighting_breed").set_value("Pug")
    click(at, "Continue")
    at.multiselect(key="sighting_dogs").set_value([rex_id]).run()
    assert at.text_input(key="sighting_dog_name").value == "Rex"  # filled in straight away
    click(at, "Spotted!")
    assert "Pug" in at.success[0].value
    assert at.session_state["backend"].list_sightings()[0]["dog_name"] == "Rex"  # filled in too
    assert at.multiselect(key="sighting_dogs").value == []  # ready for the next dog

    open_tab(at, "Social")
    assert '<span class="dog-tag" title="Rex">@rex</span>' in feed_html(at)
    at.selectbox(key="social_dog").set_value(rex_id).run()
    assert any("**@rex**" in m.value for m in at.markdown)
    assert any("Owned by alice" in c.value for c in at.caption)
    assert "Pug" in feed_html(at)


def test_several_dogs_can_be_tagged_in_one_post(at):
    sign_up(at)
    add_dog(at, "Rex", username="rex", breed="Pug")
    add_dog(at, "Bella", username="bella", breed="Pug")
    backend = at.session_state["backend"]
    at.selectbox(key="sighting_breed").set_value("Pug")
    click(at, "Continue")
    at.multiselect(key="sighting_dogs").set_value([d["id"] for d in backend.list_dogs()])
    click(at, "Spotted!")
    sighting = backend.list_sightings()[0]
    assert len(sighting["dog_ids"]) == 2
    assert sighting["breed"] == "Pug" and sighting["dog_name"] == "Bella and Rex"


def test_dogs_listed_on_an_old_profile_get_dog_profiles(at):
    sign_up(at)
    backend = at.session_state["backend"]
    backend.save_profile({**backend.my_profile(), "dogs": [{"name": "Biscuit", "breed": "Pug"}]})
    at.run()
    assert not at.exception
    assert [(d["username"], d["breed"]) for d in backend.list_dogs()] == [("biscuit", "Pug")]
    assert backend.my_profile()["dogs"] == []


def test_shared_sighting_photos_show_in_social(at):
    from datetime import date

    sign_up(at, username="alice", email="alice@example.com")
    backend = at.session_state["backend"]
    backend.add_sighting("Pug", date(2026, 11, 1), photo_path=backend.add_photo(b"jpeg"))
    click(at, "Sign out")
    sign_up(at, username="bobby", email="bobby@example.com")
    open_tab(at, "Social")
    assert 'class="sighting-photo" src="data:image/jpeg;base64,' in feed_html(at)


@pytest.fixture
def typing(monkeypatch):
    """Let AppTest type a new option into a selectbox (accept_new_options). Like the browser,
    it sends the typed text itself when it isn't one of the options."""
    from streamlit.proto.WidgetStates_pb2 import WidgetState
    from streamlit.testing.v1.element_tree import Selectbox, _format_value_for_widget

    def widget_state(self):
        ws = WidgetState(id=self.id)
        if self.value is not None:
            shown = _format_value_for_widget(self.format_func, self.value)
            ws.string_value = shown if shown in self.options else self.value
        return ws
    monkeypatch.setattr(Selectbox, "_widget_state", property(widget_state))


def type_breed(at: AppTest, text: str) -> AppTest:
    at.selectbox(key="sighting_breed").set_value(text)
    click(at, "Continue")
    return click(at, "Spotted!")


def test_a_typed_in_breed_is_logged_as_unverified_and_shared_for_review(at, typing):
    sign_up(at, username="alice", email="alice@example.com")
    type_breed(at, "Sprocker   Spaniel")
    assert "unverified breed" in at.info[0].value
    assert not at.success  # not a lifer
    assert at.metric[1].value == "0/141" and at.metric[2].value == "1"
    assert "Unverified breeds" in [h.value for h in at.subheader]
    life = "".join(m.value for m in at.markdown)
    assert "Sprocker Spaniel" in life and "Unverified breed" in life

    # Another member can pick it (typed in any capitals, it's the same breed)
    click(at, "Sign out")
    sign_up(at, username="bobby", email="bobby@example.com")
    assert "Sprocker Spaniel" in at.selectbox(key="sighting_breed").options[-1]
    type_breed(at, "sprocker spaniel")
    assert at.session_state["backend"].list_user_breeds() == ["Sprocker Spaniel"]
    open_tab(at, "Social")
    feed = feed_html(at)
    assert "Sprocker Spaniel" in feed and "cerb-chip unverified" in feed


def test_listed_breeds_say_they_are_verified(at):
    sign_up(at)
    life = "".join(m.value for m in at.markdown)
    assert "</svg> Verified breed" in life  # a sketched tick, then the label


def log_cross(at: AppTest, first: str, second: str) -> AppTest:
    at.toggle(key="sighting_is_cross").set_value(True).run()
    at.selectbox(key="sighting_breed").set_value(first)
    at.selectbox(key="sighting_breed_2").set_value(second)
    click(at, "Continue")
    return at if at.warning else click(at, "Spotted!")  # a warning stays on step 1


def test_a_cross_is_logged_as_breed_a_x_breed_b_and_shown_in_social(at):
    sign_up(at)
    assert not [s for s in at.selectbox if s.key == "sighting_breed_2"]  # only for crosses
    log_cross(at, "Labrador Retriever", "Poodle")
    assert not at.exception
    assert "New lifer! **Labrador Retriever x Poodle** is a new cross" in at.success[0].value
    assert [s.value.split("**")[1] for s in at.success[1:]] == ["First lifer", "Matchmaker"]
    assert at.metric[0].value == "1"  # a lifer...
    assert at.metric[1].value == "0/141" and at.metric[2].value == "1"  # ...but not a breed
    assert not at.toggle(key="sighting_is_cross").value  # ready for the next dog
    assert "Crosses (1)" in [h.value for h in at.subheader]
    assert "Unverified breeds" not in [h.value for h in at.subheader]
    backend = at.session_state["backend"]
    assert backend.list_sightings()[0]["breed"] == "Labrador Retriever x Poodle"
    assert backend.list_user_breeds() == []  # both breeds are verified: nothing to review

    log_cross(at, "Poodle", "Labrador Retriever")  # the same cross, picked the other way
    assert not at.success and "Logged another" in at.info[0].value

    open_tab(at, "Social")
    feed = feed_html(at)
    assert "Labrador Retriever x Poodle" in feed and "cerb-chip cross" in feed


def test_a_cross_needs_two_different_breeds(at):
    sign_up(at)
    log_cross(at, "Poodle", "Poodle")
    assert "two different breeds" in at.warning[0].value
    assert at.session_state["backend"].list_sightings() == []


def test_a_typed_in_breed_in_a_cross_goes_up_for_review(at, typing):
    sign_up(at)
    log_cross(at, "Poodle", "Sprocker Spaniel")
    backend = at.session_state["backend"]
    assert backend.list_sightings()[0]["breed"] == "Poodle x Sprocker Spaniel"
    assert backend.list_user_breeds() == ["Sprocker Spaniel"]


def test_a_photos_date_and_place_fill_in_the_sighting(at, monkeypatch):
    import datetime as dt

    from cerberus import logic, places

    monkeypatch.setattr(places, "fetch_json",
                        lambda url: {"address": {"park": "Kew Gardens", "city": "London"}})
    sign_up(at)
    # AppTest can't upload files, so put what photo_picker reads from a photo in place.
    taken = dt.date.today() - dt.timedelta(days=3)
    at.session_state["sighting_photo_details"] = ("photo-1", logic.PhotoDetails(
        taken, (51.479, -0.295)))
    at.run()
    assert at.date_input(key="sighting_date").value == taken
    assert at.text_input(key="sighting_where").value == "Kew Gardens, London"

    # A different photo replaces what the last one filled in.
    monkeypatch.setattr(places, "fetch_json",
                        lambda url: {"address": {"suburb": "Clapham", "city": "London"}})
    at.session_state["sighting_photo_details"] = ("photo-2", logic.PhotoDetails(
        taken, (51.462, -0.138)))
    at.run()
    assert at.text_input(key="sighting_where").value == "Clapham, London"


def test_photos_without_details_change_nothing(at):
    import datetime as dt

    from cerberus import logic

    sign_up(at)
    at.session_state["sighting_photo_details"] = ("photo-1", logic.PhotoDetails())
    at.run()
    assert at.date_input(key="sighting_date").value == dt.date.today()
    assert at.text_input(key="sighting_where").value == ""


# --- Spotted! in two steps ------------------------------------------------------------

def spot_step(at: AppTest) -> int:
    """Which Spotted! step is showing (the other one is hidden with CSS)."""
    hidden = [h.proto.body for h in at.get("html") if "spot_step_" in h.proto.body]
    return 1 if "spot_step_2" in hidden[-1] else 2


def test_spotted_asks_for_the_breed_first_then_the_details(at):
    sign_up(at)
    assert spot_step(at) == 1
    click(at, "Continue")  # no breed yet: stays on step 1 and says so
    assert spot_step(at) == 1 and at.warning

    at.selectbox(key="sighting_breed").set_value("Beagle")
    click(at, "Continue")
    assert spot_step(at) == 2
    summary = "".join(m.value for m in at.markdown if "spot-breed" in m.value)
    assert "Beagle" in summary and "New for your life list" in summary

    click(at, "Change breed or photo")  # back to step 1, with the breed still picked
    assert spot_step(at) == 1
    assert at.selectbox(key="sighting_breed").value == "Beagle"
    at.selectbox(key="sighting_breed").set_value("Pug")
    click(at, "Continue")
    at.text_area(key="sighting_notes").input("Snoring on a bench")
    click(at, "Spotted!")

    sighting = at.session_state["backend"].list_sightings()[0]
    assert (sighting["breed"], sighting["notes"]) == ("Pug", "Snoring on a bench")
    assert "Pug" in at.success[0].value
    assert spot_step(at) == 1  # ready for the next dog
    assert at.selectbox(key="sighting_breed").value is None


def test_badges_are_grouped_by_type(at):
    sign_up(at)
    track = at.segmented_control(key="badge_track")
    assert track.value == "lifer"
    at.session_state["badge_track"] = "purebred"
    at.run()
    page = "".join(m.value for m in at.markdown)
    assert "Next up</div><b>Pedigree pal</b>" in page and "0/10 breeds" in page
    assert any(e.label == "Still to earn (5)" for e in at.expander)

def face_balloons(at: AppTest) -> str:
    """The lifer celebration's HTML, or "" if nothing is floating up."""
    return next((m.value for m in at.markdown if 'class="face-balloons"' in m.value), "")


def test_a_lifer_floats_the_breeds_face_up_instead_of_balloons(at):
    sign_up(at)
    log_breed(at, "Beagle")
    floating = face_balloons(at)
    assert floating.count('class="face-balloon"') == logic.FACE_BALLOONS
    photos = set(re.findall(r"background-image:url\(&quot;(.*?)&quot;", floating))
    assert len(photos) == 1  # every circle is the Beagle's face
    log_breed(at, "Beagle")
    assert not face_balloons(at)  # only for a lifer


def test_a_cross_lifer_floats_both_parents_faces(at):
    sign_up(at)
    log_cross(at, "Labrador Retriever", "Poodle")
    photos = set(re.findall(r"background-image:url\(&quot;(.*?)&quot;", face_balloons(at)))
    assert len(photos) == 2
