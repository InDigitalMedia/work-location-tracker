"""The daily Slack job: Neal Street digest to a channel + quick-fill DM reminders.

Triggered by POST /internal/slack/daily-notifications, which a GitHub Actions cron
calls twice a day (08:00 and 09:00 UTC) so this can gate on "is it actually 9am
London time" without ever needing the cron expression edited for BST/GMT.
"""
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session

import queries
import roster
import slack_client
import slack_directory
import slack_views

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")
TARGET_HOUR = int(os.getenv("SLACK_DAILY_HOUR", "9"))
AFTERNOON_TARGET_HOUR = int(os.getenv("SLACK_AFTERNOON_HOUR", "16"))
SLACK_GENERAL_CHANNEL_ID = os.getenv("SLACK_GENERAL_CHANNEL_ID")


def monday_of(date_obj) -> str:
    monday = date_obj - timedelta(days=date_obj.weekday())
    return monday.strftime("%Y-%m-%d")


def run_daily_notifications(session: Session, force: bool = False) -> dict:
    """force=True skips the weekday/hour gate entirely -- used for manual test
    runs (see slack_routes.py's trigger_daily_notifications), so someone can
    actually see real messages sent on demand rather than the endpoint silently
    no-opping outside the real 9am-London/weekday window. The scheduled GitHub
    Actions cron never sets this -- only a human explicitly asking to force it."""
    now = datetime.now(LONDON_TZ)

    if not force:
        if now.weekday() >= 5:
            return {"ok": True, "skipped": "weekend"}
        if now.hour != TARGET_HOUR:
            return {"ok": True, "skipped": "not target hour", "hour": now.hour}

    today_str = now.strftime("%Y-%m-%d")
    week_start = monday_of(now.date())

    neal_street_count = _post_neal_street_digest(session, week_start, today_str)
    reminders_sent, unmatched = _send_unfilled_reminders(session, week_start)

    return {
        "ok": True,
        "neal_street_count": neal_street_count,
        "reminders_sent": reminders_sent,
        "unmatched_roster_names": unmatched,
    }


def _post_neal_street_digest(session: Session, week_start: str, today_str: str) -> int:
    return _post_neal_street_digest_for_day(session, week_start, today_str, "today")


def _post_neal_street_digest_for_day(session: Session, week_start: str, date_str: str, when_label: str) -> int:
    if not SLACK_GENERAL_CHANNEL_ID:
        logger.warning("SLACK_GENERAL_CHANNEL_ID not configured -- skipping Neal Street digest")
        return 0

    week_entries = queries.get_week_entries(session, week_start)
    people = sorted({
        row.user_name for row in week_entries
        if row.date == date_str and row.location == "Neal Street"
    })

    if people:
        text = f"🏢 At Neal Street {when_label}: {', '.join(people)}"
    else:
        text = f"🏢 Nobody's logged as being at Neal Street {when_label}."

    slack_client.post_message(SLACK_GENERAL_CHANNEL_ID, text)
    return len(people)


def run_tomorrow_digest(session: Session, force: bool = False) -> dict:
    """Posts to the Neal Street channel at 4pm London time announcing who's in
    tomorrow, so people can plan around it same-day. force=True bypasses every
    gate below for manual test runs (see trigger_tomorrow_digest in
    slack_routes.py) -- the scheduled GitHub Actions cron never sets it."""
    now = datetime.now(LONDON_TZ)
    tomorrow = now.date() + timedelta(days=1)

    if not force:
        if now.weekday() >= 5:
            return {"ok": True, "skipped": "weekend"}
        if now.hour != AFTERNOON_TARGET_HOUR:
            return {"ok": True, "skipped": "not target hour", "hour": now.hour}
        if tomorrow.weekday() >= 5:
            return {"ok": True, "skipped": "tomorrow is a weekend"}

    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    week_start = monday_of(tomorrow)

    neal_street_count = _post_neal_street_digest_for_day(session, week_start, tomorrow_str, "tomorrow")
    return {"ok": True, "neal_street_count": neal_street_count}


def _send_unfilled_reminders(session: Session, week_start: str) -> tuple[int, list]:
    roster_names = roster.get_roster()
    submitted_names = queries.get_submitted_users(session, week_start)
    submitted_keys = {name.strip().lower() for name in submitted_names}

    unfilled_names = [name for name in roster_names if name.strip().lower() not in submitted_keys]
    if not unfilled_names:
        return 0, []

    directory = slack_directory.build_directory()
    matched, unmatched = slack_directory.match_roster(unfilled_names, directory)

    if unmatched:
        logger.warning(f"Roster names with no Slack directory match: {unmatched}")

    sent = 0
    for name, slack_id in matched.items():
        user_key = name.strip().lower()
        last_week = queries.get_last_week_entries_for_user(session, user_key, week_start)
        has_split = any(slot["morning"] or slot["afternoon"] for slot in last_week.values())

        message = slack_views.build_quickfill_message(week_start, has_split_last_week=has_split)
        dm_channel = slack_client.open_dm(slack_id)
        if not dm_channel:
            continue
        slack_client.post_message(dm_channel, message["text"], blocks=message["blocks"])
        sent += 1

    return sent, unmatched
