# Summarise Alerts

Read all alert files and generate a summary report with RCA status and timing metrics.

## Usage
```
/summarise
/summarise last 7 days
/summarise service inward-edge
```

## Steps

### 1. Read all alert files
Read every `.md` file in `alert-rca-automation/alerts/` (skip `_template.md`).
Parse YAML frontmatter.

If date range specified (e.g. "last 7 days"): filter where `triggered_at` is in range.
If service filter specified (e.g. "service inward-edge"): filter where `service` matches.

### 2. Compute derived fields per alert
- **RCA time**: `rca_at` − `triggered_at` (if both present)
- **Publish lag**: `published_at` − `rca_at` (if both present)
- **Total time**: `published_at` − `triggered_at` (if both present)
- **Stale flag**: triggered but no `rca_at` and more than 1 hour since `triggered_at`
- **Missing RCA flag**: `## Root Cause Analysis` still has placeholder text
- **Unpublished flag**: RCA done but no `published_at`

### 3. Write _summary.md
Overwrite `alert-rca-automation/_summary.md`:

```markdown
# Alert RCA Summary
_Generated: {current datetime IST}_
_Filter: {filter or "All alerts"}_

## Overview
- Total alerts: {N}
- Open (no RCA): {N}
- RCA Done (unpublished): {N}
- Published: {N}
- Missing RCA: {N}

## Alert Table

| Alert ID | Monitor | Service | Status | Triggered | RCA At | Published | RCA Time | Confidence |
|----------|---------|---------|--------|-----------|--------|-----------|----------|------------|
| ...      | ...     | ...     | ...    | ...       | ...    | ...       | ...      | ...        |

## ⚠️ Flags

### Stale (triggered >1h ago, no RCA)
{list}

### Missing RCA
{list with monitor name}

### RCA Done but not Published
{list}

## Recent RCAs
{For each published alert in last 7 days, one-line root cause:}
### {alert_id} — {monitor_name}
{one-line root cause} (Confidence: {confidence})
---
```

### 4. Print confirmation
"Summary written to alert-rca-automation/_summary.md — {N} alerts processed"
Print stale, missing RCA, and unpublished alerts as immediate warnings.

## Optional — Export to CSV
If user asks, also write `alert-rca-automation/exports/summary_{date}.csv` with the alert table for Excel import.
