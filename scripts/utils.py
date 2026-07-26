#!/usr/bin/env python3
"""Shared utilities for alert-rca-automation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class AlertFrontmatter:
    alert_id: str
    monitor_id: str = ""
    monitor_name: str = ""
    service: str = ""
    env: str = ""
    severity: str = ""
    status: str = "Open"
    triggered_at: str = ""
    rca_at: str = ""
    published_at: str = ""
    confidence: str = ""
    source: str = "datadog"


def load_config() -> dict[str, str]:
    """Load config.env key=value pairs."""
    config_path = REPO_ROOT / "config.env"
    config: dict[str, str] = {}
    if not config_path.exists():
        return config
    for line in config_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        config[key.strip()] = value.strip().strip('"').strip("'")
    return config


def now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")


def parse_frontmatter(content: str) -> tuple[AlertFrontmatter, str]:
    """Parse YAML frontmatter and body from alert markdown."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        raise ValueError("Invalid alert file: missing frontmatter")

    fm_raw, body = match.group(1), match.group(2)
    fields: dict[str, str] = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()

    fm = AlertFrontmatter(
        alert_id=fields.get("alert_id", ""),
        monitor_id=fields.get("monitor_id", ""),
        monitor_name=fields.get("monitor_name", ""),
        service=fields.get("service", ""),
        env=fields.get("env", ""),
        severity=fields.get("severity", ""),
        status=fields.get("status", "Open"),
        triggered_at=fields.get("triggered_at", ""),
        rca_at=fields.get("rca_at", ""),
        published_at=fields.get("published_at", ""),
        confidence=fields.get("confidence", ""),
        source=fields.get("source", "datadog"),
    )
    return fm, body


def serialize_frontmatter(fm: AlertFrontmatter, body: str) -> str:
    """Serialize frontmatter and body back to markdown."""
    lines = [
        "---",
        f"alert_id: {fm.alert_id}",
        f"monitor_id: {fm.monitor_id}",
        f"monitor_name: {fm.monitor_name}",
        f"service: {fm.service}",
        f"env: {fm.env}",
        f"severity: {fm.severity}",
        f"status: {fm.status}",
        f"triggered_at: {fm.triggered_at}",
        f"rca_at: {fm.rca_at}",
        f"published_at: {fm.published_at}",
        f"confidence: {fm.confidence}",
        f"source: {fm.source}",
        "---",
        body.lstrip("\n"),
    ]
    return "\n".join(lines) + "\n"


def extract_section(body: str, heading: str) -> str:
    """Extract content under a ## heading until the next ## heading."""
    pattern = rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, body, re.DOTALL)
    return match.group(1).strip() if match else ""


def is_rca_complete(body: str) -> bool:
    rca = extract_section(body, "Root Cause Analysis")
    if not rca:
        return False
    placeholders = ("_Not yet generated", "_Pending RCA_", "Pending RCA")
    return not any(p in rca for p in placeholders)


def load_processed_alert_ids() -> set[str]:
    """Return set of alert IDs already in _processed_alerts.md."""
    path = REPO_ROOT / "_processed_alerts.md"
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| DD-"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if cols:
                ids.add(cols[0])
    return ids


def load_processed_alert_statuses() -> dict[str, str]:
    """Return {alert_id: status} for all rows in _processed_alerts.md."""
    path = REPO_ROOT / "_processed_alerts.md"
    if not path.exists():
        return {}
    statuses: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| DD-"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 4:
                statuses[cols[0]] = cols[3]
    return statuses


def append_processed_alert(
    alert_id: str,
    monitor: str,
    service: str,
    status: str,
    triggered_at: str,
) -> None:
    """Append a row to _processed_alerts.md."""
    path = REPO_ROOT / "_processed_alerts.md"
    row = f"| {alert_id} | {monitor} | {service} | {status} | {triggered_at} | | |"
    content = path.read_text(encoding="utf-8")
    if not content.endswith("\n"):
        content += "\n"
    path.write_text(content + row + "\n", encoding="utf-8")


