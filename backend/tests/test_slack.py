"""Unit tests for the Slack integration's non-DB-dependent logic:
signature verification, directory matching, modal submission parsing, and the
DST-safe scheduling gate. Deliberately doesn't hit the real Slack API or a
running Slack workspace -- those paths are covered by manual verification
(see the plan's Verification section).
"""
import hashlib
import hmac
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import daily_notifications
import slack_client
import slack_directory
import slack_views


# --- slack_client.verify_signature -----------------------------------------
# verify_signature implements Slack's documented v0:{timestamp}:{body} HMAC-SHA256
# scheme (https://api.slack.com/authentication/verifying-requests-from-slack).
# These tests compute the expected signature independently (same documented
# formula, separate code path from the implementation under test) rather than
# relying on a hand-transcribed "official" example that can't be verified offline.

def _sign(secret: str, timestamp: str, body: bytes) -> str:
    base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
    return "v0=" + hmac.new(secret.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha256).hexdigest()


def test_verify_signature_valid(monkeypatch):
    signing_secret = "8f742231b10e8888abcd99yyyzzz85a5"
    timestamp = "1531420618"
    body = b"token=xyzz0WbapA4vBCDEFasx0q6G&team_id=T1DC2JH3J&command=%2Fwebhook-collect"
    signature = _sign(signing_secret, timestamp, body)

    # Freeze "now" right next to the timestamp so the replay-protection age
    # check doesn't reject an otherwise-valid signature.
    monkeypatch.setattr(slack_client.time, "time", lambda: 1531420618 + 1)

    assert slack_client.verify_signature(timestamp, body, signature, signing_secret) is True


def test_verify_signature_tampered_body(monkeypatch):
    signing_secret = "8f742231b10e8888abcd99yyyzzz85a5"
    timestamp = "1531420618"
    body = b"token=xyzz0WbapA4vBCDEFasx0q6G"
    signature = _sign(signing_secret, timestamp, body)

    monkeypatch.setattr(slack_client.time, "time", lambda: 1531420618 + 1)

    tampered_body = b"token=something-else-entirely"
    assert slack_client.verify_signature(timestamp, tampered_body, signature, signing_secret) is False


def test_verify_signature_expired_timestamp():
    """A signature computed correctly for a very old timestamp should still be
    rejected -- the freshness check runs regardless of HMAC correctness."""
    signing_secret = "8f742231b10e8888abcd99yyyzzz85a5"
    timestamp = "1531420618"  # real "now" is years past this -- no monkeypatch here
    body = b"token=xyzz0WbapA4vBCDEFasx0q6G"
    signature = _sign(signing_secret, timestamp, body)

    assert slack_client.verify_signature(timestamp, body, signature, signing_secret) is False


# --- slack_directory.match_roster --------------------------------------------

def test_match_roster_exact_and_variance_and_unmatched():
    directory = {
        "alice johnson": {"id": "U001", "real_name": "Alice Johnson"},
        "bob smith": {"id": "U002", "real_name": "Bob Smith"},
    }
    roster_names = ["Alice Johnson", "  Bob Smith  ", "Ghost Person"]

    matched, unmatched = slack_directory.match_roster(roster_names, directory)

    assert matched == {"Alice Johnson": "U001", "  Bob Smith  ": "U002"}
    assert unmatched == ["Ghost Person"]


# --- slack_views.parse_week_submission ---------------------------------------

def _view_with(day_values: dict, week_start="2026-07-27", user_name="Test User") -> dict:
    """Build a minimal view_submission-shaped payload. day_values: {offset: (location, text)}."""
    values = {}
    for offset in range(5):
        loc, text = day_values.get(offset, (None, None))
        values[f"day_{offset}"] = {
            "location": {"selected_option": {"value": loc} if loc else None}
        }
        values[f"client_{offset}"] = {"text": {"value": text}}
    return {
        "private_metadata": json.dumps({"week_start": week_start, "user_name": user_name}),
        "state": {"values": values},
    }


