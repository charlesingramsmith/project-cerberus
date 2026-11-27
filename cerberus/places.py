"""Place names for a photo's location, from OpenStreetMap's free reverse geocoder.

Spotted! uses this to suggest "Where" from a photo's GPS spot. The spot is rounded to about
100 m before it's sent (`logic.photo_details`), only the place name comes back, and nothing
here is saved. Nominatim's rules (https://operations.osmfoundation.org/policies/nominatim/):
name the app in the User-Agent, at most one lookup a second, and cache results (app.py
keeps them in `st.cache_data`). Any problem (offline, slow, refused) just gives None.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from cerberus import logic

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "project-cerberus dog spotting app (https://project-cerberus.streamlit.app)"
TIMEOUT = 4  # seconds: a suggestion isn't worth a long wait


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)


def place_for(lat: float, lon: float, fetch=None) -> str | None:
    """A short place name near (lat, lon), like "Hyde Park, London", or None.
    `fetch` (url -> parsed JSON) is for tests; by default it asks Nominatim."""
    query = urllib.parse.urlencode({
        "format": "jsonv2", "lat": f"{lat:.{logic.PLACE_DECIMALS}f}",
        "lon": f"{lon:.{logic.PLACE_DECIMALS}f}", "zoom": 16, "addressdetails": 1,
        "accept-language": "en"})
    try:
        found = (fetch or fetch_json)(f"{NOMINATIM_URL}?{query}")
        return logic.place_name(found.get("address") or {})
    except Exception:  # offline, timed out, refused, or an answer we don't understand
        return None
