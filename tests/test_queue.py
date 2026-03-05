"""Tests for SQS queue publisher utility."""
import json
import pytest
from unittest.mock import patch, MagicMock

from packages.shared.queue import send_task, _resolve_queue_url


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
