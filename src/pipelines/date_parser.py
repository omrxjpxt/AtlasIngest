import re
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser

def parse_date_deterministically(date_str: str) -> datetime:
    """
    Attempts to parse a date deterministically.
    Order:
    1. Exact structured date
    2. Deterministic relative date
    Returns None if neither succeeds.
    """
    if not date_str:
        return None
        
    date_str = str(date_str).strip()
    
    # 1. Try exact structured
    try:
        if date_str.isdigit() or (date_str.replace('.', '', 1).isdigit()):
            return datetime.fromtimestamp(float(date_str), tz=timezone.utc)
        dt = date_parser.parse(date_str).astimezone(timezone.utc)
        return dt
    except Exception:
        pass
        
    # 2. Try deterministic relative date
    now = datetime.now(timezone.utc)
    date_lower = date_str.lower()
    
    hour_match = re.search(r'(\d+)\s*hour', date_lower)
    if hour_match:
        return now - timedelta(hours=int(hour_match.group(1)))
        
    minute_match = re.search(r'(\d+)\s*minute', date_lower)
    if minute_match:
        return now - timedelta(minutes=int(minute_match.group(1)))
        
    day_match = re.search(r'(\d+)\s*day', date_lower)
    if day_match:
        return now - timedelta(days=int(day_match.group(1)))
        
    if "yesterday" in date_lower:
        return now - timedelta(days=1)
        
    return None
