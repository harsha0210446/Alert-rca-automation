#!/usr/bin/env python3
"""Publish RCA to Google Chat."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (  # noqa: E402
    REPO_ROOT,
    format_chat_message,
    is_rca_complete,
    load_config,
    now_ist,
    parse_frontmatter,
    serialize_frontmatter,
    update_processed_alert_status,
)


def publish_to_chat(message: str, webhook_url: str) -> bool:
    resp = requests.post(
        webhook_url,
        json={"text": message},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return True


def publish_alert(alert_id: str) -> int:
    """Publish RCA for an alert to Google Chat. Returns 0 on success."""
    alert_path = REPO_ROOT / "alerts" / f"{alert_id}.md"
    if not alert_path.exists():
        print(f"Error: Alert file not found: {alert_path}", file=sys.stderr)
        return 1

    content = alert_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    if not is_rca_complete(body):
        print(f"Error: RCA not complete for {alert_id}. Run auto_rca first.", file=sys.stderr)
        return 1

    config = load_config()
    webhook = config.get("GOOGLE_CHAT_WEBHOOK_URL", "")
    if not webhook:
        print("⚠ GOOGLE_CHAT_WEBHOOK_URL not configured — skipping Chat", file=sys.stderr)
        print("Nothing was published. Check config.env.", file=sys.stderr)
        return 1

    message = format_chat_message(fm, body)
    try:
        publish_to_chat(message, webhook)
        print(f"✓ Published to Google Chat: {alert_id}")
    except requests.RequestException as exc:
        print(f"✗ Google Chat publish failed: {exc}", file=sys.stderr)
        return 1

    fm.published_at = now_ist()
    fm.status = "Published"
    if "- **Published to Chat**:" in body:
        body = body.replace(
            "- **Published to Chat**:",
            f"- **Published to Chat**: {fm.published_at}",
        )
    alert_path.write_text(serialize_frontmatter(fm, body), encoding="utf-8")
    update_processed_alert_status(alert_id, status="Published", published_at=fm.published_at)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish alert RCA to Google Chat")
    parser.add_argument("alert_id", help="Alert ID e.g. DD-167097893-1721780400")
    args = parser.parse_args()
    return publish_alert(args.alert_id)


if __name__ == "__main__":
    raise SystemExit(main())
