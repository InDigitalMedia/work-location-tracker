"""The Slack scheduled jobs: Neal Street digests to a channel + quick-fill DM reminders.

Triggered by POST /internal/slack/daily-digest, /internal/slack/unfilled-reminders,
/internal/slack/tomorrow-digest, and /internal/slack/next-week-reminder, each called
twice by a GitHub Actions cron (once per UTC-equivalent of the target London hour) so
this can gate on "is it actually the target hour in London" without ever needing a
cron expression edited for BST/GMT.
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
FRIDAY_TARGET_HOUR = int(os.getenv("SLACK_FRIDAY_HOUR", "14"))
SLACK_GENERAL_CHANNEL_ID = os.getenv("SLACK_GENERAL_CHANNEL_ID")

# Set to a Slack real name (e.g. "Cam Doherty") to restrict every outbound
# message below -- channel digests and DM reminders alike -- to just that
# person, without touching the real team. Meant to be a temporary flip while
# testing a change; unset it to go back to normal broadcast behavior.
TEST_MODE_USER_NAME = os.getenv("SLACK_TEST_MODE_USER_NAME")


def monday_of(date_obj) -> str:
    monday = date_obj - timedelta(days=date_obj.weekday())
    return monday.strftime("%Y-%m-%d")


def _test_mode_recipient(directory: dict) -> tuple[str, str] | None:
    if not TEST_MODE_USER_NAME:
        return None
    match = directory.get(TEST_MODE_USER_NAME.strip().lower())
    if not match:
        logger.warning(f"SLACK_TEST_MODE_USER_NAME '{TEST_MODE_USER_NAME}' not found in Slack directory")
        return None
    return TEST_MODE_USER_NAME, match["id"]


def _resolve_digest_channel(directory: dict | None = None) -> str | None:
    """The real Neal Street channel, or -- while SLACK_TEST_MODE_USER_NAME is
    set -- a DM to that one person instead, so digests can be tested without
    posting to the whole team's channel."""
    if TEST_MODE_USER_NAME:
        directory = directory if directory is not None else slack_directory.build_directory()
        recipient = _test_mode_recipient(directory)
        if recipient is None:
            return None
        _, slack_id = recipient
        return slack_client.open_dm(slack_id)

    if not SLACK_GENERAL_CHANNEL_ID:
        logger.warning("SLACK_GENERAL_CHANNEL_ID not configured -- skipping Neal Street digest")
        return None
    return SLACK_GENERAL_CHANNEL_ID


def _restrict_to_test_mode(matched: dict) -> dict:
    """While SLACK_TEST_MODE_USER_NAME is set, drop every matched reminder
    recipient except that one person, so testing doesn't DM the whole team."""
    if not TEST_MODE_USER_NAME:
        return matched
    key = TEST_MODE_USER_NAME.strip().lower()
    return {name: slack_id for name, slack_id in matched.items() if name.strip().lower() == key}


def run_today_digest(session: Session, force: bool = False) -> dict:
    """Posts to the Neal Street channel at 9am London time announcing who's in
    today. force=True bypasses the weekday/hour gate entirely -- used for
    manual test runs (see trigger_today_digest in slack_routes.py) -- the
    scheduled GitHub Actions cron never sets it."""
    now = datetime.now(LONDON_TZ)

    if not force:
        if now.weekday() >= 5:
            return {"ok": True, "skipped": "weekend"}
        if now.hour != TARGET_HOUR:
            return {"ok": True, "skipped": "not target hour", "hour": now.hour}

    today_str = now.strftime("%Y-%m-%d")
    week_start = monday_of(now.date())

    neal_street_count = _post_neal_street_digest(session, week_start, today_str)
    return {"ok": True, "neal_street_count": neal_street_count}


def run_unfilled_reminders(session: Session, force: bool = False) -> dict:
    """DMs a quick-fill prompt at 9am London to anyone who hasn't yet entered
    this week's locations. force=True bypasses the weekday/hour gate entirely
    -- used for manual test runs (see trigger_unfilled_reminders in
    slack_routes.py) -- the scheduled GitHub Actions cron never sets it."""
    now = datetime.now(LONDON_TZ)

    if not force:
        if now.weekday() >= 5:
            return {"ok": True, "skipped": "weekend"}
        if now.hour != TARGET_HOUR:
            return {"ok": True, "skipped": "not target hour", "hour": now.hour}

    week_start = monday_of(now.date())
    reminders_sent, unmatched = _send_quickfill_reminders(session, week_start)

    return {
        "ok": True,
        "reminders_sent": reminders_sent,
        "unmatched_roster_names": unmatched,
    }


def _post_neal_street_digest(session: Session, week_start: str, today_str: str) -> int:
    directory = slack_directory.build_directory()
    channel = _resolve_digest_channel(directory)
    if not channel:
        return 0

    week_entries = queries.get_week_entries(session, week_start)
    day_rows = [row for row in week_entries if row.date == today_str and row.location in ("Neal Street", "Client Office")]

    message = slack_views.build_neal_street_today_message(today_str, day_rows, directory)
    slack_client.post_message(channel, message["text"], blocks=message["blocks"])
    return len({row.user_name for row in day_rows})


