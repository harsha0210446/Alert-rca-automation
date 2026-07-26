#!/usr/bin/env python3
"""Test Datadog authentication (PAT or API keys)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datadog_client import get_access_token, has_datadog_auth, validate_auth  # noqa: E402
from utils import load_config  # noqa: E402


def main() -> int:
    config = load_config()

    if not has_datadog_auth(config):
        print("❌ No Datadog credentials found.")
        print()
        print("Option 1 — Personal Access Token (recommended, no API/App keys):")
        print("  Set DD_ACCESS_TOKEN=ddpat_... in config.env")
        print()
        print("Option 2 — Skip Datadog API entirely:")
        print("  Use create_alert_from_chat.py when alerts arrive in Google Chat")
        print("  Use /analyse-alert in Cursor (Datadog MCP handles investigation)")
        return 1

    token = get_access_token(config)
    if token:
        print(f"Using Personal Access Token: {token[:12]}...")
    else:
        print("Using DD_API_KEY + DD_APP_KEY")

    ok, msg = validate_auth(config)
    if ok:
        print(f"✓ {msg}")
        return 0
    print(f"❌ {msg}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
