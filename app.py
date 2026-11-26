"""Project Cerberus: log the dogs you spot and build your breed life list.

Run with:  streamlit run app.py
"""
import dataclasses
import datetime as dt
import html
import os
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

CERBERUS_DIR = Path(__file__).resolve().parent / "cerberus"


def drop_stale_cerberus_modules() -> bool:
    """Forget old copies of the cerberus/ modules after a deploy changed their files.

    Streamlit Community Cloud updates the files on a deploy, but the running server can
    keep the cerberus modules it imported earlier. New app.py code then meets old helpers
    and crashes (e.g. "AttributeError: ... has no attribute 'my_profile'"). If any
    cerberus/*.py file is newer than the package import, drop the cached modules so the
    imports below load the new ones. Returns True if it did.
    """
    package = sys.modules.get("cerberus")
    if package is None:
        return False
    newest = max(path.stat().st_mtime for path in CERBERUS_DIR.glob("*.py"))
    if newest <= getattr(package, "LOADED_AT", 0):  # older packages had no LOADED_AT
        return False
    for name in [n for n in sys.modules if n == "cerberus" or n.startswith("cerberus.")]:
        del sys.modules[name]
    return True


drop_stale_cerberus_modules()

# These come after the stale-module check above, on purpose.
from cerberus import logic  # noqa: E402
from cerberus.backends import AuthError, MemoryBackend, SupabaseBackend  # noqa: E402
from cerberus.oauth import PENDING, with_query, with_trailing_slash  # noqa: E402
from cerberus.remember import MAX_AGE_DAYS, SAVED_SIGN_IN_JS  # noqa: E402

