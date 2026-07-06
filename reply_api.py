from fastapi import FastAPI, HTTPException, Query

from seed_dummy_replies import seed_dummy_replies
from services.reply_processor_service import (
    list_replies,
    process_pending_replies,
)

app = FastAPI(
    title="Validiiz Reply Processing API",
    version="1.0.0",
    description=(
        "Classifies stored replies, assigns MongoDB tags, and creates private "
        "Google Calendar events with Google Meet links. This API never sends emails."
    ),
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "sends_email": False,
        "workflow": "reply_processing",
    }


@app.post("/seed-dummy-replies")
def seed_replies():
    try:
        return seed_dummy_replies()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/process-pending-replies")
def process_replies(
    limit: int = Query(default=100, ge=1, le=500),
):
    try:
        results = process_pending_replies(limit=limit)
        return {
            "processed_count": len(results),
            "results": results,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/replies")
def get_replies(
    tag: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    try:
        return {
            "tag_filter": tag,
            "replies": list_replies(tag=tag, limit=limit),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
