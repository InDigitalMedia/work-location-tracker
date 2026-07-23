"""Resolves the predefined client list (clients.json) at runtime for the Slack
integration's Client Office dropdown -- mirrors roster.py exactly (same static
frontend asset pattern, same reason to fetch over HTTP rather than assume the
file is present in the backend's own deploy)."""
import json
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CLIENTS_URL = os.getenv("CLIENTS_URL", "https://in-office.vercel.app/clients.json")
_CACHE_TTL_SECONDS = 600

_cache: list[str] | None = None
_cache_time: float = 0.0


def get_clients() -> list[str]:
    """Return the list of predefined client names, cached for a few minutes."""
    global _cache, _cache_time

    if _cache is not None and (time.time() - _cache_time) < _CACHE_TTL_SECONDS:
        return _cache

    try:
        resp = httpx.get(CLIENTS_URL, timeout=5)
        resp.raise_for_status()
        names = resp.json()["clients"]
    except Exception as e:
        logger.warning(f"Could not fetch clients from {CLIENTS_URL}: {e}")
        local = Path(__file__).parent.parent / "frontend" / "public" / "clients.json"
        if local.exists():
            logger.info(f"Falling back to local clients file: {local}")
            names = json.loads(local.read_text())["clients"]
        else:
            raise

    _cache = names
    _cache_time = time.time()
    return names
