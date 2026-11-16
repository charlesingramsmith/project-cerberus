"""End-to-end check of the Streamlit app using Streamlit's built-in test runner."""
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def log_breed(at: AppTest, breed_name: str) -> AppTest:
    breed = next(sb for sb in at.main.selectbox if sb.label == "Breed")
    index = next(i for i, label in enumerate(breed.options) if label.startswith(breed_name))
    breed.select_index(index)
    submit = next(b for b in at.main.button if b.label == "Log sighting")
    return submit.click().run()


def test_create_spotter_and_log_sightings(tmp_path, monkeypatch):
    monkeypatch.setenv("CERBERUS_DB", str(tmp_path / "test.db"))
    st.cache_resource.clear()

    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert "Welcome" in at.header[0].value

    # Create a spotter
    at.sidebar.text_input[0].input("charlie")
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert at.header[0].value == "charlie's life list"
    assert at.metric[0].value == "0 / 100"

    # First Beagle is a lifer
    at = log_breed(at, "Beagle")
    assert not at.exception
    assert "New lifer" in at.success[0].value
    assert at.metric[0].value == "1 / 100"

    # Second Beagle is just another sighting
    at = log_breed(at, "Beagle")
    assert not at.exception
    assert "another" in at.info[0].value
    assert at.metric[0].value == "1 / 100"
    assert at.metric[1].value == "2"

    st.cache_resource.clear()
