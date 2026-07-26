#!/usr/bin/env python3
"""Read-only Google Chat access (OAuth, user credentials) — lets the pipeline read
message history from a space, since incoming webhooks can only send, not read.

One-time setup:
    python scripts/google_chat_client.py --setup

Then:
    python scripts/google_chat_client.py --space-id AAQAyoHxvpU --hours 24
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import REPO_ROOT, load_config  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/chat.messages.readonly"]
TOKEN_PATH = REPO_ROOT / "credentials" / "google_chat_token.json"


def _client_secret_path(config: dict) -> Path:
    raw = config.get("GOOGLE_CHAT_OAUTH_CLIENT_JSON", "credentials/google_chat_oauth_client.json")
    return REPO_ROOT / raw


def get_credentials(config: dict | None = None):
    """Load cached OAuth credentials, refreshing or running the consent flow as needed."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Install OAuth deps: pip install google-auth google-auth-oauthlib"
        ) from exc

    config = config or load_config()
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_secret = _client_secret_path(config)
            if not client_secret.exists():
                raise RuntimeError(
                    f"OAuth client secret not found at {client_secret}.\n"
                    "Download it from Google Cloud Console (APIs & Services > Credentials > "
                    "your OAuth client > Download JSON) and save it there, or point "
                    "GOOGLE_CHAT_OAUTH_CLIENT_JSON in config.env at wherever you saved it."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def list_recent_messages(space_id: str, hours: int = 24, config: dict | None = None) -> list[dict]:
    """Return raw Chat message dicts from `space_id` created in the last `hours`."""
    import requests

    config = config or load_config()
    creds = get_credentials(config)
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    messages: list[dict] = []
    page_token = None
    while True:
        params = {
            "filter": f'createTime > "{since}"',
            "pageSize": 100,
            "orderBy": "createTime desc",
        }
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(
            f"https://chat.googleapis.com/v1/spaces/{space_id}/messages",
            headers={"Authorization": f"Bearer {creds.token}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        messages.extend(data.get("messages", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Google Chat read-access setup / test")
    parser.add_argument("--setup", action="store_true", help="Run the one-time OAuth consent flow")
    parser.add_argument("--space-id", default=None, help="Space ID to list messages from")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    config = load_config()

    if args.setup:
        get_credentials(config)
        print(f"Authorized. Token cached at {TOKEN_PATH}")
        return 0

    space_id = args.space_id or config.get("GOOGLE_CHAT_SOURCE_SPACE_ID", "")
    if not space_id:
        print("Pass --space-id or set GOOGLE_CHAT_SOURCE_SPACE_ID in config.env", file=sys.stderr)
        return 1

    msgs = list_recent_messages(space_id, hours=args.hours, config=config)
    print(f"{len(msgs)} messages in the last {args.hours}h")
    for m in msgs[:15]:
        text = (m.get("text") or "")[:90].replace("\n", " ")
        print(f"  {m.get('createTime')}  {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
