# Validiiz Reply Workflow

This standalone workflow uses the same MongoDB database as the outreach project but does not modify the outreach API.

## What it does

1. Reads `pending` documents from `inbound_replies`.
2. Uses DeepSeek to classify each reply as `interested`, `not_interested`, or `ambiguous`.
3. Saves MongoDB tags:
   - `lost`
   - `needs_review`
   - `warm_lead` + `meeting`
4. For interested replies, checks the authenticated Google Calendar and creates the first free 30-minute event between Monday–Friday, 5 PM–2 AM PKT.
5. Creates a Google Meet link and saves it inside the reply document.

No email is sent and no attendee/invitation is added to the Calendar event.

## Files you must provide

- `.env` copied from `.env.example`, with your own values.
- `credentials.json` from a Google OAuth Desktop App.

## Main commands

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python authorize_google_calendar.py
python seed_dummy_replies.py
uvicorn reply_api:app --reload --port 8001
```

Swagger:

```text
http://127.0.0.1:8001/docs
```
