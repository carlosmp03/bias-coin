from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()

def valid_hhmm(value: str) -> bool:
    try:
        parse_hhmm(value)
        return True
    except ValueError:
        return False

def get_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")

def local_now(tz_name: str) -> datetime:
    return utc_now().astimezone(get_zone(tz_name))

def is_after_hhmm(now_local: datetime, hhmm: str) -> bool:
    return now_local.time().replace(tzinfo=None) >= parse_hhmm(hhmm)

def is_quiet_time(now_local: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    start = parse_hhmm(start_hhmm)
    end = parse_hhmm(end_hhmm)
    current = now_local.time().replace(tzinfo=None)
    if start < end:
        return start <= current < end
    return current >= start or current < end

def format_minutes(total: int) -> str:
    h, m = divmod(total, 60)
    if h and m:
        return f"{h} ч {m} мин"
    if h:
        return f"{h} ч"
    return f"{m} мин"
