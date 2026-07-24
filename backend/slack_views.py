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
3. build_neal_street_week_message -- shown privately to whoever just finished
   submitting, Officely-style: each day clearly separated, Neal Street only,
   with a link back to the full tracker.
"""
import json
import os
from datetime import datetime, timedelta

from pydantic import ValidationError

import clients
from schemas import EntryCreate

VALID_LOCATIONS = ["Neal Street", "WFH", "Client Office", "Holiday", "Working From Abroad", "Other"]
CLIENT_TEXT_LOCATIONS = ("Client Office", "Other")

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# The week modal only ever covers Mon-Fri (offsets 0-4), but the single-day
# today/tomorrow digests index by date_obj.weekday() directly -- Saturday(5)/
# Sunday(6) are reachable there when force=True bypasses the weekend gate (e.g.
# manually forcing "tomorrow" on a Friday), so this list must cover all 7 days
# to avoid an IndexError -> 500.

LOCATION_ACTION_ID = "location"
CLIENT_SELECT_ACTION_ID = "client_select"
# Sentinel dropdown value for "not in the list, let me type it" -- deliberately
# not a real client name so it can never collide with an actual clients.json entry.
CUSTOM_CLIENT_VALUE = "__custom__"

ACTION_SAME_AS_LAST_WEEK = "quickfill_same_as_last_week"
ACTION_FILL_WEEK = "quickfill_fill_week"

CALLBACK_ID_WEEK_MODAL = "log_week_modal"

# Any block_id whose value changing should trigger a live modal re-render.
DISPATCH_ACTION_IDS = (LOCATION_ACTION_ID, CLIENT_SELECT_ACTION_ID)


def _day_date(week_start: str, offset: int) -> str:
    start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    return (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")


def _day_label(week_start: str, offset: int) -> str:
    date_str = _day_date(week_start, offset)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{WEEKDAY_NAMES[offset]} {date_obj.day} {date_obj.strftime('%b')}"


def _sub_label(week_start: str, offset: int, field_name: str) -> str:
    """Label for a field nested under a specific day's location select. Slack's
    Block Kit gives every input block's label the same fixed bold styling --
    there's no way to actually indent/de-emphasize one relative to another --
    so the day association has to be carried in the text itself. The "↳" plus
    a short day reference is the closest approximation of "this is a sub-field
    of the row above" that plain-text labels can convey."""
    date_str = _day_date(week_start, offset)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    short_day = f"{WEEKDAY_NAMES[offset][:3]} {date_obj.day}"
    return f"↳ {field_name} ({short_day})"


def build_quickfill_message(
    week_start: str, has_split_last_week: bool = False, header_text: str | None = None, mention: str | None = None
) -> dict:
    """Block Kit message body (blocks + fallback text) for the quick-fill prompt.
    header_text lets callers reuse this for other weeks (e.g. the Friday next-week
    reminder) with wording appropriate to that context; defaults to the standard
    "fill in your week" prompt used by the same-week daily reminder. mention is a
    ready-made Slack mention string (e.g. "<@U123>") for the recipient, prefixed
    onto the header so it's clear who's being asked even if the DM is forwarded
    or screenshotted."""
    header_text = header_text or "Don't forget to fill in your week!"
    if mention:
        header_text = f"Hey {mention} — {header_text}"
    note = ""
    if has_split_last_week:
        note = "\n_Note: last week included a split (half) day, so \"Same as last week\" will skip that day -- use Fill in week for it._"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{header_text}*{note}",
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
    return {"text": header_text, "blocks": blocks}


