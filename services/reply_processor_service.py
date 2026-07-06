import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ASCENDING, ReturnDocument

from reply_config import (
    DEEPSEEK_MODEL,
    deepseek_client,
    inbound_replies_collection,
)
from services.reply_calendar_service import create_first_available_google_meet

_INDEXES_READY = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, list):
        return [_serialize(item) for item in value]

    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}

    return value


def public_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None

    return {
        key: _serialize(value)
        for key, value in document.items()
        if key != "_id"
    }


def ensure_indexes() -> None:
    global _INDEXES_READY

    if _INDEXES_READY:
        return

    inbound_replies_collection.create_index(
        [("reply_id", ASCENDING)],
        unique=True,
        name="uniq_reply_id",
    )

    inbound_replies_collection.create_index(
        [
            ("processing_status", ASCENDING),
            ("received_at", ASCENDING),
        ],
        name="reply_processing_queue",
    )

    inbound_replies_collection.create_index(
        [("tags", ASCENDING)],
        name="reply_tags",
    )

    _INDEXES_READY = True


def _parse_model_json(raw_text: str) -> dict[str, Any]:
    raw_text = (raw_text or "").strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)

        if not match:
            raise ValueError("Reply classifier returned no JSON object.")

        return json.loads(match.group(0))


def classify_reply(reply: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
You classify B2B outbound email replies.

Return valid JSON only. The response must contain the word json by following this exact JSON shape:
{{
  "decision": "interested | not_interested | ambiguous",
  "confidence": 0.0,
  "reason": "short reason"
}}

Classification rules:
- interested: The person clearly wants a meeting, call, demo, discussion, or wants to move forward.
- not_interested: The person clearly declines, says no, asks to unsubscribe, says this is irrelevant, or says they already have a provider.
- ambiguous: The person asks for more details, pricing, a case study, asks to reconnect later, says maybe, refers another person, or intent is unclear.

Important rules:
- Never classify a polite reply as interested unless it clearly asks to move forward.
- "Send more details" is ambiguous.
- "Maybe next quarter" is ambiguous.
- "Please contact our marketing lead" is ambiguous.
- Keep reason concise and based only on the reply.

From name: {reply.get('from_name', '')}
From company: {reply.get('company', '')}
Reply subject: {reply.get('subject', '')}
Reply text: {reply.get('reply_text', '')}
"""

    response = deepseek_client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
        max_tokens=400,
        response_format={"type": "json_object"},
    )

    parsed = _parse_model_json(response.choices[0].message.content or "{}")
    decision = _clean_text(parsed.get("decision")).lower()

    if decision not in {"interested", "not_interested", "ambiguous"}:
        decision = "ambiguous"

    try:
        confidence = float(parsed.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "decision": decision,
        "confidence": max(0.0, min(1.0, confidence)),
        "reason": _clean_text(parsed.get("reason"))[:300],
        "model": DEEPSEEK_MODEL,
        "classified_at": utc_now(),
    }


def _claim_next_pending_reply() -> dict[str, Any] | None:
    now = utc_now()
    stale_before = now - timedelta(minutes=30)

    return inbound_replies_collection.find_one_and_update(
        {
            "$or": [
                {"processing_status": "pending"},
                {
                    "processing_status": "processing",
                    "processing_started_at": {"$lt": stale_before},
                },
            ]
        },
        {
            "$set": {
                "processing_status": "processing",
                "processing_started_at": now,
                "last_error": "",
            }
        },
        sort=[("received_at", ASCENDING)],
        return_document=ReturnDocument.AFTER,
    )


def _save_processed_reply(
    reply_id: str,
    classification: dict[str, Any],
    tags: list[str],
    meeting: dict[str, Any] | None,
    meeting_status: str,
    error: str = "",
) -> None:
    inbound_replies_collection.update_one(
        {"reply_id": reply_id},
        {
            "$set": {
                "classification": classification,
                "tags": tags,
                "meeting": meeting,
                "meeting_status": meeting_status,
                "processing_status": "processed",
                "processed_at": utc_now(),
                "last_error": error,
            }
        },
    )


def _process_claimed_reply(reply: dict[str, Any]) -> dict[str, Any]:
    reply_id = reply["reply_id"]

    try:
        classification = classify_reply(reply)
        decision = classification["decision"]

        if decision == "not_interested":
            _save_processed_reply(
                reply_id=reply_id,
                classification=classification,
                tags=["lost"],
                meeting=None,
                meeting_status="not_required",
            )
            return {"reply_id": reply_id, "status": "lost"}

        if decision == "ambiguous":
            _save_processed_reply(
                reply_id=reply_id,
                classification=classification,
                tags=["needs_review"],
                meeting=None,
                meeting_status="not_required",
            )
            return {"reply_id": reply_id, "status": "needs_review"}

        try:
            meeting = create_first_available_google_meet(reply)

            if not meeting:
                _save_processed_reply(
                    reply_id=reply_id,
                    classification=classification,
                    tags=["warm_lead", "needs_review"],
                    meeting=None,
                    meeting_status="no_available_slot",
                    error=(
                        "No available 30-minute slot was found in the configured search window."
                    ),
                )
                return {"reply_id": reply_id, "status": "warm_lead_no_slot"}

            if not meeting.get("meeting_url"):
                _save_processed_reply(
                    reply_id=reply_id,
                    classification=classification,
                    tags=["warm_lead", "needs_review"],
                    meeting=meeting,
                    meeting_status="meet_link_missing",
                    error=(
                        "Calendar event was created but Google Meet link was not returned."
                    ),
                )
                return {
                    "reply_id": reply_id,
                    "status": "warm_lead_meet_link_missing",
                }

            _save_processed_reply(
                reply_id=reply_id,
                classification=classification,
                tags=["warm_lead", "meeting"],
                meeting=meeting,
                meeting_status="scheduled",
            )

            return {
                "reply_id": reply_id,
                "status": "meeting_scheduled",
                "meeting": _serialize(meeting),
            }

        except Exception as calendar_error:
            _save_processed_reply(
                reply_id=reply_id,
                classification=classification,
                tags=["warm_lead", "needs_review"],
                meeting=None,
                meeting_status="calendar_error",
                error=str(calendar_error),
            )
            return {
                "reply_id": reply_id,
                "status": "warm_lead_calendar_error",
                "error": str(calendar_error),
            }

    except Exception as error:
        fallback_classification = {
            "decision": "ambiguous",
            "confidence": 0.0,
            "reason": "Automatic classification failed. Manual review is required.",
            "model": DEEPSEEK_MODEL,
            "classified_at": utc_now(),
        }

        _save_processed_reply(
            reply_id=reply_id,
            classification=fallback_classification,
            tags=["needs_review"],
            meeting=None,
            meeting_status="not_required",
            error=str(error),
        )
        return {
            "reply_id": reply_id,
            "status": "needs_review",
            "error": str(error),
        }


def process_pending_replies(limit: int = 100) -> list[dict[str, Any]]:
    ensure_indexes()
    results: list[dict[str, Any]] = []

    while len(results) < limit:
        reply = _claim_next_pending_reply()

        if not reply:
            break

        results.append(_process_claimed_reply(reply))

    return results


def list_replies(tag: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    ensure_indexes()
    query: dict[str, Any] = {}

    if tag:
        query["tags"] = tag

    documents = inbound_replies_collection.find(query).sort(
        "received_at",
        -1,
    ).limit(limit)

    return [public_document(document) for document in documents]
