# Monitor Filters & Datadog Config

Edit this file to configure which alerts to fetch and investigate.

## Datadog Monitor Query

Default query for `/fetch-alerts` and `fetch_datadog_alerts.py`:
```
status:alert OR status:warn
```

Add service/env filters as needed, e.g.:
```
(status:alert OR status:warn) AND service:inward-edge
(status:alert OR status:warn) AND env:prod
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