def _build_day_blocks(week_start: str, day_state: dict) -> list:
    """day_state: {offset: {"location": str|None, "client_choice": str|None, "text": str|None}}.

    - "Other" location: a plain free-text description block (client_{offset}).
    - "Client Office" location: a dropdown of clients.json entries plus an
      "Other (type below)" option (client_select_{offset}); choosing that reveals
      a further custom-name text block (client_custom_{offset}).
    - Anything else: no client-related block at all.

    This one function is the single source of truth for which blocks exist given
    the current state, used both when the modal first opens and every time it's
    live-updated, so rendering can't drift from what parse_week_submission expects."""
    blocks = []
    for offset in range(5):
        state = day_state.get(offset, {})
        location = state.get("location")

        location_block = {
            "type": "input",
            "block_id": f"day_{offset}",
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

        if location == "Client Office":
            client_choice = state.get("client_choice")
            options = [
                {"text": {"type": "plain_text", "text": name}, "value": name}
                for name in clients.get_clients()
            ] + [{"text": {"type": "plain_text", "text": "Other (type below)"}, "value": CUSTOM_CLIENT_VALUE}]
            select_block = {
                "type": "input",
                "block_id": f"client_select_{offset}",
                "optional": True,
                "dispatch_action": True,
                "label": {"type": "plain_text", "text": _sub_label(week_start, offset, "Client")},
                "element": {
                    "type": "static_select",
                    "action_id": CLIENT_SELECT_ACTION_ID,
                    "options": options,
                },
            }
            if client_choice:
                label = "Other (type below)" if client_choice == CUSTOM_CLIENT_VALUE else client_choice
                select_block["element"]["initial_option"] = {
                    "text": {"type": "plain_text", "text": label},
                    "value": client_choice,
                }
            blocks.append(select_block)

            if client_choice == CUSTOM_CLIENT_VALUE:
                custom_block = {
                    "type": "input",
                    "block_id": f"client_custom_{offset}",
                    "optional": True,
                    "label": {"type": "plain_text", "text": _sub_label(week_start, offset, "Client name")},
                    "element": {"type": "plain_text_input", "action_id": "text"},
                }
                if state.get("text"):
                    custom_block["element"]["initial_value"] = state["text"]
                blocks.append(custom_block)

        elif location == "Other":
            text_block = {
                "type": "input",
                "block_id": f"client_{offset}",
                "optional": True,
                "label": {"type": "plain_text", "text": _sub_label(week_start, offset, "Description")},
                "element": {"type": "plain_text_input", "action_id": "text"},
            }
            if state.get("text"):
                text_block["element"]["initial_value"] = state["text"]
            blocks.append(text_block)

    return blocks


def extract_day_state(values: dict) -> dict:
    """Reads the modal's current full state (all 5 days) out of a view's
    state.values -- used both to rebuild blocks on a live field change and to
    parse the final submission, so both paths agree on what's "currently set".

    Each block simply won't be in values if it isn't currently rendered (e.g. a
    non-Client-Office day has no client_select_N) -- .get(...) throughout handles
    that as "not set", which is the correct behavior either way."""
    day_state = {}
    for offset in range(5):
        location_field = values.get(f"day_{offset}", {}).get(LOCATION_ACTION_ID, {})
        selected = location_field.get("selected_option")
        location = selected["value"] if selected else None

        client_choice = None
        text = None
        if location == "Client Office":
            select_field = values.get(f"client_select_{offset}", {}).get(CLIENT_SELECT_ACTION_ID, {})
            choice_selected = select_field.get("selected_option")
            client_choice = choice_selected["value"] if choice_selected else None
            if client_choice == CUSTOM_CLIENT_VALUE:
                text = values.get(f"client_custom_{offset}", {}).get("text", {}).get("value")
            else:
                text = client_choice  # a real client name picked directly from the dropdown
        elif location == "Other":
            text = values.get(f"client_{offset}", {}).get("text", {}).get("value")

        day_state[offset] = {"location": location, "client_choice": client_choice, "text": text}
    return day_state


def build_week_modal(
    week_start: str, user_name: str, prefill: dict | None = None, title: str | None = None, note: str | None = None
) -> dict:
    """prefill: {offset: {"location": str, "text": str}} for pre-filling from existing entries.
    title overrides the modal's title (Slack caps plain_text titles at 24 chars).
    note, if given, renders as a leading text block above the day fields -- used
    by "Same as last week" to flag anything that couldn't be carried over."""
    blocks = _build_day_blocks(week_start, prefill or {})
    if note:
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": note}},
            {"type": "divider"},
        ] + blocks

    return {
        "type": "modal",
        "callback_id": CALLBACK_ID_WEEK_MODAL,
        "private_metadata": json.dumps(
            {"week_start": week_start, "user_name": user_name, "title": title, "note": note}
        ),
        "title": {"type": "plain_text", "text": title or "Log your week"},
        "submit": {"type": "plain_text", "text": "Save Week"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def rebuild_modal_view(
    week_start: str, user_name: str, day_state: dict, title: str | None = None, note: str | None = None
) -> dict:
    """Same view shape as build_week_modal, but built from the modal's own live
    state (day_state from extract_day_state) rather than DB prefill -- used when
    responding to a location-select change with views.update. title/note are
    carried over from the original private_metadata so a "Same as last week"
    confirmation modal keeps its title/note across live field-change updates."""
    return build_week_modal(week_start, user_name, prefill=day_state, title=title, note=note)


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
            # field-anchored inline error instead of a generic one. Anchor it to
            # whichever block is actually currently rendered for this day, or
            # Slack will silently ignore an error pointed at a nonexistent block_id.
            if location == "Client Office":
                block_id = f"client_custom_{offset}" if state["client_choice"] == CUSTOM_CLIENT_VALUE else f"client_select_{offset}"
            else:
                block_id = f"client_{offset}"
            errors[block_id] = "Client name/description is required for this location"

    return entries, errors


TRACKER_URL = os.getenv("TRACKER_URL", "https://in-office.vercel.app")

_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}

ACTION_VIEW_FULL_SCHEDULE = "view_full_schedule"


def _ordinal_day(day: int) -> str:
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = _ORDINAL_SUFFIXES.get(day % 10, "th")
    return f"{day}{suffix}"


def _mention(name: str, directory: dict) -> str:
    """A real Slack mention (<@ID>, renders as a clickable @name pill) if this
    person's normalized name matches the Slack directory, else their plain
    display name as inert text -- still informative, just not clickable."""
    match = directory.get(name.strip().lower())
    return f"<@{match['id']}>" if match else f"@{name}"


def _format_names(names: list[str], directory: dict) -> str:
    unique_sorted = sorted(set(names))
    if not unique_sorted:
        return "_No one going_"
    return "  ".join(_mention(n, directory) for n in unique_sorted)


def build_neal_street_week_message(
    week_entries: list, week_start: str, directory: dict | None = None, header_text: str | None = None
) -> dict:
    """Officely-style summary: each day clearly separated, Neal Street only (the
    "who's in the office" question people actually ask), with a link to the full
    tracker for anyone who wants the other locations too. header_text lets
    callers reuse this for a different week (e.g. the Friday next-week digest)
    -- defaults to the standard "this week" wording used by the post-submission
    summary."""
    directory = directory or {}
    header_text = header_text or "Here's who's at Neal Street this week"
    by_date: dict[str, list[str]] = {}
    for row in week_entries:
        if row.location == "Neal Street":
            by_date.setdefault(row.date, []).append(row.user_name)

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{header_text}*"},
        },
    ]
    for offset in range(5):
        date_str = _day_date(week_start, offset)
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_header = f"{WEEKDAY_NAMES[offset][:3]} {_ordinal_day(date_obj.day)}"
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{day_header}*\n🏢 {_format_names(by_date.get(date_str, []), directory)}",
            },
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                # Slack still sends a block_actions payload to our Request URL
                # even for a "url" button -- action_id/value are set so
                # _handle_block_action can recognize and ignore it cleanly
                # instead of crashing on a missing dict key.
                "type": "button",
                "text": {"type": "plain_text", "text": "See Full Schedule"},
                "url": TRACKER_URL,
                "action_id": ACTION_VIEW_FULL_SCHEDULE,
                "value": TRACKER_URL,
            }
        ],
    })

    return {"text": header_text, "blocks": blocks}


