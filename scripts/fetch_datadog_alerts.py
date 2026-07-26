#!/usr/bin/env python3
"""Poll Datadog for alerting monitors and create alert stub files."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datadog_client import has_datadog_auth, search_monitors  # noqa: E402
from utils import (  # noqa: E402
    append_processed_alert,
    create_alert_file,
    load_config,
    load_processed_alert_statuses,
    make_alert_id,
    now_ist,
)


def fetch_alerting_monitors(query: str, config: dict) -> list[dict]:
    monitor_list = search_monitors(query, config)

    results = []
    for m in monitor_list:
        if hasattr(m, "to_dict"):
            m = m.to_dict()
        status = (m.get("status") or "").lower()
        if status not in ("alert", "warn", "no data"):
            continue
        tags = {}
        for tag in m.get("tags") or []:
            if ":" in tag:
                k, v = tag.split(":", 1)
                tags[k] = v
        results.append(
            {
                "id": str(m.get("id", "")),
                "name": m.get("name", "Unknown"),
                "status": m.get("status", ""),
                "service": tags.get("service", ""),
                "env": tags.get("env", ""),
                "priority": str(m.get("priority") or tags.get("priority", "")),
                "query": m.get("query", ""),
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Datadog alerting monitors")
    parser.add_argument(
        "--query",
        default=None,
        help="Datadog monitor search query (default from config.env or status:alert OR status:warn)",
    )
    args = parser.parse_args()

    config = load_config()
    if not has_datadog_auth(config):
        print("Error: Set DD_ACCESS_TOKEN in config.env (your Datadog Personal Access Token)", file=sys.stderr)
        print("  No API key or App key needed — just the ddpat_ token.", file=sys.stderr)
        print("  Or skip fetch entirely: use create_alert_from_chat.py when alerts land in Google Chat.", file=sys.stderr)
        return 1

    query = args.query or config.get("DD_MONITOR_QUERY", "status:alert OR status:warn")

    try:
        monitors = fetch_alerting_monitors(query, config)
    except Exception as exc:
        print(f"Error fetching monitors: {exc}", file=sys.stderr)
        return 1

    processed = load_processed_alert_statuses()

    created = skipped = 0
    new_alerts: list[str] = []

    for mon in monitors:
        epoch = int(datetime.now().timestamp())
        alert_id = make_alert_id(mon["id"], epoch)

        already_open = any(
            aid.startswith(f"DD-{mon['id']}-") and status == "Open"
            for aid, status in processed.items()
        )
        if already_open:
            skipped += 1
            continue

        triggered_at = now_ist()

        create_alert_file(
            alert_id=alert_id,
            monitor_id=mon["id"],
            monitor_name=mon["name"],
            service=mon["service"] or mon["name"].split()[0],
            env=mon["env"],
            severity=mon["priority"],
            triggered_at=triggered_at,
            monitor_query=mon["query"],
        )
        append_processed_alert(
            alert_id=alert_id,
            monitor=mon["name"],
            service=mon["service"] or "",
            status="Open",
            triggered_at=triggered_at,
        )

        processed[alert_id] = "Open"
        created += 1
        new_alerts.append(f"  {alert_id} — {mon['name']}")

    print(f"Fetched {len(monitors)} alerting monitors")
    print(f"Skipped (already open): {skipped}")
    print(f"New alerts created: {created}")
    if new_alerts:
        print("New alerts:")
        print("\n".join(new_alerts))
        print("\nNext: run /analyse-alert {ID} for each new alert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
