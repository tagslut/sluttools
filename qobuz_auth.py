#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
qobuz_auth.py — dead-simple Qobuz auth helper

- Stores a user_auth_token in ~/.config/qobuz/session.json
- Two auth paths:
  1) login (email/password/app_id)
  2) paste (paste an already-captured user_auth_token)
- Minimal CLI:
    python qobuz_auth.py login
    python qobuz_auth.py paste
    python qobuz_auth.py status
    python qobuz_auth.py print
    python qobuz_auth.py clear

Env vars (optional, override prompts):
  QOBUZ_EMAIL, QOBUZ_PASSWORD, QOBUZ_APP_ID, QOBUZ_USER_AUTH_TOKEN
"""

import getpass
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import certifi
import requests

# Use one session pinned to certifi CA bundle
session = requests.Session()
session.verify = certifi.where()

# Compute config dir robustly
_HOME = Path(os.path.expanduser("~"))
_XDG = os.environ.get("XDG_CONFIG_HOME", str(_HOME / ".config"))
CONF_DIR = Path(_XDG) / "qobuz"
CONF_DIR.mkdir(parents=True, exist_ok=True)
SESSION_FILE = CONF_DIR / "session.json"

API_BASE = "https://www.qobuz.com/api.json/0.2"


def _http_get(url: str, timeout=15):
    try:
        r = session.get(url, timeout=timeout, headers={"User-Agent": "qobuz-auth/1.0"})
        r.raise_for_status()
        return r.text
    except requests.exceptions.HTTPError as e:
        # Re-raise with similar shape to previous handling
        raise RuntimeError(f"HTTP error: {e.response.status_code} {e.response.reason}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error: {e}")


def save_session(token: str, app_id: Optional[str] = None):
    payload = {
        "user_auth_token": token,
        "app_id": app_id or "",
        "saved_at": int(time.time()),
    }
    SESSION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_session():
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_session():
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
        return True
    except Exception:
        return False


def login_flow():
    email = os.environ.get("QOBUZ_EMAIL") or input("Qobuz email: ").strip()
    app_id = os.environ.get("QOBUZ_APP_ID") or input("Qobuz app_id: ").strip()
    pwd = os.environ.get("QOBUZ_PASSWORD") or getpass.getpass("Qobuz password: ")

    if not email or not app_id or not pwd:
        print("Missing email/app_id/password.", file=sys.stderr)
        sys.exit(2)

    # Public web API login (no signature required for this call)
    qs = urlencode({"email": email, "password": pwd, "app_id": app_id})
    url = f"{API_BASE}/user/login?{qs}"

    raw = ""
    try:
        raw = _http_get(url)
        obj = json.loads(raw)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("Login response was not JSON (unexpected).", file=sys.stderr)
        if raw:
            print(raw[:300], file=sys.stderr)
        sys.exit(1)

    token = obj.get("user", {}).get("user_auth_token") or obj.get("user_auth_token")
    if not token:
        # Some error payloads embed a message
        msg = obj.get("message") or obj.get("error") or "No token in response."
        print(f"Login failed: {msg}", file=sys.stderr)
        sys.exit(1)

    save_session(token, app_id)
    print("✓ Logged in and cached token.")
    return token


def paste_flow():
    existing = (
        os.environ.get("QOBUZ_USER_AUTH_TOKEN")
        or input("Paste user_auth_token: ").strip()
    )
    if not existing:
        print("No token provided.", file=sys.stderr)
        sys.exit(2)
    app_id = (
        os.environ.get("QOBUZ_APP_ID")
        or input("Optional app_id (press Enter to skip): ").strip()
    )
    save_session(existing, app_id or None)
    print("✓ Token saved.")
    return existing


def status_flow():
    s = load_session()
    if not s:
        print("No cached session.")
        return 1
    print("Cached session:")
    print(json.dumps(s, indent=2))
    # Optionally check if token is still accepted by a cheap endpoint.
    token = s.get("user_auth_token")
    app_id = s.get("app_id") or ""
    if not token:
        print("No token in cache.", file=sys.stderr)
        return 2
    # A benign check: fetch current user (works with token; app_id is commonly required)
    try:
        qs = urlencode({"user_auth_token": token, "app_id": app_id})
        url = f"{API_BASE}/user/get?{qs}"
        raw2 = _http_get(url)
        obj = json.loads(raw2)
        if obj.get("id") or obj.get("user"):
            print("✓ Token appears valid.")
            return 0
        else:
            print("Token check returned unexpected payload.")
            return 3
    except Exception as e:
        print(f"Token check failed: {e}")
        return 4


def print_flow():
    s = load_session()
    if not s or not s.get("user_auth_token"):
        print("No cached token.")
        return 1
    print(s["user_auth_token"])
    return 0


def main(argv):
    if len(argv) < 2:
        print("Usage: python qobuz_auth.py [login|paste|status|print|clear]")
        return 2
    cmd = argv[1].lower().strip()
    if cmd == "login":
        login_flow()
        return 0
    elif cmd == "paste":
        paste_flow()
        return 0
    elif cmd == "status":
        return status_flow()
    elif cmd == "print":
        return print_flow()
    elif cmd == "clear":
        ok = clear_session()
        print("✓ Cleared." if ok else "Could not clear file.")
        return 0 if ok else 1
    else:
        print("Unknown command.")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
