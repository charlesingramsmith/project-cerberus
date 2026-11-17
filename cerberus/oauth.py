"""Remembering a "Continue with Google" sign-in while the user is away at Google.

Google sign-in uses PKCE: before sending the user to Google we create a secret
"code verifier", and when Google sends them back with a one-time code we must
present that same verifier to finish signing in.

The catch with Streamlit: coming back from Google loads the app afresh, which
starts a brand-new Streamlit session, so anything kept in `st.session_state` is
gone. So the verifier waits here instead, in server memory, under a random
"flow id" that travels in the return URL (`?flow=...`).

This is the one deliberately shared store in the app. It is safe because it only
ever holds short-lived, single-use verifiers keyed by unguessable ids: never a
signed-in session, never a backend.
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Callable
from urllib.parse import urlencode

FLOW_TTL_SECONDS = 10 * 60  # how long the user has to finish signing in at Google


class PendingSignIns:
    def __init__(self, ttl: float = FLOW_TTL_SECONDS,
                 clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl
        self._clock = clock
        self._flows: dict[str, tuple[str, float]] = {}  # flow id -> (verifier, created at)
        self._lock = threading.Lock()  # Streamlit serves each visitor on its own thread

    def _drop_expired(self) -> None:
        cutoff = self._clock() - self._ttl
        for flow_id in [f for f, (_, created) in self._flows.items() if created < cutoff]:
            del self._flows[flow_id]

    @staticmethod
    def new_flow_id() -> str:
        """A fresh, unguessable id to put in the return URL."""
        return secrets.token_urlsafe(16)

    def add(self, flow_id: str, verifier: str) -> None:
        """Keep a verifier until the user comes back with this flow id."""
        with self._lock:
            self._drop_expired()
            self._flows[flow_id] = (verifier, self._clock())

    def __contains__(self, flow_id: str) -> bool:
        with self._lock:
            self._drop_expired()
            return flow_id in self._flows

    def pop(self, flow_id: str) -> str | None:
        """Take the verifier out (each one works once). None if unknown or expired."""
        with self._lock:
            self._drop_expired()
            entry = self._flows.pop(flow_id, None)
        return entry[0] if entry else None


# Lives for as long as the server process, because Python only imports a module once.
PENDING = PendingSignIns()


def with_query(url: str, **params: str) -> str:
    """Add query parameters to a URL that may or may not already have some."""
    return url + ("&" if "?" in url else "?") + urlencode(params)
