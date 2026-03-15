"""Tests for SQS worker task dispatch registration."""

from __future__ import annotations

import json


def test_register_handlers_includes_discover_all_sources():
    from apps.worker import sqs_handler

    sqs_handler._TASK_HANDLERS.clear()
    sqs_handler._register_handlers()

    assert "discover_all_sources" in sqs_handler._TASK_HANDLERS


def test_handler_routes_discover_all_sources(monkeypatch):
    from apps.worker import sqs_handler

    monkeypatch.setattr(sqs_handler, "setup_logging", lambda: None)
    monkeypatch.setattr(sqs_handler, "_register_handlers", lambda: None)

    sqs_handler._TASK_HANDLERS.clear()
    sqs_handler._TASK_HANDLERS["discover_all_sources"] = lambda **payload: {
        "received_limit": payload.get("limit"),
        "dry_run": payload.get("dry_run"),
    }

    event = {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "task_type": "discover_all_sources",
                        "task_id": "t-1",
                        "payload": {"limit": 10, "dry_run": True},
                    }
                )
            }
        ]
    }

    result = sqs_handler.handler(event, None)

    assert result["failed"] == 0
    assert result["processed"] == 1
    assert result["results"][0]["task_type"] == "discover_all_sources"
    assert result["results"][0]["result"]["received_limit"] == 10
