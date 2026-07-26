# Create Alert From Chat

Create an alert file by pasting a Datadog alert message from Google Chat. **No Datadog API key needed.**

## Usage
```
/create-alert-from-chat
```
Or with pasted text in the conversation.

## When to use
- You receive alerts in Google Chat and don't have Datadog API/App keys
- You only have a Datadog Personal Access Token for MCP (investigation), not for polling
- Manual trigger when an alert fires

## Steps

### 1. Get the alert message
Copy the full Datadog alert message from Google Chat. It usually contains:
- Monitor name
- Service / env (optional)
- Status (Triggered/Recovered)
- Timestamp

### 2. Parse and create alert file
Run:
```bash
cd alert-rca-automation && python scripts/create_alert_from_chat.py --text "{pasted message}"
```

Or if user pasted the message in chat, parse it directly and call the same logic.

Extract:
- Monitor name (line with `Monitor:` or `**Monitor**`)
- Service (line with `Service:`)
- Env, severity, triggered time if present
- Generate Alert ID: `DD-{monitor_id}-{epoch}`

### 3. Create alert file
Create `alert-rca-automation/alerts/{alert_id}.md` with the parsed fields.
Include the original Google Chat message in the Alert Summary section for RCA context.

### 4. Update _processed_alerts.md
Append row:
| Alert ID | Monitor | Service | Status | Triggered At | RCA At | Published At |

### 5. Print next step
"Alert created: {alert_id}. Run /analyse-alert {alert_id} to investigate (uses Datadog MCP)."
