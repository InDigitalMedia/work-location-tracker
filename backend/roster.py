"""Resolves the team roster (team-members.json) at runtime for the Slack integration.

The roster is a static frontend asset (frontend/public/team-members.json), fetched
directly by the browser (frontend/src/App.tsx). The backend has no knowledge of it
today. render.yaml's `rootDir: backend` means the physical file's presence inside
the backend's own deploy is unverified, so this fetches it over HTTP from the
already-deployed frontend -- the same source of truth the web app itself uses --
rather than depending on a colocated file existing in production.
"""
import json
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

ROSTER_URL = os.getenv("ROSTER_URL", "https://in-office.vercel.app/team-members.json")
_CACHE_TTL_SECONDS = 600

_cache: list[str] | None = None
_cache_time: float = 0.0


def get_roster() -> list[str]:
    """Return the list of team-member display names, cached for a few minutes."""
    global _cache, _cache_time

    if _cache is not None and (time.time() - _cache_time) < _CACHE_TTL_SECONDS:
        return _cache

    try:
        resp = httpx.get(ROSTER_URL, timeout=5)
        resp.raise_for_status()
        names = resp.json()["teamMembers"]
    except Exception as e:
        logger.warning(f"Could not fetch roster from {ROSTER_URL}: {e}")
        # Local-file fallback: dev/docker-compose convenience only, where both
        # frontend/ and backend/ are checked out side by side. Never rely on this
        # in production -- render.yaml only deploys backend/.
        local = Path(__file__).parent.parent / "frontend" / "public" / "team-members.json"
        if local.exists():
            logger.info(f"Falling back to local roster file: {local}")
            names = json.loads(local.read_text())["teamMembers"]
        else:
            raise

    _cache = names
    _cache_time = time.time()
    return names
