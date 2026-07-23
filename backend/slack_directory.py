"""Matches team-members.json roster names against the Slack workspace directory.

Used only by the daily job's bulk DM-reminder step. The slash-command path resolves
a single user's own identity via a targeted users.info call instead (slack_routes.py),
so it doesn't depend on this cache's freshness.
"""
import logging
import time

import slack_client

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600
_cache: dict | None = None
_cache_time: float = 0.0


def _normalize(name: str) -> str:
    return name.strip().lower()


def build_directory() -> dict:
    """normalized real name -> {"id": ..., "real_name": ...}, cached briefly."""
    global _cache, _cache_time

    if _cache is not None and (time.time() - _cache_time) < _CACHE_TTL_SECONDS:
        return _cache

    directory: dict[str, dict] = {}
    for u in slack_client.users_list():
        if u.get("is_bot") or u.get("deleted") or u.get("id") == "USLACKBOT":
            continue
        profile = u.get("profile", {})
        real_name = profile.get("real_name_normalized") or profile.get("real_name") or u.get("name", "")
        if not real_name:
            continue
        key = _normalize(real_name)
        if key in directory:
            logger.warning(f"Duplicate normalized Slack name '{key}' -- {u.get('id')} vs {directory[key]['id']}")
            continue
        directory[key] = {"id": u["id"], "real_name": real_name}

    _cache = directory
    _cache_time = time.time()
    return directory


def match_roster(roster_names: list[str], directory: dict) -> tuple[dict, list]:
    """Split roster names into {name: slack_id} matched and a list of unmatched names."""
    matched: dict[str, str] = {}
    unmatched: list[str] = []
    for name in roster_names:
        key = _normalize(name)
        if key in directory:
            matched[name] = directory[key]["id"]
        else:
            unmatched.append(name)
    return matched, unmatched
