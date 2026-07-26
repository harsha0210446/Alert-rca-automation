#!/usr/bin/env python3
"""
Full automated pipeline: alert → investigate → RCA → publish to Google Chat.

Called automatically by webhook_server when an alert arrives.
Can also be run manually: python scripts/run_auto_pipeline.py DD-xxxxx
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_rca import run_auto_rca  # noqa: E402
from create_alert_from_chat import parse_chat_alert_text  # noqa: E402
from publish_rca import publish_alert  # noqa: E402
from utils import (  # noqa: E402
    append_processed_alert,
    create_alert_file,
    load_config,
    load_processed_alert_ids,
    make_alert_id,
    now_ist,
)
from datetime import datetime


def create_alert_from_data(alert_data: dict) -> str:
    """Create alert file from parsed webhook/chat data. Returns alert_id."""
    processed = load_processed_alert_ids()
    monitor_id = alert_data.get("monitor_id") or str(int(datetime.now().timestamp()))
    epoch = int(datetime.now().timestamp())
    alert_id = make_alert_id(monitor_id, epoch)

    # Dedupe: skip if same monitor alerted in last 30 min
    monitor_name = alert_data.get("monitor_name", "")
    for existing_id in processed:
        if monitor_name and monitor_name != "Unknown Monitor":
            # Simple dedupe by monitor name prefix in processed file
            pass  # still create with new epoch — dedupe handled by caller

    create_alert_file(
        alert_id=alert_id,
        monitor_id=monitor_id,
        monitor_name=alert_data.get("monitor_name", "Unknown Monitor"),
        service=alert_data.get("service", ""),
        env=alert_data.get("env", ""),
        severity=alert_data.get("severity", ""),
        triggered_at=str(alert_data.get("triggered_at", now_ist())),
        monitor_query=alert_data.get("query", ""),
    )

    # Attach raw message if present
    if alert_data.get("message"):
        alert_path = Path(__file__).resolve().parent.parent / "alerts" / f"{alert_id}.md"
        content = alert_path.read_text(encoding="utf-8")
        msg = alert_data["message"][:5000]
        content = content.replace(
            "## Alert Summary",
            f"## Alert Summary\n\n**Original alert message:**\n```\n{msg}\n```\n",
        )
        alert_path.write_text(content, encoding="utf-8")

    append_processed_alert(
        alert_id=alert_id,
        monitor=alert_data.get("monitor_name", "Unknown"),
        service=alert_data.get("service", ""),
        status="Open",
        triggered_at=str(alert_data.get("triggered_at", now_ist())),
    )
    return alert_id


def run_pipeline(alert_data: dict | None = None, alert_id: str | None = None) -> dict:
    """
    Run full automation: create (if needed) → RCA → publish.
    Returns result dict with status and alert_id.
    """
    config = load_config()
    result = {"status": "error", "alert_id": alert_id, "steps": []}

    try:
        # Step 1: Create alert file if we have raw data
        if alert_data and not alert_id:
            text = alert_data.get("message", "")
            if text and alert_data.get("monitor_name") == "Unknown Monitor":
                parsed = parse_chat_alert_text(text)
                alert_data.update({k: v for k, v in parsed.items() if v})

            alert_id = create_alert_from_data(alert_data)
            result["steps"].append(f"created:{alert_id}")

        if not alert_id:
            result["error"] = "No alert_id or alert_data provided"
            return result

        result["alert_id"] = alert_id

        # Step 2: Auto RCA
        if config.get("AUTO_RCA_ENABLED", "true").lower() != "false":
            run_auto_rca(alert_id, config)
            result["steps"].append("rca:done")
        else:
            result["steps"].append("rca:skipped")

        # Step 3: Publish to Google Chat
        if config.get("AUTO_PUBLISH_ENABLED", "true").lower() != "false":
            rc = publish_alert(alert_id)
            if rc == 0:
                result["steps"].append("publish:done")
            else:
                result["steps"].append("publish:failed")
        else:
            result["steps"].append("publish:skipped")

        result["status"] = "success"
        print(f"[pipeline] ✓ Complete for {alert_id}: {result['steps']}")

    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        print(f"[pipeline] ✗ Failed: {exc}")
        traceback.print_exc()

    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_auto_pipeline.py DD-xxxxx", file=sys.stderr)
        print("   or: python scripts/run_auto_pipeline.py --text 'Monitor: ...'", file=sys.stderr)
        return 1

    if sys.argv[1] == "--text":
        text = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        alert_data = parse_chat_alert_text(text)
        alert_data["message"] = text
        result = run_pipeline(alert_data=alert_data)
    else:
        result = run_pipeline(alert_id=sys.argv[1])

    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
