#!/usr/bin/env python3
"""
Create an alert file from a Google Chat / Datadog alert message (no Datadog API needed).

Usage:
    python scripts/create_alert_from_chat.py --text "Monitor: [Prod] error rate..."
    python scripts/create_alert_from_chat.py --file alert_message.txt
    pbpaste | python scripts/create_alert_from_chat.py --stdin
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (  # noqa: E402
    append_processed_alert,
    create_alert_file,
    load_processed_alert_ids,
    make_alert_id,
    now_ist,
)


def parse_chat_alert_text(text: str) -> dict:
    """Parse a Datadog alert message copied from Google Chat."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]

    monitor_name = "Unknown Monitor"
    service = ""
    env = ""
    severity = ""
    monitor_id = ""
    triggered_at = now_ist()
    status = "Alert"

    for line in lines:
        lower = line.lower()

        if re.match(r"^monitor\s*:", lower):
            monitor_name = line.split(":", 1)[1].strip()
        elif re.match(r"^service\s*:", lower):
            service = line.split(":", 1)[1].strip()
        elif re.match(r"^env\s*:", lower) or re.match(r"^environment\s*:", lower):
            env = line.split(":", 1)[1].strip()
        elif re.match(r"^priority\s*:", lower) or re.match(r"^severity\s*:", lower):
            severity = line.split(":", 1)[1].strip()
        elif re.match(r"^status\s*:", lower):
            status = line.split(":", 1)[1].strip()
        elif re.match(r"^monitor\s*id\s*:", lower):
            monitor_id = line.split(":", 1)[1].strip()
        elif re.match(r"^(triggered|time|date)\s*:", lower):
            triggered_at = line.split(":", 1)[1].strip()

    # Datadog Chat cards sometimes use **Monitor** format
    for line in lines:
        if "**" in line:
            clean = line.replace("*", "")
            if "monitor" in clean.lower() and ":" in clean:
                monitor_name = clean.split(":", 1)[1].strip()
            if "service" in clean.lower() and ":" in clean:
                service = clean.split(":", 1)[1].strip()

    if not monitor_id:
        monitor_id = str(int(datetime.now().timestamp()))

    return {
        "monitor_id": monitor_id,
        "monitor_name": monitor_name,
        "service": service,
        "env": env,
        "severity": severity,
        "status": status,
        "triggered_at": triggered_at,
        "message": text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create alert from Google Chat message text")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Alert message text")
    group.add_argument("--file", help="Path to file containing alert message")
    group.add_argument("--stdin", action="store_true", help="Read alert message from stdin")
    args = parser.parse_args()

    if args.text:
        text = args.text
    elif args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("Error: empty alert text", file=sys.stderr)
        return 1

    alert_data = parse_chat_alert_text(text)
    processed = load_processed_alert_ids()

    monitor_id = alert_data["monitor_id"]
    epoch = int(datetime.now().timestamp())
    alert_id = make_alert_id(monitor_id, epoch)

    if alert_id in processed:
        print(f"Alert already exists: {alert_id}")
        return 0

    path = create_alert_file(
        alert_id=alert_id,
        monitor_id=monitor_id,
        monitor_name=alert_data["monitor_name"],
        service=alert_data["service"],
        env=alert_data["env"],
        severity=alert_data["severity"],
        triggered_at=alert_data["triggered_at"],
        monitor_query="",
    )

    # Append raw message to alert file for RCA context
    content = path.read_text(encoding="utf-8")
    content = content.replace(
        "## Alert Summary",
        f"## Alert Summary\n\n<details><summary>Original Google Chat message</summary>\n\n```\n{text.strip()}\n```\n\n</details>\n",
    )
    path.write_text(content, encoding="utf-8")

    append_processed_alert(
        alert_id=alert_id,
        monitor=alert_data["monitor_name"],
        service=alert_data["service"],
        status="Open",
        triggered_at=alert_data["triggered_at"],
    )

    print(f"✓ Created alert: {alert_id}")
    print(f"  File: {path}")
    print(f"  Monitor: {alert_data['monitor_name']}")
    print(f"\nNext: run /analyse-alert {alert_id} in Cursor (uses Datadog MCP — no API key needed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
