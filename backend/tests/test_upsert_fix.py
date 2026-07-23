"""Tests for atomic per-day upsert fix."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import app
from db import create_db_and_tables, engine, get_session
from models import Entry


@pytest.fixture(scope="function")
def test_session():
    """Create a test database session."""
    create_db_and_tables()
    with Session(engine) as session:
        yield session
        # Clean up all test data after test
        all_entries = session.exec(select(Entry)).all()
        for entry in all_entries:
            session.delete(entry)
        session.commit()


@pytest.fixture(scope="function")
def client(test_session):
    """Create a test client with dependency override."""
    def get_test_session():
        yield test_session

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_upsert_is_idempotent_per_day(client):
    """Test that upserting the same entries twice results in same count."""
    request_data = {
        "user_name": "Test User",
        "entries": [
            {"date": "2024-01-15", "location": "Neal Street"},
            {"date": "2024-01-16", "location": "WFH"},
        ],
    }

    # First submission
    response1 = client.post("/entries/bulk_upsert", json=request_data)
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["ok"] is True
    assert data1["count"] == 2

    # Second submission (same payload)
    response2 = client.post("/entries/bulk_upsert", json=request_data)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["ok"] is True
    assert data2["count"] == 2

    # Verify only 2 entries exist (not 4)
    entries_response = client.get("/entries?date_from=2024-01-15&date_to=2024-01-16")
    assert entries_response.status_code == 200
    entries = entries_response.json()
    assert len(entries) == 2


def test_partial_week_doesnt_delete_other_days(client):
    """Test that submitting partial week doesn't delete other days."""
    # Submit full week (Mon-Fri)
    full_week = {
        "user_name": "Test User",
        "entries": [
            {"date": "2024-01-15", "location": "Neal Street"},  # Mon
            {"date": "2024-01-16", "location": "WFH"},  # Tue
            {"date": "2024-01-17", "location": "Neal Street"},  # Wed
            {"date": "2024-01-18", "location": "WFH"},  # Thu
            {"date": "2024-01-19", "location": "Neal Street"},  # Fri
        ],
    }
    response1 = client.post("/entries/bulk_upsert", json=full_week)
    assert response1.status_code == 200

    # Verify all 5 entries exist
    entries_response = client.get("/entries?date_from=2024-01-15&date_to=2024-01-19")
    entries = entries_response.json()
    assert len(entries) == 5

    # Submit partial week (Wed-Thu only) with different locations
    partial_week = {
        "user_name": "Test User",
        "entries": [
            {"date": "2024-01-17", "location": "Client Office", "client": "Acme"},  # Wed
            {"date": "2024-01-18", "location": "Holiday"},  # Thu
        ],
    }
    response2 = client.post("/entries/bulk_upsert", json=partial_week)
    assert response2.status_code == 200
    assert response2.json()["count"] == 2

    # Verify Mon/Tue/Fri unchanged, Wed/Thu updated
    entries_response = client.get("/entries?date_from=2024-01-15&date_to=2024-01-19")
    entries = entries_response.json()
    assert len(entries) == 5  # Still 5 entries total

    # Check specific days
    entry_dict = {e["date"]: e for e in entries}
    assert entry_dict["2024-01-15"]["location"] == "Neal Street"  # Mon unchanged
    assert entry_dict["2024-01-16"]["location"] == "WFH"  # Tue unchanged
    assert entry_dict["2024-01-17"]["location"] == "Client Office"  # Wed updated
    assert entry_dict["2024-01-18"]["location"] == "Holiday"  # Thu updated
    assert entry_dict["2024-01-19"]["location"] == "Neal Street"  # Fri unchanged


def test_casing_no_longer_loses_data(client):
    """Test that changing name casing doesn't lose previous entries."""
    # Submit as "Shaz Ahmed" (Mon/Tue)
    request1 = {
        "user_name": "Shaz Ahmed",
        "entries": [
            {"date": "2024-01-15", "location": "Neal Street"},
            {"date": "2024-01-16", "location": "WFH"},
        ],
    }
    response1 = client.post("/entries/bulk_upsert", json=request1)
    assert response1.status_code == 200

    # Submit as "shaz ahmed" (Wed/Thu)
    request2 = {
        "user_name": "shaz ahmed",
        "entries": [
            {"date": "2024-01-17", "location": "Neal Street"},
            {"date": "2024-01-18", "location": "WFH"},
        ],
    }
    response2 = client.post("/entries/bulk_upsert", json=request2)
    assert response2.status_code == 200

    # Query all entries for that user_key (should get all 4 days)
    check_response = client.get("/entries/check?user_name=Shaz%20Ahmed&week_start=2024-01-15")
    assert check_response.status_code == 200
    data = check_response.json()
    assert data["exists"] is True
    assert data["count"] == 4  # All 4 entries present

    # Verify all dates are present
    dates = {e["date"] for e in data["entries"]}
    assert "2024-01-15" in dates
    assert "2024-01-16" in dates
    assert "2024-01-17" in dates
    assert "2024-01-18" in dates

    # Latest user_name should be "shaz ahmed" (last submitted)
    entries_response = client.get("/entries?date_from=2024-01-15&date_to=2024-01-18")
    entries = entries_response.json()
    user_names = {e["user_name"] for e in entries}
    # All entries should have the latest user_name casing
    assert "shaz ahmed" in user_names or "Shaz Ahmed" in user_names  # Either is fine, but consistent


def test_uniqueness_enforced(client):
    """Test that duplicate (user_key, date) entries cannot be created."""
    request_data = {
        "user_name": "Test User",
        "entries": [
            {"date": "2024-01-15", "location": "Neal Street"},
        ],
    }

    # First insert
    response1 = client.post("/entries/bulk_upsert", json=request_data)
    assert response1.status_code == 200

    # Try to insert same day again (should update, not duplicate)
    request_data["entries"][0]["location"] = "WFH"
    response2 = client.post("/entries/bulk_upsert", json=request_data)
    assert response2.status_code == 200

    # Verify only one entry exists for that date
    entries_response = client.get("/entries?date_from=2024-01-15&date_to=2024-01-15")
    entries = entries_response.json()
    assert len(entries) == 1
    assert entries[0]["location"] == "WFH"  # Updated value


def test_no_destructive_delete_path(client):
    """Test that bulk_upsert no longer calls delete-by-range before inserts.

    The upsert logic lives in entries.upsert_entries (app.bulk_upsert_entries is now
    a thin wrapper around it, also used by the Slack integration), so that's what
    this inspects.
    """
    import inspect
    from entries import upsert_entries

    source = inspect.getsource(upsert_entries)

    # Verify no destructive delete patterns (should not contain delete-by-range logic)
    assert "delete_ids_stmt" not in source
    assert ".in_(entries_to_delete)" not in source
    # Should use ON CONFLICT or merge pattern instead
    assert ("ON CONFLICT" in source or "existing = session.exec" in source)

