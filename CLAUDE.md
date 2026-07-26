# Alert RCA Automation — Claude Code Context

## What This Is
Solo automation project for investigating Datadog monitor alerts and publishing Root Cause Analysis (RCA) to Google Chat.
Claude Code slash commands in `.claude/commands/` handle fetching alerts, RCA investigation, publishing, and summarising.

## Alert Sources
- **Primary**: Datadog monitors in `Alert` or `Warn` state, scoped to the `rio` team (polled via `/fetch-alerts`)
- **Secondary**: Google Chat messages pasted in manually via `/create-alert-from-chat` (parsed from Datadog notification format)

## Alert ID Convention
Format: `DD-{monitor_id}-{epoch}` or `DD-{monitor_id}` for recurring alerts on same monitor.
Example: `DD-167097893-1721780400`

## Datadog Investigation Flow
When analysing an alert, use Datadog MCP in this order:
1. `search_datadog_monitors` — get monitor config, query, thresholds, tags
2. `search_datadog_events` — find the alert trigger event (source:alert OR monitor)
3. `search_datadog_logs` — errors around alert time window (service from monitor tags)
4. `analyze_datadog_logs` — aggregate error counts, top messages, status codes
5. `search_datadog_spans` — find failing traces if APM enabled
6. `get_datadog_trace` — deep-dive top error trace
7. `search_datadog_events` with `source:resource_changes` — check recent deploys

Default time window: 15 minutes before alert trigger to 5 minutes after.

## Stack Trace in Logs
If logs contain Kotlin/Spring stack traces:
```
java.lang.SomeException: message
  at com.pharmeasy.service.ClassName.methodName(FileName.kt:lineNumber)
```
- Use the FIRST `at com.pharmeasy...` line as entry point
- Search codebase recursively for `FileName.kt`
- Read ±50 lines around the failing line

## Data Files (all in this folder)
| File | Purpose | Who writes |
|------|---------|------------|
| `_mappings.md` | Monitor filters & Datadog query config | You (manually) |
| `_processed_alerts.md` | Alert → status, timestamps | Auto (fetch-alerts / analyse-alert / publish-rca) |
| `alerts/{ID}.md` | Per-alert detail + RCA | Auto |
| `_summary.md` | Aggregated view | Auto (/summarise) |
| `config.env` | Datadog token, Google Chat webhook URL (gitignored) | You (manually) |

## RCA Output Convention
Every analysed alert must have these sections filled:
- **What fired** — monitor name, service, threshold breached
- **When** — trigger time, duration
- **Root cause (likely)** — plain English, grounded in evidence
- **Evidence** — log counts, trace IDs, deploy events
- **Suggested fix** — actionable next steps
- **Confidence** — High / Medium / Low

## Publishing
- **Google Chat**: POST formatted RCA to incoming webhook URL (see `config.env`)
- Run `/publish-rca {ID}` or `python scripts/publish_rca.py {ID}` after analysis

## Never Do
- Never post RCA to Google Chat without filling the RCA sections (skip publish if analysis is placeholder)
- Never re-process an alert that already exists in `_processed_alerts.md` with status `RCA Done`
- Never commit `config.env` or credentials JSON files
