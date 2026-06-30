"""Calendar integration via ICS/iCal feed.

Works with any private .ics URL. Notion Calendar and Google Calendar
both expose one, so no OAuth dance is needed for local-first use.
Needs: CALENDAR_ICS_URL  (optional: CALENDAR_DAYS_AHEAD)
"""
from datetime import datetime, date, timedelta, time as dtime

import requests
from icalendar import Calendar as ICalendar

from .base import Integration


class CalendarIntegration(Integration):
    name = "calendar"

    def __init__(self, env, cache_ttl=300):
        super().__init__(env, cache_ttl)
        self.url = env.get("CALENDAR_ICS_URL", "").strip()
        try:
            self.days_ahead = int(env.get("CALENDAR_DAYS_AHEAD", "3"))
        except ValueError:
            self.days_ahead = 3

    def is_configured(self):
        return bool(self.url)

    def fetch_real(self):
        resp = requests.get(self.url, timeout=15)
        resp.raise_for_status()
        cal = ICalendar.from_ical(resp.content)

        now = datetime.now()
        window_end = now + timedelta(days=self.days_ahead)
        events = []

        for comp in cal.walk("VEVENT"):
            start = comp.get("dtstart")
            if start is None:
                continue
            start_val = start.dt
            all_day = not isinstance(start_val, datetime)
            start_dt = _as_datetime(start_val)

            if start_dt is None or start_dt > window_end:
                continue
            # Skip events that already ended today.
            if start_dt < now - timedelta(hours=12):
                continue

            events.append(
                {
                    "summary": str(comp.get("summary", "(no title)")),
                    "start_dt": start_dt,
                    "all_day": all_day,
                    "day_label": _day_label(start_dt.date()),
                    "time_label": "All day" if all_day else start_dt.strftime("%-I:%M %p"),
                }
            )

        events.sort(key=lambda e: e["start_dt"])
        for e in events:
            e.pop("start_dt", None)  # not JSON-friendly, drop after sort
        return {"events": events[:12], "count": len(events)}

    def mock(self):
        return {
            "events": [
                {"summary": "Add CALENDAR_ICS_URL to .env", "day_label": "Today", "time_label": "9:00 AM", "all_day": False},
                {"summary": "Coffee with a friend", "day_label": "Today", "time_label": "2:30 PM", "all_day": False},
                {"summary": "Flight home", "day_label": "Tomorrow", "time_label": "All day", "all_day": True},
            ],
            "count": 3,
        }


def _as_datetime(value):
    """Normalize date/datetime (tz-aware or naive) to a naive local datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone().replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, dtime.min)
    return None


def _day_label(d: date) -> str:
    today = date.today()
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    return d.strftime("%a %b %-d")