st.set_page_config(
    page_title="Project Cerberus",
    page_icon="🐕",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Mobile-first styling. Streamlit has no built-in "phone app" mode, so this small
# stylesheet does the rest: a phone-width column (also on desktop), 16px inputs so
# iPhones don't zoom in when you tap a field, comfortable tap targets, and on
# phones a bottom tab bar within thumb reach.
MOBILE_CSS = """
<style>
[data-testid="stMainBlockContainer"] {
    max-width: 560px;
    padding: 1rem 1rem 6rem;
}
input, textarea { font-size: 16px !important; }
.st-key-saved_sign_in { display: none; }  /* invisible "Keep me signed in" helper */
button { min-height: 2.75rem; }

/* Life list and sightings rows */
.cerb-row {
    display: flex; align-items: center; gap: .75rem;
    padding: .6rem .25rem; border-bottom: 1px solid rgba(128, 128, 128, .2);
}
/* A small square photo of the breed, zoomed in on its face (".face", from
   data/breed_faces.csv; a plain "img" crops the middle-top where the head usually is).
   Breeds you've seen are in colour with a tick; ones still to find are faded grey. */
.face { display: block; width: 100%; height: 100%; background-repeat: no-repeat; }
.cerb-row .thumb {
    position: relative; flex: none; width: 3rem; height: 3rem;
    border-radius: .5rem; overflow: hidden; background: rgba(128, 128, 128, .15);
}
.cerb-row .thumb img {
    display: block; width: 100%; height: 100%; object-fit: cover; object-position: 50% 30%;
}
.cerb-row.missing .thumb img, .cerb-row.missing .thumb .face { filter: grayscale(1); opacity: .5; }
.cerb-row .thumb .tick {
    position: absolute; right: .1rem; bottom: .1rem; font-size: .75rem; line-height: 1;
}
.cerb-row .main { flex: 1; min-width: 0; }
.cerb-row .name { font-weight: 600; }
.cerb-row .sub { font-size: .85rem; opacity: .7; }
.cerb-row .rank { font-size: .8rem; opacity: .6; }
.cerb-row.missing .name { font-weight: 400; opacity: .75; }

/* Tap a life list row to open that breed's profile (photo, intro, fun fact) below it.
   A plain HTML details element (don't write HTML tags in this stylesheet: st.html
   would strip the whole thing), so it opens instantly without a rerun, and the photo only
   downloads once the row is opened. */
.cerb-breed > summary { list-style: none; cursor: pointer; }
.cerb-breed > summary::-webkit-details-marker { display: none; }
.cerb-row .chev { opacity: .45; transition: transform .15s; }
.cerb-breed[open] .chev { transform: rotate(90deg); }
.cerb-profile {
    padding: .75rem .25rem 1rem; border-bottom: 1px solid rgba(128, 128, 128, .2);
}
.cerb-profile img {
    display: block; max-width: 100%; max-height: 18rem; margin: 0 auto;
    border-radius: .5rem;
}
.cerb-profile .credit { font-size: .72rem; opacity: .6; text-align: center; margin: .3rem 0 .6rem; }
.cerb-profile .credit a { color: inherit; }
.cerb-profile p { margin: 0 0 .6rem; }
.cerb-profile .facts { margin: 0 0 .6rem; font-size: .9rem; }
.cerb-profile .facts b { font-weight: 600; }
.cerb-profile .fun {
    padding: .6rem .75rem; border-radius: .5rem; font-size: .9rem;
    background: rgba(232, 131, 58, .12);  /* primaryColor, faint */
}

/* Social feed posts: avatar on the left, who/when, then the sighting */
.cerb-post {
    display: flex; gap: .75rem; padding: .75rem .25rem;
    border-bottom: 1px solid rgba(128, 128, 128, .2);
}
.cerb-post .avatar { font-size: 1.6rem; line-height: 1.2; width: 2.25rem; text-align: center; flex: none; }

/* Member pictures: a breed photo in a circle (".pic"), or an older emoji pick */
.avatar.pic, .me-avatar.pic {
    display: block; border-radius: 50%; overflow: hidden; background: rgba(128, 128, 128, .15);
}
.avatar.pic { width: 2.25rem; height: 2.25rem; }
.avatar.pic img, .me-avatar.pic img {
    display: block; width: 100%; height: 100%; object-fit: cover; object-position: 50% 30%;
}
.me-avatar { display: block; font-size: 2.6rem; line-height: 1; }
.me-avatar.pic { width: 3.5rem; height: 3.5rem; }
/* The picker + preview row: don't scroll inside itself (that clipped the label) */
.st-key-avatar_row { overflow: visible; }
.cerb-post .main { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.cerb-post .who { font-size: .85rem; opacity: .75; }
.cerb-post .breed { font-weight: 600; }
.cerb-post .sub { font-size: .85rem; opacity: .75; }

/* A sighting's own photo, on its card in Profile > Your sightings */
.sighting-photo {
    display: block; width: 100%; max-height: 20rem; object-fit: cover; border-radius: .5rem;
}

/* Bottom tab bar: the main tabs, pinned to the bottom of the screen like a phone
   app. Five equal slots, each an icon above a short label. On wider screens the
   side padding lines the tabs up with the 560px content column. */
.st-key-main_nav [role="tablist"] {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 100;
    gap: 0;
    padding: 0 max(0px, calc((100vw - 560px) / 2)) env(safe-area-inset-bottom);
    background: #FFFFFF;  /* matches [theme.light] in .streamlit/config.toml */
    border-top: 1px solid rgba(128, 128, 128, .25);
}
.st-key-main_nav [data-testid="stTab"] {
    flex: 1; min-width: 0; height: 3.75rem; padding: 0 .1rem;
    justify-content: center;
}
.st-key-main_nav [data-testid="stTab"] p {
    white-space: pre-line;  /* the line break in each label puts the icon on its own line */
    text-align: center; font-size: .72rem; line-height: 1.25;
}
.st-key-main_nav [data-testid="stTab"] p::first-line { font-size: 1.3rem; }
@media (prefers-color-scheme: dark) {
    .st-key-main_nav [role="tablist"] { background: #171614; }  /* [theme.dark] */
}
/* Streamlit Community Cloud pins its own badge (46px tall, ~140px wide) to the
   bottom-right corner, on top of the app, where the app can't move it. On narrow
   screens it would cover the last tabs, so lift the tabs above it: the bar's
   background still reaches the bottom edge and the badge sits in that strip. On
   wider screens the centred tabs stop short of the corner. */
@media (max-width: 840px) {
    [data-testid="stMainBlockContainer"] { padding-bottom: 9rem; }
    .st-key-main_nav [role="tablist"] {
        padding-bottom: calc(3rem + env(safe-area-inset-bottom));
    }
}
</style>
"""
st.html(MOBILE_CSS)

DEMO_NOTICE = (
    "**Demo mode:** no Supabase keys are configured, so accounts and sightings "
    "only last until you close this tab."
)


def make_backend():
    """Use Supabase when its keys are in secrets, otherwise fall back to demo mode."""
    if os.environ.get("CERBERUS_DEMO") == "1":
        return MemoryBackend()
    try:
        cfg = st.secrets["supabase"]
        url, key = cfg["url"], cfg["key"]
    except Exception:  # no secrets file, or no [supabase] section
        return MemoryBackend()
    if "YOUR-PROJECT-REF" in url or key.endswith("..."):  # template not filled in yet
        return MemoryBackend()
    return SupabaseBackend(url, key)


def file_version(*paths: Path) -> tuple[float, ...]:
    """When these files last changed. Passing this to a cached loader makes st.cache_data
    read the files again after a deploy edits them (it only notices changed arguments)."""
    return tuple(path.stat().st_mtime for path in paths)


@st.cache_data
def load_breeds(version: tuple) -> pd.DataFrame:  # no "_": st.cache_data skips _args
    return logic.load_breeds()


@st.cache_data
def load_breed_profiles(version: tuple) -> dict[str, logic.BreedProfile]:
    return logic.load_breed_profiles()


def refresh_stale_backend():
    """After a deploy reloaded cerberus/, a signed-in visitor's backend is still an object
    of the old class, missing any new methods. Rebuild it from the new class and carry
    its contents over (Supabase client, signed-in user), so nobody gets signed out."""
    old = st.session_state.get("backend")
    if old is None or isinstance(old, (MemoryBackend, SupabaseBackend)):
        return
    new = make_backend()
    if type(new).__name__ == type(old).__name__:
        new.__dict__.update(old.__dict__)  # attributes new in this version keep their defaults
    else:
        st.session_state.pop("user", None)
    st.session_state.backend = new


# One backend per browser session, so sign-ins are never shared between visitors.
refresh_stale_backend()
if "backend" not in st.session_state:
    st.session_state.backend = make_backend()
backend = st.session_state.backend


def end_session(message: str | None = None):
    st.session_state.pop("user", None)
    st.session_state.pop("remember", None)
    if message:
        st.session_state.auth_notice = message
    st.rerun()


# --- Continue with Google ---------------------------------------------------------------
# 1. The button links to Google, with a return address of this app plus `?flow=<id>`.
#    Google refuses to show its sign-in page inside the frame that Streamlit Community
#    Cloud wraps apps in, so the whole browser tab has to go there. That frame blocks
#    links from leaving it, so SAME_TAB_SIGN_IN_JS hands the trip to the page around
#    it instead (see below). If that ever fails, the button opens a new tab.
# 2. Google sends the user back here with `?flow=<id>&code=<one-time code>`. That's a
#    fresh Streamlit session, so the verifier needed to finish is fetched from PENDING
#    (see cerberus/oauth.py) using the flow id.
def app_url() -> str:
    """Where Google should send people back to: this app, as the browser sees it."""
    try:
        url = st.secrets["supabase"]["redirect_url"]  # optional override
    except Exception:
        url = st.context.url or "http://localhost:8501/"
    return with_trailing_slash(url)


# When the Google button is clicked, go to Google in this same tab rather than opening a
# second one. Streamlit Cloud's frame is not allowed to send the tab elsewhere, but the
# page around it is on the same site, so we put a link on that page and click it there.
# If the outer page can't be reached, nothing is cancelled and the button's own
# open-in-a-new-tab behaviour takes over. Running locally there's no frame at all, so
# window.top is just this page.
SAME_TAB_SIGN_IN_JS = """
<script>
if (!window.cerberusSameTabSignIn) {
  window.cerberusSameTabSignIn = true;
  document.addEventListener("click", (event) => {
    const link = event.target.closest(".st-key-google_sign_in a[href]");
    if (!link) return;
    let page;
    try { page = window.top.document; } catch (err) { return; }
    event.preventDefault();
    const hop = page.createElement("a");
    hop.href = link.href;
    page.body.appendChild(hop);
    hop.click();
  }, true);
}
</script>
"""


def google_sign_in_url(remember: bool) -> str:
    """One sign-in link per visit, remade only once its flow has expired or the
    "Keep me signed in" box changes (the choice rides along in the return address)."""
    url, flow_id, linked_remember = st.session_state.get("google_link", (None, None, None))
    if url is None or flow_id not in PENDING or linked_remember != remember:
        flow_id = PENDING.new_flow_id()
        return_to = with_query(app_url(), flow=flow_id, remember="1" if remember else "0")
        url, verifier = backend.start_google_sign_in(return_to)
        PENDING.add(flow_id, verifier)
        st.session_state.google_link = (url, flow_id, remember)
    return url


def finish_google_sign_in():
    """If Google just sent the user back here, finish signing them in."""
    params = st.query_params
    code, flow_id, error = params.get("code"), params.get("flow"), params.get("error")
    if not (code or error):
        return
    remember = params.get("remember") == "1"  # read before clearing the address bar
    st.query_params.clear()  # so a refresh doesn't try to reuse the one-time code
    if error:
        st.session_state.auth_notice = ("Google sign-in was cancelled or failed: "
                                        + params.get("error_description", error))
        return
    verifier = PENDING.pop(flow_id) if flow_id else None
    if verifier is None:
        st.session_state.auth_notice = "That Google sign-in link expired. Please try again."
        return
    try:
        st.session_state.user = backend.finish_google_sign_in(code, verifier)
    except AuthError as err:
        st.session_state.auth_notice = str(err)
    else:
        st.session_state.remember = remember


# --- Keep me signed in ----------------------------------------------------------------
# See cerberus/remember.py. An invisible component keeps the browser's saved sign-in (a
# single-use refresh token) in step with this visit, and reports what was saved.
saved_sign_in_store = st.components.v2.component("cerberus_saved_sign_in",
                                                 js=SAVED_SIGN_IN_JS)


def sync_saved_sign_in() -> str | None:
    """Mount the component. Returns what the browser had saved: a token, "" for nothing,
    or None until it has reported. Once it has, it's told to save the current token
    (or nothing), so a new token from a sign-in, return visit or hourly refresh is kept."""
    data = {}
    if st.session_state.get("saved_read"):
        data["save"] = backend.refresh_token() if st.session_state.get("remember") else None
    result = saved_sign_in_store(key="saved_sign_in", data=data,
                                 on_saved_change=lambda: None)
    return result.saved


def resume_saved_sign_in(saved: str | None):
    """The first time the browser reports, sign back in with its saved token if we can."""
    if saved is None or st.session_state.get("saved_read"):
        return
    st.session_state.saved_read = True
    if saved and "user" not in st.session_state:
        try:
            st.session_state.user = backend.resume_session(saved)
        except AuthError:
            pass  # expired or signed out elsewhere: the rerun below deletes it
        else:
            st.session_state.remember = True
    st.rerun()  # so the browser saves the new token (or forgets the dead one) straight away


# --- Sign in / create account ---------------------------------------------------------
def auth_screen():
    st.title("🐕 Project Cerberus")
    st.write("Spot dogs. Collect breeds. Can you find all 100?")
    if backend.demo:
        st.warning(DEMO_NOTICE)
    notice = st.session_state.pop("auth_notice", None)
    if notice:
        st.info(notice)

    remember = st.checkbox(f"Keep me signed in for {MAX_AGE_DAYS} days", value=True,
                           key="keep_signed_in",
                           help="Untick this on a shared or public computer.")
    st.link_button("Continue with Google", google_sign_in_url(remember), type="primary",
                   width="stretch", key="google_sign_in")
    st.html(SAME_TAB_SIGN_IN_JS, unsafe_allow_javascript=True)
    st.caption("New here? This creates your account too.")
    st.divider()
    st.caption("Or use your email and a password:")

    sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("sign_in"):
            email = st.text_input("Email", key="sign_in_email", type="email",
                                  autocomplete="email")
            password = st.text_input("Password", type="password", key="sign_in_password",
                                     autocomplete="current-password")
            if st.form_submit_button("Sign in", type="primary", width="stretch"):
                try:
                    st.session_state.user = backend.sign_in(email, password)
                except AuthError as err:
                    st.error(str(err))
                else:
                    st.session_state.remember = remember
                    st.rerun()

    with sign_up_tab:
        with st.form("sign_up"):
            username = st.text_input("Username", key="sign_up_username",
                                     autocomplete="username",
                                     help="Shown on your life list. 3 to 30 characters.")
            email = st.text_input("Email", key="sign_up_email", type="email",
                                  autocomplete="email")
            password = st.text_input("Password", type="password", key="sign_up_password",
                                     autocomplete="new-password",
                                     help="At least 8 characters.")
            confirm = st.text_input("Confirm password", type="password", key="sign_up_confirm",
                                    autocomplete="new-password")
            if st.form_submit_button("Create account", type="primary", width="stretch"):
                if password != confirm:
                    st.error("Passwords don't match.")
                else:
                    try:
                        user = backend.sign_up(email, password, username)
                    except AuthError as err:
                        st.error(str(err))
                    else:
                        if user is None:
                            st.success("Nearly there! Check your inbox for a confirmation "
                                       "link, then come back and sign in.")
                        else:
                            st.session_state.user = user
                            st.session_state.remember = remember
                            st.rerun()


if "user" not in st.session_state:
    finish_google_sign_in()
resume_saved_sign_in(sync_saved_sign_in())
if "user" not in st.session_state:
    auth_screen()
    st.stop()

user = st.session_state.user

if backend.demo:
    st.caption("⚠️ Demo mode: accounts and sightings vanish when you close this tab.")

# --- Load this spotter's data ---------------------------------------------------------------
breeds = load_breeds(file_version(logic.BREEDS_CSV))
breed_profiles = load_breed_profiles(
    file_version(logic.BREED_INFO_CSV, logic.BREED_PHOTOS_CSV, logic.BREED_FACES_CSV))


def breed_photo_html(profile: logic.BreedProfile, label: str = "") -> str:
    """A breed's photo filling a small square or circle, zoomed in on the dog's face
    (breed_faces.csv), or a plain thumbnail if it has no crop. label = text for screen
    readers; empty means decorative, so a photo that fails to load leaves a plain shape."""
    face = logic.face_photo(profile)
    if face:
        url, css = face
        name = f' role="img" aria-label="{html.escape(label)}"' if label else ""
        return (f'<span class="face"{name} style="background-image:url(&quot;{html.escape(url)}'
                f'&quot;);{css}"></span>')
    return (f'<img src="{html.escape(logic.thumbnail_url(profile.image_url))}" '
            f'alt="{html.escape(label)}" loading="lazy">')


def avatar_html(avatar: str, css: str) -> str:
    """A member's picture: their chosen breed's photo in a circle, or an older emoji pick."""
    photo = breed_profiles.get(avatar)
    if photo and photo.image_url:
        return f'<span class="{css} pic">{breed_photo_html(photo, avatar)}</span>'
    return f'<span class="{css}">{html.escape(avatar)}</span>'


try:
    sightings = logic.sightings_frame(backend.list_sightings())
except AuthError as err:
    end_session(str(err))

# Your profile (made on first sign-in). If the profiles table isn't set up yet, carry on
# with a stand-in so the rest of the app still works; Profile editing and Social wait.
try:
    profile, profiles_ready = backend.my_profile(), True
except AuthError as err:
    end_session(str(err))
except Exception:
    profile, profiles_ready = logic.new_profile(user.username), False
user = dataclasses.replace(user, username=profile["username"])  # the name others see


def close_sharing_notice():
    st.session_state.pop("sharing_notice", None)


@st.dialog("Your sightings are shared", on_dismiss=close_sharing_notice)
def sharing_notice():
    """Shown once, when a new member's profile is made, so sharing is never a surprise.
    It stays open (across reruns) until they pick a button or close it."""
    st.write("Other members can see the dogs you log in the **Social** tab, including "
             "where you saw them. Your email is never shown.")
    st.write("You can change this any time in **Settings > Privacy**.")
    with st.container(horizontal=True):
        if st.button("Keep sharing", type="primary", key="notice_keep_sharing",
                     width="stretch"):
            close_sharing_notice()
            st.rerun()
        if st.button("Turn sharing off", key="notice_stop_sharing", width="stretch"):
            try:
                backend.save_profile({**profile, "share_sightings": False})
            except AuthError as err:
                end_session(str(err))
            except Exception:
                st.error("That didn't save. Please try again in Settings > Privacy.")
            else:
                # The Settings switch still says "on" in the browser; set it to match below,
                # or it would save sharing straight back on.
                st.session_state.share_switch_to = False
                close_sharing_notice()
                st.rerun()


if backend.profile_is_new:  # first visit: their profile (sharing on) was just made
    backend.profile_is_new = False
    st.session_state.sharing_notice = profiles_ready
if st.session_state.get("sharing_notice"):
    sharing_notice()

life = logic.life_list(breeds, sightings)
seen = life["times_seen"] > 0
collected, total = int(seen.sum()), len(life)

flash = st.session_state.pop("flash", None)
if flash:
    kind, breed_name = flash
    if kind == "lifer":
        st.balloons()
        st.success(f"🎉 New lifer! **{breed_name}** is on your life list.")
    else:
        st.info(f"Logged another **{breed_name}**.")
photo_problem = st.session_state.pop("photo_problem", None)
if photo_problem:
    st.warning(photo_problem)

# The five main tabs. The "main_nav" key lets MOBILE_CSS pin them to the bottom of the
# screen as a tab bar; the "\n" puts each icon above its label.
NAV_TABS = ["🔍\nDog ID", "📋\nLife list", "👤\nProfile", "👥\nSocial", "⚙️\nSettings"]
SETTINGS_TAB = NAV_TABS[-1]


@st.cache_data
def load_whats_new(version: tuple) -> tuple[list[logic.Release], list[logic.RoadmapItem]]:
    """Releases from CHANGELOG.md and upcoming features from ROADMAP.md (read once per deploy)."""
    changelog = logic.CHANGELOG_MD.read_text(encoding="utf-8")
    roadmap = logic.ROADMAP_MD.read_text(encoding="utf-8")
    return logic.parse_changelog(changelog), logic.upcoming_features(roadmap)


releases, upcoming = load_whats_new(file_version(logic.CHANGELOG_MD, logic.ROADMAP_MD))
APP_VERSION = releases[0].version if releases else "dev"

# The "new update" dot on Settings. Opening Settings counts as seeing the latest update:
# the tabs below rerun the app when you switch, and st.session_state.main_tab says which
# tab is open. The version you've seen is saved to your account, so it follows you
# between devices.
NEW_UPDATE_DOT_CSS = """
<style>
.st-key-main_nav [data-testid="stTab"]:last-of-type { position: relative; }
.st-key-main_nav [data-testid="stTab"]:last-of-type::after {  /* new-update-dot */
    content: ""; position: absolute; top: .45rem; left: calc(50% + .55rem);
    width: .6rem; height: .6rem; border-radius: 50%;
    background: #E8833A;  /* primaryColor in .streamlit/config.toml */
}
</style>
"""
latest = releases[0].version if releases else None
try:
    unseen = logic.has_unseen_update(latest, backend.seen_version())
    if unseen and st.session_state.get("main_tab") == SETTINGS_TAB:
        backend.mark_version_seen(latest)
        st.session_state.new_update = latest  # show a "New" badge on it this visit
        unseen = False
except AuthError as err:
    end_session(str(err))
except Exception:  # the dot is a nice-to-have: never let it break the app
    unseen = False
if unseen:
    st.html(NEW_UPDATE_DOT_CSS)

with st.container(key="main_nav"):
    tab_id, tab_life, tab_profile, tab_social, tab_settings = st.tabs(
        NAV_TABS, key="main_tab", on_change="rerun")

# --- Dog ID: identify a dog and log the sighting ---------------------------------------------
with tab_id:
    st.header("Dog ID")
    seen_breeds = set(life.loc[seen, "breed"])

    def breed_label(name: str) -> str:
        return name if name in seen_breeds else f"{name}  ✨ new"

    with st.form("log_sighting", clear_on_submit=True, border=False):
        breed = st.selectbox(
            "Breed",
            breeds["breed"].tolist(),
            index=None,
            format_func=breed_label,
            placeholder="Start typing a breed…",
        )
        seen_on = st.date_input("Date seen", value=dt.date.today(), max_value=dt.date.today())
        dog_name = st.text_input("Dog's name (if you found out)")
        location = st.text_input(
            "Where", placeholder="e.g. Hyde Park",
            help="Other members can see this in Social if you share your sightings "
                 "(Settings > Privacy).")
        notes = st.text_area("Notes", placeholder="Good boy. Very fluffy.", height=80)
        # On a phone this offers the camera as well as the photo library.
        photo = st.file_uploader(
            "Photo (optional)", type=logic.PHOTO_TYPES, key="sighting_photo",
            max_upload_size=logic.MAX_PHOTO_UPLOAD_MB,
            help="Only you can see your photos. They're saved smaller, without the "
                 "location your phone may have stored in them.")
        submitted = st.form_submit_button("Log sighting", type="primary", width="stretch")

    st.caption("📷 Photo ID (identify a dog from a photo) is on the roadmap. "
               "For now, pick the breed yourself.")

    if submitted:
        if breed is None:
            st.warning("Pick a breed first.")
        else:
            lifer = logic.is_lifer(sightings, breed)
            photo_path = None
            if photo is not None:
                try:
                    photo_path = backend.add_photo(logic.prepare_photo(photo.getvalue()))
                except AuthError as err:
                    end_session(str(err))
                except ValueError as err:  # not an image
                    st.session_state.photo_problem = f"{err} The sighting was logged without it."
                except Exception:  # storage not set up or unreachable: still log the dog
                    st.session_state.photo_problem = ("Your photo couldn't be saved, so the "
                                                      "sighting was logged without it.")
            try:
                backend.add_sighting(breed, seen_on, location, dog_name, notes, photo_path)
            except AuthError as err:
                end_session(str(err))
            st.session_state.flash = ("lifer" if lifer else "repeat", breed)
            st.rerun()

# --- Life list ----------------------------------------------------------------------------------
def breed_profile_html(profile: logic.BreedProfile | None) -> str:
    """A breed's photo, intro, origin, temperament and fun fact (all text escaped)."""
    if profile is None:
        return '<div class="cerb-profile"><p>No profile for this breed yet.</p></div>'
    esc = html.escape
    photo = ""
    if profile.image_url:
        licence = f", {esc(profile.licence)}" if profile.licence else ""
        photo = (
            f'<img src="{esc(profile.image_url)}" alt="A {esc(profile.breed)}" loading="lazy">'
            f'<div class="credit">Photo: <a href="{esc(profile.source)}" target="_blank" '
            f'rel="noopener">{esc(profile.credit)}</a>{licence}, via Wikimedia Commons</div>'
        )
    return (
        f'<div class="cerb-profile">{photo}<p>{esc(profile.intro)}</p>'
        f'<div class="facts"><b>From:</b> {esc(profile.origin)}<br>'
        f'<b>Temperament:</b> {esc(profile.temperament)}</div>'
        f'<div class="fun">💡 <b>Fun fact:</b> {esc(profile.fun_fact)}</div></div>'
    )


def breed_thumb(profile: logic.BreedProfile | None, tick: bool = False) -> str:
    """A breed's small square photo (an empty grey square if it has none)."""
    img = breed_photo_html(profile) if profile and profile.image_url else ""
    return f'<span class="thumb">{img}{"<span class=tick>✅</span>" if tick else ""}</span>'


def life_row(row, profile: logic.BreedProfile | None) -> str:
    """One breed as a compact list row (a wide table is hard to read on a phone).
    Tapping the row opens the breed's profile underneath it."""
    if row.times_seen:
        css, seen = "cerb-row", True
        detail = f"First seen {row.first_seen} · seen {row.times_seen}×"
    else:
        css, seen, detail = "cerb-row missing", False, "Not spotted yet"
    return (
        f'<details class="cerb-breed"><summary class="{css}">{breed_thumb(profile, tick=seen)}'
        f'<div class="main"><div class="name">{html.escape(row.breed)}</div>'
        f'<div class="sub">{detail}</div></div>'
        f'<span class="rank">#{row.rank}</span><span class="chev">›</span></summary>'
        f'{breed_profile_html(profile)}</details>'
    )


with tab_life:
    st.header(f"{user.username}'s life list")
    # Three small stat cards side by side, even on a narrow phone (st.columns would stack them).
    with st.container(horizontal=True, wrap=False, gap="small"):
        st.metric("Lifers", f"{collected}/{total}", border=True)
        st.metric("Sightings", len(sightings), border=True)
        st.metric("To find", total - collected, border=True)
    st.progress(collected / total if total else 0.0)

    show = st.segmented_control(
        "Show", logic.LIFE_LIST_FILTERS, default="All", required=True,
        key="life_filter", label_visibility="collapsed", width="stretch",
    )
    query = st.text_input("Search breeds", key="life_search", type="search",
                          placeholder="Search breeds", label_visibility="collapsed")
    view = logic.filter_life_list(life, show, query)
    if view.empty:
        st.info("No breeds match.")
    else:
        st.markdown("".join(life_row(r, breed_profiles.get(r.breed)) for r in view.itertuples()),
                    unsafe_allow_html=True)
    st.caption("Tap a breed to see a photo and a short intro. "
               "Breeds ranked by AKC 2025 popularity. Photos from Wikimedia Commons.")

# --- Your profile: who you are, plus every sighting you've logged ------------------------------
def dogs_text(dogs: list[dict]) -> str:
    return ", ".join(f"{d['name']} ({d['breed']})" if d.get("breed") else d["name"] for d in dogs)


def profile_editor():
    """Username, picture, favourite breed and your own dogs. Saved with one button."""
    breed_names = breeds["breed"].tolist()
    name = st.text_input("Username", value=profile["username"], key="profile_username",
                         max_chars=logic.MAX_USERNAME_LENGTH)
    with st.container(horizontal=True, wrap=False, vertical_alignment="bottom",
                      key="avatar_row"):
        avatar = st.selectbox(
            "Profile picture", breed_names, key="profile_avatar",
            placeholder="Pick a breed",
            index=breed_names.index(profile["avatar"]) if profile["avatar"] in breed_names else None)
        st.markdown(avatar_html(avatar or profile["avatar"], "me-avatar"),  # live preview
                    unsafe_allow_html=True, width="content")
    favourite = st.selectbox(
        "Favourite breed", breed_names, key="profile_favourite", placeholder="Pick a breed",
        index=breed_names.index(profile["favourite_breed"])
        if profile["favourite_breed"] in breed_names else None)
    dogs = []
    if st.toggle("I have a dog", value=bool(profile["dogs"]), key="profile_has_dogs"):
        count = st.number_input("How many dogs?", min_value=1, max_value=logic.MAX_DOGS,
                                value=max(1, len(profile["dogs"])), key="profile_dog_count")
        own_breeds = breed_names + [logic.MIXED_BREED]
        for i in range(int(count)):
            old = profile["dogs"][i] if i < len(profile["dogs"]) else {}
            with st.container(border=True):
                dog_name = st.text_input(f"Dog {i + 1}: name", value=old.get("name", ""),
                                         key=f"profile_dog_name_{i}")
                dog_breed = st.selectbox(
                    f"Dog {i + 1}: breed", own_breeds, key=f"profile_dog_breed_{i}",
                    placeholder="Pick a breed (optional)",
                    index=own_breeds.index(old["breed"]) if old.get("breed") in own_breeds else None)
                dogs.append({"name": dog_name, "breed": dog_breed})
    if st.button("Save profile", type="primary", width="stretch", key="save_profile"):
        try:
            backend.save_profile({**profile, "username": name, "favourite_breed": favourite,
                                  "avatar": avatar or profile["avatar"], "dogs": dogs})
        except ValueError as err:
            st.error(str(err))
        except AuthError as err:
            end_session(str(err))
        except Exception:
            st.error("Your profile didn't save. Please try again.")
        else:
            st.session_state.profile_saved = True
            st.rerun()


def sighting_photo_links() -> dict[str, str]:
    """Links to show your sighting photos. Storage links expire after an hour, so they're
    kept in this browser session for 50 minutes rather than fetched again every rerun."""
    links = st.session_state.setdefault("photo_links", {})  # path -> (link, fetched at)
    now = time.time()
    wanted = [p for p in sightings["photo_path"].dropna().unique()
              if p not in links or now - links[p][1] > 50 * 60]
    if wanted:
        try:
            fresh = backend.photo_urls(list(wanted))
        except AuthError as err:
            end_session(str(err))
        except Exception:  # photos are extras: never let them break the Profile tab
            fresh = {}
        links.update({p: (link, now) for p, link in fresh.items()})
    return {p: link for p, (link, _) in links.items()}


with tab_profile:
    st.header("Your profile")
    if st.session_state.pop("profile_saved", False):
        st.success("Profile saved.")
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.markdown(avatar_html(profile["avatar"], "me-avatar"), unsafe_allow_html=True,
                        width="content")
            st.markdown(f"### {user.username}")
        if profile["favourite_breed"]:
            st.markdown(f"❤️ Favourite breed: **{profile['favourite_breed']}**")
        if profile["dogs"]:
            st.markdown(f"🐕 {'My dog' if len(profile['dogs']) == 1 else 'My dogs'}: "
                        f"{dogs_text(profile['dogs'])}")
        if sightings.empty:
            st.caption("No sightings yet.")
        else:
            st.caption(f"Spotting since {sightings['seen_on'].min()} · "
                       f"{collected} lifer{'' if collected == 1 else 's'} from "
                       f"{len(sightings)} sighting{'' if len(sightings) == 1 else 's'}")
    if profiles_ready:
        with st.expander("✏️ Edit profile"):
            profile_editor()

    st.subheader("Your sightings")
    if sightings.empty:
        st.info("No sightings yet. Go find a dog!")
    photo_links = sighting_photo_links() if tab_profile.open else {}
    for s in logic.recent_first(sightings).itertuples():
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment="top",
                              horizontal_alignment="distribute"):
                st.markdown(f"**{s.breed}**  \n{s.seen_on}"
                            + (f" · {s.location}" if s.location else ""))
                with st.popover("🗑", help="Delete this sighting"):
                    st.write("Delete this sighting? This can't be undone.")
                    if st.button("Delete", key=f"delete_{s.id}", type="primary"):
                        try:
                            backend.delete_sighting(int(s.id))
                        except AuthError as err:
                            end_session(str(err))
                        st.rerun()
            if s.photo_path in photo_links:
                st.markdown(f'<img class="sighting-photo" src="{html.escape(photo_links[s.photo_path])}" '
                            f'alt="Your photo of a {html.escape(s.breed)}" loading="lazy">',
                            unsafe_allow_html=True)
            if s.dog_name:
                st.caption(f"🐶 {s.dog_name}")
            if s.notes:
                st.caption(s.notes)

