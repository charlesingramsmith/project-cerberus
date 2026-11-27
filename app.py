"""Project Cerberus: log the dogs you spot and build your breed life list.

Run with:  streamlit run app.py
"""
import base64
import dataclasses
import datetime as dt
import hashlib
import html
import os
import re
import sys
import time
import uuid
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
from cerberus.photo_id import PhotoID  # noqa: E402
from cerberus import places  # noqa: E402
from cerberus import sketches  # noqa: E402
from cerberus.remember import MAX_AGE_DAYS, SAVED_SIGN_IN_JS  # noqa: E402

st.set_page_config(
    page_title="Project Cerberus",
    page_icon="assets/icon.png",  # LOGO_ICON (defined below)
    layout="centered",
    initial_sidebar_state="collapsed",
)

# The logo: a pencil-drawn dachshund head (assets/logo.svg; light and dark built in).
# Shown big on the sign-in screen, then small at the top left.
LOGO = "assets/logo.svg"
LOGO_ICON = "assets/icon.png"  # the same head on a pistachio tile: clearer when small


def logo_html() -> str:
    """The logo drawn inline (not as a picture file) so its pencil lines take the app's
    own light or dark colours (--ink and --plum in MOBILE_CSS / DARK_CSS)."""
    drawing = Path(LOGO).read_text(encoding="utf-8")
    drawing = re.sub(r"<style>.*?</style>", "", drawing, flags=re.S)  # it follows the phone
    return f'<div class="cerb-logo">{drawing}</div>'

