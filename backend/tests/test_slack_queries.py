"""DB-integration tests for the Slack-specific query helper in queries.py."""
import pytest
from sqlmodel import Session, select

import queries
from app import app
from db import create_db_and_tables, engine, get_session
from entries import upsert_entries
from models import Entry


@pytest.fixture(scope="function")
def test_session():
    create_db_and_tables()
    with Session(engine) as session:
        yield session
        all_entries = session.exec(select(Entry)).all()
        for entry in all_entries:
            session.delete(entry)
        session.commit()


def test_get_last_week_entries_for_user_full_days(test_session):
    from schemas import EntryCreate

    # Last week: Mon Neal Street, Wed WFH. This week starts 2026-08-03 (Monday).
    last_week_start = "2026-07-27"
    upsert_entries(test_session, "Alice Johnson", [
        EntryCreate(date="2026-07-27", location="Neal Street"),
        EntryCreate(date="2026-07-29", location="WFH"),
    ])

    result = queries.get_last_week_entries_for_user(test_session, "alice johnson", "2026-08-03")

    assert result[0]["full"].location == "Neal Street"
    assert result[0]["morning"] is None
    assert result[2]["full"].location == "WFH"
    assert 1 not in result  # Tuesday had no entry


def test_get_last_week_entries_for_user_skips_split_days(test_session):
    """A split (morning/afternoon) day should show up under morning/afternoon,
    not full -- callers (the Slack quick-fill) are expected to skip these."""
    from schemas import EntryCreate

    upsert_entries(test_session, "Bob Smith", [
        EntryCreate(date="2026-07-27", time_period="Morning", location="Neal Street"),
        EntryCreate(date="2026-07-27", time_period="Afternoon", location="WFH"),
    ])

    result = queries.get_last_week_entries_for_user(test_session, "bob smith", "2026-08-03")

    assert result[0]["full"] is None
    assert result[0]["morning"].location == "Neal Street"
    assert result[0]["afternoon"].location == "WFH"
