import hashlib
import time as time_module
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from reply_config import (
    CALENDAR_SEARCH_DAYS,
    CALENDAR_SLOT_MINUTES,
    CALENDAR_TIMEZONE,
    GOOGLE_CALENDAR_ID,
    GOOGLE_OAUTH_TOKEN_FILE,
)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]

PKT = ZoneInfo(CALENDAR_TIMEZONE)


def execute_calendar_request(
    request_factory,
    operation_name: str,
    on_conflict=None,
):
    """
    Executes a Google Calendar API request with retries.

    This protects against temporary network/API timeouts.
    """
    last_error = None

    for attempt in range(1, 4):
        try:
            print(
                f"[Calendar] {operation_name} "
                f"attempt {attempt}/3"
            )

            return request_factory().execute(num_retries=2)

        except HttpError as exc:
            if exc.resp.status == 409 and on_conflict is not None:
                print(
                    f"[Calendar] {operation_name} already exists. "
                    "Loading the existing event."
                )
                return on_conflict()

            last_error = exc

        except Exception as exc:
            last_error = exc

        print(
            f"[Calendar] {operation_name} failed on "
            f"attempt {attempt}/3: {last_error}"
        )

        if attempt < 3:
            time_module.sleep(2 ** attempt)

    raise RuntimeError(
        f"Calendar operation failed after retries: "
        f"{operation_name}. Error: {last_error}"
    )


def build_stable_event_id(reply_id: str) -> str:
    """
    Creates one stable Calendar event ID per reply.

    This prevents duplicate meetings when the same reply is retried.
    """
    digest = hashlib.sha1(
        str(reply_id).encode("utf-8")
    ).hexdigest()[:24]

    return f"evt{digest}"