# Mobile-first styling. Streamlit has no built-in "phone app" mode, so this small
# stylesheet does the rest: a phone-width column (also on desktop), 16px inputs so
# iPhones don't zoom in when you tap a field, comfortable tap targets, and on
# phones a bottom tab bar within thumb reach.
MOBILE_CSS = """
<style>
/* Brand colours (match .streamlit/config.toml). Pistachio is the main colour, plum
   highlights lifers and badges. In dark mode DARK_CSS swaps in the dark-theme values. */
:root {
    --ink: #2E2A30;
    --pistachio: #BFD99A; --pistachio-soft: rgba(191, 217, 154, .35);
    --pistachio-text: #56763A; --plum: #8A5A83; --plum-soft: rgba(138, 90, 131, .14);
    --on-pistachio: #26222A;
}
/* Pastel pistachio is too pale for Streamlit's white button text: use dark text. */
[data-testid^="stBaseButton-primary"], [data-testid^="stBaseButton-primary"] p,
[data-testid="stBaseLinkButton-primary"], [data-testid="stBaseLinkButton-primary"] p {
    color: var(--on-pistachio) !important;
}
/* ...and the open tab's label and underline in a deeper green that's easy to read. */
[data-testid="stTab"][aria-selected="true"] p { color: var(--pistachio-text) !important; }
[data-baseweb="tab-highlight"] { background-color: var(--pistachio-text) !important; }
button[data-variant="segmented_control"][aria-checked="true"],
button[data-variant="segmented_control"][aria-checked="true"] * {
    color: var(--pistachio-text) !important;
}
/* Hand-drawn icons (cerberus/sketches.py) sit in a line of text at text size */
.sketch { display: inline-block; width: 1.2em; height: 1.2em; vertical-align: -.25em; }
.cerb-label { margin: 0 0 .25rem; }
/* The logo on the sign-in screen, in the theme's own pencil colour */
.cerb-logo svg { display: block; width: 7.5rem; height: auto; }
.cerb-logo .ink { color: var(--ink); }
.cerb-logo .collar { stroke: var(--plum); }
/* The header logo (st.logo): a little bigger than Streamlit's default */
[data-testid="stHeaderLogo"] { height: 2.5rem; }
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
/* Photo ID suggestions: a bigger photo of each suggested breed, to compare with yours */
.cerb-row.guess { border-bottom: none; padding: .25rem 0; }
.cerb-row.guess .thumb { width: 4.5rem; height: 4.5rem; }
.cerb-row .thumb img {
    display: block; width: 100%; height: 100%; object-fit: cover; object-position: 50% 30%;
}
.cerb-row.missing .thumb img, .cerb-row.missing .thumb .face { filter: grayscale(1); opacity: .5; }
.cerb-row .thumb .tick {  /* a sketched tick in a pistachio circle */
    position: absolute; right: .1rem; bottom: .1rem; display: flex; width: 1.05rem;
    height: 1.05rem; border-radius: 50%; background: var(--pistachio); color: var(--on-pistachio);
}
.cerb-row .thumb .tick .sketch { width: 100%; height: 100%; }
.cerb-row .thumb.icon { display: flex; align-items: center; justify-content: center; }
.cerb-row .thumb.icon .sketch { width: 1.9rem; height: 1.9rem; }  /* unverified: no photo */
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
    background: var(--pistachio-soft);
}

/* Badges on the profile: earned ones in colour, locked ones faded grey */
.cerb-badges {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(5.5rem, 1fr));
    gap: .5rem; margin: 0 0 1rem;
}
.cerb-badge {
    padding: .6rem .4rem; border-radius: .5rem; text-align: center;
    background: var(--plum-soft);
}
.cerb-badge .icon { display: block; line-height: 1; color: var(--plum); }
.cerb-badge .icon .sketch { width: 2.2rem; height: 2.2rem; }
.cerb-badge .name { font-weight: 600; font-size: .85rem; }
.cerb-badge .sub { font-size: .75rem; opacity: .7; }
.cerb-badge.locked { background: rgba(128, 128, 128, .1); }
.cerb-badge.locked .icon { color: inherit; opacity: .35; }
.cerb-badge.locked .name { font-weight: 400; opacity: .75; }
.cerb-badge.purebred { box-shadow: inset 0 0 0 2px var(--plum); }  /* rarer: a plum ring */
.cerb-badge.cross .icon { color: var(--pistachio-text); }
.cerb-badge.cross:not(.locked) { background: var(--pistachio-soft); }
/* Life list stat cards (Lifers, Breeds, Spotted): equal widths, whatever the numbers */
.st-key-life_stats > div { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
.st-key-life_stats { align-items: stretch !important; }
.st-key-life_stats [data-testid="stMetric"] { height: 100%; }

/* Tapping a badge opens what it's for */
.cerb-badge summary { list-style: none; cursor: pointer; }
.cerb-badge summary::-webkit-details-marker { display: none; }
.cerb-badge .how { font-size: .75rem; margin-top: .35rem; text-align: left; opacity: .9; }
.cerb-badge[open] { grid-column: 1 / -1; }  /* full width, so the text has room */
/* The next badge to earn, above the grid */
.cerb-next-badge { display: flex; gap: .75rem; align-items: center; margin-bottom: .25rem; }
.cerb-next-badge .icon { color: var(--plum); opacity: .55; line-height: 1; }
.cerb-next-badge.cross .icon { color: var(--pistachio-text); }
.cerb-next-badge .icon .sketch { width: 2.6rem; height: 2.6rem; }
.cerb-next-badge .label { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; opacity: .7; }
.cerb-next-badge .sub { font-size: .85rem; opacity: .75; }

/* Social feed posts: avatar on the left, who/when, then the sighting */
.cerb-post {
    display: flex; gap: .75rem; padding: .75rem .25rem;
    border-bottom: 1px solid rgba(128, 128, 128, .2);
}
.cerb-post .avatar { font-size: 1.6rem; line-height: 1.2; width: 2.25rem; text-align: center; flex: none; }

/* Lifer celebration (face_balloons_html): the breed's face in circles floating slowly
   up the screen, each on a plum string, swaying a little as it rises. */
.face-balloons {
    position: fixed; inset: 0; pointer-events: none; overflow: hidden; z-index: 1000000;
}
.face-balloon {
    position: absolute; bottom: 0; display: block;
    transform: translateY(110%); opacity: 0;
    animation-name: face-rise; animation-timing-function: ease-in; animation-fill-mode: forwards;
}
.face-balloon .bob {
    display: flex; align-items: center; justify-content: center;
    width: 100%; height: 100%; border-radius: 50%; overflow: hidden;
    background: var(--pistachio-soft); border: 3px solid var(--pistachio);
    box-shadow: 0 4px 14px rgba(0, 0, 0, .18);
    animation: face-sway 2.6s ease-in-out infinite alternate;
}
.face-balloon:nth-child(even) .bob { border-color: var(--plum); }
.face-balloon .bob img { display: block; width: 100%; height: 100%; object-fit: cover; }
.face-balloon .bob .sketch { width: 70%; height: 70%; }
.face-balloon::after {  /* the string */
    content: ""; position: absolute; left: 50%; top: 100%; width: 0; height: 2.5rem;
    border-left: 1.5px solid var(--plum); opacity: .6;
}
@keyframes face-rise {
    0% { transform: translateY(110%); opacity: 0; }
    8% { opacity: 1; }
    85% { opacity: 1; }
    100% { transform: translateY(-115vh); opacity: 0; }
}
@keyframes face-sway {
    from { transform: translateX(-.6rem) rotate(-5deg); }
    to { transform: translateX(.6rem) rotate(5deg); }
}
@media (prefers-reduced-motion: reduce) { .face-balloons { display: none; } }

/* Member pictures: a breed photo in a circle (".pic"), or an older emoji pick */
.avatar.pic, .me-avatar.pic {
    display: block; border-radius: 50%; overflow: hidden; background: rgba(128, 128, 128, .15);
}
.avatar.pic { width: 2.25rem; height: 2.25rem; }
.avatar.pic img, .me-avatar.pic img {
    display: block; width: 100%; height: 100%; object-fit: cover; object-position: 50% 30%;
}
.me-avatar { display: block; font-size: 2.6rem; line-height: 1; }
/* No breed picture: a sketch of a dog on a pistachio circle */
.avatar.sketched, .me-avatar.sketched {
    display: flex; align-items: center; justify-content: center; border-radius: 50%;
    background: var(--pistachio-soft);
}
.avatar.sketched { width: 2.25rem; height: 2.25rem; }
.me-avatar.sketched { width: 3.5rem; height: 3.5rem; }
.avatar.sketched .sketch { width: 70%; height: 70%; }
.me-avatar.sketched .sketch { width: 70%; height: 70%; }
.me-avatar.pic { width: 3.5rem; height: 3.5rem; }
/* The picker + preview row: don't scroll inside itself (that clipped the label) */
.st-key-avatar_row { overflow: visible; }
.cerb-post .main { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.cerb-post .who { font-size: .85rem; opacity: .75; }
.cerb-post .breed { font-weight: 600; }
.cerb-post .sub { font-size: .85rem; opacity: .75; }
/* A post that earned its spotter a milestone badge */
.cerb-post .earned {
    display: inline-block; margin: .15rem 0 .25rem; padding: .2rem .5rem; border-radius: .5rem;
    font-size: .85rem; background: var(--plum-soft); color: var(--plum);
}
.cerb-post .earned.cross { background: var(--pistachio-soft); color: var(--pistachio-text); }

/* "Verified breed" and "Unverified breed" labels next to a breed's name */
.cerb-chip {
    display: inline-block; margin-left: .35rem; padding: 0 .45rem; border-radius: 999px;
    font-size: .7rem; font-weight: 600; line-height: 1.5; vertical-align: middle;
    white-space: nowrap;
}
.cerb-chip.unverified { border: 1px solid var(--plum); color: var(--plum); }
.cerb-chip.cross { border: 1px solid var(--pistachio-text); color: var(--pistachio-text); }
.cerb-chip.verified { background: var(--pistachio-soft); color: var(--pistachio-text); }

/* A sighting's own photo, on its card in Profile and on shared posts in Social */
.sighting-photo {
    display: block; width: 100%; max-height: 20rem; object-fit: cover; border-radius: .5rem;
}
.cerb-post .sighting-photo { margin-top: .4rem; }
/* The photo picker (photo_picker): Streamlit's file uploader restyled as one phone-style
   button. Phones open their usual Take photo / Photo library choice when it's tapped. */
[class*="st-key-photo_pick_"] [data-testid="stFileUploaderDropzone"] {
    border: none; background: none; padding: 0; min-height: 0; display: block;
}
[class*="st-key-photo_pick_"] [data-testid="stFileUploaderDropzoneInstructions"],
[class*="st-key-photo_pick_"] [data-testid="stFileChips"] > div:first-child { display: none; }
[class*="st-key-photo_pick_"] [data-testid="stFileChips"] { display: block; padding: 0; }
[class*="st-key-photo_pick_"] [data-testid="stFileUploaderDropzone"] button {
    width: 100%; min-height: 2.75rem; border-radius: .5rem;
    border: 1px solid rgba(128, 128, 128, .35); background: rgba(128, 128, 128, .06);
    color: inherit;
}
[class*="st-key-photo_pick_"] [data-testid="stButton"] button { min-height: 2.75rem; }
[class*="st-key-photo_pick_"] [data-testid="stFileUploaderDropzone"] button > * { display: none; }
[class*="st-key-photo_pick_"] [data-testid="stFileUploaderDropzone"] button::after {
    content: "Add photo"; font-size: 1rem; font-weight: 600;
}
[class*="st-key-photo_pick_"] button[aria-label="Add files"]::after { content: "Change"; }
.photo-preview {
    display: block; width: 100%; max-height: 16rem; object-fit: cover; border-radius: .75rem;
}
/* Spotted!'s two steps: "1 What breed?  2 About this sighting", the current one in plum */
.spot-steps { display: flex; gap: 1rem; margin: -.5rem 0 .25rem; font-size: .9rem; }
.spot-steps span { opacity: .55; }
.spot-steps span.on { opacity: 1; color: var(--plum); font-weight: 600; }
.spot-steps b {
    display: inline-flex; align-items: center; justify-content: center; width: 1.4rem;
    height: 1.4rem; margin-right: .2rem; border-radius: 50%; border: 1.5px solid currentColor;
}
.spot-breed { margin-top: .5rem; }
/* Tagged dogs on a post: @username chips */
.dog-tag {
    display: inline-block; padding: 0 .45rem; margin: .15rem .25rem 0 0; border-radius: 1rem;
    background: var(--pistachio-soft); font-size: .85rem;
}

/* Bottom tab bar: the main tabs, pinned to the bottom of the screen like a phone
   app. Five equal slots, each an icon above a short label. On wider screens the
   side padding lines the tabs up with the 560px content column. */
.st-key-main_nav [role="tablist"] {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 100;
    gap: 0;
    padding: 0 max(0px, calc((100vw - 560px) / 2)) env(safe-area-inset-bottom);
    background: #FBFAF8;  /* matches [theme.light] in .streamlit/config.toml */
    border-top: 1px solid rgba(128, 128, 128, .25);
}
.st-key-main_nav [data-testid="stTab"] {
    flex: 1; min-width: 0; height: 3.75rem; padding: 0 .1rem;
    justify-content: center;
}
.st-key-main_nav [data-testid="stTab"] p {
    text-align: center; font-size: .72rem; line-height: 1.25;
}
/* Each tab's hand-drawn icon sits above its label (the pictures are in SKETCH_CSS). It's
   a mask, so it takes the label's colour: green on the open tab. */
.st-key-main_nav [data-testid="stTab"] p::before {
    content: ""; display: block; width: 1.6rem; height: 1.6rem; margin: 0 auto .1rem;
    background-color: currentColor;
    -webkit-mask: var(--tab-icon) center / contain no-repeat;
    mask: var(--tab-icon) center / contain no-repeat;
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


def sketch_css() -> str:
    """The hand-drawn icons that CSS draws: one per bottom tab, and the photo buttons.
    Built here because the pictures come from cerberus/sketches.py."""
    tabs = "\n".join(
        f'.st-key-main_nav [data-testid="stTab"]:nth-of-type({n}) p '
        f'{{ --tab-icon: url("{sketches.data_uri(icon)}"); }}'
        for n, icon in enumerate(NAV_ICONS, start=1))
    camera, swap = sketches.data_uri("camera"), sketches.data_uri("swap")
    return f"""<style>
{tabs}
[class*="st-key-photo_pick_"] [data-testid="stFileUploaderDropzone"] button::before {{
    content: ""; display: inline-block; width: 1.4rem; height: 1.4rem;
    margin-right: .45rem; vertical-align: -.3rem; background-color: currentColor;
    -webkit-mask: url("{camera}") center / contain no-repeat;
    mask: url("{camera}") center / contain no-repeat;
}}
[class*="st-key-photo_pick_"] button[aria-label="Add files"]::before {{
    -webkit-mask-image: url("{swap}"); mask-image: url("{swap}");
}}
</style>"""


# The icons on the bottom tabs, in order (names in cerberus/sketches.py SKETCHES).
NAV_ICONS = ["binoculars", "people", "notebook", "person", "sliders"]
st.html(sketch_css())

# Dark mode: the dark-theme brand colours, used when the member picked dark in Settings
# (the browser tells us which theme is on: see sync_saved_sign_in). Light is the default.
DARK_CSS = """
<style>
:root {
    --ink: #ECE9EE;
    --pistachio: #A9C985; --pistachio-soft: rgba(169, 201, 133, .16);
    --pistachio-text: #B9D697; --plum: #E3BEDD; --plum-soft: rgba(227, 190, 221, .16);
    --on-pistachio: #18171A;
}
.st-key-main_nav [role="tablist"] { background: #18171A; }  /* [theme.dark] */
</style>
"""

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


@st.cache_resource(show_spinner=False)
def load_photo_id(version: tuple) -> PhotoID | None:
    """The Photo ID model, loaded once and shared by everyone. That's fine here because
    it holds no member data (unlike the backend, which must never be cached like this).
    None if it can't load: then the app works as before, without suggestions."""
    try:
        return PhotoID()
    except Exception:
        return None


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


def sync_saved_sign_in() -> dict | None:
    """Mount the component (cerberus/remember.py). Returns its report for this session:
    {"token": the saved sign-in or "", "theme": "Light"/"Dark", "carry": a sign-in kept
    across a theme switch or None}, or None until it has reported. It also passes on a
    theme picked in Settings (`theme_wanted`), which makes the browser reload. Once it has, it's told to save the
    current token (or nothing), so a new token from a sign-in, return visit or hourly
    refresh is kept. This runs before anything else talks to Supabase, so if the hour is
    up, refresh_token() swaps the token here and the new one is saved in this same run."""
    if "browser_session" not in st.session_state:
        st.session_state.browser_session = uuid.uuid4().hex
    data = {"session": st.session_state.browser_session}
    if st.session_state.get("saved_read"):
        data["save"] = backend.refresh_token() if st.session_state.get("remember") else None
    wanted = st.session_state.pop("theme_wanted", None)
    if wanted and wanted != st.session_state.get("theme"):
        data["theme"] = wanted  # the browser switches Streamlit's theme
        st.session_state.theme = wanted  # and our own colours follow in this same run
        if "user" in st.session_state:  # in case the browser has to reload instead
            data["carry"] = {"token": backend.refresh_token(),
                             "remember": bool(st.session_state.get("remember"))}
    result = saved_sign_in_store(key="saved_sign_in", data=data,
                                 on_saved_change=lambda: None)
    report = result.saved
    if not isinstance(report, dict) or report.get("session") != data["session"]:
        return None  # not reported yet, or a leftover report from an earlier session
    if not st.session_state.get("saved_read"):  # the theme the page loaded with
        st.session_state.theme = "Dark" if report.get("theme") == "Dark" else "Light"
    return report


def switch_theme():
    """The Settings > Appearance switch: the next run tells the browser to change theme."""
    st.session_state.theme_wanted = "Dark" if st.session_state.dark_mode else "Light"


def resume_saved_sign_in(report: dict | None):
    """The first time the browser reports, sign back in if we can: with the sign-in kept
    across a theme switch, else with the saved "Keep me signed in" token."""
    if report is None or st.session_state.get("saved_read"):
        return
    st.session_state.saved_read = True
    carry = report.get("carry") if isinstance(report.get("carry"), dict) else None
    token = (carry or {}).get("token") or report.get("token")
    if token and "user" not in st.session_state:
        try:
            st.session_state.user = backend.resume_session(token)
        except AuthError:
            pass  # expired or signed out elsewhere: the rerun below deletes it
        else:
            st.session_state.remember = bool(carry["remember"]) if carry else True
    st.rerun()  # so the browser saves the new token (or forgets the dead one) straight away


# --- Sign in / create account ---------------------------------------------------------
def auth_screen():
    st.markdown(logo_html(), unsafe_allow_html=True)
    st.title("Project Cerberus")
    st.write("Spot dogs. Collect breeds. Can you find all 141?")
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
if st.session_state.get("theme") == "Dark":
    st.html(DARK_CSS)
if "user" not in st.session_state:
    auth_screen()
    st.stop()

user = st.session_state.user
st.logo(LOGO_ICON, size="large")  # top-left once signed in (the sign-in screen shows it big)

if backend.demo:
    st.caption("Demo mode: accounts and sightings vanish when you close this tab.")

# --- Load this spotter's data ---------------------------------------------------------------
breeds = load_breeds(file_version(logic.BREEDS_CSV))
breed_profiles = load_breed_profiles(
    file_version(logic.BREED_INFO_CSV, logic.BREED_PHOTOS_CSV, logic.BREED_FACES_CSV))


def breed_photo_html(profile: logic.BreedProfile, label: str = "", box_px: int = 56) -> str:
    """A breed's photo filling a small square or circle, zoomed in on the dog's face
    (breed_faces.csv), or a plain thumbnail if it has no crop. label = text for screen
    readers; empty means decorative, so a photo that fails to load leaves a plain shape."""
    face = logic.face_photo(profile, box_px)
    if face:
        url, css = face
        name = f' role="img" aria-label="{html.escape(label)}"' if label else ""
        return (f'<span class="face"{name} style="background-image:url(&quot;{html.escape(url)}'
                f'&quot;);{css}"></span>')
    return (f'<img src="{html.escape(logic.thumbnail_url(profile.image_url))}" '
            f'alt="{html.escape(label)}" loading="lazy">')


def face_balloons_html(breed: str) -> str:
    """The lifer celebration: the new breed's face in circles floating slowly up the
    screen like balloons (both parents' faces, taking turns, for a cross). Pure CSS
    (".face-balloons" in MOBILE_CSS), so it plays once and needs no rerun. A breed with
    no photo floats up as a sketched dog instead."""
    balloons = []
    for spot in logic.celebration_layout(breed):
        photo = breed_profiles.get(spot["breed"])
        inside = (breed_photo_html(photo, box_px=80) if photo and photo.image_url
                  else sketches.svg("dog"))
        balloons.append(
            f'<span class="face-balloon" style="left:{spot["left"]}%;'
            f'width:{spot["size"]}rem;height:{spot["size"]}rem;'
            f'animation-duration:{spot["rise"]}s;animation-delay:{spot["delay"]}s">'
            f'<span class="bob" style="animation-delay:{spot["delay"]}s">{inside}</span></span>')
    return f'<div class="face-balloons" aria-hidden="true">{"".join(balloons)}</div>'


def avatar_html(avatar: str, css: str) -> str:
    """A member's picture: their chosen breed's photo in a circle. Anyone without one
    (including older profiles that picked an emoji) gets a sketch of a dog instead."""
    photo = breed_profiles.get(avatar)
    if photo and photo.image_url:
        return f'<span class="{css} pic">{breed_photo_html(photo, avatar)}</span>'
    return f'<span class="{css} sketched">{sketches.svg("dog")}</span>'


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

# Every breed in breeds.csv is verified. Members can type in others ("unverified breeds"),
# which go on a shared list (user_breeds) so others can pick them and the owner can review.
listed = set(breeds["breed"])  # only these count towards the life list, lifers and badges
try:
    added_breeds = [b for b in backend.list_user_breeds()
                    if b not in listed and not logic.is_cross(b)]
except AuthError as err:
    end_session(str(err))
md_text = logic.escape_markdown
UNVERIFIED_CHIP = f'<span class="cerb-chip unverified">{logic.UNVERIFIED}</span>'
CROSS_CHIP = f'<span class="cerb-chip cross">{logic.CROSS}</span>'



def clear_photo(key: str):
    """Empty a photo_picker (after saving, or when Remove is tapped)."""
    st.session_state[f"{key}_n"] = st.session_state.get(f"{key}_n", 0) + 1
    st.session_state.pop(f"{key}_prepared", None)
    st.session_state.pop(f"{key}_details", None)


def photo_picker(key: str, note: str, max_side: int = logic.PHOTO_MAX_SIDE) -> bytes | None:
    """A phone-style "Add photo" button: tapping it on a phone offers Take photo or the
    photo library. Once picked, it shows a preview with Change and Remove.

    Returns the photo made small and safe to store (`logic.prepare_photo`: resized, no GPS),
    or None. Keep it outside `st.form`: form widgets only send their value on submit, so
    there'd be no preview. Call `clear_photo(key)` once the photo is saved.
    When and where the original was taken (`logic.photo_details`, read before the
    metadata is stripped) waits in `st.session_state[f"{key}_details"]` as
    (photo id, details).
    """
    n = st.session_state.get(f"{key}_n", 0)  # a new number makes a new, empty uploader
    with st.container(key=f"photo_pick_{key}"):
        preview = st.container()
        with st.container(horizontal=True, gap="small"):
            photo = st.file_uploader(
                "Photo (optional)", type=logic.PHOTO_TYPES, key=f"{key}_{n}",
                max_upload_size=logic.MAX_PHOTO_UPLOAD_MB, label_visibility="collapsed")
            if photo is not None:
                st.button("Remove", key=f"{key}_remove_{n}", icon=":material/delete:",
                          on_click=clear_photo, args=(key,))
    if photo is None:
        return None
    prepared = st.session_state.get(f"{key}_prepared")
    if prepared is None or prepared[0] != photo.file_id:  # shrink each new photo once
        try:
            prepared = photo.file_id, logic.prepare_photo(photo.getvalue(), max_side)
        except ValueError as err:  # not an image
            preview.warning(str(err))
            return None
        st.session_state[f"{key}_prepared"] = prepared
        st.session_state[f"{key}_details"] = (photo.file_id,
                                              logic.photo_details(photo.getvalue()))
    src = "data:image/jpeg;base64," + base64.b64encode(prepared[1]).decode()
    preview.markdown(f'<img class="photo-preview" src="{src}" alt="Your photo">',
                     unsafe_allow_html=True)
    preview.caption(note)
    return prepared[1]


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False, max_entries=5000)
def look_up_place(lat: float, lon: float) -> str:
    """The place name for a (rounded) photo location. Cached, and shared by everyone,
    which is fine: it's only a map lookup. Raises LookupError if none was found, so a
    failed lookup isn't cached and the next photo tries again."""
    place = places.place_for(lat, lon)
    if place is None:
        raise LookupError("no place found")
    return place