# --- Social: recent sightings from everyone who shares -------------------------------------
def feed_post(post: dict) -> str:
    """One sighting in the feed as HTML. Everything members typed is escaped."""
    seen_on = dt.date.fromisoformat(str(post["seen_on"]))
    who = f"<b>{html.escape(post['username'])}</b>" + (" (you)" if post["user_id"] == user.id else "")
    details = [f"📍 {html.escape(post['location'])}" if post.get("location") else "",
               f"🐶 {html.escape(post['dog_name'])}" if post.get("dog_name") else ""]
    lines = [" · ".join(d for d in details if d), html.escape(post.get("notes") or "")]
    return (
        f'<div class="cerb-post">{avatar_html(post["avatar"], "avatar")}'
        f'<div class="main"><div class="who">{who} · {seen_on.day} {seen_on:%b %Y}</div>'
        f'<div class="breed">{html.escape(post["breed"])}</div>'
        + "".join(f'<div class="sub">{line}</div>' for line in lines if line)
        + "</div></div>"
    )


with tab_social:
    st.header("Social")
    st.caption("The latest sightings from everyone who shares them. "
               "You can stop sharing yours in Settings > Privacy.")
    if tab_social.open:  # only fetch the feed when someone is looking at it
        try:
            feed = backend.social_feed() if profiles_ready else None
        except AuthError as err:
            end_session(str(err))
        except Exception:
            feed = None
        if feed is None:
            st.info("Social isn't available right now. Please try again later.")
        elif not feed:
            st.info("No sightings yet. Log a dog and you'll be the first!")
        else:
            st.markdown("".join(feed_post(p) for p in feed), unsafe_allow_html=True)