def get_google_calendar_service():
    if not GOOGLE_OAUTH_TOKEN_FILE.exists():
        raise RuntimeError(
            "Google Calendar is not authorized. "
            "Run: python authorize_google_calendar.py"
        )

    credentials = Credentials.from_authorized_user_file(
        str(GOOGLE_OAUTH_TOKEN_FILE),
        SCOPES,
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

        GOOGLE_OAUTH_TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    if not credentials.valid:
        raise RuntimeError(
            "Google Calendar token is invalid. "
            "Run: python authorize_google_calendar.py"
        )

    http = AuthorizedHttp(
        credentials,
        http=httplib2.Http(timeout=60),
    )

    return build(
        "calendar",
        "v3",
        http=http,
        cache_discovery=False,
    )


def _round_up_to_slot(value: datetime) -> datetime:
    value = value.astimezone(PKT).replace(
        second=0,
        microsecond=0,
    )

    remainder = value.minute % CALENDAR_SLOT_MINUTES

    if remainder:
        value += timedelta(
            minutes=CALENDAR_SLOT_MINUTES - remainder
        )

    return value


def _parse_google_datetime(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def _get_busy_intervals(
    calendar_service,
    start_at: datetime,
    end_at: datetime,
) -> list[tuple[datetime, datetime]]:
    request_body = {
        "timeMin": start_at.astimezone(
            timezone.utc
        ).isoformat(),
        "timeMax": end_at.astimezone(
            timezone.utc
        ).isoformat(),
        "items": [
            {
                "id": GOOGLE_CALENDAR_ID,
            }
        ],
    }

    response = execute_calendar_request(
        lambda: calendar_service.freebusy().query(
            body=request_body
        ),
        "freebusy.query",
    )

    calendar_data = response.get(
        "calendars",
        {},
    ).get(
        GOOGLE_CALENDAR_ID,
        {},
    )

    if calendar_data.get("errors"):
        raise RuntimeError(
            f"Google Calendar free/busy error: "
            f"{calendar_data['errors']}"
        )

    intervals: list[tuple[datetime, datetime]] = []

    for item in calendar_data.get("busy", []):
        intervals.append(
            (
                _parse_google_datetime(item["start"]),
                _parse_google_datetime(item["end"]),
            )
        )

    return intervals


def _slot_overlaps_busy_time(
    slot_start: datetime,
    slot_end: datetime,
    busy_intervals: list[tuple[datetime, datetime]],
) -> bool:
    return any(
        slot_start < busy_end and slot_end > busy_start
        for busy_start, busy_end in busy_intervals
    )


def find_first_available_slot(
    calendar_service,
) -> tuple[datetime | None, datetime | None]:
    now = datetime.now(PKT)

    search_end = datetime.combine(
        now.date() + timedelta(days=CALENDAR_SEARCH_DAYS + 1),
        time(hour=2, minute=0),
        tzinfo=PKT,
    )

    busy_intervals = _get_busy_intervals(
        calendar_service=calendar_service,
        start_at=now,
        end_at=search_end,
    )

    duration = timedelta(
        minutes=CALENDAR_SLOT_MINUTES
    )

    rounded_now = _round_up_to_slot(now)

    for day_offset in range(CALENDAR_SEARCH_DAYS + 1):
        work_date = now.date() + timedelta(days=day_offset)

        # Monday = 0 through Friday = 4.
        # Friday meetings may continue until Saturday 2 AM.
        if work_date.weekday() > 4:
            continue

        window_start = datetime.combine(
            work_date,
            time(hour=17, minute=0),
            tzinfo=PKT,
        )

        window_end = datetime.combine(
            work_date + timedelta(days=1),
            time(hour=2, minute=0),
            tzinfo=PKT,
        )

        candidate_start = max(
            window_start,
            rounded_now,
        )

        while candidate_start + duration <= window_end:
            candidate_end = candidate_start + duration

            if not _slot_overlaps_busy_time(
                slot_start=candidate_start,
                slot_end=candidate_end,
                busy_intervals=busy_intervals,
            ):
                return candidate_start, candidate_end

            candidate_start += duration

    return None, None


def _extract_google_meet_url(
    event: dict[str, Any],
) -> str:
    direct_url = event.get("hangoutLink", "")

    if direct_url:
        return direct_url

    for entry in event.get(
        "conferenceData",
        {},
    ).get(
        "entryPoints",
        [],
    ):
        if entry.get("entryPointType") == "video":
            return entry.get("uri", "")

    return ""


def _read_event_until_meet_link(
    calendar_service,
    event_id: str,
) -> dict[str, Any]:
    """
    Google Meet link can take a moment to appear after event creation.
    """
    event: dict[str, Any] = {}

    for attempt in range(1, 7):
        event = execute_calendar_request(
            lambda: calendar_service.events().get(
                calendarId=GOOGLE_CALENDAR_ID,
                eventId=event_id,
            ),
            "events.get",
        )

        if _extract_google_meet_url(event):
            return event

        print(
            f"[Calendar] Meet link not ready yet "
            f"for event {event_id}. "
            f"Waiting attempt {attempt}/6."
        )

        time_module.sleep(1)

    return event


def create_first_available_google_meet(
    reply: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Creates a private Calendar event and Google Meet link.

    No attendee is added.
    No invitation email is sent.
    """
    calendar_service = get_google_calendar_service()

    start_at, end_at = find_first_available_slot(
        calendar_service
    )

    if not start_at or not end_at:
        return None

    company_name = (
        str(reply.get("company") or "").strip()
        or str(reply.get("from_name") or "").strip()
        or "Warm Lead"
    )

    reply_id = str(reply.get("reply_id") or "unknown")
    event_id = build_stable_event_id(reply_id)

    event_body = {
        "id": event_id,
        "summary": f"Warm Lead Call | {company_name}",
        "description": (
            "Created automatically from an interested reply.\n"
            f"Reply ID: {reply_id}\n"
            f"Contact: {reply.get('from_name', '')}\n"
            f"Email: {reply.get('from_email', '')}"
        ),
        "extendedProperties": {
            "private": {
                "validiiz_reply_id": reply_id,
            }
        },
        "start": {
            "dateTime": start_at.isoformat(),
            "timeZone": CALENDAR_TIMEZONE,
        },
        "end": {
            "dateTime": end_at.isoformat(),
            "timeZone": CALENDAR_TIMEZONE,
        },
        "visibility": "private",
        "guestsCanInviteOthers": False,
        "reminders": {
            "useDefault": False,
            "overrides": [],
        },
        "conferenceData": {
            "createRequest": {
                "requestId": event_id,
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet",
                },
            },
        },
    }

    def get_existing_event():
        return execute_calendar_request(
            lambda: calendar_service.events().get(
                calendarId=GOOGLE_CALENDAR_ID,
                eventId=event_id,
            ),
            "events.get existing",
        )

    created_event = execute_calendar_request(
        lambda: calendar_service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID,
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates="none",
        ),
        "events.insert",
        on_conflict=get_existing_event,
    )

    event = _read_event_until_meet_link(
        calendar_service=calendar_service,
        event_id=created_event["id"],
    )

    return {
        "calendar_event_id": event["id"],
        "calendar_event_url": event.get("htmlLink", ""),
        "meeting_url": _extract_google_meet_url(event),
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "timezone": CALENDAR_TIMEZONE,
        "duration_minutes": CALENDAR_SLOT_MINUTES,
    }
