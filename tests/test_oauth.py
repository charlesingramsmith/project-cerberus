"""Tests for the store that remembers Google sign-ins while the user is at Google."""
from cerberus.oauth import PendingSignIns, with_query


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_a_verifier_can_be_collected_once():
    pending = PendingSignIns()
    flow_id = pending.new_flow_id()
    pending.add(flow_id, "verifier-1")
    assert flow_id in pending
    assert pending.pop(flow_id) == "verifier-1"
    assert pending.pop(flow_id) is None  # single use


def test_flow_ids_are_unique_and_unguessable():
    ids = {PendingSignIns.new_flow_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(len(i) >= 20 for i in ids)


def test_unknown_flow_gives_nothing():
    assert PendingSignIns().pop("made-up") is None


def test_flows_expire():
    clock = FakeClock()
    pending = PendingSignIns(ttl=600, clock=clock)
    pending.add("flow", "verifier")
    clock.now = 601
    assert "flow" not in pending
    assert pending.pop("flow") is None


def test_with_query_adds_parameters():
    assert with_query("https://x.app/", flow="abc") == "https://x.app/?flow=abc"
    assert with_query("https://x.app/?flow=abc", code="1 2") == "https://x.app/?flow=abc&code=1+2"
