#!/usr/bin/env python3
"""Datadog API helpers — supports Personal Access Token (no API/App keys needed)."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import load_config  # noqa: E402

SITE_TO_API_HOST = {
    "datadoghq.com": "https://api.datadoghq.com",
    "datadoghq.eu": "https://api.datadoghq.eu",
    "us3.datadoghq.com": "https://api.us3.datadoghq.com",
    "us5.datadoghq.com": "https://api.us5.datadoghq.com",
    "ap1.datadoghq.com": "https://api.ap1.datadoghq.com",
    "ap2.datadoghq.com": "https://api.ap2.datadoghq.com",
    "ddog-gov.com": "https://api.ddog-gov.com",
}


def api_host(config: dict) -> str:
    site = config.get("DD_SITE", "datadoghq.com").replace("https://", "").replace("api.", "")
    return SITE_TO_API_HOST.get(site, f"https://api.{site}")


def get_access_token(config: dict) -> str | None:
    """Return PAT/access token from config (DD_ACCESS_TOKEN or legacy DD_API_KEY if ddpat_)."""
    token = config.get("DD_ACCESS_TOKEN") or config.get("DD_PAT") or ""
    if token:
        return token
    legacy = config.get("DD_API_KEY", "")
    if legacy.startswith("ddpat_") or legacy.startswith("ddsat_"):
        return legacy
    return None


def datadog_headers(config: dict) -> dict[str, str]:
    """Build auth headers — PAT first, then API key + app key fallback."""
    token = get_access_token(config)
    if token:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    api_key = config.get("DD_API_KEY", "")
    app_key = config.get("DD_APP_KEY", "")
    if api_key and app_key:
        return {
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
            "Content-Type": "application/json",
        }

    return {"Content-Type": "application/json"}


def has_datadog_auth(config: dict) -> bool:
    return bool(get_access_token(config) or (config.get("DD_API_KEY") and config.get("DD_APP_KEY")))


def validate_auth(config: dict) -> tuple[bool, str]:
    """Test Datadog credentials. Returns (ok, message)."""
    if not has_datadog_auth(config):
        return False, "No Datadog credentials. Set DD_ACCESS_TOKEN in config.env (Personal Access Token)."

    host = api_host(config)
    headers = datadog_headers(config)
    try:
        resp = requests.get(f"{host}/api/v1/validate", headers=headers, timeout=15)
        if resp.status_code == 200:
            return True, "Datadog auth OK"
        return False, f"Datadog auth failed ({resp.status_code}): {resp.text[:200]}"
    except requests.RequestException as exc:
        return False, f"Datadog auth error: {exc}"


def search_monitors(query: str, config: dict) -> list[dict]:
    """Search monitors using PAT or API keys."""
    if not has_datadog_auth(config):
        raise RuntimeError("Set DD_ACCESS_TOKEN in config.env (your ddpat_ token)")

    host = api_host(config)
    headers = datadog_headers(config)
    resp = requests.get(
        f"{host}/api/v1/monitor/search",
        params={"query": query, "per_page": 100},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("monitors", [])
