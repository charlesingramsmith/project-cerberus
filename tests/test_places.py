from cerberus import places


def test_a_place_is_looked_up_from_a_rounded_spot():
    asked = []

    def fetch(url):
        asked.append(url)
        return {"address": {"park": "Hyde Park", "city": "London"}}

    assert places.place_for(51.50734, -0.16571, fetch=fetch) == "Hyde Park, London"
    assert "lat=51.507&" in asked[0] and "lon=-0.166&" in asked[0]


def test_failed_lookups_give_no_place():
    def offline(url):
        raise OSError("no network")

    assert places.place_for(51.5, -0.1, fetch=offline) is None
    assert places.place_for(51.5, -0.1, fetch=lambda url: {"error": "Unable"}) is None
