from datetime import UTC, datetime

from sqlmodel import Field, SQLModel, UniqueConstraint


class Entry(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_key", "date", "time_period", name="uniq_entries_userkey_date_timeperiod"),)
    
    id: int | None = Field(default=None, primary_key=True)
    user_key: str = Field(index=True)  # Normalized: lower(trim(user_name))
    user_name: str = Field(index=True)  # Display name (preserves casing)
    date: str = Field(index=True)  # YYYY-MM-DD format
    location: str = Field(index=True)
    time_period: str = Field(default="", index=True)  # 'Morning', 'Afternoon', or '' for full day
    client: str | None = Field(default=None)
    notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)
