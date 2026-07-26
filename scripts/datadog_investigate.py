#!/usr/bin/env python3
"""Fetch Datadog evidence for an alert using Personal Access Token."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datadog_client import api_host, datadog_headers, has_datadog_auth  # noqa: E402
from utils import load_config, parse_frontmatter  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))

STACK_FRAME_RE = re.compile(r"at com\.pharmeasy\.[\w.$]+\(([\w]+\.(?:kt|java)):(\d+)\)")
SKIP_DIRS = {"node_modules", ".git", "build", "target", ".venv", "__pycache__", "dist", ".gradle", ".idea"}


def _time_window(triggered_at: str, minutes_before: int = 15, minutes_after: int = 5) -> tuple[str, str]:
    """Return ISO from/to for Datadog queries."""
    now = datetime.now(IST)
    try:
        # Try parsing common formats; fall back to now
        for fmt in ("%Y-%m-%d %H:%M IST", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(triggered_at.replace("+0530", "+05:30"), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=IST)
                start = dt - timedelta(minutes=minutes_before)
                end = dt + timedelta(minutes=minutes_after)
                return start.isoformat(), end.isoformat()
            except ValueError:
                continue
    except Exception:
        pass
    start = now - timedelta(minutes=minutes_before)
    end = now + timedelta(minutes=minutes_after)
    return start.isoformat(), end.isoformat()


def fetch_monitor(monitor_id: str, config: dict) -> dict[str, Any]:
    if not monitor_id or not has_datadog_auth(config):
        return {}
    host = api_host(config)
    headers = datadog_headers(config)
    try:
        resp = requests.get(f"{host}/api/v1/monitor/{monitor_id}", headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return {}


def fetch_alert_events(monitor_id: str, config: dict, time_from: str, time_to: str) -> list[dict]:
    if not has_datadog_auth(config):
        return []
    host = api_host(config)
    headers = datadog_headers(config)
    params = {
        "start": int(datetime.fromisoformat(time_from).timestamp()),
        "end": int(datetime.fromisoformat(time_to).timestamp()),
    }
    query = f"source:alert monitor_id:{monitor_id}" if monitor_id else "source:alert"
    params["text"] = query
    try:
        resp = requests.get(f"{host}/api/v1/events", headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("events", [])[:10]
    except requests.RequestException:
        pass
    return []


def fetch_error_logs(service: str, config: dict, time_from: str, time_to: str, limit: int = 25) -> list[dict]:
    if not has_datadog_auth(config):
        return []
    host = api_host(config)
    headers = datadog_headers(config)
    query = f"service:{service} status:error" if service else "status:error"
    body = {
        "filter": {
            "from": time_from,
            "to": time_to,
            "query": query,
        },
        "page": {"limit": limit},
        "sort": "-timestamp",
    }
    try:
        resp = requests.post(
            f"{host}/api/v2/logs/events/search",
            headers=headers,
            json=body,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            return [item.get("attributes", {}) for item in data]
    except requests.RequestException:
        pass
    return []


def aggregate_log_messages(logs: list[dict]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for log in logs:
        msg = (log.get("message") or "")[:200]
        if msg:
            counts[msg] = counts.get(msg, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])[:10]


def fetch_error_traces(service: str, config: dict, time_from: str, time_to: str, limit: int = 10) -> list[dict]:
    """Find failing APM spans/traces in the window (if APM enabled for the service)."""
    if not has_datadog_auth(config):
        return []
    host = api_host(config)
    headers = datadog_headers(config)
    query = f"service:{service} status:error" if service else "status:error"
    body = {
        "data": {
            "type": "search_request",
            "attributes": {
                "filter": {
                    "from": time_from,
                    "to": time_to,
                    "query": query,
                },
                "sort": "-timestamp",
                "page": {"limit": limit},
            },
        }
    }
    try:
        resp = requests.post(
            f"{host}/api/v2/spans/events/search",
            headers=headers,
            json=body,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            traces = []
            for item in data:
                attrs = item.get("attributes", {})
                error = attrs.get("error") or {}
                traces.append(
                    {
                        "trace_id": attrs.get("trace_id") or item.get("id", ""),
                        "resource_name": attrs.get("resource_name", ""),
                        "service": attrs.get("service", service),
                        "error_message": error.get("message", ""),
                        "error_type": error.get("type", ""),
                    }
                )
            return traces
    except requests.RequestException:
        pass
    return []


def fetch_deploy_events(service: str, config: dict, time_from: str, time_to: str) -> list[dict]:
    """Find recent deploys / infra changes that may correlate with the alert."""
    if not has_datadog_auth(config):
        return []
    host = api_host(config)
    headers = datadog_headers(config)
    params = {
        "start": int(datetime.fromisoformat(time_from).timestamp()),
        "end": int(datetime.fromisoformat(time_to).timestamp()),
        "text": f"source:resource_changes service:{service}" if service else "source:resource_changes",
    }
    try:
        resp = requests.get(f"{host}/api/v1/events", headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("events", [])[:10]
    except requests.RequestException:
        pass
    return []


def extract_first_stack_frame(stack_traces: list[str]) -> tuple[str, int] | None:
    """Pull the first `at com.pharmeasy...(FileName.kt:line)` frame from stack traces."""
    for trace in stack_traces:
        match = STACK_FRAME_RE.search(trace)
        if match:
            return match.group(1), int(match.group(2))
    return None


def find_code_context(file_name: str, line_no: int, search_roots: list[str]) -> dict[str, Any]:
    """Search codebase roots for file_name and return ±50 lines around line_no."""
    for root in search_roots:
        root_path = Path(root).expanduser()
        if not root_path.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            if file_name in filenames:
                path = Path(dirpath) / file_name
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                start = max(0, line_no - 51)
                end = min(len(lines), line_no + 50)
                snippet = "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))
                return {"file": str(path), "line": line_no, "snippet": snippet[:6000]}
    return {}


def investigate_alert(alert_id: str, config: dict | None = None) -> dict[str, Any]:
    """Gather all available evidence for an alert."""
    config = config or load_config()
    alert_path = Path(__file__).resolve().parent.parent / "alerts" / f"{alert_id}.md"
    if not alert_path.exists():
        raise FileNotFoundError(f"Alert file not found: {alert_id}")

    content = alert_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    time_from, time_to = _time_window(fm.triggered_at)
    monitor = fetch_monitor(fm.monitor_id, config) if fm.monitor_id else {}
    events = fetch_alert_events(fm.monitor_id, config, time_from, time_to)
    logs = fetch_error_logs(fm.service, config, time_from, time_to)
    top_errors = aggregate_log_messages(logs)
    traces = fetch_error_traces(fm.service, config, time_from, time_to)

    deploy_from, _ = _time_window(fm.triggered_at, minutes_before=120, minutes_after=0)
    deploy_events = fetch_deploy_events(fm.service, config, deploy_from, time_to)

    stack_traces = []
    for log in logs:
        msg = log.get("message") or ""
        if "at com.pharmeasy." in msg or "Exception" in msg:
            stack_traces.append(msg[:1500])
    stack_traces = stack_traces[:3]

    code_context: dict[str, Any] = {}
    search_roots = [p.strip() for p in config.get("CODEBASE_SEARCH_PATHS", "").split(",") if p.strip()]
    frame = extract_first_stack_frame(stack_traces)
    if frame and search_roots:
        code_context = find_code_context(frame[0], frame[1], search_roots)

    return {
        "alert_id": alert_id,
        "monitor_name": fm.monitor_name,
        "service": fm.service,
        "env": fm.env,
        "triggered_at": fm.triggered_at,
        "alert_summary": body,
        "monitor": monitor,
        "events": events,
        "log_count": len(logs),
        "top_errors": top_errors,
        "stack_traces": stack_traces,
        "traces": traces,
        "deploy_events": deploy_events,
        "code_context": code_context,
        "time_window": {"from": time_from, "to": time_to},
        "datadog_available": has_datadog_auth(config),
    }
