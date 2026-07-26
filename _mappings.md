# Monitor Filters & Datadog Config

Edit this file to configure which alerts to fetch and investigate.

## Datadog Monitor Query

Default query for `/fetch-alerts` and `fetch_datadog_alerts.py` — scoped to the **rio team only**
(the team whose monitor notifications post to our Google Chat space):
```
(status:alert OR status:warn) AND team:rio
```

Confirmed via the Datadog monitor tags (`team:rio`) — other teams (scm-wms, scm-mp, transact,
cpc, dataplatform, tc-lab, tc-reporting, etc.) exist in the org but are out of scope for this
automation. Verified (2026-07-26) that rio-team monitors currently in Alert/Warn notify one of
two Google Chat handles configured on the monitor message: `@googlechat-P0-service-alerts` or
`@googlechat-RIO-DD-Alerts` — that's the **source** space Datadog posts raw alerts to.

RCAs are published to a **different** space, `P0-datadog-rca-alerts` (2026-07-27 —
`GOOGLE_CHAT_WEBHOOK_URL` in `config.env` now points there instead of back into the
source-alert space), so RCA output stays separate from the raw alert feed.

Other filter examples, if scope ever needs to change:
```
(status:alert OR status:warn) AND team:rio AND service:inward-edge
(status:alert OR status:warn) AND team:rio AND env:prod
```

You can also set `DD_MONITOR_QUERY` in `config.env` to override this.

## Service Filters (optional)

Use these to narrow RCA investigation scope. Leave blank to investigate all fetched alerts.

| Service        | Env   | Notes |
| -------------- | ----- | ----- |
| inward-edge    | prod  |       |
| inventory-service | prod |    |
| outward-edge   | prod  |       |
| verifier-service | prod |      |

## Monitor Name Patterns (optional)

Glob patterns to include or skip during fetch. If empty, all monitors matching the Datadog query are fetched.

| Pattern        | Action  | Notes |
| -------------- | ------- | ----- |
| *error rate*   | include |       |
| *latency*      | include |       |
| *test*         | skip    | Ignore test monitors |

## RCA Time Window

Default investigation window (used by `/analyse-alert`):
- Logs/traces: 15 minutes before alert trigger → 5 minutes after
- Deploy events: 2 hours before alert trigger

## Severity Notes

| Datadog Priority | Notes |
| ---------------- | ----- |
| P1 / SEV-1       | Investigate immediately |
| P2 / SEV-2       | Investigate within 30 min |
| P3+              | Normal queue |