def fill_from_photo(key: str, date_key: str, where_key: str, earliest: dt.date):
    """Fill in the date seen and suggest a place from a new photo's metadata, once per
    photo. Only fills a box that's empty (or still holds today's date) or still holds
    what an earlier photo filled in, so nothing the member typed is overwritten. Photos
    without the details (screenshots, or a browser that removed them) fill in nothing."""
    photo_id, details = st.session_state.get(f"{key}_details") or (None, None)
    if details is None or st.session_state.get("photo_filled_for") == photo_id:
        return
    st.session_state.photo_filled_for = photo_id
    filled = st.session_state.get("photo_filled", {})
    today = dt.date.today()
    taken_on = details.taken_on
    if taken_on and earliest <= taken_on <= today and \
            st.session_state.get(date_key, today) in (today, filled.get("date")):
        filled["date"] = st.session_state[date_key] = taken_on
    if details.where and (st.session_state.get(where_key) or "") in ("", filled.get("where")):
        with st.spinner("Looking up where your photo was taken…"):
            try:
                filled["where"] = st.session_state[where_key] = look_up_place(*details.where)
            except LookupError:
                pass  # no place name: leave Where for the member
    st.session_state.photo_filled = filled


def pick_breed(breed: str):
    """A Photo ID suggestion was tapped: put that breed in the form's Breed box. For a
    cross whose first breed is already picked, it fills the second breed instead."""
    first = st.session_state.get("sighting_breed")
    if (st.session_state.get("sighting_is_cross") and first and first != breed
            and not st.session_state.get("sighting_breed_2")):
        st.session_state.sighting_breed_2 = breed
    else:
        st.session_state.sighting_breed = breed


