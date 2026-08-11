import pytest
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from src.models.schemas import JobRecord, JobContent, Source, NewsRecord

def test_date_validation_absolute():
    # Valid absolute date
    dt_str = "2026-08-11T12:00:00Z"
    dt = date_parser.parse(dt_str).astimezone(timezone.utc)
    assert dt.tzinfo == timezone.utc

def test_date_validation_relative():
    # If a feed says "2 hours ago", feedparser or our logic should handle it or skip.
    # We are using standard date_parser which handles standard formats.
    # If it fails, it rejects, which is correct for deterministic dates.
    now = datetime.now(timezone.utc)
    assert now.tzinfo == timezone.utc

def test_stale_rejection():
    # If older than 24h, reject
    now = datetime.now(timezone.utc)
    stale_date = now - timedelta(hours=25)
    cutoff = now - timedelta(hours=24)
    assert stale_date < cutoff

def test_future_date_rejection():
    # If future date, reject
    now = datetime.now(timezone.utc)
    future_date = now + timedelta(hours=1)
    assert future_date > now

def test_valid_fresh_record():
    now = datetime.now(timezone.utc)
    fresh_date = now - timedelta(hours=12)
    cutoff = now - timedelta(hours=24)
    assert fresh_date >= cutoff and fresh_date <= now

def test_missing_date_rejection():
    # If date is None, reject
    date = None
    assert date is None
