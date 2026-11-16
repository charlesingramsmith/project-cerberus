"""Project Cerberus: log the dogs you spot and build your breed life list.

Run with:  streamlit run app.py
"""
import datetime as dt
import os

import pandas as pd
import streamlit as st

from cerberus import logic
from cerberus.backends import AuthError, MemoryBackend, SupabaseBackend

st.set_page_config(page_title="Project Cerberus", page_icon="🐕", layout="wide")

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
    if message:
        st.session_state.auth_notice = message
    st.rerun()


# --- Sign in / create account ---------------------------------------------------------
def auth_screen():
    st.title("🐕 Project Cerberus")
    st.write("Spot dogs. Collect breeds. Can you find all 100?")
    if backend.demo:
        st.warning(DEMO_NOTICE)
    notice = st.session_state.pop("auth_notice", None)
    if notice:
        st.info(notice)

    sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("sign_in"):
            email = st.text_input("Email", key="sign_in_email")
            password = st.text_input("Password", type="password", key="sign_in_password")
            if st.form_submit_button("Sign in", type="primary"):
                try:
                    st.session_state.user = backend.sign_in(email, password)
                except AuthError as err:
                    st.error(str(err))
                else:
                    st.rerun()

    with sign_up_tab:
        with st.form("sign_up"):
            username = st.text_input("Username", key="sign_up_username",
                                     help="Shown on your life list. 3 to 30 characters.")
            email = st.text_input("Email", key="sign_up_email")
            password = st.text_input("Password", type="password", key="sign_up_password",
                                     help="At least 8 characters.")
            confirm = st.text_input("Confirm password", type="password", key="sign_up_confirm")
            if st.form_submit_button("Create account", type="primary"):
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
                            st.rerun()


if "user" not in st.session_state:
    auth_screen()
    st.stop()

user = st.session_state.user

# --- Sidebar --------------------------------------------------------------------------------
with st.sidebar:
    st.title("🐕 Project Cerberus")
    st.write(f"Signed in as **{user.username}**")
    st.caption(user.email)
    if st.button("Sign out"):
        backend.sign_out()
        end_session()
    if backend.demo:
        st.warning(DEMO_NOTICE)

# --- Load this spotter's data ---------------------------------------------------------------
breeds = load_breeds()
try:
    sightings = logic.sightings_frame(backend.list_sightings())
except AuthError as err:
    end_session(str(err))

life = logic.life_list(breeds, sightings)
seen = life["times_seen"] > 0
collected, total = int(seen.sum()), len(life)

st.header(f"{user.username}'s life list")
c1, c2, c3 = st.columns(3)
c1.metric("Lifers", f"{collected} / {total}")
c2.metric("Total sightings", len(sightings))
c3.metric("Still to find", total - collected)
st.progress(collected / total if total else 0.0)

flash = st.session_state.pop("flash", None)
if flash:
    kind, breed_name = flash
    if kind == "lifer":
        st.balloons()
        st.success(f"🎉 New lifer! **{breed_name}** is on your life list.")
    else:
        st.info(f"Logged another **{breed_name}**.")

tab_log, tab_life, tab_history = st.tabs(["Log a sighting", "Life list", "Sightings"])

# --- Log a sighting -------------------------------------------------------------------------
with tab_log:
    seen_breeds = set(life.loc[seen, "breed"])

    def breed_label(name: str) -> str:
        return name if name in seen_breeds else f"{name}  ✨ new"

    with st.form("log_sighting", clear_on_submit=True):
        breed = st.selectbox(
            "Breed",
            breeds["breed"].tolist(),
            index=None,
            format_func=breed_label,
            placeholder="Start typing a breed…",
        )
        seen_on = st.date_input("Date seen", value=dt.date.today(), max_value=dt.date.today())
        left, right = st.columns(2)
        dog_name = left.text_input("Dog's name (if you found out)")
        location = right.text_input("Where")
        notes = st.text_area("Notes", placeholder="Good boy. Very fluffy.")
        submitted = st.form_submit_button("Log sighting", type="primary")

    st.caption("📷 Photo identification is on the roadmap. For now, pick the breed yourself.")

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
with tab_life:
    show = st.radio("Show", ["All", "Collected", "Still to find"], horizontal=True)
    view = life
    if show == "Collected":
        view = life[seen]
    elif show == "Still to find":
        view = life[~seen]

    table = pd.DataFrame({
        "Rank": view["rank"],
        "": view["times_seen"].map(lambda n: "✅" if n else "⬜"),
        "Breed": view["breed"],
        "First seen": view["first_seen"],
        "Times seen": view["times_seen"],
    })
    st.dataframe(table, hide_index=True)
    st.caption("Breeds ranked by AKC 2025 popularity.")

# --- Sightings history ----------------------------------------------------------------------
with tab_history:
    if sightings.empty:
        st.info("No sightings yet. Go find a dog!")
    else:
        st.dataframe(
            sightings.drop(columns="id").rename(columns={
                "seen_on": "Date", "breed": "Breed", "dog_name": "Name",
                "location": "Where", "notes": "Notes",
            }),
            hide_index=True,
        )
        with st.expander("Delete a sighting"):
            labels = {int(r.id): f"{r.seen_on} · {r.breed}" for r in sightings.itertuples()}
            to_delete = st.selectbox("Sighting", list(labels), format_func=labels.get)
            if st.button("Delete sighting"):
                try:
                    backend.delete_sighting(to_delete)
                except AuthError as err:
                    end_session(str(err))
                st.rerun()