def photo_id_suggestions(photo: bytes):
    """Photo ID: the model's top breed guesses for this photo, as buttons that fill in
    the breed. It only suggests; the member checks and can pick any breed instead."""
    model = load_photo_id(file_version(
        logic.PHOTO_ID_MODEL, logic.PHOTO_ID_BREEDS_CSV, CERBERUS_DIR / "photo_id.py"))
    if model is None:
        return
    digest = hashlib.sha256(photo).hexdigest()
    cached = st.session_state.get("photo_id_result")
    if cached is None or cached[0] != digest:  # run the model once per photo
        try:
            cached = digest, model.guesses(photo)
        except Exception:
            return
        st.session_state.photo_id_result = cached
    result = cached[1]
    with st.container(key="photo_id"):
        st.markdown(f'<p class="cerb-label">{sketches.svg("magnifier")} <b>Photo ID</b></p>',
                    unsafe_allow_html=True)
        if not result.is_dog:
            st.caption("Photo ID can't spot a dog in this photo. Pick the breed yourself.")
            return
        if not result.guesses:
            st.caption("Photo ID isn't sure about this one. Pick the breed yourself.")
            return
        for i, guess in enumerate(result.guesses):  # each with the breed's own photo
            chosen = guess.breed in (st.session_state.get("sighting_breed"),
                                     st.session_state.get("sighting_breed_2"))
            breed_info = breed_profiles.get(guess.breed)
            pic = (breed_photo_html(breed_info, guess.breed)
                   if breed_info and breed_info.image_url else "")
            with st.container(horizontal=True, vertical_alignment="center", gap="small",
                              key=f"photo_id_guess_{i}"):
                st.markdown(
                    f'<div class="cerb-row guess"><span class="thumb">{pic}</span>'
                    f'<span class="main"><span class="name">{html.escape(guess.breed)}</span>'
                    f'<br><span class="sub">{guess.label}</span></span></div>',
                    unsafe_allow_html=True, width="stretch")
                st.button("Picked" if chosen else "Pick", key=f"photo_id_pick_{i}",
                          type="primary" if chosen else "secondary",
                          on_click=pick_breed, args=(guess.breed,))
        known = len({b for b in model.class_breeds.values() if b})
        st.caption(f"Compare each breed's photo with yours and pick the one that matches, "
                   f"then check it. Photo ID knows {known} "
                   f"of our {len(listed)} breeds so far, so it can't suggest the others yet.")


def breed_chip(breed: str) -> str:
    """A "Cross breed" label for a cross, or "Unverified breed" for a breed that isn't on
    the verified list."""
    if breed in listed:
        return ""
    return CROSS_CHIP if logic.is_cross(breed) else UNVERIFIED_CHIP


def load_dogs() -> list[dict] | None:
    """Every member's dog profiles, or None if dog profiles aren't set up yet (then the
    app carries on without them: no tagging, and the older "my dogs" list in Profile)."""
    if not profiles_ready:
        return None
    try:
        return backend.list_dogs()
    except AuthError as err:
        end_session(str(err))
    except Exception:
        return None


def move_listed_dogs_to_profiles() -> bool:
    """Members listed their dogs (name and breed) on their profile before dogs had
    profiles of their own. Give each of those a dog profile, with a username made from
    its name, then empty the old list. Returns True if anything moved."""
    if all_dogs is None or not profile["dogs"]:
        return False
    try:
        for listed in profile["dogs"]:
            for username in logic.dog_username_candidates(listed["name"]):
                try:
                    backend.add_dog({**listed, "username": username})
                    break
                except ValueError as err:
                    if str(err) != logic.DOG_USERNAME_TAKEN:
                        raise
        backend.save_profile({**profile, "dogs": []})
    except AuthError as err:
        end_session(str(err))
    except Exception:  # try again next visit; nothing is lost while the old list remains
        return False
    return True


all_dogs = load_dogs()
if move_listed_dogs_to_profiles():
    profile, all_dogs = backend.my_profile(), load_dogs()
dogs_by_id = {d["id"]: d for d in all_dogs or []}
my_dogs = [d for d in all_dogs or [] if d["owner_id"] == user.id]


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
badges = logic.badge_progress(sightings, logic.ALL_BADGES, listed=listed)
lifers = logic.lifer_count(sightings, listed)  # breeds, plus crosses

