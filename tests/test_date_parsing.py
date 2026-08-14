import pytest
import datetime
from src.pipelines.date_parser import parse_date_deterministically

def test_exact_structured_date():
    dt = parse_date_deterministically("2024-01-01T12:00:00Z")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 1

def test_relative_hours_ago():
    dt = parse_date_deterministically("2 hours ago")
    assert dt is not None
    now = datetime.datetime.now(datetime.timezone.utc)
    diff = now - dt
    assert 1.9 <= diff.total_seconds() / 3600 <= 2.1

def test_relative_days_ago():
    dt = parse_date_deterministically("5 days ago")
    assert dt is not None
    now = datetime.datetime.now(datetime.timezone.utc)
    diff = now - dt
    assert 4.9 <= diff.total_seconds() / (3600*24) <= 5.1

def test_invalid_date():
    assert parse_date_deterministically("not a date") is None
    assert parse_date_deterministically(None) is None
