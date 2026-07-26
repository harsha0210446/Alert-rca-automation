# Publish RCA

Format and publish the Root Cause Analysis for an alert to Google Chat.

## Usage
```
/publish-rca DD-167097893-1721780400
```

## Steps

### 1. Verify alert file exists and RCA is complete
Read `alert-rca-automation/alerts/{alert_id}.md`.
Check that `## Root Cause Analysis` does NOT contain placeholder text (`_Not yet generated_`).

If RCA is incomplete: say "RCA not ready. Run /analyse-alert {alert_id} first." and stop.

### 2. Read config
Read `alert-rca-automation/config.env` for:
- `GOOGLE_CHAT_WEBHOOK_URL`

If config.env missing: say "Copy config.env.example to config.env and fill in credentials." and stop.

### 3. Format Google Chat message
Post the FULL RCA, not a summary — the Chat message is the complete record, nobody
should need to open the local alert file:

```
🔍 RCA — {monitor_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Triggered: {triggered_at}
📦 Service: {service} | Env: {env}
🎚 Confidence: {confidence}

🎯 Root Cause Analysis
{full Root Cause Analysis section — What fired / When / Root cause / Confidence}

📊 Evidence
{full Evidence section — log counts, top errors, traces, deploy events, code context}

✅ Suggested Fix
{full Suggested Fix section}

📄 alert_id: {alert_id}
```

Google Chat caps messages at 4096 characters. If it doesn't fit: drop the code
snippet from Evidence first (leave a note pointing to the alert file for it),
then hard-truncate as a last resort. See `format_chat_message()` in
`scripts/utils.py` for the exact logic.

### 4. Publish to Google Chat
Run:
```bash
cd alert-rca-automation && python scripts/publish_rca.py {alert_id}
```

If webhook URL is not configured: warn and stop.

### 5. Update alert file and _processed_alerts.md
- Set frontmatter: `published_at: {current datetime IST}`, `status: Published`
- Update Timeline: Published to Chat timestamp
- Update `_processed_alerts.md`: Status → `Published`, Published At → datetime

### 6. Print confirmation
"RCA published for {alert_id}."
State whether the Google Chat publish succeeded.