flash = st.session_state.pop("flash", None)
if flash:
    kind, breed_name = flash
    if kind == "lifer":
        st.markdown(face_balloons_html(breed_name), unsafe_allow_html=True)
        st.success(f"New lifer! **{breed_name}** is on your life list.")
    elif kind == "cross_lifer":
        st.markdown(face_balloons_html(breed_name), unsafe_allow_html=True)
        st.success(f"New lifer! **{md_text(breed_name)}** is a new cross on your life list.")
    elif kind == "cross":
        st.info(f"Logged another **{md_text(breed_name)}**.")
    elif kind == "unverified":
        st.info(f"Logged a **{md_text(breed_name)}**, an unverified breed. It's not on the "
                "life list yet, so it's under **Unverified breeds** on your life list. "
                "Thanks for helping us find breeds to add!")
    else:
        st.info(f"Logged another **{breed_name}**.")
    # Any badges this sighting earned (any track: a cross can finish a Family reunion).
    for badge in logic.newly_earned(st.session_state.pop("badges_before", []), badges):
        st.success(f"Badge earned: **{badge.name}**! {badge.description}. See it in Profile.")
photo_problem = st.session_state.pop("photo_problem", None)
if photo_problem:
    st.warning(photo_problem)

# The five main tabs. The "main_nav" key lets MOBILE_CSS pin them to the bottom of the
# screen as a tab bar; NAV_ICONS draws a hand-drawn icon above each label (SKETCH_CSS).
NAV_TABS = ["Spotted!", "Social", "Life list", "Profile", "Settings"]  # life list in the middle
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
    background: #8A5A83;  /* plum, the brand highlight colour (MOBILE_CSS) */
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
    tab_spotted, tab_social, tab_life, tab_profile, tab_settings = st.tabs(
        NAV_TABS, key="main_tab", on_change="rerun")

# --- Spotted!: log a sighting in two steps --------------------------------------------------------
# Step 1 is the dog ID: add a photo, let Photo ID suggest the breed (or pick it yourself), then
# Continue. Step 2 shows your photo and breed, and asks for the rest: which dog it was, where,
# when and your notes, then posts. Both steps are drawn on every run and the one not in use is
# hidden with CSS, so nothing you've entered is lost when you go back and forth (Streamlit
# forgets a widget's value, and an uploaded photo, as soon as it stops drawing it).
SPOT_STEPS = {1: "What breed?", 2: "About this sighting"}


def go_to_step(step: int):
    st.session_state.spot_step = step


def confirm_breed():
    """Continue: check the breed picked in step 1 (a known one, a typed-in one, or a cross
    of two), then move on to step 2. Typed names are tidied and matched to a known breed,
    ignoring case."""
    known = [*listed, *added_breeds]
    first = st.session_state.get("sighting_breed")
    try:
        if st.session_state.get("sighting_is_cross"):
            breed = logic.cross_name(first, st.session_state.get("sighting_breed_2"), known)
        else:
            breed = logic.clean_breed(first, known)
    except ValueError as err:
        st.session_state.spot_problem = str(err)
        return
    st.session_state.spot_breed = breed
    go_to_step(2)


def steps_html(step: int) -> str:
    """A small "1 What breed? · 2 About this sighting" line, the current step highlighted."""
    return '<p class="spot-steps">' + "".join(
        f'<span class="{"on" if n == step else ""}"><b>{n}</b> {name}</span>'
        for n, name in SPOT_STEPS.items()) + "</p>"


def chosen_breed_html(breed: str, photo: bytes | None) -> str:
    """Step 2's summary card: your photo, then the breed you confirmed with its own photo
    and whether it's a new one for you."""
    pic = ""
    if photo is not None:
        src = "data:image/jpeg;base64," + base64.b64encode(photo).decode()
        pic = f'<img class="photo-preview" src="{src}" alt="Your photo">'
    info = breed_profiles.get(breed)
    thumb = (f'<span class="thumb">{breed_photo_html(info, breed)}</span>'
             if info and info.image_url
             else f'<span class="thumb icon">{sketches.svg("dog")}</span>')
    if logic.is_lifer(sightings, breed, listed):
        sub = f'{sketches.svg("sparkle")} New for your life list{breed_chip(breed)}'
    elif breed not in listed:
        sub = breed_chip(breed)
    else:
        sub = "Already on your life list"
    return (f'{pic}<div class="cerb-row guess spot-breed">{thumb}<span class="main">'
            f'<span class="name">{html.escape(breed)}</span><br>'
            f'<span class="sub">{sub}</span></span></div>')


