# Analyse Alert

Investigate a Datadog alert using logs, traces, metrics, and events. Write a Root Cause Analysis to the alert file.

## Usage
```
/analyse-alert DD-167097893-1721780400
/analyse-alert DD-167097893
```

## Steps

### 1. Find the alert file
Look in `alert-rca-automation/alerts/` for a file matching the given ID.
If not found: say "Alert file not found. Run /fetch-alerts first or check the ID." and stop.

Read the YAML frontmatter to get: monitor_id, monitor_name, service, env, triggered_at.

### 2. Fetch monitor details
Use Datadog MCP `search_datadog_monitors` with query:
```
id:{monitor_id}
```
Extract: full monitor query, thresholds, message template, tags, priority.

Update the `## Monitor Details` section with:
- Monitor query and threshold
- Tags (service, env)
- Notification channels
- Monitor message / runbook link if present

### 3. Fetch alert trigger event
Use `search_datadog_events`:
```
source:alert monitor_id:{monitor_id}
```
Time range: from 30 minutes before `triggered_at` to now.

Extract: exact trigger time, alert message body, transition (OK→Alert, Warn→Alert).

### 4. Investigate logs
Determine time window from `_mappings.md` (default: 15 min before trigger to 5 min after).

Use `search_datadog_logs` with filter:
```
service:{service} status:error
```
If no service tag, use monitor query tags or parse service from monitor name.

Use `analyze_datadog_logs` for aggregations:
```sql
SELECT status, count(*) FROM logs GROUP BY status ORDER BY count(*) DESC
SELECT message, count(*) FROM logs GROUP BY message ORDER BY count(*) DESC LIMIT 10
```

Look for:
- Error message patterns
- Stack traces (`at com.pharmeasy.`)
- HTTP status code spikes
- Sudden volume changes

### 5. Investigate traces (if APM enabled)
Use `search_datadog_spans`:
```
service:{service} status:error
```
Same time window. Get top failing trace IDs.

Use `get_datadog_trace` on the most frequent error trace.
Extract: exception type, entry point, latency breakdown.

### 6. Check recent deploys / infra changes
Use `search_datadog_events`:
```
source:resource_changes service:{service}
```
Time range: 2 hours before trigger to trigger time.
Note any deploys, config changes, or scaling events.

### 7. Codebase investigation (if stack trace found)
If logs or traces contain `at com.pharmeasy.` lines:
- Extract FileName.kt and line number from FIRST pharmeasy frame
- Search recursively across all microservice folders for the file
- Read ±50 lines around the failing line
- Include findings in RCA

### 8. Generate Root Cause Analysis
Write to `## Root Cause Analysis` covering:

**What fired**
- Monitor name, what metric/condition breached, threshold vs actual value

**When**
- Trigger time, how long in alert state, any flapping

**Root cause (likely)**
- Plain English explanation grounded in evidence
- Flag uncertainty explicitly if inconclusive

**Evidence**
- Log error counts and top messages
- Trace IDs and exception types
- Deploy/change events correlated in time
- Code-level findings if stack trace analysed

**Confidence**: High / Medium / Low — with one-line justification

Write to `## Suggested Fix`:
- Immediate mitigation steps
- Longer-term fix if code change needed

### 9. Update alert file
- Replace placeholder sections with generated content
- Set frontmatter: `rca_at: {current datetime IST}`, `confidence: {High/Medium/Low}`, `status: RCA Done`
- Update `## Timeline` RCA completed timestamp
- Update `_processed_alerts.md` row: Status → `RCA Done`, RCA At → datetime

### 10. Ask about publishing
Ask: "Publish RCA to Google Chat? (yes/no)"
If yes: run `/publish-rca {alert_id}` logic inline or tell user to run it.
If no: skip.

### 11. Print confirmation
"RCA complete for {alert_id}. File updated at alert-rca-automation/alerts/{alert_id}.md"
Include one-line root cause summary.
