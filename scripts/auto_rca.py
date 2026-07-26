#!/usr/bin/env python3
"""Generate RCA using LLM from Datadog evidence and write to alert file."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datadog_investigate import investigate_alert  # noqa: E402
from utils import (  # noqa: E402
    REPO_ROOT,
    extract_section,
    load_config,
    now_ist,
    parse_frontmatter,
    serialize_frontmatter,
    update_processed_alert_status,
)

RCA_PROMPT = """You are a production SRE investigating a Datadog alert. Write a concise Root Cause Analysis.

## Alert
Monitor: {monitor_name}
Service: {service}
Env: {env}
Triggered: {triggered_at}

## Alert Message
{alert_summary}

## Datadog Evidence
Monitor config: {monitor_json}
Alert events: {events_json}
Error log count: {log_count}
Top error messages: {top_errors}
Stack traces: {stack_traces}
Failing traces (APM): {traces_json}
Deploy / infra change events (2h before trigger): {deploy_events_json}
Code context at failing line (if found in codebase): {code_context}

Write the response in EXACTLY this markdown format (fill all sections):

## Root Cause Analysis

**What fired**
(one paragraph)

**When**
(one paragraph)

**Root cause (likely)**
(one paragraph — be specific, cite evidence)

**Evidence**
- (bullet 1)
- (bullet 2)
- (bullet 3)

**Confidence**: High / Medium / Low — (one line reason)

## Suggested Fix

- (immediate action)
- (longer-term fix if needed)

Keep it factual. If evidence is insufficient, say so and set Confidence to Low.
"""


def call_anthropic(prompt: str, config: dict) -> str:
    api_key = config.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("Set ANTHROPIC_API_KEY in config.env for automated RCA")

    model = config.get("LLM_MODEL", "claude-sonnet-4-20250514")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


def call_openai(prompt: str, config: dict) -> str:
    api_key = config.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY or ANTHROPIC_API_KEY in config.env")

    model = config.get("LLM_MODEL", "gpt-4o")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def generate_rca_text(evidence: dict, config: dict) -> str:
    prompt = RCA_PROMPT.format(
        monitor_name=evidence.get("monitor_name", "Unknown"),
        service=evidence.get("service", "unknown"),
        env=evidence.get("env", "unknown"),
        triggered_at=evidence.get("triggered_at", "unknown"),
        alert_summary=evidence.get("alert_summary", "")[:3000],
        monitor_json=json.dumps(evidence.get("monitor", {}), default=str)[:2000],
        events_json=json.dumps(evidence.get("events", []), default=str)[:2000],
        log_count=evidence.get("log_count", 0),
        top_errors=json.dumps(evidence.get("top_errors", [])),
        stack_traces=json.dumps(evidence.get("stack_traces", []))[:3000],
        traces_json=json.dumps(evidence.get("traces", []), default=str)[:2000],
        deploy_events_json=json.dumps(evidence.get("deploy_events", []), default=str)[:2000],
        code_context=json.dumps(evidence.get("code_context", {}), default=str)[:4000],
    )

    if config.get("ANTHROPIC_API_KEY"):
        return call_anthropic(prompt, config)
    if config.get("OPENAI_API_KEY"):
        return call_openai(prompt, config)
    raise RuntimeError("Set ANTHROPIC_API_KEY or OPENAI_API_KEY in config.env")


def extract_confidence(rca_text: str) -> str:
    match = re.search(r"\*\*Confidence\*\*:\s*(High|Medium|Low)", rca_text, re.I)
    return match.group(1).capitalize() if match else "Medium"


def write_rca_to_alert(alert_id: str, rca_text: str, evidence: dict) -> None:
    alert_path = REPO_ROOT / "alerts" / f"{alert_id}.md"
    content = alert_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    # Build evidence section
    evidence_lines = [
        f"- Error logs in window: **{evidence.get('log_count', 0)}**",
        f"- Time window: {evidence.get('time_window', {}).get('from', '')} → {evidence.get('time_window', {}).get('to', '')}",
    ]
    for msg, count in evidence.get("top_errors", [])[:5]:
        evidence_lines.append(f"- `{count}x` {msg[:120]}")
    if evidence.get("stack_traces"):
        evidence_lines.append(f"- Stack trace found in logs ({len(evidence['stack_traces'])} match(es))")

    traces = evidence.get("traces", [])
    if traces:
        evidence_lines.append(f"- Failing APM traces: **{len(traces)}** — top trace_id `{traces[0].get('trace_id', '')}`")

    deploy_events = evidence.get("deploy_events", [])
    if deploy_events:
        evidence_lines.append(f"- Deploy/infra change events in prior 2h: **{len(deploy_events)}** (check for correlation)")

    code_context = evidence.get("code_context") or {}
    if code_context.get("file"):
        evidence_lines.append(f"- Code context found: `{code_context['file']}:{code_context['line']}`")
        evidence_lines.append(f"\n```\n{code_context['snippet']}\n```")

    evidence_section = "\n".join(evidence_lines)

    # Replace placeholder sections
    monitor_details = ""
    mon = evidence.get("monitor", {})
    if mon:
        monitor_details = f"""**Query**: `{mon.get('query', 'N/A')}`