def _build_single_day_neal_street_message(greeting: str, day_label: str, names: list[str], directory: dict | None = None) -> dict:
    """Shared shape for a single-day Neal Street heads-up (today's 9am digest,
    tomorrow's 4pm digest): greeting, divider, a day section with names on the
    line below the 🏢 marker (always real @mentions via the Slack directory
    when available), divider, "See Full Schedule" button."""
    directory = directory or {}
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": greeting}},
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{day_label}*\n🏢 {_format_names(names, directory)}",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "See Full Schedule"},
                    "url": TRACKER_URL,
                    "action_id": ACTION_VIEW_FULL_SCHEDULE,
                    "value": TRACKER_URL,
                }
            ],
        },
    ]

    return {"text": greeting, "blocks": blocks}


def build_neal_street_today_message(date_str: str, names: list[str], directory: dict | None = None) -> dict:
    """Same visual style as build_neal_street_week_message (bold header, divider,
    day section, real @mentions, "See Full Schedule" button) but for the
    single-day 9am same-day digest."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_name = WEEKDAY_NAMES[date_obj.weekday()][:3]
    day_header = f"{weekday_name} {_ordinal_day(date_obj.day)}"
    return _build_single_day_neal_street_message("*Here's who's at Neal Street today*", day_header, names, directory)


def build_neal_street_tomorrow_message(date_str: str, names: list[str], directory: dict | None = None) -> dict:
    """Same visual style as build_neal_street_week_message but for the single-day
    4pm heads-up."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_name = WEEKDAY_NAMES[date_obj.weekday()][:3]
    day_header = f"{weekday_name} {_ordinal_day(date_obj.day)}"
    greeting = ":wave: Good afternoon everyone! Here's who will be at Neal Street tomorrow :point_down:"
    return _build_single_day_neal_street_message(greeting, day_header, names, directory)
