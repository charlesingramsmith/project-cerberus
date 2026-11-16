"""Project Cerberus: log the dogs you spot and build your breed life list.

Run with:  streamlit run app.py
"""
import datetime as dt

import pandas as pd
import streamlit as st

from cerberus import db

st.set_page_config(page_title="Project Cerberus", page_icon="🐕", layout="wide")


@st.cache_resource
def get_conn():
    return db.connect()


conn = get_conn()
NEW_SPOTTER = "➕ New spotter…"

# --- Sidebar: who's spotting? -------------------------------------------------
with st.sidebar:
    st.title("🐕 Project Cerberus")
    st.caption("Spot dogs. Collect breeds. Catch 'em all.")

    users = [u["username"] for u in db.list_users(conn)]
    options = users + [NEW_SPOTTER]
    current = st.session_state.get("username")
    index = options.index(current) if current in options else 0
    choice = st.selectbox("Spotter", options, index=index)

    if choice == NEW_SPOTTER:
        with st.form("new_spotter", clear_on_submit=True):
            name = st.text_input("Choose a username")
            if st.form_submit_button("Create spotter", type="primary"):
                try:
                    created = db.get_or_create_user(conn, name)
                except ValueError as err:
                    st.error(str(err))
                else:
                    st.session_state.username = created["username"]
                    st.rerun()
    else:
        st.session_state.username = choice

if choice == NEW_SPOTTER:
    st.header("Welcome to Project Cerberus 🐕")
    st.info("Create a spotter in the sidebar to start your dog breed life list.")
    st.stop()

user = db.get_or_create_user(conn, st.session_state.username)

# --- Headline stats -------------------------------------------------------------
life = pd.DataFrame([dict(r) for r in db.life_list(conn, user["id"])])
seen = life["times_seen"] > 0
collected, total = int(seen.sum()), len(life)

st.header(f"{user['username']}'s life list")
c1, c2, c3 = st.columns(3)
c1.metric("Lifers", f"{collected} / {total}")
c2.metric("Total sightings", int(life["times_seen"].sum()))
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

# --- Log a sighting -------------------------------------------------------------
with tab_log:
    breeds = db.list_breeds(conn)
    names = {b["id"]: b["name"] for b in breeds}
    seen_ids = set(life.loc[seen, "id"])

    def breed_label(breed_id: int) -> str:
        return names[breed_id] if breed_id in seen_ids else f"{names[breed_id]}  ✨ new"

    with st.form("log_sighting", clear_on_submit=True):
        breed_id = st.selectbox(
            "Breed",
            list(names),
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
        if breed_id is None:
            st.warning("Pick a breed first.")
        else:
            lifer = db.log_sighting(conn, user["id"], breed_id, seen_on, location, dog_name, notes)
            st.session_state.flash = ("lifer" if lifer else "repeat", names[breed_id])
            st.rerun()

# --- Life list ------------------------------------------------------------------
with tab_life:
    show = st.radio("Show", ["All", "Collected", "Still to find"], horizontal=True)
    view = life
    if show == "Collected":
        view = life[seen]
    elif show == "Still to find":
        view = life[~seen]

    table = pd.DataFrame({
        "Rank": view["popularity_rank"],
        "": view["times_seen"].map(lambda n: "✅" if n else "⬜"),
        "Breed": view["name"],
        "First seen": view["first_seen"],
        "Times seen": view["times_seen"],
    })
    st.dataframe(table, hide_index=True)
    st.caption("Breeds ranked by AKC 2025 popularity.")

# --- Sightings history ------------------------------------------------------------
with tab_history:
    rows = db.list_sightings(conn, user["id"])
    if not rows:
        st.info("No sightings yet. Go find a dog!")
    else:
        history = pd.DataFrame([dict(r) for r in rows])
        st.dataframe(
            history.drop(columns="id").rename(columns={
                "seen_on": "Date", "breed": "Breed", "dog_name": "Name",
                "location": "Where", "notes": "Notes",
            }),
            hide_index=True,
        )
        with st.expander("Delete a sighting"):
            labels = {r["id"]: f"{r['seen_on']} · {r['breed']}" for r in rows}
            to_delete = st.selectbox("Sighting", list(labels), format_func=labels.get)
            if st.button("Delete sighting"):
                db.delete_sighting(conn, user["id"], to_delete)
                st.rerun()
