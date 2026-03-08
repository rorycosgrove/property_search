"""Tests for SQS queue publisher utility."""
import json
from unittest.mock import MagicMock, patch

import pytest

from packages.shared.queue import _build_deduplication_id, _resolve_queue_url, send_task


class TestSendTask:
    @patch.dict(
        "os.environ",
        {"SCRAPE_QUEUE_URL": "https://sqs.eu-west-1.amazonaws.com/123/scrape"},
    )
    @patch("packages.shared.queue._get_sqs_client")
    def test_send_task_scrape(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.send_message.return_value = {"MessageId": "msg-123"}
        mock_get_client.return_value = mock_client

        result = send_task("scrape", "scrape_source", {"source_id": "abc"})

        assert result == "msg-123"
        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        body = json.loads(call_kwargs["MessageBody"])
        assert body["task_type"] == "scrape_source"
        assert body["payload"] == {"source_id": "abc"}

    def test_send_task_unknown_queue_raises(self):
        with patch.dict("os.environ", {}, clear=False):
            with pytest.raises(ValueError, match="No queue URL configured"):
                send_task("nonexistent", "task", {})

    @patch.dict(
        "os.environ",
        {"SCRAPE_QUEUE_URL": "https://sqs.eu-west-1.amazonaws.com/123/scrape.fifo"},
    )
    @patch("packages.shared.queue._get_sqs_client")
    def test_send_task_fifo_uses_deterministic_dedup_id(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.send_message.return_value = {"MessageId": "msg-123"}
        mock_get_client.return_value = mock_client

        payload = {"source_id": "abc", "force": False}
        send_task("scrape", "scrape_source", payload)

        call_kwargs = mock_client.send_message.call_args[1]
        expected = _build_deduplication_id("scrape_source", payload)
        assert call_kwargs["MessageGroupId"] == "scrape_source"
        assert call_kwargs["MessageDeduplicationId"] == expected


class TestResolveQueueUrl:
    @patch.dict(
        "os.environ",
        {"LLM_QUEUE_URL": "https://sqs.eu-west-1.amazonaws.com/123/llm"},
    )
    def test_resolve_llm(self):
        url = _resolve_queue_url("llm")
        assert "llm" in url

    def test_resolve_unknown_returns_empty(self):
        assert _resolve_queue_url("unknown") == ""


class TestDeduplicationId:
    def test_dedup_id_is_order_insensitive_for_payload_keys(self):
        a = _build_deduplication_id("scrape_source", {"source_id": "x", "force": False})
        b = _build_deduplication_id("scrape_source", {"force": False, "source_id": "x"})
        assert a == b

    def test_dedup_id_changes_with_payload(self):
        a = _build_deduplication_id("scrape_source", {"source_id": "x"})
        b = _build_deduplication_id("scrape_source", {"source_id": "y"})
        assert a != b
