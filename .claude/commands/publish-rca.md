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
Build a concise message from the alert file:

```
🔍 RCA — {monitor_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Triggered: {triggered_at}
📦 Service: {service} | Env: {env}
🎯 Root cause: {one-line from RCA}

📊 Evidence:
   • {bullet 1 from Evidence section}
   • {bullet 2}
   • {bullet 3 max}

✅ Suggested action:
   {first suggested fix item}

🎚 Confidence: {confidence}
📄 Full report: alerts/{alert_id}.md
```

Keep under 4096 characters (Google Chat limit). Truncate evidence bullets if needed.

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