def test_parse_week_submission_all_days_filled():
    view = _view_with({
        0: ("Neal Street", None),
        1: ("WFH", None),
        2: ("Client Office", "Acme Corp"),
        3: ("Holiday", None),
        4: ("Other", "Conference"),
    })
    entries, errors = slack_views.parse_week_submission(view)

    assert errors == {}
    assert len(entries) == 5
    assert entries[0].date == "2026-07-27" and entries[0].location == "Neal Street"
    assert entries[2].location == "Client Office" and entries[2].client == "Acme Corp"
    assert entries[4].location == "Other" and entries[4].client == "Conference"


def test_parse_week_submission_some_days_blank():
    view = _view_with({0: ("Neal Street", None), 2: ("WFH", None)})
    entries, errors = slack_views.parse_week_submission(view)

    assert errors == {}
    assert len(entries) == 2
    assert {e.date for e in entries} == {"2026-07-27", "2026-07-29"}


def test_parse_week_submission_client_office_blank_client_errors():
    view = _view_with({0: ("Client Office", None)})
    entries, errors = slack_views.parse_week_submission(view)

    assert entries == []
    assert "client_0" in errors


def test_parse_week_submission_notes_routing_for_non_client_location():
    """A non-Client-Office/Other day's text field should map to notes, not client."""
    view = _view_with({0: ("WFH", "working from the kitchen table")})
    entries, errors = slack_views.parse_week_submission(view)

    assert errors == {}
    assert entries[0].client is None
    assert entries[0].notes == "working from the kitchen table"


# --- daily_notifications DST-safe hour/weekday gate --------------------------

class _FixedDatetime(datetime):
    """A datetime subclass whose .now() always returns a fixed instant, so the
    gate logic can be tested without depending on the real wall clock."""
    _fixed = None

    @classmethod
    def now(cls, tz=None):
        return cls._fixed


def _run_with_fixed_now(monkeypatch, fixed_dt):
    fixed = _FixedDatetime(
        fixed_dt.year, fixed_dt.month, fixed_dt.day,
        fixed_dt.hour, fixed_dt.minute, tzinfo=fixed_dt.tzinfo,
    )
    _FixedDatetime._fixed = fixed
    monkeypatch.setattr(daily_notifications, "datetime", _FixedDatetime)
    return daily_notifications.run_daily_notifications(session=None)


def test_gate_skips_weekend(monkeypatch):
    saturday_9am = datetime(2026, 7, 25, 9, 0, tzinfo=ZoneInfo("Europe/London"))  # a Saturday
    result = _run_with_fixed_now(monkeypatch, saturday_9am)
    assert result == {"ok": True, "skipped": "weekend"}


def test_gate_skips_off_hour(monkeypatch):
    tuesday_2pm = datetime(2026, 7, 28, 14, 0, tzinfo=ZoneInfo("Europe/London"))
    result = _run_with_fixed_now(monkeypatch, tuesday_2pm)
    assert result["skipped"] == "not target hour"
    assert result["hour"] == 14


def test_gate_matches_target_hour_across_dst(monkeypatch):
    """Both a BST morning and a GMT-era morning at the configured target hour
    should pass the gate (not be skipped) -- this is the whole point of firing
    the GitHub Actions cron at both UTC 08:00 and 09:00."""
    for tz_date in [
        datetime(2026, 7, 28, 9, 0, tzinfo=ZoneInfo("Europe/London")),   # BST (summer)
        datetime(2026, 1, 27, 9, 0, tzinfo=ZoneInfo("Europe/London")),  # GMT (winter)
    ]:
        monkeypatch.setattr(daily_notifications.roster, "get_roster", lambda: [])
        fixed = _FixedDatetime(
            tz_date.year, tz_date.month, tz_date.day, tz_date.hour, tz_date.minute, tzinfo=tz_date.tzinfo
        )
        _FixedDatetime._fixed = fixed
        monkeypatch.setattr(daily_notifications, "datetime", _FixedDatetime)

        # SLACK_GENERAL_CHANNEL_ID unset in test env -> digest step no-ops safely,
        # roster empty -> reminder step no-ops safely. We're only asserting the
        # gate itself didn't short-circuit with a "skipped" result.
        class _FakeSession:
            pass

        monkeypatch.setattr(daily_notifications.queries, "get_week_entries", lambda session, week_start: [])
        monkeypatch.setattr(daily_notifications.queries, "get_submitted_users", lambda session, week_start: [])

        result = daily_notifications.run_daily_notifications(_FakeSession())
        assert "skipped" not in result
        assert result["ok"] is True