with tab_spotted:
    st.header("Spotted a dog?")
    seen_breeds = set(life.loc[seen, "breed"])

    def breed_label(name: str) -> str:
        if name not in listed:
            return f"{name}  · unverified"
        return name if name in seen_breeds else f"{name}  · new"

    def parent_label(name: str) -> str:  # a parent breed isn't the lifer, so no "new"
        return name if name in listed else f"{name}  · unverified"

    def fill_from_tags():
        """Tagging dogs fills in the dog's name straight away (if it's empty, or still holds
        what an earlier tag filled in), so you can see and change it."""
        dogs = [dogs_by_id[d] for d in st.session_state.get("sighting_dogs", [])
                if d in dogs_by_id]
        filled = st.session_state.get("tag_filled", {})
        if (st.session_state.get("sighting_dog_name") or "") in ("", filled.get("name")):
            filled["name"] = st.session_state.sighting_dog_name = logic.tagged_names(dogs)
        st.session_state.tag_filled = filled

    if st.session_state.pop("clear_tags", False):  # the last sighting was just logged
        st.session_state.sighting_dogs = []
        st.session_state.sighting_breed = st.session_state.sighting_breed_2 = None
        st.session_state.sighting_is_cross = False
        st.session_state.pop("tag_filled", None)
        st.session_state.pop("spot_breed", None)
        go_to_step(1)
    step = st.session_state.get("spot_step", 1)
    if step == 2 and not st.session_state.get("spot_breed"):
        step = 1  # e.g. a fresh session: there's no confirmed breed to show
    st.html(f"<style>.st-key-spot_step_{3 - step} {{ display: none; }}</style>")
    st.markdown(steps_html(step), unsafe_allow_html=True)

    # Step 1: the dog ID. A photo (optional) and Photo ID's suggestions, then the breed
    # (or the two breeds of a cross).
    with st.container(key="spot_step_1"):
        photo = photo_picker(
            "sighting_photo", "Shown with your sighting in Social if you share your "
            "sightings (Settings > Privacy). Saved smaller, without the location your phone "
            "may have stored in it.")
        if photo is not None:
            photo_id_suggestions(photo)
        else:
            st.caption("Add a photo and Photo ID will suggest the breed.")
        # The photo's date and place fill in step 2's boxes (looked up here, while the
        # photo is new, so its "Looking up…" spinner shows on the step you're on).
        earliest_date = dt.date(dt.date.today().year - 10, 1, 1)
        fill_from_photo("sighting_photo", "sighting_date", "sighting_where", earliest_date)
        is_cross = st.toggle(
            "It's a cross breed", key="sighting_is_cross",
            help="A dog whose parents are two different breeds, like a Labrador Retriever x "
                 "Poodle. Crosses are logged as **Breed A x Breed B**. "
                 + ("Each new cross is a lifer, but only breeds count towards badges."
                    if logic.CROSSES_ARE_LIFERS else "They don't count as lifers."))
        breed_options = [*breeds["breed"], *added_breeds]
        st.selectbox(
            "First breed" if is_cross else "Breed",
            breed_options,
            index=None,
            format_func=parent_label if is_cross else breed_label,
            placeholder="Start typing a breed…",
            accept_new_options=True,  # a breed that isn't listed can be typed in
            key="sighting_breed",
            help="Can't find the breed? Type it in. It's logged as an **unverified breed** "
                 "and we'll look at adding it to the app.",
        )
        if is_cross:
            st.selectbox(
                "Second breed", breed_options, index=None,
                placeholder="Start typing a breed…", accept_new_options=True,
                key="sighting_breed_2", format_func=parent_label)
        problem = st.session_state.pop("spot_problem", None)
        if problem:
            st.warning(problem)
        st.button("Continue", key="spot_continue", type="primary", width="stretch",
                  on_click=confirm_breed)

    # Step 2: your photo and the breed, then the details of the sighting, then post.
    with st.container(key="spot_step_2"):
        breed = st.session_state.get("spot_breed")
        if breed:
            st.markdown(chosen_breed_html(breed, photo), unsafe_allow_html=True)
        st.button("Change breed or photo", key="spot_back", icon=":material/arrow_back:",
                  on_click=go_to_step, args=(1,))
        tagged = []
        if all_dogs:  # dogs with a profile (anyone's) can be tagged by their @username
            # Outside the form below, so tagging a dog can fill in its name at once
            # (widgets inside a form only send their values when the form is submitted).
            tagged = st.multiselect(
                "Tag dogs", list(dogs_by_id), key="sighting_dogs", on_change=fill_from_tags,
                format_func=lambda dog_id: logic.dog_label(dogs_by_id[dog_id]),
                placeholder="Tag one or more dogs by @username",
                help="Tag dogs that have a profile, like your own. Their name is filled in "
                     "for you.")
        filled_in = st.session_state.get("photo_filled", {})
        with st.form("log_sighting", clear_on_submit=True, border=False):
            dog_name = st.text_input("Dog's name (if you found out)", key="sighting_dog_name")
            location = st.text_input(
                "Where", placeholder="e.g. Hyde Park", key="sighting_where",
                help="Other members can see this in Social if you share your sightings "
                     "(Settings > Privacy).")
            seen_on = st.date_input("Date seen", min_value=earliest_date,
                                    max_value=dt.date.today(), key="sighting_date")
            if photo is not None and filled_in:
                what = " and ".join(name for name, part in (("Date", "date"), ("place", "where"))
                                    if part in filled_in).capitalize()
                st.caption(f"{what} filled in from your photo. Change it if it's wrong.")
            notes = st.text_area("Your post", placeholder="Good boy. Very fluffy.", height=80,
                                 key="sighting_notes")
            submitted = st.form_submit_button("Spotted!", type="primary", width="stretch")

    if submitted and breed:
        tagged_dogs = [dogs_by_id[d] for d in tagged if d in dogs_by_id]
        dog_name = dog_name.strip() or logic.tagged_names(tagged_dogs)
        lifer = logic.is_lifer(sightings, breed, listed)
        photo_path = None
        if photo is not None:
            try:
                photo_path = backend.add_photo(photo)  # already made small, no GPS
            except AuthError as err:
                end_session(str(err))
            except Exception:  # storage not set up or unreachable: still log the dog
                st.session_state.photo_problem = ("Your photo couldn't be saved, so the "
                                                  "sighting was logged without it.")
        try:
            backend.add_sighting(breed, seen_on, location, dog_name, notes, photo_path,
                                 [d["id"] for d in tagged_dogs])
        except AuthError as err:
            end_session(str(err))
        # A typed-in breed (or either breed of a cross) goes on the list of breeds to
        # review, and for others to pick. The cross itself isn't added.
        for new_breed in logic.cross_parents(breed) or (breed,):
            if new_breed in listed or new_breed in added_breeds:
                continue
            try:
                backend.add_user_breed(new_breed)
            except AuthError as err:
                end_session(str(err))
            except Exception:
                pass  # not set up yet: the sighting is logged all the same
        st.session_state.clear_tags = True  # back to step 1, empty, for the next dog
        st.session_state.pop("photo_filled", None)
        clear_photo("sighting_photo")
        st.session_state.badges_before = [p.badge.key for p in badges if p.earned]
        st.session_state.flash = ("cross_lifer" if lifer and logic.is_cross(breed) else
                                  "lifer" if lifer else
                                  "repeat" if breed in listed else
                                  "cross" if logic.is_cross(breed) else "unverified", breed)
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
        f'<div class="cerb-profile">{photo}'
        f'<p><span class="cerb-chip verified">{sketches.svg("check")} Verified breed</span></p>'
        f'<p>{esc(profile.intro)}</p>'
        f'<div class="facts"><b>From:</b> {esc(profile.origin)}<br>'
        f'<b>Temperament:</b> {esc(profile.temperament)}</div>'
        f'<div class="fun">{sketches.svg("bulb")} <b>Fun fact:</b> {esc(profile.fun_fact)}</div></div>'
    )


def breed_thumb(profile: logic.BreedProfile | None, tick: bool = False) -> str:
    """A breed's small square photo (an empty grey square if it has none)."""
    img = breed_photo_html(profile) if profile and profile.image_url else ""
    tick_html = f'<span class="tick">{sketches.svg("check")}</span>' if tick else ""
    return f'<span class="thumb">{img}{tick_html}</span>'


def life_row(row, profile: logic.BreedProfile | None) -> str:
    """One breed as a compact list row (a wide table is hard to read on a phone).
    Tapping the row opens the breed's profile underneath it."""
    if row.times_seen:
        css, seen = "cerb-row", True
        detail = f"First seen {row.first_seen} · seen {row.times_seen}×"
    else:
        css, seen, detail = "cerb-row missing", False, "Not spotted yet"
    # Only the AKC top 100 have a popularity rank; the breeds added after them have none.
    rank = "" if pd.isna(row.rank) else f'<span class="rank">#{row.rank}</span>'
    return (
        f'<details class="cerb-breed"><summary class="{css}">{breed_thumb(profile, tick=seen)}'
        f'<div class="main"><div class="name">{html.escape(row.breed)}</div>'
        f'<div class="sub">{detail}</div></div>'
        f'{rank}<span class="chev">›</span></summary>'
        f'{breed_profile_html(profile)}</details>'
    )


def unverified_row(row, chip: str = UNVERIFIED_CHIP) -> str:
    """A breed that isn't verified yet (or a cross), as a plain row with no photo."""
    return (f'<div class="cerb-row"><span class="thumb icon">{sketches.svg("dog")}</span><div class="main">'
            f'<div class="name">{html.escape(row.breed)}{chip}</div>'
            f'<div class="sub">First seen {row.first_seen} · seen {row.times_seen}×</div>'
            f'</div></div>')


with tab_life:
    st.header(f"{user.username}'s life list")
    # Three small stat cards side by side, even on a narrow phone (st.columns would stack them).
    # The "life_stats" key lets MOBILE_CSS give all three the same width.
    with st.container(horizontal=True, wrap=False, gap="small", key="life_stats"):
        st.metric("Lifers", lifers, border=True,
                  help="Every breed and cross you've spotted at least once.")
        st.metric("Breeds", f"{collected}/{total}", border=True,
                  help="Verified breeds you've spotted, out of all of them.")
        st.metric("Spotted", len(sightings), border=True,
                  help="Every sighting you've logged, repeats included.")
    st.progress(collected / total if total else 0.0)
    coming = logic.next_badge(logic.badges_by_track(badges)[logic.LIFER])
    if coming:
        st.caption(f"Next badge: **{coming.badge.name}**, "
                   f"{coming.to_go} more lifer{'' if coming.to_go == 1 else 's'} to go.")

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
               "Numbers are AKC 2025 popularity ranks for the top 100; the other "
               "breeds follow A to Z. Photos from Wikimedia Commons.")

    unverified = logic.unverified_breeds(sightings, listed)
    if not unverified.empty:
        st.subheader("Unverified breeds")
        st.caption("Breeds you typed in that aren't on the life list yet. We review them, "
                   "and once a breed is verified your sightings of it count as lifers.")
        st.markdown("".join(unverified_row(r) for r in unverified.itertuples()),
                    unsafe_allow_html=True)

    crosses = logic.cross_breeds(sightings)
    if not crosses.empty:
        st.subheader(f"Crosses ({len(crosses)})")
        st.caption("Cross breeds you've spotted. "
                   + ("Each new cross is a lifer, but only breeds count towards badges and "
                      "the breed total above." if logic.CROSSES_ARE_LIFERS else
                      "They don't count as lifers or towards badges."))
        st.markdown("".join(unverified_row(r, CROSS_CHIP) for r in crosses.itertuples()),
                    unsafe_allow_html=True)

