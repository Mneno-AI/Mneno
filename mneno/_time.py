"""Instant comparisons: legacy naive timestamps mean UTC; stored values stay unchanged."""

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    try:
        return value.astimezone(UTC)
    except OverflowError:
        # UTC may lie outside datetime's year range; aware comparison still compares the correct instant.
        return value
