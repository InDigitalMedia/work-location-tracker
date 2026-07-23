"""The 3 Slack-facing FastAPI routes: slash command, interactivity, scheduler trigger.

Included into app.py via app.include_router(slack_router).
"""
import json
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import parse_qsl

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session

import daily_notifications
import entries as entries_module
import queries
import roster
import slack_client
import slack_views
from db import get_session
from schemas import EntryCreate

logger = logging.getLogger(__name__)

slack_router = APIRouter()

SLACK_SCHEDULER_SECRET = os.getenv("SLACK_SCHEDULER_SECRET")


def require_scheduler(x_scheduler_secret: str | None = Header(default=None)):
    """Gate the scheduler-triggered endpoint behind its own secret, separate from
    ADMIN_SECRET, to scope blast radius (mirrors require_admin in app.py)."""
    if not SLACK_SCHEDULER_SECRET:
        raise HTTPException(status_code=503, detail="Scheduler endpoint not configured")
    if x_scheduler_secret != SLACK_SCHEDULER_SECRET:
        raise HTTPException(status_code=403, detail="Invalid scheduler secret")


async def _verify_slack_request(request: Request) -> bytes:
    """Verify the request signature and return the raw body. Raises 401 on failure."""
    raw = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not slack_client.verify_signature(timestamp, raw, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    return raw


def _resolve_identity(slack_user_id: str) -> tuple[str, bool]:
    """Returns (user_name, matched_roster). Falls back to Slack's own real_name,
    unmatched, if it doesn't correspond to a roster entry."""
    slack_user = slack_client.users_info(slack_user_id)
    profile = (slack_user or {}).get("profile", {})
    real_name = profile.get("real_name_normalized") or profile.get("real_name") or (slack_user or {}).get("name", "")

    normalized_real = real_name.strip().lower()
    for candidate in roster.get_roster():
        if candidate.strip().lower() == normalized_real:
            return candidate, True
    return real_name, False


def _build_prefill(session: Session, user_key: str, week_start: str) -> dict:
    """{offset: {"location": str, "text": str}} for this user's existing full-day
    entries this week, for pre-filling the Customize modal. Split-day entries are
    skipped (full-day-only scope)."""
    start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    prefill = {}
    for row in queries.get_week_entries(session, week_start):
        if row.user_name.strip().lower() != user_key:
            continue
        if row.time_period:
            continue  # split day -- not representable in the full-day-only modal
        row_date = datetime.strptime(row.date, "%Y-%m-%d").date()
        offset = (row_date - start_date).days
        if 0 <= offset <= 4:
            text_value = row.client if row.location in ("Client Office", "Other") else row.notes
            prefill[offset] = {"location": row.location, "text": text_value or ""}
    return prefill


@slack_router.post("/slack/commands")
async def slack_slash_command(request: Request, background_tasks: BackgroundTasks):
    raw = await _verify_slack_request(request)
    fields = dict(parse_qsl(raw.decode("utf-8")))
    user_id = fields.get("user_id", "")
    response_url = fields.get("response_url", "")

    # Slack requires the initial response within 3 seconds. Resolving identity
    # (a Slack API call) and fetching the roster (an HTTP call to Vercel) are
    # both real network round trips that can blow that budget, especially on a
    # cold Render instance -- so ack instantly here and deliver the actual
    # quick-fill buttons via response_url from a background task instead.
    background_tasks.add_task(_build_and_send_quickfill_prompt, user_id, response_url)
    return JSONResponse({"response_type": "ephemeral", "text": "One sec..."})


def _build_and_send_quickfill_prompt(user_id: str, response_url: str) -> None:
    try:
        resolved_name, matched = _resolve_identity(user_id)
        week_start = daily_notifications.monday_of(datetime.now(daily_notifications.LONDON_TZ).date())

        # A note if this person's Slack profile doesn't match anyone in team-members.json --
        # they can still use the buttons (their Slack name is used as-is), but it's worth
        # surfacing so it can get reconciled.
        mismatch_note = "" if matched else "\n_(Couldn't match your Slack name to the team roster -- using your Slack name directly.)_"

        message = slack_views.build_quickfill_message(week_start)
        message["text"] += mismatch_note
        slack_client.respond_via_response_url(response_url, message["text"], blocks=message["blocks"])
    except Exception as e:
        logger.error(f"Failed to build/send quick-fill prompt: {e}")
        slack_client.respond_via_response_url(response_url, "Something went wrong opening the form -- try again.")


@slack_router.post("/slack/interactivity")
async def slack_interactivity(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    raw = await _verify_slack_request(request)
    fields = dict(parse_qsl(raw.decode("utf-8")))
    payload = json.loads(fields["payload"])
    payload_type = payload.get("type")

    if payload_type == "block_actions":
        return _handle_block_action(session, payload)
    if payload_type == "view_submission":
        return _handle_view_submission(session, payload, background_tasks)

    # Anything else (e.g. a shortcut we haven't wired up) -- ack defensively.
    return JSONResponse({})


def _handle_block_action(session: Session, payload: dict) -> JSONResponse:
    action = payload["actions"][0]
    action_id = action["action_id"]
    week_start = action["value"]
    user_id = payload["user"]["id"]
    response_url = payload.get("response_url")
    trigger_id = payload.get("trigger_id")

    resolved_name, _matched = _resolve_identity(user_id)
    user_key = resolved_name.strip().lower()

    if action_id == slack_views.ACTION_CUSTOMIZE:
        prefill = _build_prefill(session, user_key, week_start)
        slack_client.open_view(trigger_id, slack_views.build_week_modal(week_start, resolved_name, prefill))
        return JSONResponse({})

    if action_id in (slack_views.ACTION_ALL_NEAL_STREET, slack_views.ACTION_ALL_WFH):
        location = "Neal Street" if action_id == slack_views.ACTION_ALL_NEAL_STREET else "WFH"
        entries_list = [
            EntryCreate(date=_offset_date(week_start, offset), location=location)
            for offset in range(5)
        ]
        try:
            entries_module.upsert_entries(session, resolved_name, entries_list)
            if response_url:
                slack_client.respond_via_response_url(response_url, f"✅ Set: {location}, all week")
        except ValueError as e:
            if response_url:
                slack_client.respond_via_response_url(response_url, f"❌ Couldn't save: {e}")
        return JSONResponse({})

    if action_id == slack_views.ACTION_SAME_AS_LAST_WEEK:
        last_week = queries.get_last_week_entries_for_user(session, user_key, week_start)
        entries_list = []
        skipped_split = False
        for offset, slot in last_week.items():
            if slot["morning"] or slot["afternoon"]:
                skipped_split = True
                continue
            full = slot["full"]
            if not full:
                continue
            kwargs = {"date": _offset_date(week_start, offset), "location": full.location}
            if full.location in ("Client Office", "Other"):
                kwargs["client"] = full.client
            else:
                kwargs["notes"] = full.notes
            entries_list.append(EntryCreate(**kwargs))

        if not entries_list:
            if response_url:
                slack_client.respond_via_response_url(response_url, "No matching full-day entries found last week -- try Customize instead.")
            return JSONResponse({})

        try:
            entries_module.upsert_entries(session, resolved_name, entries_list)
            note = " (a split day last week was skipped -- set it via Customize)" if skipped_split else ""
            if response_url:
                slack_client.respond_via_response_url(response_url, f"✅ Copied last week{note}")
        except ValueError as e:
            if response_url:
                slack_client.respond_via_response_url(response_url, f"❌ Couldn't save: {e}")
        return JSONResponse({})

    logger.warning(f"Unhandled block_actions action_id: {action_id}")
    return JSONResponse({})


def _offset_date(week_start: str, offset: int) -> str:
    start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    return (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")


def _handle_view_submission(session: Session, payload: dict, background_tasks: BackgroundTasks) -> JSONResponse:
    view = payload["view"]
    if view.get("callback_id") != slack_views.CALLBACK_ID_WEEK_MODAL:
        return JSONResponse({})

    entries_list, errors = slack_views.parse_week_submission(view)
    if errors:
        return JSONResponse({"response_action": "errors", "errors": errors})

    metadata = json.loads(view["private_metadata"])
    user_name = metadata["user_name"]

    try:
        entries_module.upsert_entries(session, user_name, entries_list)
    except ValueError as e:
        return JSONResponse({"response_action": "errors", "errors": {"day_0": str(e)}})

    user_id = payload["user"]["id"]
    background_tasks.add_task(_send_confirmation_dm, user_id, entries_list)
    return JSONResponse({})


def _send_confirmation_dm(user_id: str, entries_list: list) -> None:
    try:
        summary = ", ".join(f"{e.date} → {e.location}" for e in entries_list) or "no days set"
        dm_channel = slack_client.open_dm(user_id)
        if dm_channel:
            slack_client.post_message(dm_channel, f"✅ Saved: {summary}")
    except Exception as e:
        logger.error(f"Failed to send confirmation DM: {e}")


@slack_router.post("/internal/slack/daily-notifications", dependencies=[Depends(require_scheduler)])
def trigger_daily_notifications(session: Session = Depends(get_session)):
    return daily_notifications.run_daily_notifications(session)