# --- Your profile: who you are, plus every sighting you've logged ------------------------------
def badges_section():
    """Profile > Badges: one tab per kind of badge (Lifers, Purebreds, Crosses), each with
    the next badge to earn up front, then all of them (earned ones in colour)."""
    tracks = logic.badges_by_track(badges)
    earned = sum(p.earned for p in badges)
    st.subheader(f"Badges ({earned}/{len(badges)})")

    def label(track: str) -> str:
        mine = tracks[track]
        return f"{logic.BADGE_TRACKS[track][0]} {sum(p.earned for p in mine)}/{len(mine)}"

    track = st.segmented_control(
        "Badge type", list(tracks), default=logic.LIFER, required=True, format_func=label,
        key="badge_track", label_visibility="collapsed", width="stretch")
    mine = tracks[track]
    st.caption(logic.BADGE_TRACKS[track][2])
    coming = [p for p in mine if not p.earned]
    if coming:  # the closest one first (cross badges each count something different)
        up = min(coming, key=lambda p: (p.to_go, p.badge.goal))
        st.markdown(
            f'<div class="cerb-next-badge {up.badge.track}"><span class="icon">'
            f'{sketches.svg(up.badge.icon)}</span><div class="main">'
            f'<div class="label">Next up</div><b>{html.escape(up.badge.name)}</b><br>'
            f'<span class="sub">{html.escape(up.badge.description)}'
            + (f": {up.have}/{up.badge.goal} {html.escape(up.badge.unit)}"
               if up.badge.goal > 1 else "") + '</span></div></div>',
            unsafe_allow_html=True)
        st.progress(up.have / up.badge.goal)
    else:
        st.success("You've earned every one of these!")
    # All of them in order: earned ones in colour, the rest grey. Tap one to see what it
    # needs (cross badges add a tip from your own sightings).
    hints = logic.cross_badge_hints(sightings) if track == logic.CROSS_TRACK else {}
    st.caption("Tap a badge to see how to earn it.")
    st.markdown(f'<div class="cerb-badges">'
                f'{"".join(badge_html(p, hints.get(p.badge.key, "")) for p in mine)}</div>',
                unsafe_allow_html=True)



def badge_html(p: logic.BadgeProgress, hint: str = "") -> str:
    """One badge as a small card: when it was earned, or how far there is to go. Tapping
    it opens what it's for (an HTML <details>, so no rerun), plus `hint` until earned."""
    if p.earned:
        day = dt.date.fromisoformat(p.earned_on)
        css, sub = f"cerb-badge {p.badge.track}", f"Earned {day.day} {day:%b %Y}"
    else:
        css = f"cerb-badge {p.badge.track} locked"
        sub = f"{p.have}/{p.badge.goal} {p.badge.unit}" if p.badge.goal > 1 else "Not yet"
    hint = f" {hint}" if hint and not p.earned else ""
    return (f'<details class="{css}"><summary>'
            f'<span class="icon">{sketches.svg(p.badge.icon)}</span>'
            f'<div class="name">{html.escape(p.badge.name)}</div><div class="sub">{sub}</div>'
            f'</summary><div class="how">{html.escape(p.badge.description)}.'
            f'{html.escape(hint)}</div></details>')


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
    dogs = profile["dogs"]
    # Before dog profiles are set up, dogs are a simple list on your profile.
    if all_dogs is None and st.toggle("I have a dog", value=bool(profile["dogs"]),
                                      key="profile_has_dogs"):
        dogs = []
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


def photo_links(paths) -> dict[str, str]:
    """Links to show photos (sightings and dogs). Storage links expire after an hour, so
    they're kept in this browser session for 50 minutes rather than fetched every rerun."""
    links = st.session_state.setdefault("photo_links", {})  # path -> (link, fetched at)
    now = time.time()
    wanted = [p for p in dict.fromkeys(p for p in paths if isinstance(p, str))
              if p not in links or now - links[p][1] > 50 * 60]
    if wanted:
        try:
            fresh = backend.photo_urls(list(wanted))
        except AuthError as err:
            end_session(str(err))
        except Exception:  # photos are extras: never let them break a tab
            fresh = {}
        links.update({p: (link, now) for p, link in fresh.items()})
    return {p: link for p, (link, _) in links.items()}


def dog_pic_html(dog: dict, links: dict[str, str], css: str = "me-avatar") -> str:
    """A dog's picture: its own photo, else its breed's photo, else a sketch of a dog."""
    if dog.get("photo_path") in links:
        return (f'<span class="{css} pic"><img src="{html.escape(links[dog["photo_path"]])}" '
                f'alt="{html.escape(dog["name"])}"></span>')
    return avatar_html(dog["breed"] if dog.get("breed") in breed_profiles else "", css)


def dog_tags_html(dog_ids) -> str:
    """The dogs tagged in a sighting, as @username chips."""
    dogs = [dogs_by_id[d] for d in dog_ids or [] if d in dogs_by_id]
    return "".join(f'<span class="dog-tag" title="{html.escape(d["name"])}">'
                   f'@{html.escape(d["username"])}</span>' for d in dogs)


def dog_card(dog: dict, links: dict[str, str]):
    """A dog's profile: picture, @username, name, breed, owner and bio (all escaped)."""
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.markdown(dog_pic_html(dog, links), unsafe_allow_html=True, width="content")
            breed = f" · {dog['breed']}" if dog.get("breed") else ""
            with st.container(gap=None):
                # The username is only letters, numbers, dots and underscores; the name is
                # typed freely, so it's plain text.
                st.markdown(f"**@{dog['username']}**")
                st.text(f"{dog['name']}{breed}")
        if dog.get("owner") and dog["owner_id"] != user.id:
            st.caption(f"Owned by {dog['owner']}")
        if dog.get("bio"):
            st.text(dog["bio"])  # plain text: members wrote it


