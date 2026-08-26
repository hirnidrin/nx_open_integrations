#!/usr/bin/env python3
# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""
Nx VMS REST Server API sample: log in to ONE site and list BOOKMARKS for one
or more devices, newest-created first.

Direct-to-server only, same auth flow as ../rest-list-cameras:

  1. Log in:  POST /rest/v4/login/sessions  {username, password}  -> {"token": ...}
  2. List:    GET  /rest/v4/devices/{deviceId}/bookmarks  (Authorization: Bearer <token>)
              ?_orderBy=creationTimeMs&order=desc (always, newest first)
              [&startTimeMs=<ms>] [&endTimeMs=<ms>] [&limit=<n>]
  3. Log out: DELETE /rest/v4/login/sessions/<token>   (clean up the session)

--device-ids accepts one or several device ids, comma-separated. Each is
fetched independently: one device failing (bad id, no permission, ...) is
reported but does not stop the rest from being listed.

This sample is READ-ONLY: it lists bookmarks. Creating/editing/deleting
bookmarks is not covered here.

Connecting to the server:
  --host is the server, e.g. https://192.168.1.10:7001  (note the https + port).
  Local servers usually present a self-signed certificate, so for a lab server
  you will typically need --insecure.

Reference: https://meta.nxvms.com/doc/developers/api-tool/main?type=1
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

import requests


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class AuthError(Exception):
    """Raised when the server rejects the credentials or token."""


class ApiError(Exception):
    """Raised for any other unexpected API/network failure."""


# ---------------------------------------------------------------------------
# Parsing helpers (pure functions = easy to test)
# ---------------------------------------------------------------------------

_DIGITS_RE = re.compile(r"^\d+$")


def parse_device_ids(raw):
    """Split a comma-separated device-id string into a non-empty list."""
    text = "" if raw is None else str(raw)
    ids = [part.strip() for part in text.split(",")]
    ids = [part for part in ids if part]
    if not ids:
        raise ApiError("--device-ids must contain at least one device id.")
    return ids


