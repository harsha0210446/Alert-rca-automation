# Full Automation Setup

When a Datadog alert lands in Google Chat → auto RCA → reply posted back to Google Chat.

**No manual copy/paste needed.**

---

## Architecture

```
Datadog alert fires
    ↓
Google Chat space (Datadog bot posts message)
    ↓
Google Chat App forwards message → your webhook server
    ↓
auto_rca.py (Datadog evidence + LLM)
    ↓
publish_rca.py → Google Chat webhook (RCA reply)
```

---

## One-time setup (3 steps)

### Step 1 — Add LLM API key to config.env

Automated RCA needs an LLM. Add **one** of these to `config.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...    # recommended
# OR
OPENAI_API_KEY=sk-...
```

Also ensure these are set:
```bash
AUTO_RCA_ENABLED=true
AUTO_PUBLISH_ENABLED=true
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/...   # already set
WEBHOOK_SECRET=my-super-secret-key                                   # already set
```

Optional (better RCA with log data):
```bash
DD_ACCESS_TOKEN=ddpat_...   # scopes: monitors_read, logs_read, timeseries_query
```

---

### Step 2 — Start the automation server

```bash
cd ~/Desktop/alert-rca-automation
source .venv/bin/activate
./scripts/start_automation.sh
```

Server runs on port **8080**.

**If running on your laptop**, expose it with ngrok:
```bash
ngrok http 8080
```
Copy the HTTPS URL (e.g. `https://abc123.ngrok.io`).

**If on a server**, use your server's public URL.

---

### Step 3 — Connect Google Chat App (this triggers automation)

This is the key step — it makes Google Chat **forward alert messages** to your server when Datadog posts them.

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable **Google Chat API**
4. Go to **Google Chat API → Configuration**
5. Fill in:
   - **App name**: `Alert RCA Bot`
   - **Avatar URL**: any image URL
   - **Description**: Auto RCA for Datadog alerts
6. Under **Connection settings**:
   - Select **HTTP endpoint URL**
   - URL: `https://YOUR-SERVER/webhook/google-chat?secret=my-super-secret-key`
     (Google Chat cannot send custom headers — put secret in URL)
7. Under **Permissions**: Bot works in spaces it's added to
8. Under **Visibility**: Make available to your org or specific people
9. **Save**
10. In Google Chat, open the space where **Datadog alerts** arrive
11. Click space name → **Apps & integrations** → **Add webhooks & apps** → add your **Alert RCA Bot**

Now when Datadog posts an alert to that space, Google Chat forwards it to your server → auto RCA → RCA posted back.

---

## Alternative: Datadog webhook (faster, bypasses Google Chat trigger)

If you can edit Datadog monitor notifications:

1. Datadog → Integrations → Webhooks → New
2. URL: `https://YOUR-SERVER/webhook/datadog`
3. Custom header: `X-Webhook-Secret: my-super-secret-key`
4. Add this webhook to your monitor notification message (alongside Google Chat)

Datadog will hit your server directly when alert fires — no Google Chat App needed for triggering.

---

## Test it

### Test 1 — Health check
```bash
curl http://localhost:8080/health
```

### Test 2 — Simulate alert
```bash
curl -X POST http://localhost:8080/webhook/google-chat \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: my-super-secret-key" \
  -d '{
    "type": "MESSAGE",
    "message": {
      "text": "Monitor: [Prod] inward-edge error rate high\nService: inward-edge\nEnv: prod\nStatus: Triggered\nTime: 2026-07-24 05:00 IST"
    }
  }'
```

You should see:
1. Server logs: `Auto-pipeline started`
2. After ~30-60 seconds: RCA message posted to Google Chat

---

## Run 24/7

**Option A — tmux/screen on server:**
```bash
tmux new -s rca
./scripts/start_automation.sh
# Ctrl+B, D to detach
```

**Option B — launchd (macOS):** create a plist to run start_automation.sh on boot.

**Option C — systemd (Linux):**
```ini
[Unit]
Description=Alert RCA Automation
After=network.target

[Service]
WorkingDirectory=/path/to/alert-rca-automation
ExecStart=/path/to/alert-rca-automation/.venv/bin/python scripts/webhook_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No RCA in Chat | Check `ANTHROPIC_API_KEY` is set |
| Server not receiving alerts | Google Chat App not added to space, or ngrok URL wrong |
| 401 on webhook | `X-Webhook-Secret` header must match `WEBHOOK_SECRET` |
| RCA says "Low confidence" | Add `DD_ACCESS_TOKEN` with logs_read scope for better evidence |
| Duplicate RCAs | Dedupe is 5 min per monitor name — adjust `DEDUPE_SECONDS` in webhook_server.py |
| Our own RCA re-triggers | Messages starting with `🔍 RCA` are auto-skipped |

---

## What runs automatically

| Step | Script | Manual? |
|------|--------|---------|
| Alert arrives | webhook_server.py | No |
| Create alert file | run_auto_pipeline.py | No |
| Fetch Datadog logs | datadog_investigate.py | No |
| Generate RCA | auto_rca.py (LLM) | No |
| Post to Google Chat | publish_rca.py | No |

**You only need the server running + Google Chat App connected.**
