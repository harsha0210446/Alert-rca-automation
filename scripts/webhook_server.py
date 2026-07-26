#!/usr/bin/env python3
"""
Automation server — receives alerts and auto-runs RCA → Google Chat.

Endpoints:
  POST /webhook/google-chat   ← Google Chat App (when Datadog posts alert to space)
  POST /webhook/datadog       ← Datadog custom webhook (optional, faster)
  GET  /health

Usage:
    python scripts/webhook_server.py
    ./scripts/start_automation.sh
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from create_alert_from_chat import parse_chat_alert_text  # noqa: E402
from run_auto_pipeline import run_pipeline  # noqa: E402
from utils import load_config, load_processed_alert_ids, now_ist  # noqa: E402

# Dedupe: don't re-process same monitor within N seconds
_recent_monitors: dict[str, float] = {}
DEDUPE_SECONDS = 300


def is_our_rca_message(text: str) -> bool:
    """Skip messages we posted (RCA replies)."""
    return text.strip().startswith("🔍 RCA") or "Full report: alerts/DD-" in text


def is_datadog_alert(text: str) -> bool:
    """Heuristic: is this a Datadog alert message?"""
    lower = text.lower()
    keywords = ("monitor", "triggered", "alert", "warn", "recovered", "datadog")
    return any(k in lower for k in keywords)


def should_process(monitor_name: str) -> bool:
    """Dedupe by monitor name within DEDUPE_SECONDS."""
    key = monitor_name.lower().strip()
    if not key or key == "unknown monitor":
        return True
    now = time.time()
    last = _recent_monitors.get(key, 0)
    if now - last < DEDUPE_SECONDS:
        return False
    _recent_monitors[key] = now
    return True


def parse_datadog_payload(payload: dict) -> dict | None:
    if "alert_type" in payload or "event_type" in payload:
        monitor_id = str(payload.get("alert_id") or payload.get("monitor_id") or payload.get("id") or "")
        body = payload.get("body") or payload.get("text") or payload.get("event_msg") or ""
        return {
            "monitor_id": monitor_id,
            "monitor_name": payload.get("title") or payload.get("alert_title") or payload.get("monitor_name") or "Unknown Monitor",
            "service": _extract_tag(payload, "service"),
            "env": _extract_tag(payload, "env"),
            "severity": str(payload.get("priority") or payload.get("alert_priority") or ""),
            "message": body,
            "triggered_at": payload.get("date") or payload.get("last_updated") or now_ist(),
            "query": payload.get("query") or "",
        }

    if "monitor" in payload:
        mon = payload["monitor"]
        return {
            "monitor_id": str(mon.get("id", "")),
            "monitor_name": mon.get("name", "Unknown Monitor"),
            "service": _extract_tag(mon, "service"),
            "env": _extract_tag(mon, "env"),
            "severity": str(mon.get("priority") or ""),
            "message": payload.get("message", ""),
            "triggered_at": payload.get("timestamp") or now_ist(),
            "query": mon.get("query", ""),
        }
    return None


def _extract_tag(source: dict, key: str) -> str:
    tags = source.get("tags") or source.get("tag") or []
    if isinstance(tags, str):
        tags = tags.split(",")
    for tag in tags:
        if isinstance(tag, str) and tag.startswith(f"{key}:"):
            return tag.split(":", 1)[1]
    return source.get(key, "")


def parse_google_chat_payload(payload: dict) -> dict | None:
    """Parse Google Chat App MESSAGE event."""
    # Google Chat App format
    if payload.get("type") == "MESSAGE":
        message = payload.get("message", {})
        text = message.get("text") or message.get("argumentText") or ""
        if not text or is_our_rca_message(text):
            return None
        if not is_datadog_alert(text):
            return None
        parsed = parse_chat_alert_text(text)
        parsed["message"] = text
        return parsed

    # Simple format (manual test)
    message = payload.get("message", {})
    text = message.get("text") or payload.get("text") or ""
    if text and not is_our_rca_message(text) and is_datadog_alert(text):
        parsed = parse_chat_alert_text(text)
        parsed["message"] = text
        return parsed

    return None


def trigger_auto_pipeline(alert_data: dict) -> None:
    """Run pipeline in background thread."""
    monitor = alert_data.get("monitor_name", "Unknown Monitor")
    if not should_process(monitor):
        print(f"[webhook] Skipping duplicate alert for: {monitor}")
        return

    def _run():
        print(f"[webhook] Auto-pipeline started for: {monitor}")
        result = run_pipeline(alert_data=alert_data)
        print(f"[webhook] Auto-pipeline finished: {result}")

    threading.Thread(target=_run, daemon=True).start()


class WebhookHandler(BaseHTTPRequestHandler):
    config = load_config()

    def _check_auth(self) -> bool:
        secret = self.config.get("WEBHOOK_SECRET", "")
        if not secret:
            return True
        if self.headers.get("X-Webhook-Secret", "") == secret:
            return True
        # Google Chat App cannot set custom headers — use ?secret= in URL
        qs = parse_qs(urlparse(self.path).query)
        if qs.get("secret", [""])[0] == secret:
            return True
        return False

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._send_json(200, {"status": "ok", "time": now_ist()})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._check_auth():
            self._send_json(401, {"error": "unauthorized"})
            return

        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        if path == "/webhook/datadog":
            alert_data = parse_datadog_payload(payload)
        elif path == "/webhook/google-chat":
            alert_data = parse_google_chat_payload(payload)
        else:
            self._send_json(404, {"error": f"unknown endpoint: {path}"})
            return

        if not alert_data:
            self._send_json(200, {"status": "ignored", "reason": "not an alert message"})
            return

        # Respond immediately, process in background
        trigger_auto_pipeline(alert_data)
        self._send_json(200, {
            "status": "accepted",
            "monitor": alert_data.get("monitor_name"),
            "message": "Auto RCA pipeline started",
        })

    def log_message(self, fmt: str, *args) -> None:
        print(f"[webhook] {self.address_string()} {fmt % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Alert RCA automation server")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    config = load_config()
    port = args.port or int(config.get("WEBHOOK_PORT", "8080"))

    # Validate config on startup
    if not config.get("ANTHROPIC_API_KEY") and not config.get("OPENAI_API_KEY"):
        print("⚠ WARNING: Set ANTHROPIC_API_KEY or OPENAI_API_KEY in config.env for auto RCA")
    if not config.get("GOOGLE_CHAT_WEBHOOK_URL"):
        print("⚠ WARNING: Set GOOGLE_CHAT_WEBHOOK_URL in config.env to publish RCA")

    server = HTTPServer((args.host, port), WebhookHandler)
    print("=" * 60)
    print("  Alert RCA Automation Server")
    print("=" * 60)
    print(f"  Listening: http://{args.host}:{port}")
    print(f"  POST /webhook/google-chat  ← connect Google Chat App here")
    print(f"  POST /webhook/datadog      ← optional Datadog webhook")
    print(f"  GET  /health")
    print("=" * 60)
    print("  Waiting for alerts...")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
