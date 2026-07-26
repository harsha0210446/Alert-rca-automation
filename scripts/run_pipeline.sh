#!/usr/bin/env bash
# Cron-friendly pipeline: fetch alerts → remind to analyse → publish completed RCAs
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
PYTHON="${VENV_PYTHON:-python3}"

echo "=== Alert RCA Pipeline — $(date) ==="

# Step 1: Fetch new alerting monitors from Datadog
echo "[1/3] Fetching alerts from Datadog..."
"$PYTHON" scripts/fetch_datadog_alerts.py || true

# Step 2: List alerts needing RCA
echo "[2/3] Alerts needing RCA:"
NEED_RCA=0
for f in alerts/DD-*.md; do
  [ -f "$f" ] || continue
  if grep -q "_Not yet generated" "$f" 2>/dev/null; then
    ALERT_ID=$(basename "$f" .md)
    echo "  → Run /analyse-alert $ALERT_ID"
    NEED_RCA=$((NEED_RCA + 1))
  fi
done
[ "$NEED_RCA" -eq 0 ] && echo "  (none)"

# Step 3: Auto-publish alerts with completed RCA but not yet published
echo "[3/3] Publishing completed RCAs..."
PUBLISHED=0
for f in alerts/DD-*.md; do
  [ -f "$f" ] || continue
  if ! grep -q "_Not yet generated" "$f" 2>/dev/null; then
    if grep -q "^published_at:$" "$f" 2>/dev/null || grep -q "^published_at: *$" "$f" 2>/dev/null; then
      ALERT_ID=$(basename "$f" .md)
      echo "  → Publishing $ALERT_ID"
      "$PYTHON" scripts/publish_rca.py "$ALERT_ID" && PUBLISHED=$((PUBLISHED + 1)) || true
    fi
  fi
done
echo "Published: $PUBLISHED"

echo "=== Done ==="