def dog_form(key: str, dog: dict | None = None):
    """Add a dog (dog=None) or edit one of yours. Saves on submit."""
    dog = dog or {}
    own_breeds = breeds["breed"].tolist() + [logic.MIXED_BREED]
    parents = logic.cross_parents(dog.get("breed")) or (None, None)
    photo = photo_picker(f"dog_{key}_photo", "Other members can see your dog's photo.",
                         logic.DOG_PHOTO_MAX_SIDE)
    # Outside the form, so switching it on shows the second breed box straight away.
    is_cross = st.toggle("My dog is a cross breed", key=f"dog_{key}_is_cross",
                         value=logic.is_cross(dog.get("breed")),
                         help="Parents of two different breeds, like a Labrador Retriever "
                              "x Poodle. Shown as **Breed A x Breed B**.")
    with st.form(f"dog_form_{key}", clear_on_submit=not dog, border=False):
        name = st.text_input("Name", value=dog.get("name", ""), key=f"dog_{key}_name",
                             max_chars=logic.MAX_DOG_NAME_LENGTH)
        username = st.text_input(
            "Username", value=dog.get("username", ""), key=f"dog_{key}_username",
            max_chars=30, placeholder="e.g. rex_the_lab",
            help="Others tag your dog in their posts with this. Letters, numbers, dots "
                 "and underscores. Leave it empty to make one from the name.")
        second = None
        if is_cross:
            names = breeds["breed"].tolist()
            breed = st.selectbox("First breed", names, key=f"dog_{key}_breed_a",
                                 placeholder="Pick a breed",
                                 index=names.index(parents[0]) if parents[0] in names else None)
            second = st.selectbox("Second breed", names, key=f"dog_{key}_breed_b",
                                  placeholder="Pick a breed",
                                  index=names.index(parents[1]) if parents[1] in names else None)
        else:
            breed = st.selectbox("Breed", own_breeds, key=f"dog_{key}_breed",
                                 placeholder="Pick a breed (optional)",
                                 index=own_breeds.index(dog["breed"])
                                 if dog.get("breed") in own_breeds else None)
        bio = st.text_area("Bio", value=dog.get("bio") or "", key=f"dog_{key}_bio",
                           max_chars=logic.MAX_DOG_BIO_LENGTH, height=80,
                           placeholder="Loves tennis balls, scared of cats.")
        saved = st.form_submit_button("Save dog" if dog else "Add dog", type="primary",
                                      width="stretch")
    if not saved:
        return
    if not username.strip() and name.strip():  # first free name made from the dog's name
        taken = {d["username"].lower() for d in all_dogs or [] if d.get("id") != dog.get("id")}
        username = next(u for u in logic.dog_username_candidates(name) if u not in taken)
    try:
        if is_cross:
            breed = logic.cross_name(breed, second, listed)
        photo_path = dog.get("photo_path")
        if photo is not None:
            photo_path = backend.add_dog_photo(photo)  # already made small, no GPS
        new = {"username": username, "name": name, "breed": breed, "bio": bio,
               "photo_path": photo_path}
        if dog:
            backend.update_dog(dog["id"], new)
        else:
            backend.add_dog(new)
    except ValueError as err:
        st.error(str(err))
    except AuthError as err:
        end_session(str(err))
    except Exception:
        st.error("Your dog didn't save. Please try again.")
    else:
        st.session_state.dog_saved = f"@{username.strip().lstrip('@')} saved."
        clear_photo(f"dog_{key}_photo")
        st.rerun()


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
            st.markdown(f"Favourite breed: **{profile['favourite_breed']}**")
        if my_dogs:
            st.markdown(f"{'My dog' if len(my_dogs) == 1 else 'My dogs'}: "
                        + ", ".join(f"@{d['username']}" for d in my_dogs))
        elif profile["dogs"]:
            st.markdown(f"{'My dog' if len(profile['dogs']) == 1 else 'My dogs'}: "
                        f"{dogs_text(profile['dogs'])}")
        if sightings.empty:
            st.caption("No sightings yet.")
        else:
            st.caption(f"Spotting since {sightings['seen_on'].min()} · "
                       f"{lifers} lifer{'' if lifers == 1 else 's'} from "
                       f"{len(sightings)} sighting{'' if len(sightings) == 1 else 's'}")
    if profiles_ready:
        with st.expander("Edit profile"):
            profile_editor()

    if all_dogs is not None:
        st.subheader("Your dogs")
        if dog_saved := st.session_state.pop("dog_saved", None):
            st.success(dog_saved)
        st.caption("Give your dogs a profile and a username, so you and others can tag "
                   "them when they're spotted.")
        mine_links = photo_links(d["photo_path"] for d in my_dogs) if tab_profile.open else {}
        for dog in my_dogs:
            dog_card(dog, mine_links)
            with st.expander(f"Edit @{dog['username']}"):
                dog_form(f"edit_{dog['id']}", dog)
                if st.button("Delete this dog", key=f"delete_dog_{dog['id']}"):
                    try:
                        backend.delete_dog(dog["id"])
                    except AuthError as err:
                        end_session(str(err))
                    st.rerun()
        with st.expander("Add a dog"):
            dog_form("new")

    badges_section()

    st.subheader("Your sightings")
    if sightings.empty:
        st.info("No sightings yet. Go find a dog!")
    my_photos = photo_links(sightings["photo_path"].dropna()) if tab_profile.open else {}
    for s in logic.recent_first(sightings).itertuples():
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment="top",
                              horizontal_alignment="distribute"):
                st.markdown(f"**{md_text(s.breed)}**"
                            + ("" if s.breed in listed else
                               f" :violet-badge[{logic.CROSS}]" if logic.is_cross(s.breed)
                               else f" :violet-badge[{logic.UNVERIFIED}]")
                            + f"  \n{s.seen_on}"
                            + (f" · {md_text(s.location)}" if md_text(s.location) else ""))
                with st.popover("Delete", help="Delete this sighting"):
                    st.write("Delete this sighting? This can't be undone.")
                    if st.button("Delete", key=f"delete_{s.id}", type="primary"):
                        try:
                            backend.delete_sighting(int(s.id))
                        except AuthError as err:
                            end_session(str(err))
                        st.rerun()
            if s.photo_path in my_photos:
                st.markdown(f'<img class="sighting-photo" src="{html.escape(my_photos[s.photo_path])}" '
                            f'alt="Your photo of a {html.escape(s.breed)}" loading="lazy">',
                            unsafe_allow_html=True)
            if tags := dog_tags_html(s.dog_ids):
                st.markdown(tags, unsafe_allow_html=True)
            if s.dog_name:
                st.caption(f"Dog: {s.dog_name}")
            if s.notes:
                st.caption(s.notes)

# --- Social: recent sightings from everyone who shares -------------------------------------
def feed_post(post: dict, links: dict[str, str]) -> str:
    """One sighting in the feed as HTML. Everything members typed is escaped."""
    seen_on = dt.date.fromisoformat(str(post["seen_on"]))
    # The feed is in posting order, so the header shows when it was posted; the date seen
    # gets its own quiet line only when it's a different day (e.g. an older photo).
    posted = logic.posted_on(post.get("created_at"), st.context.timezone) or seen_on
    seen = (f'<div class="sub">Seen {seen_on.day} {seen_on:%b %Y}</div>'
            if seen_on != posted else "")
    who = f"<b>{html.escape(post['username'])}</b>" + (" (you)" if post["user_id"] == user.id else "")
    details = [f"{sketches.svg('pin')} {html.escape(post['location'])}" if post.get("location") else "",
               f"{sketches.svg('dog')} {html.escape(post['dog_name'])}" if post.get("dog_name") else ""]
    lines = [" · ".join(d for d in details if d), html.escape(post.get("notes") or "")]
    photo = (f'<img class="sighting-photo" src="{html.escape(links[post["photo_path"]])}" '
             f'alt="A {html.escape(post["breed"])}" loading="lazy">'
             if post.get("photo_path") in links else "")
    tags = dog_tags_html(post.get("dog_ids"))
    earned = "".join(
        f'<div class="earned {badge.track}">{sketches.svg(badge.icon)} Earned the '
        f'<b>{html.escape(badge.name)}</b> badge: {html.escape(badge.description.lower())}!</div>'
        for key in post.get("badges") or [] if (badge := logic.BADGES_BY_KEY.get(key)))
    return (
        f'<div class="cerb-post">{avatar_html(post["avatar"], "avatar")}'
        f'<div class="main"><div class="who">{who} · {posted.day} {posted:%b %Y}</div>'
        f'<div class="breed">{html.escape(post["breed"])}{breed_chip(post["breed"])}</div>'
        + seen + earned + (f"<div>{tags}</div>" if tags else "")
        + "".join(f'<div class="sub">{line}</div>' for line in lines if line)
        + photo + "</div></div>"
    )


with tab_social:
    st.header("Social")
    st.caption("The latest sightings from everyone who shares them, and the badges they "
               "earn. You can stop sharing yours in Settings > Privacy.")
    if tab_social.open:  # only fetch the feed when someone is looking at it
        try:
            feed = backend.social_feed() if profiles_ready else None
        except AuthError as err:
            end_session(str(err))
        except Exception:
            feed = None
        if feed is None:
            st.info("Social isn't available right now. Please try again later.")
        else:
            if all_dogs:  # look up any member's dog, and the latest posts it's tagged in
                dog_id = st.selectbox("Find a dog", list(dogs_by_id), index=None,
                                      key="social_dog", placeholder="Find a dog by @username",
                                      format_func=lambda i: logic.dog_label(dogs_by_id[i]))
                if dog_id is not None:
                    dog = dogs_by_id[dog_id]
                    feed = [p for p in feed if dog_id in (p.get("dog_ids") or [])]
                    dog_card(dog, photo_links([dog.get("photo_path")]))
                    st.caption(f"Latest posts tagging @{dog['username']}")
            links = photo_links(p.get("photo_path") for p in feed)
            if not feed:
                st.info("No sightings yet. Log a dog and you'll be the first!"
                        if st.session_state.get("social_dog") is None else
                        "No recent posts tag this dog yet.")
            else:
                st.markdown("".join(feed_post(p, links) for p in feed), unsafe_allow_html=True)

# --- Settings ------------------------------------------------------------------------------
def release_card(release: logic.Release, border: bool = True):
    released = dt.date.fromisoformat(release.date)
    # "New" marks the update that made the dot on Settings appear, for this visit.
    badge = " :violet-badge[New]" if st.session_state.get("new_update") == release.version else ""
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
    st.toggle("Dark mode", value=st.session_state.get("theme") == "Dark", key="dark_mode",
              on_change=switch_theme)
    st.caption("Light mode is the default. Your choice is saved on this device.")

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
    st.caption("Project Cerberus: spot dogs, collect breeds. Breeds are the AKC 2025 top 100, plus 41 "
               "more that Photo ID knows.")
    st.caption(f"Version {APP_VERSION}")