def run_tomorrow_digest(session: Session, force: bool = False) -> dict:
    """Posts to the Neal Street channel at 4pm London time. On Mon-Thu this
    announces who's in tomorrow; on Friday, "tomorrow" would be Saturday (not
    useful), so it instead posts the whole of next week's schedule -- one
    action, branching on which day it's run, rather than a separate Friday-only
    job. force=True bypasses the weekday/hour gate below for manual test runs
    (see trigger_tomorrow_digest in slack_routes.py) -- the scheduled GitHub
    Actions cron never sets it."""
    now = datetime.now(LONDON_TZ)

    if not force:
        if now.weekday() >= 5:
            return {"ok": True, "skipped": "weekend"}
        if now.hour != AFTERNOON_TARGET_HOUR:
            return {"ok": True, "skipped": "not target hour", "hour": now.hour}

    if now.weekday() == 4:
        next_week_start = monday_of(now.date() + timedelta(days=7))
        neal_street_count = _post_neal_street_next_week_digest(session, next_week_start)
        return {"ok": True, "neal_street_count": neal_street_count, "period": "next_week"}

    tomorrow = now.date() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    week_start = monday_of(tomorrow)

    neal_street_count = _post_neal_street_tomorrow_digest(session, week_start, tomorrow_str)
    return {"ok": True, "neal_street_count": neal_street_count, "period": "tomorrow"}


def _post_neal_street_tomorrow_digest(session: Session, week_start: str, tomorrow_str: str) -> int:
    directory = slack_directory.build_directory()
    channel = _resolve_digest_channel(directory)
    if not channel:
        return 0

    week_entries = queries.get_week_entries(session, week_start)
    day_rows = [row for row in week_entries if row.date == tomorrow_str and row.location in ("Neal Street", "Client Office")]

    message = slack_views.build_neal_street_tomorrow_message(tomorrow_str, day_rows, directory)
    slack_client.post_message(channel, message["text"], blocks=message["blocks"])
    return len({row.user_name for row in day_rows})


def _post_neal_street_next_week_digest(session: Session, next_week_start: str) -> int:
    directory = slack_directory.build_directory()
    channel = _resolve_digest_channel(directory)
    if not channel:
        return 0

    week_entries = queries.get_week_entries(session, next_week_start)
    message = slack_views.build_neal_street_week_message(
        week_entries,
        next_week_start,
        directory,
        header_text=":wave: Good afternoon everyone! Here's who will be at Neal Street next week :point_down:",
    )
    slack_client.post_message(channel, message["text"], blocks=message["blocks"])
    return len({row.user_name for row in week_entries if row.location in ("Neal Street", "Client Office")})


def run_next_week_reminder(session: Session, force: bool = False) -> dict:
    """Posts a quick-fill DM at 2pm London every Friday, prompting anyone who
    hasn't yet entered next week's locations to do so ahead of time. Reuses the
    same quick-fill flow as the same-week reminder -- "Same as last week" here
    naturally means "same as this week", since it's relative to next week's
    Monday. force=True bypasses the Friday/hour gate for manual test runs."""
    now = datetime.now(LONDON_TZ)

    if not force:
        if now.weekday() != 4:
            return {"ok": True, "skipped": "not friday"}
        if now.hour != FRIDAY_TARGET_HOUR:
            return {"ok": True, "skipped": "not target hour", "hour": now.hour}

    next_week_start = monday_of(now.date() + timedelta(days=7))
    reminders_sent, unmatched = _send_quickfill_reminders(
        session, next_week_start, header_text="📅 Time to plan next week! Let us know where you'll be."
    )

    return {
        "ok": True,
        "reminders_sent": reminders_sent,
        "unmatched_roster_names": unmatched,
    }


def _send_quickfill_reminders(session: Session, week_start: str, header_text: str | None = None) -> tuple[int, list]:
    roster_names = roster.get_roster()
    submitted_names = queries.get_submitted_users(session, week_start)
    submitted_keys = {name.strip().lower() for name in submitted_names}

    unfilled_names = [name for name in roster_names if name.strip().lower() not in submitted_keys]
    if not unfilled_names:
        return 0, []

    directory = slack_directory.build_directory()
    matched, unmatched = slack_directory.match_roster(unfilled_names, directory)
    matched = _restrict_to_test_mode(matched)

    if unmatched:
        logger.warning(f"Roster names with no Slack directory match: {unmatched}")

    sent = 0
    for name, slack_id in matched.items():
        user_key = name.strip().lower()
        last_week = queries.get_last_week_entries_for_user(session, user_key, week_start)
        has_split = any(slot["morning"] or slot["afternoon"] for slot in last_week.values())

        message = slack_views.build_quickfill_message(
            week_start, has_split_last_week=has_split, header_text=header_text, mention=f"<@{slack_id}>"
        )
        dm_channel = slack_client.open_dm(slack_id)
        if not dm_channel:
            continue
        slack_client.post_message(dm_channel, message["text"], blocks=message["blocks"])
        sent += 1

    return sent, unmatched
