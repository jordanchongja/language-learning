"""
Local-date helper. All "today" logic (due cards, SRS scheduling,
study logs) goes through here so it uses one consistent timezone
instead of mixing SQLite's UTC `date('now')` with the server clock.
"""
from datetime import date, datetime, timedelta, timezone

import config


def local_today() -> date:
    """Today's date in the configured UTC offset."""
    return (datetime.now(timezone.utc) + timedelta(hours=config.UTC_OFFSET_HOURS)).date()