**Type**: {mon.get('type', 'N/A')}
**Message**: {mon.get('message', 'N/A')[:500]}
**Auto-investigated at**: {now_ist()}"""

    body = re.sub(
        r"## Monitor Details\n.*?(?=\n## Evidence)",
        lambda _m: f"## Monitor Details\n{monitor_details or '_Datadog monitor details unavailable_'}\n",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"## Evidence\n.*?(?=\n## Root Cause Analysis)",
        lambda _m: f"## Evidence\n{evidence_section}\n",
        body,
        flags=re.DOTALL,
    )

    # Append RCA sections from LLM output
    if "## Root Cause Analysis" in rca_text:
        rca_part = rca_text[rca_text.index("## Root Cause Analysis"):]
    else:
        rca_part = f"## Root Cause Analysis\n{rca_text}"

    rca_replacement = rca_part.split("## Suggested Fix")[0].strip() + "\n\n"
    body = re.sub(
        r"## Root Cause Analysis\n.*?(?=\n## Suggested Fix|\Z)",
        lambda _m: rca_replacement,
        body,
        flags=re.DOTALL,
    )

    if "## Suggested Fix" in rca_text:
        fix_part = rca_text[rca_text.index("## Suggested Fix"):]
        body = re.sub(r"## Suggested Fix\n.*", lambda _m: fix_part.strip(), body, flags=re.DOTALL)

    fm.rca_at = now_ist()
    fm.confidence = extract_confidence(rca_text)
    fm.status = "RCA Done"

    if "- **RCA completed**:" in body:
        body = body.replace("- **RCA completed**:", f"- **RCA completed**: {fm.rca_at}")

    alert_path.write_text(serialize_frontmatter(fm, body), encoding="utf-8")
    update_processed_alert_status(alert_id, status="RCA Done", rca_at=fm.rca_at)


def run_auto_rca(alert_id: str, config: dict | None = None) -> str:
    """Full auto RCA: investigate → LLM → write to file. Returns alert_id."""
    config = config or load_config()
    print(f"[auto-rca] Investigating {alert_id}...")
    evidence = investigate_alert(alert_id, config)
    print(f"[auto-rca] Found {evidence.get('log_count', 0)} error logs, generating RCA...")
    rca_text = generate_rca_text(evidence, config)
    write_rca_to_alert(alert_id, rca_text, evidence)
    print(f"[auto-rca] RCA written for {alert_id}")
    return alert_id


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/auto_rca.py DD-xxxxx", file=sys.stderr)
        return 1
    alert_id = sys.argv[1]
    try:
        run_auto_rca(alert_id)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