# --- Settings ------------------------------------------------------------------------------
def release_card(release: logic.Release, border: bool = True):
    released = dt.date.fromisoformat(release.date)
    # "New" marks the update that made the dot on Settings appear, for this visit.
    badge = " :orange-badge[New]" if st.session_state.get("new_update") == release.version else ""
    with st.container(border=border):
        st.markdown(f"**Version {release.version}: {release.title}**{badge}")
        st.caption(f"{released.day} {released:%B %Y}")
        st.markdown("\n".join(f"- {change}" for change in release.changes))


with tab_settings:
    st.header("Settings")
    st.subheader("Account")
    with st.container(border=True):
        st.write(f"Signed in as **{user.username}**")
        st.caption(user.email)
        if st.button("Sign out", width="stretch"):
            backend.sign_out()
            end_session()
    st.subheader("Privacy")
    if "share_switch_to" in st.session_state:  # changed from the new-member popup
        st.session_state.share_sightings = st.session_state.pop("share_switch_to")
    share = st.toggle("Share my sightings in Social", value=profile["share_sightings"],
                      key="share_sightings", disabled=not profiles_ready)
    st.caption("When this is on, other members can see your sightings in Social, "
               "including where you saw each dog. Your email is never shown.")
    if profiles_ready and share != profile["share_sightings"]:
        try:
            backend.save_profile({**profile, "share_sightings": share})
        except AuthError as err:
            end_session(str(err))
        except Exception:
            st.error("That didn't save. Please try again.")
        else:
            st.rerun()

    st.subheader("Appearance")
    st.caption("Light or dark mode follows your phone or computer setting.")

    # What's new: the latest release, with older ones folded away.
    st.subheader("What's new")
    if releases:
        release_card(releases[0])
        if len(releases) > 1:
            with st.expander("Earlier updates"):
                for release in releases[1:]:
                    release_card(release, border=False)

    # Coming next, with a +1 button per feature (one vote each, tap again to take it back).
    st.subheader("Coming next")
    st.caption("Tap +1 on the features you'd most like to see.")
    try:
        vote_counts, my_votes = backend.feature_vote_counts(), backend.my_feature_votes()
        voting = True
    except AuthError as err:
        end_session(str(err))
    except Exception:  # e.g. the vote tables haven't been created in Supabase yet
        vote_counts, my_votes, voting = {}, set(), False
        st.caption("Voting isn't available right now.")
    for item in upcoming:
        with st.container(border=True):
            # wrap=False keeps the +1 on the right, even when the text is long on a phone.
            with st.container(horizontal=True, wrap=False, vertical_alignment="center",
                              horizontal_alignment="distribute"):
                st.markdown(item.text)
                if voting:
                    voted = item.key in my_votes
                    if st.button(f"+1 · {vote_counts.get(item.key, 0)}", key=f"vote_{item.key}",
                                 type="primary" if voted else "secondary",
                                 help="Take back your +1" if voted else "I want this next"):
                        try:
                            backend.set_feature_vote(item.key, not voted)
                        except AuthError as err:
                            end_session(str(err))
                        st.rerun()

    st.subheader("Suggest a feature")
    with st.form("suggest_feature", clear_on_submit=True):
        idea = st.text_area("Your idea", key="feature_suggestion",
                            max_chars=logic.MAX_SUGGESTION_LENGTH,
                            placeholder="I'd love to be able to…")
        if st.form_submit_button("Send idea", type="primary", width="stretch"):
            try:
                backend.suggest_feature(idea)
                st.success("Thanks! Your idea has been sent.")
            except ValueError as err:
                st.error(str(err))
            except AuthError as err:
                end_session(str(err))
            except Exception:
                st.error("Your idea couldn't be sent right now. Please try again later.")

    st.subheader("About")
    st.caption("Project Cerberus: spot dogs, collect breeds. Breeds are the AKC 2025 top 100.")
    st.caption(f"Version {APP_VERSION}")