def parse_time_bound(value, flag_name):
    """Parse an optional --start/--end value into epoch ms, or None if unset.

    Accepts an ISO 8601 string (2026-06-15T12:00:00Z) or a raw epoch-ms number.
    Empty/blank/None -> None. Naive times are treated as UTC.
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    if _DIGITS_RE.match(text):
        return int(text)
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(
            f'Could not parse {flag_name} "{text}". Use ISO time or epoch ms.'
        ) from exc
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return int(when.timestamp() * 1000)


def parse_limit(value):
    """Validate an optional --limit. None/blank -> None (no limit)."""
    if value is None or str(value).strip() == "":
        return None
    try:
        number = int(str(value).strip())
    except ValueError as exc:
        raise ApiError(f'--limit must be a positive integer (got "{value}").') from exc
    if number <= 0:
        raise ApiError(f'--limit must be a positive integer (got "{value}").')
    return number


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def format_bookmarks_json(bookmarks):
    """Pretty-print the full bookmark records exactly as the API returned them."""
    return json.dumps(bookmarks, indent=2)


# ---------------------------------------------------------------------------
# Configuration (CLI > env > .env)
# ---------------------------------------------------------------------------

def load_env_file(path=".env"):
    """Read a simple KEY=VALUE .env file into a dict. Missing file -> {}."""
    values = {}
    if not path or not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_config(cli_args, env_file_values):
    """CLI flag > OS environment variable > .env file."""

    def pick(cli_value, env_key):
        if cli_value is not None:
            return cli_value
        if os.environ.get(env_key):
            return os.environ[env_key]
        return env_file_values.get(env_key)

    raw_device_ids = pick(cli_args.device_ids, "NX_DEVICE_IDS")
    device_ids = parse_device_ids(raw_device_ids) if raw_device_ids is not None else []

    return {
        "host": pick(cli_args.host, "NX_SERVER_HOST"),
        "user": pick(cli_args.user, "NX_SERVER_USER"),
        "password": pick(cli_args.password, "NX_SERVER_PASSWORD"),
        "device_ids": device_ids,
        "start_ms": parse_time_bound(cli_args.start, "--start"),
        "end_ms": parse_time_bound(cli_args.end, "--end"),
        "limit": parse_limit(cli_args.limit),
    }


def missing_fields(config):
    """Which required fields are missing."""
    required = ("host", "user", "password", "device_ids")
    return [name for name in required if not config[name]]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

# API version path segment. v4 is the latest Nx REST API.
API = "/rest/v4"


class NxServerClient:
    """Talks to a single VMS server using bearer-token auth."""

    def __init__(self, host, user, password, verify_tls=True, session=None, timeout=15):
        self.host = (host or "").rstrip("/")
        self.user = user
        self.password = password
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.verify = verify_tls
        if not verify_tls:
            # We deliberately skipped TLS verification (--insecure, for lab
            # servers with self-signed certs), so silence urllib3's repeated
            # InsecureRequestWarning instead of printing it on every request.
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass
        self.token = None

    def login(self):
        """POST credentials, receive a bearer token, remember it."""
        url = f"{self.host}{API}/login/sessions"
        body = {"username": self.user, "password": self.password, "setCookie": False}
        try:
            response = self.session.post(url, json=body, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"Could not reach {url}: {exc}") from exc
        if response.status_code in (401, 403):
            raise AuthError(
                f"Login unauthorized (HTTP {response.status_code}). Check the "
                "username/password, and that you are using a local (not cloud) user.")
        if not response.ok:
            raise ApiError(f"Login failed: HTTP {response.status_code} "
                           f"{response.text[:200]}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError("Login response was not valid JSON.") from exc
        self.token = data.get("token")
        if not self.token:
            raise ApiError("Login response did not contain a token.")
        return self.token

    def _auth_header(self):
        if not self.token:
            raise ApiError("Not logged in. Call login() first.")
        return {"Authorization": f"Bearer {self.token}"}

    def get_device_bookmarks(self, device_id, start_ms=None, end_ms=None, limit=None):
        """GET one device's bookmarks, newest-created first. Returns a list."""
        from urllib.parse import quote, urlencode
        path = f"{self.host}{API}/devices/{quote(str(device_id), safe='')}/bookmarks"
        params = [("_orderBy", "creationTimeMs"), ("order", "desc")]
        if start_ms is not None:
            params.append(("startTimeMs", str(start_ms)))
        if end_ms is not None:
            params.append(("endTimeMs", str(end_ms)))
        if limit is not None:
            params.append(("limit", str(limit)))
        url = f"{path}?{urlencode(params)}"
        try:
            response = self.session.get(
                url, headers=self._auth_header(), timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"Could not reach {url}: {exc}") from exc
        if response.status_code in (401, 403):
            raise AuthError(
                f"Bookmarks request unauthorized (HTTP {response.status_code}) "
                f"for device {device_id}.")
        if not response.ok:
            raise ApiError(f"Bookmarks for device {device_id} failed: "
                           f"HTTP {response.status_code} {response.text[:200]}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError(f"Bookmarks response for device {device_id} was not "
                           "valid JSON.") from exc
        # Some Nx versions wrap the array in a {"reply": [...]} envelope.
        if isinstance(data, dict) and isinstance(data.get("reply"), list):
            return data["reply"]
        return data if isinstance(data, list) else []

    def logout(self):
        """DELETE the session so the token cannot be reused. Best-effort."""
        if not self.token:
            return
        url = f"{self.host}{API}/login/sessions/{self.token}"
        try:
            self.session.delete(url, headers=self._auth_header(), timeout=self.timeout)
        except requests.exceptions.RequestException:
            pass  # Logout is cleanup; never let it crash the program.
        finally:
            self.token = None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Log in to one Nx VMS server and list bookmarks (newest "
                    "first) for one or more devices.")
    parser.add_argument("--host", default=None,
                        help="Server URL, e.g. https://192.168.1.10:7001")
    parser.add_argument("--user", default=None, help="Local server username")
    parser.add_argument("--password", default=None, help="Local server password")
    parser.add_argument("--device-ids", default=None,
                        help="One or more device ids, comma-separated")
    parser.add_argument("--start", default=None,
                        help="Only bookmarks starting at/after this time "
                             "(ISO 8601 or epoch ms)")
    parser.add_argument("--end", default=None,
                        help="Only bookmarks starting at/before this time "
                             "(ISO 8601 or epoch ms)")
    parser.add_argument("--limit", default=None,
                        help="Max bookmarks per device, e.g. --limit 1 for "
                             "just the most recent one")
    parser.add_argument("--env-file", default=".env", help="Path to a .env file")
    parser.add_argument("--insecure", action="store_true",
                        help="Skip TLS verification (usually needed for local servers)")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)

    try:
        config = resolve_config(args, load_env_file(args.env_file))
    except ApiError as exc:
        print(f"{exc}", file=sys.stderr)
        return 2

    missing = missing_fields(config)
    if missing:
        print("Missing config: " + ", ".join(missing) +
              ".\nProvide via flags or .env (copy .env.example). See the README.",
              file=sys.stderr)
        return 2

    client = NxServerClient(
        host=config["host"], user=config["user"], password=config["password"],
        verify_tls=not args.insecure,
    )

    any_failed = False
    try:
        client.login()
        print(f"Logged in to {config['host']} as {config['user']}\n")
        for device_id in config["device_ids"]:
            try:
                bookmarks = client.get_device_bookmarks(
                    device_id, start_ms=config["start_ms"], end_ms=config["end_ms"],
                    limit=config["limit"])
                print(f"{device_id}:")
                print(format_bookmarks_json(bookmarks))
                print()
            except (AuthError, ApiError) as exc:
                any_failed = True
                print(f"{device_id}: FAILED: {exc}", file=sys.stderr)
        return 1 if any_failed else 0
    except AuthError as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1
    except ApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.logout()


if __name__ == "__main__":
    sys.exit(main())
