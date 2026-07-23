"""Builds and parses the Slack UI surfaces for filling in a week:

1. build_quickfill_message -- "Same as last week" / "Fill in week" buttons.
   Posted as the body of the daily unfilled-week reminder DM, which can't open a
   modal directly (no fresh trigger_id in a DM) so it needs a button first.
   /log-week itself skips straight to the modal (see slack_routes.py) since a
   slash command already has a fresh trigger_id.
2. build_week_modal / parse_week_submission -- the day-by-day entry form.
   Full-day only, per the confirmed scope -- no morning/afternoon split support.
   The per-day client/description field only appears once that day's location is
   set to Client Office/Other (dispatch_action + views.update, driven from
   slack_routes.py's dispatch handler) -- _build_day_blocks is the single source
   of truth for that rendering rule, used both on initial open and on every
   live update, so the two can't drift apart.
3. format_week_summary -- shown privately to whoever just finished submitting,
   so they can see where the rest of the team is that week without switching
   to the web app.
"""
import json
from datetime import datetime, timedelta

from pydantic import ValidationError

from schemas import EntryCreate

VALID_LOCATIONS = ["Neal Street", "WFH", "Client Office", "Holiday", "Working From Abroad", "Other"]
CLIENT_TEXT_LOCATIONS = ("Client Office", "Other")

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

LOCATION_ACTION_ID = "location"

ACTION_SAME_AS_LAST_WEEK = "quickfill_same_as_last_week"
ACTION_FILL_WEEK = "quickfill_fill_week"

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
        note = "\n_Note: last week included a split (half) day, so \"Same as last week\" will skip that day -- use Fill in week for it._"

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
                    "text": {"type": "plain_text", "text": "🔁 Same as last week", "emoji": True},
                    "action_id": ACTION_SAME_AS_LAST_WEEK,
                    "value": week_start,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Fill in week", "emoji": True},
                    "action_id": ACTION_FILL_WEEK,
                    "value": week_start,
                },
            ],
        },
    ]
    return {"text": f"Fill in your week of {_day_label(week_start, 0)}", "blocks": blocks}


def _build_day_blocks(week_start: str, day_state: dict) -> list:
    """day_state: {offset: {"location": str|None, "text": str|None}}. The client/
    description block for a day is only included when that day's location is
    Client Office/Other -- this one function is the single source of truth for
    that rule, used both when the modal first opens and every time it's
    live-updated, so rendering can't drift from what parse_week_submission expects."""
    blocks = []
    for offset in range(5):
        state = day_state.get(offset, {})
        location = state.get("location")

        location_block = {
            "type": "input",
            "block_id": f"day_{offset}",
            "optional": True,
            "dispatch_action": True,
            "label": {"type": "plain_text", "text": _day_label(week_start, offset)},
            "element": {
                "type": "static_select",
                "action_id": LOCATION_ACTION_ID,
                "options": [
                    {"text": {"type": "plain_text", "text": loc}, "value": loc}
                    for loc in VALID_LOCATIONS
                ],
            },
        }
        if location:
            location_block["element"]["initial_option"] = {
                "text": {"type": "plain_text", "text": location},
                "value": location,
            }
        blocks.append(location_block)

        if location in CLIENT_TEXT_LOCATIONS:
            text_block = {
                "type": "input",
                "block_id": f"client_{offset}",
                "optional": True,
                "label": {"type": "plain_text", "text": "Client / description"},
                "element": {"type": "plain_text_input", "action_id": "text"},
            }
            if state.get("text"):
                text_block["element"]["initial_value"] = state["text"]
            blocks.append(text_block)

    return blocks


def extract_day_state(values: dict) -> dict:
    """Reads the modal's current full state (all 5 days) out of a view's
    state.values -- used both to rebuild blocks on a live location change and to
    parse the final submission, so both paths agree on what's "currently set"."""
    day_state = {}
    for offset in range(5):
        location_field = values.get(f"day_{offset}", {}).get(LOCATION_ACTION_ID, {})
        selected = location_field.get("selected_option")
        location = selected["value"] if selected else None

        # The client_N block simply won't be in values if it isn't currently
        # rendered (e.g. the day isn't Client Office/Other) -- .get(...) handles
        # that as "no text", which is the correct behavior either way.
        text_field = values.get(f"client_{offset}", {}).get("text", {})
        text = text_field.get("value")

        day_state[offset] = {"location": location, "text": text}
    return day_state


def build_week_modal(week_start: str, user_name: str, prefill: dict | None = None) -> dict:
    """prefill: {offset: {"location": str, "text": str}} for pre-filling from existing entries."""
    return {
        "type": "modal",
        "callback_id": CALLBACK_ID_WEEK_MODAL,
        "private_metadata": json.dumps({"week_start": week_start, "user_name": user_name}),
        "title": {"type": "plain_text", "text": "Log your week"},
        "submit": {"type": "plain_text", "text": "Save Week"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": _build_day_blocks(week_start, prefill or {}),
    }


def rebuild_modal_view(week_start: str, user_name: str, day_state: dict) -> dict:
    """Same view shape as build_week_modal, but built from the modal's own live
    state (day_state from extract_day_state) rather than DB prefill -- used when
    responding to a location-select change with views.update."""
    return build_week_modal(week_start, user_name, prefill=day_state)


def parse_week_submission(view: dict) -> tuple[list[EntryCreate], dict]:
    """Returns (entries, errors). If errors is non-empty, caller must return a
    Slack response_action:errors payload and must NOT touch the database."""
    metadata = json.loads(view["private_metadata"])
    week_start = metadata["week_start"]
    day_state = extract_day_state(view["state"]["values"])

    entries: list[EntryCreate] = []
    errors: dict[str, str] = {}

    for offset in range(5):
        state = day_state[offset]
        location = state["location"]
        if not location:
            continue  # day left blank -- no entry for this day

        text_value = (state["text"] or "").strip() or None

        # The single per-day text field means either "client" (required for
        # Client Office/Other) or free-form "notes" -- matches the web app's own
        # conditional routing (frontend/src/App.tsx:1012-1015).
        entry_kwargs = {"date": _day_date(week_start, offset), "location": location}
        if location in CLIENT_TEXT_LOCATIONS:
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


def format_week_summary(week_entries: list, week_start: str) -> str:
    """Text summary of the whole team's week, grouped by day then location --
    mirrors the dashboard style documented in docs/CHANGELOG.md
    ("[Neal Street] - John, Alice, Bob")."""
    by_date: dict[str, dict[str, list[str]]] = {}
    for row in week_entries:
        by_date.setdefault(row.date, {}).setdefault(row.location, []).append(row.user_name)

    sections = [f"*Who's where this week ({_day_label(week_start, 0)}):*"]
    for offset in range(5):
        date_str = _day_date(week_start, offset)
        locations = by_date.get(date_str, {})
        day_lines = [f"*{WEEKDAY_NAMES[offset]}*"]
        if not locations:
            day_lines.append("  _No entries yet_")
        else:
            for loc in VALID_LOCATIONS:
                names = locations.get(loc)
                if names:
                    day_lines.append(f"  {loc} - {', '.join(sorted(set(names)))}")
        sections.append("\n".join(day_lines))

    return "\n\n".join(sections)
