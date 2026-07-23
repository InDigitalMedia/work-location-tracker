"""Builds and parses the two Slack UI surfaces for filling in a week:

1. build_quickfill_message -- the primary, low-friction UX: 4 buttons
   ("All Neal Street" / "All WFH" / "Same as last week" / "Customize...").
   Posted both as the /log-week slash command's response and as the body of the
   daily unfilled-week reminder DM -- the reminder *is* the fill-in prompt.
2. build_week_modal / parse_week_submission -- the "Customize" fallback for
   anything the quick buttons can't express (mixed days, Client Office/Other,
   or a week that had a split day last week). Full-day only, per the confirmed
   scope -- no morning/afternoon split support here.
"""
import json
from datetime import datetime, timedelta

from pydantic import ValidationError

from schemas import EntryCreate

VALID_LOCATIONS = ["Neal Street", "WFH", "Client Office", "Holiday", "Working From Abroad", "Other"]

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

ACTION_ALL_NEAL_STREET = "quickfill_all_neal_street"
ACTION_ALL_WFH = "quickfill_all_wfh"
ACTION_SAME_AS_LAST_WEEK = "quickfill_same_as_last_week"
ACTION_CUSTOMIZE = "quickfill_customize"

CALLBACK_ID_WEEK_MODAL = "log_week_modal"


def _day_date(week_start: str, offset: int) -> str:
    start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    return (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")


def _day_label(week_start: str, offset: int) -> str:
    date_str = _day_date(week_start, offset)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{WEEKDAY_NAMES[offset]} {date_obj.day} {date_obj.strftime('%b')}"


def build_quickfill_message(week_start: str, has_split_last_week: bool = False) -> dict:
    """Block Kit message body (blocks + fallback text) for the quick-fill prompt."""
    note = ""
    if has_split_last_week:
        note = "\n_Note: last week included a split (half) day, so \"Same as last week\" will skip that day -- use Customize for it._"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Fill in your week of {_day_label(week_start, 0)}*{note}",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🏢 All Neal Street", "emoji": True},
                    "action_id": ACTION_ALL_NEAL_STREET,
                    "value": week_start,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🏠 All WFH", "emoji": True},
                    "action_id": ACTION_ALL_WFH,
                    "value": week_start,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔁 Same as last week", "emoji": True},
                    "action_id": ACTION_SAME_AS_LAST_WEEK,
                    "value": week_start,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Customize...", "emoji": True},
                    "action_id": ACTION_CUSTOMIZE,
                    "value": week_start,
                },
            ],
        },
    ]
    return {"text": f"Fill in your week of {_day_label(week_start, 0)}", "blocks": blocks}


def build_week_modal(week_start: str, user_name: str, prefill: dict | None = None) -> dict:
    """prefill: {offset: {"location": str, "text": str}} for pre-filling from existing entries."""
    prefill = prefill or {}
    blocks = []
    for offset in range(5):
        day_prefill = prefill.get(offset, {})
        location_block = {
            "type": "input",
            "block_id": f"day_{offset}",
            "optional": True,
            "label": {"type": "plain_text", "text": _day_label(week_start, offset)},
            "element": {
                "type": "static_select",
                "action_id": "location",
                "options": [
                    {"text": {"type": "plain_text", "text": loc}, "value": loc}
                    for loc in VALID_LOCATIONS
                ],
            },
        }
        if day_prefill.get("location"):
            location_block["element"]["initial_option"] = {
                "text": {"type": "plain_text", "text": day_prefill["location"]},
                "value": day_prefill["location"],
            }
        blocks.append(location_block)

        text_block = {
            "type": "input",
            "block_id": f"client_{offset}",
            "optional": True,
            "label": {"type": "plain_text", "text": "Client / notes (optional)"},
            "element": {"type": "plain_text_input", "action_id": "text"},
        }
        if day_prefill.get("text"):
            text_block["element"]["initial_value"] = day_prefill["text"]
        blocks.append(text_block)

    return {
        "type": "modal",
        "callback_id": CALLBACK_ID_WEEK_MODAL,
        "private_metadata": json.dumps({"week_start": week_start, "user_name": user_name}),
        "title": {"type": "plain_text", "text": "Log your week"},
        "submit": {"type": "plain_text", "text": "Save Week"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def parse_week_submission(view: dict) -> tuple[list[EntryCreate], dict]:
    """Returns (entries, errors). If errors is non-empty, caller must return a
    Slack response_action:errors payload and must NOT touch the database."""
    metadata = json.loads(view["private_metadata"])
    week_start = metadata["week_start"]
    values = view["state"]["values"]

    entries: list[EntryCreate] = []
    errors: dict[str, str] = {}

    for offset in range(5):
        location_field = values.get(f"day_{offset}", {}).get("location", {})
        selected = location_field.get("selected_option")
        if not selected:
            continue  # day left blank -- no entry for this day

        location = selected["value"]
        text_field = values.get(f"client_{offset}", {}).get("text", {})
        text_value = (text_field.get("value") or "").strip() or None

        # The single per-day text field means either "client" (required for
        # Client Office/Other) or free-form "notes" -- matches the web app's own
        # conditional routing (frontend/src/App.tsx:1012-1015).
        entry_kwargs = {"date": _day_date(week_start, offset), "location": location}
        if location in ("Client Office", "Other"):
            entry_kwargs["client"] = text_value
        else:
            entry_kwargs["notes"] = text_value

        try:
            entries.append(EntryCreate(**entry_kwargs))
        except ValidationError:
            # Client Office/Other require a client name -- EntryCreate's own
            # validator raises for that, but this offers Slack a friendlier,
            # field-anchored inline error instead of a generic one.
            errors[f"client_{offset}"] = "Client name/description is required for this location"

    return entries, errors
