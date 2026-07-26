# Fetch Alerts

Poll Datadog for monitors currently in Alert or Warn state and create alert files for new ones.

## Steps

### 1. Load existing processed alerts
Read `alert-rca-automation/_processed_alerts.md` from the repo root.
Extract all Alert IDs already in the table — these will be skipped.

### 2. Load monitor filters
Read `alert-rca-automation/_mappings.md` for:
- Datadog monitor query (default: `status:alert OR status:warn`)
- Optional service/env filters
- Optional monitor name include/skip patterns

### 3. Fetch alerting monitors from Datadog
Use Datadog MCP `search_datadog_monitors` with query from `_mappings.md` or `config.env` (`DD_MONITOR_QUERY`).

For each monitor, extract:
- Monitor ID (e.g. `167097893`)
- Monitor name / title
- Status (`Alert`, `Warn`, `OK`, etc.)
- Tags (service, env)
- Priority (if available)
- Last triggered time

Also use `search_datadog_events`:
```
source:alert from:now-1h
```
Match events to monitors for precise trigger timestamps.

Apply include/skip patterns from `_mappings.md` if configured.

### 4. Skip already-processed alerts
For each alerting monitor, generate Alert ID: `DD-{monitor_id}-{trigger_epoch}`.
If the ID (or same monitor_id with status still Open in `_processed_alerts.md`) exists: skip.
If new: proceed to step 5.

### 5. Create alert file
For each new alert, create `alert-rca-automation/alerts/DD-{monitor_id}-{epoch}.md`:

```markdown
---
alert_id: DD-{monitor_id}-{epoch}
monitor_id: {monitor_id}
monitor_name: {monitor name}
service: {service tag or extracted from name}
env: {env tag or blank}
severity: {priority or blank}
status: Open
triggered_at: {trigger datetime IST}
rca_at:
published_at:
confidence:
source: datadog
---

## Alert Summary
**Monitor**: {monitor name}
**Status**: {Alert/Warn}
**Service**: {service}
**Env**: {env}
**Triggered**: {datetime}
**Monitor query**: {monitor query if available}

## Monitor Details
_Not yet fetched — run /analyse-alert DD-{monitor_id}-{epoch}_

## Evidence
_Not yet collected — run /analyse-alert DD-{monitor_id}-{epoch}_

## Root Cause Analysis
_Not yet generated — run /analyse-alert DD-{monitor_id}-{epoch}_

## Suggested Fix
_Pending RCA_

## Timeline
- **Triggered**: {datetime}
- **Fetched**: {current datetime IST}
- **RCA completed**:
- **Published to Chat**:
```

### 6. Update _processed_alerts.md
Append a row for each new alert:

| Alert ID | Monitor | Service | Status | Triggered At | RCA At | Published At |
| DD-{id} | {monitor name} | {service} | Open | {datetime} | | |

### 7. Print run summary
- Total monitors in Alert/Warn
- Alerts skipped (already processed)
- New alerts created (list with ID and monitor name)
- Reminder: run `/analyse-alert {ID}` for each new alert
