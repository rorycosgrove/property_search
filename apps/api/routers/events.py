"""Real-time events endpoint — Server-Sent Events (SSE) for live property signals.

Clients connect to GET /api/v1/events/stream to receive a continuous stream of
signal events (price drops, status changes, new listings) as they are detected.

The implementation uses a simple polling approach: once connected, the server
queries for recent activity every N seconds and emits only new events.  This is
deployment-safe for Lambda (short-lived) but works perfectly for long-running
uvicorn / ECS deployments where SSE connections are kept alive.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from packages.properties.discovery import get_discovery_feed
from packages.storage.database import get_db_session

router = APIRouter()

_SSE_HEARTBEAT_S = 15
_SSE_POLL_S = 20
_SSE_MAX_DURATION_S = 60 * 5   # 5 min max connection before client must reconnect


async def _event_generator(db: Session, since_seconds: int) -> AsyncIterator[str]:
    """Async generator yielding SSE-formatted text chunks."""
    started_at = datetime.now(timezone.utc)
    last_ids: set[str] = set()

    def _make_sse(event: str, data: dict) -> str:
        payload = json.dumps(data, default=str)
        return f"event: {event}\ndata: {payload}\n\n"

    # Emit an initial connection event
    yield _make_sse("connected", {"ts": started_at.isoformat(), "poll_interval_s": _SSE_POLL_S})

    poll_count = 0
    while True:
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        if elapsed >= _SSE_MAX_DURATION_S:
            yield _make_sse("close", {"reason": "max_duration_reached", "reconnect": True})
            break

        # Heartbeat
        yield f": heartbeat {int(elapsed)}s\n\n"

        # Poll for fresh signals every _SSE_POLL_S seconds
        if poll_count % max(1, _SSE_POLL_S // _SSE_HEARTBEAT_S) == 0:
            try:
                cards = get_discovery_feed(db, limit=10)
                for card in cards:
                    card_id = f"{card['signal_type']}:{card['property_id']}"
                    if card_id not in last_ids:
                        last_ids.add(card_id)
                        yield _make_sse("signal", card)
            except Exception:  # noqa: BLE001 — don't kill the stream on DB error
                pass

        poll_count += 1
        await asyncio.sleep(_SSE_HEARTBEAT_S)


@router.get("/stream")
async def event_stream(
    since: int = Query(
        300,
        ge=0,
        le=86400,
        description="Look-back window in seconds for initial signal emission",
    ),
    db: Session = Depends(get_db_session),
):
    """Server-Sent Events stream of property signals.

    Connect with::

        const es = new EventSource('/api/v1/events/stream');
        es.addEventListener('signal', e => console.log(JSON.parse(e.data)));

    Events emitted:
    - ``connected``  — on first connect, includes poll interval info
    - ``signal``     — a discovery signal card (same schema as /discovery/feed)
    - ``close``      — server is ending the stream; client should reconnect
    - heartbeat comments (``:``) every 15 s keep the connection alive
    """
    return StreamingResponse(
        _event_generator(db, since),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable nginx buffering
            "Connection": "keep-alive",
        },
    )
