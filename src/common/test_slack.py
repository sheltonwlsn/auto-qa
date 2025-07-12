import os
from unittest.mock import MagicMock, patch

import httpx


def post_slack_notification(text: str, webhook_url: str = None):
    webhook = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        print("\n[Slack Notification Skipped]: No webhook URL configured.\n")
        return

    payload = {"text": text}

    try:
        response = httpx.post(webhook, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"[Slack Error]: {response.status_code} - {response.text}")
        else:
            print("[Slack]: Notification sent.")
    except Exception as e:
        print(f"[Slack Error]: {e}")


# Unit tests for post_slack_notification function
def test_post_slack_notification_no_webhook(monkeypatch):
    # Test when no webhook URL is provided and environment variable is not set
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with patch("builtins.print") as mock_print:
        post_slack_notification("Test message")
        mock_print.assert_called_once_with(
            "\n[Slack Notification Skipped]: No webhook URL configured.\n"
        )


def test_post_slack_notification_with_env_webhook(monkeypatch):
    # Test when webhook URL is provided via environment variable
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "http://example.com/webhook")
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        with patch("builtins.print") as mock_print:
            post_slack_notification("Test message")
            mock_post.assert_called_once_with(
                "http://example.com/webhook", json={"text": "Test message"}, timeout=10
            )
            mock_print.assert_called_once_with("[Slack]: Notification sent.")


def test_post_slack_notification_with_argument_webhook():
    # Test when webhook URL is provided as an argument
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        with patch("builtins.print") as mock_print:
            post_slack_notification("Test message", "http://example.com/webhook")
            mock_post.assert_called_once_with(
                "http://example.com/webhook", json={"text": "Test message"}, timeout=10
            )
            mock_print.assert_called_once_with("[Slack]: Notification sent.")


def test_post_slack_notification_http_error():
    # Test when the HTTP request returns a non-200 status code
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response
        with patch("builtins.print") as mock_print:
            post_slack_notification("Test message", "http://example.com/webhook")
            mock_post.assert_called_once_with(
                "http://example.com/webhook", json={"text": "Test message"}, timeout=10
            )
            mock_print.assert_called_once_with("[Slack Error]: 400 - Bad Request")


def test_post_slack_notification_exception():
    # Test when an exception is raised during the HTTP request
    with patch("httpx.post", side_effect=Exception("Network error")) as mock_post:
        with patch("builtins.print") as mock_print:
            post_slack_notification("Test message", "http://example.com/webhook")
            mock_post.assert_called_once_with(
                "http://example.com/webhook", json={"text": "Test message"}, timeout=10
            )
            mock_print.assert_called_once_with("[Slack Error]: Network error")
