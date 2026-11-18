"""Project Cerberus: log the dogs you spot and build your breed life list.

Run with:  streamlit run app.py
"""
import datetime as dt
import html
import os

import pandas as pd
import streamlit as st

from cerberus import logic
from cerberus.backends import AuthError, MemoryBackend, SupabaseBackend
from cerberus.oauth import PENDING, with_query, with_trailing_slash
from cerberus.remember import COOKIE_NAME, MAX_AGE_DAYS, cookie_script

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
button { min-height: 2.75rem; }

/* Life list and sightings rows */
.cerb-row {
    display: flex; align-items: center; gap: .75rem;
    padding: .6rem .25rem; border-bottom: 1px solid rgba(128, 128, 128, .2);
}
.cerb-row .icon { font-size: 1.25rem; width: 1.5rem; text-align: center; }
.cerb-row .dot {
    display: inline-block; width: 1rem; height: 1rem;
    border: 2px solid rgba(128, 128, 128, .5); border-radius: 50%;
}
.cerb-row .main { flex: 1; min-width: 0; }
.cerb-row .name { font-weight: 600; }
.cerb-row .sub { font-size: .85rem; opacity: .7; }
.cerb-row .rank { font-size: .8rem; opacity: .6; }
.cerb-row.missing .name { font-weight: 400; opacity: .75; }

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


@st.cache_data
def load_breeds() -> pd.DataFrame:
    return logic.load_breeds()


# One backend per browser session, so sign-ins are never shared between visitors.
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
# See cerberus/remember.py. The cookie holds a single-use refresh token, so whenever the
# token changes (sign-in, a returning visit, an hourly refresh) the new one is written back.
def resume_remembered_sign_in():
    """Once per visit: if the browser has a saved sign-in, use it."""
    if st.session_state.get("resume_tried"):
        return
    st.session_state.resume_tried = True
    # What the browser had when this visit started; sync_cookie() tracks it from here.
    token = st.context.cookies.get(COOKIE_NAME)
    st.session_state.cookie_token = token
    if not token:
        return
    try:
        st.session_state.user = backend.resume_session(token)
    except AuthError:
        return  # expired or signed out elsewhere: sync_cookie() deletes the stale cookie
    st.session_state.remember = True


def sync_cookie():
    """Make the browser's cookie match this visit: the current token, or nothing."""
    wanted = backend.refresh_token() if st.session_state.get("remember") else None
    if wanted != st.session_state.get("cookie_token"):
        st.html(cookie_script(wanted), unsafe_allow_javascript=True)
        st.session_state.cookie_token = wanted


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
if "user" not in st.session_state:
    resume_remembered_sign_in()
if "user" not in st.session_state:
    sync_cookie()  # clears a saved sign-in that has expired or was signed out
    auth_screen()
    st.stop()

user = st.session_state.user

if backend.demo:
    st.caption("⚠️ Demo mode: accounts and sightings vanish when you close this tab.")

# --- Load this spotter's data ---------------------------------------------------------------
breeds = load_breeds()
try:
    sightings = logic.sightings_frame(backend.list_sightings())
except AuthError as err:
    end_session(str(err))

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

# The five main tabs. The "main_nav" key lets MOBILE_CSS pin them to the bottom of the
# screen as a tab bar; the "\n" puts each icon above its label.
NAV_TABS = ["🔍\nDog ID", "📋\nLife list", "👤\nProfile", "👥\nSocial", "⚙️\nSettings"]
with st.container(key="main_nav"):
    tab_id, tab_life, tab_profile, tab_social, tab_settings = st.tabs(NAV_TABS)

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
        location = st.text_input("Where")
        notes = st.text_area("Notes", placeholder="Good boy. Very fluffy.", height=80)
        submitted = st.form_submit_button("Log sighting", type="primary", width="stretch")

    st.caption("📷 Photo ID and a guided \"help me identify\" are on the roadmap. "
               "For now, pick the breed yourself.")

    if submitted:
        if breed is None:
            st.warning("Pick a breed first.")
        else:
            lifer = logic.is_lifer(sightings, breed)
            try:
                backend.add_sighting(breed, seen_on, location, dog_name, notes)
            except AuthError as err:
                end_session(str(err))
            st.session_state.flash = ("lifer" if lifer else "repeat", breed)
            st.rerun()

# --- Life list ----------------------------------------------------------------------------------
def life_row(row) -> str:
    """One breed as a compact list row (a wide table is hard to read on a phone)."""
    if row.times_seen:
        css, icon = "cerb-row", "✅"
        detail = f"First seen {row.first_seen} · seen {row.times_seen}×"
    else:
        css, icon, detail = "cerb-row missing", "<span class=\"dot\"></span>", "Not spotted yet"
    return (
        f'<div class="{css}"><span class="icon">{icon}</span>'
        f'<div class="main"><div class="name">{html.escape(row.breed)}</div>'
        f'<div class="sub">{detail}</div></div>'
        f'<span class="rank">#{row.rank}</span></div>'
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
        st.markdown("".join(life_row(r) for r in view.itertuples()), unsafe_allow_html=True)
    st.caption("Breeds ranked by AKC 2025 popularity.")

# --- Your profile: who you are, plus every sighting you've logged ------------------------------
with tab_profile:
    st.header("Your profile")
    with st.container(border=True):
        st.markdown(f"### 👤 {user.username}")
        if sightings.empty:
            st.caption("No sightings yet.")
        else:
            st.caption(f"Spotting since {sightings['seen_on'].min()} · "
                       f"{collected} lifer{'' if collected == 1 else 's'} from "
                       f"{len(sightings)} sighting{'' if len(sightings) == 1 else 's'}")

    st.subheader("Your sightings")
    if sightings.empty:
        st.info("No sightings yet. Go find a dog!")
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
            if s.dog_name:
                st.caption(f"🐶 {s.dog_name}")
            if s.notes:
                st.caption(s.notes)

# --- Social (placeholder until friends and shared life lists are built) ----------------------
with tab_social:
    st.header("Social")
    st.info("Coming soon: follow friends, compare life lists and see who spots the most breeds.")

# --- Settings ------------------------------------------------------------------------------
with tab_settings:
    st.header("Settings")
    st.subheader("Account")
    with st.container(border=True):
        st.write(f"Signed in as **{user.username}**")
        st.caption(user.email)
        if st.button("Sign out", width="stretch"):
            backend.sign_out()
            end_session()
    st.subheader("Appearance")
    st.caption("Light or dark mode follows your phone or computer setting.")
    st.subheader("About")
    st.caption("Project Cerberus: spot dogs, collect breeds. Breeds are the AKC 2025 top 100.")

# Last, so it saves any refresh token that changed during this run.
sync_cookie()