def update_processed_alert_status(alert_id: str, **updates: str) -> None:
    """Update columns in _processed_alerts.md for an alert ID."""
    path = REPO_ROOT / "_processed_alerts.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    col_map = {
        "status": 3,
        "rca_at": 5,
        "published_at": 6,
    }
    new_lines = []
    for line in lines:
        if line.startswith(f"| {alert_id} "):
            cols = [c.strip() for c in line.split("|")]
            while len(cols) < 8:
                cols.append("")
            for key, val in updates.items():
                if key in col_map:
                    cols[col_map[key] + 1] = val
            line = "| " + " | ".join(cols[1:-1]) + " |"
        new_lines.append(line)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def make_alert_id(monitor_id: str, triggered_epoch: Optional[int] = None) -> str:
    if triggered_epoch is None:
        triggered_epoch = int(datetime.now(IST).timestamp())
    return f"DD-{monitor_id}-{triggered_epoch}"


def create_alert_file(
    alert_id: str,
    monitor_id: str,
    monitor_name: str,
    service: str,
    env: str,
    severity: str,
    triggered_at: str,
    monitor_query: str = "",
) -> Path:
    """Create a new alert markdown file from template."""
    alerts_dir = REPO_ROOT / "alerts"
    alerts_dir.mkdir(exist_ok=True)
    path = alerts_dir / f"{alert_id}.md"

    body = f"""## Alert Summary
**Monitor**: {monitor_name}
**Status**: Alert
**Service**: {service}
**Env**: {env}
**Triggered**: {triggered_at}
**Monitor query**: {monitor_query or 'N/A'}

## Monitor Details
_Not yet fetched — run /analyse-alert {alert_id}_

## Evidence
_Not yet collected — run /analyse-alert {alert_id}_

## Root Cause Analysis
_Not yet generated — run /analyse-alert {alert_id}_

## Suggested Fix
_Pending RCA_

## Timeline
- **Triggered**: {triggered_at}
- **Fetched**: {now_ist()}
- **RCA completed**:
- **Published to Chat**:
"""

    fm = AlertFrontmatter(
        alert_id=alert_id,
        monitor_id=str(monitor_id),
        monitor_name=monitor_name,
        service=service,
        env=env,
        severity=severity,
        status="Open",
        triggered_at=triggered_at,
        source="datadog",
    )
    path.write_text(serialize_frontmatter(fm, body), encoding="utf-8")
    return path


def format_chat_message(fm: AlertFrontmatter, body: str) -> str:
    """Format RCA for Google Chat."""
    rca = extract_section(body, "Root Cause Analysis")
    evidence = extract_section(body, "Evidence")
    fix = extract_section(body, "Suggested Fix")

    root_cause_line = ""
    for line in rca.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "**" not in stripped[:20]:
            root_cause_line = stripped.lstrip("- ").strip()
            break
        if "Root cause" in stripped.lower():
            root_cause_line = stripped.split(":", 1)[-1].strip()
            break
    if not root_cause_line:
        root_cause_line = rca.splitlines()[0].strip() if rca else "See full report"

    evidence_bullets = []
    for line in evidence.splitlines():
        stripped = line.strip().lstrip("-•").strip()
        if stripped and not stripped.startswith("_"):
            evidence_bullets.append(stripped)
            if len(evidence_bullets) >= 3:
                break

    fix_line = ""
    for line in fix.splitlines():
        stripped = line.strip().lstrip("-•").strip()
        if stripped and not stripped.startswith("_"):
            fix_line = stripped
            break

    msg = f"""🔍 RCA — {fm.monitor_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Triggered: {fm.triggered_at}
📦 Service: {fm.service} | Env: {fm.env}
🎯 Root cause: {root_cause_line}

📊 Evidence:"""

    if evidence_bullets:
        for b in evidence_bullets:
            msg += f"\n   • {b}"
    else:
        msg += "\n   • See full report"

    msg += f"""

✅ Suggested action:
   {fix_line or 'See full report'}

🎚 Confidence: {fm.confidence or 'N/A'}
📄 Full report: alerts/{fm.alert_id}.md"""

    return msg[:4096]
