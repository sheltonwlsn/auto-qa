import os

import click
import httpx


def post_slack_notification(text: str, webhook_url: str = None):
    webhook = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        click.echo("\n[Slack Notification Skipped]: No webhook URL configured.\n")
        return

    payload = {"text": text}

    try:
        response = httpx.post(webhook, json=payload, timeout=10)
        if response.status_code != 200:
            click.echo(f"[Slack Error]: {response.status_code} - {response.text}")
        else:
            click.echo("[Slack]: Notification sent.")
    except Exception as e:
        click.echo(f"[Slack Error]: {e}")
